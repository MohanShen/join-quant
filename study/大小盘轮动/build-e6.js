// Builds the epoch-6 baseline and one-change variants for the 大小盘轮动 round.
// Base = 2f5bc859 (四择时高息低价小市值和白马大市值轮动) — the family's only gate-passing member and the
// epoch-2 study base (study/大小盘轮动/baseline.py, old OVERRIDE). The epoch-2 round (q-2..q-7 + the
// archived single-strategy q-1) found the style vote a net drag; the size edge was never tested.
// Every variant = py2to3(source) + asserted edit(s) + the live OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-05-20_四择时高息低价小市值和白马大市值轮动-2f5bc859.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

// signal() computes three votes then writes g.signal. Forcing a leg returns before the votes are
// computed: the three strategy_*_signal functions write no g state, so skipping them changes
// nothing but run time.
const VOTES = '    s1_signal = strategy_one_signal(context)\n';
const force = leg => s => edit(s, VOTES, `    g.signal = '${leg}'  # style vote bypassed: always '${leg}'\n    return\n` + VOTES);

const SMALL_SORT = '\n            .order_by(valuation.market_cap.asc())\n        )\n        stocks = list(df.code)\n';
const DIV = 'stocks = get_dividend_ratio_filter_list(context, stocks, False, 0, g.dividend_ratio_1)';
const DAPAN = "    top_divergence, bottom_divergence = detect_divergences('399303.XSHE', context)\n";

const V = {};
Object.assign(V, {
  // edge test 风格轮动择时 (re-measure of the archived q-1 on epoch 6): hold the small sleeve always
  'u-1_always-small': force('small'),
  // what the other leg earns on its own
  'u-2_always-big': force('big'),
  // edge test 规模因子: same sleeve, same filters, but the LARGEST caps first
  'u-3_small-largest-first': s => edit(V['u-1_always-small'](s), SMALL_SORT,
    SMALL_SORT.replace('market_cap.asc()', 'market_cap.desc()')),
  // edge test 股息率: the LOWEST quarter of dividend yield (still a dividend payer, so 次新 stays excluded)
  'u-4_small-low-yield': s => edit(V['u-1_always-small'](s), DIV, DIV.replace('False, 0,', 'True, 0,')),
  // u-4 de-confound: yield = dividend / market cap, so the high-yield quarter leans small by
  // construction. Drop the dividend gate entirely — the pool can only get SMALLER — and make the
  // 次新 exclusion explicit, since the dividend record was what excluded them (q-6).
  'u-6_small-no-dividend-gate': s => edit(V['u-1_always-small'](s), DIV,
    'stocks = filter_new_stock(context, stocks)  # u-6: dividend gate removed, 次新 exclusion explicit'),
  // 低价: drop the <¥9 cap — like u-6 the pool can only get smaller, so a loss is price, not size
  'u-7_small-no-price-cap': s => edit(V['u-1_always-small'](s),
    '    stocks = filter_highprice_stock(context, stocks)\n', ''),
  // imp-3 (¥5) collapsed 2023: is ¥9 a knife-edge peak? The other shoulder.
  'u-8_small-price-cap-12': s => edit(V['u-1_always-small'](s),
    '    g.max_stock_price = 9 ', '    g.max_stock_price = 12'),
  // does dapan still earn on the always-small book? (epoch-2 q-2 measured it on the voting base)
  'u-5_always-small-no-dapan': s => edit(V['u-1_always-small'](s), DAPAN,
    DAPAN + '    top_divergence = False  # dapan off\n'),
});

// improve candidates -> enhance/candidates/ (filled in as the round measures the edge)
const CANDIDATES = {
  // imp-1 (edge 风格轮动择时 refuted, u-1): drop the vote, hold the small sleeve always
  'dxp-imp-1': V['u-1_always-small'],
  // imp-2 (edge 股息率 refuted, u-6): imp-1 without the dividend gate, 次新 exclusion explicit
  'dxp-imp-2': V['u-6_small-no-dividend-gate'],
  // imp-3 (edge 低价股效应, u-7): imp-1 with the price cap tightened ¥9 -> ¥5
  'dxp-imp-3': s => edit(V['u-1_always-small'](s),
    '    g.max_stock_price = 9 ', '    g.max_stock_price = 5 '),
};

const dir = __dirname;
fs.mkdirSync(path.join(dir, 'variants'), { recursive: true });
fs.writeFileSync(path.join(dir, 'baseline-e6.py'), src + OVERRIDE);
for (const [id, fn] of Object.entries(V)) fs.writeFileSync(path.join(dir, 'variants', `${id}.py`), fn(src) + OVERRIDE);
fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
for (const [id, fn] of Object.entries(CANDIDATES)) fs.writeFileSync(path.join(ROOT, 'enhance/candidates', `${id}.py`), fn(src) + OVERRIDE);
console.log('built baseline-e6 +', Object.keys(V).join(', '), '| candidates:', Object.keys(CANDIDATES).join(', '));
