# Clone from JoinQuant
# postId: ea4c7625a722cf0ec05ea5f2efa976f3
# backtestId: 149c3f13597d4c4a68d6ee69cb23d666
# title: 新手，大神能否帮找下编写错误，实在找不出了

# 导入函数库
from jqdata import *
import talib

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')

    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    g.stock = get_index_stocks('000300.XSHG')
    g.n = 30

def handle_data(context,data):
    buy = buy_signal(context)
    sell = sell_signal(context)
    for i in range(len(g.stock)):
         if buy ==1 :
             order_target_value(g.stock[i],context.portfolio.available_cash/g.n)
        
    for i in range(len(g.stock)):
         if sell == 1:
             order_target_value(g.stock[i],0)
   
    
def get_ma(security_codes,days):
    a = attribute_history(security_codes,days,'1d',['close'])
    ma = a['close'].mean()
    b = attribute_history(security_codes,days+1,'1d',['close'])
    ma_pre = b['close'].mean()
    return (ma,ma_pre)

def buy_signal(context):
    buy = 0
    for i in range(len(g.stock)):
        ma_short_pre,ma_short = get_ma(g.stock[i],5)
        ma_long_pre,ma_long = get_ma(g.stock[i],10)
        if ma_short_pre < ma_long_pre and ma_short > ma_long and context.portfolio.positions[g.stock[i]].sellable_amount == 0:
            buy = 1
    return buy

def sell_signal(context):
    sell = 0
    for i in range(len(g.stock)):
        ma_short_pre,ma_short = get_ma(g.stock[i],5)
        ma_long_pre,ma_long = get_ma(g.stock[i],10)
        if ma_short_pre > ma_long_pre and ma_short < ma_long and context.portfolio.positions[g.stock[i]].sellable_amount > 0:
            sell = 1
            
    return sell
            













## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
