# Clone from JoinQuant
# postId: 3a0d2c5e148fd7551c69d69f10cbf5aa
# backtestId: 03099cf1e27b5d8d288a41420d937a54
# title: 小市值初筛 + 反转打分 + 市场状态门控 + 风控卖出

# 克隆自聚宽文章：https://www.joinquant.com/post/78471
# 标题：小市值不等于盲目追小：20日乖离择时＋涨停保护的四股轮动策略
# 作者：让子弹飞一会fd

import datetime
import json
import socket
import time

import numpy as np
import pandas as pd
from jqdata import *


# ============ MyTT.py原版MACD算法 ============
def RD(N, D=3):
    """四舍五入取3位小数"""
    return np.round(N, D)


def mytt_ema(S, N):
    """
    完全按照MyTT.py原版EMA实现
    使用pandas.ewm()确保与原版完全一致
    """
    return pd.Series(S).ewm(span=N, adjust=False).mean().values


def mytt_macd(CLOSE, SHORT=12, LONG=26, M=9):
    """
    完全按照MyTT.py原版MACD实现
    DIF = EMA(CLOSE,SHORT) - EMA(CLOSE,LONG)
    DEA = EMA(DIF,M)
    MACD = (DIF-DEA)*2
    """
    if len(CLOSE) < max(SHORT, LONG, M):
        # 数据不足时返回空值
        return [], [], []

    DIF = mytt_ema(CLOSE, SHORT) - mytt_ema(CLOSE, LONG)
    DEA = mytt_ema(DIF, M)
    MACD = (DIF - DEA) * 2

    return RD(DIF), RD(DEA), RD(MACD)


# 初始化函数
def initialize(context):
    g.signal = ''
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 设定基准
    set_benchmark('399101.XSHE')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0.02))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5 / 10000, close_commission=2.5 / 10000,
                             close_today_commission=0, min_commission=5), type='stock')

    # 初始化全局变量 bool
    g.no_trading_today_signal = False  # 是否为可交易日
    g.enable_macd_control = True  # 启用MACD顶背离控制
    g.run_stoploss = True  # 启用止损

    # MACD大盘顶背离控制
    g.dbl = []  # 记录MACD顶背离信号
    g.macd_dead_threshold = 3  # 最近几天内出现顶背离信号则暂停交易

    # 全局变量list
    g.hold_list = []  # 当前持仓的全部股票
    g.yesterday_HL_list = []  # 记录持仓中昨日涨停的股票
    g.yesterday_HL_volume = {}  # 记录昨日涨停股票的昨日成交量（用于放量判断）
    g.target_list = []
    g.not_buy_again = []

    # 全局变量
    g.stock_num = 4
    g.up_price = 100  # 设置股票单价
    g.reason_to_sell = ''

    # 市场趋势止损参数
    g.stoploss_strategy = 3  # 使用第三种止损策略
    g.stoploss_limit = 0.91  # 个股止损线
    g.stoploss_market = 0.95  # 大盘止损线

    # 空仓窗口持有的避险资产：
    # - 增加 511880（货币ETF）用于降低“现金空仓”的机会成本，同时控制回撤波动
    # - 保留黄金/低波动大盘股作为对冲与分散
    g.no_trading_buy = ['511880.XSHG', '518880.XSHG', '600036.XSHG', '600900.XSHG']
    g.no_trading_hold_signal = False
    g.limitup_break_sell_triggered = set()  # 分钟级监控触发过的股票（避免重复卖出信号）

    # 换手风控：缩量信号“只在弱市+弱势个股”触发（避免 V2 的过度换仓，同时保留对流动性陷阱的保护）
    g.huanshou_shrink_enabled = True
    g.huanshou_shrink_avg_threshold = 0.003
    g.huanshou_shrink_only_in_weak_market = True
    g.huanshou_shrink_market_index = '399101.XSHE'
    g.huanshou_shrink_market_ma = 60
    g.huanshou_shrink_market_weak = False
    g.huanshou_shrink_require_stock_weak = True  # 要求个股弱势（跌破MA20或亏损）才触发缩量卖出

    # 昨日涨停开板处理：仅在“强趋势且低波动”市场放宽（减少卖飞），否则保持严格（控制回撤）
    g.limitup_open_hold_market_index = '399101.XSHE'
    g.limitup_open_hold_market_strong = False
    g.limitup_open_hold_vol_lookback = 20
    g.limitup_open_hold_vol_threshold = 0.02  # 20日收益率波动率阈值（越小越稳）

    # 反转选股增强：波动/尾部风险惩罚（弱市加重、强市减弱，避免牛市被“低波动”拖累）
    g.reversal_risk_penalty_enabled = True
    g.reversal_risk_lookback = 20
    g.reversal_risk_vol_weight_weak = 0.1
    g.reversal_risk_tail_weight_weak = 0.2
    g.reversal_risk_vol_weight_strong = 0.0
    g.reversal_risk_tail_weight_strong = 0.0
    g.reversal_risk_apply_only_in_weak_market = True

    # 反转选股增强：风险惩罚的市场门控（除弱市外，也可在“高波动市”启用）
    g.reversal_risk_apply_in_high_vol_market = True
    g.reversal_risk_market_vol_threshold = 0.02
    g.reversal_risk_disable_in_strong_market = True

    # 反转选股增强：RSI 极端超卖惩罚（避免“接飞刀”）；在“强趋势且低波动”市场禁用以减少趋势年拖累
    g.reversal_rsi_penalty_enabled = True
    g.reversal_rsi_period = 14
    g.reversal_rsi_threshold = 20
    g.reversal_rsi_penalty_weight = 0.05
    g.reversal_rsi_disable_in_strong_market = True

    # 调仓“缓冲区”/Banding（V100）：弱市减少噪音换手，强势市不干预
    g.banding_enabled = True
    g.banding_apply_only_in_weak_market = True
    g.banding_margin = 0.005  # score 差距阈值（绝对值），越大越少换仓

    # 空仓窗口结束后“尽快恢复调仓”（V105）
    # - last_forced_adjustment_date：用于避免“周二例行调仓”与“窗口结束提前调仓”在短时间内重复触发
    # - last_adjustment_date：记录最近一次实际发生调仓的日期（用于判断 forced 是否成功执行）
    # - adjustment_caller：None=例行周调仓；"window_exit"=窗口结束触发
    g.last_forced_adjustment_date = None
    g.last_adjustment_date = None
    g.adjustment_caller = None

    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:10')
    run_daily(dapan_macd_check, '9:25')  # 增加MACD大盘检查
    run_daily(monitor_limitup_break_volume_sell, time='every_bar')  # 分钟级监控：昨日涨停开板+放量+跌破开盘价卖出
    run_weekly(weekly_adjustment, 2, '10:33')
    run_daily(window_exit_adjustment, time='10:40')  # 空仓窗口结束后尽快恢复调仓
    run_daily(sell_stocks, time='09:58')  # 止损函数
    run_daily(trade_afternoon, time='14:23')  # 检查持仓中的涨停股是否需要卖出
    run_daily(trade_afternoon, time='14:53')  # 检查持仓中的涨停股是否需要卖出
    run_daily(close_account, '14:48')


def _v119_livesafe_migrate_state_from_baseline():
    """
    实盘/模拟盘代码替换时的“状态迁移”：
    - 聚宽会恢复旧代码保存的 g/context/全局变量
    - initialize 在模拟盘生命周期中只会执行一次（代码替换时不会再执行）
    - 因此需要在 after_code_changed 中补齐/覆盖 V119 新增的关键 g 变量，避免 AttributeError
    """

    def _set(name, value_factory, *, force=False, valid_types=None):
        try:
            exists = hasattr(g, name)
            if not exists:
                setattr(g, name, value_factory() if callable(value_factory) else value_factory)
                return

            if force:
                setattr(g, name, value_factory() if callable(value_factory) else value_factory)
                return

            current = getattr(g, name, None)
            if current is None:
                setattr(g, name, value_factory() if callable(value_factory) else value_factory)
                return

            if valid_types is not None and (not isinstance(current, valid_types)):
                setattr(g, name, value_factory() if callable(value_factory) else value_factory)
        except Exception as e:
            log.warn(f"V119 livesafe migrate failed for g.{name}: {e}")

    # ---- 必须补齐的“新增且在运行期直接读取”的变量（否则可能直接 AttributeError） ----
    _set("yesterday_HL_volume", dict, valid_types=(dict,))
    _set("limitup_break_sell_triggered", set, valid_types=(set,))

    # ---- V119 新增配置（缺失则补齐；其中 no_trading_buy 需要覆盖旧值以生效） ----
    _set("huanshou_shrink_enabled", True)
    _set("huanshou_shrink_avg_threshold", 0.003)
    _set("huanshou_shrink_only_in_weak_market", True)
    _set("huanshou_shrink_market_index", "399101.XSHE")
    _set("huanshou_shrink_market_ma", 60)
    _set("huanshou_shrink_market_weak", False)
    _set("huanshou_shrink_require_stock_weak", True)

    _set("limitup_open_hold_market_index", "399101.XSHE")
    _set("limitup_open_hold_market_strong", False)
    _set("limitup_open_hold_vol_lookback", 20)
    _set("limitup_open_hold_vol_threshold", 0.02)
    _set("limitup_open_hold_market_vol", 0.0)

    _set("reversal_risk_penalty_enabled", True)
    _set("reversal_risk_lookback", 20)
    _set("reversal_risk_vol_weight_weak", 0.1)
    _set("reversal_risk_tail_weight_weak", 0.2)
    _set("reversal_risk_vol_weight_strong", 0.0)
    _set("reversal_risk_tail_weight_strong", 0.0)
    _set("reversal_risk_apply_only_in_weak_market", True)
    _set("reversal_risk_apply_in_high_vol_market", True)
    _set("reversal_risk_market_vol_threshold", 0.02)
    _set("reversal_risk_disable_in_strong_market", True)

    _set("reversal_rsi_penalty_enabled", True)
    _set("reversal_rsi_period", 14)
    _set("reversal_rsi_threshold", 20)
    _set("reversal_rsi_penalty_weight", 0.05)
    _set("reversal_rsi_disable_in_strong_market", True)

    _set("banding_enabled", True)
    _set("banding_apply_only_in_weak_market", True)
    _set("banding_margin", 0.005)

    _set("last_forced_adjustment_date", None)
    _set("last_adjustment_date", None)
    _set("adjustment_caller", None)

    # V119 的空仓窗口停泊资产篮子（覆盖旧值，确保切换后立刻生效）
    _set(
        "no_trading_buy",
        lambda: ["511880.XSHG", "518880.XSHG", "600036.XSHG", "600900.XSHG"],
        force=True,
        valid_types=(list,),
    )
    _set("no_trading_hold_signal", False)

    # 兜底：这些在旧版本通常已存在，但防止异常状态丢失
    _set("hold_list", list, valid_types=(list,))
    _set("yesterday_HL_list", list, valid_types=(list,))
    _set("target_list", list, valid_types=(list,))
    _set("not_buy_again", list, valid_types=(list,))
    _set("dbl", list, valid_types=(list,))
    _set("macd_dead_threshold", 3)
    _set("stock_num", 4)
    _set("up_price", 100)
    _set("stoploss_strategy", 3)
    _set("stoploss_limit", 0.91)
    _set("stoploss_market", 0.95)
    _set("enable_macd_control", True)
    _set("run_stoploss", True)
    _set("reason_to_sell", "")


def _v119_livesafe_capture_g_snapshot(keys):
    def _brief(v):
        try:
            if v is None:
                return "None"
            if isinstance(v, (bool, int, float, str)):
                return repr(v)
            if isinstance(v, (list, tuple)):
                if len(v) <= 10:
                    return repr(v)
                return f"{type(v).__name__}(len={len(v)})"
            if isinstance(v, set):
                if len(v) <= 10:
                    return repr(sorted(list(v)))
                return f"set(len={len(v)})"
            if isinstance(v, dict):
                if len(v) <= 5:
                    return repr(v)
                return f"dict(len={len(v)})"
            return type(v).__name__
        except Exception as e:
            return f"<BRIEF_ERROR {type(e).__name__}: {e}>"

    snap = {}
    for k in keys:
        try:
            if hasattr(g, k):
                snap[k] = _brief(getattr(g, k))
            else:
                snap[k] = "<MISSING>"
        except Exception as e:
            snap[k] = f"<CAPTURE_ERROR {type(e).__name__}: {e}>"
    return snap


def after_code_changed(context):
    log.info("V119 livesafe: after_code_changed -> migrate state + reschedule")
    debug_keys = [
        # critical runtime fields
        "yesterday_HL_volume",
        "limitup_break_sell_triggered",
        # key configs added/changed in V119
        "no_trading_buy",
        "huanshou_shrink_enabled",
        "limitup_open_hold_market_strong",
        "reversal_risk_penalty_enabled",
        "reversal_rsi_penalty_enabled",
        "banding_enabled",
        "banding_margin",
        "last_forced_adjustment_date",
        "last_adjustment_date",
        # common fields (baseline already has; just for sanity)
        "dbl",
        "stock_num",
        "no_trading_hold_signal",
        "no_trading_today_signal",
    ]
    before = _v119_livesafe_capture_g_snapshot(debug_keys)
    # 1) 迁移/补齐状态（关键：initialize 不会在代码替换时重新执行）
    _v119_livesafe_migrate_state_from_baseline()
    after = _v119_livesafe_capture_g_snapshot(debug_keys)
    changed = []
    for k in debug_keys:
        if before.get(k) != after.get(k):
            changed.append((k, before.get(k), after.get(k)))
    log.info(f"V119 livesafe migrate: changed_keys={len(changed)}")
    for k, b, a in changed:
        log.info(f"  g.{k}: {b} -> {a}")

    # 2) 重建定时任务（避免旧代码 schedule 残留）
    unschedule_all()
    run_daily(prepare_stock_list, '9:10')
    run_daily(dapan_macd_check, '9:25')  # 增加MACD大盘检查
    run_daily(monitor_limitup_break_volume_sell, time='every_bar')  # 分钟级监控：昨日涨停开板+放量+跌破开盘价卖出
    run_weekly(weekly_adjustment, 2, '10:33')
    run_daily(window_exit_adjustment, time='10:40')  # 空仓窗口结束后尽快恢复调仓
    run_daily(sell_stocks, time='09:58')  # 止损函数
    run_daily(trade_afternoon, time='14:23')  # 检查持仓中的涨停股是否需要卖出
    run_daily(trade_afternoon, time='14:53')  # 检查持仓中的涨停股是否需要卖出
    run_daily(close_account, '14:48')


# MACD大盘顶背离判断函数
def dapan_macd_check(context):
    """大盘MACD顶背离检查"""
    if not g.enable_macd_control:
        g.dbl.append(False)
        return

    log.info('大盘MACD检查')

    decision = doDecide('399101.XSHE', context)
    if decision['dead']:
        g.dbl.append(True)
        log.info('🚨 大盘MACD顶背离，执行清仓')
        # 清空所有股票仓位
        for stock in context.portfolio.positions.keys():
            if context.portfolio.positions[stock].closeable_amount > 0:
                send_to_trader(context=context, buy_sell='sell', code=stock, money=0)
                order_target_value(stock, 0)
                log.info(f"因MACD顶背离卖出[{stock}]")

        # 买入货币基金避险（如果持有现金）
        if context.portfolio.cash > 10000 and g.no_trading_buy:
            buy_security(context, g.no_trading_buy[:1], cash=context.portfolio.cash, buy_number=1)
            log.info(f"买入避险资产[{g.no_trading_buy[0]}]")
    else:
        g.dbl.append(False)

    # 只保留最近10天的记录
    if len(g.dbl) > 10:
        g.dbl = g.dbl[-10:]

    log.info(f"MACD顶背离信号记录: {g.dbl[-5:]}")  # 显示最近5天


def doDecide(stock, context):
    """MACD顶背离判断函数"""
    fast = 12
    slow = 26
    sign = 9
    rows = (fast + slow + sign) * 5
    suit = {'dif': 0, 'dea': 0, 'macd': 0, 'gold': False, 'dead': False}

    try:
        # 获取足够的历史数据
        grid = attribute_history(stock, rows, fields=['close', 'high', 'low']).dropna()
        if len(grid) < rows * 0.8:
            return suit

        close_list = grid.close.tolist()
        dif_list, dea_list, macd_list = mytt_macd(close_list, SHORT=fast, LONG=slow, M=sign)

        if len(dif_list) > 0:
            # 计算最近的价格和指标
            grid['dif'] = pd.Series(dif_list, index=grid.index)
            grid['dea'] = pd.Series(dea_list, index=grid.index)
            grid['macd'] = pd.Series(macd_list, index=grid.index)

            # 获取当前值
            suit['dif'] = grid['dif'].iloc[-1]
            suit['dea'] = grid['dea'].iloc[-1]
            suit['macd'] = grid['macd'].iloc[-1]

            # 寻找金叉和死叉
            # 金叉：MACD由负转正
            mask = grid['macd'] > 0
            mask = mask[mask == True][mask.shift(1) == False]
            if len(mask) >= 2:
                key2 = mask.keys()[-2]
                key1 = mask.keys()[-1]
                # 底背离条件：价格创新低，但DIF不创新低
                suit['gold'] = grid.close[key2] > grid.close[key1] and \
                               grid.dif[key2] < grid.dif[key1] < 0 and \
                               grid.macd[-2] < 0 < grid.macd[-1]

            # 死叉：MACD由正转负
            mask = grid['macd'] < 0
            mask = mask[mask == True][mask.shift(1) == False]
            if len(mask) >= 2:
                key2 = mask.keys()[-2]
                key1 = mask.keys()[-1]
                # 顶背离条件：价格创新高，但DIF不创新高
                suit['dead'] = grid.close[key2] < grid.close[key1] and \
                               grid.dif[key2] > grid.dif[key1] > 0 and \
                               grid.macd[-2] > 0 > grid.macd[-1]

    except Exception as e:
        log.debug(f"MACD计算异常: {e}")

    return suit


# 1-1 准备股票池
def prepare_stock_list(context):
    # 重置分钟级触发记录（按天）
    g.limitup_break_sell_triggered = set()
    update_huanshou_shrink_market_signal(context)
    update_limitup_open_hold_market_signal(context)

    # 获取已持有列表
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)

    # 获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit', 'low_limit', 'volume'], count=1, panel=False, fill_paused=False)
        df_hl = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df_hl.code)
        g.yesterday_HL_volume = {row.code: row.volume for row in df_hl.itertuples()}
    else:
        g.yesterday_HL_list = []
        g.yesterday_HL_volume = {}

    # 判断今天是否为账户资金再平衡的日期
    g.no_trading_today_signal = today_is_between(context)

    # 调整策略：如果最近有MACD顶背离信号，减少持股数量或暂停交易
    if g.enable_macd_control and g.dbl:
        recent_dead = sum(g.dbl[-g.macd_dead_threshold:])  # 最近几天内的顶背离次数
        if recent_dead > 0:
            g.stock_num = max(2, g.stock_num - 2)  # 减少持股数量
            log.info(f"近期有{recent_dead}次MACD顶背离信号，持股数调整为{g.stock_num}")


# 1-2 选股模块 - 已优化：按市值筛选后按均线偏离度排序
def get_stock_list(context):
    MKT_index = '399101.XSHE'
    initial_list = get_index_stocks(MKT_index)
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)

    # 如果MACD顶背离频繁出现，进一步严格筛选
    if g.enable_macd_control and g.dbl and sum(g.dbl[-5:]) >= 2:
        log.info("MACD顶背离频繁，启用严格筛选")
        # 额外过滤：选择市值更小的股票（更抗跌）
        initial_list = filter_by_market_cap(initial_list, top_n=100)

    # 第一步：按流通市值排序，选取最小的 g.stock_num * 2 只股票
    q = query(valuation.code).filter(valuation.code.in_(initial_list)).order_by(
        valuation.circulating_market_cap.asc()).limit(g.stock_num * 2)
    df_cap = get_fundamentals(q)
    candidate_list = list(df_cap.code)

    # 过滤涨停跌停股
    candidate_list = filter_limitup_stock(context, candidate_list)
    candidate_list = filter_limitdown_stock(context, candidate_list)

    if len(candidate_list) == 0:
        log.warn("没有符合条件的候选股票")
        return []

    # 第二步：计算均线偏离度并排序
    deviation_list = calculate_ma_deviation(context, candidate_list)

    if len(deviation_list) == 0:
        log.warn("无法计算均线偏离度")
        return []

    # 按“反转打分”升序排序（越低越优：越超跌 +（弱市）越低波动/尾部风险）
    deviation_list.sort(key=lambda x: x[1])

    # 选取分数最低的股票
    final_list = [stock for stock, score, deviation, vol, tail, rsi in deviation_list[:g.stock_num * 2]]

    log.info('今日选股结果:%s' % final_list)
    log.info(
        '反转打分:%s' % [
            (stock, f"score={score:.2%}", f"dev={deviation:.2%}",
             f"vol={vol:.2%}" if vol is not None else "vol=?",
             f"tail={tail:.2%}" if tail is not None else "tail=?",
             f"rsi={rsi:.1f}" if rsi is not None else "rsi=?")
            for stock, score, deviation, vol, tail, rsi in deviation_list[:g.stock_num]
        ]
    )

    return final_list


def filter_by_market_cap(stock_list, top_n=100):
    """按市值筛选股票"""
    if not stock_list:
        return []

    q = query(valuation.code).filter(valuation.code.in_(stock_list)).order_by(
        valuation.circulating_market_cap.asc()).limit(top_n)
    df = get_fundamentals(q)
    return list(df.code)


# 新增函数：计算均线偏离度
def calculate_ma_deviation(context, stock_list):
    """
    计算股票的均线偏离度
    偏离度 = (当前收盘价 / 20日MA - 1)
    并在弱市加入波动/尾部风险惩罚（强市不惩罚，避免拖累趋势年）
    额外：RSI 极端超卖惩罚（避免“接飞刀”，在强趋势低波动市禁用）
    返回值：[(股票代码, score, 偏离度, 波动率, 尾部风险, RSI), ...]
    """
    end_date = context.previous_date
    deviation_data = []
    penalty_enabled = bool(getattr(g, 'reversal_risk_penalty_enabled', True))
    lookback = int(getattr(g, 'reversal_risk_lookback', 20))
    lookback = max(10, lookback)
    apply_only_weak = bool(getattr(g, 'reversal_risk_apply_only_in_weak_market', True))
    market_weak = bool(getattr(g, 'huanshou_shrink_market_weak', False))
    market_strong = bool(getattr(g, 'limitup_open_hold_market_strong', False))
    market_vol = getattr(g, 'limitup_open_hold_market_vol', None)
    try:
        market_vol = float(market_vol) if market_vol is not None else None
    except Exception:
        market_vol = None

    apply_in_high_vol = bool(getattr(g, 'reversal_risk_apply_in_high_vol_market', False))
    vol_thr = float(getattr(g, 'reversal_risk_market_vol_threshold', 0.02))
    disable_in_strong = bool(getattr(g, 'reversal_risk_disable_in_strong_market', True))

    if disable_in_strong and market_strong:
        apply_penalty = False
    else:
        apply_penalty = bool(market_weak) if apply_only_weak else False
        if (not apply_penalty) and apply_in_high_vol and (market_vol is not None):
            apply_penalty = bool(market_vol >= vol_thr)

    if not apply_penalty:
        w_vol, w_tail = 0.0, 0.0
    else:
        w_vol = float(getattr(g, 'reversal_risk_vol_weight_weak', 0.4))
        w_tail = float(getattr(g, 'reversal_risk_tail_weight_weak', 0.8))

    rsi_enabled = bool(getattr(g, 'reversal_rsi_penalty_enabled', True))
    rsi_period = int(getattr(g, 'reversal_rsi_period', 14))
    rsi_period = max(2, min(rsi_period, 60))
    rsi_thr = float(getattr(g, 'reversal_rsi_threshold', 20.0))
    rsi_weight = float(getattr(g, 'reversal_rsi_penalty_weight', 0.0))
    disable_rsi_in_strong = bool(getattr(g, 'reversal_rsi_disable_in_strong_market', True))
    w_rsi = rsi_weight if (rsi_enabled and (rsi_weight != 0.0) and (not (disable_rsi_in_strong and market_strong))) else 0.0

    for stock in stock_list:
        try:
            count = max(20, lookback) + 1
            prices = get_price(stock, end_date=end_date, frequency='daily',
                               fields=['close'], count=count, panel=False, fill_paused=False)

            if prices is None or prices.empty:
                continue

            close_series = pd.to_numeric(prices['close'], errors='coerce').dropna()
            if len(close_series) < 21:
                continue

            current_close = float(close_series.iloc[-1])
            ma20 = float(close_series.iloc[-20:].mean())

            # 计算偏离度
            deviation = (current_close / ma20) - 1 if ma20 > 0 else 0.0

            score = float(deviation)
            vol = None
            tail = None
            rsi = None
            if penalty_enabled and (w_vol != 0.0 or w_tail != 0.0):
                returns = close_series.pct_change().dropna()
                lb = returns.iloc[-lookback:] if len(returns) >= lookback else returns
                if lb is not None and not lb.empty:
                    vol = float(lb.std())
                    min_ret = float(lb.min())
                    tail = float(abs(min_ret)) if min_ret < 0 else 0.0
                else:
                    vol = 0.0
                    tail = 0.0
                score = float(deviation) + w_vol * float(vol) + w_tail * float(tail)

            if w_rsi != 0.0 and rsi_thr > 0 and len(close_series) >= (rsi_period + 1):
                delta = close_series.diff()
                gain = delta.clip(lower=0.0)
                loss = (-delta).clip(lower=0.0)
                avg_gain = gain.ewm(alpha=1 / float(rsi_period), adjust=False, min_periods=rsi_period).mean()
                avg_loss = loss.ewm(alpha=1 / float(rsi_period), adjust=False, min_periods=rsi_period).mean()
                rs = avg_gain / avg_loss
                rsi_series = 100.0 - (100.0 / (1.0 + rs))
                rsi_val = float(rsi_series.iloc[-1])
                if not pd.isna(rsi_val):
                    rsi = rsi_val
                    if rsi < rsi_thr:
                        score = float(score) + w_rsi * (float(rsi_thr) - float(rsi)) / float(rsi_thr)

            deviation_data.append((stock, float(score), float(deviation), vol, tail, rsi))

        except Exception as e:
            log.warn(f"计算股票{stock}均线偏离度时出错: {e}")
            continue

    return deviation_data


def window_exit_adjustment(context):
    """
    空仓窗口结束后恢复调仓（V119）：
    - 若刚从空仓窗口出来且仍持有停泊资产（no_trading_hold_signal=True）；
    - 仅在“强趋势 + 低波动”市场（limitup_open_hold_market_strong=True）才提前恢复调仓；
      否则等待例行周调仓，避免在弱势环境中“过早回到小市值仓位”带来额外回撤与噪音换手。
    """
    if bool(getattr(g, "no_trading_today_signal", False)):
        return
    if not bool(getattr(g, "no_trading_hold_signal", False)):
        return
    # 仅强势市场才提前恢复
    if not bool(getattr(g, "limitup_open_hold_market_strong", False)):
        return

    prev_adjust_date = getattr(g, "last_adjustment_date", None)
    g.adjustment_caller = "window_exit"
    try:
        weekly_adjustment(context)
    finally:
        g.adjustment_caller = None

    cur_adjust_date = getattr(g, "last_adjustment_date", None)
    today = context.current_dt.date()
    if cur_adjust_date == today and cur_adjust_date != prev_adjust_date:
        g.last_forced_adjustment_date = today


# 1-3 整体调整持仓 - 已优化：按均线偏离度排序调仓
def weekly_adjustment(context):
    # 若本周已在“空仓窗口结束”后提前调仓，则跳过距离过近的例行周调仓（避免重复换手）
    caller = getattr(g, "adjustment_caller", None)
    if caller is None:
        forced_date = getattr(g, "last_forced_adjustment_date", None)
        if forced_date:
            try:
                days = (context.current_dt.date() - forced_date).days
            except Exception:
                days = None
            if days is not None and 0 <= days <= 2:
                log.info("已在空仓窗口结束后提前调仓，跳过本次例行周调仓")
                g.last_forced_adjustment_date = None
                return
            # 清理过期标记，避免长期占用状态
            g.last_forced_adjustment_date = None

    # 检查MACD顶背离信号，如果近期有信号则暂停调仓
    if g.enable_macd_control and g.dbl:
        recent_dead = sum(g.dbl[-g.macd_dead_threshold:])
        if recent_dead > 0:
            log.info(f"近期有{recent_dead}次MACD顶背离信号，暂停本周调仓")
            return

    if g.no_trading_today_signal == False:
        close_no_trading_hold(context)
        # 避免持仓列表过期（分钟级卖出可能发生在 prepare_stock_list 之后）
        g.hold_list = [position.security for position in list(context.portfolio.positions.values())]
        # 获取应买入列表
        g.not_buy_again = []
        desired_list = get_stock_list(context)
        g.target_list = desired_list

        # banding：弱市减少“微小分数差异”导致的无效换手
        if bool(getattr(g, "banding_enabled", False)):
            apply_only_weak = bool(getattr(g, "banding_apply_only_in_weak_market", True))
            market_weak = bool(getattr(g, "huanshou_shrink_market_weak", False))
            if (not apply_only_weak) or market_weak:
                g.target_list = apply_banding_to_target_list(context, desired_list)

        if not g.target_list:
            log.warn("今日无目标股票，跳过调仓")
            return

        log.info('target list:{}'.format(g.target_list))

        # 调仓卖出：不在目标列表且不是昨日涨停的股票
        for stock in g.hold_list:
            if (stock not in g.target_list) and (stock not in g.yesterday_HL_list):
                log.info("卖出[%s]" % (stock))
                if stock not in context.portfolio.positions:
                    continue
                position = context.portfolio.positions[stock]
                send_to_trader(context=context, buy_sell='sell', code=stock, money=0)
                close_position(position)
            else:
                log.info("已持有[%s]" % (stock))

        # 调仓买入
        buy_security(context, g.target_list)

        # 记录已买入股票
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.not_buy_again.append(stock)

        # 记录本次实际调仓日期（用于 forced 调仓识别）
        g.last_adjustment_date = context.current_dt.date()


# 1-4 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        # 对昨日涨停股票：
        # - “强趋势且低波动”市：开板不立刻卖，只有跌破开盘价才卖（减少卖飞）
        # - 其他市场：维持原逻辑（开板就卖，控制回撤）
        market_strong = bool(getattr(g, 'limitup_open_hold_market_strong', False))
        cur = get_current_data()
        for stock in g.yesterday_HL_list:
            if stock not in context.portfolio.positions:
                continue
            if context.portfolio.positions[stock].closeable_amount > -100:
                cd = cur.get(stock)
                if cd is None or cd.paused:
                    continue

                last_price = getattr(cd, 'last_price', None)
                high_limit = getattr(cd, 'high_limit', None)
                if last_price is None or high_limit is None or pd.isna(last_price) or pd.isna(high_limit) or high_limit <= 0:
                    continue

                if float(last_price) >= float(high_limit):
                    log.info("[%s]涨停，继续持有" % (stock))
                    continue

                if not market_strong:
                    log.info("[%s]非强势低波动市涨停打开，卖出" % (stock))
                    position = context.portfolio.positions[stock]
                    send_to_trader(context=context, buy_sell='sell', code=stock, money=0)
                    close_position(position)
                    g.reason_to_sell = 'limitup'
                    continue

                open_price = getattr(cd, 'day_open', None)
                if open_price is None or pd.isna(open_price) or open_price <= 0:
                    df_open = get_price(stock, end_date=now_time, frequency='daily', fields=['open'],
                                        skip_paused=False, fq='pre', count=1, panel=True, fill_paused=True)
                    if df_open is None or df_open.empty:
                        continue
                    open_price = float(df_open['open'].iloc[-1])
                if open_price is None or pd.isna(open_price) or open_price <= 0:
                    continue

                if float(last_price) < float(open_price):
                    log.info("[%s]强势低波动市涨停打开且跌破开盘价，卖出" % (stock))
                    position = context.portfolio.positions[stock]
                    send_to_trader(context=context, buy_sell='sell', code=stock, money=0)
                    close_position(position)
                    g.reason_to_sell = 'limitup'
                else:
                    log.info("[%s]强势低波动市涨停打开但未跌破开盘价，继续持有" % (stock))


# 分钟级监控：昨日涨停，今日开板 + 放量（今量 > 2 * 昨量）+ 跌破开盘价 直接卖出
def monitor_limitup_break_volume_sell(context):
    if not g.yesterday_HL_list:
        return
    if getattr(g, 'no_trading_today_signal', False):
        return

    now_time = context.current_dt
    current_data = get_current_data()

    for stock in g.yesterday_HL_list:
        if stock in g.limitup_break_sell_triggered:
            continue
        if stock not in context.portfolio.positions:
            continue

        position = context.portfolio.positions[stock]
        if position.closeable_amount <= 0:
            continue

        cd = current_data[stock]
        if cd.paused:
            continue

        last_price = cd.last_price
        high_limit = cd.high_limit
        if last_price is None or high_limit is None or pd.isna(last_price) or pd.isna(high_limit) or high_limit <= 0:
            continue
        if last_price >= high_limit:
            # 仍在涨停价，不处理
            continue

        open_price = getattr(cd, 'day_open', None)
        if open_price is None or pd.isna(open_price) or open_price <= 0:
            # 兜底：取当日（日线）开盘价
            df_open = get_price(stock, end_date=now_time, frequency='daily', fields=['open'],
                                skip_paused=False, fq='pre', count=1, panel=True, fill_paused=True)
            if df_open is None or df_open.empty:
                continue
            open_price = float(df_open['open'].iloc[-1])
        if open_price is None or pd.isna(open_price) or open_price <= 0:
            continue

        if last_price >= open_price:
            continue

        yesterday_volume = g.yesterday_HL_volume.get(stock)
        if yesterday_volume is None:
            df_yv = get_price(stock, end_date=context.previous_date, frequency='daily', fields=['volume'],
                              skip_paused=False, fq='pre', count=1, panel=True, fill_paused=False)
            if df_yv is None or df_yv.empty:
                continue
            yesterday_volume = float(df_yv['volume'].iloc[-1])
            g.yesterday_HL_volume[stock] = yesterday_volume

        if yesterday_volume is None or pd.isna(yesterday_volume) or yesterday_volume <= 0:
            continue

        # 今天当前成交量：分钟成交量累加（与本策略现有换手率计算口径一致）
        df_tv = get_price(stock, start_date=now_time.date(), end_date=now_time, frequency='1m', fields=['volume'],
                          skip_paused=False, fq='pre', panel=True, fill_paused=False)
        if df_tv is None or df_tv.empty:
            today_volume = getattr(cd, 'volume', None) or getattr(cd, 'day_volume', None)
        else:
            today_volume = float(df_tv['volume'].sum())
        if today_volume is None or pd.isna(today_volume) or today_volume <= 0:
            continue

        if today_volume <= 2 * yesterday_volume:
            continue

        log.info(
            f"[{stock}] 昨日涨停，今日开板+放量+跌破开盘价 -> 卖出 | "
            f"现价:{last_price:.2f} 开盘:{open_price:.2f} 涨停价:{high_limit:.2f} "
            f"今量:{today_volume:.0f} 昨量:{yesterday_volume:.0f}"
        )
        g.limitup_break_sell_triggered.add(stock)
        send_to_trader(context=context, buy_sell='sell', code=stock, money=0)
        close_position(position)
        g.reason_to_sell = 'limitup'


# 1-5 如果昨天有股票卖出或者买入失败，剩余的金额今天早上买入
def check_remain_amount(context):
    if g.reason_to_sell == 'limitup':  # 判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
        g.hold_list = []
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.hold_list.append(stock)
        if len(g.hold_list) < g.stock_num:
            target_list = get_stock_list(context)
            # 剔除本周一曾买入的股票，不再买入
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            log.info('有余额可用' + str(round((context.portfolio.cash), 2)) + '元。' + str(target_list))
            buy_security(context, target_list)
        g.reason_to_sell = ''

    else:
        g.reason_to_sell = ''


# 1-6 下午检查交易
def trade_afternoon(context):
    if g.no_trading_today_signal == False:
        check_limit_up(context)
        huanshou(context)
        check_remain_amount(context)


# 1-7 止盈止损 - 融合了MACD策略的止损逻辑
def sell_stocks(context):
    if not g.run_stoploss:
        return

    # 使用第三种止损策略：结合大盘和个股止损
    if g.stoploss_strategy == 3:
        # 检查大盘情况
        stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date,
                             frequency='daily', fields=['close', 'open'], count=1, panel=False)
        down_ratio = (stock_df['close'] / stock_df['open']).mean()

        # 如果大盘大幅下跌，清仓
        if down_ratio <= g.stoploss_market:
            g.reason_to_sell = 'stoploss'
            log.info("大盘惨跌,平均降幅{:.2%}，执行清仓".format(down_ratio))
            for stock in context.portfolio.positions.keys():
                if context.portfolio.positions[stock].closeable_amount > 0:
                    send_to_trader(context=context, buy_sell='sell', code=stock, money=0)
                    order_target_value(stock, 0)
        else:
            # 个股止损
            for stock in context.portfolio.positions.keys():
                if context.portfolio.positions[stock].price < context.portfolio.positions[
                    stock].avg_cost * g.stoploss_limit:
                    send_to_trader(context=context, buy_sell='sell', code=stock, money=0)
                    order_target_value(stock, 0)
                    log.info("收益止损,卖出{}".format(stock))
                    g.reason_to_sell = 'stoploss'


# 2-1 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


# 2-2 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


# 2-3 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68' or stock[:2] == '30':
            stock_list.remove(stock)
    return stock_list


# 2-4 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


# 2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if (stock in context.portfolio.positions.keys()
                                              or last_prices[stock][-1] > current_data[stock].low_limit)
            ]


# 2-6 过滤次新股
def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if
            not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=375)]


# 2-6.5 过滤股价
def filter_highprice_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] <= g.up_price]


# 2-7 删除本周一买入的股票
def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]


# 获取股票所属行业
def get_stock_industry(stock):
    result = get_industry(security=stock)
    selected_stocks = []
    industry_list = []

    for stock_code, info in result.items():
        industry_name = info['sw_l2']['industry_name']
        if industry_name not in industry_list:
            industry_list.append(industry_name)
            selected_stocks.append(stock_code)
            print(f"行业信息: {industry_name} (股票: {stock_code})")
            # 选取了 10 个不同行业的股票
            if len(industry_list) == 10:
                break
    return selected_stocks


# 换手率计算
def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        # 计算平均换手率
        start_date = context.current_dt - datetime.timedelta(days=20)
        end_date = context.previous_date
        df_volume = get_price(stock, end_date=end_date, frequency='daily', fields=['volume'], count=20)
        df_cap = get_valuation(stock, end_date=end_date, fields=['circulating_cap'], count=1)
        circulating_cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
        return df_volume['turnover_ratio'].mean()
    else:
        # 计算实时换手率
        date_now = context.current_dt
        df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now, frequency='1m', fields=['volume'],
                           skip_paused=False, fq='pre', panel=True, fill_paused=False)
        volume = df_vol['volume'].sum()
        date_pre = context.previous_date
        df_circulating_cap = get_valuation(stock, end_date=date_pre, fields=['circulating_cap'], count=1)
        circulating_cap = df_circulating_cap['circulating_cap'].iloc[0] if not df_circulating_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        turnover_ratio = volume / (circulating_cap * 10000)
        return turnover_ratio


# 换手检测
def huanshou(context):
    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0: continue
        r = rt / avg
        action, icon = '', ''
        # 缩量：只在弱市且个股弱势时触发（保留对流动性陷阱的保护，避免牛市/强势股被误杀）
        if bool(getattr(g, 'huanshou_shrink_enabled', False)) and avg < float(
            getattr(g, 'huanshou_shrink_avg_threshold', shrink)
        ):
            only_weak_market = bool(getattr(g, 'huanshou_shrink_only_in_weak_market', True))
            market_weak = bool(getattr(g, 'huanshou_shrink_market_weak', False))
            if (not only_weak_market) or market_weak:
                if not bool(getattr(g, 'huanshou_shrink_require_stock_weak', True)) or is_stock_weak(
                    context, stock, float(current_data[stock].last_price), context.portfolio.positions[stock]
                ):
                    action, icon = '缩量', '❄️'

        # 放量：保留“放量异常”作为风险信号
        if rt > expand and r > 2:
            action, icon = '放量', '🔥'
        if action:
            log.info(
                f"{action} {stock} {get_security_info(stock).display_name} 换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x {icon}")
            position = context.portfolio.positions[stock]
            send_to_trader(context=context, buy_sell='sell', code=stock, money=0)
            close_position(position)
            g.reason_to_sell = 'limitup'


def update_huanshou_shrink_market_signal(context):
    """更新“缩量卖出”所用的大盘弱势信号（仅用于缩量条件，避免频繁计算）。"""
    try:
        index_code = str(getattr(g, 'huanshou_shrink_market_index', '399101.XSHE'))
        ma = int(getattr(g, 'huanshou_shrink_market_ma', 60))
        ma = max(20, ma)
        df = get_price(index_code, end_date=context.previous_date, frequency='daily', fields=['close'],
                       count=ma, panel=False, fill_paused=False)
        if df is None or df.empty or len(df) < ma:
            return
        close_series = pd.to_numeric(df['close'], errors='coerce').dropna()
        if len(close_series) < ma:
            return
        last_close = float(close_series.iloc[-1])
        ma_val = float(close_series.mean())
        g.huanshou_shrink_market_weak = bool(last_close < ma_val)
    except Exception as e:
        log.warn(f"update_huanshou_shrink_market_signal failed: {e}")


def update_limitup_open_hold_market_signal(context):
    """更新“强趋势且低波动”信号（用于昨日涨停开板是否放宽卖出）。"""
    try:
        index_code = str(getattr(g, 'limitup_open_hold_market_index', '399101.XSHE'))
        df = get_price(index_code, end_date=context.previous_date, frequency='daily', fields=['close'],
                       count=60, panel=False, fill_paused=False)
        if df is None or df.empty or len(df) < 60:
            return
        close_series = pd.to_numeric(df['close'], errors='coerce').dropna()
        if len(close_series) < 60:
            return

        close = float(close_series.iloc[-1])
        ma20 = float(close_series.iloc[-20:].mean())
        ma60 = float(close_series.mean())
        ret5 = (close / float(close_series.iloc[-6]) - 1) if float(close_series.iloc[-6]) > 0 else 0.0

        lookback = int(getattr(g, 'limitup_open_hold_vol_lookback', 20))
        lookback = max(10, min(lookback, 60))
        vol_thr = float(getattr(g, 'limitup_open_hold_vol_threshold', 0.02))
        returns = pd.Series(close_series).pct_change().dropna()
        vol = float(returns.iloc[-lookback:].std()) if len(returns) >= lookback else float(returns.std())

        g.limitup_open_hold_market_vol = float(vol)
        g.limitup_open_hold_market_strong = bool(close > ma20 > ma60 and ret5 > 0.0 and vol < vol_thr)
    except Exception as e:
        log.warn(f"update_limitup_open_hold_market_signal failed: {e}")


def apply_banding_to_target_list(context, desired_list):
    """
    调仓缓冲区（banding）：
    - 先计算“持仓 ∪ 目标候选”的 score
    - 如果持仓将被“微弱优势”的新候选替换，则允许继续持有（减少噪音换手）
    返回：用于调仓的 target_list（主要用于“哪些股票不卖 + 买哪些”）
    """
    if not desired_list:
        return desired_list

    # 当前持仓（剔除昨日涨停：该类本来就不在周调仓中卖出）
    holdings_all = [position.security for position in list(context.portfolio.positions.values())]
    fixed = set(s for s in holdings_all if s in getattr(g, "yesterday_HL_list", []))
    holdings = [s for s in holdings_all if s not in fixed]

    target_num = int(getattr(g, "stock_num", 4))
    adjustable_slots = max(0, target_num - len(fixed))
    if adjustable_slots <= 0:
        return []

    universe = list(set(list(desired_list) + list(holdings)))
    if not universe:
        return desired_list

    scored = calculate_ma_deviation(context, universe)
    score_map = {s: float(score) for (s, score, dev, vol, tail, rsi) in scored}

    def score_of(s):
        return float(score_map.get(s, 1e9))

    ranked = sorted(universe, key=score_of)
    proposed = ranked[:adjustable_slots]
    if not proposed:
        return desired_list

    cutoff = max(score_of(s) for s in proposed)
    margin = float(getattr(g, "banding_margin", 0.005))

    # 仅当“当前持仓将被新候选替换”且差距很小，才允许继续持有以减少换手
    keepers = [h for h in holdings if (h not in proposed) and (score_of(h) <= cutoff + margin)]
    if not keepers:
        final = list(proposed)
        return final + [s for s in desired_list if s not in final]

    # 只替换 proposed 中的“新买入”（不替换原本就持有的），以最大化减少交易
    new_entrants = [s for s in proposed if s not in holdings]
    new_entrants.sort(key=score_of, reverse=True)  # 最差的新买入优先被替换

    final = list(proposed)
    replaced = []
    for k in sorted(keepers, key=score_of):
        if not new_entrants:
            break
        drop = new_entrants.pop(0)
        if drop in final:
            final.remove(drop)
            final.append(k)
            replaced.append((drop, k))

    final = sorted(list(dict.fromkeys(final)), key=score_of)
    log.info(f"banding: cutoff={cutoff:.2%} margin={margin:.2%} replaced={replaced} final={final}")
    return final + [s for s in desired_list if s not in final]


def is_stock_weak(context, stock, last_price, position):
    """个股弱势判定：跌破 MA20 或处于亏损（避免强势股缩量被误杀）。"""
    try:
        # 若已明显盈利，则不因缩量卖出（避免卖飞强势股）
        if position is not None and getattr(position, 'avg_cost', None):
            avg_cost = float(position.avg_cost)
            if avg_cost > 0 and float(last_price) >= avg_cost * 1.05:
                return False

        df = get_price(stock, end_date=context.previous_date, frequency='daily', fields=['close'],
                       count=20, panel=False, fill_paused=False)
        if df is None or df.empty or len(df) < 20:
            # 数据缺失时，回退用盈亏判断
            if position is None or not getattr(position, 'avg_cost', None):
                return True
            avg_cost = float(position.avg_cost)
            return avg_cost > 0 and float(last_price) < avg_cost

        close_series = pd.to_numeric(df['close'], errors='coerce').dropna()
        if len(close_series) < 20:
            if position is None or not getattr(position, 'avg_cost', None):
                return True
            avg_cost = float(position.avg_cost)
            return avg_cost > 0 and float(last_price) < avg_cost

        ma20 = float(close_series.mean())
        if ma20 <= 0:
            return True

        # 亏损 or 跌破 MA20
        if position is not None and getattr(position, 'avg_cost', None):
            avg_cost = float(position.avg_cost)
            if avg_cost > 0 and float(last_price) < avg_cost:
                return True
        return float(last_price) < ma20
    except Exception as e:
        log.warn(f"is_stock_weak failed for {stock}: {e}")
        return True


# 3-1 交易模块-自定义下单
def order_target_value_(security, value):
    if value == 0:
        pass
    else:
        pass
    return order_target_value(security, value)


# 3-2 交易模块-开仓
def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return order
    return None


# 3-3 交易模块-平仓
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False


# 3-4 买入模块
def buy_security(context, target_list, cash=0, buy_number=0):
    # 调仓买入
    position_count = len(context.portfolio.positions)
    target_num = g.stock_num
    if cash == 0:
        cash = context.portfolio.total_value  # cash
    if buy_number == 0:
        buy_number = target_num
    bought_num = 0

    if target_num > position_count:
        value = cash / (target_num - position_count)
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
                if bought_num < buy_number:
                    order = open_position(stock, value)
                    if order is not None:
                        # 用聚宽实际成交量发送，避免因资金/手数调整导致下游下单量偏大
                        send_to_trader(context=context, buy_sell='buy', code=stock, volume=order.filled)
                        g.not_buy_again.append(stock)  # 持仓清单，后续不希望再买入
                        bought_num += 1
                        if len(context.portfolio.positions) == target_num:
                            break


# 4-1 判断今天是否为四月
def today_is_between(context):
    """
    空仓区间：
    1) 03-25 ~ 04-25（同一年）
    2) 12-25 ~ 次年 01-25（跨年）
    返回 True 表示空仓期
    """
    d = context.current_dt.date()
    y = d.year

    # 区间1：当年 03-25 ~ 04-25
    if datetime.date(y, 3, 25) <= d <= datetime.date(y, 4, 25):
        return True

    # 区间2：跨年 12-25 ~ 次年 01-25
    # 如果在当年12月25日之后（含），或在当年1月25日之前（含），都属于跨年区间
    if d >= datetime.date(y, 12, 25) or d <= datetime.date(y, 1, 25):
        return True

    return False


# 4-2 清仓后次日资金可转
def close_account(context):
    """
    空仓窗口资产切换逻辑优化（V102）：
    - 修复原逻辑的“若当日已无持仓则不会买入避险资产，导致长期 Cash-only”的问题；
    - 进入空仓窗口后：卖出所有非避险资产，并买入避险资产篮子。
    """
    if g.no_trading_today_signal != True:
        return

    no_trading_assets = list(getattr(g, "no_trading_buy", []) or [])
    if not no_trading_assets:
        return

    desired = set(no_trading_assets)

    # 卖出所有非避险资产
    has_non_desired = False
    for stock in list(context.portfolio.positions.keys()):
        if stock in desired:
            continue
        position = context.portfolio.positions.get(stock)
        if position is None:
            continue
        if getattr(position, "closeable_amount", 0) <= 0:
            continue
        has_non_desired = True
        send_to_trader(context=context, buy_sell='sell', code=stock, money=0)
        if close_position(position):
            log.info("卖出[%s]" % (stock))
        else:
            log.info("卖出[%s]错误！！！！！" % (stock))

    # 判断是否已持有任意避险资产
    holding_no_trading = False
    for stock in desired:
        if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
            holding_no_trading = True
            break

    # 买入避险资产（即便当日原本没有持仓，也应从现金切换到避险资产）
    if (not holding_no_trading) and (context.portfolio.cash > 10000):
        buy_security(context, no_trading_assets, cash=context.portfolio.cash, buy_number=len(no_trading_assets))
        log.info(f"买入避险资产{no_trading_assets}")
        holding_no_trading = True

    # 标记空仓窗口持有信号（即便有部分非避险资产因停牌/跌停卖不掉，也应进入“空仓窗口状态”）
    if holding_no_trading:
        g.no_trading_hold_signal = True


# 4-3 清仓小市值不交易期间股票
def close_no_trading_hold(context):
    if g.no_trading_hold_signal == True:
        for stock in g.hold_list:
            if stock not in context.portfolio.positions:
                continue
            position = context.portfolio.positions[stock]
            send_to_trader(context=context, buy_sell='sell', code=stock, money=0)
            close_position(position)
            log.info("卖出[%s]" % (stock))
        g.no_trading_hold_signal = False



def send_to_trader(context, buy_sell, code, money=None, volume=None, use_open_price=False):
    """
    说明：
    - 卖出：请传 money=0（先发信号再真正卖出），函数会用持仓的 closeable_amount 计算应卖数量
    - 买入：可传 money=目标金额，本函数按当前价换算为100股整数倍
    - use_open_price=True 时取当日开盘价，否则取最新价
    """
    pass
    # try:
    #     assert money is not None or volume is not None, 'money or volume must be not None'
    #     content = read_file('socket.json')  # JoinQuant 内置文件读
    #     socket_dict = json.loads(content)
    #     current_data = get_current_data()
    #     price = current_data[code].day_open if use_open_price else current_data[code].last_price

    #     if money is not None:
    #         if money == 0:
    #             # 卖出：取可卖数量
    #             if code in context.portfolio.positions:
    #                 volume = context.portfolio.positions[code].closeable_amount
    #             else:
    #                 volume = 0
    #         else:
    #             # 买入：按金额→股数（取100股整数倍）
    #             volume = int(money // max(price, 1e-9)) // 100 * 100

    #     if volume is None:
    #         volume = 0
    #     if volume < 0:
    #         volume = -volume

    #     dict_send = {
    #         'strategy': 'XSZ_MACD_MA20',  # 策略标识可按需修改
    #         'buy_sell': buy_sell,  # 'buy' | 'sell'
    #         'price': price,
    #         'code': code,
    #         'volume': int(volume),
    #         'run_type': context.run_params.type
    #     }
    #     print('send:', dict_send)

    #     payload = json.dumps(dict_send).encode('utf-8')
    #     client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     client.settimeout(5.0)
    #     client.connect((socket_dict['ip'], socket_dict['port']))
    #     client.send(payload)
    #     client.close()
    #     time.sleep(5)  # 与你其他策略保持一致，给下游处理时间
    # except Exception as e:
    #     print(str(e))
    #     send_message('Send Error, msg: {}'.format(str(e)))  # JoinQuant 内置消息推送
