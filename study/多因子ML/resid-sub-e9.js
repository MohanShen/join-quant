#!/usr/bin/env node
/**
 * q-e9-corr-resid, part 4 — ZERO-BACKTEST, READ-ONLY (writes nothing).
 *
 * q-e9-corr CLOSED the "reassign to ETF动量" direction on a RAW-rho subsample reading:
 * dropping 2024-09+10 took 0aa4028d from 0.7060 to 0.5303 in lockstep with the benchmark's
 * own 0.6388 -> 0.4164, which was read as "the ETF-side overlap is shared 9/10 beta".
 * Residualising is exactly the test that reading needs, so re-run the subsample on RESIDUALS:
 * if the ETF-side residual rho survives dropping 9/10, "shared beta" is the wrong explanation.
 *
 * Returns are chained on the WHOLE series FIRST and the subsample is a slice of the RETURNS
 * (slicing cum would fold Jan-Aug's cumulative gain into the first retained day). Day 1 kept.
 */
const series = require('../../utils/backtest-series');

const base = series.load('2026-06-28_高质量稳定上涨策略-d02cde29__train__e9');
const vari = series.load('study_多因子ML_variants_q-e9-1__train__e9');
const PEERS = [
  ['d5040aa0', '2026-10-26_多策略组合系统_ETF轮动_小市值增强-d5040aa0__train__e9', '(prop:多因子ML)'],
  ['8d6831d4', '2026-10-18_市场大小盘风格切换多因子轮动策略-8d6831d4__train__e9', '小市值'],
  ['9f6f8188', '2026-06-18_年化52_-回撤17_-大小盘多策略-9f6f8188__train__e9', '小市值'],
  ['1c80dd9a', '2026-05-21_大小外择时小市值-1c80dd9a__train__e9', '小市值'],
  ['7301c5c4', '2026-07-17_三马_小市值_七星高照_白马_未来函数拟合分析和现实优化-7301c5c4__train__e9', '七星高照'],
  ['5a70adc1', '2026-05-22_关于小市值的不同筛选条件的差异研究-5a70adc1__train__e9', '小市值'],
  ['0aa4028d', '2026-06-15_追电ETF动量轮动_10年60多倍收益-0aa4028d__train__e9', 'ETF动量'],
  ['bba95a11', '2026-06-21_小市值_五福6年87倍13回撤-bba95a11__train__e9', '小市值'],
  ['73b13d92', '2026-06-21_五福闹新春_ETF动量轮动-73b13d92__train__e9', '五福闹新春'],
];

const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
function resid(y, x) {
  const my = mean(y), mx = mean(x);
  let sxy = 0, sxx = 0;
  for (let i = 0; i < y.length; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) ** 2; }
  const beta = sxy / sxx, alpha = my - beta * mx;
  return { beta, r: y.map((v, i) => v - alpha - beta * x[i]) };
}
function m2(dates, cum) {
  const r = series.dailyReturns(cum), out = new Map();
  dates.forEach((d, i) => Number.isFinite(r[i]) && out.set(d, r[i]));
  return out;
}
const B = m2(base.dates, base.cum), V = m2(vari.dates, vari.cum), M = m2(base.dates, base.benchCum);
const drop = d => d.startsWith('2024-09') || d.startsWith('2024-10');

console.log('tag      family        | FULL 2024                    | EXCL 2024-09/10');
console.log('                       | base   varOnly  sleeve  betaP| base   varOnly  sleeve  betaP   Δbase');
for (const [tag, key, fam] of PEERS) {
  const rec = series.load(key);
  if (!rec) { console.log(`${tag}  (no curve)`); continue; }
  const P = m2(rec.dates, rec.cum);
  const line = [];
  for (const sub of [false, true]) {
    const ds = base.dates.filter(d => B.has(d) && V.has(d) && M.has(d) && P.has(d) && (!sub || !drop(d)));
    const mm = ds.map(d => M.get(d));
    const z = resid(ds.map(d => P.get(d)), mm);
    const rb = resid(ds.map(d => B.get(d)), mm).r;
    const rv = resid(ds.map(d => V.get(d)), mm).r;
    const rd = resid(ds.map(d => B.get(d) - V.get(d)), mm).r;
    line.push({ n: ds.length, base: series.pearson(rb, z.r), varOnly: series.pearson(rv, z.r), sleeve: series.pearson(rd, z.r), betaP: z.beta });
  }
  const f = line[0], s = line[1];
  const p = (v) => v.toFixed(4).padStart(7);
  console.log(`${tag}  ${fam.padEnd(12)} |${p(f.base)}${p(f.varOnly)}${p(f.sleeve)}${p(f.betaP)}|${p(s.base)}${p(s.varOnly)}${p(s.sleeve)}${p(s.betaP)}   ${(s.base - f.base >= 0 ? '+' : '') + (s.base - f.base).toFixed(4)}   n ${f.n}/${s.n}`);
}

// the benchmark cannot appear in this table: its residual against itself is 0 by construction.
const dsAll = base.dates.filter(d => B.has(d) && M.has(d));
const dsSub = dsAll.filter(d => !drop(d));
const rawSelf = series.pearson(dsAll.map(d => B.get(d)), dsAll.map(d => M.get(d)));
const rawSelfSub = series.pearson(dsSub.map(d => B.get(d)), dsSub.map(d => M.get(d)));
console.log('');
console.log(`raw rho(base, own benchmark): full ${rawSelf.toFixed(4)}  excl 9/10 ${rawSelfSub.toFixed(4)}`);
console.log('NOTE: the benchmark has NO residual-rho entry — residualising it against itself gives 0 by');
console.log('      construction, so the 0.6388 "yardstick" simply ceases to exist on the residual scale.');
