/**
 * factorlib-query.js — query JQ's 因子看板 snapshot as an IDEA source for the enhance loop.
 *
 * Why this exists. `research/factorlib/` has held 285 factors with formulas, IC/IR and
 * post-cost returns since it was ingested, and NOTHING read it — zero references outside its
 * own ingester. Meanwhile the integration round has run out of material: four of six strategy
 * types are exhausted, in the sense that no member improves the type leader (the biggest,
 * 小盘-H-unknown, has 29 members and its best candidate still scores −0.0301 at correlation
 * 0.77). Recombining redundant things cannot fix redundancy; the library needs orthogonal
 * material from outside itself, and this is the outside.
 *
 * ⚠⚠ THIS IS A HYPOTHESIS SOURCE, NOT AN EVIDENCE SOURCE.
 *
 * Every number here was measured on a DIFFERENT BENCH: zz500 universe, 3-year window, JQ's own
 * cost model — none of it comparable to our epoch-5 TRAIN. The whole discipline of this repo is
 * that a result belongs to the bench that produced it; that is what the ledger's `epoch` column
 * and `comparability.measurementPreservedFromPrevious` exist to enforce. So:
 *
 *   - a factor's numbers may NEVER be written into a family page, a type page, results.tsv,
 *     or a candidate.json;
 *   - a factor becomes a real candidate only by being BUILT and MEASURED on our bench, after
 *     which it carries an ordinary ledger row like anything else;
 *   - quote these figures only as provenance ("JQ factor board, zz500/3y, post-cost").
 *
 * ⚠ Turnover is NOT joinable with ours. This table's 换手 runs 1.8–3.06; our family turnover
 * runs 0.0078–0.3061 and is JQ's per-day `turnover_rate` (verified against the stats endpoint:
 * 0.0103 over 484 days). They are different quantities, so "filter factors to this type's
 * turnover band" — the tempting move, since the type axis IS turnover — needs a conversion
 * nobody has derived. `--max-turnover` filters on THIS table's own scale, nothing else.
 *
 * ⚠ Universe mismatch bites hardest where it is needed most. The snapshot is zz500 (mid-cap);
 * the exhausted types are 小盘/微盘. Factor IC measured on zz500 may not transfer at all.
 * Re-ingest with `--universe zz1000` before trusting any of this for the small-cap types.
 *
 * The one finding that does travel: only **6 of 285** factors keep a positive post-cost excess
 * return, and the survivors are the low-turnover end. That is a PRIOR — for a high-turnover
 * idea, the base rate of surviving costs is about 2%.
 *
 * Usage:
 *   node utils/factorlib-query.js                       # top survivors, ranked post-cost
 *   node utils/factorlib-query.js --survivors           # only post-cost positive
 *   node utils/factorlib-query.js --category 动量       # substring match on category
 *   node utils/factorlib-query.js --search 换手         # match name / intro / formula
 *   node utils/factorlib-query.js --min-ir 0.05 --limit 20
 *   node utils/factorlib-query.js --name beta           # one factor, with its formula
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const TSV = path.join(ROOT, 'research/factorlib/factors.tsv');
const README = path.join(ROOT, 'research/factorlib/README.md');

const num = v => { const x = parseFloat(v); return Number.isFinite(x) ? x : null; };

function load() {
  if (!fs.existsSync(TSV)) {
    throw new Error(`no factor snapshot at ${path.relative(ROOT, TSV)} — run: node utils/factorlib-ingest.js`);
  }
  const lines = fs.readFileSync(TSV, 'utf8').split('\n').filter(l => l.trim());
  const head = lines[0].split('\t');
  return lines.slice(1).map(l => {
    const c = l.split('\t');
    const o = {};
    head.forEach((h, i) => { o[h] = c[i]; });
    return o;
  });
}

/** The bench the snapshot was taken on, read from the generated README rather than assumed. */
function provenance() {
  try {
    const t = fs.readFileSync(README, 'utf8');
    const get = k => ((t.match(new RegExp(`\\|\\s*${k}\\s*\\|\\s*([^|]+)\\|`)) || [])[1] || '').trim();
    return {
      universe: get('股票池') || '?',
      range: get('回测周期') || '?',
      fee: get('成本档（主）') || '?',
      takenAt: get('抓取时间') || '?',
    };
  } catch { return { universe: '?', range: '?', fee: '?', takenAt: '?' }; }
}

function query(rows, opt = {}) {
  let out = rows;
  if (opt.survivors) out = out.filter(r => (num(r.top_ex_annual_cost) ?? -1e9) > 0);
  if (opt.category) out = out.filter(r => (r.category || '').includes(opt.category));
  if (opt.search) {
    const s = opt.search.toLowerCase();
    out = out.filter(r => ['name', 'intro', 'formula']
      .some(k => (r[k] || '').toLowerCase().includes(s)));
  }
  if (opt.name) out = out.filter(r => (r.name || '').toLowerCase() === opt.name.toLowerCase());
  if (opt.minIr != null) out = out.filter(r => Math.abs(num(r.ir) ?? 0) >= opt.minIr);
  if (opt.maxTurnover != null) out = out.filter(r => (num(r.turnover_top) ?? 1e9) <= opt.maxTurnover);
  return out.sort((a, b) => (num(b.top_ex_annual_cost) ?? -1e9) - (num(a.top_ex_annual_cost) ?? -1e9));
}

function banner() {
  const p = provenance();
  const rows = load();
  const surv = rows.filter(r => (num(r.top_ex_annual_cost) ?? -1e9) > 0).length;
  return [
    `[factorlib] ${rows.length} factors — ${p.universe} / ${p.range} / ${p.fee}, taken ${p.takenAt.slice(0, 10)}`,
    `[factorlib] ⚠ DIFFERENT BENCH from harness epoch 5. These numbers are a HYPOTHESIS source:`,
    `[factorlib]   never write them into a family/type page, results.tsv or candidate.json.`,
    `[factorlib]   A factor becomes a candidate only by being built and measured on our bench.`,
    `[factorlib] ⚠ ${surv}/${rows.length} keep a positive excess return after costs — the base rate`,
    `[factorlib]   for surviving friction is ~${(100 * surv / rows.length).toFixed(0)}%, and the survivors are low-turnover.`,
  ].join('\n');
}

if (require.main === module) {
  const argv = process.argv.slice(2);
  const arg = n => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : null; };
  try {
    const rows = load();
    const opt = {
      survivors: argv.includes('--survivors'),
      category: arg('--category'),
      search: arg('--search'),
      name: arg('--name'),
      minIr: arg('--min-ir') != null ? parseFloat(arg('--min-ir')) : null,
      maxTurnover: arg('--max-turnover') != null ? parseFloat(arg('--max-turnover')) : null,
    };
    const limit = parseInt(arg('--limit'), 10) || 15;
    const hits = query(rows, opt);

    console.log(banner());
    console.log('');

    if (opt.name && hits.length === 1) {
      const r = hits[0];
      console.log(`  ${r.name}   [${r.category}]`);
      console.log(`  intro   : ${r.intro}`);
      console.log(`  formula : ${r.formula}`);
      console.log(`  post-cost excess annual : ${r.top_ex_annual_cost}%   (cost-free ${r.top_ex_annual_free}%, erosion ${r.erosion})`);
      console.log(`  IC ${r.ic_mean}  IR ${r.ir}  sharpe ${r.sharpe_top_cost}  maxdd ${r.maxdd_top_cost}%  turnover ${r.turnover_top}`);
      console.log('\n  ⚠ zz500/3y on JQ\'s bench. To use it: build it, measure it on TRAIN, let it earn a ledger row.');
      process.exit(0);
    }

    console.log(`  ${hits.length} match(es), showing ${Math.min(limit, hits.length)} ranked by POST-COST excess annual`);
    console.log('   post-cost   free  erosion      IR   turnover  factor');
    for (const r of hits.slice(0, limit)) {
      console.log(`   ${String(r.top_ex_annual_cost).padStart(8)}%  ${String(r.top_ex_annual_free).padStart(6)}%  ` +
                  `${String(r.erosion).padStart(7)}  ${String(num(r.ir) == null ? '—' : num(r.ir).toFixed(3)).padStart(7)}  ` +
                  `${String(r.turnover_top).padStart(8)}  ${r.name} [${(r.category || '').slice(0, 10)}]`);
    }
    if (hits.length > limit) console.log(`   … ${hits.length - limit} more (--limit N)`);
  } catch (e) {
    console.error(`[factorlib] ${e.message}`);
    process.exit(1);
  }
}

module.exports = { load, query, provenance, banner };
