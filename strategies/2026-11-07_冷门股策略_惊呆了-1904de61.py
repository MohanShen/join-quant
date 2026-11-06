# Clone from JoinQuant
# postId: 1904de61578628fce8c6a5029d8fee6e
# backtestId: d466de2592c65455a2bd598a4c6a6925
# title: 冷门股策略，惊呆了。

# 导入函数库
from jqdata import *
import math
import numpy as np
from scipy.stats import spearmanr
import datetime
import pandas as pd

def set_param():
    # 交易设置
    g.stocknum = 4                     # 理想持股数量
    g.bearpercent = 0.3                # 熊市仓位
    g.bearposition = True              # 熊市是否持仓
    g.sellrank = 10                    # 排名多少位之后(不含)卖出
    g.buyrank = 9                      # 排名多少位之前(含)可以买入

    # 初始筛选
    g.tradeday = 300                   # 上市天数
    g.increase1d = 0.087               # 前一日涨幅
    g.tradevaluemin = 0.01             # 最小流通市值 单位（亿）
    g.tradevaluemax = 1000             # 最大流通市值 单位（亿）
    g.pbmin = 0.01                     # 最小市净率
    g.pbmax = 30                       # 最大市净率

    # 排名条件及权重，正数代表从小到大，负数表示从大到小
    # 各因子权重：总市值，流通市值，最新价格，5日平均成交量，60日涨幅，ROE，波动率(倒数)
    # 注意：该权重仅作为 fallback，动态权重启用时会被覆盖
    g.fallback_weights = [5, 5, 8, 4, 10, 5, 8]   # 新增波动率权重
    
    # 配置择时
    g.MA = ['000001.XSHG', 10]         # 均线择时（大盘指数）
    g.choose_time_signal = True        # 启用择时信号
    g.threshold = 0.003                # 牛熊切换阈值

    # 冷却期设置（替代原有的 g.buyagain）
    g.cooling_profit_days = 5          # 盈利卖出冷却天数
    g.cooling_loss_days = 20           # 止损卖出冷却天数

    # 动态权重相关设置
    g.dynamic_weight_enable = False      # 是否启用动态权重
    g.ic_window = 60                    # 计算IC的滚动窗口（天）
    g.ic_horizon = 5                    # 预测未来N天收益
    g.weights_update_freq = 5           # 每N天更新一次权重（减少计算量）
    g.last_weight_update_date = None
    g.current_weights = None            # 存储当前使用的动态权重

    # 小盘控制相关设置
    g.small_index = '000852.XSHG'       # 小盘代表指数（中证1000）
    g.enable_smallcap_control = True    # 是否启用小盘控制（基于大盘+小盘组合仓位）
    g.is_small_bull = False             # 小盘是否牛市，将在运行时更新

    # 波动率因子相关设置
    g.volatility_window = 20            # 计算波动率的窗口（天）
    g.enable_volatility_factor = True   # 是否启用波动率因子（若关闭，则权重中波动率项为0）

    # ================== 止损设置 ==================
    g.stop_loss_fixed = -0.15           # 固定止损阈值（亏损20%）
    g.enable_dynamic_stop = True        # 是否启用动态止损（根据波动率调整）
    g.base_volatility = 0.02            # 基准波动率（日均收益率标准差2%）
    g.dynamic_stop_range = [-0.50, -0.10]  # 动态止损的上下限（-50% ~ -10%）
    
    g.consecutive_loss_days = 3         # 连续亏损天数阈值（基于买入成本）
    g.consecutive_loss_enable = True    # 是否启用连续亏损止损

# ========== 辅助函数 ==========
def get_growth_rate(code, n=20):
    lc = get_close_price(code, n)
    c = get_close_price(code, 1, '1m')
    if not isnan(lc) and not isnan(c) and lc != 0:
        return (c - lc) / lc
    else:
        log.error("数据非法, code: %s, %d日收盘价: %f, 当前价: %f" %(code, n, lc, c))
        return 0

def get_growth_rate60(code):
    price60d = attribute_history(code, 60, '1d', 'close', False)['close'][0]
    pricenow = get_close_price(code, 1, '1m')
    if not isnan(pricenow) and not isnan(price60d) and price60d != 0:
        return pricenow / price60d
    else:
        return 100

def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list, df=False)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys() 
        or last_prices[stock][-1] < current_data[stock].high_limit]

def get_close_price(code, n, unit='1d'):
    return attribute_history(code, n, unit, 'close', df=False)['close'][0]

def close_position(code, reason='adjust'):
    """
    卖出股票，并根据卖出原因设置冷却期。
    reason: 'adjust' (调仓卖出) 或 'stop_loss' (止损卖出)
    """
    order = order_target_value(code, 0)
    if order is not None and order.status == OrderStatus.held:
        if reason == 'stop_loss':
            g.sold_stock_loss[code] = g.cooling_loss_days
            log.info("股票 %s 因止损卖出，进入 %d 天冷却期" % (code, g.cooling_loss_days))
        else:
            g.sold_stock_profit[code] = g.cooling_profit_days
            log.info("股票 %s 因调仓卖出，进入 %d 天冷却期" % (code, g.cooling_profit_days))

def clear_position(context):
    if context.portfolio.positions:
        log.info("==> 清仓，卖出所有股票")
        for stock in context.portfolio.positions.keys():
            close_position(stock)  # 清仓按调仓处理

def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list 
        if not current_data[stock].is_st 
        and 'ST' not in current_data[stock].name 
        and '*' not in current_data[stock].name 
        and '退' not in current_data[stock].name]

def filter_gem_stock(context, stock_list):
    return [stock for stock in stock_list if stock[0:3] != '300' and stock[0:3] != "688"]

def filter_new_stock(context, stock_list):
    return [stock for stock in stock_list if (context.previous_date - datetime.timedelta(days=g.tradeday)) > get_security_info(stock).start_date]

def filter_increase1d(stock_list):
    return [stock for stock in stock_list if get_close_price(stock, 1) / get_close_price(stock, 2) < (1 + g.increase1d)]

def filter_buyagain(stock_list):
    """
    过滤掉处于冷却期内的股票（无论是盈利卖出冷却还是止损卖出冷却）
    """
    return [stock for stock in stock_list 
            if stock not in g.sold_stock_profit and stock not in g.sold_stock_loss]

def get_stock_list(context):
    df = get_fundamentals(query(valuation.code).filter(valuation.pb_ratio.between(g.pbmin, g.pbmax)
        ).order_by(valuation.circulating_market_cap.asc()).limit(1000)).dropna()
    stock_list = list(df['code'])
    stock_list = filter_gem_stock(context, stock_list)
    stock_list = filter_st_stock(stock_list)
    stock_list = filter_paused_stock(stock_list)
    stock_list = filter_limitup_stock(context, stock_list)
    stock_list = filter_new_stock(context, stock_list)
    stock_list = filter_increase1d(stock_list)
    stock_list = filter_buyagain(stock_list)
    return stock_list

# ========== 动态权重相关函数 ==========
def calc_factor_ic(factor_dict, ret_dict):
    stocks = [s for s in factor_dict.keys() if s in ret_dict]
    if len(stocks) < 10:
        return None
    factor_vals = [factor_dict[s] for s in stocks]
    ret_vals = [ret_dict[s] for s in stocks]
    ic, _ = spearmanr(factor_vals, ret_vals)
    return ic

def get_dynamic_weights(context, stock_list):
    if len(stock_list) < 50:
        return g.fallback_weights
    end_date = context.current_dt.date()
    start_date = end_date - datetime.timedelta(days=g.ic_window + g.ic_horizon + 10)
    df_price = get_price(stock_list, start_date=start_date, end_date=end_date,
                         fields=['close', 'volume'])
    if df_price is None or len(df_price) == 0:
        return g.fallback_weights
    close_df = df_price['close']
    volume_df = df_price['volume']
    if isinstance(close_df, pd.Series):
        close_df = pd.DataFrame(close_df)
        volume_df = pd.DataFrame(volume_df)
    all_dates = sorted(close_df.index)
    if len(all_dates) < g.ic_window + g.ic_horizon:
        return g.fallback_weights
    ic_lists = [[] for _ in range(7)]
    step = 2
    for idx in range(0, len(all_dates) - g.ic_window - g.ic_horizon, step):
        date_t = all_dates[idx]
        date_future = all_dates[idx + g.ic_horizon]
        q_cap = query(valuation.code, valuation.market_cap, valuation.circulating_market_cap)\
                .filter(valuation.code.in_(stock_list))
        df_cap = get_fundamentals(q_cap, date=date_t)
        if df_cap.empty:
            continue
        cap_dict = dict(zip(df_cap['code'], df_cap['market_cap']))
        circ_cap_dict = dict(zip(df_cap['code'], df_cap['circulating_market_cap']))
        if date_t not in close_df.index:
            continue
        close_t = close_df.loc[date_t]
        try:
            idx_t = all_dates.index(date_t)
            if idx_t >= 4:
                vol_5d = volume_df.loc[all_dates[idx_t-4:idx_t+1]].mean(axis=0)
                volume_5d_dict = vol_5d.to_dict()
            else:
                continue
        except:
            continue
        try:
            idx_60 = all_dates.index(date_t)
            if idx_60 >= 60:
                close_60d_ago = close_df.loc[all_dates[idx_60-60]]
                ret60_dict = {}
                for stock in stock_list:
                    if stock in close_t and stock in close_60d_ago and close_60d_ago[stock] != 0:
                        ret60_dict[stock] = close_t[stock] / close_60d_ago[stock]
            else:
                continue
        except:
            continue
        q_roe = query(indicator.code, indicator.roe).filter(indicator.code.in_(stock_list))
        df_roe = get_fundamentals(q_roe, date=date_t)
        if df_roe.empty:
            continue
        roe_dict = dict(zip(df_roe['code'], df_roe['roe']))
        volatility_dict = {}
        for stock in stock_list:
            try:
                pos = all_dates.index(date_t)
                if pos >= g.volatility_window:
                    start_pos = pos - g.volatility_window
                    close_series = close_df.loc[all_dates[start_pos:pos+1], stock]
                    if len(close_series) >= g.volatility_window+1:
                        returns = np.diff(np.log(close_series.values))
                        vol = np.std(returns)
                        if not np.isnan(vol) and vol > 1e-6:
                            volatility_dict[stock] = 1.0 / vol
                        else:
                            volatility_dict[stock] = 0.0
                    else:
                        volatility_dict[stock] = 0.0
                else:
                    volatility_dict[stock] = 0.0
            except:
                volatility_dict[stock] = 0.0
        factor_dicts = [
            cap_dict, circ_cap_dict, close_t.to_dict(),
            volume_5d_dict, ret60_dict, roe_dict, volatility_dict
        ]
        if date_future not in close_df.index:
            continue
        close_future = close_df.loc[date_future]
        ret_dict = {}
        for stock in stock_list:
            if stock in close_t and stock in close_future and close_t[stock] != 0:
                ret_dict[stock] = close_future[stock] / close_t[stock] - 1
        for i, fdict in enumerate(factor_dicts):
            if fdict is None or len(fdict) == 0:
                continue
            ic = calc_factor_ic(fdict, ret_dict)
            if ic is not None:
                ic_lists[i].append(ic)
    mean_ic = []
    for i in range(7):
        if len(ic_lists[i]) > 5:
            mean_ic.append(np.mean(ic_lists[i]))
        else:
            mean_ic.append(0)
    raw_weights = [max(0, m) for m in mean_ic]
    total = sum(raw_weights)
    if total > 0:
        weights = [w / total for w in raw_weights]
    else:
        weights = [1.0/7] * 7
    if g.current_weights is not None:
        alpha = 0.7
        weights = [alpha * w + (1-alpha) * gw for w, gw in zip(weights, g.current_weights)]
    return weights

# ========== 波动率倒数计算 ==========
def get_volatility_inv(code, window=20):
    try:
        close_prices = attribute_history(code, window+1, '1d', 'close', df=False)['close']
        if len(close_prices) < window+1:
            return 0.0
        returns = np.diff(np.log(close_prices))
        vol = np.std(returns)
        if np.isnan(vol) or vol <= 1e-6:
            return 0.0
        return 1.0 / vol
    except:
        return 0.0

# ========== 动态止损阈值计算 ==========
def get_dynamic_stop_loss(code):
    if not g.enable_dynamic_stop:
        return g.stop_loss_fixed
    try:
        vol_inv = get_volatility_inv(code, g.volatility_window)
        if vol_inv > 0:
            vol = 1.0 / vol_inv
        else:
            vol = 0.02
    except:
        vol = 0.02
    ratio = g.base_volatility / max(vol, 0.005)
    dynamic_stop = g.stop_loss_fixed * ratio
    dynamic_stop = max(g.dynamic_stop_range[0], min(g.dynamic_stop_range[1], dynamic_stop))
    return dynamic_stop

# ========== 选股排序函数 ==========
def get_stock_rank_m_m(context, stock_list):
    rank_stock_list = get_fundamentals(query(
        valuation.code, valuation.market_cap, valuation.circulating_market_cap
        ).filter(valuation.code.in_(stock_list)
        ).order_by(valuation.circulating_market_cap.asc()).limit(100))
    if rank_stock_list is None or len(rank_stock_list) == 0:
        return []
    codes = list(rank_stock_list['code'])
    q_roe = query(indicator.code, indicator.roe).filter(indicator.code.in_(codes))
    df_roe = get_fundamentals(q_roe)
    if df_roe is not None and not df_roe.empty:
        roe_dict = dict(zip(df_roe['code'], df_roe['roe']))
        valid_codes = [c for c in codes if c in roe_dict and roe_dict[c] is not None and roe_dict[c] > 0]
        if len(valid_codes) == 0:
            return []
        rank_stock_list = rank_stock_list[rank_stock_list['code'].isin(valid_codes)].reset_index(drop=True)
        codes = list(rank_stock_list['code'])
    else:
        return []
    volume5d = [attribute_history(stock, 1200, '1m', 'volume', df=False)['volume'].sum() for stock in codes]
    increase60d = [get_growth_rate60(stock) for stock in codes]
    current_price = [get_close_price(stock, 1, '1m') for stock in codes]
    roe_list = [roe_dict.get(stock, 0) for stock in codes]
    volatility_inv_list = [get_volatility_inv(stock, g.volatility_window) for stock in codes]
    
    min_price = min(current_price)
    min_increase60d = min(increase60d)
    min_circulating_market_cap = min(rank_stock_list['circulating_market_cap'])
    min_market_cap = min(rank_stock_list['market_cap'])
    min_volume = min(volume5d)
    roe_inv_list = [1.0 / r if r > 0 else float('inf') for r in roe_list]
    min_roe_inv = min(roe_inv_list)
    min_vol_inv = min(volatility_inv_list) if volatility_inv_list else 1.0
    if min_vol_inv == 0:
        min_vol_inv = 1.0
    
    if g.dynamic_weight_enable:
        weights = g.current_weights if g.current_weights is not None else g.fallback_weights
    else:
        weights = g.fallback_weights
    if weights is None or len(weights) != 7:
        weights = g.fallback_weights
    
    totalcount = []
    for i in range(len(codes)):
        vol_ratio = min_vol_inv / volatility_inv_list[i] if volatility_inv_list[i] > 0 else 1.0
        score = (
            math.log(min_market_cap / rank_stock_list['market_cap'][i]) * weights[0] +
            math.log(min_circulating_market_cap / rank_stock_list['circulating_market_cap'][i]) * weights[1] +
            math.log(min_price / current_price[i]) * weights[2] +
            math.log(min_volume / volume5d[i]) * weights[3] +
            math.log(min_increase60d / increase60d[i]) * weights[4] +
            math.log(min_roe_inv / roe_inv_list[i]) * weights[5] +
            math.log(vol_ratio) * weights[6]
        )
        totalcount.append([i, score])
    totalcount.sort(key=lambda x: x[1], reverse=True)
    return [rank_stock_list['code'][totalcount[i][0]] for i in range(min(g.sellrank, len(totalcount)))]

# ========== 牛熊判断 ==========
def get_small_bull_bear_signal_minute():
    nowindex = get_close_price(g.small_index, 1, '1m')
    MAold = (attribute_history(g.small_index, g.MA[1] - 1, '1d', 'close', df=False)['close'].sum() + nowindex) / g.MA[1]
    if g.is_small_bull:
        if nowindex * (1 + g.threshold) <= MAold:
            g.is_small_bull = False
    else:
        if nowindex > MAold * (1 + g.threshold):
            g.is_small_bull = True

def get_bull_bear_signal_minute():
    nowindex = get_close_price(g.MA[0], 1, '1m')
    MAold = (attribute_history(g.MA[0], g.MA[1] - 1, '1d', 'close', df=False)['close'].sum() + nowindex) / g.MA[1]
    if g.isbull:
        if nowindex * (1 + g.threshold) <= MAold:
            g.isbull = False
    else:
        if nowindex > MAold * (1 + g.threshold):
            g.isbull = True

def get_target_position_ratio():
    if not g.choose_time_signal:
        return 1.0
    if not g.enable_smallcap_control:
        return 1.0 if g.isbull else g.bearpercent
    if g.isbull and not g.is_small_bull:
        return 1.0
    elif not g.isbull and g.is_small_bull:
        return 0.8
    elif not g.isbull and not g.is_small_bull:
        return 0.3
    else:
        return 1.0

# ========== 调仓函数 ==========
def my_adjust_position(context, hold_stocks):
    position_ratio = g.current_position_ratio
    free_value = context.portfolio.total_value * position_ratio
    maxpercent = 1.3 / g.stocknum * position_ratio
    buycash = free_value / g.stocknum
    for stock in context.portfolio.positions.keys():
        current_data = get_current_data()
        nosell_1 = context.portfolio.positions[stock].price >= current_data[stock].high_limit
        sell_2 = stock not in hold_stocks
        if sell_2 and not nosell_1:
            close_position(stock)  # 调仓卖出，使用默认 reason='adjust'
        else:
            current_percent = context.portfolio.positions[stock].value / context.portfolio.total_value
            if current_percent > maxpercent:
                order_target_value(stock, buycash)

def mybuy(context):
    if not g.nohold:
        hold_stocks = filter_buyagain(g.chosen_stock_list)
        log.info("待买股票列表：%s" %(hold_stocks))
        position_ratio = g.current_position_ratio
        free_value = context.portfolio.total_value * position_ratio
        minpercent = 0.7 / g.stocknum * position_ratio
        buycash = free_value / g.stocknum
        for i in range(min(g.buyrank, len(hold_stocks))):
            free_cash = free_value - context.portfolio.positions_value
            if hold_stocks[i] not in get_blacklist() and free_cash > context.portfolio.total_value / (g.stocknum * 10):
                if hold_stocks[i] in context.portfolio.positions.keys():
                    log.info("已经持有股票：[%s]" %(hold_stocks[i]))
                    current_percent = context.portfolio.positions[hold_stocks[i]].value / context.portfolio.total_value
                    if current_percent >= minpercent:
                        continue
                    tobuy = min(free_cash, buycash - context.portfolio.positions[hold_stocks[i]].value)
                else:
                    tobuy = min(buycash, free_cash)
                order_value(hold_stocks[i], tobuy)

def gogogo(context):
    get_bull_bear_signal_minute()
    if g.isbull:
        log.info("当前市场判断为：大盘牛市")
    else:
        log.info("当前市场判断为：大盘熊市")
    if g.enable_smallcap_control:
        get_small_bull_bear_signal_minute()
        if g.is_small_bull:
            log.info("小盘市场判断为：牛市")
        else:
            log.info("小盘市场判断为：熊市")
    
    # ================== 止损模块 ==================
    # 初始化连续亏损计数器（基于买入成本）
    if not hasattr(g, 'consecutive_loss_count'):
        g.consecutive_loss_count = {}
    
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.total_amount == 0:
            continue
        cost = pos.avg_cost
        if cost is None or cost == 0:
            continue
        
        # 获取当前价格（用于亏损比例判断）
        current_data = get_current_data()
        current_price = current_data[stock].day_open
        if isnan(current_price):
            # 如果无法获取开盘价，用get_close_price获取最新价
            current_price = get_close_price(stock, 1, '1m')
        if current_price is None or isnan(current_price):
            continue
        
        # 1. 固定/动态止损（亏损幅度达到阈值）
        pnl = (current_price - cost) / cost
        stop_threshold = get_dynamic_stop_loss(stock)
        if pnl <= stop_threshold:
            log.warning("触发动态止损: %s, 成本%.2f, 现价%.2f, 亏损%.2f%% (阈值%.2f%%)" 
                        % (stock, cost, current_price, pnl*100, stop_threshold*100))
            close_position(stock, reason='stop_loss')
            if stock in g.consecutive_loss_count:
                del g.consecutive_loss_count[stock]
            continue
        
        # 2. 连续亏损止损（基于买入成本：连续N个交易日收盘价低于成本价）
        if g.consecutive_loss_enable:
            # 获取昨天和前天的收盘价来计算连续亏损
            # 使用 attribute_history 获取最近2天的收盘价
            price_data = attribute_history(stock, 2, '1d', 'close', df=False, skip_paused=True)
            close_prices = price_data['close']
            
            if len(close_prices) >= 2:
                # 获取昨天的收盘价（最后一个值）
                yesterday_close = close_prices[-1]
                # 获取前天的收盘价（第一个值）
                day_before_yesterday_close = close_prices[-2] if len(close_prices) >= 2 else None
                
                # 判断昨天是否亏损（昨天收盘价 < 成本价）
                if yesterday_close < cost:
                    g.consecutive_loss_count[stock] = g.consecutive_loss_count.get(stock, 0) + 1
                else:
                    g.consecutive_loss_count[stock] = 0
                
                # 判断前天是否亏损，如果前天亏损而昨天未亏损，计数器会清零
                # 如果需要检查前天的亏损状态，可以在这里添加逻辑
                
                if g.consecutive_loss_count[stock] >= g.consecutive_loss_days:
                    log.warning("触发连续亏损止损: %s, 已连续%d个交易日收盘价低于成本价(%.2f), 昨日收盘价%.2f" 
                                % (stock, g.consecutive_loss_count[stock], cost, yesterday_close))
                    close_position(stock, reason='stop_loss')
                    if stock in g.consecutive_loss_count:
                        del g.consecutive_loss_count[stock]
                    continue
            else:
                # 数据不足，重置计数器
                g.consecutive_loss_count[stock] = 0
    # ================== 止损模块结束 ==================
    
    g.current_position_ratio = get_target_position_ratio()
    log.info("当前目标总仓位系数：%.2f" % g.current_position_ratio)
    
    if g.dynamic_weight_enable:
        if g.last_weight_update_date is None or (context.current_dt.date() - g.last_weight_update_date).days >= g.weights_update_freq:
            new_weights = get_dynamic_weights(context, g.chosen_stock_list)
            g.current_weights = new_weights
            g.last_weight_update_date = context.current_dt.date()
            log.info("动态权重已更新: %s" % g.current_weights)
    
    if (g.choose_time_signal and g.current_position_ratio == 0 and not g.bearposition) or len(g.chosen_stock_list) < 10:
        clear_position(context)
        g.nohold = True
    else:
        g.chosen_stock_list = get_stock_rank_m_m(context, g.chosen_stock_list)
        log.info(g.chosen_stock_list)
        my_adjust_position(context, g.chosen_stock_list)
        g.nohold = False

# ========== 生命周期函数 ==========
def before_trading_start(context):
    # 更新盈利卖出冷却期
    temp_profit = g.sold_stock_profit.copy()
    g.sold_stock_profit = {}
    for stock, days in temp_profit.items():
        remaining = days - 1
        if remaining > 0:
            g.sold_stock_profit[stock] = remaining

    # 更新止损卖出冷却期
    temp_loss = g.sold_stock_loss.copy()
    g.sold_stock_loss = {}
    for stock, days in temp_loss.items():
        remaining = days - 1
        if remaining > 0:
            g.sold_stock_loss[stock] = remaining

    g.chosen_stock_list = get_stock_list(context)

def myscheduler():
    set_param()
    unschedule_all()
    run_daily(gogogo, '14:50')
    run_daily(mybuy, '14:55')

def after_code_changed(context):
    myscheduler()

def initialize(context):
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    log.set_level('history', 'error')
    myscheduler()
    g.isbull = False
    g.is_small_bull = False
    g.chosen_stock_list = []
    g.nohold = True
    # 初始化冷却期字典
    g.sold_stock_profit = {}
    g.sold_stock_loss = {}
    if not hasattr(g, 'dynamic_weight_enable'):
        g.dynamic_weight_enable = True
        g.ic_window = 60
        g.ic_horizon = 5
        g.weights_update_freq = 5
        g.last_weight_update_date = None
        g.current_weights = None
        g.fallback_weights = [5, 5, 8, 4, 10, 5, 3]

def get_blacklist():
    return []