# Clone from JoinQuant
# postId: e7113e8dbed2de8b25360bbfd853876e
# backtestId: a8f18b6ff6f1401149e34d7de611a0e1
# title: 关于聚宽模拟交易的一些问题，代码附上

# 导入函数库
import jqdata
from jqlib.technical_analysis import *


# 初始化函数，设定基准等等
def initialize(context):
    #每股收益(eps)>0.3，净资产收益率(roe)>15%，20<市盈率(pe ratio)<45，
    #净利润增长率(inc_net_profit_annual)>0.3
    set_params(context)
    set_backtest(context)
    run_daily(trade, 'every_bar')
   
def set_params(context):
    g.days = 0
    g.refresh_rate = 10
    g.stocksnum = 5
    g.g = []
def before_trading_start(context):
    set_slip_fee(context)
    
def trade(context):
    g.g.append(context.portfolio.total_value)
    date = context.current_dt.strftime('%Y-%m-%d')
    q = query(valuation.code, valuation.pe_ratio, indicator.roe, income.basic_eps, indicator.inc_net_profit_annual).filter(
        income.basic_eps > 0.3,indicator.roe >0.15, indicator.inc_net_profit_annual > 0.3, valuation.pe_ratio > 20 , valuation.pe_ratio < 45,
    ).order_by(indicator.roe.desc()).limit(50)
        
    df = get_fundamentals(q, date = date)
    stocks = list(df['code'])
    stock_set = filter_paused_stock(stocks)

    if g.days % g.refresh_rate == 0:
        
        #MA1 = MA(security_list1, check_date='2017-01-04', timeperiod=5)
        MA5 = MA(stocks, check_date = date, timeperiod=5)
        # 取得上一时间点价格
        #current_price = close_data['close'][-1]
        # 取得当前的现金
        cash = context.portfolio.available_cash
        
        if context.portfolio.total_value<0.8*max(g.g):
            log.info("risk " )
            for stock in list(context.portfolio.positions):
            # 卖出所有股票,使这只股票的最终持有量为0
                order_target(stock, 0)
        else:
            # 如果上一时间点价格高出五天平均价1%, 则全仓买入
            for stock in stock_set:
                current_price2 = attribute_history(stock,1,'1m','close')
                current_price = current_price2['close'][-1]
 
                if current_price > 1.03*MA5[stock]:
                    # 记录这次买入
                    log.info("价格高于均价 3%%, 买入 %s" % (stock))
                    # 用所有 cash 买入股票
                    order_value(stock, cash / g.stocksnum)
                # 如果上一时间点价格低于五天平均价, 则空仓卖出
                elif current_price <  MA5[stock]:
                    # 记录这次卖出
                    print(current_price, MA5[stock])
                    log.info("价格低于均价1%%, 卖出 %s" % (stock))
                    # 卖出所有股票,使这只股票的最终持有量为0
                    order_target(stock, 0)
        
        g.days = g.days + 1
    else:
        g.days += 1
    
def set_backtest(context):
    set_benchmark('000905.XSHG')            #将基准设置为中证500
    set_option('use_real_price', True)      #设置动态复权(真实价格)模式
    log.set_level('order', 'error')         #设置不同种类的log的级别, 低于这个级别的log不会输出. 所有log的默认级别是debug
    
def filter_paused_stock(stock_list):
    current_data = get_current_data()       #获取当前单位时间（当天/当前分钟）的涨跌停价, 是否停牌，当天的开盘价等
    return [stock for stock in stock_list if not current_data[stock].paused]  #生成一个未停牌股票代码的列表

def set_slip_fee(context):
    set_slippage(FixedSlippage(0.02))   #使用函数set_slippage()设置滑点为固定值0.02，即交易时加减0.01元

    dt=context.current_dt   #通过current_dt函数得到当前单位时间的开始时间

    if dt>datetime.datetime(2013,1, 1):
        #如果当前时间在2013.1.1之后，买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱，交易类型type设置为'stock'股票
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')

    else:
        #这里进行简化，如果当前时间在2013.1.1之前，买入时佣金千分之三，卖出时佣金千分之三加千分之一印花税, 每笔交易佣金最低扣5块钱，交易类型type设置为'stock'股票
        set_order_cost(OrderCost(open_tax=0, open_commission=0.003,close_commission=0.003, close_tax=0.001,min_commission=5), type='stock')
