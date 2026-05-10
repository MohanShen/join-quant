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