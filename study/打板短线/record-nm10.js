// Step-0 (new-members) finding for the 2026-11-05 re-invocation — six members, zero cost. Idempotent by qId.
//   node -e "require('./study/打板短线/record-nm10.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-11-05', type: 'probe',
  component_or_param: '六个新成员（2026-11-05 分配）。低位三连阳首板血统（51f7b3ab 同族）：353f0f75 优化14.1、b5218789 次日买第4版（两本指标逐位相同，非逐字节相同：同一代码体）、215cfc4a 接力第1版；724cf7e4 = 低位三连阳 + 基类 439385b4 首板高开腿合书（09:27 买）。连板血统（e1053979 / b518f737 同族）：b4089243 涨停先锋 v0.11（连板≥2 + 热门概念 + 09:25:45 竞价高开 2–8%）。涨停基因 子血统（c9e0451d 同族）：94c64f06 变种小狮子 + get_history_highlimit / get_start_point，周二 10:30 周频、1/4 月空仓',
  metric_delta: 'epoch 9 obj / sharpe / maxDD 与 2024 逐半年（零成本，曲线切片）：353f0f75 = b5218789 −0.3651 / −0.48 / 24.8，H1 −7.8 / H2 −4.3；215cfc4a −0.2994 / 0.01 / 34.1，H1 −17.1 / H2 +25.7；724cf7e4 0.3294 / 1.53 / 53.9，**H1 +200.1 / H2 −37.7**；b4089243 −0.2338 / 0.47 / 51.2，**H1 −28.5 / H2 +78.8**（Q4 +99）；94c64f06 **1.6092 / 5.32 / 17.9，H1 +44.2 / H2 +93.4**。对照：51f7b3ab −0.3933；e1053979 −0.0844（H1 −39 / H2 +117）；c9e0451d 1.2056（+38 / +76）、b3751277 1.3443',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9 归一化行与曲线切片）',
  finding: '三条血统各自复现已知读数。(1) 低位三连阳首板在 2024 四本全部 DQ（−0.39 / −0.37 / −0.37 / −0.30），没有上半年肥尾；只有把基类首板高开腿并进去的 724cf7e4 过闸，且带上了 H1 +200 / H2 −38 的基类形状——过闸与形状都来自那条腿。(2) 连板接力 b4089243 是 H1 负 / H2 正（−28.5 / +78.8），与 e1053979 同向：nm-2026-10-30 的「二板以上接力是下半年腿」第二本书独立印证（另一作者、另一套过滤）。(3) 涨停基因 子血统 94c64f06 obj 1.6092 是该子血统 epoch-9 新头名（> b3751277 1.3443 > c9e0451d 1.2056），两个半年都正（+44 / +93），无竞价入场——该子血统的形状与打板血统无关，再次说明它属于 小市值（jy-u-1 / jy-u-2：涨停基因 refuted 为独立 edge，规模 measured）',
  confidence: 'high（数字与形状直接；连板方向现由两本不同作者的书支持）',
  flags: 'zero-cost · step-0-exit · 低位三连阳-lineage-DQ-4-of-4 · 连板-H2-leg-2-books · 涨停基因-sublineage-new-best（94c64f06）· duplicate-metrics（353f0f75=b5218789）· R1-family',
  description: '数据：harness/normalize-train.tsv e9 行；data/series/<slug>__train__e9.json 切片；data/family-assignments.tsv 分配说明；cmp 两本同指标书',
  implication: '关闭对六本的单独研究：无新问题，家族 R=1 在 exit gate 终局拒绝，valReopened: 9 下先前 basis 仍绑定，不花 VAL。把「二板以上 = 下半年腿」从单书观察升为两书方向（仍非同代码消融，不改 edge status）。低位三连阳血统在 2024 无可研究的正结果（4/4 DQ），不为它开题。涨停基因 子血统的拆分建议（并入 小市值）更有理由：它现在有过闸、非竞价入场、无 R=1 机制的新头名 94c64f06——拆分是人工的 family: 改写，不在本循环权限内，记在 §4 请人决定',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
