# Clone from JoinQuant
# postId: 05b539a34b3d96a496f8fa235afdefb5
# backtestId: 4f560ae6860341d316b8f63f194f826d
# title: 低回撤，稳定盈利，小盘股三因子加上RSRS择时

# 克隆自聚宽文章：https://www.joinquant.com/post/43593
# 标题：分享一个收益高回撤低的小盘策略~
# 作者：Sissie

#导入函数库
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from utils import *


#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('399303.XSHE')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    #初始化全局变量
    g.stock_num = 10
    g.hold_list = [] #当前持仓的全部股票    
    g.yesterday_HL_list = [] #记录持仓中昨日涨停的股票
    g.factor_list = [
        'liquidity', #风格因子 流动性因子
        'value_change_profit_ttm', #基础科目及衍生类因子 价值变动净收益TTM
        'roa_ttm' #质量类因子 资产回报率TTM
        ]
    g.sign = '大盘国'
    g.run_type = context.run_params.type
    g.momentum_day = 20 #最新动量参考最近momentum_day的
    g.ref_stock = '000300.XSHG' #用ref_stock做择时计算的基础数据
    g.N = 13 # 计算最新斜率slope，拟合度r2参考最近N天
    g.M = 300 # 计算最新标准分zscore，rsrs_score参考最近M天
    g.score_threshold = 0.5 # rsrs标准分指标阈值
    g.slope_series = initial_slope_series() # 除去回测第一天的slope，避免运行时重复加入
    g.signal = ''
    # 设置交易运行时间
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    run_weekly(open_check, weekday=1, time='9:10', reference_security='000300.XSHG')
    run_weekly(weekly_adjustment, weekday=1, time='9:30', reference_security='000300.XSHG')
    run_daily(check_limit_up, time='14:00', reference_security='000300.XSHG') #检查持仓中的涨停股是否需要卖出
    run_daily(print_position_info, time='15:10', reference_security='000300.XSHG')

# 购买前检查择时
def open_check(context):
    g.signal = get_timing_signal(context, g.ref_stock)
    print('今日{},择时信号:{}'.format(context.current_dt, g.signal))




#1-1 准备股票池
def prepare_stock_list(context):
    #获取已持有列表
    g.hold_list= []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    #获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []

#1-2 选股模块
def get_stock_list(context):
    yesterday = context.previous_date
    initial_list = get_all_securities().index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    #MS
    factor_values = get_factor_values(initial_list, [
        g.factor_list[0],
        g.factor_list[1],
        g.factor_list[2],
        ], end_date=yesterday, count=1)
    df = pd.DataFrame(index=initial_list, columns=factor_values.keys())
    df[g.factor_list[0]] = list(factor_values[g.factor_list[0]].T.iloc[:,0])
    df[g.factor_list[1]] = list(factor_values[g.factor_list[1]].T.iloc[:,0])
    df[g.factor_list[2]] = list(factor_values[g.factor_list[2]].T.iloc[:,0])
    df = df.dropna()
    coef_list = [
        -0.04963427582597701,
        6.451436607157746e-13,
        -0.04698060391789672
        ]
    df['total_score'] = coef_list[0]*df[g.factor_list[0]] + coef_list[1]*df[g.factor_list[1]] + coef_list[2]*df[g.factor_list[2]]
    df = df.sort_values(by=['total_score'], ascending=False) #分数越高即预测未来收益越高，排序默认降序
    complex_factor_list = list(df.index)[:int(0.1*len(list(df.index)))]
    q = query(valuation.code,valuation.circulating_market_cap,indicator.eps).filter(valuation.code.in_(complex_factor_list)).order_by(valuation.circulating_market_cap.asc())
    df = get_fundamentals(q)
    df = df[df['eps']>0]
    final_list  = list(df.code)
    return final_list

#1-3 整体调整持仓
def weekly_adjustment(context):
    # 择时卖出所有股票并不买入
    if g.signal == 'SELL':
        for stock in context.portfolio.positions:
            position = context.portfolio.positions[stock]
            close_position(position)
        return
    
    target_list = get_stock_list(context)
    target_list = filter_paused_stock(target_list)
    target_list = filter_limitup_stock(context, target_list)
    target_list = filter_limitdown_stock(context, target_list)
    #截取不超过最大持仓数的股票量
    target_list = target_list[:min(g.stock_num, len(target_list))]
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
                    if len(context.portfolio.positions) == target_num:
                        break


#1-4 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0,0] < current_data.iloc[0,1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("[%s]涨停，继续持有" % (stock))



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
			or last_prices[stock][-1] < current_data[stock].high_limit]

#2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	current_data = get_current_data()
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] > current_data[stock].low_limit]

#2-6 过滤次新股
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=375)]



#3-1 交易模块-自定义下单
def order_target_value_(security, value):
	if value == 0:
		log.debug("Selling out %s" % (security))
	else:
		log.debug("Order %s to value %f" % (security, value))
	return order_target_value(security, value)

#3-2 交易模块-开仓
def open_position(security, value):
	order = order_target_value_(security, value)
	if order != None and order.filled > 0:
	    send_order_to_task(security, order.amount)
	    return True
	return False

#3-3 交易模块-平仓
def close_position(position):
	security = position.security
	order = order_target_value_(security, 0)  # 可能会因停牌失败
	if order != None:
	    send_order_to_task(security, 0)
	    if order.status == OrderStatus.held and order.filled == order.amount:
	        return True
	return False

def send_order_to_task(code, amount):
    if g.run_type == 'sim_trade':
        send_gm_joinquant(g.sign, code, amount)

## 线性回归：复现statsmodels的get_OLS函数
def get_ols(x, y):
    slope, intercept = np.polyfit(x, y, 1)
    r2 = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
    return (intercept, slope, r2)

## 因子标准化
def get_zscore(slope_series):
    mean = np.mean(slope_series)
    std = np.std(slope_series)
    return (slope_series[-1] - mean) / std

# 只看RSRS因子值作为买入、持有和清仓依据，前版本还加入了移动均线的上行作为条件
def get_timing_signal(context,stock):
    # if is_bear_market_by_ma():
    #     return 'SELL'
    # else:
    #     return 'BUY'
        
    data = attribute_history(g.ref_stock, 18, '1d', ['high', 'low','volume'])
    intercept, slope, r2 = get_ols(data.low, data.high)
    g.slope_series.append(slope)
    rsrs_score = get_zscore(g.slope_series[-g.M:]) * r2
    log.info('今日择时', context.current_dt, intercept, slope, r2, rsrs_score)

    # log.info('rsrs_score {:.3f}'.format(rsrs_score))
    if (rsrs_score > g.score_threshold) : return "BUY"
    elif (rsrs_score < -g.score_threshold): return "SELL"
    else: return "KEEP"

#### 择时过程  ----->--------------------------------------------
def initial_slope_series():
    data = attribute_history(g.ref_stock, g.N + g.M, '1d', ['high', 'low'])
    return [get_ols(data.low[i:i+g.N], data.high[i:i+g.N])[1] for i in range(g.M)]

#4-1 打印每日持仓信息
def print_position_info(context):
    #打印当天成交记录
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：'+str(_trade))
    #打印账户信息
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