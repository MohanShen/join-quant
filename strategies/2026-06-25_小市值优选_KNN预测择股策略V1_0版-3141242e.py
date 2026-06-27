# Clone from JoinQuant
# postId: 3141242edf50e5f3d037e904781fc979
# backtestId: cce58ae31335dd82285709edc8ebb174
# title: 小市值优选+KNN预测择股策略V1.0版

# 聚宽KNN自动选股交易策略
# 功能：小市值优选+KNN预测择股策略
import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import accuracy_score
from datetime import datetime, timedelta

# ===================== 【策略参数】可自行调整 =====================
def initialize(context):
    # 只保留 error 级别的下单日志，info/warning 都不显示
    log.set_level('order', 'error')
    # 1. 基础设置
    set_benchmark('000300.XSHG')        # 对标沪深300
    set_option('use_real_price', True)  # 实盘价格
    set_slippage(FixedSlippage(0.002), type="stock")
    set_slippage(FixedSlippage(0.001), type="fund")
    cost_configs = [
        ("stock", 0.0005, 0.85 / 10000, 5),
        ("fund", 0, 0.5 / 10000, 5),
        ("mmf", 0, 0, 0)
    ]
    for asset_type, close_tax, commission, min_comm in cost_configs:
        set_order_cost(OrderCost(
            open_tax=0, close_tax=close_tax,
            open_commission=commission, close_commission=commission,
            close_today_commission=0, min_commission=min_comm
        ), type=asset_type)
    
    # 2. 策略核心参数
    g.train_days = 300    # 训练样本天数（扩大训练集，更准确）
    g.hold_num = 5        # 持仓数量
    g.top_n = 20          # 初选股票池（避免全市场计算过慢）
    g.min_accuracy = 0.53 # 模型最低准确率阈值（低于则空仓）
    g.starting_cash = context.portfolio.total_value #启动资金
    
    # 3. 止盈止损参数
    g.stop_loss = 0.08    # 止损线：亏损8%
    g.stop_profit = 0.15  # 止盈线：盈利15%
    g.trade_interval = 3  # 每3天执行一次选股调仓
    g.last_trade_day = None  # 上次交易日期（用于计数）

    g.knn_model = None  #KNN模型
    g.knn_accuracy = 0  #KNN模型准确率
    
    # 5. 每日运行：止盈止损 + 持仓日志
    run_daily(daily_check, time='09:35')
    # 6. 每3天运行一次选股调仓
    run_daily(market_trade, time='09:40')

# ===================== 【特征工程】核心+进阶特征 =====================
def get_features(df):
    """计算所有特征：基础+技术指标+进阶特征"""
    # 1. 基础特征
    df['pct_change'] = df['close'].pct_change()
    df['vol_change'] = df['volume'].pct_change()
    df['amt_change'] = df['money'].pct_change()

    # 2. 均线特征
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma10'] = df['close'].rolling(10).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma5_ratio'] = df['close'] / df['ma5']
    df['ma10_ratio'] = df['close'] / df['ma10']
    df['ma20_ratio'] = df['close'] / df['ma20']

    # 3. RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 4. MACD
    df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()

    # 5. KDJ
    low9 = df['low'].rolling(9).min()
    high9 = df['high'].rolling(9).max()
    df['k'] = (df['close'] - low9) / (high9 - low9) * 100
    df['d'] = df['k'].rolling(3).mean()

    # 6. 布林带（进阶）
    df['bb_mid'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_up'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_down'] = df['bb_mid'] - 2 * df['bb_std']
    df['bb_pos'] = (df['close'] - df['bb_down']) / (df['bb_up'] - df['bb_down'])

    # 7. 波动率（进阶）
    df['vol_5'] = df['close'].pct_change().rolling(5).std()

    # 8. 量价特征（进阶）
    df['vol_ma5'] = df['volume'].rolling(5).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma5']

    # 最终特征列表
    feature_cols = [
        'pct_change','vol_change','amt_change',
        'ma5_ratio','ma10_ratio','ma20_ratio',
        'rsi','macd','signal','k','d',
        'bb_pos','vol_5','vol_ratio'
    ]
    
    return df, feature_cols

# ===================== 【涨停基因筛选】 =====================
def get_limit_up_stocks(context, stock_list, d=200):
    """筛选近N个交易日有涨停基因的股票（单日涨幅超过8%）"""
    if not stock_list:
        return []
    end_date = context.current_dt.date()
    start_date = end_date - timedelta(days=d)
    try:
        df = get_price(stock_list, start_date=start_date, end_date=end_date,
                       frequency='daily', fields=['close'], panel=False, fill_paused=False)
        # 计算单日涨幅
        df['pct'] = df.groupby('code')['close'].pct_change()
        # 涨幅超过8%
        limit_df = df[df['pct'] > 0.08]
        limit_stocks = limit_df['code'].unique().tolist()
        return limit_stocks
    except:
        return []

# ===================== 【全局KNN模型初始化】只运行一次 =====================
def init_global_knn(context):
    if g.knn_model is not None:
        return
    """用近200日有涨停基因的100只小市值股票训练全局KNN模型"""
    try:
        end_date = context.current_dt.date()
        log.info(f'当前日期：{end_date}')
        # 1. 获取全市场股票并基础过滤
        all_stocks = get_all_securities(['stock'], date=end_date).index.tolist()
        log.info(f'所有股票数{len(all_stocks)}')
        valid_stocks = filter_stocks(all_stocks, end_date)
        log.info(f'过滤后股票数{len(valid_stocks)}')
        # 2. 筛选近200日有涨停基因的股票
        limit_stocks = get_limit_up_stocks(context, valid_stocks, d=g.train_days)
        log.info(f'筛选近200日有涨停基因的股票数{len(limit_stocks)}')
        if len(limit_stocks) < 50:
            log.warning(f'有涨停基因的股票数量{len(limit_stocks)}不足， fallback到沪深300训练')
            limit_stocks = ['000300.XSHG']

        # 3. 按市值排序取最小的100只
        q = query(valuation.code, valuation.market_cap).filter(
            valuation.code.in_(limit_stocks)
        ).order_by(valuation.market_cap.asc()).limit(100)
        cap_df = get_fundamentals(q, date=end_date)
        train_stocks = cap_df['code'].tolist()

        if len(train_stocks) < 10:
            log.warning(f'小市值涨停基因股票数{len(train_stocks)}不足，fallback到沪深300训练')
            train_stocks = ['000300.XSHG']

        log.info(f'全局KNN训练股票池：共{len(train_stocks)}只，近{g.train_days}日有涨停基因的小市值股票')

        # 4. 批量获取数据并拼接训练集
        all_X = []
        all_y = []
        feature_cols = None
        for stock in train_stocks:
            try:
                df = get_price(stock, count=g.train_days, end_date=end_date,
                               frequency='daily', fields=['open','high','low','close','volume','money'], fq='pre')
                if len(df) < 200:
                    continue
                df['label'] = np.where(df['close'].shift(-1) > df['close'], 1, 0)
                df = df.iloc[:-1]
                df, cols = get_features(df)
                feature_cols = cols
                model_df = df[feature_cols + ['label']].dropna()
                if len(model_df) < 50:
                    continue
                all_X.append(model_df[feature_cols])
                all_y.append(model_df['label'])
            except:
                continue

        if len(all_X) == 0:
            log.warning('没有足够数据训练全局模型')
            g.knn_model = None
            g.knn_scaler = None
            g.knn_accuracy = 0
            return

        X = pd.concat(all_X, ignore_index=True)
        y = pd.concat(all_y, ignore_index=True)

        # 清理NaN和无穷大值
        X = X.replace([np.inf, -np.inf], np.nan).dropna()
        y = y.loc[X.index]

        if len(X) < 250:
            log.warning('有效训练样本不足，无法训练全局模型')
            g.knn_model = None
            g.knn_scaler = None
            g.knn_accuracy = 0
            return

        # 5. 训练模型
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        split = int(len(X_scaled) * 0.85)
        X_train, X_test = X_scaled[:split], X_scaled[split:]
        y_train, y_test = y[:split], y[split:]

        knn = KNeighborsClassifier()
        params = {'n_neighbors': [3,5,7,9,11,13,15]}
        grid = GridSearchCV(knn, params, cv=5)
        grid.fit(X_train, y_train)
        best_model = grid.best_estimator_

        y_pred = best_model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)

        g.knn_model = best_model
        g.knn_scaler = scaler
        g.knn_accuracy = acc
        g.knn_feature_cols = feature_cols

        log.info(f'全局KNN模型初始化完成 | 训练样本={len(X)} | 最优K={best_model.n_neighbors} | 测试集准确率={acc:.2%}')

    except Exception as e:
        log.error(f'全局KNN模型初始化失败: {e}')
        g.knn_model = None
        g.knn_scaler = None
        g.knn_accuracy = 0

# ===================== 【单只股票预测】使用全局模型 =====================
def predict_stock(stock, context):
    """使用全局KNN模型预测单只股票上涨概率"""
    if g.knn_model is None or g.knn_scaler is None:
        log.warning('全局KNN模型未初始化，无法预测')
        return 0, 0

    try:
        # 1. 获取数据
        end_date = context.current_dt- timedelta(days=1)
        df = get_price(
            stock, count=50, end_date=end_date,
            frequency='daily', fields=['open','high','low','close','volume','money'], fq='pre'
        )
        # 2. 计算特征（不需要标签，只做预测）
        df, feature_cols = get_features(df)
        model_df = df[feature_cols].dropna()
        if len(model_df) < 1:
            log.info(f'股票{stock}特征计算失败，model_df不足长度')
            return 0, 0

        # 3. 使用全局scaler和模型预测
        X = model_df[feature_cols]
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        prob = g.knn_model.predict_proba(X_scaled)[0][1]

        # 返回上涨概率和全局模型准确率
        return prob, g.knn_accuracy

    except Exception as e:
        log.error(f'预测股票{stock}上涨概率失败: {e}')
        return 0, 0
        
#  基础过滤各种股票
def filter_stocks(stock_list, end_date=None):
    current_data = get_current_data()
    log.info(f'原始股票数 {len(stock_list)}')
    
    if end_date is None:
        end_date = context.current_dt.date()

    # ========== 新增：统计每个条件过滤数量 ==========
    count_paused_st = 0       # 停牌 + ST
    count_delisting = 0       # 退市
    count_block = 0           # 板块（30/68/8/4）
    count_ipo_days = 0        # 上市不足200天
    valid_stocks = []
    # ==============================================

    for s in stock_list:
        # 条件1：停牌 或 ST
        if current_data[s].paused or current_data[s].is_st:
            count_paused_st += 1
            continue

        # 条件2：退市
        if '退' in current_data[s].name:
            count_delisting += 1
            continue

        # 条件3：板块过滤（你原来的致命条件）
        if s.startswith('30') or s.startswith('68') or s.startswith('8') or s.startswith('4'):
            count_block += 1
            continue

        # 条件4：上市不足200天
        ipo_date = get_security_info(s).start_date
        if (end_date - ipo_date).days < 200:
            count_ipo_days += 1
            continue

        # 全部通过
        valid_stocks.append(s)

    # ========== 新增：打印详细过滤统计 ==========
    # log.info('='*20)
    # log.info(f'【过滤条件详细统计】')
    # log.info(f'停牌/ST 过滤：{count_paused_st} 只')
    # log.info(f'退市 过滤：{count_delisting} 只')
    # log.info(f'板块(30/68/8/4) 过滤：{count_block} 只')
    # log.info(f'上市不足200天 过滤：{count_ipo_days} 只')
    # log.info(f'过滤后剩余：{len(valid_stocks)} 只')
    # log.info('='*20)
    # ===========================================

    return valid_stocks

# ===================== 【每日检查：止盈止损 + 持仓日志】 =====================
def daily_check(context):
      # 初始化全局KNN模型（只用沪深300训练一次，后续复用）
    init_global_knn(context)
    """每日执行：持仓日志打印 + 止盈止损检查"""
    today_date = context.current_dt.date()
    positions = context.portfolio.positions

    # 1. 打印持仓日志
    if len(positions) > 0:
        log.info('='*30)
        log.info(f'📋 持仓日志 | 日期：{today_date} | 持仓数量：{len(positions)}')
        total_pnl = 0
        for stock, pos in positions.items():
            cost = pos.avg_cost
            price = pos.price
            pnl_ratio = (price - cost) / cost if cost > 0 else 0
            pnl_amount = (price - cost) * pos.total_amount
            total_pnl += pnl_amount
            log.info(f'   {stock} | 成本：{cost:.2f} | 现价：{price:.2f} | 收益率：{pnl_ratio:+.2%} | 盈亏：{pnl_amount:+.2f}')
        log.info(f'💰 总浮动盈亏：{total_pnl:+.2f}')
        log.info('='*30)
    else:
        log.info(f'📋 持仓日志 | 日期：{today_date} | 当前空仓')

    # 2. 止盈止损检查
    for stock, pos in list(positions.items()):
        cost = pos.avg_cost
        price = pos.price
        if cost <= 0:
            continue
        pnl_ratio = (price - cost) / cost

        if pnl_ratio <= -g.stop_loss:
            log.info(f'🛑 止损触发 | {stock} | 亏损：{pnl_ratio:.2%} | 卖出')
            order_target_value(stock, 0)
        elif pnl_ratio >= g.stop_profit:
            log.info(f'🎯 止盈触发 | {stock} | 盈利：{pnl_ratio:.2%} | 卖出')
            order_target_value(stock, 0)

# ===================== 【底部放量启动判断】 =====================
def is_bottom_breakout(stock, context):
    """判断股票是否处于底部放量启动状态
    条件：
    1. 股价处于近期低位（60日低点附近）
    2. 今日放量（成交量 > 5日均量 * 1.6）
    3. 今日上涨（收盘价 > 开盘价）
    """
    try:
        end_date = context.current_dt.date()
        df = get_price(stock, count=60, end_date=end_date,
                       frequency='daily', fields=['open','high','low','close','volume'], fq='pre')
        if len(df) < 20:
            return False

        # 条件1：股价处于60日低点附近（当前close <= 60日最低 * 1.05）
        low_60 = df['low'].min()
        current_close = df['close'].iloc[-1]
        if current_close > low_60 * 1.3:
            return False

        # 条件2：今日放量（成交量 > 5日均量 * 1.5）
        vol_ma5 = df['volume'].rolling(5).mean().iloc[-1]
        today_vol = df['volume'].iloc[-1]
        if today_vol < vol_ma5 * 1.6:
            return False

        # 条件3：今日上涨（收盘价 > 开盘价）
        today_open = df['open'].iloc[-1]
        if current_close <= today_open:
            return False

        return True
    except:
        return False

# ===================== 【全市场选股 + 调仓】 =====================
def market_trade(context):
    """每3天执行一次：选股→排序→调仓"""
    today_date = context.current_dt.date()
    current_month = today_date.month

    # 1、4月份空仓逻辑
    if current_month in [1, 4]:
        log.info(f'⚠️ {current_month}月份空仓期，清仓所有持仓')
        for stock in list(context.portfolio.positions.keys()):
            order_target_value(stock, 0)
        return

    # 判断是否需要执行（每3天一次）
    if g.last_trade_day is not None and (today_date - g.last_trade_day).days < g.trade_interval:
        return
    g.last_trade_day = today_date

    # 1. 获取全市场股票 + 基础过滤
    all_stocks = get_all_securities(['stock'], date=today_date).index.tolist()
    current_data = get_current_data()

    valid_stocks = filter_stocks(all_stocks, today_date)

    # 2. 筛选近200日有涨停基因的股票
    limit_stocks = get_limit_up_stocks(context, valid_stocks, d=200)

    # 3. 基本面筛选：pb>0 且 总营收同比增长率>0，按市值升序取前10
    q = query(
        valuation.code, valuation.market_cap,
        indicator.inc_total_revenue_year_on_year
    ).filter(
        valuation.code.in_(limit_stocks),
        valuation.pb_ratio > 0,
        indicator.inc_total_revenue_year_on_year > 0
    ).order_by(valuation.market_cap.asc())

    fund_df = get_fundamentals(q, date=today_date)
    stock_list = fund_df['code'].tolist()

    log.info(f'涨停基因+基本面筛选结果：共{len(stock_list)}只')

    # 4. 底部放量启动过滤
    breakout_stocks = []
    for stock in stock_list:
        if is_bottom_breakout(stock, context):
            breakout_stocks.append(stock)

    log.info(f'底部放量启动筛选结果：共{len(breakout_stocks)}只')

    # 5. 用KNN全局模型预测，取上涨概率最高的前5只
    target_stocks = breakout_stocks[:g.hold_num]
    #如果已有KNN模型，则使用模型预测涨跌
    if g.knn_model is not None and len(breakout_stocks) > 0:
        stock_score = []
        for stock in breakout_stocks:
            prob, acc = predict_stock(stock, context)
            if acc >= g.min_accuracy and prob > 0.5:
                stock_score.append((stock, prob, acc))

        stock_score.sort(key=lambda x: x[1], reverse=True)
        selected = stock_score[:g.hold_num]
        target_stocks = [x[0] for x in selected]

        # 6. 日志输出
        log.info(f'KNN预测上涨概率排名前{g.hold_num}只股票：')
        for i, (s, p, a) in enumerate(selected):
            log.info(f'{i+1}. {s} | 上涨概率：{p:.1%} | 模型准确率：{a:.1%}')

    # 7. 自动调仓：替换已有仓位
    # 清仓不在目标列表的股票
    for stock in list(context.portfolio.positions.keys()):
        if stock not in target_stocks:
            order_target_value(stock, 0)

    # 平均仓位买入目标股票
    if len(target_stocks) > 0:
        weight = g.starting_cash * 1.0 / len(target_stocks)
        for stock in target_stocks:
            order_target_value(stock, weight)
    else:
        log.info('⚠️ 未选中符合条件的股票，当前空仓')

# 必须保留
def handle_data(context, data):
    pass