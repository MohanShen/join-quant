// Builds the epoch-6 baseline and one-change variants for the PT多策略 round.
// Base = fa0d3bd9 (P-T多策略并行实战：用"自有账本"实现四大策略各安其位). Despite the title, the
// backtested code is ONE sleeve: every ETF whose previous-day turnover (money) sits in 5e6..2e7,
// premium = day_open/NAV − 1 at 09:25, keep premium < 0, take the 10 deepest discounts weighted by
// |premium|, trade at 09:30, sell anything that left the set. The other member c70281d3 is the same
// sleeve (last_price at 09:30 instead of day_open, plus a −5%/+10% stop) followed by 4,200 lines of
// "分仓隔离插件" that sit inside a module-level ''' … ''' string (lines 143–4355) and never run.
// The source sets fund costs and 0.1% slippage itself; the OVERRIDE pins both. It never sets
// order_volume_ratio, so the epoch-4 5% participation cap is the pin that bites (ledger: epoch 2
// annual 369.07 -> epoch 4 195.74 on the same file).
// Every variant = py2to3(source) + asserted edit(s) + the live OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-06-23_P-T多策略并行实战_用_quot_自有账本_quot_实现四大策略各安其位-fa0d3bd9.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

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

const BAND = "df = df[(df['money'] < 2e7) & (df['money'] > 5e6)]";
const PREMIUM = "df['premium'] = (df['open_price'] / df['unit_net_value'] - 1) * 100";
const SORT = "df = df.sort_values(['premium'], ascending=True)";
const FILTER = "df = df[df['premium'] < 0]";
const TOPN = 'selected_funds = df.head(10)';
const WEIGHTS = "weights = selected_funds['premium'].abs().tolist()  # 取绝对值计算权重";

// u-1 — edge test 流动性溢价, arm (a): the same rule on LIQUID funds (previous-day money 5e7..1e8).
// The pre-wipe epoch-2 q-1 measured this arm at obj 0.0535 / sharpe 1.09 (DQ) with no participation
// cap; epoch 6 caps fills at 5% of bar volume, which is exactly the thing the claim is about.
const bandLiquid = s => editLine(s, BAND, ind => `${ind}df = df[(df['money'] < 1e8) & (df['money'] > 5e7)]  # u-1: liquid band`);

// u-2 — arm (b): drop the 2e7 ceiling, keep the 5e6 floor (liquid funds may now crowd the top-10).
const bandNoCap = s => editLine(s, BAND, ind => `${ind}df = df[df['money'] > 5e6]  # u-2: no ceiling`);

// u-3 — edge test 均值回归 (of the NAV discount) by mirror: same band, same weighting, but keep
// premium > 0 and take the 10 LARGEST premiums (buy what trades furthest ABOVE NAV). If the mirror
// also earns, the information is not in the sign of the discount.
const mirrorPremium = s => editLine(
  editLine(s, SORT, ind => `${ind}df = df.sort_values(['premium'], ascending=False)  # u-3: mirror`),
  FILTER, ind => `${ind}df = df[df['premium'] > 0]  # u-3: mirror (premium > 0)`);

// u-4 — universe-only control: same band, NO NAV information. premium is replaced by a rank on
// thinness (−1e7/money: thinner = more negative = first), so the filter passes everything and the
// book holds the 10 thinnest names in the band, EQUAL weight. What is left is "hold thin ETFs";
// the difference to the base is what the discount signal earns on top of the universe.
const universeControl = s => editLine(
  editLine(s, PREMIUM, ind => `${ind}df['premium'] = -1e7 / df['money']  # u-4: no NAV info, thinnest first`),
  WEIGHTS, ind => `${ind}weights = [1.0] * len(order_fund)  # u-4: equal weight`);

// u-5 — weighting: |premium| → equal weight, everything else as the base (pre-wipe §4 gap).
const equalWeight = s => editLine(s, WEIGHTS, ind => `${ind}weights = [1.0] * len(order_fund)  # u-5: equal weight`);

// pt-imp-1 — on-mechanism for 流动性溢价 in the REALIZABLE direction: raise the floor 5e6 → 1e7,
// keep the 2e7 ceiling. ETF溢价 q-1 found its 2e6 share-volume floor too loose (1e7: obj +0.47,
// maxDD halved). Here the analogue is dropping the thinnest half of the band.
const floor1e7 = s => editLine(s, BAND, ind => `${ind}df = df[(df['money'] < 2e7) & (df['money'] > 1e7)]  # pt-imp-1: floor 1e7`);

// pt-imp-2 — concentration: top-10 → top-5. The author widened 5 → 10 "以求能够尽可能多地成交";
// ETF溢价 q-2 found obj peaks at N=2 and maxDD is lowest at N=5.
const top5 = s => editLine(s, TOPN, ind => `${ind}selected_funds = df.head(5)  # pt-imp-2: top-5`);

// u-7 — realizability: the signal is the 09:25 auction open; the base fills at 09:30 (daily mode:
// the open price) at up to 5% of the DAY's volume. Move execution (sells and buys) to 14:50 so the
// fill is the close: what is left is the part of the open-vs-NAV gap that survives past the auction,
// i.e. what an account that cannot take the auction print could actually collect.
const EXEC = "run_daily(market_open, '09:30', reference_security='000300.XSHG')";
const exec1450 = s => editLine(s, EXEC, ind => `${ind}run_daily(market_open, '14:50', reference_security='000300.XSHG')  # u-7: execute at 14:50`);

const V = {
  'u-1_band-liquid': bandLiquid,
  'u-2_band-nocap': bandNoCap,
  'u-3_mirror-premium': mirrorPremium,
  'u-4_universe-control': universeControl,
  'u-5_equal-weight': equalWeight,
  'u-7_exec-1450': exec1450,
};
const CANDIDATES = { 'pt-imp-1': floor1e7, 'pt-imp-2': top5 };

for (const [id, fn] of Object.entries({ ...V, ...CANDIDATES })) {
  if (fn(src) === src) throw new Error(`${id}: variant is byte-identical to the source`);
}
if (!src.includes(BAND) || !src.includes(PREMIUM) || !src.includes(WEIGHTS)) throw new Error('anchor lines not found');

const dir = __dirname;
fs.mkdirSync(path.join(dir, 'variants'), { recursive: true });
fs.writeFileSync(path.join(dir, 'baseline-e6.py'), src + OVERRIDE);
for (const [id, fn] of Object.entries(V)) fs.writeFileSync(path.join(dir, 'variants', `${id}.py`), fn(src) + OVERRIDE);
fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
for (const [id, fn] of Object.entries(CANDIDATES)) fs.writeFileSync(path.join(ROOT, 'enhance/candidates', `${id}.py`), fn(src) + OVERRIDE);
console.log('built baseline-e6 +', Object.keys(V).join(', '), '| candidates:', Object.keys(CANDIDATES).join(', '));
