// q-e9-liq: max|Δcum| of a variant curve vs the base d0a149b1 e9 TRAIN curve, + daily-return corr.
// Usage: node -e "require('./study/红利质量/liq-compare.js')" -- <variant series key>
const fs = require('fs');
const path = require('path');
const S = path.join(__dirname, '../../data/series');
const key = process.argv.slice(1).filter(a => a !== '--' && a !== '-e')[0];
const base = JSON.parse(fs.readFileSync(path.join(S, '2026-10-17_年化14_回撤16_对标美股SCHD的A股红利股息策略月频-d0a149b1__train__e9.json'), 'utf8'));
const v = JSON.parse(fs.readFileSync(path.join(S, key + '.json'), 'utf8'));
const bm = new Map(base.dates.map((t, i) => [t, base.cum[i]]));
let maxd = 0, at = null, n = 0, same = 0;
for (let i = 0; i < v.dates.length; i++) {
  const b = bm.get(v.dates[i]); if (b == null) continue;
  n++; const d = Math.abs(v.cum[i] - b); if (d === 0) same++;
  if (d > maxd) { maxd = d; at = v.dates[i]; }
}
const r = c => c.map((x, i) => i ? (1 + x / 100) / (1 + c[i - 1] / 100) - 1 : (1 + x / 100) - 1);
const rb = r(base.cum), rv = r(v.cum);
const m = a => a.reduce((s, x) => s + x, 0) / a.length;
const mb = m(rb), mv = m(rv);
let sxy = 0, sxx = 0, syy = 0;
for (let i = 0; i < Math.min(rb.length, rv.length); i++) { sxy += (rb[i] - mb) * (rv[i] - mv); sxx += (rb[i] - mb) ** 2; syy += (rv[i] - mv) ** 2; }
console.log(JSON.stringify({ key, points: v.points, aligned: n, identicalDays: same, maxAbsDeltaCumPp: +maxd.toFixed(4), at,
  endBase: base.cum.at(-1), endVar: v.cum.at(-1), corr: +(sxy / Math.sqrt(sxx * syy)).toFixed(5) }));
