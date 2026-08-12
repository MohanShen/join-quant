# 交接：多因子ML 家族解剖（resume note）

> ## ✅ 已完成（2026-08-11）——本文件的任务已结束，可删
>
> `/run-study 多因子ML` 已跑完并**收口**：7 个问题全部 answered（q-1~q-6 + q-audit），
> 结论写回 `wiki/families/多因子ML.md`（§1/§2/§4/§6 + frontmatter `realism:`），
> 账本 `study/多因子ML/findings.tsv` 8 行。本轮花费 JQ 预算 **31/60 分钟**。
> 下面第 1、2 节保留作为**背景与已查证结论**；第 3、4 节的「起跑前状态/怎么跑」已过期。
>
> **仍未决**（与本族结论不冲突）：2 个 slow-skipped 成员 `b8a7451f` / `914d5724`
> 从未跑出结果（被 20 分钟安全帽取消，非终态），要跑需 `--max-poll-min` 调大。

> 写于 2026-08-11。给下一个在 **仓库目录内** 启动的会话（`/run-study` 是项目技能，
> 只在 `cd /Users/mshen/join-quant` 后启动的会话里可用）。

## 1. 结论先行：base 已定

`多因子ML` 的 `base:` 长期是未填占位符 `[[<postId8>_<代表基类>]]`，且唯一过闸的成员
`a30641fb` 已被 `c374bf5` **改判到 [[小市值]]**（它其实是微盘日内剥头皮，不是多因子/ML）。
2026-08-11 把家族剩余 12 个从未归一化的成员补跑 TRAIN 归一化后，选出新 base：

| 成员 | sharpe | objective | gate |
|---|---|---|---|
| **d02cde29_高质量稳定上涨** | **3.21** | **0.4737** | ✅ pass |
| 775faa4e_信息熵策略 | 0.47 | DQ | fail |

**已改动**（未 commit）：
- `wiki/families/多因子ML.md` frontmatter：`base:`/`bestVariant:` → `[[d02cde29_高质量稳定上涨]]`，
  `bestObjective: 1.1706 → 0.4737`，`updatedAt → 2026-08-11`
- `wiki/strategies/d02cde29_高质量稳定上涨.md`：`familyRole: variant → base`
- 删除 `study/多因子ML/baseline.py`（那是 a30641fb 的旧快照，属于别的家族了）
  → **Setup 会从新 base 重新快照**，不要复用旧文件。

## 2. ✅ 已查证（2026-08-11）：8 个 `compile-error` **不是权限问题**，终态判定成立

12 个补跑的结果：**2 normalized / 8 compile-error / 2 slow-skipped**。

原假设是「账号缺 jqfactor 付费数据权限 → 8 个被误判永久剔除」。**该假设已被证伪**：

- 新 base `d02cde29` 自己就 `from jqfactor import *` 并且**跑完了**；`914d5724` 也 import jqfactor，
  只是被 20 分钟安全帽取消。`77e78b06` 的 `import torch` 也过了（它死在第 118 行，远在 import 之后）。
- 8 个全部**真的启动了回测**（`回测失败，实际耗时 00分08秒` 一类），是**运行期异常**，不是编译/权限拒绝。
  `compile-error` 这个标签名有误导性。

逐条实证（从 JQ 历史里读回 traceback，**零回测预算**：`/algorithm/backtest/error?backtestId=..&ajax=1`；
每条都用该 algorithm 自己保存的 `# postId:` 头核对过身份，行号与源码逐行对上）：

| 成员 | 真实死因 | 性质 |
|---|---|---|
| `5a5ba567` | `from pandas.stats.api import ols` → ModuleNotFoundError | pandas 0.20 删掉的 API — 代码腐烂 |
| `c748b9d5` | `range(1,13,12/f)` → `'float' object cannot be interpreted as an integer` | Py2 整除腐烂 |
| `796c6f98` | `df.sort(columns=...)` → AttributeError | pandas 0.20 改名 `sort_values` — 代码腐烂 |
| `b0e7b728` | `drop_duplicates(take_last=True)` → TypeError | pandas 0.17 删掉的参数 — 代码腐烂 |
| `26b52dca` | `read_file('DateStockDict.pkl')` → 文件不存在 | 依赖原作者研究目录的外部 .pkl — 克隆后天然跑不了 |
| `77e78b06` | `read_file('inference_config.pkl')` → 文件不存在 | 同上（ML 模型配置） |
| `c18e0923` | `TabError` | 真语法错 |
| `5a127075` | `duyi_df.loc[today,'op']` → `KeyError: [2022-01-04] not in index` | **唯一可能与窗口有关**，见下 |

**结论**：这 8 个作为「克隆原样」确实不可跑，终态剔除是对的 → **base 选择 `d02cde29` 不受影响**。

剩下的真·未知只有 2 个 slow-skipped（`b8a7451f` / `914d5724`，被安全帽取消而非失败）——
它们才是可能翻盘 `objective 0.4737` 的候选，想跑要 `--max-poll-min` 调大。
另：`5a127075` 的 KeyError 落在 TRAIN 起点首个交易日，换窗口/补数据也许能跑，但优先级低于上面两个。

> 前 4 条是**机械可修**的（pandas 现代化）。但那等于改写克隆源码 = 改变被测对象，
> 属于归一化口径决策，不要顺手做进 study 循环。
>
> 顺带记一笔工程问题：账本只写 `compile-error`，**把异常正文丢了**，所以才要事后回捞。
> 以后值得把 exception 一行存进 `harness/normalize-train.tsv`。

被 20 分钟安全帽取消的 2 个（可重试，非终态）：
`b8a7451f_实战模型量化转化`、`914d5724_中证500增强`。想跑要 `--max-poll-min` 调大。

## 3. 起跑前状态

- 分支：`remote-cdp-mode`（study 的分支门禁已移除，**在当前分支跑即可**，不必切 `study/all`）
- 已 commit：`a4e74c0` 远程 CDP 模式；**未 commit**：分支门禁移除 + 上面第 1 节的 base 改动
- CDP：`JQ_EXEC_MODE=remote`，Chrome 在 Windows QMT 服务器上，隧道**按需自动拉起**
  （查状态：`./scripts/cdp-tunnel.sh status`）
- 预算：2026-08-11 已重置（`used=0 free=60`）。前一天补跑归一化花了 45 分钟。
- `study/manifest.json` / `findings.tsv` / `questions.json` 都是 gitignore 的瞬态文件，本 clone 里没有，
  Setup 会重建。
- **另有 1 个只在 `origin/study/all` 上的家族页 `套利.md`**（提交 `27cbbb8`，唯一未并入 main 的提交）。
  只做 多因子ML 不受影响；将来跑批量遍历前要先并进来，否则 `套利` 会被静默漏掉。

## 4. 怎么跑

```bash
cd /Users/mshen/join-quant
tmux new -s study                 # 关终端不中断
node utils/jq-budget.js           # 确认 used 接近 0
claude                            # 会话必须从仓库目录起，技能才加载
# 会话内：
/run-study 多因子ML
```

## 5. 记账时的注意

- 新 base `objective 0.4737` 比家族旧的 `1.1706` 弱很多，而那个 1.1706 属于一条
  **已被改判走**的策略。本族结论的量级会相应偏小，别和旧数字对比。
- 家族页 `realism:` 仍是 `"<⚠ 待人工填写>"`，§4 待研究为空 —— questioner 没有人写的空白清单可依，
  只能从 §1/§2 和成员页推问题。
- 红线不变：评测台冻结、**2025+ OOS 永不碰**、一次一处、§2/§6 只追加不覆盖。
