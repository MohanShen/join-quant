# Clone from JoinQuant
# postId: a533fba3a36d8a258527738842ad59dd
# backtestId: 01396a0298541d09472d4da4f2bdceeb
# title: ETF动量策略对比（目前看ETF才是王道）


# 添加必要的导入
import numpy as np
import math
import pandas as pd

# 初始化函数，设置策略参数
def initialize(context):
    # ==================== 实盘交易设置（参考策略1）====================
    set_option("avoid_future_data", True)  # 打开防未来函数
    set_option("use_real_price", True)     # 开启动态复权模式(真实价格)
    
    # 设置滑点
    set_slippage(FixedSlippage(0.0001), type="fund")
    set_slippage(FixedSlippage(0.003), type="stock")
    
    # 设置交易成本（ETF交易成本较低）
    set_order_cost(
        OrderCost(
            open_tax=0,               # 买入印花税
            close_tax=0,          # 卖出印花税:近股票收取
            open_commission=0.0002,   # 买入佣金
            close_commission=0.0002,  # 卖出佣金
            close_today_commission=0, # 今平佣金
            min_commission=5,         # 最低佣金
        ),
        type="fund",
    )
    
    # 设置货币ETF交易佣金为0
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0,
            close_commission=0,
            close_today_commission=0,
            min_commission=0,
        ),
        type="mmf",
    )
    
    # 设置日志级别
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    
    log.info("策略2优化版初始化完成 - 包含完整实盘交易设置和短期动量过滤")
    #设置基准
    set_benchmark("513100.XSHG")  #组合中含纳斯达克，故设置纳斯达克为参考基准
    # ==================== 策略参数设置 ====================
    # 设置ETF池，包含A股、美股、商品等全球主要ETF

    # ETF轮动策略ETF池
    g.etf_pool = [
        #大宗商品ETF
        "518880.XSHG",  # 黄金ETF
        # "159980.XSHE",  # 有色ETF（跟踪有色金属板块）
        # "159985.XSHE",  # 豆粕ETF（跟踪豆粕期货价格）
        # "501018.XSHG",  # 南方原油（投资原油相关资产）
        # "159981.XSHE",  # 能源化工ETF
        # "159980.XSHE",  # 有色金属ETF
        # "511130.XSHG",  # 30年国债ETF
        #国际ETF
        "513100.XSHG",  # 纳指ETF
        "513500.XSHG",  # 标普500ETF
        "513520.XSHG",  # 日经225ETF
        "513030.XSHG",  # 德国30ETF
        "513080.XSHG",  # 法国ETF
        #香港ETF
        "159920.XSHE",  # 恒生ETF
        #中国ETF
        "510300.XSHG",  # 沪深300ETF
        "510500.XSHG",  # 上证500ETF
        "159915.XSHE",  # 创业板ETF
        "588080.XSHG",  # 科创50          
        "159845.XSHE",  # 华夏中证1000ETF
        "563300.XSHG",  # 中证2000ETF华泰
        #防御ETF
        "511880.XSHG",  # 防御性ETF（货币ETF
    ]
        
    # 策略参数
    g.lookback_days = 25  # 长期动量计算周期
    g.holdings_num = 1    # 只持有1只ETF
    g.stop_loss = 0.95    # 止损线（0.92表示下跌8%止损）
    g.loss = 0.97   #近3日跌幅止损线：用于过滤
    g.defensive_etf = "511880.XSHG"  # 防御性ETF（货币ETF）
    g.min_score_threshold = 0.0  # 最低得分阈值，低于此值进入防御模式
    g.max_score_threshold = 5.0  # 最高得分阈值，高于此值的ETF视为异常值:过度上涨，下跌风险高
    g.min_money = 5000  # 最小交易金额
    
    # ==================== 新增短期动量过滤参数 ====================
    g.use_short_momentum_filter = True  # 是否启用短期动量过滤（新增参数）
    g.short_lookback_days = 10  # 短期动量计算周期（新增参数）
    g.short_momentum_threshold = 0.0  # 短期动量阈值（新增参数）
    
    # ==================== 新增ATR动态止损参数 ====================
    g.use_atr_stop_loss = True  # 是否启用ATR动态止损（新增参数）
    g.atr_period = 14  # ATR计算周期，默认14日（新增参数）
    g.atr_multiplier = 2  # ATR倍数，默认2倍（新增参数）
    g.atr_trailing_stop = False  # 是否使用跟踪止损（新增参数）
    g.atr_exclude_defensive = True  # 防御ETF是否豁免ATR止损（新增参数）

    
    # ==================== 新增MA过滤参数 ====================
    g.use_ma_filter = False  # 是否启用MA过滤（新增参数）
    g.ma_short_period = 5   # 短期MA周期，默认5日（新增参数）
    g.ma_long_period = 25   # 长期MA周期，默认25日（新增参数）
    g.ma_filter_condition = "above"  # MA过滤条件："above"表示MA5>MA25，"below"表示MA5<MA25（新增参数）
    
    # ==================== 新增RSI过滤参数 ====================
    g.use_rsi_filter = True  # 是否启用RSI过滤（新增参数）
    g.rsi_period = 6  # RSI计算周期（默认6日）
    g.rsi_lookback_days = 1  # 检查RSI的历史天数（默认5日）
    g.rsi_threshold = 95  # RSI阈值（默认90）
    
    # ==================== 新增MACD过滤参数 ====================
    g.use_macd_filter = False  # 是否启用MACD过滤（新增参数）
    g.macd_fast_period = 12  # MACD快线周期（默认12）
    g.macd_slow_period = 26  # MACD慢线周期（默认26）
    g.macd_signal_period = 9  # MACD信号线周期（默认9）
    g.macd_filter_condition = "bullish"  # MACD过滤条件："bullish"表示看多（DIF>DEA），"bearish"表示看空（DIF<DEA）
    
    # ==================== 新增成交量异常过滤参数 ====================
    g.use_volume_filter = False  # 是否启用成交量异常过滤（新增参数）
    g.volume_lookback_days = 7  # 成交量计算周期，默认10日（新增参数）
    g.volume_threshold = 2.0  # 成交量异常倍数，默认2倍（新增参数）
    g.volume_exclude_defensive = True  # 防御ETF是否豁免成交量过滤（新增参数）
    
    # ==================== 新增布林带过滤参数 ====================
    g.use_bollinger_filter = False  # 是否启用布林带过滤（新增参数）
    g.bollinger_period = 20  # 布林带周期，默认20日（新增参数）
    g.bollinger_std = 2.0  # 布林带标准差倍数，默认2.0（新增参数）
    g.bollinger_lookback_days = 3  # 检查布林带突破的天数，默认5日（新增参数）
    

    # 持仓管理（参考策略1的持仓管理方式）
    g.positions = {}  # 记录持仓
    # 新增：记录每个持仓的最高价和ATR止损价
    g.position_highs = {}  # 记录持仓期间的最高价
    g.position_stop_prices = {}  # 记录持仓的ATR止损价

    # ==================== 交易调度 ====================
    # 每天14:50执行ETF轮动交易
    run_daily(etf_trade, time='14:29')
    # 每天开盘后检查持仓（参考策略1）
    run_daily(check_positions, time='09:30')
    # 新增：每天开盘后检查ATR动态止损
    run_daily(check_atr_stop_loss, time='09:35')

# 计算ATR（平均真实波幅）指标
def calculate_atr(security, period=14):
    """
    计算ATR（平均真实波幅）指标
    :param security: 证券代码
    :param period: ATR计算周期
    :return: 当前ATR值，ATR序列，是否计算成功
    """
    try:
        # 获取历史数据，需要period+1天的数据来计算TR
        needed_days = period + 20  # 多取一些数据
        hist_data = attribute_history(security, needed_days, '1d', 
                                     ['high', 'low', 'close'])
        
        if len(hist_data) < period + 1:
            return 0, [], False, f"数据不足{period+1}天"
        
        # 计算真实波幅（TR）
        high_prices = hist_data['high'].values
        low_prices = hist_data['low'].values
        close_prices = hist_data['close'].values
        
        # 初始化TR数组
        tr_values = np.zeros(len(high_prices))
        
        # 计算每天的TR值
        for i in range(1, len(high_prices)):
            tr1 = high_prices[i] - low_prices[i]  # 当日最高价-最低价
            tr2 = abs(high_prices[i] - close_prices[i-1])  # 当日最高价-前日收盘价
            tr3 = abs(low_prices[i] - close_prices[i-1])   # 当日最低价-前日收盘价
            tr_values[i] = max(tr1, tr2, tr3)
        
        # 计算ATR（使用简单移动平均）
        atr_values = np.zeros(len(tr_values))
        
        # 前period个ATR值为0
        for i in range(period, len(tr_values)):
            atr_values[i] = np.mean(tr_values[i-period+1:i+1])
        
        # 获取最新的ATR值
        current_atr = atr_values[-1] if len(atr_values) > 0 else 0
        
        # 返回ATR序列（只返回有效部分）
        valid_atr = atr_values[period:] if len(atr_values) > period else atr_values
        
        return current_atr, valid_atr, True, "计算成功"
    
    except Exception as e:
        log.warn(f"计算{security} ATR时出错: {e}")
        return 0, [], False, f"计算出错:{str(e)}"

# 检查并执行ATR动态止损
def check_atr_stop_loss(context):
    """
    检查并执行ATR动态止损
    """
    if not g.use_atr_stop_loss:
        return
    
    current_data = get_current_data()
    
    for security in list(context.portfolio.positions.keys()):
        # 只处理ETF池中的标的且当前有持仓
        if security not in g.etf_pool:
            continue
            
        position = context.portfolio.positions[security]
        if position.total_amount <= 0:
            continue
            
        # 防御ETF豁免检查
        if g.atr_exclude_defensive and security == g.defensive_etf:
            continue
        
        try:
            # 获取当前价格
            current_price = current_data[security].last_price
            if current_price == 0:
                continue
            
            # 获取成本价
            cost_price = position.avg_cost
            
            # 计算当前ATR值
            current_atr, atr_values, success, atr_info = calculate_atr(security, g.atr_period)
            
            if not success:
                log.info(f"⚠️ {security} {get_security_name(security)} ATR计算失败: {atr_info}")
                continue
            
            # 更新持仓期间的最高价
            if security not in g.position_highs:
                g.position_highs[security] = current_price
            else:
                g.position_highs[security] = max(g.position_highs[security], current_price)
            
            # 获取当前持仓期间的最高价
            position_high = g.position_highs[security]
            
            # 计算ATR止损价
            if g.atr_trailing_stop:
                # 跟踪止损：基于持仓期间最高价
                atr_stop_price = position_high - g.atr_multiplier * current_atr
            else:
                # 固定止损：基于成本价
                atr_stop_price = cost_price - g.atr_multiplier * current_atr
            
            # 记录止损价
            g.position_stop_prices[security] = atr_stop_price
            
            # 检查是否触发ATR止损
            if current_price <= atr_stop_price:
                # 触发ATR止损
                success = smart_order_target_value(security, 0, context)
                if success:
                    security_name = get_security_name(security)
                    loss_percent = (current_price/cost_price - 1) * 100
                    atr_stop_type = "跟踪" if g.atr_trailing_stop else "固定"
                    log.info(f"🚨 ATR动态止损({atr_stop_type})卖出: {security} {security_name}，成本: {cost_price:.3f}，现价: {current_price:.3f}，ATR: {current_atr:.3f}，止损价: {atr_stop_price:.3f}，亏损: {loss_percent:.2f}%")
                    
                    # 清除记录
                    if security in g.position_highs:
                        del g.position_highs[security]
                    if security in g.position_stop_prices:
                        del g.position_stop_prices[security]
            else:
                # 记录ATR止损状态（可选，避免日志过多）
                if context.current_dt.hour == 14 and context.current_dt.minute == 20:
                    # 仅在交易时间记录
                    security_name = get_security_name(security)
                    atr_stop_type = "跟踪" if g.atr_trailing_stop else "固定"
                    log.debug(f"ATR止损状态: {security} {security_name}，现价: {current_price:.3f}，ATR: {current_atr:.3f}，止损价: {atr_stop_price:.3f}，距离止损: {(current_price/atr_stop_price-1)*100:.2f}%")
        
        except Exception as e:
            log.warn(f"检查{security} ATR止损时出错: {e}")

# 计算布林带指标
def calculate_bollinger_bands(prices, period=20, std_dev=2.0):
    """
    计算布林带指标
    :param prices: 价格序列
    :param period: 布林带周期
    :param std_dev: 标准差倍数
    :return: 中轨、上轨、下轨
    """
    if len(prices) < period:
        return [], [], []
    
    # 初始化结果数组
    middle_band = np.zeros(len(prices))
    upper_band = np.zeros(len(prices))
    lower_band = np.zeros(len(prices))
    
    # 计算布林带
    for i in range(period - 1, len(prices)):
        # 取最近period天的数据
        window = prices[i-period+1:i+1]
        
        # 计算中轨（简单移动平均）
        middle = np.mean(window)
        
        # 计算标准差
        std = np.std(window)
        
        # 计算上轨和下轨
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        
        middle_band[i] = middle
        upper_band[i] = upper
        lower_band[i] = lower
    
    # 只返回有效数据
    return middle_band[period-1:], upper_band[period-1:], lower_band[period-1:]

# 检查布林带过滤条件
def check_bollinger_filter(etf, current_price, lookback_days=5, period=20, std_dev=2.0):
    """
    检查布林带过滤条件
    :param etf: ETF代码
    :param current_price: 当前价格
    :param lookback_days: 检查突破的天数
    :param period: 布林带周期
    :param std_dev: 标准差倍数
    :return: 是否通过布林带过滤，详细信息
    """
    try:
        # 获取历史价格数据
        # 需要获取足够的天数来计算布林带和检查突破
        needed_days = max(period, lookback_days) + 10  # 多取一些数据
        price_data = attribute_history(etf, needed_days, '1d', ['close', 'high'])
        
        if len(price_data) < period:
            return True, f"数据不足{period}天，无法计算布林带"
        
        # 获取收盘价序列
        close_prices = price_data['close'].values
        
        # 计算布林带
        middle_band, upper_band, lower_band = calculate_bollinger_bands(
            close_prices, period, std_dev
        )
        
        if len(upper_band) < lookback_days:
            return True, f"布林带数据不足{lookback_days}天"
        
        # 检查近lookback_days日内是否曾经突破上轨
        # 取最近lookback_days天的布林带上轨和对应的收盘价
        recent_upper_band = upper_band[-lookback_days:]
        recent_close_prices = close_prices[-(len(middle_band)-len(upper_band)+lookback_days):][-lookback_days:]
        
        # 检查是否有任何一天收盘价突破上轨
        breakthrough_occurred = False
        breakthrough_day = None
        breakthrough_price = 0
        breakthrough_upper = 0
        
        for i in range(len(recent_close_prices)):
            if recent_close_prices[i] > recent_upper_band[i]:
                breakthrough_occurred = True
                breakthrough_day = i
                breakthrough_price = recent_close_prices[i]
                breakthrough_upper = recent_upper_band[i]
                break
        
        # 计算MA5（使用最近5天的收盘价）
        if len(close_prices) >= 5:
            ma5 = np.mean(close_prices[-5:])
        else:
            ma5 = np.mean(close_prices)
        
        # 判断是否满足过滤条件
        # 条件：近lookback_days日价格曾经突破布林带上轨，且当前价格低于MA5
        if breakthrough_occurred and current_price < ma5:
            return False, f"近{lookback_days}日曾突破布林带上轨(第{breakthrough_day+1}日:{breakthrough_price:.3f}>{breakthrough_upper:.3f})，且当前价{current_price:.3f}<MA5({ma5:.3f})"
        else:
            if breakthrough_occurred:
                return True, f"近{lookback_days}日曾突破布林带上轨(第{breakthrough_day+1}日:{breakthrough_price:.3f}>{breakthrough_upper:.3f})，但当前价{current_price:.3f}≥MA5({ma5:.3f})，未触发过滤"
            else:
                return True, f"近{lookback_days}日未突破布林带上轨，当前价{current_price:.3f}，MA5={ma5:.3f}"
    
    except Exception as e:
        log.warn(f"检查{etf}布林带时出错: {e}")
        return True, f"检查出错:{str(e)}"

# 计算成交量异常指标
def check_volume_anomaly(etf, lookback_days=10, threshold=2.0, exclude_defensive=False, defensive_etf=""):
    """
    检查成交量是否异常
    :param etf: ETF代码
    :param lookback_days: 成交量计算周期
    :param threshold: 成交量异常倍数
    :param exclude_defensive: 防御ETF是否豁免
    :param defensive_etf: 防御ETF代码
    :return: 是否通过成交量过滤，成交量比值，近1日成交量，近N日均成交量
    """
    # 防御ETF豁免检查
    if exclude_defensive and etf == defensive_etf:
        return True, 0.0, 0, 0, "防御ETF豁免成交量检查"
    
    try:
        # 获取历史成交量数据，需要足够的天数
        volume_lookback = lookback_days + 5  # 多取几天作为缓冲
        volume_data = attribute_history(etf, volume_lookback, '1d', ['volume'])
        
        if len(volume_data) < lookback_days:
            return True, 0.0, 0, 0, f"数据不足{lookback_days}天"
        
        # 获取近1日成交量
        recent_volume = volume_data['volume'].iloc[-1]
        
        # 获取近lookback_days日成交量均值（排除最近1日）
        if len(volume_data) >= lookback_days + 1:
            # 取前lookback_days日的成交量（排除最近1日）
            avg_volume = volume_data['volume'].iloc[-(lookback_days+1):-1].mean()
        else:
            # 数据不足时，使用所有可用数据（排除最近1日）
            avg_volume = volume_data['volume'].iloc[:-1].mean()
        
        # 避免除零错误
        if avg_volume <= 0:
            return True, 0.0, recent_volume, avg_volume, f"历史均量异常:{avg_volume:.0f}"
        
        # 计算成交量比值
        volume_ratio = recent_volume / avg_volume
        
        # 检查是否超过阈值
        if volume_ratio > threshold:
            return False, volume_ratio, recent_volume, avg_volume, f"成交量异常:近1日{recent_volume:.0f} > 近{lookback_days}日均值{avg_volume:.0f}的{threshold}倍"
        else:
            return True, volume_ratio, recent_volume, avg_volume, f"成交量正常:比值{volume_ratio:.2f}"
    
    except Exception as e:
        log.warn(f"检查{etf}成交量时出错: {e}")
        return True, 0.0, 0, 0, f"检查出错:{str(e)}"

# 计算RSI指标
def calculate_rsi(prices, period=6):
    """
    计算RSI指标
    :param prices: 价格序列
    :param period: RSI计算周期
    :return: RSI值列表
    """
    if len(prices) < period + 1:
        return []
    
    # 计算价格变化
    deltas = np.diff(prices)
    
    # 分离上涨和下跌
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    # 计算平均增益和平均损失（简单移动平均）
    avg_gains = np.zeros_like(prices)
    avg_losses = np.zeros_like(prices)
    
    # 初始化第一个平均值
    avg_gains[period] = np.mean(gains[:period])
    avg_losses[period] = np.mean(losses[:period])
    
    # 计算后续的RSI值
    rsi_values = np.zeros(len(prices))
    rsi_values[:period] = 50  # 初始值设为50
    
    for i in range(period + 1, len(prices)):
        avg_gains[i] = (avg_gains[i-1] * (period - 1) + gains[i-1]) / period
        avg_losses[i] = (avg_losses[i-1] * (period - 1) + losses[i-1]) / period
        
        if avg_losses[i] == 0:
            rsi_values[i] = 100
        else:
            rs = avg_gains[i] / avg_losses[i]
            rsi_values[i] = 100 - (100 / (1 + rs))
    
    return rsi_values[period:]

# 计算MACD指标
def calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9):
    """
    计算MACD指标
    :param prices: 价格序列
    :param fast_period: 快线周期
    :param slow_period: 慢线周期
    :param signal_period: 信号线周期
    :return: MACD指标值 (DIF, DEA, MACD柱)
    """
    if len(prices) < slow_period + signal_period:
        return [], [], []
    
    # 计算EMA
    def calculate_ema(data, period):
        ema = np.zeros_like(data)
        ema[0] = data[0]
        alpha = 2 / (period + 1)
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    # 计算快线EMA和慢线EMA
    ema_fast = calculate_ema(prices, fast_period)
    ema_slow = calculate_ema(prices, slow_period)
    
    # 计算DIF（差离值）
    dif = ema_fast - ema_slow
    
    # 计算DEA（DIF的EMA）
    dea = calculate_ema(dif, signal_period)
    
    # 计算MACD柱（DIF-DEA）
    macd_bar = dif - dea
    
    # 只返回有效数据（去掉前面不够计算的部分）
    start_idx = slow_period + signal_period - 1
    return dif[start_idx:], dea[start_idx:], macd_bar[start_idx:]

# 检查持仓状态
def check_positions(context):
    """每日开盘后检查持仓状态"""
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 持仓检查: {security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")

# 计算ETF动量得分（添加短期动量和MA计算）
def calculate_momentum_metrics(etf):
    try:
        # 获取历史价格数据 - 使用attribute_history避免未来函数
        # 获取足够多的数据用于长期和短期动量计算
        lookback = max(g.lookback_days, g.short_lookback_days, g.ma_long_period, 
                      g.rsi_period + g.rsi_lookback_days, 
                      g.macd_slow_period + g.macd_signal_period,
                      g.volume_lookback_days,
                      g.bollinger_period + g.bollinger_lookback_days) + 20  # 加20天保证有足够数据
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        current_data = get_current_data()
        
        # 检查数据是否足够
        if len(prices) < lookback:
            return None
            
        # 策略1的关键：获取当前价格并添加到价格序列中
        current_price = current_data[etf].last_price
        price_series = np.append(prices["close"].values, current_price)
        
        # ========== 新增：计算MA指标 ==========
        if len(price_series) >= g.ma_long_period:
            # 计算MA5和MA25
            ma5 = np.mean(price_series[-g.ma_short_period:])
            ma25 = np.mean(price_series[-g.ma_long_period:])
            
            # 判断MA过滤条件是否满足
            if g.ma_filter_condition == "above":
                ma_condition_met = ma5 >= ma25
                condition_desc = f"MA{g.ma_short_period}>={g.ma_long_period}"
            else:
                ma_condition_met = ma5 <= ma25
                condition_desc = f"MA{g.ma_short_period}<={g.ma_long_period}"
            
            ma_ratio = ma5 / ma25 - 1  # MA相对比值
        else:
            ma5 = 0
            ma25 = 0
            ma_condition_met = True  # 数据不足时默认满足条件
            ma_ratio = 0
            condition_desc = "数据不足"
        # =====================================
        
        # ========== 新增：计算RSI指标并检查过滤条件 ==========
        rsi_filter_pass = True  # 默认通过RSI过滤
        
        if g.use_rsi_filter and len(price_series) >= g.rsi_period + g.rsi_lookback_days:
            # 计算RSI指标
            rsi_values = calculate_rsi(price_series, g.rsi_period)
            
            if len(rsi_values) >= g.rsi_lookback_days:
                # 获取最近g.rsi_lookback_days日的RSI值
                recent_rsi = rsi_values[-g.rsi_lookback_days:]
                
                # 检查是否曾经超过阈值
                rsi_ever_above_threshold = np.any(recent_rsi > g.rsi_threshold)
                
                # 检查当前价格是否在MA5之下
                #current_below_ma5 = current_price < ma5 if ma5 > 0 else False
                current_below_ma5 = True
                # 如果近N日RSI曾经大于阈值且当前价格在MA5之下，则过滤掉
                if rsi_ever_above_threshold and current_below_ma5:
                    rsi_filter_pass = False
                    
                    # 获取最大RSI值和当前RSI值
                    max_rsi = np.max(recent_rsi)
                    current_rsi = recent_rsi[-1] if len(recent_rsi) > 0 else 0
                    log.info(f"⛔ RSI过滤: {etf} {get_security_name(etf)} 近{g.rsi_lookback_days}日RSI曾达{max_rsi:.1f}>={g.rsi_threshold}，当前价{current_price:.3f}<MA5({ma5:.3f})，当前RSI={current_rsi:.1f}")
                else:
                    # 记录RSI信息但不过滤
                    max_rsi = np.max(recent_rsi) if len(recent_rsi) > 0 else 0
                    current_rsi = recent_rsi[-1] if len(recent_rsi) > 0 else 0
                    rsi_info = f"RSI(max={max_rsi:.1f}, current={current_rsi:.1f})"
            else:
                rsi_info = "RSI数据不足"
                current_rsi = 0
                max_rsi = 0
        else:
            rsi_info = "未启用RSI过滤或数据不足"
            current_rsi = 0
            max_rsi = 0
        # ===================================================
        
        # ========== 新增：计算MACD指标并检查过滤条件 ==========
        macd_filter_pass = True  # 默认通过MACD过滤
        dif_value = 0
        dea_value = 0
        macd_bar = 0
        macd_info = "未启用MACD过滤或数据不足"
        
        if g.use_macd_filter and len(price_series) >= g.macd_slow_period + g.macd_signal_period:
            # 计算MACD指标
            dif_values, dea_values, macd_bars = calculate_macd(
                price_series, 
                g.macd_fast_period, 
                g.macd_slow_period, 
                g.macd_signal_period
            )
            
            if len(dif_values) > 0:
                # 获取最新的MACD值
                dif_value = dif_values[-1] if len(dif_values) > 0 else 0
                dea_value = dea_values[-1] if len(dea_values) > 0 else 0
                macd_bar = macd_bars[-1] if len(macd_bars) > 0 else 0
                
                # 判断MACD过滤条件是否满足
                if g.macd_filter_condition == "bullish":
                    # 看多条件：DIF > DEA（金叉或保持多头）
                    macd_condition_met = dif_value > dea_value
                    condition_desc = f"DIF({dif_value:.4f})>DEA({dea_value:.4f})"
                else:
                    # 看空条件：DIF < DEA（死叉或保持空头）
                    macd_condition_met = dif_value < dea_value
                    condition_desc = f"DIF({dif_value:.4f})<DEA({dea_value:.4f})"
                
                macd_filter_pass = macd_condition_met
                macd_info = f"MACD(DIF={dif_value:.4f}, DEA={dea_value:.4f}, BAR={macd_bar:.4f})"
                
                if not macd_filter_pass:
                    log.info(f"📉 MACD过滤: {etf} {get_security_name(etf)} 不满足{condition_desc}，MACD柱={macd_bar:.4f}")
            else:
                macd_info = "MACD数据不足"
        # ===================================================
        
        # ========== 新增：检查成交量异常 ==========
        volume_filter_pass = True  # 默认通过成交量过滤
        volume_ratio = 0
        recent_volume = 0
        avg_volume = 0
        volume_info = "未启用成交量过滤"
        
        if g.use_volume_filter:
            volume_filter_pass, volume_ratio, recent_volume, avg_volume, volume_info = check_volume_anomaly(
                etf, 
                g.volume_lookback_days, 
                g.volume_threshold,
                g.volume_exclude_defensive,
                g.defensive_etf
            )
            
            if not volume_filter_pass:
                log.info(f"📊 成交量过滤: {etf} {get_security_name(etf)} {volume_info}")
        # =====================================
        
        # ========== 新增：检查布林带过滤条件 ==========
        bollinger_filter_pass = True  # 默认通过布林带过滤
        bollinger_info = "未启用布林带过滤"
        
        if g.use_bollinger_filter:
            bollinger_filter_pass, bollinger_info = check_bollinger_filter(
                etf,
                current_price,
                g.bollinger_lookback_days,
                g.bollinger_period,
                g.bollinger_std
            )
            
            if not bollinger_filter_pass:
                log.info(f"📈 布林带过滤: {etf} {get_security_name(etf)} {bollinger_info}")
        # ============================================
        
        # ========== 计算短期动量 ==========
        short_current_price = None
        short_10d_ago_price = None
        if len(price_series) >= g.short_lookback_days + 1:
            short_current_price = price_series[-1]
            short_10d_ago_price = price_series[-(g.short_lookback_days + 1)]
            # 计算短期动量：近N天的收益率
            short_return = short_current_price / short_10d_ago_price - 1
            # 转换为年化收益率
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_return = 0
            short_annualized = 0
        # =====================================

        # 使用策略1的线性权重计算方式计算长期动量
        # 使用最后g.lookback_days+1天的数据（包括当前价格）
        recent_price_series = price_series[-(g.lookback_days + 1):]
        y = np.log(recent_price_series)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))  # 线性权重1-2，近期权重更高

        # 计算年化收益率（完全复制策略1）
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1  # 年化处理

        # 计算R²（拟合优度，值越高趋势越稳定）- 使用加权计算（策略1方式）
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0

        # 综合得分 = 年化收益率 * 趋势稳定性（策略1的核心公式）
        score = annualized_returns * r_squared

        # 策略1的短期风控：过滤近3日跌幅超过N%的ETF
        if len(price_series) >= 4:
            # 检查最近3个交易日的连续表现（策略1的严格风控）
            day1_ratio = price_series[-1] / price_series[-2]  # 今日/昨日
            day2_ratio = price_series[-2] / price_series[-3]  # 昨日/前日  
            day3_ratio = price_series[-3] / price_series[-4]  # 前日/大前日
            
            # 如果任意一日跌幅超过N%，排除该ETF（策略1的逻辑）
            if min(day1_ratio, day2_ratio, day3_ratio) < g.loss:
                score = 0  # 设为0分，不会被选中
                log.info(f"⚠️ {etf} {get_security_name(etf)} 近3日有单日跌幅超5%，已排除")

        return {
            'etf': etf,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'slope': slope,
            'current_price': current_price,
            'short_return': short_return,
            'short_annualized': short_annualized,
            'short_momentum_pass': short_return >= g.short_momentum_threshold,
            'short_current_price': short_current_price,    # 新增
            'short_10d_ago_price': short_10d_ago_price,    # 新增
            'ma5': ma5,
            'ma25': ma25,
            'ma_condition_met': ma_condition_met,
            'ma_ratio': ma_ratio,
            'ma_condition_desc': condition_desc,
            'rsi_filter_pass': rsi_filter_pass,
            'current_rsi': current_rsi,
            'max_recent_rsi': max_rsi,
            'rsi_info': rsi_info,
            'macd_filter_pass': macd_filter_pass,
            'dif': dif_value,
            'dea': dea_value,
            'macd_bar': macd_bar,
            'macd_info': macd_info,
            'volume_filter_pass': volume_filter_pass,
            'volume_ratio': volume_ratio,
            'recent_volume': recent_volume,
            'avg_volume': avg_volume,
            'volume_info': volume_info,
            'bollinger_filter_pass': bollinger_filter_pass,
            'bollinger_info': bollinger_info
        }
    except Exception as e:
        log.warn(f"计算{etf}动量指标时出错: {e}")
        return None

# 获取ETF排名（添加短期动量和MA过滤）
def get_ranked_etfs():
    etf_metrics = []
    for etf in g.etf_pool:
        metrics = calculate_momentum_metrics(etf)
        if metrics is not None:
            # 应用短期动量过滤（如果启用）
            if g.use_short_momentum_filter and not metrics['short_momentum_pass']:
                # 增强日志：显示计算过程
                cur = metrics['short_current_price']
                ago = metrics['short_10d_ago_price']
                if cur is not None and ago is not None:
                    calc_detail = f"{cur:.3f}/{ago:.3f}-1={metrics['short_return']:.4f}"
                else:
                    calc_detail = f"数据不足，短期动量={metrics['short_return']:.4f}"
                log.info(f"📉 排除短期动量不足的ETF: {etf} {get_security_name(etf)}，短期动量计算: {calc_detail}，阈值: {g.short_momentum_threshold}")
                continue
            
            # 应用MA过滤（如果启用）
            if g.use_ma_filter and not metrics['ma_condition_met']:
                log.info(f"📊 排除MA条件不符的ETF: {etf} {get_security_name(etf)}，MA{g.ma_short_period}: {metrics['ma5']:.3f}，MA{g.ma_long_period}: {metrics['ma25']:.3f}，{metrics['ma_condition_desc']}: {metrics['ma_ratio']:.4f}")
                continue
            
            # 应用RSI过滤（如果启用）
            if g.use_rsi_filter and not metrics['rsi_filter_pass']:
                continue
            
            # 应用MACD过滤（如果启用）
            if g.use_macd_filter and not metrics['macd_filter_pass']:
                continue
            
            # 应用成交量过滤（如果启用）
            if g.use_volume_filter and not metrics['volume_filter_pass']:
                continue
            
            # 应用布林带过滤（如果启用）
            if g.use_bollinger_filter and not metrics['bollinger_filter_pass']:
                continue
            
            # 过滤掉得分异常的ETF（得分过高可能是数据异常）
            if 0 < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)
            else:
                log.info(f"排除异常值ETF: {etf} {get_security_name(etf)}，得分: {metrics['score']:.4f}")
    
    # 按得分降序排序
    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics

# 获取基金名称
def get_security_name(security):
    """获取证券名称"""
    current_data = get_current_data()
    return current_data[security].name if security in current_data else security

# 自定义下单函数（完善交易执行控制，参考策略1的交易逻辑）
def smart_order_target_value(security, target_value, context):
    """
    智能下单函数，检查交易条件并执行下单
    参考策略1的交易控制逻辑
    """
    current_data = get_current_data()
    
    # 检查标的是否停牌
    if current_data[security].paused:
        log.info(f"{security} {get_security_name(security)}: 今日停牌，跳过交易")
        return False

    # 检查涨停（策略1的涨停检查）
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {get_security_name(security)}: 当前涨停，跳过买入")
        return False

    # 检查跌停（策略1的跌停检查）
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {get_security_name(security)}: 当前跌停，跳过卖出")
        return False

    # 获取当前价格
    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"{security} {get_security_name(security)}: 当前价格为0，跳过交易")
        return False

    # 计算目标数量
    target_amount = int(target_value / current_price)
    
    # 对于ETF，按100股整数倍调整（实盘交易要求）
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100  # 至少买100股
    
    # 获取当前持仓
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    
    # 计算需要调整的数量
    amount_diff = target_amount - current_amount
    
    # 检查最小交易金额
    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < g.min_money:
        log.info(f"{security} {get_security_name(security)}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过交易")
        return False

    # 检查T+1限制（策略1的关键风控）
    if amount_diff < 0:  # 卖出操作
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {get_security_name(security)}: 当天买入不可卖出(T+1)")
            return False
        # 确保卖出数量不超过可卖数量
        amount_diff = -min(abs(amount_diff), closeable_amount)

    # 执行下单
    if amount_diff != 0:
        # 使用order函数下单，让聚宽处理具体交易细节
        order_result = order(security, amount_diff)
        if order_result:
            # 更新持仓记录（参考策略1的持仓管理）
            if security not in g.positions:
                g.positions[security] = 0
            g.positions[security] = target_amount
            
            # 新增：如果买入操作，初始化最高价记录和ATR止损价
            if amount_diff > 0 and security in g.etf_pool:
                g.position_highs[security] = current_price
                
                # 计算ATR止损价
                if g.use_atr_stop_loss and not (g.atr_exclude_defensive and security == g.defensive_etf):
                    current_atr, _, success, _ = calculate_atr(security, g.atr_period)
                    if success:
                        if g.atr_trailing_stop:
                            g.position_stop_prices[security] = current_price - g.atr_multiplier * current_atr
                        else:
                            g.position_stop_prices[security] = current_price - g.atr_multiplier * current_atr
            
            security_name = get_security_name(security)
            if amount_diff > 0:
                log.info(f"📥 买入 {security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}，金额: {trade_value:.2f}")
            else:
                log.info(f"📤 卖出 {security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}，金额: {trade_value:.2f}")
            return True
        else:
            log.warn(f"下单失败: {security} {get_security_name(security)}，数量: {amount_diff}")
            return False
    
    return False

# 检查防御性ETF是否可交易
def is_defensive_etf_available():
    """检查黄金ETF是否可交易"""
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    
    if defensive_etf not in g.etf_pool:
        return False
        
    if current_data[defensive_etf].paused:
        log.info(f"防御性ETF {defensive_etf} {get_security_name(defensive_etf)} 今日停牌")
        return False
        
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        log.info(f"防御性ETF {defensive_etf} {get_security_name(defensive_etf)} 当前涨停")
        return False
        
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        log.info(f"防御性ETF {defensive_etf} {get_security_name(defensive_etf)} 当前跌停")
        return False
        
    return True

# ETF轮动交易主函数
def etf_trade(context):
    # 获取ETF排名和指标（已过滤异常值）
    ranked_etfs = get_ranked_etfs()
    
    # 记录所有ETF的指标（包括短期动量和MA指标）
    log.info("=== ETF趋势指标分析（含短期动量、MA指标、RSI指标、MACD指标、成交量指标和布林带指标） ===")
    for metrics in ranked_etfs:
        etf_name = get_security_name(metrics['etf'])
        # 构造短期动量显示文本（带计算过程）
        if metrics['short_current_price'] is not None and metrics['short_10d_ago_price'] is not None:
            short_info = f"{metrics['short_return']:.4f}({metrics['short_current_price']:.3f}/{metrics['short_10d_ago_price']:.3f}-1)"
        else:
            short_info = f"{metrics['short_return']:.4f}"
        bollinger_status = metrics['bollinger_info'] if g.use_bollinger_filter else "未启用"
        log.info(f"{metrics['etf']} {etf_name}: 年化={metrics['annualized_returns']:.4f}, R²={metrics['r_squared']:.4f}, 得分={metrics['score']:.4f}, 短期动量={short_info}, MA{g.ma_short_period}={metrics['ma5']:.3f}, MA{g.ma_long_period}={metrics['ma25']:.3f}, 成交量比={metrics['volume_ratio']:.2f}, RSI={metrics['current_rsi']:.1f}, MACD(DIF={metrics['dif']:.4f}), 布林带={bollinger_status}, 当前价={metrics['current_price']:.3f}")
    
    # 如果没有通过过滤条件的ETF，记录日志
    filter_conditions = []
    if g.use_short_momentum_filter:
        filter_conditions.append(f"短期动量<{g.short_momentum_threshold}")
    if g.use_ma_filter:
        if g.ma_filter_condition == "above":
            ma_desc = f"MA{g.ma_short_period}<MA{g.ma_long_period}"
        else:
            ma_desc = f"MA{g.ma_short_period}>MA{g.ma_long_period}"
        filter_conditions.append(ma_desc)
    if g.use_rsi_filter:
        filter_conditions.append(f"RSI过滤(近{g.rsi_lookback_days}日曾>{g.rsi_threshold}且现价<MA5)")
    if g.use_macd_filter:
        if g.macd_filter_condition == "bullish":
            macd_desc = f"MACD不满足看多条件(DIF>DEA)"
        else:
            macd_desc = f"MACD不满足看空条件(DIF<DEA)"
        filter_conditions.append(macd_desc)
    if g.use_volume_filter:
        filter_conditions.append(f"成交量>近{g.volume_lookback_days}日均{g.volume_threshold}倍")
    if g.use_bollinger_filter:
        filter_conditions.append(f"布林带过滤(近{g.bollinger_lookback_days}日曾突破上轨且现价<MA5)")
    
    if (g.use_short_momentum_filter or g.use_ma_filter or g.use_rsi_filter or g.use_macd_filter or g.use_volume_filter or g.use_bollinger_filter) and not ranked_etfs:
        log.info(f"📊 所有ETF均未通过过滤条件({', '.join(filter_conditions)})，将进入防御模式或空仓")

    # 确定目标ETF - 只选择得分最高的一只
    target_etf = None
    if ranked_etfs and ranked_etfs[0]['score'] >= g.min_score_threshold:
        # 正常模式：选择得分最高的一只ETF
        target_etf = ranked_etfs[0]['etf']
        top_metrics = ranked_etfs[0]
        etf_name = get_security_name(target_etf)
        # 最终选择日志也显示短期动量计算过程
        if top_metrics['short_current_price'] is not None and top_metrics['short_10d_ago_price'] is not None:
            short_info = f"{top_metrics['short_return']:.4f}({top_metrics['short_current_price']:.3f}/{top_metrics['short_10d_ago_price']:.3f}-1)"
        else:
            short_info = f"{top_metrics['short_return']:.4f}"
        log.info(f"🎯 正常模式，选择得分最高的ETF: {target_etf} {etf_name}，得分: {top_metrics['score']:.4f}，短期动量: {short_info}，MA比率: {top_metrics['ma_ratio']:.4f}，成交量比: {top_metrics['volume_ratio']:.2f}，RSI: {top_metrics['current_rsi']:.1f}，MACD柱: {top_metrics['macd_bar']:.4f}，布林带: {top_metrics['bollinger_info']}")
    else:
        # 防御模式：检查是否可买入防御ETF
        # 注意：防御性ETF可以豁免过滤条件，因为它是在市场不好时的避险选择
        if is_defensive_etf_available():
            target_etf = g.defensive_etf
            etf_name = get_security_name(target_etf)
            log.info(f"🛡️ 进入防御模式，选择防御ETF: {target_etf} {etf_name}")
        else:
            log.info("💤 进入空仓模式，所有ETF得分均不达标且防御ETF不可用")
    
    target_etfs = [target_etf] if target_etf else []
    
    # 检查并执行固定百分比止损
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        # 确保只处理ETF池中的标的且当前有持仓
        if security in g.etf_pool and position.total_amount > 0:
            current_price = position.price
            cost_price = position.avg_cost
            # 止损检查
            if current_price <= cost_price * g.stop_loss:
                # 使用智能下单函数执行止损
                success = smart_order_target_value(security, 0, context)
                if success:
                    security_name = get_security_name(security)
                    loss_percent = (current_price/cost_price-1)*100
                    log.info(f"🚨 固定百分比止损卖出: {security} {security_name}，成本: {cost_price:.3f}，现价: {current_price:.3f}，亏损: {loss_percent:.2f}%")
                    
                    # 清除记录
                    if security in g.position_highs:
                        del g.position_highs[security]
                    if security in g.position_stop_prices:
                        del g.position_stop_prices[security]

    # 计算目标持仓金额
    total_value = context.portfolio.total_value
    target_value = total_value if target_etfs else 0
    
    # 调仓逻辑
    current_positions = set(context.portfolio.positions.keys())
    target_etfs_set = set(target_etfs)
    
    # 卖出不在目标列表中的ETF
    for security in current_positions:
        if security in g.etf_pool and security not in target_etfs_set:
            position = context.portfolio.positions[security]
            if position.total_amount > 0:  # 确保有持仓才卖出
                success = smart_order_target_value(security, 0, context)
                if success:
                    security_name = get_security_name(security)
                    log.info(f"📤 卖出: {security} {security_name} (不在目标列表中)")
                    
                    # 清除记录
                    if security in g.position_highs:
                        del g.position_highs[security]
                    if security in g.position_stop_prices:
                        del g.position_stop_prices[security]

    # 调整目标ETF的仓位
    for etf in target_etfs:
        # 获取该ETF的指标用于日志显示
        etf_metrics = next((m for m in ranked_etfs if m['etf'] == etf), None)
        
        # 计算当前持仓价值
        current_value = 0
        if etf in context.portfolio.positions:
            position = context.portfolio.positions[etf]
            if position.total_amount > 0:
                current_value = position.total_amount * position.price
        
        # 判断是否需要调仓（5%容差）
        if abs(current_value - target_value) > target_value * 0.05 or current_value == 0:
            success = smart_order_target_value(etf, target_value, context)
            if success and etf_metrics:
                action = "买入" if current_value < target_value else "调仓"
                etf_name = get_security_name(etf)
                log.info(f"📦 {action}: {etf} {etf_name}，目标金额: {target_value:.2f}，年化: {etf_metrics['annualized_returns']:.4f}，R²: {etf_metrics['r_squared']:.4f}，得分: {etf_metrics['score']:.4f}，短期动量: {etf_metrics['short_return']:.4f}，MA比率: {etf_metrics['ma_ratio']:.4f}，成交量比: {etf_metrics['volume_ratio']:.2f}，RSI: {etf_metrics['current_rsi']:.1f}，MACD柱: {etf_metrics['macd_bar']:.4f}，布林带: {etf_metrics['bollinger_info']}")

# 每日交易执行函数（保持兼容性）
def trade(context):
    """主交易函数，为了兼容性保留"""
    etf_trade(context)

