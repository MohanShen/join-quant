# Clone from JoinQuant
# postId: a221d4a4ad678e45b64b09f7dbacce65
# backtestId: a5cd96543b6a572f64fa1f8defc3fa30
# title: 高股息策略 基于芹菜大佬高股息低市盈率高增长的价投策略分析

from jqdata import *
import pandas as pd
import numpy as np
import datetime

def initialize(context):
    # ==============================
    # 基础设置
    # ==============================
    # 基准改成红利低波ETF
    set_benchmark('512890.XSHG')
    
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0))
    
    # 股票手续费
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                             open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='stock')
    
    log.set_level('order', 'error')

    # ==============================
    # 可调参数区
    # 以后你主要改这里
    # ==============================
    g.stock_num = 10                  # 最终持仓股票数量
    g.pre_select_num = 30             # 股息率排序后先保留前多少只
    g.industry_max_num = 2            # 每个行业最多保留几只

    # 基本面筛选参数
    g.pe_min = 0
    g.pe_max = 25
    g.roe_min = 3
    g.revenue_growth_min = 5
    g.profit_growth_min = 11

    # PEG参数
    g.use_peg = True
    g.peg_min = 0.08
    g.peg_max = 1.9

    # 分红参数
    g.dividend_years = 3              # 连续分红年数，同时也是平均股息率统计年数
    g.dividend_min = 0.03             # 平均股息率最低要求，0.03=3%

    # 其它参数
    g.new_stock_days = 375            # 次新股过滤天数
    g.use_industry_limit = True       # 是否启用行业分散
    g.debug_top_n = 10                # 打印前几只股票的平均股息率

    # 全局变量
    g.hold_list = []
    g.high_limit_list = []

    # ==============================
    # 调仓频率设置
    # 默认：月调仓
    # 如果想测试周调仓，把月调仓注释掉，打开周调仓
    # ==============================
    run_daily(prepare_stock_list, time='9:05', reference_security='512890.XSHG')

    # 默认月调仓
    run_monthly(monthly_adjustment, monthday=1, time='9:30', reference_security='512890.XSHG')

    # 如果以后你想改成周调仓，把上面这句注释掉，打开下面这句
    # run_weekly(weekly_adjustment, weekday=1, time='9:30', reference_security='512890.XSHG')

    run_daily(check_limit_up, time='14:00', reference_security='512890.XSHG')
    run_daily(print_position_info, time='15:10', reference_security='512890.XSHG')


# ==============================
# 每日准备：记录持仓和昨日涨停股票
# ==============================
def prepare_stock_list(context):
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        g.hold_list.append(position.security)

    if len(g.hold_list) > 0:
        df = get_price(
            g.hold_list,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1,
            panel=False,
            fill_paused=False
        )
        df = df[df['close'] == df['high_limit']]
        g.high_limit_list = list(df.code)
    else:
        g.high_limit_list = []


# ==============================
# 月调仓
# ==============================
def monthly_adjustment(context):
    adjust_position_main(context)


# ==============================
# 周调仓
# 如果以后切换周调仓，就在initialize里启用
# ==============================
def weekly_adjustment(context):
    adjust_position_main(context)


# ==============================
# 调仓主逻辑
# ==============================
def adjust_position_main(context):
    # 获取目标股票池
    target_list = get_stock_list(context)

    # 再做交易层过滤：停牌、涨停、跌停
    target_list = filter_paused_stock(target_list)
    target_list = filter_limitup_stock(context, target_list)
    target_list = filter_limitdown_stock(context, target_list)

    # 最终只保留前g.stock_num只
    target_list = target_list[:min(g.stock_num, len(target_list))]

    log.info("最终目标持仓列表：%s" % target_list)

    # ==============================
    # 先卖出：不在目标池里的股票卖掉
    # 但如果是昨日涨停股票，就暂时保留，交给 check_limit_up 处理
    # ==============================
    for stock in g.hold_list:
        if (stock not in target_list) and (stock not in g.high_limit_list):
            log.info("卖出[%s]" % stock)
            position = context.portfolio.positions[stock]
            close_position(position)
        else:
            log.info("继续持有[%s]" % stock)

    # ==============================
    # 再买入：买入目标池中还没有持仓的股票
    # 这里已经改成不会触发positions warning的写法
    # ==============================
    position_count = len(context.portfolio.positions)
    target_num = len(target_list)

    if target_num > position_count:
        value = context.portfolio.cash / (target_num - position_count)

        for stock in target_list:
            # 关键修改：不用再直接访问 positions[stock]
            if stock not in context.portfolio.positions:
                if open_position(stock, value):
                    if len(context.portfolio.positions) == target_num:
                        break


# ==============================
# 核心选股函数
# 流程：
# 1. 基础过滤
# 2. 先基本面筛选
# 3. 连续3年分红筛选
# 4. 每年单独计算股息率，再取平均
# 5. 平均股息率过滤并排序
# 6. 行业分散
# ==============================
def get_stock_list(context):
    yesterday = context.previous_date

    # 1. 全市场股票
    stock_list = get_all_securities('stock', yesterday).index.tolist()

    # 2. 基础过滤
    stock_list = filter_kcbj_stock(stock_list)
    stock_list = filter_new_stock(context, stock_list, g.new_stock_days)
    stock_list = filter_st_stock(stock_list)
    log.info("基础过滤后数量：%d" % len(stock_list))

    # 3. 先基本面筛选
    stock_list = filter_by_fundamentals(context, stock_list)
    log.info("基本面筛选后数量：%d" % len(stock_list))
    if len(stock_list) == 0:
        return []

    # 4. 连续3年分红筛选
    stock_list = filter_by_continuous_dividend(context, stock_list, g.dividend_years)
    log.info("连续分红筛选后数量：%d" % len(stock_list))
    if len(stock_list) == 0:
        return []

    # 5. 每年单独计算股息率，再取平均
    dividend_df = calculate_average_dividend_ratio(context, stock_list, g.dividend_years)
    if len(dividend_df) == 0:
        return []

    # 6. 平均股息率下限过滤
    dividend_df = dividend_df[dividend_df['avg_dividend_ratio'] >= g.dividend_min]
    log.info("股息率过滤后数量：%d" % len(dividend_df))
    if len(dividend_df) == 0:
        return []

    # 打印前几只，方便观察
    top_n = min(g.debug_top_n, len(dividend_df))
    for stock in list(dividend_df.index)[:top_n]:
        log.info("股票[%s] 平均股息率=%.2f%%" % (stock, dividend_df.loc[stock, 'avg_dividend_ratio'] * 100))

    # 7. 先保留股息率前N只
    stock_list = list(dividend_df.index)[:g.pre_select_num]

    # 8. 行业分散
    if g.use_industry_limit:
        stock_list = industry_diversify(stock_list, g.industry_max_num, yesterday)

    return stock_list


# ==============================
# 基本面筛选
# 如果以后想放宽或收紧条件，主要改 initialize 里的参数
# ==============================
def filter_by_fundamentals(context, stock_list):
    yesterday = context.previous_date

    if g.use_peg:
        df = get_fundamentals(query(
            valuation.code,
            valuation.pe_ratio,
            indicator.inc_return,
            indicator.inc_total_revenue_year_on_year,
            indicator.inc_net_profit_year_on_year
        ).filter(
            valuation.code.in_(stock_list),
            valuation.pe_ratio > g.pe_min,
            valuation.pe_ratio < g.pe_max,
            indicator.inc_return > g.roe_min,
            indicator.inc_total_revenue_year_on_year > g.revenue_growth_min,
            indicator.inc_net_profit_year_on_year > g.profit_growth_min,
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year > g.peg_min,
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year < g.peg_max
        ), date=yesterday)
    else:
        df = get_fundamentals(query(
            valuation.code,
            valuation.pe_ratio,
            indicator.inc_return,
            indicator.inc_total_revenue_year_on_year,
            indicator.inc_net_profit_year_on_year
        ).filter(
            valuation.code.in_(stock_list),
            valuation.pe_ratio > g.pe_min,
            valuation.pe_ratio < g.pe_max,
            indicator.inc_return > g.roe_min,
            indicator.inc_total_revenue_year_on_year > g.revenue_growth_min,
            indicator.inc_net_profit_year_on_year > g.profit_growth_min
        ), date=yesterday)

    return list(df.code)


# ==============================
# 连续N年分红筛选
# 要求每一年都至少发生过一次分红
# ==============================
def filter_by_continuous_dividend(context, stock_list, years):
    yesterday = context.previous_date
    qualified = []

    for stock in stock_list:
        is_ok = True

        for i in range(years):
            end_date = yesterday - datetime.timedelta(days=i * 365)
            start_date = yesterday - datetime.timedelta(days=(i + 1) * 365)

            q = query(
                finance.STK_XR_XD.code,
                finance.STK_XR_XD.a_registration_date,
                finance.STK_XR_XD.bonus_amount_rmb
            ).filter(
                finance.STK_XR_XD.code == stock,
                finance.STK_XR_XD.a_registration_date >= start_date,
                finance.STK_XR_XD.a_registration_date <= end_date,
                finance.STK_XR_XD.bonus_amount_rmb > 0
            )

            df = finance.run_query(q)

            if len(df) == 0:
                is_ok = False
                break

        if is_ok:
            qualified.append(stock)

    return qualified


# ==============================
# 获取某一年区间内的分红总额
# 返回：按股票代码汇总后的DataFrame
# ==============================
def get_dividend_year_data(stock_list, start_date, end_date):
    interval = 1000
    all_df = pd.DataFrame()

    for i in range(0, len(stock_list), interval):
        sub_list = stock_list[i:i + interval]

        q = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.a_registration_date,
            finance.STK_XR_XD.bonus_amount_rmb
        ).filter(
            finance.STK_XR_XD.a_registration_date >= start_date,
            finance.STK_XR_XD.a_registration_date <= end_date,
            finance.STK_XR_XD.code.in_(sub_list)
        )

        df = finance.run_query(q)

        if len(df) > 0:
            all_df = pd.concat([all_df, df], axis=0)

    if len(all_df) == 0:
        return pd.DataFrame(columns=['bonus_amount_rmb'])

    all_df = all_df.fillna(0)
    all_df = all_df.groupby('code').sum()
    return all_df


# ==============================
# 每年单独计算股息率，再取平均
# 计算口径参考你原始可运行代码：
# dividend_ratio = (bonus_amount_rmb / 10000) / market_cap
# ==============================
def calculate_average_dividend_ratio(context, stock_list, years):
    yesterday = context.previous_date
    total_df = pd.DataFrame(index=stock_list)

    for i in range(years):
        end_date = yesterday - datetime.timedelta(days=i * 365)
        start_date = yesterday - datetime.timedelta(days=(i + 1) * 365)

        # 1. 获取这一年分红总额
        dividend_df = get_dividend_year_data(stock_list, start_date, end_date)

        # 2. 获取该年末总市值
        q = query(
            valuation.code,
            valuation.market_cap
        ).filter(
            valuation.code.in_(stock_list)
        )
        cap_df = get_fundamentals(q, date=end_date)

        if len(cap_df) == 0:
            continue

        cap_df = cap_df.set_index('code')

        # 3. 合并后计算这一年的股息率
        year_df = pd.concat([dividend_df, cap_df], axis=1, sort=False)
        year_df = year_df.fillna(0)

        year_col = 'dividend_ratio_%d' % (i + 1)
        year_df[year_col] = (year_df['bonus_amount_rmb'] / 10000.0) / year_df['market_cap']

        total_df = total_df.join(year_df[[year_col]], how='left')

    if len(total_df.columns) == 0:
        return pd.DataFrame()

    total_df = total_df.fillna(0)

    ratio_cols = [col for col in total_df.columns if 'dividend_ratio_' in col]
    total_df['avg_dividend_ratio'] = total_df[ratio_cols].mean(axis=1)

    total_df = total_df.sort_values(by='avg_dividend_ratio', ascending=False)

    return total_df


# ==============================
# 行业分散
# 每个申万一级行业最多保留 max_num 只
# 由于输入列表已经按股息率降序排列
# 所以会优先保留每个行业股息率更高的股票
# ==============================
def industry_diversify(stock_list, max_num, date):
    industry_count = {}
    final_list = []

    for stock in stock_list:
        try:
            industry_info = get_industry(stock, date=date)
            if industry_info is None:
                continue

            sw_l1 = industry_info[stock].get('sw_l1', None)
            if sw_l1 is None:
                continue

            industry_name = sw_l1['industry_name']

            if industry_name not in industry_count:
                industry_count[industry_name] = 0

            if industry_count[industry_name] < max_num:
                final_list.append(stock)
                industry_count[industry_name] += 1

        except:
            continue

    return final_list


# ==============================
# 昨日涨停打开卖出
# ==============================
def check_limit_up(context):
    if g.high_limit_list != []:
        for stock in g.high_limit_list:
            current_data = get_price(
                stock,
                end_date=context.current_dt,
                frequency='1m',
                fields=['close', 'high_limit'],
                skip_paused=False,
                fq='pre',
                count=1,
                panel=False,
                fill_paused=True
            )

            if len(current_data) > 0:
                if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                    log.info("[%s]涨停打开，卖出" % stock)
                    position = context.portfolio.positions[stock]
                    close_position(position)
                else:
                    log.info("[%s]涨停，继续持有" % stock)


# ==============================
# 过滤函数
# ==============================
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

def filter_limitup_stock(context, stock_list):
    if len(stock_list) == 0:
        return stock_list

    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()

    return [stock for stock in stock_list
            if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]

def filter_limitdown_stock(context, stock_list):
    if len(stock_list) == 0:
        return stock_list

    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()

    return [stock for stock in stock_list
            if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]

def filter_kcbj_stock(stock_list):
    return [stock for stock in stock_list
            if not (stock[0] == '4' or stock[0] == '8' or stock[:2] == '68')]

def filter_new_stock(context, stock_list, days):
    yesterday = context.previous_date
    return [stock for stock in stock_list
            if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=days)]


# ==============================
# 交易函数
# ==============================
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % security)
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)

def open_position(security, value):
    order = order_target_value_(security, value)
    if order is not None and order.filled > 0:
        return True
    return False

def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order is not None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False


# ==============================
# 打印持仓信息
# ==============================
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

        print('代码:{}'.format(securities))
        print('成本价:{}'.format(format(cost, '.2f')))
        print('现价:{}'.format(price))
        print('收益率:{}%'.format(format(ret, '.2f')))
        print('持仓(股):{}'.format(amount))
        print('市值:{}'.format(format(value, '.2f')))
        print('———————————————————————————————————')
    print('———————————————————————————————————————分割线————————————————————————————————————————')