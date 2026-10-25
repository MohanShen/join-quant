// node -e "require('./study/五福闹新春/build-e9-liq.js')"
//
// q-e9-liq for 五福闹新春: a PER-LEG feasibility floor on the champion's two capital-isolated
// sub-accounts, applied as a BUY-SIDE screen only.
//
// PARENT is study/五福闹新春/q-e9-pit_bf30eb36.py — the exact bytes measured at
// objective 1.9658 / sharpe 7.51 / final cum 209.36 under epoch 9 TRAIN. Both the sha256 and the
// stored curve are asserted, so the Delta rests on a measured parent rather than a re-derivation.
//
// Floor arithmetic is READ FROM THE HARNESS (utils/harness-config.js), never hand-copied, so it
// survives the next bump. A leg that must build a position of V yuan can take at most
// order_volume_ratio of a name's daily traded money, hence the name must trade >= V / ovr per day.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '../..');
const PARENT = path.join(__dirname, 'q-e9-pit_bf30eb36.py');
const PARENT_CURVE = path.join(ROOT, 'data/series/study_五福闹新春_q-e9-pit_bf30eb36__train__e9.json');
const EXPECT_SHA = '7eb11d31a64fd7527211dca2daebdbcee62ae1440a4c291b85762aa81014c700';
const EXPECT_CUM = 209.36;

// ---------------------------------------------------------------- parent provenance
const parentBytes = fs.readFileSync(PARENT);
const parentSha = crypto.createHash('sha256').update(parentBytes).digest('hex');
console.log('parent        :', path.relative(ROOT, PARENT));
console.log('parent sha256 :', parentSha);
console.log('parent bytes  :', parentBytes.length);
if (parentSha !== EXPECT_SHA) throw new Error(`parent sha256 mismatch: expected ${EXPECT_SHA}`);
if (!fs.existsSync(PARENT_CURVE)) {
  throw new Error('parent TRAIN curve missing — the Delta would rest on unmeasured bytes: ' + PARENT_CURVE);
}
const pc = JSON.parse(fs.readFileSync(PARENT_CURVE, 'utf8'));
const finalCum = pc.cum[pc.cum.length - 1];
console.log(`parent curve  : ${path.basename(PARENT_CURVE)} (${pc.points} pts, ${pc.start}..${pc.end}, epoch ${pc.epoch}, final cum ${finalCum})`);
if (pc.epoch !== 9 || pc.window !== 'train') throw new Error('parent curve is not an epoch-9 TRAIN curve');
if (Math.abs(finalCum - EXPECT_CUM) > 0.005) throw new Error(`parent curve final cum ${finalCum} != ${EXPECT_CUM}`);

// ---------------------------------------------------------------- floor arithmetic, from the harness
const harness = require('../../utils/harness-config');
const hc = harness.config();
const CAPITAL = hc.costs.capital;            // 1000000
const OVR = hc.costs.orderVolumeRatio;       // 0.05
const PROP_STOCK = 0.5;                      // g.portfolio_value_proportion[0]  (小市值)
const PROP_ETF = 0.5;                        // g.portfolio_value_proportion[2]  (ETF 轮动)
const ETF_SLOTS = 1;                         // g.holdings_num
const STOCK_SLOTS = 5;                       // dispatched divisor; live g.xsz_stock_num is dynamic 3..6
const FLOOR_ETF = CAPITAL * PROP_ETF / ETF_SLOTS / OVR;
const FLOOR_STOCK = CAPITAL * PROP_STOCK / STOCK_SLOTS / OVR;
console.log(`harness epoch ${hc.epoch}: capital=${CAPITAL} order_volume_ratio=${OVR}`);
console.log(`static floors : etf=${FLOOR_ETF.toExponential(2)}  stock=${FLOOR_STOCK.toExponential(2)}`);
if (FLOOR_ETF !== 1e7) throw new Error(`ETF static floor should be 1e7, got ${FLOOR_ETF}`);
if (FLOOR_STOCK !== 2e6) throw new Error(`stock static floor should be 2e6, got ${FLOOR_STOCK}`);

const src = parentBytes.toString('utf8');

const HEADER = [
  '# ============================================================================',
  '# q-e9-liq 变体：对冠军的「两条资金隔离子账户」各自施加自己的可行性下限（BUY 侧筛选）',
  '#',
  '# 【父本】',
  `#   study/五福闹新春/q-e9-pit_bf30eb36.py  sha256 ${parentSha}`,
  '#   父本实测（epoch 9, TRAIN 2024）：objective 1.9658 / sharpe 7.51 / final cum 209.36',
  `#   曲线：data/series/${path.basename(PARENT_CURVE)}（${pc.points} 点，${pc.start}..${pc.end}）`,
  '#   本变体与父本只差「流动性约束」一个维度。',
  '#',
  '# 【地板算术 —— 由 harness 推出，不是我们挑的数】',
  `#   harness epoch ${hc.epoch}: costs.capital = ${CAPITAL}, costs.orderVolumeRatio = ${OVR}`,
  '#   一天最多只能吃掉某只标的成交量的 order_volume_ratio，所以「要建 V 元的仓」要求',
  '#   该标的日成交额 >= V / order_volume_ratio。L118 的 g.portfolio_value_proportion',
  '#   = [0.5 小市值, 0, 0.5 ETF轮动, 0]，于是：',
  `#     ETF 腿 ：capital x 0.5 / g.holdings_num ${ETF_SLOTS} / ${OVR} = ¥${FLOOR_ETF.toExponential(2)}/日`,
  `#     股票腿 ：capital x 0.5 / ${STOCK_SLOTS} 名 / ${OVR} = ¥${FLOOR_STOCK.toExponential(2)}/日`,
  '#',
  '# ⚠ 【固定地板会低估要求 —— 本测显式处理】',
  '#   本书 2024 年赚 +209%，且 q-e9-leg 已确认 ETF 腿按 context.portfolio.total_value',
  '#   x proportion[2] 定仓（L1679），是「整个组合的一半」而不是静态子账户。所以真实仓位',
  '#   全年约长 3 倍，由 ¥1e6 本金算出的地板只是「年初的要求」。',
  '#   做法：每腿每日用 LIVE 的 context.portfolio.total_value 按同一公式算地板（判据用它），',
  '#   同时并行记录静态 ¥1e6 地板「本会」剔除谁（static_removed=），两个数都能报。',
  '#',
  '# 【BUY 侧筛选，不强制卖出 —— liq-1 约定】',
  '#   已持仓的名字一律豁免（exempt=），只拦「今天本要新建的仓」。因此实测 Δ 是',
  '#   「严格执行地板（含强制减仓）」的下界，不是它本身。',
  '#',
  '# 【流动性度量 = 本书自己的那一个】',
  "#   get_price(codes, end_date=context.previous_date, count=3, fields=['money']) 的日均，",
  '#   与本书 filter_fixed_pool_by_volume / filter_by_liquidity 逐字同构。取数失败不剔除任何名字',
  '#   （保持父本行为），并记一条 status=bypass-nodata，使「静默绕过」可数。',
  '#',
  '# 【三处改动，别无其他】',
  '#   (1) set_params：定义 g.liq_* 旋钮（ovr / 静态本金 / 两腿名额 / 3 日窗口）',
  '#   (2) 新增两个只读函数 liq_avg_money() 与 liq_screen()，后者每次调用打一条',
  '#       LIQFLOOR leg= date= floor= floor_static= in= out= removed= static_removed= exempt=',
  '#       slots= n= tv= money= status=',
  '#   (3) 两个调用点：',
  '#       - ETF 腿：get_final_ranked_etfs 的 candidate_pool 成形后、第四步（结合持仓）之前',
  '#       - 股票腿：strategy_1_sell 里 g.target_list 成形之后（卖出名单正是由它派生，',
  '#         已持仓豁免 ⇒ 不会因此多卖一股）',
  '#   其余逐字不动：g.portfolio_value_proportion = [0.5, 0, 0.5, 0]、7 处 [0, 0, 1, 0] 守卫、',
  '#     g.holdings_num 1、动量/择时/阈值/排序、run_daily/run_weekly/run_monthly 全表、',
  '#     三个成本 pin 与文件尾部 frozen OVERRIDE。',
  '#',
  '# 【判据（跑前固定）】',
  '#   (A) 结构判据（主判据，与 objective 无关）：每腿有多少个决策日 in != out、剔除分布、',
  '#       以及与父本曲线 max|Δcum| 是否恰为 0。惰性是真答案（大小盘轮动 liq-1 判例）。',
  '#   (B) 水平判据：Δobjective 对父本 1.9658；家族噪声底换算到本量级约 0.161，',
  '#       |Δ| 低于它不可读，判据须落在 (A)。',
  '#   (C) 预注册：floored objective < 1.00 或 sharpe < 1.0 ⇒ R=1；',
  '#       Δ ≥ −0.20 且地板可证非惰性 ⇒ R=2；其余 ⇒ partial，realizability 保持未设。',
  '#       ⚠ 本测不得主张 R=3（那需要 5–10 倍地板点位）。',
  '#   (D) 两腿必须分别归因：q-e9-leg 实测 ETF 腿只占冠军 objective 的 28.4%，',
  '#       多数来自 小市值 股票腿，而 小市值 家族本身是 R=1 且已在本闸门被拒。',
  '# ============================================================================',
  '',
].join('\n');

function edit(s, from, to, tag) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`[${tag}] expected exactly 1 match, got ${n}: ${JSON.stringify(from.slice(0, 160))}`);
  console.log(`edit ${tag}: FROM matched exactly once`);
  return s.replace(from, to);
}

let out = src;

// ------------------------------------------------------------------ edit (1) the knobs, in set_params
const FROM1 = [
  '    g.starting_cash = context.portfolio.total_value',
  '    g.stock_strategy = {}',
  '    g.strategy_holdings = {1: [], 2: [], 3: [], 4: []}',
].join('\n');
const INS1 = '\n' + [
  '',
  '    # ---- q-e9-liq: 每腿自己的可行性下限（BUY 侧筛选，已持仓豁免，不强制卖出） ----',
  `    # 全部由 harness epoch ${hc.epoch} 推出：costs.capital = ${CAPITAL}, costs.orderVolumeRatio = ${OVR}`,
  `    g.liq_ovr = ${OVR}                     # harness order_volume_ratio`,
  `    g.liq_static_capital = ${CAPITAL}.0       # harness costs.capital（静态地板的本金）`,
  `    g.liq_etf_slots = ${ETF_SLOTS}                     # ETF 腿名额 = g.holdings_num`,
  `    g.liq_stock_slots = ${STOCK_SLOTS}                   # 股票腿名额（dispatch 固定 5；实际 g.xsz_stock_num 动态 3~6，逐日记入 n=）`,
  '    g.liq_days = 3                       # 3 日均成交额，与本书自己的流动性度量一致',
  "    g.liq_enforce = 'live'               # 判据用 LIVE total_value 算的地板；静态 ¥1e6 地板只做并行观测",
].join('\n');
out = edit(out, FROM1, FROM1 + INS1, '1-knobs');

// ------------------------------------------------------------------ edit (2) the two read-only helpers
const FROM2 = '""" ====================== 核心交易引擎 (隔离专用) ====================== """\n';
const INS2 = [
  '# ==================== q-e9-liq: 可行性地板（只读观测 + BUY 侧筛选） ====================',
  'def liq_avg_money(codes, context):',
  '    """本书自己的流动性度量：前 g.liq_days 个交易日的日均成交额（money），end_date=前一交易日。',
  '    与 filter_fixed_pool_by_volume / filter_by_liquidity 逐字同构。只读，不改任何 g.*。',
  '    返回 None 表示取数失败 —— 调用方据此不剔除任何名字（保持父本行为）并记一条 bypass。"""',
  '    if not codes:',
  '        return {}',
  '    try:',
  '        pdata = get_price(list(codes), end_date=context.previous_date, count=g.liq_days,',
  "                          frequency='daily', fields=['money'], panel=False)",
  '        if pdata is None or pdata.empty:',
  '            return None',
  "        tot = pdata.groupby('code')['money'].sum()",
  '        res = {}',
  '        for c in list(codes):',
  '            try:',
  '                res[c] = float(tot.get(c, 0)) / float(g.liq_days)',
  '            except Exception:',
  '                res[c] = 0.0',
  '        return res',
  '    except Exception:',
  '        return None',
  '',
  '',
  'def liq_screen(context, leg, cand, held, slots, prop_idx, nlive):',
  '    """BUY 侧可行性地板筛选 + 逐日普查行。返回筛后名单（保序）。',
  '    地板 = context.portfolio.total_value x proportion[prop_idx] / slots / order_volume_ratio。',
  '    已持仓名字 (held) 一律豁免 ⇒ 本函数永不触发卖出，实测 Δ 是严格地板的下界。"""',
  '    cand = list(cand)',
  '    live_tv = float(context.portfolio.total_value)',
  '    _den = float(max(1, slots)) * float(g.liq_ovr)',
  '    floor_live = live_tv * float(g.portfolio_value_proportion[prop_idx]) / _den',
  '    floor_static = float(g.liq_static_capital) * float(g.portfolio_value_proportion[prop_idx]) / _den',
  '    money = liq_avg_money(cand, context)',
  '    if money is None:',
  '        log.info("LIQFLOOR leg=%s date=%s floor=%.0f floor_static=%.0f in=%d out=%d removed=- "',
  '                 "static_removed=- exempt=- slots=%d n=%d tv=%.0f money=- status=bypass-nodata"',
  '                 % (leg, context.previous_date, floor_live, floor_static,',
  '                    len(cand), len(cand), slots, nlive, live_tv))',
  '        return cand',
  '    kept = []',
  '    removed = []',
  '    static_removed = []',
  '    exempt = []',
  '    for c in cand:',
  '        m = float(money.get(c, 0.0))',
  '        if c in held:',
  '            kept.append(c)',
  '            exempt.append(c)',
  '            continue',
  '        if m >= floor_live:',
  '            kept.append(c)',
  '        else:',
  '            removed.append(c)',
  '        if m < floor_static:',
  '            static_removed.append(c)',
  '    log.info("LIQFLOOR leg=%s date=%s floor=%.0f floor_static=%.0f in=%d out=%d removed=%s "',
  '             "static_removed=%s exempt=%s slots=%d n=%d tv=%.0f money=%s status=ok"',
  '             % (leg, context.previous_date, floor_live, floor_static, len(cand), len(kept),',
  "                ';'.join(removed) or '-', ';'.join(static_removed) or '-',",
  "                ';'.join(exempt) or '-', slots, nlive, live_tv,",
  "                ';'.join(['%s:%.0f' % (c, float(money.get(c, 0.0))) for c in cand]) or '-'))",
  '    return kept',
  '',
  '',
  '',
].join('\n');
out = edit(out, FROM2, INS2 + FROM2, '2-helpers');

// ------------------------------------------------------------------ edit (3a) ETF leg call site
const FROM3a = "    log_buffer.append(f\"【候选池】共{len(candidate_pool)}只ETF（按{'短期' if use_short_momentum else '原'}动量得分排序）：\")\n";
const INS3a = [
  '    # q-e9-liq: ETF 腿 BUY 侧可行性地板。放在第四步（结合持仓）之前，并对已持仓豁免，',
  '    # 所以 retained 不受影响 —— 不会因为地板而多卖一股。',
  '    _liq_held_etf = set([sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0])',
  "    _liq_kept_etf = set(liq_screen(context, 'etf', [it['etf'] for it in candidate_pool],",
  '                                   _liq_held_etf, g.liq_etf_slots, 2, g.holdings_num))',
  "    candidate_pool = [it for it in candidate_pool if it['etf'] in _liq_kept_etf]",
  '',
].join('\n');
out = edit(out, FROM3a, INS3a + FROM3a, '3a-etf-callsite');

// ------------------------------------------------------------------ edit (3b) stock leg call site
const FROM3b = [
  '    g.target_list = {',
  '        "v1": get_small_cap_stocks_v1,',
  '        "v2": get_small_cap_stocks_v2,',
  '        "v3": get_small_cap_stocks_v3,',
  '    }[g.xsz_version](context)[: g.xsz_stock_num]',
].join('\n');
const INS3b = '\n' + [
  '    # q-e9-liq: 股票腿 BUY 侧可行性地板。held = g.strategy_holdings[1]，正是下方 sell_list /',
  '    # hold_list 的来源，已持仓豁免 ⇒ 地板永不触发卖出（实测 Δ 为严格地板的下界）。',
  "    g.target_list = liq_screen(context, 'stock', g.target_list, set(g.strategy_holdings[1]),",
  '                               g.liq_stock_slots, 0, g.xsz_stock_num)',
].join('\n');
out = edit(out, FROM3b, FROM3b + INS3b, '3b-stock-callsite');

const variant = HEADER + out;
const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, 'q-e9-liq_both-legs.py');

// ================================================================== ASSERTIONS
// Every count is taken on `out` — the variant MINUS our own header comment block. The header
// quotes several markers in prose, and counting the whole file makes assertions fail on their own
// documentation (the build-siblings.js lesson in CLAUDE.md).
const fail = [];
const A = (ok, msg) => { console.log((ok ? 'OK   ' : 'FAIL ') + msg); if (!ok) fail.push(msg); };

// --- (a) the capital split is untouched
A((out.match(/g\.portfolio_value_proportion = \[0\.5, 0, 0\.5, 0\]  # 小市值\/ETF轮动 \(用于长回测\)/g) || []).length === 1,
  'active split line g.portfolio_value_proportion = [0.5, 0, 0.5, 0] present exactly once');
A((src.match(/\[0, 0, 1, 0\]/g) || []).length === 7 && (out.match(/\[0, 0, 1, 0\]/g) || []).length === 7,
  'the 7 exact-literal [0, 0, 1, 0] pure_wufu_mode guards are unchanged (7 -> 7)');
A((out.match(/pure_wufu_mode = \(g\.portfolio_value_proportion == \[0, 0, 1, 0\]\)/g) || []).length
  === (src.match(/pure_wufu_mode = \(g\.portfolio_value_proportion == \[0, 0, 1, 0\]\)/g) || []).length,
  'pure_wufu_mode assignment count unchanged (so every guard takes the parent branch)');

// --- (b) scheduling table byte-identical
const sched = s => s.split('\n').map(l => l.trim()).filter(l => /^run_(daily|weekly|monthly)\(/.test(l));
const sA = sched(src), sB = sched(out);
A(sA.length === sB.length && sA.every((l, i) => l === sB[i]),
  `run_daily/weekly/monthly schedule byte-identical (${sA.length} lines)`);

// --- (c) THE STRONGEST ASSERTION: deleting exactly our four inserted blocks restores the parent
// byte-for-byte. This subsumes every per-marker count — nothing else in 4,535 lines moved.
// (Marker counting on the whole file is unreliable here: our own comments and docstring mention
// `order_volume_ratio`, and the parent carries `g.avg_etf_money_threshold = 10000000` for its own
// reasons, so a naive count fails on our documentation — the build-siblings.js lesson.)
let restored = out;
for (const [tag, blk] of [['1-knobs', INS1], ['2-helpers', INS2], ['3a-etf', INS3a], ['3b-stock', INS3b]]) {
  const n = restored.split(blk).length - 1;
  A(n === 1, `inserted block ${tag} appears exactly once in the variant`);
  restored = restored.replace(blk, '');
}
A(restored === src, 'removing exactly the 4 inserted blocks restores the parent BYTE-FOR-BYTE');
const { OVERRIDE } = require('../../utils/strategy-normalize');
A(variant.endsWith(OVERRIDE), 'frozen OVERRIDE cost block is the file tail, byte-identical');

// --- (d) the three cost pins and the mechanism knobs, counted on the RESTORED text (so our own
// prose cannot flatter the count) and on the inserted blocks (which must not mention them in code)
for (const marker of ['avoid_future_data', "set_option('order_volume_ratio', 0.05)", 'set_order_cost']) {
  const a = src.split(marker).length - 1, b = restored.split(marker).length - 1;
  A(a === b && a > 0, `cost pin count unchanged: ${marker} (${a} -> ${b})`);
}
for (const marker of [
  'g.holdings_num = 1', 'g.score_threshold_ratio', 'g.lookback_days',
  'g.xsz_stock_num = 5', 'g.xsz_version = "v3"', 'g.enable_dynamic_stock_num = True',
  'g.avg_etf_money_threshold', 'avg_daily_money[avg_daily_money > dynamic_threshold]',
  'g.avg_etf_money_threshold = 10000000',
]) {
  const a = src.split(marker).length - 1, b = restored.split(marker).length - 1;
  A(a === b && a > 0, `marker count unchanged: ${marker} (${a} -> ${b})`);
}
// our inserted CODE may not touch the book's own liquidity threshold or the cost pins
// ⚠ strip TRAILING comments too, not just whole-comment lines: a knob line carries
// `# 静态 ¥1e6 地板只做并行观测`, and a check that reads prose as code fails on the right answer.
const insCode = [INS1, INS2, INS3a, INS3b].join('\n').split('\n')
  .filter(l => !/^\s*#/.test(l)).map(l => l.replace(/\s+#.*$/, '')).join('\n');
for (const forbidden of ['g.avg_etf_money_threshold', 'dynamic_threshold', 'set_order_cost',
  'set_slippage', 'set_commission', 'set_option', 'g.holdings_num =', 'g.xsz_stock_num =']) {
  A(!insCode.includes(forbidden), `inserted code does not touch: ${forbidden}`);
}

// --- (e) floor literals agree with the harness
A((out.match(new RegExp(`g\\.liq_ovr = ${String(OVR).replace('.', '\\.')}`, 'g')) || []).length === 1,
  `g.liq_ovr literal equals harness orderVolumeRatio (${OVR})`);
A((out.match(new RegExp(`g\\.liq_static_capital = ${CAPITAL}\\.0`, 'g')) || []).length === 1,
  `g.liq_static_capital literal equals harness capital (${CAPITAL})`);
A((out.match(/g\.liq_etf_slots = 1\b/g) || []).length === 1, 'g.liq_etf_slots = 1 (= g.holdings_num)');
A((out.match(/g\.liq_stock_slots = 5\b/g) || []).length === 1, 'g.liq_stock_slots = 5 (dispatched divisor)');
// no hard-coded floor VALUE in our inserted code — both floors are derived at runtime from the
// knobs. (The parent's own `g.avg_etf_money_threshold = 10000000` fallback is untouched and is a
// different quantity: the book's relative ETF liquidity gate, not our feasibility floor.)
A(!/\b(1e7|2e6|10000000|2000000|1e6)\b/.test(insCode),
  'no hard-coded floor value appears in the inserted code — both floors are derived from the knobs');
const codeLines = out.split('\n').filter(l => !/^\s*#/.test(l));
const code = codeLines.join('\n');
A(code.includes('floor_live = live_tv * float(g.portfolio_value_proportion[prop_idx]) / _den'),
  'LIVE floor is computed from context.portfolio.total_value each call');
A(code.includes('floor_static = float(g.liq_static_capital) * float(g.portfolio_value_proportion[prop_idx]) / _den'),
  'STATIC floor is computed in parallel and only logged');

// --- (f) the floor is a BUY-side screen only: it can never place or cancel an order
const helperStart = out.indexOf('def liq_avg_money(codes, context):');
const helperEnd = out.indexOf('""" ====================== 核心交易引擎');
A(helperStart > 0 && helperEnd > helperStart, 'helper block located');
const helpers = out.slice(helperStart, helperEnd);
const TRADE_RE = /\b(order|order_target|order_value|order_target_value|close_position|open_position|smart_order_target_value|trade_for_strategy|smart_open_15|smart_close_15)\s*\(/;
A(!TRADE_RE.test(helpers), 'helper block calls no order/position function');
A(!/\bg\.\w+\s*=[^=]/.test(helpers), 'helper block assigns no g.* (pure read + log)');
A(helpers.includes('if c in held:') && helpers.includes('exempt.append(c)'),
  'held names are exempted (buy-side only, no force-sell)');
// the two inserted call sites touch only candidate_pool / g.target_list
const etfIns = out.split('    # q-e9-liq: ETF 腿 BUY 侧可行性地板')[1].split('    log_buffer.append(f"【候选池】')[0];
A(!TRADE_RE.test(etfIns), 'ETF call site calls no order/position function');
A(/candidate_pool = \[it for it in candidate_pool if it\['etf'\] in _liq_kept_etf\]/.test(etfIns),
  'ETF call site rewrites only candidate_pool');
const stkIns = out.split('    # q-e9-liq: 股票腿 BUY 侧可行性地板')[1].split('\n\n')[0];
A(!TRADE_RE.test(stkIns), 'stock call site calls no order/position function');
A(/g\.target_list = liq_screen\(context, 'stock'/.test(stkIns), 'stock call site rewrites only g.target_list');

// --- (g) exactly two call sites, one per leg
A((code.match(/liq_screen\(context, '/g) || []).length === 2, 'exactly 2 liq_screen call sites');
A((code.match(/liq_screen\(context, 'etf'/g) || []).length === 1, 'exactly 1 etf call site');
A((code.match(/liq_screen\(context, 'stock'/g) || []).length === 1, 'exactly 1 stock call site');
A((code.match(/def liq_screen\(/g) || []).length === 1 && (code.match(/def liq_avg_money\(/g) || []).length === 1,
  'each helper defined exactly once');

// --- (h) the census lines are bare log.info and cannot influence a decision
const liqStmts = out.split('\n').filter(l => l.includes('"LIQFLOOR '));
A(liqStmts.length === 2, `2 LIQFLOOR log statements (1 ok + 1 bypass), got ${liqStmts.length}`);
A(liqStmts.every(l => /^\s*log\.info\("LIQFLOOR /.test(l)), 'every LIQFLOOR statement starts as a bare log.info(');
const vlines = variant.split('\n');
for (let i = 0; i < vlines.length; i++) {
  if (!/^\s*log\.info\("LIQFLOOR /.test(vlines[i])) continue;
  let j = i, expr = '', bal = 0;
  do { expr += vlines[j] + '\n'; for (const ch of vlines[j]) { if (ch === '(') bal++; if (ch === ')') bal--; } j++; }
  while (bal > 0 && j < vlines.length);
  A(!/\bg\.\w+\s*=[^=]/.test(expr), `LIQFLOOR stmt at line ~${i + 1} assigns no g.*`);
  A(!/\.sort\(|\.append\(|\.pop\(|\bdel\s/.test(expr), `LIQFLOOR stmt at line ~${i + 1} has no sort/append/pop/del`);
  A(!TRADE_RE.test(expr), `LIQFLOOR stmt at line ~${i + 1} places no order`);
}
// every census field the report needs
for (const f of ['leg=', 'date=', 'floor=', 'floor_static=', 'in=', 'out=', 'removed=',
  'static_removed=', 'exempt=', 'slots=', 'n=', 'tv=', 'money=', 'status=']) {
  A(liqStmts.every(l => out.slice(out.indexOf(l)).slice(0, 900).includes(f)),
    `census field present in both statements: ${f}`);
}

// --- (i) only the three intended regions differ
const diffOnly = (() => {
  let d = '';
  try { execFileSync('diff', ['-u', PARENT, '/dev/stdin'], { input: variant, encoding: 'utf8' }); }
  catch (e) { d = e.stdout; }
  return d;
})();
const hunks = (diffOnly.match(/^@@/gm) || []).length;
A(hunks === 5, `diff has 5 hunks (header + 3 edits, the helper insert splitting one) — got ${hunks}`);
const removedLines = diffOnly.split('\n').filter(l => l.startsWith('-') && !l.startsWith('---'));
A(removedLines.length === 0, `diff REMOVES no parent line (got ${removedLines.length})`);
removedLines.forEach(l => console.log('     removed:', l.slice(0, 120)));

if (fail.length) {
  console.error('\n' + fail.length + ' ASSERTION(S) FAILED — not writing the variant');
  fail.forEach(m => console.error('  - ' + m));
  process.exitCode = 1;
} else {
  fs.writeFileSync(outFile, variant);
  console.log('\nwrote', path.relative(ROOT, outFile), `(${Buffer.byteLength(variant)} bytes)`);
  console.log('sha256', crypto.createHash('sha256').update(variant).digest('hex'));
  console.log('\n===== diff q-e9-pit_bf30eb36.py -> variants/q-e9-liq_both-legs.py =====');
  console.log(diffOnly);
}
