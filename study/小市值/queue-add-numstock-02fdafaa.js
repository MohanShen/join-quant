// Gatekeeper 2026-11-04: append q-e9-champ-numstock to study/小市值/queue.json.
// Idempotent — refuses if the id is already present. Ranked 26.3, status active (named for dispatch;
// the orchestrator spawns the executor).
const fs = require('fs');
const path = require('path');
const FILE = path.join(__dirname, 'queue.json');
const ID = 'q-e9-champ-numstock';
const q = JSON.parse(fs.readFileSync(FILE, 'utf8'));
if (q.some(e => e.id === ID)) { console.log(`[queue] ${ID} already present — nothing to do`); process.exit(0); }
q.push({
  id: ID,
  kind: 'understand',
  rank: 26.3,
  status: 'active',
  title: '消融（反向）：把 champion 02fdafaa 自带却从未调用的 adjust_stock_num（399101 close−MA10 点差 ⇒ 持仓数 3..6）打开',
  hypothesis:
    'champion 02fdafaa 定义了 adjust_stock_num (L576–590) 但全文只出现 1 次（定义本身，0 处调用），始终以 g.stock_num = 6 (L50) 运行。' +
    '同一函数（阈值 ≥200→3、[−200,200)→4、[−500,−200)→5、其余→6，逐行相同）在本族 **4 本已测成员**里是打开的：aaba7575 (obj 1.1403)、17c95d16 (1.3571)、76593fb6 (0.6923)、7e59016c (0.7751)；语料另有 55458717（无页、无台账行）。' +
    '**4 本里没有一本被测过 规则开/关 的对照**，所以「这条规则对一本 399101 周度小市值书是什么部件」在本族是未测的。待答：在同一本书、同一 TRAIN 2024 上只把它打开，Δ 是负、近零还是正。' +
    '**判定（预注册，区间无缝）**：令 Δ = objective(variant) − 3.0172。' +
    '(a) Δ ≤ −0.30 ⇒ 趋势条件集中度在本书上有害，作者留成死代码的这本是更好的书；' +
    '(b) −0.30 < Δ < +0.30 ⇒ 在 objective 分辨率上惰性，规则不是这条谱系的承重部件（兄弟书的水平不能归功于它）；' +
    '(c) Δ ≥ +0.30 ⇒ 有益——**只是一条理解，不是采纳**（TRAIN-only；VAL 已用且失败，owner: human；要采纳须另开 improve 条目）。' +
    '无论落哪支，结论都限定为「在 2024 年的 399101 点位上」（阈值是绝对点数，见 why 的 caveat）。',
  why:
    '**值不值 ~3 分钟**：值，但理由不是 exit gate——本族 VAL 已用且失败，任何结果都不能让它过闸，报告里要明说。理由是：' +
    '(1) 它把一个**语料里已被 4 本已测成员运行**的部件变成一次干净的单书归因；目前只能跨书比较，而跨书比较混着池子/排序/空仓月/持仓基数的差别，无法归因。' +
    '(2) 方向事前不明：指数在 MA10 之上时集中（追强）可能放大 2024-09 末的反弹，也可能在 2024-02 前后的踩踏里放大损失——两个方向都可信，正是 understand 该花钱的地方。' +
    '(3) 结果直接决定该部件在 components 层是「可收割」「惰性」还是「警告」。成本低：单书 TRAIN 一次，同书 liq-1 已顺利跑完、无 cap/phantom。' +
    '**edgeRef = null，判为 regime-timing overlay，不是 on-mechanism**：输入是 399101 的趋势状态（close−MA10），输出是持仓数；排序、池子、规模档逐字不动，它只改「按市场状态把多少权益压在排序头部几只上」。' +
    '它与 规模 edge 的唯一接触是头部集中度，而集中度本身已由 q-e9-champ-breadth（另一本书 0a7de9fa、静态 2→4）测为「有影响但非解释性」——本条测的是**状态条件化**的集中度，不是那条的重复。本族无 趋势择时 edge 条目可挂，不为此新建 edge。' +
    '⚠ **不是重复**：findings.tsv / queue.json / 家族页 §2/§4 中关于本规则的唯一记录是 q-e9-champ-liq-02fdafaa 的 caveat（「从未被调用；若调用则除数变动态 3..6，下限须重推」）。stale closures 中无持仓数相关项。' +
    '⚠ **点数 vs 水平（caveat，必须写进结果）**：阈值是 399101 的**绝对点数**。该指数 2024 年大致在 7000–11000（gatekeeper **未能在本地核实**——所以 variant 必须把 close 与 ma 原值打进日志，百分比带宽由运行本身给出）。按此估计 ±200 点 ≈ ±2.9%（7000）到 ±1.8%（11000），带宽随水平漂移约 1.6×。' +
    '判断：**尺度依赖，不是病态**——diff 的符号与排序在一年内单调，规则在 2024 内良定义，只是有效灵敏度随点位漂移（低位更难触发两端）。它在**跨窗口**时才病态：在别的点位上它是另一条百分比规则，所以本结果不对任何别的窗口作陈述。',
  design:
    '**基座**：strategies/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa.py 原文 + 现行 OVERRIDE，构建路径照抄 study/小市值/build-liq-02fdafaa.js；builder study/小市值/build-numstock-02fdafaa.js，产物 study/小市值/variants/02fdafaa-numstock.py，--window train。' +
    '**唯一行为改动（EDIT 1）**：weekly_adjustment 的 `if g.no_trading_today_signal == False:`（L145）分支内**第一行**、`close_no_trading_hold(context)` 之前插入 `g.stock_num = adjust_stock_num(context)`。放在分支**内**是刻意的：与 7e59016c 的用法一致（它也在交易信号闸门内调用），空仓月不重算。' +
    '⚠ 由此带来**三个传导通道**，报告必须分别列出，不得合成一个「集中度效应」：' +
    '【T1 选股切片】get_stock_list L117 `stock_list[:g.stock_num*2]` 与 weekly_adjustment L160 的 target 切片都随 n 变为 2n。' +
    '【T2 卖出滞后】本书只卖**不在 top-2n 里**的持仓，buy_security 只在 target_num > 持仓数时才买（L506）。所以 n 由 6 降到 3 **不会强制卖到 3 只**：若现有 6 只都还在 top-6 里，就继续持 6 只且不加仓。**名义 n ≠ 实际持仓数**——这与 7e59016c 不同（它切 [:stock_num] 并卖掉其余）。' +
    '【T3 四月防御篮】close_account (L552) 在空仓月买 g.no_trading_buy 的 3 个名字，每只按 total_value / g.stock_num，投资比例 = 3/n：基线 n=6 ⇒ 50%；变体用**最后一次三月调仓**冻结下来的 n（n=3 ⇒ 100%，n=4 ⇒ 75%）。这是与集中度无关的现金比例通道。' +
    '**INSTRUMENTATION（非行为）**：' +
    '(I-1) 新增辅助函数 `_numstock_probe(context)`，逐字复制 adjust_stock_num 的取数（399101、MA10、start = previous_date − 20 天、end = previous_date），返回 (close, ma, diff, n_probe)；**不修改 adjust_stock_num 本身**。在 EDIT 1 之后紧接一行打印 `NUMSTOCK date=<previous_date> close=<close> ma=<ma> diff=<diff> pct=<diff/ma> n=<g.stock_num> probe=<n_probe> held_before=<len(context.portfolio.positions)>`，每次调仓恰一行；n != probe 时同行加 `MISMATCH=1`。' +
    '(I-2) weekly_adjustment 分支末尾打印 `NUMHELD date=<current_dt.date> n=<g.stock_num> held_after=<len(context.portfolio.positions)>`。' +
    '(I-3) close_account 买入防御篮之后打印 `NUMDEF date=<d> n=<g.stock_num> invested_frac=<3/n>`。' +
    '⚠ 可被日志直接核对的预测：2024-02-20 那次调仓 previous_date = 02-19、start = 01-30；若春节休市为 02-09..02-17，其间只有 **9** 个交易日，rolling(10) 末行 ma = NaN ⇒ diff = NaN ⇒ 全部比较为假 ⇒ 落到 else 返回 **6**。日志必须如实打出 diff=nan；这是作者规则的真实行为，**不得修补**，但报告要说明那次 n=6 来自 NaN 落空而非市场状态。' +
    '**BUILDER 规则**：' +
    '(B-1) 断言只测**代码侧**：每行先剥掉 `#` 之后的部分再匹配——本目录已有三个 builder 因匹配到自己的解释性注释而拒绝了正确构建。断言：EDIT 1 那行（去注释后）恰为 `g.stock_num = adjust_stock_num(context)`，位于 L145 分支内、早于 close_no_trading_hold；去注释后 `adjust_stock_num(` 的**调用**次数 0 → 1（def 行不计）；adjust_stock_num 函数体逐行未变；除 EDIT 1 与 I-1..I-3 外**没有任何**代码行变化。' +
    '(B-2) 撤销/重放簿记按**位置**而非字符串：所有插入点先在**原始**行号上算好，按行号**降序**插入（前一处插入不移动后一处锚点），记录 (原行号, 插入行数) 表，验证时用它把变体映射回原文逐行比对。不要用字符串 replace 定位：`if g.no_trading_today_signal == False:` 在原文出现两次（L145、L233），替换会打错地方。' +
    '(B-3) 不加流动性地板、不改 OVERRIDE、不改 g.pass_april。' +
    '**预注册读法（数字出来之前）**：' +
    '【R0 有效性闸门，先读】NUMSTOCK 行数 = 实际执行的周度调仓次数（预计约 40：全年减去 1 月与 4 月的周）；0 个 MISMATCH；0 个 ERROR。若 NUMSTOCK 行缺失 ⇒ 插桩失败、结果作废，不得读成「n 恒为 6」。若 n=6 **全程**（含 NaN 落空）⇒ 判为「规则在 2024 未触发」，这本身是答案，此时 |Δobjective| 必须 ≤ 0.02（重跑漂移量级），否则是构建故障，不得读成「规则无作用」。' +
    '【R1 持仓数分布】报告 n ∈ {3,4,5,6} 各几次、对应 pct 带宽（diff/ma），以及 held_after 的分布——区分名义 n 与实际持仓数（T2）。若「n 下降而 held_after 未降」的调仓占多数 ⇒ 结论写成「本书的卖出规则吸收了这个旋钮」，不写成「集中度无效」。' +
    '【R2 主读数】Δobjective / Δsharpe / ΔmaxDD / Δannual 对照 **02fdafaa 自身 epoch-9 台账行** 3.0172 / 8.22 / 18.63 / 320.35——不是 0a7de9fa、不是 base 7a1c225f、也不是 7e59016c 或任何兄弟书。按 (a)/(b)/(c) 判定，边界值 ≤ −0.30 归 (a)、≥ +0.30 归 (c)，区间无缝。另报 maxDD 窗口是否仍为 2024-05-07 → 2024-06-24。' +
    '【R3 一月/二月形状】一月 r_jan 必须**恰为 0.00%**（一月调仓被闸门挡住、开局空仓、close_account 无可卖 ⇒ 构造上不受本改动影响）；r_jan ≠ 0 ⇒ 构建错误，结果作废。二月三段无缝：r_feb < +30.34% ⇒ 「空仓后底部入场」形状被削弱；+30.34% ≤ r_feb ≤ +40.34% ⇒ 存活（±5pp）；r_feb > +40.34% ⇒ 被放大。并列出二月两次调仓的 n（预测 02-06 由市场状态决定、02-20 为 NaN 落空的 6）。' +
    '【R4 通道归因】用曲线按月拆 Δ（对数增长），单列四月（T3）与 2024-09-24 之后（指数急涨，预计 n=3）。四月一段贡献 > 50% 的总 |Δ对数增长| ⇒ 结论写成「效应主要来自四月防御篮的投资比例 3/n」，**不得**归给集中度；≤ 50% ⇒ 可说集中度通道主导，但仍报出四月份额。' +
    '【R5 明确的不陈述】n=3 时单只仓位翻倍，q-e9-champ-liq-02fdafaa 的 ¥3.33e6/日 下限对本变体**不成立**（起始资本下应为 ¥6.67e6/日，且随权益复利）。**本结果不是 realizability 陈述**；不得修改家族页 `realizability:` / `realizabilityScope:`，不得据此动 R=2；若 (c) 成立，任何后续 improve 条目须先在 n=3 仓位上重推并实测地板。',
  from: [
    'strategies/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa.py（L50 g.stock_num=6；L576–590 adjust_stock_num 定义；全文 1 次出现 = 0 次调用；gatekeeper 2026-11-04 复核）',
    'strategies/2026-11-03_模拟没有下单是为什么啊-7e59016c.py（L67 g.adjust_num=True；L165–175 调用并赋值；L282–296 与 champion 逐行一致）',
    'ledger epoch 9：aaba7575 1.1403 / 17c95d16 1.3571 / 76593fb6 0.6923 / 7e59016c 0.7751 —— 4 本已测 小市值 成员都打开此规则，0 本有开/关对照',
    'q-e9-champ-liq-02fdafaa（realizabilityScope caveat：若调用则除数变动态 3..6，下限须重推）',
    'q-e9-champ-breadth（0a7de9fa 静态 2→4：objective −28.2%、年化保留 76.8%——另一本书、非状态条件化，故非重复）',
    'q-e9-champ-emptymonth（一月 0.00% / 二月 +35.34% 的形状及其「空仓后底部入场」解释）'
  ],
  edgeRef: null,
  control: '02fdafaa 自身的 epoch-9 台账行：objective 3.0172 / sharpe 8.22 / annual 320.35 / maxDD 18.63（365d，曲线在盘；maxDD 窗口 2024-05-07 → 2024-06-24）。唯一合法对照。',
  secondaryRead: 'R1 名义 n vs held_after；R3 一月必须 0.00% + 二月三段；R4 四月份额 >/≤ 50%；R5 不作 realizability 陈述。',
  consequenceIfAdopted: '不适用——understand 条目，不采纳。(c) 只授权另开 improve 条目，且那条须先在 n=3 仓位上重推并实测流动性地板，并承认 VAL 已用（owner: human）。',
  note: 'gatekeeper 2026-11-04：排 26.3，先于 q-e9-champ-liq-2（26.5，目标已过期、需重建，不能按原文派发）与 q-e9-bench-dayopen-prepos（28，零回测成本，可随时做）。预计 ~3 回测分钟。edgeRef null：regime-timing overlay，不是 规模 机制上的测试。',
  result: null,
  artifacts: []
});
fs.writeFileSync(FILE, JSON.stringify(q, null, 2) + '\n');
console.log(`[queue] ${ID} appended; entries = ${q.length}`);
