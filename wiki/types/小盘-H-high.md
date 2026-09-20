---
type: 小盘-H-high
universe: 小盘
horizon: H-high
families: [[[ETF动量]], [[七星高照]]]
familyCount: 2
memberStrategies: 38
bestFamily: [[ETF动量]]
bestFamilyObjective: 0.5267
intradayDependent: true
generatedBy: utils/wiki-type-build.js
updatedAt: 2026-09-20
---

# 小盘-H-high — strategy type

**由 `utils/wiki-type-build.js` 生成，勿手改。** 家族归属由基类源码（universe）+ 实测换手
（horizon）导出，不读正文叙述。

## 成员家族

| 家族 | 成员数 | bestObjective | 实测换手 | 盘中依赖 |
|---|---|---|---|---|
| [[ETF动量]] | 27 | 0.5267 | 0.16112 | ⚠ 是 |
| [[七星高照]] | 11 | 0.1871 | 0.133 | ⚠ 是 |

## 整合回合（见 `docs/consolidation-plan.md` §4）

> ⚠ **合并必然抬高夏普**：相关性 < 1 时混合的夏普机械地高于单腿，而闸门**就是**夏普阈值。
> 本仓库已两次实测到这点——[[七星高照]] 混合 sharpe 3.17 高于两腿（2.85 / 1.60）且波动低于两腿；
> [[红利低频]] 的双因子合取回报 23.41% 对两腿之和 11.75%。所以整合候选的判据是
> **超过本类型最好的那个成员**，不是过闸；并须报出「多少来自分散化」。

_（本节由整合回合追加；当前无记录。）_
