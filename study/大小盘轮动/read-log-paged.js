// Page the 日志 tab of an algorithm's newest backtest, 100 lines per call (the endpoint ignores
// `limit`), until a short page. Writes the whole log to OUT. Usage (from repo root):
//   node -e "require('./study/大小盘轮动/read-log-paged.js').run('<algorithmId>', '<outFile>')"
const { chromium } = require('playwright');
const fs = require('fs');
exports.run = async (alg, out) => {
  const browser = await chromium.connectOverCDP(process.env.JQ_CDP_URL || 'http://localhost:9225');
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    const r = await page.evaluate(async (alg) => {
      const t = await (await fetch(`/algorithm/backtest/buildList?algorithmId=${alg}`, { credentials: 'include' })).text();
      const ids = [...new Set([...t.matchAll(/backtestId[=":\s]+([a-f0-9]{32})/g)].map(m => m[1]))];
      const bid = ids[0];
      const all = []; const pages = [];
      for (let off = 0; off < 20000; off += 100) {
        const j = JSON.parse(await (await fetch(`/algorithm/backtest/log?backtestId=${bid}&offset=${off}&limit=100&ajax=1`, { credentials: 'include' })).text());
        const arr = (j.data && j.data.logArr) || [];
        pages.push(arr.length); all.push(...arr);
        if (arr.length < 100) break;
      }
      const er = JSON.parse(await (await fetch(`/algorithm/backtest/error?backtestId=${bid}&ajax=1`, { credentials: 'include' })).text());
      return { bid, pages, all, err: (er.data && er.data.logArr) || [] };
    }, alg);
    fs.writeFileSync(out, r.all.join('\n'));
    console.log('bid', r.bid, 'pages', r.pages.join(','), 'lines', r.all.length, 'errLines', r.err.length);
    if (r.err.length) console.log(r.err.slice(0, 10).join('\n'));
  } finally { try { await browser.close(); } catch {} }
};
