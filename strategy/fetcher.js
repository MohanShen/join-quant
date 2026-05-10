/**
 * strategy/fetcher.js
 * 
 * Fetches strategy source code from JoinQuant community posts via API.
 * 
 * Usage:
 *   const { StrategyFetcher } = require('./strategy/fetcher');
 *   const fetcher = new StrategyFetcher({ loginManager });
 *   const source = await fetcher.fetch({ postId, backtestId });
 */

const { execSync } = require('child_process');

class StrategyFetcher {
  /**
   * @param {object} options
   * @param {LoginManager} options.loginManager - Auth handler (optional, uses curl if not provided)
   * @param {string} options.username - JoinQuant username (default: env.JOINQUANT_USERNAME)
   */
  constructor(options = {}) {
    this.loginManager = options.loginManager;
    this.username = options.username || process.env.JOINQUANT_USERNAME || '15656096430';
    this._cache = new Map();
  }

  /**
   * Fetch strategy source code from a community post.
   * 
   * @param {object} params
   * @param {string} params.postId - Community post ID
   * @param {string} params.backtestId - Strategy backtest ID
   * @param {string} [params.replyId] - Reply ID if fetching from a reply
   * @returns {Promise<string|null>} Python source code or null if unavailable
   */
  async fetch(params) {
    const { postId, backtestId, replyId = '' } = params;
    
    if (!postId || !backtestId) {
      throw new Error('postId and backtestId are required');
    }

    // Check cache first
    const cacheKey = `${postId}/${backtestId}/${replyId}`;
    if (this._cache.has(cacheKey)) {
      return this._cache.get(cacheKey);
    }

    // Try via loginManager first, then curl fallback
    let source = await this._fetchViaBrowser(postId, backtestId, replyId);
    
    if (!source) {
      source = await this._fetchViaCurl(postId, backtestId, replyId);
    }

    if (source) {
      this._cache.set(cacheKey, source);
    }

    return source;
  }

  /**
   * Fetch source via Playwright browser (has full session).
   * @private
   */
  async _fetchViaBrowser(postId, backtestId, replyId) {
    if (!this.loginManager) return null;

    try {
      const { browser, context, page } = await this.loginManager.getBrowserContext();
      
      try {
        // Navigate to strategy page
        const url = `https://www.joinquant.com/algorithm/backtest/summary?backtestId=${backtestId}&postId=${postId}&replyId=${replyId}&iframe=1`;
        await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
        await page.waitForTimeout(1000);

        // Click "源码" tab if visible, or look for code in page
        const source = await page.evaluate(async () => {
          // Try clicking the source tab
          const tabs = document.querySelectorAll('*');
          for (const tab of tabs) {
            if ((tab.textContent || '').trim() === '源码') {
              tab.click();
              break;
            }
          }
          
          await new Promise(r => setTimeout(r, 1000));
          
          // Look for the code element (ace editor or pre/code)
          const codeEl = document.querySelector('#code-view') || 
                         document.querySelector('.code-view') ||
                         document.querySelector('pre') ||
                         document.querySelector('code');
          
          if (codeEl) {
            return codeEl.textContent || null;
          }
          
          // Try window.__SOURCE__ or similar
          return window.__STRATEGY_SOURCE__ || window.strategySource || null;
        });

        return source;

      } finally {
        await browser.close();
      }
    } catch (e) {
      console.warn(`[fetcher] Browser fetch failed: ${e.message}`);
      return null;
    }
  }

  /**
   * Fetch source via curl (uses fresh login each time).
   * @private
   */
  async _fetchViaCurl(postId, backtestId, replyId) {
    try {
      // Step 1: Fresh login to get cookies
      const loginCmd = `curl -s -c /tmp/jq-source-cookies.txt -X POST https://www.joinquant.com/user/login ` +
        `-d "username=${this.username}&password=${this.loginManager?.password || process.env.JOINQUANT_PASSWORD || ''}" ` +
        `-L -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"`;
      
      execSync(loginCmd, { stdio: 'pipe' });

      // Read cookies
      const cookieContent = fs.readFileSync('/tmp/jq-source-cookies.txt', 'utf8');
      const uidMatch = cookieContent.match(/uid\t([^\t\n]+)/);
      const phpsessidMatch = cookieContent.match(/PHPSESSID\t([^\t\n]+)/);
      const tokenMatch = cookieContent.match(/token\t([^\t\n]+)/);

      if (!uidMatch || !phpsessidMatch) {
        console.warn('[fetcher] Login failed via curl');
        return null;
      }

      const uid = uidMatch[1].trim();
      const phpsessid = phpsessidMatch[1].trim();
      const token = tokenMatch ? tokenMatch[1].trim() : '';

      // Step 2: Fetch source via the source API
      const sourceCmd = `curl -s "https://www.joinquant.com/algorithm/backtest/source?backtestId=${backtestId}" ` +
        `-H "Accept: application/json" ` +
        `-H "X-Requested-With: XMLHttpRequest" ` +
        `--cookie "uid=${uid}; PHPSESSID=${phpsessid}; token=${token}"`;

      const output = execSync(sourceCmd, { encoding: 'utf8', timeout: 15000 });
      const parsed = JSON.parse(output);

      if (parsed.data && parsed.data.source) {
        return parsed.data.source;
      }

      return null;

    } catch (e) {
      console.warn(`[fetcher] curl fetch failed: ${e.message}`);
      return null;
    }
  }

  /**
   * List available backtests for a community post.
   * 
   * @param {string} postId - Community post ID
   * @returns {Promise<Array>} Array of { backtestId, name, annualReturn, maxDrawdown, sharpe }
   */
  async listBacktests(postId) {
    // This would require navigating to the community page
    // For now, return empty - community page backtest listing is complex
    console.warn('[fetcher] listBacktests not yet implemented - requires community page navigation');
    return [];
  }
}

const fs = require('fs');

module.exports = { StrategyFetcher };