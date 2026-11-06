// Step-0 (new-members) finding for the 2026-11-06 second re-invocation. Zero cost. Idempotent by qId.
//   node -e "require('./study/打板短线/record-nm12.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-11-06b', type: 'probe',
  component_or_param: '新成员 16d201f2 三连阳新五福·年化374.51%（git ba6b86d）：第 81–550 行是低位三连阳首板接力第 3 版代码体（与 215cfc4a 同一函数集，09:31 买、MarketOrderStyle(开盘价)、11:25 / 13:30 / 14:55 卖 + 分钟止盈止损），尾部逐字附加 五福 v5.1 ETF 模块，只在股票腿空仓时持有、股票买入一触发即 sell_all_etf 清仓——五福 是闲置资金停车位',
  metric_delta: 'epoch 9：obj 0.3029 / annual 68.70 / sharpe 1.35 / maxDD 38.41，过闸；2024 H1 +32.1 / H2 +27.7（Q 39 / −5 / −9 / 40）。对照：同股票腿的纯三连阳书 2024 五本全 DQ（−0.46 … −0.30）',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9 归一化行与曲线切片）',
  finding: '三连阳股票腿 + 五福 ETF 停车位的组合书过闸（0.30 / 1.35），而同一股票腿单独成书在 2024 五本全 DQ；形状两个半年都正，没有打板血统的上半年肥尾。最可能的读法：过闸来自 五福 ETF 腿在股票腿空仓日的收益，而不是三连阳腿——与 bba95a11（小盘 + 五福停车）同一结构。未消融，属于跨书推断',
  confidence: 'low（归因未经消融：关掉 五福 腿的单点 diff 才能证实）',
  flags: 'zero-cost · step-0-exit · 三连阳-stock-leg + 五福-idle-parking · combination-book · attribution-unablated · R1-family',
  description: '数据：harness/normalize-train.tsv e9 行；data/series/<slug>__train__e9.json 切片；源码 run_daily 表与函数表；data/family-assignments.tsv 分配说明（git ba6b86d）',
  implication: '关闭对 16d201f2 的单独研究：本家族的问题（三连阳腿）2024 已 5/5 DQ，五福 腿的贡献是 五福闹新春 的机制，且纯 ETF 动量书带 19–33% 的池子事后性（CLAUDE.md point-in-time 表），在本家族下消融它不改变本家族任何结论，家族 R=1 也让结果无处可去。若 五福闹新春 或 多策略分仓组合 想知道「停车位腿」值多少，关掉 sell_all_etf 之外的 五福 调度即是单点 diff——记在 §4 交给那边。valReopened: 9 下先前 basis 仍绑定，不花 VAL',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
