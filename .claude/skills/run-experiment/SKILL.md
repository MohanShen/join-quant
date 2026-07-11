---
name: run-experiment
description: Run the join-quant autoresearch loop — generate/mutate a strategy from the wiki knowledge base, backtest it on the frozen JoinQuant harness (train/val/holdout), keep or discard by the objective, and write learnings back to wiki/experiments + concept pages. Use when asked to run an experiment, start/continue the research loop, propose or improve a strategy, or do autoresearch on strategies.
---

# Run autoresearch experiment(s)

驱动 `research/` 自主策略研究循环：从 `wiki/` 知识库提假设 → 变异策略 → 冻结评测台回测 → keep/discard → 回填知识。
你既是研究者，也是知识库的记账员。**权威规则见 `docs/research-schema.md` 与 `research/program.md`，冲突以它们为准**——本技能是入口，不复述全部细节。

## 必读（每次开始前）
1. `research/program.md` —— 研究循环 agent 指令（**主流程**）。
2. `docs/research-schema.md` —— 结构与规则（实验页/账本/keep-discard/回填格式，**权威**）。
3. `research/harness.md` —— 冻结评测台常量（三窗区间/费率/滑点/objective 门槛）。**只读**。
4. `docs/wiki-schema.md` §2.1 —— 受控因子词表（变异空间边界）。
5. `wiki/index.md` + 相关 `wiki/concepts/*.md` —— 假设来源（尤其各概念页「待研究/空白」）。

## 前置检查
- CDP Chrome 在跑（见根 `CLAUDE.md`）；**登录/预算用 statistics API 查**：`curl -s http://localhost:9225/json/version` 通，`/algorithm/index/statistics` 返回 `duration.{used,free}`（不用 `index.js status`）。
- **预算**：`used < --usage-limit`（默认 55=仅免费 60 分钟内；超出烧积分）。`used ≥ limit` → 停，等次日重置。
- 在实验分支上：`research/<tag>`（新纪元先 `git checkout -b research/<tag>`）。
- `research/results.tsv` 存在（不存在则建表头；该文件 git 不跟踪）。

## 回测命令（唯一执行器 = Pipeline 2，已加固）
```bash
JQ_USAGE_LIMIT=55 node utils/strategy-post-backtest.js research/candidates/<expId>.py "<expId>" --window <train|val|holdout>
```
- `--window` 经 URL 参数强制映射到 `harness.md` 冻结区间；基础资金 ¥1,000,000。UI 选择器已修（`#algo-save-button`/`#validate-button`），窗口自动核验。
- 读输出末尾机器可读行（10 列，`harness.md` §5）：
  `SUMMARY\t<window>\t<start>\t<end>\t<days>\t<total%>\t<annual%>\t<sharpe>\t<maxdd%>\t<status>`
  `annual%` 已由执行器年化；直接用它算 `objective`。
- `status`：`completed`（可记账）/ `window-mismatch`（区间不符，**不得记账**，重跑）/ `slow-skipped`（超安全上限被取消）/ `USAGE-STOP`（预算到顶，停）/ `failed`/无 SUMMARY（crash）。

## 单个实验（严格按序）
1. **提假设**：优先从概念页「**归一化绩效横评**」的强/弱对照出发（同一区间下谁过门槛、赢家的因子构成），或「待研究/空白」。写一句可证伪的话，溯源页记入实验页 `sourceRefs`。
2. **变异**：从当前分支最优 candidate 复制为 `research/candidates/<expId>.py`（`expId=<tag>-<NNN>` 递增），在四个因子槽位（选股/择时/风控/仓位）内**小步**改动（改一处，别多改），只用受控词表内的信号，朝赢家配方（低开小市值+国九强过滤+止损）靠拢。
   - **首个 `<tag>-000` = 已归一化的过门槛策略源码 + 冻结成本 override**（见 `program.md` Setup 5；不要用裸 `strategy_template.py`——jul4 已证其全 DQ）。`strategy_template.py` 仅作从头造概念的脚手架。
3. `git commit` candidate 源码。
4. **回测 TRAIN + VAL**：分别 `--window train`、`--window val`。按 `harness.md` §4 算：`gate = sharpe(VAL)≥2.5`；`objective(VAL)=annualReturn−maxDrawdown`（小数），gate 不过记 `DQ`。
5. **判定**：
   - `DQ` 或 `objective(VAL) ≤ 当前分支最优` → **discard**：`git reset` 回上个 keep。
   - `> 当前最优且非 DQ` → **provisional keep**：推进分支，**再跑一次 `--window holdout`** 确认。holdout 未失格且未显著劣于 val → `confirmed:true`；否则标 `flags:[overfit]`、`confirmed:false`（仍推进，但明确标注、不当成果）。
6. **记账**（每个实验都要）：
   - 追加 `research/results.tsv` 一行（7 列，见 schema §7）。
   - 写/更新 `wiki/experiments/<expId>.md`（schema §6 模板）。
   - **回填**（schema §9）：有跨策略价值 → 追加到相关概念页「观察/待研究」小节，带 `[[<expId>]]` 指针；假设若来自某「待研究」，更新该条。
   - 追加 `wiki/log.md`：`## [YYYY-MM-DD] experiment | <expId> (<摘要>) val=<> holdout=<> <status> → 回填 [[<页>]]`。

## 循环（受预算约束的 LOOP FOREVER）
按 `program.md` 连续做实验：只要**免费额度未用尽且思路未穷**就不停下问「要不要继续」。**预算例外**（优先）：`used ≥ --usage-limit`、积分不足、或会话失效时——停在干净 git 状态，简报当前最优+剩余想法，告知人类「等次日重置/续额度/续 session」，不空转、不烧不该烧的积分。恢复后从当前最优继续。

## 完成后简报
本纪元跑了多少实验、keep 几个、当前分支最优 `objective(VAL)`/`objective(HOLDOUT)`、发现的规律与回填落点、多少 crash/DQ/window-mismatch。
不 `git commit` wiki 改动或 `results.tsv`，除非人类明确要求。

## 红线（见 `research-schema.md` §10 / `harness.md`）
- **评测台冻结**：objective/门槛/三窗/费率滑点不可改；改动即新纪元。
- **HOLDOUT 只确认不选择**：任何用 holdout 调参 = 数据泄漏，纪元作废。
- **预算优先**：`used ≥ --usage-limit` 就停；不为「跑满循环」烧积分。停≠放弃，是按天分批。
- **零滑点高估**：高换手/微盘/打板类 keep 必标「零滑点高估」，不当可实现收益（`harness.md` §2）。
- **真实性红线**、**raw 不可变**、**受控命名**、**概念页只追加不覆盖、冲突只标记**——与 ingest/query 一致。
