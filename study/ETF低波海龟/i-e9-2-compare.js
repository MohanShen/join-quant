// i-e9-2 vs base: per-day lowest-ranked name (波动率最低三只 first) and held name, from the two full logs.
// Usage: node -e "require('./study/ETF低波海龟/i-e9-2-compare.js')"
const fs = require('fs');
const path = require('path');
function parse(f) {
  const L = fs.readFileSync(path.join(__dirname, 'logs', f), 'utf8').split('\n');
  const best = {}, held = {}, med = {}, events = [];
  let cur = null;
  for (const l of L) {
    const d = l.slice(0, 10);
    if (!/^\d{4}-\d\d-\d\d/.test(d)) continue;
    let m;
    if ((m = l.match(/波动率最低三只：(\S+?) /))) best[d] = m[1];
    if ((m = l.match(/风险资产波动率中位数 ([\d.]+)%/))) med[d] = +m[1];
    if ((m = l.match(/(建仓|换入|换回)：(\S+?) /)) || (m = l.match(/(避险买入)：(\S+?)，/))) { cur = m[2]; events.push(d + ' ' + m[1] + ' ' + cur); }
    if ((m = l.match(/止损：(\S+?) /))) { cur = null; events.push(d + ' 止损 ' + m[1]); }
    if ((m = l.match(/止盈：(\S+?) /))) events.push(d + ' 止盈 ' + m[1]);
    if ((m = l.match(/加仓完成：(\S+?)，现 (\d)/))) events.push(d + ' 加仓 ' + m[1] + ' ' + m[2] + 'U');
    if (best[d] !== undefined) held[d] = cur;
  }
  return { best, held, med, events };
}
const b = parse('q-e9-1-train.log'), v = parse('i-e9-2-train.log');
const days = Object.keys(b.best).filter(d => d in v.best);
const bd = days.filter(d => b.best[d] !== v.best[d]);
const hd = days.filter(d => b.held[d] !== v.held[d]);
console.log('days', days.length, 'lowest-ranked name differs', bd.length, 'held name (end of 09:35) differs', hd.length);
const vm = Object.values(v.med);
console.log('i-e9-2 median: max', Math.max(...vm), 'days>40%', vm.filter(x => x > 40).length, 'of', vm.length);
console.log('i-e9-2 events:\n  ' + v.events.join('\n  '));
