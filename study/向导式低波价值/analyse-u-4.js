// analyse-u-4.js — reads log-u-4.txt: day-1 set with PE/close, per-name day-1 fill -> 12-31 price
// return grouped by PE band, and the per-date gate admission counts (U4CNT).
const fs = require('fs');
const path = require('path');
const L = fs.readFileSync(path.join(__dirname, 'log-u-4.txt'), 'utf8').split('\n');
const kv = s => Object.fromEntries([...s.matchAll(/(\w+)=(\S+)/g)].map(m => [m[1], m[2]]));
const pe = {}, fill = {}, fin = {}, cnt = [];
let d1 = null;
for (const l of L) {
  if (l.includes('U4CNT ')) cnt.push(+kv(l.split('U4CNT ')[1]).n);
  if (l.includes('U4PE ')) { const o = kv(l.split('U4PE ')[1]); if (!d1) d1 = o.date; if (o.date === d1) pe[o.code] = o; }
  if (l.includes('EWFILL ')) { const o = kv(l.split('EWFILL ')[1]); if (o.date === d1) fill[o.code] = o; }
  if (l.includes('EWFINAL ')) { const o = kv(l.split('EWFINAL ')[1]); fin[o.code] = o; }
}
const U7 = ['600018.XSHG', '601006.XSHG', '601117.XSHG', '601319.XSHG', '601669.XSHG', '601800.XSHG'];
const rows = Object.values(pe).map(o => {
  const f = fill[o.code] || {}; const z = fin[o.code];
  const p0 = +f.price, p1 = z ? +z.price : NaN;
  return { code: o.code, pe: o.pe === 'NA' ? NaN : +o.pe, close: +o.close, inband: o.inband === 'True',
    filled: +f.filled || 0, ret: (p1 / p0 - 1) * 100, u7: U7.includes(o.code) };
});
rows.sort((a, b) => a.pe - b.pe);
for (const r of rows) console.log([r.code, r.pe.toFixed(2), r.close.toFixed(2), r.inband ? 'IN' : 'out', r.u7 ? 'u7' : '', r.filled, isFinite(r.ret) ? r.ret.toFixed(1) : 'NA'].join('\t'));
const st = a => {
  const v = a.map(r => r.ret).filter(isFinite).sort((x, y) => x - y);
  if (!v.length) return 'n=0';
  const m = v.reduce((s, x) => s + x, 0) / v.length;
  const med = v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2;
  return `n=${v.length} mean=${m.toFixed(2)} median=${med.toFixed(1)}`;
};
const g = {
  inband: rows.filter(r => r.inband), 'inband-u7': rows.filter(r => r.u7), 'inband-not-u7': rows.filter(r => r.inband && !r.u7),
  out: rows.filter(r => !r.inband), 'pe0-6': rows.filter(r => !r.inband && r.pe >= 0 && r.pe < 6),
  'pe>11': rows.filter(r => r.pe > 11), 'pe<0': rows.filter(r => r.pe < 0), 'pe-NA': rows.filter(r => isNaN(r.pe)), all: rows,
};
for (const k in g) console.log(k, st(g[k]));
console.log('688:', rows.filter(r => r.code.startsWith('688')).map(r => r.code + ' filled=' + r.filled).join(' ') || 'none');
console.log('SZ:', rows.filter(r => r.code.endsWith('XSHE')).length, 'unfilled:', rows.filter(r => !r.filled).map(r => r.code).join(' ') || 'none');
console.log('u7 names missing from day1:', U7.filter(c => !pe[c]).join(',') || 'none');
const s = [...cnt].sort((a, b) => a - b);
console.log('U4CNT dates', cnt.length, 'min', s[0], 'median', s[Math.floor(s.length / 2)], 'max', s[s.length - 1]);
