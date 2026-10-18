/**
 * strategy-daily.js
 *
 * Cron job entry point for the daily join-quant pipeline.
 * Run order:
 *   1. Discover new strategies (2 API calls ≈ 147 strategies)
 *   2. Rebuild copy-queue sorted by composite score
 *   3. Iterate queue, clone each strategy, until access limit hit
 *   4. Normalize the newly-fetched strategies on the frozen TRAIN window + auto-create
 *      wiki stubs (utils/normalize-daily.js; best-effort, skips if CDP Chrome is down)
 *   5. Report summary (incl. new gate-passers) to WeChat
 *
 * Usage:
 *   node utils/strategy-daily.js          # full pipeline (fetch + normalize)
 *   node utils/strategy-daily.js --discover-only   # discovery only (fast)
 *   node utils/strategy-daily.js --copy-only       # copy only (uses existing queue)
 *   node utils/strategy-daily.js --no-normalize    # fetch, skip the normalization phase
 */

const { execSync, execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

// Global notification CLI (~/.local/bin/notify → ~/.notify/). Delivers to WeChat via Server酱.
const NOTIFY_BIN = path.join(os.homedir(), '.local', 'bin', 'notify');

const DATA_DIR = path.join(__dirname, '..', 'data');
const COPY_QUEUE_FILE = path.join(DATA_DIR, 'copy-queue.json');
const DISCOVERED_FILE = path.join(DATA_DIR, 'discovered.json');

// Discovery now delegates to utils/strategy-discover.js rather than keeping a
// second copy of the listV2 crawl. That copy used `curl` directly, which since
// the geo-block went up returns an HTTP 200 HTML page and made JSON.parse throw
// on every call. strategy-discover routes through the logged-in CDP browser and
// walks multiple pages. See utils/jq-http.js.
const discover = require('./strategy-discover');

// Pages per (cate,type) combo for the nightly sweep. Override with JQ_DISCOVER_PAGES.
const DISCOVER_PAGES = parseInt(process.env.JQ_DISCOVER_PAGES || '5', 10);

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function loadStore() {
  ensureDataDir();
  if (fs.existsSync(DISCOVERED_FILE))
    return JSON.parse(fs.readFileSync(DISCOVERED_FILE, 'utf8'));
  return { lastScraped: null, strategies: {}, scrapedPostIds: [] };
}

function saveStore(store) {
  fs.writeFileSync(DISCOVERED_FILE, JSON.stringify(store, null, 2));
}

function loadQueue() {
  if (fs.existsSync(COPY_QUEUE_FILE))
    return JSON.parse(fs.readFileSync(COPY_QUEUE_FILE, 'utf8'));
  return { queue: [], copied: {}, lastUpdated: null };
}

function saveQueueData(queueData) {
  fs.writeFileSync(COPY_QUEUE_FILE, JSON.stringify(queueData, null, 2));
}

// buildCopyQueue lives in strategy-discover.js. This file used to keep a second
// copy that filtered on `s.postId`; after the uniqueKey re-key that copy matched
// nothing in the `copied` map and would have re-queued every already-fetched
// strategy. One implementation only.
const buildCopyQueue = discover.buildCopyQueue;

async function discoveryPhase() {
  const before = Object.keys(discover.loadStore().strategies || {}).length;
  await discover.scrapeCommunityList({
    pages: DISCOVER_PAGES,
    limit: 200,
    cates: [3],
    types: ['isNew', 'isHot'],
  });
  const after = Object.keys(discover.loadStore().strategies || {}).length;
  const newCount = after - before;
  // Rank the research resources picked up alongside the strategies.
  try { discover.buildResourceQueue(); } catch (e) { console.error('[daily] resource queue:', e.message); }
  console.log(`[daily] Discovery done. +${newCount} new. Total: ${after}`);
  return newCount;
}

async function sendWeChatAlert(lines) {
  const msg = lines.join('\n');
  // Local record (append-only log; kept for debugging).
  const notifyFile = path.join(DATA_DIR, 'notifications.json');
  const notifs = fs.existsSync(notifyFile) ? JSON.parse(fs.readFileSync(notifyFile, 'utf8')) : [];
  notifs.push({ type: 'daily-pipeline', text: msg, at: new Date().toISOString() });
  fs.writeFileSync(notifyFile, JSON.stringify(notifs, null, 2));

  // Deliver to WeChat via the global notifier (immediate). Uses the same node running this
  // script so PATH doesn't matter; body is piped on stdin so multi-line text needs no escaping.
  // ⚠ Check the notifier exists before invoking it, and keep its stderr out of our log.
  //
  // This was `execFileSync(node, [NOTIFY_BIN, ...])` with `stdio: 'inherit'`. The binary is absent
  // on this machine, so every run printed a full `Cannot find module` stack trace into the daily
  // log — and `daily-pipeline.js`'s cause-extractor greps the tail for /error|Error|failed/, so it
  // reported that stack as the REASON the discover stage failed. The delivery was always caught
  // and queued; the misleading part was the noise. It cost real diagnosis time: a module-resolution
  // error looked like the discover bug while the actual cause was a 4-hour normalize sub-phase.
  if (!fs.existsSync(NOTIFY_BIN)) {
    console.log(`[daily] notify not installed (${NOTIFY_BIN}) — queued in notifications.json`);
  } else {
    try {
      const title = (lines[0] || '📡 join-quant 每日').replace(/\s+/g, ' ').slice(0, 60);
      execFileSync(process.execPath,
        [NOTIFY_BIN, '--source', 'join-quant-daily', '--level', 'info', '--title', title, '--now'],
        { input: msg, stdio: ['pipe', 'inherit', 'pipe'] });
      console.log('[daily] WeChat alert delivered via notify');
    } catch (e) {
      console.warn(`[daily] notify delivery failed (${String(e.message).split('\n')[0]}) — ` +
                   'queued in notifications.json');
    }
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const mode = args[0];
  const today = new Date().toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' });

  // Parse --limit N
  //
  // ⚠ Raised 3 -> 20 (user decision, 2026-10-17) because the ADMISSION RATE had become the
  // binding constraint instead of the backtest budget. Measured that day: the chain ran nine
  // stages, `data/pending-normalize.json` drained to `[]`, the deferred pool held 20 entries with
  // **0 retryable**, and the day finished at **used=36 of 180 minutes** — while 720 strategies sat
  // uncopied in the queue. At the measured ~3.3 min/backtest, 3 fetches is ~10-15 minutes of work
  // against a 180-minute budget, so ~80% of capacity went idle with the funnel's mouth as the only
  // reason. The old 3/day was right at 60 min/day with ~70 queued; neither still holds.
  //
  // ⚠ This does NOT relax the once-per-chain brake in `daily-pipeline.runDiscover` — that brake is
  // what keeps the total bounded (40 stages x 20 would be 800 fetches). The limit caps one run;
  // the brake caps the runs per day.
  let limit = 20;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--limit' && args[i + 1] != null) {
      limit = parseInt(args[i + 1]) || 20;
      i++;
    }
  }

  console.log(`\n=== join-quant Daily Pipeline | ${today} ===`);

  let newCount = 0;
  if (mode !== '--copy-only') {
    const queueData = loadQueue();
    const pendingCount = queueData.queue.filter(s => !queueData.copied[s.key || s.postId]).length;
    const SKIP_LIST_THRESHOLD = 100;
    if (pendingCount > SKIP_LIST_THRESHOLD) {
      console.log(`[daily] Queue has ${pendingCount} pending (>${SKIP_LIST_THRESHOLD}), skipping discovery`);
    } else {
      newCount = await discoveryPhase();
    }
  }

  const queueData = buildCopyQueue();
  const pendingAfterBuild = queueData.queue.filter(s => !queueData.copied[s.key || s.postId]).length;
  console.log(`[daily] Queue: ${pendingAfterBuild} pending, ${Object.keys(queueData.copied || {}).length} copied`);

  if (mode === '--discover-only') {
    console.log('[daily] Discovery-only mode, skipping fetch phase');
    console.log(
      `📡 每日策略发现完成 | ${today}\n` +
      `新增: ${newCount} 个策略\n` +
      `待抓取: ${queueData.queue.length} 个\n` +
      `已抓取: ${Object.keys(queueData.copied || {}).length} 个`
    );
    return;
  }

  // Refresh session cookies before fetching. The fetch phase authenticates via
  // data/cookies.json. We try username/password form login first (unattended),
  // then fall back to harvesting the live session from a running Chrome over
  // CDP when the form login is blocked by a CAPTCHA. Best-effort — if both fail
  // we proceed with the existing cookies.
  const { refreshCookies } = require('./refresh-cookies');
  const cookieRes = await refreshCookies();
  if (!cookieRes.ok) {
    console.warn(`[daily] Cookie refresh failed: ${cookieRes.error} — using existing cookies`);
  }

  // Fetch phase — read source + stats via API, save to strategies/
  const copiedBefore = new Set(Object.keys(loadQueue().copied || {}));
  const { processQueue } = require('./strategy-fetch');
  const { processed, limitHit } = await processQueue(limit);

  // Normalization phase — re-backtest the newly-fetched strategies on the frozen TRAIN
  // window and auto-create wiki stubs (best-effort; skips cleanly if CDP Chrome is down).
  // Hand the normalizer the SAVED FILENAMES, not ids. The `copied` map is keyed
  // by uniqueKey while strategy files are named after the (ephemeral) postId, so
  // passing keys made the normalizer's id->file lookup miss every time. markFetched
  // already records `sourceFile`, which is the only durable link between them.
  const copiedNow = loadQueue().copied || {};
  const newPostIds = Object.keys(copiedNow)
    .filter(k => !copiedBefore.has(k))
    .map(k => (copiedNow[k] && copiedNow[k].sourceFile) || k)   // filename when we have it
    .filter(Boolean);
  let normLines = [];
  // ⚠⚠ `--no-normalize` ENQUEUES but does not measure — it does not skip the step entirely.
  //
  // It used to skip it, and the enqueue lives inside `normalizeNew()`, so every strategy fetched
  // that day was stranded: nothing else appends to `data/pending-normalize.json`. Meanwhile the
  // default path ran backtests here, which is how the `discover` STAGE came to spend hours
  // measuring — 4h25m on 2026-10-16, killed only by STAGE_TIMEOUT_MIN=255 — outside the
  // `normalize` stage that owns the budget and the deferred pool.
  try {
    const nd = require('./normalize-daily');
    normLines = mode === '--no-normalize'
      ? nd.enqueueOnly(newPostIds).lines
      : nd.normalizeNew(newPostIds, { usageLimit: 55 }).lines;
  } catch (e) { normLines = [`⚠ 归一化阶段异常：${(e.message || '').slice(0, 60)}`]; }

  // Final summary
  const queueFinal = loadQueue();
  const totalCopied = Object.keys(queueFinal.copied || {}).length;
  const summary = [
    `📡 每日策略发现+归一化完成 | ${today}`,
    `新增: ${newCount} 个 | 本次克隆: ${processed} 个 | 待克隆: ${queueFinal.queue.length} | 已克隆: ${totalCopied}`,
    ...normLines,
  ];
  console.log('\n' + summary.join('\n'));
  await sendWeChatAlert(summary);
}

// CLI
if (require.main === module) {
  // ⚠⚠⚠ `jq.close()` is MANDATORY here, and its absence made this stage never exit.
  //
  // `jq-http` holds a Playwright CDP connection to the logged-in Chrome. Eight modules call
  // `jq.close()` — but each does so in its own `require.main === module` CLI block. This file
  // requires `strategy-discover` and `strategy-fetch` as MODULES, so those blocks never run, and
  // nothing closed the connection. The open socket
  // (`localhost:* -> localhost:9225 ESTABLISHED`) kept Node's event loop alive, so the process sat
  // idle forever after finishing its work.
  //
  // Measured 2026-10-17: all output written by 02:40:31, process still alive and idle at 02:45
  // (1.59s CPU, 1 open socket), and it would have sat until `STAGE_TIMEOUT_MIN=255` killed it.
  // ⚠ This is a SECOND, INDEPENDENT cause of the discover stage running for hours — the first was
  // the normalize sub-phase (see runDiscover). Either alone takes the stage to the timeout, which
  // is why fixing one did not fix the symptom: the work completed in ~3 minutes and the PROCESS
  // did not exit.
  //
  // `main()` must therefore be the only thing that opens jq-http in this process, and the close
  // must run on both paths — hence `finally`, not a trailing call.
  main()
    .catch(e => { console.error(e); process.exitCode = 1; })
    .finally(async () => {
      try { await require('./jq-http').close(); } catch { /* already gone */ }
    });
}

module.exports = { main, discoveryPhase, buildCopyQueue };
