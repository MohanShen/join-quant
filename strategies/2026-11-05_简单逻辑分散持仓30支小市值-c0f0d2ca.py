# Clone from JoinQuant
# postId: c0f0d2cab11259c89723191c2a552ac6
# backtestId: a23a2ce7286bd8fe672cbe97cfb9beb6
# title: 简单逻辑分散持仓30支小市值

'''
筛选出市值介于0-30亿的股票，选取其中市值最小的三十只股票，
每天开盘买入，持有五个交易日，然后调仓。
'''

## 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # True为开启动态复权模式，使用真实价格交易
    set_option('use_real_price', True) 
    # 设定成交量比例
    set_option('order_volume_ratio', 1)
    # 股票类交易手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, \
                             open_commission=0.0003, close_commission=0.0003,\
                             close_today_commission=0, min_commission=5), type='stock')
    # 持仓数量
    g.stocknum = 30
    # 交易日计时器
    g.days = 0 
    # 调仓频率
    g.refresh_rate = 5
    g.hold_list = []
    g.yesterday_HL_list = []
    
    # 运行函数
    run_daily(prepare_stock_list, '9:05')
    run_daily(trade, '10:10')
    run_daily(check_limit_up, '14:25')  # 检查持仓中的涨停股是否需要卖出
    run_daily(close_account, '14:55')
    
# 1-1 准备股票池
def prepare_stock_list(context):
    g.hold_list = [position.security for position in context.portfolio.positions.values()]
    # 获取昨日涨停列表
    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        g.yesterday_HL_list = list(df[df['close'] == df['high_limit']]['code'])
    else:
        g.yesterday_HL_list = []
    # 判断今天是否为账户资金再平衡的日期
    g.no_trading_today_signal = today_is_between(context)

## 选出小市值股票
def check_stocks(context):
    
    MKT_index = '399101.XSHE'
    # # MKT_index = '000852.XSHG'# (ZZ1000)
    # MKT_index = '000300.XSHG'# (HS300)
    initial_list = get_index_stocks(MKT_index)
    
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    # 设定查询条件
    
    q = query(
            valuation.code,
            valuation.market_cap
        ).filter(
            valuation.code.in_(initial_list)
        ).order_by(
            valuation.market_cap.asc()
        )

    # 选出低市值的股票，构成buylist
    df = get_fundamentals(q)
    buylist =list(df['code'])

    # 过滤停牌股票
    buylist = filter_paused_stock(buylist)

    return buylist[:g.stocknum]
  
## 交易函数
def trade(context):
    if g.no_trading_today_signal: return
    if g.days%g.refresh_rate == 0:
        ## 选股
        stock_list = check_stocks(context)
        ## 获取持仓列表
        sell_list = list(context.portfolio.positions.keys())
        # 如果有持仓，则卖出
        if len(sell_list) > 0 :
            for stock in sell_list:
                if stock in stock_list: continue
                if stock in g.yesterday_HL_list: continue
                order_target_value(stock, 0)

        ## 分配资金
        if len(context.portfolio.positions) < g.stocknum :
            Num = g.stocknum - len(context.portfolio.positions)
            Cash = context.portfolio.cash/Num
        else: 
            Cash = 0

        # ## 选股
        # stock_list = check_stocks(context)
        hold_list = [position.security for position in context.portfolio.positions.values()]
        ## 买入股票
        for stock in stock_list:
            
            if len(context.portfolio.positions.keys()) < g.stocknum:
                if stock not in hold_list:
                    order_value(stock, Cash)

        # 天计数加一
        g.days = 1
    else:
        g.days += 1

# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

# 辅助函数
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].is_st and 'ST' not in current_data[stock].name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]

def filter_kcbj_stock(stock_list):
    return [stock for stock in stock_list if not (stock.startswith('4') or stock.startswith('8') or stock.startswith('68'))]

def filter_limitup_stock(context, stock_list):
    last_prices = history(1, '1m', 'close', stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions or last_prices[stock][-1] < current_data[stock].high_limit]

def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, '1m', 'close', stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions or last_prices[stock][-1] > current_data[stock].low_limit]

def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if (yesterday - get_security_info(stock).start_date).days >= 375]

def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    return ('04-01' <= today <= '04-30') or ('01-01' <= today <= '01-30')
    # return False
def close_account(context):
    if g.no_trading_today_signal:
        # 清空所有非ETF持仓
        for stock in list(context.portfolio.positions.keys()):
            order_target_value(stock, 0)
            
# 1-4 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    for stock in g.yesterday_HL_list:
        current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
        if current_data['close'][0] < current_data['high_limit'][0]:
            order_target_value(stock, 0)