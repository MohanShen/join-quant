# Clone from JoinQuant
# postId: 92dbf9aafae2d1952f104b02f969dc33
# backtestId: 1b887fbce0b7d072402009ed171c94de
# title: (小市值-白马-ETF组合)挺火的，模拟运行了半年多...

# 克隆自聚宽文章：https://www.joinquant.com/post/1399
# 标题：【量化课堂】多因子策略入门
# 作者：JoinQuant量化课堂

"""
三种策略集合在一起，便于模拟
策略1：小市值策略
策略2：白马攻防策略
策略3：ETF轮动策略

需完善点1：缺少涨停股票卖出后，调整期内剩余资金处理部分
"""
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time, datetime, timedelta
from jqdata import finance

def initialize(context):
    set_backtest()         # 设置回测条件
    set_params(context)    # 设置参数
    
    # 过滤日志
    log.set_level('order', 'error')
    
    # 子策略执行计划  
    if g.portfolio_value_proportion[0] > 0:  # 小市值策略
        run_weekly(xsz_get_stock_list, 2, '9:05') 
        run_weekly(xsz_adjustment, 2, '10:00')
        
    if g.portfolio_value_proportion[1] > 0:  # 白马策略
        run_monthly(bm_before_market_open, 1, time='9:00', reference_security='000300.XSHG')
        run_monthly(bm_adjust_position, 1, time='9:45', reference_security='000300.XSHG')
    
    if g.portfolio_value_proportion[2] > 0:  # ETF策略
        run_daily(trade, '10:00')    
    
    run_daily(sell_stocks, '10:00')     # 止损函数
    run_daily(check_limit_up, '14:00')  # 检查涨停板
    run_weekly(print_position_info, 2, time='14:55')

# 参数设置
def set_params(context):
    g.run_stoploss = True    # 是否进行止损
    g.stoploss_limit = 0.08  # 止损线
    
    g.stock_num = 5          # 策略1和策略2分别持股数量
    g.up_price = 50          # 个股价格上限
    g.pass_months = [1, 4]   # 空仓月份（1月和4月）
    
    # 策略持仓记录（关键修复）
    g.strategy_holdings = {
        1: [],  # 小市值策略持仓
        2: [],  # 白马策略持仓
    }
    
    # 策略1全局变量
    g.trading_signal = True
    g.yesterday_HL_list = [] # 昨日涨停股票
    g.target_list = []       # 目标持仓股票
    g.limitup_stocks = []    # 涨停股票避免买入
    g.min_mv = 10            # 最小市值(亿)
    g.max_mv = 100           # 最大市值(亿)
    g.reason_to_sell = {}    # 卖出原因记录
    
    # 策略2全局变量
    g.check_out_lists = []
    g.market_temperature = "warm"
    g.roe = 10  # ROE权重
    g.roa = 6   # ROA权重
    
    # 策略3全局变量
    g.etf_pool = [
        '518880.XSHG', #黄金ETF
        '513100.XSHG', # 纳指100
        '159915.XSHE', # 创业板
        '510180.XSHG', # 上证180
        '512290.XSHG', # 生物医药
        '513020.XSHG', # 港股科技
        '515070.XSHG', # 人工智能
        '588120.XSHG', # 科创板 
    ]
    g.m_days = 25  # 动量参考天数
    g.etf_pre = None  # 上次持有的ETF
    g.portfolio_value_proportion = [0.4, 0.4, 0.2]  # 策略资金占比

# 回测设置
def set_backtest():
    set_option('avoid_future_data', True)
    set_benchmark('399101.XSHE')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.0001), type="fund")  
    set_slippage(FixedSlippage(0.002), type="stock")  
    set_order_cost(  
        OrderCost(  
            open_tax=0,  
            close_tax=0.0005,  
            open_commission=0.0001,  
            close_commission=0.0001,  
            close_today_commission=0,  
            min_commission=5,  
        ),  
        type="stock",  
    )  
    set_order_cost(  
        OrderCost(  
            open_tax=0,  
            close_tax=0,  
            open_commission=0,  
            close_commission=0,  
            close_today_commission=0,  
            min_commission=0,  
        ),  
        type="mmf",  
    )  

# 打印持仓信息
def print_position_info(context):
    print('————————————————————————— 持仓信息 —————————————————————————')
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        stock_info = get_security_info(stock)
        stock_name = stock_info.display_name if stock_info else "未知"
        cost = position.avg_cost
        price = position.price
        ret = 100 * (price/cost - 1) if cost > 0 else 0
        print(f'代码: {stock}, 名称: {stock_name}, 成本价: {cost:.2f}')
        print(f'现价: {price:.2f}, 收益率: {ret:.2f}%')
        print(f'持仓: {position.total_amount:.0f}股, 市值: {position.value:.2f}')
        print('———————————————————————————————————————————————————————') 

# ====================== 策略1: 小市值策略 ======================
def xsz_get_stock_list(context):
    """选股模块"""
    MKT_index = '399101.XSHE'
    initial_list = filter_stocks(context, get_index_stocks(MKT_index))
    
    # 财务指标过滤 (修复：移除不存在的turnover_ratio字段)
    q = query(
        valuation.code,
        valuation.market_cap,
        income.np_parent_company_owners,
        income.net_profit,
        income.operating_revenue
    ).filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(g.min_mv, g.max_mv),
        income.np_parent_company_owners > 0,
        income.net_profit > 0,
        income.operating_revenue > 1e8,
        indicator.roe > 0.15,
        indicator.roa > 0.10,
        valuation.turnover_ratio > 0.5  # 换手率过滤 >0.5%
    ).order_by(valuation.market_cap.asc()).limit(g.stock_num*3)
    
    df = get_fundamentals(q)
    if df.empty:
        return [] 

    final_list = list(df.code)
    last_prices = history(1, '1d', 'close', final_list, df=False)
    
    # 价格过滤
    return [stock for stock in final_list 
            if stock in context.portfolio.positions or last_prices[stock] <= g.up_price]

def xsz_adjustment(context):
    """调整持仓"""
    g.trading_signal = today_is_between(context)
    if not g.trading_signal:
        # 关键修复：只清空本策略持仓
        for stock in g.strategy_holdings[1][:]:
            order_target_value(stock, 0)
            if stock in g.strategy_holdings[1]:
                g.strategy_holdings[1].remove(stock)
        log.info('小市值策略：空仓月份，已清仓')
        return
    
    g.target_list = xsz_get_stock_list(context)[:g.stock_num]
    log.info(f'小市值目标持仓: {g.target_list}')
    
    # 获取当前持仓
    current_holdings = g.strategy_holdings[1][:]
    
    # 卖出不在目标列表中的股票（除昨日涨停股）
    sell_list = [s for s in current_holdings 
                if s not in g.target_list and s not in g.yesterday_HL_list]
                
    for stock in sell_list:
        order_target_value(stock, 0)
        if stock in g.strategy_holdings[1]:
            g.strategy_holdings[1].remove(stock)
        log.info(f"小市值策略卖出: {stock}")
    
    # 计算可用资金（策略1专用部分）
    strategy_value = context.portfolio.total_value * g.portfolio_value_proportion[0]
    current_value = sum([pos.value for pos in context.portfolio.positions.values() 
                        if pos.security in g.strategy_holdings[1]])
    available_cash = max(0, strategy_value - current_value)  # 确保非负
    
    # 买入新标的
    buy_list = [s for s in g.target_list if s not in current_holdings]
    if buy_list and available_cash > 0:
        cash_per_stock = available_cash / len(buy_list)
        for stock in buy_list:
            if open_position(stock, cash_per_stock, strategy_id=1):
                log.info(f"小市值策略买入: {stock}, 金额: {cash_per_stock:.2f}")

def filter_stocks(context, stock_list):
    """股票过滤"""
    current_data = get_current_data()
    filtered = []
    
    for stock in stock_list:
        if current_data[stock].paused: continue  # 停牌
        if current_data[stock].is_st: continue   # ST
        if '退' in current_data[stock].name: continue
        
        # 板块过滤 (排除创业板/科创板/北交所)
        if stock.startswith(('30', '68', '8', '4')): continue  
        
        # 次新股过滤 (上市不足1年)
        ipo_date = get_security_info(stock).start_date
        if (context.current_dt.date() - ipo_date).days < 365: continue
        
        # 价格过滤 (非涨停跌停)
        last_price = current_data[stock].last_price
        if last_price >= current_data[stock].high_limit: continue  # 涨停
        if last_price <= current_data[stock].low_limit: continue   # 跌停
        
        filtered.append(stock)
    
    return filtered

def today_is_between(context):
    """判断是否空仓月份"""
    month = context.current_dt.month
    day = context.current_dt.day
    
    if month in g.pass_months:
        return False
    elif month in [3, 12] and day >= 16:
        return False
    return True

# ====================== 策略2: 白马攻防策略 ======================
def bm_adjust_position(context):
   
    if not g.check_out_lists:
        bm_before_market_open(context)
        
    buy_stocks = g.check_out_lists
    
    # 卖出不在目标列表中的股票（只处理本策略持仓）
    for stock in g.strategy_holdings[2][:]:
        current_data = get_current_data()
        # 不在买入列表则卖出
        if stock not in buy_stocks:
            # 涨停无法卖出时跳过
            if current_data[stock].last_price >= current_data[stock].high_limit:
                continue
            order_target_value(stock, 0)
            if stock in g.strategy_holdings[2]:
                g.strategy_holdings[2].remove(stock)
            log.info(f"白马策略调出: {stock}")
    
    # 买入新标的
    position_count = len([s for s in context.portfolio.positions.keys() 
                         if s in g.strategy_holdings[2]])
    if len(buy_stocks) > position_count:
        # 使用策略2专用资金
        value = context.portfolio.total_value * g.portfolio_value_proportion[1] / g.stock_num
        
        for stock in buy_stocks:
            if stock not in g.strategy_holdings[2]:
                if open_position(stock, value, strategy_id=2):
                    if len(g.strategy_holdings[2]) >= g.stock_num:
                        break

def open_position(security, value, strategy_id):
    """开仓买入并记录策略持仓"""
    if value > 0:
        order = order_target_value(security, value)
        if order and order.filled > 0:
            # 记录策略持仓
            if security not in g.strategy_holdings[strategy_id]:
                g.strategy_holdings[strategy_id].append(security)
            log.info(f"策略{strategy_id}买入 {security}, 金额: {value:.2f}")
            return True
    return False

def Market_temperature(context):
    """市场温度判断"""
    index300 = attribute_history('000300.XSHG', 220, '1d', ('close'), df=False)['close']
    market_height = (mean(index300[-5:]) - min(index300)) / (max(index300) - min(index300))
    if market_height < 0.20:
        g.market_temperature = "cold"

    elif market_height > 0.90:
        g.market_temperature = "hot"

    elif max(index300[-60:]) / min(index300) > 1.20:
        g.market_temperature = "warm"
    log.info(f"市场温度: {g.market_temperature}")
    
## 开盘前运行函数
def bm_before_market_open(context):
    Market_temperature(context)
    g.check_out_lists = []
    current_data = get_current_data()
    all_stocks = get_index_stocks("000300.XSHG") #以沪深300成分股味股票池进一步筛选
    # 过滤创业板、ST、停牌、当日涨停
    all_stocks = [stock for stock in all_stocks if not (
            (current_data[stock].day_open == current_data[stock].high_limit) or  # 涨停开盘
            (current_data[stock].day_open == current_data[stock].low_limit) or  # 跌停开盘
            current_data[stock].paused or  # 停牌
            current_data[stock].is_st or  # ST
            ('ST' in current_data[stock].name) or
            ('*' in current_data[stock].name) or
            ('退' in current_data[stock].name) or
            (stock.startswith('30')) or  # 创业
            (stock.startswith('68')) or  # 科创
            (stock.startswith('8')) or  # 北交
            (stock.startswith('4'))   # 北交
    )]
    all_stocks=filter_highprice_stock(context,all_stocks)  #过滤高价股
    
    if g.market_temperature == "cold":
        q = query(
            valuation.code, 
            indicator.roe,
            indicator.roa
            ).filter(
            valuation.pb_ratio > 0,
            valuation.pb_ratio < 1,
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit>2.0,
            indicator.inc_return > 1.5,
            indicator.inc_net_profit_year_on_year > -15,
        	valuation.code.in_(all_stocks)
        	).order_by(
        	(indicator.roa/valuation.pb_ratio).desc()
        ).limit(
        	50
        )
    elif g.market_temperature == "warm":
        q = query(
            valuation.code, 
            indicator.roe,
            indicator.roa
            ).filter(
            valuation.pb_ratio > 0,
            valuation.pb_ratio < 1,
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit>1.0,
            indicator.inc_return > 2.0,
            indicator.inc_net_profit_year_on_year > 0,
        	valuation.code.in_(all_stocks)
        	).order_by(
        	(indicator.roa/valuation.pb_ratio).desc()
        ).limit(
        	50
        )
    elif g.market_temperature == "hot":
        q = query(
            valuation.code, 
            indicator.roe,
            indicator.roa
            ).filter(
 
            valuation.pb_ratio > 3,
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit>0.5,
            indicator.inc_return > 3.0,
            indicator.inc_net_profit_year_on_year > 20,
        	valuation.code.in_(all_stocks)
        	).order_by(
        	indicator.roa.desc()
        ).limit(
        	50#*10
        )
        
        
    
    """*****************************************************************************************"""            
    df = get_fundamentals(q)
    df.index = df['code'].values
    
    
      #按照因子给股票排序（相当于各因子平权）
    #pb_rank= df['pb_ratio'].rank(ascending=True)  # 升序排名（pb越低越好）
    roe_inv_rank= df['roe'].rank(ascending=False)  # 降序排名（roe越高越好）
    roa_inv_rank= df['roa'].rank(ascending=False)  # 降序排名（roa越高越好）

    # 应用权重计算综合得分
    df['point'] = ( g.roe * roe_inv_rank + g.roa * roa_inv_rank)
    
    
    #按得分进行排序，取指定数量的股票
    df = df.sort_values(by='point')#[:g.buy_stock_count]
    
    check_out_lists = list(df.code)
    """*****************************************************************************************"""
        
   
    #check_out_lists = list(get_fundamentals(q).code)
    # 动量趋势过滤，剔除太高和太低的
    check_out_lists2 = Moment_rank(check_out_lists, 25, -1.0, 10.5)
    # 顺序还是按照动量趋滤前原来的顺序
    check_out_lists = [x for x in check_out_lists if x in check_out_lists2]
    
    
   
    g.check_out_lists = check_out_lists[:g.stock_num]
    log.info("今日股票池：%s" % g.check_out_lists)
    
    
'''
#### 动量计算（MOM）
- 对股票近days天的收盘价取对数，进行加权线性回归（近期权重高）。
- 计算年化收益率（指数化斜率）和R平方（趋势强度）。
- 动量得分=年化收益率×R平方。
'''
def MOM(stock,days):
    df = attribute_history(stock, days, '1d', ['close'], df= False)
    y = np.log(df['close'])
    n = len(y)  
    x = np.arange(n)
    weights = np.linspace(1, 2, n)  
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    annualized_returns = math.pow(math.exp(slope), 250) - 1
    residuals = y - (slope * x + intercept)
    weighted_residuals = weights * residuals**2
    r_squared = 1 - (np.sum(weighted_residuals) / np.sum(weights * (y - np.mean(y))**2))
    score = annualized_returns * r_squared
    return score

def Moment_rank(stock_pool, days,ll, hh):
    score_list = []
    for stock in stock_pool:
        score = MOM(stock,days)
        score_list.append(score)
    df = pd.DataFrame(index=stock_pool, data={'score':score_list})
    df = df.sort_values(by='score', ascending=False)  # 降序 
    df = df[(df['score']>ll) & (df['score']<hh)]
    rank_list = list(df.index)    
    return rank_list
    
    
    
#过滤高价股（>50元）    
def filter_highprice_stock(context,stock_list):
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    last_prices = history(1, unit='1d', field='close', security_list=stock_list)
    return [stock for stock in stock_list if stock in g.hold_list or
            last_prices[stock][-1] <= g.up_price]



# ====================== 策略3: ETF轮动策略 ======================
def get_etf_rank(etf_pool):
    """ETF动量排名"""
    score_list = []
    for etf in etf_pool:
        try:
            df = attribute_history(etf, g.m_days, '1d', ['close'], skip_paused=True, df=True)
            if df.empty:
                score_list.append(-100)
                continue
                
            y = np.log(df['close'])
            x = np.arange(len(y))
            
            # 线性回归
            slope, intercept = np.polyfit(x, y, 1)
            annualized_returns = np.exp(slope * 250) - 1  # 年化收益
            
            # 计算R平方
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred)**2)
            ss_tot = np.sum((y - np.mean(y))**2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            score = annualized_returns * r_squared
            score_list.append(score)
        except:
            score_list.append(-100)  # 出错时给低分
    
    df = pd.DataFrame({'etf': etf_pool, 'score': score_list})
    return df.sort_values('score', ascending=False)

def trade(context):
    """ETF交易"""
    # 获取动量最高的ETF
    rank_df = get_etf_rank(g.etf_pool)
    if rank_df.empty:
        return
    
    sel_etf = rank_df.iloc[0]['etf']
    current_etf = None
    
    # 检查当前持仓
    for asset in context.portfolio.positions:
        if asset in g.etf_pool:
            current_etf = asset
            break
    
    # 策略3专用资金
    strategy_cash = context.portfolio.total_value * g.portfolio_value_proportion[2]
    
    # 需要调仓的情况
    if current_etf and current_etf != sel_etf:
        order_target_value(current_etf, 0)  # 卖出原ETF
        order_target_value(sel_etf, strategy_cash)  # 买入新ETF
        log.info(f"ETF调仓: {current_etf} -> {sel_etf}")
        g.etf_pre = sel_etf
    
    # 首次买入或恢复持仓
    elif not current_etf and strategy_cash > 0:
        order_target_value(sel_etf, strategy_cash)
        log.info(f"ETF建仓: {sel_etf}")
        g.etf_pre = sel_etf

# ====================== 公共策略函数 ======================
def sell_stocks(context):
    """止盈止损"""
    if not g.run_stoploss:
        return
    
    for stock, pos in context.portfolio.positions.items():
        # 盈利100%止盈
        if pos.price >= pos.avg_cost * 2:
            order_target_value(stock, 0)
            # 从策略持仓记录中移除
            for strategy_id in [1, 2]:
                if stock in g.strategy_holdings[strategy_id]:
                    g.strategy_holdings[strategy_id].remove(stock)
            log.info(f"止盈卖出 {stock}, 收益率:{(pos.price/pos.avg_cost-1):.2%}")
        
        # 亏损止损
        elif pos.price <= pos.avg_cost * (1 - g.stoploss_limit):
            order_target_value(stock, 0)
            # 从策略持仓记录中移除
            for strategy_id in [1, 2]:
                if stock in g.strategy_holdings[strategy_id]:
                    g.strategy_holdings[strategy_id].remove(stock)
            log.info(f"止损卖出 {stock}, 亏损:{(1 - pos.price/pos.avg_cost):.2%}")
            g.reason_to_sell[stock] = 'stoploss'

def check_limit_up(context):
    """检查昨日涨停股今日表现"""
    # 获取当前持仓
    holdings = list(context.portfolio.positions.keys())
    
    # 获取昨日涨停股
    if holdings:
        # 确保所有持仓股票代码都是字符串
        valid_holdings = [s for s in holdings if isinstance(s, str) and '.' in s]
        
        if valid_holdings:
            df = get_price(valid_holdings, end_date=context.previous_date, 
                          frequency='daily', fields=['close','high_limit'], 
                          count=1, panel=False)
            # 添加容错处理，避免空数据
            if not df.empty:
                g.yesterday_HL_list = list(df[df['close'] >= df['high_limit'] * 0.999].index)
            else:
                g.yesterday_HL_list = []
        else:
            g.yesterday_HL_list = []
    else:
        g.yesterday_HL_list = []

    # 检查涨停是否打开
    for stock in g.yesterday_HL_list:
        # 验证股票代码格式
        if not isinstance(stock, str) or '.' not in stock:
            log.error(f"无效股票代码格式: {stock}, 类型: {type(stock)}")
            continue
            
        try:
            current_data = get_current_data()[stock]
            if current_data.last_price < current_data.high_limit * 0.99:  # 打开超过1%
                order_target_value(stock, 0)
                # 从策略持仓记录中移除
                for strategy_id in [1, 2]:
                    if stock in g.strategy_holdings[strategy_id]:
                        g.strategy_holdings[strategy_id].remove(stock)
                log.info(f"涨停打开卖出 {stock}")
                g.reason_to_sell[stock] = 'limitup'
                g.limitup_stocks.append(stock)
        except Exception as e:
            log.error(f"处理股票{stock}时出错: {str(e)}")