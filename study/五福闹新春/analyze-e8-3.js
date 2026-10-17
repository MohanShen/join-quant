// node -e "require('./study/五福闹新春/analyze-e8-3.js')"
// Reads the harvested LIQFLOOR / WEAKHOLD lines and the two stored TRAIN curves, and
// prints every item the dispatch asks for. Measurement-free: all inputs are on disk.
const fs = require('fs');
const path = require('path');
const series = require('../../utils/backtest-series');
const scan = require('../../utils/component-scan');

const LIQ = 'data/autostudy-logs/wufu-q-e8-3.liqfloor.txt';
const WH3 = 'data/autostudy-logs/wufu-q-e8-3.weakhold.txt';
const WH7 = 'data/autostudy-logs/wufu-q-e8-7.weakhold.txt';
const POOL = ['518880.XSHG', '513100.XSHG', '513500.XSHG', '513030.XSHG', '161226.XSHE',
  '501018.XSHG', '513520.XSHG', '159985.XSHE', '159980.XSHE'];

const lines = fs.readFileSync(LIQ, 'utf8').trim().split('\n');
console.log('=== (A) STRUCTURAL ===');
console.log('LIQFLOOR lines:', lines.length, '(expected 294 = weak days)');

const rows = [];
for (const l of lines) {
  const m = l.match(/LIQFLOOR (\S+) floor=(\S+) dyn=(\S+) in=(\d+) out=(\d+) removed=(\S+) dynout=(-?\d+) dynremoved=(\S+) money=(\S*) status=(\S+)/);
  if (!m) { console.log('UNPARSED:', l.slice(0, 200)); continue; }
  rows.push({
    date: m[1], floor: Number(m[2]), dyn: Number(m[3]), in: +m[4], out: +m[5],
    removed: m[6] === '-' ? [] : m[6].split(';'),
    dynout: +m[7], dynremoved: m[8] === '-' ? [] : m[8].split(';'),
    money: Object.fromEntries((m[9] === '-' || !m[9] ? [] : m[9].split(';')).map(p => {
      const [k, v] = p.split(':'); return [k, Number(v)];
    })),
    status: m[10],
  });
}
console.log('parsed rows:', rows.length);

const byStatus = {};
rows.forEach(r => { byStatus[r.status] = (byStatus[r.status] || 0) + 1; });
console.log('\n=== (4) status counts ===', JSON.stringify(byStatus));
const bypass = rows.filter(r => r.status !== 'ok');
console.log('bypass lines total:', bypass.length);

const inEqOut = rows.filter(r => r.in === r.out).length;
console.log('\nin==out rows:', inEqOut, '/', rows.length);
const dist = {};
rows.forEach(r => { dist[r.out] = (dist[r.out] || 0) + 1; });
console.log('out (survivors of 9) distribution:', JSON.stringify(dist, null, 0));
const rdist = {};
rows.forEach(r => { rdist[r.removed.length] = (rdist[r.removed.length] || 0) + 1; });
console.log('removed-count distribution:', JSON.stringify(rdist));

const perName = {};
POOL.forEach(s => { perName[s] = { removedDays: 0, dynRemovedDays: 0 }; });
rows.forEach(r => {
  r.removed.forEach(s => { if (perName[s]) perName[s].removedDays++; });
  r.dynremoved.forEach(s => { if (perName[s]) perName[s].dynRemovedDays++; });
});
console.log('\nper-ticker removed days (of %d):', rows.length);
console.log('ticker        floor2e7  relThresh');
POOL.forEach(s => console.log(`${s}   ${String(perName[s].removedDays).padStart(6)}   ${String(perName[s].dynRemovedDays).padStart(8)}`));

console.log('\n=== (3) floor leg vs the base relative threshold ===');
const dynMinusOut = rows.map(r => r.dynout - r.out);
const ddist = {};
dynMinusOut.forEach(v => { ddist[v] = (ddist[v] || 0) + 1; });
console.log('dynout - out distribution (names removed ONLY by the 2e7 floor):', JSON.stringify(ddist));
const dynDist = {};
rows.forEach(r => { dynDist[r.dynout] = (dynDist[r.dynout] || 0) + 1; });
console.log('dynout (survivors under base relative threshold alone) distribution:', JSON.stringify(dynDist));
const floorVals = [...new Set(rows.map(r => r.floor))];
const dyns = rows.filter(r => r.dyn >= 0).map(r => r.dyn).sort((a, b) => a - b);
console.log('floor value(s) seen:', floorVals);
console.log('dyn threshold over weak days: min', dyns[0], 'median', dyns[Math.floor(dyns.length / 2)], 'max', dyns[dyns.length - 1]);
console.log('weak days where dyn > floor:', rows.filter(r => r.dyn > r.floor).length, '(0 => the floor binds every day)');

console.log('\n=== (6) money= per-ticker 3-day average turnover (CNY/day) ===');
console.log('ticker          days  min        p10        median     p90        max        >2e7 days  >1e7  >5e7  >1e8');
POOL.forEach(s => {
  const v = rows.map(r => r.money[s]).filter(x => Number.isFinite(x)).sort((a, b) => a - b);
  const q = p => v.length ? v[Math.floor(p * (v.length - 1))] : NaN;
  const cnt = th => v.filter(x => x > th).length;
  const f = x => (Number.isFinite(x) ? (x / 1e8).toFixed(3) + '亿' : 'n/a');
  console.log(`${s}  ${String(v.length).padStart(4)}  ${f(v[0]).padEnd(10)} ${f(q(0.1)).padEnd(10)} ${f(q(0.5)).padEnd(10)} ${f(q(0.9)).padEnd(10)} ${f(v[v.length - 1]).padEnd(10)} ${String(cnt(2e7)).padStart(9)} ${String(cnt(1e7)).padStart(5)} ${String(cnt(5e7)).padStart(5)} ${String(cnt(1e8)).padStart(5)}`);
});
console.log('\nremoval-side curve at any floor (names surviving, summed over the 294 weak days):');
for (const th of [0, 5e6, 1e7, 2e7, 3e7, 5e7, 1e8, 2e8, 5e8]) {
  let tot = 0; const perDay = [];
  rows.forEach(r => { const n = POOL.filter(s => Number.isFinite(r.money[s]) && r.money[s] > th).length; tot += n; perDay.push(n); });
  perDay.sort((a, b) => a - b);
  console.log(`  floor ${(th / 1e8).toFixed(2)}亿: mean survivors ${(tot / rows.length).toFixed(2)}/9  median ${perDay[Math.floor(perDay.length / 2)]}  min ${perDay[0]}  max ${perDay[perDay.length - 1]}  zero-survivor days ${perDay.filter(x => x === 0).length}`);
}

console.log('\n=== (5) WEAKHOLD: 511880 fallback days ===');
function weakhold(file) {
  const t = fs.readFileSync(file, 'utf8').trim().split('\n');
  let n511 = 0, empty = 0, other = 0; const held = {};
  const days = [];
  for (const l of t) {
    const m = l.match(/WEAKHOLD (\d{4}-\d\d-\d\d) \[(.*)\]/);
    if (!m) continue;
    const syms = m[2] ? m[2].match(/\d{6}\.XSH[GE]/g) || [] : [];
    days.push({ date: m[1], syms });
    syms.forEach(s => { held[s] = (held[s] || 0) + 1; });
    if (syms.includes('511880.XSHG')) n511++;
    else if (!syms.length) empty++;
    else other++;
  }
  return { lines: t.length, days: days.length, n511, empty, other, held, raw: days };
}
const w3 = weakhold(WH3), w7 = weakhold(WH7);
console.log(`q-e8-3: 511880 held on ${w3.n511}/${w3.days} weak days; flat ${w3.empty}; other ${w3.other}`);
console.log(`q-e8-7: 511880 held on ${w7.n511}/${w7.days} weak days; flat ${w7.empty}; other ${w7.other}`);
console.log('\nq-e8-3 holdings on weak days, by ticker:');
Object.entries(w3.held).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`  ${k}  ${v}`));
console.log('q-e8-7 holdings on weak days, by ticker:');
Object.entries(w7.held).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`  ${k}  ${v}`));
// consistency: a weak day whose decision target was removed by the floor should not hold it
const liqByDate = Object.fromEntries(rows.map(r => [r.date, r]));
let violations = 0, checked = 0;
w3.raw.forEach(d => {
  const r = liqByDate[d.date];
  if (!r) return;             // WEAKHOLD prints context.current_dt, LIQFLOOR prints previous_date
  checked++;
});
console.log(`\nWEAKHOLD dates that also appear as a LIQFLOOR date: ${checked}/${w3.days} (keys differ by one trading day by construction)`);

console.log('\n=== (1)(2) curve + level ===');
const K3 = 'study/五福闹新春/variants/q-e8-3_pit9-liqfloor-2e7.py';
const K7 = 'study/五福闹新春/variants/q-e8-7_weak-pit9.py';
const KB = 'study/五福闹新春/baseline-e6.py';
const lc = (k) => { const r = series.loadComparable(k, 'train', 8); return r && r.rec ? r.rec : null; };
const c3 = lc(K3);
const c7 = lc(K7);
const cb = lc(KB);
console.log('curve q-e8-3:', c3 ? `${c3.points}d ${c3.start}..${c3.end} e${c3.epoch}` : 'MISSING');
console.log('curve q-e8-7:', c7 ? `${c7.points}d ${c7.start}..${c7.end} e${c7.epoch}` : 'MISSING');
console.log('curve base  :', cb ? `${cb.points}d ${cb.start}..${cb.end} e${cb.epoch}` : 'MISSING');

if (c3 && c7) {
  const n = Math.min(c3.cum.length, c7.cum.length);
  let maxd = 0, argmax = null;
  for (let i = 0; i < n; i++) {
    const d = Math.abs(c3.cum[i] - c7.cum[i]);
    if (d > maxd) { maxd = d; argmax = c3.dates[i]; }
  }
  console.log(`max|Δcum| vs q-e8-7 = ${maxd.toFixed(6)} pp at ${argmax} (0 => bit-identical)`);
  // first divergence
  let first = null;
  for (let i = 0; i < n; i++) if (Math.abs(c3.cum[i] - c7.cum[i]) > 1e-9) { first = c3.dates[i]; break; }
  console.log('first divergent day:', first || 'none');
  console.log('daily-return correlation vs q-e8-7:', JSON.stringify(series.correlate(c3, c7)));
}
if (c3 && cb) console.log('daily-return correlation vs baseline-e6:', JSON.stringify(series.correlate(c3, cb)));

function yearly(c, label) {
  if (!c) return;
  const sp = scan.yearlySplit(c);
  const parts = sp.map(v => `${v.year}: total ${v.totalPct.toFixed(2)}%  sharpe ${v.sharpe.toFixed(2)}  maxdd ${v.maxddPct.toFixed(2)}%  obj ${v.objective.toFixed(4)}  (n=${v.n}d)`);
  console.log(`${label}\n  ` + parts.join('\n  '));
}
console.log('\n=== (7) year split ===');
yearly(c3, 'q-e8-3');
yearly(c7, 'q-e8-7 pit9');
yearly(cb, 'baseline-e6');

console.log('\n=== headline ===');
const obj = (a, d) => (a - d) / 100;
const T = [
  ['q-e8-3 (pit9 + ¥2e7 floor)', 122.43, 49.22, 1.85, 14.59],
  ['q-e8-7 pit9 (PARENT)', null, 52.69, 2.04, 13.07],
  ['baseline-e6', null, null, 1.99, null],
];
console.log('book                          total%   annual%  sharpe  maxDD%  objective');
console.log(`q-e8-3                        122.43   49.22    1.85    14.59   ${obj(49.22, 14.59).toFixed(4)}`);
console.log(`q-e8-7 pit9 (parent)             -     52.69    2.04    13.07   ${obj(52.69, 13.07).toFixed(4)}`);
console.log(`Δ vs pit9                                -3.47   -0.19   +1.52   ${(obj(49.22, 14.59) - obj(52.69, 13.07)).toFixed(4)}`);
console.log(`baseline-e6 (side-by-side only)  -        -       1.99     -      0.3755`);
console.log(`Δ vs baseline-e6                                                 ${(obj(49.22, 14.59) - 0.3755).toFixed(4)}`);
