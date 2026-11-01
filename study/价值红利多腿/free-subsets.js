// q-e9-free-subsets (zero backtests): sleeve-subset table on the post-orphan-fix reference by curve
// subtraction. s2/s4 split from q-e9-div-only's own 持仓/交易/日志 (sleeve tag = ownership).
// Usage: node -e "require('./study/价值红利多腿/free-subsets.js').main()"
const fs = require('fs');
const path = require('path');
const D = __dirname;
const SER = path.join(D, '..', '..', 'data', 'series') + '/';
const { sh } = require('./orphan-fix-curves.js');
const L = k => JSON.parse(fs.readFileSync(SER + k + '__train__e9.json', 'utf8'));
const V = 'study_价值红利多腿_variants_';
const INIT = 1e6;
const codeOf = s => { const m = String(s).match(/(\d{6}\.XS\w\w)/); return m ? m[1] : null; };
const num = s => parseFloat(String(s).replace(/[^\d.\-]/g, ''));

function main() {
  const fix = L(V + 'q-e9-orphan-fix'), s1 = L(V + 'q-e9-s1-only'), dv = L(V + 'q-e9-div-only'), pbm = L('enhance_candidates_pbm-e9-2');
  const log = fs.readFileSync(path.join(D, 'log-q-e9-div-only.txt'), 'utf8').split('\n');
  const fills = [];
  for (const l of log) {
    const m = l.match(/^(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d) - INFO\s+- \[(s\d)\]\[(买入|卖出)\] (\S+) amt=(\d+) px=([\d.]+) val=([\d.]+)/);
    if (m) fills.push({ d: m[1], t: m[2], sid: m[3], side: m[4] === '买入' ? 'B' : 'S', code: m[5], amt: +m[6] });
  }
  const T = JSON.parse(fs.readFileSync(path.join(D, 'tx-q-e9-div-only.json'), 'utf8'));
  const used = new Set();
  for (const f of fills) {
    const i = T.findIndex((t, k) => !used.has(k) && t.date === f.d && t.time === f.t && codeOf(t.stock) === f.code &&
      (t.transaction === '买') === (f.side === 'B') && Math.abs(num(t.amount)) === f.amt);
    if (i < 0) throw new Error('nofill ' + JSON.stringify(f));
    used.add(i); f.comm = +T[i].commission; f.total = Math.abs(+T[i].total);
  }
  console.log('fills', fills.length, 'tx', T.length, 'unmatched tx', T.length - used.size, 'sleeves', [...new Set(fills.map(f => f.sid))]);
  const owner = {}; for (const f of fills) (owner[f.code] = owner[f.code] || new Set()).add(f.sid);
  console.log('shared codes', Object.entries(owner).filter(([, s]) => s.size > 1).map(x => x[0]));
  const P = JSON.parse(fs.readFileSync(path.join(D, 'pos-q-e9-div-only.json'), 'utf8'));
  const days = new Map();
  for (const r of P) {
    const d = days.get(r.date) || { pos: {}, cash: null }; days.set(r.date, d);
    const c = codeOf(r.stock);
    if (c) d.pos[c] = { v: +r.value, a: num(r.amount), ac: num(r.avgCost) }; else if (/Cash/.test(r.stock)) d.cash = +r.value;
  }
  const ds = dv.dates;
  const pnl = { s2: [], s4: [] }, acc = { s2: 0, s4: 0 };
  let prev = { pos: {}, cash: INIT }, unalloc = 0, tvErr = 0, nev = 0; const sleeveBook = {}; let exactN = 0;
  for (let i = 0; i < ds.length; i++) {
    const d = ds[i], cur = days.get(d); if (!cur) throw new Error('no day ' + d);
    const fl = fills.filter(f => f.d === d);
    const flow = fl.reduce((s, f) => s + (f.side === 'S' ? f.total : -f.total) - f.comm, 0);
    const resid = (cur.cash - prev.cash) - flow;
    const codes = new Set([...Object.keys(prev.pos), ...Object.keys(cur.pos)]);
    const dsl = { s2: 0, s4: 0 };
    // sleeve share of a code's value: by sleeve-ledger shares (from tagged fills); a code held by one
    // sleeve only (the shared 600398 never overlaps in time) gets the whole real value incl. any 送转.
    const frac = (c, book) => { const h = book[c] || {}; const tot = (h.s2 || 0) + (h.s4 || 0); return tot ? { s2: (h.s2 || 0) / tot, s4: (h.s4 || 0) / tot } : null; };
    const before = JSON.parse(JSON.stringify(sleeveBook));
    for (const f of fl) { const h = sleeveBook[f.code] = sleeveBook[f.code] || {}; h[f.sid] = (h[f.sid] || 0) + (f.side === 'B' ? f.amt : -f.amt); }
    for (const c of codes) {
      if (!owner[c]) throw new Error('unowned ' + c);
      const v0 = prev.pos[c] ? prev.pos[c].v : 0, v1 = cur.pos[c] ? cur.pos[c].v : 0;
      const f0 = frac(c, before), f1 = frac(c, sleeveBook);
      if (v0 && !f0) throw new Error('value with no sleeve ' + c + ' ' + d);
      if (v1 && !f1) throw new Error('value with no sleeve ' + c + ' ' + d);
      for (const s of ['s2', 's4']) dsl[s] += (f1 ? v1 * f1[s] : 0) - (f0 ? v0 * f0[s] : 0);
      for (const f of fl.filter(f => f.code === c)) dsl[f.sid] += (f.side === 'S' ? f.total : -f.total) - f.comm;
    }
    if (Math.abs(resid) > 0.5) {
      nev++;
      const held = Object.keys(prev.pos), W = held.reduce((s, c) => s + prev.pos[c].v, 0);
      const sids = new Set(held.flatMap(c => Object.entries(before[c] || {}).filter(([, a]) => a > 0).map(([s]) => s)));
      // exact name: JQ lowers avgCost by the gross dividend on the credit day (attrib.js rule)
      const traded = new Set(fl.map(f => f.code));
      const exact = Object.keys(cur.pos).filter(c => prev.pos[c] && !traded.has(c) && cur.pos[c].a * cur.pos[c].ac < prev.pos[c].a * prev.pos[c].ac - 1);
      if (exact.length === 1) { const f0 = frac(exact[0], before); for (const s of ['s2', 's4']) dsl[s] += resid * f0[s]; exactN++; }
      else if (sids.size === 1) dsl[[...sids][0]] += resid;
      else { for (const c of held) { const f0 = frac(c, before); for (const s of ['s2', 's4']) dsl[s] += resid * prev.pos[c].v / W * f0[s]; } unalloc += Math.abs(resid); }
    }
    acc.s2 += dsl.s2; acc.s4 += dsl.s4; pnl.s2.push(acc.s2 / INIT * 100); pnl.s4.push(acc.s4 / INIT * 100);
    const tv = cur.cash + Object.values(cur.pos).reduce((s, x) => s + x.v, 0);
    tvErr = Math.max(tvErr, Math.abs((tv / INIT - 1) * 100 - dv.cum[i]));
    prev = cur;
  }
  let res = 0; ds.forEach((d, i) => { res = Math.max(res, Math.abs(pnl.s2[i] + pnl.s4[i] - dv.cum[i])); });
  console.log('split: s2 final pp', pnl.s2.at(-1).toFixed(2), 's4', pnl.s4.at(-1).toFixed(2), 'div', dv.cum.at(-1),
    'max|s2+s4-div| pp', res.toFixed(4), 'tvErr', tvErr.toFixed(4), 'cash events', nev, 'exact-named', exactN, 'multi-sleeve cash events abs ¥', unalloc.toFixed(0));
  const st = o => { const { rets, ...x } = o; x.objective = +((x.annual - x.maxdd) / 100).toFixed(4); return x; };
  console.log('CALIB fix', JSON.stringify(st(sh(fix.cum))), '(JQ 0.1369/1.35/33.87/20.18)');
  console.log('CALIB s2 own', JSON.stringify(st(sh(pnl.s2.map(x => x * 4)))), '(rec 29.79/1.15/16.14)');
  console.log('CALIB s4 own', JSON.stringify(st(sh(pnl.s4.map(x => x * 4)))), '(rec 9.77/0.16/42.47)');
  for (const c of [s1, dv]) if (c.dates.join() !== fix.dates.join()) throw new Error('dates');
  const s3 = fix.cum.map((c, i) => c - s1.cum[i] - dv.cum[i]);
  const sub = {
    'full ref (s1+s2+s3+s4)': fix.cum,
    's1+s3 (=fix-div)': fix.cum.map((c, i) => c - dv.cum[i]),
    's3 alone (derived)': s3,
    'base minus s4 (s1+s2+s3)': fix.cum.map((c, i) => c - pnl.s4[i]),
    'base minus s2 (s1+s3+s4)': fix.cum.map((c, i) => c - pnl.s2[i]),
    's2 alone (split)': pnl.s2, 's4 alone (split)': pnl.s4,
  };
  const idx = new Map(pbm.dates.map((d, i) => [d, i])); const common = fix.dates.filter(d => idx.has(d));
  const rr = (dates, cum) => { const v = cum.map(c => 1 + c / 100); const m = new Map(dates.map((d, i) => [d, i ? v[i] / v[i - 1] - 1 : v[i] - 1])); return common.map(d => m.get(d)); };
  function pearson(a, b) { const n = a.length, ma = a.reduce((x, y) => x + y) / n, mb = b.reduce((x, y) => x + y) / n; let ab = 0, aa = 0, bb = 0; for (let i = 0; i < n; i++) { ab += (a[i] - ma) * (b[i] - mb); aa += (a[i] - ma) ** 2; bb += (b[i] - mb) ** 2; } return ab / Math.sqrt(aa * bb); }
  const pR = rr(pbm.dates, pbm.cum); console.log('common days', common.length);
  for (const [k, c] of Object.entries(sub)) {
    const m = st(sh(c));
    console.log(k.padEnd(28), 'total', m.total, 'sharpe', m.sharpe, 'maxDD', m.maxdd, 'objJQ(total-maxDD)', +((m.total - m.maxdd) / 100).toFixed(4), '| rho vs pbm-e9-2', pearson(rr(fix.dates, c), pR).toFixed(4));
  }
  return { pnl };
}
module.exports = { main };
