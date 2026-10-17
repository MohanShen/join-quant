// node -e "require('./study/五福闹新春/harvest-e8-3.js')"
// Clone of harvest-e8-7.js for the q-e8-3 run. Pages /algorithm/backtest/log and saves
// the full log + the LIQFLOOR and WEAKHOLD lines separately.
const fs = require('fs');
const { chromium } = require('playwright');
const ALG = 'eef76ddece02ddaf8ef2eeaec0a1230d';
const FULL = 'data/autostudy-logs/wufu-q-e8-3.full.txt';
const LIQ = 'data/autostudy-logs/wufu-q-e8-3.liqfloor.txt';
const WH = 'data/autostudy-logs/wufu-q-e8-3.weakhold.txt';

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
    const liq = all.filter(l => l.includes('LIQFLOOR'));
    fs.writeFileSync(LIQ, liq.join('\n') + '\n');
    const weak = all.filter(l => l.includes('WEAKHOLD'));
    fs.writeFileSync(WH, weak.join('\n') + '\n');
    console.log('LIQFLOOR lines:', liq.length, '->', LIQ);
    console.log('WEAKHOLD lines:', weak.length, '->', WH);
  } finally {
    try { await browser.close(); } catch {}
  }
})();
