// Split leg-A native returns by the regime of the HOLDING period.
// Day t's return is attributed to the regime logged on the most recent rebalance date STRICTLY before t
// (rebalance runs 14:30, so day-of-rebalance return is mostly the old book). Days before the first
// regime line are 'pre'. NAV convention as native-sharpe.js: NAV = ((1+c/100)-(1-w))/w.
// usage: node -e "require('./study/多策略分仓组合/regime-split.js').main('u-6', 0.35)"
const fs = require('fs');
const path = require('path');
const SER = path.join(__dirname, '../../data/series');

function regimes(logFile) {
  const L = fs.readFileSync(logFile, 'utf8').split('\n');
  const m = new Map();
  for (const l of L) {
    if (/当前为牛市/.test(l)) m.set(l.slice(0, 10), 'bull');
    else if (/当前为熊市/.test(l)) m.set(l.slice(0, 10), 'bear');
  }
  return [...m.entries()].sort((a, b) => a[0] < b[0] ? -1 : 1);
}

function seg(r, K) {
  const n = r.length; if (n < 2) return { n };
  const m = r.reduce((a, b) => a + b, 0) / n;
  const sd = Math.sqrt(r.reduce((a, b) => a + (b - m) ** 2, 0) / (n - 1));
  const tot = r.reduce((a, x) => a * (1 + x), 1) - 1;
  const ann = Math.pow(1 + tot, K / n) - 1;
  return { n, tot: +(tot * 100).toFixed(2), annTrading: +(ann * 100).toFixed(2), vol: +(sd * Math.sqrt(K)).toFixed(4),
    sharpe: +((ann - 0.04) / (sd * Math.sqrt(K))).toFixed(3) };
}

function main(id, w, K = 250) {
  const s = JSON.parse(fs.readFileSync(path.join(SER, `study_多策略分仓组合_variants_${id}__train__e9.json`), 'utf8'));
  const R = regimes(path.join(__dirname, `${id}.log`));
  const nav = s.cum.map(c => ((1 + c / 100) - (1 - w)) / w);
  const out = { pre: [], bull: [], bear: [] };
  let prev = 1;
  s.dates.forEach((d, i) => {
    const r = nav[i] / prev - 1; prev = nav[i];
    let reg = 'pre';
    for (const [rd, g] of R) { if (rd < d) reg = g; else break; }
    out[reg].push(r);
  });
  console.log(id, 'regime dates', R.length, JSON.stringify({ pre: seg(out.pre, K), bull: seg(out.bull, K), bear: seg(out.bear, K) }));
  return R;
}
module.exports = { main, regimes };
