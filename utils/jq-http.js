/**
 * jq-http.js — ONE HTTP path for every JoinQuant API call.
 *
 * Why this exists
 * ---------------
 * JoinQuant geo-blocks requests coming from outside mainland China. A blocked
 * request still returns HTTP 200, but the body is an HTML page titled
 * 「当前地区暂不支持访问」 — so `JSON.parse()` throws a syntax error and every
 * caller that wrapped the parse in a try/catch silently treated it as "no
 * results". Pipeline 1 (discover → fetch → daily) used raw `https.get` /
 * `curl` and died this way; its state files stopped moving in 2026-07.
 *
 * Pipeline 2 never had the problem because it drives a Chrome that already
 * lives in the right region (the Windows QMT box, reached over an SSH tunnel)
 * and is already logged in. This module gives Pipeline 1 the same path:
 * `fetch()` executed INSIDE that browser, same-origin against joinquant.com,
 * so it inherits both the region and the httpOnly session cookies.
 *
 * Order of preference
 *   1. CDP browser (correct region + logged-in session)     <- normal path
 *   2. Direct https from this process                        <- only if CDP is
 *      down; throws a clear, actionable error if the response is the
 *      geo-block page rather than pretending the list was empty.
 *
 * Page etiquette (matches strategy-post-backtest.js): REUSE an existing tab
 * and never close it — closing the last page tears down the CDP session's
 * cookie context. We only ever close a tab we opened ourselves.
 *
 * Usage:
 *   const jq = require('./jq-http');
 *   const json = await jq.jqJson('https://www.joinquant.com/...');
 *   await jq.close();          // once, at the end of the process
 */

const https = require('node:https');
const { ensureCdp, cdpUrl, describe: describeExec } = require('./exec-config');

/** The geo-block interstitial. HTTP 200 + HTML, so only the body identifies it. */
const GEO_BLOCK_RE = /当前地区暂不支持访问|地区暂不支持/;

const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36';

let _browser = null;       // Playwright Browser (CDP connection)
let _page = null;          // the tab we run fetch() in
let _pageIsOurs = false;   // did we open it? only then may we close it
let _cdpDown = false;      // sticky: don't re-probe a dead endpoint every call

class GeoBlockedError extends Error {
  constructor(url) {
    super(
      `JoinQuant geo-blocked this request (当前地区暂不支持访问).\n` +
      `  url: ${url}\n` +
      `  Direct HTTP from this machine cannot reach the API. Route through the\n` +
      `  CDP browser instead — exec mode is ${describeExec()}.\n` +
      `  Check it with: ./scripts/cdp-tunnel.sh status`
    );
    this.name = 'GeoBlockedError';
    this.url = url;
  }
}

/** True when a response body is the geo-block interstitial rather than data. */
function isGeoBlocked(text) {
  return typeof text === 'string' && GEO_BLOCK_RE.test(text);
}

/**
 * Connect to the CDP browser (once) and return a tab sitting on joinquant.com.
 * Returns null when CDP is unreachable, so callers can fall back.
 */
async function getPage() {
  if (_page) return _page;
  if (_cdpDown) return null;

  const cdp = await ensureCdp({ quiet: true });
  if (!cdp.ok) {
    _cdpDown = true;
    return null;
  }

  let chromium;
  try {
    ({ chromium } = require('playwright'));
  } catch {
    _cdpDown = true;
    return null;
  }

  try {
    _browser = await chromium.connectOverCDP(cdp.url);
    const ctx = _browser.contexts()[0];

    // Prefer a tab already on joinquant.com: same-origin fetch, and reusing it
    // means we never have to close anything.
    const pages = ctx.pages();
    const existing = pages.find(p => /joinquant\.com/.test(p.url()) && !/\/user\/login/.test(p.url()));
    if (existing) {
      _page = existing;
      _pageIsOurs = false;
    } else {
      _page = await ctx.newPage();
      _pageIsOurs = true;
      await _page.goto('https://www.joinquant.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
    }
    return _page;
  } catch {
    _cdpDown = true;
    try { if (_browser) await _browser.close(); } catch { /* ignore */ }
    _browser = null;
    _page = null;
    return null;
  }
}

/**
 * Run one fetch() inside the browser tab.
 * @returns {Promise<{status:number, body:string}>}
 */
async function viaCdp(page, url, { method = 'GET', body = null, json = false } = {}) {
  return page.evaluate(async ({ url, method, body, json }) => {
    const headers = { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json, text/plain, */*' };
    if (json) headers['Content-Type'] = 'application/json';
    const res = await fetch(url, {
      method,
      credentials: 'include',
      headers,
      body: body == null ? undefined : (json ? JSON.stringify(body) : body),
    });
    return { status: res.status, body: await res.text() };
  }, { url, method, body, json });
}

/** Raw https from this process. Used only when CDP is unavailable. */
function viaDirect(url, { method = 'GET', body = null, json = false, cookies = '' } = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const payload = body == null ? null : (json ? JSON.stringify(body) : body);
    const headers = {
      'Accept': 'application/json, text/plain, */*',
      'X-Requested-With': 'XMLHttpRequest',
      'User-Agent': UA,
    };
    if (cookies) headers['Cookie'] = cookies;
    if (payload != null) {
      headers['Content-Type'] = json ? 'application/json' : 'application/x-www-form-urlencoded';
      headers['Content-Length'] = Buffer.byteLength(payload);
    }
    const req = https.request(
      { hostname: u.hostname, path: u.pathname + u.search, method, headers },
      res => {
        let data = '';
        res.on('data', c => (data += c));
        res.on('end', () => resolve({ status: res.statusCode, body: data }));
      }
    );
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(new Error(`timeout: ${url}`)); });
    if (payload != null) req.write(payload);
    req.end();
  });
}

/**
 * GET/POST a JoinQuant URL and return the raw response body.
 * Throws GeoBlockedError when the region gate answered instead of the API.
 *
 * @param {string} url
 * @param {{method?:string, body?:any, json?:boolean, cookies?:string}} [opts]
 * @returns {Promise<string>}
 */
async function jqText(url, opts = {}) {
  const page = await getPage();
  let res;
  if (page) {
    try {
      res = await viaCdp(page, url, opts);
    } catch {
      // Tab went away (user closed it, navigation, etc.) — drop it and retry direct.
      _page = null;
      res = await viaDirect(url, opts);
    }
  } else {
    res = await viaDirect(url, opts);
  }
  if (isGeoBlocked(res.body)) throw new GeoBlockedError(url);
  return res.body;
}

/**
 * GET/POST a JoinQuant URL and parse the response as JSON.
 * Throws on a non-JSON body so a blocked/HTML response can never be mistaken
 * for an empty result set — that silent failure is what broke Pipeline 1.
 *
 * @param {string} url
 * @param {{method?:string, body?:any, json?:boolean, cookies?:string}} [opts]
 * @returns {Promise<object>}
 */
async function jqJson(url, opts = {}) {
  const text = await jqText(url, opts);
  try {
    return JSON.parse(text);
  } catch {
    const head = text.replace(/\s+/g, ' ').slice(0, 160);
    throw new Error(`JoinQuant returned non-JSON for ${url}\n  body starts: ${head}`);
  }
}

/** POST a JSON body and parse the JSON reply. */
function jqPostJson(url, body, opts = {}) {
  return jqJson(url, { ...opts, method: 'POST', body, json: true });
}

/** Which transport the next call will use, for logs. */
function transport() {
  if (_page) return 'cdp';
  return _cdpDown ? 'direct' : 'cdp (not yet connected)';
}

/** Disconnect from the browser. Only closes a tab we opened ourselves. */
async function close() {
  try {
    if (_page && _pageIsOurs) await _page.close();
  } catch { /* ignore */ }
  try {
    if (_browser) await _browser.close();   // connectOverCDP: disconnects, does not kill Chrome
  } catch { /* ignore */ }
  _page = null;
  _browser = null;
  _pageIsOurs = false;
}

module.exports = {
  jqText,
  jqJson,
  jqPostJson,
  isGeoBlocked,
  GeoBlockedError,
  transport,
  close,
  cdpUrl,
};
