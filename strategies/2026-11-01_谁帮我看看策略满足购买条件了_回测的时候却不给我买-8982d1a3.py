# Clone from JoinQuant
# postId: 8982d1a3027a9b09ad6d1ec89e57525c
# backtestId: eae8a09879bd0a3c62128e4f2881d806
# title: 谁帮我看看策略满足购买条件了，回测的时候却不给我买

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

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：平安银行（g.为全局变量）
    g.security = '600183.XSHG'

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    security = g.security
    
    # 获取今天,昨天,前天股票的收盘价列表
    close_data = get_bars(security, count=3, unit='1d', fields=['close'])['close']
    
    # 获取今天,昨天,前天股票的开盘价列表
    open_data = get_bars(security, count=3, unit='1d', fields=['open'])['open']
    
    #####判断K线是否又‘十’子的形态
    
    #收集K线‘十’子的形态
    panduan=[]
    
    #遍历前几天的开,收收盘价的绝对值差值
    for i in range(len(close_data)):
        if abs(close_data[i]-open_data[i])<0.003 or abs(close_data[i]-open_data[i])<0.007*close_data[i] : #如果差值小于5%则为K线‘十’子的形态
            panduan.append('y')  #添加到K线‘十’子的形态列表
    
    # 取得昨天的收盘价格
    ytd = close_data[-2]
    # 取得今天的收盘价格
    today_price = close_data[-1]
    # 取得当前的现金
    cash = context.portfolio.available_cash
    
    
    yn=len(panduan)>=1
    
    log.info('检查购买条件')
    log.info(today_price,ytd,yn)
    log.info('购买条件满足为%s'%str(yn))
    
    
    
    #if len(panduan) >= 1 :
        #log.lnfo('满足购买条件')
    
    
    # 如果今天的收盘价格高出昨天的收盘价1%, 则明天一开盘就全仓买入            len(panduan) >= 1则说明前几天有K线‘十’子的形态 
    if yn==True and cash/10>101*today_price :
        log.info('成功后检查购买条件')
        log.info(len(panduan))
        
        # 记录这次买入
        log.info("价格高于均价 1%%, 买入 %s" % (security))
        # 用所有 cash 买入股票
        order_value(security, cash/10)
    
    
       
    # 如果今天的收盘价格低于昨天的收盘价, 则明天一开盘就卖出
    #elif today_price > ytd and context.portfolio.positions[security].closeable_amount > 0 :

        # 记录这次卖出
        #log.info("价格低于均价, 卖出 %s" % (security))
        # 卖出所有股票,使这只股票的最终持有量为0
        #order_target(security, 0)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
