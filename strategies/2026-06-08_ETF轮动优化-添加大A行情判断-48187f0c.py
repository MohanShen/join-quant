# Clone from JoinQuant
# postId: 48187f0ce0274ff9c7a4034c18eae975
# backtestId: 2074a2817e8271cf09983dbf24379e1a
# title: ETF轮动优化-添加大A行情判断

# 克隆自聚宽文章：https://www.joinquant.com/post/69163
# 标题：【策略优化】ETF轮动策略优化-V1.7
# 作者：旭日东升量化
# 克隆自聚宽文章：https://www.joinquant.com/post/69163
# 标题：【策略优化】ETF轮动策略优化-V1.7.2
# 作者：晨曦量化
# 策略名称：七星高照ETF轮动策略-V1.8 (最小改造版：仅增加大A行情判断)
# 策略作者：屌丝逆袭量化
# V1.7.2 修复作者：GLM5
# V1.8 改造作者：Claude

# ==================== V1.8 改动说明（仅一点） ====================
# 在 V1.7.2 (GLM5修复版) 基础上，仅新增一个功能：
#   【大A行情判断】每日 9:40 检查 4 大指数(沪深300/深证综指/创业板/中证A500)是否站上 MA10。
#   ≥3 个跌破 → 进入"走弱期"，只使用海外子池(22 只:大宗商品+海外股指+港股)。
#   ≥3 个站上 → 恢复"正常期"，使用完整池 38 只。
#   走弱期最长 20 个交易日强制退出。
# 其他全部模块(动量得分、成交量、溢价率、盈利保护、买入二次检查、日内黑名单)保持 V1.7.2 原状。

# ==================== V1.7.2 原改动说明（保留） ====================
# 1、保留官方V1.7.2对溢价率数据缺失的前向搜索修复
# 2、手动补全官方文档声称但漏掉的"买入二次检查"代码
# 3、新增"日内卖出黑名单"机制，彻底解决反弹买回的BUG
# 4、清理买入模块无效代码
# 5、策略频率改为分钟级别，买卖合并到13:10同一时间点，先卖后买

import numpy as np
import math
import datetime
import pandas as pd
from jqdata import *




# ==================== 初始化模块 ====================

def initialize(context):
    """初始化函数：设置交易参数、ETF池、核心参数、调度任务"""
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
    set_benchmark("000300.XSHG")

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    log.info("========== 策略初始化开始 ==========")

    # ---------- ETF池 ----------
    g.etf_pool_bak = [
        "518880.XSHG",   # 黄金ETF
        "159985.XSHE",   # 豆粕ETF
        "501018.XSHG",   # 南方原油
        "161226.XSHE",   # 白银LOF
        "513100.XSHG",   # 纳指ETF
        "159915.XSHE",   # 创业板ETF
        "511220.XSHG",   # 城投债ETF
    ]
    g.etf_pool = [
        # 大宗商品ETF
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色ETF
        "159985.XSHE",  # 豆粕ETF
        "501018.XSHG",  # 南方原油
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

    # ========== V1.8 新增：海外子池（走弱期使用，港股归入海外） ==========
    g.overseas_etf_pool = [
        # 大宗商品
        "518880.XSHG", "159980.XSHE", "159985.XSHE", "501018.XSHG",
        "161226.XSHE", "159981.XSHE",
        # 海外股指
        "513100.XSHG", "159509.XSHE", "513290.XSHG", "513500.XSHG",
        "159529.XSHE", "513400.XSHG", "513520.XSHG", "513030.XSHG",
        "513080.XSHG", "513310.XSHG", "513730.XSHG",
        # 港股
        "159792.XSHE", "513130.XSHG", "513050.XSHG", "159920.XSHE",
        "513690.XSHG",
    ]

    # ---------- 核心参数 ----------
    g.lookback_days = 25               # 动量计算周期
    g.holdings_num = 1                 # 候选数量
    g.defensive_etf = "511880.XSHG"    # 防御ETF（货币基金）
    g.min_money = 5000                 # 最小交易金额

    # ---------- 盈利保护参数 ----------
    g.enable_profit_protection = True
    g.profit_protection_lookback = 1
    g.profit_protection_threshold = 0.05
    g.profit_protection_check_times = ['11:00']

    g.loss = 0.97                      # 近3日单日跌幅阈值（排除）

    g.min_score_threshold = 0          # 最低得分
    g.max_score_threshold = 100.0      # 最高得分

    # ---------- 成交量过滤 ----------
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 2
    g.volume_return_limit = 1

    # ---------- 短期动量过滤 ----------
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0

    # ---------- 溢价率过滤 ----------
    g.enable_premium_filter = True
    g.premium_threshold = 0.20

    # ========== V1.8 新增：行情判断参数 ==========
    g.enable_regime_switch = True              # 行情切换总开关
    g.weak_period_ma_lookback = 10             # 10日均线
    g.weak_period_max_days = 20                # 走弱期最长持续20个交易日
    g.regime_indexes = {
        '大盘':    '000300.XSHG',
        '小盘':    '399101.XSHE',
        '创业板':  '399006.XSHE',
        '中证A500':'000510.XSHG',
    }
    g.is_a_share_weak = False                  # 当前是否走弱期（运行时变量）
    g.weak_period_counter = 0                  # 走弱期天数计数器

    # ---------- 运行时变量 ----------
    g.rankings_cache = {'date': None, 'data': None}
    g.profit_protection_sold_today = []

    # ---------- 交易调度 ----------
    # 注意：分钟级别下同一时间点的 run_daily 按注册顺序执行
    # 13:10 先注册卖出再注册买入，保证先卖后买
    run_daily(check_positions, time='09:10')
    run_daily(regime_check, time='09:40')          # V1.8 新增：9:40 行情判断
    run_daily(etf_sell_trade, time='13:10')
    run_daily(etf_buy_trade, time='13:10')

    # 动态注册盈利保护检查时间点
    for check_time in g.profit_protection_check_times:
        run_daily(profit_protection_check, time=check_time)
        log.info(f"已注册盈利保护检查时间：{check_time}")

    log.info(f"策略初始化完成：ETF池{len(g.etf_pool)}只，海外子池{len(g.overseas_etf_pool)}只")
    log.info(f"动量周期{g.lookback_days}天，持仓{g.holdings_num}只")
    log.info(f"盈利保护：{'开启' if g.enable_profit_protection else '关闭'}，回看{g.profit_protection_lookback}天，回撤阈值{g.profit_protection_threshold*100:.0f}%")
    log.info(f"行情切换：{'开启' if g.enable_regime_switch else '关闭'}，MA{g.weak_period_ma_lookback}，走弱期最长{g.weak_period_max_days}日")
    if g.enable_premium_filter:
        log.info(f"溢价率过滤已启用，阈值：{g.premium_threshold*100:.0f}%")
    else:
        log.info("溢价率过滤未启用")
    log.info("========== 策略初始化完成 ==========")


# ==================== V1.8 新增：行情判断模块 ====================

def regime_check(context):
    """每日 9:40 判断大A行情，决定使用完整池还是海外子池。
    进入条件：≥3 个指数跌破 MA10 → 走弱期
    退出条件：≥3 个指数站上 MA10 → 正常期，或走弱期满 20 日强制退出
    """
    if not g.enable_regime_switch:
        g.is_a_share_weak = False
        return

    below_count = 0
    above_count = 0
    detail = []
    for name, code in g.regime_indexes.items():
        try:
            df = attribute_history(code, g.weak_period_ma_lookback + 1, '1d',
                                   ['close'], skip_paused=False)
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
            log.warning(f"行情指数{name}({code})获取失败: {e}")

    old_state = g.is_a_share_weak
    if not g.is_a_share_weak:
        # 当前是正常期，看是否进入走弱期
        if below_count >= 3:
            g.is_a_share_weak = True
            g.weak_period_counter = 0
            log.info(f"🔴 进入【大A走弱期】：跌破MA10指数数={below_count} {detail}")
            log.info(f"   → 切换至海外子池({len(g.overseas_etf_pool)}只)")
    else:
        # 当前是走弱期，看是否退出
        g.weak_period_counter += 1
        if above_count >= 3:
            g.is_a_share_weak = False
            g.weak_period_counter = 0
            log.info(f"🟢 恢复【正常期】：站上MA10指数数={above_count} {detail}")
            log.info(f"   → 切换至完整池({len(g.etf_pool)}只)")
        elif g.weak_period_counter >= g.weak_period_max_days:
            g.is_a_share_weak = False
            g.weak_period_counter = 0
            log.info(f"⏰ 走弱期满{g.weak_period_max_days}日，强制退出，恢复正常期")

    # 行情切换时清空排名缓存，强制重新计算
    if old_state != g.is_a_share_weak:
        g.rankings_cache = {'date': None, 'data': None}


# ==================== 盈利保护独立检查函数 ====================

def profit_protection_check(context):
    if not g.enable_profit_protection:
        log.debug("盈利保护模块已关闭，跳过检查")
        return

    log.info("========== 盈利保护独立检查开始 ==========")
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if check_profit_protection(sec, context):
                if smart_order_target_value(sec, 0, context):
                    log.info(f"🛡️ 盈利保护卖出（独立检查）：{sec} {get_name(sec)}")
                    if sec not in g.profit_protection_sold_today:
                        g.profit_protection_sold_today.append(sec)
    log.info("========== 盈利保护独立检查完成 ==========")


# ==================== 盈利保护检查函数（核心逻辑） ====================

def check_profit_protection(security, context, lookback=None, threshold=None):
    if not g.enable_profit_protection:
        return False

    lookback = lookback or g.profit_protection_lookback
    threshold = threshold or g.profit_protection_threshold

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

    net_value = None
    used_date = date
    start_date = date - datetime.timedelta(days=max_back_days*2)
    trade_days = get_trade_days(start_date=start_date, end_date=date)
    trade_days = [pd.to_datetime(d).date() for d in trade_days]
    for dt in reversed(trade_days):
        if dt > date:
            continue
        net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            used_date = dt
            break
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
    today = context.current_dt.date()
    if g.rankings_cache['date'] != today:
        log.info("重新计算ETF排名...")
        ranked = get_ranked_etfs(context)
        g.rankings_cache = {'date': today, 'data': ranked}
    else:
        log.debug("使用缓存的ETF排名")
    return g.rankings_cache['data']


def get_ranked_etfs(context):
    """V1.8 改动：根据行情判断切换候选池"""
    # ========== V1.8 新增：走弱期切换至海外子池 ==========
    if g.is_a_share_weak:
        active_pool = g.overseas_etf_pool
        log.info(f"📊 当前【走弱期】，使用海外子池({len(active_pool)}只)")
    else:
        active_pool = g.etf_pool
        log.info(f"📊 当前【正常期】，使用完整池({len(active_pool)}只)")

    etf_metrics = []
    for etf in active_pool:
        if get_current_data()[etf].paused:
            log.debug(f"{etf} {get_name(etf)} 停牌，��过")
            continue

        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            if g.min_score_threshold < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)
            else:
                log.debug(f"{etf} {metrics['etf_name']} 得分{metrics['score']:.2f}超出阈值，过滤")

    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def calculate_momentum_metrics(context, etf):
    try:
        name = get_name(etf)
        lookback = max(g.lookback_days, g.short_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < g.lookback_days:
            log.debug(f"{etf} {name} 历史数据不足{len(prices)}天，跳过")
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
                log.debug(f"{etf} {name} 无法获取溢价率，跳过溢价率过滤")

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
            log.debug(f"{etf} {name} 短期动量不足，过滤")
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
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def get_volume_ratio(context, security, lookback=None, threshold=None):
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
            log.debug(f"{security} {name} 成交量比{ratio:.2f} > {threshold}")
            return ratio
        return None
    except Exception as e:
        log.warning(f"成交量计算失败 {security}: {e}")
        return None


# ==================== 工具函数 ====================

def get_name(security):
    try:
        return get_current_data()[security].name
    except:
        return "未知"


def smart_order_target_value(security, target_value, context):
    data = get_current_data()
    name = get_name(security)

    if data[security].paused:
        log.info(f"{security} {name} 停牌，跳过")
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
            log.info(f"{security} {name} 涨停，跳过买入")
            return False
    elif diff < 0:
        if data[security].last_price <= data[security].low_limit:
            log.info(f"{security} {name} 跌停，跳过卖出")
            return False

    trade_val = abs(diff) * price
    if 0 < trade_val < g.min_money:
        log.info(f"{security} {name} 交易金额太小，跳过")
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
            return True
        else:
            log.warning(f"下单失败: {security} {name}")
            return False
    return False


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


# ==================== 卖出 / 持仓检查模块 ====================

def check_positions(context):
    g.profit_protection_sold_today = []

    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")


def etf_sell_trade(context):
    log.info("========== 卖出操作开始 ==========")

    ranked = get_cached_rankings(context)
    target_etfs = []
    for m in ranked[:g.holdings_num]:
        if m['score'] >= g.min_score_threshold:
            target_etfs.append(m['etf'])

    defensive_available = check_defensive_etf_available(context)
    if not target_etfs and defensive_available:
        target_etfs = [g.defensive_etf]

    target_set = set(target_etfs)

    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        if sec not in target_set:
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                if smart_order_target_value(sec, 0, context):
                    log.info(f"📤 卖出不在目标的持仓：{sec} {get_name(sec)}")

    log.info("========== 卖出操作完成 ==========")


# ==================== 买入模块（含买入二次检查、日内卖出黑名单） ====================

def etf_buy_trade(context):
    log.info("========== 买入操作开始 ==========")

    ranked = get_cached_rankings(context)
    log.info("=== ETF排名前5 ===")
    for i, m in enumerate(ranked[:5]):
        log.info(f"排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f}")

    target_etfs = []

    for m in ranked:
        if len(target_etfs) >= g.holdings_num:
            break
        etf = m['etf']

        # 买入二次检查1：盈利保护
        if check_profit_protection(etf, context):
            log.debug(f"⚠️ {etf} {m['etf_name']} 二次检查触发盈利保护，跳过")
            continue

        # 买入二次检查2：日内卖出黑名单
        if etf in g.profit_protection_sold_today:
            log.info(f"🚫 {etf} {m['etf_name']} 今日已触发盈利保护卖出，禁止买回")
            continue

        target_etfs.append(etf)
        log.info(f"🎯 目标ETF {len(target_etfs)}: {etf} {m['etf_name']} 得分{m['score']:.4f}")

    # 防御模式
    if not target_etfs:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
            log.info(f"🛡️ 进入防御模式：{g.defensive_etf} {get_name(g.defensive_etf)}")
        else:
            log.info("💤 无目标ETF且防御不可用，保持空仓")
            return

    # 检查是否有持仓需要先卖出
    current_etf_pos = [s for s in context.portfolio.positions if s in g.etf_pool or s == g.defensive_etf]
    to_sell = [s for s in current_etf_pos if s not in target_etfs]
    if to_sell:
        log.info(f"尚有持仓需要卖出：{[get_name(s) for s in to_sell]}，等待卖出完成")
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

    log.info("========== 买入操作完成 ==========")
