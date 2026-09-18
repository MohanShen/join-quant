/**
 * normalize-daily.js — after the daily fetch, normalize the newly-fetched strategies
 * (TRAIN window), auto-create wiki stubs, refresh concept tables. Best-effort: if the
 * CDP Chrome isn't up it skips cleanly so the daily job still completes.
 *
 * exports normalizeNew(postIds, { usageLimit }) -> { skipped?, reason?, results, lines }
 */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { createStub, regenConceptTables } = require('./kb-stub');

const ROOT = path.join(__dirname, '..');
const STRAT_DIR = path.join(ROOT, 'strategies');
const LEDGER = path.join(ROOT, 'harness/normalize-train.tsv');
const PENDING = path.join(ROOT, 'data/pending-normalize.json');   // fetched but not yet normalized
const { cdpUrl, ensureCdpSync } = require('./exec-config');
const CDP_URL = cdpUrl();

function loadPending() { try { return JSON.parse(fs.readFileSync(PENDING, 'utf8')); } catch { return []; } }
function savePending(list) { fs.mkdirSync(path.dirname(PENDING), { recursive: true }); fs.writeFileSync(PENDING, JSON.stringify([...new Set(list)], null, 2)); }

// In remote mode this also opens the SSH tunnel to the server's Chrome if it isn't up yet.
function cdpAlive() {
  return ensureCdpSync().ok;
}

// postId8 -> latest ledger row (any status)
function ledgerByPid8() {
  const map = {};
  if (!fs.existsSync(LEDGER)) return map;
  for (const line of fs.readFileSync(LEDGER, 'utf8').trim().split('\n').slice(1)) {
    const c = line.split('\t');
    if (c[1]) map[c[1].slice(0, 8)] = c;   // c = [sourceFile,postId,title,status,start,end,days,total,annual,sharpe,maxdd,obj,gate]
  }
  return map;
}

function normalizeNew(postIds, { usageLimit = 55 } = {}) {
  const lines = [];
  // Pending = anything queued for normalization. Today's new fetches are appended to
  // whatever is already pending: entries carried over from a skipped run, AND the backlog
  // that utils/normalize-backfill.js writes in screening-priority order. This file used to
  // refuse the backlog on principle, which left 77 held strategies that nothing would ever
  // measure. Order is preserved end to end (see strategy-normalize.js --files).
  const pending = [...new Set([...loadPending(), ...(postIds || [])])];   // priority order first
  const all = fs.readdirSync(STRAT_DIR).filter(f => f.endsWith('.py'));
  // Accept either a saved filename (what strategy-daily now passes) or a legacy
  // id. Ids are matched on their first 8 chars, which is the suffix saveStrategyFile
  // puts in the name — but ids are re-minted per request, so filenames are preferred.
  // Accept either a saved filename (what strategy-daily now passes) or a legacy id.
  // Filenames are preferred: ids are re-minted per request. Match a filename
  // exactly first, then by suffix — `sourceFile` values recorded before the
  // YYYY-MM-DD_ prefix was introduced lack that prefix and would otherwise miss.
  const pidToFile = ref => {
    const r = String(ref);
    if (r.endsWith('.py')) {
      return all.includes(r) ? r : all.find(f => f === r || f.endsWith('_' + r) || f.endsWith(r));
    }
    return all.find(f => f.includes('-' + r.slice(0, 8) + '.py'));
  };
  const basenames = pending.map(pidToFile).filter(Boolean);
  const todayN = (postIds || []).length;
  if (!basenames.length) { savePending(pending); return { results: [], lines: [`归一化：无待归一化策略（今日抓取 ${todayN}）`] }; }

  if (!cdpAlive()) {
    savePending(pending);   // keep them queued for next run
    return { skipped: true, reason: 'CDP Chrome not reachable', lines: [`⚠ 归一化跳过：CDP Chrome (${CDP_URL}) 未运行，${basenames.length} 个待归一化（含今日 ${todayN}）留待下次`] };
  }

  // run the normalizer scoped to just these files
  try {
    execFileSync('node', [path.join(__dirname, 'strategy-normalize.js'),
      '--window', 'train', '--files', basenames.join(','), '--usage-limit', String(usageLimit)],
      { stdio: 'inherit', timeout: 60 * 60 * 1000 });
  } catch (e) { lines.push(`⚠ 归一化执行中断（${(e.message || '').slice(0, 40)}）`); }

  // read results (fresh, after the normalizer ran), build stubs
  const ledAfter = ledgerByPid8();
  const pid8ToFull = {}; for (const pid of pending) pid8ToFull[pid.slice(0, 8)] = pid;
  const results = [];
  for (const f of basenames) {
    const src = fs.readFileSync(path.join(STRAT_DIR, f), 'utf8');
    const pid8 = (src.match(/^#\s*postId:\s*(\S+)/m) || [])[1]?.slice(0, 8) || (f.match(/-([a-f0-9]{8})\.py$/) || [])[1];
    const pid = pid8ToFull[pid8] || pid8;
    const row = ledAfter[pid8];
    if (!row || row[3] !== 'normalized') { results.push({ file: f, pid, status: row ? row[3] : 'not-run' }); continue; }
    const metrics = { annual: parseFloat(row[8]), sharpe: row[9], maxdd: parseFloat(row[10]), obj: row[11], gate: row[12] };
    const stub = createStub('strategies/' + f, src, metrics);
    results.push({ file: f, pid, title: row[2], status: 'normalized', sharpe: metrics.sharpe, gate: metrics.gate, stub: stub.existed ? 'existing-page' : 'stub-created', concepts: stub.concepts });
  }

  const nStub = results.filter(r => r.stub === 'stub-created').length;
  if (nStub) regenConceptTables();

  // Prune pending: drop terminal (normalized + terminal-fails); keep retriable for next run.
  // Mirrors strategy-normalize.js's TERMINAL set — `no-trades` included, or those
  // entries are never pruned from pending-normalize.json and re-run every day.
  const TERMINAL = new Set(['normalized', 'failed-final', 'incompatible-futures', 'incompatible-notrunnable', 'slow-skipped', 'compile-error', 'no-trades']);
  const resByPid = {}; for (const r of results) resByPid[r.pid] = r;
  savePending(pending.filter(pid => { const r = resByPid[pid]; return !(r && TERMINAL.has(r.status)); }));

  const norm = results.filter(r => r.status === 'normalized');
  const pass = norm.filter(r => r.gate === 'pass');
  lines.push(`归一化：${norm.length}/${basenames.length} 完成，${pass.length} 过门槛(夏普≥2.5)，${nStub} 桩页新建`);
  for (const r of pass) lines.push(`  ✅ ${r.title}（夏普 ${r.sharpe}）→ [${(r.concepts || []).join('/')}]`);
  const notNorm = results.filter(r => r.status !== 'normalized');
  if (notNorm.length) lines.push(`  ⚠ ${notNorm.length} 个未完成：${notNorm.map(r => r.status).join(',')}`);

  return { results, lines };
}

module.exports = { normalizeNew };
