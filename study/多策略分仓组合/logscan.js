// Scan a paged backtest log for the u-1 single-leg checks.
// usage: node -e "require('./study/多策略分仓组合/logscan.js').main('<logfile>')"
//    or: node -e "require('./study/多策略分仓组合/logscan.js').fetch('<backtestId>','<savePath>')"
const fs = require('fs');

function scan(L) {
  const err = L.filter(l => / - ERROR - /.test(l));
  const errOther = err.filter(l => !/同花顺概念/.test(l));
  console.log('lines', L.length, 'ERROR', err.length, 'ERROR(non-concept)', errOther.length);
  errOther.slice(0, 10).forEach(l => console.log('  ', l));
  const legs = {};
  for (const l of L) { const m = l.match(/\[(策略[^\]]*)\]/); if (m) legs[m[1]] = (legs[m[1]] || 0) + 1; }
  console.log('leg tag counts', JSON.stringify(legs));
  const trade = {};
  for (const l of L) {
    const m = l.match(/\[(策略[^\]]*)\]/); if (!m) continue;
    const t = l.match(/虚拟账户(买入|卖出)/);
    if (t) { const k = m[1] + ':' + t[1]; trade[k] = (trade[k] || 0) + 1; }
  }
  console.log('virtual trades per leg', JSON.stringify(trade));
  const days = re => [...new Set(L.filter(l => re.test(l)).map(l => l.slice(0, 10)))];
  const wd = d => new Date(d + 'T00:00:00Z').getUTCDay();
  for (const [n, re] of [['bull', /当前为牛市/], ['bear', /当前为熊市/], ['etf', /无适合股票，买入ETF/], ['emptyMonth', /空仓月份/], ['conceptFail', /读取同花顺概念失败/]]) {
    const d = days(re);
    console.log(n, d.length, 'days (wed', d.filter(x => wd(x) === 3).length + ')', d.join(' '));
  }
  const warn = L.filter(l => / - WARNING - /.test(l)).map(l => l.replace(/^\S+ \S+ - WARNING - /, '').slice(0, 40));
  const wc = {}; warn.forEach(w => wc[w] = (wc[w] || 0) + 1);
  console.log('WARNING kinds', JSON.stringify(wc));
}

function main(file) { scan(fs.readFileSync(file, 'utf8').split('\n')); }

async function fetch(bid, save) {
  const { pageAll } = require('../小市值/pagelog.js');
  const r = await pageAll(bid);
  console.log('state=' + r.state + ' pages=' + r.pages + ' lines=' + r.lines.length);
  const L = r.lines.map(String);
  if (save) fs.writeFileSync(save, L.join('\n') + '\n');
  scan(L);
}
module.exports = { scan, main, fetch };
