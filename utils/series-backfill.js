/**
 * series-backfill.js — recover daily equity curves for strategies ALREADY measured, at zero
 * backtest cost.
 *
 * `utils/backtest-series.js` captures a curve at the moment a run finishes, which only helps
 * from now on. But JoinQuant retains every backtest this account has ever run (238+ algorithms
 * at the time of writing), and each one still serves its curve. So the whole existing ledger
 * can be given series without spending a single one of the 60 daily backtest minutes — the
 * same trick `normalize-ledger-rebuild.js` uses to reconstruct the ledger from the wiki.
 *
 * ⚠ The matching problem. Runs are created through `/algorithm/index/new`, which does NOT set
 * a name, and every JQ id is re-minted per request (CLAUDE.md), so there is no stored link
 * from a retained backtest back to the `.py` that produced it. We match on the NUMBERS instead:
 *
 *   window (start/end)  +  annualized return  +  max drawdown
 *
 * Both metrics are recomputed FROM THE CURVE, not read from JQ's stats endpoint, so a match
 * means the curve itself reproduces the ledger row. Validated against JQ's own figures: a
 * curve-derived max drawdown of 0.3302 against JQ's reported 0.33022.
 *
 * Only `total_pct` is a measured column and only 23 of 124 normalized rows have one (the rest
 * were reconstructed from the wiki, which does not store it). `annual_pct` and `maxdd_pct`
 * survive on every row, which is why they are the match keys.
 *
 * ⚠ Ambiguity is never guessed. Two different strategies can land on the same pair — the
 * ledger already holds two such collisions. A candidate matching more than one row, or a row
 * matched by more than one candidate, is REPORTED and SKIPPED. A wrong series is worse than no
 * series: it would silently corrupt every correlation computed from it.
 *
 * The epoch is taken from the ROW, not from today's config: a retained backtest ran under
 * whatever bench was in force then, and that is exactly what its numbers identify it as.
 *
 * Usage:
 *   node utils/series-backfill.js --scan            # walk the account, cache what it holds
 *   node utils/series-backfill.js --dry             # match against the ledger, write nothing
 *   node utils/series-backfill.js                   # match and save
 *   node utils/series-backfill.js --window val      # backfill the VAL ledger instead
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const { ensureCdp } = require('./exec-config');
const series = require('./backtest-series');

const ROOT = path.resolve(__dirname, '..');
const CACHE = path.join(ROOT, 'data/series-scan.json');
const LEDGER = w => path.join(ROOT, `harness/normalize-${w}.tsv`);

/** Same annualization the harness uses (harness.md §4) — JQ reports total, not annual. */
const annualize = (totalPct, days) =>
  (totalPct == null || !days || days <= 0) ? null : (Math.pow(1 + totalPct / 100, 365 / days) - 1) * 100;

const daysBetween = (a, b) => Math.abs((new Date(a) - new Date(b)) / 86400000);

/** Max drawdown of a cumulative-percent curve, as a percentage. */
function maxDrawdownPct(cum) {
  let peak = -Infinity, mdd = 0;
  for (const c of cum) {
    const eq = 1 + Number(c) / 100;
    if (!Number.isFinite(eq)) continue;
    if (eq > peak) peak = eq;
    if (peak > 0) mdd = Math.max(mdd, (peak - eq) / peak);
  }
  return mdd * 100;
}

/** Reduce a raw curve to the figures the ledger can be matched on. */
function fingerprint(rec) {
  const days = rec.start && rec.end ? Math.max(1, Math.round(daysBetween(rec.start, rec.end))) : null;
  const totalPct = rec.cum.length ? Number(rec.cum[rec.cum.length - 1]) : null;
  return {
    start: rec.start, end: rec.end, points: rec.points, days,
    totalPct,
    annualPct: annualize(totalPct, days),
    maxddPct: maxDrawdownPct(rec.cum),
  };
}

// ── Scan the account ────────────────────────────────────────────────────────

async function listAlgorithms(page) {
  const seen = [];
  const set = new Set();
  for (let p = 1; p <= 60; p++) {
    const ids = await page.evaluate(async (pg) => {
      const t = await (await fetch(`/algorithm/index/list?page=${pg}`, { credentials: 'include' })).text();
      return [...new Set((t.match(/algorithmId=([a-f0-9]{32})/g) || []).map(s => s.split('=')[1]))];
    }, p);
    const before = set.size;
    for (const id of ids) if (!set.has(id)) { set.add(id); seen.push(id); }
    if (set.size === before) break;     // a page that adds nothing is the end of the list
  }
  return seen;
}

async function backtestIdsFor(page, algorithmId) {
  return page.evaluate(async (alg) => {
    const t = await (await fetch(`/algorithm/backtest/buildList?algorithmId=${alg}`,
      { credentials: 'include' })).text();
    return [...new Set([...t.matchAll(/backtestId[=":\s]+([a-f0-9]{32})/g)].map(m => m[1]))];
  }, algorithmId);
}

async function scan({ limit }) {
  const cdp = await ensureCdp();
  const browser = await chromium.connectOverCDP(cdp.url);
  const pages = await browser.contexts()[0].pages();
  const page = pages.find(p => p.url().includes('joinquant.com') && !p.url().includes('/user/login'));
  if (!page) throw new Error('no logged-in JoinQuant tab found in the CDP browser');

  const cache = fs.existsSync(CACHE) ? JSON.parse(fs.readFileSync(CACHE, 'utf8')) : { algorithms: {}, curves: [] };
  const algs = await listAlgorithms(page);
  console.log(`[backfill] account holds ${algs.length} algorithm(s)`);

  const todo = algs.filter(a => !cache.algorithms[a]).slice(0, limit || algs.length);
  console.log(`[backfill] ${todo.length} not yet scanned (${algs.length - todo.length} cached)`);

  let n = 0;
  for (const alg of todo) {
    n++;
    try {
      const ids = await backtestIdsFor(page, alg);
      const found = [];
      for (const id of ids) {
        try {
          const raw = await series.fetchViaPage(page, id);
          if (!raw.time.length) continue;
          const rec = series.toRecord(raw, { backtestId: id, algorithmId: alg });
          // Only the FINGERPRINT is cached, never the curve. The account holds 1,133
          // algorithms; storing every curve would write tens of MB of mostly-unmatched data
          // into a tracked directory. A matched row re-fetches its own curve — at most ~124
          // extra calls, against ~2,300 saved files.
          found.push({ backtestId: id, algorithmId: alg, ...fingerprint(rec) });
        } catch {}
      }
      cache.algorithms[alg] = { scannedAt: new Date().toISOString(), curves: found.length };
      cache.curves.push(...found);
      process.stdout.write(`\r[backfill] scanned ${n}/${todo.length}  curves=${cache.curves.length}   `);
    } catch (e) {
      cache.algorithms[alg] = { scannedAt: new Date().toISOString(), error: String(e.message).slice(0, 80) };
    }
    if (n % 10 === 0) fs.writeFileSync(CACHE, JSON.stringify(cache, null, 1));
  }
  fs.writeFileSync(CACHE, JSON.stringify(cache, null, 1));
  console.log(`\n[backfill] cached ${cache.curves.length} curve(s) -> ${path.relative(ROOT, CACHE)}`);
  try { await browser.close(); } catch {}
  return cache;
}

// ── Match against the ledger ────────────────────────────────────────────────

const TOL_PP = 0.10;      // metrics are stored to 2dp; re-runs move annual ~0.15pp
const TOL_DAYS = 3;       // the window check strategy-post-backtest.js already applies

function ledgerRows(windowName) {
  const p = LEDGER(windowName);
  if (!fs.existsSync(p)) return [];
  const lines = fs.readFileSync(p, 'utf8').split('\n');
  const out = [];
  for (const l of lines.slice(1)) {
    if (!l.trim()) continue;
    const c = l.split('\t');
    if (c[3] !== 'normalized') continue;
    const annual = parseFloat(c[8]), maxdd = parseFloat(c[10]);
    if (!Number.isFinite(annual) || !Number.isFinite(maxdd)) continue;
    out.push({ sourceFile: c[0], title: c[2], start: c[4], end: c[5],
               days: parseInt(c[6], 10) || null, total: c[7] === '' ? null : parseFloat(c[7]),
               annual, maxdd, epoch: c[13] || '2' });
  }
  return out;
}

/**
 * ⚠ Annualize the CANDIDATE over the ROW's day count, not the curve's own span.
 *
 * The ledger annualizes over the REQUESTED window (2022-01-01..2023-12-31, a uniform 729 days
 * on every TRAIN row) while a curve spans the TRADING days that actually occurred
 * (2022-01-04..2023-12-29, 724). Annualizing each over its own span put the same run at 34.06
 * against the row's 33.79 — a 0.27pp gap on identical data, which is three times the match
 * tolerance and matched 0 of 124 rows on the first attempt. `total_pct` agrees exactly
 * (78.86 = 78.86), so the discrepancy is purely the denominator.
 */
function matches(row, cand) {
  if (!cand.start || !cand.end || cand.totalPct == null) return false;
  if (daysBetween(row.start, cand.start) > TOL_DAYS) return false;
  if (daysBetween(row.end, cand.end) > TOL_DAYS) return false;
  if (Math.abs(row.maxdd - cand.maxddPct) > TOL_PP) return false;
  // The strongest key when the row has it: a measured total is exact, with no annualization.
  if (row.total != null) return Math.abs(row.total - cand.totalPct) <= TOL_PP;
  const candAnnual = annualize(cand.totalPct, row.days);
  return candAnnual != null && Math.abs(row.annual - candAnnual) <= TOL_PP;
}

/**
 * Content hash of a strategy body, ignoring the metadata header the fetcher stamps on.
 *
 * 16% of everything fetched is a byte-identical duplicate posted under a different postId
 * (CLAUDE.md), so "one curve claimed by several rows" is usually not ambiguity at all — it is
 * the same strategy under two filenames, and both rows deserve the curve. Two rows whose
 * bodies differ but whose metrics agree to 2dp stay ambiguous: identical endpoints do not
 * prove an identical daily path, and a wrong path silently corrupts every correlation.
 */
const bodyHash = f => {
  try {
    const raw = fs.readFileSync(path.join(ROOT, f), 'utf8').replace(/^(#.*\n)+/, '');
    return require('crypto').createHash('sha256').update(raw).digest('hex');
  } catch { return null; }
};

function reconcile(rows, curves) {
  const pairs = [];
  for (const row of rows) {
    const hits = curves.filter(c => matches(row, c));
    pairs.push({ row, hits });
  }
  // Which rows claim each curve. A curve claimed by several DIFFERENT strategies is ambiguous;
  // one claimed by several copies of the SAME strategy is not.
  const claimants = new Map();
  for (const p of pairs) {
    for (const h of p.hits) {
      if (!claimants.has(h.backtestId)) claimants.set(h.backtestId, []);
      claimants.get(h.backtestId).push(p.row);
    }
  }

  const matched = [], ambiguous = [], unmatched = [];
  for (const p of pairs) {
    if (p.hits.length === 0) { unmatched.push(p.row); continue; }
    // Several retained backtests of the SAME run are common (the same curve surfaces under
    // multiple algorithmIds) — that is not ambiguity, it is a duplicate. Collapse on the
    // fingerprint before deciding.
    const distinct = [...new Map(p.hits.map(h => [`${h.totalPct.toFixed(4)}|${h.maxddPct.toFixed(4)}|${h.points}`, h])).values()];
    if (distinct.length > 1) {
      ambiguous.push({ row: p.row, n: distinct.length, reason: 'row matches several distinct curves' });
      continue;
    }
    const others = claimants.get(distinct[0].backtestId) || [];
    if (others.length > 1) {
      const mine = bodyHash(p.row.sourceFile);
      const allSame = mine && others.every(r => r.sourceFile === p.row.sourceFile || bodyHash(r.sourceFile) === mine);
      if (!allSame) {
        ambiguous.push({ row: p.row, n: others.length, reason: 'curve claimed by several DIFFERENT strategies' });
        continue;
      }
      // else: duplicates of one strategy — every copy legitimately gets the same curve.
    }
    matched.push({ row: p.row, curve: distinct[0] });
  }
  return { matched, ambiguous, unmatched };
}

/**
 * Re-fetch and store the curve for each matched row. The scan cached only fingerprints, so
 * this is where the real data is pulled — for matched rows only.
 */
async function adopt(matched, { dry }) {
  const todo = matched.filter(m => !series.load(series.seriesKey(m.row.sourceFile, WINDOW, m.row.epoch)));
  if (dry) return todo.length;
  if (!todo.length) return 0;

  const cdp = await ensureCdp();
  const browser = await chromium.connectOverCDP(cdp.url);
  const pages = await browser.contexts()[0].pages();
  const page = pages.find(p => p.url().includes('joinquant.com') && !p.url().includes('/user/login'));
  if (!page) throw new Error('no logged-in JoinQuant tab found in the CDP browser');

  let written = 0;
  for (const { row, curve } of todo) {
    try {
      const raw = await series.fetchViaPage(page, curve.backtestId);
      const rec = series.toRecord(raw, {
        sourceFile: row.sourceFile, title: row.title, window: WINDOW, epoch: Number(row.epoch),
        backtestId: curve.backtestId,
        backfilledFrom: curve.backtestId, backfilledAt: new Date().toISOString(),
      });
      series.save(series.seriesKey(row.sourceFile, WINDOW, row.epoch), rec);
      written++;
      process.stdout.write(`\r[backfill] fetched ${written}/${todo.length}   `);
    } catch (e) {
      console.log(`\n[backfill] ⚠ ${row.sourceFile}: ${String(e.message).slice(0, 70)}`);
    }
  }
  if (written) console.log('');
  try { await browser.close(); } catch {}
  return written;
}

let WINDOW = 'train';

if (require.main === module) {
  (async () => {
    const argv = process.argv.slice(2);
    const arg = n => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : null; };
    WINDOW = arg('--window') || 'train';
    const dry = argv.includes('--dry');

    if (argv.includes('--scan')) {
      await scan({ limit: parseInt(arg('--limit'), 10) || 0 });
      return;
    }

    if (!fs.existsSync(CACHE)) {
      console.error('[backfill] no scan cache — run: node utils/series-backfill.js --scan');
      process.exit(1);
    }
    const cache = JSON.parse(fs.readFileSync(CACHE, 'utf8'));
    const rows = ledgerRows(WINDOW);
    console.log(`[backfill] window=${WINDOW}  ledger rows=${rows.length}  cached curves=${cache.curves.length}`);

    const { matched, ambiguous, unmatched } = reconcile(rows, cache.curves);
    console.log(`[backfill] matched ${matched.length}  ambiguous ${ambiguous.length}  unmatched ${unmatched.length}`);

    for (const a of ambiguous.slice(0, 10)) {
      console.log(`  ⚠ AMBIGUOUS ${a.row.sourceFile} — ${a.reason} (${a.n})`);
    }
    if (ambiguous.length > 10) console.log(`  … and ${ambiguous.length - 10} more`);

    const written = await adopt(matched, { dry });
    console.log(`[backfill] ${dry ? 'would write' : 'wrote'} ${written} series`);
    if (dry) console.log('[backfill] (--dry — nothing written)');
  })().catch(e => { console.error(`[backfill] ${e.message}`); process.exit(1); });
}

module.exports = { fingerprint, maxDrawdownPct, annualize, matches, reconcile, ledgerRows, TOL_PP };
