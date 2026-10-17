// node -e "require('./study/五福闹新春/harvest-e8-2.js')"
// Pages /algorithm/backtest/log for BOTH the q-e8-2 (13:12) run and the baseline-e6
// (13:10) run and saves each full log. Free: the account retains the algorithms and
// each still serves its log. No backtest is started.
const fs = require('fs');
const { chromium } = require('playwright');

const RUNS = [
  { tag: 'q-e8-2', alg: '7402984cef2e7513efa2879a284f764f' },   // this round's 13:12 variant
  { tag: 'base-e6', alg: '3169335da3f185c01cfb0648c9188d17' },  // wufu-q-e6-0 = baseline-e6 (129.29/51.51/1.99/13.96)
];

(async () => {
  const browser = await chromium.connectOverCDP(process.env.JQ_CDP_URL || 'http://localhost:9225');
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    for (const { tag, alg } of RUNS) {
      const bid = await page.evaluate(async (a) => {
        const t = await (await fetch(`/algorithm/backtest/buildList?algorithmId=${a}`, { credentials: 'include' })).text();
        const rows = (t.match(/class="backtest-tr"/g) || []).length;
        const ids = [...new Set([...t.matchAll(/backtestId[=":\s]+([a-f0-9]{32})/g)].map(m => m[1]))];
        return { rows, bytes: t.length, id: ids[0] || null };
      }, alg);
      console.log(`${tag}: buildList rows=${bid.rows} bytes=${bid.bytes} backtestId=${bid.id}`);
      if (!bid.id) { console.log(`${tag}: NO backtestId -- reaped by JQ, log unavailable`); continue; }
      const all = await page.evaluate(async (b) => {
        const out = [];
        let offset = 0;
        for (let i = 0; i < 4000; i++) {
          const r = await fetch(`/algorithm/backtest/log?backtestId=${b}&offset=${offset}&limit=2000&ajax=1`,
            { credentials: 'include' });
          const j = await r.json().catch(() => null);
          const arr = (j && j.data && j.data.logArr) || [];
          if (!arr.length) break;
          out.push(...arr.map(x => (typeof x === 'string' ? x : JSON.stringify(x))));
          offset += arr.length;
          if (arr.length < 2) break;
        }
        return out;
      }, bid.id);
      const out = `data/autostudy-logs/wufu-${tag}.full.txt`;
      fs.writeFileSync(out, all.join('\n') + '\n');
      console.log(`${tag}: ${all.length} log lines -> ${out}`);
    }
  } finally {
    try { await browser.close(); } catch {}
  }
})();
