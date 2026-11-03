# Clone from JoinQuant
# postId: e4a6d4f5ab1ad42c6075903a8ba9e3dd
# backtestId: 0f9d996773dc51b3f66385f59c88c692
# title: Statsmodels 统计包之 OLS 回归疑问

# 导入函数库
from jqdata import *
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.api as sm

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    # log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    run_daily(market_open, time='open', reference_security='000300.XSHG')

## 开盘时运行函数
def market_open(context):
    nsample = 100
    x = np.linspace(0, 10, nsample)
    X = sm.add_constant(x)
    beta = np.array([1, 10])
    e = np.random.normal(size=nsample)
    y = np.dot(X, beta) + e
    model = sm.OLS(y,X)
    results = model.fit()
    print(results.params)
    print(results.summary())
    