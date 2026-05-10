/**
 * strategy-copy.js
 *
 * Iterates through the copy-queue and clones each strategy.
 * For each strategy:
 *   1. Visit post detail page in browser
 *   2. Click "克隆策略" button → creates new backtest
 *   3. Fetch source code via API
 *   4. Fetch performance stats via API
 *   5. Save strategy file to strategies/
 *   6. Send WeChat summary message
 *   7. Mark as copied in copy-queue.json
 *
 * Stops when hitting VIP strategy access limit.
 *
 * Usage:
 *   node utils/strategy-copy.js          # process entire queue
 *   node utils/strategy-copy.js 3       # process up to N strategies
 *   node utils/strategy-copy.js --dry    # show next N strategies without copying
 */

const { chromium } = require('playwright');
const https = require('node:https');
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const STRATEGIES_DIR = path.join(__dirname, '..', 'strategies');
const DISCOVERED_FILE = path.join(DATA_DIR, 'discovered.json');
const COPY_QUEUE_FILE = path.join(DATA_DIR, 'copy-queue.json');

// Threshold for stopping (VIP max strategies)
const ACCESS_LIMIT_KEYWORDS = ['策略数已达上限', '访问受限', 'maximum strategies', '10001'];

// ── HTTP helper ──────────────────────────────────────────────────────────────

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

function httpPost(url, data) {
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
        'Content-Length': Buffer.byteLength(postData),
      },
    };
    https.request(opts, res => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => resolve(JSON.parse(body)));
    }).on('error', reject).end(postData);
  });
}

// ── Data helpers ─────────────────────────────────────────────────────────────

function loadQueue() {
  if (fs.existsSync(COPY_QUEUE_FILE))
    return JSON.parse(fs.readFileSync(COPY_QUEUE_FILE, 'utf8'));
  return { queue: [], copied: {}, lastUpdated: null };
}

function saveQueue(queueData) {
  fs.writeFileSync(COPY_QUEUE_FILE, JSON.stringify(queueData, null, 2));
}

function markCopied(postId, newBacktestId, result = {}) {
  const queueData = loadQueue();
  if (!queueData.copied) queueData.copied = {};
  queueData.copied[postId] = {
    backtestId: newBacktestId,
    copiedAt: new Date().toISOString(),
    ...result,
  };
  queueData.queue = queueData.queue.filter(s => s.postId !== postId);
  saveQueue(queueData);
}

function isAccessLimitError(json) {
  if (!json) return false;
  // Common access limit patterns
  if (json.code === '10001') return true;
  if (json.msg && ACCESS_LIMIT_KEYWORDS.some(k => json.msg.includes(k))) return true;
  if (json.code === '20000' && json.msg && json.msg.includes('系统繁忙')) return false; // temporary
  return false;
}

// ── Strategy file I/O ───────────────────────────────────────────────────────

function saveStrategyFile(postId, backtestId, title, sourceCode) {
  if (!fs.existsSync(STRATEGIES_DIR)) fs.mkdirSync(STRATEGIES_DIR, { recursive: true });
  const safeName = title
    .replace(/[^\u4e00-\u9fa5a-zA-Z0-9_\-]/g, '_')
    .replace(/_+/g, '_')
    .slice(0, 60)
    .trim()
    .replace(/^_+|_+$/g, '') || postId.slice(0, 8);

  const filename = `${safeName}-${postId.slice(0, 8)}.py`;
  const filepath = path.join(STRATEGIES_DIR, filename);
  const header = `# Clone from JoinQuant\n# postId: ${postId}\n# backtestId: ${backtestId}\n# title: ${title}\n\n`;
  fs.writeFileSync(filepath, header + (sourceCode || ''));
  console.log(`[copy] Saved: ${filename}`);
  return filepath;
}

// ── WeChat notification ─────────────────────────────────────────────────────

async function sendWeChatMessage(text) {
  // Write to notification file picked up by the main session
  const notifyFile = path.join(DATA_DIR, 'notifications.json');
  const notifs = fs.existsSync(notifyFile) ? JSON.parse(fs.readFileSync(notifyFile, 'utf8')) : [];
  notifs.push({ type: 'strategy-clone', text, at: new Date().toISOString() });
  fs.writeFileSync(notifyFile, JSON.stringify(notifs, null, 2));
  console.log(`[copy] Notification queued: ${text.slice(0, 80)}`);
}

// ── Clone one strategy ───────────────────────────────────────────────────────

async function cloneOneStrategy(entry, loginManager) {
  const { postId, backtestId: originalBacktestId, title, likes, clones } = entry;

  console.log(`\n[copy] Cloning: ${title} (postId=${postId})`);

  const { browser, context, page } = await loginManager.getBrowserContext();
  let newBacktestId = null;
  let sourceCode = null;
  let stats = null;
  let clonedFilePath = null;
  let limitHit = false;

  try {
    // 1. Navigate to strategy page
    const strategyUrl = `https://www.joinquant.com/view/community/detail/${postId}`;
    await page.goto(strategyUrl, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    // 2. Switch to the backtest iframe (clone button lives there)
    const frame = page.frames().find(f => f.url().includes('/algorithm/backtest/summary'));
    if (!frame) {
      console.log(`[copy] No backtest iframe found`);
    } else {
      // Wait for clone button inside iframe
      try {
        await frame.waitForSelector('text=克隆策略', { timeout: 8000 });
      } catch (e) {
        console.log(`[copy] Clone button not found in iframe`);
      }

      // 3. Click "克隆策略" inside iframe
      let cloneResult = await frame.evaluate(() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
          if ((el.textContent || '').trim() === '克隆策略') {
            el.click();
            return 'clicked';
          }
        }
        return 'not found';
      });
      console.log(`[copy] Clone button: ${cloneResult}`);

      if (cloneResult !== 'not found') {
        await page.waitForTimeout(6000);
        const match = page.url().match(/backtestId=([a-f0-9]{32})/);
        newBacktestId = match ? match[1] : null;
        console.log(`[copy] New backtestId: ${newBacktestId}`);
      }
    }

    // 4. Fetch source code via API
    if (newBacktestId) {
      try {
        const sourceUrl = `https://www.joinquant.com/algorithm/backtest/source?backtestId=${newBacktestId}`;
        const sourceJson = await httpGet(sourceUrl);
        if (sourceJson.data && sourceJson.data.source) {
          sourceCode = sourceJson.data.source;
        }
      } catch (e) {
        console.warn(`[copy] Source fetch failed: ${e.message}`);
      }

      // 5. Fetch stats via API
      try {
        const statsUrl = `https://www.joinquant.com/algorithm/backtest/stats?backtestId=${newBacktestId}&ajax=1`;
        const statsJson = await httpPost(statsUrl, {});
        if (statsJson.data) {
          stats = {
            annualReturn: statsJson.data.annual_algo_return
              ? parseFloat(statsJson.data.annual_algo_return) : null,
            maxDrawdown: statsJson.data.max_drawdown
              ? parseFloat(statsJson.data.max_drawdown) : null,
            sharpe: statsJson.data.sharpe
              ? parseFloat(statsJson.data.sharpe) : null,
            winRatio: statsJson.data.win_ratio
              ? parseFloat(statsJson.data.win_ratio) : null,
            tradingDays: statsJson.data.trading_days || null,
          };
        }
      } catch (e) {
        console.warn(`[copy] Stats fetch failed: ${e.message}`);
      }

      // 6. Save strategy file
      if (sourceCode) {
        clonedFilePath = saveStrategyFile(postId, newBacktestId, title, sourceCode);
      }

      // 7. Send WeChat message
      const score = (likes || 0) + (clones || 0) * 0.5;
      const statsLine = stats && stats.annualReturn != null
        ? `年化${(stats.annualReturn * 100).toFixed(1)}% | 夏普${stats.sharpe} | 回撤${(stats.maxDrawdown * 100).toFixed(1)}%`
        : '绩效获取失败';
      const wechatMsg =
        `📊 *新策略克隆成功*\n` +
        `📌 ${title}\n` +
        `🔢 点赞${likes} | 克隆${clones} | 社区分${score.toFixed(0)}\n` +
        `📁 ${path.basename(clonedFilePath || '')}\n` +
        `🧮 ${statsLine}`;
      await sendWeChatMessage(wechatMsg);

      // 8. Mark as copied
      markCopied(postId, newBacktestId, { sourceFile: path.basename(clonedFilePath || ''), stats });
    }

  } catch (e) {
    console.error(`[copy] Error cloning ${postId}: ${e.message}`);
    // Check if it's an access limit error
    if (e.message && e.message.includes('10001')) {
      limitHit = true;
    }
  } finally {
    await browser.close();
  }

  return { postId, newBacktestId, limitHit, stats };
}

// ── Main loop ────────────────────────────────────────────────────────────────

async function processQueue(maxToProcess = 0) {
  const queueData = loadQueue();
  const { LoginManager } = require('./login');

  const loginManager = new LoginManager(
    path.join(DATA_DIR, 'cookies.json'),
    {
      username: process.env.JOINQUANT_USERNAME || '15656096430',
      password: process.env.JOINQUANT_PASSWORD,
    }
  );

  await loginManager.ensureLogin();

  const pending = queueData.queue.filter(s => !queueData.copied[s.postId]);
  const total = maxToProcess > 0 ? Math.min(maxToProcess, pending.length) : pending.length;

  console.log(`[copy] Processing up to ${total} strategies (${pending.length} pending total)`);

  let processed = 0;
  let limitHit = false;

  for (const entry of pending) {
    if (maxToProcess > 0 && processed >= maxToProcess) break;
    if (limitHit) {
      console.log('[copy] Stopping: access limit reached');
      break;
    }

    const result = await cloneOneStrategy(entry, loginManager);
    processed++;
    if (result.limitHit) {
      limitHit = true;
      console.log('[copy] Access limit hit, stopping loop');
    }

    // Rate-limit between strategies
    if (!limitHit && processed < total) {
      await new Promise(r => setTimeout(r, 3000));
    }
  }

  console.log(`\n[copy] Done. Processed: ${processed}/${total}`);
  return { processed, limitHit };
}

// ── CLI ─────────────────────────────────────────────────────────────────────

if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.includes('--dry')) {
    const queueData = loadQueue();
    console.log(`=== Next strategies in queue ===`);
    queueData.queue.slice(0, 5).forEach((s, i) => {
      console.log(`  #${i + 1} [likes=${s.likes} clones=${s.clones} score=${s.compositeScore}] ${s.title}`);
    });
  } else {
    const max = parseInt(args[0] || '0'); // 0 = unlimited
    (async () => {
      console.log(`=== Strategy Copy (max=${max || 'unlimited'}) ===`);
      const { processed, limitHit } = await processQueue(max);
      console.log(`Processed: ${processed}, Limit hit: ${limitHit}`);
    })().catch(e => { console.error(e); process.exit(1); });
  }
}

module.exports = { processQueue, cloneOneStrategy, markCopied, loadQueue };
