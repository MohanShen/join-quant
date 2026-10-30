# Clone from JoinQuant
# postId: 142b8551cdd934ebfe5ab34a9d58aee2
# backtestId: 8144cafaf0cd7bbd5c2df51d23aa0f28
# title: 本地库函数调用问题

# 克隆自聚宽文章：https://www.joinquant.com/post/44932
# 标题：主力资金净流入策略
# 作者：silvatree

# 导入函数库
from jqdata import *
import talib
#股票池：选择DIFF小于0 MACD大于0的股票 按DIFF从小到大取前500
#从股票池中获取连续3日每天资金金流入大于50小于1000的个股
#选前5个买入

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
    
    g.stock_pool = [] #盘前选股票池

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：平安银行（g.为全局变量）
    g.security = '000001.XSHE'

    g.stock_pool = do_select(context)
    print('资金净流入：', g.stock_pool)

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    open_position(context, g.stock_pool)
    
#开仓
def open_position(context, codes):
    #次日全平仓
    long_positions_dict  = context.subportfolios[0].long_positions
    for position in list(long_positions_dict.values()):
        code = position.security
        #还在买入名单，则忽略
        if code in codes:
            continue
        #if position.price > (position.avg_cost * 1.1) or position.price < (position.avg_cost * 0.8): #盈利20%才卖
            # log.info('========= code: ', code, ' profit: ', round((position.price/position.avg_cost - 1) * 100, 2))
        _order = order_target(code, 0)  # 可能会因停牌或跌停失败
   
    #每天换股分仓买入
    if len(codes) > 0:
        if len(codes) > 5:
            codes = codes[:5]
        # print('待买入：', codes)
        cash = context.portfolio.available_cash
        cash_per_code = cash / len(codes)
        for code in codes:
            order_value(code, cash_per_code)


# --------------------- 选股 ------------------------------------
# 过滤停牌、退市、ST股票、涨停、跌停
def filter_specials(stock_list):
    curr_data = get_current_data()
    stock_list = [stock for stock in stock_list if \
                  (not curr_data[stock].paused)  # 未停牌
                  and (not curr_data[stock].is_st)  # 非ST
                  and ('ST' not in curr_data[stock].name)
                  and ('*' not in curr_data[stock].name)
                  and ('退' not in curr_data[stock].name)
                  and (not stock.startswith('688'))
                  and (curr_data[stock].low_limit < curr_data[stock].day_open < curr_data[stock].high_limit)  # 未涨跌停
                  ]

    return stock_list

def do_select(context):
    
    #stockpool = get_index_stocks(index)
    stockpool = list(set(get_all_securities(types=['stock']).index))
    
    
    #stockpool = list(stock_to_choose['code'])
    log.info('选出股票只数: %d' % len(stockpool))

    # 过滤停牌、退市、ST股票、涨停、跌停
    stockpool = filter_specials(stockpool)
    cur_dt = str(context.current_dt.date())

    count=180
    freq='1d'
    datas = get_bars(stockpool, count=count, unit=freq, fields=['date','open','low','high','close','volume'],  include_now=False, end_dt=cur_dt)
    stock_pool = []
    

    for code in datas:
        data = datas[code]
        
        if (len(data) < count):
            continue
        
        dif, dea, bar = talib.MACD(data['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        if dif[-1] < 0 and bar[-1] > 0:
            stock_pool.append({'code':code, 'dif':dif[-1], 'macd': bar[-1], 'close':data['close'][-1]})

    if len(stock_pool) == 0:
        return []
    #stock_pool.sort(key=lambda x:x['dif']) #dif升序排列
    stock_pool.sort(key=lambda x:x['dif'], reverse=True) #dif降序排列
    df = pd.DataFrame(stock_pool)
    codes = list(df['code'])
    
    
    #获取近3日净流入
    count = 4
    fields = ["date", "sec_code", "change_pct", "net_amount_main", "net_pct_l"]
    
    df_money = get_money_flow(codes, start_date=None, end_date=cur_dt, fields=fields, count=count)
    buy_pool = [] #连续3日每日主力资金净流入介于50到1000之间
    for code in codes:
         #df[df['sec_code']==code]['net_amount_main']
        df2 = df_money[df_money['sec_code']==code]
        money_flow = True
        for i in range(len(df2)):
            #每日主力净流入50到1000万
            money_flow = money_flow and (df2.iloc[i]['net_amount_main'] > 50) and ((df2.iloc[i]['net_amount_main'] < 1000))
        #print(money_flow)
        if money_flow:
            buy_pool.append(code)
    
    return buy_pool
    


## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
