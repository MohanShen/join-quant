// Findings of the ETF动量 epoch-6 rebuild round, recorded one at a time:
//   node -e "require('./study/ETF动量/record.js')('q-e6-0')"
const rq = require('../../utils/research-queue');
const F = 'ETF动量';
const W = 'train 2022-01-01→2023-12-31 (729d)';
const Z = '⚠零滑点台';
const B = 'base-e6 annual 36.15 / sharpe 1.41 / maxdd 17.47 / obj 0.1868';

const ROWS = {
  'q-e6-0': {
    type: 're-measure', window: W, confidence: 'high', edgeRef: '动量',
    component_or_param: 'base 0aa4028d（追电，11 只跨资产 ETF，25 日加权斜率×R² 持第一）原样 + epoch-6 OVERRIDE（study/ETF动量/baseline-e6.py）',
    metric_delta: 'Δ epoch 2 → 6: annual 47.05→36.15 (−10.90pp) / sharpe 1.67→1.41 / maxdd 17.40→17.47 / objective 0.2965→0.1868 (−0.1097)；total 85.21%；年度（曲线）2022 total 66.46 maxdd 17.47 sharpe~1.87，2023 total 11.33 maxdd 12.05 sharpe~0.48',
    finding: '纯动量 base 在 epoch-6 台上 objective 0.1868、sharpe 1.41，不过 1.5 闸；pin 吃掉 10.9pp 年化（作者自带 1bp 滑点与 2bp 基金佣金被替换），回撤不变。预注册证伪项（obj < 0.05 或 sharpe < 1.0）未触发。两年极不均衡：2022 赚 66%，2023 只赚 11%',
    implication: '本族所有 Δ 以 0.1868 为基线、且必须拆年度读：base 是一个「2022 年的策略」，与 [[七星高照]] 同形。旧 study（baseline..q-12、0.3830）全部作废为本族基线——它测的是 22152780 的小市值混合；其「规模因子」edge 属于 [[小市值]]，不再挂在本页',
    flags: `${Z}, regime-specific(2022), hypothesis-not-falsified`,
    description: '冻结台 epoch 6，一次跑完。池中 511090（30 年国债）/159525（红利低波）等在 2022 年初无行情，得分为 NaN 自动出局——池子是 2026 年写的',
    spawned: 'q-e6-1, q-e6-2, q-e6-3, q-e6-4, q-e6-5',
  },
  'q-e6-1': {
    type: 'edge-test', window: W, confidence: 'high', edgeRef: '动量',
    component_or_param: 'sort_values ascending False→True（variants/q-1_invert-rank.py，单行 diff）＝在 0<score≤4.8 的合格者里持得分最低者',
    metric_delta: `Δ vs ${B}: annual 36.15→10.62 (−25.53pp, 保留 29%) / sharpe 1.41→0.38 / maxdd 17.47→18.22 / objective 0.1868→−0.0760 (−0.2628)；日收益相关 0.31；年度 2022 total 66.46→14.13，2023 total 11.33→7.08`,
    finding: '反排后年化只剩 base 的 29%，objective 变负；预注册证伪项（反排年化 ≥ 75%）远未触发。差距主要在 2022（66 vs 14），2023 也同向（11.3 vs 7.1）。持池内最弱的正趋势者仍赚约 10%/年',
    implication: '动量 edge 从 proposed 升为 measured：本族 11 只池里排第一有信息，且两年同向（不同于 [[七星高照]] 有闸门时 2023 反转、[[五福闹新春]] 反排保留 78%）。这把 improve 的先验定在打分本身（窗口、R²），而不是叠择时或分散；同时池底约 10%/年 说明池子贡献了一个与排序无关的底，由 q-e6-3 拆',
    flags: `${Z}, edge-measured, 反排仍受 score>0 闸门约束（闸门测为惰性，见 q-e6-2，故无需在无闸门版复核）`,
    description: '冻结台 epoch 6，完成。卖出侧 target 同样取 rank()[:1]，买卖一致',
    spawned: 'q-e6-7, q-e6-8',
  },
  'q-e6-2': {
    type: 'edge-test', window: W, confidence: 'high', edgeRef: '趋势择时',
    component_or_param: "df[(score>0)&(score<=4.8)] → df[score<=4.8]（variants/q-2_no-abs-gate.py，单行 diff）＝总持得分第一者，不再因全池无正趋势而空仓",
    metric_delta: `Δ vs ${B}: annual 36.15→34.96 (−1.19pp) / sharpe 1.41→1.35 / maxdd 17.47→17.47 / objective 0.1868→0.1749 (−0.0119)；日收益相关 0.996；年度 2022 total 66.46→66.46（逐位相同），2023 total 11.33→9.39`,
    finding: '去掉绝对动量闸门几乎不改变任何东西：2022 逐位相同、2023 少 2pp，相关 0.996。预注册证伪项（Δobj > −0.05）触发：11 只跨资产池在 TRAIN 里几乎总有一只正趋势，闸门极少咬合',
    implication: '趋势择时 edge 关闭（refuted）：本族在跨资产池上不靠「无趋势就躲」。闸门是否有用取决于池子——它只在全池同跌时才咬合，跨资产池（黄金/国债/海外）让这种日子几乎不出现。所以闸门相关的 improve（放宽、加 MA 择时、借 [[五福闹新春]] 的 breadth 切换）不排队；闸门的价值只能在单一资产类别池上测，见 q-e6-3',
    flags: `${Z}, edge-refuted, near-inert`,
    description: '冻结台 epoch 6，完成。上限 4.8 保留，止损保留',
    spawned: 'q-e6-3',
  },
  'q-e6-3': {
    type: 'isolate', window: W, confidence: 'high', edgeRef: '动量',
    component_or_param: 'g.etf_pool 换为新成员 0717871e 的 A 股 4 只（510300/510500/159915/159949），打分/闸门/止损不动（variants/q-3_ashare-pool.py）',
    metric_delta: `Δ vs ${B}: annual 36.15→−6.97 / sharpe 1.41→−0.89 / maxdd 17.47→20.32 / objective 0.1868→−0.2729 (−0.4597)；日收益相关 0.30；年度 2022 total 66.46→3.31 (maxdd 12.76)，2023 total 11.33→−15.98 (maxdd 20.27)。对照 0717871e（同打分、无闸门、5% 止损、10:00）：annual −22.17 / maxdd 41.48`,
    finding: '同一套打分+闸门+止损搬到 A 股宽基池，年化 −7%、objective −0.27；预注册证伪项（obj < 0）触发：收益属于跨资产池，不属于这套机制。与新成员 0717871e 比，闸门把 2022 熊市从大亏拉到 +3%、回撤从 41% 压到 20%——闸门在单一资产类别池上是真的；但 2023 A 股来回震荡里动量本身亏 16%',
    implication: '池子是本族收益的必要条件，而且是一个 2026 年事后写的池子（2022 有大行情的豆粕/黄金/海外都在里面）。这关闭「把本族机制推广到 A 股宽基/行业池」这个方向，并且决定了 VAL 的读法：2024–25 对一个 2026 年选的池子不是干净样本外。它也为 q-e6-2 给出条件：闸门的价值 = 池子里资产类别的同质度',
    flags: `${Z}, pool-is-source, hindsight-pool, 0717871e 的 −22% 中约一半是缺闸门造成的`,
    description: '冻结台 epoch 6，完成。这是新成员 0717871e 提出、本族从未问过的「机制 vs 池子」问题',
    spawned: 'q-e6-8',
  },
  'q-e6-4': {
    type: 'ablation', window: W, confidence: 'high', edgeRef: '趋势择时',
    component_or_param: 'stop_loss −0.10→−9（variants/q-4_no-stop.py，单行 diff）',
    metric_delta: `Δ vs ${B}: 逐位相同（85.21 / 36.15 / 1.41 / 17.47），Δobj 0`,
    finding: '去掉 −10% 止损后结果逐位相同；预注册证伪项（|ΔmaxDD| ≥ 1pp 或 |Δannual| ≥ 2pp）未触发：TRAIN 里止损一次也没先于排名换仓触发',
    implication: '止损这个旋钮关闭——日频重排在单只 ETF 跌 10% 之前就把它换掉了，调止损线不会动结果。本族的「风控」全部是排序本身，任何止损类 improve 不排队',
    flags: `${Z}, inert(exact)`,
    description: '冻结台 epoch 6，完成',
    spawned: 'none',
  },
  'q-e6-5': {
    type: 'ablation', window: W, confidence: 'med', edgeRef: '动量',
    component_or_param: "去掉 score≤4.8 上限（variants/q-5_no-cap.py，单行 diff）",
    metric_delta: `Δ vs ${B}: annual 36.15→33.90 (−2.25pp) / sharpe 1.41→1.28 / maxdd 17.47→17.47 / objective 0.1868→0.1643 (−0.0225)；日收益相关 0.941；年度 2022 total 66.46→60.92，2023 total 11.33→11.40`,
    finding: '去掉「不极端」上限 objective 降 0.0225，全部在 2022（−5.5pp），2023 不变；预注册（|Δobj| ≥ 0.02 即有作用）刚过线',
    implication: '上限有一个小而单年的作用：2022 年某段第一名的得分超过 4.8（年化斜率×R² > 380%），躲开它少亏了一点——这是一次事件的修补而不是机制，量级在 ~0.15pp 重跑漂移之上但只来自一个年份。保留但不作为 improve 方向（调上限=拟合那一次事件），旋钮关闭',
    flags: `${Z}, single-episode, 2022-only`,
    description: '冻结台 epoch 6，完成',
    spawned: 'none',
  },
  'q-e6-7': {
    type: 'ablation', window: W, confidence: 'med', edgeRef: '动量',
    component_or_param: 'return annual_ret*r2 → annual_ret（variants/q-7_no-r2.py，单行 diff）',
    metric_delta: `Δ vs ${B}: annual 36.15→23.27 (−12.88pp) / sharpe 1.41→0.87 / maxdd 17.47→21.71 (+4.24pp) / objective 0.1868→0.0156 (−0.1712)；日收益相关 0.83；年度 2022 total 66.46→54.18，2023 total 11.33→−1.45 (maxdd 19.41)`,
    finding: '去掉 R² 乘子 objective 掉 0.17，两年都更差，2023 由正转负；预注册证伪项（|Δobj| < 0.03）未触发：信息有相当一部分在「趋势是否平滑」而不只是斜率',
    implication: '动量 edge 的措辞收窄为「平滑的动量」：R² 把高斜率但锯齿的资产压下去，在 2023 的震荡里这是唯一的正收益来源。所以 on-mechanism 的打分改进应在平滑度这一侧（如 R² 门槛、更长窗的 R²），而不是在斜率一侧；⚠ 但去掉 R² 也让分数放大、4.8 上限咬合更多，两效应未拆',
    flags: `${Z}, component-measured, confound: 无 R² 时分数尺度变大，4.8 上限更常咬合`,
    description: '冻结台 epoch 6，完成',
    spawned: 'none',
  },
  'q-e6-8': {
    type: 'isolate', window: W, confidence: 'low', edgeRef: '动量',
    component_or_param: 'max_hold 1→11（variants/q-8_hold-all.py，单行 diff）',
    metric_delta: `Δ vs ${B}: annual 36.15→4.41 / sharpe 1.41→0.09 / maxdd 17.47→5.19 / objective 0.1868→−0.0078 (−0.1946)`,
    finding: '持全部合格者年化只剩 4.4%、回撤只有 5.2%——但这主要是现金拖累，不是等权池的收益：源码的买入按 available_cash/(max_hold−held) 分钱，max_hold=11 而合格者常只有 3–6 只时大半仓位闲置。预注册证伪项（≥90% 年化）未触发，但该读数被仓位不足混淆，不能作为「池平均」',
    implication: '这个问题没有被回答，但不再需要回答：q-e6-1 的反排（持最弱合格者、满仓）已经给出池底 ≈10%/年。同时它关闭一个 improve 方向的捷径——任何 max_hold>1 的变体必须先重写仓位分配（按目标数等分总资产），否则测到的是现金比例而不是分散；鉴于 [[七星高照]] q-e6-3 已测分散用收益换回撤、净降，本轮不排队',
    flags: `${Z}, confounded(cash-drag), uninformative-as-designed`,
    description: '冻结台 epoch 6，完成。设计缺陷记录在案，不重跑',
    spawned: 'none',
  },
  'etfmom-e6-imp-1': {
    type: 'improve', window: W, confidence: 'high', edgeRef: '动量',
    component_or_param: 'm_days 25→50（enhance/candidates/etfmom-e6-imp-1.py，单行 diff）',
    metric_delta: `Δ vs ${B}: annual 36.15→4.15 / sharpe 1.41→0.01 / maxdd 17.47→23.81 / objective 0.1868→−0.1966 (−0.3834)；日收益相关 0.56；年度 2022 total 66.46→4.22，2023 total 11.33→4.12`,
    finding: '放慢到 50 日，2022 从赚 66% 变成赚 4%，2023 也更差，objective −0.38。预注册采纳条件（两年 sharpe 都不低于 base 且 Δobj>0）不满足：rejected',
    implication: '放慢动量这个方向关闭：2022 的收益依赖短窗口抓住豆粕/海外的轮换，50 日太慢、跟不上。它同时开出一个必须回答的问题——25 日是平台还是孤峰（若是孤峰，动量 edge 是一个参数点而非现象），由 q-e6-9（20 日）回答',
    flags: `${Z}, rejected, lookback-fragile`,
    description: '冻结台 epoch 6，完成。§2 rejected 一行',
    spawned: 'q-e6-9',
  },
  'q-e6-9': {
    type: 'sensitivity', window: W, confidence: 'med', edgeRef: '动量',
    component_or_param: 'm_days 25→20（variants/q-9_m20.py，单行 diff）',
    metric_delta: `Δ vs ${B}: annual 36.15→29.10 (−7.05pp) / sharpe 1.41→1.17 / maxdd 17.47→15.03 (−2.44pp) / objective 0.1868→0.1407 (−0.0461)；日收益相关 0.72；年度 2022 total 66.46→52.65，2023 total 11.33→9.18`,
    finding: '20 日仍是同一本书的量级（objective 0.14，2022 赚 53%），相关 0.72；预注册（Δobj > −0.05 即平台）刚好成立。窗口曲线是 20→0.14、25→0.19、50→−0.20：短端平缓、长端断崖',
    implication: '动量 edge 保持 measured 但限定为「短窗口（约 20–25 日）的平滑动量」：短端是平台不是孤峰，长端不成立。25 日是平台上的局部高点，再细扫窗口只会拟合 2022，窗口旋钮关闭；本族不再有 on-mechanism 的参数方向，improve 队列清空',
    flags: `${Z}, plateau(short-side), lookback-asymmetric`,
    description: '冻结台 epoch 6，完成',
    spawned: 'none',
  },
};

module.exports = qId => {
  const r = ROWS[qId];
  if (!r) throw new Error(`no row for ${qId}`);
  rq.recordFinding(F, { qId, ...r });
  console.log('recorded', qId);
};
module.exports.ROWS = ROWS;
