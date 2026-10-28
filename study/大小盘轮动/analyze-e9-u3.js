// e9-u3 readout: curve + month-start signal comparison vs base (2f5bc859 e9; signals from u2 log) and i3.
// Usage: node -e "require('./study/大小盘轮动/analyze-e9-u3.js')"
const fs = require('fs');
const path = require('path');
const S = path.join(__dirname, '../..') + '/data/series/';
const V = __dirname + '/variants/';
const files = {
  base: '2026-05-20_四择时高息低价小市值和白马大市值轮动-2f5bc859__train__e9.json',
  i3: 'study_大小盘轮动_variants_i3-e9_no-s2__train__e9.json',
  u3: 'study_大小盘轮动_variants_u3-e9_s3-only__train__e9.json',
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
const firstDiff = (a, b) => c[a].d.find((_, i) => Math.abs(c[a].v[i] - c[b].v[i]) > 1e-9);
console.log('points', c.u3.d.length, c.u3.d[0], c.u3.d.at(-1), '| first day u3 != base', firstDiff('u3', 'base'), '| != i3', firstDiff('u3', 'i3'));
for (const k of ['base', 'i3', 'u3']) {
  const all = stats(k, '2024-01-01', '2024-12-31');
  const jf = stats(k, '2024-01-01', '2024-02-29');
  const st = stats(k, '2024-01-04', '2024-02-07');
  console.log(k, 'total', c[k].v.at(-1).toFixed(2), 'mdd', all.mdd.toFixed(2), all.pk, '->', all.tr,
    '| Jan-Feb ret', jf.ret.toFixed(2), 'dd', jf.mdd.toFixed(2), jf.pk, '->', jf.tr,
    '| 01-04..02-07 ret', st.ret.toFixed(2), 'dd', st.mdd.toFixed(2), st.pk, '->', st.tr);
}
console.log('month   base      i3      u3  u3-base   u3-i3 | mdd base / i3 / u3');
for (let m = 1; m <= 12; m++) {
  const mm = String(m).padStart(2, '0');
  const r = ['base', 'i3', 'u3'].map(k => stats(k, `2024-${mm}-01`, `2024-${mm}-31`));
  console.log(mm, r.map(x => x.ret.toFixed(2).padStart(7)).join(' '), (r[2].ret - r[0].ret).toFixed(2).padStart(8),
    (r[2].ret - r[1].ret).toFixed(2).padStart(7), '|', r.map(x => x.mdd.toFixed(2)).join(' / '));
}
const sig = f => {
  const m = {};
  for (const l of fs.readFileSync(V + f, 'utf8').split('\n')) {
    const x = l.match(/^(\S+) .*SIGDAY s1=(\S+) s2=(\S+) s3=(\S+) final=(\S+) prev=(\S+)/);
    if (x) m[x[1]] = { s1: x[2], s2: x[3], s3: x[4], final: x[5] };
  }
  return m;
};
const mon = f => fs.readFileSync(V + f, 'utf8').split('\n').filter(l => /09:30:10.*MONTHLY/.test(l)).map(l => l.slice(0, 10));
const A = sig('u2-e9_signal-log.log.txt'), I = sig('i3-e9_no-s2.log.txt'), U = sig('u3-e9_s3-only.log.txt');
const days = mon('u3-e9_s3-only.log.txt');
console.log('month-start: base(s1/s2/s3->final) | i3 | u3');
for (const d of days) {
  const f = x => x ? `${x.s1}/${x.s2}/${x.s3}->${x.final}` : '-';
  console.log(d, f(A[d]), '|', f(I[d]), '|', f(U[d]), (A[d] && U[d] && A[d].final !== U[d].final) ? '  <-- differs from base' : '');
}
let s3same = 0, n = 0;
for (const d of Object.keys(U)) if (A[d]) { n++; if (A[d].s3 === U[d].s3) s3same++; }
console.log('s3 vote identical to base on', s3same, 'of', n, 'days; u3 final=empty days', Object.values(U).filter(x => x.final === 'empty').length,
  '; u3 s3=empty days', Object.values(U).filter(x => x.s3 === 'empty').length);
const dap = f => fs.readFileSync(V + f, 'utf8').split('\n').filter(l => /DAPAN/.test(l)).map(l => l.slice(0, 10));
console.log('DAPAN base', dap('u2-e9_signal-log.log.txt').join(','), '| i3', dap('i3-e9_no-s2.log.txt').join(','), '| u3', dap('u3-e9_s3-only.log.txt').join(','));
