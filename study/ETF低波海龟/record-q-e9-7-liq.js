// One-shot recorder input for q-e9-7 (gold removed) + liq-e9-1 (own-size liquidity floor), 2026-11-01.
// Run once; recordFinding appends.
const rq = require('../../utils/research-queue');
const F = 'ETF低波海龟';
const have = new Set(rq.findings(F).map(f => f.qId));
if (have.has('q-e9-7') || have.has('liq-e9-1')) { console.error('already recorded — refusing to append twice'); process.exit(2); }

rq.recordFinding(F, {
  qId: 'q-e9-7', type: 'understand',
  component_or_param: '黄金在/不在：手选 14 只风险池去掉 518880 黄金ETF（14 → 13 只），母本 q-e9-3（叠加关闭），其余逐字不动',
  metric_delta: 'vs q-e9-3 Δobj +0.0172 / Δsharpe −0.40 / ΔmaxDD −3.07；行情两周 +23.75% vs +7.09%；其余天 −3.46%（rest sh −0.15）vs +12.82%（1.04）',
  window: 'train',
  finding: 'TRAIN 2024（242 点，曲线末值 19.47 经 orchestrator 校验）：去黄金 total 19.47 / sharpe 0.84 / maxDD 10.71 / obj 0.0876；母本 q-e9-3 20.82 / 1.24 / 13.78 / 0.0704。09-24..10-08 两周 +23.75%（q-e9-3 +7.09%），其余天 −3.46%（rest sharpe −0.15；q-e9-3 +12.82% / 1.04）。持仓链 红利 → 银行 → 50ETF（至 09-30）→ 红利 → 国债（1 天）→ 豆粕 → 国债 → 纳指。去掉黄金后避险腿开始放行：13 只池中位波动 >0.40 共 50 天（峰值 41.32%，12-02），国债持有 19 天。⚠ objective 上升（0.0704 → 0.0876）而 sharpe 跌破 1.0 闸（1.24 → 0.84）：maxDD 降得比 annual 多。',
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific (2024 单窗口；9 月刺激行情); objective-misrank (obj 升而 sharpe 跌破闸)',
  description: 'variant study/ETF低波海龟/variants/q-e9-7.py（builder study/ETF低波海龟/build-q-e9-7.js，断言 diff 恰为删除 518880 一行）；日志 study/ETF低波海龟/logs/q-e9-7-train.log；曲线 data/series/study_ETF低波海龟_variants_q-e9-7__train__e9.json；对照 q-e9-3 变体。预声明：行情外收益落到 PIT 附近（≈ +3.8%）⇒ 黄金承载；≥ ~+10% ⇒ 不是黄金。结果 −3.46% ⇒ 黄金承载（且超出预期：行情外不只降到 PIT 水平，而是转负）。',
  implication: '(1) 手选池的行情外避损**全部**是黄金：去掉一只名字，行情外 +12.82% → −3.46%，比点时权益池（+3.80%）还差 ⇒ 手选书在行情外的 sharpe 是一个单资产（黄金）结果，不是低波排序在 14 只截面上的作用；除一个两周外本书近乎持平到为负。(2) ⇒ VAL 读法改变：黄金在 2025 同样大涨，14 只池 base 的 VAL 2025 通过将被读成黄金，而不是低波排序——这是 decline 或 redirect 本族 VAL（例如改到不含黄金的池/点时权益池书上，并事先声明拆段）的证据，不应把唯一一次验证花在 14 只池 base 上。(3) 新脆弱性：避险腿是否放行取决于池里是否有一只低波名字压低中位数——去掉黄金就从 0/242 天变为 50 天 ⇒ 避险腿的触发是池构成的函数，不是市场状态的函数，记入 §4。(4) objective 再次误排（升 0.0172 而 sharpe 跌破 1.0），与 q-e9-3 的 §4 张力同向：本族任何候选比较须并报 sharpe 与拆段，不得按 objective 单排。(5) edge 低波动异象 保持 measured，但作用域再收窄：手选池上的「异象」= 持有黄金；只有点时权益池（q-e9-4，红利/银行）是不依赖黄金的读数。',
  spawned: 'none (VAL decline/redirect is the orchestrator decision; safe-leg fragility recorded as §4 gap)',
  edgeRef: '低波动异象',
});

rq.recordFinding(F, {
  qId: 'liq-e9-1', type: 'understand',
  component_or_param: 'realizability：base 加买入侧流动性下限 2e7 元/日（capital 1e6 / 1 只 / order_volume_ratio 0.05，从 harness 读），20 日平均成交额；其余逐字不动',
  metric_delta: 'vs base Δobj 0 / Δsharpe 0 / ΔmaxDD 0（max|Δcum| = 0 over 242 pts）',
  window: 'train',
  finding: 'TRAIN 2024（242 点，曲线末值 22.51 经 orchestrator 校验，max|Δcum| = 0 vs base）：22.51 / sharpe 1.22 / maxDD 12.96 / obj 0.0955，与 base 逐位相同。下限只剔除 159768 房地产ETF银华（79/242 天），而它本就从未被选中。可选名字中最薄的是 159870 化工，20 日均额最低 24.9M（≈ 1.25× 下限）；实际持有的 红利/黄金/50ETF 日成交 227M–1.7B。5×/10× 下限未跑。',
  confidence: 'high',
  flags: '⚠零滑点高估; regime-specific (2024 单窗口); 单持仓 100%（容量上限未测）',
  description: 'variant study/ETF低波海龟/variants/liq-e9-1.py（builder study/ETF低波海龟/build-liq-e9-1.js，断言 parent sha256 + 下限由 harness 计算）；日志 study/ETF低波海龟/logs/liq-e9-1-train.log；曲线 data/series/study_ETF低波海龟_variants_liq-e9-1__train__e9.json；对照 ledger 4a8bcfd5 e9 行。',
  implication: '(1) realizability 在本书自身尺寸上测得：下限惰性、曲线逐位相同 ⇒ R=1 被测量否定，R≥2 已挣得；写入 frontmatter `realizability: 2`，exit gate 的 realizability 阻塞解除（gate 的剩余阻塞是 VAL，由 orchestrator 决定）。(2) R=3 未挣得：5×/10× 下限未跑，容量上限未测；但持有名字有 >10× 余量（227M–1.7B vs 2e7），最可能先咬的是 化工（≈1.25×）一类从未被选中的边缘名字 ⇒ 若要 R=3 只需跑 1e8 一点，非优先。(3) 惰性是池构成的偶然（手选 14 只全为大流动 ETF，地产 ETF 是唯一薄名），⚠ 任何改池的变体（点时池、去黄金等）都会重开此轴，引用其数字前须重跑 liq。',
  spawned: 'none (5×/10× floors optional for R=3; not queued)',
  edgeRef: 'realizability',
});

const q = rq.load(F);
for (const e of q) {
  if (e.id === 'q-e9-7') {
    e.status = 'done';
    e.result = '去黄金 on q-e9-3：19.47 / sh 0.84 / maxDD 10.71 / obj 0.0876 vs 20.82 / 1.24 / 13.78 / 0.0704；行情两周 +23.75% / 其余 −3.46%（rest sh −0.15）vs +7.09% / +12.82% / 1.04。避险腿放行 50 天（中位峰值 41.32%），国债 19 天。⇒ 手选池行情外避损全部是黄金；VAL 2025 在 14 只池 base 上将被读成黄金；obj 升而 sharpe 跌破闸';
  }
  if (e.id === 'liq-e9-1') {
    e.status = 'done';
    e.result = '2e7 下限 on base：逐位相同（max|Δcum| 0；22.51 / 1.22 / 12.96 / 0.0955）。只剔除 159768 地产（79/242 天，从未被选）；最薄可选 159870 化工 24.9M ≈1.25×；持仓日额 227M–1.7B ⇒ R=2（3 未挣得，5×/10× 未跑）';
  }
}
rq.save(F, q);
console.log(rq.load(F).map(e => e.id + ':' + e.status).join(' '));
