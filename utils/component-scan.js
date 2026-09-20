/**
 * component-scan.js — propose INGREDIENTS by measuring what each strategy adds to the leader
 * of its own strategy type.
 *
 * The question this answers is not "is this strategy good?" — the ledger already answers that,
 * and since epoch 5 it answers it for every strategy including the ones that fail the gate.
 * The question is "does adding this to what we already hold make it better?", which no scalar
 * in the ledger can answer, because it depends on correlation.
 *
 * With daily curves stored (utils/backtest-series.js) the answer is COMPUTABLE WITHOUT A
 * BACKTEST: align two return series by date, blend them, and measure the blend. Every pair in
 * a type can be screened for the price of some arithmetic, and only the survivors need to
 * spend real backtest minutes.
 *
 * ⚠⚠ What an ex-post blend is NOT. Averaging two return series models a portfolio rebalanced
 * to equal weight EVERY DAY, for free. Real rebalancing costs money and this charges none, so
 * a blend figure here is an UPPER BOUND and a screening device — never a result. Nothing from
 * this file may be written to a family page or the results ledger; a candidate that looks good
 * here still has to be built as one strategy and run through the frozen harness, where
 * `utils/type-integrate-check.js` applies the four rules. The repo has already measured what
 * unpriced friction does to a headline: pinning execution settings took one book from 369.07%
 * to 195.74% annual return.
 *
 * ⚠ It also inherits the diversification trap the integrate guard exists for: blending raises
 * Sharpe mechanically whenever correlation < 1. That is exactly why the ranking below is on
 * the SCORE UPLIFT OVER THE LEADER (annual − maxdd, the harness objective), not on Sharpe, and
 * why correlation is printed next to every candidate rather than hidden inside a single number.
 *
 * Usage:
 *   node utils/component-scan.js --validate     # check series-derived metrics vs the ledger
 *   node utils/component-scan.js                # rank ingredients per type
 *   node utils/component-scan.js --type 小盘-H-mid
 */

const fs = require('fs');
const path = require('path');
const series = require('./backtest-series');
const harness = require('./harness-config');

const ROOT = path.resolve(__dirname, '..');
const PAGES_DIR = path.join(ROOT, 'wiki/strategies');
const TYPE_DIR = path.join(ROOT, 'wiki/types');
const LEDGER = path.join(ROOT, 'harness/normalize-train.tsv');

const fmField = (t, k) => (t.match(new RegExp(`^${k}:\\s*(.*)$`, 'm')) || [])[1] || '';
const daysBetween = (a, b) => Math.abs((new Date(a) - new Date(b)) / 86400000);

/**
 * JQ's own Sharpe uses a 4% risk-free rate. Calibrated, not assumed: `--validate` prints the
 * series-derived figure next to the ledger's for the same strategy, so a wrong constant here
 * shows up immediately rather than silently biasing every blend.
 */
const RISK_FREE = 0.04;

/** Compound a daily return series into cumulative percent. */
function toCum(returns) {
  const out = [];
  let eq = 1;
  for (const r of returns) { eq *= (1 + (Number.isFinite(r) ? r : 0)); out.push((eq - 1) * 100); }
  return out;
}

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

/** Annual / sharpe / maxdd of a daily return series spanning `days` calendar days. */
function metrics(returns, days) {
  const clean = returns.filter(Number.isFinite);
  if (clean.length < 3) return null;
  const cum = toCum(clean);
  const totalPct = cum[cum.length - 1];
  const annualPct = (Math.pow(1 + totalPct / 100, 365 / days) - 1) * 100;
  const mean = clean.reduce((s, v) => s + v, 0) / clean.length;
  const sd = Math.sqrt(clean.reduce((s, v) => s + (v - mean) ** 2, 0) / (clean.length - 1));
  const vol = sd * Math.sqrt(252);
  const sharpe = vol === 0 ? null : (annualPct / 100 - RISK_FREE) / vol;
  const maxddPct = maxDrawdownPct(cum);
  return {
    totalPct: +totalPct.toFixed(2),
    annualPct: +annualPct.toFixed(2),
    maxddPct: +maxddPct.toFixed(2),
    volPct: +(vol * 100).toFixed(2),
    sharpe: sharpe == null ? null : +sharpe.toFixed(2),
    score: +((annualPct - maxddPct) / 100).toFixed(4),
    days, n: clean.length,
  };
}

/** Align two stored series on their shared dates. Position-alignment would compare wrong days. */
function align(A, B) {
  const ra = series.dailyReturns(A.cum), rb = series.dailyReturns(B.cum);
  const ma = new Map();
  // dailyReturns is index-aligned with dates (same length), so date i carries return i.
  for (let i = 0; i < A.dates.length; i++) ma.set(A.dates[i], ra[i]);
  const dates = [], xa = [], xb = [];
  for (let i = 0; i < B.dates.length; i++) {
    const v = ma.get(B.dates[i]);
    if (v == null || !Number.isFinite(v) || !Number.isFinite(rb[i])) continue;
    dates.push(B.dates[i]); xa.push(v); xb.push(rb[i]);
  }
  return { dates, a: xa, b: xb };
}

/**
 * Split a blend's risk reduction into "diversification" and "edge".
 *
 * This is the attribution `type-integrate-check.js` documented as NOT computable from the
 * ledger, which stores only scalars. With daily curves it is:
 *
 *   weightedVol = Σ wᵢ·σᵢ   — the blend's volatility IF every member moved together (ρ = 1)
 *   blendVol    = σ of the actual blended return series
 *   ratio       = weightedVol / blendVol   (1.0 = no diversification at all)
 *
 * `sharpeNoDiversification` is then the Sharpe the SAME returns would earn at `weightedVol`.
 * Comparing it with the blend's real Sharpe separates the two sources cleanly: whatever sits
 * above it is risk-side (correlation < 1), and only what `sharpeNoDiversification` itself
 * clears is return-side.
 *
 * ⚠ Still an ex-post, cost-free, daily-rebalanced construction — the same upper bound the
 * rest of this file carries. It decides how to READ a measured blend, never replaces measuring one.
 */
function diversification(seriesList, weights = null) {
  const n = seriesList.length;
  if (n < 2) return null;
  const w = weights || Array(n).fill(1 / n);

  // Align every member on the dates ALL of them share.
  const maps = seriesList.map(s => {
    const r = series.dailyReturns(s.cum);
    const m = new Map();
    for (let i = 0; i < s.dates.length; i++) if (Number.isFinite(r[i])) m.set(s.dates[i], r[i]);
    return m;
  });
  const dates = [...maps[0].keys()].filter(d => maps.every(m => m.has(d))).sort();
  if (dates.length < 30) return null;

  const cols = maps.map(m => dates.map(d => m.get(d)));
  const sd = xs => {
    const mu = xs.reduce((s, v) => s + v, 0) / xs.length;
    return Math.sqrt(xs.reduce((s, v) => s + (v - mu) ** 2, 0) / (xs.length - 1));
  };
  const ann = v => v * Math.sqrt(252);

  const vols = cols.map(c => ann(sd(c)));
  const blended = dates.map((_, i) => cols.reduce((s, c, k) => s + w[k] * c[i], 0));
  const blendVol = ann(sd(blended));
  const weightedVol = vols.reduce((s, v, k) => s + w[k] * v, 0);

  const days = Math.max(1, Math.round(daysBetween(dates[0], dates[dates.length - 1])));
  const m = metrics(blended, days);

  const corr = [];
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) corr.push({ i, j, rho: series.pearson(cols[i], cols[j]) });
  }

  return {
    overlapDays: dates.length,
    memberVolPct: vols.map(v => +(v * 100).toFixed(2)),
    blendVolPct: +(blendVol * 100).toFixed(2),
    weightedVolPct: +(weightedVol * 100).toFixed(2),
    ratio: +(weightedVol / blendVol).toFixed(3),
    correlations: corr,
    meanCorr: corr.length ? +(corr.reduce((s, c) => s + (c.rho ?? 0), 0) / corr.length).toFixed(3) : null,
    blend: m,
    sharpeNoDiversification: m && weightedVol > 0
      ? +(((m.annualPct / 100) - RISK_FREE) / weightedVol).toFixed(2) : null,
  };
}

/** sourceFile -> { family, page } */
function pageIndex() {
  const out = {};
  if (!fs.existsSync(PAGES_DIR)) return out;
  for (const p of fs.readdirSync(PAGES_DIR).filter(f => f.endsWith('.md'))) {
    const t = fs.readFileSync(path.join(PAGES_DIR, p), 'utf8');
    const src = fmField(t, 'sourceFile').trim();
    if (src) out[src] = { family: fmField(t, 'family').trim(), page: p.replace(/\.md$/, '') };
  }
  return out;
}

/** family -> type key, from the generated type pages. */
function familyToType() {
  const out = {};
  if (!fs.existsSync(TYPE_DIR)) return out;
  for (const f of fs.readdirSync(TYPE_DIR).filter(f => f.endsWith('.md'))) {
    const t = fs.readFileSync(path.join(TYPE_DIR, f), 'utf8');
    const key = fmField(t, 'type').trim() || f.replace(/\.md$/, '');
    // The frontmatter is a YAML list OF wiki links, so the line reads `families: [[[A]], [[B]]]`
    // — three opening brackets on the first entry. Stripping only the `[[`/`]]` pairs left the
    // list's own bracket on the first name (`[ETF动量`), so the first family of every type
    // silently failed to match and its strategies fell into `(untyped)`.
    for (const m of (fmField(t, 'families').match(/\[\[([^\]]+)\]\]/g) || [])) {
      out[m.replace(/[[\]]/g, '')] = key;
    }
  }
  return out;
}

/** Normalized ledger rows that have a stored series, decorated with family + type. */
function members() {
  const idx = pageIndex(), f2t = familyToType();
  const out = [];
  if (!fs.existsSync(LEDGER)) return out;
  for (const line of fs.readFileSync(LEDGER, 'utf8').split('\n').slice(1)) {
    if (!line.trim()) continue;
    const c = line.split('\t');
    if (c[3] !== 'normalized') continue;
    const epoch = c[13] || '2';
    const key = series.seriesKey(c[0], 'train', epoch);
    const rec = series.load(key);
    if (!rec) continue;
    const family = (idx[c[0]] || {}).family || '';
    out.push({
      sourceFile: c[0], title: c[2], family, type: f2t[family] || '(untyped)',
      days: parseInt(c[6], 10) || null,
      annual: parseFloat(c[8]), sharpe: parseFloat(c[9]), maxdd: parseFloat(c[10]),
      objective: c[11] === 'DQ' ? null : parseFloat(c[11]), gate: c[12], epoch,
      seriesKey: key, rec,
    });
  }
  return out;
}

/**
 * Compare series-derived metrics against the ledger row they belong to.
 *
 * ⚠ Annualize over the ROW's day count, not the curve's own span. The ledger uses the
 * REQUESTED window (a uniform 729 days on TRAIN); a curve spans the trading days that
 * occurred (724). Using each side's own span injects a systematic gap that SCALES WITH THE
 * RETURN LEVEL — about 0.27pp at the median but 0.80pp on an 85.9% book — which made healthy
 * rows look like bad matches and buried any real disagreement underneath a known convention.
 */
function validate(ms) {
  const rows = [];
  for (const m of ms) {
    const r = series.dailyReturns(m.rec.cum);
    const days = m.days || Math.max(1, Math.round(daysBetween(m.rec.start, m.rec.end)));
    const got = metrics(r, days);
    if (!got) continue;
    rows.push({
      file: path.basename(m.sourceFile),
      annualLedger: m.annual, annualSeries: got.annualPct, dAnnual: +(got.annualPct - m.annual).toFixed(2),
      maxddLedger: m.maxdd, maxddSeries: got.maxddPct, dMaxdd: +(got.maxddPct - m.maxdd).toFixed(2),
      sharpeLedger: m.sharpe, sharpeSeries: got.sharpe, dSharpe: got.sharpe == null ? null : +(got.sharpe - m.sharpe).toFixed(2),
    });
  }
  return rows;
}

/** For one type: rank every other member by what a 50/50 blend with the leader would score. */
function rankType(list) {
  const scored = list.filter(m => m.objective != null);
  if (scored.length < 2) return null;
  const leader = scored.reduce((a, b) => (b.objective > a.objective ? b : a));
  const out = [];
  for (const m of list) {
    if (m.sourceFile === leader.sourceFile) continue;
    const al = align(leader.rec, m.rec);
    if (al.dates.length < 30) continue;
    const days = Math.max(1, Math.round(daysBetween(al.dates[0], al.dates[al.dates.length - 1])));
    const solo = metrics(al.a, days);
    const cand = metrics(al.b, days);
    const blend = metrics(al.a.map((v, i) => (v + al.b[i]) / 2), days);
    if (!solo || !blend) continue;
    out.push({
      ...m,
      corr: series.pearson(al.a, al.b),
      overlap: al.dates.length,
      soloScore: solo.score, soloSharpe: solo.sharpe,
      candScore: cand ? cand.score : null,
      blendScore: blend.score, blendSharpe: blend.sharpe,
      uplift: +(blend.score - solo.score).toFixed(4),
    });
  }
  out.sort((a, b) => b.uplift - a.uplift);
  return { leader, candidates: out };
}

if (require.main === module) {
  const argv = process.argv.slice(2);
  const arg = n => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : null; };
  const ms = members();

  if (!ms.length) {
    console.log('[component] no strategies have a stored series yet.');
    console.log('[component] run: node utils/series-backfill.js --scan  then  node utils/series-backfill.js');
    process.exit(0);
  }

  if (argv.includes('--validate')) {
    const rows = validate(ms);
    console.log(`[component] series-derived vs ledger, ${rows.length} strategy(ies)`);
    console.log('  file                                  annual(led/ser/Δ)        maxdd(led/ser/Δ)      sharpe(led/ser/Δ)');
    for (const r of rows.slice(0, 25)) {
      console.log(`  ${r.file.slice(0, 36).padEnd(36)}  ${String(r.annualLedger).padStart(8)}/${String(r.annualSeries).padStart(8)}/${String(r.dAnnual).padStart(6)}` +
                  `   ${String(r.maxddLedger).padStart(6)}/${String(r.maxddSeries).padStart(6)}/${String(r.dMaxdd).padStart(5)}` +
                  `   ${String(r.sharpeLedger).padStart(5)}/${String(r.sharpeSeries).padStart(5)}/${String(r.dSharpe).padStart(5)}`);
    }
    const med = a => { const s = a.filter(Number.isFinite).sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : null; };
    console.log(`\n  median |Δannual| = ${med(rows.map(r => Math.abs(r.dAnnual)))}pp  ` +
                `|Δmaxdd| = ${med(rows.map(r => Math.abs(r.dMaxdd)))}pp  ` +
                `|Δsharpe| = ${med(rows.map(r => Math.abs(r.dSharpe)))}`);
    console.log('  (a large Δ means the curve does not reproduce the row — investigate before trusting any blend)');
    process.exit(0);
  }

  const byType = {};
  for (const m of ms) (byType[m.type] = byType[m.type] || []).push(m);
  const only = arg('--type');

  console.log(`[component] ${ms.length} strategy(ies) with series across ${Object.keys(byType).length} type(s)`);
  console.log('[component] ⚠ blends below are DAILY-REBALANCED AND COST-FREE — a screening upper bound,');
  console.log('[component]   not a result. Survivors must be built and run through the frozen harness.\n');

  const intThreshold = harness.stageThreshold('integrate');
  for (const [type, list] of Object.entries(byType).sort((a, b) => b[1].length - a[1].length)) {
    if (only && type !== only) continue;
    const r = rankType(list);
    if (!r) { console.log(`── ${type}: ${list.length} member(s), not enough scored members to rank`); continue; }
    console.log(`── ${type}  (${list.length} members)  leader: ${path.basename(r.leader.sourceFile)} score=${r.leader.objective}`);
    if (!r.candidates.length) { console.log('   (no comparable members)\n'); continue; }
    console.log('   uplift   corr   blendScore  blendSharpe  gate  candidate');
    for (const c of r.candidates.slice(0, 8)) {
      const mark = c.uplift > 0 ? '+' : ' ';
      console.log(`   ${mark}${String(c.uplift).padStart(7)}  ${String(c.corr).padStart(6)}  ` +
                  `${String(c.blendScore).padStart(10)}  ${String(c.blendSharpe).padStart(11)}  ` +
                  `${c.gate.padEnd(4)}  ${path.basename(c.sourceFile).slice(0, 44)}`);
    }
    const harvest = r.candidates.filter(c => c.uplift > 0 && c.gate === 'fail');
    if (harvest.length) {
      console.log(`   → ${harvest.length} GATE-FAILING member(s) still improve the leader — these are the`);
      console.log('     component candidates a standalone bar would have discarded.');
    }
    const best = r.candidates[0];
    if (best && best.blendSharpe != null && best.blendSharpe < intThreshold) {
      console.log(`   → note: best blend sharpe ${best.blendSharpe} is below the integrate bar ${intThreshold}`);
    }
    console.log('');
  }
}

module.exports = { metrics, align, members, rankType, validate, toCum, maxDrawdownPct, familyToType,
                   diversification, RISK_FREE };
