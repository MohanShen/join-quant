# Clone from JoinQuant
# postId: 8f57bd36b93e0d427721ef4bbfd198d9
# backtestId: b7e45ea8432e451321de07070ec3209b
# title: ETF网格交易策略 v30 — 渐进式网格策略简介

# -*- coding: utf-8 -*-
"""
ETF网格交易策略 v30 — 渐进式网格版 (精简聚焦)
────────────────────────────────────────────────────────
标的: 纳指ETF(513100) 30% | 黄金ETF(518880) 30% | 创业板(159915) 20% | 沪深300(510300) 20%

核心逻辑:
  4只ETF做渐进式网格 — 层越深间距越大、金额越大，适应超跌
  牛市动态底仓 — MA200上方时底仓比例从60%提至75%，提高资金利用率
  盘后破网重置 — 价格偏离15%后重置参考价

v30核心变更 (v29→v30):
  ① 去掉国债及所有相关功能: 弹药机制、买卖逻辑、统计、参数全部删除
  ② 权重重构: 纳指30% | 黄金30% | 创业板20% | 沪深30020%
  ③ 再平衡改为每ETF独立目标: 各ETF按cash_pct×base_pos_ratio计算底仓目标

调度:
  09:40~14:50 每10分钟 (网格交易 + 偏离触发再平衡)
  16:00 盘后破网重置
  收盘后 统计

资金结构:
  纳指ETF 30%: 底仓60%/75% + 网格40%/25%
  黄金ETF 30%: 底仓60%/75% + 网格40%/25%
  创业板  20%: 底仓60%/75% + 网格40%/25%
  沪深300 20%: 底仓60%/75% + 网格40%/25%
  渐进式网格: 层1-2每层3%配额→层3-4每层3.8%→层5-6每层4.8%→层7+每层6%

风控:
  偏离触发再平衡(每ETF底仓偏离±12.5%时调仓)
  盘后破网重置(双向)
"""
import numpy as np
from jqdata import *


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    if context.run_params.type == 'simple_backtest':
        set_option("avoid_future_data", True)
        log.info("回测模式：已启用 avoid_future_data")
    else:
        log.info("模拟交易模式：已跳过 avoid_future_data 设置")
    set_slippage(PriceRelatedSlippage(0.0003), type='fund')
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                              open_commission=0.0001, close_commission=0.0001,
                              close_today_commission=0.0001, min_commission=0.1), type='fund')
    log.set_level('order', 'error')
    log.set_level('system', 'error')

    # ==================== 网格标的 (4只全做网格) ====================
    g.grids = [
        {'code': '513100.XSHG', 'name': '纳指ETF',  'cash_pct': 0.30, 'atype': 'us_stock'},
        {'code': '518880.XSHG', 'name': '黄金ETF',  'cash_pct': 0.30, 'atype': 'gold'},
        {'code': '159915.XSHE', 'name': '创业板',    'cash_pct': 0.20, 'atype': 'growth'},
        {'code': '510300.XSHG', 'name': '沪深300',  'cash_pct': 0.20, 'atype': 'stock'},
    ]

    # ==================== 网格参数 ====================
    g.layer_pct = 0.15           # 基础每层用15%的ETF配额(=3%总资产)
    g.max_trade_pct = 0.30
    g.min_money = 2000
    g.buy_cooldown = 1

    # ==================== 渐进式网格参数 ====================
    # 每2层扩大一次参数，越深越大
    g.progressive_spacing_mult = 1.3    # 间距递进系数
    g.progressive_target_mult = 1.3     # 止盈递进系数
    g.progressive_amount_mult = 1.26    # 金额递进系数(3%→6%, 4层递进×1.26³≈2)

    # ==================== 动态间距参数 ====================
    g.vol_lookback = 60

    # ==================== 趋势增强参数 ====================
    g.ma_period = 200

    # ==================== 按资产类型差异化参数 ====================
    g.type_params = {
        'stock': {
            'base_spacing': 0.01, 'vol_scaling': 1.5, 'min_spacing': 0.003, 'max_spacing': 0.08,
            'sell_target': 0.015, 'init_pos_pct': 0.60,
            'trend_up_mult': 1.3, 'trend_down_mult': 1.0, 'min_sell_target': 0.01,
        },
        'gold': {
            'base_spacing': 0.01, 'vol_scaling': 1.5, 'min_spacing': 0.003, 'max_spacing': 0.08,
            'sell_target': 0.015, 'init_pos_pct': 0.60,
            'trend_up_mult': 1.3, 'trend_down_mult': 1.2, 'min_sell_target': 0.008,
        },
        'us_stock': {
            'base_spacing': 0.01, 'vol_scaling': 1.5, 'min_spacing': 0.003, 'max_spacing': 0.08,
            'sell_target': 0.015, 'init_pos_pct': 0.60,
            'trend_up_mult': 1.5, 'trend_down_mult': 1.0, 'min_sell_target': 0.01,
        },
        'growth': {
            'base_spacing': 0.01, 'vol_scaling': 1.5, 'min_spacing': 0.003, 'max_spacing': 0.08,
            'sell_target': 0.015, 'init_pos_pct': 0.60,
            'trend_up_mult': 1.3, 'trend_down_mult': 1.0, 'min_sell_target': 0.01,
        },
    }

    # ==================== 偏离触发再平衡参数 ====================
    # 基于每ETF底仓价值占总资产的比例（不是总仓位）
    # 各ETF底仓目标 = cash_pct × base_pos_ratio (熊市60%, 牛市75%按MA200判断)
    g.rebalance_base_ratio_bear = 0.60  # 熊市底仓比例(每ETF配额的60%为底仓)
    g.rebalance_base_ratio_bull = 0.75  # 牛市底仓比例(每ETF配额的75%为底仓)
    g.rebalance_deviation = 0.125       # 偏离±12.5%触发
    g.rebalance_cooldown = 3
    g.rebalance_log_enabled = False     # 再平衡日志开关

    # ==================== 破网重置参数 ====================
    g.breakout_reset_threshold = 0.15
    g.breakout_cooldown = 5

    # ==================== 网格状态初始化 ====================
    for gd in g.grids:
        tp = g.type_params.get(gd['atype'], {})
        gd['ref_price'] = None
        gd['cash_total'] = 0
        gd['positions'] = []
        gd['last_buy_price'] = None
        gd['base_shares'] = 0
        gd['base_cost'] = 0
        gd['last_buy_date'] = None
        gd['last_reset_date'] = None
        gd['sell_target_base'] = tp.get('sell_target', 0.015)
        gd['sell_target'] = gd['sell_target_base']
        gd['init_pos_pct'] = tp.get('init_pos_pct', 0.60)
        gd['min_sell_target'] = tp.get('min_sell_target', 0.01)
        gd['base_spacing'] = tp.get('base_spacing', 0.01)
        gd['grid_spacing'] = gd['base_spacing']
        # 趋势参数
        gd['trend_up_mult'] = tp.get('trend_up_mult', 1.3)
        gd['trend_down_mult'] = tp.get('trend_down_mult', 1.0)

    g.grid_initialized = False
    g.last_rebalance_date = None
    g.rebalance_log_printed = False

    # 名称映射
    g.etf_names = {}
    for gd in g.grids:
        try:
            g.etf_names[gd['code']] = get_security_info(gd['code']).display_name
        except:
            g.etf_names[gd['code']] = gd['name']

    # ==================== 统计 ====================
    g.stats = {
        'trades': [], 'total_pnl': 0.0,
        'wins': 0, 'losses': 0,
        'etf_pnl': {},
        'etf_stats': {},
        'start_date': None, 'first_value': None,
        'peak_value': 0, 'max_dd': 0, 'max_dd_date': '',
        'total_util': {'sum': 0.0, 'days': 0, 'min': 1.0, 'max': 0.0},
        'rebalance_count': 0,
    }
    all_codes = [gd['code'] for gd in g.grids]
    for code in all_codes:
        g.stats['etf_pnl'][code] = [0.0]
        g.stats['etf_stats'][code] = {'trades': 0, 'wins': 0, 'pnl': 0.0,
                                       'realized_pnl': 0.0, 'resets': 0}

    # 每10分钟检查一次
    for h in range(9, 15):
        for m in range(0, 60, 10):
            if h == 9 and m < 40:
                continue
            if h == 11 and m > 30:
                continue
            if h == 12:
                continue
            run_daily(grid_routine, time=f"{h:02d}:{m:02d}")
    run_daily(after_close, time='after_close')
    run_daily(after_close_reset, time='16:00')


def after_close_reset(context):
    """盘后16:00破网重置"""
    cd = get_current_data()
    for gd in g.grids:
        if gd['ref_price'] is None:
            continue
        code = gd['code']
        lp = cd[code].last_price
        if not (lp > 0) or cd[code].paused:
            continue

        reset_ok = True
        if gd['last_reset_date'] is not None:
            reset_ok = (context.current_dt.date() - gd['last_reset_date']).days >= g.breakout_cooldown
        if not reset_ok:
            continue

        ratio = lp / gd['ref_price']
        threshold = 1 + g.breakout_reset_threshold
        if 1 / threshold < ratio < threshold:
            continue

        direction = "上移" if ratio > 1 else "下移"
        g.stats['etf_stats'][code]['resets'] += 1
        gd['ref_price'] = lp
        # 保留last_buy_price，仅重置参考价
        gd['last_reset_date'] = context.current_dt.date()
        new_spacing = get_dynamic_spacing(code, context, gd)
        gd['base_spacing'] = new_spacing
        gd['grid_spacing'] = new_spacing
        gd['sell_target'] = gd['sell_target_base']
        log.info(f"  ↺ {gd['name']} 盘后重心{direction}至{lp:.3f} 间距{new_spacing*100:.2f}%"
                 f"（持有{len(gd['positions'])}笔网格仓）")


def init_grid(context):
    """初始化：买入所有标的"""
    total_cash = context.portfolio.total_value
    cd = get_current_data()

    # 网格ETF建仓
    for gd in g.grids:
        code = gd['code']
        gd['cash_total'] = total_cash * gd['cash_pct']
        df = get_price(code, count=5, end_date=context.previous_date,
                       frequency='1d', fields=['close'], skip_paused=False)
        if df is None or df.empty:
            continue
        gd['ref_price'] = df['close'].iloc[-1]
        lp = cd[code].last_price

        init_pct = gd['init_pos_pct']
        if lp and lp > 0 and not cd[code].paused:
            total_shares = int(gd['cash_total'] * init_pct / lp / 100) * 100
            if total_shares >= 100:
                _safe_order(code, total_shares)
                gd['ref_price'] = lp
                gd['base_shares'] = total_shares
                gd['base_cost'] = lp
                log.info(f"  初始建仓 {gd['name']}: {total_shares}股 @{lp:.3f}"
                         f" 底仓{init_pct*100:.0f}%(={gd['cash_pct']*100:.0f}%配额×{init_pct*100:.0f}%) (渐进式网格)")
                dyn_spacing = get_dynamic_spacing(code, context, gd)
                gd['base_spacing'] = dyn_spacing
                gd['grid_spacing'] = dyn_spacing
                log.info(f"    动态间距: {dyn_spacing*100:.2f}% 止盈: {gd['sell_target_base']*100:.1f}%")

        gd['positions'] = []
        gd['last_buy_price'] = None

    g.grid_initialized = True
    g.last_rebalance_date = context.current_dt.date()
    g.rebalance_log_printed = False
    log.info(f"初始化完成: {len(g.grids)}只网格(底仓60%~75%), v30")


def grid_routine(context):
    """盘中: 网格交易 + 偏离触发再平衡"""
    cd = get_current_data()

    if not g.grid_initialized:
        init_grid(context)

    if not g.grid_initialized:
        return

    total_log = []

    # ==================== 网格ETF处理 ====================
    for gd in g.grids:
        code = gd['code']
        if cd[code].paused:
            continue
        lp = cd[code].last_price
        if not (lp > 0):
            continue

        buy_log, sell_log = [], []
        did_sell = False

        # ==================== 趋势增强 ====================
        ma200 = get_ma200(code, context)
        if ma200 and ma200 > 0:
            trend_mult = gd['trend_up_mult'] if lp > ma200 else gd['trend_down_mult']
        else:
            trend_mult = 1.0
        gd['grid_spacing'] = gd['base_spacing'] * trend_mult
        gd['sell_target'] = max(gd['min_sell_target'], gd['sell_target_base'] * trend_mult)

        # ==================== 网格止盈卖出 ====================
        # 渐进式网格: 每笔仓位有独立止盈目标(买入时存入position)
        sell_shares_total = 0
        sold_positions = []
        for i, pos in enumerate(gd['positions']):
            pos_target = pos.get('sell_target', gd['sell_target'])
            if lp >= pos['buy_price'] * (1 + pos_target):
                sell_shares_total += pos['shares']
                sold_positions.append(i)

        if sell_shares_total >= 100:
            pos_info = context.portfolio.positions.get(code)
            actual_sell = min(sell_shares_total, pos_info.closeable_amount if pos_info else 0)
            actual_sell = int(actual_sell / 100) * 100
            if actual_sell >= 100:
                _safe_order(code, -actual_sell)
                for i in sorted(sold_positions, reverse=True):
                    pos = gd['positions'].pop(i)
                    pnl = (lp - pos['buy_price']) * pos['shares']
                    _record_trade(code, pnl, lp, pos)
                    sell_log.append(f"{gd['name']}({pos['buy_price']:.3f}→{lp:.3f},"
                                    f"{pos['shares']}股,+{(lp/pos['buy_price']-1)*100:.2f}%)")
                did_sell = True

        if len(gd['positions']) == 0:
            gd['last_buy_price'] = None

        if sell_log:
            total_log.append(f"  网格卖出: {' | '.join(sell_log)}")

        if did_sell:
            cur_shares = _get_shares(code, context)
            if cur_shares > 0:
                total_log.append(f"  {gd['name']}: {cur_shares}股={cur_shares*lp:,.0f}元"
                                 f"({len(gd['positions'])}笔持仓)"
                                 f" [间距{gd['grid_spacing']*100:.2f}%"
                                 f" 止盈{gd['sell_target']*100:.2f}%]")
            continue

        # ==================== 网格买入(渐进式) ====================
        next_layer = len(gd['positions']) + 1  # 下一层编号
        prog_spacing, prog_target, prog_layer_pct = get_progressive_params(next_layer, gd)

        trigger_price = gd['last_buy_price'] if gd['last_buy_price'] else gd['ref_price']
        if trigger_price and lp <= trigger_price * (1 - prog_spacing):
            cool_ok = True
            if gd['last_buy_date'] is not None:
                cool_ok = (context.current_dt.date() - gd['last_buy_date']).days >= g.buy_cooldown
            if cool_ok:
                total = context.portfolio.total_value
                etf_target = total * gd['cash_pct']
                layer_amount = etf_target * prog_layer_pct
                buy_amount = min(layer_amount, context.portfolio.available_cash)
                buy_amount = min(buy_amount, total * g.max_trade_pct)
                buy_shares = max(int(buy_amount / lp / 100) * 100, 100)
                cost = buy_shares * lp * 1.0002
                if context.portfolio.available_cash >= cost and cost >= g.min_money and buy_shares >= 100:
                    _safe_order(code, buy_shares)
                    gd['positions'].append({
                        'buy_price': lp, 'shares': buy_shares,
                        'date': str(context.current_dt.date()),
                        'layer': next_layer,
                        'sell_target': prog_target,
                        'spacing': prog_spacing,
                    })
                    gd['last_buy_price'] = lp
                    gd['last_buy_date'] = context.current_dt.date()
                    tier_name = ['小', '中', '大', '深'][(next_layer - 1) // 2] if next_layer <= 8 else '深'
                    buy_log.append(f"{gd['name']}({lp:.3f}≤触发价"
                                   f"{trigger_price*(1-prog_spacing):.3f},"
                                   f"{buy_shares}股,层{next_layer}({tier_name})"
                                   f"间距{prog_spacing*100:.1f}%止盈{prog_target*100:.1f}%)")

        if buy_log:
            total_log.append(f"  网格买入: {' | '.join(buy_log)}")

        has_activity = bool(sell_log) or bool(buy_log)
        cur_shares = _get_shares(code, context)
        if has_activity and cur_shares > 0:
            total_log.append(f"  {gd['name']}: {cur_shares}股={cur_shares*lp:,.0f}元"
                             f"({len(gd['positions'])}笔持仓)"
                             f" [间距{gd['grid_spacing']*100:.2f}%"
                             f" 止盈{gd['sell_target']*100:.2f}%]")

    if total_log:
        for msg in total_log:
            log.info(msg)

    # ==================== 偏离触发再平衡 ====================
    check_and_rebalance(context, cd)


def _record_trade(code, pnl, lp, pos, shares_override=None):
    """记录交易统计"""
    shares = shares_override if shares_override else pos['shares']
    g.stats['total_pnl'] += pnl
    g.stats['trades'].append({'code': code, 'pnl': pnl,
                              'pnl_pct': (lp / pos['buy_price'] - 1) * 100 if pos['buy_price'] > 0 else 0,
                              'date': str(__import__('datetime').datetime.now().date()),
                              'value': lp * shares})
    if pnl > 0:
        g.stats['wins'] += 1
    else:
        g.stats['losses'] += 1
    g.stats['etf_stats'][code]['trades'] += 1
    g.stats['etf_stats'][code]['pnl'] += pnl
    g.stats['etf_stats'][code]['realized_pnl'] += pnl
    if pnl > 0:
        g.stats['etf_stats'][code]['wins'] += 1


def _get_shares(code, context):
    """获取持仓股数"""
    pos = context.portfolio.positions.get(code)
    return pos.total_amount if pos and pos.total_amount > 0 else 0


def _safe_order(code, amount):
    try:
        return order(code, amount)
    except:
        return None


def get_dynamic_spacing(security, context, gd=None):
    """基于波动率动态计算网格间距"""
    try:
        df = attribute_history(security, g.vol_lookback + 1, '1d',
                                ['close'], skip_paused=True)
        if df is None or len(df) < 20:
            return gd.get('base_spacing', 0.01) if gd else 0.01
        closes = df['close'].values
        log_returns = np.log(closes[1:] / closes[:-1])
        daily_vol = np.std(log_returns)
        tp = g.type_params.get(gd['atype'], {}) if gd else {}
        scaling = tp.get('vol_scaling', 1.5)
        min_sp = tp.get('min_spacing', 0.003)
        max_sp = tp.get('max_spacing', 0.08)
        spacing = daily_vol * scaling
        spacing = max(min_sp, min(max_sp, spacing))
        return spacing
    except:
        return gd.get('base_spacing', 0.01) if gd else 0.01


def get_progressive_params(layer_num, gd):
    """根据网格层数返回渐进式参数

    渐进式网格: 每2层扩大参数
    - 层1-2: 基础参数(3%总资产)
    - 层3-4: 间距×1.3, 止盈×1.3, 金额×1.26
    - 层5-6: 间距×1.3², 止盈×1.3², 金额×1.26²
    - 层7+:  间距×1.3³, 止盈×1.3³, 金额×1.26³(≈6%总资产)
    """
    tier = (layer_num - 1) // 2  # 层1-2→tier0, 层3-4→tier1, ...
    spacing_mult = g.progressive_spacing_mult ** tier
    target_mult = g.progressive_target_mult ** tier
    amount_mult = g.progressive_amount_mult ** tier

    tp = g.type_params.get(gd['atype'], {})
    min_sp = tp.get('min_spacing', 0.003)
    max_sp = tp.get('max_spacing', 0.08)
    min_target = gd.get('min_sell_target', 0.01)

    # 间距和止盈基于当前动态值递进
    spacing = gd['grid_spacing'] * spacing_mult
    spacing = max(min_sp, min(max_sp, spacing))

    sell_target = gd['sell_target'] * target_mult
    sell_target = max(min_target, sell_target)

    # 金额基于基础层金额递进
    layer_pct = g.layer_pct * amount_mult

    return spacing, sell_target, layer_pct


def get_ma200(security, context):
    """计算200日均线"""
    try:
        df = attribute_history(security, g.ma_period, '1d',
                                ['close'], skip_paused=True)
        if df is None or len(df) < g.ma_period:
            return None
        return df['close'].mean()
    except:
        return None


def _find_grid(code):
    """根据代码查找网格数据"""
    for gd in g.grids:
        if gd['code'] == code:
            return gd
    return None


def check_and_rebalance(context, cd):
    """偏离触发再平衡：基于底仓价值，只管底仓

    判断偏离时只看底仓价值（base_shares × price）占总资产比例
    网格持仓不计入，避免"网格刚买就被再平衡卖掉"
    各ETF底仓目标 = cash_pct × base_pos_ratio (熊市60%, 牛市75%按MA200判断)
    日志: g.rebalance_log_enabled控制
    """
    total_value = context.portfolio.total_value
    if total_value <= 0:
        return

    if g.last_rebalance_date is not None:
        days_since = (context.current_dt.date() - g.last_rebalance_date).days
        if days_since < g.rebalance_cooldown:
            g.rebalance_log_printed = False
            return

    # ==================== 牛市动态底仓比例 ====================
    # 沪深300在MA200上方=牛市, 提高底仓比例
    hs300_code = [gd['code'] for gd in g.grids if '300' in gd['code']][0]
    ma200 = get_ma200(hs300_code, context)
    lp_bench = cd[hs300_code].last_price
    is_bull = ma200 and lp_bench and lp_bench > ma200
    base_pos_ratio = g.rebalance_base_ratio_bull if is_bull else g.rebalance_base_ratio_bear

    deviations = []

    for gd in g.grids:
        code = gd['code']
        price = cd[code].last_price
        if not (price and price > 0):
            continue

        base_shares = gd.get('base_shares', 0)
        if base_shares <= 0:
            continue
        base_value = base_shares * price
        cur_pct = base_value / total_value

        # 每ETF独立底仓目标
        base_target_pct = gd['cash_pct'] * base_pos_ratio
        rebalance_upper = base_target_pct * (1 + g.rebalance_deviation)
        rebalance_lower = base_target_pct * (1 - g.rebalance_deviation)

        if cur_pct > rebalance_upper or cur_pct < rebalance_lower:
            target_value = total_value * base_target_pct
            deviations.append({
                'code': code, 'name': gd['name'],
                'cur_pct': cur_pct, 'cur_value': base_value,
                'target_value': target_value,
                'target_pct': base_target_pct,
                'lower': rebalance_lower,
                'upper': rebalance_upper,
                'direction': 'over' if cur_pct > rebalance_upper else 'under',
            })

    if not deviations:
        return

    if g.rebalance_log_enabled and not g.rebalance_log_printed:
        market_label = "牛市区" if is_bull else "熊市区"
        log.info(f"→ 偏离触发再平衡 ({market_label}, "
                 f"底仓比例{base_pos_ratio*100:.0f}%, 偏离{g.rebalance_deviation*100:.1f}%)")
        g.rebalance_log_printed = True
    rebalanced = False

    # 第一步：处理超配 — 只卖底仓，不碰网格持仓
    for d in deviations:
        if d['direction'] != 'over':
            continue
        code = d['code']
        price = cd[code].last_price
        gd = _find_grid(code)
        if not gd:
            continue

        grid_shares = sum(p['shares'] for p in gd['positions'])
        pos = context.portfolio.positions.get(code)
        total_shares = pos.total_amount if pos and pos.total_amount > 0 else 0
        actual_base = total_shares - grid_shares
        sellable_base = max(0, int(actual_base / 100) * 100)
        if sellable_base < 100:
            continue

        sell_shares = int((d['cur_value'] - d['target_value']) / price / 100) * 100
        sell_shares = min(sell_shares, sellable_base)
        sell_shares = min(sell_shares, pos.closeable_amount if pos else 0)
        sell_shares = int(sell_shares / 100) * 100
        if sell_shares >= 100:
            _safe_order(code, -sell_shares)
            gd['base_shares'] = max(0, gd['base_shares'] - sell_shares)
            if g.rebalance_log_enabled:
                log.info(f"  减持底仓 {d['name']}: {d['cur_pct']*100:.1f}%>{d['upper']*100:.1f}%"
                         f" 卖出{sell_shares}股(网格{grid_shares}股受保护)→现金")
            rebalanced = True

    # 第二步：处理低配 — 只补底仓
    for d in deviations:
        if d['direction'] != 'under':
            continue
        code = d['code']
        price = cd[code].last_price
        if not (price and price > 0 and not cd[code].paused):
            continue

        buy_value = d['target_value'] - d['cur_value']
        if buy_value < g.min_money:
            continue

        buy_amount = min(buy_value, context.portfolio.available_cash)
        buy_shares = int(buy_amount / price / 100) * 100
        if buy_shares >= 100:
            _safe_order(code, buy_shares)
            gd = _find_grid(code)
            if gd:
                gd['base_shares'] = gd.get('base_shares', 0) + buy_shares
            if g.rebalance_log_enabled:
                log.info(f"  增持底仓 {d['name']}: {d['cur_pct']*100:.1f}%<{d['lower']*100:.1f}%"
                         f" 买入{buy_shares}股")
            rebalanced = True

    if rebalanced:
        g.last_rebalance_date = context.current_dt.date()
        g.stats['rebalance_count'] += 1
    else:
        g.last_rebalance_date = context.current_dt.date()


def after_close(context):
    """盘后统计"""
    v = context.portfolio.total_value
    s = g.stats
    if s['start_date'] is None:
        s['start_date'] = context.current_dt.date()
        s['first_value'] = v

    if v > s['peak_value']:
        s['peak_value'] = v
    if s['peak_value'] > 0:
        dd = (s['peak_value'] - v) / s['peak_value']
        if dd > s['max_dd']:
            s['max_dd'] = dd
            s['max_dd_date'] = str(context.current_dt.date())

    cd = get_current_data()
    all_codes = [gd['code'] for gd in g.grids]

    for code in all_codes:
        pos = context.portfolio.positions.get(code)
        if pos and pos.total_amount > 0:
            lp = cd[code].last_price
            cost = pos.total_amount * pos.avg_cost if pos.avg_cost else 0
            cur_val = pos.total_amount * lp
            unrealized = cur_val - cost
            realized = s['etf_stats'][code]['realized_pnl']
            cum_pnl = realized + unrealized
        else:
            cum_pnl = s['etf_stats'][code]['realized_pnl']
        s['etf_pnl'][code].append(cum_pnl)

    invested_pct = 1.0 - context.portfolio.available_cash / v if v > 0 else 0
    util = s['total_util']
    util['days'] += 1
    util['sum'] += invested_pct
    if invested_pct < util['min']:
        util['min'] = invested_pct
    if invested_pct > util['max']:
        util['max'] = invested_pct

    # 副图
    grid_codes = [gd['code'] for gd in g.grids]
    if len(s['etf_pnl'][grid_codes[0]]) > 1:
        record(纳指ETF=round(s['etf_pnl'][grid_codes[0]][-1], 0),
               黄金ETF=round(s['etf_pnl'][grid_codes[1]][-1], 0),
               创业板=round(s['etf_pnl'][grid_codes[2]][-1], 0),
               沪深300=round(s['etf_pnl'][grid_codes[3]][-1], 0))

    trade_days = get_trade_days(start_date=context.run_params.start_date,
                                end_date=context.run_params.end_date)
    if len(trade_days) > 0 and context.current_dt.date() == trade_days[-1] and not getattr(g, '_printed', False):
        g._printed = True
        _print_summary(context)


def _print_summary(context):
    s = g.stats
    v = context.portfolio.total_value
    sv = s['first_value'] or v
    total_ret = (v / sv - 1) * 100 if sv > 0 else 0
    days = len(s['etf_pnl'][g.grids[0]['code']])
    years = max(days / 250.0, 0.01)
    annual = ((v / sv) ** (1.0 / years) - 1) * 100 if sv > 0 else 0
    trades = s['trades']
    wins = s['wins']
    losses = s['losses']
    total = wins + losses
    wr = wins / total * 100 if total > 0 else 0
    wp = [t['pnl'] for t in trades if t['pnl'] > 0]
    lp_list = [t['pnl'] for t in trades if t['pnl'] < 0]
    avg_win = np.mean(wp) if wp else 0
    avg_loss = abs(np.mean(lp_list)) if lp_list else 0
    pf_str = f"{avg_win / avg_loss:.2f}" if avg_loss > 0 else "-- (无亏损)"
    trade_values = [t['value'] for t in trades]
    avg_trade_val = np.mean(trade_values) if trade_values else 0
    months = max(days / 21.0, 0.01)
    trades_per_month = total / months

    log.info("\n" + "=" * 70)
    log.info("       ETF网格交易 v30 渐进式网格版 回测总结")
    log.info("=" * 70)
    log.info(f"  回测: {s['start_date']} → {context.current_dt.date()}  ({days}天, {years:.1f}年)")
    log.info(f"  总收益: {total_ret:+.2f}%  年化: {annual:+.2f}%")
    log.info(f"  最大回撤: {s['max_dd']*100:.2f}% ({s['max_dd_date']})")
    log.info(f"  再平衡次数: {s['rebalance_count']}")
    log.info("-" * 40)
    log.info(f"  网格交易: {total}笔  ({trades_per_month:.1f}笔/月)")
    log.info(f"  胜率: {wr:.1f}%  盈亏比: {pf_str}")
    if wp:
        log.info(f"  总盈利: {sum(wp):+,.0f}  总亏损: {abs(sum(lp_list)):,.0f}")
    if trades:
        log.info(f"  平均每笔盈亏: {np.mean([t['pnl'] for t in trades]):+,.0f}")
        log.info(f"  平均每笔金额: {avg_trade_val:,.0f}")
    log.info("-" * 40)
    log.info("  ETF详细统计:")
    log.info(f"  {'ETF':<10} {'类型':>4} {'交易':>4} {'胜':>3} {'已实现':>10} {'浮盈':>10} {'合计':>10} {'重置':>4}")
    log.info(f"  {'-'*10} {'-'*4} {'-'*4} {'-'*3} {'-'*10} {'-'*10} {'-'*10} {'-'*4}")
    all_codes = [gd['code'] for gd in g.grids]
    all_names = [gd['name'] for gd in g.grids]
    all_types = ['网格'] * len(g.grids)
    for code, name, atype in zip(all_codes, all_names, all_types):
        es = s['etf_stats'][code]
        final_pnl = s['etf_pnl'][code][-1] if s['etf_pnl'][code] else 0
        realized = es['realized_pnl']
        unreal = final_pnl - realized
        log.info(f"  {name:<10} {atype:>4} {es['trades']:>4} {es['wins']:>3}"
                 f" {realized:>+10,.0f} {unreal:>+10,.0f} {final_pnl:>+10,.0f} {es['resets']:>4}")
    u = s['total_util']
    if u['days'] > 0:
        avg_u = u['sum'] / u['days'] * 100
        log.info(f"  总资金利用率: {avg_u:.0f}%({u['min']*100:.0f}~{u['max']*100:.0f})")
    log.info("=" * 70)
