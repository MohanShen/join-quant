/**
 * The OOS reserve's accounting.
 *
 * ⚠⚠ Why this file exists. `oosPolicy: { maxTestsPerCandidate: 1, maxTestsPerEpoch: 2 }` was
 * declared in epoch 3 and enforced NOWHERE until 2026-10-16. It appeared in harness-config's
 * console output and in one test asserting the per-epoch figure had gone down, and that was all.
 * `assertNotOOS` guards the WINDOW — nothing may reach past the cutoff without JQ_ALLOW_OOS=1 —
 * but once that flag was set, nothing counted the tests. The repo's least recoverable surface was
 * the only one with no budget, while VAL had val-budget.js watching it.
 */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'oos-'));
process.env.JQ_CONSUMPTION_FILE = path.join(dir, 'consumption.tsv');

const oos = require('../utils/oos-budget');
const consumption = require('../utils/consumption');
const harness = require('../utils/harness-config');

const HEADER = 'key\tkind\tstage\trunId\tat\toutcome\tnote\tmembers\tmemberHash\tepoch';
const reset = () => fs.writeFileSync(process.env.JQ_CONSUMPTION_FILE, HEADER + '\n');
/** Append a raw row so a test can control the epoch, which record() stamps on purpose. */
const raw = (key, runId, outcome, epoch, stage = 'oos') =>
  fs.appendFileSync(process.env.JQ_CONSUMPTION_FILE,
    [key, 'candidate', stage, runId, '2026-10-01T00:00:00Z', outcome, '', '', '', epoch].join('\t') + '\n');

test('OOS budget', async (t) => {
  const perEpoch = oos.policy().maxTestsPerEpoch;

  await t.test('an untested candidate on a fresh bench is allowed', () => {
    reset();
    const r = oos.check('cand-A');
    assert.strictEqual(r.allowed, true);
    assert.strictEqual(r.reason, 'first-of-bench');
    assert.strictEqual(r.used, 0);
    assert.strictEqual(r.remaining, perEpoch);
  });

  await t.test('a candidate with no id is refused — an uncharged test is spent twice', () => {
    reset();
    const r = oos.check(null);
    assert.strictEqual(r.allowed, false);
    assert.strictEqual(r.reason, 'no-candidate');
  });

  await t.test('the per-CANDIDATE limit is absolute, across every epoch', () => {
    // Not per epoch. Re-testing one book on the reserve after a bench change is still selection
    // on OOS, one look at a time, and no later discipline un-sees it.
    reset();
    const stale = [1, 2, 3, 4, 5].find(e => !harness.measurementValid(e));
    raw('cand-A', 'r-old', 'oos-sharpe 1.9', String(stale != null ? stale : 2));
    const r = oos.check('cand-A');
    assert.strictEqual(r.allowed, false);
    assert.strictEqual(r.reason, 'candidate-already-tested');
    assert.match(r.why, /r-old/, 'the refusal must name what spent it');
    // …while the bench's own budget is untouched by that older-epoch test.
    assert.strictEqual(oos.check('cand-B').allowed, true);
  });

  await t.test('the per-bench budget blocks a NEW candidate once it is spent', () => {
    reset();
    const ep = String(harness.config().epoch);
    for (let i = 0; i < perEpoch; i++) raw(`spent-${i}`, `r${i}`, 'oos-completed', ep);
    const r = oos.check('fresh-candidate');
    assert.strictEqual(r.allowed, false);
    assert.strictEqual(r.reason, 'bench-budget-spent');
    assert.strictEqual(r.remaining, 0);
  });

  await t.test('a SCORING-ONLY bump does NOT restore the reserve', () => {
    // The lesson from the VAL budget, applied before it could bite here: keying on the epoch
    // NUMBER meant epochs 7 and 8 each read as a fresh slate. A scoring-only bump hands back no
    // 2026 data, so it cannot hand back tests either.
    reset();
    const active = harness.config().epoch;
    const earlier = [...harness.comparableEpochs()].filter(e => e < active).sort((a, b) => b - a)[0];
    if (earlier == null) return;
    for (let i = 0; i < perEpoch; i++) raw(`spent-${i}`, `r${i}`, 'oos-completed', String(earlier));
    const r = oos.check('fresh-candidate');
    assert.strictEqual(r.allowed, false,
      `tests charged to epoch ${earlier} must still count at epoch ${active} — same bench`);
    assert.strictEqual(r.reason, 'bench-budget-spent');
    assert.match(r.why, /SCORING-ONLY/);
  });

  await t.test('a bump that DID change the measurement does restore it', () => {
    reset();
    const stale = [1, 2, 3, 4, 5].find(e => !harness.measurementValid(e));
    if (stale == null) return;
    for (let i = 0; i < perEpoch; i++) raw(`spent-${i}`, `r${i}`, 'oos-completed', String(stale));
    assert.strictEqual(oos.check('fresh-candidate').allowed, true,
      `epoch-${stale} tests were charged to a bench that no longer exists`);
  });

  await t.test('an UNSTAMPED row counts — unknown blocks, it does not permit', () => {
    reset();
    for (let i = 0; i < perEpoch; i++) raw(`spent-${i}`, `r${i}`, 'oos-completed', '');
    const r = oos.check('fresh-candidate');
    assert.strictEqual(r.allowed, false,
      'a row that cannot be shown to belong to an older bench must count against this one');
  });

  await t.test('a test MIS-FILED under another stage still counts', () => {
    // The exact mis-filing that hid a VAL from val-budget for weeks (etfmom-005 under stage
    // `enhance`). The same accident must not hide an OOS test.
    reset();
    const ep = String(harness.config().epoch);
    for (let i = 0; i < perEpoch; i++) raw(`spent-${i}`, `r${i}`, 'oos-completed', ep, 'enhance');
    assert.strictEqual(oos.check('fresh-candidate').allowed, false);
    assert.strictEqual(oos.check('fresh-candidate').reason, 'bench-budget-spent');
  });

  await t.test('record() stamps the epoch itself and refuses to double-count', () => {
    reset();
    assert.strictEqual(oos.record('cand-X', 'run-1', { outcome: 'sharpe 1.2' }), true);
    // A caller that could choose its own epoch could make a spent test look older and free up
    // the reserve — so record() takes the live epoch and nothing else.
    const row = oos.priorTests().find(e => e.key === 'cand-X');
    assert.strictEqual(String(row.epoch), String(harness.config().epoch));
    assert.match(row.outcome, /^oos-/, 'the outcome shape is what makes a mis-filed row findable');
    assert.strictEqual(oos.record('cand-X', 'run-1', {}), false, 'a retry must not double-count');
    assert.strictEqual(oos.check('cand-X').allowed, false);
  });

  await t.test('record() demands a runId — an unidentifiable test cannot be audited', () => {
    reset();
    assert.throws(() => oos.record('cand-Y', null, {}), /runId/);
    assert.throws(() => oos.record(null, 'run-1', {}), /candidateId/);
  });

  await t.test('the override is a SEPARATE switch from the window flag', () => {
    reset();
    const ep = String(harness.config().epoch);
    for (let i = 0; i < perEpoch; i++) raw(`spent-${i}`, `r${i}`, 'oos-completed', ep);
    // JQ_ALLOW_OOS unlocks the WINDOW; it must not also unlock the BUDGET, or a legitimate
    // first test would silently authorize an unlimited number of them.
    const prevW = process.env.JQ_ALLOW_OOS;
    process.env.JQ_ALLOW_OOS = '1';
    try {
      assert.strictEqual(oos.check('fresh').allowed, false,
        'the window flag must not grant budget');
    } finally {
      if (prevW === undefined) delete process.env.JQ_ALLOW_OOS; else process.env.JQ_ALLOW_OOS = prevW;
    }
    const prevB = process.env.JQ_ALLOW_OOS_OVERBUDGET;
    process.env.JQ_ALLOW_OOS_OVERBUDGET = '1';
    try {
      const r = oos.check('fresh');
      assert.strictEqual(r.allowed, true);
      assert.strictEqual(r.reason, 'human-override');
    } finally {
      if (prevB === undefined) delete process.env.JQ_ALLOW_OOS_OVERBUDGET;
      else process.env.JQ_ALLOW_OOS_OVERBUDGET = prevB;
    }
  });
});

test('the executor enforces the OOS budget, not just the window', async (t) => {
  const src = fs.readFileSync(path.join(__dirname, '..', 'utils/strategy-post-backtest.js'), 'utf8');

  await t.test('the window test is shared, so the two gates cannot drift apart', () => {
    assert.match(src, /function touchesOOS\(window\)/);
    assert.match(src, /if \(touchesOOS\(window\)\) \{/, 'assertNotOOS must use the shared test');
  });

  await t.test('the budget is checked BEFORE the browser, like VAL', () => {
    const gate = src.indexOf("require('./oos-budget')");
    const loader = src.indexOf('new StrategyLoader()');
    assert.ok(gate > 0 && loader > 0 && gate < loader,
      'an OOS run must be refused before anything costs a minute');
    assert.match(src, /OOS-BUDGET\\t/, 'the decision must be machine-readable on stdout');
  });

  await t.test('a spent test is recorded at every completion path', () => {
    const calls = src.match(/recordOosIfCompleted\(/g) || [];
    // One definition + both completion paths, mirroring recordValIfCompleted.
    assert.ok(calls.length >= 3, `expected the recorder at both completion paths, found ${calls.length}`);
    assert.match(src, /status !== 'completed'/);
    assert.match(src, /FAILED to record the OOS spend/,
      'a bookkeeping failure must shout — the reserve would look less spent than it is');
  });
});
