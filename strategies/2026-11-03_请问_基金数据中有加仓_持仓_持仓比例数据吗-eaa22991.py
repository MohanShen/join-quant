# Clone from JoinQuant
# postId: eaa22991d6043ba6ba9a60087520d0a9
# backtestId: 85a203792f35b2a0baa11b14fe5160b5
# title: 请问，基金数据中有加仓、持仓、持仓比例数据吗

# 克隆自聚宽文章：https://www.joinquant.com/post/6596
# 标题：【新手入门教程】简单市值轮动策略
# 作者：JoinQuant-TWist

def initialize(context):
    g.stocksnum = 5 # 持有最小市值股票数
    g.period = 10 # 轮动频率
    run_daily(daily,time='every_bar')# 周期循环daily
    g.days = 1 # 记录策略进行到第几天，初始为1

def daily(context):
    # 判断策略进行天数是否能被轮动频率整除余1
    if g.days % g.period == 1:

        # 获取当前时间
        date=context.current_dt.strftime("%Y-%m-%d")
        # 获取上证指数和深证综指的成分股代码并连接，即为全A股市场所有股票
        scu = get_index_stocks('000001.XSHG')+get_index_stocks('399106.XSHE')

        # 选出在scu内的股票的股票代码，并按照当前时间市值从小到大排序
        df = get_fundamentals(query(
                valuation.code,valuation.market_cap
            ).filter(
                valuation.code.in_(scu)
            ).order_by(
                valuation.market_cap.asc()
            ), date=date
            )

        # 取出前g.stocksnum名的股票代码，并转成list类型，buylist为选中的股票
        buylist =list(df['code'][:g.stocksnum])

        # 对于每个当下持有的股票进行判断：现在是否已经不在buylist里，如果是则卖出
        for stock in context.portfolio.positions:
            if stock not in buylist: #如果stock不在buylist
                order_target(stock, 0) #调整stock的持仓为0，即卖出

        # 将资金分成g.stocksnum份
        position_per_stk = context.portfolio.cash/g.stocksnum
        # 用position_per_stk大小的g.stocksnum份资金去买buylist中的股票
        for stock in buylist:
            order_value(stock, position_per_stk)
    else:
        pass # 什么也不做

    g.days = g.days + 1 # 策略经过天数增加1