# Clone from JoinQuant
# postId: b6aed7dc26db318a76d94d8be11857ab
# backtestId: 636add8695bf021c1b8ede4616ad8fa8
# title: 温度白马攻防策略-V2--&gt;更新成V2.1版

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
	set_benchmark('000300.XSHG')	# 设定沪深300作为基准
	set_option('use_real_price', True)	# 开启动态复权模式(真实价格)
	set_option("avoid_future_data", True)	#防止未来函数
	log.set_level('order', 'error')	# 过滤掉order系列API产生的比error级别低的log
	set_order_cost(OrderCost(close_tax=0.001, open_commission=0.00012, close_commission=0.00012, min_commission=5), type='stock')	### 股票相关设定 ###

def after_code_changed(context):
    unschedule_all()
    g.buy_stock_count = 5  # 目标持股数量
    g.check_out_lists = []  # 入选股票清单
    g.low_risk_ETFs = ['563020.XSHG', '511010.XSHG']    #股票池为{}时，买入低风险ETF组合: 1.低波红利，2，国债ETF1
    run_daily(filter_before_open, time='9:35', reference_security='000300.XSHG')
    run_daily(adjust_position, time='9:45', reference_security='000300.XSHG')

def adjust_position(context): # 月度调仓交易
    if context.current_dt.month != context.previous_date.month or len(context.portfolio.positions) == 0:
        print(f"调仓时间 {context.current_dt}" )
        message_str = f"\n调仓时间 {context.current_dt}"
        target_stock_list = g.check_out_lists
        current_data = get_current_data()
        for stock in context.portfolio.positions:
            nosell_1 = context.portfolio.positions[stock].price >= current_data[stock].high_limit
            sell_2 = stock not in target_stock_list
            if sell_2 and not nosell_1:
                if target_stock_list==[] and stock in g.low_risk_ETFs: continue  # 股票池为空，持有的ETF不用卖出
                print(f" - 卖出 {stock}  {current_data[stock].name}")
                message_str+=f"\n - 卖出 {stock}  {current_data[stock].name}"
                order_target_value(stock, 0)
        
        if target_stock_list:
            position_count = len(context.portfolio.positions)
            if g.buy_stock_count > position_count:
                value = context.portfolio.cash / (g.buy_stock_count - position_count)
                for stock in target_stock_list[:g.buy_stock_count]:
                    if stock not in context.portfolio.positions:
                        print(f" - 买入 {stock}  {current_data[stock].name}")
                        message_str+=f"\n - 买入 {stock}  {current_data[stock].name}"
                        order_target_value(stock, value)
                        if len(context.portfolio.positions) >= g.buy_stock_count:
                            break
        # 账户闲置资金买入低风险ETF组合  
        if context.portfolio.cash>context.portfolio.total_value*0.10:
            _ETFs = [x for x in g.low_risk_ETFs if (context.previous_date-get_security_info(x).start_date).days>375]
            if _ETFs:
                print("账户闲置资金买入低风险ETF组合")
                message_str+="\n账户闲置资金买入低风险ETF组合"
                cash = context.portfolio.cash/len(_ETFs)
                for etf in _ETFs:
                    print(f" - 买入 {etf}  {current_data[etf].name}")
                    message_str+=f"\n - 买入 {etf}  {current_data[etf].name}"
                    order_value(etf, cash)
        print("-")
        print("- 最新持仓:")
        message_str+="\n- 最新持仓:"
        for stock in context.portfolio.positions:
            qty = context.portfolio.positions[stock].total_amount
            print(f" {stock}  {current_data[stock].name} {qty}股 ")
            message_str+=(f"\n {stock}  {current_data[stock].name} {qty}股 ")
        print("\n微信发送信息:", message_str)
        if context.run_params.type == 'sim_trade':
            send_message(message_str, channel='weixin')
        

## 开盘前获取股票池
def filter_before_open(context):
    if context.current_dt.month != context.previous_date.month or len(context.portfolio.positions) == 0:
        Market_temperature(context)
        g.check_out_lists = []
        current_data = get_current_data()
        all_stocks = get_index_stocks("000300.XSHG")
        all_stocks = [stock for stock in all_stocks if not (
                (current_data[stock].last_price>round(context.portfolio.total_value*0.95/g.buy_stock_count/100,2)) or  # 股价限高
                (current_data[stock].day_open == current_data[stock].high_limit) or  # 涨停开盘
                (current_data[stock].day_open == current_data[stock].low_limit) or  # 跌停开盘
                current_data[stock].paused or  # 停牌
                current_data[stock].is_st or  # ST
                ('ST' in current_data[stock].name) or  # SB
                ('*' in current_data[stock].name) or
                ('退' in current_data[stock].name) or
                (stock.startswith('30')) or  # 创业
                (stock.startswith('68')) or  # 科创
                (stock.startswith('8')) or  # 北交
                (stock.startswith('4'))  # 北交
        )]
        if g.market_temperature == "cold":
            q = query(valuation.code,
            ).filter(
                valuation.pb_ratio > 0,
                valuation.pb_ratio < 1,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 2.0,
                indicator.inc_return > 1.5,
                indicator.inc_net_profit_year_on_year > -15,
                valuation.code.in_(all_stocks)
            ).order_by(      (indicator.roa / valuation.pb_ratio).desc()
            ).limit(                g.buy_stock_count + 1
            )
        elif g.market_temperature == "warm":
            q = query(valuation.code,
            ).filter(
                valuation.pb_ratio > 0,
                valuation.pb_ratio < 1,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 1.0,
                indicator.inc_return > 2.0,
                indicator.inc_net_profit_year_on_year > 0,
                valuation.code.in_(all_stocks)
            ).order_by(     (indicator.roa / valuation.pb_ratio).desc()
            ).limit(                g.buy_stock_count + 1
            )
        elif g.market_temperature == "hot":
            q = query(valuation.code,
            ).filter(
                valuation.pb_ratio > 3,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 0.5,
                indicator.inc_return > 3.0,
                indicator.inc_net_profit_year_on_year > 20,
                valuation.code.in_(all_stocks)
            ).order_by(                indicator.roa.desc()
            ).limit(                g.buy_stock_count + 1
            )
        check_out_lists = list(get_fundamentals(q).code)
        check_out_lists2 = Moment_rank(check_out_lists, 25, -1.0, 10.5)    # 动量趋势过滤，剔除太高和太低的
        g.check_out_lists = [x for x in check_out_lists if x in check_out_lists2]    # 顺序还是按照动量趋滤前原来的顺序
    
        log.info(f"\n\n\n========今日股票池: {g.check_out_lists} ===========")
        if g.check_out_lists:
            for stock in g.check_out_lists:
                print(f' {stock}  {current_data[stock].name}  {"持仓" if stock in context.portfolio.positions else ""}')
            print("-")
     
def track_back_market_temp(context):# 数据回滚两年判断市场温度       
    long_index300 = list(attribute_history('000300.XSHG', 220 * 3, '1d', ('close'), df=False)['close'])
    g.market_temperature = 'cold'
    for back_day in range(220, len(long_index300)):
        index300 = long_index300[back_day - 220:back_day]
        market_height = (mean(index300[-5:]) - min(index300)) / (max(index300) - min(index300))
        if market_height < 0.20:
            g.market_temperature = "cold"
        elif market_height > 0.90:
            g.market_temperature = "hot"
        elif max(index300[-60:]) / min(index300) > 1.20:
            g.market_temperature = "warm"

def Market_temperature(context):
    if not hasattr(g, 'market_temperature'):
        track_back_market_temp(context)

    index300 = attribute_history('000300.XSHG', 220, '1d', ('close'), df=False)['close']
    market_height = (mean(index300[-5:]) - min(index300)) / (max(index300) - min(index300))
    if market_height < 0.20:
        g.market_temperature = "cold"
    elif market_height > 0.90:
        g.market_temperature = "hot"
    elif max(index300[-60:]) / min(index300) > 1.20:
        g.market_temperature = "warm"

    if g.market_temperature == "cold":
        temp = 200
    elif g.market_temperature == "warm":
        temp = 300
    else:
        temp = 400
    if context.run_params.type != 'sim_trade':
        record(temp=temp)

def MOM(stock, days):
    df = attribute_history(stock, days, '1d', ['close'], df=False)
    y = np.log(df['close'])
    n = len(y)
    x = np.arange(n)
    weights = np.linspace(1, 2, n)
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    annualized_returns = math.pow(math.exp(slope), 250) - 1
    residuals = y - (slope * x + intercept)
    weighted_residuals = weights * residuals ** 2
    r_squared = 1 - (np.sum(weighted_residuals) / np.sum(weights * (y - np.mean(y)) ** 2))
    score = annualized_returns * r_squared
    return score

def Moment_rank(stock_pool, days, ll, hh):
    score_list = []
    for stock in stock_pool:
        score_list.append(MOM(stock, days))
    df = pd.DataFrame(index=stock_pool, data={'score': score_list})
    df = df.sort_values(by='score', ascending=False)  # 降序 
    df = df[(df['score'] > ll) & (df['score'] < hh)]
    rank_list = list(df.index)
    return rank_list