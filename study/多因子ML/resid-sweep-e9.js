#!/usr/bin/env node
/**
 * q-e9-corr-resid, part 2 — ZERO-BACKTEST, READ-ONLY (writes nothing).
 *
 * Context for the 8 named peers: residualise EVERY stored epoch-9 TRAIN curve against the
 * SAME benchmark daily-return series (the base record's benchCum, 000300.XSHG) and report the
 * distribution of residual rho, so "residual rho 0.51" can be read against its own population
 * rather than against zero. Also supplies the design's required median-rho control book.
 *
 * Same discipline as resid-e9.js: chain cum -> returns on the WHOLE series, align by DATE,
 * day 1 EXCLUDED (the prior run's headline convention; resid-e9.js shows the two conventions
 * differ by <= 0.001 here).
 */
const series = require('../../utils/backtest-series');
const fs = require('fs');
const path = require('path');
const fm = require('../../utils/frontmatter');
const ledger = require('../../utils/ledger');

const ROOT = path.resolve(__dirname, '../..');
const BASE_KEY = '2026-06-28_高质量稳定上涨策略-d02cde29__train__e9';

const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
function ols(y, x) {
  const my = mean(y), mx = mean(x);
  let sxy = 0, sxx = 0;
  for (let i = 0; i < y.length; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) ** 2; }
  if (sxx === 0) return null;
  const beta = sxy / sxx, alpha = my - beta * mx;
  return { beta, resid: y.map((v, i) => v - alpha - beta * x[i]) };
}
function retMap(dates, cum) {
  const r = series.dailyReturns(cum);
  const m = new Map();
  for (let i = 1; i < dates.length; i++) if (Number.isFinite(r[i])) m.set(dates[i], r[i]);
  return m;
}

const base = series.load(BASE_KEY);
const bRet = retMap(base.dates, base.cum);
const mRet = retMap(base.dates, base.benchCum);

const meta = new Map();
for (const f of fs.readdirSync(path.join(ROOT, 'wiki/strategies')).filter(x => x.endsWith('.md'))) {
  const t = fs.readFileSync(path.join(ROOT, 'wiki/strategies', f), 'utf8');
  const src = fm.field(t, 'sourceFile');
  if (src) meta.set(src, fm.link(t, 'family') || (fm.link(t, 'familyProposal') ? '(prop:' + fm.link(t, 'familyProposal') + ')' : '(unassigned)'));
}
const obj = new Map();
for (const r of ledger.normalized()) if (Number(r.epoch) === 9) obj.set(r.sourceFile, Number(r.objective));

const rows = [];
for (const k of series.list().filter(x => x.endsWith('__train__e9') && x !== BASE_KEY)) {
  const rec = series.load(k);
  if (!rec) continue;
  const pRet = retMap(rec.dates, rec.cum);
  const dates = base.dates.filter(d => bRet.has(d) && mRet.has(d) && pRet.has(d));
  if (dates.length < 60) continue;
  const y = dates.map(d => bRet.get(d)), z = dates.map(d => pRet.get(d)), m = dates.map(d => mRet.get(d));
  const fb = ols(y, m), fp = ols(z, m);
  if (!fb || !fp) continue;
  rows.push({
    key: k, src: rec.sourceFile, tag: (rec.sourceFile.match(/-([0-9a-f]{8})\.py$/) || [, k.slice(0, 20)])[1],
    family: meta.get(rec.sourceFile) || '(unassigned)',
    raw: series.pearson(y, z), resid: series.pearson(fb.resid, fp.resid),
    betaPeer: fp.beta, n: dates.length, obj: obj.get(rec.sourceFile),
  });
}

const resids = rows.map(r => r.resid).filter(Number.isFinite).sort((a, b) => a - b);
const raws = rows.map(r => r.raw).filter(Number.isFinite).sort((a, b) => a - b);
const q = (arr, p) => arr[Math.min(arr.length - 1, Math.floor(p * arr.length))];

console.log(`n curves = ${rows.length}  (shared regressor: base's benchCum = 000300.XSHG)`);
console.log(`raw   rho: min ${q(raws,0).toFixed(4)} p25 ${q(raws,.25).toFixed(4)} med ${q(raws,.5).toFixed(4)} p75 ${q(raws,.75).toFixed(4)} p95 ${q(raws,.95).toFixed(4)} max ${q(raws,.9999).toFixed(4)}`);
console.log(`resid rho: min ${q(resids,0).toFixed(4)} p25 ${q(resids,.25).toFixed(4)} med ${q(resids,.5).toFixed(4)} p75 ${q(resids,.75).toFixed(4)} p95 ${q(resids,.95).toFixed(4)} max ${q(resids,.9999).toFixed(4)}`);
console.log(`resid rho > 0.4: ${resids.filter(v => v > 0.4).length}   > 0.5: ${resids.filter(v => v > 0.5).length}   <= 0.2: ${resids.filter(v => v <= 0.2).length}`);
console.log('');

// median-rho CONTROL book the design asks for
const byRaw = [...rows].filter(r => Number.isFinite(r.raw)).sort((a, b) => a.raw - b.raw);
const ctrl = byRaw[Math.floor(byRaw.length / 2)];
console.log(`== MEDIAN-raw-rho CONTROL == ${ctrl.tag}  family ${ctrl.family}`);
console.log(`   raw ${ctrl.raw.toFixed(4)}  resid ${ctrl.resid.toFixed(4)}  betaPeer ${ctrl.betaPeer.toFixed(4)}  n ${ctrl.n}  obj ${ctrl.obj}`);
console.log(`   src ${ctrl.src}`);
console.log('');

console.log('== TOP 15 BY RESIDUAL rho ==');
console.log(['tag     ', '   raw', ' resid', '  beta', 'family      ', 'obj'].join('  '));
for (const r of [...rows].sort((a, b) => b.resid - a.resid).slice(0, 15)) {
  console.log([r.tag.padEnd(8), r.raw.toFixed(4).padStart(6), r.resid.toFixed(4).padStart(6),
    r.betaPeer.toFixed(4).padStart(6), String(r.family).padEnd(12),
    (r.obj == null ? '—' : r.obj.toFixed(4)).padStart(7)].join('  '));
}
console.log('');

const byFam = new Map();
for (const r of rows) {
  if (!Number.isFinite(r.resid)) continue;
  if (!byFam.has(r.family)) byFam.set(r.family, []);
  byFam.get(r.family).push(r);
}
console.log('== PER-FAMILY: max / median residual rho (and the same for raw) ==');
const summ = [...byFam.entries()].map(([fam, rs]) => {
  const sr = [...rs].sort((a, b) => a.resid - b.resid), sw = [...rs].sort((a, b) => a.raw - b.raw);
  return { fam, n: rs.length, maxR: sr[sr.length - 1].resid, medR: sr[Math.floor(sr.length / 2)].resid,
    maxW: sw[sw.length - 1].raw, medW: sw[Math.floor(sw.length / 2)].raw, who: sr[sr.length - 1].tag };
}).sort((a, b) => b.maxR - a.maxR);
for (const s of summ) {
  console.log(`  resid max ${s.maxR.toFixed(4)} med ${s.medR.toFixed(4)} | raw max ${s.maxW.toFixed(4)} med ${s.medW.toFixed(4)} | n=${String(s.n).padStart(3)}  ${s.fam.padEnd(14)} (max by ${s.who})`);
}

module.exports = { rows, ctrl };
