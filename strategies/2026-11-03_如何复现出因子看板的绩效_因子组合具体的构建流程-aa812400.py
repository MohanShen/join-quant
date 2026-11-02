# Clone from JoinQuant
# postId: aa8124002a68252cb4776968ea70bc1b
# backtestId: 7cd2020e2734ae9368f36daa673e614f
# title: 如何复现出因子看板的绩效？【因子组合具体的构建流程】

# 导入函数库
from jqdata import *
from jqfactor import *
from pathlib import Path
import pandas as pd
from six import BytesIO

'''
这个版本是
1、在回测环境，先在票池剔除 ST、停牌、涨跌停股票，获取因子数据，并预处理，生成权重数据，生成目标市值
2、开盘买入昨天收盘计算好的股票，收盘时候全部卖出

'''

'''过滤奇怪股票的函数'''
def remove_paused(stock_list, end_date):
    s = get_price(stock_list,end_date=end_date, count=1,fields='paused', panel=False).iloc[:, 1:].set_index('code').T.sum()
    return s[s < 1].index.tolist()
    
def remove_st(stock_list, end_date):
    s = get_extras('is_st',stock_list,end_date=end_date, count=1).sum()
    return s[s < 1].index.tolist()

def remove_reach_limit(stock_list, end_date):
    df = get_price(stock_list, end_date=end_date,count=1,
    fields=['close','low','high','high_limit','low_limit'], 
    panel=False).iloc[:, 1:].set_index('code')
    #剔除掉收盘价等于涨、跌停价的
    c1 = df['close'] != df['high_limit']
    c2 = df['close'] != df['low_limit']
    ##剔除掉最低价等于涨停价的(涨停一字板)
    c3 =  df['low'] != df['high_limit']
    #剔除掉最高价等于涨停价的(跌停一字板)
    c4 =  df['high'] != df['low_limit']
    c = c1 & c2 & c3  & c4  
    s = df[c].index.tolist()
    return s 

'''因子预处理函数'''
def preprocess_factor(data):
    # 3、标准化
    res = standardlize(
        
        # 1.去极值
        winsorize_med(
            data, scale=3,
        # 2、中性化
        ).apply(lambda x: neutralize(x, how=['jq_l1', 'size'], date=str(x.name.date())), axis=1)
)
    return res 


'''因子选股函数'''
def select_stocks(data, q=0.8):
    data_rank = data.rank(axis=1, pct=True)
    pick_mask = data_rank.copy()
    pick_mask[::] = 0
    # 选择最大的一组
    pick_mask[data_rank > q] = 1
    return pick_mask

def generate_portfolio(pick_mask, market_cap):
    w = market_cap[pick_mask.columns].reindex(pick_mask.index)
    res = w[pick_mask==1].div( w[pick_mask==1].sum(axis=1), axis=0).fillna(0)
    return res 


def get_factor_porfolio(factor_data, market_cap, q=0.8):
    return generate_portfolio(select_stocks(factor_data, q=q), market_cap)
    
    

# 初始化函数，设定基准等等
def initialize(context):
    # 权重文件，“当天”意思是日期都打在了收盘当日
    # 设定中证500作为基准
    set_benchmark('000905.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_option("t0_mode", True) 
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.000, close_commission=0., min_commission=0), type='stock')
    set_slippage(PriceRelatedSlippage(0.00))
    
    context.factor_name = 'VOL5'
    # 交易时剔除停牌股票
    context.remove_paused = True 
    # 交易时剔除ST股票
    context.remove_st = True
    # 交易时剔除涨跌停股票
    context.remove_reach_limit=True 
    # 股票的目标市值
    context.target_value_arr = pd.Series([])
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
    # run_daily(clear_position, time='14:55', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：平安银行（g.为全局变量）
    g.security = '000001.XSHE'

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    cur_holdings= []
    holdings = context.portfolio.positions
    
    for key, val in holdings.items():
        if val.total_amount > 0:
            cur_holdings.append(key)
            
    for key in cur_holdings:
        if not key in context.target_value_arr.index:
            log.info(f'卖出{key}')
            # 收盘即卖出 所有持仓
            order_target(key, 0)
    
    for key, val in context.target_value_arr.items():
        log.info(f'买入{val}元的{key}')
        order_target_value(key, val, )
    
    context.to_trade = []
    context.target_value_arr = pd.Series([])
    
# 收盘前运行的函数
def clear_position(context):
    log.info('函数运行时间(clear_position):'+str(context.current_dt.time()))
    holdings = context.portfolio.positions
    for key, val in holdings.items():
        if val.total_amount > 0:
            log.info(f'卖出{key}')
            # 收盘即卖出 所有持仓
            order_target(key, 0)
    
    
## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # 当前日期
    cur_date = str(context.current_dt.date())
    # 当日票池
    stock_list = get_index_stocks('000905.XSHG', cur_date)
    if context.remove_paused:
        stock_list = remove_paused(stock_list, end_date=cur_date)
    if context.remove_st:
        stock_list = remove_st(stock_list, end_date=cur_date)
    if context.remove_reach_limit:
        stock_list = remove_reach_limit(stock_list, end_date=cur_date)
    # 当日因子
    factor_data = get_factor_values(securities=stock_list, 
                                factors=[context.factor_name], 
                                start_date=cur_date, end_date=cur_date)[context.factor_name]
    # 预处理
    factor_date_2 = preprocess_factor(factor_data)
    # 当日市值 
    market_cap = get_factor_values(securities=stock_list, 
                                factors=['market_cap'], 
                                start_date=cur_date, end_date=cur_date)['market_cap']
    portfolio_df = get_factor_porfolio(factor_date_2, market_cap)
    weight_arr = portfolio_df.T.squeeze()
    context.weight_arr = weight_arr[weight_arr > 0]

    log.info(f'需要买入{len(context.weight_arr)}支股票')
    total_value = context.portfolio.total_value
    target_value_arr = total_value * context.weight_arr
    context.target_value_arr = target_value_arr
    
    
