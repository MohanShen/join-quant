# Clone from JoinQuant
# postId: 74cb10fcfe9d8e475d50bfcca75e6a90
# backtestId: 8dd8d8d06f7c5f42c01e5b468056ca01
# title: 低股价轮动（无择时无止损）V0.02

"""
#最低股价轮动
#V0.02， 2017.5.18，新增条件，剔除ST个股

"""
# 导入聚宽函数库
import jqdata

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    set_parameters()
    
## 开盘前运行函数     
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    #send_message('美好的一天~')

    # 要操作的股票池
    g.scu1 = get_index_stocks('000001.XSHG')
    g.scu2 = get_index_stocks('399106.XSHE')
    g.scu = g.scu1 +g.scu2
    

def set_parameters():
    #最大持股数
    g.max_stock_num = 10
    #轮换周期
    g.period = 20 
    g.days = 0  
    g.dic1 = {}
    g.list1 = []
    
    

    
## 开盘时运行函数
##包括选股、买入和卖出
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    g.days +=1  
    if g.days % g.period == 0:
        sell_stocks(context)
        select_stocks()
        buy_selected(context)

def select_stocks():
    current_data = get_current_data()
    g.scu = [stock for stock in g.scu if not current_data[stock].paused]
    g.scu = [stock for stock in g.scu 
        if not current_data[stock].is_st 
        and 'ST' not in current_data[stock].name 
        and '*' not in current_data[stock].name 
        and '退' not in current_data[stock].name]
    #以上两句剔除停牌个股，剔除ST个股
    for stock in g.scu:
        h = attribute_history(stock, 2, '1d', fields=['close'], skip_paused =True, df=False)
        closeprice = h['close'][-1]
        g.dic1[stock] = closeprice
    g.dic2 = sorted(g.dic1.items(),key = lambda item:item[1])
    g.dic2 = g.dic2[0:g.max_stock_num]
    for stock in g.dic2:
        g.list1.append(stock[0])
    print g.list1


def sell_stocks(context):
    for stock in context.portfolio.positions:
        order_target_value(stock,0)

def buy_selected(context):
    cash = context.portfolio.available_cash
    for stock in g.list1:
        order_value(stock,cash/len(g.list1))

## 收盘后运行函数  
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
