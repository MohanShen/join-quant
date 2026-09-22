// Findings of the 七星高照 epoch-6 round, recorded one at a time:
//   node -e "require('./study/七星高照/record.js')('q-e6-0')"
const rq = require('../../utils/research-queue');
const F = '七星高照';
const W = 'train 2022-01-01→2023-12-31 (729d)';
const Z = '⚠零滑点台';

const ROWS = {
  'q-e6-0': {
    type: 're-measure', window: W, confidence: 'high', edgeRef: '动量',
    component_or_param: 'base 19ca0e69（七星 V1.7）原样 + epoch-6 OVERRIDE（study/七星高照/baseline-e6.py）',
    metric_delta: 'Δ epoch 2 → 6: annual 32.72→28.79 (−3.93pp) / sharpe 1.33→1.21 / maxdd 18.60→16.27 (−2.33pp) / objective 0.1412→0.1252 (−0.0160)；total 65.75%；年度拆分（曲线）2022 total 50.97 maxdd 14.68 sharpe~1.77，2023 total 9.75 maxdd 16.27 sharpe~0.39',
    finding: '纯七星 V1.7 在 epoch-6 台上几乎没被 pin 伤到（年化只少 3.9pp，回撤还小了 2.3pp），objective 0.1252、sharpe 1.21，不过 1.5 闸。预注册证伪项（obj < 0.05 或 sharpe < 1.0）未触发。但两年极不均衡：2022 赚 51%，2023 只赚 9.75%（sharpe~0.39），全窗最深回撤落在 2023',
    implication: '本族基线是一个「2022 年的策略」：之后任何 Δ 都必须拆年度看，只在 2022 成立的改进不算 on-mechanism。旧 study 的 0.4814 / q-1..q-5 全部作废为本族基线（它们测的是 406a1e4d 小市值混合），本轮所有 Δ 以 0.1252 为基线。与 [[五福闹新春]] 被 pin 吃掉 32pp 相反，七星几乎不受成本影响，说明它换手低——降换手类 improve 在本族没有空间，不排队',
    flags: `${Z}, regime-specific(2022), hypothesis-not-falsified`,
    description: '冻结台 epoch 6，一次跑完 43s。旧 study 基线 baseline.py = 406a1e4d 三马+七星16 混合 [0.5,0,0.5,0]，其 ETF 腿是 V1.6，不是本 base',
    spawned: 'q-e6-1, q-e6-2, q-e6-3, q-e6-4, q-e6-5',
  },
  'q-e6-1': {
    type: 'edge-test', window: W, confidence: 'med', edgeRef: '动量',
    component_or_param: 'get_ranked_etfs: etf_metrics.sort reverse=True→False（variants/q-1_invert-rank.py，单行 diff）＝持通过全部滤波的得分最低者',
    metric_delta: 'Δ vs baseline-e6: annual 28.79→6.43 (−22.36pp, 保留 22%) / sharpe 1.21→0.18 / maxdd 16.27→18.33 (+2.06pp) / objective 0.1252→−0.1190 (−0.2442)；日收益相关 0.31；年度 2022 total 50.97→2.77 (maxdd 17.07)，2023 total 9.75→10.18 (maxdd 7.04)',
    finding: '反排后年化只剩 base 的 22%，objective 变负，预注册证伪项（反排年化 ≥ 75%）远未触发——与 [[五福闹新春]]（反排保留 78%）相反，七星的 7 只池里选第一名是有信息的。但这份信息全部在 2022：2022 base 赚 51%、反排赚 2.8%；2023 反排 10.18% 反而略好于 base 9.75%，且回撤只有 7%',
    implication: '动量 edge 从 proposed 升为 measured，但收窄为「2022 单年」：在 2023 排序不带信息，反排持的是完全不同的资产（相关 0.31）却赚得一样多。这开出一个必须先答的问题——2022 的截面动量是不是只是「一路持有某一只大涨资产（原油/豆粕）」：若是，edge 是一次事后可见的商品牛市而非可重复的动量，需看 q-e6-3（持全部合格者）与 2022 的持仓集中度。它同时说明排序相关的 improve（调 lookback、R² 乘子）只能在 2022 找到证据，不单独排队',
    flags: `${Z}, edge-measured, regime-specific(2022-only), confound: 反排持的是通过「得分>0 且 10 日收益>0」滤波的最弱者，仍是正趋势资产，故这是「正趋势池内排序」的检验`,
    description: '冻结台 epoch 6，完成。反排的 sell 侧 target 同样取 ranked[:1]，买卖一致。2023 的持平说明 edge 不是全窗现象',
    spawned: 'q-e6-3',
  },
  'q-e6-2': {
    type: 'edge-test', window: W, confidence: 'high', edgeRef: '趋势择时',
    component_or_param: 'min_score_threshold 0→−1e9 且 use_short_momentum_filter True→False（variants/q-2_no-trend-gate.py，同一概念两行）＝不要求正趋势，总持池内得分第一者；3 日跌幅排除与盈利保护照旧可把它送进 511880',
    metric_delta: 'Δ vs baseline-e6: annual 28.79→39.33 (+10.54pp) / sharpe 1.21→1.70（过 1.5 闸）/ maxdd 16.27→20.44 (+4.17pp) / objective 0.1252→0.1889 (+0.0637)；total 93.95%；日收益相关 0.91；年度 2022 total 50.97→47.60 (maxdd 14.68→20.44)，2023 total 9.75→31.37 (maxdd 16.27→7.93)',
    finding: '关掉正趋势闸门后 objective 不降反升 +0.064、sharpe 升到 1.70 过闸。预注册证伪项（Δobj > −0.05）触发，趋势择时 edge 证伪。闸门在 2022 买到了回撤（maxDD 20.4→14.7，收益几乎不变），但在 2023 把收益从 31% 砍到 9.75%：2023 里它反复把本该持有的第一名踢进货币 ETF。两本书相关 0.91，差别集中在闸门触发的那些日子',
    implication: '趋势择时 edge 关闭（refuted）：本族的收益不来自「没趋势就躲」，与 [[五福闹新春]] 恰好相反（五福的收益只来自择时切池）。这直接开出一个 improve：去掉/放宽正趋势闸门本身就是一个过闸候选（sharpe 1.70），但它的代价是 2022 回撤 +5.8pp，必须先弄清闸门里是哪一半（score>0 还是 10 日收益>0）在 2023 误杀——拆开测，只保留在两年都不伤的那一半；并且 q-e6-1 的动量 edge 必须在无闸门版上复核，因为 2023 的赚钱正来自「持第一名不躲」',
    flags: `${Z}, edge-refuted, bundled: 两个正趋势条件一起关，未拆, 2022 maxdd 恶化 +5.76pp（回撤窗换到 2022）`,
    description: '冻结台 epoch 6，完成。闸门两部分：get_ranked_etfs 的 score > min_score_threshold（25 日加权斜率年化×R² > 0）与 10 日年化收益 > 0。无合格者时 base 持 511880',
    spawned: 'q-e6-6, q-e6-7, imp-1',
  },
  'q-e6-3': {
    type: 'isolate', window: W, confidence: 'high', edgeRef: '动量',
    component_or_param: 'holdings_num 1→7（variants/q-3_hold-all.py，单行 diff）＝等权持有全部通过滤波的 ETF',
    metric_delta: 'Δ vs baseline-e6: annual 28.79→18.44 (−10.35pp, 保留 64%) / sharpe 1.21→1.13 / maxdd 16.27→10.75 (−5.52pp) / objective 0.1252→0.0769 (−0.0483)；日收益相关 0.78；年度 2022 total 50.97→22.06，2023 total 9.75→14.93',
    finding: '把钱摊到全部合格 ETF 上，年化少三分之一多、回撤少 5.5pp，objective 降 0.048。预注册证伪项（年化 ≥ base 的 90%）未触发：集中持第一名确实是收益来源。损失全在 2022（51→22），2023 等权反而多赚（9.75→14.93）',
    implication: '「持全部合格者」这个分散方向关闭：它用收益换回撤，objective 净降。与 q-e6-1 合读，第一名 > 合格者平均 > 最后一名在 2022 清晰单调，说明排序在 2022 有信息；2023 的反常（等权与反排都好于 base）指向 base 的闸门在 2023 误伤第一名，而不是排序失效——由 q-e6-8 在无闸门版上复核',
    flags: `${Z}, isolate, holdings_num=7 时仍受同一套滤波与 511880 兜底`,
    description: '冻结台 epoch 6，完成',
    spawned: 'q-e6-8',
  },
  'q-e6-8': {
    type: 'edge-test', window: W, confidence: 'high', edgeRef: '动量',
    component_or_param: 'q-2_no-trend-gate + sort reverse=False（variants/q-8_invert-no-gate.py）；对照 = q-e6-2（无闸门版），非 baseline',
    metric_delta: 'Δ vs q-e6-2: annual 39.33→16.60 (−22.73pp, 保留 42%) / sharpe 1.70→0.62 / maxdd 20.44→13.68 / objective 0.1889→0.0292 (−0.1597)；日收益相关 0.06；年度 2022 total 47.60→17.53，2023 total 31.37→15.82',
    finding: '在不躲闪的书上把排序反过来，年化只剩 42%，且两年都一样：2022 47.6→17.5、2023 31.4→15.8。预注册证伪项（≥ 75%）未触发。两本书日收益几乎不相关（0.06），持的是完全不同的资产。即使持池内最弱者也能赚约 16%/年——池子本身有正漂移，动量在它之上再加约 23pp',
    implication: '动量 edge 由「仅 2022」改为两年都成立：q-e6-1 在 2023 看到的「排序无信息」是闸门把第一名踢进货币 ETF 造成的假象，不是动量失效。这确立本族的 improve 先验——on-mechanism 的方向是让资金更多时间留在第一名上（放宽/去掉误杀第一名的滤波），off-mechanism 的是加择时或分散。同时池本身约 16%/年的底 表明 7 只资产是事后可见的好池（黄金/纳指/原油在 2022–23 都有大行情），VAL 读数须带这条',
    flags: `${Z}, edge-measured, hindsight-pool: 反排仍赚 16%/年，池子贡献了底`,
    description: '冻结台 epoch 6，完成。无闸门下反排持池内得分最低者（可为负趋势），只受 3 日跌幅与盈利保护过滤',
    spawned: 'q-e6-6, q-e6-7',
  },
  'q-e6-6': {
    type: 'ablation', window: W, confidence: 'high', edgeRef: '趋势择时',
    component_or_param: 'min_score_threshold 0→−1e9（variants/q-6_no-score-gate.py，单行 diff）＝只关 25 日得分 > 0 要求，10 日过滤保留',
    metric_delta: 'Δ vs baseline-e6: annual 28.79→29.68 (+0.89pp) / sharpe 1.21→1.26 / maxdd 16.27→15.45 (−0.82pp) / objective 0.1252→0.1423 (+0.0171)；日收益相关 0.996；年度 2022 total 50.97→51.06，2023 total 9.75→11.21',
    finding: '只关 25 日得分闸门几乎不改变任何东西（相关 0.996，Δobj +0.017）。预注册（Δobj < +0.02）成立：得分 > 0 这道闸门基本被 10 日过滤覆盖，很少单独起作用',
    implication: '25 日得分闸门这个旋钮关闭——去掉或调它都不会动结果；q-e6-2 的全部效应归到 10 日短期动量过滤上（见 q-e6-7），后续 improve 只在那一个部件上做',
    flags: `${Z}, near-inert`,
    description: '冻结台 epoch 6，完成',
    spawned: 'none',
  },
  'q-e6-7': {
    type: 'ablation', window: W, confidence: 'high', edgeRef: '趋势择时',
    component_or_param: 'use_short_momentum_filter True→False（variants/q-7_no-short-filter.py，单行 diff）＝只关「10 日年化收益 > 0」过滤',
    metric_delta: 'Δ vs baseline-e6: annual 28.79→39.36 (+10.57pp) / sharpe 1.21→1.71（过闸）/ maxdd 16.27→20.44 (+4.17pp) / objective 0.1252→0.1892 (+0.0640)；total 94.03%；与 q-e6-2 几乎逐位相同（39.33/1.70/20.44）；年度 2022 total 50.97→47.60 (maxdd 14.68→20.44)，2023 total 9.75→31.42 (maxdd 16.27→7.89)',
    finding: '只关 10 日短期过滤就复现了 q-e6-2 的全部效应（+0.064，sharpe 1.71）。预注册（Δobj ≥ +0.04）成立：本族正趋势闸门的作用全部来自这条 10 日过滤。它在 2022 以不变的收益买到了 5.8pp 回撤，在 2023 砍掉了 21pp 收益',
    implication: '10 日过滤是本族唯一有量级的择时部件，且净为负。这开出本轮唯一的 improve 方向：去掉它（imp-1 = q-e6-7 本身，sharpe 1.71 过闸）或把它放慢到只在真正的下跌段咬合（imp-2：short_lookback_days 10→20）。判据必须拆年度：只在 2023 加分、同时把 2022 回撤推深的改动，是用一个年份的收益换另一个年份的风险，不是改进',
    flags: `${Z}, component-measured, 2022 回撤窗换到 2022、+5.76pp`,
    description: '冻结台 epoch 6，完成。10 日过滤：price[-1]/price[-11]−1 年化 < 0 即从排名剔除',
    spawned: 'imp-1, imp-2',
  },
  'q-e6-4': {
    type: 'ablation', window: W, confidence: 'med', edgeRef: '动量',
    component_or_param: 'enable_profit_protection True→False（variants/q-4_no-profit-protection.py，单行 diff）＝关掉「较昨日最高价回撤 5% 即卖并从排名剔除」',
    metric_delta: 'Δ vs baseline-e6: annual 28.79→31.45 (+2.66pp) / sharpe 1.21→1.34 / maxdd 16.27→15.60 (−0.67pp) / objective 0.1252→0.1585 (+0.0333)；日收益相关 0.991；年度 2022 total 50.97→49.64，2023 total 9.75→15.35 (maxdd 16.27→11.87)',
    finding: 'V1.7 的招牌盈利保护不是回撤压制器：关掉它回撤反而少 0.7pp、年化多 2.7pp，objective +0.033，改善几乎全在 2023。预注册「maxDD +2pp 以上」被证伪，惰性判据（|Δannual| < 2pp 且 |ΔmaxDD| < 1pp）也未成立——它是一个轻度净负的部件',
    implication: '盈利保护与 10 日过滤是同一类东西：把第一名从持仓里踢出去的滤波，在本族都是净负。这把 improve 先验收紧为「减少对第一名的误杀」，并开出 imp-3：在 imp-1（无 10 日过滤）上再关盈利保护，检验两者是否叠加；若不叠加，盈利保护只是 10 日过滤误杀的同一批日子',
    flags: `${Z}, hypothesis-falsified, 小量级（相关 0.991，只在 2023 可见）`,
    description: '冻结台 epoch 6，完成。盈利保护在 11:00 检查，并在排名计算里再检查一次',
    spawned: 'imp-3',
  },
  'q-e6-5': {
    type: 'ablation', window: W, confidence: 'high', edgeRef: '动量',
    component_or_param: 'g.loss 0.97→0.0（variants/q-5_no-loss-filter.py，单行 diff）＝关掉「近 3 日有单日跌幅 > 3% 即从排名剔除」',
    metric_delta: 'Δ vs baseline-e6: annual 28.79→21.92 (−6.87pp) / sharpe 1.21→0.92 / maxdd 16.27→16.67 (+0.40pp) / objective 0.1252→0.0525 (−0.0727)；日收益相关 0.956；年度 2022 total 50.97→37.64，2023 total 9.75→7.91',
    finding: '3 日跌幅排除是本族唯一明确净正的滤波：关掉它 objective 降 0.073，两年都降（2022 −13pp、2023 −1.8pp），回撤几乎不变。预注册的机理（回撤压制器）不对——它保的是收益而不是回撤：躲开刚刚急跌过的资产，避免在急跌后的续跌里持有',
    implication: '跌幅排除保留，不在 improve 里动它（去掉或放宽都是负方向，关闭）。它与 10 日过滤对照鲜明：同是短期过滤，只看「单日急跌」的保住收益，看「10 日方向」的误杀第一名——说明 improve 若要替换 10 日过滤，替代物应当是事件型（急跌）而非方向型；把 10 日窗口拉长（imp-2）仍是方向型，预期不如直接去掉',
    flags: `${Z}, hypothesis-falsified(机理), component-measured`,
    description: '冻结台 epoch 6，完成',
    spawned: 'imp-2',
  },
  'imp-1': {
    type: 'improve', window: W, confidence: 'med', edgeRef: '动量',
    component_or_param: 'use_short_momentum_filter True→False（enhance/candidates/qixing-imp-1.py，与 variants/q-7 相同，不重跑）',
    metric_delta: 'Δ vs baseline-e6 (= q-e6-7): objective 0.1252→0.1892 (+0.0640) / sharpe 1.21→1.71 / maxdd 16.27→20.44；分年 objective（total−maxdd）2022 36.29→27.16 (−9.13)，2023 −6.52→23.53 (+30.05)',
    finding: '全窗 objective +0.064 且过 1.5 闸，但按预注册的分年判据不合格：2022 的分年 objective 从 36.3 降到 27.2（收益少 3.4pp、回撤深 5.8pp），全部改善来自 2023',
    implication: '不采纳（rejected）：它是拿 2022 的回撤换 2023 的收益，两年 TRAIN 只能说明这笔交换在这两年划算，不能说明过滤本身无用；而 VAL 只有一次，不足以裁决年份交换。这关闭「直接去掉 10 日过滤」作为 VAL 候选，留下的开放问题是 2022 那 5.8pp 回撤由哪几次持仓造成——需要持仓级数据，不是再一次整体回测',
    flags: `${Z}, year-tradeoff, gate-pass-but-rejected`,
    description: '判据在 q-e6-7 记录时预注册（「只在 2023 加分、同时把 2022 回撤推深的改动不是改进」）',
    spawned: 'none',
  },
  'imp-2': {
    type: 'improve', window: W, confidence: 'med', edgeRef: '动量',
    component_or_param: 'short_lookback_days 10→20（enhance/candidates/qixing-imp-2.py，单行 diff）',
    metric_delta: 'Δ vs baseline-e6: annual 28.79→36.89 / sharpe 1.21→1.53 / maxdd 16.27→20.19 / objective 0.1252→0.1670 (+0.0418)；vs imp-1 −0.0222；年度 2022 total 57.44 maxdd 20.19，2023 total 18.88 maxdd 11.10',
    finding: '把 10 日过滤放慢到 20 日，objective 介于 base 与 imp-1 之间（0.1670 < 0.1892），且没有躲开 2022 的下跌段（2022 maxDD 20.19）。预注册的两条（obj > imp-1、2022 maxDD < 18%）都没达成',
    implication: '方向型过滤调窗口这个旋钮关闭：拉长窗口只是在「去掉过滤」与「原过滤」之间插值，既不保住 2022 的回撤，也拿不全 2023 的收益——与 q-e6-5 的读法一致，若要替换 10 日过滤，替代物应是事件型（急跌）而非另一个方向窗口',
    flags: `${Z}, hypothesis-falsified, interpolation`,
    description: '冻结台 epoch 6，完成',
    spawned: 'none',
  },
  'imp-3': {
    type: 'improve', window: W, confidence: 'high', edgeRef: '动量',
    component_or_param: 'imp-1 + enable_profit_protection False（enhance/candidates/qixing-imp-3.py）；对照 = imp-1',
    metric_delta: 'Δ vs imp-1: annual 39.36→39.33 / sharpe 1.71→1.70 / maxdd 20.44→20.59 / objective 0.1892→0.1874 (−0.0018)；日收益相关 0.992',
    finding: '在无 10 日过滤的书上再关盈利保护几乎没有变化（Δobj −0.002）。预注册证伪项（|Δ| < 0.01）触发：两个滤波不叠加',
    implication: '盈利保护单独 +0.033（q-e6-4）的收益与 10 日过滤误杀的是同一批日子——去掉 10 日过滤后它不再有可省的东西，这个旋钮在任何候选上都关闭',
    flags: `${Z}, hypothesis-falsified, non-additive`,
    description: '冻结台 epoch 6，完成',
    spawned: 'none',
  },
};

module.exports = id => {
  const r = ROWS[id];
  if (!r) throw new Error(`no row ${id}`);
  rq.recordFinding(F, { qId: id, ...r });
  console.log('recorded', id);
};
module.exports.ROWS = ROWS;
