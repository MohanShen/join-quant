// Builds the epoch-6 baseline and one-change variants for the ETF动量 rebuild round.
// Base = 0aa4028d (追电ETF动量轮动): 25-day weighted log-regression slope x R2 over an 11-ETF
// cross-asset pool, hold the single top score if 0 < score <= 4.8, else cash; 10% stop.
// The pre-wipe study (baseline .. q-12) ran on 22152780, a 50/50 小市值 + ETF blend whose return
// was carried by the small-cap leg, so none of its deltas describe this family's own mechanism.
// Every variant = py2to3(source) with ONE asserted conceptual edit, + the live OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-06-15_追电ETF动量轮动_10年60多倍收益-0aa4028d.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

const SORT = "    df = pd.DataFrame({'score': scores}).sort_values('score', ascending=False)\n";
const GATE = "    df = df[(df['score'] > 0) & (df['score'] <= 4.8)]\n";

const VARIANTS = {
  // edge test 动量: hold the WEAKEST ETF that passes the 0 < score <= 4.8 filter
  'q-1_invert-rank': s => edit(s, SORT,
    "    df = pd.DataFrame({'score': scores}).sort_values('score', ascending=True)  # q-1: rank inverted\n"),
  // edge test 趋势择时 (absolute momentum): drop score > 0, always hold the top score (cap kept)
  'q-2_no-abs-gate': s => edit(s, GATE,
    "    df = df[(df['score'] <= 4.8)]  # q-2: absolute-momentum gate off\n"),
  // pool attribution: the same score/gate/stop on 0717871e's A-share-only 4-ETF pool
  'q-3_ashare-pool': s => edit(s,
    '        "513100.XSHG",  # 纳指ETF\n',
    '        "510300.XSHG", "510500.XSHG", "159915.XSHE", "159949.XSHE",  # q-3: A-share pool of 0717871e\n    ]\n    _q3_unused = [\n        "513100.XSHG",  # 纳指ETF\n'),
  // exit component: the -10% fixed stop
  'q-4_no-stop': s => edit(s,
    '    g.stop_loss = -0.10    # 止损线（-10%）\n',
    '    g.stop_loss = -9.0     # q-4: stop off\n'),
  // filter component: the "not extreme" upper cap 4.8
  'q-5_no-cap': s => edit(s, GATE,
    "    df = df[(df['score'] > 0)]  # q-5: upper cap off\n"),
  // (no q-6: the no-gate re-check of q-1 was dropped once q-2 measured the gate as inert)
  // score component: drop the R2 multiplier, rank on annualized weighted slope alone
  'q-7_no-r2': s => edit(s,
    '    return annual_ret * r2\n',
    '    return annual_ret  # q-7: R2 multiplier off\n'),
  // pool floor: hold every qualifying ETF equal-weight instead of the top one
  'q-8_hold-all': s => edit(s,
    '    g.max_hold  = 1        # 最大持仓数\n',
    '    g.max_hold  = 11       # q-8: hold every qualifying ETF\n'),
  // lookback sensitivity, the other side of imp-1 (50d collapsed): plateau or fitted point?
  'q-9_m20': s => edit(s,
    '    g.m_days    = 25       # 动量计算天数\n',
    '    g.m_days    = 20       # q-9: lookback sensitivity\n'),
};

const CANDIDATES = {
  // imp-1: slower momentum (25 -> 50 days), on-mechanism: the 2023 half is a whipsaw year
  'etfmom-e6-imp-1': s => edit(s,
    '    g.m_days    = 25       # 动量计算天数\n',
    '    g.m_days    = 50       # imp-1: slower momentum\n'),
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
