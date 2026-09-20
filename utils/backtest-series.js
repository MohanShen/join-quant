/**
 * backtest-series.js — capture and store the DAILY EQUITY CURVE of a backtest.
 *
 * Why this exists. Every number this repo stores about a backtest is a scalar scraped from a
 * summary row: annual, sharpe, maxdd. That is enough to rank a strategy STANDALONE and not
 * enough to judge it as an INGREDIENT, because the thing that makes an ingredient valuable —
 * low correlation with what you already hold — is not a function of any scalar.
 *
 * The concrete consequence was in `utils/type-integrate-check.js`: rule 2 wants to know how
 * much of a blend's Sharpe gain is diversification, and could only test the *signature*
 * (sharpe up, return not up) because "the ledger stores annual/sharpe/maxdd, not return
 * series, so correlation and a true variance decomposition are NOT computable here".
 * With a series they are.
 *
 * Where the data comes from. JQ's backtest page renders its chart from
 *   GET /algorithm/backtest/result?backtestId=<id>&offset=<n>&userRecordOffset=0&ajax=1
 * which returns `data.result.overallReturn = { time: [ms…], value: [cumulative %…] }` plus the
 * same shape under `benchmark`. It pages 1000 points at a time; the page whose length is under
 * 1000 is the last. Found by sniffing the summary page's own network traffic — it is not
 * documented, and `/algorithm/backtest/summary` is HTML, not JSON.
 *
 * ⚠ `value` is CUMULATIVE PERCENT, not a daily return, and it is not a price. Chaining is
 * therefore (1+c_t/100)/(1+c_{t-1}/100)-1, NOT a difference of the percentages — differencing
 * silently understates every return once the curve is far from zero, which on a book up 300%
 * is a factor-of-four error. `dailyReturns` is the only place this conversion is written.
 *
 * ⚠ Identity. `backtestId` is re-minted on every request like every other JQ id (CLAUDE.md),
 * so it is recorded for provenance but never used as a key. Series are keyed by
 * `sourceFile + window + epoch`, the same triple the ledger rows use.
 *
 * Usage:
 *   node utils/backtest-series.js --backtest <id> [--out <file>]   # fetch + print a summary
 *   node utils/backtest-series.js --list                           # what is stored
 *   node utils/backtest-series.js --corr <keyA> <keyB>             # correlation of two stored series
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DIR = path.join(ROOT, 'data/series');
const BASE = 'https://www.joinquant.com/algorithm/backtest/result';
const PAGE = 1000;

const url = (backtestId, offset) =>
  `${BASE}?backtestId=${encodeURIComponent(backtestId)}&offset=${offset}&userRecordOffset=0&ajax=1`;

const iso = ms => new Date(ms).toISOString().slice(0, 10);

/** Storage key for a measured run. Mirrors the ledger's identity triple. */
function seriesKey(sourceFile, windowName, epoch) {
  const slug = String(sourceFile).replace(/^strategies\//, '').replace(/\.py$/, '')
    .replace(/[^\w一-龥.-]+/g, '_');
  return `${slug}__${windowName}__e${epoch}`;
}

const seriesPath = key => path.join(DIR, `${key}.json`);

/**
 * Pull every page of one series. `getJson` is injected so the same walk serves both the
 * in-page fetch (inside the CDP browser, where the backtest just ran) and the standalone
 * jq-http path — the two differ only in transport.
 */
async function walk(backtestId, getJson) {
  const time = [], value = [], bTime = [], bValue = [];
  for (let offset = 0; ; offset += PAGE) {
    const r = await getJson(url(backtestId, offset));
    const res = r && r.data && r.data.result;
    if (!res || !res.overallReturn) {
      throw new Error(`no result payload at offset ${offset} for backtest ${backtestId}`);
    }
    const t = res.overallReturn.time || [], v = res.overallReturn.value || [];
    time.push(...t); value.push(...v);
    const b = res.benchmark || {};
    bTime.push(...(b.time || [])); bValue.push(...(b.value || []));
    // The short page is the last one. A full page with nothing on it also ends the walk,
    // so a server-side change of PAGE size cannot spin this forever.
    if (t.length < PAGE || t.length === 0) break;
  }
  return { time, value, bTime, bValue };
}

/** Fetch through the already-open CDP page the backtest ran in (no new tab, no navigation). */
async function fetchViaPage(page, backtestId) {
  return walk(backtestId, u => page.evaluate(async link => {
    const r = await fetch(link, { credentials: 'include' });
    return r.json();
  }, u));
}

/** Fetch standalone (backfill / CLI). Routes through jq-http like all other JQ traffic. */
async function fetchViaHttp(backtestId) {
  const jq = require('./jq-http');
  return walk(backtestId, u => jq.jqJson(u));
}

/**
 * Cumulative-percent curve -> daily fractional returns, SAME LENGTH as `cum`.
 *
 * ⚠ The curve starts from an implicit 0 baseline, so `cum[0]` is already the FIRST DAY'S
 * RETURN, not a starting level. An earlier version began the loop at i=1 and silently threw
 * that day away: on 以混沌之火_信息熵策略 the first point is +21.51%, and dropping it turned a
 * +25.77% run into +3.51%, reporting annual 1.75% against the ledger's 12.16%. 18 of 71
 * stored curves open above 1%, so this was not a single bad row.
 *
 * Returns null for a point whose predecessor wiped the account out (-100%), which would
 * otherwise divide by zero.
 */
function dailyReturns(cum) {
  const out = [];
  for (let i = 0; i < cum.length; i++) {
    const prev = i === 0 ? 1 : 1 + Number(cum[i - 1]) / 100;
    const cur = 1 + Number(cum[i]) / 100;
    out.push(prev === 0 || !Number.isFinite(prev) || !Number.isFinite(cur) ? null : cur / prev - 1);
  }
  return out;
}

/** Pearson correlation over the pairwise-complete entries of two equal-length arrays. */
function pearson(a, b) {
  const xs = [], ys = [];
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    if (Number.isFinite(a[i]) && Number.isFinite(b[i])) { xs.push(a[i]); ys.push(b[i]); }
  }
  if (xs.length < 3) return null;
  const mx = xs.reduce((s, v) => s + v, 0) / xs.length;
  const my = ys.reduce((s, v) => s + v, 0) / ys.length;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < xs.length; i++) {
    const dx = xs[i] - mx, dy = ys[i] - my;
    sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
  }
  if (sxx === 0 || syy === 0) return null;   // a flat series has no correlation, not zero
  return Number((sxy / Math.sqrt(sxx * syy)).toFixed(4));
}

/**
 * Correlate two stored series BY DATE rather than by position. Two backtests over the same
 * window can still differ in length (a strategy that starts late, a halted name), and lining
 * two unequal arrays up from index 0 would silently compare different days.
 */
function correlate(A, B) {
  const ra = dailyReturns(A.cum), rb = dailyReturns(B.cum);
  const ma = new Map(), xs = [], ys = [];
  // dailyReturns is index-aligned with dates (same length), so date i carries return i.
  for (let i = 0; i < A.dates.length; i++) ma.set(A.dates[i], ra[i]);
  for (let i = 0; i < B.dates.length; i++) {
    const v = ma.get(B.dates[i]);
    if (v == null) continue;
    xs.push(v); ys.push(rb[i]);
  }
  return { corr: pearson(xs, ys), overlapDays: xs.length };
}

/** Normalize a raw walk into the stored record. */
function toRecord(raw, meta) {
  const dates = raw.time.map(iso);
  const cum = raw.value.map(Number);
  const bench = new Map();
  raw.bTime.forEach((t, i) => bench.set(iso(t), Number(raw.bValue[i])));
  return {
    ...meta,
    capturedAt: new Date().toISOString(),
    points: dates.length,
    start: dates[0] || null,
    end: dates[dates.length - 1] || null,
    dates,
    cum,
    benchCum: dates.map(d => (bench.has(d) ? bench.get(d) : null)),
  };
}

function save(key, record) {
  fs.mkdirSync(DIR, { recursive: true });
  fs.writeFileSync(seriesPath(key), JSON.stringify(record));
  return seriesPath(key);
}

function load(key) {
  const p = seriesPath(key);
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
}

function list() {
  if (!fs.existsSync(DIR)) return [];
  return fs.readdirSync(DIR).filter(f => f.endsWith('.json')).map(f => f.replace(/\.json$/, ''));
}

/**
 * Trim a record to a window. The editor's date inputs decide what actually ran, so this is a
 * guard against a series that overshoots the requested window, not a substitute for the
 * window check in strategy-post-backtest.js.
 */
function clip(record, start, end) {
  const keep = record.dates.map((d, i) => ((!start || d >= start) && (!end || d <= end) ? i : -1))
    .filter(i => i >= 0);
  return {
    ...record,
    points: keep.length,
    start: record.dates[keep[0]] || null,
    end: record.dates[keep[keep.length - 1]] || null,
    dates: keep.map(i => record.dates[i]),
    cum: keep.map(i => record.cum[i]),
    benchCum: keep.map(i => record.benchCum[i]),
  };
}

if (require.main === module) {
  (async () => {
    const argv = process.argv.slice(2);
    const arg = n => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : null; };

    if (argv.includes('--list')) {
      const keys = list();
      console.log(`[series] ${keys.length} stored series in data/series/`);
      for (const k of keys) {
        const r = load(k);
        console.log(`  ${k}  ${r.points}d  ${r.start}..${r.end}`);
      }
      return;
    }

    if (argv.includes('--corr')) {
      const i = argv.indexOf('--corr');
      const A = load(argv[i + 1]), B = load(argv[i + 2]);
      if (!A || !B) { console.error('[series] one or both keys not found (see --list)'); process.exit(1); }
      const { corr, overlapDays } = correlate(A, B);
      console.log(`[series] corr(${argv[i + 1]}, ${argv[i + 2]}) = ${corr}  over ${overlapDays} shared days`);
      return;
    }

    const bt = arg('--backtest');
    if (!bt) {
      console.error('usage: node utils/backtest-series.js --backtest <id> [--out <file>] | --list | --corr <a> <b>');
      process.exit(2);
    }
    const raw = await fetchViaHttp(bt);
    const rec = toRecord(raw, { backtestId: bt, sourceFile: null, window: 'adhoc', epoch: null });
    const r = dailyReturns(rec.cum).filter(Number.isFinite);
    const mean = r.reduce((s, v) => s + v, 0) / (r.length || 1);
    const sd = Math.sqrt(r.reduce((s, v) => s + (v - mean) ** 2, 0) / (r.length || 1));
    console.log(`[series] ${rec.points} points  ${rec.start}..${rec.end}`);
    console.log(`[series] cumulative ${rec.cum[rec.cum.length - 1]}%  |  daily sd ${(sd * 100).toFixed(3)}%  ` +
                `annualized vol ${(sd * Math.sqrt(252) * 100).toFixed(1)}%`);
    const out = arg('--out');
    if (out) { fs.writeFileSync(out, JSON.stringify(rec)); console.log(`[series] wrote ${out}`); }
    try { await require('./jq-http').close(); } catch {}
  })().catch(e => { console.error(`[series] ${e.message}`); process.exit(1); });
}

module.exports = { seriesKey, seriesPath, fetchViaPage, fetchViaHttp, toRecord, save, load, list,
                   dailyReturns, pearson, correlate, clip, PAGE };
