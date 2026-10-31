// u-1 cross-leg analysis from the four single-leg stored curves + the base curve (account level).
// Usage: node -e "require('./study/多策略分仓组合/u1-combine.js').main()"
const fs = require('fs');
const path = require('path');
const SER = path.join(__dirname, '../../data/series');
const load = f => JSON.parse(fs.readFileSync(path.join(SER, f), 'utf8'));
const BASE = '2026-07-18_多策略-题材概念-35ce65d2__train__e9.json';
const LEGS = { A: 'u-1a', B: 'u-1b', ETF3: 'u-1e3', ETF2: 'u-1e2' };
const daily = cum => { const o = []; let p = 1; for (const x of cum) { const v = 1 + x / 100; o.push(v / p - 1); p = v; } return o; };
const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
const sd = a => { const m = mean(a); return Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1)); };
const corr = (a, b) => { const ma = mean(a), mb = mean(b); let c = 0; for (let i = 0; i < a.length; i++) c += (a[i] - ma) * (b[i] - mb); return c / (a.length - 1) / sd(a) / sd(b); };

function main() {
  const b = load(BASE);
  const rb = daily(b.cum);
  const R = {}, C = {};
  for (const [k, id] of Object.entries(LEGS)) {
    const s = load(`study_多策略分仓组合_variants_${id}__train__e9.json`);
    if (JSON.stringify(s.dates) !== JSON.stringify(b.dates)) throw new Error(`${id} dates differ from base`);
    R[k] = daily(s.cum); C[k] = s.cum[s.cum.length - 1];
  }
  const keys = Object.keys(LEGS);
  const sdb = sd(rb), sds = keys.map(k => sd(R[k])), sumSd = sds.reduce((a, x) => a + x, 0);
  console.log('account daily sd: base', sdb.toFixed(6), keys.map((k, i) => `${k} ${sds[i].toFixed(6)}`).join(' '), 'sum', sumSd.toFixed(6));
  console.log('DR = sd_base / sum sd_i =', (sdb / sumSd).toFixed(4));
  const sumR = rb.map((_, t) => keys.reduce((a, k) => a + R[k][t], 0));
  console.log('sd(sum r_i)', sd(sumR).toFixed(6), ' DR using sd(sum r_i) =', (sd(sumR) / sumSd).toFixed(4));
  const diff = rb.map((x, t) => sumR[t] - x);
  const ad = diff.map(Math.abs);
  console.log('additivity: corr(sum r_i, r_base)', corr(sumR, rb).toFixed(4),
    ' mean|d|', (mean(ad) * 1e4).toFixed(2) + 'bp', ' max|d|', (Math.max(...ad) * 1e4).toFixed(2) + 'bp',
    'on', b.dates[ad.indexOf(Math.max(...ad))], ' mean d', (mean(diff) * 1e4).toFixed(2) + 'bp', ' sd d', (sd(diff) * 1e4).toFixed(2) + 'bp');
  const cumSum = rb.reduce((a, _, t) => a * (1 + sumR[t]), 1) - 1;
  console.log('compounded sum-of-legs total', (cumSum * 100).toFixed(2) + '%', ' base', b.cum[b.cum.length - 1] + '%',
    ' sum of leg totals', keys.reduce((a, k) => a + C[k], 0).toFixed(2) + '%');
  const top = ad.map((x, t) => [x, t]).sort((p, q) => q[0] - p[0]).slice(0, 5);
  console.log('top |d| days', top.map(([x, t]) => `${b.dates[t]} ${(diff[t] * 1e4).toFixed(1)}bp`).join(', '));
  console.log('corr matrix (account daily returns)');
  console.log('      ' + keys.map(k => k.padStart(7)).join('') + '   base');
  for (const i of keys) console.log(i.padEnd(6) + keys.map(j => corr(R[i], R[j]).toFixed(3).padStart(7)).join('') + corr(R[i], rb).toFixed(3).padStart(7));
  const tb = b.cum[b.cum.length - 1];
  console.log('share of base total return (leg total / base total):', keys.map(k => `${k} ${C[k]}% = ${(C[k] / tb * 100).toFixed(1)}%`).join(', '));
}
module.exports = { main };
