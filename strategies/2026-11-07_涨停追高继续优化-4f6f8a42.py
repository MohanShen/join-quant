# Clone from JoinQuant
# postId: 4f6f8a42601e6f50c427c979c925904a
# backtestId: 020d8a9bfec2459fd4bcdb0398ec0ae6
# title: 涨停追高继续优化

# ============ 清风 🎭 变体：A4_市值下限70to50亿 2026-10-01 ============
# 相对『前视修复版』的改动：总市值下限 70 → 50 亿（-29%）
# ============ 清风 🎭 前视修复版 2026-09-30 ============
# 本版【只修正确性，一个参数值都不动】，目的是量出"去掉前视后还剩多少"。
#
# 已修（3 处）：
#   ① 【前视】ST 过滤原用 current_data.is_st + current_data.name —— 两者都是
#      「今天的值」，不随回测日期回溯。实证：2020-01-03 日志里出现「*ST搜特」「数知退」，
#      而这两只是 2023 年才退市 ⇒ 回测在 2020 年就用上了未来的退市信息（乐观偏差）。
#      改为 get_extras('is_st', ..., 昨日) 历史口径；名称类判断（ST/*/退）全部删除
#      （名称无法历史化，留着就是前视）。
#   ② 【正确性】买入"够不够 1 手"原判据用「全部可用现金」比（L154），应用「单只预算」比
#      ⇒ 高价股判"够"但 order_value 被削到不足 100 股 → 拒单、现金趴账。已改为单只预算判据。
#   ③ 【注释】turnover_max=25.0 注释写 20%；max_buy_num=3 注释写 Top2。**只改注释，值不动**。
#
# 未动（刻意保留，否则不可比）：
#   · 回测频率=分钟（11:25/14:50 靠 current_data.last_price，必须分钟频率）
#   · 区间 / 初始资金 / 滑点 PriceRelatedSlippage(0.001) / 全部门槛参数值 / 评分权重
#   · 评分权重"来自本次回测日志表现"（L475 注释自证）属过拟合指纹，但改它就是我在做参数挖掘
#
# 已知残留（无法修，已在报告说明）：
#   · 「退」字名称过滤被移除后，可能漏掉个别退市整理期个股（无历史名称接口）
#   · 单笔规模随复利膨胀（末笔近 1 亿），容量问题属策略本身，非代码可修
# =======================================================

import numpy as np
import math
import pandas as pd
import json
from jqdata import *
from jqfactor import *
from jqlib.technical_analysis import *
from datetime import datetime, date, timedelta


class _LegG(object):
    pass


# ==================== 独立账户下单包装 ====================
def l0_ord_order(*a, **k):
    k.pop('pindex', None)
    return order(*a, **k)

def l0_ord_order_value(*a, **k):
    k.pop('pindex', None)
    return order_value(*a, **k)

def l0_ord_order_target_value(*a, **k):
    k.pop('pindex', None)
    return order_target_value(*a, **k)

def l0_ord_order_target(*a, **k):
    k.pop('pindex', None)
    return order_target(*a, **k)


# ==================== 独立策略初始化 ====================
def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.001), type="stock")
    set_benchmark("510300.XSHG")
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')

    g.l0 = _LegG()

    # 保留原股票腿初始化与调度
    l0_initialize(context)
    l0_after_code_changed(context)

    run_daily(l0_standalone_recon, time='15:20')
    log.info("【86TL拆分-A】78A1首板高开股票腿独立版启动")


def after_trading_end(context):
    try:
        l0_after_trading_end(context)
    except Exception as e:
        log.warning("[78A1独立版] after_trading_end 异常: %s" % e)


def l0_standalone_recon(context):
    """独立账户收盘校验：只读，不影响信号。"""
    try:
        p = context.portfolio
        n = len([1 for _s, pos in p.positions.items() if pos.total_amount > 0])
        log.info("【78A1收盘校验】总值%.0f 现金%.0f 持仓%d只"
                 % (p.total_value, p.available_cash, n))
    except Exception as e:
        log.warning("【78A1收盘校验】异常: %s" % e)


# ================== 腿 0 : 78A1《首板高开质量精选V1.1》(post/80233) ==================
# ================================================================
def l0_initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(PriceRelatedSlippage(0.001), type='stock')  # 任务78统一口径
    log.set_level('system', 'error')





# ====================== 初始化 ======================

def l0_after_code_changed(context):
    g.l0.n_days_limit_up_list = []

    # ===== 原有：昨日换手率 + 首板质量硬条件 =====
    g.l0.turnover_min = 3                 # 昨日换手率下限 3%
    g.l0.turnover_max = 25.0                 # 昨日换手率上限 25%（原注释误写 20%，2026-09-30 订正；值未改）
    g.l0.first_limit_latest_time = '14:30'   # 首次封板最晚时间
    g.l0.max_open_board_times = 3            # 最多允许炸板次数
    g.l0.final_reseal_latest_time = '14:45'  # 最后回封最晚时间

    # ===== 新增：通过硬条件后再评分，最多买Top3（原注释误写 Top2，2026-09-30 订正；值未改）=====
    g.l0.max_buy_num = 3
    # 诊断计数（前视修复版新增，只统计不改行为）
    g.l0.diag_st_hit = 0
    g.l0.diag_hand_skip = 0

    # ===== 新增：固定硬止损 -5% =====
    g.l0.hard_stop_ratio = 0.95

    pass  # [86合并] 原版 unschedule_all() 会清掉其它腿调度 -> 合并版禁用

    # 09:26 选股并买入
    run_daily(l0_buy, '09:26')

    # 【前视修复版新增】一次性接口自检：确认历史 ST 接口可用与返回结构。
    # 若不可用，l0_filter_st_history 会走 warning 分支（等于没过滤）——必须能从日志看出来。
    try:
        _t = get_extras('is_st', ['600000.XSHG', '000001.XSHE'],
                        start_date=context.previous_date,
                        end_date=context.previous_date, df=True)
        _cols = list(_t.columns)[:3] if (_t is not None and hasattr(_t, 'columns')) else None
        _row = _t.iloc[-1].to_dict() if (_t is not None and not _t.empty) else None
        log.info('【接口自检】get_extras(is_st) shape=%s cols=%s row=%s'
                 % (getattr(_t, 'shape', None), _cols, _row))
    except Exception as e:
        log.info('【接口自检】get_extras(is_st) 不可用: %s' % e)

    # 新增：09:35先检查昨日及更早持仓的固定止损
    run_daily(l0_hard_stop, time='09:35', reference_security='000300.XSHG')

    # 原卖出时间保持不变，同时内部也会先检查-5%硬止损
    run_daily(l0_sell, time='11:25', reference_security='000300.XSHG')
    run_daily(l0_sell, time='14:50', reference_security='000300.XSHG')


def l0_after_trading_end(context):
    print('———————————————————————————————————')


# ====================== 基础股票池 ======================

def l0_set_stockpool(context):
    yesterday = context.previous_date
    initial_list = get_all_securities('stock', yesterday).index.tolist()
    return initial_list


# ====================== 交易函数 ======================

def l0_buy(context):
    current_data = get_current_data()
    qualified_stocks = l0_get_stock_list(context)

    if not qualified_stocks:
        return

    # 【修复 2026-09-30】原判据 L154 用「全部可用现金 / last_price > 100」判够不够 1 手，
    # 应以「单只预算」判。否则高价股被判"够"、order_value 却被削到不足 100 股 → 拒单、现金趴账。
    budget = context.portfolio.available_cash / len(qualified_stocks)

    for s in qualified_stocks:
        if current_data[s].paused:
            continue

        last_price = current_data[s].last_price
        if last_price is None or last_price <= 0:
            continue

        # 单只预算不足 1 手 ⇒ 跳过（并留痕，便于统计实盘偏离）
        if budget / last_price < 100:
            log.info('【一手门槛跳过】%s %s 单只预算%.0f 不足1手(价%.2f)'
                     % (s, get_security_info(s).display_name, budget, last_price))
            continue

        l0_ord_order_value(
            s,
            budget,
            MarketOrderStyle(current_data[s].day_open)
        )
        print('买入' + s)


def l0_hard_stop(context):
    """
    新增固定硬止损：
    持仓浮亏达到或超过5%，且可卖、未跌停时立即清仓。

    09:35单独检查一次；
    11:25和14:50在sell()内部还会再次检查。
    """
    current_data = get_current_data()

    for s in list(context.portfolio.positions):
        position = context.portfolio.positions[s]

        if position.closeable_amount == 0:
            continue

        if current_data[s].paused:
            continue

        last_price = current_data[s].last_price
        avg_cost = position.avg_cost

        if (
            last_price is None
            or last_price <= 0
            or avg_cost is None
            or avg_cost <= 0
        ):
            continue

        ret_ratio = last_price / avg_cost

        if ret_ratio <= g.l0.hard_stop_ratio:
            ret = 100 * (last_price / avg_cost - 1)

            # 跌停时即使发单也大概率无法成交，日志单独提示
            if last_price <= current_data[s].low_limit:
                print(
                    '硬止损触发但跌停无法卖出 '
                    + get_security_info(s).display_name
                    + s
                    + ' 收益率:{:.2f}%'.format(ret)
                )
                continue

            l0_ord_order_target_value(s, 0)
            print(
                '硬止损卖出 '
                + get_security_info(s).display_name
                + s
                + ' 收益率:{:.2f}%'.format(ret)
            )


def l0_sell(context):
    current_data = get_current_data()

    for s in list(context.portfolio.positions):
        position = context.portfolio.positions[s]

        if position.closeable_amount == 0:
            continue

        if current_data[s].paused:
            continue

        last_price = current_data[s].last_price
        avg_cost = position.avg_cost

        if (
            last_price is None
            or last_price <= 0
            or avg_cost is None
            or avg_cost <= 0
        ):
            continue

        # --------------------------------------------------
        # 第一优先级：新增 -5% 固定硬止损
        # --------------------------------------------------
        if last_price <= avg_cost * g.l0.hard_stop_ratio:
            ret = 100 * (last_price / avg_cost - 1)

            if last_price <= current_data[s].low_limit:
                print(
                    '硬止损触发但跌停无法卖出 '
                    + get_security_info(s).display_name
                    + s
                    + ' 收益率:{:.2f}%'.format(ret)
                )
                continue

            l0_ord_order_target_value(s, 0)
            print(
                '硬止损卖出 '
                + get_security_info(s).display_name
                + s
                + ' 收益率:{:.2f}%'.format(ret)
            )
            continue

        # --------------------------------------------------
        # 以下保持原来的止盈 / MA5逻辑
        # --------------------------------------------------
        close_data = attribute_history(
            s,
            4,
            '1d',
            ['close']
        )

        if close_data is None or len(close_data) < 4:
            continue

        M4 = close_data['close'].mean()
        MA5 = (M4 * 4 + last_price) / 5

        # 原止盈：当前盈利、未涨停则卖出
        if (
            last_price < current_data[s].high_limit
            and last_price > avg_cost
        ):
            l0_ord_order_target_value(s, 0)
            ret = 100 * (last_price / avg_cost - 1)
            print(
                '止盈卖出 '
                + get_security_info(s).display_name
                + s
                + ' 收益率:{:.2f}%'.format(ret)
            )
            continue

        # 原止损：跌破5日线
        if last_price < MA5:
            # 跌停无法正常卖出时仅记录
            if last_price <= current_data[s].low_limit:
                ret = 100 * (last_price / avg_cost - 1)
                print(
                    'MA5止损触发但跌停无法卖出 '
                    + get_security_info(s).display_name
                    + s
                    + ' 收益率:{:.2f}%'.format(ret)
                )
                continue

            l0_ord_order_target_value(s, 0)
            ret = 100 * (last_price / avg_cost - 1)
            print(
                '止损卖出 '
                + get_security_info(s).display_name
                + s
                + ' 收益率:{:.2f}%'.format(ret)
            )


# ====================== 首板质量 ======================

def l0_check_yesterday_first_board_quality(stock, context):
    """
    昨日首板质量硬验证：
    1）首次封板时间 <= 14:30
    2）炸板次数 <= 3（参数 g.l0.max_open_board_times；原 docstring 误写 2，2026-09-30 订正）
    3）最后一次回封时间 <= 14:45
    4）尾盘最后有效分钟仍然封住涨停

    仅使用昨日完整1分钟行情。
    """
    yesterday = context.previous_date

    start_dt = datetime.combine(
        yesterday,
        datetime.strptime('09:30', '%H:%M').time()
    )
    end_dt = datetime.combine(
        yesterday,
        datetime.strptime('15:00', '%H:%M').time()
    )

    try:
        df = get_price(
            stock,
            start_date=start_dt,
            end_date=end_dt,
            frequency='1m',
            fields=['close', 'high_limit'],
            skip_paused=False,
            fq='none',
            panel=False,
            fill_paused=False
        )
    except Exception as e:
        return False, {
            'reason': '分钟数据异常:{}'.format(e),
            'first_limit_time': None,
            'open_board_times': None,
            'final_reseal_time': None
        }

    if df is None or df.empty:
        return False, {
            'reason': '无昨日分钟数据',
            'first_limit_time': None,
            'open_board_times': None,
            'final_reseal_time': None
        }

    df = df.dropna(subset=['close', 'high_limit'])

    if df.empty:
        return False, {
            'reason': '昨日分钟数据无效',
            'first_limit_time': None,
            'open_board_times': None,
            'final_reseal_time': None
        }

    # 允许极小浮点误差
    is_limit = df['close'] >= df['high_limit'] * 0.9999

    if not is_limit.any():
        return False, {
            'reason': '昨日分钟级无封板',
            'first_limit_time': None,
            'open_board_times': 0,
            'final_reseal_time': None
        }

    # 首次分钟收盘封板
    first_limit_dt = df.index[is_limit][0]

    # 聚宽旧版pandas兼容写法
    prev_limit = is_limit.shift(1).fillna(False)
    prev_limit = prev_limit.astype(bool)

    # 上一分钟封板，本分钟不再封板 => 一次炸板
    open_board_mask = prev_limit & (~is_limit)
    open_board_times = int(open_board_mask.sum())

    # 非封板 -> 封板的最后一次转换 => 最后回封
    seal_start_mask = is_limit & (~prev_limit)
    seal_start_index = df.index[seal_start_mask]
    final_reseal_dt = seal_start_index[-1]

    final_is_limit = bool(is_limit.iloc[-1])

    first_limit_time = first_limit_dt.strftime('%H:%M')
    final_reseal_time = final_reseal_dt.strftime('%H:%M')

    first_limit_ok = first_limit_time <= g.l0.first_limit_latest_time
    open_board_ok = open_board_times <= g.l0.max_open_board_times
    final_reseal_ok = final_reseal_time <= g.l0.final_reseal_latest_time
    final_seal_ok = final_is_limit

    passed = (
        first_limit_ok
        and open_board_ok
        and final_reseal_ok
        and final_seal_ok
    )

    reasons = []

    if not first_limit_ok:
        reasons.append(
            '首封{}晚于{}'.format(
                first_limit_time,
                g.l0.first_limit_latest_time
            )
        )

    if not open_board_ok:
        reasons.append(
            '炸板{}次>允许{}次'.format(
                open_board_times,
                g.l0.max_open_board_times
            )
        )

    if not final_reseal_ok:
        reasons.append(
            '最后回封{}晚于{}'.format(
                final_reseal_time,
                g.l0.final_reseal_latest_time
            )
        )

    if not final_seal_ok:
        reasons.append('尾盘未封住涨停')

    return passed, {
        'reason': '通过' if passed else '；'.join(reasons),
        'first_limit_time': first_limit_time,
        'open_board_times': open_board_times,
        'final_reseal_time': final_reseal_time
    }


# ====================== 质量评分 ======================

def l0_time_to_minutes(time_str):
    hour, minute = time_str.split(':')
    return int(hour) * 60 + int(minute)


def l0_calculate_quality_score(
    turnover_ratio,
    board_info,
    auction_volume_ratio
):
    """
    通过全部硬条件后再做质量评分。

    评分依据来自本次回测日志表现：
    1）换手率8%～15%给予最高分；
    2）炸板越少越好，但0/1/2次均保留；
    3）首封越早加分越高；
    4）最后回封越早加分越高；
    5）竞价量比只做小幅加分，不作为新的硬门槛。

    满分100分。
    """
    score = 0.0
    detail = {}

    # --------------------------------------------------
    # 1. 换手率：30分
    # 日志中 8%～15% 的样本表现最好，因此给予最高权重。
    # --------------------------------------------------
    if 8.0 <= turnover_ratio <= 15.0:
        turnover_score = 30
    elif 5.0 <= turnover_ratio < 8.0:
        turnover_score = 20
    elif 15.0 < turnover_ratio <= 20.0:
        turnover_score = 18
    else:  # 3%～5%
        turnover_score = 10

    score += turnover_score
    detail['turnover_score'] = turnover_score

    # --------------------------------------------------
    # 2. 炸板次数：25分
    # --------------------------------------------------
    open_board_times = board_info['open_board_times']

    if open_board_times == 0:
        board_score = 25
    elif open_board_times == 1:
        board_score = 18
    else:  # 2次
        board_score = 10

    score += board_score
    detail['board_score'] = board_score

    # --------------------------------------------------
    # 3. 首次封板时间：20分
    # --------------------------------------------------
    first_minutes = l0_time_to_minutes(board_info['first_limit_time'])

    if first_minutes <= l0_time_to_minutes('10:00'):
        first_score = 20
    elif first_minutes <= l0_time_to_minutes('11:30'):
        first_score = 15
    elif first_minutes <= l0_time_to_minutes('13:30'):
        first_score = 8
    else:
        first_score = 3

    score += first_score
    detail['first_score'] = first_score

    # --------------------------------------------------
    # 4. 最后回封时间：15分
    # --------------------------------------------------
    reseal_minutes = l0_time_to_minutes(board_info['final_reseal_time'])

    if reseal_minutes <= l0_time_to_minutes('11:30'):
        reseal_score = 15
    elif reseal_minutes <= l0_time_to_minutes('13:30'):
        reseal_score = 10
    elif reseal_minutes <= l0_time_to_minutes('14:15'):
        reseal_score = 5
    else:
        reseal_score = 0

    score += reseal_score
    detail['reseal_score'] = reseal_score

    # --------------------------------------------------
    # 5. 竞价量比：10分
    # 原硬门槛仍然是 >=3%，这里仅用于排序。
    # --------------------------------------------------
    if 0.04 <= auction_volume_ratio <= 0.08:
        auction_score = 10
    elif 0.03 <= auction_volume_ratio < 0.04:
        auction_score = 6
    elif 0.08 < auction_volume_ratio <= 0.12:
        auction_score = 8
    else:
        auction_score = 5

    score += auction_score
    detail['auction_score'] = auction_score

    return score, detail


# ====================== 选股 ======================

def l0_get_stock_list(context):
    target_list = l0_prepare_stock_list(context)

    # 不再“通过就全部买”，而是保存通过票及其评分
    scored_candidates = []

    date_now = context.current_dt.strftime("%Y-%m-%d")
    start = date_now + ' 09:15:00'
    end = date_now + ' 09:26:00'

    for s in target_list:

        # --------------------------------------------------
        # 条件一：原均价 / 成交额
        # --------------------------------------------------
        prev_day_data = attribute_history(
            s,
            1,
            '1d',
            fields=['close', 'volume', 'money'],
            skip_paused=True
        )

        if prev_day_data is None or prev_day_data.empty:
            continue

        if (
            prev_day_data['volume'][0] is None
            or prev_day_data['volume'][0] <= 0
            or prev_day_data['close'][0] is None
            or prev_day_data['close'][0] <= 0
        ):
            continue

        avg_price_increase_value = (
            prev_day_data['money'][0]
            / prev_day_data['volume'][0]
            / prev_day_data['close'][0]
            * 1.1
            - 1
        )

        if (
            avg_price_increase_value < 0.07
            or prev_day_data['money'][0] < 5.5e8
            or prev_day_data['money'][0] > 20e8
        ):
            continue

        # --------------------------------------------------
        # 原市值 + 换手率
        # --------------------------------------------------
        turnover_ratio_data = get_valuation(
            s,
            start_date=context.previous_date,
            end_date=context.previous_date,
            fields=[
                'turnover_ratio',
                'market_cap',
                'circulating_market_cap'
            ]
        )

        if turnover_ratio_data.empty:
            continue

        turnover_ratio = turnover_ratio_data['turnover_ratio'][0]

        if (
            pd.isna(turnover_ratio)
            or turnover_ratio < g.l0.turnover_min
            or turnover_ratio > g.l0.turnover_max
        ):
            print(
                '【换手率过滤】{} {} | 昨日换手率:{}'
                .format(
                    s,
                    get_security_info(s).display_name,
                    'None'
                    if pd.isna(turnover_ratio)
                    else '{:.2f}%'.format(turnover_ratio)
                )
            )
            continue

        if (
            turnover_ratio_data['market_cap'][0] < 50
            or turnover_ratio_data['circulating_market_cap'][0] > 520
        ):
            continue

        # --------------------------------------------------
        # 原昨日首板质量硬验证
        # --------------------------------------------------
        board_passed, board_info = l0_check_yesterday_first_board_quality(
            s,
            context
        )

        if not board_passed:
            print(
                '【首板质量过滤】{} {} | {}'
                .format(
                    s,
                    get_security_info(s).display_name,
                    board_info['reason']
                )
            )
            continue

        # --------------------------------------------------
        # 条件二：原竞价量 + 高开
        # --------------------------------------------------
        auction_data = get_call_auction(
            s,
            start_date=start,
            end_date=end,
            fields=['time', 'volume', 'current']
        )

        if auction_data is None or auction_data.empty:
            continue

        if (
            prev_day_data['volume'][-1] is None
            or prev_day_data['volume'][-1] <= 0
        ):
            continue

        auction_volume_ratio = (
            auction_data['volume'][0]
            / prev_day_data['volume'][-1]
        )

        # 原竞价量硬门槛 >=3%
        if auction_volume_ratio < 0.03:
            continue

        current_ratio = (
            auction_data['current'][0]
            / prev_day_data['close'][-1]
        )

        # 原高开范围：0%～6%
        if current_ratio <= 1 or current_ratio >= 1.06:
            continue

        # --------------------------------------------------
        # 条件三：原左压
        # --------------------------------------------------
        hst = attribute_history(
            s,
            101,
            '1d',
            fields=['high', 'volume'],
            skip_paused=True
        )

        if hst is None or len(hst) < 2:
            continue

        prev_high = hst['high'].iloc[-1]

        zyts_0 = next(
            (
                i - 1
                for i, high in enumerate(
                    hst['high'][-3::-1],
                    2
                )
                if high >= prev_high
            ),
            100
        )

        zyts = zyts_0 + 5
        volume_data = hst['volume'][-zyts:]

        if (
            len(volume_data) < 2
            or volume_data.iloc[-1]
            <= volume_data.iloc[:-1].max() * 0.9
        ):
            continue

        # --------------------------------------------------
        # 新增：所有硬条件通过后再评分
        # --------------------------------------------------
        quality_score, score_detail = l0_calculate_quality_score(
            turnover_ratio=turnover_ratio,
            board_info=board_info,
            auction_volume_ratio=auction_volume_ratio
        )

        scored_candidates.append({
            'stock': s,
            'score': quality_score,
            'turnover_ratio': turnover_ratio,
            'first_limit_time': board_info['first_limit_time'],
            'open_board_times': board_info['open_board_times'],
            'final_reseal_time': board_info['final_reseal_time'],
            'auction_volume_ratio': auction_volume_ratio,
            'open_ratio': current_ratio - 1,
            'score_detail': score_detail
        })

        print(
            '【候选评分】{} {} | 总分{:.1f} | 换手{:.2f}% | '
            '首封{} | 炸板{}次 | 回封{} | 竞价量比{:.2f}% | 高开{:.2f}%'
            .format(
                s,
                get_security_info(s).display_name,
                quality_score,
                turnover_ratio,
                board_info['first_limit_time'],
                board_info['open_board_times'],
                board_info['final_reseal_time'],
                auction_volume_ratio * 100,
                (current_ratio - 1) * 100
            )
        )

    # --------------------------------------------------
    # 新增：按质量分排序，只取Top2
    # --------------------------------------------------
    scored_candidates.sort(
        key=lambda x: (
            x['score'],
            x['auction_volume_ratio']
        ),
        reverse=True
    )

    top_candidates = scored_candidates[:g.l0.max_buy_num]
    qualified_stocks = [x['stock'] for x in top_candidates]

    if scored_candidates:
        print('========== 今日候选质量排名 ==========')

        for i, item in enumerate(scored_candidates, 1):
            print(
                '第{}名 {} {} | 分数{:.1f} | 换手{:.2f}% | '
                '首封{} | 炸板{}次 | 回封{} | 竞价量比{:.2f}%'
                .format(
                    i,
                    item['stock'],
                    get_security_info(item['stock']).display_name,
                    item['score'],
                    item['turnover_ratio'],
                    item['first_limit_time'],
                    item['open_board_times'],
                    item['final_reseal_time'],
                    item['auction_volume_ratio'] * 100
                )
            )

    if qualified_stocks:
        print('今日最终选股Top{}：{}'.format(
            g.l0.max_buy_num,
            qualified_stocks
        ))
        print('首板高开：' + str(qualified_stocks))

    return qualified_stocks


# ====================== 每日初始股票池 ======================

def l0_prepare_stock_list(context):
    today = context.current_dt.date()
    yesterday = context.previous_date

    initial_list = l0_set_stockpool(context)
    initial_list = l0_filter_kcbj_stock(initial_list)
    initial_list = l0_filter_st_paused_stock(initial_list, today)
    initial_list = l0_filter_new_stock(initial_list, today)

    # 首次运行，添加前2天的数据
    if not g.l0.n_days_limit_up_list:
        days = get_trade_days(
            end_date=yesterday,
            count=3
        )[:-1]

        for day in days:
            g.l0.n_days_limit_up_list.append(
                l0_get_hl_stock(
                    initial_list,
                    day,
                    1
                )
            )

    # 昨日涨停
    hl_list = l0_get_hl_stock(
        initial_list,
        yesterday,
        1
    )

    g.l0.n_days_limit_up_list.append(hl_list)

    # 前一交易日涨停
    hl1_list = set(
        g.l0.n_days_limit_up_list[-2]
    )

    # 只保留昨日首板：
    # 昨日涨停，并且前一交易日没有涨停
    hl_list = [
        stock
        for stock in hl_list
        if stock not in hl1_list
    ]

    # 【前视修复 2026-09-30】历史 ST 过滤只对首板候选执行（全市场逐日取 is_st 太慢；
    # 三个过滤都是纯谓词、交集不变，故重排不影响结果集）
    hl_list = l0_filter_st_history(hl_list, yesterday)

    g.l0.n_days_limit_up_list.pop(0)

    return hl_list


# ====================== 其它函数 ======================

def l0_get_hl_stock(stock_list, date1, days=1):
    if not stock_list:
        return []

    h_s = get_price(
        stock_list,
        end_date=date1,
        frequency='daily',
        fields=[
            'close',
            'high_limit',
            'paused'
        ],
        count=days,
        panel=False,
        fill_paused=False,
        skip_paused=False
    ).query(
        'close==high_limit and paused==0'
    ).groupby('code').size()

    return h_s.index.tolist()


# ====================== 过滤函数 ======================

def l0_filter_new_stock(initial_list, date, days=50):
    return [
        stock
        for stock in initial_list
        if get_security_info(stock).start_date
        < date - timedelta(days=days)
    ]


def l0_filter_st_paused_stock(initial_list, date):
    """【前视修复 2026-09-30】原版只剔 paused（无前视，保留）；ST 判断已拆到
    l0_filter_st_history()，只对「昨日首板」候选执行历史 ST 查询（省掉全市场逐日取数）。"""
    current_data = get_current_data()
    result = []
    for stock in initial_list:
        try:
            data = current_data[stock]
        except Exception:
            continue
        if data.paused:
            continue
        result.append(stock)
    return result


def l0_filter_st_history(candidates, st_date):
    """【前视修复 2026-09-30 核心】
    原版用 current_data.is_st 与 current_data.name 判 ST —— 两者都是「今天的值」，
    不随回测日期回溯 ⇒ 回测在 2020 年就用上了 2023 年才发生的退市/ST 信息（乐观偏差）。
    实证：原版 2020-01-03 日志打出「*ST搜特」「数知退」（均 2023 年才退市）。

    本版：改用 get_extras('is_st', ..., 指定日, 指定日) 的**历史当日** ST 标记。
    名称类判断（'ST' / '*' / '退'）全部删除 —— 名称字段无历史接口，留着就是前视。
    st_date 取「昨日」（= context.previous_date）：绝对无前视，且与"昨日首板"语义一致。
    """
    if not candidates:
        return candidates
    st_set = set()
    try:
        df = get_extras('is_st', list(candidates),
                        start_date=st_date, end_date=st_date, df=True)
        if df is not None and not df.empty:
            row = df.iloc[-1]
            st_set = {c for c in row.index if bool(row[c])}
    except Exception as e:
        log.warning('【前视修复】get_extras(is_st) 取数失败，本期不做ST过滤: %s' % e)

    kept, hit = [], []
    for c in candidates:
        if c in st_set:
            hit.append(c)
        else:
            kept.append(c)
    log.info('【前视修复·历史ST】候选%d只 → 剔除当时ST %d只 → 剩%d只'
             % (len(candidates), len(hit), len(kept)))
    if hit:
        log.info('【前视修复·历史ST】剔除明细: %s' % ','.join(hit[:20]))
    return kept


def l0_filter_kcbj_stock(initial_list):
    return [
        stock
        for stock in initial_list
        if stock[0] != '4'
        and stock[0] != '8'
        and stock[:2] != '68'
    ]  # 创业板仍按原策略保留


### end ###
