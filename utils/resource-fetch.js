/**
 * resource-fetch.js — download the community RESEARCH posts that the strategy
 * pipeline throws away.
 *
 * Where the content comes from
 * ----------------------------
 *   GET /community/post/detailV2?postId=<id>
 *
 * This returns the post's **complete markdown body** plus its notebook and
 * attachment metadata, and it costs nothing. For a research post the body is the
 * artefact: the write-up, the factor definitions, the reasoning. The strategy
 * pipeline never calls it because it only wants `backtest/source`.
 *
 * What we cannot get, and why
 * ---------------------------
 * The shared Jupyter notebook itself is NOT downloadable. The post page offers
 * 克隆研究 (clone research), which copies the notebook into your own research
 * environment and spends 积分 (credits) unless the account holds VIP. The
 * `notebookReport` path stored on older posts 302s to a 404. So this tool
 * records notebook availability — path, clone count, whether a clone is the only
 * route — and saves the free prose around it. Cloning stays a human decision
 * because it spends real credits.
 *
 * Identity: entries are keyed by the queue row's stable `key` (uniqueKey), never
 * `postId` — JoinQuant re-mints postIds on every request.
 *
 * Output
 *   resources/<YYYY-MM-DD>_<title>-<key8>.md   raw layer, mirrors strategies/
 *   data/resource-hashes.json                  SHA256 dedup registry
 *
 * Usage:
 *   node utils/resource-fetch.js            # whole queue
 *   node utils/resource-fetch.js 10         # up to N
 *   node utils/resource-fetch.js --dry      # show what is next
 *   node utils/resource-fetch.js --kind notebook
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const jq = require('./jq-http');
const cache = require('./post-cache');
const { loadResourceQueue, markResourceIngested } = require('./strategy-discover');

const REPO = path.join(__dirname, '..');
const OUT_DIR = path.join(REPO, 'resources');
const DATA_DIR = path.join(REPO, 'data');
const HASH_FILE = path.join(DATA_DIR, 'resource-hashes.json');

const readJson = (f, d) => {
  if (!fs.existsSync(f)) return d;
  try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; }
};

const contentHash = text => crypto.createHash('sha256').update(text || '', 'utf8').digest('hex');

function safeName(title, key) {
  return (title || '')
    .replace(/[^一-龥a-zA-Z0-9_\-]/g, '_')
    .replace(/_+/g, '_')
    .slice(0, 60)
    .replace(/^_+|_+$/g, '') || key.slice(0, 8);
}

/** Fetch one post's full body + metadata. */
async function fetchDetail(postId) {
  const json = await jq.jqJson(`https://www.joinquant.com/community/post/detailV2?postId=${postId}`);
  if (!json || json.code !== '00000' || !json.data) {
    throw new Error(`detailV2 refused postId=${postId}: ${(json && json.msg) || 'no data'}`);
  }
  return json.data;
}

/**
 * Render one resource as a markdown file with a provenance header.
 * The header records that the notebook, if any, still needs a credit-spending
 * clone — so a later reader never mistakes the prose for the full artefact.
 */
function renderMarkdown(entry, detail) {
  const nb = detail.notebookPath || entry.notebookPath;
  const lines = [
    '---',
    `title: ${JSON.stringify(detail.title || entry.title)}`,
    `uniqueKey: ${detail.uniqueKey || entry.uniqueKey || ''}`,
    `key: ${entry.key}`,
    `kind: ${entry.kind}`,
    `author: ${JSON.stringify(entry.author || '')}`,
    `postedAt: ${detail.addTime || entry.postedAt || ''}`,
    `likes: ${detail.likeCount || entry.likes || 0}`,
    `views: ${detail.viewCount || entry.viewCount || 0}`,
    `collections: ${detail.collectionCount || entry.collectionCount || 0}`,
    `tags: [${(entry.tags || []).join(', ')}]`,
    `sourceUrl: https://www.joinquant.com/view/community/detail/${detail.postId || entry.postId}`,
    `fetchedAt: ${new Date().toISOString()}`,
  ];
  if (nb) {
    lines.push(`notebookPath: ${JSON.stringify(nb)}`);
    lines.push(`notebookClones: ${detail.notebookCloneCount || entry.notebookClones || 0}`);
    lines.push('notebookAvailable: false   # requires 克隆研究, which spends 积分 (credits)');
  }
  if (entry.fileName) {
    lines.push(`fileName: ${JSON.stringify(entry.fileName)}`);
    lines.push(`fileType: ${JSON.stringify(entry.fileType || '')}`);
    lines.push(`fileDownloads: ${entry.fileDownloads || 0}`);
  }
  if (detail.backtestId) lines.push(`backtestId: ${detail.backtestId}   # ephemeral, re-minted per request`);
  lines.push('---', '');
  lines.push(`# ${detail.title || entry.title}`, '');
  if (nb) {
    lines.push(`> 📓 **附带研究 notebook**：\`${nb}\`（${detail.notebookCloneCount || 0} 次克隆）。`);
    lines.push('> notebook 本体**无法直接下载**，只能在帖子页「克隆研究」复制到自己的研究环境，**消耗积分**。');
    lines.push('> 以下为帖子正文（免费），不含 notebook 代码。', '');
  }
  lines.push(String(detail.content || '').trim(), '');
  return lines.join('\n');
}

async function fetchOne(entry, registry) {
  // Served from data/post-bodies.json when the screener already fetched this post,
  // which is the common case — screening runs before ingestion.
  const detail = await cache.detail(entry.key, entry.postId);
  if (!detail) throw new Error(`detailV2 unavailable for ${entry.key}`);
  const body = String(detail.content || '');
  if (!body.trim()) return { status: 'empty' };

  const hash = contentHash(body);
  if (registry[hash]) {
    return { status: 'duplicate', duplicateOf: registry[hash].file };
  }

  const file = `${new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Shanghai' })}_` +
               `${safeName(detail.title || entry.title, entry.key)}-${entry.key.slice(0, 8)}.md`;
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(path.join(OUT_DIR, file), renderMarkdown(entry, detail));

  registry[hash] = { key: entry.key, file, registeredAt: new Date().toISOString() };
  return {
    status: 'saved',
    file,
    bytes: body.length,
    hasNotebook: Boolean(detail.notebookPath || entry.notebookPath),
    hasFile: Boolean(entry.fileName),
  };
}

async function processQueue({ max = 0, kind = null } = {}) {
  const q = loadResourceQueue();
  const registry = readJson(HASH_FILE, {});
  let pending = q.queue.filter(r => !(q.ingested || {})[r.key || r.postId]);
  if (kind) pending = pending.filter(r => (r.kind || '').includes(kind));

  const total = max > 0 ? Math.min(max, pending.length) : pending.length;
  console.log(`[resource] Processing up to ${total} resources (${pending.length} pending${kind ? `, kind~${kind}` : ''})`);

  const counts = { saved: 0, duplicate: 0, empty: 0, failed: 0, notebooks: 0, files: 0 };

  for (const entry of pending.slice(0, total)) {
    const key = entry.key || entry.postId;
    try {
      const r = await fetchOne(entry, registry);
      counts[r.status] = (counts[r.status] || 0) + 1;
      if (r.status === 'saved') {
        if (r.hasNotebook) counts.notebooks++;
        if (r.hasFile) counts.files++;
        console.log(`[resource] ✓ ${entry.kind.padEnd(16)} ${String(r.bytes).padStart(6)}B  ${r.file}`);
        markResourceIngested(key, { file: r.file, kind: entry.kind, bytes: r.bytes });
      } else if (r.status === 'duplicate') {
        console.log(`[resource] = DUPLICATE of ${r.duplicateOf} — ${entry.title.slice(0, 40)}`);
        markResourceIngested(key, { duplicateOf: r.duplicateOf });
      } else {
        console.log(`[resource] ∅ empty body — ${entry.title.slice(0, 40)}`);
        markResourceIngested(key, { empty: true });
      }
    } catch (e) {
      counts.failed++;
      console.error(`[resource] ✗ ${entry.title.slice(0, 40)} :: ${e.message.split('\n')[0].slice(0, 90)}`);
    }
    fs.writeFileSync(HASH_FILE, JSON.stringify(registry, null, 2));
    cache.save();
    await new Promise(r => setTimeout(r, 1200));
  }

  console.log(`\n[resource] Done. saved=${counts.saved} duplicate=${counts.duplicate} ` +
              `empty=${counts.empty} failed=${counts.failed} ` +
              `(of saved: ${counts.notebooks} carry a notebook, ${counts.files} an attachment)`);
  return counts;
}

// ── CLI ──────────────────────────────────────────────────────────────────────

if (require.main === module) {
  const args = process.argv.slice(2);
  const dry = args.includes('--dry');
  const kindIdx = args.indexOf('--kind');
  const kind = kindIdx >= 0 ? args[kindIdx + 1] : null;
  const max = parseInt(args.find(a => /^\d+$/.test(a)) || '0', 10);

  if (dry) {
    const q = loadResourceQueue();
    const pending = q.queue.filter(r => !(q.ingested || {})[r.key || r.postId]);
    console.log(`=== Next ${Math.min(8, pending.length)} of ${pending.length} pending resources ===`);
    pending.slice(0, 8).forEach(r =>
      console.log(`  #${r.rank} [${r.kind} score=${r.compositeScore}] ${r.title.slice(0, 56)}`));
  } else {
    processQueue({ max, kind })
      .catch(e => { console.error(e.message || e); process.exitCode = 1; })
      .finally(() => jq.close());
  }
}

module.exports = { processQueue, fetchOne, fetchDetail, renderMarkdown };
