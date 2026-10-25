// q-e9-leg: leg decomposition of the champion bf30eb36 (三马105-五福35).
//
// One line (L118): g.portfolio_value_proportion [0.5,0,0.5,0] -> [0,0,0.5,0] — the 小市值 sleeve's
// weight zeroed while the 五福 slot KEEPS its 0.5 capital, so the ETF sleeve's position size,
// order_volume_ratio bite and min_money are identical to the champion's.
//
// Parent = study/五福闹新春/q-e9-pit_bf30eb36.py (the POINT-IN-TIME build, objective 1.9658 /
// sharpe 7.51), not the raw book: all 17 post-window pool names are ETF-pool names, so
// decomposing the raw book would have measured an ETF leg inflated by post-window selection —
// biased toward exactly the side this test examines.
const rq = require('../../utils/research-queue');
const h = require('../../utils/harness-config');

const w = h.window('train');
const PARENT = h.objective(209.36, 12.78, 7.51);   // 1.9658, verified against the stored curve
const LEG = h.objective(65.93, 10.04, 3.45);       // 0.5589, (65.93-10.04)/100 reconciles
const RAW = 1.9437;                                // bf30eb36's epoch-9 ledger row, side by side
const dObj = LEG - PARENT;
const shareObj = (LEG / PARENT * 100).toFixed(1);
const shareAnn = (65.93 / 209.36 * 100).toFixed(1);

// Dilution envelope: if the ETF sleeve had carried 73b13d92's own relative pool bonus
// (objective -33%, total 164.24 -> 115.74 i.e. -29.5% of return), the champion's TOTAL would have
// moved by only the sleeve's share of it.
const sleeveHit = 65.93 * 0.295;                            // 19.45pp of total annual
const projected = h.objective(209.36 - sleeveHit, 12.78, 7.0); // ~1.7713
const envelope = (projected - PARENT);                       // ~-0.1945, -9.9%

rq.recordFinding('五福闹新春', {
  qId: 'q-e9-leg',
  type: 'isolate',
  component_or_param:
    '冠军 bf30eb36 的资本权重向量，单行：**L118** `g.portfolio_value_proportion` ' +
    '[0.5, 0, 0.5, 0] → [0, 0, 0.5, 0]（小市值腿权重归零，五福腿保留其 0.5 资本，' +
    '小市值那一半躺成现金）。父本 = **study/五福闹新春/q-e9-pit_bf30eb36.py**（点时池构建，' +
    'objective 1.9658 / sharpe 7.51），**不是** strategies 里的生书 —— 生书 17 只窗后上市名字' +
    '全在 ETF 袖子里，用生书做腿分解会系统性高报 ETF 腿，正好偏向本测要检验的那一侧。' +
    '刻意**不用** [0,0,1,0]：该字面量是作者支持的 pure_wufu_mode 特例，在 **7** 处被精确比较' +
    '（L103-104/665/1629/1657/1734/1774/2005），父本与 [0,0,0.5,0] 下 7 处全为 False，' +
    '[0,0,1,0] 下 7 处全部翻转、会改掉 ETF 袖子自身的逻辑（executor 读文件数得 7，' +
    'gatekeeper 的「≥8」以 7 为准）。L3586 的重复赋值经审计**不可达**（在 `if not pv_ok:` 之下，' +
    '4 元素列表令 pv_ok 恒 True），构建期仍打印两处生效值确认。diff 实为一行，' +
    'builder = study/五福闹新春/build-e9-leg.js。',
  metric_delta:
    `ETF-腿-only ${LEG.toFixed(4)} / annual 65.93% / sharpe 3.45 / maxDD 10.04 ` +
    `‖ 父本 q-e9-pit_bf30eb36 ${PARENT.toFixed(4)} / 209.36% / 7.51 / 12.78 ` +
    `⇒ **Δobj ${dObj.toFixed(4)}**（−143.43pp annual、−4.06 sharpe、−2.74 maxDD）。` +
    `腿保留父本 objective 的 **${shareObj}%**、annual 的 **${shareAnn}%**。` +
    `并列参照（非判据）：生书 bf30eb36 账本行 ${RAW}（207.63% / 7.44 / 13.26）。` +
    '曲线核对：242 点 2024-01-02..2024-12-31，末值 cum 65.93，(65.93−10.04)/100 = 0.5589 自洽；' +
    '父↔腿日收益相关 **0.721**（242 日，recorder 独立复算）。137s / 2 JQ min。',
  window: `train ${w.start}→${w.end}, 1 run, 2 JQ min`,
  finding:
    '把冠军的小市值腿权重归零、ETF 腿资本与持仓规模逐字不动，objective 从 1.9658 掉到 **0.5589**' +
    `（annual 209.36% → **65.93%**）—— 本族自己的 ETF 机制只占冠军 objective 的 ${shareObj}%、` +
    `annual 的 ${shareAnn}%。预注册的下侧两个门槛（annual ≤100% / obj ≤0.90）**同时触发**，` +
    '且未落在 100–150% 的 partial 带里。它还**低于预注册的先验**：v5.2 单独 annual 187.39% ⇒ ' +
    '半仓 + 另一半闲置约 93.7%，实测 65.93% —— 冠军的五福袖子比家族 base 在同等权重下更弱。' +
    '构建正确性由日志三重确认：**strategy-1 成交笔数 = 0**（无 `策略1|小市值` 日志行；' +
    '`prepare_small_cap` 从未运行，L4422 的 `pvp[0] > 0` 排程块从未触发；' +
    '67 只成交标的的代码前缀直方图 {15:17, 16:1, 51:40, 52:1, 56:5, 58:3} —— ' +
    '**零只股票形态代码**（00/30/60/68））。ETF 腿 242 日里持仓 **241** 日（唯一空仓日 2024-01-02 ' +
    '首次 13:10 买入之前），26 日落到货币 ETF 511880 的防御模式（集中在 2024-08-02→09-19），' +
    '120 买 / 120 卖，`震荡期` 状态 **0** 日。',
  confidence: 'high',
  flags:
    '⚠零滑点高估 / single-window（2024 单年，epoch 9） / ' +
    '⚠⚠ **leg-coupling —— 本条最重要的边界，不可省略**：ETF 袖子的下单规模取 ' +
    '**L1679 `context.portfolio.total_value * pvp[2]`**，即**全组合**总资产的一半，而不是它自己' +
    '子账户的资产。所以 (i) 在**父本**里这条袖子被小市值腿的盈利一起放大（作者自己在 ' +
    '`make_record` 的注释里点名这件事：「避免在 [0.5,0,0.5,0] 下被组合总资产再平衡放大而出现误读」）' +
    '⇒ 65.93pp 是该袖子在父本内贡献的 pp 的**下界**，31.5% 是其份额的**下界**而非点估计；' +
    '(ii) 在**变体**里另一半是死现金，袖子被连续再平衡到总资产的 50% ⇒ 65.93 **不等于** ' +
    '0.5 × 单独水平，**任何「袖子单独跑多少」的数字都不得从本测推导**（我没有写 ' +
    '0.5*r1/0.5*r2 的分解，正是因为它在这本书里不成立）。可主张的是「给定它自己的资本，' +
    '本族机制产不出冠军的水平」与「小市值腿是冠军水平的必要条件（去掉值 −143pp）」，' +
    '**不可**主张「冠军 = 68.5% 股票腿 + 31.5% ETF 腿」这样一个加法分解 / ' +
    'redundancy-across-families: 冠军的多数收益来自 **规模**，那是 小市值 的 edge 而不是本族的；' +
    '而 小市值 自己的冠军 bba95a11 又是一张 小市值×五福 杂交书 —— 两族在互相把对方的腿记成自己的产品 / ' +
    '⚠ 效应量 −1.4069 是本族实测噪声地板 ≈0.031（q-e8-2，测于 epoch 6）的 **45×**，' +
    '按 epoch-9 水平（4.6×）缩放后仍是 ~10×，故读数不依赖尚未重测的 q-e9-floor',
  description:
    'epoch 9 把 TRAIN 换到 2024，本族 §3 头名成了 bf30eb36（三马105-五福35，objective 1.9437），' +
    '而它是一张**跨族组合书**：资本隔离的 4 个子账户里，50% 给 小市值 选股腿、50% 给 五福 ETF 轮动腿。' +
    '四件事同时压在这一个读数上：(a) 本族 `bestVariant` 指向它，而 小市值 自己的冠军 bba95a11 ' +
    '也是 小市值×五福 杂交 —— 谁的产品归谁，从未测过；(b) 它能把一条**已记录的** epoch-9 结论' +
    '（q-e9-pit-r2「有股票腿 ⇒ 池不敏感 3/3」）从结构性降级为算术性，而 CLAUDE.md 已经在用那张' +
    '4 本书的表决定哪些书 pool-clean 可推进；(c) integrate guard 的 rule-2 腿归因；' +
    '(d) 我们正要给这本书打 realizability 分。一条被引用的错结论比一条缺失的结论贵。',
  implication:
    '**关闭一条**：「冠军 bf30eb36 可以当作本族的产品来推进」不再成立 —— 给定它自己的资本，' +
    `本族机制只产出 ${LEG.toFixed(4)}（annual 65.93%），不但远低于冠军，还**低于家族 base v5.2 ` +
    '在同等权重下的先验 93.7% 与其自身的 1.7479**。所以 (i) 本族在本台上能诚实主张的最好的' +
    '**ETF 机制**书仍是 base 17b3b439（1.7479 / sharpe 5.97），不是 §3 的头名；' +
    '(ii) bf30eb36 属于 **小市值×五福 冗余**那场讨论（与 bba95a11 并列），' +
    '若日后把它作为本族候选送 integrate，rule-2 的腿归因必须按跨族处理、' +
    '且「本族贡献」一栏只能写它的 ETF 袖子。' +
    '**收窄一条已记录的结论（不改旧行，收窄写在这里与 §4）**：q-e9-pit-r2 的「有股票腿 ⇒ 池不敏感」' +
    `不可再当作**机制**结论（「股票腿的边没有池可选」）—— 在一张 ETF 袖子只占 objective ${shareObj}% ` +
    `的书上，池检验的**杠杆本身小 ~3.5×**，所以 +1.1% 与纯 ETF 书的 +1.1% 不可比。` +
    `但也**不得**把它读成纯稀释：若该袖子带着 73b13d92 的同等相对池加成（−29.5% 的收益），` +
    `冠军总额会掉到 objective ≈${projected.toFixed(4)}（${envelope.toFixed(4)}，−9.9%，` +
    '是噪声地板的 ~6×），而实测是 +0.0221 —— 本测对 bf30eb36 仍有检出力，' +
    `所以它的 ETF 袖子**自身**也近乎 pool-clean。可操作的修正是：**池 Δ 今后按袖子报，不按书报**` +
    '（除以该袖子的份额），否则那张 4 本书的表是在比较灵敏度不同的四次测试。' +
    '**开出三条**：(1) **bba95a11 与 b50e4387 的袖子权重完全未测**，它们的 +0.1% / +1.1% ' +
    '杠杆未知 ⇒ 在做同一个腿分解之前，这两本不得被引用为「股票腿 ⇒ 池不敏感」的机制证据，' +
    'q-e9-pit-r2 的 3/3 只剩 1/3 是带杠杆核算的；' +
    '(2) **q-e9-liq 必须按腿 scope**：多数收益坐在股票腿上，而 小市值 的 realizability 是实测 **R=1**，' +
    '所以 realizability 不能由 ETF 袖子的地板读数代表，`realizabilityScope:` 必须点名所描述的那本书 —— ' +
    '这是**阻断性**考虑而非注脚，七星高照 已经因为完全相同的形状被 blocked' +
    '（把一条 R=1 的微盘腿经由冠军路由进 ETF 宇宙）；' +
    '(3) **imp-e9-1 的朴素 +0.17 失去基础**：它把走弱期切池移植进一条自身水平已低于家族 base ' +
    '的少数袖子，而 +0.17 的估算取自两本 100% 暴露的整书之差 ⇒ 须按袖子重估，' +
    '并且它预注册的 census 定案条款（走弱日数 × 两分支归属）现在是它唯一可用的定案路径。' +
    '**另开两条便宜的收尾测项**（同一编辑点、各 1 跑）：`q-e9-leg2`（L118 → [0.5,0,0,0]，' +
    '镜像腿）—— 两条腿之和与父本 209.36 的差直接量出上面那条 leg-coupling 有多大；' +
    '`q-e9-leg-pure`（L118 → [0,0,1,0]，作者自己支持的 pure_wufu_mode，100% 暴露、' +
    '走 `available_cash` 路径）—— 这是唯一能与 base 的 1.7479 直接并读的「袖子单独水平」，' +
    '本测因要保住与冠军逐字相同的持仓规模而刻意放弃了它。',
  spawned: 'q-e9-leg2, q-e9-leg-pure',
  edgeRef: '动量',
});

console.log('[record] q-e9-leg written to study/五福闹新春/findings.tsv');
console.log(`[check] projected-if-sleeve-carried-full-pool-bonus = ${projected.toFixed(4)} (${envelope.toFixed(4)})`);
