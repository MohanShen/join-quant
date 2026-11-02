# Clone from JoinQuant
# postId: a8dbcaaac926268e45bd2f82b13b5a0e
# backtestId: 19b5e06ede023921171997489b3699e5
# title: 回测和研究不一致

# 导入函数库
import jqdata

# 初始化函数，设定基准等等
def initialize(context):

    run_daily(market_open, time='open', reference_security='000300.XSHG')


def market_open(context):
    df = get_fundamentals(query(indicator).filter(indicator.code=='000001.XSHE'), date ='2010-02-01')
    print "2010-02-01返回扣非净利润为 %s"%df['adjusted_profit'][0]
 

    df = get_fundamentals(query(indicator).filter(indicator.code=='000001.XSHE'), statDate ='2009Q3')
    print "2009Q3返回扣非净利润为 %s"%df['adjusted_profit'][0]