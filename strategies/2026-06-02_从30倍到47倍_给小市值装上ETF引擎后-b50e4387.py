# Clone from JoinQuant
# postId: b50e4387c814d47c1b7ce93e38da9cd8
# backtestId: 201a6cbce5bef24329b312f4ca36b820
# title: 从30倍到47倍：给小市值装上ETF引擎后

import numpy as np
import pandas as pd
import math
import datetime
from datetime import timedelta
from jqdata import *
from jqfactor import *

# ==================== 全局初始化 ====================
def initialize(context):
    # 回测基础设置
    set_option("avoid_future_data", True)
    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)

    # 滑点和佣金（股票和ETF分开设置）
    set_slippage(FixedSlippage(0.002), type="stock")
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    cost_configs = [
        ("stock", 0.0005, 0.85 / 10000, 5),
        ("fund", 0, 0.5 / 10000, 5),
        ("mmf", 0, 0, 0),
    ]
    for asset_type, close_tax, commission, min_comm in cost_configs:
        set_order_cost(
            OrderCost(
                open_tax=0,
                close_tax=close_tax,
                open_commission=commission,
                close_commission=commission,
                close_today_commission=0,
                min_commission=min_comm,
            ),
            type=asset_type,
        )

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')

    # 资金分配比例
    g.portfolio_value_proportion = [0.5, 0.5]  # 策略1:小市值, 策略2:五福ETF
    g.starting_cash = context.portfolio.total_value
    g.xsz_starting_cash = g.starting_cash * g.portfolio_value_proportion[0]
    g.etf_starting_cash = g.starting_cash * g.portfolio_value_proportion[1]

    # 初始化子策略收益记录
    g.run_days = 0
    g.sub_strategy_records = {
        'strategy1': {  # 小市值
            'name': '小市值',
            'initial_cash': g.xsz_starting_cash,
            'daily_values': [],
            'daily_dates': [],
            'daily_returns': []
        },
        'strategy2': {  # 五福ETF
            'name': '五福ETF',
            'initial_cash': g.etf_starting_cash,
            'daily_values': [],
            'daily_dates': [],
            'daily_returns': []
        }
    }

    # 设置子账户
    set_subportfolios([
        SubPortfolioConfig(cash=g.xsz_starting_cash, type='stock'),  # 策略1: 小市值
        SubPortfolioConfig(cash=g.etf_starting_cash, type='stock'),  # 策略2: 五福ETF
    ])

    # 初始化两个子策略
    xsz_initialize(context)
    etf_initialize(context)

    # 每日收盘后记录收益
    run_daily(record_daily_performance, 'after_close')

def get_sub_portfolio(context, pindex):
    return context.subportfolios[pindex]

def record_daily_performance(context):
    """记录每日各子策略收益"""
    try:
        g.run_days += 1
        current_date = context.current_dt.date()
        records_to_log = {}

        for i, strategy_key in enumerate(['strategy1', 'strategy2']):
            sub_portfolio = context.subportfolios[i]
            strategy_info = g.sub_strategy_records[strategy_key]

            initial_cash = strategy_info['initial_cash']
            current_value = sub_portfolio.total_value

            strategy_info['daily_values'].append(current_value)
            strategy_info['daily_dates'].append(current_date)

            cumulative_return = (current_value / initial_cash - 1) * 100
            strategy_info['daily_returns'].append(cumulative_return)
            records_to_log[strategy_info['name']] = cumulative_return

            # 限制历史记录长度（252个交易日）
            MAX_HISTORY = 252
            if len(strategy_info['daily_values']) > MAX_HISTORY:
                strategy_info['daily_values'] = strategy_info['daily_values'][-MAX_HISTORY:]
                strategy_info['daily_dates'] = strategy_info['daily_dates'][-MAX_HISTORY:]
                strategy_info['daily_returns'] = strategy_info['daily_returns'][-MAX_HISTORY:]

        record(**records_to_log)

    except Exception as e:
        log.error(f"记录每日收益时出错: {e}")

# ==================== 策略1：小市值（原代码完整，日志增加前缀“小市值：”） ====================
def xsz_initialize(context):
    """小市值策略初始化"""
    # ========== 策略参数 ==========
    g.xsz_huanshou_check = False          # 放量换手检测
    g.xsz_enable_dynamic_stock_num = True # 动态选股数量 3~6
    g.xsz_stock_num = 5                   # 默认持股数
    g.xsz_yesterday_HL_list = []          # 昨日涨停股票
    g.xsz_target_list = []                # 目标持仓股票
    g.xsz_buy_etf = "511880.XSHG"         # 空仓时购买ETF

    # 动态资金管理
    g.xsz_enable_dynamic_position = False
    g.xsz_volatility_lookback = 20
    g.xsz_base_position_ratio = 1.0
    g.xsz_volatility_threshold_low = 0.015
    g.xsz_volatility_threshold_high = 0.035
    g.xsz_position_ratio_min = 0.5
    g.xsz_position_ratio_max = 1.0

    # 止损检查
    g.xsz_run_stoploss = True
    g.xsz_stoploss_limit = 0.09
    g.xsz_stoploss_market = 0.05

    # ATR动态止损
    g.xsz_enable_atr_stop_loss = True
    g.xsz_atr_period = 14
    g.xsz_atr_multiplier = 2.0
    g.xsz_atr_stop_prices = {}

    # 成本保护止损
    g.xsz_enable_cost_protection = True
    g.xsz_cost_protection_profit_threshold_1 = 0.15
    g.xsz_cost_protection_profit_threshold_2 = 0.30
    g.xsz_cost_protection_stop_line_1 = 0.00
    g.xsz_cost_protection_stop_line_2 = 0.10

    # 一致性风控
    g.xsz_enable_consistency_control = False
    g.xsz_consistency_signal = False
    g.xsz_consistency_boll_period = 120
    g.xsz_consistency_threshold_mean = 0.8
    g.xsz_consistency_threshold_std = 0.05
    g.xsz_mini_cosi_list = []

    # 异常处理窗口期
    g.xsz_check_after_no_buy = True
    g.xsz_no_buy_stocks = {}
    g.xsz_no_buy_after_day = 2

    # 顶背离检查
    g.xsz_DBL_control = True
    g.xsz_dbl = []
    g.xsz_check_macd_divergence_days = 10

    # ========== 定时任务 ==========
    run_daily(xsz_prepare_strategy, "9:05")
    if g.xsz_DBL_control:
        run_daily(xsz_check_macd_divergence, "9:31")
    run_weekly(xsz_strategy_sell, 2, "09:40")
    run_weekly(xsz_strategy_buy, 2, "09:45")
    run_daily(xsz_sell_stocks, time="10:00")
    if g.xsz_enable_atr_stop_loss:
        run_daily(xsz_update_atr_stop_prices, "10:30")
        run_daily(xsz_update_atr_stop_prices, "14:00")
    if g.xsz_huanshou_check:
        run_daily(xsz_check_turnover, "10:30")
    run_daily(xsz_check_limit_up, "14:00")

    log.info("小市值：小市值策略初始化完成")

def xsz_prepare_strategy(context):
    if g.xsz_enable_consistency_control:
        g.xsz_consistency_signal = xsz_mini_consistency_check(context, g.xsz_consistency_signal)
    g.xsz_yesterday_HL_list = []
    stock_list = list(get_sub_portfolio(context, 0).positions.keys())
    if stock_list:
        df = get_price(stock_list, end_date=context.previous_date,
                       fields=["close", "high_limit", "low_limit"],
                       frequency="daily", count=1, panel=False, fill_paused=False)
        g.xsz_yesterday_HL_list = list(df[df["close"] == df["high_limit"]].code)

def xsz_mini_consistency_check(context, signal):
    today_date = context.current_dt.date()
    last_date = context.previous_date
    all_data = get_current_data()
    stock_list = list(get_all_securities(["stock"]).index)
    total_stock_cnt = len(stock_list)
    stock_list = [code for code in stock_list if not all_data[code].paused]
    stock_list = [code for code in stock_list if not all_data[code].is_st]
    stock_list = [code for code in stock_list if "退" not in all_data[code].name]
    stock_list = [code for code in stock_list if code[0:3] != "688"]
    stock_list = [code for code in stock_list if (today_date - get_security_info(code).start_date).days > 20]

    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(stock_list)).order_by(valuation.market_cap.asc())
    df_val = get_fundamentals(q)
    sample_stock_cnt = round(0.05 * total_stock_cnt)
    stock_list = list(df_val["code"])[:sample_stock_cnt]

    df_chg = get_money_flow(stock_list, end_date=last_date, fields="change_pct", count=1)
    chg_med = np.median(df_chg.change_pct)
    chg_std = np.std(df_chg.change_pct)
    df_temp = df_chg[(df_chg.change_pct < (chg_med + chg_std)) & (df_chg.change_pct > (chg_med - chg_std))]
    consistency_stock_cnt = len(df_temp)
    consistency_last = consistency_stock_cnt / sample_stock_cnt
    g.xsz_mini_cosi_list.append(consistency_last)

    df_index = get_price("399101.XSHE", end_date=last_date, frequency="1d", fields="close", count=250, panel=False)
    if df_index["close"].values[-1] > df_index["close"].values.mean():
        return False

    if len(g.xsz_mini_cosi_list) >= g.xsz_consistency_boll_period:
        cosistency_mean = np.mean(g.xsz_mini_cosi_list[-g.xsz_consistency_boll_period:])
        cosistency_std = np.std(g.xsz_mini_cosi_list[-g.xsz_consistency_boll_period:])
    else:
        cosistency_mean = g.xsz_consistency_threshold_mean
        cosistency_std = g.xsz_consistency_threshold_std
    cosistency_upper = cosistency_mean + cosistency_std

    if chg_med < -2 and consistency_last >= cosistency_upper:
        return True
    elif chg_med > 2 and consistency_last >= cosistency_mean:
        return False
    else:
        return signal

def xsz_calculate_market_volatility(context):
    index_code = "000300.XSHG"
    df = get_price(index_code, end_date=context.previous_date, count=g.xsz_volatility_lookback + 1,
                   frequency="daily", fields=["close"])
    if len(df) < g.xsz_volatility_lookback:
        return None
    returns = df["close"].pct_change().dropna()
    return returns.std()

def xsz_calculate_dynamic_position_ratio(context):
    if not g.xsz_enable_dynamic_position:
        return g.xsz_base_position_ratio
    volatility = xsz_calculate_market_volatility(context)
    if volatility is None:
        return g.xsz_base_position_ratio
    if volatility < g.xsz_volatility_threshold_low:
        return g.xsz_position_ratio_max
    elif volatility > g.xsz_volatility_threshold_high:
        return g.xsz_position_ratio_min
    else:
        ratio_range = g.xsz_position_ratio_max - g.xsz_position_ratio_min
        volatility_range = g.xsz_volatility_threshold_high - g.xsz_volatility_threshold_low
        return g.xsz_position_ratio_max - ((volatility - g.xsz_volatility_threshold_low) / volatility_range * ratio_range)

def xsz_calculate_atr(security, context, period=14):
    df = get_price(security, end_date=context.previous_date, count=period + 1,
                   frequency="daily", fields=["high", "low", "close"])
    if len(df) < period + 1:
        return None
    df["pre_close"] = df["close"].shift(1)
    df["tr1"] = df["high"] - df["low"]
    df["tr2"] = abs(df["high"] - df["pre_close"])
    df["tr3"] = abs(df["low"] - df["pre_close"])
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
    return df["tr"].iloc[-period:].mean()

def xsz_update_atr_stop_prices(context):
    if not g.xsz_enable_atr_stop_loss:
        return
    current_positions = get_sub_portfolio(context, 0).positions
    for stock in current_positions.keys():
        if stock in current_positions:
            if stock not in g.xsz_atr_stop_prices:
                atr = xsz_calculate_atr(stock, context, g.xsz_atr_period)
                if atr:
                    avg_cost = current_positions[stock].avg_cost
                    stop_price = avg_cost - (g.xsz_atr_multiplier * atr)
                    g.xsz_atr_stop_prices[stock] = stop_price
            else:
                current_price = current_positions[stock].price
                atr = xsz_calculate_atr(stock, context, g.xsz_atr_period)
                if atr:
                    trailing_stop = current_price - (g.xsz_atr_multiplier * atr)
                    if trailing_stop > g.xsz_atr_stop_prices[stock]:
                        g.xsz_atr_stop_prices[stock] = trailing_stop

def xsz_check_atr_stop_loss(context):
    if not g.xsz_enable_atr_stop_loss:
        return
    current_positions = get_sub_portfolio(context, 0).positions
    for stock in list(current_positions.keys()):
        if stock in current_positions and stock in g.xsz_atr_stop_prices:
            current_price = current_positions[stock].price
            stop_price = g.xsz_atr_stop_prices[stock]
            if current_price <= stop_price:
                avg_cost = current_positions[stock].avg_cost
                loss_pct = (current_price - avg_cost) / avg_cost * 100
                log.warn(f"小市值：[小市值-ATR止损] {xsz_format_stock_code(stock)} 触发止损 亏损: {loss_pct:.2f}%")
                xsz_close_position(stock, context)
                if g.xsz_check_after_no_buy:
                    g.xsz_no_buy_stocks[stock] = context.current_dt.date()
                del g.xsz_atr_stop_prices[stock]

def xsz_strategy_sell(context):
    log.info("小市值：" + "=" * 100)
    log.info(f"小市值：[小市值-卖出] 日期: {context.current_dt.date()}")
    g.xsz_target_list = []

    if g.xsz_enable_consistency_control and g.xsz_consistency_signal:
        log.warn("小市值：[小市值] 一致性风控触发清仓信号，暂停调仓")
        return
    if g.xsz_DBL_control:
        if len(g.xsz_dbl) < 10:
            for i in range(9, -1, -1):
                xsz_check_macd_divergence(context, end_days=0 - i)
    if g.xsz_DBL_control and 1 in g.xsz_dbl[-g.xsz_check_macd_divergence_days:]:
        log.warn(f"小市值：[小市值] 近{g.xsz_check_macd_divergence_days}日检测到大盘顶背离，暂停调仓")
        return

    diff = None
    if g.xsz_enable_dynamic_stock_num:
        ma_para = 10
        today = context.previous_date
        start_date = today - timedelta(days=ma_para * 2)
        index_df = get_price("399101.XSHE", start_date=start_date, end_date=today, frequency="daily")
        index_df["ma"] = index_df["close"].rolling(window=ma_para).mean()
        last_row = index_df.iloc[-1]
        diff = last_row["close"] - last_row["ma"]
        if diff >= 200:
            g.xsz_stock_num = 3
        elif diff >= -200:
            g.xsz_stock_num = 4
        elif diff >= -500:
            g.xsz_stock_num = 5
        else:
            g.xsz_stock_num = 6

    g.xsz_target_list = xsz_get_small_cap_stocks(context)[:g.xsz_stock_num]

    log.info(f"小市值：[小市值] 目标持股数: {g.xsz_stock_num} [diff:{str(diff)[:6]}] 目标持仓: {g.xsz_target_list}")

    sell_list = [s for s in get_sub_portfolio(context, 0).positions if s not in g.xsz_target_list and s not in g.xsz_yesterday_HL_list]
    hold_list = [s for s in get_sub_portfolio(context, 0).positions if s in g.xsz_target_list or s in g.xsz_yesterday_HL_list]
    if sell_list:
        if hold_list:
            log.info(f"小市值：[小市值] 当前持有: {[xsz_format_stock_code(stock) for stock in hold_list]}")
        log.info(f"小市值：[小市值] 计划卖出: {[xsz_format_stock_code(stock) for stock in sell_list]}")
    for stock in sell_list:
        xsz_close_position(stock, context)

def xsz_strategy_buy(context):
    if g.xsz_enable_consistency_control and g.xsz_consistency_signal:
        log.warn("小市值：[小市值] 一致性风控触发清仓信号，暂停买入")
        return

    position_ratio = xsz_calculate_dynamic_position_ratio(context)
    strategy_value = get_sub_portfolio(context, 0).total_value * position_ratio
    current_value = sum([pos.value for pos in get_sub_portfolio(context, 0).positions.values()])
    available_cash = max(0, strategy_value - current_value)

    buy_list = [s for s in g.xsz_target_list if s not in get_sub_portfolio(context, 0).positions]
    if buy_list and available_cash > 0:
        cash_per_stock = available_cash / len(buy_list)
        for stock in buy_list:
            xsz_open_position(context, stock, cash_per_stock)

    if g.xsz_enable_atr_stop_loss:
        xsz_update_atr_stop_prices(context)

def xsz_check_limit_up(context):
    holdings = get_sub_portfolio(context, 0).positions
    if holdings:
        now_time = context.current_dt
        if g.xsz_yesterday_HL_list:
            for stock in g.xsz_yesterday_HL_list:
                current_data = get_price(stock, end_date=now_time, frequency="1m",
                                         fields=["close", "high_limit"], skip_paused=False,
                                         fq="pre", count=1, panel=False, fill_paused=True)
                if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                    log.info(f"小市值：[小市值] {xsz_format_stock_code(stock)} 涨停打开，卖出")
                    xsz_close_position(stock, context)
                else:
                    log.info(f"小市值：[小市值] {stock} 继续涨停，继续持有")

def xsz_sell_stocks(context):
    if g.xsz_run_stoploss:
        current_positions = get_sub_portfolio(context, 0).positions
        if g.xsz_enable_atr_stop_loss:
            xsz_check_atr_stop_loss(context)

        for stock in list(current_positions.keys()):
            if stock in current_positions:
                price = current_positions[stock].price
                avg_cost = current_positions[stock].avg_cost
                profit_ratio = (price - avg_cost) / avg_cost

                if price >= avg_cost * 2:
                    log.info(f"小市值：[小市值] {xsz_format_stock_code(stock)} 收益100%止盈，卖出")
                    xsz_close_position(stock, context)
                    if stock in g.xsz_atr_stop_prices:
                        del g.xsz_atr_stop_prices[stock]
                elif g.xsz_enable_cost_protection:
                    if profit_ratio >= g.xsz_cost_protection_profit_threshold_2:
                        stop_loss_line = g.xsz_cost_protection_stop_line_2
                        trigger_name = f"成本保护止损(盈利{profit_ratio:.1%}，止损线{stop_loss_line:.1%})"
                    elif profit_ratio >= g.xsz_cost_protection_profit_threshold_1:
                        stop_loss_line = g.xsz_cost_protection_stop_line_1
                        trigger_name = f"成本保护止损(盈利{profit_ratio:.1%}，止损线{stop_loss_line:.1%})"
                    else:
                        stop_loss_line = -g.xsz_stoploss_limit
                        trigger_name = "固定止损"
                    if profit_ratio < stop_loss_line:
                        log.warn(f"小市值：[小市值] {xsz_format_stock_code(stock)} 触发{trigger_name}，卖出")
                        xsz_close_position(stock, context)
                        if g.xsz_check_after_no_buy:
                            g.xsz_no_buy_stocks[stock] = context.current_dt.date()
                        if stock in g.xsz_atr_stop_prices:
                            del g.xsz_atr_stop_prices[stock]
                elif price < avg_cost * (1 - g.xsz_stoploss_limit):
                    log.warn(f"小市值：[小市值] {xsz_format_stock_code(stock)} 触发固定止损，卖出")
                    xsz_close_position(stock, context)
                    if g.xsz_check_after_no_buy:
                        g.xsz_no_buy_stocks[stock] = context.current_dt.date()
                    if stock in g.xsz_atr_stop_prices:
                        del g.xsz_atr_stop_prices[stock]

        stock_df = get_price(security=get_index_stocks("399101.XSHE"), end_date=context.previous_date,
                             frequency="daily", fields=["close", "open"], count=1, panel=False)
        down_ratio = (stock_df["close"] / stock_df["open"] - 1).mean()
        if down_ratio <= -g.xsz_stoploss_market:
            log.warn(f"小市值：[小市值] 大盘惨跌，平均降幅 {down_ratio:.2%}")
            for stock in get_sub_portfolio(context, 0).positions:
                xsz_close_position(stock, context)
                if stock in g.xsz_atr_stop_prices:
                    del g.xsz_atr_stop_prices[stock]

def xsz_check_macd_divergence(context, market_index="399101.XSHE", end_days=0):
    if not g.xsz_dbl and "9:31" in str(context.current_dt.time()):
        return

    def detect_divergence():
        fast, slow, sign = 12, 26, 9
        rows = (fast + slow + sign) * 5
        grid = attribute_history(market_index, rows + 10, fields=["close"]).dropna()
        if end_days < 0:
            grid = grid.iloc[:end_days]
        if len(grid) < rows:
            return False
        try:
            grid["dif"], grid["dea"], grid["macd"] = xsz_mcad(grid.close, fast, slow, sign)
            mask = (grid["macd"] < 0) & (grid["macd"].shift(1) >= 0)
            if mask.sum() < 2:
                return False
            key2, key1 = mask[mask].index[-2], mask[mask].index[-1]
            price_cond = grid.close[key2] < grid.close[key1]
            dif_cond = grid.dif[key2] > grid.dif[key1] > 0
            macd_cond = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]
            if len(grid["dif"]) > 20:
                recent_avg = grid["dif"].iloc[-10:].mean()
                prev_avg = grid["dif"].iloc[-20:-10].mean()
                trend_cond = recent_avg < prev_avg
            else:
                trend_cond = False
            return price_cond and dif_cond and macd_cond and trend_cond
        except Exception:
            return False

    if market_index != "399101.XSHE":
        return 1 if detect_divergence() else 0
    if detect_divergence():
        g.xsz_dbl.append(1)
        log.warn(f"小市值：[顶背离] 检测到{market_index}顶背离信号，清仓非涨停股票")
        current_data = get_current_data()
        for stock in get_sub_portfolio(context, 0).positions:
            if current_data[stock].last_price < current_data[stock].high_limit:
                xsz_close_position(stock, context)
    else:
        g.xsz_dbl.append(0)

def xsz_check_turnover(context):
    xsz_huanshou(context, stock_list=get_sub_portfolio(context, 0).positions)

def xsz_filter_cooldown_stocks(context, stock_list):
    if not g.xsz_check_after_no_buy:
        return stock_list
    current_date = context.current_dt.date()
    valid_stocks = []
    for stock in stock_list:
        if stock in g.xsz_no_buy_stocks:
            stop_date = g.xsz_no_buy_stocks[stock]
            trade_days = get_trade_days(start_date=stop_date, end_date=current_date)
            passed_days = len(trade_days) - 1
            if passed_days < g.xsz_no_buy_after_day:
                log.info(f"小市值：[冷却过滤] {xsz_format_stock_code(stock)} 仍在冷却期内，跳过")
                continue
            else:
                del g.xsz_no_buy_stocks[stock]
        valid_stocks.append(stock)
    return valid_stocks

def xsz_my_order_target_value(security, value, context):
    o = order_target_value(security, value, pindex=0)
    if o:
        if o.is_buy:
            if o.price * o.amount > 0:
                log.info(f"小市值：[小市值-交易] 买入 {xsz_format_stock_code(security)} 买价{o.price:<7.2f} 买量{o.amount:<7} 价值{o.price * o.amount:.2f}")
        else:
            if o.price * o.amount > 0:
                log.info(f"小市值：[小市值-交易] 卖出 {xsz_format_stock_code(security)} 卖价{o.price:<7.2f} 成本{o.avg_cost:<7.2f} 卖量{o.amount:<7} 盈亏{(o.price - o.avg_cost) * o.amount:.2f}")
    return o

def xsz_open_position(context, security, value):
    if value <= 5000:
        return
    if security in get_sub_portfolio(context, 0).positions:
        security_value = get_sub_portfolio(context, 0).positions[security].value
        if abs(value - security_value) < 5000:
            return
    return xsz_my_order_target_value(security, value, context)

def xsz_close_position(security, context):
    return xsz_my_order_target_value(security, 0, context)

def xsz_filter_stocks(context, stock_list):
    current_data = get_current_data()
    last_prices = history(1, unit="1m", field="close", security_list=stock_list)
    filtered = []
    for stock in stock_list:
        if current_data[stock].paused:
            continue
        if current_data[stock].is_st:
            continue
        if "退" in current_data[stock].name:
            continue
        if stock.startswith("30") or stock.startswith("68") or stock.startswith("8") or stock.startswith("4"):
            continue
        if not (stock in get_sub_portfolio(context, 0).positions or last_prices[stock][-1] < current_data[stock].high_limit):
            continue
        if not (stock in get_sub_portfolio(context, 0).positions or last_prices[stock][-1] > current_data[stock].low_limit):
            continue
        start_date = get_security_info(stock).start_date
        if context.previous_date - start_date < timedelta(days=375):
            continue
        filtered.append(stock)
    return filtered

def xsz_get_small_cap_stocks(context):
    initial_list = xsz_filter_stocks(context, get_index_stocks("399101.XSHE"))
    q = query(valuation.code, valuation.market_cap, income.net_profit, income.operating_revenue).filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(10, 100),
        income.operating_revenue > 1e8,
        indicator.roe > 0,
        indicator.roa > 0,
        income.net_profit > 2000000
    ).order_by(valuation.market_cap.asc()).limit(g.xsz_stock_num * 5)
    candidate_list = list(get_fundamentals(q).code)
    current_date = context.current_dt.date()
    start_audit_date = datetime.date(2025, 1, 1)
    if current_date > start_audit_date:
        audited_list = xsz_apply_nine_point_audit(context, candidate_list)
    else:
        audited_list = xsz_filter_audit(context, candidate_list)
    final_list = xsz_bonus_filter(context, audited_list)
    final_list = xsz_filter_cooldown_stocks(context, final_list)
    if not final_list:
        return [g.xsz_buy_etf]
    last_prices = history(1, unit="1d", field="close", security_list=final_list)
    return [s for s in final_list if s in get_sub_portfolio(context, 0).positions or last_prices[s][-1] <= 50][:g.xsz_stock_num]

def xsz_apply_nine_point_audit(context, stock_list):
    if not stock_list:
        return []
    yesterday = context.previous_date
    curr_year = yesterday.year
    curr_month = yesterday.month
    if curr_month <= 4:
        report_year = curr_year - 2
    else:
        report_year = curr_year - 1
    report_date_str = f"{report_year}-12-31"
    q = query(valuation.code, indicator.adjusted_profit, income.net_profit,
              cash_flow.subtotal_operate_cash_inflow, cash_flow.subtotal_operate_cash_outflow,
              balance.good_will, balance.equities_parent_company_owners,
              balance.total_liability, balance.total_assets,
              balance.shortterm_loan, balance.cash_equivalents).filter(valuation.code.in_(stock_list))
    fund_df = get_fundamentals(q, date=yesterday)
    if not fund_df.empty:
        fund_df = fund_df.set_index('code')
        fund_df.fillna(0, inplace=True)
    else:
        return stock_list
    final_list = []
    max_tolerance = 2
    for stock in stock_list:
        score = 0
        hit_reasons = []
        try:
            stock_name = get_security_info(stock).display_name if get_security_info(stock) else ""
            # 1. 披露时间检查
            if hasattr(finance, 'STK_INCOME_STATEMENT'):
                q_time = query(finance.STK_INCOME_STATEMENT.pub_date).filter(
                    finance.STK_INCOME_STATEMENT.code == stock,
                    finance.STK_INCOME_STATEMENT.end_date == report_date_str,
                    finance.STK_INCOME_STATEMENT.pub_date <= yesterday).limit(1)
                time_df = finance.run_query(q_time)
                if not time_df.empty:
                    actual_date = time_df['pub_date'].iloc[0]
                    if isinstance(actual_date, str):
                        actual_date = datetime.datetime.strptime(actual_date, '%Y-%m-%d').date()
                    elif isinstance(actual_date, datetime.datetime):
                        actual_date = actual_date.date()
                    if actual_date and actual_date > datetime.date(report_year + 1, 4, 20):
                        score += 1
                        hit_reasons.append("年报迟发(>4.20)")
            # 2. 业绩预告检查
            if hasattr(finance, 'STK_FIN_FORCAST'):
                q_forcast = query(finance.STK_FIN_FORCAST).filter(
                    finance.STK_FIN_FORCAST.code == stock,
                    finance.STK_FIN_FORCAST.end_date == report_date_str,
                    finance.STK_FIN_FORCAST.pub_date <= yesterday).limit(1)
                forcast_df = finance.run_query(q_forcast)
                if not forcast_df.empty:
                    type_id = forcast_df['type_id'].iloc[0]
                    if type_id in [3, 4, 5, 9, 10]:
                        score += 1
                        hit_reasons.append("业绩预告不良(预减/亏损等)")
            # 3. 审计意见检查 - 修复：查询时添加 opinion_type_id
            if hasattr(finance, 'STK_AUDIT_OPINION'):
                q_audit = query(finance.STK_AUDIT_OPINION.code,
                                finance.STK_AUDIT_OPINION.opinion_type_id).filter(
                    finance.STK_AUDIT_OPINION.code == stock,
                    finance.STK_AUDIT_OPINION.end_date == report_date_str,
                    finance.STK_AUDIT_OPINION.pub_date <= yesterday).limit(1)
                audit_df = finance.run_query(q_audit)
                if not audit_df.empty:
                    opinion_id = audit_df['opinion_type_id'].iloc[0]
                    if opinion_id in [3, 4, 5]:
                        continue
            if stock in fund_df.index:
                row = fund_df.loc[stock]
                adj_p = row['adjusted_profit']
                net_p = row['net_profit']
                cash_net = row['subtotal_operate_cash_inflow'] - row['subtotal_operate_cash_outflow']
                if adj_p < 0 or (net_p != 0 and adj_p / net_p < 0.5):
                    score += 1
                    hit_reasons.append("主业存疑(扣非<0或占比低)")
                if net_p > 0 and cash_net < 0:
                    score += 1
                    hit_reasons.append("现金流异常(净利>0但现金流<0)")
                equity = row['equities_parent_company_owners']
                gw = row['good_will']
                if equity > 0 and (gw / equity) > 0.3:
                    score += 1
                    hit_reasons.append("高危资产(商誉占净资产>30%)")
                t_liab = row['total_liability']
                t_assets = row['total_assets']
                st_loan = row['shortterm_loan']
                cash_val = row['cash_equivalents']
                debt_ratio = (t_liab / t_assets) if t_assets > 0 else 0
                if debt_ratio > 0.70 or st_loan > cash_val:
                    score += 1
                    hit_reasons.append(f"资金链紧绷(负债率{(debt_ratio*100):.0f}%)")
            # 大股东风险
            if hasattr(finance, 'STK_SHARES_PLEDGE'):
                q_pledge = query(finance.STK_SHARES_PLEDGE).filter(
                    finance.STK_SHARES_PLEDGE.code == stock,
                    finance.STK_SHARES_PLEDGE.pub_date <= yesterday
                ).order_by(finance.STK_SHARES_PLEDGE.pub_date.desc()).limit(1)
                pledge_df = finance.run_query(q_pledge)
                if not pledge_df.empty:
                    ratio_col = 'pledge_proportion' if 'pledge_proportion' in pledge_df.columns else ('pledge_ratio' if 'pledge_ratio' in pledge_df.columns else None)
                    if ratio_col and pd.notna(pledge_df[ratio_col].iloc[0]) and pledge_df[ratio_col].iloc[0] > 80:
                        score += 1
                        hit_reasons.append("大股东高质押(>80%)")
            # 监管信号
            if hasattr(finance, 'STK_INVESTIGATION'):
                q_inv = query(finance.STK_INVESTIGATION).filter(
                    finance.STK_INVESTIGATION.code == stock,
                    finance.STK_INVESTIGATION.pub_date >= f"{curr_year-1}-01-01",
                    finance.STK_INVESTIGATION.pub_date <= yesterday).limit(1)
                inv_df = finance.run_query(q_inv)
                if not inv_df.empty:
                    score += 1
                    hit_reasons.append("曾遭监管立案调查")
            if score > 0:
                log.info(f"小市值：[排雷透视] {stock}({stock_name}) 累计踩中 {score} 项: {' | '.join(hit_reasons)}")
            if score < max_tolerance:
                final_list.append(stock)
            else:
                log.info(f"小市值：[排雷剔除] {stock}({stock_name}) 踩雷 {score} 项，已拦截")
        except Exception as e:
            log.error(f"小市值：[排雷报错] 股票 {stock} 异常: {e}")
            final_list.append(stock)
    return final_list

def xsz_filter_audit(context, code_list):
    final_list = []
    for stock in code_list:
        previous_date = context.previous_date
        last_year = (previous_date.replace(year=previous_date.year - 3, month=1, day=1)).strftime("%Y-%m-%d")
        # 修复：查询时添加 opinion_type_id 字段
        q = query(finance.STK_AUDIT_OPINION.code, 
                  finance.STK_AUDIT_OPINION.pub_date,
                  finance.STK_AUDIT_OPINION.opinion_type_id).filter(
            finance.STK_AUDIT_OPINION.code == stock,
            finance.STK_AUDIT_OPINION.pub_date >= last_year,
            finance.STK_AUDIT_OPINION.pub_date <= context.previous_date)
        df = finance.run_query(q)
        if df.empty:
            final_list.append(stock)
            continue
        # 检查 opinion_type_id 列是否存在
        if 'opinion_type_id' in df.columns:
            if not df["opinion_type_id"].isin([3, 4, 5, 7]).any():
                final_list.append(stock)
        else:
            # 若列不存在，保守起见保留该股票
            final_list.append(stock)
    return final_list

def xsz_bonus_filter(context, stock_list):
    year = context.previous_date.year
    start_date = datetime.datetime(year=year, month=1, day=1)
    end_date = context.previous_date
    if end_date.month == 5:
        q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.company_name,
                  finance.STK_XR_XD.board_plan_pub_date, finance.STK_XR_XD.bonus_amount_rmb,
                  finance.STK_XR_XD.bonus_ratio_rmb).filter(
            finance.STK_XR_XD.board_plan_pub_date > start_date,
            finance.STK_XR_XD.implementation_pub_date <= end_date,
            finance.STK_XR_XD.bonus_ratio_rmb > 0,
            finance.STK_XR_XD.code.in_(stock_list))
        expected_bonus_df = finance.run_query(q)
        if len(expected_bonus_df) > 0:
            bonus_list = expected_bonus_df["code"].unique().tolist()
            # 修复：使用 get_price 获取明确日期的收盘价，避免 history + 转置的列名问题
            price_df = get_price(bonus_list, end_date=end_date, count=1, fields=['close'], panel=False, skip_paused=False)
            if price_df is not None and not price_df.empty:
                latest_close = price_df.groupby('code')['close'].last().reset_index()
                latest_close.rename(columns={'close': 'Close_now'}, inplace=True)
                expected_bonus_df = pd.merge(expected_bonus_df, latest_close, on="code", how="left")
                expected_bonus_df = expected_bonus_df[expected_bonus_df['Close_now'] > 0].copy()
                if expected_bonus_df.empty:
                    bonus_list = []
                else:
                    expected_bonus_df["bonus_ratio"] = expected_bonus_df["bonus_ratio_rmb"] / expected_bonus_df["Close_now"]
                    expected_bonus_df = expected_bonus_df.sort_values(by="bonus_ratio", ascending=True)
                    bonus_list = expected_bonus_df["code"].unique().tolist()
            else:
                bonus_list = []
        else:
            bonus_list = []
    else:
        reprot_date = datetime.datetime(year=year - 1, month=12, day=31)
        q = query(finance.STK_XR_XD.code).filter(
            finance.STK_XR_XD.report_date == reprot_date,
            finance.STK_XR_XD.bonus_type == "年度分红",
            finance.STK_XR_XD.implementation_pub_date <= end_date,
            finance.STK_XR_XD.board_plan_bonusnote == "不分配不转增",
            finance.STK_XR_XD.code.in_(stock_list))
        no_year_bonus = finance.run_query(q)
        no_year_bonus_list = no_year_bonus["code"].unique().tolist()
        bonus_list = [code for code in stock_list if code not in no_year_bonus_list]
        bonus_list = xsz_short_by_market_cap(context, bonus_list)
    if len(bonus_list) < g.xsz_stock_num:
        bonus_list.extend([x for x in xsz_short_by_market_cap(context, stock_list) if x not in bonus_list][:g.xsz_stock_num - len(bonus_list)])
    return bonus_list

def xsz_short_by_market_cap(context, stock_list):
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(stock_list), valuation.day == context.previous_date).order_by(valuation.market_cap.asc())
    df = get_fundamentals(q)
    return df["code"].unique().tolist()

def xsz_mcad(close, short=12, long=26, m=9):
    def ema(series, n):
        return pd.Series.ewm(series, span=n, min_periods=n - 1, adjust=False).mean()
    dif = ema(close, short) - ema(close, long)
    dea = ema(dif, m)
    return dif, dea, (dif - dea) * 2

def xsz_huanshou(context, stock_list):
    def huanshoulv(_stock, is_avg=False):
        if is_avg:
            end_date = context.previous_date
            df_volume = get_price(_stock, end_date=end_date, frequency="daily", fields=["volume"], count=20)
            df_cap = get_valuation(_stock, end_date=end_date, fields=["circulating_cap"], count=1)
            circulating_cap = df_cap["circulating_cap"].iloc[0] if not df_cap.empty else 0
            if circulating_cap == 0:
                return 0.0
            df_volume["turnover_ratio"] = df_volume["volume"] / (circulating_cap * 10000)
            return df_volume["turnover_ratio"].mean()
        else:
            date_now = context.current_dt
            df_vol = get_price(_stock, start_date=date_now.date(), end_date=date_now, frequency="1m",
                               fields=["volume"], skip_paused=False, fq="pre", panel=True, fill_paused=False)
            volume = df_vol["volume"].sum()
            date_pre = context.previous_date
            df_cap = get_valuation(_stock, end_date=date_pre, fields=["circulating_cap"], count=1)
            circulating_cap = df_cap["circulating_cap"].iloc[0] if not df_cap.empty else 0
            if circulating_cap == 0:
                return 0.0
            return volume / (circulating_cap * 10000)
    current_data = get_current_data()
    for stock in stock_list:
        if current_data[stock].paused:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if get_sub_portfolio(context, 0).positions[stock].closeable_amount == 0:
            continue
        rt = huanshoulv(stock, False)
        avg = huanshoulv(stock, True)
        if avg == 0:
            continue
        r = rt / avg
        action, icon = "", ""
        if avg < 0.003:
            action, icon = "缩量", "❄️"
        elif rt > 0.1 and r > 2:
            action, icon = "放量", "🔥"
        if action:
            log.warn(f"小市值：[换手] {action} {xsz_format_stock_code(stock)} 换手率:{rt:.2%} 均:{avg:.2%} 倍率:x{r:.1f} {icon}")
            xsz_close_position(stock, context)
    def get_market_breadth(ma_days):
        required_days = ma_days + 10
        end_date = context.current_dt.replace(hour=14, minute=49)
        sw_l1 = get_industries("sw_l1", date=context.current_dt.date())
        industry_stocks = {}
        for idx, row in sw_l1.iterrows():
            ind_stocks = get_industry_stocks(idx, date=end_date)
            industry_stocks[row["name"]] = ind_stocks
        all_stocks = []
        for stocks in industry_stocks.values():
            all_stocks.extend(stocks)
        all_stocks = list(set(all_stocks))
        data = get_bars(all_stocks, end_dt=end_date, count=required_days, unit="1d",
                        fields=["date", "close", "volume", "money"], include_now=True, df=True)
        price_reset = data.reset_index()
        price_pivot = price_reset.pivot(index="level_1", columns="level_0", values="close")
        ma = price_pivot.rolling(window=ma_days).mean()
        above_ma = price_pivot > ma
        money_reset = data.reset_index()
        money_pivot = money_reset.pivot(index="level_1", columns="level_0", values="money")
        recent_20d_money_pivot = money_pivot.tail(20)
        avg_money = recent_20d_money_pivot.mean().reset_index()
        avg_money.columns = ["code", "avg_money"]
        avg_money = avg_money.sort_values("avg_money", ascending=False)
        avg_money["money_group"] = pd.qcut(avg_money["avg_money"], 20, labels=[f"组{i+1}" for i in range(20)], duplicates="drop")
        money_groups = {group: group_df["code"].tolist() for group, group_df in avg_money.groupby("money_group")}
        group_scores = pd.DataFrame(index=price_pivot.index)
        for group, stocks in money_groups.items():
            valid_stocks = list(set(above_ma.columns) & set(stocks))
            if valid_stocks:
                group_scores[group] = 100 * above_ma[valid_stocks].sum(axis=1) / len(valid_stocks)
        recent_group_data = group_scores[-3:].mean()
        _sorted_ma_data = recent_group_data.sort_values(ascending=False)
        df = data.reset_index().rename(columns={"level_0": "symbol", "level_1": "index"})
        df["pct_change"] = df.groupby(["symbol"])["close"].pct_change()
        trade_days = get_trade_days(end_date=context.current_dt, count=3)
        by_date = trade_days[0]
        df = df[df.date >= by_date]
        grouped = df.groupby("date")
        _result = pd.DataFrame({"up_ratio": grouped["pct_change"].apply(lambda x: (x > 0).mean()),
                                "down_over": grouped["pct_change"].apply(lambda x: (x <= -0.0985).sum())}).reset_index()
        return _sorted_ma_data, _result

    def calculate_trend_indicators(index_symbol="399101.XSHE"):
        high_lookback = 60
        high_proximity = 0.95
        check_days = 2
        end_date = context.current_dt.replace(hour=14, minute=49)
        total_days_needed = high_lookback + 10
        data = get_bars(index_symbol, end_dt=end_date, count=total_days_needed, unit="1d",
                        fields=["date", "close", "high", "avg", "volume"], include_now=True, df=True)
        data["date"] = pd.to_datetime(data["date"])
        _past_is_high_list = []
        for i in range(-check_days, 0):
            valid_data = data.iloc[:i][-high_lookback:]
            current_day_price = valid_data["close"].iloc[-1]
            day_max_high = valid_data["high"].max()
            day_close_to_high = current_day_price >= (day_max_high * high_proximity)
            _past_is_high_list.append(day_close_to_high)
        current_data = data[-high_lookback:]
        current_price = current_data["close"].iloc[-1]
        max_high = current_data["high"].max()
        close_to_high = current_price >= (max_high * high_proximity)
        _past_is_high_list.append(close_to_high)
        return any(_past_is_high_list), _past_is_high_list

def xsz_format_stock_code(stock_code):
    try:
        stock_info = get_security_info(stock_code)
    except Exception:
        return f"{stock_code[:6]}"
    return f"{stock_code[:6]}({stock_info.display_name})"

# ==================== 策略2：五福ETF v3.5（日志增加前缀“ETF：”） ====================
def etf_initialize(context):
    """五福ETF v3.5 初始化"""
    log.info("ETF：【五福闹新春】v3.5启动！")

    # ==================== 固定ETF池 ====================
    g.etf_fixed_etf_pool = [
        '518880.XSHG', '161226.XSHE', '159980.XSHE', '501018.XSHG', '159985.XSHE',
        '513100.XSHG', '159509.XSHE', '513290.XSHG', '513500.XSHG', '159518.XSHE',
        '159502.XSHE', '159529.XSHE', '513400.XSHG', '520830.XSHG', '513520.XSHG',
        '513030.XSHG', '513090.XSHG', '513180.XSHG', '513120.XSHG', '513330.XSHG',
        '513750.XSHG', '159892.XSHE', '159605.XSHE', '513190.XSHG', '510900.XSHG',
        '513630.XSHG', '513920.XSHG', '159323.XSHE', '513970.XSHG', '510500.XSHG',
        '512100.XSHG', '563300.XSHG', '510300.XSHG', '512050.XSHG', '510760.XSHG',
        '159915.XSHE', '159949.XSHE', '159967.XSHE', '588080.XSHG', '588220.XSHG',
        '511380.XSHG', '513310.XSHG', '588200.XSHG', '159852.XSHE', '512880.XSHG',
        '159206.XSHE', '512400.XSHG', '512980.XSHG', '159516.XSHE', '512480.XSHG',
        '515880.XSHG', '562500.XSHG', '159218.XSHE', '159869.XSHE', '159870.XSHE',
        '159326.XSHE', '159851.XSHE', '560860.XSHG', '159363.XSHE', '588170.XSHG',
        '159755.XSHE', '512170.XSHG', '512800.XSHG', '159819.XSHE', '512710.XSHG',
        '159638.XSHE', '517520.XSHG', '515980.XSHG', '159995.XSHE', '159227.XSHE',
        '512660.XSHG', '512690.XSHG', '516150.XSHG', '512890.XSHG', '588790.XSHG',
        '159992.XSHE', '512070.XSHG', '562800.XSHG', '512010.XSHG', '515790.XSHG',
        '510880.XSHG', '159928.XSHE', '159883.XSHE', '159998.XSHE', '515220.XSHG',
        '561980.XSHG', '515400.XSHG', '515120.XSHG', '159566.XSHE', '515050.XSHG',
        '516510.XSHG', '159256.XSHE', '159766.XSHE', '512200.XSHG', '513350.XSHG',
        '159583.XSHE', '159732.XSHE', '516160.XSHG', '516520.XSHG', '562590.XSHG',
        '515030.XSHG', '512670.XSHG', '561330.XSHG', '516190.XSHG', '159840.XSHE',
        '159611.XSHE', '159981.XSHE', '159865.XSHE', '561360.XSHG', '159667.XSHE',
        '515170.XSHG', '513360.XSHG', '159825.XSHE', '515210.XSHG'
    ]
    g.etf_filtered_fixed_pool = []
    g.etf_dynamic_etf_pool = []
    g.etf_merged_etf_pool = []
    g.etf_ranked_etfs_result = []
    g.etf_positions = {}
    g.etf_target_etfs_list = []
    g.etf_etf_names_dict = {}
    g.etf_cache_date = None
    g.etf_yesterday_close_cache = {}

    # ==================== 策略核心参数 ====================
    g.etf_holdings_num = 1
    g.etf_defensive_etf = "511880.XSHG"
    g.etf_min_money = 10

    g.etf_lookback_days = 25
    g.etf_min_score_threshold = 0
    g.etf_max_score_threshold = 5
    g.etf_score_threshold_ratio = 0.9

    g.etf_use_short_momentum_period = False
    g.etf_short_momentum_lookback = 21
    g.etf_short_momentum_min_score = 0
    g.etf_short_momentum_max_score = 6

    g.etf_enable_r2_filter = True
    g.etf_r2_threshold = 0.4
    g.etf_enable_volume_check = True
    g.etf_volume_lookback = 5
    g.etf_volume_threshold = 1.8
    g.etf_enable_loss_filter = True
    g.etf_loss = 0.97
    g.etf_enable_premium_filter = False
    g.etf_max_premium_rate = 30

    g.etf_laplace_s_param = 0.05
    g.etf_laplace_min_slope = 0.002
    g.etf_gaussian_sigma = 1.2
    g.etf_gaussian_min_slope = 0.002

    g.etf_enable_range_bound_mode = True
    g.etf_current_filter = '正常期'
    g.etf_risk_state = '正常期'
    g.etf_lookback_high_low_days = 20
    g.etf_risk_benchmark = '510300.XSHG'

    g.etf_enable_bias_trigger = True
    g.etf_bias_threshold = 0.08
    g.etf_ma_period = 20
    g.etf_enable_rsi_trigger = True
    g.etf_rsi_overbought = 70
    g.etf_rsi_pullback = 65
    g.etf_previous_rsi = None
    g.etf_enable_stop_loss_trigger = True
    g.etf_stop_loss_triggered_today = False

    g.etf_enable_low_point_rise_trigger = True
    g.etf_low_point_rise_threshold = 0.04
    g.etf_enable_stable_signal_trigger = True
    g.etf_drawdown_recovery = 0.02
    g.etf_max_range_bound_days = 20
    g.etf_stable_days = 0

    g.etf_filter_switch_cooldown = 3
    g.etf_last_switch_date = None
    g.etf_range_bound_start_date = None
    g.etf_range_bound_days_count = 0

    g.etf_previous_drawdown = None
    g.etf_max_portfolio_value = 0
    g.etf_drawdown_threshold = 0.03
    g.etf_drawdown_records = []

    g.etf_use_fixed_stop_loss = True
    g.etf_fixedStopLossThreshold = 0.95
    g.etf_use_pct_stop_loss = False
    g.etf_pct_stop_loss_threshold = 0.95

    g.etf_avg_etf_money_threshold = None

    # ==================== 定时任务 ====================
    run_daily(etf_morning_routine, time='09:00')
    run_daily(etf_afternoon_routine, time='13:10')
    run_daily(etf_reset_daily_flags, time='15:10')
    run_daily(etf_minute_level_stop_loss, time='every_bar')
    run_daily(etf_minute_level_pct_stop_loss, time='every_bar')

    # 首次运行震荡期状态初始化
    etf_init_range_bound_status(context)

    log.info("ETF：五福ETF v3.5 初始化完成")

# ---------- 五福ETF v3.5 核心函数（日志前缀“ETF：”） ----------
def etf_init_range_bound_status(context):
    if not g.etf_enable_range_bound_mode:
        return
    log.info("ETF：🔍 【首次运行】初始化震荡期状态...")
    try:
        if context.previous_date is None:
            log.warning("ETF：【首次运行】无法获取前一个交易日，保持正常期")
            return
        end_date = context.previous_date
        lookback = max(g.etf_ma_period, g.etf_lookback_high_low_days) + 30
        df = get_price(g.etf_risk_benchmark, end_date=end_date, count=lookback,
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.etf_ma_period, g.etf_lookback_high_low_days):
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        if len(close) >= g.etf_lookback_high_low_days:
            recent_high = np.max(high[-g.etf_lookback_high_low_days:])
            recent_low = np.min(low[-g.etf_lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        ma = np.mean(close[-g.etf_ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        current_rsi = etf_calculate_rsi(close, period=14)
        should_enter_range_bound = False
        signals = []
        if g.etf_enable_bias_trigger and bias > g.etf_bias_threshold:
            should_enter_range_bound = True
            signals.append(f"乖离率{bias:.2%}>{g.etf_bias_threshold:.0%}")
        if g.etf_enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = etf_calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.etf_rsi_overbought and current_rsi < g.etf_rsi_pullback:
                should_enter_range_bound = True
                signals.append(f"RSI超买回落{prev_rsi:.1f}→{current_rsi:.1f}")
        if should_enter_range_bound:
            g.etf_current_filter = '震荡期'
            g.etf_risk_state = '震荡期'
            g.etf_range_bound_start_date = end_date
            g.etf_range_bound_days_count = 0
            log.info(f"ETF：🔔 【首次运行】初始化进入震荡期: {'; '.join(signals)}")
        else:
            g.etf_current_filter = '正常期'
            g.etf_risk_state = '正常期'
            if len(close) >= g.etf_lookback_high_low_days:
                g.etf_previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            else:
                g.etf_previous_drawdown = 0
            g.etf_previous_rsi = current_rsi
            log.info(f"ETF：📌 【首次运行】初始状态: 正常期(拉普拉斯滤波器), 乖离率: {bias:.2%}, RSI: {current_rsi:.1f}")
    except Exception as e:
        log.warning(f"ETF：【首次运行】初始化震荡期状态异常: {e}")

def etf_morning_routine(context):
    log.info("ETF：★" * 80)
    log.info("ETF：▶️ 【晨间流水线】启动...")
    etf_check_positions(context)
    etf_monitor_drawdown(context)
    etf_calculate_global_etf_threshold(context)
    etf_update_sector_pool(context)
    etf_filter_fixed_pool_by_volume(context)
    etf_daily_merge_etf_pools(context)
    log.info("ETF：⏸️ 【晨间流水线】执行完毕！")

def etf_afternoon_routine(context):
    log.info("ETF：▶️ 【午后交易流水线】启动...")
    etf_check_and_exit_range_bound_mode(context)
    etf_check_and_enter_range_bound_mode(context)
    etf_calculate_and_log_ranked_etfs(context)
    etf_execute_sell_trades(context)
    etf_execute_buy_trades(context)
    log.info("ETF：⏸️ 【午后交易流水线】执行完毕！")

def etf_reset_daily_flags(context):
    g.etf_cache_date = None
    g.etf_yesterday_close_cache = {}
    if g.etf_current_filter == '震荡期' and g.etf_range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.etf_range_bound_start_date, end_date=context.current_dt.date())
        g.etf_range_bound_days_count = len(trade_days) - 1
        log.info(f"ETF：📊 震荡期已持续 {g.etf_range_bound_days_count} 个交易日")
    log.info("ETF：🔄 收盘缓存重置完成")

def etf_check_positions(context):
    current_data = get_current_data()
    sub_port = get_sub_portfolio(context, 1)
    for security in sub_port.positions:
        position = sub_port.positions[security]
        if position.total_amount > 0:
            security_name = etf_get_security_name(security)
            log.info(f"ETF：📊 【持仓检查】{security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"ETF：⚠️ {security} {security_name} 今日停牌")

def etf_monitor_drawdown(context):
    try:
        sub_port = get_sub_portfolio(context, 1)
        current_value = sub_port.total_value
        if current_value > g.etf_max_portfolio_value:
            g.etf_max_portfolio_value = current_value
        if g.etf_max_portfolio_value > 0:
            current_drawdown = (g.etf_max_portfolio_value - current_value) / g.etf_max_portfolio_value
            if current_drawdown >= g.etf_drawdown_threshold:
                record = {
                    'date': context.current_dt.strftime('%Y-%m-%d'),
                    'drawdown': current_drawdown,
                    'portfolio_value': current_value,
                    'max_value': g.etf_max_portfolio_value,
                    'current_filter': g.etf_current_filter,
                    'risk_state': g.etf_risk_state
                }
                positions_info = []
                for security in sub_port.positions:
                    position = sub_port.positions[security]
                    if position.total_amount > 0:
                        security_name = etf_get_security_name(security)
                        positions_info.append(f"{security_name}:{position.total_amount}股")
                record['positions'] = positions_info
                g.etf_drawdown_records.append(record)
                log.info(f"ETF：【回撤预警】回撤达到 {current_drawdown:.2%} (阈值: {g.etf_drawdown_threshold:.0%})")
    except Exception as e:
        log.error(f"ETF：【回撤监控】计算异常: {e}")

def etf_calculate_global_etf_threshold(context):
    log.info("ETF：【全局阈值更新】开始计算全市场ETF流动性门槛")
    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            log.warning("ETF：未找到任何场内ETF，使用保守阈值1000万")
            g.etf_avg_etf_money_threshold = 10000000
            return
        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]
        df = get_price(security=etf_list, start_date=start_day, end_date=context.previous_date,
                       frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or df.empty:
            log.warning("ETF：无法获取历史成交额数据，使用保守阈值1000万")
            g.etf_avg_etf_money_threshold = 10000000
            return
        daily_totals = df.groupby('time')['money'].sum()
        if len(daily_totals) < 3:
            log.warning(f"ETF：仅有{len(daily_totals)}个有效交易日，使用保守阈值1000万")
            g.etf_avg_etf_money_threshold = 10000000
            return
        avg_total_money = daily_totals.mean()
        threshold = max(avg_total_money / 20000, 10000000)
        g.etf_avg_etf_money_threshold = threshold
        log.info(f"ETF：【全局阈值更新完成】阈值={threshold/1e4:.0f}万元")
    except Exception as e:
        log.warning(f"ETF：计算全局阈值异常: {e}")
        g.etf_avg_etf_money_threshold = 10000000

def etf_update_sector_pool(context):
    log.info("ETF：【动态池更新】开始执行")
    if g.etf_avg_etf_money_threshold is None:
        etf_calculate_global_etf_threshold(context)
    FUND_COMPANIES = sorted(list(set([
        '易方达', '广发', '华夏', '华安', '嘉实', '富国', '招商', '鹏华', '南方', '汇添富', '国泰', '平安',
        '银华', '天弘', '建信', '工银', '华泰柏瑞', '博时', '景顺长城', '景顺', '华宝', '申万菱信', '万家', '中欧',
        '兴证全球', '浙商', '诺安', '前海开源', '泰康', '泰达宏利', '农银汇理', '交银', '东方红', '财通', '华商',
        '国联', '永赢', '金鹰', '德邦', '创金合信', '西部利得', '圆信永丰', '泓德', '汇安', '诺德', '恒生前海',
        '华润元大', '大成', '海富通', '摩根', '华泰', '中信', '中银', '兴全', '国信', '长城', '中金', '浙商证券',
        '东海', '东吴', '浦银安盛', '信达澳亚', '中加', '中航', '中融', '中邮', '中庚', '中信保诚', '中信建投',
        '中银国际', '中银证券', '九泰', '交银施罗德', '光大保德信', '兴银', '农银', '国投瑞银', '国海富兰克林',
        '国联安', '国金', '太平', '方正富邦', '民生加银', '汇丰晋信', '银河', '长信', '长安', '长盛', '长江证券', '鹏扬'
    ])), key=len, reverse=True)
    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)
    SPECIAL_GROUPS = sorted([
        {'name': '香港组', 'keywords': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS科技'], key=len, reverse=True),
         'remove_words': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS'], key=len, reverse=True)},
        {'name': '科创组', 'keywords': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True),
         'remove_words': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创', '债券', '债汇', '债指', '债沪', '债易', '债基', '债兴', '债摩', '债', 'AAA'], key=len, reverse=True)},
        {'name': '创业组', 'keywords': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True),
         'remove_words': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True)},
        {'name': '美指组', 'keywords': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True),
         'remove_words': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True)}
    ], key=lambda x: max(len(kw) for kw in x['keywords']), reverse=True)
    exclude_keywords = sorted(list(set([
        '300', '500', '1000', '2000', '800', '30', '50', '100', '180', '200',
        '沪深', '中证', '上证', '深证', '深成', 'A50', 'A100', 'A500', '深100',
        '短融', '可转债', '转债', '双债', '利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债',
        '信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债', '科创债', '科债', '科创AAA',
        '自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流',
        '货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数',
        '全指现金', '现金全指', 'ESG', 'MSCI', 'MS', '债',
    ])), key=len, reverse=True)
    try:
        df_etf = get_all_securities(['etf'])
        etf_list = df_etf.index.tolist()
        g.etf_etf_names_dict = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"ETF：获取全市场ETF列表失败: {e}")
        return
    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0
    for code in etf_list:
        try:
            name = g.etf_etf_names_dict.get(code, str(code))
            is_special = False
            matched_group = None
            for group in SPECIAL_GROUPS:
                for kw in group['keywords']:
                    if kw in name:
                        is_special = True
                        matched_group = group['name']
                        break
                if is_special:
                    break
            is_excluded = False
            for k in exclude_keywords:
                if k in name:
                    is_excluded = True
                    excluded_count += 1
                    break
            if not is_excluded:
                if is_special:
                    special_etfs.append(code)
                    special_group_map[code] = matched_group
                else:
                    normal_etfs.append(code)
        except Exception:
            continue
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.etf_avg_etf_money_threshold

    def filter_by_liquidity(etf_codes, group_name):
        if not etf_codes:
            return pd.Series(dtype=float), 0
        try:
            price_data = get_price(etf_codes, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
            if price_data is None or price_data.empty:
                return pd.Series(dtype=float), len(etf_codes)
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / TRADE_DAYS_COUNT
            qualified_series = avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
            filtered_out = len(etf_codes) - len(qualified_series)
            return qualified_series, filtered_out
        except Exception:
            return pd.Series(dtype=float), len(etf_codes)

    normal_qualified, _ = filter_by_liquidity(normal_etfs, "普通组")
    special_qualified, _ = filter_by_liquidity(special_etfs, "特别组")
    normal_sorted = normal_qualified.index.tolist()
    special_sorted = special_qualified.index.tolist()

    def get_remove_words_for_etf(_, is_special, matched_group_name):
        if not is_special:
            return []
        for group in SPECIAL_GROUPS:
            if group['name'] == matched_group_name:
                return group['remove_words']
        return []

    def clean_name(original_name, is_special=False, matched_group_name=None):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        if is_special and matched_group_name:
            for word in get_remove_words_for_etf(original_name, is_special, matched_group_name):
                cleaned = cleaned.replace(word, '')
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()

    normal_industry_groups = {}
    for code in normal_sorted:
        try:
            original_name = g.etf_etf_names_dict.get(code, str(code))
            money = normal_qualified[code]
            cleaned = clean_name(original_name, is_special=False)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            normal_industry_groups.setdefault(industry_key, []).append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': '普通'
            })
        except Exception:
            continue
    special_industry_groups = {}
    for code in special_sorted:
        try:
            original_name = g.etf_etf_names_dict.get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            money = special_qualified[code]
            cleaned = clean_name(original_name, is_special=True, matched_group_name=matched_group)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            group_key = f"{matched_group}_{industry_key}"
            special_industry_groups.setdefault(group_key, []).append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': matched_group, 'display_group': matched_group
            })
        except Exception:
            continue
    final_pool_info = []
    for industry_key, items in normal_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    for group_key, items in special_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    final_pool_info_sorted = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    top_100 = final_pool_info_sorted[:100]
    g.etf_dynamic_etf_pool = [item['code'] for item in top_100]
    log.info(f"ETF：【动态池更新完成】动态池共{len(g.etf_dynamic_etf_pool)}只ETF")

def etf_filter_fixed_pool_by_volume(context):
    log.info("ETF：【固定池过滤】开始执行")
    if getattr(g, 'etf_avg_etf_money_threshold', None) is None:
        etf_calculate_global_etf_threshold(context)
    if not g.etf_fixed_etf_pool:
        log.info("ETF：【固定池过滤】固定池为空，跳过过滤")
        return
    dynamic_threshold = g.etf_avg_etf_money_threshold
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.etf_fixed_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("ETF：【固定池过滤】无法获取成交额数据，跳过过滤")
            g.etf_filtered_fixed_pool = g.etf_fixed_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        g.etf_filtered_fixed_pool = qualified.index.tolist()
        log.info(f"ETF：【固定池过滤】保留高流动性ETF({len(g.etf_filtered_fixed_pool)}只)")
    except Exception as e:
        log.warning(f"ETF：【固定池过滤】异常: {e}")
        g.etf_filtered_fixed_pool = g.etf_fixed_etf_pool[:]

def etf_daily_merge_etf_pools(context):
    if not hasattr(g, 'etf_filtered_fixed_pool'):
        g.etf_filtered_fixed_pool = g.etf_fixed_etf_pool[:]
    merged = list(set(g.etf_filtered_fixed_pool + g.etf_dynamic_etf_pool))
    merged.sort()
    log.info(f"ETF：【合并池统计】固定池: {len(g.etf_filtered_fixed_pool)}只, 动态池: {len(g.etf_dynamic_etf_pool)}只, 合并后: {len(merged)}只")
    g.etf_merged_etf_pool = merged

def etf_check_and_exit_range_bound_mode(context):
    if not g.etf_enable_range_bound_mode:
        return
    if g.etf_current_filter != '震荡期':
        return
    log.info("ETF：🔍 【震荡期退出检查】开始检测退出条件...")
    try:
        lookback = max(g.etf_ma_period, g.etf_lookback_high_low_days) + 30
        end_date = context.previous_date
        df = get_price(g.etf_risk_benchmark, end_date=end_date, count=lookback,
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.etf_ma_period, g.etf_lookback_high_low_days):
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        if len(close) >= g.etf_lookback_high_low_days:
            recent_high = np.max(high[-g.etf_lookback_high_low_days:])
            recent_low = np.min(low[-g.etf_lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        recovery_signals = []
        ma = np.mean(close[-g.etf_ma_period:])
        current_rsi = etf_calculate_rsi(close, period=14)
        log.info(f"ETF：📊 【震荡期数据】当前价: {current_price:.3f}, 近{g.etf_lookback_high_low_days}日高点: {recent_high:.3f}, 低点: {recent_low:.3f}")
        if g.etf_enable_low_point_rise_trigger and rise_from_low >= g.etf_low_point_rise_threshold:
            recovery_signals.append(f"从近{g.etf_lookback_high_low_days}日低点上涨{rise_from_low:.2%}≥{g.etf_low_point_rise_threshold:.0%}")
        if g.etf_enable_stable_signal_trigger:
            if current_price > ma:
                recovery_signals.append("价格站上均线")
            if len(close) >= 2 and close[-1] > close[-2]:
                recovery_signals.append("价格回升")
            if g.etf_previous_drawdown is not None and current_drawdown < g.etf_previous_drawdown:
                recovery_signals.append(f"回撤收窄({current_drawdown:.2%}<{g.etf_previous_drawdown:.2%})")
            if current_rsi is not None and g.etf_previous_rsi is not None and current_rsi > g.etf_previous_rsi:
                recovery_signals.append(f"RSI回升({current_rsi:.1f})")
            drawdown_safe = current_drawdown < g.etf_drawdown_recovery
            if drawdown_safe:
                g.etf_stable_days += 1
            else:
                g.etf_stable_days = 0
        g.etf_previous_drawdown = current_drawdown
        g.etf_previous_rsi = current_rsi
        range_bound_days = 0
        if hasattr(g, 'etf_range_bound_start_date') and g.etf_range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.etf_range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = len(trade_days) - 1
            if range_bound_days >= g.etf_max_range_bound_days:
                recovery_signals.append(f"震荡期满({range_bound_days}个交易日)")
        low_point_rise_condition = g.etf_enable_low_point_rise_trigger and rise_from_low >= g.etf_low_point_rise_threshold
        stable_signal_condition = False
        if g.etf_enable_stable_signal_trigger:
            drawdown_safe = current_drawdown < g.etf_drawdown_recovery
            stable_signal_condition = drawdown_safe and len(recovery_signals) >= 2 and g.etf_stable_days >= 2
        force_condition = range_bound_days >= g.etf_max_range_bound_days
        should_recover = low_point_rise_condition or stable_signal_condition or force_condition
        if should_recover:
            can_switch = True
            if g.etf_last_switch_date is not None:
                trade_days = get_trade_days(start_date=g.etf_last_switch_date, end_date=context.current_dt.date())
                days_since_switch = len(trade_days) - 1
                if days_since_switch < g.etf_filter_switch_cooldown:
                    can_switch = False
            if can_switch:
                g.etf_current_filter = '正常期'
                g.etf_risk_state = '正常期'
                g.etf_last_switch_date = context.current_dt.date()
                g.etf_range_bound_start_date = None
                g.etf_range_bound_days_count = 0
                g.etf_stable_days = 0
                log.info(f"ETF：🔔 【退出震荡期】切换回拉普拉斯滤波器: {'; '.join(recovery_signals)}")
            else:
                log.info("ETF：⏳ 【震荡期退出】冷却期内，暂不切换")
        else:
            log.info("ETF：📌 【震荡期退出检查】未满足退出条件，保持震荡期")
    except Exception as e:
        log.warning(f"ETF：【震荡期退出检查】判断出错: {e}")

def etf_check_and_enter_range_bound_mode(context):
    if not g.etf_enable_range_bound_mode:
        return
    log.info("ETF：🔍 【震荡期检查】开始检测进入条件...")
    can_switch = True
    if g.etf_last_switch_date is not None:
        trade_days = get_trade_days(start_date=g.etf_last_switch_date, end_date=context.current_dt.date())
        days_since_switch = len(trade_days) - 1
        if days_since_switch < g.etf_filter_switch_cooldown:
            can_switch = False
    if g.etf_current_filter == '震荡期' or not can_switch:
        return
    risk_signals = []
    try:
        lookback = max(g.etf_ma_period, g.etf_lookback_high_low_days) + 10
        end_date = context.previous_date
        df = get_price(g.etf_risk_benchmark, end_date=end_date, count=lookback, frequency='daily', fields=['close'], panel=False)
        if df is not None and len(df) >= max(g.etf_ma_period, g.etf_lookback_high_low_days):
            close = df['close'].values
            current_price = close[-1]
            if g.etf_enable_bias_trigger:
                ma = np.mean(close[-g.etf_ma_period:])
                bias = (current_price - ma) / ma if ma > 0 else 0
                if bias > g.etf_bias_threshold:
                    risk_signals.append(f"乖离率过大({bias:.2%}>{g.etf_bias_threshold:.0%})")
            if g.etf_enable_rsi_trigger:
                current_rsi = etf_calculate_rsi(close, period=14)
                if len(close) >= 15 and current_rsi is not None:
                    prev_rsi = etf_calculate_rsi(close[:-1], period=14)
                    if prev_rsi is not None and prev_rsi > g.etf_rsi_overbought and current_rsi < g.etf_rsi_pullback and current_rsi < prev_rsi:
                        risk_signals.append(f"RSI超买回落({prev_rsi:.1f}→{current_rsi:.1f})")
    except Exception as e:
        log.warning(f"ETF：【震荡期检查】获取基准数据异常: {e}")
    if g.etf_enable_stop_loss_trigger and g.etf_stop_loss_triggered_today:
        risk_signals.append("今日触发止损")
        g.etf_stop_loss_triggered_today = False
    if len(risk_signals) > 0:
        g.etf_current_filter = '震荡期'
        g.etf_risk_state = '震荡期'
        g.etf_last_switch_date = context.current_dt.date()
        g.etf_range_bound_start_date = context.current_dt.date()
        g.etf_range_bound_days_count = 0
        g.etf_stable_days = 0
        log.info(f"ETF：🔔 【进入震荡期】切换到高斯滤波器: {'; '.join(risk_signals)}")
    else:
        log.info("ETF：✅ 【震荡期检查】未满足进入条件，保持正常期")

def etf_calculate_and_log_ranked_etfs(context):
    if not hasattr(g, 'etf_merged_etf_pool') or not g.etf_merged_etf_pool:
        log.warning("ETF：【动量计算】合并池为空，无法计算")
        g.etf_ranked_etfs_result = []
        return
    final_list = etf_get_final_ranked_etfs(context)
    g.etf_ranked_etfs_result = final_list

def etf_calculate_momentum_score(price_series, lookback_days):
    if len(price_series) < lookback_days + 1:
        return None, None, None
    recent_price_series = price_series[-(lookback_days + 1):]
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    W = weights ** 2
    W_sum = np.sum(W)
    x_bar = np.sum(W * x) / W_sum
    y_bar = np.sum(W * y) / W_sum
    dx = x - x_bar
    dy = y - y_bar
    variance_x = np.sum(W * dx**2)
    if variance_x == 0:
        return 0, 0, 0
    slope = np.sum(W * dx * dy) / variance_x
    intercept = y_bar - slope * x_bar
    annualized_returns = math.exp(slope * 250) - 1
    y_pred = slope * x + intercept
    ss_res = np.sum(weights * (y - y_pred) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0
    momentum_score = annualized_returns * r_squared
    return momentum_score, annualized_returns, r_squared

def etf_calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    try:
        price_series = np.append(hist_closes, current_price)
        if len(price_series) < max(g.etf_lookback_days, g.etf_short_momentum_lookback) * 0.8:
            return None
        momentum_score, annualized_returns, r_squared = etf_calculate_momentum_score(price_series, g.etf_lookback_days)
        if momentum_score is None:
            return None
        short_momentum_score, short_annualized_returns, short_r_squared = etf_calculate_momentum_score(price_series, g.etf_short_momentum_lookback)
        passed_momentum = (g.etf_min_score_threshold <= momentum_score <= g.etf_max_score_threshold)
        passed_short_momentum = (g.etf_short_momentum_min_score <= short_momentum_score <= g.etf_short_momentum_max_score) if short_momentum_score is not None else False
        volume_ratio = etf_get_volume_ratio(hist_volumes, today_vol, context, g.etf_volume_lookback)
        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.etf_loss:
                passed_loss_filter = False
        premium_rate, passed_premium = etf_calculate_premium_rate(etf, context)
        laplace_value = 0
        laplace_slope = 0
        passed_laplace = False
        gaussian_value = 0
        gaussian_slope = 0
        passed_gaussian = False
        if len(price_series) >= 10:
            try:
                laplace_values = etf_laplace_filter(price_series, s=g.etf_laplace_s_param)
                if len(laplace_values) >= 2:
                    laplace_value = laplace_values[-1]
                    laplace_slope = laplace_values[-1] - laplace_values[-2]
                    passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.etf_laplace_min_slope)
                g1, g2 = etf_gaussian_filter_last_two(price_series, sigma=g.etf_gaussian_sigma)
                gaussian_value = g1
                gaussian_slope = g1 - g2
                passed_gaussian = (current_price > g1 and gaussian_slope > g.etf_gaussian_min_slope)
            except Exception:
                pass
        if g.etf_current_filter == '正常期':
            filter_value = laplace_value
            filter_slope = laplace_slope
            passed_filter = passed_laplace
        else:
            filter_value = gaussian_value
            filter_slope = gaussian_slope
            passed_filter = passed_gaussian
        return {
            'etf': etf, 'etf_name': etf_name, 'momentum_score': momentum_score,
            'short_momentum_score': short_momentum_score, 'annualized_returns': annualized_returns,
            'r_squared': r_squared, 'current_price': current_price, 'volume_ratio': volume_ratio,
            'day_ratios': day_ratios, 'premium_rate': premium_rate, 'passed_momentum': passed_momentum,
            'passed_short_momentum': passed_short_momentum, 'passed_r2': r_squared > g.etf_r2_threshold,
            'passed_volume': volume_ratio is not None and volume_ratio < g.etf_volume_threshold,
            'passed_loss': passed_loss_filter, 'passed_premium': passed_premium,
            'laplace_value': laplace_value, 'laplace_slope': laplace_slope,
            'gaussian_value': gaussian_value, 'gaussian_slope': gaussian_slope,
            'passed_laplace': passed_laplace, 'passed_gaussian': passed_gaussian,
            'filter_value': filter_value, 'filter_slope': filter_slope, 'passed_filter': passed_filter,
        }
    except Exception as e:
        log.debug(f"ETF：【指标计算】{etf} {etf_name} 计算失败: {e}")
        return None

def etf_get_volume_ratio(hist_volumes, today_vol, context, lookback_days=None):
    if lookback_days is None:
        lookback_days = g.etf_volume_lookback
    try:
        if hist_volumes is None or len(hist_volumes) < lookback_days:
            return None
        past_n_days_vol = hist_volumes[-lookback_days:]
        if np.any(np.isnan(past_n_days_vol)) or np.any(past_n_days_vol == 0):
            return None
        avg_volume = np.mean(past_n_days_vol)
        if avg_volume == 0:
            return None
        now = context.current_dt
        elapsed_minutes = (now.hour - 9) * 60 + now.minute - 30
        if now.hour >= 13:
            elapsed_minutes -= 90
        elapsed_minutes = max(1, min(elapsed_minutes, 240))
        projected_today_vol = today_vol * (240.0 / elapsed_minutes)
        return projected_today_vol / avg_volume if avg_volume > 0 else 0
    except Exception:
        return None

def etf_calculate_premium_rate(etf, context):
    try:
        etf_price = getattr(g, 'etf_etf_yesterday_close_batch', {}).get(etf)
        if etf_price is None or pd.isna(etf_price):
            etf_price_df = get_price(etf, start_date=context.previous_date, end_date=context.previous_date, fields=['close'])
            if etf_price_df is None or len(etf_price_df) == 0:
                return None, False
            etf_price = etf_price_df['close'].iloc[-1]
        nav = getattr(g, 'etf_etf_yesterday_nav_batch', {}).get(etf)
        if nav is None or pd.isna(nav):
            nav_df = get_extras('unit_net_value', etf, start_date=context.previous_date, end_date=context.previous_date)
            if nav_df is None or len(nav_df) == 0:
                return None, False
            nav = nav_df.iloc[-1].values[0]
        if nav <= 0 or pd.isna(nav):
            return None, False
        premium_rate = (etf_price - nav) / nav * 100
        passed_premium = premium_rate <= g.etf_max_premium_rate
        return premium_rate, passed_premium
    except Exception:
        return None, True

def etf_gaussian_filter_last_two(price, sigma=1.2):
    n = len(price)
    if n < 2:
        return 0, 0
    idx_1 = np.arange(n)
    weights_1 = np.exp(-((idx_1+1)**2) / (2 * sigma**2))[::-1]
    weights_1 /= np.sum(weights_1)
    g1 = np.sum(price * weights_1)
    price_2 = price[:-1]
    idx_2 = np.arange(n-1)
    weights_2 = np.exp(-((idx_2+1)**2) / (2 * sigma**2))[::-1]
    weights_2 /= np.sum(weights_2)
    g2 = np.sum(price_2 * weights_2)
    return g1, g2

def etf_laplace_filter(price, s=0.05):
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t-1]
    return L

def etf_calculate_rsi(close, period=14):
    try:
        if len(close) < period + 1:
            return None
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except:
        return None

def etf_apply_filters(metrics_list):
    use_short_momentum = g.etf_use_short_momentum_period
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], not use_short_momentum),
        ('短期动量', lambda m: m['passed_short_momentum'], use_short_momentum),
        ('R²', lambda m: m['passed_r2'], g.etf_enable_r2_filter),
        ('成交量', lambda m: m['passed_volume'], g.etf_enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.etf_enable_loss_filter),
        ('溢价率', lambda m: m['passed_premium'], g.etf_enable_premium_filter),
        ('动态滤波', lambda m: m['passed_filter'], g.etf_enable_range_bound_mode),
    ]
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered

def etf_get_final_ranked_etfs(context):
    all_metrics = []
    etf_set = list(g.etf_merged_etf_pool)
    end_date = context.previous_date
    log.info(f"ETF：【动量得分计算】使用合并池，合计{len(etf_set)}只ETF, 当前滤波器: {g.etf_current_filter}")
    use_short_momentum = g.etf_use_short_momentum_period
    lookback = max(g.etf_lookback_days, g.etf_short_momentum_lookback, g.etf_volume_lookback) + 20
    today = context.current_dt.date()
    current_data = get_current_data()
    safe_lookback = lookback + 20
    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d', fields=['close', 'volume'], panel=False)
    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        log.warning("ETF：【动量计算】无法获取历史价格数据")
        return []
    g.etf_etf_yesterday_close_batch = {}
    g.etf_etf_yesterday_nav_batch = {}
    try:
        y_price_df = get_price(etf_set, start_date=end_date, end_date=end_date, fields=['close'], panel=False)
        if y_price_df is not None and not y_price_df.empty:
            g.etf_etf_yesterday_close_batch = y_price_df.groupby('code')['close'].last().to_dict()
        nav_df = get_extras('unit_net_value', etf_set, start_date=end_date, end_date=end_date)
        if nav_df is not None and not nav_df.empty:
            g.etf_etf_yesterday_nav_batch = nav_df.iloc[-1].to_dict()
    except Exception as e:
        log.warning(f"ETF：【动量计算】批量获取溢价率数据异常: {e}")
    today_vols = today_vol_df.groupby('code')['volume'].sum() if (today_vol_df is not None and not today_vol_df.empty) else pd.Series(dtype=float)
    close_pivot = hist_df.pivot(index='time', columns='code', values='close')
    volume_pivot = hist_df.pivot(index='time', columns='code', values='volume')
    for etf in etf_set:
        if current_data[etf].paused:
            continue
        if etf not in close_pivot.columns:
            continue
        raw_closes = close_pivot[etf].values
        raw_volumes = volume_pivot[etf].values
        valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)
        hist_closes = raw_closes[valid_mask]
        hist_volumes = raw_volumes[valid_mask]
        hist_closes = hist_closes[-lookback:]
        hist_volumes = hist_volumes[-lookback:]
        if len(hist_closes) < max(g.etf_lookback_days, g.etf_short_momentum_lookback):
            continue
        etf_name = etf_get_security_name(etf)
        current_price = current_data[etf].last_price
        today_vol = today_vols.get(etf, 0)
        metrics = etf_calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
        if metrics:
            all_metrics.append(metrics)
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
        short_score = item.get('short_momentum_score')
        if pd.isna(short_score) or (isinstance(short_score, float) and np.isnan(short_score)):
            item['short_momentum_score'] = float('-inf')
    if use_short_momentum:
        all_metrics.sort(key=lambda x: x.get('short_momentum_score', float('-inf')), reverse=True)
    else:
        all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    filtered_list = etf_apply_filters(all_metrics)
    if use_short_momentum:
        filtered_list.sort(key=lambda x: x.get('short_momentum_score', float('-inf')), reverse=True)
    else:
        filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    top_10 = filtered_list[:10]
    if not top_10:
        log.info("ETF：（无符合条件的ETF）")
        return []
    score_key = 'short_momentum_score' if use_short_momentum else 'momentum_score'
    if len(top_10) >= g.etf_holdings_num:
        reference_score = top_10[g.etf_holdings_num - 1].get(score_key, float('-inf'))
        score_threshold = reference_score * g.etf_score_threshold_ratio
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        candidate_pool = top_10[:]
    sub_port = get_sub_portfolio(context, 1)
    current_holdings = [sec for sec, pos in sub_port.positions.items() if pos.total_amount > 0]
    candidate_dict = {item['etf']: item for item in candidate_pool}
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    if len(retained) >= g.etf_holdings_num:
        retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        final_result = retained_sorted[:g.etf_holdings_num]
    else:
        need = g.etf_holdings_num - len(retained)
        remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
        additional = remaining_pool[:need]
        final_result = retained + additional
    log.info(f"ETF：【最终目标】共{len(final_result)}只ETF")
    return final_result

def etf_execute_sell_trades(context):
    log.info("ETF：========== 卖出操作开始 ==========")
    ranked_etfs = getattr(g, 'etf_ranked_etfs_result', [])
    target_etfs = []
    if ranked_etfs:
        for metrics in ranked_etfs[:g.etf_holdings_num]:
            target_etfs.append(metrics['etf'])
    else:
        if etf_check_defensive_etf_available(context):
            target_etfs = [g.etf_defensive_etf]
        else:
            target_etfs = []
    g.etf_target_etfs_list = target_etfs
    sub_port = get_sub_portfolio(context, 1)
    current_positions = list(sub_port.positions.keys())
    target_set = set(target_etfs)
    for security in current_positions:
        position = sub_port.positions[security]
        if position.total_amount > 0 and security not in target_set:
            etf_smart_order_target_value(security, 0, context)
    log.info("ETF：========== 卖出操作完成 ==========")

def etf_execute_buy_trades(context):
    log.info("ETF：========== 买入操作开始 ==========")
    target_etfs = g.etf_target_etfs_list
    if not target_etfs:
        log.info("ETF：根据计算的结果，今日无目标ETF，保持空仓")
        return
    sub_port = get_sub_portfolio(context, 1)
    current_positions = set(sub_port.positions.keys())
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.etf_holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    if num_etfs_to_buy <= 0:
        log.info(f"ETF：当前实际持仓数量({actual_holding_count})已达到或超过目标({g.etf_holdings_num})，无需买入")
        return
    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    available_cash = sub_port.available_cash
    allocated_value_per_etf = available_cash // num_etfs_to_buy
    if allocated_value_per_etf < g.etf_min_money:
        log.info(f"ETF：单只ETF分配金额{allocated_value_per_etf:.2f}小于最小交易额{g.etf_min_money:.2f}，无法买入")
        return
    for i, etf in enumerate(etfs_to_buy):
        target_value = allocated_value_per_etf
        if i == len(etfs_to_buy) - 1 and sub_port.available_cash >= g.etf_min_money:
            target_value = sub_port.available_cash
        etf_smart_order_target_value(etf, target_value, context)
    log.info("ETF：========== 买入操作完成 ==========")

def etf_smart_order_target_value(security, target_value, context):
    current_data = get_current_data()
    security_name = etf_get_security_name(security)
    if current_data[security].paused:
        log.info(f"ETF：{security} {security_name}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"ETF：{security} {security_name}: 当前涨停，跳过交易")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"ETF：{security} {security_name}: 当前跌停，跳过交易")
        return False
    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"ETF：{security} {security_name}: 当前价格为0，跳过交易")
        return False
    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    sub_port = get_sub_portfolio(context, 1)
    current_position = sub_port.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < g.etf_min_money:
        log.info(f"ETF：{security} {security_name}: 交易金额{trade_value:.2f}小于最小交易额{g.etf_min_money}，跳过")
        return False
    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"ETF：{security} {security_name}: 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)
    if amount_diff != 0:
        order_result = order(security, amount_diff, pindex=1)
        if order_result:
            if amount_diff > 0:
                log.info(f"ETF：📦 买入{security} {security_name}，数量: {amount_diff}, 价格: {current_price:.3f}")
            else:
                log.info(f"ETF：📤 卖出{security} {security_name}，数量: {abs(amount_diff)}, 价格: {current_price:.3f}")
            return True
        else:
            log.warning(f"ETF：下单失败: {security} {security_name}，数量: {amount_diff}")
            return False
    return False

def etf_minute_level_stop_loss(context):
    if not g.etf_use_fixed_stop_loss:
        return
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    current_data = get_current_data()
    sub_port = get_sub_portfolio(context, 1)
    for security in list(sub_port.positions.keys()):
        position = sub_port.positions[security]
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        cost_price = position.avg_cost
        if cost_price <= 0:
            continue
        if current_price <= cost_price * g.etf_fixedStopLossThreshold:
            security_name = etf_get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"ETF：🚨 【分钟级固定止损】{security} {security_name} 触发止损，亏损: {loss_percent:.2f}%")
            success = etf_smart_order_target_value(security, 0, context)
            if success and g.etf_enable_stop_loss_trigger:
                g.etf_stop_loss_triggered_today = True
                log.info(f"ETF：✅ 【止损触发】记录今日止损，将在13:10检查并进入震荡期")

def etf_minute_level_pct_stop_loss(context):
    if not g.etf_use_pct_stop_loss:
        return
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    current_data = get_current_data()
    current_date = context.current_dt.date()
    if not hasattr(g, 'etf_cache_date') or g.etf_cache_date != current_date:
        g.etf_yesterday_close_cache = {}
        g.etf_cache_date = current_date
    sub_port = get_sub_portfolio(context, 1)
    for security in list(sub_port.positions.keys()):
        position = sub_port.positions[security]
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        yesterday_close = getattr(g, 'etf_yesterday_close_cache', {}).get(security)
        if yesterday_close is None:
            try:
                close_series = attribute_history(security, 1, '1d', ['close'], skip_paused=False)
                if len(close_series['close']) == 0:
                    continue
                yesterday_close = close_series['close'][-1]
                if yesterday_close <= 0:
                    continue
                g.etf_yesterday_close_cache[security] = yesterday_close
            except Exception:
                continue
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        stop_price = yesterday_close * g.etf_pct_stop_loss_threshold
        if current_price <= stop_price:
            security_name = etf_get_security_name(security)
            daily_loss = (current_price / yesterday_close - 1) * 100
            log.info(f"ETF：🚨 【分钟级跌幅止损】{security} {security_name} 触发止损，当日跌幅: {daily_loss:.2f}%")
            success = etf_smart_order_target_value(security, 0, context)
            if success and g.etf_enable_stop_loss_trigger:
                g.etf_stop_loss_triggered_today = True
                log.info(f"ETF：✅ 【止损触发】记录今日止损，将在13:10检查并进入震荡期")

def etf_get_security_name(security):
    try:
        if hasattr(g, 'etf_etf_names_dict') and security in g.etf_etf_names_dict:
            return g.etf_etf_names_dict[security]
        return get_security_info(security).display_name
    except Exception:
        return "未知名称"

def etf_check_defensive_etf_available(context):
    current_data = get_current_data()
    defensive_etf = g.etf_defensive_etf
    if current_data[defensive_etf].paused:
        log.info(f"ETF：防御性ETF {defensive_etf} 今日停牌")
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        log.info(f"ETF：防御性ETF {defensive_etf} 当前涨停")
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        log.info(f"ETF：防御性ETF {defensive_etf} 当前跌停")
        return False
    return True