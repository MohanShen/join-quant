// Builds the epoch-6 baseline and one-change variants for the 网格 round.
// Base = 598050b9 (【网格交易策略-年化30%+】-网格大法好，熊市不用跑~). 32021d45 is the same file
// modulo two clone-header lines (epoch-2 q-dup), so the family holds ONE code body plus
// 9498d93f_多ETF网格交易 (sharpe −0.90). The source never calls set_slippage / set_commission /
// set_order_cost, so every epoch-4/6 pin lands on JQ defaults it already ran on; the epoch-4
// ledger row reproduces the epoch-2 digits (33.79 / 1.19 / 19.68). baseline-e6 is the anchor
// under the live OVERRIDE regardless — the ledger has no epoch-6 row for this family.
// Every variant = py2to3(source) + asserted edit(s) + the live OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-05-12_网格交易策略-年化30_-网格大法好_熊市不用跑-598050b9.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

// The file mixes tabs and spaces (handle_data's loop body is indented with "    \t"), so edits
// are matched on a unique substring of ONE line and the line's own indentation is preserved.
function editLine(s, needle, make) {
  const lines = s.split('\n');
  const hits = lines.map((l, i) => (l.includes(needle) ? i : -1)).filter(i => i >= 0);
  if (hits.length !== 1) throw new Error(`expected exactly 1 line containing ${JSON.stringify(needle)}, got ${hits.length}`);
  const i = hits[0];
  const indent = lines[i].match(/^[ \t]*/)[0];
  const out = make(indent, lines[i]);
  lines.splice(i, 1, ...(Array.isArray(out) ? out : [out]));
  return lines.join('\n');
}

// u-1 — edge test 均值回归: the ladder buys only after the price is ≥8% BELOW its first-sight
// anchor (rungs at −8/−16/−24/−32% to 4/7/9/10 units) and trims only ≥15% ABOVE it
// (+15/+30/+45/+60% to 6/3/1/0 units). Control: the same pool, quarterly rotation, index and
// per-stock stops, but a stock is bought ONCE at the ladder's entry size (4 units) when first
// seen (or when flat after a stop) and never added to or trimmed. What is left is the basket
// under the same stops; the difference is what the ladder's dip-buying/rip-selling earns.
const HOLD_FN = [
  '# u-1 control: entry rung only, no ladder (buy 4 units when flat, never add or trim)',
  'def hold_position(context,data,stock):',
  '    if g.initial_price[stock] == 0:',
  '        return',
  '    if context.portfolio.positions[stock].amount == 0 and context.portfolio.cash > 0:',
  '        order_target_value(stock, 4*(g.cash/40))',
  '',
];
const holdControl = s => editLine(
  editLine(
    editLine(s, "setup_position(context,data,stock,-0.08,'long')", ind => `${ind}hold_position(context,data,stock)  # u-1: ladder off`),
    "setup_position(context,data,stock,0.15,'short')", () => []),
  '# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次', (ind, line) => [...HOLD_FN, line]);

// u-2 — is the return the I64/I65 (互联网 / 软件) sector in the 2023-H1 AI rally, or the machine?
// Same rules on the author's own first commented-out pair C27 (医药制造) + C39 (计算机通信电子):
// two industries again, so the g.cash/40 ladder geometry and the 5-per-industry pick are unchanged.
const sectorSwap = s => editLine(s, "'I64','I65'", ind => `${ind}'C27','C39'  # u-2: sector swap (author's commented-out pair)`);

// u-3 — documented vs implemented: the comment says 取波动率最高 but s1[s1 < 6] takes the 5 LOWEST
// price-level variances (rank() ascending) among the top-30 by cap with pe<50. Flip to the
// documented intent: the 5 highest.
const topVariance = s => editLine(s, 'stocks = list(s1[s1 < 6].index)', ind => `${ind}stocks = list(s1[s1 > len(s1) - 5].index)  # u-3: top-5 variance (documented intent)`);

// imp-1 — on the baseline finding that 77% of variance is idiosyncratic (5 names, 2 codes):
// twice the names at half the unit. Same total ladder capacity per industry, spread thinner.
const diversify = s => editLine(
  editLine(s, 'stocks = list(s1[s1 < 6].index)', ind => `${ind}stocks = list(s1[s1 < 11].index)  # imp-1: 10 per industry`),
  'unit_value = g.cash/40', ind => `${ind}unit_value = g.cash/80  # imp-1: half the unit`);

// u-4 — u-1 follow-up, edge test 均值回归 by mirror: the same ladder geometry with the direction
// flipped. Buy rungs fire when the price is ≥8/16/24/32% ABOVE the anchor (4/7/9/10 units), trim
// rungs when it is ≥15/30/45/60% BELOW it (6/3/1/0 units). Eight comparisons and two call-site
// signs, one concept: "buy rips, sell dips". If the mirror ≥ the ladder, the information is not
// in the direction (any exposure-scaling ladder would do); if it collapses, it is.
const mirrorLadder = s => {
  const lines = s.split('\n');
  let start = lines.findIndex(l => l.startsWith('def setup_position(')), end = lines.findIndex((l, i) => i > start && l.startsWith('def '));
  if (start < 0 || end < 0) throw new Error('u-4: setup_position not found');
  let flipped = 0;
  for (let i = start; i < end; i++) {
    const before = lines[i];
    if (before.includes('returns > ')) lines[i] = before.replace('returns > ', 'returns < ');
    else if (before.includes('returns < ')) lines[i] = before.replace('returns < ', 'returns > ');
    if (lines[i] !== before) flipped++;
  }
  if (flipped !== 8) throw new Error(`u-4: expected 8 flipped comparisons, got ${flipped}`);
  let out = lines.join('\n');
  out = editLine(out, "setup_position(context,data,stock,-0.08,'long')", ind => `${ind}setup_position(context,data,stock,0.08,'long')  # u-4: mirror`);
  out = editLine(out, "setup_position(context,data,stock,0.15,'short')", ind => `${ind}setup_position(context,data,stock,-0.15,'short')  # u-4: mirror`);
  return out;
};

// u-5 — edge test 趋势择时 on the epoch-6 anchor itself (epoch-2 q-2 ran it on the same bench in
// fact; this removes the cross-epoch caveat for 1 JQ minute): index 2-day −3% liquidation off.
const noIndexStop = s => editLine(s, "if conduct_nday_stoploss(context, '000001.XSHG', 2,-0.03):", ind => `${ind}if False:  # u-5: index stop off`);

// u-3 follow-ups — variance() is the variance of the 180-day close PRICE LEVEL, which scales with
// price² × return variance, so "lowest 5" mixes two things. Split them, one line each, same
// ascending rank and the same s1 < 6 pick:
//   u-6: rank on the last close (pure nominal price, 低价股效应 reading)
//   u-7: rank on the 180-day std of daily log returns (pure realized volatility)
const VARLINE = 'variance_list.append(variance(stock))';
const lowPrice = s => editLine(s, VARLINE, ind => `${ind}variance_list.append(attribute_history(stock, 1, '1d', 'close', df=False)['close'][-1])  # u-6: rank on last close`);
const lowVol = s => editLine(s, VARLINE, ind => `${ind}variance_list.append(numpy.std(numpy.diff(numpy.log(attribute_history(stock, 180, '1d', 'close', df=False)['close']))))  # u-7: rank on 180d return vol`);

const V = {
  'u-1_hold-control': holdControl,
  'u-2_sector-swap': sectorSwap,
  'u-3_top-variance': topVariance,
  'u-4_mirror-ladder': mirrorLadder,
  'u-5_no-index-stop': noIndexStop,
  'u-6_low-price': lowPrice,
  'u-7_low-vol': lowVol,
};
// imp-2 / imp-3 — on-mechanism for the measured 均值回归 edge (u-1, u-4): rung spacing, one knob
// each. imp-2 tightens the buy rungs (−8/16/24/32% → −5/10/15/20%), imp-3 the sell rungs
// (+15/30/45/60% → +10/20/30/40%). Selection, stops and the unit are untouched.
const tightBuy = s => editLine(s, "setup_position(context,data,stock,-0.08,'long')", ind => `${ind}setup_position(context,data,stock,-0.05,'long')  # imp-2: buy rung -8% -> -5%`);
const tightSell = s => editLine(s, "setup_position(context,data,stock,0.15,'short')", ind => `${ind}setup_position(context,data,stock,0.10,'short')  # imp-3: sell rung +15% -> +10%`);
const CANDIDATES = { 'wg-imp-1': diversify, 'wg-imp-2': tightBuy, 'wg-imp-3': tightSell };

// no silent no-ops
for (const [id, fn] of Object.entries({ ...V, ...CANDIDATES })) {
  if (fn(src) === src) throw new Error(`${id}: variant is byte-identical to the source`);
}
if (holdControl(src).includes("setup_position(context,data,stock,0.15,'short')")) throw new Error('u-1: short ladder still present');

const dir = __dirname;
fs.mkdirSync(path.join(dir, 'variants'), { recursive: true });
fs.writeFileSync(path.join(dir, 'baseline-e6.py'), src + OVERRIDE);
for (const [id, fn] of Object.entries(V)) fs.writeFileSync(path.join(dir, 'variants', `${id}.py`), fn(src) + OVERRIDE);
fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
for (const [id, fn] of Object.entries(CANDIDATES)) fs.writeFileSync(path.join(ROOT, 'enhance/candidates', `${id}.py`), fn(src) + OVERRIDE);
console.log('built baseline-e6 +', Object.keys(V).join(', '), '| candidates:', Object.keys(CANDIDATES).join(', '));
