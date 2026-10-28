// Recorder helper: finding val-e9-i3 (the family's one epoch-9 VAL, on dxp-e9-i3).
const rq = require('../../utils/research-queue');
rq.recordFinding('大小盘轮动', {
  qId: 'val-e9-i3',
  type: 'validate',
  component_or_param: 'e9 候选 dxp-e9-i3（base 2f5bc859 去择时二，variants/i3-e9_no-s2.py）的唯一一次 epoch-9 VAL（runId dxp-e9-i3-val）',
  metric_delta: 'VAL obj 0.4676 vs TRAIN 1.1219（不同窗，不可直接比）；sharpe 4.11→2.54；maxDD 18.23→10.23',
  window: 'VAL 2025-01-01..2025-12-31（364d，243 点）',
  finding: 'VAL PASS：total 56.80 / annual 56.99 / sharpe 2.54 / maxDD 10.23 ⇒ objective 0.4676（记录者自曲线复核：final 56.80、maxDD 10.24 于 2025-11-17→12-17、obj 0.4676）。预注册线 sharpe ≥ 1.0 过，且 objective 如预注册所料远低于 TRAIN 的 1.1219。逐半年 H1 +37.76% / H2 +13.82%。回撤小于 TRAIN 的 18.23。',
  implication: '本族 epoch-9 候选已定稿并验证：dxp-e9-i3 归档到 validated_strategies/dxp-e9-i3.py（gate_val pass），且 TRAIN/VAL 曲线俱在，可直接进入 integrate 的逐年 sharpe 闸——下一步是集成，不是再开研究回合；本台 VAL 已用（val-budget BLOCKED），本族不得再换候选重验。⚠ 被验证的是 i3 这本书，不是 base 2f5bc859：base 在 e9 未经 VAL，不得作为「已验证」引用；e6 产品 dxp-imp-1 在本台上被取代。⚠ 2025 窗口对本族并非从未见过：epoch 6 的 VAL 让 always-small（dxp-imp-1）跑过 2025（+74.2% / DD 10.36），而选投票书而非 always-small 是按 2024 TRAIN 做的、方向与那份 2025 知识相反——故不是 selection-on-VAL，但也不能当作干净的首次留出。realizabilityScope 须移到本书（编排者负责）。',
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific（单年 TRAIN）; 2025 在 e6 被另一本书看过',
  description: 'build-e9-i3.js 构建；一处改动 g.enable_strategy_two=False + 四行仅日志；增益推断载体为 14:00 补仓路径',
  spawned: 'none',
  edgeRef: '规模 / 低价（选股链未动）；择时投票（去择时二）',
});
console.log('ok');
