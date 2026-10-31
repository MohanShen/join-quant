# Clone from JoinQuant
# postId: 45fcdc1314197f3541e0e67f2b2fa27a
# backtestId: 4acda657473c2334af497c25aa60391a
# title: 改写了一下机器学习多因子策略，但是为什么回测结果上没有改变？

import pandas as pd
import numpy as np
import math
from sklearn.svm import SVR  
from sklearn.model_selection import GridSearchCV  
from sklearn.model_selection import learning_curve
from sklearn.ensemble import RandomForestRegressor
import jqdata
from jqlib.technical_analysis import *

def initialize(context):	#定义函数‘初始化’
    set_params()	#设置‘策略参数’
    set_backtest()	#设置‘回测条件’
    run_daily(trade, 'every_bar')	#设置执行频率（每k线）
    
def set_params():	#定义函数‘设置策略参数’
    g.days = 0		#初始日期为0
    g.refresh_rate = 10		#刷新率（10日一刷新）
    g.stocknum = 10	#持仓数目=10
    
def set_backtest():	#定义函数：‘设置回测条件’
    set_benchmark('000985.XSHG')	#设定基准：
    set_option('use_real_price', True)	#真实价格
    log.set_level('order', 'error')
    
#本案例中采用了m对数市值，IND行业，b对数净资产，NI公司净利润，LEV财务杠杆，g营业收入同比增长率，RD对数开发支出
def trade(context):	#定义‘交易’函数
    if g.days % 10 == 0:	#如果日期被10整除（按10日轮动）
        sample = get_index_stocks('000985.XSHG', date = None)	#股票池为？
	#各种财务数据，依次为：股票名称、股票市值、净资产（总资产-负债），杠杆（总资产/负债，但应该是负债/资产），净利润，净利润+1（存疑），营业收入同比增值率，开发支出
        q = query(valuation.code, valuation.market_cap, balance.total_assets - balance.total_liability,
                  balance.total_assets / balance.total_liability, income.net_profit, income.net_profit + 1, 
                  indicator.inc_revenue_year_on_year, balance.development_expenditure).filter(valuation.code.in_(sample))
        df = get_fundamentals(q, date = None)	#获取财务数据，制成df表格
        df.columns = ['code', 'log_mcap', 'log_NC', 'LEV', 'NI_p', 'NI_n', 'g', 'log_RD']	#列索引，log为取对数，取对数的原因是逻辑回归公式是
        
        df['log_mcap'] = np.log(df['log_mcap'])	#市值对数
        df['log_NC'] = np.log(df['log_NC'])	#?按照下文中的因子来看应该是对数净资产
        df['NI_p'] = np.log(np.abs(df['NI_p']))	#公司净利润对数
        df['NI_n'] = np.log(np.abs(df['NI_n'][df['NI_n']<0]))	#负公司净利润
        df['log_RD'] = np.log(df['log_RD'])	#开发支出对数
        df.index = df.code.values	#目录就是股票名称
        del df['code']	#删除股票表格
        df = df.fillna(0)	#把0填充空值
        df[df>10000] = 10000	#把表格中大于10000的数改为10000
        df[df<-10000] = -10000	#把表格中小于-10000的数改为-10000
        industry_set = ['801010', '801020', '801030', '801040', '801050', '801080', '801110', '801120', '801130', 
                  '801140', '801150', '801160', '801170', '801180', '801200', '801210', '801230', '801710',
                  '801720', '801730', '801740', '801750', '801760', '801770', '801780', '801790', '801880','801890']	#行业代码
        
        for i in range(len(industry_set)):
            industry = get_industry_stocks(industry_set[i], date = None)	#取得行业
            s = pd.Series([0]*len(df), index=df.index)	#把s定义为一个serise（panda的一种格式，一维数组），目录是df的index也就是股票名称，而内容是df的长度的0）
            s[set(industry) & set(df.index)]=1	#s这个series中，industry和index都是1
            df[industry_set[i]] = s	#在df中加一列行业
            
        X = df[['log_NC', 'LEV', 'NI_p', 'NI_n', 'g', 'log_RD','801010', '801020', '801030', '801040', '801050', 
                '801080', '801110', '801120', '801130', '801140', '801150', '801160', '801170', '801180', '801200', 
                '801210', '801230', '801710', '801720', '801730', '801740', '801750', '801760', '801770', '801780', 
                '801790', '801880', '801890']]	#所有因子
        Y = df[['log_mcap']]	#市值对数
        X = X.fillna(0)	#填充0
        Y = Y.fillna(0)	#填充0
        
        svr = SVR(kernel='rbf', gamma=0.1) 
        model = svr.fit(X, Y)
        factor = Y - pd.DataFrame(svr.predict(X), index = Y.index, columns = ['log_mcap'])	#因子计算总值=市值对数-计算得出的市值对数
        factor = factor.sort_index(by = 'log_mcap')	#对因子计算总值从小到大排序（即差值越小越好，总而言之没问题）
        stockset_first =  list(factor.index[:30])	#@@@@@@@@@@@@
	stockset = []
	#@@@@@@@@@@@@
	for i in stockset_first:	#@@@@@@@@@@@@
		if RSI(i,context.previous_date,N1=6)>50 and len(stockset) <11:	#@@@@@@@@@@@@
			stockset = stockset+[i]		#@@@@@@@@@@@@
        sell_list = list(context.portfolio.positions.keys())	#卖出列表=持仓股
        for stock in sell_list:	#对于卖出列表中的股票
            if stock not in stockset[:g.stocknum]:	#如果股票不在买入列表中
                stock_sell = stock	#卖出股就是该股
                order_target_value(stock_sell, 0)	#卖出
            
        if len(context.portfolio.positions) < g.stocknum:	#如果持仓数目小于目标数目
            num = g.stocknum - len(context.portfolio.positions)	#数量=目标数目-持仓数目
            cash = context.portfolio.cash/num	#现金=持有现金/数量
        else:
            cash = 0
            num = 0
        for stock in stockset[:g.stocknum]:	#如果在买入列表中的股票
            if stock in sell_list:	#如果股票在卖出列表中
                pass	#不管
            else:
                stock_buy = stock	#如果股票不在卖出列表中
                order_target_value(stock_buy, cash)	#买入
                num = num - 1
                if num == 0:
                    break
        g.days += 1
    else:
        g.days = g.days + 1    
            