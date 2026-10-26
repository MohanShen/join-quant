// q-e9-champ-bbi-off — EDGE TEST for the proposed edge 中期趋势带 (BBI) on the 小市值 family's
// epoch-9 champion `strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py`
// (control: objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00, 365 days).
//
// ## What is being tested
//
// A free code audit found L243 contradicts its own comment one line above:
//
//   L242  # 收盘价在BBI上方，说明中期趋势向上          <- "close ABOVE BBI", a single-sided rule
//   L243  if bbi*0.9 < prev_close < bbi*1.3:          <- a BAND whose lower edge is 10% BELOW BBI
//
// So the implemented rule is not "trend is up" but "neither weak nor overheated". The proposed
// edge 中期趋势带 (BBI) claims that band is a SOURCE OF SELECTION inside the 80 smallest names of
// 399101, not decoration. This variant REMOVES the condition to find out.
//
// ## Insertion site — ONE line, and it is a REMOVAL
//
//   L243  `        if bbi*0.9 < prev_close < bbi*1.3:`  ->  `        if True:`
//
// Everything else is verbatim:
//   * the `len(stock_data) < 24` data-sufficiency guard (L228) STAYS, so a name with too little
//     history is still excluded — the pool's composition changes only by the band's absence;
//   * `candidate_list`'s ordering (L205, `market_cap.asc()` then `head(80)`) is untouched, and
//     `bbi_pass.append` still walks it in that order, so downstream ranking sees the same
//     sequence with more members;
//   * `bbi`, `prev_close` and the four moving averages are still computed (they feed L245's
//     log.debug), so the diff is the predicate alone.
//
// ⚠ This is NOT rank 33 (`imp-e9-bbi-doc`), which REPLACES the band with the documented
// single-sided `prev_close > bbi`. Opposite directions — one removes a filter, the other swaps a
// filter — and merging them would make the result uninterpretable (orchestrator ruling 4).
// Rank 33 stays unrun and is blocked on this result.
//
// ## Candidate counts come free — NO instrumentation was added
//
// The book already logs both sides of this filter on every rebalance:
//
//   L206  log.info(f"精选市值后数量: {len(candidate_list)}")            <- pool entering the filter
//   L247  log.info(f"BBI趋势过滤后最终选股数量: {len(bbi_pass)}")        <- pool leaving it
//
// and `init` sets `log.set_level('strategy', 'debug')` (L96), so both are in the 日志 tab and
// `utils/backtest-log.js` can read them. Adding a counter would have been a second edit for
// information the author already prints.
// ⚠ The CONTROL's leaving-count is also already measured, at zero extra cost: liq-1
// (`build-liq-0a7de9fa.js`) inserted its floor at `return bbi_pass`, so that run's
// `LIQFLOOR … in=` IS `len(bbi_pass)` under the unmodified band — 41 calls, cumIn 3116.
//
// ## Why the count matters for READING the delta
//
// If the band was already admitting nearly the whole 80-name pool, it was close to inert and a
// small Δ means "the filter never did much", NOT "the edge is real". That is a different
// conclusion from "the filter mattered and removing it cost nothing", and only the counts
// separate them. Report both.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;

const TAG = 'bbi-off';

// Line-exact, both directions. Matching whole lines (never substrings) is what keeps the undo
// assertion below a real check rather than a tautology.
const SITE = '        if bbi*0.9 < prev_close < bbi*1.3:';
const EDITED = '        if True:  # q-e9-champ-bbi-off: BBI band REMOVED (edge test) — ONLY change vs the raw book';

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /0a7de9fa/.test(f));
if (!src) throw new Error('0a7de9fa not found in strategies/');

// ⚠ The comparison baseline is py2to3(raw), NOT the on-disk file: the variant is built on the
// py2to3 output, which is also what the normalizer measured the control on.
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));

const hits = raw.split('\n').filter(l => l === SITE).length;
if (hits !== 1) throw new Error(`expected exactly 1 edit site, got ${hits}`);

// The data-sufficiency guard must survive the edit — it is named in the design and is what keeps
// the candidate set otherwise identical.
const GUARD = '        if len(stock_data) < 24:  # 确保有24天以上数据（满足最长周期计算）';
if (raw.split('\n').filter(l => l === GUARD).length !== 1) {
  throw new Error('the len(stock_data) < 24 guard is not where the design says it is — refusing');
}

const body = raw.split('\n').map(l => (l === SITE ? EDITED : l)).join('\n');

if (!body.includes(EDITED)) throw new Error('the edit did not land');
if (body.includes('bbi*0.9')) throw new Error('the band predicate survived the edit — refusing');
if (!body.includes(GUARD)) throw new Error('the 24-bar guard was lost — refusing');
// The two count log lines are the whole free read; a refactor upstream that dropped either one
// would leave the run uninterpretable, so assert on them rather than discovering it afterwards.
for (const need of ['f"精选市值后数量: {len(candidate_list)}"',
                    'f"BBI趋势过滤后最终选股数量: {len(bbi_pass)}"']) {
  if (!body.includes(need)) throw new Error(`missing count log line: ${need}`);
}

// ⚠⚠ The ONLY difference from py2to3(raw) must be the swapped line. Assert on `body` — the
// PRE-OVERRIDE text — never on a slice of the final file: cutting the output at a marker is
// ambiguous against the file's own trailing newlines, and that is exactly what made
// build-liq-5a70adc1 report a false "first difference at line 840" of an 839-line file.
const undone = body.split('\n').map(l => (l === EDITED ? SITE : l)).join('\n');
if (undone !== raw) {
  const a = undone.split('\n'), b = raw.split('\n');
  const first = a.findIndex((l, i) => l !== b[i]);
  throw new Error(`undoing the edit does not reproduce py2to3(raw) byte-for-byte ` +
                  `(first difference at line ${first + 1} of ${b.length}) — refusing`);
}

const out = body + OVERRIDE;
const file = path.join(OUT, `variants/0a7de9fa-${TAG}.py`);
fs.writeFileSync(file, out);

console.log(`[bbi] built variants/0a7de9fa-${TAG}.py  (epoch ${harness.config().epoch})`);
console.log(`[bbi] ONE edit: L${raw.split('\n').indexOf(SITE) + 1}  ${SITE.trim()}  ->  if True:`);
console.log('[bbi] kept verbatim: the len(stock_data) < 24 guard, candidate_list ordering, '
          + 'the BBI computation, both count log lines');
console.log('[bbi] undo reproduces py2to3(raw) byte-for-byte (pre-OVERRIDE comparison)');
console.log("[bbi] control = the champion's own epoch-9 row: objective 2.6282 / sharpe 7.07 / "
          + 'annual 276.82 / maxDD 14.00');
console.log('[bbi] PRE-REGISTERED FALSIFIER: annual >= 235.3% AND |sharpe - 7.07| <= 1.0 '
          + '=> the 中期趋势带 (BBI) edge proposal is REFUTED and WITHDRAWN');
