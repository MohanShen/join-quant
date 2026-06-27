---
name: ingest-strategy
description: Ingest one or more join-quant strategy .py files into the wiki/ knowledge base, following docs/wiki-schema.md. Use when asked to ingest, summarize, or add strategies to the wiki / knowledge base, or to backfill strategies/ into wiki/. Writes strategy pages, updates concept pages, index.md, and log.md.
---

# Ingest strategy → wiki

把 `strategies/` 里的策略源码 ingest 进 `wiki/` 知识库。你是知识库的**唯一维护者**，负责全部记账：摘要、交叉链接、建索引、去重、标记矛盾、写日志。**绝不手写结论式正文**——一切按规则从源码生成。

## 必读（每次开始前）
1. `docs/wiki-schema.md` —— 知识库结构与维护规则（**权威**，冲突以它为准）。
2. `docs/push-format.md` —— 忠实翻译的逐段规范（用于策略页「忠实翻译」段）。
3. `wiki/index.md` 与相关 `wiki/concepts/*.md` —— 了解已有内容，避免重复/分叉。

## 输入
- 一个或多个策略文件路径（`strategies/<…>.py`）。未指定时，向用户确认要 ingest 哪些（或哪个聚类）。
- 绩效数据来自 `data/fetch-manifest.json` 中对应 `postId` 的 `stats`；manifest 没有则在策略页标「绩效未公开」。

## 流程（对每个文件，严格按序）
1. 读源码，解析头部元数据（postId / backtestId / title / 聚宽原帖 / 作者）与代码行数。
2. 查 manifest：若该条目带 `duplicateOf` → **不建页**，仅在 `wiki/log.md` 追加 `skip-dup` 一行，跳过。
3. 按 `wiki-schema.md` §3.1 写策略页 `wiki/strategies/<postId前8位>_<安全标题>.md`：
   - 「忠实翻译」段**严格套用** `push-format.md`：选股池/仓位分配/止损/风控；
   - 均线周期必须从代码读取（如 `g.short_d`/`g.long_d`），不硬编码；
   - 被注释掉/未启用的模块不写。
4. 判定涉及的**规范概念**（`wiki-schema.md` §2 受控词表）与**因子**（§2.1 四角色：选股/择时/风控/仓位，选股按子类受控）。填入 frontmatter 的 `concepts` 与 `factors`。若翻译已产出「概要要素行」（`push-format.md` §2），优先直接复用其 选股/择时/风控/概念 字段，避免二次推断。出现新概念或新选股子类：先登记词表，再使用。
5. 对每个涉及概念，**追加**（不覆盖）到其概念页的「变体与差异」「绩效横评」，刷新 `strategyCount`/`updatedAt`；并在策略页「涉及概念」用 `[[概念名]]` 双向链接。
6. 更新 `wiki/index.md`（策略节 + 受影响概念节）。
7. 追加 `wiki/log.md`：`## [YYYY-MM-DD] ingest | <title> (<postId8>) → concepts: <…>`。
8. 发现与既有结论矛盾 → 写进该策略页「矛盾」小节 + `log.md` 标注，**留待人工裁决，不改既有结论**。

## 完成后
- 简报：新建/更新了哪些策略页、概念页，命中多少 `skip-dup`，发现哪些矛盾。
- 不要 `git commit`，除非用户明确要求。

## 红线（见 wiki-schema.md §9）
- 绝不修改 `strategies/`（raw 不可变）。
- 概念页只追加、不覆盖；冲突只标记、不裁决。
- 概念命名一律走受控词表，杜绝同义分叉。
