// Monthly returns + maxDD window from stored epoch-9 TRAIN curves. Read-only.
// Usage: node study/小市值/curve-months.js <tag> [<tag> ...]
const fs = require('fs'), path = require('path');
const dir = path.join(__dirname, '../../data/series');
function main(tags) {
for (const t of tags) {
  const f = fs.readdirSync(dir).find(x => x.includes(t) && x.includes('__train__e9'));
  if (!f) { console.log(t, 'NO CURVE'); continue; }
  const r = JSON.parse(fs.readFileSync(path.join(dir, f)));
  const d = r.dates || r.time, c = r.cum || r.value;
  if (!d || !c) { console.log(t, 'keys', Object.keys(r)); continue; }
  const nav = c.map(x => 1 + x / 100);
  const monthEnd = {};
  d.forEach((x, i) => { monthEnd[x.slice(0, 7)] = i; });
  const ms = Object.keys(monthEnd).sort(), mret = {};
  let prev = 1;
  for (const m of ms) { const v = nav[monthEnd[m]]; mret[m] = ((v / prev - 1) * 100).toFixed(2); prev = v; }
  let pk = 1, pkd = 'start', mdd = 0, w = null;
  nav.forEach((v, i) => { if (v > pk) { pk = v; pkd = d[i]; } const dd = 1 - v / pk; if (dd > mdd) { mdd = dd; w = [pkd, d[i]]; } });
  console.log(t, 'n', d.length, d[0], d[d.length - 1], 'final', c[c.length - 1], 'bt', r.backtestId,
    '| Jan', mret['2024-01'], 'Feb', mret['2024-02'], 'Apr', mret['2024-04'],
    '| maxDD', (mdd * 100).toFixed(2), w && w.join('->'));
  console.log('   ', ms.map(m => m.slice(5) + ':' + mret[m]).join(' '));
}
}
function load(t) {
  const f = fs.readdirSync(dir).find(x => x.includes(t) && x.includes('__train__e9'));
  return JSON.parse(fs.readFileSync(path.join(dir, f)));
}
// max |Δcum| between two stored curves, date-aligned
function cmp(a, b) {
  const A = load(a), B = load(b);
  const m = new Map(B.dates.map((d, i) => [d, B.cum[i]]));
  let mx = 0, n = 0;
  A.dates.forEach((d, i) => { if (m.has(d)) { n++; mx = Math.max(mx, Math.abs(A.cum[i] - m.get(d))); } });
  console.log(a, 'vs', b, 'common', n, 'max|dcum|', mx);
}
// comment/blank-stripped line diff between two strategy files
function strip(file) {
  return fs.readFileSync(file, 'utf8').split('\n')
    .map(l => l.replace(/#.*$/, '').trimEnd()).filter(l => l.trim());
}
function codeDiff(fa, fb) {
  const A = strip(fa), B = strip(fb);
  console.log('lines', A.length, B.length);
  const sa = new Set(A), sb = new Set(B);
  const onlyA = A.map((l, i) => [i, l]).filter(([, l]) => !sb.has(l));
  const onlyB = B.map((l, i) => [i, l]).filter(([, l]) => !sa.has(l));
  console.log('onlyA', onlyA.length); onlyA.slice(0, 40).forEach(x => console.log('  A', x[0], x[1].slice(0, 160)));
  console.log('onlyB', onlyB.length); onlyB.slice(0, 40).forEach(x => console.log('  B', x[0], x[1].slice(0, 160)));
  let same = A.length === B.length && A.every((l, i) => l === B[i]);
  console.log('identical in order:', same);
}
// postedAt by exact title match in data/discovered.json
function posted(titles) {
  const raw = JSON.parse(fs.readFileSync(path.join(__dirname, '../../data/discovered.json'), 'utf8'));
  const recs = [];
  (function walk(o) {
    if (Array.isArray(o)) return o.forEach(walk);
    if (o && typeof o === 'object') {
      if (typeof o.title === 'string' && ('postedAt' in o || 'addTime' in o)) recs.push(o);
      Object.values(o).forEach(v => { if (v && typeof v === 'object') walk(v); });
    }
  })(raw);
  for (const t of titles) {
    const hit = recs.filter(r => r.title === t);
    console.log(JSON.stringify(t), hit.length, hit.map(r => r.postedAt || r.addTime).join(' , '));
  }
}
// fdf13c81 vs 954f1d36: ordered compare after removing 954f1d36's MACD-顶背离 layer
function dropMacd(fa, fb) {
  const st = f => fs.readFileSync(f, 'utf8').split('\n').map(l => l.replace(/#.*$/, '').trim()).filter(l => l);
  const A = st(fa); let B = st(fb);
  const s = B.indexOf('def doDecide(stock,context):');
  const e = B.findIndex((l, i) => i > s && l.startsWith('def ') && !l.startsWith('def dapan'));
  console.log('block', s, e, B[e], 'docstring', B.slice(0, 7).join(' / '));
  const drop = new Set(['g.dbl=[]', "run_daily(dapan, '9:30')", 'if True not in g.dbl[-20:]:']);
  B = B.filter((l, i) => !(i < 7 || (i >= s && i < e) || drop.has(l)));
  console.log(A.length, B.length);
  let d = 0;
  for (let i = 0; i < Math.max(A.length, B.length); i++) if (A[i] !== B[i]) { d++; if (d < 8) console.log(i, 'A:', A[i], '| B:', B[i]); }
  console.log('diffs', d);
}
function grepTag(tag, reSrc, max) {
  const S = fs.readdirSync(path.join(__dirname, '../../strategies'));
  const f = path.join(__dirname, '../../strategies', S.find(x => x.includes(tag)));
  const re = new RegExp(reSrc);
  const L = fs.readFileSync(f, 'utf8').split('\n');
  console.log('==', tag, L.length, 'lines');
  let n = 0;
  L.forEach((l, i) => { if (re.test(l) && n++ < (max || 80)) console.log(i + 1, l.trim().slice(0, 170)); });
}
// body of `def <name>` (comment/blank-stripped, trimmed) from the strategy whose filename holds tag
function fnBody(tag, name) {
  const S = fs.readdirSync(path.join(__dirname, '../../strategies'));
  const hit = S.find(x => x.includes(tag));
  if (!hit) return null;
  const L = fs.readFileSync(path.join(__dirname, '../../strategies', hit), 'utf8').split('\n');
  const s = L.findIndex(l => new RegExp('^def ' + name + '\\(').test(l));
  if (s < 0) return null;
  let e = L.findIndex((l, i) => i > s && /^\S/.test(l) && !/^#/.test(l));
  if (e < 0) e = L.length;
  return { line: s + 1, body: L.slice(s, e).map(l => l.replace(/#.*$/, '').trim()).filter(Boolean) };
}
function sameFn(name, tags) {
  const ref = fnBody(tags[0], name);
  for (const t of tags) {
    const b = fnBody(t, name);
    if (!b) { console.log(name, t, 'ABSENT'); continue; }
    const same = ref && b.body.join('\n') === ref.body.join('\n');
    console.log(name, t, 'L' + b.line, b.body.length, 'lines', same ? 'IDENTICAL to ' + tags[0] : 'differs');
  }
}
function fnDiff(name, a, b) {
  const A = fnBody(a, name), B = fnBody(b, name);
  if (!A || !B) { console.log(name, a, b, 'absent', !!A, !!B); return; }
  const sb = new Set(B.body), sa = new Set(A.body);
  console.log('--', name, a, 'L' + A.line, 'vs', b, 'L' + B.line);
  A.body.filter(l => !sb.has(l)).forEach(l => console.log('  only', a, l.slice(0, 150)));
  B.body.filter(l => !sa.has(l)).forEach(l => console.log('  only', b, l.slice(0, 150)));
}
// share of A's stripped code lines that appear anywhere in B
function overlap(a, b) {
  const S = fs.readdirSync(path.join(__dirname, '../../strategies'));
  const rd = t => fs.readFileSync(path.join(__dirname, '../../strategies', S.find(x => x.includes(t))), 'utf8')
    .split('\n').map(l => l.replace(/#.*$/, '').trim()).filter(l => l.length > 3);
  const A = rd(a), sb = new Set(rd(b));
  console.log(a, 'in', b, A.filter(l => sb.has(l)).length + '/' + A.length);
}
module.exports = { main, cmp, codeDiff, posted, dropMacd, grepTag, sameFn, fnBody, fnDiff, overlap };
if (require.main === module) main(process.argv.slice(2));
