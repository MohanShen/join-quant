# Clone from JoinQuant
# postId: dd17cc2d449de31939a6a6a5ffd1adee
# backtestId: 05e3d04c61c91929b2c12d73955dc932
# title: 考夫曼自适应均线在大跌行情中的应用

"""
聚宽实盘/模拟交易策略 — KAMA只做多择时
标的：中证2000增强ETF（159552.XSHE）

策略逻辑：
  - KAMA由跌转涨（AMA1出现） → 满仓买入
  - KAMA由涨转跌（AMA1消失） → 清仓卖出
  - 其余情况 → 保持当前仓位

执行流程：
  1. 初始化时预热KAMA指标
  2. 每天9:00开盘前，用前一交易日收盘价计算KAMA，生成当日交易信号
  3. 当日9:35根据信号执行买卖
"""

import numpy as np
import pandas as pd

# ============================================================================
# 聚宽策略框架
# ============================================================================

def initialize(context):
    log.set_level('order', 'error')
    log.set_level('strategy', 'debug')
        
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)  
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='fund')
          
    """初始化：设置参数、预热KAMA、注册定时任务"""
    # 标的
    g.security = '159552.XSHE'
    set_benchmark('399303.XSHE')

    # KAMA参数（全局变量，可修改）
    g.kama_n = 22         # KAMA效率比率回看周期
    g.kama_fastest = 1    # 最快EMA周期 → SC = 2/(2+1) ≈ 0.6667
    g.kama_slowest = 60   # 最慢EMA周期 → SC = 2/(30+1) ≈ 0.0645

    # 预热天数：KAMA_N + 额外缓冲，确保VIR窗口填满
    warmup_days = g.kama_n + 20

    # 获取历史数据预热KAMA
    log.info("正在预热KAMA指标，获取最近 %d 个交易日数据...", warmup_days)
    df = attribute_history(
        g.security,
        warmup_days + 1,
        unit='1d',
        fields=['close'],
        df=True
    )

    if df is None or len(df) == 0:
        log.error("预热数据获取失败，请检查标的代码")
        return

    close_arr = df['close'].values
    log.info("预热数据: %d 个交易日, 最新收盘价: %.4f", len(close_arr), close_arr[-1])

    # 计算完整KAMA
    kama_vals, kama_up_vals, er_vals = calc_kama(
        close_arr,
        n=g.kama_n,
        fastest=g.kama_fastest,
        slowest=g.kama_slowest
    )

    # 存储最后有效的KAMA状态
    g.kama_val = kama_vals[-1] if not np.isnan(kama_vals[-1]) else np.nan
    g.prev_kama_up = kama_up_vals[-1] if not np.isnan(kama_vals[-1]) else False
    g.close_window = list(close_arr[-(g.kama_n + 1):])  # 保留最近 n+1 根收盘价

    # 交易信号（None / 'buy' / 'sell'）
    g.signal = None

    # 初始仓位状态
    g.position = 0  # 0=空仓, 1=满仓

    log.info("KAMA预热完成: KAMA值=%.4f, 方向=%s",
             g.kama_val, "上升" if g.prev_kama_up else "下降")
    log.info("策略参数: KAMA_N=%d, FASTEST=%d, SLOWEST=%d",
             g.kama_n, g.kama_fastest, g.kama_slowest)

    # 初始状态修正：如果预热后KAMA已处于上升状态，回测首日强制买入建仓
    g.need_init_buy = False
    if g.prev_kama_up:
        g.signal = 'buy'          # 回测首日直接生成买入信号
        g.need_init_buy = True    # 标记初始建仓，防止generate_signal覆盖
        log.info("KAMA预热方向为上升，回测首日将直接买入建仓")
    else:
        log.info("KAMA预热方向为下降，回测首日保持空仓等待信号")

    # 注册定时任务
    run_daily(generate_signal, '9:00')   # 开盘前生成信号
    run_daily(check_and_trade, '9:35')   # 开盘执行交易



# ============================================================================
# 核心函数：KAMA计算（复刻同花顺公式）
# ============================================================================

def calc_kama(close, n=20, fastest=2, slowest=30):
    """
    计算考夫曼自适应移动平均线（KAMA），复刻同花顺公式

    DIR = |CLOSE - REF(CLOSE, n)|
    VIR = SUM(|CLOSE - REF(CLOSE, 1)|, n)
    ER  = DIR / VIR
    CS  = ER * (2/(fastest+1) - 2/(slowest+1)) + 2/(slowest+1)
    CQ  = CS^2
    KAMA[i] = KAMA[i-1] + CQ * (CLOSE[i] - KAMA[i-1])

    返回: (kama, kama_up, er)
        kama:    KAMA值数组
        kama_up: 布尔数组，KAMA上升时为True（AMA1可见）
        er:      效率比率数组
    """
    close = np.asarray(close, dtype=float)
    length = len(close)

    # DIR = |CLOSE - REF(CLOSE, n)|
    dir_arr = np.abs(close - np.roll(close, n))
    dir_arr[:n] = 0

    # VIR = SUM(|CLOSE - REF(CLOSE, 1)|, n)
    d = np.diff(close)
    abs_diff = np.abs(np.concatenate([[0], d]))
    vir_arr = pd.Series(abs_diff).rolling(window=n, min_periods=n).sum().values

    # ER = DIR / VIR
    er_arr = np.divide(dir_arr, vir_arr, out=np.zeros_like(dir_arr), where=vir_arr > 1e-12)

    # CS = ER * (fastest_SC - slowest_SC) + slowest_SC
    fastest_sc = 2.0 / (fastest + 1)
    slowest_sc = 2.0 / (slowest + 1)
    cs_arr = er_arr * (fastest_sc - slowest_sc) + slowest_sc

    # CQ = CS^2
    cq_arr = cs_arr * cs_arr

    # KAMA递归
    kama = np.full(length, np.nan)
    if length >= n:
        kama[n - 1] = np.mean(close[:n])
    for i in range(n, length):
        kama[i] = kama[i - 1] + cq_arr[i] * (close[i] - kama[i - 1])

    # KAMA方向判别（同花顺AMA1逻辑）
    kama_shift = np.roll(kama, 1)
    kama_shift[0] = np.nan
    kama_up = kama > kama_shift

    return kama, kama_up, er_arr


def calc_kama_incremental(close, kama_prev, n, fastest, slowest):
    """
    KAMA增量递推：已知前一天KAMA值，用当天收盘价计算新KAMA值

    参数:
        close:     最近 n+1 根收盘价（用于计算DIR、VIR、ER）
        kama_prev: 前一天的KAMA值
        n, fastest, slowest: KAMA参数

    返回: (kama_new, kama_up, er)
    """
    close = np.asarray(close, dtype=float)
    length = len(close)
    if length < n + 1 or np.isnan(kama_prev):
        return kama_prev, False, 0.0

    # DIR = |CLOSE[-1] - CLOSE[-(n+1)]|
    dir_val = abs(close[-1] - close[-(n + 1)])

    # VIR = SUM(|CLOSE[i] - CLOSE[i-1]|, 最近n根)
    vir_val = np.sum(np.abs(np.diff(close[-n - 1:])))

    # ER
    er = dir_val / vir_val if vir_val > 1e-12 else 0.0

    # CS, CQ
    fastest_sc = 2.0 / (fastest + 1)
    slowest_sc = 2.0 / (slowest + 1)
    cs = er * (fastest_sc - slowest_sc) + slowest_sc
    cq = cs * cs

    # KAMA递推
    kama_new = kama_prev + cq * (close[-1] - kama_prev)

    # 方向判别
    kama_up = kama_new > kama_prev

    return kama_new, kama_up, er


def generate_signal(context):
    """
    每天9:00开盘前执行：
    用前一交易日收盘价计算KAMA，生成当日交易信号
    """
    # 如果是初始建仓日，不覆盖initialize中设置的买入信号
    if g.need_init_buy:
        g.need_init_buy = False
        log.info("[初始建仓] 跳过首次信号生成，保留买入信号")
        return

    # 用attribute_history获取历史收盘数据
    df = attribute_history(
        g.security,
        g.kama_n + 2,
        unit='1d',
        fields=['close'],
        df=True
    )

    if df is None or len(df) < g.kama_n + 1:
        log.warn("数据不足，跳过信号生成")
        return

    close_arr = df['close'].values
    last_date = df.index[-1].strftime('%Y-%m-%d')  # 前一交易日

    # 增量计算KAMA
    kama_new, kama_up, er = calc_kama_incremental(
        close_arr,
        g.kama_val,
        g.kama_n,
        g.kama_fastest,
        g.kama_slowest
    )

    if np.isnan(kama_new):
        log.warn("KAMA计算结果无效，跳过")
        return

    # 生成信号
    old_kama_up = g.prev_kama_up
    g.prev_kama_up = kama_up
    g.kama_val = kama_new
    g.close_window = list(close_arr[-(g.kama_n + 1):])

    if kama_up and not old_kama_up:
        # KAMA由跌转涨 → 买入信号
        g.signal = 'buy'
        log.info("[%s] KAMA由跌转涨 → 生成买入信号 (KAMA=%.4f, ER=%.4f)",
                 last_date, kama_new, er)
    elif not kama_up and old_kama_up:
        # KAMA由涨转跌 → 卖出信号
        g.signal = 'sell'
        log.info("[%s] KAMA由涨转跌 → 生成卖出信号 (KAMA=%.4f, ER=%.4f)",
                 last_date, kama_new, er)
    else:
        g.signal = None
        log.info("[%s] KAMA方向未变化，无信号 (KAMA=%.4f, 方向=%s)",
                 last_date, kama_new, "上升" if kama_up else "下降")


def check_and_trade(context):
    """
    每天9:35执行：
    根据前一日收盘生成的交易信号进行买卖
    """
    signal = g.signal

    if signal is None:
        return

    today_str = context.current_dt.strftime('%Y-%m-%d')
    current_value = context.portfolio.total_value

    if signal == 'buy':
        if g.position == 1:
            log.info("[%s] 已持仓，忽略买入信号", today_str)
            g.signal = None
            return
        # 满仓买入（留1%现金避免精度问题）
        target_value = current_value * 0.99
        order_target_value(g.security, target_value)
        g.position = 1
        log.info("[%s] 执行买入: 买入金额=%.2f", today_str, target_value)

    elif signal == 'sell':
        if g.position == 0:
            log.info("[%s] 已空仓，忽略卖出信号", today_str)
            g.signal = None
            return
        # 清仓卖出
        order_target(g.security, 0)
        g.position = 0
        log.info("[%s] 执行卖出: 清仓", today_str)

    # 清空信号
    g.signal = None
