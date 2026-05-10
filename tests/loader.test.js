/**
 * strategy/loader.test.js
 * Tests for the StrategyLoader module.
 */

const { describe, it, beforeEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const TEST_STRATEGIES_DIR = '/tmp/jq-test-strategies';

beforeEach(() => {
  // Clean up test directory
  if (fs.existsSync(TEST_STRATEGIES_DIR)) {
    fs.rmSync(TEST_STRATEGIES_DIR, { recursive: true });
  }
  fs.mkdirSync(TEST_STRATEGIES_DIR, { recursive: true });
});

describe('StrategyLoader', () => {
  it('should be constructable with baseDir option', () => {
    const { StrategyLoader } = require('../utils/loader');
    const loader = new StrategyLoader({ baseDir: TEST_STRATEGIES_DIR });
    assert.strictEqual(loader.baseDir, TEST_STRATEGIES_DIR);
  });

  it('should use cwd/strategies as default baseDir', () => {
    const { StrategyLoader } = require('../utils/loader');
    const loader = new StrategyLoader();
    assert.ok(loader.baseDir.endsWith('strategies'));
  });

  it('should load a valid Python strategy', async () => {
    const { StrategyLoader } = require('../utils/loader');
    
    // Create test strategy
    const strategyPath = path.join(TEST_STRATEGIES_DIR, 'test-strategy.py');
    fs.writeFileSync(strategyPath, `
# Clone from JoinQuant post/12345
# Author: Test

def initialize(context):
    g.stock = '000001.XSHE'
    run_daily(market_open, time='9:30')

def handle_data(context, data):
    order_target_percent(g.stock, 0.1)
`);

    const loader = new StrategyLoader({ baseDir: TEST_STRATEGIES_DIR });
    const strategy = await loader.load('test-strategy.py');

    assert.strictEqual(strategy.name, 'test-strategy');
    assert.strictEqual(strategy.language, 'python');
    assert.ok(strategy.sourceCode.includes('initialize'));
    assert.ok(strategy.sourceCode.includes('handle_data'));
    assert.strictEqual(strategy.metadata.clonedFrom, 'Clone from JoinQuant post/12345');
  });

  it('should load a JSON config with inline source', async () => {
    const { StrategyLoader } = require('../utils/loader');
    
    const configPath = path.join(TEST_STRATEGIES_DIR, 'config-test.json');
    fs.writeFileSync(configPath, JSON.stringify({
      name: 'My Custom Strategy',
      sourceCode: `
def initialize(context):
    g.stock = '000001.XSHE'

def handle_data(context, data):
    order_target_percent(g.stock, 0.1)
`,
      params: {
        initCash: 200000,
        frequency: 'daily'
      }
    }));

    const loader = new StrategyLoader({ baseDir: TEST_STRATEGIES_DIR });
    const strategy = await loader.load('config-test.json');

    assert.strictEqual(strategy.name, 'My Custom Strategy');
    assert.strictEqual(strategy.params.initCash, 200000);
    assert.strictEqual(strategy.params.frequency, 'daily');
  });

  it('should throw when strategy file not found', async () => {
    const { StrategyLoader } = require('../utils/loader');
    const loader = new StrategyLoader({ baseDir: TEST_STRATEGIES_DIR });

    await assert.rejects(
      () => loader.load('nonexistent.py'),
      /Strategy file not found/
    );
  });

  it('should throw for unsupported file types', async () => {
    const { StrategyLoader } = require('../utils/loader');
    
    const badPath = path.join(TEST_STRATEGIES_DIR, 'strategy.java');
    fs.writeFileSync(badPath, 'public class Strategy {}');

    const loader = new StrategyLoader({ baseDir: TEST_STRATEGIES_DIR });
    
    await assert.rejects(
      () => loader.load('strategy.java'),
      /Unsupported strategy file type/
    );
  });

  it('should warn about missing initialize and handle_data', async () => {
    const { StrategyLoader } = require('../utils/loader');
    
    const strategyPath = path.join(TEST_STRATEGIES_DIR, 'incomplete.py');
    fs.writeFileSync(strategyPath, `
def initialize(context):
    pass
`);

    const loader = new StrategyLoader({ baseDir: TEST_STRATEGIES_DIR });
    // Should not throw, just warn
    const strategy = await loader.load('incomplete.py');
    assert.ok(strategy);
  });

  it('should list all strategies in baseDir', () => {
    const { StrategyLoader } = require('../utils/loader');
    
    // Create test files
    fs.writeFileSync(path.join(TEST_STRATEGIES_DIR, 'strategy1.py'), '# strategy 1');
    fs.writeFileSync(path.join(TEST_STRATEGIES_DIR, 'strategy2.py'), '# strategy 2');
    fs.writeFileSync(path.join(TEST_STRATEGIES_DIR, 'config.json'), '{"sourceCode": ""}');

    const loader = new StrategyLoader({ baseDir: TEST_STRATEGIES_DIR });
    const strategies = loader.list();

    assert.strictEqual(strategies.length, 3);
    assert.ok(strategies.find(s => s.name === 'strategy1'));
    assert.ok(strategies.find(s => s.name === 'strategy2'));
    assert.ok(strategies.find(s => s.name === 'config'));
  });

  it('should return empty array when dir empty', () => {
    const { StrategyLoader } = require('../utils/loader');
    const loader = new StrategyLoader({ baseDir: TEST_STRATEGIES_DIR });
    
    const strategies = loader.list();
    assert.strictEqual(strategies.length, 0);
  });

  it('should extract clone metadata from comments', async () => {
    const { StrategyLoader } = require('../utils/loader');
    
    const strategyPath = path.join(TEST_STRATEGIES_DIR, 'cloned.py');
    fs.writeFileSync(strategyPath, `
# Clone from JoinQuant post/55002
# backtestId: 92a25fb27fd006b1f6b995dcc9533a83

def initialize(context):
    pass
`);

    const loader = new StrategyLoader({ baseDir: TEST_STRATEGIES_DIR });
    const strategy = await loader.load('cloned.py');

    assert.strictEqual(
      strategy.metadata.clonedFrom,
      'Clone from JoinQuant post/55002'
    );
  });
});

describe('StrategyLoader._extractMetadata', () => {
  it('should parse requirements comment', async () => {
    const { StrategyLoader } = require('../utils/loader');
    
    const strategyPath = path.join(TEST_STRATEGIES_DIR, 'req-test.py');
    fs.writeFileSync(strategyPath, `
# Clone from post/123
# requirements:
#   pandas
#   numpy
#   talib

def initialize(context):
    pass
`);

    const loader = new StrategyLoader({ baseDir: TEST_STRATEGIES_DIR });
    const strategy = await loader.load('req-test.py');

    assert.deepStrictEqual(strategy.metadata.packages, ['pandas', 'numpy', 'talib']);
  });
});