# Clone from JoinQuant
# postId: 5e874b5b8c431d3ff4054da2b7b66352
# backtestId: 28ddb2103f08007e65eab6038c08d90c
# title: 低开小市值，年化105%，最大回撤20%


import math

from jqdata import *
import pandas as pd

def initialize(context):
    log.set_level('order', 'warning')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.002))
    set_commission(PerTrade(buy_cost=0.0002, sell_cost=0.0007, min_cost=5))
    set_benchmark('399303.XSHE')
    g.avoid_months = [1, 4]	 # “规避的月份”，不持仓的月份
    g.choice = 969
    g.target_count = 5



def after_code_changed(context):

    unschedule_all() # 取消所有定时运行
    # 设置交易时间，每天运行
    run_daily(my_trade, time='9:27', reference_security='399303.XSHE')  # 为模拟盘做准备，提前收到调仓信息
    # 在9:40检查持仓并卖出
    run_daily(sell_at_9_40, time='11:30', reference_security='399303.XSHE')
    # 在14:50检查持仓盈利情况并止盈
    run_daily(stop_profit_at_14_50, time='14:50', reference_security='399303.XSHE')


def filter_specials(context, stock_list):
    # type: (Context, int) -> list
    """
    过滤掉：1）三停：涨停、跌停、停牌；2）三特：st, *st, 退；3）科创、创业; 4）次新；
    适用于开盘前选股，如果是盘中，用curr_data[security].last_price替代curr_data[stock].day_open

    """
    curr_data = get_current_data()
    stock_list = [stock for stock in stock_list if not (
            (curr_data[stock].day_open == curr_data[stock].high_limit) or  # 涨停开盘
            (curr_data[stock].day_open == curr_data[stock].low_limit) or  # 跌停开盘
            curr_data[stock].paused or  # 停牌
            curr_data[stock].is_st or  # ST
            # ('ST' in curr_data[stock].name) or
            # ('*' in curr_data[stock].name) or
            ('退' in curr_data[stock].name) or
            #(stock.startswith('300')) or  # 创业
            (stock.startswith('688'))  # 科创
    )]
    #
    return stock_list



def get_stocks(context):
    fundamentals_data = get_fundamentals(
        query(valuation.code, valuation.market_cap).order_by(valuation.market_cap.asc()).limit(g.choice))
    stock_pool = list(fundamentals_data['code'])
    stock_pool = filter_specials(context, stock_pool)
    return stock_pool

def my_trade(context):
    if context.current_dt.month in g.avoid_months:
        return False
    data_today = get_current_data()
    position_count = len(context.portfolio.positions)

    # 检查可用资金是否少于总资金的10%
    total_value = context.portfolio.total_value
    available_cash = context.portfolio.available_cash
    if available_cash < total_value * 0.5 / g.target_count:
    # if available_cash < total_value * 0.1:
        log.info("可用资金不足买入一份股票，跳过买入")
        return
    target_list = get_stocks(context)
    preselected_count = g.target_count- position_count  # 预选数量
    # 选股  昨日收盘价大于五日收盘均价 且 昨日最低大于今天开盘价，卖出是第二天无条件卖出。
    
    buy_stocks = []
    for s in target_list:
        # if position_count + len(buy_stocks) >= g.target_count:
        #     break

        df = attribute_history(security=s, 
                                count=15, 
                                unit='1d', 
                                fields= ('close', 'low', 'high', 'paused','high_limit'), 
                                skip_paused=False, 
                                df=False, 
                                fq='pre')
        if (max(df['paused'][-5:]) == 0):  # 过去5天没有停盘
            if df['close'][-1] == df['high_limit'][-1]:
                continue
            today_open = data_today[s].day_open
            prev_close = df['close'][-1]
            prev_low = df['low'][-1]
            chg = (today_open - prev_close) / prev_close * 100  # 计算开盘时跌幅

            if prev_close > min(df['close']) * 1.40:
                continue
            if today_open < prev_low and chg < -0.75:
                low = min(df['low'][-4:])
                high = max(df['high'][-4:])
                precent = (high - low) / low * 100  # 计算4天振幅
                if (precent <= 20):
                    ma = mean(df['close'][-5:])
                    if (prev_close > ma) and s not in context.portfolio.positions:
                        buy_stocks.append(s)
        if len(buy_stocks) >= preselected_count*2:
            break  

    # # 按选股数分配资金买入
    target_num = len(buy_stocks)
    valid_stocks = []
    if buy_stocks:    # 有需要买入的股票
        ticks = get_current_tick(security=buy_stocks)
        for stock,tick in ticks.items():
            money = tick['a1_p'] * tick['a1_v'] * 100
            if money > 5e4:
                valid_stocks.append([stock,money])
        if not valid_stocks:
            return False
        # 按 money（即子列表的第二个元素）升序排序
        valid_stocks.sort(key=lambda x: x[1], reverse=True)

        # 提取出排序后的 stock 列表
        sorted_stock_list = [item[0] for item in valid_stocks]     
                
        buy_stocks = sorted_stock_list[: preselected_count]       
        # 初始化消息，因未开盘，返回是昨天的收盘价，为了一致，直接返回当天的开盘价
        msg = '类别|代 码\t|名称\t|成交价|数量'
        target_num = max(len(buy_stocks),g.target_count-len(context.portfolio.positions))
        value = context.portfolio.available_cash / target_num
        for stock in buy_stocks:
            open_position(context, stock, value)
            price = get_current_data()[stock].day_open

            bs = '买入'
            name = get_security_info(stock).display_name
            filled_price = price  # 按开盘价
            filled_amount = int(value/price/100)*100
            
            # 严格保持与表头一致的格式：保留空格和 \t
            record = f'\n{bs}|{stock[:6]}\t|{name}\t|{filled_price:.2f} |{filled_amount}'
            msg += record  # 将每条记录追加到 msg，用换行符分隔
    
       
        # log.info(msg)   # 所有内容合并完成后，只打印一次
        send_message(msg)
    else:
        g.stock_pool = []


# 9:40检查持仓并卖出
def sell_at_9_40(context):
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        if position.closeable_amount < 200:
            continue

        data_today = get_current_data()
        today_open = data_today[stock].day_open
        last_price = data_today[stock].last_price
        # 如果最新价低于开盘价，则卖出
        if last_price < today_open:  
            close_position(stock)

# 14:50检查持仓盈利情况并止盈
def stop_profit_at_14_50(context):
    for stock,position in context.portfolio.positions.items():
        if position.closeable_amount < 200:
            continue
        curr_data = get_current_data()
        last_price = curr_data[stock].last_price
        # 如果股票涨停，则保留
        if last_price == curr_data[stock].high_limit:
            log.info(f"股票 {stock} 已涨停，保留到第二天处理")
            continue
        # 如果股票未涨停，则继续检查止盈条件
        cost_basis = position.avg_cost # 成本价
        profit_percent = (last_price - cost_basis) / cost_basis * 100  # 盈利百分比
        # 如果盈利达到5%，则卖出
        if profit_percent >= 5:
            close_position(stock)

# 3-1 交易模块-自定义下单
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s %4s" % (security,get_security_info(security).display_name))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)  # ,MarketOrderStyle(get_current_data()[security].last_price)

# 3-2 交易模块-开仓
def open_position(context,security, value):
    _order = order_target_value_(security, value)
    if _order is not None and _order.filled > 0:
        return True
    return False

# 3-3 交易模块-平仓
def close_position(security):
    _order = order_target_value_(security, 0)  # 可能会因停牌失败
    if _order is not None:
        if _order.status == OrderStatus.held and _order.filled == _order.amount:
            return True
    return False
    

# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# research/harness.md §2 — force zero slippage + frozen commission regardless of
# what the raw strategy sets, even if it re-sets costs every bar.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
except NameError:
    pass
# ===== END OVERRIDE =====
