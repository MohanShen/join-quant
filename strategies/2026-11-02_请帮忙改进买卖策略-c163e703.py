# Clone from JoinQuant
# postId: c163e7032a0fb60a784b60eee43318e6
# backtestId: 9a3bacdefde4d154d50c5f547b6fe9dd
# title: 请帮忙改进买卖策略

import json
from jqdata import *

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    
    
    g.stock_pool = []
    g.stocks_to_sell = []
    g.stocks_bought_today = []
    g.limit_up_days = {}  # 记录涨停天数
    g.order_info_dict = {}  # 记录订单信息    
    g.failed_to_sell_stocks = []  # 记录未能卖出的股票
    g.purchase_dates = {}  # 记录股票购买日期
    
    run_daily(before_market_open, time='9:05', reference_security='000300.XSHG')
    run_daily(market_open, time='9:30', reference_security='000300.XSHG')
    run_daily(market_close, time='14:55', reference_security='000300.XSHG')
  
# 开盘前运行的函数
def before_market_open(context):
    
    # 将昨天购买和涨停的股票添加到今天要卖出的股票列表中
    g.stocks_to_sell = g.stocks_bought_today.copy() + list(g.limit_up_days.keys())
    g.stocks_bought_today = []  # 清空今天购买的股票列表
    g.limit_up_days = {}  # 清空涨停天数字典
    
    content = read_file('20202021.json')
    stock_pool_dict = json.loads(content)
    today_date = context.current_dt.strftime('%Y-%m-%d')
    if today_date in stock_pool_dict.keys():
        g.stock_pool = stock_pool_dict[today_date]['\u6a21\u578b10']
        log.info('今日股票池为:', g.stock_pool)
    
    # 尝试再次卖出之前因跌停而未能卖出的股票
    for stock in g.failed_to_sell_stocks:
        if stock in context.portfolio.positions:
            g.stocks_to_sell.append(stock)
    g.failed_to_sell_stocks = []

def market_open(context):
    if g.stock_pool:
        cash_per_stock = min(context.portfolio.total_value / 6, context.portfolio.available_cash / len(g.stock_pool))
        for stock in g.stock_pool:
            if open_position(stock, cash_per_stock): # 检查是否成功买入
                log.info('买入个股:{}, 买入价格:{}, 买入数量:{}'.format(stock, context.portfolio.positions[stock].avg_cost, context.portfolio.positions[stock].total_amount))
                g.stocks_bought_today.append(stock) # 更新今天购买的股票列表
                g.purchase_dates[stock] = context.current_dt  # 记录购买日期

def market_close(context):
    for stock in list(g.stocks_to_sell):
        if stock not in context.portfolio.positions:  # 检查是否持有此股票
            g.stocks_to_sell.remove(stock)
            continue
        current_price = get_current_data()[stock].last_price
        prev_close_price = get_price(stock, end_date=context.previous_date, count=1, frequency='daily')['close'][0]
        if current_price >= prev_close_price * 1.1:
            if stock in g.limit_up_days:
                g.limit_up_days[stock] += 1
            else:
                g.limit_up_days[stock] = 1
            log.info('涨停，明日再卖出个股:{}'.format(stock))
        else:
            close_position(context.portfolio.positions[stock])
            # 检查股票是否仍在持仓中
            if stock in context.portfolio.positions:
                g.failed_to_sell_stocks.append(stock)  # 添加到未能卖出的股票列表
                log.info('未能卖出股票:{}'.format(stock))
            else:
                purchase_date = g.purchase_dates.get(stock, context.current_dt)
                holding_days = (context.current_dt - purchase_date).days  # 计算持有天数
                log.info('已卖出个股:{}, 买入价格:{}, 卖出价格:{}, 涨停天数:{}, 持有天数:{}'.format(stock, context.portfolio.positions[stock].avg_cost, current_price, g.limit_up_days.get(stock, 0), holding_days))
                g.stocks_to_sell.remove(stock)
                if stock in g.purchase_dates:
                    del g.purchase_dates[stock]  # 移除已卖出股票的购买日期记录


# 订单执行函数
def order_target_value_(security, value):
    order = order_target_value(security, value)
    return order

def open_position(security, value):
    order = order_target_value_(security, value)
    if order is not None and order.filled > 0:
        return True
    return False

def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order is not None:
        return True
    return False
