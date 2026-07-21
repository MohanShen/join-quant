# Clone from JoinQuant
# postId: 93379f98cd48e1246cb0396365872839
# backtestId: bd10862dd353c3405f7f30ecfc8a0eab
# title: 低换手红利策略

# 股息率TTM + 20日换手率 双因子轮动策略
# 每25个交易日轮动一次，选取综合排名最靠前的10只股票
# 排名规则：
#   1. 排除科创板，获取A股股票的股息率TTM和20日换手率
#   2. 股息率TTM从大到小排名，20日换手率从小到大排名，加权相加作为综合排名

from jqdata import *
from jqdata import finance
import pandas as pd
import numpy as np
from datetime import timedelta


def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 避免使用未来数据
    set_option('avoid_future_data', True)
    # 设置滑点
    set_slippage(FixedSlippage(0.02))
    # 设置交易成本
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=2.5/10000,
        close_commission=2.5/10000,
        min_commission=5
    ), type='stock')
    # 过滤低级别日志
    log.set_level('order', 'error')

    # 策略参数
    g.stock_num = 10        # 持股数量
    g.rebalance_days = 25   # 轮动周期（交易日）
    g.day_count = 0         # 交易日计数器
    g.turnover_window = 20  # 换手率统计窗口

    # 收盘前10分钟检查是否到达轮动日
    run_daily(check_rebalance, time='14:50')


def check_rebalance(context):
    """收盘前10分钟检查是否到达轮动日，执行调仓"""
    g.day_count += 1
    if g.day_count % g.rebalance_days == 1 or g.day_count == 1:
        rebalance(context)


def get_stock_pool(context):
    """获取股票池：全A股，排除科创板、停牌"""
    curr_date = context.current_dt.date()
    all_stocks = get_all_securities(['stock'], date=curr_date)

    # 排除科创板（688开头）
    all_stocks = all_stocks[~all_stocks.index.str.startswith('688')]

    stock_list = list(all_stocks.index)

    # 排除停牌
    current_data = get_current_data()
    stock_list = [s for s in stock_list if not current_data[s].paused]

    return stock_list


def get_dividend_yield_ttm(stock_list, date):
    """
    计算股息率TTM：
    从 finance.STK_XR_XD 表获取过去12个月内已实施的分红数据，
    股息率TTM = 近12个月每股累计派息(元) / 当前股价
    """
    # 获取过去12个月已实施分红的数据
    start_date = date - timedelta(days=365)
    q = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.bonus_ratio_rmb,          # 每10股派息(元)
        finance.STK_XR_XD.a_registration_date,       # A股股权登记日
        finance.STK_XR_XD.plan_progress
    ).filter(
        finance.STK_XR_XD.code.in_(stock_list),
        finance.STK_XR_XD.a_registration_date >= str(start_date),
        finance.STK_XR_XD.a_registration_date <= str(date),
        finance.STK_XR_XD.plan_progress == '实施方案'
    )

    # 分批查询（每次最多4000行）
    df_all = []
    offset = 0
    while True:
        df_batch = finance.run_query(q.offset(offset).limit(4000))
        if df_batch is None or len(df_batch) == 0:
            break
        df_all.append(df_batch)
        if len(df_batch) < 4000:
            break
        offset += 4000

    if not df_all:
        log.warn('未获取到分红数据')
        return pd.Series(dtype=float)

    df_div = pd.concat(df_all, ignore_index=True)

    # 过滤掉无派息数据的行
    df_div = df_div[df_div['bonus_ratio_rmb'].notna() & (df_div['bonus_ratio_rmb'] > 0)]
    if len(df_div) == 0:
        return pd.Series(dtype=float)

    # 每10股派息(元) -> 每股派息(元)
    df_div['dps'] = df_div['bonus_ratio_rmb'] / 10.0

    # 按股票汇总近12个月的每股累计派息
    dps_ttm = df_div.groupby('code')['dps'].sum()

    # 获取当前股价（用前一日收盘价）
    price_stocks = list(dps_ttm.index)
    price_df = get_price(price_stocks, end_date=date, frequency='daily',
                         fields=['close'], count=1, panel=False)
    price_dict = dict(zip(price_df['code'], price_df['close']))

    # 计算股息率TTM = 每股派息TTM / 股价
    dy_dict = {}
    for stock in price_stocks:
        if stock in price_dict and price_dict[stock] > 0:
            dy_dict[stock] = dps_ttm[stock] / price_dict[stock]

    return pd.Series(dy_dict)


def calc_factor_rank(context, stock_list):
    """计算双因子综合排名"""
    prev_date = context.previous_date

    # --- 获取股息率TTM ---
    dy_series = get_dividend_yield_ttm(stock_list, prev_date)
    log.info(f'获取到股息率TTM数据: {len(dy_series)} 只')

    if len(dy_series) == 0:
        log.warn('无股息率数据')
        return []

    # --- 获取20日平均换手率 ---
    turnover_dict = {}
    batch_size = 500
    for i in range(0, len(stock_list), batch_size):
        batch = stock_list[i:i + batch_size]
        df_val = get_valuation(
            batch,
            end_date=prev_date,
            count=g.turnover_window,
            fields=['code', 'turnover_ratio']
        )
        if df_val is not None and len(df_val) > 0:
            avg_turnover = df_val.groupby('code')['turnover_ratio'].mean()
            turnover_dict.update(avg_turnover.to_dict())

    turnover_series = pd.Series(turnover_dict)
    log.info(f'获取到换手率数据: {len(turnover_series)} 只')

    # --- 合并数据，构建排名 ---
    df = pd.DataFrame({
        'dy_ttm': dy_series,
        'turnover_20d': turnover_series,
    })

    # 去除含空值的行
    df = df.dropna()
    # 排除股息率为0或负的
    df = df[df['dy_ttm'] > 0]

    if len(df) == 0:
        log.warn('合并后无有效数据')
        return []

    log.info(f'有效双因子数据: {len(df)} 只')

    # 股息率TTM 从大到小排名（越大越好，排名数值越小越好）
    df['dy_rank'] = df['dy_ttm'].rank(ascending=False, method='min')

    # 20日换手率 从小到大排名（越小越好，排名数值越小越好）
    df['turnover_rank'] = df['turnover_20d'].rank(ascending=True, method='min')

    # 综合排名 = 加权排名之和，越小越好
    df['total_rank'] = df['dy_rank'] * 3 + df['turnover_rank'] * 3

    # 按综合排名排序，取前N只
    df = df.sort_values('total_rank', ascending=True)
    target_stocks = list(df.index[:g.stock_num])

    log.info('=== 选股结果 ===')
    for s in target_stocks:
        log.info(f'{s}: 股息率TTM={df.loc[s, "dy_ttm"]:.4f}, '
                 f'20日换手率={df.loc[s, "turnover_20d"]:.2f}%, '
                 f'股息率排名={int(df.loc[s, "dy_rank"])}, '
                 f'换手率排名={int(df.loc[s, "turnover_rank"])}, '
                 f'综合排名={int(df.loc[s, "total_rank"])}')

    return target_stocks


def rebalance(context):
    """执行调仓"""
    log.info(f'===== 第{g.day_count}个交易日，执行调仓 =====')

    # 获取股票池
    stock_list = get_stock_pool(context)
    log.info(f'股票池数量: {len(stock_list)}')

    # 计算排名，选出目标股票
    target_list = calc_factor_rank(context, stock_list)

    if len(target_list) == 0:
        log.warn('未选出目标股票，跳过调仓')
        return

    # 获取当前持仓
    current_data = get_current_data()
    hold_stocks = list(context.portfolio.positions.keys())

    # --- 卖出不在目标列表中的持仓 ---
    for stock in hold_stocks:
        if stock not in target_list:
            if not current_data[stock].paused:
                order_target_value(stock, 0)
                log.info(f'卖出: {stock}')

    # --- 等权买入目标股票 ---
    # 计算每只股票的目标市值
    total_value = context.portfolio.total_value
    target_value = total_value / g.stock_num

    for stock in target_list:
        if not current_data[stock].paused:
            order_target_value(stock, target_value)
            log.info(f'买入/调整: {stock}, 目标市值: {target_value:.2f}')
