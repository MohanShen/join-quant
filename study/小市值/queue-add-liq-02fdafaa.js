// Append the EXIT-GATE measurement q-e9-champ-liq-02fdafaa to study/小市值/queue.json as `answered`.
//
// The executor was dispatched directly (the gate's own requirement, not a ranked research idea), so
// no queue entry existed. The orchestrator's instruction: add it as `answered` if the recorder has
// not. Idempotent — refuses if the id is already present.

const fs = require('fs');
const path = require('path');

const FILE = path.join(__dirname, 'queue.json');
const ID = 'q-e9-champ-liq-02fdafaa';

const q = JSON.parse(fs.readFileSync(FILE, 'utf8'));
if (q.some(e => e.id === ID)) {
  console.log(`[queue] ${ID} already present — nothing to do`);
  process.exitCode = 0;
} else {
  q.push({
    id: ID,
    kind: 'understand',
    rank: 1,
    status: 'answered',
    title: '流动性可行性下限 ¥3.33e6/日：NEW champion 02fdafaa 吃得下自己的仓位吗',
    hypothesis: '预注册三分证伪，在看到数字前锁定（与 q-e9-champ-liq 在旧 champion 上用的同一套约定，故两者可比）：'
      + '(a) 剔除 0 个名字且曲线与 control 逐位相同 ⇒ R>=2，容量上限未测；'
      + '(b) 有名字被剔除但 objective 仍 >= 1.0 闸门 ⇒ R=2；'
      + '(c) 有名字被剔除且 sharpe < 1.0 或 objective < 1.5 ⇒ 本书 R=1，champion 不是候选。'
      + ' 先验：本书持 6 个名字（旧 champion 持 2），故下限 ~3 倍更小，预期咬得更少而非更多。',
    why: 'EXIT GATE 自身的要求：integrate-eligible 需要 realizability >= 2，而 UNKNOWN 是 BLOCK。'
      + 'realizability 是「一本书」的属性，家族页上的分数是在别的书上取证的（低开剥头皮支，以及后来的 '
      + '0a7de9fa / 5a70adc1），所以新 champion 的容量未测。容量也是唯一读不出源码的轴：'
      + '大小盘轮动 liq-1 在 31/31 次 rebalance 剔 0 个（曲线逐位相同），而 ETF溢价 的把 sharpe 8.44 打到 1.10。',
    design: '下限推导（全部来自本书自身仓位，非猜测）：SINGLE SLEEVE（源码无 g.portfolio_value_proportion），'
      + 'buy_security L500-521 以 `cash / target_num` 定仓、target_num = g.stock_num = 6 (L50)；'
      + 'adjust_stock_num (L576) 会把它变成动态 3..6，但**从未被调用**（builder 断言）。'
      + 'capital 1,000,000 / 6 = 166,666.67 每仓；epoch 4 钉死 order_volume_ratio=0.05，'
      + '故单根日 bar 填满一仓需该 bar 成交额 >= 166,666.67 / 0.05 = 3,333,333.33 CNY/日。\n'
      + 'SINGLE EDIT — L137 `    return final_list` -> `    return filter_liquidity_floor(context, final_list)`，'
      + 'get_stock_list 的末行。两个调用点（weekly_adjustment L149、check_remain_amount L216）都被这一改动覆盖。\n'
      + 'helper：20 根日 bar 的 median `money`，在 context.previous_date 求值（今天要交易的那根 bar 永不被查询），'
      + '每次调用 log.error 打一行 LIQFLOOR + 累计计数器（日志 tab 每请求只给 100 行，本书很吵，故最后一行必须自足）。\n'
      + '! 只建并只跑 liq-1。FLOORS 表已把 liq-2 (5x=1.67e7) / liq-3 (10x=3.33e7) 写进 builder 以免日后按口味补点。\n'
      + '! final_list 是 12 个候选（g.stock_num*2）而只填 6 个槽，所以剔掉前 6 名里的一个会让第 7 名顶上 —— '
      + '这是「填不满就不要、换下一个」的有纪律版本。slots=min(6,n_out) 每次都打，因为这个顶替会用尽：'
      + 'n_out < 6 时是持仓饿死，Δ 就混进了「名字质量」之外的东西，必须看得见而不是推出来。',
    from: [
      'EXIT GATE (integrate-eligible: realizability >= 2, UNKNOWN BLOCKS)',
      'q-e9-champ-liq (旧 champion 0a7de9fa，¥1e7，剔 61/3116=1.96%，15/41 次，slots=2 全程，Δobjective -0.1823 ⇒ (b) R=2)',
      'study-b3751277-liq-1 (同族另一本：¥4e6 下限 INERT，objective 1.3443 -> 1.3443)',
      '大小盘轮动 liq-1 (31/31 次剔 0 个，曲线逐位相同)',
      'ETF溢价 liq (sharpe 8.44 -> 1.10，反例；小市值 7/8 不可成交)',
    ],
    edgeRef: '规模',
    control: "CONTROL = the NEW champion's own epoch-9 ledger row: "
      + 'strategies/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa.py, '
      + 'objective 3.0172 / sharpe 8.22 / annual 320.35 / maxDD 18.63, 365 days, curve on disk '
      + '(maxDD window 2024-05-07 -> 2024-06-24; 2024-01 return 0.00%). '
      + '⚠ 文件名前缀是 FETCH 日期；本书 POSTED 2025-06-06。',
    secondaryRead: 'FREE，全部来自已存曲线：2024-01 月度收益 + maxDD 窗口。control 的 1 月是 0.00%'
      + '（today_is_between / g.pass_april=True 空仓），maxDD 窗口 2024-05-07 -> 2024-06-24；'
      + '同日的 emptymonth 消融把 1 月打到 -17.76% 并把 maxDD 窗口搬进 1 月。'
      + '所以若下限改变了「持哪些名字」，就看 1 月的平坦与 5-6 月的回撤窗口是否还在 —— '
      + '这两个可观测量告诉你下限有没有悄悄重塑这本书。',
    consequenceIfAdopted: '落在 (b) 时，带下限的那本书——而不是裸 champion——才是本族 candidate；'
      + '落在 (a) 时 champion 原样即是可成交形态。两种情况 realizability 都 >= 2，退出闸门解锁。'
      + '落在 (c) 时 champion 不是候选。',
    result: '落在预注册的 (b) 支：名字**确实被剔除**，但代价为零甚至微正 —— 不是 (a) INERT（曲线不是逐位相同）。'
      + 'objective 3.0172 -> **3.0192**（Δ **+0.0020**），sharpe 8.22 -> 8.20，maxDD **18.63 -> 18.63 不变**，'
      + 'annual 320.35 -> 320.55。LIQFLOOR 共 **91 行 / 0 ERROR 行**，其中 in > out 共 **3 次**'
      + '（2024-09-18 / 09-19 / 09-23 的 previous_date，每次 in=10 out=9，removedFrac=0.1000），'
      + '累计 in=910 / out=907 = 剔掉 **3 个名字 = 候选的 0.33%**。'
      + '**91/91 次全部 slots=6，minSlots=6、cumShort=0** —— 一次都没有饿死，第 7 名顶替全部成功，'
      + '所以 Δ 纯粹是「名字质量」，不混持仓稀释。'
      + '曲线：首个相异日 **2024-09-19**（正是第一次剔除的次日），max|Δcum| 4.17pp，日收益相关 0.9986；'
      + '月度表里只有 9 月 -0.2300pp / 10 月 +0.2747pp 是真分歧，11 月 +0.0036 / 12 月 -0.0042 是 board-lot 舍入残差'
      + '（11-12 月 max|Δdaily| 0.0056pp）。**1 月 0.00% 与 maxDD 窗口 2024-05-07 -> 2024-06-24 两者都逐位保留**，'
      + '所以下限没有重塑这本书，只在 9 月换掉了一个名字。'
      + ' ⇒ **realizability >= 2** 在 ¥3.33e6/日 可行性下限处成立；容量上限（liq-2 1.67e7 / liq-3 3.33e7）已构建未跑。',
    artifacts: [
      'study/小市值/build-liq-02fdafaa.js',
      'study/小市值/variants/02fdafaa-liq-1.py',
      'data/series/study_小市值_variants_02fdafaa-liq-1__train__e9.json',
    ],
  });
  fs.writeFileSync(FILE, JSON.stringify(q, null, 2) + '\n');
  console.log(`[queue] appended ${ID} as answered (${q.length} entries)`);
}
