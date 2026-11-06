# Clone from JoinQuant
# postId: 31eb59d118cd583abad6f0e57d303ed7
# backtestId: 2124eafd4769210624ad77009e018390
# title: 红利PEG小市值周轮

#导入函数库
from jqdata import *
from jqfactor import get_factor_values
import numpy as np
import pandas as pd

#初始化函数 
def initialize(context):
    set_benchmark('000905.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    # 将滑点设置为0.005
    set_slippage(FixedSlippage(0.005))
    # 设置交易成本万分之三
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),type='fund')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    #选股参数
    g.ZT=[]
    g.high_limit_list = []
    g.just_sold = []  # 涨停破板卖出后，避免当日回补重复买入
    g.stock_num = 10 #持仓数
    g.up_price = 50.0 #低价股上限
    # 设置交易时间，每天运行
    run_daily(prepare_stock_list, time='9:15') #每日9:15跑一次股票池
    run_weekly(my_trade, 1, time='9:35')
    run_daily(check_limit_up, time='14:00') #每日14:00检查持仓涨停，破板即卖并同日补仓买入
    run_daily(print_trade_info, time='15:30')

#2-1 选股模块
def get_factor_filter_list(context,stock_list,jqfactor,sort,p1,p2):
    yesterday = context.previous_date
    score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
    df = pd.DataFrame(columns=['code','score'])
    df['code'] = stock_list
    df['score'] = score_list
    df.dropna(inplace=True)
    df.sort_values(by='score', ascending=sort, inplace=True)
    filter_list = list(df.code)[int(p1*len(stock_list)):int(p2*len(stock_list))]
    return filter_list

# ============ 选股逻辑分界 ============
#2-2 选股模块（移植：股息率前25% + PEG(-3,3) + 总市值升序小市值）
def get_stock_list(context):
    """
    选股：全市场 -> 次新(250日)/科创北交 -> 股息率前25% -> PEG(-3,3)且市值升序
          -> ST/停牌/涨跌停/高价(<=g.up_price) 过滤 -> 取 g.stock_num
    """
    dt_last = context.previous_date
    initial_list = get_all_securities('stock', dt_last).index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    # 股息率前25%
    initial_list = get_dividend_ratio_filter_list(context, initial_list, False, 0, 0.25)
    # PEG(-3,3) 并按市值升序
    initial_list = get_peg(context, initial_list)
    # 常规过滤
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    initial_list = filter_highprice_stock(context, initial_list)
    final_list = initial_list[:g.stock_num]
    print('初选候选股票:{}'.format(final_list))
    return final_list



#3-1 过滤模块-过滤停牌股票
#输入选股列表，返回剔除停牌股票后的列表
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

#3-2 过滤模块-过滤ST及其他具有退市标签的股票
#输入选股列表，返回剔除ST及其他具有退市标签股票后的列表
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]

#3-3 过滤模块-过滤涨停的股票
#输入选股列表，返回剔除未持有且已涨停股票后的列表
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    # 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]

#3-4 过滤模块-过滤跌停的股票
#输入股票列表，返回剔除已跌停股票后的列表
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]

#3-5 过滤模块-过滤科创板北交所
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list

#3-6 过滤次新股
#输入股票列表，返回剔除上市日期不足250日股票后的列表
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=250)]

#3-6.5 过滤高价股（排除股价高于 g.up_price 的非持仓股；源策略注释写<9元，代码误用10000，此处用可配参数）
def filter_highprice_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] <= g.up_price]

#4-1 交易模块
def my_trade(context):  
    g.just_sold = []  # 每周重置，避免破板卖出标记无限膨胀
    #获取选股列表并过滤掉:st,st*,退市,涨停,跌停,停牌  
    check_out_list = get_stock_list(context)  
    check_out_list = filter_limitup_stock(context, check_out_list)  
    check_out_list = filter_limitdown_stock(context, check_out_list)  
    check_out_list = filter_paused_stock(check_out_list)  
    #check_out_list = filter_highprice_stock(context,check_out_list)
    buy_stocks = check_out_list[:g.stock_num]  
    print('今日自选股:{}'.format(buy_stocks))  

    for stock in list(context.portfolio.positions.keys()):
        if stock not in buy_stocks:
            df2=attribute_history(stock,count=2,unit='1d',\
                          fields=['open','close','volume','high','low','money','high_limit','low_limit','paused'],\
                          fq='pre')
            if (df2['close'][-1]==df2['high_limit'][-1] and df2['volume'][-1]>0 and df2['money'][-1]>0):
                g.high_limit_list.append(stock)
            else:
                order_target_value(stock, 0) 
  
    # 根据股票数量分仓  
    # 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配  
    position_count = len(context.portfolio.positions)  
    if g.stock_num > position_count:  
        value = context.portfolio.cash / (g.stock_num - position_count)  
        for stock in buy_stocks:  
            if context.portfolio.positions[stock].total_amount == 0:  
                order_target_value(stock, value)

# 准备股票池
def prepare_stock_list(context):
    #获取已持有列表
    g.high_limit_list = []
    hold_list = list(context.portfolio.positions)
    if hold_list:
        panel = get_price(hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'],
                       count=1)

        df_close = panel['close'].T
        df_close.columns = ['close']
        print(df_close)
        df_high_limit = panel['high_limit'].T
        df_high_limit.columns = ['high_limit']
        print(df_high_limit)
        df = pd.concat([df_close, df_high_limit] ,axis=1)
        print(df)
        g.high_limit_list = df[df['close'] == df['high_limit']].index.tolist()
        
#  调整昨日涨停股票
def check_limit_up(context):
     # 获取持仓的昨日涨停列表
    current_data = get_current_data()
    if g.high_limit_list:
        for stock in g.high_limit_list:
            if current_data[stock].last_price < current_data[stock].high_limit:
                log.info("[%s]涨停打开，卖出" % stock)
                order_target(stock, 0)
                g.just_sold.append(stock)
                buy_after_high_limit_sell(context)  # 破板当日同报复性买入
            else:
                log.info("[%s]涨停，继续持有" % stock)

# 涨停破板卖出后，同日重新计算候选池并补齐仓位（移植自源策略 buy_after_high_limit_sell）
def buy_after_high_limit_sell(context):
    position_count = len(context.portfolio.positions)
    if g.stock_num > position_count and position_count != 0:  # !=0 避免首次运行代替 my_trade 买入
        choice = get_stock_list(context)
        psize = context.portfolio.available_cash / (g.stock_num - position_count)
        for s in choice:
            if s not in context.portfolio.positions and s not in g.just_sold:
                log.info('涨停卖出后的买入:{}'.format(s))
                order_target_value(s, psize)
                if len(context.portfolio.positions) == g.stock_num:
                    break
#5-1 复盘模块-打印
#打印每日持仓信息
def print_trade_info(context):
    #打印当天成交记录
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：'+str(_trade))
    #打印账户信息
    for position in list(context.portfolio.positions.values()):
        securities=position.security
        cost=position.avg_cost
        price=position.price
        ret=100*(price/cost-1)
        value=position.value
        amount=position.total_amount    
        print('代码:{}'.format(securities))
        print('成本价:{}'.format(format(cost,'.2f')))
        print('现价:{}'.format(price))
        print('收益率:{}%'.format(format(ret,'.2f')))
        print('持仓(股):{}'.format(amount))
        print('市值:{}'.format(format(value,'.2f')))
        print('———————————————————————————————————')
    print('———————————————————————————————————————分割线————————————————————————————————————————')


# ===== 以下为专属选股辅助函数 =====

#1-1 根据最近一年分红除以当前总市值计算股息率并筛选
def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365)
    # 获取分红数据，由于 finance.run_query 最多返回4000行，按 interval 拆分查询再组合
    interval = 1000
    list_len = len(stock_list)
    q = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.a_registration_date,
        finance.STK_XR_XD.bonus_amount_rmb
    ).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)
    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(
                finance.STK_XR_XD.code,
                finance.STK_XR_XD.a_registration_date,
                finance.STK_XR_XD.bonus_amount_rmb
            ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[interval*(i+1):min(list_len,interval*(i+2))]))
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    dividend = df.fillna(0)
    dividend = dividend.set_index('code')
    dividend = dividend.groupby('code').sum()
    temp_list = list(dividend.index)
    # 获取市值相关数据
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1)
    cap = cap.set_index('code')
    # 计算股息率
    DR = pd.concat([dividend, cap], axis=1, sort=False)
    DR['dividend_ratio'] = (DR['bonus_amount_rmb']/10000) / DR['market_cap']
    # 排序并筛选
    DR = DR.sort_values(by=['dividend_ratio'], ascending=sort)
    final_list = list(DR.index)[int(p1*len(DR)):int(p2*len(DR))]
    return final_list

# 按 PEG 过滤并按总市值升序返回（小市值优先）
def get_peg(context, stocks):
    q = query(
        valuation.code,
        valuation.pe_ratio / indicator.inc_net_profit_year_on_year,  # PEG
        indicator.roe / valuation.pb_ratio,  # PB-ROE
        indicator.roe,
    ).filter(
        valuation.pe_ratio / indicator.inc_net_profit_year_on_year > -3,
        valuation.pe_ratio / indicator.inc_net_profit_year_on_year < 3,
        valuation.code.in_(stocks))
    df_fundamentals = get_fundamentals(q, date=None)
    stocks = list(df_fundamentals.code)
    df = get_fundamentals(query(valuation.code).filter(valuation.code.in_(stocks)).order_by(valuation.market_cap.asc()))
    choice = list(df.code)
    return choice
    
'''
选股逻辑

全市场 → 剔次新(250日) / 剔科创北交(4/8/68)
股息率前 25%（近 365 天分红 ÷ 昨日总市值）
PEG 过滤 |PE÷净利同比| < 3，再按总市值升序（小市值优先）
过 ST / 停牌 / 涨跌停 / 高价
取最小的10 只
交易

持仓不在候选 → 卖；空仓等权买入
涨停破板（14:00）：卖出后当日同补
本质：高股息 + 低 PEG + 极小市值的周度价值轮动，附涨停破板换。
'''
