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
