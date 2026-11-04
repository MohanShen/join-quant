// q-e9-champ-numstock — R3/R4 reads from the two stored TRAIN curves (zero backtest cost).
// Usage: node -e "require('./study/小市值/analyse-numstock.js')"
const fs = require('fs');
const P = require('path').join(__dirname, '../../data/series/');
const curve = f => { const j = JSON.parse(fs.readFileSync(P + f, 'utf8')); return j.dates.map((d, i) => ({ d, v: 1 + j.cum[i] / 100 })); };
const base = curve('2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa__train__e9.json');
const varc = curve('study_小市值_variants_02fdafaa-numstock__train__e9.json');
function monthly(c) { const m = {}; let prev = 1; for (const p of c) { const k = p.d.slice(0, 7); if (!(k in m)) m[k] = { start: prev }; m[k].end = p.v; prev = p.v; } return m; }
function seg(c, from, to) { let prev = 1, lg = 0; for (const p of c) { if (p.d > from && p.d <= to) lg += Math.log(p.v / prev); prev = p.v; } return lg; }
function maxdd(c) { let pk = 1, pkd = 'start', best = 0, w = null; for (const p of c) { if (p.v > pk) { pk = p.v; pkd = p.d; } const dd = 1 - p.v / pk; if (dd > best) { best = dd; w = [pkd, p.d]; } } return { dd: +(best * 100).toFixed(2), w }; }
const mb = monthly(base), mv = monthly(varc);
let tot = 0, sumAbs = 0; const rows = [];
for (const k of Object.keys(mb)) {
  const lb = Math.log(mb[k].end / mb[k].start), lv = Math.log(mv[k].end / mv[k].start);
  rows.push([k, ((mb[k].end / mb[k].start - 1) * 100).toFixed(2), ((mv[k].end / mv[k].start - 1) * 100).toFixed(2), (lv - lb).toFixed(4)]);
  tot += lv - lb; sumAbs += Math.abs(lv - lb);
}
console.log('month    base%   var%    dLog'); rows.forEach(r => console.log(r.join('  ')));
const dApr = +rows.find(r => r[0] === '2024-04')[3];
console.log('total dLog', tot.toFixed(4), '| sum|dLog_m|', sumAbs.toFixed(4));
console.log('April |d|/|total d|', (Math.abs(dApr) / Math.abs(tot)).toFixed(3), '| April |d|/sum|d_m|', (Math.abs(dApr) / sumAbs).toFixed(3));
const post = seg(varc, '2024-09-23', '2024-12-31') - seg(base, '2024-09-23', '2024-12-31');
console.log('2024-09-24..12-31 dLog', post.toFixed(4), 'share of total', (post / tot).toFixed(3));
console.log('maxDD base', JSON.stringify(maxdd(base)), 'var', JSON.stringify(maxdd(varc)));
console.log('final cum base', ((base.at(-1).v - 1) * 100).toFixed(2), 'var', ((varc.at(-1).v - 1) * 100).toFixed(2), 'points', base.length, varc.length);
