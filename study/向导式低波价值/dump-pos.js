// u-1 helper (read-only, NO backtest): dump the stored base TRAIN run's 持仓 (positionInfo) and
// 交易 (transactionInfo) tabs. Pattern copied from study/价值红利多腿/dump-pos.js; output files are
// written beside this script, keyed by the backtestId, so no other family's dumps are overwritten.
// Usage: node -e "require('./study/向导式低波价值/dump-pos.js').main()" -- <backtestId>
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';

async function main() {
  const bid = process.argv.slice(1).find(a => /^[a-f0-9]{32}$/.test(a));
  if (!bid) throw new Error('need a 32-hex backtestId');
  const browser = await chromium.connectOverCDP(CDP);
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    const get = u => page.evaluate(async (u) => (await fetch(u, { credentials: 'include' })).text(), u);
    async function pageAll(ep, key) {
      let off = 0, dateOff = null, seen = new Set(), all = [], raw0 = null;
      for (let i = 0; i < 200; i++) {
        const q = dateOff ? `&offset=${off}&dateOffset=${dateOff}` : '';
        const txt = await get(`/algorithm/backtest/${ep}?backtestId=${bid}${q}&ajax=1`);
        if (raw0 === null) raw0 = txt.slice(0, 300);
        let j; try { j = JSON.parse(txt); } catch (e) { console.log(ep, 'non-JSON:', txt.slice(0, 200)); break; }
        const arr = (j.data && j.data[key]) || [];
        let added = 0;
        for (const r of arr) { const k = JSON.stringify(r); if (!seen.has(k)) { seen.add(k); all.push(r); added++; } }
        if (!arr.length || !added) break;
        off = all.length;
        dateOff = arr[arr.length - 1].tradeDate || arr[arr.length - 1].date;
      }
      if (!all.length) console.log(ep, 'first response:', raw0);
      return all;
    }
    const P = await pageAll('positionInfo', 'position');
    const T = await pageAll('transactionInfo', 'transaction');
    const tag = bid.slice(0, 8);
    fs.writeFileSync(path.join(__dirname, `pos-${tag}.json`), JSON.stringify(P));
    fs.writeFileSync(path.join(__dirname, `tx-${tag}.json`), JSON.stringify(T));
    const dates = [...new Set(P.map(r => r.date))].sort();
    console.log('positions', P.length, 'days', dates.length, dates[0], dates[dates.length - 1], 'tx', T.length);
  } finally {
    try { await browser.close(); } catch (e) { /* detach only */ }
  }
}
module.exports = { main };
