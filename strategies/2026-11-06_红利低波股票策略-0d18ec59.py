# Clone from JoinQuant
# postId: 0d18ec5938cf9d5800eb183a255f1644
# backtestId: dfc3df8ea59058e9addbd90e69223b56
# title: 红利低波股票策略

# -*- coding: utf-8 -*-
"""
聚宽(JoinQuant)策略：红利低波
--------------------------------------------------
筛选：
  1. 上市天数 > 365 天
  2. 最近一年股息率全市场排名前 200
  3. 市盈率 > 0
  4. 最近一年股息率 < 15%
  5. 120 日相对上证指数涨幅 > 0
  6. 剔除 ST（可选剔除北交所/科创板/创业板）
排序：250 日年化波动率升序为主，股息率降序为辅
交易：按 g.freq 设定频率调仓（月/季/半年/年），
      同一行业（聚宽一级行业）持仓数不超过总持仓的 25%

股息率口径（与参考策略一致）：
  股息率 = 近12个月派现总额(万元)/10000(→亿元) / 总市值(亿元)
  数据来源：finance.STK_XR_XD 分红送股表 + valuation.market_cap
"""

import datetime
import numpy as np
import pandas as pd
from jqdata import *   # 提供 finance 模块（STK_XR_XD分红表）


def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)   # 避免使用未来数据
    set_benchmark('000001.XSHG')            # 基准：上证指数
    log.set_level('order', 'error')

    # ==================== 可调参数区 ====================
    g.stock_num       = 10          # 目标持仓数量
    g.industry_pct    = 0.25        # 单一行业最大占比（不超过持仓数的25%）
    g.min_list_days   = 365         # 上市天数下限
    g.dy_top_n        = 200         # 股息率排名取前 N
    g.dy_max          = 0.15        # 股息率上限（小数，0.15 = 15%）
    g.rel_window      = 120         # 相对涨幅窗口（交易日）
    g.vol_window      = 250         # 波动率窗口（交易日）
    g.exclude_bj      = True        # 排除北交所（8/4/92开头）
    g.exclude_kcb     = False        # 排除科创板（688开头）
    g.exclude_cyb     = False       # 排除创业板（30开头）
    g.freq            = 'quarterly' # 调仓频率：'monthly'月度 / 'quarterly'季度 /
                                    #           'half_yearly'半年 / 'yearly'年度
    # ====================================================

    freq_map = {'monthly': 1, 'quarterly': 3, 'half_yearly': 6, 'yearly': 12}
    g.month_interval = freq_map[g.freq]
    g.run_count = 0  # 调仓计数器，用于控制调仓频率

    # 佣金印花税（可按需调整）
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                             open_commission=0.00025, close_commission=0.00025,
                             min_commission=5), type='stock')

    # 每月第 1 个交易日开盘检查是否到调仓时点
    run_monthly(rebalance, monthday=1, time='09:40')


def rebalance(context):
    """按设定频率调仓"""
    g.run_count += 1
    if (g.run_count - 1) % g.month_interval != 0:
        return

    target = get_target_stocks(context)
    if len(target) == 0:
        log.info('本期无符合条件的股票，保持原仓位')
        return

    current_data = get_current_data()

    # 1）卖出：不在目标名单中的持仓全部清仓
    for s in list(context.portfolio.positions.keys()):
        if s not in target and context.portfolio.positions[s].closeable_amount > 0:
            order_target(s, 0)
            log.info('卖出 %s' % s)

    # 2）买入：等权配置（保留2%现金缓冲，避免涨跌停/手续费导致下单失败）
    value_per = context.portfolio.total_value * 0.98 / len(target)
    for s in target:
        if current_data[s].paused:      # 停牌跳过
            log.info('跳过停牌股 %s' % s)
            continue
        order_target_value(s, value_per)

    log.info('本期调仓完成，目标持仓 %d 只：%s' % (len(target), target))


def calc_dividend_fundamentals(context, codes):
    """
    计算股息率并取 PE、市值（参考策略口径）：
      近12个月分红总额(万元) / 10000 → 亿元，除以总市值(亿元) = 股息率(小数)
    返回 DataFrame，index=code，列=[bonus_amount_rmb, market_cap, pe_ratio, dividend_ratio]
    """
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365)

    # 1）分批查询近12个月分红记录（避开单次查询数量限制）
    dfs = []
    for i in range(0, len(codes), 1000):
        batch = codes[i:i + 1000]
        q = query(finance.STK_XR_XD.code,
                  finance.STK_XR_XD.bonus_amount_rmb
                  ).filter(
            finance.STK_XR_XD.a_registration_date >= time0,
            finance.STK_XR_XD.a_registration_date <= time1,
            finance.STK_XR_XD.code.in_(batch))
        dfs.append(finance.run_query(q))
    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 0 else pd.DataFrame()
    if df.empty:
        return pd.DataFrame()
    df = df.fillna(0)
    dividend = df.groupby('code')['bonus_amount_rmb'].sum()   # 单位：万元

    # 2）分批查询市值、市盈率
    temp_list = list(dividend.index)
    caps = []
    for i in range(0, len(temp_list), 1000):
        batch = temp_list[i:i + 1000]
        q = query(valuation.code,
                  valuation.market_cap,
                  valuation.pe_ratio
                  ).filter(valuation.code.in_(batch))
        caps.append(get_fundamentals(q, date=time1))
    cap = pd.concat(caps).set_index('code')

    # 3）合并，计算股息率（小数）
    result = pd.concat([dividend, cap], axis=1, sort=False)
    result = result.dropna()
    result['dividend_ratio'] = (result['bonus_amount_rmb'] / 10000.0) / result['market_cap']
    return result


def get_target_stocks(context):
    """选股主流程：筛选 → 排序 → 行业约束"""
    date = context.previous_date  # 使用前一交易日数据，避免未来函数

    # ---------- 筛选1：上市天数 > 365 天、未退市、板块过滤 ----------
    df = get_all_securities(types=['stock'], date=date)
    df = df[df['start_date'].apply(lambda d: (date - d).days) > g.min_list_days]
    df = df[df['end_date'].apply(lambda d: (d - date).days) > 0]  # 剔除已退市
    codes = [c for c in df.index
             if not (g.exclude_bj  and c[:2] in ('8', '4', '92'))
             and not (g.exclude_kcb and c.startswith('68'))
             and not (g.exclude_cyb and c.startswith('30'))]
    log.info('上市天数+板块过滤后：%d 只' % len(codes))

    # ---------- 筛选6：剔除 ST ----------
    is_st = get_extras('is_st', codes, end_date=date, count=1)
    codes = [c for c in codes if not bool(is_st[c].iloc[-1])]
    log.info('剔除ST后：%d 只' % len(codes))
    if len(codes) == 0:
        return []

    # ---------- 筛选3、4、2：PE>0、0<股息率<15%、股息率前200 ----------
    fund = calc_dividend_fundamentals(context, codes)
    if fund.empty:
        log.info('近12个月无分红记录，无符合条件股票')
        return []
    fund = fund[(fund['pe_ratio'] > 0) &
                (fund['dividend_ratio'] > 0) &
                (fund['dividend_ratio'] < g.dy_max)]
    fund = fund.sort_values('dividend_ratio', ascending=False).head(g.dy_top_n)
    codes = list(fund.index)
    log.info('股息率筛选+前%d后：%d 只' % (g.dy_top_n, len(codes)))
    if len(codes) == 0:
        return []

    # ---------- 筛选5：120日相对上证指数涨幅 > 0 ----------
    idx = get_price('000001.XSHG', end_date=date, count=g.rel_window + 1,
                    fields=['close'], fq=None)['close']
    idx_ret = idx.iloc[-1] / idx.iloc[0] - 1
    px = get_price(codes, end_date=date, count=g.rel_window + 1,
                   fields=['close'], fq='pre', panel=False)
    close = px.pivot_table(index='time', columns='code', values='close')
    stk_ret = close.iloc[-1] / close.iloc[0] - 1
    codes = [c for c in codes
             if not np.isnan(stk_ret.get(c, np.nan)) and (stk_ret[c] - idx_ret) > 0]
    log.info('120日相对涨幅>0后：%d 只' % len(codes))
    if len(codes) == 0:
        return []

    # ---------- 排序1、2：250日波动率升序为主，股息率降序为辅 ----------
    px = get_price(codes, end_date=date, count=g.vol_window + 1,
                   fields=['close'], fq='pre', panel=False)
    close = px.pivot_table(index='time', columns='code', values='close')
    vol = close.pct_change().std() * np.sqrt(250)   # 250日年化波动率
    rank = pd.DataFrame({'vol': vol, 'dy': fund['dividend_ratio']}).dropna()
    rank = rank.sort_values(by=['vol', 'dy'], ascending=[True, False])

    # ---------- 交易2：行业集中度约束（同行业 < 持仓数的25%） ----------
    max_per_ind = max(1, int(round(g.stock_num * g.industry_pct)))
    ind = get_industry(list(rank.index), date=date)
    target, ind_cnt = [], {}
    for s in rank.index:
        try:
            ind_name = ind[s]['jq_l1']['industry_name']
        except Exception:
            ind_name = '未知'
        if ind_cnt.get(ind_name, 0) < max_per_ind:
            target.append(s)
            ind_cnt[ind_name] = ind_cnt.get(ind_name, 0) + 1
        if len(target) >= g.stock_num:
            break

    log.info('行业约束后入选 %d 只' % len(target))
    show = rank.loc[target][['vol', 'dy']].copy()
    show['dy'] = (show['dy'] * 100).round(2)   # 日志中股息率显示为%
    log.info('明细：\n%s' % show.to_string())
    return target