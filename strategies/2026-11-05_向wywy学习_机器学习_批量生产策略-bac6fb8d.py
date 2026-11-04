# Clone from JoinQuant
# postId: bac6fb8d70e250b3ca844963f97472c6
# backtestId: acb1206bfdd3c8aa13f9f232ccca51c3
# title: 向wywy学习，机器学习，批量生产策略

# 克隆自聚宽文章：https://www.joinquant.com/post/37025
# 标题：小市值近一年，年化38%，回撤11%
# 作者：小赵团子🍡
from jqdata import *
from jqfactor import *
import datetime
import numpy as np
import pandas as pd
import json

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

# 获取前n个单位时间当时的收盘价
def get_close_price(code, n, unit='1d'):
    return attribute_history(code, n, unit, 'close', df=False)['close'][0]

# 平仓，卖出指定持仓
def close_position(code):
    order = order_target_value(code, 0) # 可能会因停牌或跌停失败
    if order != None and order.status == OrderStatus.held:
        g.sold_stock[code] = 0

# 清空卖出所有持仓
def clear_position(context):
    if context.portfolio.positions:
        log.info("==> 清仓，卖出所有股票")
        for stock in context.portfolio.positions.keys():
            close_position(stock)

def filter_stock(context, stock_list):
    current_data = get_current_data()
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    filter_list = []
    for stock in stock_list:
        # 过滤停牌、ST
        if current_data[stock].paused or 'ST' in current_data[stock].name or '*' in current_data[stock].name or '退' in current_data[stock].name or current_data[stock].is_st:
            continue
        # 过滤北交所
        if stock[0] == '8' or stock[:3] == '688':
            continue
        # 过滤次新股
        if (context.previous_date - datetime.timedelta(days=g.tradeday)) < get_security_info(stock).start_date:
            continue
        # 过滤昨天涨幅大
        if get_close_price(stock, 1) / get_close_price(stock, 2) >= (1 + g.increase1d):
            continue
        # 过滤当日涨停
        if last_prices[stock][-1] >= current_data[stock].high_limit:
            continue
        # 过滤当日跌停
        if last_prices[stock][-1] <= current_data[stock].low_limit:
            continue
        filter_list.append(stock)
    return filter_list
# 取流通市值最小的500股作为基础的股票池
def get_stock_list(context):
    yesterday = context.previous_date
    securities = get_all_securities()
    df = get_fundamentals(query(valuation.code).filter(valuation.pb_ratio.between(g.pbmin, g.pbmax)
        ).order_by(valuation.circulating_market_cap.asc()).limit(len(securities)/3)).dropna()
    stock_list = list(df['code'])
    stock_list = filter_stock(context, stock_list)[:30]
    g.securities_every_day_0 = stock_list
    print('当日初选个股：', g.securities_every_day_0)
    factor_values = get_factor_values(g.securities_every_day_0, [
        g.factor_list[0],
        g.factor_list[1],
        g.factor_list[2],
        g.factor_list[3],
        ], end_date=yesterday, count=1)
    df = pd.DataFrame(index=g.securities_every_day_0, columns=factor_values.keys())
    df[g.factor_list[0]] = list(factor_values[g.factor_list[0]].T.iloc[:,0])
    df[g.factor_list[1]] = list(factor_values[g.factor_list[1]].T.iloc[:,0])
    df[g.factor_list[2]] = list(factor_values[g.factor_list[2]].T.iloc[:,0])
    df[g.factor_list[3]] = list(factor_values[g.factor_list[3]].T.iloc[:,0])
    df = df.dropna()
    df['total_score'] = g.coef_list[0]*df[g.factor_list[0]] + g.coef_list[1]*df[g.factor_list[1]] + g.coef_list[2]*df[g.factor_list[2]] + g.coef_list[3]*df[g.factor_list[3]]
    df = df.sort_values(by=['total_score'], ascending=False) #分数越高即预测未来收益越高，排序默认降序
    g.securities_every_day_1 = list(df.index[:10])
    print('因子计算后：', g.securities_every_day_1)

def weekly_adjustment(context):
    get_stock_list(context)
    #获取应买入列表 
    target_list = g.securities_every_day_1
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
    
def initialize(context):
    #使用真实价格
    set_option('use_real_price', True)
    #避免使用未来函数
    set_option('avoid_future_data', True)
    g.increase1d = 0.087 # 前一日涨幅
    g.tradeday = 500
    g.pbmin = 0.01 # 最小市净率
    g.pbmax = 30 # 最大市净率
    g.stock_num = 10
    g.factor_list = ['total_operating_revenue_per_share_ttm', 'EBITDA', 'VOL5', 'BIAS5']
    g.coef_list = [ 7.76902587e-04, -1.28465094e-10, -2.13766506e-03, -2.09650382e-03]
    log.set_level('order', 'error')
    log.set_level('history', 'error')
    g.securities_every_day_0=[]
    g.securities_every_day_1 = []
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    run_weekly(weekly_adjustment, weekday=1, time='9:30', reference_security='000300.XSHG')
    run_daily(check_limit_up, time='14:00', reference_security='000300.XSHG') #检查持仓中的涨停股是否需要卖出
    run_daily(print_position_info, time='15:10', reference_security='000300.XSHG')
    
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
