/**
 * oos-budget.js — the accounting on the 2026+ out-of-sample reserve.
 *
 * ## The gap this closes
 *
 * `harness/config/epoch-<n>.json` has declared `oosPolicy: { maxTestsPerCandidate: 1,
 * maxTestsPerEpoch: 2 }` since epoch 3, and **nothing enforced it**. The numbers appeared in
 * `harness-config.js`'s console output and in one test asserting the per-epoch figure had gone
 * down, and nowhere else. `assertNotOOS` in `strategy-post-backtest.js` guards the WINDOW — it
 * refuses any run reaching past the cutoff unless `JQ_ALLOW_OOS=1` — but once that flag is set
 * nothing counts the tests. So the reserve could be spent repeatedly with no record, while VAL,
 * the strictly less scarce resource, had `utils/val-budget.js` watching it.
 *
 * ## Why OOS is stricter than VAL
 *
 * VAL is a two-year window a candidate meets once per family. OOS is the LAST clean surface: once
 * a candidate has been looked at there, nothing is left but waiting for more calendar. A
 * selection decision taken after seeing an OOS number is not recoverable by any later discipline,
 * and no re-run, re-scoring or epoch bump un-sees it.
 *
 * So two independent limits, both enforced here:
 *
 *   - **per candidate: 1, ABSOLUTE.** Not per epoch — any epoch. Re-testing the same candidate on
 *     OOS after a bench change is still selection on OOS, one look at a time, which is exactly the
 *     failure the VAL budget documents and refuses ("a different candidate does not buy a second
 *     validation", read in the other direction).
 *   - **per bench: `maxTestsPerEpoch` across the whole repo.** Deliberately per BENCH, not per
 *     epoch NUMBER. A scoring-only bump — epochs 5, 7 and 8 — changes how results are judged and
 *     hands back no fresh 2026 data, so it must not restore the reserve. Keying on equality is the
 *     bug that silently re-granted six validations today (`harness.sameBench`, val-budget).
 *
 * ⚠ **An honest limit of the per-bench rule.** A bump that DOES change the measurement still
 * hands back no new data either — re-running the same nine months under new costs is the same
 * nine months. The declared policy says "per epoch", so that is what is implemented, and the one
 * thing genuinely on our side is that the reserve is a ROLLING window (`holdout.end: "today"`), so
 * real calendar does accumulate between benches. A reader deciding whether to spend the last test
 * should weigh that rather than trusting the counter to be a deep statement about leakage.
 *
 * ## Recording
 *
 * Append-only in `data/consumption.tsv` under `stage: 'oos'`, so the account is the same tracked
 * ledger every other stage writes to. ⚠ `priorTests` also counts a row whose OUTCOME carries an
 * oos verdict wherever it was filed — a VAL recorded under `stage: enhance` was invisible to the
 * VAL budget for weeks, and the same mis-filing must not hide an OOS test. ⚠⚠ But that pattern is
 * narrow by necessity: see `priorTests`, where a bookkeeping NOTE reading `oos-recorded` once
 * counted as a second test and falsely exhausted the reserve.
 *
 * ⚠ **Never record a note whose `outcome` begins with an oos verdict.** Write the research side
 * under `stage: 'research'` with a neutral outcome; the budget has already written the real row.
 *
 * Usage:
 *   const oos = require('./oos-budget');
 *   oos.check('<candidateId>', { family })    // { allowed, reason, why, used, remaining }
 *   oos.record('<candidateId>', { family, outcome, note })
 *
 *   node utils/oos-budget.js                  # the reserve's state
 *   node utils/oos-budget.js <candidateId>    # may this candidate be tested?
 */

const harness = require('./harness-config');
const consumption = require('./consumption');

/** Human-only, and separate from JQ_ALLOW_OOS: that unlocks the WINDOW, this the BUDGET. */
const OVERRIDE = () => process.env.JQ_ALLOW_OOS_OVERBUDGET === '1';

const activeEpoch = () => harness.config().epoch;
const policy = () => harness.config().oosPolicy || {};

/**
 * Every recorded OOS test, however it was filed.
 *
 * ⚠⚠ The outcome pattern is NARROW on purpose, and the reason is a mistake made on 2026-10-17:
 * a bookkeeping note recorded as `stage: 'research'` with `outcome: 'oos-recorded'` matched a bare
 * `/^oos-/` and pushed the bench to a false 2 of 2 — i.e. a NOTE about a test read as a second
 * test and appeared to exhaust the reserve. `consumption.tsv` is append-only, so the row cannot be
 * withdrawn; the reading is what gets corrected.
 *
 * So the match is on the VERDICT SHAPES `oos-budget.record()` actually emits — `oos-sharpe …`,
 * `oos-completed`, and `oos-pass`/`oos-fail` for safety — rather than on any string beginning
 * "oos-". A properly filed row (`stage: 'oos'`) is still counted whatever its outcome says, which
 * is what catches the mis-staged case this clause exists for (the VAL budget lost a spent
 * validation to exactly that, `etfmom-005` under `stage: enhance`).
 */
function priorTests() {
  const VERDICT = /^oos-(sharpe|completed|pass|fail)\b/i;
  return consumption.events({})
    .filter(e => e.stage === 'oos' || VERDICT.test(String(e.outcome || '').trim()));
}

/** Tests charged against the CURRENT bench (a scoring-only bump does not restore the reserve). */
function testsOnThisBench() {
  const epoch = activeEpoch();
  // An unstamped row cannot be shown to belong to an older bench, so it counts. Unknown must
  // block rather than permit: a false block is one command for a human to clear, a false permit
  // spends the last clean surface in the repo.
  return priorTests().filter(e => !e.epoch || harness.sameBench(e.epoch, epoch));
}

/**
 * May `candidateId` be tested on the OOS reserve right now?
 *
 * `candidateId` is the thing being tested — an `expId` or a `sourceFile` — NOT the family. The
 * per-candidate limit is about one specific book meeting the held-out data once.
 */
function check(candidateId, { family = null } = {}) {
  const epoch = activeEpoch();
  const perCandidate = policy().maxTestsPerCandidate == null ? 1 : policy().maxTestsPerCandidate;
  const perEpoch = policy().maxTestsPerEpoch == null ? 2 : policy().maxTestsPerEpoch;

  if (!candidateId) {
    return { allowed: false, reason: 'no-candidate', used: null, remaining: null,
             why: 'OOS-BLOCKED: a candidate id is required. The budget is per candidate, so a ' +
                  'test that does not say what it tested cannot be charged to anything — and an ' +
                  'uncharged OOS test is exactly how a reserve gets spent twice.' };
  }

  const bench = testsOnThisBench();
  const used = bench.length;
  const remaining = Math.max(0, perEpoch - used);

  // Per candidate, across EVERY epoch — see the header.
  const mine = priorTests().filter(e => e.key === candidateId);
  if (mine.length >= perCandidate) {
    const p = mine[mine.length - 1];
    const detail = `${candidateId} was already tested on OOS on ${String(p.at || '').slice(0, 10)}` +
                   ` as "${p.runId || 'unnamed'}" -> ${p.outcome || '?'}` +
                   (p.epoch ? ` (epoch ${p.epoch})` : ' (epoch not recorded)');
    if (OVERRIDE()) {
      return { allowed: true, reason: 'human-override', used, remaining, prior: mine,
               why: `JQ_ALLOW_OOS_OVERBUDGET=1 — ${detail}. This looks at the reserve a second ` +
                    'time with the same candidate; it is recorded as an override.' };
    }
    return { allowed: false, reason: 'candidate-already-tested', used, remaining, prior: mine,
             why: `OOS-BLOCKED: ${detail}. The limit is ${perCandidate} test per CANDIDATE, in ` +
                  'any epoch — re-testing the same book on the reserve is selection on OOS one ' +
                  'look at a time, and no later discipline un-sees it. ' +
                  '(User-only override: JQ_ALLOW_OOS_OVERBUDGET=1.)' };
  }

  if (used >= perEpoch) {
    const names = bench.map(e => `${e.key}/${e.runId || '?'}`).join(', ');
    if (OVERRIDE()) {
      return { allowed: true, reason: 'human-override', used, remaining, prior: bench,
               why: `JQ_ALLOW_OOS_OVERBUDGET=1 — the bench's ${perEpoch} OOS tests are already ` +
                    `spent (${names}). Recorded as an override.` };
    }
    return { allowed: false, reason: 'bench-budget-spent', used, remaining, prior: bench,
             why: `OOS-BLOCKED: this bench's ${perEpoch} OOS test(s) are already spent (${names}). ` +
                  '⚠ A SCORING-ONLY epoch bump does not restore them — it hands back no fresh ' +
                  '2026 data, so the reserve is per BENCH. Wait for a bench change, or for enough ' +
                  'calendar that the rolling reserve is materially longer. ' +
                  '(User-only override: JQ_ALLOW_OOS_OVERBUDGET=1.)' };
  }

  return { allowed: true, reason: used === 0 ? 'first-of-bench' : 'within-budget',
           used, remaining, prior: bench,
           why: `${used} of ${perEpoch} OOS test(s) spent on epoch ${epoch}'s bench; ` +
                `${candidateId} has never been tested` + (family ? ` (family ${family})` : '') };
}

/**
 * Record a spent OOS test. Returns false if this exact (candidateId, runId) was already recorded,
 * so a retry cannot double-count.
 *
 * ⚠ `epoch` is stamped by `consumption.record()` from the live config and is never passed in — a
 * caller that could choose its own epoch could make a spent test look like it belonged to an older
 * bench and free up the reserve.
 */
function record(candidateId, runId, { family = null, outcome = '', note = '' } = {}) {
  if (!candidateId) throw new Error('oos-budget.record needs a candidateId');
  if (!runId) throw new Error('oos-budget.record needs a runId — the test must be identifiable');
  const dup = priorTests().some(e => e.key === candidateId && e.runId === runId);
  if (dup) return false;
  consumption.record({
    key: candidateId, kind: 'candidate', stage: 'oos', runId,
    outcome: /^oos-/i.test(outcome) ? outcome : `oos-${outcome || 'completed'}`,
    note: (family ? `family ${family}. ` : '') + note,
  });
  return true;
}

if (require.main === module) {
  const argv = process.argv.slice(2);
  const candidate = argv.find(a => !a.startsWith('--'));
  const epoch = activeEpoch();
  const perEpoch = policy().maxTestsPerEpoch == null ? 2 : policy().maxTestsPerEpoch;
  const w = harness.window('holdout');

  console.log(`[oos] epoch ${epoch} reserve: ${w.start} .. ${w.end}  ` +
              `(rolling — it lengthens with the calendar)`);
  console.log(`[oos] policy: ${policy().maxTestsPerCandidate} test/candidate (absolute), ` +
              `${perEpoch}/bench`);

  const bench = testsOnThisBench();
  console.log(`[oos] spent on this bench: ${bench.length} of ${perEpoch}`);
  for (const e of bench) {
    console.log(`   ${e.key} / ${e.runId || '?'} -> ${e.outcome || '?'}` +
                `  ${String(e.at || '').slice(0, 10)}  e${e.epoch || '?'}`);
  }
  const all = priorTests();
  if (all.length > bench.length) {
    console.log(`[oos] ${all.length - bench.length} test(s) charged to EARLIER benches (not restored)`);
  }

  if (candidate) {
    const r = check(candidate);
    console.log(`\n[oos] ${candidate}: ${r.allowed ? 'ALLOWED' : 'BLOCKED'} (${r.reason})`);
    console.log(`      ${r.why}`);
    process.exitCode = r.allowed ? 0 : 3;
  } else if (!all.length) {
    console.log('\n[oos] nothing has ever been tested on the reserve.');
    console.log('[oos] ⚠ Spending a test needs BOTH switches, and both are the human\'s:');
    console.log('[oos]     JQ_ALLOW_OOS=1             unlocks the window (assertNotOOS)');
    console.log('[oos]     JQ_ALLOW_OOS_OVERBUDGET=1  only to exceed the budget above');
  }
}

module.exports = { check, record, priorTests, testsOnThisBench, activeEpoch, policy };
