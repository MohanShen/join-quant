// q-e9-sleeve-attrib helper (read-only, no backtest): save the reference run's 持仓 (positionInfo)
// and 交易 (transactionInfo) tabs. These give each day's per-name close price/value from the run itself,
// so open positions are marked at the run's own 2024-12-31 close.
// Usage: node -e "require('./study/价值红利多腿/dump-pos.js').main()" -- <backtestId>
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';

async function main() {
  const bid = process.argv.slice(1).find(a => /^[a-f0-9]{32}$/.test(a));
  const browser = await chromium.connectOverCDP(CDP);
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    const get = u => page.evaluate(async (u) => (await fetch(u, { credentials: 'include' })).text(), u);
    // Both tabs page; walk `offset` by the returned length until an empty page (cap 100 pages).
    async function pageAll(ep, key) {
      // The page's own JS pages with &offset=<n>&dateOffset=<last row date>. Rows are deduped by
      // their full JSON, so an overlapping page cannot double-count.
      let off = 0, dateOff = null, seen = new Set(), all = [];
      for (let i = 0; i < 200; i++) {
        const q = dateOff ? `&offset=${off}&dateOffset=${dateOff}` : '';
        const j = JSON.parse(await get(`/algorithm/backtest/${ep}?backtestId=${bid}${q}&ajax=1`));
        const arr = (j.data && j.data[key]) || [];
        let added = 0;
        for (const r of arr) { const k = JSON.stringify(r); if (!seen.has(k)) { seen.add(k); all.push(r); added++; } }
        if (!arr.length || !added) break;
        off = all.length;
        dateOff = arr[arr.length - 1].tradeDate || arr[arr.length - 1].date;
      }
      return all;
    }
    const P = await pageAll('positionInfo', 'position');
    const T = await pageAll('transactionInfo', 'transaction');
    fs.writeFileSync(path.join(__dirname, 'pos-q-e9-s4-pit.json'), JSON.stringify(P));
    fs.writeFileSync(path.join(__dirname, 'tx-q-e9-s4-pit.json'), JSON.stringify(T));
    const dates = [...new Set(P.map(r => r.date))].sort();
    console.log('positions', P.length, 'days', dates.length, dates[0], dates[dates.length - 1], 'tx', T.length);
  } finally {
    try { await browser.close(); } catch (e) { /* detach only */ }
  }
}
module.exports = { main };
