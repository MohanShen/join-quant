# Clone from JoinQuant
# postId: 2e02fb4c347906333618966b3e67da10
# backtestId: 8f71cd85a1df62212195bc8080e23762
# title: 回撤18%年化389%，反狙击ETF轮动

# 克隆自聚宽文章：https://www.joinquant.com/post/69163
# 标题：【策略优化】ETF轮动策略优化-V1.7
# 作者：旭日东升量化

# 策略名称：牛来ETF轮动策略-V1.0
# 策略作者：屌丝逆袭量化
# 优化作者：养家大哥
# 优化时间：2026-9-3
# 优化内容：
# 1、将盈利保护模块独立拆分，支持自定义多个检查时间点（如11:00）
# 2、移除原有卖出函数中的盈利保护逻辑，由独立检查函数负责
# 3、优化各过滤顺序，统一在排名计算中排除不符合条件的ETF
# 4、溢价率获取失败时跳过过滤，而非直接排除（2026-04-01修改）
# 5、【V1.8】买卖时点随机化，防止固定时间（14:00）被阻击：
#    - 开盘前（09:15）随机生成当日买卖触发基准时间（全天交易时段随机，5分钟整数倍）
#    - 盘中每5分钟轮询，到达随机时点即执行买卖（保留原有日频动量信号，不引入额外择时）
#    - 14:45仍未触发则保底执行，避免整天不成交
# 6、【V1.0】本轮优化（养家大哥，2026-9-3）：
#    - ETF池去重：删除高相关重复标的（纳指科技/纳指生物/标普消费、港股互联/恒生科技/中概互联网/港股红利、中证2000/上证ETF），38只精简至29只
#    - 代码精简：删除死代码（etf_sell_trade/etf_buy_trade/备份池），消除重复计算（抽出fit_log_slope统一拟合），清理无用参数，18函数精简至16函数
#    - 净值回撤保护（双净值+弹性空仓）：实际净值相对历史最高回撤超10%触发空仓；空仓期维护模拟净值（假设一直按动量信号持仓），满5个交易日后若模拟净值回撤收窄到阈值内则提前恢复，否则持续空仓至信号出现

import numpy as np
import math
import datetime
import random
import pandas as pd
from jqdata import *

# ==================== 初始化模块 ====================
def initialize(context):
    """
    初始化函数：设置交易参数、ETF池、核心参数、调度任务
    """
    # ---------- 交易设置 ----------
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0002,
            close_commission=0.0002,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    set_benchmark("161226.XSHE")

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    log.info("========== 策略初始化开始 ==========")

    # ---------- ETF池 ----------
    g.etf_pool = [
        # 大宗商品ETF
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色ETF（跟踪有色金属板块）
        "159985.XSHE",  # 豆粕ETF（跟踪豆粕期货价格）
        "501018.XSHG",  # 南方原油（投资原油相关资产）
        '161226.XSHE',  # 白银LOF
        "159981.XSHE",  # 能源化工ETF
        # 国际ETF
        "513100.XSHG",  # 纳指ETF
        "513500.XSHG",  # 标普500ETF
        "513400.XSHG",  # 道琼斯ETF
        "513520.XSHG",  # 日经225ETF
        "513030.XSHG",  # 德国30ETF
        "513080.XSHG",  # 法国ETF
        "513310.XSHG",  # 中韩半导体ETF
        "513730.XSHG",  # 东南亚ETF
        # 香港ETF
        "159920.XSHE",  # 恒生ETF
        # 指数ETF
        "510300.XSHG",  # 沪深300ETF
        "510500.XSHG",  # 中证500ETF
        "510050.XSHG",  # 上证50ETF
        "159915.XSHE",  # 创业板ETF
        "588080.XSHG",  # 科创50
        "512100.XSHG",  # 中证1000ETF
        "563360.XSHG",  # A500-ETF
        # 风格ETF
        "512890.XSHG",  # 红利低波ETF
        "159967.XSHE",  # 创业板成长ETF
        "512040.XSHG",  # 价值ETF
        "159201.XSHE",  # 自由现金流ETF
        # 债券ETF
        "511380.XSHG",  # 可转债ETF
        "511010.XSHG",  # 国债ETF
        "511220.XSHG",  # 城投债ETF
    ]

    # ---------- 核心参数 ----------
    g.lookback_days = 25               # 动量计算周期
    g.holdings_num = 1                 # 候选数量
    g.defensive_etf = "511880.XSHG"    # 防御ETF（货币基金）
    g.min_money = 5000                 # 最小交易金额

    # ---------- 盈利保护参数 ----------
    g.enable_profit_protection = True                      # 盈利保护开关
    g.profit_protection_lookback = 1                       # 盈利保护回看周期（天）
    g.profit_protection_threshold = 0.05                   # 盈利保护回撤阈值（5%）
    g.profit_protection_check_times = ['11:00']            # 盈利保护检查时间点（可添加多个，如['09:45','11:00','13:30']）

    g.loss = 0.97                      # 近3日单日跌幅阈值（排除）

    g.min_score_threshold = 0          # 最低得分
    g.max_score_threshold = 100.0      # 最高得分

    # ---------- 成交量过滤 ----------
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 2
    g.volume_return_limit = 1          # 年化收益>100%时启用放量过滤

    # ---------- 短期动量过滤 ----------
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0

    # ---------- 溢价率过滤 ----------
    g.enable_premium_filter = True      # 是否启用溢价率过滤
    g.premium_threshold = 0.20          # 溢价率阈值（20%）

    # ---------- 净值回撤保护参数（V1.0新增） ----------
    g.enable_drawdown_protection = True   # 净值回撤保护开关
    g.drawdown_threshold = 0.10           # 回撤阈值（相对历史最高净值，10%）
    g.drawdown_cooldown_days = 5          # 触发后最短空仓交易日数（下限）
    g.high_watermark = None               # 实际净值历史最高（运行时初始化）
    g.cooldown_days_left = 0              # 已空仓交易日数（0=非空仓期）
    g.cooldown_date = None                # 上一次递增空仓天数的日期（防止同一交易日重复计数）
    # 模拟净值（假设一直持仓、未空仓）——用于判断空仓期是否可提前结束
    g.paper_value = None                  # 模拟净值（空仓触发时初始化）
    g.paper_high_watermark = None         # 模拟净值历史最高
    g.paper_position = None               # 模拟当前持有的ETF（每日跟真实换仓）
    g.paper_date = None                   # 上一次更新模拟净值的日期（防止重复）

    # ---------- 随机买卖时点参数（V1.8新增） ----------
    g.random_trade_enable = True        # 随机时点开关
    g.random_time_window = [9, 30, 14, 45]  # 随机时点可选区间 [起始时, 起始分, 结束时, 结束分]，默认全天 9:30-14:45
    g.fallback_time = '14:45'           # 保底执行时间（到点未触发则强制下单）
    g.trigger_time = None               # 当日随机生成的买卖触发基准时间（字符串，如'10:35'）
    g.trade_executed = False            # 当日是否已执行买卖（保证每日只执行一轮）
    g.last_minute = -1                  # 上一次轮询的分钟数（去重）

    # ---------- 运行时变量 ----------
    g.rankings_cache = {'date': None, 'data': None}   # 排名缓存

    # ---------- 交易调度 ----------
    run_daily(check_positions, time='09:10')
    run_daily(generate_trade_time, time='09:15')   # 开盘前生成随机买卖时点
    # 每5分钟轮询买卖（分钟级回测下 every_bar 每分钟触发，函数内过滤到5分钟整数倍）
    run_daily(intraday_trade_check, time='every_bar')
    # 收盘后检测净值回撤（更新高水位 + 触发/递减空仓期）
    run_daily(drawdown_protection_check, time='15:30')

    # 动态注册盈利保护检查时间点
    for check_time in g.profit_protection_check_times:
        run_daily(profit_protection_check, time=check_time)
        log.info(f"已注册盈利保护检查时间：{check_time}")

    log.info(f"策略初始化完成：ETF池{len(g.etf_pool)}只，动量周期{g.lookback_days}天，持仓{g.holdings_num}只")
    log.info(f"盈利保护开关：{'开启' if g.enable_profit_protection else '关闭'}，回看周期{g.profit_protection_lookback}天，回撤阈值{g.profit_protection_threshold*100:.0f}%")
    if g.enable_premium_filter:
        log.info(f"溢价率过滤已启用，阈值：{g.premium_threshold*100:.0f}%")
    else:
        log.info("溢价率过滤未启用")
    if g.random_trade_enable:
        log.info(f"随机买卖时点已启用，随机区间 {g.random_time_window[0]:02d}:{g.random_time_window[1]:02d} - {g.random_time_window[2]:02d}:{g.random_time_window[3]:02d}，保底时间 {g.fallback_time}")
    if g.enable_drawdown_protection:
        log.info(f"净值回撤保护已启用：回撤超{g.drawdown_threshold*100:.0f}%空仓{g.drawdown_cooldown_days}个交易日")
    log.info("========== 策略初始化完成 ==========")


# ==================== 随机买卖时点生成 ====================
def generate_trade_time(context):
    """
    开盘前（09:15）随机生成当日买卖触发基准时间。
    在全天交易时段内（g.random_time_window）随机取一个 5 分钟整数倍的时间点。
    时间点落在 9:30-11:30 或 13:00-15:00 之间（跳过午休），作为当日唯一触发基准。
    """
    if not g.random_trade_enable:
        g.trigger_time = g.fallback_time   # 关闭随机时，退化为保底时间
        log.info(f"随机时点关闭，当日买卖时点固定为 {g.fallback_time}")
        return

    sh, sm = g.random_time_window[0], g.random_time_window[1]
    eh, em = g.random_time_window[2], g.random_time_window[3]

    # 生成所有可选时间点（5分钟整数倍，且落在连续竞价时段，跳过午休 11:30-13:00）
    candidates = []
    total_start = sh * 60 + sm
    total_end = eh * 60 + em
    # 交易时段边界（分钟）：9:30=570, 11:30=690, 13:00=780, 15:00=900
    sessions = [(570, 690), (780, 900)]   # (起始分钟, 结束分钟)，右端不包含
    for t in range(total_start, total_end + 1, 5):
        in_session = any(s <= t < e for s, e in sessions)
        if in_session:
            candidates.append(t)

    if not candidates:
        g.trigger_time = g.fallback_time
        log.warning("随机时点区间内无可选交易时间，退化为保底时间")
        return

    chosen = random.choice(candidates)
    hh, mm = divmod(chosen, 60)
    g.trigger_time = f"{hh:02d}:{mm:02d}"
    g.trade_executed = False
    g.last_minute = -1
    log.info(f"🎲 当日随机买卖触发时间：{g.trigger_time}（到点即执行，保底 {g.fallback_time}）")


# ==================== 盘中每5分钟买卖轮询 ====================
def intraday_trade_check(context):
    """
    每5分钟轮询一次（分钟级回测下每分钟触发，此处过滤到5分钟整数倍）。
    逻辑：
      1. 到达随机触发时间之前：不动作
      2. 到达随机触发时间：直接执行买卖（保留原有日频动量信号，无额外择时）
      3. 到达保底时间（g.fallback_time）后仍未成交：强制执行
    """
    now = context.current_dt
    now_str = now.strftime('%H:%M')

    # 只在连续竞价时段内处理（跳过午休）
    hm = now.hour * 60 + now.minute
    in_session = (570 <= hm < 690) or (780 <= hm < 900)
    if not in_session:
        return

    # 去重：同一分钟内只处理一次（every_bar 每分钟触发一次，无需再按5分钟过滤，
    # 但保留此判断以兼容未来可能的调整）
    if now.minute == g.last_minute:
        return
    g.last_minute = now.minute

    # 已执行过则不再重复
    if g.trade_executed:
        return

    # 未到随机触发时间，且未到保底时间：不动作
    trigger_reached = g.trigger_time is not None and now_str >= g.trigger_time
    fallback_reached = now_str >= g.fallback_time
    if not trigger_reached and not fallback_reached:
        return

    # 到达随机触发时间或保底时间 → 执行买卖
    if fallback_reached:
        log.info(f"⏰ 已到保底时间 {g.fallback_time}，执行买卖")
    else:
        log.info(f"🎯 到达随机时点 {g.trigger_time}，执行买卖")
    g.trade_executed = True
    execute_trade(context)


# ==================== 净值回撤保护 ====================
def drawdown_protection_check(context):
    """
    收盘后（15:30）运行：双净值回撤保护。
    实际净值：真实账户，空仓期冻结。
    模拟净值（paper）：假设一直按动量信号持仓、未空仓，空仓期仍每日虚拟换仓跟踪。
    逻辑：
      1. 更新实际净值高水位
      2. 非空仓期：检测实际净值回撤，超阈值则触发空仓（初始化模拟净值）
      3. 空仓期：每日更新模拟净值（跟真实换仓），并递增已空仓天数
      4. 空仓期：满足「已空仓>=下限 且 模拟净值回撤收窄到阈值内」则恢复交易
    """
    if not g.enable_drawdown_protection:
        return

    total_value = context.portfolio.total_value
    today = context.current_dt.date()

    # 初始化实际净值高水位
    if g.high_watermark is None:
        g.high_watermark = total_value

    # 更新实际净值高水位
    if total_value > g.high_watermark:
        g.high_watermark = total_value

    # ---------- 空仓期处理 ----------
    if g.cooldown_days_left > 0:
        # 每日递增已空仓天数（每个交易日一次）
        if g.cooldown_date != today:
            g.cooldown_days_left += 1
            g.cooldown_date = today

        # 每日更新模拟净值（跟真实换仓，每个交易日一次）
        if g.paper_date != today:
            update_paper_value(context)
            g.paper_date = today

        # 判断是否可恢复：已空仓>=下限 且 模拟净值回撤收窄到阈值内
        paper_drawdown = 1 - g.paper_value / g.paper_high_watermark if g.paper_high_watermark > 0 else 0
        if g.cooldown_days_left >= g.drawdown_cooldown_days and paper_drawdown <= g.drawdown_threshold:
            log.info(f"🛡️ 空仓保护结束：已空仓{g.cooldown_days_left}个交易日，模拟净值回撤{paper_drawdown*100:.2f}%已收窄到阈值内，恢复正常交易")
            g.cooldown_days_left = 0
            g.cooldown_date = None
            g.paper_value = None
            g.paper_high_watermark = None
            g.paper_position = None
            g.paper_date = None
        else:
            log.info(f"🛡️ 净值回撤保护空仓中（已{g.cooldown_days_left}个交易日），模拟净值回撤{paper_drawdown*100:.2f}%")
        return

    # ---------- 非空仓期：检测触发 ----------
    drawdown = 1 - total_value / g.high_watermark if g.high_watermark > 0 else 0
    if drawdown > g.drawdown_threshold:
        # 触发空仓，初始化模拟净值（等于当前实际净值，模拟账户从这里开始假设持仓）
        g.cooldown_days_left = 1
        g.cooldown_date = today
        g.paper_value = total_value
        g.paper_high_watermark = total_value
        g.paper_position = None
        g.paper_date = today
        log.info(f"🔴 净值回撤{drawdown*100:.2f}% > {g.drawdown_threshold*100:.0f}%，触发空仓保护（最短{g.drawdown_cooldown_days}个交易日，模拟净值恢复后提前结束）")


def update_paper_value(context):
    """
    更新模拟净值：空仓期内假设一直按动量信号持仓，每日虚拟换仓到排名第一的目标ETF。
    用当日目标ETF的日收益率（当日收盘/昨收 - 1）复利更新模拟净值。
    """
    if g.paper_value is None:
        return

    # 取当日排名第一的目标ETF（与真实策略同信号）
    ranked = get_cached_rankings(context)
    target_etf = None
    for m in ranked[:g.holdings_num]:
        if m['score'] >= g.min_score_threshold:
            target_etf = m['etf']
            break
    if target_etf is None and check_defensive_etf_available(context):
        target_etf = g.defensive_etf

    if target_etf is None:
        # 无目标ETF，模拟账户持币，净值不变
        return

    # 获取该ETF当日收益率（当日收盘 / 昨收 - 1）
    try:
        prices = attribute_history(target_etf, 2, '1d', ['close'])
        if prices.empty or len(prices) < 2:
            return
        prev_close = prices['close'].iloc[-2]
        cur_close = prices['close'].iloc[-1]
        if prev_close <= 0:
            return
        daily_return = cur_close / prev_close - 1
        g.paper_value *= (1 + daily_return)
        # 更新模拟净值高水位
        if g.paper_value > g.paper_high_watermark:
            g.paper_high_watermark = g.paper_value
    except Exception as e:
        log.warning(f"模拟净值更新失败 {target_etf}: {e}")


# ==================== 统一买卖执行入口 ====================
def execute_trade(context):
    """
    统一的买卖执行入口：先卖出不在目标列表的持仓，再等权买入/调仓目标ETF。
    """
    log.info("========== 执行买卖操作开始 ==========")

    # 空仓期：清仓所有持仓，不买入，直接返回
    if g.enable_drawdown_protection and g.cooldown_days_left > 0:
        log.info(f"🛡️ 净值回撤保护空仓中（已{g.cooldown_days_left}个交易日），清仓不买入")
        for sec in list(context.portfolio.positions.keys()):
            if sec not in g.etf_pool and sec != g.defensive_etf:
                continue
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                if smart_order_target_value(sec, 0, context):
                    log.info(f"📤 空仓清仓卖出：{sec} {get_name(sec)}")
        log.info("========== 执行买卖操作完成（空仓） ==========")
        return

    ranked = get_cached_rankings(context)

    # ---------- 确定目标ETF列表 ----------
    target_etfs = []
    for m in ranked[:g.holdings_num]:
        if m['score'] >= g.min_score_threshold:
            target_etfs.append(m['etf'])

    if not target_etfs:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
            log.info(f"🛡️ 进入防御模式，选择防御ETF：{g.defensive_etf} {get_name(g.defensive_etf)}")
        else:
            # 无目标且防御不可用，仅清仓现有持仓
            log.info("💤 无目标ETF且防御不可用，清仓现有持仓")
            for sec in list(context.portfolio.positions.keys()):
                if sec not in g.etf_pool and sec != g.defensive_etf:
                    continue
                pos = context.portfolio.positions[sec]
                if pos.total_amount > 0:
                    if smart_order_target_value(sec, 0, context):
                        log.info(f"📤 清仓卖出：{sec} {get_name(sec)}")
            log.info("========== 执行买卖操作完成 ==========")
            return

    target_set = set(target_etfs)

    # ---------- 先卖出不在目标列表的持仓 ----------
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        if sec not in target_set:
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                if smart_order_target_value(sec, 0, context):
                    log.info(f"📤 卖出不在目标的持仓：{sec} {get_name(sec)}")

    # ---------- 再等权买入/调仓目标ETF ----------
    total_val = context.portfolio.total_value
    target_per_etf = total_val / len(target_etfs)

    for etf in target_etfs:
        current_val = 0
        if etf in context.portfolio.positions:
            pos = context.portfolio.positions[etf]
            if pos.total_amount > 0:
                current_val = pos.total_amount * pos.price
        if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
            if smart_order_target_value(etf, target_per_etf, context):
                action = "买入" if current_val < target_per_etf else "调仓"
                log.info(f"📦 {action}：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}")

    log.info("========== 执行买卖操作完成 ==========")


# ==================== 盈利保护独立检查函数 ====================
def profit_protection_check(context):
    """
    独立执行的盈利保护检查函数
    遍历所有持仓，若触发盈利保护则卖出
    """
    if not g.enable_profit_protection:
        log.debug("盈利保护模块已关闭，跳过检查")
        return

    log.info("========== 盈利保护独立检查开始 ==========")
    for sec in list(context.portfolio.positions.keys()):
        # 只处理ETF池中的标的和防御ETF
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if check_profit_protection(sec, context):
                if smart_order_target_value(sec, 0, context):
                    log.info(f"🛡️ 盈利保护卖出（独立检查）：{sec} {get_name(sec)}")
    log.info("========== 盈利保护独立检查完成 ==========")


# ==================== 盈利保护检查函数（核心逻辑） ====================
def check_profit_protection(security, context):
    """
    检查是否触发盈利保护（从最近N日最高点回撤超过阈值）
    N 和阈值取自 g.profit_protection_lookback / g.profit_protection_threshold
    返回:
        bool: True表示应触发盈利保护（卖出/排除），False表示安全
    """
    # 若开关关闭，直接返回安全
    if not g.enable_profit_protection:
        return False

    lookback = g.profit_protection_lookback
    threshold = g.profit_protection_threshold

    # 获取最近N日的最高价（不包括当天）
    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback:
        log.debug(f"{security} {get_name(security)} 历史数据不足{lookback}天，无法检查盈利保护")
        return False

    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price

    if current_price <= max_high * (1 - threshold):
        log.info(f"🔻 {security} {get_name(security)} 触发盈利保护：当前价{current_price:.3f}，最近{lookback}日最高{max_high:.3f}，回撤{(1 - current_price/max_high)*100:.2f}% > {threshold*100:.0f}%")
        return True
    else:
        return False


# ==================== 溢价率获取函数 ====================
def get_premium_rate(code, date, max_back_days=5):
    """
    获取指定日期的溢价率，若当天无净值则向前搜索最多max_back_days个交易日
    参数:
        code: 基金代码
        date: 日期，datetime.date 对象
        max_back_days: 最大回退天数
    返回:
        premium_rate: 溢价率（小数形式），None 表示获取失败
        price: 场内交易价格
        net_value: 基金净值
    """
    # 获取场内交易价格（给定日期）
    price_data = get_price(
        code,
        start_date=date,
        end_date=date,
        frequency='daily',
        fields=['close']
    )
    if price_data.empty:
        log.debug(f"{date} {code} 无交易价格数据")
        return None, None, None
    price = price_data['close'].iloc[0]

    # 获取净值，先尝试指定日期，若失败则向前搜索交易日
    net_value = None
    used_date = date
    # 获取从date往前max_back_days个交易日的列表（扩大范围确保包含足够交易日）
    start_date = date - datetime.timedelta(days=max_back_days*2)
    trade_days = get_trade_days(start_date=start_date, end_date=date)
    # 转换为 Python date 对象
    trade_days = [pd.to_datetime(d).date() for d in trade_days]
    # 倒序搜索，从date开始向前
    for dt in reversed(trade_days):
        if dt > date:  # 忽略大于date的日期
            continue
        # 尝试获取净值的两种方式
        net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            used_date = dt
            break
        # 备用方法
        try:
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == code,
                finance.FUND_NET_VALUE.day == dt
            )
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
                used_date = dt
                break
        except:
            continue

    if net_value is None:
        log.debug(f"{code} 在{date}及前{max_back_days}个交易日均无净值数据")
        return None, None, None

    premium_rate = (price - net_value) / net_value
    if used_date != date:
        log.debug(f"{code} 使用{used_date}的净值{net_value:.4f}代替{date}的净值计算溢价率")
    return premium_rate, price, net_value


# ==================== 核心计算模块 ====================
def get_cached_rankings(context):
    """获取缓存的ETF排名，保证同一交易日内多次调用结果一致"""
    today = context.current_dt.date()
    if g.rankings_cache['date'] != today:
        log.info("重新计算ETF排名...")
        ranked = get_ranked_etfs(context)
        g.rankings_cache = {'date': today, 'data': ranked}
    else:
        log.debug("使用缓存的ETF排名")
    return g.rankings_cache['data']


def get_ranked_etfs(context):
    """
    计算所有ETF的动量得分，应用所有过滤条件，返回按得分降序的列表
    """
    etf_metrics = []
    for etf in g.etf_pool:
        # 停牌过滤
        if get_current_data()[etf].paused:
            log.debug(f"{etf} {get_name(etf)} 停牌，跳过")
            continue

        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            # 得分范围过滤
            if g.min_score_threshold < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)
            else:
                log.debug(f"{etf} {metrics['etf_name']} 得分{metrics['score']:.2f}超出阈值，过滤")

    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def calculate_momentum_metrics(context, etf):
    """
    计算单只ETF的动量指标，应用所有过滤条件
    返回字典：etf, etf_name, annualized_returns, r_squared, score, current_price, short_annualized
    """
    try:
        name = get_name(etf)
        # 获取足够历史数据
        lookback = max(g.lookback_days, g.short_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < g.lookback_days:
            log.debug(f"{etf} {name} 历史数据不足{len(prices)}天，跳过")
            return None

        # 价格序列（含当天）
        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        # ===== 1. 盈利保护检查（排除） =====
        if check_profit_protection(etf, context):
            log.info(f"🚫 {etf} {name} 触发盈利保护，从排名中排除")
            return None

        # ===== 2. 溢价率过滤（提前至排名阶段，获取失败则跳过过滤）=====
        if g.enable_premium_filter:
            # 获取前一个交易日（用于净值数据）
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = get_premium_rate(etf, prev_date)
            if premium is not None:
                if premium > g.premium_threshold:
                    log.info(f"🚫 {etf} {name} 溢价率{premium*100:.2f}% > {g.premium_threshold*100:.0f}%，从排名中排除")
                    return None
            else:
                # 无法获取溢价率，跳过该过滤条件（不过滤）
                log.debug(f"{etf} {name} 无法获取溢价率，跳过溢价率过滤")

        # ===== 3. 成交量过滤（排除） =====
        if g.enable_volume_check:
            vol_ratio = get_volume_ratio(context, etf)
            if vol_ratio is not None:
                slope, _, _, _ = fit_log_slope(price_series, g.lookback_days)
                annualized = math.exp(slope * 250) - 1
                if annualized > g.volume_return_limit:
                    log.info(f"📉 {etf} {name} 成交量放量{vol_ratio:.1f}倍，且年化{annualized*100:.1f}% > 阈值{g.volume_return_limit*100:.1f}%，过滤")
                    return None

        # ===== 4. 短期动量过滤（排除） =====
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = 0

        if g.use_short_momentum_filter and short_annualized < g.short_momentum_threshold:
            log.debug(f"{etf} {name} 短期动量{short_annualized*100:.1f}% < 阈值{g.short_momentum_threshold*100:.1f}%，过滤")
            return None

        # ===== 5. 长期动量计算（得分） =====
        slope, intercept, weights, y = fit_log_slope(price_series, g.lookback_days)
        annualized_returns = math.exp(slope * 250) - 1

        # R²（趋势稳定性）
        x = np.arange(len(y))
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        score = annualized_returns * r_squared

        # ===== 6. 近3日单日跌幅过滤（排除） =====
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if min(day1, day2, day3) < g.loss:
                log.info(f"⚠️ {etf} {name} 近3日有单日跌幅超{(1-g.loss)*100:.1f}%，直接排除")
                return None

        return {
            'etf': etf,
            'etf_name': name,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'current_price': current_price,
            'short_annualized': short_annualized,
        }

    except Exception as e:
        log.warning(f"计算{etf} {get_name(etf)}时出错: {e}")
        return None


def fit_log_slope(price_series, lookback_days):
    """对最近 lookback_days 的 log 价格做加权线性拟合，返回 (slope, intercept, weights, y)"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    return slope, intercept, weights, y


def get_volume_ratio(context, security):
    """计算当日成交量与过去N日均量的比值，若超过阈值则返回比值，否则None"""
    lookback = g.volume_lookback
    threshold = g.volume_threshold
    try:
        name = get_name(security)
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()

        # 获取当日分钟成交量累计
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        if ratio > threshold:
            log.debug(f"{security} {name} 成交量比{ratio:.2f} > {threshold}")
            return ratio
        return None
    except Exception as e:
        log.warning(f"成交量计算失败 {security}: {e}")
        return None


# ==================== 持仓检查 ====================
def check_positions(context):
    """每日开盘检查持仓状态，仅用于日志"""
    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")


# ==================== 辅助函数 ====================
def get_name(security):
    """获取证券名称，带异常处理"""
    try:
        return get_current_data()[security].name
    except:
        return "未知"


def check_defensive_etf_available(context):
    """检查防御ETF是否可交易（未停牌、未涨跌停）"""
    data = get_current_data()
    etf = g.defensive_etf
    if data[etf].paused:
        log.debug(f"防御ETF {etf} {get_name(etf)} 停牌")
        return False
    if data[etf].last_price >= data[etf].high_limit:
        log.debug(f"防御ETF {etf} {get_name(etf)} 涨停")
        return False
    if data[etf].last_price <= data[etf].low_limit:
        log.debug(f"防御ETF {etf} {get_name(etf)} 跌停")
        return False
    return True


def smart_order_target_value(security, target_value, context):
    """
    智能下单：根据目标市值调整持仓，处理停牌、涨跌停、最小交易金额、T+1
    """
    data = get_current_data()
    name = get_name(security)

    if data[security].paused:
        log.info(f"{security} {name} 停牌，跳过")
        return False

    price = data[security].last_price
    if price == 0:
        log.info(f"{security} {name} 当前价格0，跳过")
        return False

    target_amount = int(target_value / price)
    # 按100股整数倍调整
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount

    # 根据交易方向检查涨跌停
    if diff > 0:  # 买入
        if data[security].last_price >= data[security].high_limit:
            log.info(f"{security} {name} 涨停，跳过买入")
            return False
    elif diff < 0:  # 卖出
        if data[security].last_price <= data[security].low_limit:
            log.info(f"{security} {name} 跌停，跳过卖出")
            return False

    # 最小交易金额检查
    trade_val = abs(diff) * price
    if 0 < trade_val < g.min_money:
        log.info(f"{security} {name} 交易金额{trade_val:.2f} < {g.min_money}，跳过")
        return False

    # T+1处理
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            log.info(f"{security} {name} 当天买入不可卖出")
            return False
        diff = -min(abs(diff), closeable)

    if diff != 0:
        order_result = order(security, diff)
        if order_result:
            log.info(f"{'📥 买入' if diff>0 else '📤 卖出'} {security} {name} 数量{abs(diff)} 价格{price:.3f}")
            return True
        else:
            log.warning(f"下单失败: {security} {name} 数量{diff}")
            return False
    return False
