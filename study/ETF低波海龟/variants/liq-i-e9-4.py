# liq-i-e9-4: i-e9-4 + buy-side floor capital 1000000 / 3 / ovr 0.05 = 6666667 CNY/day on 20d avg money; held exempt. Built by study/ETF低波海龟/build-liq-i-e9-4.js
# i-e9-4: i-e9-3 (3 lowest-vol, 1/vol, set-change, overlay off) with the 14 hand-picked risk ETFs -> q-e9-4 daily point-in-time equity pool (verbatim). Built by study/ETF低波海龟/build-i-e9-4.js
# i-e9-3: q-e9-3 (overlay off) -> 3 lowest-vol names, weights ∝ 1/vol, set-change rebalance, per-name min-hold + 10% band. Built by study/ETF低波海龟/build-i-e9-2-3.js
# q-e9-3: ETF低波海龟 base 4a8bcfd5, turtle overlay removed (100% entry, no add/stop/TP). Built by study/ETF低波海龟/build-q-e9-3-6.js
# Clone from JoinQuant
# postId: 4a8bcfd5092334a3a73493475f007f7a
# backtestId: bb63d032b576af1c71febb6ad20a157a
# title: 【量化分享】ETF低波海龟法则与复利增强的验证

# 克隆自聚宽文章：https://www.joinquant.com/post/78820
# 标题：开源一个年化超25%的ETF策略
# 作者：ETF量化老司机
#
# 本版本在原策略基础上增加：
#   1. 基于持仓成本的止盈，卖出利润的一半
#   2. ATR/N 计算
#   3. 每上涨1N加仓1个Unit，最多4个Unit
#   4. 加仓前10条检查
#   5. 4N止损
#   6. 初始仓位 3/4，加仓间距用最新 N
#   7. 止盈阈值30%，最短持有期20天
#   8. 避险资产只留国债ETF，阈值放宽到0.40
#   9. 去掉大盘风控，allow_safe 只看波动率中位数
#  10. 复利增强：止盈后允许用现金继续加仓，不转国债
# ============================================================================

import numpy as np
import pandas as pd

from jqdata import *


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.0001))
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0,
                  open_commission=0.0002, close_commission=0.0002,
                  close_today_commission=0, min_commission=5),
        type='fund')
    log.set_level('system', 'error')

    # ===== 资产分类 =====
    # q-e9-4: risk pool = point-in-time A-share EQUITY ETF pool, rebuilt daily before the open
    # (see POINT-IN-TIME EQUITY POOL block at the bottom). Was 14 hand-picked names.
    g.all_risk_etfs = {}
    run_daily(rebuild_pool, 'before_open')
    run_daily(q4_hold_log, '14:55')   # observation only
    # 避险资产（只留国债ETF，剔除货币ETF）
    g.safe_etfs = {
        '511010.XSHG': '国债ETF',
        '511260.XSHG': '十年国债ETF',
    }

    g.lookback = 60
    g.min_sample_ratio = 0.8
    g.topup_band = 0.95
    g.min_hold_days = 20
    g.switch_threshold = 0.1
    g.hold_days = 0

    # ===== 止盈参数 =====
    g.take_profit_cost_threshold = 0.30
    g.take_profit_sell_profit_ratio = 0.5
    g.take_profit_armed = True
    g.take_profit_done = False

    # ===== ATR/N 与加仓参数 =====
    g.atr_period = 20
    g.max_units = 4
    g.initial_units = 3
    g.add_interval_n = 1.0
    g.unit_value_ratio = 1.0 / g.max_units
    g.units = 0
    g.last_entry_price = None
    g.entry_n = None
    g.stop_price = None
    g.stop_atr_mult = 4.0
    g.risk_per_unit_ratio = 0.01
    g.max_total_risk_ratio = 0.04
    g.max_market_risk_ratio = 0.06
    g.min_trade_value = 1000

    # ===== 避险判断 =====
    g.risk_vol_median_threshold = 0.40
    g.in_safe_asset = False

    g.i3_days = {}  # i-e9-3
    run_daily(rebalance_top3, '09:35')  # i-e9-3: was rebalance_trade


def etf_name(code):
    return (g.all_risk_etfs.get(code) or
            g.safe_etfs.get(code) or code)


def get_vol_rank(context, candidates):
    """返回按 60 日年化波动率升序排列的 Series"""
    etfs = list(candidates.keys())
    if not etfs:
        return pd.Series(dtype=float)
    df = get_price(
        etfs,
        end_date=context.previous_date,
        count=g.lookback + 1,
        frequency='daily',
        fields=['close'],
        panel=False
    )
    if 'time' in df.columns:
        df = df.sort_values(['code', 'time'])
    df['log_ret'] = df.groupby('code')['close'].transform(
        lambda x: np.log(x / x.shift(1))
    )
    grp = df.groupby('code')['log_ret']
    counts = grp.count()
    need = int(g.lookback * g.min_sample_ratio)
    valid = counts[counts >= need].index
    dropped = [c for c in counts.index if c not in valid]
    if dropped:
        log.info("样本不足剔除（<%d 个有效收益率）：%s" % (
            need, "、".join(f"{etf_name(c)}({counts[c]})" for c in dropped)))
    vol = grp.std().mul(np.sqrt(252)).loc[valid].dropna().sort_values()
    return vol


def get_atr_n(context, code):
    """计算 N = TR 的 20 日 EMA"""
    df = get_price(
        code,
        end_date=context.previous_date,
        count=g.atr_period + 1,
        frequency='daily',
        fields=['high', 'low', 'close'],
        panel=False
    )
    if df is None or len(df) < g.atr_period + 1:
        return None
    if 'time' in df.columns:
        df = df.sort_values('time')
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    tr_list = []
    for i in range(1, len(df)):
        h = high[i]
        l = low[i]
        pdc = close[i - 1]
        tr = max(h - l, abs(h - pdc), abs(l - pdc))
        tr_list.append(tr)
    if len(tr_list) < g.atr_period:
        return None
    n = np.mean(tr_list[:g.atr_period])
    for tr in tr_list[g.atr_period:]:
        n = (19 * n + tr) / 20
    return n


def open_position(context, code, note):
    """初始建仓：买入 initial_units 个 Unit，设置 N 和止损"""
    n = get_atr_n(context, code)
    if n is None or n <= 0:
        log.warn(f"{etf_name(code)} 无法计算N，放弃建仓")
        return False
    price = get_current_data()[code].last_price
    if price is None or np.isnan(price) or price <= 0:
        return False
    total_value = context.portfolio.total_value
    target_value = total_value  # q-e9-3: 100% on entry (was 3 Units)
    target_value = min(target_value, context.portfolio.available_cash)
    if target_value < g.min_trade_value:
        log.warn(f"可用资金不足，放弃建仓：{target_value:.0f}")
        return False
    order_target_value(code, target_value)
    g.units = g.initial_units
    g.last_entry_price = price
    g.entry_n = n
    g.stop_price = price - g.stop_atr_mult * n
    g.hold_days = 0
    g.take_profit_done = False
    g.take_profit_armed = True
    g.in_safe_asset = False
    log.info(
        f"{note}：{etf_name(code)} {g.initial_units} Unit，金额 {target_value:,.0f}，"
        f"N={n:.4f}，止损={g.stop_price:.4f}（{g.stop_atr_mult:.0f}N）"
    )
    return True


def buy_safe_asset(context, code):
    """全仓买入避险资产（国债ETF），不设止损、不加仓"""
    price = get_current_data()[code].last_price
    if price is None or np.isnan(price) or price <= 0:
        return False
    total_value = context.portfolio.total_value
    order_target_value(code, total_value)
    g.units = g.max_units
    g.last_entry_price = None
    g.entry_n = None
    g.stop_price = None
    g.hold_days = 0
    g.take_profit_done = False
    g.take_profit_armed = True
    g.in_safe_asset = True
    log.info(f"避险买入：{etf_name(code)}，金额 {total_value:,.0f}")
    return True


def check_take_profit(context, code):
    """
    基于持仓成本止盈，卖出利润的一半。
    复利增强：止盈后不再转国债，资金留在账户里，
    允许后续用现金继续加仓。返回 True 表示已止盈。
    """
    if g.in_safe_asset:
        return False
    if code not in context.portfolio.positions:
        return False
    pos = context.portfolio.positions[code]
    if pos.total_amount <= 0:
        return False
    current_price = get_current_data()[code].last_price
    if current_price is None or np.isnan(current_price) or current_price <= 0:
        return False
    cost = pos.avg_cost
    if cost <= 0:
        return False
    ret = current_price / cost - 1
    if ret < g.take_profit_cost_threshold:
        g.take_profit_armed = True
        return False
    if not g.take_profit_armed:
        return False

    profit = pos.total_amount * (current_price - cost)
    if profit <= 0:
        return False
    sell_value = profit * g.take_profit_sell_profit_ratio
    sell_value = min(sell_value, pos.total_amount * current_price)
    sell_shares = int(sell_value / current_price / 100) * 100
    if sell_shares <= 0:
        log.info(f"止盈触发但不足一手：{etf_name(code)} 收益率 {ret:.2%}")
        return False

    sell_value = sell_shares * current_price
    target_value = pos.total_amount * current_price - sell_value
    order_target_value(code, target_value)

    g.take_profit_armed = False
    # 关键：不再设置 take_profit_done = True 阻止加仓，
    # 而是允许后续用现金继续加仓
    g.take_profit_done = False

    log.info(
        f"止盈：{etf_name(code)} 成本 {cost:.4f} 现价 {current_price:.4f}，"
        f"收益率 {ret:.2%}，利润约 {profit:,.0f}，"
        f"卖出利润一半 {sell_value:,.0f}，剩余市值 {target_value:,.0f}，"
        f"现金留在账户，后续可继续加仓"
    )
    return True


def check_stop_loss(context, code):
    """价格跌破止损价则清仓"""
    if g.in_safe_asset:
        return False
    if g.stop_price is None:
        return False
    price = get_current_data()[code].last_price
    if price is None or np.isnan(price) or price <= 0:
        return False
    if price <= g.stop_price:
        log.info(
            f"止损：{etf_name(code)} 价格 {price:.4f} <= "
            f"止损 {g.stop_price:.4f}，清仓"
        )
        order_target_value(code, 0)
        g.units = 0
        g.last_entry_price = None
        g.entry_n = None
        g.stop_price = None
        return True
    return False


def check_add_position(context, code):
    """
    检查并执行加仓，加仓间距用最新 N。
    复利增强：允许用现金继续加仓，止盈后不再阻止。
    """
    if g.in_safe_asset:
        return False
    if g.units >= g.max_units:
        return False
    if g.last_entry_price is None:
        return False

    price = get_current_data()[code].last_price
    if price is None or np.isnan(price) or price <= 0:
        return False

    current_n = get_atr_n(context, code)
    if current_n is None or current_n <= 0:
        return False

    trigger_price = g.last_entry_price + g.add_interval_n * current_n
    if price < trigger_price:
        return False

    # 加仓金额：优先用 Unit 计算，但受可用现金限制
    total_value = context.portfolio.total_value
    add_value = total_value * g.unit_value_ratio
    add_value = min(add_value, context.portfolio.available_cash)

    if add_value < g.min_trade_value:
        log.info(f"加仓资金不足：{add_value:.0f}")
        return False
    if g.units + 1 > g.max_units:
        return False

    pos = context.portfolio.positions[code]
    cur_shares = pos.total_amount
    add_shares = int(add_value / price / 100) * 100
    if add_shares <= 0:
        return False
    new_shares = cur_shares + add_shares

    new_stop = price - g.stop_atr_mult * current_n
    if new_stop <= 0:
        return False

    total_risk_ratio = (g.units + 1) * g.risk_per_unit_ratio
    if total_risk_ratio > g.max_total_risk_ratio:
        log.info(f"加仓后单品种总风险 {total_risk_ratio:.2%} 超限")
        return False
    if total_risk_ratio > g.max_market_risk_ratio:
        log.info(f"加仓后同市场组风险 {total_risk_ratio:.2%} 超限")
        return False

    cd = get_current_data()[code]
    if cd.paused:
        log.info("标的停牌，不加仓")
        return False

    log.info(
        f"加仓检查通过：{etf_name(code)} 现价 {price:.4f} >= "
        f"上次入场 {g.last_entry_price:.4f} + 1N({current_n:.4f})，"
        f"加 {add_shares} 份，Unit {g.units}->{g.units + 1}，"
        f"总风险 {total_risk_ratio:.2%}"
    )

    order_target_value(code, new_shares * price)
    g.units += 1
    g.last_entry_price = price
    g.entry_n = current_n
    g.stop_price = new_stop
    log.info(
        f"加仓完成：{etf_name(code)}，现 {g.units} Unit，"
        f"止损上移至 {g.stop_price:.4f}（4N）"
    )
    return True


def rebalance_trade(context):
    # 1. 计算风险资产波动率中位数
    risk_vol = get_vol_rank(context, g.all_risk_etfs)
    risk_vol_median = risk_vol.median() if len(risk_vol) > 0 else 0

    # 2. 判断是否允许避险（只看波动率中位数，去掉大盘风控）
    allow_safe = risk_vol_median > g.risk_vol_median_threshold
    log.info(f"风险资产波动率中位数 {risk_vol_median:.2%}；允许避险：{allow_safe}")

    # 3. 确定候选池
    if allow_safe:
        candidates = {**g.all_risk_etfs, **g.safe_etfs}
    else:
        candidates = g.all_risk_etfs

    vol = get_vol_rank(context, candidates)
    if len(vol) == 0:
        log.warn("无有效标的，今日不交易")
        return

    best = vol.index[0]
    best_vol = vol.iloc[0]

    top3 = "，".join(f"{etf_name(c)} {vol[c]:.1%}" for c in vol.index[:3])
    log.info(f"波动率最低三只：{top3}")

    # 4. 当前持仓
    held = [c for c in context.portfolio.positions
            if context.portfolio.positions[c].total_amount > 0]

    if len(held) > 1:
        for c in held[1:]:
            order_target_value(c, 0)
            log.warn(f"清理多余持仓：{etf_name(c)}({c})")
        held = held[:1]

    # 5. 空仓 → 建仓
    if not held:
        if best in g.safe_etfs:
            buy_safe_asset(context, best)
        else:
            open_position(context, best, "建仓")
        return

    cur = held[0]
    is_safe_cur = cur in g.safe_etfs

    # 6. 如果当前持有避险资产，检查是否应该换回风险资产
    if is_safe_cur:
        # 风控解除：波动率中位数 <= 0.40，allow_safe=False
        if not allow_safe:
            risk_vol_only = get_vol_rank(context, g.all_risk_etfs)
            if len(risk_vol_only) > 0:
                risk_best = risk_vol_only.index[0]
                risk_best_vol = risk_vol_only.iloc[0]
                log.info(f"风控解除，换回风险资产：{etf_name(risk_best)} "
                         f"波动率 {risk_best_vol:.2%}")
                order_target_value(cur, 0)
                g.in_safe_asset = False
                g.units = 0
                g.last_entry_price = None
                g.entry_n = None
                g.stop_price = None
                open_position(context, risk_best, "换回")
                return
        log.info(f"继续持有避险资产：{etf_name(cur)}")
        return

    # 7. 当前持有风险资产
    if False and check_stop_loss(context, cur):  # q-e9-3: no 4N stop
        return
    if False and check_take_profit(context, cur):  # q-e9-3: no take-profit
        # 复利增强：止盈后不 return，继续往下走，尝试加仓
        pass

    g.hold_days += 1

    # 8. 如果当前持仓仍是最低波动，尝试加仓
    # 复利增强：止盈后仍允许加仓，只要满足加仓条件
    if cur == best:
        if False and check_add_position(context, cur):  # q-e9-3: no add-ons
            return
        log.info(f"当前持仓 {etf_name(cur)} 仍是最低波动，"
                 f"未触发加仓条件或资金不足，继续持有")
        return

    # 9. 当前持仓不在有效池，或波动率切换
    if cur not in vol.index:
        log.info(f"当前持仓 {etf_name(cur)} 已不在有效池，无条件换出")
        order_target_value(cur, 0)
        g.units = 0
        g.last_entry_price = None
        g.entry_n = None
        g.stop_price = None
        if best in g.safe_etfs:
            buy_safe_asset(context, best)
        else:
            open_position(context, best, "换入")
        return

    cur_vol = vol[cur]

    # 最短持有期
    if g.hold_days < g.min_hold_days:
        log.info(f"最短持有期未满：{etf_name(cur)} 已持有 {g.hold_days}/"
                 f"{g.min_hold_days} 日，"
                 f"{etf_name(best)}({best_vol:.2%}) 更低但不换")
        return

    # 波动率切换阈值
    if best_vol < cur_vol * (1 - g.switch_threshold):
        log.info(f"换仓：{etf_name(cur)} {cur_vol:.2%} → "
                 f"{etf_name(best)} {best_vol:.2%}")
        order_target_value(cur, 0)
        g.units = 0
        g.last_entry_price = None
        g.entry_n = None
        g.stop_price = None
        if best in g.safe_etfs:
            buy_safe_asset(context, best)
        else:
            open_position(context, best, "换入")
    else:
        log.info(f"抑制换手：{etf_name(best)} {best_vol:.2%} 仅比持仓 "
                 f"{etf_name(cur)} {cur_vol:.2%} 相对低 "
                 f"{1 - best_vol / cur_vol:.1%}，未达阈值 "
                 f"{g.switch_threshold:.0%}，继续持有")

# i-e9-3: hold the K=3 lowest-vol names (same get_vol_rank, same safe-leg rule), weights ∝ 1/vol,
# re-weighted ONLY on a day the held SET changes. Per-name 20-day min hold; per-name 10% band:
# a held name outside the top-K is replaced by the lowest-vol non-held top-K name only if
# in_vol < out_vol * (1 - 0.10) and the outgoing name has been held >= 20 days.
# Forced (no min-hold, no band): a held name missing from the valid pool (incl. a bond once
# allow_safe turns False — the base's 换回 rule) is dropped and the slot refilled from the ranking.
# A held bond is exempt from the band while allow_safe is True (base: 继续持有避险资产).
I3_K = 3

def rebalance_top3(context):
    risk_vol = get_vol_rank(context, g.all_risk_etfs)
    risk_vol_median = risk_vol.median() if len(risk_vol) > 0 else 0
    allow_safe = risk_vol_median > g.risk_vol_median_threshold
    if allow_safe:
        candidates = {**g.all_risk_etfs, **g.safe_etfs}
    else:
        candidates = g.all_risk_etfs
    candidates = liq_screen_i4(context, candidates)  # liq-i-e9-4
    vol = get_vol_rank(context, candidates)
    if len(vol) == 0:
        log.warn("I3 无有效标的，今日不交易")
        return
    pos = context.portfolio.positions
    held = [c for c in pos if pos[c].total_amount > 0]
    for c in held:
        g.i3_days[c] = g.i3_days.get(c, 0) + 1
    for c in list(g.i3_days.keys()):
        if c not in held:
            del g.i3_days[c]
    topk = list(vol.index[:I3_K])
    new_set = list(held)
    why = []
    for c in list(new_set):
        if c not in vol.index:
            new_set.remove(c)
            why.append("drop-invalid %s" % c)
    for c in vol.index:
        if len(new_set) >= I3_K:
            break
        if c not in new_set:
            new_set.append(c)
            why.append("fill %s" % c)
    while True:
        incoming = [c for c in topk if c not in new_set]
        outgoing = [c for c in new_set if c not in topk
                    and g.i3_days.get(c, 0) >= g.min_hold_days
                    and not (allow_safe and c in g.safe_etfs)]
        if not incoming or not outgoing:
            break
        outgoing.sort(key=lambda c: -vol[c])
        i, o = incoming[0], outgoing[0]
        if vol[i] < vol[o] * (1 - g.switch_threshold):
            new_set.remove(o)
            new_set.append(i)
            why.append("swap %s(%.4f)->%s(%.4f)" % (o, vol[o], i, vol[i]))
        else:
            break
    changed = set(new_set) != set(held)
    log.info("I3 med=%.4f allow=%s top=%s held=%s" % (
        risk_vol_median, allow_safe, ",".join(topk), ",".join(sorted(held))))
    if not changed:
        return
    inv = {c: 1.0 / vol[c] for c in new_set}
    s = 0.0  # builtin sum is shadowed by 'from jqdata import *'
    for c in new_set:
        s += inv[c]
    w = {c: inv[c] / s for c in new_set}
    tv = context.portfolio.total_value
    for c in held:
        if c not in new_set:
            order_target_value(c, 0)
    cur = {c: (pos[c].total_amount * pos[c].price if c in pos else 0.0) for c in new_set}
    order = sorted(new_set, key=lambda c: tv * w[c] - cur[c])
    for c in order:
        tgt = tv * w[c]
        if tgt > cur[c]:
            tgt = min(tgt, cur[c] + context.portfolio.available_cash)
        order_target_value(c, tgt)
    for c in new_set:
        if c not in held:
            g.i3_days[c] = 0
    log.info("I3SET %s | %s | %s" % (
        " ".join("%s:%.3f" % (c, w[c]) for c in sorted(new_set)), "; ".join(why),
        " ".join("%s=%.4f" % (c, vol[c]) for c in sorted(new_set))))

# ===== POINT-IN-TIME EQUITY POOL (q-e9-4; construction from study/ETF动量/variants/pit-pool.py) =====
#  - universe: get_all_securities(['etf'], date=context.previous_date) — only funds that existed then.
#  - 次新 exclusion: listed < 250 calendar days is never eligible (harness §3).
#  - liquidity floor 2e7 CNY = 1,000,000 full position / order_volume_ratio 0.05, on the trailing
#    20-bar MEDIAN money (pit-pool's rule, so one spike day cannot admit an illiquid fund); not paused.
#  - EQUITY-ONLY (queue design): display_name must not match POOL_EXCL_NAME, and code prefix must
#    not be SH 511 (bond/money ETFs), 513 (cross-border/QDII), 518 (gold). The low-vol rank would
#    otherwise degenerate to a money/short-bond fund.
#  - rebuilt every trading day; the current RISK holding is unioned in (pit-pool rule) so a name
#    drifting under the floor is handled by the strategy's own ranking/min-hold/switch band rather
#    than a forced exit. Safe-leg codes are never unioned into the risk pool.
import re as _q4re
POOL_MIN_MONEY   = 2.0e7
POOL_MIN_LISTED  = 250
POOL_LIQ_WINDOW  = 20
POOL_TYPES       = ['etf']
POOL_EXCL_NAME   = _q4re.compile(u'债|货币|现金|黄金|豆粕|商品|纳指|标普|日经|德国|恒生|港|H股|纳斯达克'
                                 u'|理财|短融|日利|添益|快线|快钱|财富宝|保证金|货基'
                                 u'|QDII|美国|美股|美元|道琼斯|中概|法国|日本|亚太|东南亚|沙特|欧洲|英国|全球|海外'
                                 u'|期货|原油|白银|能源化工|有色期货|大宗')
POOL_EXCL_PREFIX = ('511', '513', '518')
# Non-equity funds whose display_name carries no excluded word (found in run 1's POOLLIST audit):
# 159980 有色ETF大成 = 大成有色金属期货ETF (commodity futures); 159831 金ETF嘉实 = 嘉实黄金ETF.
POOL_EXCL_CODE   = ('159980.XSHE', '159831.XSHE')


def _pool_not_paused(cur, c):
    try:
        return not cur[c].paused
    except Exception:
        return False


def _pool_median_money(cand, d):
    candset = set(cand)
    out = {}
    try:
        try:
            px = get_price(cand, end_date=d, count=POOL_LIQ_WINDOW, frequency='daily',
                           fields=['money'], skip_paused=False, panel=False)
        except TypeError:
            px = get_price(cand, end_date=d, count=POOL_LIQ_WINDOW, frequency='daily',
                           fields=['money'], skip_paused=False)
        cols = list(getattr(px, 'columns', []))
        if 'code' in cols:
            for c, grp in px.groupby('code'):
                out[c] = float(grp['money'].median())
        elif 'money' in cols and getattr(px.index, 'nlevels', 1) > 1:
            s = px['money']
            for lvl in (0, 1):
                g2 = s.groupby(level=lvl).median()
                if len(candset & set(g2.index)) > 0:
                    out = dict((k, float(v)) for k, v in g2.items())
                    break
        else:
            m = px['money'].median()
            out = dict((k, float(v)) for k, v in m.items())
    except Exception as e:
        log.error('POOLWARN batched liquidity failed (%s)' % e)
        out = {}
    if len(candset & set(out.keys())) < len(candset) * 0.5:
        log.error('POOLWARN batched shape unusable (%d/%d) -> per-code fallback'
                  % (len(candset & set(out.keys())), len(candset)))
        out = {}
        for c in cand:
            try:
                p1 = get_price(c, end_date=d, count=POOL_LIQ_WINDOW, frequency='daily',
                               fields=['money'], skip_paused=False)
                out[c] = float(p1['money'].median())
            except Exception:
                continue
    return out


def rebuild_pool(context):
    d = context.previous_date
    allsec = get_all_securities(types=POOL_TYPES, date=d)
    sd = pd.to_datetime(allsec['start_date'])
    old = allsec.index[sd <= pd.Timestamp(d) - pd.Timedelta(days=POOL_MIN_LISTED)]
    names = allsec['display_name']
    cand = [c for c in old
            if not c.startswith(POOL_EXCL_PREFIX) and not POOL_EXCL_NAME.search(names[c])
            and c not in g.safe_etfs and c not in POOL_EXCL_CODE]
    med = _pool_median_money(cand, d) if cand else {}
    cur = get_current_data()
    pool = [c for c in cand if med.get(c, 0.0) >= POOL_MIN_MONEY and _pool_not_paused(cur, c)]
    held = [s for s in context.portfolio.positions
            if context.portfolio.positions[s].total_amount > 0 and s not in g.safe_etfs]
    g.all_risk_etfs = dict((c, names.get(c, c)) for c in sorted(set(pool) | set(held)))
    log.info('POOLSIZE %s listed=%d old=%d equity=%d pool=%d'
             % (str(d), len(allsec), len(old), len(cand), len(g.all_risk_etfs)))
    if getattr(g, 'q4_pool_month', None) != (d.year, d.month):
        g.q4_pool_month = (d.year, d.month)
        log.info('POOLLIST %s %s' % (str(d), ','.join('%s|%s' % (c, n) for c, n in g.all_risk_etfs.items())))


def q4_hold_log(context):
    held = [(c, p.total_amount * p.price) for c, p in context.portfolio.positions.items()
            if p.total_amount > 0]
    log.info('Q4HOLD %s %s' % (str(context.current_dt.date()),
             ';'.join('%s|%s|%.0f' % (c, etf_name(c), v) for c, v in held) or 'CASH'))
# ===== END POINT-IN-TIME EQUITY POOL =====


# ==================== liq-i-e9-4: buy-side feasibility floor (capital/3/ovr) ====================
LIQ4_CAPITAL = 1000000.0  # harness capital
LIQ4_OVR = 0.05  # harness orderVolumeRatio
LIQ4_SLOTS = 3
LIQ4_DAYS = 20

def liq_screen_i4(context, cands):
    codes = list(cands.keys())
    floor = LIQ4_CAPITAL / LIQ4_SLOTS / LIQ4_OVR
    floor_live = float(context.portfolio.total_value) / LIQ4_SLOTS / LIQ4_OVR
    pos = context.portfolio.positions
    held = set([c for c in pos if pos[c].total_amount > 0])
    try:
        df = get_price(codes, end_date=context.previous_date, count=LIQ4_DAYS,
                       frequency='daily', fields=['money'], panel=False)
        money = df.groupby('code')['money'].mean().to_dict()
    except Exception as e:
        money = None
    if not money:
        log.info("LIQ4 date=%s floor=%.0f in=%d status=bypass-nodata" % (context.previous_date, floor, len(codes)))
        return cands
    kept = {}
    removed = []
    live_removed = []
    for c in codes:
        m = float(money.get(c, 0.0) or 0.0)
        if c in held:
            kept[c] = cands[c]
            continue
        if m < floor_live:
            live_removed.append(c)
        if m >= floor:
            kept[c] = cands[c]
        else:
            removed.append(c)
    safe = ';'.join(['%s:%.0f' % (c, float(money.get(c, 0.0) or 0.0)) for c in codes if c in g.safe_etfs]) or '-'
    nonheld = [float(money.get(c, 0.0) or 0.0) for c in codes if c not in held and c not in g.safe_etfs]
    log.info("LIQ4 date=%s floor=%.0f floor_live=%.0f in=%d out=%d removed=%s live_removed=%s safe=%s minRiskNonHeld=%.0f status=ok"
             % (context.previous_date, floor, floor_live, len(codes), len(kept),
                ';'.join(removed) or '-', ';'.join(live_removed) or '-', safe,
                sorted(nonheld)[0] if nonheld else -1))
    return kept


# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====
