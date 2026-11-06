# Clone from JoinQuant
# postId: 8c1cf7a7595672b90fcf559e5302f038
# backtestId: 48ae95d5604bc7aadaca62c8003cf2d6
# title: 删

# 克隆自聚宽文章：https://www.joinquant.com/post/25215
# 标题：年化35%以上，alpha191因子在一些指数上的表现
# 作者：abbey

import pandas as pd
from jqdata import *
from jqlib.alpha191 import *
from jqfactor import neutralize
from jqfactor import standardlize
import datetime
import time

# 初始化函数
def initialize(context):
    # 到Alpha191因子及权值的元组序列；测试到Alpha120
    g.Alpha191FactorList = [(135, 0.167 ), (184, -0.333), (114, -0.5)]
    # g.Alpha191FactorList = [(114, -0.5),]
    g.period = 1                # 调仓频率，单位：日
    g.buy_stock_count = 5      # 买入股票数目
    g.day_count = 0             # 调仓日计数器，单位：日
    g.emptyFlag = True          # 空仓标志
    g.hurst_days = 80           # 大盘牛熊判断序列天数
    
    log.info('运行初始化函数')
    set_benchmark('000905.XSHG')  # 设置基准指数
    set_option('use_real_price', True)  # 动态复权
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.00025, close_commission=0.00025, min_commission=5), type='stock')  # 设置交易成本
    set_slippage(PriceRelatedSlippage(0.0006),type='stock')  # 设置滑点

# 数据处理函数
def handle_data(context, data):
    if TimeChoice(context):  # 根据择时信号决定是否调仓
        if g.emptyFlag:
            Adjust(context, data)  # 调仓
        else:
            log.info("调仓日计数 [%d]" %(g.day_count))
            if g.day_count >= g.period:
                Adjust(context, data)  # 调仓
            else:
                g.day_count += 1
    else:
        if not g.emptyFlag:
            Clear(context)  # 清仓

# 调仓
def Adjust(context, data):
    buy_stocks = PickStocks(context, data)  # 选股
    log.info("==> 调仓日选股后可买股票: %s" % GetStockInfo(buy_stocks))
    adjust_position(context, buy_stocks)  # 调整持仓
    g.day_count = 0
    g.emptyFlag = False

# 清仓
def Clear(context):
    g.emptyFlag = True
    clear_position(context)  # 清空持仓

# ================================== 以下是选股函数 ==================================
def PickStocks(context, data):
    # 获取沪深300股票
    stock_list = get_index_stocks('000905.XSHG')
    # 获取全A市场股票，去掉次新股
    # by_date = context.previous_date - datetime.timedelta(days=375)
    # stock_list = get_all_securities(date=by_date).index.tolist()
    # 过滤停牌股票
    stock_list = filter_paused_stock(stock_list)
    # 过滤涨停的股票 
    stock_list = filter_limitup_stock(context, stock_list)
    end_date = "%04d-%02d-%02d" % (context.previous_date.year, context.previous_date.month, context.previous_date.day)
    rank_factor_value = None
    for alpha_num, factor_coefficient in g.Alpha191FactorList:
        alpha_func_name = "alpha_%03d" % alpha_num
        # 获取股票因子数据
        series_alpha_values = eval(alpha_func_name)(stock_list, end_date=end_date)
        # 行业、市值中性化
        series_alpha_values = neutralize(series_alpha_values, how=['jq_l1', 'market_cap'], date=end_date, axis=1)
        # print('行业、市值中性化后因子值：',series_alpha_values.index,series_alpha_values.values)
        if rank_factor_value is None:
            rank_factor_value = factor_coefficient * standardlize(series_alpha_values)
            # print('标准化后因子值1：',rank_factor_value.index,rank_factor_value.values)
        else:
            rank_factor_value += factor_coefficient * standardlize(series_alpha_values)
    rank_factor_value = rank_factor_value.sort_values(ascending=True)
    stock_list = list(rank_factor_value.index)
    # 选取指定可买数目的股票
    if len(stock_list) > g.buy_stock_count:
        stock_list = stock_list[:g.buy_stock_count]
    return stock_list

# =================================== 以下是择时函数 ===================================
def TimeChoice(context):
    # return True #不择时
    if get_signal() == 0.0:
        return False  # 熊市清仓
    elif get_signal() == 1.0:
        return True   # 牛市开仓
    else:
        return True   # 震荡市开仓

# ====================================以下是下单函数==================================== 
def open_position(security, value):
    order = order_target_value(security, value)
    if order != None and order.filled > 0:
        return True
    return False

def close_position(position):
    security = position.security
    order = order_target_value(security, 0) # 可能会因停牌失败

def clear_position(context):
    if context.portfolio.positions:
        log.info("==> 清仓，卖出所有股票")
        for stock in list(context.portfolio.positions.keys()):
            position = context.portfolio.positions[stock]
            close_position(position)

def adjust_position(context, buy_stocks):
    for stock in list(context.portfolio.positions.keys()):
        if stock not in buy_stocks:
            log.info("stock [%s] in position is not in buy list, should sell" %(stock))
            position = context.portfolio.positions[stock]
            close_position(position)
        else:
            log.info("stock [%s]%s is already in position" % (stock, get_security_info(stock).display_name))
    position_count = len(context.portfolio.positions)
    if g.buy_stock_count > position_count:
        value = context.portfolio.cash / (g.buy_stock_count - position_count)
        for stock in buy_stocks:
            if not stock in context.portfolio.positions or context.portfolio.positions[stock].total_amount == 0:
                if open_position(stock, value):
                    if len(context.portfolio.positions) == g.buy_stock_count:
                        break

# =============================== 以下是股票常用过滤函数 ==============================
# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

# 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list 
        if not current_data[stock].is_st 
        and 'ST' not in current_data[stock].name 
        and '*' not in current_data[stock].name 
        and '退' not in current_data[stock].name]
        
# 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    # 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
    return [stock for stock in stock_list if stock in list(context.portfolio.positions.keys()) 
        or last_prices[stock][-1] < current_data[stock].high_limit]

# 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    return [stock for stock in stock_list if stock in list(context.portfolio.positions.keys()) 
        or last_prices[stock][-1] > current_data[stock].low_limit]

###########################################hurst指数仓位控制函数###################################  
# 函数：get_signal计算和返回g.position_percent
def get_signal():
    #取得股票的价格历史数据，并计算收益率
    h = attribute_history('000300.XSHG', count = g.hurst_days, unit='1d',fields='close')['close']
    x = []
    for i in range(g.hurst_days-1):
        x.append(h[i+1]/h[i]-1)
    #计算收益率在60天内的变动趋势
    beta_value = beta(x)
    #计算hurst指数
    hurst_value = hurst(x)
    if (beta_value<0 and hurst_value>0.55)  or (beta_value>0 and hurst_value<0.45): 
        g.position_percent = 0.0
        print('当前指数为熊市，beta：{0}，hurst：{1}'.format(beta_value,hurst_value))
        return g.position_percent
    elif (beta_value>0 and hurst_value>0.55)  or (beta_value<0 and hurst_value<0.45): 
        g.position_percent =1.0
        print('当前指数为牛市，beta：{0}，hurst：{1}'.format(beta_value,hurst_value))
        return g.position_percent
    else:
        g.position_percent =0.5
        print('当前指数为震荡市，beta：{0}，hurst：{1}'.format(beta_value,hurst_value))
        return g.position_percent

# 函数：R/S算法计算Hurst
#变量：x-日收益率-list(之后使用np.array变换成数组) 
#输出：计算得到的Hurst值
def hurst(X):
    #输入日回报率
    X = np.array(X)
    #N代表最大的片段值（即不对X分割时）
    N = X.size
    T = np.arange(1, N + 1)
    Y = np.cumsum(X)
    #分别计算不同长度的片段的均值
    Ave_T = Y / T
    #每个片段的最大差距R_T
    R_T = np.zeros(N)
    #对应的每段的标准差S_T
    S_T = np.zeros(N)
    #分别对不同的大小的切片计算R_T和S_T
    for i in range(N):
        S_T[i] = np.std(X[:i + 1])
        Z_T = Y - T * Ave_T[i]
        R_T[i] = np.ptp(Z_T[:i + 1])
    #计算R/S
    R_S = R_T / S_T
    #将lg(R/S)作为被解释变量Y
    R_S = np.log(R_S)[1:]
    #将lgt作为解释变量X
    n = np.log(T)[1:]
    A = np.column_stack((n, np.ones(n.size)))
    #回归得到的斜率即为hurst指数
    [m, c] = np.linalg.lstsq(np.nan_to_num(A), np.nan_to_num(R_S))[0]
    H = m
    return H
    
# 函数：计算beta
#变量：x-日收益率-list
#输出：回归计算得到的斜率beta
def beta(x):
	regindex = np.polyfit(x,np.arange(len(x)),1)
	return regindex[0]

# ================================== 以下是辅助函数 ==================================
def GetStockInfo(lStock):
    s = ""
    for sStock in lStock:
        s += "%s%s, " % (sStock, get_security_info(sStock).display_name)
    return s