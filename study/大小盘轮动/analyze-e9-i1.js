// e9-i1 readout: curve + signal comparison vs base (2f5bc859 e9), u2 (base+logging) and i3.
// Usage: node -e "require('./study/大小盘轮动/analyze-e9-i1.js')"
const fs = require('fs');
const path = require('path');
const R = path.join(__dirname, '../..') + '/';
const S = R + 'data/series/';
const V = __dirname + '/variants/';
const files = {
  base: '2026-05-20_四择时高息低价小市值和白马大市值轮动-2f5bc859__train__e9.json',
  u2: 'study_大小盘轮动_variants_u2-e9_signal-log__train__e9.json',
  i3: 'study_大小盘轮动_variants_i3-e9_no-s2__train__e9.json',
  i1: 'study_大小盘轮动_variants_i1-e9_tie-s3__train__e9.json',
};
const c = {};
for (const [k, f] of Object.entries(files)) {
  const j = JSON.parse(fs.readFileSync(S + f, 'utf8'));
  c[k] = { d: j.dates, v: j.cum.map(Number) };
}
const nav = x => 1 + x / 100;
function stats(k, from, to) {
  const { d, v } = c[k];
  let prev = 1, peak = 1, mdd = 0, pk = null, tr = null, curPk = null, s = null, e = null;
  for (let i = 0; i < d.length; i++) {
    const n = nav(v[i]);
    if (d[i] >= from && d[i] <= to) {
      if (s === null) { s = prev; peak = prev; curPk = d[i - 1] || 'start'; }
      if (n > peak) { peak = n; curPk = d[i]; }
      const dd = 1 - n / peak; if (dd > mdd) { mdd = dd; pk = curPk; tr = d[i]; }
      e = n;
    }
    prev = n;
  }
  return { ret: (e / s - 1) * 100, mdd: mdd * 100, pk, tr };
}
const maxdiff = (a, b) => Math.max(...c[a].v.map((x, i) => Math.abs(x - c[b].v[i])));
console.log('max|Δcum| u2 vs base', maxdiff('u2', 'base'), ' i1 vs base', maxdiff('i1', 'base'));
const firstDiff = (a, b) => c[a].d.find((_, i) => Math.abs(c[a].v[i] - c[b].v[i]) > 1e-9);
console.log('first day i1 != base', firstDiff('i1', 'base'), '| first day i1 != i3', firstDiff('i1', 'i3'));
for (const k of ['base', 'i3', 'i1']) {
  const all = stats(k, '2024-01-01', '2024-12-31'), jf = stats(k, '2024-01-01', '2024-02-29');
  console.log(k, 'final', c[k].v.at(-1), 'mdd', all.mdd.toFixed(2), all.pk, '->', all.tr, '| Jan-Feb ret', jf.ret.toFixed(2), 'dd', jf.mdd.toFixed(2), jf.pk, '->', jf.tr);
}
console.log('month   base     i3      i1     i1-base');
for (let m = 1; m <= 12; m++) {
  const mm = String(m).padStart(2, '0');
  const r = ['base', 'i3', 'i1'].map(k => stats(k, `2024-${mm}-01`, `2024-${mm}-31`).ret);
  console.log(mm, r.map(x => x.toFixed(2).padStart(7)).join(' '), (r[2] - r[0]).toFixed(2).padStart(7));
}
const sig = f => {
  const m = {};
  for (const l of fs.readFileSync(V + f, 'utf8').split('\n')) {
    const x = l.match(/^(\S+) .*SIGDAY s1=(\S+) s2=(\S+) s3=(\S+) final=(\S+) prev=(\S+)/);
    if (x) m[x[1]] = { s1: x[2], s2: x[3], s3: x[4], final: x[5], prev: x[6] };
  }
  return m;
};
const a = sig('u2-e9_signal-log.log.txt'), b = sig('i1-e9_tie-s3.log.txt');
const days = [...new Set([...Object.keys(a), ...Object.keys(b)])].sort();
console.log('SIGDAY days base', Object.keys(a).length, 'i1', Object.keys(b).length);
for (const d of days) {
  const x = a[d], y = b[d];
  if (!x || !y || x.final !== y.final) console.log('DIFF', d, 'base', x ? `${x.s1}/${x.s2}/${x.s3}->${x.final}` : '-', '| i1', y ? `${y.s1}/${y.s2}/${y.s3}->${y.final}` : '-');
}
const mon = f => fs.readFileSync(V + f, 'utf8').split('\n').filter(l => /MONTHLY|DAPAN/.test(l)).map(l => l.slice(0, 10) + ' ' + l.replace(/.*INFO  - /, '').replace(/  # .*/, ''));
const ma = mon('u2-e9_signal-log.log.txt'), mb = mon('i1-e9_tie-s3.log.txt');
console.log('--- MONTHLY/DAPAN lines differing (base=u2 vs i1)');
const sa = new Set(ma), sb = new Set(mb);
ma.filter(l => !sb.has(l)).forEach(l => console.log('base only:', l));
mb.filter(l => !sa.has(l)).forEach(l => console.log('i1   only:', l));
