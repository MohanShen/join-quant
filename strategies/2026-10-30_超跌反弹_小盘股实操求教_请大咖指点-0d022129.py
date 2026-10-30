# Clone from JoinQuant
# postId: 0d022129841ab182fb97c45ffa6eaf8b
# backtestId: db56b7800517b94ff4cb22a222d42868
# title: 超跌反弹，小盘股实操求教，请大咖指点！

"""
策略逻辑，
1，周二1030(最OK)盘前选股(市值升序),7>10=5只
2，有4月空仓(加1月空仓)
3，2点有破板卖出
4，10点有止损卖出(中小指日跌幅6点，单票12点止损,最佳)

"""
#原收益2189%，夏普4，最大回撤19%，策略波动0.29
#1.1修改失败，改成春节前30天4月空仓，1853%，夏普3.9，回撤19%，波动0.28
#银棍修改g.no_trading_today_signal == False and g.defense_signal == False三段
#1.2修改,斜率高位,银行股上涨，收益1431.13% 回撤18.52%，夏普3.5,策略波动率0.282,调整失败
#1.3修改，高位银行股防御规则收益1739.27% ，夏普4，最大回撤13%，策略波动率0.26,原策略：2189% / 19% ≈ 115.21修改后：1739.27% / 13% ≈ 133.79
#1.4修改，过滤最低点上来5%的股票

#导入函数库
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time
#import datetime
#初始化函数 
def initialize(context):
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 设定基准
    set_benchmark('000001.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(3/10000))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5/10000, close_commission=2.5/10000, close_today_commission=0, min_commission=5),type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    #初始化全局变量 bool
    g.no_trading_today_signal = False  # 是否为可交易日
    g.pass_april = True  # 是否四月空仓
    g.run_stoploss = True  # 是否进行止损
    #全局变量list
    g.hold_list = [] #当前持仓的全部股票    
    g.yesterday_HL_list = [] #记录持仓中昨日涨停的股票
    g.target_list = []
    g.not_buy_again = []
    #全局变量float/strs
    g.stock_num = 7
    #g.m_days = 7 #取值参考天数,未生效
    g.up_price = 100  # 设置股票单价 
    g.reason_to_sell = ''
    g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
    g.stoploss_limit = 0.88  # 止损线
    g.stoploss_market = 0.94  # 市场趋势止损参数
    
    g.HV_control = False #新增，Ture是日频判断是否放量，False则不然
    g.HV_duration = 120 #HV_control用，周期可以是240-120-60，默认比例是0.9
    g.HV_ratio = 0.9    #HV_control用
    
    g.industries=["银行I"]#高位防御板块
    g.defense_signal =False 
    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')
    run_weekly(weekly_adjustment,2,'10:30')#周调仓
    run_daily(sell_stocks, time='10:00') # 止损函数
    run_daily(trade_afternoon, time='14:30') #检查持仓中的连板股及放量卖出
    run_daily(close_account, '14:50')#日历空仓或防御信号空仓
    run_weekly(print_position_info, 5, time='15:10')

#1-1 准备股票池
def prepare_stock_list(context):
    #获取已持有列表
    g.hold_list= []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    #获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    #判断今天是否为账户资金再平衡的日期
    g.no_trading_today_signal = today_is_between(context)
    check_defense_trigger(context)

#1-2 选股模块
def get_stock_list(context):
    final_list = []
    MKT_index = '399101.XSHE'
    initial_list = get_index_stocks(MKT_index)
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    #测试过滤60日最低点上来5%的股票
    initial_list = filter_lowest_point(context, initial_list)
    
    q = query(valuation.code,indicator.eps).filter(valuation.code.in_(initial_list)).order_by(valuation.market_cap.asc())
    df = get_fundamentals(q)
    stock_list = list(df.code)
    stock_list = stock_list[:100]
    final_list = stock_list[:2*g.stock_num]
    log.info('今日前10:%s' % final_list)
    
    """
    initial_list = list(df_fun.code)
    initial_list = filter_paused_stock(initial_list)
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    #print('initial_list中含有{}个元素'.format(len(initial_list)))
    q = query(valuation.code,valuation.market_cap).filter(valuation.code.in_(initial_list)).order_by(valuation.market_cap.asc())
    df_fun = get_fundamentals(q)
    
    df_fun = df_fun[:50]
    final_list  = list(df_fun.code)
    """
    return final_list


#1-3 整体调整持仓
def weekly_adjustment(context):
    log.info(f"★ ★ 【进入 weekly_adjustment 函数，当前日期: {context.current_dt.date()}, 空仓 {g.no_trading_today_signal}")
    if g.no_trading_today_signal == False and g.defense_signal == False:
        #获取应买入列表 
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        """
        target_list = filter_not_buy_again(g.target_list)
        target_list = filter_paused_stock(target_list)
        target_list = filter_limitup_stock(context, target_list)
        target_list = filter_limitdown_stock(context, target_list)
        target_list = filter_highprice_stock(context, target_list)
        """
        target_list = g.target_list[:g.stock_num]
        log.info(str(target_list))
        
        #print(day_of_week)
        #print(type(day_of_week))
        #调仓卖出
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("已持有[%s]" % (stock))
        #调仓买入
        buy_security(context,target_list)
        #记录已买入股票
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.not_buy_again.append(stock)

#1-4 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0,0] <    current_data.iloc[0,1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
                g.reason_to_sell = 'limitup'
            else:
                log.info("[%s]涨停，继续持有" % (stock))
 
#1-5 如果昨天有股票卖出或者买入失败，剩余的金额今天早上买入
def check_remain_amount(context):
    log.info(f"进入 check_remain_amount 函数，当前日期: {context.current_dt.date()}, g.reason_to_sell: {g.reason_to_sell}, 持仓数量: {len(g.hold_list)}, g.stock_num: {g.stock_num}")
    if g.reason_to_sell is 'limitup': #判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
        g.hold_list= []
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.hold_list.append(stock)
        if len(g.hold_list) < g.stock_num:
            target_list = g.target_list
            #剔除本周一曾买入的股票，不再买入
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            log.info('有余额可用'+str(round((context.portfolio.cash),2))+'元。'+ str(target_list))
            buy_security(context,target_list)
        g.reason_to_sell = ''
    else:
        log.info('虽然有余额可用，但是为止损后余额，下周再交易')
        g.reason_to_sell = ''

#1-6 下午检查交易
def trade_afternoon(context):
    if g.no_trading_today_signal == False and g.defense_signal == False:
        check_limit_up(context)
        if g.HV_control == True:
            check_high_volume(context)
        check_remain_amount(context)
        
#1-7 止盈止损
def sell_stocks(context):
    if g.run_stoploss == True:
        if g.stoploss_strategy == 1:
            for stock in context.portfolio.positions.keys():
                # 股票盈利大于等于100%则卖出
                if context.portfolio.positions[stock].price >= context.portfolio.positions[stock].avg_cost * 2:
                    order_target_value(stock, 0)
                    log.debug("收益100%止盈,卖出{}".format(stock))
                # 止损
                elif context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_limit:
                    order_target_value(stock, 0)
                    log.debug("收益止损,卖出{}".format(stock))
                    g.reason_to_sell = 'stoploss'
        elif g.stoploss_strategy == 2:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            #down_ratio = (stock_df['close'] / stock_df['open'] < 1).sum() / len(stock_df)
            #down_ratio = abs((stock_df['close'] / stock_df['open'] - 1).mean())
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
        elif g.stoploss_strategy == 3:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            #down_ratio = abs((stock_df['close'] / stock_df['open'] - 1).mean())
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
            else:
                for stock in context.portfolio.positions.keys():
                    if context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_limit:
                        order_target_value(stock, 0)
                        log.debug("收益止损,卖出{}".format(stock))
                        g.reason_to_sell = 'stoploss'

# 3-2 调整放量股票
def check_high_volume(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        if context.portfolio.positions[stock].closeable_amount ==0:
            continue
        df_volume = get_bars(stock,count=g.HV_duration,unit='1d',fields=['volume'],include_now=True, df=True)
        if df_volume['volume'].values[-1] > g.HV_ratio*df_volume['volume'].values.max():
            log.info("[%s]天量，卖出" % stock)
            position = context.portfolio.positions[stock]
            close_position(position)
#2-1 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

#2-2 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]

#2-3 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list

#2-4 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] <    current_data[stock].high_limit]

#2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]

#2-6 过滤次新股
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date <  datetime.timedelta(days=375)]

#2-6.5 过滤股价
def filter_highprice_stock(context,stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] <= g.up_price]

#2-7 删除本周一买入的股票
def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]
 
#3-1 交易模块-自定义下单
def order_target_value_(security, value):
    if value == 0:
        pass
        #log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)

#3-2 交易模块-开仓
def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False

#3-3 交易模块-平仓
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False

#3-4 买入模块
def buy_security(context,target_list):
    #调仓买入
    position_count = len(context.portfolio.positions)
    target_num = len(target_list)
    if target_num > position_count:
        value = context.portfolio.cash / (target_num - position_count)
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
            #if stock not in context.portfolio.positions:
                if open_position(stock, value):
                    log.info("买入[%s]（%s元）" % (stock,value))
                    g.not_buy_again.append(stock) #持仓清单，后续不希望再买入
                    if len(context.portfolio.positions) == target_num:
                        break


#4-1 判断今天是否为四月
def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    if g.pass_april is True:
        if (('04-01' <= today) and (today <= '04-30')) or (('01-01' <= today) and (today <= '01-31')):
            return True
        else:
           return False
    else:
        return False


#4-2 清仓后次日资金可转
def close_account(context):
    if g.no_trading_today_signal == True or g.defense_signal == True:
        if len(g.hold_list) != 0:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                close_position(position)
                log.info("卖出[%s]" % (stock))

#5-1 TOP宽度板块
def get_market_breadth(context,ma_days):
    required_days=ma_days+35
    end_date =context.current_dt      
    trade_days = get_trade_days(end_date=end_date, count=required_days)
    # 获取行业分类数据
    sw_l1 = get_industries('sw_l1', date=end_date)
    industry_stocks = {}
    for idx, row in sw_l1.iterrows():
        ind_stocks = get_industry_stocks(idx, date=end_date)
        industry_stocks[row['name']] = ind_stocks  # 存储行业对应的股票列表
    # 获取所有股票
    all_stocks = []
    for stocks in industry_stocks.values():
        all_stocks.extend(stocks)
    all_stocks = list(set(all_stocks))  # 去重
    # 获取价格数据（包含所有股票的收盘价）
    data =get_bars(all_stocks,end_dt=end_date,count=required_days,unit='1d',fields=['close'],include_now=True, df=True)
    price_data=data.reset_index()
    price_data = price_data.pivot(index='level_1', columns='level_0', values='close')  # 转换为时间序列格式
    ma = price_data.rolling(window=ma_days).mean()  # 计算移动平均
    above_ma = price_data > ma  # 标记股价是否在均线上方
    # 按行业计算均线分数
    industry_scores = pd.DataFrame(index=price_data.index)  # 初始化行业得分表
    
    for industry, stocks in industry_stocks.items():
        # 获取行业内有效股票（同时存在于价格数据中的股票）
        valid_stocks = list(set(above_ma.columns) & set(stocks))
        if valid_stocks:
            # 计算该行业在均线因子上的得分（符合条件的股票比例）
            industry_scores[industry] = 100 * above_ma[valid_stocks].sum(axis=1) / len(valid_stocks)
    transposed_data = industry_scores[-3:].mean()#近3天
    sorted_data = transposed_data.sort_values( ascending=False)
    return sorted_data
    
# #5-2 斜率趋势高位且TOP宽度板块中有银行    
# def check_defense_trigger(context):
#     """检查防御触发条件"""
#     if g.defense_signal:
#         # 只判断行业强度
#         sorted_data = get_market_breadth(context, 10)
#         defense_in_top = any([ind in sorted_data.index[:5] for ind in g.industries])  # 防御板块在前3
#         g.defense_signal= defense_in_top
#         log.info(f"防御: {g.defense_signal} top宽度:{sorted_data.index[:5]}")
#     else:    
#         # 1. 获取趋势分位
#         conf = 276
#         ma_window=20
#         slope_window=5
#         # 获取足够的历史数据
#         data = get_bars('399101.XSHE', end_dt=context.current_dt, unit='1d', count=conf,fields=['close'], include_now=True, df=True)
#         # 计算主均线
#         ma = data['close'].rolling(ma_window).mean().dropna()
#         # 计算每日斜率（百分比变化，当前20均线对比5天前的20均线,最后得出252（一年）每日的斜率）
#         slopes = (ma.diff(slope_window) / ma.shift(slope_window)) * 100
#         slopes = slopes[np.isfinite(slopes)]
#         slopes_series = pd.Series(slopes.values, index=slopes.index)
#         window_size = 5
#         if len(slopes_series) >= window_size:
#             # 计算 slopes_series.iloc[-5:] 中每个元素在 slopes_series 中的分位数
#             last_five_percentiles = []
#             for value in slopes_series.iloc[-window_size:]:
#                 percentile = (slopes_series <= value).mean()
#                 last_five_percentiles.append(percentile)
#             slopes_percentile = np.mean(last_five_percentiles)
#         #高位防御判断
#         if slopes_percentile>=0.8:
#           # 1. 获取行业强度排名
#             sorted_data = get_market_breadth(context,10)
#             # log.info(sorted_data)
#             # 2. 判断防御板块是否在前5
#             defense_in_top = any([ind in sorted_data.index[:5] for ind in g.industries])
#             # 3. 判断防御板块是否高于市场平均分，避免全市场共涨误判
#             avg_score = np.mean(sorted_data.values)
#             defense_score = sorted_data[[ind in g.industries for ind in sorted_data.index]].max()
#             relative_strength = (defense_score - avg_score) / avg_score
#             above_average=True if relative_strength > 0.1 else False # 相对强度超过10%
#         else:
#             defense_in_top=False
#             above_average=False
#         is_defense=defense_in_top and slopes_percentile>=0.8 and above_average
#         g.defense_signal=is_defense
#         log.info(f"防御: {g.defense_signal} 高位:{round(slopes_percentile,2)} 相对强度:{above_average}")


#5-2 相对高位且TOP宽度板块中有银行    
def check_defense_trigger(context):
    """改进后的防御条件检查"""
    def calculate_trend_indicators(context, index_symbol='399101.XSHE'):
        """计算趋势指标:接近近期高点"""
        # 参数设置
        high_lookback = 60   # 近期高点观察窗口
        high_proximity = 0.95       # 接近高点的阈值（95%）
        # 获取历史数据
        data = get_bars(index_symbol, end_dt=context.current_dt, 
                      count=high_lookback,
                      unit='1d', fields=['close','high'], include_now=True, df=True)
        current_price = data['close'].iloc[-1]
        # 计算近期高点接近度
        max_high = data['high'][-high_lookback:].max()
        is_high = True if current_price >= (max_high * high_proximity) else False 
        return is_high
        
    if g.defense_signal:#如果已经进入防御板块，只要看银行有没有在前三
            # 行业强度判断
        sorted_data = get_market_breadth(context, 10)
        defense_in_top = any([ind in sorted_data.index[:3] for ind in g.industries])  # 防御板块在前3
        g.defense_signal= defense_in_top
        log.info(f"防御: {defense_in_top} top宽度:{sorted_data.index[:3]}")
        
    else:
        # 趋势高位判断条件
        is_high = calculate_trend_indicators(context)
        if is_high:
            # 行业强度判断
            sorted_data = get_market_breadth(context, 10)
            defense_in_top = any(ind in sorted_data.index[:3] for ind in g.industries)  # 防御板块在前3
            # 相对强度判断
            avg_score = sorted_data.mean()
            defense_score = sorted_data[[ind in g.industries for ind in sorted_data.index]].max()
            relative_strength = (defense_score - avg_score) / avg_score
            above_average = relative_strength > 0.1  # 相对强度超过10%
            # 综合判断
            is_defense = is_high and defense_in_top and above_average
            log.info(f"防御: {is_defense} 高位:{is_high} top宽度:{sorted_data.index[:3]} 相对强度:{above_average}")
            g.defense_signal=is_defense
        else:
            g.defense_signal=False
            log.info(f"防御: {g.defense_signal} 高位:{is_high} ")
            
        
#选股条件添加


def filter_lowest_point(context, initial_list):
    """过滤最低点"""
    # 参数设置
    low_lookback = 60   # 近期低点观察窗口
    low_proximity = 1.05  # 突破最低点的阈值（105%）
    # 获取历史数据
    data = get_price(
        initial_list, end_date=context.previous_date, frequency='daily', fields=['close', 'low'], count=low_lookback, 
        panel=False,  
        fill_paused=False)
    filtered_list = []
    # 按股票代码分组
    grouped = data.groupby('code')
    # 计算每个股票的最低低点和最新收盘价
    min_lows = grouped['low'].min()
    current_prices = grouped['close'].last()
    # 筛选满足条件的股票
    filtered = current_prices >= min_lows * low_proximity
    filtered_list = filtered[filtered].index.tolist()
    return filtered_list


def print_position_info(context):
    for position in list(context.portfolio.positions.values()):
        securities=position.security
        cost=position.avg_cost
        price=position.price
        ret=100*(price/cost-1)
        value=position.value
        amount=position.total_amount    
        print('代码:{}'.format(securities))
        print('成本价:{}'.format(format(cost,'.2f')))
        print('现价:{}'.format(price))
        print('收益率:{}%'.format(format(ret,'.2f')))
        print('持仓(股):{}'.format(amount))
        print('市值:{}'.format(format(value,'.2f')))
        print('———————————————————————————————————')
    print('———————————————————————————————————————分割线————————————————————————————————————————')