#!/usr/bin/env node
/**
 * _build-etf-m2.js — builds the three declared candidates of the ETF universe MERGE round 2.
 *
 * Pair: [[ETF动量]] × [[七星高照]] — IDENTICAL edge set {动量}, so this is a
 * "better implementation of one edge" merge, not a combine.
 *
 * Host  : study/ETF动量/baseline-e6.py   (0aa4028d, epoch-6 obj 0.1868, worst year 2023 -0.0072)
 * Donor : study/七星高照/baseline-e6.py  (19ca0e69, epoch-6 obj 0.1252, worst year 2023 -0.0651)
 *
 * The host is chosen as the skeleton for the universe-screen step because it is the member with
 * the BETTER worst TRAIN year (-0.0072 vs -0.0651), i.e. the one that sets the epoch-7 bar.
 *
 * Every edit is asserted against the host text; nothing is hand-edited afterwards. The appended
 * harness OVERRIDE block (the epoch pins) is split off and re-attached untouched.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const HOST = path.join(ROOT, 'study/ETF动量/baseline-e6.py');
const OUT = __dirname;
const MARK = '# ===== AUTORESEARCH NORMALIZATION OVERRIDE';

function load() {
  const txt = fs.readFileSync(HOST, 'utf8');
  const i = txt.indexOf(MARK);
  if (i < 0) throw new Error('host lost its harness OVERRIDE block');
  return { body: txt.slice(0, i), override: txt.slice(i) };
}

/** Exact single-occurrence replacement; throws rather than silently producing the host. */
function sub(txt, from, to, label) {
  const n = txt.split(from).length - 1;
  if (n !== 1) throw new Error(`[${label}] expected exactly 1 occurrence, found ${n}`);
  return txt.replace(from, to);
}

// ─────────────────────────────────────────────────────────────────────────────
// Step: RISK OVERLAY — the one net-positive filter measured anywhere in this universe.
// 七星高照 q-e6-5: removing 近3日单日跌幅排除 costs Δobj -0.0727, and its §1 names it
// 「唯一净正的滤波」. ETF动量's base carries NO event-type filter at all (its own two
// overlays are measured inert: stop Δ0 q-e6-4, abs-momentum gate Δ-0.012 q-e6-2).
// Transplanted verbatim: the donor appends the live last_price to the close series, so the
// three day-ratios are read at the host's own execution moment, exactly as in the donor.
// ─────────────────────────────────────────────────────────────────────────────
const CRASH_HELPER = `

def _qx_crash_excluded(etf):
    """[[七星高照]] baseline-e6 §5「近3日单日跌幅过滤」逐字移植。

    供体 study/七星高照/baseline-e6.py calculate_momentum_metrics 第 361-368 行：
        price_series = np.append(prices["close"].values, current_price)
        day1/day2/day3 = 相邻比值；min(day1, day2, day3) < g.loss 即剔出排名。
    证据：七星 study-q-e6-5，去掉它 Δobjective −0.0727，是本 universe 里**唯一**实测
    净正的滤波（其 §1：「唯一净正的滤波是 3 日急跌排除」，且「保的是收益」）。
    """
    try:
        df = attribute_history(etf, 4, '1d', ['close'])
        ps = np.append(df['close'].values, get_current_data()[etf].last_price)
        if len(ps) < 4:
            return False
        day1 = ps[-1] / ps[-2]
        day2 = ps[-2] / ps[-3]
        day3 = ps[-3] / ps[-4]
        return min(day1, day2, day3) < g.loss
    except Exception:
        return False
`;

const RANK_OLD = `    df = df[(df['score'] > 0) & (df['score'] <= 4.8)]
    return list(df.index)`;

const RANK_CRASH = `    df = df[(df['score'] > 0) & (df['score'] <= 4.8)]
    # ===== MERGE 移植（[[七星高照]] q-e6-5）：近3日单日跌幅排除 =====
    return [e for e in list(df.index) if not _qx_crash_excluded(e)]`;

const RANK_NOCAP_CRASH = `    # ===== MERGE 步骤选择：取 [[七星高照]] 的「无上限」变体 =====
    # 宿主的 score <= 4.8 上限按其 §1 自述是「单一 2022 事件的修补」（q-e6-5 值 +0.0225，
    # 全在 2022）；供体 g.max_score_threshold = 100.0 等于无上限，且其 动量 edge 是在无
    # 上限下测得的（七星 q-e6-1 / q-e6-8）。epoch-7 的 BAR 比的是最差年（2023），一个压在
    # 2022 的修补不属于这一步的最优变体。score > 0 闸门保留：两族都测得近乎惰性
    # （ETF动量 q-e6-2 −0.012 / 七星 q-e6-6 +0.017），而它正是「无合格者」这一步存在的前提。
    df = df[df['score'] > 0]
    # ===== MERGE 移植（[[七星高照]] q-e6-5）：近3日单日跌幅排除 =====
    return [e for e in list(df.index) if not _qx_crash_excluded(e)]`;

// ─────────────────────────────────────────────────────────────────────────────
// Step: HOLDING / EXIT — the donor's cash leg. 七星高照 §1: 无合格者持 511880 货币ETF.
// The host goes flat instead. Measured-equivalent in effect on the host (its gate is nearly
// inert, q-e6-2), but the donor's is the variant with a measured pipeline behind it.
// ─────────────────────────────────────────────────────────────────────────────
const TRADE_OLD = `def trade(context):
    stop_loss_check(context)

    target = rank(context)[:g.max_hold]`;

const TRADE_MERGED = `def trade(context):
    # ===== MERGE 步骤选择：去掉宿主的 −10% 固定止损 =====
    # ETF动量 q-e6-4 实测逐位惰性（Δobjective 0 / Δsharpe 0 / ΔmaxDD 0），供体没有止损。
    # 去掉一个实测为零的部件是零代价化简，不是调参。
    target = rank(context)[:g.max_hold]

    # ===== MERGE 步骤选择：取 [[七星高照]] 的「无合格者持 511880 货币ETF」离场变体 =====
    # 宿主的变体是空仓持现金；供体 §1 的变体是退到防御 ETF，且供体的 动量 edge 正是在这条
    # 离场腿上测得的。
    if not target:
        target = [g.defensive_etf]`;

// ─────────────────────────────────────────────────────────────────────────────
// Step: ENTRY MOMENT — 09:30 (host) vs 14:00 (donor). On the daily bench 09:30 fills at the
// OPEN and an afternoon slot fills at the CLOSE (established by ETF溢价 study-u-1 and
// PT多策略 study-u-7, where moving the same signal to 14:50 collapsed +321%→+10% and
// +196%→−29%: in this universe the open-auction print is the known artefact surface).
// ⚠ This change moves SIGNAL and FILL together — momentum_score appends the live last_price —
// exactly as the donor does. That is why it is isolated in its own candidate.
// ─────────────────────────────────────────────────────────────────────────────
const SCHED_OLD = `    run_daily(trade, '9:30')`;
const SCHED_1400 = `    # ===== MERGE 步骤选择：取 [[七星高照]] 的 14:00 执行时点 =====
    # 供体 §1：run_daily(etf_sell_trade, '14:00') / (etf_buy_trade, '14:01')，其 动量 edge
    # （q-e6-1 / q-e6-8）全部在该时点测得。日频台上 09:30 成交 = 开盘价、午后 = 收盘价；
    # 本 universe 的两次 realizability 判决（ETF溢价 u-1、PT多策略 u-7）都指向开盘集合竞价
    # 那口价。⚠ 该改动同时移动信号与成交（momentum_score 追加当日 last_price），与供体一致。
    run_daily(trade, '14:00')`;

const PARAMS_OLD = `    g.stop_loss = -0.10    # 止损线（-10%）`;
const PARAMS_MERGED = `    g.stop_loss = -0.10    # 止损线（-10%）——MERGE：stop_loss_check 已不再调用（q-e6-4 惰性）
    g.loss = 0.97          # MERGE 移植：近3日单日跌幅阈值（[[七星高照]] g.loss, q-e6-5）
    g.defensive_etf = "511880.XSHG"   # MERGE 移植：无合格者时的防御ETF（[[七星高照]] §1）`;

const PARAMS_C1 = `    g.stop_loss = -0.10    # 止损线（-10%）
    g.loss = 0.97          # MERGE 移植：近3日单日跌幅阈值（[[七星高照]] g.loss, q-e6-5）`;

function header(id, oneLine, diffLines) {
  return `# ${id} — ETF universe MERGE round 2 (epoch 7 bar, epoch 6 measurement台)
# pair  : [[ETF动量]] × [[七星高照]] — IDENTICAL edge set {动量} => better-implementation merge
# host  : study/ETF动量/baseline-e6.py  (0aa4028d, obj 0.1868, worst TRAIN year 2023 −0.0072 = the BAR)
# donor : study/七星高照/baseline-e6.py (19ca0e69, obj 0.1252, worst TRAIN year 2023 −0.0651)
# ${oneLine}
#
${diffLines.map(l => `# ${l}`).join('\n')}
#
# ⚠ 两族的 动量 edge 都只在各自**事后写定（2026）**的手选跨资产池内成立
#   （ETF动量 q-e6-3 A股池 −0.27；七星 q-e6-9 源码自带 38 只大池 0.0016），两页都把
#   「点时池」列为读任何水平数字的**前置条件**。故本候选的任何数字只是**同池内的相对比较**，
#   不是可交易主张（rule 4：合并继承最差腿的现实性）。
# generated by enhance/candidates/_build-etf-m2.js — do not hand-edit
`;
}

const { body, override } = load();

// ── etf-m2-c1 — the single attributable transplant ──────────────────────────
{
  let t = body;
  t = sub(t, PARAMS_OLD, PARAMS_C1, 'c1 params');
  t = sub(t, RANK_OLD, RANK_CRASH, 'c1 rank');
  t = sub(t, `def stop_loss_check(context):`, `${CRASH_HELPER.trim()}\n\n\ndef stop_loss_check(context):`, 'c1 helper');
  const out = header('etf-m2-c1', 'ONE change: + 七星高照 的近3日急跌排除（唯一实测净正的滤波）', [
    'step  : risk overlay',
    'diff  : rank() 末尾按 [[七星高照]] q-e6-5 的 min(day1,day2,day3) < 0.97 剔出排名；其余逐字不动',
    'cite  : 七星高照 study-q-e6-5（去掉 Δobj −0.0727，唯一净正滤波）；ETF动量 §1（无任何事件型滤波）',
    'thesis: 宿主的弱年是 2023（annual 11.33 vs maxDD 12.05 ⇒ obj −0.0072），是回撤问题而非收益问题',
  ]) + t + override;
  fs.writeFileSync(path.join(OUT, 'etf-m2-c1.py'), out);
  console.log('wrote etf-m2-c1.py');
}

// ── etf-m2-c2 — the merged pipeline, host execution moment ──────────────────
{
  let t = body;
  t = sub(t, PARAMS_OLD, PARAMS_MERGED, 'c2 params');
  t = sub(t, RANK_OLD, RANK_NOCAP_CRASH, 'c2 rank');
  t = sub(t, TRADE_OLD, TRADE_MERGED, 'c2 trade');
  t = sub(t, `def stop_loss_check(context):`, `${CRASH_HELPER.trim()}\n\n\ndef stop_loss_check(context):`, 'c2 helper');
  const out = header('etf-m2-c2', '合并流水线：每一步取两族中有实测支持的最优变体（执行时点仍为宿主 09:30）', [
    'universe  : ETF动量 的 11 只跨资产池（两族池都是事后选的；取最差年较好的那一族的池）',
    'selection : 25 日加权对数回归 slope×R²、top-1（两族逐字相同）',
    'entry     : 宿主 09:30（在 c3 里换成供体的 14:00，以隔离该步）',
    'exit      : 供体变体——无合格者持 511880 货币ETF（七星 §1）',
    'risk      : 保留供体唯一净正的近3日急跌排除（q-e6-5）；去掉 score≤4.8 上限（宿主 q-e6-5：',
    '            单一 2022 事件的修补）与 −10% 止损（宿主 q-e6-4：逐位惰性）；不引入供体三件',
    '            实测净负的滤波——10 日动量过滤（q-e6-7 +0.0640）、盈利保护（q-e6-4 +0.0333）、',
    '            得分闸门放开（q-e6-6 +0.0171）',
    'sizing    : 单持仓满仓（七星 q-e6-3 −0.0483 / ETF动量 q-e6-8 −0.1946 都说集中是来源）',
    '⚠ 不是加总 Δ：本候选作为**一个**策略整体实测，上列 Δ 只用来为每一步的变体选择提供依据',
  ]) + t + override;
  fs.writeFileSync(path.join(OUT, 'etf-m2-c2.py'), out);
  console.log('wrote etf-m2-c2.py');
}

// ── etf-m2-c3 — the merged pipeline at the donor's execution moment ─────────
{
  let t = body;
  t = sub(t, PARAMS_OLD, PARAMS_MERGED, 'c3 params');
  t = sub(t, RANK_OLD, RANK_NOCAP_CRASH, 'c3 rank');
  t = sub(t, TRADE_OLD, TRADE_MERGED, 'c3 trade');
  t = sub(t, SCHED_OLD, SCHED_1400, 'c3 schedule');
  t = sub(t, `def stop_loss_check(context):`, `${CRASH_HELPER.trim()}\n\n\ndef stop_loss_check(context):`, 'c3 helper');
  const out = header('etf-m2-c3', '= c2，但执行时点取供体的 14:00（隔离「入场时刻」这一步）', [
    'diff vs c2 : run_daily(trade, 9:30) -> run_daily(trade, 14:00)，其余与 c2 逐字相同',
    'cite       : 七星高照 §1（其 动量 edge 全在 14:00/14:01 测得）；realizability 侧由',
    '             ETF溢价 u-1 / PT多策略 u-7 给出——本 universe 的开盘集合竞价成交是已判决的伪影面',
    '⚠ 该步同时移动信号与成交（momentum_score 追加当日 last_price），与供体一致；故 c2↔c3 的差',
    '  是「这本轮动书是否依赖开盘价那口成交」的直接测量，而不是一个纯执行实验',
  ]) + t + override;
  fs.writeFileSync(path.join(OUT, 'etf-m2-c3.py'), out);
  console.log('wrote etf-m2-c3.py');
}
