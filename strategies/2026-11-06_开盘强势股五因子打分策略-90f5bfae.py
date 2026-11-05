# Clone from JoinQuant
# postId: 90f5bfaea24eebee91909603e453202a
# backtestId: 88cd1392c4781c40c25f4007c0085bb0
# title: 开盘强势股五因子打分策略




from jqdata import *
import datetime
import pandas as pd
import numpy as np


def calc_ema(data, period):
    """计算EMA（指数移动平均）"""
    if len(data) < period:
        return np.mean(data) if len(data) > 0 else 0
    ema = np.zeros(len(data))
    ema[0] = data[0]
    alpha = 2 / (period + 1)
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    return ema[-1]


def calc_atr(high, low, close, period=14):
    """计算ATR（平均真实波幅）"""
    if len(high) < period + 1:
        return np.mean(high - low) if len(high) > 0 else 0
    tr_list = []
    for i in range(1, len(high)):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr_list.append(max(hl, hc, lc))
    if len(tr_list) >= period:
        return np.mean(tr_list[-period:])
    return np.mean(tr_list) if tr_list else 0


def calc_adx(high, low, close, n=14, m=6):
    """计算ADX、+DI、-DI（简化版，返回ADX, PDI, MDI）"""
    if len(high) < n + m:
        return 0, 0, 0
    tr_list = []
    for i in range(1, len(high)):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr_list.append(max(hl, hc, lc))
    plus_dm = []
    minus_dm = []
    for i in range(1, len(high)):
        hd = high[i] - high[i - 1]
        ld = low[i - 1] - low[i]
        plus_dm.append(hd if (hd > 0 and hd > ld) else 0)
        minus_dm.append(ld if (ld > 0 and ld > hd) else 0)
    tr_sum = np.sum(tr_list[-n:]) if len(tr_list) >= n else 1
    plus_sum = np.sum(plus_dm[-n:]) if len(plus_dm) >= n else 0
    minus_sum = np.sum(minus_dm[-n:]) if len(minus_dm) >= n else 0
    pdi = (plus_sum / tr_sum) * 100 if tr_sum > 0 else 0
    mdi = (minus_sum / tr_sum) * 100 if tr_sum > 0 else 0
    dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
    return dx, pdi, mdi


def calc_five_factor_score(stock, date):
    """
    计算单只股票的五因子得分（基于date之前的数据）
    返回：total_score, score1~score5 明细
    """
    try:
        hist = get_price(stock, end_date=date, count=60,
                         fields=['close', 'high', 'low', 'volume'],
                         fq='pre', skip_paused=True)
        if len(hist) < 60:
            return 0, 0, 0, 0, 0, 0

        close = hist['close'].values
        high = hist['high'].values
        low = hist['low'].values
        volume = hist['volume'].values

        # 因子1：MA多头排列（MA5>MA20>MA60）
        ma5 = np.mean(close[-5:])
        ma20 = np.mean(close[-20:])
        ma60 = np.mean(close[-60:])
        score1 = 1 if (ma5 > ma20 and ma20 > ma60) else 0

        # 因子2：MACD零轴上方（DIF>0）
        dif = calc_ema(close, 12) - calc_ema(close, 26)
        score2 = 1 if dif > 0 else 0

        # 因子3：ADX>25 且 +DI>-DI
        adx, pdi, mdi = calc_adx(high, low, close, n=14, m=6)
        score3 = 1 if (adx > 25 and pdi > mdi) else 0

        # 因子4：量能放大（昨日成交量 > 20日均量*1.2）
        vol_ma20 = np.mean(volume[-20:])
        score4 = 1 if (volume[-1] > vol_ma20 * 1.2) else 0

        # 因子5：低ATR（ATR14 < ATR14的20日均值）
        atr14 = calc_atr(high, low, close, 14)
        atr_history = []
        for i in range(20, len(close)):
            atr_history.append(calc_atr(high[:i + 1], low[:i + 1], close[:i + 1], 14))
        if len(atr_history) >= 20:
            atr_ma20 = np.mean(atr_history[-20:])
            score5 = 1 if (atr14 < atr_ma20) else 0
        else:
            score5 = 0

        total = score1 + score2 + score3 + score4 + score5
        return total, score1, score2, score3, score4, score5
    except Exception as e:
        return 0, 0, 0, 0, 0, 0


# ==================== 辅助函数（保持不变） ====================
def get_dynamic_max_hold(total_asset):
    if total_asset < 100000:
        return 2, 2
    elif 100000 <= total_asset < 300000:
        return 3, 3
    elif 300000 <= total_asset < 1000000:
        return 4, 4
    elif 1000000 <= total_asset < 5000000:
        return 5, 5
    else:
        return 8, 8


def get_stock_board(stock):
    try:
        code = stock.split('.')[0]
        suffix = stock.split('.')[1] if '.' in stock else ''
        if (code.startswith('60') and suffix == 'XSHG') or \
                ((code.startswith('000') or code.startswith('001')) and suffix == 'XSHE'):
            return 'main'
        elif code.startswith(('300', '301', '302')) and suffix == 'XSHE':
            return 'gem'
        elif code.startswith('688') and suffix == 'XSHG':
            return 'star'
        else:
            return 'unknown'
    except Exception as e:
        log.warn(f"判断{stock}板块失败: {str(e)[:20]}")
        return 'unknown'


def calculate_continuous_gain(stock, end_date, days):
    try:
        hist = get_price(stock, end_date=end_date, count=days + 1, fields=['close'], fq='pre', skip_paused=True)
        if len(hist) < days + 1:
            return -999
        start_price = hist['close'].iloc[0]
        end_price = hist['close'].iloc[-1]
        total_gain = (end_price - start_price) / start_price * 100
        return round(total_gain, 2)
    except Exception as e:
        log.warn(f"计算{stock}连续{days}天涨幅失败: {str(e)[:20]}")
        return -999


def filter_by_continuous_gain(stock, end_date):
    try:
        stock_name = get_security_info(stock).display_name
    except:
        stock_name = "未知名称"
    board = get_stock_board(stock)
    if board == 'main':
        check_days = 5
        max_gain = 60.0
    elif board in ['gem', 'star']:
        check_days = 3
        max_gain = 72.0
    else:
        return True, "未知板块，跳过涨幅过滤", stock_name
    total_gain = calculate_continuous_gain(stock, end_date, check_days)
    if total_gain == -999:
        return True, f"无法计算{check_days}天涨幅，跳过过滤", stock_name
    elif total_gain > max_gain:
        return False, f"{board}连续{check_days}天涨幅{total_gain}% > {max_gain}%", stock_name
    else:
        return True, f"{board}连续{check_days}天涨幅{total_gain}% <= {max_gain}%", stock_name


def filter_after_1430_gain(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        gain_thresholds = {'main': 5.0, 'gem': 8.0, 'star': 8.0}
        if board not in gain_thresholds:
            return True, "未知板块，跳过尾盘涨幅过滤", stock_name
        date_obj = pd.Timestamp(date)
        time_1430 = pd.Timestamp.combine(date_obj.date(), pd.Timestamp('14:30:00').time())
        end_time = pd.Timestamp.combine(date_obj.date(), pd.Timestamp('15:00:00').time())
        min1_data = get_price(stock, start_date=time_1430, end_date=end_time, frequency='1m', fields=['close'],
                              fq='pre', skip_paused=True)
        if min1_data.empty or len(min1_data) < 2:
            min5_data = get_price(stock, start_date=time_1430, end_date=end_time, frequency='5m', fields=['close'],
                                  fq='pre', skip_paused=True)
            if min5_data.empty or len(min5_data) < 2:
                daily_data = get_price(stock, end_date=date, count=1, fields=['open', 'close'], fq='pre')
                if daily_data.empty:
                    return True, "无尾盘数据，默认通过", stock_name
                price_1430 = daily_data['open'].iloc[0]
                price_close = daily_data['close'].iloc[0]
            else:
                price_1430 = min5_data['close'].iloc[0]
                price_close = min5_data['close'].iloc[-1]
        else:
            price_1430 = min1_data['close'].iloc[0]
            price_close = min1_data['close'].iloc[-1]
        gain = (price_close - price_1430) / price_1430 * 100
        gain = round(gain, 2)
        threshold = gain_thresholds[board]
        if gain > threshold:
            log.error(f"[淘汰] 尾盘过滤淘汰: {stock} {stock_name} | {board} | 14:30后涨幅{gain}% > {threshold}%")
            return False, f"{board}14:30后涨幅{gain}% > {threshold}%", stock_name
        else:
            return True, f"{board}14:30后涨幅{gain}% <= {threshold}%", stock_name
    except Exception as e:
        return True, f"过滤异常({str(e)[:20]})，默认通过", "未知名称"


def filter_by_amplitude(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        amp_thresholds = {'main': 16.0, 'gem': 20.0, 'star': 20.0}
        if board not in amp_thresholds:
            return True, "未知板块，跳过振幅过滤", stock_name
        hist = attribute_history(stock, 1, '1d', fields=['high', 'low', 'close'], skip_paused=True, df=True)
        if hist.empty:
            return True, "无振幅数据", stock_name
        high = hist['high'].iloc[-1]
        low = hist['low'].iloc[-1]
        close = hist['close'].iloc[-1]
        if close == 0:
            return True, "昨日收盘价为0", stock_name
        amplitude = (high - low) / close * 100
        amplitude = round(amplitude, 2)
        threshold = amp_thresholds[board]
        if amplitude >= threshold:
            return False, f"{board}昨日振幅{amplitude}% >= {threshold}%", stock_name
        else:
            return True, f"{board}昨日振幅{amplitude}% < {threshold}%", stock_name
    except Exception as e:
        return True, f"振幅异常({str(e)[:20]})", stock_name


def filter_by_turnover(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        turnover_thresholds = {'main': 24.0, 'gem': 28.0, 'star': 28.0}
        if board not in turnover_thresholds:
            return True, "未知板块，跳过换手率过滤", stock_name
        threshold = turnover_thresholds[board]
        turnover = None
        try:
            turnover_df = get_money_flow(stock, start_date=date, end_date=date)
            if not turnover_df.empty and 'turnover_rate' in turnover_df.columns:
                turnover = turnover_df['turnover_rate'].iloc[0]
        except:
            pass
        if turnover is None:
            try:
                vol_data = attribute_history(stock, 1, '1d', fields=['volume'], skip_paused=True, df=True)
                if vol_data.empty:
                    return False, "无成交量数据", stock_name
                volume = vol_data['volume'].iloc[-1]
                q = query(valuation.circulating_cap).filter(valuation.code == stock)
                df = get_fundamentals(q, date=date)
                if df.empty:
                    return False, "无流通股本", stock_name
                float_share = df['circulating_cap'].iloc[0] * 10000
                if float_share <= 0:
                    return False, "流通股本异常", stock_name
                turnover = volume / float_share * 100
            except:
                return False, "计算异常", stock_name
        if turnover is None:
            return False, "无法获取换手率", stock_name
        turnover = round(float(turnover), 2)
        if turnover >= threshold:
            return False, f"{board}昨日换手率{turnover}% >= {threshold}%", stock_name
        else:
            return True, f"{board}昨日换手率{turnover}% < {threshold}%", stock_name
    except Exception as e:
        log.error(f"换手率过滤异常 {stock}: {str(e)[:50]}")
        return False, "过滤异常", stock_name


def is_double_in_month(stock, context):
    try:
        hist = attribute_history(stock, 20, '1d', fields=['close'], skip_paused=True, df=True)
        if len(hist) < 20:
            return False
        old_price = hist['close'].iloc[0]
        today_price = hist['close'].iloc[-1]
        if old_price <= 0:
            return False
        gain = (today_price - old_price) / old_price * 100
        return gain >= 95
    except:
        return False


def has_limit_down_in_last_3days(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        hist = attribute_history(stock, 3, '1d', fields=['close', 'low_limit'], skip_paused=True, df=True)
        if len(hist) < 3:
            return True, "无足够数据", stock_name
        for i in range(len(hist)):
            close = hist['close'].iloc[i]
            low_limit = hist['low_limit'].iloc[i]
            if close <= low_limit * 1.005:
                return False, "近3日有跌停", stock_name
        return True, "近3日无跌停", stock_name
    except:
        return True, "跌停异常", stock_name


# ==================== ★ 新增：参数化的涨停次数过滤函数 ====================
def has_limit_up_recently(stock, date, days=None, threshold=None):
    """
    判断股票在最近 days 个交易日内（不包括date当天）是否至少有 threshold 次涨停
    返回 True 表示需要过滤掉（即涨停次数>=threshold）
    若未传参，则从 g 中读取
    """
    if days is None:
        days = g.limit_up_check_days
    if threshold is None:
        threshold = g.limit_up_threshold

    try:
        # 取 date 及之前 days+1 个交易日（确保有 days 个历史日）
        trade_days = get_trade_days(end_date=date, count=days + 1)
        if len(trade_days) < days + 1:
            return False  # 数据不足，不过滤
        # 排除 date 当天，取前 days 个交易日
        hist_dates = trade_days[:-1]
        limit_up_count = 0
        for d in hist_dates:
            if is_limit_up_simple(stock, d):
                limit_up_count += 1
                if limit_up_count >= threshold:
                    return True
        return False
    except Exception:
        return False  # 异常时不过滤


# ==================== 原有函数（未改动） ====================
def is_continuous_shrink_rise(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        hist = attribute_history(stock, 3, '1d', fields=['close', 'volume'], skip_paused=True, df=True)
        if len(hist) < 3:
            return True, "无足够数据", stock_name
        for i in range(1, 3):
            if hist['close'].iloc[i] <= hist['close'].iloc[i - 1]:
                return True, "非连续上涨", stock_name
        for i in range(1, 3):
            if hist['volume'].iloc[i] >= hist['volume'].iloc[i - 1]:
                return True, "非连续缩量", stock_name
        return False, "连续3日缩量上涨", stock_name
    except:
        return True, "缩量异常", stock_name


# ==================== ★ 修改点1：sell_only_930 加入紧急队列并增加返回值日志（移除动态仓位调用） ====================
def sell_only_930(context):
    log.info("=== 9:30 专属卖出开始 ===")
    log.info(f"[资金] 卖出前可用资金：{context.portfolio.available_cash:.2f}")
    # ★ 修改：不再动态更新 g.max_stock_num 和 g.max_buy_per_day，直接使用盘前设定值
    check_break_limit_drop(context)
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        try:
            current_data = get_current_data()[stock]
            hl = current_data.high_limit
            op = current_data.day_open
            if op is None or op <= 0 or hl is None or hl <= 0:
                continue
            # ★ 新增：若开盘价接近跌停（跌停开盘），则加入紧急队列，不卖出
            low_limit = current_data.low_limit
            if low_limit and abs(op - low_limit) / low_limit < 0.01:
                if stock not in g.emergency_sell_stocks:
                    g.emergency_sell_stocks.append(stock)
                log.info(f"[延迟卖出] {stock} 开盘跌停，加入紧急队列，等待打开")
                continue
            # 正常未涨停则卖出
            # ★ 隔日模式：开盘清仓只在只卖日执行；只买日隔夜仓保留、走其余原逻辑
            if g.only_sell_today and abs(op - hl) / hl > 0.005:
                log.info("[卖出] 9:30 开盘未涨停卖出：" + stock)
                # ★ 增加返回值判断，便于调试
                if not execute_sell(stock, context):
                    log.info(f"[卖出失败] {stock} 开盘未涨停卖出失败，已加入紧急队列")
        except:
            continue
    sell_decision(context)
    log.info(f"[资金] 卖出后可用资金：{context.portfolio.available_cash:.2f}")
    log.info("=== 9:30 卖出全部完成 ===")


# ==================== ★ 修改二：放宽持有天数限制（修改 check_break_limit_drop_for_long_hold） ====================
def check_break_limit_drop_for_long_hold(context):
    for stock in list(context.portfolio.positions.keys()):
        hold_days = g.hold_days.get(stock, 0)
        # ★ 修改：只跳过今日买入（0天），允许持有1天及以上的进入检查（原来是 <= 1）
        if hold_days <= 0:
            continue
        try:
            current_price, _ = get_realtime_price(context, stock)
            today_high = get_intraday_high_since_open(context, stock)
            high_limit = get_current_data()[stock].high_limit
            if current_price is None or current_price <= 0 or today_high <= 0 or high_limit is None or high_limit <= 0:
                continue
            if today_high >= high_limit * 0.995:
                g.has_limit_up.add(stock)
            if stock in g.has_limit_up:
                drop_ratio = (today_high - current_price) / today_high * 100
                if drop_ratio >= g.break_drop_ratio:
                    execute_sell(stock, context)
                    if stock not in g.break_limit_sold_stocks:
                        g.break_limit_sold_stocks.append(stock)
        except:
            continue


def check_break_limit_drop(context):
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        try:
            current_price, _ = get_realtime_price(context, stock)
            today_high = get_intraday_high_since_open(context, stock)
            high_limit = get_current_data()[stock].high_limit
            if current_price is None or current_price <= 0 or today_high <= 0 or high_limit is None or high_limit <= 0:
                continue
            if today_high >= high_limit * 0.995:
                g.has_limit_up.add(stock)
            if stock in g.has_limit_up:
                drop_ratio = (today_high - current_price) / today_high * 100
                if drop_ratio >= g.break_drop_ratio:
                    execute_sell(stock, context)
                    if stock not in g.break_limit_sold_stocks:
                        g.break_limit_sold_stocks.append(stock)
        except:
            continue


# ==================== ★ 修改 initialize：新增固定/动态仓位开关 + 订单推送初始化 ====================
def initialize(context):
    context.order_cost = OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5
    )
    g.debug = True
    g.max_stock_num = 3
    g.max_buy_per_day = 3
    g.base_min_open_ratio = 0
    g.base_max_open_ratio = 8.0
    g.base_stop_loss_ratio = -4.0
    g.base_stop_profit_ratio = 19.0
    g.base_max_hold_days = 3
    g.base_break_drop_ratio = 1.5
    g.base_min_turnover_rate = 2
    g.base_min_volume_ratio = 1.2
    g.ma_period = 5
    g.base_min_limit_up_time = 90
    g.base_min_volume_growth = 0.5

    # 五因子过滤阈值
    g.five_factor_threshold = 1

    # ★ 新增：涨停次数过滤参数（近N天有M次涨停则过滤）
    g.limit_up_check_days = 3  # 检查最近几天
    g.limit_up_threshold = 2  # 涨停次数阈值（>=此值即过滤）

    # ★ 新增：固定/动态仓位开关（默认固定2只均仓）
    g.use_dynamic_position = False  # True=动态（按资产规模调整），False=固定
    g.fixed_stock_num = 2  # 固定模式下的持仓数量和单日买入数
    g.max_stock_num = g.fixed_stock_num
    g.max_buy_per_day = g.fixed_stock_num

    # 原有变量
    g.risk_filter_count = 0
    g.auction_drop_count = 0
    g.weak_limitup_count = 0
    g.total_filtered = 0

    g.min_open_ratio = g.base_min_open_ratio
    g.max_open_ratio = g.base_max_open_ratio
    g.stop_loss_ratio = g.base_stop_loss_ratio
    g.stop_profit_ratio = g.base_stop_profit_ratio
    g.max_hold_days = g.base_max_hold_days
    g.break_drop_ratio = g.base_break_drop_ratio
    g.min_turnover_rate = g.base_min_turnover_rate
    g.min_volume_ratio = g.base_min_volume_ratio
    g.min_limit_up_time = g.base_min_limit_up_time
    g.min_volume_growth = g.base_min_volume_growth

    g.candidate_stocks = []
    g.hold_days = {}
    g.has_limit_up = set()
    g.bought_stocks = set()
    g.rebuy_candidates = []
    g.bought_today_count = 0
    g.market_env = "normal"
    g.only_buy = False
    g.break_limit_sold_stocks = []
    g.sold_today = []
    g.sold_today_stock_codes = set()
    g.has_touched_limit_down = set()
    g.filtered_stocks = []

    # ★ 新增：紧急卖出队列和买入开关
    g.emergency_sell_stocks = []
    g.emergency_processed = False
    g.buy_enabled = False

    # ★ 新增（2026-10-18）：隔日买卖模式状态——奇数交易日只买、偶数交易日只卖，
    #   每日由 before_market_open 按交易日计数刷新
    g.trade_day_counter = 0
    g.cycle_date = None
    g.only_buy_today = True
    g.only_sell_today = False

    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_slippage(PriceRelatedSlippage(0.002))
    # ★ 2026-10-18 内存优化第二档：关闭数据缓存（聚宽官方接口，专为内存超限场景）。
    #   代价是回测明显变慢；若开启后内存仍超限被杀，则占用不来自数据缓存，需另行排查
    disable_cache()

    # 定时任务
    run_daily(before_market_open, time='before_open')
    run_daily(auction_filter, time='09:28:00')
    run_daily(set_only_buy_False, time='09:30:00')
    run_daily(sell_only_930, time='09:30:01')
    # ★ 2026-10-18 买入时点平移到 9:30:40：开盘后观察40秒盘口再判定，限价单=tick+2跳；
    #   时窗分支上限同步 9:30:47，撮合口径不变（9:31:00 前限价单按开盘价+滑点成交）
    run_daily(set_only_buy_True, time='09:30:40')
    run_daily(market_open, time='09:30:40')
    run_daily(market_open, time='09:31:00')
    run_daily(market_open, time='09:32:00')
    run_daily(market_open, time='09:37')
    run_daily(market_open, time='10:29')
    run_daily(after_market_close, time='after_close')

    # 长期持仓的破板检测（每2分钟）
    for hour in range(10, 15):
        for minute in range(0, 60, 2):
            if (hour == 10 and minute < 20) or (hour == 14 and minute >= 56):
                continue
            time_str = f"{hour:02d}:{minute:02d}"
            run_daily(check_break_limit_drop_for_long_hold, time=time_str)

    # ★ 修改：重试卖出改为从09:40起每10分钟一次
    for hour in range(9, 15):
        for minute in range(40, 60, 10):
            if hour == 14 and minute > 50:
                break
            time_str = f"{hour:02d}:{minute:02d}"
            run_daily(retry_sell_limit_down_stocks, time=time_str)


# ==================== 辅助函数（未改动） ====================
def get_prev_trade_date(context):
    try:
        return context.previous_date
    except:
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) >= 2:
            return trade_days[0]
        return context.current_dt.date() - datetime.timedelta(days=1)


def get_realtime_price(context, stock):
    try:
        t = context.current_dt.time()
        if datetime.time(9, 30, 0) <= t <= datetime.time(9, 30, 47):
            tick_price, tick_msg = get_tick_b1_price_at_93006(context, stock)
            if tick_price is not None and tick_price > 0:
                return tick_price, tick_msg
        current_data = get_current_data()[stock]
        if current_data.last_price is not None and current_data.last_price > 0:
            return float(current_data.last_price), "last_price"
        if current_data.day_open is not None and current_data.day_open > 0:
            return float(current_data.day_open), "day_open兜底"
        return None, "实时价格无效"
    except Exception as e:
        return None, "实时价格异常:%s" % str(e)[:30]


def get_intraday_high_since_open(context, stock):
    try:
        current_data = get_current_data()[stock]
        price, _ = get_realtime_price(context, stock)
        high_price = 0.0
        if current_data.day_open is not None and current_data.day_open > 0:
            high_price = max(high_price, float(current_data.day_open))
        if price is not None and price > 0:
            high_price = max(high_price, float(price))
        if context.current_dt.time() >= datetime.time(9, 31, 0):
            query_date = context.current_dt.date()
            start_dt = datetime.datetime.combine(query_date, datetime.time(9, 31, 0))
            min_data = get_price(stock, start_date=start_dt, end_date=context.current_dt, frequency='1m',
                                 fields=['high'], fq='pre', skip_paused=True)
            if min_data is not None and len(min_data) > 0:
                high_price = max(high_price, float(min_data['high'].max()))
        return high_price
    except:
        return 0.0


def get_intraday_volume_since_open(context, stock):
    try:
        if context.current_dt.time() < datetime.time(9, 31, 0):
            return 0.0
        query_date = context.current_dt.date()
        start_dt = datetime.datetime.combine(query_date, datetime.time(9, 31, 0))
        min_data = get_price(stock, start_date=start_dt, end_date=context.current_dt, frequency='1m', fields=['volume'],
                             fq='pre', skip_paused=True)
        if min_data is None or len(min_data) == 0:
            return 0.0
        return float(min_data['volume'].sum())
    except:
        return 0.0


def get_tick_b1_price_at_93006(context, stock):
    try:
        query_date = context.current_dt.date()
        start_dt = datetime.datetime.combine(query_date, datetime.time(9, 30, 0))
        # ★ 2026-10-18 前视修复：窗口截止由固定 9:30:07 夹到当前时刻——原实现在 9:30:01
        #   卖出路径上会提前取到 9:30:40 的 tick（秒级前视）；9:30:40 买入路径行为不变
        end_dt = context.current_dt
        ticks_df = get_ticks(stock, start_dt=start_dt, end_dt=end_dt, fields=['time', 'b1_p', 'current'], skip=False,
                             df=True)
        if ticks_df is None or len(ticks_df) == 0:
            return None, "09:30:40无tick"
        time_str = ticks_df['time'].astype(str)
        result = ticks_df[time_str.str.contains('093040', na=False)]
        if len(result) > 0:
            row = result.iloc[0]
            msg = "精确09:30:40"
        else:
            row = ticks_df.iloc[-1]
            msg = "无精确06秒，取最近快照"
        price = None
        if 'current' in ticks_df.columns and pd.notnull(row['current']) and float(row['current']) > 0:
            price = float(row['current'])
        elif 'b1_p' in ticks_df.columns and pd.notnull(row['b1_p']) and float(row['b1_p']) > 0:
            price = float(row['b1_p'])
            msg += "，无成交价改用买一价"
        if price is None or price <= 0:
            return None, "tick价格无效"
        return price, msg
    except Exception as e:
        return None, "tick获取异常:%s" % str(e)[:30]


# ★ 新增：获取最近30秒内最新tick价格
def get_latest_tick_price(stock, context):
    """获取最近30秒内最新的有效tick价格（current或b1_p）"""
    try:
        end_dt = context.current_dt
        start_dt = end_dt - datetime.timedelta(seconds=30)
        ticks = get_ticks(stock, start_dt=start_dt, end_dt=end_dt,
                          fields=['time', 'current', 'b1_p'], skip=False, df=True)
        if ticks is None or len(ticks) == 0:
            return None
        ticks = ticks.sort_values('time', ascending=False)
        for _, row in ticks.iterrows():
            price = row['current'] if pd.notnull(row['current']) and row['current'] > 0 else row['b1_p']
            if pd.notnull(price) and price > 0:
                return float(price)
        return None
    except:
        return None


def is_real_time_drop(context, stock):
    try:
        stock_name = get_security_info(stock).display_name
        current_data = get_current_data()[stock]
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return False, "无昨日数据"
        yesterday_close = get_price(stock, end_date=trade_days[0], count=1, fields=['close'], fq='pre')['close'].iloc[0]
        open_price = current_data.day_open
        tick_price, tick_msg = get_tick_b1_price_at_93006(context, stock)
        if tick_price is None or tick_price <= 0:
            return False, "无09:30:40附近tick价，不做高开低走判断"
        judge_price = tick_price
        if open_price <= 0 or judge_price <= 0:
            return False, "价格异常"
        open_ratio = (open_price - yesterday_close) / yesterday_close * 100
        drop_ratio = (open_price - judge_price) / open_price * 100
        if open_ratio > 0 and judge_price < open_price and drop_ratio > 0.3:
            log.info(
                f"[淘汰] 09:30:40高开低走：{stock} {stock_name} 高开{open_ratio:.1f}%，{tick_msg}回落{drop_ratio:.1f}%")
            return True, f"09:30:40回落{drop_ratio:.1f}%"
        return False, f"高开{open_ratio:.1f}% | {tick_msg}"
    except:
        return False, "检测异常"


# ==================== 修改 set_only_buy_True 开启买入窗口 ====================
def set_only_buy_True(context):
    g.only_buy = True
    g.buy_enabled = True  # ★ 开启买入窗口（仅在09:30:40有效）
    log.info(f"当前时间{context.current_dt.time()}，设置为【仅买入模式】，买入窗口已开启")


def set_only_buy_False(context):
    g.only_buy = False
    log.info(f"当前时间{context.current_dt.time()}，设置为【先卖后买模式】")


# ==================== 其余辅助函数（未改动） ====================
def adjust_params_by_market(context):
    try:
        yesterday = get_prev_trade_date(context)
        trade_days = get_trade_days(end_date=yesterday, count=2)
        if len(trade_days) < 2:
            g.market_env = "normal"
            return
        day_before_yesterday = trade_days[0]
        hs300_data = get_price('000300.XSHG', end_date=yesterday, count=1, fields=['close'], fq='pre')
        hs300_prev_data = get_price('000300.XSHG', end_date=day_before_yesterday, count=1, fields=['close'], fq='pre')
        if hs300_data.empty or hs300_prev_data.empty:
            g.market_env = "normal"
            return
        hs300_change = (hs300_data['close'].iloc[0] - hs300_prev_data['close'].iloc[0]) / hs300_prev_data['close'].iloc[
            0] * 100
        if yesterday is None:
            limit_up_count = 50
        else:
            all_stocks = [code for code in get_all_securities(['stock'], date=yesterday).index if '.BJ' not in code]
            # ★ 2026-10-18 批量优化：原逐股 500 次 is_limit_up_simple 改为批量判定（同口径）
            sample = all_stocks[:500]
            lu_set, _ = batch_scan_first_layer(sample, yesterday)
            limit_up_count = len(lu_set)
        if hs300_change > 1 and limit_up_count > 80:
            g.market_env = "bull"
            g.min_open_ratio = g.base_min_open_ratio + 1
            g.max_open_ratio = g.base_max_open_ratio - 1
            g.min_turnover_rate = g.base_min_turnover_rate + 1
            g.stop_profit_ratio = g.base_stop_profit_ratio + 2
        elif hs300_change < -1 and limit_up_count < 30:
            g.market_env = "bear"
            g.min_open_ratio = g.base_min_open_ratio - 0.5
            g.max_open_ratio = g.base_max_open_ratio + 1
            g.min_turnover_rate = g.base_min_turnover_rate - 0.5
            g.stop_loss_ratio = g.base_stop_loss_ratio + 1
        else:
            g.market_env = "normal"
            g.min_open_ratio = g.base_min_open_ratio
            g.max_open_ratio = g.base_max_open_ratio
            g.stop_loss_ratio = g.base_stop_loss_ratio
            g.stop_profit_ratio = g.base_stop_profit_ratio
            g.min_turnover_rate = g.base_min_turnover_rate
        log.info(
            f"市场环境：{g.market_env} | 开盘涨幅：{g.min_open_ratio}%~{g.max_open_ratio}% | 换手率：{g.min_turnover_rate}%")
    except Exception as e:
        log.warn(f"动态参数调整失败：{str(e)[:30]}")
        g.market_env = "normal"
        g.min_open_ratio = g.base_min_open_ratio
        g.max_open_ratio = g.base_max_open_ratio


def before_market_open(context):
    log.info("=" * 50)
    log.info("盘前选股开始: {}".format(context.current_dt.date()))
    # ★ 2026-10-18 隔日买卖模式：按交易日计数（按日期幂等，重复执行不会多计），
    #   奇数交易日只买不卖、偶数交易日只卖不买
    _today = context.current_dt.date()
    if getattr(g, 'cycle_date', None) != _today:
        g.cycle_date = _today
        g.trade_day_counter = getattr(g, 'trade_day_counter', 0) + 1
    g.only_buy_today = (g.trade_day_counter % 2 == 1)
    g.only_sell_today = (not g.only_buy_today)
    log.info("[隔日模式] 第{}个交易日 | 今日{}"
             .format(g.trade_day_counter, "只买日（隔夜仓照常管理，仅跳过开盘清仓）" if g.only_buy_today else "只卖日（不买入，开盘清仓照做）"))
    g.candidate_stocks = []
    g.has_limit_up.clear()
    g.bought_stocks.clear()
    g.rebuy_candidates = []
    g.bought_today_count = 0
    g.only_buy = False
    g.break_limit_sold_stocks = []
    g.sold_today = []
    g.sold_today_stock_codes.clear()
    g.has_touched_limit_down.clear()
    g.filtered_stocks = []
    # ★ 重置紧急队列相关
    g.emergency_sell_stocks = []
    g.emergency_processed = False
    g.buy_enabled = False
    if hasattr(g, 'checked_today'):
        del g.checked_today

    adjust_params_by_market(context)
    total_asset = context.portfolio.total_value
    # ★ 修改：根据开关决定是否动态调整仓位
    if g.use_dynamic_position:
        g.max_stock_num, g.max_buy_per_day = get_dynamic_max_hold(total_asset)
        log.info(f"盘前动态配置：总资产{total_asset:.2f} -> 最大持仓{g.max_stock_num}只，单日买入{g.max_buy_per_day}只")
    else:
        g.max_stock_num = g.fixed_stock_num
        g.max_buy_per_day = g.fixed_stock_num
        log.info(f"盘前固定配置（固定模式）：最大持仓{g.max_stock_num}只，单日买入{g.max_buy_per_day}只")

    yesterday = get_prev_trade_date(context)
    if yesterday is None:
        log.info("无昨日交易日，今日跳过选股")
        return

    current_tradable_stocks = [
        code for code in get_all_securities(['stock'], date=context.current_dt.date()).index
        if '.BJ' not in code
    ]
    current_tradable_stocks = [
        code for code in current_tradable_stocks
        if get_stock_board(code) in ("main")
    ]
    log.info("今日可交易A股数量: {}".format(len(current_tradable_stocks)))

    limit_up_stocks = []
    # ★ 2026-10-18 前视修复：ST/退市过滤改历史口径（get_st_set 批量取昨日标记）——
    #   原逐股用「今天」的股票名称判断，回测会在历史时点提前用上未来的 ST/退市信息
    st_set = get_st_set(current_tradable_stocks, yesterday)
    # ★ 2026-10-18 批量优化：第一层"昨日涨停/强势"由逐股 3000~6000 次 get_price 改为
    #   分块批量取数（回测内存超限的主因）；判定公式与逐股版完全一致，失败块自动退回逐股
    first_limit_up, first_strong = batch_scan_first_layer(current_tradable_stocks, yesterday)
    first_layer_set = first_limit_up | first_strong
    batch_size = 1000
    for i in range(0, len(current_tradable_stocks), batch_size):
        batch_stocks = current_tradable_stocks[i:i + batch_size]
        for stock in batch_stocks:
            try:
                if stock in st_set:
                    continue
                if stock in first_layer_set:
                    pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, yesterday)
                    if not pass_filter:
                        log.info(f"[淘汰] {stock} {stock_name} 涨幅过滤淘汰：{filter_msg}")
                        continue
                    pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, yesterday)
                    if not pass_1430_filter:
                        log.info(f"[淘汰] {stock} {stock_name} 尾盘涨幅过滤淘汰：{filter_1430_msg}")
                        continue
                    pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, yesterday)
                    if not pass_amp_filter:
                        log.info(f"[淘汰] {stock} {stock_name} 振幅过滤淘汰：{amp_msg}")
                        continue
                    pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, yesterday)
                    if not pass_turnover_filter:
                        log.info(f"[淘汰] {stock} {stock_name} 换手率过滤淘汰：{turnover_msg}")
                        continue
                    pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, yesterday)
                    if not pass_limitdown_filter:
                        log.info(f"[淘汰] {stock} {stock_name} 近3日跌停过滤淘汰：{limitdown_msg}")
                        continue
                    pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, yesterday)
                    if not pass_shrink_filter:
                        log.info(f"[淘汰] {stock} {stock_name} 连续3日缩量上涨过滤淘汰：{shrink_msg}")
                        continue
                    limit_up_stocks.append(stock)
            except Exception as e:
                log.warn("检查股票{}出错: {}".format(stock, str(e)[:30]))
                continue

    log.info("核心识别强势股(已过滤涨幅+尾盘急拉+振幅+换手+跌停+缩量): {}只".format(len(limit_up_stocks)))
    if len(limit_up_stocks) > 0:
        log.info("前30只强势股：")
        for stock in limit_up_stocks[:30]:
            try:
                stock_name = get_security_info(stock).display_name
                hist = get_price(stock, end_date=yesterday, count=2, fields=['close', 'high_limit'], fq='pre')
                if len(hist) >= 2:
                    change = (hist['close'].iloc[-1] - hist['close'].iloc[-2]) / hist['close'].iloc[-2] * 100
                    log.info(f"  {stock} {stock_name} | 昨日涨幅: {change:.2f}%")
            except:
                log.info(f"  {stock}（名称获取失败）")

    if len(limit_up_stocks) == 0:
        log.info("无强势股，尝试宽松识别...")
        limit_up_stocks = find_limit_up_loose(current_tradable_stocks[:1500], yesterday)
        log.info("宽松识别后强势股: {}只".format(len(limit_up_stocks)))
        if len(limit_up_stocks) > 0:
            log.info("前30只强势股：")
            for stock in limit_up_stocks[:30]:
                try:
                    stock_name = get_security_info(stock).display_name
                    log.info(f"  {stock} {stock_name}")
                except:
                    log.info(f"  {stock}（名称获取失败）")

    if len(limit_up_stocks) == 0:
        log.info("宽松识别仍无结果，尝试超宽松识别...")
        limit_up_stocks = find_limit_up_ultra_loose(current_tradable_stocks[:1500], yesterday)
        log.info("超宽松识别后强势股: {}只".format(len(limit_up_stocks)))
        if len(limit_up_stocks) > 0:
            log.info("前30只强势股：")
            for stock in limit_up_stocks[:30]:
                try:
                    stock_name = get_security_info(stock).display_name
                    log.info(f"  {stock} {stock_name}")
                except:
                    log.info(f"  {stock}（名称获取失败）")

    g.candidate_stocks = limit_up_stocks.copy()
    g.rebuy_candidates = limit_up_stocks.copy()


# ==================== ★ 修改 auction_filter：增加涨停次数过滤 ====================
def auction_filter(context):
    log.info("=" * 50)
    log.info("9:28 竞价过滤（按板块区分高开阈值+开盘涨幅区间过滤）")

    g.risk_filter_count = 0
    range_filter_count = 0
    total_filter_count = 0
    final_stocks = []
    yesterday = get_prev_trade_date(context)

    for stock in g.candidate_stocks:
        if not check_basic_quality(stock, context):
            total_filter_count += 1
            continue

        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知"

        # ★ 新增：近N天有M次涨停过滤（参数化）
        if has_limit_up_recently(stock, yesterday):
            log.info(
                f"[淘汰] {stock} {stock_name} | 近{g.limit_up_check_days}天内有{g.limit_up_threshold}次及以上涨停，过滤掉")
            total_filter_count += 1
            continue

        is_risk = False
        risk_reason = ""

        try:
            board = get_stock_board(stock)
            if board in ['gem', 'star']:
                open_threshold = 6.0
            elif board == 'main':
                open_threshold = 5.0
            else:
                open_threshold = 5.0

            hist = get_price(stock, end_date=yesterday, count=3, fields=['close', 'volume', 'high_limit'], fq='pre')
            current_data = get_current_data()[stock]
            open_price = current_data.day_open

            if open_price is None or open_price <= 0:
                is_risk = True
                risk_reason = "09:28仍无法获取有效开盘价"
                log.info(f"[淘汰] {stock} {stock_name} | 拦截原因：{risk_reason}")
                total_filter_count += 1
                continue

            if len(hist) < 2:
                is_risk = True
                risk_reason = "无昨日收盘价数据"
                log.info(f"[淘汰] {stock} {stock_name} | 拦截原因：{risk_reason}")
                total_filter_count += 1
                continue

            close_yest = hist['close'].iloc[-1]
            open_ratio = (open_price - close_yest) / close_yest * 100

            if not (g.min_open_ratio <= open_ratio <= g.max_open_ratio):
                is_risk = True
                range_filter_count += 1
                risk_reason = f"开盘涨幅{open_ratio:.1f}%，超出区间[{g.min_open_ratio}%,{g.max_open_ratio}%]"
                log.info(f"[淘汰] {stock} {stock_name} | 拦截原因：{risk_reason}")

            if not is_risk and len(hist) >= 3:
                vol_yest = hist['volume'].iloc[-1]
                vol_beyest = hist['volume'].iloc[-2]
                high_limit = hist['high_limit'].iloc[-1]
                is_limit_up = abs(close_yest - high_limit) / high_limit < 0.006
                is_vol_big = vol_yest >= vol_beyest * 1.8

                if is_limit_up and is_vol_big and open_ratio >= open_threshold:
                    is_risk = True
                    g.risk_filter_count += 1
                    risk_reason = f"涨停+放量+高开{open_ratio:.1f}%（{board}阈值{open_threshold}%）"
                    log.info(f"[淘汰] {stock} {stock_name} | 拦截原因：{risk_reason}")

        except Exception as e:
            is_risk = True
            risk_reason = f"过滤异常：{str(e)[:30]}"
            log.warn(f"[淘汰] {stock} {stock_name} | 拦截原因：{risk_reason}")

        if is_risk:
            total_filter_count += 1
        else:
            final_stocks.append(stock)

    # 五因子得分过滤（保持不变）
    log.info("=" * 50)
    log.info("【五因子得分过滤】开始对 %d 只候选股打分（阈值≥%d）" % (len(final_stocks), g.five_factor_threshold))

    five_factor_pass = []
    orig_count = len(final_stocks)

    for stock in final_stocks:
        try:
            stock_name = get_security_info(stock).display_name
        except:
            stock_name = "未知"

        total, s1, s2, s3, s4, s5 = calc_five_factor_score(stock, yesterday)

        if total >= g.five_factor_threshold:
            five_factor_pass.append(stock)
            log.info("[五因子通过] %s %s | 总分%d (MA:%d MACD:%d ADX:%d VOL:%d ATR:%d)"
                     % (stock, stock_name, total, s1, s2, s3, s4, s5))
        else:
            log.info("[五因子淘汰] %s %s | 总分%d (MA:%d MACD:%d ADX:%d VOL:%d ATR:%d)"
                     % (stock, stock_name, total, s1, s2, s3, s4, s5))

    final_stocks = five_factor_pass
    five_factor_filtered_count = orig_count - len(final_stocks)

    log.info("五因子过滤统计：候选 %d 只 → 通过 %d 只，淘汰 %d 只"
             % (orig_count, len(final_stocks), five_factor_filtered_count))

    g.candidate_stocks = final_stocks.copy()
    g.rebuy_candidates = final_stocks.copy()
    g.filtered_stocks = final_stocks.copy()

    log.info(f"[统计] 竞价过滤统计：")
    log.info(f"   |-- 涨幅区间拦截：{range_filter_count} 只")
    log.info(f"   |-- 风险股拦截：{g.risk_filter_count} 只")
    log.info(f"   |-- 其他异常拦截：{total_filter_count - range_filter_count - g.risk_filter_count} 只")
    log.info(f"   |-- 五因子过滤淘汰：{five_factor_filtered_count} 只")
    log.info(f"   +-- 最终候选股：{len(final_stocks)} 只")
    log.info("=" * 50)


# ==================== 下列函数（is_main_board ~ find_limit_up_ultra_loose）保持不变 ====================
def is_main_board(stock):
    try:
        code = stock.split('.')[0]
        suffix = stock.split('.')[1] if '.' in stock else ''
        if code.startswith('60') and suffix == 'XSHG':
            return True
        if (code.startswith('000') or code.startswith('001')) and suffix == 'XSHE':
            return True
        return False
    except:
        return False


def get_st_set(stock_list, date):
    """
    【2026-10-18 前视修复】批量取指定交易日的 ST/退市整理期标记集合（get_extras 历史口径）。
    原实现用 get_security_info().display_name 判断 ST/退——那是「今天」的名称，不随回测
    日期回溯，回测会在历史时点提前用上未来的 ST/退市信息（乐观偏差）。
    取数失败时本期不过滤（fail-open）并告警。
    """
    if not stock_list or date is None:
        return set()
    st_set = set()
    try:
        codes = list(stock_list)
        for i in range(0, len(codes), 1000):
            df = get_extras('is_st', codes[i:i + 1000], start_date=date, end_date=date, df=True)
            if df is None or df.empty:
                continue
            row = df.iloc[-1]
            st_set.update(c for c in row.index if bool(row[c]))
    except Exception as e:
        log.warning("[ST过滤] get_extras(is_st) 批量取数失败，本期不做ST过滤: %s" % str(e)[:40])
        return set()
    if st_set:
        log.info("[ST过滤] %s 历史口径剔除 ST/退市 %d 只" % (date, len(st_set)))
    return st_set


def is_limit_up_down(stock):
    try:
        current_data = get_current_data()[stock]
        if current_data.paused:
            return True
        op = current_data.day_open
        hl = current_data.high_limit
        ll = current_data.low_limit
        if op is None or op <= 0:
            return True
        if abs(op - hl) < 0.001 or abs(op - ll) < 0.001:
            return True
        return False
    except:
        return True


def batch_scan_first_layer(stocks, date):
    """
    【2026-10-18 批量优化】第一层"昨日涨停/强势"识别的批量版：
    分块（每块500只）get_price 一次拉块内全部标的截至 date 的近 2 根日线
    （close/high_limit，fq='pre'），在返回表上逐票判定——公式与逐股版
    is_limit_up_simple / is_strong_stock 完全一致（含数据不足2根/异常即排除的口径）。
    某块取数失败时该块自动退回逐股判定，行为与原版一致。返回 (limit_up_set, strong_set)。
    """
    limit_up_set, strong_set = set(), set()
    if not stocks or date is None:
        return limit_up_set, strong_set
    codes = list(stocks)
    CHUNK = 500  # 全市场级超大列表 get_price 实测不稳，500/块在已验证安全区
    for i in range(0, len(codes), CHUNK):
        chunk = codes[i:i + CHUNK]
        try:
            df = get_price(chunk, end_date=date, count=2,
                           fields=['close', 'high_limit'], fq='pre', panel=False)
            if df is None or len(df) == 0 or 'code' not in df.columns or 'time' not in df.columns:
                raise ValueError('返回形态异常')
            for code, grp in df.groupby('code'):
                if len(grp) < 2:
                    continue  # 数据不足2根 → 与逐股版 len(hist)<2 返回 False 一致
                grp = grp.sort_values('time')
                pc = float(grp['close'].iloc[0])
                yc = float(grp['close'].iloc[-1])
                yl = float(grp['high_limit'].iloc[-1])
                change = (yc - pc) / pc * 100
                if change > 8.5 or abs(yc - yl) / yl < 0.006:
                    limit_up_set.add(code)
                elif 6 <= change < 8.5:
                    strong_set.add(code)
        except Exception as e:
            log.warning("[批量扫描] 第%d块取数失败，该块退回逐股判定: %s" % (i // CHUNK, str(e)[:40]))
            for stock in chunk:
                if is_limit_up_simple(stock, date):
                    limit_up_set.add(stock)
                elif is_strong_stock(stock, date):
                    strong_set.add(stock)
    log.info("[批量扫描] %s 涨停口径 %d 只 + 强势口径 %d 只" % (date, len(limit_up_set), len(strong_set)))
    return limit_up_set, strong_set


def is_limit_up_simple(stock, date):
    try:
        hist = get_price(stock, end_date=date, count=2, fields=['close', 'high_limit'], fq='pre')
        if len(hist) < 2:
            return False
        yc = hist['close'].iloc[-1]
        yl = hist['high_limit'].iloc[-1]
        pc = hist['close'].iloc[-2]
        change = (yc - pc) / pc * 100
        if change > 8.5 or abs(yc - yl) / yl < 0.006:
            return True
        return False
    except:
        return False


def is_strong_stock(stock, date):
    try:
        hist = get_price(stock, end_date=date, count=2, fields=['close'], fq='pre')
        if len(hist) < 2:
            return False
        change = (hist['close'].iloc[-1] - hist['close'].iloc[-2]) / hist['close'].iloc[-2] * 100
        return 6 <= change < 8.5
    except:
        return False


def find_limit_up_loose(stocks, date):
    limit_stocks = []
    st_set = get_st_set(stocks, date)  # ★ 2026-10-18 前视修复：历史口径ST过滤
    for stock in stocks:
        try:
            if stock in st_set:
                continue
            hist = get_price(stock, end_date=date, count=2, fields=['close', 'high'], fq='pre')
            if len(hist) < 2:
                continue
            yc = hist['close'].iloc[-1]
            yh = hist['high'].iloc[-1]
            pc = hist['close'].iloc[-2]
            change = (yc - pc) / pc * 100
            if change > 8.0 or (abs(yh - yc) / yc < 0.01 and change > 6.5):
                pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, date)
                if not pass_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 宽松选股涨幅过滤淘汰：{filter_msg}")
                    continue
                pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, date)
                if not pass_1430_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 宽松选股尾盘过滤淘汰：{filter_1430_msg}")
                    continue
                pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, date)
                if not pass_amp_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 宽松选股振幅过滤淘汰：{amp_msg}")
                    continue
                pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, date)
                if not pass_turnover_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 宽松选股换手率过滤淘汰：{turnover_msg}")
                    continue
                pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, date)
                if not pass_limitdown_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 宽松选股近3日跌停过滤淘汰：{limitdown_msg}")
                    continue
                pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, date)
                if not pass_shrink_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 宽松选股连续3日缩量上涨过滤淘汰：{shrink_msg}")
                    continue
                limit_stocks.append(stock)
                log.info("宽松涨停: {} {} 涨幅: {:.2f}% | {}".format(stock, stock_name, change, filter_msg))
        except:
            continue
    return limit_stocks


def find_limit_up_ultra_loose(stocks, date):
    limit_stocks = []
    st_set = get_st_set(stocks, date)  # ★ 2026-10-18 前视修复：历史口径ST过滤
    for stock in stocks:
        try:
            if stock in st_set:
                continue
            hist = get_price(stock, end_date=date, count=2, fields=['close'], fq='pre')
            if len(hist) < 2:
                continue
            change = (hist['close'].iloc[-1] - hist['close'].iloc[-2]) / hist['close'].iloc[-2] * 100
            if change > 5.0:
                pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, date)
                if not pass_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 超宽松选股涨幅过滤淘汰：{filter_msg}")
                    continue
                pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, date)
                if not pass_1430_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 超宽松选股尾盘过滤淘汰：{filter_1430_msg}")
                    continue
                pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, date)
                if not pass_amp_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 超宽松选股振幅过滤淘汰：{amp_msg}")
                    continue
                pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, date)
                if not pass_turnover_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 超宽松选股换手率过滤淘汰：{turnover_msg}")
                    continue
                pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, date)
                if not pass_limitdown_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 超宽松选股近3日跌停过滤淘汰：{limitdown_msg}")
                    continue
                pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, date)
                if not pass_shrink_filter:
                    log.info(f"[淘汰] {stock} {stock_name} 超宽松选股连续3日缩量上涨过滤淘汰：{shrink_msg}")
                    continue
                limit_stocks.append(stock)
                log.info("超宽松识别: {} {} 涨幅: {:.2f}% | {}".format(stock, stock_name, change, filter_msg))
        except:
            continue
    return limit_stocks


def check_basic_quality(stock, context):
    try:
        if is_limit_up_down(stock):
            return False
        current_data = get_current_data()[stock]
        return (not current_data.paused) and current_data.day_open is not None and current_data.day_open > 0
    except:
        return False


def calculate_turnover_rate(stock, date):
    try:
        vol_data = get_price(stock, end_date=date, count=1, fields=['volume'], fq='pre')
        if vol_data.empty:
            return 0.0
        volume = vol_data['volume'].iloc[0]
        stock_info = get_security_info(stock)
        float_share = stock_info.float_share if hasattr(stock_info, 'float_share') else 0
        if float_share == 0:
            return 0.0
        return (volume / (float_share * 10000)) * 100
    except:
        return 0.0


def check_turnover_volume(stock, context):
    try:
        yesterday = get_prev_trade_date(context)
        trade_days = get_trade_days(end_date=yesterday, count=2)
        if len(trade_days) < 2:
            return True, "无足够数据"
        day_before_yesterday = trade_days[0]
        turnover_df = get_money_flow(stock, start_date=yesterday, end_date=yesterday)
        if turnover_df.empty or 'turnover_rate' not in turnover_df.columns:
            turnover_rate = calculate_turnover_rate(stock, yesterday)
        else:
            turnover_rate = turnover_df['turnover_rate'].iloc[0]
        if 0 < turnover_rate < g.min_turnover_rate:
            return False, f"换手率{turnover_rate:.2f}% < {g.min_turnover_rate}%"
        vol_df = get_price(stock, start_date=day_before_yesterday, end_date=yesterday, fields=['volume'], fq='pre')
        if len(vol_df) < 2:
            return True, "无成交量数据"
        vol_growth = vol_df['volume'].iloc[-1] / vol_df['volume'].iloc[-2]
        if vol_growth < g.min_volume_growth:
            return False, f"成交量增长{vol_growth:.2f} < {g.min_volume_growth}"
        if context.current_dt.time() > datetime.time(9, 30):
            try:
                today_vol = get_intraday_volume_since_open(context, stock)
                avg_vol = get_price(stock, end_date=yesterday, count=5, fields=['volume'], fq='pre')['volume'].mean()
                if avg_vol > 0:
                    volume_ratio = today_vol / avg_vol
                    if 0 < volume_ratio < g.min_volume_ratio:
                        return False, f"量比{volume_ratio:.2f} < {g.min_volume_ratio}"
            except:
                pass
        return True, "量能达标"
    except:
        return True, "量能校验异常"


def check_ma_trend(stock, context):
    try:
        ma_df = get_price(stock, end_date=get_prev_trade_date(context), count=g.ma_period + 1, fields=['close'],
                          fq='pre')
        if len(ma_df) < g.ma_period + 1:
            return True, "无均线数据"
        ma = ma_df['close'].rolling(window=g.ma_period).mean().iloc[-1]
        if ma_df['close'].iloc[-1] <= ma:
            return True, f"{g.ma_period}日均线空头，仍纳入"
        return True, f"{g.ma_period}日均线多头"
    except:
        return True, "均线校验异常"


def check_limit_up_quality(stock, date):
    try:
        hist = get_price(stock, end_date=date, count=1, fields=['close', 'high_limit', 'high'], fq='pre')
        if hist.empty:
            return True, "无价格数据"
        high_limit = hist['high_limit'].iloc[0]
        high_price = hist['high'].iloc[0]
        if high_price < high_limit * 0.995:
            return True, "未触及涨停"
        return True, "封板质量达标"
    except:
        return True, "封板质量异常"


def check_volume_drop(stock, context):
    try:
        yesterday = get_prev_trade_date(context)
        if yesterday is None:
            return False, ""
        today_volume = get_intraday_volume_since_open(context, stock)
        yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['volume'], fq='pre')
        if today_volume <= 0 or yesterday_data.empty:
            return False, ""
        volume_ratio = today_volume / yesterday_data['volume'].iloc[0]
        today_change = get_current_change(stock, context)
        if volume_ratio > 1.5 and today_change < -2.0:
            return True, f"放量下跌（量比{volume_ratio:.2f}，跌幅{today_change:.2f}%）"
        return False, ""
    except:
        return False, ""


# ==================== ★ 修改三：market_open 中移出 only_buy 限制 ====================
def market_open(context):
    log.info(f"[资金] {context.current_dt.time()} 买入前可用资金：{context.portfolio.available_cash:.2f}")
    # ★ 隔日模式（2026-10-18 修订）：破板回落/紧急队列/止盈止损每天都照做（含只买日），
    #   仅"开盘未涨停清仓"只在只卖日执行；买入窗口只在只买日执行
    check_break_limit_drop(context)

    # ----- 第一步：处理紧急卖出（仅在09:30:40首次执行） -----
    if not g.emergency_processed:
        log.info("[紧急处理] 09:30:40 开始处理紧急卖出队列")
        for stock in list(g.emergency_sell_stocks):  # 使用副本迭代
            if stock not in context.portfolio.positions:
                if stock in g.emergency_sell_stocks:
                    g.emergency_sell_stocks.remove(stock)
                    log.info(f"[紧急处理] 从紧急队列移除 {stock}（已清仓）")
                continue
            # 使用tick快照判断是否打开跌停
            tick_price = get_latest_tick_price(stock, context)
            if tick_price is None:
                current_price, _ = get_realtime_price(context, stock)
            else:
                current_price = tick_price
            low_limit = get_current_data()[stock].low_limit
            if low_limit and current_price and current_price > low_limit * 1.01:
                # 已打开，强制市价卖出（execute_sell 内部会移除队列）
                if execute_sell(stock, context, force=True):
                    log.info(f"[紧急卖出] {stock} 以tick价{current_price}市价卖出成功，队列已清理")
                else:
                    log.info(f"[紧急卖出] {stock} 卖出失败，保留队列")
            else:
                log.info(f"[紧急卖出] {stock} 仍未打开跌停（当前价{current_price}，跌停价{low_limit}），保留队列")
        g.emergency_processed = True  # 标记已处理，后续不再进入此分支

    # ----- 第二步：正常卖出逻辑 -----
    # 开盘未涨停卖出（避免重复卖出已处理的）——★ 隔日模式：开盘清仓只在只卖日执行
    if g.only_sell_today:
        for stock in list(context.portfolio.positions.keys()):
            if stock in g.bought_stocks:
                continue
            try:
                current_data = get_current_data()[stock]
                hl = current_data.high_limit
                op = current_data.day_open
                if op is None or op <= 0 or hl is None or hl <= 0:
                    continue
                if abs(op - hl) / hl > 0.005:
                    log.info("[卖出] 开盘未涨停卖出: {}".format(stock))
                    execute_sell(stock, context)
            except:
                continue
    # 执行止盈止损等卖出决策（每天都执行）
    sell_decision(context)

    # ----- 第三步：买入逻辑（仅在09:30:40执行一次） -----
    if g.buy_enabled:
        g.buy_enabled = False  # 关闭，后续不再买入
        if g.only_buy_today:
            buy_decision(context)
            log.info("[买入] 今日买入窗口已关闭，后续不再买入")
        else:
            log.info("[隔日模式] 今日只卖不买，买入窗口跳过")
    else:
        log.info("[买入] 当前不在买入窗口，跳过买入")

    update_hold_status(context)


# ==================== sell_decision / should_sell（未改动） ====================
def sell_decision(context):
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        if should_sell(stock, context):
            execute_sell(stock, context)


def should_sell(stock, context):
    try:
        current_price, _ = get_realtime_price(context, stock)
        if current_price is None or current_price <= 0:
            return True
        pos = context.portfolio.positions[stock]
        if pos.avg_cost <= 0:
            return True
        profit_ratio = (current_price - pos.avg_cost) / pos.avg_cost * 100
        vdrop, _ = check_volume_drop(stock, context)
        if vdrop:
            return True
        if profit_ratio <= g.stop_loss_ratio:
            return True
        if profit_ratio >= g.stop_profit_ratio and stock not in g.has_limit_up:
            return True
        if g.hold_days.get(stock, 0) >= g.max_hold_days and stock not in g.has_limit_up:
            return True
        return False
    except:
        return True


# ==================== ★ 修改 execute_sell：统一市价单 + 持仓校验 + 订单推送 ====================
def execute_sell(stock, context, force=False):
    """
    卖出股票，统一采用市价单，确保以最新价快速成交。
    force参数保留，用于日志区分紧急卖出，但价格策略相同。
    ★ 增加持仓校验：若卖出后持仓未清零，则视为失败，加入紧急队列。
    """
    # 1. 避免重复卖出
    if stock in g.sold_today_stock_codes:
        return True

    # 2. 取消该股票的现有订单（如有）
    try:
        for od in get_open_orders().values():
            if od.security == stock:
                cancel_order(od)
    except:
        pass

    # 3. 获取当前持仓
    pos = context.portfolio.positions.get(stock)
    if pos is None or pos.total_amount == 0:
        # 已清仓，视为成功
        return True

    # 4. 获取当前价格（用于日志）
    current_price, _ = get_realtime_price(context, stock)
    if current_price is None or current_price <= 0:
        # 无有效价格，加入紧急队列
        if stock not in g.emergency_sell_stocks:
            g.emergency_sell_stocks.append(stock)
        log.warning(f"[卖出失败] {stock} 无法获取有效价格，加入紧急队列")
        return False

    # 5. 执行市价卖出
    order_id = order_target(stock, 0, MarketOrderStyle())
    if not order_id:
        # 下单失败，加入紧急队列
        if stock not in g.emergency_sell_stocks:
            g.emergency_sell_stocks.append(stock)
        log.warning(f"[卖出失败] {stock} 市价单被拒绝，加入紧急队列")
        return False

    # ★★★ 关键：检查卖出是否真的成交（持仓是否已清零） ★★★
    new_pos = context.portfolio.positions.get(stock)
    if new_pos is None or new_pos.total_amount == 0:
        # 卖出成功，记录信息
        avg_cost = pos.avg_cost
        profit_ratio = (current_price - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
        hold_days = g.hold_days.get(stock, 0) + 1
        stock_name = get_security_info(stock).display_name

        g.sold_today.append({
            'code': stock,
            'name': stock_name,
            'cost': avg_cost,
            'sell_price': current_price,
            'profit_ratio': profit_ratio,
            'hold_days': hold_days,
            'sell_time': context.current_dt.strftime('%H:%M:%S')
        })
        g.sold_today_stock_codes.add(stock)
        if stock in g.hold_days:
            del g.hold_days[stock]
        if stock in g.emergency_sell_stocks:
            g.emergency_sell_stocks.remove(stock)
        if stock in g.has_touched_limit_down:
            g.has_touched_limit_down.discard(stock)

        log.info(
            f"[卖出] {stock} {stock_name} 市价卖出 @ 参考价{current_price:.3f}，收益{profit_ratio:.2f}%，持有{hold_days}天")
        return True
    else:
        # 卖出失败（可能跌停未成交），加入紧急队列
        if stock not in g.emergency_sell_stocks:
            g.emergency_sell_stocks.append(stock)
        log.warning(f"[卖出失败] {stock} 市价单未成交（持仓仍为{new_pos.total_amount}股），可能跌停，加入紧急队列")
        return False


# ==================== ★ 修改 retry_sell_limit_down_stocks（修正重复移除队列，增加调试日志） ====================
def retry_sell_limit_down_stocks(context):
    """
    09:40起每10分钟执行，缓慢重试紧急队列和跌停标记股，使用tick判断打开后市价卖出。
    """
    # 处理紧急队列（迭代副本，安全移除）
    for stock in list(g.emergency_sell_stocks):
        if stock not in context.portfolio.positions:
            # 如果股票已清仓，从队列中移除（安全操作）
            if stock in g.emergency_sell_stocks:
                g.emergency_sell_stocks.remove(stock)
                log.info(f"[重试卖出] 从紧急队列移除 {stock}（已清仓）")
            continue

        tick_price = get_latest_tick_price(stock, context)
        if tick_price is None:
            current_price, _ = get_realtime_price(context, stock)
        else:
            current_price = tick_price

        low_limit = get_current_data()[stock].low_limit
        if low_limit and current_price and current_price > low_limit * 1.01:
            # 执行卖出，execute_sell 内部会处理队列移除，外部无需再 remove
            if execute_sell(stock, context, force=True):
                log.info(f"[重试卖出] {stock} 打开跌停，市价卖出成功，队列已由execute_sell清理")
            else:
                log.info(f"[重试卖出] {stock} 尝试卖出但未成功（可能再次跌停），保留队列")
        else:
            log.info(f"[重试卖出] {stock} 仍跌停（当前价{current_price}，跌停价{low_limit}），暂不卖出")

    # 处理原有跌停标记（备用）
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks or stock in g.sold_today_stock_codes:
            continue
        if stock in g.has_touched_limit_down:
            tick_price = get_latest_tick_price(stock, context)
            if tick_price is None:
                current_price, _ = get_realtime_price(context, stock)
            else:
                current_price = tick_price
            low_limit = get_current_data()[stock].low_limit
            if low_limit and current_price and current_price > low_limit * 1.01:
                if execute_sell(stock, context, force=True):
                    g.has_touched_limit_down.discard(stock)
                    log.info(f"[重试卖出] {stock} 跌停标记打开，市价卖出成功")


# ==================== 买入相关函数（仅修改 execute_buy 使用市价单 + 订单推送） ====================
def buy_decision(context):
    cash = context.portfolio.available_cash
    hold_num = len(context.portfolio.positions)
    log.info(f"[查询] 实盘买入检查：持仓={hold_num} 只 | 资金={cash:.2f}")
    if hold_num >= g.max_stock_num or cash < 1000:
        log.info("[警告] 持仓已满或资金不足，今日停止买入")
        return
    current_hold_num = len(context.portfolio.positions)
    if g.bought_today_count >= g.max_buy_per_day:
        return
    if current_hold_num >= g.max_stock_num:
        return
    if len(g.rebuy_candidates) == 0:
        return

    # 只有经过09:28过滤（含五因子）的股票才能被买入
    available_stocks = [
        s for s in g.rebuy_candidates
        if s not in context.portfolio.positions
           and s not in g.bought_stocks
           and s in g.filtered_stocks
    ]
    if len(available_stocks) == 0:
        return

    suspend_count = 0
    double_count = 0
    open_drop_count = 0
    buy_condition_pass = []
    buy_condition_fail = []
    buy_candidates = []
    log_count = 0
    MAX_LOG = 30

    for stock in available_stocks:
        try:
            stock_name = get_security_info(stock).display_name
        except:
            stock_name = "未知名称"
        try:
            current_data = get_current_data()[stock]
            if current_data.paused:
                suspend_count += 1
                log.info(f"[淘汰] 跳过 {stock} {stock_name}：停牌")
                continue
        except Exception:
            suspend_count += 1
            log.info(f"[淘汰] 跳过 {stock} {stock_name}：无法获取当前行情，视为不可交易")
            continue
        if is_double_in_month(stock, context):
            double_count += 1
            log.info(f"[淘汰] 跳过 {stock} {stock_name}：一个月内翻倍")
            continue
        is_drop, drop_msg = is_real_time_drop(context, stock)
        if is_drop:
            open_drop_count += 1
            log.info(f"[淘汰] 跳过 {stock} {stock_name}：开盘高开低走 {drop_msg}")
            continue
        if log_count < MAX_LOG:
            buy_signal, reason = check_buy_condition(stock, context)
            log_count += 1
        else:
            buy_signal, reason = check_buy_condition_silent(stock, context)
        if buy_signal:
            buy_candidates.append((stock, reason))
            buy_condition_pass.append((stock, stock_name, reason))
        else:
            buy_condition_fail.append((stock, stock_name, reason))

    log.info("")
    log.info("=" * 80)
    log.info("[统计] 【买入过滤统计表】")
    log.info("=" * 80)
    log.info(f"  总候选股票数：{len(available_stocks)} 只")
    log.info(f"  |-- 停牌过滤：{suspend_count} 只")
    log.info(f"  |-- 一个月翻倍过滤：{double_count} 只")
    log.info(f"  |-- 开盘急跌过滤：{open_drop_count} 只")
    log.info(f"  |-- 买入条件未通过：{len(buy_condition_fail)} 只")
    log.info(f"  +-- 买入条件通过：{len(buy_condition_pass)} 只")
    log.info("=" * 80)

    if len(buy_candidates) == 0:
        log.info("")
        log.info("[警告] 过滤后无符合条件的买入标的 ")
        log.info("=" * 80)
        return

    def get_gain_diff(stock, context):
        try:
            trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
            if len(trade_days) < 2:
                return 0
            yesterday = trade_days[0]
            yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
            if yesterday_data.empty:
                return 0
            current_data = get_current_data()[stock]
            open_price = current_data.day_open
            yesterday_close = yesterday_data['close'].iloc[0]
            if open_price <= 0 or yesterday_close <= 0:
                return 0
            tick_price, tick_msg = get_tick_b1_price_at_93006(context, stock)
            if tick_price is None or tick_price <= 0:
                return 0
            diff = (tick_price - open_price) / yesterday_close * 100
            return diff
        except:
            return 0

    sort_start_time = datetime.datetime.now()
    buy_candidates.sort(key=lambda x: get_gain_diff(x[0], context), reverse=True)
    sort_end_time = datetime.datetime.now()
    sort_ms = (sort_end_time - sort_start_time).total_seconds() * 1000
    log.info(f"[耗时] 排序耗时: {sort_ms:.0f}ms | 排序完成时刻: {sort_end_time.strftime('%H:%M:%S.%f')[:-3]}")

    remain_buy_num = g.max_stock_num - current_hold_num
    remain_buy_today = g.max_buy_per_day - g.bought_today_count
    final_buy_num = min(remain_buy_num, remain_buy_today)

    signal_send_start = datetime.datetime.now()
    log.info(f"[信号] 开始推送买入信号: {signal_send_start.strftime('%H:%M:%S.%f')[:-3]} | 将买入前 {final_buy_num} 只")
    signal_times = {}
    for i, (stock, reason) in enumerate(buy_candidates[:final_buy_num]):
        try:
            current_data = get_current_data()[stock]
            if datetime.time(9, 30, 0) <= context.current_dt.time() <= datetime.time(9, 30, 47):
                tick_price, _ = get_tick_b1_price_at_93006(context, stock)
                sig_price = tick_price if tick_price and tick_price > 0 else current_data.last_price
            else:
                sig_price = current_data.last_price
            if sig_price is None or sig_price <= 0:
                sig_price = current_data.day_open
            available_cash = context.portfolio.available_cash
            remain_buy = g.max_stock_num - len(context.portfolio.positions)
            if remain_buy > 0 and sig_price > 0:
                target_cash = available_cash / remain_buy
                est_amount = int(target_cash / sig_price / 100) * 100
            else:
                est_amount = 100
        except Exception as e:
            log.warning(f"[信号] 预推送信号异常 {stock}: {str(e)[:30]}")
    signal_send_end = datetime.datetime.now()
    signal_total_ms = (signal_send_end - signal_send_start).total_seconds() * 1000
    log.info(
        f"[信号] 买入信号全部推送完成: {signal_send_end.strftime('%H:%M:%S.%f')[:-3]} | 总耗时: {signal_total_ms:.0f}ms | 推送 {len(signal_times)} 只")

    log.info("")
    log.info("=" * 80)
    log.info(f"  本次满足买入条件股票总数：{len(buy_candidates)} 只")
    log.info("  排序后股票列表（按09:30:40快照拉升幅度降序）：")
    log.info("-" * 80)
    display_count = min(30, len(buy_candidates))
    for i, (stock, reason) in enumerate(buy_candidates[:display_count]):
        try:
            s_name = get_security_info(stock).display_name
        except:
            s_name = "未知"
        change = get_current_change(stock, context)
        diff = get_gain_diff(stock, context)
        log.info(f"  {i + 1:>2}. {stock:<12} {s_name:<10} | 涨幅:{change:>6.2f}% | 拉升:{diff:>6.2f}% | {reason}")
    if display_count < len(buy_candidates):
        log.info(f"  ... 剩余 {len(buy_candidates) - display_count} 只未显示")
    log.info("=" * 80)

    log.info("")
    log.info(f"  本次将买入前 {final_buy_num} 只股票：")
    log.info("-" * 60)

    bought_count = 0
    for i, (stock, reason) in enumerate(buy_candidates[:final_buy_num]):
        if execute_buy(stock, context, signal_times.get(stock)):
            bought_count += 1
            g.bought_stocks.add(stock)
            g.bought_today_count += 1
            try:
                name = get_security_info(stock).display_name
            except:
                name = "未知"
            diff = get_gain_diff(stock, context)
            order_time = datetime.datetime.now()
            if stock in signal_times:
                sig_to_order_ms = (order_time - signal_times[stock]).total_seconds() * 1000
                log.info(
                    f"  已买入 {i + 1:>2}. {stock:<15} {name:<12} | 拉升:{diff:>6.2f}% | 信号->下单: {sig_to_order_ms:.0f}ms")
            else:
                log.info(f"  已买入 {i + 1:>2}. {stock:<15} {name:<12} | 拉升:{diff:>6.2f}%")
        else:
            log.info(f"  买入失败 {i + 1:>2}. {stock:<15}")

    if bought_count < final_buy_num:
        log.info(f"[警告] 本次实际买入 {bought_count} 只，剩余 {final_buy_num - bought_count} 只因资金或买入失败未成交")

    log.info("=" * 80)


def check_buy_condition(stock, context):
    if hasattr(g, 'checked_today') and stock in g.checked_today:
        return g.checked_today[stock]
    try:
        stock_name = get_security_info(stock).display_name
    except:
        stock_name = "未知"
    try:
        current_data = get_current_data()[stock]
        open_p = current_data.day_open
        current_price, price_msg = get_realtime_price(context, stock)
        yesterday = get_prev_trade_date(context)
        if yesterday is None:
            res = (False, "无昨日数据")
        else:
            yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
            if yesterday_data.empty or open_p is None or open_p <= 0 or current_price is None or current_price <= 0:
                res = (False, "无数据/停牌")
            else:
                last_p = current_price
                yes_close = yesterday_data['close'].iloc[0]
                open_ratio = (open_p - yes_close) / yes_close * 100
                t = context.current_dt.time()
                if datetime.time(9, 30, 00) <= t <= datetime.time(9, 30, 47):
                    tick_price, tick_msg = get_tick_b1_price_at_93006(context, stock)
                    if tick_price is None or tick_price <= 0:
                        if g.debug:
                            log.info(f"[日志] {stock} {stock_name} 买入过滤：无09:30:40附近tick价 | {tick_msg}")
                        res = (False, "无09:30:40附近tick价")
                    else:
                        judge_price = tick_price
                        drop_ratio = (judge_price - open_p) / open_p * 100
                        if drop_ratio < -0.5:
                            if g.debug:
                                log.info(
                                    f"[日志] {stock} {stock_name} 买入过滤：09:30:40开盘急跌{drop_ratio:.2f}% < -0.5% | {tick_msg}")
                            res = (False, f"09:30:40急跌{drop_ratio:.2f}%")
                        else:
                            vol_ok, vol_msg = check_turnover_volume(stock, context)
                            if not vol_ok:
                                if g.debug:
                                    log.info(f"[日志] {stock} {stock_name} 买入过滤：{vol_msg}")
                                res = (False, vol_msg)
                            else:
                                ma_ok, ma_msg = check_ma_trend(stock, context)
                                lu_ok, lu_msg = check_limit_up_quality(stock, yesterday)
                                if g.debug:
                                    log.info(f"[日志] {stock} {stock_name} 买入条件：通过")
                                res = (True, f"开盘{open_ratio:.2f}%|09:30:40价{judge_price:.3f}")
                else:
                    vol_ok, vol_msg = check_turnover_volume(stock, context)
                    if not vol_ok:
                        if g.debug:
                            log.info(f"[日志] {stock} {stock_name} 买入过滤：{vol_msg}")
                        res = (False, vol_msg)
                    else:
                        current_change = (last_p - yes_close) / yes_close * 100
                        if current_change > g.max_open_ratio + 2:
                            if g.debug:
                                log.info(f"[日志] {stock} {stock_name} 买入过滤：实时涨幅{current_change:.2f}% 过高")
                            res = (False, f"实时涨幅{current_change:.2f}%过高")
                        else:
                            ma_ok, ma_msg = check_ma_trend(stock, context)
                            lu_ok, lu_msg = check_limit_up_quality(stock, yesterday)
                            if g.debug:
                                log.info(f"[日志] {stock} {stock_name} 买入条件：通过")
                            res = (True, f"实时{current_change:.2f}%")
        if not hasattr(g, 'checked_today'):
            g.checked_today = {}
        g.checked_today[stock] = res
        return res
    except Exception as e:
        log.error(f"[日志] {stock} {stock_name} 买入条件检查异常：{str(e)[:50]}")
        res = (False, f"检查异常:{str(e)[:20]}")
        if hasattr(g, 'checked_today'):
            g.checked_today[stock] = res
        return res


def check_buy_condition_silent(stock, context):
    if hasattr(g, 'checked_today') and stock in g.checked_today:
        return g.checked_today[stock]
    try:
        current_data = get_current_data()[stock]
        open_p = current_data.day_open
        current_price, price_msg = get_realtime_price(context, stock)
        yesterday = get_prev_trade_date(context)
        if yesterday is None:
            res = (False, "无昨日数据")
        else:
            yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
            if yesterday_data.empty or open_p is None or open_p <= 0 or current_price is None or current_price <= 0:
                res = (False, "无数据/停牌")
            else:
                last_p = current_price
                yes_close = yesterday_data['close'].iloc[0]
                open_ratio = (open_p - yes_close) / yes_close * 100
                t = context.current_dt.time()
                if datetime.time(9, 30, 00) <= t <= datetime.time(9, 30, 47):
                    tick_price, tick_msg = get_tick_b1_price_at_93006(context, stock)
                    if tick_price is None or tick_price <= 0:
                        res = (False, "无09:30:40附近tick价")
                    else:
                        judge_price = tick_price
                        drop_ratio = (judge_price - open_p) / open_p * 100
                        if drop_ratio < -0.5:
                            res = (False, f"09:30:40急跌{drop_ratio:.2f}%")
                        else:
                            vol_ok, vol_msg = check_turnover_volume(stock, context)
                            if not vol_ok:
                                res = (False, vol_msg)
                            else:
                                res = (True, f"开盘{open_ratio:.2f}%|09:30:40价{judge_price:.3f}")
                else:
                    vol_ok, vol_msg = check_turnover_volume(stock, context)
                    if not vol_ok:
                        res = (False, vol_msg)
                    else:
                        current_change = (last_p - yes_close) / yes_close * 100
                        if current_change > g.max_open_ratio + 2:
                            res = (False, f"实时涨幅{current_change:.2f}%过高")
                        else:
                            res = (True, f"实时{current_change:.2f}%")
        if not hasattr(g, 'checked_today'):
            g.checked_today = {}
        g.checked_today[stock] = res
        return res
    except:
        res = (False, "检查异常")
        if hasattr(g, 'checked_today'):
            g.checked_today[stock] = res
        return res


def get_current_change(stock, context):
    try:
        yesterday = get_prev_trade_date(context)
        if yesterday is None:
            return 0
        yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
        if yesterday_data.empty:
            return 0
        yesterday_close = yesterday_data['close'].iloc[0]
        current_price, _ = get_realtime_price(context, stock)
        if current_price is None or current_price <= 0:
            return 0
        return (current_price - yesterday_close) / yesterday_close * 100
    except:
        return 0


# ★★★ 修改：execute_buy 使用市价单 + 推送买入订单 ★★★
def execute_buy(stock, context, pre_signal_time=None):
    try:
        if stock in context.portfolio.positions or stock in g.bought_stocks:
            return False
        current_data = get_current_data()[stock]
        price_source = "last_price"
        order_style = None
        limit_price = None
        if datetime.time(9, 30, 0) <= context.current_dt.time() <= datetime.time(9, 30, 47):
            tick_price, tick_msg = get_tick_b1_price_at_93006(context, stock)
            if tick_price is None or tick_price <= 0:
                log.info(f"[买入] {stock} 无09:30:40附近tick价，取消买入 | {tick_msg}")
                return False
            current_price = tick_price
            price_source = "09:30:40_tick_b1_p"
            # ★ 2026-10-18 限价单：当根tick价+2跳（A股最小价位0.01×2），封顶涨停价。
            #   回测撮合=开盘价+滑点（委托价高于该值即成交，结果与市价单几乎一致）；
            #   实盘把"买贵"风险封顶为"买不到"，向回测的开盘价口径收敛
            _hl = current_data.high_limit
            limit_price = round(tick_price + 0.02, 2)
            if _hl is not None and float(_hl) > 0:
                limit_price = min(limit_price, float(_hl))
            order_style = LimitOrderStyle(limit_price)
        else:
            current_price = current_data.last_price
        if current_price <= 0:
            return False
        order_start = datetime.datetime.now()
        log.info(f"[买入] {stock} 买入参考价({price_source}): {current_price}, 时间: {order_start.time()}")
        available_cash = context.portfolio.available_cash
        current_hold = len(context.portfolio.positions)
        remain_buy = g.max_stock_num - current_hold
        if remain_buy <= 0 or available_cash < 100:
            return False
        target_cash = available_cash / remain_buy
        # 限价窗口按限价估股数（保守，防按tick价估导致实际委托金额超可用资金被削单）
        size_price = limit_price if limit_price is not None else current_price
        buy_amount = int(target_cash / size_price / 100) * 100
        if buy_amount < 100:
            return False
        # ★ 2026-08-04 市价单 → 2026-10-18 起限价窗口（9:30:40）改限价单：tick价+2跳封顶涨停价
        order_id = order(stock, buy_amount, order_style if order_style is not None else MarketOrderStyle())
        order_end = datetime.datetime.now()
        order_ms = (order_end - order_start).total_seconds() * 1000
        if order_id:
            stock_name = get_security_info(stock).display_name
            _style_desc = ("限价单@%.2f" % limit_price) if limit_price is not None else "市价单"
            log.info(
                f"[买入] 买入: {stock} {stock_name} | {buy_amount}股 @ {_style_desc} (参考价{current_price:.3f}) | 下单耗时: {order_ms:.0f}ms")
            g.hold_days[stock] = 0
            return True
        return False
    except Exception as e:
        log.error(f"[买入] 买入失败{stock}: {str(e)[:30]}")
        return False


def update_hold_status(context):
    for stock in context.portfolio.positions:
        try:
            high = get_intraday_high_since_open(context, stock)
            high_limit = get_current_data()[stock].high_limit
            if high <= 0 or high_limit is None or high_limit <= 0:
                continue
            if high >= high_limit * 0.995 and stock not in g.has_limit_up:
                g.has_limit_up.add(stock)
                stock_name = get_security_info(stock).display_name
                log.info("  标记涨停: {} {}".format(stock, stock_name))
        except:
            continue


def after_market_close(context):
    log.info("=" * 50)
    trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
    if len(trade_days) >= 1:
        today = trade_days[-1]
    else:
        today = context.current_dt.date()
    log.info("收盘总结: {}".format(today))
    for stock in context.portfolio.positions:
        if stock not in g.bought_stocks:
            g.hold_days[stock] = g.hold_days.get(stock, 0) + 1
    if len(g.sold_today) > 0:
        log.info(f"  今日卖出：{len(g.sold_today)}只")
        for sell in g.sold_today:
            log.info(
                f"  {sell['code']} {sell['name']} | 成本:{sell['cost']:.3f} | 卖出:{sell['sell_price']:.3f} | 收益:{sell['profit_ratio']:.2f}% | 持有{sell['hold_days']}天 | 时间:{sell['sell_time']}")
    hold_stocks = list(context.portfolio.positions.keys())
    log.info(f"  最终持仓：{len(hold_stocks)}只")
    for stock in hold_stocks:
        try:
            pos = context.portfolio.positions[stock]
            stock_name = get_security_info(stock).display_name
            profit_ratio = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else 0
            days = g.hold_days.get(stock, 0)
            flag = "涨停" if stock in g.has_limit_up else "未涨停"
            log.info(
                f"  {stock} {stock_name} | 成本:{pos.avg_cost:.3f} | 当前:{pos.price:.3f} | 收益:{profit_ratio:.2f}% | 持有{days}天 | {flag}")
        except:
            log.info(f"  {stock} | 持仓信息获取失败")
    total_asset = context.portfolio.total_value
    cash = context.portfolio.available_cash
    market_value = total_asset - cash
    log.info(f"  总资产：{total_asset:.2f} | 可用资金：{cash:.2f} | 持仓市值：{market_value:.2f}")
    log.info("=" * 50)