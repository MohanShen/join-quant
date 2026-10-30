# Clone from JoinQuant
# postId: 088da3a5fa6f6ae923e3e32df4310a56
# backtestId: f7782127e30d22f7fd9163e04583207d
# title: 怎样把监控单只股票改成同时监控多只股票的呢？

# 克隆自聚宽文章：https://www.joinquant.com/post/9228
# 标题：MACD 金叉和死叉代码分享（调用同花顺数据判断）
# 作者：FunnyKun

# 导入函数库
import jqdata
from jqlib.technical_analysis import *

# 初始化函数，设定基准等等
def initialize(context):

    init_cash = 30000 # 初始资金
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type='stock')])
    
    
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    # 要操作的股票池：（g:global为全局变量）
    #g.securitys = ['002439.XSHE']
    #g.security = '' 
    g.security = '002439.XSHE' #启明，市值不高100-300亿之间，流通100-200亿，2017年稳定增长年约10%
    #g.security = '300369.XSHE' #绿盟，创业板,市值50亿<x<200亿，2017年下跌70%
    #g.security = '601398.XSHG' #工行，市值&流通均上万亿，大盘股
    #g.security = '603019.XSHG' #中科曙光，4G5G概念
    #g.security = '300297.XSHE' #蓝盾，竟然是亏本的，股票下跌12%，策略下跌9%
    #g.security = '300229.XSHE'  #拓乐思，2017年股价下跌14%，策略收益26%
    #g.security = '000005.XSHE'
    #g.security = '600100.XSHG'
    
    
    
    g.holding_high_price = 0    #持有期间最高价
    
    
    g.init_price = 0    # 股票初始价格,用于计算股票收益
    
    # 获取股票的收盘价
    close_data = attribute_history(g.security, 5, '1d', ['close'])
    # 取得上一时间点价格
    g.init_price = close_data['close'][-1]

    
    
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时或每分钟开始时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
## 开盘前运行函数
def before_market_open(context):
    pass
    
## 开盘时运行函数
def market_open(context):
    
    security = g.security
    
    #获取某支股票的价格
    '''
    current_data = get_current_data()
    print current_data[security].last_price
    '''
    # 获取股票的收盘价
    close_data = attribute_history(security, 5, '1d', ['close'])
    # 取得上一时间点价格
    previous_price = close_data['close'][-1]
    # 画出上一时间点价格
    record(stock_price=previous_price)
    
    # 计算股票收益率
    stock_returns = (previous_price-g.init_price)/g.init_price
    # 画出上一时间点持股收益，方便查看，放大100倍
    record(stock_returns=stock_returns*100)
    
    # 取得当前可用的资金
    cash = context.portfolio.available_cash
    
    #资金小于8000，无需买入操作
    if cash > 8000:
        # 分析是否买入
        analysis_buy(context,security)

    # 无持有股票时，无需分析卖出
    if context.subportfolios[0].long_positions <> {}:
        # 卖出策略
        analysis_sell(context,security)
    
    
## 收盘后运行函数  
def after_market_close(context):
    pass

def analysis_choose_securitys(context,securitys):
    #分析股票池中的优质股
    choose_securitys = []
    
    
    return choose_securitys

def analysis_buy(context,security):
    # 分析某支股票是否买入时机，如是则买入
    # MACD 金叉
    
    # 取得当前可用的资金
    cash = context.portfolio.available_cash
    
    # MACD 金叉
    if isMACDGold(context,security):
        # 用所有 cash 买入股票
        order_value(security, cash)
        # 记录这次买入
        msg_to_send = "Buying %s:macd_gold" % (security)
        log.info(msg_to_send)
        send_message(msg_to_send, channel='weixin')

def analysis_sell(context,security):
    # 分析某支股票是否卖出时机
    # MACD 死叉
    # 亏损超过15%
    # 持有期间最高价下跌超过15%
    
    # MACD 死叉
    if isMACDDead(context,security):
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)
        # 记录这次卖出
        msg_to_send = "Selling %s:macd_dead" % (security)
        log.info(msg_to_send)
        send_message(msg_to_send, channel='weixin')
    
    # 亏损超过15%
    price = context.subportfolios[0].long_positions[security].price
    avg_cost = context.subportfolios[0].long_positions[security].avg_cost
    
    if price <> 0 and price < avg_cost*0.85:
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)
        # 记录这次卖出
        msg_to_send = "Selling %s:亏损超过15%%" % (security)
        log.info(msg_to_send)
        send_message(msg_to_send, channel='weixin')
    
    # 持有期间最高价下跌超过15%
    # 先计算持有期间最高价holding_high_price
    if price == 0:
        g.holding_high_price = 0 # 无持仓
    elif price > g.holding_high_price :
        g.holding_high_price = price    #设置股价为更高值
        
        if price < g.holding_high_price * 0.85:
            # 卖出所有股票,使这只股票的最终持有量为0
            order_target(security, 0)
            # 记录这次卖出
            msg_to_send = "Selling %s:持有期间最高价下跌超过15%%" % (security)
            log.info(msg_to_send)
            send_message(msg_to_send, channel='weixin')
    
    #应该卖出，但订单未成交，需要继续出售
    pass
    
    
def isMACDGold(context,security):
    '''
    判断是否 MACD 金叉
    return True or False
    '''
    #当天和前一个交易日的日期
    check_date = context.current_dt.strftime('%Y-%m-%d')
    previous_date = context.previous_date
    
    # 计算并输出 security 的 MACD 值
    macd_dif, macd_dea, macd_macd = MACD(security,check_date=check_date, SHORT = 12, LONG = 26, MID = 9)
    previous_date_macd_dif, previous_date_macd_dea, previous_date_macd_macd = MACD(security,check_date=previous_date, SHORT = 12, LONG = 26, MID = 9)
    
    if previous_date_macd_macd[security] < 0  and macd_macd[security] > 0:
        return True
    else:
        return False
        
def isMACDDead(context,security):
    '''
    判断是否 MACD 死叉
    return True or False
    '''
    #当天和前一个交易日的日期
    check_date = context.current_dt.strftime('%Y-%m-%d')
    previous_date = context.previous_date
    
    # 计算并输出 security 的 MACD 值
    macd_dif, macd_dea, macd_macd = MACD(security,check_date=check_date, SHORT = 12, LONG = 26, MID = 9)
    previous_date_macd_dif, previous_date_macd_dea, previous_date_macd_macd = MACD(security,check_date=previous_date, SHORT = 12, LONG = 26, MID = 9)
    
    if previous_date_macd_macd[security] > macd_macd[security] < 0:
        return True
    else:
        return False
