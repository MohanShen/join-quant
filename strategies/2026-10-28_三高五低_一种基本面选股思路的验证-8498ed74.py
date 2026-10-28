# Clone from JoinQuant
# postId: 8498ed7422235f6e5cf9653e407015b6
# backtestId: 1551318bba028d9b65aa5ff6e122889d
# title: 三高五低，一种基本面选股思路的验证

def initialize(context):
    g.stock_set = []
    g.buy_stock = [] #选中买入股票池
    g.month = context.current_dt.month
    run_monthly(select_stocks,1) #定期更新股票池

#----基本面选股模块-------------------------------------
def select_stocks(context):
    #每3个月更新股票池
    month = context.current_dt.month
    if month%3 !=1:
        return
    scu0 = get_index_stocks('000001.XSHG')
    scu3 = get_index_stocks('399001.XSHE')#操作沪深300股票池
    g.stock_set = scu0+scu3
    q = query(
        income,balance
        ).filter(
            income.code.in_(g.stock_set),
            #毛利为正
            income.total_profit/income.total_operating_revenue >0,
            #ROE >10%
            income.net_profit/balance.total_owner_equities >0.1
        ).order_by(
            balance.inventories.asc() #低存货
        ).limit(
            5
        )
    df = get_fundamentals(q)
    stock_set = list(df['code'])
    g.buy_stock = stock_set
    print g.buy_stock
    if len(g.buy_stock) ==0:
        return
    reset_position(context)
    set_position(context)
# 轮换选股后清除新股票池外的持仓
def reset_position(context):
    if context.portfolio.positions.keys() !=[]:
        for stock in context.portfolio.positions.keys():
            if stock not in g.buy_stock:
                order_target_value(stock, 0)
    return None
#股票池全部买入持有至更换股票池
def set_position(context):
    value = context.portfolio.cash/len(g.buy_stock)
    for stock in g.buy_stock:
        order_target_value(stock,value)

#----回测处理模块---------------------------------------
def handle_data(context, data):
    pass

    