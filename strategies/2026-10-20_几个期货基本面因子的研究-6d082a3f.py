# Clone from JoinQuant
# postId: 6d082a3f37ec8f24e6dd70da2e0930d6
# backtestId: c145328472b76508afbee749a1afae5f
# title: 几个期货基本面因子的研究

# 导入函数库
from six import StringIO

## 初始化函数，设定基准等等
def initialize(context):
    
    #设定做多/空因子排名前/后N%
    context.rate = 0.3
    
    #设定杠杆
    context.lever = 1
    
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    
    # 设定备选品种
    context.allVar = ['A','AG','AL','AP','AU','BU','C','CF','CS','CU','FG','HC','I','J',
    'JD','JM','L','M','MA','NI','OI','P','PB','PP','RB','RM','RU','SF','SM','SN','SR',
    'TA','V','Y','ZC','ZN']

    # 获得研究目录csv数据
    body=read_file("ry.csv")
    df = pd.read_csv(StringIO(body))
    df.index = df['Unnamed: 0']
    del df['Unnamed: 0']
    context.df = df[context.allVar]

    set_order_cost(OrderCost(open_commission=0.0000, close_commission=0.0000,close_today_commission=0.00), type='index_futures')

    set_option('futures_margin_rate', 0.1)

    set_slippage(FixedSlippage(0))

    run_daily( before_market_open, time='20:30:00')

    run_daily( market_open, time='21:00:01')

    run_daily( after_market_close, time='15:00:01')
    

## 开盘前20:30:00运行函数
def before_market_open(context):
    
    ## 现在的自然日日期
    date = context.current_dt.strftime('%Y-%m-%d')

    ## 此日期的各合约展期
    ry_today_df = context.df.loc[date,:].dropna(how='any')
    ry_today_df.sort()
    
    ## 选出多品种列表、空品种列表
    var_num = len(ry_today_df)
    do_num = var_num*context.rate
    var_more = ry_today_df.index[:do_num]
    var_short = ry_today_df.index[-do_num:]

    ## 找到待做多空品种的主力合约
    context.symbol_more = [get_dominant_future(var) for var in var_more]
    context.symbol_short = [get_dominant_future(var) for var in var_short]
    context.symbol_do = context.symbol_more + context.symbol_short
    print(context.symbol_do)
    
## 开盘时运行函数
def market_open(context):
 

    ## 清理掉持仓池中的多余合约
    for k in context.portfolio.long_positions.keys():
        if k not in context.symbol_more:
            order_target_value(k, 0, style=None, side='long', pindex=0, close_today=False)

    for k in context.portfolio.short_positions.keys():
        if k not in context.symbol_short:
            order_target_value(k, 0, style=None, side='short', pindex=0, close_today=False)

    if len(context.symbol_do) > 0:
        symbol_money = context.portfolio.total_value/len(context.symbol_do)*context.lever
    
    ## 调整仓位
    for symbol in context.symbol_more:
        order_target_value(symbol, symbol_money, style=None, side='long', pindex=0, close_today=False)
    for symbol in context.symbol_short:
        order_target_value(symbol, symbol_money, style=None, side='short', pindex=0, close_today=False)
        


## 收盘后运行函数
def after_market_close(context):
    pass