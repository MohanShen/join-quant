# ============================================================================
# q-e9-avoid-off 变体：七星高照 候选 d9dafab2 —— 关闭「走弱期回避A股」开关
#
# 【唯一的改动】第 181 行 g.enable_avoid_a_share = True -> False
#   即：行情判断照常运行并记录，但走弱期不再把池切到「海外+商品」，始终使用完整池。
#
# 【刻意不碰】池（29 只）、排序、滤波栈、分钟级回撤保护（由 is_a_share_weak 独立管辖）、
#   得分阈值、溢价过滤、流动性过滤、成本块 —— 全部逐字不动。
#
# 【对照】台账行 d9dafab2@epoch9: objective 1.2451 / sharpe 4.40 / annual 137.84 / maxDD 13.33
# 【预注册】|Δobjective| < 0.10 => 该部件在 2024 近乎惰性（装饰，不是收益来源）
#           Δobjective >= +0.05 => 净负部件，更简单的书更好
#           Δobjective <= -0.10 => 净正部件（换资产形式的择时），须重开 趋势择时 edge 状态
# ============================================================================
# Clone from JoinQuant
# postId: d9dafab2dbfbfd7aebb6c696467c3c5c
# backtestId: fa22956439cb2de67fdd2910d83a6d02
# title: 该相信癌股还是该相信海外？【思考再三，决定将这压轴策略奉上】

import numpy as np
import math
import datetime
import pandas as pd
import time
from functools import wraps
from jqdata import *

# ==================== 物理时间监控装饰器 ====================
def time_monitor(func_name=None):
    """时间监控装饰器，记录函数执行的真实物理时间"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_real = datetime.datetime.now()

            log.info(f"⏱️ [{func_name or func.__name__}] 开始执行 - 真实时间: {start_real.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                end_real = datetime.datetime.now()
                elapsed = end_time - start_time

                log.info(f"✅ [{func_name or func.__name__}] 执行完成 - 耗时: {elapsed*1000:.2f}ms | 真实时间: {end_real.strftime('%H:%M:%S')}")

                if elapsed > 0.95:
                    log.warning(f"⚠️ [{func_name or func.__name__}] 执行耗时过长: {elapsed*1000:.2f}ms")

                return result
            except Exception as e:
                end_time = time.time()
                elapsed = end_time - start_time
                log.error(f"❌ [{func_name or func.__name__}] 执行异常 - 耗时: {elapsed*1000:.2f}ms | 错误: {str(e)[:100]}")
                raise
        return wrapper
    return decorator

# ==================== 辅助函数：获取真实时间 ====================
def get_real_time():
    return datetime.datetime.now().strftime('%H:%M:%S')

# ==================== 初始化模块 ====================
def initialize(context):
    """
    初始化函数：设置交易参数、ETF池、核心参数、调度任务
    """
    # ---------- 交易设置 ----------
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.001), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0002,
            close_commission=0.0002,
            close_today_commission=0,
            min_commission=0.2,
        ),
        type="fund",
    )
    set_benchmark("000300.XSHG")

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    log.info("🚀 ========== 策略初始化开始 ==========")

    # ---------- ETF池 ----------
    g.etf_pool_bak = [
        "518880.XSHG",   # 黄金ETF
        "159985.XSHE",   # 豆粕ETF
        "501018.XSHG",   # 南方原油
        "161226.XSHE",   # 白银LOF
        "513100.XSHG",   # 纳指ETF
        "159949.XSHE",   # 创业50ETF
        "511220.XSHG",   # 城投债ETF
    ]

    # ==========按类别分类ETF ==========
    # 海外ETF（走弱期可交易）
    g.overseas_etf_pool = [
        "513100.XSHG",  # 纳指ETF
        "159509.XSHE",  # 纳指科技ETF
        "513290.XSHG",  # 纳指生物ETF
        "513500.XSHG",  # 标普500ETF
        "159529.XSHE",  # 标普消费
        "513400.XSHG",  # 道琼斯ETF
        "513520.XSHG",  # 日经225ETF
        "513030.XSHG",  # 德国30ETF
        "513080.XSHG",  # 法国ETF
        "513310.XSHG",  # 中韩半导体ETF
        "501225.XSHG",  # 全球芯片
        "513730.XSHG",  # 东南亚ETF
        "159792.XSHE",  # 港股互联ETF
        "513130.XSHG",  # 恒生科技
        "513050.XSHG",  # 中概互联网ETF
        "159920.XSHE",  # 恒生ETF
        "513690.XSHG",  # 港股红利
        # 债券ETF
        "511380.XSHG",  # 可转债ETF
        "511010.XSHG",  # 国债ETF
        "511220.XSHG",  # 城投债ETF
    ]

    # 商品ETF（走弱期可交易）
    g.commodity_etf_pool = [
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色金属ETF
        "159985.XSHE",  # 豆粕ETF
        "501018.XSHG",  # 南方原油
        '161226.XSHE',  # 白银LOF
        "159981.XSHE",  # 能源化工ETF
        "512400.XSHG",  # 工业有色ETF
    ]

    # A股ETF（走弱期回避）
    g.domestic_etf_pool = [
        # 指数ETF
        "510300.XSHG",  # 沪深300ETF
        "563360.XSHG",  # A500-ETF
    ]

    # 完整ETF池（初始化时合并）
    g.etf_pool = g.overseas_etf_pool + g.commodity_etf_pool + g.domestic_etf_pool

    # ---------- 核心参数 ----------
    g.lookback_days = 25               # 动量计算周期
    g.holdings_num = 1                 # 候选数量
    g.defensive_etf = '511010.XSHG'    # 避险资产：10年国债ETF
    g.min_money = 5000                 # 最小交易金额

    # ---------- 盈利保护参数 ----------
    g.enable_profit_protection = True                      # 盈利保护开关
    g.profit_protection_lookback = 1                       # 盈利保护回看周期（天）
    g.profit_protection_threshold = 0.05                   # 盈利保护回撤阈值（5%）

    # 盈利保护检查时间点
    g.profit_protection_check_times = ['11:00']


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

    # ========== 分钟级当日回撤保护（V2.1：开关自动跟随行情状态） ==========
    g.intraday_drawdown_threshold = 0.02            # 当日回撤阈值（2%）
    # 注意：不再使用 g.enable_intraday_drawdown，改为在 handle_data 中动态判断
    # ================================================================

    # ==========  A股行情判断 ==========
    g.enable_regime_switch = True                    # 行情判断开关
    g.weak_period_ma_lookback = 10                   # 10日均线
    g.weak_period_max_days = 20                      # 走弱期最长持续20个交易日
    g.is_a_share_weak = False                        # 当前是否走弱期
    g.weak_period_counter = 0                        # 走弱期天数计数器
    # ==========  独立手动开关 ==========
    g.enable_avoid_a_share = False                   # q-e9-avoid-off: 消融——走弱期不回避A股
    g.enable_intraday_drawdown = True                # 分钟级回撤保护独立开关（关闭则不触发）
    # ==========================================
    g.regime_indexes = {                             # 监测指数
        '沪深300': '000300.XSHG',
        '深证综指': '399101.XSHE',
        '创业板指': '399006.XSHE',
        '中证A500': '000510.XSHG',
    }
    # ============================================

    # ---------- 运行时变量 ----------
    g.rankings_cache = {'date': None, 'data': None}   # 排名缓存
    g.target_etfs_cache = {'date': None, 'data': None}  
    g.drawdown_selled_today = set()                    # 当日因回撤/盈利保护卖出的标的（禁止日内买回）

    # 盘后总结需要的变量
    g.buy_date = {}                                    # 记录买入日期
    g.trade_log = {'sell_records': []}                 # 记录当日卖出

    # ---------- 交易调度 ----------
    run_daily(check_positions, time='09:10')
    run_daily(regime_check, time='09:40')              # 行情判断
    run_daily(etf_sell_trade, time='13:11')
    run_daily(etf_buy_trade, time='13:12')
    run_daily(daily_summary_report, time='15:05')      # 盘后总结

    # 动态注册盈利保护检查时间点
    for check_time in g.profit_protection_check_times:
        run_daily(profit_protection_check, time=check_time)
        log.info(f"📅 已注册盈利保护检查时间：{check_time}")

    # V2.2 日志
    if g.enable_regime_switch:
        log.info(f"🌍 A股行情判断已启用，走弱期最长{g.weak_period_max_days}日")
        if g.enable_avoid_a_share:
            log.info(f"🔄 走弱期回避A股开关：ON（走弱期自动回避A股ETF）")
        else:
            log.info(f"⚠️ 走弱期回避A股开关：OFF（走弱期仍交易A股ETF）")
        if g.enable_intraday_drawdown:
            log.info(f"🛡️ 分钟级回撤保护开关：ON（走弱期自动启用）")
        else:
            log.info(f"⭕ 分钟级回撤保护开关：OFF（不触发）")
    else:
        log.info("⚠️ A股行情判断未启用")

    log.info(f"📋 策略初始化完成：ETF池{len(g.etf_pool)}只（海外{len(g.overseas_etf_pool)}只+商品{len(g.commodity_etf_pool)}只+A股{len(g.domestic_etf_pool)}只）")
    log.info(f"📈 盈利保护：{'开' if g.enable_profit_protection else '关'}，回撤{g.profit_protection_threshold*100:.0f}%")
    if g.enable_premium_filter:
        log.info(f"💰 溢价率过滤已启用，阈值：{g.premium_threshold*100:.0f}%")
    else:
        log.info("⚠️ 溢价率过滤未启用")

    log.info("🎉 ========== 策略初始化完成 ==========")


# ==================== 开盘检查模块 ====================
def check_positions(context):
    """每日开盘检查持仓状态"""

    # 日期标记
    log.info(f"\n{'='*22}🐂🧨🧨🧨🧨🧨{context.current_dt.strftime('%Y-%m-%d')}📌策略运行开始📌一路长红🧨🧨🧨🧨🧨🐂{'='*22}")

    g.drawdown_selled_today = set()                    # 清空当日回撤卖出缓存
    g.target_etfs_cache = {'date': None, 'data': None}
    g.trade_log['sell_records'] = []
    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")

# ====================  行情判断模块 ====================
def regime_check(context):
    """每日 9:40 判断A股行情，决定是否允许交易A股ETF，同时自动控制分钟级回撤开关（受独立开关影响）"""

    log.info("🌍 ========== 行情判断开始 ==========")

    if not g.enable_regime_switch:
        g.is_a_share_weak = False
        return

    below_count, above_count = 0, 0
    detail = []
    for name, code in g.regime_indexes.items():
        try:
            df = attribute_history(code, g.weak_period_ma_lookback + 1, '1d', ['close'], skip_paused=False)
            if df.empty or len(df) < g.weak_period_ma_lookback:
                continue
            current_price = df['close'].iloc[-1]
            ma_val = df['close'].iloc[-g.weak_period_ma_lookback:].mean()
            if current_price < ma_val:
                below_count += 1
                detail.append(f"{name}↓")
            else:
                above_count += 1
                detail.append(f"{name}↑")
        except Exception as e:
            log.warning(f"⚠️ 指数{name}获取失败: {e}")

    old_state = g.is_a_share_weak

    if not g.is_a_share_weak:
        # 正常期 → 检查是否进入走弱期
        if below_count >= 3:
            g.is_a_share_weak = True
            g.weak_period_counter = 0
            log.info(f"🔴 进入走弱期 (跌破:{below_count} {detail})")
            # 根据独立开关决定日志
            if g.enable_avoid_a_share:
                log.info(f"   → 将回避A股ETF，仅交易海外+商品ETF")
            else:
                log.info(f"   → ⚠️ 回避A股开关已关闭，仍交易全市场ETF")
            if g.enable_intraday_drawdown:
                log.info(f"   → 🛡️ 分钟级回撤保护已启用（阈值{g.intraday_drawdown_threshold*100:.0f}%）")
            else:
                log.info(f"   → ⭕ 分钟级回撤保护已被独立开关关闭，不触发")
    else:
        # 走弱期 → 检查是否恢复
        g.weak_period_counter += 1
        if above_count >= 3:
            g.is_a_share_weak = False
            g.weak_period_counter = 0
            log.info(f"🟢 恢复正常期 (站上:{above_count} {detail})")
            if g.enable_avoid_a_share:
                log.info(f"   → 恢复交易A股ETF")
            else:
                log.info(f"   → 回避A股开关关闭，始终交易全市场")
            if g.enable_intraday_drawdown:
                log.info(f"   → 关闭分钟级回撤保护")
            else:
                log.info(f"   → 分钟级回撤保护独立开关已关闭，无变化")
        elif g.weak_period_counter >= g.weak_period_max_days:
            g.is_a_share_weak = False
            g.weak_period_counter = 0
            log.info(f"⏰ 走弱期满{g.weak_period_max_days}日强制退出，恢复正常期")
            if g.enable_avoid_a_share:
                log.info(f"   → 恢复交易A股ETF")
            else:
                log.info(f"   → 回避A股开关关闭，始终交易全市场")
            if g.enable_intraday_drawdown:
                log.info(f"   → 关闭分钟级回撤保护")
            else:
                log.info(f"   → 分钟级回撤保护独立开关已关闭，无变化")

    if old_state != g.is_a_share_weak:
        g.rankings_cache = {'date': None, 'data': None}
        g.target_etfs_cache = {'date': None, 'data': None}

    # 输出当前状态
    if g.enable_regime_switch:
        current_status = '🔴走弱期' if g.is_a_share_weak else '🟢正常期'
        avoid_status = '(回避A股)' if (g.is_a_share_weak and g.enable_avoid_a_share) else ('(不回避A股)' if g.is_a_share_weak else '')
        drawdown_status = '🛡️启用' if (g.is_a_share_weak and g.enable_intraday_drawdown) else ('⭕关闭' if (g.is_a_share_weak and not g.enable_intraday_drawdown) else '⭕关闭')
        log.info(f"📊 当前状态：{current_status}{avoid_status} 计数:{g.weak_period_counter}/{g.weak_period_max_days}")
        log.info(f"📊 分钟级回撤保护：{drawdown_status}（阈值{g.intraday_drawdown_threshold*100:.0f}%）")
    log.info("🌍 ========== 行情判断完成 ==========")


def is_intraday_drawdown_enabled():
    """判断分钟级回撤保护是否启用
    V2.2: 优先判断独立开关，关闭则不触发；开启则走弱期自动启用"""
    # 独立开关关闭 → 不触发
    if not g.enable_intraday_drawdown:
        return False
    # 行情判断未启用 → 不触发
    if not g.enable_regime_switch:
        return False
    # 走弱期自动启用
    return g.is_a_share_weak


def get_active_etf_pool():
    """根据行情状态获取当前可交易的ETF池
    V2.2: 若手动关闭回避开关(g.enable_avoid_a_share=False)，则无视行情判断，始终返回完整池"""
    # 手动关闭回避开关 → 走弱期也不回避A股
    if not g.enable_avoid_a_share:
        log.info(f"📊 【强制】A股回避开关已关闭，使用完整池({len(g.etf_pool)}只)")
        return g.etf_pool

    if g.is_a_share_weak:
        # 走弱期：只交易海外ETF + 商品ETF（回避A股）
        active_pool = g.overseas_etf_pool + g.commodity_etf_pool
        log.info(f"📊 【走弱期】使用海外+商品池({len(active_pool)}只)")
        return active_pool
    else:
        # 正常期：交易全部ETF
        log.info(f"📊 【正常期】使用完整池({len(g.etf_pool)}只)")
        return g.etf_pool


# ==================== 分钟级回测入口：每分钟执行一次 ====================
def handle_data(context, data):
    """当回测/实盘频率设为'分钟'时，此函数每分钟自动调用一次。
    V2.1: 只在走弱期执行回撤检查，正常期跳过
    V2.2: 受独立开关控制"""
    # V2.2: 动态判断是否启用（独立开关 + 走弱期）
    if not is_intraday_drawdown_enabled():
        return

    # 9:46 之后才执行检查
    current_time = context.current_dt.strftime('%H:%M')
    if current_time < '09:46':
        return

    intraday_drawdown_check(context)


# ==================== 分钟级当日回撤检查函数 ====================
def intraday_drawdown_check(context):
    """每分钟执行一次，检查所有持仓从当日盘中最高点的回撤。
    V2.1: 此函数仅在走弱期被调用
    V2.2: 受独立开关控制"""
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount == 0:
            continue
        # 跳过当日买入的ETF（避免刚买入就被日内回撤保护卖出）
        if g.buy_date.get(sec) == context.current_dt.date():
            continue

        try:
            df = get_price(sec, start_date=context.current_dt.date(), end_date=context.current_dt,
                           frequency='1m', fields=['high', 'close'], skip_paused=True, fq='pre')
            if df is None or df.empty:
                continue
            day_high = df['high'].max()
            current_price = df['close'].iloc[-1]
            if day_high <= 0:
                continue
            drawdown = (day_high - current_price) / day_high
            if drawdown >= g.intraday_drawdown_threshold:
                log.info(f"⚠️ 分钟级回撤触发：{sec} {get_name(sec)} 回撤{drawdown*100:.2f}%")
                if smart_order_target_value(sec, 0, context):
                    log.info(f"🧨 分钟级回撤卖出：{sec} {get_name(sec)}")
                    g.drawdown_selled_today.add(sec)
        except Exception as e:
            log.debug(f"分钟级回撤检查异常 {sec}: {e}")


# ==================== 盈利保护独立检查函数 ====================
@time_monitor(func_name="盈利保护检查")
def profit_protection_check(context):
    """独立执行的盈利保护检查函数"""
    if not g.enable_profit_protection:
        log.debug("盈利保护模块已关闭，跳过检查")
        return

    log.info("🛡️ ========== 盈利保护检查开始 ==========")
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if check_profit_protection(sec, context):
                if smart_order_target_value(sec, 0, context):
                    log.info(f"🛡️ 盈利保护卖出：{sec} {get_name(sec)}")
                    g.drawdown_selled_today.add(sec)
    log.info("🛡️ ========== 盈利保护检查完成 ==========")


# ==================== 盈利保护检查函数（核心逻辑） ====================
def check_profit_protection(security, context, lookback=None, threshold=None):
    """检查是否触发盈利保护（从最近N日最高点回撤超过阈值）"""
    if not g.enable_profit_protection:
        return False

    lookback = lookback or g.profit_protection_lookback
    threshold = threshold or g.profit_protection_threshold

    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback:
        return False

    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price

    if current_price <= max_high * (1 - threshold):
        log.info(f"🔻 盈利保护触发 {security} 回撤{(1-current_price/max_high)*100:.2f}% > {threshold*100:.0f}%")
        return True
    return False


# ==================== 溢价率获取函数 ====================
def get_premium_rate(code, date):
    """获取指定交易日的溢价率，自动向前寻找最近有净值的交易日"""
    price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
    if price_data.empty:
        log.debug(f"⚠️ {date} {code} 无交易价格数据")
        return None, None, None
    price = price_data['close'].iloc[0]

    net_value = None
    use_date = date
    max_search_days = 3
    found = False

    for _ in range(max_search_days):
        net_data = get_extras('unit_net_value', code, start_date=use_date, end_date=use_date, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            found = True
            break

        try:
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == code,
                finance.FUND_NET_VALUE.day == use_date
            )
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
                found = True
                break
        except:
            pass

        trade_days = get_trade_days(end_date=use_date, count=2)
        if len(trade_days) < 2:
            break
        use_date = trade_days[0]

    if not found or net_value is None:
        log.debug(f"⚠️ {code} 在{date}无净值数据")
        return None, None, None

    if use_date != date:
        log.debug(f"🔍 {code} 使用最近净值日期 {use_date}")

    premium_rate = (price - net_value) / net_value
    return premium_rate, price, net_value


# ==================== 核心计算模块 ====================
def get_cached_rankings(context):
    """获取缓存的ETF排名"""
    today = context.current_dt.date()
    if g.rankings_cache['date'] != today:
        log.info("📊 重新计算ETF排名...")
        ranked = get_ranked_etfs(context)
        g.rankings_cache = {'date': today, 'data': ranked}
    else:
        log.debug("🔍 使用缓存的ETF排名")
    return g.rankings_cache['data']


def get_ranked_etfs(context):
    """计算所有ETF的动量得分（V2.0：根据行情状态动态选择ETF池，V2.2受独立开关影响）"""
    active_pool = get_active_etf_pool()

    etf_metrics = []
    for etf in active_pool:
        if get_current_data()[etf].paused:
            log.debug(f"❌ {etf} {get_name(etf)} 停牌，跳过")
            continue

        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            if g.min_score_threshold < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)
            else:
                log.debug(f"❌ {etf} {metrics['etf_name']} 得分{metrics['score']:.2f}超出阈值，过滤")

    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def calculate_momentum_metrics(context, etf):
    """计算单只ETF的动量指标（无未来）"""
    try:
        name = get_name(etf)
        lookback = max(g.lookback_days, g.short_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < g.lookback_days:
            log.debug(f"🚫 {etf} {name} 历史数据不足{len(prices)}天，跳过")
            return None

        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        # 1. 盈利保护检查
        if check_profit_protection(etf, context):
            log.info(f"🚫 {etf} {name} 触发盈利保护，从排名中排除")
            return None

        # 2. 溢价率过滤
        if g.enable_premium_filter:
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = get_premium_rate(etf, prev_date)
            if premium is not None:
                if premium > g.premium_threshold:
                    log.info(f"🚫 {etf} {name} 溢价率{premium*100:.2f}% > 阈值，排除")
                    return None
            else:
                log.debug(f"🚫 {etf} {name} 无法获取{prev_date}的净值，排除")
                return None

        # 3. 成交量过滤
        if g.enable_volume_check:
            vol_ratio = get_volume_ratio(context, etf)
            if vol_ratio is not None:
                annualized = get_annualized_returns(price_series, g.lookback_days)
                if annualized > g.volume_return_limit:
                    log.info(f"📉 {etf} {name} 成交量放量，过滤")
                    return None

        # 4. 短期动量过滤
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = 0

        if g.use_short_momentum_filter and short_annualized < g.short_momentum_threshold:
            log.debug(f"❌ {etf} {name} 短期动量不足，过滤")
            return None

        # 5. 长期动量计算
        recent = price_series[-(g.lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1

        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        score = annualized_returns * r_squared

        # 6. 近3日跌幅过滤
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if min(day1, day2, day3) < g.loss:
                log.info(f"⚠️ {etf} {name} 近3日有单日跌幅超限，排除")
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


def get_annualized_returns(price_series, lookback_days):
    """计算加权年化收益率（无未来）"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def get_volume_ratio(context, security, lookback=None, threshold=None):
    """计算成交量比值（基于分钟线）"""
    lookback = lookback or g.volume_lookback
    threshold = threshold or g.volume_threshold
    try:
        name = get_name(security)
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()

        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        if ratio > threshold:
            log.debug(f"❌ {security} {name} 成交量比{ratio:.2f} > {threshold}")
            return ratio
        return None
    except Exception as e:
        log.warning(f"🚨成交量计算失败 {security}: {e}")
        return None


def check_intraday_drawdown_for_buy(security, context):
    """买入前检查：ETF当前是否处于日内显著回撤状态
    返回 True 表示正在回撤（不宜买入），False 表示正常
    """
    try:
        df = get_price(security, start_date=context.current_dt.date(), end_date=context.current_dt,
                       frequency='1m', fields=['high', 'close'], skip_paused=True, fq='pre')
        if df is None or df.empty:
            return False
        day_high = df['high'].max()
        current = df['close'].iloc[-1]
        if day_high <= 0:
            return False
        drawdown = (day_high - current) / day_high
        return drawdown >= g.intraday_drawdown_threshold
    except:
        return False


def select_target_etfs_from_rankings(context, ranked):
    """从排名列表中按统一过滤条件选出目标ETF，最多 holdings_num 个。

    卖出和买入共用此函数，确保两者的目标集合完全一致，
    杜绝「13:09 卖出 → 13:10 买回同一标的」的现象。

    过滤逻辑（优先级从高到低）：
      1. 得分阈值（min_score_threshold）
      2. 盈利保护检查（避免卖了又买）
      3. 当日回撤/盈利保护卖出禁止买回（drawdown_selled_today）
      4. 日内回撤检查（避免"接飞刀"）
    """
    target_etfs = []
    for m in ranked:
        if len(target_etfs) >= g.holdings_num:
            break

        if m['score'] < g.min_score_threshold:
            continue

        etf = m['etf']

        if g.enable_profit_protection and check_profit_protection(etf, context):
            log.info(f"🚫 {etf} {m['etf_name']} 触发盈利保护，从候选列表中排除")
            continue

        if etf in g.drawdown_selled_today:
            log.info(f"🚫 {etf} {m['etf_name']} 今日因回撤/盈利保护卖出，禁止日内买回")
            continue

        if check_intraday_drawdown_for_buy(etf, context):
            log.info(f"🌊 {etf} {m['etf_name']} 当前处于日内回撤状态(>{g.intraday_drawdown_threshold*100:.0f}%)，暂不买入")
            continue

        target_etfs.append(etf)

    return target_etfs


# ==================== 卖出模块 ====================
@time_monitor(func_name="卖出操作")
def etf_sell_trade(context):
    """卖出不符合条件的持仓"""
    log.info("📤 ========== 卖出操作开始 ==========")

    ranked = get_cached_rankings(context)
    target_etfs = select_target_etfs_from_rankings(context, ranked)

    defensive_available = check_defensive_etf_available(context)
    if not target_etfs and defensive_available:
        target_etfs = [g.defensive_etf]
        log.info(f"🛡️ 无目标ETF，防御模式：{g.defensive_etf} {get_name(g.defensive_etf)}")

    # 缓存最终目标列表，供 13:10 买入复用（避免时间敏感过滤在 1 分钟内变化）
    g.target_etfs_cache = {'date': context.current_dt.date(), 'data': list(target_etfs)}

    target_set = set(target_etfs)

    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        if sec not in target_set:
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                cost = pos.avg_cost
                buy_date = g.buy_date.get(sec)
                hold_days = (context.current_dt.date() - buy_date).days if buy_date else 0
                if smart_order_target_value(sec, 0, context):
                    log.info(f"📤 卖出持仓：{sec} {get_name(sec)}")
                    g.trade_log['sell_records'].append({
                        'time': get_real_time(),
                        'code': sec,
                        'name': get_name(sec),
                        'cost': cost,
                        'price': get_current_data()[sec].last_price,
                        'hold_days': hold_days
                    })
                    if sec in g.buy_date:
                        del g.buy_date[sec]

    log.info("📤 ========== 卖出操作完成 ==========")


# ==================== 买入模块 ====================
@time_monitor(func_name="买入操作")
def etf_buy_trade(context):
    """买入符合条件的ETF"""
    log.info("📥 ========== 买入操作开始 ==========")

    ranked = get_cached_rankings(context)
    log.info("📊 === ETF排名前5 ===")
    for i, m in enumerate(ranked[:5]):
        annual_pct = m['annualized_returns'] * 100
        r_sq = m['r_squared']
        log.info(f"   排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f} 年化{annual_pct:.2f}%")

    today = context.current_dt.date()
    if g.target_etfs_cache['date'] == today and g.target_etfs_cache['data'] is not None:
        target_etfs = list(g.target_etfs_cache['data'])
        log.info(f"📋 复用13:09目标ETF缓存：{target_etfs}")
    else:
        # 兜底：卖出未执行或缓存缺失时，重新计算（含防御模式判断）
        target_etfs = select_target_etfs_from_rankings(context, ranked)
        if not target_etfs:
            if check_defensive_etf_available(context) and g.defensive_etf not in g.drawdown_selled_today:
                target_etfs = [g.defensive_etf]
                log.info(f"🛡️ 进入防御模式：{g.defensive_etf} {get_name(g.defensive_etf)}")
            else:
                log.info("💤 无目标ETF且防御不可用，保持空仓")
                return

    if target_etfs:
        for i, etf in enumerate(target_etfs):
            m = next((x for x in ranked if x['etf'] == etf), None)
            if m:
                log.info(f"🎯 目标ETF {i+1}: {etf} {m['etf_name']} 得分{m['score']:.4f}")
    else:
        log.info("💤 无目标ETF，保持空仓")
        return

    # 检查是否有持仓需要先卖出
    current_etf_pos = [s for s in context.portfolio.positions if s in g.etf_pool or s == g.defensive_etf]
    to_sell = [s for s in current_etf_pos if s not in target_etfs]
    if to_sell:
        log.info(f"⏳ 尚有持仓需要卖出：{[get_name(s) for s in to_sell]}，等待卖出完成")
        return

    # 等权分配
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

    log.info("📥 ========== 买入操作完成 ==========")


# ==================== 辅助函数 ====================
def get_name(security):
    try:
        return get_current_data()[security].name
    except:
        return "未知"


def check_defensive_etf_available(context):
    data = get_current_data()
    etf = g.defensive_etf
    if data[etf].paused:
        return False
    if data[etf].last_price >= data[etf].high_limit:
        return False
    if data[etf].last_price <= data[etf].low_limit:
        return False
    return True


def smart_order_target_value(security, target_value, context):
    data = get_current_data()
    name = get_name(security)

    if data[security].paused:
        log.info(f"❌ {security} {name} 停牌，跳过")
        return False

    price = data[security].last_price
    if price == 0:
        return False

    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount

    if diff > 0:
        if data[security].last_price >= data[security].high_limit:
            log.info(f"🔒 {security} {name} 涨停，跳过买入")
            return False
    elif diff < 0:
        if data[security].last_price <= data[security].low_limit:
            log.info(f"🔒 {security} {name} 跌停，跳过卖出")
            return False

    trade_val = abs(diff) * price
    if 0 < trade_val < g.min_money:
        log.info(f"💰 {security} {name} 交易金额太小，跳过")
        return False

    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            return False
        diff = -min(abs(diff), closeable)

    if diff != 0:
        order_result = order(security, diff)
        if order_result:
            log.info(f"{'📥 买入' if diff>0 else '📤 卖出'} {security} {name} 数量{abs(diff)} 价格{price:.3f}")
            if diff > 0:
                g.buy_date[security] = context.current_dt.date()
            return True
        else:
            log.warning(f"⚠️ 下单失败: {security} {name}")
            return False
    return False


# ==================== 盘后总结报告 ====================
def daily_summary_report(context):
    """盘后总结"""
    current_date = context.current_dt.strftime('%Y-%m-%d')
    total_value = context.portfolio.total_value
    cash = context.portfolio.cash
    positions_value = total_value - cash

    log.info("📋 ========== 策略运行日报 ==========")
    log.info(f"📅 日期: {current_date}")

    # 市场状态（含独立开关状态）
    if g.enable_regime_switch:
        status = "🔴走弱期" if g.is_a_share_weak else "🟢正常期"
        avoid_status = "回避A股" if (g.is_a_share_weak and g.enable_avoid_a_share) else ("不回避A股" if g.is_a_share_weak else "正常交易")
        drawdown_status = "🛡️启用" if (g.is_a_share_weak and g.enable_intraday_drawdown) else ("⭕关闭" if (g.is_a_share_weak and not g.enable_intraday_drawdown) else "⭕关闭")
        log.info(f"🌍 市场状态：{status} | {avoid_status} 计数:{g.weak_period_counter}/{g.weak_period_max_days}")
        log.info(f"🛡️ 分钟级回撤：{drawdown_status}（阈值{g.intraday_drawdown_threshold*100:.0f}%）")
    else:
        log.info("🌍 行情判断未启用，始终全市场交易")

    # 独立开关汇总
    avoid_switch_status = "ON（走弱期回避A股）" if g.enable_avoid_a_share else "OFF（走弱期不回避A股）"
    drawdown_switch_status = "ON（走弱期自动启用）" if g.enable_intraday_drawdown else "OFF（不触发）"
    log.info(f"⚙️ 独立开关：A股回避={avoid_switch_status} | 分钟回撤={drawdown_switch_status}")

    # 今日卖出
    sell_records = g.trade_log.get('sell_records', [])
    log.info(f"📤 今日卖出：{len(sell_records)}只")
    for r in sell_records:
        cost = r.get('cost', 0)
        sell_price = r.get('price', 0)
        profit_pct = (sell_price / cost - 1) * 100 if cost > 0 else 0
        hold_days = r.get('hold_days', 0)
        log.info(f"   {r['code']} {r['name']} | 成本:{cost:.3f} | 卖出:{sell_price:.3f} | 收益:{profit_pct:+.2f}% | 持有{hold_days}天")

    # 最终持仓
    pos_list = []
    for sec, pos in context.portfolio.positions.items():
        if pos.total_amount == 0:
            continue
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos_list.append(sec)
    log.info(f"📊 最终持仓：{len(pos_list)}只")
    for sec, pos in context.portfolio.positions.items():
        if pos.total_amount == 0:
            continue
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        current_price = get_current_data()[sec].last_price
        cost = pos.avg_cost
        profit_pct = (current_price / cost - 1) * 100 if cost > 0 else 0
        buy_date = g.buy_date.get(sec)
        hold_days = (context.current_dt.date() - buy_date).days if buy_date else 0
        log.info(f"   {sec} {get_name(sec)} | 成本:{cost:.3f} | 当前:{current_price:.3f} | 收益:{profit_pct:+.2f}% | 持有{hold_days}天")

    # 账户汇总
    returns = (total_value - context.portfolio.starting_cash) / context.portfolio.starting_cash * 100
    log.info(f"💰 总资产：{total_value:.2f} | 可用：{cash:.2f} | 市值：{positions_value:.2f} | 累计收益：{returns:.2f}%")
    log.info("📋🐂🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩报告结束 🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🚩🐂")
    log.info("")

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
