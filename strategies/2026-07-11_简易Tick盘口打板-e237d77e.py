# Clone from JoinQuant
# postId: e237d77ed5761e4b2e6c972ce36b2148
# backtestId: 53fc764a741539bdbf134c3b7e3d220e
# title: 简易Tick盘口打板

from jqdata import *
import numpy as np
import pandas as pd

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    g.initial_price = context.portfolio.available_cash
    g.num = 0
    g.cash = 0
def before_trading_start(context):
    g.take_stock = []
    g.take_stock = market_value(context)
    
    if g.num ==0:
        g.cash = (g.initial_price / 10)
        g.num += 1
    subscribe(g.take_stock,'tick')

def handle_tick(context, tick):
    today_date = context.current_dt.date()
    hour_time = context.current_dt.hour
    min_time = context.current_dt.minute
    if hour_time > 13 and min_time > 30:
        if context.portfolio.positions > 0:
            for stock in context.portfolio.positions:
                build_date = context.portfolio.positions[stock].init_time.date()
                sell_to = today_date != build_date
                if sell_to:
                    order_target(stock, 0)
                    if stock not in context.portfolio.positions:
                        log.info('卖出股票:' + str(stock))
    
    stock = tick['code']
    current_data = get_current_data()
    limit_high = current_data[stock].high_limit
    now_peice = current_data[stock].last_price
    if now_peice != limit_high:
    
        sell_5 = tick['a5_p']
        sell_4 = tick['a4_p']
        sell_3 = tick['a3_p']
        sell_2 = tick['a2_p']
        sell_1 = tick['a1_p']
        if limit_high == sell_3 or limit_high == sell_2:
            if stock not in context.portfolio.positions:
                current_data = get_current_data()
                new_peice = current_data[stock].last_price
                if context.portfolio.available_cash > g.cash: 
                    if g.cash > new_peice*100:
                        order_count = (int(g.cash // (new_peice*100))) * 100
                        order_target(stock, order_count)
                        if stock in context.portfolio.positions:
                            log.info('买入股票:' + str(stock) +', 金额:'+ str(int(new_peice*order_count)))
            



def market_value(context):
    pass_stocks = []
    str_ndate = context.current_dt.strftime('%Y-%m-%d')
    now_date = datetime.datetime.strptime(str_ndate, '%Y-%m-%d')
    df = get_fundamentals(query(
          valuation.code, valuation.market_cap, valuation.pe_ratio, income.total_operating_revenue
      ).filter(
          valuation.market_cap < 70,
          valuation.pe_ratio < 50,
      ).order_by(
          # 按市值降序排列
          valuation.market_cap.desc()
      ).limit(
          # 最多返回100个
          100
      ), date= now_date)
      
    for stock in list(df['code']):
        current_data = get_current_data()
        if not current_data[stock].is_st:
            pass_stocks.append(stock)
    return pass_stocks    




def after_trading_end(context):
    unsubscribe_all()
    
    




