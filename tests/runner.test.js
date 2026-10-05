/**
 * backtest/runner.test.js
 * Tests for the BacktestRunner module.
 */

const { describe, it } = require('node:test');
const assert = require('node:assert');

describe('BacktestRunner', () => {
  it('should be constructable with options', () => {
    const { BacktestRunner } = require('../backtest/runner');
    
    const runner = new BacktestRunner({
      pollIntervalMs: 5000,
      maxPollAttempts: 10
    });
    
    assert.ok(runner);
    assert.strictEqual(runner.pollIntervalMs, 5000);
    assert.strictEqual(runner.maxPollAttempts, 10);
  });

  it('should use default values when not provided', () => {
    const { BacktestRunner } = require('../backtest/runner');
    
    const runner = new BacktestRunner();
    
    assert.strictEqual(runner.pollIntervalMs, 10000);
    assert.strictEqual(runner.maxPollAttempts, 120);
  });

  it('should accept loginManager as option', () => {
    const { BacktestRunner } = require('../backtest/runner');
    const { LoginManager } = require('../utils/login');
    
    const lm = new LoginManager('/tmp/test-cookies.json');
    const runner = new BacktestRunner({ loginManager: lm });
    
    assert.strictEqual(runner.loginManager, lm);
  });

  it('should require postId and backtestId for run()', async () => {
    const { BacktestRunner } = require('../backtest/runner');
    
    const runner = new BacktestRunner();
    
    await assert.rejects(
      () => runner.run({}),
      /postId and backtestId are required/
    );

    await assert.rejects(
      () => runner.run({ postId: 'abc' }),
      /postId and backtestId are required/
    );
  });

  it('should have pollResults method', () => {
    const { BacktestRunner } = require('../backtest/runner');
    const runner = new BacktestRunner();
    assert.strictEqual(typeof runner.pollResults, 'function');
  });
});

describe('BacktestRunner._parseResults', () => {
  it('should parse all fields from API response', () => {
    const { BacktestRunner } = require('../backtest/runner');
    
    const runner = new BacktestRunner();
    
    const rawData = {
      annual_algo_return: 1.878,
      algorithm_return: 213.27,
      benchmark_return: 45.5,
      max_drawdown: 0.2357,
      algorithm_volatility: 0.32,
      benchmark_volatility: 0.25,
      sharpe: 6.3,
      sortino: 4.2,
      information: 2.1,
      alpha: 0.15,
      beta: 0.8,
      trading_days: 1269,
      win_ratio: 0.6427,
      day_win_ratio: 0.55,
      profit_loss_ratio: 1.8,
      win_count: 812,
      lose_count: 457
    };
    
    const parsed = runner._parseResults(rawData);
    
    assert.strictEqual(parsed.annualReturn, 1.878);
    assert.strictEqual(parsed.cumulativeReturn, 213.27);
    assert.strictEqual(parsed.benchmarkReturn, 45.5);
    assert.strictEqual(parsed.maxDrawdown, 0.2357);
    assert.strictEqual(parsed.volatility, 0.32);
    assert.strictEqual(parsed.benchmarkVolatility, 0.25);
    assert.strictEqual(parsed.sharpe, 6.3);
    assert.strictEqual(parsed.sortino, 4.2);
    assert.strictEqual(parsed.information, 2.1);
    assert.strictEqual(parsed.alpha, 0.15);
    assert.strictEqual(parsed.beta, 0.8);
    assert.strictEqual(parsed.tradingDays, 1269);
    assert.strictEqual(parsed.winRatio, 0.6427);
    assert.strictEqual(parsed.dayWinRatio, 0.55);
    assert.strictEqual(parsed.profitLossRatio, 1.8);
    assert.strictEqual(parsed.winCount, 812);
    assert.strictEqual(parsed.loseCount, 457);
  });

  it('should handle missing fields gracefully', () => {
    const { BacktestRunner } = require('../backtest/runner');
    
    const runner = new BacktestRunner();
    const parsed = runner._parseResults({});
    
    assert.strictEqual(parsed.annualReturn, 0);
    assert.strictEqual(parsed.sharpe, 0);
    assert.strictEqual(parsed.tradingDays, 0);
    assert.strictEqual(parsed.winRatio, 0);
  });

  it('should parse decimal percentages correctly', () => {
    const { BacktestRunner } = require('../backtest/runner');
    
    const runner = new BacktestRunner();
    
    const rawData = {
      annual_algo_return: 0.5,     // 50%
      max_drawdown: 0.25,           // 25%
      win_ratio: 0.6                // 60%
    };
    
    const parsed = runner._parseResults(rawData);
    
    assert.strictEqual(parsed.annualReturn, 0.5);
    assert.strictEqual(parsed.maxDrawdown, 0.25);
    assert.strictEqual(parsed.winRatio, 0.6);
  });
});
/**
 * Concurrency gate.
 *
 * `pollUntilComplete` decides a run is finished by watching the account's GLOBAL running count
 * go 0 -> >=1 -> 0. That is a valid signal only while exactly one backtest exists on the
 * account. Measured 2026-09-20: two enhance engineers ran against one CDP Chrome and returned
 * BYTE-IDENTICAL metrics for different strategies. The window check cannot catch it — both
 * requested `--window train` — so two experiments entered the record as one measurement.
 *
 * A refusal is visible; a mis-attributed result is not. Hence: refuse to start.
 */
const test2 = require('node:test');
const assert2 = require('node:assert');
const fs2 = require('fs');
const path2 = require('path');

test2('backtest runner refuses to start alongside another run', async t => {
  const src = fs2.readFileSync(path2.join(__dirname, '../utils/strategy-post-backtest.js'), 'utf8');

  await t.test('the gate exists and reads the account-wide running list', () => {
    assert2.match(src, /async function concurrencyGate\(page\)/);
    assert2.match(src, /concurrencyGate[\s\S]{0,700}data\.running/,
      'the gate must read running[] from the statistics API');
  });

  await t.test('it guards BOTH entry paths, not just the one that broke', () => {
    const calls = src.match(/await concurrencyGate\(/g) || [];
    assert2.strictEqual(calls.length, 2,
      `expected the gate on both backtest entry paths, found ${calls.length}`);
  });

  await t.test('it refuses rather than warning, and says so machine-readably', () => {
    assert2.match(src, /CONCURRENT-STOP\\trunning=/,
      'a batch runner needs a parseable marker, like USAGE-STOP');
    assert2.match(src, /status: 'concurrent-stop'/,
      'the refusal must reach the caller as a distinct status, not as a generic failure');
  });

  await t.test('the override is explicit, opt-in, and warns when used', () => {
    assert2.match(src, /JQ_ALLOW_CONCURRENT === '1'/);
    assert2.match(src, /MIS-ATTRIBUTED/,
      'running with the override on must say what it is risking');
  });

  await t.test('an unreadable running[] does not silently block every run', () => {
    // Failing closed here would make a transient API hiccup look like a permanent refusal,
    // and this gate sits in front of the daily budget. Proceed, but say the signal is unverified.
    assert2.match(src, /could not read running\[\] — proceeding/);
  });
});

/**
 * Completion is measured against a BASELINE, not against zero.
 *
 * The gate filtered unreapable `running[]` entries out by age; `pollUntilComplete` counted them
 * (`running.length`, no filter). That asymmetry meant a lingering entry let a run START and never
 * let it COMPLETE: `seenRunning` latched true on the first poll, `emptyStreak` could never
 * accumulate, and the run spun to MAX_POLL_MS and was recorded as a slow-skip — which left
 * another unreapable entry behind it. Self-reinforcing, and invisible: a slow-skip looks like a
 * slow strategy.
 */
const blt = require('node:test');
const bla = require('node:assert');
const blfs = require('fs');
const blpath = require('path');

blt('completion is relative to a baseline, not to zero', async (t) => {
  const src = blfs.readFileSync(blpath.join(__dirname, '../utils/strategy-post-backtest.js'), 'utf8');

  await t.test('the detector compares against the baseline', () => {
    bla.match(src, /async function pollUntilComplete\(page, algorithmId, \{ baseline = 0 \} = \{\}\)/,
      'it must accept a baseline');
    bla.match(src, /st\.runningCount > baseline/,
      'the 0 -> >=1 -> 0 edge must be read against the baseline');
    bla.doesNotMatch(src, /if \(st\.runningCount > 0\) \{ seenRunning = true/,
      'comparing against 0 is the bug — a lingering entry never lets the count reach it');
  });

  await t.test('the baseline counts EVERY entry, not the filtered live ones', () => {
    // This is the whole fix. A baseline of the age-filtered count would reproduce the original
    // asymmetry exactly, because the detector reads the unfiltered length.
    bla.match(src, /baseline: rows\.length/,
      'the baseline must be what the detector will actually see');
  });

  await t.test('a non-zero baseline demands positive evidence of OUR result', () => {
    // At baseline 0, the count returning to 0 is conclusive. With a tolerated entry present it is
    // not: that entry dropping off reads identically. The rendered panel belongs to an
    // algorithmId created this run, so it can only be ours.
    // The decision now lives in the pure `completionStep`, which is driven directly by the
    // state-machine tests below — a stronger check than matching this string ever was.
    bla.match(src, /const evidence = baseline === 0 \|\| rendered;/,
      'absence of a count is not evidence of completion when something else is listed');
    bla.match(src, /function completionStep\(st, \{ runningCount, baseline, rendered \}\)/,
      'the decision must stay a pure function so it can be tested without a browser');
  });

  await t.test('only LIVE contention refuses the run', () => {
    bla.match(src, /young\.length > 0 && !ALLOW_CONCURRENT/,
      'a past-cap entry is ours and dead — refusing on it created a 75-minute dead zone');
    bla.match(src, /age > CONCURRENT_STALE_MIN \? stale : age > capMin \? dead : young/,
      'the split must be three-way: live / dead / stale');
  });

  await t.test('both call sites carry the baseline through', () => {
    const calls = src.match(/pollUntilComplete\([^)]*baseline:/g) || [];
    bla.strictEqual(calls.length, 2,
      `both dispatch paths must pass the baseline, found ${calls.length}`);
  });

  await t.test('the refusal still emits the marker the batch runner reads', () => {
    // Narrowing what we refuse on must not change HOW we refuse — the normalizer keys on this.
    bla.match(src, /CONCURRENT-STOP\\trunning=\$\{young\.length\}/);
  });
});

/**
 * The completion state machine, driven directly.
 *
 * These are the cases that cost real days. Driving the pure function is the only way to test
 * them: the condition they describe — an unreapable `running[]` entry — appears and vanishes on
 * JQ's schedule, so a live run that completes may just have had a baseline of 0.
 */
const cst2 = require('node:test');
const csa2 = require('node:assert');
const { completionStep } = require('../utils/strategy-post-backtest');

cst2('the completion state machine', async (t) => {
  const S0 = { seenRunning: false, emptyStreak: 0, renderedStreak: 0 };
  // Drive a sequence of (runningCount, rendered) observations; return the final state.
  const run = (baseline, obs) => {
    let st = { ...S0 };
    for (const [runningCount, rendered] of obs) {
      st = completionStep(st, { runningCount, baseline, rendered });
      if (st.finished) break;
    }
    return st;
  };

  await t.test('baseline 0: the classic 0 -> 1 -> 0 edge finishes', () => {
    // The old path, unchanged. Two empty polls confirm it.
    const st = run(0, [[1, false], [1, false], [0, false], [0, false]]);
    csa2.strictEqual(st.finished, true);
  });

  await t.test('baseline 1: a run completes with an unreapable entry present', () => {
    // THE case that was 100% broken. Count 1 -> 2 -> 1, panel rendered.
    const st = run(1, [[2, false], [2, false], [1, true], [1, true]]);
    csa2.strictEqual(st.finished, true, 'a run must be able to finish alongside a dead entry');
  });

  await t.test('baseline 1: the old logic would never have finished', () => {
    // Proof the bug was real rather than theoretical: against a baseline of 0, the same
    // observations never reach an empty poll, so emptyStreak can never accumulate.
    const st = run(0, [[2, false], [2, false], [1, true], [1, true]]);
    csa2.strictEqual(st.finished, false,
      'comparing to 0 cannot terminate while an entry lingers — it spins to the cap');
  });

  await t.test('baseline 1: the dead entry dropping off is NOT completion', () => {
    // Count 2 -> 1 looks identical to our run finishing, but the panel has not rendered. Calling
    // this done would scrape an empty panel and lose the run.
    const st = run(1, [[2, false], [1, false], [1, false], [1, false]]);
    csa2.strictEqual(st.finished, false, 'absence of a count is not evidence of our result');
    csa2.strictEqual(st.emptyStreak, 0, 'and the streak must reset, not creep up');
  });

  await t.test('a single blip does not finish a run', () => {
    // Two consecutive confirmations are required, at either baseline.
    csa2.strictEqual(run(0, [[1, false], [0, false], [1, false]]).finished, false);
    csa2.strictEqual(run(1, [[2, false], [1, true], [2, false]]).finished, false);
  });

  await t.test('a run finishing inside the settle wait is still detected', () => {
    // Never observed above baseline; the rendered panel is the only signal there is.
    csa2.strictEqual(run(1, [[1, true], [1, true]]).finished, true);
    csa2.strictEqual(run(0, [[0, true], [0, true]]).finished, true);
  });

  await t.test('it is pure — the caller\'s state object is not mutated', () => {
    const st = { ...S0 };
    completionStep(st, { runningCount: 5, baseline: 0, rendered: true });
    csa2.deepStrictEqual(st, S0, 'the loop reassigns from the return value; mutation would alias');
  });
});

/**
 * Cancelling the right run, and knowing whether it worked.
 *
 * Both measured on 2026-10-05 by killing a stage mid-backtest:
 *  - `#backtestId` is present but EMPTY on the page the executor holds, so the count rule was
 *    the only selector, and `length === 1` is false exactly when a cancel matters most.
 *  - `status:"0"` was returned for a cancel that did not happen: the run stayed listed 7 more
 *    minutes, and from its own editor page the API said 在此状态不能取消. The executor logged
 *    "⏹ cancelled" on the strength of that code.
 */
const ckt = require('node:test');
const cka = require('node:assert');
const { pickOurRun } = require('../utils/strategy-post-backtest');
const ckfs = require('fs');
const ckpath = require('path');

ckt('cancel targets our run and confirms it stopped', async (t) => {
  const row = (usedSec, time) => ({ id: 'x'.repeat(32), usedSec, time });

  await t.test('a run sitting AT the cap is still selected', () => {
    // The main code path: we cancel because it reached the cap, so a strict `<= cap` would
    // have excluded it and cancelled nothing.
    cka.ok(pickOurRun([row('45分02秒', 't1')], 45), 'the run at the cap is the one being cancelled');
    cka.ok(pickOurRun([row('30分00秒', 't1')], 30));
  });

  await t.test('a zombie past the cap is never selected', () => {
    cka.strictEqual(pickOurRun([row('701分34秒', 'z')], 45), null,
      'cancelling a zombie is what returns status:0 and does nothing');
    cka.strictEqual(pickOurRun([], 45), null);
  });

  await t.test('with a zombie present it picks OURS, where length===1 gave up', () => {
    const picked = pickOurRun([row('701分34秒', 'zombie'), row('02分10秒', 'ours')], 45);
    cka.strictEqual(picked && picked.time, 'ours');
  });

  await t.test('among several candidates it takes the youngest', () => {
    const picked = pickOurRun([row('40分00秒', 'older'), row('01分00秒', 'newest')], 45);
    cka.strictEqual(picked && picked.time, 'newest');
  });

  await t.test('success is verified against running[], not the status code', () => {
    const src = ckfs.readFileSync(ckpath.join(__dirname, '../utils/strategy-post-backtest.js'), 'utf8');
    const fn = src.slice(src.indexOf('async function cancelBacktest'), src.indexOf('// Detect a compile/runtime error'));
    cka.match(fn, /gone = !now\.some\(x => x\.time === target\.time\)/,
      'verification must match on start time — ids are re-minted per request');
    cka.match(fn, /confirmed gone/, 'only a confirmed stop may report success');
    cka.match(fn, /ZOMBIE entry/, 'an accepted-but-not-stopped cancel must say so');
    // The old unconditional claim on status:0 is the bug.
    cka.doesNotMatch(fn, /if \(r\.ok\) \{ console\.log\(`\\n\[post\] ⏹ cancelled/,
      'reporting a cancel on the status code alone is what hid these');
    cka.doesNotMatch(fn, /run\.length === 1 \? run\[0\]\.id : null/, 'the count selector is gone');
  });
});
