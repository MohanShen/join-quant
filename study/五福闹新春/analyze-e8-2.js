// node -e "require('./study/五福闹新春/analyze-e8-2.js')"
// Compares the per-day CHOSEN TARGET and the per-day weak/normal STATE between the
// baseline-e6 (13:10) run and the q-e8-2 (13:12) run, from the two harvested logs.
// Reads only; starts nothing.
const fs = require('fs');

function parse(file) {
  const lines = fs.readFileSync(file, 'utf8').split('\n');
  const target = {}, state = {}, clock = {};
  for (const l of lines) {
    const m = l.match(/^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}):\d{2} - \w+\s+- (.*)$/);
    if (!m) continue;
    const [, date, hhmm, body] = m;
    let t = null;
    if (body.includes('确定最终目标(防御模式)')) t = (body.match(/([0-9]{6}\.[A-Z]{4})/) || [, 'DEFENSIVE?'])[1] + '(def)';
    else if (body.includes('确定最终目标')) t = (body.match(/([0-9]{6}\.[A-Z]{4})/) || [, '?'])[1];
    else if (body.includes('无最终目标')) t = 'CASH';
    if (t) { target[date] = t; clock[date] = hhmm; }
    if (body.includes('【当前状态】')) state[date] = body.includes('走弱期') ? 'weak' : 'normal';
  }
  return { target, state, clock };
}

const A = parse('data/autostudy-logs/wufu-base-e6.full.txt');   // 13:10
const B = parse('data/autostudy-logs/wufu-q-e8-2.full.txt');    // 13:12

const clocksA = [...new Set(Object.values(A.clock))].sort();
const clocksB = [...new Set(Object.values(B.clock))].sort();
console.log('target-line clock stamps  base:', clocksA.join(','), ' | q-e8-2:', clocksB.join(','));

const daysA = Object.keys(A.target).sort(), daysB = Object.keys(B.target).sort();
console.log(`days with a target line  base: ${daysA.length} (${daysA[0]}..${daysA[daysA.length - 1]})`);
console.log(`days with a target line  q-e8-2: ${daysB.length} (${daysB[0]}..${daysB[daysB.length - 1]})`);

const common = daysA.filter(d => d in B.target);
console.log('common days:', common.length);

let diff = 0; const byState = { weak: [0, 0], normal: [0, 0], unknown: [0, 0] };
const diffDays = [];
for (const d of common) {
  const st = A.state[d] || 'unknown';
  byState[st][1]++;
  if (A.target[d] !== B.target[d]) { diff++; byState[st][0]++; diffDays.push([d, st, A.target[d], B.target[d]]); }
}
console.log(`\nTARGET DIFFERS on ${diff} of ${common.length} days (${(100 * diff / common.length).toFixed(1)}%)`);
for (const st of ['normal', 'weak', 'unknown']) {
  const [d, n] = byState[st];
  if (n) console.log(`  ${st}: ${d} of ${n} days differ (${(100 * d / n).toFixed(1)}%)`);
}

// did the weak/normal state itself ever move?
let stDiff = 0;
const stCommon = Object.keys(A.state).filter(d => d in B.state);
for (const d of stCommon) if (A.state[d] !== B.state[d]) stDiff++;
const wA = Object.values(A.state).filter(x => x === 'weak').length;
const wB = Object.values(B.state).filter(x => x === 'weak').length;
console.log(`\nweak-period days  base ${wA}/${Object.keys(A.state).length}  q-e8-2 ${wB}/${Object.keys(B.state).length}  state disagrees on ${stDiff} of ${stCommon.length} common days`);

// CASH / defensive census
const cash = (o) => Object.values(o.target).filter(t => t === 'CASH').length;
const def = (o) => Object.values(o.target).filter(t => t.endsWith('(def)')).length;
console.log(`CASH days   base ${cash(A)}  q-e8-2 ${cash(B)}`);
console.log(`DEF  days   base ${def(A)}  q-e8-2 ${def(B)}`);

// distinct names held
const names = (o) => new Set(Object.values(o.target));
console.log(`distinct targets  base ${names(A).size}  q-e8-2 ${names(B).size}`);

// target CHANGES (proxy for turnover)
const changes = (o) => { const d = Object.keys(o.target).sort(); let c = 0; for (let i = 1; i < d.length; i++) if (o.target[d[i]] !== o.target[d[i - 1]]) c++; return c; };
console.log(`target changes day-over-day  base ${changes(A)}  q-e8-2 ${changes(B)}`);

console.log('\nfirst 25 differing days (date, state, base -> q-e8-2):');
diffDays.slice(0, 25).forEach(r => console.log('  ', r.join('\t')));
console.log(`... ${Math.max(0, diffDays.length - 25)} more`);

// per-year split of the disagreement
for (const y of ['2022', '2023']) {
  const c = common.filter(d => d.startsWith(y));
  const dd = diffDays.filter(r => r[0].startsWith(y));
  console.log(`${y}: ${dd.length} of ${c.length} days differ (${(100 * dd.length / c.length).toFixed(1)}%)`);
}
