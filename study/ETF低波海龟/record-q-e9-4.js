// One-shot recorder input for q-e9-4 (PIT pool) + q-e9-4s (static 4-name arm, orchestrator error), 2026-11-01.
// Run once; recordFinding appends.
const rq = require('../../utils/research-queue');
const F = 'ETF低波海龟';
const have = new Set(rq.findings(F).map(f => f.qId));
if (have.has('q-e9-4') || have.has('q-e9-4s')) { console.error('already recorded — refusing to append twice'); process.exit(2); }

rq.recordFinding(F, {
  qId: 'q-e9-4s', type: 'understand',
  component_or_param: '⚠ 设计偏离（orchestrator 错误，queue design 指定的是点时池）：14 只手选池 → 静态 4 只宽基（510300/510500/159915/159949，取自 ETF动量 q-3），分别跑在 base 与 q-e9-3 上',
  metric_delta: 'base 臂 vs base Δobj +0.1714 / Δsharpe +0.62 / ΔmaxDD −0.58；q3 臂 vs q-e9-3 Δobj +0.2021 / Δsharpe +0.63 / ΔmaxDD −1.63',
  window: 'train',
  finding: 'TRAIN 2024（242 点，曲线末值 39.07 / 39.40 经 orchestrator 校验）：base 臂 total 39.07 / sharpe 1.84 / maxDD 12.38 / obj 0.2669；q3 臂 39.40 / 1.87 / 12.15 / 0.2725。两臂路径相同：01→10-08 一直持有 沪深300（510300），其余三只从未被选中；风险池中位波动在行情中峰值 58.74% > 0.40，国债避险腿放行 61 天，10-08（行情顶部）切换至 国债ETF 并持有至年末。09-24..10-08 两周 +42%，其余天 −2.1% / −1.3%（rest sharpe −0.16 / −0.07）。',
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific (2024 单窗口；9 月刺激行情); design-deviation (orchestrator 跑错池：静态 4 只而非点时池); 非排序测试 (4 只高度相关宽基)',
  description: 'variants study/ETF低波海龟/variants/q-e9-4-base.py + q-e9-4-q3.py（builder study/ETF低波海龟/build-q-e9-4.js）；日志 study/ETF低波海龟/logs/q-e9-4-{base,q3}-train.log；曲线 data/series/study_ETF低波海龟_variants_q-e9-4-{base,q3}__train__e9.json。不是 q-e9-4 的设计，不回答池分句。',
  implication: '(1) 不得作为排序证据或池后见证据引用：4 只相关宽基上的低波排序退化为「一直持有 300」，收益 = 一个两周的 300 beta + 一次波动触发的退出，objective 0.27 是窄池的水平事件，不是候选——不得据此开 improve（「换成宽基池」是 off-mechanism 的水平追逐）。(2) ⚠ 改写 q-e9-1 的读法：国债避险腿并非一般性惰性——它只在手选 14 只池上惰性（中位波动从未 >0.40）；在窄权益池上中位波动 58.74% 触发它，作为行情尖峰后的去风险退出恰在 10-08 顶部离场。⇒ 避险腿重新成为一个 understand 议题（何种池构成使其触发、触发时是否系统性地在尖峰后离场），不是 improve 旋钮；§4 中「国债腿 TRAIN 惰性」须限定为「在 14 只池上」。(3) 设计偏离本身：q-e9-4 的门控问题未由本次回答，须由点时池跑（见 q-e9-4）。',
  spawned: 'none (safe-leg reopened as §4 understand gap, not queued)',
  edgeRef: '低波动异象',
});

rq.recordFinding(F, {
  qId: 'q-e9-4', type: 'understand',
  component_or_param: '池后见测试：手选 14 只风险池 → 逐日点时 A 股权益 ETF 池（get_all_securities etf、上市 ≥250 日、20 日成交额中位数 ≥2e7、权益类名称正则 + 511/513/518 前缀排除 + 手工排除 159980/159831；152–294 只），跑在 q-e9-3（叠加关闭）上，其余逐字不动',
  metric_delta: 'PIT vs q-e9-3 Δobj +0.0340 / Δsharpe −0.10 / ΔmaxDD −4.44；行情外 +3.80% vs +12.82%（rest sharpe 0.38 vs 1.04）',
  window: 'train',
  finding: 'TRAIN 2024（242 点，曲线末值 19.78 经 orchestrator 校验）：PIT 池 total 19.78 / sharpe 1.14 / maxDD 9.34 / obj 0.1044；母本 q-e9-3 20.82 / 1.24 / 13.78 / 0.0704。09-24..10-08 两周 +15.39%（q-e9-3 +7.09%），其余天 +3.80%（rest sharpe 0.38；q-e9-3 +12.82% / 1.04）。持仓链 100红利 → 银行 → 红利50 → 红利300（被选中的权益名字全部是红利/银行），10-10..12-31 国债ETF（避险腿放行 59 天），共 5 次换仓。⚠ 第一次运行泄漏了非权益名字（有色期货 159980、黄金类、纳斯达克），该次结果作废并被覆盖，日志留作 logs/q-e9-4-pit-run1-leaky-train.log；手工排除 159980/159831 即源于此。⚠ 池宽度 14 → 152–294 同时改变（与 ETF动量 q-e9-5 同类混淆）。',
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific (2024 单窗口；2024 红利/银行本身是赢家); 宽度混淆 (14 → 152–294); 首跑泄漏非权益名字已作废重跑',
  description: 'variant study/ETF低波海龟/variants/q-e9-4-pit.py（builder study/ETF低波海龟/build-q-e9-4-pit.js，断言 diff 只落在池构建 + 观察用 HOLD 日志）；日志 study/ETF低波海龟/logs/q-e9-4-pit-train.log（作废首跑 q-e9-4-pit-run1-leaky-train.log）；曲线 data/series/study_ETF低波海龟_variants_q-e9-4-pit__train__e9.json；对照 q-e9-3 变体。预声明规则：sharpe ≥ 1.0 且 obj ≥ 母本 ~60% ⇒ 排序不由名单承载。结果 1.14 ≥ 1.0、0.1044 ≥ 0.0704×0.6 ⇒ PASS。跑的就是 edge 低波动异象 test 的池分句（与 q-e9-2/q-e9-6 合起来 test 完整）。',
  implication: 'edge 低波动异象 升为 measured，但作用域写死：(1) 在事前可定义的权益池上，最低波排序 = 红利/银行 ETF，TRAIN 2024 sharpe 1.14 仍过 1.0 ⇒ 名单不承载排序本身，「ETF动量 q-3 的 −0.27」形态未出现，池后见不是本族的致命解释。(2) 但行情外收益 12.82% → 3.80%：手选池的行情外避损主要来自黄金（q-e9-1：黄金 ≈ 全年 +15–17%），一个权益池排除的跨资产名字 ⇒ 本族在 TRAIN 2024 的诚实机制是「持有最平静的名字，而这一年最平静的是黄金或红利/银行」；手选名单经黄金贡献约 +9pp 行情外收益。(3) 2024 年红利/银行本身就是赢家 ⇒ 「低波异象」与「2024 防御性行情」在 TRAIN 上不可分离，measured 只覆盖「排序不由名单承载」，不覆盖「异象跨年成立」。(4) 任何 VAL 读数必须拆为 行情 / 非行情 两段，并分开报池效应（黄金在/不在）；以 VAL 的水平数字确认 edge 不被接受。(5) 黄金的贡献目前是由持仓归因推出的，不是消融测得 ⇒ 排入 q-e9-7（手选 14 只去掉 518880，跑在 q-e9-3 上，一次 TRAIN）把 +9pp 变成测量，它决定 VAL 时池效应该如何拆读。',
  spawned: 'q-e9-7',
  edgeRef: '低波动异象',
});

const q = rq.load(F);
for (const e of q) {
  if (e.id === 'q-e9-4') {
    e.status = 'done';
    e.result = 'PIT 权益池（152–294 只）on q-e9-3：19.78 / sh 1.14 / maxDD 9.34 / obj 0.1044 vs q-e9-3 20.82 / 1.24 / 13.78 / 0.0704；行情两周 +15.39% / 其余 +3.80%（rest sh 0.38）vs +7.09% / +12.82% / 1.04。持仓全为红利/银行，10-10 起国债。预声明规则 PASS ⇒ 低波动异象 measured（作用域：排序不由名单承载；行情外避损主要是黄金；与 2024 防御行情不可分）。⚠ 静态 4 只臂 q-e9-4s 为 orchestrator 设计偏离，单独记录';
  }
}
rq.save(F, q);

rq.add(F, {
  id: 'q-e9-7', kind: 'understand',
  title: '黄金在/不在：手选 14 只池去掉 518880 黄金ETF，跑在 q-e9-3 上，其余逐字不动',
  hypothesis: 'q-e9-4 推论：手选池的行情外避损（q-e9-3 其余天 +12.82%）主要来自黄金。若成立，去掉黄金后行情外收益落到 PIT 池附近（≈ +3.8%），全年 sharpe 降向 ~1.1。证伪：行情外收益仍 ≥ ~+10% ⇒ 手选池的行情外优势不是黄金，而是名单中其他名字，需另找',
  why: '1 次 TRAIN。把 q-e9-4 中由持仓归因推出的「黄金 ≈ +9pp 行情外」变成测量；它决定 VAL 读数时池效应如何拆读（VAL 2025 黄金同样大涨，若黄金承载池效应，VAL 的强数字是黄金而不是低波排序）。不是 improve：不会据此改池',
  design: '从 variants/q-e9-3.py 出发，仅删除 g.all_risk_etfs 中 "518880.XSHG" 一行（断言 diff 恰为该行）；--window train；报告 09-24..10-08 与其余天的收益/rest sharpe、持仓链，与 q-e9-3 和 q-e9-4 对照',
  from: ['q-e9-4', 'q-e9-1', 'q-e9-3'],
  edgeRef: '低波动异象',
  rank: 5,
});
console.log(rq.load(F).map(e => e.id + ':' + e.status).join(' '));
