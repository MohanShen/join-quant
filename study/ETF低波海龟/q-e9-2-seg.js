// q-e9-2: Sep-rally segment (2024-09-24..10-08) vs rest-of-year from stored curves, chained.
// Usage: node -e "require('./study/ETF低波海龟/q-e9-2-seg.js')"
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const files = {
  base: '2026-10-17_量化分享_ETF低波海龟法则与复利增强的验证-4a8bcfd5__train__e9',
  mid: 'study_ETF低波海龟_variants_q-e9-2-mid__train__e9',
  high: 'study_ETF低波海龟_variants_q-e9-2-high__train__e9',
};
for (const [k, f] of Object.entries(files)) {
  const S = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'series', f + '.json'), 'utf8'));
  const r = S.cum.map((c, i) => (1 + c / 100) / (1 + (i ? S.cum[i - 1] : 0) / 100) - 1);
  const inS = d => d >= '2024-09-24' && d <= '2024-10-08';
  let a = 1, b = 1; const rest = [];
  S.dates.forEach((d, i) => { if (inS(d)) a *= 1 + r[i]; else { b *= 1 + r[i]; rest.push(r[i]); } });
  const m = rest.reduce((x, y) => x + y, 0) / rest.length;
  const sd = Math.sqrt(rest.reduce((x, y) => x + (y - m) ** 2, 0) / (rest.length - 1));
  const ann = Math.pow(b, 252 / rest.length) - 1;
  console.log(k, 'final', S.cum.at(-1), 'seg', ((a - 1) * 100).toFixed(2), 'rest', ((b - 1) * 100).toFixed(2),
    'restDays', rest.length, 'restSharpe(rf4%)', ((ann - 0.04) / (sd * Math.sqrt(252))).toFixed(2),
    'restSharpe(rf0)', (m / sd * Math.sqrt(252)).toFixed(2));
}
