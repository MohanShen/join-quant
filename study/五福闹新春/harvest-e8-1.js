// node -e "require('./study/五福闹新春/harvest-e8-1.js')"
// Pages /algorithm/backtest/log for the q-e8-1 run and writes every WEAKHOLD line out.
// The wrapper's single call returned only 100 lines, so the endpoint pages by offset.
const fs = require('fs');
const { chromium } = require('playwright');
const ALG = 'e32233fda48869330cb3e7d0f3f79be6';
const OUT = 'data/autostudy-logs/wufu-q-e8-1.weakhold.txt';

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
      for (let i = 0; i < 2000; i++) {
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
    const weak = all.filter(l => l.includes('WEAKHOLD'));
    fs.writeFileSync(OUT, weak.join('\n') + '\n');
    console.log('WEAKHOLD lines:', weak.length, '->', OUT);
    fs.writeFileSync('data/autostudy-logs/wufu-q-e8-1.full.txt', all.join('\n') + '\n');
  } finally {
    try { await browser.close(); } catch {}
  }
})();
