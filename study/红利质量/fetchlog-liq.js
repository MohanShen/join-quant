// Page a run's full 日志 tab to a file (q-e9-liq). Usage:
//   node -e "require('./study/红利质量/fetchlog-liq.js')" -- <algorithmId> <outFile>
const fs = require('fs');
const bl = require('../../utils/backtest-log.js');
const { pageAll } = require('../小市值/pagelog.js');
(async () => {
  const [alg, out] = process.argv.slice(1).filter(a => a !== '--' && a !== '-e');
  const r = await bl.forAlgorithm(alg, { limit: 10 });
  console.log('backtestId', r.backtestId, 'errTab', (r.error || []).length);
  const p = await pageAll(r.backtestId);
  fs.writeFileSync(out, p.lines.map(String).join('\n') + '\n');
  console.log('state', p.state, 'pages', p.pages, 'lines', p.lines.length);
})().catch(e => { console.error(e); process.exitCode = 1; })
  .finally(async () => { try { await require('../../utils/jq-http.js').close(); } catch (e) {} });
