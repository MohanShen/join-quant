// node -e "require('./study/多因子ML/build-e9-liq.js')"
//
// q-e9-liq for 多因子ML: a PER-SLEEVE, DYNAMIC, PARAMETER-FREE fill-feasibility floor on the
// family champion 高质量稳定上涨策略 (d02cde29), applied at the book's three selection sites.
//
// WHY: the family is REJECTED at integration's exit gate on `realizability: 1`, and that 1 is
// declared PROSE — its realizabilityBasis quotes a sentence about the headline LEVEL being
// unachievable, which is a different claim from "fills a daily bar cannot honour".
// `node utils/realizability-lint.js` raises NO flag on this book. This run replaces the guess with
// a measurement, in whichever direction the number falls.
//
// PARENT is study/多因子ML/baseline-e6.py, asserted byte-identical to
// py2to3(strategies/2026-06-28_高质量稳定上涨策略-d02cde29.py) + the CURRENT frozen OVERRIDE, and
// asserted against its stored epoch-9 TRAIN curve (final cum 156.71). The control is therefore
// free — no backtest is owed for it.
//
// Floor arithmetic is READ FROM THE HARNESS (utils/harness-config.js), never hand-copied, so it
// survives the next bump. A sleeve that must build V yuan in ONE name can take at most
// order_volume_ratio of that name's daily traded money, hence the name must trade >= V / ovr/day.
//
// Style is borrowed VERBATIM from study/ETF动量/variants/q-e9-3_liq-1.py: a 20-bar MEDIAN of daily
// `money` evaluated on context.previous_date, one log.error('LIQFLOOR ...') per call (so it
// survives this book's three log.set_level calls), and a LOUD except rather than a silent skip.
//
// Emits THREE variants. Only liq-1 (multiplier 1.0 = the feasibility minimum) is dispatched for a
// run; liq-2 (5x) and liq-3 (10x) are built and NOT run — the capacity ceiling is a separate
// question and a later decision (the b3751277 / 大小盘轮动 precedent).
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '../..');
const PARENT = path.join(__dirname, 'baseline-e6.py');
const RAW = path.join(ROOT, 'strategies/2026-06-28_高质量稳定上涨策略-d02cde29.py');
const PARENT_CURVE = path.join(ROOT, 'data/series/2026-06-28_高质量稳定上涨策略-d02cde29__train__e9.json');
const EXPECT_SHA = 'fa3e86afc68ce6fe514554c0a4f25f7aa2418edf440fa79ae75fb22445a1dcad';
const EXPECT_CUM = 156.71;

// ---------------------------------------------------------------- parent provenance
const parentBytes = fs.readFileSync(PARENT);
const src = parentBytes.toString('utf8');
const parentSha = crypto.createHash('sha256').update(parentBytes).digest('hex');
console.log('parent        :', path.relative(ROOT, PARENT));
console.log('parent sha256 :', parentSha);
console.log('parent chars  :', src.length, '(bytes', parentBytes.length + ')');
if (parentSha !== EXPECT_SHA) throw new Error(`parent sha256 mismatch: expected ${EXPECT_SHA}`);

// the parent must BE py2to3(raw) + the CURRENT OVERRIDE, or the Delta is against a stale bench
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const rebuilt = py2to3(fs.readFileSync(RAW, 'utf8')) + OVERRIDE;
if (rebuilt !== src) {
  const a = rebuilt.split('\n'), b = src.split('\n');
  let n = 0;
  for (let i = 0; i < Math.max(a.length, b.length); i++) if (a[i] !== b[i]) n++;
  throw new Error(`parent != py2to3(raw) + current OVERRIDE (${n} differing lines)`);
}
console.log('parent        : == py2to3(raw) + current OVERRIDE  (0 differing lines, 43002 chars)');

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
const CAPITAL = hc.costs.capital;        // 1000000
const OVR = hc.costs.orderVolumeRatio;   // 0.05
console.log(`harness epoch ${hc.epoch}: capital=${CAPITAL} order_volume_ratio=${OVR}`);
if (OVR !== 0.05) throw new Error(`order_volume_ratio changed to ${OVR} — re-derive the documented base-capital floors`);
if (CAPITAL !== 1000000) throw new Error(`capital changed to ${CAPITAL} — re-derive the documented base-capital floors`);

// the three sleeves, their allocation (read out of the parent so a doc drift cannot pass) and slots
const ALLOC = {};
for (const m of src.matchAll(/^\s+'(etf|small_cap|white_horse)': ([0-9.]+),?$/gm)) ALLOC[m[1]] = parseFloat(m[2]);
console.log('STRATEGY_ALLOCATION read from parent:', JSON.stringify(ALLOC));
const SLEEVES = [
  { name: 'small_cap', slots: 6, alloc: ALLOC.small_cap },
  { name: 'etf', slots: 1, alloc: ALLOC.etf },
  { name: 'white_horse', slots: 20, alloc: ALLOC.white_horse },
];
if (Math.abs(ALLOC.etf - 0.4) > 1e-12 || Math.abs(ALLOC.small_cap - 0.35) > 1e-12 || Math.abs(ALLOC.white_horse - 0.25) > 1e-12) {
  throw new Error('STRATEGY_ALLOCATION is not {etf 0.4, small_cap 0.35, white_horse 0.25}');
}
const baseFloor = s => CAPITAL * s.alloc / s.slots / OVR;
for (const s of SLEEVES) console.log(`  base floor ${s.name.padEnd(12)} = ${CAPITAL} x ${s.alloc} / ${s.slots} / ${OVR} = ${baseFloor(s).toExponential(3)} CNY/day`);

function edit(s, from, to, tag) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`[${tag}] expected exactly 1 match, got ${n}: ${JSON.stringify(from.slice(0, 160))}`);
  return s.replace(from, to);
}

// ================================================================== the variant builder
function build(id, mult, note) {
  const HEADER = [
    '# ============================================================================',
    `# ${id} 变体：多因子ML 冠军 d02cde29 —— 逐仓「可成交下限」(fill-feasibility floor)${note}`,
    '#',
    '# 【为什么跑这一测】',
    '#   本家族在 integrate-eligible 被 REJECTED，唯一阻断是 realizability: 1，owner=none ——',
    '#   没有任何别的阶段会去清它。而那个 1 是 prose：realizabilityBasis 引的是一句关于 headline',
    '#   「水平」不可达的话，与「日线 bar 撑不起这笔成交」是两回事；realizability-lint 在本书上零 flag。',
    '#   本测把猜测换成测量，无论数字落在哪一边。',
    '#',
    '# 【父本】',
    `#   study/多因子ML/baseline-e6.py  sha256 ${parentSha}  (43002 chars)`,
    '#   == py2to3(strategies/2026-06-28_高质量稳定上涨策略-d02cde29.py) + 当前 frozen OVERRIDE，逐字相同。',
    '#   父本实测（epoch 9, TRAIN 2024-01-01..2024-12-31）：',
    '#     objective 1.4731 / sharpe 5.45 / annual 156.71 / maxDD 9.40',
    `#   曲线：data/series/${path.basename(PARENT_CURVE)}（${pc.points} 点，${pc.start}..${pc.end}，final cum ${finalCum}）`,
    '#   ⇒ 对照不欠 backtest。本变体与父本只差「可成交下限」一个维度。',
    '#',
    '# 【地板算术 —— 由 harness 推出，不是我们挑的数，且没有自由参数】',
    `#   harness epoch ${hc.epoch}: costs.capital = ${CAPITAL}, costs.orderVolumeRatio = ${OVR}`,
    '#   某仓要在「一只标的」上建 V 元的仓，而一天最多只能吃掉该标的成交额的 order_volume_ratio，',
    '#   所以要求该标的日成交额 >= V / order_volume_ratio。V 本身逐日由 LIVE 市值算出：',
    '#     V = context.portfolio.total_value x STRATEGY_ALLOCATION[sleeve] / n_slots',
    '#   因此地板随净值复利自动放大（本书 2024 年 +156.71%，年末约为年初的 2.5 倍），',
    '#   不是一个静态阈值。按 1e6 本金折算到年初：',
    ...SLEEVES.map(s => `#     ${s.name.padEnd(12)} alloc ${s.alloc} / ${String(s.slots).padStart(2)} 槽 ⇒ ${(baseFloor(s) * mult).toExponential(3)} CNY/日` + (mult === 1 ? '  （= 可成交下限本身）' : `  （= 下限 x ${mult}）`)),
    `#   LIQ_FLOOR_MULT = ${mult.toFixed(1)}` + (mult === 1
      ? '  —— 恰为可成交最小值，不是一个「舒适水位」。'
      : `  —— ${mult} 倍余量，用来问「容量天花板」这个另一个问题（本变体建好但不跑）。`),
    '#',
    '# 【流动性度量】',
    "#   get_price(codes, count=20, end_date=context.previous_date, fields=['money'], frequency='1d')",
    '#   的 20 bar 中位数。用中位数而不是均值：一天的放量不得把一只平常没量的标的放进来。',
    '#   end_date 是前一交易日 ⇒ 今天要成交的那根 bar 永不被查询，无未来函数。',
    '#   取数失败 → log.error 一条 LIQFLOOR ERROR 并原样返回（LOUD，不静默跳过）：静默失败会',
    '#   逐字复现父本，和「地板什么都没剔掉」不可区分 —— 而后者恰恰是 大小盘轮动 / b3751277 的',
    '#   liq-1 实际得到的答案，必须可信。',
    '#',
    '# 【三处选股点（本书三仓各一处），别无其他】',
    '#   (1) small_cap：small_cap_get_stocks 的 return 之前，行业分散之后、[:stock_num*2] 之前',
    '#       （周二调仓与 small_cap_check_remain 补仓两个调用点自动都被覆盖）',
    '#   (2) etf     ：etf_trade 里排序后的候选名单上、[:target_num] 切片之前（auto/fixed 两支都插）',
    '#   (3) white_horse：white_horse_select_big 与 white_horse_select_small 的 return',
    '#   逐仓打 LIQFLOOR 行（sleeve / site / date / floor / in / out / removedFrac / slots / removed），',
    '#   归因因此免费附带。用 log.error 而不是 log.info，因为本书有三处 log.set_level。',
    '#',
    '# 【刻意不碰】',
    '#   动量/ATR 动态窗口/溢价率扣分、小市值的市值排序与行业分散、白马的三档市场温度与因子筛，',
    '#   止损、空仓月、调度表、三个成本 pin 与文件尾部 frozen OVERRIDE，全部逐字不动。',
    '#   white_horse_adjust 的 else 支（config[\'foreign_etfs\'] 四只宽基）没有被地板筛 —— 它不是',
    '#   dispatch 指名的选股点，且是四只大 ETF；这一点明写出来，不是遗漏。',
    '#',
    '# ⚠ 【这是 STRICT 版，不是 buy-side 下界】',
    '#   与 study/ETF动量/variants/q-e9-3_liq-1.py 的约定一致：不对已持仓名字豁免。被地板剔除的',
    '#   名字会从 target_list 消失，于是下一次调仓的卖出逻辑会把它卖掉。这是「拿不进来的名字也',
    '#   拿不住」的严格读法，而不是 五福闹新春 q-e9-liq 的买入侧下界读法。',
    '#',
    '# 【判据（跑前固定，两个方向都已写死）】',
    '#   INERT：三仓每次 rebalance 的 removedFrac 全为 0 且与父本曲线 max|Δcum| == 0',
    '#          ⇒ R=1 的「成交」这一条被测量否证，fills 上挣到 R>=2（另三条 realism 腿',
    '#          —— 事后池、日线止损坍塌、n=2 日历规则 —— 仍然开放，所以只能挣到 2，绝不是 3）',
    '#   BITES：sharpe < 1.0 或 Δobjective < -0.6 ⇒ R=1 由测量确证，本家族继续按证据被拒',
    '#   其余  ⇒ partial：报逐仓 removedFrac 分布，并指出是哪一仓在咬',
    '# ============================================================================',
    '',
  ].join('\n');

  // ---------------------------------------------------------------- edit (1) the helper block
  const FROM1 = '# ==================== 初始化函数 ====================\n';
  const INS1 = [
    `# ==================== ${id}: 可成交下限（fill-feasibility floor） ====================`,
    `# 全部由 harness epoch ${hc.epoch} 推出：costs.capital = ${CAPITAL}, costs.orderVolumeRatio = ${OVR}。`,
    '# 这两个常量在 JQ 服务器上跑，读不到 harness/config/epoch-9.json，所以是 builder 写进来的',
    '# 字面量；build-e9-liq.js 从 utils/harness-config 读出同一个值并断言，绝不手抄。',
    `LIQ_ORDER_VOLUME_RATIO = ${OVR}      # harness costs.orderVolumeRatio（由 frozen OVERRIDE 钉住）`,
    'LIQ_LOOKBACK = 20                  # 20 bar 中位成交额',
    `LIQ_FLOOR_MULT = ${mult.toFixed(1)}` + (mult === 1
      ? '                 # 1.0 = 可成交最小值本身，没有余量，没有自由参数'
      : `                 # ${mult} 倍余量 —— 容量问题，不是可行性问题`),
    'LIQ_SLOTS = {' + SLEEVES.map(s => `'${s.name}': ${s.slots}`).join(', ') + '}  # 每仓的槽位数',
    '',
    '',
    'def liq_floor_for(context, sleeve):',
    '    """逐仓、逐次调用的 DYNAMIC 地板，没有自由参数。',
    '',
    '    某仓要在一只标的上建 V 元的仓：',
    '        V = context.portfolio.total_value * STRATEGY_ALLOCATION[sleeve] / LIQ_SLOTS[sleeve]',
    '    一天最多吃掉该标的成交额的 LIQ_ORDER_VOLUME_RATIO，所以要求日成交额 >= V / ratio。',
    '    随净值复利自动放大，不是静态阈值。',
    '    """',
    '    slots = float(max(1, LIQ_SLOTS[sleeve]))',
    '    pos = float(context.portfolio.total_value) * float(STRATEGY_ALLOCATION[sleeve]) / slots',
    '    return pos / float(LIQ_ORDER_VOLUME_RATIO) * float(LIQ_FLOOR_MULT)',
    '',
    '',
    'def filter_liquidity_floor(context, sleeve, site, stock_list):',
    '    """保留 20 bar 中位日成交额 >= 本仓地板的名字。',
    '',
    '    中位数而非均值：一天放量不得放进一只平常没量的标的。',
    '    end_date=context.previous_date ⇒ 今天要成交的那根 bar 永不被查询。',
    '    每次调用打一条 LIQFLOOR 行，用 log.error 以穿过本书的三处 log.set_level。',
    '    """',
    '    stock_list = list(stock_list)',
    '    n_in = len(stock_list)',
    '    floor = liq_floor_for(context, sleeve)',
    '    if n_in == 0:',
    "        log.error('LIQFLOOR sleeve=%s site=%s date=%s floor=%.0f in=0 out=0 removedFrac=NA slots=0 removed=- status=empty' % (",
    '            sleeve, site, str(context.previous_date), floor))',
    '        return []',
    '    try:',
    '        df = get_price(stock_list, count=LIQ_LOOKBACK, end_date=context.previous_date,',
    "                       fields=['money'], frequency='1d', panel=False)",
    "        med = df.groupby('code')['money'].median()",
    '        keep = [s for s in stock_list if (s in med.index) and (med[s] >= floor)]',
    '    except Exception as e:',
    '        # LOUD，绝不静默：静默失败会逐字复现父本，和「地板什么都没剔掉」不可区分 ——',
    '        # 而后者正是 大小盘轮动 / b3751277 的 liq-1 得到的答案，必须可信。',
    "        log.error('LIQFLOOR ERROR sleeve=%s site=%s date=%s floor=%.0f in=%d exc=%s' % (",
    '            sleeve, site, str(context.previous_date), floor, n_in, str(e)))',
    '        return stock_list',
    '    removed = [s for s in stock_list if s not in keep]',
    "    log.error('LIQFLOOR sleeve=%s site=%s date=%s floor=%.0f in=%d out=%d removedFrac=%.4f slots=%d removed=%s status=ok' % (",
    '        sleeve, site, str(context.previous_date), floor, n_in, len(keep),',
    '        1.0 - float(len(keep)) / float(n_in), min(LIQ_SLOTS[sleeve], len(keep)),',
    "        ';'.join(removed) or '-'))",
    '    return keep',
    '',
    '',
  ].join('\n');

  // ---------------------------------------------------------------- edit (2) small_cap selection
  const FROM2 = [
    '    # 行业分散',
    '    stock_list = small_cap_get_stock_industry(stock_list)',
    "    final_list = stock_list[:config['stock_num']*2]",
  ].join('\n');
  const TO2 = [
    '    # 行业分散',
    '    stock_list = small_cap_get_stock_industry(stock_list)',
    `    # ${id}: 可成交下限（切片之前 ⇒ 被剔掉的名字由下一名顶上，而不是留空槽）`,
    "    stock_list = filter_liquidity_floor(context, 'small_cap', 'get_stocks', stock_list)",
    "    final_list = stock_list[:config['stock_num']*2]",
  ].join('\n');

  // ---------------------------------------------------------------- edit (3) etf candidate list
  const FROM3 = [
    "    if config['auto_day']:",
    '        target_list, rank_info = etf_get_rank_auto(context, return_info=True)',
    "        target_list = target_list[:config['target_num']]",
    '    else:',
    '        target_list, rank_info = etf_get_rank_fixed(context, return_info=True)',
    "        target_list = target_list[:config['target_num']]",
  ].join('\n');
  const TO3 = [
    "    if config['auto_day']:",
    '        target_list, rank_info = etf_get_rank_auto(context, return_info=True)',
    `        # ${id}: 可成交下限，作用在排序后的候选名单上、[:target_num] 切片之前`,
    "        target_list = filter_liquidity_floor(context, 'etf', 'rank_auto', target_list)",
    "        target_list = target_list[:config['target_num']]",
    '    else:',
    '        target_list, rank_info = etf_get_rank_fixed(context, return_info=True)',
    `        # ${id}: 同上（本书 auto_day=True，这一支不会跑，插上以免两支语义不一致）`,
    "        target_list = filter_liquidity_floor(context, 'etf', 'rank_fixed', target_list)",
    "        target_list = target_list[:config['target_num']]",
  ].join('\n');

  // ---------------------------------------------------------------- edit (4) white_horse_select_big
  const FROM4 = [
    '    return list(get_fundamentals(q).code)',
    '',
    'def white_horse_select_small(context):',
  ].join('\n');
  const TO4 = [
    `    # ${id}: 可成交下限`,
    "    return filter_liquidity_floor(context, 'white_horse', 'select_big', list(get_fundamentals(q).code))",
    '',
    'def white_horse_select_small(context):',
  ].join('\n');

  // ---------------------------------------------------------------- edit (5) white_horse_select_small
  const FROM5 = [
    '    current_data = get_current_data()',
    '    return [s for s in final_list ',
    "           if s in context.portfolio.positions or current_data[s].last_price <= config['max_stock_price']]",
  ].join('\n');
  const TO5 = [
    '    current_data = get_current_data()',
    `    # ${id}: 可成交下限`,
    "    return filter_liquidity_floor(context, 'white_horse', 'select_small', [s for s in final_list ",
    "           if s in context.portfolio.positions or current_data[s].last_price <= config['max_stock_price']])",
  ].join('\n');

  const EDITS = [
    ['1-helpers', FROM1, INS1 + FROM1],
    ['2-small_cap', FROM2, TO2],
    ['3-etf', FROM3, TO3],
    ['4-wh_big', FROM4, TO4],
    ['5-wh_small', FROM5, TO5],
  ];

  let out = src;
  for (const [tag, from, to] of EDITS) {
    out = edit(out, from, to, tag);
    console.log(`  edit ${tag}: FROM matched exactly once`);
  }
  const variant = HEADER + out;

  // ================================================================ ASSERTIONS
  // Counts are taken on `out` (the variant MINUS our own header prose): the header quotes several
  // markers, and counting the whole file makes an assertion fail on its own documentation — the
  // build-siblings.js lesson in CLAUDE.md.
  const fail = [];
  const A = (ok, msg) => { console.log((ok ? '  OK   ' : '  FAIL ') + msg); if (!ok) fail.push(msg); };

  // --- (a) THE REFUSAL CONDITION: reversing exactly our 5 edits restores the parent BYTE-FOR-BYTE.
  // This is the "changed-line set is exactly the intended insertion sites" check — it subsumes
  // every per-marker count, because nothing else in the file can have moved.
  let restored = out;
  for (const [tag, from, to] of EDITS) {
    const n = restored.split(to).length - 1;
    A(n === 1, `edit ${tag}: its TO text appears exactly once in the variant`);
    restored = restored.replace(to, from);
  }
  A(restored === src, 'reversing exactly the 5 edits restores the parent BYTE-FOR-BYTE');

  // --- (b) the diff touches only the 5 intended regions, and REMOVES only the 3 return/slice
  // lines it must rewrite (the other 2 edits are pure insertions).
  const diffOut = (() => {
    let d = '';
    try { execFileSync('diff', ['-u', PARENT, '/dev/stdin'], { input: variant, encoding: 'utf8' }); }
    catch (e) { d = e.stdout; }
    return d;
  })();
  // 6 regions: our header (top of file), the helper block (before 初始化函数), and the 4 call sites
  // (small_cap, etf, white_horse_select_big, white_horse_select_small).
  const hunks = (diffOut.match(/^@@/gm) || []).length;
  A(hunks === 6, `diff has exactly 6 hunks (header + helpers + 4 call sites) — got ${hunks}`);
  const removedLines = diffOut.split('\n').filter(l => l.startsWith('-') && !l.startsWith('---')).map(l => l.slice(1));
  const EXPECT_REMOVED = [
    '    return list(get_fundamentals(q).code)',
    '    return [s for s in final_list ',
    "           if s in context.portfolio.positions or current_data[s].last_price <= config['max_stock_price']]",
  ];
  A(removedLines.length === EXPECT_REMOVED.length && removedLines.every((l, i) => l === EXPECT_REMOVED[i]),
    `diff removes exactly the ${EXPECT_REMOVED.length} white_horse return lines it rewrites (got ${removedLines.length})`);
  removedLines.forEach(l => console.log('       removed:', JSON.stringify(l.slice(0, 110))));

  // --- (c) the frozen cost block is the tail, byte-identical, and never hand-copied
  A(variant.endsWith(OVERRIDE), 'frozen OVERRIDE cost block is the file tail, byte-identical');

  // --- (d) cost pins and mechanism knobs unchanged, counted on the RESTORED text so our own prose
  // cannot flatter the count
  for (const marker of ['avoid_future_data', 'set_order_cost', 'set_slippage',
    "'target_num': 1", "'stock_num': 6", "'stock_num': 20", "'m25_days': 25",
    "'premium_threshold': 5.0", "'stoploss_limit': 0.91", "'max_stock_price': 50",
    "'etf': 0.4", "'small_cap': 0.35", "'white_horse': 0.25"]) {
    const a = src.split(marker).length - 1, b = restored.split(marker).length - 1;
    A(a === b && a > 0, `marker count unchanged: ${marker} (${a} -> ${b})`);
  }

  // --- (e) scheduling table byte-identical
  const sched = s => s.split('\n').map(l => l.trim()).filter(l => /^run_(daily|weekly|monthly)\(/.test(l));
  const sA = sched(src), sB = sched(out);
  A(sA.length === sB.length && sA.every((l, i) => l === sB[i]),
    `run_daily/weekly/monthly schedule byte-identical (${sA.length} lines)`);

  // --- (f) the floor is derived at runtime from the harness constants; no magic threshold in code
  const insCode = EDITS.map(([, , to]) => to).join('\n').split('\n')
    .filter(l => !/^\s*#/.test(l)).map(l => l.replace(/\s+#.*$/, '')).join('\n');
  A(insCode.includes('pos = float(context.portfolio.total_value) * float(STRATEGY_ALLOCATION[sleeve]) / slots'),
    'the floor is computed from LIVE context.portfolio.total_value each call (DYNAMIC)');
  A(insCode.includes('return pos / float(LIQ_ORDER_VOLUME_RATIO) * float(LIQ_FLOOR_MULT)'),
    'the floor divides by order_volume_ratio — the fill-feasibility minimum, not a chosen level');
  A(!/\b(1\.17e6|8\.0e6|0\.25e6|1170000|8000000|250000)\b/.test(insCode),
    'no per-sleeve floor VALUE is hard-coded in the inserted code');
  for (const forbidden of ['set_order_cost', 'set_slippage', 'set_commission', 'set_option',
    'premium_threshold', 'stoploss', 'm25_days', 'market_temp']) {
    A(!insCode.includes(forbidden), `inserted code does not touch: ${forbidden}`);
  }
  // ⚠ `target_num` and `max_stock_price` CANNOT be on that forbidden list: edits 3 and 5 are
  // REPLACEMENTS, so they necessarily re-emit the parent's own slice line and price-filter
  // comprehension verbatim. The right test for a replacement is that the marker's count in the
  // VARIANT equals its count in the PARENT — i.e. the knob was carried through, not altered or
  // duplicated. (A check that reads a carried-through line as a new edit fails on the right answer
  // — the build-siblings.js lesson.)
  // ⚠ Counted on CODE LINES ONLY in both texts: our own inserted comment says "[:target_num] 切片
  // 之前", and counting prose made this assertion fail on the correct build — again the
  // build-siblings.js lesson, which is that a check reading prose as code fails on the right answer.
  const codeText = s => s.split('\n').filter(l => !/^\s*#/.test(l)).map(l => l.replace(/\s+#\s.*$/, '')).join('\n');
  const srcCode = codeText(src), outCode = codeText(out);
  for (const carried of ["config['target_num']", "config['max_stock_price']", 'target_num', 'max_stock_price']) {
    const a = srcCode.split(carried).length - 1, b = outCode.split(carried).length - 1;
    A(a === b && a > 0, `knob carried through unchanged in the VARIANT (code lines only): ${carried} (${a} -> ${b})`);
  }
  A((out.match(new RegExp(`^LIQ_ORDER_VOLUME_RATIO = ${String(OVR).replace('.', '\\.')}`, 'm')) || []).length === 1,
    `LIQ_ORDER_VOLUME_RATIO literal equals harness orderVolumeRatio (${OVR})`);
  A((out.match(/^LIQ_SLOTS = \{'small_cap': 6, 'etf': 1, 'white_horse': 20\}/m) || []).length === 1,
    'LIQ_SLOTS = {small_cap 6, etf 1, white_horse 20}');
  A((out.match(new RegExp(`^LIQ_FLOOR_MULT = ${mult.toFixed(1).replace('.', '\\.')}`, 'm')) || []).length === 1,
    `LIQ_FLOOR_MULT literal is ${mult.toFixed(1)}`);

  // --- (g) the floor is a pure read + log: it can never place, cancel or size an order
  const hs = out.indexOf('def liq_floor_for(context, sleeve):');
  const he = out.indexOf('# ==================== 初始化函数 ====================');
  A(hs > 0 && he > hs, 'helper block located');
  const helpers = out.slice(hs, he);
  const TRADE_RE = /\b(order|order_target|order_value|order_target_value|strategy_open_position|strategy_open_position_add|strategy_close_position|close_position|open_position)\s*\(/;
  A(!TRADE_RE.test(helpers), 'helper block calls no order/position function');
  A(!/\bg\.\w+\s*=[^=]/.test(helpers), 'helper block assigns no g.* (pure read + log)');
  A(/get_price\(stock_list, count=LIQ_LOOKBACK, end_date=context\.previous_date,/.test(helpers),
    'liquidity is read on context.previous_date (no future data)');
  A(/\.median\(\)/.test(helpers) && !/\.mean\(\)/.test(helpers),
    'MEDIAN of the 20 bars, never the mean');
  A(/except Exception as e:/.test(helpers) && /LIQFLOOR ERROR/.test(helpers) && !/\n\s+pass\n/.test(helpers),
    'the except is LOUD (logs LIQFLOOR ERROR), never a silent pass');

  // --- (h) exactly 4 call sites, one per selection site (etf has 2 branches, only 1 can run)
  const codeOnly = out.split('\n').filter(l => !/^\s*#/.test(l)).join('\n');
  A((codeOnly.match(/filter_liquidity_floor\(context, '/g) || []).length === 5,
    'exactly 5 filter_liquidity_floor call sites (small_cap 1 + etf 2 branches + wh 2)');
  for (const [sl, st, n] of [['small_cap', 'get_stocks', 1], ['etf', 'rank_auto', 1], ['etf', 'rank_fixed', 1],
    ['white_horse', 'select_big', 1], ['white_horse', 'select_small', 1]]) {
    A((codeOnly.match(new RegExp(`filter_liquidity_floor\\(context, '${sl}', '${st}'`, 'g')) || []).length === n,
      `exactly ${n} call site for sleeve=${sl} site=${st}`);
  }
  A((codeOnly.match(/def filter_liquidity_floor\(/g) || []).length === 1
    && (codeOnly.match(/def liq_floor_for\(/g) || []).length === 1, 'each helper defined exactly once');

  // --- (i) the census lines are bare log.error and cannot influence a decision
  const liqStmts = out.split('\n').filter(l => l.includes("'LIQFLOOR "));
  A(liqStmts.length === 3, `3 LIQFLOOR log statements (ok + empty + ERROR), got ${liqStmts.length}`);
  A(liqStmts.every(l => /^\s*log\.error\('LIQFLOOR /.test(l)),
    'every LIQFLOOR statement starts as a bare log.error( — survives log.set_level');
  const vlines = variant.split('\n');
  for (let i = 0; i < vlines.length; i++) {
    if (!/^\s*log\.error\('LIQFLOOR /.test(vlines[i])) continue;
    let j = i, expr = '', bal = 0;
    do { expr += vlines[j] + '\n'; for (const ch of vlines[j]) { if (ch === '(') bal++; if (ch === ')') bal--; } j++; }
    while (bal > 0 && j < vlines.length);
    A(!/\bg\.\w+\s*=[^=]/.test(expr), `LIQFLOOR stmt at line ~${i + 1} assigns no g.*`);
    A(!/\.sort\(|\.append\(|\.pop\(|\bdel\s/.test(expr), `LIQFLOOR stmt at line ~${i + 1} has no sort/append/pop/del`);
    A(!TRADE_RE.test(expr), `LIQFLOOR stmt at line ~${i + 1} places no order`);
  }
  for (const f of ['sleeve=', 'site=', 'date=', 'floor=', 'in=', 'out=', 'removedFrac=', 'slots=', 'removed=', 'status=']) {
    A(out.split("'LIQFLOOR sleeve=%s site=%s date=%s floor=%.0f in=%d out=%d removedFrac=%.4f slots=%d removed=%s status=ok'").length === 2
      && out.includes(f), `census field present: ${f}`);
  }

  if (fail.length) {
    console.error(`\n${fail.length} ASSERTION(S) FAILED for ${id} — REFUSING to write the variant`);
    fail.forEach(m => console.error('  - ' + m));
    return { id, ok: false, diff: diffOut };
  }
  const outDir = path.join(__dirname, 'variants');
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, `${id}.py`);
  fs.writeFileSync(outFile, variant);
  console.log(`  wrote ${path.relative(ROOT, outFile)} (${Buffer.byteLength(variant)} bytes, ${variant.length} chars)`);
  console.log('  sha256', crypto.createHash('sha256').update(variant).digest('hex'));
  return { id, ok: true, diff: diffOut, file: outFile };
}

// ================================================================== emit the three variants
const results = [];
for (const [id, mult, note] of [
  ['q-e9-liq-1', 1, '（可成交最小值，1x —— 本次要跑的那个）'],
  ['q-e9-liq-2', 5, '（5x 余量 —— 容量问题，建好但不跑）'],
  ['q-e9-liq-3', 10, '（10x 余量 —— 容量问题，建好但不跑）'],
]) {
  console.log(`\n================ ${id}  (LIQ_FLOOR_MULT = ${mult}) ================`);
  results.push(build(id, mult, note));
}

const bad = results.filter(r => !r.ok);
if (bad.length) {
  console.error('\nREFUSED: ' + bad.map(r => r.id).join(', '));
  process.exitCode = 1;
} else {
  console.log('\n===== diff baseline-e6.py -> variants/q-e9-liq-1.py =====');
  console.log(results[0].diff);
}
