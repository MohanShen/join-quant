# Clone from JoinQuant
# postId: 6cf38f730419f52a36b644eaa549964a
# backtestId: 95bf78374b942c75a439e0b7286714e7
# title: 发个低回撤没未来函数月度调仓的策略赚点积分

# -*- coding: utf-8 -*-
"""
红利增强 + 全天候分批减仓 + 沪深300ETF 情绪择时 —— 三腿合并回测版
=========================================================================

子组合（各 1/3 初始资金，按 context.portfolio.starting_cash 自动三等分）：
    pindex=0  红利增强策略（A 股，月初调仓，5 只红利低波 + 3 只红利价值）
    pindex=1  全天候动态再平衡 · 分批减仓（纳指/黄金/豆粕 ETF + 银华日利）
    pindex=2  沪深300ETF 情绪择时（510500 交易，000300 信号）

推荐回测：
    区间 2020-01-01 ~ 2026-10-23，初始资金 100000（每个子组合约 33333）
    基准 000300.XSHG

成本口径：
    股票腿：聚宽默认（佣金 0.03%、卖出印花税、滑点 0.246%）
    ETF 腿（全天候 + 情绪）：佣金 0.02%（最低 5 元）、无印花税、滑点 0.1%
    注：情绪策略原版是 0.0086% 佣金 / 0.04% 滑点；合并后统一用较保守的口径。

注意：
    * 三个子组合的下单都必须带 pindex，否则会落到 pindex=0。
    * 情绪腿的 510500 是原文件取值；它跟踪的是中证500，不是沪深300。
    * 情绪腿的现金预留按子组合规模的 0.2% 动态设置（最低 500 元）。
    * 合并后只能设一个基准；红利单独回测时用的是 000015。
"""

import builtins
import math

import numpy as np
import pandas as pd
from jqdata import *
from jqfactor import get_factor_values

# 聚宽的 from jqdata import * 会覆盖 sum/max/min/abs/round，恢复成 Python 原生版本
sum, max, min, abs, round = (builtins.sum, builtins.max, builtins.min,
                             builtins.abs, builtins.round)


# ======================================================================
# 情绪择时腿参数（来自 沪深300ETF 情绪择时.py）
# ======================================================================

ETF = "510500.XSHG"           # 交易标的（原文件取值；510500 实际跟踪中证500）
HS300 = "000300.XSHG"         # 信号用指数
SH, SZ = "000001.XSHG", "399001.XSHE"

POSITION_PCT = 1.0
COLD = 20
HOT = 75
REGIME_MA = 250
REGIME_BAND = 0.02
BEAR_PCT = 0.3
BEAR_COLD = 15
EXIT_MODE = "ma"
EXIT_MA = 10
PROTECT = 0.05
MIN_REBAL = 0.05

CASH_ETF = "511880.XSHG"

PCT_WINDOW, PCT_MINP = 250, 120
SCORE_SMOOTH = 3
HIST_DAYS = 520
TAIL_DAYS = 40

BREADTH_POOL = [
    "000001.XSHG", "000016.XSHG", "000300.XSHG", "000905.XSHG", "000852.XSHG",
    "000903.XSHG", "000906.XSHG", "000010.XSHG", "000009.XSHG", "000015.XSHG",
    "000922.XSHG", "399001.XSHE", "399005.XSHE", "399006.XSHE", "399106.XSHE",
    "399330.XSHE", "000986.XSHG", "000987.XSHG", "000988.XSHG", "000989.XSHG",
    "000990.XSHG", "000991.XSHG", "000992.XSHG", "000993.XSHG", "000994.XSHG",
    "000995.XSHG",
]
BREADTH_MIN = 5


# ======================================================================
# 初始化
# ======================================================================

def initialize(context):
    # 系统设置
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_benchmark("000300.XSHG")
    log.set_level("order", "error")
    log.set_level("history", "error")
    log.set_level("system", "error")

    # ETF 腿成本；股票腿不覆盖，沿用聚宽默认
    set_slippage(PriceRelatedSlippage(0.001), type="fund")
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                             open_commission=0.0002,
                             close_commission=0.0002,
                             close_today_commission=0,
                             min_commission=5), type="fund")

    # 三个子组合，各 1/3 资金
    total_cash = float(context.portfolio.starting_cash)
    cash0 = total_cash / 3.0
    cash1 = total_cash / 3.0
    cash2 = total_cash - cash0 - cash1
    set_subportfolios([
        SubPortfolioConfig(cash=cash0, type="stock"),
        SubPortfolioConfig(cash=cash1, type="stock"),
        SubPortfolioConfig(cash=cash2, type="stock"),
    ])
    g.sent_cash_reserve = max(500.0, cash2 * 0.002)
    log.info("=== 三腿合并 | 红利 %.2f | 全天候 %.2f | 情绪 %.2f ==="
             % (cash0, cash1, cash2))

    # ---------------- 红利腿状态 ----------------
    g.div_sell_list = []
    g.div_buy_df = pd.DataFrame(index=[], columns=["name", "price", "amount", "value"])
    g.div_target_num = [5, 3]
    g.div_high_limit_list = []
    g.div_hold_list = []

    # ---------------- 全天候腿参数 ----------------
    g.aw_risk_assets = [
        "513100.XSHG",  # 纳指ETF
        "518880.XSHG",  # 黄金ETF
        "159985.XSHE",  # 豆粕ETF
    ]
    g.aw_cash_etf = "511880.XSHG"  # 银华日利
    g.aw_asset_num = len(g.aw_risk_assets)
    g.aw_base_weight = 1.0 / g.aw_asset_num

    g.aw_exit_levels = [1.25, 1.30, 1.35]
    g.aw_level_weight = {
        0: 1.0,
        1: 2.0 / 3.0,
        2: 1.0 / 3.0,
        3: 0.0,
    }
    g.aw_level_hysteresis = 0.02
    g.aw_trigger_on_level_change = False

    g.aw_price_threshold = 0.10
    g.aw_ma_period = 250
    g.aw_fee_buffer = 0.998

    g.aw_level_state = {sec: 0 for sec in g.aw_risk_assets}
    g.aw_last_level_map = {sec: 0 for sec in g.aw_risk_assets}
    g.aw_last_rebalance_prices = {}
    g.aw_initialized = False
    g.aw_wait_adjust = False
    g.aw_today_level_map = {}
    g.aw_need_sell_cash_etf_value = 0
    g.aw_rebalance_count = 0

    g.aw_etf_names = {}
    for sec in g.aw_risk_assets + [g.aw_cash_etf]:
        info = get_security_info(sec)
        g.aw_etf_names[sec] = info.display_name if info else sec

    # ---------------- 情绪择时腿状态 ----------------
    g.state = 0.0        # 情绪状态：0 空仓 / 1 持仓
    g.seen = False       # 本轮是否到过高潮
    g.pk = 0.0           # 高潮以来最高收盘
    g.hot_date = None
    g.bull = True        # 牛熊状态（带缓冲带）
    g.last_w = 0.0       # 已下达的目标仓位
    g.target = None      # 今天开盘要调到的目标仓位 (w, reason, score)
    g.score = np.nan
    g.cur_round = None
    g.rounds = []
    g.fills = []
    g.breadth_pool = None

    # ---------------- 定时任务 ----------------
    # 红利腿
    run_daily(div_prepare_stock_list, "09:00")
    run_monthly(div_get_stock_list, 1, "09:01")
    run_monthly(div_trade, 1, "09:35")
    run_daily(div_check_limit_up, "10:00")
    # 情绪择时腿
    run_daily(sent_trade, "09:30", reference_security=HS300)
    # 全天候腿
    run_daily(aw_pre_adjust, "10:00")
    run_daily(aw_execute_etf_adjust, "10:10")
    # 合并报告
    run_monthly(merged_monthly_report, 1, "close")

    log.info("=== 分批减仓版 | 年线%d | 档位=%s | 滞回=%.2f | 档位触发=%s ==="
             % (g.aw_ma_period, g.aw_exit_levels, g.aw_level_hysteresis,
                g.aw_trigger_on_level_change))


# ======================================================================
# 红利增强腿（pindex=0）
# ======================================================================

def div_prepare_stock_list(context):
    """09:00：记录持仓和昨日涨停列表。"""
    g.div_high_limit_list = []
    sp = context.subportfolios[0]
    g.div_hold_list = list(sp.positions.keys())
    if len(g.div_hold_list) != 0:
        df = get_price(g.div_hold_list, end_date=context.previous_date,
                       frequency="daily", fields=["close", "high_limit"],
                       count=1, panel=False, fill_paused=False,
                       skip_paused=False).dropna()
        df = df[df["close"] == df["high_limit"]]
        g.div_high_limit_list = list(df.code)


def div_get_stock_list(context):
    """月初第一个交易日 09:01：选股并计算目标股数（全部用 T-1 数据）。"""
    g.div_buy_df = pd.DataFrame(index=[], columns=["name", "price", "amount", "value"])
    yesterday = str(context.previous_date)
    today = context.current_dt

    # 初始过滤
    initial_list = get_all_securities("stock", today).index.tolist()
    initial_list = div_filter_new_stock(context, initial_list)
    initial_list = div_filter_kcb_stock(initial_list)
    initial_list = div_filter_st_stock(initial_list)
    initial_list = div_filter_paused_stock(initial_list)

    # 红利低波
    stock_list = initial_list
    stock_list = div_get_dividend_ratio_filter_list(
        context, stock_list, False, 0.00, 0.10, 0.03)
    stock_list = div_get_factor_filter_list(
        context, stock_list, "beta", True, 0.00, 0.50)
    hldb_list = stock_list[:min(g.div_target_num[0], len(stock_list))]

    # 红利价值
    stock_list = initial_list
    df = get_fundamentals(query(
        valuation.code,
    ).filter(
        valuation.code.in_(stock_list),
        valuation.pe_ratio.between(5, 50),
        indicator.inc_return.between(5, 100),
        indicator.inc_total_revenue_year_on_year.between(5, 100),
        indicator.inc_net_profit_year_on_year.between(10, 100),
    ))
    stock_list = list(df.code)
    stock_list = div_get_dividend_ratio_filter_list(
        context, stock_list, False, 0.00, 0.10, 0.03)
    hljz_list = stock_list[:min(g.div_target_num[1], len(stock_list))]

    # 目标/卖出/买入
    target_list = list(set(hldb_list).union(set(hljz_list)))
    g.div_sell_list = [s for s in g.div_hold_list
                       if s not in target_list and s not in g.div_high_limit_list]
    buy_list = [s for s in target_list if s not in g.div_hold_list]

    # 计算下单价格与数量（T-1 收盘价；当天行情不参与）
    sp = context.subportfolios[0]
    value = sp.available_cash
    for s in g.div_sell_list:
        pos = sp.positions.get(s)
        if pos:
            value += pos.value

    if len(buy_list) > 0:
        value = value / len(buy_list)
        df = get_price(buy_list, end_date=yesterday, frequency="1d", count=1,
                       fields=["close"], fq="pre", panel=False,
                       skip_paused=False, fill_paused=True).set_index("code")
        df["today_hl_price"] = [round(df.loc[s, "close"] * 1.05, 2)
                                for s in list(df.index)]
        g.div_buy_df["name"] = [get_security_info(s, yesterday).display_name
                                for s in buy_list]
        g.div_buy_df["price"] = [df.loc[s, "today_hl_price"] for s in buy_list]
        g.div_buy_df["amount"] = [100 * int(1.05 * value
                                           / df.loc[s, "today_hl_price"] / 100)
                                  for s in buy_list]
        g.div_buy_df["value"] = g.div_buy_df["price"] * g.div_buy_df["amount"]
        g.div_buy_df.index = buy_list

    log.info("[红利] 卖出 %s" % g.div_sell_list)
    log.info("[红利] 买入 %s" % list(g.div_buy_df.index))


def div_trade(context):
    """09:35：卖出旧持仓，按限价买入新目标。"""
    current_data = get_current_data()

    for s in g.div_sell_list:
        if current_data[s].last_price < current_data[s].high_limit:
            order_target_value(s, 0, pindex=0)

    df = g.div_buy_df
    for s in list(df.index):
        log.info("[红利] 买入 %s %s" % (s, df.loc[s, "name"]))
        order(s, df.loc[s, "amount"],
              LimitOrderStyle(df.loc[s, "price"]), pindex=0)


def div_check_limit_up(context):
    """10:00：昨日涨停股若打开涨停则卖出。"""
    current_data = get_current_data()
    if g.div_high_limit_list:
        for s in g.div_high_limit_list:
            if current_data[s].last_price < current_data[s].high_limit:
                order_target_value(s, 0, pindex=0)
                log.info("[红利] %s 涨停打开，卖出" % s)


# ---------------- 红利过滤函数 ----------------

def div_filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def div_filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and "ST" not in current_data[stock].name
            and "*" not in current_data[stock].name
            and "退" not in current_data[stock].name]


def div_filter_kcb_stock(stock_list):
    return [stock for stock in stock_list
            if stock[0] not in ("4", "8") and stock[0:2] != "68"]


def div_filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list
            if not yesterday - get_security_info(stock).start_date
            < datetime.timedelta(days=250)]


def div_get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2, threshold):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365)
    interval = 1000
    list_len = len(stock_list)

    q = query(finance.STK_XR_XD.code,
              finance.STK_XR_XD.a_registration_date,
              finance.STK_XR_XD.bonus_amount_rmb).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)

    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(finance.STK_XR_XD.code,
                      finance.STK_XR_XD.a_registration_date,
                      finance.STK_XR_XD.bonus_amount_rmb).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(
                    stock_list[interval * (i + 1):
                               min(list_len, interval * (i + 2))]))
            df = df.append(finance.run_query(q))

    dividend = df.fillna(0).set_index("code").groupby("code").sum()
    temp_list = list(dividend.index)

    q = query(valuation.code, valuation.market_cap).filter(
        valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1).set_index("code")

    df = pd.concat([dividend, cap], axis=1, sort=False)
    df["dividend_ratio"] = (df["bonus_amount_rmb"] / 10000) / df["market_cap"]
    df = df.sort_values(by=["dividend_ratio"], ascending=sort)
    df = df[int(p1 * len(df)):int(p2 * len(df))]
    df = df[df["dividend_ratio"] > threshold]
    return list(df.index)


def div_get_factor_filter_list(context, stock_list, factor_name, sort, p1, p2):
    yesterday = context.previous_date
    score_list = get_factor_values(stock_list, factor_name,
                                   end_date=yesterday, count=1)[factor_name].iloc[0].tolist()
    df = pd.DataFrame(columns=["code", "score"])
    df["code"] = stock_list
    df["score"] = score_list
    df = df.dropna()
    df.sort_values(by="score", ascending=sort, inplace=True)
    return list(df.code)[int(p1 * len(df)):int(p2 * len(df))]


# ======================================================================
# 全天候分批减仓腿（pindex=1）
# ======================================================================

def aw_get_usable_price(security, lookback=5):
    cd = get_current_data()
    if security in cd:
        p = cd[security].last_price
        if p is not None and not math.isnan(p) and p > 0:
            return p
    df = attribute_history(security, lookback, "1d", "close", skip_paused=True)
    if len(df) > 0:
        return df["close"].iloc[-1]
    return None


def aw_get_ratio(security):
    df = attribute_history(security, g.aw_ma_period, "1d", "close",
                          skip_paused=True, fq="pre")
    if len(df) < g.aw_ma_period:
        return None
    ma_val = df["close"].mean()
    price = aw_get_usable_price(security)
    if price is None or ma_val <= 0:
        return None
    return price / ma_val


def aw_update_level(security, ratio):
    lvl = g.aw_level_state.get(security, 0)
    while lvl < 3 and ratio > g.aw_exit_levels[lvl]:
        lvl += 1
    while lvl > 0 and ratio < g.aw_exit_levels[lvl - 1] - g.aw_level_hysteresis:
        lvl -= 1
    g.aw_level_state[security] = lvl
    return lvl


def aw_compute_levels():
    levels = {}
    for sec in g.aw_risk_assets:
        ratio = aw_get_ratio(sec)
        if ratio is None:
            levels[sec] = g.aw_level_state.get(sec, 0)
        else:
            levels[sec] = aw_update_level(sec, ratio)
    return levels


def aw_build_target_values(total_value, level_map):
    usable = total_value * g.aw_fee_buffer
    target = {}
    for sec in g.aw_risk_assets:
        lvl = level_map.get(sec, 0)
        target[sec] = usable * g.aw_base_weight * g.aw_level_weight[lvl]
    return target


def aw_check_trigger(context):
    if not g.aw_initialized:
        return True, "首次运行，初始建仓"

    if g.aw_trigger_on_level_change:
        levels = aw_compute_levels()
        for sec in g.aw_risk_assets:
            if levels[sec] != g.aw_last_level_map.get(sec, 0):
                return True, "%s 档位变化 %d -> %d" % (
                    g.aw_etf_names[sec], g.aw_last_level_map.get(sec, 0),
                    levels[sec])

    for sec in g.aw_risk_assets:
        last_p = g.aw_last_rebalance_prices.get(sec)
        cur_p = aw_get_usable_price(sec)
        if last_p and cur_p:
            change = abs(cur_p - last_p) / last_p
            if change >= g.aw_price_threshold:
                return True, "%s 偏离上次调仓价 %.2f%%" % (
                    g.aw_etf_names[sec], change * 100)
    return False, ""


def aw_pre_adjust(context):
    """10:00：算档位、判断触发、计算资金缺口，缺钱先卖银华日利。"""
    trigger, reason = aw_check_trigger(context)
    if not trigger:
        return
    log.info("[全天候] 触发调仓：%s" % reason)

    levels = aw_compute_levels()
    for sec in g.aw_risk_assets:
        ratio = aw_get_ratio(sec)
        log.info("[全天候] 标的:%s 档位=%d ratio=%s"
                 % (g.aw_etf_names[sec], levels[sec],
                    ("%.3f" % ratio) if ratio else "NA"))
    g.aw_today_level_map = levels
    g.aw_last_level_map = dict(levels)

    sp = context.subportfolios[1]
    total_value = sp.total_value
    target_map = aw_build_target_values(total_value, levels)

    total_risk_target = 0.0
    for sec in g.aw_risk_assets:
        total_risk_target += target_map[sec]

    current_risk_value = 0.0
    for sec in g.aw_risk_assets:
        pos = sp.positions.get(sec)
        amount = pos.total_amount if pos else 0
        p = aw_get_usable_price(sec) or (pos.price if pos else 0)
        current_risk_value += amount * p

    gap = total_risk_target - current_risk_value
    g.aw_need_sell_cash_etf_value = max(0.0, gap)
    g.aw_wait_adjust = True
    g.aw_rebalance_count += 1

    if g.aw_need_sell_cash_etf_value > 100:
        p_cash = aw_get_usable_price(g.aw_cash_etf)
        if p_cash and p_cash > 0:
            sell_share = int(g.aw_need_sell_cash_etf_value / p_cash / 100) * 100
            cash_pos = sp.positions.get(g.aw_cash_etf)
            cash_amount = cash_pos.total_amount if cash_pos else 0
            sell_share = min(sell_share, cash_amount)
            if sell_share >= 100:
                o = order_target(g.aw_cash_etf, cash_amount - sell_share,
                                 pindex=1)
                if o is None:
                    log.warning("[全天候] 卖出银华日利失败")
                else:
                    log.info("[全天候] 资金缺口%.2f，卖出银华日利 %d股"
                             % (g.aw_need_sell_cash_etf_value, sell_share))


def aw_execute_etf_adjust(context):
    """10:10：把风险资产调到目标股数，剩余现金买银华日利。"""
    if not g.aw_wait_adjust:
        return
    g.aw_wait_adjust = False
    levels = g.aw_today_level_map

    sp = context.subportfolios[1]
    target_map = aw_build_target_values(sp.total_value, levels)
    cd = get_current_data()

    for sec in g.aw_risk_assets:
        if sec in cd and cd[sec].paused:
            log.warning("[全天候] %s 停牌，跳过" % g.aw_etf_names[sec])
            continue

        price = aw_get_usable_price(sec)
        if price is None or price <= 0:
            log.warning("[全天候] %s 获取价格失败，跳过" % g.aw_etf_names[sec])
            continue

        target_share = int(target_map[sec] / price / 100) * 100
        pos = sp.positions.get(sec)
        current_share = pos.total_amount if pos else 0

        if target_share <= 0:
            if current_share > 0:
                o = order_target(sec, 0, pindex=1)
                if o is None:
                    log.warning("[全天候] 清仓 %s 失败" % g.aw_etf_names[sec])
                else:
                    log.info("[全天候] 清仓：%s" % g.aw_etf_names[sec])
            continue

        if target_share != current_share:
            o = order_target(sec, target_share, pindex=1)
            if o is None:
                log.warning("[全天候] %s 调仓失败" % g.aw_etf_names[sec])
            else:
                log.info("[全天候] %s 调仓：档位%d，目标%d股，当前%d股"
                         % (g.aw_etf_names[sec], levels[sec],
                            target_share, current_share))

    if g.aw_cash_etf in cd and cd[g.aw_cash_etf].paused:
        log.warning("[全天候] 银华日利停牌，剩余现金保持不动")
    else:
        cash_left = sp.available_cash
        p_cash = aw_get_usable_price(g.aw_cash_etf)
        if p_cash and p_cash > 0:
            buy_share = int(cash_left * g.aw_fee_buffer / p_cash / 100) * 100
            if buy_share >= 100:
                cash_pos = sp.positions.get(g.aw_cash_etf)
                cash_amount = cash_pos.total_amount if cash_pos else 0
                o = order_target(g.aw_cash_etf, cash_amount + buy_share,
                                 pindex=1)
                if o is None:
                    log.warning("[全天候] 买入银华日利失败")
                else:
                    log.info("[全天候] 剩余现金%.2f，买入银华日利 %d股"
                             % (cash_left, buy_share))

    for sec in g.aw_risk_assets:
        p = aw_get_usable_price(sec)
        if p:
            g.aw_last_rebalance_prices[sec] = p
    g.aw_initialized = True


# ======================================================================
# 合并报告
# ======================================================================

def merged_monthly_report(context):
    """月初收盘：分别打印三个子组合的规模，便于和单策略回测对拍。"""
    sp0 = context.subportfolios[0]
    sp1 = context.subportfolios[1]
    sp2 = context.subportfolios[2]
    log.info("[合并] 红利 子组合 p0 总资产=%.2f 可用现金=%.2f"
             % (sp0.total_value, sp0.available_cash))
    log.info("[合并] 全天候 子组合 p1 总资产=%.2f 可用现金=%.2f 调仓次数=%d"
             % (sp1.total_value, sp1.available_cash, g.aw_rebalance_count))
    log.info("[合并] 情绪 子组合 p2 总资产=%.2f 可用现金=%.2f"
             % (sp2.total_value, sp2.available_cash))


# ======================================================================
# 情绪择时腿（pindex=2）
# ======================================================================

def _rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _pct_tail(arr, k, w=PCT_WINDOW, minp=PCT_MINP):
    """只算最后 k 个位置的滚动分位。"""
    arr = np.asarray(arr, dtype=float)
    n = len(arr)
    out = np.full(n, np.nan)
    for j in range(max(0, n - k), n):
        win = arr[max(0, j - w + 1): j + 1]
        if np.sum(~np.isnan(win)) < minp:
            continue
        last = win[-1]
        if np.isnan(last):
            continue
        hist = win[:-1]
        hist = hist[~np.isnan(hist)]
        if len(hist) == 0:
            continue
        out[j] = ((hist < last).mean() + 0.5 * (hist == last).mean()) * 100
    return out


def _get_breadth_pool(context):
    """第一次调用时检查指数池里哪些代码在聚宽有数据。"""
    if g.breadth_pool is None:
        ok = []
        for code in BREADTH_POOL:
            try:
                df = get_price(code, end_date=context.previous_date, count=5,
                               fields=["close"], skip_paused=False, panel=False)
                if df is not None and len(df) and df["close"].notna().any():
                    ok.append(code)
            except Exception:
                pass
        g.breadth_pool = ok
        log.info("[情绪] 市场宽度指数池可用 %d / %d 个"
                 % (len(ok), len(BREADTH_POOL)))
    return g.breadth_pool


def compute_sentiment(context):
    end = context.previous_date
    hs = get_price(HS300, end_date=end, count=HIST_DAYS, frequency="daily",
                   fields=["open", "close", "high", "low", "money"],
                   skip_paused=False, panel=False)
    if "time" in hs.columns:
        hs = hs.set_index("time")
    c = hs["close"]
    k = TAIL_DAYS

    f = pd.DataFrame(index=hs.index)
    f["f_rsi"] = _pct_tail(_rsi(c, 14).values, k)
    f["f_bias"] = _pct_tail((c / c.rolling(20).mean() - 1).values, k)
    f["f_ret20"] = _pct_tail(c.pct_change(20).values, k)
    hh, ll = hs["high"].rolling(60).max(), hs["low"].rolling(60).min()
    f["f_pos60"] = ((c - ll) / (hh - ll).replace(0, np.nan) * 100).clip(0, 100)

    try:
        m1 = get_price(SH, end_date=end, count=HIST_DAYS, fields=["money"],
                       skip_paused=False, panel=False)
        m2 = get_price(SZ, end_date=end, count=HIST_DAYS, fields=["money"],
                       skip_paused=False, panel=False)
        amt = pd.Series(m1["money"].values + m2["money"].values, index=hs.index)
    except Exception:
        amt = hs["money"]
    f["f_amt"] = _pct_tail((amt.rolling(5).mean() / amt.rolling(120).mean()).values, k)

    pool = _get_breadth_pool(context)
    if len(pool) >= BREADTH_MIN:
        px = get_price(pool, end_date=end, count=k + 25, fields=["close"],
                       skip_paused=False, panel=False)
        px = px.pivot(index="time", columns="code", values="close")
        ma = px.rolling(20).mean()
        above = (px > ma).astype(float)
        above[ma.isna()] = np.nan
        cnt = above.notna().sum(axis=1)
        br = above.mean(axis=1) * 100
        br[cnt < BREADTH_MIN] = np.nan
        f["f_breadth"] = br.reindex(f.index)

    tail = f.iloc[-k:]
    cols = [x for x in tail.columns if tail[x].notna().sum() > 0]
    raw = tail[cols].mean(axis=1, skipna=True)
    raw[tail[cols].notna().sum(axis=1) < max(2, len(cols) - 2)] = np.nan
    score = raw.ewm(span=SCORE_SMOOTH, adjust=False).mean() if SCORE_SMOOTH > 1 else raw
    s = score.iloc[-1] if not np.isnan(raw.iloc[-1]) else np.nan

    info = dict(close=c.iloc[-1],
                ma_exit=c.rolling(EXIT_MA).mean().iloc[-1],
                reg_ma=c.rolling(REGIME_MA).mean().iloc[-1] if REGIME_MA else np.nan,
                factors={x: tail[x].iloc[-1] for x in cols})
    return s, info


def before_trading_start(context):
    """T 日收盘数据出信号，T+1 日 09:30 执行。"""
    s, info = compute_sentiment(context)
    g.score = s
    c = info["close"]
    d = context.previous_date

    # 1) 牛熊（带缓冲带）
    if REGIME_MA and not np.isnan(info["reg_ma"]):
        if g.bull and c < info["reg_ma"] * (1 - REGIME_BAND):
            g.bull = False
        elif (not g.bull) and c > info["reg_ma"] * (1 + REGIME_BAND):
            g.bull = True
    bull = g.bull

    # 2) 情绪状态机
    reason = None
    if not np.isnan(s):
        if g.state == 0:
            th = COLD if (bull or BEAR_COLD is None) else BEAR_COLD
            if s <= th:
                g.state, g.seen, g.pk = 1.0, False, 0.0
                reason = ("情绪冰点 %.1f ≤ %s，建仓" % (s, th)) if bull else \
                         ("熊市情绪冰点 %.1f ≤ %s，%.0f%%仓位试探"
                          % (s, th, BEAR_PCT * 100))
        else:
            if EXIT_MODE == "touch":
                if s >= HOT:
                    g.state, reason = 0.0, "情绪高潮 %.1f ≥ %s，清仓" % (s, HOT)
            else:
                if s >= HOT and not g.seen:
                    g.seen, g.pk, g.hot_date = True, c, d
                if g.seen:
                    g.pk = max(g.pk, c)
                    if not np.isnan(info["ma_exit"]) and c < info["ma_exit"]:
                        g.state, reason = 0.0, (
                            "%s到过高潮，沪深300 %.0f 跌破 MA%d %.0f，清仓"
                            % (g.hot_date, c, EXIT_MA, info["ma_exit"]))
                    elif PROTECT and c < g.pk * (1 - PROTECT):
                        g.state, reason = 0.0, (
                            "%s到过高潮，沪深300 %.0f 较高点 %.0f 回撤 %.1f%%，止盈清仓"
                            % (g.hot_date, c, g.pk, (1 - c / g.pk) * 100))

    # 3) 目标仓位
    w = g.state * POSITION_PCT * (1.0 if bull else BEAR_PCT)
    g.target = None
    if abs(w - g.last_w) > 1e-9:
        if reason is None:
            if g.state > 0 and not bull:
                reason = "沪深300 %.0f 跌破年线 %.0f（转熊），降到 %.0f%% 仓位" % (
                    c, info["reg_ma"], w * 100)
            elif g.state > 0 and bull:
                reason = "沪深300 %.0f 站上年线 %.0f（转牛），加到 %.0f%% 仓位" % (
                    c, info["reg_ma"], w * 100)
            else:
                reason = "仓位调整"
        g.target = (w, reason, s)
        g.last_w = w

    record(情绪指数=s if not np.isnan(s) else 50,
           目标仓位=w * 100, 牛市=100 if bull else 0)


def _log_fill(context, o, op, reason, s):
    if o is None or o.filled == 0:
        return None
    amt = o.filled * o.price
    rec = dict(日期=str(context.current_dt.date()), 操作=op, 代码=o.security,
               成交价=round(o.price, 3), 数量=o.filled,
               成交金额=round(amt, 2), 佣金=round(o.commission, 2),
               情绪=round(s, 1) if not np.isnan(s) else None, 原因=reason)
    g.fills.append(rec)
    log.info("【情绪】%s %s %s %d股 @%.3f 金额%.0f 佣金%.2f | 情绪%s | %s"
             % (rec["日期"], op, o.security, o.filled, o.price, amt,
                o.commission, rec["情绪"], reason))
    return rec


def sent_trade(context):
    cur = get_current_data()
    pf = context.subportfolios[2]
    s = g.score

    if g.target is not None:
        w, reason, s_sig = g.target
        tv = pf.total_value
        pos = pf.positions[ETF] if ETF in pf.positions else None
        held = pos.total_amount if pos else 0
        price = cur[ETF].day_open
        cur_w = held * price / tv if tv > 0 else 0

        do_buy = w > cur_w + MIN_REBAL or (w > 0 and held == 0)
        do_sell = (w <= 0 and held > 0) or (w < cur_w - MIN_REBAL and held > 0)

        if do_buy:
            if CASH_ETF and CASH_ETF in pf.positions \
                    and pf.positions[CASH_ETF].total_amount > 0:
                order_target(CASH_ETF, 0, pindex=2)
            target_val = (w * pf.total_value
                          - g.sent_cash_reserve * (1 if w >= 0.999 else 0))
            before = held
            o = order_target_value(ETF, max(target_val, 0), pindex=2)
            r = _log_fill(context, o,
                          "买入·建仓" if before == 0 else "买入·加仓",
                          reason, s_sig)
            if r:
                _round_buy(context, o)
        elif do_sell:
            o = order_target_value(ETF, 0 if w <= 0 else w * pf.total_value,
                                   pindex=2)
            after = pf.positions[ETF].total_amount if ETF in pf.positions else 0
            r = _log_fill(context, o,
                          "卖出·清仓" if after == 0 else "卖出·减仓",
                          reason, s_sig)
            if r:
                _round_sell(context, o, reason, after == 0)

    # 闲置资金买货币 ETF（按子组合规模，至少 1 手）
    if CASH_ETF:
        cash = pf.available_cash - g.sent_cash_reserve
        p = cur[CASH_ETF].day_open
        if cash > p * 100 * 1.05 and not cur[CASH_ETF].paused:
            order_value(CASH_ETF, cash * 0.99, pindex=2)


def _round_buy(context, o):
    cost = o.filled * o.price + o.commission
    if g.cur_round is None:
        g.cur_round = dict(start=str(context.current_dt.date()),
                           cost_basis=0.0, peak=0.0, realized=0.0,
                           buys=0, sells=0,
                           entry_score=g.target[2] if g.target else np.nan)
    r = g.cur_round
    r["cost_basis"] += cost
    r["peak"] = max(r["peak"], r["cost_basis"])
    r["buys"] += 1
    r["shares"] = r.get("shares", 0) + o.filled


def _round_sell(context, o, reason, closed):
    r = g.cur_round
    if r is None:
        return
    proceeds = o.filled * o.price - o.commission
    part_cost = r["cost_basis"] * o.filled / max(r["shares"], 1)
    r["realized"] += proceeds - part_cost
    r["cost_basis"] -= part_cost
    r["shares"] -= o.filled
    r["sells"] += 1
    if closed:
        g.rounds.append(dict(轮次=len(g.rounds) + 1, 首次买入=r["start"],
                             清仓=str(context.current_dt.date()),
                             买卖次数="%d/%d" % (r["buys"], r["sells"]),
                             最大占用=round(r["peak"]),
                             盈亏=round(r["realized"]),
                             收益率=r["realized"] / r["peak"],
                             入场情绪=r["entry_score"], 出场原因=reason))
        g.cur_round = None


def on_strategy_end(context):
    log.info("=" * 30 + " 情绪腿每轮交易统计 " + "=" * 30)
    for r in g.rounds:
        log.info("第%2d轮 %s → %s 买/卖%s 最大占用%12s 盈亏%12s 收益率%7.2f%% | %s"
                 % (r["轮次"], r["首次买入"], r["清仓"], r["买卖次数"],
                    format(r["最大占用"], ","), format(r["盈亏"], ","),
                    r["收益率"] * 100, r["出场原因"]))
    if g.cur_round:
        log.info("期末仍持仓：%s 起，买%d次"
                 % (g.cur_round["start"], g.cur_round["buys"]))
    rets = np.array([r["收益率"] for r in g.rounds])
    if len(rets):
        win, loss = rets[rets > 0], rets[rets <= 0]
        pl = (win.mean() / abs(loss.mean())) if len(win) and len(loss) else float("inf")
        log.info("已平仓 %d 轮 | 胜率 %.1f%% (盈%d 亏%d) | 均盈 %.2f%% 均亏 %.2f%% | 盈亏比 %.2f"
                 % (len(rets), len(win) / len(rets) * 100, len(win), len(loss),
                    win.mean() * 100 if len(win) else 0,
                    loss.mean() * 100 if len(loss) else 0, pl))
    log.info("情绪腿交割单共 %d 笔（不含货币ETF）：" % len(g.fills))
