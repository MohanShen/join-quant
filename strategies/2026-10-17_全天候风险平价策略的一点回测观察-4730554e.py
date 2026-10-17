# Clone from JoinQuant
# postId: 4730554eac007c4bfe89dbf2c96781e5
# backtestId: 1307176eae7a9d979bb5c07ea3c3e5fe
# title: 全天候风险平价策略的一点回测观察

# 克隆/改写说明：
# 由本地 天候风险平价策略实盘版.py 静态改写为聚宽回测版。
# 当前默认复刻“去掉国债”的 S1 配置：股票ETF×4 + 黄金ETF + 商品ETF。
# 若要对照原始全天候含债券版本，把 INCLUDE_BONDS 改为 True 后在聚宽分别回测。

from jqdata import *
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from datetime import timedelta


# ==================== 参数区 ====================

STRATEGY_NAME = 'S1 全天候风险平价 聚宽回测版'

# 当前 S1 实盘版已注释 5年/10年国债；默认 False 用于复刻当前版本。
# 发帖讨论时建议分别回测 False / True 两组结果。
INCLUDE_BONDS = False

# WEEKLY: 每周第 N 个交易日调仓；MONTHLY: 每月第一个交易日调仓；DAILY: 每日调仓。
REBALANCE_MODE = 'WEEKLY'
REBALANCE_WEEKDAY = 1  # 0=每周第1个交易日，1=每周第2个交易日，与当前 QMT S1 保持一致
TRADE_TIME = '09:48'

COV_DAYS = 120
MIN_TRADE_VALUE = 3000
TARGET_VALUE_RATIO = 0.98

# QMT -> 聚宽代码映射：
# 510300.SH -> 510300.XSHG，159xxx.SZ -> 159xxx.XSHE。
ASSET_DICT = {
    'stock': [
        '510300.XSHG',  # 沪深300ETF
        '510500.XSHG',  # 中证500ETF
        '513500.XSHG',  # 标普500ETF
        '513100.XSHG',  # 纳指ETF
    ],
    'gold': [
        '518880.XSHG',  # 黄金ETF
    ],
    'commodity': [
        '510170.XSHG',  # 大宗商品/商品ETF，按当前 S1 代码映射
    ],
}

BOND_ASSET_DICT = {
    'middle_bond': ['511010.XSHG'],  # 5年期国债ETF
    'long_bond': ['511260.XSHG'],    # 10年期国债ETF
}

REPLACE_DICT = {
    '511260.XSHG': '511010.XSHG',
    'default': '510050.XSHG',
}


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('order', 'error')
    log.set_level('system', 'error')

    set_slippage(PriceRelatedSlippage(0.001), type='fund')
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0,
        open_commission=0.0001,
        close_commission=0.0001,
        close_today_commission=0,
        min_commission=0.1,
    ), type='fund')

    g.asset_dict = build_asset_dict()
    g.etf_info = {}
    g.last_weight_dict = {}
    g.trade_count = 0

    for code in get_all_assets():
        try:
            info = get_security_info(code)
            g.etf_info[code] = info.start_date
        except Exception:
            g.etf_info[code] = None

    run_daily(rebalance, time=TRADE_TIME, reference_security='000300.XSHG')
    log.info('%s 初始化完成。INCLUDE_BONDS=%s, COV_DAYS=%s, REBALANCE=%s' %
             (STRATEGY_NAME, INCLUDE_BONDS, COV_DAYS, REBALANCE_MODE))
    log.info('资产池: %s' % g.asset_dict)


def build_asset_dict():
    asset_dict = {}
    for asset, codes in ASSET_DICT.items():
        asset_dict[asset] = codes[:]
    if INCLUDE_BONDS:
        for asset, codes in BOND_ASSET_DICT.items():
            asset_dict[asset] = codes[:]
    return asset_dict


def get_all_assets():
    codes = []
    for security_list in build_asset_dict().values():
        codes.extend(security_list)
    codes.extend(REPLACE_DICT.values())
    return sorted(set(codes))


def rebalance(context):
    if not should_rebalance_today(context):
        return

    today = context.current_dt.date()
    previous_date = context.previous_date
    log.info('========== %s 再平衡开始，previous_date=%s ==========' % (today, previous_date))

    trade_list = build_trade_list(previous_date)
    if len(trade_list) < 2:
        log.info('可交易资产不足，跳过：%s' % trade_list)
        return

    returns_df = get_returns_df(trade_list, previous_date)
    if returns_df is None or len(returns_df) < max(30, COV_DAYS // 2):
        log.info('收益率数据不足，跳过。trade_list=%s' % trade_list)
        return

    weight_dict = get_risk_parity_weights(returns_df)
    g.last_weight_dict = weight_dict
    log.info('风险平价目标权重: %s' % format_weight_dict(weight_dict))

    adjust_positions(context, weight_dict)
    g.trade_count += 1
    log.info('========== 再平衡完成，第 %s 次 ==========' % g.trade_count)


def should_rebalance_today(context):
    if len(context.portfolio.positions) == 0:
        log.info('当前空仓，直接执行首次/补充再平衡')
        return True

    if REBALANCE_MODE == 'DAILY':
        return True

    today = context.current_dt.date()
    if REBALANCE_MODE == 'MONTHLY':
        month_start = today.replace(day=1)
        trade_days = list(get_trade_days(start_date=month_start, end_date=today))
        return len(trade_days) > 0 and today == trade_days[0]

    if REBALANCE_MODE == 'WEEKLY':
        week_start = today - timedelta(days=today.weekday())
        trade_days = list(get_trade_days(start_date=week_start, end_date=today))
        if not trade_days:
            return False
        target_idx = min(REBALANCE_WEEKDAY, len(trade_days) - 1)
        return today == trade_days[target_idx]

    raise ValueError('未知 REBALANCE_MODE: %s' % REBALANCE_MODE)


def build_trade_list(previous_date):
    trade_list = []
    min_history_days = int(round(1.5 * COV_DAYS))

    for security_list in g.asset_dict.values():
        for code in security_list:
            final_code = code
            start_date = g.etf_info.get(code)
            if start_date is not None and previous_date < start_date + timedelta(days=min_history_days):
                final_code = REPLACE_DICT.get(code, REPLACE_DICT['default'])
            trade_list.append(final_code)

    # 保持顺序去重，避免 set 打乱日志和权重展示。
    result = []
    for code in trade_list:
        if code not in result:
            result.append(code)
    return result


def get_returns_df(trade_list, end_date):
    df = get_price(
        trade_list,
        end_date=end_date,
        count=COV_DAYS + 30,
        frequency='daily',
        fields=['close'],
        panel=False,
        fill_paused=True,
        fq='pre',
    )
    if df is None or len(df) == 0:
        return None

    if 'code' in df.columns:
        price_df = df.pivot(index='time', columns='code', values='close')
    else:
        # 兼容部分聚宽环境返回多层列的情况。
        price_df = df['close'] if isinstance(df.columns, pd.MultiIndex) else df

    price_df = price_df.sort_index().fillna(method='ffill').dropna(how='all')
    price_df = price_df.dropna(axis=1, how='all')
    returns_df = price_df.pct_change().dropna().tail(COV_DAYS)
    return returns_df


def get_risk_parity_weights(returns_df):
    returns_df = returns_df.dropna(axis=1, how='any')
    codes = list(returns_df.columns)
    if len(codes) == 0:
        return {}
    if len(codes) == 1:
        return {codes[0]: 1.0}

    cov_matrix = returns_df.cov().values

    def risk_parity(weights):
        sigma = np.sqrt(np.dot(np.dot(weights, cov_matrix), weights))
        if sigma <= 0:
            return 1e9
        mrc = np.dot(cov_matrix, weights) / sigma
        trc = weights * mrc
        return 10000 * np.sum((trc - np.mean(trc)) ** 2)

    weights0 = np.ones(len(codes)) / len(codes)
    cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
    bounds = tuple((0, 1.0) for _ in weights0)

    res = minimize(risk_parity, weights0, method='SLSQP',
                   constraints=cons, bounds=bounds, options={'maxiter': 100})
    if not res.success:
        log.info('风险平价优化失败，退化为逆波动率权重: %s' % res.message)
        vol = returns_df.std()
        inv_vol = 1.0 / vol.replace(0, np.nan)
        inv_vol = inv_vol.replace([np.inf, -np.inf], np.nan).dropna()
        weights = inv_vol / inv_vol.sum()
        return weights.to_dict()

    weights = pd.Series(res.x, index=codes)
    weights = weights / weights.sum()
    return weights.to_dict()


def adjust_positions(context, weight_dict):
    target_codes = set(weight_dict.keys())
    current_data = get_current_data()
    total_value = context.portfolio.total_value

    action_list = []

    for code in list(context.portfolio.positions.keys()):
        if code not in target_codes:
            action_list.append((code, 0, -context.portfolio.positions[code].value))

    for code, weight in sorted(weight_dict.items(), key=lambda x: x[1]):
        target_value = total_value * TARGET_VALUE_RATIO * weight
        position = context.portfolio.positions[code] if code in context.portfolio.positions else None
        current_value = 0 if position is None else position.value

        if abs(target_value - current_value) < MIN_TRADE_VALUE:
            log.info('[%s] 调整金额 %.2f 小于阈值，跳过' % (code, target_value - current_value))
            continue

        action_list.append((code, target_value, target_value - current_value))

    for code, target_value, adjust_value in sorted(action_list, key=lambda x: x[2]):
        safe_order_target_value(context, code, target_value, current_data)


def safe_order_target_value(context, code, target_value, current_data):
    try:
        data = current_data[code]
    except Exception:
        log.info('[%s] 无 current_data，跳过' % code)
        return False

    if data.paused:
        log.info('[%s] 停牌，跳过' % code)
        return False

    last_price = data.last_price
    if last_price is None or last_price <= 0:
        log.info('[%s] 价格无效，跳过' % code)
        return False

    if target_value > 0 and last_price >= data.high_limit:
        log.info('[%s] 涨停，跳过买入/加仓' % code)
        return False

    if target_value == 0 and last_price <= data.low_limit:
        log.info('[%s] 跌停，跳过卖出' % code)
        return False

    log.info('[%s] 调整到目标市值 %.2f' % (code, target_value))
    order_target_value(code, target_value)
    return True


def format_weight_dict(weight_dict):
    return ', '.join(['%s: %.2f%%' % (k, v * 100) for k, v in sorted(weight_dict.items())])


def after_trading_end(context):
    record(cash=context.portfolio.cash,
           total_value=context.portfolio.total_value,
           positions=len(context.portfolio.positions))
