// Resolve an algorithmId to its backtestId, page the whole log, save + scan it (logscan.scan),
// and count leg-B real buys/skips. Also prints the 错误 tab length.
// usage: node -e "require('./study/多策略分仓组合/alglog.js').main('<algorithmId>','study/多策略分仓组合/<id>.log')"
const fs = require('fs');
const path = require('path');

async function main(alg, save) {
  const bl = require('../../utils/backtest-log.js');
  try {
    const r = await bl.forAlgorithm(alg, { limit: 100 });
    if (!r.backtestId) { console.log('resolve failed', r.err); return; }
    console.log('backtestId', r.backtestId, 'errorTab', (r.error || []).length);
    (r.error || []).slice(0, 5).forEach(l => console.log('  ERRTAB', String(l).slice(0, 200)));
    await require('./logscan.js').fetch(r.backtestId, path.resolve(__dirname, '../..', save));
    const L = fs.readFileSync(path.resolve(__dirname, '../..', save), 'utf8').split('\n');
    const bBuy = L.filter(l => /\[策略B[^\]]*\] 买入 /.test(l)).length;
    const bSell = L.filter(l => /\[策略B[^\]]*\] 卖出 /.test(l)).length;
    const cand = L.filter(l => /\[策略B[^\]]*\] 今日成分股数量/.test(l)).map(l => +((l.match(/候选股票数量：(\d+)/) || [])[1]));
    const s = cand.slice().sort((a, b) => a - b);
    console.log('legB real buys', bBuy, 'sells', bSell, 'prepare-days-with-candidates', cand.length,
      'candidates median', s[Math.floor(s.length / 2)], 'max', s[s.length - 1]);
  } finally {
    try { await require('../../utils/jq-http.js').close(); } catch (e) {}
  }
}
module.exports = { main };
