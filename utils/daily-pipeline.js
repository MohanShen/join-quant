/**
 * daily-pipeline.js — one day's worth of pipeline, chosen by queue priority under a fixed
 * backtest budget.
 *
 * The rule (user's, 2026-09-21): the unit of work is a **FAMILY**, and the pipeline is a funnel —
 *
 *     research (/run-family)  >  normalize  >  discover+fetch
 *
 * Drain the family queue; when no family is due, normalize to refill it; when nothing is left to
 * normalize, fetch a new batch. Run until the budget is gone. A pull system: finish what is in
 * the pipe before widening its mouth.
 *
 * ⚠ This REPLACED `enhance > study > normalize > discover`. Those were two queues over the same
 * 14 families, competing for the same minutes and each able to starve the other, with no route
 * from a newly normalized strategy into research except a human noticing. `research` is the
 * merged loop over one family queue ordered by max post-screen priority
 * (`utils/family-queue.js`). enhance/study stay reachable via `--stage` while their pinned
 * sessions exist, but they are out of the automatic order.
 *
 * ⚠ The starvation consequence is unchanged and still by design: while any family is due,
 * normalize does not run. `--plan` prints every depth so it stays visible.
 *
 * ⚠ What this CANNOT do: start study or enhance from cold. Those are Claude agent loops, not
 * scripts. Their cron wrappers resume a session a human pinned
 * (`data/auto{study,enhance}-session.txt` -> `claude -p --resume <uuid>`); with no pin they
 * exit cleanly and nothing happens. The planner reports that as `blocked`, never as success,
 * because a daily job that silently no-ops for a week is worse than one that fails loudly.
 *
 * State that survives the day lives in `utils/daily-state.js` — the in-flight claim, the run
 * log, and the deferred pool for strategies that blew the slow-skip cap.
 *
 * Usage:
 *   node utils/daily-pipeline.js --plan          # decide and explain, run nothing
 *   node utils/daily-pipeline.js                 # decide and run
 *   node utils/daily-pipeline.js --stage normalize
 *   node utils/daily-pipeline.js --seed-deferred # park existing slow-skipped rows in the pool
 *   node utils/daily-pipeline.js --once          # one stage only, no chaining
 *   node utils/daily-pipeline.js --sync-manifest # reconcile study/manifest.json with the ledger
 *   node utils/daily-pipeline.js --no-commit     # run + write the summary, but do not push
 *   node utils/daily-pipeline.js --no-summary    # run only
 *   node utils/daily-pipeline.js --status        # queues, budget, deferred pool, last runs
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const state = require('./daily-state');
const consumption = require('./consumption');

/**
 * This pipeline's per-backtest cap, in minutes.
 *
 * Env-configurable for the same reason as USAGE_LIMIT: it is a budget knob, and the budget
 * changed. It also gates the deferred pool — a parked strategy is only re-offered at a cap
 * HIGHER than the one that already failed it, so raising this is what makes the 17 currently
 * parked strategies reachable at all.
 *
 * ⚠ A higher cap is not free: at 45 minutes one pathological strategy can eat a quarter of a
 * 180-minute day. That is affordable on VIP and was not on the free tier.
 */
const SLOW_SKIP_MIN = (() => {
  const n = parseInt(process.env.SLOW_SKIP_MIN || '', 10);
  return Number.isFinite(n) && n > 0 ? n : 30;
})();
/**
 * Daily backtest ceiling handed to every child.
 *
 * ⚠ Read from the environment. This was a hard-coded 55, which silently ignored the
 * USAGE_LIMIT the cron wrapper and the plist both export — so the one knob meant to control
 * spend did nothing, and a VIP account with 180 free minutes would still have stopped at 55.
 * 55 remains the default because it is the free-tier figure for a non-VIP account.
 */
const usageLimit = require('./usage-limit');
// SPEC, resolved per-check against JQ's reported free tier. 'free' is the configured value: stop
// only once usage is PAST the tier, letting the in-flight run carry the small overshoot, rather
// than stopping short to protect it and stranding the tail (2026-10-06: 39 minutes, 21 pending).
const USAGE_LIMIT_SPEC = process.env.USAGE_LIMIT || '55';
const USAGE_LIMIT = usageLimit.resolve(USAGE_LIMIT_SPEC, null);   // static view, for logs/exports
/**
 * Outer wall-clock bound on one stage, in minutes. A HANG GUARD, not a budget — the budget is
 * USAGE_LIMIT and every child already enforces it.
 *
 * ⚠ This was a hard-coded 60 minutes inside `sh()`, which was a plausible bound only while the
 * daily budget was 55. VIP raised it to 170 and the first run past the old ceiling was killed at
 * exactly 60:00 mid-backtest and recorded as `error` — the loop was healthy and had spent 27 of
 * its 170 minutes. Derive it from the budget so the two can never drift apart again: a stage
 * cannot outlive the minutes it is allowed to spend, plus slack for agent turns and one
 * slow-skip that runs to the cap.
 */
const STAGE_TIMEOUT_MIN = (() => {
  const n = parseInt(process.env.STAGE_TIMEOUT_MIN || '', 10);
  return Number.isFinite(n) && n > 0 ? n : USAGE_LIMIT + SLOW_SKIP_MIN + 30;
})();
/**
 * Stage order. Later stages first: finish what is in the pipe before admitting more.
 *
 * ⚠ The unit of work is now a FAMILY, not a stage of a strategy. `enhance` and `study` were two
 * queues over the same 14 families, competing for the same minutes and each able to starve the
 * other; `research` is the merged loop (/run-family) over one family queue. The funnel is
 *
 *     integrate (ship it) -> research (drain the family queue) -> normalize (refill it)
 *                         -> discover (refill THAT)
 *
 * so normalize only runs when no family is due, and discover only when nothing is left to
 * normalize. `enhance`/`study` remain dispatchable via --stage for fallback while their pinned
 * sessions still exist, but they are out of the automatic order.
 *
 * ⚠ `integrate` leads because it is the LAST stage, and the rule is that later stages outrank
 * earlier ones. It was absent until 2026-10-17, which made the funnel end one step short of its
 * own product: a family that cleared `/run-family` and VAL had nowhere to go, so the exit gate
 * accumulated candidates while the cron spent every minute admitting more raw strategies.
 * Its SEED action costs no backtest at all (`scripts/run-integrate.sh` skips the budget and CDP
 * preflights for it), so leading with it cannot starve anything of minutes.
 *
 * ⚠⚠ `oos` LEADS, as of 2026-10-17 — **user decision, reversing the recommendation in this file.**
 * It was excluded because it spends an irreversible test on the only clean surface left, and that
 * reasoning has not changed. What makes automating it defensible is that the ceiling lives in
 * CODE, not in the absence of a queue:
 *   - `utils/oos-budget.js` refuses past 1/candidate or 2/bench, before the browser opens;
 *   - `OOS-READINESS` refuses a family `integrate-eligible` does not call eligible;
 *   - `utils/oos-queue.js` reports `ready` only for a candidate that is untested, within budget,
 *     AND has a pinned runnable artifact.
 * So when the bench's tests are gone the queue is empty, depth is 0, and the stage never runs
 * again until a bench change. That is the stop — not a human remembering. (It happened the same
 * day: both tests spent, 大小盘轮动 −0.21 and 红利低频 −0.51, and the queue went to 0 ready.)
 * ⚠ The two PROTECTION overrides stay human-only env vars: `JQ_ALLOW_OOS_OVERBUDGET`,
 * `JQ_ALLOW_OOS_UNREADY`. Nothing here sets them.
 */
const PRIORITY = ['oos', 'integrate', 'research', 'assign', 'normalize', 'discover'];

const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };

/**
 * Does this planned stage cost BACKTEST MINUTES?
 *
 * ⚠ Shared by both budget gates on purpose. There are two — one in `runChain` for a mid-chain
 * stage, one in the CLI for a single stage — and they disagreed: the CLI exempted
 * `discover`/`assign`/seed-`integrate` while runChain exempted only `discover`. So a free stage
 * reached mid-chain was stopped by a budget it was never going to spend, which is the same bug the
 * CLI exemption was added to fix (2026-10-17), surviving in the other copy of the rule.
 *
 * Free stages: `discover` (HTTP only), `assign` (judgement, no bench), and an `integrate` round
 * whose head action is `seed` — a seed reads the champion's figures out of the ledger and writes
 * one `promoted.tsv` row, with no browser and no backtest.
 */
const isFreeStage = p =>
  p.stage === 'discover'
  || p.stage === 'assign'
  || (p.stage === 'integrate' && ((p.q.integrate || [])[0] || {}).action === 'seed');

// ── budget ──────────────────────────────────────────────────────────────────

/** @returns {{used:number|null, free:number|null, ok:boolean, raw:string}} */
function budget() {
  try {
    const out = execFileSync('node', [path.join(__dirname, 'jq-budget.js')],
      { encoding: 'utf8', cwd: ROOT, timeout: 180000 }).trim();
    const m = out.match(/used=(\d*)\s+free=(\d*)/);
    if (!m || m[1] === '') return { used: null, free: null, ok: false, raw: out };
    return { used: parseInt(m[1], 10), free: parseInt(m[2], 10), ok: true, raw: out };
  } catch (e) {
    return { used: null, free: null, ok: false, raw: String(e.message).slice(0, 80) };
  }
}

// ── queues ──────────────────────────────────────────────────────────────────

const familyNames = () => {
  const d = path.join(ROOT, 'wiki/families');
  return fs.existsSync(d) ? fs.readdirSync(d).filter(f => f.endsWith('.md')).map(f => f.replace(/\.md$/, '')) : [];
};

const { field: fmField } = require('./frontmatter');

/** Families whose membership changed since the stage last consumed them (or never did). */
function staleFamilies(stage, { requireBest = false } = {}) {
  const out = [];
  for (const name of familyNames()) {
    if (requireBest) {
      const t = fs.readFileSync(path.join(ROOT, 'wiki/families', `${name}.md`), 'utf8');
      if (!Number.isFinite(parseFloat(fmField(t, 'bestObjective')))) continue;
    }
    const s = consumption.staleFor(stage, name);
    if (s.stale) out.push({ family: name, reason: s.reason, members: s.now.count });
  }
  return out;
}

/**
 * ⚠⚠ `total` is REAL WORK, not queue length — and the difference drove stage selection.
 *
 * Measured 2026-10-17: the queue reported **24** while only **9** entries were runnable. 5 could
 * never resolve (1 carried a `strategies/` prefix, 4 were re-minted ids matching no file) and 10
 * were already finished — 9 of them `normalized` at epoch 6, which epoch 8 accepts. So the planner
 * picked `normalize` twice on a queue with nothing in it, the normalizer exited in 6 seconds
 * having started no backtest, and the run was recorded as `RAN  21 queued`. A depth that counts
 * entries nothing can run is fiction, and this is the number the funnel decides on.
 *
 * `pending`/`retry` keep every entry so a human can still see them; `total` counts what would
 * actually be measured. `utils/normalize-sync.js` is what REMOVES the dead ones.
 */
function normalizeQueue() {
  const pending = readJson(path.join(ROOT, 'data/pending-normalize.json'), []);
  const list = Array.isArray(pending) ? pending : [];
  const retry = state.dueForRetry(SLOW_SKIP_MIN);

  let runnable = [], dead = [];
  try {
    const harness = require('./harness-config');
    const ledger = require('./ledger');
    const onDisk = new Set(fs.readdirSync(path.join(ROOT, 'strategies')).filter(f => f.endsWith('.py')));
    const row = {};
    for (const r of ledger.rows()) row[r.sourceFile.replace(/^strategies\//, '')] = r;
    // A file is work if it resolves to something on disk AND does not already carry a terminal
    // row this bench accepts. `slow-skipped` counts as terminal here for the same reason the
    // normalizer does: re-running it at the SAME cap learns nothing (the retry path below raises
    // the cap explicitly).
    const TERMINAL = new Set(['normalized', 'compile-error', 'slow-skipped', 'no-trades',
                              'incompatible-futures', 'incompatible-notrunnable', 'failed-final']);
    const isWork = e => {
      const b = String(e).replace(/^strategies\//, '');
      if (!onDisk.has(b)) return false;
      const r = row[b];
      return !(r && TERMINAL.has(r.status) && harness.measurementValid(r.epoch));
    };
    const all = [...new Set([...retry.map(r => r.file), ...list])];
    // ⚠ A DUE deferred-retry entry IS work, even though its ledger row is `slow-skipped` and so
    // terminal. `dueForRetry(cap)` already filtered on `maxCapTried < cap`, which is the right
    // judge for a retry — the ledger-terminal test is the right judge for a PENDING entry. Mixing
    // them made the pool permanently unrunnable: 4 entries read "waiting for a higher cap" at the
    // cron's cap of 45 while `runnable` stayed 0, so a higher cap would never have helped.
    const dueRetry = new Set(retry.map(r => r.file));
    runnable = all.filter(e => dueRetry.has(e) || isWork(e));
    // ⚠ Of the rest, separate DEAD from merely not-runnable-at-this-cap. A `slow-skipped` row in
    // the deferred pool is real work waiting for a bigger cap, not a leak — calling it
    // "unresolvable" would repeat the conflation this whole change exists to remove.
    dead = all.filter(e => {
      if (runnable.includes(e) || dueRetry.has(e)) return false;
      const b = String(e).replace(/^strategies\//, '');
      if (!onDisk.has(b)) return true;                     // resolves to no file
      const r = row[b];
      return !!(r && r.status !== 'slow-skipped');          // finished some other way
    });
  } catch {
    runnable = [...list, ...retry.map(r => r.file)];     // cannot judge — report it all
  }
  return { pending: list, retry, runnable, dead, total: runnable.length,
           listed: list.length + retry.length };
}

function discoverQueue() {
  const q = readJson(path.join(ROOT, 'data/copy-queue.json'), []);
  const rows = Array.isArray(q) ? q : (q.queue || Object.values(q).find(Array.isArray) || []);
  const uncopied = rows.filter(r => r && !r.copied && !r.fetched);
  return { uncopied: uncopied.length, total: rows.length };
}

function queues() {
  let research = [];
  try { research = require('./family-queue').build().due; }
  catch (e) { research = []; }
  return {
    // Universes with something to do: `seed` (free — promote a first candidate) or `integrate`
    // (a merge round). `idle` universes are excluded, because an idle universe's blocker is
    // upstream in /run-family and a round here would only re-litigate eligibility.
    // The candidate a universe ships, waiting on the held-out window. `ready` already means
    // untested + within budget + has a pinned artifact, so depth 0 is the budget's own stop.
    oos: (() => { try { return require('./oos-queue').ready(); } catch { return []; } })(),
    // ⚠ Seeds lead, which is what `integrate-queue.next()` also does — so the universe the
    // planner reports and the one the wrapper would pick unprompted are the same one. A seed is
    // free and unblocks every later arrival in that universe (it defines the incumbent they must
    // beat), so doing it before spending minutes on a merge is strictly right.
    integrate: (() => {
      try {
        const rows = require('./integrate-queue').build().filter(r => r.action !== 'idle');
        return [...rows.filter(r => r.action === 'seed'), ...rows.filter(r => r.action !== 'seed')];
      } catch { return []; }
    })(),
    research,
    // A normalized strategy with no family: is invisible to the family queue — wiki-family-build
    // skips pages without one. Assigning costs no backtest minutes, so it sits AHEAD of normalize:
    // making what we already measured visible beats measuring more.
    assign: (() => { try { return require('./family-assign').pending(); } catch { return []; } })(),
    enhance: staleFamilies('enhance', { requireBest: true }),
    study: staleFamilies('study'),
    normalize: normalizeQueue(),
    discover: discoverQueue(),
  };
}

const depth = (stage, q) =>
  stage === 'normalize' ? q.normalize.total
  : stage === 'discover' ? q.discover.uncopied
  : (q[stage] || []).length;

// ── planning ────────────────────────────────────────────────────────────────

/**
 * Decide the stage for this run.
 * `discover` is the only stage allowed to run on an empty board — it is what refills it.
 */
function plan({ stageOverride = null, exclude = [] } = {}) {
  const q = queues();
  const b = budget();

  if (stageOverride) {
    return { stage: stageOverride, q, budget: b, why: `--stage ${stageOverride} (override)` };
  }
  const skip = new Set(exclude);
  for (const stage of PRIORITY) {
    if (skip.has(stage)) continue;        // already ran without progress in this chain
    const d = depth(stage, q);
    if (stage === 'discover') {
      return { stage, q, budget: b, why: 'every other queue is empty — refill the board' };
    }
    if (d > 0) {
      const higher = PRIORITY.slice(0, PRIORITY.indexOf(stage)).filter(h => !skip.has(h));
      return {
        stage, q, budget: b,
        why: `${stage} queue has ${d}` +
             (higher.length ? `; ${higher.join('/')} empty` : '') +
             (skip.size ? `; ${[...skip].join('/')} stalled this chain` : ''),
      };
    }
  }
  // Everything is either empty or stalled. `stage: null` is the honest answer; the caller stops.
  if (skip.has('discover')) {
    return { stage: null, q, budget: b,
             why: `every stage ran without draining its queue (${[...skip].join('/')})` };
  }
  return { stage: 'discover', q, budget: b, why: 'fallthrough' };
}

// ── dispatch ────────────────────────────────────────────────────────────────

/**
 * Run a stage, bounded.
 *
 * The bound is enforced by `scripts/with-timeout.sh`, not by node's own `timeout` option, because
 * node signals the DIRECT CHILD only. Every stage here is a wrapper that spawns the real worker,
 * so a node-side kill leaves an orphan still spending backtest minutes and still holding the JQ
 * session — see that script's header for the run where it happened. `with-timeout.sh` kills the
 * process GROUP and exits 124.
 *
 * Node's timeout is kept as a backstop, set deliberately LONGER (the watchdog's own TERM->KILL
 * grace plus a minute) so the group-kill always fires first and the two causes stay
 * distinguishable in the log.
 */
const TIMEOUT_WRAPPER = path.join(ROOT, 'scripts/with-timeout.sh');

function sh(cmd, args, { timeout = STAGE_TIMEOUT_MIN * 60000 } = {}) {
  const mins = Math.max(1, Math.ceil(timeout / 60000));
  const wrapped = fs.existsSync(TIMEOUT_WRAPPER);
  const c = wrapped ? 'bash' : cmd;
  const a = wrapped ? [TIMEOUT_WRAPPER, String(mins), cmd, ...args] : args;
  try {
    const out = execFileSync(c, a, { encoding: 'utf8', cwd: ROOT, timeout: timeout + 90000 });
    return { ok: true, out };
  } catch (e) {
    const timedOut = e.status === 124 || e.code === 'ETIMEDOUT' || e.signal === 'SIGTERM';
    const out = `${e.stdout || ''}${e.stderr || ''}${e.message}`.slice(0, 4000);
    // ⚠ Name the timeout explicitly. `spawnSync bash ETIMEDOUT` is what the first VIP run wrote
    // into the daily summary, and it reads like the loop script crashed. It did not — we killed
    // it. The note a human reads has to say which.
    return { ok: false, timedOut, out: timedOut
      ? `${out}\n[daily] stage exceeded STAGE_TIMEOUT_MIN=${STAGE_TIMEOUT_MIN} min; process group terminated`
      : out };
  }
}

/**
 * Does the agent loop for `stage` have a session it can actually resume?
 *
 * The pin file is `<branch>\t<uuid>`, and the loop script's own Precheck 0 refuses a session
 * pinned to a different branch — it logs and `exit 0`. That success code is the trap: a cron
 * that only checked "does the file exist" would report OK every day while starting nothing.
 * Both halves are therefore checked here, and a mismatch is reported as blocked.
 */
function sessionPinned(stage, target = null) {
  // ⚠ `research` is NOT gated on a pin, and that is the point of run-family.sh.
  //
  // The "a cron can only RESUME, never cold-start an agent loop" rule was true of
  // agent-loop.sh, which can only continue a session a human pinned. run-family.sh cold-starts a
  // family that has never been studied and pins it per FAMILY. Left gated on the old per-stage
  // file (data/autoresearch-session.txt, which nothing writes any more), research reported
  // BLOCKED every single time and ceded the entire budget to assign/normalize — a funnel whose
  // first stage can never run.
  //
  // `integrate` is the same arrangement one level up: run-integrate.sh pins per UNIVERSE
  // (data/integrate-sessions/<universe>.txt) and cold-starts a universe that has never had a
  // round. Both are "pinned per unit of work", so neither is gated on a per-stage file.
  const PER_UNIT = { research: 'data/research-sessions', integrate: 'data/integrate-sessions',
                     oos: 'data/oos-sessions' };
  if (PER_UNIT[stage]) {
    const pin = target && path.join(ROOT, PER_UNIT[stage], `${target}.txt`);
    const has = pin && fs.existsSync(pin);
    return { pinned: true, coldStart: !has,
             detail: has ? fs.readFileSync(pin, 'utf8').trim().split('\t')[1].slice(0, 8) : 'new' };
  }

  const f = path.join(ROOT, `data/auto${stage}-session.txt`);
  if (!fs.existsSync(f)) return { pinned: false, why: `no data/auto${stage}-session.txt` };
  const [pinBranch, uuid] = fs.readFileSync(f, 'utf8').trim().split('\t');
  if (!uuid) return { pinned: false, why: `${path.basename(f)} has no uuid (got "${pinBranch || ''}")` };

  let branch = '';
  try {
    branch = execFileSync('git', ['rev-parse', '--abbrev-ref', 'HEAD'],
      { encoding: 'utf8', cwd: ROOT }).trim();
  } catch { /* not a checkout; fall through to the mismatch report */ }

  if (pinBranch !== branch) {
    return {
      pinned: false,
      why: `session is pinned to branch "${pinBranch}" but HEAD is "${branch}" — ` +
           `${path.basename(f)} would be skipped by the loop script's own branch gate`,
    };
  }
  const transcript = fs.existsSync(path.join(process.env.HOME || '', '.claude/projects'));
  return { pinned: true, detail: uuid.slice(0, 8), branch, transcriptRoot: transcript };
}

function runNormalize(q, { dry }) {
  // ⚠ DE-DUPLICATED. A file can sit in the deferred pool and the pending queue at once, and the
  // normalizer preserves caller order without de-duping — so it would run twice and append two
  // identical ledger rows. That happened on 2026-09-26 (5511f8f0, `normalized epoch=6` twice) and
  // a ledger-integrity test caught it. Retry entries come first, so keeping the first occurrence
  // preserves their priority.
  // ⚠ Strip the `strategies/` prefix from PENDING as well as from retry. Only retry was stripped,
  // and `strategy-normalize --files` matches bare basenames against the directory listing — so a
  // prefixed pending entry was silently dropped by `asked.filter(f => onDisk.has(f))`.
  const base = e => String(e).replace(/^strategies\//, '');
  const files = [...new Set([
    ...q.normalize.retry.map(r => base(r.file)),
    ...q.normalize.pending.map(base),
  ])];
  // Nothing RUNNABLE is not the same as nothing listed — see normalizeQueue.
  if (!q.normalize.total) {
    return { outcome: 'empty',
             note: `nothing runnable (${q.normalize.listed} listed, all finished or unresolvable ` +
                   '— run node utils/normalize-sync.js to clean them)' };
  }
  if (!files.length) return { outcome: 'empty', note: 'nothing pending' };

  // ⚠⚠ TWO invocations, because a retry needs `--redo` and a fresh file must not get it.
  //
  // A `slow-skipped` row is TERMINAL to the normalizer, so handing a deferred entry to `--files`
  // alone makes it skip the entry as already-done — at ANY cap. The deferred pool therefore never
  // retried anything: it re-offered, the normalizer skipped, and `runNormalize` reported
  // "0 deferred" because it only counts newly-parked files. `--redo` is what re-measures a file
  // that already carries a terminal row, and it is guarded to an explicit `--files` list precisely
  // so it can be used this way.
  //
  // Retries go FIRST (they are the pool's priority) and are the only ones that get `--redo`,
  // scoped to exactly those names. A fresh pending file must never see it: `--redo` on a file with
  // a current measurement re-bills a backtest to learn the same thing.
  const retryFiles = q.normalize.retry.map(r => base(r.file))
    .filter(f => files.includes(f));
  const freshFiles = files.filter(f => !retryFiles.includes(f));

  const argsFor = (list, redo) => [
    'utils/strategy-normalize.js', '--window', 'train',
    '--files', list.slice(0, 40).join(','),
    '--usage-limit', USAGE_LIMIT_SPEC,
    '--max-poll-min', String(SLOW_SKIP_MIN),
    ...(redo ? ['--redo'] : []),
  ];

  if (dry) {
    const parts = [];
    if (retryFiles.length) parts.push(`node ${argsFor(retryFiles, true).join(' ')}`);
    if (freshFiles.length) parts.push(`node ${argsFor(freshFiles, false).join(' ')}`);
    return { outcome: 'dry', note: `would run: ${parts.join('  THEN  ')}`.slice(0, 400) };
  }

  const runs = [];
  if (retryFiles.length) runs.push({ label: 'retry', r: sh('node', argsFor(retryFiles, true)) });
  if (freshFiles.length) runs.push({ label: 'fresh', r: sh('node', argsFor(freshFiles, false)) });
  // One combined view for the parking scan and the outcome below.
  const r = {
    ok: runs.every(x => x.r.ok),
    out: runs.map(x => `--- ${x.label} ---\n${x.r.out}`).join('\n'),
    timedOut: runs.some(x => x.r.timedOut),
  };
  // Park whatever blew the cap, so it is not stranded the way the first 14 were.
  const parked = [];
  for (const line of r.out.split('\n')) {
    const m = line.match(/slow-skipped.*?([^\s]+\.py)/);
    if (m) { state.defer(`strategies/${path.basename(m[1])}`, { reason: 'slow-skipped', capMin: SLOW_SKIP_MIN }); parked.push(m[1]); }
  }
  return {
    outcome: r.ok ? 'ran' : 'error',
    note: `${retryFiles.length} retry(--redo) + ${freshFiles.length} fresh, ` +
          `${parked.length} newly deferred at ${SLOW_SKIP_MIN}min`,
    tail: r.out.split('\n').filter(Boolean).slice(-6).join('\n'),
  };
}

function runAgentLoop(stage, target, { dry }) {
  const pin = sessionPinned(stage, target);
  if (!pin.pinned) {
    return {
      outcome: 'blocked',
      note: `${stage} needs a pinned Claude session (${pin.why}). ` +
            `Start it once interactively: scripts/auto${stage}-interactive.sh — ` +
            `the cron can only RESUME, never cold-start an agent loop.`,
    };
  }
  // ⚠ `research` dispatches run-family.sh, NOT agent-loop.sh.
  //
  // They pin differently and only one of them is right for this loop. agent-loop.sh pins ONE
  // session per STAGE (data/autoresearch-session.txt), so every family would inherit the previous
  // family's context — the exact failure that made a resumed enhance session keep working ETF动量
  // after its queue had been re-pointed at ETF溢价. run-family.sh pins per FAMILY
  // (data/research-sessions/<family>.txt): a family in progress resumes its own session, a family
  // never studied gets a clean one.
  //
  // ⚠⚠ The two LEGACY stages are DEAD, not merely demoted (verified 2026-10-17).
  // `scripts/autoenhance-loop.sh` dispatches `/run-enhance` and `autostudy-loop.sh` dispatches
  // `/run-study`, and **neither skill exists** — both were merged into `/run-family`. So a
  // `--stage enhance` run would spawn a Claude session, tell it to invoke a missing slash command,
  // and exit 0 having done nothing: precisely the silent-no-op shape this file's header warns
  // about three times. Their 8 agent contracts are orphaned too, and still carry epoch-5-era
  // facts (integrate gate 2.0, VAL ending 2025-12-31).
  //
  // Refused here rather than in the wrapper, because the planner is what a human reaches through
  // `--stage`. Not deleted: the wrappers and pins are the fallback path's history, and re-pointing
  // them at /run-family would resurrect the per-STAGE pin bug that made a resumed enhance session
  // keep working ETF动量 after its queue had moved to ETF溢价.
  if (stage === 'enhance' || stage === 'study') {
    return {
      outcome: 'blocked',
      note: `${stage} is a RETIRED stage: scripts/auto${stage}-loop.sh invokes ` +
            `/run-${stage === 'enhance' ? 'enhance' : 'study'}, a skill that no longer exists ` +
            '(both merged into /run-family). Dispatching would start a session that can do ' +
            'nothing and exit 0. Use --stage research, or /run-family <family>.',
    };
  }
  // agent-loop.sh remains wired for them so the path's history is intact, but the guard above
  // means it is never reached.
  const PER_UNIT_SCRIPT = {
    research: 'scripts/run-family.sh',
    integrate: 'scripts/run-integrate.sh',
    oos: 'scripts/run-oos.sh',
  };
  const script = PER_UNIT_SCRIPT[stage]
    ? path.join(ROOT, PER_UNIT_SCRIPT[stage])
    : path.join(ROOT, `scripts/auto${stage}-loop.sh`);
  // The planner picked the family/universe; pass it so the dispatch and the log agree on which
  // one ran. ⚠ run-integrate.sh re-reads the ACTION from the queue even when named — an `idle`
  // universe is skipped there rather than argued with here.
  const args = PER_UNIT_SCRIPT[stage] ? [script, target].filter(Boolean) : [script];
  if (!fs.existsSync(script)) return { outcome: 'error', note: `missing ${path.relative(ROOT, script)}` };
  // ⚠ `target` is the head of OUR queue, reported for the log only — it is not passed to the
  // agent and does not steer it. The study nudge tells the agent to take "the next pending
  // family (strongest bestObjective first)" from study/manifest.json, which is a different
  // ordering over the same set. Claiming to have targeted a family would be a fiction; what
  // the planner actually controls is WHICH STAGE runs, and (via syncStudyManifest) which
  // families are eligible at all.
  if (dry) {
    // ⚠ The note differs by stage because the CONTRACT differs. For research the planner really
    // does choose the family and run-family.sh cold-starts one that has never been studied;
    // for the legacy stages the target is reported for the log only and the agent picks its own
    // order. Saying "resume ... agent picks its own order" for research would be a fiction.
    const note = PER_UNIT_SCRIPT[stage]
      ? `would ${pin.coldStart ? 'START a CLEAN session for' : `resume session ${pin.detail} on`} ` +
        `${target || '(queue head)'} via ${path.relative(ROOT, script)}`
      : `would resume session ${pin.detail} via ${path.relative(ROOT, script)}` +
        `; our queue head is ${target || 'n/a'} (agent picks its own order)`;
    return { outcome: 'dry', note };
  }
  const r = sh('bash', args);
  const lines = r.out.split('\n').filter(Boolean);

  // ⚠ On failure the note must carry the CAUSE, not the dispatch boilerplate. The first
  // failing run wrote "exit 0 is NOT proof work happened" into an `error` row — true, but it
  // tells a human reading the daily summary nothing about what broke (a bash syntax error,
  // as it happened). The "Needs a human" section is only useful if it names the problem.
  const cause = lines
    .filter(l => /error|Error|failed|not found|No such|syntax|denied|refus/.test(l))
    .slice(-2).join(' | ')
    || lines.slice(-1).join('') || 'no output';

  // A stage we cut off is not a stage that broke. It had work in hand and ran out of wall clock,
  // so the human action is "raise the bound or split the work", not "debug the loop script".
  return {
    outcome: r.ok ? 'ran' : r.timedOut ? 'timeout' : 'error',
    note: r.ok
      ? `resumed ${stage} session ${pin.detail} (exit 0 is NOT proof work happened — check its ledger)`
      : r.timedOut
        ? `${stage} was CUT OFF at STAGE_TIMEOUT_MIN=${STAGE_TIMEOUT_MIN} min (not a crash); ` +
          `its process group was terminated — resume it tomorrow or raise the bound`
        : `${stage} loop FAILED: ${cause.slice(0, 200)}`,
    tail: lines.slice(-6).join('\n'),
  };
}

/**
 * Discover + fetch. ⚠ **`--no-normalize` is required**, and it is the fix for the longest-running
 * silent failure in this pipeline.
 *
 * `strategy-daily.js` ends by calling `normalize-daily.normalizeNew()`, which runs BACKTESTS. So
 * the `discover` stage was quietly doing the `normalize` stage's work — outside the budget
 * accounting, outside the deferred pool, outside the retry-at-a-higher-cap rule — bounded only by
 * `STAGE_TIMEOUT_MIN`. Measured: **4h25m on 2026-10-16**, killed by that timeout, taking the day's
 * remaining budget with it; and 61 minutes on 2026-10-17 before it was killed by hand. Neither run
 * moved `used`, because JQ settles `duration.used` only when a run TERMINATES — so a budget gate
 * could never see it, and two monitors expired in silence while it sat there.
 *
 * With the flag, the same stage completes in ~3 minutes (measured: discover -> cookie refresh ->
 * fetch 3 -> done).
 *
 * ⚠ The flag now means "enqueue but do not measure", NOT "skip". `normalizeNew()` is the only
 * thing that appends a day's fetches to `data/pending-normalize.json`, so the old skip-entirely
 * behaviour would have stranded every strategy fetched that day — which is why this is a
 * three-file change and not a one-word one.
 */
function runDiscover({ dry }) {
  const args = ['utils/strategy-daily.js', '--no-normalize'];
  if (dry) return { outcome: 'dry', note: `would run: node ${args.join(' ')}` };
  const r = sh('node', args);
  return { outcome: r.ok ? 'ran' : 'error', note: 'discover + fetch (normalize is its own stage)',
           tail: r.out.split('\n').filter(Boolean).slice(-6).join('\n') };
}

function runStage(stage, q, dry) {
  // For `research` and `integrate` the target is REAL, not decorative: the queue is ordered (by
  // max post-screen priority / by action then arrival sharpe) and the loop is told to take the
  // head. For the legacy stages the agent still picks its own order, which is why those targets
  // are reported and not passed.
  const target = stage === 'research' ? (q.research[0] || {}).family
    : stage === 'oos' ? ((q.oos[0] || {}).members || [])[0]
    : stage === 'integrate' ? (q.integrate[0] || {}).universe
    : stage === 'enhance' ? (q.enhance[0] || {}).family
    : stage === 'study' ? (q.study[0] || {}).family : null;
  let r;
  if (stage === 'normalize') r = runNormalize(q, { dry });
  else if (stage === 'assign') {
    r = dry ? { outcome: 'dry', note: `would assign ${q.assign.length} strategy(ies)` }
            : (() => { const x = sh('bash', [path.join(ROOT, 'scripts/run-assign.sh')]);
                       return { outcome: x.ok ? 'ran' : 'error',
                                note: `family assignment over ${q.assign.length} pending`,
                                tail: x.out.split('\n').filter(Boolean).slice(-4).join('\n') }; })();
  }
  else if (stage === 'oos' || stage === 'integrate' || stage === 'research'
           || stage === 'enhance' || stage === 'study') {
    r = runAgentLoop(stage, target, { dry });
  } else r = runDiscover({ dry });
  return { ...r, stage, target };
}

/**
 * Run the planned stage, ceding to the next priority stage when one is BLOCKED.
 *
 * A blocked stage is not the same as an empty one: the work exists, the runner cannot start
 * it. Stopping there would hand the whole day's budget to a problem no cron can fix — the
 * agent loops can only resume a session a human pinned, so a stale pin would idle the pipeline
 * indefinitely while every run still exited 0. Ceding keeps the budget working; the skipped
 * stages are returned in `cededFrom` and reported, so the blockage stays loud.
 */
function execute(p, { dry = false } = {}) {
  // ⚠⚠ A `--stage` override for a stage that is NOT in PRIORITY used to run something else
  // entirely, silently. `PRIORITY.indexOf('enhance')` is -1 and `slice(-1)` is `['discover']`, so
  // `--stage enhance` printed "-> ENHANCE" and then ran DISCOVER with no mention of the
  // substitution. Measured 2026-10-17 while checking that the retired stages refuse properly: the
  // refusal never fired because the stage was never attempted. A silent substitution is worse than
  // either outcome it replaced.
  const i = PRIORITY.indexOf(p.stage);
  const order = i >= 0 ? PRIORITY.slice(i) : [p.stage, ...PRIORITY];
  const cededFrom = [];

  for (const stage of order) {
    if (stage !== p.stage && stage !== 'discover' && depth(stage, p.q) === 0) continue;

    // Recorded on the run claim so the day's log says WHICH unit was worked, not just which
    // stage. `runStage` recomputes it from the same queue; this is the same value.
    const target = stage === 'oos' ? ((p.q.oos[0] || {}).members || [])[0]
      : stage === 'integrate' ? (p.q.integrate[0] || {}).universe
      : stage === 'research' ? (p.q.research[0] || {}).family
      : stage === 'enhance' ? (p.q.enhance[0] || {}).family
      : stage === 'study' ? (p.q.study[0] || {}).family : null;

    if (!dry && !state.beginRun({ stage, target, budget: p.budget.used })) {
      const f = state.inFlight();
      return { outcome: 'held', stage, cededFrom,
               note: `a run claimed ${f.claim.stage} at ${f.claim.at} and has not finished` };
    }

    const r = runStage(stage, p.q, dry);
    if (!dry) state.endRun({ outcome: r.outcome, note: r.note });

    if (r.outcome === 'blocked') { cededFrom.push({ stage, why: r.note }); continue; }
    return { ...r, cededFrom };
  }
  return { outcome: 'blocked', stage: p.stage, cededFrom,
           note: 'every stage from the planned one down is blocked or empty' };
}

/**
 * Run stage after stage while the budget lasts, re-planning between each.
 *
 * One fire used to mean one stage: if enhance finished in ten minutes having spent eight of
 * sixty, the other fifty-two sat idle until the next fire four hours later. Chaining re-reads
 * the budget and the queues after every stage, so the day's minutes get used by whatever is
 * next in priority order.
 *
 * Re-planning each time (rather than computing an order up front) is what makes it correct:
 * a normalize pass changes the ledger, which changes family staleness, which can legitimately
 * promote study above normalize mid-run.
 *
 * Stops on: budget spent, nothing runnable, an error, or `maxStages` — the last a guard
 * against a stage that returns instantly and would otherwise spin.
 */
/**
 * ⚠⚠ THE CHAIN STOPS WHEN THE BUDGET IS GONE — user decision, 2026-10-17.
 *
 * It used to stop on five other things as well, and each one could end a day with minutes unspent:
 *
 *   `maxStages = 6`                     six EXECUTIONS, with six stages in PRIORITY — so a stage
 *                                       that legitimately needs several passes (normalize takes 40
 *                                       files at a time) could not get them
 *   `outcome: 'empty'`                  a stage found nothing -> whole chain over
 *   `outcome: 'error'`                  one stage failed -> whole chain over
 *   `outcome: 'blocked'`                every stage from the planned one down was blocked
 *
 * `empty` / `error` / `blocked` now CEDE, exactly as `no-progress` already did. That is safe
 * because the no-progress guard is what prevents a retry loop: a stage whose queue did not drain is
 * re-planned once, caught by `depth >= before`, added to `stalled`, and skipped for the rest of the
 * chain. So a failing stage costs one wasted re-plan, not an infinite loop.
 *
 * ⚠ `held` STILL breaks, and must. It means `state.beginRun` refused because another run holds the
 * in-flight claim — a lock, not a stall. Proceeding would let two runs spend the same budget.
 *
 * ⚠ `exhausted` still breaks: every queue is empty, so there is nothing for the remaining minutes
 * to buy. That is not stopping early.
 *
 * ⚠⚠ **`discover` runs at most ONCE per chain**, which is the one place "run until the budget is
 * gone" needed a brake. It is the stage that ADMITS work rather than consuming it, its own
 * `strategy-daily.js` limit is **20 fetches per run** (raised from 3 on 2026-10-17, when the
 * admission rate rather than the budget became the binding constraint), and it costs no backtest
 * minutes — so an unbounded chain would re-run it until `maxStages`, admitting up to 800 strategies
 * in a day and burying the normalize queue it is supposed to feed. ⚠ The raise makes this brake
 * MORE load-bearing, not less: the per-run limit caps one invocation, this caps the invocations.
 * The consuming stages may run as long as the budget allows; the admitting stage may not.
 *
 * ⚠ **What the budget gate CANNOT see**: an agent stage that spends no backtest minutes. A research
 * round taking the Step-0 early exit costs ZERO minutes (measured today: 小市值, `logged-only`), so
 * the budget will never stop it — only its queue draining will. That is token spend, not JQ spend,
 * and `maxStages` is now the only bound on it. If that becomes a problem the right fix is a
 * separate cap on agent dispatches, not a smaller `maxStages`.
 */
function runChain({ dry = false, maxStages = 40, stageOverride = null } = {}) {
  const log = [];
  let last = null;
  // ⚠ A stage that ran without draining its queue must not be picked again in the same chain.
  // Observed live: enhance "ran", its queue stayed at 13 (the agent recorded no consumption
  // event), so the planner immediately picked enhance again — each repeat resuming a Claude
  // session to redo the same thing. Depth is the honest completion signal here, because the
  // stage's own exit code is not one.
  //
  // ⚠⚠ But the comparison must be LOCAL TO THE STAGE'S OWN RUN, measured the moment it returns.
  // It used to be deferred to the stage's NEXT pick, comparing against the depth at its previous
  // pick — which in a funnel spans other stages that legitimately ADD to that queue. Measured
  // 2026-10-17 (the 18:00Z cron, `data/daily-logs/2026-10-17_110009.log`):
  //
  //   assign    picked at 1 → assigned it → 0.   normalize then measured 2 strategies, which
  //             have no `family:` yet, so assign's queue became 2 and its next pick read
  //             "queue still 2 after running" → STALLED, having in fact drained it.
  //   normalize picked at 2 → measured both → 0. discover then admitted 3 fetches (its job), so
  //             normalize's next pick read "queue still 3" → STALLED, having in fact drained it.
  //
  // Both stages did exactly what they exist to do and both were recorded as stalled; the chain
  // then reported EXHAUSTED and the day ended at **used=2 of 180 minutes** with 3 runnable
  // strategies queued. A downstream stage's queue growing because an upstream stage fed it is the
  // funnel WORKING — it is the single thing this pipeline is built to do.
  //
  // So `stalled` is now decided from (depth before execute → depth immediately after), and a
  // stage that moved its own queue stays eligible however much later work arrives.
  // ⚠ Termination no longer rests on `stalled` growing to PRIORITY.length: a productive stage can
  // be re-picked indefinitely, which is the intent ("stop when the budget is gone"). The bounds
  // are the budget gate, the queue draining, and `maxStages` as a backstop.
  const before = {};
  // ⚠ A stalled stage CEDES ITS TURN; it does not end the day. This `break`ed the whole chain,
  // which contradicted its own note ("not repeating IT this chain") and the comment above.
  // Measured 2026-10-04: research stalled on a phantom-blocked backtest, the chain stopped, and
  // normalize never got another turn despite 35 queued strategies and 124 unspent budget minutes.
  // Four consecutive days read as "the day finished" when a later stage had simply stalled.
  const stalled = new Set();
  // The counter advances only on a stage we actually EXECUTE — an exclusion must not burn one of
  // the maxStages slots, or excluding the stages would itself end the chain early. Termination is
  // guaranteed by `stalled` growing monotonically toward PRIORITY.length, with the defensive
  // break below as a backstop.
  for (let i = 0; i < maxStages; ) {
    const p = plan({ stageOverride: i === 0 ? stageOverride : null, exclude: [...stalled] });

    if (!p.stage) {
      log.push({ stage: '—', outcome: 'exhausted', note: p.why });
      break;
    }
    if (stalled.has(p.stage)) {        // cannot happen via plan(); guards against a future change
      log.push({ stage: p.stage, outcome: 'planner-loop',
                 note: 'planner re-proposed a stalled stage — stopping rather than looping' });
      break;
    }

    before[p.stage] = depth(p.stage, p.q);
    i++;

    const ceiling = usageLimit.resolve(USAGE_LIMIT_SPEC, p.budget.free);
    if (p.budget.ok && p.budget.used >= ceiling && !isFreeStage(p)) {
      log.push({ stage: p.stage, outcome: 'budget-spent',
                 note: `used ${p.budget.used} >= ${ceiling}` });
      break;
    }
    const r = execute(p, { dry });
    log.push({ stage: r.stage, outcome: r.outcome, note: r.note, cededFrom: r.cededFrom });
    last = r;

    // ⚠ Only a HELD claim ends the chain: another run owns the in-flight slot, and proceeding
    // would let two runs spend the same budget. `blocked` / `error` / `empty` cede instead — the
    // no-progress guard below catches a stage whose queue did not drain, so a failing stage costs
    // one re-plan rather than the rest of the day. (This list used to break on all four, which is
    // how 2026-10-04 ended with 124 unspent minutes.)
    if (r.outcome === 'held') break;

    // ── did THIS run move THIS stage's own queue? Asked now, while nothing else has run.
    // `dry` executes nothing, so its depth cannot move and asking would stall every stage.
    if (!dry) {
      const after = depth(p.stage, queues());
      if (after >= before[p.stage]) {
        log.push({ stage: p.stage, outcome: 'no-progress',
                   note: `queue ${before[p.stage]} -> ${after} across its own run — ceding its ` +
                         `turn to the next stage (not repeated this chain)` });
        stalled.add(p.stage);
      }
    }

    // ⚠ `discover` ADMITS work; it does not consume it. Its own limit is 20 fetches per RUN, so
    // without this brake a chain would re-run it to maxStages and admit up to 800 in a day.
    if (r.stage === 'discover') stalled.add('discover');
    // In dry mode nothing actually changed, so a second pass would replan identically.
    if (dry) break;
  }
  return { log, last };
}

// ── keeping the planner and the agent looking at the same queue ─────────────

/**
 * Reconcile `study/manifest.json` with the consumption ledger.
 *
 * ⚠ The planner and the study agent read DIFFERENT queues, and they disagreed. The planner
 * derives staleness from `consumption.tsv` (member-aware: a family reopens when its membership
 * changes); the loop script's nudge tells the agent to "work study/manifest.json in order".
 * The manifest said all 14 families were `done` while the planner said all 14 were stale — so
 * the daily job would have dispatched study, the agent would have found nothing pending and
 * exited 0, and the run would have been recorded as `ran`. A silent no-op reported as success
 * is the exact failure the `blocked` path exists to prevent, and it slipped through because
 * the script's exit code is clean.
 *
 * The ledger is the durable truth (tracked, append-only, member-aware), so it wins: a family
 * the ledger calls stale is set back to `pending` in the manifest the agent actually reads.
 * The agent marks it `done` again when it finishes, and records the event — which then makes
 * it non-stale, so this converges rather than oscillating.
 */
function syncStudyManifest({ dry = false } = {}) {
  const f = path.join(ROOT, 'study/manifest.json');
  if (!fs.existsSync(f)) return { changed: [], reason: 'no manifest' };
  const raw = readJson(f, null);
  if (!Array.isArray(raw)) return { changed: [], reason: 'manifest is not an array' };

  const changed = [];
  for (const row of raw) {
    if (!row || !row.family) continue;
    const s = consumption.staleFor('study', row.family);
    if (s.stale && row.status === 'done') {
      changed.push({ family: row.family, from: 'done', to: 'pending', why: s.reason });
      if (!dry) { row.status = 'pending'; row.reopenedBy = 'daily-pipeline'; row.reopenedWhy = s.reason; }
    }
  }
  if (changed.length && !dry) fs.writeFileSync(f, JSON.stringify(raw, null, 2) + '\n');
  return { changed, total: raw.length };
}

// ── seeding ─────────────────────────────────────────────────────────────────

/** Park the slow-skipped rows already in the ledger, which are otherwise stranded forever. */
function seedDeferred({ dry = false } = {}) {
  // Columns via `utils/ledger.js` — `rows()` returns [] when the ledger is absent.
  const seen = new Set();
  const rows = [];
  for (const r of require('./ledger').rows()) {
    if (r.status !== 'slow-skipped' || seen.has(r.sourceFile)) continue;
    seen.add(r.sourceFile);
    rows.push(r.sourceFile);
    // The ledger does not record the cap those runs used; the default was 20.
    if (!dry) state.defer(r.sourceFile, { reason: 'slow-skipped (seeded from ledger)', capMin: 20 });
  }
  return { added: rows.length, rows };
}

// ── CLI ─────────────────────────────────────────────────────────────────────

function printPlan(p) {
  const q = p.q;
  console.log(`[daily] budget: ${p.budget.ok ? `used ${p.budget.used} / free ${p.budget.free}` : `UNAVAILABLE (${p.budget.raw})`}`);
  console.log(`[daily] slow-skip cap ${SLOW_SKIP_MIN} min/backtest, usage limit ${USAGE_LIMIT} min/day`);
  console.log('[daily] queues (funnel order — drain the end before widening the mouth):');
  // ⚠ `oos` is a DISPATCHABLE stage since 2026-10-17 (user decision) and leads PRIORITY, so it is
  // printed with the funnel rather than beneath it. Depth is the number of READY candidates, which
  // already accounts for the budget — when the bench's tests are spent this reads 0 and the stage
  // cannot be picked. The candidates are named because a bare count ("1 test left") never said
  // WHICH book was waiting.
  try {
    const oos = require('./oos-budget');
    const used = oos.testsOnThisBench().length;
    const cap = oos.policy().maxTestsPerEpoch;
    const rows = require('./oos-queue').build();
    const byState = st => rows.filter(r => r.state === st);
    console.log(`   oos       ${String(q.oos.length).padStart(4)}   ready; ${cap - used} of ${cap} ` +
                `test(s) left on this bench (1/candidate, ABSOLUTE)`);
    for (const r of byState('ready')) {
      console.log(`             READY  ${r.universe} ${r.candidateId}` +
                  (r.flags && r.flags.length ? `  ⚠ ${r.flags.join('; ')}` : ''));
    }
    for (const st of ['unrunnable', 'blocked']) {
      for (const r of byState(st)) console.log(`             ${st.toUpperCase()}  ${r.universe} — ${r.why.slice(0, 90)}`);
    }
    const t = byState('tested');
    if (t.length) console.log(`             (${t.length} already tested: ${t.map(r => `${r.universe} ${r.why.match(/-> (.*)$/)?.[1] || ''}`).join(', ')})`);
  } catch (e) {
    console.log(`   oos         ?   (could not read: ${String(e.message).slice(0, 60)})`);
  }
  const ihead = q.integrate.slice(0, 3)
    .map(x => `${x.universe}(${x.action})`).join(', ')
    || 'every universe idle — the gate is upstream (/run-family)';
  console.log(`   integrate ${String(q.integrate.length).padStart(4)}   ${ihead}`);
  const head = q.research.slice(0, 3)
    .map(x => `${x.family}(${x.score ?? '—'}/${x.reason})`).join(', ') || '—';
  console.log(`   research  ${String(q.research.length).padStart(4)}   ${head}`);
  console.log(`   assign    ${String(q.assign.length).padStart(4)}   normalized but no family: (invisible to the queue)`);
  console.log(`   normalize ${String(q.normalize.total).padStart(4)}   runnable; ${q.normalize.listed} listed ` +
              `(${q.normalize.pending.length} pending + ${q.normalize.retry.length} deferred-retry)` +
              `${(q.normalize.dead || []).length
                  ? `  ⚠ ${q.normalize.dead.length} finished/unresolvable — normalize-sync cleans them`
                  : ''}` +
              `${q.normalize.listed - q.normalize.total - (q.normalize.dead || []).length > 0
                  ? `  (${q.normalize.listed - q.normalize.total - (q.normalize.dead || []).length} waiting for a higher cap)`
                  : ''}`);
  console.log(`   discover  ${String(q.discover.uncopied).padStart(4)}   uncopied of ${q.discover.total} in queue`);
  console.log(`   (RETIRED: enhance ${q.enhance.length}, study ${q.study.length} — their skills ` +
              'are gone; --stage refuses both and points at /run-family)');

  // ⚠ OOS is the one stage the cron must never run, so it is reported and never dispatched. It
  // was invisible until 2026-10-16 — the planner would report "research 0" and look finished
  // while candidates sat waiting — and the fix for `integrate` was to put it IN the funnel
  // above (2026-10-17). OOS gets no such promotion: spending the last clean surface is a
  // decision with no undo, not a queue to drain.
  console.log(`[daily] -> ${p.stage.toUpperCase()}   (${p.why})`);
}

/**
 * ⚠ Exported BEFORE the CLI block on purpose. `utils/daily-summary.js` requires this module,
 * and this module requires it back at the end of a run. Node returns a partially-initialised
 * module to the inner require, so with `module.exports` sitting after the CLI block the
 * summary saw `{}` and died with "daily.queues is not a function" — after a real run, which
 * is the worst time to lose the report.
 */
module.exports = { plan, queues, execute, budget, seedDeferred, staleFamilies,
                   runChain, syncStudyManifest,
                   SLOW_SKIP_MIN, USAGE_LIMIT, PRIORITY,
                   // A function, not the constant: the caps are read from the environment at
                   // require time, so a test that wants to vary them has to re-require anyway —
                   // exposing it as a getter keeps that honest instead of freezing one value.
                   stageTimeoutMin: () => STAGE_TIMEOUT_MIN };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const arg = n => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : null; };

  if (argv.includes('--seed-deferred')) {
    const dry = argv.includes('--dry');
    const r = seedDeferred({ dry });
    console.log(`[daily] ${dry ? 'would park' : 'parked'} ${r.added} slow-skipped strategy(ies) in the deferred pool`);
    r.rows.slice(0, 10).forEach(f => console.log(`   + ${f.replace('strategies/', '').slice(0, 64)}`));
    process.exit(0);
  }

  if (argv.includes('--sync-manifest')) {
    const dry = argv.includes('--dry');
    const r = syncStudyManifest({ dry });
    console.log(`[daily] ${dry ? 'would reopen' : 'reopened'} ${r.changed.length} of ${r.total} study families`);
    r.changed.forEach(c => console.log(`   ${c.family}  done -> pending   (${c.why})`));
    process.exit(0);
  }

  if (argv.includes('--status')) {
    const p = plan({});
    printPlan(p);
    const due = state.dueForRetry(SLOW_SKIP_MIN);
    const done = state.exhausted(SLOW_SKIP_MIN);
    console.log(`\n[daily] deferred pool: ${due.length} retryable at ${SLOW_SKIP_MIN}min, ${done.length} exhausted`);
    due.slice(0, 6).forEach(d => console.log(`   retry  attempts=${d.attempts} maxCap=${d.maxCapTried}  ${d.file.replace('strategies/', '').slice(0, 56)}`));
    done.slice(0, 4).forEach(d => console.log(`   held   ${d.why}  ${d.file.replace('strategies/', '').slice(0, 52)}`));
    const s = state.load();
    const f = state.inFlight();
    if (f.claim) console.log(`\n[daily] in-flight: ${f.claim.stage} since ${f.claim.at}${f.stale ? '  ⚠ STALE — next run takes over' : ''}`);
    console.log(`[daily] last ${Math.min(5, s.runs.length)} run(s):`);
    s.runs.slice(-5).forEach(r => console.log(`   ${String(r.endedAt || r.at).slice(0, 16)}  ${String(r.stage).padEnd(10)} ${String(r.outcome).padEnd(9)} ${String(r.note || '').slice(0, 60)}`));
    process.exit(0);
  }

  const p = plan({ stageOverride: arg('--stage') });
  printPlan(p);

  if (argv.includes('--plan')) { console.log('[daily] (--plan — nothing run)'); process.exit(0); }

  const dry = argv.includes('--dry');

  // ⚠ A budget-spent day still gets a run row and a summary.
  //
  // This used to `process.exit(0)` here, which skipped both — so a day the pipeline fired and
  // correctly stood down left NO trace at all, indistinguishable from a day the cron never
  // fired. "Correctly did nothing" is a result, and on a 60-minute budget it will be the most
  // common one; it has to be visible or the record only covers the days work happened.
  //
  // ⚠ Some stages cost NO backtest minutes, and stopping those on a spent budget throws away
  // free progress. `discover` was always exempt (HTTP only); `assign` and a SEED-headed
  // `integrate` round belong in the same class and were not, which meant a universe could sit
  // shipping nothing all day for want of minutes it was never going to use. A seed is a record:
  // read the champion's figures out of the ledger and promote it, no browser, no backtest —
  // `scripts/run-integrate.sh` skips its own CDP and budget preflights for exactly this.
  //
  // The exemption is narrow on purpose. It is the PLANNED stage that must be free, and a free
  // stage on a spent budget runs ALONE (`freeOnly` below forces `--once`) rather than chaining
  // into normalize, whose first act would be to ask for minutes that are gone.
  const free = isFreeStage(p);
  const budgetSpent = p.budget.ok &&
    p.budget.used >= usageLimit.resolve(USAGE_LIMIT_SPEC, p.budget.free) && !free;
  const freeOnly = p.budget.ok && !budgetSpent && free &&
    p.budget.used >= usageLimit.resolve(USAGE_LIMIT_SPEC, p.budget.free);
  let log = [], last = null;

  if (budgetSpent) {
    const note = `used ${p.budget.used} >= ${USAGE_LIMIT}; ${p.stage} not started`;
    console.log(`[daily] budget spent (${p.budget.used} >= ${USAGE_LIMIT}) — clean stop, nothing started`);
    if (!dry) {
      state.beginRun({ stage: p.stage, target: null, budget: p.budget.used, force: true });
      state.endRun({ outcome: 'budget-spent', note });
    }
    log = [{ stage: p.stage, outcome: 'budget-spent', note }];
  } else {
    // Keep the agent's own queue honest before dispatching — see syncStudyManifest.
    const sync = syncStudyManifest({ dry });
    if (sync.changed.length) {
      console.log(`[daily] study manifest: reopened ${sync.changed.length} family(ies) the ledger calls stale`);
      sync.changed.slice(0, 4).forEach(c => console.log(`         ${c.family}  (${c.why})`));
    }
    if (freeOnly) {
      console.log(`[daily] budget spent (${p.budget.used} >= ${USAGE_LIMIT}) but ${p.stage.toUpperCase()}` +
                  ' costs no backtest minutes — running it alone, no chain');
    }
    const once = argv.includes('--once') || freeOnly;
    ({ log, last } = once
      ? (() => { const r = execute(p, { dry }); return { log: [r], last: r }; })()
      : runChain({ dry, stageOverride: arg('--stage') }));
  }

  for (const r of log) {
    for (const c of (r.cededFrom || [])) {
      console.log(`[daily] ⚠ ${String(c.stage).toUpperCase()} BLOCKED — budget ceded to the next stage`);
      console.log(`         ${c.why}`);
    }
    console.log(`[daily] ${r.stage} -> ${String(r.outcome).toUpperCase()}  ${r.note || ''}`);
  }
  if (last && last.tail) last.tail.split('\n').forEach(l => console.log(`   ${l.slice(0, 110)}`));

  // Close the day with a readable record, and commit it. `--no-summary` opts out; `--dry`
  // never writes. The summary leads with what MOVED rather than what ran, because a clean
  // exit is exactly what this repo's three silent-no-op failures produced.
  if (!dry && !argv.includes('--no-summary')) {
    try {
      const summary = require('./daily-summary');
      const r = summary.write({ commit: !argv.includes('--no-commit') });
      console.log(`[daily] summary -> ${path.relative(ROOT, r.file)}  (${r.moved ? 'work moved' : 'NO-OP'})`);
      if (r.commit && !r.commit.ok) console.error(`[daily] ⚠ summary commit: ${r.commit.why}`);
      else if (r.commit && r.commit.skipped) console.log('[daily] summary: nothing to commit');
      else if (r.commit) console.log(`[daily] summary: committed ${r.commit.staged} file(s)` +
        (r.commit.pushed ? ' and pushed' : ` — ${r.commit.why}`));
    } catch (e) {
      console.error(`[daily] ⚠ summary failed (the run itself is unaffected): ${String(e.message).slice(0, 120)}`);
    }
  }

  const bad = log.some(r => r.outcome === 'error' || r.outcome === 'blocked');
  process.exitCode = bad ? 1 : 0;
}

