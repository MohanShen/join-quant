// node -e "require('./study/五福闹新春/harvest-e8-7.js')"
// Pages /algorithm/backtest/log for the q-e8-7 run and saves the full log + WEAKHOLD lines.
const fs = require('fs');
const { chromium } = require('playwright');
const ALG = 'f810355e6f4c508f9c468ddbbda9dc57';
const OUT = 'data/autostudy-logs/wufu-q-e8-7.weakhold.txt';
const FULL = 'data/autostudy-logs/wufu-q-e8-7.full.txt';

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
    fs.writeFileSync(FULL, all.join('\n') + '\n');
    const weak = all.filter(l => l.includes('WEAKHOLD'));
    fs.writeFileSync(OUT, weak.join('\n') + '\n');
    console.log('WEAKHOLD lines:', weak.length, '->', OUT);
  } finally {
    try { await browser.close(); } catch {}
  }
})();
