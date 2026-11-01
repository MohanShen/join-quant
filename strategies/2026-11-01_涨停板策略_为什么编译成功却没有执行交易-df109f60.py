# Clone from JoinQuant
# postId: df109f60433390b074ce8dbd8dd85ad1
# backtestId: 518c4a78ac0608eddce31f85dba4f8af
# title: 涨停板策略，为什么编译成功却没有执行交易？

# 导入函数库
import jqdata

# 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 300253.XSHE 卫宁健康，
    g.security = '300253.XSHE'
   
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    # 开盘时运行
    #设定交易时间研究已知龙虎榜，买入时机的影响
    run_daily(market_open, time='9:30', reference_security='000300.XSHG')
    #设定尾盘判断
    run_daily(sell_weipan, '14:40',reference_security='000300.XSHG')
    # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def before_market_open(context):
    pass


##    security = g.security
    #消除未来函数影响
    #back_date=str(context.current_dt - datetime.timedelta(days=1))
    # 获取股票的收盘价
##    df_sec =  get_price(security, count = 2, end_date=context.current_dt, frequency='daily', fields=['close','open','high_limit'])
##    high_limit=df_sec['high_limit']
    #for(i in range(count))
     #   high_limit[i]=df_sec['close'][i-1]*1.1
##    close_data=df_sec['close']
##    open_data=df_sec['open']
    #high_limit = attribute_history(security, 1, '1d', ['high_limit'])
    # 取得过去五天的平均价格
    #MA5 = close_data['close'].mean()
    # 取得上一时间点价格
    # 取得当前的现金
##    cash = context.portfolio.cash
    #昨天涨停，今天开盘超过5个点就开盘半仓0.5买入，明天不涨停就卖
    #如果昨天没有涨停，而且有仓位,就要开盘卖出
def market_open(context):
    
    security = g.security
    #消除未来函数影响
    #back_date=str(context.current_dt - datetime.timedelta(days=1))
    # 获取股票的收盘价
    df_sec =  get_price(security, count=2,end_date=context.current_dt, frequency='daily', fields=['close','open','high_limit'])
    high_limit=df_sec['high_limit']
    #for(i in range(count))
     #   high_limit[i]=df_sec['close'][i-1]*1.1
    close_data=df_sec['close']
    open_data=df_sec['open']
    #high_limit = attribute_history(security, 1, '1d', ['high_limit'])
    # 取得过去五天的平均价格
    #MA5 = close_data['close'].mean()
    # 取得上一时间点价格
    # 取得当前的现金
    cash = context.portfolio.cash
    #昨天涨停，今天开盘超过2个点就开盘半仓0.5买入，明天不涨停就卖
    #如果昨天没有涨停，而且有仓位,就要开盘卖出
    
    if (close_data[-2]==high_limit[-2]):
       if (open_data[-1]>1.02*close_data[-2]) and (open_data[-1]<0.96*high_limit):
          order_value(security, 0.5*cash)
          log.info("Buying %s" % (security))
    elif  (context.portfolio.positions[security].closeable_amount > 0):
          order_target_value(security, 0)
          log.info("Selling %s" % (security))
          
          
          
    #尾盘如果不涨停，有仓位就卖出     
def sell_weipan(context):
    
    security = g.security
    df_sec =  get_price(security, count = 2, end_date=context.current_dt, frequency='daily', fields=['close','open','high_limit'])
    high_limit=df_sec['high_limit']
    close_data=df_sec['close']
    open_data=df_sec['open']
    cash = context.portfolio.cash
    
    if (close_data[-1]<high_limit[-1]) and (context.portfolio.positions[security].closeable_amount > 0):
       order_target_value(security, 0)
       log.info("Selling %s" % (security))
       
       
       
## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
    