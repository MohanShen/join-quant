// Recorder for q-e9-crowd-jan (STEP 0, zero backtests: a log read). Run once:
//   node -e "require('./study/小市值/record-crowd-jan.js')"
const rq = require('../../utils/research-queue');

const already = rq.findings('小市值').some(f => f.qId === 'q-e9-crowd-jan');
if (already) { console.log('q-e9-crowd-jan already recorded — nothing written'); return; }

rq.recordFinding('小市值', {
  qId: 'q-e9-crowd-jan',
  type: 'understand',
  component_or_param: '7ddb4855 抱团（成交额集中度）闸门对 2024-01 小盘踩踏的可见性 —— STEP 0 免费读日志、零回测。'
    + '度量 c_t = 前一交易日全市场 money 前 5% 占比（L384–449，09:15）；闸门 = MA20 > 0.43 且 c_t > 0.45 清仓并禁买（L113–114、L452–505、L186–188；L11 注释的 42/44 与代码不符）。'
    + '日志 = 7ddb4855 自身 epoch-9 TRAIN run，backtestId 4331b929d9dbf663efbcfb5ff3bec0be（取自存盘曲线），study/小市值/pagelog.js 16 页 / 1464 行 / 242 日，state=2；摘录 study/小市值/crowd-jan-log.txt',
  metric_delta: '0.0000 / 0.00 / 0.00（no backtest, log read）',
  window: 'TRAIN 2024（7ddb4855 epoch-9 log）',
  finding: 'BAND A（预注册 PRIMARY），完整性控制全过。控制：(a) 241 个 [集中度]「当前」日值 + 01-02 由 01-03 行的单点均值反推（36.3%）= 242，0 次取数失败；'
    + '(b)「[抱团风控] 历史数据不足」恰 19 行、01-02..01-26（当前 1..19），01-29 历史达 20 后停止，与 gatekeeper 的预热盲区推算逐日吻合 ⇒ 结果是真的，不是被收割的日志。'
    + 'PRIMARY：01-02..02-07 窗口 c_t 从未 > 0.45，窗口最大 40.3%（01-22），差阈值 4.7pp ⇒ A。'
    + 'SECONDARY：01-03..01-16 均值 35.72%（含反推的 01-02 为 35.77%）= 2024 全年 242 个日值的第 9.1 百分位（≤ 50 ⇒ 踩踏前没有升高）；一月均值 36.8%、二月 35.6%，全年中位 39.1%（最大 46.6% 07-17，最小 31.1% 02-19）。'
    + 'TERTIARY：全年 0 行触发 / 已卖出 / 卖出失败 / 风险解除 —— 闸门 2024 年从未触发；MA20 峰值 42.62%（约 08-02），从未越 43%；c_t > 0.45 只 3 天，全在七月（07-17 46.6 / 07-18 45.5 / 07-22 45.5），MA20 均 < 43% 故未触发。'
    + '01-23..01-26 的平台是本书个股 9% 止损（01-22 卖 3 只、01-23 卖 2 只），不是闸门（那时仍在预热）。',
  confidence: 'high',
  flags: 'regime-specific（n=1 有日期的踩踏事件，TRAIN 2024 单年；阈值由 2026-06-19 发帖的作者带着 2024–25 的知识选出，只有 PRIMARY/SECONDARY 的序列位置对阈值稳健）',
  description: '零回测、零文件改动的 STEP 0。STEP 1（把闸门预填充后移植到 02fdafaa-emptymonth）按预注册只在 B/C 时开，本条落 A，故不开、不入队。',
  implication: '关闭「抱团 / 成交额集中度闸门是 2024-01 踩踏保护的非日历路径」这一方向（本台）。稳健的一半不依赖作者的 0.43/0.45：一月小盘踩踏发生时全市场成交额集中度处于全年低位（第 9 百分位，窗口最高 40.3%），它不是一次大盘股抱团事件，「前 5% 成交额占比」在方向上就对它结构性失明，任何阈值都看不见。'
    + '⇒ champion 02fdafaa 的一月保护（−1.7321 的主体）仍是一个**没有找到市场可观测替代的日历效应**，g.pass_april 的事后性 caveat 照旧成立，3.0172 的强制引用规则不变；STEP 1 不开。'
    + '次要：闸门在 7ddb4855 自己的 2024 run 上是惰性的，其 0.29 不含任何闸门贡献，不得读作「带抱团风控的小市值」的测量。'
    + '重开条件必须是不同的东西、不是同一度量换阈值：(i) 量另一端的拥挤 —— 小盘 / 微盘在全市场成交额中的占比，或微盘指数的宽度 / 回撤信号；(ii) 一个本度量真正会移动的窗口。'
    + '免费线索（不是结论、不入队）：新成员 9cd43943 的 SW1 宽度「搅屎棍」闸门曲线自 2024-01-11 平到 03-06（一月 −0.17%、二月 0.00%），与该闸门在一月清仓相符，但日志未读、且它错过了整个二月反弹；若重开先读它的日志（零回测），并仍受 §4 2026-10-28「本台不排市场级止损 / 防踩踏实验」规则约束。',
  spawned: 'none',
  edgeRef: '',
});
console.log('recorded q-e9-crowd-jan');
