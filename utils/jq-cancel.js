/**
 * jq-cancel.js — cancel the backtest this pipeline left running.
 *
 * ## Why this exists
 *
 * The research stage is a Claude agent loop. Its wrapper hands it a prompt and waits for the
 * session to exit — but the agent runs long backtests in the background, so the session can end
 * cleanly (rc=0) with a run still in flight. Measured 2026-10-06: the stage finished at 22:01
 * having launched a backtest at ~21:05, which was still listed 57 minutes later with nobody left
 * to read its panel. The minutes were spent and the result was lost.
 *
 * An orphan used to be worse than wasteful: it refused the next stage's first backtest, the wait
 * expired, and the chain ended — the signature of every under-spent day (09-29 used 0/180).
 * Zombie tolerance and baseline completion have since defanged that, but the quota is still gone.
 *
 * Cancelling beats waiting here. Once the agent has exited, nothing can read the result, so
 * waiting for the run to finish buys nothing and costs the whole remaining cap in billed minutes.
 *
 * ⚠ Only safe because the pipeline holds the SHARED lock (`data/jq-pipeline.lock`): one JQ
 * backtest consumer at a time, so a live run at this moment is ours. Do not call it from
 * anywhere that does not hold that lock — it would cancel somebody else's work.
 *
 * It reuses the executor's own `cancelBacktest`, which selects the youngest run under the cap and
 * VERIFIES the entry left running[] (matched on start time, because ids are re-minted). A second
 * copy of that logic would be free to drift from it.
 *
 * Usage:
 *   node utils/jq-cancel.js [--cap-min N]     # exit 0 = clear (cancelled or nothing running)
 *                                             # exit 1 = still listed (now a zombie; it ages out)
 */

const path = require('path');

const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';

async function main(capMin) {
  // ⚠ Set this BEFORE requiring the executor: it reads JQ_MAX_POLL_MS at module load to derive
  // the cap that `cancelBacktest` uses to tell our run from a zombie.
  if (capMin) process.env.JQ_MAX_POLL_MS = String(capMin * 60 * 1000);
  const { chromium } = require('playwright');
  const { cancelBacktest, readRunning } = require(path.join(__dirname, 'strategy-post-backtest.js'));

  const browser = await chromium.connectOverCDP(CDP);
  try {
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    if (!page) { console.log('[cancel] no joinquant page — cannot act'); return 0; }

    const before = await readRunning(page);
    if (before == null) { console.log('[cancel] could not read running[] — leaving it alone'); return 0; }
    if (!before.length) { console.log('[cancel] nothing running — no orphan'); return 0; }
    console.log(`[cancel] ${before.length} entr(y/ies) listed: ` +
                before.map(r => `${r.usedSec} (started ${r.time})`).join(', '));

    const ok = await cancelBacktest(page);
    const after = await readRunning(page);
    const left = (after || []).length;
    console.log(`[cancel] ${ok ? 'cancelled' : 'could NOT cancel'}; ${left} still listed`);
    return left === 0 ? 0 : 1;
  } finally {
    // Detach only — closing the page would destroy the CDP cookie context.
    try { await browser.close(); } catch { /* best effort */ }
  }
}

module.exports = { main };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const i = argv.indexOf('--cap-min');
  const capMin = i >= 0 ? parseInt(argv[i + 1], 10) : 0;
  main(Number.isFinite(capMin) ? capMin : 0)
    .then(code => process.exit(code))
    .catch(e => { console.error('[cancel] FATAL ' + e.message); process.exit(0); });  // never fail a stage
}
