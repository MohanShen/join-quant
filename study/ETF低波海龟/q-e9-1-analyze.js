// q-e9-1: event counts, vol-median stats, holding periods and per-holding return attribution
// for TRAIN run 0b949625ef74dc0c31a55273a8015bfb. Zero backtests — reads the saved log + stored curve.
// Usage: node study/ETF低波海龟/q-e9-1-analyze.js
const fs = require('fs');
const path = require('path');
const DIR = __dirname;
const ROOT = path.join(DIR, '..', '..');
const log = fs.readFileSync(path.join(DIR, 'logs', 'q-e9-1-train.log'), 'utf8').split('\n')
  .filter(l => /^\d{4}-\d\d-\d\d /.test(l));
const S = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'series',
  '2026-10-17_量化分享_ETF低波海龟法则与复利增强的验证-4a8bcfd5__train__e9.json'), 'utf8'));

// --- event counts (message prefix after "INFO  - " / "WARNING - ")
const msg = l => l.replace(/^\S+ \S+ - [A-Z]+\s+- /, '');
const KEYS = ['建仓', '换入', '换回', '换仓', '加仓完成', '止损', '止盈', '避险买入', '清理多余持仓',
  '加仓检查通过', '加仓资金不足', '抑制换手', '最短持有期未满', '继续持有避险资产'];
const counts = {};
for (const k of KEYS) counts[k] = log.filter(l => msg(l).startsWith(k + '：') || msg(l).startsWith(k + ' ')
  || (k === '换回' && msg(l).startsWith('风控解除，换回'))).length;
// 换回 is logged both as "风控解除，换回..." and via open_position(note='换回') -> "换回：..."
counts['换回'] = log.filter(l => /^换回：|^风控解除，换回/.test(msg(l))).length;
console.log('COUNTS', JSON.stringify(counts));

// --- vol median
const vm = [];
for (const l of log) { const m = l.match(/^(\S+) .*风险资产波动率中位数 ([\d.]+)%；允许避险：(\w+)/); if (m) vm.push({ d: m[1], v: +m[2] / 100, safe: m[3] }); }
const mx = vm.reduce((a, b) => (b.v > a.v ? b : a));
console.log(`VOLMEDIAN days=${vm.length} max=${(mx.v * 100).toFixed(2)}% on ${mx.d} days>0.40=${vm.filter(x => x.v > 0.40).length} allowSafeTrue=${vm.filter(x => x.safe === 'True').length}`);

// --- holding state per day (after the 09:35 trade)
const evByDay = {};
for (const l of log) { const d = l.slice(0, 10); (evByDay[d] = evByDay[d] || []).push(msg(l)); }
let held = null, units = 0; const after = {}; const periods = []; let cur = null;
for (const d of S.dates) {
  for (const m of evByDay[d] || []) {
    let r;
    if ((r = m.match(/^止损：(\S+?) /))) { if (cur) { cur.to = d; cur.exit = '止损'; periods.push(cur); cur = null; } held = null; units = 0; }
    else if ((r = m.match(/^换仓：(\S+) /))) { if (cur) { cur.to = d; cur.exit = '换仓'; periods.push(cur); cur = null; } held = null; units = 0; }
    else if ((r = m.match(/^(建仓|换入|换回)：(\S+) (\d) Unit/))) { held = r[2]; units = +r[3]; cur = { etf: held, from: d, to: null, entry: r[1], units0: units, maxUnits: units, adds: [], tp: [] }; }
    else if ((r = m.match(/^避险买入：(\S+?)，/))) { held = r[1]; units = 4; cur = { etf: held, from: d, entry: '避险买入', units0: 4, maxUnits: 4, adds: [], tp: [] }; }
    else if ((r = m.match(/^加仓完成：(\S+?)，现 (\d) Unit/))) { units = +r[2]; cur.maxUnits = Math.max(cur.maxUnits, units); cur.adds.push(`${d}->${units}`); }
    else if (/^止盈：/.test(m)) { cur.tp.push(d); }
  }
  after[d] = { held, units };
}
if (cur) { cur.to = S.dates.at(-1) + '(end)'; cur.exit = 'open'; periods.push(cur); }

// --- daily returns, chained (never difference percentages)
const ret = S.cum.map((c, i) => (1 + c / 100) / (1 + (i ? S.cum[i - 1] : 0) / 100) - 1);
const final = S.cum.at(-1);
console.log(`CONTROL curve final cum=${final} (expect 22.51) points=${S.cum.length} logDays=${vm.length}`);

// Attribution: convention A = day D credited to the holding AFTER D's 09:35 trade;
// convention B = credited to the holding at D-1 close (overnight gap belongs to the old book).
function attrib(conv) {
  const g = {};
  S.dates.forEach((d, i) => {
    const st = conv === 'A' ? after[d] : (i ? after[S.dates[i - 1]] : { held: null });
    const k = st.held || '(cash)';
    g[k] = g[k] || { lg: 0, n: 0 }; g[k].lg += Math.log1p(ret[i]); g[k].n++;
  });
  return g;
}
for (const conv of ['A', 'B']) {
  const g = attrib(conv);
  console.log(`ATTRIB conv=${conv} ` + Object.entries(g).map(([k, v]) => `${k}: ${((Math.exp(v.lg) - 1) * 100).toFixed(2)}% over ${v.n}d`).join(' | '));
}

console.log('PERIODS');
for (const p of periods) {
  const i0 = S.dates.indexOf(p.from), i1 = p.to.endsWith('(end)') ? S.dates.length - 1 : S.dates.indexOf(p.to);
  // conv A: days from..(to-1) inclusive (exit day credited to the next book)
  const endA = p.to.endsWith('(end)') ? i1 : i1 - 1;
  let lg = 0; for (let i = i0; i <= endA; i++) lg += Math.log1p(ret[i]);
  console.log(`  ${p.etf}\t${p.from}\t${p.to}\t${p.entry}/${p.exit}\tunits ${p.units0}->${p.maxUnits}\tadds[${p.adds.join(',')}]\ttp[${p.tp.join(',')}]\tret(A)=${((Math.exp(lg) - 1) * 100).toFixed(2)}%`);
}

// Sep window
const win = (a, b) => { let lg = 0, n = 0; S.dates.forEach((d, i) => { if (d >= a && d <= b) { lg += Math.log1p(ret[i]); n++; } }); return [(Math.exp(lg) - 1) * 100, n]; };
const [w, wn] = win('2024-09-23', '2024-10-08');
const tot = Math.log1p(final / 100), wl = Math.log1p(w / 100);
console.log(`SEPWIN 2024-09-23..10-08 ret=${w.toFixed(2)}% over ${wn}d; rest=${((Math.exp(tot - wl) - 1) * 100).toFixed(2)}%`);
console.log('SEPWIN holdings: ' + S.dates.filter(d => d >= '2024-09-23' && d <= '2024-10-08').map(d => `${d}:${after[d].held}@${after[d].units}U r=${(ret[S.dates.indexOf(d)] * 100).toFixed(2)}%`).join(' '));
