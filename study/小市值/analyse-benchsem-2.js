// Per-TIMEPOINT breakdown of the q-e9-bench-lastprice probe. The pooled answer is already decided;
// this asks the follow-on question the pooled number hides: HOW CLOSE to the day's close does each
// clock time read? 14:55 sits 5 minutes before the closing auction, so if that handler's reading is
// the close in practice, the 涨停-keep decision scheduled there is near-close even though the bench
// is not leaking.
const fs = require('fs');
const path = require('path');

const txt = fs.readFileSync(path.join(__dirname, 'benchsem-log.txt'), 'utf8');
const RE = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}):\d{2} - ERROR - BENCHSEM t=(\S+) date=(\S+) code=(\S+) last=(\S+) high_limit=(\S+) open=(\S+) prev_close=(\S+) day_close=(\S+)/;
const rows = [];
for (const l of txt.split('\n')) {
  const m = RE.exec(l);
  if (m) rows.push({ date: m[1], clock: m[2], t: m[3], code: m[5], last: m[6], hl: m[7], open: m[8], pc: m[9], dc: m[10] });
}
const dates = [...new Set(rows.map(r => r.date))].sort();
const pcOn = new Map();
for (const r of rows) if (r.code !== 'NONE') pcOn.set(r.date + '|' + r.code, r.pc);
const closeOfD = (d, code) => {
  const i = dates.indexOf(d);
  if (i < 0 || i + 1 >= dates.length) return null;
  const v = pcOn.get(dates[i + 1] + '|' + code);
  return v && /^[\d.]+$/.test(v) ? parseFloat(v) : null;
};

const CLOCKS = ['09:05', '10:00', '14:25', '14:55'];
console.log('clock  n   ==close(D)   ==prev_close(D)   median |last-close|/close');
for (const c of CLOCKS) {
  const rs = rows.filter(r => r.clock === c && r.code !== 'NONE' && /^[\d.]+$/.test(r.last));
  let n = 0, eqC = 0, eqP = 0, devs = [];
  for (const r of rs) {
    const cl = closeOfD(r.date, r.code);
    if (/^[\d.]+$/.test(r.pc) && Math.abs(parseFloat(r.last) - parseFloat(r.pc)) < 0.005) eqP++;
    if (cl == null) continue;
    n++;
    if (Math.abs(parseFloat(r.last) - cl) < 0.005) eqC++;
    devs.push(Math.abs(parseFloat(r.last) - cl) / cl);
  }
  devs.sort((a, b) => a - b);
  const med = devs.length ? devs[Math.floor(devs.length / 2)] : NaN;
  console.log(`${c}  ${String(rs.length).padStart(3)}  ${String(eqC).padStart(3)}/${String(n).padEnd(4)} ${(100 * eqC / n).toFixed(1).padStart(5)}%   ` +
              `${String(eqP).padStart(3)}/${String(rs.length).padEnd(4)} ${(100 * eqP / rs.length).toFixed(1).padStart(5)}%        ${(100 * med).toFixed(2)}%`);
}

// How often does the high_limit read change within a day? (it is a per-day constant, so it should not)
const hlByDay = new Map();
for (const r of rows) {
  if (r.code === 'NONE') continue;
  const k = r.date + '|' + r.code;
  if (!hlByDay.has(k)) hlByDay.set(k, new Set());
  hlByDay.get(k).add(r.hl);
}
const hlVary = [...hlByDay.values()].filter(s => s.size > 1).length;
console.log(`\nhigh_limit varies within a (day,code): ${hlVary} of ${hlByDay.size}  (expected 0 — it is a daily constant)`);

// day_open: constant within the day, and != prev_close -> the probe really is seeing today's bar
const opByDay = new Map();
for (const r of rows) {
  if (r.code === 'NONE') continue;
  const k = r.date + '|' + r.code;
  if (!opByDay.has(k)) opByDay.set(k, new Set());
  opByDay.get(k).add(r.open);
}
console.log(`day_open varies within a (day,code): ${[...opByDay.values()].filter(s => s.size > 1).length} of ${opByDay.size}  (expected 0)`);

// the pre-open timepoint: does day_open already have a value at 09:05, before the 09:30 open?
const pre = rows.filter(r => r.clock === '09:05' && r.code !== 'NONE');
let preOpenKnown = 0, preLastEqPc = 0;
for (const r of pre) {
  if (/^[\d.]+$/.test(r.open) && parseFloat(r.open) > 0) preOpenKnown++;
  if (/^[\d.]+$/.test(r.pc) && Math.abs(parseFloat(r.last) - parseFloat(r.pc)) < 0.005) preLastEqPc++;
}
console.log(`\n09:05 (PRE-OPEN, market opens 09:30), n=${pre.length}`);
console.log(`  day_open already non-zero: ${preOpenKnown}  <-- if high, TODAY'S OPEN is readable before the open`);
console.log(`  last_price == prev_close : ${preLastEqPc}  <-- the correct pre-open answer`);

// day_close refusal
const dcNum = rows.filter(r => r.code !== 'NONE' && /^[\d.]+$/.test(r.dc)).length;
const pcNum = rows.filter(r => r.code !== 'NONE' && /^[\d.]+$/.test(r.pc)).length;
console.log(`\nget_price(end_date=context.current_dt, 'daily') returned a number: ${dcNum} of ${rows.filter(r => r.code !== 'NONE').length}`);
console.log(`get_price(end_date=context.previous_date,'daily') returned a number: ${pcNum} of ${rows.filter(r => r.code !== 'NONE').length}`);
console.log('  (identical call shape; only end_date differs — so the bench REFUSES the same-day daily bar)');

// one fully worked day, for the report
console.log('\n---- worked example: 2024-02-07, 002144.XSHE ----');
for (const r of rows.filter(r => r.date === '2024-02-07' && r.code !== 'NONE')) {
  console.log(`  ${r.clock} ${r.t.padEnd(18)} last=${r.last}  high_limit=${r.hl}  day_open=${r.open}  prev_close=${r.pc}`);
}
console.log(`  close(2024-02-07) = ${closeOfD('2024-02-07', '002144.XSHE')}   <- from 2024-02-08's prev_close`);
