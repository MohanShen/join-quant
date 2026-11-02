// One-shot family-page update for lcfh-dxpit-val-e9 (family-recorder, 2026-11-01). Idempotent guard.
const fs = require('fs');
const path = require('path');
const p = path.join(__dirname, '../../wiki/families/蓝筹分红持续性.md');
let t = fs.readFileSync(p, 'utf8');
if (t.includes('| lcfh-dxpit-val-e9 候选 VAL 2025 |')) { console.log('already applied'); process.exit(0); }
function rep(a, b) { if (!t.includes(a)) throw new Error('missing: ' + a.slice(0, 80)); t = t.replace(a, b); }

// edge 股息率 evidence (append)
rep('不涉及股息 vs 行业（补位者同为银行）"',
  '不涉及股息 vs 行业（补位者同为银行） ‖ **2026-11-01 VAL 2025（lcfh-dxpit-val-e9，e9）——状态不动（measured），但范围收窄为 2024**：VAL 跑的是候选书 dxpit，不是本 claim 的 test（排序反转未在 2025 重跑，再跑会被 val-budget 拒绝）。候选 5.36 / sharpe 0.09 / maxDD 14.61 / obj −0.0923 → 闸门 FAIL（TRAIN 0.2630 / 2.02），跑输沪深300 **12.3pp**（+17.66），亏损全在 1–4 月。帖子发布于 2026-06-19，2025 在作者样本内，仍失败 → 无事后性可解释。⚠⚠ **本条只能读作「2024 年合格池内高股息端胜低股息端」，不是可前推的 edge**；与 [[银行股轮动]] VAL 0.69、[[红利低频]] OOS −0.51 同形：本台上的股息书拟合 2024、不延续。curve study_蓝筹分红持续性_variants_dxpit__val__e9"');
// edge 分红持续性 evidence (append)
rep('级联承担约半效应的读法得到加强"',
  '级联承担约半效应的读法得到加强 ‖ **2026-11-01 VAL 2025（lcfh-dxpit-val-e9，e9）——状态不动（measured），范围收窄为 2024**：VAL 未重跑本 test（删门槛+级联）；候选 dxpit（门槛+级联完整）2025 sharpe 0.09 / obj −0.0923 → FAIL，跑输沪深300 12.3pp，即持续性门槛+级联没有让书避开红利落后的一年。⚠⚠ 上面全部证据均为 2024 单年测量，**不得**当作前推有效的 edge 引用；「放宽门槛会吃亏」是 2024 内的比较，2025 的同比未测"');
// scope -> product expId
rep('realizabilityScope: "study/蓝筹分红持续性/variants/dxpit.py"', 'realizabilityScope: "lcfh-dxpit-val-e9"');
rep('realizabilityScopeBasis: "分数测于 dxpit',
  'realizabilityScopeBasis: "2026-11-01 VAL 后已改为产品 expId lcfh-dxpit-val-e9：validated_strategies/lcfh-dxpit-val-e9.py 头部之后的正文与 variants/dxpit.py 逐字节相同（sha256 7846fdbb…，归档时核验），故 liq-1 的分数原样适用。原注：分数测于 dxpit');
rep('updatedAt: 2026-11-01\n---', 'updatedAt: 2026-11-01\n---');

// §1 heading
rep('**为什么可能有效（未测）**：高股息 + 盈利（pe>0）+ 分红可持续的大盘股，即 A 股的「红利」风格；2024 正是红利/中特估的大年。',
  '**为什么可能有效（注册时的读码假设；已测，见 §2 / `edge:`）**：高股息 + 盈利（pe>0）+ 分红可持续的大盘股，即 A 股的「红利」风格；2024 正是红利/中特估的大年。**2026-11-01 测量结果**：TRAIN 2024 上排序（u-e9-dxinv，Δsharpe −1.10）与持续性门槛+级联（u-e9-dxpers Δsharpe −1.81；i-1-gxlonly 显示约半在级联）均 CONFIRM，约 3/4 水平来自合格池风格篮子本身（u-e9-dxew）；但候选 dxpit 在 **VAL 2025 FAIL**（sharpe 0.09，跑输沪深300 12.3pp），所以这些都是 **2024 范围**的读数，不是可前推的 edge。');
// registration note
rep('因此本族在 `/run-family` 的 exit gate 上是 blocked——那是正确状态，不是待办。',
  '因此本族在 `/run-family` 的 exit gate 上是 blocked——那是正确状态，不是待办。此段描述的是注册时状态；**截至 2026-11-01 已过时**：两条 edge 已 measured（TRAIN 2024），realizability 2（liq-1，scope = 产品 lcfh-dxpit-val-e9），**VAL 已花在 dxpit 上并 FAIL（sharpe 0.09 < 1.0），本族 epoch 9 无候选**——只有新成员或新台能重开，见 §4 末尾。');

// §2 row
const liqRow = t.split('\n').find(l => l.startsWith('| liq-1 可成交性地板'));
rep(liqRow, liqRow + '\n| lcfh-dxpit-val-e9 候选 VAL 2025 | understand | `variants/dxpit.py` 原样跑 VAL 2025-01-01..2025-12-31（runId lcfh-dxpit-val-e9，algorithmId 5d2e296d…）；本族 epoch 9 唯一一次 VAL；**Δ 为 VAL 相对同书 TRAIN** | research-lcfh-dxpit-val-e9 (e9) | −0.3553 | −1.93 | 0 | rejected | **VAL FAIL**：5.36 / sharpe 0.09 / maxDD 14.61 / obj −0.0923（闸门 1.0）；沪深300 +17.66 → 跑输 12.3pp，beta 0.48；亏损全在 1–4 月（谷底 04-07）。maxDD 14.61 为 JQ stats 原值（自初始资金起算，首日 −3.06%），非抓取伪影——与 TRAIN 的 14.61 相同是巧合；首点起算为 12.48 / obj −0.0710。帖子 2026-06-19 发布，2025 在作者样本内仍失败。已归档 `validated_strategies/lcfh-dxpit-val-e9.py`（gate_val: fail）。**本族 epoch 9 无候选，VAL 已用** |');

// §4 append before §5
rep('\n## 5. 沿革 (provenance)', [
  '',
  '- **[2026-11-01 lcfh-dxpit-val-e9 已答 → 已关：本台] VAL**：VAL 2025 花在 dxpit 上并 FAIL（sharpe 0.09 / obj −0.0923，跑输沪深300 12.3pp），已归档 `validated_strategies/lcfh-dxpit-val-e9.py`（gate_val: fail）。**本族 epoch 9 无候选，一次 VAL 已用**；不得对任何变体（含 dxew 篮子、i-x 改进）再跑 VAL，不得设 JQ_ALLOW_REVAL；不要为「再找一个能过 VAL 的候选」开 improve 轮——那是在 VAL 上做选择。重开条件：新成员（可能改变候选）或新台。',
  '- **[已关：moot] liq-2 容量点 2e8**：只为整合与 dxpit/dxew 之选而设，两者都因 VAL 失败而无意义 → queue 中 dropped。',
  '- **[解读约束] 两条 edge 为 2024 范围**：股息率、分红持续性 的 test 都只在 TRAIN 2024 跑过，VAL 未重跑 test。候选在作者样本内的 2025 仍失败，所以 TRAIN 上的 Δ 只说明「2024 年合格池内谁胜谁」，不能作为本族或合并候选的前推依据。',
  '- **[跨族 / 证据汇总] 股息书在本台不延续**：[[银行股轮动]] VAL 0.69、[[红利低频]] OOS −0.51、本族 VAL 0.09——三本拟合 2024 的股息/红利书都没有延续到下一窗口。新注册的股息族在花 VAL 前应先说明其 edge 为何不是 2024 红利风格年的产物。',
  '- **[maxDD 口径]** VAL 的 14.61 与 TRAIN 相同到两位小数，被疑为抓取伪影；JQ stats 端点（免费重取）给 max_drawdown 0.14607、区间 2025-01-02→04-07，确认是真值。差异在口径：JQ 从初始资金起算，`component-scan.maxDrawdownPct` 从曲线首点起算（12.48）。首日即亏的书两者会分开；台账与闸门用 JQ 口径。',
  '- **[仍开放 / 低价值] 2025 的空仓规则与合格数**：VAL 日志里 n_qual 是否接近 10（空仓规则）未统计；VAL 已用，仅作读数，不得据此调参。',
  '',
  '## 5. 沿革 (provenance)',
].join('\n'));
rep('| 2026-10-31 | 注册。来源 `screen/qita/verdicts.json`，screener confidence medium。零实验。 |',
  '| 2026-10-31 | 注册。来源 `screen/qita/verdicts.json`，screener confidence medium。零实验。 |\n| 2026-11-01 | run-family 第 1 轮：9 次 TRAIN（dxla 前视探针 → dxpit 诚实基线；两条 edge measured；i-1/i-2 rejected；liq-1 R=2）+ 1 次 VAL（lcfh-dxpit-val-e9，sharpe 0.09，FAIL）。归档 `validated_strategies/lcfh-dxpit-val-e9.py`（gate_val: fail）。 |');

fs.writeFileSync(p, t);
console.log('page updated');
