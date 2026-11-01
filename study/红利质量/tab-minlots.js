// Monthly funnel table from a paged run log: candidates N, TopM, bought, 1手保底 skips,
// mean 1-lot price of the target book (总1手成本 / 100 / M — a MEAN, the log carries no median).
// Usage: node -e "require('./study/红利质量/tab-minlots.js')(file)"
const fs = require('fs');
module.exports = function tab(file) {
  const L = fs.readFileSync(file, 'utf8').split('\n');
  const m = {};
  const g = k => m[k] || (m[k] = { skip: 0, skipPx: [] });
  for (const l of L) {
    const d = l.slice(0, 7); let x;
    if ((x = l.match(/候选(\d+)只 → 目标Top(\d+)/))) { Object.assign(g(d), { N: +x[1], M: +x[2], date: l.slice(0, 10) }); }
    if ((x = l.match(/【1手保底】(\S+) 1手需(\d+)元/))) { g(d).skip++; g(d).skipPx.push((+x[2] / 100).toFixed(0)); }
    if ((x = l.match(/买入: 目标(\d+)只中(\d+)只单笔成交（资金(\d+) 总1手成本(\d+)/))) { g(d).bought = +x[2]; g(d).lot = +x[4]; }
    if ((x = l.match(/MIN_LOTS预筛: (\d+)→(\d+)/))) g(d).minlotsDrop = +x[1] - +x[2];
    if ((x = l.match(/容量】.*保底1手(\d+)只/))) g(d).cap = +x[1];
  }
  console.log('month\tdate\tN\tM\tbought\tskips\tskipPx\tmeanLotPx\tminlotsDrop\tcapTrim');
  for (const k of Object.keys(m).sort()) {
    const v = m[k]; if (v.N == null && !v.skip) continue;
    console.log([k, v.date, v.N, v.M, v.bought, v.skip, v.skipPx.join('/'),
      v.lot != null ? (v.lot / 100 / v.M).toFixed(1) : '', v.minlotsDrop ?? '', v.cap ?? ''].join('\t'));
  }
};
