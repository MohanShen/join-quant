---
name: query-wiki
description: Answer questions against the join-quant wiki/ knowledge base (strategies + concepts) — comparisons, "which strategies use factor/concept X", performance filtering/ranking, or how a specific strategy works. Reads index.md → concept pages → strategy pages, cites [[pages]], honors the ⚠ inflated-backtest caveats, and optionally files reusable answers back into the wiki. Use when asked to query/search/compare/rank strategies or ask about the knowledge base.
---

# Query the strategy wiki

回答关于 `wiki/` 知识库的问题。遵循 `docs/wiki-schema.md` §7 查询工作流：**经 `index.md` 定位 → 阅读相关页 → 带引用作答 → 有价值的结论回填**。不要凭记忆答，一律以 wiki 页面与 frontmatter 为准。

## 必读
- `wiki/index.md` —— 目录入口（按概念分组 + 一句话 + 绩效）。
- `wiki/concepts/*.md` —— **跨策略问题的首选入口**（变体与差异表、绩效横评、关联概念、待研究）。
- `docs/wiki-schema.md` §7 查询、§2.1 因子分类、§ⒶⒸ 绩效警示约定。

## 流程
1. **分类问题**，选对入口：
   - *横比/「哪些策略…」/「区别…」* → 读对应**概念页**（多数答案已在其 变体与差异 / 绩效横评 里）。
   - *「某策略怎么做的」* → 读该**策略页**（`wiki/strategies/<postId8>_*.md`）。
   - *按因子/概念/绩效筛选或排名* → 用下方**结构化检索**（grep / frontmatter）。
2. **检索**：从 `index.md` 找到候选 `[[页]]`，读取。必要时用结构化检索缩小范围。
3. **作答**：简洁直答，**每条结论标 `[[页名]]` 引用**（可回溯到策略页或概念页）。
4. **回填（可选但鼓励）**：若结论有复用价值（如一次有用的横比、发现的规律），**追加**到最相关概念页的「观察」或「待研究」小节，并在 `wiki/log.md` 记一行 `## [YYYY-MM-DD] query | <问题摘要> → <落点页>`。回填只追加、不覆盖既有结论。

## 结构化检索配方（frontmatter 可 grep）
每个策略页 frontmatter 含 `concepts`、按角色分类的 `factors`（选股子类受控）、`stats`。例：
- 用某概念：`grep -rl "择时-RSRS" wiki/strategies/`
- 用某选股子类/信号：`grep -rl "动量:" wiki/strategies/`、`grep -rl "规模价值:" wiki/strategies/`
- 用某风控类型：`grep -rl "盈利保护\|排名止损\|破开盘价" wiki/strategies/`
- 按绩效筛选/排名：用 node 解析 frontmatter 的 `stats`（annualReturn/sharpe/maxDrawdown/periodLabel）过滤排序，例如「回撤<12% 且含 [[止损模块]] 的小市值」。
- 某概念有多少成员：概念页 frontmatter 的 `strategyCount`，或 `grep -rl "<概念>" wiki/strategies/`。

## 红线
- **尊重绩效警示**：标 ⚠/⚠⚠ 的策略（打板成交假设、五福/七星短窗口外推、e3914be0/537edfae 等失真）**绝不**当作可实现收益呈现；引用其绩效时必须带上警示。
- **区间不一致不可直接横比**绝对收益；横比时点明各自 `periodLabel`。
- **只用 wiki 内容作答**；wiki 未覆盖处如实说「知识库未记录」，必要时建议 `/ingest-strategy` 或读源码。
- 引用用 `[[页名]]`；回填只追加、不改既有结论、不改 raw `strategies/`。
