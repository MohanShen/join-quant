# join-quant 自主研究（autoresearch）Schema

本文件定义 `research/` 自主策略研究循环的结构与规则，是 `docs/wiki-schema.md`（知识库 Schema）的姊妹篇。
灵感来自 Andrej Karpathy 的 [`autoresearch`](https://github.com/karpathy/autoresearch)：
**「人类只编辑 `program.md`（研究组织的代码），AI 在冻结的评测台上自主迭代单一产物，keep/discard 全凭一个客观指标。」**

本项目在其基础上加了 autoresearch 没有的东西：一个**持久知识库**（`wiki/`）。
因此研究循环是闭环的：

```
wiki 概念页「待研究/空白」  →  提出假设  →  生成/变异 strategy.py
        ↑                                          │
        │                                          ▼
   回填新知识（wiki/experiments/）  ←  keep/discard  ←  冻结评测台回测
```

分工同 `wiki-schema.md`：**人类**提假设方向、审阅、裁决冲突、维护冻结常量；**LLM** 负责生成策略、跑回测、记账、回填。

---

## 1. 与 autoresearch 的对应关系

| autoresearch | 本项目 | 说明 |
|---|---|---|
| `train.py`（被编辑的产物） | `research/candidates/<expId>.py`（策略源码） | 唯一被变异的对象 |
| `prepare.py`（只读评测台） | **冻结评测台**（§3）：回测窗口 + 标的池 + 费率滑点 + 目标函数 | **绝不可被 agent 修改** |
| `val_bpb`（单标量，样本外） | `objective`（§3.3），在**验证期**上度量 | 越大越好 |
| 固定 5 分钟预算 | 固定回测窗口（train/val/holdout，§3.1） | 保证实验可比 |
| `results.tsv` | `research/results.tsv`（§7） | 追加式账本，git 不跟踪 |
| `program.md` | `research/program.md` | 研究循环的 agent 指令 |
| keep=advance / discard=git reset | 同（§8），但 keep 需**验证期提升 + holdout 确认** | |
| （无持久知识） | `wiki/experiments/`（§6）+ 回填契约（§9） | **本项目独有** |

---

## 2. 目录结构

```
join-quant/
├── research/
│   ├── program.md              # 研究循环 agent 指令（人类编辑，见姊妹文件）
│   ├── harness.md              # 冻结评测台常量的权威定义（§3，人类维护，改动即新纪元）
│   ├── strategy_template.py    # 策略脚手架（§5）：受控因子槽位
│   ├── candidates/<expId>.py   # 每个实验的策略源码（变异产物，raw）
│   └── results.tsv             # 追加式账本（§7，git 不跟踪）
└── wiki/
    └── experiments/<expId>.md  # 每个实验一页（§6）：假设·变异·三窗结果·结论·回填指针
```

- `research/candidates/` 与 `strategies/` 一样属于 **raw 层**：一旦回测过即不可变（git 记录演进）。
- `wiki/experiments/` 是 wiki 的**第四类页面**（前三类：strategies / concepts / authors）。
- 所有正文为**中文**，与 `wiki-schema.md`、`push-format.md` 一致。

---

## 3. 冻结评测台（frozen harness）

这是本 Schema 的核心。类比 `prepare.py`：**一经设定即冻结，agent 只读不可改**。
**权威常量定义在 `research/harness.md`**（本节仅摘要，冲突以 harness.md 为准）。
任何改动都视为「新纪元」，需人类在 `research/harness.md` 显式变更并记 `log.md`，此前所有实验结果就此封版、不再与新纪元横比。

### 3.1 三个回测窗口（period split）

用 JoinQuant Pipeline 2（`utils/strategy-post-backtest.js`）的回测区间参数实现。当前 epoch 1（权威见 `research/harness.md`）：

| 窗口 | 区间 | 用途 | agent 可见性 |
|---|---|---|---|
| **TRAIN** | 2022-01-01 → 2023-12-31 | 开发/自检 | 可见，可无限次 |
| **VAL** | 2024-01-01 → 2024-12-31 | **选择指标**（keep/discard 依据） | 可见，可无限次 |
| **HOLDOUT** | 2025-01-01 → 回测当日（滚动） | **最终确认**，防过拟合 | **锁定**：仅对「验证期新最优」跑一次，绝不用于逐轮调参 |

> ⚠ JoinQuant Pipeline 2 当前硬编码窗口 2019-01-01→2019-06-30（见 README「Known Limitations」）。
> 实现本 Schema 需把三个窗口参数化（改 `strategy-post-backtest.js` 的 `newStrategy` URL 参数），
> 这属于**评测台实现**，不属于策略变异——agent 不得借调参之名改动它。
> ⚠ 区间特性：TRAIN 无明显牛市、VAL 仅一年，夏普噪声大——见 `harness.md` §1。

### 3.2 标的池与成本假设（冻结，权威见 `harness.md` §2–§3）

- **手续费**：`PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)`（买万3 / 卖万3+印花税千1 / 最低5元）。
- **滑点**：**零滑点** `FixedSlippage(0)`——刻意与社区/wiki 绩效保持可比。**代价：换手成本被忽略**，高换手/微盘/打板类 `objective` 被系统性高估；此类 keep 必标「零滑点高估」（详见 `harness.md` §2 警示）。
- **基准**：`000300.XSHG`，仅显示用，不影响 `objective`（夏普对基准无关）；固定它只为跨实验一致。
- **基础资金**：￥1,000,000；**真实性过滤**（剔除 ST/停牌/次新、涨停不买/跌停不卖）强制内置于 `strategy_template.py`，不得移除（`harness.md` §3）。
- **真实性红线**：继承 wiki 的 ⚠ 约定——打板/涨停/龙虎榜等**成交假设不真实**的范式，其回测收益不得当作可实现收益；此类实验必标 ⚠，`objective` 仅作参考、不得据以宣称「有效」。

### 3.3 目标函数（objective）——本项目的 `evaluate_bpb`

单标量，越大越好。在指定窗口 `w` 上：

```
gate(w)   = ( sharpe(w) >= 2.5 )                       # 硬门槛：夏普 < 2.5 直接淘汰
score(w)  = annualReturn(w) - maxDrawdown(w)           # 均为小数（0.35 = 35%）
objective(w) = score(w)        若 gate(w) 为真
             = DQ (disqualified，记为 -inf)   否则
```

- **选择指标** = `objective(VAL)`。keep/discard 只看它（§8）。
- `gate` 未过（夏普 < 2.5）即 `DQ`，等价于 discard，无论收益多高。
- `score` 用「年化 − 最大回撤」而非夏普/卡玛：奖励高收益、惩罚深回撤，夏普退化为门槛而非连续目标。
- 门槛值 2.5、公式形式均属**冻结常量**，改动即新纪元。

---

## 4. 假设来源（hypothesis）

实验不能凭空起。每个实验的假设必须可溯源到 wiki 的某处「缺口」或「观察」：

1. **概念页「待研究/空白」小节**——首选来源。这是 KB 明确登记的知识缺口。
2. **概念页「变体与差异」表**——横向对比暴露的规律（如「加了大盘趋势止损的小市值回撤更低」）可作为可检验假设。
3. **`/query-wiki` 回填的「观察」**——过往问答沉淀的规律。
4. **跨概念组合**——把两个概念页的因子拼装（如 [[小市值因子]] × [[择时-均线]]），检验 1+1 是否 >2。

每个假设写成一句可证伪的话，落入实验页 frontmatter 的 `hypothesis` 字段（§6）。

---

## 5. 策略脚手架与变异空间（mutation space）

策略不是随意改代码，而是从 KB 的**受控因子词表**（`wiki-schema.md` §2.1）组合而来。
`research/strategy_template.py` 提供带槽位的骨架，槽位对应四类因子角色：

```
选股因子  →  规模价值 / 质量基本面 / 动量 / 技术量价 / 流动性 / 情绪事件
择时因子  →  趋势均线 / 位置估值 / 日历 / 防御信号
风控因子  →  §3.1 止损类型枚举
仓位因子  →  等权 / 动态持仓数 / 满仓单标的 / 流动性配权 / 预留资金
```

一次「变异」= 下列之一：
- **参数调整**：在既有因子上调参（均线周期、持仓数、止损线）。
- **因子增删**：加/减一个受控因子（如给纯小市值加「大盘趋势」风控）。
- **模块替换**：换择时或风控模块（如 MA10偏离 → RSRS）。
- **跨概念拼装**：组合两个概念族的信号。

新因子子类/概念**必须先登记** `wiki-schema.md` 的受控词表，再使用——杜绝同义分叉，与 ingest 规则一致。

---

## 6. 实验页格式 `wiki/experiments/<expId>.md`

`expId` = `<tag>-<NNN>`（如 `jul3-007`），与分支 `research/<tag>`、账本行、`candidates/<expId>.py` 一一对应。

```markdown
---
expId: jul3-007
branch: research/jul3
commit: <7位短哈希>                      # candidates/<expId>.py 的提交
baseExpId: jul3-006                     # 本实验从哪个已 keep 的实验变异而来（首个填 baseline）
hypothesis: 给最小市值轮动叠加深证综指MA10择时能把回撤压到15%以内而不牺牲年化   # 一句可证伪的话
sourceRefs: [[[小市值因子]], [[择时-均线]]]   # 假设溯源到的 wiki 页
mutation: 在 baseline 上增加 择时·趋势均线(深证综指MA10偏离) 空仓开关
factors:                                # 同 wiki-schema §2.1，四角色受控
  选股: { 规模价值: [小市值], 质量基本面: [国九条] }
  择时: [深证综指MA10偏离]
  风控: [止损线-9%]
  仓位: [等权, 动态持仓数]
results:                                # 三窗指标，缺失窗口省略
  train:   { annualReturn: <小数>, sharpe: <数>, maxDrawdown: <小数>, objective: <数或DQ> }
  val:     { annualReturn: <小数>, sharpe: <数>, maxDrawdown: <小数>, objective: <数或DQ> }
  holdout: { annualReturn: <小数>, sharpe: <数>, maxDrawdown: <小数>, objective: <数或DQ> }   # 仅验证期新最优时填
status: keep | discard | crash          # 与账本一致
confirmed: true | false                 # holdout 是否确认（val 提升且 holdout 未失格）
flags: [overfit?, ⚠不真实成交]           # 可选：holdout 明显劣于 val 记 overfit
ranAt: <YYYY-MM-DD>
---

# 实验 jul3-007：小市值 + MA10择时

**假设**：<复述 frontmatter 的可证伪命题>

## 变异
<相对 baseExpId 具体改了什么：加了哪个因子/调了哪个参数，引用 [[概念]]>

## 结果
| 窗口 | 年化 | 夏普 | 最大回撤 | objective |
|------|------|------|----------|-----------|
| TRAIN | … | … | … | … |
| VAL | … | … | … | … |
| HOLDOUT | … | … | … | …（仅新最优时）|

## 结论
<假设成立与否？相对 baseExpId 是提升还是劣化？是否 confirmed？>

## 回填指针（§9）
- 已回填至 [[择时-均线]]「观察」小节：<一句结论>
- 或：无跨策略价值，未回填。
```

---

## 7. 结果账本 `research/results.tsv`

追加式，制表符分隔（**非逗号**，描述里会有逗号）。**git 不跟踪**（同 autoresearch，`.gitignore` 加 `research/results.tsv`）。
账本是快速 `grep` 的一手记录；`wiki/experiments/` 是其结构化、带溯源的对应物。

7 列：

```
expId	commit	val_objective	holdout_objective	sharpe_val	status	description
```

1. `expId`（如 `jul3-007`）
2. `commit`（7 位短哈希）
3. `val_objective`（验证期目标值；DQ 记 `DQ`）
4. `holdout_objective`（holdout 目标值；未跑记 `-`）
5. `sharpe_val`（验证期夏普，用于一眼看门槛）
6. `status`：`keep` / `discard` / `crash`
7. 简短描述（这次变异试了什么）

示例：

```
expId	commit	val_objective	holdout_objective	sharpe_val	status	description
jul3-000	a1b2c3d	0.22	0.19	2.8	keep	baseline 最小市值月度轮动
jul3-001	b2c3d4e	0.28	0.24	3.1	keep	加国九条质量过滤
jul3-002	c3d4e5f	DQ	-	1.9	discard	持仓数降到2 夏普跌破门槛
jul3-003	d4e5f6g	0.31	0.16	2.9	discard	MA5择时 val涨但holdout崩 overfit
```

---

## 8. Keep / discard / branch 规则

实验跑在专用分支 `research/<tag>`（如 `research/jul3`）。**LOOP**：

1. 看 git 状态：当前分支/commit。
2. 按 §5 变异 `research/candidates/<expId>.py`（从当前最优变异）。
3. `git commit`。
4. 回测 **TRAIN**（自检不崩）与 **VAL**（选择指标）。
5. 读 `objective(VAL)`：
   - **`DQ`（夏普<2.5）或 ≤ 当前分支最优** → **discard**：`git reset` 回上一个 keep，账本记 `discard`，实验页 `status: discard`。
   - **> 当前分支最优且非 DQ** → **provisional keep**：保留 commit，推进分支。
6. 对每个 provisional keep，**跑一次 HOLDOUT**（此为 holdout 唯一合法用途）：
   - holdout 未失格且 `objective(HOLDOUT)` 未显著劣于 VAL → `confirmed: true`，`status: keep`。
   - holdout 失格或明显崩塌 → 标 `flags: [overfit]`，`confirmed: false`；**仍推进分支**（因为 val 是选择指标），但实验页与账本明确标注，**不得当作可实现的成果**。
7. 记账本（§7）+ 写/更新实验页（§6）+ 回填（§9）+ 追加 `wiki/log.md`。
8. 回到 1。

- **首个实验** `<tag>-000` 永远是 **baseline**：跑未变异的脚手架/某个已知策略，确立基准线。
- **HOLDOUT 绝不驱动逐轮决策**——只确认，不选择。违反即数据泄漏，使整个纪元作废。
- **崩溃**：回测跑不动/CDP 掉线/策略报错，判断是否手误可修；否则记 `crash`，跳过。
- **超时/限流**：JoinQuant Pipeline 2 是唯一执行器，受 CDP 会话与 VIP 限额约束；throughput 远低于 autoresearch 的 100/夜。可按批次人机协作推进，但**单批次内**遵循上述自主循环。

---

## 9. 知识回填契约（write-back）

实验产生两类知识：

1. **单实验结果** → `wiki/experiments/<expId>.md`（§6）+ 账本（§7）。
2. **跨策略规律** → 回填到相关**概念页**。复用 `/query-wiki` 的回填机制：**只追加**到概念页的「观察」或「待研究/空白」小节，**不覆盖**既有结论。

回填规则（与 `wiki-schema.md` §9 一致）：
- **可溯源**：概念页每条新结论必须带 `[[<expId>]]` 指针，回溯到实验页 → commit → `candidates/<expId>.py`。
- **追加优先**：概念页只加不改；矛盾只标记、留人裁决。
- **闭环登记**：假设若来自某概念页的「待研究」，实验有结论后应把该条从「待研究」移动/更新为「观察」，并注明 `[[expId]]`。
- **`log.md` 新增 op** `experiment`：
  ```
  ## [YYYY-MM-DD] experiment | jul3-007 (小市值+MA10择时) val=0.28 holdout=0.24 keep → 回填 [[择时-均线]]
  ```
  op 全集扩展为：`ingest` / `skip-dup` / `concept` / `query` / `lint` / `merge` / **`experiment`**。

---

## 10. 不可违反的原则

- **评测台冻结**：`objective`、门槛 2.5、三窗区间、费率滑点一经设定即不可改；改动即新纪元，旧结果封版。
- **HOLDOUT 只确认不选择**：任何用 holdout 调参的行为都使纪元作废。
- **raw 不可变**：`strategies/` 与已回测的 `research/candidates/` 均不改。
- **真实性红线**：继承 wiki 的 ⚠ 约定；不真实成交的范式不得宣称「有效」。
- **可溯源**：账本、实验页、概念页结论均可回溯到 commit 与源码。
- **受控命名**：因子/概念一律走 `wiki-schema.md` §2 词表，先登记后使用。
- **追加与人裁**：概念页只追加；冲突只标记、不自行裁决。

---

## 11. 归一化（normalize）——把 raw 策略重测到统一基线

`strategies/` 里的 144+ 策略是**不同年代、不同费率/滑点、不同回测区间**下自报绩效的 raw 层，彼此不可横比。
归一化 = 用**冻结评测台**把每个 raw 策略在**同一 TRAIN 区间、同一成本、同一 objective** 下重测一遍，
得到 apples-to-apples 的「谁在统一区间真能打」——这是 autoresearch 的**先验基线**：
已知有效的策略/因子 = 归一化后过门槛者，据此挑选变异起点、避免重复造轮子。

### 11.1 强制成本归一（raw 不可变）
- 每个 raw 策略源码**尾部追加**一段 override（不改 `strategies/` 原文，写临时副本喂 Pipeline 2）：
  重定义 `set_slippage`/`set_commission` 为**恒定冻结值**（零滑点 + `PerTrade(万3/万13/5)`），
  这样即便策略在 `before_trading_start`/`handle_data` 里**逐 bar 重设**成本，也一律被拉回冻结值；
  并包裹 `initialize` 补 `use_real_price=True`。见 `utils/strategy-normalize.js` 的 `OVERRIDE`。
- 区间/基础资金（¥100万）由 Pipeline 2 平台参数强制（`--window train`）。

### 11.2 批量执行器与账本
- `node utils/strategy-normalize.js --window train [--filter <substr>] [--limit N]`：枚举 → 兼容性预检 → 追加 override → 跑 Pipeline 2 → 解析 SUMMARY → 写账本。
- **可续跑**账本 `research/normalize-<window>.tsv`（git 不跟踪），已有终态的策略跳过。列：
  `sourceFile  postId  title  status  start  end  days  total_pct  annual_pct  sharpe  maxdd_pct  objective  gate`
- `status`：`normalized`（完成，可入 KB）/ `incompatible-futures`（期货，stock 回测跑不了）/ `incompatible-notrunnable`（无 `initialize` 的工具/研究页）/ `crash`（回测报错）/ `window-mismatch`。
- `objective` / `gate` 同 §3.3（`annual−maxdd`，门槛 `sharpe≥2.5`；不过门槛记 `DQ`/`fail`）。

### 11.3 KB 更新契约
账本产出后，按下列方式更新 wiki（可分批，像 ingest 一样）：
- **策略页 frontmatter** 增 `normalized` 块（可溯源到本次 epoch 与账本）：
  ```yaml
  normalized:
    epoch: 1
    window: TRAIN 2022-01-01..2023-12-31
    annualReturn: <小数>   sharpe: <数>   maxDrawdown: <小数>
    objective: <数或DQ>    gate: pass|fail
    ranAt: <YYYY-MM-DD>
  ```
  与页内既有「自报绩效」并存、不覆盖；若归一化结果与自报差距大，在「备注/矛盾」注明（区间/成本差异）。
- **概念页** 增「## 归一化绩效横评（TRAIN 2022–2023，epoch 1）」小节：按 `objective` 排序的表，
  标 `gate pass/fail`，一眼看出该概念下**统一区间真能打的成员**；旧「绩效横评」保留（自报、区间不一）。
- **`log.md` 新增 op** `normalize`：`## [YYYY-MM-DD] normalize | <n> 策略 @TRAIN epoch1 | pass <a> / fail <b> / incompat <c>`。
  op 全集：`ingest` / `skip-dup` / `concept` / `query` / `lint` / `merge` / `experiment` / **`normalize`**。

### 11.4 运行时预算与安全（JoinQuant 计费现实）

JoinQuant 对回测**计时收费**，直接约束归一化的节奏：
- **每日免费 60 分钟**回测运行时长（每日重置）；超出部分**每 30 分钟扣 2 积分**，**积分为负时才无法新建回测**（超免费但积分为正仍可跑，只是花积分）。
- 用量直接查 API：`GET /algorithm/index/statistics` → `{data:{duration:{used,free}, running:[{id,name,usedSec}]}}`。
- **并发上限 2**（`编译失败:当前并行编译或回测数量最多2个`）。
- ⚠ **回测一经开启即运行至结束（最长 3 天），即使前端离开也在服务器端继续跑、并在结束时计入 `used`**。

**成本控制 = 事前用量闸门（不是取消）**。取消一个运行中的回测既脆弱又易失败，且失败会让慢回测跑到底、全额计费——这正是早期烧积分的根因。故新策略：
- **事前闸门**：每个回测开跑前查 `used`；`used ≥ USAGE_LIMIT`（`--usage-limit`，默认 55）就**不再新建**回测（子进程打印 `USAGE-STOP`，`strategy-normalize.js` 据此停批）。因批次**串行**，`used` 在每次检查时都是最新，无滞后。
- **运行中不早停**：让回测跑到 `完成/失败`，其时长计费（已接受）。最坏超支 = 最后一个刚好卡在闸门下启动的回测的时长。
- **仅保留安全网**：`MAX_POLL_MS`（默认 45 分钟）——只有**真卡死**的回测才在此调**取消 API** 兜底，防止阻塞整批；正常慢回测远早于此结束。
- **取消 API（关键）**：`#cancel-daily-backtest-button` 只弹「确实要取消?」确认框，点它**不会取消**（早期孤儿的根因）。真正的取消是 `Cy.ajax("/algorithm/index/cancel",{data:"backtestId="+backtestId})`——即带 `X-Requested-With: XMLHttpRequest` 头请求 `/algorithm/index/cancel`，`backtestId` 取编辑页隐藏输入 `#backtestId`。`cancelBacktest()` 已直接调此 API。
- **并发上限检测**：`编译运行` 后读编辑页 `编译失败…并行…最多` toast → `rate-limited`，退避 45s 后重试（不烧该策略）。**熔断**：连续 6 次失败即停（`process.exit(2)`），可续跑。

**按日预算跑法**（用量闸门自动控成本，可花积分换吞吐）：
```bash
# 例：小市值概念，日用量上限 240 分钟（免费60 + ~180 积分时长）
node utils/strategy-normalize.js --window train --concept 小市值因子 --usage-limit 240
```
`--concept <名>` 按 wiki 概念挑成员；`--usage-limit N` 设日用量上限（默认 55，仅免费额度内）；`--limit N` 限批量条数；账本可续跑。

### 11.5 与 autoresearch 的关系（起点契约）
- 归一化基线回答「**起点**在哪」：过门槛（gate ✅）的策略/因子组合是 autoresearch 变异的高价值起点；
  全员 DQ 的概念（如 jul4 里 2024 的裸小市值族）则提示该方向在此区间不成立。
- **autoresearch 的 `<tag>-000` baseline 必须是一个已归一化的过门槛策略**（从各概念页「归一化绩效横评」挑 gate ✅ 者），
  而**不是**裸 `strategy_template.py`——jul4 已证裸最小市值月度轮动在 VAL 全 DQ。做法：
  取该策略 `strategies/<file>.py` 源码 + `strategy-normalize.js` 的冻结成本 `OVERRIDE`（零滑点/PerTrade），
  存为 `research/candidates/<tag>-000.py`；其 TRAIN objective 应≈ 该策略页 `normalized:` 值。此后小步变异，朝赢家配方靠拢。
- 归一化用 **TRAIN**（与实验开发区间一致），故它是**先验/特征**，**不是** holdout——
  不构成数据泄漏：VAL/HOLDOUT 仍只在 autoresearch 循环里按 §8 使用。
- **预算一致**：autoresearch 与归一化共用同一 JQ 计费现实（§11.4）——循环受 `--usage-limit` 约束，
  `used ≥ limit` 即停、等次日重置，不为「跑满循环」烧积分。
