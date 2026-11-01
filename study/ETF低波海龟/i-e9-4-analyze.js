// i-e9-4: log + curve summary. Usage: node -e "require('./study/ETF低波海龟/i-e9-4-analyze.js')"
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const L = fs.readFileSync(path.join(__dirname, 'logs', 'i-e9-4-train.log'), 'utf8').split('\n');
const cnt = re => L.filter(l => re.test(l)).length;
console.log('lines', L.length, 'Q4HOLD', cnt(/Q4HOLD/), 'POOLSIZE', cnt(/POOLSIZE/), 'I3 med', cnt(/I3 med/),
  'ERROR/WARN/Traceback', cnt(/ERROR|POOLWARN|Traceback/), 'allow=True days', cnt(/I3 med.*allow=True/));
const sizes = L.filter(l => /POOLSIZE/.test(l)).map(l => +l.match(/pool=(\d+)/)[1]);
console.log('pool size min/max', Math.min(...sizes), Math.max(...sizes));
const meds = L.filter(l => /I3 med/.test(l)).map(l => +l.match(/med=([\d.]+)/)[1]);
console.log('risk-vol median max', Math.max(...meds).toFixed(4), '>0.40 days', meds.filter(x => x > 0.4).length);
console.log('--- I3SET');
L.filter(l => /I3SET/.test(l)).forEach(l => console.log(l.slice(0, 300)));
console.log('--- errors');
L.filter(l => /ERROR|POOLWARN|Traceback/.test(l)).slice(0, 5).forEach(l => console.log(l.slice(0, 300)));
// holdings per day
const SAFE = ['511010.XSHG', '511260.XSHG'];
let bondDays = 0, cashDays = 0;
const monthly = {};
const names = {};
for (const l of L.filter(x => /Q4HOLD/.test(x))) {
  const m = l.match(/Q4HOLD (\S+) (.*)$/); if (!m) continue;
  const d = m[1], rest = m[2].trim();
  if (rest === 'CASH') { cashDays++; continue; }
  const items = rest.split(';').map(s => s.split('|'));
  items.forEach(([c, n]) => { names[c] = n; });
  if (items.some(([c]) => SAFE.includes(c))) bondDays++;
  const mo = d.slice(0, 7);
  monthly[mo] = monthly[mo] || {};
  items.forEach(([c]) => { monthly[mo][c] = (monthly[mo][c] || 0) + 1; });
}
console.log('bond holding days', bondDays, 'cash days', cashDays);
console.log('--- monthly holdings (code name days)');
for (const [mo, o] of Object.entries(monthly))
  console.log(mo, Object.entries(o).map(([c, n]) => `${c}|${names[c]}|${n}`).join('  '));
// curve split
const S = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series/study_ETF低波海龟_variants_i-e9-4__train__e9.json'), 'utf8'));
const r = S.cum.map((c, i) => (1 + c / 100) / (1 + (i ? S.cum[i - 1] : 0) / 100) - 1);
const inS = d => d >= '2024-09-24' && d <= '2024-10-08';
let a = 1, b = 1; const rest = [];
S.dates.forEach((d, i) => { if (inS(d)) a *= 1 + r[i]; else { b *= 1 + r[i]; rest.push(r[i]); } });
const mu = rest.reduce((x, y) => x + y, 0) / rest.length;
const sd = Math.sqrt(rest.reduce((x, y) => x + (y - mu) ** 2, 0) / (rest.length - 1));
let peak = -1e9, mdd = 0; S.cum.forEach(c => { const v = 1 + c / 100; peak = Math.max(peak, v); mdd = Math.max(mdd, 1 - v / peak); });
console.log('curve final', S.cum.at(-1), 'maxDD', (mdd * 100).toFixed(2), 'seg', ((a - 1) * 100).toFixed(2),
  'rest', ((b - 1) * 100).toFixed(2), 'restDays', rest.length, 'restSharpe(rf0)', (mu / sd * Math.sqrt(252)).toFixed(2));
