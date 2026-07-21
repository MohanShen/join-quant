# Clone from JoinQuant
# postId: da82dd02f874a1a5f656b3f6725d5afa
# backtestId: 4c82cb77ab8c1c8d797d721affbf4d73
# title: 五境掘金全球ETF轮动（中频）


import pandas as pd
import numpy as np
from jqdata import *
import datetime

def initialize(context):
    # 基金池（5只，已添加交易所后缀）
    g.etf_pool = [
        '159915.XSHE',   # 创业板
        '159941.XSHE',   # 纳指ETF
        '518880.XSHG',   # 黄金ETF
        '162719.XSHE',   # 广发石油（LOF）
        '513030.XSHG'    # 德国30
    ]
    g.min_gain = 2
    g.bias20_max = 18.0
    g.bias60_max = 35.0
    g.bias250_max = 50.0
    g.cooldown_days = 10
    g.last_sell_record = {}
    g.cash_etf = '511880.XSHG'   # 银华日利
    g.stop_loss_pct = -8.0       # 止损阈值 -8%

    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.0001))
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                             open_commission=0.0001, close_commission=0.0001,
                             close_today_commission=0, min_commission=5), type='fund')
    run_daily(trade, time='14:57')
    log.info('策略初始化完成，ETF数量：{}'.format(len(g.etf_pool)))

def check_etf(security, context):
    """返回 (20日涨幅%, 20日乖离率%, 60日乖离率%, 250日乖离率%)"""
    try:
        df = attribute_history(security, 300, '1d', ['close'], skip_paused=True, df=True)
        if df is None or len(df) < 250:
            return None
        closes = df['close'].values
        current = closes[-1]
        ret20 = (current / closes[-21] - 1) * 100
        ma20 = np.mean(closes[-20:])
        bias20 = (current / ma20 - 1) * 100
        ma60 = np.mean(closes[-60:])
        bias60 = (current / ma60 - 1) * 100
        ma250 = np.mean(closes[-250:])
        bias250 = (current / ma250 - 1) * 100
        return ret20, bias20, bias60, bias250
    except Exception as e:
        log.debug('{} 计算异常: {}'.format(security, e))
        return None

def filter_and_rank(context, current_dt):
    qualified = []
    for etf in g.etf_pool:
        res = check_etf(etf, context)
        if res is None:
            continue
        ret20, b20, b60, b250 = res
        if (ret20 > g.min_gain) and (b20 < g.bias20_max) and (b60 < g.bias60_max) and (b250 < g.bias250_max):
            qualified.append((etf, ret20))
    if not qualified:
        return []
    qualified.sort(key=lambda x: x[1], reverse=True)
    return [etf for etf, _ in qualified]

def get_current_hold(context):
    positions = context.portfolio.positions
    for etf in g.etf_pool:
        if etf in positions and positions[etf].total_amount > 0:
            return etf
    if g.cash_etf in positions and positions[g.cash_etf].total_amount > 0:
        return g.cash_etf
    return None

def cooling_check(etf, today):
    if etf not in g.last_sell_record:
        return False
    last = g.last_sell_record[etf]
    trade_days = get_trade_days(start_date=last, end_date=today)
    diff = len(trade_days) - 1
    return diff <= g.cooldown_days

def stop_loss_triggered(security, context):
    """检查是否触发止损：当前价格相对于持仓成本跌幅超过8%"""
    pos = context.portfolio.positions[security]
    if pos.total_amount == 0:
        return False
    avg_cost = pos.avg_cost
    if avg_cost <= 0:
        return False
    # 获取当前价格（使用最新行情）
    current_data = get_current_data()
    if security in current_data:
        current_price = current_data[security].last_price
    else:
        # 备选：用attribute_history获取最新收盘价
        df = attribute_history(security, 1, '1d', ['close'], skip_paused=True, df=True)
        if df is None or len(df) == 0:
            return False
        current_price = df['close'].iloc[-1]
    ret = (current_price - avg_cost) / avg_cost * 100
    return ret <= g.stop_loss_pct

def trade(context):
    today = context.current_dt.date()
    if context.current_dt.year < 2021:
        return

    # 1. 当前持仓
    current_hold = get_current_hold(context)

    # 2. 获得当日符合条件的ETF排名列表
    ranked_list = filter_and_rank(context, context.current_dt)

    # 3. 确定目标品种
    if not ranked_list:
        target = g.cash_etf
    else:
        target = ranked_list[0]

    # 4. 判断是否需要调仓（卖出条件）
    need_trade = False
    if current_hold is None:
        need_trade = True   # 空仓
    elif current_hold != target:
        # 当前有持仓且与目标不同，检查是否触发卖出条件
        if current_hold != g.cash_etf:
            # 条件1：止损
            if stop_loss_triggered(current_hold, context):
                need_trade = True
                log.info('触发止损: {}'.format(current_hold))
            else:
                # 条件2：不符合筛选条件
                res = check_etf(current_hold, context)
                if res is None:
                    need_trade = True
                else:
                    ret20, b20, b60, b250 = res
                    cond_self = (ret20 > g.min_gain) and (b20 < g.bias20_max) and (b60 < g.bias60_max) and (b250 < g.bias250_max)
                    # 条件3：排名 >= 4
                    rank = ranked_list.index(current_hold) + 1 if current_hold in ranked_list else len(ranked_list) + 1
                    if (not cond_self) or (rank >= 4):
                        need_trade = True
        else:
            # 当前持有银华日利，直接调仓
            need_trade = True

    if not need_trade:
        return

    # 5. 调仓：先清空所有持仓
    positions = context.portfolio.positions
    for etf in g.etf_pool:
        if etf in positions and positions[etf].total_amount > 0:
            log.info('清仓 ETF: {}'.format(etf))
            g.last_sell_record[etf] = today
            order_target_value(etf, 0)
    if g.cash_etf in positions and positions[g.cash_etf].total_amount > 0:
        log.info('清仓 银华日利')
        order_target_value(g.cash_etf, 0)

    # 6. 买入目标
    if target == g.cash_etf:
        cash = context.portfolio.available_cash
        if cash > 0:
            order_target_value(g.cash_etf, cash)
            log.info('买入银华日利，金额 {:.2f}'.format(cash))
    else:
        if cooling_check(target, today):
            log.info('{} 在冷却期内，暂不买入，今日空仓'.format(target))
            return
        total_value = context.portfolio.portfolio_value
        if total_value > 0:
            order_target_value(target, total_value)
            log.info('买入 {}，金额 {:.2f}'.format(target, total_value))