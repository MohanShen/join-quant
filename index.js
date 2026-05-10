#!/usr/bin/env node

/**
 * joinquant-pipeline - CLI entry point
 * 
 * Usage:
 *   node index.js community <postId> <backtestId>   Run community post backtest
 *   node index.js custom <filePath>               Run custom strategy backtest
 *   node index.js custom --backtestId <id>       Run existing backtestId
 *   node index.js login                           Test login
 *   node index.js status                          Show cookie status
 */

const path = require('path');

// Load environment variables from .env if present
const envPath = path.join(__dirname, '.env');
if (require('fs').existsSync(envPath)) {
  require('fs').readFileSync(envPath, 'utf8')
    .split('\n')
    .filter(line => line.trim() && !line.startsWith('#'))
    .forEach(line => {
      const [key, value] = line.split('=').map(s => s.trim());
      if (key && !process.env[key]) {
        process.env[key] = value;
      }
    });
}

const { LoginManager } = require('./auth/login');
const { CommunityPipeline } = require('./pipelines/community');
const { CustomPipeline } = require('./pipelines/custom');

// Default cookie storage path
const DEFAULT_COOKIE_PATH = path.join(__dirname, 'auth', 'cookies.json');

// CLI argument parsing
const args = process.argv.slice(2);
const command = args[0] || 'help';

async function main() {
  // Create shared login manager
  const loginManager = new LoginManager(DEFAULT_COOKIE_PATH, {
    username: process.env.JOINQUANT_USERNAME,
    password: process.env.JOINQUANT_PASSWORD
  });

  switch (command) {
    case 'community': {
      // node index.js community <postId> <backtestId> [replyId]
      const [postId, backtestId, replyId] = args.slice(1);
      
      if (!postId || !backtestId) {
        console.error('Usage: node index.js community <postId> <backtestId> [replyId]');
        process.exit(1);
      }

      console.log('========================================');
      console.log('  JoinQuant Community Pipeline');
      console.log('========================================');
      console.log(`  Post ID:    ${postId}`);
      console.log(`  Backtest:   ${backtestId}`);
      console.log(`  Reply ID:   ${replyId || '(none)'}`);
      console.log('========================================\n');

      const pipeline = new CommunityPipeline({ loginManager });
      
      console.log('[CLI] Ensuring login...');
      await loginManager.ensureLogin();
      console.log('[CLI] Login ready\n');

      console.log('[CLI] Starting backtest...');
      const result = await pipeline.run({ postId, backtestId, replyId: replyId || '' });

      console.log('\n========================================');
      console.log('  Pipeline Result');
      console.log('========================================');
      console.log(`  Status:     ${result.status}`);
      console.log(`  Pipeline:   ${result.pipelineId}`);
      
      if (result.newBacktestId) {
        console.log(`  New ID:     ${result.newBacktestId}`);
      }
      
      if (result.results) {
        const r = result.results;
        console.log('\n  Performance:');
        console.log(`    Annual Return:    ${(r.annualReturn * 100).toFixed(2)}%`);
        console.log(`    Cumulative:       ${(r.cumulativeReturn * 100).toFixed(2)}%`);
        console.log(`    Sharpe:           ${r.sharpe.toFixed(2)}`);
        console.log(`    Max Drawdown:     ${(r.maxDrawdown * 100).toFixed(2)}%`);
        console.log(`    Win Rate:          ${(r.winRatio * 100).toFixed(1)}%`);
        console.log(`    Trading Days:     ${r.tradingDays}`);
      }
      
      if (result.error) {
        console.log(`\n  Error:      ${result.error}`);
      }
      
      console.log(`\n  Duration:   ${(result.durationMs / 1000).toFixed(1)}s`);
      console.log('========================================\n');

      process.exit(result.status === 'completed' ? 0 : 1);
    }

    case 'custom': {
      // node index.js custom <filePath|--backtestId <id>>
      let filePath = null;
      let backtestId = null;

      if (args[1] === '--backtestId' && args[2]) {
        backtestId = args[2];
      } else if (args[1]) {
        filePath = args[1];
      }

      if (!filePath && !backtestId) {
        console.error('Usage: node index.js custom <filePath>  OR  node index.js custom --backtestId <id>');
        process.exit(1);
      }

      const pipeline = new CustomPipeline({ loginManager });

      console.log('[CLI] Ensuring login...');
      await loginManager.ensureLogin();
      console.log('[CLI] Login ready\n');

      let result;
      if (backtestId) {
        console.log(`[CLI] Running backtest for existing ID: ${backtestId}`);
        result = await pipeline.runFromBacktestId(backtestId);
      } else {
        console.log(`[CLI] Loading strategy from: ${filePath}`);
        result = await pipeline.runFromFile(filePath);
      }

      console.log('\n========================================');
      console.log('  Custom Pipeline Result');
      console.log('========================================');
      console.log(`  Status:     ${result.status}`);
      console.log(`  Strategy:   ${result.strategyName}`);
      
      if (result.newBacktestId) {
        console.log(`  New ID:     ${result.newBacktestId}`);
      }
      
      if (result.results) {
        const r = result.results;
        console.log('\n  Performance:');
        console.log(`    Annual Return:    ${(r.annualReturn * 100).toFixed(2)}%`);
        console.log(`    Sharpe:            ${r.sharpe.toFixed(2)}`);
        console.log(`    Max Drawdown:      ${(r.maxDrawdown * 100).toFixed(2)}%`);
      }
      
      if (result.error) {
        console.log(`\n  Error:      ${result.error}`);
      }
      
      console.log(`  Duration:   ${(result.durationMs / 1000).toFixed(1)}s`);
      console.log('========================================\n');

      process.exit(result.status === 'completed' ? 0 : 1);
    }

    case 'login': {
      console.log('[CLI] Testing login...');
      const result = await loginManager.forceLogin();
      console.log('\n========================================');
      console.log('  Login Result');
      console.log('========================================');
      console.log(`  Status:    ${result.cookies.length} cookies loaded`);
      console.log(`  PageToken: ${result.pageToken ? 'YES' : 'NO'}`);
      console.log(`  Cached:    ${result.loginAt ? new Date(result.loginAt).toISOString() : 'N/A'}`);
      console.log('========================================\n');
      break;
    }

    case 'status': {
      try {
        const cached = loginManager.getCookies();
        console.log('========================================');
        console.log('  Cookie Status');
        console.log('========================================');
        console.log(`  Cached:    YES`);
        console.log(`  Cookies:   ${cached.cookies?.length || 0}`);
        console.log(`  PageToken: ${cached.pageToken ? 'YES' : 'NO'}`);
        console.log(`  LoginAt:   ${cached.loginAt ? new Date(cached.loginAt).toISOString() : 'N/A'}`);
        console.log(`  Expires:   ${cached.expires ? new Date(cached.expires).toISOString() : 'N/A'}`);
        console.log('========================================\n');
      } catch (e) {
        console.log('No cached cookies found. Run `node index.js login` first.');
      }
      break;
    }

    case 'list': {
      // List local strategies
      const pipeline = new CustomPipeline({ loginManager });
      const strategies = pipeline.listStrategies();
      
      if (strategies.length === 0) {
        console.log('No strategies found in ./strategies/');
        console.log('Add .py or .json strategy files to run custom backtests.');
      } else {
        console.log('========================================');
        console.log(`  Found ${strategies.length} strategy(ies)`);
        console.log('========================================');
        for (const s of strategies) {
          console.log(`  ${s.name} (${s.language})`);
          console.log(`    Path: ${s.path}`);
          console.log(`    Size: ${(s.size / 1024).toFixed(1)} KB`);
          console.log('');
        }
      }
      break;
    }

    case 'help':
    default:
      console.log(`
joinquant-pipeline - Automated JoinQuant backtest pipeline

USAGE:
  node index.js community <postId> <backtestId> [replyId]
    Run backtest for a community post strategy.
    Example: node index.js community 5aa05159e33a10f96fd215cfeb59137c 5c94c550e05e21cb0227715f0c7451ce

  node index.js custom <filePath>
    Run backtest for a local strategy file.
    Example: node index.js custom ./strategies/ma-cross.py

  node index.js custom --backtestId <id>
    Run backtest for an existing backtestId already on JoinQuant.
    Example: node index.js custom --backtestId 92a25fb27fd006b1f6b995dcc9533a83

  node index.js login
    Force fresh login and cache cookies.

  node index.js status
    Show current cookie status.

  node index.js list
    List local strategies in ./strategies/

  node index.js help
    Show this help message.

ENVIRONMENT VARIABLES:
  JOINQUANT_USERNAME   Your JoinQuant username (default: 15656096430)
  JOINQUANT_PASSWORD   Your JoinQuant password

EXAMPLES:
  # Run community post backtest
  JOINQUANT_PASSWORD=yourpass node index.js community 5aa05159e33a10f96fd215cfeb59137c 5c94c550e05e21cb0227715f0c7451ce

  # Run custom strategy
  node index.js custom ./strategies/my-strategy.py

  # Run existing backtest
  node index.js custom --backtestId 92a25fb27fd006b1f6b995dcc9533a83
`);
      break;
  }
}

main().catch(error => {
  console.error('[CLI] Fatal error:', error.message);
  process.exit(1);
});