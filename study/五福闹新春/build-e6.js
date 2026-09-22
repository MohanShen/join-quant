// Builds the epoch-6 baseline and one-change variants for the 五福闹新春 round.
// Every variant = py2to3(v5.2 source) with exactly ONE asserted edit, + the live OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-07-08_五福闹新春_v5_2-已解密_别再被13_10狙击了_快跑-17b3b439.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

const VARIANTS = {
  // edge test 动量: hold the WEAKEST positive-trend ETF that passes every filter
  'q-1_invert-rank': s => edit(s,
    "    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)\n",
    "    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=False)  # q-1: rank inverted\n"),
  // edge test 趋势择时: the A-share weak period never triggers
  'q-2_no-weak-switch': s => edit(s,
    '    weak_condition_met = (below_count >= 3)\n',
    '    weak_condition_met = (below_count >= 999)  # q-2: weak period disabled\n'),
  // hindsight check: normal-period universe = point-in-time dynamic pool only (no hand-picked fixed pool)
  'q-3_dynamic-only': s => edit(s,
    '    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))\n',
    '    merged = list(set(g.dynamic_etf_pool))  # q-3: hand-picked fixed pool dropped in normal period\n'),
  // control for q-e6-2: weak period holds the money-market ETF 511880 instead of the hand-picked overseas pool
  'q-4_weak-to-cash': s => edit(s,
    '        g.merged_etf_pool.sort()\n',
    '        g.merged_etf_pool = []  # q-4: weak period -> empty pool -> defensive 511880\n'),
};

// improve candidates -> enhance/candidates/
const CANDIDATES = {
  // idea-imp-1: wider normal-period hold band (ranking is uninformative, q-e6-1)
  'wufu-imp-1': s => edit(s, '    g.score_threshold_ratio = 0.9\n', '    g.score_threshold_ratio = 0.7  # imp-1\n'),
  // idea-imp-2: no forced 20-day exit — the breadth signal alone ends a weak period
  'wufu-imp-2': s => edit(s, '    g.max_weak_days = 20\n', '    g.max_weak_days = 999  # imp-2\n'),
  // idea-imp-2 on the cash control (q-e6-4), to check the change is on-mechanism, not on the overseas pool
  'wufu-imp-2c': s => edit(VARIANTS['q-4_weak-to-cash'](s), '    g.max_weak_days = 20\n', '    g.max_weak_days = 999  # imp-2\n'),
  // idea-imp-3: weak period enters on 2 of 4 indices below MA10 (was 3), base + cash control
  'wufu-imp-3': s => edit(s, '    weak_condition_met = (below_count >= 3)\n', '    weak_condition_met = (below_count >= 2)  # imp-3\n'),
  'wufu-imp-3c': s => edit(VARIANTS['q-4_weak-to-cash'](s), '    weak_condition_met = (below_count >= 3)\n', '    weak_condition_met = (below_count >= 2)  # imp-3\n'),
};
fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
for (const [id, fn] of Object.entries(CANDIDATES)) {
  fs.writeFileSync(path.join(ROOT, 'enhance/candidates', `${id}.py`), fn(src) + OVERRIDE);
}

const dir = __dirname;
fs.mkdirSync(path.join(dir, 'variants'), { recursive: true });
fs.writeFileSync(path.join(dir, 'baseline-e6.py'), src + OVERRIDE);
for (const [id, fn] of Object.entries(VARIANTS)) {
  fs.writeFileSync(path.join(dir, 'variants', `${id}.py`), fn(src) + OVERRIDE);
}
console.log('built baseline-e6 +', Object.keys(VARIANTS).join(', '));
