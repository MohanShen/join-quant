/**
 * strategy-normalize.js
 *
 * Re-backtest every raw strategy in strategies/ on the FROZEN harness window
 * (default: TRAIN) with the harness objective, producing an apples-to-apples
 * "what actually works under one regime" ledger. See docs/research-schema.md §11.
 *
 * Cost normalization (forced): a wrapper is APPENDED to each strategy's source so
 * that any set_slippage/set_commission it calls — even per-bar via set_slip_fee —
 * is overridden to the frozen harness (zero slippage + PerTrade(万3/万13/5)).
 * The raw file in strategies/ is NEVER modified; a normalized copy is written to a
 * temp dir and fed to Pipeline 2.
 *
 * Resumable: results append to research/normalize-<window>.tsv; strategies already
 * carrying a terminal status are skipped on re-run.
 *
 * Usage:
 *   node utils/strategy-normalize.js [--window train|val|holdout]
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
// Must exceed the child's MAX_POLL_MS (JQ_MAX_POLL_MS) + cancel-retry overhead, else the
// child is killed mid-poll → the backtest orphans → jams slots → rate-limit cascade.
const PER_STRATEGY_TIMEOUT_MS = parseInt(process.env.JQ_MAX_POLL_MS || String(5 * 60 * 1000), 10) + 5 * 60 * 1000;

// ── Frozen-harness cost override (appended to each strategy; raw file untouched) ──
// Redefining set_slippage/set_commission at module scope shadows the JQ builtins,
// so every call the strategy makes (initialize OR before_trading_start/handle_data)
// resolves to our override. Python resolves globals at call time, so this catches
// per-bar re-sets (e.g. set_slip_fee). initialize is also wrapped for use_real_price.
const OVERRIDE = `

# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# research/harness.md epoch 1 — force zero slippage + frozen commission regardless of
# what the raw strategy sets, even if it re-sets costs every bar.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
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

function objectiveOf(annualPct, maxddPct, sharpe) {
  if (sharpe == null || annualPct == null || maxddPct == null) return { obj: '', gate: '' };
  const gate = sharpe >= SHARPE_GATE;
  const obj = gate ? (annualPct / 100 - maxddPct / 100).toFixed(4) : 'DQ';
  return { obj, gate: gate ? 'pass' : 'fail' };
}

function main() {
  const opt = parseArgs(process.argv.slice(2));
  const ledgerPath = path.join(ROOT, `research/normalize-${opt.window}.tsv`);
  if (!fs.existsSync(TMP_DIR)) fs.mkdirSync(TMP_DIR, { recursive: true });

  // Ledger (resumable). Terminal statuses are skipped on resume; failed/crash are
  // RETRIABLE (rate-limiting can cause spurious failures) until they hit failed-final.
  const HEADER = ['sourceFile','postId','title','status','start','end','days','total_pct','annual_pct','sharpe','maxdd_pct','objective','gate'].join('\t');
  const TERMINAL = new Set(['normalized', 'incompatible-futures', 'incompatible-notrunnable', 'failed-final', 'slow-skipped', 'compile-error']);
  const RETRIABLE = new Set(['failed', 'crash', 'window-mismatch', 'rate-limited', 'budget-stopped']);
  const done = new Set();       // sourceFile with a terminal status
  const failCount = {};         // sourceFile -> # prior retriable failures
  if (fs.existsSync(ledgerPath)) {
    for (const line of fs.readFileSync(ledgerPath, 'utf8').split('\n')) {
      const c = line.split('\t');
      const f = c[0], st = c[3];
      if (!f || f === 'sourceFile') continue;
      if (TERMINAL.has(st)) done.add(f);
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
  let consecFails = 0;
  const sleepSync = (s) => { try { execFileSync('sleep', [String(s)]); } catch {} };

  let files = fs.readdirSync(STRAT_DIR).filter(f => f.endsWith('.py')).sort();
  if (opt.files) {                                   // explicit basename list (e.g. daily's new fetches)
    const set = new Set(opt.files.split(',').map(s => s.trim()).filter(Boolean));
    files = files.filter(f => set.has(f));
    console.log(`[normalize] --files → ${files.length}/${set.size} present`);
  }
  if (opt.concept) {
    const wanted = conceptSourceBasenames(opt.concept);
    files = files.filter(f => wanted.has(f));
    console.log(`[normalize] concept=${opt.concept} → ${files.length} strategies`);
  }
  if (opt.filter) files = files.filter(f => f.includes(opt.filter));
  const todo = files.filter(f => !done.has('strategies/' + f));
  const slice = opt.limit ? todo.slice(0, parseInt(opt.limit, 10)) : todo;

  console.log(`[normalize] window=${opt.window} | total=${files.length} done=${done.size} todo=${todo.length} running=${slice.length}`);
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
      out = execFileSync('node', [POST_BT, tmp, `norm-${tag}`, '--window', opt.window],
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
}

function appendRow(ledgerPath, cells) {
  fs.appendFileSync(ledgerPath, cells.join('\t') + '\n');
}

main();
