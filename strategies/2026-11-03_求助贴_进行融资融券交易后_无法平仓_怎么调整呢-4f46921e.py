# Clone from JoinQuant
# postId: 4f46921e158a2c2a8e64d7c78e438085
# backtestId: 7d44923c54127a7f863b051615fea53d
# title: 求助贴：进行融资融券交易后，无法平仓，怎么调整呢？

# 克隆自聚宽文章：https://www.joinquant.com/post/4896
# 标题：读《基于协整的搬砖策略》有感，有趣的协整！
# 作者：luyou

import numpy as np
import pandas as pd
from scipy import stats

#===========================================

def initialize(context):
    set_params()
    set_variables()
    set_backtest()
    init_cash = context.portfolio.starting_cash
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type='stock_margin')])

# ---代码块1. 设置参数
def set_params():
    # 股票1
    g.security1 = '601398.XSHG' 
    # 股票2
    g.security2 = '601988.XSHG'
    # 基准
    g.benchmark = '601398.XSHG'
    #回归天数
    g.test_days = 200

# ---代码块2. 设置变量
def set_variables():
    # 现在状态
    g.state = 'empty'

# ---代码块3. 设置回测
def set_backtest():
    # 设置基准
    set_benchmark(g.benchmark)
    # 只报错
    log.set_level('order', 'error')
    # 真实价格
    set_option('use_real_price', True) 
    #融资融券利率
    set_option('margincash_interest_rate', 0)
    set_option('marginsec_interest_rate', 0)
    #设置融资融券保证金
    set_option('marginsec_margin_rate',1)
    set_option('margincash_margin_rate',1)
    #避免未来函数
    set_option("avoid_future_data", True)
    
#==============================================
    
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    new_state = get_signal()
    change_positions(new_state,context)

# ---代码块4.计算z-score
def z_test():
    # 获取两支股票历史价格
    prices1 = np.array(attribute_history(g.security1, g.test_days, '1d', ['close']).close)
    prices2 = np.array(attribute_history(g.security2, g.test_days, '1d', ['close']).close)
    # 根据回归比例算它们的平稳序列 Y-a.X
    stable_series = prices2 - stats.linregress(prices2,prices1)[0]*prices1
    # 算均值
    series_mean = mean(stable_series)
    # 算标准差
    sigma = np.std(stable_series)
    # 算序列现值离均值差距多少
    diff = stable_series[-1] - series_mean
    # 返回z值
    return(diff/sigma)

# ---代码块5.获取信号
# 返回新的状态，是一个string
def get_signal():
    z_score = z_test()
    print(z_score)
    if z_score > 1:
        # 状态为全仓第一支
        return('buy1')
    # 如果小于负标准差
    if z_score < -1:
        # 状态为全仓第二支
        return('buy2')
    # 如果在正负标准差之间
    if -1 <= z_score <= 1:
        # 如果差大于0
        if z_score >= 0:
            # 在均值上面
            return('side1')
        # 反之
        else:
            # 在均值下面
            return('side2')
    

# ---代码块6.根据信号调换仓位
# 输入是目标状态，输入为一个string
def change_positions(new_state,context):
    #融资融券账户信息:查询中行持仓情况
    CNL = context.portfolio.subportfolios[0].long_positions['601988.XSHG'].total_amount
    CNS = context.portfolio.subportfolios[0].short_positions['601988.XSHG'].total_amount
    #查询工行持仓情况
    ICBCL = context.portfolio.subportfolios[0].long_positions['601398.XSHG'].total_amount
    ICBCS = context.portfolio.subportfolios[0].short_positions['601398.XSHG'].total_amount
    prices1 = np.array(attribute_history(g.security1, g.test_days, '1d', ['close']).close)[-1]
    prices2 = np.array(attribute_history(g.security2, g.test_days, '1d', ['close']).close)[-1]
    # 如果新状态是全仓股票1
    if (new_state == 'buy1' and CNL == CNS == ICBCL == ICBCS == 0):
        # 全卖股票2
        marginsec_open(g.security2, 10000)
        # 全买股票1
        margincash_open(g.security1, 10000)
        # 旧状态更改
        print('卖空组合')
        g.state = 'buy1'
    else:
        g.state = 'buy1'
    # 如果新状态是全仓股票2
    if (new_state == 'buy2' and CNL == CNS == ICBCL == ICBCS == 0):
        # 全卖股票1
        marginsec_open(g.security1, 10000)
        # 全买股票2
        margincash_open(g.security2, 10000)
        # 旧状态更改
        print('买空组合')
        g.state = 'buy2'
    else:
        g.state = 'buy2'
    # 如果处于全仓一股票状态，但是z-score交叉0点
    if (g.state == 'buy1' and new_state == 'side1'):
        print('买空平仓')
        #卖券还款
        margincash_close(g.security1, 10000)
        #买券还券
        marginsec_close(g.security2, 10000)
        # 状态改为‘平’
        g.state = 'empty'
    if (g.state == 'buy2' and new_state == 'side2'):
        print('卖空平仓')
        #卖券还款
        margincash_close(g.security2, 10000)
        #买券还券
        marginsec_close(g.security1, 10000)
        # 状态改为‘平’
        
        g.state = 'empty'
    if (g.state == 'side1' and new_state == 'side2'):
        print('Pass')
    if (g.state == 'side2' and new_state == 'side1'):
        print('Pass')
    