# Clone from JoinQuant
# postId: 537edfaeaae663007f1c6a5703a780d0
# backtestId: 926f977fcfe0284475c0d28478c40918
# title: 选用近5日最热门板块，人气最高最强股的策略

# 导入必要的库
from jqdata import *
import pandas as pd
import numpy as np
import datetime

# 1. 初始化配置
def initialize(context):
    # 设置日志级别，屏蔽交易系统日志
    log.set_level('order', 'error')  # 只显示错误级别的订单日志
    log.set_level('system', 'error') # 只显示错误级别的系统日志
    
    # 设置主线相关板块代码池
    g.main_concepts = {
        'AI核心': ['AI概念', 'ChatGPT概念', '机器人概念', '算力概念', 'AIGC概念'],
        '基础设施': ['云计算', '数据中心', 'GPU', '服务器', 'FPGA', '存储芯片'],
        '软件数据': ['大数据', '国产软件', '信创产业', '工业软件'],
        '智能应用': ['智能驾驶', '智慧医疗', '智能制造', '智慧城市'],
        '产业链': ['华为概念', '半导体', 'PCB', '光模块', '高端制造']
    }
    
    # 策略参数
    g.stock_num = 4          # 持股数
    g.concept_num = 3        # 跟踪的概念板块数
    g.position_size = 0.3    # 单股仓位
    g.min_hold_days = 3      # 最小持有天数
    g.max_hold_days = 20     # 最大持有天数
    
    # 运行参数
    run_daily(market_open, time='9:30')
    run_daily(market_close, time='14:50')

# 2. 板块分析
def analyze_concepts(context):
    """分析所有主线板块的强度和轮动情况"""
    all_concepts = []
    
    # 遍历所有主线板块
    for category, concepts in g.main_concepts.items():
        for concept_name in concepts:
            try:
                # 获取板块代码
                concept = get_concepts()[get_concepts()['name'] == concept_name]
                if len(concept) == 0:
                    continue
                concept_code = concept.index[0]
                
                # 获取板块成分股
                stocks = get_concept_stocks(concept_code)
                if len(stocks) < 10:  # 排除成分股过少的板块
                    continue
                
                # 计算板块指标
                concept_data = {
                    'code': concept_code,
                    'name': concept_name,
                    'category': category,
                    'stock_count': len(stocks)
                }
                
                # 1. 计算涨幅指标
                prices = get_price(stocks, count=11, end_date=context.current_dt, 
                                 fields=['close', 'volume', 'money'],
                                 panel=False)  # 修改这里，使用DataFrame格式
                
                # 重新组织数据结构
                close_df = prices.pivot(columns='code', values='close')
                volume_df = prices.pivot(columns='code', values='volume')
                money_df = prices.pivot(columns='code', values='money')
                
                # 当日、5日、10日涨幅
                concept_data['rise_1d'] = (close_df.iloc[-1] / close_df.iloc[-2] - 1).mean() * 100
                concept_data['rise_5d'] = (close_df.iloc[-1] / close_df.iloc[-6] - 1).mean() * 100
                concept_data['rise_10d'] = (close_df.iloc[-1] / close_df.iloc[0] - 1).mean() * 100
                
                # 2. 计算资金流向
                concept_data['money_ratio'] = (
                    money_df.iloc[-1].sum() / 
                    money_df.iloc[-6:-1].mean().sum() - 1
                ) * 100
                
                # 3. 计算涨停数量
                current_data = get_current_data()
                limit_up_count = sum(1 for stock in stocks 
                                   if close_df[stock].iloc[-1] >= current_data[stock].high_limit * 0.99)
                concept_data['limit_up_count'] = limit_up_count
                
                # 4. 计算强势股数量（涨幅超5%的个股数量）
                strong_stocks = sum(1 for stock in stocks 
                                  if (close_df[stock].iloc[-1] / 
                                      close_df[stock].iloc[-2] - 1) > 0.05)
                concept_data['strong_stocks'] = strong_stocks
                
                # 5. 计算板块换手率
                concept_data['turnover'] = get_fundamentals(
                    query(valuation.turnover_ratio
                    ).filter(valuation.code.in_(stocks))
                )['turnover_ratio'].mean()
                
                # 6. 计算板块量能
                concept_data['volume_ratio'] = (
                    volume_df.iloc[-1].sum() / 
                    volume_df.iloc[-6:-1].mean().sum()
                )
                
                # 7. 计算龙头股表现
                market_caps = get_fundamentals(
                    query(valuation.code, valuation.market_cap
                    ).filter(valuation.code.in_(stocks))
                ).sort_values('market_cap', ascending=False)
                
                if len(market_caps) > 0:
                    leaders = market_caps.head(3)['code'].tolist()
                    leader_prices = get_price(leaders, count=2, end_date=context.current_dt, 
                                           fields=['close'], panel=False)  # 这里也修改
                    leader_close = leader_prices.pivot(columns='code', values='close')
                    concept_data['leader_rise'] = (
                        leader_close.iloc[-1] / 
                        leader_close.iloc[0] - 1
                    ).mean() * 100
                
                # 8. 计算综合得分 - 优化热度计算
                try:
                    # 基础分数
                    base_score = (
                        max(concept_data['rise_1d'], 0) * 0.3 +     # 当日涨幅权重
                        max(concept_data['rise_5d'], 0) * 0.2       # 5日涨幅权重
                    )
                    
                    # 热度分数
                    heat_score = (
                        concept_data['limit_up_count'] * 3.0 +      # 涨停股数量权重加大
                        concept_data['strong_stocks'] * 2.0 +       # 强势股权重加大
                        (concept_data['volume_ratio'] > 2) * 2.0 +  # 量能放大
                        (concept_data['money_ratio'] > 30) * 2.0    # 资金流入显著
                    )
                    
                    # 龙头股表现加分
                    leader_score = max(concept_data.get('leader_rise', 0), 0) * 0.3
                    
                    # 计算最终得分
                    concept_data['score'] = base_score + heat_score + leader_score
                    
                    # 惩罚项：当日跌幅超过2%或5日跌幅超过5%的板块得分减半
                    if concept_data['rise_1d'] < -2 or concept_data['rise_5d'] < -5:
                        concept_data['score'] *= 0.5
                        
                except:
                    concept_data['score'] = 0.0
                
                # 确保得分为有效数值
                if pd.isna(concept_data['score']) or np.isinf(concept_data['score']):
                    concept_data['score'] = 0.0
                
                all_concepts.append(concept_data)
                
            except Exception as e:
                log.error(f"处理板块 {concept_name} 时出错: {str(e)}")
                continue
    
    # 转换为DataFrame并排序
    if all_concepts:
        df = pd.DataFrame(all_concepts)
        # 确保所有数值列都是有效的数字
        numeric_columns = ['rise_1d', 'rise_5d', 'limit_up_count', 'strong_stocks', 
                         'volume_ratio', 'money_ratio', 'score']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        df = df.sort_values('score', ascending=False)
        
        # 输出板块分析结果
        log.info("\n=============== 热门概念板块排名 ===============")
        log.info(f"{'概念名称':<12} {'日涨幅':>8} {'5日涨幅':>8} {'涨停数':>6} {'强势股':>6} "
                f"{'量比':>6} {'资金比':>8} {'得分':>8}")
        log.info("-" * 75)
        
        for _, row in df.head(g.concept_num).iterrows():
            log.info(f"{row['name']:<12} {row['rise_1d']:>7.2f}% {row['rise_5d']:>7.2f}% "
                    f"{row['limit_up_count']:>6.0f} {row['strong_stocks']:>6.0f} "
                    f"{row['volume_ratio']:>6.2f} {row['money_ratio']:>7.2f}% {row['score']:>7.2f}")
        
        log.info("=" * 75 + "\n")
        
        return df
    
    return pd.DataFrame()

# 3. 选股逻辑
def select_stocks(context, hot_concepts):
    """从强势板块中选择最优质的股票"""
    if hot_concepts.empty:
        return []
    
    selected_stocks = []
    all_stock_scores = []  # 存储所有板块的股票得分
    
    # 遍历最强概念板块
    for _, concept in hot_concepts.head(g.concept_num).iterrows():
        try:
            # 获取板块成分股
            stocks = get_concept_stocks(concept['code'])
            if len(stocks) < 10:
                continue
            
            # 更严格的股票类型检查
            def is_valid_stock(stock):
                try:
                    # 获取股票信息
                    security_info = get_security_info(stock)
                    if security_info is None:
                        return False
                        
                    # 检查是否为ST股
                    if security_info.display_name.startswith(('ST', '*ST', 'SST')):
                        return False
                    
                    # 排除所有指数
                    if stock.startswith(('000', '399')):  # 深市指数通常以000或399开头
                        return False
                    # 确保是普通A股
                    if not stock.startswith(('000', '002', '300', '600', '601', '603', '605')):
                        return False
                    return True
                except:
                    return False
            
            # 过滤股票
            stocks = [s for s in stocks if is_valid_stock(s)]
            
            # 获取基本面数据
            q = query(
                valuation.code,
                valuation.market_cap,
                valuation.turnover_ratio,
                valuation.pe_ratio,
                indicator.roe,  # 新增ROE指标
                balance.total_assets,  # 新增总资产
                income.total_operating_revenue,  # 新增营收
                income.net_profit  # 新增净利润
            ).filter(
                valuation.code.in_(stocks),
                valuation.market_cap > 30,  # 市值大于30亿
                valuation.market_cap < 300  # 市值小于300亿
            ).order_by(valuation.code)
            
            df = get_fundamentals(q)
            if df.empty:
                continue
            
            # 获取最近交易数据 - 修改数据获取方式
            codes = sorted(df['code'].tolist())
            prices = {}
            for stock in codes:
                try:
                    price_data = get_price(stock, 
                                         count=21, 
                                         end_date=context.current_dt, 
                                         fields=['open', 'close', 'high', 'low', 'volume', 'money'],
                                         skip_paused=True)  # 跳过停牌
                    if price_data is not None and not price_data.empty:
                        prices[stock] = price_data
                except Exception as e:
                    log.error(f"获取股票 {stock} 价格数据时出错: {str(e)}")
                    continue
            
            # 获取技术指标数据
            tech_indicators = {}
            for stock in codes:
                try:
                    # 计算MACD
                    close_prices = prices[stock]['close']
                    ema12 = close_prices.ewm(span=12).mean()
                    ema26 = close_prices.ewm(span=26).mean()
                    dif = ema12 - ema26
                    dea = dif.ewm(span=9).mean()
                    macd = (dif - dea) * 2
                    
                    # 计算KDJ
                    low_prices = prices[stock]['low']
                    high_prices = prices[stock]['high']
                    
                    low_9 = low_prices.rolling(9).min()
                    high_9 = high_prices.rolling(9).max()
                    rsv = (close_prices - low_9) / (high_9 - low_9) * 100
                    k = rsv.ewm(com=2).mean()
                    d = k.ewm(com=2).mean()
                    j = 3 * k - 2 * d
                    
                    # 计算布林带
                    ma20 = close_prices.rolling(20).mean()
                    std20 = close_prices.rolling(20).std()
                    upper_band = ma20 + 2 * std20
                    lower_band = ma20 - 2 * std20
                    
                    # 计算均线多头排列
                    ma5 = close_prices.rolling(5).mean()
                    ma10 = close_prices.rolling(10).mean()
                    ma20 = close_prices.rolling(20).mean()
                    
                    tech_indicators[stock] = {
                        'macd': macd,
                        'dif': dif,
                        'dea': dea,
                        'k': k,
                        'd': d,
                        'j': j,
                        'ma5': ma5,
                        'ma10': ma10,
                        'ma20': ma20,
                        'upper_band': upper_band,
                        'lower_band': lower_band
                    }
                except Exception as e:
                    log.error(f"计算股票 {stock} 技术指标时出错: {str(e)}")
                    tech_indicators[stock] = None
            
            # 重新设计选股打分系统
            stock_scores = []
            current_data = get_current_data()
            
            for stock in codes:
                try:
                    # 检查是否有价格数据
                    if stock not in prices or stock not in tech_indicators or tech_indicators[stock] is None:
                        continue
                        
                    if current_data[stock].paused or \
                       current_data[stock].low_limit >= current_data[stock].high_limit:
                        continue
                    
                    price_data = prices[stock]
                    tech_data = tech_indicators[stock]
                    fund_data = df[df['code'] == stock].iloc[0]
                    
                    stock_data = {
                        'code': stock,
                        'concept': concept['name'],
                        'concept_score': concept['score']  # 加入板块得分
                    }
                    
                    # 1. 涨幅表现
                    stock_data['rise_1d'] = (price_data['close'][-1] / price_data['close'][-2] - 1) * 100
                    stock_data['rise_3d'] = (price_data['close'][-1] / price_data['close'][-4] - 1) * 100
                    stock_data['rise_5d'] = (price_data['close'][-1] / price_data['close'][-6] - 1) * 100
                    stock_data['rise_10d'] = (price_data['close'][-1] / price_data['close'][-11] - 1) * 100
                    
                    # 2. 量能分析
                    vol_5d_avg = price_data['volume'][-6:-1].mean()
                    stock_data['volume_ratio'] = price_data['volume'][-1] / vol_5d_avg if vol_5d_avg > 0 else 0
                    
                    # 3. 资金强度
                    money_5d_avg = price_data['money'][-6:-1].mean()
                    stock_data['money_ratio'] = price_data['money'][-1] / money_5d_avg if money_5d_avg > 0 else 0
                    
                    # 4. 涨停统计
                    high_limit = current_data[stock].high_limit
                    stock_data['limit_up_count'] = sum(1 for p in price_data['close'][-5:] 
                                                     if abs(p - high_limit) < high_limit * 0.001)
                    
                    # 5. 强度分析
                    # 5.1 创新高分析
                    highs_20d = price_data['high'][-20:].max()
                    stock_data['new_high'] = 1 if abs(price_data['close'][-1] - highs_20d) < highs_20d * 0.01 else 0
                    
                    # 5.2 突破分析
                    ma5 = tech_data['ma5'][-1]
                    ma10 = tech_data['ma10'][-1]
                    ma20 = tech_data['ma20'][-1]
                    stock_data['ma_break'] = 1 if price_data['close'][-1] > max(ma5, ma10) else 0
                    
                    # 5.3 连续上涨天数
                    up_days = 0
                    for i in range(len(price_data['close'])-1, 0, -1):
                        if price_data['close'][i] > price_data['close'][i-1]:
                            up_days += 1
                        else:
                            break
                    stock_data['continuous_up_days'] = up_days
                    
                    # 6. 技术指标分析
                    # 6.1 MACD金叉
                    stock_data['macd_golden_cross'] = 1 if (tech_data['dif'][-2] < tech_data['dea'][-2] and 
                                                          tech_data['dif'][-1] > tech_data['dea'][-1]) else 0
                    
                    # 6.2 MACD柱状图放大
                    stock_data['macd_hist_expand'] = 1 if (tech_data['macd'][-1] > 0 and 
                                                         tech_data['macd'][-1] > tech_data['macd'][-2] * 1.2) else 0
                    
                    # 6.3 KDJ金叉
                    stock_data['kdj_golden_cross'] = 1 if (tech_data['k'][-2] < tech_data['d'][-2] and 
                                                         tech_data['k'][-1] > tech_data['d'][-1]) else 0
                    
                    # 6.4 KDJ超买区
                    stock_data['kdj_overbought'] = 1 if tech_data['j'][-1] > 80 else 0
                    
                    # 6.5 均线多头排列
                    stock_data['ma_alignment'] = 1 if (ma5 > ma10 > ma20 and 
                                                     price_data['close'][-1] > ma5) else 0
                    
                    # 6.6 布林带突破上轨
                    stock_data['bollinger_break'] = 1 if price_data['close'][-1] > tech_data['upper_band'][-1] else 0
                    
                    # 7. 成交结构分析
                    # 7.1 大单比例
                    stock_data['big_order_ratio'] = price_data['money'][-1] / price_data['volume'][-1] * 100 if price_data['volume'][-1] > 0 else 0
                    
                    # 7.2 开盘价位置
                    stock_data['open_position'] = (price_data['open'][-1] - price_data['low'][-1]) / (price_data['high'][-1] - price_data['low'][-1]) if (price_data['high'][-1] - price_data['low'][-1]) > 0 else 0.5
                    
                    # 7.3 收盘价位置
                    stock_data['close_position'] = (price_data['close'][-1] - price_data['low'][-1]) / (price_data['high'][-1] - price_data['low'][-1]) if (price_data['high'][-1] - price_data['low'][-1]) > 0 else 0.5
                    
                    # 7.4 尾盘强度
                    if len(price_data) >= 2:
                        stock_data['end_strength'] = (price_data['close'][-1] - (price_data['high'][-1] + price_data['low'][-1])/2) / ((price_data['high'][-1] - price_data['low'][-1])/2) if (price_data['high'][-1] - price_data['low'][-1]) > 0 else 0
                    else:
                        stock_data['end_strength'] = 0
                    
                    # 8. 基本面指标
                    stock_data['market_cap'] = fund_data['market_cap']
                    stock_data['pe_ratio'] = fund_data['pe_ratio'] if not pd.isna(fund_data['pe_ratio']) else 100
                    stock_data['roe'] = fund_data['roe'] if not pd.isna(fund_data['roe']) else 0
                    stock_data['turnover'] = fund_data['turnover_ratio'] if not pd.isna(fund_data['turnover_ratio']) else 0
                    
                    # 9. 行业地位分析
                    # 使用市值在板块中的排名作为行业地位指标
                    stock_data['industry_rank'] = df['market_cap'].rank(ascending=False)[df[df['code'] == stock].index[0]]
                    stock_data['industry_rank_ratio'] = stock_data['industry_rank'] / len(df)
                    
                    # 10. 资金流向分析
                    # 计算近5日主力资金净流入
                    stock_data['main_money_net_inflow'] = 1 if stock_data['money_ratio'] > 1.5 and stock_data['volume_ratio'] > 1.5 else 0
                    
                    # 计算更多风险指标
                    try:
                        # 1. 计算股票波动率 - 用于评估风险
                        close_prices = prices[stock]['close']
                        returns = close_prices.pct_change().dropna()
                        stock_data['volatility'] = returns.std() * 100  # 标准差百分比
                        
                        # 2. 计算股票下跌概率 - 近10日中下跌的天数比例
                        down_days = sum(1 for r in returns if r < 0)
                        stock_data['down_probability'] = down_days / len(returns) if len(returns) > 0 else 0.5
                        
                        # 3. 计算最大回撤
                        cumulative = (1 + returns).cumprod()
                        max_return = cumulative.cummax()
                        drawdown = (cumulative / max_return - 1) * 100
                        stock_data['max_drawdown'] = abs(drawdown.min())
                        
                        # 4. 计算成交量稳定性 - 用于评估是否存在异常放量
                        volume_data = prices[stock]['volume']
                        volume_mean = volume_data.mean()
                        volume_std = volume_data.std()
                        stock_data['volume_stability'] = volume_std / volume_mean if volume_mean > 0 else 999
                        
                        # 5. 计算价格支撑强度 - 用于评估下方支撑
                        lows = prices[stock]['low']
                        # 计算近5日最低价的支撑线
                        support_level = lows[-5:].min()
                        current_price = close_prices.iloc[-1]
                        # 计算当前价格距离支撑线的距离百分比
                        stock_data['support_strength'] = (current_price / support_level - 1) * 100
                        
                        # 6. 计算主力控盘程度 - 用于评估主力意图
                        if 'big_order_ratio' in stock_data:
                            big_ratio_5d = stock_data['big_order_ratio']
                            # 计算大单比例变化趋势
                            stock_data['big_order_trend'] = big_ratio_5d - stock_data.get('big_order_ratio_prev', 0)
                        else:
                            stock_data['big_order_trend'] = 0
                        
                        # 7. 计算涨停封板强度 - 用于评估涨停质量
                        if stock_data['limit_up_count'] > 0:
                            # 获取当日分时数据(如果可用)
                            try:
                                minute_data = get_price(stock, 
                                                      count=240,  # 一个交易日约240分钟
                                                      frequency='1m',
                                                      end_date=context.current_dt,
                                                      fields=['close'])
                                
                                # 计算涨停时间占比
                                high_limit = current_data[stock].high_limit
                                limit_up_minutes = sum(1 for p in minute_data['close'] 
                                                    if p >= high_limit * 0.99)
                                stock_data['limit_up_strength'] = limit_up_minutes / len(minute_data) * 100
                            except:
                                # 如果无法获取分时数据，使用收盘价与涨停价的接近程度评估
                                high_limit = current_data[stock].high_limit
                                stock_data['limit_up_strength'] = (close_prices.iloc[-1] / high_limit) * 100
                        else:
                            stock_data['limit_up_strength'] = 0
                        
                        # 8. 计算开盘资金博弈强度 - 用于评估早盘资金意图
                        open_price = prices[stock]['open'].iloc[-1]
                        prev_close = close_prices.iloc[-2]
                        stock_data['open_strength'] = (open_price / prev_close - 1) * 100
                        
                    except Exception as e:
                        log.error(f"计算股票 {stock} 风险指标时出错: {str(e)}")
                        # 设置默认风险值
                        stock_data['volatility'] = 5.0  # 默认中等波动率
                        stock_data['down_probability'] = 0.5  # 默认50%下跌概率
                        stock_data['max_drawdown'] = 10.0  # 默认10%最大回撤
                        stock_data['volume_stability'] = 1.0  # 默认中等稳定性
                        stock_data['support_strength'] = 5.0  # 默认中等支撑强度
                        stock_data['big_order_trend'] = 0  # 默认无变化
                        stock_data['limit_up_strength'] = 0  # 默认无涨停强度
                        stock_data['open_strength'] = 0  # 默认无开盘强度
                    
                    # 计算市场热度和人气指标
                    try:
                        # 1. 计算换手率 - 衡量交易活跃度
                        turnover_rate = get_fundamentals(query(
                            valuation.code, valuation.turnover_ratio
                        ).filter(valuation.code == stock), date=context.current_dt)
                        
                        if not turnover_rate.empty:
                            stock_data['turnover_rate'] = turnover_rate['turnover_ratio'][0]
                            
                            # 获取历史换手率数据
                            hist_turnover = get_fundamentals(query(
                                valuation.code, valuation.turnover_ratio
                            ).filter(valuation.code == stock), 
                            date=context.current_dt - datetime.timedelta(days=5))
                            
                            if not hist_turnover.empty:
                                stock_data['turnover_ratio'] = stock_data['turnover_rate'] / hist_turnover['turnover_ratio'][0]
                            else:
                                stock_data['turnover_ratio'] = 1.0
                        else:
                            stock_data['turnover_rate'] = 0
                            stock_data['turnover_ratio'] = 1.0
                        
                        # 2. 计算人气指标 - 基于分时成交量变化
                        try:
                            # 获取当日分时数据
                            minute_data = get_price(stock, 
                                                  count=240,  # 一个交易日约240分钟
                                                  frequency='1m',
                                                  end_date=context.current_dt,
                                                  fields=['volume', 'money'])
                            
                            if not minute_data.empty:
                                # 计算分时成交量变化趋势
                                volumes = minute_data['volume']
                                
                                # 将交易日分为四个时段，计算各时段成交量占比
                                morning_early = volumes[:60].sum()  # 9:30-10:30
                                morning_late = volumes[60:120].sum()  # 10:30-11:30
                                afternoon_early = volumes[120:180].sum()  # 13:00-14:00
                                afternoon_late = volumes[180:].sum()  # 14:00-15:00
                                
                                total_volume = volumes.sum()
                                if total_volume > 0:
                                    # 计算尾盘成交量占比 - 尾盘放量通常意味着热度高
                                    stock_data['late_volume_ratio'] = afternoon_late / total_volume
                                    
                                    # 计算成交量增长趋势 - 持续放量意味着人气上升
                                    first_half = morning_early + morning_late
                                    second_half = afternoon_early + afternoon_late
                                    stock_data['volume_trend'] = second_half / first_half if first_half > 0 else 1.0
                                    
                                    # 计算分时成交量波动 - 波动大意味着博弈激烈，人气高
                                    stock_data['volume_volatility'] = volumes.std() / volumes.mean() if volumes.mean() > 0 else 0
                                else:
                                    stock_data['late_volume_ratio'] = 0
                                    stock_data['volume_trend'] = 1.0
                                    stock_data['volume_volatility'] = 0
                            else:
                                stock_data['late_volume_ratio'] = 0
                                stock_data['volume_trend'] = 1.0
                                stock_data['volume_volatility'] = 0
                        except:
                            stock_data['late_volume_ratio'] = 0
                            stock_data['volume_trend'] = 1.0
                            stock_data['volume_volatility'] = 0
                        
                        # 3. 计算市场关注度 - 基于龙虎榜数据(如果可用)
                        try:
                            # 获取龙虎榜数据
                            tops_list = get_billboard_list(stock_list=[stock], 
                                                         start_date=context.current_dt - datetime.timedelta(days=10),
                                                         end_date=context.current_dt)
                            
                            if not tops_list.empty:
                                # 计算近期上榜次数
                                stock_data['tops_list_count'] = len(tops_list)
                                
                                # 计算近期净买入金额
                                stock_data['tops_list_net_amount'] = tops_list['net_amount'].sum()
                                
                                # 计算近期买入席位数
                                stock_data['tops_list_buy_seats'] = tops_list['buy_seat_count'].sum()
                            else:
                                stock_data['tops_list_count'] = 0
                                stock_data['tops_list_net_amount'] = 0
                                stock_data['tops_list_buy_seats'] = 0
                        except:
                            stock_data['tops_list_count'] = 0
                            stock_data['tops_list_net_amount'] = 0
                            stock_data['tops_list_buy_seats'] = 0
                        
                        # 4. 计算市场热点关联度 - 与当日热门概念的关联程度
                        try:
                            # 获取股票所属的所有概念
                            stock_concepts = get_concept(stock)
                            
                            if stock_concepts:
                                # 计算与热门概念的重合数
                                hot_concept_count = sum(1 for c in stock_concepts if c in hot_concepts['code'].values)
                                stock_data['hot_concept_count'] = hot_concept_count
                                
                                # 计算热点关联度
                                stock_data['hot_concept_ratio'] = hot_concept_count / len(stock_concepts) if len(stock_concepts) > 0 else 0
                            else:
                                stock_data['hot_concept_count'] = 0
                                stock_data['hot_concept_ratio'] = 0
                        except:
                            stock_data['hot_concept_count'] = 0
                            stock_data['hot_concept_ratio'] = 0
                        
                        # 5. 计算市场情绪指标 - 基于大单成交和委托数据
                        try:
                            # 计算大单净流入占比
                            if 'main_money_net_inflow' in stock_data and stock_data['money_ratio'] > 0:
                                stock_data['main_money_ratio'] = stock_data['main_money_net_inflow'] / stock_data['money_ratio']
                            else:
                                stock_data['main_money_ratio'] = 0
                            
                            # 计算市场情绪得分
                            stock_data['market_sentiment'] = (
                                (stock_data['turnover_rate'] > 15) * 1 +  # 高换手
                                (stock_data['turnover_ratio'] > 2) * 1 +  # 换手率上升
                                (stock_data['late_volume_ratio'] > 0.3) * 1 +  # 尾盘放量
                                (stock_data['volume_trend'] > 1.2) * 1 +  # 成交量上升趋势
                                (stock_data['volume_volatility'] > 1.5) * 1 +  # 成交量波动大
                                (stock_data['tops_list_count'] > 0) * 1 +  # 上榜龙虎榜
                                (stock_data['tops_list_net_amount'] > 0) * 1 +  # 龙虎榜净买入
                                (stock_data['hot_concept_count'] > 0) * 1 +  # 热门概念关联
                                (stock_data['main_money_ratio'] > 0) * 1  # 主力资金净流入
                            )
                        except:
                            stock_data['market_sentiment'] = 0
                        
                    except Exception as e:
                        log.error(f"计算股票 {stock} 市场热度指标时出错: {str(e)}")
                        # 设置默认值
                        stock_data['turnover_rate'] = 0
                        stock_data['turnover_ratio'] = 1.0
                        stock_data['late_volume_ratio'] = 0
                        stock_data['volume_trend'] = 1.0
                        stock_data['volume_volatility'] = 0
                        stock_data['tops_list_count'] = 0
                        stock_data['tops_list_net_amount'] = 0
                        stock_data['tops_list_buy_seats'] = 0
                        stock_data['hot_concept_count'] = 0
                        stock_data['hot_concept_ratio'] = 0
                        stock_data['main_money_ratio'] = 0
                        stock_data['market_sentiment'] = 0
                    
                    # 重新设计强度得分计算 - 增加市场热度和人气因素
                    stock_data['strength_score'] = (
                        # 1. 首板得分 - 极高优先级
                        (stock_data['limit_up_count'] == 1) * 3000 +   # 首板基础分极大提高
                        (stock_data['limit_up_count'] > 1) * 1000 +    # 连板降低权重
                        
                        # 2. 强势股得分 - 极端大涨股
                        (stock_data['rise_1d'] > 9.5) * 1500 +         # 涨停附近极大加分
                        (stock_data['rise_1d'] > 7) * 800 +            # 大涨加分大幅提高
                        (stock_data['rise_1d'] > 5) * 400 +            # 中等涨幅也加分
                        (stock_data['rise_3d'] > 20) * 600 +           # 3日大涨加分
                        (stock_data['rise_5d'] > 30) * 400 +           # 5日大涨加分
                        
                        # 3. 量能得分 - 超级爆量股
                        (stock_data['volume_ratio'] > 15) * 1200 +     # 超级特大量
                        (stock_data['volume_ratio'] > 10) * 800 +      # 特大量
                        (stock_data['volume_ratio'] > 5) * 500 +       # 大量
                        (stock_data['volume_ratio'] > 3) * 300 +       # 明显放量
                        (stock_data['money_ratio'] > 15) * 1000 +      # 资金超级特大量
                        (stock_data['money_ratio'] > 10) * 700 +       # 资金特大量
                        (stock_data['money_ratio'] > 5) * 400 +        # 资金大量
                        
                        # 4. 风险控制得分 - 低风险高得分
                        (stock_data['volatility'] < 3) * 1000 +        # 低波动率
                        (stock_data['down_probability'] < 0.3) * 1200 + # 低下跌概率
                        (stock_data['max_drawdown'] < 5) * 800 +       # 低回撤
                        (stock_data['volume_stability'] < 0.8) * 600 + # 成交量稳定
                        (stock_data['support_strength'] < 5) * 800 +   # 强支撑
                        (stock_data['big_order_trend'] > 0) * 1000 +   # 大单比例上升
                        (stock_data['limit_up_strength'] > 80) * 1500 + # 涨停强度高
                        (stock_data['open_strength'] > 2) * 800 +      # 开盘强度高
                        
                        # 5. 市场热度得分 - 新增
                        (stock_data['turnover_rate'] > 20) * 2000 +    # 超高换手
                        (stock_data['turnover_rate'] > 15) * 1500 +    # 高换手
                        (stock_data['turnover_rate'] > 10) * 1000 +    # 中等换手
                        (stock_data['turnover_ratio'] > 3) * 1500 +    # 换手率大幅上升
                        (stock_data['turnover_ratio'] > 2) * 1000 +    # 换手率明显上升
                        (stock_data['late_volume_ratio'] > 0.4) * 1200 + # 尾盘特大放量
                        (stock_data['late_volume_ratio'] > 0.3) * 800 + # 尾盘大放量
                        (stock_data['volume_trend'] > 1.5) * 1500 +    # 成交量大幅上升趋势
                        (stock_data['volume_trend'] > 1.2) * 1000 +    # 成交量上升趋势
                        (stock_data['volume_volatility'] > 2) * 1200 + # 成交量波动极大
                        (stock_data['volume_volatility'] > 1.5) * 800 + # 成交量波动大
                        
                        # 6. 市场关注度得分 - 新增
                        (stock_data['tops_list_count'] > 2) * 2000 +   # 多次上榜
                        (stock_data['tops_list_count'] > 0) * 1200 +   # 上榜龙虎榜
                        (stock_data['tops_list_net_amount'] > 10000000) * 1500 + # 大额净买入
                        (stock_data['tops_list_net_amount'] > 0) * 800 + # 净买入
                        (stock_data['tops_list_buy_seats'] > 3) * 1200 + # 多个买入席位
                        (stock_data['hot_concept_count'] > 2) * 1500 + # 多个热门概念
                        (stock_data['hot_concept_count'] > 0) * 800 +  # 热门概念
                        (stock_data['hot_concept_ratio'] > 0.5) * 1200 + # 高热点关联度
                        (stock_data['market_sentiment'] >= 7) * 2000 + # 市场情绪极高
                        (stock_data['market_sentiment'] >= 5) * 1200 + # 市场情绪高
                        (stock_data['market_sentiment'] >= 3) * 600    # 市场情绪中等
                    )
                    
                    # 重新设计综合排名分数 - 增加市场热度和人气因素权重
                    stock_data['rank_score'] = (
                        # 1. 基础得分
                        (stock_data['limit_up_count'] == 1) * 5000 +   # 首板权重
                        (stock_data['limit_up_count'] > 1) * 1000 +    # 连板权重
                        stock_data['rise_1d'] * 100.0 +                # 当日涨幅权重
                        stock_data['strength_score'] * 5.0 +           # 强度得分权重
                        (stock_data['volume_ratio'] > 10) * 1000 +     # 特大量权重
                        (stock_data['volume_ratio'] > 5) * 600 +       # 明显放量权重
                        stock_data['new_high'] * 1200 +                # 创新高权重
                        stock_data['continuous_up_days'] * 200 +       # 连续上涨权重
                        
                        # 2. 市场热度和人气得分 - 新增高权重
                        (stock_data['turnover_rate'] > 20) * 3000 +    # 超高换手权重
                        (stock_data['turnover_rate'] > 15) * 2000 +    # 高换手权重
                        (stock_data['turnover_ratio'] > 3) * 2500 +    # 换手率大幅上升权重
                        (stock_data['late_volume_ratio'] > 0.4) * 2000 + # 尾盘特大放量权重
                        (stock_data['volume_trend'] > 1.5) * 2500 +    # 成交量大幅上升趋势权重
                        (stock_data['volume_volatility'] > 2) * 2000 + # 成交量波动极大权重
                        (stock_data['tops_list_count'] > 2) * 3000 +   # 多次上榜权重
                        (stock_data['tops_list_net_amount'] > 10000000) * 2500 + # 大额净买入权重
                        (stock_data['hot_concept_count'] > 2) * 2500 + # 多个热门概念权重
                        (stock_data['market_sentiment'] >= 7) * 3000   # 市场情绪极高权重
                    )
                    
                    # 额外的强势特征加分 - 聚焦市场热点和人气股
                    # 1. 首板溢价 - 结合市场热度
                    if stock_data['limit_up_count'] == 1:
                        # 高人气首板
                        if stock_data['market_sentiment'] >= 7 and stock_data['turnover_rate'] > 15:
                            stock_data['rank_score'] *= 25.0           # 高人气首板翻25倍
                        else:
                            stock_data['rank_score'] *= 15.0           # 普通首板翻15倍
                    elif stock_data['limit_up_count'] > 1:
                        stock_data['rank_score'] *= 5.0                # 连板溢价
                    
                    # 2. 强势组合特征溢价 - 结合市场热度
                    # 放量新高 - 结合市场热度
                    if stock_data['new_high'] and stock_data['volume_ratio'] > 10:
                        # 高人气放量新高
                        if stock_data['market_sentiment'] >= 5 and stock_data['turnover_rate'] > 10:
                            stock_data['rank_score'] *= 20.0           # 高人气特大量新高翻20倍
                        else:
                            stock_data['rank_score'] *= 10.0           # 普通特大量新高翻10倍
                    elif stock_data['new_high'] and stock_data['volume_ratio'] > 5:
                        stock_data['rank_score'] *= 6.0                # 大量新高翻6倍
                    
                    # 3. 市场热点溢价 - 新增
                    # 龙虎榜活跃股
                    if stock_data['tops_list_count'] > 2 and stock_data['tops_list_net_amount'] > 0:
                        stock_data['rank_score'] *= 15.0               # 多次上榜且净买入翻15倍
                    elif stock_data['tops_list_count'] > 0 and stock_data['tops_list_net_amount'] > 0:
                        stock_data['rank_score'] *= 8.0                # 上榜且净买入翻8倍
                    
                    # 热门概念关联股
                    if stock_data['hot_concept_count'] > 2 and stock_data['hot_concept_ratio'] > 0.5:
                        stock_data['rank_score'] *= 12.0               # 多个热门概念且关联度高翻12倍
                    elif stock_data['hot_concept_count'] > 0 and stock_data['hot_concept_ratio'] > 0.3:
                        stock_data['rank_score'] *= 6.0                # 热门概念且关联度中等翻6倍
                    
                    # 市场情绪极高股
                    if stock_data['market_sentiment'] >= 7:
                        stock_data['rank_score'] *= 18.0               # 市场情绪极高翻18倍
                    elif stock_data['market_sentiment'] >= 5:
                        stock_data['rank_score'] *= 10.0               # 市场情绪高翻10倍
                    
                    # 4. 超级人气组合 - 新增
                    # 高换手+大涨+放量
                    if stock_data['turnover_rate'] > 15 and stock_data['rise_1d'] > 7 and stock_data['volume_ratio'] > 10:
                        stock_data['rank_score'] *= 20.0               # 超级人气组合翻20倍
                    
                    # 龙虎榜+热门概念+市场情绪高
                    if stock_data['tops_list_count'] > 0 and stock_data['hot_concept_count'] > 0 and stock_data['market_sentiment'] >= 5:
                        stock_data['rank_score'] *= 25.0               # 全方位人气组合翻25倍
                    
                    # 5. 终极人气王 - 新增
                    # 首板+高换手+龙虎榜+热门概念+市场情绪极高
                    if (stock_data['limit_up_count'] == 1 and 
                        stock_data['turnover_rate'] > 15 and 
                        stock_data['tops_list_count'] > 0 and 
                        stock_data['hot_concept_count'] > 0 and 
                        stock_data['market_sentiment'] >= 7):
                        stock_data['rank_score'] *= 50.0               # 终极人气王翻50倍
                    
                    # 6. 风险控制 - 适当降权
                    # 近期累计涨幅过高的适当降权，避免追高
                    if stock_data['rise_5d'] > 60:                     # 5日涨幅超60%
                        stock_data['rank_score'] *= 0.5                # 降权50%
                    elif stock_data['rise_5d'] > 50:                   # 5日涨幅超50%
                        stock_data['rank_score'] *= 0.7                # 降权30%
                    
                    # 高风险股票降权
                    risk_score = (
                        (stock_data['volatility'] > 5) * 1 +           # 高波动率
                        (stock_data['down_probability'] > 0.5) * 1 +   # 高下跌概率
                        (stock_data['max_drawdown'] > 10) * 1 +        # 高回撤
                        (stock_data['volume_stability'] > 1.2) * 1 +   # 成交量不稳定
                        (stock_data['support_strength'] > 8) * 1 +     # 支撑弱
                        (stock_data['big_order_trend'] < 0) * 1        # 大单比例下降
                    )
                    
                    # 根据风险得分降权
                    if risk_score >= 4:                                # 极高风险
                        stock_data['rank_score'] *= 0.1                # 降权90%
                    elif risk_score >= 3:                              # 高风险
                        stock_data['rank_score'] *= 0.3                # 降权70%
                    
                    stock_scores.append(stock_data)
                    all_stock_scores.append(stock_data)  # 添加到全局列表
                    
                except Exception as e:
                    log.error(f"处理个股 {stock} 时出错: {str(e)}")
                    continue
            
            if stock_scores:
                # 转换为DataFrame并排序
                df_scores = pd.DataFrame(stock_scores)
                df_scores = df_scores.sort_values(
                    ['rank_score', 'strength_score', 'limit_up_count', 'rise_1d'], 
                    ascending=[False, False, False, False]
                )
                
                # 输出选股结果
                log.info(f"\n============== {concept['name']} 板块个股排名 ==============")
                log.info(f"{'股票代码':<10} {'股票名称':<8} {'日涨幅':>7} {'涨停数':>6} {'量比':>6} "
                        f"{'连板':>4} {'新高':>4} {'强度分':>6} {'综合分':>6}")
                log.info("-" * 75)
                
                for _, row in df_scores.head(2).iterrows():
                    # 获取股票名称
                    stock_name = get_security_info(row['code']).display_name
                    log.info(f"{row['code']:<10} {stock_name[:8]:<8} {row['rise_1d']:>6.2f}% {row['limit_up_count']:>6.0f} "
                            f"{row['volume_ratio']:>6.2f} {row['continuous_up_days']:>4.0f} "
                            f"{row['new_high']:>4.0f} {row['strength_score']:>5.0f} "
                            f"{row['rank_score']:>5.1f}")
                    selected_stocks.append(row['code'])
                
                log.info("=" * 75 + "\n")
                
        except Exception as e:
            log.error(f"处理板块 {concept['name']} 时出错: {str(e)}")
            continue
    
    # 全局最强股票排名 - 跨板块比较
    if all_stock_scores:
        df_all = pd.DataFrame(all_stock_scores)
        df_all = df_all.sort_values(
            ['rank_score', 'strength_score', 'limit_up_count', 'rise_1d'], 
            ascending=[False, False, False, False]
        )
        
        # 去除重复股票
        df_all = df_all.drop_duplicates(subset=['code'])
        
        log.info("\n=============== 全市场最强股票排名 ===============")
        log.info(f"{'股票代码':<10} {'股票名称':<8} {'板块':>12} {'日涨幅':>7} {'涨停数':>6} {'量比':>6} "
                f"{'连板':>4} {'新高':>4} {'强度分':>6} {'综合分':>6}")
        log.info("-" * 85)
        
        # 输出全局最强股票
        global_top_stocks = []
        for _, row in df_all.head(g.stock_num * 2).iterrows():
            # 获取股票名称
            stock_name = get_security_info(row['code']).display_name
            log.info(f"{row['code']:<10} {stock_name[:8]:<8} {row['concept'][:10]:>12} {row['rise_1d']:>6.2f}% {row['limit_up_count']:>6.0f} "
                    f"{row['volume_ratio']:>6.2f} {row['continuous_up_days']:>4.0f} "
                    f"{row['new_high']:>4.0f} {row['strength_score']:>5.0f} "
                    f"{row['rank_score']:>5.1f}")
            global_top_stocks.append(row['code'])
        
        log.info("=" * 85 + "\n")
        
        # 优先选择全局最强股票
        final_stocks = global_top_stocks[:g.stock_num]
        return final_stocks
    
    # 如果没有全局排名，则返回板块内排名的股票
    return sorted(list(set(selected_stocks)))[:g.stock_num]

# 4. 交易执行
def market_open(context):
    """开盘时执行的逻辑"""
    # 获取当前最强概念板块
    hot_concepts = analyze_concepts(context)
    if hot_concepts.empty:
        return
    
    # 获取推荐股票
    recommended_stocks = select_stocks(context, hot_concepts)
    if not recommended_stocks:
        return
    
    # 获取当前持仓
    current_positions = list(context.portfolio.positions.keys())
    
    # 计算需要调仓的股票
    stocks_to_sell = [stock for stock in current_positions if stock not in recommended_stocks]
    stocks_to_buy = [stock for stock in recommended_stocks if stock not in current_positions]
    
    # 执行卖出操作
    for stock in stocks_to_sell:
        position = context.portfolio.positions[stock]
        # 检查最小持有天数
        hold_days = (context.current_dt.date() - position.init_time.date()).days
        if hold_days < g.min_hold_days:
            continue
            
        # 检查是否可以交易
        current_data = get_current_data()
        if current_data[stock].paused:
            continue
            
        # 检查涨跌停
        if current_data[stock].low_limit >= current_data[stock].high_limit:
            continue
            
        # 执行卖出
        order_target_value(stock, 0)
    
    # 修改这里：计算每只股票的目标持仓价值
    # 平均分配资金给所有推荐股票
    total_value = context.portfolio.total_value  # 使用总资产而不是可用现金
    position_value = total_value / g.stock_num   # 平均分配给g.stock_num只股票
    
    # 执行买入操作
    available_cash = context.portfolio.available_cash
    
    for stock in stocks_to_buy:
        # 检查是否还有足够的现金
        if available_cash < position_value * 0.9:  # 留一些余量
            break
            
        current_data = get_current_data()
        if current_data[stock].paused:
            continue
            
        # 检查涨跌停
        if current_data[stock].low_limit >= current_data[stock].high_limit:
            continue
            
        # 获取当前价格
        price = current_data[stock].day_open
        if price > 0:
            # 计算买入数量
            amount = int(position_value / price / 100) * 100
            if amount > 0:
                order_value(stock, position_value)
                available_cash -= position_value

def market_close(context):
    """收盘前执行的逻辑"""
    # 输出当日持仓及收益情况
    positions = context.portfolio.positions
    if positions:
        log.info("\n=============== 当日持仓汇总 ===============")
        log.info(f"{'股票代码':<12} {'股票名称':<8} {'持仓天数':>8} {'持仓收益':>8} {'当日涨幅':>8}")
        log.info("-" * 58)
        
        for stock in positions:
            position = positions[stock]
            hold_days = (context.current_dt.date() - position.init_time.date()).days
            profit_pct = (position.price / position.avg_cost - 1) * 100
            today_pct = (position.price / position.last_sale_price - 1) * 100
            
            # 获取股票名称
            stock_name = get_security_info(stock).display_name
            
            log.info(f"{stock:<12} {stock_name[:8]:<8} {hold_days:>8d} {profit_pct:>8.2f}% {today_pct:>8.2f}%")
        
        log.info("=" * 58)
        
    # 输出当日收益汇总
    portfolio = context.portfolio
    daily_returns = (portfolio.total_value / portfolio.starting_cash - 1) * 100
    log.info(f"\n当日收益率: {daily_returns:.2f}%")
    log.info(f"当前总市值: {portfolio.total_value:.2f}")
    log.info(f"当前现金: {portfolio.available_cash:.2f}")
