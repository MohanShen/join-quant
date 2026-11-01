# Clone from JoinQuant
# postId: 2a3235229fdfd62a917c78a5d8236c15
# backtestId: 1c770f0f1cb42e87e17b574b39aaba59
# title: 自己搭建的一个10年230%收益率的银行股策略

# 聚宽策略：银行股精简轮动增强版（基于139%收益策略优化）
# 核心：PB + 股息率 + 动量（权重30/30/40），布林择时，250日线动态仓位
# 止损放宽至-12%，持仓3只分散，每周固定调仓

from jqdata import finance
import datetime
import pandas as pd

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)

    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                             open_commission=0.000095, close_commission=0.000095,
                             close_today_commission=0, min_commission=1), type='stock')

    g.stocks = ['601398.XSHG', '601939.XSHG', '601288.XSHG', '601988.XSHG', '600036.XSHG']
    g.max_holdings = 3          # 分散持仓
    g.min_holdings = 2
    g.buy_prices = {}

    # 每周五调仓
    run_weekly(rebalance, weekday=5, time='close')


def calc_dividend_yield(stock, context):
    """计算TTM股息率"""
    start_date = context.current_dt - datetime.timedelta(days=365)
    q = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.bonus_ratio_rmb
    ).filter(
        finance.STK_XR_XD.code == stock,
        finance.STK_XR_XD.a_bonus_date >= start_date
    )
    df = finance.run_query(q)
    if df.empty:
        return 0.0
    total_div = df['bonus_ratio_rmb'].sum() / 10.0
    if total_div <= 0:
        return 0.0
    df_price = get_price(stock, end_date=context.current_dt, frequency='daily',
                         fields=['close'], count=1, skip_paused=True, fq=None)
    if len(df_price) == 0:
        return 0.0
    price = df_price['close'].iloc[-1]
    if price <= 0:
        return 0.0
    return total_div / price


def get_ma250(stock, context):
    df = get_price(stock, end_date=context.current_dt, frequency='daily',
                   fields=['close'], count=260, skip_paused=True)
    if len(df) >= 250:
        return df['close'].rolling(250).mean().iloc[-1]
    return None


def get_bollinger(stock, context, period=20, num_std=2):
    df = get_price(stock, end_date=context.current_dt, frequency='daily',
                   fields=['close'], count=period+5, skip_paused=True)
    if len(df) < period:
        return None
    close = df['close']
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    return {
        'ma': ma.iloc[-1],
        'close': close.iloc[-1]
    }


def rebalance(context):
    log_liq_min(context)  # liq-cap: observation only
    # ----- 获取基本面数据（PB）-----
    df_fund = get_fundamentals(
        query(
            valuation.code,
            valuation.pb_ratio
        ).filter(
            valuation.code.in_(g.stocks)
        )
    )
    if len(df_fund) == 0:
        return

    # ----- 计算得分 -----
    scores = {}
    # 价格数据
    price_data = {}
    for stock in g.stocks:
        df = get_price(stock, end_date=context.current_dt, frequency='daily',
                       fields=['close'], count=30, skip_paused=True)
        if len(df) >= 20:
            price_data[stock] = df['close']

    for _, row in df_fund.iterrows():
        code = row['code']
        pb = row['pb_ratio']
        if pb is None or pb <= 0:
            continue

        # 股息率
        dy = calc_dividend_yield(code, context)
        if dy <= 0:
            continue

        # 因子1：低PB
        pb_score = 1 / pb
        # 因子2：高股息
        dy_score = dy * 100
        # 因子3：近一月动量（收益率越高分越高）
        mom_score = 0
        if code in price_data and len(price_data[code]) >= 20:
            ret_1m = (price_data[code].iloc[-1] - price_data[code].iloc[-20]) / price_data[code].iloc[-20]
            mom_score = max(0, (ret_1m + 0.05) * 10)  # 将涨幅映射为正分

        # 综合评分（动量权重提高）
        scores[code] = 0.30 * pb_score + 0.30 * dy_score + 0.40 * mom_score

    if not scores:
        return

    # ----- 择时：股价低于布林中轨的股票才纳入候选-----
    eligible_stocks = []
    for stock in g.stocks:
        if stock not in scores:
            continue
        bb = get_bollinger(stock, context)
        if bb is None:
            continue
        if bb['close'] <= bb['ma']:
            eligible_stocks.append(stock)

    # 若没有符合条件的股票，空仓时放宽条件（允许略高于中轨5%）
    if not eligible_stocks:
        has_position = any(
            context.portfolio.positions[s].total_amount > 0
            for s in g.stocks if context.portfolio.positions.get(s)
        )
        if not has_position:
            sorted_stocks = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
            for s in sorted_stocks[:3]:
                bb = get_bollinger(s, context)
                if bb and (bb['close'] - bb['ma']) / bb['ma'] < 0.05:
                    eligible_stocks.append(s)
        else:
            # 有持仓但无新标的，保留持仓不调仓
            return

    # 按得分排序
    eligible_stocks.sort(key=lambda x: scores.get(x, 0), reverse=True)
    eligible_stocks = filter_liquidity_floor(context, eligible_stocks)  # liq-cap: ONLY behavioural change vs baseline

    # ----- 动态仓位：250日线决定仓位高低 -----
    ma250 = get_ma250('601398.XSHG', context)
    current_price_icbc = get_bollinger('601398.XSHG', context)['close'] if get_bollinger('601398.XSHG', context) else None
    if ma250 is not None and current_price_icbc is not None and current_price_icbc < ma250:
        target_position_ratio = 0.5
    else:
        target_position_ratio = 1.0

    total_value = context.portfolio.total_value
    target_per_stock_value = (total_value * target_position_ratio) / g.min_holdings

    # ----- 止损：-12% -----
    for stock in g.stocks:
        pos = context.portfolio.positions.get(stock)
        if pos and pos.total_amount > 0:
            current_price = get_bollinger(stock, context)['close'] if get_bollinger(stock, context) else None
            if current_price is not None:
                loss_pct = (current_price - pos.avg_cost) / pos.avg_cost
                if loss_pct < -0.12:
                    order_target(stock, 0)

    # ----- 确定目标持仓 -----
    current_holdings = [
        s for s in g.stocks
        if context.portfolio.positions.get(s) and context.portfolio.positions[s].total_amount > 0
    ]

    target_holdings = eligible_stocks[:g.max_holdings]
    # 如果目标持仓少于最小持有数，补充候选
    if len(target_holdings) < g.min_holdings:
        for s in eligible_stocks:
            if s not in target_holdings:
                target_holdings.append(s)
                if len(target_holdings) >= g.min_holdings:
                    break
        # 若仍不足，保留当前持仓
        if len(target_holdings) < g.min_holdings and current_holdings:
            target_holdings = current_holdings[:g.min_holdings]

    # ----- 调仓 -----
    for stock in current_holdings:
        if stock not in target_holdings:
            order_target(stock, 0)

    for stock in target_holdings:
        max_single = total_value * 0.4
        target_value = min(target_per_stock_value, max_single)
        order_target_value(stock, target_value)

# ----------------- liquidity floor (understand experiment liq-cap, 2026-11-01) -----------------
# Floor derivation: capital 1,000,000 CNY x 40% single-name cap = 400,000 CNY per full position.
# Epoch 4 pins order_volume_ratio = 0.05, so filling it inside one daily bar needs traded value
# >= 400,000 / 0.05 = 8,000,000 CNY (1x feasibility). LIQ_FLOOR = 8e7 is 10x that.
LIQ_FLOOR = 8e7

def filter_liquidity_floor(context, stock_list):
    """Keep names whose TRAILING-20-BAR MEDIAN daily `money` is >= LIQ_FLOOR.

    Median, not mean: a single spike day must not admit a name that is normally illiquid.
    Evaluated on context.previous_date, so the bar being traded today is never consulted.
    """
    n_in = len(stock_list)
    if n_in == 0:
        log.error('LIQFLOOR floor=%.0f in=0 out=0 removedFrac=NA slots=0' % LIQ_FLOOR)
        return []
    try:
        df = get_price(stock_list, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        keep = [s for s in stock_list if (s in med.index) and (med[s] >= LIQ_FLOOR)]
    except Exception as e:
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s' % (LIQ_FLOOR, n_in, str(e)))
        return stock_list
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(g.max_holdings, len(keep))))
    return keep

def log_liq_min(context):
    try:
        df = get_price(g.stocks, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        log.error('LIQMIN date=%s ' % str(context.previous_date) +
                  ' '.join('%s=%.0f' % (s, med[s] if s in med.index else -1) for s in g.stocks))
    except Exception as e:
        log.error('LIQMIN ERROR exc=%s' % str(e))


# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====
