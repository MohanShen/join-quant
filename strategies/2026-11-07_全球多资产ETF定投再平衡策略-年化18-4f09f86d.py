# Clone from JoinQuant
# postId: 4f09f86d6bfd86d09ef6b2393b6455d0
# backtestId: 33b1b53187828ffe42fbd94222cd089a
# title: 全球多资产ETF定投再平衡策略-年化18%+

# -*- coding: utf-8 -*-
# ============================================================
# 策略名称：全球多资产ETF定投再平衡策略（v4.5.5 双触发·5%台阶最终稳定版）
# 聚宽平台适配版（消除系统警告、修复实际成交金额计算、优化再平衡触发逻辑）
# 创建日期：2026-09-22
# 更新日期：2026-10-20
# ============================================================

from jqdata import *
import pandas as pd
import numpy as np
import datetime
from datetime import timedelta


# =============================================================================
# 通用辅助函数
# =============================================================================

def _to_date_str(dt):
    if dt is None:
        return None
    if hasattr(dt, 'strftime'):
        return dt.strftime('%Y-%m-%d')
    return str(dt)


def _fmt_money(x):
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return "N/A"


def _bare_code(code):
    if not code:
        return code
    return str(code).split('.')[0]


def _disp_width(s):
    return sum(2 if ord(c) > 0x2E7F else 1 for c in str(s))


def _pad(s, width, align='left'):
    s = str(s)
    pad = max(0, width - _disp_width(s))
    if align == 'right':
        return ' ' * pad + s
    if align == 'center':
        left = pad // 2
        return ' ' * left + s + ' ' * (pad - left)
    return s + ' ' * pad


def _assert_in_pool(code):
    if not hasattr(g, 'etf_codes_bare') or _bare_code(code) not in g.etf_codes_bare:
        raise ValueError(f"[SAFETY] 试图操作非 ETF 池标的: {code}，已拦截")
    return True


def _get_position(context, code):
    """兼容平台代码后缀不一致的持仓获取（消除聚宽 WARNING）"""
    positions = context.portfolio.positions
    if not positions:
        return None
    # ★ 使用 in 判断，避免触发聚宽系统的空持仓警告
    if code in positions:
        return positions[code]
    bare = _bare_code(code)
    for pk, pv in positions.items():
        if _bare_code(pk) == bare:
            return pv
    return None


def _get_amount(pos):
    """聚宽持仓数量字段：total_amount"""
    if pos is None:
        return 0
    amt = getattr(pos, 'total_amount', 0) or 0
    try:
        return int(amt)
    except Exception:
        return 0


def safe_order_value(context, security, target_value):
    """
    安全下单引擎
    返回: (实际下单金额, 实际买入/卖出的股数变化量)
    """
    if target_value <= 0:
        pos = _get_position(context, security)
        before_amt = _get_amount(pos)
        if before_amt > 0:
            order_target_value(security, 0)
            return 0, -before_amt
        return 0, 0

    cd = get_current_data()
    if cd[security].paused:
        log.warning(f"[安全下单] {security} 停牌，无法下单")
        return 0, 0
        
    price = cd[security].last_price
    if price <= 0 or np.isnan(price):
        log.warning(f"[安全下单] {security} 价格异常，放弃")
        return 0, 0

    if price >= cd[security].high_limit:
        log.warning(f"[安全下单] {security} 涨停，暂缓买入")
        return 0, 0
    if price <= cd[security].low_limit:
        log.warning(f"[安全下单] {security} 跌停，暂缓卖出")
        return 0, 0

    pos = _get_position(context, security)
    current_shares = _get_amount(pos)
    current_value = current_shares * price

    target_shares = (int(target_value / price) // 100) * 100
    if target_shares < 100 and target_value > 0:
        if context.portfolio.available_cash + current_value >= 100 * price:
            target_shares = 100
        else:
            return 0, 0

    actual_value = target_shares * price
    net_cash_needed = actual_value - current_value

    if net_cash_needed > context.portfolio.available_cash:
        log.warning(f"[安全下单] {security} 资金不足，自动缩减")
        max_shares = ((int((context.portfolio.available_cash + current_value) / price)) // 100) * 100
        if max_shares >= 100:
            target_shares = max_shares
            actual_value = target_shares * price
        else:
            return 0, 0

    if abs(target_shares - current_shares) < 100:
        return 0, 0

    try:
        order_target_value(security, actual_value)
        # 计算股数差值（注意：聚宽订单在回测中可能会立即部分/全部成交）
        # 为了获取真实的成交变化，我们稍微延后获取，或者直接信任目标股数差值
        delta_shares = target_shares - current_shares
        return actual_value, delta_shares
    except Exception as e:
        log.error(f"[安全下单] {security} 下单异常: {e}")
        return 0, 0


# =============================================================================
# 全局参数
# =============================================================================

ETF_POOL = [
    ('510300.XSHG', '沪深300', 0.05, '压舱石', 'A股', 0.50),
    ('588000.XSHG', '科创50', 0.07, '压舱石', 'A股', 0.50),
    ('513500.XSHG', '标普500', 0.08, '压舱石', '美股', 0.50),
    ('513100.XSHG', '纳指ETF', 0.13, '压舱石', '美股', 0.60),
    ('513520.XSHG', '日经ETF', 0.05, '进攻方向', '海外-日经', 0.35),
    ('513030.XSHG', '德国ETF', 0.05, '进攻方向', '海外-欧洲', 0.35),
    ('513080.XSHG', '法国ETF', 0.05, '进攻方向', '海外-欧洲', 0.35),
    ('513180.XSHG', '恒指科技', 0.05, '进攻方向', '中概恒科', 0.40),
    ('164824.XSHE', '印度ETF', 0.05, '进攻方向', '海外-新兴', 0.35),
    ('501018.XSHG', '南方原油', 0.05, '进攻方向', '能源', 0.35),
    ('159980.XSHE', '有色ETF', 0.05, '进攻方向', '商品', 0.35),
    ('159985.XSHE', '豆粕ETF', 0.05, '进攻方向', '商品', 0.35),
    ('159981.XSHE', '能源化工', 0.05, '进攻方向', '商品', 0.35),
    ('518880.XSHG', '黄金ETF', 0.10, '防守方向', '黄金', 0.30),
    ('515080.XSHG', '红利低波', 0.12, '防守方向', '红利', 0.20),
]

INVEST_AMOUNT = 6000
TOLERANCE = 0.10
REBALANCE_RATIO = 0.50
REBALANCE_STEP = 0.05
PCT_WINDOW = 500
WEIGHT_PCT = 0.50
WEIGHT_MA = 0.30
WEIGHT_DD = 0.20
GAP_K = 5.0
PREMIUM_THRESHOLDS = {
    'A股': 0.02, '美股': 0.03, '海外-日经': 0.03, '海外-欧洲': 0.03,
    '海外-新兴': 0.03, '中概恒科': 0.03, '能源': 0.04, '商品': 0.04,
    '黄金': 0.03, '红利': 0.02,
}
PREMIUM_THRESHOLD_FALLBACK = 0.03
TAKE_PROFIT_SELL_PCT = 0.50
TAKE_PROFIT_STEP = 0.20
FINAL_REPORT_DATE = None


# =============================================================================
# 初始化
# =============================================================================

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_option('order_volume_ratio', 1)
    set_order_cost(OrderCost(close_tax=0, open_commission=0.00013,
                             close_commission=0.00013, min_commission=5), type='fund')

    g.etf_pool = ETF_POOL
    g.etf_codes_set = set(item[0] for item in ETF_POOL)
    g.etf_codes_bare = set(_bare_code(item[0]) for item in ETF_POOL)
    g.etf_names_bare = {_bare_code(item[0]): item[1] for item in ETF_POOL}
    g.etf_meta_bare = {
        _bare_code(item[0]): {
            'code': item[0], 'name': item[1], 'weight': item[2],
            'direction': item[3], 'category': item[4], 'tp': item[5],
        } for item in ETF_POOL
    }

    g.invest_amount = INVEST_AMOUNT
    g.tolerance = TOLERANCE
    g.rebalance_ratio = REBALANCE_RATIO
    g.rebalance_step = REBALANCE_STEP
    g.pct_window = PCT_WINDOW
    g.weight_pct = WEIGHT_PCT
    g.weight_ma = WEIGHT_MA
    g.weight_dd = WEIGHT_DD
    g.gap_k = GAP_K
    g.premium_thresholds = PREMIUM_THRESHOLDS
    g.premium_threshold_fallback = PREMIUM_THRESHOLD_FALLBACK
    g.take_profit_sell_pct = TAKE_PROFIT_SELL_PCT
    g.take_profit_step = TAKE_PROFIT_STEP

    g.daily_asset = {}
    g.is_live = False
    g.initial_value = context.portfolio.portfolio_value
    if not g.initial_value or g.initial_value <= 0:
        g.initial_value = context.portfolio.cash

    g.invest_count = 0
    g.total_invested = 0.0
    g.total_sold = 0.0
    g.total_take_profit = 0.0
    g.invest_records = []
    g.rebalance_count = 0
    g.skipped_etfs = set()

    try:
        _init_pct = (context.portfolio.portfolio_value - g.initial_value) / g.initial_value \
                    if g.initial_value > 0 else 0.0
        _init_level = int(max(0.0, _init_pct) // g.rebalance_step)
    except Exception:
        _init_level = 0
    g.last_rebalance_level = _init_level

    g.etf_stats = {}
    g.verbose_log = True
    g.final_report_date = FINAL_REPORT_DATE

    run_daily(check_rebalance,       time='14:45', reference_security='000300.XSHG')
    run_daily(check_and_trade,       time='14:50', reference_security='000300.XSHG')
    run_daily(monitor_all_positions, time='14:59', reference_security='000300.XSHG')
    run_daily(after_market_close,    time='after_close', reference_security='000300.XSHG')

    log.info("=" * 88)
    log.info("全球多资产ETF定投再平衡策略初始化完成 v4.5.5 (双触发·5%台阶最终稳定版)")
    log.info(f"  运行环境: {'🔴 实盘' if g.is_live else '🟢 回测/模拟'}")
    log.info(f"  单次定投: {g.invest_amount} 元/次（每月两次，约 12000 元/月）")
    log.info(f"  账户初始总资产: {_fmt_money(g.initial_value)} 元")
    log.info(f"  ETF池: {len(g.etf_pool)} 只")
    log.info(f"  ★ 再平衡条件A：单标的权重偏离目标 ±{g.tolerance*100:.0f}% (仅超配可卖出)")
    log.info(f"  ★ 再平衡条件B：账户累计收益率每跨过 {g.rebalance_step*100:.0f}% 台阶")
    log.info(f"  ★ 定投日：每月第3个交易日 + 第15个交易日")
    log.info(f"  ★ 当前已触发台阶：{g.last_rebalance_level * g.rebalance_step * 100:.0f}%")
    log.info("=" * 88)


# =============================================================================
# 账本对账与订单管理
# =============================================================================

def _default_stats(code):
    tp_target = None
    for item in g.etf_pool:
        if item[0] == code:
            tp_target = item[5]
            break
    return {
        'buy_amount': 0.0,
        'sell_amount': 0.0,
        'holding_amount': 0,
        'current_tp_target': tp_target if tp_target is not None else 0.30,
    }


def _find_stats_by_bare(code):
    bare = _bare_code(code)
    for key, stats in g.etf_stats.items():
        if _bare_code(key) == bare:
            return stats
    return None


def _reconcile_etf_stats(context):
    fixed_count = 0
    for code, name, weight, direction, category, tp_target in g.etf_pool:
        if code not in g.etf_stats:
            g.etf_stats[code] = _default_stats(code)
        stats = g.etf_stats[code]

        pos = _get_position(context, code)
        actual_amount = _get_amount(pos)
        book_amount = stats.get('holding_amount', 0)

        if actual_amount != book_amount:
            if g.verbose_log:
                log.info(f"  ⚠️ 账本对账: {name}({code}) 账本 {book_amount} → 实际 {actual_amount}")
            stats['holding_amount'] = actual_amount
            fixed_count += 1

        if actual_amount == 0:
            if stats.get('buy_amount', 0) > 0 or stats.get('sell_amount', 0) > 0:
                if g.verbose_log:
                    log.info(f"  🔄 {name}({code}) 已清仓，重置账本止盈目标为 {tp_target}")
            stats['buy_amount'] = 0.0
            stats['sell_amount'] = 0.0
            stats['current_tp_target'] = tp_target
        else:
            if stats.get('buy_amount', 0) <= 0 and pos is not None:
                cost_basis = _probe_avg_cost(pos, code)
                if cost_basis and cost_basis > 0:
                    stats['buy_amount'] = cost_basis * actual_amount
                    if g.verbose_log:
                        log.info(f"  📝 追溯历史持仓: {name} 成本 {_fmt_money(stats['buy_amount'])} 元")

    if fixed_count > 0 and g.verbose_log:
        log.info(f"  ✅ 账本对账完成，共修正 {fixed_count} 只 ETF")


def _cancel_own_open_orders(context):
    codes_bare = g.etf_codes_bare
    try:
        open_orders = get_open_orders()
    except Exception as e:
        if g.verbose_log:
            log.warning(f"  ⚠️ 获取未成交订单失败: {e}")
        return

    if not open_orders:
        return

    cancelled = 0
    try:
        for code, orders in open_orders.items():
            if _bare_code(code) not in codes_bare:
                continue
            order_list = orders if isinstance(orders, (list, tuple)) else [orders]
            for o in order_list:
                try:
                    cancel_order(o)
                    cancelled += 1
                    if g.verbose_log:
                        log.info(f"  ⏹️ 撤销未成交订单: {code} ({getattr(o, 'order_id', '')})")
                except Exception as e:
                    log.warning(f"  ⚠️ 撤单失败 {code}: {e}")
    except Exception as e:
        if g.verbose_log:
            log.warning(f"  ⚠️ 遍历未成交订单异常: {e}")

    if cancelled > 0 and g.verbose_log:
        log.info(f"  ✅ 共撤销 {cancelled} 笔未成交订单")


# =============================================================================
# ★ 再平衡（双触发）
# =============================================================================

def _scan_weight_deviations(context, total_value):
    deviations = []
    if total_value <= 0:
        return deviations
    
    positions = context.portfolio.positions
    if not positions:
        return deviations

    # ★ 优化：如果持仓总市值占总资产比例极低（如 < 20%），说明处于定投建仓早期
    # 此时全市场都是严重低配，无需进行权重偏离检查（避免每日频繁误触发）
    total_mv = sum(_get_amount(p) * get_current_price(context, c, p) for c, p in positions.items() if _get_amount(p) > 0)
    if total_mv / total_value < 0.20:
        return deviations

    for code, name, target_w, direction, category, tp in g.etf_pool:
        pos = _get_position(context, code)
        actual_amount = _get_amount(pos)
        if actual_amount <= 0:
            continue
        price = get_current_price(context, code, pos)
        if not price or price <= 0:
            continue
        mv = actual_amount * price
        cw = mv / total_value
        dev = cw - target_w
        if abs(dev) > g.tolerance:
            deviations.append({
                'code': code, 'name': name, 'current_w': cw,
                'target_w': target_w, 'dev': dev, 'actionable': dev > 0,
            })
    return deviations


def check_rebalance(context):
    initial_value = getattr(g, 'initial_value', 0) or 0
    if initial_value <= 0:
        return

    total_value = context.portfolio.portfolio_value
    pct = (total_value - initial_value) / initial_value

    threshold_trigger = False
    current_level = int(max(0.0, pct) // g.rebalance_step)
    if pct >= 0 and current_level > g.last_rebalance_level:
        threshold_trigger = True

    deviations = _scan_weight_deviations(context, total_value)
    # 只有存在 actionable (超配) 的标的，才算真正的条件A触发
    deviation_trigger = any(d['actionable'] for d in deviations)

    if not threshold_trigger and not deviation_trigger:
        return

    log.info(f"\n{'=' * 88}")
    log.info(f"🎯 触发再平衡 | 日期: {context.current_dt.strftime('%Y-%m-%d')}")
    log.info(f"  账户累计收益率 : {pct * 100:+.2f}%")

    if threshold_trigger:
        threshold = (g.last_rebalance_level + 1) * g.rebalance_step * 100
        log.info(f"  [条件B] 首次突破台阶 {threshold:.0f}% "
                 f"（当前台阶 {current_level * g.rebalance_step * 100:.0f}%）")

    if deviation_trigger:
        log.info(f"  [条件A] 存在标的权重偏离超 ±{g.tolerance * 100:.0f}%：")
        for d in deviations:
            if d['actionable']:
                log.info(f"      · {d['name']}({d['code']}) "
                         f"当前 {d['current_w'] * 100:.1f}% / 目标 {d['target_w'] * 100:.1f}% "
                         f"| 偏差 {d['dev'] * 100:+.2f}%  [超配→卖出]")
    log.info(f"{'=' * 88}")

    execute_rebalance(context)

    if threshold_trigger:
        g.last_rebalance_level = current_level
        log.info(f"  ✅ 再平衡完成，已记录台阶至 {current_level * g.rebalance_step * 100:.0f}%")
    else:
        log.info(f"  ✅ 再平衡完成（由条件A权重偏离触发，台阶保持不变："
                 f"{g.last_rebalance_level * g.rebalance_step * 100:.0f}%）")
    log.info(f"{'=' * 88}\n")


def execute_rebalance(context):
    codes = [item[0] for item in g.etf_pool]
    names = {item[0]: item[1] for item in g.etf_pool}
    target_weights = {item[0]: item[2] for item in g.etf_pool}
    categories = {item[0]: item[4] for item in g.etf_pool}

    _cancel_own_open_orders(context)
    _reconcile_etf_stats(context)

    prices = {}
    for code in codes:
        pos = _get_position(context, code)
        prices[code] = get_current_price(context, code, pos)

    sold_any = False
    period_sold_amount = 0.0
    total_value = context.portfolio.portfolio_value

    for code in codes:
        pos = _get_position(context, code)
        actual_amount = _get_amount(pos)
        if actual_amount <= 0 or not prices.get(code):
            continue

        price = prices[code]
        market_value = actual_amount * price
        current_weight = market_value / total_value if total_value > 0 else 0.0
        dev = current_weight - target_weights[code]

        if dev > g.tolerance:
            avg_cost = _probe_avg_cost(pos, code)
            if avg_cost > 0 and price < avg_cost:
                if g.verbose_log:
                    loss_pct = (price - avg_cost) / avg_cost * 100
                    log.info(f"  ⏭️ {names[code]} 当前浮亏 {loss_pct:+.2f}%，"
                             f"跳过再平衡卖出（保留仓位待回本）")
                continue

            sell_value = dev * total_value * g.rebalance_ratio
            target_val = market_value - sell_value
            
            if get_premium_rate(context, code) > _get_premium_threshold(code, categories):
                if g.verbose_log:
                    log.info(f"  ⏭️ {names[code]} 溢价过高，跳过再平衡卖出")
                continue

            _assert_in_pool(code)
            actual_sold_val, delta_shares = safe_order_value(context, code, target_val)
            if delta_shares != 0:
                sold_any = True
                real_sold_val = -delta_shares * price
                period_sold_amount += real_sold_val
                g.etf_stats[code]['sell_amount'] += real_sold_val
                if g.verbose_log:
                    log.info(f"  📤 再平衡卖出 {names[code]} {abs(delta_shares)}股 | "
                             f"当前 {current_weight * 100:.1f}% / 目标 {target_weights[code] * 100:.0f}%")

    if sold_any:
        g.rebalance_count += 1
        g.total_sold += period_sold_amount
        log.info(f"  ✅ 本次再平衡共卖出 {_fmt_money(period_sold_amount)} 元 "
                 f"（累计 {g.rebalance_count} 次）")
    else:
        log.info(f"  ℹ️ 本次再平衡没有触发任何卖出（可能全部浮亏/未超配/溢价过高）")


# =============================================================================
# 定投日判断 & 定投主逻辑
# =============================================================================

def is_investment_day(context):
    today = context.current_dt.date()
    try:
        recent_days = get_trade_days(end_date=today, count=15)
    except Exception:
        return False

    current_month_days = [d for d in recent_days if d.year == today.year and d.month == today.month]
    if len(current_month_days) == 3 or len(current_month_days) == 15:
        return True
    return False


def check_and_trade(context):
    if not is_investment_day(context):
        return
    execute_investment(context)


def execute_investment(context):
    codes = [item[0] for item in g.etf_pool]
    names = {item[0]: item[1] for item in g.etf_pool}
    target_weights = {item[0]: item[2] for item in g.etf_pool}
    categories = {item[0]: item[4] for item in g.etf_pool}

    _cancel_own_open_orders(context)
    _reconcile_etf_stats(context)

    # --- 1. 获取价格 ---
    prices = {}
    unavailable = []
    for code in codes:
        pos = _get_position(context, code)
        price = get_current_price(context, code, pos)
        if price is None or price <= 0:
            unavailable.append(code)
            g.skipped_etfs.add(code)
        prices[code] = price
    if unavailable and g.verbose_log:
        log.info(f"  ⏭️ 数据不足跳过（未上市或停牌）: "
                 f"{', '.join([f'{names[c]}({c})' for c in unavailable])}")

    # --- 2. 价格评分 ---
    raw_metrics = {code: get_raw_metrics(context, code) for code in codes}
    scores = normalize_scores(raw_metrics, codes)

    # --- 3. 差异化止盈卖出 ---
    take_profit_any = False
    period_tp_amount = 0.0

    for code in codes:
        pos = _get_position(context, code)
        actual_amount = _get_amount(pos)
        if actual_amount <= 0 or not prices.get(code):
            continue

        stats = g.etf_stats[code]
        if stats.get('buy_amount', 0) <= 0:
            continue

        price = prices[code]
        current_mv = actual_amount * price
        total_profit = (current_mv + stats.get('sell_amount', 0.0)) - stats['buy_amount']
        total_return_pct = total_profit / stats['buy_amount']
        target_pct = stats.get('current_tp_target', 0.30)

        if total_return_pct >= target_pct:
            sell_shares = int(actual_amount * g.take_profit_sell_pct / 100) * 100
            if sell_shares <= 0:
                continue
            if get_premium_rate(context, code) > _get_premium_threshold(code, categories):
                if g.verbose_log:
                    log.info(f"  ⏭️ {names[code]} 溢价过高，跳过止盈卖出")
                continue

            target_val = current_mv - (sell_shares * price)
            _assert_in_pool(code)
            actual_sold_val, delta_shares = safe_order_value(context, code, target_val)
            if delta_shares != 0:
                take_profit_any = True
                real_sold_val = -delta_shares * price
                period_tp_amount += real_sold_val
                stats['sell_amount'] += real_sold_val
                stats['current_tp_target'] += g.take_profit_step
                if g.verbose_log:
                    log.info(f"  🎯 止盈卖出 {names[code]} {abs(delta_shares)}股 ≈ {_fmt_money(real_sold_val)} 元 | "
                             f"下次止盈目标 {stats['current_tp_target'] * 100:.0f}%")

    if take_profit_any:
        g.total_take_profit += period_tp_amount

    # --- 4. 资金保护 ---
    invest_amount = g.invest_amount
    available_cash = context.portfolio.cash
    if available_cash < 100:
        _log_period_summary(context)
        return
    if invest_amount > available_cash:
        invest_amount = available_cash

    # --- 5. 分配得分 ---
    total_value_after = context.portfolio.portfolio_value
    current_weights_after = {}
    for code in codes:
        pos = _get_position(context, code)
        actual_amount = _get_amount(pos)
        mv = actual_amount * prices[code] if (actual_amount > 0 and prices.get(code)) else 0.0
        current_weights_after[code] = (mv / total_value_after) if total_value_after > 0 else 0.0

    alloc_scores = {}
    for code in codes:
        if not prices.get(code) or prices[code] <= 0:
            alloc_scores[code] = 0.0
            continue
        dev = current_weights_after[code] - target_weights[code]
        if dev >= g.tolerance:
            alloc_scores[code] = 0.0
        else:
            gap = max(0.0, target_weights[code] - current_weights_after[code])
            try:
                val = float(scores[code])
                if np.isnan(val):
                    val = 0.0
                alloc_scores[code] = val * (1 + gap * g.gap_k)
            except Exception:
                alloc_scores[code] = 0.0

    total_score = 0.0
    for code in codes:
        try:
            sv = float(alloc_scores.get(code, 0.0))
            if not np.isnan(sv) and sv > 0:
                total_score += sv
        except Exception:
            pass

    if total_score <= 0:
        _log_period_summary(context)
        return

    # --- 6. 执行定投买入 ---
    period_invested_amount = 0.0
    remaining_cash = invest_amount

    for code in codes:
        if alloc_scores.get(code, 0.0) <= 0:
            continue
        buy_amount = min(invest_amount * (alloc_scores[code] / total_score), remaining_cash)
        if buy_amount < 100:
            continue
        price = prices.get(code)
        if not price or price <= 0:
            continue
        if get_premium_rate(context, code) > _get_premium_threshold(code, categories):
            if g.verbose_log:
                log.info(f"  ⏭️ {names[code]} 溢价过高，跳过买入")
            continue

        _assert_in_pool(code)
        pos = _get_position(context, code)
        current_val = _get_amount(pos) * price
        actual_bought_val, delta_shares = safe_order_value(context, code, current_val + buy_amount)
        
        if delta_shares > 0:
            real_bought_val = delta_shares * price
            period_invested_amount += real_bought_val
            remaining_cash -= real_bought_val
            g.etf_stats[code]['buy_amount'] += real_bought_val
            # 同步更新账本持股数
            g.etf_stats[code]['holding_amount'] += delta_shares
            if g.verbose_log:
                log.info(f"  📥 定投买入 {names[code]} {delta_shares}股 ≈ {_fmt_money(real_bought_val)} 元")

    # --- 7. 记录定投统计 ---
    g.invest_count += 1
    g.total_invested += period_invested_amount
    current_total_value = context.portfolio.portfolio_value
    invest_profit = current_total_value - g.initial_value
    invest_return_pct = (invest_profit / g.initial_value * 100) if g.initial_value > 0 else 0.0

    g.invest_records.append({
        'period': g.invest_count,
        'date': context.current_dt.strftime('%Y-%m-%d'),
        'invested': period_invested_amount,
        'cumulative_invested': g.total_invested,
        'invest_current_value': current_total_value,
        'cumulative_profit': invest_profit,
        'cumulative_return_pct': invest_return_pct,
    })

    _log_period_summary(context, period_invested_amount)


def _log_period_summary(context, period_invested_amount=0.0):
    total_value = context.portfolio.portfolio_value
    initial_value = g.initial_value
    gain_amount = total_value - initial_value
    gain_pct = (gain_amount / initial_value * 100) if initial_value > 0 else 0.0
    date_str = context.current_dt.strftime('%Y-%m-%d')

    try:
        cur_level = int(max(0.0, gain_amount / initial_value) // g.rebalance_step)
    except Exception:
        cur_level = 0

    log.info(f"\n{'=' * 88}")
    log.info(f"📌 第 {g.invest_count} 期定投 | 日期: {date_str}")
    log.info(f"  本期定投金额     : {_fmt_money(period_invested_amount)} 元")
    log.info(f"  累计定投本金     : {_fmt_money(g.total_invested)} 元")
    log.info(f"  账户总资产       : {_fmt_money(total_value)} 元")
    log.info(f"  初始总资产       : {_fmt_money(initial_value)} 元")
    log.info(f"  账户盈亏         : {gain_amount:+,.2f} 元")
    log.info(f"  相对初始总资产涨幅: {gain_pct:+.2f}%")
    log.info(f"  再平衡台阶进度   : 已触发 {g.last_rebalance_level * g.rebalance_step * 100:.0f}% / "
             f"当前 {cur_level * g.rebalance_step * 100:.0f}%")
    log.info(f"{'=' * 88}\n")


# =============================================================================
# 每日持仓监控（只读）
# =============================================================================

_COL_CODE_W   = 14
_COL_NAME_W   = 20
_COL_AMT_W    = 10
_COL_COST_W   = 11
_COL_PRICE_W  = 11
_COL_MV_W     = 16
_COL_PNL_W    = 16
_COL_PNLPCT_W = 11


def _probe_avg_cost(pos, code):
    if pos is None:
        return 0.0
    val = getattr(pos, 'avg_cost', None)
    try:
        v = float(val)
        if v > 0:
            return v
    except Exception:
        pass
    stats = _find_stats_by_bare(code)
    if stats:
        ha = stats.get('holding_amount', 0) or 0
        ba = stats.get('buy_amount', 0) or 0
        if ha > 0 and ba > 0:
            return ba / ha
    return 0.0


def _get_position_price(pos, context, code):
    return get_current_price(context, code, pos) or 0.0


def _get_position_name(pos, code):
    bare = _bare_code(code)
    if bare in g.etf_names_bare:
        return g.etf_names_bare[bare]
    for attr in ('name', 'security_name', 'stock_name', 'display_name'):
        val = getattr(pos, attr, None)
        if val:
            return str(val)
    return '—'


def _fmt_cell_code(code):
    return _pad(str(code), _COL_CODE_W)

def _fmt_cell_name(name):
    return _pad(str(name), _COL_NAME_W)

def _fmt_cell_amount(amount):
    try:
        return _pad(f"{int(amount):,}", _COL_AMT_W, 'right')
    except Exception:
        return _pad(str(amount), _COL_AMT_W, 'right')

def _fmt_cell_cost(cost):
    if cost and cost > 0:
        return _pad(f"{cost:.3f}", _COL_COST_W, 'right')
    return _pad("—", _COL_COST_W, 'right')

def _fmt_cell_price(price):
    if price and price > 0:
        return _pad(f"{price:.3f}", _COL_PRICE_W, 'right')
    return _pad("—", _COL_PRICE_W, 'right')

def _fmt_cell_mv(mv):
    return _pad(f"{mv:,.2f}", _COL_MV_W, 'right')

def _fmt_cell_pnl(pnl, valid):
    if not valid:
        return _pad("—", _COL_PNL_W, 'right')
    return _pad(f"{pnl:+,.2f}", _COL_PNL_W, 'right')

def _fmt_cell_pnl_pct(pct, valid):
    if not valid:
        return _pad("—", _COL_PNLPCT_W, 'right')
    return _pad(f"{pct:+.2f}%", _COL_PNLPCT_W, 'right')


def _build_table_header():
    return ("  "
            + _pad("代码", _COL_CODE_W)
            + _pad("名称", _COL_NAME_W)
            + _pad("数量", _COL_AMT_W, 'right')
            + _pad("成本价", _COL_COST_W, 'right')
            + _pad("现价", _COL_PRICE_W, 'right')
            + _pad("市值", _COL_MV_W, 'right')
            + _pad("盈亏", _COL_PNL_W, 'right')
            + _pad("盈亏%", _COL_PNLPCT_W, 'right'))


def _build_table_sep():
    total = 2 + _COL_CODE_W + _COL_NAME_W + _COL_AMT_W + _COL_COST_W + \
            _COL_PRICE_W + _COL_MV_W + _COL_PNL_W + _COL_PNLPCT_W
    return "  " + "-" * (total - 2)


def monitor_all_positions(context):
    date_str = context.current_dt.strftime('%Y-%m-%d')
    positions = context.portfolio.positions or {}
    active = []
    for code, pos in positions.items():
        amt = _get_amount(pos)
        if amt > 0:
            active.append((code, pos))

    log.info(f"\n{'━' * 100}")
    log.info(f"📊 [{date_str}] 账户持仓监控（只读，不下单）")
    log.info(f"{'━' * 100}")

    if not active:
        log.info("  当前账户无持仓")
        log.info(f"  可用现金   : {_fmt_money(context.portfolio.cash)} 元")
        log.info(f"  账户总资产 : {_fmt_money(context.portfolio.portfolio_value)} 元")
        _print_account_summary(context)
        log.info(f"{'━' * 100}\n")
        return

    in_pool, out_pool = [], []
    for code, pos in active:
        if _bare_code(code) in g.etf_codes_bare:
            in_pool.append((code, pos))
        else:
            out_pool.append((code, pos))

    pool_order = {_bare_code(item[0]): i for i, item in enumerate(g.etf_pool)}
    in_pool.sort(key=lambda x: pool_order.get(_bare_code(x[0]), 999))
    out_pool.sort(key=lambda x: _bare_code(x[0]))

    state = {'mv': 0.0, 'cost': 0.0, 'has_cost': False}

    def _print_section(title, rows, tag=''):
        if not rows:
            return
        log.info(f"\n  {title}共 {len(rows)} 只")
        log.info(_build_table_header())
        log.info(_build_table_sep())
        for code, pos in rows:
            amount = _get_amount(pos)
            avg_cost = _probe_avg_cost(pos, code)
            price = _get_position_price(pos, context, code)
            mv = amount * price
            cost = amount * avg_cost
            valid_cost = avg_cost > 0
            pnl = mv - cost
            pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0

            state['mv'] += mv
            if valid_cost:
                state['cost'] += cost
                state['has_cost'] = True

            name = _get_position_name(pos, code)
            line = ("  "
                    + _fmt_cell_code(code)
                    + _fmt_cell_name(name)
                    + _fmt_cell_amount(amount)
                    + _fmt_cell_cost(avg_cost)
                    + _fmt_cell_price(price)
                    + _fmt_cell_mv(mv)
                    + _fmt_cell_pnl(pnl, valid_cost)
                    + _fmt_cell_pnl_pct(pnl_pct, valid_cost))
            if tag:
                line += f"   {tag}"
            log.info(line)

    _print_section("【ETF 池内持仓 · 策略管辖】", in_pool)
    _print_section("【ETF 池外持仓 · 个股等 · 本策略不操作】", out_pool, tag='★ 不操作')

    log.info(f"\n  {'─' * 60}")
    log.info(f"  持仓总市值 : {_fmt_money(state['mv']):>18} 元")
    if state['has_cost']:
        log.info(f"  已知总成本 : {_fmt_money(state['cost']):>18} 元")
        log.info(f"  已知总盈亏 : {state['mv'] - state['cost']:>+18,.2f} 元")
    else:
        log.info(f"  已知总成本 : {'—':>18}")
        log.info(f"  已知总盈亏 : {'—':>18}")
    log.info(f"  可用现金   : {_fmt_money(context.portfolio.cash):>18} 元")
    log.info(f"  账户总资产 : {_fmt_money(context.portfolio.portfolio_value):>18} 元")
    _print_account_summary(context)
    log.info(f"{'━' * 100}\n")


def _print_account_summary(context):
    total_value = context.portfolio.portfolio_value
    initial_value = g.initial_value
    if not initial_value or initial_value <= 0:
        initial_value = total_value
    gain_amount = total_value - initial_value
    gain_pct = (gain_amount / initial_value * 100) if initial_value > 0 else 0.0

    try:
        cur_level = int(max(0.0, gain_amount / initial_value) // g.rebalance_step)
    except Exception:
        cur_level = 0

    log.info(f"  {'─' * 60}")
    log.info(f"  账户初始总资产 : {_fmt_money(initial_value):>18} 元")
    log.info(f"  账户累计盈亏   : {gain_amount:>+18,.2f} 元")
    log.info(f"  账户累计收益率 : {gain_pct:>+17.2f}%")
    log.info(f"  再平衡台阶进度 : 已触发 {g.last_rebalance_level * g.rebalance_step * 100:.0f}% / "
             f"当前 {cur_level * g.rebalance_step * 100:.0f}%")


# =============================================================================
# 溢价阈值、价格与指标获取（聚宽版）
# =============================================================================

def _get_premium_threshold(code, categories):
    cat = categories.get(code)
    return g.premium_thresholds.get(cat, g.premium_threshold_fallback)


def get_current_price(context, code, pos=None):
    if pos is not None:
        val = getattr(pos, 'price', None)
        try:
            if val is not None and not np.isnan(val) and float(val) > 0:
                return float(val)
        except Exception:
            pass
    try:
        cd = get_current_data()
        last_px = cd[code].last_price
        if last_px and not np.isnan(last_px) and float(last_px) > 0:
            return float(last_px)
    except Exception:
        pass
    try:
        end_date_str = _to_date_str(context.previous_date)
        df = get_price(code, end_date=end_date_str, count=1,
                       frequency='daily', fields=['close'], fq='pre')
        if df is not None and not df.empty:
            px = df['close'].values[-1]
            if not np.isnan(px) and px > 0:
                return float(px)
    except Exception:
        pass
    return None


def get_raw_metrics(context, stock):
    end_date_str = _to_date_str(context.previous_date)
    try:
        df = get_price(stock, end_date=end_date_str, count=g.pct_window + 20,
                       frequency='daily', fields=['close'], fq='pre')
    except Exception:
        return {'pct_rank': 0.5, 'ma_dev': 0.0, 'drawdown': 0.0}

    if df is None or df.empty:
        return {'pct_rank': 0.5, 'ma_dev': 0.0, 'drawdown': 0.0}

    closes = df['close'].dropna().values.astype(float)
    if len(closes) < 60:
        return {'pct_rank': 0.5, 'ma_dev': 0.0, 'drawdown': 0.0}

    current_price = closes[-1]
    window = min(len(closes), g.pct_window)
    recent = closes[-window:]
    
    if len(recent) == 0:
        return {'pct_rank': 0.5, 'ma_dev': 0.0, 'drawdown': 0.0}

    min_p, max_p = np.min(recent), np.max(recent)
    pct_rank = (current_price - min_p) / (max_p - min_p) if max_p > min_p else 0.5
    ma = np.mean(closes[-min(120, len(closes)):])
    ma_dev = (current_price - ma) / ma if ma > 0 else 0.0
    high = np.max(recent)
    drawdown = (current_price - high) / high if high > 0 else 0.0
    return {'pct_rank': pct_rank, 'ma_dev': ma_dev, 'drawdown': drawdown}


def normalize_scores(raw_metrics, codes):
    pct_vals = np.array([raw_metrics[c]['pct_rank'] for c in codes])
    ma_vals = np.array([raw_metrics[c]['ma_dev'] for c in codes])
    dd_vals = np.array([raw_metrics[c]['drawdown'] for c in codes])

    def rank_score(vals):
        n = len(vals)
        if n <= 1:
            return np.ones(n) * 0.5
        sorted_idx = np.argsort(vals)
        ranks = np.empty(n)
        ranks[sorted_idx] = np.arange(n)
        return 1.0 - (ranks / (n - 1))

    pct_scores = rank_score(pct_vals)
    ma_scores = rank_score(ma_vals)
    dd_scores = rank_score(dd_vals)

    return {
        code: (g.weight_pct * pct_scores[i]
               + g.weight_ma * ma_scores[i]
               + g.weight_dd * dd_scores[i])
        for i, code in enumerate(codes)
    }


def get_premium_rate(context, stock):
    return 0.0


# =============================================================================
# 收盘处理与最终报告
# =============================================================================

def _is_backtest_final_day(context):
    if getattr(g, 'final_report_date', None):
        return context.current_dt.strftime('%Y-%m-%d') == g.final_report_date
    try:
        end_date = context.run_params.end_date
        if hasattr(end_date, 'date'):
            ed = end_date.date()
        elif isinstance(end_date, str):
            ed = datetime.datetime.strptime(end_date[:10], '%Y-%m-%d').date()
        else:
            ed = end_date
        return context.current_dt.date() >= ed
    except Exception:
        return False


def _print_final_report(context):
    total_value = context.portfolio.portfolio_value
    initial_value = g.initial_value
    total_invested = g.total_invested
    invest_profit = total_value - initial_value
    invest_return_pct = (invest_profit / initial_value * 100) if initial_value > 0 else 0.0

    if g.daily_asset:
        dates = sorted(g.daily_asset.keys())
        start_date, end_date, trading_days = dates[0], dates[-1], len(dates)
    else:
        start_date = 'N/A'
        end_date = context.current_dt.strftime('%Y-%m-%d')
        trading_days = 0

    annual_return_pct = 0.0
    if trading_days > 0 and initial_value > 0:
        try:
            annual_return_pct = ((1 + invest_profit / initial_value)
                                 ** (250.0 / trading_days) - 1) * 100
        except Exception:
            pass

    log.info("\n\n" + "╔" + "═" * 96 + "╗")
    log.info("║" + "【回测最终统计报告 - 定投专项】".center(84) + "║")
    log.info("╚" + "═" * 96 + "╝")
    log.info("─" * 98)
    log.info("【一、回测概况】")
    log.info(f"  回测区间              : {start_date}  ~  {end_date}")
    log.info(f"  交易日数              : {trading_days} 天 | 定投总期数: {g.invest_count} 期")
    log.info(f"  再平衡次数            : {g.rebalance_count} 次 "
             f"（双触发：权重偏离 ±{g.tolerance*100:.0f}% 或 收益率台阶 {g.rebalance_step*100:.0f}%）")

    log.info("─" * 98)
    log.info("【二、★ 定投专项统计】")
    log.info(f"  累计定投投入本金      : {_fmt_money(total_invested):>20} 元")
    log.info(f"  账户当前总资产        : {_fmt_money(total_value):>20} 元")
    log.info(f"  账户累计盈亏          : {invest_profit:>+20,.2f} 元")
    log.info(f"  账户累计收益率        : {invest_return_pct:>+19.2f}%")
    log.info(f"  近似年化收益率        : {annual_return_pct:>+19.2f}%")
    log.info(f"  累计再平衡卖出        : {_fmt_money(g.total_sold):>20} 元")
    log.info(f"  累计策略止盈卖出      : {_fmt_money(g.total_take_profit):>20} 元")

    log.info("─" * 98)
    log.info("【三、账户层面信息】")
    log.info(f"  账户初始总资产        : {_fmt_money(initial_value):>20} 元")
    log.info(f"  账户当前总资产        : {_fmt_money(total_value):>20} 元")
    log.info(f"  账户总盈亏            : {total_value - initial_value:>+20,.2f} 元")
    log.info(f"  账户总收益率          : {((total_value - initial_value) / initial_value * 100):>+19.2f}%")
    log.info(f"  再平衡已触发台阶      : {g.last_rebalance_level * g.rebalance_step * 100:.0f}%")

    log.info("─" * 98)
    log.info("【四、定投记录明细】")
    if g.invest_records:
        log.info(f"  {'期数':<4} {'日期':<12} {'本期投入':>12} {'累计本金':>14} "
                 f"{'账户现值':>14} {'累计盈亏':>14} {'累计收益率':>12}")
        log.info("  " + "-" * 88)
        for rec in g.invest_records:
            log.info(f"  {rec['period']:<4} {rec['date']:<12} "
                     f"{rec['invested']:>12,.2f} {rec['cumulative_invested']:>14,.2f} "
                     f"{rec['invest_current_value']:>14,.2f} "
                     f"{rec['cumulative_profit']:>+14,.2f} "
                     f"{rec['cumulative_return_pct']:>+11.2f}%")
    log.info("═" * 98)


def after_market_close(context):
    total_value = context.portfolio.portfolio_value
    date_str = context.current_dt.strftime('%Y-%m-%d')
    g.daily_asset[date_str] = total_value

    if _is_backtest_final_day(context):
        _print_final_report(context)


def handle_data(context, data):
    pass