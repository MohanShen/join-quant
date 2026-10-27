#!/usr/bin/env node
/**
 * q-e9-corr-resid — ZERO-BACKTEST analysis. READ-ONLY: writes nothing, anywhere.
 *
 * q-e9-corr measured rho(base, base's OWN benchmark curve) = 0.6388, HIGHER than
 * rho(base, bba95a11) = 0.6243 — so raw rho cannot separate "shares this family's edge"
 * from "shares the market". Fix: residualise BOTH sides against the SAME benchmark
 * daily-return series (the base record's stored benchCum) and correlate the residuals.
 * Correlating residuals of two variables on a common regressor IS the partial correlation
 * rho(base, peer | bench).
 *
 * Discipline (errors this repo has already paid for):
 *  - returns are CHAINED from cumulative percent by series.dailyReturns(); never differenced
 *    (differencing reports vol 1.3620 where JQ reports 0.2271).
 *  - dailyReturns() runs on the WHOLE series; slicing/aligning happens AFTER conversion.
 *  - alignment is BY DATE, never by index. Overlap length is reported for every pair.
 *  - both conventions are reported: incl = day 1 kept (prev=1, what series.correlate does),
 *    excl = day 1 dropped (the prior run's headline convention).
 */
const path = require('path');
const series = require('../../utils/backtest-series');
const ledger = require('../../utils/ledger');

const BASE_KEY = '2026-06-28_高质量稳定上涨策略-d02cde29__train__e9';

const PEERS = [
  ['d5040aa0', '2026-10-26_多策略组合系统_ETF轮动_小市值增强-d5040aa0__train__e9'],
  ['8d6831d4', '2026-10-18_市场大小盘风格切换多因子轮动策略-8d6831d4__train__e9'],
  ['9f6f8188', '2026-06-18_年化52_-回撤17_-大小盘多策略-9f6f8188__train__e9'],
  ['1c80dd9a', '2026-05-21_大小外择时小市值-1c80dd9a__train__e9'],
  ['7301c5c4', '2026-07-17_三马_小市值_七星高照_白马_未来函数拟合分析和现实优化-7301c5c4__train__e9'],
  ['5a70adc1', '2026-05-22_关于小市值的不同筛选条件的差异研究-5a70adc1__train__e9'],
  ['0aa4028d', '2026-06-15_追电ETF动量轮动_10年60多倍收益-0aa4028d__train__e9'],
  ['bba95a11', '2026-06-21_小市值_五福6年87倍13回撤-bba95a11__train__e9'],
];

// ---- helpers --------------------------------------------------------------------------------
const mean = a => a.reduce((s, v) => s + v, 0) / a.length;

/** OLS of y on x (with intercept). Returns {alpha, beta, resid, r2}. */
function ols(y, x) {
  const my = mean(y), mx = mean(x);
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < y.length; i++) {
    const dx = x[i] - mx, dy = y[i] - my;
    sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
  }
  const beta = sxx === 0 ? null : sxy / sxx;
  const alpha = beta == null ? null : my - beta * mx;
  const resid = beta == null ? null : y.map((v, i) => v - alpha - beta * x[i]);
  const r2 = (sxx === 0 || syy === 0) ? null : (sxy * sxy) / (sxx * syy);
  return { alpha, beta, resid, r2 };
}

/** date -> chained daily return map, converted on the WHOLE series then keyed by date. */
function retMap(dates, cum, { dropFirst }) {
  const r = series.dailyReturns(cum);
  const m = new Map();
  for (let i = dropFirst ? 1 : 0; i < dates.length; i++) {
    if (Number.isFinite(r[i])) m.set(dates[i], r[i]);
  }
  return m;
}

function analyse(base, peer, dropFirst) {
  const bRet = retMap(base.dates, base.cum, { dropFirst });
  const mRet = retMap(base.dates, base.benchCum, { dropFirst });   // the SHARED benchmark
  const pRet = retMap(peer.dates, peer.cum, { dropFirst });

  // align by DATE across all three
  const dates = base.dates.filter(d => bRet.has(d) && mRet.has(d) && pRet.has(d));
  const y = dates.map(d => bRet.get(d));
  const z = dates.map(d => pRet.get(d));
  const m = dates.map(d => mRet.get(d));
  if (dates.length < 3) return null;

  const rawRho = series.pearson(y, z);
  const fb = ols(y, m);          // base on bench
  const fp = ols(z, m);          // peer on bench
  const residRho = series.pearson(fb.resid, fp.resid);
  return {
    n: dates.length, first: dates[0], last: dates[dates.length - 1],
    rawRho, residRho,
    betaBase: fb.beta, betaPeer: fp.beta, r2Base: fb.r2, r2Peer: fp.r2,
    rhoBaseBench: series.pearson(y, m), rhoPeerBench: series.pearson(z, m),
  };
}

// ---- run ------------------------------------------------------------------------------------
const base = series.load(BASE_KEY);
if (!base) throw new Error('base curve missing: ' + BASE_KEY);
if (!base.benchCum || base.benchCum.length !== base.cum.length) throw new Error('base benchCum unusable');

const obj = new Map();
for (const r of ledger.normalized()) {
  if (Number(r.epoch) !== 9) continue;
  obj.set(r.sourceFile, { objective: Number(r.objective), sharpe: Number(r.sharpe) });
}

const out = [];
for (const [tag, key] of PEERS) {
  const peer = series.load(key);
  if (!peer) { out.push({ tag, key, missing: true }); continue; }
  const incl = analyse(base, peer, false);
  const excl = analyse(base, peer, true);
  // does the peer run against the SAME benchmark curve? (sanity check, not used in the maths)
  let benchSame = null;
  if (peer.benchCum && peer.benchCum.length === peer.dates.length) {
    const pm = retMap(peer.dates, peer.benchCum, { dropFirst: false });
    const bm = retMap(base.dates, base.benchCum, { dropFirst: false });
    const ds = base.dates.filter(d => pm.has(d) && bm.has(d));
    benchSame = series.pearson(ds.map(d => bm.get(d)), ds.map(d => pm.get(d)));
  }
  const o = obj.get(peer.sourceFile) || {};
  out.push({ tag, key, sourceFile: peer.sourceFile, incl, excl, benchSame, ...o });
}

// the base vs its own benchmark, both conventions
const selfIncl = (() => {
  const y = series.dailyReturns(base.cum), m = series.dailyReturns(base.benchCum);
  return { incl: series.pearson(y, m), excl: series.pearson(y.slice(1), m.slice(1)) };
})();

console.log(`BASE ${base.sourceFile}  ${base.points} pts  ${base.start}..${base.end}`);
const bo = obj.get(base.sourceFile) || {};
console.log(`     objective ${bo.objective} sharpe ${bo.sharpe}`);
console.log(`     rho(base, OWN benchmark) incl-day1 ${selfIncl.incl.toFixed(4)}  excl-day1 ${selfIncl.excl.toFixed(4)}`);
console.log(`     benchmark curve: ${base.benchCum.length} pts, final cum ${base.benchCum[base.benchCum.length - 1]}%`);
console.log('');

const hdr = ['tag     ', ' rawRho', 'residRho', 'betaBase', 'betaPeer', '  R2base', '  R2peer', 'rhoPB ', '  n', 'obj', 'sharpe'].join(' ');
for (const conv of ['excl', 'incl']) {
  console.log(`== convention: day 1 ${conv === 'excl' ? 'EXCLUDED (prior run headline)' : 'INCLUDED (series.correlate)'} ==`);
  console.log(hdr);
  const sorted = [...out].filter(r => !r.missing).sort((a, b) => b[conv].rawRho - a[conv].rawRho);
  for (const r of sorted) {
    const a = r[conv];
    console.log([
      r.tag.padEnd(8),
      a.rawRho.toFixed(4).padStart(7),
      a.residRho.toFixed(4).padStart(8),
      a.betaBase.toFixed(4).padStart(8),
      a.betaPeer.toFixed(4).padStart(8),
      a.r2Base.toFixed(4).padStart(8),
      a.r2Peer.toFixed(4).padStart(8),
      a.rhoPeerBench.toFixed(4).padStart(6),
      String(a.n).padStart(3),
      (r.objective == null ? '—' : r.objective.toFixed(4)).padStart(7),
      (r.sharpe == null ? '—' : r.sharpe.toFixed(2)).padStart(6),
    ].join(' '));
  }
  console.log('');
}

console.log('== RANK CHANGE (day 1 excluded) ==');
const byRaw = [...out].filter(r => !r.missing).sort((a, b) => b.excl.rawRho - a.excl.rawRho).map(r => r.tag);
const byRes = [...out].filter(r => !r.missing).sort((a, b) => b.excl.residRho - a.excl.residRho).map(r => r.tag);
console.log('  by raw rho     : ' + byRaw.join(' > '));
console.log('  by residual rho: ' + byRes.join(' > '));

console.log('');
console.log('== PEER BENCHMARK CURVE vs BASE BENCHMARK CURVE (rho of their bench daily returns) ==');
for (const r of out.filter(x => !x.missing)) {
  console.log(`  ${r.tag}  ${r.benchSame == null ? 'n/a' : r.benchSame.toFixed(6)}`);
}

module.exports = { base, out, selfIncl };
