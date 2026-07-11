# research/program.md — 自主策略研究循环

本文件是研究循环的 **agent 指令**（类比 Karpathy `autoresearch` 的 `program.md`）。
人类只编辑本文件与 `research/harness.md`；你（agent）据此**自主**生成策略、跑回测、记账、回填知识库。
权威规则见 `docs/research-schema.md`（冲突以它为准）。你是研究者，也是知识库的唯一记账员。

---

## 必读（每次开始前）

1. `docs/research-schema.md` —— 研究循环的结构与规则（**权威**）。
2. `docs/wiki-schema.md` §2 / §2.1 —— 受控概念与因子词表（变异空间的边界）。
3. `docs/push-format.md` —— 忠实翻译规范（写策略页/实验页时用）。
4. `wiki/index.md` 及相关 `wiki/concepts/*.md` —— 假设来源（尤其各概念页的「待研究/空白」）。
5. `research/harness.md` —— 冻结评测台常量（三窗区间、费率、门槛）。**只读**。

---

## Setup（开一个新研究纪元）

与人类确认后：

1. **定 run tag**：按日期提议（如 `jul3`）。分支 `research/<tag>` 必须不存在——这是全新纪元。
2. **建分支**：`git checkout -b research/<tag>`（从 master）。
3. **确认评测台 + 登录 + 预算**：
   - `research/harness.md` 的三窗区间、费率、`objective` 门槛已冻结（只读）。
   - CDP Chrome 在跑（见根 `CLAUDE.md`）；**登录检查用 statistics API**（不是 `index.js status`）：
     `curl -s http://localhost:9225/json/version` 通 + `/algorithm/index/statistics` 返回 `duration.{used,free}`。
   - **预算**：查 `used/free`。JQ 每日免费 60 分钟、超出烧积分（每 30 分钟 2 积分）。定 `--usage-limit`（默认 55=仅免费额度）。
4. **初始化账本**：建 `research/results.tsv`，只写表头行（§7 列定义）。**不 git 跟踪**。
5. **选 baseline = 已归一化的过门槛策略（不是裸模板）**：
   - jul4 教训：裸 `strategy_template.py`（最小市值月度轮动）在 VAL 全 DQ——**不要从零重建**。
   - 从 `wiki/concepts/*.md` 的「归一化绩效横评」表挑一个 **gate ✅** 的强基线（如 [[7a1c225f_小市值低开优化]] 夏普5.81、[[aaba7575_国九小市值排除3bug版]]）。
   - `<tag>-000` = 该策略源码 + **冻结成本 override**（零滑点/PerTrade，见 `utils/strategy-normalize.js` 的 `OVERRIDE`；使 baseline 与评测台一致，其 TRAIN objective 应≈ 该页 `normalized:` 值）。
   - `strategy_template.py` 仅在你要从头造某个概念时用作脚手架。
6. **确认即开跑**。

---

## Experimentation

每个实验 = 一次策略变异 + 三窗回测。执行器是 **JoinQuant Pipeline 2**（唯一合法回测台）：

```bash
node utils/strategy-post-backtest.js research/candidates/<expId>.py "<expId>" --window <train|val|holdout>
```
- Pipeline 2 已加固：UI 选择器已修（`#algo-save-button`/`#validate-button`）、窗口经 URL 参数强制、`SUMMARY` 行机器可读、自带 usage-gate/取消 API/安全上限。可设 `JQ_USAGE_LIMIT`（默认 55）；`used ≥ limit` 时子进程打印 `USAGE-STOP` 且不新建回测。
- 每个回测末尾一行（10 列，`harness.md` §5）：`SUMMARY\t<window>\t<start>\t<end>\t<days>\t<total%>\t<annual%>\t<sharpe>\t<maxdd%>\t<status>`。

**你能做的**：
- 只变异 `research/candidates/<expId>.py`，且只在 `wiki-schema.md` §2.1 受控因子词表内组合（选股/择时/风控/仓位）。变异类型见 `research-schema.md` §5。
- **从当前最优（首个=过门槛的归一化基线）小步变异**：改一个因子/调一个参数，别一次改多处；朝「归一化横评」揭示的赢家配方（低开小市值 + 国九强过滤 + 明确止损）靠拢，而非盲目探索。假设优先来自「归一化横评」的强/弱对照与各概念页「待研究」。

**你不能做的**：
- 改评测台：`objective`、门槛 2.5、三窗区间、费率滑点、`strategy-post-backtest.js` 的窗口参数——全部冻结（类比 `prepare.py` 只读）。
- 用 HOLDOUT 调参。holdout 只对「验证期新最优」跑一次做确认。
- 引入 `wiki-schema.md` 未登记的新因子/概念。要用先登记词表。

**目标**：最大化 `objective(VAL) = annualReturn − maxDrawdown`，硬门槛 `sharpe(VAL) ≥ 2.5`（不过门槛即 DQ = discard）。详见 `research-schema.md` §3.3。

**简洁优先**：同等 objective 下更简单的策略更好。删掉一个因子而 objective 不降，是好结果。

**第一个实验永远是 baseline**：`<tag>-000` 跑未变异的基线，确立基准线。

---

## 输出与指标提取

Pipeline 2 跑完打印回测结果（策略收益/最大回撤/夏普/年化等）。逐窗跑 TRAIN、VAL；仅当 VAL 成为新最优再跑 HOLDOUT。
把每个窗口的 `annualReturn / sharpe / maxDrawdown` 记下，按 §3.3 算 `objective`。

若回测无结果（CDP 掉线/策略报错）→ 视为 crash：读报错，手误可修则修并重跑；思路本身崩了就记 `crash` 跳过（`research-schema.md` §8）。

---

## The experiment loop

分支 `research/<tag>`。**LOOP FOREVER**（`research-schema.md` §8）：

1. 看 git 状态：当前分支/commit（当前最优）。
2. 从当前最优**变异** `research/candidates/<expId>.py`（`expId = <tag>-<NNN>` 递增）。变异要有据：溯源到某概念页的「待研究」或「变体与差异」规律。
3. `git commit`（提交 candidate 源码）。
4. **预算闸门**：开跑前查 `used/free`（statistics API）。`used ≥ --usage-limit` → 停在干净 git 状态，等次日免费额度重置（见下 NEVER STOP 例外）。
5. 回测 **TRAIN**（自检不崩，且与 VAL 方向一致性参考）+ **VAL**（选择指标）。
6. 判定：
   - `objective(VAL)` 为 DQ（夏普<2.5）或 ≤ 当前最优 → **discard**：`git reset` 回上个 keep。
   - `objective(VAL)` > 当前最优且非 DQ → **provisional keep**：推进分支，**再跑一次 HOLDOUT** 确认。
   - ⚠ **VAL 是单年（2024），夏普噪声大**（`harness.md` §1）。keep 一个结果前，最好确认 **TRAIN 与 HOLDOUT 同向**——三窗一致才算真提升；仅 VAL 亮眼、TRAIN/HOLDOUT 拉胯 → 标 `overfit`、`confirmed:false`（仍推进，但不当成果）。
7. **记录**（每个实验都要）：
   - 追加 `research/results.tsv` 一行（§7）。
   - 写/更新 `wiki/experiments/<expId>.md`（§6）。
   - **回填**（§9）：有跨策略价值 → 追加到相关概念页「观察/待研究」小节，带 `[[<expId>]]` 指针；假设若来自某「待研究」，更新该条。
   - 追加 `wiki/log.md`：`## [YYYY-MM-DD] experiment | <expId> (<摘要>) val=<> holdout=<> <status> → 回填 [[<页>]]`。
8. 回到 1。

**HOLDOUT 只确认不选择**——绝不用于逐轮 keep/discard，否则数据泄漏、整个纪元作废。

**NEVER STOP（受预算约束）**：setup 之后，不要停下来问「要不要继续」——只要**免费额度未用尽且思路未穷**，就持续做实验。没思路了就想得更深：重读概念页「待研究」与「归一化横评」的强/弱对照、组合过往近似成功、尝试更大胆的跨概念拼装。
> **预算/执行器例外**（现实约束，优先于 NEVER STOP）：JQ 每日免费 60 分钟、超出烧积分、并发上限 2、CDP 会话可能失效。当 **`used ≥ --usage-limit`**、积分不足、或会话失效导致无法回测时——**停在干净 git 状态**，简报当前最优 + 剩余想法，告知人类「等次日免费额度重置 / 续额度 / 续 session」，**不空转、不烧不该烧的积分**。恢复后从当前最优继续。这不是「放弃」，是按预算分批推进。

---

## 完成/交接后

- 简报：本纪元跑了多少实验、keep 几个、当前分支最优 `objective(VAL)`/`objective(HOLDOUT)`、发现的规律与回填落点、命中多少 crash/DQ。
- 不要 `git commit` wiki 改动或 `results.tsv`，除非人类明确要求（`results.tsv` 本就不跟踪）。

---

## 红线（见 `research-schema.md` §10）

- 评测台冻结、HOLDOUT 只确认、raw 不可变、真实性红线（⚠ 不真实成交不得称「有效」）、可溯源、受控命名、概念页只追加不覆盖、冲突只标记不裁决。
