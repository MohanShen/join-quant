/**
 * strategy-fetch.js
 *
 * Read-only pipeline: for each strategy in the copy-queue,
 * fetch source + stats via API (no cloning needed) and save to strategy files.
 *
 * Flow:
 *   1. Load queue from data/copy-queue.json
 *   2. For each uncopied strategy:
 *      - Fetch source via API (GET /algorithm/backtest/source)
 *      - Fetch stats via API (POST /algorithm/backtest/stats)
 *      - DEDUP: skip if source content matches an already-fetched strategy (SHA256)
 *      - Save to strategies/ with metadata header
 *      - Queue WeChat summary
 *   3. Stop when hitting access limit
 *
 * Usage:
 *   node utils/strategy-fetch.js          # process entire queue
 *   node utils/strategy-fetch.js 3        # process up to N strategies
 *   node utils/strategy-fetch.js --dry     # show next N without fetching
 */

const https = require('node:https');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const DATA_DIR = path.join(__dirname, '..', 'data');
const STRATEGIES_DIR = path.join(__dirname, '..', 'strategies');
const DISCOVERED_FILE = path.join(DATA_DIR, 'discovered.json');
const COPY_QUEUE_FILE = path.join(DATA_DIR, 'copy-queue.json');
const COOKIES_FILE = path.join(DATA_DIR, 'cookies.json');
const CONTENT_HASH_FILE = path.join(DATA_DIR, 'content-hashes.json');

const ACCESS_LIMIT_KEYWORDS = ['策略数已达上限', '访问受限', 'maximum strategies', '10001'];

// ── HTTP helpers ─────────────────────────────────────────────────────────────

function httpGet(url, cookies) {
  return new Promise((resolve, reject) => {
    https.get(url, {
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Cookie': cookies,
      },
    }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => { try { resolve(JSON.parse(data)); } catch { resolve({ raw: data.slice(0, 200) }); } });
    }).on('error', reject);
  });
}

function httpPost(url, data, cookies) {
  return new Promise((resolve, reject) => {
    const postData = JSON.stringify(data);
    const urlObj = new URL(url);
    const opts = {
      hostname: urlObj.hostname,
      path: urlObj.pathname + urlObj.search,
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Cookie': cookies,
        'Content-Length': Buffer.byteLength(postData),
      },
    };
    https.request(opts, res => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => { try { resolve(JSON.parse(body)); } catch { resolve({ raw: body.slice(0, 200) }); } });
    }).on('error', reject).end(postData);
  });
}

// ── Load cookies ─────────────────────────────────────────────────────────────

function loadCookies() {
  if (!fs.existsSync(COOKIES_FILE)) return null;
  const auth = JSON.parse(fs.readFileSync(COOKIES_FILE, 'utf8'));
  return auth.cookies || [];
}

function cookiesToString(cookies) {
  return cookies.map(c => `${c.name}=${c.value}`).join('; ');
}

// ── Content-hash dedup registry ──────────────────────────────────────────────

/**
 * SHA256 hex digest of source code content.
 * @param {string} code
 * @returns {string}
 */
function contentHash(code) {
  return crypto.createHash('sha256').update(code || '', 'utf8').digest('hex');
}

function loadHashRegistry() {
  if (!fs.existsSync(CONTENT_HASH_FILE)) return {};
  try {
    return JSON.parse(fs.readFileSync(CONTENT_HASH_FILE, 'utf8'));
  } catch {
    return {};
  }
}

function saveHashRegistry(registry) {
  fs.writeFileSync(CONTENT_HASH_FILE, JSON.stringify(registry, null, 2));
}

/**
 * Find if this exact source content was already saved under a different postId.
 * Returns the original postId if duplicate, null otherwise.
 * @param {string} sourceCode
 * @returns {string|null}
 */
function findDuplicateByContent(sourceCode) {
  if (!sourceCode) return null;
  const hash = contentHash(sourceCode);
  const registry = loadHashRegistry();
  const entry = Object.entries(registry).find(([h]) => h === hash);
  return entry ? entry[1].postId : null;
}

/**
 * Register source content hash after successfully saving a file.
 * @param {string} sourceCode
 * @param {string} postId
 * @param {string} sourceFile
 */
function registerContentHash(sourceCode, postId, sourceFile) {
  if (!sourceCode) return;
  const hash = contentHash(sourceCode);
  const registry = loadHashRegistry();
  registry[hash] = { postId, sourceFile, registeredAt: new Date().toISOString() };
  saveHashRegistry(registry);
}

// ── Queue helpers ────────────────────────────────────────────────────────────

function loadQueue() {
  if (fs.existsSync(COPY_QUEUE_FILE))
    return JSON.parse(fs.readFileSync(COPY_QUEUE_FILE, 'utf8'));
  return { queue: [], copied: {}, lastUpdated: null };
}

function saveQueue(queueData) {
  fs.writeFileSync(COPY_QUEUE_FILE, JSON.stringify(queueData, null, 2));
}

function markFetched(postId, result = {}) {
  const queueData = loadQueue();
  if (!queueData.copied) queueData.copied = {};
  queueData.copied[postId] = {
    fetchedAt: new Date().toISOString(),
    ...result,
  };
  queueData.queue = queueData.queue.filter(s => s.postId !== postId);
  saveQueue(queueData);
}

function isAccessLimitError(json) {
  if (!json) return false;
  if (json.code === '10001') return true;
  if (json.msg && ACCESS_LIMIT_KEYWORDS.some(k => json.msg.includes(k))) return true;
  if (json.code === '20000' && json.msg && json.msg.includes('系统繁忙')) return false;
  return false;
}

// ── Save strategy file ──────────────────────────────────────────────────────

function saveStrategyFile(postId, backtestId, title, sourceCode) {
  if (!fs.existsSync(STRATEGIES_DIR)) fs.mkdirSync(STRATEGIES_DIR, { recursive: true });
  const safeName = title
    .replace(/[^\u4e00-\u9fa5a-zA-Z0-9_\-]/g, '_')
    .replace(/_+/g, '_')
    .slice(0, 60)
    .trim()
    .replace(/^_+|_+$/g, '') || postId.slice(0, 8);

  // Prefix with the fetch date (Asia/Shanghai) so saved files sort
  // chronologically and match the YYYY-MM-DD_ naming convention.
  // 'en-CA' renders as YYYY-MM-DD.
  const datePrefix = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Shanghai' });
  const filename = `${datePrefix}_${safeName}-${postId.slice(0, 8)}.py`;
  const filepath = path.join(STRATEGIES_DIR, filename);
  const header = `# Clone from JoinQuant\n# postId: ${postId}\n# backtestId: ${backtestId}\n# title: ${title}\n\n`;
  fs.writeFileSync(filepath, header + (sourceCode || ''));
  return filepath;
}

// ── Fetch one strategy via API ────────────────────────────────────────────────

async function fetchOneStrategy(entry, cookiesStr) {
  const { postId, backtestId, title, likes, clones } = entry;

  console.log(`[fetch] ${title} (backtestId=${backtestId})`);

  let sourceCode = null;
  let stats = null;
  let limitHit = false;
  let sourceError = null;
  let statsError = null;

  // 1. Fetch source
  try {
    const sourceJson = await httpGet(
      `https://www.joinquant.com/algorithm/backtest/source?backtestId=${backtestId}`,
      cookiesStr
    );
    if (sourceJson.data && sourceJson.data.source) {
      sourceCode = sourceJson.data.source;
    } else if (sourceJson.code === '10001' || sourceJson.code === '20000') {
      sourceError = sourceJson.msg || sourceJson.code;
    }
  } catch (e) {
    sourceError = e.message;
  }

  // 2. Fetch stats
  try {
    const statsJson = await httpPost(
      `https://www.joinquant.com/algorithm/backtest/stats?backtestId=${backtestId}&ajax=1`,
      {},
      cookiesStr
    );
    if (statsJson.data) {
      stats = {
        annualReturn: statsJson.data.annual_algo_return
          ? parseFloat(statsJson.data.annual_algo_return) : null,
        cumulativeReturn: statsJson.data.algorithm_return
          ? parseFloat(statsJson.data.algorithm_return) : null,
        maxDrawdown: statsJson.data.max_drawdown
          ? parseFloat(statsJson.data.max_drawdown) : null,
        sharpe: statsJson.data.sharpe
          ? parseFloat(statsJson.data.sharpe) : null,
        winRatio: statsJson.data.win_ratio
          ? parseFloat(statsJson.data.win_ratio) : null,
        tradingDays: statsJson.data.trading_days || null,
        periodLabel: statsJson.data.period_label || null,
      };
    } else if (isAccessLimitError(statsJson)) {
      statsError = statsJson.msg || 'access limit';
      limitHit = true;
    }
  } catch (e) {
    statsError = e.message;
  }

  return { sourceCode, stats, limitHit, sourceError, statsError };
}

// ── WeChat notification ───────────────────────────────────────────────────────

function queueWeChatMessage(text) {
  const notifyFile = path.join(DATA_DIR, 'notifications.json');
  const notifs = fs.existsSync(notifyFile) ? JSON.parse(fs.readFileSync(notifyFile, 'utf8')) : [];
  notifs.push({ type: 'strategy-fetch', text, at: new Date().toISOString() });
  fs.writeFileSync(notifyFile, JSON.stringify(notifs, null, 2));
}

// ── Main loop ─────────────────────────────────────────────────────────────────

async function processQueue(maxToProcess = 0) {
  const queueData = loadQueue();
  const cookies = loadCookies();
  if (!cookies || cookies.length === 0) {
    console.error('[fetch] No cookies found. Run login first.');
    return { processed: 0, limitHit: false };
  }
  const cookiesStr = cookiesToString(cookies);

  const pending = queueData.queue.filter(s => !queueData.copied[s.postId]);
  const total = maxToProcess > 0 ? Math.min(maxToProcess, pending.length) : pending.length;

  console.log(`[fetch] Processing up to ${total} strategies (${pending.length} pending total)`);

  let processed = 0;
  let limitHit = false;
  let skippedDup = 0;
  const fetchedEntries = []; // collected for manifest

  for (const entry of pending) {
    if (maxToProcess > 0 && processed >= maxToProcess) break;
    if (limitHit) {
      console.log('[fetch] Stopping: access limit reached');
      break;
    }

    const { sourceCode, stats, limitHit: hit, sourceError, statsError } = await fetchOneStrategy(entry, cookiesStr);

    if (hit) {
      limitHit = true;
      console.log('[fetch] Access limit hit, stopping loop');
      break;
    }

    // ── Deduplicate by source content ───────────────────────────────────────
    let isDuplicate = false;
    let duplicateOfPostId = null;

    if (sourceCode) {
      duplicateOfPostId = findDuplicateByContent(sourceCode);
      if (duplicateOfPostId) {
        console.log(`[fetch] DUPLICATE — content matches postId=${duplicateOfPostId.slice(0, 8)}, skipping postId=${entry.postId.slice(0, 8)}`);
        isDuplicate = true;
        markFetched(entry.postId, { duplicateOf: duplicateOfPostId });
        skippedDup++;
      }
    }

    // Save file only if we got source AND it's not a duplicate
    let savedPath = null;
    let fetched = false;
    if (sourceCode && !isDuplicate) {
      savedPath = saveStrategyFile(entry.postId, entry.backtestId, entry.title, sourceCode);
      registerContentHash(sourceCode, entry.postId, path.basename(savedPath));
      fetched = true;
      markFetched(entry.postId, {
        sourceFile: path.basename(savedPath),
        stats,
      });
      fetchedEntries.push({
        postId: entry.postId,
        backtestId: entry.backtestId,
        title: entry.title,
        url: entry.url,
        sourceFile: path.basename(savedPath),
        stats,
      });
    } else if (isDuplicate) {
      // Record in manifest so LLM knows it's a dup
      fetchedEntries.push({
        postId: entry.postId,
        backtestId: entry.backtestId,
        title: entry.title,
        url: entry.url,
        stats: stats || {},
        duplicateOf: duplicateOfPostId,
      });
    }

    if (fetched) {
      const statsLine = stats && stats.annualReturn != null
        ? `年化${(stats.annualReturn * 100).toFixed(1)}% | 夏普${stats.sharpe?.toFixed(2)} | 回撤${(stats.maxDrawdown * 100).toFixed(1)}%`
        : '绩效未公开';
      const notifText = `📊 *策略发现*\n📌 ${entry.title}\n🔢 ${statsLine}\n📁 ${entry.sourceFile}`;
      queueWeChatMessage(notifText);
      console.log(`FETCHED|${entry.title}|${statsLine}`);
    } else if (isDuplicate) {
      console.log(`DUPLICATE|${entry.title}|same content as postId=${duplicateOfPostId.slice(0, 8)}`);
    } else {
      console.log(`FETCH_FAILED|${entry.title}|${sourceError || 'unknown'}`);
    }

    processed++;

    // Rate limit
    if (!limitHit && processed < total) {
      await new Promise(r => setTimeout(r, 2000));
    }
  }

  // Write manifest for LLM to read
  if (fetchedEntries.length > 0) {
    const { writeManifest } = require('./strategy-manifest');
    writeManifest(fetchedEntries);
  }

  console.log(`\n[fetch] Done. Processed: ${processed}/${total}, duplicates skipped: ${skippedDup}`);
  return { processed, limitHit, skippedDup };
}

// ── CLI ─────────────────────────────────────────────────────────────────────

function parseArgs(args) {
  const result = { max: 0, dry: false };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--dry') result.dry = true;
    if (args[i] === '--limit' && args[i + 1] != null) {
      result.max = parseInt(args[i + 1]) || 3;
      i++;
    } else if (/^\d+$/.test(args[i])) {
      result.max = parseInt(args[i]) || 3;
    }
  }
  return result;
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const { max, dry } = parseArgs(args);

  if (dry) {
    const queueData = loadQueue();
    const pending = queueData.queue.filter(s => !queueData.copied[s.postId]);
    console.log(`=== Next ${Math.min(5, pending.length)} strategies in queue ===`);
    pending.slice(0, 5).forEach((s, i) => {
      console.log(`  #${i + 1} [likes=${s.likes} clones=${s.clones} score=${s.compositeScore}] ${s.title}`);
    });
  } else {
    (async () => {
      console.log(`=== Strategy Fetch (limit=${max || 3}) ===`);
      const { processed, limitHit, skippedDup } = await processQueue(max || 3);
      console.log(`Processed: ${processed}, Limit hit: ${limitHit}, Dup skipped: ${skippedDup}`);
    })().catch(e => { console.error(e); process.exit(1); });
  }
}

module.exports = { processQueue, fetchOneStrategy, loadQueue, markFetched };