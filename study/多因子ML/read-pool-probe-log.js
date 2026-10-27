// node -e "require('./study/多因子ML/read-pool-probe-log.js')"
//
// Paged reader for the q-e9-pool probe's 日志 tab.
// ⚠ /algorithm/backtest/log caps a page at 100 lines REGARDLESS of &limit — a single limit=2000
// call returns only the first page, which is how a previous executor was misled. So this walks
// &offset= until a page comes back short or stops adding new lines.
// utils/backtest-log.js is used for the 错误 tab and for the backtestId resolution.
const { chromium } = require('playwright');

const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';
const ALG = process.env.PROBE_ALG || 'fca6b0f408f3483956aa3a68a29ee70a';

(async () => {
  const browser = await chromium.connectOverCDP(CDP);
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];

    const out = await page.evaluate(async (alg) => {
      const txt = async (u) => (await fetch(u, { credentials: 'include' })).text();
      const json = async (u) => { try { return JSON.parse(await txt(u)); } catch { return null; } };

      // ids are re-minted per request: resolve and use in the same breath
      const bl = await txt(`/algorithm/backtest/buildList?algorithmId=${alg}`);
      const ids = [...new Set([...bl.matchAll(/backtestId[=":\s]+([a-f0-9]{32})/g)].map(m => m[1]))];
      const bid = ids[0];
      if (!bid) return { err: 'no backtestId' };

      const lines = [];
      const seen = new Set();
      let state = null;
      for (let off = 0; off < 5000; off += 100) {
        const r = await json(`/algorithm/backtest/log?backtestId=${bid}&offset=${off}&limit=100&ajax=1`);
        const arr = (r && r.data && r.data.logArr) || [];
        if (r && r.data && r.data.state != null) state = r.data.state;
        let added = 0;
        for (const l of arr) { const s = String(l); if (!seen.has(s)) { seen.add(s); lines.push(s); added++; } }
        if (arr.length === 0 || added === 0) break;
      }
      const er = await json(`/algorithm/backtest/error?backtestId=${bid}&ajax=1`);
      return { bid, state, lines, error: (er && er.data && er.data.logArr) || [] };
    }, ALG);

    if (out.err) { console.error(out.err); process.exitCode = 1; return; }
    console.log(`[log] backtestId=${out.bid} state=${out.state} lines=${out.lines.length} errors=${out.error.length}`);
    for (const l of out.error) console.log('ERRTAB  ' + l);
    for (const l of out.lines) console.log(l);
  } finally {
    try { await browser.close(); } catch { /* detach only */ }
  }
})().catch(e => { console.error('FATAL', e.message); process.exitCode = 1; });
