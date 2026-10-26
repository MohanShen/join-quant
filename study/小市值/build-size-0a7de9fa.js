// q-e9-champ-size — EDGE TEST for the 小市值 family's `measured` edge 规模 on its epoch-9 champion
// `strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py`
// (control: objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00, 365 days).
//
// ## What is being tested
//
// The family's strongest measurement (q-e6-1: "ranks 1-1000 >> ranks 1001-2000"; q-e6-17: only 5%
// of annual survives the shift once the 100x unit bug is fixed) was taken on a DIFFERENT book
// (7a1c225f), a DIFFERENT pool (all-A bottom-1000) and a DIFFERENT bench (epoch 6, TRAIN 2022-23).
// This champion's pool is 399101 components -> market_cap.between(10, 80) -> head(200) -> head(80),
// so 规模 is UNPROVEN for it. Shift the pool ONE cap notch up and see what survives.
//
// ## The ONE edit — L190
//
//   `    initial_list = fund_df['code'].head(200).tolist()`
//     ->
//   `    initial_list = fund_df['code'].iloc[200:400].tolist()`
//
// `fund_df` is already sorted market_cap ASCENDING (L184 `order_by(valuation.market_cap.asc())`),
// so `.iloc[200:400]` is exactly the next 200 names by ascending cap. Everything else is verbatim:
// the 10-80亿 cap filter, the three secondary filters, the second `head(80)`, the BBI band, the
// 2-name sizing, the 顶背离 risk overlay and the frozen cost block.
//
// ⚠ The downstream `head(80)` (L205) is UNTOUCHED, so `candidate_list` becomes "the 80 smallest
// names among ranks 201-400" — a clean one-notch shift, not a widening.
//
// ## THE THIRD BRANCH — a RUNTIME pool-depth guard (gatekeeper requirement, mandatory)
//
// A BUILD-TIME assertion that `len(fund_df) >= 400` is impossible: build time is JS with no JQ
// data, and the depth of 399101 after the 10-80亿 cap filter is only knowable at run time. If that
// depth is ever < 400 the slice silently returns fewer than 200 names (or none), and the run would
// hand back a small number that reads EXACTLY like a refutation of 规模 while really meaning "the
// pool was not deep enough to run the test".
//
// So the builder inserts ONE log line immediately after the edit site:
//
//   `    log.error('POOLDEPTH date=%s n=%d' % (str(context.previous_date), len(fund_df)))`
//
// `log.error` (not `log.info`) so it lands in the 错误 tab as well as the 日志 tab and
// `utils/backtest-log.js` can read it either way. It is INSTRUMENTATION, not a second edit: it
// changes no selection, no ordering and no order. The undo assertion below restores L190 AND
// removes this line, and must reproduce `py2to3(raw)` byte-for-byte.
//
// Verdict rule, pre-registered:
//   any rebalance with n < 400  => INVALID ("could not run"), NOT "no effect"
//   annual >= 207.6% (75% of 276.82) => 规模 does NOT explain this book
//   annual <  138.4% (50%)           => 规模 reproduces on the champion
//
// ## Free reads already in the book
//
//   L191  log.info(f"市值筛选后数量: {len(initial_list)}")      <- names surviving the slice
//   L206  log.info(f"精选市值后数量: {len(candidate_list)}")    <- after head(80)
//   L247  log.info(f"BBI趋势过滤后最终选股数量: {len(bbi_pass)}") <- after the band
// and `init` sets `log.set_level('strategy', 'debug')` (L96), so all three are retrievable.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;

const TAG = 'size-up1';

// Line-exact, both directions. Matching whole lines (never substrings) is what keeps the undo
// assertion a real check rather than a tautology.
const SITE = "    initial_list = fund_df['code'].head(200).tolist()";
const EDITED = "    initial_list = fund_df['code'].iloc[200:400].tolist()"
             + "  # q-e9-champ-size: pool moved ONE cap notch up (ranks 201-400) — ONLY change vs the raw book";
// Instrumentation, inserted immediately after the edit site. Reports the depth BEFORE the slice.
const PROBE = "    log.error('POOLDEPTH date=%s n=%d' % (str(context.previous_date), len(fund_df)))"
            + "  # q-e9-champ-size instrumentation: n < 400 at ANY rebalance => measurement INVALID";

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /0a7de9fa/.test(f));
if (!src) throw new Error('0a7de9fa not found in strategies/');

// ⚠ The comparison baseline is py2to3(raw), NOT the on-disk file: the variant is built on the
// py2to3 output, which is also what the normalizer measured the control on.
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));
const rawLines = raw.split('\n');

const hits = rawLines.filter(l => l === SITE).length;
if (hits !== 1) throw new Error(`expected exactly 1 edit site, got ${hits}`);

// The ascending sort is what makes `.iloc[200:400]` mean "the next 200 by ascending cap". If that
// ordering were ever descending the edit would mean the opposite of the design.
const SORT = '    ).order_by(valuation.market_cap.asc())  # 从小到大排序';
if (rawLines.filter(l => l === SORT).length !== 1) {
  throw new Error('the ascending market_cap sort is not where the design says it is — refusing');
}
// The downstream second-stage head(80) must survive untouched: the test is a SHIFT, not a widening.
const HEAD80 = "    candidate_list = fund_df['code'].head(80).tolist()";
if (rawLines.filter(l => l === HEAD80).length !== 1) {
  throw new Error('the second-stage head(80) is not where the design says it is — refusing');
}
// The cap filter defines the universe whose depth the probe measures.
const CAPFILTER = '        valuation.market_cap.between(10, 80)  # 市值范围：5亿-50亿';
if (rawLines.filter(l => l === CAPFILTER).length !== 1) {
  throw new Error('the 10-80亿 cap filter is not where the design says it is — refusing');
}

// Build: replace the site, and insert the probe immediately after it.
const body = rawLines.flatMap(l => (l === SITE ? [EDITED, PROBE] : [l])).join('\n');

if (!body.includes(EDITED)) throw new Error('the edit did not land');
if (!body.includes(PROBE)) throw new Error('the POOLDEPTH probe did not land');
if (body.includes("fund_df['code'].head(200)")) {
  throw new Error('the head(200) slice survived the edit — refusing');
}
if (!body.includes(HEAD80)) throw new Error('the second-stage head(80) was lost — refusing');
if (!body.includes(CAPFILTER)) throw new Error('the cap filter was lost — refusing');
for (const need of ['f"市值筛选后数量: {len(initial_list)}"',
                    'f"精选市值后数量: {len(candidate_list)}"',
                    'f"BBI趋势过滤后最终选股数量: {len(bbi_pass)}"',
                    "log.set_level('strategy', 'debug')"]) {
  if (!body.includes(need)) throw new Error(`missing free-read log line: ${need}`);
}

// ⚠⚠ The ONLY differences from py2to3(raw) must be the swapped line and the inserted probe.
// Assert on `body` — the PRE-OVERRIDE text — never on a slice of the final file: cutting the
// output at a marker is ambiguous against the file's own trailing newlines, and that is exactly
// what made build-liq-5a70adc1 report a false "first difference at line 840" of an 839-line file.
const undone = body.split('\n')
  .filter(l => l !== PROBE)
  .map(l => (l === EDITED ? SITE : l))
  .join('\n');
if (undone !== raw) {
  const a = undone.split('\n'), b = rawLines;
  const first = a.findIndex((l, i) => l !== b[i]);
  throw new Error(`undoing the edit does not reproduce py2to3(raw) byte-for-byte ` +
                  `(first difference at line ${first + 1} of ${b.length}) — refusing`);
}

const out = body + OVERRIDE;
const file = path.join(OUT, `variants/0a7de9fa-${TAG}.py`);
fs.writeFileSync(file, out);

console.log(`[size] built variants/0a7de9fa-${TAG}.py  (epoch ${harness.config().epoch})`);
console.log(`[size] ONE edit at L${rawLines.indexOf(SITE) + 1}: head(200) -> iloc[200:400]`);
console.log('[size] + 1 instrumentation line (POOLDEPTH, log.error) immediately after it');
console.log('[size] kept verbatim: the 10-80亿 cap filter, the asc sort, the second head(80), '
          + 'the BBI band, the 2-name sizing, the risk overlay, the frozen cost block');
console.log('[size] undo (restore L190 + drop the probe) reproduces py2to3(raw) byte-for-byte');
console.log("[size] control = the champion's own epoch-9 row: objective 2.6282 / sharpe 7.07 / "
          + 'annual 276.82 / maxDD 14.00 (365 days)');
console.log('[size] PRE-REGISTERED, THREE BRANCHES:');
console.log('[size]   (a) annual >= 207.6% (75%) => 规模 does NOT explain this candidate');
console.log('[size]   (b) annual <  138.4% (50%) => 规模 reproduces on the champion');
console.log('[size]   (c) ANY rebalance with POOLDEPTH n < 400 => measurement INVALID, '
          + 'report as "could not run", never as "no effect"');
