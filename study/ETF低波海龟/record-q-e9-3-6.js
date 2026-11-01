// One-shot recorder input for q-e9-6 + q-e9-3 (2026-11-01). Run once; recordFinding appends.
const rq = require('../../utils/research-queue');
const F = 'ETF低波海龟';
const have = new Set(rq.findings(F).map(f => f.qId));
if (have.has('q-e9-3') || have.has('q-e9-6')) { console.error('already recorded — refusing to append twice'); process.exit(2); }

rq.recordFinding(F, {
  qId: 'q-e9-6', type: 'understand',
  component_or_param: '参照：14 只风险池等权买入持有（首日买入、年内不调仓，无排序无叠加，冻结 OVERRIDE 与成本）',
  metric_delta: 'EW vs base Δobj −0.0775 / Δsharpe −0.57 / ΔmaxDD +0.69；行情外 236 天 −8.24% vs +0.76%',
  window: 'train',
  finding: 'TRAIN 2024（242 点，曲线末值 15.45 经 orchestrator 校验）：池等权 B&H total 15.45 / sharpe 0.65 / maxDD 13.65 / obj 0.0180；base 22.51 / 1.22 / 12.96 / 0.0955。按 09-24..10-08 拆分：该两周 等权 +25.82%（base +21.58%），其余 236 天 等权 −8.24%（sharpe rf0 −0.52；base +0.76% / 0.13）。即最低波排序在 sharpe 上胜等权（1.22 vs 0.65），决定性的差距在行情外（+0.76% vs −8.24%），而等权抓到的行情反而更多。',
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific (2024 单窗口；9 月刺激行情主导全年); 等权臂同时去掉了叠加与换仓（不只是换排序键）',
  description: 'variant study/ETF低波海龟/variants/q-e9-6.py（builder study/ETF低波海龟/build-q-e9-3-6.js）；分段 study/ETF低波海龟/q-e9-3-6-seg.js；曲线 data/series/study_ETF低波海龟_variants_q-e9-6__train__e9.json；对照 ledger 4a8bcfd5 e9 行。跑完 edge.test 的『池内等权』一半（与 q-e9-2 合起来池内半边完整）。',
  implication: '(1) 与 q-e9-2 合读：池内低波选择 = 行情外避损（等权 −8.24% → base +0.76%），不是行情捕获（等权 +25.82% > base +21.58%）⇒ 凡以『抓到更多 9 月行情』为卖点的 improve 想法是 off-mechanism；VAL/OOS 的预期写为『行情外持平、行情内少于等权』。(2) edge 低波动异象 的池内半边现已通过（最低 > 等权；最高/中位全年最差），但 claim 的池分句（「而不是池子里恰好有 2024 年的赢家」）未触达 ⇒ 保持 proposed；q-e9-4（点时权益池）是唯一剩余的门控测试，应排为下一条 understand。(3) 等权在行情外 −8.24% 说明手选 14 只池本身在 2024 行情外是亏的 ⇒ base 的正收益不是『池子都在涨』，这削弱（不排除）后见池解释，q-e9-4 不宜预设失败。',
  spawned: 'q-e9-4 (now the sole open half of edge.test)',
  edgeRef: '低波动异象',
});

rq.recordFinding(F, {
  qId: 'q-e9-3', type: 'understand',
  component_or_param: '海龟叠加消融：建仓即 100%（4 Unit），删除加仓/止损/止盈调用点，持有至换仓；选股/换仓/避险逐字不动',
  metric_delta: 'overlay-off vs base Δobj −0.0251 / Δsharpe +0.02 / ΔmaxDD +0.82；行情外 236 天 +12.82% vs +0.76%',
  window: 'train',
  finding: 'TRAIN 2024（242 点，曲线末值 20.82 经 orchestrator 校验）：叠加关闭 total 20.82 / sharpe 1.24 / maxDD 13.78 / obj 0.0704；base 22.51 / 1.22 / 12.96 / 0.0955。按 09-24..10-08 拆分：该两周 关闭 +7.09%（base +21.58%），其余 236 天 关闭 +12.82%（sharpe rf0 1.04；base +0.76% / 0.13）。持仓链：红利 01-02..01-30 → 黄金 ..05-06 → 50ETF ..09-25 → 黄金 ..12-31（3 次换仓）。它在 09-25（行情第 2 天）离开 50ETF：无止损时 20 日最短持有期早已过期，黄金波动率低 >10%。base 里 09-04 的 4N 止损 + 09-05 再入场把 hold_days 重置，正是最短持有期让 base 在 50ETF 里一直待到 10-08。',
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific (2024 单窗口；9 月刺激行情); path-dependent (base 的领先来自一次止损/再入场重置持有计数)',
  description: 'variant study/ETF低波海龟/variants/q-e9-3.py（builder study/ETF低波海龟/build-q-e9-3-6.js）；分段 study/ETF低波海龟/q-e9-3-6-seg.js；曲线 data/series/study_ETF低波海龟_variants_q-e9-3__train__e9.json；对照 ledger 4a8bcfd5 e9 行。跑的就是 edge 海龟加仓止损叠加 的 test 原文。',
  implication: 'edge 海龟加仓止损叠加 REFUTED（claim 是正的风险调整贡献；消融后 sharpe 1.24 ≥ 1.22，方向相反），同写改为 refuted。(a) base 对关闭版的 objective 领先（+0.0251）全部来自行情两周，且是经止损/再入场重置最短持有计数得到的路径偶然 ⇒ 叠加关闭的 q-e9-3 书（行情外 +12.82%，sharpe 1.04）是本族机制更诚实的表示、较少依赖一个两周，后续 improve 想法以它为基而不是以 base 为基。(b) i-e9-3（最低波 3 只逆波动加权）的前提正是本结果 ⇒ 转为 LIVE，从 q-e9-3 变体构建。(c) i-e9-1（只去止盈）在整个叠加被 refuted 后失去意义 ⇒ 关闭（dropped, rejected-by-finding），不花回测。(d) 国债避险腿仍未测试（TRAIN 惰性），本结果不涉及。(e) 按 objective base 仍排第一 ⇒ 候选选择不得只按 objective，objective 在此奖励的是一次路径偶然——记入 §4。',
  spawned: 'i-e9-3 (now live, built from q-e9-3); i-e9-1 closed',
  edgeRef: '海龟加仓止损叠加',
});

const q = rq.load(F);
for (const e of q) {
  if (e.id === 'q-e9-3' || e.id === 'q-e9-6') e.status = 'done';
  if (e.id === 'i-e9-1') {
    e.status = 'dropped';
    e.note = 'rejected-by-finding q-e9-3 (2026-11-01): 整个海龟叠加消融后 sharpe 不降（1.24 vs 1.22），edge 海龟加仓止损叠加 refuted；只去止盈是被否定叠加的一个子件，不再值一次回测';
  }
  if (e.id === 'i-e9-3') {
    e.why = e.why + ' ‖ q-e9-3 (2026-11-01): 条件满足——叠加 refuted（sharpe 1.24 vs 1.22，行情外 +12.82% / 1.04）⇒ 本条 LIVE，从 variants/q-e9-3.py 构建，对照 = q-e9-3（obj 0.0704 / sharpe 1.24），须拆 09-24..10-08 段';
    e.note = 'live after q-e9-3';
  }
}
rq.save(F, q);
console.log(q.map(e => e.id + ':' + e.status).join(' '));
