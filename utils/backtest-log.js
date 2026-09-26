/**
 * backtest-log.js — read a backtest's 日志 and 错误 tabs.
 *
 * ## This was believed impossible
 *
 * CLAUDE.md states: "The backtest log is not retrievable via the API
 * (`/algorithm/backtest/log` returns empty). A probe must encode its answer as a marker trade, and
 * always needs a control." That constraint shaped `study/_probes/` entirely — every probe had to
 * smuggle its answer out through trades because nothing could read what the strategy printed.
 *
 * It is wrong, and narrowly so. The BARE url really does fail:
 *
 *     /algorithm/backtest/log?backtestId=X                      -> 400, 0 bytes
 *     /algorithm/backtest/log?backtestId=X&offset=0&limit=50&ajax=1 -> 200, 23747 bytes, logArr[]
 *
 * The query parameters are the whole difference. Whoever probed it once, probed the short form,
 * and the finding hardened into a rule.
 *
 * ## What each endpoint gives
 *
 *   log   — the 日志 tab: every `log.info/warn/error` line the strategy emitted, with timestamps.
 *   error — the 错误 tab: `{ state, logArr }`, empty for a clean run. This is where a Python
 *           traceback lands when a strategy dies mid-run.
 *
 * ⚠ Both are keyed on `backtestId`, which JoinQuant RE-MINTS on every request (CLAUDE.md). So an
 * id must be resolved and used in the same breath; never store one. `forAlgorithm()` does that
 * resolution.
 *
 * Usage:
 *   node utils/backtest-log.js <backtestId>            # log + error
 *   node utils/backtest-log.js <backtestId> --errors   # error tab only
 *   node utils/backtest-log.js --algorithm <algId>     # resolve the id first, then fetch
 *   node utils/backtest-log.js <backtestId> --grep 'Traceback|Error'
 */

const { chromium } = require('playwright');

const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';

async function withPage(fn) {
  const browser = await chromium.connectOverCDP(CDP);
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    return await fn(page);
  } finally {
    // NEVER close the page — it holds the CDP cookie context. Detach only.
    try { await browser.close(); } catch { /* detach is best-effort */ }
  }
}

/**
 * Fetch both tabs for one backtest.
 * @returns {{log:string[], error:string[], state:string|null, err:string|null}}
 */
async function fetchLog(backtestId, { limit = 2000 } = {}) {
  return withPage(page => page.evaluate(async ({ bid, limit }) => {
    const get = async (u) => {
      try {
        const r = await fetch(u, { credentials: 'include' });
        const t = await r.text();
        try { return JSON.parse(t); } catch { return { __raw: t.slice(0, 300) }; }
      } catch (e) { return { __err: e.message }; }
    };
    // ⚠ The parameters are load-bearing — without them this endpoint 400s, which is how it came
    // to be documented as "returns empty".
    const lg = await get(`/algorithm/backtest/log?backtestId=${bid}&offset=0&limit=${limit}&ajax=1`);
    const er = await get(`/algorithm/backtest/error?backtestId=${bid}&ajax=1`);
    return {
      state: (lg.data && lg.data.state) || null,
      log: (lg.data && lg.data.logArr) || [],
      error: (er.data && er.data.logArr) || [],
      err: lg.__err || er.__err || (lg.__raw ? `unparsed: ${lg.__raw}` : null),
    };
  }, { bid: backtestId, limit }));
}

/**
 * Resolve an algorithm's newest backtest id and fetch its logs.
 *
 * Ids are re-minted per request, so resolution and use must happen together — the same reason
 * `captureSeries` resolves from the algorithm's own buildList rather than storing an id.
 */
async function forAlgorithm(algorithmId, opts = {}) {
  const bid = await withPage(page => page.evaluate(async (alg) => {
    const t = await (await fetch(`/algorithm/backtest/buildList?algorithmId=${alg}`,
      { credentials: 'include' })).text();
    const ids = [...new Set([...t.matchAll(/backtestId[=":\s]+([a-f0-9]{32})/g)].map(m => m[1]))];
    return ids[0] || null;
  }, algorithmId));
  if (!bid) return { err: `no backtest found for algorithm ${algorithmId}`, log: [], error: [] };
  return { backtestId: bid, ...(await fetchLog(bid, opts)) };
}

/** Lines that look like a failure, for a quick verdict without reading the whole log. */
function failures(lines) {
  const re = /Traceback|Error|Exception|错误|失败|无法|NameError|KeyError|ValueError|TypeError|IndexError|AttributeError/i;
  return (lines || []).filter(l => re.test(String(l)));
}

module.exports = { fetchLog, forAlgorithm, failures };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const arg = n => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : null; };
  const alg = arg('--algorithm');
  const bid = argv.find(a => /^[a-f0-9]{32}$/.test(a));
  const grep = arg('--grep');

  if (!alg && !bid) {
    console.error('usage: node utils/backtest-log.js <backtestId> | --algorithm <algorithmId>');
    process.exit(1);
  }

  (async () => {
    const r = alg ? await forAlgorithm(alg) : await fetchLog(bid);
    if (r.err) { console.error(`[log] ${r.err}`); process.exit(1); }
    console.log(`[log] backtestId ${r.backtestId || bid}  state=${r.state}  ` +
                `${r.log.length} log line(s), ${r.error.length} error line(s)`);

    if (r.error.length) {
      console.log('\n── 错误 ──');
      for (const l of r.error) console.log('  ' + l);
    }
    if (argv.includes('--errors')) process.exit(0);

    const fails = failures(r.log);
    if (fails.length) {
      console.log(`\n── failure-shaped lines in 日志 (${fails.length}) ──`);
      for (const l of fails.slice(0, 40)) console.log('  ' + String(l).slice(0, 200));
    }
    if (grep) {
      const re = new RegExp(grep, 'i');
      const hits = r.log.filter(l => re.test(String(l)));
      console.log(`\n── /${grep}/ (${hits.length}) ──`);
      for (const l of hits.slice(0, 40)) console.log('  ' + String(l).slice(0, 200));
    } else if (!fails.length) {
      console.log('\n── 日志 head ──');
      for (const l of r.log.slice(0, 12)) console.log('  ' + String(l).slice(0, 180));
      if (r.log.length > 12) console.log(`  …and ${r.log.length - 12} more`);
    }
  })().catch(e => { console.error('FATAL', e.message); process.exit(1); });
}
