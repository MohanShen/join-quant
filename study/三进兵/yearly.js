// Per-year split of stored curves for the 三进兵 round (zero backtest cost).
//   node -e "process.argv[2]='baseline-e6,variants_u-1_pool-transfer';require('./study/三进兵/yearly.js')"
// Prints, per curve: whole-window total / maxDD / vol, then per calendar year total / maxDD /
// vol and the implied exposure vs a reference curve when one is named after a colon
// (key:refKey) — exposure = vol(curve)/vol(ref), the number the equal-exposure reading needs.
const { load, dailyReturns } = require('../../utils/backtest-series');
const keys = (process.argv[2] || 'baseline-e6').split(',');

function stats(dates, cum) {
  const r = dailyReturns(cum);
  let peak = 1, nav = 1, mdd = 0, mddEnd = null;
  const navs = [];
  for (let i = 0; i < r.length; i++) {
    nav *= 1 + r[i]; navs.push(nav);
    if (nav > peak) peak = nav;
    const dd = 1 - nav / peak;
    if (dd > mdd) { mdd = dd; mddEnd = dates[i + 1]; }
  }
  const mean = r.reduce((a, b) => a + b, 0) / r.length;
  const vol = Math.sqrt(r.reduce((a, b) => a + (b - mean) ** 2, 0) / (r.length - 1)) * Math.sqrt(250);
  return { total: (nav - 1) * 100, maxDD: mdd * 100, mddEnd, vol, n: r.length };
}

function sliceYear(s, y) {
  const idx = s.dates.map((d, i) => (d.startsWith(y) ? i : -1)).filter(i => i >= 0);
  const first = idx[0], last = idx[idx.length - 1];
  // rebase: cumulative % relative to the close before the year's first day
  const base = first > 0 ? 1 + s.cum[first - 1] / 100 : 1;
  const cum = s.cum.slice(Math.max(first - 1, 0), last + 1).map(c => ((1 + c / 100) / base - 1) * 100);
  const dates = s.dates.slice(Math.max(first - 1, 0), last + 1);
  if (first === 0) { cum.unshift(0); dates.unshift(dates[0]); }
  return { dates, cum };
}

for (const spec of keys) {
  const [k, refK] = spec.split(':');
  const s = load(`study_三进兵_${k}__train__e6`);
  const ref = refK ? load(`study_三进兵_${refK}__train__e6`) : null;
  const all = stats(s.dates, [0, ...s.cum]);
  const line = y => {
    const yr = sliceYear(s, y); const st = stats(yr.dates, yr.cum);
    let exp = '';
    if (ref) { const ry = sliceYear(ref, y); const rs = stats(ry.dates, ry.cum); exp = ` exposure≈${(st.vol / rs.vol).toFixed(3)} refTotal ${rs.total.toFixed(2)}`; }
    return `  ${y}: total ${st.total.toFixed(2)}% maxDD ${st.maxDD.toFixed(2)}% (ends ${st.mddEnd}) vol ${st.vol.toFixed(4)} n=${st.n}${exp}`;
  };
  let expAll = '';
  if (ref) { const ra = stats(ref.dates, [0, ...ref.cum]); expAll = ` exposure≈${(all.vol / ra.vol).toFixed(3)} refTotal ${ra.total.toFixed(2)}`; }
  console.log(`${k}: total ${all.total.toFixed(2)}% maxDD ${all.maxDD.toFixed(2)}% (ends ${all.mddEnd}) vol ${all.vol.toFixed(4)} n=${all.n}${expAll}`);
  console.log(line('2022'));
  console.log(line('2023'));
}
