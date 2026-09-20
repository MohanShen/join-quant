---
type: 全A-H-low
universe: 全A
horizon: H-low
families: [[[三进兵]], [[套利]], [[红利低频]], [[网格]]]
familyCount: 4
memberStrategies: 15
bestFamily: [[网格]]
bestFamilyObjective: 0.1411
intradayDependent: true
generatedBy: utils/wiki-type-build.js
updatedAt: 2026-09-20
---

# 全A-H-low — strategy type

**由 `utils/wiki-type-build.js` 生成，勿手改。** 家族归属由基类源码（universe）+ 实测换手
（horizon）导出，不读正文叙述。

## 成员家族

| 家族 | 成员数 | bestObjective | 实测换手 | 盘中依赖 |
|---|---|---|---|---|
| [[网格]] | 3 | 0.1411 | 0.010291 | 否 |
| [[红利低频]] | 7 | 0.1348 | 0.016646 | ⚠ 是 |
| [[三进兵]] | 4 | -0.09 | 0.007809 | 否 |
| [[套利]] | 1 | DQ | 0.02044 | ⚠ 是 |

## 整合回合（见 `docs/consolidation-plan.md` §4）

> ⚠ **合并必然抬高夏普**：相关性 < 1 时混合的夏普机械地高于单腿，而闸门**就是**夏普阈值。
> 本仓库已两次实测到这点——[[七星高照]] 混合 sharpe 3.17 高于两腿（2.85 / 1.60）且波动低于两腿；
> [[红利低频]] 的双因子合取回报 23.41% 对两腿之和 11.75%。所以整合候选的判据是
> **超过本类型最好的那个成员**，不是过闸；并须报出「多少来自分散化」。

_（本节由整合回合追加；当前无记录。）_
