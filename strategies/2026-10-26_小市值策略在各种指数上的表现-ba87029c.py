# Clone from JoinQuant
# postId: ba87029cbd57ddd8a9d5b70be3cd5ded
# backtestId: 20da534a5b7ff9f7c2434b3bd9cd7e1f
# title: 小市值策略在各种指数上的表现

# 克隆自聚宽文章：https://www.joinquant.com/post/25496
# 标题：收益狂飙，年化收益100%，11年1700倍，绝无未来函数
# 原作者：jqz1226 ZUEL
# 修改者: will be rich man

# 流程分析
#     每天14:40执行
#     → 获取中小板股票
#     → 按流通市值升序排序
#     → 取最小的20只
#     → 过滤：
#         ST
#         停牌
#         涨停
#         跌停
#     → 最终取前5只
#     → 调仓：
#         不在名单 → 卖
#         新进入名单 → 买

# 导入函数库
from jqdata import *


# 初始化函数，设定基准等等
def initialize(context):
    # 避免未来函数
    set_option("avoid_future_data", True)
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')

    # 股票池
    g.security_universe_index = "399101.XSHE"  # 中小板
    # g.security_universe_index = "000985.XSHG"  # 中证全指
    # g.security_universe_index = "000001.XSHG"   # 上证综指
    # g.security_universe_index = "399106.XSHE"  # 深证综指
    g.buy_stock_count = 5
    

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5),
                   type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
    # 定时运行
    run_daily(my_trade, time='14:40', reference_security='000300.XSHG')
    # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')


## 开盘时运行函数
def my_trade(context):
    check_out_lists = get_index_stocks(g.security_universe_index)
    q = query(valuation.code).filter(
        valuation.code.in_(check_out_lists)
    ).order_by(
        valuation.circulating_market_cap.asc()
    ).limit(
        g.buy_stock_count * 8
    )
    check_out_lists = list(get_fundamentals(q).code)
    # 只保留沪深主板
    check_out_lists = filter_main_board_stock(check_out_lists)
    # 过滤: 三停（停牌、涨停、跌停）及st,*st,退市
    check_out_lists = filter_st_stock(check_out_lists)
    check_out_lists = filter_limitup_stock(context, check_out_lists)
    check_out_lists = filter_limitdown_stock(context, check_out_lists)
    check_out_lists = filter_paused_stock(check_out_lists)
    # 取需要的只数
    check_out_lists = check_out_lists[:g.buy_stock_count]
    current_data = get_current_data()
    log.info(
        "\n当日选股:\n" +
        "\n".join([
            "{} {}".format(stock, current_data[stock].name)
            for stock in check_out_lists
        ])
    )
    # 买卖
    adjust_position(context, check_out_lists)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):' + str(context.current_dt.time())))
    # 得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：' + str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
    log.info('\n\n\n\n\n\n')


# 自定义下单
# 根据Joinquant文档，当前报单函数都是阻塞执行，报单函数（如order_target_value）返回即表示报单完成
# 报单成功返回报单（不代表一定会成交），否则返回None
def order_target_value_(security, value):
    if value == 0:
        log.debug("正在卖出 %s" % (security))
    else:
        log.debug("正在买入%s 目标金额为 %.2f 元" % (security, value))

    # 如果股票停牌，创建报单会失败，order_target_value 返回None
    # 如果股票涨跌停，创建报单会成功，order_target_value 返回Order，但是报单会取消
    # 部成部撤的报单，聚宽状态是已撤，此时成交量>0，可通过成交量判断是否有成交
    return order_target_value(security, value)


# 开仓，买入指定价值的证券
# 报单成功并成交（包括全部成交或部分成交，此时成交量大于0），返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），返回False
def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        log.info('报单成功并成交（包括全部成交或部分成交，此时成交量大于0）')
        return True
    log.info('报单失败或者报单成功但被取消（此时成交量等于0）')
    return False


# 平仓，卖出指定持仓
# 平仓成功并全部成交，返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），或者报单非全部成交，返回False
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            log.info('平仓成功并全部成交')
            return True
    log.info('报单失败或者报单成功但被取消（此时成交量等于0），或者报单非全部成交')
    return False


# 交易
def adjust_position(context, buy_stocks):
    if not context.portfolio.positions:
        log.info("当前持仓为空，跳过卖出步骤")
    else:
        for stock in context.portfolio.positions:
            if stock not in buy_stocks:
                log.info("股票 [%s] 不再持有" % (stock))
                position = context.portfolio.positions[stock]
                if close_position(position):
                    log.info("股票 [%s] 已卖出" % (stock))
                else:
                    log.info("股票 [%s] 卖出失败" % (stock))
            else:
                log.info("股票 [%s] 已持有" % (stock))

    # 根据股票数量分仓
    # 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配
    position_count = len(context.portfolio.positions)
    log.info("开始买入逻辑：当前持仓 %d 只，目标持仓 %d 只" % (position_count, g.buy_stock_count))
    if g.buy_stock_count > position_count:
        value = context.portfolio.cash / (g.buy_stock_count - position_count)
        log.info("每只分配资金约 %.2f 元" % (value))
        for stock in buy_stocks:
            # 稳健检查：股票不在持仓中，或持仓股数为0（实际不会），则需要买入
            if stock not in context.portfolio.positions or context.portfolio.positions[stock].total_amount == 0:
                log.info("股票 %s 未持有，尝试买入 %.2f 元" % (stock, value))
                if open_position(stock, value):
                    current_count = len(context.portfolio.positions)
                    log.info("买入 %s 成功，当前持仓数量变为 %d 只" % (stock, current_count))
                    if len(context.portfolio.positions) == g.buy_stock_count:
                        log.info("已达到目标持仓数量 %d 只，停止买入" % g.buy_stock_count)
                        break


# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


# 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


# 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()

    # 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


# return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
#    or last_prices[stock][-1] < current_data[stock].high_limit * 0.995]

# 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()

    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]

# 只保留沪深主板
def filter_main_board_stock(stock_list):
    return [stock for stock in stock_list 
            if stock.startswith('00') or stock.startswith('60')]
