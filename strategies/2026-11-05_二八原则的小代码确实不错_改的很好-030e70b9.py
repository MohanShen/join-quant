# Clone from JoinQuant
# postId: 030e70b9a6de522173d2386bba77ad75
# backtestId: 3fb44fe705b0078019d452261277ef75
# title: 二八原则的小代码确实不错，改的很好。

'''
二八小市值择时买卖

配置指定频率的调仓日，在调仓日每日指定时间，计算所选大盘指数和所选小盘指数当前的20日涨
幅，如果2个指数的20日涨幅有一个为正，则进行选股调仓，之后如此循环往复。

止损策略：

    大盘止损：(可选)
        1. 每分钟取大盘前160日的最低价和最高价，如果最高大于最低的两倍则清仓，停止交易。
        2. 每分钟判断大盘是否呈现三只黑鸦止损，如果是则当天清仓并停止交易，第二天停止交
           易一天。

    个股止损：(可选)
        每分钟判断个股是否从持仓后的最高价回撤幅度，如果超过个股回撤阈值，则平掉该股持仓

    二八止损：(必需)
        每日指定时间，计算沪深300指数和中证500指数当前的20日涨幅，如果2个指数涨幅都为负，
        则清仓，重置调仓计数，待下次调仓条件满足再操作

版本：v2.0.7
日期：2016.11.15
作者：Morningstar
'''
enable_profile()

from collections import OrderedDict
import tradestat


def initialize(context):
    log_section('initialize', '初始化', sep=False)

    # 设置系统参数
    set_sys()
    # 设置常数
    set_const()
    # 设置策略参数
    set_param()
    # 设置过滤器
    set_filter()
    # 设置止损器
    set_stop_loss()
    # 设置缓存参数
    set_cache()
    # 加载统计模块
    g.trade_stat = tradestat.trade_stat()

    # 打印自定义信息
    # log.info('')
    # 打印策略参数
    log_param()
    # 打印使用的过滤器
    log_filter()
    # 打印使用的止损器
    log_stop_loss()


# def process_initialize(context):
#     log_section('process_initialize','进程重新启动')


# def after_code_changed(context):
#     log_section('after_code_changed','代码发生修改')


def before_trading_start(context):
    log_section('before_trading_start', '盘前处理')

    reset_day_param()
    # 盘前就判断三黑鸦状态，因为判断的数据为前4日
    g.cache['is_last_day_3_crows'] = _is_3_crows(
        g.param['index_3_crows'][g.VALUE])
    if g.cache['is_last_day_3_crows']:
        log.info("==> 前4日已经构成三黑鸦形态")


def after_trading_end(context):
    log_section('after_trading_end', '盘后处理')

    g.trade_stat.report(context)
    # 得到当前未完成订单
    orders = get_open_orders()
    for _order in orders.values():
        log.info("canceled uncompleted order: %s" % (_order.order_id))


def handle_data(context, data):
    '''
    按分钟回测
    '''
    # for key in g.stop_loss_minute:
    #     g.stop_loss_minute[key][g.FUNC](context, data)
    for stop in g.stop_loss_minute:
        stop[g.FUNC](context, data)

    # 每天指定时间检查是否调仓并处理
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    adjust_position_time = g.param['adjust_position_time'][g.VALUE]
    if hour == adjust_position_time[g.HOUR] and minute == adjust_position_time[g.MINUTE] and not g.cache['stop_trade']:
        _adjust_position(context, data)


def _adjust_position(context, data):
    log.info("调仓日计数 [%d]" % (g.cache['day_count']))

    # 回看指数前20天的涨幅
    gr_index_l = get_growth_rate(g.param['index_l'][g.VALUE])
    gr_index_s = get_growth_rate(g.param['index_s'][g.VALUE])
    log.info("当前%s指数的20日涨幅 [%.2f%%]" % (
        get_security_info(g.param['index_l'][g.VALUE]).display_name, gr_index_l * 100))
    log.info("当前%s指数的20日涨幅 [%.2f%%]" % (
        get_security_info(g.param['index_s'][g.VALUE]).display_name, gr_index_s * 100))

    if gr_index_l <= g.param['index_growth_rate'][g.VALUE] and gr_index_s <= g.param['index_growth_rate'][g.VALUE]:
        position_clear(context)
        g.cache['day_count'] = 0
    else:
        if g.cache['day_count'] % g.param['period'][g.VALUE] == 0:
            log.info("==> 满足条件进行调仓")
            buy_stocks = pick_stocks(context, data)
            log.info("选股后可买股票: %s" % (buy_stocks))
            position_adjust(context, buy_stocks)
        g.cache['day_count'] += 1


# 按月运行
# run_monthly(func, monthday, time='open', reference_security)
# 按周运行
# run_weekly(func, weekday, time='open', reference_security)
# 每天内何时运行
# run_daily(func, time='open', reference_security)


#### initialize ####


def set_sys():
    # 以上证指数为基准
    # 设定上证指数作为基准
    set_benchmark('000001.XSHG')
    # 设定沪深300指数作为基准
    # set_benchmark('000300.XSHG')
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003,
                             close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    # 设定滑点为百分比
    # set_slippage(PriceRelatedSlippage(0.002))
    # 使用真实价格回测
    set_option('use_real_price', True)


def set_const():
    g.VALUE = 0
    g.FUNC = 0
    g.DESCR = 1
    g.HOUR = 0
    g.MINUTE = 1


def set_param():
    p = {}

    p['period'] = (4, '调仓频率，单位：日')
    p['adjust_position_time'] = ((14, 50), '配置调仓时间（24小时分钟制）')
    p['pick_by_pe'] = (False, '是否根据PE选股')
    p['pick_by_eps'] = (True, '是否根据EPS选股')
    p['pick_stock_count'] = (100, '备选股票数目')
    p['is_rank_stock'] = (True, '是否对股票评分')
    p['rank_stock_count'] = (20, '参与评分的股票数目')  # 评分的股票数目不能大于备选股票数目
    p['buy_stock_count'] = (3, '买入股票数目')
    # p['index_l']=('000300.XSHG','大盘股指数') # 沪深300指数
    # p['index_s']=('000905.XSHG','小盘股指数') # 中证500指数
    p['index_l'] = ('000016.XSHG', '大盘股指数')  # 上证50指数
    p['index_s'] = ('399333.XSHE', '小盘股指数')  # 中小板R指数
    # p['index_s']=('399006.XSHE','小盘股指数') # 创业板指数
    p['buy_stock_count'] = (3, '买入股票数目')
    p['index_growth_rate'] = (0.01, '判定调仓的二八指数n日增幅')  # n = 20
    p['index_3_crows'] = ('000001.XSHG', '判定三黑鸦的指数')
    # 配置价格止损判定指数，默认为上证指数，可修改为其他指数
    p['index_price'] = ('000001.XSHG', '判定价格止损的指数')

    g.param = p


def set_filter():
    # g.filter={}
    g.filter = []
    func_register(g.filter, filter_by_query, '查询财务数据库过滤')
    func_register(g.filter, filter_gem, '过滤创业版股票')
    func_register(g.filter, filter_paused, '过滤停牌股票')
    func_register(g.filter, filter_st, '过滤ST及其他具有退市标签的股票')
    func_register(g.filter, filter_limitup, '过滤涨停的股票')
    func_register(g.filter, filter_limitdown, '过滤跌停的股票')
    # func_register(g.filter,filter_by_growth_rate, '过滤n日增长率为负的股票')
    # func_register(g.filter,filter_blacklist, '过滤黑名单股票')
    # func_register(g.filter,filter_new, '过滤新股')
    func_register(g.filter, filter_by_rank, '评分过滤器')


def set_stop_loss():
    # g.stop_loss_day = {}
    # g.stop_loss_minute = {}
    g.stop_loss_day = []
    g.stop_loss_minute = []
    func_register(g.stop_loss_minute, stop_loss_by_price, '大盘价格止损')
    func_register(g.stop_loss_minute, stop_loss_by_3_crows, '三黑鸦止损')
    # func_register(g.stop_loss_minute,stop_loss_by_index_l,'二八止损')
    # func_register(g.stop_loss_minute,stop_loss_by_stoc,'个股止损')
    # func_register(g.stop_loss_minute,stop_profit_by_stoc,'个股止盈')


def set_cache():
    c = {}

    # 调仓日计数器，单位：日
    c['day_count'] = 0

    # 缓存股票持仓后的最高价
    c['last_high'] = {}

    df = get_fundamentals(query(valuation.code))
    c['stock_list'] = list(df['code'])

    # 缓存当日个股250天内最大的3日涨幅，避免当日反复获取，每日盘后清空
    c['pct_change'] = {}
    # 缓存指数下跌分钟数
    c['minute_count_index_ls_drop'] = 0
    c['minute_count_cur_drop'] = 0
    c['is_last_day_3_crows'] = False
    c['is_day_stop_loss_by_price'] = False
    c['stop_trade'] = False  # 暂停当天交易

    g.cache = c


def reset_day_param():
    '''
    重置当日参数，仅针对需要当日需要重置的参数
    '''
    df = get_fundamentals(query(valuation.code))
    g.cache['stock_list'] = list(df['code'])
    # 重置当日大盘价格止损状态
    g.cache['is_day_stop_loss_by_price'] = False

    # 重置三黑鸦状态
    g.cache['is_last_day_3_crows'] = False
    g.cache['minute_count_cur_drop'] = 0
    g.cache['minute_count_index_ls_drop'] = 0

    # 清空当日个股250天内最大的3日涨幅的缓存
    g.cache['pct_change'].clear()

    g.cache['stop_trade'] = False  # 暂停当天交易


#### pick & filter ####


def pick_stocks(context, data):
    '''
    选取指定数目的小市值股票，再进行过滤，最终挑选指定可买数目的股票
    '''
    stock_list = g.cache['stock_list']

    # for key in g.filter.keys():
    #     stock_list = g.filter[key][g.FUNC](stock_list, context, data)
    for filter in g.filter:
        stock_list = filter[g.FUNC](stock_list, context, data)

    # 选取指定可买数目的股票
    return stock_list[:g.param['buy_stock_count'][g.VALUE]]


def filter_by_query(stock_list, context, data):
    '''
    查询财务数据库过滤
    '''
    pe_min = 0
    pe_max = 200
    eps_min = 0

    q = query(valuation.code).filter(valuation.code.in_(stock_list))
    if g.param['pick_by_pe'][g.VALUE]:
        q = q.filter(
            valuation.pe_ratio > pe_min,
            valuation.pe_ratio < pe_max
        )
    if g.param['pick_by_eps'][g.VALUE]:
        q = q.filter(indicator.eps > eps_min)

    df = get_fundamentals(
        q.order_by(valuation.market_cap.asc()
                   ).limit(
            g.param['pick_stock_count'][g.VALUE]
        ))

    return list(df['code'])


# def filter_by_pe(stock_list, context, data):
#     '''
#     过滤不在PE范围内股票
#     '''
#     min=0
#     max=200
#     df=get_fundamentals(query(
#         valuation.code
#     ).filter(
#         valuation.code.in_(stock_list),
#         valuation.pe_ratio > min,
#         valuation.pe_ratio < max)
#     )
#     return df['code']


# def filter_by_eps(stock_list, context, data):
#     '''
#     过滤不在EPS范围内股票
#     '''
#     min=0
#     # max = 200
#     df=get_fundamentals(query(
#         valuation.code
#     ).filter(
#         valuation.code.in_(stock_list),
#         indicator.eps > min,
#     )
#     return df['code']


def filter_paused(stock_list, context, data):
    '''
    过滤停牌股票
    '''
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def filter_st(stock_list, context, data):
    '''
    过滤ST及其他具有退市标签的股票
    '''
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and not current_data[stock].name.startswith('退')]


def filter_gem(stock_list, context, data):
    '''
    过滤创业版股票
    '''
    return [stock for stock in stock_list if stock[0:3] != '300']


def filter_limitup(stock_list, context, data):
    '''
    过滤涨停的股票
    '''
    threshold = 1.00
    # last_prices = history(1, unit='1m', field='close',
    #                       security_list=stock_list)

    # 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
    # return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
    #         or last_prices[stock][-1] < data[stock].high_limit * threshold]
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or data[stock].close < data[stock].high_limit * threshold]


def filter_limitdown(stock_list, context, data):
    '''
    过滤跌停的股票
    '''
    threshold = 1.00
    # last_prices = history(1, unit='1m', field='close',
    #                       security_list=stock_list)

    # return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
    #         or last_prices[stock][-1] > data[stock].low_limit * threshold]
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or data[stock].close > data[stock].low_limit * threshold]


def filter_by_growth_rate(stock_list, context, data):
    '''
    过滤n日增长率为负的股票
    '''
    n = 20
    return [stock for stock in stock_list if get_growth_rate(stock, n) > 0]


def filter_blacklist(stock_list, context, data):
    '''
    过滤黑名单股票
    '''
    blacklist = _get_blacklist()
    return [stock for stock in stock_list if stock not in blacklist]


def _get_blacklist():
    # 黑名单一览表，更新时间 2016.7.10 by 沙米
    # 科恒股份、太空板业，一旦2016年继续亏损，直接面临暂停上市风险
    blacklist = ["600656.XSHG", "300372.XSHE", "600403.XSHG", "600421.XSHG", "600733.XSHG", "300399.XSHE",
                 "600145.XSHG", "002679.XSHE", "000020.XSHE", "002330.XSHE", "300117.XSHE", "300135.XSHE",
                 "002566.XSHE", "002119.XSHE", "300208.XSHE", "002237.XSHE", "002608.XSHE", "000691.XSHE",
                 "002694.XSHE", "002715.XSHE", "002211.XSHE", "000788.XSHE", "300380.XSHE", "300028.XSHE",
                 "000668.XSHE", "300033.XSHE", "300126.XSHE", "300340.XSHE", "300344.XSHE", "002473.XSHE"]
    return blacklist


def filter_new(stock_list, context, data):
    '''
    过滤新股
    '''
    delta = 60
    stocks = get_all_securities(['stock'])
    stocks = stocks[(context.current_dt.date() - stocks.start_date)
                    > datetime.timedelta(delta)].index


def filter_by_rank(stock_list, context, data):
    '''
    评分过滤器
    '''
    stock_list = stock_list[:g.param['rank_stock_count'][g.VALUE]]
    dst_stocks = {}
    for stock in stock_list:
        h = attribute_history(stock, 130, unit='1d', fields=(
            'close', 'high', 'low'), skip_paused=True)
        low_price_130 = h.low.min()
        high_price_130 = h.high.max()

        avg_15 = data[stock].mavg(15, field='close')
        cur_price = data[stock].close

        # avg_15 = h['close'][-15:].mean()
        # cur_price = get_close_price(stock, 1, '1m')

        score = (cur_price - low_price_130) + \
            (cur_price - high_price_130) + (cur_price - avg_15)
        # score = ((cur_price-low_price_130) + (cur_price-high_price_130) +
        # (cur_price-avg_15)) / cur_price
        dst_stocks[stock] = score

    df = pd.DataFrame(dst_stocks.values(), index=dst_stocks.keys())
    df.columns = ['score']
    df = df.sort(columns='score', ascending=True)
    return df.index


#### stop loss ####


def stop_loss_by_price(context, data):
    '''
    大盘指数前130日内最高价超过最低价2倍，则清仓止损
    基于历史数据判定，因此若状态满足，则当天都不会变化
    增加此止损，回撤降低，收益降低
    '''
    index = g.param['index_price'][g.VALUE]
    if not g.cache['is_day_stop_loss_by_price']:
        h = attribute_history(index, 160, unit='1d', fields=(
            'close', 'high', 'low'), skip_paused=True)
        low_price = h.low.min()
        high_price = h.high.max()
        # if high_price > 2 * low_price:
        if high_price > 2.2 * low_price \
                and h['close'][-1] < h['close'][-4] \
                and h['close'][-1] > h['close'][-100]:
            # 当日第一次输出日志
            log.info("==> 大盘止损，%s指数前130日内最高价超过最低价2倍, 最高价: %f, 最低价: %f" % (
                get_security_info(index).display_name, high_price, low_price))
            g.cache['is_day_stop_loss_by_price'] = True

    if g.cache['is_day_stop_loss_by_price']:
        position_clear(context)
        g.cache['day_count'] = 0
        g.cache['stop_trade'] = True  # 暂停当天交易

    return g.cache['is_day_stop_loss_by_price']


def stop_loss_by_3_crows(context, data):
    '''
    前日三黑鸦，累计当日大盘指数涨幅<0的分钟计数
    如果分钟计数超过值n，则开始进行三黑鸦止损
    避免无效三黑鸦乱止损
    minute
    '''
    # 配置三黑鸦判定指数，默认为上证指数，可修改为其他指数
    index = g.param['index_3_crows'][g.VALUE]
    # 配置是否开启大盘三黑鸦止损
    # 个人认为针对大盘判断三黑鸦效果并不好，首先有效三只乌鸦难以判断，准确率实际来看也不好，
    # 其次，分析历史行情看一般大盘出现三只乌鸦的时候，已经严重滞后了，使用其他止损方式可能会更好
    n = 60

    if g.cache['is_last_day_3_crows']:
        if get_growth_rate(index, 1) < 0:
            g.cache['minute_count_cur_drop'] += 1

        if g.cache['minute_count_cur_drop'] >= n:
            if g.cache['minute_count_cur_drop'] == n:
                log.info("==> 当日%s增幅 < 0 已超过%d分钟，执行三黑鸦止损" %
                         (get_security_info(index).display_name, n))

            position_clear(context)
            g.cache['day_count'] = 0
            g.cache['stop_trade'] = True  # 暂停当天交易
            return True

    return False


def _is_3_crows(stock):
    # talib.CDL3BLACKCROWS

    # 三只乌鸦说明来自百度百科
    # 1. 连续出现三根阴线，每天的收盘价均低于上一日的收盘
    # 2. 三根阴线前一天的市场趋势应该为上涨
    # 3. 三根阴线必须为长的黑色实体，且长度应该大致相等
    # 4. 收盘价接近每日的最低价位
    # 5. 每日的开盘价都在上根K线的实体部分之内；
    # 6. 第一根阴线的实体部分，最好低于上日的最高价位
    #
    # 算法
    # 有效三只乌鸦描述众说纷纭，这里放宽条件，只考虑1和2
    # 根据前4日数据判断
    # 3根阴线跌幅超过4.5%（此条件忽略）

    h = attribute_history(stock, 4, '1d', ('close', 'open'),
                          skip_paused=True, df=False)
    h_close = list(h['close'])
    h_open = list(h['open'])

    if len(h_close) < 4 or len(h_open) < 4:
        return False

    # 一阳三阴
    if h_close[-4] > h_open[-4] \
            and (h_close[-1] < h_open[-1] and h_close[-2] < h_open[-2] and h_close[-3] < h_open[-3]):
        # and (h_close[-1] < h_close[-2] and h_close[-2] < h_close[-3]) \
        # and h_close[-1] / h_close[-4] - 1 < -0.045:
        return True
    return False


def stop_loss_by_index_ls(context, data):
    '''
    二八止损
    minute
    '''
    count = 120
    # 回看指数前20天的涨幅
    gr_index_l = get_growth_rate(g.param['index_l'][g.VALUE])
    gr_index_s = get_growth_rate(g.param['index_s'][g.VALUE])

    if gr_index_l <= g.param['index_growth_rate'][g.VALUE] and gr_index_s <= g.param['index_growth_rate'][g.VALUE]:
        if (g.cache['minute_count_index_ls_drop'] == 0):
            log.info("当前二八指数的20日涨幅同时低于[%.2f%%], %s指数: [%.2f%%], %s指数: [%.2f%%]"
                     % (g.param['index_growth_rate'][g.VALUE] * 100, get_security_info(g.param['index_l'][g.VALUE]).display_name, gr_index_l * 100, get_security_info(g.param['index_s'][g.VALUE]).display_name, gr_index_s * 100))

            # log.info("当前%s指数的20日涨幅 [%.2f%%]" %(get_security_info(g.param['index_l'][g.VALUE]).display_name, gr_index_l*100))
            # log.info("当前%s指数的20日涨幅 [%.2f%%]"
            # %(get_security_info(g.param['index_s'][g.VALUE]).display_name,
            # gr_index_s*100))
        g.cache['minute_count_index_ls_drop'] += 1
    else:
        # 不连续状态归零
        if g.cache['minute_count_index_ls_drop'] < count:
            g.cache['minute_count_index_ls_drop'] = 0

    if g.cache['minute_count_index_ls_drop'] >= count:
        if g.cache['minute_count_index_ls_drop'] == count:
            log.info("==> 当日%s指数和%s指数的20日增幅低于[%.2f%%]已超过%d分钟，执行28指数止损"
                     % (get_security_info(g.param['index_l'][g.VALUE]).display_name, get_security_info(g.param['index_s'][g.VALUE]).display_name, g.param['index_growth_rate'][g.VALUE] * 100, count))

        position_clear(context)
        g.cache['day_count'] = 0
        g.cache['stop_trade'] = True  # 暂停当天交易
        return True

    return False


def stop_loss_by_stock(context, data):
    '''
    个股止损
    minute 级别
    '''
    for stock in context.portfolio.positions.keys():
        cur_price = data[stock].close

        if g.cache['last_high'][stock] < cur_price:
            g.cache['last_high'][stock] = cur_price

        threshold = _get_stop_loss_threshold(stock, g.param['period'][g.VALUE])
        # log.debug("个股止损阈值, stock: %s, threshold: %f" %(stock, threshold))
        if cur_price < g.cache['last_high'][stock] * (1 - threshold):
            log.info("==> 个股止损, stock: %s, cur_price: %f, last_high: %f, threshold: %f"
                     % (stock, cur_price, g.cache['last_high'][stock], threshold))

            position = context.portfolio.positions[stock]
            if position_close(position):
                g.cache['day_count'] = 0


def stop_profit_by_stock(context, data):
    '''
    个股止盈
    minute 级别
    '''
    for stock in context.portfolio.positions.keys():
        position = context.portfolio.positions[stock]
        cur_price = data[stock].close
        threshold = _get_stop_profit_threshold(
            stock, g.param['period'][g.VALUE])
        # log.debug("个股止盈阈值, stock: %s, threshold: %f" %(stock, threshold))
        if cur_price > position.avg_cost * (1 + threshold):
            log.info("==> 个股止盈, stock: %s, cur_price: %f, avg_cost: %f, threshold: %f"
                     % (stock, cur_price, g.cache['last_high'][stock], threshold))

            position = context.portfolio.positions[stock]
            if position_close(position):
                g.cache['day_count'] = 0


def _get_stop_loss_threshold(security, n=3):
    '''
    计算个股回撤止损阈值
    即个股在持仓n天内能承受的最大跌幅
    算法：(个股250天内最大的n日跌幅 + 个股250天内平均的n日跌幅)/2
    返回正值
    '''
    pct_change = _get_pct_change(security, 250, n)
    # log.debug("pct of security [%s]: %s", pct)
    maxd = pct_change.min()
    # maxd = pct[pct<0].min()
    avgd = pct_change.mean()
    # avgd = pct[pct<0].mean()
    # maxd和avgd可能为正，表示这段时间内一直在增长，比如新股
    bstd = (maxd + avgd) / 2

    # 数据不足时，计算的bstd为nan
    if not isnan(bstd):
        if bstd != 0:
            return abs(bstd)
        else:
            # bstd = 0，则 maxd <= 0
            if maxd < 0:
                # 此时取最大跌幅
                return abs(maxd)

    return 0.099  # 默认配置回测止损阈值最大跌幅为-9.9%，阈值高貌似回撤降低


def _get_stop_profit_threshold(security, n=3):
    '''
    计算个股止盈阈值
    算法：个股250天内最大的n日涨幅
    返回正值
    '''
    pct_change = _get_pct_change(security, 250, n)
    maxr = pct_change.max()

    # 数据不足时，计算的maxr为nan
    # 理论上maxr可能为负
    if (not isnan(maxr)) and maxr != 0:
        return abs(maxr)
    return 0.30  # 默认配置止盈阈值最大涨幅为30%


def _get_pct_change(security, n, m):
    '''
    获取个股前n天的m日增幅值序列
    增加缓存避免当日多次获取数据
    '''
    pct_change = None
    if security in g.pct_change.keys():
        pct_change = g.pct_change[security]
    else:
        h = attribute_history(security, n, unit='1d',
                              fields=('close'), skip_paused=True)
        pct_change = h['close'].pct_change(m)  # 3日的百分比变比（即3日涨跌幅）
        g.pct_change[security] = pct_change
    return pct_change


#### trade ####


def position_open(security, value):
    '''
    开仓，买入指定价值的证券
    报单成功并成交（包括全部成交或部分成交，此时成交量大于0），返回True
    报单失败或者报单成功但被取消（此时成交量等于0），返回False
    '''
    order = _order_target_value(security, value)
    if order != None and order.filled > 0:
        # 报单成功并有成交则初始化最高价
        cur_price = get_close_price(security, 1, '1m')
        # cur_price = order.price
        g.cache['last_high'][security] = cur_price
        return True
    return False


def position_close(position):
    '''
    平仓，卖出指定持仓
    平仓成功并全部成交，返回True
    报单失败或者报单成功但被取消（此时成交量等于0），或者报单非全部成交，返回False
    '''
    security = position.security
    # order = _order_target_value(security, 0)  # 可能会因停牌失败
    order = _order(security, -position.closeable_amount)  # 卖出可用仓位
    if order:
        if order.filled > 0:
            # 只要有成交，无论全部成交还是部分成交，则统计盈亏
            g.trade_stat.watch(security, order.filled,
                               position.avg_cost, position.price)

        if order.status == OrderStatus.held:
            # 全部成交则删除相关证券的最高价缓存
            if security in g.cache['last_high']:
                g.cache['last_high'].pop(security)
            else:
                log.warn("last high price of %s not found" % (security))
            return True
    return False


def position_clear(context):
    '''
    清空卖出所有持仓
    '''
    if context.portfolio.positions:
        log.info("==> 清仓，卖出所有股票")
        for stock in context.portfolio.positions.keys():
            position = context.portfolio.positions[stock]
            position_close(position)


def position_adjust(context, buy_stocks):
    '''
    根据待买股票创建或调整仓位
    对于因停牌等原因没有卖出的股票则继续持有
    始终保持持仓数目为g.buy_stock_count
    '''
    for stock in context.portfolio.positions.keys():
        if stock not in buy_stocks:
            log.info("stock [%s] in position is not buyable" % (stock))
            position = context.portfolio.positions[stock]
            position_close(position)
        else:
            log.info("stock [%s] is already in position" % (stock))

    # 根据股票数量分仓
    # 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配
    position_count = len(context.portfolio.positions)
    count = g.param['buy_stock_count'][g.VALUE]
    if count > position_count:
        value = context.portfolio.cash / (count - position_count)

        for stock in buy_stocks:
            if context.portfolio.positions[stock].total_amount == 0:
                if position_open(stock, value):
                    if len(context.portfolio.positions) == count:
                        break


def _order(security, amount):
    '''
    自定义下单
    根据Joinquant文档，当前报单函数都是阻塞执行，报单函数（如order_target）返回即表示报单完成
    报单成功返回报单（不代表一定会成交），否则返回None
    '''
    if amount < 0:
        log.info("Selling out %s : %f" % (security, -amount))
    elif amount > 0:
        log.info("Buying in %s : %f" % (security, amount))

    # 如果股票停牌，创建报单会失败，order_target_value 返回None
    # 如果股票涨跌停，创建报单会成功，order_target_value 返回Order，但是报单会取消
    # 部成部撤的报单，聚宽状态是已撤，此时成交量>0，可通过成交量判断是否有成交
    return order(security, amount)


def _order_target_value(security, value):
    '''
    自定义下单
    根据Joinquant文档，当前报单函数都是阻塞执行，报单函数（如order_target_value）返回即表示报单完成
    报单成功返回报单（不代表一定会成交），否则返回None
    '''
    if value == 0:
        log.info("Selling out %s" % (security))
    else:
        log.info("Order %s to value %f" % (security, value))

    # 如果股票停牌，创建报单会失败，order_target_value 返回None
    # 如果股票涨跌停，创建报单会成功，order_target_value 返回Order，但是报单会取消
    # 部成部撤的报单，聚宽状态是已撤，此时成交量>0，可通过成交量判断是否有成交
    return order_target_value(security, value)

#### utils ####


def get_growth_rate(security, n=20):
    '''
    获取股票n日以来涨幅，根据当前价计算
    '''
    lc = get_close_price(security, n)
    c = get_close_price(security, 1, '1m')

    if not isnan(lc) and not isnan(c) and lc != 0:
        return (c - lc) / lc
    else:
        log.error("数据非法, security: %s, %d日收盘价: %f, 当前价: %f" %
                  (security, n, lc, c))
        return 0


def get_close_price(security, n, unit='1d'):
    '''
    获取前n个单位时间当时的收盘价
    '''
    close = 0
    while(n > 0):  # 如果前n日数据为nan，则取n-1日数据，直至n为1
        close = attribute_history(security, n, unit, ('close'))['close'][0]
        if isnan(close):
            n -= 1
        else:
            break
    return close


def func_register(register, func, descr=''):
    register.append((func, descr))


#### log ####


def log_section(name, descr, sep=True, sep_char='-', sep_count=50):
    if sep:
        log.info(sep_char * sep_count)
    log.info('%s - %s' % (name, descr))


def log_param():
    log_section('param', '策略参数')
    for key in g.param:
        log.info('%s : %s' %
                 (g.param[key][g.DESCR], str(g.param[key][g.VALUE])))


def log_filter():
    log.info('filter - 过滤器:')
    for filter in g.filter:
        log.info(' + ' + filter[g.DESCR])


def log_stop_loss():
    log.info('stop_loss - 止损器:')
    for stop in g.stop_loss_minute:
        log.info(' + ' + stop[g.DESCR])
    for stop in g.stop_loss_day:
        log.info(' + ' + stop[g.DESCR])
