// Leg-native metrics for the u-1 single-leg runs, from stored curves.
// NAV_leg_t = ((1 + c_t/100) - (1 - w)) / w   (idle cash constant, leg sub-ledger compounds)
// Chained daily returns, rf 4%, sharpe = (ann - rf) / (sd * sqrt(K)).
// Reproduce the base (w=1) first; if it does not reproduce JQ's 4.96, the native number is not citable.
//
// Usage: node -e "require('./study/多策略分仓组合/native-sharpe.js').main('study_多策略分仓组合_variants_u-1b__train__e9.json', 0.35)"
const fs = require('fs');
const path = require('path');
const SER = path.join(__dirname, '../../data/series');
const BASE = '2026-07-18_多策略-题材概念-35ce65d2__train__e9.json';
const load = f => JSON.parse(fs.readFileSync(path.join(SER, f), 'utf8'));

function stats(cum, w, K, annMode) {
  const nav = cum.map(c => ((1 + c / 100) - (1 - w)) / w);
  const r = []; let prev = 1;
  for (const v of nav) { r.push(v / prev - 1); prev = v; }
  const n = r.length, m = r.reduce((a, b) => a + b, 0) / n;
  const sd = Math.sqrt(r.reduce((a, b) => a + (b - m) ** 2, 0) / (n - 1));
  const vol = sd * Math.sqrt(K);
  const tot = nav[n - 1] - 1;
  const ann = annMode === 'row' ? tot : Math.pow(1 + tot, K / n) - 1; // row = 365-day window, 1 year
  let pk = 1, dd = 0;
  for (const v of nav) { pk = Math.max(pk, v); dd = Math.max(dd, 1 - v / pk); }
  return { tot: +(tot * 100).toFixed(2), ann: +(ann * 100).toFixed(2), vol: +vol.toFixed(4),
    sharpe: +((ann - 0.04) / vol).toFixed(3), mdd: +(dd * 100).toFixed(2), minNav: +Math.min(...nav).toFixed(4), n };
}

function dailyAcct(cum) { const o = []; let p = 1; for (const x of cum) { const v = 1 + x / 100; o.push(v / p - 1); p = v; } return o; }

function main(file, w) {
  const b = load(BASE), u = load(file);
  for (const K of [250, 252]) for (const am of ['row', 'trading']) {
    console.log(`K=${K} ann=${am}`);
    console.log('  base w=1      ', JSON.stringify(stats(b.cum, 1, K, am)));
    console.log('  run  w=1      ', JSON.stringify(stats(u.cum, 1, K, am)));
    console.log(`  run  w=${w} NAV `, JSON.stringify(stats(u.cum, w, K, am)));
  }
  console.log('run', u.start, u.end, u.points, 'dates==base:', JSON.stringify(u.dates) === JSON.stringify(b.dates),
    'final cum', u.cum[u.cum.length - 1], 'base final', b.cum[b.cum.length - 1]);
  const rb = dailyAcct(b.cum), ru = dailyAcct(u.cum);
  const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
  const sd = a => { const m = mean(a); return Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1)); };
  const mb = mean(rb), mu = mean(ru); let cov = 0;
  for (let i = 0; i < rb.length; i++) cov += (rb[i] - mb) * (ru[i] - mu);
  cov /= rb.length - 1;
  console.log('account daily sd: base', sd(rb).toFixed(6), 'run', sd(ru).toFixed(6), 'corr', (cov / sd(rb) / sd(ru)).toFixed(4));
}
module.exports = { stats, main };
