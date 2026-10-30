// Offline analysis of the q-e9-bench-lastprice probe log. Reads nothing but the saved log file.
//
// The three comparisons, in order of how much they can be argued with:
//   (A) WITHIN-DAY  : last(D, s) across the four timepoints 9:05 / 10:00 / 14:25 / 14:55.
//   (B) NEXT-DAY PC : last(D, s) vs prev_close(D+1, s). prev_close is queried at
//                     end_date=context.previous_date, so this is day D's OFFICIAL close arriving
//                     from a source that cannot be accused of lookahead. THIS IS THE AUTHORITATIVE
//                     "equals the day's close" test.
//   (C) SAME-DAY DC : last(D, s) vs day_close(D, s) = get_price(end_date=context.current_dt).
//                     Corroboration only — that call's own semantics are part of what is in doubt.
// Plus the benign alternative reading, (D) last(D, s) vs prev_close(D, s): if last_price were
// simply YESTERDAY's close there would be no lookahead at all.
const fs = require('fs');
const path = require('path');

const txt = fs.readFileSync(path.join(__dirname, 'benchsem-log.txt'), 'utf8');
const RE = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}):\d{2} - ERROR - BENCHSEM t=(\S+) date=(\S+) code=(\S+) last=(\S+) high_limit=(\S+) open=(\S+) prev_close=(\S+) day_close=(\S+)/;
const rows = [];
let fails = 0;
for (const l of txt.split('\n')) {
  if (/BENCHSEM-FAIL/.test(l)) { fails++; continue; }
  const m = RE.exec(l);
  if (!m) continue;
  rows.push({ date: m[1], clock: m[2], t: m[3], code: m[5],
              last: m[6], hl: m[7], open: m[8], pc: m[9], dc: m[10] });
}
console.log(`rows=${rows.length}  BENCHSEM-FAIL=${fails}`);
const flat = rows.filter(r => r.code === 'NONE').length;
console.log(`code=NONE (flat) ${flat}  |  with a holding ${rows.length - flat}`);
const nanLast = rows.filter(r => r.code !== 'NONE' && !/^[\d.]+$/.test(r.last)).length;
console.log(`non-numeric last on a holding: ${nanLast}`);

// ---- (A) within-day identity across timepoints ----
const byDay = new Map();
for (const r of rows) {
  if (r.code === 'NONE') continue;
  const k = r.date;
  if (!byDay.has(k)) byDay.set(k, []);
  byDay.get(k).push(r);
}
let sameCodeDays = 0, allIdentical = 0, differing = [];
for (const [d, rs] of byDay) {
  const codes = new Set(rs.map(r => r.code));
  if (codes.size !== 1 || rs.length < 2) continue;   // only compare like with like
  sameCodeDays++;
  const vals = new Set(rs.map(r => r.last));
  if (vals.size === 1) allIdentical++;
  else differing.push([d, rs.map(r => `${r.clock}:${r.last}`).join(' ')]);
}
console.log(`\n(A) WITHIN-DAY  days where all timepoints report the SAME code: ${sameCodeDays}`);
console.log(`    last_price identical across every timepoint: ${allIdentical}`);
console.log(`    days with ANY intraday difference: ${differing.length}`);
for (const [d, s] of differing.slice(0, 15)) console.log(`      ${d}  ${s}`);

// ---- (B) last(D) vs prev_close(D+1), same code ----
const dates = [...new Set(rows.map(r => r.date))].sort();
const pcOn = new Map();   // date|code -> prev_close
const lastOn = new Map(); // date|code -> Set of last values
for (const r of rows) {
  if (r.code === 'NONE') continue;
  pcOn.set(r.date + '|' + r.code, r.pc);
  const k = r.date + '|' + r.code;
  if (!lastOn.has(k)) lastOn.set(k, new Set());
  lastOn.get(k).add(r.last);
}
let pairs = 0, eqClose = 0, neq = [];
for (let i = 0; i + 1 < dates.length; i++) {
  const d = dates[i], n = dates[i + 1];
  for (const [k, vals] of lastOn) {
    const [kd, code] = k.split('|');
    if (kd !== d) continue;
    const nextPc = pcOn.get(n + '|' + code);
    if (nextPc == null || !/^[\d.]+$/.test(nextPc)) continue;
    pairs++;
    const v = [...vals];
    const hit = v.every(x => Math.abs(parseFloat(x) - parseFloat(nextPc)) < 0.005);
    if (hit) eqClose++;
    else neq.push(`${d} ${code} last=${v.join('/')} closeOfD(from ${n} prev_close)=${nextPc}`);
  }
}
console.log(`\n(B) NEXT-DAY PC  (D,code) pairs where the same code is still held on D+1: ${pairs}`);
console.log(`    last_price(D) == close(D): ${eqClose}   differs: ${neq.length}`);
for (const s of neq.slice(0, 15)) console.log(`      ${s}`);

// ---- (C) same-day day_close ----
let dcN = 0, dcEq = 0, dcNeq = [];
for (const r of rows) {
  if (r.code === 'NONE' || !/^[\d.]+$/.test(r.dc) || !/^[\d.]+$/.test(r.last)) continue;
  dcN++;
  if (Math.abs(parseFloat(r.dc) - parseFloat(r.last)) < 0.005) dcEq++;
  else dcNeq.push(`${r.date} ${r.clock} ${r.code} last=${r.last} day_close=${r.dc}`);
}
console.log(`\n(C) SAME-DAY DC  readings with a numeric day_close: ${dcN}`);
console.log(`    last_price == day_close: ${dcEq}   differs: ${dcNeq.length}`);
for (const s of dcNeq.slice(0, 10)) console.log(`      ${s}`);

// ---- (D) the benign reading: is last_price just YESTERDAY's close? ----
let dN = 0, dEq = 0;
for (const r of rows) {
  if (r.code === 'NONE' || !/^[\d.]+$/.test(r.pc) || !/^[\d.]+$/.test(r.last)) continue;
  dN++;
  if (Math.abs(parseFloat(r.pc) - parseFloat(r.last)) < 0.005) dEq++;
}
console.log(`\n(D) BENIGN READING  last_price == prev_close (same row): ${dEq} of ${dN}`);
console.log(`    (if this were ~all, last_price would be yesterday's close and there is no leak)`);

// ---- raw triples for the report ----
console.log('\n---- RAW: the first 6 days with a holding, every timepoint ----');
let shown = 0;
for (const d of dates) {
  const rs = rows.filter(r => r.date === d && r.code !== 'NONE');
  if (!rs.length) continue;
  const nd = dates[dates.indexOf(d) + 1];
  for (const r of rs) {
    const closeOfD = nd ? pcOn.get(nd + '|' + r.code) : undefined;
    console.log(`  ${d} ${r.clock} ${r.t.padEnd(18)} ${r.code} last=${r.last} hl=${r.hl} open=${r.open} prevclose=${r.pc} dayclose=${r.dc} | close(D) via D+1 = ${closeOfD || '-'}`);
  }
  if (++shown >= 6) break;
}
