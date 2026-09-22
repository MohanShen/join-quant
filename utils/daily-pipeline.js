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
const USAGE_LIMIT = (() => {
  const n = parseInt(process.env.USAGE_LIMIT || '', 10);
  return Number.isFinite(n) && n > 0 ? n : 55;
})();
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
 *     research (drain the family queue) -> normalize (refill it) -> discover (refill THAT)
 *
 * so normalize only runs when no family is due, and discover only when nothing is left to
 * normalize. `enhance`/`study` remain dispatchable via --stage for fallback while their pinned
 * sessions still exist, but they are out of the automatic order.
 */
const PRIORITY = ['research', 'assign', 'normalize', 'discover'];

const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };

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

const fmField = (t, k) => (t.match(new RegExp(`^${k}:\\s*(.*)$`, 'm')) || [])[1] || '';

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

function normalizeQueue() {
  const pending = readJson(path.join(ROOT, 'data/pending-normalize.json'), []);
  const list = Array.isArray(pending) ? pending : [];
  const retry = state.dueForRetry(SLOW_SKIP_MIN);
  return { pending: list, retry, total: list.length + retry.length };
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
function plan({ stageOverride = null } = {}) {
  const q = queues();
  const b = budget();

  if (stageOverride) {
    return { stage: stageOverride, q, budget: b, why: `--stage ${stageOverride} (override)` };
  }
  for (const stage of PRIORITY) {
    const d = depth(stage, q);
    if (stage === 'discover') {
      return { stage, q, budget: b, why: 'every other queue is empty — refill the board' };
    }
    if (d > 0) {
      const higher = PRIORITY.slice(0, PRIORITY.indexOf(stage));
      return {
        stage, q, budget: b,
        why: `${stage} queue has ${d}` +
             (higher.length ? `; ${higher.join('/')} empty` : ''),
      };
    }
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
  if (stage === 'research') {
    const pin = target && path.join(ROOT, 'data/research-sessions', `${target}.txt`);
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
  const files = [
    ...q.normalize.retry.map(r => r.file.replace(/^strategies\//, '')),
    ...q.normalize.pending,
  ];
  if (!files.length) return { outcome: 'empty', note: 'nothing pending' };
  const list = files.slice(0, 40).join(',');
  const args = ['utils/strategy-normalize.js', '--window', 'train',
                '--files', list,
                '--usage-limit', String(USAGE_LIMIT),
                '--max-poll-min', String(SLOW_SKIP_MIN)];
  if (dry) return { outcome: 'dry', note: `would run: node ${args.join(' ')}`.slice(0, 300) };

  const r = sh('node', args);
  // Park whatever blew the cap, so it is not stranded the way the first 14 were.
  const parked = [];
  for (const line of r.out.split('\n')) {
    const m = line.match(/slow-skipped.*?([^\s]+\.py)/);
    if (m) { state.defer(`strategies/${path.basename(m[1])}`, { reason: 'slow-skipped', capMin: SLOW_SKIP_MIN }); parked.push(m[1]); }
  }
  return {
    outcome: r.ok ? 'ran' : 'error',
    note: `${files.length} queued, ${parked.length} deferred at ${SLOW_SKIP_MIN}min`,
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
  // agent-loop.sh remains for the two legacy stages, whose pins are per-stage by design.
  const script = stage === 'research'
    ? path.join(ROOT, 'scripts/run-family.sh')
    : path.join(ROOT, `scripts/auto${stage}-loop.sh`);
  // The planner picked the family; pass it so the dispatch and the log agree on which one ran.
  const args = stage === 'research' ? [script, target].filter(Boolean) : [script];
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
    const note = stage === 'research'
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

function runDiscover({ dry }) {
  if (dry) return { outcome: 'dry', note: 'would run: node utils/strategy-daily.js' };
  const r = sh('node', ['utils/strategy-daily.js']);
  return { outcome: r.ok ? 'ran' : 'error', note: 'discover + fetch',
           tail: r.out.split('\n').filter(Boolean).slice(-6).join('\n') };
}

function runStage(stage, q, dry) {
  // For `research` the target is REAL, not decorative: the queue is ordered by max post-screen
  // priority and the loop is told to take the head. For the legacy stages the agent still picks
  // its own order, which is why those targets are reported and not passed.
  const target = stage === 'research' ? (q.research[0] || {}).family
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
  else if (stage === 'research' || stage === 'enhance' || stage === 'study') {
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
  const order = PRIORITY.slice(PRIORITY.indexOf(p.stage));
  const cededFrom = [];

  for (const stage of order) {
    if (stage !== p.stage && stage !== 'discover' && depth(stage, p.q) === 0) continue;

    const target = stage === 'enhance' ? (p.q.enhance[0] || {}).family
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
function runChain({ dry = false, maxStages = 6, stageOverride = null } = {}) {
  const log = [];
  let last = null;
  // ⚠ A stage that ran without draining its queue must not be picked again in the same chain.
  // Observed live: enhance "ran", its queue stayed at 13 (the agent recorded no consumption
  // event), so the planner immediately picked enhance again — each repeat resuming a Claude
  // session to redo the same thing. Depth is the honest completion signal here, because the
  // stage's own exit code is not one.
  const before = {};
  for (let i = 0; i < maxStages; i++) {
    const p = plan({ stageOverride: i === 0 ? stageOverride : null });

    if (before[p.stage] != null && depth(p.stage, p.q) >= before[p.stage]) {
      log.push({ stage: p.stage, outcome: 'no-progress',
                 note: `queue still ${depth(p.stage, p.q)} after running — not repeating it this chain` });
      break;
    }
    before[p.stage] = depth(p.stage, p.q);

    if (p.budget.ok && p.budget.used >= USAGE_LIMIT && p.stage !== 'discover') {
      log.push({ stage: p.stage, outcome: 'budget-spent',
                 note: `used ${p.budget.used} >= ${USAGE_LIMIT}` });
      break;
    }
    const r = execute(p, { dry });
    log.push({ stage: r.stage, outcome: r.outcome, note: r.note, cededFrom: r.cededFrom });
    last = r;

    // A stage that could not start, errored, or found nothing will not start next time
    // either — the inputs have not changed. Stopping beats spinning.
    if (['blocked', 'error', 'empty', 'held'].includes(r.outcome)) break;
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
  const ledger = path.join(ROOT, 'harness/normalize-train.tsv');
  if (!fs.existsSync(ledger)) return { added: 0, rows: [] };
  const seen = new Set();
  const rows = [];
  for (const line of fs.readFileSync(ledger, 'utf8').split('\n').slice(1)) {
    const c = line.split('\t');
    if (c[3] !== 'slow-skipped' || !c[0] || seen.has(c[0])) continue;
    seen.add(c[0]);
    rows.push(c[0]);
    // The ledger does not record the cap those runs used; the default was 20.
    if (!dry) state.defer(c[0], { reason: 'slow-skipped (seeded from ledger)', capMin: 20 });
  }
  return { added: rows.length, rows };
}

// ── CLI ─────────────────────────────────────────────────────────────────────

function printPlan(p) {
  const q = p.q;
  console.log(`[daily] budget: ${p.budget.ok ? `used ${p.budget.used} / free ${p.budget.free}` : `UNAVAILABLE (${p.budget.raw})`}`);
  console.log(`[daily] slow-skip cap ${SLOW_SKIP_MIN} min/backtest, usage limit ${USAGE_LIMIT} min/day`);
  console.log('[daily] queues (funnel order — drain the end before widening the mouth):');
  const head = q.research.slice(0, 3)
    .map(x => `${x.family}(${x.score ?? '—'}/${x.reason})`).join(', ') || '—';
  console.log(`   research  ${String(q.research.length).padStart(4)}   ${head}`);
  console.log(`   assign    ${String(q.assign.length).padStart(4)}   normalized but no family: (invisible to the queue)`);
  console.log(`   normalize ${String(q.normalize.total).padStart(4)}   ${q.normalize.pending.length} pending + ${q.normalize.retry.length} deferred-retry`);
  console.log(`   discover  ${String(q.discover.uncopied).padStart(4)}   uncopied of ${q.discover.total} in queue`);
  console.log(`   (legacy: enhance ${q.enhance.length}, study ${q.study.length} — --stage only)`);
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
  const budgetSpent = p.budget.ok && p.budget.used >= USAGE_LIMIT && p.stage !== 'discover';
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
    const once = argv.includes('--once');
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

