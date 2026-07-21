# Clone from JoinQuant
# postId: 4bc2448002195bcf40c121532ef4e087
# backtestId: 750267bbc9a9a7e5e2a1f86c5b7d2030
# title: 从克隆别人策略到自己造模型——一个老股民的量化探索手记

# ====================================================================
# 多因子选股 + 三重市场状态过滤策略
# ====================================================================
# 配套：v1_training_clean.py 训练出的 model_latest.pkl
#
# 市场状态判定（三重确认）：
#   第一重：大盘趋势（上证指数 MA20 vs MA60）
#   第二重：市场宽度（中证1000站上20日均线的股票占比）
#   第三重：动量加速（近5日收益率，急跌触发清仓）
#
# 仓位映射：
#   牛市     → 满仓 5 只
#   震荡市    → 半仓 3 只
#   熊市     → 清仓持现金
#   急跌避险  → 立即清仓
#
# 风控：
#   个股止损 8%
#   翻倍止盈
#   涨停打开次日卖出
# ====================================================================

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import pickle
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


def initialize(context):
    set_benchmark('399101.XSHE')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(3 / 10000))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                              open_commission=0.0003, close_commission=0.0003,
                              close_today_commission=0, min_commission=5),
                   type='stock')
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')

    # ========== 持仓参数 ==========
    g.stock_num_bull = 5         # 牛市持仓
    g.stock_num_neutral = 3      # 震荡市持仓
    g.stock_num_current = 5      # 当前目标持仓数（动态更新）
    g.hold_list = []
    g.yesterday_HL_list = []

    # ========== 市场状态参数 ==========
    g.breadth_threshold_bull = 0.60      # 宽度 >60% 视为健康
    g.breadth_threshold_bear = 0.40      # 宽度 <40% 视为危险
    g.crash_threshold = -0.05            # 5日跌幅 <-5% 触发紧急避险
    g.market_status = 'neutral'          # 当前市场状态

    # ========== 风控参数 ==========
    g.stoploss_individual = 0.08
    g.take_profit = 2.0
    g.run_stoploss = True

    # ========== 加载模型 ==========
    g.model = None
    g.factor_list = []
    g.model_target_type = 'rank'
    g.model_train_end = 'unknown'
    load_latest_model()

    # ========== 定时任务 ==========
    run_daily(market_status_check, '9:15')      # 早盘判断市场状态
    run_daily(prepare_stock_list, '9:20')
    run_weekly(weekly_adjustment, 1, '9:30')    # 每周一调仓
    run_daily(sell_stocks, '10:00')             # 早盘止损
    run_daily(check_crash, '10:30')             # 急跌检测
    run_daily(sell_stocks, '14:20')             # 下午止损
    run_daily(check_limit_up, '14:00')


# ============================================================
# 模型加载
# ============================================================

def load_latest_model():
    """从研究环境加载滚动训练出的最新模型"""
    try:
        model_data = pickle.loads(read_file('model_latest.pkl'))
        g.model = model_data['model']
        g.factor_list = model_data['factor_cols']
        g.model_target_type = model_data.get('target_type', 'rank')
        g.model_train_end = model_data.get('train_end', 'unknown')
        log.info(f"✅ 模型加载: 训练截止={g.model_train_end}, 因子数={len(g.factor_list)}")
    except Exception as e:
        log.error(f"❌ 模型加载失败: {e}")
        log.info("将退化为纯小市值选股")
        g.model = None


# ============================================================
# 市场状态判定（核心 - 三重确认）
# ============================================================

def market_status_check(context):
    """
    早盘 9:15 判断市场状态，全天沿用此判断
    """
    yesterday = context.previous_date

    # ─── 第一重：大盘趋势 ───
    trend_status = check_index_trend(yesterday)

    # ─── 第二重：市场宽度 ───
    breadth = check_market_breadth(yesterday)

    # ─── 第三重：动量加速度 ───
    momentum_5d = check_5day_momentum(yesterday)

    # ─── 综合判定 ───
    # 急跌优先：5日跌幅超过阈值无条件清仓
    if momentum_5d < g.crash_threshold:
        g.market_status = 'crash'
        g.stock_num_current = 0
    # 大盘空头 或 宽度低于熊市阈值 = 熊市
    elif trend_status == 'bear' or breadth < g.breadth_threshold_bear:
        g.market_status = 'bear'
        g.stock_num_current = 0
    # 大盘多头 + 宽度健康 = 牛市
    elif trend_status == 'bull' and breadth >= g.breadth_threshold_bull:
        g.market_status = 'bull'
        g.stock_num_current = g.stock_num_bull
    # 其他情况 = 震荡市
    else:
        g.market_status = 'neutral'
        g.stock_num_current = g.stock_num_neutral

    log.info(f"📊 市场状态: {g.market_status} | 趋势={trend_status} | "
             f"宽度={breadth:.1%} | 5日动量={momentum_5d:.2%} | "
             f"目标持仓={g.stock_num_current}")


def check_index_trend(date):
    """第一重：上证指数 MA20 vs MA60 判断大盘趋势"""
    try:
        df = get_price('000001.XSHG', end_date=date, count=65,
                       fields=['close'], frequency='daily')
        if len(df) < 60:
            return 'neutral'

        ma20 = df['close'].iloc[-20:].mean()
        ma60 = df['close'].iloc[-60:].mean()
        ma20_prev = df['close'].iloc[-25:-5].mean()
        current = df['close'].iloc[-1]

        ma20_trend = (ma20 - ma20_prev) / ma20_prev

        if current > ma20 > ma60 and ma20_trend > 0:
            return 'bull'
        elif current < ma20 < ma60 and ma20_trend < 0:
            return 'bear'
        else:
            return 'neutral'
    except Exception as e:
        log.error(f"大盘趋势判断失败: {e}")
        return 'neutral'


def check_market_breadth(date):
    """
    第二重：市场宽度
    计算中证1000中站上自身20日均线的股票占比
    """
    try:
        # 取中证1000成分股（采样100只够用，全量计算太慢）
        all_stocks = get_index_stocks('399101.XSHE', date)
        # 取前150只小市值（与策略池一致）
        q = query(valuation.code).filter(
            valuation.code.in_(all_stocks),
            valuation.market_cap.between(5, 100)
        ).order_by(valuation.market_cap.asc()).limit(150)
        sample_stocks = list(get_fundamentals(q, date=date)['code'])

        if len(sample_stocks) < 30:
            return 0.5  # 数据不足返回中性值

        # 取近20+1日的收盘价
        prices = get_price(sample_stocks, end_date=date, count=21,
                            frequency='daily', fields=['close'], panel=False)

        # 按股票分组，每只股票计算最新价 vs MA20
        above_ma_count = 0
        total_count = 0
        for stock, group in prices.groupby('code'):
            if len(group) < 20:
                continue
            ma20 = group['close'].iloc[-20:].mean()
            current = group['close'].iloc[-1]
            if current > ma20:
                above_ma_count += 1
            total_count += 1

        if total_count == 0:
            return 0.5
        return above_ma_count / total_count

    except Exception as e:
        log.error(f"市场宽度计算失败: {e}")
        return 0.5


def check_5day_momentum(date):
    """第三重：中证1000近5日收益率"""
    try:
        df = get_price('399101.XSHE', end_date=date, count=6,
                       fields=['close'], frequency='daily')
        if len(df) < 5:
            return 0
        return df['close'].iloc[-1] / df['close'].iloc[-5] - 1
    except Exception as e:
        log.error(f"5日动量计算失败: {e}")
        return 0


# ====================================================================
# check_crash 修复版 - 替换原策略中的同名函数
# ====================================================================
# 问题：avoid_future_data=True 禁止盘中取当日日K的 close
# 修复：改用 1分钟数据 取当日开盘价 + get_current_data 取实时价
# ====================================================================

def check_crash(context):
    """
    盘中急跌检测：每天 10:30 检查中证1000当日实时跌幅
    """
    try:
        index_code = '399101.XSHE'

        # 取当日开盘价：用 1 分钟数据从开盘到当前
        # 注意 frequency='1m' 时 end_date=current_dt 是允许的
        minute_df = get_price(
            index_code,
            end_date=context.current_dt,
            frequency='1m',
            fields=['open', 'close'],
            count=240,           # 取足够多分钟，覆盖整个上午
            panel=False,
            skip_paused=False
        )

        if minute_df.empty:
            return

        # 过滤出今日的分钟数据（剔除昨日尾盘）
        today_str = context.current_dt.strftime('%Y-%m-%d')
        minute_df.index = pd.to_datetime(minute_df.index)
        today_data = minute_df[minute_df.index.strftime('%Y-%m-%d') == today_str]

        if today_data.empty or len(today_data) < 5:
            return

        # 计算当日跌幅：当前价 / 当日开盘价 - 1
        today_open = today_data['open'].iloc[0]      # 今日 9:30 开盘价
        current_price = today_data['close'].iloc[-1]  # 当前最新价
        intraday_drop = current_price / today_open - 1

        # 当日跌幅超过 4% 直接清仓
        if intraday_drop < -0.04 and context.portfolio.positions:
            log.warning(f"⚠️ 盘中急跌 {intraday_drop:.2%}，紧急清仓")
            for stock in list(context.portfolio.positions.keys()):
                close_position(context.portfolio.positions[stock])
            g.market_status = 'crash'
        else:
            # 调试日志：正常情况下也输出当日跌幅，方便观察
            if abs(intraday_drop) > 0.02:
                log.info(f"盘中观察: 中证1000当日波动 {intraday_drop:.2%}")

    except Exception as e:
        log.error(f"急跌检测失败: {e}")

# ============================================================
# 准备股票池
# ============================================================

def prepare_stock_list(context):
    g.hold_list = list(context.portfolio.positions.keys())
    if g.hold_list:
        try:
            df = get_price(g.hold_list, end_date=context.previous_date,
                            frequency='daily', fields=['close', 'high_limit'],
                            count=1, panel=False, fill_paused=False)
            g.yesterday_HL_list = list(df[df['close'] == df['high_limit']]['code'])
        except Exception:
            g.yesterday_HL_list = []
    else:
        g.yesterday_HL_list = []


# ============================================================
# 选股
# ============================================================

def get_stock_list(context):
    yesterday = context.previous_date

    stocks = get_index_stocks('399101.XSHE', yesterday)
    stocks = filter_kcbj(stocks)
    stocks = filter_st(stocks)
    stocks = filter_paused(stocks)
    stocks = filter_new(context, stocks)
    stocks = filter_limitup(context, stocks)
    stocks = filter_limitdown(context, stocks)

    # 5-50亿市值筛选
    q = query(valuation.code, valuation.market_cap).filter(
        valuation.code.in_(stocks),
        valuation.market_cap.between(5, 50)
    ).order_by(valuation.market_cap.asc()).limit(100)
    df = get_fundamentals(q, date=yesterday)
    initial_list = list(df['code'])

    if not initial_list:
        log.warning("初始股票池为空")
        return []

    # 模型未加载 → 退化为市值选股
    if g.model is None or not g.factor_list:
        log.info("模型未加载，使用纯小市值选股")
        return initial_list[:g.stock_num_current]

    # ========== 用模型预测 ==========
    try:
        factor_data = get_factor_values(initial_list, g.factor_list,
                                          end_date=yesterday, count=1)
        df_factors = pd.DataFrame(index=initial_list)
        for f in g.factor_list:
            if f in factor_data:
                df_factors[f] = factor_data[f].iloc[0, :]
            else:
                df_factors[f] = 0

        # 截面预处理（与训练保持一致）
        df_factors = df_factors.fillna(df_factors.median())
        for col in df_factors.columns:
            q1, q99 = df_factors[col].quantile(0.01), df_factors[col].quantile(0.99)
            df_factors[col] = df_factors[col].clip(q1, q99)
            mean, std = df_factors[col].mean(), df_factors[col].std()
            if std > 1e-8:
                df_factors[col] = (df_factors[col] - mean) / std

        # 预测
        scores = g.model.predict(df_factors.values)
        df_factors['score'] = scores
        df_sorted = df_factors.sort_values('score', ascending=False)
        target_list = df_sorted.index.tolist()[:g.stock_num_current]

        log.info(f"模型选股 ({g.market_status}市,{g.stock_num_current}只): {target_list}")
        log.info(f"  最高分={df_sorted['score'].max():.4f}, "
                 f"最低分={df_sorted['score'].min():.4f}")
        return target_list

    except Exception as e:
        log.error(f"模型选股失败: {e}, 退化为市值选股")
        return initial_list[:g.stock_num_current]


# ============================================================
# 调仓
# ============================================================

def weekly_adjustment(context):
    # ⭐ 核心：根据市场状态决定是否调仓 ⭐
    if g.market_status in ('bear', 'crash'):
        log.info(f"🔴 {g.market_status}市，执行清仓保护")
        # 清仓所有持仓（除涨停股暂留）
        for stock in g.hold_list:
            if stock not in g.yesterday_HL_list:
                close_position(context.portfolio.positions[stock])
        return

    # 牛市/震荡市正常调仓
    target_list = get_stock_list(context)
    if not target_list:
        log.warning("目标列表为空，跳过调仓")
        return

    log.info(f"本周调仓 ({g.market_status}市): {target_list}")

    # 卖出不在目标列表的（涨停股保留）
    for stock in g.hold_list:
        if stock not in target_list and stock not in g.yesterday_HL_list:
            close_position(context.portfolio.positions[stock])

    # 买入新标的
    buy_list = [s for s in target_list if s not in context.portfolio.positions]
    n_holding = len(context.portfolio.positions)
    n_target = g.stock_num_current

    if buy_list and n_holding < n_target:
        # 按目标持仓数等分现金
        n_to_buy = min(len(buy_list), n_target - n_holding)
        cash_per_stock = context.portfolio.cash / n_to_buy if n_to_buy > 0 else 0

        for stock in buy_list[:n_to_buy]:
            if context.portfolio.cash >= cash_per_stock and cash_per_stock > 1000:
                open_position(stock, cash_per_stock)


# ============================================================
# 止损止盈
# ============================================================

def sell_stocks(context):
    if not g.run_stoploss:
        return

    # 个股止盈止损
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.avg_cost <= 0:
            continue
        ret = pos.price / pos.avg_cost - 1

        if pos.price >= pos.avg_cost * g.take_profit:
            log.info(f"🎉 翻倍止盈 {stock} 收益{ret:.2%}")
            close_position(pos)
        elif ret <= -g.stoploss_individual:
            log.info(f"💀 个股止损 {stock} 亏损{ret:.2%}")
            close_position(pos)


# ============================================================
# 涨停股管理
# ============================================================

def check_limit_up(context):
    if not g.yesterday_HL_list:
        return
    now_time = context.current_dt
    for stock in g.yesterday_HL_list:
        try:
            data = get_price(stock, end_date=now_time, frequency='1m',
                              fields=['close', 'high_limit'], count=1, panel=False)
            if data.iloc[0]['close'] < data.iloc[0]['high_limit']:
                log.info(f"[{stock}] 涨停打开，卖出")
                close_position(context.portfolio.positions[stock])
        except Exception as e:
            log.error(f"涨停检查失败 {stock}: {e}")


# ============================================================
# 交易函数
# ============================================================

def open_position(security, value):
    order = order_target_value(security, value)
    if order is not None and order.filled > 0:
        log.info(f"买入 {security} {order.filled}股")
        return True
    return False


def close_position(position):
    security = position.security
    order = order_target_value(security, 0)
    return order is not None and order.status == OrderStatus.held


# ============================================================
# 过滤函数
# ============================================================

def filter_paused(stocks):
    cd = get_current_data()
    return [s for s in stocks if not cd[s].paused]


def filter_st(stocks):
    cd = get_current_data()
    return [s for s in stocks if not cd[s].is_st
            and 'ST' not in cd[s].name
            and '*' not in cd[s].name
            and '退' not in cd[s].name]


def filter_kcbj(stocks):
    return [s for s in stocks if not s.startswith(('30', '68', '4', '8'))]


def filter_new(context, stocks):
    cutoff = context.previous_date - timedelta(days=375)
    return [s for s in stocks
            if get_security_info(s) is not None
            and get_security_info(s).start_date < cutoff]


def filter_limitup(context, stocks):
    if not stocks:
        return []
    try:
        last_prices = history(1, unit='1m', field='close', security_list=stocks)
        cd = get_current_data()
        return [s for s in stocks
                if s in context.portfolio.positions
                or last_prices[s].iloc[-1] < cd[s].high_limit]
    except Exception:
        return stocks


def filter_limitdown(context, stocks):
    if not stocks:
        return []
    try:
        last_prices = history(1, unit='1m', field='close', security_list=stocks)
        cd = get_current_data()
        return [s for s in stocks
                if s in context.portfolio.positions
                or last_prices[s].iloc[-1] > cd[s].low_limit]
    except Exception:
        return stocks