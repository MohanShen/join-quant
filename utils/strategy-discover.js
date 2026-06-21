/**
 * strategy-discover.js
 *
 * Discovers strategies from JoinQuant community via the listV2 API.
 * Uses limit=200 & cate=3 (精华) per call for efficiency (~100+ strategies/call).
 * Saves all discovered strategies to data/discovered.json (deduped).
 * Builds data/copy-queue.json sorted by composite score (likes + clones*0.5).
 *
 * Usage:
 *   node utils/strategy-discover.js [calls]   # number of API calls (default 2 = ~100 strategies)
 *   node utils/strategy-discover.js status    # show data file status
 *
 * Data files:
 *   data/discovered.json   - all strategies ever discovered (keyed by postId)
 *   data/copy-queue.json  - sorted by composite score, excludes already-copied
 */

const https = require('node:https');
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const DISCOVERED_FILE = path.join(DATA_DIR, 'discovered.json');
const COPY_QUEUE_FILE = path.join(DATA_DIR, 'copy-queue.json');

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
  return { lastUpdated: null, queue: [], copied: {} };
}

function saveQueueData(queueData) {
  fs.writeFileSync(COPY_QUEUE_FILE, JSON.stringify(queueData, null, 2));
}

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
      annualReturn: null,
      tags: (item.tagInfo || []).map(t => t.name),
      replyCount: parseInt(item.replyCount) || 0,
      viewCount: parseInt(item.viewCount) || 0,
      author: item.user ? item.user.name : null,
      discoveredAt: new Date().toISOString(),
    }));
}

async function scrapeCommunityList(callsToMake = 2) {
  const store = loadStore();
  let newCount = 0;

  const calls = [
    { cate: 3, type: 'isNew', limit: 200 },
    { cate: 3, type: 'isHot', limit: 200 },
  ].slice(0, callsToMake);

  for (const combo of calls) {
    const strategies = await fetchListPage(combo);
    for (const s of strategies) {
      if (store.scrapedPostIds.includes(s.postId)) continue;
      store.scrapedPostIds.push(s.postId);
      store.strategies[s.postId] = s;
      newCount++;
    }
    console.log(`[discover] ${combo.type}: +${strategies.length} strategies`);
  }

  store.lastScraped = new Date().toISOString();
  saveStore(store);
  console.log(`[discover] Done. +${newCount} new. Total: ${Object.keys(store.strategies).length}`);
  return store;
}

async function enrichOneStrategy(postId, backtestId) {
  try {
    const url = `https://www.joinquant.com/algorithm/backtest/stats?backtestId=${backtestId}&ajax=1`;
    const json = await httpGet(url);
    if (json.data) {
      return {
        annualReturn: json.data.annual_algo_return ? parseFloat(json.data.annual_algo_return) : null,
        maxDrawdown: json.data.max_drawdown ? parseFloat(json.data.max_drawdown) : null,
        sharpe: json.data.sharpe ? parseFloat(json.data.sharpe) : null,
        tradingDays: json.data.trading_days || null,
        enrichedAt: new Date().toISOString(),
      };
    }
  } catch (e) { /* ok to fail */ }
  return {};
}

async function enrichStrategies(limit = 20) {
  const store = loadStore();
  let enriched = 0;
  const pending = Object.values(store.strategies).filter(s => s.backtestId && !s.enrichedAt);

  for (const s of pending.slice(0, limit)) {
    const data = await enrichOneStrategy(s.postId, s.backtestId);
    store.strategies[s.postId] = { ...s, ...data };
    enriched++;
    if (enriched % 5 === 0) saveStore(store);
    await new Promise(r => setTimeout(r, 500));
  }

  saveStore(store);
  console.log(`[discover] Enriched ${enriched} strategies`);
  return enriched;
}

function buildCopyQueue() {
  const store = loadStore();
  const queueData = loadQueue();
  const copiedPostIds = new Set(Object.keys(queueData.copied));

  const pending = Object.values(store.strategies)
    .filter(s => !copiedPostIds.has(s.postId));

  // ── Title-based deduplication ────────────────────────────────────────────
  // Keep the highest-scoring post per unique title.
  // Score = likes + clones * 0.5; tiebreak: higher clones wins.
  const bestByTitle = new Map();
  for (const s of pending) {
    const score = (s.likes || 0) + (s.clones || 0) * 0.5;
    const existing = bestByTitle.get(s.title);
    if (!existing) {
      bestByTitle.set(s.title, { ...s, _score: score });
    } else {
      const exScore = existing._score;
      if (score > exScore || (score === exScore && (s.clones || 0) > (existing.clones || 0))) {
        bestByTitle.set(s.title, { ...s, _score: score });
      }
    }
  }

  // Convert back to array sorted by score desc
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

  const totalRaw = pending.length;
  const totalDeduped = deduped.length;
  const dupRemoved = totalRaw - totalDeduped;

  queueData.lastUpdated = new Date().toISOString();
  saveQueueData(queueData);

  console.log(`[discover] Queue: ${queueData.queue.length} pending, ${copiedPostIds.size} copied`);
  if (dupRemoved > 0) {
    console.log(`[discover] Title dedup: removed ${dupRemoved} duplicate posts (${totalRaw} → ${totalDeduped})`);
  }
  console.log(`[discover] Top 5:`);
  queueData.queue.slice(0, 5).forEach(s =>
    console.log(`  #${s.rank} [likes=${s.likes} clones=${s.clones} score=${s.compositeScore}] ${s.title.slice(0, 60)}`)
  );
  return queueData;
}

function markCopied(postId, backtestId, result = {}) {
  const queueData = loadQueue();
  if (!queueData.copied) queueData.copied = {};
  queueData.copied[postId] = { backtestId, copiedAt: new Date().toISOString(), ...result };
  queueData.queue = queueData.queue.filter(s => s.postId !== postId);
  saveQueueData(queueData);
  console.log(`[discover] Marked ${postId} copied. Queue: ${queueData.queue.length} remaining`);
}

function showStatus() {
  const store = loadStore();
  const queueData = loadQueue();
  const copied = Object.keys(queueData.copied || {}).length;
  console.log(`=== Discovery Status ===`);
  console.log(`Discovered: ${Object.keys(store.strategies).length} total`);
  console.log(`Queue: ${queueData.queue.length} pending`);
  console.log(`Copied: ${copied}`);
  console.log(`Last scraped: ${store.lastScraped || 'never'}`);
  if (queueData.queue.length > 0) {
    console.log(`Top queue:`);
    queueData.queue.slice(0, 3).forEach(s => console.log(`  #${s.rank} ${s.title} [likes=${s.likes} clones=${s.clones}]`));
  }
}

// CLI
if (require.main === module) {
  const args = process.argv.slice(2);
  if (args[0] === 'status') {
    showStatus();
  } else {
    const calls = parseInt(args[0] || '2');
    (async () => {
      console.log(`=== Discovery (${calls} API calls) ===`);
      await scrapeCommunityList(calls);
      buildCopyQueue();
    })().catch(e => { console.error(e); process.exit(1); });
  }
}

module.exports = {
  scrapeCommunityList,
  enrichOneStrategy,
  enrichStrategies,
  buildCopyQueue,
  markCopied,
  showStatus,
  loadStore,
  loadQueue,
};
