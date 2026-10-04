// Polls the JQ account's running-backtest count every 60s and exits 0 with "CLEAR" when it is
// zero (so a new run can start without CONCURRENT-STOP). Prints one progress line every 5 min.
// Waiting spends no quota minutes. Gives up after MAX_MIN (exit 3) so a phantom cannot hold the
// session forever — a phantom is reported, never worked around (git 31dc1c5).
//   node -e "require('./study/打板短线/wait-clear.js')"
const h = require('../../utils/jq-http');
const MAX_MIN = parseInt(process.env.WAIT_CLEAR_MAX_MIN || '28', 10);
(async () => {
  const t0 = Date.now();
  let tick = 0;
  for (;;) {
    let r = null;
    try {
      const j = await h.jqJson('https://www.joinquant.com/algorithm/index/statistics');
      r = (j.data && j.data.running) || [];
    } catch (e) { console.log('ERR ' + e.message); }
    if (r && r.length === 0) { console.log('CLEAR running=0'); break; }
    if (r && tick % 5 === 0) console.log(`running=${r.length} age=${r[0].usedSec} name=${r[0].name}`);
    if (Date.now() - t0 > MAX_MIN * 60 * 1000) { console.log(`GIVEUP still running after ${MAX_MIN} min`); process.exitCode = 3; break; }
    tick++;
    await new Promise(res => setTimeout(res, 60 * 1000));
  }
  await h.close();
})();
