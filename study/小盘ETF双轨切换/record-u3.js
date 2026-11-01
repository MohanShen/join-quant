// Recorder helper for u-3 (规模因子 declared test, asc -> desc). One-shot; guarded so a re-run
// cannot double-append.
const rq = require('../../utils/research-queue');
const F = '小盘ETF双轨切换';
if (rq.findings(F).some(r => r.qId === 'u-3')) { console.log('u-3 already recorded'); process.exit(0); }
rq.recordFinding(F, {
  qId: 'u-3',
  type: 'understand',
  component_or_param: '偷鸡选股 get_peg：market_cap.asc() → desc()（唯一改动；<¥10 / ROE / ROA 筛选与 DDDD 进场逐字保留）',
  metric_delta: 'Δobjective −0.6028 (0.7266→0.1238); sharpe 2.85→1.05; total 89.75→23.30%; maxDD 17.09→10.92',
  window: 'TRAIN 2024 (epoch 9)',
  finding: 'Size ablation (variant u-3-mcap-desc, builder build-u3.js, algorithmId 17687305caf412ddf970f7b978ad214f, curve study_小盘ETF双轨切换_variants_u-3-mcap-desc__train__e9, final cum 23.30 / maxDD 10.92 verified) scores total 23.30% / sharpe 1.05 / maxDD 10.92 / objective 0.1238. Same 3 decision days as base (02-20 / 09-30 / 11-21) and the same 摸狗 path (non-偷鸡 return +15.79 vs base +15.77), so the entire gap sits inside the 偷鸡 periods. Per 偷鸡 period (base → u-3): #1 +33.83 → +1.80, #2 +16.56 → −3.82, #3 +5.06 → +8.76; compounded +63.90 → +6.49 (queue confirm rule < +26%). Names held at first entry: base = 10 micro-caps (002247 聚力文化, 603580, 002188, 002629, 600778, 002830, 002316, 002836, 002295, 002715); u-3 = 10 mega-cap banks/oil/telecom (工行, 建行, 中石油, 农行, 中行, 中石化, 中国电信, 邮储, 交行, 中信银行), identical at all three entries. Side observation: those banks passed `indicator.roe > 0.15 and indicator.roa > 0.10`, consistent with quarterly-percent units (bank quarterly ROA ≈ 0.2%) — the filter looks near-inert, but u-5 is the test that settles it.',
  confidence: 'high',
  flags: '⚠零滑点高估; regime-specific (one-year TRAIN); n=3 entries (Feb-2024 period dominates)',
  description: 'edge 规模因子 declared test (asc → desc), run as stated; entry dates and 摸狗 leg unchanged, so not exposed to the ~0.6 lock-phase noise.',
  implication: '规模因子 → status measured: its declared test ran and the 偷鸡 return collapsed (+63.90 → +6.49), so the 偷鸡 leg is a micro-cap size bet, not a <¥10/ROE/ROA stock-picking edge; on the same 3 dates the large-cap end earns ~nothing. With u-6/u-7 the book reads as (micro-cap size exposure) × (one well-timed Feb-2024 entry). Consequences: (1) for integration this family joins the 规模因子 redundancy group with [[小市值]] / [[大小盘轮动]] / [[多因子ML]] (and 打板短线 涨停基因) — it is not orthogonal material for the 小盘 universe, and any merge must be judged as shared-edge, not diversification; (2) improve ideas that tune the price/ROE/ROA chain are low-prior — the chain is not where the return comes from (and may be unit-inert, pending u-5); (3) closes the selection-ranking question: no further ranking-direction ablations, the size sign is settled.',
  spawned: 'none',
  edgeRef: '规模因子',
});
console.log('ok', require('./queue.json').find(x => x.id === 'u-3').status);
