/**
 * pipelines/custom.js
 * 
 * Pipeline for running a custom local strategy on JoinQuant.
 * 
 * Flow:
 * 1. Load strategy from local file
 * 2. (Future) Upload to JoinQuant and configure params
 * 3. Run backtest
 * 4. Return results
 * 
 * Note: Currently the "deploy custom strategy" step requires manual upload
 * since JoinQuant doesn't expose an API for code upload. This pipeline
 * handles the backtest execution for strategies that already exist on
 * the platform.
 * 
 * Usage:
 *   const { CustomPipeline } = require('./pipelines/custom');
 *   const pipeline = new CustomPipeline({ loginManager });
 *   const result = await pipeline.runFromFile('./strategies/my-strategy.py');
 *   const result2 = await pipeline.runFromBacktestId('existing-backtest-id-123');
 */

const { StrategyLoader } = require('../utils/loader');
const { BacktestRunner } = require('../backtest/runner');

class CustomPipeline {
  /**
   * @param {object} options
   * @param {LoginManager} options.loginManager - Auth handler
   * @param {object} options.loaderOptions - Options passed to StrategyLoader
   * @param {object} options.runnerOptions - Options passed to BacktestRunner
   */
  constructor(options = {}) {
    this.loginManager = options.loginManager;
    this.loader = new StrategyLoader(options.loaderOptions);
    this.runner = new BacktestRunner({
      loginManager: this.loginManager,
      ...options.runnerOptions
    });
  }

  /**
   * Run backtest for a local strategy file.
   * 
   * This first uploads the strategy to JoinQuant (if supported) or
   * creates a new backtest configuration with the strategy code.
   * 
   * For now, this requires the strategy to already exist on JoinQuant.
   * Pass the existing backtestId to runBacktestFromBacktestId().
   * 
   * @param {string} filePath - Path to strategy file
   * @param {object} params - Backtest params
   * @returns {Promise<object>} Pipeline result
   */
  async runFromFile(filePath, params = {}) {
    const startTime = Date.now();
    const pipelineId = `custom_${Date.now()}`;

    console.log(`[custom:${pipelineId}] Loading strategy from ${filePath}`);
    
    let strategy;
    try {
      strategy = await this.loader.load(filePath);
      console.log(`[custom:${pipelineId}] Strategy loaded: ${strategy.name} (${strategy.sourceCode.length} chars)`);
    } catch (error) {
      return {
        pipelineId,
        status: 'failed',
        error: `Failed to load strategy: ${error.message}`,
        durationMs: Date.now() - startTime
      };
    }

    // For now, we need an existing backtestId on JoinQuant to run against
    // The custom strategy upload API is not yet supported
    if (!params.backtestId) {
      return {
        pipelineId,
        status: 'failed',
        error: 'backtestId is required for custom strategies. Custom code upload not yet supported - provide an existing backtestId on JoinQuant.',
        strategyName: strategy.name,
        durationMs: Date.now() - startTime
      };
    }

    // Run the backtest
    return await this._runBacktest(pipelineId, {
      postId: params.postId || 'custom',
      backtestId: params.backtestId,
      replyId: params.replyId || '',
      strategy,
      startTime
    });
  }

  /**
   * Run backtest for an existing backtestId (already deployed on JoinQuant).
   * 
   * @param {string} backtestId - Existing backtest ID
   * @param {string} [postId] - Associated post ID (default: "custom")
   * @returns {Promise<object>} Pipeline result
   */
  async runFromBacktestId(backtestId, postId = 'custom') {
    const startTime = Date.now();
    const pipelineId = `custom_${Date.now()}`;

    return await this._runBacktest(pipelineId, {
      postId,
      backtestId,
      replyId: '',
      strategy: null,
      startTime
    });
  }

  /**
   * Internal: run backtest and format result.
   * @private
   */
  async _runBacktest(pipelineId, params) {
    const { postId, backtestId, replyId, strategy, startTime } = params;

    console.log(`[custom:${pipelineId}] Starting backtest: postId=${postId}, backtestId=${backtestId}`);

    try {
      const backtestResult = await this.runner.run({ postId, backtestId, replyId });

      return {
        pipelineId,
        strategyName: strategy?.name || 'existing',
        newBacktestId: backtestResult.backtestId,
        status: backtestResult.status,
        results: backtestResult.results,
        sourceCodeLength: strategy?.sourceCode?.length || null,
        durationMs: Date.now() - startTime
      };

    } catch (error) {
      console.error(`[custom:${pipelineId}] Backtest failed: ${error.message}`);

      return {
        pipelineId,
        strategyName: strategy?.name || 'unknown',
        status: 'failed',
        error: error.message,
        sourceCodeLength: strategy?.sourceCode?.length || null,
        durationMs: Date.now() - startTime
      };
    }
  }

  /**
   * List all local strategies.
   * @returns {Array} List of strategy info objects
   */
  listStrategies() {
    return this.loader.list();
  }
}

module.exports = { CustomPipeline };