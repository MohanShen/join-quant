# Clone from JoinQuant
# postId: f72181d51050c23fc60720f62d84c10d
# backtestId: 2efeb0b419bdd177d79c6760c5657c27
# title: 请问这个策略问题出在哪里，为什么一直回测失败啊

# 导入函数库
import jqdatasdk as jq
import datetime

# 初始化参数
max_holdings = 10  # 最大持仓数量
stocks = get_index_stocks('000001.XSHG')  # A股市场
commission_rate = 0.0003  # 买入时佣金率
tax_rate = 0.0013  # 卖出时佣金率和印花税的总和
minimum_commission = 5.0  # 每笔交易的最低佣金费用
stop_loss_threshold = -0.06  # 止损阈值，大盘60日线与昨日收盘价构成死叉时进行止损

# 定义筛选函数
def screen(context):
    q = query(
        valuation.code,
        valuation.pe_ratio,
        indicator.roe,
        indicator.net_profit_cash_cover,
        valuation.market_cap).filter(
        valuation.code.in_(context.stocks),
        valuation.pe_ratio > 35,
        indicator.roe > 0.15,
        indicator.net_profit_cash_cover > 0.8
    ).order_by(
        valuation.market_cap.desc()
    ).limit(
        context.max_holdings
    )
    df = finance.run_query(q)
    return list(df['code'])

# 初始资金为100万元
def initialize(context):
    context.portfolio_value = 1000000.0
    context.stocks = stocks
    context.max_holdings = max_holdings
    context.commission_rate = commission_rate
    context.tax_rate = tax_rate
    context.minimum_commission = minimum_commission
    context.stop_loss_threshold = stop_loss_threshold
    schedule_function(rebalance, date_rule='quarter_start')

def handle_data(context, data):
    pass

# 调仓函数
def rebalance(context, data):
    # 获取当前持仓
    positions = context.portfolio.positions
    holdings = len(positions)
    if holdings == 0:
        # 如果当前没有持仓，则全仓买入筛选出的股票
        for stock in screen(context):
            order_target_value(stock, context.portfolio_value / context.max_holdings)
    else:
        # 如果当前有持仓，则进行卖出、买入操作
        sell_list = []
        for stock in positions:
            current_price = data.current(stock, 'price')
            cost_basis = positions[stock].cost_basis
            holding_value = positions[stock].amount * current_price
            if (current_price < cost_basis * (1 + context.stop_loss_threshold)):
                # 止损操作：如果大盘60日线与昨日收盘价构成死叉，则清空所有持仓
                for stock in positions:
                    order_target_value(stock, 0)
                return
            elif current_price < cost_basis * 0.95:
                # 当亏损超过5%时直接卖出
                amount = positions[stock].amount
                sell_list.append((stock, amount))
            elif stock not in screen(context):
                # 如果当前股票不在筛选结果中，则卖出
                amount = positions[stock].amount
                sell_list.append((stock, amount))
        for stock, amount in sell_list:
            order_target_value(stock, 0)
        holdings = len(positions) - len(sell_list)
        buy_list = screen(context)[:context.max_holdings - holdings]
        cash_per_stock = context.portfolio_value / context.max_holdings
        for stock in buy_list:
            order_target_value(stock, cash_per_stock)