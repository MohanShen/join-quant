# Clone from JoinQuant
# postId: a8380587d50166ee327979f7b6b34ba3
# backtestId: 77d2575d8d1a5b0ee01c66f9abe3a8f4
# title: 融券卖出是保证金比例好像起不到作用

# 导入函数库
import jqdata


# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('510300.XSHG')
    # 只设定一个账号
    # 获取初始资金
    init_cash = context.portfolio.starting_cash
    # 设置账户为融资融券账户
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type='stock_margin')])
    # 设置融资利率
    set_option('margincash_interest_rate', 0.02)
    # 设置融券利率
    set_option('marginsec_interest_rate', 0.02)
    # 设置融资保证金比例
    set_option('margincash_margin_rate', 1)
    # 设置融券保证金比例
    set_option('marginsec_margin_rate', 1)

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0, open_commission=0.00006, close_commission=0.00006, min_commission=5),
                   type='fund')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
    # 开盘时或每分钟开始时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
    g.security = '510300.XSHG'

## 开盘时运行函数
def market_open(context):
    # 要操作的股票
    fund = g.security
    # 判断某股票security在cyclelevel周期级别的趋势，短周期均线高于长周期即为多头返回1，空头返回2。
    # security,标的股票，cyclelevel: K线的周期级别，如30分钟，输入30m，输入规则：Xm,Xd,X是正整数，shortterm:短周期数字，如：5, longterm: 长周期数字，如：10。
    def determtendency(security, cyclelevel, shortterm, longterm):
        # 获取K线数据
        include_now_short = get_bars(security, shortterm, cyclelevel, ['close'])
        include_now_long = get_bars(security, longterm, cyclelevel, ['close'])
        # 获得短周期均线
        ma1 = include_now_short['close'].mean()
        # 获得长周期均线
        ma2 = include_now_long['close'].mean()

        # 判断多头行情返回1, 空头行情返回2
        if ma1 > ma2:
            return 1
        elif ma1 < ma2:
            return 2

    # 获取security的X分钟级别的Y周期均线，当前价格>均线，返回1，<返回2， 其他返回0。
    def bpoint(security, x, y):
        # 获取K线数据
        closedata = attribute_history(security, y, x, ['close'], True, True, 'pre')
        # 获得均线点位
        ma1 = closedata['close'].mean()
        # 获得当前股价
        currentdata = get_current_data()
        price = currentdata[fund].last_price
        if price > ma1:
            return 1
        elif price < ma1:
            return 2
        else:
            return 0

    # 开仓-根据目标钱数融券卖出。
    def marginsec_open_value(security, value):
        # 获取当前时刻的价格
        close_data = attribute_history(security, 1, '1m', ['close'])
        # 获取股票收盘价
        price = close_data['close'].mean()
        # 获取可做空的股票数量
        amount = value / price
        marginsec_open(security, int(amount/100)*100)

    # 开仓-根据目标钱数融资买入。
    def margincash_open_value(security, value):
        # 获取当前时刻的价格
        close_data = attribute_history(security, 1, '1m', ['close'])
        # 获取股票收盘价
        price = close_data['close'].mean()
        # 获取可做多的股票数量
        amount = value / price
        margincash_open(security, int(amount/100)*100)

    # 平仓-融券卖出-买券还券
    def marginsec_close_position(security):
        position_now = context.portfolio.short_positions[security].total_amount
        if position_now != 0:
            marginsec_close(security, position_now)
        else:
            pass

    # 平仓-融资买入——卖券还款
    def margincash_close_position(security):
        position_now = context.portfolio.long_positions[security].total_amount
        if position_now != 0:
            margincash_close(security, position_now)
        else:
            pass
    # 获取现金数量
    cash = context.portfolio.available_cash - context.portfolio.margin
    # # 判断买点买入,卖点卖出。
    # # 多头行情下融资买入
    # if determtendency(fund, '30m', 5, 10) == 1 and bpoint(fund, '1m', 300) == 2:
    #     margincash_open_value(fund, cash)
    # # 空头行情下卖券还款
    # elif determtendency(fund, '30m', 5, 10) == 2:
    #     margincash_close_position(fund)

    # 判断行情趋势，卖点做空卖出，买点买入
    if determtendency(fund, '30m', 5, 10) == 2 and bpoint(fund, '1m', 300) == 1:
        marginsec_open_value(fund, cash)
    # 多头行情下卖券还款
    elif determtendency(fund, '30m', 5, 10) == 1:
        marginsec_close_position(fund)
