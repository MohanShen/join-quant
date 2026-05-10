/**
 * backtest/runner.js
 * 
 * Handles the full backtest lifecycle:
 * 1. Trigger a new backtest via Playwright button click
 * 2. Poll stats API until completion
 * 3. Parse and return normalized results
 * 
 * Usage:
 *   const { BacktestRunner } = require('./backtest/runner');
 *   const runner = new BacktestRunner({ loginManager });
 *   const result = await runner.run({ postId, backtestId });
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

/**
 * Polling configuration defaults
 */
const DEFAULT_POLL_INTERVAL_MS = 10000;
const DEFAULT_MAX_POLL_ATTEMPTS = 120; // 20 minutes max
const DEFAULT_COMPLETION_TIMEOUT_MS = 25 * 60 * 1000;

class BacktestRunner {
  /**
   * @param {object} options
   * @param {LoginManager} options.loginManager - Auth handler
   * @param {number} options.pollIntervalMs - How often to poll stats (default: 10000)
   * @param {number} options.maxPollAttempts - Max poll calls before giving up (default: 120)
   * @param {string} options.browserDir - Path for browser user data (default: /tmp/jq-browser)
   */
  constructor(options = {}) {
    this.loginManager = options.loginManager;
    this.pollIntervalMs = options.pollIntervalMs || DEFAULT_POLL_INTERVAL_MS;
    this.maxPollAttempts = options.maxPollAttempts || DEFAULT_MAX_POLL_ATTEMPTS;
    this.browserDir = options.browserDir || '/tmp/jq-browser';
  }

  /**
   * Run a backtest given a postId and source backtestId.
   * 
   * Flow:
   * 1. Navigate to the strategy summary page (iframe context)
   * 2. Click "克隆策略" button
   * 3. Capture the new backtestId from the redirect URL
   * 4. Poll the stats API until backtest completes
   * 5. Return normalized results
   * 
   * @param {object} params
   * @param {string} params.postId - Community post ID (e.g. "5aa05159e33a10f96fd215cfeb59137c")
   * @param {string} params.backtestId - Source strategy backtestId (e.g. "5c94c550e05e21cb0227715f0c7451ce")
   * @param {string} [params.replyId] - Reply ID if responding to a reply
   * @param {number} [params.initCash] - Initial cash (default: 100000)
   * @param {string} [params.startDate] - Start date override
   * @param {string} [params.endDate] - End date override
   * @returns {Promise<object>} { backtestId, status, results }
   */
  async run(params) {
    const { postId, backtestId, replyId = '' } = params;
    
    if (!postId || !backtestId) {
      throw new Error('postId and backtestId are required');
    }

    let browser = null;
    let context = null;
    let page = null;

    try {
      console.log(`[runner] Starting backtest for post=${postId}, source=${backtestId}`);
      
      // Launch browser with persistent context for cookie reuse
      const { browser: b, context: ctx, page: p } = await this._launchBrowser();
      browser = b;
      context = ctx;
      page = p;

      // Navigate to strategy summary iframe page
      const strategyUrl = `https://www.joinquant.com/algorithm/backtest/summary?backtestId=${backtestId}&postId=${postId}&replyId=${replyId}&iframe=1`;
      console.log(`[runner] Navigating to strategy page...`);
      
      await page.goto(strategyUrl, { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(2000);

      // Check if we're logged in (page should show "克隆策略" button)
      const hasCloneButton = await this._hasCloneButton(page);
      if (!hasCloneButton) {
        throw new Error('Not logged in or strategy page not accessible. Try re-logging.');
      }

      // Click the clone button and capture the new backtestId
      const newBacktestId = await this._clickCloneAndGetNewId(page, postId, backtestId);
      console.log(`[runner] Clone created, new backtestId=${newBacktestId}`);

      // Poll for results
      console.log(`[runner] Waiting for backtest to complete...`);
      const results = await this._pollUntilComplete(newBacktestId);
      
      console.log(`[runner] Backtest completed successfully`);
      return {
        backtestId: newBacktestId,
        status: 'completed',
        results
      };

    } catch (error) {
      console.error(`[runner] Error: ${error.message}`);
      throw error;
      
    } finally {
      if (page) await page.close();
      if (context) await context.close();
      if (browser) await browser.close();
    }
  }

  /**
   * Poll a specific backtestId for results.
   * Useful for re-checking a backtest that was started externally.
   * 
   * @param {string} backtestId - Backtest ID to poll
   * @returns {Promise<object>} Backtest results
   */
  async pollResults(backtestId) {
    return await this._pollUntilComplete(backtestId);
  }

  /**
   * Launch Playwright browser with persistent cookie context.
   * @private
   */
  async _launchBrowser() {
    // Ensure browser data directory exists
    if (!fs.existsSync(this.browserDir)) {
      fs.mkdirSync(this.browserDir, { recursive: true });
    }

    const browser = await chromium.launch({ 
      headless: true,
      args: ['--no-sandbox']
    });

    // Create a new context (separate from any existing logins)
    // We handle auth via the loginManager's cookies
    const context = await browser.newContext({
      userDataDir: this.browserDir,
      acceptDownloads: false
    });

    // Inject cookies from login manager
    if (this.loginManager) {
      const { cookies } = this.loginManager.getCookies();
      
      // Add cookies that are not HttpOnly
      const addableCookies = cookies.filter(c => !c.httpOnly);
      if (addableCookies.length > 0) {
        await context.addCookies(addableCookies);
      }
      
      // Navigate once to establish session for HttpOnly cookies
      const page = await context.newPage();
      await page.goto('https://www.joinquant.com/', { waitUntil: 'domcontentloaded' });
      
      // Inject page token if available
      const { pageToken } = this.loginManager.getCookies();
      if (pageToken) {
        await page.addInitScript((token) => {
          window.__JQ_PAGE_TOKEN__ = token;
        }, pageToken);
      }
      
      await page.close();
    }

    const page = await context.newPage();
    return { browser, context, page };
  }

  /**
   * Check if the clone button is visible on the page.
   * @private
   */
  async _hasCloneButton(page) {
    try {
      const hasButton = await page.evaluate(() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
          if ((el.textContent || '').trim() === '克隆策略') {
            return true;
          }
        }
        return false;
      });
      return hasButton;
    } catch {
      return false;
    }
  }

  /**
   * Click the clone button and wait for navigation to new backtest.
   * Returns the new backtestId from the URL.
   * 
   * @private
   */
  async _clickCloneAndGetNewId(page, postId, backtestId) {
    // Set up URL change listener
    let newBacktestIdPromise = new Promise((resolve, reject) => {
      // Check URL every 500ms for backtestId change
      const checkInterval = setInterval(async () => {
        try {
          const url = page.url();
          const match = url.match(/backtestId=([a-f0-9]{32})/);
          if (match && match[1] !== backtestId) {
            clearInterval(checkInterval);
            resolve(match[1]);
          }
        } catch {}
      }, 500);

      // Timeout after 30 seconds
      setTimeout(() => {
        clearInterval(checkInterval);
        reject(new Error('Timeout waiting for clone to create new backtest'));
      }, 30000);
    });

    // Click the button via evaluate to trigger the JS handler
    const clickResult = await page.evaluate(() => {
      const all = document.querySelectorAll('*');
      for (const el of all) {
        if ((el.textContent || '').trim() === '克隆策略') {
          el.click();
          return 'clicked';
        }
      }
      return 'not found';
    });

    if (clickResult !== 'clicked') {
      throw new Error('Clone button not found on page');
    }

    // Wait for new backtestId
    const newBacktestId = await newBacktestIdPromise;
    return newBacktestId;
  }

  /**
   * Poll the stats API until the backtest completes.
   * 
   * @private
   */
  async _pollUntilComplete(backtestId) {
    let attempts = 0;
    let lastError = null;

    while (attempts < this.maxPollAttempts) {
      attempts++;
      
      try {
        const stats = await this._fetchStats(backtestId);
        
        if (stats && stats.data) {
          // Check for completion indicators
          if (stats.data.trading_days && stats.data.trading_days > 0) {
            return this._parseResults(stats.data);
          }
        }
        
        // If we got data but not complete yet, keep polling
        console.log(`[runner] Poll ${attempts}/${this.maxPollAttempts}: backtest still running...`);
        
      } catch (error) {
        lastError = error;
        // Some errors are expected while backtest is running (e.g. 503)
        console.log(`[runner] Poll ${attempts}/${this.maxPollAttempts}: ${error.message}`);
      }

      if (attempts < this.maxPollAttempts) {
        await this._sleep(this.pollIntervalMs);
      }
    }

    throw new Error(`Backtest polling timed out after ${attempts} attempts. Last error: ${lastError?.message}`);
  }

  /**
   * Fetch stats for a backtest via the API.
   * 
   * @private
   */
  async _fetchStats(backtestId) {
    // Try via Playwright browser fetch (has full session)
    const context = await this._getActiveContext();
    if (context) {
      try {
        const resp = await context.evaluate(async (btId) => {
          const response = await fetch(`/algorithm/backtest/stats?backtestId=${btId}&ajax=1`, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
          });
          return { status: response.status, body: await response.json() };
        }, backtestId);
        
        if (resp.status === 200 && resp.body.data) {
          return resp.body;
        }
      } catch {}
    }

    // Fallback: try via curl with fresh login
    return await this._fetchStatsViaCurl(backtestId);
  }

  /**
   * Fallback: fetch stats via curl (fresh login each time for fresh cookies).
   * @private
   */
  async _fetchStatsViaCurl(backtestId) {
    return new Promise((resolve, reject) => {
      const { execSync } = require('child_process');
      
      try {
        // Fresh login
        const loginCmd = `curl -s -c /tmp/jq-stats-cookies.txt -X POST https://www.joinquant.com/user/login -d "username=${this.loginManager?.username || '15656096430'}&password=${this.loginManager?.password || ''}" -L -A "Mozilla/5.0"`;
        execSync(loginCmd, { stdio: 'pipe' });
        
        const cookies = fs.readFileSync('/tmp/jq-stats-cookies.txt', 'utf8');
        const uidMatch = cookies.match(/uid\t([^\t]+)/);
        const phpsessidMatch = cookies.match(/PHPSESSID\t([^\t]+)/);
        const tokenMatch = cookies.match(/token\t([^\t]+)/);
        
        if (!uidMatch || !phpsessidMatch) {
          throw new Error('Login failed for stats fetch');
        }
        
        const uid = uidMatch[1];
        const phpsessid = phpsessidMatch[1];
        const token = tokenMatch ? tokenMatch[1] : '';
        
        const curlCmd = `curl -s "https://www.joinquant.com/algorithm/backtest/stats?backtestId=${backtestId}&ajax=1" -X POST -H "X-Requested-With: XMLHttpRequest" --cookie "uid=${uid}; PHPSESSID=${phpsessid}; token=${token}"`;
        const output = execSync(curlCmd, { encoding: 'utf8', timeout: 15000 });
        
        const parsed = JSON.parse(output);
        resolve(parsed);
        
      } catch (error) {
        // If curl login fails, return null (will retry)
        console.warn(`[runner] curl fallback failed: ${error.message}`);
        return null;
      }
    });
  }

  _activeContext = null;
  
  async _getActiveContext() {
    return this._activeContext;
  }

  /**
   * Parse raw stats data into normalized format.
   * 
   * @private
   */
  _parseResults(data) {
    return {
      // Performance
      annualReturn: data.annual_algo_return || 0,         // 年化收益 (decimal, e.g. 1.88 = 188%)
      cumulativeReturn: data.algorithm_return || 0,         // 累计收益 (decimal, e.g. 213.27 = 21327%)
      benchmarkReturn: data.benchmark_return || 0,         // 基准收益
      
      // Risk metrics
      maxDrawdown: data.max_drawdown || 0,                // 最大回撤 (decimal, e.g. 0.24 = 24%)
      volatility: data.algorithm_volatility || 0,         // 策略波动率
      benchmarkVolatility: data.benchmark_volatility || 0,
      
      // Ratios
      sharpe: data.sharpe || 0,
      sortino: data.sortino || 0,
      information: data.information || 0,
      alpha: data.alpha || 0,
      beta: data.beta || 0,
      
      // Trading stats
      tradingDays: data.trading_days || 0,
      winRatio: data.win_ratio || 0,                      // 胜率 (decimal)
      dayWinRatio: data.day_win_ratio || 0,              // 日胜率
      profitLossRatio: data.profit_loss_ratio || 0,      // 盈亏比
      winCount: data.win_count || 0,
      loseCount: data.lose_count || 0,
    };
  }

  _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

module.exports = { BacktestRunner };