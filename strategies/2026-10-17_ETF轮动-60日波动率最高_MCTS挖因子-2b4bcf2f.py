# Clone from JoinQuant
# postId: 2b4bcf2f2ddbe2094f1c21976ec6f953
# backtestId: bc6e9a5d2790fe7def6e667c51b35dcc
# title: ETF轮动-60日波动率最高 MCTS挖因子

from jqdata import *
import numpy as np
import pandas as pd

def initialize(context):
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)

    set_slippage(FixedSlippage(0))
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0,
            close_commission=0,
            close_today_commission=0,
            min_commission=0.1
        ),
        type='fund'
    )
    log.set_level('order', 'error')

    g.holdetf = []

    context.ETF_POOL = [
        '518880.XSHG',  # 黄金ETF
        '159908.XSHE',  # 创业板ETF
        '513100.XSHG',  # 纳指100ETF
        '510300.XSHG',  # 沪深300ETF
        '512890.XSHG',  # 红利低波ETF
        '159920.XSHE',  # 恒生ETF
        '501018.XSHG',  # 原油LOF
        '159980.XSHE',  # 有色ETF
        '159985.XSHE',  # 豆粕ETF
        '511010.XSHG',  # 国债ETF
    ]

    # 每周三 9:35 调仓；你原来写 run_weekly(rebalance, 3)
    run_weekly(rebalance, 3, time='9:35', reference_security='000300.XSHG')
def get_previous_trade_date(context):
    trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
    return trade_days[0]

def calculate_vol_factor(etf, context, vol_window=60, smooth_window=5):
    count = vol_window + smooth_window + 2

    try:
        end_date = get_previous_trade_date(context)

        df = get_price(
            etf,
            count=count,
            end_date=end_date,
            frequency='daily',
            fields=['close'],
            skip_paused=True,
            fq='pre'
        )

        if df is None or df.empty or len(df) < count * 0.8:
            return None

        close = df['close'].dropna()

        if len(close) < vol_window + smooth_window + 1:
            return None

        log_close = np.log(close)
        log_ret = log_close.diff()

        vol_60 = log_ret.rolling(vol_window).std()
        factor = vol_60.rolling(smooth_window).mean().iloc[-1]

        if pd.isna(factor) or np.isinf(factor):
            return None

        return factor

    except Exception as e:
        log.warn('计算因子失败: %s, error=%s' % (etf, e))
        return None


def get_top_factor_etfs(etf_pool, context, top_n=2):
    scores = {}

    for etf in etf_pool:
        score = calculate_vol_factor(etf, context)
        if score is not None:
            scores[etf] = score

    if len(scores) == 0:
        return []

    sorted_etfs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    log.info('ETF因子排序: %s' % sorted_etfs)

    return [etf for etf, score in sorted_etfs[:top_n]]


def rebalance(context, data=None):
    target_etfs = get_top_factor_etfs(context.ETF_POOL, context, top_n=2)

    if len(target_etfs) == 0:
        log.warn('没有可用目标ETF，本次不调仓')
        return

    current_holds = list(context.portfolio.positions.keys())

    # 卖出不在目标池里的ETF
    for etf in current_holds:
        if etf not in target_etfs:
            order_target_value(etf, 0)

    # 等权买入目标ETF
    target_value = context.portfolio.total_value / len(target_etfs)

    for etf in target_etfs:
        order_target_value(etf, target_value)

    g.holdetf = target_etfs

    log.info('目标ETF: %s, 单只目标市值: %.2f' % (target_etfs, target_value))
