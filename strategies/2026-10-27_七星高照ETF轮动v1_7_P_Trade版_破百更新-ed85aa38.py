# Clone from JoinQuant
# postId: ed85aa38f5aa1ca413cbb9d50e3ca61a
# backtestId: 9ebfc2aff3a91920e345e34e97639b53
# title: 七星高照ETF轮动v1.7_P_Trade版（破百更新）

# 七星高照ETF轮动v1.7_P_Trade版
# 修改时间：2026-05-24
# 修改作者：云白山人
#
#
# 策略名称：七星高照ETF轮动策略-V1.7
# 策略作者：屌丝逆袭量化
# 优化时间：2026-3-29
# 优化内容：
# 1、将盈利保护模块独立拆分，支持自定义多个检查时间点（如11:00）
# 2、移除原有卖出函数中的盈利保护逻辑，由独立检查函数负责
# 3、优化各过滤顺序，统一在排名计算中排除不符合条件的ETF

import numpy as np
import math
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
    set_benchmark("510300.XSHG")

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    log.info("========== 策略初始化开始 ==========")

    # ---------- ETF池 ----------
    g.etf_pool = [
        "518880.XSHG",   # 黄金ETF
        "159985.XSHE",   # 豆粕ETF
        "501018.XSHG",   # 南方原油
        "161226.XSHE",   # 白银LOF
        "513100.XSHG",   # 纳指ETF
        "159915.XSHE",   # 创业板ETF
        "511220.XSHG",   # 城投债ETF
    ]
        # 大ETF池
    g.etf_pool_bak  = [
        # 大宗商品ETF
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色ETF（跟踪有色金属板块）
        "159985.XSHE",  # 豆粕ETF（跟踪豆粕期货价格）
        "501018.XSHG",  # 南方原油（投资原油相关资产）
        '161226.XSHE',  # 白银LOF
        "159981.XSHE",  # 能源化工ETF
        # 国际ETF
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
        "513730.XSHG",  # 东南亚ETF
        # 香港ETF
        "159792.XSHE",  # 港股互联ETF
        "513130.XSHG",  # 恒生科技
        "513050.XSHG",  # 中概互联网ETF
        "159920.XSHE",  # 恒生ETF
        "513690.XSHG",  # 港股红利
        # 指数ETF
        "510300.XSHG",  # 沪深300ETF
        "510500.XSHG",  # 中证500ETF
        "510050.XSHG",  # 上证50ETF
        "510210.XSHG",  # 上证ETF
        "159915.XSHE",  # 创业板ETF
        "588080.XSHG",  # 科创50
        "512100.XSHG",  # 中证1000ETF
        "563360.XSHG",  # A500-ETF
        "563300.XSHG",  # 中证2000ETF
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
    g.premium_threshold = 0.20          # 溢价率阈值（10%）

    # ---------- 运行时变量 ----------
    g.rankings_cache = {'date': None, 'data': None}   # 排名缓存

    # ---------- 交易调度 ----------
    run_daily(check_positions, time='09:10')
    run_daily(etf_sell_trade, time='14:00')
    run_daily(etf_buy_trade, time='14:01')

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
    log.info("========== 策略初始化完成 ==========")


# ==================== 盈利保护独立检查函数（新增） ====================
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

    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price

    if current_price <= max_high * (1 - threshold):
        log.info(f"🔻 {security} {get_name(security)} 触发盈利保护：当前价{current_price:.3f}，最近{lookback}日最高{max_high:.3f}，回撤{(1 - current_price/max_high)*100:.2f}% > {threshold*100:.0f}%")
        return True
    else:
        return False


# ==================== 溢价率获取函数 ====================
def get_premium_rate(code, date):
    """
    获取指定日期的溢价率（使用前一日净值，适合盘中判断）
    参数:
        code: 基金代码
        date: 日期，datetime.date 对象
    返回:
        premium_rate: 溢价率（小数形式），None 表示获取失败
        price: 场内交易价格
        net_value: 基金净值
    """
    # 获取场内交易价格
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

    # 获取基金净值（优先 get_extras，回退 finance.FUND_NET_VALUE）
    net_data = get_extras('unit_net_value', code, start_date=date, end_date=date, df=True)
    if net_data.empty or pd.isna(net_data[code].iloc[0]):
        # 备用方法
        try:
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == code,
                finance.FUND_NET_VALUE.day == date
            )
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
            else:
                log.debug(f"{date} {code} 无净值数据")
                return None, None, None
        except:
            log.debug(f"{date} {code} 查询净值异常")
            return None, None, None
    else:
        net_value = net_data[code].iloc[0]

    premium_rate = (price - net_value) / net_value
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

        # ===== 2. 成交量过滤（排除） =====
        if g.enable_volume_check:
            vol_ratio = get_volume_ratio(context, etf)
            if vol_ratio is not None:
                annualized = get_annualized_returns(price_series, g.lookback_days)
                if annualized > g.volume_return_limit:
                    log.info(f"📉 {etf} {name} 成交量放量{vol_ratio:.1f}倍，且年化{annualized*100:.1f}% > 阈值{g.volume_return_limit*100:.1f}%，过滤")
                    return None

        # ===== 3. 短期动量过滤（排除） =====
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = 0

        if g.use_short_momentum_filter and short_annualized < g.short_momentum_threshold:
            log.debug(f"{etf} {name} 短期动量{short_annualized*100:.1f}% < 阈值{g.short_momentum_threshold*100:.1f}%，过滤")
            return None

        # ===== 4. 长期动量计算（得分） =====
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

        # ===== 5. 近3日单日跌幅过滤（排除） =====
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


# ==================== 卖出模块 ====================
def check_positions(context):
    """每日开盘检查持仓状态，仅用于日志"""
    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")


def etf_sell_trade(context):
    """卖出不符合条件的持仓（排名变化、溢价率过高）"""
    log.info("========== 卖出操作开始 ==========")

    ranked = get_cached_rankings(context)
    # 确定目标ETF列表（得分前N名且满足得分阈值）
    target_etfs = []
    for m in ranked[:g.holdings_num]:
        if m['score'] >= g.min_score_threshold:
            target_etfs.append(m['etf'])
    # 若没有目标ETF且防御可用，则把防御ETF作为目标（供卖出判断用）
    defensive_available = check_defensive_etf_available(context)
    if not target_etfs and defensive_available:
        target_etfs = [g.defensive_etf]

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

    # 溢价率检查（保留）
    if g.enable_premium_filter:
        prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
        for sec in list(context.portfolio.positions.keys()):
            if sec not in g.etf_pool and sec != g.defensive_etf:
                continue
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                premium, _, _ = get_premium_rate(sec, prev_date)
                if premium is not None and premium > g.premium_threshold:
                    if smart_order_target_value(sec, 0, context):
                        log.info(f"🚨 溢价率过高 {sec} {get_name(sec)} 溢价率{premium*100:.2f}% > {g.premium_threshold*100:.0f}%，卖出")

    log.info("========== 卖出操作完成 ==========")


# ==================== 买入模块 ====================
def etf_buy_trade(context):
    """买入符合条件的ETF，等权分配，按排名顺序逐个尝试直到凑够持仓数量"""
    log.info("========== 买入操作开始 ==========")

    ranked = get_cached_rankings(context)
    # 打印排名前5的指标（调试用）
    log.info("=== ETF排名前5 ===")
    for i, m in enumerate(ranked[:5]):
        log.info(f"排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f} 年化{m['annualized_returns']*100:.2f}% R²={m['r_squared']:.4f}")

    # ---------- 确定目标ETF列表：依次尝试排名靠前的ETF ----------
    target_etfs = []
    prev_date = None
    if g.enable_premium_filter:
        # 获取前一个交易日用于溢价率计算
        prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]

    for m in ranked:   # 按得分从高到低遍历所有ETF
        if len(target_etfs) >= g.holdings_num:
            break   # 已凑够目标持仓数量

        # 得分过滤
        if m['score'] < g.min_score_threshold:
            continue

        etf = m['etf']

        # ----- 盈利保护检查（买入前再次检查，防止卖了又买）-----
        if g.enable_profit_protection and check_profit_protection(etf, context):
            log.info(f"🚫 {etf} {get_name(etf)} 触发盈利保护，从买入候选列表中排除")
            continue

        # 溢价率过滤（若启用）
        if g.enable_premium_filter:
            premium, price, net = get_premium_rate(etf, prev_date)
            if premium is None:
                log.info(f"⚠️ {etf} {get_name(etf)} 无法获取溢价率，视为不合格，跳过")
                continue
            if premium > g.premium_threshold:
                log.info(f"🚫 {etf} {get_name(etf)} 溢价率{premium*100:.2f}% > {g.premium_threshold*100:.0f}%，跳过")
                continue
            else:
                log.info(f"✅ {etf} {get_name(etf)} 溢价率{premium*100:.2f}% ≤ {g.premium_threshold*100:.0f}%，通过")

        # 通过所有检查，加入目标列表
        target_etfs.append(etf)
        log.info(f"🎯 目标ETF {len(target_etfs)}: {etf} {m['etf_name']} 得分{m['score']:.4f}")

    # ---------- 防御模式判断 ----------
    if not target_etfs:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
            log.info(f"🛡️ 进入防御模式，选择防御ETF：{g.defensive_etf} {get_name(g.defensive_etf)}")
        else:
            log.info("💤 无目标ETF且防御不可用，保持空仓")
            return

    # ... 后续调仓逻辑不变 ...

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
    


# ================================================================================
# 以下为聚宽版本转PTrade版本的完整代码（已注释）
# ================================================================================
#
# # 策略名称：七星高照ETF轮动策略-V1.7 (PTrade版)
# # 策略作者：屌丝逆袭量化
# # 转换时间：2026-05-24
# # 转换作者：云白山人
#
# import numpy as np
# import math
#
# # ==================== 初始化模块 ====================
# def initialize(ContextInfo):
#     """
#     初始化函数：设置交易参数、ETF池、核心参数、调度任务
#     """
#     # ---------- 交易设置 ----------
#     # PTrade中设置基准和手续费的方式
#     ContextInfo.benchmark = '510300.SH'
#
#     log.info("========== 策略初始化开始 ==========")
#
#     # ---------- ETF池 ----------
#     ContextInfo.etf_pool = [
#         "518880.SH",   # 黄金ETF
#         "159985.SZ",   # 豆粕ETF
#         "501018.SH",   # 南方原油
#         "161226.SZ",   # 白银LOF
#         "513100.SH",   # 纳指ETF
#         "159915.SZ",   # 创业板ETF
#         "511220.SH",   # 城投债ETF
#     ]
#     # 大ETF池
#     ContextInfo.etf_pool_bak = [
#         # 大宗商品ETF
#         "518880.SH",  # 黄金ETF
#         "159980.SZ",  # 有色ETF
#         "159985.SZ",  # 豆粕ETF
#         "501018.SH",  # 南方原油
#         '161226.SZ',  # 白银LOF
#         "159981.SZ",  # 能源化工ETF
#         # 国际ETF
#         "513100.SH",  # 纳指ETF
#         "159509.SZ",  # 纳指科技ETF
#         "513290.SH",  # 纳指生物ETF
#         "513500.SH",  # 标普500ETF
#         "159529.SZ",  # 标普消费
#         "513400.SH",  # 道琼斯ETF
#         "513520.SH",  # 日经225ETF
#         "513030.SH",  # 德国30ETF
#         "513080.SH",  # 法国ETF
#         "513310.SH",  # 中韩半导体ETF
#         "513730.SH",  # 东南亚ETF
#         # 香港ETF
#         "159792.SZ",  # 港股互联ETF
#         "513130.SH",  # 恒生科技
#         "513050.SH",  # 中概互联网ETF
#         "159920.SZ",  # 恒生ETF
#         "513690.SH",  # 港股红利
#         # 指数ETF
#         "510300.SH",  # 沪深300ETF
#         "510500.SH",  # 中证500ETF
#         "510050.SH",  # 上证50ETF
#         "510210.SH",  # 上证ETF
#         "159915.SZ",  # 创业板ETF
#         "588080.SH",  # 科创50
#         "512100.SH",  # 中证1000ETF
#         "563360.SH",  # A500-ETF
#         "563300.SH",  # 中证2000ETF
#         # 风格ETF
#         "512890.SH",  # 红利低波ETF
#         "159967.SZ",  # 创业板成长ETF
#         "512040.SH",  # 价值ETF
#         "159201.SZ",  # 自由现金流ETF
#         # 债券ETF
#         "511380.SH",  # 可转债ETF
#         "511010.SH",  # 国债ETF
#         "511220.SH",  # 城投债ETF
#     ]
#
#     # ---------- 核心参数 ----------
#     ContextInfo.lookback_days = 25               # 动量计算周期
#     ContextInfo.holdings_num = 1                 # 候选数量
#     ContextInfo.defensive_etf = "511880.SH"      # 防御ETF（货币基金）
#     ContextInfo.min_money = 5000                 # 最小交易金额
#
#     # ---------- 盈利保护参数 ----------
#     ContextInfo.enable_profit_protection = True                      # 盈利保护开关
#     ContextInfo.profit_protection_lookback = 1                       # 盈利保护回看周期（天）
#     ContextInfo.profit_protection_threshold = 0.05                   # 盈利保护回撤阈值（5%）
#     ContextInfo.profit_protection_check_times = ['11:00']            # 盈利保护检查时间点
#
#     ContextInfo.loss = 0.97                      # 近3日单日跌幅阈值
#     ContextInfo.min_score_threshold = 0          # 最低得分
#     ContextInfo.max_score_threshold = 100.0      # 最高得分
#
#     # ---------- 成交量过滤 ----------
#     ContextInfo.enable_volume_check = True
#     ContextInfo.volume_lookback = 5
#     ContextInfo.volume_threshold = 2
#     ContextInfo.volume_return_limit = 1          # 年化收益>100%时启用放量过滤
#
#     # ---------- 短期动量过滤 ----------
#     ContextInfo.use_short_momentum_filter = True
#     ContextInfo.short_lookback_days = 10
#     ContextInfo.short_momentum_threshold = 0.0
#
#     # ---------- 溢价率过滤 ----------
#     ContextInfo.enable_premium_filter = True      # 是否启用溢价率过滤
#     ContextInfo.premium_threshold = 0.20          # 溢价率阈值
#
#     # ---------- 运行时变量 ----------
#     ContextInfo.rankings_cache = {'date': None, 'data': None}   # 排名缓存
#
#     # ---------- 交易调度（PTrade使用schedule） ----------
#     # PTrade的定时器注册方式
#     ContextInfo.schedule('09:10', 'check_positions')
#     ContextInfo.schedule('14:00', 'etf_sell_trade')
#     ContextInfo.schedule('14:01', 'etf_buy_trade')
#
#     # 动态注册盈利保护检查时间点
#     for check_time in ContextInfo.profit_protection_check_times:
#         ContextInfo.schedule(check_time, 'profit_protection_check')
#         log.info(f"已注册盈利保护检查时间：{check_time}")
#
#     log.info(f"策略初始化完成：ETF池{len(ContextInfo.etf_pool)}只，动量周期{ContextInfo.lookback_days}天，持仓{ContextInfo.holdings_num}只")
#     log.info("========== 策略初始化完成 ==========")
#
#
# # ==================== 盈利保护独立检查函数 ====================
# def profit_protection_check(ContextInfo):
#     """
#     独立执行的盈利保护检查函数
#     """
#     if not ContextInfo.enable_profit_protection:
#         log.debug("盈利保护模块已关闭，跳过检查")
#         return
#
#     log.info("========== 盈利保护独立检查开始 ==========")
#     positions = ContextInfo.positions  # PTrade获取持仓
#     for sec in list(positions.keys()):
#         if sec not in ContextInfo.etf_pool and sec != ContextInfo.defensive_etf:
#             continue
#         pos = positions[sec]
#         if pos.get('volume', 0) > 0:
#             if check_profit_protection(sec, ContextInfo):
#                 if smart_order_target_value(sec, 0, ContextInfo):
#                     log.info(f"🛡️ 盈利保护卖出（独立检查）：{sec} {get_name(sec, ContextInfo)}")
#     log.info("========== 盈利保护独立检查完成 ==========")
#
#
# # ==================== 盈利保护检查函数 ====================
# def check_profit_protection(security, ContextInfo, lookback=None, threshold=None):
#     """
#     检查是否触发盈利保护
#     """
#     if not ContextInfo.enable_profit_protection:
#         return False
#
#     lookback = lookback or ContextInfo.profit_protection_lookback
#     threshold = threshold or ContextInfo.profit_protection_threshold
#
#     # PTrade获取历史数据
#     hist = ContextInfo.get_market_data(
#         security,
#         period='1d',
#         count=lookback,
#         field='high'
#     )
#     if hist is None or len(hist) < lookback:
#         log.debug(f"{security} {get_name(security, ContextInfo)} 历史数据不足{lookback}天")
#         return False
#
#     max_high = max(hist) if isinstance(hist, list) else hist.max()
#     current_price = get_current_price(security, ContextInfo)
#
#     if current_price and current_price <= max_high * (1 - threshold):
#         log.info(f"🔻 {security} {get_name(security, ContextInfo)} 触发盈利保护")
#         return True
#     else:
#         return False
#
#
# # ==================== 核心计算模块 ====================
# def get_cached_rankings(ContextInfo):
#     """获取缓存的ETF排名"""
#     today = ContextInfo.current_date
#     if ContextInfo.rankings_cache['date'] != today:
#         log.info("重新计算ETF排名...")
#         ranked = get_ranked_etfs(ContextInfo)
#         ContextInfo.rankings_cache = {'date': today, 'data': ranked}
#     else:
#         log.debug("使用缓存的ETF排名")
#     return ContextInfo.rankings_cache['data']
#
#
# def get_ranked_etfs(ContextInfo):
#     """计算所有ETF的动量得分"""
#     etf_metrics = []
#     for etf in ContextInfo.etf_pool:
#         # 停牌过滤（PTrade接口）
#         if is_paused(etf, ContextInfo):
#             log.debug(f"{etf} {get_name(etf, ContextInfo)} 停牌，跳过")
#             continue
#
#         metrics = calculate_momentum_metrics(ContextInfo, etf)
#         if metrics is not None:
#             if ContextInfo.min_score_threshold < metrics['score'] < ContextInfo.max_score_threshold:
#                 etf_metrics.append(metrics)
#             else:
#                 log.debug(f"{etf} {metrics['etf_name']} 得分{metrics['score']:.2f}超出阈值")
#
#     etf_metrics.sort(key=lambda x: x['score'], reverse=True)
#     return etf_metrics
#
#
# def calculate_momentum_metrics(ContextInfo, etf):
#     """计算单只ETF的动量指标"""
#     try:
#         name = get_name(etf, ContextInfo)
#         lookback = max(ContextInfo.lookback_days, ContextInfo.short_lookback_days) + 20
#
#         # PTrade获取历史数据
#         prices = ContextInfo.get_market_data(
#             etf,
#             period='1d',
#             count=lookback,
#             field=['close', 'high']
#         )
#         if prices is None or len(prices) < ContextInfo.lookback_days:
#             log.debug(f"{etf} {name} 历史数据不足")
#             return None
#
#         current_price = get_current_price(etf, ContextInfo)
#         if not current_price:
#             return None
#
#         # 价格序列
#         close_prices = prices['close'] if isinstance(prices, dict) else prices[:, 0]
#         price_series = np.append(close_prices, current_price)
#
#         # 盈利保护检查
#         if check_profit_protection(etf, ContextInfo):
#             log.info(f"🚫 {etf} {name} 触发盈利保护，从排名中排除")
#             return None
#
#         # 成交量过滤
#         if ContextInfo.enable_volume_check:
#             vol_ratio = get_volume_ratio(ContextInfo, etf)
#             if vol_ratio is not None:
#                 annualized = get_annualized_returns(price_series, ContextInfo.lookback_days)
#                 if annualized > ContextInfo.volume_return_limit:
#                     log.info(f"📉 {etf} {name} 放量且年化过高，过滤")
#                     return None
#
#         # 短期动量过滤
#         if len(price_series) >= ContextInfo.short_lookback_days + 1:
#             short_return = price_series[-1] / price_series[-(ContextInfo.short_lookback_days + 1)] - 1
#             short_annualized = (1 + short_return) ** (250 / ContextInfo.short_lookback_days) - 1
#         else:
#             short_annualized = 0
#
#         if ContextInfo.use_short_momentum_filter and short_annualized < ContextInfo.short_momentum_threshold:
#             log.debug(f"{etf} {name} 短期动量不足，过滤")
#             return None
#
#         # 长期动量计算
#         recent = price_series[-(ContextInfo.lookback_days + 1):]
#         y = np.log(recent)
#         x = np.arange(len(y))
#         weights = np.linspace(1, 2, len(y))
#         slope, intercept = np.polyfit(x, y, 1, w=weights)
#         annualized_returns = math.exp(slope * 250) - 1
#
#         ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
#         ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
#         r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0
#
#         score = annualized_returns * r_squared
#
#         # 近3日跌幅过滤
#         if len(price_series) >= 4:
#             day1 = price_series[-1] / price_series[-2]
#             day2 = price_series[-2] / price_series[-3]
#             day3 = price_series[-3] / price_series[-4]
#             if min(day1, day2, day3) < ContextInfo.loss:
#                 log.info(f"⚠️ {etf} {name} 近3日有单日跌幅过大，排除")
#                 return None
#
#         return {
#             'etf': etf,
#             'etf_name': name,
#             'annualized_returns': annualized_returns,
#             'r_squared': r_squared,
#             'score': score,
#             'current_price': current_price,
#             'short_annualized': short_annualized,
#         }
#
#     except Exception as e:
#         log.warning(f"计算{etf} {get_name(etf, ContextInfo)}时出错: {e}")
#         return None
#
#
# def get_annualized_returns(price_series, lookback_days):
#     """计算加权年化收益率"""
#     recent = price_series[-(lookback_days + 1):]
#     y = np.log(recent)
#     x = np.arange(len(y))
#     weights = np.linspace(1, 2, len(y))
#     slope, _ = np.polyfit(x, y, 1, w=weights)
#     return math.exp(slope * 250) - 1
#
#
# def get_volume_ratio(ContextInfo, security, lookback=None, threshold=None):
#     """计算成交量比值"""
#     lookback = lookback or ContextInfo.volume_lookback
#     threshold = threshold or ContextInfo.volume_threshold
#     try:
#         name = get_name(security, ContextInfo)
#         hist = ContextInfo.get_market_data(security, period='1d', count=lookback, field='volume')
#         if hist is None or len(hist) < lookback:
#             return None
#         avg_vol = sum(hist) / len(hist) if isinstance(hist, list) else hist.mean()
#
#         # 获取当日成交量（PTrade接口）
#         current_vol = get_today_volume(security, ContextInfo)
#         if current_vol is None:
#             return None
#
#         ratio = current_vol / avg_vol if avg_vol > 0 else 0
#         if ratio > threshold:
#             log.debug(f"{security} {name} 成交量比{ratio:.2f}")
#             return ratio
#         return None
#     except Exception as e:
#         log.warning(f"成交量计算失败 {security}: {e}")
#         return None
#
#
# # ==================== 卖出模块 ====================
# def check_positions(ContextInfo):
#     """每日开盘检查持仓状态"""
#     positions = ContextInfo.positions
#     for sec, pos in positions.items():
#         if pos.get('volume', 0) > 0:
#             log.info(f"📊 持仓：{sec} {get_name(sec, ContextInfo)} 数量{pos['volume']}")
#
#
# def etf_sell_trade(ContextInfo):
#     """卖出不符合条件的持仓"""
#     log.info("========== 卖出操作开始 ==========")
#
#     ranked = get_cached_rankings(ContextInfo)
#     target_etfs = []
#     for m in ranked[:ContextInfo.holdings_num]:
#         if m['score'] >= ContextInfo.min_score_threshold:
#             target_etfs.append(m['etf'])
#
#     defensive_available = check_defensive_etf_available(ContextInfo)
#     if not target_etfs and defensive_available:
#         target_etfs = [ContextInfo.defensive_etf]
#
#     target_set = set(target_etfs)
#     positions = ContextInfo.positions
#
#     # 卖出不在目标列表的持仓
#     for sec in list(positions.keys()):
#         if sec not in ContextInfo.etf_pool and sec != ContextInfo.defensive_etf:
#             continue
#         if sec not in target_set:
#             pos = positions[sec]
#             if pos.get('volume', 0) > 0:
#                 if smart_order_target_value(sec, 0, ContextInfo):
#                     log.info(f"📤 卖出不在目标的持仓：{sec} {get_name(sec, ContextInfo)}")
#
#     # 溢价率检查
#     if ContextInfo.enable_premium_filter:
#         for sec in list(positions.keys()):
#             if sec not in ContextInfo.etf_pool and sec != ContextInfo.defensive_etf:
#                 continue
#             pos = positions[sec]
#             if pos.get('volume', 0) > 0:
#                 premium = get_premium_rate_ptrade(sec, ContextInfo)
#                 if premium is not None and premium > ContextInfo.premium_threshold:
#                     if smart_order_target_value(sec, 0, ContextInfo):
#                         log.info(f"🚨 溢价率过高 {sec} {get_name(sec, ContextInfo)}，卖出")
#
#     log.info("========== 卖出操作完成 ==========")
#
#
# # ==================== 买入模块 ====================
# def etf_buy_trade(ContextInfo):
#     """买入符合条件的ETF"""
#     log.info("========== 买入操作开始 ==========")
#
#     ranked = get_cached_rankings(ContextInfo)
#     log.info("=== ETF排名前5 ===")
#     for i, m in enumerate(ranked[:5]):
#         log.info(f"排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f}")
#
#     target_etfs = []
#     for m in ranked:
#         if len(target_etfs) >= ContextInfo.holdings_num:
#             break
#
#         if m['score'] < ContextInfo.min_score_threshold:
#             continue
#
#         etf = m['etf']
#
#         # 盈利保护检查
#         if ContextInfo.enable_profit_protection and check_profit_protection(etf, ContextInfo):
#             log.info(f"🚫 {etf} {get_name(etf, ContextInfo)} 触发盈利保护，排除")
#             continue
#
#         # 溢价率过滤
#         if ContextInfo.enable_premium_filter:
#             premium = get_premium_rate_ptrade(etf, ContextInfo)
#             if premium is None:
#                 log.info(f"⚠️ {etf} {get_name(etf, ContextInfo)} 无法获取溢价率，跳过")
#                 continue
#             if premium > ContextInfo.premium_threshold:
#                 log.info(f"🚫 {etf} {get_name(etf, ContextInfo)} 溢价率过高，跳过")
#                 continue
#
#         target_etfs.append(etf)
#         log.info(f"🎯 目标ETF: {etf} {m['etf_name']}")
#
#     # 防御模式
#     if not target_etfs:
#         if check_defensive_etf_available(ContextInfo):
#             target_etfs = [ContextInfo.defensive_etf]
#             log.info(f"🛡️ 进入防御模式：{ContextInfo.defensive_etf}")
#         else:
#             log.info("💤 无目标ETF且防御不可用")
#             return
#
#     # 检查是否有需要先卖出的持仓
#     positions = ContextInfo.positions
#     current_etf_pos = [s for s in positions.keys() if s in ContextInfo.etf_pool or s == ContextInfo.defensive_etf]
#     to_sell = [s for s in current_etf_pos if s not in target_etfs and positions[s].get('volume', 0) > 0]
#     if to_sell:
#         log.info(f"尚有持仓需要卖出，等待卖出完成")
#         return
#
#     # 等权分配
#     total_val = ContextInfo.account.get('total_asset', 0)  # PTrade获取总资产
#     target_per_etf = total_val / len(target_etfs)
#
#     for etf in target_etfs:
#         current_val = 0
#         if etf in positions:
#             pos = positions[etf]
#             current_val = pos.get('market_value', 0)
#
#         if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
#             if smart_order_target_value(etf, target_per_etf, ContextInfo):
#                 action = "买入" if current_val < target_per_etf else "调仓"
#                 log.info(f"📦 {action}：{etf} {get_name(etf, ContextInfo)}")
#
#     log.info("========== 买入操作完成 ==========")
#
#
# # ==================== 辅助函数 ====================
# def get_name(security, ContextInfo):
#     """获取证券名称（PTrade）"""
#     try:
#         # PTrade获取股票名称的接口
#         return ContextInfo.get_stock_name(security)
#     except:
#         return "未知"
#
#
# def get_current_price(security, ContextInfo):
#     """获取当前价格（PTrade）"""
#     try:
#         quote = ContextInfo.get_full_quote([security])
#         if quote and security in quote:
#             return quote[security].get('lastPrice', 0)
#     except:
#         pass
#     return None
#
#
# def is_paused(security, ContextInfo):
#     """判断是否停牌（PTrade）"""
#     try:
#         quote = ContextInfo.get_full_quote([security])
#         if quote and security in quote:
#             return quote[security].get('paused', False)
#     except:
#         pass
#     return False
#
#
# def check_defensive_etf_available(ContextInfo):
#     """检查防御ETF是否可交易"""
#     etf = ContextInfo.defensive_etf
#     if is_paused(etf, ContextInfo):
#         return False
#     price = get_current_price(etf, ContextInfo)
#     if not price:
#         return False
#     return True
#
#
# def smart_order_target_value(security, target_value, ContextInfo):
#     """
#     智能下单（PTrade版）
#     """
#     price = get_current_price(security, ContextInfo)
#     if not price or price == 0:
#         log.info(f"{security} {get_name(security, ContextInfo)} 价格无效，跳过")
#         return False
#
#     if is_paused(security, ContextInfo):
#         log.info(f"{security} {get_name(security, ContextInfo)} 停牌，跳过")
#         return False
#
#     target_amount = int(target_value / price)
#     target_amount = (target_amount // 100) * 100
#     if target_amount <= 0 and target_value > 0:
#         target_amount = 100
#
#     positions = ContextInfo.positions
#     cur_pos = positions.get(security, {})
#     cur_amount = cur_pos.get('volume', 0)
#     diff = target_amount - cur_amount
#
#     # 最小交易金额检查
#     trade_val = abs(diff) * price
#     if 0 < trade_val < ContextInfo.min_money:
#         log.info(f"{security} {get_name(security, ContextInfo)} 交易金额过小，跳过")
#         return False
#
#     # T+1处理
#     if diff < 0:
#         closeable = cur_pos.get('closeable_volume', 0)
#         if closeable == 0:
#             log.info(f"{security} {get_name(security, ContextInfo)} 当天买入不可卖出")
#             return False
#         diff = -min(abs(diff), closeable)
#
#     if diff != 0:
#         # PTrade下单接口
#         if diff > 0:
#             order_result = ContextInfo.buy(security, price, abs(diff))
#         else:
#             order_result = ContextInfo.sell(security, price, abs(diff))
#
#         if order_result:
#             log.info(f"{'📥 买入' if diff>0 else '📤 卖出'} {security} {get_name(security, ContextInfo)} 数量{abs(diff)}")
#             return True
#         else:
#             log.warning(f"下单失败: {security}")
#             return False
#     return False
#
#
# def get_today_volume(security, ContextInfo):
#     """获取当日成交量（PTrade）"""
#     try:
#         quote = ContextInfo.get_full_quote([security])
#         if quote and security in quote:
#             return quote[security].get('volume', 0)
#     except:
#         pass
#     return None
#
#
# def get_premium_rate_ptrade(security, ContextInfo):
#     """
#     获取溢价率（PTrade版）
#     注意：PTrade可能需要通过其他方式获取基金净值
#     """
#     try:
#         price = get_current_price(security, ContextInfo)
#         if not price:
#             return None
#
#         # PTrade获取净值的接口（如果支持）
#         # net_value = ContextInfo.get_fund_net_value(security)
#         # 这里需要根据PTrade实际接口调整
#         net_value = None  # 暂时返回None，跳过溢价率过滤
#
#         if not net_value:
#             return None
#
#         premium_rate = (price - net_value) / net_value
#         return premium_rate
#     except:
#         return None

