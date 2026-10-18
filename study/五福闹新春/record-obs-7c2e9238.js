#!/usr/bin/env node
/**
 * record-obs-7c2e9238.js — step-0 EARLY EXIT log for the new member 7c2e9238.
 *
 *   node -e "require('./study/五福闹新春/record-obs-7c2e9238.js')"
 *
 * ⚠ NO BACKTEST RAN AND NONE WILL. This is the step-0 case the skill names: a close fork of a
 * settled mechanism, landing inside the intraday-execution-timing axis q-e8-2 measured and the
 * gatekeeper then CLOSED. Everything below is a free read.
 *
 * Every figure was taken from the LEDGER / the stored base curve, and the attribution was
 * re-verified by this recorder independently of the orchestrator's report:
 *   - harness/normalize-train.tsv row for 7c2e9238 (epoch 8):
 *       total 98.10 / annual 40.81 / sharpe 1.67 / maxdd 15.67 / objective 0.2514 / gate pass
 *   - baseline-e6 (epoch 6, §1): 0.3755 / 51.51 / 1.99 / 13.96 / total 129.29
 *   - Jaccard of normalized code lines vs study/五福闹新春/baseline-e6.py = 0.838
 *     (orchestrator reported 0.832 — same conclusion, a normalization difference, not a dispute)
 *   - function-set diff: EXACTLY four added (check_intraday_trend / execute_buy_with_trend /
 *     check_pending_buys_trend / force_buy_pending); the two "missing" ones are set_slippage /
 *     set_commission, i.e. the injected OVERRIDE's wrappers present only in our normalized
 *     snapshot — an artifact of comparing a normalized copy with a raw file, NOT a missing pin
 *   - all seven base knobs byte-identical; below_count >= 3 unchanged; the three core run_daily
 *     lines still at 13:10
 *   - the NEW mechanism carries two knobs of its own (L180 g.trend_lookback_minutes = 30,
 *     L181 g.trend_slope_threshold = 0.001), which are NOT swept by anything
 *   - sibling rows re-read from the ledger: aaee3035 0.2533 (sharpe 1.71, pass),
 *     5ac906ea 0.2552 (sharpe 1.47, FAIL)
 */
const rq = require('../../utils/research-queue');

rq.recordFinding('五福闹新春', {
  qId: 'obs-7c2e9238',
  type: 'observational / ledger-read（零回测——本条不花任何回测分钟，仅为 step-0 登记）',
  component_or_param:
    '新成员 [[7c2e9238_五福5.2修改byClaudeV4版本]]' +
    '（strategies/2026-10-18_五福5_2修改by_Claude_V4版本-7c2e9238.py，ledger epoch 8）' +
    '相对 study/五福闹新春/baseline-e6.py 的**唯一机制差异**：13:10 的买入不再无条件成交——' +
    '每只目标 ETF 须先过 check_intraday_trend（近 30 分钟分钟收盘的线性回归斜率，除以均价归一化为 %/min，' +
    '> g.trend_slope_threshold = 0.001 才算上涨；分钟数据缺失或异常则默认上涨、有效根数 < 5 则默认非上涨）；' +
    '判定为上涨才立即买入，否则进 g.pending_buy_etfs，于 13:40 / 14:10 / 14:40 由 check_pending_buys_trend 复判，' +
    '并在 14:55 由 force_buy_pending 无条件强制买入；现金按「本次买入 + 仍待买」只数均分，' +
    '故延后名字的现金是被预留而非改派（holdings_num = 1 下即「这一只不买就持现金等到最晚 14:55」）。' +
    '函数集恰好新增四个（check_intraday_trend / execute_buy_with_trend / check_pending_buys_trend / ' +
    'force_buy_pending），无其它增删',
  metric_delta:
    '**以下全部引自 harness/normalize-train.tsv，非转述**：7c2e9238 @ epoch 8 — ' +
    'total 98.10 / annual 40.81 / sharpe 1.67 / maxdd 15.67 / objective **0.2514** / gate **pass** ‖ ' +
    'baseline-e6（§1，epoch 6）— total 129.29 / annual 51.51 / sharpe 1.99 / maxdd 13.96 / objective 0.3755 ' +
    '⇒ Δobjective **−0.1241**、Δannual −10.70pp、Δsharpe **−0.32**、ΔmaxDD **+1.71**。' +
    '与本族实测噪声地板之比：0.1241 / 0.0308 = **4.03×**（q-e8-2）。' +
    '同轴三个 fork（均为 ledger epoch 8 行）：7c2e9238 0.2514 / sharpe 1.67 pass ‖ ' +
    'aaee3035 0.2533 / sharpe 1.71 pass（13:10 算分、14:10 卖、14:20 买）‖ ' +
    '5ac906ea 0.2552 / sharpe 1.47 **gate FAIL**（全部 13:12 + 第二道止损）——' +
    '三者极差 0.0038（= 地板的 0.12×），对 base 的差额 −0.1241 / −0.1222 / −0.1203。' +
    '归因证据（零成本、recorder 独立复核）：Jaccard(normalized code lines, baseline-e6) = **0.838**；' +
    'base 的七个旋钮逐字相同（holdings_num 1 / score_threshold_ratio 0.9 / max_weak_days 20 / ' +
    'r2_threshold 0.4 / volume_threshold 1.8 / fixedStopLossThreshold 0.95 / ' +
    'global_threshold_divisor 20000）、走弱进入阈值 below_count >= 3 未动、' +
    'afternoon_routine / sell_routine / buy_routine 三条 run_daily 仍在 **13:10**',
  window:
    'train 2022-01-01→2023-12-31（ledger 行，729 天请求窗口）；' +
    '⚠ 本条未运行任何回测，7c2e9238 的数字是 normalize 阶段已付过的测量，base 侧取 §1 的既有快照',
  finding:
    '新成员是 base 加**恰好一条**机制：把 13:10 的无条件买入换成「盘中趋势确认后才买、最晚 14:55 强制买」。' +
    '它在本台上 objective **0.2514**（sharpe 1.67，仍过 1.5 闸），对 baseline-e6 的 0.3755 是 **−0.1241**，' +
    '即本族实测执行分钟噪声地板 0.0308 的 **4.03×** ⇒ 这不是抖动，而是一个真实且可观的损失。' +
    '之所以可归因到这一条机制，是因为它的调参面与 base 逐字相同：七个旋钮、走弱进入阈值 below_count >= 3、' +
    '以及三条核心 run_daily 的 13:10 全部未动，函数集只多出那四个支撑延后买入的函数，' +
    'Jaccard 0.838 ⇒ 这是一次**别人出钱做完的受控实验**。' +
    '⚠ 自由参数仍在该机制内部（30 分钟回看、0.001 %/min 斜率阈值），所以被证伪的是「这一族规则在其作者选的参数上」，' +
    '不是「任何延后入场规则在任何参数上」。' +
    '方向上它与 q-e8-2 测得的渠道一致：该书本来就把成交分钟喂进信号' +
    '（price_series = append(hist_closes, current_price) 与放量外推乘子），' +
    '而延后入场把这个暴露从「固定 2 分钟位移」放大成「逐日 0–105 分钟的状态相关位移」——' +
    '它只在下跌的日子里延后，于是系统性地买在当日更高的价上（上涨才买），' +
    '并在 14:55 对始终不涨者照样全额成交，故**没有任何退出条款**来抵掉成本。' +
    '⚠ **三 fork 聚类是旁证，不是测量**：另两个成员 aaee3035（0.2533）与 5ac906ea（0.2552）同样把成交移离 13:10，' +
    '三者落在 0.0038 之内、对 base 都是约 −0.12；但它们与 base 的代码差异分别达 57% 与 25% 的行' +
    '（Jaccard 0.432 / 0.745），其 −0.12 中有多少属于时点早已被 q-e8-2 判定为「~0.09 属代码差异」。' +
    '所以**只有 7c2e9238 这一行是干净的受控 Δ**；三本书同向只是暗示，绝不可读成「−0.12 被测了三次」',
  confidence: 'high',
  flags:
    '⚠零滑点高估（延后入场恰恰把暴露挪向流动性与价差更不利的午后尾盘，真实滑点只会放大 −0.1241；' +
    '而 14:55 的强制买入在零滑点台上是免费的，实盘上是最贵的一笔）/ ' +
    '⚠ 单一窗口（TRAIN 2022–23）、单次测量、单一参数点（30 分钟 / 0.001）——不得外推到「任何趋势确认入场」/ ' +
    'attribution: **7c2e9238 的 Δ 可归因**（旋钮逐字相同、仅四个新函数、Jaccard 0.838）；' +
    '**三 fork 聚类仅为旁证**（aaee3035 / 5ac906ea 与 base 的行差异 57% / 25%，不是受控 Δ，' +
    '不得记作「同一结论被测了三次」）/ ' +
    'no-run: **本条未花任何回测分钟**，7c2e9238 的行由 normalize 阶段付费、base 侧取 §1 既有快照；' +
    '故本条既不运行也不触碰任何 edge claim 的 test: / ' +
    '⚠ 跨 epoch 并读：7c2e9238 为 epoch 8 行、baseline-e6 为 epoch 6 行——' +
    'epoch 7/8 均为 scoring-only（measurementPreservedFromPrevious），同一台，可比 / ' +
    '⚠ 函数集相对 baseline-e6「少了」set_slippage / set_commission，这是**normalized 快照 vs raw 文件**的产物' +
    '（注入的 OVERRIDE 包装器只存在于我们的 baseline 副本里，任何 strategies/*.py 都没有），' +
    '**不是缺 pin、不是策略差异**——下一个读者不要误读 / ' +
    '⚠ 该机制自带的两个旋钮（30 分钟回看、0.001 斜率阈值）未被任何人扫描，' +
    '故「最优延后规则」在严格意义上未被穷尽——见 implication 为何这仍足以关闭该子方向',
  description:
    '零回测路径，全部为免费读：(1) grep 7c2e9238 harness/normalize-train.tsv 取其 epoch-8 行；' +
    '(2) 以归一化代码行集合（去注释、去空行、trim）算与 baseline-e6 的 Jaccard = 0.838；' +
    '(3) 正则取两侧 ^def 名字求差集，得恰好四个新增函数；' +
    '(4) 逐个比对 base 的七个 g.<knob> 赋值与 below_count 阈值、列出全部 run_daily 时点；' +
    '(5) 直读 L1204–1345 的四个新函数确认机制（含 14:55 强制买入与现金均分）；' +
    '(6) 另读 aaee3035 / 5ac906ea 的 ledger 行。无 build / 无 run / 无 harvest 脚本。' +
    'recorder 复核结论：(40.81 − 15.67)/100 = 0.2514 与 ledger 的 objective 列一致',
  implication:
    '**关闭 q-e8-2 技术上留下的最后一条执行时点子方向：「也许一条更聪明的盘中入场规则能打败 13:10」。**' +
    'q-e8-2 只证明了纯分钟位移值 0.031（故 ±2 分钟量级的调时不值得资助），' +
    '但它明确留着「状态相关的、带趋势确认的入场」这一侧未答——本条由社区自费把它答了：' +
    '一条逐日自适应、最晚 14:55 兜底的趋势确认入场，在旋钮与 base 逐字相同的情况下亏掉 **0.1241**（地板的 4×）。' +
    '方向性很强：延后只发生在**下跌的日子**，而该书的信号本就吃当日价，' +
    '所以「等它涨起来再买」买到的是更高的价而且没有任何可抵消的退出条款——' +
    '机制上没有理由相信换个回看长度或斜率阈值会翻转符号（那只会改变延后的频率，不改变其方向性）。' +
    '**由此 §4 的已关闭清单新增一条：成交时点/入场择时轴（含状态相关的盘中确认）整条关闭**，' +
    '今后此轴的任何提案必须先给出一个与「延后只发生在下跌日」不同的机制论证，否则不排队。' +
    '**不开新方向**：本族剩下的唯一活口仍是逐日点时海外池（需数据），improve 轴仍被加总上界 0.4621 < 0.4848 关死。' +
    '**同时开出一条可复用的方法**（这是本条最耐久的产出，适用于所有家族，不只本族）：' +
    '一个新成员若与 base 的 Jaccard 高且**调参面逐字相同**，它就是一次别人付费完成的受控实验——' +
    '所以 **close-fork 成员必须先与 base 做 diff（旋钮比对 + 函数集差集），再决定是否提出任何回测**；' +
    '本条以 0 回测分钟买到了一个 4× 地板的 Δ 与一条方向的关闭，而若按「新成员 ⇒ 跑一轮」处理则要花 2 次回测' +
    '（变体 + 对照）去重新发现同一件事。' +
    '**不触碰**：valDeclined: 8 不变（0.2514 远不及成员 73b13d92 的 0.4848，清除条件未被接近）；' +
    'realizability: 保持未设（q-e8-3 的 PARTIAL 定案未变，且本条未测容量）；' +
    '两个 edge claim 的 status 不动（本条未运行任何 claim 的 test:，既不支持也不证伪）；VAL 不动',
  spawned: 'none',
  edgeRef: '趋势择时',
});
