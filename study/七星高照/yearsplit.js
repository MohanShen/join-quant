// Per-calendar-year stats from a captured curve (cum = cumulative percent; chained, never differenced).
// Sharpe here is a descriptive curve statistic (rf 0.04, 250d), not JQ's reported number.
// Usage: node study/七星高照/yearsplit.js <series key> [<other key> -> also prints daily-return correlation]
const fs = require('fs');
const path = require('path');
const load = key => JSON.parse(fs.readFileSync(path.join(__dirname, '../../data/series', `${key}.json`), 'utf8'));
const j = load(process.argv[2]);
const nav = j.cum.map(c => 1 + c / 100);
const byYear = {};
for (let i = 1; i < nav.length; i++) {
  const y = String(j.dates[i]).slice(0, 4);
  (byYear[y] = byYear[y] || []).push({ r: nav[i] / nav[i - 1] - 1, nav: nav[i], prev: nav[i - 1] });
}
for (const [y, rows] of Object.entries(byYear)) {
  const total = rows.reduce((a, x) => a * (1 + x.r), 1) - 1;
  let peak = rows[0].prev, mdd = 0;
  for (const x of rows) { peak = Math.max(peak, x.nav); mdd = Math.max(mdd, 1 - x.nav / peak); }
  const m = rows.reduce((a, x) => a + x.r, 0) / rows.length;
  const sd = Math.sqrt(rows.reduce((a, x) => a + (x.r - m) ** 2, 0) / (rows.length - 1));
  const sharpe = (m * 250 - 0.04) / (sd * Math.sqrt(250));
  console.log(`${y}\tdays=${rows.length}\ttotal=${(total * 100).toFixed(2)}\tmaxdd=${(mdd * 100).toFixed(2)}\tsharpe~${sharpe.toFixed(2)}`);
}
if (process.argv[3]) {
  const k = load(process.argv[3]);
  const ret = s => { const byDate = {}; for (let i = 1; i < s.cum.length; i++) byDate[s.dates[i]] = (1 + s.cum[i] / 100) / (1 + s.cum[i - 1] / 100) - 1; return byDate; };
  const a = ret(j), b = ret(k);
  const ds = Object.keys(a).filter(d => d in b);
  const xa = ds.map(d => a[d]), xb = ds.map(d => b[d]);
  const mean = x => x.reduce((p, q) => p + q, 0) / x.length;
  const ma = mean(xa), mb = mean(xb);
  let sab = 0, saa = 0, sbb = 0;
  for (let i = 0; i < ds.length; i++) { sab += (xa[i] - ma) * (xb[i] - mb); saa += (xa[i] - ma) ** 2; sbb += (xb[i] - mb) ** 2; }
  console.log(`corr(daily) over ${ds.length} days = ${(sab / Math.sqrt(saa * sbb)).toFixed(3)}`);
}
