# Clone from JoinQuant
# postId: 4cde4c71ce75e6d333f70c90365dd79f
# backtestId: f28a8c17f972eafd7e9100bbc75b96d8
# title: 网格分钟版，有错误，自己没有找出来，请大家更正，谢谢！

from jqdata import *
import pandas as pd
import talib
import numpy as np
from jqlib.technical_analysis import *

'''
持仓原则：
        截断亏损，让利润奔跑。
        1、EMA20+ATR 确认买一份。
        2、跌破EMA20-ATR，减仓一份。
        3、跌破EMA60，离场。
        多品种。
        小仓位，10%资金。
改成网格策略
        1、初始仓位1格。
        2、基准价上下两格，上卖一格，下买一格。
        3、重新以新的成交价为基准，生成网格。
        4、网格以日线ATR波动为准。
        
        
'''


def initialize(context):
    set_params()
    #
    set_option("avoid_future_data", True)
    set_option('use_real_price', True)  # 用真实价格交易
    set_benchmark('000300.XSHG')
    log.set_level('order', 'error')
    #
    # 将滑点设置为0
    set_slippage(FixedSlippage(0.002))
    # 手续费: 采用系统默认设置
    set_order_cost(OrderCost(open_commission=0.0001, close_commission=0.0001, min_commission=0.2), type='fund')

    # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    # 11:30 计算大盘信号
    run_daily(get_signal, time='every_bar')
    # 14:40 进行交易
    #run_daily(ETFtrade, time='14:40')
    #15:00 输出日志持仓信息
    run_daily(hold_log_output, time='15:00')
    
# 1 设置参数
def set_params():
    g.target_market = '000300.XSHG'
    #g.empty_keep_stock = '511880.XSHG'  # 闲时买入的标的
    g.timeinterval = 20  # 价格涨幅计算周期
    g.max_count = 1  #最多持仓标的数
    g.hisv_timeinterval = 30 #年化标准差取的周期数
    g.fengxian_ratio = 0.1 #风险比率
    g.buy = {}  # 购买股票字典
    
    # 指数、基金对, 所有想交易的etf都可以，会自动过滤掉交易时没有上市的
    g.ETF_targets =  {
        #'399905.XSHE': '159902.XSHE',#中小板指
        #'399632.XSHE': '159901.XSHE',#深100etf
        #'000016.XSHG': '510050.XSHG',#上证50
        #'000010.XSHG': '510180.XSHG',#上证180
        #'000015.XSHG': '510880.XSHG',#红利ETF
        #'399324.XSHE': '159905.XSHE',#深红利
        '000300.XSHG': '510300.XSHG', #沪深300
        #'000905.XSHG': '510500.XSHG', #中证500
        #'513100.XSHG': '513100.XSHG', #纳指ETF
        #'513500.XSHG': '513500.XSHG', #标普500ETF
        #'518880.XSHG': '518880.XSHG', #黄金ETF
        #'399006.XSHE': '159915.XSHE', #创业板
        #'159920.XSHE': '159920.XSHE', #恒生ETF
        #'399932.XSHE': '159928.XSHE', #中证消费
        #'399913.XSHE': '512010.XSHG', #医药ETF
        #'399975.XSHE': '512880.XSHG', #证券ETF
        #'000993.XSHE': '159939.XSHE', #信息技术
        #'399986.XSHE': '512800.XSHG', #银行ETF
    }
    #
    stocks_info = "\n股票池:\n"
    for security in g.ETF_targets.values():
        s_info = get_security_info(security)
        stocks_info += "【%s】%s 上市日期:%s\n" % (s_info.code, s_info.display_name, s_info.start_date)
    log.info(stocks_info)

def get_before_after_trade_days(date, count, is_before=True):
    """
    来自： https://www.joinquant.com/view/community/detail/c9827c6126003147912f1b47967052d9?type=1
    date :查询日期
    count : 前后追朔的数量
    is_before : True , 前count个交易日  ; False ,后count个交易日
    返回 : 基于date的日期, 向前或者向后count个交易日的日期 ,一个datetime.date 对象
    """
    all_date = pd.Series(get_all_trade_days())
    if isinstance(date, str):
        date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    if isinstance(date, datetime.datetime):
        date = date.date()

    if is_before:
        return all_date[all_date <= date].tail(count).values[0]
    else:
        return all_date[all_date >= date].head(count).values[-1]

def before_market_open(context):
    # 确保交易标的已经上市g.timeinterval个交易日以上
    yesterday = context.previous_date
    list_date = get_before_after_trade_days(yesterday, g.timeinterval)  # 今天的前g.timeinterval个交易日的日期
    g.ETFList = {}
    all_funds = get_all_securities(types='etf', date=yesterday)  # 上个交易日之前上市的所有基金
    #all_idxes = get_all_securities(types='index', date=yesterday)  # 上个交易日之前就已经存在的指数
    for idx in g.ETF_targets:
        symbol = g.ETF_targets[idx]
        if symbol in all_funds.index:
            if all_funds.loc[symbol].start_date <= list_date:  # 对应的基金也已经在要求的日期前上市
                g.ETFList[idx] = symbol  # 则列入可交易对象中
    #
    #log.info("ETF交易列表：%s" % g.ETFList)
    return


# 每日交易时
def ETFtrade(context):
        #
    current_returns = 100 * context.portfolio.returns
    #log.info("当前收益：%.2f%%，当前持仓: %s", current_returns, list(context.portfolio.positions.keys()))
    

# 获取信号
def get_signal(context):
    # 创建保持计算结果的DataFramejavascript:void(0)
    current_data = get_current_data()
    single_stock_cash = context.portfolio.total_value * g.fengxian_ratio
    for mkt_idx in g.ETFList:
        security = g.ETFList[mkt_idx]  # 指数对应的基金
        # 获取股票现价
        current_price = current_data[security].last_price
        #获取标的的指数移动平均值,ATR值
        #EMA20 = EXPMA(security, context.current_dt, timeperiod = 20, include_now = False)
        #stock_ema20 = (EMA20[security])
        #EMA60 = EXPMA(security, context.current_dt, timeperiod = 60, include_now = False)
        #stock_ema60 = (EMA60[security])       
        MTR20,ATR20 = ATR(security, context.current_dt, timeperiod = 20, include_now = False)
        atr_rate = ATR20[security]/current_price

        
        if not(security in context.portfolio.positions.keys()):
            log.info('买入一份: %s' % security)
            orders = order_target_value(security, single_stock_cash)
            if orders is None:
                log.info("创建订单失败...")
            else:
                g.buy[mkt_idx] = orders.price #记录本次买入订单的成交均价
        elif (1 - current_price  / g.buy[mkt_idx]) > atr_rate and context.portfolio.available_cash > single_stock_cash:
            log.info('加仓一份: %s' % security)
            orders = order_value(security, single_stock_cash)
            print(current_price, g.buy[mkt_idx], single_stock_cash, orders.price, context.portfolio.available_cash)
            if orders is None:
                log.info("创建订单失败...")
            else:
                print(orders.price)
                g.buy[mkt_idx] = orders.price
                print(g.buy[mkt_idx])
                    
        up_signal_price = g.buy[mkt_idx] * ( 1 + atr_rate )
        down_signal_price = g.buy[mkt_idx] * ( 1 - atr_rate )
        
        if (current_price / g.buy[mkt_idx] - 1) > atr_rate and (context.portfolio.positions[security].closeable_amount * current_price >= 2 * single_stock_cash):
            log.info("减仓一份: %s" % security)
            #print(current_price, g.buy[mkt_idx], single_stock_cash)
            orders = order_value(security, -single_stock_cash)
            g.buy[mkt_idx] = orders.price
            print(g.buy[mkt_idx])
        elif (current_price / g.buy[mkt_idx] - 1) > atr_rate and context.portfolio.positions[security].closeable_amount * current_price < 2 * single_stock_cash and context.portfolio.positions[security].closeable_amount * current_price > 0:
            print(context.portfolio.positions[security].closeable_amount * current_price, up_signal_price, current_price, down_signal_price)
            log.info("清仓: %s" % security)
            orders = order_target(security, 0)
            g.buy[mkt_idx] = orders.price
            print(g.buy[mkt_idx])

# 持仓信息日志输出函数
def hold_log_output(context):
    long_positions_dict = context.portfolio.long_positions
    for position in list(long_positions_dict.values()):  
        print("标的:{0},总仓位:{1},标的价值:{2:.2f},可用资金:{3:.2f}".format(position.avg_cost, position.total_amount, position.value, context.portfolio.available_cash))
    #print("总资产:{0:.2f},剩余资金:{1:.2f}".format(context.portfolio.total_value, context.portfolio.available_cash))
    

