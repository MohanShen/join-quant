# Clone from JoinQuant
# postId: c9b21e9d79dbd2ac3b38d2383845da21
# backtestId: 0e14948c4e28541faea02508b522455c
# title: 【钟摆系列3】——单股票价值中枢动态调仓

# 钟摆3-单只股票价值中枢动态调仓
import statsmodels.api as sm
import numpy as np
import pandas as pd
import time
from statsmodels import regression
def initialize(context):
    # 设置初始数据获取时间，回测时在09年开始，累积一个牛熊市出来
    g.initial = '2005-01-05'
    g.stocks_ttl = ['000423.XSHE']
    set_universe(g.stocks_ttl)
    #获取东阿阿胶的在05年到现在之间的所有交易日
    g.tradingdays = get_price('000423.XSHE', fields='price', start_date=g.initial, end_date=time.strftime('%Y-%m-%d', time.localtime()))
    # 在价值中枢时买入50%，越跌越买，仓位按10%升高，到过去最低点时满仓。
    # 越涨越卖，到过去最高点时空仓。
    g.position = [ 0. ,  0.1,  0.2,  0.3,  0.4,  0.5,  0.6,  0.7,  0.8,  0.9,  1. ]
    # 交易间隔，每跌中枢到最低点的0.2时加一次仓
    # 每涨中枢到最高点的0.2时减一次仓
    g.interval = 0.2
def before_trading_start(context):
    pass
def handle_data(context,data):
    # 每周一运行一次
    if context.current_dt.isoweekday() == 1:
        security = g.stocks_ttl[0]
        # 获取当前回测时间
        today = context.current_dt.strftime("%Y-%m-%d")
        # 获取初始时间到当前回测时间的交易日天数
        days = len(g.tradingdays.ix[g.initial:today].index)
        asset = attribute_history(security, days-1, '1d','close')
        asset = asset.dropna()
        # 计算价值中枢，可以参考钟摆2帖子
        X = np.arange(len(asset.values))
        x = sm.add_constant(X)
        model = regression.linear_model.OLS(asset.values, x).fit()
        a = model.params[0]  
        b = model.params[1]
        # 得到拟合的价值中枢线
        Y_hat = X * b + a
        
        # 真实值-拟合值，差值最大最小作为价值波动区间
        # 向上平移
        i = (asset.values.T-Y_hat).argmax()
        # 得到上边界线
        c_high = X[i] * b + a-asset.values[i]
        # 越高越卖
        # C记录不同分位数对应的直线截距
        # 每涨中枢到最高点的0.2时减一次仓
        C=[]
        d = -c_high*g.interval
        c = c_high
        while c<=0.1:
            C.append(c)
            c = c+d
        C = C[:-1]
        
        # 向下平移
        i = (asset.values.T-Y_hat).argmin()
        c_low = X[i] * b + a-asset.values[i]
        d = c_low*g.interval
        c = 0
        while c<=c_low+0.1: 
            C.append(c)
            c = c+d

        # 计算出回测日各分位对应的价格
        Y = X[-1] * b + a-array(C)
        # 找到当前价格对应的位置
        i = argmin(pd.Series(abs(Y-asset.values[-1])))
        current_position = g.position[i]
        print current_position
        value = context.portfolio.portfolio_value*current_position
        # 调整仓位
        order_target_value(security, value, style=None)
        log.info("Position %s" % (value))
    
def after_trading_end(context):
    pass
    