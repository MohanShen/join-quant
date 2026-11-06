# Clone from JoinQuant
# postId: 8e8aa1083dd18331e72564705847fdf7
# backtestId: fd45080b1db0c19e75fc95fb51b1f47e
# title: 左侧抄底反弹抓涨策略

# 完整策略：左侧抄底 + 反弹趋势确认（实时止损）
import jqdata
import pandas as pd
import datetime

def initialize(context):
    # ====== 核心选股参数 ======
    g.lookback_days = 180              # 回溯窗口天数（自然日），用于计算最低价/最高价
    g.T_minus = 10                     # T-N日（用于计算最低价和涨幅区间，可调）
    g.rise_low_threshold = 0.001        # 当前价相对回溯窗口最低价涨幅下限（5%）
    g.rise_high_threshold = 0.20       # 当前价相对回溯窗口最低价涨幅上限（10%）
    g.pre_drop_threshold = 0.10        #停用 T-N日前10个交易日的跌幅要求（>10%下跌）
    g.limit_down_threshold = -0.095    #停用 跌停判定阈值（跌幅 ≤ -9.5% 视为跌停）
    g.min_price_threshold = 2.0        # 最低股价限制（低于此价格不买入）

    # ====== 移动止盈参数 ======
    g.trailing_profit_trigger = 0.10   # 触发移动止盈的最低收益率（9%）
    g.trailing_profit_retracement = 0  # 从最高点回撤超过此比例则卖出（5%），设为0则立即止盈

    # ====== 其他可调参数 ======
    g.stop_loss = -0.10                # 止损收益率（-10%）
    g.max_hold_days = 15               # 最大持有交易日数（含买入当天）
    g.max_rise_10d = 0.25              # 前N日最高价相对回溯窗口最低价涨幅上限（16%）
    g.max_days_rise_4pct = 10           #停用 前N日内涨幅>4%的最大允许天数
    g.min_days_between_high_low = 90   # 回溯窗口内高低点相隔最少天数（自然日）
    g.max_candidate_count = 10         # 候选数量达到此上限则全部放弃（≥此值放弃）
    g.blacklist_days = 60              # 黑名单禁买交易日数
    g.max_stock_count = 1              # 单票满仓（固定为1）

    # 时间设置
    g.buy_time = '09:35'
    g.sell_time_1 = '14:50'    # 用于超时和ST检查，止损已在profit_check中实时处理
    g.sell_time_2 = '09:30'

    # 状态变量
    g.blacklist = {}
    g.hold_info = {}
    g.highest_profit = {}

    # 定时任务
    run_daily(check_stocks, time=g.buy_time)
    run_daily(sell_check, time=g.sell_time_1)
    run_daily(sell_check, time=g.sell_time_2)
    run_daily(profit_check, time='every_bar')  # 每分钟执行，包含止损和止盈
    run_daily(after_trading_end, time='after_close')

# ================== 收盘后打印持仓 ==================
def after_trading_end(context):
    today = context.current_dt.date()
    for stock, position in context.portfolio.positions.items():
        if position.total_amount == 0:
            continue
        buy_info = g.hold_info.get(stock)
        if buy_info is None:
            continue
        buy_price = buy_info['buy_price']
        price_data = get_price(stock, end_date=today, count=1, fields=['close'])
        if price_data is None or price_data.empty:
            continue
        current_price = price_data['close'].iloc[-1]
        if pd.isna(current_price):
            continue
        ret = (current_price - buy_price) / buy_price
        if stock not in g.highest_profit or ret > g.highest_profit[stock]:
            g.highest_profit[stock] = ret
        log.info('收盘持仓: {}, 数量: {}, 成本: {:.2f}, 现价: {:.2f} 增加显示：当前收益 {:.2%}, 最高收益 {:.2%}'.format(
            stock, position.total_amount, buy_price, current_price, ret, g.highest_profit.get(stock, ret)
        ))

# ================== 选股与买入 ==================
def check_stocks(context):
    today = context.current_dt.date()
    if context.portfolio.positions:
        return
    market_scan_and_buy(context, today)

def market_scan_and_buy(context, today):
    all_stocks = get_all_securities(['stock']).index.tolist()
    stocks = [s for s in all_stocks if not s.startswith(('688', '8', '4'))]
    if not stocks:
        return

    # ---- 基础过滤 ----
    current_data = get_current_data()
    try:
        st_data = get_extras('is_st', stocks, start_date=today, end_date=today)
        if today in st_data.index:
            st_series = st_data.loc[today]
        else:
            st_series = st_data.iloc[0]
    except:
        st_series = pd.Series({s: False for s in stocks})
    paused_series = pd.Series({s: current_data[s].paused for s in stocks})
    securities_info = get_all_securities(['stock'])
    start_dates = securities_info['start_date']
    listed_ok = (today - start_dates).dt.days >= 200
    base_filter = (~st_series) & (~paused_series) & listed_ok
    log.info('基础过滤后剩余股票数: {}'.format(base_filter.sum()))

    # ---- 获取数据 ----
    lookback_days = g.lookback_days
    extra_days = g.T_minus + 20
    date_lookback_start = today - datetime.timedelta(days=lookback_days)
    start_date = date_lookback_start - datetime.timedelta(days=extra_days)
    price_data = get_price(stocks, start_date=start_date, end_date=today,
                           fields=['open', 'high', 'low', 'close'],
                           skip_paused=False, fq='pre')
    if price_data is None or price_data.empty:
        return

    open_df = price_data['open']
    high_df = price_data['high']
    low_df = price_data['low']
    close_df = price_data['close']

    date_list = open_df.index.tolist()
    if len(date_list) < g.T_minus + 10:
        log.warning('交易日不足 {} 天，跳过'.format(g.T_minus + 10))
        return

    t_minus_date = date_list[-(g.T_minus + 1)]
    t_minus_9_date = date_list[-(g.T_minus + 1 + 9)]
    yesterday = date_list[-2] if len(date_list) >= 2 else date_list[0]
    start_date_lookback = date_lookback_start

    # ---- 计算指标 ----
    low_lookback = low_df.loc[start_date_lookback:today].min(axis=0)
    high_lookback = high_df.loc[start_date_lookback:today].max(axis=0)
    low_Tminus = low_df.loc[t_minus_date] if t_minus_date in low_df.index else pd.Series(index=stocks)
    open_today = open_df.loc[today] if today in open_df.index else pd.Series(index=stocks)
    high_sub = high_df.loc[t_minus_date:yesterday] if t_minus_date in high_df.index else high_df.loc[:yesterday]
    max_high_Tminus = high_sub.max(axis=0)

    start_recent = date_list[-(g.T_minus + 1)] if len(date_list) >= g.T_minus + 1 else date_list[0]
    recent_low = low_df.loc[start_recent:today].min(axis=0)

    # ---- 条件⑨：前10日跌幅 ----
    close_Tminus = close_df.loc[t_minus_date] if t_minus_date in close_df.index else pd.Series(index=stocks)
    close_Tminus_9 = close_df.loc[t_minus_9_date] if t_minus_9_date in close_df.index else pd.Series(index=stocks)
    drop_10d = (close_Tminus - close_Tminus_9) / close_Tminus_9
    cond9 = drop_10d <= -g.pre_drop_threshold

    # ---- 条件⑩：前10日无跌停 ----
    low_range = low_df.loc[t_minus_9_date:t_minus_date]
    close_range = close_df.loc[t_minus_9_date:t_minus_date]
    prev_close = close_range.shift(1)
    daily_drop = (low_range - prev_close) / prev_close
    has_limit_down = (daily_drop <= g.limit_down_threshold).any(axis=0)
    cond10 = ~has_limit_down

    # ---- 条件⑪：股价不低于最低阈值 ----
    cond_price = (open_today >= g.min_price_threshold) & (open_today.notna())

    # ---- 涨停检查 ----
    high_recent = high_df.loc[start_recent:today]
    prev_close_recent = close_df.loc[start_recent:today].shift(1)
    high_ret = (high_recent - prev_close_recent) / prev_close_recent

    has_limit_up = pd.Series(index=stocks, dtype=bool)
    for stock in stocks:
        if stock not in high_ret.columns:
            has_limit_up[stock] = False
            continue
        ret_series = high_ret[stock]
        valid_ret = ret_series.dropna()
        if len(valid_ret) == 0:
            has_limit_up[stock] = False
            continue
        max_ret = valid_ret.max()
        threshold = 0.195 if stock.startswith(('300', '301')) else 0.095
        has_limit_up[stock] = max_ret >= threshold

    cond5 = ~has_limit_up

    # ---- 前 T_minus 日内涨幅>4%天数 ----
    close_prev = close_df.loc[t_minus_date:yesterday]
    if len(close_prev) >= 2:
        prev_close_prev = close_prev.shift(1)
        daily_ret_prev = (close_prev - prev_close_prev) / prev_close_prev
        daily_ret_valid = daily_ret_prev.iloc[1:]
    else:
        daily_ret_valid = pd.DataFrame()
    days_gt_4pct = (daily_ret_valid > 0.04).sum(axis=0)

    # ---- 条件 ----
    low = g.rise_low_threshold
    high = g.rise_high_threshold
    rise = (open_today - low_Tminus) / low_Tminus
    cond1 = (rise > low) & (rise < high)
    cond2 = abs(low_Tminus - low_lookback) <= 0.001
    cond3 = low_Tminus < high_lookback * 0.5
    cond4 = recent_low >= low_Tminus
    cond6 = (max_high_Tminus - low_lookback) / low_lookback <= g.max_rise_10d
    cond7 = days_gt_4pct <= g.max_days_rise_4pct
    low_lookback_idx = low_df.loc[start_date_lookback:today].idxmin(axis=0)
    high_lookback_idx = high_df.loc[start_date_lookback:today].idxmax(axis=0)
    days_between = abs((low_lookback_idx - high_lookback_idx).dt.days)
    cond8 = days_between >= g.min_days_between_high_low

    all_cond = base_filter & cond1 & cond2 & cond3 & cond4 & cond5 & cond6 & cond7 & cond8 & cond_price

    mask = all_cond.fillna(False)
    stocks_series = pd.Series(stocks, index=stocks)
    candidates = stocks_series[mask].tolist()

    log.info('今日选股筛选出 {} 只候选股票'.format(len(candidates)))

    if candidates:
        log.info('候选股票详情（按涨幅排序）：')
        mid = (g.rise_low_threshold + g.rise_high_threshold) / 2
        detail_list = []
        for stock in candidates:
            base = low_lookback[stock]
            price = open_today[stock] if stock in open_today.index else None
            if price is not None and not pd.isna(price):
                rise_val = (price - base) / base
                dev = abs(rise_val - mid)
                detail_list.append((stock, base, rise_val, dev))
        detail_list.sort(key=lambda x: x[2])
        for stock, base, rise_val, dev in detail_list:
            log.info('  {}  基低{:.2f}  涨幅{:.2%}  距中点{:.2%}'.format(stock, base, rise_val, dev))

    # ---- 买入决策 ----
    if len(candidates) >= g.max_candidate_count:
        log.info('候选数量{}达到上限({})，全部放弃'.format(len(candidates), g.max_candidate_count))
        return
    elif len(candidates) == 0:
        return
    elif len(candidates) == 1:
        stock = candidates[0]
        base_low = low_lookback[stock]
        if stock in g.blacklist and g.blacklist[stock] > today:
            log.info('候选股票在黑名单，跳过')
            return
        buy_stock(context, stock, base_low)
    else:
        mid = (g.rise_low_threshold + g.rise_high_threshold) / 2
        candidate_info = []
        for stock in candidates:
            base = low_lookback[stock]
            price = open_today[stock] if stock in open_today.index else None
            if price is None or pd.isna(price):
                continue
            rise_val = (price - base) / base
            deviation = abs(rise_val - mid)
            candidate_info.append((stock, rise_val, deviation, base))
        if not candidate_info:
            return
        candidate_info.sort(key=lambda x: x[2])
        best_stock, best_rise, best_dev, base_low = candidate_info[0]
        log.info('选择股票: {}，涨幅 {:.2%}，距中点 {:.2%}，基准最低价 {:.2f}'.format(
            best_stock, best_rise, best_dev, base_low))
        if best_stock in g.blacklist and g.blacklist[best_stock] > today:
            log.info('目标股票在黑名单，跳过')
            return
        buy_stock(context, best_stock, base_low)

# ================== 买卖函数 ==================
def buy_stock(context, stock, base_low):
    if stock in g.blacklist and g.blacklist[stock] > context.current_dt.date():
        return
    cash = context.portfolio.available_cash
    if cash <= 0:
        return
    current_data = get_current_data()
    if current_data[stock].paused:
        log.info('{} 当前停牌，跳过买入'.format(stock))
        return
    current_price = current_data[stock].last_price
    if current_price is None or pd.isna(current_price):
        return
    if current_price < g.min_price_threshold:
        log.info('{} 当前价格 {:.2f} 低于最低价格限制 {:.2f}，放弃买入'.format(stock, current_price, g.min_price_threshold))
        return
    order_target_value(stock, cash)
    log.info('买入 {} 价格 {:.2f} 基准最低价 {:.2f}, 金额 {:.2f}'.format(stock, current_price, base_low, cash))
    g.hold_info[stock] = {'buy_date': context.current_dt.date(), 'buy_price': current_price}
    g.highest_profit[stock] = 0.0

# ================== 实时监控（包含止损和移动止盈） ==================
def profit_check(context):
    """每分钟执行：包含止损和移动止盈"""
    today = context.current_dt.date()
    for stock, position in context.portfolio.positions.items():
        if position.total_amount == 0:
            continue
        buy_info = g.hold_info.get(stock)
        if buy_info is None:
            continue
        # T+1 保护：当天买入不操作
        if buy_info['buy_date'] == today:
            continue

        buy_price = buy_info['buy_price']
        current_price = get_current_data()[stock].last_price
        if current_price is None:
            continue
        ret = (current_price - buy_price) / buy_price

        # 更新最高收益
        if stock not in g.highest_profit or ret > g.highest_profit[stock]:
            g.highest_profit[stock] = ret

        # ---- 1. 止损（优先级最高） ----
        if ret <= g.stop_loss:
            order_target_value(stock, 0)  # 市价卖出
            log.info('止损卖出: {}，当前收益 {:.2%}，触发实时止损'.format(stock, ret))
            add_to_blacklist(stock, today)
            continue  # 已平仓，跳过后续检查

        # ---- 2. 移动止盈 ----
        if ret >= g.trailing_profit_trigger:
            if g.trailing_profit_retracement == 0:
                order_target_value(stock, 0)
                log.info('移动止盈（回撤0%%）：{} 当前收益 {:.2%}，触发即卖出'.format(stock, ret))
                add_to_blacklist(stock, today)
                continue
            highest_ret = g.highest_profit[stock]
            drawdown = (highest_ret - ret) / (1 + highest_ret) if highest_ret >= 0 else 0
            if drawdown >= g.trailing_profit_retracement:
                order_target_value(stock, 0)
                log.info('移动止盈：{} 当前收益 {:.2%}，最高收益 {:.2%}，回撤 {:.2%} >= 阈值 {:.2%}，卖出'.format(
                    stock, ret, highest_ret, drawdown, g.trailing_profit_retracement))
                add_to_blacklist(stock, today)

# ================== 卖出检查（超时、ST） ==================
def sell_check(context):
    """检查超时、ST（当天买入的股票跳过）"""
    today = context.current_dt.date()
    for stock, position in context.portfolio.positions.items():
        if position.total_amount == 0:
            continue
        buy_info = g.hold_info.get(stock)
        if buy_info is None:
            continue
        if buy_info['buy_date'] == today:
            continue

        # ST 强制卖出
        try:
            st_data = get_extras('is_st', [stock], start_date=today, end_date=today)
            if not st_data.empty and st_data.loc[today, stock]:
                order_target_value(stock, 0)
                log.info('ST强制卖出: {}'.format(stock))
                add_to_blacklist(stock, today)
                continue
        except:
            pass

        buy_price = buy_info['buy_price']
        current_price = get_current_data()[stock].last_price
        if current_price is None:
            continue
        ret = (current_price - buy_price) / buy_price

        # 如果已经触发止盈或止损（已由profit_check处理），这里不再重复
        # 超时检查：仅当未触发移动止盈（收益低于触发线）时才执行
        if ret >= g.trailing_profit_trigger:
            continue  # 已进入止盈模式，超时豁免

        hold_days = len(jqdata.get_trade_days(start_date=buy_info['buy_date'], end_date=today))
        if hold_days >= g.max_hold_days:
            order_target_value(stock, 0)
            log.info('超时卖出: {}, 当前收益: {:.2%}, 最高收益: {:.2%}, 持仓天数(交易日): {}'.format(
                stock, ret, g.highest_profit.get(stock, ret), hold_days
            ))
            add_to_blacklist(stock, today)
            continue

def add_to_blacklist(stock, date):
    g.blacklist[stock] = date + datetime.timedelta(days=g.blacklist_days)
    if stock in g.hold_info:
        del g.hold_info[stock]
    if stock in g.highest_profit:
        del g.highest_profit[stock]