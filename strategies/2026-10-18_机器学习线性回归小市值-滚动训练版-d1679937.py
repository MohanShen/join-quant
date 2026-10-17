# Clone from JoinQuant
# postId: d1679937d4cb53cd990346dd1230ea2e
# backtestId: 6a41a87e69e75a9ec98b4a90b2349882
# title: 机器学习线性回归小市值-滚动训练版

# ============================================================
# 机器学习线性回归小市值策略 - 滚动训练版
# 核心：每N月滚动训练5组BayesianRidge模型 + 小市值精选
# ============================================================

from jqdata import *
from jqfactor import *
from sklearn.linear_model import BayesianRidge
import numpy as np
import pandas as pd
import datetime

# 初始化函数
def initialize(context):
    # 设定基准
    set_benchmark('000905.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003,
                             close_commission=0.0003, close_today_commission=0,
                             min_commission=5), type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')

    # 初始化全局变量
    g.no_trading_today_signal = False
    g.stock_num = 1
    g.hold_list = []
    g.yesterday_HL_list = []

    # ============ 滚动训练参数 ============
    g.train_frequency_months = 6     # 每6个月重新训练
    g.train_lookback_years = 1       # 训练回看3年
    g.train_period = 'M'             # 训练采样周期: 'M'月 / 'W'周(更慢但数据更多)
    g.min_train_samples = 100        # 最少训练样本数
    g.last_train_month = None        # 上次训练月份(格式'YYYY-MM')
    g.model_list = [None] * 5        # 5个BayesianRidge模型

    # 5组因子名称列表
    g.factor_names_list = [
        ['ARBR', 'SGAI', 'net_profit_to_total_operate_revenue_ttm', 'retained_profit_per_share'],
        ['Price1Y', 'total_profit_to_cost_ratio', 'VOL120'],
        ['price_no_fq', 'total_profit_to_cost_ratio', 'inventory_turnover_rate'],
        ['debt_to_assets', 'operating_cost_to_operating_revenue_ratio', 'DAVOL20', 'price_no_fq', 'sales_growth'],
        ['TVSTD6', 'cashflow_per_share_ttm', 'sharpe_ratio_120', 'non_operating_net_profit_ttm']
    ]

    # 所有去重因子
    g.all_factors = list(set([f for group in g.factor_names_list for f in group]))

    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')
    run_daily(check_and_train, '9:15')
    run_weekly(weekly_adjustment, 1, '9:30')
    run_daily(check_limit_up, '14:00')
    run_daily(close_account, '14:30')
    run_daily(print_position_info, '15:10')


# ================================================================
# 一、滚动训练模块 (复用训练代码)
# ================================================================

def get_period_date(peroid, start_date, end_date):
    """获取指定周期的日期列表 (复用训练代码)"""
    stock_data = get_price('000001.XSHE', start_date, end_date, 'daily', fields=['close'])
    stock_data['date'] = stock_data.index
    period_stock_data = stock_data.resample(peroid).last()
    period_stock_data = period_stock_data.set_index('date').dropna()
    date = period_stock_data.index
    pydate_array = date.to_pydatetime()
    date_only_array = np.vectorize(lambda s: s.strftime('%Y-%m-%d'))(pydate_array)
    date_only_series = pd.Series(date_only_array)
    start_date_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    start_date_dt = start_date_dt - datetime.timedelta(days=1)
    start_date_str = start_date_dt.strftime("%Y-%m-%d")
    date_list = date_only_series.values.tolist()
    date_list.insert(0, start_date_str)
    return date_list


def delect_stop(stocks, beginDate, n=90):
    """去除上市距beginDate不足n天的股票 (复用训练代码)"""
    stockList = []
    beginDate = datetime.datetime.strptime(beginDate, "%Y-%m-%d")
    for stock in stocks:
        start_date = get_security_info(stock).start_date
        if start_date < (beginDate - datetime.timedelta(days=n)).date():
            stockList.append(stock)
    return stockList


def get_stock_train(stockPool, begin_date):
    """获取训练用股票池 (复用训练代码)"""
    if stockPool == 'small_25':
        initial_list = get_index_stocks('000002.XSHG', begin_date) + get_index_stocks('399107.XSHE', begin_date)
        stockList = list(get_fundamentals(
            query(valuation.code, valuation.market_cap).filter(
                valuation.code.in_(initial_list),
                valuation.market_cap < 25
            ).order_by(
                valuation.circulating_market_cap.asc()
            )).code)[:50]
    # 剔除ST股
    st_data = get_extras('is_st', stockList, count=1, end_date=begin_date)
    stockList = [stock for stock in stockList if not st_data[stock][0]]
    # 剔除新股
    stockList = delect_stop(stockList, begin_date)
    return stockList


def get_factor_data(securities_list, date, jqfactors_list):
    """获取因子数据 (复用训练代码)"""
    factor_data = get_factor_values(securities=securities_list,
                                    factors=jqfactors_list,
                                    count=1,
                                    end_date=date)
    df_jq_factor = pd.DataFrame(index=securities_list)
    for i in factor_data.keys():
        df_jq_factor[i] = factor_data[i].iloc[0, :]
    return df_jq_factor


def month_diff(month1, month2):
    """计算两个月份字符串'YYYY-MM'之间的月份差"""
    y1, m1 = int(month1[:4]), int(month1[5:7])
    y2, m2 = int(month2[:4]), int(month2[5:7])
    return (y2 - y1) * 12 + (m2 - m1)


def check_and_train(context):
    """检查是否需要滚动训练"""
    current_month = context.current_dt.strftime('%Y-%m')
    if g.last_train_month is None or month_diff(g.last_train_month, current_month) >= g.train_frequency_months:
        log.info("=" * 40)
        log.info("[%s] 开始滚动训练..." % current_month)
        try:
            train_models(context)
            g.last_train_month = current_month
            for i, model in enumerate(g.model_list):
                if model is not None:
                    coef_dict = dict(zip(g.factor_names_list[i],
                                        [round(c, 6) for c in model.coef_]))
                    log.info("模型%d系数: %s" % (i + 1, str(coef_dict)))
            log.info("滚动训练完成！")
        except Exception as e:
            log.error("训练失败: %s" % str(e))


def train_models(context):
    """执行滚动训练，构建5个BayesianRidge模型"""
    current_date = context.current_dt
    lookback_start = (current_date - datetime.timedelta(days=g.train_lookback_years * 365)).strftime('%Y-%m-%d')
    lookback_end = context.previous_date.strftime('%Y-%m-%d')

    # 获取训练日期列表
    dateList = get_period_date(g.train_period, lookback_start, lookback_end)

    if len(dateList) < 3:
        log.warn("训练日期不足，跳过训练")
        return

    # 构建训练数据
    train_data = pd.DataFrame()
    for i in range(len(dateList) - 1):
        date = dateList[i]
        next_date = dateList[i + 1]
        try:
            stockList = get_stock_train('small_25', date)
            if len(stockList) < 10:
                continue

            # 获取因子数据
            factor_data = get_factor_data(stockList, date, g.all_factors)

            # 计算远期收益率 (与原始训练代码一致: iloc[-1]/iloc[1]-1)
            price_df = get_price(stockList, date, next_date, '1d', 'close',
                                skip_paused=False, fill_paused=True, panel=False)
            if price_df.empty:
                continue

            grp = price_df.groupby('code')['close']
            second_close = grp.nth(1)
            last_close = grp.last()
            pchg = (last_close / second_close - 1).replace([np.inf, -np.inf], np.nan)

            factor_data['pchg'] = pchg
            factor_data['date'] = date
            factor_data = factor_data.dropna(subset=['pchg'])

            train_data = pd.concat([train_data, factor_data])
        except:
            pass

    if train_data.empty or len(train_data) < g.min_train_samples:
        log.warn("训练数据不足(%d条)，跳过训练" % len(train_data))
        return

    # 填充NaN: 按日期分组用中位数填充 (复用训练代码逻辑)
    for col in g.all_factors:
        if col in train_data.columns:
            train_data[col] = train_data.groupby('date')[col].transform(
                lambda x: x.fillna(x.median()))
    train_data = train_data.dropna(subset=g.all_factors)

    y_train = train_data['pchg']

    # 训练5个BayesianRidge模型
    trained_count = 0
    for i, factor_names in enumerate(g.factor_names_list):
        X = train_data[factor_names]
        model = BayesianRidge()
        model.fit(X, y_train)
        g.model_list[i] = model
        trained_count += 1

    log.info("训练样本数: %d, 成功训练模型: %d/5" % (len(train_data), trained_count))


# ================================================================
# 二、选股与交易模块
# ================================================================

def prepare_stock_list(context):
    """准备持仓列表和昨日涨停列表"""
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    # 获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    # 判断今天是否为账户资金再平衡的日期
    g.no_trading_today_signal = today_is_between(context, '04-05', '04-30')


def get_stock_list(context):
    """选股模块 (使用训练好的BayesianRidge模型预测得分)"""
    yesterday = context.previous_date
    today = context.current_dt
    initial_list = get_all_securities('stock', today).index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    final_list = []

    for i, factor_names in enumerate(g.factor_names_list):
        if g.model_list[i] is None:
            continue

        factor_values = get_factor_values(initial_list, factor_names, end_date=yesterday, count=1)
        df = pd.DataFrame(index=initial_list, columns=factor_values.keys())
        for j in range(len(factor_names)):
            df[factor_names[j]] = list(factor_values[factor_names[j]].T.iloc[:, 0])
        df = df.dropna()

        # ========== 核心修改：用模型预测替代固定系数打分 ==========
        df['total_score'] = g.model_list[i].predict(df[factor_names])

        df = df.sort_values(by=['total_score'], ascending=False)
        complex_factor_list = list(df.index)[:int(0.1 * len(list(df.index)))]

        q = query(valuation.code, valuation.circulating_market_cap, indicator.eps).filter(
            valuation.code.in_(complex_factor_list)
        ).order_by(valuation.circulating_market_cap.asc())
        df_fund = get_fundamentals(q)
        df_fund = df_fund[df_fund['eps'] > 0]
        lst = list(df_fund.code)
        lst = filter_paused_stock(lst)
        lst = filter_limitup_stock(context, lst)
        lst = filter_limitdown_stock(context, lst)
        lst = lst[:min(g.stock_num, len(lst))]

        for stock in lst:
            if stock not in final_list:
                final_list.append(stock)

    return final_list


def weekly_adjustment(context):
    """每周调仓"""
    if g.no_trading_today_signal == False:
        target_list = get_stock_list(context)
        # 调仓卖出
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("已持有[%s]" % (stock))
        # 调仓买入
        position_count = len(context.portfolio.positions)
        target_num = len(target_list)
        if target_num > position_count:
            value = context.portfolio.cash / (target_num - position_count)
            for stock in target_list:
                if context.portfolio.positions[stock].total_amount == 0:
                    if open_position(stock, value):
                        if len(context.portfolio.positions) == target_num:
                            break


def check_limit_up(context):
    """检查持仓中的涨停股是否需要卖出"""
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m',
                                    fields=['close', 'high_limit'], skip_paused=False,
                                    fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("[%s]涨停，继续持有" % (stock))


# ================================================================
# 三、过滤函数 (保持不变)
# ================================================================

def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list


def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]


def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list
            if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=375)]


# ================================================================
# 四、交易模块 (保持不变)
# ================================================================

def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)


def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False


def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False


# ================================================================
# 五、其他工具函数 (保持不变)
# ================================================================

def today_is_between(context, start_date, end_date):
    today = context.current_dt.strftime('%m-%d')
    if (start_date <= today) and (today <= end_date):
        return True
    else:
        return False


def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                close_position(position)
                log.info("卖出[%s]" % (stock))


def print_position_info(context):
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：' + str(_trade))
    for position in list(context.portfolio.positions.values()):
        securities = position.security
        cost = position.avg_cost
        price = position.price
        ret = 100 * (price / cost - 1)
        value = position.value
        amount = position.total_amount
