/**
 * The VAL budget: one validation per (family, epoch).
 *
 * TRAIN is where selection happens and may be re-run freely. VAL answers "does the thing we chose
 * on TRAIN survive data we did not choose it with", and that question can be asked once. Nothing
 * protected it — `assertNotOOS` guards the 2026 reserve and `stageGate` sets a threshold, but a
 * family could be validated any number of times. That was tolerable only while VAL was reached
 * rarely; it stops being tolerable when validation becomes a terminal stage every family passes
 * through and that reopens as members arrive.
 *
 * The failure is quiet and permanent: validate five candidates, keep the best number, and VAL is a
 * second training set — no error, no flag. And it cannot be walked back, because the only clean
 * surface left is the OOS reserve (~9 months, 2 tests per epoch).
 *
 * ⚠ State is redirected to a temp file before anything is required. data/consumption.tsv is
 * TRACKED, and a stray probe row here would silently cost a real family its one validation.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'jq-val-'));
process.env.JQ_CONSUMPTION_FILE = path.join(TMP, 'consumption.tsv');
// The budget refuses a family it cannot account for, so the synthetic ones need pages.
process.env.JQ_FAMILIES_DIR = path.join(TMP, 'families');
fs.mkdirSync(process.env.JQ_FAMILIES_DIR, { recursive: true });
for (const f of ['家族A', '家族B', '家族C', 'TEST家族']) {
  fs.writeFileSync(path.join(process.env.JQ_FAMILIES_DIR, `${f}.md`), `---\nfamily: ${f}\n---\n`);
}

const val = require('../utils/val-budget');
const consumption = require('../utils/consumption');
const harness = require('../utils/harness-config');

const reset = () => { try { fs.unlinkSync(process.env.JQ_CONSUMPTION_FILE); } catch {} };

test('VAL budget', async (t) => {
  await t.test('a family that has never validated may validate', () => {
    reset();
    const v = val.check('家族A');
    assert.strictEqual(v.allowed, true);
    assert.strictEqual(v.reason, 'first-of-epoch');
  });

  await t.test('the second validation in the same epoch is refused', () => {
    reset();
    val.record('家族A', 'cand-001', { outcome: 'sharpe 3.1' });
    const v = val.check('家族A');
    assert.strictEqual(v.allowed, false);
    assert.strictEqual(v.reason, 'already-validated');
    assert.match(v.why, /VAL-BLOCKED/);
    assert.match(v.why, /cand-001/, 'the refusal must name what already spent the budget');
  });

  await t.test('a SCORING-ONLY epoch bump does NOT reset the budget', () => {
    // ⚠⚠ The live bug, found 2026-10-16. The filter was `e.epoch === epoch`, so the moment
    // epochs 7 and 8 activated — both scoring-only, both leaving the measurement bench
    // byte-identical — every family read ALLOWED (first-of-epoch), including all six that had
    // already validated at epoch 6. The single most protected resource in the repo was silently
    // re-granted by a bump that measured nothing.
    //
    // Same bug class as the normalizer's old `rowEpoch === ACTIVE_EPOCH` done-check, which
    // `measurementValid()` exists to fix; the VAL budget never received that fix.
    reset();
    const active = harness.config().epoch;
    // Find a comparable-but-earlier epoch, i.e. one a scoring-only bump preserved.
    const earlier = [...harness.comparableEpochs()].filter(e => e < active).sort((a, b) => b - a)[0];
    if (earlier == null) return;        // nothing to prove on a bench with no preserved predecessor
    consumption.record({ key: '家族B', kind: 'family', stage: 'validate',
                         runId: 'old-bench-val', outcome: 'sharpe 2.05' });
    // Rewrite that row's epoch to the earlier one — record() stamps the live epoch on purpose.
    const f = process.env.JQ_CONSUMPTION_FILE;
    const lines = fs.readFileSync(f, 'utf8').trimEnd().split('\n');
    const cols = lines[lines.length - 1].split('\t');
    cols[9] = String(earlier);
    lines[lines.length - 1] = cols.join('\t');
    fs.writeFileSync(f, lines.join('\n') + '\n');

    const v = val.check('家族B');
    assert.strictEqual(v.allowed, false,
      `an epoch-${earlier} VAL must still block at epoch ${active} — the bench is identical`);
    assert.strictEqual(v.reason, 'already-validated');
    assert.match(v.why, /SCORING-ONLY epoch bump does not reset it/i);
  });

  await t.test('a bump that DID change the measurement does re-authorize it', () => {
    // The inverse must keep working: epoch 6 pinned stock costs, so it changed fills and fees and
    // an epoch-5 VAL is genuinely not a current result. Blocking on it would strand a family
    // forever on a bench that no longer exists.
    reset();
    const stale = [...Array(5).keys()].map(i => i + 1)
      .find(e => !harness.measurementValid(e));
    if (stale == null) return;
    consumption.record({ key: '家族C', kind: 'family', stage: 'validate',
                         runId: 'stale-bench-val', outcome: 'sharpe 9.9' });
    const f = process.env.JQ_CONSUMPTION_FILE;
    const lines = fs.readFileSync(f, 'utf8').trimEnd().split('\n');
    const cols = lines[lines.length - 1].split('\t');
    cols[9] = String(stale);
    lines[lines.length - 1] = cols.join('\t');
    fs.writeFileSync(f, lines.join('\n') + '\n');

    const v = val.check('家族C');
    assert.strictEqual(v.allowed, true,
      `an epoch-${stale} VAL must NOT block — that bench changed fills and fees`);
  });

  await t.test('A DIFFERENT CANDIDATE does not re-authorize it', () => {
    // The proposal drafted "unless the finalized candidate itself changed" and it is deliberately
    // NOT implemented: an agent that produces a new candidate whenever the last VAL disappoints is
    // doing selection on VAL one run at a time, and every one of those runs satisfies that clause.
    reset();
    val.record('家族A', 'cand-001', { outcome: 'sharpe 3.1' });
    assert.strictEqual(val.check('家族A').allowed, false,
      'a new candidate must NOT buy a second validation — that is the hole the rule closes');
  });

  await t.test('a different family is unaffected', () => {
    reset();
    val.record('家族A', 'cand-001', {});
    assert.strictEqual(val.check('家族B').allowed, true);
  });

  await t.test('a prior validation at ANOTHER epoch does not block', () => {
    reset();
    val.record('家族A', 'cand-001', {});
    const older = String(Number(harness.config().epoch) + 1);
    assert.strictEqual(val.check('家族A', { epoch: older }).allowed, true,
      'the budget is per (family, EPOCH) — a new bench grants a new validation');
  });

  await t.test('a VAL filed under ANOTHER stage still counts as spent', () => {
    // ⚠⚠ Live case: `etfmom-005` sits under stage `enhance` with outcome `val-pass`, and
    // data/series/enhance_candidates_etfmom-005__val__e6.json proves the VAL-window run happened.
    // Filtering on stage alone missed it and reported ETF动量 as never validated — while that
    // family's own §4 had already written down that the budget 「误报 ALLOWED」 and the VAL should
    // be treated as spent. The page knew; the code did not.
    reset();
    consumption.record({ key: '家族A', kind: 'family', stage: 'enhance',
                         runId: 'cand-mis-filed', outcome: 'val-pass' });
    const v = val.check('家族A');
    assert.strictEqual(v.allowed, false,
      'a validation recorded under the wrong stage is still a validation spent');
    assert.match(v.why, /cand-mis-filed/, 'the refusal must name what spent it');
  });

  await t.test('the match is narrow — an ordinary outcome does not block', () => {
    // A false block is cheap to clear; a false permit silently spends the one window. But
    // over-matching "val" anywhere would block families that never validated, so the rule keys on
    // the recorded verdict SHAPE (val-pass / val-fail) rather than the substring.
    reset();
    for (const outcome of ['reject', 'keep-with-caveat', 'promoted', 'logged-only', 'done',
                           'sharpe 2.05', 'approval pending', 'interval swept']) {
      consumption.record({ key: 'TEST家族', kind: 'family', stage: 'research',
                           runId: 'r-' + outcome.slice(0, 4), outcome });
    }
    assert.strictEqual(val.check('TEST家族').allowed, true,
      `none of those outcomes is a validation: ${val.check('TEST家族').why}`);
  });

  await t.test('a DECLINE is not a validation — recording one must not spend the window', () => {
    // ⚠⚠ Live bug, 2026-10-31. 资产配置's first research round decided NOT to spend its VAL and
    // recorded that as `stage: research, outcome: val-declined` — which is the documented way to
    // make the loop converge instead of being re-dispatched daily. The filter was a bare
    // `/^val-/`, so it counted the decline as a spend: check() returned
    // "already validated … as run-family-2026-10-31" for a family with zero validation RUNS.
    //
    // Exactly the bug oos-budget already fixed on its own side ("a NOTE about an OOS test must not
    // look like one", where stage: research / outcome: oos-recorded pushed the bench to a false
    // 2 of 2). The decline is the one row whose whole purpose is to say the window was NOT used.
    reset();
    for (const outcome of ['val-declined', 'val-skipped', 'val-deferred']) {
      consumption.record({ key: '家族A', kind: 'family', stage: 'research',
                           runId: 'decision-' + outcome, outcome });
    }
    const v = val.check('家族A');
    assert.strictEqual(v.allowed, true,
      `a recorded decision not to validate must leave the window available: ${v.why}`);
  });

  await t.test('a decline filed under the validate stage is still not a validation', () => {
    // The stage arm counts anything under `validate` regardless of outcome, which is right for a
    // run but would re-open the hole if a round filed its DECISION there. The decision check runs
    // first, so stage cannot override it.
    reset();
    consumption.record({ key: '家族A', kind: 'family', stage: 'validate',
                         runId: 'mis-staged-decline', outcome: 'val-declined' });
    assert.strictEqual(val.check('家族A').allowed, true,
      'a decline is never a validation, whatever stage it was filed under');
  });

  await t.test('a DISQUALIFIED run still counts — it saw the window', () => {
    // val-dq is a RUN verdict, not a decision: the backtest executed on VAL data. Live row exists
    // (UNRESOLVED:jul12-023). Excluding it would hand back a window that was actually looked at.
    reset();
    consumption.record({ key: '家族A', kind: 'family', stage: 'enhance',
                         runId: 'dq-run', outcome: 'val-dq' });
    assert.strictEqual(val.check('家族A').allowed, false,
      'a disqualified VAL run still spent the window');
  });

  await t.test('an UNKNOWN epoch blocks, because VAL cannot be un-spent', () => {
    // Rows written before consumption.tsv gained its epoch column carry none. Blocking is visible
    // and a human clears it in one command; permitting silently re-spends the protected resource.
    reset();
    consumption.record({ key: '家族C', kind: 'family', stage: 'validate', runId: 'old', outcome: 'ok' });
    const f = process.env.JQ_CONSUMPTION_FILE;
    fs.writeFileSync(f, fs.readFileSync(f, 'utf8').split('\n')
      .map(l => l.startsWith('家族C\t') ? l.replace(/\t\d+$/, '\t') : l).join('\n'));
    const v = val.check('家族C');
    assert.strictEqual(v.allowed, false);
    assert.strictEqual(v.reason, 'prior-unknown-epoch');
  });

  await t.test('a run with no family is refused — an unnamed VAL is an untracked VAL', () => {
    reset();
    const v = val.check(null);
    assert.strictEqual(v.allowed, false);
    assert.strictEqual(v.reason, 'no-family');
  });

  await t.test('every event the rule writes is stamped with the epoch', () => {
    reset();
    val.record('家族A', 'cand-001', {});
    const e = consumption.events({ stage: 'validate', key: '家族A' })[0];
    assert.strictEqual(e.epoch, String(harness.config().epoch),
      'without an epoch on the row the ledger cannot say which bench a validation belongs to');
  });
});

test('VAL budget is enforced in the executor, not merely documented', async (t) => {
  const src = fs.readFileSync(path.join(__dirname, '../utils/strategy-post-backtest.js'), 'utf8');

  await t.test('--window val without --family is refused at parse time', () => {
    // Before the browser opens and before a minute is spent.
    assert.match(src, /assertValWindowNamesFamily/);
    assert.match(src, /VAL-BLOCKED: --window val requires --family/);
  });

  await t.test('the budget is checked before any browser work', () => {
    const check = src.indexOf("require('./val-budget')");
    const browser = src.indexOf('connectOverCDP');
    assert.ok(check > 0 && check < browser,
      'the VAL check must run before CDP — a refusal should cost nothing');
  });

  await t.test('a refusal exits non-zero and is machine-readable', () => {
    assert.match(src, /VAL-BUDGET\\tfamily=/, 'needs a parseable marker, like USAGE-STOP');
    assert.match(src, /process\.exit\(3\)/);
  });

  await t.test('the budget is spent only by a COMPLETED run', () => {
    // A compile-error or slow-skip produces no number, so nothing was learned about the held-out
    // window and the family should not lose its one validation.
    assert.match(src, /status !== 'completed'/,
      'the spend must be gated on a completed run');
    assert.match(src, /function recordValIfCompleted\(status, family, runId, window, result\)[\s\S]{0,200}status !== 'completed'[\s\S]{0,40}return;/,
      'the gate must be inside the recorder, so no path can spend the budget without a number');
  });

  await t.test('a failure to record shouts, because silence would grant a second VAL', () => {
    assert.match(src, /FAILED to record the VAL spend/);
  });

  await t.test('TRAIN is untouched', () => {
    assert.match(src, /window\.name !== 'val'\) return/,
      'the guard must be scoped to val — selection on TRAIN stays free');
  });
});

test('VAL budget refuses a family it cannot account for', async (t) => {
  const val = require('../utils/val-budget');

  await t.test('a typo in --family does not grant a fresh budget', () => {
    // The rule is per-family accounting. A name with no page reads as "never validated" and was
    // waved through, spending a VAL charged to a family nobody will look at while the real one
    // kept its budget. An unaccountable family is not a lesser problem than a second run.
    assert.strictEqual(val.check('没有这个家族').reason, 'unknown-family');
    assert.match(val.check('没有这个家族').why, /VAL-BLOCKED/);
  });

  await t.test('a registered family is still evaluated normally', () => {
    assert.notStrictEqual(val.check('家族A').reason, 'unknown-family');
  });
});
