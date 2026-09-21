/**
 * strategy-normalize.js
 *
 * Re-backtest every raw strategy in strategies/ on the FROZEN harness window
 * (default: TRAIN) with the harness objective, producing an apples-to-apples
 * "what actually works under one regime" ledger. See docs/enhance-schema.md §11.
 *
 * Cost normalization (forced): a wrapper is APPENDED to each strategy's source so
 * that any set_slippage/set_commission it calls — even per-bar via set_slip_fee —
 * is overridden to the frozen harness (zero slippage + PerTrade(万3/万13/5)).
 * The raw file in strategies/ is NEVER modified; a normalized copy is written to a
 * temp dir and fed to Pipeline 2.
 *
 * Resumable: results append to harness/normalize-<window>.tsv; strategies already
 * carrying a terminal status are skipped on re-run.
 *
 * Usage:
 *   node utils/strategy-normalize.js [--window train|val]   (normalization uses train;
 *                                    2025+ is OOS-BLOCKED by the executor)
 *                                    [--filter <substr>] [--limit N] [--dry-run]
 */

const fs   = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT       = path.resolve(__dirname, '..');
const STRAT_DIR  = path.join(ROOT, 'strategies');
const TMP_DIR    = '/tmp/jq-normalize';
const POST_BT    = path.join(__dirname, 'strategy-post-backtest.js');
const SHARPE_GATE = 2.5;
// Child MAX_POLL safety cap in MINUTES ("slow-skip"). Precedence: --max-poll-min flag >
// JQ_MAX_POLL_MS env > child default (20). Forwarded to the child as a plain CLI arg so no
// JQ_MAX_POLL_MS=… env prefix is needed (that prefix breaks the allowlist and forces approval).
// The parent timeout must exceed the child MAX_POLL_MS + cancel-retry overhead, else the child
// is killed mid-poll → the backtest orphans → jams slots → rate-limit cascade.
function resolveMaxPollMin(opt) {
  if (opt['max-poll-min'] != null) { const m = parseInt(opt['max-poll-min'], 10); if (m > 0) return m; }
  if (process.env.JQ_MAX_POLL_MS) { const m = Math.round(parseInt(process.env.JQ_MAX_POLL_MS, 10) / 60000); if (m > 0) return m; }
  return 20;   // matches strategy-post-backtest.js default
}

// ── Frozen-harness cost override (appended to each strategy; raw file untouched) ──
// Redefining set_slippage/set_commission at module scope shadows the JQ builtins,
// so every call the strategy makes (initialize OR before_trading_start/handle_data)
// resolves to our override. Python resolves globals at call time, so this catches
// per-bar re-sets (e.g. set_slip_fee). initialize is also wrapped for use_real_price.
const OVERRIDE = `

# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====
`;

function parseArgs(argv) {
  const opt = { window: 'train' };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--dry-run') opt.dryRun = true;
    else if (a.startsWith('--')) opt[a.slice(2)] = argv[++i];
  }
  return opt;
}

function headerField(src, key) {
  const m = src.match(new RegExp('^#\\s*' + key + ':\\s*(.+)$', 'm'));
  return m ? m[1].trim() : '';
}

// Lightweight Python 2 → 3 conversion for the constructs old JQ strategies use (2to3 /
// lib2to3 is gone in Python 3.13+). Handles `print` statements and `except X, e:`; anything
// this misses is caught downstream by the compile-error detector (fast terminal skip).
function py2to3(src) {
  if (!/(^|\r?\n)[ \t]*print[ \t]+(?!\()|except[ \t]+[\w.]+[ \t]*,[ \t]*\w+[ \t]*:/.test(src)) return src;
  return src.split(/\r?\n/).map(line => {          // split also strips CRLF \r
    line = line.replace(/^([ \t]*except[ \t]+[\w.()\[\] ]+?)[ \t]*,[ \t]*(\w+)[ \t]*:/, '$1 as $2:');
    const m = line.match(/^([ \t]*)print[ \t]+(?!\()(.*\S)[ \t]*$/);
    if (m) line = `${m[1]}print(${m[2].replace(/,\s*$/, '')})`;
    return line;
  }).join('\n');
}

// Map a wiki concept → the set of strategies/<file>.py basenames whose wiki page
// lists that concept, so a batch can prioritize e.g. --concept 小市值因子.
function conceptSourceBasenames(concept) {
  const dir = path.join(ROOT, 'wiki/strategies');
  const set = new Set();
  for (const p of fs.readdirSync(dir).filter(f => f.endsWith('.md'))) {
    const fm = (fs.readFileSync(path.join(dir, p), 'utf8').split('---')[1] || '');
    const cm = fm.match(/concepts:\s*\[([^\]]*)\]/);
    if (!cm || !cm[1].includes(concept)) continue;
    const sm = fm.match(/sourceFile:\s*(\S+)/);
    if (sm) set.add(path.basename(sm[1]));
  }
  return set;
}

// Precheck: skip clearly non-stock-backtestable files without spending a backtest.
function incompatibility(src) {
  if (!/def\s+initialize\s*\(/.test(src)) return 'incompatible-notrunnable'; // tool/research page
  if (/RealFuture|get_dominant_future|set_future_commission|期货合约|subscribe\s*\(/.test(src)) return 'incompatible-futures';
  return null;
}

/**
 * Gate threshold and score formula come from harness/config/epoch-<n>.json.
 * Returns { obj, gate } — the caller destructures both, and a bare return value
 * silently wrote empty objective/gate columns for a whole run.
 */
function objectiveOf(annual, maxdd, sharpe) {
  const h = require('./harness-config');
  return { obj: h.objective(annual, maxdd, sharpe), gate: h.gate(sharpe) ? 'pass' : 'fail' };
}

function main() {
  const opt = parseArgs(process.argv.slice(2));
  const ledgerPath = path.join(ROOT, `harness/normalize-${opt.window}.tsv`);
  if (!fs.existsSync(TMP_DIR)) fs.mkdirSync(TMP_DIR, { recursive: true });

  // Ledger (resumable). Terminal statuses are skipped on resume; failed/crash are
  // RETRIABLE (rate-limiting can cause spurious failures) until they hit failed-final.
  // `epoch` records WHICH bench measured a row. Epoch 4 pins order_volume_ratio, fund costs
  // and avoid_future_data, which change fills and fees — so a row is only comparable to rows
  // from the same epoch. Appended last: wiki-family-build.js reads columns 0..12 and ignores it.
  const HEADER = ['sourceFile','postId','title','status','start','end','days','total_pct','annual_pct','sharpe','maxdd_pct','objective','gate','epoch'].join('\t');
  // `no-trades` IS terminal. strategy-post-backtest.js calls it "an outcome to
  // investigate, not a transient failure to rerun" — but until it was listed here
  // it was in neither TERMINAL nor RETRIABLE, so it was never marked done AND never
  // incremented failCount, meaning finalize() could not escalate it either. Those
  // strategies were re-run and re-billed on every batch forever; two files already
  // appear twice in the ledger from exactly this.
  const harness = require('./harness-config');
  const ACTIVE_EPOCH = harness.config().epoch;
  const TERMINAL = new Set(['normalized', 'incompatible-futures', 'incompatible-notrunnable', 'failed-final', 'slow-skipped', 'compile-error', 'no-trades']);
  const RETRIABLE = new Set(['failed', 'crash', 'window-mismatch', 'rate-limited', 'budget-stopped']);
  const done = new Set();       // sourceFile with a terminal status
  const failCount = {};         // sourceFile -> # prior retriable failures
  if (fs.existsSync(ledgerPath)) {
    for (const line of fs.readFileSync(ledgerPath, 'utf8').split('\n')) {
      const c = line.split('\t');
      const f = c[0], st = c[3];
      if (!f || f === 'sourceFile') continue;
      // Epoch-aware: a row only counts as done if a bench EQUIVALENT to the current one
      // measured it. Epoch 4 pins order_volume_ratio / fund costs / avoid_future_data, which
      // change fills and fees, so an epoch-2 row is not a result for epoch 4 — without this
      // the normalizer reported "todo=0" and silently refused to re-measure after a bump.
      //
      // ⚠ Equivalence, not equality. This was `rowEpoch === ACTIVE_EPOCH`, which also discarded
      // epoch-4 rows under epoch 5 even though epoch 5 changed ONLY the scoring rule and says so
      // in its config. Strict equality means every future scoring-only bump re-measures the
      // whole library at 60 backtest-minutes a day. `measurementValid` walks the declared
      // `measurementPreservedFromPrevious` chain and is conservative when it is unstated.
      const rowEpoch = c[13] || null;
      if (TERMINAL.has(st) && harness.measurementValid(rowEpoch)) done.add(f);
      if (RETRIABLE.has(st)) failCount[f] = (failCount[f] || 0) + 1;
    }
  } else {
    fs.writeFileSync(ledgerPath, HEADER + '\n');
  }
  const MAX_RETRIES = 2;                 // after this many prior fails → failed-final
  const CIRCUIT_BREAK = 6;               // consecutive backtest failures → stop (rate-limit guard)
  const COOLDOWN_S = 6;                  // between strategies — let JQ's 2 backtest slots free up
  const RATELIMIT_BACKOFF_S = 45;        // wait when JQ reports the concurrency cap
  const USAGE_LIMIT = parseInt(opt['usage-limit'] || '55', 10);   // daily used-minutes ceiling
  process.env.JQ_USAGE_LIMIT = String(USAGE_LIMIT);               // children read this for the pre-start gate
  console.log(`[normalize] usage limit = ${USAGE_LIMIT} min/day (children stop starting new backtests past this)`);
  // Slow-skip cap (minutes) forwarded to each child; parent timeout must exceed it + cancel-retry overhead.
  const MAX_POLL_MIN = resolveMaxPollMin(opt);
  const PER_STRATEGY_TIMEOUT_MS = MAX_POLL_MIN * 60 * 1000 + 5 * 60 * 1000;
  console.log(`[normalize] slow-skip cap = ${MAX_POLL_MIN} min/strategy (parent timeout ${MAX_POLL_MIN + 5} min)`);
  let consecFails = 0;
  const sleepSync = (s) => { try { execFileSync('sleep', [String(s)]); } catch {} };

  const onDisk = new Set(fs.readdirSync(STRAT_DIR).filter(f => f.endsWith('.py')));
  let files = [...onDisk].sort();
  if (opt.files) {                                   // explicit basename list (e.g. daily's new fetches)
    // Preserve the CALLER'S order. utils/normalize-backfill.js hands this list in
    // screening-priority order, and re-sorting by directory listing would silently
    // throw that away — the highest-value strategy would wait behind an alphabetical
    // queue while the daily backtest budget ran out.
    const asked = opt.files.split(',').map(s => s.trim()).filter(Boolean);
    files = asked.filter(f => onDisk.has(f));
    console.log(`[normalize] --files → ${files.length}/${asked.length} present (caller order preserved)`);
  }
  if (opt.concept) {
    const wanted = conceptSourceBasenames(opt.concept);
    files = files.filter(f => wanted.has(f));
    console.log(`[normalize] concept=${opt.concept} → ${files.length} strategies`);
  }
  if (opt.filter) files = files.filter(f => f.includes(opt.filter));
  const todo = files.filter(f => !done.has('strategies/' + f));
  const slice = opt.limit ? todo.slice(0, parseInt(opt.limit, 10)) : todo;

  console.log(`[normalize] window=${opt.window} | epoch=${ACTIVE_EPOCH} | total=${files.length} ` +
              `done(this epoch)=${done.size} todo=${todo.length} running=${slice.length}`);
  if (opt.dryRun) { slice.forEach(f => console.log('  would run:', f)); return; }

  let n = 0;
  for (const f of slice) {
    n++;
    const srcFile = 'strategies/' + f;
    const src = fs.readFileSync(path.join(STRAT_DIR, f), 'utf8');
    const postId = headerField(src, 'postId');
    const title  = headerField(src, 'title') || f;
    const tag = (postId || f).slice(0, 8);

    const bad = incompatibility(src);
    if (bad) {   // no backtest spent — safe even when over budget
      appendRow(ledgerPath, [srcFile, postId, title, bad, '', '', '', '', '', '', '', '', '']);
      console.log(`[${n}/${slice.length}] ${bad}  ${f}`);
      continue;
    }

    // Write normalized copy (Py2→Py3 if needed, raw + override) to temp, run Pipeline 2.
    const tmp = path.join(TMP_DIR, `${tag}.py`);
    fs.writeFileSync(tmp, py2to3(src) + OVERRIDE);

    let out = '';
    try {
      out = execFileSync('node', [POST_BT, tmp, `norm-${tag}`, '--window', opt.window, '--max-poll-min', String(MAX_POLL_MIN)],
        { encoding: 'utf8', timeout: PER_STRATEGY_TIMEOUT_MS, stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (e) {
      out = (e.stdout || '') + (e.stderr || '');
    }

    // Pre-start usage gate tripped in the child (didn't run) → stop the batch.
    const us = out.split('\n').find(l => l.startsWith('USAGE-STOP\t'));
    if (us) {
      const m = us.match(/used=(\d+)\tlimit=(\d+)/);
      console.log(`[normalize] USAGE STOP: used ${m ? m[1] : '?'}min ≥ limit ${m ? m[2] : USAGE_LIMIT}min. ` +
                  `Stopping (${f} not run) — resume when quota resets or raise --usage-limit.`);
      break;
    }

    // Escalate a retriable failure to failed-final once it has failed enough times.
    const finalize = (st) => ((failCount[srcFile] || 0) >= MAX_RETRIES ? 'failed-final' : st);
    const breaker = () => {
      if (consecFails >= CIRCUIT_BREAK) {
        console.error(`[normalize] CIRCUIT BREAK: ${consecFails} consecutive failures — likely JQ ` +
                      `rate-limit or session drop. Stopping; re-run to resume (failures are retriable).`);
        process.exit(2);
      }
    };

    const sm = out.split('\n').find(l => l.startsWith('SUMMARY\t'));
    if (!sm) {
      const st = finalize('crash');
      appendRow(ledgerPath, [srcFile, postId, title, st, '', '', '', '', '', '', '', '', '']);
      console.log(`[${n}/${slice.length}] ${st}  ${f}`);
      consecFails++; breaker(); continue;
    }
    // SUMMARY\t<window>\t<start>\t<end>\t<days>\t<total%>\t<annual%>\t<sharpe>\t<maxdd%>\t<status>
    const c = sm.split('\t');
    const [ , , start, end, days, total, annual, sharpe, maxdd, status ] = c;
    const num = x => (x === '' || x == null ? null : parseFloat(x));

    if (status === 'rate-limited') {                    // JQ concurrency cap — not the strategy's fault
      appendRow(ledgerPath, [srcFile, postId, title, 'rate-limited', '', '', '', '', '', '', '', '', '']);
      console.log(`[${n}/${slice.length}] rate-limited (backoff ${RATELIMIT_BACKOFF_S}s)  ${f}`);
      consecFails++; sleepSync(RATELIMIT_BACKOFF_S); breaker(); continue;   // never finalized; retried later
    }
    if (status === 'compile-error') {                   // traceback/syntax/import error → deterministic; terminal
      appendRow(ledgerPath, [srcFile, postId, title, 'compile-error', '', '', '', '', '', '', '', '', '']);
      console.log(`[${n}/${slice.length}] compile-error (terminal)  ${f}`);
      sleepSync(COOLDOWN_S); continue;
    }
    if (status === 'slow-skipped') {                    // hit the MAX_POLL safety cap → cancelled via API; terminal
      appendRow(ledgerPath, [srcFile, postId, title, 'slow-skipped', start, end, days, total, annual, sharpe, maxdd, '', '']);
      console.log(`[${n}/${slice.length}] slow-skipped (safety cap, cancelled)  ${f}`);
      sleepSync(COOLDOWN_S); continue;                  // not a failure cascade — don't touch breaker
    }
    if (status === 'no-trades') {                       // ran clean but placed zero orders — terminal
      appendRow(ledgerPath, [srcFile, postId, title, 'no-trades', start, end, days, total, annual, sharpe, maxdd, '', '']);
      console.log(`[${n}/${slice.length}] no-trades (terminal — selection/data path produced no orders)  ${f}`);
      sleepSync(COOLDOWN_S); continue;                  // not a failure cascade — don't trip the breaker
    }
    if (status !== 'completed') {                       // failed / window-mismatch
      const st = finalize(status);
      appendRow(ledgerPath, [srcFile, postId, title, st, start, end, days, total, annual, sharpe, maxdd, '', '']);
      console.log(`[${n}/${slice.length}] ${st}  ${f}`);
      consecFails = 0; sleepSync(COOLDOWN_S); continue;  // genuine backtest error → pipeline works, don't trip breaker
    }

    consecFails = 0;                                     // a real result resets the breaker
    const { obj, gate } = objectiveOf(num(annual), num(maxdd), num(sharpe));
    appendRow(ledgerPath, [srcFile, postId, title, 'normalized', start, end, days, total, annual, sharpe, maxdd, obj, gate]);
    console.log(`[${n}/${slice.length}] normalized  sharpe=${sharpe} obj=${obj} gate=${gate}  ${f}`);
    sleepSync(COOLDOWN_S);                               // let JQ slots free before next
  }
  console.log(`[normalize] batch done. ledger: ${ledgerPath}`);

  // Bookkeeping that belongs to "a strategy was measured", not to one caller: create the
  // wiki page for anything newly normalized and prune finished entries from the pending
  // queue. Both used to live only in normalize-daily.js, so a direct run silently skipped
  // them (3 results ended up with a ledger row and no page). Derived from the ledger, so
  // running it twice is a no-op. Never fatal — a bookkeeping failure must not lose results.
  try {
    const { sync } = require('./normalize-sync');
    const r = sync({ window: opt.window });
    if (r.stubbed.length || r.pruned.length) {
      console.log(`[normalize] sync: +${r.stubbed.length} wiki page(s), -${r.pruned.length} queue entr(ies)`);
    }
  } catch (e) {
    console.error(`[normalize] ⚠ post-batch sync failed (results are safe in the ledger): ${e.message}`);
  }
}

function appendRow(ledgerPath, cells) {
  const epoch = require('./harness-config').config().epoch;
  fs.appendFileSync(ledgerPath, [...cells, epoch].join('\t') + '\n');
}

// Guard: without this, `require('./strategy-normalize')` RAN A FULL BATCH. It happened —
// a require in a one-liner started a 214-strategy run and spent 42 of the day's 60
// backtest minutes before it was killed. Every other entry point in utils/ has this guard.
if (require.main === module) main();

// The frozen cost block is the ONE literal every candidate has to carry, and it runs on JQ's
// servers where it cannot read harness/config/epoch-<n>.json. Exporting it is what keeps
// `enhance/candidates/*.py` from being built by hand-copying it — a hand copy is a second
// source of truth that `harness-config.js --verify` does not police, free to drift the moment
// an epoch changes costs. Exports sit AFTER the guard above and export no side effects.
module.exports = { OVERRIDE, py2to3 };
