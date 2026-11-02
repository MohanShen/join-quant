# Clone from JoinQuant
# postId: b44a7b39075f9474cb6b20571f4ea5e4
# backtestId: c787324c90a10216b6749b68f78703b5
# title: 5日上窜30日，按照昨天以前都一收盘价位准，今天的一分钟价，来统计，为什么不准啊？

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
 
   # 最大持仓数目限制
    g.Stocknum=5
    #短期M日均线
    g.M=-5
    #长期N日均线
    g.N=-20
    #为求J日钱的N日均线设立的J变量
    g.J=-7
   #设置阈值为1（百分之1），要求当前价格不超过N日均线价格的阈值比例
    g.Threshold=1
    
      # 交易运行
    run_daily(trade, time='every_bar', reference_security='000300.XSHG') 
      # 收盘后运行
   # run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
## 开盘前运行函数     
def trade(context):
    # 输出运行时间
    log.info('函数运行时间(market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    #send_message('美好的一天~')


#stocks类型为panel的三维数组类型，（items,行,列），
#例子中对应于（【close,open】,日期，股票代码）
#（g.为全局变量）

    #stocks类型为list类型【'','','',..】
    stocks = get_index_stocks('000300.XSHG')
    stocks_his_price=get_price(stocks, \
    start_date=datetime.datetime.now()-datetime.timedelta(days=120), \
    end_date=datetime.datetime.now(),\
    frequency='1d', fields=['close'])

    # 要操作的股票：平安银行（g.为全局变量）
    # g.security = '000001.XSHE'
#取出stock_his_price这个panel中以close价格为
#超三维Items的剩下以日期为行+股票代码为列的
#dataframe赋值给hs_data_frame
    his_data_frame=stocks_his_price['close']
#print(type(his_data_frame))
#stocks_his_price=filter_paused_stock(stocks_his_price)
    # 取得当前的现金
   #cash = context.portfolio.available_cash
    
#shape[0]统计行数
    column_num=his_data_frame.shape[0]
#print(column_num)
#如果下面N=-1，代表是今天最新的数据，不是代表昨天的数据
#print(his_data_frame['000002.XSHE'][-1:column_num].mean())
    his_columns_name=his_data_frame.columns.values.tolist()

#如有股票达到要求先卖出

#结束卖出
   
    #要求满足当前价格小于任意一条卖出
    #满足K最新价格小于B代表的当然N日均线卖出
    #求最近N天的均价 
    #取得最新价格
    if len(context.portfolio.positions)>0:
       for stock in list(context.portfolio.positions.keys()):
           k=his_data_frame[stock][-1:column_num].mean()
           b=(his_data_frame[stock][g.N:column_num].mean())
           if (k-b)<0: 
             # 记录这次卖出
              log.info("价格低于均价, 卖出 %s" % (stock))
              # 卖出所有股票,使这只股票的最终持有量为0
              order_target(stock,0)


#循环开始指数标的股票如果满足则买入或卖出    
    for data_frame in his_columns_name:  
    #求最近N天的均价 
        a=(his_data_frame[data_frame][g.M:column_num].mean())
        b=(his_data_frame[data_frame][g.N:column_num].mean())
    #取J天前的N天均价（用mean()方法）
        c=(his_data_frame[data_frame][g.N+g.J:column_num+g.J].mean())
    #print("")

    
    #取得最新价格
        k=his_data_frame[data_frame][-1:column_num].mean()
    
    #print((k-b)/b*100)
    
    #要求下面三者只要满足任意一条，就执行下面买入操作！！！
    #或要求M天均线价格大于N天均线价格
    #或前1天M天均线价格大于前1天N天均线价格
    #或前2天M天均线价格大于前2天N天均线价格
        buy_list=list(context.portfolio.positions)
        if len(buy_list)<g.Stocknum : 
           cash=context.portfolio.available_cash/(g.Stocknum-len(buy_list))
           if (a>b and b>c ):
              if (k-b)>=0 and ((k-b)/b*100)<g.Threshold and data_frame not in buy_list:
                   # 记录这次买入
                 log.info("价格高于均价 1%%, 买入 %s" % (data_frame))
                   # 用所有 cash 买入股票 
                 order_value(data_frame,cash)
                    
  
  
## 收盘后运行函数  
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
