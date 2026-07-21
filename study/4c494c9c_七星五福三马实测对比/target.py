# Clone from JoinQuant
# postId: 4c494c9c665fc7d0544fcd58e3f7a9f2
# backtestId: d5c523e88684d9c9a74265f32178a1ee
# title: 七星高照5.1+五福闹春5.0+三马七星1.7实测收益对比

# 克隆自聚宽文章：https://www.joinquant.com/post/67371
# 标题：小改七星高照5.0
# 作者：futures hh

# 七星高照5.0最终版 - 多标的持仓版
# 修改说明：支持持仓数量参数 HOLDINGS_NUM_DEF，实现等权重多ETF轮动
# 作者：弈剑（原版），修改：Assistant

# 2026/2/23修改说明：
# 七星高照5.0最终版 - 单/多标的自适应版
# 修改说明：
# - 当 HOLDINGS_NUM_DEF = 1 时，使用原单标的买入逻辑（含资金动态调整）
# - 当 HOLDINGS_NUM_DEF > 1 时，使用多标的等权重买入逻辑（预留佣金）
# - 卖出逻辑统一：卖出不在目标列表中的持仓
# - 10年国债替换30年

import numpy as np
import math
import pandas as pd
from jqdata import *
from datetime import time

# ================== 【全局静态常量】==================
ETF_POOL_DEF = [
    # 境外
    "159941.XSHE", #纳指ETF
    "159509.XSHE", #纳指科技ETF
    "513500.XSHG", #标普500ETF
    "513520.XSHG", #日经ETF
    "513030.XSHG", #德国ETF
    "513080.XSHG", #法国ETF
    "159100.XSHE", #巴西ETF
    "159329.XSHE", #沙特ETF
    # 商品
    "518880.XSHG", #黄金ETF
    "159980.XSHE", #有色ETF
    "161226.XSHE", #白银ETF
    "159985.XSHE", #豆粕ETF
    "159981.XSHE", #能源化工ETF
    "501018.XSHG", #南方原油LOF
    # 债券
    "511260.XSHG", #10年国债ETF
    # 国内
    "513130.XSHG", #恒生科技ETF
    "520500.XSHG", #恒生创新药ETF
    "513970.XSHG", #消费ETF
    "513690.XSHG", #港股红利ETF
    "159915.XSHE", #创业板ETF
    "563300.XSHG", #中证2000ETF
    "563360.XSHG", #中证A500ETF
    "510410.XSHG", #资源ETF
    "515210.XSHG", #钢铁ETF
    "562800.XSHG", #稀有金属ETF
    "159928.XSHE", #中证消费ETF
    "512690.XSHG", #中证酒ETF
    "159992.XSHE", #创新药ETF
    "588220.XSHG", #科创100ETF
    "159819.XSHE", #人工智能ETF
    "159851.XSHE", #金融科技ETF
    "159326.XSHE", #电网设备ETF
    "515030.XSHG", #新能源车ETF
    "516160.XSHG", #新能源ETF
    "512710.XSHG", #军工ETF
    "515220.XSHG", #煤炭ETF
    "512880.XSHG", #证券ETF
    "159378.XSHE", #通用航空ETF
    "159206.XSHE", #卫星ETF
    "516510.XSHG", #云计算ETF
    "515050.XSHG", #5GETF
    "512170.XSHG", #医疗ETF
    "159870.XSHE", #化工ETF
    "159611.XSHE", #电力ETF
    "159995.XSHE", #芯片ETF
    "515790.XSHG", #光伏ETF
    "159755.XSHE", #电池ETF
    "515000.XSHG", #科技ETF
    "562500.XSHG", #机器人ETF
]

# ============== 策略参数默认值 ==============
HOLDINGS_NUM_DEF = 3          # 持仓ETF数量（可调节：1=单标的，>1=多标的等权重）
LOOKBACK_DAYS_DEF = 24        # 长期动量计算周期
DEFENSIVE_ETF_DEF = "511880.XSHG"  # 防御性ETF（银华日利）
MIN_MONEY_DEF = 5000          # 最小交易金额

STOP_LOSS_DEF = 0.95          # 固定百分比止损线
LOSS_DEF = 0.965              # 近3日跌幅止损线

ENABLE_VOLUME_CHECK_DEF = True
VOLUME_LOOKBACK_DEF = 5
VOLUME_THRESHOLD_DEF = 2.5
VOLUME_RETURN_LIMIT_DEF = 1

USE_R2_FILTER_DEF = True
R2_MIN_THRESHOLD_DEF = 0.4

MIN_SCORE_THRESHOLD_DEF = 0.0
MAX_SCORE_THRESHOLD_DEF = 5.0

# =================== 【初始化函数】 =====================
def initialize(context):
    g.context = context
    g.etf_pool = ETF_POOL_DEF

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')

    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0, close_tax=0,
            open_commission=0.0002, close_commission=0.0002,
            close_today_commission=0, min_commission=5,
        ), type="fund"
    )
    set_benchmark("000300.XSHG")

    g.lookback_days = LOOKBACK_DAYS_DEF
    g.holdings_num = HOLDINGS_NUM_DEF
    g.defensive_etf = DEFENSIVE_ETF_DEF
    g.min_money = MIN_MONEY_DEF

    g.stop_loss = STOP_LOSS_DEF
    g.loss = LOSS_DEF
    g.stopped_etfs = set()

    g.enable_volume_check = ENABLE_VOLUME_CHECK_DEF
    g.volume_lookback = VOLUME_LOOKBACK_DEF
    g.volume_threshold = VOLUME_THRESHOLD_DEF
    g.volume_return_limit = VOLUME_RETURN_LIMIT_DEF

    g.use_r2_filter = USE_R2_FILTER_DEF
    g.r2_min_threshold = R2_MIN_THRESHOLD_DEF

    g.min_score_threshold = MIN_SCORE_THRESHOLD_DEF
    g.max_score_threshold = MAX_SCORE_THRESHOLD_DEF

    g.positions = {}

    # 交易调度
    run_daily(check_positions, time='09:25')
    run_daily(check_stop_loss_minutely, time='every_bar')
    run_daily(etf_sell_trade, time='14:00')
    run_daily(etf_buy_trade, time='14:01')

    log.info(f"""策略参数初始化完成:
    - ETF池大小: {len(g.etf_pool)} 只ETF | 动量周期: {g.lookback_days} 天
    - 目标持仓数量: {g.holdings_num} 只 | 成交量过滤: {'启用' if g.enable_volume_check else '禁用'}
    - 防御ETF: {g.defensive_etf} | 实时止损阈值: {(1-g.stop_loss)*100:.1f}%
    - 运行模式: {'单标的' if g.holdings_num == 1 else '多标的等权重'}
""")

# ============ 获取目标ETF列表（统一入口） ===============
def get_target_etf_list(context):
    """
    根据 holdings_num 返回需要持有的目标ETF代码列表
    逻辑：
    1. 获取所有ETF的得分排名
    2. 筛选得分 >= g.min_score_threshold 的ETF
    3. 取前 g.holdings_num 个作为进攻型目标
    4. 若无进攻型目标且防御ETF可用，则返回[防御ETF]
    5. 否则返回空列表
    """
    ranked_etfs = get_ranked_etfs(context)
    qualified = [item for item in ranked_etfs if item['score'] >= g.min_score_threshold]
    if qualified:
        target_etfs = [item['etf'] for item in qualified[:g.holdings_num]]
        log.info(f"🎯 进攻型目标ETF ({len(target_etfs)}只): {[get_security_name(etf) for etf in target_etfs]}")
        return target_etfs
    else:
        if check_defensive_etf_available(context):
            log.info(f"🛡️ 防御型目标ETF: {get_security_name(g.defensive_etf)}")
            return [g.defensive_etf]
        else:
            log.info("💤 无任何目标ETF，将空仓")
            return []

# ============ 持仓检查（不变） ===============
def check_positions(context):
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.debug(f"📊 持仓检查: {security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")

# ================== 实时止损（不变）==================
def check_stop_loss_minutely(context):
    current_time = context.current_dt.time()
    if not ((time(9, 30) <= current_time <= time(11, 30)) or 
            (time(13, 00) <= current_time <= time(15, 00))):
        return
    check_secs = [s for s in context.portfolio.positions if s in g.etf_pool or s == g.defensive_etf]
    for security in check_secs:
        try:
            pos = context.portfolio.positions[security]
            if pos.total_amount <= 0:
                continue
            current_price = pos.price
            cost_price = pos.avg_cost
            security_name = get_security_name(security)
            if cost_price <= 0:
                continue
            if pos.closeable_amount <= 0:
                continue
            stop_loss_price = cost_price * g.stop_loss * 1.001
            loss_pct = (current_price / cost_price - 1) * 100
            if current_price <= stop_loss_price:
                success = smart_order_target_value(security, 0, context)
                if success:
                    g.stopped_etfs.add(security)
                    log.info(f"🚨 【实时止损成功】盘中止损卖出：{security} {security_name} | 成本：{cost_price:.3f} | 当前价：{current_price:.3f} | 亏损：{loss_pct:.2f}%")
                else:
                    log.error(f"🚨 【实时止损失败】盘中止损失败：{security} {security_name} | 亏损：{loss_pct:.2f}% | 无法卖出")
        except Exception as e:
            log.error(f"🚨 【实时止损检查失败】{security}：{e}")

# ==================== 统一卖出函数 ====================
def etf_sell_trade(context):
    """
    统一卖出逻辑：卖出不在目标列表中的所有持仓
    """
    log.info("======================== 卖出操作开始 ========================")
    target_etfs = get_target_etf_list(context)
    target_set = set(target_etfs)

    for security in list(context.portfolio.positions.keys()):
        if security not in g.etf_pool and security != g.defensive_etf:
            continue
        pos = context.portfolio.positions[security]
        if pos.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            success = smart_order_target_value(security, 0, context)
            if success:
                log.debug(f"📤 卖出非目标持仓: {security} {security_name}")
            else:
                log.warning(f"❌ 卖出失败: {security} {security_name}")
    log.info("======================== 卖出操作完成 ========================")

# ==================== 买入函数（根据 holdings_num 分支）====================
def etf_buy_trade(context):
    """
    买入函数：根据 holdings_num 选择单标的或多标的模式
    """
    log.info("======================== 买入操作开始 ========================")
    target_etfs = get_target_etf_list(context)
    if not target_etfs:
        log.info("无目标ETF，保持空仓")
        log.info("======================== 买入操作完成 ========================")
        return

    if g.holdings_num == 1:
        # ---------- 单标的模式：使用原初始策略的买入逻辑（含资金调整）----------
        target_etf = target_etfs[0]  # 取第一个（也是唯一一个）
        # 检查其他持仓是否已清空
        current_positions = list(context.portfolio.positions.keys())
        current_etf_positions = [pos for pos in current_positions if pos in g.etf_pool or pos == g.defensive_etf]
        other_positions = [pos for pos in current_etf_positions if pos != target_etf]
        if other_positions:
            for pos in other_positions:
                if context.portfolio.positions[pos].total_amount > 0:
                    log.info(f"⚠️ 尚有其他持仓 {get_security_name(pos)} 未卖出，等待卖出完成后再买入新标的")
                    log.info("======================== 买入操作完成 ========================")
                    return

        total_value = context.portfolio.total_value
        target_value = total_value
        current_value = 0
        if target_etf in context.portfolio.positions:
            pos = context.portfolio.positions[target_etf]
            current_value = pos.total_amount * pos.price

        need_cash = max(0, target_value - current_value)
        available_cash = context.portfolio.available_cash

        def calc_commission(amount):
            return max(5, amount * 0.0002)

        if need_cash > 0:
            estimated_commission = calc_commission(need_cash)
            total_required = need_cash + estimated_commission
            if total_required > available_cash + 1e-6:
                log.info(f"⚠️ 可用现金不足：需要 {total_required:.2f}，实际可用 {available_cash:.2f}，尝试调整目标市值")
                if available_cash > 25000 + 5:
                    max_buy_cash = available_cash / 1.0002 * 0.999999
                else:
                    max_buy_cash = max(0, available_cash - 5)
                new_target = current_value + max_buy_cash
                if new_target < target_value - 1e-6:
                    log.info(f"⚖️ 调整目标市值：从 {target_value:.2f} 降至 {new_target:.2f}")
                    target_value = new_target
                    need_cash = max_buy_cash
                else:
                    log.info("调整后目标未变，无法买入")
                    log.info("======================== 买入操作完成 ========================")
                    return
                if need_cash > 0:
                    new_commission = calc_commission(need_cash)
                    if need_cash + new_commission > available_cash + 1e-6:
                        log.info("⚠️ 调整后仍现金不足，放弃买入")
                        log.info("======================== 买入操作完成 ========================")
                        return
            else:
                log.debug(f"资金充足，可直接买入，需现金 {need_cash:.2f}")
        else:
            log.debug("无需新增现金")

        if abs(current_value - target_value) > target_value * 0.05 or current_value == 0:
            success = smart_order_target_value(target_etf, target_value, context)
            if success:
                action = "买入" if current_value < target_value else "调仓"
                log.debug(f"📦 {action}: {target_etf} {get_security_name(target_etf)}，目标金额: {target_value:.2f}")
        else:
            log.debug("持仓市值与目标接近，无需调仓")

    else:  # g.holdings_num > 1 多标的模式
        # ---------- 多标的等权重买入逻辑（预留佣金）----------
        total_value = context.portfolio.total_value
        available_cash = context.portfolio.available_cash
        num_targets = len(target_etfs)

        # 预留佣金估算
        estimated_commission = max(5 * num_targets, total_value * 0.0002)
        safe_total_value = total_value - estimated_commission
        if safe_total_value <= 0:
            log.info("⚠️ 预留佣金后可用资产为负，无法买入")
            log.info("======================== 买入操作完成 ========================")
            return

        target_value_per_etf = safe_total_value / num_targets
        log.info(f"💰 总资产: {total_value:.2f}, 预留佣金: {estimated_commission:.2f}, 等权重每只目标市值: {target_value_per_etf:.2f}")

        for etf in target_etfs:
            current_value = 0
            if etf in context.portfolio.positions:
                pos = context.portfolio.positions[etf]
                current_value = pos.total_amount * pos.price

            if abs(current_value - target_value_per_etf) > target_value_per_etf * 0.05 or current_value == 0:
                success = smart_order_target_value(etf, target_value_per_etf, context)
                if success:
                    log.debug(f"📦 调仓 {etf} {get_security_name(etf)} 至目标市值 {target_value_per_etf:.2f}")
            else:
                log.debug(f"✅ {etf} {get_security_name(etf)} 市值已接近目标，无需调仓")

    log.info("======================== 买入操作完成 ========================")

# ==================== 以下函数与原策略完全一致（未修改）====================
def get_ranked_etfs(context):
    etf_metrics = []
    filtered_pool = g.etf_pool
    current_data = get_current_data()
    for etf in filtered_pool:
        if current_data[etf].paused:
            log.debug(f"{etf}: 今���停牌，跳过计算")
            continue
        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            if 0 < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)
            else:
                log.debug(f"⚠️ {etf} 得分不满足要求！")
    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics

def calculate_momentum_metrics(context, etf):
    try:
        lookback = g.lookback_days + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        current_data = get_current_data()
        if prices.empty or len(prices) < g.lookback_days:
            log.debug(f"{etf}: 历史数据为空或数据不足（仅{len(prices)}天），跳过计算")
            return None
        current_price = current_data[etf].last_price
        if current_price <= 0:
            log.debug(f"{etf}: 实时价格异常（{current_price}），跳过计算")
            return None
        price_series = np.append(prices["close"].values, current_price)

        if len(price_series) >= 4:
            day1_prev = price_series[-2] if price_series[-2] > 0 else 1
            day2_prev = price_series[-3] if price_series[-3] > 0 else 1
            day3_prev = price_series[-4] if price_series[-4] > 0 else 1
            day1_ratio = price_series[-1] / day1_prev
            day2_ratio = price_series[-2] / day2_prev
            day3_ratio = price_series[-3] / day3_prev
            min_ratio = min(day1_ratio, day2_ratio, day3_ratio)
            if min_ratio < g.loss:
                log.debug(f"⚠️ {etf} 近3日单日最大跌幅超过阈值，直接过滤")
                return None

        if g.enable_volume_check and len(price_series) > g.lookback_days:
            volume_ratio = get_volume_ratio(context, etf)
            volume_annualized = get_annualized_returns(price_series, g.lookback_days)
            if volume_ratio is not None:
                if volume_annualized > g.volume_return_limit:
                    log.debug(f"{etf}: 高位放量过滤")
                    return None

        recent_price_series = price_series[-(g.lookback_days + 1):]
        y = np.log(recent_price_series)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1

        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0

        if g.use_r2_filter:
            if not (g.r2_min_threshold <= r_squared <= 1):
                log.debug(f"{etf}: R²={r_squared:.4f} 不在阈值内，过滤")
                return None

        score = annualized_returns * r_squared

        if len(price_series) >= 4:
            day1_ratio = price_series[-1] / price_series[-2]
            day2_ratio = price_series[-2] / price_series[-3]
            day3_ratio = price_series[-3] / price_series[-4]
            if min(day1_ratio, day2_ratio, day3_ratio) < g.loss:
                score = 0
                log.debug(f"⚠️ {etf} 近3日有单日跌幅超设定值，得分置零")

        return {
            'etf': etf,
            'current_price': current_price,
            'slope': slope,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
        }
    except Exception as e:
        log.warning(f"计算{etf}动量指标时出错: {e}")
        return None

def get_volume_ratio(context, security, lookback_days=None, threshold=None):
    if lookback_days is None:
        lookback_days = g.volume_lookback
    if threshold is None:
        threshold = g.volume_threshold
    try:
        hist_data = attribute_history(security, lookback_days, '1d', ['volume'])
        if hist_data.empty or len(hist_data) < lookback_days:
            return None
        avg_volume = hist_data['volume'].mean()
        today = context.current_dt.date()
        df_vol = get_price(
            security,
            start_date=today,
            end_date=context.current_dt,
            frequency='1m',
            fields=['volume'],
            skip_paused=False,
            fq='pre',
            panel=True,
            fill_paused=False
        )
        if df_vol is None or df_vol.empty:
            return None
        current_volume = df_vol['volume'].sum()
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        if volume_ratio > threshold:
            return volume_ratio
        else:
            return None
    except Exception as e:
        log.warning(f"成交量检测失败 {security}: {e}")
        return None

def get_annualized_returns(price_series, lookback_days):
    recent_price_series = price_series[-(lookback_days + 1):]
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    annualized_returns = math.exp(slope * 250) - 1
    return annualized_returns

def get_security_name(security):
    current_data = get_current_data()
    return current_data[security].name

def check_defensive_etf_available(context):
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    if current_data[defensive_etf].paused:
        log.info(f"防御性ETF {defensive_etf} 今日停牌")
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        log.info(f"防御性ETF {defensive_etf} 当前涨停")
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        log.info(f"防御性ETF {defensive_etf} 当前跌停")
        return False
    return True

def smart_order_target_value(security, target_value, context):
    current_data = get_current_data()
    if current_data[security].paused:
        log.info(f"{security} {get_security_name(security)}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {get_security_name(security)}: 当前涨停，跳过买入")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {get_security_name(security)}: 当前跌停，跳过卖出")
        return False
    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"{security} {get_security_name(security)}: 当前价格为0，跳过交易")
        return False
    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < g.min_money:
        log.info(f"{security} {get_security_name(security)}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过交易")
        return False
    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {get_security_name(security)}: 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)
    if amount_diff > 0:
        required_cash = amount_diff * current_price
        estimated_commission = max(5, required_cash * 0.0002)
        total_required = required_cash + estimated_commission
        available_cash = context.portfolio.available_cash
        if total_required > available_cash + 1e-6:
            log.info(f"⚠️ {security} {get_security_name(security)}: 现金不足（含佣金），需要 {total_required:.2f}，可用 {available_cash:.2f}，跳过买入")
            return False
    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            g.positions[security] = target_amount
            security_name = get_security_name(security)
            if amount_diff > 0:
                log.info(f"📥 买入 {security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}")
            else:
                log.info(f"📤 卖出 {security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}")
            return True
        else:
            log.warning(f"下单失败: {security} {get_security_name(security)}，数量: {amount_diff}")
            return False
    return False

def trade(context):
    pass