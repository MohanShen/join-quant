// q-e9-weak: re-test the family's ONLY measured edge (趋势择时) on the epoch-9 bench.
//
// ## Parent — the RAW book, rebuilt the build-e9-pit.js way
//
//   strategies/2026-07-08_五福闹新春_v5_2-已解密_别再被13_10狙击了_快跑-17b3b439.py
//   py2to3(src) + the LIVE OVERRIDE from require('../../utils/strategy-normalize')
//
// That is byte-for-byte what `strategy-normalize.js` submits for a ledger row (L347:
// `fs.writeFileSync(tmp, py2to3(src) + OVERRIDE)`), and py2to3 is a verified NO-OP on this
// source (sha256 unchanged), so the epoch-9 ledger row IS the control and no control run is
// needed:
//
//   annual 187.39 / sharpe 5.97 / maxDD 12.60 / objective 1.7479   (epoch 9, TRAIN 2024)
//
// ## The edit — one line, L816
//
//   weak_condition_met = (below_count >= 3)   ->   (below_count >= 999)
//
// in `check_a_share_weak_period`. The A-share weak period can then never trigger: the universe
// stays the normal-period merged pool (fixed + dynamic) all year, R² filtering stays ON, the MA
// filter stays OFF, the candidate coefficient stays 0.9. Identical single edit to the existing
// variants/q-2_no-weak-switch.py (built by build-e6.js, the 2022–23 run of this same test).
//
// ## Assertions (a failure voids the build; it is not interpreted)
//
//   1. parent sha256 pinned; py2to3 asserted a no-op; OVERRIDE verbatim at the tail.
//   2. exactly ONE changed line, it is L816, and the new literal is `>= 999`.
//   3. the OTHER weak-period knobs are byte-identical: max_weak_days 20,
//      weak_period_ma_lookback 10, score_threshold_ratio 0.9, r2_threshold 0.4,
//      holdings_num 1, defensive_etf 511880.
//   4. every `run_daily(` line byte-identical (the schedule must not move).
//   5. the three cost/pin markers present.
//   6. the daily census log line (L818 `【走弱期判断】低于MA10: n/4`) is UNCHANGED — the free
//      riders (weak-day census, longest consecutive run, 511880 days) are read off it, so an
//      edit that silenced it would void the harvest without failing the run.
//
//   node -e "require('./study/五福闹新春/build-e9-weak.js')" --dry
//   node -e "require('./study/五福闹新春/build-e9-weak.js')"

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const DIR = __dirname;
const ROOT = path.join(DIR, '../..');
const DRY = process.argv.includes('--dry');

const SRC = path.join(ROOT, 'strategies/2026-07-08_五福闹新春_v5_2-已解密_别再被13_10狙击了_快跑-17b3b439.py');
const SRC_SHA = 'b6884010b2e664f4480c20ab83f91a99e327433fe37bbc0bd7dae70ae173a349';
const OUT = path.join(DIR, 'variants', 'q-e9-weak_no-switch.py');

const EDIT_LINE = 816;
const FROM = 'weak_condition_met = (below_count >= 3)';
const TO = 'weak_condition_met = (below_count >= 999)';

// ── 1. parent identity ───────────────────────────────────────────────────────────────────────
const raw = fs.readFileSync(SRC, 'utf8');
const sha = crypto.createHash('sha256').update(raw).digest('hex');
console.log(`[weak] parent ${path.relative(ROOT, SRC)}`);
console.log(`[weak] parent sha256 ${sha}`);
if (sha !== SRC_SHA) throw new Error(`parent sha256 moved: expected ${SRC_SHA}`);

const body = py2to3(raw);
if (body !== raw) throw new Error('py2to3 is NOT a no-op on this source — the control row is no longer byte-comparable');
console.log('[weak] py2to3: verified NO-OP (source already py3) => ledger row 1.7479 is the exact control');
console.log(`[weak] active TRAIN window ${JSON.stringify(harness.window('train'))}  epoch ${harness.config().epoch}`);

for (const m of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!OVERRIDE.includes(m)) throw new Error(`live OVERRIDE missing cost/pin marker ${m}`);
}
console.log('[weak] live OVERRIDE carries all 3 cost/pin markers (avoid_future_data, order_volume_ratio, set_order_cost)');

// ── 2. the single edit ───────────────────────────────────────────────────────────────────────
const rl = body.split('\n');
if (rl[EDIT_LINE - 1].trim() !== FROM) {
  throw new Error(`L${EDIT_LINE} is not the weak-period trigger: ${rl[EDIT_LINE - 1]}`);
}
if (/^\s*#/.test(rl[EDIT_LINE - 1])) throw new Error(`L${EDIT_LINE} is commented out`);
if (body.split(FROM).length - 1 !== 1) throw new Error('trigger string is not unique in the source');

const ol = rl.slice();
ol[EDIT_LINE - 1] = rl[EDIT_LINE - 1].replace(FROM, TO) +
  '  # q-e9-weak: A 股走弱期永不触发（epoch-9 台上重测 趋势择时）';

const changed = rl.map((l, i) => [i + 1, l, ol[i]]).filter(([, a, b]) => a !== b);
if (changed.length !== 1) throw new Error(`expected exactly 1 changed line, got ${changed.length}`);
if (changed[0][0] !== EDIT_LINE) throw new Error(`changed line ${changed[0][0]} != ${EDIT_LINE}`);
if (!changed[0][2].includes(TO)) throw new Error('new literal wrong');
if (!changed[0][2].includes('q-e9-weak:')) throw new Error('changed line carries no marker');

// ── 3. the other weak-period knobs must be byte-identical ────────────────────────────────────
const KNOBS = [
  ['g.weak_period_ma_lookback = 10', 'MA lookback'],
  ['g.max_weak_days = 20', 'forced-exit cap (idea-imp-2 subject — must NOT move)'],
  ['g.holdings_num = 1', 'holdings'],
  ['g.defensive_etf = "511880.XSHG"', 'defensive ETF'],
  ['g.score_threshold_ratio = 0.9', 'candidate coefficient'],
  ['g.r2_threshold = 0.4', 'R² threshold'],
];
for (const [needle, desc] of KNOBS) {
  const a = rl.filter(l => l.includes(needle));
  const b = ol.filter(l => l.includes(needle));
  if (a.length !== 1) throw new Error(`knob not uniquely present in parent: ${needle} (${a.length})`);
  if (b.length !== 1 || a[0] !== b[0]) throw new Error(`knob changed but must not: ${needle}`);
  console.log(`[weak] byte-identical knob: ${a[0].trim()}   (${desc})`);
}

// ── 4. the run_daily schedule must not move ──────────────────────────────────────────────────
const sched = s => s.filter(l => l.includes('run_daily(')).join('\n');
if (sched(rl) !== sched(ol)) throw new Error('a run_daily line changed but must not');
console.log(`[weak] byte-identical: all ${rl.filter(l => l.includes('run_daily(')).length} run_daily lines`);

// ── 5. the census log line must survive (the free riders are read off it) ────────────────────
const CENSUS = '【走弱期判断】低于MA{g.weak_period_ma_lookback}: {below_count}/4';
const censusA = rl.filter(l => l.includes(CENSUS));
const censusB = ol.filter(l => l.includes(CENSUS));
if (censusA.length !== 1) throw new Error('daily census log line not found in parent — harvest would be impossible');
if (censusB.length !== 1 || censusA[0] !== censusB[0]) throw new Error('census log line changed but must not');
console.log(`[weak] byte-identical census line L${rl.indexOf(censusA[0]) + 1}: ${censusA[0].trim()}`);
console.log('[weak]   => the UNMODIFIED rule\'s below_count is still printed every day; the weak/normal');
console.log('[weak]      census, its longest consecutive run and the 511880 fallback count are free riders.');

// ── assemble + OVERRIDE ──────────────────────────────────────────────────────────────────────
const out0 = ol.join('\n') + OVERRIDE;
if (!out0.endsWith(OVERRIDE)) throw new Error('OVERRIDE block not verbatim at tail');
if (out0.length - (body.length + OVERRIDE.length) !== ol[EDIT_LINE - 1].length - rl[EDIT_LINE - 1].length) {
  throw new Error('byte delta does not match the single edited line');
}
console.log('[weak] byte-identical: frozen OVERRIDE cost block (tail, verbatim from strategy-normalize)');

// Corroboration: identical single edit to the 2022–23 run of this test.
const PRIOR = path.join(DIR, 'variants', 'q-2_no-weak-switch.py');
if (fs.existsSync(PRIOR)) {
  const prior = fs.readFileSync(PRIOR, 'utf8');
  const hit = prior.split('\n').filter(l => l.includes('below_count >= 999'));
  console.log(`[weak] prior (2022–23) run of this test used the same edit: ${hit.length === 1 ? hit[0].trim() : 'NOT FOUND'}`);
  if (hit.length !== 1) throw new Error('q-2_no-weak-switch.py does not carry the >= 999 edit — design mismatch');
}

const header = [
  '# ============================================================================',
  '# q-e9-weak 变体：A 股走弱期永不触发（epoch-9 台上重测本族唯一 measured 的 edge 趋势择时）',
  '#',
  `# 【父本】${path.relative(ROOT, SRC)}`,
  `#         sha256 ${SRC_SHA}`,
  '#         py2to3 已验证为恒等变换（sha256 不变）⇒ 账本行即精确对照，不跑对照：',
  '#         epoch-9 TRAIN 2024-01-01..2024-12-31：annual 187.39 / sharpe 5.97 /',
  '#         maxDD 12.60 / objective 1.7479',
  '#',
  `# 【唯一改动】L${EDIT_LINE}  check_a_share_weak_period:`,
  `#         ${FROM}  ->  ${TO}`,
  '#   走弱期从此永不触发：全年 universe 恒为正常期合并池（固定池+动态池），R² 过滤保持开启，',
  '#   MA 过滤保持关闭，候选系数保持 0.9。与 variants/q-2_no-weak-switch.py（2022–23 上同一测试）',
  '#   的改动逐字相同。',
  '#',
  '# 【构建期断言】父本 sha256、py2to3 恒等、OVERRIDE 逐字、唯一一行 diff、其余走弱期旋钮',
  '#   （max_weak_days 20 / weak_period_ma_lookback 10 / score_threshold_ratio 0.9 /',
  '#   r2_threshold 0.4 / holdings_num 1 / defensive_etf 511880）逐字不动、全部 run_daily 逐字',
  '#   不动、三个成本标记在位、逐日普查日志行逐字不动。',
  '#',
  '# 【预注册判读】2022–23 上关掉本闸值 −0.4796，占当时水平 0.3755 的 −128%。',
  '#   Δobj > −0.50（仍保留 ≥1.25，>71% 的水平）⇒ 在本台上不再主导，claim 必须重新界定范围；',
  '#   Δobj ≥ 0 ⇒ 直接证伪；大幅负 Δ ⇒ 在当下这张台上确认。',
  '#   免费 rider（从 JQ 日志取）：2024 逐日 weak/normal 普查（未改动规则的 below_count>=3 天数）、',
  '#   最长连续走弱天数（免费重测 idea-imp-2 的 20 日上限前提）、防御 511880 兜底天数。',
  '# ============================================================================',
  '',
].join('\n');

if (DRY) {
  console.log('[weak] --dry: nothing written');
} else {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, header + out0);
  console.log(`[weak] wrote ${path.relative(ROOT, OUT)}  (${(header + out0).length} bytes)`);
}

console.log('\n[weak] DIFF (parent -> variant), 1 line:');
console.log(`  -L${EDIT_LINE}  ${rl[EDIT_LINE - 1]}`);
console.log(`  +L${EDIT_LINE}  ${ol[EDIT_LINE - 1]}`);
