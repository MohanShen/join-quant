# Clone from JoinQuant
# postId: c7a8aa43d9df00e9a1cd304738f2c7e9
# backtestId: 8a3e9d3bdebb054def49ba63a09d205c
# title: 求教高手帮忙解决问题：打板策略，运行到后面没有交易了

# 导入函数库
from jqdata import *
import json #Python2 输出中文列表使用
import talib as tb
import time

# 初始化程序, 整个回测只运行一次
def initialize(context):
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    
    # 让每天早上开盘时执行 morning_sell_all
    run_daily(morning_sell_all, '10:30')

# 替换代码
def after_code_changed(context):
    # 每天买入股票数量
    g.daily_buy_count  = 4
    # 设置我们要操作的股票池, 这里我们操作多只股票，下列股票选自计算机信息技术相关板块
    g.stocks =list(get_all_securities().index)
    # 今天已经买入的股票
    g.today_bought_stocks = set()

    # 得到所有股票昨日收盘价, 每天只需要取一次, 所以放在 before_trading_start 中
    g.last_df = history(1,'1d','close',g.stocks)
    
    
def morning_sell_all(context):
    # 将目前所有的股票卖出
    for security in context.portfolio.positions:
        # 全部卖出
        order_target(security, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security))

    

# 3天中主力必须吸筹1天以上。判断主力吸条件：均线大于昨天收盘价的1.03
def attracting_funds(context,stock_list):
    stock_avg=history(3, unit='1d', field='avg', security_list=stock_list, df=False, skip_paused=True, fq='pre')
    stock_close=history(4, unit='1d', field='close', security_list=stock_list, df=False, skip_paused=True, fq='pre')
    stock_list = [stock for stock in stock_list  if
                    stock_avg[stock][-1]>=stock_close[stock][-2]*1.03
                    or stock_avg[stock][-2]>=stock_close[stock][-3]*1.03
                    or stock_avg[stock][-3]>=stock_close[stock][-4]*1.03
                ]
    return   stock_list       

# 前三天不涨停
def No_limit_for_three_days(context,stock_list):
    stock_close=history(3, unit='1d', field='close', security_list=stock_list, df=False, skip_paused=True, fq='pre')
    stock_high_limit=history(3, unit='1d', field='high_limit', security_list=stock_list, df=False, skip_paused=True, fq='pre')
    stock_list = [stock for stock in stock_list if stock_close[stock][-1] != stock_high_limit[stock][-1]]
    stock_list = [stock for stock in stock_list if stock_close[stock][-2] != stock_high_limit[stock][-2]]
    stock_list = [stock for stock in stock_list if stock_close[stock][-3] != stock_high_limit[stock][-3]]
    return  stock_list

# 过滤器，过滤停牌，ST，科创，新股，1元股，一字板（可选择过滤）
def filter_specials(context,stock_list):
    curr_data = get_current_data()
    stock_list=[stock for stock in stock_list if stock[0:3] != '688'] #过滤科创板'688' 
    # stock_list=[stock for stock in stock_list if stock[0:3] != '300'] #过滤创业板'300' 
    # stock_list=[stock for stock in stock_list if stock[0:2] != '60'] #过滤科创板'60' 
    # stock_list=[stock for stock in stock_list if stock[0:2] != '00'] #过滤科创板'00' 
    stock_list = [stock for stock in stock_list if not curr_data[stock].is_st]
    stock_list = [stock for stock in stock_list if not curr_data[stock].paused] 
    stock_list = [stock for stock in stock_list if 'ST' not in curr_data[stock].name]
    stock_list = [stock for stock in stock_list if '*'  not in curr_data[stock].name]
    stock_list = [stock for stock in stock_list if '退' not in curr_data[stock].name]
    stock_list = [stock for stock in stock_list if  curr_data[stock].day_open>1] # 过滤一元股
    stock_list = [stock for stock in stock_list if  curr_data[stock].high_limit<99] # 过滤99以上元股
    stock_list = [stock for stock in stock_list if curr_data[stock].day_open!= curr_data[stock].high_limit] # 过滤一字板
    return   stock_list 

#macd函数
def MACD(stock,context):
    h = get_bars(stock, count = 50,end_dt=context.current_dt,unit='1d', fields=['close'], include_now=True)
    close = array(h['close'])
    macd_tmp = tb.MACD(close, fastperiod = 7, slowperiod = 28, signalperiod = 5) 
    DIF  = macd_tmp[0]
    DEA  = macd_tmp[1]
    MACD = macd_tmp[2]*2
    return MACD

def trade(context):
    if MACD('000001.XSHG',context)[-1] < 0:
        return True
    else:
        return False

# 在每分钟的第一秒运行, data 是上一分钟的切片数据
def handle_data(context, data):
    if trade(context) == False:
    # 只追涨11点前的股票
        if context.current_dt.hour > 11:
            return
    # 每天只买这么多个
        if len(context.portfolio.positions) < g.daily_buy_count and str(context.current_dt.time()) >= '09:30:00' and str(context.current_dt.time()) <= '10:30:00':
            g.stocks= filter_specials(context,g.stocks) #过滤科创板，ST，停牌，退市，上市半年内的新股,1元股,99元以上股
            g.stocks=No_limit_for_three_days(context,g.stocks) # 前3天不涨停
            g.stocks=attracting_funds(context,g.stocks) #主力吸筹
            for security in g.stocks:
                a=1
                if security[0:3] != '300':
                    a=2
        # 得到当前价格
                price = data[security].close
                high_limit=get_current_data()[security].high_limit
        # 获取这只股票昨天收盘价
                last_close = g.last_df[security][0]
        # 如果上一时间点价格已经涨了9.8%~9.9%
                if price/last_close > 1.098*a and price/last_close < 1.0998*a :
                    if security not in context.portfolio.positions.keys() :
            # 得到当前资金余额
                        cash = context.portfolio.cash
            # 计算今天还需要买入的股票数量
                        need_count = g.daily_buy_count - len(g.today_bought_stocks)
            # 把现金分成几份,
                        buy_cash = context.portfolio.cash / need_count

            # 买入这么多现金的股票
                        order_value(security, buy_cash,LimitOrderStyle(high_limit))
                        g.stocks.remove(security)

            # 放入今日已买股票的集合
                        g.today_bought_stocks.add(security)

            # 记录这次买入
                        log.info("Buying %s" % (security))

            # 买够4个之后就不买了
                if len(g.today_bought_stocks) >= g.daily_buy_count:
                    break