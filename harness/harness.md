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

- **epoch**: 5
- **setAt**: 2026-09-20
- **note**: **只改计分，不改测量台**（成本/钉死项/窗口与 epoch 4 完全相同）。两点：
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
#   bar = worstTrainYear   # 候选最差年 objective 必须赢过「最稳健成员」的最差年
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

### 4.1 整合回合的 BAR（epoch 7 起冻结）

闸门（`sharpe >= 1.5`）回答「这个结果可用吗」。**BAR 回答「它赢过被整合的家族了吗」**，这才是整合
回合真正的判据，由 `objective.integrateBar` 声明、`harness.integrateBar()` 读取。

**basis = `worstTrainYear`**：候选在 **TRAIN 最差自然年**的 objective，必须赢过**最稳健成员**在其
TRAIN 最差自然年的 objective。逐年的 annual / maxDD 在**年内**计算
（`component-scan.yearlySplit()` / `worstYear()`），公式仍是 `(annual − maxDD)/100`。

**为什么不再用汇总 objective。** 在 60 行 epoch-6 实测上：

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

**为什么是 maximin 而不是「每年都赢」。** 逐年支配允许一个成员占住 2022、另一个占住 2023，于是候选
会因为输给一个**没有任何单一成员能匹配的组合**而被拒——那不是与任何真实替代方案的比较。maximin 比的
是同类：最稳健的那个成员，对候选自己最弱的那一年。

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
