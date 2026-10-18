# Clone from JoinQuant
# postId: 4e0feefc054353e9e82552e0bba6d3a9
# backtestId: 7cb0b9befc45df7f806cdd8f29143c47
# title: RSRS模型深入研究2-对右偏态样本处理的质疑与分析

from jqdata import *
import pandas as pd
import numpy as np
import scipy.stats as stats
import datetime
import talib
from jqlib.technical_analysis import *
import math
import statsmodels.api as sm


# 初始化函数，设定基准等等
def initialize(context):
    # 设定上证指数作为基准
    set_param(context) #初始化系统参数
    set_rscore_param(context) # 初始化RS参数
    set_first_run(context) #初始化运行
    g.Trading = 'open' #'open'
    ## 开盘前运行函数 
    # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security=g.security) 
    # 开盘时运行
    run_daily(market_open, time = g.Trading, reference_security=g.security)
    # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security=g.security)

def set_param(context):
    # 要操作的股票：平安银行（g.为全局变量）
    g.security = '000300.XSHG'
    ### 股票相关设定 ###
    set_benchmark(g.security)
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    log.set_level('order', 'error') # 过滤掉order系列API产生的比error级别低的log

def set_rscore_param(context):
    g.N = 18
    g.M = 1100
    g.buy = 0.01288
    g.sell = -0.1123
    
def set_first_run(context):
    rs = RSRS_CALC(g.security,context.previous_date,g.N,g.M)
    g.beta_list = rs.create_base_record('2005-01-05')
       
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    send_message('美好的一天~')

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    
    stock = g.security
    positions_value = context.portfolio.positions_value
    total_value = context.portfolio.total_value
    #context.portfolio.positions[stock].closeable_amount
    # 取得当前的现金
    cash = context.portfolio.available_cash
    date = context.previous_date #context.previous_date 
    
    rs = RSRS_CALC(stock,date,g.N,g.M)
    g.rscore = rs.calc_rscore(g.beta_list)
    #DF,g.buy,g.sell = rs.marshal(g.beta_list,g.rightdev_list)
    ## 获取上下交易买卖点
    print ('rscore%s'%g.rscore)
    
    if g.rscore > g.buy:
        # 记录这次买入
        log.info("买入 %s" % (stock))
        # 用所有 cash 买入股票
        order_value(stock, cash)
        # 如果上一时间点的值小于卖出阈值, 则空仓卖出
    elif g.rscore < g.sell and positions_value > 0:
        # 记录这次卖出
        log.info("卖出 %s" % (stock))
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(stock, 0)

 
## 收盘后运行函数  
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
    record(rscore=g.rscore,buy=g.buy,sell=g.sell)

## 运行函数
class RSRS_CALC:
    N = 18
    M = 1100
    
    def __init__(self,security,date,N,M) :
        self.date = date
        self.security = security
        self.N = N
        self.M = M
        
    def get_prices(self,start_date,count) :
        security = self.security
        end_date = self.date
        if count > 0 : 
            prices = attribute_history(security, count, '1d', ['close'])
        elif start_date is not None: 
            prices = get_price(security = security, start_date = start_date, end_date = end_date, \
                 frequency='daily', fields=['close'])
        if len(prices.values)>0 :
            return prices.close
        else: pass
        
    def calc_OLS_list(self,x) : #OLS线性回归
        results = x.pct_change().dropna()
        return results[-1:].values
    
    def create_base_record(self,start_date = '2005-01-05'):
        N = self.N
        closes = self.get_prices(start_date,0)
        beta_list = []
        for i in range(N,len(closes)):
            x = closes[i-N:i]
            results = self.calc_OLS_list(x)
            if len(results)>0:
                beta_list.append(results[0])
        return beta_list
    
    def new_beta_record(self):
        N = self.N
        closes = self.get_prices(None,N)
        x = closes
        results = self.calc_OLS_list(x)
        beta= results[0]
        return beta
    
    def calc_rscore(self,beta_list):# 计算标准化的RSRS指标
        M = self.M
        if not (len(beta_list) > 0 or len(rightdev_list) > 0 ):
            beta_list = self.create_base_record('2005-01-05')
        beta = self.new_beta_record()
        beta_list.append(beta)
        section = beta_list[-M:] # 计算均值序列 
        zscore = stats.zscore(section).tolist()[-1] #序列标准分
        #计算右偏RSRS标准分
        #zscore_rightdev= zscore*beta
        zscore_rightdev= -1*math.log(abs(zscore))*sqrt(abs(beta))
        return zscore_rightdev
    
    def marshal(self,beta_list):
        DF = pd.DataFrame([beta_list],index=['beta']).T
        DF['zscore'] = DF.beta.apply(lambda x: (x-DF.beta.mean())/DF.beta.std())
        DF['rscore'] = DF.zscore.apply(lambda x: -math.log(abs(x)))
        DF['qscore'] = DF.apply(lambda x: -1*x.rscore*sqrt(abs(x.beta)),axis=1)
        return DF,np.nanpercentile(DF.rscore,80),np.nanpercentile(DF.rscore,5)