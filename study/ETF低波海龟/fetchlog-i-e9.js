// Resolve an algorithm's backtestId, page its full 日志 with study/小市值/pagelog.js, write to logs/.
// Usage: node -e "require('./study/ETF低波海龟/fetchlog-i-e9.js')(algId, 'i-e9-3')"
const fs = require('fs');
const path = require('path');
const { forAlgorithm } = require('../../utils/backtest-log');
const { pageAll } = require('../小市值/pagelog');
const jq = require('../../utils/jq-http');
module.exports = async function (alg, name) {
  try {
    const r = await forAlgorithm(alg, { limit: 10 });
    if (!r.backtestId) throw new Error(r.err);
    const p = await pageAll(r.backtestId);
    const out = path.join(__dirname, 'logs', `${name}-train.log`);
    fs.writeFileSync(out, `state=${p.state} pages=${p.pages} lines=${p.lines.length} backtestId=${r.backtestId}\n` + p.lines.map(String).join('\n') + '\n');
    console.log('wrote', out, 'lines', p.lines.length, 'state', p.state);
  } finally {
    try { await jq.close(); } catch (e) { /* */ }
  }
};
