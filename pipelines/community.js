/**
 * pipelines/community.js
 * 
 * Automated pipeline for fetching a strategy from a JoinQuant community post
 * and running a backtest.
 * 
 * Usage:
 *   const { CommunityPipeline } = require('./pipelines/community');
 *   const pipeline = new CommunityPipeline({ loginManager });
 *   const result = await pipeline.run({ postId, backtestId });
 */

const { StrategyFetcher } = require('../utils/fetcher');
const { BacktestRunner } = require('../backtest/runner');

class CommunityPipeline {
  /**
   * @param {object} options
   * @param {LoginManager} options.loginManager - Auth handler
   * @param {object} options.fetcherOptions - Options passed to StrategyFetcher
   * @param {object} options.runnerOptions - Options passed to BacktestRunner
   */
  constructor(options = {}) {
    this.loginManager = options.loginManager;
    this.fetcher = new StrategyFetcher({
      loginManager: this.loginManager,
      ...options.fetcherOptions
    });
    this.runner = new BacktestRunner({
      loginManager: this.loginManager,
      ...options.runnerOptions
    });
  }

  /**
   * Run the full community → fetch → backtest pipeline.
   * 
   * @param {object} params
   * @param {string} params.postId - Community post ID (e.g. "5aa05159e33a10f96fd215cfeb59137c")
   * @param {string} params.backtestId - Source strategy backtest ID
   * @param {string} [params.replyId] - Reply ID if applicable
   * @param {boolean} [params.skipFetch] - Skip fetching source, just run backtest (default: false)
   * @returns {Promise<object>} Full pipeline result
   */
  async run(params) {
    const { postId, backtestId, replyId = '', skipFetch = false } = params;

    const startTime = Date.now();
    const pipelineId = `pipeline_${postId}_${Date.now()}`;

    console.log(`[community:${pipelineId}] Starting pipeline`);
    console.log(`[community:${pipelineId}] postId=${postId}, backtestId=${backtestId}`);

    let sourceCode = null;
    let backtestResult = null;

    try {
      // Step 1: Fetch strategy source (optional - can skip if source already known)
      if (!skipFetch) {
        console.log(`[community:${pipelineId}] Fetching strategy source...`);
        sourceCode = await this.fetcher.fetch({ postId, backtestId, replyId });
        
        if (sourceCode) {
          console.log(`[community:${pipelineId}] Source fetched (${sourceCode.length} chars)`);
        } else {
          console.warn(`[community:${pipelineId}] Could not fetch source, proceeding with backtest anyway`);
        }
      }

      // Step 2: Run backtest (clone strategy → poll → get results)
      console.log(`[community:${pipelineId}] Starting backtest...`);
      backtestResult = await this.runner.run({ postId, backtestId, replyId });
      
      console.log(`[community:${pipelineId}] Backtest completed: backtestId=${backtestResult.backtestId}`);

      return {
        pipelineId,
        postId,
        sourceBacktestId: backtestId,
        newBacktestId: backtestResult.backtestId,
        status: backtestResult.status,
        sourceCodeFetched: !!sourceCode,
        sourceCodeLength: sourceCode?.length || null,
        results: backtestResult.results,
        durationMs: Date.now() - startTime
      };

    } catch (error) {
      console.error(`[community:${pipelineId}] Pipeline failed: ${error.message}`);
      
      return {
        pipelineId,
        postId,
        sourceBacktestId: backtestId,
        status: 'failed',
        error: error.message,
        sourceCodeFetched: !!sourceCode,
        sourceCodeLength: sourceCode?.length || null,
        results: backtestResult?.results || null,
        durationMs: Date.now() - startTime
      };
    }
  }
}

module.exports = { CommunityPipeline };