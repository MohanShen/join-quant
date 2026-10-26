// Recorder input for q-e9-champ-bbi-off + q-e9-champ-size (小市值, epoch 9), and the WITHDRAWAL
// of the dependent improve idea imp-e9-bbi-doc (rank 33). Run via:
//   node -e "require('./study/小市值/record-q-e9-champ-bbi-size.js')"
//
// CONTROL for both findings = the champion's own epoch-9 ledger row
//   strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py
//   objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00, 365d  — NOT the base 7a1c225f.
// Never re-run (orchestrator ruling 1); its stored curve recomputes to 2.6281.
const rq = require('../../utils/research-queue');

// ── 1. q-e9-champ-bbi-off ───────────────────────────────────────────────────
rq.recordFinding('小市值', {
  qId: 'q-e9-champ-bbi-off',
  type: 'edge-test',
  component_or_param:
    '中期趋势带（BBI）—— study/小市值/build-bbi-0a7de9fa.js → study/小市值/variants/0a7de9fa-bbi-off.py。' +
    'CONTROL = champion [[0a7de9fa_中小盘趋势策略（年化85%）]] 自身的 epoch-9 台账行（中小盘趋势：399101 中小板综指池、' +
    'BBI 带、2 仓、周二 10:45），objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00（365d），' +
    '**不是 base 7a1c225f** —— §2 其余各行的 Δ 都对 base，两者不可并列读。' +
    '唯一改动：L243 `if bbi*0.9 < prev_close < bbi*1.3:` → `if True:`，' +
    '保留 L228 的 `len(stock_data) < 24` 数据量守卫与 candidate_list 的原有顺序（市值升序），' +
    '所以唯一变化是「带」本身消失，池子大小与排序分毫未动；builder 断言撤销该行后与 py2to3(raw) 逐字节相同。',
  metric_delta:
    'objective 2.6282 → **2.5978**（Δ −0.0304）‖ annual = total 276.82 → **279.24**（+2.42pp，**控制组的 100.9%**）' +
    '‖ sharpe 7.07 → **6.91**（−0.16）‖ maxDD 14.00 → **19.46**（**+5.46pp**，即 +39%）。' +
    '曲线自算复现：control 2.6281 / bbi-off 2.5978（两条各 242 天，末值 276.82 / 279.24）。' +
    '非惰性：日收益在 **205/242** 天上不同，累计曲线自 **2024-02-06** 起每一天都不同（217/217 天），' +
    'pearson 0.9746，max|Δcum| 12.89pp。实现波动率 41.0% → 42.3%。' +
    '预注册 Jan–Nov 副读（335 天跨度年化）：control 1.6888 → bbi-off **1.6552**（Δ −0.0336，与全年 −0.0304 同号同量级），' +
    '十二月占全年对数增长 28.1% → 27.9%（两侧 maxDD 均等于各自全年值：14.01 / 19.46）。',
  window: 'train 2024-01-01→2024-12-31 (365d)',
  finding:
    '**预注册证伪项触发，且两项都有很大余量**：判据是「年化 ≥ control 的 85%（≥ 235.3%）且 |Δsharpe| ≤ 1.0」，' +
    '实测年化 **279.24%**（100.9%，比 control 还高）与 |Δsharpe| **0.16**。' +
    '故 PROPOSED 的 edge **中期趋势带（BBI）被 REFUTED**：去掉这条带在收益上一分不损，' +
    '它唯一可测的贡献是回撤（14.00 → 19.46）。' +
    '不是空测——两本书确实分岔（日收益 205/242 天不同，首次分岔 2024-02-06，max|Δcum| 12.89pp）。' +
    '机制：`bbi_pass` 继承市值升序、书再取 `[:2]`，所以这条带真正的作用是**把落在带外的更小的名字跳过**；' +
    '去掉它＝永远买 80 只里绝对最小的 2 只 —— 同样的收益，多 39% 的回撤。' +
    '⚠ **诚实读法**：这条带本来就已经放过 **96.9%** 的候选槽（41 次调用共剔 101/3217；' +
    '其中 **17 个来自 2024-02-06 单日**（当日全剔，正是曲线首次分岔之处），余下 40 次只剔 84/3200 = 2.6%）。' +
    '所以它**按只数计近乎惰性**，小 Δ **不**构成「被剔掉的名字一样好」的证据。' +
    '另：日志 0 行 `数据不足24天`，故保留的 24 根 bar 守卫在 2024 上没有排除任何名字，不是混淆项。',
  confidence: 'high',
  flags:
    '⚠零滑点台 / single-window（epoch-9 TRAIN 只有 2024 一年）/ edge-refuted（预注册证伪项触发）/ ' +
    'near-inert-on-count（带只剔 3.1% 候选槽，其中 17/101 来自单日）—— 故**不可**读成「带外的名字一样好」，' +
    '只能读成「带从未作为选择来源发挥作用，它作用的那 ~3% 是从市值排序的**头部**剔掉的，买到的是回撤压制而不是收益」/ ' +
    'drawdown-component-not-selection-source / ' +
    '⚠ realizability 不自动转移：q-e9-champ-liq 的 R≥2 测在**带开**的书上；带关后永远买绝对最小的 2 只、' +
    '向薄端偏移，那个 R 不自动覆盖它（本变体 objective 下降、不是候选，故非阻塞项；但若将来采纳任何替代规则，' +
    '必须重跑 liq-1 才能引用 R）',
  description:
    '1 次回测（TRAIN 2024，epoch 9，365 天，242 个交易日）。对照未另跑：按 orchestrator ruling 1，' +
    'builder 走归一化器同一条 py2to3 + OVERRIDE 路径，单行变体可直接对台账行 2.6282 读。' +
    '所有数字由记录者对 data/series/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa__train__e9.json 与 ' +
    'data/series/study_小市值_variants_0a7de9fa-bbi-off__train__e9.json 两条存盘曲线独立复核，非取自执行者报告。' +
    '旁证：带剔除后的候选数 3217 − 101 = 3116，与 q-e9-champ-liq 记下的 control `bbi_pass` in=3116 完全一致。',
  implication:
    '**关闭 BBI 这个方向，并且不给本族新增 edge**：带状条件不是选择来源，而是一个回撤部件——' +
    '它只碰到约 3% 的候选槽，碰到的还是市值排序的**头部**，换回来的是 5.46pp 回撤而不是收益。' +
    '因此 (a) 该 edge 提案按其 `withheldUntil` 条款 **WITHDRAWN，不写入族页 edge 块**；' +
    '(b) 依赖它存活的 improve 条目 **imp-e9-bbi-doc（rank 33）本轮直接 WITHDRAW，不花回测分钟**——' +
    '带不承重时「把过滤器换成注释写的 prev_close > bbi」没有可解读的前提；' +
    '(c) champion 的绩效解释必须到**别处**去找（规模见 q-e9-champ-size，剩下的是 rank 31 的 MACD 顶背离择时与 rank 32 的 2 仓集中度），' +
    '不得再把 BBI 带当作这本书为什么赚钱的一部分；' +
    '(d) **带只能作为回撤旋钮重提**，而任何这类替代规则（含 0.9/1.3 两个上下沿的重新取值）在被引用前必须先重跑 ' +
    'liq-1 —— R≥2 是在带开的书上测的，而放松带会把持仓推向更小更薄的名字，容量结论不自动转移。' +
    'Jan–Nov 副读与全年同号同量级（−0.0336 vs −0.0304），所以这条结论不是十二月的产物，无需二次确认。',
  spawned: 'none',
  edgeRef: '中期趋势带 (BBI)（本轮 PROPOSED → REFUTED；按提案自带的 withheldUntil 条款不写入族页 edge 块）',
});

// ── 2. q-e9-champ-size ──────────────────────────────────────────────────────
rq.recordFinding('小市值', {
  qId: 'q-e9-champ-size',
  type: 'edge-test',
  component_or_param:
    '规模（选股池上挪一档）—— study/小市值/build-size-0a7de9fa.js → study/小市值/variants/0a7de9fa-size-up1.py。' +
    'CONTROL = champion [[0a7de9fa_中小盘趋势策略（年化85%）]] 自身的 epoch-9 台账行 2.6282 / sharpe 7.07 / ' +
    'annual 276.82 / maxDD 14.00（365d），**不是 base 7a1c225f**。' +
    '唯一改动：L190 `initial_list = fund_df[\'code\'].head(200).tolist()` → `.iloc[200:400].tolist()`' +
    '（fund_df 已按 market_cap 升序，L205 的二段 head(80) 不动 ⇒ 变成「第 201–400 名中最小的 80 只」，一档干净的上挪）；' +
    '另加一行 runtime 守卫 `log.error(\'POOLDEPTH …\' % len(fund_df))`，属 helper 不属第二处编辑，undo 断言只还原 L190。',
  metric_delta:
    'objective 2.6282 → **0.4984**（Δ **−2.1298**，保留 **19.0%**）‖ annual = total 276.82 → **81.63**（**保留 29.5%**）' +
    '‖ sharpe 7.07 → **2.25**（−4.82）‖ maxDD 14.00 → **31.79**（**+17.79pp，2.27×**）。' +
    '曲线自算复现：control 2.6281 / size-up1 0.4984。日收益相关仅 **0.5880**；' +
    '实现波动率反而**下降** 41.0% → 36.1%（隐含波动 36.3%，一致，非抓取伪影）。' +
    '预注册 Jan–Nov 副读：control 1.6888 → size-up1 **0.4735**，保留 **28.0%**（与全年 29.5% 基本相同）。' +
    '十二月占全年对数增长：control 28.1% → size-up1 **10.3%**。',
  window: 'train 2024-01-01→2024-12-31 (365d)',
  finding:
    '**先过有效性闸门**：41 次 rebalance 全部打出 POOLDEPTH，n 的 min **580** / mean **642.1** / max **705**，' +
    '**0 次 < 400**，且 `市值筛选后数量` 41 次全部正好 = 200 ⇒ `.iloc[200:400]` 每次都返回满 200 个，' +
    '预注册第三支（INVALID「无法执行」）**不触发**。' +
    '结果落在预注册的 **(b)** 支：证伪线是年化 ≥ 207.6%，实测 **81.63%（保留 29.5%）**，' +
    '故 **规模 在 champion 上复现** —— 与 q-e6-1（保留 40%）、q-e6-17（保留 5%）同向，' +
    '但那两次测在**另一本书**（base 7a1c225f 低开剥头皮）、**另一个池**（全 A 升序前 1000）、**另一个台**（epoch 6 / 2022–23）上。' +
    '变体仍过 epoch-9 的 1.0 闸门（sharpe 2.25），却丢掉 81% 的 objective。' +
    '机制上**不是**变薄的故事：上挪后的池子在下游反而**更深**（candidate_list 合计 3250、mean 79.3、min 50；' +
    '`bbi_pass` 3182 对 control 的 3116），买入每次仍是设计中的 1–2 只，' +
    '所以损失来自**选股**而不是机会集枯竭。日收益相关只有 **0.5880** —— 一档之差是另一本书，不是同一本书的缩放。' +
    '风险端：实现波动率**下降**（41.0% → 36.1%）而回撤**翻倍**，故风险上升是路径形态而非波动率。' +
    '无成交病理：0 行 `不可成交`、0 行 `买入失败`；10 行 `下单失败` 是现金耗尽/取整导致的零额委托。',
  confidence: 'high',
  flags:
    '⚠零滑点台 / single-window（epoch-9 TRAIN 只有 2024 一年）/ edge-reproduced-on-new-book（第三次独立确认，首次在 champion 上）/ ' +
    'validity-gate-passed（POOLDEPTH 41/41 ≥ 580，无 (c) 支）/ selection-not-breadth（上挪后下游候选反而更多）/ ' +
    'low-correlation-with-control（0.5880，一档即换书）/ vol-falls-while-drawdown-doubles（风险在路径不在波动率）/ ' +
    'no-scrape-artefact（隐含 36.3% vs 实现 36.1%）/ ' +
    '⚠ 本条只测「规模是否是本书收益主体」，**不**测容量，也不改 q-e9-champ-liq 的 R=2',
  description:
    '1 次回测（TRAIN 2024，epoch 9，365 天，242 个交易日）。对照未另跑（orchestrator ruling 1）。' +
    '日志统计：41 行 POOLDEPTH、41 行 `市值筛选后数量`（全部 = 200）、0 行 `不可成交`、0 行 `买入失败`、10 行 `下单失败`。' +
    '所有绩效数字由记录者对 data/series/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa__train__e9.json 与 ' +
    'data/series/study_小市值_variants_0a7de9fa-size-up1__train__e9.json 两条存盘曲线独立复核，非取自执行者报告。',
  implication:
    '**champion 的 edge 就是 规模**，于是本族**没有第三个机制**：第三支（399101 + BBI 带 + 2 仓）与低开剥头皮支、' +
    '399101 周度轮动支共用同一个已测来源，差别只在实现。两个直接后果：' +
    '(1) **对 integration 而言这一支与本族其余成员冗余** —— 它不给 小盘 这个 type 带来新机制，' +
    '把它当作「新 edge 的来源」去配对是错的；它能贡献的只有同一条 edge 的另一种实现（相关 0.5880 说明实现确实不同），' +
    '要在 type 层主张价值必须走「同一 edge 两种实现的稳健性」这条论证，而不是「两条不同的 edge」。' +
    '(2) 规模 这条 claim 的 `evidence:` 加上本条、`test:` 补记「已在 399101 champion 上于 epoch 9 复核（保留 29.5%）」，' +
    '从此它不再是一条只测在低开支上的主张 —— §4 里「两条已测 edge 都测在低开支上、没有一条说明 champion 为什么赚钱」这一项就 edge 归属而言**已结清**。' +
    '**仍未解释的是量级**：规模 解释了方向，但不解释 champion 为什么以 2.6282 领先同族其他规模书一个量级——' +
    '它的波动率只是中游（41%），所以多出来的分不是单纯加杠杆。下一步**只**在这两个未测部件上找：' +
    'rank 31 **q-e9-champ-dbl**（MACD 顶背离择时：是收益的一部分，还是约 6 个未申报自由度）与 ' +
    'rank 32 **q-e9-champ-breadth**（`g.target_stock_count` 2→4：2 是不是又一个顶在作者值上的驼峰）。' +
    '两者都已在队列、都未跑，且在它们返回前不得把 2.6282 归因于任何已测 edge 之外的东西。' +
    '另记一条副产品：十二月占对数增长从 28.1% 掉到 10.3%，即 **champion 的十二月暴涨本身是最小市值现象、不是全市场现象**——' +
    '这解释了为什么 Jan–Nov 副读（保留 28.0%）与全年（29.5%）几乎相同，本结论不是十二月的产物。',
  spawned: 'none',
  edgeRef: '规模',
});

// ── 3. WITHDRAW imp-e9-bbi-doc (rank 33) ────────────────────────────────────
// Its own entry pre-declared this: "若 rank 29 落在证伪支（年化 >= control 的 85% 且 sharpe 相差 <= 1.0），
// 则 BBI 根本不承重，换一条过滤规则没有意义，本条由 recorder 直接 WITHDRAW，不花分钟。"
// Both halves of that falsifier fired (279.24% = 100.9%, |Δsharpe| 0.16), so it is dropped unrun.
const entries = rq.load('小市值');
const hit = entries.find(e => e.id === 'imp-e9-bbi-doc');
if (!hit) throw new Error('imp-e9-bbi-doc not found in the queue — refusing to write a silent no-op');
if (hit.status !== 'dropped') {
  hit.status = 'dropped';
  hit.result =
    'WITHDRAWN 不跑（本条自己的 design 已预先声明该条款），因为 q-e9-champ-bbi-off 落在证伪支：' +
    '年化 279.24% = control 的 100.9%（判据 ≥ 85%）且 |Δsharpe| = 0.16（判据 ≤ 1.0），两半都以很大余量触发。' +
    'BBI 带被 REFUTED，它不是选择来源而是一个回撤部件（只碰 3.1% 候选槽、且碰的是市值排序头部），' +
    '于是「保留一个过滤器、换成注释写的 prev_close > bbi」失去可解读的前提：' +
    '采纳线（obj ≥ 2.37）与证伪线（obj < 2.1）都只在「带承重」的前提下有意义，' +
    '而无条件通过已经给出 2.5978 —— 任何介于两者之间的规则都只会读出一个无法归因的中间数。' +
    '其 AUTHORSHIP 论证（注释与代码不符是调参指纹，q-e6-8）**未被推翻**，只是不再值一次回测：' +
    '0.9/1.3 两个上下沿现在记作「回撤旋钮上的 DATED calibration」，' +
    '若将来有人要把带当回撤部件重新取值，须连同 liq-1 一起重跑（R≥2 测在带开的书上）。';
  rq.save('小市值', entries);
}

console.log('recorded q-e9-champ-bbi-off + q-e9-champ-size; dropped imp-e9-bbi-doc (rank 33)');
