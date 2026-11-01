// q-e9-div-only helper (read-only, no backtest): resolve the run's backtestId from its algorithmId and
// save its 持仓 / 交易 tabs + full 日志 to *-q-e9-div-only.*. Same method as dump-pb-only.js.
// Usage: node -e "require('./study/价值红利多腿/dump-div-only.js').main('<algorithmId>')"
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const { pageAll: pageLog } = require('../小市值/pagelog.js');
const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';
const TAG = 'q-e9-div-only';

async function main(alg) {
  const browser = await chromium.connectOverCDP(CDP);
  let bid;
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    const get = u => page.evaluate(async (u) => (await fetch(u, { credentials: 'include' })).text(), u);
    const bl = await get(`/algorithm/backtest/buildList?algorithmId=${alg}`);
    const ids = [...new Set([...bl.matchAll(/backtestId[=":\s]+([a-f0-9]{32})/g)].map(m => m[1]))];
    bid = ids[0];
    if (!bid) throw new Error('no backtest for ' + alg);
    async function pageAll(ep, key) {
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
    fs.writeFileSync(path.join(__dirname, `pos-${TAG}.json`), JSON.stringify(P));
    fs.writeFileSync(path.join(__dirname, `tx-${TAG}.json`), JSON.stringify(T));
    console.log('positions', P.length, 'tx', T.length);
  } finally {
    try { await browser.close(); } catch (e) { /* detach only */ }
  }
  const r = await pageLog(bid);
  fs.writeFileSync(path.join(__dirname, `log-${TAG}.txt`), r.lines.map(String).join('\n') + '\n');
  console.log('log state=' + r.state + ' pages=' + r.pages + ' lines=' + r.lines.length);
}
module.exports = { main };
