// Recorder input for q-e9-champ-liq (小市值, epoch 9). Run via:
//   node -e "require('./study/小市值/record-q-e9-champ-liq.js')"
const rq = require('../../utils/research-queue');

rq.recordFinding('小市值', {
  qId: 'q-e9-champ-liq',
  type: 'isolate',
  component_or_param:
    '流动性可行性地板（study/小市值/build-liq-0a7de9fa.js → study/小市值/variants/0a7de9fa-liq-1.py）。' +
    'CONTROL = champion 自身的 epoch-9 台账行 strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py' +
    '（中小盘趋势：399101 中小板综指池、BBI 带、2 仓、周二 10:45），**不是 base 7a1c225f**。' +
    '唯一改动：L248 `return bbi_pass` → `return filter_liquidity_floor(context, bbi_pass)`，保留' +
    '「近 20 根日线 money 中位数 ≥ 1e7 CNY/日」的名字，在 context.previous_date 上求值（当日要交易的那根 bar 永不被查询）。' +
    '地板由本书自身仓位推出、非选定：capital 1,000,000 / g.target_stock_count 2 = 500,000 每仓，' +
    '再除 epoch-4 钉死的 order_volume_ratio 0.05 = 1e7/日，是 FILL-FEASIBILITY MINIMUM 而非舒适水平。' +
    'builder 断言「撤销唯一那行改动后与 py2to3(raw) 逐字节相同」；排名/BBI 带/择时/阈值/成本块分毫未动。',
  metric_delta:
    'objective 2.6282 → 2.4459（Δ −0.1823）‖ sharpe 7.07 → 6.59（−0.48）‖ annual = total 276.82 → 258.59（−18.23pp）' +
    '‖ maxDD 14.00 → 14.00（Δ 0.00；两侧曲线自算均 14.01）。曲线自算复现台账：control 2.6281 / liq-1 2.4458。' +
    'max|Δcum| = 18.23pp，首次分岔 2024-09-19。预注册 Jan–Nov 副读：control objective 1.6888（total 159.71 / annual 182.88 / 335d）' +
    '→ liq-1 1.5329（total 146.55 / annual 167.30），Δ −0.1558，仍过 1.5；两侧 maxDD 均 14.01，故该副读只动收益不动风险。',
  window: 'train 2024-01-01→2024-12-31 (365d)',
  finding:
    '落在预注册的 (b) 支：名字**确实被剔除**，而结果仍以很大余量过 1.0 闸门 —— 不是 (a) INERT，曲线并非逐位相同。' +
    'LIQFLOOR 41 行、0 ERROR 行，其中 in > out 共 **15/41** 次，全部连续落在 2024-07-09…2024-10-15；' +
    '累计 in=3116 / out=3055，即剔掉 **61 个名字 = 候选的 1.96%**，单次峰值 2024-09-19 的 80→72（10.0%）。' +
    '40 次非空调用**全部 slots=2**，所以这不是持仓饿死（另有 1 次 in=0 的退化调用 2024-02-06，当日 BBI 无候选）。' +
    '诚实标签是「剔了但几乎无关痛痒」，不是「惰性」。机制上全部损失从 **2024-09-19 一天**进来：' +
    '7-09…9-10 那十次剔的都是排名在前 2 之外的名字，持仓没变；9-19 剔掉 8 个后持仓对变成 002211/002633，两条路径此后再未收敛。',
  confidence: 'high',
  flags:
    '⚠零滑点台 / single-window（epoch-9 TRAIN 只有 2024 一年） / floor-removed-but-immaterial（非 INERT，15/41 次有剔除） / ' +
    '⚠⚠ floor-under-constrains-back-half：1e7 是**年初**可行性下限，而 buy_security() 把当前现金摊给需要的名字、仓位随权益复利——' +
    '2024-09-19 已 619,430/仓，2024-12-05 单笔峰值 1,939,339 ⇒ 当时实际需要 3.88e7/日，约为所测地板的 3.9× / ' +
    'capacity-ceiling-unmeasured（liq-2 5e7 / liq-3 1e8 在 builder 的 FLOORS 表中已声明、未跑） / ' +
    '⚠ 地板只改选择不改成交价（滑点仍为 0），是「不碰吃不下的名字」的纪律版容量问题，不是真实冲击成本',
  description:
    '1 次回测（TRAIN 2024，epoch 9，365 天）。对照未另跑：按 orchestrator ruling 1，builder 走的是归一化器同一条 py2to3 + OVERRIDE 路径，' +
    '故单行变体可直接对 2.6282 读。LIQFLOOR 日志 41 行、0 ERROR。所有数字由记录者对 data/series/' +
    '2026-10-26_中小盘趋势策略_年化_85-0a7de9fa__train__e9.json 与 study_小市值_variants_0a7de9fa-liq-1__train__e9.json 两条存盘曲线复核过，' +
    '非取自执行者报告（两条曲线各 242 天，末值 276.82 / 258.59）。',
  implication:
    '按「支」重新定界本族 realizability——这是本轮的**产物**而不是建议：champion 0a7de9fa 在自己的可行性下限上**测得 R=2**，' +
    '而 frontmatter 原有的 R=1 是在**另一支**（低开剥头皮：base 7a1c225f、8dbd994c、5e874b5b、前 champion a30641fb）上测的，' +
    '按 realizabilityScope 自述本就不覆盖当前候选书。故本轮直接改 realizability: 2，并把两处 carve-out（低开支仍 R=1 by its own evidence、' +
    '399101 周度轮动支仍未评分）写进 scope、realizabilityBasis 改为叠加式——本族不再被一个不适用于候选的分数挡在 exit gate 外。' +
    '同时开出下一次测量：容量曲线 liq-2 (5e7) / liq-3 (1e8)，因为所测的 1e7 只约束年初，到 12-05 的单笔 1,939,339 意味着当时需 3.88e7，' +
    '下半年欠约束约 3.9× —— 这正是给 2 而不给 3 的理由（判据同 大小盘轮动 的产品：容量是「能吃下多少」，不是「闸门上还剩多少余量」）。' +
    '不要把本条读成「容量已知」。',
  spawned: 'q-e9-champ-liq-2',
  edgeRef: '规模',
});

rq.add('小市值', {
  id: 'q-e9-champ-liq-2',
  kind: 'understand',
  rank: 26.5,
  status: 'queued',
  title: '容量曲线：champion 0a7de9fa 在 5e7 / 1e8 地板下还剩多少（liq-2 / liq-3，已构建未跑）',
  hypothesis:
    'q-e9-champ-liq 已测得 1e7（年初可行性下限）只剔掉 1.96% 的候选、objective 2.6282→2.4459。' +
    '但仓位随权益复利：2024-12-05 单笔配置 1,939,339 ⇒ 当时实际需要 3.88e7/日，故 1e7 对下半年欠约束约 3.9×。' +
    '预注册：liq-2 (5e7) 若 objective ≥ 1.0 且 sharpe ≥ 1.0 ⇒ 容量覆盖实际峰值仓位，R=3 可被争取；' +
    '若 liq-2 过而 liq-3 (1e8) 不过 ⇒ 容量区间落在 ¥5e7–1e8，R 停在 2；若 liq-2 即不过闸 ⇒ 本书的 2.4459 依赖它在下半年填不满的名字，R 退回更严的读法。',
  why:
    '本族 realizability 刚从 1（另一支的分数）改为 2（champion 自测），而 2 与 3 的差别恰恰是容量上限——' +
    '现在未测。判据同 大小盘轮动 的产品：容量是「能吃下多少」，不是「闸门上还剩多少余量」，所以不能用 6.59 的 sharpe 余量代替测量。',
  design:
    '两点已在 study/小市值/build-liq-0a7de9fa.js 的 FLOORS 表中声明（5e7 = 5×、1e8 = 10×），跑前固定、不按口味补点。' +
    '同一个单行插入点（L248），同一个 filter_liquidity_floor helper，同样在 context.previous_date 求值。' +
    '⚠ 报告必须数 LIQFLOOR 行里 in>out 的次数与 slots，并区分「剔除」与「持仓饿死」（1e7 下 40 次非空调用全部 slots=2）。' +
    '⚠ q-e8-3 的教训：helper 每次 rebalance 调 get_price(count=20)，地板咬得越狠候选越多、跑得越慢——' +
    '本书固定 2 仓，候选数不随持仓数反馈膨胀，但若 liq-3 出现 cap/phantom，先改成一次性预计算中位数序列，不要直接重跑。',
  from: [
    'q-e9-champ-liq（本轮：1e7 剔 1.96%，Δobj −0.1823，仍大幅过闸；3.88e7 的峰值仓位推导）',
    'q-e9-liq-5a70adc1（同族周度 8 仓书：2.5e6 逐位相同 / 12.5e6 −1.9% / 25e6 −26% 仍 sharpe 3.99）',
    '大小盘轮动 liq-1..liq-3（¥1M 过 / ¥5M 过 / ¥10M sharpe 1.32 不过闸 ⇒ 产品记 2 不记 3）',
    'q-e8-3（helper 按 rebalance 调 get_price 的不利反馈，liq-2 因此 cap 且无数字）',
    'wiki/families/小市值.md frontmatter realizability: 2 / realizabilityScope（本轮改写）',
  ],
  edgeRef: '规模',
  note: 'CONTROL 同 q-e9-champ-liq：champion 自身的 epoch-9 台账行 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00（365d），曲线在盘。',
});

console.log('recorded q-e9-champ-liq; queued q-e9-champ-liq-2');
