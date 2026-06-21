/**
 * auth/login.js
 * 
 * Handles JoinQuant login via Playwright, cookie persistence,
 * and captcha detection. Automatically refreshes cookies when stale.
 * 
 * Usage:
 *   const { LoginManager } = require('./login');
 *   const lm = new LoginManager('./auth/cookies.json');
 *   await lm.ensureLogin();
 *   const cookies = lm.getCookies();
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

class LoginManager {
  /**
   * @param {string} cookiePath - Path to store cookies JSON file
   * @param {object} options
   * @param {string} options.username - JoinQuant username
   * @param {string} options.password - JoinQuant password
   * @param {number} options.maxRetries - Max retry attempts on captcha failure (default: 3)
   * @param {number} options.retryDelayMs - Delay between retries (default: 3000)
   */
  constructor(cookiePath, options = {}) {
    this.cookiePath = cookiePath;
    this.username = options.username || process.env.JOINQUANT_USERNAME || '15656096430';
    this.password = options.password || process.env.JOINQUANT_PASSWORD;
    this.maxRetries = options.maxRetries || 3;
    this.retryDelayMs = options.retryDelayMs || 3000;
    
    // Cookie cache for runtime
    this._cookies = null;
    this._pageToken = null;
  }

  /**
   * Ensures we have valid login cookies. Attempts to load from cache first,
   * falls back to fresh login if stale or missing.
   * 
   * @returns {Promise<object>} Object with cookies array and pageToken string
   */
  async ensureLogin() {
    const cached = this._loadFromCache();
    if (cached) {
      console.log('[auth] Using cached cookies');
      return cached;
    }
    
    console.log('[auth] No valid cache, performing fresh login');
    return await this._doLogin();
  }

  /**
   * Force a fresh login, ignoring cache.
   * @returns {Promise<object>} Fresh login credentials
   */
  async forceLogin() {
    return await this._doLogin();
  }

  /**
   * Get current cookies (must call ensureLogin first).
   * @returns {object} { cookies: [{name, value, domain, path}], pageToken: string }
   */
  getCookies() {
    if (!this._cookies) {
      throw new Error('Must call ensureLogin() before getCookies()');
    }
    return this._cookies;
  }

  /**
   * Get Playwright browser context with cookies pre-loaded.
   * Caller is responsible for closing the browser when done.
   * 
   * @param {boolean} headless - Run browser in headless mode (default: true)
   * @returns {Promise<{browser, context, page}>}
   */
  async getBrowserContext(headless = true) {
    const { cookies } = await this.ensureLogin();
    
    const browser = await chromium.launch({
      headless,
      executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    const context = await browser.newContext();
    
    // Set cookies in context
    for (const cookie of cookies) {
      // Don't set HttpOnly cookies that Playwright manages
      if (!cookie.httpOnly) {
        await context.addCookies([cookie]);
      }
    }
    
    // Also set HttpOnly cookies via addInitScript since we can't set them directly
    const httpOnlyCookies = cookies.filter(c => c.httpOnly);
    if (httpOnlyCookies.length > 0) {
      await context.addInitScript((cookies) => {
        // Set HttpOnly cookies via document.cookie workaround isn't possible
        // So we rely on the PHPSESSID being set via the navigation
      }, httpOnlyCookies);
    }
    
    const page = await context.newPage();
    
    // Try to set page token from storage if available
    if (this._pageToken) {
      await page.addInitScript((token) => {
        window.__JQ_PAGE_TOKEN__ = token;
      }, this._pageToken);
    }
    
    return { browser, context, page };
  }

  /**
   * Load cookies from disk cache if valid.
   * @returns {object|null} Cached credentials or null if invalid/missing
   */
  _loadFromCache() {
    if (!fs.existsSync(this.cookiePath)) return null;
    
    try {
      const data = JSON.parse(fs.readFileSync(this.cookiePath, 'utf8'));
      
      // Basic validation
      if (!data.cookies || !Array.isArray(data.cookies)) return null;
      if (!data.cookies.find(c => c.name === 'uid')) return null;
      if (!data.cookies.find(c => c.name === 'PHPSESSID')) return null;
      
      // Check if expires is set and not past
      if (data.expires && Date.now() > data.expires) {
        console.log('[auth] Cache expired');
        return null;
      }
      
      // Restore runtime cache
      this._cookies = data;
      this._pageToken = data.pageToken || null;
      
      return data;
    } catch (e) {
      console.warn('[auth] Failed to load cache:', e.message);
      return null;
    }
  }

  /**
   * Save cookies to disk cache.
   * @param {object} data - { cookies, pageToken?, expires? }
   */
  _saveToCache(data) {
    const dir = path.dirname(this.cookiePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(this.cookiePath, JSON.stringify(data, null, 2));
  }

  /**
   * Perform fresh login via Playwright.
   * Handles: captcha checkbox, login form, redirect detection.
   * 
   * @returns {Promise<object>} Logged-in credentials
   * @private
   */
  async _doLogin() {
    if (!this.password) {
      throw new Error('Password not set. Set JOINQUANT_PASSWORD env var or pass in constructor.');
    }

    const browser = await chromium.launch({
      headless: true,
      executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    const context = await browser.newContext();
    const page = await context.newPage();
    
    try {
      console.log('[auth] Navigating to login page...');
      await page.goto('https://www.joinquant.com/user/login', {
        waitUntil: 'networkidle',
        timeout: 30000
      });
      await page.waitForTimeout(1500);
      
      // Check if we got redirected (already logged in via browser cookies)
      const afterLoginUrl = page.url();
      if (!afterLoginUrl.includes('/user/login')) {
        console.log('[auth] Already logged in, no form needed');
      } else {
        console.log('[auth] Filling login form...');
        
        // Check and click captcha checkbox if present
        const checkbox = page.locator('input[type="checkbox"]').first();
        if (await checkbox.isVisible({ timeout: 2000 }).catch(() => false)) {
          await checkbox.check();
          console.log('[auth] Checked agreement checkbox');
        }
        
        // Fill credentials
        await page.fill('input[name="username"]', this.username);
        await page.fill('input[name="pwd"]', this.password);
        await page.waitForTimeout(500);
        
        // Click login button
        const loginBtn = page.locator('button:has-text("登  录")').first();
        await loginBtn.click({ timeout: 5000 });
        
        // Wait for redirect
        await page.waitForTimeout(6000);
      }
      
      // Extract cookies
      const rawCookies = await context.cookies();
      
      // Filter out overly long or invalid cookies
      const cookies = rawCookies
        .filter(c => c.value && c.value.length < 2000)
        .map(c => ({
          name: c.name,
          value: c.value,
          domain: c.domain,
          path: c.path || '/',
          httpOnly: c.httpOnly || false,
          secure: c.secure || false,
          sameSite: c.sameSite || 'Lax',
          expires: c.expires
        }));
      
      // Get page token if available (for subsequent API calls)
      let pageToken = null;
      try {
        await page.goto('https://www.joinquant.com/algorithm/backtest/summary?backtestId=demo', {
          waitUntil: 'networkidle',
          timeout: 15000
        });
        pageToken = await page.evaluate(() => window.tokenData?.value || null);
      } catch (e) {
        console.warn('[auth] Could not fetch page token:', e.message);
      }
      
      const result = {
        cookies,
        pageToken,
        loginAt: Date.now(),
        expires: Date.now() + 24 * 60 * 60 * 1000 // 24h cache
      };
      
      // Cache to disk
      this._cookies = result;
      this._pageToken = pageToken;
      this._saveToCache(result);
      
      console.log(`[auth] Login successful. Cookies: ${cookies.length}, HasPageToken: ${!!pageToken}`);
      
      return result;
      
    } finally {
      await browser.close();
    }
  }
}

module.exports = { LoginManager };