// node -e "require('./study/五福闹新春/analyze-e9-imp1.js')"
// imp-e9-1 report: (a) the mandatory weak-day census from the JQ log, (b) sub-window Δlog vs the
// parent for the four segments q-e9-weak used, (c) daily-return correlation vs the parent.
const fs = require('fs');
const series = require('../../utils/backtest-series');

const LOG = 'data/autostudy-logs/wufu-imp-e9-1.full.txt';
const P_CURVE = 'data/series/study_五福闹新春_q-e9-pit_bf30eb36__train__e9.json';
const V_CURVE = 'data/series/study_五福闹新春_variants_imp-e9-1_champion-weakswitch__train__e9.json';

const L = fs.readFileSync(LOG, 'utf8').split('\n');
const day = l => (l.match(/^(\d{4}-\d{2}-\d{2})/) || [])[1];

// ── A. census ───────────────────────────────────────────────────────────────────────────────
// branch actually taken by the sleeve at 13:10
const branch = new Map();            // date -> {state, pool, names}
for (const l of L) {
  const m = l.match(/IMP-E9-1-CENSUS (WEAK|NORMAL) pool=(\d+)(?: names=(\S+))?/);
  if (!m) continue;
  branch.set(day(l), { state: m[1], pool: +m[2], names: m[3] ? m[3].split(',') : null });
}
// the copied rule's own inputs and final state
const rule = new Map();              // date -> {below, above}
for (const l of L) {
  const m = l.match(/低于MA10: (\d)\/4, 站上MA10: (\d)\/4/);
  if (m) rule.set(day(l), { below: +m[1], above: +m[2] });
}
const finalState = new Map();        // date -> {weak, count}
for (const l of L) {
  const m = l.match(/最终状态: 走弱期=(True|False)(?: \(已持续(\d+)\/(\d+)个交易日\))?/);
  if (m) finalState.set(day(l), { weak: m[1] === 'True', count: m[2] ? +m[2] : 0, cap: m[3] ? +m[3] : null });
}
const entries = L.filter(l => l.includes('【走弱期进入】')).map(day);
const resets = L.filter(l => l.includes('【走弱期延续】')).map(day);
const exitsCond = L.filter(l => l.includes('【走弱期退出】满足退出条件')).map(day);
const exitsMax = L.filter(l => l.includes('【走弱期退出】已达到最大持续天数')).map(day);

const dates = [...branch.keys()].sort();
const weakDays = dates.filter(d => branch.get(d).state === 'WEAK');
const normalDays = dates.filter(d => branch.get(d).state === 'NORMAL');

// longest consecutive WEAK run (trading days)
let run = 0, best = 0, bestEnd = null;
for (const d of dates) {
  if (branch.get(d).state === 'WEAK') { run++; if (run > best) { best = run; bestEnd = d; } } else run = 0;
}
// branch agreement with the rule's own final state (sanity: no off-by-one from the 09:00/13:10 split)
const mismatch = dates.filter(d => finalState.has(d) && (finalState.get(d).weak !== (branch.get(d).state === 'WEAK')));

console.log('===== A. WEAK-DAY CENSUS (242 trading days, from the JQ 日志 tab) =====');
console.log(`days with the gate ACTIVE (sleeve took the weak branch): ${weakDays.length} / ${dates.length}`);
console.log(`days NORMAL (champion's merged pool):                    ${normalDays.length} / ${dates.length}`);
console.log(`inertness clause (<20 active days => INERT):             ${weakDays.length < 20 ? 'FIRES' : 'does NOT fire'}`);
console.log(`entries 【走弱期进入】: ${entries.length}   re-trigger resets 【走弱期延续】: ${resets.length}`);
console.log(`exits by condition: ${exitsCond.length}   exits by max_weak_days(20): ${exitsMax.length}`);
console.log(`longest consecutive weak run: ${best} trading days (ending ${bestEnd})`);
console.log(`max weak_days_count reached:  ${Math.max(...[...finalState.values()].map(v => v.count))} (cap ${[...finalState.values()].find(v => v.cap) ? [...finalState.values()].find(v => v.cap).cap : '?'})`);
console.log(`09:00 rule state vs 13:10 branch mismatches: ${mismatch.length}${mismatch.length ? ' ' + mismatch.slice(0, 5).join(',') : ''}`);
const poolsW = new Set(weakDays.map(d => branch.get(d).pool));
const poolsN = normalDays.map(d => branch.get(d).pool);
console.log(`weak-day pool size(s): ${[...poolsW].join(',')}  (13 global names ∩ champion liquidity filter)`);
console.log(`normal-day pool size: min ${Math.min(...poolsN)} max ${Math.max(...poolsN)} median ${poolsN.slice().sort((a, b) => a - b)[Math.floor(poolsN.length / 2)]}`);
const everyWeakFull = weakDays.every(d => branch.get(d).names && branch.get(d).names.length === 13);
console.log(`every weak day carried all 13 names (liquidity filter never cut one): ${everyWeakFull}`);
console.log(`entry dates: ${entries.join(' ')}`);

// ── holdings on weak vs normal days (策略3 ETF buys only; 策略1 lines are the stock leg) ─────
const buys = [];
for (const l of L) {
  const m = l.match(/📦 买入(\d{6}\.XSH[GE]) (\S+)，数量: (\d+)/);
  if (m) buys.push({ d: day(l), code: m[1], name: m[2] });
}
const tally = ds => {
  const s = new Set(ds); const t = new Map();
  for (const b of buys) if (s.has(b.d)) t.set(`${b.code} ${b.name}`, (t.get(`${b.code} ${b.name}`) || 0) + 1);
  return [...t.entries()].sort((a, b) => b[1] - a[1]);
};
console.log('\n--- 策略3 ETF buys on WEAK days (code name × count) ---');
for (const [k, v] of tally(weakDays)) console.log(`  ${String(v).padStart(3)}  ${k}`);
console.log('--- 策略3 ETF buys on NORMAL days ---');
for (const [k, v] of tally(normalDays)) console.log(`  ${String(v).padStart(3)}  ${k}`);

// defensive ETF: days the sleeve HELD 511880 (the fall-through), from the 09:00 holdings check
const heldDef = new Set();
for (const l of L) if (/【持仓检查】511880\.XSHG/.test(l)) heldDef.add(day(l));
const defBuys = buys.filter(b => b.code === '511880.XSHG');
console.log(`\ndefensive ETF 511880 (g.defensive_etf): bought on ${defBuys.length} day(s) ${defBuys.map(b => b.d).join(' ')}`);
console.log(`days HOLDING 511880 at the 09:00 check: ${heldDef.size}  (${[...heldDef].sort().join(' ')})`);
const defWeak = [...heldDef].filter(d => branch.get(d) && branch.get(d).state === 'WEAK').length;
console.log(`  of which weak-branch days: ${defWeak}, normal-branch days: ${heldDef.size - defWeak}`);

// ── B. sub-window Δlog ──────────────────────────────────────────────────────────────────────
const P = JSON.parse(fs.readFileSync(P_CURVE, 'utf8'));
const V = JSON.parse(fs.readFileSync(V_CURVE, 'utf8'));
if (P.dates.length !== V.dates.length || P.dates[0] !== V.dates[0]) throw new Error('curve dates differ');
const SEGS = [
  ['Jan 2 – Feb 29', '2024-01-01', '2024-02-29'],
  ['Mar 1 – Sep 23', '2024-03-01', '2024-09-23'],
  ['Sep 24 – Oct 8', '2024-09-24', '2024-10-08'],
  ['Oct 9 – Dec 31', '2024-10-09', '2024-12-31'],
];
// segment log-growth = sum of log(1+r) over the segment's trading days — additive by construction
const dlog = (cum, dates, a, b) => {
  const r = series.dailyReturns(cum);
  let s = 0, n = 0;
  for (let i = 0; i < dates.length; i++) {
    if (dates[i] >= a && dates[i] <= b && r[i] != null) { s += Math.log(1 + r[i]); n++; }
  }
  return { s, n };
};
console.log('\n===== B. SUB-WINDOW Δlog (variant − parent), additive =====');
console.log('segment              days   parent Δlog   variant Δlog      Δ(V−P)   weak-days in segment');
let tot = 0;
for (const [name, a, b] of SEGS) {
  const p = dlog(P.cum, P.dates, a, b), v = dlog(V.cum, V.dates, a, b);
  const w = dates.filter(d => d >= a && d <= b && branch.get(d).state === 'WEAK').length;
  const nd = dates.filter(d => d >= a && d <= b).length;
  tot += v.s - p.s;
  console.log(`${name.padEnd(20)} ${String(p.n).padStart(4)}   ${p.s.toFixed(4).padStart(11)}   ${v.s.toFixed(4).padStart(12)}   ${(v.s - p.s >= 0 ? '+' : '') + (v.s - p.s).toFixed(4)}   ${w}/${nd}`);
}
const pAll = dlog(P.cum, P.dates, '2024-01-01', '2024-12-31'), vAll = dlog(V.cum, V.dates, '2024-01-01', '2024-12-31');
console.log(`${'FULL TRAIN'.padEnd(20)} ${String(pAll.n).padStart(4)}   ${pAll.s.toFixed(4).padStart(11)}   ${vAll.s.toFixed(4).padStart(12)}   ${(vAll.s - pAll.s >= 0 ? '+' : '') + (vAll.s - pAll.s).toFixed(4)}   ${weakDays.length}/${dates.length}`);
console.log(`segments sum to ${tot.toFixed(4)} vs full ${(vAll.s - pAll.s).toFixed(4)} (additivity check)`);

// ── C. correlation + headline deltas ────────────────────────────────────────────────────────
const pr = series.dailyReturns(P.cum), vr = series.dailyReturns(V.cum);
const pairs = pr.map((x, i) => [x, vr[i]]).filter(([a, b]) => a != null && b != null);
const corr = series.pearson(pairs.map(p => p[0]), pairs.map(p => p[1]));
const mdd = cum => { let pk = -1e9, m = 0; for (const c of cum) { const v = 1 + c / 100; if (v > pk) pk = v; const d = (pk - v) / pk; if (d > m) m = d; } return m * 100; };
console.log('\n===== C. HEADLINE + CORRELATION =====');
const pa = P.cum[P.cum.length - 1], va = V.cum[V.cum.length - 1];
const pm = mdd(P.cum), vm = mdd(V.cum);
console.log(`parent  annual ${pa.toFixed(2)}  maxDD ${pm.toFixed(2)}  objective ${((pa - pm) / 100).toFixed(4)}  sharpe 7.51`);
console.log(`variant annual ${va.toFixed(2)}  maxDD ${vm.toFixed(2)}  objective ${((va - vm) / 100).toFixed(4)}  sharpe 7.45`);
console.log(`Δ       annual ${(va - pa >= 0 ? '+' : '') + (va - pa).toFixed(2)}pp  maxDD ${(vm - pm >= 0 ? '+' : '') + (vm - pm).toFixed(2)}pp  Δobjective ${(((va - vm) - (pa - pm)) / 100 >= 0 ? '+' : '') + (((va - vm) - (pa - pm)) / 100).toFixed(4)}`);
console.log(`daily-return correlation vs parent: ${corr.toFixed(4)}  (n=${pairs.length})`);
const ident = pairs.filter(([a, b]) => a === b).length;
console.log(`byte-identical daily returns: ${ident}/${pairs.length} days`);
