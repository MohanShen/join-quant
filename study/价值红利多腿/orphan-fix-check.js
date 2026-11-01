// q-e9-orphan-fix helper (zero backtests): are s1/s2/s4 trades identical to the reference (the
// subtraction's validity condition beyond "all ORPHANSYNC lines are s3")? what does s3 do differently?
// is 600368 flat after 2024-08-15? where do the 订单委托失败 lines differ?
// Usage: node -e "require('./study/价值红利多腿/orphan-fix-check.js').main()"
const fs = require('fs');
const path = require('path');
const rd = f => fs.readFileSync(path.join(__dirname, f), 'utf8').split('\n');
const TR = /^(\S+ \S+) - INFO\s+- \[(s\d)\]\[(买入|卖出)\] (\S+) amt=(\d+) px=([\d.]+) val=([\d.]+)/;

function main() {
  const A = rd('log-q-e9-s4-pit.txt'), B = rd('log-q-e9-orphan-fix.txt');
  const tr = (L, keep) => L.map(l => l.match(TR)).filter(Boolean).filter(m => keep(m[2])).map(m => m.slice(1).join(' '));
  for (const sid of ['s1', 's2', 's4']) {
    const a = tr(A, s => s === sid), b = tr(B, s => s === sid);
    console.log(sid, 'trades ref', a.length, 'fix', b.length, 'identical', a.join('\n') === b.join('\n'));
  }
  const a3 = tr(A, s => s === 's3'), b3 = tr(B, s => s === 's3');
  const sa = new Set(a3), sb = new Set(b3);
  console.log('s3 trades ref', a3.length, 'fix', b3.length);
  console.log('-- s3 only in ref:'); a3.filter(x => !sb.has(x)).forEach(x => console.log('  ' + x));
  console.log('-- s3 only in fix:'); b3.filter(x => !sa.has(x)).forEach(x => console.log('  ' + x));
  const fail = L => L.filter(l => /订单委托失败/.test(l)).map(l => l.slice(0, 16) + ' ' + (l.match(/security=(\S+)/) || [])[1] + ' ' + (l.match(/error=(.*)\)$/) || [])[1]);
  const fa = fail(A), fb = fail(B);
  const months = L => L.reduce((o, x) => { const k = x.slice(0, 7) + ' ' + x.split(' ')[2]; o[k] = (o[k] || 0) + 1; return o; }, {});
  console.log('order failures ref', fa.length, JSON.stringify(months(fa)));
  console.log('order failures fix', fb.length, JSON.stringify(months(fb)));
  const P = JSON.parse(fs.readFileSync(path.join(__dirname, 'pos-q-e9-orphan-fix.json'), 'utf8'));
  const rows = P.filter(r => /600368/.test(r.stock)).map(r => r.date + ' ' + r.amount);
  console.log('600368 持仓 rows fix: first', rows[0], 'last', rows[rows.length - 1], 'n', rows.length);
  const PR = JSON.parse(fs.readFileSync(path.join(__dirname, 'pos-q-e9-s4-pit.json'), 'utf8'));
  const rr = PR.filter(r => /600368/.test(r.stock)).map(r => r.date + ' ' + r.amount);
  console.log('600368 持仓 rows ref: last', rr[rr.length - 1], 'n', rr.length);
  const ye = PR.filter(r => /600368/.test(r.stock) && r.date === '2024-12-31')[0];
  if (ye) console.log('ref 600368 on 12-31', ye.amount, ye.price, ye.value);
}
module.exports = { main };
