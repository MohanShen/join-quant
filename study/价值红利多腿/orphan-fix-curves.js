// q-e9-orphan-fix helper (zero backtests): book metrics, first divergence vs the reference, the
// derived s3 curve = fixed − s1-only − div-only (P&L in ¥ on the common ¥1M base), its share of net,
// own-capital (¥250k) sharpe, and daily ρ vs enhance_candidates_pbm-e9-2.
// Usage: node -e "require('./study/价值红利多腿/orphan-fix-curves.js').main()"
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const L = k => JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'series', k + '__train__e9.json'), 'utf8'));
const V = 'study_价值红利多腿_variants_';

// cum is percent of OWN capital
function sh(cum, opt) {
  opt = opt || {};
  const rf = opt.rf == null ? 0.04 : opt.rf, ann = 250;
  const v = cum.map(c => 1 + c / 100);
  const r = v.map((x, i) => (i ? x / v[i - 1] - 1 : x - 1));
  const m = r.reduce((a, b) => a + b) / r.length;
  const sd = Math.sqrt(r.reduce((a, b) => a + (b - m) ** 2, 0) / (r.length - 1));
  const tot = v[v.length - 1] - 1;
  const an = opt.annDays ? Math.pow(1 + tot, 365 / opt.annDays) - 1 : Math.pow(1 + tot, ann / r.length) - 1;
  let peak = 1, mdd = 0; for (const x of v) { peak = Math.max(peak, x); mdd = Math.max(mdd, 1 - x / peak); }
  return { total: +(tot * 100).toFixed(2), annual: +(an * 100).toFixed(2), vol: +(sd * Math.sqrt(ann)).toFixed(4),
    sharpe: +((an - rf) / (sd * Math.sqrt(ann))).toFixed(3), sharpe365: +(((Math.pow(1 + tot, 365 / 365) - 1) - rf) / (sd * Math.sqrt(ann))).toFixed(3), maxdd: +(mdd * 100).toFixed(2), rets: r };
}
function pearson(a, b) {
  const n = a.length, ma = a.reduce((x, y) => x + y) / n, mb = b.reduce((x, y) => x + y) / n;
  let sab = 0, sa = 0, sb = 0;
  for (let i = 0; i < n; i++) { sab += (a[i] - ma) * (b[i] - mb); sa += (a[i] - ma) ** 2; sb += (b[i] - mb) ** 2; }
  return sab / Math.sqrt(sa * sb);
}
const strip = o => { const { rets, ...x } = o; return x; };

function main() {
  const fix = L(V + 'q-e9-orphan-fix'), ref = L(V + 'q-e9-s4-pit');
  const s1 = L(V + 'q-e9-s1-only'), dv = L(V + 'q-e9-div-only'), pb = L(V + 'q-e9-pb-only');
  const pbm = L('enhance_candidates_pbm-e9-2');
  for (const c of [ref, s1, dv, pb]) if (c.dates.join() !== fix.dates.join()) throw new Error('date mismatch ' + c.sourceFile);

  // calibration: the formula must reproduce recorded figures before it is used on the derived curve
  console.log('CALIB ref book', JSON.stringify(strip(sh(ref.cum))), '(recorded sharpe 1.32)');
  console.log('CALIB pb own¥250k', JSON.stringify(strip(sh(pb.cum.map(x => x * 4)))), '(recorded 1.87)');
  console.log('CALIB s1 own¥250k', JSON.stringify(strip(sh(s1.cum.map(x => x * 4)))), '(recorded 0.75)');
  console.log('CALIB div own¥500k', JSON.stringify(strip(sh(dv.cum.map(x => x * 2)))), '(recorded 0.61)');
  console.log('FIX book', JSON.stringify(strip(sh(fix.cum))));

  let first = null;
  fix.cum.forEach((c, i) => { if (first == null && c !== ref.cum[i]) first = i; });
  console.log('first divergence vs ref:', first == null ? 'none' : fix.dates[first] + ' fix ' + fix.cum[first] + ' ref ' + ref.cum[first] +
    (first ? ' (prev ' + fix.dates[first - 1] + ' ' + fix.cum[first - 1] + '/' + ref.cum[first - 1] + ')' : ''));
  let maxd = 0, at = null; fix.cum.forEach((c, i) => { const d = Math.abs(c - ref.cum[i]); if (d > maxd) { maxd = d; at = fix.dates[i]; } });
  console.log('max |Δcum| fix−ref', maxd.toFixed(2), 'pp at', at);

  // derived s3 P&L in pp of ¥1M: fixed − s1-only − div-only; own capital ¥250k ⇒ ×4
  const s3pp = fix.cum.map((c, i) => c - s1.cum[i] - dv.cum[i]);
  const net = fix.cum[fix.cum.length - 1], s3net = s3pp[s3pp.length - 1];
  console.log('net book pp', net, '| s1', s1.cum.at(-1), '| div', dv.cum.at(-1), '| derived s3', s3net.toFixed(2),
    '| s3 share of net', (100 * s3net / net).toFixed(1) + '%', '| pb-only (pre-fix s3) pp', pb.cum.at(-1));
  const s3own = sh(s3pp.map(x => x * 4));
  console.log('derived s3 own¥250k', JSON.stringify(strip(s3own)));
  // derived s3 vs the s3-only run, day by day (they should agree up to 06-20)
  let agree = null; s3pp.forEach((x, i) => { if (agree == null && Math.abs(x - pb.cum[i]) > 0.05) agree = i; });
  console.log('derived s3 vs pb-only first |Δ|>0.05pp:', agree == null ? 'none' : fix.dates[agree] + ' derived ' + s3pp[agree].toFixed(2) + ' pb ' + pb.cum[agree]);

  // ρ vs pbm-e9-2 on common dates
  const idx = new Map(pbm.dates.map((d, i) => [d, i]));
  const common = fix.dates.filter(d => idx.has(d));
  const rr = (cumPct, dates, all) => { const v = all.map(c => 1 + c / 100); const m = new Map(dates.map((d, i) => [d, i ? v[i] / v[i - 1] - 1 : v[i] - 1])); return common.map(d => m.get(d)); };
  const pR = rr(null, pbm.dates, pbm.cum);
  const fR = rr(null, fix.dates, fix.cum);
  // s3 own-capital daily returns: from s3 own value series
  const s3R = rr(null, fix.dates, s3pp.map(x => x * 4));
  console.log('common days', common.length, '| ρ(fixed book, pbm-e9-2)', pearson(fR, pR).toFixed(4),
    '| ρ(derived s3, pbm-e9-2)', pearson(s3R, pR).toFixed(4), '| ρ(ref book, pbm-e9-2)', pearson(rr(null, ref.dates, ref.cum), pR).toFixed(4),
    '| ρ(pb-only, pbm-e9-2)', pearson(rr(null, pb.dates, pb.cum), pR).toFixed(4), '| ρ(derived s3, fixed)', pearson(s3R, fR).toFixed(4));
}
module.exports = { main, sh };
