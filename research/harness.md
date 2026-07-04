# research/harness.md — 冻结评测台常量（权威）

本文件是**冻结评测台**的唯一权威定义（类比 Karpathy `autoresearch` 的 `prepare.py`）。
`docs/research-schema.md` §3 引用本文件；如有出入，**以本文件为准**。

> **纪元（epoch）**：本文件全部常量一经设定即冻结。任何改动 = 新纪元：
> 递增下方 `epoch`、记 `wiki/log.md` 一行 `experiment | harness epoch <n> ...`，
> 此前所有实验结果就此封版，不再与新纪元横比。
> agent **只读本文件，绝不修改**；也绝不在策略代码里改动被本文件冻结的项。

---

## Epoch

- **epoch**: 1
- **setAt**: 2026-07-04
- **note**: 首个纪元。

---

## 1. 回测三窗（period split）

由 JoinQuant Pipeline 2（`utils/strategy-post-backtest.js`）的回测区间参数实现（平台级，非策略代码）。

| 窗口 | 起 | 止 | 用途 | agent 可见性 |
|---|---|---|---|---|
| **TRAIN** | 2022-01-01 | 2023-12-31 | 开发/自检 | 可见，可无限次 |
| **VAL** | 2024-01-01 | 2024-12-31 | **选择指标**（keep/discard 依据） | 可见，可无限次 |
| **HOLDOUT** | 2025-01-01 | **回测当日最新交易日**（滚动） | **最终确认**，防过拟合 | **锁定**：仅对「验证期新最优」跑一次 |

- HOLDOUT 止点随时间前滚（真·样本外），每次跑取当日可得的最新数据。
- ⚠ **区间特性**（读结果时牢记）：TRAIN 覆盖 2022 熊 + 2023 震荡，**无明显牛市**；VAL 仅 2024 一年，样本短、夏普噪声大。keep 一个验证期结果前，最好确认 TRAIN 与 HOLDOUT 方向一致，别被单年 VAL 带偏。

---

## 2. 回测配置（冻结）

**平台级**（由 Pipeline 2 的 `newStrategy` URL 参数设定，不在策略代码里）：

| 项 | 值 |
|---|---|
| 基础资金 | **￥1,000,000** |
| 频率 | 每天（日线） |
| 复权/真实价 | `use_real_price=True` |

**代码级**（在策略 `initialize` 的「勿改区块」里设定，见 `strategy_template.py`；agent 不得改动这些行）：

| 项 | 值 | JQ 写法 |
|---|---|---|
| 基准 | 沪深300 | `set_benchmark('000300.XSHG')` |
| 手续费 | 买万3 / 卖万3+印花税千1 / 每笔最低5元 | `set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))` |
| **滑点** | **0（零滑点）** | `set_slippage(FixedSlippage(0))` |

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
gate(w)      = ( sharpe(w) >= 2.5 )                    # 硬门槛
score(w)     = annualReturn(w) - maxDrawdown(w)        # 均为小数，如 0.35 = 35%
objective(w) = score(w)      若 gate(w) 为真
             = DQ (记为 -inf) 否则
```

- **选择指标** = `objective(VAL)`；keep/discard 只看它（`research-schema.md` §8）。
- 门槛 `2.5`、公式形式均为**冻结常量**，改动即新纪元。

> **annualReturn 的来源**：JoinQuant 回测列表（buildList）只给**总收益**（策略收益），不直接给年化。
> 故 `annualReturn` 由执行器 `strategy-post-backtest.js` 按**实际回测区间天数**从总收益年化：
> `annualReturn = (1 + 总收益)^(365/天数) − 1`。
> `sharpe`、`maxDrawdown` 直接取自 JQ 回测结果。三者与区间一并写入机器可读的 `SUMMARY` 行（见 §6）。

---

## 5. 回测执行器输出契约（SUMMARY 行）

`node utils/strategy-post-backtest.js <file> "<expId>" --window <train|val|holdout>` 跑完在末尾打印一行：

```
SUMMARY\t<window>\t<start>\t<end>\t<days>\t<total%>\t<annual%>\t<sharpe>\t<maxdd%>\t<status>
```

- `annual%` 已按 §4 从 `total%` 与实际 `days` 年化；`sharpe`/`maxdd%` 取自 JQ。
- `status`：`completed`（可记账）/ `window-mismatch`（实际区间≠请求，**不得记账**，修正重跑）/ `failed`（崩溃，记 crash）。
- `/run-experiment` 据此算 `objective = annual%/100 − maxdd%/100`，门槛 `sharpe ≥ 2.5`。

## 6. 变更协议（怎么开新纪元）

1. 人类编辑本文件对应常量。
2. `epoch` +1，更新 `setAt` 与 `note`。
3. `wiki/log.md` 追加：`## [YYYY-MM-DD] experiment | harness epoch <n> | <改了什么>`。
4. 旧纪元的 `research/results.tsv` 与 `wiki/experiments/` 结果封版；新实验从新 baseline 起，不与旧纪元横比。
