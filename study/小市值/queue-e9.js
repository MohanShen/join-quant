// Gatekeeper: append the epoch-9 round's gated/ranked entries to study/小市值/queue.json.
//
// Idempotent — refuses if any of this round's ids is already present.
// The entries target the UNSTUDIED champion
// strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py (objective 2.6282 / sharpe 7.07).

const fs = require('fs');
const path = require('path');

const P = path.join(__dirname, 'queue.json');
const q = JSON.parse(fs.readFileSync(P, 'utf8'));
if (q.some(e => /^q-e9-champ|^imp-e9|^q-e9-bench/.test(e.id))) {
  throw new Error('this round is already written — refusing');
}

const CHAMP = 'strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py';

const SECONDARY = [
  'PRE-REGISTERED FREE SECONDARY READ (on every entry, orchestrator ruling 3) — recompute the',
  "variant's objective EXCLUDING December 2024 from its stored curve, and compare with the control's",
  'Jan-Nov figure. CONTROL, recomputed by the gatekeeper from',
  'data/series/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa__train__e9.json:',
  '  full 2024  total 276.82 | annual 276.82 | maxDD 14.01 | objective 2.6281  (reproduces ledger 2.6282)',
  '  Jan-Nov    total 159.71 | annual 182.88 (365/335) | maxDD 14.01 | objective 1.6888',
  "  December alone +45.09% in 22 trading days = 28.1% of the year's LOG-growth.",
  '! The orchestrator\'s "~45% of the year" is the simple-return figure; the log-growth share is 28.1%,',
  '  and log-growth is the convention CLAUDE.md uses (the 62%-in-2022 precedent). Quote 28.1%.',
  "! maxDD is 14.01 in BOTH slices — the year's drawdown is NOT in December, so the Jan-Nov read moves",
  '  return only, never risk.',
  "!! Annualize over the SLICE'S CALENDAR SPAN (365 full / 335 Jan-Nov), never over the curve's own",
  '  trading-day count, and compute BOTH sides with the one formula. Self-annualizing each side',
  '  reported annual 298.05 / objective 2.8405 for a row the ledger stores as 2.6282.',
  'This is a ROBUSTNESS FALSIFIER, never the adoption metric. Adoption is always the full-2024 number.',
].join('\n');

const BUILD = [
  'BUILDER CONVENTION (mandatory, orchestrator ruling 1) — follow study/小市值/build-liq-5a70adc1.js:',
  '  raw = py2to3(readFileSync(<champion>)); out = raw.replace(SITE, EDIT) + <helper?> + OVERRIDE;',
  '  then ASSERT that undoing the single edit reproduces `raw` BYTE-FOR-BYTE, and throw otherwise.',
  '! "byte-for-byte" means against py2to3(raw), NOT against the file on disk — py2to3 runs first.',
  '! Assert on the pre-OVERRIDE body, not on a slice of the final string (the trailing-newline trap',
  '  that made build-liq-5a70adc1 report a false difference at line 840 of an 839-line file).',
  '! Also assert the edit site occurs EXACTLY ONCE in raw before replacing.',
  '! Never edit strategies/ — that layer is immutable.',
].join('\n');

const CTRL =
  "CONTROL = the champion's own epoch-9 ledger row: " + CHAMP +
  ', objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00, 365 days, curve on disk. ' +
  'No separate re-measure of the control is queued (orchestrator ruling 1): every builder uses the ' +
  'same exported py2to3 + OVERRIDE path the normalizer used, so a one-edit variant is directly ' +
  "comparable to 2.6282, and rank 26's inert case doubles as the build-path reproduction check.";

const add = [
  {
    id: 'q-e9-champ-liq',
    kind: 'understand',
    rank: 26,
    status: 'active',
    title: '流动性可行性下限 ¥1e7/日：当前 champion 0a7de9fa 吃得下自己的仓位吗',
    hypothesis:
      '假设：下限一个名字都不剔除（本书 market_cap.between(10,80) 已把 ¥10亿 以下全部排除，底仓名字本就不是微盘）。' +
      '预注册三分证伪，在看到数字前锁定：' +
      '(a) 剔除 0 个名字且曲线与 control 逐位相同 ⇒ 可行性在 ¥1e7 处 INERT，本支 R>=2，容量上限未测；' +
      '(b) 有名字被剔除但 objective 仍 >= 1.0 闸门 ⇒ R=2，被剔除的名字不是收益主体；' +
      '(c) 有名字被剔除且 sharpe < 1.0 或 objective < 1.5 ⇒ 2.6282 依赖填不满的名字，本支 R=1 与低开支同级，champion 不是候选。',
    why:
      '家族唯一 BINDING 的闭合 q-e9-liq-5a70adc1 明确开出这条：小市值 的 realizability 必须按「支」重新定界——' +
      'R=1 的依据（min-500 市值、9:26 竞价、~100% 换手）描述的是低开剥头皮支，' +
      '而 frontmatter 的 realizabilityScope 指的那本书已经不是 candidate。' +
      '本条是本族唯一能动其约束性瓶颈（realizability: 1）的测量，故排第一（orchestrator ruling 2）。成本 ~1-3 JQ 分钟。',
    design:
      '下限推导（全部来自本书自身仓位，非猜测）：capital 1,000,000 x proportion 1.0 / g.target_stock_count=2 (L111) ' +
      '= 500,000 每仓；epoch 4 钉死 order_volume_ratio=0.05，故单根日 bar 填满一仓需该 bar 成交额 ' +
      '>= 500,000 / 0.05 = 1e7 CNY/日。这是 FILL-FEASIBILITY MINIMUM，不是舒适水平。\n' +
      'SINGLE EDIT — L248 `    return bbi_pass` -> `    return filter_liquidity_floor(context, bbi_pass)`。' +
      '唯一插入点，位于 get_stock_list 末尾（即已通过全部其他筛选之后），所以只有真正的候选才付 20 根 bar 的代价。\n' +
      'helper 直接复用 build-liq-5a70adc1.js 的 filter_liquidity_floor：20 根日 bar 的 median `money`，' +
      '在 context.previous_date 求值（今天要交易的那根 bar 永不被查询），每次调用用 log.error 打一行 ' +
      '`LIQFLOOR floor= date= in= out= removedFrac= slots=`，异常走响亮分支而不是静默返回原表。\n' +
      '! 只建并只跑 liq-1（1e7）。liq-2 (5e7) / liq-3 (1e8) 的容量曲线现在就写进 builder 的 FLOORS 表以免日后按口味补点，' +
      '但 NOT QUEUED —— 只有 liq-1 过了才值得花分钟。\n' +
      '! 报告必须数 LIQFLOOR 行里 in>out 的次数。「Δ=0」只有在没有一行 in>out 时才是 INERT；' +
      '否则是「剔了但不影响」，是不同的结论。',
    from: [
      'q-e9-liq-5a70adc1 (BINDING closure — explicitly opens this direction for this family)',
      'study-b3751277-liq-1 (同族另一本：下限 INERT，objective 1.3443 -> 1.3443)',
      '大小盘轮动 liq-1 (31/31 次 rebalance 剔除 0 个，曲线逐位相同)',
      'ETF溢价 liq (sharpe 8.44 -> 1.10，反例；小市值 7/8 不可成交)',
      'q-e6-13 / q-e6-15 / q-e6-18 (低开支的 100x 深度单位缺陷 + 仓位纪律)',
      'wiki/families/小市值.md frontmatter realizability: 1 / realizabilityScope',
    ],
    edgeRef: '规模',
    control: CTRL,
    secondaryRead: SECONDARY,
    consequenceIfAdopted:
      '落在 (b) 时，带下限的那本书——而不是裸 champion——才是本族 candidate，objective 以带下限的数字为准。' +
      '落在 (a) 时，champion 原样即是可成交形态，并同时证明 builder 路径能复现 control（2.6282 / 逐位相同）。',
  },
  {
    id: 'q-e9-bench-lastprice',
    kind: 'understand',
    rank: 27,
    status: 'open',
    title: '台面语义：日频台上 get_current_data()[s].last_price 是否等于当日收盘价',
    hypothesis:
      'harness 的 costs.frequency 是 "daily"（已核 harness/config/epoch-9.json），' +
      'JQ 日频回测里 run_daily 的时间串只决定当日内的执行顺序，所有 handler 共享同一根日 bar。' +
      '预注册证伪：若 9:00 / 10:30 / 14:00 三个时点记录到的 last_price 彼此不同，或任一时点不等于该股当日 close ' +
      '⇒ 语义干净，本条关闭，2.6282 不因此被质疑。' +
      '若三者相同且等于当日 close ⇒ 2.6282 不是一个结果，必须按前视重读，' +
      '且该结论外推到全库所有盘中调用 get_current_data 的成员。',
    why:
      '这是本轮唯一能一次性作废其余全部条目的测量，故紧随 liq。本书把 get_current_data().last_price 用在四处决策上：' +
      'L376 顶背离清仓时「未涨停才清」、L742 now_high_limit 决定调仓日保留谁、L309 current_price >= avg_cost*1.4 止盈、' +
      'L318 跌破 7% 止损；check_limit_up 还用 get_price(end_date=context.current_dt) 取「当前价」与涨停价比。' +
      '若这些读到的是当日收盘，那么「涨停就留着」「跌 7% 就走」都是用当天答案做当天决定。' +
      '§4 已把「买一档数据在日频台上的语义」列为 open gap；' +
      'CLAUDE.md 只测过 get_extras(is_st) 与无日期 get_fundamentals 两条，本条从未测。',
    design:
      'STEP 0 — 先免费试，不花分钟：存盘曲线 data/series/2026-10-26_..._0a7de9fa__train__e9.json 里带着本次运行的 backtestId。' +
      '先用 `node utils/backtest-log.js --backtestId <id>`（分页 offset 取满）读已有日志——' +
      '本书自带 L552/L558 的「涨停打开（当前价: X < 涨停价: Y）」与 L311 的止盈日志；' +
      '若其中能看出「当前价」恒等于当日收盘，问题零成本就答了。日志已被 JQ 回收或信息不足时才进 STEP 1。\n' +
      'STEP 1 — 探针变体，不改任何交易逻辑：在 dapan(9:00)、sell_stocks(10:30)、trade_afternoon(14:00) 各插一行 log.error，格式 ' +
      '`BENCHSEM t=<handler> date=<d> code=<s> last=<v> high_limit=<v> open=<v> prev_close=<v>`。' +
      '每个 handler 每天只打一行（取 g.hold_list 的第一只，无持仓时打 code=NONE），' +
      '否则 242 天 x 多持仓会把日志撑过 limit；取回时按 offset 分页直到取尽。' +
      '离线对比：同一天三个时点的 last 是否相同、是否等于该股当日 close' +
      '（当日 close 用 get_price 事后在 Node 侧核对，不在策略内取）。\n' +
      '! CONTROL 内建：探针只增加 log.error，不得改动任何条件、下单或参数，所以回测指标必须与 champion 行逐位相同；' +
      '若不同，说明插入点改变了行为，整次测量作废重建。',
    from: [
      'harness/config/epoch-9.json costs.frequency = "daily"（gatekeeper 已核）',
      '§4 open gap 「买一档数据在日频台上的语义」',
      'q-e6-13 / q-e6-19 (本族已有一次单位/语义误读把头条抬高 ~8.6x 的先例)',
      'CLAUDE.md: 两条社区前视主张已测并未复现；本条未测',
      'CLAUDE.md: 回测日志可用 utils/backtest-log.js 取回（旧说法「不可取」已被推翻）',
    ],
    edgeRef: null,
    edgeRefNote: '无 edge —— 这是台面语义，不是机制主张。按 understand 判：两个方向都是信息。',
    control: CTRL,
    secondaryRead: SECONDARY,
  },
  {
    id: 'q-e9-champ-emptymonth',
    kind: 'understand',
    rank: 28,
    status: 'open',
    title: '归因 EMPTY_MONTHS=[1,4]：2.6282 里有多少是「2026 年作者写下的一月空仓」',
    hypothesis:
      'gatekeeper 已从存盘曲线测实的前提：本书 2024 年 1 月只赚 +0.11%（当月持 511880 现金 ETF），' +
      '而 2024 年 1 月正是微盘踩踏月。预注册双向读数，在看到数字前锁定：' +
      '(a) Δobjective > -0.5 ⇒ 日历空仓不是收益主体，2.6282 可以不带这条注脚引用；' +
      '(b) Δobjective < -0.5 ⇒ 一个实打实的份额来自「一月不开仓」，' +
      '而该规则由一位 2026 年的作者写在一本 2024 年 TRAIN 的书里，所以这不是 edge 而是 HINDSIGHT，' +
      '量级必须带注脚引用，与「池子是一个 2026 年事后写的池子」同类。' +
      '! (b) 是坏消息不是好消息：它不开出任何 improve。',
    why:
      '这是 champion 上最便宜也最直接的事后性测量。本书文件名日期 2026-10-26、TRAIN 是 2024，' +
      '作者写 [1,4] 时已经知道 2024 年 1 月发生了什么。' +
      '曲线已证：1 月 +0.11%，且全年与 Jan-Nov 的 maxDD 都是 14.01——即 1 月既没贡献收益也没贡献回撤，它是被「跳过」的。' +
      '消融后这本书会在 1 月持微盘；若那一个月把 14.01 的回撤顶上去，就说明 2.6282 的低回撤是一条日历规则买来的。',
    design:
      'SINGLE EDIT — L29 `EMPTY_MONTHS = [1,4,]` -> `EMPTY_MONTHS = []`。' +
      '不改 close_account / trading_signal / g.pass_months 的任何代码路径，让空仓机器照常求值并恒为 False。\n' +
      '! 明确不做：不换月份、不加月份、不只去掉 1 月留下 4 月。' +
      'q-e6-4 的旋钮半边（换月份只会拟合当年）在一年期 TRAIN 上只会更成立；本条只做归因，不做调参。\n' +
      '报告必须给出消融后的分月收益表与 1 月单月回撤，而不只是 Δobjective。' +
      'control 的分月表（gatekeeper 已算，免费）：01 +0.11 / 02 +8.63 / 03 +15.69 / 04 +3.05 / 05 -9.28 / ' +
      '06 +2.36 / 07 +2.87 / 08 +8.20 / 09 +22.46 / 10 +17.20 / 11 +35.04 / 12 +45.09。',
    from: [
      'q-e6-4 (STALE closure, epoch 6 — 它关的是「调月份」这个 improve 旋钮，且测在 base 7a1c225f 上。' +
        '本条是 champion 上的归因消融，不是重复；且该闭合的理由是 WINDOW-level（「只会拟合 2022」），按契约属可重开类)',
      'gatekeeper 从存盘曲线算出的分月表：2024-01 +0.11%，Jan-Nov 与全年 maxDD 同为 14.01',
      'ETF动量 / 七星高照「池子是 2026 年事后写的」的事后性论证形状（MECHANISM 类，跨台成立）',
    ],
    edgeRef: '规模',
    edgeRefNote: 'off-mechanism check —— 日历空仓不属于本族任一 measured edge；本条测的就是它占了多少。',
    control: CTRL,
    secondaryRead: SECONDARY,
  },
  {
    id: 'q-e9-champ-bbi-off',
    kind: 'understand',
    rank: 29,
    status: 'open',
    title: 'edge test 中期趋势带(BBI)：把 L243 的带状条件改成无条件通过',
    hypothesis:
      '假设：若「既不弱也不过热」这条带是选择性来源，去掉后 TRAIN 年化损失过半。' +
      '预注册证伪：年化 >= control 的 85%（>= 235.3%）且 sharpe 与 control 相差在 1.0 以内 ⇒ edge 被 REFUTED，' +
      '新 edge 提案当场 WITHDRAWN，champion 就只是一本「规模 + 一个不起作用的叠加层」，' +
      '对 integration 而言与本族其余成员冗余。',
    why:
      '代码审计（零成本）发现 L243 的条件与它自己上一行的注释矛盾：注释写「收盘价在BBI上方」，' +
      '代码写 bbi*0.9 < prev_close < bbi*1.3 —— 一条带，下沿还在 BBI 下方 10%。' +
      '这不是「趋势向上」，是「既不弱也不过热」。本族另有一位成员 7da05cc8 也是 BBI 书，' +
      '所以这可能是一条本族尚未登记的 edge，而不是这一本的装饰。' +
      'champion 目前 UNSTUDIED，族页 §1/§2/§6 描述的还是低开剥头皮支 7a1c225f（现仅第 13，1.1627），' +
      '所以本族对 champion 的机制一条都没有。',
    design:
      'SINGLE EDIT — L243 `        if bbi*0.9 < prev_close < bbi*1.3:` -> `        if True:`。' +
      '保留 >=24 根 bar 的数据量要求（L228 的 continue）与 candidate_list 的原有顺序，' +
      '所以唯一变化是「带」本身消失，池子大小与排序不动。\n' +
      '! 这不是 rank 33 的那条。rank 33 换成 `prev_close > bbi`，那是「保留一个过滤器、换成文档写的那条规则」；' +
      '本条是「移除过滤器」的 edge test。两者方向相反，不可合并（orchestrator ruling 4）。',
    from: [
      'free code audit: L243 与 L208 / L242 的注释自相矛盾（gatekeeper 已逐行核对源码）',
      'member 7da05cc8 (本族第二本 BBI 书)',
      '族页 §1/§2/§6 描述的是 7a1c225f，对 champion 的机制为空',
    ],
    edgeRef: '中期趋势带 (BBI)',
    edgeProposal: {
      name: '中期趋势带 (BBI)',
      kind: 'anomaly',
      status: 'proposed',
      claim:
        '在 399101 成分中市值最小的 80 只里，前收盘价落在 (0.9xBBI, 1.3xBBI) 区间内的名字优于同一池不加该条件的名字' +
        '——钱在「既不弱也不过热」，而不只在「市值最小」。',
      test:
        '把该带状条件设为无条件通过（保留 >=24 根 bar 的数据量要求与原排序），其余逐字不动；' +
        '若 edge 成立，TRAIN 年化应损失过半。证伪：年化 >= control 的 85% 且 sharpe 相差 <= 1.0。',
      withheldUntil: 'q-e9-champ-bbi-off 返回。证伪即 WITHDRAWN，不写入族页 edge 块。',
    },
    control: CTRL,
    secondaryRead: SECONDARY,
  },
  {
    id: 'q-e9-champ-size',
    kind: 'understand',
    rank: 30,
    status: 'open',
    title: 'edge test 规模：把选股池换成市值升序第 201-400 名（上挪一档）',
    hypothesis:
      '假设：若规模是本书收益主体，上挪一档年化损失过半。预注册三分证伪：' +
      '(a) 年化 >= control 的 75%（>= 207.6%）⇒ 规模 NOT 解释这本书，' +
      '该主张不得被携带到 epoch 9 的这个 candidate 上（本族的 规模 edge 仍对低开支成立，但对 champion 未证）；' +
      '(b) 年化 < 50%（< 138.4%）⇒ 规模 在 champion 上复现，与 q-e6-1 在另一本书、另一个窗口上的结果同向；' +
      '(c) 运行期日志显示任一次 len(fund_df) < 400 ⇒ 池子不够深，本次测量 INVALID，报告为「无法执行」而非「无效应」。',
    why:
      'q-e6-1 测得的「第 1-1000 名 >> 第 1001-2000 名」是本族最强的一条测量，但它测在 7a1c225f 上、测在 2022-23 上，' +
      '而那本书现在只排第 13（1.1627）。champion 的池子完全不同' +
      '（399101 成分 + market_cap.between(10,80) + head(200) + head(80)），所以 规模 对它是未证的。' +
      'edgeRef 是 规模，但判定按 understand：任一方向都是信息。',
    design:
      "SINGLE EDIT — L190 `    initial_list = fund_df['code'].head(200).tolist()` -> " +
      "`    initial_list = fund_df['code'].iloc[200:400].tolist()`。" +
      'fund_df 已按 market_cap 升序（L184 order_by asc），L205 的二段 head(80) 保持不动，' +
      '于是 candidate_list 变成「第 201-400 名中最小的 80 只」——干净的上挪一档。\n' +
      '!! GATEKEEPER CORRECTION：提案要求 builder 在 BUILD TIME 断言 len(fund_df) >= 400。做不到——' +
      'build time 是 JS，没有 JQ 数据，而 399101 成分经 cap 10-80亿 过滤后的深度只有运行时才知道。改为 RUNTIME 守卫：' +
      "紧随该行加一句 `log.error('POOLDEPTH date=%s n=%d' % (str(context.previous_date), len(fund_df)))`，" +
      '并在报告里统计 n < 400 的 rebalance 次数；任一次 n < 400 即落入证伪支 (c)。' +
      '该 log 行属于 helper 而非第二处编辑：undo 断言只还原 L190。',
    from: [
      'q-e6-1 (STALE, epoch 6 — 测在 7a1c225f + 2022-23 上。机制级论证可跨台，但「本书的池子」是不同的事实，故不是重复)',
      'q-e6-17 (STALE — 修正单位后换档只剩 5%，规模 反而更强)',
      'q-e6-6 / q-e6-7 (STALE — 规模阈值往大放的代价远大于往小收)',
      'edge 规模 (measured，但测在低开支上)',
    ],
    edgeRef: '规模',
    control: CTRL,
    secondaryRead: SECONDARY,
  },
  {
    id: 'q-e9-champ-dbl',
    kind: 'understand',
    rank: 31,
    status: 'open',
    title: '消融 MACD 顶背离择时：它是 2.6282 的一部分，还是约 6 个未申报自由度',
    hypothesis:
      '假设：|Δobjective| < 0.3 —— 择时对本族是 off-mechanism，三本动量族的 趋势择时 都已被证伪。预注册三分：' +
      '(a) |Δ| < 0.05 ⇒ 这套机器什么也没做，剥掉它的那本书 EQUAL PERFORMANCE / STRICTLY FEWER DoF，' +
      '按本族唯一一次历史采纳（一次删除）的形状应当采纳为 candidate 形态；' +
      '(b) Δ >= +0.05 ⇒ 它是负贡献，直接采纳剥掉版；' +
      '(c) Δ < -0.30 ⇒ 择时在 2024 上是承重的，与两条独立先验相反，不采纳，' +
      '而是作为一条候选新 edge 记录，并拿去对照三本动量族里已被证伪的 趋势择时 证据读。',
    why:
      'detect_divergence 带约 6 个未申报自由度（MACD 的三参数 + 背离窗口 + 新高判据 + g.dbl[-4:] 的 4 日），' +
      '全部由一位 2026 年作者写在一本 2024 年 TRAIN 的书上。' +
      '它有两条作用路径——L366 的 9:00 清非涨停持仓、L263 的暂停本周调仓——一次消融同时关掉两条。',
    design:
      'MERGED：两个 generator 提了同一个实验（understand 要把 dapan 的 body 改成只 append(False)；' +
      'improve 要在 detect_divergence 顶部插 return False）。' +
      'gatekeeper 已核实 detect_divergence 在全文件只有 L366 一个调用点，g.dbl 只在 L263 被读，' +
      '所以两种改法行为完全等价。取 improve 的那一处，因为它是严格的单行插入而不是多行函数体替换。\n' +
      'SINGLE EDIT — 在 L592 `def detect_divergence(stock, context):` 的 docstring 之后插入首条语句 ' +
      '`    return False  # ablation: 顶背离机器整体停用`。' +
      '于是 dapan 恒走 else 分支（g.dbl.append(False)，L263 的 `True in g.dbl[-4:]` 恒为 False），' +
      '两条路径一起停用，而两段代码仍被求值。\n' +
      '! 报告需给出消融后的调仓次数。若 control 里 L263 从未触发过，则 Δ 只来自 9:00 清仓那一条，' +
      '两条路径的归因必须分开陈述，而不是合并成一个 Δ。',
    from: [
      'q-e6-2 的 implication，仅取其 MECHANISM-CLASS 半边（「择时对本族 off-mechanism」不依赖测的是哪一年）',
      '趋势择时 在 ETF动量 / 五福闹新春 / 七星高照 三族被证伪（MECHANISM 论证）',
      'q-e6-5 (STALE — 退出部件是否属于 edge 的一部分)',
    ],
    edgeRef: '规模',
    edgeRefNote: 'off-mechanism check —— 顶背离不属于本族任一 measured edge；本条测它是否该留在 candidate 里。',
    control: CTRL,
    secondaryRead: SECONDARY,
    consequenceIfAdopted:
      '落在 (a) 或 (b) 时，剥掉顶背离的那本书成为本族 candidate 的形态（更少自由度、同等表现）。' +
      '! 与 rank 26 的下限结论叠加时，两处改动的叠加效果不可由两个 Δ 相加推出' +
      '（q-e6-18 的教训：0.65 与 0.36 叠成 0.16），需要单独一次测量，' +
      '由 recorder 开出新条目而不是在本条里顺带宣布。',
  },
  {
    id: 'q-e9-champ-breadth',
    kind: 'understand',
    rank: 32,
    status: 'open',
    title: 'g.target_stock_count 2 -> 4：作者取的 2 是不是又一个顶在作者值上的驼峰',
    hypothesis:
      '假设（由本族历史先验给出，方向是 2 更好）：本族两个独立旋钮' +
      '（g.choice 的 500/800/1000/1200/1500、低开阈值的 -0.5/-1/-2）都在作者值上尖峰、两侧各掉约一半，' +
      '那是事后调参的指纹。预注册三分：' +
      '(a) objective < 1.6 ⇒ 2.6282 的优势特指「只持 2 只」的集中度，' +
      '而这同时意味着它在 ¥1e7 下限上无处可退——把 rank 26 的结论读成「容量恰好卡在边上」；' +
      '(b) objective 在 2.1-2.68 之间 ⇒ 平台而非尖峰，量级可信，' +
      '且 4 只把可行性下限从 1e7 砍到 5e6（capacity 白赚）；' +
      '(c) objective >= 2.68 ⇒ 作者的 2 是个被 2024 调出来的旋钮，量级本身要打折。',
    why:
      '本条按 understand 判而不是 improve，这是 gatekeeper 的改判。' +
      '两个 generator 分别提了 2->5 与 2->4（同一旋钮、同一方向，已合并）。' +
      'improve 的理由是「4 只把 1e7 下限减半」——但那条理由只在 rank 26 测出下限 BINDING 时才有价值；' +
      '若下限 INERT，2->4 就退化成一年期 TRAIN 上的纯分数旋钮，' +
      '正是本轮明确不收的那一类（退出阈值扫描、低开支排序微调）。' +
      '它仍然值一个槽位，因为它测的是「作者的 2 是不是驼峰顶」' +
      '——那是关于 2.6282 可不可引用的问题，不是关于怎么调高它的问题。' +
      '取 4 不取 5：4 有机制锚点（1,000,000 / 4 / 0.05 = 5e6，恰好是下限减半），5 没有。',
    design:
      'SINGLE EDIT — L111 `    g.target_stock_count = 2` -> `    g.target_stock_count = 4`。' +
      '该变量在 L270 / L276 / L286 / L573 / L727 共 5 处被读，全部随之改变——这是预期行为而不是第二处编辑。\n' +
      '! executor 必须每次 rebalance 记录持仓只数：现金 ETF g.etf 本身占一个仓位' +
      '（L257 的 buy_security(context,[g.etf])），而 buy_security 在 L727 ' +
      '`len(context.portfolio.positions) >= g.target_stock_count` 处 break，' +
      '所以空仓月里 ETF 会吃掉一个名额，2->4 改变的不只是股票只数。报告需讲清这一点，否则 Δ 无法归因。\n' +
      '! 只测 4 这一个点。邻点（3、6）由本条的结果 spawn，不预先入列——' +
      'q-e6-6/7 的教训是形状有用，但一次一个点、由结果驱动，而不是一次排三个点去拟合驼峰。',
    from: [
      'q-e6-6 / q-e6-7 (STALE, epoch 6 — 它们关的是 g.choice 那个旋钮本身。' +
        '本条用的是它们的 LEVEL-INDEPENDENT 论证「本族作者值常是驼峰顶」，不是重开那个旋钮)',
      'imp-1..imp-4 (STALE §2 rejected — 两个独立参数恰好都在最优点是事后调参的指纹)',
      'q-e6-15 (STALE — annual - maxdd 对隐含集中度是开口的；这条算术论证不是 2022 年的事实)',
      'q-e9-liq-5a70adc1 (capacity 是本族的约束性轴)',
    ],
    edgeRef: '规模',
    edgeRefNote:
      'on-mechanism：g.target_list 全程按市值升序，[:2] -> [:4] 就是沿 规模 排名往下走一档，测的是档内的规模梯度。',
    control: CTRL,
    secondaryRead: SECONDARY,
  },
  {
    id: 'imp-e9-bbi-doc',
    kind: 'improve',
    rank: 33,
    status: 'open',
    title: '把 BBI 过滤器改回它自己注释写的那条规则：prev_close > bbi',
    hypothesis:
      '预期增益：若带的上下沿不承重，换成文档规则可以在同等表现下少掉两个被调出来的自由度（0.9 与 1.3）。' +
      '预注册采纳线：objective >= 2.37（control 的 90% 以内）⇒ 采纳更简规则；objective >= 2.68 ⇒ 直接采纳。' +
      '证伪：objective < 2.1 ⇒ 带是承重的，不采纳，' +
      '并把 1.3x 上沿记为一个「拟合在 2024 上的 DATED calibration」，是可引用量级上的一笔 tuned-knob 负债。',
    why:
      '这是本轮唯一一条 improve，形状与本族历史上唯一一次被采纳的 improve 相同：' +
      '一次删除（更少自由度、同等表现），而不是一次调参。依据是 AUTHORSHIP 论证（q-e6-8）：' +
      '本书有五处注释与代码不符——市值注释「5亿-50亿」/ 代码 between(10,80)；注释「前100只」/ 代码 head(200)；' +
      '注释「前50只」/ 代码 head(80)；注释「收益达100%止盈」/ 代码 avg_cost*1.4；' +
      '以及 L242 注释「收盘价在BBI上方」/ 代码的 0.9-1.3 带。' +
      '前四处是注释没跟上代码；第五处不同——它把一个单边不等式变成了一条两边都要调的带，这是调参留下的形状。',
    design:
      "SINGLE EDIT — L243 `        if bbi*0.9 < prev_close < bbi*1.3:` -> `        if prev_close > bbi:`。\n" +
      '! 与 rank 29 是不同的实验，不可合并（orchestrator ruling 4）：rank 29 的 `if True:` 移除过滤器（edge test）；' +
      '本条保留一个过滤器、换成注释写的那条规则（improve by subtraction）。\n' +
      '!! 调度依赖：必须排在 rank 29 之后执行。' +
      '若 rank 29 落在证伪支（年化 >= control 的 85% 且 sharpe 相差 <= 1.0），则 BBI 根本不承重，' +
      '「换一条过滤规则」没有意义，本条由 recorder 直接 WITHDRAW，不花分钟。',
    from: [
      'q-e6-8 (STALE, epoch 6 — 引其 AUTHORSHIP 论证：作者注释与取值不符是调参的指纹。该论证与窗口无关)',
      'q-e6-10 / imp-5 (STALE — 本族 improve 的 subtractive 形状)',
      'imp-6 (STALE §2 rejected — 排序旋钮在可成交口径下关闭；本条不是排序改动)',
      'free code audit: 本书五处注释/代码不符（gatekeeper 已逐处核对）',
    ],
    edgeRef: '中期趋势带 (BBI)  [proposed @ rank 29 — on-mechanism 依赖该提案存活]',
    control: CTRL,
    secondaryRead: SECONDARY,
  },
];

for (const e of add) q.push(e);
fs.writeFileSync(P, JSON.stringify(q, null, 2) + '\n');
console.log('wrote ' + add.length + ' entries; total ' + q.length);
for (const e of add) {
  console.log('  ' + e.rank + '  ' + e.status.padEnd(6) + ' ' + e.kind.padEnd(10) + ' ' + e.id);
}
