// q-e9-atr-attrib: per-ETF P&L attribution from the base run's own 卖出 log lines.
// Input: the paged 日志 of base backtest 5e3c1028cd652f9070ffce1ca79cbeb7 (e79e9884, epoch 9 TRAIN),
// saved by study/小市值/pagelog.js to study/突破ATR趋势跟踪/atr-log-base.txt.
// Usage: node study/突破ATR趋势跟踪/attrib.js [logfile]
const fs = require('fs');
const path = require('path');
const file = process.argv[2] || path.join(__dirname, 'atr-log-base.txt');
const lines = fs.readFileSync(file, 'utf8').split('\n');

const opens = {}; // sym -> [{date, qty, px}]
const trades = [];
for (const l of lines) {
  let m = l.match(/\[(\d{4}-\d\d-\d\d)\] 开仓 (\S+) 数量=(\d+) 入场价~([\d.]+)/);
  if (m) { (opens[m[2]] = opens[m[2]] || []).push({ date: m[1], qty: +m[3], px: +m[4] }); continue; }
  m = l.match(/\[(\d{4}-\d\d-\d\d)\] 卖出 (\S+) @([\d.]+) 数量=(\d+) 盈亏=(-?[\d.]+) 原因=(\S+)/);
  if (m) {
    const o = (opens[m[2]] || []).shift();
    trades.push({ sym: m[2], entry: o && o.date, entryPx: o && o.px, exit: m[1], exitPx: +m[3],
      qty: +m[4], pnl: +m[5], reason: m[6] });
  }
}
const stillOpen = Object.entries(opens).filter(([, v]) => v.length);
const equity = +((lines.find(l => /期末权益/.test(l)) || '').match(/([\d.]+)\s*$/) || [])[1];

const net = trades.reduce((s, t) => s + t.pnl, 0);
const by = {};
for (const t of trades) {
  const b = by[t.sym] = by[t.sym] || { n: 0, net: 0, win: 0, loss: 0, sep: 0 };
  b.n++; b.net += t.pnl; if (t.pnl > 0) b.win += t.pnl; else b.loss += t.pnl;
  if (t.entry && t.entry.startsWith('2024-09')) b.sep += t.pnl;
}
const gross = trades.filter(t => t.pnl > 0).reduce((s, t) => s + t.pnl, 0);
const sepTot = trades.filter(t => t.entry && t.entry.startsWith('2024-09')).reduce((s, t) => s + t.pnl, 0);

console.log(`trades=${trades.length} stillOpen=${stillOpen.length} net=${net.toFixed(2)} gross_wins=${gross.toFixed(2)}`);
console.log('sym\tn\tnet\tnet%\twins\twins%\tlosses\tsep_entry_pnl');
const rows = Object.entries(by).sort((a, b) => b[1].net - a[1].net);
for (const [s, b] of rows) {
  console.log([s, b.n, b.net.toFixed(2), (100 * b.net / net).toFixed(1), b.win.toFixed(2),
    (100 * b.win / gross).toFixed(1), b.loss.toFixed(2), b.sep.toFixed(2)].join('\t'));
}
console.log(`top1 share of net=${(100 * rows[0][1].net / net).toFixed(1)}%  top2=${(100 * (rows[0][1].net + rows[1][1].net) / net).toFixed(1)}%`);
console.log(`Sep(9/25 entries) pnl=${sepTot.toFixed(2)} = ${(100 * sepTot / net).toFixed(1)}% of net, ${(sepTot / 1e4).toFixed(2)}% of capital`);
console.log('9/25 sizes:', trades.filter(t => t.entry === '2024-09-25')
  .map(t => `${t.sym} ${t.qty}x${t.entryPx}=${(t.qty * t.entryPx).toFixed(0)}`).join('; '));
// Reconcile: logged pnl uses the logged exit price (day_open), not the fill, and excludes fees.
const recomputed = trades.reduce((s, t) => s + t.qty * (t.exitPx - t.entryPx), 0);
const ledger = 0.2845 * 1e6;
console.log(`logged net=${net.toFixed(2)} | qty*(exit-entry) recomputed=${recomputed.toFixed(2)} | ledger 28.45%*1e6=${ledger.toFixed(0)} | log 期末权益-1e6=${(equity - 1e6).toFixed(2)}`);
console.log(`gap logged - realised(equity) = ${(net - (equity - 1e6)).toFixed(2)} (${(100 * (net - (equity - 1e6)) / 1e6).toFixed(2)}pp of capital)`);
