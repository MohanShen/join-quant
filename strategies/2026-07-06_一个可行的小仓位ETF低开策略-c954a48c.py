# Clone from JoinQuant
# postId: c954a48c4d83e06a85c1d11b39f8bfb0
# backtestId: 1ad70fac95721c387ec9e2dae4958222
# title: 一个可行的小仓位ETF低开策略

import pandas as pd

def initialize(context):
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    # 设置日志级别
    log.set_level('order', 'error')
    # 避免使用未来数据
    set_option("avoid_future_data", True)
    # 使用真实价格
    set_option('use_real_price', True)
    
def handle_data(context, data):
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    if hour == 14 and minute == 55: #40分卖出符合条件的
        adjust_position(context)
    if hour == 9 and minute == 30: #45分买入
        adjust_position0(context)

def adjust_position(context):
    # 获取所有ETF基金
    all_fund = get_all_securities(['etf'], context.previous_date)
    funds = all_fund.index.tolist()
    # 流动性过滤
    hm = history(5, '1d', 'money', funds).min()
    funds = hm[hm > 1e7].index.tolist()
    current_data = get_current_data()
     # 存储每个基金的计算数据
    fund_data = []
    
    for fund in funds:
        h = attribute_history(fund, 2, '1d', ('close','open','high','low','high_limit','low_limit'))
        fund_current = current_data[fund]
        last_price = fund_current.last_price
        day_open = fund_current.day_open
        # 取前一天的收盘价（历史数据中最后一条）
        prev_close = h['close'][-1]
        # 计算低开比例
        price_ratio = last_price / prev_close
        # 存储到列表
        fund_data.append({
            'fund': fund,
            'price_ratio': price_ratio
        })
    
    # 存储到全局变量
    nchoice = 1
    
    df = pd.DataFrame(fund_data)
    df = df.set_index('fund')  # 以基金代码为索引
    
    # 按价格低开比例排序
    df = df.sort_values('price_ratio', ascending=True).head(nchoice)
    choice = df.index.tolist()
    # 卖出
    for s in context.portfolio.positions:
        if s not in choice and not current_data[s].paused:
            order_target_value(s, 0)

def adjust_position0(context):
    # 获取所有ETF基金
    all_fund = get_all_securities(['etf'], context.previous_date)
    funds = all_fund.index.tolist()
    # 流动性过滤
    hm = history(5, '1d', 'money', funds).min()
    funds = hm[hm > 1e7].index.tolist()
    
    price_ratios = {}  # 存储基金代码:价格比例的字典
    current_data = get_current_data()
    for fund in funds:
        # 逐个获取基金的2天历史价格（仅需close字段）
        fund_price_history = attribute_history(fund, 2, '1d', 'close')
        
        # 获取昨天的收盘价和昨天的跌停价
        yesterday_close = fund_price_history['close'][-1]
        yesterday_low_limit = yesterday_close * 0.9
        
        # 获取今天的开盘价和今天的跌停价
        fund_current = current_data[fund]
        today_open = fund_current.day_open
        today_low_limit = fund_current.low_limit
        
        # 过滤条件：昨天收盘价不能是跌停价，且今天开盘价不能是跌停价
        if abs(yesterday_close - yesterday_low_limit) < 1e-6 or abs(today_open - today_low_limit) < 1e-6:
            continue  # 不满足条件，跳过该基金
        
        # 获取前一天的收盘价（假设[-1]是最新的历史数据，即前一天收盘价）
        prev_close = fund_price_history['close'][-1]
        day_open = current_data[fund].day_open
        # 获取当前价格
        last_price = current_data[fund].last_price
        # 计算当前价格/前一天收盘价的比例
        ratio = day_open / prev_close
        price_ratios[fund] = ratio
    
    df = pd.DataFrame(list(price_ratios.items()), columns=['fund', 'price_ratio'])
    df = df.set_index('fund')  # 以基金代码为索引
    # 按比例升序排序（低开比例小的在前），取前nchoice个
    nchoice = 1
    df = df.sort_values('price_ratio', ascending=True).head(nchoice)
    choice = df.index.tolist()  # 最终选择的基金列表
    
    # 配置资金
    for s in choice:
        position_count = len(context.portfolio.positions)
        if nchoice > position_count:
            value = context.portfolio.cash / (nchoice - position_count)
            if s not in context.portfolio.positions:
                order_target_value(s, value)
# end