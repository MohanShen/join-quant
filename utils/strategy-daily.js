/**
 * strategy-daily.js
 *
 * Cron job entry point for the daily join-quant pipeline.
 * Run order:
 *   1. Discover new strategies (2 API calls ≈ 147 strategies)
 *   2. Rebuild copy-queue sorted by composite score
 *   3. Iterate queue, clone each strategy, until access limit hit
 *   4. Report summary to WeChat
 *
 * Usage:
 *   node utils/strategy-daily.js          # full pipeline
 *   node utils/strategy-daily.js --discover-only   # discovery only (fast)
 *   node utils/strategy-daily.js --copy-only       # copy only (uses existing queue)
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const COPY_QUEUE_FILE = path.join(DATA_DIR, 'copy-queue.json');
const DISCOVERED_FILE = path.join(DATA_DIR, 'discovered.json');

/**
 * Use curl via execSync to bypass VPN HTTPS interference.
 * @param {string} url
 * @returns {object} parsed JSON
 */
function httpGet(url) {
  const cmd = `curl -s "${url.replace(/"/g, '\\"')}" \
    -H "Accept: application/json" \
    -H "X-Requested-With: XMLHttpRequest" \
    -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"`;
  const out = execSync(cmd, { timeout: 20000 });
  return JSON.parse(out.toString());
}

async function fetchListPage({ cate = 3, type = 'isNew', limit = 200 }) {
  const url = `https://www.joinquant.com/community/post/listV2?limit=${limit}&page=1&cate=${cate}&type=${type}`;
  const json = await httpGet(url);
  if (!json.data || !json.data.list) return [];
  return json.data.list
    .filter(item => {
      if (!item.backtestId || item.backtestId.length !== 32) return false;
      const tags = (item.tagInfo || []).map(t => t.name);
      if (tags.includes('文章') && tags.includes('函数')) return false;
      if (tags.includes('研报分享')) return false;
      return true;
    })
    .map(item => ({
      postId: item.postId,
      backtestId: item.backtestId,
      title: item.title,
      url: `https://www.joinquant.com/view/community/detail/${item.postId}`,
      likes: parseInt(item.likeCount) || 0,
      clones: parseInt(item.backtestCloneCount) || 0,
      tags: (item.tagInfo || []).map(t => t.name),
      discoveredAt: new Date().toISOString(),
    }));
}

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
  const store = loadStore();
  let newCount = 0;

  const calls = [
    { cate: 3, type: 'isNew', limit: 200 },
    { cate: 3, type: 'isHot', limit: 200 },
  ];

  for (const combo of calls) {
    const strategies = await fetchListPage(combo);
    for (const s of strategies) {
      if (store.scrapedPostIds.includes(s.postId)) continue;
      store.scrapedPostIds.push(s.postId);
      store.strategies[s.postId] = s;
      newCount++;
    }
    console.log(`[daily] ${combo.type}: +${strategies.length} strategies`);
  }

  store.lastScraped = new Date().toISOString();
  saveStore(store);
  console.log(`[daily] Discovery done. +${newCount} new. Total: ${Object.keys(store.strategies).length}`);
  return newCount;
}

async function sendWeChatAlert(lines) {
  const msg = lines.join('\n');
  const notifyFile = path.join(DATA_DIR, 'notifications.json');
  const notifs = fs.existsSync(notifyFile) ? JSON.parse(fs.readFileSync(notifyFile, 'utf8')) : [];
  notifs.push({ type: 'daily-pipeline', text: msg, at: new Date().toISOString() });
  fs.writeFileSync(notifyFile, JSON.stringify(notifs, null, 2));
  console.log(`[daily] WeChat alert queued: ${msg.slice(0, 100)}`);
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
  const { processQueue } = require('./strategy-fetch');
  const { processed, limitHit } = await processQueue(limit);

  // Final summary
  const queueFinal = loadQueue();
  const totalCopied = Object.keys(queueFinal.copied || {}).length;
  const summary = [
    `📡 每日策略发现完成 | ${today}`,
    `新增: ${newCount} 个策略`,
    `待克隆: ${queueFinal.queue.length} 个`,
    `已克隆: ${totalCopied} 个`,
  ];
  console.log('\n' + summary.join('\n'));
  await sendWeChatAlert(summary);
}

// CLI
if (require.main === module) {
  main().catch(e => { console.error(e); process.exit(1); });
}

module.exports = { main, discoveryPhase, buildCopyQueue };
