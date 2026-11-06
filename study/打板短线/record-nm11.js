// Step-0 (new-members) finding for the 2026-11-06 re-invocation — three members, zero cost. Idempotent by qId.
//   node -e "require('./study/打板短线/record-nm11.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-11-06', type: 'probe',
  component_or_param: '三个新成员（git 90cd0a0）。92b3fdc7 年化300%秘密游资…：基类 439385b4 换标题重发，代码体逐字节相同（只有 4 行头注释不同）。a197e98c 小市值策略·绝对没有未来函数：涨停基因 子血统（变种小狮子 V2.2：get_history_highlimit(3*250) / get_start_point 逐字、最小 1000 只、周二 10:15 卖 / 10:30 买），本地改动是 08:30 的布林「韶华一致性」开关，清仓时暂停交易。209b6204 目前回测收益最高的三连阳首板：低位三连阳血统的重写调参版（流通市值 30–300 亿、09:27 买、11:25 / 13:30 / 14:55 卖）',
  metric_delta: 'epoch 9：92b3fdc7 obj 7.5458 / sharpe 11.46 / maxDD 44.38，与基类逐位相同，H1 +933.1 / H2 −13.0；a197e98c **1.7762 / 5.42 / 21.76**，H1 +36.8 / H2 +118.8（Q 62 / −16 / 61 / 36）；209b6204 −0.4600 / −0.51 / 29.18，DQ，H1 −21.6 / H2 +6.1。对照：子血统 94c64f06 1.6092、b3751277 1.3443、c9e0451d 1.2056；低位三连阳 51f7b3ab −0.39、353f0f75 −0.37、215cfc4a −0.30',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9 归一化行与曲线切片）',
  finding: '92b3fdc7 是基类的副本，指标逐位复现基类（同时证明本台对同一代码体在不同提交时间可重复）。209b6204 让低位三连阳血统在 2024 变成 5 本全 DQ——调参与重写都没救回来。a197e98c 是涨停基因 子血统第二次连续刷新头名（1.6092 → 1.7762），布林暂停开关之外与 94c64f06 同一代码体，形状同样是下半年更强、两个半年都正、周频非竞价入场——与本家族的打板形状无关',
  confidence: 'high（逐字节 diff、账本与曲线直接）',
  flags: 'zero-cost · step-0-exit · base-repost（92b3fdc7 = 439385b4）· 低位三连阳-DQ-5-of-5 · 涨停基因-sublineage-new-best（a197e98c）· R1-family',
  description: '数据：harness/normalize-train.tsv e9 行；data/series/<slug>__train__e9.json 切片；data/family-assignments.tsv 分配说明（git 90cd0a0，含与基类的 diff 结论与 Jaccard）',
  implication: '关闭对三本的单独研究：无新问题，家族 R=1 在 exit gate 终局拒绝，valReopened: 9 下先前 basis 仍绑定，不花 VAL。低位三连阳血统 2024 已 5/5 DQ，后续同血统新成员按副本处理即可。涨停基因 子血统已连续两次刷新、头名 1.78 且无 R=1 机制——§4 的拆分建议（并入 小市值）仍待人工；它留在本家族一天，就一天被本家族的 R=1 挡在 exit gate 外',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
