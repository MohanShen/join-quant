# Clone from JoinQuant
# postId: 6be8cff8592b665ff8edb9c966c9788b
# backtestId: 441014b44f50f497ce39f057d1f2d2f3
# title: 这个策略今年很强，点赞回复必回赞、克隆，没积分，模拟盘快到期

# 克隆自聚宽文章：https://www.joinquant.com/post/69033
# 标题：【五福闹新春】v2.3-7只ETF11年210倍-回应
# 作者：烟花三月ETF

import numpy as np
import math
import pandas as pd
from jqdata import *
from datetime import datetime, date


# ==================== 策略初始化 ====================
def initialize(context):
    """初始化策略（设置参数、全局变量、定时任务）"""
    set_option("avoid_future_data", True)       # 避免未来函数
    set_option("use_real_price", True)          # 使用真实价格
    
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")  # 设置滑点
    
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002,
                              close_commission=0.0002, close_today_commission=0.0002,
                              min_commission=5), type="fund")  # 设置交易费用

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    log.info("【五福闹新春】v2.3启动！")

    set_benchmark("510300.XSHG")                # 设置基准

    # ==================== 固定ETF池 ====================
    g.etf_pool = [
        '510300.XSHG',  # 沪深300ETF
        '159915.XSHE',  # 创业板ETF
        '510500.XSHG',  # 中证500ETF
        '513100.XSHG',  # 纳指ETF
        '518880.XSHG',  # 黄金ETF
        '561580.XSHG',  # 央企红利ETF
        '159985.XSHE',   # 豆粕ETF
        '588000.XSHG',  # 科创50ETF 
        "501018.XSHG",   # 南方原油
        "161226.XSHE",   # 白银LOF
        "511220.XSHG",   # 城投债ETF
        "513180.XSHG",   # 恒生科技ETF
        "510050.XSHG",   # 上证50ETF
        "513310.XSHG",   # 中韩芯片ETF
    ]

    g.ranked_etfs_result = []            # 动量计算结果的ETF列表
    g.positions = {}                     # 记录目标持仓  
    
    # ==================== 策略核心参数 ====================
    g.holdings_num = 1                  # 持仓数量
    g.defensive_etf = "511880.XSHG"     # 防御型ETF（市场低迷时持有）
    g.safe_haven_etf = '511660.XSHG'    # 冷却期避险ETF
    g.min_money = 10                    # 最小交易金额（元）

    # 动量计算参数
    g.lookback_days = 25                # 动量计算回看天数
    g.min_score_threshold = 0           # 动量得分下限
    g.max_score_threshold = 600         # 动量得分上限
    g.score_threshold_ratio = 1         # 减少调仓控制得分比例

    # 过滤开关及参数
    g.use_short_momentum_filter = True  # 短期动量过滤开关
    g.short_lookback_days = 10          # 短期动量回看天数
    g.short_momentum_threshold = 0.0    # 短期动量阈值

    g.enable_r2_filter = True           # R²过滤开关
    g.r2_threshold = 0.4                # R²阈值

    g.enable_annualized_return_filter = True  # 年化收益过滤开关
    g.min_annualized_return = 1.0       # 年化收益阈值

    g.enable_ma_filter = True          # 均线过滤开关
    g.ma_filter_days = 20               # 均线周期

    g.enable_volume_check = True        # 成交量过滤开关
    g.volume_lookback = 5               # 成交量回看天数
    g.volume_threshold = 2              # 成交量比阈值

    g.enable_loss_filter = True         # 短期风控过滤开关
    g.loss = 0.97                       # 单日最大允许跌幅（3%）

    g.use_rsi_filter = True           # RSI过滤开关
    g.rsi_period = 6                    # RSI周期
    g.rsi_lookback_days = 1             # RSI回看天数
    g.rsi_threshold = 98                # RSI超买阈值

    # 止损参数
    g.use_fixed_stop_loss = True        # 固定比例止损开关
    g.fixedStopLossThreshold = 0.95     # 固定止损比例（5%）
    g.use_pct_stop_loss = False         # 当日跌幅止损开关
    g.pct_stop_loss_threshold = 0.95    # 当日跌幅止损比例

    # 冷却期参数
    g.sell_cooldown_enabled = False     # 卖出冷却期开关
    g.sell_cooldown_days = 3            # 冷却期天数
    g.cooldown_end_date = None          # 冷却期结束日期
    
    # ==================== 记录持仓ETF得分的全局变量 ====================
    g.current_holding_etf = None        # 当前持仓的ETF代码
    g.current_holding_score = 0.0       # 当前持仓ETF的得分
    
    # ==================== 定时任务 ====================
    run_daily(check_positions, time='09:04')                  # 每天9:04盘前检查持仓
    run_daily(calculate_and_log_ranked_etfs, time='13:09:59') # 计算动量得分
    run_daily(execute_sell_trades, time='13:10:00')           # 执行卖出
    run_daily(execute_buy_trades, time='13:11:00')            # 执行买入
    run_daily(record_holding_etf_score, time='13:12:00')      # 每天13:12记录持仓ETF得分
    run_daily(record_pool_avg_score, time='13:12:05')         # 每天13:12记录7只ETF得分均值

    # 分钟级止损任务（每1分钟检查一次）
    for hour in range(9, 15):
        for minute in range(0, 60):
            current_time = "%02d:%02d" % (hour, minute)
            if ('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57'):
                run_daily(minute_level_stop_loss, time=current_time)      # 固定比例止损
                run_daily(minute_level_pct_stop_loss, time=current_time)  # 当日跌幅止损
    
    # 日志输出
    log.info(f"""策略参数初始化完成:
=== 过滤条件 ===
- 固定ETF池: {len(g.etf_pool)} 只
- 动量得分过滤: {'启用' if (g.min_score_threshold > -1e9 or g.max_score_threshold < 1e9) else '禁用'} (阈值范围: [{g.min_score_threshold}, {g.max_score_threshold}])
- 短期动量过滤: {'启用' if g.use_short_momentum_filter else '禁用'} (周期: {g.short_lookback_days}天, 阈值 ≥ {g.short_momentum_threshold:.2f})
- R²过滤: {'启用' if g.enable_r2_filter else '禁用'} (阈值 > {g.r2_threshold:.1f})
- 年化收益率过滤: {'启用' if g.enable_annualized_return_filter else '禁用'} (阈值 ≥ {g.min_annualized_return:.0%})
- 均线过滤: {'启用' if g.enable_ma_filter else '禁用'} ({g.ma_filter_days}日均线)
- 成交量过滤: {'启用' if g.enable_volume_check else '禁用'} (近{g.volume_lookback}日均量比 < {g.volume_threshold:.1f})
- 短期风控过滤: {'启用' if g.enable_loss_filter else '禁用'} (近3日单日跌幅 < {1 - g.loss:.0%})
- RSI过滤: {'启用' if g.use_rsi_filter else '禁用'} (周期: {g.rsi_period}, 回看{g.rsi_lookback_days}日, 触发阈值 > {g.rsi_threshold})
- 减少调仓控制得分比例: {g.score_threshold_ratio}（第{g.holdings_num}名得分 × 此比例）

=== 止损机制 ===
- 分钟级固定比例止损: {'启用' if g.use_fixed_stop_loss else '禁用'} (持仓成本价 × {g.fixedStopLossThreshold:.2%})
- 分钟级当日跌幅止损: {'启用' if g.use_pct_stop_loss else '禁用'} (昨日收盘价 × {g.pct_stop_loss_threshold:.2%})

=== 其他配置 ===
- 持仓数量: {g.holdings_num}只
- 防御ETF: {g.defensive_etf}
- 冷却期避险ETF: {g.safe_haven_etf}
- 冷却期: {'启用' if g.sell_cooldown_enabled else '禁用'}
""")


# ==================== 记录ETF池得分均值 ====================
def record_pool_avg_score(context):
    """
    每天13:12记录7只ETF的动量得分的均值
    副图显示：ETF池得分均值（保留2位小数）
    """
    log.info("========== 记录ETF池得分均值 ==========")
    
    scores = []
    
    for etf in g.etf_pool:
        try:
            # 获取过去 g.lookback_days 天的收盘价历史数据
            prices = attribute_history(etf, g.lookback_days + 5, '1d', ['close'])
            
            if prices.empty or len(prices) < g.lookback_days:
                log.warning(f"{etf} 数据不足，无法计算得分")
                continue
            
            # 使用与主策略相同的计算方法
            price_series = prices['close'].values
            recent_prices = price_series[-g.lookback_days:]
            
            # 加权线性回归
            y = np.log(recent_prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            annualized_returns = math.exp(slope * 250) - 1
            
            # 计算R²
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            r_squared = 1 - ss_res / ss_tot if ss_tot else 0
            
            # 动量得分
            score = annualized_returns * r_squared
            scores.append(score)
            
            etf_name = get_security_name(etf)
            log.info(f"{etf_name}({etf}) 得分: {score:.4f}")
            
        except Exception as e:
            log.warning(f"计算 {etf} 得分时出错: {e}")
            continue
    
    # 计算均值
    if scores:
        avg_score = np.mean(scores)
        display_avg = round(avg_score, 2)
        log.info(f"7只ETF得分列表: {[round(s, 4) for s in scores]}")
        log.info(f"得分均值: {avg_score:.4f} -> 记录值: {display_avg:.2f}")
        record(ETF池得分均值=display_avg)
    else:
        log.warning("无法计算任何ETF得分，记录0.00")
        record(ETF池得分均值=0.00)
    
    log.info("========== 记录完成 ==========")


# ==================== 记录持仓ETF得分 ====================
def record_holding_etf_score(context):
    """
    每天13:12记录当前持仓ETF的动量得分
    副图显示：当前持仓ETF的得分（保留2位小数）
    """
    log.info("========== 记录持仓ETF动量得分 ==========")
    
    # 获取当前持仓（排除现金和避险资产）
    current_holding = None
    for security, position in context.portfolio.positions.items():
        if position.total_amount > 0:
            # 只记录策略相关的ETF（排除避险ETF）
            if security in g.etf_pool or security == g.defensive_etf:
                current_holding = security
                break  # 只取第一只持仓（因为通常只持仓1只）
    
    # 如果没有持仓，记录0
    if not current_holding:
        log.info("当前无持仓，记录得分: 0.00")
        record(持仓ETF得分=0.00)
        g.current_holding_etf = None
        g.current_holding_score = 0.0
        log.info("========== 记录完成 ==========")
        return
    
    # 计算该ETF的动量得分
    try:
        # 获取过去 g.lookback_days 天的收盘价历史数据
        prices = attribute_history(current_holding, g.lookback_days + 5, '1d', ['close'])
        
        if prices.empty or len(prices) < g.lookback_days:
            log.warning(f"{current_holding} 数据不足，无法计算得分")
            record(持仓ETF得分=0.00)
            log.info("========== 记录完成 ==========")
            return
        
        # 使用与主策略相同的计算方法
        price_series = prices['close'].values
        recent_prices = price_series[-g.lookback_days:]
        
        # 加权线性回归
        y = np.log(recent_prices)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        
        # 计算R²
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0
        
        # 动量得分
        score = annualized_returns * r_squared
        
        # 保留2位小数
        display_score = round(score, 2)
        
        # 记录到副图
        record(持仓ETF得分=display_score)
        
        # 更新全局变量
        g.current_holding_etf = current_holding
        g.current_holding_score = display_score
        
        etf_name = get_security_name(current_holding)
        log.info(f"当前持仓: {etf_name}({current_holding})")
        log.info(f"动量得分: {score:.4f} -> 记录值: {display_score:.2f}")
        
    except Exception as e:
        log.warning(f"计算 {current_holding} 得分时出错: {e}")
        record(持仓ETF得分=0.00)
    
    log.info("========== 记录完成 ==========")


# ==================== 过滤条件应用 ====================
def apply_filters(metrics_list):
    """根据开关应用所有过滤条件"""
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], True),
        ('短期动量', lambda m: m['passed_short_mom'], g.use_short_momentum_filter),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter),
        ('年化收益率', lambda m: m['passed_annual_ret'], g.enable_annualized_return_filter),
        ('均线', lambda m: m['passed_ma'], g.enable_ma_filter),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
        ('RSI', lambda m: m['passed_rsi'], g.use_rsi_filter),
    ]
    filtered = metrics_list[:]
    for _, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered


# ==================== 持仓检查 ====================
def check_positions(context):
    """盘前持仓检查"""
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 持仓检查: {security} {security_name}, 数量: {position.total_amount}, "
                     f"成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")


# ==================== 动量得分计算 ====================
def calculate_and_log_ranked_etfs(context):
    """计算固定池中的标的动量得分"""
    if not g.etf_pool:
        log.warning("【动量计算】固定池为空，无法计算")
        g.ranked_etfs_result = []
        return
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list


def calculate_all_metrics_for_etf(context, etf):
    """计算单个ETF的所有动量指标"""
    try:
        etf_name = get_security_name(etf)

        lookback = max(
            g.lookback_days,
            g.short_lookback_days,
            g.rsi_period + g.rsi_lookback_days,
            g.ma_filter_days,
            g.volume_lookback
        ) + 20

        prices = attribute_history(etf, lookback, '1d', ['close', 'high', 'low'])
        current_data = get_current_data()

        if len(prices) < max(g.lookback_days, g.ma_filter_days):
            return None

        current_price = current_data[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        # 计算动量得分（加权线性回归）
        recent_price_series = price_series[-(g.lookback_days + 1):]
        y = np.log(recent_price_series)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0
        momentum_score = annualized_returns * r_squared

        # 短期动量
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = -np.inf

        # 均线
        ma_price = np.mean(price_series[-g.ma_filter_days:])
        current_above_ma = current_price >= ma_price

        # 成交量比
        volume_ratio = get_volume_ratio(context, etf, show_detail_log=False)

        # 短期风控（近3日单日跌幅）
        day_ratios = []
        passed_loss_filter = True
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False

        # RSI指标
        current_rsi = 0
        max_recent_rsi = 0
        passed_rsi_filter = True
        if g.use_rsi_filter and len(price_series) >= g.rsi_period + g.rsi_lookback_days:
            rsi_values = calculate_rsi(price_series, g.rsi_period)
            if len(rsi_values) >= g.rsi_lookback_days:
                recent_rsi = rsi_values[-g.rsi_lookback_days:]
                max_recent_rsi = np.max(recent_rsi)
                current_rsi = recent_rsi[-1]
                if np.any(recent_rsi > g.rsi_threshold):
                    ma5 = np.mean(price_series[-5:]) if len(price_series) >= 5 else current_price
                    if current_price < ma5:
                        passed_rsi_filter = False

        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'short_annualized': short_annualized,
            'current_price': current_price,
            'ma_price': ma_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'current_rsi': current_rsi,
            'max_recent_rsi': max_recent_rsi,
            'passed_momentum': g.min_score_threshold <= momentum_score <= g.max_score_threshold,
            'passed_short_mom': short_annualized >= g.short_momentum_threshold,
            'passed_r2': r_squared > g.r2_threshold,
            'passed_annual_ret': annualized_returns >= g.min_annualized_return,
            'passed_ma': current_above_ma,
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter,
            'passed_rsi': passed_rsi_filter,
        }
    except Exception as e:
        log.warning(f"计算 {etf} 指标出错: {e}")
        return None


def get_volume_ratio(context, security, lookback_days=None, threshold=None, show_detail_log=True):
    """计算成交量比（当前量/过去N日均量）"""
    if lookback_days is None:
        lookback_days = g.volume_lookback
    try:
        hist_data = attribute_history(security, lookback_days, '1d', ['volume'])
        if hist_data.empty or len(hist_data) < lookback_days:
            return None
        past_n_days_vol = hist_data['volume']
        if past_n_days_vol.isnull().any() or past_n_days_vol.eq(0).any():
            return None
        avg_volume = past_n_days_vol.mean()
        if avg_volume == 0:
            return None
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt, frequency='1m',
                           fields=['volume'], skip_paused=False, fq='pre', panel=False, fill_paused=False)
        if df_vol is None or df_vol.empty:
            return None
        current_volume = df_vol['volume'].sum()
        return current_volume / avg_volume if avg_volume > 0 else 0
    except Exception:
        return None


def calculate_rsi(prices, period=6):
    """计算RSI指标"""
    if len(prices) < period + 1:
        return np.array([])
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    alpha = 2.0 / (period + 1)
    avg_gains = np.zeros(len(deltas))
    avg_losses = np.zeros(len(deltas))
    avg_gains[period - 1] = np.mean(gains[:period])
    avg_losses[period - 1] = np.mean(losses[:period])
    for i in range(period, len(deltas)):
        avg_gains[i] = (gains[i] * alpha) + (avg_gains[i - 1] * (1 - alpha))
        avg_losses[i] = (losses[i] * alpha) + (avg_losses[i - 1] * (1 - alpha))
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))
    full_rsi = np.full(len(prices), np.nan)
    full_rsi[1:] = rsi
    return full_rsi[period:]


def get_final_ranked_etfs(context):
    """主筛选函数，从固定池中选出最终排名ETF（含详细日志）"""
    all_metrics = []
    etf_set = list(g.etf_pool)

    end_date = context.previous_date

    log.info(f"【动量得分计算】使用固定池，合计{len(etf_set)}只ETF")

    for etf in etf_set:
        try:
            info = get_security_info(etf)
            start_date_raw = info.start_date if info else None
        except Exception:
            start_date_raw = None

        if start_date_raw is None:
            start_date = None
        elif isinstance(start_date_raw, datetime):
            start_date = start_date_raw.date()
        elif isinstance(start_date_raw, date):
            start_date = start_date_raw
        else:
            start_date = None

        if start_date is None or end_date < start_date:
            continue

        current_data = get_current_data()
        if current_data[etf].paused:
            continue

        metrics = calculate_all_metrics_for_etf(context, etf)
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                log.warning(f"发现重复ETF数据: {metrics['etf']}，跳过。")
                continue
            all_metrics.append(metrics)

    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')

    all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)

    log_lines_step1 = ["", ">>> 第一步：所有ETF按动量得分从大到小排序 <<<"]
    for m in all_metrics:
        def fmt_status(value_str, passed):
            return f"{value_str} {'✅' if passed else '❌'}"

        original_score = m.get('momentum_score')
        if original_score == float('-inf'):
            mom_score_str = "nan"
            mom_passed = False
        else:
            mom_score_str = f"{original_score:.4f}" if not pd.isna(original_score) else "nan"
            mom_passed = m['passed_momentum']

        short_str = f"{m['short_annualized']:.4f}" if not pd.isna(m['short_annualized']) else "nan"
        short = fmt_status(f"短期动量: {short_str}", m['passed_short_mom'])
        r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
        r2 = fmt_status(f"R²: {r2_str}", m['passed_r2'])
        ann_str = f"{m['annualized_returns']:.2%}" if not pd.isna(m['annualized_returns']) else "nan%"
        ann = fmt_status(f"年化收益率: {ann_str}", m['passed_annual_ret'])
        ma_price_str = f"{m['ma_price']:.2f}" if not pd.isna(m['ma_price']) else "nan"
        ma = fmt_status(f"均线: 当前价{m['current_price']:.2f} vs 均线{ma_price_str}", m['passed_ma'])
        vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
        vol = fmt_status(f"成交量比值: {vol_val}", m['passed_volume'])
        min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
        loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
        loss = fmt_status(f"短期风控（近3日最低比值）: {loss_val}", m['passed_loss'])
        rsi_str = f"{m['current_rsi']:.1f}" if not pd.isna(m['current_rsi']) else "nan"
        max_rsi_str = f"{m['max_recent_rsi']:.1f}" if not pd.isna(m['max_recent_rsi']) else "nan"
        rsi = fmt_status(f"RSI: 当前{rsi_str} (峰值{max_rsi_str})", m['passed_rsi'])

        line = (
            f"{m['etf']} {m['etf_name']}: "
            f"{fmt_status(f'动量得分: {mom_score_str}', mom_passed)} ，"
            f"{short} ，"
            f"{r2}，"
            f"{ann}，"
            f"{ma}，"
            f"{vol}，"
            f"{loss}，"
            f"{rsi}"
        )
        log_lines_step1.append(line)

    # 第二步：应用过滤条件
    filtered_list = apply_filters(all_metrics)
    for item in filtered_list:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
    
    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    
    # 取前10名
    top_10 = filtered_list[:10]
    
    log_lines_step2 = ["", ">>> 第二步：符合全部过滤条件的ETF按动量得分从大到小排序 (前10名) <<<"]
    
    if top_10:
        for i, m in enumerate(top_10):
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"

            original_score = m.get('momentum_score')
            if original_score == float('-inf'):
                mom_score_str = "nan"
                mom_passed = False
            else:
                mom_score_str = f"{original_score:.4f}" if not pd.isna(original_score) else "nan"
                mom_passed = m['passed_momentum']

            short_str = f"{m['short_annualized']:.4f}" if not pd.isna(m['short_annualized']) else "nan"
            short = fmt_status(f"短期动量: {short_str}", m['passed_short_mom'])
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            r2 = fmt_status(f"R²: {r2_str}", m['passed_r2'])
            ann_str = f"{m['annualized_returns']:.2%}" if not pd.isna(m['annualized_returns']) else "nan%"
            ann = fmt_status(f"年化收益率: {ann_str}", m['passed_annual_ret'])
            ma_price_str = f"{m['ma_price']:.2f}" if not pd.isna(m['ma_price']) else "nan"
            ma = fmt_status(f"均线: 当前价{m['current_price']:.2f} vs 均线{ma_price_str}", m['passed_ma'])
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            vol = fmt_status(f"成交量比值: {vol_val}", m['passed_volume'])
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            loss = fmt_status(f"短期风控（近3日最低比值）: {loss_val}", m['passed_loss'])
            rsi_str = f"{m['current_rsi']:.1f}" if not pd.isna(m['current_rsi']) else "nan"
            max_rsi_str = f"{m['max_recent_rsi']:.1f}" if not pd.isna(m['max_recent_rsi']) else "nan"
            rsi = fmt_status(f"RSI: 当前{rsi_str} (峰值{max_rsi_str})", m['passed_rsi'])

            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"{fmt_status(f'动量得分: {mom_score_str}', mom_passed)} ，"
                f"{short} ，"
                f"{r2}，"
                f"{ann}，"
                f"{ma}，"
                f"{vol}，"
                f"{loss}，"
                f"{rsi}"
            )
            log_lines_step2.append(line)
    else:
        log_lines_step2.append("（无符合条件的ETF）")
        full_log = "\n".join(log_lines_step1 + log_lines_step2)
        log.info(full_log)
        return []
    
    # ========== 第三步：获取参考得分阈值，构建候选池（按动量得分排序） ==========
    if len(top_10) >= g.holdings_num:
        # 取第g.holdings_num名的得分作为参考
        reference_score = top_10[g.holdings_num - 1]['momentum_score']
        # 使用配置的阈值比例 g.score_threshold_ratio
        score_threshold = reference_score * g.score_threshold_ratio
        log_lines_step3 = [f"", f">>> 第三步：选取动量得分 ≥ 第{g.holdings_num}名 ({top_10[g.holdings_num - 1]['etf_name']}) 得分 {reference_score:.4f} × {g.score_threshold_ratio} = {score_threshold:.4f} 的ETF <<<"]
        
        # 筛选得分 ≥ 阈值的ETF
        candidate_pool = [item for item in top_10 if item['momentum_score'] >= score_threshold]
    else:
        # 如果不足g.holdings_num只，则全部入选
        log_lines_step3 = [f"", f">>> 第三步：前10名不足{g.holdings_num}只，全部作为候选池 <<<"]
        candidate_pool = top_10[:]   # 复制一份，保持原有顺序

    # 候选池已按动量得分从大到小排序（top_10原本就是排序的，筛选后保持顺序）
    log_lines_step3.append(f"【候选池】共{len(candidate_pool)}只ETF（按动量得分排序）：")
    for i, item in enumerate(candidate_pool):
        log_lines_step3.append(f"  {i+1}. {item['etf_name']}({item['etf']}) 动量得分: {item['momentum_score']:.4f}")

    # ========== 第四步：结合当前持仓进行调整 ==========
    log_lines_step4 = ["", ">>> 第四步：结合当前持仓进行调整 <<<"]

    # 获取当前持仓（排除现金）
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    log_lines_step4.append(f"当前持仓ETF：{current_holdings}")

    # 建立候选池字典（便于快速查找）
    candidate_dict = {item['etf']: item for item in candidate_pool}

    # 确定保留的持仓ETF（存在于候选池中的）
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    log_lines_step4.append(f"其中存在于候选池中的持仓ETF：{[item['etf'] for item in retained]}")

    # 根据保留数量决定最终目标
    if len(retained) >= g.holdings_num:
        # 保留的超过目标数，从保留中按动量得分取前g.holdings_num
        retained_sorted = sorted(retained, key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
        log_lines_step4.append(f"保留的持仓ETF数量({len(retained)})超过目标持仓数({g.holdings_num})，将从保留的ETF中按动量得分取前{g.holdings_num}只作为最终目标。")
    else:
        need = g.holdings_num - len(retained)
        # 从候选池中剔除已保留的ETF
        remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
        # remaining_pool仍保持原动量得分排序
        additional = remaining_pool[:need]
        final_result = retained + additional
        log_lines_step4.append(f"保留持仓ETF {len(retained)}只，还需补充{need}只。")
        if retained:
            log_lines_step4.append("保留的ETF（按原有顺序）：")
            for item in retained:
                log_lines_step4.append(f"  {item['etf_name']}({item['etf']})")
        if additional:
            log_lines_step4.append("补充的ETF（按动量得分排序）：")
            for i, item in enumerate(additional):
                log_lines_step4.append(f"  {i+1}. {item['etf_name']}({item['etf']}) 动量得分: {item['momentum_score']:.4f}")

    log_lines_step4.append(f"【最终目标】共{len(final_result)}只ETF：")
    for i, item in enumerate(final_result):
        log_lines_step4.append(f"  {i+1}. {item['etf_name']}({item['etf']})")
    log_lines_step4.append("==================================================")

    # 合并所有日志并输出
    full_log = "\n".join(log_lines_step1 + log_lines_step2 + log_lines_step3 + log_lines_step4)
    log.info(full_log)

    return final_result


# ==================== 交易执行 ====================
def execute_sell_trades(context):
    """卖出交易逻辑"""
    log.info("========== 卖出操作开始 ==========")
    if is_in_cooldown(context):
        log.info("🔒 当前处于冷却期，跳过轮动逻辑中的卖出操作")
        log.info("========== 卖出操作完成 ==========")
        return

    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    target_etfs = []

    if ranked_etfs:
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
            log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}，得分: {metrics['momentum_score']:.4f}")
    else:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
            etf_name = get_security_name(g.defensive_etf)
            log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
        else:
            log.info("💤 无最终目标(空仓模式)")
            target_etfs = []

    g.target_etfs_list = target_etfs
    current_positions = list(context.portfolio.positions.keys())
    target_set = set(target_etfs)

    sell_count = 0
    for security in current_positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            success = smart_order_target_value(security, 0, context)
            if success:
                sell_count += 1
                log.info(f"✅ 已成功卖出: {security} {security_name}")

    log.info(f"本次共计划卖出 {sell_count} 只ETF。")
    log.info("========== 卖出操作完成 ==========")


def execute_buy_trades(context):
    """买入交易逻辑"""
    log.info("========== 买入操作开始 ==========")
    exit_safe_haven_if_cooldown_ends(context)
    if is_in_cooldown(context):
        log.info("🔒 当前处于冷却期，跳过正常买入操作")
        log.info("========== 买入操作完成 ==========")
        return

    target_etfs = g.target_etfs_list
    if not target_etfs:
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        log.info("========== 买入操作完成 ==========")
        return

    current_positions = set(context.portfolio.positions.keys())
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)

    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        log.info("========== 买入操作完成 ==========")
        return

    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    log.info(f"当前实际持仓: {actual_holding_count}只, 目标持仓: {g.holdings_num}只, 本次计划买入: {num_etfs_to_buy}只")

    available_cash = context.portfolio.available_cash
    allocated_value_per_etf = available_cash // num_etfs_to_buy
    log.info(f"账户可用现金: {available_cash:.2f}, 分配给每只ETF的资金: {allocated_value_per_etf:.2f}")

    if allocated_value_per_etf < g.min_money:
        log.info(f"单只ETF分配金额 {allocated_value_per_etf:.2f} 小于最小交易额 {g.min_money:.2f}，无法买入")
        log.info("========== 买入操作完成 ==========")
        return

    for i, etf in enumerate(etfs_to_buy):
        target_value_for_this_etf = allocated_value_per_etf
        if i == len(etfs_to_buy) - 1 and context.portfolio.available_cash >= g.min_money:
            target_value_for_this_etf = context.portfolio.available_cash

        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
        else:
            log.info(f"❌ ETF {etf} 下单失败")

    log.info("========== 买入操作完成 ==========")


def smart_order_target_value(security, target_value, context):
    """智能下单（考虑停牌、涨跌停、最小交易额等）"""
    current_data = get_current_data()
    security_name = get_security_name(security)

    if current_data[security].paused:
        log.info(f"{security} {security_name}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {security_name}: 当前涨停，跳过交易")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {security_name}: 当前跌停，跳过卖出")
        return False

    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"{security} {security_name}: 当前价格为0，跳过交易")
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
        log.info(f"{security} {security_name}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过")
        return False

    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {security_name}: 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)

    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            g.positions[security] = target_amount
            if amount_diff > 0:
                log.info(f"📦 买入 {security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}")
                # 更新当前持仓信息
                g.current_holding_etf = security
            else:
                log.info(f"📤 卖出 {security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}")
                # 如果清仓，重置持仓信息
                if target_amount == 0:
                    g.current_holding_etf = None
                    g.current_holding_score = 0.0
            return True
        else:
            log.warning(f"下单失败: {security} {security_name}，数量: {amount_diff}")
            return False
    return False


# ==================== 止损机制 ====================
def minute_level_stop_loss(context):
    """分钟级固定比例止损"""
    if not g.use_fixed_stop_loss:
        return
    if is_in_cooldown(context):
        return

    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0:
            continue
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        cost_price = position.avg_cost
        if cost_price <= 0:
            continue
        if current_price <= cost_price * g.fixedStopLossThreshold:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"🚨 [分钟级] 固定止损卖出: {security} {security_name}，亏损: {loss_percent:.2f}%")
            success = smart_order_target_value(security, 0, context)
            if success:
                log.info(f"✅ [分钟级] 止损成功: {security} {security_name}")
                enter_safe_haven_and_set_cooldown(context, trigger_reason="分钟级固定止损")


def minute_level_pct_stop_loss(context):
    """分钟级当日跌幅止损（基于昨日收盘价）"""
    if not g.use_pct_stop_loss:
        return
    if is_in_cooldown(context):
        return

    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0:
            continue
        try:
            close_series = attribute_history(security, 1, '1d', ['close'], skip_paused=False)
            if len(close_series['close']) == 0:
                continue
            yesterday_close = close_series['close'][-1]
            if yesterday_close <= 0:
                continue
        except Exception:
            continue

        current_price = current_data[security].last_price
        if current_price <= 0:
            continue

        stop_price = yesterday_close * g.pct_stop_loss_threshold
        if current_price <= stop_price:
            security_name = get_security_name(security)
            daily_loss = (current_price / yesterday_close - 1) * 100
            log.info(f"🚨 [分钟级] 当日跌幅止损卖出: {security} {security_name}，跌幅: {daily_loss:.2f}%")
            success = smart_order_target_value(security, 0, context)
            if success:
                log.info(f"✅ [分钟级] 止损成功: {security} {security_name}")
                enter_safe_haven_and_set_cooldown(context, trigger_reason="分钟级当日跌幅止损")


# ==================== 辅助函数 ====================
def get_security_name(security):
    """安全获取证券名称"""
    try:
        current_data = get_current_data()
        return current_data[security].name
    except Exception:
        return "未知名称"


def check_defensive_etf_available(context):
    """检查防御性ETF是否可交易"""
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


# ==================== 冷却期机制 ====================
def is_in_cooldown(context):
    """判断是否在冷却期内"""
    if not g.sell_cooldown_enabled or g.cooldown_end_date is None:
        return False
    return context.current_dt.date() <= g.cooldown_end_date


def set_cooldown(context):
    """设置冷却期结束日期"""
    if g.sell_cooldown_enabled:
        g.cooldown_end_date = context.current_dt.date() + pd.Timedelta(days=g.sell_cooldown_days)
        log.info(f"🔒 触发冷却期，结束日期: {g.cooldown_end_date.strftime('%Y-%m-%d')}")


def enter_safe_haven_and_set_cooldown(context, trigger_reason=""):
    """进入冷却期并买入避险ETF"""
    if not g.sell_cooldown_enabled:
        return

    # 卖出所有持仓
    for security in list(context.portfolio.positions.keys()):
        if security in g.etf_pool or security == g.defensive_etf:
            position = context.portfolio.positions[security]
            if position.total_amount > 0:
                success = smart_order_target_value(security, 0, context)
                if success:
                    log.info(f"✅ [冷却期] 卖出持仓: {security}")

    # 买入避险ETF
    total_value = context.portfolio.total_value
    if total_value > g.min_money:
        success = smart_order_target_value(g.safe_haven_etf, total_value * 0.99, context)
        if success:
            log.info(f"🛡️ [冷却期] 买入避险ETF: {g.safe_haven_etf}，金额: {total_value * 0.99:.2f}")

    set_cooldown(context)
    log.info(f"🔒 [冷却期] 已进入冷却期，由 [{trigger_reason}] 触发")


def exit_safe_haven_if_cooldown_ends(context):
    """冷却期结束时卖出避险ETF"""
    if not g.sell_cooldown_enabled or g.cooldown_end_date is None:
        return

    current_date = context.current_dt.date()
    if current_date > g.cooldown_end_date:
        log.info(f"🔓 冷却期结束，当前日期: {current_date.strftime('%Y-%m-%d')}")
        if g.safe_haven_etf in context.portfolio.positions:
            position = context.portfolio.positions[g.safe_haven_etf]
            if position.total_amount > 0:
                success = smart_order_target_value(g.safe_haven_etf, 0, context)
                if success:
                    log.info(f"✅ [冷却期结束] 卖出避险ETF: {g.safe_haven_etf}")
        g.cooldown_end_date = None
        log.info(f"🔄 策略恢复正常运行")


def trade(context):
    pass