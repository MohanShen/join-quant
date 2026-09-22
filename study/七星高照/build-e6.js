// Builds the epoch-6 baseline and one-change variants for the 七星高照 round.
// Base = 19ca0e69 (七星高照 V1.7, the pure 7-ETF rotation). The epoch-2 study (q-1..q-5) ran on
// 406a1e4d, a 50/50 小市值 + 七星 blend, so none of its deltas describe this family's own leg.
// Every variant = py2to3(V1.7 source) with ONE asserted conceptual edit, + the live OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-05-23_策略变身_七星高照ETF轮动策略V1_7成功变身-19ca0e69.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

const VARIANTS = {
  // edge test 动量: hold the WEAKEST ETF that passes every filter
  'q-1_invert-rank': s => edit(s,
    "    etf_metrics.sort(key=lambda x: x['score'], reverse=True)\n",
    "    etf_metrics.sort(key=lambda x: x['score'], reverse=False)  # q-1: rank inverted\n"),
  // edge test 趋势择时: no positive-trend requirement (score > 0 and 10-day return > 0 both off)
  'q-2_no-trend-gate': s => edit(edit(s,
    '    g.min_score_threshold = 0          # 最低得分\n',
    '    g.min_score_threshold = -1e9       # q-2: trend gate off\n'),
    '    g.use_short_momentum_filter = True\n',
    '    g.use_short_momentum_filter = False  # q-2: trend gate off\n'),
  // concentration: hold every ETF that passes the filters, equal weight, instead of the top one
  'q-3_hold-all': s => edit(s,
    '    g.holdings_num = 1                 # 候选数量\n',
    '    g.holdings_num = 7                 # q-3: hold every qualifying ETF\n'),
  // exit component: the 5%-off-yesterday's-high profit protection
  'q-4_no-profit-protection': s => edit(s,
    '    g.enable_profit_protection = True                      # 盈利保护开关\n',
    '    g.enable_profit_protection = False                     # q-4\n'),
  // exit component: the "any of the last 3 days fell >3%" exclusion
  'q-5_no-loss-filter': s => edit(s,
    '    g.loss = 0.97                      # 近3日单日跌幅阈值（排除）\n',
    '    g.loss = 0.0                       # q-5: 3-day loss filter off\n'),
  // split of q-2's gate: only the 25-day score > 0 requirement off
  'q-6_no-score-gate': s => edit(s,
    '    g.min_score_threshold = 0          # 最低得分\n',
    '    g.min_score_threshold = -1e9       # q-6: score gate off\n'),
  // split of q-2's gate: only the 10-day return > 0 filter off
  'q-7_no-short-filter': s => edit(s,
    '    g.use_short_momentum_filter = True\n',
    '    g.use_short_momentum_filter = False  # q-7: short-momentum filter off\n'),
  // edge 动量 re-check on the no-gate book (q-2 + inverted rank; control = q-2)
  'q-8_invert-no-gate': s => VARIANTS['q-1_invert-rank'](VARIANTS['q-2_no-trend-gate'](s)),
};

// improve candidates -> enhance/candidates/ (added after the understand round)
const CANDIDATES = {
  // imp-1: drop the 10-day short-momentum filter (= q-7, the whole of q-2's effect)
  'qixing-imp-1': s => VARIANTS['q-7_no-short-filter'](s),
  // imp-2: keep the filter but slow it to 20 days, so it bites only on a real downswing
  'qixing-imp-2': s => edit(s,
    '    g.short_lookback_days = 10\n',
    '    g.short_lookback_days = 20  # imp-2\n'),
  // imp-3: imp-1 + profit protection off (both filters eject the top pick; do they stack?)
  'qixing-imp-3': s => VARIANTS['q-4_no-profit-protection'](VARIANTS['q-7_no-short-filter'](s)),
};

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
