# Clone from JoinQuant
# postId: b6739620a4966a7e4292c3fccf20bca9
# backtestId: 3d8f7bfb36b4ab9c32ce40ee5c25339c
# title: 通过ai搞了一个简单策略

# -*- coding: utf-8 -*-
"""
多因子选股策略 —— 信号增强版（使用聚宽 residual_volatility）
"""

from jqdata import *
from jqfactor import get_factor_values
import pandas as pd
import numpy as np
from collections import deque


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.001))
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0.001,
                  open_commission=0.0003, close_commission=0.0003,
                  close_today_commission=0, min_commission=5),
        type='stock'
    )

    g.stock_num = 10
    g.factor_weights = {
        'market_cap':          -0.50,
        'roe_ttm':              0.20,
        'gross_profit_ttm':     0.05,
        'net_profit_growth_rate': 0.05,
        'quick_ratio':          0.10,
        'cash_flow_to_price_ratio': 0.05,
        'momentum':             0.05,
        'VOL20':               -0.05,                # 20日平均换手率
        'residual_volatility': -0.10,                # 残差波动率（聚宽因子）
        'return_5d':           -0.05,                # 5日反转（自算）
    }
    g.max_turnover = 20.0                           # 换手率过滤阈值（%）
    g.stop_loss_ratio = 0.15
    g.stock_high = {}
    g.rebalance_days = 7
    g.empty_months = [1, 4, 12]

    # 动态权重参数
    g.ic_window = 24
    g.ic_data = deque(maxlen=g.ic_window)
    g.pending_factor_df = None
    g.pending_date = None
    g.dynamic_weights = None

    g.last_rebalance_date = None
    g.DIAG_MODE = True

    log.set_level('order', 'error')
    run_daily(main, time='14:50')


def main(context):
    current_month = context.current_dt.month
    if current_month in g.empty_months:
        for stock in list(context.portfolio.positions.keys()):
            order_target_value(stock, 0)
        g.stock_high.clear()
        g.last_rebalance_date = context.current_dt.date()
        return

    if not is_rebalance_day(context):
        return

    log.info('='*50)
    log.info(f'调仓日期：{context.current_dt.strftime("%Y-%m-%d")}')
    log.info('='*50)

    update_dynamic_weights(context)

    stock_pool = get_filtered_stock_pool(context)
    if len(stock_pool) == 0:
        log.warning('无符合条件的股票')
        g.last_rebalance_date = context.current_dt.date()
        return

    try:
        factor_df = get_raw_factors(stock_pool, context)
    except Exception as e:
        log.error(f'获取因子失败：{e}')
        g.last_rebalance_date = context.current_dt.date()
        return

    if factor_df is None or factor_df.empty:
        log.warning('因子数据为空')
        g.last_rebalance_date = context.current_dt.date()
        return

    g.pending_factor_df = factor_df.copy()
    g.pending_date = context.current_dt

    scores = calculate_composite_score(factor_df, context)
    if scores is None or len(scores) == 0:
        log.warning('因子计算无结果')
        g.last_rebalance_date = context.current_dt.date()
        return

    target_stocks = scores.nlargest(g.stock_num).index.tolist()
    target_stocks = filter_paused_stocks(target_stocks, context)

    if len(target_stocks) == 0:
        log.warning('目标股票全部停牌')
        g.last_rebalance_date = context.current_dt.date()
        return

    log.info(f'目标持仓：{target_stocks}')
    rebalance_portfolio(context, target_stocks)
    g.last_rebalance_date = context.current_dt.date()


def is_rebalance_day(context):
    if g.last_rebalance_date is None:
        return True
    days_passed = (context.current_dt.date() - g.last_rebalance_date).days
    return days_passed >= g.rebalance_days


def get_filtered_stock_pool(context):
    all_stocks = list(get_all_securities(['stock']).index)
    all_stocks = [s for s in all_stocks if not s.startswith(('4','8','688'))]
    yesterday = context.previous_date

    df_is_st = get_extras('is_st', all_stocks, start_date=yesterday, end_date=yesterday)
    if df_is_st is not None and not df_is_st.empty:
        st_series = df_is_st.iloc[-1]
        non_st = [s for s in all_stocks if s in st_series.index and not st_series[s]]
    else:
        non_st = all_stocks

    price_dict = get_price(non_st, end_date=yesterday, count=1, fields=['close'], panel=False)
    if price_dict is not None and not price_dict.empty:
        tradable = price_dict.dropna(subset=['close'])['code'].unique().tolist()
    else:
        tradable = []

    sec_info = get_all_securities(['stock']).start_date
    current_date = context.current_dt.date()
    qualified = [s for s in tradable if s in sec_info.index and (current_date - sec_info[s]).days >= 180]

    if len(qualified) > 0:
        try:
            df_turn = get_factor_values(qualified, ['VOL20'],
                                        start_date=yesterday, end_date=yesterday)
            if 'VOL20' in df_turn and not df_turn['VOL20'].empty:
                turn_series = df_turn['VOL20'].iloc[-1]
                keep = [s for s in qualified if s in turn_series.index and
                        not pd.isna(turn_series[s]) and turn_series[s] < g.max_turnover]
                qualified = keep
        except Exception as e:
            log.warning(f'换手率过滤异常：{e}')
    return qualified


def get_raw_factors(stock_list, context):
    date = context.previous_date
    factor_names = list(g.factor_weights.keys())

    # 从聚宽获取的因子（排除手动计算的 return_5d）
    custom_factors = ['return_5d']
    base_factors = [f for f in factor_names if f not in custom_factors]
    factor_data = get_factor_values(stock_list, base_factors, start_date=date, end_date=date)
    factor_df = pd.DataFrame(index=stock_list)
    for fn in base_factors:
        if fn in factor_data and not factor_data[fn].empty:
            factor_df[fn] = factor_data[fn].iloc[-1]

    # 计算 return_5d
    try:
        prices = get_price(stock_list, end_date=date, count=6, fields=['close'], panel=False)
        if prices is not None and not prices.empty:
            price_df = prices.pivot(index='code', columns='time', values='close')
            if price_df.shape[1] >= 2:
                ret_5d = price_df.iloc[:, -1] / price_df.iloc[:, 0] - 1
                factor_df['return_5d'] = ret_5d
    except Exception as e:
        log.warning(f'计算return_5d失败：{e}')

    # 行业信息
    industry_dict = {}
    try:
        industry_info = get_industries(name='sw_l1', date=date)
        if industry_info:
            for s in stock_list:
                if s in industry_info and industry_info[s]:
                    industry_dict[s] = industry_info[s].get('sw_l1', {}).get('industry_name', '其他')
                else:
                    industry_dict[s] = '其他'
    except:
        industry_dict = {s: '其他' for s in stock_list}
    factor_df['industry'] = factor_df.index.map(industry_dict)

    # 合并小行业
    ind_counts = factor_df['industry'].value_counts()
    small = ind_counts[ind_counts < 3].index.tolist()
    if small:
        factor_df['industry'] = factor_df['industry'].apply(lambda x: '其他' if x in small else x)

    return factor_df


def update_dynamic_weights(context):
    if g.pending_factor_df is None or g.pending_date is None:
        g.dynamic_weights = dict(g.factor_weights)
        return

    stocks = g.pending_factor_df.index.tolist()
    start_date = g.pending_date
    end_date = context.previous_date
    try:
        price_df = get_price(stocks, start_date=start_date, end_date=end_date,
                             fields=['close'], panel=False, skip_paused=True)
        if price_df is not None and not price_df.empty:
            price_pivot = price_df.pivot(index='code', columns='time', values='close')
            if price_pivot.shape[1] >= 2:
                ret = price_pivot.iloc[:, -1] / price_pivot.iloc[:, 0] - 1
            else:
                ret = pd.Series(np.nan, index=stocks)
        else:
            ret = pd.Series(np.nan, index=stocks)
    except:
        g.pending_factor_df, g.pending_date = None, None
        g.dynamic_weights = dict(g.factor_weights)
        return

    factor_names = [f for f in g.factor_weights.keys() if f in g.pending_factor_df.columns]
    ic_series = {}
    for fn in factor_names:
        combined = pd.DataFrame({
            'factor': g.pending_factor_df[fn],
            'return': ret
        }).dropna()
        if len(combined) > 10:
            ic_series[fn] = combined['factor'].corr(combined['return'])
        else:
            ic_series[fn] = 0.0

    g.ic_data.append(ic_series)
    g.pending_factor_df, g.pending_date = None, None

    if len(g.ic_data) > 0:
        ic_sum = {fn: 0.0 for fn in g.factor_weights}
        for ic_dict in g.ic_data:
            for fn, ic in ic_dict.items():
                ic_sum[fn] += ic
        count = len(g.ic_data)
        mean_ic = {fn: v/count for fn, v in ic_sum.items()}
        dynamic = {}
        for fn, w0 in g.factor_weights.items():
            ic_mean = mean_ic.get(fn, 0.0)
            if (w0 > 0 and ic_mean > 0) or (w0 < 0 and ic_mean < 0):
                dynamic[fn] = w0 * (1 + abs(ic_mean))
            elif (w0 > 0 and ic_mean < 0) or (w0 < 0 and ic_mean > 0):
                dynamic[fn] = 0.0
            else:
                dynamic[fn] = w0
        for fn in dynamic:
            max_abs = abs(g.factor_weights[fn]) * 2.0
            if abs(dynamic[fn]) > max_abs:
                dynamic[fn] = max_abs if dynamic[fn] > 0 else -max_abs
        g.dynamic_weights = dynamic
    else:
        g.dynamic_weights = dict(g.factor_weights)


def calculate_composite_score(factor_df, context):
    if factor_df.empty:
        return None

    current_weights = g.dynamic_weights if g.dynamic_weights else dict(g.factor_weights)
    factor_names = [f for f in current_weights.keys() if f in factor_df.columns]
    if 'industry' not in factor_df.columns:
        return None

    # 缺失值用行业中位数填充
    for fn in factor_names:
        if fn not in factor_df.columns:
            continue
        for ind, group in factor_df.groupby('industry'):
            med = group[fn].median()
            if pd.isna(med):
                med = 0.0
            factor_df.loc[group.index, fn] = group[fn].fillna(med)

    # 市值中性化（除market_cap自身）
    if 'market_cap' in factor_df.columns:
        factor_df['ln_cap'] = np.log(factor_df['market_cap'].replace(0, np.nan))
    else:
        factor_df['ln_cap'] = 0.0

    for fn in factor_names:
        if fn == 'market_cap':
            continue
        if fn not in factor_df.columns or factor_df[fn].isna().all():
            continue
        try:
            y = factor_df[fn].copy()
            mask = y.notna() & factor_df['ln_cap'].notna()
            if mask.sum() < 10:
                continue
            X = pd.get_dummies(factor_df.loc[mask, 'industry'], drop_first=True)
            X['ln_cap'] = factor_df.loc[mask, 'ln_cap']
            X = X.assign(const=1.0)
            coeff = np.linalg.lstsq(X.values, y[mask].values, rcond=None)[0]
            pred = X.values.dot(coeff)
            resid = y[mask].values - pred
            factor_df.loc[mask, fn+'_neutral'] = resid
        except Exception as e:
            log.warning(f'{fn}中性化失败：{e}')
            factor_df[fn+'_neutral'] = factor_df[fn].copy()
        factor_df[fn] = factor_df[fn+'_neutral'].combine_first(factor_df[fn])

    # 行业内标准化
    for fn in factor_names:
        norm_col = f'{fn}_norm'
        factor_df[norm_col] = np.nan
        for ind, group in factor_df.groupby('industry'):
            series = group[fn].dropna().copy()
            if len(series) < 2:
                factor_df.loc[group.index, norm_col] = 0.0
                continue
            median = series.median()
            mad = (series - median).abs().median()
            if mad > 0:
                series = series.clip(median - 5*mad, median + 5*mad)
            mean = series.mean()
            std = series.std()
            if std > 0:
                factor_df.loc[series.index, norm_col] = (series - mean) / std
            else:
                factor_df.loc[series.index, norm_col] = 0.0

    scores = pd.Series(0.0, index=factor_df.index)
    for fn in factor_names:
        norm_col = f'{fn}_norm'
        if norm_col in factor_df.columns:
            scores += factor_df[norm_col].fillna(0) * current_weights[fn]
    return scores.dropna()


def filter_paused_stocks(stock_list, context):
    tradable = []
    today = context.current_dt.date()
    for stock in stock_list:
        try:
            df = get_price(stock, end_date=today, count=1, fields=['close'], panel=False)
            if df is not None and not df.empty and not pd.isna(df.iloc[0]['close']):
                tradable.append(stock)
        except:
            continue
    return tradable


def rebalance_portfolio(context, target_stocks):
    today = context.current_dt.date()
    current_holdings = list(context.portfolio.positions.keys())
    all_needed = list(set(current_holdings + target_stocks))
    prices = {}
    if all_needed:
        try:
            df_prices = get_price(all_needed, end_date=today, count=1, fields=['close'], panel=False)
            if df_prices is not None and not df_prices.empty:
                prices = df_prices.set_index('code')['close'].to_dict()
        except:
            for stock in all_needed:
                try:
                    df = get_price(stock, end_date=today, count=1, fields=['close'], panel=False)
                    if df is not None and not df.empty:
                        prices[stock] = df.iloc[0]['close']
                except:
                    pass

    for stock, price in prices.items():
        if stock in g.stock_high:
            if price > g.stock_high[stock]:
                g.stock_high[stock] = price
        elif stock in context.portfolio.positions:
            g.stock_high[stock] = price

    stopped_out = []
    for stock in current_holdings:
        sell = False
        reason = ''
        if stock not in target_stocks:
            sell = True
            reason = '调出'
        elif stock in g.stock_high and stock in prices:
            high = g.stock_high[stock]
            cur = prices[stock]
            if (high - cur) / high >= g.stop_loss_ratio:
                sell = True
                reason = f'止损(最高{high:.2f}, 现价{cur:.2f})'
                stopped_out.append(stock)
        if sell:
            order_target_value(stock, 0)
            log.info(f'卖出 {stock}，原因：{reason}')
            if stock in g.stock_high:
                del g.stock_high[stock]

    if stopped_out:
        target_clean = [s for s in target_stocks if s not in stopped_out]
        log.info(f'止损剔除：{stopped_out}，剩余目标：{target_clean}')
    else:
        target_clean = target_stocks

    if target_clean:
        target_value = context.portfolio.total_value / len(target_clean)
        for stock in target_clean:
            order = order_target_value(stock, target_value)
            if order is not None:
                log.info(f'买入/调整 {stock}，目标市值 {target_value:.2f}')
                if stock in prices and stock not in g.stock_high:
                    g.stock_high[stock] = prices[stock]