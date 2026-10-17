// node -e "require('./study/五福闹新春/analyze-e8-7.js')"
// Weak-day census for q-e8-7 from the harvested JQ log.
//  (C) 511880 day count out of the weak days + per-filter reason split on zero-pass days
//  (5) the decided-target census (确定最终目标 lines), plus the 13:10 WEAKHOLD carry-in census
const fs = require('fs');
const L = fs.readFileSync('data/autostudy-logs/wufu-q-e8-7.full.txt', 'utf8').split('\n');

const POOL = ['518880.XSHG', '513100.XSHG', '513500.XSHG', '513030.XSHG', '161226.XSHE',
  '501018.XSHG', '513520.XSHG', '159985.XSHE', '159980.XSHE'];
const POOLSET = new Set(POOL);

// walk, carrying the current date from timestamped lines (multi-line log.info blocks
// arrive as continuation lines with no timestamp)
let cur = null;
const day = {};                       // date -> { weakhold, targets[], rows[] }
const D = d => (day[d] = day[d] || { weakhold: null, targets: [], rows: [] });
for (const raw of L) {
  const m = raw.match(/^(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2} - \w+\s+- (.*)$/);
  let body = raw;
  if (m) { cur = m[1]; body = m[2]; }
  if (!cur) continue;
  if (body.includes('WEAKHOLD ')) {
    const t = body.match(/WEAKHOLD (\S+) \[(.*)\]/);
    D(cur).weakhold = t ? (t[2] ? t[2].split(',').map(s => s.trim().replace(/'/g, '')) : []) : null;
  }
  if (body.includes('确定最终目标')) {
    if (body.includes('防御模式')) D(cur).targets.push({ etf: '511880.XSHG', mode: 'defensive' });
    else {
      const t = body.match(/确定最终目标:\s*(\S+)/);
      if (t) D(cur).targets.push({ etf: t[1], mode: 'normal' });
    }
  }
  if (body.includes('无最终目标(空仓模式)')) D(cur).targets.push({ etf: null, mode: 'empty' });
  // step-1 per-ETF filter table row
  const r = body.match(/^(\d{6}\.XSH[GE]) .*?动量得分: (\S+) ([✅❌])，R²: (\S+) ([✅❌])，均线: MA\d+: (\S+) ([✅❌])，成交量比值: (\S+) ([✅❌])，短期风控: (\S+) ([✅❌])/);
  if (r && POOLSET.has(r[1])) {
    D(cur).rows.push({
      etf: r[1],
      mom: r[3] === '✅', ma: r[7] === '✅', vol: r[9] === '✅', loss: r[11] === '✅',
      momv: r[2], mav: r[6], volv: r[8], lossv: r[10],
    });
  }
}

const weakDays = Object.keys(day).filter(d => day[d].weakhold !== null).sort();
console.log('weak days (WEAKHOLD lines):', weakDays.length);

// ---- (C) what the strategy DECIDED to hold on each weak day ----
const decided = {};
let noTarget = 0, multi = 0;
for (const d of weakDays) {
  const t = day[d].targets;
  if (!t.length) { noTarget++; continue; }
  if (t.length > 1) multi++;
  const key = t.map(x => x.etf || 'CASH').join('+');
  decided[key] = (decided[key] || 0) + 1;
}
console.log('weak days with no 确定最终目标 line:', noTarget, ' with >1 target:', multi);
console.log('\n== DECIDED-TARGET census over weak days (from 确定最终目标) ==');
Object.entries(decided).sort((a, b) => b[1] - a[1])
  .forEach(([k, v]) => console.log(`  ${k}\t${v}\t${(v / weakDays.length * 100).toFixed(1)}%`));
const defDays = weakDays.filter(d => day[d].targets.some(t => t.mode === 'defensive'));
console.log(`\n511880 (defensive) decided on ${defDays.length} of ${weakDays.length} weak days` +
  ` = ${(defDays.length / weakDays.length * 100).toFixed(1)}%`);

// ---- reason split on the days that fell to 511880 ----
const split = { 'momentum-only': 0, 'MA10-only': 0, 'volume-only': 0, 'loss-only': 0, 'multi-filter': 0, 'no-rows': 0 };
const perFilterBlocked = { mom: 0, ma: 0, vol: 0, loss: 0 };
let unlockable = { mom: 0, ma: 0, vol: 0, loss: 0 };
for (const d of defDays) {
  const rows = day[d].rows;
  if (!rows.length) { split['no-rows']++; continue; }
  // the weak branch runs: 动量得分 (always), 均线 (active in weak), 成交量, 短期风控. R² inactive.
  const fails = rows.map(r => {
    const f = [];
    if (!r.mom) f.push('mom');
    if (!r.ma) f.push('ma');
    if (!r.vol) f.push('vol');
    if (!r.loss) f.push('loss');
    return f;
  });
  for (const k of ['mom', 'ma', 'vol', 'loss']) if (fails.some(f => f.includes(k))) perFilterBlocked[k]++;
  // which SINGLE filter, if dropped, would have admitted >=1 name that day
  const single = {};
  for (const f of fails) if (f.length === 1) single[f[0]] = true;
  for (const k of Object.keys(single)) unlockable[k]++;
  const keys = Object.keys(single);
  if (keys.length === 1) split[{ mom: 'momentum-only', ma: 'MA10-only', vol: 'volume-only', loss: 'loss-only' }[keys[0]]]++;
  else split['multi-filter']++;
}
console.log('\n== why zero of 9 passed, on the ' + defDays.length + ' defensive days ==');
console.log('  binding filter (the ONLY one whose removal would admit >=1 name):');
Object.entries(split).forEach(([k, v]) => console.log(`    ${k}\t${v}`));
console.log('  days on which each filter blocked >=1 name:', JSON.stringify(perFilterBlocked));
console.log('  days on which dropping that one filter alone would admit >=1 name:', JSON.stringify(unlockable));

// ---- 13:10 carry-in census (WEAKHOLD) ----
const carry = {};
let flat = 0;
for (const d of weakDays) {
  const h = day[d].weakhold;
  if (!h.length) { flat++; continue; }
  const k = h.slice().sort().join('+');
  carry[k] = (carry[k] || 0) + 1;
}
console.log(`\n== 13:10 CARRY-IN census (WEAKHOLD; position carried INTO the weak day) ==`);
console.log('  flat (no position) days:', flat);
Object.entries(carry).sort((a, b) => b[1] - a[1])
  .forEach(([k, v]) => console.log(`  ${k}\t${v}\t${(v / weakDays.length * 100).toFixed(1)}%`));

// ---- pool-presence sanity: the 9-name literal is what the weak branch ranked ----
const poolSizes = {};
for (const d of weakDays) poolSizes[day[d].rows.length] = (poolSizes[day[d].rows.length] || 0) + 1;
console.log('\npool rows seen per weak day (expect 9):', JSON.stringify(poolSizes));
