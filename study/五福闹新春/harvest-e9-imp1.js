// node -e "require('./study/五福闹新春/harvest-e9-imp1.js')"
// Pages /algorithm/backtest/log for the imp-e9-1 run and dumps the full 日志 tab.
// Census sources in the variant:
//   - the VERBATIM copied rule prints 「📊 【走弱期判断】低于MA10: n/4, 站上MA10: m/4」 every day
//     plus 「最终状态: 走弱期=True/False (已持续 k/20 个交易日)」
//   - insertion 4 prints `IMP-E9-1-CENSUS WEAK pool=<n> names=<...>` / `... NORMAL pool=<n>`
//     at 13:10, i.e. the branch the SLEEVE actually took that day.
const fs = require('fs');
const { chromium } = require('playwright');
const ALG = '369a94a4a9669c4fb7e13f90f808c634';
const OUT = 'data/autostudy-logs/wufu-imp-e9-1.full.txt';

(async () => {
  const browser = await chromium.connectOverCDP(process.env.JQ_CDP_URL || 'http://localhost:9225');
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    const bid = await page.evaluate(async (alg) => {
      const t = await (await fetch(`/algorithm/backtest/buildList?algorithmId=${alg}`, { credentials: 'include' })).text();
      const ids = [...new Set([...t.matchAll(/backtestId[=":\s]+([a-f0-9]{32})/g)].map(m => m[1]))];
      return ids[0] || null;
    }, ALG);
    console.log('backtestId', bid);
    const all = await page.evaluate(async ({ bid }) => {
      const out = [];
      let offset = 0;
      for (let i = 0; i < 6000; i++) {
        const r = await fetch(`/algorithm/backtest/log?backtestId=${bid}&offset=${offset}&limit=2000&ajax=1`,
          { credentials: 'include' });
        const j = await r.json().catch(() => null);
        const arr = (j && j.data && j.data.logArr) || [];
        if (!arr.length) break;
        out.push(...arr.map(x => (typeof x === 'string' ? x : JSON.stringify(x))));
        offset += arr.length;
        if (arr.length < 2) break;
      }
      return out;
    }, { bid });
    console.log('total log lines fetched:', all.length);
    fs.mkdirSync('data/autostudy-logs', { recursive: true });
    fs.writeFileSync(OUT, all.join('\n') + '\n');
    console.log('->', OUT);
    console.log('rule lines (低于MA):', all.filter(l => l.includes('低于MA')).length);
    console.log('branch lines (IMP-E9-1-CENSUS):', all.filter(l => l.includes('IMP-E9-1-CENSUS')).length);
    console.log('final-state lines (最终状态):', all.filter(l => l.includes('最终状态')).length);
  } finally {
    try { await browser.close(); } catch {}
  }
})();
