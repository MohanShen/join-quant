// Records the epoch-9 round's findings into study/趋势技术/findings.tsv (idempotent by qId).
//   node -e "require('./study/趋势技术/record-e9.js')"
const rq = require('../../utils/research-queue');
const F = '趋势技术';
const have = new Set(rq.findings(F).map(f => f.qId));
const rows = [
  {
    qId: 'q-e9-val', type: 'validate',
    component_or_param: '家族 epoch-9 冠军 9befa9b8（600030 中信证券 单股 MA10 择时：价格 > MA10 全仓、< MA10 空仓；非页面基类 33b1b1e3，后者 08:00 读当日收盘，在 avoid_future_data 下无 epoch-9 行）在 VAL 2025 上的唯一一次验证',
    metric_delta: 'TRAIN 2024 obj 0.1912 / sharpe 1.03 / total 34.13 / maxDD 15.01 → VAL 2025 obj −0.1143 / sharpe −0.31 / total −0.72 / maxDD 10.71；gate_val fail（−0.31 < 1.0）',
    window: 'val 2025-01-01→2025-12-31（364d / 243 交易日）',
    finding: '冠军在 2025 上归零：全年 −0.72%、回撤 10.7%、sharpe −0.31，过不了 1.0 闸门。2024 的 34% 是一只券商股在 2024-09 V 型反转里的 beta（MA10 让它在场），择时器本身没有带到 2025 的东西；TRAIN 过闸只有 0.03 的边际，本就是桶里最薄的一次通过',
    confidence: 'high',
    flags: 'VAL-spent（epoch 9，本家族唯一一次）· gate_val-fail · single-stock · thin-train-margin(+0.03) · 零滑点台（中信证券流动性极深，折价可忽略）',
    description: 'study/趋势技术/champion-e9.py（build-e9.js：py2to3(源码)+OVERRIDE，与 normalizer 构造逐字节一致，TRAIN 曲线 …__train__e9 复现 ledger 行 34.13/15.01）；algorithmId 63c6c78d15c536ae8ce9a30c44f13f93；SUMMARY val 2025-01-01 2025-12-31 364 -0.72 -0.72 -0.31 10.71 completed；曲线 data/series/2026-06-08_十日均线策略-9befa9b8__val__e9.json（final cum −0.72，maxDD 10.71）；归档 validated_strategies/qsjs-e9-9befa9b8.py（gate_val: fail）；约 1 JQ 分钟',
    implication: '本家族 epoch 9 的 VAL 已花在一本失败的书上，出口闸门在本 bench 上到此为止（owner none/human，不再是 research 待办）——除非新成员改变冠军。关闭：单标的均线择时作为本桶的候选方向（五个同胞 + 冠军，TRAIN 全部 ≤1.03，VAL 归零）。打开（只在 TRAIN，不花验证）：桶内真正的血统 RPS 基类 33b1b1e3 在 epoch 9 上还没有清洁数——它的 e6 清洁书（e6-1，previous_date 改动）应在 TRAIN 2024 上复测一次，这是 8 条 stale closure 能否沿用的前提；§4 的「桶应拆」仍是结构性修复',
    spawned: 'q-e9-rps-clean',
    edgeRef: '',
  },
  {
    qId: 'q-e9-rps-clean', type: 're-measure',
    component_or_param: 'RPS 清洁基类（variants/e6-1_clean.py：基类 33b1b1e3 的 08:00 通道改 previous_date，其余原样）在 epoch-9 TRAIN 2024 上的复测——8 条 e6 closure 能否沿用的前提',
    metric_delta: 'TRAIN 2024：total 4.89 / annual 4.89 / sharpe 0.04 / maxDD 15.26 / obj −0.1037；对照 e6 bench（TRAIN 2022–23）annual 3.67 / sharpe −0.01 / maxDD 20.03；同窗沪深300 约 +15%（低约 10pp）；本 epoch 冠军 9befa9b8 0.1912 / 1.03',
    window: 'train 2024-01-01→2024-12-31（365d / 242 交易日）',
    finding: '换了 bench 结论不变：清洁的 RPS 书在 2024 年化 4.89%、sharpe 0.04、回撤 15.3%，比买入持有沪深300 低约 10pp，和 2022–23 上的 3.67% / −0.01 是同一个水平。2024 含 9 月 V 型反转这种对 MA20 闸门最坏的窗口，书没有爆、也没有赚——它仍然是「两个部件各自为负、合起来约等于零」的那本书',
    confidence: 'high',
    flags: 'bench-transfer · single-year · DQ（sharpe 0.04 ≪ 1.0）· ⚠零滑点台 · no-timer-control-on-2024（u-5 的指数择时器未在 2024 重跑，假设的「不优于择时器 +10pp」那一半未直接量；但书已低于买入持有，结论不依赖它）',
    description: 'study/趋势技术/variants/e6-1_clean.py 原样（build-e6.js 用 live OVERRIDE 重建后 git 无 diff，即 e6→e9 成本块逐字节相同）；algorithmId 5b252b04aeb2ea762b86af454377f3ce；SUMMARY train 2024-01-01 2024-12-31 365 4.89 4.89 0.04 15.26 completed；曲线 data/series/study_趋势技术_variants_e6-1_clean__train__e9.json；约 2 JQ 分钟。预注册证伪项（obj ≥ 0.19 或 sharpe ≥ 1.0）未触发',
    implication: '关闭（本 bench）：RPS 血统作为候选来源——基类在 2024 距 1.0 闸门差 0.96 个 sharpe，8 条 e6 stale closure 讨论的是旋钮与耦合，而旋钮在一本 sharpe 0.04 的书上无论开关都到不了候选，所以它们不必在 2024 逐条重测，按「基类本身出局」一并封存；两条 measured edge 保持原状（它们量的是部件间的相对效应，本次没有跑它们的 test，不升不降）。本家族在 epoch 9 的状态：VAL 已花且失败、桶内 7 本单标的均线/趋势择时书无一过闸、唯一有机理的血统在新窗上仍为零——无新成员改变冠军之前，不再有 research 待办；结构性修复仍是 §4 的「桶应拆」',
    spawned: 'none',
    edgeRef: '',
  },
];
let n = 0;
for (const r of rows) if (!have.has(r.qId)) { rq.recordFinding(F, r); n++; }
console.log(`record-e9: wrote ${n}, findings now ${rq.findings(F).length}`);
