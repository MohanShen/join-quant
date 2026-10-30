# Clone from JoinQuant
# postId: 172cce1d195f92113d0ea7da087d92af
# backtestId: 72123a8d4bdf0db9540bcd063157630a
# title: ETF动量策略V3-懒人躲避熊市

# 导入函数库
from jqdata import *
import pandas as pd
import numpy as np
import datetime

def initialize(context):
    # 设置基准
    set_benchmark('000300.XSHG')
    # 使用真实价格
    set_option('use_real_price', True)
    # 设置佣金（ETF免印花税，佣金万分之0.8）
    set_order_cost(OrderCost(close_tax=0, open_commission=0.00008, close_commission=0.00008, min_commission=0), type='fund')
    log.set_level('order', 'error')
    
    # ========== 策略参数 ==========
    g.etf_pool = get_etf_pool(context)           # 300只ETF池，传入context
    g.max_positions = 3                          # 最大持仓数量（改为3只）
    g.trend_ma_short = 5
    g.trend_ma_long = 20
    g.adx_threshold = 20
    g.stop_loss = 0.08
    g.trailing_stop = 0.08
    g.max_drawdown = 0.12
    g.peak_value = None
    g.last_trade_date = None
    g.peak_price = {}
    g.breakout_triggered = False
    g.breakout_hold_days = 0
    g.breakout_max_hold = 15                    # 突破后最多持有15个交易日
    
    # 大盘择时参数
    g.market_ma_long = 20
    g.market_volume_ma = 20
    g.market_confirm_days = 1
    
    # 选股因子权重
    g.momentum_short = 5
    g.momentum_mid = 20
    g.relative_strength_weight = 0.2
    g.trend_strength_weight = 0.1
    
    # 政策热点关键词
    g.policy_keywords = ['人工智能', '芯片', '半导体', '数字经济', '新能源', '光伏', 
                         '新能源汽车', '国企改革', '中特估', '低空经济', '新质生产力']
    
    # ========== 定时任务 ==========
    # 每周一 09:35 执行调仓（weekday=1代表周一，可改为0-6）
    run_weekly(weekly_rebalance, weekday=1, time='09:35', reference_security='000300.XSHG')
    # 收盘后风控（每日）
    run_daily(after_trading_end, time='after_close', reference_security='000300.XSHG')
    # 盘中止损（每日）
    run_daily(stop_loss_check, time='every_bar', reference_security='000300.XSHG')


# ==================== ETF池（300只，宽基12%） ====================
def get_etf_pool(context):
    """
    动态获取流动性最好的300只ETF，宽基约占12%
    若动态获取失败，则使用预定义列表
    """
    try:
        # 获取所有ETF基金代码
        etf_list = get_fundamentals(query(
            fund_public_info.fund_code,
            fund_public_info.fund_type
        ).filter(
            fund_public_info.fund_type.like('%ETF%')
        ), date=context.current_dt.date())
        if len(etf_list) == 0:
            return get_default_etf_pool()
        
        codes = [code + ('.XSHG' if code.startswith('51') else '.XSHE') 
                 for code in etf_list['fund_code'].values]
        
        # 计算最近20日日均成交额
        today = context.current_dt.date()
        start = today - datetime.timedelta(days=20)
        volumes = {}
        for code in codes[:500]:
            try:
                df = attribute_history(code, count=20, fields=['volume'], df=True)
                if len(df) >= 10:
                    volumes[code] = df['volume'].mean()
            except:
                continue
        
        sorted_codes = sorted(volumes.items(), key=lambda x: x[1], reverse=True)[:300]
        etf_pool = [code for code, _ in sorted_codes]
        
        broad_keywords = ['300', '500', '50', '创业板', '科创50', '双创', '深证100', '中证1000']
        broad_etfs = [c for c in etf_pool if any(kw in c for kw in broad_keywords) or 
                      any(kw in get_security_info(c).display_name for kw in broad_keywords)]
        if len(broad_etfs) > 36:
            broad_etfs = broad_etfs[:36]
        elif len(broad_etfs) < 36:
            others = [c for c in etf_pool if c not in broad_etfs]
            broad_etfs += others[:36 - len(broad_etfs)]
        final_pool = broad_etfs + [c for c in etf_pool if c not in broad_etfs][:300 - len(broad_etfs)]
        return final_pool[:300]
    except:
        return get_default_etf_pool()


def get_default_etf_pool():
    """预定义300只ETF列表（宽基36只 + 行业/主题264只）"""
    broad_etfs = [
        '510300.XSHG', '510500.XSHG', '159915.XSHE', '588000.XSHG', '510050.XSHG',
        '159949.XSHE', '512100.XSHG', '159922.XSHE', '510310.XSHG', '159901.XSHE',
        '159919.XSHE', '510330.XSHG', '159905.XSHE', '512500.XSHG', '159902.XSHE',
        '159916.XSHE', '159948.XSHE', '159967.XSHE', '159781.XSHE', '159780.XSHE',
        '159790.XSHE', '588050.XSHG', '588080.XSHG', '588090.XSHG', '588180.XSHG',
        '516970.XSHG', '517180.XSHG', '516750.XSHG', '510880.XSHG', '515080.XSHG',
        '515180.XSHG', '159820.XSHE', '159825.XSHE', '159830.XSHE', '159835.XSHE',
        '159840.XSHE'
    ]
    while len(broad_etfs) < 36:
        broad_etfs.append('510300.XSHG')
    broad_etfs = broad_etfs[:36]

    sector_etfs = [
        '512480.XSHG', '159995.XSHE', '512760.XSHG', '515050.XSHG', '159819.XSHE',
        '515070.XSHG', '159852.XSHE', '515000.XSHG', '512330.XSHG', '159939.XSHE',
        '588080.XSHG', '588090.XSHG', '159967.XSHE', '159780.XSHE', '516160.XSHG',
        '515020.XSHG', '159997.XSHE', '512770.XSHG', '159806.XSHE', '516500.XSHG',
        '159888.XSHE', '515880.XSHG', '516650.XSHG', '516600.XSHG', '159870.XSHE',
        '516950.XSHG', '159722.XSHE', '512580.XSHG', '159865.XSHE', '512980.XSHG',
        '159805.XSHE', '159766.XSHE', '561800.XSHG', '516780.XSHG', '159892.XSHE',
        '516390.XSHG', '516380.XSHG', '159755.XSHE', '561910.XSHG', '515700.XSHG',
        '159864.XSHE', '516880.XSHG', '159945.XSHE', '515030.XSHG', '159806.XSHE',
        '516750.XSHG', '512690.XSHG', '159928.XSHE', '515650.XSHG', '159996.XSHE',
        '561130.XSHG', '515170.XSHG', '159843.XSHE', '159895.XSHE', '512600.XSHG',
        '516900.XSHG', '159930.XSHE', '515220.XSHG', '159981.XSHE', '512010.XSHG',
        '159929.XSHE', '512290.XSHG', '159839.XSHE', '159992.XSHE', '515120.XSHG',
        '512170.XSHG', '159828.XSHE', '159883.XSHE', '516610.XSHG', '159858.XSHE',
        '560080.XSHG', '512880.XSHG', '512000.XSHG', '159841.XSHE', '512800.XSHG',
        '159940.XSHE', '512200.XSHG', '159707.XSHE', '512070.XSHG', '512660.XSHG',
        '512710.XSHG', '159959.XSHE', '516780.XSHG', '159892.XSHE', '516500.XSHG',
        '159888.XSHE', '515880.XSHG', '512400.XSHG', '159930.XSHE', '515220.XSHG',
        '159945.XSHE', '516650.XSHG', '159981.XSHE', '516600.XSHG', '159870.XSHE',
        '516950.XSHG', '159722.XSHE', '510880.XSHG', '515080.XSHG', '159905.XSHE',
        '512890.XSHG', '515450.XSHG', '513100.XSHG', '513500.XSHG', '159740.XSHE',
        '513130.XSHG', '518880.XSHG', '159937.XSHE', '513050.XSHG', '513010.XSHG',
        '513090.XSHG', '513600.XSHG', '159920.XSHE', '159941.XSHE', '513030.XSHG'
    ]
    sector_etfs = list(dict.fromkeys(sector_etfs))
    while len(sector_etfs) < 264:
        sector_etfs.append('512480.XSHG')
    sector_etfs = sector_etfs[:264]
    return broad_etfs + sector_etfs


# ==================== 政策热点判断 ====================
def is_policy_hot(etf, current_date):
    try:
        name = get_security_info(etf).display_name
        for kw in g.policy_keywords:
            if kw in name:
                return True
        return False
    except:
        return False


# ==================== 大盘择时（严格） ====================
def market_timing_check(date):
    """沪深300收盘价低于20日均线即空仓"""
    try:
        hs300 = get_price('000300.XSHG', end_date=date, count=30,
                          frequency='daily', fields=['close'])
        if len(hs300) < g.market_ma_long:
            return True
        close = hs300['close'].values
        ma20 = np.mean(close[-g.market_ma_long:])
        return close[-1] > ma20
    except:
        return True


# ==================== 突破信号检测（捕捉政策行情）====================
def check_breakout_signal(date):
    """沪深300单日涨幅>3%且成交量>20日均量1.5倍"""
    try:
        hs300 = get_price('000300.XSHG', start_date=date, end_date=date,
                          frequency='daily', fields=['close', 'volume'])
        if len(hs300) == 0:
            return False
        close = hs300['close'][0]
        volume = hs300['volume'][0]
        prev_data = get_price('000300.XSHG', end_date=date - datetime.timedelta(days=1), count=1,
                              frequency='daily', fields=['close'])
        if len(prev_data) == 0:
            return False
        prev_close = prev_data['close'][0]
        ret = (close - prev_close) / prev_close
        
        vol_data = get_price('000300.XSHG', end_date=date, count=21,
                             frequency='daily', fields=['volume'])
        if len(vol_data) < 20:
            return False
        vol_ma20 = vol_data['volume'][:-1].mean()
        volume_surge = volume > vol_ma20 * 1.5
        
        return ret > 0.03 and volume_surge
    except:
        return False


# ==================== 选股评分（趋势+动量+相对强度）====================
def get_etf_score(etf, current_date, benchmark_close=None):
    """计算综合得分，返回得分或None"""
    try:
        df = attribute_history(etf, count=61, fields=['close'], df=True)
        if len(df) < 61:
            return None
        close = df['close'].values
        
        # 基础过滤：价格>20日均线
        ma20 = np.mean(close[-20:])
        if close[-1] <= ma20:
            return None
        
        # 5日动量（必须为正）
        ret_5 = (close[-1] - close[-6]) / close[-6] if len(close) >= 6 else 0
        if ret_5 <= 0:
            return None
        
        # 20日动量
        ret_20 = (close[-1] - close[-21]) / close[-21] if len(close) >= 21 else 0
        
        # 相对强度（相对于沪深300的20日超额收益）
        relative = 0
        if benchmark_close is not None and len(benchmark_close) >= 21:
            bench_ret_20 = (benchmark_close[-1] - benchmark_close[-21]) / benchmark_close[-21]
            relative = ret_20 - bench_ret_20
        
        # 趋势强度：价格/60日均线
        ma60 = np.mean(close[-60:])
        trend = close[-1] / ma60 if ma60 > 0 else 1
        
        # 4周涨幅限制（避免追高）
        if len(close) >= 21:
            ret_4w = (close[-1] - close[-21]) / close[-21]
            if ret_4w > 0.40:
                return None
        
        # 综合得分
        score = (0.3 * ret_5 + 0.4 * ret_20 + 0.2 * relative + 0.1 * trend)
        return score
    except:
        return None


# ==================== ADX趋势强度（未使用但保留）====================
def get_adx(security, date, period=14):
    try:
        df = attribute_history(security, count=period+5, fields=['high','low','close'], df=True)
        if len(df) < period:
            return 0
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        tr = []
        for i in range(1, len(close)):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i-1])
            lc = abs(low[i] - close[i-1])
            tr.append(max(hl, hc, lc))
        volatility = np.std(close[-period:] / close[-period-1]) * np.sqrt(252)
        return volatility * 100
    except:
        return 0


# ==================== 趋势破坏检查（严格）====================
def check_trend_broken(etf, current_date):
    """趋势破坏：价格跌破20日均线 或 5日均线下穿20日均线"""
    try:
        df = attribute_history(etf, count=25, fields=['close'], df=True)
        if len(df) < 20:
            return True
        close = df['close'].values
        ma5 = np.mean(close[-5:])
        ma20 = np.mean(close[-20:])
        if close[-1] <= ma20:
            return True
        if ma5 <= ma20:
            return True
        return False
    except:
        return True


# ==================== 每周调仓函数（原market_open重命名）====================
def weekly_rebalance(context):
    current_date = context.current_dt.date()
    yesterday = current_date - datetime.timedelta(days=1)
    
    # 记录是否有任何交易操作
    has_trade = False
    
    # 1. 大盘择时
    if not market_timing_check(current_date):
        # 清仓
        for stock in list(context.portfolio.positions.keys()):
            order_target_value(stock, 0)
            has_trade = True
        g.last_trade_date = current_date
        log.info('大盘择时空仓')
        return
    
    # 2. 检查突破信号（昨日是否出现）
    is_breakout = check_breakout_signal(yesterday)
    if is_breakout:
        log.info('检测到突破信号，重置突破模式')
        g.breakout_triggered = True
        g.breakout_hold_days = 0
        # 突破模式选股（高弹性、政策热点）
        candidates = []
        try:
            hs300 = get_price('000300.XSHG', end_date=current_date, count=21, fields=['close'])
            bench_close = hs300['close'].values
        except:
            bench_close = None
        
        for etf in g.etf_pool:
            try:
                df = attribute_history(etf, count=21, fields=['close'], df=True)
                if len(df) < 21:
                    continue
                close = df['close'].values
                if close[-1] <= np.mean(close[-20:]):
                    continue
                ret_5 = (close[-1] - close[-6]) / close[-6] if len(close) >= 6 else 0
                if ret_5 <= 0:
                    continue
                daily_ret = close[-20:] / close[-21] - 1
                vol = np.std(daily_ret) * np.sqrt(252)
                policy_bonus = 1.2 if is_policy_hot(etf, current_date) else 1.0
                score = ret_5 * (1 + vol) * policy_bonus
                candidates.append((etf, score))
            except:
                continue
        if len(candidates) > 0:
            candidates.sort(key=lambda x: x[1], reverse=True)
            top_etfs = [etf for etf, _ in candidates[:g.max_positions]]
            # 调仓
            current_holdings = list(context.portfolio.positions.keys())
            for stock in current_holdings:
                if stock not in top_etfs:
                    order_target_value(stock, 0)
                    has_trade = True
            target_value = context.portfolio.total_value / len(top_etfs) if top_etfs else 0
            for etf in top_etfs:
                order_target_value(etf, target_value)
                has_trade = True
            g.last_trade_date = current_date
            log.info('突破模式调仓，持仓：{}'.format(top_etfs))
        return
    
    # 3. 常规模式（每周调仓日评估）
    # 如果突破模式已触发且持有天数未超过最大持有期，则继续持有原仓位（不做替换，只做退出检查）
    if g.breakout_triggered:
        g.breakout_hold_days += 1
        for stock in list(context.portfolio.positions.keys()):
            if check_trend_broken(stock, current_date):
                order_target_value(stock, 0)
                has_trade = True
                log.info('突破模式持仓趋势破坏，卖出 {}'.format(stock))
                g.breakout_triggered = False
                g.breakout_hold_days = 0
        if len(context.portfolio.positions.keys()) == 0:
            g.breakout_triggered = False
            g.breakout_hold_days = 0
        if g.breakout_hold_days >= g.breakout_max_hold:
            for stock in list(context.portfolio.positions.keys()):
                order_target_value(stock, 0)
                has_trade = True
            log.info('突破模式持有期满，清仓')
            g.breakout_triggered = False
            g.breakout_hold_days = 0
        if has_trade:
            g.last_trade_date = current_date
        return
    
    # 4. 常规每周调仓（非突破模式）
    try:
        hs300 = get_price('000300.XSHG', end_date=current_date, count=21, fields=['close'])
        bench_close = hs300['close'].values
    except:
        bench_close = None
    
    # 计算所有ETF得分
    scores = {}
    for etf in g.etf_pool:
        score = get_etf_score(etf, current_date, bench_close)
        if score is not None:
            scores[etf] = score
    
    if len(scores) == 0:
        for stock in list(context.portfolio.positions.keys()):
            order_target_value(stock, 0)
            has_trade = True
        if has_trade:
            g.last_trade_date = current_date
        return
    
    current_holdings = list(context.portfolio.positions.keys())
    
    # 检查现有持仓是否还满足趋势条件
    for stock in current_holdings[:]:
        if check_trend_broken(stock, current_date):
            order_target_value(stock, 0)
            has_trade = True
            log.info('趋势破坏，卖出 {}'.format(stock))
            current_holdings.remove(stock)
    
    # 计算现有持仓得分
    holding_scores = {}
    for stock in current_holdings:
        score = get_etf_score(stock, current_date, bench_close)
        if score is not None:
            holding_scores[stock] = score
        else:
            order_target_value(stock, 0)
            has_trade = True
            current_holdings.remove(stock)
    
    # 补足仓位至 g.max_positions 只
    need = g.max_positions - len(current_holdings)
    if need > 0:
        candidate_list = [(etf, score) for etf, score in scores.items() if etf not in current_holdings]
        candidate_list.sort(key=lambda x: x[1], reverse=True)
        new_etfs = [etf for etf, _ in candidate_list[:need]]
        if new_etfs:
            target_value = context.portfolio.total_value / g.max_positions
            for etf in new_etfs:
                order_target_value(etf, target_value)
                has_trade = True
            current_holdings.extend(new_etfs)
            log.info('补入新持仓：{}'.format(new_etfs))
    elif len(current_holdings) == g.max_positions:
        # 持仓已满，检查是否需要替换
        worst_stock = min(holding_scores.items(), key=lambda x: x[1])[0]
        worst_score = holding_scores[worst_stock]
        best_candidate = max([(etf, score) for etf, score in scores.items() if etf not in current_holdings],
                             key=lambda x: x[1], default=(None, -999))
        if best_candidate[0] is not None and best_candidate[1] > worst_score * 1.05:
            order_target_value(worst_stock, 0)
            has_trade = True
            target_value = context.portfolio.total_value / g.max_positions
            order_target_value(best_candidate[0], target_value)
            has_trade = True
            log.info('替换持仓：卖出 {} (得分{:.4f})，买入 {} (得分{:.4f})'.format(
                worst_stock, worst_score, best_candidate[0], best_candidate[1]))
    
    if has_trade:
        g.last_trade_date = current_date
    else:
        log.info('{} 无调仓操作'.format(current_date))


# ==================== 风控函数（每日执行） ====================
def after_trading_end(context):
    current_value = context.portfolio.portfolio_value
    if g.peak_value is None or current_value > g.peak_value:
        g.peak_value = current_value
    if g.peak_value > 0:
        drawdown = (g.peak_value - current_value) / g.peak_value
        if drawdown >= g.max_drawdown:
            for stock in list(context.portfolio.positions.keys()):
                order_target_value(stock, 0)
            log.info('触发组合回撤止损（{:.2%}），清仓！'.format(drawdown))

def stop_loss_check(context):
    current_data = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.total_amount == 0:
            continue
        if stock not in current_data:
            continue
        current_price = current_data[stock].close
        cost = pos.avg_cost
        if cost > 0:
            loss_pct = (current_price - cost) / cost
            if loss_pct <= -g.stop_loss:
                order_target_value(stock, 0)
                log.info('触发单只止损 {}，亏损 {:.2%}'.format(stock, loss_pct))
                if stock in g.peak_price:
                    del g.peak_price[stock]
                continue
            if stock not in g.peak_price:
                g.peak_price[stock] = current_price
            else:
                if current_price > g.peak_price[stock]:
                    g.peak_price[stock] = current_price
                else:
                    drawdown = (g.peak_price[stock] - current_price) / g.peak_price[stock]
                    if drawdown >= g.trailing_stop:
                        order_target_value(stock, 0)
                        log.info('触发移动止损 {}，回撤 {:.2%}'.format(stock, drawdown))
                        if stock in g.peak_price:
                            del g.peak_price[stock]