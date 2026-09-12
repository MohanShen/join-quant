/**
 * strategy-discover.js
 *
 * Discovers strategies AND research resources from the JoinQuant community
 * via the listV2 API.
 *
 * Transport
 *   Every call goes through utils/jq-http.js, which routes via the logged-in
 *   CDP Chrome. Direct HTTP from outside mainland China is geo-blocked with an
 *   HTTP 200 HTML page, which older versions of this file silently parsed as
 *   "no results" — see jq-http.js for the full story.
 *
 * Pagination
 *   listV2 honours `page`. The archive is deep: page=800 at limit=50 still
 *   returns a full page, reaching back to 2019. Earlier versions of this file
 *   only ever requested page=1, capping discovery at ~400 posts. `--pages N`
 *   now walks N pages per (cate,type) combination and stops early on the first
 *   page that yields nothing new.
 *
 * Two output streams
 *   STRATEGIES — posts carrying a 32-char backtestId. Queue: copy-queue.json.
 *   RESOURCES  — posts carrying a research notebook (`notebookPath`), a file
 *                attachment (`fileKey`), or a research tag (研报分享 / 研报复现
 *                / 研究). Queue: resource-queue.json. These used to be thrown
 *                away: the old filter required a backtestId and explicitly
 *                dropped 研报分享. In a 401-post sample, 22 carried notebooks
 *                and 29 carried file attachments.
 *   A post can be both; it is then recorded in both stores.
 *
 * Usage:
 *   node utils/strategy-discover.js                  # default sweep (2 combos x 3 pages)
 *   node utils/strategy-discover.js 4                # legacy: N combos, 1 page each
 *   node utils/strategy-discover.js --pages 20       # 20 pages per combo (deep crawl)
 *   node utils/strategy-discover.js --pages 50 --limit 50 --cates 3,0
 *   node utils/strategy-discover.js status
 *
 * Data files (all gitignored):
 *   data/discovered.json     - every strategy post ever seen (keyed by postId)
 *   data/copy-queue.json     - strategies to clone, ranked by composite score
 *   data/resources.json      - every resource post ever seen (keyed by postId)
 *   data/resource-queue.json - resources to ingest, ranked by composite score
 */

const fs = require('fs');
const path = require('path');
const jq = require('./jq-http');

const DATA_DIR = path.join(__dirname, '..', 'data');
const DISCOVERED_FILE = path.join(DATA_DIR, 'discovered.json');
const COPY_QUEUE_FILE = path.join(DATA_DIR, 'copy-queue.json');
const RESOURCES_FILE = path.join(DATA_DIR, 'resources.json');
const RESOURCE_QUEUE_FILE = path.join(DATA_DIR, 'resource-queue.json');

/** Tags that mark a post as research material worth keeping on its own. */
const RESEARCH_TAGS = ['研报分享', '研报复现', '研究'];

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function readJson(file, dflt) {
  if (!fs.existsSync(file)) return dflt;
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return dflt; }
}

function loadStore() {
  ensureDataDir();
  return readJson(DISCOVERED_FILE, { lastScraped: null, strategies: {}, scrapedPostIds: [] });
}

function saveStore(store) {
  ensureDataDir();
  fs.writeFileSync(DISCOVERED_FILE, JSON.stringify(store, null, 2));
}

function loadQueue() {
  return readJson(COPY_QUEUE_FILE, { lastUpdated: null, queue: [], copied: {} });
}

function saveQueueData(queueData) {
  ensureDataDir();
  fs.writeFileSync(COPY_QUEUE_FILE, JSON.stringify(queueData, null, 2));
}

function loadResources() {
  ensureDataDir();
  return readJson(RESOURCES_FILE, { lastScraped: null, resources: {} });
}

function saveResources(store) {
  ensureDataDir();
  fs.writeFileSync(RESOURCES_FILE, JSON.stringify(store, null, 2));
}

function loadResourceQueue() {
  return readJson(RESOURCE_QUEUE_FILE, { lastUpdated: null, queue: [], ingested: {} });
}

function saveResourceQueue(q) {
  ensureDataDir();
  fs.writeFileSync(RESOURCE_QUEUE_FILE, JSON.stringify(q, null, 2));
}

// ── Classification ───────────────────────────────────────────────────────────

/** Junk that is neither a usable strategy nor a research resource. */
function isJunk(tags) {
  return tags.includes('文章') && tags.includes('函数');
}

/** A clonable strategy post: has a real backtest attached. */
function isStrategyPost(item, tags) {
  if (!item.backtestId || item.backtestId.length !== 32) return false;
  return !isJunk(tags);
}

/**
 * A research resource: a shared Jupyter notebook, a file attachment, or a post
 * tagged as research-report sharing/replication. Independent of backtestId.
 */
function isResourcePost(item, tags) {
  if (isJunk(tags)) return false;
  if (item.notebookPath) return true;
  if (item.fileKey) return true;
  return tags.some(t => RESEARCH_TAGS.includes(t));
}

/** What kind of resource this is, for the queue row. */
function resourceKind(item, tags) {
  const kinds = [];
  if (item.notebookPath) kinds.push('notebook');
  if (item.fileKey) kinds.push('file');
  if (tags.includes('研报分享')) kinds.push('research-report');
  if (tags.includes('研报复现')) kinds.push('research-replication');
  if (!kinds.length && tags.includes('研究')) kinds.push('research-note');
  return kinds.join('+');
}

function commonFields(item, tags) {
  return {
    postId: item.postId,
    title: item.title,
    url: `https://www.joinquant.com/view/community/detail/${item.postId}`,
    likes: parseInt(item.likeCount) || 0,
    clones: parseInt(item.backtestCloneCount) || 0,
    tags,
    replyCount: parseInt(item.replyCount) || 0,
    viewCount: parseInt(item.viewCount) || 0,
    collectionCount: parseInt(item.collectionCount) || 0,
    author: item.user ? item.user.name : null,
    postedAt: item.addTime || null,
    discoveredAt: new Date().toISOString(),
  };
}

function toStrategy(item, tags) {
  return { ...commonFields(item, tags), backtestId: item.backtestId, annualReturn: null };
}

function toResource(item, tags) {
  return {
    ...commonFields(item, tags),
    kind: resourceKind(item, tags),
    backtestId: item.backtestId && item.backtestId.length === 32 ? item.backtestId : null,
    notebookPath: item.notebookPath || null,
    notebookClones: parseInt(item.notebookCloneCount) || 0,
    fileKey: item.fileKey || null,
    fileName: item.fileName || null,
    fileType: item.fileType || null,
    fileDownloads: parseInt(item.fileDownloadCount) || 0,
  };
}

// ── Fetch ────────────────────────────────────────────────────────────────────

/**
 * Fetch one page of listV2 and split it into strategies and resources.
 *
 * @param {{cate?:number, type?:string, limit?:number, page?:number}} opts
 * @returns {Promise<{strategies:object[], resources:object[], raw:number}>}
 */
async function fetchListPage({ cate = 3, type = 'isNew', limit = 200, page = 1 } = {}) {
  const url = `https://www.joinquant.com/community/post/listV2?limit=${limit}&page=${page}&cate=${cate}&type=${type}`;
  const json = await jq.jqJson(url);
  const list = json && json.data && json.data.list;
  if (!Array.isArray(list)) return { strategies: [], resources: [], raw: 0 };

  const strategies = [];
  const resources = [];
  for (const item of list) {
    const tags = (item.tagInfo || []).map(t => t.name);
    if (isStrategyPost(item, tags)) strategies.push(toStrategy(item, tags));
    if (isResourcePost(item, tags)) resources.push(toResource(item, tags));
  }
  return { strategies, resources, raw: list.length };
}

/**
 * Crawl the community list.
 *
 * Legacy form `scrapeCommunityList(2)` still works: N combos, one page each.
 * New form takes an options object and walks `pages` pages per combo, stopping
 * a combo early once a page adds nothing new (the archive is finite).
 *
 * @param {number|{pages?:number, limit?:number, cates?:number[], types?:string[]}} arg
 */
async function scrapeCommunityList(arg = 2) {
  const legacyCalls = typeof arg === 'number' ? arg : null;
  const opts = typeof arg === 'object' && arg ? arg : {};
  const pages = legacyCalls != null ? 1 : (opts.pages || 3);
  const limit = opts.limit || 200;
  const cates = opts.cates || [3];
  const types = opts.types || ['isNew', 'isHot'];

  const store = loadStore();
  const resStore = loadResources();
  if (!store.scrapedPostIds) store.scrapedPostIds = [];
  const seen = new Set(store.scrapedPostIds);

  let combos = [];
  for (const cate of cates) for (const type of types) combos.push({ cate, type });
  if (legacyCalls != null) combos = combos.slice(0, legacyCalls);

  let newStrategies = 0;
  let newResources = 0;

  for (const combo of combos) {
    let comboStrat = 0;
    let comboRes = 0;
    for (let page = 1; page <= pages; page++) {
      let batch;
      try {
        batch = await fetchListPage({ ...combo, limit, page });
      } catch (e) {
        console.error(`[discover] ${combo.type} p${page}: ${e.message.split('\n')[0]}`);
        break;                                  // transport problem: stop this combo
      }
      if (batch.raw === 0) break;               // past the end of the archive

      let addedThisPage = 0;

      for (const s of batch.strategies) {
        if (!seen.has(s.postId)) { seen.add(s.postId); store.scrapedPostIds.push(s.postId); }
        if (store.strategies[s.postId]) continue;
        store.strategies[s.postId] = s;
        newStrategies++; comboStrat++; addedThisPage++;
      }

      for (const r of batch.resources) {
        if (resStore.resources[r.postId]) continue;
        resStore.resources[r.postId] = r;
        newResources++; comboRes++; addedThisPage++;
      }

      if (addedThisPage === 0 && page > 1) break;   // fully-seen page: nothing deeper to gain
      if (page % 10 === 0) { saveStore(store); saveResources(resStore); }
    }
    console.log(`[discover] cate=${combo.cate} ${combo.type}: +${comboStrat} strategies, +${comboRes} resources`);
  }

  store.lastScraped = new Date().toISOString();
  resStore.lastScraped = store.lastScraped;
  saveStore(store);
  saveResources(resStore);

  console.log(
    `[discover] Done via ${jq.transport()}. +${newStrategies} strategies (total ${Object.keys(store.strategies).length}), ` +
    `+${newResources} resources (total ${Object.keys(resStore.resources).length})`
  );
  return store;
}

// ── Enrichment ───────────────────────────────────────────────────────────────

async function enrichOneStrategy(postId, backtestId) {
  try {
    const url = `https://www.joinquant.com/algorithm/backtest/stats?backtestId=${backtestId}&ajax=1`;
    const json = await jq.jqJson(url);
    if (json && json.data) {
      return {
        annualReturn: json.data.annual_algo_return ? parseFloat(json.data.annual_algo_return) : null,
        maxDrawdown: json.data.max_drawdown ? parseFloat(json.data.max_drawdown) : null,
        sharpe: json.data.sharpe ? parseFloat(json.data.sharpe) : null,
        tradingDays: json.data.trading_days || null,
        enrichedAt: new Date().toISOString(),
      };
    }
  } catch { /* a single stats miss is not fatal */ }
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

// ── Queues ───────────────────────────────────────────────────────────────────

/** Composite score: likes plus half a point per clone. */
const scoreOf = s => (s.likes || 0) + (s.clones || 0) * 0.5;

/** Keep the highest-scoring post per unique title. */
function dedupeByTitle(items, score) {
  const best = new Map();
  for (const s of items) {
    const sc = score(s);
    const ex = best.get(s.title);
    if (!ex || sc > ex._score || (sc === ex._score && (s.clones || 0) > (ex.clones || 0))) {
      best.set(s.title, { ...s, _score: sc });
    }
  }
  return [...best.values()].sort((a, b) => b._score - a._score);
}

function buildCopyQueue() {
  const store = loadStore();
  const queueData = loadQueue();
  const copiedPostIds = new Set(Object.keys(queueData.copied || {}));

  const pending = Object.values(store.strategies).filter(s => !copiedPostIds.has(s.postId));
  const deduped = dedupeByTitle(pending, scoreOf);

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
  queueData.lastUpdated = new Date().toISOString();
  saveQueueData(queueData);

  console.log(`[discover] Strategy queue: ${queueData.queue.length} pending, ${copiedPostIds.size} copied`);
  if (dupRemoved > 0) {
    console.log(`[discover] Title dedup: removed ${dupRemoved} duplicate posts (${pending.length} → ${deduped.length})`);
  }
  console.log('[discover] Top 5:');
  queueData.queue.slice(0, 5).forEach(s =>
    console.log(`  #${s.rank} [likes=${s.likes} clones=${s.clones} score=${s.compositeScore}] ${s.title.slice(0, 60)}`)
  );
  return queueData;
}

/**
 * Rank research resources. Score favours what the community actually used:
 * likes, plus notebook clones and file downloads, plus collections.
 */
function buildResourceQueue() {
  const store = loadResources();
  const q = loadResourceQueue();
  const done = new Set(Object.keys(q.ingested || {}));

  const score = r =>
    (r.likes || 0) +
    (r.notebookClones || 0) * 1.0 +
    (r.fileDownloads || 0) * 0.5 +
    (r.collectionCount || 0) * 0.25;

  const pending = Object.values(store.resources).filter(r => !done.has(r.postId));
  const deduped = dedupeByTitle(pending, score);

  q.queue = deduped.map((r, idx) => ({
    rank: idx + 1,
    postId: r.postId,
    kind: r.kind,
    title: r.title,
    url: r.url,
    author: r.author,
    likes: r.likes || 0,
    notebookPath: r.notebookPath,
    notebookClones: r.notebookClones || 0,
    fileName: r.fileName,
    fileType: r.fileType,
    fileDownloads: r.fileDownloads || 0,
    backtestId: r.backtestId,
    tags: r.tags,
    compositeScore: r._score.toFixed(2),
    addedToQueueAt: new Date().toISOString(),
  }));

  q.lastUpdated = new Date().toISOString();
  saveResourceQueue(q);

  const byKind = {};
  q.queue.forEach(r => { byKind[r.kind] = (byKind[r.kind] || 0) + 1; });
  console.log(`[discover] Resource queue: ${q.queue.length} pending, ${done.size} ingested`);
  console.log(`[discover] By kind: ${Object.entries(byKind).map(([k, v]) => `${k}=${v}`).join(' ') || '(none)'}`);
  console.log('[discover] Top 5 resources:');
  q.queue.slice(0, 5).forEach(r =>
    console.log(`  #${r.rank} [${r.kind} score=${r.compositeScore}] ${r.title.slice(0, 58)}`)
  );
  return q;
}

function markCopied(postId, backtestId, result = {}) {
  const queueData = loadQueue();
  if (!queueData.copied) queueData.copied = {};
  queueData.copied[postId] = { backtestId, copiedAt: new Date().toISOString(), ...result };
  queueData.queue = queueData.queue.filter(s => s.postId !== postId);
  saveQueueData(queueData);
  console.log(`[discover] Marked ${postId} copied. Queue: ${queueData.queue.length} remaining`);
}

function markResourceIngested(postId, result = {}) {
  const q = loadResourceQueue();
  if (!q.ingested) q.ingested = {};
  q.ingested[postId] = { ingestedAt: new Date().toISOString(), ...result };
  q.queue = q.queue.filter(r => r.postId !== postId);
  saveResourceQueue(q);
  console.log(`[discover] Marked resource ${postId} ingested. Queue: ${q.queue.length} remaining`);
}

function showStatus() {
  const store = loadStore();
  const queueData = loadQueue();
  const resStore = loadResources();
  const resQueue = loadResourceQueue();
  console.log('=== Discovery Status ===');
  console.log(`Transport:   ${jq.transport()}`);
  console.log(`Strategies:  ${Object.keys(store.strategies).length} discovered, ` +
              `${queueData.queue.length} queued, ${Object.keys(queueData.copied || {}).length} copied`);
  console.log(`Resources:   ${Object.keys(resStore.resources || {}).length} discovered, ` +
              `${resQueue.queue.length} queued, ${Object.keys(resQueue.ingested || {}).length} ingested`);
  console.log(`Last scraped: ${store.lastScraped || 'never'}`);
  if (queueData.queue.length) {
    console.log('Top strategies:');
    queueData.queue.slice(0, 3).forEach(s => console.log(`  #${s.rank} ${s.title} [likes=${s.likes} clones=${s.clones}]`));
  }
  if (resQueue.queue.length) {
    console.log('Top resources:');
    resQueue.queue.slice(0, 3).forEach(r => console.log(`  #${r.rank} [${r.kind}] ${r.title}`));
  }
}

// ── CLI ──────────────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const out = { pages: null, limit: null, cates: null, types: null, legacyCalls: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--pages') out.pages = parseInt(argv[++i], 10);
    else if (a === '--limit') out.limit = parseInt(argv[++i], 10);
    else if (a === '--cates') out.cates = argv[++i].split(',').map(n => parseInt(n, 10));
    else if (a === '--types') out.types = argv[++i].split(',');
    else if (/^\d+$/.test(a)) out.legacyCalls = parseInt(a, 10);
  }
  return out;
}

if (require.main === module) {
  const args = process.argv.slice(2);
  if (args[0] === 'status') {
    showStatus();
  } else {
    const o = parseArgs(args);
    (async () => {
      const useLegacy = o.legacyCalls != null && o.pages == null;
      const spec = useLegacy
        ? o.legacyCalls
        : {
            pages: o.pages || 3,
            limit: o.limit || 200,
            cates: o.cates || [3],
            types: o.types || ['isNew', 'isHot'],
          };
      const label = useLegacy
        ? `${o.legacyCalls} legacy calls`
        : `${spec.cates.length * spec.types.length} combos x ${spec.pages} pages @ limit ${spec.limit}`;
      console.log(`=== Discovery (${label}) ===`);
      await scrapeCommunityList(spec);
      buildCopyQueue();
      buildResourceQueue();
    })()
      .catch(e => { console.error(e.message || e); process.exitCode = 1; })
      .finally(() => jq.close());
  }
}

module.exports = {
  scrapeCommunityList,
  fetchListPage,
  enrichOneStrategy,
  enrichStrategies,
  buildCopyQueue,
  buildResourceQueue,
  markCopied,
  markResourceIngested,
  showStatus,
  loadStore,
  loadQueue,
  loadResources,
  loadResourceQueue,
  isStrategyPost,
  isResourcePost,
  resourceKind,
};
