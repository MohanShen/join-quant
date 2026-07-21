# Clone from JoinQuant
# postId: 7fc942bf539b45add88e26ec3f8fa0a9
# backtestId: 4aab108fad7d72ad9e6459ae5b24309f
# title: 小市值+动量止损（没有1和4空仓）|回撤15.64%

# 克隆自聚宽文章：https://www.joinquant.com/post/50238
# 标题：TSmall-100, 微盘三正
# 作者：Gyro^.^

import pandas as pd
import datetime as dt


def initialize(context):
    # setting system
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    g.max = 0 #当前最大值
    g.check_days = 3  # 最少要拥有的数据天数
    g.max_virtual_amount_days = 60 #虚拟持仓统计最多保留的天数
    g.virtual_available_cash = 100000 #虚拟持仓的仓位
    g.recent_loss = -0.05 #最近一天跌幅阈值，跌幅大于此阈值则触发止损
    g.stop = False
    
    # 参数
    g.etf_pool = [
        '515450.XSHG',  # 红利 ETF
        '510050.XSHG',  # 上证50
        '510300.XSHG', #沪深300（价值股，蓝筹股，中大盘）
        '563300.XSHG',  # 中证 2000
    ]
    g.m_days = 25 #动量参考天数

    context.virtual_positions = {}  # 用于存储虚拟持仓信息
    context.stop_loss_threshold = -0.1  # 最大回撤幅度10%，超过则止损
    context.recover_threshold = 0.00  # 最近一天只要不是绿的就恢复建仓

    context.virtual_amount = {}  # 用于存储虚拟仓的金额

    # setting strategy
    run_daily(iUpdate, 'before_open')
    run_daily(iTrader, 'open')
    run_daily(iReport, 'after_close')
    g.values = pd.DataFrame(columns=['Value'])  # daily portfolio value
    g.values.index.name = 'date'
    g.values.loc[context.previous_date] = [context.portfolio.total_value]  # init value


def iUpdate(context):
    # parameters
    nposition = 20  # number of positions
    nchoice = 30  # number of choice stocks
    # daily update
    g.stocks = _choice_small(context, nchoice)
    g.position_size = 1.0 / nposition * context.portfolio.total_value


def iTrader(context):
    # load data
    stocks = g.stocks
    log.info('stocks:', stocks)
    position_size = g.position_size
    cash_size = 1.5 * position_size
    cdata = get_current_data()

    stopCheck = checkStop(context)
    if stopCheck:
        sellAll(context, cdata)
    else:
        log.info('正常开始买卖')
        realSell(context, stocks, cdata)
        realBuy(context, stocks, cash_size, cdata, position_size)
        log.info('买完之后实际仓位统计:', context.portfolio.positions)

    virtualSell(context, stocks, cdata)
    virtualBuy(context, stocks, cash_size, cdata, position_size)
    log.info('买完之后虚拟仓位统计:', context.virtual_positions)


def realBuy(context, stocks, cash_size, cdata, position_size):
    # buy stocks
    for s in stocks:
        if context.portfolio.available_cash < cash_size:
            log.info('停止循环，available_cash&cash_size', context.portfolio.available_cash, cash_size)
            break
        if cdata[s].paused or \
                cdata[s].last_price >= cdata[s].high_limit or cdata[s].last_price <= cdata[s].low_limit:
            continue

        if s not in context.portfolio.positions:
            log.info('avaliable_cash:', context.portfolio.available_cash, cash_size)
            last_price = cdata[s].last_price
            # 计算可以买入的最大股数(持仓现金和单只股票仓位取最小)
            max_shares = min(int(context.portfolio.available_cash / (1.01 * last_price)),
                             int(position_size / (1.01 * last_price)))  # 考虑溢价
            # 检查是否能买入至少 1 手
            if max_shares < 100:
                continue
            # 确定买入数量，必须是 100 的倍数
            shares_to_buy = min(int(position_size / last_price) // 100 * 100, max_shares // 100 * 100)
            log.info('买入股数以及价格', shares_to_buy, last_price)
            log.info('buy', s, cdata[s].name, shares_to_buy * 1.01 * last_price)
            order_value(s, shares_to_buy * 1.01 * last_price, MarketOrderStyle(1.01 * last_price))


def virtualBuy(context, stocks, cash_size, cdata, position_size):
    # buy stocks
    for s in stocks:
        if g.virtual_available_cash < cash_size:
            log.info('停止循环，virtual_available_cash&cash_size', g.virtual_available_cash, cash_size)
            break
        if cdata[s].paused or \
                cdata[s].last_price >= cdata[s].high_limit or cdata[s].last_price <= cdata[s].low_limit:
            continue

        if s not in context.virtual_positions:
            log.info('虚拟money:', g.virtual_available_cash, 'cashSize:', cash_size)
            last_price = cdata[s].last_price
            # 计算可以买入的最大股数(持仓现金和单只股票仓位取最小)
            max_shares = min(int(g.virtual_available_cash / (1.01 * last_price)),
                             int(position_size / (1.01 * last_price)))  # 考虑溢价
            # 检查是否能买入至少 1 手
            if max_shares < 100:
                continue
            # 确定买入数量，必须是 100 的倍数
            shares_to_buy = min(int(position_size / last_price) // 100 * 100, max_shares // 100 * 100)
            log.info('虚拟买入股数以及价格', shares_to_buy, last_price)
            log.info('buy', s, cdata[s].name, shares_to_buy * 1.003 * last_price)
            context.virtual_positions[s] = {'shares': shares_to_buy, 'cost_price': 1.003 * last_price}
            g.virtual_available_cash = g.virtual_available_cash - 1.003 * last_price * shares_to_buy
            log.info('虚拟money剩余:', g.virtual_available_cash)
            log.info('虚拟仓位:', context.virtual_positions)


def realSell(context, stocks, cdata):
    # sell
    for s in context.portfolio.positions:
        if cdata[s].paused or \
                cdata[s].last_price >= cdata[s].high_limit or cdata[s].last_price <= cdata[s].low_limit:
            continue
        if s not in stocks:
            log.info('sell', s, cdata[s].name)
            order_target(s, 0, MarketOrderStyle(0.99 * cdata[s].last_price))


def virtualSell(context, stocks, cdata):
    # sell
    keys = list(context.virtual_positions.keys())
    for s in keys:
        if cdata[s].paused or \
                cdata[s].last_price >= cdata[s].high_limit or cdata[s].last_price <= cdata[s].low_limit:
            continue
        if s not in stocks:
            log.info('virtual sell', s, cdata[s].name)
            shares = context.virtual_positions[s]['shares']
            g.virtual_available_cash = g.virtual_available_cash + shares * 0.998 * cdata[s].last_price
            del context.virtual_positions[s]


def sellAll(context, cdata):
    log.info('注意！要清仓了！')
    # sell
    for s in context.portfolio.positions:
        if cdata[s].paused or \
                cdata[s].last_price >= cdata[s].high_limit or cdata[s].last_price <= cdata[s].low_limit:
            continue

        log.info('开始卖:', s, cdata[s].name)
        order_target(s, 0, MarketOrderStyle(0.99 * cdata[s].last_price))


def iReport(context):
    log.info(' 收盘统计 虚拟持仓', context.virtual_positions)

    if context.virtual_positions:
        tmp_amount = 0
        for stock, position in context.virtual_positions.items():
            price_df = get_price(stock, end_date=context.current_dt, frequency='daily', count=1, fields=['close'])
            end_price = price_df['close'].iloc[0]
            # 假设初始买入价格为position['cost']，数量为position['quantity']
            tmp_amount += position['shares'] * end_price
    addAmount(context, tmp_amount)

    # table of positions
    cdata = get_current_data()
    tvalue = context.portfolio.total_value
    ptable = pd.DataFrame(columns=['amount', 'value', 'weight', 'name'])
    for s in context.portfolio.positions:
        ps = context.portfolio.positions[s]
        ptable.loc[s] = [ps.total_amount, int(ps.value), 100 * ps.value / tvalue, cdata[s].name]
    ptable = ptable.sort_values(by='weight', ascending=False)
    # daily report
    log.info('  positions', len(ptable), '\n', ptable.head())
    log.info('  total value %.2f, cash %.2f', \
             context.portfolio.total_value / 10000, context.portfolio.available_cash / 10000)
    # daily save
    d = context.current_dt.date()
    g.values.loc[d] = [context.portfolio.total_value]
    write_file('Tiny-100', g.values.to_csv())


# U虚拟持仓统计
def addAmount(context, tmp_amount):
    log.info('收盘统计虚拟仓市值:', tmp_amount, '虚拟仓现金：', g.virtual_available_cash)
    totalMoney = tmp_amount + g.virtual_available_cash
    context.virtual_amount[context.current_dt.strftime('%Y-%m-%d')] = totalMoney
    if totalMoney > g.max:
        g.max = totalMoney
    if len(context.virtual_amount) > g.max_virtual_amount_days:
        earliest_date = min(context.virtual_amount.keys())
        del context.virtual_amount[earliest_date]
    log.info('len', len(context.virtual_amount), context.virtual_amount)


def checkStop(context):
    if (len(context.virtual_amount) >= g.check_days):

        endKey, endValue = get_nth_last_key_value(context.virtual_amount, 1)
        secondKey, secondValue = get_nth_last_key_value(context.virtual_amount, 2)
        recentLoss = (endValue - secondValue) / secondValue
        maxLoss = (endValue - g.max)/g.max
        log.info('recentLoss:', recentLoss, 'maxLoss:', maxLoss)

        target_num = 1    
        target_list = get_rank(g.etf_pool)[:target_num]
        log.info('rank:',target_list)
        rankFlag = False
        if '563300.XSHG' not in target_list:
            log.info('排名止损，跌出第一')
            rankFlag = True
        if g.stop:
            
            if rankFlag:
                log.info('排名止损，继续保持空仓!当前第一:',target_list)
                return rankFlag
            
            if recentLoss > context.recover_threshold:
                log.info('需要重新建仓了！recentLoss:', recentLoss)
                g.max = endValue
                g.stop = False
                return False
            else:
                log.info('继续保持空仓！recentLoss:', recentLoss)
                return True
        
        if rankFlag:
            log.info('排名止损！开始清仓！当前第一：',target_list)
            g.stop = True
            return True


        if maxLoss < context.stop_loss_threshold or recentLoss < g.recent_loss :
            log.info('需要清仓了！maxLoss：', maxLoss,'recentLoss:',recentLoss)
            g.max = endValue
            g.stop = True
            return True
        return False


def get_average_of_last_n_values(data_dict, n):
    """
    计算字典中最近插入的N个键值对所对应值的均值。

    注意：这个函数依赖于 Python 3.7+ 中字典的插入顺序特性。

    :param data_dict: 字典，键为任意类型，值为数值类型（支持加法和除法运算）。
    :param n: 整数，表示要计算最近插入的键值对所对应值的均值的数量。
    :return: 浮点数，表示最近N个键值对所对应值的均值；如果n超出范围（大于字典长度或小于等于0），则返回None。
    """
    # 检查n是否在有效范围内
    if n <= 0:
        return None

    # 获取字典的键列表（保持插入顺序）
    keys = list(data_dict.keys())

    # 检查n是否大于字典长度
    if n > len(keys):
        return None

    # 获取最近N个键对应的值
    last_n_values = [data_dict[key] for key in keys[-n:]]

    # 计算值的总和
    total_sum = sum(last_n_values)

    # 计算均值
    average = total_sum / n

    # 返回均值
    return average


def get_nth_last_key_value(data_dict, n):
    """
    获取字典中倒数第N个插入的键值对。

    :param data_dict: 字典，键为任意类型，值为对应的任意类型。
    :param n: 整数，表示要获取倒数第几个插入的键值对。
    :return: 一个元组，包含倒数第N个插入的键和值；如果n超出范围，则返回None。
    """
    # 将字典的键保存到一个列表中
    keys = list(data_dict.keys())
    # 检查n是否在有效范围内内
    if n <= 0 or n > len(keys):
        return None
    # 获取倒数第N个键
    nth_last_key = keys[-n]
    # 获取对应的值
    nth_last_value = data_dict[nth_last_key]
    # 返回键值对
    return nth_last_key, nth_last_value
    
def get_rank(etf_pool):
    score_list = []
    for etf in etf_pool:
        df = attribute_history(etf, g.m_days, '1d', ['close'])
        y = df['log'] = np.log(df.close)
        x = df['num'] = np.arange(df.log.size)
        slope, intercept = np.polyfit(x, y, 1)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
        score = annualized_returns * r_squared
        score_list.append(score)
    df = pd.DataFrame(index=etf_pool, data={'score':score_list})
    df = df.sort_values(by='score', ascending=False)
    rank_list = list(df.index)    
    print(df)     
    record(价值 = round(df.loc['510300.XSHG'], 2))
    record(红利 = round(df.loc['515450.XSHG'], 2))
    record(五十 = round(df.loc['510050.XSHG'], 2))
    record(两千 = round(df.loc['563300.XSHG'], 2))

    return rank_list


def _choice_small(context, nchoice):
    # parameters
    index = '399317.XSHE'
    # stocks
    cdata = get_current_data()
    stocks = get_index_stocks(index)
    stocks = [stock for stock in stocks if not stock.startswith('68')]

    # fundamental data
    df = get_fundamentals(query(
        valuation.code,
        valuation.market_cap,
    ).filter(
        valuation.code.in_(stocks),
        valuation.pb_ratio > 0,
        indicator.inc_return > 0,
        indicator.ocf_to_revenue > 0,
    ).order_by(valuation.market_cap.asc()
               ).limit(nchoice)
                          ).dropna().set_index('code')
    stocks = df.index.tolist()
    # report
    df = df.loc[stocks]
    df['name'] = [cdata[s].name for s in df.index]
    log.info('small stocks', len(df), '\n', df.head())
    # reuslt
    return stocks
# end