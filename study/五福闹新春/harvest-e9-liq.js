// node -e "require('./study/五福闹新春/harvest-e9-liq.js')"
// Pages /algorithm/backtest/log for the q-e9-liq run and saves the full log plus the
// per-leg LIQFLOOR census separately. Same pagination pattern as harvest-e8-3.js.
const fs = require('fs');
const { chromium } = require('playwright');
const ALG = '50e0d4abd94bb4a7176c3141f1765af1';
const FULL = 'data/autostudy-logs/wufu-q-e9-liq.full.txt';
const LIQ = 'data/autostudy-logs/wufu-q-e9-liq.liqfloor.txt';

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
    console.log('total log entries fetched:', all.length);
    fs.writeFileSync(FULL, all.join('\n') + '\n');
    // LIQFLOOR lines may be embedded inside a multi-line log entry — split first.
    const lines = all.join('\n').split('\n');
    const liq = lines.filter(l => l.includes('LIQFLOOR'));
    fs.writeFileSync(LIQ, liq.join('\n') + '\n');
    console.log('LIQFLOOR lines:', liq.length, '->', LIQ);
    const err = lines.filter(l => /Traceback|NameError|KeyError|TypeError|AttributeError/.test(l));
    console.log('error-looking lines:', err.length);
    err.slice(0, 10).forEach(l => console.log('  ', l.slice(0, 200)));
  } finally {
    try { await browser.close(); } catch { /* detach only */ }
  }
})();
