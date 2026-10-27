// Count the 走弱期 days in the q-e9-avoid-off run's own log.
// ⚠ /algorithm/backtest/log serves 100 lines per request regardless of `limit` (CLAUDE.md),
// so page by offset until a short page.
const jq = require('../../utils/jq-http');

const ALG = '47075c43fb94cdf82d2edcfa9c3c7d58'; // q-e9-avoid-off-d9dafab2 run, 2026-10-27

(async () => {
  const bl = await jq.jqText(`https://www.joinquant.com/algorithm/backtest/buildList?algorithmId=${ALG}`);
  const ids = [...new Set([...String(bl).matchAll(/backtestId[=":\s]+([a-f0-9]{32})/g)].map(x => x[1]))];
  console.log('resolved backtestIds:', ids.join(' '));
  const bid = ids[ids.length - 1];

  const lines = [];
  for (let off = 0; off < 20000; off += 100) {
    const r = await jq.jqJson(`https://www.joinquant.com/algorithm/backtest/log?backtestId=${bid}&offset=${off}&limit=100&ajax=1`);
    const arr = (r && r.data && r.data.logArr) || [];
    lines.push(...arr.map(x => (typeof x === 'string' ? x : JSON.stringify(x))));
    if (arr.length < 100) break;
  }
  console.log('log lines:', lines.length);

  const pick = (re) => lines.filter(l => re.test(l));
  const enter = pick(/进入走弱期/);
  const recover = pick(/恢复正常期|走弱期结束|恢复/);
  const weakPool = pick(/【走弱期】/);
  const forced = pick(/【强制】/);
  const statusWeak = pick(/当前状态：🔴走弱期|🔴走弱期/);
  console.log('进入走弱期:', enter.length);
  enter.forEach(l => console.log('   ', l.slice(0, 160)));
  console.log('恢复/退出:', recover.length);
  recover.forEach(l => console.log('   ', l.slice(0, 160)));
  console.log('【走弱期】pool-switch log lines:', weakPool.length);
  console.log('【强制】full-pool log lines:', forced.length);
  console.log('lines mentioning 🔴走弱期:', statusWeak.length);
  const days = new Set(statusWeak.map(l => (l.match(/\d{4}-\d{2}-\d{2}/) || [''])[0]).filter(Boolean));
  console.log('distinct calendar days in 走弱期 state:', days.size);
  if (days.size && days.size <= 60) console.log('   ', [...days].sort().join(' '));
  await jq.close();
})().catch(async e => { console.error('ERR', e.message); try { await jq.close(); } catch {} process.exitCode = 1; });
