# Clone from JoinQuant
# postId: bba81e385a9fa79435c5054f3a6493e0
# backtestId: 9d375022980936d802623c1ce1332141
# title: 热点概念追踪 低吸小市值

# -*- coding: utf-8 -*-
"""
小市值 + 启动点 + 固定概念策略（周频版）
===========================================
基于 small_cap_high_limitup_concept.py 修改：
  1. 不再动态分析热点概念，固定跟踪 6 个核心概念：
     "华为概念"、"人工智能"、"机器人概念"、"军工"、"光伏概念"、"锂电池概念"
  2. 每周一从每个固定概念中选出启动点偏离度最低的股票买入
  3. 止损后该股票 20 个交易日内不再买入
  4. 止盈止损、空仓期、放量控制等逻辑保留不变
"""

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import datetime as dt
from datetime import timedelta
from collections import defaultdict


# ============================================================
#  概念查询（简化版 — 只查询固定概念归属）
# ============================================================

def get_fixed_concept_stocks(context, stock_list):
    """
    查询候选股中哪些属于固定 6 大概念
    返回: {概念名: [股票代码, ...]} 按偏离度升序
    （stock_list 已是偏离度升序，概念池顺序即偏离度顺序）
    """
    yesterday_str = context.previous_date.strftime('%Y-%m-%d')
    concept_pool = defaultdict(list)

    try:
        cd_map = get_concept(stock_list, yesterday_str)
        log.info(f"  ✔ 批量概念查询: {len(stock_list)}只候选股 → 1次get_concept")
    except Exception:
        cd_map = {}

    for code in stock_list:
        cd = cd_map.get(code, {})
        concepts = cd.get('jq_concept', [])
        for c in concepts:
            if c['concept_name'] in g.fixed_concepts:
                concept_pool[c['concept_name']].append(code)

    # stock_to_concept_map: stock → [概念1, 概念2, ...]
    stock_to_concept = defaultdict(list)
    for cname, codes in concept_pool.items():
        for code in codes:
            stock_to_concept[code].append(cname)

    g._stock_to_concept_map = dict(stock_to_concept)

    total_coverage = sum(len(v) for v in concept_pool.values())
    log.info(f"固定概念覆盖: {total_coverage} 只候选股")
    for cname in g.fixed_concepts:
        count = len(concept_pool.get(cname, []))
        if count > 0:
            log.info(f"  {cname}: {count} 只")

    return concept_pool


# ============================================================
#  初始化
# ============================================================

def after_code_changed(context):
    log.info(f"{context.current_dt} 代码替换完成（固定概念·周频）")
    unschedule_all()

    set_option('avoid_future_data', True)
    set_benchmark('399101.XSHE')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.02), type="stock")
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0.0005,
                  open_commission=0.0005, close_commission=0.0005,
                  close_today_commission=0, min_commission=5),
        type="stock",
    )
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')

    # 全局变量
    g.no_trading_today_signal = False
    g.pass_april = True
    g.run_stoploss = True

    g.hold_list = []
    g.yesterday_HL_list = []
    g.target_list = []
    g.not_buy_again = []
    g.bought_today = []

    g.stock_num = 6
    g.max_stock_num = g.stock_num * 3
    g.up_price = 300
    g.limit_days_window = 3 * 250
    g.init_stock_count = 1000
    g.reason_to_sell = ''

    g.stoploss_strategy = 3
    g.stoploss_limit = 0.90
    g.stoploss_market = 0.93

    # 固定概念清单（可在自动化注入前修改）
    g.fixed_concepts = [
        '华为概念',
        '人工智能',
        '机器人概念',
        '军工',
        '光伏概念',
        '锂电池概念',
    ]

    g.no_trading_buy = ['511880.XSHG']
    g.no_trading_hold_signal = False

    # 止损黑名单：{stock_code: 止损日期_str}，20个交易日内不买入
    g.stoploss_blacklist = {}

    # 周频调仓：周一卖出→买入
    run_daily(prepare_stock_list,    time='09:05:00')
    run_weekly(weekly_sell,        1, time='10:26:00')
    run_weekly(weekly_buy,         1, time='10:27:00')
    run_daily(sell_stocks,           time='10:00:00')
    run_daily(trade_sell,            time='14:44:30')
    run_daily(trade_buy,             time='14:45:00')
    run_daily(close_account,         time='14:50:00')
    run_daily(print_position_info,   time='15:10')

    log.info("")
    log.info("=" * 60)
    log.info("🚀 小市值 + 启动点 + 固定6概念（周频·周一）初始化完成")
    log.info(f"固定概念: {g.fixed_concepts}")
    log.info(f"每只{int(g.stock_num)}只 | 止损线{g.stoploss_limit*100:.0f}% | 止损黑名单20日")
    log.info("=" * 60)


# ============================================================
#  准备股票池
# ============================================================

def prepare_stock_list(context):
    date_str = context.current_dt.strftime('%Y-%m-%d %a')
    cash = context.portfolio.cash
    total = context.portfolio.total_value
    log.info("")
    log.info(f"{'='*60}")
    log.info(f"📅 {date_str} | 总资产 {total:.0f} | 现金 {cash:.0f} | 持仓 {len(context.portfolio.positions)}只")

    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        g.hold_list.append(position.security)

    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date,
                       frequency='daily', fields=['close', 'high_limit', 'low_limit'],
                       count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
        if g.yesterday_HL_list:
            log.info(f"📈 持仓中昨日涨停: {g.yesterday_HL_list}")
    else:
        g.yesterday_HL_list = []

    g.no_trading_today_signal = today_is_between(context)


# ============================================================
#  启动点偏离度（核心因子）
# ============================================================

def get_start_point(context, stock_list, days=3*250):
    """
    计算股票启动点及当前价格偏离度（含时间衰减惩罚）

    找最近一次涨停 → 向前找首个阴线最低价作为启动点
    → 偏离度 = (现价 / 启动点) / 时间衰减系数

    时间衰减规则（基于最近一次涨停距今的时间）：
      近 1 年（≤365天）：÷ 1.00（100%，原始值，不变）
      1~2 年（366~730天）：÷ 0.80（=×1.25，放大25%）
      2~3 年（731~1095天）：÷ 0.50（=×2.00，放大100%）
      3 年以上：÷ 0.30（=×3.33，放大233%）

    由于排序取偏离度最小的，老启动点通过除法惩罚放大偏离度，
    使其排名后移——避免长期下跌的股票因启动点过时而虚低。
    """
    df = get_price(stock_list, end_date=context.previous_date, frequency='daily',
                   fields=['open', 'low', 'close', 'high_limit'], count=days, panel=False)

    stock_start_point = {}
    stock_limitup_dates = {}
    stock_price_bias = {}
    current_data = get_current_data()
    prev_date = context.previous_date

    df = df.sort_values(['code', 'time'])
    for code, group in df.groupby('code'):
        close_arr = group['close'].values
        high_limit_arr = group['high_limit'].values
        open_arr = group['open'].values
        low_arr = group['low'].values
        limit_indices = np.where(close_arr == high_limit_arr)[0]
        if len(limit_indices) > 0:
            latest_idx = limit_indices[-1]
            limitup_date = group.iloc[latest_idx]['time']
            if hasattr(limitup_date, 'date'):
                limitup_date = limitup_date.date()
            elif isinstance(limitup_date, np.datetime64):
                limitup_date = pd.Timestamp(limitup_date).date()
            stock_limitup_dates[code] = limitup_date

            for j in range(latest_idx, -1, -1):
                if close_arr[j] < open_arr[j]:
                    stock_start_point[code] = low_arr[j]
                    break

    for code, start_point in stock_start_point.items():
        last_price = current_data[code].last_price
        raw_bias = last_price / start_point

        limitup_date = stock_limitup_dates.get(code)
        if limitup_date is not None:
            days_since = (prev_date - limitup_date).days
            if days_since <= 365:
                decay = 1.00
            elif days_since <= 730:
                decay = 0.80
            elif days_since <= 1095:
                decay = 0.50
            else:
                decay = 0.30
        else:
            decay = 1.00

        stock_price_bias[code] = raw_bias / decay

    sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1])
    sorted_codes = [i[0] for i in sorted_list]
    log.info(f"偏离度排序（含时间衰减）: {len(sorted_codes)}只")
    if len(sorted_list) >= 3:
        top3 = ' '.join([f"{s[0]}({s[1]:.2f})" for s in sorted_list[:3]])
        log.info(f"最低Top3（衰减后）: {top3}")
    return sorted_codes, stock_price_bias


# ============================================================
#  选股
# ============================================================

def get_stock_list(context):
    # 日频缓存：同一交易日只跑一次
    prev_date = context.previous_date
    if (hasattr(g, '_cached_stock_date') and g._cached_stock_date == prev_date
            and hasattr(g, '_cached_stock_list')):
        log.info(f"▶ 选股流程（缓存命中 {prev_date}，{len(g._cached_stock_list)} 只）")
        g._deviation_map = g._cached_stock_deviation_map
        return g._cached_stock_list

    yesterday = context.previous_date
    initial_list = get_all_securities().index.tolist()
    total_count = len(initial_list)

    log.info("")
    log.info("▶ 选股流程")

    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    log.info(f"├─ 基础过滤: {total_count} → {len(initial_list)}只")

    q = query(valuation.code, valuation.circulating_market_cap, indicator.eps).filter(
        valuation.code.in_(initial_list)).order_by(valuation.circulating_market_cap.asc())
    df = get_fundamentals(q)
    initial_list = df['code'].tolist()[:g.init_stock_count]
    log.info(f"├─ 小市值: → {len(initial_list)}只")

    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    log.info(f"├─ 涨跌停过滤: → {len(initial_list)}只")

    # 启动点偏离度排序
    initial_list, deviation_map = get_start_point(context, initial_list, g.limit_days_window)

    # 查询固定6大概念的归属
    log.info(f"├─ 查询固定6大概念归属...")
    concept_pool = get_fixed_concept_stocks(context, initial_list)

    # 每个概念取偏离度最低的1只，尽量不重复
    stock_to_concept = getattr(g, '_stock_to_concept_map', {})
    selected_codes = set()
    for cname in g.fixed_concepts:
        codes_for_concept = concept_pool.get(cname, [])
        if not codes_for_concept:
            continue
        chosen = None
        for code in codes_for_concept:
            if code not in selected_codes:
                chosen = code
                break
        if chosen is None:
            chosen = codes_for_concept[0]
        selected_codes.add(chosen)

    # 候选池 = 所有被选中的 + 从概念池按偏离度补充到 max_stock_num
    all_concept_stocks = set()
    for codes in concept_pool.values():
        all_concept_stocks.update(codes)

    final_list = list(selected_codes)
    remaining = g.max_stock_num - len(final_list)
    if remaining > 0:
        for code in initial_list:
            if code not in final_list and code in all_concept_stocks:
                final_list.append(code)
                if len(final_list) >= g.max_stock_num:
                    break

    log.info(f"├─ 固定概念候选: {len(selected_codes)}只（每概念取最低偏离度1只）")
    log.info(f"├─ 最终候选池: {len(final_list)}只")
    log.info(f"")
    log.info(f"📋 最终候选池偏离度:")
    log.info(f"{'股票代码':<12}{'名称':<10}{'偏离度':<10}{'所属固定概念'}")
    log.info(f"{'─'*50}")
    yesterday_str = context.previous_date.strftime('%Y-%m-%d')
    for code in final_list:
        dev = deviation_map.get(code, float('inf'))
        current_data = get_current_data()
        name = current_data[code].name
        cons = ','.join(stock_to_concept.get(code, []))
        fire = '🔥' if dev <= 0.5 else '✨' if dev <= 0.75 else ''
        log.info(f"{fire}{code:<12}{name:<10}{dev:<10.3f}{cons}")
    log.info(f"{'─'*50}")

    g._cached_stock_date = prev_date
    g._cached_stock_list = final_list
    g._cached_stock_deviation_map = deviation_map
    g._deviation_map = deviation_map
    return final_list


# ============================================================
#  持仓概念批量查询（供卖出判断用）
# ============================================================

def get_stock_concepts_for_list(context, stock_list):
    """批量获取股票所属的概念名称列表，返回 {code: [概念名, ...]}"""
    date_str = context.previous_date.strftime('%Y-%m-%d')
    result = {}
    try:
        cd_map = get_concept(stock_list, date_str)
        log.info(f"  ✔ 批量概念查询: {len(stock_list)}只持仓股 → 1次get_concept")
        for code in stock_list:
            result[code] = [c['concept_name'] for c in cd_map.get(code, {}).get('jq_concept', [])]
    except Exception:
        for code in stock_list:
            result[code] = []
    return result


# ============================================================
#  止损黑名单管理（止损后20交易日不买入）
# ============================================================

def update_stoploss_blacklist(context):
    """清理已过期（>20交易日）的止损黑名单"""
    if not hasattr(g, 'stoploss_blacklist'):
        g.stoploss_blacklist = {}
    if not g.stoploss_blacklist:
        return

    current_date = context.previous_date
    all_trade_days = get_all_trade_days()
    current_idx = np.where(all_trade_days == current_date)[0]
    if len(current_idx) == 0:
        return
    current_idx = current_idx[0]

    expired = []
    for code, stop_date_str in g.stoploss_blacklist.items():
        stop_date = dt.datetime.strptime(stop_date_str, '%Y-%m-%d').date()
        stop_idx = np.where(all_trade_days == stop_date)[0]
        if len(stop_idx) == 0:
            continue
        trading_days_since = current_idx - stop_idx[0]
        if trading_days_since > 20:
            expired.append(code)

    for code in expired:
        del g.stoploss_blacklist[code]

    if expired:
        log.info(f"  止损黑名单清理: {len(expired)} 只已过期（>20交易日）")


def is_in_stoploss_blacklist(code):
    """检查股票是否在止损黑名单中"""
    if not hasattr(g, 'stoploss_blacklist'):
        return False
    return code in g.stoploss_blacklist


# ============================================================
#  每周一卖出（简化版：只做杂项清理）
# ============================================================

def weekly_sell(context):
    """周一检查持仓：不属于6大固定概念的卖出"""
    if g.no_trading_today_signal:
        return
    close_no_trading_hold(context)

    g.not_buy_again = []
    g.bought_today = []
    g.target_list = get_stock_list(context)
    deviation_map = getattr(g, '_deviation_map', {})

    current_hold_list = [s for s in list(context.portfolio.positions.keys()) if not s.startswith('511')]
    stock_concepts = get_stock_concepts_for_list(context, current_hold_list)

    log.info("")
    log.info("▶ 周一调仓卖出（固定6概念检测）")
    log.info(f"  固定概念: {g.fixed_concepts}")

    sell_count, hold_count = 0, 0
    for stock in current_hold_list:
        current_data = get_current_data()
        stock_name = current_data[stock].name
        if current_data[stock].paused:
            log.info(f"│  {stock}({stock_name}) [停牌] 保留")
            hold_count += 1
            continue
        if current_data[stock].last_price <= current_data[stock].low_limit:
            log.info(f"│  {stock}({stock_name}) [跌停] 跳过")
            hold_count += 1
            continue

        cons = stock_concepts.get(stock, [])
        cons_set = set(cons)
        in_fixed = bool(cons_set & set(g.fixed_concepts))
        is_limitup_yesterday = stock in g.yesterday_HL_list

        matched = [c for c in cons if c in g.fixed_concepts]
        log.info(f"│  📋 诊断 {stock}({stock_name}) 概念={cons} | in_fixed={in_fixed} matched={matched} | 昨日涨停={is_limitup_yesterday}")

        if in_fixed or is_limitup_yesterday:
            reason = f"固定概念: {','.join(matched)}" if in_fixed else '昨日涨停'
            log.info(f"│  🟢 保留 {stock}({stock_name}) [{reason}] 偏离{deviation_map.get(stock, 0):.3f}")
            hold_count += 1
        else:
            log.info(f"│  🔴 卖出 {stock}({stock_name}) [不属于固定6概念] 偏离{deviation_map.get(stock, 0):.3f}")
            close_position(context.portfolio.positions[stock])
            g.not_buy_again.append(stock)
            sell_count += 1

    log.info(f"└─ 调仓卖出{sell_count}只 | 保留{hold_count}只")


# ============================================================
#  每周一买入（固定概念最低偏离度）
# ============================================================

def weekly_buy(context):
    """周一买入：固定6概念，每个概念选偏离度最低的，买满 g.stock_num 只"""
    if g.no_trading_today_signal:
        return

    target_list = getattr(g, 'target_list', [])
    deviation_map = getattr(g, '_deviation_map', {})

    if not target_list or not deviation_map:
        log.info("⚠ 无候选数据，跳过买入")
        return

    log.info("")
    log.info("▶ 周一买入（固定6概念·最低偏离度）")

    buy_fixed_concept(context, target_list, deviation_map)

    for position in list(context.portfolio.positions.values()):
        g.not_buy_again.append(position.security)


def buy_fixed_concept(context, candidate_list, deviation_map):
    """
    固定概念买入逻辑：
    1. 遍历 g.fixed_concepts，每个概念找到候选池中偏离度最低的股票
    2. 排除止损黑名单中的股票
    3. 按偏离度升序买入，最多买 g.stock_num 只
    """
    # 清理过期黑名单
    update_stoploss_blacklist(context)

    stock_to_concept = getattr(g, '_stock_to_concept_map', {})

    # 当前持仓数
    current_hold = len([p for p in context.portfolio.positions.values()
                        if p.total_amount > 0 and not p.security.startswith('511')])
    max_buy = g.stock_num - current_hold
    if max_buy <= 0:
        log.info(f"├─ 持仓已达上限({current_hold}/{g.stock_num})，跳过买入")
        return

    total_cash = context.portfolio.total_value
    portion = total_cash / g.stock_num

    log.info(f"├─ 当前持仓{current_hold}只 | 可买{max_buy}只 | 每份{portion:.0f}元")

    # 为每个概念选出候选股中偏离度最低的1只（需在 stock_to_concept 中）
    concept_best = {}
    for cname in g.fixed_concepts:
        best_code = None
        best_dev = float('inf')
        for code, concepts in stock_to_concept.items():
            if cname in concepts and code in candidate_list:
                dev = deviation_map.get(code, float('inf'))
                # 跳过止损黑名单
                if is_in_stoploss_blacklist(code):
                    continue
                # 跳过当日已卖出的
                if code in g.not_buy_again:
                    continue
                if dev < best_dev and dev < 1.0:
                    best_dev = dev
                    best_code = code
        if best_code is not None:
            concept_best[cname] = (best_code, best_dev)

    if not concept_best:
        log.info("│  ⚠ 无符合条件的候选股（均已在持仓或偏离过高或止损黑名单）")
        return

    # 按偏离度升序排列，取前 max_buy 个
    sorted_concepts = sorted(concept_best.items(), key=lambda x: x[1][1])
    log.info(f"├─ 各概念最佳候选（按偏离度排列）:")
    for cname, (code, dev) in sorted_concepts:
        current_data = get_current_data()
        name = current_data[code].name
        blocked = '🚫止损黑名单' if is_in_stoploss_blacklist(code) else ''
        log.info(f"│    {cname}: {code}({name}) 偏离度{dev:.3f} {blocked}")

    total_bought = 0
    for cname, (code, dev) in sorted_concepts:
        if total_bought >= max_buy:
            break
        current_data = get_current_data()
        name = current_data[code].name

        if is_in_stoploss_blacklist(code):
            log.info(f"│  ⚠ 跳过 {code}({name}) [{cname}] 止损黑名单中")
            continue
        if code in g.bought_today:
            log.info(f"│  ⚠ 跳过 {code}({name}) [{cname}] 已为其他概念买入")
            continue
        if code in context.portfolio.positions and context.portfolio.positions[code].total_amount > 0:
            log.info(f"│  ⚠ 跳过 {code}({name}) [{cname}] 已在持仓")
            continue
        if current_data[code].is_st or current_data[code].paused or current_data[code].last_price >= current_data[code].high_limit:
            log.info(f"│  ⚠ 跳过 {code}({name}) [{cname}] ST/停牌/涨停")
            continue

        if open_position(code, portion):
            log.info(f"│  🟢 买入 {code}({name}) [{cname}] {portion:.0f}元 偏离度{dev:.3f}")
            g.bought_today.append(code)
            total_bought += 1

    log.info(f"└─ 实际买入{total_bought}只")


# ============================================================
#  日内检查（涨停打开、放量、止盈止损）
# ============================================================

def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list:
        for stock in g.yesterday_HL_list:
            if context.portfolio.positions[stock].closeable_amount > -100:
                current_data = get_current_data()
                stock_name = current_data[stock].name
                if current_data[stock].paused:
                    log.info(f"│  {stock}({stock_name}) [停牌] 跳过卖出")
                    continue
                if current_data[stock].last_price > current_data[stock].low_limit:
                    cd = get_price(stock, end_date=now_time, frequency='1m',
                                   fields=['close', 'high_limit'], skip_paused=False,
                                   fq='pre', count=1, panel=False, fill_paused=True)
                    if cd.iloc[0, 0] < cd.iloc[0, 1]:
                        log.info(f"│  🔴 卖出 {stock}({stock_name}) [涨停打开]")
                        close_position(context.portfolio.positions[stock])
                        g.not_buy_again.append(stock)
                        if g.reason_to_sell != 'stoploss':
                            g.reason_to_sell = 'limitup'
                    else:
                        log.info(f"│  🟢 持有 {stock}({stock_name}) [涨停中]")
                else:
                    log.info(f"│  {stock}({stock_name}) [跌停] 跳过卖出")


def check_remain_amount(context):
    if g.reason_to_sell == 'limitup':
        target_list = getattr(g, 'target_list', [])
        deviation_map = getattr(g, '_deviation_map', {})
        if target_list and deviation_map:
            log.info(f"▶ 固定概念补仓：现金{context.portfolio.cash:.2f}元")
            buy_fixed_concept(context, target_list, deviation_map)
        else:
            log.info("├─ 候选池为空，跳过补仓")
        g.reason_to_sell = ''
    else:
        log.info(f"│  有余额({context.portfolio.cash:.2f}元)，止盈止损后余额，下周再交易")
        g.reason_to_sell = ''


def trade_sell(context):
    if g.no_trading_today_signal is False:
        check_limit_up(context)
        huanshou(context)


def trade_buy(context):
    if g.no_trading_today_signal is False:
        check_remain_amount(context)


def sell_stocks(context):
    current_data = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        if current_data[stock].is_st:
            stock_name = current_data[stock].name
            log.info(f"▶ ST清除: {stock}({stock_name}) [强制卖出]")
            if current_data[stock].last_price > current_data[stock].low_limit and not current_data[stock].paused:
                order_target_value(stock, 0)
                g.not_buy_again.append(stock)
            else:
                log.info(f"├─ {stock} 跌停或停牌，跳过卖出")

    if g.run_stoploss is False:
        return
    log.info("▶ 止盈止损")
    if g.stoploss_strategy == 3:
        stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date,
                             frequency='daily', fields=['close', 'open'], count=1, panel=False)
        down_ratio = (stock_df['close'] / stock_df['open']).mean()
        if down_ratio <= g.stoploss_market:
            g.reason_to_sell = 'stoploss'
            log.info(f"│  🌪 大盘惨跌!平均降幅{1-down_ratio:.2%},清仓!")
            current_data = get_current_data()
            for stock in context.portfolio.positions.keys():
                if current_data[stock].paused:
                    continue
                if current_data[stock].last_price > current_data[stock].low_limit:
                    order_target_value(stock, 0)
                    g.not_buy_again.append(stock)
        else:
            triggered = False
            current_data = get_current_data()
            for stock in context.portfolio.positions.keys():
                if current_data[stock].paused:
                    continue
                if current_data[stock].last_price > current_data[stock].low_limit:
                    pos = context.portfolio.positions[stock]
                    stock_name = current_data[stock].name
                    profit_pct = (pos.price / pos.avg_cost - 1) * 100
                    if pos.price >= pos.avg_cost * 2:
                        order_target_value(stock, 0)
                        log.info(f"│  🟢 卖出 {stock}({stock_name}) [止盈] +{profit_pct:.1f}%")
                        g.not_buy_again.append(stock)
                        triggered = True
                    elif pos.price < pos.avg_cost * g.stoploss_limit:
                        order_target_value(stock, 0)
                        log.info(f"│  🔴 卖出 {stock}({stock_name}) [止损] {profit_pct:.1f}%")
                        g.not_buy_again.append(stock)
                        # 记录止损黑名单
                        if not hasattr(g, 'stoploss_blacklist'):
                            g.stoploss_blacklist = {}
                        g.stoploss_blacklist[stock] = context.previous_date.strftime('%Y-%m-%d')
                        log.info(f"│  📝 加入止损黑名单: {stock}({stock_name}) 20个交易日内不买入")
                        g.reason_to_sell = 'stoploss'
                        triggered = True
            if not triggered:
                log.info("│  无需操作")
        log.info("└─ 止盈止损完成")


# ============================================================
#  过滤器
# ============================================================

def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].paused]


def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].is_st
            and 'ST' not in current_data[s].name
            and '*' not in current_data[s].name
            and '退' not in current_data[s].name]


def filter_kcbj_stock(stock_list):
    for s in stock_list[:]:
        if s[0] == '4' or s[0] == '8' or s[:2] == '68':
            stock_list.remove(s)
    return stock_list


def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [s for s in stock_list if s in context.portfolio.positions.keys()
            or last_prices[s][-1] < current_data[s].high_limit]


def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [s for s in stock_list if s in context.portfolio.positions.keys()
            or last_prices[s][-1] > current_data[s].low_limit]


def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [s for s in stock_list
            if not yesterday - get_security_info(s).start_date < dt.timedelta(days=375)]


def filter_highprice_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    return [s for s in stock_list if s in context.portfolio.positions.keys()
            or last_prices[s][-1] <= g.up_price]


def filter_not_buy_again(stock_list):
    return [s for s in stock_list if s not in g.not_buy_again]


def filter_stoploss(stock_list):
    """过滤掉止损黑名单中的股票"""
    if not hasattr(g, 'stoploss_blacklist'):
        return stock_list
    return [s for s in stock_list if s not in g.stoploss_blacklist]


# ============================================================
#  换手率检查
# ============================================================

def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        end_date = context.previous_date
        df_volume = get_price(stock, end_date=end_date, frequency='daily', fields=['volume'], count=20)
        df_cap = get_valuation(stock, end_date=end_date, fields=['circulating_cap'], count=1)
        cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if cap == 0:
            return 0.0
        return (df_volume['volume'] / (cap * 10000)).mean()
    else:
        date_now = context.current_dt
        df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now,
                           frequency='1m', fields=['volume'], skip_paused=False,
                           fq='pre', panel=True, fill_paused=False)
        volume = df_vol['volume'].sum()
        date_pre = context.previous_date
        df_cap = get_valuation(stock, end_date=date_pre, fields=['circulating_cap'], count=1)
        cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if cap == 0:
            return 0.0
        return volume / (cap * 10000)


def huanshou(context):
    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in context.portfolio.positions:
        if current_data[stock].paused:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        if current_data[stock].last_price <= current_data[stock].low_limit:
            continue
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0:
            continue
        ratio = rt / avg
        action = ''
        if avg < shrink:
            action = '缩量'
        elif rt > expand and ratio > 2:
            action = '放量'
        if action:
            stock_name = current_data[stock].name
            close_position(context.portfolio.positions[stock])
            log.info(f"│  🔴 卖出 {stock}({stock_name}) [{action}] 换手{rt:.2%}→均{avg:.2%} {ratio:.1f}x")
            g.not_buy_again.append(stock)
            if g.reason_to_sell != 'stoploss':
                g.reason_to_sell = 'limitup'


# ============================================================
#  下单辅助
# ============================================================

def order_target_value_(security, value):
    return order_target_value(security, value)


def open_position(security, value):
    order = order_target_value_(security, value)
    return order is not None and order.filled > 0


def close_position(position):
    order = order_target_value_(position.security, 0)
    return order is not None and order.status == OrderStatus.held and order.filled == order.amount


def buy_security(context, target_list, cash=0, buy_number=0):
    if cash == 0:
        cash = context.portfolio.cash
    if buy_number == 0:
        buy_number = len(target_list)
    if buy_number == 0:
        return
    value_per = cash / buy_number
    bought_num = 0
    log.info(f"│  买入: 目标{buy_number}只 | 每只约{value_per:.0f}元")
    for stock in target_list:
        current_data = get_current_data()
        if current_data[stock].is_st:
            continue
        if current_data[stock].paused:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit:
            continue
        if is_in_stoploss_blacklist(stock):
            log.info(f"│  ⚠ 跳过 {stock}({current_data[stock].name}) 止损黑名单中")
            continue
        if (stock not in context.portfolio.positions or context.portfolio.positions[stock].total_amount == 0) and bought_num < buy_number:
            if open_position(stock, value_per):
                log.info(f"│  🟢 买入 {stock}({current_data[stock].name}) {value_per:.0f}元")
                g.not_buy_again.append(stock)
                bought_num += 1
    log.info(f"└─ 实际买入{bought_num}只")


# ============================================================
#  空仓期管理
# ============================================================

def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    if g.pass_april:
        return ('04-01' <= today <= '04-30') or ('01-01' <= today <= '01-31')
    return False


def close_account(context):
    if g.no_trading_today_signal and len(g.hold_list) > 0 and not g.no_trading_hold_signal:
        log.info("")
        log.info("▶ 空仓期清仓")
        current_data = get_current_data()
        sell_count = 0
        for stock in g.hold_list:
            if current_data[stock].paused:
                log.info(f"│  {stock} 停牌,跳过")
                continue
            if current_data[stock].last_price > current_data[stock].low_limit:
                if close_position(context.portfolio.positions[stock]):
                    log.info(f"│  🔴 卖出 {stock}")
                    sell_count += 1
                else:
                    log.info(f"│  ❌ 卖出 {stock} 错误!")
            else:
                log.info(f"│  {stock} 跌停,跳过")
        log.info(f"└─ 卖出{sell_count}只")
        buy_security(context, g.no_trading_buy)
        g.no_trading_hold_signal = True


def close_no_trading_hold(context):
    if g.no_trading_hold_signal:
        log.info("")
        log.info("▶ 关闭空仓期持仓")
        current_data = get_current_data()
        for stock in g.hold_list:
            if current_data[stock].paused:
                log.info(f"│  {stock} 停牌,跳过")
                continue
            if current_data[stock].last_price > current_data[stock].low_limit:
                close_position(context.portfolio.positions[stock])
                log.info(f"│  🔴 卖出 {stock}")
            else:
                log.info(f"│  {stock} 跌停,跳过")
        g.no_trading_hold_signal = False


# ============================================================
#  收盘打印持仓
# ============================================================

def print_position_info(context):
    total_value = context.portfolio.total_value
    date_str = context.current_dt.strftime('%Y-%m-%d')
    log.info("")
    log.info(f"{'='*60}")
    log.info(f"📊 {date_str} 持仓报告 | 总资产 {total_value:.0f}")
    log.info(f"{'='*60}")

    positions = context.portfolio.positions
    if not positions:
        log.info("  空仓")
        log.info(f"{'='*60}")
        return

    total_pnl = 0
    for stock, pos in sorted(positions.items()):
        if stock.startswith('511'):
            continue
        current_data = get_current_data()
        stock_name = current_data[stock].name
        price = pos.price
        avg_cost = pos.avg_cost
        amount = pos.total_amount
        pnl = (price - avg_cost) * amount
        pnl_pct = (price / avg_cost - 1) * 100
        total_pnl += pnl
        flag = '🟢' if pnl_pct >= 0 else '🔴'
        log.info(f"  {flag} {stock}({stock_name}) {amount}股 | 成本{avg_cost:.2f} | 现价{price:.2f} | {pnl_pct:+.2f}%")

    log.info(f"{'─'*60}")
    log.info(f"  总浮动盈亏: {total_pnl:+.0f} ({total_pnl/total_value*100:+.2f}%)")
    log.info(f"{'='*60}")
