/**
 * refresh-cookies.js
 *
 * Refresh data/cookies.json for the fetch pipeline, trying two login methods
 * in order:
 *
 *   1. PRIMARY  — username/password form login (LoginManager). Fully
 *      unattended. Works whenever JoinQuant is NOT showing a CAPTCHA.
 *   2. FALLBACK — harvest the live session from a running Chrome over CDP
 *      (refresh-cookies-cdp.js). Used when form login is blocked (CAPTCHA)
 *      or no password is configured.
 *
 * Form login is tried first on purpose: if JoinQuant drops the CAPTCHA again
 * in the future, the pipeline automatically returns to unattended login with
 * no code change. Until then it transparently falls back to CDP.
 *
 * The canonical data/cookies.json is only overwritten once a candidate set of
 * cookies is validated (must contain uid + PHPSESSID), so a failed form-login
 * attempt never clobbers a previously-good session.
 *
 * Usage:
 *   node utils/refresh-cookies.js          # refresh cookies, then exit
 *
 * Environment:
 *   JOINQUANT_USERNAME — JQ account (default: 15656096430)
 *   JOINQUANT_PASSWORD — JQ password (enables form login)
 *   JQ_CDP_URL         — Chrome debugging URL for fallback (default: :9225)
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

const { LoginManager } = require('./login');
const { refreshCookiesFromCDP } = require('./refresh-cookies-cdp');

const DATA_DIR = path.join(__dirname, '..', 'data');
const COOKIES_FILE = path.join(DATA_DIR, 'cookies.json');
const REQUIRED_COOKIES = ['PHPSESSID', 'uid'];

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

/** True if the cookie set carries an authenticated session (uid + PHPSESSID). */
function hasRequired(cookies) {
  const names = new Set((cookies || []).map(c => c.name));
  return REQUIRED_COOKIES.every(n => names.has(n));
}

/** Dedupe cookies by name (last write wins) so the Cookie header has no dupes. */
function dedupeByName(cookies) {
  const byName = new Map();
  for (const c of cookies || []) byName.set(c.name, c);
  return [...byName.values()];
}

function writeCookies(cookies, source, pageToken) {
  ensureDataDir();
  const payload = { cookies: dedupeByName(cookies), refreshedAt: new Date().toISOString(), source };
  if (pageToken) payload.pageToken = pageToken;
  fs.writeFileSync(COOKIES_FILE, JSON.stringify(payload, null, 2));
}

/**
 * PRIMARY: username/password form login. Writes to a throwaway temp file so a
 * blocked/partial login never overwrites the canonical cookie file; only on
 * success do we promote the cookies to data/cookies.json.
 *
 * @returns {Promise<{ok: boolean, source?: string, count?: number, names?: string[], error?: string}>}
 */
async function tryFormLogin() {
  const username = process.env.JOINQUANT_USERNAME || '15656096430';
  const password = process.env.JOINQUANT_PASSWORD;
  if (!password) return { ok: false, error: 'JOINQUANT_PASSWORD not set' };

  const tmpPath = path.join(os.tmpdir(), `jq-form-cookies-${process.pid}.json`);
  try {
    const lm = new LoginManager(tmpPath, { username, password });
    const data = await lm.forceLogin();
    if (!hasRequired(data.cookies)) {
      return { ok: false, error: 'login returned no uid/PHPSESSID (CAPTCHA likely active)' };
    }
    writeCookies(data.cookies, 'form', data.pageToken);
    const saved = dedupeByName(data.cookies);
    return { ok: true, source: 'form', count: saved.length, names: saved.map(c => c.name) };
  } catch (e) {
    return { ok: false, error: e.message };
  } finally {
    try { fs.unlinkSync(tmpPath); } catch {}
  }
}

/**
 * Refresh data/cookies.json: form login first, CDP harvest as fallback.
 * Best-effort — never throws; returns a result object describing what happened.
 *
 * @returns {Promise<{ok: boolean, source?: string, count?: number, names?: string[], error?: string}>}
 */
async function refreshCookies() {
  console.log('[cookies] Refreshing session — trying username/password login first...');
  const form = await tryFormLogin();
  if (form.ok) {
    console.log(`[cookies] ✅ Form login succeeded (${form.count} cookies: ${form.names.join(', ')})`);
    return form;
  }

  console.warn(`[cookies] Form login unavailable: ${form.error}`);
  console.log('[cookies] Falling back to CDP cookie harvest...');
  const cdp = await refreshCookiesFromCDP();
  if (cdp.ok) {
    console.log('[cookies] ✅ Session refreshed via CDP fallback');
  } else {
    console.warn(`[cookies] CDP fallback also failed: ${cdp.error}`);
  }
  return cdp;
}

// ── CLI ─────────────────────────────────────────────────────────────────────
if (require.main === module) {
  refreshCookies()
    .then(res => {
      if (!res.ok) {
        console.error(`[cookies] ❌ All login methods failed: ${res.error}`);
        process.exit(1);
      }
    })
    .catch(e => { console.error(e); process.exit(1); });
}

module.exports = { refreshCookies, tryFormLogin };
