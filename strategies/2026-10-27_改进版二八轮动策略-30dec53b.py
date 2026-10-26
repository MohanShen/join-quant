# Clone from JoinQuant
# postId: 30dec53b56badb2e2e6fce5890ac6c5b
# backtestId: 891d54c49ce78cfe12891da10e0222e5
# title: 改进版二八轮动策略

# 策略说明：基本思想来源于二八轮动；
# 但做了一个改动：一旦买入一个ETF，直到它动量小于零才卖出
# 于原始策略相比：交易次数减少，回撤也减少，收益更高
# 收盘前7分钟决定是否调仓
# 在雪球网上，我有一些关于ETF定投的资料，雪球ID：江州金猪
# 另有一个ETF定投与量化交易 的QQ群：133815027
# 江州金猪 2016-4-23

def initialize(context):
    # 对比标的
    set_benchmark('000300.XSHG') 
    # 设置佣金
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0003, min_cost=5))

def getStockPrice(stock, interval):
    h = attribute_history(stock, interval, unit='1d', fields=('close'), skip_paused=True)
    return h['close'].values[0]

def handle_data(context, data):
    # 获得当前时间
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    
    # 每天下午14:53调仓
    if hour ==14 and minute==53:
        lag = 20 # 回看前20天
        # 获得当前总资产
        value = context.portfolio.portfolio_value
        
        zs2 =  '000300.XSHG' #300指数
        zs8 =  '000905.XSHG'#500指数
        etf300 = '510300.XSHG'#'510300.XSHG'
        etf500 = '510500.XSHG'#'510500.XSHG'
        hs300 = getStockPrice(zs2, lag)
        zz500 = getStockPrice(zs8, lag)
        cp300 = data[zs2].close
        cp500 = data[zs8].close
        ret300 = (cp300 - hs300) / hs300;
        ret500 = (cp500 - zz500) / zz500;
        hold300 = context.portfolio.positions[etf300].total_amount
        hold500 = context.portfolio.positions[etf500].total_amount

        if ret300<=0 and hold300>0:
            order_target(etf300, 0)
            print("卖出300")
        elif  ret500<=0 and hold500>0:
            order_target(etf500, 0)
            print("卖出500")   

        elif ret300>ret500 and ret300>0 and (hold300==0 and hold500==0):
            order_target(etf300, value)
            print("买入300")

        elif ret500>ret300 and ret500>0 and (hold300==0 and hold500==0):
            order_target_value(etf500, value)
            print("买入500")