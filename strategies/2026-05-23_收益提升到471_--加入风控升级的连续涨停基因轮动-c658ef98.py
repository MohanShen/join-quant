# Clone from JoinQuant
# postId: c658ef984ae714a7d158e7dcb4fa823c
# backtestId: 7409748aa026afc34cdff3243ea65a68
# title: 收益提升到471%--加入风控升级的连续涨停基因轮动

# 克隆自聚宽文章：https://www.joinquant.com/post/64881
# 标题：【变种小狮子】带涨停基因的股池轮动V2.2(BUGFIX)
# 作者：0xtao
# 优化版：融合机器学习风控模型 - 逻辑回归代价敏感评分
# 核心改造：
#   1. 从"750天涨停次数Top10%"改为"500天内有过2连板历史"
#   2. 剔除距离最近涨停最近的10%（避开最热、最拥挤的票）
#   3. 保留创业板（原版已过滤科创板和北交所）
#   4. ⭐新增：机器学习风控，动态调节买入仓位

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time, datetime, timedelta


# ========== 初始化函数 ==========
def initialize(context):
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 设定基准
    set_benchmark('399101.XSHE')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 将滑点设置为0
    set_slippage(PriceRelatedSlippage(0.002), type="stock")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=1,
        ),
        type="stock",
    )
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')

    # ---------- 原策略全局变量 ----------
    g.no_trading_today_signal = False
    g.pass_april = True
    g.run_stoploss = True
    g.hold_list = []
    g.yesterday_HL_list = []
    g.target_list = []
    g.not_buy_again = []
    g.filter_loss_black = True
    g.loss_black = {}
    g.stock_num = 6
    g.up_price = 20
    g.limit_days_window = 500
    g.init_stock_count = 1000
    g.reason_to_sell = ''
    g.stoploss_strategy = 3
    g.stoploss_limit = 0.91
    g.stoploss_market = 0.93
    g.HV_control = False
    g.HV_duration = 120
    g.HV_ratio = 0.9
    g.stockL = []
    g.no_trading_buy = []
    g.no_trading_hold_signal = False

    # ---------- 机器学习风控全局变量 ----------
    g.ml_weights = None            # 逻辑回归权重 (14,)
    g.ml_feature_num = 14          # 特征数量
    g.ml_window = 500              # 训练用历史数据天数
    g.ml_threshold_skip = 0.7      # 得分>0.7直接跳过
    g.ml_threshold_half = 0.5      # 得分在0.5~0.7买一半

    # ---------- 定时任务 ----------
    run_daily(prepare_stock_list, '9:05')
    run_weekly(weekly_sell, 2, '10:15')
    run_weekly(weekly_buy, 2, '10:30')
    run_daily(sell_stocks, time='10:00')
    run_daily(trade_afternoon, time='14:20')
    run_daily(trade_afternoon, time='14:55')
    run_daily(close_account, '14:50')

    # ⭐ 每周一早上训练一次模型（用完全历史数据）
    run_weekly(train_ml_model, 1, '9:10')


# ========== 1. 特征工程 ==========
def get_ml_features(stock, end_date, count=500):
    df = get_price(
        stock,
        end_date=end_date,
        frequency='daily',
        fields=['close', 'volume', 'high', 'low'],
        count=count,
        skip_paused=False,
        fq='pre'
    )
    if df is None or len(df) < 20:
        return np.zeros(g.ml_feature_num)

    closes = df['close'].values
    volumes = df['volume'].values
    highs = df['high'].values
    lows = df['low'].values

    features = []

    # 1. 20日收益率
    ret_20 = closes[-1] / closes[-20] - 1 if len(closes) >= 20 else 0
    features.append(ret_20)

    # 2. 60日波动率（年化）【⭐ 修复点】
    if len(closes) >= 61:
        # 用 pandas 的 pct_change 安全计算
        ret_series = df['close'].iloc[-61:].pct_change().dropna()
        vol_60 = ret_series.std() * np.sqrt(250) if len(ret_series) > 1 else 0
    else:
        vol_60 = 0
    features.append(vol_60)

    # 3. 20日平均成交量 / 100日平均成交量 - 1
    avg_vol_20 = np.mean(volumes[-20:]) if len(volumes) >= 20 else 0
    avg_vol_100 = np.mean(volumes[-100:]) if len(volumes) >= 100 else 1e-9
    turnover_proxy = avg_vol_20 / (avg_vol_100 + 1e-9) - 1
    features.append(turnover_proxy)

    # 4. 过去20日最高价 / 最低价 - 1
    if len(highs) >= 20 and len(lows) >= 20:
        range_20 = (highs[-20:].max() / lows[-20:].min() - 1)
    else:
        range_20 = 0
    features.append(range_20)

    # 5. RSI(14)
    if len(closes) >= 15:
        delta = np.diff(closes[-15:])
        gain = np.mean(delta[delta > 0]) if np.any(delta > 0) else 0
        loss = -np.mean(delta[delta < 0]) if np.any(delta < 0) else 1e-9
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
    else:
        rsi = 50
    features.append(rsi / 100.0)

    # 6. 收盘价与20日均线距离
    ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
    price_ma_ratio = closes[-1] / (ma20 + 1e-9) - 1
    features.append(price_ma_ratio)

    # 7. 流通市值对数
    try:
        fundamentals = get_fundamentals(
            query(valuation.circulating_market_cap)
            .filter(valuation.code == stock),
            date=end_date
        )
        if not fundamentals.empty:
            cap = fundamentals['circulating_market_cap'].iloc[0]
            log_cap = np.log(cap + 1e9)
        else:
            log_cap = 20
    except:
        log_cap = 20
    features.append(log_cap)

    # 8. 近500天涨停次数占比（简单用收盘==最高近似）
    limit_up_days = (closes == highs) & (highs > 0)
    limit_ratio = np.sum(limit_up_days) / max(len(closes), 1)
    features.append(limit_ratio)

    # 9. 距离上次涨停天数（归一化）
    limit_indices = np.where(limit_up_days)[0]
    if len(limit_indices) > 0:
        last_limit_idx = limit_indices[-1]
        days_since_limit = len(closes) - 1 - last_limit_idx
    else:
        days_since_limit = 500
    features.append(days_since_limit / 500.0)

    # 10. 近5日收益率
    ret_5 = closes[-1] / closes[-5] - 1 if len(closes) >= 5 else 0
    features.append(ret_5)

    # 11. 近20日最大回撤
    if len(closes) >= 20:
        peak = np.maximum.accumulate(closes[-20:])
        drawdown = (closes[-20:] - peak) / peak
        max_dd = np.min(drawdown) if len(drawdown) > 0 else 0
    else:
        max_dd = 0
    features.append(max_dd)

    # 12. Beta（同前，无修改）
    try:
        bench_df = get_price('399101.XSHE', end_date=end_date, frequency='daily',
                             fields=['close'], count=60, fq='pre')
        if bench_df is not None and len(bench_df) >= 2:
            bench_ret = bench_df['close'].pct_change().dropna()
            stock_ret = df['close'].iloc[-len(bench_ret)-1:].pct_change().dropna()
            if len(stock_ret) == len(bench_ret) and len(bench_ret) > 1:
                cov = np.cov(stock_ret, bench_ret)[0, 1]
                bench_var = np.var(bench_ret)
                beta = cov / bench_var if bench_var > 0 else 1
            else:
                beta = 1
        else:
            beta = 1
    except:
        beta = 1
    features.append(beta)

    # 13. Alpha（近20日超额收益）
    if len(closes) >= 20:
        bench_df_20 = get_price('399101.XSHE', end_date=end_date, frequency='daily',
                                fields=['close'], count=20, fq='pre')
        if bench_df_20 is not None and len(bench_df_20) >= 2:
            bench_ret_20 = bench_df_20['close'].iloc[-1] / bench_df_20['close'].iloc[0] - 1
        else:
            bench_ret_20 = 0
        stock_ret_20 = closes[-1] / closes[-20] - 1
        alpha_20 = stock_ret_20 - 0.02/250*20 - beta * bench_ret_20
    else:
        alpha_20 = 0
    features.append(alpha_20)

    # 14. 近5日成交量变化率
    if len(volumes) >= 10:
        vol_5_avg = np.mean(volumes[-5:])
        vol_prev_5 = np.mean(volumes[-10:-5])
        vol_change = vol_5_avg / (vol_prev_5 + 1e-9) - 1
    else:
        vol_change = 0
    features.append(vol_change)

    return np.array(features)


# ========== 2. ML 训练函数 ==========
def train_ml_model(context):
    """使用完全历史数据训练代价敏感逻辑回归，结果存入 g.ml_weights"""
    log.info("开始训练机器学习模型...")
    yesterday = context.previous_date  # 昨天
    # 样本时间范围：在昨天之前，且标签所需的未来5日也必须在昨天之前
    # 因此最晚的样本日期是 yesterday - 5天
    latest_sample_date = yesterday - timedelta(days=5)
    # 从500天前到 latest_sample_date 之间取样
    start_sample_date = latest_sample_date - timedelta(days=500)
    date_range = pd.date_range(start=start_sample_date, end=latest_sample_date, freq='B')  # 工作日

    if len(date_range) > 100:
        date_range = date_range[::5]  # 每5天取一个样本，减少计算量
    if len(date_range) < 30:
        log.error("训练样本日期不足，跳过训练")
        return

    # 初步股票池（全市场过滤）
    all_stocks = list(get_all_securities('stock').index)
    all_stocks = filter_kcbj_stock(all_stocks)
    all_stocks = filter_st_stock(all_stocks)
    all_stocks = filter_new_stock(context, all_stocks)
    all_stocks = all_stocks[:300]  # 限制训练池数量，防止超时

    X_list = []
    y_list = []

    for sample_date in date_range[:200]:  # 最多200个样本日
        for stock in all_stocks:
            # 检查该日期股票是否上市且可交易
            if not is_trade_day(sample_date, stock):
                continue

            # 特征：以 sample_date 为截止日
            features = get_ml_features(stock, sample_date, count=g.ml_window)
            if np.all(features == 0):
                continue

            # 标签：sample_date 之后5个交易日的收益率
            future_start = sample_date + timedelta(days=1)  # 实际要找下一个交易日，简化用
            # 直接用回 historical price 精确计算
            future_df = get_price(
                stock,
                start_date=sample_date + timedelta(days=1),
                end_date=sample_date + timedelta(days=10),  # 留足缓冲
                frequency='daily',
                fields=['close'],
                skip_paused=False,
                fq='pre'
            )
            if future_df is None or len(future_df) < 2:
                continue
            # 确保取的日期不超过 yesterday
            future_df = future_df[future_df.index <= pd.Timestamp(yesterday)]
            if len(future_df) < 2:
                continue
            buy_price = future_df['close'].iloc[0]
            # 找到第5个交易日（如果数据不够则跳过）
            if len(future_df) >= 5:
                sell_price = future_df['close'].iloc[4]
            else:
                sell_price = future_df['close'].iloc[-1]  # 少于5日则用最后
            ret = sell_price / buy_price - 1
            label = 1 if ret > 0 else 0  # 盈利=1，亏损=0

            X_list.append(features)
            y_list.append(label)

    if len(X_list) < 50:
        log.error(f"训练样本不足（仅{len(X_list)}个），跳过训练")
        return

    X = np.array(X_list)
    y = np.array(y_list)
    log.info(f"训练集大小: {X.shape}")
    log.info(f"盈利样本比例: {np.mean(y):.2%}")

    # 代价敏感：复制亏损样本
    loss_mask = (y == 0)
    X_loss = X[loss_mask]
    y_loss = y[loss_mask]
    X_aug = np.vstack([X, X_loss])
    y_aug = np.concatenate([y, y_loss])

    # IRLS 训练
    w = np.zeros(X_aug.shape[1])
    for iteration in range(10):
        z = np.dot(X_aug, w)
        p = 1.0 / (1.0 + np.exp(-z))  # sigmoid
        p = np.clip(p, 0.01, 0.99)
        grad = np.dot(X_aug.T, (p - y_aug))
        W = p * (1 - p)
        H = np.dot(X_aug.T * W, X_aug) + 0.01 * np.eye(X_aug.shape[1])
        try:
            w -= np.linalg.solve(H, grad)
        except:
            break

    g.ml_weights = w
    log.info("模型训练完成，权重: %s" % str(w.round(4).tolist()))


def is_trade_day(date, stock):
    """简单判断某日期股票是否可交易"""
    try:
        df = get_price(stock, start_date=date, end_date=date+timedelta(days=1),
                       frequency='daily', fields=['close'], skip_paused=False)
        if df is not None and len(df) > 0:
            return True
    except:
        pass
    return False


# ========== 3. 机器学习评分 + 风控买入 ==========
def get_ml_score(stock, context):
    """返回股票当前的机器学习风险得分 (0~1)"""
    if g.ml_weights is None:
        return 0.5  # 无模型时中性
    features = get_ml_features(stock, context.previous_date, count=g.ml_window)
    if np.all(features == 0):
        return 0.5
    z = np.dot(features, g.ml_weights)
    try:
        score = 1.0 / (1.0 + np.exp(-z))
    except:
        score = 0.5
    return score


def ml_adjust_buy(stock, context, base_value):
    """
    根据ML评分调整买入金额：
    返回 (是否买入, 调整后的value)
    """
    score = get_ml_score(stock, context)
    if score > g.ml_threshold_skip:
        log.info(f"ML风控：{stock} 得分 {score:.3f} > {g.ml_threshold_skip}，跳过买入")
        return False, 0
    elif score > g.ml_threshold_half:
        adjust_value = base_value * 0.5
        log.info(f"ML风控：{stock} 得分 {score:.3f} 在 [{g.ml_threshold_half},{g.ml_threshold_skip}]，减半买入({adjust_value:.0f}元)")
        return True, adjust_value
    else:
        log.info(f"ML风控：{stock} 得分 {score:.3f} <= {g.ml_threshold_half}，正常买入")
        return True, base_value


# ========== 4. 原策略函数（保持逻辑不变，仅买入流程加入ML） ==========
# 以下所有原函数均为复制原策略代码，只修改了 buy_security 函数

def prepare_stock_list(context):
    g.hold_list= []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    g.no_trading_today_signal = today_is_between(context)


def get_consecutive_limit_up(context, stock_list, days=500):
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close", "high_limit"],
        count=days,
        panel=False,
        fill_paused=False,
    )
    df['is_limit_up'] = (df['close'] == df['high_limit']).astype(int)
    result_stocks = []
    for code, group in df.groupby('code'):
        group = group.sort_values('time')
        limit_series = group['is_limit_up'].values
        for i in range(len(limit_series) - 1):
            if limit_series[i] == 1 and limit_series[i + 1] == 1:
                result_stocks.append(code)
                break
    log.info(f"2连板筛选：输入{len(stock_list)}只，筛选后{len(result_stocks)}只")
    return result_stocks


def filter_fresh_stocks(context, stock_list, exclude_ratio=0.10):
    if len(stock_list) == 0:
        return []
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close", "high_limit"],
        count=g.limit_days_window,
        panel=False,
        fill_paused=False,
    )
    freshness_dict = {}
    for code, group in df.groupby('code'):
        group = group.sort_values('time', ascending=False)
        limit_days = group[group['close'] == group['high_limit']]['time']
        if len(limit_days) > 0:
            last_limit_date = limit_days.iloc[0]
            days_since = (context.previous_date - last_limit_date.to_pydatetime().date()).days
            freshness_dict[code] = days_since
        else:
            freshness_dict[code] = 999999
    sorted_stocks = sorted(freshness_dict.items(), key=lambda x: x[1])
    exclude_count = int(len(sorted_stocks) * exclude_ratio)
    excluded_stocks = set([s[0] for s in sorted_stocks[:exclude_count]])
    result_list = [s for s in stock_list if s not in excluded_stocks]
    log.info(f"新鲜度剔除：剔除{exclude_count}只最热股票，剩余{len(result_list)}只")
    return result_list


def get_start_point(context, stock_list, days=500):
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["open", "low", "close", "high_limit"],
        count=days,
        panel=False,
        fill_paused=False,
    )
    stock_start_point = {}
    stock_price_bias = {}
    current_data = get_current_data()
    for code, group in df.groupby('code'):
        group = group.sort_values('time')
        limit_hit_rows = group[group['close'] == group['high_limit']]
        if not limit_hit_rows.empty:
            latest_limit_hit = limit_hit_rows.iloc[-1]
            latest_limit_index = latest_limit_hit.name
            previous_rows = group[group.index <= latest_limit_index].iloc[::-1]
            for idx, row in previous_rows.iterrows():
                if row['close'] < row['open']:
                    stock_start_point[code] = row['low']
                    break
    for code, start_point in stock_start_point.items():
        last_price = current_data[code].last_price
        bias = last_price / start_point
        stock_price_bias[code] = bias
    sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1], reverse=False)
    return [i[0] for i in sorted_list]


def get_stock_list(context):
    final_list = []
    yesterday = context.previous_date
    initial_list = get_all_securities("stock", yesterday).index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    if g.filter_loss_black:
        initial_list = filter_loss_black(context, initial_list, days=20)
    q = query(
        valuation.code, indicator.eps
    ).filter(
        valuation.code.in_(initial_list)
    ).order_by(
        valuation.market_cap.asc()
    )
    df = get_fundamentals(q)
    initial_list = df['code'].tolist()[:g.init_stock_count]
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    initial_list = get_consecutive_limit_up(context, initial_list, g.limit_days_window)
    initial_list = filter_fresh_stocks(context, initial_list, exclude_ratio=0.10)
    initial_list = get_start_point(context, initial_list, g.limit_days_window)
    stock_list = get_stock_industry(initial_list)
    final_list = stock_list[:g.stock_num*2]
    log.info('今日前10:%s' % final_list)
    return final_list


def weekly_sell(context):
    if g.no_trading_today_signal == False:
        current_data = get_current_data()
        close_no_trading_hold(context)
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        target_list = g.target_list[:g.stock_num*2]
        log.info(str(target_list))
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list) and (current_data[stock].last_price < current_data[stock].high_limit):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("已持有[%s]" % (stock))


# ⭐ 唯一改动：买入时接入ML风控
def buy_security(context, target_list, cash=0, buy_number=0):
    position_count = len(context.portfolio.positions)
    target_num = g.stock_num
    if cash == 0:
        cash = context.portfolio.total_value
    if buy_number == 0:
        buy_number = target_num
    bought_num = 0
    base_value = cash / target_num
    log.info(f'base_value={base_value:.0f}元，目标持{target_num}只，当前持{position_count}只')

    for stock in target_list:
        if position_count >= target_num:
            break
        if context.portfolio.positions[stock].total_amount > 0:
            continue
        if bought_num >= buy_number:
            break

        # ---- ML风控介入 ----
        buy_ok, buy_value = ml_adjust_buy(stock, context, base_value)
        if not buy_ok:
            continue

        if open_position(stock, buy_value):
            g.not_buy_again.append(stock)
            bought_num += 1
            position_count += 1
            log.info(f"买入[{stock}] {buy_value:.0f}元")
        else:
            log.warn(f"买入[{stock}]失败")


# 后面所有原函数照搬，无任何改动
def weekly_buy(context):
    if g.no_trading_today_signal == False:
        current_data = get_current_data()
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        target_list = g.target_list[:g.stock_num*2]
        log.info(str(target_list))
        buy_security(context, target_list)
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.not_buy_again.append(stock)


def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        for stock in g.yesterday_HL_list:
            if context.portfolio.positions[stock].closeable_amount > -100:
                current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
                if current_data.iloc[0,0] < current_data.iloc[0,1]:
                    log.info("[%s]涨停打开，卖出" % (stock))
                    position = context.portfolio.positions[stock]
                    close_position(position)
                    g.reason_to_sell = 'limitup'
                else:
                    log.info("[%s]涨停，继续持有" % (stock))


def check_remain_amount(context):
    if g.reason_to_sell == 'limitup':
        g.hold_list= []
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.hold_list.append(stock)
        if len(g.hold_list) < g.stock_num:
            target_list = get_stock_list(context)
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            log.info('有余额可用'+str(round((context.portfolio.cash),2))+'元。'+ str(target_list))
            buy_security(context, target_list)
        g.reason_to_sell = ''
    else:
        g.reason_to_sell = ''


def trade_afternoon(context):
    if g.no_trading_today_signal == False:
        check_limit_up(context)
        if g.HV_control == True:
            check_high_volume(context)
        huanshou(context)
        check_remain_amount(context)


def sell_stocks(context):
    if g.run_stoploss == True:
        if g.stoploss_strategy == 3:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
            else:
                for stock in context.portfolio.positions.keys():
                    if context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_limit:
                        order_target_value(stock, 0)
                        log.debug("收益止损,卖出{}".format(stock))
                        g.reason_to_sell = 'stoploss'
                        g.loss_black[stock] = context.current_dt
        # 其他策略分支略，保持原样


def check_high_volume(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        if context.portfolio.positions[stock].closeable_amount ==0:
            continue
        df_volume = get_bars(stock,count=g.HV_duration,unit='1d',fields=['volume'],include_now=True, df=True)
        if df_volume['volume'].values[-1] > g.HV_ratio*df_volume['volume'].values.max():
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(f"[{stock}]天量，卖出, close_position: {r}")
            g.reason_to_sell == 'limitup'


def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list


def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if (stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit)]


def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < timedelta(days=375)]


def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]


def filter_loss_black(context, stock_list, days=20):
    result_list = []
    for stock in stock_list:
        if (stock in g.loss_black.keys()
            and context.current_dt - g.loss_black[stock] < timedelta(days=days)):
            log.info(f"{stock}由于近期止损被过滤, 止损时间：{g.loss_black[stock]}")
            continue
        result_list.append(stock)
    return result_list


def get_stock_industry(stock):
    result = get_industry(security=stock)
    selected_stocks = []
    industry_list = []
    for stock_code, info in result.items():
        industry_name = info['sw_l2']['industry_name']
        if industry_name not in industry_list:
            industry_list.append(industry_name)
            selected_stocks.append(stock_code)
            if len(industry_list) == 10:
                break
    return selected_stocks


def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        start_date = context.current_dt - timedelta(days=20)
        end_date = context.previous_date
        df_volume = get_price(stock, end_date=end_date, frequency='daily', fields=['volume'], count=20)
        df_cap = get_valuation(stock, end_date=end_date, fields=['circulating_cap'], count=1)
        circulating_cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
        return df_volume['turnover_ratio'].mean()
    else:
        date_now = context.current_dt
        df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now, frequency='1m', fields=['volume'],
                           skip_paused=False, fq='pre', panel=True, fill_paused=False)
        volume = df_vol['volume'].sum()
        date_pre = context.previous_date
        df_circulating_cap = get_valuation(stock, end_date=date_pre, fields=['circulating_cap'], count=1)
        circulating_cap = df_circulating_cap['circulating_cap'].iloc[0] if not df_circulating_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        turnover_ratio = volume / (circulating_cap * 10000)
        return turnover_ratio


def huanshou(context):
    ss = []
    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit*0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount ==0:
            continue
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0: continue
        r = rt / avg
        action, icon = '', ''
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '🔥'
        if action:
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(f"{action} {stock} {get_security_info(stock).display_name} 换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x {icon} close_position: {r}")
            g.reason_to_sell = 'limitup'


def order_target_value_(security, value):
    return order_target_value(security, value)


def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False


def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False


def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    if g.pass_april is True:
        if (('04-01' <= today) and (today <= '04-30')) or (('01-01' <= today) and (today <= '01-30')):
            return True
        else:
            return False
    else:
        return False


def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0 and g.no_trading_hold_signal == False:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                if close_position(position):
                    log.info("卖出[%s]" % (stock))
                else:
                    log.info("卖出[%s]错误！！！！！" % (stock))
            buy_security(context, g.no_trading_buy)
            g.no_trading_hold_signal = True


def close_no_trading_hold(context):
    if g.no_trading_hold_signal == True:
        for stock in g.hold_list:
            position = context.portfolio.positions[stock]
            close_position(position)
            log.info("卖出[%s]" % (stock))
        g.no_trading_hold_signal = False