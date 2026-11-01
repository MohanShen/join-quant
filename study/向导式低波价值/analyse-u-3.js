// Parses study/向导式低波价值/log-u-3.txt (u-3, paged via study/小市值/pagelog.js): order-error classes,
// day-1 POOL0 fills, per-name day-1 -> final price return (gate 6 vs non-gate 20), late-entry dust,
// and daily-return correlation of the u-3 curve vs u-7 and vs the base.
const fs = require('fs');
const path = require('path');
const S = require('../../utils/backtest-series');
const L = fs.readFileSync(path.join(__dirname, 'log-u-3.txt'), 'utf8').split('\n');
const err = {}, errCodes = {};
for (const l of L) {
  if (!/ERROR/.test(l)) continue;
  const m = l.match(/error=([^)]*)/); const k = (m ? m[1] : '?').replace(/\d[\d.]*/g, 'N');
  err[k] = (err[k] || 0) + 1;
  const c = (l.match(/security=(\S+)/) || [])[1]; const a = (l.match(/_amount=(\d+)/) || [])[1];
  (errCodes[k] = errCodes[k] || new Set()).add(c + (a === '0' ? '(amt0)' : ''));
}
console.log('ERR', err);
for (const k in errCodes) console.log('  ', k.slice(0, 40), [...errCodes[k]].join(' '));
const fill0 = {}, fin = {};
for (const l of L) {
  let m = l.match(/EWFILL date=2024-01-02 code=(\S+) .*filled=(\d+) price=([\d.]+)/);
  if (m) fill0[m[1]] = { f: +m[2], p: +m[3] };
  m = l.match(/EWFINAL date=\S+ code=(\S+) amount=(\d+) avg_cost=([\d.]+) price=([\d.]+) value=([\d.]+)/);
  if (m) fin[m[1]] = { a: +m[2], c: +m[3], p: +m[4], v: +m[5] };
}
const gate = ['600018.XSHG', '601006.XSHG', '601117.XSHG', '601319.XSHG', '601669.XSHG', '601800.XSHG'];
const rows = Object.keys(fill0).map(c => ({ c, gate: gate.includes(c), p0: fill0[c].p, filled: fill0[c].f, p1: fin[c] ? fin[c].p : null,
  r: fin[c] && fill0[c].p ? (fin[c].p / fill0[c].p - 1) * 100 : null }));
rows.sort((a, b) => (b.r ?? -1e9) - (a.r ?? -1e9));
for (const r of rows) console.log(r.c, r.gate ? 'GATE' : '    ', r.p0, r.p1, r.r == null ? 'n/a(unfilled)' : r.r.toFixed(1));
const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
const med = a => { const s = a.slice().sort((x, y) => x - y); return (s[(s.length - 1) >> 1] + s[s.length >> 1]) / 2; };
const g = rows.filter(r => r.gate && r.r != null).map(r => r.r), n = rows.filter(r => !r.gate && r.r != null).map(r => r.r);
console.log('gate n', g.length, 'mean', mean(g).toFixed(2), 'median', med(g).toFixed(2), '| non-gate filled n', n.length, 'mean', mean(n).toFixed(2), 'median', med(n).toFixed(2));
const sz = rows.filter(r => /XSHE/.test(r.c) && r.r != null).map(r => r.r);
console.log('SZ n', sz.length, 'mean', mean(sz).toFixed(2));
const extra = Object.keys(fin).filter(c => !fill0[c] || fill0[c].f === 0);
const tot = Object.values(fin).reduce((s, x) => s + x.v, 0);
console.log('final names', Object.keys(fin).length, '| non-day1 names', extra.length, '| value share', (extra.reduce((s, c) => s + fin[c].v, 0) / tot * 100).toFixed(2) + '%');
console.log('  ', extra.map(c => c + ':' + (fin[c].v / tot * 100).toFixed(2)).join(' '));
const u3 = S.load('study_向导式低波价值_variants_u-3__train__e9');
const u7 = S.load('study_向导式低波价值_variants_u-7__train__e9');
const b = S.load('2026-10-29_向导式_ATR指标择时测试_0_0_1-8b9cb8e2__train__e9');
console.log('corr u3-u7', JSON.stringify(S.correlate(u3, u7)));
console.log('corr u3-base', JSON.stringify(S.correlate(u3, b)));
console.log('corr u7-base', JSON.stringify(S.correlate(u7, b)));
