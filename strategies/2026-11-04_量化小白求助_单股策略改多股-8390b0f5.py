# Clone from JoinQuant
# postId: 8390b0f5885ad3228a6fd2039e0908a0
# backtestId: b6f0152c21ef61e24633c0c06d7c7356
# title: 量化小白求助，单股策略改多股

# 克隆自聚宽文章：https://www.joinquant.com/post/9227
# 标题：只根据MACD金叉和死叉交易，实盘会有哪些缺点？
# 作者：FunnyKun

# 导入函数库
import jqdata
from jqlib.technical_analysis import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    # 要操作的股票：启明（g:global为全局变量）
    g.security = '002466.XSHE'
    #g.security = '002732.XSHE'
    
    g.holding_high_price = 0    #持有期间最高价
    
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
    
    # 取得当前可用的资金
    cash = context.portfolio.available_cash
    
    # 买入策略
    # MACD 金叉
    if isMACDGold(context,g.security):
        # 用所有 cash 买入股票
        order_value(security, cash)
        # 记录这次买入
        msg_to_send = "Buying %s:macd_gold" % (security)
        log.info(msg_to_send)
        send_message(msg_to_send, channel='weixin')
    
    # 卖出策略
    # MACD 死叉
    if isMACDDead(context,g.security):
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)
        # 记录这次卖出
        msg_to_send = "Selling %s:macd_dead" % (security)
        log.info(msg_to_send)
        send_message(msg_to_send, channel='weixin')
    
    # # 亏损超过15%
    # price = context.subportfolios[0].long_positions[security].price
    # avg_cost = context.subportfolios[0].long_positions[security].avg_cost
    
    # if price < avg_cost*0.85:
    #     # 卖出所有股票,使这只股票的最终持有量为0
    #     order_target(security, 0)
    #     # 记录这次卖出
    #     msg_to_send = "Selling %s:亏损超过15%%" % (security)
    #     log.info(msg_to_send)
    #     send_message(msg_to_send, channel='weixin')
    
    # # 持有期间最高价下跌超过15%
    # # 先计算持有期间最高价holding_high_price
    # if price == 0:
    #     g.holding_high_price = 0 # 无持仓
    # elif price > g.holding_high_price :
    #     g.holding_high_price = price
    
    # if price < g.holding_high_price * 0.85:
    #     # 卖出所有股票,使这只股票的最终持有量为0
    #     order_target(security, 0)
    #     # 记录这次卖出
    #     msg_to_send = "Selling %s:持有期间最高价下跌超过15%%" % (security)
    #     log.info(msg_to_send)
    #     send_message(msg_to_send, channel='weixin')
    
## 收盘后运行函数  
def after_market_close(context):
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
    
    if previous_date_macd_macd[security] > 0 and macd_macd[security] < 0:
        return True
    else:
        return False
