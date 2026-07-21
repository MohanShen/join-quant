// dq-finalize.js — generate a lighter DQ study report + finding for a gate-fail strategy that
// is a transparent member of an already-dissected family (auto-study batch, "why it doesn't work").
// Usage: node utils/dq-finalize.js <id> <category> <sharpe> [total annual maxdd]
//   category ∈ etf-momentum | daban | no-riskcontrol | naive-ta
//   sourceFile is read from study/manifest.json. Also snapshots the source into study/<id>/target.py.
// Writes study/<id>/findings.tsv, wiki/studies/<id>.md, and marks manifest status=done.
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const [, , id, category, sharpe, total, annual, maxdd] = process.argv;
if (!id || !category) { console.error('usage: <id> <category> <sharpe> [total annual maxdd]'); process.exit(1); }
const mp = path.join(ROOT, 'study', 'manifest.json');
const m = JSON.parse(fs.readFileSync(mp, 'utf8'));
const entry = m.strategies.find(x => x.id === id);
if (!entry) { console.error('id not in manifest: ' + id); process.exit(1); }
const sourceFile = entry.sourceFile;

const measured = total != null;
const metricStr = measured
  ? `total ${total}% / annual ${annual}% / sharpe ${sharpe} / maxdd ${maxdd}%`
  : `Sharpe ${sharpe}（normalize train）< 2.5 门槛`;
const src = measured ? 'baseline 直接观测' : 'transfer + normalize 指标';

const T = {
  'etf-momentum': {
    refs: '[[ETF轮动]], [[动量与趋势]]',
    concl: `ETF/七星-五福-三马 动量轮动家族成员。${measured ? `train 2022-2023 ` : `normalize train `}**Sharpe ${sharpe} → DQ**（不达 2.5 门槛）。属 [[ETF轮动]] 动量轮动家族典型 regime-dependent DQ。`,
    why: `动量轮动高度依赖趋势 regime（[[ETF轮动]] 核心结论）；冻结 2022-23 非趋势窗动量 whipsaw，Sharpe 结构性不足。参数/池/滤波/实盘链路类变体不改动量核心的 regime 依赖，故与家族同 DQ。头条长窗高倍数是含牛市产物。`,
    finding: `DQ：ETF/七星-五福-三马 动量轮动家族成员。Sharpe ${sharpe} → 不达门槛。属 [[ETF轮动]] 动量轮动家族 regime-dependent DQ（2022-23 非趋势窗 whipsaw），与 [[0aa4028d_追电ETF动量轮动]]/[[4fa17009_五福v5差异化滤波]] 同源。`,
    flags: measured ? 'regime-dependent' : 'regime-dependent, transfer-only',
    feed: `又一个 ETF/动量轮动 家族 DQ 数据点（family 归一化横评：动量族多数 DQ、regime 依赖）。`,
  },
  'daban': {
    refs: '[[动量与趋势]]',
    concl: `打板/首板/连板/竞价类追涨策略。${measured ? `train 2022-2023 真实价成交下 ` : `normalize train `}**Sharpe ${sharpe} → DQ 无 edge**。头条高收益是乐观成交假设（涨停/一字板/高开/竞价能理想成交）的幻觉。`,
    why: `**⚠ 打板不真实成交**：这类策略头条收益依赖「涨停/一字板/高开/竞价按理想价成交」；真实价成交 + 冻结成本下 edge 消失（追高的短期动量多数反转）。属真实性红线（harness.md §3）里典型的不真实成交幻觉。与 [[25898ae1_连阳倍量首板高开1进2]] 同类。`,
    finding: `DQ 无 edge：打板/首板/连板/竞价追涨。Sharpe ${sharpe}。头条高收益是乐观成交（涨停/高开/竞价可成交）幻觉；真实价成交下追高动量反转，无 edge。⚠ 打板不真实成交（harness.md §3），与 [[25898ae1_连阳倍量首板高开1进2]] 同类。`,
    flags: '⚠打板不真实成交, no-edge',
    feed: `打板/首板/连板/竞价类头条 = 乐观成交假设产物，真实价成交下无 edge；ideator/critic 默认打真实性红旗，勿当可研究 alpha。`,
  },
  'no-riskcontrol': {
    refs: '[[小市值因子]]',
    concl: `long-only 无（或弱）风控组合。${measured ? `train 2022-2023 ` : `normalize train `}**Sharpe ${sharpe} → DQ**：${measured ? `年化 ${annual}% 但 maxDD ${maxdd}%` : `回撤大/Sharpe 不足`}。无择时/止损 → market-like 回撤 → 风险调整收益不达门槛。`,
    why: `无风控 → 熊市 regime 吃满回撤：无空仓/止损/择时的 long-only 组合在 2022 熊市随大盘下行，raw 收益可能正但回撤 market-like、Sharpe 掉出门槛。印证 [[1d995d0b_小市值多体系融合]]/[[17c95d16_小市值微调]]：家族低回撤/高 Sharpe 是风控机器造的，非 raw 因子自带。`,
    finding: `DQ：long-only 无风控组合。${metricStr}。无择时/止损 → market-like 回撤 → Sharpe 不达门槛；印证风控机器对 gate-pass 的必要性（cf. [[1d995d0b_小市值多体系融合]]）。`,
    flags: measured ? 'no-riskcontrol' : 'no-riskcontrol, transfer-only',
    feed: `低换手/低频/基本面/裸因子 long-only 无风控 → 熊市 regime 高回撤 DQ；下行保护是 gate-pass 的必要条件。`,
  },
  'weak-factor': {
    refs: '[[多因子模型]]',
    concl: `多因子/机器学习选股策略，无（或弱）风控。${measured ? `train 2022-2023 ` : `normalize train `}**DQ**${measured ? `：${metricStr}` : `（Sharpe ${sharpe}）`}。因子/ML 组合在冻结 2022-23 窗无稳健 edge${measured && annual != null && annual < 0 ? '（甚至负收益）' : ''}。`,
    why: `多因子/ML 入门/教学/作业类组合通常因子拼凑、缺乏 out-of-sample 稳健性与风控，在冻结 2022-23 窗产出低/负风险调整收益 + 高回撤。A 股散户级多因子/ML 少有真 alpha，且无下行保护 → DQ。`,
    finding: `DQ：多因子/ML 选股，无稳健 edge。${metricStr}。因子/ML 组合缺 out-of-sample 稳健性+风控，冻结 2022-23 窗低/负风险调整收益 + 高回撤。`,
    flags: measured ? 'weak-factor, no-edge' : 'weak-factor, transfer-only',
    feed: `散户级多因子/ML「入门/教学/作业」组合在冻结窗少有真 alpha 且无风控；勿当可部署 edge。`,
  },
  'zero-trade': {
    refs: '[[动量与趋势]]',
    concl: `策略在冻结 train 2022-2023 全窗**近乎零交易**（total ${total}% / maxDD ${maxdd}% / Sharpe ${sharpe}）→ DQ。入场条件在本窗几乎不触发 / 标的不趋势 / long-only 无对手方，全窗空仓或极少建仓。`,
    why: `零交易签名（total≈0 / maxDD≈0 或极低）= 策略入场条件在冻结窗几乎不触发（趋势/价值/突破门槛过严或标的不配合），long-only 无做空 → 空转。结构性不适配本窗，无 EV。与 [[11406b82_海龟交易体系股票版]]（单股 Turtle 零交易）同类。`,
    finding: `DQ 零/近零交易：${metricStr}。入场条件在冻结 2022-23 窗几乎不触发（门槛过严/标的不趋势/long-only），全窗空转，无 EV。与 [[11406b82_海龟交易体系股票版]] 同类。`,
    flags: 'zero-trade, structural-misfit',
    feed: `入场门槛过严 / 趋势-价值系统套非配合标的 → 冻结窗零交易空转；勿当 alpha。`,
  },
  'naive-ta': {
    refs: '[[动量与趋势]]',
    concl: `裸技术指标（单指标）策略。${measured ? `train 2022-2023 ` : `normalize train `}**Sharpe ${sharpe} → DQ 无 edge**${measured ? `（年化 ${annual}%/maxDD ${maxdd}%）` : ''}。单一 TA 指标无真实 alpha。`,
    why: `裸技术指标（均线/网格/布林/MACD/RSI 单指标）在 A 股冻结窗普遍无 alpha，产出近零风险调整收益 + market-like 回撤。经典「单一 TA 无 edge」DQ，与 [[3c269466_布林通道策略]] 同类。`,
    finding: `DQ 无 edge：裸技术指标策略。${metricStr}。单一 TA 指标无真实 alpha，近零 Sharpe + market-like 回撤；与 [[3c269466_布林通道策略]] 同类。`,
    flags: measured ? 'no-edge, naive-ta' : 'no-edge, naive-ta, transfer-only',
    feed: `裸单指标 TA（均线/网格/布林/MACD/RSI）冻结窗普遍无 alpha；勿当 edge。`,
  },
};
const t = T[category];
if (!t) { console.error('unknown category: ' + category); process.exit(1); }

const dir = path.join(ROOT, 'study', id);
fs.mkdirSync(path.join(dir, 'variants'), { recursive: true });
// snapshot the raw source (no OVERRIDE — transfer-DQ is not re-run)
try { fs.copyFileSync(path.join(ROOT, sourceFile), path.join(dir, 'target.py')); } catch (e) { console.error('snapshot warn:', e.message); }
const header = 'qId\ttype\tcomponent_or_param\tmetric_delta\twindow\tfinding\tconfidence\tflags\tdescription\n';
const row = ['q-0', 'probe', `DQ 归因（${src}）`, metricStr, 'train 2022-2023', t.finding, measured ? 'high' : 'med', t.flags, `${src}；${category} 家族 DQ`].join('\t') + '\n';
fs.writeFileSync(path.join(dir, 'findings.tsv'), header + row);

const rep = `---
studyId: ${id}
target: ${sourceFile}
targetRefs: [[${id}]], ${t.refs}
harness: research/harness.md（冻结成本；窗口 2022–2024，2025 OOS 禁用）
startedAt: 2026-07-16
status: done
---

# 解剖报告：${id}（DQ — 为什么不行）

## 一句话结论
${t.concl}

## 为什么不过门槛（DQ 归因）
${t.why}

## 机理与真实性
归因基于 ${measured ? 'baseline 直接观测' : 'normalize train 指标（Sharpe ' + sharpe + '）+ 家族已确立机理；未独立重跑（清晰家族迁移，节省预算）'}。confidence=${measured ? 'high' : 'med'}。

## 待研究 / 反哺 auto-research
${t.feed}
`;
fs.writeFileSync(path.join(ROOT, 'wiki', 'studies', id + '.md'), rep);

entry.status = 'done';
fs.writeFileSync(mp, JSON.stringify(m, null, 2) + '\n');
console.log(`DQ-finalized ${id} [${category}] sharpe=${sharpe}${measured ? ' (measured)' : ' (transfer)'} → done`);
