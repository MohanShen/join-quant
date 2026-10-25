// node -e "require('./study/五福闹新春/harvest-e9-leg.js')"
// Pages /algorithm/backtest/log for the q-e9-leg run and censuses the structural riders:
//   - strategy-1 (小市值) trade count — MUST be 0, else the build failed
//   - the ETF sleeve's holding days / cash days
//   - 走弱/震荡 branch day counts
const fs = require('fs');
const { chromium } = require('playwright');
const ALG = '4c22e36535039eccab3c72a887b50519';
const OUT = 'data/autostudy-logs/q-e9-leg.full.txt';

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
    fs.writeFileSync(OUT, all.join('\n') + '\n');
    console.log('total log lines:', all.length, '->', OUT);
  } finally {
    try { await browser.close(); } catch {}
  }
})();
