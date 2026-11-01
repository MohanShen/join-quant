// q-e9-sleeve-attrib helper: page the reference run's full 日志 tab (via study/小市值/pagelog.js,
// 100 lines/page until a short page) and save it locally so the attribution can be re-run offline.
// Usage: node -e "require('./study/价值红利多腿/dump-log.js').main()" -- <backtestId>
const fs = require('fs');
const path = require('path');
const { pageAll } = require('../小市值/pagelog.js');

async function main() {
  const bid = process.argv.slice(1).find(a => /^[a-f0-9]{32}$/.test(a));
  if (!bid) { console.error('usage: dump-log.js <backtestId>'); process.exitCode = 1; return; }
  const r = await pageAll(bid);
  if (r.raw) console.error('UNPARSED ' + r.raw);
  const out = path.join(__dirname, 'log-q-e9-s4-pit.txt');
  fs.writeFileSync(out, r.lines.map(String).join('\n') + '\n');
  console.log('state=' + r.state + ' pages=' + r.pages + ' lines=' + r.lines.length + ' -> ' + out);
  const first = String(r.lines[0] || ''), last = String(r.lines[r.lines.length - 1] || '');
  console.log('first: ' + first.slice(0, 160));
  console.log('last : ' + last.slice(0, 160));
}
module.exports = { main };
