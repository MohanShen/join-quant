// q-e9-leg: LEG DECOMPOSITION of champion bf30eb36 (三马105-五福35) — run the ETF (五福) leg alone.
//
// ## Parent — deliberately NOT the raw champion
//
//   study/五福闹新春/q-e9-pit_bf30eb36.py   objective 1.9658 / sharpe 7.51 / final cum 209.36
//   stored curve: data/series/study_五福闹新春_q-e9-pit_bf30eb36__train__e9.json (242 pts,
//   2024-01-02..2024-12-31)
//
// The raw book's ETF pool carries 17 names that listed AFTER the TRAIN window (7 of them in 2025),
// and every one of them sits in the ETF sleeve. Decomposing the raw book would therefore measure an
// ETF leg inflated by post-window selection — biasing the test toward the very conclusion it exists
// to challenge. The point-in-time build is the only honest parent.
//
// ## The edit — one line, L118
//
//   g.portfolio_value_proportion = [0.5, 0, 0.5, 0]   ->   [0, 0, 0.5, 0]
//            ^ [小市值, ETF反弹, ETF轮动(五福), 白马]
//
// Capital is held in ISOLATED virtual sub-accounts (`g.sub_account[i].initial_capital =
// g.starting_cash * pvp[i-1]`, L128-134), so zeroing slot 1 while slot 3 KEEPS its 0.5 leaves the
// ETF sleeve's position size, its `order_volume_ratio` bite and its `min_money` thresholds
// byte-identical to the parent. The small-cap half simply sits in cash. That is why the edit is
// NOT `[0, 0, 1, 0]`:
//
//   ⚠ `[0, 0, 1, 0]` is an author-supported `pure_wufu_mode` special case, tested as an EXACT
//     literal at 7 sites (L103-104, L665, L1629, L1657, L1734, L1774, L2005). Under the parent
//     every one is False; under `[0,0,0.5,0]` every one is STILL False; under `[0,0,1,0]` they all
//     FLIP, changing the ETF sleeve's own logic. So `[0,0,1,0]` would confound a logic-branch
//     change into what is meant to be a capital-allocation change. Asserted below.
//
// ## Assertions (a failure voids the build, it is not interpreted)
//
//   1. parent sha256 pinned; OVERRIDE block present verbatim at the tail; 3 cost markers present.
//   2. exactly ONE line differs, it is L118, and the new literal is [0, 0, 0.5, 0].
//   3. all 7 `== [0,0,1,0]` guards evaluate IDENTICALLY in parent and variant (all False).
//   4. the SECOND assignment of the vector (L3586, inside `_ensure_make_record_globals` behind
//      `if not pv_ok:` where `pv_ok = isinstance(pv,(list,tuple)) and len(pv) >= 4`) is unchanged
//      and unreachable for a 4-element edited list. Asserted even though the gatekeeper resolved
//      it, because a silent revert would produce Δ≈0 — which in THIS test reads as "the ETF leg
//      alone produces the champion's entire return", the worst-direction false positive.
//   5. the 五福 (strategy 3) `run_daily` schedule block and the sleeve's own knob block are
//      byte-identical to the parent.
//
//   node -e "require('./study/五福闹新春/build-e9-leg.js')" --dry
//   node -e "require('./study/五福闹新春/build-e9-leg.js')"

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const DIR = __dirname;
const DRY = process.argv.includes('--dry');

const PARENT = path.join(DIR, 'q-e9-pit_bf30eb36.py');
const PARENT_SHA = '7eb11d31a64fd7527211dca2daebdbcee62ae1440a4c291b85762aa81014c700';
const OUT = path.join(DIR, 'variants', 'q-e9-leg_etf-only.py');

const WEIGHT_LINE = 118;                 // gatekeeper-verified; NOT L87 as both generators said
const DUP_LINE = 3586;                   // gatekeeper-verified; NOT L3555
const FROM = '[0.5, 0, 0.5, 0]';
const TO = '[0, 0, 0.5, 0]';

// ── 1. parent identity ──────────────────────────────────────────────────────────────────────
const raw = fs.readFileSync(PARENT, 'utf8');
const sha = crypto.createHash('sha256').update(raw).digest('hex');
console.log(`[leg] parent ${path.relative(path.join(DIR, '../..'), PARENT)}`);
console.log(`[leg] parent sha256 ${sha}`);
if (sha !== PARENT_SHA) throw new Error(`parent sha256 moved: expected ${PARENT_SHA}`);
if (!raw.endsWith(OVERRIDE)) throw new Error('parent does not end with the frozen OVERRIDE block');
for (const m of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!raw.includes(m)) throw new Error(`parent missing cost/pin marker ${m}`);
}
const curve = path.join(DIR, '../..', 'data/series/study_五福闹新春_q-e9-pit_bf30eb36__train__e9.json');
if (!fs.existsSync(curve)) throw new Error('parent TRAIN curve missing — parent is not a measured row');
{
  const j = JSON.parse(fs.readFileSync(curve, 'utf8'));
  console.log(`[leg] parent curve ${j.points} pts ${j.start}..${j.end} final cum ${j.cum[j.cum.length - 1]}`);
}
console.log(`[leg] active TRAIN window ${JSON.stringify(harness.window('train'))}`);

// ── 2. the single edit ──────────────────────────────────────────────────────────────────────
const rl = raw.split('\n');
if (!rl[WEIGHT_LINE - 1].includes(`g.portfolio_value_proportion = ${FROM}`)) {
  throw new Error(`L${WEIGHT_LINE} is not the live weight assignment: ${rl[WEIGHT_LINE - 1]}`);
}
if (/^\s*#/.test(rl[WEIGHT_LINE - 1])) throw new Error(`L${WEIGHT_LINE} is commented out`);

const ol = rl.slice();
ol[WEIGHT_LINE - 1] = rl[WEIGHT_LINE - 1].replace(FROM, TO) +
  '   # q-e9-leg: 小市值腿权重归零，五福腿保留 0.5 资本（子账户隔离 ⇒ 持仓规模/成交比例/min_money 与父本相同）';

const changed = rl.map((l, i) => [i + 1, l, ol[i]]).filter(([, a, b]) => a !== b);
if (changed.length !== 1) throw new Error(`expected exactly 1 changed line, got ${changed.length}`);
if (changed[0][0] !== WEIGHT_LINE) throw new Error(`changed line ${changed[0][0]} != ${WEIGHT_LINE}`);
if (!changed[0][2].includes(`g.portfolio_value_proportion = ${TO}`)) throw new Error('new literal wrong');
if (!changed[0][2].includes('q-e9-leg:')) throw new Error('changed line carries no marker');

// ── 3. pure_wufu_mode invariant: all 7 exact-literal guards must take the SAME branch ──────
const PURE = [0, 0, 1, 0];
const eq = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
const vec = s => JSON.parse(s.replace(/\s+/g, ''));
const P = vec(FROM), V = vec(TO);
const GUARDS = [
  { line: '103-104', desc: 'pvp[2] > 0 and not (pvp == [0,0,1,0])  -> init_range_bound_status',
    f: v => v[2] > 0 && !eq(v, PURE) },
  { line: '665', desc: 'pvp != [0,0,1,0]  -> sync_strategy3_holdings_from_portfolio',
    f: v => !eq(v, PURE) },
  ...[1629, 1657, 1734, 1774, 2005].map(n => ({
    line: String(n), desc: 'pure_wufu_mode = (pvp == [0,0,1,0])', f: v => eq(v, PURE),
  })),
];
console.log('[leg] exact-literal [0,0,1,0] guards — parent vs variant:');
for (const g of GUARDS) {
  const a = g.f(P), b = g.f(V);
  console.log(`      L${g.line.padEnd(8)} parent=${String(a).padEnd(5)} variant=${String(b).padEnd(5)}  ${g.desc}`);
  if (a !== b) throw new Error(`guard L${g.line} FLIPS between parent and variant — refusing`);
}
if (eq(V, PURE)) throw new Error('variant vector IS the pure_wufu_mode literal — refusing');
// Sanity: the thing a bad edit would have done.
if (GUARDS.filter(g => g.f([0, 0, 1, 0]) !== g.f(P)).length !== GUARDS.length) {
  throw new Error('self-check failed: [0,0,1,0] should flip every guard');
}
console.log(`[leg] pure_wufu_mode: parent=${eq(P, PURE)} variant=${eq(V, PURE)}  (all 7 guards identical; [0,0,1,0] would have flipped all 7)`);

// ── 4. the SECOND assignment at L3586 ───────────────────────────────────────────────────────
if (!rl[DUP_LINE - 1].includes(`g.portfolio_value_proportion = ${FROM}`)) {
  throw new Error(`L${DUP_LINE} is not the duplicate assignment: ${rl[DUP_LINE - 1]}`);
}
if (ol[DUP_LINE - 1] !== rl[DUP_LINE - 1]) throw new Error('L3586 must stay untouched');
const guardLine = rl[DUP_LINE - 2];          // `if not pv_ok:`
const pvOkLine = rl.find(l => l.includes('pv_ok = isinstance'));
if (!/if not pv_ok:/.test(guardLine)) throw new Error(`L${DUP_LINE - 1} is not "if not pv_ok:": ${guardLine}`);
if (!/len\(pv\) >= 4/.test(pvOkLine || '')) throw new Error('pv_ok definition not as audited');
// The edited value is a 4-element list, so pv_ok stays True and the literal never re-fires.
const pvOk = Array.isArray(V) && V.length >= 4;
if (!pvOk) throw new Error('edited vector would make pv_ok False — L3586 becomes reachable');
console.log('[leg] both assignments of g.portfolio_value_proportion — final effective value:');
console.log(`      L${WEIGHT_LINE}  set_params                     -> ${JSON.stringify(V)}   (EFFECTIVE)`);
console.log(`      L${DUP_LINE} _ensure_make_record_globals     -> ${JSON.stringify(P)}   GUARDED by "if not pv_ok:"`);
console.log(`              pv_ok(isinstance(list) and len>=4) = ${pvOk}  => "if not pv_ok" is False => literal NEVER re-fires`);
console.log('              and if the enclosing `need` branch runs for another reason it REBUILDS');
console.log('              g.sub_account by RE-READING the edited value (L3594-3603), so no revert path exists.');

// ── 5. the 五福 sleeve's own schedule + knobs must be byte-identical ─────────────────────────
const BLOCKS = [
  { name: '策略3 五福 run_daily schedule (L4449-4460)', a: 4449, b: 4460 },
  { name: '策略3 setup_wufu35_globals gate (L1978-1990)', a: 1978, b: 1990 },
  { name: 'sub_account capital isolation (L126-139)', a: 126, b: 139 },
  { name: 'capital_balance zero-weight early return (L260-272)', a: 260, b: 272 },
];
for (const bl of BLOCKS) {
  const A = rl.slice(bl.a - 1, bl.b).join('\n');
  const B = ol.slice(bl.a - 1, bl.b).join('\n');
  if (A !== B) throw new Error(`block changed but must not: ${bl.name}`);
  console.log(`[leg] byte-identical: ${bl.name}`);
}
// OVERRIDE / cost block untouched.
const out0 = ol.join('\n');
if (!out0.endsWith(OVERRIDE)) throw new Error('OVERRIDE block no longer verbatim at tail');
if (out0.length - raw.length !== ol[WEIGHT_LINE - 1].length - rl[WEIGHT_LINE - 1].length) {
  throw new Error('byte delta does not match the single edited line');
}
console.log('[leg] byte-identical: frozen OVERRIDE cost block (tail, verbatim)');

// ── header + write ──────────────────────────────────────────────────────────────────────────
const header = [
  '# ============================================================================',
  '# q-e9-leg 变体：冠军 bf30eb36（三马105-五福35）的腿分解 —— 只跑 ETF（五福）腿',
  '#',
  '# 【父本】study/五福闹新春/q-e9-pit_bf30eb36.py',
  `#         sha256 ${PARENT_SHA}`,
  '#         已测：objective 1.9658 / sharpe 7.51 / final cum 209.36（epoch-9 TRAIN）',
  '#         曲线：data/series/study_五福闹新春_q-e9-pit_bf30eb36__train__e9.json（242 点）',
  '#   ⚠ 刻意不用 strategies/ 里的生书：生书 ETF 池含 17 只窗后上市名字（7 只 2025 年上市），',
  '#     且全部落在 ETF 袖子里 —— 用生书做腿分解会系统性高报 ETF 腿，正好偏向本测要检验的一侧。',
  '#',
  `# 【唯一改动】L${WEIGHT_LINE}  g.portfolio_value_proportion  ${FROM} -> ${TO}`,
  '#         [小市值, ETF反弹, ETF轮动(五福), 白马]',
  '#   资本在隔离的虚拟子账户里（L128-134 initial_capital = starting_cash * pvp[i-1]），所以把',
  '#   第 1 槽归零、第 3 槽保留 0.5，使 ETF 袖子的持仓规模 / order_volume_ratio 咬合 / min_money',
  '#   与父本逐字相同，小市值那一半单纯躺成现金。',
  '#',
  '#   ⚠ 刻意不用 [0, 0, 1, 0]：该字面量是作者支持的 pure_wufu_mode 特例，在 7 处被精确比较',
  '#     （L103-104, L665, L1629, L1657, L1734, L1774, L2005）。父本下 7 处全为 False；',
  `#     ${TO} 下仍全为 False；[0,0,1,0] 下 7 处全部翻转，会改掉 ETF 袖子自身的逻辑。`,
  '#',
  '# 【构建期断言】父本 sha256、OVERRIDE 逐字、三个成本标记、唯一一行 diff、7 处 guard 同分支、',
  `#   L${DUP_LINE} 重复赋值未动且因 pv_ok=True 不可达、五福排程与旋钮块逐字相同。`,
  '#',
  '# 【预注册判读】ETF-腿-only annual ≥ 150%（obj ≥ 1.35）⇒ ETF 腿是驱动；',
  '#   annual ≤ 100%（obj ≤ 0.90）⇒ 小市值腿供给多数，冠军归因错误。100–150% 之间读作部分。',
  '#   结构性 rider（必须从日志取）：strategy-1 成交笔数必须为 0。',
  '# ============================================================================',
  '',
].join('\n');

if (DRY) {
  console.log('[leg] --dry: nothing written');
} else {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, header + out0);
  console.log(`[leg] wrote ${path.relative(path.join(DIR, '../..'), OUT)}  (${(header + out0).length} bytes)`);
}

console.log('\n[leg] DIFF (parent -> variant), 1 line:');
console.log(`  -L${WEIGHT_LINE}  ${rl[WEIGHT_LINE - 1]}`);
console.log(`  +L${WEIGHT_LINE}  ${ol[WEIGHT_LINE - 1]}`);
