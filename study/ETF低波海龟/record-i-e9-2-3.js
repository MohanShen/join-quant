// One-shot recorder input for i-e9-3 (3-name 1/vol on q-e9-3) + i-e9-2 (downside semi-dev on base),
// 2026-11-01, plus the i-e9-4 queue entry i-e9-3 opens. Run once; recordFinding appends.
const rq = require('../../utils/research-queue');
const F = 'ETF低波海龟';
const have = new Set(rq.findings(F).map(f => f.qId));
if (have.has('i-e9-3') || have.has('i-e9-2')) { console.error('already recorded — refusing to append twice'); process.exit(2); }
if (rq.load(F).some(e => e.id === 'i-e9-4')) { console.error('i-e9-4 already queued — refusing'); process.exit(2); }

rq.recordFinding(F, {
  qId: 'i-e9-3', type: 'improve',
  component_or_param: '最低波 3 只风险 ETF、权重 ∝ 1/vol，仅在持仓集合变化时再平衡，逐名 20 日最短持有 + 10% 换仓带；母本 q-e9-3（叠加关闭），手选 14 只池与国债腿逐字不动',
  metric_delta: 'vs q-e9-3 Δobj +0.0898 / Δsharpe +0.54 / ΔmaxDD −4.75；行情两周 +13.03% vs +7.09%；其余天 +10.64%（rest sh 1.08）vs +12.82%（1.04）',
  window: 'train',
  finding: 'TRAIN 2024（242 点，曲线末值 25.05 经 orchestrator 校验）：3 只 1/vol total 25.05 / sharpe 1.78 / maxDD 9.03 / obj 0.1602；母本 q-e9-3 20.82 / 1.24 / 13.78 / 0.0704。09-24..10-08 两周 +13.03%（q-e9-3 +7.09%），其余天 +10.64%（rest sharpe 1.08；q-e9-3 +12.82% / 1.04）。持仓集合链：红利/黄金/银行 → 50/银行/黄金（03-19）→ 50/红利/银行（05-22）→ 50/红利/黄金（09-02）→ 豆粕/红利/黄金（09-30）→ 豆粕/纳指/黄金（11-07）；黄金在 12 个月中约 8.5 个月在持仓内。避险腿未放行（0 天）。首次提交因 jqdata `sum` 遮蔽内建函数失败，未计费，修正后重跑。',
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific (2024 单窗口；9 月刺激行情); 手选 14 只池含黄金（q-e9-7 的黄金依赖适用于本书）; 改池前 liq 未重跑（持仓仍为原池大流动名字）',
  description: 'variant study/ETF低波海龟/variants/i-e9-3.py（builder study/ETF低波海龟/build-i-e9-2-3.js）；日志 study/ETF低波海龟/logs/i-e9-3-train.log；曲线 data/series/study_ETF低波海龟_variants_i-e9-3__train__e9.json；对照 q-e9-3 变体。queue 预声明证伪：sharpe ≤ q-e9-3（1.24）⇒ 结果 1.78 未证伪。',
  implication: '(1) 判定 adopted（仅 TRAIN）：本书是本族目前最好的构造书（sharpe 1.78、maxDD 9.03，全面优于 q-e9-3 与 base），后续 improve 以它为基。(2) 改进是 on-mechanism 的：在 vol 排序低端加宽度提高风险调整收益，且不更依赖行情——行情外 sharpe 1.08 ≈ q-e9-3 的 1.04，行情两周贡献只从 +7.09% 升到 +13.03%（远低于 base 的 +21.58%）⇒ Δsharpe 主要来自分散降回撤，不是多抓一个两周。(3) 但它**不是 VAL 候选**：池仍是作者事后写的 14 只、黄金在持仓约 8.5/12 个月，q-e9-7 已测得手选池的行情外优势全部是黄金，而 2025 黄金同样大涨 ⇒ 本书的 VAL 通过会被读成黄金。(4) ⇒ 开 i-e9-4：同一 3 只 1/vol 构造搬到 q-e9-4 的点时权益池上，这才是本族可送 VAL 的形态；预声明 sharpe ≥ 1.0 且 ≥ q-e9-4 的 1.14，sharpe < 1.0 即证伪。(5) edge 低波动异象 status 不动（本次不是其 test，只是在已 measured 的 edge 上的一次 improve）。',
  spawned: 'i-e9-4',
  edgeRef: '低波动异象',
});

rq.recordFinding(F, {
  qId: 'i-e9-2', type: 'improve',
  component_or_param: '选股排序键：60 日总标准差 → 下行半方差 sqrt(mean(min(r,0)^2))×√252；母本 base（海龟叠加开），换仓阈值/叠加/池逐字不动',
  metric_delta: 'vs base Δobj +0.1516 / Δsharpe +0.53 / ΔmaxDD −2.82；rank-1 名字与 base 不同 18/242 天，持有名字不同 42/242 天',
  window: 'train',
  finding: 'TRAIN 2024（242 点，曲线末值 34.85 经 orchestrator 校验）：下行半方差 total 34.85 / sharpe 1.75 / maxDD 10.14 / obj 0.2471；base 22.51 / 1.22 / 12.96 / 0.0955。排序第 1 名只在 18/242 天与 base 不同，实际持有名字在 42/242 天不同。增益是路径依赖的：(a) 1 月起持黄金而非红利（行情外约 +5.8pp）；(b) 09-05 止损/再入场重置后在行情中加到第 4 个 Unit（两周内约 +5pp）——与 q-e9-3 所揭示的 base 叠加路径偶然同一机制。避险腿未放行；风险池半方差中位数最大 24.97%（离 0.40 更远）。',
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific (2024 单窗口；9 月刺激行情); path-dependent (经已 refuted 的叠加的止损/再入场重置); 仅在叠加开的 base 上测，未在 q-e9-3/i-e9-3 上测',
  description: 'variant study/ETF低波海龟/variants/i-e9-2.py（builder study/ETF低波海龟/build-i-e9-2-3.js）；对比 study/ETF低波海龟/i-e9-2-compare.js；日志 study/ETF低波海龟/logs/i-e9-2-train.log；曲线 data/series/study_ETF低波海龟_variants_i-e9-2__train__e9.json；对照 ledger 4a8bcfd5 e9 行。queue 预声明证伪：obj ≤ base 或选择序列与 base 相同——两者均未触发，但见判定。',
  implication: '判定 rejected：Δ 不是更好的风险度量，而是 18 天不同排序经已 refuted 的海龟叠加放大出的路径偶然（黄金早换入 + 一次止损/再入场重置后的第 4 Unit），与 q-e9-3 判定 base 领先为路径偶然同理 ⇒ 关闭「下行半方差替代总 std」这个旋钮**在叠加开的 base 上**，不得把 0.2471 当作本族水平引用，也不得据此在 base 上继续调排序键。⚠ 它**未在叠加关闭的书（q-e9-3 / i-e9-3）上测**：那里没有止损重置路径，结论可能不同——这是一个未关闭的问题而非已否定，非优先（排序键只在 18/242 天改变第 1 名，在 3 只构造上影响可能更小），不排队，记入 §4。另：半方差中位数峰值 24.97% 离 0.40 更远 ⇒ 若用于避险开关会使国债腿更惰性，任何组合须单独报放行天数。',
  spawned: 'none (semi-dev on the overlay-off / 3-name book left as a §4 gap, not queued)',
  edgeRef: '低波动异象',
});

const q = rq.load(F);
for (const e of q) {
  if (e.id === 'i-e9-3') {
    e.status = 'done';
    e.result = 'adopted（TRAIN only）：3 只 1/vol on q-e9-3 25.05 / sh 1.78 / maxDD 9.03 / obj 0.1602 vs 20.82 / 1.24 / 13.78 / 0.0704；行情两周 +13.03% / 其余 +10.64%（rest sh 1.08）vs +7.09% / +12.82% / 1.04。黄金持有 ~8.5/12 月 ⇒ 非 VAL 候选（手选含金池），开 i-e9-4（点时权益池）';
  }
  if (e.id === 'i-e9-2') {
    e.status = 'done';
    e.result = 'rejected：下行半方差 on base 34.85 / sh 1.75 / maxDD 10.14 / obj 0.2471 vs 22.51 / 1.22 / 12.96 / 0.0955；rank-1 不同 18/242 天、持有不同 42/242 天；增益 = 黄金早换入 + 09-05 止损重置后第 4 Unit 的路径偶然。仅在叠加开的 base 上测，未在 q-e9-3/i-e9-3 上测';
  }
}
rq.save(F, q);

rq.add(F, {
  id: 'i-e9-4', kind: 'improve',
  title: 'i-e9-3 的 3 只 1/vol 构造搬到 q-e9-4 点时权益 ETF 池（不含黄金）',
  hypothesis: '3 只逆波动加权在点时权益池上 sharpe ≥ 1.0 且 ≥ q-e9-4 的 1.14。证伪：sharpe < 1.0',
  why: 'on-mechanism（低波动异象）。i-e9-3 在手选含金池上 adopted 但不是 VAL 候选（q-e9-7：手选池行情外优势全部是黄金；黄金持有 ~8.5/12 月）。点时权益池是本族唯一不依赖黄金的读数（q-e9-4 sh 1.14），本条决定本族是否有可送 VAL 的书。1 次 TRAIN；须拆 09-24..10-08 段并报避险腿放行天数；改池 ⇒ 引用数字前须重跑 liq',
  design: '以 variants/i-e9-3.py 为母本，把 g.all_risk_etfs 手选 14 只替换为 variants/q-e9-4-pit.py 的池构建块（逐日 get_all_securities etf、上市 ≥250 日、20 日成交额中位 ≥2e7、权益类正则 + 511/513/518 前缀排除 + 手工 159980/159831），3 只 1/vol / 集合变化再平衡 / 逐名 20 日最短持有 + 10% 带 / 国债腿逐字不动；对照 = q-e9-4（19.78 / 1.14 / 9.34 / 0.1044）与 i-e9-3；--window train',
  from: ['i-e9-3', 'q-e9-4'],
  edgeRef: '低波动异象',
  rank: 1,
  status: 'queued',
});

console.log(rq.load(F).map(e => e.id + ':' + e.status).join(' '));
