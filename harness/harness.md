# harness/harness.md — 冻结评测台常量（权威）

本文件是**冻结评测台**的唯一权威定义（类比 Karpathy `autoenhance` 的 `prepare.py`）。
`docs/enhance-schema.md` §3 引用本文件；如有出入，**以本文件为准**。

> **纪元（epoch）**：本文件全部常量一经设定即冻结。任何改动 = 新纪元：
> 递增下方 `epoch`、记 `wiki/log.md` 一行 `experiment | harness epoch <n> ...`，
> 此前所有实验结果就此封版，不再与新纪元横比。
> agent **只读本文件，绝不修改**；也绝不在策略代码里改动被本文件冻结的项。

---

> ⚠ **数值的唯一权威是 `harness/config/epoch-<n>.json`**（当前生效者由 `harness/config/active.json`
> 指定）。本文件解释**意图**，JSON 存**数值**，代码经 `utils/harness-config.js` 读取——不再有第二处硬编码。
> 换纪元 = 新写一个 `epoch-<n+1>.json` + 改 `active.json`；旧纪元文件保留，使历史结果始终挂在产生它的规则上。
> `node utils/harness-config.js` 打印当前生效配置；`--verify` 校验 Python 字面量（模板/OVERRIDE 在
> 聚宽服务器上执行，无法读 JSON）仍与配置一致。

## Epoch

- **epoch**: 8 ｜ **setAt**: 2026-10-16 ｜ ⚠ 权威在 `harness/config/active.json` + `epoch-<n>.json`，
  本节只是导读；**代码一律读 `node utils/harness-config.js`，不要抄这里的数字**。
- **epoch 8**（只改计分）：整合 BAR 由 epoch 7 的「最差年 objective maximin」改为
  **逐年 sharpe 支配**（每个 TRAIN 自然年都要赢过最佳 parent champion），见 §4.1。
- **epoch 7**（只改计分）：整合门槛 2.0 → 1.5；BAR 由汇总 objective 改为逐年。**已被 epoch 8 取代**。
- **epoch 6**：钉死**股票**撮合成本（`set_order_cost(..., type='stock')`）——测量台改变，pre-6 行不可比。
- **epoch 5**（只改计分，台与 epoch 4 完全相同）。两点：
  ①**门槛 2.5 → 1.5**；②**未过闸也保留分数**。理由：124 个实测策略的夏普中位数是 **1.02**，2.5 约在
  **88 百分位**，且在 2.5 下 **14 个家族里有 5 个全员 DQ**（三进兵/红利低频/网格/趋势技术/套利），
  objective 全为 −inf、**不承载任何比较信息**——红利低频页自己写着「永不报 Δobjective」。把 2.5 换算成
  收益门槛更直白：在该家族实测波动与 JQ 平的 4% 无风险利率下，2.5 要求年化 ≥ **37.34%**，它做到 23.41%，
  页面结论是「不是没有 edge，是 edge 装不进闸」。另外 epoch 4 钉死执行项后同一策略夏普 18.16→11.15，
  固定的 2.5 已在无人决定的情况下变得更严。
  **闸门自此是标签不是橡皮擦**：分数照记，`gate` 列另记 pass/fail。**因 score = 年化 − 最大回撤 是账本
  已存列的纯函数，全部历史行已就地重算，未花一分钟回测**（103 行重算，16 行由 fail 转 pass）。
  **分阶段门槛（epoch 7 起全部为 1.5）**：整合回合曾用 2.0，但在 60 行 epoch-6 实测上
  **它从未对任何可能胜出的候选起作用**——Spearman ρ(objective, sharpe) = **0.9836**（两个标准从不分歧）、
  objective 前 16 名**无一人**被任一门槛拦下、1.5–2.0 之间只有 **3** 行且 objective 仅 0.2139–0.2970。
  整合的真实门槛改为**逐年比较**，见 §4.1。
  （epoch 4：钉死 `order_volume_ratio=0.05`/基金费率/`avoid_future_data`；epoch 3：VAL 延至 2024–2025。）
  团队架构见 `enhance/program.md`。

---

## 1. 回测窗口（period split）——严格协议

由 JoinQuant Pipeline 2（`utils/strategy-post-backtest.js`）的回测区间参数实现（平台级，非策略代码）。

| 窗口 | 起 | 止 | 用途 | 谁能跑 / 何时跑 |
|---|---|---|---|---|
| **TRAIN** | 2022-01-01 | 2023-12-31 | **迭代与选择**：所有变异/调参在此搜索，选择指标 = `objective(TRAIN)` | Agent 3，迭代中（Type-1）可无限次 |
| **VAL** | 2024-01-01 | **2025-12-31** | **定稿确认**：仅对 Agent 1 已**定稿**的策略跑一次做泛化检验 | Agent 3，仅 Type-2（定稿）时 |
| ~~OOS~~ | **2026-01-01** | 今 | **保留样本外**——用户私有最终检验 | **任何 agent 禁用**（代码硬阻断） |

- **迭代只看 TRAIN**：Agent 1 在 TRAIN 上搜索，追求 TRAIN 上的正向改进并自行判断定稿。**绝不**在迭代中看 VAL。
- **VAL 仅定稿一次**：策略定稿后跑一次 VAL，结果由 Agent 4 记账，作泛化参考，**不回头驱动选择**（否则 VAL 泄漏）。
- **2026→今 = 禁区**：`strategy-post-backtest.js` 对任何触及 `>= 2026-01-01` 的窗口**抛错拒跑**（`OOS-BLOCKED`）。这是代码级保证，不是口头约定。只有用户为私有最终检验可设 `JQ_ALLOW_OOS=1` 手动越过——agent 永远不设。
- ⚠ **区间特性**（读结果时牢记）：TRAIN 覆盖 2022 熊 + 2023 震荡，**无明显牛市**；VAL 为 2024–2025 两年（2024 含 2 月微盘踩踏，2025 为另一 regime）——故 VAL 只作定稿泛化参考，不作逐轮选择。

---

## 2. 回测配置（冻结）

**平台级**（由 Pipeline 2 的 `newStrategy` URL 参数设定，不在策略代码里）：

| 项 | 值 |
|---|---|
| 基础资金 | **￥1,000,000** |
| 频率 | 每天（日线） |
| 复权/真实价 | `use_real_price=True` |
| **成交量占比上限** | **`order_volume_ratio=0.05`**（epoch 4 新增） |
| **未来函数防护** | **`avoid_future_data=True`**（epoch 4 新增） |

**代码级**（在策略 `initialize` 的「勿改区块」里设定，见 `strategy_template.py`；agent 不得改动这些行）：

| 项 | 值 | JQ 写法 |
|---|---|---|
| 基准 | 沪深300 | `set_benchmark('000300.XSHG')` |
| 手续费 | 买万3 / 卖万3+印花税千1 / 每笔最低5元 | `set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))` |
| **滑点** | **0（零滑点）** | `set_slippage(FixedSlippage(0))` |
| **基金费率** | 买卖各万3 / 无印花税 / 每笔最低5元 | `set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')`（epoch 4 新增） |

> **为什么 epoch 4 要钉这三项**：
> - `order_volume_ratio` 不设时，一笔单可以吃掉成交量中不合理的比例——这正是本库最高分两个策略的
>   来源机制（[[ETF溢价]] study-q-1：抬高成交量下界后 sharpe 8.44→1.10，边缘**由最薄的标的构造**）。
>   215 个策略里只有 **9 个**自己设过它。
> - `set_commission` **管不到基金**：170 个策略自设 `set_order_cost(type='fund')`，所以此前每个 ETF
>   策略跑的都是作者的费率而不是台子的。
> - `avoid_future_data` 只有 **144/215** 个策略设了，等于 71 个在没有未来函数防护下跑。
>
> ⚠⚠ **零滑点的后果（务必知晓）**：这是本纪元刻意的选择——与聚宽社区策略、及 `wiki/` 已记录的绩效保持**可比**。
> 代价：**换手成本被完全忽略**，高换手 / 微盘 / 打板类策略的 `objective` 会被**系统性高估**。
> 因此本纪元里：
> - `objective` 的「− 最大回撤」项 与 wiki 的 **⚠ 不真实成交红线**（§3）是仅有的两道防线；
> - 高换手策略的 keep 结论必须在实验页标注「零滑点高估」，不得当作可实现收益；
> - 若后续要更诚实地惩罚换手，改 `set_slippage`（如 `PriceRelatedSlippage(0.002)`）→ 即新纪元。
> 基准 `000300` 仅影响 alpha/beta 显示，**不影响 `objective`**（夏普对基准无关）；固定它只为跨实验一致。

---

## 3. 标的真实性过滤（强制，所有策略必须遵守）

零滑点下真实性更依赖这些过滤。`strategy_template.py` 已内置，agent 变异时**不得移除**：

- **剔除 ST/\*ST**：`get_current_data()[s].is_st` 为真者不选。
- **剔除停牌**：`get_current_data()[s].paused` 为真者不选。
- **剔除次新**：上市不足 **250 个自然日** 的不选。
- **涨停不买 / 跌停不卖**：买入前若 `last_price >= high_limit` 跳过该买单；清仓时若 `last_price <= low_limit` 当日不强卖。
- **继承 wiki ⚠ 约定**：打板/涨停/龙虎榜等成交假设不真实的范式，回测收益仅作参考，实验页必标 ⚠。

---

## 4. 目标函数与门槛（冻结）——本项目的 `evaluate_bpb`

单标量，越大越好。在窗口 `w` 上（`sharpe / annualReturn / maxDrawdown` 取自 JQ 回测结果）：

```
score(w)     = annualReturn(w) - maxDrawdown(w)        # 均为小数，如 0.35 = 35%
objective(w) = score(w)                                # epoch 5：永远记分
gate(w)      = ( sharpe(w) >= 1.5 )                    # 标签，不再抹掉分数
# 分阶段标准（epoch 7 起统一）：
#   normalize / study / enhance / validate / type integration : sharpe >= 1.5
# 整合回合另有 BAR（不是闸门），见 §4.1：
#   bar = perYearSharpe    # epoch 8：每个 TRAIN 自然年的 sharpe 都要赢过最佳 parent champion
```

- **选择指标 = `objective(TRAIN)`**：Agent 1 迭代中的 keep/继续/定稿全看它。一个变异算「正向改进」当且仅当 `gate(TRAIN)` 为真且 `objective(TRAIN) > 当前定稿中最优`。
- **`objective(VAL)`** 仅在策略**定稿后**算一次，作泛化确认，由 Agent 4 记账；**不参与迭代选择**。
- **2025/OOS 永不计算**——被代码硬阻断。
- 门槛与公式形式均为**冻结常量**，改动即新纪元；数值见 `harness/config/epoch-<n>.json`。

> **annualReturn 的来源**：JoinQuant 回测列表（buildList）只给**总收益**（策略收益），不直接给年化。
> 故 `annualReturn` 由执行器 `strategy-post-backtest.js` 按**实际回测区间天数**从总收益年化：
> `annualReturn = (1 + 总收益)^(365/天数) − 1`。
> `sharpe`、`maxDrawdown` 直接取自 JQ 回测结果。三者与区间一并写入机器可读的 `SUMMARY` 行（见 §5）。

---

### 4.1 整合回合的 BAR（epoch 8 起冻结；epoch 7 的 bar 已作废）

闸门（`sharpe >= 1.5`）回答「这个结果可用吗」。**BAR 回答「它赢过被整合的家族了吗」**，这才是整合
回合真正的判据，由 `objective.integrateBar` 声明、`harness.integrateBar()` 读取。

**basis = `perYearSharpe`（epoch 8）**：在 **TRAIN 的每一个自然年**里，候选在**该年内**计算的
sharpe 都必须高于**任一 parent 在同一年**的最高 sharpe。逐年指标在**年内**计算
（`component-scan.yearlySplit()`），parent = 家族 **champion**。

⚠ **epoch 7 的 `worstTrainYear`（最差年 objective 的 maximin）已作废**，不再是任何结论的判据。
epoch-7 的回合结论仍按 epoch-7 的规则成立（guard 依 `integrateBar.basis` 分派，老纪元用老规则判），
但**不自动升格为 epoch-8 结论**——要宣称 epoch-8 结论必须按本节重判（重判，不是重测）。

**为什么用 sharpe 而不是 objective。** objective = `(annual − maxDD)/100` 几乎就是年化收益
（60 行 epoch-6 实测：r = 0.9698，maxDrawdown 只占公式所见离散度的 24%），所以 objective 的 bar 是
一个**收益水平**的 bar；一次以风险调整质量为收益的合并，会因为与质量无关的原因过线或不过线。
sharpe 才是风险调整后的量，而且它本来就是闸门的度量。

**为什么要求「每一年」而不是「最差的那一年」。** maximin 允许候选靠「在某一年最不差」胜出，同时放弃
另一年。domination 问的是更难也更诚实的问题：**市场换了 regime 的时候，这次合并是否仍然比它的
parent 好？** TRAIN 恰好跨两个差异极大的年份（已存曲线上 2022 贡献 log 增长中位数 62%，头部书
63–71%），所以「两年都要赢」就是「这次合并必须撑过 regime 切换，而不是骑在其中一边」。

⚠ **逐年的最佳 parent 可能逐年不同**，于是候选面对的是一个**没有任何单一 parent 能达到的复合体**。
epoch 7 把这当成选 maximin 的理由；**epoch 8 接受它，作为 domination 的代价**。guard 会打
`parents-split-by-year` 标记并打印逐年归属。实测例（2026-10-16）：全A 的 打板短线 champion 逐年
sharpe 为 **2022 7.45 / 2023 −0.18**，红利低频为 **1.18 / 1.67**，所以 全A 的 bar 是
「2022 打败 7.45 **且** 2023 打败 1.67」。

⚠ **它需要曲线**：候选与**每一个** parent 都要有已存 TRAIN 曲线，否则退回汇总 objective 规则并
**必须声明**（`flags: bar=pooled-fallback`）。当前 13 个家族里 **7 个 champion 有可用逐年切分，
4 个没有**（七星高照 / 五福闹新春 / 大小盘轮动 / 小市值），涉及它们的回合会落到退回路径。
先跑 `node utils/series-backfill.js`（零回测成本）。

**为什么汇总 objective 不再是判据。** 在 60 行 epoch-6 实测上：

| 实测 | 值 |
|---|---|
| Pearson r(annual%, objective) | **0.9698** |
| maxDrawdown 占公式所见离散度 | **24%**（sd 13.7 对 43.6） |
| Spearman ρ(objective, sharpe) | **0.9836** |

即 **objective 几乎就是年化收益**；「赢过最佳成员」实际等于「比这个 universe 里最大的那本书赚得更多」。
而 TRAIN 的年化**本身主要是一次 2022 的测量**：13 条已存 TRAIN 曲线中，2022 贡献 log 增长的
**中位数 62%**，前 8 名**全部在 63–71%**（2022/2023 收益为 286/121、182/52、157/55、156/55）。
TRAIN = 2022-01-01..2023-12-31，2022 是小盘行情年。所以**用 2022 的尾部换 2023 的稳定性的候选，
按构造必输**——2026-10 的 全A 回合原话：「combining relocates WHICH YEAR earns; it does not add」。
同理，**以稳健性为收益的合并**（小盘：同一 edge 的两种实现）在汇总指标里**根本没有表达通道**。

⚠ 上面这段「为什么用汇总 objective 不行」仍然成立，但 **epoch 7 当时据此选的 maximin 已被 epoch 8
反转为逐年支配**：epoch 7 认为「逐年支配会让候选输给一个没有单一成员能匹配的组合」是拒绝它的理由，
epoch 8 把同一件事当作 domination 的**代价**接受下来。本节保留 epoch-7 的论证是为了让旧结论能按产生
它的规则被读懂；现行判据一律以上文 basis = `perYearSharpe` 为准。

**成员 = 家族 CHAMPION，不是你拆解的 base。** rule 1 问的是「这次合并是否打败了本 universe 本来
就会交付的东西」，而 universe 交付的是最好家族的 champion（PROMOTE 就是这么做的）。拆解当然从
base 走——那才有可读的流水线骨架——但**判定对标 champion**。ETF 第 2 回合把两者混为一谈，于是跑在一个
低了 0.38 的 bar 上：ETF动量 base obj 0.1868 / sharpe 1.41 / 最差年 −0.0072，champion
**0.4725 / 2.23 / +0.3673**；七星高照 base 0.1252 / 1.21，champion **0.3365 / 2.54**。该回合报出
「+0.0274 uplift」，对标 champion 则是约 **−0.43**。bar 由 `championOf()` 从账本推导（在
`measurementValid()` 接受的纪元里取 objective 最大的行），**不是调用方的输入**；调用方给低了会被标记
`member-below-champion:<family>`。
⚠ 它读**账本**而不是 `component-scan.members()`——后者会跳过没有曲线的行，那样会把一个较弱的行当成
七星高照的 champion（它真正的 champion 是一本三马/七星组合书，没有可取回的曲线），于是又一次低估 bar。
⚠ **两套聚合必须分开**：bar 侧用 champion（rule 1，我们本来会交付的替代品），腿侧用调用方给的成员
（rule 2，对实际被组合的东西做归因）。把两者合并就是这个 bug 的成因，也让 `all-parents-below-gate`
在 ETF 上误报。

**汇总比较仍然打印，但不再否决**（`pooledIsVeto: false`）。它是证据：候选赢在稳健性、让出了量级时，
回合必须说清自己要的是哪一个。

⚠ **缺曲线时退回汇总规则，并且必须声明**（`flags: bar=pooled-fallback`）。因为少了一个文件就悄悄
放松的门槛，比一个单纯严格的门槛更坏。所以 `candidate.json` 的**候选本身**和**每个成员**都要带
`sourceFile`（或 `seriesKey`）；**成员只覆盖了一部分也算退回**——在子集上算出来的 BAR，悄悄漏掉的
恰好可能是那个定下 BAR 的成员。

⚠ **`yearlySplit` 必须先换算再切片。** `dailyReturns()` 在**整条** `cum` 上跑，**收益序列**再按日期
切。先切 `cum` 会把该片段第一天对着基数 1 来算，于是把之前所有年份的累计涨幅折进一天——一本 2022
涨了两倍的书，2023 片段会以 ~200% 的「日收益」开场，该年的年化/波动/夏普/回撤**全是看起来像数字的
虚构**。与「用累计百分比作差而不是链式相乘」同一类错误（那次报出波动 1.3620 对 JQ 的 0.2271）。

⚠ **逐年年化按窗口年的自然日数**（`harness.windowYears()`，TRAIN 两年各 365），不是曲线自己的跨度。
各自按自身跨度年化会注入一个**随收益水平放大**的偏差（中位 0.27pp，但在一本 85.9% 的书上 0.80pp）。

## 5. 回测执行器输出契约（SUMMARY 行）

`node utils/strategy-post-backtest.js <file> "<expId>" --window <train|val>` 跑完在末尾打印一行：

```
SUMMARY\t<window>\t<start>\t<end>\t<days>\t<total%>\t<annual%>\t<sharpe>\t<maxdd%>\t<status>
```

- `annual%` 已按 §4 从 `total%` 与实际 `days` 年化；`sharpe`/`maxdd%` 取自 JQ。
- `status`：`completed`（可记账）/ `window-mismatch`（实际区间≠请求，**不得记账**，修正重跑）/ `no-trades`（跑完但**零成交**：收益与回撤同为 0，通常是选股/数据链路断了，**不得记账**，查因而非重跑）/ `failed`（崩溃，记 crash）。
- `--window` 只接受 `train` / `val`；`holdout` 或任何 `>= 2026-01-01` 的区间会被 `OOS-BLOCKED` 拒跑（除非用户 `JQ_ALLOW_OOS=1`）。
- 迭代中（Type-1）算 `objective(TRAIN)`；定稿（Type-2）算 `objective(VAL)`。门槛见配置（epoch 7：全阶段 `sharpe ≥ 1.5`；整合回合的 BAR 见 §4.1）。

## 6. 变更协议（怎么开新纪元）

1. 人类编辑本文件对应常量。
2. `epoch` +1，更新 `setAt` 与 `note`。
3. `wiki/log.md` 追加：`## [YYYY-MM-DD] experiment | harness epoch <n> | <改了什么>`。
4. 旧纪元的 `enhance/results.tsv` 与 `wiki/experiments/` 结果封版；新实验从新 baseline 起，不与旧纪元横比。
