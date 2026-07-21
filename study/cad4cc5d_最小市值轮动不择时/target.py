# Clone from JoinQuant
# postId: cad4cc5d954f9d59d1361ae74e4c2e13
# backtestId: 6dfbf03d6c8c450875c435f25466a47d
# title: 最小市值轮动,不择时

from sqlalchemy.sql.expression import or_

# 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    g.stocks_to_hold = []
    g.choicenum = 5
    #设定沪深300作为基准
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    set_slippage(PriceRelatedSlippage(0.002))
    run_monthly(monthly, 1)
    
def unpaused(stockspool):
    current_data=get_current_data()
    return [s for s in stockspool if not current_data[s].paused]    
    
# 调整
def rebalance(context):
    print 'rebalance at %s' % context.current_dt
    
    date=context.current_dt.strftime("%Y-%m-%d")

    # 选出低市值的股票，buylist
    df = get_fundamentals(query(
            valuation.code,valuation.market_cap, valuation.pe_ratio
        ).filter(
            or_ (valuation.pe_ratio >100,
                valuation.pe_ratio <0)
        ).order_by(
            valuation.market_cap.asc()
        ), date=date
        ).dropna()
    
    # 去除创业板
    df = df[df['code'].map(lambda x: not x.startswith('300'))]
    
    stock_list = list(df['code'])
    #去除停牌股
    buylist = unpaused(stock_list)
    # 去除ST，*ST
    st=get_extras('is_st', buylist, start_date=date, end_date=date, df=True)
    st=st.loc[date]
    buylist=list(st[st==False].index)[:5]
    
    g.stocks_to_hold =buylist[:g.choicenum]
    context.universe = g.stocks_to_hold
    #print g.stocks_to_hold

    print("before clean: %d" %len(context.portfolio.positions))
    clean_stocks_to_sell(context)
    print("after clean: %d" %len(context.portfolio.positions))
    choicenum = g.choicenum - len(context.portfolio.positions)
    if choicenum <= 0:
        return

    # 等权重买入buylist中的股票
    position_per_stk = context.portfolio.cash/choicenum
    closes = history(1, '1d', 'price', security_list=g.stocks_to_hold, df=False)
    for stock in buylist:
        if stock in context.portfolio.positions:
            continue
        if choicenum <= 0:
            continue
        choicenum = choicenum - 1
        close = closes[stock][-1]
        if not isnan(close):
            amount = int(position_per_stk/close)
            order(stock, +amount)

# 清空应该卖出的股票
def clean_stocks_to_sell(context):
    for stock in context.portfolio.positions:
        if stock not in g.stocks_to_hold:
            order_target(stock, 0)   

def monthly(context):
    rebalance(context)
