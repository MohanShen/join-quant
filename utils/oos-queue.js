/**
 * oos-queue.js — which promoted candidate is READY for the out-of-sample reserve, and which is not.
 *
 * ## The gap this closes
 *
 * `integrate` writes `data/promoted.tsv`; OOS is the step after it. But nothing connected the two:
 * `daily-pipeline --plan` printed only `oos  1  test(s) left on this bench`, a count of remaining
 * BUDGET. It never said *which candidate* was waiting, so "integrate produced something new" and
 * "something is ready for the final surface" were facts a human had to join by hand — and the
 * promoted register is append-only prose, so joining it by hand means reading notes.
 *
 * This derives the join: for every universe's CURRENT promoted candidate, has it been tested, may
 * it be tested, and is it the kind of artifact the executor's readiness gate will accept.
 *
 * ## ⚠⚠ It reports. It never dispatches, and that is not a gap
 *
 * The reserve is **2 tests per bench, 1 per candidate, absolute** (`utils/oos-budget.js`). A
 * promoted candidate appearing here is *not* authorisation to spend one. In particular, when
 * integrate supersedes a candidate with a slightly-changed one, testing the new one is a SECOND
 * look at the same held-out window — which `harness/harness.md` and the VAL budget both name as
 * the failure it exists to prevent: selection on the last clean surface, one look at a time. So a
 * superseding candidate shows up here as `ready`, and whether that is worth one of two tests is a
 * judgement with no undo. `/run-oos` is the entry point; `oos` is deliberately absent from
 * `PRIORITY` and will stay absent.
 *
 * Usage:
 *   const oosq = require('./oos-queue');
 *   oosq.build()        // [{ universe, candidateId, members, state, why, ... }]
 *   node utils/oos-queue.js
 */

const fs = require('fs');
const path = require('path');
const promoted = require('./promoted');
const oosBudget = require('./oos-budget');

const ROOT = path.resolve(__dirname, '..');
/** The three markers `strategy-post-backtest.missingPins()` looks for. */
const PINS = ['avoid_future_data', 'order_volume_ratio', 'set_order_cost'];
const isPinned = f => {
  try {
    const c = fs.readFileSync(path.join(ROOT, f), 'utf8');
    return PINS.every(k => c.includes(k));
  } catch { return false; }
};

/**
 * The PINNED, RUNNABLE artifact for a promoted candidate — which is often not the candidate's own
 * path.
 *
 * ⚠⚠ Found while preparing 红利低频's test, and it would have made this stage dispatch a session
 * that could not run. A universe may promote a raw INGESTED member (`strategies/*.py`), because
 * that is what `integrate-eligible` names when a family has no shelf product. But `strategies/` is
 * the immutable raw layer and carries **none of the frozen pins** — 93379f98 is missing
 * `order_volume_ratio` — so the executor refuses with `UNPINNED-STOP` before spending anything.
 * It does not inject pins; only `strategy-normalize.js` (into a temp copy) and
 * `enhance/strategy_template.py` supply them. And the normalizer never passes `--allow-oos`, so
 * there is no path to the holdout window through it either.
 *
 * The runnable form of such a book is the family's own pinned baseline, which is also the artifact
 * its VAL actually ran — for 红利低频 the stored curve `study_红利低频_baseline__val__e6` proves it.
 * Run that, and pass `--source-file <candidateId>` so the budget, the promoted register and the
 * stored curve all key on the book rather than on the copy.
 *
 * @returns {{file:string|null, via:string}}
 */
function runnableArtifact(candidateId, members) {
  if (!candidateId) return { file: null, via: 'no candidate' };
  if (isPinned(candidateId)) return { file: candidateId, via: 'the candidate itself is pinned' };
  // A raw ingested member: its pinned, already-validated form is the family's baseline.
  for (const fam of members || []) {
    const b = `study/${fam}/baseline.py`;
    if (isPinned(b)) return { file: b, via: `pinned baseline of ${fam} (what its VAL ran)` };
  }
  return { file: null,
           via: `${candidateId} carries no frozen pins and no pinned baseline was found — ` +
                'the executor would refuse with UNPINNED-STOP' };
}

/**
 * Every universe's current promoted candidate, with its OOS state.
 *
 * `state` is one of:
 *   `ready`   — never tested, budget available. A human decides whether to spend a test.
 *   `tested`  — this exact candidate already met the reserve; the outcome is carried.
 *   `blocked` — the bench's tests are spent, or the budget refuses for another stated reason.
 */
function build() {
  let current = [];
  try { current = promoted.current() || []; } catch { return []; }

  let prior = [];
  try { prior = oosBudget.priorTests(); } catch { prior = []; }

  const out = [];
  for (const c of current) {
    const id = c.candidateId;
    if (!id) continue;
    const mine = prior.filter(e => e.key === id);
    let check = { allowed: false, reason: 'unknown', why: 'oos-budget unavailable' };
    try { check = oosBudget.check(id, { family: (c.members || [])[0] || null }); } catch { /* keep default */ }

    // ⚠ A tested candidate is reported, not hidden. The register carries the result in its note,
    // and "this universe already spent its look" is exactly what a reader needs to know before
    // asking for another.
    // ⚠ Resolve the runnable artifact BEFORE calling anything ready. A promoted candidate with no
    // pinned form cannot be tested at all, and a queue that says `ready` would dispatch a session
    // straight into UNPINNED-STOP.
    const art = runnableArtifact(id, c.members);

    const state = mine.length ? 'tested'
      : !art.file ? 'unrunnable'
      : check.allowed ? 'ready' : 'blocked';

    // ⚠ Flag a candidate whose own TRAIN sharpe is below the stage gate.
    //
    // The budget says whether a test is PERMITTED; it never says whether the candidate deserves
    // one, and `integrate-eligible` checks the VAL sharpe rather than the champion's TRAIN sharpe
    // — a gap CLAUDE.md records. Live consequence: 红利低频 is promoted and OOS-ready on a champion
    // at sharpe 1.46, below the 1.5 every other stage holds. That is exactly what a reader needs
    // in front of them before spending one of two irreversible tests, so it travels with the row
    // instead of being something they have to remember.
    const flags = [];
    try {
      const harness = require('./harness-config');
      if (c.sharpe != null && !harness.stageGate('validate', c.sharpe)) {
        flags.push(`train-sharpe ${c.sharpe} below the ${harness.stageThreshold('validate')} gate`);
      }
    } catch { /* harness unavailable — no flag rather than a wrong one */ }

    out.push({
      flags,
      runFile: art.file,
      runVia: art.via,
      universe: c.universe || (c.members || []).join('+') || '(unknown)',
      candidateId: id,
      kind: c.kind || 'family',
      members: c.members || [],
      sharpe: c.sharpe ?? null,
      objective: c.objective ?? null,
      epoch: c.epoch || null,
      state,
      why: mine.length
        ? `already tested as ${mine[mine.length - 1].runId || 'unnamed'} -> ${mine[mine.length - 1].outcome || '?'}`
        : !art.file ? art.via
        : check.why,
      used: check.used ?? null,
      remaining: check.remaining ?? null,
    });
  }
  // Ready first — that is the only actionable state.
  const rank = s => (s === 'ready' ? 0 : s === 'unrunnable' ? 1 : s === 'blocked' ? 2 : 3);
  return out.sort((a, b) => rank(a.state) - rank(b.state)
                         || (b.sharpe ?? -Infinity) - (a.sharpe ?? -Infinity));
}

/** Just the actionable ones, for a planner line. */
const ready = () => build().filter(r => r.state === 'ready');

if (require.main === module) {
  const rows = build();
  const w = require('./harness-config').window('holdout');
  console.log(`[oosq] reserve ${w.start} .. ${w.end} (rolling)`);
  console.log('[oosq] ⚠ REPORTS ONLY — 2 tests per bench, 1 per candidate, absolute. Spending one');
  console.log('[oosq]   is a human decision with no undo: /run-oos\n');
  if (!rows.length) {
    console.log('  nothing promoted — integrate has shipped no candidate yet');
  }
  for (const r of rows) {
    const tag = { ready: 'READY  ', tested: 'tested ', unrunnable: 'NO-PINS', blocked: 'BLOCKED' }[r.state];
    console.log(`  ${tag} ${String(r.universe).padEnd(8)} ${r.kind.padEnd(7)} ` +
                `sharpe ${String(r.sharpe ?? '?').padStart(6)}  ${r.candidateId}`);
    console.log(`          ${r.why}`);
    for (const f of r.flags || []) console.log(`          ⚠ ${f}`);
    if (r.runFile && r.runFile !== r.candidateId) {
      console.log(`          run: ${r.runFile}  (${r.runVia})`);
      console.log(`          and pass --source-file ${r.candidateId} so the budget charges the book`);
    }
  }
  const n = rows.filter(r => r.state === 'ready').length;
  const by = st => rows.filter(r => r.state === st).length;
  console.log(`\n[oosq] ${n} ready, ${by('tested')} tested, ${by('unrunnable')} unrunnable (no pins), ` +
              `${by('blocked')} blocked`);
}

module.exports = { build, ready };
