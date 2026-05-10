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

const https = require('node:https');
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const COPY_QUEUE_FILE = path.join(DATA_DIR, 'copy-queue.json');
const DISCOVERED_FILE = path.join(DATA_DIR, 'discovered.json');

function httpGet(url) {
  return new Promise((resolve, reject) => {
    https.get(url, {
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      },
    }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve(JSON.parse(data)));
    }).on('error', reject);
  });
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

  pending.sort((a, b) => {
    const scoreA = (a.likes || 0) + (a.clones || 0) * 0.5;
    const scoreB = (b.likes || 0) + (b.clones || 0) * 0.5;
    return scoreB - scoreA;
  });

  queueData.queue = pending.map((s, idx) => ({
    rank: idx + 1,
    postId: s.postId,
    backtestId: s.backtestId,
    title: s.title,
    url: s.url,
    likes: s.likes || 0,
    clones: s.clones || 0,
    annualReturn: s.annualReturn,
    compositeScore: (((s.likes || 0) + (s.clones || 0) * 0.5)).toFixed(2),
    addedToQueueAt: new Date().toISOString(),
  }));

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

  console.log(`\n=== join-quant Daily Pipeline | ${today} ===`);

  let newCount = 0;
  if (mode !== '--copy-only') {
    newCount = await discoveryPhase();
  }

  const queueData = buildCopyQueue();
  console.log(`[daily] Queue: ${queueData.queue.length} pending, ${Object.keys(queueData.copied || {}).length} copied`);

  if (mode === '--discover-only') {
    console.log('[daily] Discovery-only mode, skipping copy phase');
    await sendWeChatAlert([
      `📡 每日策略发现完成 | ${today}`,
      `新增: ${newCount} 个策略`,
      `待克隆: ${queueData.queue.length} 个`,
      `已克隆: ${Object.keys(queueData.copied || {}).length} 个`,
    ]);
    return;
  }

  // Fetch phase — read source + stats via API, save to strategies/
  const { processQueue } = require('./strategy-fetch');
  const { processed, limitHit } = await processQueue(0); // 0 = unlimited

  // Final WeChat summary
  const queueFinal = loadQueue();
  const copied = Object.keys(queueFinal.copied || {}).length;
  await sendWeChatAlert([
    `✅ 每日策略流水线完成 | ${today}`,
    `本轮克隆: ${processed} 个`,
    `累计已克隆: ${copied} 个`,
    `队列剩余: ${queueFinal.queue.length} 个`,
    `访问限制: ${limitHit ? '是' : '否'}`,
  ]);
}

// CLI
if (require.main === module) {
  main().catch(e => { console.error(e); process.exit(1); });
}

module.exports = { main, discoveryPhase, buildCopyQueue };
