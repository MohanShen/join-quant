---
family: 小盘ETF双轨切换
concepts: []
edge:
  - name: 小盘离散度择时：偷鸡买低价小市值10只，摸狗退到ETF动
    kind: unknown
    claim: "注册时未验证。screener 读源码得出的机制描述：小盘离散度择时：偷鸡买低价小市值10只，摸狗退到ETF动量（入场：daily 9:30 (consistent), 止损/补跌加仓 14:00）。这是**代码读出来的机制**，不是测量过的 edge"
    test: "待定——注册时本族没有任何实验。第一步应是一次消融：关掉上面 claim 里的核心信号，看 sharpe 是否下降"
    status: proposed
    evidence: "无。来源是 screen/qita/verdicts.json 的 screener 判定（confidence: medium），依据为 Single capital pool with a TWO-STATE router, not parallel sleeves: DDDD() takes the 20 smallest circulating-cap names of 399101, normalises their 1-day returns and returns (variance, mean); consistent() sets g.type='偷鸡' "
base: [[0d1bbe83_年化51%的晴雨双轨：小盘游击+ETF防御]]
baseBasis: "本族注册时只有 1 名成员，base 即该成员。单成员/无血缘的族 family-match 不会匹配到新成员（它对 base 做代码 Jaccard），新成员只能靠人发现"
universe: 小盘
universeBasis: "screener 判定为 other；由书中的指数/标的代码推断为 小盘"
universeAt: 2026-10-31
bestVariant: [[0d1bbe83_年化51%的晴雨双轨：小盘游击+ETF防御]]
bestObjective: 0.7266
bestObjectiveEpoch: 9
memberCount: 1
sources: { normalized: 1, study: 0, enhance: 0 }
realism: "⚠ **注册时零研究**：没有 study、没有 enhance、没有可成交性测量。下面只有 screener 的读码观察。 ‖ 机制：小盘离散度择时：偷鸡买低价小市值10只，摸狗退到ETF动量；入场 daily 9:30 (consistent), 止损/补跌加仓 14:00。 ‖ ⚠ 本族成立于一次**筛选**而不是一次测量：唯一的台上事实是 1 个成员的 epoch-9 normalize 行（objective 0.727，sharpe 2.85）。过闸不等于有机制。"
# ⚠ realizability 故意未设：从未测量。未知 BLOCK 而非 PERMIT，所以本族在 exit gate 上显示 blocked，
# 这是正确状态。键整个省略而不是写成空值（空值会被 frontmatter.field() 读成下一行）。
status: active
updatedAt: 2026-10-31
---

# 小盘ETF双轨切换

**注册于 2026-10-31**（人工决定：家族划分不必过细，单成员不构成阻碍）。来源是 `screen/qita` 那轮筛选——`其他` catch-all 桶里 30 本过闸的书经三个 `post-screener` 读源码后给出的 `NEW:` 提案之一。

⚠⚠ **注册时本族的全部证据是一次 screener 判定（confidence: medium）加 1 行 epoch-9 normalize 台账。** 没有任何实验。`edge` 是 `proposed`，`realizability` 未设，因此本族在 `/run-family` 的 exit gate 上是 blocked——那是正确状态，不是待办。

⚠ **每个新家族等于一次新的 VAL 配额**（VAL 预算的键是 (family, bench)）。本批共注册 12 族，即本台的一次性验证额度从 14 增加到 26。这是 2026-10-31 的人工决定，记在此处以便将来复盘。

## 1. 基类 (base archetype)

`0d1bbe83`：小盘离散度择时：偷鸡买低价小市值10只，摸狗退到ETF动量。入场 daily 9:30 (consistent), 止损/补跌加仓 14:00。

screener 的依据：Single capital pool with a TWO-STATE router, not parallel sleeves: DDDD() takes the 20 smallest circulating-cap names of 399101, normalises their 1-day returns and returns (variance, mean); consistent() sets g.type='偷鸡' when variance < 0.02 and mean > 0, else '摸狗'. 偷鸡 = choose_stocks -> filter_high_price_stock (last price < 10) + get_peg (roe>0.15, roa>0.10, order_by market_cap.asc), 10 slots, hel

## 2. 变体 (variants)

（空——注册时零实验。）

## 3. 家族内绩效横评 (auto)

| 排名 | 变体 | obj | sharpe | annual% | maxDD% | gate | epoch |
|---|---|---|---|---|---|---|---|
| **1** | **[[0d1bbe83_年化51%的晴雨双轨：小盘游击+ETF防御]]** | 0.7266 | 2.85 | 89.75 | 17.09 | ✅ | 9 |

*1 gate-pass / 1 members. 快照 2026-10-31（TRAIN 2022–2023, 冻结零滑点 ⚠）。由 `wiki-family-build.js` 生成，勿手改。*

## 4. 待研究 / 空白 (research gaps)

- **[第一步] 机制消融**：跑 `edge.test`，关掉核心信号看 sharpe。在此之前 `edge` 不得被当作事实引用。
- **[阻塞 exit gate] realizability 未测**：需要一次 liq 跑在本书自己的可行性下限上。先验不能代替测量（[[大小盘轮动]] 的地板是惰性的，[[ETF溢价]] 的是 8.44→1.10）。
- **[⚠ 不要先花 VAL]** 与 [[资产配置]] 同理：在 `edge` 仍为 `proposed`、realizability 未测时花掉本族唯一一次验证，确认的是一个**水平数字**而不是机制。顺序：消融 → liq → 才考虑 VAL。

## 5. 沿革 (provenance)

| 时间 | 事件 |
|---|---|
| 2026-10-31 | 注册。来源 `screen/qita/verdicts.json`，screener confidence medium。零实验。 |

## 6. 研究问答 (study-log)

（空）
