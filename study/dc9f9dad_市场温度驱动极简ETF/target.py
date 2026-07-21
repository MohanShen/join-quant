# Clone from JoinQuant
# postId: dc9f9dad0c32850c2356b3993b88fae8
# backtestId: 965db35369fd23f2ac349298273c7786
# title: 市场温度驱动的极简ETF 轮动策略--6年10倍

# -*- coding: utf-8 -*-
"""
策略名称：市场温度驱动的 ETF 轮动策略
适用平台：聚宽（JoinQuant）
主要标的：创业板ETF（159915.XSHE）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【核心思想】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
策略以"市场温度"作为唯一决策变量，量化描述 A 股所处的长周期冷暖状态，
从而在大牛市中满仓持有创业板 ETF，在过热或熊市初期及时退出，
空档期通过轮动至商品/债券 ETF 保持资金利用率。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【温度指标体系（分四层递进）】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  temp1：原始周期位置
    = 当前价格在过去 960 个交易日（约 4 年）高低区间内的百分位，
      映射到 [-1, 1]，反映价格在大周期中的冷热位置。

  temp2：平滑温度（短中期核心信号）
    = temp1 经指数移动平均（EMA60）平滑，再叠加极端热度强化项，
      抑制噪声的同时，在市场极端状态时加大信号幅度。

  temp3：温度积分（长期趋势慢变量）
    = temp2 的滚动积分（120 日窗口），捕捉多年维度的温度积累效应，
      区分"短暂回暖"与"真正的牛市"。

  temp4：综合温度评分（最终决策信号）
    = (temp2 + temp3) 的 365 日滚动累计 / 365
      + temp2 × 0.5 + 近 365 日收益率 × 0.5
    融合中期趋势、长期积累与价格动量，构成最终买卖判据。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【买卖信号规则】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  买入：当前空仓且 temp4 < -3.52（市场极度低温，长期底部区域）
  卖出：当前满仓且 temp4 >  3.52（市场极度高温，长期顶部区域）
  首次运行：立即买入（捕捉策略启动时的初始机会）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【空档期轮动逻辑】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  卖出创指后进入分阶段过渡，而非直接空仓：
    阶段一（0～200 天）：持有南方原油 ETF（501018.XSHG）
                         若标的尚未上市则以城投债 ETF 代替
    阶段二（200～400 天）：切换至豆粕 ETF（159985.XSHE）
                           若标的尚未上市则以城投债 ETF 代替
    阶段三（400 天后）：转入纳指 ETF（513100.XSHG），长期持有
                        直至温度信号触发回归创指

  从纳指切回创指时，设置 20 天观察期（持城投债），
  确认信号稳定后再正式买入创指，避免频繁切换。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【过热短期保护】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  在主逻辑仍处于持仓信号期间，若持有标的出现短期急涨（过热），
  临时切换至城投债 ETF（511220.XSHG），7 个交易日后自动恢复原持仓。
  触发条件（任一满足）：
    ① 当前价 vs 10 个交易日前收盘价涨幅 > 35%
    ② 当前价 vs 过去 1 个月（21 日）最低价涨幅 > 40%
  冷静期 14 天，防止连续触发。
  注意：过热保护不影响主状态机（温度信号、等待期计时不受干预）。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【其他风控】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  最大持仓天数：创指单次持仓上限 1060 天（约 4.2 年），
  防止因温度信号长期未触发而永久持仓。
"""

from __future__ import division

try:
    from jqdata import *  # noqa: F401,F403
except Exception:
    pass

import numpy as np
import pandas as pd


# ==================== 初始化 ====================

def initialize(context):
    set_benchmark("159915.XSHE")
    set_option("use_real_price", True)
    try:
        set_option("avoid_future_data", True)
    except Exception:
        pass

    set_slippage(FixedSlippage(0.0003))
    set_order_cost(
        OrderCost(
            open_tax=0, close_tax=0,
            open_commission=0.00025, close_commission=0.00025,
            close_today_commission=0, min_commission=5,
        ),
        type="fund",
    )
    log.set_level("order", "error")
    log.set_level("system", "error")

    # 主要品种
    g.security          = "159915.XSHE"   # 创业板ETF
    g.defensive_security = "513100.XSHG"  # 纳指ETF（长期空档）
    g.gold_security1    = "501018.XSHG"   # 原油ETF（空档前半段，兜底城投债）
    g.gold_security2    = "159985.XSHE"   # 豆粕ETF（空档后半段，兜底城投债）
    g.gold_security_fallback = "511220.XSHG"  # 城投债ETF（兜底 / 纳指→创指空档 / 过热规避）

    # 状态变量
    g.chuangzhi_sell_date = None   # 创指卖出日（进入空档计时）
    g.nasdaq_sell_date    = None   # 纳指切回创指的等待计时
    g.chuangzhi_buy_date  = None   # 创指买入日（最大持仓天数计时）
    g.last_target_pct     = 0.0
    g.last_source         = "flat"
    g.last_week_logged    = None
    g.score_dodge_end_date      = None  # 过热规避期结束日（含当日）
    g.score_dodge_triggered_date = None  # 上次触发日（7日冷静期）

    g.params = build_default_params()
    g.bar_count = max(
        required_bars(g.params),
        g.params["temperature_cycle_window"],
        g.params["temperature_integral_window"] + g.params["temperature_turn_window"] + 2,
    ) + 20

    run_daily(on_daily_bar, time="09:35", reference_security=g.security)


def build_default_params():
    return {
        # 趋势锚（MA）
        "anchor_ma_window":    120,
        "anchor_slope_window":  15,
        # 温度体系
        "temperature_cycle_window":     960,
        "temperature_cycle_min_bars":    90,
        "temperature_slow_span":         60,
        "temperature_extreme_window":    20,
        "temperature_extreme_boost":   0.45,
        "temperature_turn_window":        5,
        "temperature_integral_window":  120,
        "temperature_integral_min_bars": 20,
        "temperature_integral_deadband": 0.12,
        "temperature_integral_divisor":  70.0,
        "temperature_integral_clip":      2.6,
        # temp4 合成
        "temperature_sum_window":   365,
        "temperature_sum_divisor": 365.0,
        "return_multiple_window":   365,
        # 仓位
        "full_position_pct":      0.98,
        "defensive_position_pct": 0.98,
        "gold_position_pct":      0.98,
        "rebalance_tolerance_pct": 0.03,
        # 轮动等待
        "nasdaq_wait_days":    400,  # 卖出创指后持有商品/城投债等待进纳指的天数
        "chuangzhi_wait_days":  20,  # 纳指切回创指前持有城投债的天数
        "max_holding_days":   1060,  # 创指最大持仓天数
        # 过热保护
        "overheating_week_threshold":      0.35,  # 相对10个交易日前涨幅触发阈值
        "overheating_month_low_threshold": 0.40,  # 相对1个月内最低点涨幅触发阈值
        "overheating_dodge_days":             7,  # 触发后临时持城投债天数（含触发当天）
        "overheating_cooldown_days":          14,  # 触发后冷静期（天），防止连续触发
    }


def required_bars(params):
    return max(
        params["anchor_ma_window"] + params["anchor_slope_window"] + 2,
        params["temperature_cycle_min_bars"] + 2,
        params["temperature_integral_min_bars"] + params["temperature_turn_window"] + 2,
        params["temperature_sum_window"] + 2,
        params["return_multiple_window"] + 2,
    )


# ==================== 每日主逻辑 ====================

def on_daily_bar(context):
    bars = get_bars_frame(g.security, g.bar_count, context.current_dt)
    if bars is None or len(bars) < 1:
        return

    features = compute_latest_features(bars, g.params)
    if features is None:
        # 预热期：数据不足，直接买入创指
        rebalance_targets(context, {g.security: g.params["full_position_pct"]},
                          g.params["rebalance_tolerance_pct"])
        if g.last_source != "warmup_buy":
            log.info("Warmup period: buying %s" % g.security)
            g.last_source = "warmup_buy"
            g.last_target_pct = g.params["full_position_pct"]
        return

    # 每周首日打印温度
    current_week = context.current_dt.isocalendar()[:2]
    if current_week != g.last_week_logged:
        log.info("Weekly temp4=%.2f  %s" % (
            features["market_temperature_score4"],
            context.current_dt.strftime("%Y-%m-%d"),
        ))
        g.last_week_logged = current_week

    # 过热规避期内用上次主逻辑目标仓位代替实际仓位（含恢复日，防状态机误判）
    today = context.current_dt.date()
    current_pct = current_position_pct(context, g.security)
    in_dodge = (g.score_dodge_end_date is not None and today <= g.score_dodge_end_date)
    effective_pct = g.last_target_pct if in_dodge else current_pct

    target_pct, source = decide_target_pct(features, effective_pct, g.params)

    # 最大持仓天数限制
    if target_pct > 0.01:
        if g.chuangzhi_buy_date is None:
            g.chuangzhi_buy_date = context.current_dt
        if (context.current_dt - g.chuangzhi_buy_date).days >= g.params["max_holding_days"]:
            log.info("达到最大持仓天数，强制卖出创指。")
            target_pct, source = 0.0, "max_holding_limit"
    else:
        g.chuangzhi_buy_date = None

    targets = _build_targets(context, target_pct, source)
    # source 可能在 _build_targets 内更新，通过返回值传出
    targets, source = targets

    # 过热保护（仅覆盖 exec_targets，不触碰 source/target_pct）
    exec_targets = _apply_overheating_guard(context, targets, today)

    rebalance_targets(context, exec_targets, g.params["rebalance_tolerance_pct"])

    # 状态更新（基于主逻辑信号，与过热规避无关）
    if abs(target_pct - g.last_target_pct) > 1e-6 or source != g.last_source:
        log.info(
            "bar=%s src=%s tgt=%.2f close=%.3f gap=%.3f t2=%.2f t3=%.2f t4=%.2f"
            % (features["date"], source, target_pct, features["close"],
               features["anchor_gap"], features["market_temperature_score2"],
               features["market_temperature_score3"], features["market_temperature_score4"])
        )
        g.last_target_pct = target_pct
        g.last_source = source

    record(
        temp2=features["market_temperature_score2"],
        temp3=features["market_temperature_score3"],
        temp4=features["market_temperature_score4"],
    )


def _build_targets(context, target_pct, source):
    """根据主信号构建目标持仓字典，返回 (targets, source)。"""
    targets = {}
    if target_pct > 0.01:
        # 信号：持仓创指
        if g.last_source == "hold_nasdaq" and g.nasdaq_sell_date is None:
            g.nasdaq_sell_date = context.current_dt
            log.info("从纳指切换为创指信号，进入观察期（持城投债）...")

        if g.nasdaq_sell_date is not None:
            days = (context.current_dt - g.nasdaq_sell_date).days
            if days >= g.params["chuangzhi_wait_days"]:
                targets[g.security] = target_pct
                g.chuangzhi_sell_date = None
                g.nasdaq_sell_date = None
            else:
                targets[g.gold_security_fallback] = g.params["gold_position_pct"]
                source = "gold_waiting_for_chuangzhi"
        else:
            targets[g.security] = target_pct
            g.chuangzhi_sell_date = None
    else:
        # 信号：清仓创指
        g.nasdaq_sell_date = None
        if g.last_target_pct > 0.01:
            g.chuangzhi_sell_date = context.current_dt
            log.info("卖出创指，进入空档期（%d 天）" % g.params["nasdaq_wait_days"])

        if g.chuangzhi_sell_date is not None:
            days = (context.current_dt - g.chuangzhi_sell_date).days
            if days >= g.params["nasdaq_wait_days"]:
                targets[g.defensive_security] = g.params["defensive_position_pct"]
                source = "hold_nasdaq"
            else:
                half = g.params["nasdaq_wait_days"] * 0.5
                sec = get_valid_security(
                    g.gold_security1 if days < half else g.gold_security2,
                    context.current_dt, g.gold_security_fallback,
                )
                targets[sec] = g.params["gold_position_pct"]
                source = "hold_gold_waiting"
        else:
            source = "stay_flat"

    return targets, source


def _apply_overheating_guard(context, targets, today):
    """
    过热保护层：对 targets 中持仓 ETF 检测两个条件（OR），任一触发则临时切城投债。
      条件1：当前价 vs 10个交易日前收盘价涨幅 > overheating_week_threshold
      条件2：当前价 vs 过去1个月(21日)最低价涨幅 > overheating_month_low_threshold
    三态：
      1. 规避中 (today < end_date)  → 持城投债
      2. 恢复日 (today == end_date) → 清除状态，恢复原目标
      3. 正常日                     → 检测涨幅（冷静期内不重触发）
    """
    dodge_days    = g.params["overheating_dodge_days"]
    cooldown_days = g.params["overheating_cooldown_days"]
    city_bond     = {g.gold_security_fallback: g.params["gold_position_pct"]}

    # 无持仓目标则直接返回
    if not any(p > 0.01 for p in targets.values()):
        return targets

    if g.score_dodge_end_date is not None and today < g.score_dodge_end_date:
        log.info("过热规避中，持城投债（恢复日: %s）" % g.score_dodge_end_date)
        return city_bond

    if g.score_dodge_end_date is not None and today == g.score_dodge_end_date:
        log.info("过热规避结束，恢复原目标")
        g.score_dodge_end_date = None
        g.score_dodge_triggered_date = None
        return targets

    # 正常日：冷静期内不检测
    cooldown_ok = (
        g.score_dodge_triggered_date is None or
        (today - g.score_dodge_triggered_date).days > cooldown_days
    )
    if not cooldown_ok:
        return targets

    # 检测持有 ETF 涨幅（任一条件成立即触发）
    threshold      = g.params["overheating_week_threshold"]
    month_low_thr  = g.params["overheating_month_low_threshold"]
    for sec, pct in targets.items():
        if pct <= 0.01:
            continue
        try:
            hist10 = attribute_history(sec, 10, "1d", ["close"])
            hist21 = attribute_history(sec, 21, "1d", ["low"])
            current_price = float(get_current_data()[sec].last_price)
            # 条件1：相对10个交易日前
            price_10d_ago = float(hist10["close"].iloc[0]) if len(hist10) >= 10 else None
            ret_10d = current_price / price_10d_ago - 1 if price_10d_ago else None
            # 条件2：相对1个月内最低点
            month_low = float(hist21["low"].min()) if len(hist21) >= 21 else None
            ret_month_low = current_price / month_low - 1 if month_low else None
        except Exception:
            ret_10d = ret_month_low = None

        trigger_reason = None
        if ret_10d is not None and ret_10d > threshold:
            trigger_reason = "10日涨幅=%.1f%% > %.0f%%" % (ret_10d * 100, threshold * 100)
        elif ret_month_low is not None and ret_month_low > month_low_thr:
            trigger_reason = "1月最低点涨幅=%.1f%% > %.0f%%" % (ret_month_low * 100, month_low_thr * 100)

        if trigger_reason:
            tdays = get_trade_days(start_date=today, end_date=None, count=dodge_days + 1)
            g.score_dodge_end_date = tdays[dodge_days] if len(tdays) > dodge_days else today
            g.score_dodge_triggered_date = today
            log.info("过热触发：%s %s，切城投债，恢复日: %s" % (sec, trigger_reason, g.score_dodge_end_date))
            return city_bond

    return targets


# ==================== 工具函数 ====================

def decide_target_pct(features, current_pct, params):
    """基于 temp4 和当前持仓判断目标仓位。"""
    if g.last_source == "flat":
        return params["full_position_pct"], "initial_buy"
    temp4 = features["market_temperature_score4"]
    if current_pct > 0.01:
        return (0.0, "clear_long") if temp4 > 3.52 else (params["full_position_pct"], "stay_long")
    else:
        return (params["full_position_pct"], "buy_in") if temp4 < -3.52 else (0.0, "stay_flat")


def get_bars_frame(security, count, end_dt):
    raw = get_bars(
        security=security, count=count, unit="1d",
        fields=["date", "close"], include_now=True,
        end_dt=end_dt, fq_ref_date=end_dt.date(),
    )
    if raw is None or len(raw) == 0:
        return None
    frame = pd.DataFrame(raw)
    if frame.empty:
        return None
    frame["date"] = pd.to_datetime(frame["date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    return frame.reset_index(drop=True)


def compute_latest_features(bars, params):
    close = bars["close"]
    ma_anchor = close.rolling(params["anchor_ma_window"]).mean()
    ma_anchor_slope = (ma_anchor / ma_anchor.shift(params["anchor_slope_window"])) - 1.0
    anchor_gap = (close / ma_anchor) - 1.0

    mp = min(int(params["temperature_cycle_min_bars"]), int(params["temperature_cycle_window"]))
    hi = close.rolling(params["temperature_cycle_window"], min_periods=mp).max()
    lo = close.rolling(params["temperature_cycle_window"], min_periods=mp).min()
    rng = (hi - lo).where(lambda s: s > 0.0)
    pos = ((close - lo) / rng).clip(0.0, 1.0).fillna(0.5)
    temp = ((pos * 2.0) - 1.0).clip(-1.0, 1.0)

    temp_slow = temp.ewm(span=params["temperature_slow_span"], min_periods=1).mean()
    heat_i = (temp > 0.8).astype(float).rolling(params["temperature_extreme_window"], min_periods=1).mean()
    cold_i = (temp < -0.8).astype(float).rolling(params["temperature_extreme_window"], min_periods=1).mean()
    boost = params["temperature_extreme_boost"]
    temp2 = (temp_slow + heat_i * boost - cold_i * boost).clip(-1.5, 1.5)
    temp2_delta = temp2 - temp2.shift(params["temperature_turn_window"])

    mp3 = min(int(params["temperature_integral_min_bars"]), int(params["temperature_integral_window"]))
    t3_src = np.sign(temp2) * np.maximum(np.abs(temp2) - params["temperature_integral_deadband"], 0.0)
    temp3 = (
        t3_src.rolling(params["temperature_integral_window"], min_periods=mp3).sum()
        / float(params["temperature_integral_divisor"])
    ).clip(-params["temperature_integral_clip"], params["temperature_integral_clip"])

    t4_raw = (temp2 + temp3).rolling(params["temperature_sum_window"], min_periods=1).sum()
    ret = (close - close.shift(params["return_multiple_window"])) / close.shift(params["return_multiple_window"])
    temp4 = t4_raw / float(params["temperature_sum_divisor"]) + temp2 * 0.5 + ret * 0.5

    latest = {
        "date":                       bars["date"].iloc[-1] if "date" in bars.columns else None,
        "close":                      float(close.iloc[-1]),
        "ma_anchor":                  float(ma_anchor.iloc[-1]),
        "anchor_gap":                 float(anchor_gap.iloc[-1]),
        "market_temperature_score":   float(temp.iloc[-1]),
        "market_temperature_score2":  float(temp2.iloc[-1]),
        "market_temperature_score2_delta": float(temp2_delta.iloc[-1]),
        "market_temperature_score3":  float(temp3.iloc[-1]),
        "market_temperature_score4":  float(temp4.iloc[-1]),
    }
    if not np.all(np.isfinite(list(latest.values())[1:])):  # skip date
        return None
    return latest


def current_position_pct(context, security):
    total = float(context.portfolio.total_value)
    if total <= 0.0:
        return 0.0
    pos = context.portfolio.positions.get(security)
    return float(pos.value) / total if pos else 0.0


def rebalance_targets(context, targets, tolerance):
    total = float(context.portfolio.total_value)
    if total <= 0.0:
        return
    norm = {s: max(0.0, min(1.0, float(p))) for s, p in targets.items()}
    for s in list(context.portfolio.positions):
        if s not in norm:
            order_target_value(s, 0)
    for s, pct in norm.items():
        if abs(current_position_pct(context, s) - pct) >= tolerance:
            order_target_value(s, total * pct)


def get_valid_security(security, current_dt, fallback):
    """若标的已上市则返回该标的，否则返回 fallback。"""
    try:
        info = get_security_info(security)
        if info and info.start_date <= current_dt.date():
            return security
    except Exception:
        pass
    return fallback
