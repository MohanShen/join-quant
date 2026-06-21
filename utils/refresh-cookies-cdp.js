/**
 * refresh-cookies-cdp.js
 *
 * Refresh data/cookies.json by harvesting the live session from a running
 * Chrome over CDP — replaces the disabled username/password form login
 * (LoginManager._doLogin), which JoinQuant now blocks with a CAPTCHA.
 *
 * The fetch pipeline (strategy-fetch.js) authenticates with raw HTTPS using a
 * Cookie header built from data/cookies.json; it only needs PHPSESSID + uid.
 * This script reads those cookies straight from the Chrome you've already
 * logged into manually — no form, no CAPTCHA.
 *
 * Prerequisite (one-time, keep running): start Chrome with a debug port and
 * log into joinquant.com once:
 *   nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
 *     --remote-debugging-port=9225 --user-data-dir=/tmp/jq-auth-browser \
 *     > /tmp/chrome-jq.log 2>&1 &
 *
 * Usage:
 *   node utils/refresh-cookies-cdp.js          # refresh cookies, then exit
 *
 * Environment:
 *   JQ_CDP_URL — Chrome debugging URL (default: http://localhost:9225)
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const COOKIES_FILE = path.join(DATA_DIR, 'cookies.json');
const CDP_URL = process.env.JQ_CDP_URL || 'http://localhost:9225';

const REQUIRED_COOKIES = ['PHPSESSID', 'uid'];

/**
 * Harvest JoinQuant session cookies from a running Chrome over CDP and write
 * them to data/cookies.json. Best-effort: never throws — returns a result
 * object so callers (e.g. the daily pipeline) can fall back to existing cookies.
 *
 * @param {object} [opts]
 * @param {string} [opts.cdpUrl] - Chrome debugging URL (default: env or :9225)
 * @returns {Promise<{ok: boolean, count?: number, names?: string[], error?: string}>}
 */
async function refreshCookiesFromCDP(opts = {}) {
  const cdpUrl = opts.cdpUrl || CDP_URL;
  let browser;
  try {
    console.log(`[cookies] Connecting to Chrome via CDP at ${cdpUrl} ...`);
    browser = await chromium.connectOverCDP(cdpUrl);

    // Gather cookies from every context, keep only joinquant.com cookies.
    const jqCookies = new Map(); // name -> cookie (last write wins)
    for (const ctx of browser.contexts()) {
      const cookies = await ctx.cookies();
      for (const c of cookies) {
        if (!c.domain || !c.domain.includes('joinquant.com')) continue;
        jqCookies.set(c.name, {
          name: c.name,
          value: c.value,
          domain: c.domain,
          path: c.path || '/',
          httpOnly: c.httpOnly || false,
          secure: c.secure || false,
          sameSite: c.sameSite || 'Lax',
          expires: c.expires,
        });
      }
    }

    const missing = REQUIRED_COOKIES.filter(n => !jqCookies.has(n));
    if (missing.length > 0) {
      return {
        ok: false,
        error: `Chrome is not logged into JoinQuant (missing ${missing.join(', ')}). ` +
               `Open joinquant.com in the debug Chrome and log in.`,
      };
    }

    const cookies = [...jqCookies.values()];
    ensureDataDir();
    fs.writeFileSync(
      COOKIES_FILE,
      JSON.stringify({ cookies, refreshedAt: new Date().toISOString(), source: 'cdp' }, null, 2)
    );

    const names = cookies.map(c => c.name);
    console.log(`[cookies] ✅ Refreshed data/cookies.json (${cookies.length} cookies: ${names.join(', ')})`);
    return { ok: true, count: cookies.length, names };
  } catch (e) {
    return { ok: false, error: e.message };
  } finally {
    // For a CDP connection, close() only disconnects Playwright — it does NOT
    // terminate the user's Chrome or its login session.
    if (browser) { try { await browser.close(); } catch {} }
  }
}

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

// ── CLI ─────────────────────────────────────────────────────────────────────
if (require.main === module) {
  (async () => {
    const res = await refreshCookiesFromCDP();
    if (!res.ok) {
      console.error(`[cookies] ❌ Refresh failed: ${res.error}`);
      process.exit(1);
    }
  })().catch(e => { console.error(e); process.exit(1); });
}

module.exports = { refreshCookiesFromCDP };
