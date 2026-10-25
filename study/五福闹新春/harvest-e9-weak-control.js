// node -e "require('./study/五福闹新春/harvest-e9-weak-control.js')"
// FREE: the CONTROL's own backtest log. Its backtestId is retained in the stored epoch-9 TRAIN
// curve (data/series/2026-07-08_…17b3b439__train__e9.json), so the weak/normal census and the
// 511880 fallback days can be read off the UNMODIFIED book rather than simulated.
const fs = require('fs');
const { chromium } = require('playwright');
const BID = '88a08ffb468b1925e69c52175f13f662';
const OUT = 'data/autostudy-logs/wufu-e9-control-17b3b439.full.txt';

(async () => {
  const browser = await chromium.connectOverCDP(process.env.JQ_CDP_URL || 'http://localhost:9225');
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
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
    }, { bid: BID });
    console.log('control log lines fetched:', all.length);
    if (!all.length) { console.log('EMPTY — the control log is no longer retrievable'); return; }
    fs.mkdirSync('data/autostudy-logs', { recursive: true });
    fs.writeFileSync(OUT, all.join('\n') + '\n');
    console.log('->', OUT);
  } finally {
    try { await browser.close(); } catch {}
  }
})();
