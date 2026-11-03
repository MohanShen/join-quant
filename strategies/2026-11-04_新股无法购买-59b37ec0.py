# Clone from JoinQuant
# postId: 59b37ec029c49674b4b5a7d35dab1029
# backtestId: 2d3c619f921725fa46d15524b49752fd
# title: 新股无法购买..

# 导入函数库
from jqdata import *

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
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

def select_stocks(market, start_date):
    df = get_all_securities(types=['stock'])    
    df = df[(df['start_date'] == start_date)]

    if (market == "主板"):
        code = [code for code in df.index.tolist() if (code[0]=='6' and code[1]!='8') or (code[0]=='0' and code[2]!='2')]        
    elif (market == "中小板"):
        code = [code for code in df.index.tolist() if code[0]=='0' and code[2]=='2']
    elif (market == "创业板"):
        code = [code for code in df.index.tolist() if code[0]=='3']
    else:
        print("不支持%s" % market)

    return df.loc[code, ['display_name','start_date']]

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：平安银行（g.为全局变量）
    g.security = '000001.XSHE'


## 开盘时运行函数
def market_open(context):
    code_list = select_stocks("创业板", context.current_dt.date())
    log.info('今日新股:%s'%code_list)
    for stock in code_list.index:
        df = get_bars(stock, 1, '1m', [
            'close', 'low', 'high', 'money'], df=False)
        order_target(stock, 100)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
