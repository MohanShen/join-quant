# Clone from JoinQuant
# postId: 0bb616f3649a849dd349680b98d4e0b8
# backtestId: 3fbae017ae4da00d2616d049bffb95f7
# title: 小哥，为嘛我的策略选不到股呢？烦请指导！

# 导入函数库
from jqdata import *
import datetime

def initialize(context):
    # 设置初始资金30万元
    set_option('use_real_price', True)
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    g.cash = 300000
    
    # 设置策略参数
    g.max_stocks = 2  # 最大持仓股票数
    g.stop_profit = 0.03  # 止盈比例3%
    g.stop_loss = -0.02  # 止损比例-2%
    
    # 定时在每天9:50运行选股函数
    run_daily(before_market_open, time='before_open')
    run_daily(market_open, time='09:50')
    run_daily(after_market_close, time='15:00')
    
    # 记录日志
    log.info('策略初始化完成，初始资金: %.2f' % context.portfolio.total_value)

def before_market_open(context):
    # 盘前运行
    pass

def market_open(context):
    # 获取当前时间
    now = context.current_dt
    
    # 卖出持仓股票
    sell_stocks(context)
    
    # 选股并买入
    buy_stocks(context)
    
    # 如果没有持仓，买入逆回购
    if len(context.portfolio.positions) == 0:
        buy_reverse_repo(context)

def after_market_close(context):
    # 盘后运行
    log.info('交易日结束后持仓市值: %.2f' % context.portfolio.total_value)
    record(pos=(context.portfolio.total_value / g.cash - 1) * 100)

def sell_stocks(context):
    # 卖出持仓股票逻辑
    for stock in list(context.portfolio.positions.keys()):
        current_price = get_current_data()[stock].last_price
        cost = context.portfolio.positions[stock].avg_cost
        returns = (current_price - cost) / cost
        
        # 达到止盈或止损条件时卖出
        if returns >= g.stop_profit or returns <= g.stop_loss:
            order_target(stock, 0)
            log.info('卖出股票: %s, 价格: %.2f, 收益率: %.2f%%' % 
                    (stock, current_price, returns * 100))

def buy_stocks(context):
    # 选股逻辑
    stock_list = pick_stocks(context)
    
    # 如果没有选到股票，直接返回
    if len(stock_list) == 0:
        log.info('今日未选到符合条件的股票')
        return
    
    # 计算每只股票分配的资金
    cash_per_stock = context.portfolio.available_cash / min(g.max_stocks, len(stock_list))
    
    # 买入选中的股票
    for stock in stock_list[:g.max_stocks]:
        # 计算可买数量（按100股整数倍）
        current_price = get_current_data()[stock].last_price
        amount = int(cash_per_stock / current_price / 100) * 100
        if amount > 0:
            order(stock, amount)
            log.info('买入股票: %s, 价格: %.2f, 数量: %d' % (stock, current_price, amount))

def pick_stocks(context):
    # 获取当前日期
    now = context.current_dt
    
    # 1. 获取所有股票列表
    all_stocks = get_all_securities(types=['stock'], date=now).index.tolist()
    
    # 2. 过滤ST股票、科创板、8开头的股票
    stocks = [s for s in all_stocks if not is_st_stock(s) 
              and not s.startswith('688') 
              and not s.startswith('8')]
    
    # 3. 获取股票的基本面数据
    q = query(
        valuation.code, valuation.pe_ratio, valuation.circulating_market_cap,
        indicator.inc_net_profit_year_on_year
    ).filter(
        valuation.code.in_(stocks),
        valuation.pe_ratio > 0,
        valuation.circulating_market_cap > 20e8,
        valuation.circulating_market_cap < 100e8
    )
    
    df = get_fundamentals(q, date=now)
    if df.empty:
        return []
    
    # 4. 获取股票的市场数据
    stocks = df['code'].tolist()
    
    # 计算前5日和前10日的涨跌幅
    start_date_5 = now - datetime.timedelta(days=7)  # 多几天确保有5个交易日
    start_date_10 = now - datetime.timedelta(days=14)
    
    prices_5 = get_price(stocks, start_date=start_date_5, end_date=now, fields='close', panel=False)
    prices_10 = get_price(stocks, start_date=start_date_10, end_date=now, fields='close', panel=False)
    
    # 计算涨跌幅
    returns_5 = prices_5.groupby('code')['close'].apply(lambda x: (x.iloc[-1] - x.iloc[0]) / x.iloc[0])
    returns_10 = prices_10.groupby('code')['close'].apply(lambda x: (x.iloc[-1] - x.iloc[0]) / x.iloc[0])
    
    # 过滤前5日涨幅>=10%，前10日涨幅>=10%
    stocks_filtered = returns_5[returns_5 >= 0.10].index.intersection(returns_10[returns_10 >= 0.10].index).tolist()
    
    if not stocks_filtered:
        return []
    
    # 5. 获取竞价涨幅数据
    current_data = get_current_data()
    prev_close = {s: get_price(s, end_date=now - datetime.timedelta(days=1), fields='close', count=1).iloc[-1] for s in stocks_filtered}
    stocks_filtered = [s for s in stocks_filtered 
                      if 0.01 <= (current_data[s].last_price / prev_close[s] - 1) <= 0.03]
    
    if not stocks_filtered:
        return []
    
    # 6. 获取量比和主力净流入数据
    # 注意：JoinQuant可能需要使用其他方式获取这些数据
    # 这里简化处理，假设所有股票都满足量比>0.1和主力净流入>0
    
    # 7. 过滤上市天数>60天
    stocks_filtered = [s for s in stocks_filtered 
                      if (now - get_security_info(s).start_date).days > 60]
    
    # 8. 获取热门板块
    # JoinQuant可能需要使用其他方式获取热门板块数据
    # 这里简化处理，假设所有股票都属于热门板块
    
    return stocks_filtered

def buy_reverse_repo(context):
    # 买入逆回购
    if context.portfolio.available_cash > 1000:
        order_target('204001.XSHG', int(context.portfolio.available_cash / 1000) * 1000)
        log.info('买入逆回购，金额: %.2f' % context.portfolio.available_cash)

def is_st_stock(stock):
    # 判断是否为ST股票
    name = get_security_info(stock).display_name
    return 'ST' in name or '*ST' in name or '退' in name