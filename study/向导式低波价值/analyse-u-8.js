// analyse-u-8.js — u-8 Leg A (low-vol 6) vs Leg B (PE-pool EW), both on the rebalance harness.
// Reads the two stored TRAIN curves + log-u-8a.txt / log-u-8b.txt. Prints: curve metrics, daily corr,
// per-holding-period returns (close before rebalance d_i -> close before d_{i+1}), win share,
// turnover / order counts, per-date breadth + sector mix, cash ratio.
const fs = require('fs');
const path = require('path');
const S = require('../../utils/backtest-series');
const ROOT = path.join(__dirname, '..', '..');
const cur = k => JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series', k + '.json'), 'utf8'));
const A = cur('study_向导式低波价值_variants_u-8a__train__e9');
const B = cur('study_向导式低波价值_variants_u-8b__train__e9');
const kv = s => Object.fromEntries([...s.matchAll(/(\w+)=(\S+)/g)].map(m => [m[1], m[2]]));
const readLog = f => {
  const L = fs.readFileSync(path.join(__dirname, f), 'utf8').split('\n');
  const reb = [], ord = { filled: 0, refused: 0 };
  for (const l of L) {
    if (l.includes('REBAL ')) reb.push(kv(l.split('REBAL ')[1]));
    if (l.includes('RBORD ')) { if (/filled=[1-9]/.test(l)) ord.filled++; else ord.refused++; }
  }
  return { reb, ord };
};
const la = readLog('log-u-8a.txt'), lb = readLog('log-u-8b.txt');

function metrics(C) {
  const r = S.dailyReturns(C.cum).filter(Number.isFinite);
  const m = r.reduce((s, x) => s + x, 0) / r.length;
  const sd = Math.sqrt(r.reduce((s, x) => s + (x - m) ** 2, 0) / (r.length - 1));
  let peak = 1, dd = 0;
  for (const c of C.cum) { const v = 1 + c / 100; peak = Math.max(peak, v); dd = Math.max(dd, 1 - v / peak); }
  return { final: C.cum[C.cum.length - 1], vol: sd * Math.sqrt(250), sharpe: (m * 250 - 0.04) / (sd * Math.sqrt(250)), maxdd: dd * 100 };
}
const ma = metrics(A), mb = metrics(B);
console.log('curve A', JSON.stringify(ma));
console.log('curve B', JSON.stringify(mb));
console.log('daily corr', S.correlate(A, B));

// per period
const nav = C => { const m = new Map(); C.dates.forEach((d, i) => m.set(d, 1 + C.cum[i] / 100)); return m; };
const na = nav(A), nb = nav(B);
const dates = A.dates;
const before = d => { const i = dates.indexOf(d); return i <= 0 ? null : dates[i - 1]; };
const rd = la.reb.map(o => o.date);
const rdB = lb.reb.map(o => o.date);
console.log('rebalance dates A', rd.length, 'B', rdB.length, 'same:', JSON.stringify(rd) === JSON.stringify(rdB));
let win = 0, n = 0;
const rows = [];
for (let i = 0; i < rd.length; i++) {
  const s = before(rd[i]);
  const e = i + 1 < rd.length ? before(rd[i + 1]) : dates[dates.length - 1];
  const g = (m, x) => (x === null ? 1 : m.get(x));
  const ra = (g(na, e) / g(na, s) - 1) * 100, rb = (g(nb, e) / g(nb, s) - 1) * 100;
  n++; if (ra > rb) win++;
  const a = la.reb[i], b = lb.reb[i];
  rows.push([rd[i], ra.toFixed(2), rb.toFixed(2), (ra - rb).toFixed(2), b.n_tgt, b.n_held, (100 * +b.cash / +b.tv).toFixed(1) + '%',
    (+a.turnover).toFixed(2), (+b.turnover).toFixed(2), a.sectors, b.sectors.split(';').slice(0, 3).join(';')].join('\t'));
}
console.log(['date', 'A%', 'B%', 'A-B', 'B_ntgt', 'B_held', 'B_cash', 'A_to', 'B_to', 'A_sectors', 'B_top3'].join('\t'));
rows.forEach(r => console.log(r));
console.log(`A beats B in ${win}/${n} periods = ${(100 * win / n).toFixed(1)}%`);
const sum = a => a.reduce((s, x) => s + x, 0);
const toA = la.reb.map(o => +o.turnover), toB = lb.reb.map(o => +o.turnover);
console.log('two-sided turnover sum (traded value / tv, incl. day-1 build): A', sum(toA).toFixed(2), 'B', sum(toB).toFixed(2),
  '| excl day 1: A', sum(toA.slice(1)).toFixed(2), 'B', sum(toB.slice(1)).toFixed(2));
console.log('orders filled / refused: A', la.ord.filled, '/', la.ord.refused, ' B', lb.ord.filled, '/', lb.ord.refused);
const nt = lb.reb.map(o => +o.n_tgt).sort((x, y) => x - y);
console.log('B pool size per date min', nt[0], 'median', nt[Math.floor(nt.length / 2)], 'max', nt[nt.length - 1]);
// sector frequency in Leg A across all dates
const sf = {};
for (const o of la.reb) for (const p of o.sectors.split(';')) { const [k, v] = p.split(':'); sf[k] = (sf[k] || 0) + +v; }
console.log('A sector slot-share over all dates:', Object.entries(sf).sort((x, y) => y[1] - x[1]).map(([k, v]) => `${k} ${(100 * v / (6 * la.reb.length)).toFixed(0)}%`).join(', '));
const sfb = {};
for (const o of lb.reb) for (const p of o.sectors.split(';')) { const [k, v] = p.split(':'); sfb[k] = (sfb[k] || 0) + +v; }
const totB = sum(Object.values(sfb));
console.log('B sector slot-share over all dates:', Object.entries(sfb).sort((x, y) => y[1] - x[1]).slice(0, 10).map(([k, v]) => `${k} ${(100 * v / totB).toFixed(0)}%`).join(', '));
