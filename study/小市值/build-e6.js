// Builds the epoch-6 baseline and one-change variants for the 小市值 round.
// Base = 7a1c225f (小市值低开优化, hpkiller) — the family's best member and the epoch-2 study base.
// The epoch-2 study (q-1..q-3, study/小市值/baseline.py) called it "intraday scalping"; it is not:
// buys at 9:30:30 are T+1, so the 11:30 below-open exit and the 14:50 +5% take-profit only ever
// act on positions from a PREVIOUS day. Every variant = py2to3(source) + ONE asserted edit + OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-06-21_小市值低开优化-10年年化近100_回撤15-7a1c225f.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

const VARIANTS = {
  // edge test 规模: same machine on market-cap ranks 1001-2000 instead of the smallest 1000
  'q-1_next-1000': s => edit(s,
    "    stock_pool = df['code'].tolist()\n",
    "    stock_pool = df['code'].tolist()[1000:]  # q-1: skip the smallest 1000\n")
    .replace('    g.choice = 1000 ', '    g.choice = 2000 '),
  // edge test 低开反转: drop the gap-down entry condition (open < prev low and gap < -1%)
  'q-2_no-gap': s => edit(s,
    '    if not (today_open < prev_low and chg < -1):\n        return False\n',
    '    pass  # q-2: gap-down entry condition removed\n'),
  // exit component: the 11:30 "below today's open" liquidation of prior-day positions
  'q-3_no-below-open-exit': s => edit(s,
    "    run_daily(sell, time='11:30', reference_security='399303.XSHE')\n",
    "    pass  # q-3: 11:30 below-open exit off\n"),
  // calendar component: trade January and April too
  'q-4_no-avoid-months': s => edit(s,
    '    g.avoid_months = [1, 4] ',
    '    g.avoid_months = [] '),
  // q-3 follow-up: keep an 11:30 exit but drop its CONDITION — every sellable position leaves at
  // 11:30 (limit-down still blocks). Separates "a loss exit exists" from "below-open picks exits".
  'q-5_unconditional-exit': s => edit(s,
    '        if last_price < today_open:\n            close_position(stock)\n',
    '        if True:  # q-5: exit every sellable position, below-open condition removed\n            close_position(stock)\n'),
  // ridge width: the two entry knobs both peak at the author's value (imp-1..imp-4); near neighbours
  'q-6_choice-800': s => edit(s, '    g.choice = 1000 ', '    g.choice = 800  '),
  'q-7_choice-1200': s => edit(s, '    g.choice = 1000 ', '    g.choice = 1200 '),
  'q-8_gap-075': s => edit(s,
    '    if not (today_open < prev_low and chg < -1):\n',
    '    if not (today_open < prev_low and chg < -0.75):  # q-8\n'),
  // ranking layer: drop the bid1-money / market-cap sort, so candidates keep the preselect order
  // (market cap ascending) — i.e. rank by size alone
  'q-10_rank-by-size': s => edit(s,
    '    valid_stocks.sort(key=get_ratio, reverse=True)\n',
    '    pass  # q-10: bid1/mcap sort removed, preselect order (market cap asc) kept\n'),
  // The 2026-10-09 round, prompted by the JQ log (data/autostudy-logs/xsz-base-jqlog-full.txt):
  // JQ's tick b1_v is in SHARES, so `a1_p * a1_v * 100` overstates bid-1 money 100x and the
  // advertised "买一档金额 > 5万" gate really means "> 500". q-13 makes the gate mean what it says.
  'q-13_fix-bid-units': s => edit(s,
    '        money = a1_p * a1_v * 100\n',
    '        money = a1_p * a1_v  # q-13: b1_v is in shares, the *100 was a 100x overstatement\n'),
  // q-14: the same gate turned OFF, to measure what it contributes at its current (100x) threshold
  'q-14_no-liquidity-gate': s => edit(s,
    '        if money > 5e4:  ',
    '        if money > 0:  # q-14: liquidity gate off  '),
  // q-15: size each buy at the reserve the strategy's own cash gate implies (total*0.5/target_count)
  // instead of handing all available cash to however many candidates appeared (1 name = 100% book)
  'q-15_cap-position-size': s => edit(s,
    '    cash_per_stock = available_cash / len(final_buy_list)\n',
    '    cash_per_stock = min(available_cash / len(final_buy_list), total_value * 0.5 / g.target_count)  # q-15\n'),
  // Do the two measured edges survive the unit fix? Both were measured with the gate inert.
  // Controls for these two are q-13 (the corrected base), NOT baseline-e6.
  'q-16_fix-units-no-gap': s => VARIANTS['q-2_no-gap'](VARIANTS['q-13_fix-bid-units'](s)),
  'q-17_fix-units-next-1000': s => VARIANTS['q-1_next-1000'](VARIANTS['q-13_fix-bid-units'](s)),
  // q-18: the honest configuration — real liquidity gate + the position discipline §1 claims
  'q-18_fix-units-cap-size': s => VARIANTS['q-15_cap-position-size'](VARIANTS['q-13_fix-bid-units'](s)),
  // is q-10's gain structural or ridge luck? apply it at the two shoulders (controls: q-6, q-8)
  'q-11_rank-by-size-choice-800': s => VARIANTS['q-10_rank-by-size'](VARIANTS['q-6_choice-800'](s)),
  'q-12_rank-by-size-gap-075': s => VARIANTS['q-10_rank-by-size'](VARIANTS['q-8_gap-075'](s)),
  'q-9_gap-150': s => edit(s,
    '    if not (today_open < prev_low and chg < -1):\n',
    '    if not (today_open < prev_low and chg < -1.5):  # q-9\n'),
};

// improve candidates -> enhance/candidates/ (steered by the two measured edges)
const CANDIDATES = {
  // imp-1 (edge 规模): shrink the pool to the smallest 500
  'xsz-imp-1': s => edit(s,
    '    g.choice = 1000 ',
    '    g.choice = 500  '),
  // imp-2 (edge 低开反转): demand a deeper gap, -1% -> -2%
  'xsz-imp-2': s => edit(s,
    '    if not (today_open < prev_low and chg < -1):\n',
    '    if not (today_open < prev_low and chg < -2):  # imp-2\n'),
  // imp-3 (breadth, after imp-1): widen the pool to the smallest 1500
  'xsz-imp-3': s => edit(s,
    '    g.choice = 1000 ',
    '    g.choice = 1500 '),
  // imp-4 (breadth, after imp-2): loosen the gap threshold, -1% -> -0.5%
  'xsz-imp-4': s => edit(s,
    '    if not (today_open < prev_low and chg < -1):\n',
    '    if not (today_open < prev_low and chg < -0.5):  # imp-4\n'),
  // imp-5 (edge 规模, = q-10): rank the final candidates by market cap alone, not bid1-money / cap
  'xsz-imp-5': s => VARIANTS['q-10_rank-by-size'](s),
  // imp-6: imp-5 on the CORRECTED base (q-13). Control = q-13, not baseline-e6. This is the
  // candidate a next epoch would validate, since epoch 6's VAL for this family is already spent.
  'xsz-imp-6': s => VARIANTS['q-10_rank-by-size'](VARIANTS['q-13_fix-bid-units'](s)),
};

// q-1 must actually have changed g.choice (the .replace above is not asserted by edit())
if (!VARIANTS['q-1_next-1000'](src).includes('g.choice = 2000')) throw new Error('q-1: g.choice edit missed');

const dir = __dirname;
fs.mkdirSync(path.join(dir, 'variants'), { recursive: true });
fs.writeFileSync(path.join(dir, 'baseline-e6.py'), src + OVERRIDE);
for (const [id, fn] of Object.entries(VARIANTS)) {
  fs.writeFileSync(path.join(dir, 'variants', `${id}.py`), fn(src) + OVERRIDE);
}
fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
for (const [id, fn] of Object.entries(CANDIDATES)) {
  fs.writeFileSync(path.join(ROOT, 'enhance/candidates', `${id}.py`), fn(src) + OVERRIDE);
}
console.log('built baseline-e6 +', Object.keys(VARIANTS).join(', '), '| candidates:', Object.keys(CANDIDATES).join(', ') || 'none');
