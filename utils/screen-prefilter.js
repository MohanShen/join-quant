/**
 * screen-prefilter.js — the deterministic half of screening (`screen/screen.md` §2).
 *
 * Applies hard rejects R1–R5 to everything discovery has found, then fetches the post body
 * for each survivor so a screener judges substance rather than a title. Nothing here uses
 * judgement: a post dropped at this stage never costs a token, and a post that survives
 * arrives with everything the rubric needs.
 *
 * The point is budget. The forum holds 60,000+ posts and the scarce resources downstream are
 * 60 backtest-minutes/day and analyst attention. Code should throw away everything whose
 * answer is already known — duplicates, already-fetched, API docs — so judgement is spent
 * only where it can actually change a decision.
 *
 * Bodies come from `community/post/detailV2`, which is free and returns the full markdown.
 * Median post is ~460 tokens; title-only screening measured 0.75 AUC against 0.90 with bodies
 * (`screen/calibration/`), so this fetch is what makes the screener worth running.
 *
 * Usage:
 *   node utils/screen-prefilter.js                 # all discovered, un-screened
 *   node utils/screen-prefilter.js --limit 200
 *   node utils/screen-prefilter.js --limit 200 --sample 42   # seeded random slice, not store order
 *   node utils/screen-prefilter.js --cates 14,3               # screen 精华/文章 first; 问答 deferred
 *   node utils/screen-prefilter.js --no-bodies     # metadata only (fast, weaker screening)
 *   node utils/screen-prefilter.js --stats         # rejection breakdown, fetch nothing
 *
 * Output: screen/candidates.json — the screener's input, matching screen/calibration/posts.json.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const jq = require('./jq-http');
const cache = require('./post-cache');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'screen/candidates.json');
const VERDICTS = path.join(ROOT, 'screen/verdicts.json');

const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };

/**
 * A hint, NOT a filter. An earlier version of this file hard-rejected titles with no
 * mechanism token; measured against the corpus it discarded 287 of 549 strategies including
 * 五福 / 三马 / 七星 variants — a held family with 20 members and 4 gate-passes — because this
 * community names mechanisms after family lineages, not after techniques. Per screen.md §2 a
 * hard reject must be something already KNOWN, and "the title looks vague" is a guess. So the
 * match is passed to the screener as `mechanismHint` and it decides.
 */
const MECHANISM = /因子|择时|轮动|止损|止盈|仓位|网格|涨停|打板|套利|对冲|动量|反转|均线|突破|微盘|小市值|多因子|机器学习|深度学习|增量学习|神经|模型|回归|配对|期权|可转债|债|ETF|基金|基本面|财报|研报|龙头|竞价|首板|高开|低开|风控|组合|红利|股息|价值|成长|板块|题材|热点|情绪|资金流|北向|量价|分钟|日内|T0|做T|轮换|再平衡|五福|七星|三马|海龟|缠论|RSRS|KDJ|MACD|布林|均值回归|低频|高频/i;

/**
 * R7: the post IS a 量化课堂 lesson we already ingested into research/tutorials/.
 * Conservative on purpose — exact title match after stripping a leading marker only.
 * Containment would also catch 「『【量化课堂】股指期货对冲策略』之学习笔记」, which is a
 * reader's notes ABOUT the lesson, not the lesson; that is a judgement call, and §2 reserves
 * hard rejects for known facts. Those reach the screener and score M there.
 */
const normTitle = t => String(t || '')
  .replace(/[\s_\-–—【】\[\]()（）:：,，。.、？?！!]/g, '')
  .replace(/^(量化课堂|重磅更新|转载)/, '')
  .toLowerCase();

function heldLessons() {
  const dir = path.join(ROOT, 'research/tutorials');
  const out = new Set();
  if (!fs.existsSync(dir)) return out;
  for (const d of fs.readdirSync(dir)) {
    const p = path.join(dir, d);
    if (!fs.statSync(p).isDirectory()) continue;
    for (const f of fs.readdirSync(p)) if (f.endsWith('.md')) out.add(normTitle(f.slice(0, -3)));
  }
  return out;
}

/** Families already held, with member counts — feeds the screener's M axis. */
function heldFamilies() {
  const dir = path.join(ROOT, 'wiki/families');
  const out = {};
  if (!fs.existsSync(dir)) return out;
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.md'))) {
    const t = fs.readFileSync(path.join(dir, f), 'utf8');
    const n = (t.match(/^memberCount:\s*(\d+)/m) || [])[1];
    out[f.replace(/\.md$/, '')] = parseInt(n || '0', 10);
  }
  return out;
}

/**
 * Apply R1–R5. Returns a reject reason, or null when the post survives.
 * Order matters only for reporting; the rules are disjoint in practice.
 */
function hardReject(row, { hashes, copied, lessons = new Set() }) {
  const tags = row.tags || [];
  const hasBacktest = row.backtestId && row.backtestId.length === 32;
  const isResource = Boolean(row.notebookPath || row.fileKey) ||
                     tags.some(t => ['研报分享', '研报复现', '研究'].includes(t));

  if (!hasBacktest && !isResource) return 'R1 no backtest, no research payload';
  if (tags.includes('文章') && tags.includes('函数')) return 'R4 platform API docs';
  const key = row.uniqueKey || row.key;
  if (key && copied.has(key)) return 'R3 already fetched';
  if (row.contentHash && hashes.has(row.contentHash)) return 'R2 duplicate source';
  if (!String(row.title || '').trim()) return 'R5 empty title';
  if (lessons.has(normTitle(row.title))) return 'R7 already held as a 量化课堂 lesson';
  return null;
}

/** Deterministic shuffle so a bounded batch is a representative sample, not store order. */
function seededShuffle(arr, seed) {
  const a = [...arr];
  let x = seed >>> 0 || 1;
  const rnd = () => ((x = (x * 1103515245 + 12345) >>> 0) / 4294967296);
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

async function run({ limit = 0, bodies = true, statsOnly = false, sampleSeed = null, cates = null } = {}) {
  const disc = readJson(path.join(ROOT, 'data/discovered.json'), { strategies: {} }).strategies || {};
  const res = readJson(path.join(ROOT, 'data/resources.json'), { resources: {} }).resources || {};
  const hashes = new Set(Object.keys(readJson(path.join(ROOT, 'data/content-hashes.json'), {})));
  const copied = new Set(Object.keys(readJson(path.join(ROOT, 'data/copy-queue.json'), {}).copied || {}));
  const seen = new Set(Object.keys((readJson(VERDICTS, {}).verdicts) || {}));
  const lessons = heldLessons();   // verdicts nest under .verdicts

  // One pool: strategies and research resources are screened by the same rubric.
  const pool = new Map();
  for (const [k, v] of Object.entries(disc)) pool.set(k, { ...v, key: k });
  for (const [k, v] of Object.entries(res)) if (!pool.has(k)) pool.set(k, { ...v, key: k });

  const reasons = {};
  const survivors = [];
  for (const row of pool.values()) {
    if (seen.has(row.key)) { reasons['already screened'] = (reasons['already screened'] || 0) + 1; continue; }
    const why = hardReject(row, { hashes, copied, lessons });
    if (why) { reasons[why] = (reasons[why] || 0) + 1; continue; }
    // Selection, not rejection: 问答 (cate=10) screened at 94% drop, so --cates lets a run
    // spend judgement on 文章/精华 first. Q&A is deferred, never discarded (screen.md §2).
    if (cates && !cates.includes(row.cate)) { reasons[`deferred: cate=${row.cate}`] = (reasons[`deferred: cate=${row.cate}`] || 0) + 1; continue; }
    survivors.push(row);
  }

  console.log(`[screen] pool ${pool.size} -> ${survivors.length} survive the hard rejects`);
  for (const [r, n] of Object.entries(reasons).sort((a, b) => b[1] - a[1])) {
    console.log(`  dropped ${String(n).padStart(5)}  ${r}`);
  }
  if (statsOnly) return { survivors: survivors.length, reasons };

  const held = heldFamilies();
  // R6: identical post BODY. R2 only catches duplicate strategy SOURCE, and only after the
  // fetch stage has already spent a request on it. Reposts under a different title are
  // common (one ETF-discount write-up appeared twice in the first full run), and an
  // identical body is a known fact, which is what §2 requires of a hard reject.
  const bodySeen = new Map();
  const normBody = b => String(b || '').replace(/\s+/g, '').slice(0, 1200);
  // Store order is crawl order, which front-loads the old popularity-ranked cate=3 posts.
  // --sample <seed> takes a seeded random slice instead, so a bounded batch is representative.
  const ordered = sampleSeed != null ? seededShuffle(survivors, sampleSeed) : survivors;
  const targets = limit > 0 ? ordered.slice(0, limit) : ordered;
  const out = [];
  let fetched = 0, failed = 0;

  for (const row of targets) {
    let body = '';
    if (bodies) {
      const cached = cache.get(row.key);
      body = await cache.body(row.key, row.postId);
      if (body) fetched++; else failed++;
      // Only pause when we actually hit the network — a cached run costs nothing.
      if (!cached) await new Promise(r => setTimeout(r, 900));
    }
    const nb = normBody(body);
    if (nb.length >= 200) {
      const h = crypto.createHash('sha1').update(nb).digest('hex');
      if (bodySeen.has(h)) {
        reasons['R6 duplicate body'] = (reasons['R6 duplicate body'] || 0) + 1;
        continue;
      }
      bodySeen.set(h, row.key);
    }
    out.push({
      ref: row.key,
      title: row.title,
      tags: row.tags || [],
      likes: row.likes || 0,
      clones: row.clones || 0,
      views: row.viewCount || 0,
      replies: row.replyCount || 0,
      kind: row.kind || (row.backtestId ? 'strategy' : 'resource'),
      cate: row.cate ?? null,
      mechanismHint: MECHANISM.test(row.title || ''),   // hint for the screener, not a filter
      body: body.slice(0, 2500),
    });
    if (out.length % 25 === 0) console.log(`[screen] bodies ${out.length}/${targets.length}`);
  }

  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({
    builtAt: new Date().toISOString(),
    rubric: 'screen/screen.md epoch 1',
    heldFamilies: held,                 // the screener needs these to score axis M
    baseRate: 0.221,                    // from screen/calibration
    posts: out,
  }, null, 1));

  if (bodies) cache.save();
  console.log(`[screen] wrote ${path.relative(ROOT, OUT)}: ${out.length} candidates` +
              (bodies ? ` (bodies: ${cache.report()})` : ' (no bodies)'));
  console.log(`[screen] held families: ${Object.entries(held).sort((a, b) => b[1] - a[1])
    .slice(0, 5).map(([k, v]) => `${k}=${v}`).join(' ')}`);
  return { survivors: survivors.length, written: out.length, reasons };
}

if (require.main === module) {
  const a = process.argv.slice(2);
  const li = a.indexOf('--limit');
  const si = a.indexOf('--sample');
  run({
    limit: li >= 0 ? parseInt(a[li + 1], 10) : 0,
    sampleSeed: si >= 0 ? parseInt(a[si + 1], 10) : null,
    cates: a.indexOf('--cates') >= 0 ? a[a.indexOf('--cates') + 1].split(',').map(Number) : null,
    bodies: !a.includes('--no-bodies'),
    statsOnly: a.includes('--stats'),
  })
    .catch(e => { console.error(e.message || e); process.exitCode = 1; })
    .finally(() => jq.close());
}

module.exports = { run, hardReject, heldFamilies, MECHANISM };
