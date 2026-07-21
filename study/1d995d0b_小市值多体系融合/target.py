# Clone from JoinQuant
# postId: 1d995d0b92617b5e14e67629679ac7da
# backtestId: 0de1b99f7ecd7bfa539da34c4e8e8b85
# title: 小市值多体系融合版本，不择时不风控也能60%+

# -*- coding: utf-8 -*-
# 双方法整合版：排除科创板+创业板，保留北交所
# 方法1：ML因子打分（3因子线性回归）
# 方法2：股息率 × 换手率波动率因子
# 合并：ML优先 + 因子补充 + 去重 -> 统一交易
# 克隆来源：https://www.joinquant.com/post/40346
from jqdata import *
from jqfactor import get_factor_values
import numpy as np
import pandas as pd
import datetime                          # ← 加这一行

# ===================== 初始化 =====================
def initialize(context):
    set_benchmark('000905.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003,
                             close_commission=0.0003, close_today_commission=0,
                             min_commission=5), type='stock')
    log.set_level('order', 'error')

    # === 公共参数 ===
    g.stock_num = 10
    g.limit_days = 20
    g.limit_up_list = []
    g.hold_list = []
    g.history_hold_list = []
    g.not_buy_again_list = []

    # === 方法1：ML因子参数（3因子线性回归）===
    g.ml_factor_list = [
        'price_no_fq',                    # 不复权价格因子
        'total_profit_to_cost_ratio',     # 成本费用利润率
        'inventory_turnover_rate',        # 存货周转率
    ]
    g.ml_coef_list = [
        -6.123355346008858e-05,           # price_no_fq 系数
        -0.002579342458393642,            # total_profit_to_cost_ratio 系数
        -2.194257357346814e-06,           # inventory_turnover_rate 系数
    ]

    # === 方法2：因子筛选参数 ===
    g.jqfactor = 'turnover_volatility'    # 换手率波动率
    g.jqfactor_sort = False               # False=降序(选大)

    # === 定时运行 ===
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    run_weekly(weekly_adjustment, weekday=1, time='9:30', reference_security='000300.XSHG')
    run_daily(check_limit_up, time='14:00', reference_security='000300.XSHG')
    run_daily(print_position_info, time='15:10', reference_security='000300.XSHG')


# ===================== 板过滤（版本2：保留北交所） =====================
def filter_board_v2(stock_list):
    """
    保留：主板(60/00) + 北交所(4/8)
    排除：科创板(68)、创业板(30)
    """
    return [s for s in stock_list if not (s[:2] == '68' or s[:2] == '30')]


# ===================== 方法1：ML因子选股（3因子线性回归） =====================
def get_ml_stock_list(context):
    """
    方法1：ML因子打分排序
    流程：板过滤 → 次新股 → ST → 3因子打分前10% → 流通市值升序 → EPS>0
    """
    yesterday = context.previous_date
    initial_list = get_all_securities().index.tolist()
    initial_list = filter_board_v2(initial_list)
    initial_list = filter_new_stock(context, initial_list, 375)
    initial_list = filter_st_stock(initial_list)

    # 获取3因子值
    factor_values = get_factor_values(initial_list, g.ml_factor_list, end_date=yesterday, count=1)
    df = pd.DataFrame(index=initial_list, columns=factor_values.keys())
    for f_name in g.ml_factor_list:
        df[f_name] = list(factor_values[f_name].T.iloc[:, 0])
    df = df.dropna()

    # 加权总分（分数越高=预测未来收益越高）
    df['ml_score'] = (
        g.ml_coef_list[0] * df[g.ml_factor_list[0]] +
        g.ml_coef_list[1] * df[g.ml_factor_list[1]] +
        g.ml_coef_list[2] * df[g.ml_factor_list[2]]
    )
    df = df.sort_values(by='ml_score', ascending=False)  # 降序
    ml_top_list = list(df.index)[:int(0.1 * len(df))]    # 取top 10%

    # 流通市值升序 + EPS>0
    q = query(valuation.code, valuation.circulating_market_cap, indicator.eps).filter(
        valuation.code.in_(ml_top_list)
    ).order_by(valuation.circulating_market_cap.asc())
    df2 = get_fundamentals(q, date=yesterday)
    df2 = df2[df2['eps'] > 0]
    final_list = list(df2.code)
    print('方法1(ML)选股数: {}'.format(len(final_list)))
    return final_list


# ===================== 方法2：股息率×因子选股 =====================
def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2):
    """股息率筛选：取近一年分红/总市值，按区间截取"""
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365)
    interval = 1000
    list_len = len(stock_list)

    q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date,
              finance.STK_XR_XD.bonus_amount_rmb).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)
    if list_len > interval:
        for i in range(list_len // interval):
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date,
                      finance.STK_XR_XD.bonus_amount_rmb).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(
                    stock_list[interval * (i + 1):min(list_len, interval * (i + 2))]))
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    dividend = df.fillna(0).set_index('code')
    dividend = dividend.groupby('code').sum()
    temp_list = list(dividend.index)

    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1).set_index('code')
    DR = pd.concat([dividend, cap], axis=1, sort=False)
    DR['dividend_ratio'] = (DR['bonus_amount_rmb'] / 10000) / DR['market_cap']
    DR = DR.sort_values(by=['dividend_ratio'], ascending=sort)
    return list(DR.index)[int(p1 * len(DR)):int(p2 * len(DR))]


def get_factor_filter_list(context, stock_list, jqfactor, sort, p1, p2):
    """单因子值百分比截取"""
    yesterday = context.previous_date
    score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
    df = pd.DataFrame({'code': stock_list, 'score': score_list}).dropna()
    df.sort_values(by='score', ascending=sort, inplace=True)
    return list(df.code)[int(p1 * len(df)):int(p2 * len(df))]


def get_factor_stock_list(context):
    """
    方法2：股息率 + 因子 + 市值轮动
    流程：板过滤 → 次新股 → ST → 股息率top50% → 因子top50% → 流通市值升序
    """
    yesterday = context.previous_date
    initial_list = get_all_securities().index.tolist()
    initial_list = filter_board_v2(initial_list)
    initial_list = filter_new_stock(context, initial_list, 375)
    initial_list = filter_st_stock(initial_list)

    dr_list = get_dividend_ratio_filter_list(context, initial_list, False, 0, 0.5)
    print('方法2-股息率筛选后: {}'.format(len(dr_list)))

    x_list = get_factor_filter_list(context, dr_list, g.jqfactor, g.jqfactor_sort, 0, 0.5)
    print('方法2-因子筛选后: {}'.format(len(x_list)))

    q = query(valuation.code, valuation.circulating_market_cap).filter(
        valuation.code.in_(x_list)
    ).order_by(valuation.circulating_market_cap.asc())
    df = get_fundamentals(q, date=yesterday)
    final_list = list(df.code)[:15]
    print('方法2(因子)选股数: {}'.format(len(final_list)))
    return final_list


# ===================== 合并选股（ML优先 + 因子补充 + 去重） =====================
def get_combined_stock_list(context):
    """
    双方法合并：交叉交替插入 + 去重
    ML与因子列表地位平等，轮询取数：
        result = [ML[0], Factor[0], ML[1], Factor[1], ML[2], Factor[2], ...]
    遇重复跳过，直至取满 g.stock_num 只
    """
    ml_list = get_ml_stock_list(context)
    factor_list = get_factor_stock_list(context)

    combined = []
    seen = set()
    max_len = max(len(factor_list),len(ml_list) )
    for i in range(max_len):
        # 先从因子取
        if i < len(factor_list) and factor_list[i] not in seen:
            combined.append(factor_list[i])
            seen.add(factor_list[i])
        # 再从ML取
        if i < len(ml_list) and ml_list[i] not in seen:
            combined.append(ml_list[i])
            seen.add(ml_list[i])
        # 够数就停
        if len(combined) >= g.stock_num:
            break

    final = combined[:g.stock_num]
    print('合并选股列表(前{}只): {}'.format(len(final), [_fmt(s) for s in final]))
    return final


# ===================== 盘前准备 =====================
def prepare_stock_list(context):
    g.hold_list = [s for s in context.portfolio.positions]
    g.history_hold_list.append(g.hold_list)
    if len(g.history_hold_list) >= g.limit_days:
        g.history_hold_list = g.history_hold_list[-g.limit_days:]
    temp_set = set()
    for hold_list in g.history_hold_list:
        for stock in hold_list:
            temp_set.add(stock)
    g.not_buy_again_list = list(temp_set)

    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.high_limit_list = list(df.code)
    else:
        g.high_limit_list = []


# ===================== 周调仓（使用合并选股结果） =====================
def weekly_adjustment(context):
    target_list = get_combined_stock_list(context)
    target_list = filter_paused_stock(target_list)
    target_list = filter_limitup_stock(context, target_list)
    target_list = filter_limitdown_stock(context, target_list)

    # 卖出不在目标中的持仓（涨停持有的除外）
    for stock in g.hold_list:
        if stock not in target_list and stock not in g.high_limit_list:
            log.info("卖出[%s]" % (stock))
            close_position(context.portfolio.positions[stock])
        else:
            log.info("已持有[%s]" % (stock))

    # 买入目标中未持仓的
    position_count = len(context.portfolio.positions)
    target_num = len(target_list)
    if target_num > position_count:
        value = context.portfolio.cash / (target_num - position_count)
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
                if open_position(stock, value):
                    if len(context.portfolio.positions) == target_num:
                        break


# ===================== 涨停检查 =====================
def check_limit_up(context):
    now_time = context.current_dt
    if g.high_limit_list:
        for stock in g.high_limit_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m',
                                     fields=['close', 'high_limit'], skip_paused=False,
                                     fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                close_position(context.portfolio.positions[stock])
            else:
                log.info("[%s]涨停，继续持有" % (stock))


# ===================== 过滤辅助函数 =====================
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].paused]

def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [s for s in stock_list
            if not current_data[s].is_st
            and 'ST' not in current_data[s].name
            and '*' not in current_data[s].name
            and '退' not in current_data[s].name]

def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [s for s in stock_list if s in context.portfolio.positions.keys()
            or last_prices[s][-1] < current_data[s].high_limit]

def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [s for s in stock_list if s in context.portfolio.positions.keys()
            or last_prices[s][-1] > current_data[s].low_limit]

def filter_new_stock(context, stock_list, d):
    yesterday = context.previous_date
    return [s for s in stock_list
            if not yesterday - get_security_info(s).start_date < datetime.timedelta(days=d)]


# ===================== 交易函数 =====================
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)

def open_position(security, value):
    order = order_target_value_(security, value)
    return order is not None and order.filled > 0

def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    return order is not None and order.status == OrderStatus.held and order.filled == order.amount


# ===================== 辅助工具 =====================
def _fmt(code):
    try:
        info = get_security_info(code)
        return '{}({})'.format(code[:6], info.display_name)
    except:
        return code[:6]


# ===================== 持仓信息打印 =====================
def print_position_info(context):
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：' + str(_trade))
    for position in list(context.portfolio.positions.values()):
        s = position.security
        cost = position.avg_cost
        price = position.price
        ret = 100 * (price / cost - 1)
        value = position.value
        amount = position.total_amount
        print('代码:{}'.format(s))
        print('成本价:{:.2f}'.format(cost))
        print('现价:{}'.format(price))
        print('收益率:{:.2f}%'.format(ret))
        print('持仓(股):{}'.format(amount))
        print('市值:{:.2f}'.format(value))
        print('———————————————————————————————————')
    print('———————————————————————————————————————分割线————————————————————————————————————————')

# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
except NameError:
    pass
# ===== END OVERRIDE =====
