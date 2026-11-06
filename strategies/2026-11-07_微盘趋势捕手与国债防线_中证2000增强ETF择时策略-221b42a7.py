# Clone from JoinQuant
# postId: 221b42a7ac1e8060d4ba946b8a9155cd
# backtestId: 39d9abd852a0c56895a40516880ffeca
# title: 微盘趋势捕手与国债防线——中证2000增强ETF择时策略

# -*- coding: utf-8 -*-
"""
中证2000增强ETF · 趋势打分择时策略（完美复现版）
================================================================
核心修正：
  1. 拟合权重改为指数衰减（0.7的幂），对近期价格波动极其敏感。
  2. 修正持仓期与止损的优先级：触发止损时无视最小持有天数，立即斩仓。
  3. 解决日线回测中“14:30”获取收盘价带未来函数的隐患，改为获取昨日收盘价拼接当前实时价。
================================================================
"""

from jqdata import *
import numpy as np
import datetime


# ==============================================================
# 一、参数配置
# ==============================================================
class Cfg(object):
    RISK_SEC   = "159552.XSHE"   # 中证2000增强ETF
    DEF_SEC    = "511260.XSHG"   # 十年国债ETF

    # ---------- 趋势打分 ----------
    FIT_N        = 10            # 拟合窗口
    ANNUAL_FACTOR = 250          # 斜率年化因子
    SCORE_LOWER  = 0.4           # 入场得分下限
    SCORE_UPPER  = 2.5           # 入场得分上限
    MA_N         = 10            # 均线窗口
    DECAY_FACTOR = 0.7           # 拟合权重衰减因子（近期权重高）

    # ---------- 持仓约束 ----------
    MIN_HOLD_DAYS = 5            # 最小持有交易日数
    STOP_LOSS_PCT = 0.05         # 止损阈值（成本/高水位通用）
    COOLDOWN_DAYS = 5            # 止损后冷却交易日数

    # ---------- 执行 ----------
    LOT = 100
    MIN_ORDER = 100
    CASH_BUFFER = 0.995

    NAME = {
        "159552.XSHE": "中证2000增强ETF",
        "511260.XSHG": "十年国债ETF",
    }

    @classmethod
    def name_of(cls, sec):
        return cls.NAME.get(sec, sec)


# ==============================================================
# 二、初始化
# ==============================================================
def initialize(context):
    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)
    set_option("avoid_future_data", True)
    log.set_level("order", "warning")

    set_order_cost(
        OrderCost(
            open_tax=0, close_tax=0,
            open_commission=0.00005, close_commission=0.00005,
            close_today_commission=0, min_commission=0,
        ),
        type="fund",
    )

    g.start_value = context.portfolio.starting_cash
    g.prev_total_value = context.portfolio.starting_cash

    g.holding = "DEFENSE"        # RISK / DEFENSE
    g.entry_date = None          
    g.avg_cost = None            
    g.high_water = None          
    g.cooldown_until = None      

    g.trade_count = 0
    g.stop_loss_count = 0

    run_daily(execute_strategy, time="14:30")
    run_daily(after_trading_end, time="15:30")

    log.info("【策略初始化】进攻=%s  防守=%s", Cfg.RISK_SEC, Cfg.DEF_SEC)
    log.info("【参数】拟合%d日  得分(%.1f, %.1f)  MA%d  最小持有%d日  止损%.0f%%",
             Cfg.FIT_N, Cfg.SCORE_LOWER, Cfg.SCORE_UPPER,
             Cfg.MA_N, Cfg.MIN_HOLD_DAYS, Cfg.STOP_LOSS_PCT * 100)


# ==============================================================
# 三、趋势打分引擎
# ==============================================================
def _get_closes_with_realtime(sec, n):
    """获取历史收盘价，并将最后一天替换为当前实时价（避免14:30带未来函数）"""
    try:
        df = attribute_history(sec, n, "1d", ["close"], fq="pre", df=True)
        if df is None or len(df) < n:
            return None
        closes = df["close"].values.astype(float)
        
        # 获取当前价格替换最后一天
        px = get_valid_price(sec)
        if px is not None:
            closes[-1] = px
        return closes
    except Exception as e:
        log.error("【数据】%s 获取失败: %s", sec, e)
        return None


def compute_trend_score(closes):
    n = Cfg.FIT_N
    if closes is None or len(closes) < n:
        return None, None, None

    y = np.log(closes[-n:])
    x = np.arange(n, dtype=float)
    
    # 指数衰减权重：越靠近今天，权重越大。最近一天的权重为1.0，最远的为 (0.7)^9
    w = np.power(Cfg.DECAY_FACTOR, np.arange(n-1, -1, -1), dtype=float)

    sw = np.sum(w)
    x_bar = np.sum(w * x) / sw
    y_bar = np.sum(w * y) / sw

    num = np.sum(w * (x - x_bar) * (y - y_bar))
    den = np.sum(w * (x - x_bar) ** 2)
    if den <= 0:
        return None, None, None

    slope = num / den
    intercept = y_bar - slope * x_bar

    y_hat = slope * x + intercept
    sst = np.sum(w * (y - y_bar) ** 2)
    sse = np.sum(w * (y - y_hat) ** 2)
    r2 = 1.0 - sse / sst if sst > 0 else 0.0
    r2 = max(r2, 0.0)

    score = slope * Cfg.ANNUAL_FACTOR * r2
    return float(score), float(slope), float(r2)


def check_entry(context):
    closes = _get_closes_with_realtime(Cfg.RISK_SEC, max(Cfg.FIT_N, Cfg.MA_N) + 5)
    if closes is None:
        return False

    px = float(closes[-1])
    ma = float(np.mean(closes[-Cfg.MA_N:]))
    score, slope, r2 = compute_trend_score(closes)

    if score is None:
        return False

    ok = (Cfg.SCORE_LOWER < score < Cfg.SCORE_UPPER) and (px > ma)
    if ok:
        log.info("【入场信号】得分 %.4f  斜率 %.6f  R2 %.4f  价格 %.3f  MA10 %.3f",
                 score, slope, r2, px, ma)
    return ok


def check_exit(context):
    closes = _get_closes_with_realtime(Cfg.RISK_SEC, max(Cfg.FIT_N, Cfg.MA_N) + 5)
    if closes is None:
        return False

    px = float(closes[-1])
    ma = float(np.mean(closes[-Cfg.MA_N:]))
    score, _, _ = compute_trend_score(closes)

    if score is None:
        return False

    exit_signal = (score <= Cfg.SCORE_LOWER) or (score >= Cfg.SCORE_UPPER) or (px <= ma)
    if exit_signal:
        log.info("【正常退出】得分 %.4f  价格 %.3f  MA10 %.3f", score, px, ma)
    return exit_signal


# ==============================================================
# 四、主执行引擎
# ==============================================================
def execute_strategy(context):
    date = context.current_dt.date()
    port = context.portfolio
    risk_pos = port.positions.get(Cfg.RISK_SEC, None)
    risk_amt = risk_pos.total_amount if risk_pos else 0

    # ---------- 持有风险资产 ----------
    if g.holding == "RISK" and risk_amt > 0:
        px = get_valid_price(Cfg.RISK_SEC)
        if px is None:
            return

        if g.high_water is None or px > g.high_water:
            g.high_water = px

        # 1. 止损检查（优先级最高，无视最小持有期）
        stop_cost = g.avg_cost is not None and px < g.avg_cost * (1 - Cfg.STOP_LOSS_PCT)
        stop_high = g.high_water is not None and px < g.high_water * (1 - Cfg.STOP_LOSS_PCT)

        if stop_cost or stop_high:
            reason = "成本止损" if stop_cost else "高水位止损"
            _switch_to_defense(context, reason)
            g.stop_loss_count += 1
            g.cooldown_until = _add_trade_days(date, Cfg.COOLDOWN_DAYS)
            log.info("【触发止损】%s  冷却至 %s", reason, g.cooldown_until)
            return

        # 2. 最小持有期检查
        held_days = _trade_days_between(g.entry_date, date) if g.entry_date else 0
        if held_days < Cfg.MIN_HOLD_DAYS:
            return

        # 3. 正常退出检查
        if check_exit(context):
            _switch_to_defense(context, "趋势失效")
        return

    # ---------- 持有防守资产 ----------
    if g.holding == "DEFENSE":
        def_pos = port.positions.get(Cfg.DEF_SEC, None)
        if not def_pos or def_pos.total_amount == 0:
            _buy_defense(context)
            return

        if g.cooldown_until is not None and date < g.cooldown_until:
            return

        if check_entry(context):
            _switch_to_risk(context)


# ==============================================================
# 五、切换执行
# ==============================================================
def _buy_defense(context):
    date = context.current_dt.strftime("%Y-%m-%d")
    port = context.portfolio
    px = get_valid_price(Cfg.DEF_SEC)
    if px is None:
        return
    target_amt = int(port.total_value * Cfg.CASH_BUFFER / (px * Cfg.LOT)) * Cfg.LOT
    cur = port.positions.get(Cfg.DEF_SEC, None)
    delta = target_amt - (cur.total_amount if cur else 0)
    if delta >= Cfg.MIN_ORDER:
        order(Cfg.DEF_SEC, delta)
        log.info("【%s 买入防守】%s %d 份", date, Cfg.name_of(Cfg.DEF_SEC), delta)
    g.holding = "DEFENSE"


def _switch_to_defense(context, reason):
    date = context.current_dt.strftime("%Y-%m-%d")
    port = context.portfolio

    risk_pos = port.positions.get(Cfg.RISK_SEC, None)
    if risk_pos and risk_pos.closeable_amount > 0:
        order(Cfg.RISK_SEC, -risk_pos.closeable_amount)
        log.info("【%s 卖出风险】%s %d 份  原因:%s",
                 date, Cfg.name_of(Cfg.RISK_SEC), risk_pos.closeable_amount, reason)

    px = get_valid_price(Cfg.DEF_SEC)
    if px is None:
        return
    target_amt = int(port.total_value * Cfg.CASH_BUFFER / (px * Cfg.LOT)) * Cfg.LOT
    cur = port.positions.get(Cfg.DEF_SEC, None)
    delta = target_amt - (cur.total_amount if cur else 0)
    if delta >= Cfg.MIN_ORDER:
        order(Cfg.DEF_SEC, delta)
        log.info("【%s 买入防守】%s %d 份", date, Cfg.name_of(Cfg.DEF_SEC), delta)

    g.holding = "DEFENSE"
    g.entry_date = None
    g.avg_cost = None
    g.high_water = None
    g.trade_count += 1


def _switch_to_risk(context):
    date = context.current_dt.strftime("%Y-%m-%d")
    port = context.portfolio

    def_pos = port.positions.get(Cfg.DEF_SEC, None)
    if def_pos and def_pos.closeable_amount > 0:
        order(Cfg.DEF_SEC, -def_pos.closeable_amount)
        log.info("【%s 卖出防守】%s %d 份",
                 date, Cfg.name_of(Cfg.DEF_SEC), def_pos.closeable_amount)

    px = get_valid_price(Cfg.RISK_SEC)
    if px is None:
        return
    target_amt = int(port.total_value * Cfg.CASH_BUFFER / (px * Cfg.LOT)) * Cfg.LOT
    cur = port.positions.get(Cfg.RISK_SEC, None)
    delta = target_amt - (cur.total_amount if cur else 0)
    
    if delta >= Cfg.MIN_ORDER:
        order(Cfg.RISK_SEC, delta)
        log.info("【%s 买入风险】%s %d 份  价格 %.3f",
                 date, Cfg.name_of(Cfg.RISK_SEC), delta, px)
        g.holding = "RISK"
        g.entry_date = context.current_dt.date()
        g.avg_cost = px
        g.high_water = px
        g.trade_count += 1


# ==============================================================
# 六、辅助工具
# ==============================================================
def get_valid_price(sec):
    try:
        cd = get_current_data()[sec]
        if getattr(cd, "paused", False):
            return None
        px = cd.last_price
        if px is not None and np.isfinite(px) and px > 0:
            return float(px)
    except Exception:
        pass
    try:
        df = attribute_history(sec, 1, "1d", ["close"], fq="pre", df=True)
        if df is not None and len(df) > 0:
            px = float(df["close"].iloc[-1])
            if np.isfinite(px) and px > 0:
                return px
    except Exception:
        pass
    return None


def _trade_days_between(start_date, end_date):
    try:
        days = get_trade_days(start_date=start_date, end_date=end_date)
        return len(days) - 1
    except Exception:
        return 0


def _add_trade_days(start_date, n):
    try:
        days = get_trade_days(start_date=start_date, count=n + 1)
        return days[-1]
    except Exception:
        return start_date + datetime.timedelta(days=n * 2)


# ==============================================================
# 七、收盘总结
# ==============================================================
def after_trading_end(context):
    date = context.current_dt.strftime("%Y-%m-%d")
    port = context.portfolio
    total = port.total_value
    prev = g.prev_total_value if g.prev_total_value else total
    daily_pnl = total - prev
    daily_ret = daily_pnl / prev * 100 if prev > 0 else 0.0
    cum_ret = (total - g.start_value) / g.start_value * 100 if g.start_value > 0 else 0.0
    g.prev_total_value = total

    lines = [
        "",
        "=" * 66,
        "  【每日收盘总结】  %s" % date,
        "-" * 66,
        "  账户总资产 : %14.2f 元" % total,
        "  当日盈亏   : %+14.2f 元  (%+.3f%%)" % (daily_pnl, daily_ret),
        "  累计收益   : %+14.2f%%" % cum_ret,
        "-" * 66,
        "  当前状态   : %s" % ("进攻（中证2000）" if g.holding == "RISK" else "防守（国债）"),
        "  累计切换   : %d 次   止损次数: %d 次" % (g.trade_count, g.stop_loss_count),
    ]
    if g.high_water is not None:
        lines.append("  持仓高水位 : %.3f" % g.high_water)
    if g.cooldown_until is not None:
        lines.append("  冷却期至   : %s" % g.cooldown_until)
    lines.append("=" * 66)

    log.info("\n".join(lines))