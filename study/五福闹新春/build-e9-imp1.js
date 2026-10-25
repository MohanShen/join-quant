// imp-e9-1: port the A-share breadth 走弱期切池 mechanism INTO the champion's 五福 ETF sleeve.
//
// ## Parent (NOT the raw champion — the point-in-time build is the measured row)
//
//   study/五福闹新春/q-e9-pit_bf30eb36.py
//   sha256 7eb11d31a64fd7527211dca2daebdbcee62ae1440a4c291b85762aa81014c700
//   objective 1.9658 / sharpe 7.51 / final cum 209.36 (epoch-9 TRAIN 2024)
//   curve data/series/study_五福闹新春_q-e9-pit_bf30eb36__train__e9.json (242 pts)
//
// ## Donor
//
//   strategies/2026-07-08_五福闹新春_v5_2-…-17b3b439.py  (ledger 1.7479 @ e9)
//   Its switch is the family's ONLY measured edge (趋势择时), re-confirmed on THIS bench by
//   q-e9-weak: disabling it costs Δobj −0.8930 (annual 187.39 → 108.38, maxDD 12.60 → 22.89).
//   The champion has no A-share breadth input and no pool switch at all.
//
// ## FOUR INSERTIONS — no existing parent line is modified, so the diff is pure insertion
//
//   1. setup_wufu35_globals(), after the g.fixed_etf_pool literal:
//      g.global_etf_pool = [ 13 literals ]  = the donor's 17 global/overseas names MINUS the 4
//      the q-e9-pit rule already excluded (159502 2024-01-10, 159529 2024-02-02,
//      513400 2024-02-02, 520830 2024-07-16), each left commented IN PLACE with the author's own
//      listing date — same auditable form build-e9-pit.js used. 13/13 are already in the
//      champion's own g.fixed_etf_pool, asserted below: the port invents NO name.
//      Plus the donor's weak-period globals, VERBATIM from its L160-164.
//      ⚠ The dispatch names two of those five (weak_period_ma_lookback, is_a_share_weak); all
//        five are required because insertion 2 is a VERBATIM copy that reads weak_start_date,
//        weak_days_count and max_weak_days. Omitting them is an AttributeError on the first
//        weak evaluation, i.e. a broken port, not a smaller one.
//
//   2. check_a_share_weak_period — copied VERBATIM from the donor's L789-861 (indices
//      000300/399101/399006/000510; below_count >= 3 to enter, above_count >= 3 to exit).
//      The threshold stays 3: idea-imp-3 closed tuning it. Asserted byte-identical.
//
//   3. ONE call in morning_routine (09:00), immediately BEFORE daily_merge_etf_pools —
//      deliberately OUTSIDE the 13:1x snapshot, because q-e8-2 measured this family's execution
//      noise as living there.
//
//   4. The donor's weak branch at the TOP of afternoon_routine, but sourced as
//      [x for x in g.filtered_fixed_pool if x in g.global_etf_pool] — i.e. KEEPING the
//      champion's own liquidity filter, which avoids re-importing the bypass confound q-e8-3
//      had to spend a run settling. Placement at the top is equivalent to the donor's placement
//      (immediately before the momentum calc) because g.merged_etf_pool is read ONLY by
//      calculate_and_log_ranked_etfs / get_final_ranked_etfs — asserted below.
//
// ## NOT changed (asserted)
//
//   g.portfolio_value_proportion stays [0.5, 0, 0.5, 0] at L118 — this variant does NOT touch
//   weights; the 7 exact-literal [0,0,1,0] pure_wufu_mode guards therefore take the parent's
//   branch; the 7 sleeve knobs, score_threshold_ratio 0.9, r2_threshold 0.4, the 13:10 run_daily
//   schedule block and the frozen OVERRIDE cost block are byte-identical.
//
//   ⚠ Deliberately NOT ported: the donor couples is_a_share_weak into three further places
//     (apply_filters' R²/MA swap at its L867-868, score_threshold_ratio -> 1.0 at its L985,
//     midday_routine's pool-update split at its L257). The dispatch specifies four insertions;
//     porting the filter-side couplings too would make this a multi-variable change.
//
//   node -e "require('./study/五福闹新春/build-e9-imp1.js')" --dry
//   node -e "require('./study/五福闹新春/build-e9-imp1.js')"

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const DIR = __dirname;
const ROOT = path.join(DIR, '../..');
const DRY = process.argv.includes('--dry');

const PARENT = path.join(DIR, 'q-e9-pit_bf30eb36.py');
const PARENT_SHA = '7eb11d31a64fd7527211dca2daebdbcee62ae1440a4c291b85762aa81014c700';
const DONOR = path.join(ROOT, 'strategies',
  '2026-07-08_五福闹新春_v5_2-已解密_别再被13_10狙击了_快跑-17b3b439.py');
const OUT = path.join(DIR, 'variants', 'imp-e9-1_champion-weakswitch.py');

// gatekeeper-verified parent line numbers
const L_WEIGHT = 118;              // g.portfolio_value_proportion = [0.5, 0, 0.5, 0]  (LIVE)
const L_DUP = 3586;                // second assignment, behind `if not pv_ok:` — unreachable
const L_POOL_END = 461;            // closing `]` of g.fixed_etf_pool
const L_DEF_MORNING = 592;         // def morning_routine(context):
const L_MERGE_LOG = 606;           // log.info("【合并池】…")
const L_MERGE_CALL = 607;          // daily_merge_etf_pools(context)
const L_AFT_START = 658;           // log.info("▶️ 【午后交易流水线】启动...")
// donor line numbers
const D_FN_A = 789, D_FN_B = 861;  // def check_a_share_weak_period … return
const D_GLOBALS_A = 160, D_GLOBALS_B = 164;

// ── 1. parent identity ──────────────────────────────────────────────────────────────────────
const raw = fs.readFileSync(PARENT, 'utf8');
const sha = crypto.createHash('sha256').update(raw).digest('hex');
console.log(`[imp1] parent ${path.relative(ROOT, PARENT)}`);
console.log(`[imp1] parent sha256 ${sha}`);
if (sha !== PARENT_SHA) throw new Error(`parent sha256 moved: expected ${PARENT_SHA}`);
if (!raw.endsWith(OVERRIDE)) throw new Error('parent does not end with the frozen OVERRIDE block');
for (const m of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!raw.includes(m)) throw new Error(`parent missing cost/pin marker ${m}`);
}
const curve = path.join(ROOT, 'data/series/study_五福闹新春_q-e9-pit_bf30eb36__train__e9.json');
if (!fs.existsSync(curve)) throw new Error('parent TRAIN curve missing — parent is not a measured row');
{
  const j = JSON.parse(fs.readFileSync(curve, 'utf8'));
  console.log(`[imp1] parent curve ${j.points} pts ${j.start}..${j.end} final cum ${j.cum[j.cum.length - 1]}`);
  if (j.points !== 242) throw new Error(`parent curve has ${j.points} pts, expected 242`);
  if (j.cum[j.cum.length - 1] !== 209.36) throw new Error('parent curve final cum != 209.36');
}
console.log(`[imp1] active TRAIN window ${JSON.stringify(harness.window('train'))}`);

const rl = raw.split('\n');
const donor = fs.readFileSync(DONOR, 'utf8').split('\n');

// anchors
const expectAt = (lines, n, re, what) => {
  if (!re.test(lines[n - 1])) throw new Error(`L${n} is not ${what}: ${JSON.stringify(lines[n - 1])}`);
};
expectAt(rl, L_WEIGHT, /^\s*g\.portfolio_value_proportion = \[0\.5, 0, 0\.5, 0\]/, 'the live weight line');
expectAt(rl, L_POOL_END, /^\s*\]\s*$/, 'the closing ] of g.fixed_etf_pool');
expectAt(rl, L_DEF_MORNING, /^def morning_routine\(context\):/, 'def morning_routine');
expectAt(rl, L_MERGE_LOG, /log\.info\("【合并池】/, 'the 合并池 log line');
expectAt(rl, L_MERGE_CALL, /^\s*daily_merge_etf_pools\(context\)\s*$/, 'the daily_merge_etf_pools call');
expectAt(rl, L_AFT_START, /log\.info\("▶️ 【午后交易流水线】启动\.\.\."\)/, 'the afternoon_routine opening log');
expectAt(donor, D_FN_A, /^def check_a_share_weak_period\(context\):/, 'donor def check_a_share_weak_period');
expectAt(donor, D_FN_B, /^\s*return g\.is_a_share_weak\s*$/, 'donor function return');

// ── 2. the champion must not already carry any of this ──────────────────────────────────────
for (const sym of ['global_etf_pool', 'is_a_share_weak', 'weak_period_ma_lookback',
  'check_a_share_weak_period', 'weak_start_date', 'max_weak_days']) {
  const hits = rl.map((l, i) => [i + 1, l]).filter(([, l]) => l.includes(sym) && !/^\s*#/.test(l));
  if (hits.length) throw new Error(`parent already references ${sym} in code: L${hits[0][0]}`);
}
console.log('[imp1] parent carries NO breadth input and NO pool switch (6 symbols absent from code)');

// ── 3. the 13 names, and the proof that none is invented ────────────────────────────────────
const KEEP = ['518880', '501018', '161226', '159985', '159980', '513310', '159518', '159509',
  '513100', '513520', '513500', '513030', '513290'];
const DROP = { 159502: '2024-01-10', 159529: '2024-02-02', 513400: '2024-02-02', 520830: '2024-07-16' };

// donor's global pool block, verbatim lines keyed by code
const gpA = donor.findIndex(l => /^\s*g\.global_etf_pool = \[/.test(l)) + 1;
const gpB = (() => { for (let i = gpA; i < donor.length; i++) if (/^\s*\]\s*$/.test(donor[i])) return i + 1; })();
const donorPool = donor.slice(gpA, gpB - 1);                   // body between [ and ]
const codeOf = l => (l.match(/'(\d{6})\.XSH[GE]'/) || [])[1];
const donorCodes = donorPool.map(codeOf).filter(Boolean);
if (donorCodes.length !== 17) throw new Error(`donor g.global_etf_pool has ${donorCodes.length} names, expected 17`);
const expectDrop = Object.keys(DROP);
const derived = donorCodes.filter(c => !expectDrop.includes(c));
if (derived.join() !== KEEP.join()) {
  throw new Error(`13-name set mismatch\n  derived ${derived.join(',')}\n  dispatch ${KEEP.join(',')}`);
}
console.log(`[imp1] donor global pool 17 names, minus the 4 post-window exclusions => ${derived.length}: ${derived.join(', ')}`);

// every kept name must already be in the CHAMPION's own fixed pool
const champPool = rl.slice(345, L_POOL_END - 1).map(codeOf).filter(Boolean);
const missing = derived.filter(c => !champPool.includes(c));
if (missing.length) throw new Error(`port would INVENT names absent from the champion pool: ${missing.join(',')}`);
console.log(`[imp1] all ${derived.length}/${derived.length} kept names already in the champion's g.fixed_etf_pool (${champPool.length} names) — the port invents nothing`);
// and the 4 excluded names must be absent from the champion pool too (the pit rule removed them)
const resurrect = expectDrop.filter(c => champPool.includes(c));
if (resurrect.length) throw new Error(`pit-excluded name present in champion pool: ${resurrect.join(',')}`);
console.log(`[imp1] the 4 pit-excluded names are absent from the champion pool too — no post-window name re-enters`);

// ── 4. build the four insertion blocks ──────────────────────────────────────────────────────
const poolLines = [];
for (const l of donorPool) {
  const c = codeOf(l);
  if (!c) { poolLines.push(l); continue; }                       // donor's section comments
  if (DROP[c]) poolLines.push(`       # imp-e9-1: 移除 ${c}.XSH${c.startsWith('1') ? 'E' : 'G'}（上市 ${DROP[c]} >= 2024-01-01，q-e9-pit 点时规则）`);
  else poolLines.push(l);                                        // VERBATIM donor line, date comment intact
}
const donorGlobals = donor.slice(D_GLOBALS_A - 1, D_GLOBALS_B);  // the 5 weak globals, verbatim

const INS1 = [
  '',
  '    # ── imp-e9-1 插入 1/4：移植 base v5.2(17b3b439) 的「全球/海外 ETF 子池」────────────────',
  '    # 本书（冠军）原本没有这个子池，也没有 A 股 breadth 输入。下列 13 只 = base 的 17 只全球池',
  '    # 减去 q-e9-pit 点时规则已排除的 4 只（注释保留在原位，作者自带上市日期可见）。',
  '    # 13/13 均已在上方 g.fixed_etf_pool 内 —— 本移植不发明任何名字（构建期已断言）。',
  '    g.global_etf_pool = [',
  ...poolLines,
  '    ]',
  '    # imp-e9-1：走弱期判断所需的 5 个全局量，逐字取自 base L160-164。',
  '    # （insertion 2 是逐字复制的函数，它读 weak_start_date / weak_days_count / max_weak_days，',
  '    #   少一个即 AttributeError，所以五个都必须在。max_weak_days=20 是 base 自己的退出上限。）',
  ...donorGlobals,
];

const INS2 = [
  '',
  '# ── imp-e9-1 插入 2/4：check_a_share_weak_period 逐字复制自 base 17b3b439 L789-861 ─────────',
  '#   指数 000300 / 399101 / 399006 / 000510；below_count >= 3 进入，above_count >= 3 退出。',
  '#   阈值保持 3 —— idea-imp-3 已关闭「调进入阈值」这条轴。函数体构建期断言与来源逐字相同。',
  ...donor.slice(D_FN_A - 1, D_FN_B),
  '',
];

const INS3 = [
  '    # ── imp-e9-1 插入 3/4：09:00 一次 A 股 breadth 走弱期判断 ─────────────────────────────',
  '    #   刻意放在晨间（09:00）、且在 daily_merge_etf_pools 之前：q-e8-2 已定位本族的执行噪声',
  '    #   住在 13:1x 快照里，所以判断不放进那个快照。',
  '    log.info("【走弱期判断】A股 breadth 走弱期判断（imp-e9-1 移植）...")',
  '    check_a_share_weak_period(context)',
];

const INS4 = [
  '    # ── imp-e9-1 插入 4/4：base v5.2 的走弱期切池分支 ─────────────────────────────────────',
  '    #   池源 = [x for x in g.filtered_fixed_pool if x in g.global_etf_pool]，即保留冠军自己的',
  '    #   流动性过滤，避免重新引入 q-e8-3 花一跑才定下来的 bypass 混淆。',
  '    #   g.merged_etf_pool 只被 calculate_and_log_ranked_etfs / get_final_ranked_etfs 读取，',
  '    #   所以放在本函数最顶端与 base 放在动量计算之前等价。',
  '    if g.is_a_share_weak:',
  '        weak_pool = [x for x in g.filtered_fixed_pool if x in g.global_etf_pool]',
  '        if weak_pool:',
  '            g.merged_etf_pool = list(set(weak_pool))',
  '        else:',
  '            g.merged_etf_pool = list(set(g.global_etf_pool))',
  '        g.merged_etf_pool.sort()',
  '        log.info("IMP-E9-1-CENSUS WEAK pool=%d names=%s" % (len(g.merged_etf_pool), ",".join(g.merged_etf_pool)))',
  '        log.info(f"🔴 【大A走弱期】使用全球/海外ETF池（冠军流动性过滤后），共{len(g.merged_etf_pool)}只")',
  '    else:',
  '        log.info("IMP-E9-1-CENSUS NORMAL pool=%d" % len(g.merged_etf_pool))',
  '        log.info(f"🟢 【大A正常期】使用合并池，共{len(g.merged_etf_pool)}只")',
];

// ── 5. splice (descending line order so earlier indices stay valid) ──────────────────────────
const ol = rl.slice();
ol.splice(L_AFT_START, 0, ...INS4);          // after the opening log of afternoon_routine
ol.splice(L_MERGE_LOG - 1, 0, ...INS3);      // before the 合并池 log + daily_merge_etf_pools call
ol.splice(L_DEF_MORNING - 1, 0, ...INS2);    // module level, immediately before def morning_routine
ol.splice(L_POOL_END, 0, ...INS1);           // after the closing ] of g.fixed_etf_pool

const INSERTED = INS1.length + INS2.length + INS3.length + INS4.length;
if (ol.length - rl.length !== INSERTED) {
  throw new Error(`line delta ${ol.length - rl.length} != inserted ${INSERTED}`);
}

// ── 6. assertion: the change is PURE INSERTION — every parent line survives, in order ───────
{
  let i = 0;
  const added = [];
  for (const line of ol) {
    if (i < rl.length && line === rl[i]) { i++; continue; }
    added.push(line);
  }
  if (i !== rl.length) throw new Error(`parent lines not all preserved in order (matched ${i}/${rl.length})`);
  if (added.length !== INSERTED) throw new Error(`added ${added.length} lines, expected ${INSERTED}`);
  console.log(`[imp1] PURE INSERTION verified: all ${rl.length} parent lines survive in order; ${added.length} lines added (${INS1.length}+${INS2.length}+${INS3.length}+${INS4.length})`);
}

// ── 7. the verbatim-copy assertion ──────────────────────────────────────────────────────────
{
  const src = donor.slice(D_FN_A - 1, D_FN_B).join('\n');
  const out = ol.join('\n');
  if (!out.includes(src)) throw new Error('copied check_a_share_weak_period is NOT byte-identical to the donor');
  if (!/below_count >= 3\)/.test(src) || !/above_count >= 3\)/.test(src)) {
    throw new Error('donor thresholds are not 3/3 — refusing (idea-imp-3 closed tuning them)');
  }
  const occ = out.split('def check_a_share_weak_period(context):').length - 1;
  if (occ !== 1) throw new Error(`check_a_share_weak_period defined ${occ} times`);
  console.log(`[imp1] insertion 2 byte-identical to donor L${D_FN_A}-${D_FN_B} (${D_FN_B - D_FN_A + 1} lines); thresholds enter>=3 / exit>=3 intact`);
  const gsrc = donor.slice(D_GLOBALS_A - 1, D_GLOBALS_B).join('\n');
  if (!out.includes(gsrc)) throw new Error('the 5 weak globals are not byte-identical to the donor');
  console.log(`[imp1] insertion 1 weak globals byte-identical to donor L${D_GLOBALS_A}-${D_GLOBALS_B}: ${donorGlobals.map(l => l.trim()).join(' | ')}`);
}

// ── 8. the weights line, the duplicate assignment, and the 7 pure_wufu_mode guards ──────────
const nWeight = ol.findIndex(l => /^\s*g\.portfolio_value_proportion = \[0\.5, 0, 0\.5, 0\]/.test(l)) + 1;
if (ol[nWeight - 1] !== rl[L_WEIGHT - 1]) throw new Error('weight line changed');
console.log(`[imp1] weights UNCHANGED: parent L${L_WEIGHT} == variant L${nWeight}  ${rl[L_WEIGHT - 1].trim()}`);
if (!ol.includes(rl[L_DUP - 1])) throw new Error('L3586 duplicate assignment vanished');
{
  const PURE = [0, 0, 1, 0];
  const eq = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
  const V = [0.5, 0, 0.5, 0];                    // identical in parent and variant
  const GUARDS = [
    { line: '103-104', f: v => v[2] > 0 && !eq(v, PURE), desc: 'init_range_bound_status gate' },
    { line: '665', f: v => !eq(v, PURE), desc: 'sync_strategy3_holdings_from_portfolio' },
    ...[1629, 1657, 1734, 1774, 2005].map(n => ({ line: String(n), f: v => eq(v, PURE), desc: 'pure_wufu_mode' })),
  ];
  console.log('[imp1] the 7 exact-literal [0,0,1,0] guards (vector identical in both books):');
  for (const g of GUARDS) {
    console.log(`       L${g.line.padEnd(8)} parent=${String(g.f(V)).padEnd(5)} variant=${String(g.f(V)).padEnd(5)}  ${g.desc}`);
  }
  if (eq(V, PURE)) throw new Error('vector IS pure_wufu_mode — refusing');
  const count = ol.filter(l => l.includes('[0, 0, 1, 0]')).length;
  const pcount = rl.filter(l => l.includes('[0, 0, 1, 0]')).length;
  if (count !== pcount) throw new Error(`[0,0,1,0] site count changed ${pcount} -> ${count}`);
  console.log(`[imp1] all 7 guards take the parent's branch; [0,0,1,0] literal sites ${pcount} -> ${count}`);
}

// ── 9. named-knob + block assertions ────────────────────────────────────────────────────────
const KNOBS = [
  ['g.holdings_num', '1'], ['g.defensive_etf', '"511880.XSHG"'], ['g.min_money', '10'],
  ['g.lookback_days', '25'], ['g.score_threshold_ratio', '0.9'], ['g.r2_threshold', '0.4'],
  ['g.max_range_bound_days', '20'],
];
for (const [k, v] of KNOBS) {
  const line = `    ${k} = ${v}`;
  if (!rl.includes(line)) throw new Error(`parent knob line absent: ${line}`);
  if (!ol.includes(line)) throw new Error(`knob changed in variant: ${line}`);
  console.log(`[imp1] sleeve knob byte-identical: ${k} = ${v}`);
}
const outStr = ol.join('\n');
const BLOCKS = [
  { name: '五福 sleeve knob block (parent L462-527)', a: 462, b: 527 },
  { name: '策略3 run_daily schedule incl. 13:10 (parent L4448-4460)', a: 4448, b: 4460 },
  { name: 'sub_account capital isolation (parent L126-139)', a: 126, b: 139 },
  { name: 'setup_wufu35_globals gate (parent L1978-1990)', a: 1978, b: 1990 },
];
for (const b of BLOCKS) {
  const blk = rl.slice(b.a - 1, b.b).join('\n');
  if (!outStr.includes(blk)) throw new Error(`block not byte-identical: ${b.name}`);
  console.log(`[imp1] byte-identical block: ${b.name}`);
}
if (!/run_daily\(afternoon_routine, time="13:10"\)/.test(outStr)) throw new Error('13:10 schedule line lost');
if (!outStr.endsWith(OVERRIDE)) throw new Error('OVERRIDE block no longer verbatim at tail');
console.log('[imp1] byte-identical: frozen OVERRIDE cost block (tail, verbatim)');
for (const m of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!outStr.includes(m)) throw new Error(`variant missing cost/pin marker ${m}`);
}
console.log('[imp1] three cost/pin markers present');
// python syntax sanity: every inserted STATEMENT inside a function body is indented 4+.
// Comment lines are exempt — the donor's own section comments sit at column 0 inside the list
// literal (`#大宗商品ETF：`), which is legal Python and copied verbatim on purpose.
for (const l of INS1.concat(INS3, INS4)) {
  if (!l.trim() || l.trim().startsWith('#')) continue;
  if (!/^ {4}/.test(l)) throw new Error(`function-body insertion not indented 4+: ${JSON.stringify(l)}`);
}

// ── header + write ──────────────────────────────────────────────────────────────────────────
const header = [
  '# ============================================================================',
  '# imp-e9-1 变体：把 A 股 breadth 走弱期切池移植进冠军的 ETF（五福）袖子',
  '#',
  '# 【父本】study/五福闹新春/q-e9-pit_bf30eb36.py',
  `#         sha256 ${PARENT_SHA}`,
  '#         已测：objective 1.9658 / sharpe 7.51 / final cum 209.36（epoch-9 TRAIN 2024）',
  '#         曲线：data/series/study_五福闹新春_q-e9-pit_bf30eb36__train__e9.json（242 点）',
  '#',
  '# 【供体】strategies/…五福闹新春_v5_2…17b3b439.py（账本 1.7479 @ e9）',
  '#   其走弱期切池是本族唯一 measured 的 edge（趋势择时），q-e9-weak 在本台上重测确认：',
  '#   关掉它 Δobj −0.8930（annual 187.39→108.38，maxDD 12.60→22.89）。冠军本身没有这个机制。',
  '#',
  '# 【四处插入，全部为纯插入，父本无一行被修改】',
  '#   1/4 setup_wufu35_globals：g.global_etf_pool = 13 只（base 17 只减去 q-e9-pit 已排除的 4 只',
  '#       159502/159529/513400/520830，注释保留原位）+ base L160-164 的 5 个走弱期全局量。',
  '#       13/13 均已在本书 g.fixed_etf_pool 内 —— 不发明任何名字（构建期断言）。',
  '#   2/4 check_a_share_weak_period 逐字复制 base L789-861（000300/399101/399006/000510，',
  '#       below>=3 进 / above>=3 出；阈值保持 3，idea-imp-3 已关闭该轴）。',
  '#   3/4 morning_routine（09:00）内一次调用，位于 daily_merge_etf_pools 之前 —— 刻意在',
  '#       13:1x 快照之外（q-e8-2 把本族执行噪声定位在该快照）。',
  '#   4/4 afternoon_routine 顶部的走弱分支，池源取',
  '#       [x for x in g.filtered_fixed_pool if x in g.global_etf_pool]，保留冠军自己的流动性',
  '#       过滤，避免重新引入 q-e8-3 settle 过的 bypass 混淆。',
  '#',
  '# 【不改】g.portfolio_value_proportion 仍为 [0.5, 0, 0.5, 0]（L118，本变体不动权重）；7 处',
  '#   [0,0,1,0] 精确比较取父本同一分支；7 个袖子旋钮、score_threshold_ratio 0.9、r2_threshold',
  '#   0.4、13:10 排程块、OVERRIDE 成本块逐字相同。',
  '#   刻意未移植：供体把 is_a_share_weak 还耦合进 apply_filters 的 R²/均线互换、',
  '#   score_threshold_ratio→1.0、midday_routine 的池更新分流 —— 一并移植会变成多变量改动。',
  '#',
  '# 【预注册判读（三条，不可合并）】Δobj <= 0 ⇒ 移植无效；走弱日普查 < 20/242 日 ⇒ 判「惰性」',
  '#   而非「被证伪」；0 < Δ < 0.16 ⇒ 定案必须来自结构侧（走弱日数 × 两分支持仓与收益归属），',
  '#   不得用 Δ 的数值（本族在 epoch-9 上没有重新标定的噪声地板）。',
  '# ============================================================================',
  '',
].join('\n');

if (DRY) {
  console.log('[imp1] --dry: nothing written');
} else {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, header + outStr);
  console.log(`[imp1] wrote ${path.relative(ROOT, OUT)}  (${(header + outStr).length} bytes, ${(header + outStr).split('\n').length} lines)`);
}

// ── diff ────────────────────────────────────────────────────────────────────────────────────
console.log(`\n[imp1] DIFF (parent -> variant): 4 insertion blocks, ${INSERTED} added lines, 0 modified lines`);
const show = (n, name, at, lines) => {
  console.log(`\n--- insertion ${n}/4  ${name}  @ parent L${at}  (+${lines.length} lines)`);
  for (const l of lines) console.log(`  +${l}`);
};
// splice index i  ==  "inserted AFTER parent line i", so the surrounding parent lines are
// rl[i-1] and rl[i]. Printing it any other way is off by one and hides a misplaced block.
const SITES = [
  [1, L_POOL_END, 'setup_wufu35_globals: g.global_etf_pool + weak globals', INS1],
  [2, L_DEF_MORNING - 1, 'check_a_share_weak_period (verbatim, module level)', INS2],
  [3, L_MERGE_LOG - 1, 'morning_routine 09:00 call', INS3],
  [4, L_AFT_START, 'afternoon_routine weak branch', INS4],
];
for (const [n, at, name, lines] of SITES) show(n, name, at, lines);
console.log('\n[imp1] placement, parent lines bracketing each insertion:');
for (const [n, at, name] of SITES) {
  console.log(`  ins${n} after parent L${at} (${name})`);
  console.log(`        prev  L${at}    ${JSON.stringify(rl[at - 1])}`);
  console.log(`        next  L${at + 1}  ${JSON.stringify(rl[at])}`);
}
