/**
 * daily-pipeline.js — one day's worth of pipeline, chosen by queue priority under a fixed
 * backtest budget.
 *
 * The rule (user's, 2026-09-20): **later stages outrank earlier ones** —
 *
 *     enhance  >  study  >  normalize  >  discover+fetch
 *
 * This is a pull system: finish what is already in the pipe before admitting more. The 60
 * backtest-minutes a day are the binding constraint, so an idle enhance-ready family is a
 * worse use of them than a raw strategy that cannot be acted on yet.
 *
 * ⚠ A consequence worth stating rather than discovering: while ANY family is enhance-ready,
 * normalization never runs. With 13 families never enhanced and 53 strategies pending, the
 * normalize queue starves indefinitely — by design, but only correct if you agree that
 * draining the end of the pipe beats widening its mouth. `--plan` shows every queue's depth so
 * the starvation is visible, and `--stage <name>` overrides the pick for a day.
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

/** This pipeline's per-backtest cap, in minutes. */
const SLOW_SKIP_MIN = 30;
/** Daily backtest ceiling handed to every child. */
const USAGE_LIMIT = 55;
/** Stage order: later stages first. Index 0 wins. */
const PRIORITY = ['enhance', 'study', 'normalize', 'discover'];

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
  return {
    enhance: staleFamilies('enhance', { requireBest: true }),
    study: staleFamilies('study'),
    normalize: normalizeQueue(),
    discover: discoverQueue(),
  };
}

const depth = (stage, q) =>
  stage === 'normalize' ? q.normalize.total
  : stage === 'discover' ? q.discover.uncopied
  : q[stage].length;

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

function sh(cmd, args, { timeout = 3.6e6 } = {}) {
  try {
    const out = execFileSync(cmd, args, { encoding: 'utf8', cwd: ROOT, timeout });
    return { ok: true, out };
  } catch (e) {
    return { ok: false, out: `${e.stdout || ''}${e.stderr || ''}${e.message}`.slice(0, 4000) };
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
function sessionPinned(stage) {
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
  const pin = sessionPinned(stage);
  if (!pin.pinned) {
    return {
      outcome: 'blocked',
      note: `${stage} needs a pinned Claude session (${pin.why}). ` +
            `Start it once interactively: scripts/auto${stage}-interactive.sh — ` +
            `the cron can only RESUME, never cold-start an agent loop.`,
    };
  }
  const script = path.join(ROOT, `scripts/auto${stage}-loop.sh`);
  if (!fs.existsSync(script)) return { outcome: 'error', note: `missing ${path.relative(ROOT, script)}` };
  // ⚠ `target` is the head of OUR queue, reported for the log only — it is not passed to the
  // agent and does not steer it. The study nudge tells the agent to take "the next pending
  // family (strongest bestObjective first)" from study/manifest.json, which is a different
  // ordering over the same set. Claiming to have targeted a family would be a fiction; what
  // the planner actually controls is WHICH STAGE runs, and (via syncStudyManifest) which
  // families are eligible at all.
  if (dry) {
    return { outcome: 'dry',
             note: `would resume session ${pin.detail} via ${path.relative(ROOT, script)}` +
                   `; our queue head is ${target || 'n/a'} (agent picks its own order)` };
  }
  const r = sh('bash', [script]);
  return { outcome: r.ok ? 'ran' : 'error',
           note: `resumed ${stage} session ${pin.detail} (exit 0 is NOT proof work happened — check its ledger)`,
           tail: r.out.split('\n').filter(Boolean).slice(-6).join('\n') };
}

function runDiscover({ dry }) {
  if (dry) return { outcome: 'dry', note: 'would run: node utils/strategy-daily.js' };
  const r = sh('node', ['utils/strategy-daily.js']);
  return { outcome: r.ok ? 'ran' : 'error', note: 'discover + fetch',
           tail: r.out.split('\n').filter(Boolean).slice(-6).join('\n') };
}

function runStage(stage, q, dry) {
  const target = stage === 'enhance' ? (q.enhance[0] || {}).family
    : stage === 'study' ? (q.study[0] || {}).family : null;
  let r;
  if (stage === 'normalize') r = runNormalize(q, { dry });
  else if (stage === 'enhance' || stage === 'study') r = runAgentLoop(stage, target, { dry });
  else r = runDiscover({ dry });
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
  for (let i = 0; i < maxStages; i++) {
    const p = plan({ stageOverride: i === 0 ? stageOverride : null });

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
  console.log('[daily] queues (priority order — later stages first):');
  console.log(`   enhance   ${String(q.enhance.length).padStart(4)}   ${q.enhance.slice(0, 3).map(x => x.family).join(', ') || '—'}`);
  console.log(`   study     ${String(q.study.length).padStart(4)}   ${q.study.slice(0, 3).map(x => x.family).join(', ') || '—'}`);
  console.log(`   normalize ${String(q.normalize.total).padStart(4)}   ${q.normalize.pending.length} pending + ${q.normalize.retry.length} deferred-retry`);
  console.log(`   discover  ${String(q.discover.uncopied).padStart(4)}   uncopied of ${q.discover.total} in queue`);
  console.log(`[daily] -> ${p.stage.toUpperCase()}   (${p.why})`);
}

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

  if (p.budget.ok && p.budget.used >= USAGE_LIMIT && p.stage !== 'discover') {
    console.log(`[daily] budget spent (${p.budget.used} >= ${USAGE_LIMIT}) — clean stop, nothing started`);
    process.exit(0);
  }

  // Keep the agent's own queue honest before dispatching — see syncStudyManifest.
  const sync = syncStudyManifest({ dry: argv.includes('--dry') });
  if (sync.changed.length) {
    console.log(`[daily] study manifest: reopened ${sync.changed.length} family(ies) the ledger calls stale`);
    sync.changed.slice(0, 4).forEach(c => console.log(`         ${c.family}  (${c.why})`));
  }

  const dry = argv.includes('--dry');
  const once = argv.includes('--once');
  const { log, last } = once
    ? (() => { const r = execute(p, { dry }); return { log: [r], last: r }; })()
    : runChain({ dry, stageOverride: arg('--stage') });

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

module.exports = { plan, queues, execute, budget, seedDeferred, staleFamilies,
                   runChain, syncStudyManifest,
                   SLOW_SKIP_MIN, USAGE_LIMIT, PRIORITY };
