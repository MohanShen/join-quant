#!/usr/bin/env node
/**
 * q-e9-month — ZERO-BACKTEST, READ-ONLY (writes nothing).
 *
 * Month-by-month contribution of the micro-cap sleeve over all 12 months of 2024, from the
 * two stored curves: base (d02cde29) and the small_cap-ABLATED variant (q-e9-1).
 *   base(m), variant(m)  = compounded monthly return
 *   ablationDelta(m)     = variant(m) - base(m)   <- "what removing the sleeve costs"
 *   c_sleeve(m)          = base(m) - variant(m)   <- the sleeve's contribution, same magnitude
 * Both signs are printed so neither reading can be quoted with the wrong one.
 *
 * Discipline: series.dailyReturns() chains cum -> returns on the WHOLE 242-pt series; the
 * returns are THEN sliced by month (clipping cum first would fold every earlier month's
 * cumulative gain into the slice's first day). Aligned by DATE. Both day-1 conventions shown.
 */
const series = require('../../utils/backtest-series');

const BASE_KEY = '2026-06-28_高质量稳定上涨策略-d02cde29__train__e9';
const VAR_KEY = 'study_多因子ML_variants_q-e9-1__train__e9';

const base = series.load(BASE_KEY), vari = series.load(VAR_KEY);
const rB = series.dailyReturns(base.cum);        // whole series, THEN sliced
const rV = series.dailyReturns(vari.cum);
const mapB = new Map(), mapV = new Map();
base.dates.forEach((d, i) => Number.isFinite(rB[i]) && mapB.set(d, rB[i]));
vari.dates.forEach((d, i) => Number.isFinite(rV[i]) && mapV.set(d, rV[i]));

const compound = arr => arr.reduce((s, v) => s * (1 + v), 1) - 1;
const maxDD = arr => {               // drawdown of the compounded path within the slice
  let peak = 1, cur = 1, dd = 0;
  for (const v of arr) { cur *= 1 + v; peak = Math.max(peak, cur); dd = Math.max(dd, 1 - cur / peak); }
  return dd;
};

function run(dropFirst) {
  const dates = base.dates.filter((d, i) => (dropFirst ? i > 0 : true) && mapB.has(d) && mapV.has(d));
  const byMonth = new Map();
  for (const d of dates) {
    const k = d.slice(0, 7);
    if (!byMonth.has(k)) byMonth.set(k, []);
    byMonth.get(k).push(d);
  }
  const rows = [];
  for (const [k, ds] of [...byMonth.entries()].sort()) {
    const b = compound(ds.map(d => mapB.get(d)));
    const v = compound(ds.map(d => mapV.get(d)));
    rows.push({
      month: k, n: ds.length, base: b * 100, vari: v * 100,
      delta: (v - b) * 100, sleeve: (b - v) * 100,
      shareOfBase: b === 0 ? null : ((b - v) / b) * 100,
      ddBase: maxDD(ds.map(d => mapB.get(d))) * 100,
    });
  }
  return { rows, n: dates.length, first: dates[0], last: dates[dates.length - 1] };
}

for (const dropFirst of [true, false]) {
  const { rows, n, first, last } = run(dropFirst);
  const sumAbs = rows.reduce((s, r) => s + Math.abs(r.sleeve), 0);
  const totB = rows.reduce((s, r) => s * (1 + r.base / 100), 1) - 1;
  const totV = rows.reduce((s, r) => s * (1 + r.vari / 100), 1) - 1;
  console.log(`== day 1 ${dropFirst ? 'EXCLUDED (prior run headline)' : 'INCLUDED'} ==  ${n} overlapping days  ${first}..${last}`);
  console.log('month      d   base%   var%  sleeve%  |share of |Σ|sleeve||  sleeve as % of base month   base monthDD%');
  for (const r of rows) {
    console.log([
      r.month, String(r.n).padStart(3),
      r.base.toFixed(2).padStart(7), r.vari.toFixed(2).padStart(7),
      (r.sleeve >= 0 ? '+' : '') + r.sleeve.toFixed(2).padStart(6),
      ((Math.abs(r.sleeve) / sumAbs) * 100).toFixed(1).padStart(16) + '%',
      (r.shareOfBase == null ? '—' : r.shareOfBase.toFixed(0) + '%').padStart(26),
      r.ddBase.toFixed(2).padStart(15),
    ].join('  '));
  }
  const pos = rows.filter(r => r.sleeve > 0).length, neg = rows.filter(r => r.sleeve < 0).length;
  const top = [...rows].sort((a, b) => Math.abs(b.sleeve) - Math.abs(a.sleeve));
  console.log(`  Σ sleeve (additive, pp) ${rows.reduce((s, r) => s + r.sleeve, 0).toFixed(2)}   Σ|sleeve| ${sumAbs.toFixed(2)}pp`);
  console.log(`  compounded year: base ${(totB * 100).toFixed(2)}%  variant ${(totV * 100).toFixed(2)}%  multiplicative sleeve ${((totB - totV) * 100).toFixed(2)}pp`);
  console.log(`  months sleeve>0: ${pos}   sleeve<0: ${neg}`);
  console.log(`  largest single month ${top[0].month} = ${((Math.abs(top[0].sleeve) / sumAbs) * 100).toFixed(1)}% of Σ|sleeve|   top2 ${(((Math.abs(top[0].sleeve) + Math.abs(top[1].sleeve)) / sumAbs) * 100).toFixed(1)}%   top3 ${(((Math.abs(top[0].sleeve) + Math.abs(top[1].sleeve) + Math.abs(top[2].sleeve)) / sumAbs) * 100).toFixed(1)}%`);
  // Herfindahl on |sleeve| shares
  const hhi = rows.reduce((s, r) => s + ((Math.abs(r.sleeve) / sumAbs) ** 2), 0);
  console.log(`  HHI of |sleeve| shares ${hhi.toFixed(4)}  (1/12 = 0.0833 would be perfectly even; 1.0 = one month)`);
  console.log('');
}

module.exports = { run };
