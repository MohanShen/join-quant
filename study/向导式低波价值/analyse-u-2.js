// Parses study/向导式低波价值/log-u-2.txt (u-2 probe, paged via study/小市值/pagelog.js) and prints
// the ATR-unit agreement rates, per-stage counts, PE-band binding, and the day-1 / 2024-11-04 lists.
const fs = require('fs');
const path = require('path');
const lines = fs.readFileSync(path.join(__dirname, 'log-u-2.txt'), 'utf8').split('\n');
const kv = s => Object.fromEntries([...s.matchAll(/(\w+)=(\S+)/g)].map(m => [m[1], m[2]]));
const rows = [], cnt = {}, lists = {}, order = [], open0 = [], closen = [], buyn = [], peu = {};
for (const l of lines) {
  const m = l.match(/ - INFO  - (\w+) (.*)$/);
  if (!m) continue;
  const [, tag, rest] = m;
  const o = kv(rest);
  if (tag === 'ATRU' || tag === 'ATRH') rows.push({ tag, ...o });
  else if (tag === 'CNT') { (cnt[o.date] = cnt[o.date] || {})[o.stage] = { n: +o.n, sz: +o.sz }; }
  else if (tag === 'LIST') { const k = o.date + '|' + o.stage; (lists[k] = lists[k] || []).push(...o.codes.split(',').filter(Boolean)); }
  // PEU is logged on BOTH full dates; keep day 1 only (the first date seen) — later lines must not overwrite it
  else if (tag === 'PEU') { if (!peu.__d) peu.__d = o.date; if (o.date === peu.__d) for (const it of (o.codes || '').split(',')) { const [c, p] = it.split(':'); if (c) peu[c] = p; } }
  else if (tag === 'ORDER') order.push(o);
  else if (tag === 'OPEN0') open0.push(o);
  else if (tag === 'CLOSEN') closen.push(o);
  else if (tag === 'BUYN') buyn.push(o);
}
const B = s => s === 'True';
function agree(sel, rs) {
  const out = {};
  for (const [name, f] of Object.entries(sel)) out[name] = (rs.filter(f).length / rs.length * 100).toFixed(1) + '%';
  return out;
}
const U = rows.filter(r => r.tag === 'ATRU'), H = rows.filter(r => r.tag === 'ATRH');
console.log('ATRU rows', U.length, 'ATRH rows', H.length);
console.log('xiaoyu(0.15) agreement:', agree({
  'yuan atr15<0.15': r => B(r.xiaoyu) === (+r.atr15 < 0.15),
  'yuan atr60<0.15': r => B(r.xiaoyu) === (+r.atr60 < 0.15),
  'rel15<0.15': r => B(r.xiaoyu) === (+r.rel15 < 0.15),
  'rel60<0.15': r => B(r.xiaoyu) === (+r.rel60 < 0.15),
}, U));
const all = U.concat(H);
console.log('dayu(0.35) agreement (ATRU+ATRH):', agree({
  'yuan atr15>0.35': r => B(r.dayu) === (+r.atr15 > 0.35),
  'yuan atr60>0.35': r => B(r.dayu) === (+r.atr60 > 0.35),
  'rel15>0.35': r => B(r.dayu) === (+r.rel15 > 0.35),
  'rel60>0.35': r => B(r.dayu) === (+r.rel60 > 0.35),
}, all));
console.log('xiaoyu True count', U.filter(r => B(r.xiaoyu)).length, 'dayu True (all)', all.filter(r => B(r.dayu)).length);
// disagreements under the best rule
const dis = U.filter(r => B(r.xiaoyu) !== (+r.atr15 < 0.15));
console.log('xiaoyu vs atr15 disagreements:', dis.length); for (const r of dis.slice(0, 15)) console.log('  ', r.date, r.code, r.atr15, r.atr60, r.xiaoyu);
const dis2 = all.filter(r => B(r.dayu) !== (+r.atr15 > 0.35));
console.log('dayu vs atr15 disagreements:', dis2.length); for (const r of dis2.slice(0, 15)) console.log('  ', r.tag, r.date, r.code, r.atr15, r.atr60, r.dayu);
// best fitting threshold on xiaoyu for atr15/atr60 (boundary)
for (const k of ['atr15', 'atr60']) {
  const t = U.filter(r => B(r.xiaoyu)).map(r => +r[k]), f = U.filter(r => !B(r.xiaoyu)).map(r => +r[k]);
  console.log(k, 'xiaoyu=True max', Math.max(...t).toFixed(4), ' xiaoyu=False min', Math.min(...f).toFixed(4));
}
for (const k of ['atr15', 'atr60']) {
  const t = all.filter(r => B(r.dayu)).map(r => +r[k]), f = all.filter(r => !B(r.dayu)).map(r => +r[k]);
  console.log(k, 'dayu=True min', t.length ? Math.min(...t).toFixed(4) : '-', ' dayu=False max', Math.max(...f).toFixed(4));
}
// close of xiaoyu-True names
const tc = U.filter(r => B(r.xiaoyu)).map(r => +r.close).sort((a, b) => a - b);
const fc = U.filter(r => !B(r.xiaoyu)).map(r => +r.close).sort((a, b) => a - b);
const q = (a, p) => a[Math.floor(p * (a.length - 1))];
console.log('close | xiaoyu True: min', tc[0], 'med', q(tc, .5), 'max', tc[tc.length - 1], ' | False: min', fc[0], 'med', q(fc, .5), 'max', fc[fc.length - 1]);
const rel = U.filter(r => B(r.xiaoyu)).map(r => +r.rel15).sort((a, b) => a - b);
console.log('rel15 of xiaoyu-True: min', rel[0], 'max', rel[rel.length - 1]);

// stage counts
const dates = Object.keys(cnt).sort();
const stagesAll = ['universe', 'industry', 'concept', 'st', 'delisted', 'pe', 'sort', 'b_in', 'b_st', 'b_paused', 'b_delisted', 'b_highlimit', 'b_atr'];
console.log('\ncheck dates', dates.length);
console.log(['date', ...stagesAll].join('\t'));
for (const d of dates) console.log([d, ...stagesAll.map(s => cnt[d][s] ? `${cnt[d][s].n}/${cnt[d][s].sz}` : '-')].join('\t'));
const dist = s => { const v = dates.map(d => cnt[d][s] && cnt[d][s].n).filter(x => x != null).sort((a, b) => a - b); return `min ${v[0]} med ${q(v, .5)} max ${v[v.length - 1]}`; };
for (const s of stagesAll) console.log('dist', s, dist(s));
// PE band binding after ATR gate: of ATR-passing names among delisted-stage survivors on full dates
for (const d of [dates[0], '2024-11-04']) {
  const del = lists[d + '|delisted'] || [], pe = lists[d + '|pe'] || [], atr = lists[d + '|b_atr'] || [];
  console.log(`\n${d}: delisted ${del.length} -> pe ${pe.length}; b_atr ${atr.length}`);
  console.log('  pe-stage order preserved vs delisted order?', JSON.stringify(pe) === JSON.stringify(del.filter(c => pe.includes(c))));
  console.log('  pe list:', pe.join(','));
  console.log('  b_highlimit:', (lists[d + '|b_highlimit'] || []).join(','));
  console.log('  b_atr:', atr.join(','));
  const sz = del.filter(c => c.endsWith('XSHE'));
  const szBand = sz.filter(c => peu[c] !== 'NA' && +peu[c] >= 6 && +peu[c] <= 11);
  if (d === dates[0]) console.log('  day1 SZ in delisted', sz.length, 'SZ with PEU in [6,11]', szBand.length, szBand.map(c => c + ':' + peu[c]).join(','));
  for (const st of ['universe', 'industry', 'concept', 'st', 'delisted', 'pe']) console.log('  ', st, (lists[d + '|' + st] || []).length, 'sz', (lists[d + '|' + st] || []).filter(c => c.endsWith('XSHE')).length);
  const urows = U.filter(r => r.date === d);
  console.log('  ATRU rows', urows.length);
  for (const r of urows) console.log('    ', r.code, 'close', r.close, 'atr15', r.atr15, 'rel15', r.rel15, 'pe', r.pe, 'x', r.xiaoyu);
}
// universe-to-industry drops on day 1
const d0 = dates[0];
const uni = lists[d0 + '|universe'] || [], ind = lists[d0 + '|industry'] || [];
const dropped = uni.filter(c => !ind.includes(c));
console.log('\nday1 industry dropped', dropped.length, 'sz', dropped.filter(c => c.endsWith('XSHE')).length);
console.log('day1 universe SZ names with PE in band:', uni.filter(c => c.endsWith('XSHE') && peu[c] && peu[c] !== 'NA' && +peu[c] >= 6 && +peu[c] <= 11).join(','));
console.log('\nORDER'); for (const o of order) console.log(' ', o.date, o.n, o.codes);
console.log('BUYN'); for (const o of buyn) if (o.codes) console.log(' ', o.date, o.num, o.codes);
console.log('OPEN0'); for (const o of open0) console.log(' ', o.date, o.code, o.open);
console.log('CLOSEN'); for (const o of closen) console.log(' ', o.date, o.code, o.ah_close, o.ah_date, o.last_price, o.held);
// does PE band bind on ATR survivors: ATR-passing names with PE outside band would only exist if PE ran after; instead count
// ATR-pass among highlimit-stage per date
