# etfprem-000 — ETF溢价 enhance baseline
# base: wiki/families/ETF溢价.md bestVariant edd94ebc (ETF溢价回撤)
# source: strategies/2026-06-19_ETF溢价回撤13_12_年化1599_实盘效果好-edd94ebc.py
# harness epoch 6, window TRAIN. Frozen cost OVERRIDE appended verbatim from
# utils/strategy-normalize.js — never hand-copied.
#
# ⚠ Its published 1599% / sharpe 51 is a SHORT-WINDOW headline, and study q-1 measured this
# family's alpha as an illiquidity premium that dies as the volume floor rises
# (sharpe 8.44 -> 3.16 -> 1.10, DQ at 1e8). This baseline exists to be BEATEN under
# realizability constraints, not to be reproduced.
# Clone from JoinQuant
# postId: edd94ebc3a42fe6ad845ce0555314b31
# backtestId: 6b3ab11afe6b8a117294cf3851fc5758
# title: ETF溢价回撤13.12%年化1599%，实盘效果好

# 导入函数库
from jqdata import *

def initialize(context):
    set_option('use_real_price', True)
    log.set_level('system', 'error')
    set_option("avoid_future_data", True)
        # 设定沪深300作为基准
    set_benchmark('000300.XSHG')

    set_option('use_real_price', True)
    # 为全部交易品种设定固定值滑点
    # set_slippage(FixedSlippage(0.02))
    
    g.max_hold_num=2
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.00025, close_commission=0.00025, min_commission=5), type='fund')
    run_daily(before_market_open, '09:20', reference_security='000300.XSHG')
    run_daily(market_open, '09:30', reference_security='000300.XSHG')
    

    
def before_market_open(context):
   # 获取基金
    fund_list = get_all_securities(['etf'], context.previous_date).index.tolist()
    # 价格波动过滤
    high_df = history(count=1, unit='1d', field="high", security_list=fund_list).T
    high_df.columns=['high_price']
    low_df = history(count=1, unit='1d', field="low", security_list=fund_list).T
    low_df.columns=['low_price']
    # 使用 merge 合并两个数据帧
    df = high_df.merge(low_df, left_index=True, right_index=True)
    df['price_range'] = df['high_price'] - df['low_price']
    df = df[df.price_range < 0.1]
    # 获取净值
    df = get_extras('unit_net_value',df.index.tolist(),end_date=context.previous_date, df=True, count=1).T
    df.columns=['unit_net_value']
    
###########如下为本次魔改内容#############    
    # 获取昨日成交量数据
    volume_df = history(count=1, unit='1d', field="money", security_list=fund_list).T
    volume_df.columns = ['money']
    # 将成交量数据合并到已有的数据帧df中
    df = df.merge(volume_df, left_index=True, right_index=True)
    # 筛选昨日成交量大于1000万（这里假设成交量数据单位是股，可根据实际情况调整换算）的ETF
    df = df[df['money'] > 800000]
    # 增加站上5日线校验
    df['ma5'] = [get_ma5(etf, context.previous_date) for etf in df.index.tolist()]
    df['last_close'] = [get_price(etf, end_date=context.previous_date, frequency='daily', fields=['close'], skip_paused=True, fq='pre', count=1)['close'][0] for etf in df.index.tolist()]
    df = df[df['last_close'] > df['ma5']]  # 保留站上5日线的ETF
    
    
    # 最后将筛选后的数据赋值给g.fund_list
    g.fund_list = df
###########以上为本次魔改内容#############  

def get_ma5(etf, date):
    """计算5日移动平均线"""
    close_prices = get_price(etf, end_date=date, frequency='daily', fields=['close'], skip_paused=True, fq='pre', count=5)['close']
    return close_prices.mean()
    
    
def market_open(context):
    df = g.fund_list
    current = get_current_data()
    
    # 过滤停牌的ETF
    df = df[[not current[etf].paused for etf in df.index.tolist()]]
    
    ## 获得基金最新价
    df['last_price'] = [current[c].last_price for c in df.index.tolist()]
    ## 计算溢价
    df['premium'] = (df.last_price / df.unit_net_value - 1) * 100
    ## 根据溢价大小排序
    df = df.sort_values(['premium'], ascending = True)
    df = df[(df.premium < 0)]
    order_fund = df[:g.max_hold_num].index.tolist()
    g.max_position = len(order_fund)
    log.info(order_fund)
    # 卖出
    for fund in context.portfolio.positions.keys():
        # 卖出不在股票池或节假日前清仓
        if fund not in order_fund:
        #if fund not in order_fund :
            order_target_value(fund, 0)
    
    # 买入
    for fund in order_fund:
        now_position = g.max_position - len(context.portfolio.positions)
        if now_position == 0:
            continue
        if fund not in context.portfolio.positions.keys():
            position = context.portfolio.available_cash / now_position * 0.998  # 调低买入金额0.2%
            order_target_value(fund, position)

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
