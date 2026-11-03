# Clone from JoinQuant
# postId: 10816e4753f6118f445303f524bbdd97
# backtestId: 89ad51f97c00d558d66d3e85ac7a59df
# title: 新手求救，交易无法正常执行！！

# 导入函数库
from jqdata import *
import pandas as pd
# 初始化函数，设定基准等等
def initialize(context):
    set_params()    #1设置策参数
    set_slippage(FixedSlippage(0))
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
    set_order_cost(OrderCost(open_tax=0, close_tax=0, \
    #买入卖出印花税
    open_commission=0.0003, close_commission=0.0003,\
        #买入卖出佣金
    close_today_commission=0, min_commission=5), type='fund')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 每周最后一天确定信号
    run_weekly(before_market_open,weekday = 5, time = '14:57')
      # 每周最后一天交易
    run_weekly(market_open,weekday = 5, time = '14:57')
      # 收盘后运行记录当天收益
    run_daily(after_market_close, time='after_close')

def set_params():
    g.security = ['159995.XSHE', '159992.XSHE','512690.XSHG', '512290.XSHG', '512010.XSHG', '512480.XSHG', '159928.XSHE',
 '515220.XSHG', '512170.XSHG', '515000.XSHG', '512400.XSHG', '515880.XSHG', '159996.XSHE', '510050.XSHG',
 '515050.XSHG', '515790.XSHG', '515750.XSHG', '510300.XSHG', '512200.XSHG', '510500.XSHG',
 '159825.XSHE', '512800.XSHG', '510900.XSHG', '159920.XSHE', '159827.XSHE', '512580.XSHG', '512660.XSHG',
 '512670.XSHG', '515210.XSHG', '510650.XSHG', '588000.XSHG', '159915.XSHE', '512260.XSHG', '512980.XSHG',
 '159949.XSHE', '512720.XSHG', '515700.XSHG', '160723.XSHE', '513050.XSHG', '512880.XSHG',
 '518880.XSHG', '161226.XSHE']
#持仓初始化
    g.chicang = []
#买入列表
    g.buylist = []
#卖出列表
    g.selllist = []
#继续持有列表
    g.nochange =[]
#信号周期
    g.period = 10

## 开盘前运行函数
def before_market_open(context):
#输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
#初始化计数器
    i = 0
#初始化购买列表
    g.buylist = []#初始化每周要购买的列表
#建立数据表格
    df = pd.DataFrame()
#建立信号表格
    for row in g.security:
        #取出股票池中每只股票10周期的收盘价
        security = row
        close_data = attribute_history(security, g.period, '1d', ['close'],df=False)
        #前周期收盘价
        old_price = close_data['close'][0]
        #本周期数据
        current_data = get_current_data()
        #当前时间价格
        new_price = current_data[security].last_price
        #周期内涨幅
        increase = (new_price - old_price)/old_price * 100
        #写出一个DF表格
        df.loc[i,'股票代码'] = row
        df.loc[i,'股票名称'] = get_security_info(row).display_name
        df.loc[i,'周期涨幅'] = increase
        df.loc[i,'前收盘价'] = old_price
        df.loc[i,'现收盘价'] = new_price
        i = i+1
        #优化DF格式
    df.sort_values(by = '周期涨幅',ascending=False,inplace=True)#按照涨幅排序
    df.reset_index(drop=True,inplace=True)# 重新设置索引
    df['周期涨幅'] = df['周期涨幅'].apply(lambda x:'%.2f'%x)#周期涨幅列保留2位小数
    log.info("行情统计结果表:\n%s" % (df))
#取出信号(选取涨幅排名第345名标的,删除下跌标的)
    df1 = df.head(6) #取前六
    df1 = df1.drop([0,1,2]) #去前三
#删除下跌标的
    for a in df1.index: 
        if float(df1.loc[a,'周期涨幅']) < 0:
            df1 = df1.drop(a)
    g.buylist = df1
    print(g.buylist)

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    need_count = len(g.buylist)
    if need_count == 0:
        cash = context.portfolio.available_cash
    else:
        buy_cash = context.portfolio.available_cash / need_count
#设置交易行为
    if g.buylist.empty:#如果没有信号
        for stock in context.portfolio.positions.keys():#获取持有标的
            order_target_value(stock, 0)#卖出持有标的
            log.info('没信号清仓卖出%s'% (stock))
    else:#如果有信号
        if g.chicang:#如果没有持仓
            for c in g.buylist['股票代码']:
                order_value(c, buy_cash)
                log.info('有信号0持仓买入%s'% (c))
        else:
            for stock in context.portfolio.positions.keys():#获取持有标的
                if stock not in g.buylist['股票代码']:
                    order_target_value(stock, 0)#卖出持有标的
                    log.info('持仓不在信号表卖出%s'% (stock))
                elif stock in g.buylist['股票代码']:
                    pass
            for d in g.buylist['股票代码']:
                if d not in context.portfolio.positions.keys():
                    order_value(d, buy_cash)
                    log.info('信号表不在持仓买入%s'% (d))

        
## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
