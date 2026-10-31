---
family: 突破ATR趋势跟踪
concepts: []
edge:
  - name: Bollinger upper-band breakou
    kind: unknown
    claim: "注册时未验证。screener 读源码得出的机制描述：Bollinger upper-band breakout on 6 ETFs, ATR stops, 2%-risk sizing（入场：open (run_daily time='open'), buys at day_open）。这是**代码读出来的机制**，不是测量过的 edge"
    test: "待定——注册时本族没有任何实验。第一步应是一次消融：关掉上面 claim 里的核心信号，看 sharpe 是否下降"
    status: proposed
    evidence: "无。来源是 screen/qita/verdicts.json 的 screener 判定（confidence: high），依据为 L23-30 fixed 6-ETF pool; L326-329 entry needs all four of close>upper band, previous day inside the band, band rising, close>MA60 — a per-asset event, never a cross-sectional rank; L335 entry at current_data[symbol].day_"
base: [[e79e9884_基于上一版本进行了适当调整，增加其攻击性]]
baseBasis: "本族注册时只有 1 名成员，base 即该成员。单成员/无血缘的族 family-match 不会匹配到新成员（它对 base 做代码 Jaccard），新成员只能靠人发现"
universe: ETF
universeBasis: "screener 判定为 ETF；直接映射"
universeAt: 2026-10-31
bestVariant: [[e79e9884_基于上一版本进行了适当调整，增加其攻击性]]
bestObjective: 0.2007
bestObjectiveEpoch: 9
memberCount: 1
sources: { normalized: 1, study: 0, enhance: 0 }
realism: "⚠ **注册时零研究**：没有 study、没有 enhance、没有可成交性测量。下面只有 screener 的读码观察。 ‖ 机制：Bollinger upper-band breakout on 6 ETFs, ATR stops, 2%-risk sizing；入场 open (run_daily time='open'), buys at day_open。 ‖ ⚠ 本族成立于一次**筛选**而不是一次测量：唯一的台上事实是 1 个成员的 epoch-9 normalize 行（objective 0.201，sharpe 1.54）。过闸不等于有机制。"
# ⚠ realizability 故意未设：从未测量。未知 BLOCK 而非 PERMIT，所以本族在 exit gate 上显示 blocked，
# 这是正确状态。键整个省略而不是写成空值（空值会被 frontmatter.field() 读成下一行）。
status: active
updatedAt: 2026-10-31
---

# 突破ATR趋势跟踪

**注册于 2026-10-31**（人工决定：家族划分不必过细，单成员不构成阻碍）。来源是 `screen/qita` 那轮筛选——`其他` catch-all 桶里 30 本过闸的书经三个 `post-screener` 读源码后给出的 `NEW:` 提案之一。

⚠⚠ **注册时本族的全部证据是一次 screener 判定（confidence: high）加 1 行 epoch-9 normalize 台账。** 没有任何实验。`edge` 是 `proposed`，`realizability` 未设，因此本族在 `/run-family` 的 exit gate 上是 blocked——那是正确状态，不是待办。

⚠ **每个新家族等于一次新的 VAL 配额**（VAL 预算的键是 (family, bench)）。本批共注册 12 族，即本台的一次性验证额度从 14 增加到 26。这是 2026-10-31 的人工决定，记在此处以便将来复盘。

## 1. 基类 (base archetype)

`e79e9884`：Bollinger upper-band breakout on 6 ETFs, ATR stops, 2%-risk sizing。入场 open (run_daily time='open'), buys at day_open。

screener 的依据：L23-30 fixed 6-ETF pool; L326-329 entry needs all four of close>upper band, previous day inside the band, band rising, close>MA60 — a per-asset event, never a cross-sectional rank; L335 entry at current_data[symbol].day_open; L39-40/L340 initial stop = entry - 2.5*ATR(14), L217 trailing exit when highest-close falls 4*ATR; L218 MA20-rollover exit; L345-354 size = 2% of equity / per-share risk, cap

## 2. 变体 (variants)

（空——注册时零实验。）

## 3. 家族内绩效横评 (auto)

| 排名 | 变体 | obj | sharpe | annual% | maxDD% | gate | epoch |
|---|---|---|---|---|---|---|---|
| **1** | **[[e79e9884_基于上一版本进行了适当调整，增加其攻击性]]** | 0.2007 | 1.54 | 28.45 | 8.38 | ✅ | 9 |

*1 gate-pass / 1 members. 快照 2026-10-31（TRAIN 2022–2023, 冻结零滑点 ⚠）。由 `wiki-family-build.js` 生成，勿手改。*

## 4. 待研究 / 空白 (research gaps)

- **[第一步] 机制消融**：跑 `edge.test`，关掉核心信号看 sharpe。在此之前 `edge` 不得被当作事实引用。
- **[阻塞 exit gate] realizability 未测**：需要一次 liq 跑在本书自己的可行性下限上。先验不能代替测量（[[大小盘轮动]] 的地板是惰性的，[[ETF溢价]] 的是 8.44→1.10）。
- **[⚠ 不要先花 VAL]** 与 [[资产配置]] 同理：在 `edge` 仍为 `proposed`、realizability 未测时花掉本族唯一一次验证，确认的是一个**水平数字**而不是机制。顺序：消融 → liq → 才考虑 VAL。

## 5. 沿革 (provenance)

| 时间 | 事件 |
|---|---|
| 2026-10-31 | 注册。来源 `screen/qita/verdicts.json`，screener confidence high。零实验。 |

## 6. 研究问答 (study-log)

（空）
