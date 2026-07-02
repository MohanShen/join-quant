# Clone from JoinQuant
# postId: ecb69615383ae70f89f388b66e687990
# backtestId: 97303cdce723177e6ca6a870c0467674
# title: 趋势选股工具--取自某国外冠军策略

# 克隆自聚宽文章：https://www.joinquant.com/post/71653
# 标题：只用两条免费指标，两个月超额收益153%
# 作者：希有见杰

# 导入函数库
from jqdata import *

# 聚宽策略：SAR + MACD 趋势跟踪 + 动态仓位管理
# 作者：QuantMaster
# 版本：1.0 (2026-04-28)
# 说明：
# 1. 大盘择时：中证500收盘价 vs MA20 决定总仓位上下限
# 2. 选股：中证500成分股中，同时满足 SAR上升趋势 且 MACD金叉 的股票
# 3. 出场：止盈10%、止损5%、SAR转跌、MACD死叉
# 4. 仓位：单票上限15%，总仓位随大盘强弱动态调整（强势80%/弱势60%）

from jqdata import *
import talib
import numpy as np
import pandas as pd

def initialize(context):
    # ==================== 基础设置 ====================
    set_benchmark('000905.XSHG')                     # 基准：中证500
    set_option('use_real_price', True)               # 使用真实价格
    set_option('order_volume_ratio', 1)              # 按实际数量下单
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                             open_commission=0.00025, close_commission=0.00025,
                             min_commission=5), type='stock')
    set_slippage(FixedSlippage(0.002))               # 滑点0.2%

    # ==================== 策略参数 ====================
    g.stock_pool_index = '000905.XSHG'   # 股票池基准指数
    g.update_pool_freq = 20             # 每20个交易日更新一次股票池
    g.max_hold_count = 8                # 最大持仓股票数
    g.min_price = 8                     # 最低股价（低于此价不考虑）
    g.min_avg_volume = 20e6             # 20日均成交额最低要求（2000万）
    g.base_max_position = 0.80          # 大盘强势时最大总仓位
    g.weak_max_position = 0.60          # 大盘弱势时最大总仓位
    g.max_single_position = 0.15        # 单只股票最大仓位（占总资产15%）

    # SAR 参数
    g.sar_acc = 0.02                    # SAR 加速因子
    g.sar_max = 0.2                     # SAR 最大加速因子

    # MACD 参数
    g.macd_fast = 12
    g.macd_slow = 26
    g.macd_signal = 9

    # 止盈止损参数
    g.stop_profit = 0.10                # 止盈10%
    g.stop_loss = 0.05                  # 止损5%

    # 历史数据长度（需覆盖SAR和MACD计算）
    g.data_count = 100

    # ==================== 全局变量 ====================
    g.last_pool_update = None           # 上次股票池更新日期
    g.stock_pool = []                   # 当前股票池
    g.current_max_position = g.base_max_position  # 当前实际总仓位上限

    # ==================== 定时任务 ====================
    run_daily(check_market_regime, time='09:36')   # 大盘择时
    run_daily(trade_logic, time='09:46')           # 主交易逻辑（09:40后避免波动）
    run_daily(after_market_close, time='15:10')    # 收盘记录

    log.info('SAR+MACD 策略初始化完成')

# ==================== 大盘择时 ====================
def check_market_regime(context):
    """根据中证500指数与20日均线关系决定总仓位上限"""
    current_date = context.current_dt.date()
    try:
        df = get_price(g.stock_pool_index, end_date=current_date,
                       count=21, frequency='daily', fields=['close'])
        if df is None or len(df) < 20:
            g.current_max_position = g.base_max_position
            return
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        current_close = df['close'].iloc[-1]
        if current_close > ma20:
            g.current_max_position = g.base_max_position
            log.info(f"【大盘强势】Close {current_close:.2f} > MA20 {ma20:.2f}")
        else:
            g.current_max_position = g.weak_max_position
            log.info(f"【大盘弱势】Close {current_close:.2f} <= MA20 {ma20:.2f}，启动防御模式")
    except Exception as e:
        log.error(f"大盘择时失败: {e}")
        g.current_max_position = g.base_max_position

# ==================== 主交易逻辑 ====================
def trade_logic(context):
    """每日调仓：获取股票池、根据SAR+MACD信号筛选、调整持仓"""
    current_date = context.current_dt.date()
    current_data = get_current_data()

    # 1. 获取过滤后的股票池
    stock_pool = get_current_stock_pool(context, current_date, current_data)
    if not stock_pool:
        return

    # 2. 基于SAR和MACD筛选目标股票
    target_list = select_by_sar_macd(context, stock_pool)
    log.info(f'{current_date} 目标持仓: {target_list}')

    # 3. 执行调仓（包含止盈止损及信号出场）
    adjust_positions(context, target_list, current_data)

def select_by_sar_macd(context, stock_pool):
    """从股票池中选出满足SAR上升趋势且MACD金叉的股票"""
    qualified = []
    for stock in stock_pool:
        try:
            # 获取足够长的历史数据（后复权）
            df = get_price(stock, end_date=context.current_dt.date(),
                           count=g.data_count, frequency='daily',
                           fields=['high', 'low', 'close'], fq='post')
            if df is None or len(df) < 30:
                continue
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values

            # 计算 SAR
            sar = talib.SAR(high, low, acceleration=g.sar_acc, maximum=g.sar_max)
            # 计算 MACD
            macd, signal, hist = talib.MACD(close,
                                           fastperiod=g.macd_fast,
                                           slowperiod=g.macd_slow,
                                           signalperiod=g.macd_signal)
            if np.isnan(sar[-1]) or np.isnan(macd[-1]) or np.isnan(signal[-1]):
                continue

            # 入场条件：
            # 1. 收盘价 > SAR（上升趋势）
            # 2. MACD 金叉：前一日 DIF < DEA，当日 DIF > DEA
            if close[-1] > sar[-1] and macd[-2] < signal[-2] and macd[-1] > signal[-1]:
                qualified.append(stock)
        except Exception as e:
            log.warn(f"SAR/MACD 筛选 {stock} 失败: {e}")
            continue
    # 不需要打分，直接按代码顺序或可加动量排序，这里简单处理即可
    # 为增加稳健性，可按近5日涨幅排序（保留强势股）
    if qualified:
        # 简单排序（按最近5日涨幅降序，取前g.max_hold_count只）
        rets = {}
        for s in qualified:
            try:
                df_ret = get_price(s, end_date=context.current_dt.date(),
                                   count=6, frequency='daily', fields=['close'], fq='post')
                if len(df_ret) >= 6:
                    rets[s] = (df_ret['close'].iloc[-1] / df_ret['close'].iloc[-6] - 1)
                else:
                    rets[s] = 0
            except:
                rets[s] = 0
        qualified = sorted(qualified, key=lambda x: rets.get(x, 0), reverse=True)
    return qualified[:g.max_hold_count]

def adjust_positions(context, target_list, current_data):
    """调仓：卖出不在目标列表或出场信号触发的股票；买入目标股"""
    total_value = context.portfolio.total_value
    positions = context.portfolio.positions

    # ------------------- 卖出逻辑 -------------------
    for stock in list(positions.keys()):
        pos = positions[stock]
        if pos.total_amount == 0:
            continue
        # 检查是否需要卖出
        need_sell = False
        reason = ''

        # 1. 不在目标列表
        if stock not in target_list:
            need_sell = True
            reason = '不在目标列表'

        # 2. 止盈止损（以开盘价估算，避免未来函数；盘中用current_data.price也可，但这里统一用开盘价）
        if not need_sell:
            cost = pos.avg_cost
            price = current_data[stock].day_open
            if np.isnan(price) or price <= 0:
                price = current_data[stock].last_price  # 退而求其次用最新价
            pnl_pct = (price - cost) / cost
            if pnl_pct >= g.stop_profit:
                need_sell = True
                reason = f'止盈 ({pnl_pct:.2%})'
            elif pnl_pct <= -g.stop_loss:
                need_sell = True
                reason = f'止损 ({pnl_pct:.2%})'

        # 3. 技术出场：SAR跌破或MACD死叉
        if not need_sell and can_trade(stock, current_data):
            try:
                df = get_price(stock, end_date=context.current_dt.date(),
                               count=g.data_count, frequency='daily',
                               fields=['high', 'low', 'close'], fq='post')
                if len(df) >= 30:
                    high = df['high'].values
                    low = df['low'].values
                    close = df['close'].values
                    sar = talib.SAR(high, low, acceleration=g.sar_acc, maximum=g.sar_max)
                    macd, signal, hist = talib.MACD(close,
                                                   fastperiod=g.macd_fast,
                                                   slowperiod=g.macd_slow,
                                                   signalperiod=g.macd_signal)
                    # SAR 反转：收盘价跌破 SAR
                    if close[-1] < sar[-1]:
                        need_sell = True
                        reason = 'SAR反转'
                    # MACD 死叉：前一日 DIF > DEA，当日 DIF < DEA
                    elif macd[-2] > signal[-2] and macd[-1] < signal[-1]:
                        need_sell = True
                        reason = 'MACD死叉'
            except Exception as e:
                log.warn(f"技术出场判断失败 {stock}: {e}")

        if need_sell:
            order_target(stock, 0)
            log.info(f'卖出 {stock} 原因: {reason}')

    # ------------------- 买入逻辑 -------------------
    # 计算当前持仓市值
    current_position_value = sum([p.value for p in positions.values() if p.total_amount > 0])
    max_allowed_value = total_value * g.current_max_position
    if current_position_value >= max_allowed_value:
        return  # 已达仓位上限

    # 需要买入的股票
    stocks_to_buy = [s for s in target_list if s not in positions or positions[s].total_amount == 0]
    if not stocks_to_buy:
        return

    available_cash = context.portfolio.available_cash
    num_to_buy = len(stocks_to_buy)
    # 每只股票的理想买入金额（不超过单票上限，且不超过剩余可用现金）
    ideal_per_stock = min(available_cash / num_to_buy, total_value * g.max_single_position)

    for stock in stocks_to_buy:
        if not can_trade(stock, current_data):
            continue
        price = current_data[stock].day_open
        if np.isnan(price) or price <= 0:
            continue
        target_value = min(ideal_per_stock, available_cash)
        if target_value < price * 100:   # 不够买一手
            continue
        order_target_value(stock, target_value)
        log.info(f'买入 {stock}，目标市值 {target_value:.2f}，价格 {price:.2f}')
        available_cash -= target_value

def can_trade(stock, current_data):
    """判断股票是否可交易（未停牌、未涨跌停）"""
    if current_data[stock].paused:
        return False
    if current_data[stock].high_limit <= current_data[stock].day_open:
        return False
    if current_data[stock].low_limit >= current_data[stock].day_open:
        return False
    return True

# ==================== 股票池管理 ====================
def get_current_stock_pool(context, current_date, current_data):
    """获取过滤后的股票池，每20天更新一次"""
    if g.last_pool_update is None:
        days_passed = 999
    else:
        days_passed = (current_date - g.last_pool_update).days

    if days_passed >= g.update_pool_freq:
        log.info(f'{current_date} 更新中证500股票池')
        try:
            pool = get_index_stocks(g.stock_pool_index, date=current_date)
            st_df = get_extras('is_st', pool, start_date=current_date, end_date=current_date, df=True)
            filtered = []
            for s in pool:
                if current_data[s].paused:
                    continue
                if s in st_df.columns and st_df.iloc[0][s]:
                    continue
                # 过滤次新股（上市不足一年）
                try:
                    sec_info = get_security_info(s)
                    days_listed = len(get_trade_days(sec_info.start_date, current_date))
                    if days_listed < 250:
                        continue
                except:
                    pass
                if current_data[s].day_open < g.min_price:
                    continue
                # 过滤日均成交额过低的股票
                try:
                    df_vol = get_price(s, end_date=current_date, count=20, frequency='daily',
                                       fields=['volume', 'close'], skip_paused=False, fq=None)
                    if df_vol is not None and len(df_vol) >= 10:
                        df_vol['money'] = df_vol['volume'] * df_vol['close']
                        if df_vol['money'].mean() < g.min_avg_volume:
                            continue
                except:
                    pass
                filtered.append(s)
            g.stock_pool = filtered
            g.last_pool_update = current_date
            log.info(f'股票池更新完成，数量：{len(g.stock_pool)}')
        except Exception as e:
            log.error(f'更新股票池失败: {e}')
            if not hasattr(g, 'stock_pool'):
                g.stock_pool = []
    return g.stock_pool

# ==================== 盘后记录 ====================
def after_market_close(context):
    """收盘后输出总资产和仓位"""
    total_value = context.portfolio.total_value
    position_ratio = context.portfolio.positions_value / total_value if total_value > 0 else 0
    log.info(f'{context.current_dt.date()} 总资产: {total_value:.2f}, 仓位: {position_ratio:.2%}')