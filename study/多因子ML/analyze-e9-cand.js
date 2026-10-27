// node -e "require('./study/多因子ML/analyze-e9-cand.js')"
// ZERO-BACKTEST analysis of the xp-e9-1 combined candidate against its three stored controls.
// ⚠ dailyReturns() chains (1+c_t/100)/(1+c_{t-1}/100)-1 over the WHOLE series; any month slicing
// happens on the RETURNS, never on `cum` (the yearlySplit lesson in CLAUDE.md).
const fs = require('fs');
const path = require('path');
const S = require('../../utils/backtest-series');

const ROOT = path.join(__dirname, '../..');
const load = (k) => JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series', k + '.json'), 'utf8'));

const C = load('enhance_candidates_xp-e9-1__train__e9');
const B = load('2026-06-28_高质量稳定上涨策略-d02cde29__train__e9');
const L = load('study_多因子ML_variants_q-e9-liq-1__train__e9');
const P = load('study_多因子ML_variants_q-e9-pit__train__e9');
const ALL = [['cand', C], ['base', B], ['liq-1', L], ['pit', P]];

console.log('=== curves ===');
for (const [n, c] of ALL) {
  console.log(`  ${n.padEnd(6)} ${c.points}d ${c.start}..${c.end} epoch ${c.epoch} finalCum ${c.cum[c.cum.length - 1]}`);
}
const aligned = ALL.every(([, c]) => c.dates.length === C.dates.length && c.dates.every((d, i) => d === C.dates[i]));
console.log('  date grids identical across all four:', aligned);
if (!aligned) throw new Error('date grids differ — a day-by-day comparison would be meaningless');

console.log('\n=== cumulative-curve identity (max |Delta cum|, pp) ===');
const md = (a, b) => Math.max(...a.cum.map((v, i) => Math.abs(v - b.cum[i])));
const diffDays = (a, b) => a.cum.map((v, i) => [a.dates[i], +(v - b.cum[i]).toFixed(6)]).filter(([, d]) => Math.abs(d) > 1e-9);
for (const [n, c] of [['liq-1', L], ['pit', P], ['base', B]]) {
  const dd = diffDays(C, c);
  console.log(`  cand vs ${n.padEnd(6)}: max|dCum| = ${md(C, c).toFixed(6)}pp | differing days ${dd.length}/${C.points}` +
    (dd.length ? ` | first ${dd[0][0]} (${dd[0][1] > 0 ? '+' : ''}${dd[0][1]}pp) last ${dd[dd.length - 1][0]} (${dd[dd.length - 1][1] > 0 ? '+' : ''}${dd[dd.length - 1][1]}pp)` : '  <= BIT-IDENTICAL'));
}

console.log('\n=== daily-return correlation (chained, 241 returns) ===');
// ⚠ dailyReturns takes the cum ARRAY and is INDEX-ALIGNED with dates (index 0 = first day,
// measured against a base of 1), not offset by one.
const r = Object.fromEntries(ALL.map(([n, c]) => [n, S.dailyReturns(c.cum)]));
for (const n of ['base', 'liq-1', 'pit']) {
  console.log(`  rho(cand, ${n.padEnd(6)}) = ${S.pearson(r.cand, r[n]).toFixed(6)}   (n=${r.cand.length})`);
}
console.log('  --- reference pairs among the controls ---');
for (const [a, b] of [['base', 'liq-1'], ['base', 'pit'], ['liq-1', 'pit']]) {
  console.log(`  rho(${a}, ${b}) = ${S.pearson(r[a], r[b]).toFixed(6)}`);
}

console.log('\n=== Sep+Oct share of log-growth ===');
for (const [n, c] of ALL) {
  const dates = c.dates;                         // index-aligned with the returns
  const lgAll = r[n].map(x => Math.log(1 + x));
  // Reported two ways, as q-e9-1 / q-e9-month did: INCLUDING day 0 (cum[0] measured against a
  // base of 1, i.e. the window's first day) and EXCLUDING it.
  for (const [tag, from] of [['incl cum[0]', 0], ['excl cum[0]', 1]]) {
    const lg = lgAll.slice(from), dd = dates.slice(from);
    const total = lg.reduce((s, x) => s + x, 0);
    const sepOct = lg.reduce((s, x, i) => s + (/^2024-(09|10)-/.test(dd[i]) ? x : 0), 0);
    const nDays = dd.filter(d => /^2024-(09|10)-/.test(d)).length;
    console.log(`  ${n.padEnd(6)} [${tag}] total log-growth ${total.toFixed(5)} | Sep+Oct ${sepOct.toFixed(5)} over ${nDays}d = ${(100 * sepOct / total).toFixed(1)}%`);
  }
}

console.log('\n=== max drawdown, from the curve (and its date range) ===');
for (const [n, c] of ALL) {
  // equity from cumulative percent; drawdown on the equity path
  const eq = c.cum.map(v => 1 + v / 100);
  let peak = eq[0], peakI = 0, worst = 0, wPeakI = 0, wTroughI = 0;
  for (let i = 0; i < eq.length; i++) {
    if (eq[i] > peak) { peak = eq[i]; peakI = i; }
    const dd = 1 - eq[i] / peak;
    if (dd > worst) { worst = dd; wPeakI = peakI; wTroughI = i; }
  }
  // recovery: first day after the trough that regains the peak
  let rec = -1;
  for (let i = wTroughI + 1; i < eq.length; i++) if (eq[i] >= eq[wPeakI]) { rec = i; break; }
  console.log(`  ${n.padEnd(6)} maxDD ${(100 * worst).toFixed(2)}%  peak ${c.dates[wPeakI]} (cum ${c.cum[wPeakI]}) -> trough ${c.dates[wTroughI]} (cum ${c.cum[wTroughI]})` +
    `  [${wTroughI - wPeakI} trading days]  recovered ${rec < 0 ? 'NOT within TRAIN' : c.dates[rec]}`);
}

console.log('\n=== objective table ((annual - maxdd)/100, annual == total over a 365-day window) ===');
const obj = (ann, dd) => ((ann - dd) / 100).toFixed(4);
console.log(`  base   156.71 / 9.40 => ${obj(156.71, 9.40)}   (ledger row)`);
console.log(`  liq-1  165.79 / 9.36 => ${obj(165.79, 9.36)}`);
console.log(`  pit    168.83 / 9.40 => ${obj(168.83, 9.40)}`);
console.log(`  cand   165.79 / 9.36 => ${obj(165.79, 9.36)}   (SUMMARY line)`);
