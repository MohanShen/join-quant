# Clone from JoinQuant
# postId: 838d19b8034c2d7aafdf78831471751d
# backtestId: 22ef07c88780343e5c5e419b93efef30
# title: 悬赏分钟止损

# 导入函数库
import jqdata
import datetime
import talib as tb

# 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    g.stocks = []
    g.buy_count = 3
    g.min_count=0
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
	### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003,
                             close_commission=0.0003, min_commission=5), type='stock')
    run_daily(trade, time='14:50')
    run_daily(sell,time="every_bar")
    
 
def before_trading_start(context):
    select_stocks(context)
    g.min_count = 0


def base_filter(context,stock_list):
    # 过滤器，过滤科创板,停牌,ST，科创，新股
    curr_data = get_current_data()
    stock_list=[stock for stock in stock_list if stock[0:3] not in  ('688','300')] #过滤科创板'688',创业板'300'
    stock_list = [stock for stock in stock_list if not curr_data[stock].is_st]
    stock_list = [stock for stock in stock_list if not curr_data[stock].paused] 
    stock_list = [stock for stock in stock_list if 'ST' not in curr_data[stock].name]
    stock_list = [stock for stock in stock_list if '*'  not in curr_data[stock].name]
    stock_list = [stock for stock in stock_list if '退' not in curr_data[stock].name]
    stock_list = [stock for stock in stock_list if  curr_data[stock].day_open>1]
    stock_list = [stock for stock in stock_list if  (context.current_dt.date()-get_security_info(stock).start_date).days>50]
    print(len(stock_list))
    return stock_list


def boll_filter(context,stocks):
    ret = set()
    # 过去任意7个交易日内，任何一天最高价，超过boll(30)上轨的股票
    df = get_price(stocks, count=120, end_date=context.previous_date, fq=None)
    for code in stocks:
        close = df['close'][code].values
        upper, middle, lower =  tb.BBANDS(close,timeperiod=30,
                    # number of non-biased standard deviations from the mean
                    nbdevup=2,
                    nbdevdn=2,
                    # Moving average type: simple moving average here
                    matype=0)
        
        # 最近七日上轨与收盘价
        upper_7_days = upper[-7:]
        close_7_days = close[-7:]
        for i in range(7):
            if close_7_days[i]>upper_7_days[i]:
                ret.add(code)
                break
        
    return list(ret)
 
  

def select_stocks(context):
    # 流通股小于10亿股，流通市值小于200亿
    stocks = get_fundamentals(
        query(valuation.code).filter(
            valuation.circulating_cap <100000,
            valuation.circulating_market_cap<200
        ).order_by(
            # 按换手率降序排列
            valuation.turnover_ratio.desc()),
        date=context.current_dt)['code'].values
    
    stocks = base_filter(context,stocks)
    stocks = boll_filter(context,stocks)
    g.stocks = stocks
    print("筛选到股票数量：" + str(len(g.stocks)))
    

    
def get_turnover_ratio(stocks,now_time):
    '''传入股票池,时间,返回实时换手率'''
    if isinstance(stocks, str):
        stocks = [stocks]
    if isinstance(now_time, str):
        now_time =datetime.datetime.strptime(now_time,'%Y-%m-%d %H:%M:%S')
    data = get_price(stocks,fields='volume',end_date=now_time,start_date=now_time.date(),frequency ='1m' ).volume.sum()
    
    valuation_data = get_fundamentals(query(         #财务数据可以一天获取一次,自行更改
                            valuation.code,valuation.circulating_cap    
                            ).filter(valuation.code.in_(stocks)),date=now_time).set_index('code')
    return data/valuation_data.iloc[:,0]/100


def sell(context):
    for stock in context.portfolio.positions:
      avg_cost = context.portfolio.positions[stock].avg_cost  #持仓股票的平均成本
      current_price = context.portfolio.positions[stock].price  #持仓股票的当前价
      if current_price>avg_cost*1.05 or current_price<avg_cost*0.95:
        order_target(stock, 0)



def trade(context):
    if g.stocks:
        curr_data = get_current_data()
        # 今昨日大盘跌50点，不买
        if curr_data['000001.XSHG'].day_open - curr_data['000001.XSHG'].last_price >50:
            return
        
        h = attribute_history('000001.XSHG', 1, '1d', ('open','close'))
        if h['open'][-1]-h['close'][-1]>50:
            return
        
        df = get_price(g.stocks, count=60, end_date=context.previous_date, fq=None)
        turnover_ratio = get_turnover_ratio(g.stocks,context.current_dt)
        for code in g.stocks:
            log.info("*"*88)
            log.info("当前代码：%s"%code)
            close = df['close'][code].values
            upper, middle, lower =  tb.BBANDS(close,timeperiod=30,
                                              # number of non-biased standard deviations from the mean
                                              nbdevup=2,
                                              nbdevdn=2,
                                              # Moving average type: simple moving average here
                                              matype=0)
            
            ema_12 = tb.EMA(close,12)
            # 最新价格在额ema12 1%波动
            if not (curr_data[code].last_price > ema_12[-1]*0.99 and curr_data[code].last_price < ema_12[-1]*1.01):
                log.info("不满足最新价格在额ema12 1%波动")
                log.info("last_price:%s,ema_12:%s"%(curr_data[code].last_price,ema_12[-1]))
                continue
                
            if turnover_ratio[code]>3:
                log.info("不满足换手率小于3")
                log.info("当前换手率：%s"%turnover_ratio[code])
                continue
                
            if ema_12[-1]<middle[-1]:
                log.info("ema12小于中轨")
                continue
            
            all_cash = context.portfolio.available_cash
            
            if code in context.portfolio.positions:
                continue
            
            if len(context.portfolio.positions)>=g.buy_count:
                log.info("仓位已满，暂不买入其他股票")
                return
            
            cash = all_cash/(g.buy_count-len(context.portfolio.positions))
            order_value(code, cash)
            