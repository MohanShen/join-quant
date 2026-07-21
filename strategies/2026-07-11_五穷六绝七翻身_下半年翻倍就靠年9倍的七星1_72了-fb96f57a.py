# Clone from JoinQuant
# postId: fb96f57ae0499819c98d286b62ee1242
# backtestId: dc53e00361efb29766b82ca8cc423a8e
# title: 五穷六绝七翻身，下半年翻倍就靠年9倍的七星1.72了！

# 标题：七星172拉普拉斯核心精华版 v3.1（聚宽）
# 基线回测：1151.58%/16.19%/夏普11.102（2025-01起，主题域18只）
# 上一版：七星172拉普拉斯核心精简V3-1151.58倍2年半.txt

"""
七星172拉普拉斯核心精华版 v3.1（聚宽）

【版本规范】每次修改复制为新文件，勿覆盖旧定版
【上一版】七星172拉普拉斯核心精简V3-Live1定版.py

================================================================================
【v3.1 优化内容 2026-05-31】聚宽实盘补丁（核心逻辑与 V3 回测基线一致）
================================================================================

1. 买卖目标统一（修复 11:10/11:11 分歧）
   - 新增 select_target_etfs_from_rankings / resolve_rotation_targets
   - 卖出、买入共用同一套过滤，避免「刚卖又买回」或「卖 A 买 B 目标不一致」

2. 盘中临时停牌防护 is_etf_tradable
   - 聚宽 get_current_data().paused 对下午临时停牌常为 False
   - 本交易时段开盘 5 分钟后仍无分钟成交 → 视为不可交易，排名与下单均跳过

3. 轮动深度限制 rotation_buy_max_rank_depth=5
   - 仅在前 5 名内选目标；前排因盈利保护/停牌被挡时，不降级买入低分 ETF

4. 得分边界修复
   - 原：min_score < score < max（score=0 且 min=0 时被误排除）
   - 现：min_score <= score < max

5. 有害卖出当日禁买回 drawdown_selled_today
   - 11:00 盈利保护独立卖出 → 写入集合
   - 11:10/11:11 目标选择跳过该标的，防止当日买回

6. 日内状态每日重置（check_positions 09:10）
   - 清空 target_etfs_cache、drawdown_selled_today

7. 下单前复检 + 类型安全
   - smart_order_target_value 下单前再次 is_etf_tradable
   - check_profit_protection 现价统一 float，避免 str/float 比较异常

================================================================================
【定版参数摘要】
  - ETF池：主题域 18 只（商品5 + A股13），无海外/宽基/债券
  - 调度：09:10持仓 | 09:25震荡期 | 09:26排名 | 11:00盈利保护 | 11:10卖 | 11:11买
  - 动量：lookback=25 | holdings=1 | 防御511880 | 风险基准515880
  - 滤波：正常期拉普拉斯 / 震荡期高斯

【实盘提示】
  - 聚宽运行频率：分钟（09:26 早盘排名依赖分钟数据）
  - 佣金默认万1（0.0001），账户万0.5请改 initialize 内 commission
  - 买卖时点可按 七星大池子改时间方法和池子.txt 微调（如 11:12/11:13）
  - 上传前确认 18 只 ETF 均可交易（尤其 161226 白银 LOF）
"""

import numpy as np
import math
import datetime
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
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    set_benchmark('000300.XSHG')

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    log.info("========== 策略初始化开始 ==========")

    g.strategy_version = '172-精华V3.1'
    g.strategy_id = 'QX172-V3.1'
    g.rotation_buy_max_rank_depth = 5   # 仅在前N名内轮动，不降级买低分标的

    # ---------- ETF池：核心精简V3（18只，无海外/港股/宽基/债券）----------
    # 选池原则：2025+日志高贡献主线 + 2026延续品种；商品补白银/黄金/电池，去零成交与2025拖累
    g.etf_pool = [
        # 商品轮动（5）— 原油+有色 + 2025高贡献白银/黄金/电池
        '501018.XSHG',  # 南方原油（2025+总贡献第1）
        '512400.XSHG',  # 有色金属
        '161226.XSHE',  # 国投白银LOF（2025 y25=+52224，补9-12月平淡期）
        '518880.XSHG',  # 黄金ETF（2025 y25=+4175）
        '561910.XSHG',  # 电池ETF（2025 y25=+15645）
        # AI / 半导体（4）
        '512930.XSHG',  # AI人工智能
        '588200.XSHG',  # 科创芯片
        '512480.XSHG',  # 半导体
        '588710.XSHG',  # 科创半导体设备
        # 机器人 / 卫星 / 通信（6）
        '562500.XSHG',  # 机器人华夏
        '562950.XSHG',  # 消电50（2026高贡献）
        '159206.XSHE',  # 卫星永赢
        '159218.XSHE',  # 卫星招商
        '563230.XSHG',  # 卫星产业
        '515880.XSHG',  # 通信ETF（2025 y25=+59807，风险基准）
        # TMT / 制造（3）
        '512220.XSHG',  # TMT ETF
        '159667.XSHE',  # 工业母机
        '159326.XSHE',  # 电网设备
    ]
    # V3相对V2：+161226/518880/561910；-562800/516150(日志零成交)、159583(2025亏)

    # ---------- 核心参数 ----------
    g.lookback_days = 25               # 动量计算周期
    g.holdings_num = 1                 # 候选数量
    g.defensive_etf = "511880.XSHG"    # 防御ETF（货币基金）
    g.min_money = 5000                 # 最小交易金额

    # ---------- 盈利保护参数 ----------
    g.enable_profit_protection = True                      # 盈利保护开关
    g.profit_protection_lookback = 1                       # 盈利保护回看周期（天）
    g.profit_protection_threshold = 0.05                   # 盈利保护回撤阈值（5%）
    g.profit_protection_check_times = ['11:00'] #['09:45','11:00','13:30'] #['11:00']            # 盈利保护检查时间点（可添加多个，如['09:45','11:00','13:30']）

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

    # ---------- 早盘选股刷新（T日集合竞价后重算，替代纯T-1收盘数据） ----------
    g.enable_morning_ranking_refresh = True   # 是否在T日早盘重算排名
    g.morning_ranking_refresh_time = '09:26'  # 集合竞价结束后刷新（9:25竞价结束，9:26数据更稳定）

    # ---------- 运行时变量 ----------
    g.rankings_cache = {'date': None, 'data': None}   # 排名缓存
    g.target_etfs_cache = {'date': None, 'data': None}
    g.drawdown_selled_today = set()                   # 盈利保护等有害卖出，禁止当日买回

    # ---------- 震荡期参数 ----------
    g.enable_range_bound_mode = True      # 震荡期模式开关
    g.current_filter = '正常期'           # 当前滤波器：'正常期'=拉普拉斯, '震荡期'=高斯
    g.risk_state = '正常期'               # 风险状态
    g.lookback_high_low_days = 20         # 近N个交易日高低点回看
    g.risk_benchmark = '515880.XSHG'      # 风险基准（须在池内；通信主线）
    # 滤波器参数（正常期拉普拉斯，震荡期高斯）
    g.laplace_s_param = 0.05
    g.laplace_min_slope = 0.001
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002
    # 进入震荡期条件
    g.enable_bias_trigger = True          # 乖离率过大触发
    g.bias_threshold = 0.10               # 乖离率阈值（10%）
    g.ma_period = 20                      # 均线周期
    g.enable_rsi_trigger = True           # RSI超买回落触发
    g.rsi_overbought = 75
    g.rsi_pullback = 60
    g.previous_rsi = None
    g.enable_stop_loss_trigger = False    # 盈利保护触发止损信号开关
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    # 退出震荡期条件
    g.enable_low_point_rise_trigger = True
    g.low_point_rise_threshold = 0.03     # 从低点上涨3%退出震荡期
    g.enable_stable_signal_trigger = True
    g.drawdown_recovery = 0.03            # 回撤收窄阈值
    g.max_range_bound_days = 15           # 最大震荡期天数
    g.stable_days = 0
    # 震荡期控制
    g.filter_switch_cooldown = 2          # 切换冷却期（交易日）
    g.last_switch_date = None
    g.range_bound_start_date = None
    g.range_bound_days_count = 0
    g.previous_drawdown = None

    # ---------- 交易调度 ----------
    run_daily(check_positions, time='09:10')
    # 震荡期检查提前到早盘选股前，确保9:26排名使用正确的滤波器状态
    run_daily(check_range_bound, time='09:25')
    if g.enable_morning_ranking_refresh:
        run_daily(refresh_morning_rankings, time=g.morning_ranking_refresh_time)
        log.info(f"已注册T日早盘选股刷新：{g.morning_ranking_refresh_time}（集合竞价后重算排名）")
    run_daily(etf_sell_trade, time='11:10')
    run_daily(etf_buy_trade, time='11:11')

    # 动态注册盈利保护检查时间点
    for check_time in g.profit_protection_check_times:
        run_daily(profit_protection_check, time=check_time)
        log.info(f"已注册盈利保护检查时间：{check_time}")

    run_daily(reset_range_bound_daily, time='15:10')

    log.info(f"策略初始化完成：{g.strategy_version} 核心精华池{len(g.etf_pool)}只，动量{g.lookback_days}天，持仓{g.holdings_num}只")
    log.info("V3池：原油/有色/白银/黄金/电池+AI半导体+机器人消电+三星+通信+TMT+工母机电网")
    log.info(f"盈利保护开关：{'开启' if g.enable_profit_protection else '关闭'}，回看周期{g.profit_protection_lookback}天，回撤阈值{g.profit_protection_threshold*100:.0f}%")
    if g.enable_premium_filter:
        log.info(f"溢价率过滤已启用，阈值：{g.premium_threshold*100:.0f}%")
    else:
        log.info("溢价率过滤未启用")
    log.info(f"震荡期模式：{'开启' if g.enable_range_bound_mode else '关闭'}，正常期=拉普拉斯滤波器，震荡期=高斯滤波器")

    # 首次运行时，根据历史数据判断当前是否处于震荡期
    init_range_bound_status(context)
    log.info("========== 策略初始化完成 ==========")


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
                    g.drawdown_selled_today.add(sec)
                    log.info(f"🛡️ 盈利保护卖出（独立检查）：{sec} {get_name(sec)}")
                    # 触发止损信号，用于震荡期进入判断
                    if getattr(g, 'enable_stop_loss_trigger', False):
                        g.stop_loss_triggered_today = True
                        g.stop_loss_triggered_date = context.current_dt.date()
                        log.info("【盈利保护触发】记录止损信号，将在震荡期检查时使用")
    log.info("========== 盈利保护独立检查完成 ==========")


# ==================== 盈利保护检查函数（核心逻辑） ====================
def check_profit_protection(security, context, lookback=None, threshold=None):
    """
    检查是否触发盈利保护（从最近N日最高点回撤超过阈值）
    参数:
        security: ETF代码
        context: 上下文
        lookback: 回看天数，默认g.profit_protection_lookback
        threshold: 回撤阈值，默认g.profit_protection_threshold
    返回:
        bool: True表示应触发盈利保护（卖出/排除），False表示安全
    """
    # 若开关关闭，直接返回安全（独立检查函数已在外层判断，但保留此判断以防直接调用）
    if not g.enable_profit_protection:
        return False

    lookback = lookback or g.profit_protection_lookback
    threshold = threshold or g.profit_protection_threshold

    # 获取最近N日的最高价（不包括当天）
    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback:
        log.debug(f"{security} {get_name(security)} 历史数据不足{lookback}天，无法检查盈利保护")
        return False

    max_high = float(hist['high'].max())
    current_price = get_current_data()[security].last_price
    if current_price is None:
        return False
    current_price = float(current_price)

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


# ==================== 震荡期机制 ====================
def calculate_rsi(close, period=14):
    """计算RSI值"""
    try:
        if len(close) < period + 1:
            return None
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except:
        return None


def laplace_filter(price, s=0.05):
    """拉普拉斯滤波器（正常期使用）"""
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


def gaussian_filter_last_two(price, sigma=1.2):
    """仅计算高斯滤波最后两个点（震荡期使用，效率优化）"""
    n = len(price)
    if n < 2:
        return 0, 0
    idx_1 = np.arange(n)
    weights_1 = np.exp(-((idx_1+1)**2) / (2 * sigma**2))[::-1]
    weights_1 /= np.sum(weights_1)
    g1 = np.sum(price * weights_1)
    price_2 = price[:-1]
    idx_2 = np.arange(n-1)
    weights_2 = np.exp(-((idx_2+1)**2) / (2 * sigma**2))[::-1]
    weights_2 /= np.sum(weights_2)
    g2 = np.sum(price_2 * weights_2)
    return g1, g2


def get_risk_benchmark_state(context):
    """获取风险基准的日线+盘中融合状态，用于震荡期判断"""
    required_days = max(g.ma_period, g.lookback_high_low_days)
    lookback = required_days + 30
    end_date = getattr(context, 'previous_date', None)
    if end_date is None:
        return None
    df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,
                   frequency='daily', fields=['close', 'high', 'low'], panel=False)
    if df is None or len(df) < required_days:
        return None
    daily_close = df['close'].values.astype(float)
    daily_high = df['high'].values.astype(float)
    daily_low = df['low'].values.astype(float)
    current_price = float(daily_close[-1])
    intraday_high = current_price
    intraday_low = current_price
    data_source = '昨日日线'
    try:
        today = context.current_dt.date()
        minute_df = get_price(
            g.risk_benchmark, start_date=today, end_date=context.current_dt,
            frequency='1m', fields=['close', 'high', 'low'],
            panel=False, fill_paused=False
        )
        if minute_df is not None and not minute_df.empty:
            minute_close = minute_df['close'].dropna()
            minute_high = minute_df['high'].dropna()
            minute_low = minute_df['low'].dropna()
            if not minute_close.empty:
                current_price = float(minute_close.iloc[-1])
                intraday_high = float(minute_high.max()) if not minute_high.empty else current_price
                intraday_low = float(minute_low.min()) if not minute_low.empty else current_price
                data_source = '当日盘中'
    except Exception:
        pass
    if current_price <= 0:
        try:
            current_data = get_current_data()
            live_price = current_data[g.risk_benchmark].last_price
            if live_price is not None and live_price > 0:
                current_price = float(live_price)
                intraday_high = max(intraday_high, current_price)
                intraday_low = min(intraday_low, current_price)
                data_source = '实时快照'
        except Exception:
            current_price = float(daily_close[-1])
    close_series = np.append(daily_close, current_price)
    high_series = np.append(daily_high, max(intraday_high, current_price))
    low_series = np.append(daily_low, min(intraday_low, current_price))
    recent_high = np.max(high_series[-g.lookback_high_low_days:])
    recent_low = np.min(low_series[-g.lookback_high_low_days:])
    ma = np.mean(close_series[-g.ma_period:])
    current_rsi = calculate_rsi(close_series, period=14)
    previous_rsi = calculate_rsi(daily_close, period=14)
    return {
        'close_series': close_series,
        'high_series': high_series,
        'low_series': low_series,
        'current_price': current_price,
        'recent_high': recent_high,
        'recent_low': recent_low,
        'ma': ma,
        'current_rsi': current_rsi,
        'previous_rsi': previous_rsi,
        'data_source': data_source,
    }


def is_fresh_stop_loss_signal(context):
    """判断止损信号是否仍在有效期内"""
    signal_date = getattr(g, 'stop_loss_triggered_date', None)
    if signal_date is None:
        return False
    today = context.current_dt.date()
    previous_date = getattr(context, 'previous_date', None)
    if signal_date == today:
        return True
    if previous_date is not None and signal_date == previous_date:
        return True
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    return False


def init_range_bound_status(context):
    """首次运行时，根据历史数据判断当前是否处于震荡期"""
    if not g.enable_range_bound_mode:
        return
    log.info("【首次运行】初始化震荡期状态...")
    try:
        if context.previous_date is None:
            log.warning("【首次运行】无法获取前一个交易日，保持正常期")
            return
        end_date = context.previous_date
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback,
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            log.warning("【首次运行】数据不足，保持正常期")
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        if len(close) >= g.lookback_high_low_days:
            recent_high = np.max(high[-g.lookback_high_low_days:])
            recent_low = np.min(low[-g.lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        ma = np.mean(close[-g.ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        current_rsi = calculate_rsi(close, period=14)
        should_enter = False
        signals = []
        if g.enable_bias_trigger and bias > g.bias_threshold:
            should_enter = True
            signals.append(f"乖离率{bias:.2%}>{g.bias_threshold:.0%}")
        if g.enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback:
                should_enter = True
                signals.append(f"RSI超买回落{prev_rsi:.1f}->{current_rsi:.1f}")
        if should_enter:
            g.current_filter = '震荡期'
            g.risk_state = '震荡期'
            g.range_bound_start_date = end_date
            g.range_bound_days_count = 0
            log.info(f"【首次运行】初始化进入震荡期: {'; '.join(signals)}")
        else:
            g.current_filter = '正常期'
            g.risk_state = '正常期'
            if len(close) >= g.lookback_high_low_days:
                g.previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            else:
                g.previous_drawdown = 0
            g.previous_rsi = current_rsi
            rsi_str = f"{current_rsi:.1f}" if current_rsi is not None else "N/A"
            log.info(f"【首次运行】初始状态: 正常期, 乖离率: {bias:.2%}, RSI: {rsi_str}, 从低点涨幅: {rise_from_low:.2%}")
    except Exception as e:
        log.warning(f"【首次运行】初始化震荡期状态异常: {e}，保持正常期")


def check_and_exit_range_bound_mode(context):
    """检查是否需要退出震荡期"""
    if not g.enable_range_bound_mode:
        return
    if g.current_filter != '震荡期':
        return
    log.info("【震荡期退出检查】开始检测退出条件...")
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is None:
            log.warning("【震荡期退出检查】数据不足，跳过")
            return
        close = benchmark_state['close_series']
        current_price = benchmark_state['current_price']
        recent_high = benchmark_state['recent_high']
        recent_low = benchmark_state['recent_low']
        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        recovery_signals = []
        ma = benchmark_state['ma']
        current_rsi = benchmark_state['current_rsi']
        log.info(f"【震荡期数据】当前价: {current_price:.3f}, 近{g.lookback_high_low_days}日高点: {recent_high:.3f}, 低点: {recent_low:.3f}")
        log.info(f"【震荡期数据】回撤: {current_drawdown:.2%}, 从低点涨幅: {rise_from_low:.2%}")
        if g.enable_low_point_rise_trigger:
            if rise_from_low >= g.low_point_rise_threshold:
                recovery_signals.append(f"从低点上涨{rise_from_low:.2%}>={g.low_point_rise_threshold:.0%}")
                log.info(f"【退出条件触发】从低点上涨: {rise_from_low:.2%}")
        if g.enable_stable_signal_trigger:
            if current_price > ma:
                recovery_signals.append("价格站上均线")
            if len(close) >= 2 and close[-1] > close[-2]:
                recovery_signals.append("价格回升")
            if g.previous_drawdown is not None and current_drawdown < g.previous_drawdown:
                recovery_signals.append(f"回撤收窄({current_drawdown:.2%}<{g.previous_drawdown:.2%})")
            if current_rsi is not None and g.previous_rsi is not None and current_rsi > g.previous_rsi:
                recovery_signals.append(f"RSI回升({current_rsi:.1f})")
            drawdown_safe = current_drawdown < g.drawdown_recovery
            if drawdown_safe:
                g.stable_days += 1
                log.info(f"【企稳计数】连续企稳天数: {g.stable_days}")
            else:
                g.stable_days = 0
        g.previous_drawdown = current_drawdown
        g.previous_rsi = current_rsi
        range_bound_days = 0
        if g.range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = len(trade_days) - 1
            if range_bound_days >= g.max_range_bound_days:
                recovery_signals.append(f"震荡期满({range_bound_days}天)")
                log.info(f"【退出条件触发】震荡期已满{range_bound_days}天")
        low_point_condition = g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold
        stable_condition = False
        if g.enable_stable_signal_trigger:
            drawdown_safe = current_drawdown < g.drawdown_recovery
            stable_condition = drawdown_safe and len(recovery_signals) >= 2 and g.stable_days >= 2
        force_condition = range_bound_days >= g.max_range_bound_days
        should_recover = low_point_condition or stable_condition or force_condition
        if should_recover:
            can_switch = True
            if g.last_switch_date is not None:
                trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
                days_since = len(trade_days) - 1
                if days_since < g.filter_switch_cooldown:
                    can_switch = False
                    log.info(f"【震荡期退出】冷却期中，距上次切换{days_since}天")
            if can_switch:
                g.current_filter = '正常期'
                g.risk_state = '正常期'
                g.last_switch_date = context.current_dt.date()
                g.range_bound_start_date = None
                g.range_bound_days_count = 0
                g.stable_days = 0
                log.info(f"【退出震荡期】切换回拉普拉斯滤波器: {'; '.join(recovery_signals)}")
        else:
            log.info("【震荡期退出检查】未满足退出条件，保持震荡期(高斯滤波器)")
    except Exception as e:
        log.warning(f"【震荡期退出检查】判断出错: {e}")


def check_and_enter_range_bound_mode(context):
    """检查是否需要进入震荡期"""
    if not g.enable_range_bound_mode:
        return
    log.info("【震荡期进入检查】开始检测...")
    stop_loss_signal_active = is_fresh_stop_loss_signal(context)
    can_switch = True
    if g.last_switch_date is not None:
        trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
        days_since = len(trade_days) - 1
        if days_since < g.filter_switch_cooldown:
            can_switch = False
            log.info(f"【震荡期检查】冷却期中，距上次切换{days_since}天")
    if g.current_filter == '震荡期':
        log.info("【震荡期检查】当前已在震荡期")
        return
    if not can_switch:
        return
    risk_signals = []
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is not None:
            close = benchmark_state['close_series']
            current_price = benchmark_state['current_price']
            # 条件1: 乖离率过大
            if g.enable_bias_trigger:
                ma = benchmark_state['ma']
                bias = (current_price - ma) / ma if ma > 0 else 0
                if bias > g.bias_threshold:
                    risk_signals.append(f"乖离率过大({bias:.2%}>{g.bias_threshold:.0%})")
                    log.info(f"【条件触发】乖离率: {bias:.2%} (数据源:{benchmark_state['data_source']})")
            # 条件2: RSI超买回落
            if g.enable_rsi_trigger:
                current_rsi = benchmark_state['current_rsi']
                if len(close) >= 15 and current_rsi is not None:
                    prev_rsi = benchmark_state['previous_rsi']
                    if prev_rsi is not None:
                        if prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback and current_rsi < prev_rsi:
                            risk_signals.append(f"RSI超买回落({prev_rsi:.1f}->{current_rsi:.1f})")
                            log.info(f"【条件触发】RSI超买回落: {prev_rsi:.1f}->{current_rsi:.1f}")
    except Exception as e:
        log.warning(f"【震荡期检查】获取基准数据异常: {e}")
    # 条件3: 盈利保护触发止损
    if g.enable_stop_loss_trigger and stop_loss_signal_active:
        risk_signals.append("盈利保护触发止损")
        log.info("【条件触发】盈利保护触发止损信号")
    if len(risk_signals) > 0:
        g.current_filter = '震荡期'
        g.risk_state = '震荡期'
        g.last_switch_date = context.current_dt.date()
        g.range_bound_start_date = context.current_dt.date()
        g.range_bound_days_count = 0
        g.stable_days = 0
        g.stop_loss_triggered_today = False
        g.stop_loss_triggered_date = None
        log.info(f"【进入震荡期】切换到高斯滤波器: {'; '.join(risk_signals)}")
    else:
        log.info("【震荡期检查】未满足进入条件，保持正常期(拉普拉斯滤波器)")


def check_range_bound(context):
    """震荡期检查入口（09:25定时调度，在早盘选股刷新前执行）"""
    if not g.enable_range_bound_mode:
        return
    log.info("========== 震荡期检查开始 ==========")
    log.info(f"当前状态: {g.current_filter}")
    prev_filter = g.current_filter
    check_and_exit_range_bound_mode(context)
    check_and_enter_range_bound_mode(context)
    log.info(f"检查后状态: {g.current_filter}")
    if prev_filter != g.current_filter:
        invalidate_rankings_cache()
        log.info("滤波器状态变更，已清除排名缓存")
    log.info("========== 震荡期检查完成 ==========")


def reset_range_bound_daily(context):
    """收盘后重置震荡期相关的每日标志"""
    if g.current_filter == '震荡期' and g.range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
        g.range_bound_days_count = len(trade_days) - 1
        log.info(f"震荡期已持续 {g.range_bound_days_count} 个交易日")
    log.debug("收盘震荡期标志重置完成")


# ==================== 核心计算模块 ====================
def invalidate_rankings_cache():
    """清除排名缓存，下次调用 get_cached_rankings 时强制重算"""
    g.rankings_cache = {'date': None, 'data': None}


def get_today_reference_price(context, security):
    """获取T日参考价：早盘优先用集合竞价开盘价，盘中用最新价"""
    data = get_current_data()[security]
    current_time = context.current_dt.time()
    auction_done = current_time >= datetime.time(9, 25)

    if auction_done:
        day_open = getattr(data, 'day_open', None)
        if day_open is not None and day_open > 0:
            return float(day_open)

    if data.last_price is not None and data.last_price > 0:
        return float(data.last_price)

    try:
        today = context.current_dt.date()
        minute_df = get_price(
            security, start_date=today, end_date=context.current_dt,
            frequency='1m', fields=['close'], panel=False, fill_paused=False
        )
        if minute_df is not None and not minute_df.empty:
            last_close = minute_df['close'].dropna()
            if not last_close.empty and last_close.iloc[-1] > 0:
                return float(last_close.iloc[-1])
    except Exception:
        pass

    return None


def refresh_morning_rankings(context):
    """
    T日9:26集合竞价结束后重算ETF排名。
    历史仍用T-1及以前日线收盘价，当日点位用开盘价，比纯T-1收盘选股更精确。
    """
    if not g.enable_morning_ranking_refresh:
        return

    log.info("========== T日早盘选股刷新开始（集合竞价后） ==========")
    log.info(f"当前时间：{context.current_dt.strftime('%H:%M:%S')}，滤波器：{g.current_filter}")

    invalidate_rankings_cache()
    ranked = get_cached_rankings(context)

    log.info("=== 早盘刷新后排名前5 ===")
    for i, m in enumerate(ranked[:5]):
        log.info(
            f"排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f} "
            f"年化{m['annualized_returns']*100:.2f}% 参考价{m['current_price']:.3f}"
        )
    log.info("========== T日早盘选股刷新完成，11:10/11:11交易将使用此排名 ==========")


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
        tradable, reason = is_etf_tradable(context, etf)
        if not tradable:
            log.debug(f"{etf} {get_name(etf)} 不可交易({reason})，跳过")
            continue

        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            # 得分范围过滤（含下限等于）
            if g.min_score_threshold <= metrics['score'] < g.max_score_threshold:
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

        # 价格序列：T-1及以前用日线收盘，T日优先用集合竞价开盘价
        current_price = get_today_reference_price(context, etf)
        if current_price is None or current_price <= 0:
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
                annualized = get_annualized_returns(price_series, g.lookback_days)
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
        recent = price_series[-(g.lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1

        # R²（趋势稳定性）
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

        # ===== 7. 动态滤波器过滤（震荡期机制） =====
        if g.enable_range_bound_mode and len(price_series) >= 10:
            try:
                laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                laplace_slope = laplace_values[-1] - laplace_values[-2] if len(laplace_values) >= 2 else 0
                passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
                g1_val, g2_val = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
                gaussian_slope = g1_val - g2_val
                passed_gaussian = (current_price > g1_val and gaussian_slope > g.gaussian_min_slope)
                if g.current_filter == '正常期':
                    passed_filter = passed_laplace
                    filter_name = '拉普拉斯'
                else:
                    passed_filter = passed_gaussian
                    filter_name = '高斯'
                if not passed_filter:
                    log.debug(f"{etf} {name} 未通过{filter_name}滤波器({g.current_filter})，过滤")
                    return None
            except Exception as e:
                log.debug(f"{etf} {name} 滤波器计算异常: {e}")

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
    """计算加权年化收益率"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def get_volume_ratio(context, security, lookback=None, threshold=None):
    """计算当日成交量与过去N日均量的比值，若超过阈值则返回比值，否则None"""
    lookback = lookback or g.volume_lookback
    threshold = threshold or g.volume_threshold
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


# ==================== 可交易性 / 目标选择 ====================
def is_etf_tradable(context, security):
    """判断 ETF 是否可交易（含盘中临时停牌）。返回 (bool, reason)。"""
    try:
        data = get_current_data()[security]
        if data.paused:
            return False, '全天停牌(paused)'

        price = data.last_price
        if price is None or price <= 0:
            return False, '现价无效'

        now = context.current_dt
        t = now.time()
        session_start = None
        if datetime.time(9, 30) <= t <= datetime.time(11, 30):
            session_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        elif datetime.time(13, 0) <= t <= datetime.time(15, 0):
            session_start = now.replace(hour=13, minute=0, second=0, microsecond=0)
        else:
            return True, ''

        minutes_elapsed = (now - session_start).total_seconds() / 60.0
        if minutes_elapsed < 5:
            return True, ''

        df = get_price(
            security, start_date=session_start, end_date=now,
            frequency='1m', fields=['volume'], skip_paused=True, fq='pre'
        )
        if df is None or df.empty:
            return False, '本交易时段无分钟行情(可能盘中停牌)'

        recent = df.tail(min(15, len(df)))
        if recent['volume'].sum() == 0:
            return False, '本交易时段近段无成交(可能盘中停牌)'

        return True, ''
    except Exception as e:
        log.warning(f"{security} {get_name(security)} 可交易性检查异常: {e}")
        return True, ''


def select_target_etfs_from_rankings(context, ranked):
    """买卖共用：从排名中选出目标 ETF，最多 holdings_num 个。"""
    max_depth = getattr(g, 'rotation_buy_max_rank_depth', 5)
    target_etfs = []
    for idx, m in enumerate(ranked):
        if idx >= max_depth:
            if not target_etfs:
                log.info(
                    f"🛡️ 排名前{max_depth}内无可买标的，不降级买入低分ETF"
                )
            break
        if len(target_etfs) >= g.holdings_num:
            break
        if m['score'] < g.min_score_threshold:
            continue

        etf = m['etf']
        tradable, reason = is_etf_tradable(context, etf)
        if not tradable:
            log.info(f"🚫 {etf} {m['etf_name']} 排名{idx+1} 不可交易({reason})，跳过")
            continue
        if g.enable_profit_protection and check_profit_protection(etf, context):
            log.info(f"🚫 {etf} {m['etf_name']} 排名{idx+1} 盈利保护，跳过")
            continue
        if etf in g.drawdown_selled_today:
            log.info(f"🚫 {etf} {m['etf_name']} 排名{idx+1} 今日有害卖出，禁止买回")
            continue

        target_etfs.append(etf)
        log.info(f"✅ 选股命中 排名{idx+1}: {etf} {m['etf_name']} 得分{m['score']:.4f}")
    return target_etfs


def resolve_rotation_targets(context, ranked):
    """解析最终目标：无合格标的时 fallback 防御 ETF（172 原逻辑）。"""
    target_etfs = select_target_etfs_from_rankings(context, ranked)
    if not target_etfs and check_defensive_etf_available(context):
        if g.defensive_etf not in g.drawdown_selled_today:
            target_etfs = [g.defensive_etf]
            log.info(f"🛡️ 无目标ETF，防御模式：{g.defensive_etf} {get_name(g.defensive_etf)}")
    return target_etfs


# ==================== 卖出模块 ====================
def check_positions(context):
    """每日开盘检查持仓状态，重置日内缓存"""
    g.target_etfs_cache = {'date': None, 'data': None}
    g.drawdown_selled_today = set()
    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")


def etf_sell_trade(context):
    """卖出不符合条件的持仓（排名变化、溢价率过高）"""
    log.info("========== 卖出操作开始 ==========")

    ranked = get_cached_rankings(context)
    target_etfs = resolve_rotation_targets(context, ranked)
    g.target_etfs_cache = {'date': context.current_dt.date(), 'data': list(target_etfs)}

    target_set = set(target_etfs)

    # 卖出不在目标列表的持仓
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        if sec not in target_set:
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                if smart_order_target_value(sec, 0, context):
                    log.info(f"📤 卖出不在目标的持仓：{sec} {get_name(sec)}")

    log.info("========== 卖出操作完成 ==========")


# ==================== 买入模块 ====================
def etf_buy_trade(context):
    """买入符合条件的ETF，等权分配，按排名顺序逐个尝试直到凑够持仓数量"""
    log.info("========== 买入操作开始 ==========")

    ranked = get_cached_rankings(context)
    log.info("=== ETF排名前5 ===")
    for i, m in enumerate(ranked[:5]):
        log.info(f"排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f} 年化{m['annualized_returns']*100:.2f}% R²={m['r_squared']:.4f}")

    # 11:11 重新解析目标（与 11:10 同一套逻辑，反映 1 分钟内可交易性变化）
    target_etfs = resolve_rotation_targets(context, ranked)
    if not target_etfs:
        log.info("💤 无目标ETF且防御不可用，保持空仓")
        return

    for i, etf in enumerate(target_etfs):
        m = next((x for x in ranked if x['etf'] == etf), None)
        if m:
            log.info(f"🎯 目标ETF {i+1}: {etf} {m['etf_name']} 得分{m['score']:.4f}")

    # 检查是否有持仓需要先卖出（不在目标列表的持仓）
    current_etf_pos = [s for s in context.portfolio.positions if s in g.etf_pool or s == g.defensive_etf]
    to_sell = [s for s in current_etf_pos if s not in target_etfs]
    if to_sell:
        to_sell_names = [get_name(s) for s in to_sell]
        log.info(f"尚有持仓需要卖出：{list(zip(to_sell, to_sell_names))}，等待卖出完成再买入")
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
        # 5%容差调仓
        if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
            if smart_order_target_value(etf, target_per_etf, context):
                action = "买入" if current_val < target_per_etf else "调仓"
                log.info(f"📦 {action}：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}")

    log.info("========== 买入操作完成 ==========")


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

    tradable, reason = is_etf_tradable(context, security)
    if not tradable:
        log.info(f"{security} {name} 不可交易({reason})，跳过")
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