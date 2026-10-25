// node -e "require('./study/五福闹新春/analyze-e9-liq.js')"
// (A) structural result from the LIQFLOOR census + (B) curve comparison against the parent.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');

const LIQ = path.join(ROOT, 'data/autostudy-logs/wufu-q-e9-liq.liqfloor.txt');
const PARENT_CURVE = path.join(ROOT, 'data/series/study_五福闹新春_q-e9-pit_bf30eb36__train__e9.json');
const CHILD_CURVE = path.join(ROOT, 'data/series/study_五福闹新春_variants_q-e9-liq_both-legs__train__e9.json');

const raw = fs.readFileSync(LIQ, 'utf8').split('\n').filter(l => l.includes('LIQFLOOR'));
const rows = raw.map(l => {
  const body = l.slice(l.indexOf('LIQFLOOR'));
  const f = {};
  for (const [, k, v] of body.matchAll(/(\w+)=([^\s]*)/g)) f[k] = v;
  return f;
});
console.log(`census lines: ${rows.length}`);

const legs = ['etf', 'stock'];
const q = (arr, p) => {
  if (!arr.length) return NaN;
  const s = [...arr].sort((a, b) => a - b);
  const i = (s.length - 1) * p;
  const lo = Math.floor(i), hi = Math.ceil(i);
  return s[lo] + (s[hi] - s[lo]) * (i - lo);
};
const fmt = n => (Number.isFinite(n) ? (n / 1e8).toFixed(4) + '亿' : 'n/a');

const perLeg = {};
for (const leg of legs) {
  const r = rows.filter(x => x.leg === leg);
  const ok = r.filter(x => x.status === 'ok');
  const bypass = r.filter(x => x.status !== 'ok');
  const dates = new Set(r.map(x => x.date));
  const changed = ok.filter(x => +x.in !== +x.out);
  const staticChanged = ok.filter(x => x.static_removed !== '-');
  const removedCount = {};
  const staticRemovedCount = {};
  const removedPerDay = [];
  let allMoney = [];
  let candTotal = 0, keptTotal = 0, exemptDays = 0, exemptTotal = 0;
  const floors = [], floorsStatic = [], tvs = [], nlive = {};
  for (const x of ok) {
    candTotal += +x.in; keptTotal += +x.out;
    floors.push(+x.floor); floorsStatic.push(+x.floor_static); tvs.push(+x.tv);
    nlive[x.n] = (nlive[x.n] || 0) + 1;
    const rem = x.removed === '-' ? [] : x.removed.split(';');
    removedPerDay.push(rem.length);
    rem.forEach(c => { removedCount[c] = (removedCount[c] || 0) + 1; });
    const srem = x.static_removed === '-' ? [] : x.static_removed.split(';');
    srem.forEach(c => { staticRemovedCount[c] = (staticRemovedCount[c] || 0) + 1; });
    const ex = x.exempt === '-' ? [] : x.exempt.split(';');
    if (ex.length) { exemptDays++; exemptTotal += ex.length; }
    if (x.money && x.money !== '-') {
      for (const pair of x.money.split(';')) {
        const [c, m] = pair.split(':');
        if (c && m !== undefined) allMoney.push({ code: c, money: +m });
      }
    }
  }
  const dist = {};
  removedPerDay.forEach(n => { dist[n] = (dist[n] || 0) + 1; });
  const moneyVals = allMoney.map(x => x.money);
  perLeg[leg] = { rows: r, ok, bypass, dates, changed, staticChanged, removedCount, staticRemovedCount, dist, moneyVals, allMoney, floors, floorsStatic, tvs, nlive, candTotal, keptTotal, exemptDays, exemptTotal };

  console.log(`\n================ leg=${leg} ================`);
  console.log(`decision days (census lines): ${r.length}   distinct dates: ${dates.size}`);
  console.log(`status ok: ${ok.length}   bypass: ${bypass.length}` +
    (bypass.length ? ' [' + [...new Set(bypass.map(x => x.status))].join(',') + ']' : ''));
  console.log(`LIVE floor range : ${fmt(Math.min(...floors))} .. ${fmt(Math.max(...floors))}   (median ${fmt(q(floors, 0.5))})`);
  console.log(`STATIC floor     : ${fmt(floorsStatic[0])} (constant: ${new Set(floorsStatic).size === 1})`);
  console.log(`total_value      : ${(Math.min(...tvs) / 1e4).toFixed(1)}万 .. ${(Math.max(...tvs) / 1e4).toFixed(1)}万`);
  console.log(`live slots n=    : ${JSON.stringify(nlive)}`);
  console.log(`candidates seen  : ${candTotal}  kept: ${keptTotal}  removed: ${candTotal - keptTotal}`);
  console.log(`days with in!=out (LIVE floor)   : ${changed.length} / ${ok.length}`);
  console.log(`days with any static_removed     : ${staticChanged.length} / ${ok.length}`);
  console.log(`removal-count distribution (removed-per-day -> days): ${JSON.stringify(dist)}`);
  console.log(`days where a HELD name was exempted: ${exemptDays} (total exemptions ${exemptTotal})`);
  const top = Object.entries(removedCount).sort((a, b) => b[1] - a[1]);
  console.log(`tickers removed by the LIVE floor (${top.length} distinct):`);
  top.slice(0, 40).forEach(([c, n]) => console.log(`   ${c}  on ${n} day(s)`));
  const stop = Object.entries(staticRemovedCount).sort((a, b) => b[1] - a[1]);
  console.log(`tickers the STATIC ¥${(floorsStatic[0] / 1e4).toFixed(0)}万 floor would have removed (${stop.length} distinct):`);
  stop.slice(0, 40).forEach(([c, n]) => console.log(`   ${c}  on ${n} day(s)`));
  console.log(`candidate money= distribution (n=${moneyVals.length} name-days):`);
  console.log(`   min ${fmt(Math.min(...moneyVals))}  p10 ${fmt(q(moneyVals, 0.10))}  median ${fmt(q(moneyVals, 0.5))}  p90 ${fmt(q(moneyVals, 0.90))}  max ${fmt(Math.max(...moneyVals))}`);
  // survival curve: mean surviving candidates per decision day at a range of fixed thresholds
  console.log(`   mean surviving candidates per decision day vs a FIXED floor:`);
  const byDay = ok.map(x => (x.money && x.money !== '-' ? x.money.split(';').map(p => +p.split(':')[1]) : []));
  for (const th of [1e6, 2e6, 5e6, 1e7, 2e7, 5e7, 1e8, 2e8, 5e8, 1e9]) {
    const surv = byDay.map(ms => ms.filter(m => m >= th).length);
    const mean = surv.reduce((a, b) => a + b, 0) / (surv.length || 1);
    const zero = surv.filter(s => s === 0).length;
    console.log(`     floor ${fmt(th).padStart(10)} -> mean ${mean.toFixed(2)} of ${(candTotal / (ok.length || 1)).toFixed(2)}   days with ZERO survivor: ${zero}`);
  }
}

// ---------------------------------------------------------------- curve comparison
const p = JSON.parse(fs.readFileSync(PARENT_CURVE, 'utf8'));
const c = JSON.parse(fs.readFileSync(CHILD_CURVE, 'utf8'));
console.log(`\n================ curve ================`);
console.log(`parent ${p.points}d ${p.start}..${p.end} final ${p.cum[p.cum.length - 1]}`);
console.log(`child  ${c.points}d ${c.start}..${c.end} final ${c.cum[c.cum.length - 1]}`);
const n = Math.min(p.dates.length, c.dates.length);
let maxAbs = 0, firstDiff = null, sameDates = true;
for (let i = 0; i < n; i++) {
  if (p.dates[i] !== c.dates[i]) { sameDates = false; break; }
  const d = Math.abs(p.cum[i] - c.cum[i]);
  if (d > maxAbs) maxAbs = d;
  if (firstDiff === null && d > 1e-9) firstDiff = { date: p.dates[i], parent: p.cum[i], child: c.cum[i] };
}
console.log(`dates aligned: ${sameDates}  compared ${n} days`);
console.log(`max|Δcum| = ${maxAbs.toFixed(6)}  (exactly 0 ⇒ bit-identical)`);
console.log(`first divergence: ${firstDiff ? `${firstDiff.date}  parent ${firstDiff.parent} vs child ${firstDiff.child}` : 'none'}`);

// objective
const harness = require('../../utils/harness-config');
const PARENT_OBJ = 1.9658;
const annual = 201.37, maxdd = 12.79, sharpe = 7.16;
const obj = (annual - maxdd) / 100;
console.log(`\nchild  : annual ${annual}  maxDD ${maxdd}  sharpe ${sharpe}  objective ${obj.toFixed(4)}`);
console.log(`parent : objective ${PARENT_OBJ}`);
console.log(`Δobjective = ${(obj - PARENT_OBJ).toFixed(4)}   (family noise floor at this level ≈ 0.161)`);
console.log(`stage gate (study, epoch ${harness.config().epoch}): sharpe >= ${harness.stageThreshold('study')} -> ${harness.stageGate('study', sharpe) ? 'PASS' : 'FAIL'}`);
