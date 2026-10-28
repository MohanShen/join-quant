# Clone from JoinQuant
# postId: 7d57c2629921be1616ef07f41ee85793
# backtestId: b353f32baf76444916d9aa6191e571c4
# title: 小市值轮动策略 - 20年至今年化57.87%

# 克隆自聚宽文章：https://www.joinquant.com/post/46785
# 标题：分享一个自己实盘年化80%+的策略，绝对可实盘
# 作者：kobe

# 克隆自聚宽文章：https://www.joinquant.com/post/46298
# 标题：一个9年18倍的策略
# 作者：水封

#导入函数库
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time


#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0.0))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    #初始化全局变量
    g.no_trading_today_signal = False #是否清仓信号
    g.stock_adjustment_day = False #是否调仓日
    g.stock_num = 2 #最大持股数
    g.hold_list = [] #当前持仓的全部股票    
    
    g.yesterday_HL_list = [] #记录持仓中昨日涨停的股票
    g.yesterday_LL_list = [] #记录持仓中昨日跌停的股票
    g.target_list = []  #目标股票
    g.not_buy_again = [] #不再买的股票
    g.limit_days = 6 #不再买入的时间段天数
    g.history_hold_list = [] #过去一段时间内持仓过的股票

    #每天准备昨天脏跌停的股票
    run_daily(prepare_highlowstock_list, '9:05')
    #每天补充仓位没满的票
    run_daily(restock_stock, '9:30')
    #周期性调整股票
    #准备要调整的股票
    run_weekly(prepare_adjustment_list, 1, '09:10')
    #发消息，9:15～9:25可以挂单买入
    run_weekly(stock_adjustment_msg, 1, '09:10')
    #调整flag，避免和restock_stock 冲突
    run_weekly(stock_adjustment_flag, 1, '09:00')
    #调仓
    run_weekly(stock_adjustment, 1, '09:30')

    #每天检查是否在清仓周期
    run_daily(check_period, '9:00')
    
    #昨天涨停票调整
    run_daily(highlimit_adjustment, time='14:00')
    #昨天跌停票调整
    run_daily(lowlimit_adjustment, time='14:00')
    #若在不持仓周期内，清空股票
    run_daily(close_account, '14:30')


#每天准备昨天脏跌停以及近期持有过的股票
def prepare_highlowstock_list(context):
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
        df_low = df[df['close'] == df['low_limit']]
        g.yesterday_LL_list = list(df_low.code)
    else:
        g.yesterday_HL_list = []
        g.yesterday_LL_list = []

    #获取最近一段时间持有过的股票列表
    g.history_hold_list.append(g.hold_list)
    if len(g.history_hold_list) >= g.limit_days:
        g.history_hold_list = g.history_hold_list[-g.limit_days:]
    temp_set = set()
    for hold_list in g.history_hold_list:
        for stock in hold_list:
            temp_set.add(stock)
    g.not_buy_again_list = list(temp_set)
    #print(g.not_buy_again_list)

#标记是否调仓日
def stock_adjustment_flag(context):
    g.stock_adjustment_day=True
    
#定期调仓
def stock_adjustment(context):
    if g.no_trading_today_signal == True:
        return
    g.not_buy_again = []
    #截取不超过最大持仓数的股票量
    target_list = g.target_list[:min(g.stock_num, len(g.target_list))]
    #调仓卖出
    for stock in g.hold_list:
        if (stock not in target_list) and (stock not in g.yesterday_HL_list):
            log.info("卖出[%s]" % (stock))
            position = context.portfolio.positions[stock]
            close_position(position)
        else:
            log.info("已持有[%s]" % (stock))
    #调仓买入
    position_count = len(context.portfolio.positions)
    target_num = len(target_list)
    if target_num > position_count:
        value = context.portfolio.cash / (target_num - position_count)
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
                if open_position(stock, value):
                    g.not_buy_again.append(stock) #持仓清单，后续不希望再买入
                    if len(context.portfolio.positions) == target_num:
                        break
                    
    g.stock_adjustment_day=False

#持仓不足则补充
def restock_stock(context):
    if g.stock_adjustment_day == True:
        return
    if g.no_trading_today_signal == True:
        return
    position_count = len(context.portfolio.positions)
    if position_count >= g.stock_num:
        return
    #准备股票
    #prepare_adjustment_list(context)
    target_list = filter_not_buy_again(g.target_list)
    target_list = target_list[:min(g.stock_num, len(target_list))]
    #补充买入
    target_num = len(target_list)
    if target_num > position_count:
        value = context.portfolio.cash / (target_num - position_count)
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
                if open_position(stock, value):
                    g.not_buy_again.append(stock) #持仓清单，后续不希望再买入
                    if len(context.portfolio.positions) == target_num:
                        break

#定期调仓发消息
def stock_adjustment_msg(context):
    if g.no_trading_today_signal == True:
        return
    #截取不超过最大持仓数的股票量
    target_list = g.target_list[:min(g.stock_num, len(g.target_list))]
    current_data = get_current_data()
    strMsg = "卖出:<br/>"
    msgFlag=False
    cash=context.portfolio.available_cash
    position_count= len(context.portfolio.positions)
    #调仓卖出
    for stock in g.hold_list:
        if (stock not in target_list) and (stock not in g.yesterday_HL_list):
            strMsg = strMsg + stock +"," +current_data[stock].name+";<br/>"
            cash=cash+context.portfolio.long_positions[stock].value
            msgFlag=True
            position_count=position_count-1
        else:
            log.info("已持有[%s]" % (stock))
    #调仓买入
    strMsg=strMsg+"买入:<br/>"
    target_num = len(target_list)
    if target_num > position_count:
        value = cash / (target_num - position_count)
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
                msgFlag=True
                position_count=position_count+1
                strMsg = strMsg + stock +"," +current_data[stock].name+","+str(round(value,0)) +";<br/>"
                if position_count == target_num:
                    break
    if msgFlag== True:
        print(strMsg)
        send_message(strMsg,channel='weixin')

#调整昨日跌停股票
def lowlimit_adjustment(context):
    if g.yesterday_LL_list != []:
        for stock in g.yesterday_LL_list:
            position = context.portfolio.positions[stock]
            log.info("[%s]跌停打开，卖出" % (stock))
            g.not_buy_again.append(stock) #持仓清单，后续不希望再买入
            close_position(position)
        #如果今天能补则补充股票
        restock_stock(context)
   
    

#调整昨日涨停股票
def highlimit_adjustment(context):
    if g.no_trading_today_signal == True:
        return
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0,0] <    current_data.iloc[0,1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                g.not_buy_again.append(stock) #持仓清单，后续不希望再买入
                close_position(position)
            else:
                log.info("[%s]涨停，继续持有" % (stock))
        #补充股票
        restock_stock(context)

#每天检查是否在清仓周期
def check_period(context):
    #判断今天是否为空仓周期
    g.no_trading_today_signal = today_is_between(context)
    
#判断今天是否为账户资金再平衡的日期
def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    if (('04-05' <= today) and (today <= '04-30')) :
        return True
    elif (('01-04' <= today) and (today <= '01-31')) :
        return True
    else:
        return False


#获取要调整的股票列表
def prepare_adjustment_list(context):
    if g.no_trading_today_signal == True:
        return
    #根据趋势获取股票
    t_list=prepare_adjustment_list_bytrend(context)
    
    g.target_list = t_list
    


#根据趋势获取股票
def prepare_adjustment_list_bytrend(context):  
    
    yesterday = context.previous_date
    final_list = []
    MKT_index = '399101.XSHE'
    initial_list = get_index_stocks(MKT_index)
    #initial_list = get_all_securities().index.tolist()
    #initial_list = list(filter(lambda x: x.startswith('002') or x.startswith('003'), initial_list))
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    q = query(valuation.code,valuation.circulating_market_cap).filter(valuation.code.in_(initial_list)).order_by(valuation.circulating_market_cap.asc())
    df_fun = get_fundamentals(q)
    df_fun = df_fun[:50]
    initial_list = list(df_fun.code)
    
    initial_list = filter_paused_stock(initial_list)
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    
    
    q = query(valuation.code,valuation.circulating_market_cap).filter(valuation.code.in_(initial_list)).order_by(valuation.circulating_market_cap.asc())
    df_fun = get_fundamentals(q)
    df_fun = df_fun[:5]
    
    final_list  = list(df_fun.code)
    stat_date = yesterday
    stock_list = final_list
    df_price = get_price(stock_list, 
                        end_date=stat_date,
                        count=3, 
                        frequency='1d', 
                        fields=['close','volume'], 
                        skip_paused=False, 
                        fq='pre', 
                        panel=False, 
                        fill_paused=True)
    df_price = df_price.drop(['time'], axis=1)
    #近3天的平均收盘股价
    df_price_close = df_price.groupby(by='code')['close'].mean().to_frame()
     #近3天的平均交易股票数量
    df_price_volume = df_price.groupby(by='code')['volume'].mean().to_frame()
   
    df_price_7days = get_price(stock_list, 
                                    end_date=stat_date,
                                    count=7, 
                                    frequency='1d', 
                                    fields=['low','volume'], 
                                    skip_paused=False, 
                                    fq='pre', 
                                    panel=False, 
                                    fill_paused=True)
    df_price_7days = df_price_7days.drop(['time'], axis=1)
    #近7天的最低股价
    df_price_7days_close = df_price_7days.groupby(by='code')['low'].min().to_frame()
    #近7天的平均交易股票数量
    df_price_7days_volume = df_price_7days.groupby(by='code')['volume'].mean().to_frame()
    df_price_7days_close.columns=['after7daysclose']
    df_price_7days_volume.columns=['after7daysvolume']
    
    df_price_50days = get_price(stock_list, 
                                    end_date=stat_date,
                                    count=50, 
                                    frequency='1d', 
                                    fields=['low','volume'], 
                                    skip_paused=False, 
                                    fq='pre', 
                                    panel=False, 
                                    fill_paused=True)
    df_price_50days = df_price_50days.drop(['time'], axis=1)
    #近50天的最低股价
    df_price_50days_close = df_price_50days.groupby(by='code')['low'].min().to_frame()
    #近50天的平均交易股票数量
    df_price_50days_volume = df_price_50days.groupby(by='code')['volume'].mean().to_frame()
    df_price_50days_close.columns=['after50daysclose']
    df_price_50days_volume.columns=['after50daysvolume']
    
    df_price_100days = get_price(stock_list, 
                                    end_date=stat_date,
                                    count=100, 
                                    frequency='1d', 
                                    fields=['low','volume'], 
                                    skip_paused=False, 
                                    fq='pre', 
                                    panel=False, 
                                    fill_paused=True)
    df_price_100days = df_price_100days.drop(['time'], axis=1)
    #近100天的最低股价
    df_price_100days_close = df_price_100days.groupby(by='code')['low'].min().to_frame()
    #近100天的平均交易股票数量
    df_price_100days_volume = df_price_100days.groupby(by='code')['volume'].mean().to_frame()
    df_price_100days_close.columns=['after100daysclose']
    df_price_100days_volume.columns=['after100daysvolume']
    
    df_y = pd.merge(df_price_close, df_price_volume, on=['code'])
    df_y = pd.merge(df_y, df_price_7days_close, on=['code'])
    df_y = pd.merge(df_y, df_price_7days_volume, on=['code'])
    df_y = pd.merge(df_y, df_price_50days_close, on=['code'])
    df_y = pd.merge(df_y, df_price_50days_volume, on=['code'])
    df_y = pd.merge(df_y, df_price_100days_close, on=['code'])
    df_y = pd.merge(df_y, df_price_100days_volume, on=['code'])
    df_y = pd.merge(df_y, df_fun, on=['code'])
    
    df_y['price_rate7'] = df_y['close'] / df_y['after7daysclose']
    df_y['volume_rate7'] =  df_y['after7daysvolume'] / df_y['volume']
    df_y['price_rate50'] = df_y['close'] / df_y['after50daysclose']
    df_y['volume_rate50'] =  df_y['after50daysvolume'] / df_y['volume']
    df_y['price_rate100'] = df_y['close'] / df_y['after100daysclose']
    df_y['volume_rate100'] =  df_y['after100daysvolume'] / df_y['volume']
    
    df_y['rate'] = df_y['price_rate100']*4 + df_y['price_rate50']*8 + df_y['price_rate7']*8 + df_y['volume_rate50']*3 + df_y['circulating_market_cap']/10*1
    df_y = df_y.sort_values(by = 'rate',axis = 0,ascending = True)
    df_y = df_y.drop(['close','volume','after50daysvolume','after50daysclose'], axis=1)
    #显示所有列
    pd.set_option('display.max_columns', None)
    
    final_list = list(df_y.code)
    
    final_list = filter_paused_stock(final_list)
    final_list = filter_limitup_stock(context, final_list)
    final_list = filter_limitdown_stock(context, final_list)

    return final_list
    


    





#过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

#过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]

#过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list

#过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] <    current_data[stock].high_limit]

#过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]
						
#过滤次新股
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date <    datetime.timedelta(days=375)]


#删除本周一买入的股票
def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]
    

#交易模块-自定义下单
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)


#交易模块-开仓
def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False

#交易模块-平仓
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False

#清仓后次日资金可转
def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                close_position(position)
                log.info("卖出[%s]" % (stock))
                



