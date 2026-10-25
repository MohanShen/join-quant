// node -e "require('./study/五福闹新春/harvest-e9-weak.js')"
// Pages /algorithm/backtest/log for the q-e9-weak run and dumps the full log.
// The variant disables the weak switch, but L818 still prints the UNMODIFIED rule's inputs
// every day: 「📊 【走弱期判断】低于MA10: n/4, 站上MA10: m/4」. That is the census.
const fs = require('fs');
const { chromium } = require('playwright');
const ALG = 'f32d4565c879f0fe297dd11e1463a43b';
const OUT = 'data/autostudy-logs/wufu-q-e9-weak.full.txt';

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
      for (let i = 0; i < 4000; i++) {
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
    const census = all.filter(l => l.includes('低于MA'));
    console.log('census lines (低于MA):', census.length);
    console.log(census.slice(0, 3).join('\n'));
  } finally {
    try { await browser.close(); } catch {}
  }
})();
