/**
 * fetcher.js — strategy source for a community post, via the one HTTP path.
 *
 * Usage:
 *   const { StrategyFetcher } = require('./fetcher');
 *   const source = await new StrategyFetcher().fetch({ postId, backtestId });
 *
 * ## ⚠⚠ Rewritten 2026-10-17: this was a second, WRONG HTTP client
 *
 * `fetch()` tried two paths of its own and both were things CLAUDE.md forbids by name:
 *
 *   1. `_fetchViaBrowser` — launched its own Playwright browser through the loginManager. That
 *      cannot work: JQ keeps `PHPSESSID`/`token` as **httpOnly** cookies Playwright may not set,
 *      and a fresh headless browser lands on the 拼图验证 CAPTCHA. Pipeline 2 connects over CDP to
 *      an already-logged-in Chrome for exactly this reason.
 *   2. `_fetchViaCurl` — **raw `curl` to joinquant.com**, the one call this repo must never make.
 *      JQ geo-blocks requests from outside mainland China with an **HTTP 200 HTML** page
 *      (「当前地区暂不支持访问」), so `JSON.parse` threw, the bare `catch` returned `null`, and the
 *      caller read that as "this post has no source". That is not a hypothetical: it is the exact
 *      failure that killed Pipeline 1 silently **for two months**.
 *
 *   It also shipped three credential problems on that path: a hard-coded phone number as the
 *   default username, the password interpolated into a shell command line (readable by any local
 *   user via `ps`), and the resulting session cookies written to a predictable
 *   `/tmp/jq-source-cookies.txt`.
 *
 * `utils/jq-http.js` already does this correctly — it runs `fetch()` **inside** the CDP Chrome
 * (right region, logged-in cookies), falls back to direct https only when CDP is down, and
 * **throws** `GeoBlockedError` instead of returning an empty result. So this file is now a thin
 * wrapper over it and `utils/strategy-fetch.js`'s proven endpoint, with the ~120 lines of parallel
 * transport deleted rather than kept "just in case": a second transport is what drifted.
 *
 * ⚠ `loginManager` and `username` are still accepted so `pipelines/community.js` and
 * `index.js` need no change, and are deliberately IGNORED — jq-http needs no credentials.
 */

const jq = require('./jq-http');

const SOURCE_URL = id =>
  `https://www.joinquant.com/algorithm/backtest/source?backtestId=${id}`;

class StrategyFetcher {
  /**
   * @param {object} [options]
   * @param {object} [options.loginManager] accepted for call-site compatibility; unused.
   * @param {string} [options.username]     accepted for call-site compatibility; unused.
   */
  constructor(options = {}) {
    // Kept only so an existing caller's option bag does not become a silent typo. The CDP
    // transport authenticates by reusing the real browser session, so there is nothing to pass.
    this.loginManager = options.loginManager || null;
    this._cache = new Map();
  }

  /**
   * Strategy source for one community post.
   *
   * @param {object} params
   * @param {string} params.postId
   * @param {string} params.backtestId
   * @param {string} [params.replyId]  carried for the cache key only — the source endpoint keys
   *                                   on backtestId alone, and a reply's strategy has its own.
   * @returns {Promise<string|null>} the Python source, or null when JQ serves none.
   * @throws {GeoBlockedError} when the request leaves mainland China — see the header. Never
   *         swallowed: "no source" and "we could not ask" must not look alike.
   */
  async fetch(params) {
    const { postId, backtestId, replyId = '' } = params;
    if (!postId || !backtestId) throw new Error('postId and backtestId are required');

    const cacheKey = `${postId}/${backtestId}/${replyId}`;
    if (this._cache.has(cacheKey)) return this._cache.get(cacheKey);

    const json = await jq.jqJson(SOURCE_URL(backtestId));
    // JQ reports "gone"/"not yours" as a code rather than an HTTP status, and both mean the same
    // thing to a caller: there is no source to have. `10001`/`20000` are the two seen in the wild
    // (see strategy-fetch.js), but any missing `data.source` reads the same way.
    const source = (json && json.data && json.data.source) || null;
    if (source) this._cache.set(cacheKey, source);
    return source;
  }
}

module.exports = { StrategyFetcher };
