# Clone from JoinQuant
# postId: a0ba35addfc694ca2618d937a1b785cf
# backtestId: 55d53ade2345265471560f3f9e89eb65
# title: 求帮助，这个代码哪里错了

# 导入函数库
import jqdata
from jqlib.technical_analysis import*
def initialize(context):
    g.security='002594.XSHE'
    set_benchmark('000300.XSHG')
    set_option('ues_real_price',True)
def handle_data(context,data):
    security=g.security
    macd_diff,macd_dea,macd_macd=MACD(security,check_data=context.current_dt,SHORT=12,LONG=26,MID=9)
    cash=context.portfolio.cash
    if macd_diff>0 and macd_dea>0 and macd_diff>macd_dea:
        order_value(security,cash)
        log.info('买入股票%s'%(security))
    elif macd_diff<0 and macd_dea<0 and macd_diff<macd_dea and context.portfolio.positions[security].closeable_amount>0:
        order_target(security,0)
        log.info('买出股票%s'%(security))