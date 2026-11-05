# Clone from JoinQuant
# postId: b8f2414b3b17db932ff23f37b78ce6a1
# backtestId: caeed7bcf58078338c151dd0ce69dc85
# title: 股债再平衡研究

def initialize(context):
    #设置环境
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    set_benchmark('399311.XSHE')
    #设置场外基金参数
    init_cash = context.portfolio.starting_cash
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type='open_fund')])

def process_initialize(context):
    g.stocks = {
        '100018.OF': 0.5, #富国天利
        '050002.OF': 0.5, #博时沪深300指数基金
        }
    g.last_month = 0

def handle_data(context, data):
    #每个季度运行一次
    if context.current_dt.month not in [2, 5, 8, 11]:
        return
    if context.current_dt.month == g.last_month:
        return
    g.last_month = context.current_dt.month
    # 获取基金信息
    fund_info = get_extras('unit_net_value', g.stocks.keys(), start_date=context.current_dt, end_date=context.current_dt, df=False)
    # 维护账户
    for stock in g.stocks.keys():
        weight = g.stocks[stock]
        print stock, weight
        # 计算头寸大小
        position = weight * context.portfolio.portfolio_value
        # 调整持仓
        if context.portfolio.positions.has_key(stock):
            if context.portfolio.positions[stock].value/position > 1.1:
                # 超过配置比例
                amount = (context.portfolio.positions[stock].value - position) / fund_info[stock][0]
                amount = 100*int(amount/100)
                redeem(stock, amount)
                log.info("赎回%s %i", stock, amount)
            elif context.portfolio.positions[stock].value/position < 0.9:
                # 低于配置比例
                amount = (position - context.portfolio.positions[stock].value) / fund_info[stock][0]
                amount = 100*int(amount/100)
                purchase(stock, amount)
                log.info("申购%s %i", stock, amount)
        else:
            amount = position / fund_info[stock][0]
            amount = 100*int(amount/100)
            purchase(stock, position)
            log.info("申购%s %i", stock, amount)
#end