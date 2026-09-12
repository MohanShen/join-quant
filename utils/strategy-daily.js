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

function buildCopyQueue() {
  const store = loadStore();
  const queueData = loadQueue();
  const copiedPostIds = new Set(Object.keys(queueData.copied));

  const pending = Object.values(store.strategies)
    .filter(s => !copiedPostIds.has(s.postId));

  // ── Title-based deduplication ────────────────────────────────────────────
  // Keep the highest-scoring post per unique title.
  const bestByTitle = new Map();
  for (const s of pending) {
    const score = (s.likes || 0) + (s.clones || 0) * 0.5;
    const existing = bestByTitle.get(s.title);
    if (!existing) {
      bestByTitle.set(s.title, { ...s, _score: score });
    } else {
      if (score > existing._score ||
          (score === existing._score && (s.clones || 0) > (existing.clones || 0))) {
        bestByTitle.set(s.title, { ...s, _score: score });
      }
    }
  }

  const deduped = [...bestByTitle.values()].sort((a, b) => b._score - a._score);

  queueData.queue = deduped.map((s, idx) => ({
    rank: idx + 1,
    postId: s.postId,
    backtestId: s.backtestId,
    title: s.title,
    url: s.url,
    likes: s.likes || 0,
    clones: s.clones || 0,
    annualReturn: s.annualReturn,
    compositeScore: s._score.toFixed(2),
    addedToQueueAt: new Date().toISOString(),
  }));

  const dupRemoved = pending.length - deduped.length;
  if (dupRemoved > 0) {
    console.log(`[daily] Title dedup: removed ${dupRemoved} duplicate posts (${pending.length} → ${deduped.length})`);
  }

  queueData.lastUpdated = new Date().toISOString();
  saveQueueData(queueData);
  return queueData;
}

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
  try {
    const title = (lines[0] || '📡 join-quant 每日').replace(/\s+/g, ' ').slice(0, 60);
    execFileSync(process.execPath,
      [NOTIFY_BIN, '--source', 'join-quant-daily', '--level', 'info', '--title', title, '--now'],
      { input: msg, stdio: ['pipe', 'inherit', 'inherit'] });
    console.log('[daily] WeChat alert delivered via notify');
  } catch (e) {
    console.warn(`[daily] notify delivery failed (${e.message}) — queued in notifications.json`);
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const mode = args[0];
  const today = new Date().toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' });

  // Parse --limit N
  let limit = 3; // default 3 per day
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--limit' && args[i + 1] != null) {
      limit = parseInt(args[i + 1]) || 3;
      i++;
    }
  }

  console.log(`\n=== join-quant Daily Pipeline | ${today} ===`);

  let newCount = 0;
  if (mode !== '--copy-only') {
    const queueData = loadQueue();
    const pendingCount = queueData.queue.filter(s => !queueData.copied[s.postId]).length;
    const SKIP_LIST_THRESHOLD = 100;
    if (pendingCount > SKIP_LIST_THRESHOLD) {
      console.log(`[daily] Queue has ${pendingCount} pending (>${SKIP_LIST_THRESHOLD}), skipping discovery`);
    } else {
      newCount = await discoveryPhase();
    }
  }

  const queueData = buildCopyQueue();
  const pendingAfterBuild = queueData.queue.filter(s => !queueData.copied[s.postId]).length;
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
  const newPostIds = Object.keys(loadQueue().copied || {}).filter(p => !copiedBefore.has(p));
  let normLines = [];
  if (mode !== '--no-normalize') {
    try {
      const { normalizeNew } = require('./normalize-daily');
      normLines = normalizeNew(newPostIds, { usageLimit: 55 }).lines;
    } catch (e) { normLines = [`⚠ 归一化阶段异常：${(e.message || '').slice(0, 60)}`]; }
  }

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
  main().catch(e => { console.error(e); process.exit(1); });
}

module.exports = { main, discoveryPhase, buildCopyQueue };
