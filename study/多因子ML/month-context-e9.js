#!/usr/bin/env node
/**
 * q-e9-month, part 2 — ZERO-BACKTEST, READ-ONLY (writes nothing).
 *
 * Adjudicate the two readings of the sleeve's monthly contribution:
 *   "post-crash REBOUND harvester"  => the sleeve fires in months FOLLOWING a drawdown, and
 *                                      not much otherwise.
 *   "small-cap/size beta leg"       => the sleeve tracks a pure 小市值 book month by month,
 *                                      up in its up-months and down in its down-months.
 * Reference books, both already on disk: the harness benchmark curve stored with the base
 * (000300.XSHG) and 5a70adc1 (「关于小市值的不同筛选条件的差异研究」 — the purest 小市值
 * reference, and the peer whose SLEEVE-channel residual rho is highest, 0.6653).
 *
 * Same discipline: chain on the WHOLE series, slice by month afterwards, align by date,
 * day 1 included (that convention reproduces the ledger's annual_pct exactly: 156.71 / 58.95).
 */
const series = require('../../utils/backtest-series');

const base = series.load('2026-06-28_高质量稳定上涨策略-d02cde29__train__e9');
const vari = series.load('study_多因子ML_variants_q-e9-1__train__e9');
const ref = series.load('2026-05-22_关于小市值的不同筛选条件的差异研究-5a70adc1__train__e9');

function m2(dates, cum) {
  const r = series.dailyReturns(cum), out = new Map();
  dates.forEach((d, i) => Number.isFinite(r[i]) && out.set(d, r[i]));
  return out;
}
const B = m2(base.dates, base.cum), V = m2(vari.dates, vari.cum);
const M = m2(base.dates, base.benchCum), R = m2(ref.dates, ref.cum);

const dates = base.dates.filter(d => B.has(d) && V.has(d) && M.has(d) && R.has(d));
const months = [...new Set(dates.map(d => d.slice(0, 7)))].sort();
const comp = (ds, map) => ds.reduce((s, d) => s * (1 + map.get(d)), 1) - 1;

console.log(`overlap ${dates.length} days  ${dates[0]}..${dates[dates.length - 1]}  (base/variant/bench/5a70adc1)`);
console.log('month      sleeve%   bench%  smallcapRef%   prior-month ref%   sleeve sign vs ref sign');
const rows = [];
for (const k of months) {
  const ds = dates.filter(d => d.startsWith(k));
  const b = comp(ds, B), v = comp(ds, V), m = comp(ds, M), r = comp(ds, R);
  rows.push({ month: k, sleeve: (b - v) * 100, bench: m * 100, ref: r * 100 });
}
for (let i = 0; i < rows.length; i++) {
  const r = rows[i], prev = i ? rows[i - 1].ref : null;
  const agree = Math.sign(r.sleeve) === Math.sign(r.ref) ? 'same' : 'OPPOSITE';
  console.log([
    r.month,
    ((r.sleeve >= 0 ? '+' : '') + r.sleeve.toFixed(2)).padStart(9),
    ((r.bench >= 0 ? '+' : '') + r.bench.toFixed(2)).padStart(9),
    ((r.ref >= 0 ? '+' : '') + r.ref.toFixed(2)).padStart(14),
    (prev == null ? '—' : (prev >= 0 ? '+' : '') + prev.toFixed(2)).padStart(19),
    agree.padStart(26),
  ].join(''));
}
const corr = (a, b) => series.pearson(a, b);
const sl = rows.map(r => r.sleeve), bn = rows.map(r => r.bench), rf = rows.map(r => r.ref);
console.log('');
console.log(`monthly rho(sleeve, smallcapRef)        ${corr(sl, rf).toFixed(4)}   (n=12 months)`);
console.log(`monthly rho(sleeve, bench)              ${corr(sl, bn).toFixed(4)}`);
console.log(`monthly rho(sleeve, PRIOR month ref)    ${corr(sl.slice(1), rf.slice(0, -1)).toFixed(4)}   (n=11; the REBOUND reading predicts this is NEGATIVE and large)`);
console.log(`monthly rho(sleeve, PRIOR month bench)  ${corr(sl.slice(1), bn.slice(0, -1)).toFixed(4)}   (n=11)`);
console.log(`sign agreement sleeve vs ref: ${rows.filter(r => Math.sign(r.sleeve) === Math.sign(r.ref)).length} of 12 months`);

module.exports = { rows };
