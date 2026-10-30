// q-e9-champ-liq-02fdafaa — liq-1 LIQUIDITY-FEASIBILITY FLOOR for the 小市值 family's NEW epoch-9
// champion `strategies/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa.py`
// (control: objective 3.0172 / sharpe 8.22 / annual 320.35 / maxDD 18.63, epoch 9, 365 days,
//  curve on disk; maxDD window 2024-05-07 -> 2024-06-24, 2024-01 return 0.00%).
//
// ⚠ The filename prefix is the FETCH date. This book was POSTED 2025-06-06.
//
// ## Why this run exists, and why it is not a ranked research idea
//
// This is the EXIT GATE's own requirement: `integrate-eligible` needs `realizability: >= 2` and
// UNKNOWN BLOCKS. 小市值's page carries a score evidenced on OTHER books (the 低开反转 scalping
// branch, and later 0a7de9fa / 5a70adc1), and realizability is a property of a BOOK — so the new
// champion's capacity is unmeasured. Capacity is also the one axis that cannot be read off source:
// 大小盘轮动's liq-1 removed ZERO names on 31/31 rebalances (curve bit-identical) while ETF溢价's
// took sharpe 8.44 -> 1.10. A measurement, not a prediction.
//
// ## FLOOR DERIVATION — from this book's own position size, nothing guessed
//
// SINGLE SLEEVE: the source has no `g.portfolio_value_proportion`, and `buy_security` (L500-521)
// sizes every position as `cash / target_num` with `target_num = g.stock_num` (L503) and
// `g.stock_num = 6` (L50). `adjust_stock_num` (L576) would return 3..6 dynamically but is NEVER
// CALLED — it is scheduled nowhere and referenced nowhere else — so 6 holds for the whole run
// (asserted below).
//
//   capital 1,000,000 / g.stock_num 6              = 166,666.67 CNY per full position
//   epoch 4 pins order_volume_ratio = 0.05, so filling one full position inside a SINGLE daily
//   bar needs that bar's traded value >= 166,666.67 / 0.05 = 3,333,333.33 CNY/day.
//
// liq-1 = 3.33e6 is the FILL-FEASIBILITY MINIMUM at the book's own size, not a comfort level.
// It is ~3x SMALLER than 0a7de9fa's 1e7 (that book holds 2 names, this one 6), so the a-priori
// expectation is that it bites LESS, not more. liq-2 (5x) / liq-3 (10x) are DECLARED here so the
// capacity curve cannot be fitted to taste later, but only liq-1 is BUILT and only liq-1 is run —
// feasibility first.
//
// ## Insertion site — ONE line
//
//   L137  `    return final_list`  ->  `    return filter_liquidity_floor(context, final_list)`
//
// That is the last line of `get_stock_list(context)` (L99-137), i.e. the names the book is about to
// buy, after 市值 / 新股 / 科创北交 / ST / 停牌 / 涨跌停 / 行业 screening and after the
// `final_list = stock_list[:g.stock_num*2]` truncation to 12 candidates. Both call sites are
// covered by the one edit — `weekly_adjustment` L149 and `check_remain_amount` L216 — so nothing
// the book buys escapes the floor. Only genuine candidates pay for 20 bars of `money`, and the
// floor cannot interact with any other screen's ordering.
//
// ## Why the floor sees 12 names and fills 6 slots
//
// `final_list` is 12 (= g.stock_num*2) and `buy_security` fills at most 6. So removing a name from
// the top 6 promotes name #7 — the disciplined manager who DECLINES a name he cannot fill and
// takes the next one. `slots = min(6, n_out)` is logged per call precisely because that promotion
// can run out: if n_out < 6 the book is STARVED and the delta mixes holdings thinning with name
// quality. That distinction must be visible, never inferred.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;

const CAP = harness.config().costs.capital;
const RATIO = harness.config().costs.orderVolumeRatio;
const NAMES = 6;                                  // g.stock_num, L50, read off the source
const PER_POSITION = CAP / NAMES;
const BASE_FLOOR = PER_POSITION / RATIO;          // 3.33e6

// Declared up front; only liq-1 is built. liq-2/liq-3 are the capacity CURVE, a different question.
const FLOORS = { 'liq-1': 1, 'liq-2': 5, 'liq-3': 10 };   // multiples of the feasibility minimum
const BUILD = ['liq-1'];

const SITE = '    return final_list';
const INSERTED = '    return filter_liquidity_floor(context, final_list)  # liq: ONLY change vs the raw book';

// ⚠ Guard on the CODE side of a line only, never the whole line: THREE builders in this family
// have already refused a CORRECT build by matching their own explanatory comment
// (build-siblings' stray-`*100`, build-universe's MARKET_INDEX count, build-liq-5a70adc1's
// trailing-newline slice). `codeOf` strips any trailing `#` comment before comparing.
const codeOf = (l) => {
  const i = l.indexOf('#');
  return (i === -1 ? l : l.slice(0, i)).trimEnd();
};

const helper = mult => {
  const floor = BASE_FLOOR * mult;
  return `

# ---------------- liquidity floor (realizability measurement, epoch ${harness.config().epoch}) ----------------
# Derivation, entirely from this book's own position size:
#   capital ${CAP} / g.stock_num (=${NAMES}, L50) = ${PER_POSITION.toFixed(2)} CNY per full position
#   epoch 4 pins order_volume_ratio = ${RATIO}, so filling one full position inside a SINGLE daily
#   bar requires that bar's traded value >= ${PER_POSITION.toFixed(2)} / ${RATIO} = ${BASE_FLOOR.toFixed(2)} CNY/day.
# ${mult === 1 ? 'This is the FILL-FEASIBILITY MINIMUM for this book, not a comfort level.'
              : `This is ${mult}x that minimum (capacity headroom).`}
LIQ_FLOOR_MULT = ${mult}
LIQ_FLOOR = LIQ_FLOOR_MULT * (${CAP}.0 / ${NAMES} / ${RATIO})

# Cumulative counters, so the LAST LIQFLOOR line is SELF-SUFFICIENT: the 日志 tab serves 100 lines
# per request and this book is chatty, so a reader may never reach every per-call line. The
# per-call line is still emitted — the count of calls where in > out, and the per-call slots, are
# the whole point of this measurement and must not be inferred from a total.
LIQ_STATS = {'calls': 0, 'cut': 0, 'n_in': 0, 'n_out': 0, 'err': 0,
             'short': 0, 'min_slots': ${NAMES}}

def filter_liquidity_floor(context, stock_list):
    """Keep names whose TRAILING-20-BAR MEDIAN daily \`money\` is >= LIQ_FLOOR.

    Median, not mean: one spike day must not admit a normally-illiquid name.
    Evaluated at context.previous_date, so the bar being traded today is NEVER consulted — the
    floor is a point-in-time feasibility screen, not a lookahead.
    Emits one LIQFLOOR line per call via log.error, so it survives log.set_level.
    """
    stock_list = list(stock_list)
    n_in = len(stock_list)
    LIQ_STATS['calls'] += 1
    LIQ_STATS['n_in'] += n_in
    if n_in == 0:
        LIQ_STATS['short'] += 1
        LIQ_STATS['min_slots'] = 0
        log.error('LIQFLOOR floor=%.0f date=%s in=0 out=0 removedFrac=NA slots=0 cumCalls=%d cumCut=%d cumShort=%d minSlots=%d'
                  % (LIQ_FLOOR, str(context.previous_date), LIQ_STATS['calls'],
                     LIQ_STATS['cut'], LIQ_STATS['short'], LIQ_STATS['min_slots']))
        return []
    try:
        df = get_price(stock_list, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        keep = [s for s in stock_list if (s in med.index) and (med[s] >= LIQ_FLOOR)]
    except Exception as e:
        # Loud, never silent: a swallowed failure reproduces the baseline exactly and is
        # indistinguishable from "the floor did nothing" — which is the one answer that must be
        # trustworthy, since that is what 大小盘轮动's liq-1 actually found.
        LIQ_STATS['err'] += 1
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s cumErr=%d'
                  % (LIQ_FLOOR, n_in, str(e), LIQ_STATS['err']))
        return stock_list
    n_out = len(keep)
    LIQ_STATS['n_out'] += n_out
    if n_out < n_in:
        LIQ_STATS['cut'] += 1
    slots = min(${NAMES}, n_out)
    if slots < ${NAMES}:
        LIQ_STATS['short'] += 1
    if slots < LIQ_STATS['min_slots']:
        LIQ_STATS['min_slots'] = slots
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d cumCalls=%d cumCut=%d cumIn=%d cumOut=%d cumShort=%d minSlots=%d cumErr=%d'
              % (LIQ_FLOOR, str(context.previous_date), n_in, n_out,
                 1.0 - float(n_out) / float(n_in), slots,
                 LIQ_STATS['calls'], LIQ_STATS['cut'], LIQ_STATS['n_in'], LIQ_STATS['n_out'],
                 LIQ_STATS['short'], LIQ_STATS['min_slots'], LIQ_STATS['err']))
    return keep
`;
};

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /02fdafaa/.test(f));
if (!src) throw new Error('02fdafaa not found in strategies/');

// ⚠ The comparison baseline is py2to3(raw), NOT the on-disk file: the variant is built on the
// py2to3 output, which is also what the normalizer measured the control on.
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));
const lines = raw.split('\n');

const hits = lines.filter(l => l === SITE).length;
if (hits !== 1) throw new Error(`expected exactly 1 insertion site, got ${hits}`);

// Every premise of the floor derivation, asserted on the CODE side of its own line.
const ANCHORS = [
  '    g.stock_num = 6',                            // the divisor; if this moves, the floor is wrong
  '    final_list = stock_list[:g.stock_num*2]',    // the 12 candidates the floor sees
  '    target_num = g.stock_num',                   // buy_security's slot count (L503)
  '        g.target_list = get_stock_list(context)',// call site 1 (weekly_adjustment)
  '            target_list = get_stock_list(context)', // call site 2 (check_remain_amount)
];
for (const a of ANCHORS) {
  const n = lines.filter(l => codeOf(l) === a).length;
  if (n !== 1) throw new Error(`anchor not where the design says it is (${n} matches): ${a}`);
}
// `adjust_stock_num` would make g.stock_num dynamic (3..6) and invalidate the divisor. It must
// appear ONCE — its own `def` — and never as a call.
const adjHits = lines.filter(l => /adjust_stock_num/.test(codeOf(l)));
if (adjHits.length !== 1 || !/^def adjust_stock_num\(context\):$/.test(codeOf(adjHits[0]))) {
  throw new Error(`adjust_stock_num is referenced ${adjHits.length} time(s); the floor's divisor `
                + 'assumes g.stock_num is the constant 6 — refusing');
}
// Single sleeve: a proportion split would change the per-position size.
if (/portfolio_value_proportion/.test(raw)) {
  throw new Error('the book declares a portfolio_value_proportion split; the floor derivation '
                + 'assumes a single sleeve — refusing');
}
if (/filter_liquidity_floor/.test(raw)) {
  throw new Error('the raw book already defines filter_liquidity_floor — refusing');
}

const built = [];
for (const tag of BUILD) {
  const mult = FLOORS[tag];
  // Line-exact replacement: `    return final_list` must not match a longer line by substring.
  const body = lines.map(l => (l === SITE ? INSERTED : l)).join('\n');
  if (!body.split('\n').some(l => codeOf(l) === '    return filter_liquidity_floor(context, final_list)')) {
    throw new Error(`${tag}: the call site is missing`);
  }
  if (body.split('\n').some(l => l === SITE)) {
    throw new Error(`${tag}: an unfloored \`return final_list\` survived the edit — refusing`);
  }
  // ⚠⚠ The ONLY difference from py2to3(raw) must be the swapped line. Assert on `body` — the
  // PRE-OVERRIDE text — never on a slice of the final file: cutting the output at the helper's
  // marker is ambiguous against the file's own trailing newlines (the helper opens "\n\n#" and the
  // body already ends in a newline), and that is exactly what made build-liq-5a70adc1 report a
  // false "first difference at line 840" of an 839-line file.
  const undone = body.split('\n').map(l => (l === INSERTED ? SITE : l)).join('\n');
  if (undone !== raw) {
    const a = undone.split('\n'), b = raw.split('\n');
    const first = a.findIndex((l, i) => l !== b[i]);
    throw new Error(`${tag}: undoing the edit does not reproduce py2to3(raw) byte-for-byte `
                  + `(first difference at line ${first + 1} of ${b.length}) — refusing`);
  }
  const out = body + helper(mult) + OVERRIDE;
  fs.writeFileSync(path.join(OUT, `variants/02fdafaa-${tag}.py`), out);
  built.push(`variants/02fdafaa-${tag}.py (floor ${(BASE_FLOOR * mult).toFixed(2)})`);
}

console.log('[liq] built:', built.join(', '));
console.log(`[liq] ONE edit: L${lines.indexOf(SITE) + 1}  ${SITE.trim()}  ->  `
          + 'return filter_liquidity_floor(context, final_list)');
console.log(`[liq] derivation: capital ${CAP} / ${NAMES} names = ${PER_POSITION.toFixed(2)} per position; `
          + `/ order_volume_ratio ${RATIO} = ${BASE_FLOOR.toFixed(2)} CNY/day`);
console.log('[liq] FLOORS declared: '
          + Object.entries(FLOORS).map(([k, m]) => `${k}=${(BASE_FLOOR * m).toFixed(0)} (${m}x)`).join(' '));
console.log('[liq] QUEUE liq-1 ONLY — it answers feasibility. liq-2/liq-3 are the capacity curve.');
console.log('[liq] undo reproduces py2to3(raw) byte-for-byte (pre-OVERRIDE comparison)');
console.log("[liq] control = the NEW champion's epoch-9 row: objective 3.0172 / sharpe 8.22 / "
          + 'annual 320.35 / maxDD 18.63 (maxDD window 2024-05-07 -> 2024-06-24, 2024-01 = 0.00%)');
console.log('[liq] PRE-REGISTERED: (a) 0 removed AND bit-identical => R>=2, ceiling unmeasured; '
          + '(b) removed but objective clears the 1.0 gate => R=2; '
          + '(c) removed AND (sharpe < 1.0 or objective < 1.5) => R=1 for this book.');
console.log(`[liq] REPORT: count of LIQFLOOR lines with in > out (cumCut), and slots= per call `
          + `(cumShort / minSlots flag starvation below ${NAMES}).`);
