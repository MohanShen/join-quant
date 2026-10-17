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

const promoted = require('./promoted');
const oosBudget = require('./oos-budget');

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
    const state = mine.length ? 'tested' : check.allowed ? 'ready' : 'blocked';

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
        : check.why,
      used: check.used ?? null,
      remaining: check.remaining ?? null,
    });
  }
  // Ready first — that is the only actionable state.
  const rank = s => (s === 'ready' ? 0 : s === 'blocked' ? 1 : 2);
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
    const tag = r.state === 'ready' ? 'READY  ' : r.state === 'tested' ? 'tested ' : 'BLOCKED';
    console.log(`  ${tag} ${String(r.universe).padEnd(8)} ${r.kind.padEnd(7)} ` +
                `sharpe ${String(r.sharpe ?? '?').padStart(6)}  ${r.candidateId}`);
    console.log(`          ${r.why}`);
    for (const f of r.flags || []) console.log(`          ⚠ ${f}`);
  }
  const n = rows.filter(r => r.state === 'ready').length;
  console.log(`\n[oosq] ${n} ready, ${rows.filter(r => r.state === 'tested').length} already tested, ` +
              `${rows.filter(r => r.state === 'blocked').length} blocked`);
}

module.exports = { build, ready };
