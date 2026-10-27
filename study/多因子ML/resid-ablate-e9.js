#!/usr/bin/env node
/**
 * q-e9-corr-resid, part 3 — ZERO-BACKTEST, READ-ONLY (writes nothing).
 *
 * The sharpest version of the attribution question. If the base's residual overlap with the
 * 小市值 books is really the micro-cap sleeve (§4's "reassign to 小市值" conjecture), then:
 *   (a) the small_cap-ABLATED variant q-e9-1 should show a LOWER residual rho to those books;
 *   (b) the SYNTHETIC SLEEVE  d(t) = r_base(t) - r_variant(t)  should show a HIGHER one.
 * Both use curves already on disk. d(t) is a return DIFFERENCE, not a tradeable book — it is
 * the ablation's own definition of the leg's daily contribution, and is labelled as such.
 *
 * Everything is residualised against the SAME regressor: the base record's benchCum
 * (000300.XSHG) daily returns. Chain-convert on the WHOLE series, align by DATE, day 1
 * excluded (resid-e9.js shows the conventions differ by <= 0.001).
 */
const series = require('../../utils/backtest-series');

const BASE_KEY = '2026-06-28_高质量稳定上涨策略-d02cde29__train__e9';
const VAR_KEY = 'study_多因子ML_variants_q-e9-1__train__e9';
const PEERS = [
  ['d5040aa0', '2026-10-26_多策略组合系统_ETF轮动_小市值增强-d5040aa0__train__e9', '(prop:多因子ML)'],
  ['8d6831d4', '2026-10-18_市场大小盘风格切换多因子轮动策略-8d6831d4__train__e9', '小市值'],
  ['9f6f8188', '2026-06-18_年化52_-回撤17_-大小盘多策略-9f6f8188__train__e9', '小市值'],
  ['1c80dd9a', '2026-05-21_大小外择时小市值-1c80dd9a__train__e9', '小市值'],
  ['7301c5c4', '2026-07-17_三马_小市值_七星高照_白马_未来函数拟合分析和现实优化-7301c5c4__train__e9', '七星高照'],
  ['5a70adc1', '2026-05-22_关于小市值的不同筛选条件的差异研究-5a70adc1__train__e9', '小市值'],
  ['0aa4028d', '2026-06-15_追电ETF动量轮动_10年60多倍收益-0aa4028d__train__e9', 'ETF动量'],
  ['bba95a11', '2026-06-21_小市值_五福6年87倍13回撤-bba95a11__train__e9', '小市值'],
];

const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
function resid(y, x) {
  const my = mean(y), mx = mean(x);
  let sxy = 0, sxx = 0;
  for (let i = 0; i < y.length; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) ** 2; }
  const beta = sxy / sxx, alpha = my - beta * mx;
  return { beta, r: y.map((v, i) => v - alpha - beta * x[i]) };
}
function retMap(dates, cum) {
  const r = series.dailyReturns(cum);
  const m = new Map();
  for (let i = 1; i < dates.length; i++) if (Number.isFinite(r[i])) m.set(dates[i], r[i]);
  return m;
}

const base = series.load(BASE_KEY), vari = series.load(VAR_KEY);
if (!base || !vari) throw new Error('missing curve');
const bRet = retMap(base.dates, base.cum);
const vRet = retMap(vari.dates, vari.cum);
const mRet = retMap(base.dates, base.benchCum);

const dates = base.dates.filter(d => bRet.has(d) && vRet.has(d) && mRet.has(d));
console.log(`base/variant/bench common dates: ${dates.length}  ${dates[0]}..${dates[dates.length - 1]}`);
const m = dates.map(d => mRet.get(d));
const yB = dates.map(d => bRet.get(d));
const yV = dates.map(d => vRet.get(d));
const yD = dates.map(d => bRet.get(d) - vRet.get(d));   // synthetic sleeve contribution

const fB = resid(yB, m), fV = resid(yV, m), fD = resid(yD, m);
const sd = a => Math.sqrt(a.reduce((s, v) => s + (v - mean(a)) ** 2, 0) / (a.length - 1));
console.log(`beta to bench: base ${fB.beta.toFixed(4)}  variant(no small_cap) ${fV.beta.toFixed(4)}  sleeve d=base-variant ${fD.beta.toFixed(4)}`);
console.log(`daily sd (%) : base ${(sd(yB) * 100).toFixed(3)}  variant ${(sd(yV) * 100).toFixed(3)}  sleeve ${(sd(yD) * 100).toFixed(3)}`);
console.log(`rho(base, variant) raw ${series.pearson(yB, yV).toFixed(4)}  resid ${series.pearson(fB.r, fV.r).toFixed(4)}`);
console.log('');

console.log('== residual rho against the SAME bench, three objects ==');
console.log(['tag     ', 'family      ', ' base', ' varOnly', '  sleeve', 'Δ(sleeve-base)'].join('  '));
const rows = [];
for (const [tag, key, fam] of PEERS) {
  const rec = series.load(key);
  const pRet = retMap(rec.dates, rec.cum);
  const dd = dates.filter(d => pRet.has(d));
  if (dd.length !== dates.length) console.log(`  (note ${tag}: overlap ${dd.length} of ${dates.length})`);
  const mm = dd.map(d => mRet.get(d));
  const z = resid(dd.map(d => pRet.get(d)), mm).r;
  const rb = resid(dd.map(d => bRet.get(d)), mm).r;
  const rv = resid(dd.map(d => vRet.get(d)), mm).r;
  const rd = resid(dd.map(d => bRet.get(d) - vRet.get(d)), mm).r;
  const o = { tag, fam, base: series.pearson(rb, z), varOnly: series.pearson(rv, z), sleeve: series.pearson(rd, z) };
  rows.push(o);
  console.log([tag.padEnd(8), fam.padEnd(12), o.base.toFixed(4).padStart(6),
    o.varOnly.toFixed(4).padStart(8), o.sleeve.toFixed(4).padStart(8),
    (o.sleeve - o.base >= 0 ? '+' : '') + (o.sleeve - o.base).toFixed(4)].join('  '));
}

module.exports = { rows, dates };
