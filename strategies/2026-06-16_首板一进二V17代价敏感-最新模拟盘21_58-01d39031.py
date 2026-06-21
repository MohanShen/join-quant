# Clone from JoinQuant
# postId: 01d3903199ba2a04fd2f753b767c64c6
# backtestId: 0b3b6af5b0ea52688d6ee9861df6aeaf
# title: 首板一进二V17代价敏感-最新模拟盘21.58%

# ========================================================================
# 策略名称：首板一进二 优化版 v17_ML代价敏感
# ========================================================================
# v7: 1539%牛市/31.6%回撤/Sharpe13.66 (最优规则版)
# v7熊市: -10.95%/39.89%回撤
#
# v17_ML：v14特征 + 代价敏感学习
#   1. v14的13个特征(含5日动量+大小盘强弱)
#   2. 更严阈值：0.7跳过/0.5减半(v12是0.6/0.4)
#   3. 代价敏感：亏损样本权重2x(让模型更怕亏损)
#   4. 保留v12全部逻辑
# ========================================================================

from jqdata import *
import pandas as pd
import numpy as np

CONDITION_RULES = [
    ('A: 昨日成交额1~5亿 | 竞价涨幅7~9% | 竞昨比10~20%',  1.07, 1.09, 0.10, 0.20),
    ('B: 昨日成交额5~15亿 | 竞价涨幅7~9% | 竞昨比10~20%', 1.07, 1.09, 0.10, 0.20),
    ('C: 昨日成交额5~15亿 | 竞价涨幅4~7% | 竞昨比3~7%',   1.04, 1.07, 0.03, 0.07),
    ('D: 昨日成交额5~15亿 | 竞价涨幅4~7% | 竞昨比10~20%', 1.04, 1.07, 0.10, 0.20),
    ('E: 昨日成交额5~15亿 | 竞价涨幅0~4% | 竞昨比3~7%',   1.00, 1.04, 0.03, 0.07),
    ('F: 昨日成交额5~15亿 | 竞价涨幅0~4% | 竞昨比7~10%',  1.00, 1.04, 0.07, 0.10),
]

def initialize(context):
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.005))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0002, close_commission=0.0002, min_commission=5), type='stock')
    set_benchmark('399303.XSHE')
    
    g.information = {}
    g.drop_percent = 0.05
    g.condition_stats = {}
    g.name_cache = {}
    
    # 净值曲线动量
    g.consecutive_loss_days = 0     # 连续亏损天数
    g.skip_buy = False              # 暂停买入标志
    g.peak_value = 0               # 近期净值高点
    g.drawdown_reduction = 1.0     # 回撤减仓系数(0.5或1.0)
    g.prev_day_value = 0           # 昨日总资产
    
    # ML在线学习
    g.ml_features = []             # 历史特征列表
    g.ml_labels = []               # 历史标签(次日是否盈利)
    g.ml_weights = None            # 模型权重
    g.ml_pred_reduction = 1.0      # ML预测的买入系数
    g.recent_pnls = []             # 近5日收益
    g.yesterday_buy_count = 0      # 昨日买入数
    g.pending_features = None      # 待标注的特征(今日采集，明日标注)
    g.day_count = 0
    
    run_daily(before_market_open, time='09:10')
    run_daily(get_buy, '09:26')
    run_daily(get_close_sell, time='11:25')
    run_daily(get_close_sell, time='13:30')
    run_daily(eod_stats, time='15:00')


def before_market_open(context): 
    y_day = context.previous_date.strftime('%Y-%m-%d')

    initial_list = prepare_stock_list(context)
    log.info(f"[选股] 初始股票池: {len(initial_list)}只")
    
    g.target_list = get_stocks_with_high_increase(initial_list, y_day)
    log.info(f"[选股] 昨日涨幅>7%: {len(g.target_list)}只")
    
    g.target_list = filter_excessive_limit_up(g.target_list, y_day)
    log.info(f"[选股] 过滤一字/T字涨停后: {len(g.target_list)}只")
    
    g.target_list = filter_excessive_increase(g.target_list, y_day)
    log.info(f"[选股] 过滤近5日波动>40%后: {len(g.target_list)}只")
    
    g.target_list = filter_excessive_limit_days(g.target_list, y_day)
    log.info(f"[选股] 过滤近5日涨停>=4天后: {len(g.target_list)}只")
    
    g.target_list = filter_below_n_high(g.target_list, y_day, days=100)
    log.info(f"[选股] 过滤低于100日高点后: {len(g.target_list)}只")
    
    # 净值曲线动量判断
    if g.skip_buy:
        g.skip_buy = False  # 只暂停1天
        log.info("[净值动量] 冷静期结束，恢复交易")
    
    if g.peak_value > 0:
        current_dd = (context.portfolio.total_value / g.peak_value - 1)
        if current_dd < -0.08:
            g.drawdown_reduction = 0.5
            log.info(f"[净值动量] 净值从高点回撤{current_dd:.1%}，买入减半")
        else:
            g.drawdown_reduction = 1.0
    
    # ML风控预测
    if g.ml_weights is not None and g.day_count >= 60:
        try:
            today_features = compute_ml_features(context)
            if today_features is not None:
                score = sigmoid(np.dot(g.ml_weights, today_features))
                if score > 0.7:
                    g.ml_pred_reduction = 0.0  # 预测亏损概率>70%，跳过
                    log.info(f"[ML风控] 预测亏损概率{score:.1%}，跳过买入")
                elif score > 0.5:
                    g.ml_pred_reduction = 0.5  # 预测亏损概率50-70%，减半
                    log.info(f"[ML风控] 预测亏损概率{score:.1%}，减半买入")
                else:
                    g.ml_pred_reduction = 1.0
                    log.info(f"[ML风控] 预测亏损概率{score:.1%}，正常买入")
        except Exception as e:
            g.ml_pred_reduction = 1.0
            log.info(f"[ML风控] 预测异常: {e}")
    else:
        g.ml_pred_reduction = 1.0
    
    g.name_cache = {}
    if g.target_list:
        for s in g.target_list:
            try:
                g.name_cache[s] = get_security_info(s).display_name
            except:
                g.name_cache[s] = '未知'
        stock_info = [f"{s}({g.name_cache[s]})" for s in g.target_list]
        log.info(f"今日选股结果 ({len(g.target_list)}只):\n" + "\n".join(stock_info))
        send_message(f"今日选股: {len(g.target_list)}只, 涨幅>7%")
    else:
        log.info("今日无符合条件的股票")
        send_message("今日无符合条件的股票")


def get_buy(context):
    # 净值动量：连亏暂停
    if g.skip_buy:
        log.info("[净值动量] 冷静期，不买入")
        return
    
    # ML风控：预测亏损
    if g.ml_pred_reduction == 0.0:
        log.info("[ML风控] 预测亏损，跳过买入")
        return

    qualified_stocks = []
    current_data = get_current_data()
    y_day = context.previous_date.strftime('%Y-%m-%d')
    t_day = context.current_dt.strftime("%Y-%m-%d")
    start = t_day + ' 09:15:00'
    end = t_day + ' 09:26:00'
    DTJiner = context.portfolio.available_cash * g.drawdown_reduction * g.ml_pred_reduction  # 回撤+ML减仓

    if not g.target_list:
        return

    prev_df = get_price(
        g.target_list, end_date=y_day, frequency='daily',
        fields=['close', 'volume', 'money'], count=1, panel=False,
        fill_paused=False, skip_paused=True
    )
    prev_map = {row['code']: row for _, row in prev_df.iterrows()}

    val_df = get_fundamentals(
        query(valuation.code, valuation.market_cap, valuation.circulating_market_cap)
        .filter(valuation.code.in_(g.target_list)),
        date=str(y_day)[:10]
    )
    val_map = {row['code']: row for _, row in val_df.iterrows()} if not val_df.empty else {}

    hl_base = {s: current_data[s].high_limit / 1.1 for s in g.target_list}

    for s in g.target_list:
        name = g.name_cache.get(s, '未知')

        try:
            prev = prev_map.get(s)
            if prev is None:
                continue
            avg_chg = prev['money'] / prev['volume'] / prev['close'] * 1.1 - 1
            money = prev['money']
            open_price = current_data[s].day_open
            val = val_map.get(s)

            if avg_chg < 0.07:
                continue
            if open_price <= 3:
                continue
            if val is None or val['market_cap'] < 10 or val['circulating_market_cap'] > 520:
                continue
            if money < 1e8 or money > 15e8:
                continue
            is_1_5 = money < 5e8
            is_5_15 = not is_1_5
        except:
            continue

        try:
            zyts = calculate_zyts(s, context)
            vol_data = attribute_history(s, zyts, '1d', fields=['volume'], skip_paused=True)
            if len(vol_data) < 2:
                continue
            if vol_data['volume'][-1] <= max(vol_data['volume'][:-1]) * 0.9:
                continue
        except:
            continue

        try:
            auction = get_call_auction(s, start_date=start, end_date=end, fields=['time', 'volume', 'current'])
            if auction.empty:
                continue
            cur_ratio = auction['current'][0] / hl_base[s]
            auction_ratio = auction['volume'][0] / vol_data['volume'][-1]

            matched_condition = None
            for cond_name, open_lo, open_hi, auc_lo, auc_hi in CONDITION_RULES:
                if cond_name.startswith('A') and not is_1_5:
                    continue
                if not cond_name.startswith('A') and not is_5_15:
                    continue
                if open_lo < cur_ratio <= open_hi and auc_lo <= auction_ratio <= auc_hi:
                    matched_condition = cond_name
                    break

            if matched_condition is None:
                continue
        except:
            continue

        qualified_stocks.append(s)
        g.information[s] = matched_condition
        log.info(f"✅ {s}({name}) 通过筛选，命中: {matched_condition}")

    log.info(f"最终符合条件: {len(qualified_stocks)}只")

    buy_count = 0
    if qualified_stocks and context.portfolio.available_cash / context.portfolio.total_value > 0.3:
        value_per_stock = DTJiner / len(qualified_stocks)
        for s in qualified_stocks:
            price = current_data[s].last_price
            shares = int(value_per_stock / price / 100) * 100
            if shares >= 100:
                order_value(s, value_per_stock, MarketOrderStyle(current_data[s].day_open))
                buy_count += 1
                log.info(f"买入 {s}: 价格={price}, 数量={shares}, 条件={g.information.get(s,'未知')}, 减仓={g.drawdown_reduction}*{g.ml_pred_reduction}")
    g.yesterday_buy_count = buy_count


def get_close_sell(context):
    y_day = context.previous_date.strftime('%Y-%m-%d')
    current_data = get_current_data()
    positions = context.portfolio.positions
    
    t = context.current_dt
    h, m = t.hour, t.minute
    
    yst_close_map = {}
    if positions:
        try:
            yst_df = get_price(
                list(positions.keys()), end_date=y_day,
                frequency='daily', fields=['close'], count=1,
                panel=False, skip_paused=True
            )
            yst_close_map = dict(zip(yst_df['code'], yst_df['close']))
        except:
            pass
    
    for s in list(positions):
        if s not in g.name_cache:
            try:
                g.name_cache[s] = get_security_info(s).display_name
            except:
                g.name_cache[s] = '未知'
                
    if (h == 11 and m == 25) or (h == 13 and m == 30):
        for s in list(positions):
            pos = positions[s]
            last_price = current_data[s].last_price
            high_limit = current_data[s].high_limit
            avg_cost = pos.avg_cost
            closeable = pos.closeable_amount
            
            try:
                close_data2 = attribute_history(s, 4, '1d', ['close'])
                M4 = close_data2['close'].mean()
                MA5 = (M4 * 4 + last_price) / 5
            except:
                continue
            
            if closeable != 0 and last_price < high_limit and last_price > avg_cost:
                get_record_sell(context, s, '未涨停止盈')
                order_target_value(s, 0)
                log.info(f'止盈卖出 {s}({g.name_cache[s]})')
            
            elif closeable != 0 and last_price < (MA5 + MA5 * 0.05):
                get_record_sell(context, s, '跌破5日线止损')
                order_target_value(s, 0)
                log.info(f'价格跌破5日线+5%止损卖出 {s}({g.name_cache[s]})')
            
            elif closeable != 0:
                yst_close = yst_close_map.get(s)
                if yst_close and yst_close > 0:
                    drop_ratio = (yst_close - last_price) / yst_close
                    if drop_ratio >= g.drop_percent:
                        get_record_sell(context, s, '跌幅止损')
                        order_target_value(s, 0)
                        log.info(f'跌幅止损卖出: {s}({g.name_cache[s]}) 跌幅{-drop_ratio:.2%}')


def eod_stats(context):
    total_value = context.portfolio.total_value
    daily_pnl = 0
    
    # 更新净值高点
    g.peak_value = max(g.peak_value, total_value)
    
    # 更新连续亏损天数
    if g.prev_day_value > 0:
        daily_pnl = (total_value / g.prev_day_value - 1)
        g.recent_pnls.append(daily_pnl)
        if len(g.recent_pnls) > 5:
            g.recent_pnls = g.recent_pnls[-5:]
        if daily_pnl < -0.005:  # 亏损超0.5%算亏
            g.consecutive_loss_days += 1
        else:
            g.consecutive_loss_days = 0
        
        # 连亏3天 → 暂停1天
        if g.consecutive_loss_days >= 2:
            g.skip_buy = True
            log.info(f"[净值动量] 连亏{g.consecutive_loss_days}天，明日暂停买入")
    
    # ========== ML在线学习 ==========
    g.day_count += 1
    
    # 标注昨日的特征（用今日收益作为标签）
    if g.pending_features is not None and g.prev_day_value > 0:
        label = 1.0 if daily_pnl > 0 else 0.0  # 1=盈利, 0=亏损
        g.ml_features.append(g.pending_features)
        g.ml_labels.append(label)
        # 滚动窗口：只保留最近120天
        if len(g.ml_features) > 120:
            g.ml_features = g.ml_features[-120:]
            g.ml_labels = g.ml_labels[-120:]
    
    # 采集今日特征（明日标注）
    if g.day_count >= 3:
        try:
            today_f = compute_ml_features(context)
            if today_f is not None:
                g.pending_features = today_f
        except:
            g.pending_features = None
    
    # 每5天重新训练模型
    if len(g.ml_features) >= 60 and g.day_count % 5 == 0:
        try:
            train_ml_model()
        except Exception as e:
            log.info(f"[ML训练] 异常: {e}")
    
    g.prev_day_value = total_value
    
    ml_info = f"ML权重={'已训练' if g.ml_weights is not None else '未训练'} 样本={len(g.ml_features)}" if len(g.ml_features) > 0 else "ML=无数据"
    log.info(f"=== 盘后 === 总资产:{total_value:,.0f} | 日收益:{daily_pnl:.2%} | 持仓:{len(context.portfolio.positions)} | "
             f"连亏:{g.consecutive_loss_days}天 | 净值高点回撤:{(total_value/g.peak_value-1):.1%} | {ml_info}")


def compute_ml_features(context):
    """计算10个市场+策略特征"""
    hs300 = '000300.XSHG'
    zz1000 = '000852.XSHG'
    
    # f1-f3: 指数趋势(在MA上方=1)
    hs300_hist = attribute_history(hs300, 60, '1d', ['close'], df=False)
    hs300_c = hs300_hist['close'][-1]
    f1 = 1.0 if hs300_c > np.mean(hs300_hist['close'][-20:]) else 0.0
    f2 = 1.0 if hs300_c > np.mean(hs300_hist['close'][-60:]) else 0.0
    
    zz1000_hist = attribute_history(zz1000, 20, '1d', ['close'], df=False)
    f3 = 1.0 if zz1000_hist['close'][-1] > np.mean(zz1000_hist['close'][-20:]) else 0.0
    
    # f4: 昨日涨停家数(用选股结果近似)
    f4 = float(len(g.target_list))
    
    # f5: 沪深300近10日波动率(年化)
    rets = np.diff(hs300_hist['close'][-10:]) / hs300_hist['close'][-10:-1]
    f5 = float(np.std(rets) * np.sqrt(252))
    
    # f6: 策略近5日胜率
    if len(g.recent_pnls) >= 3:
        f6 = float(sum(1 for p in g.recent_pnls if p > 0) / len(g.recent_pnls))
    else:
        f6 = 0.5
    
    # f7: 连亏天数
    f7 = float(g.consecutive_loss_days)
    
    # f8: 当前回撤幅度
    f8 = float((context.portfolio.total_value / g.peak_value - 1)) if g.peak_value > 0 else 0.0
    
    # f9: 昨日买入股票数
    f9 = float(g.yesterday_buy_count)
    
    # f10: 可用现金占比
    f10 = float(context.portfolio.available_cash / max(context.portfolio.total_value, 1))
    
    # f11: HS300 5日动量(短期趋势强度)
    f11 = float(hs300_c / hs300_hist['close'][-5] - 1) if len(hs300_hist['close']) >= 5 else 0.0
    
    # f12: ZZ1000 5日动量(小盘股趋势)
    f12 = float(zz1000_hist['close'][-1] / zz1000_hist['close'][-5] - 1) if len(zz1000_hist['close']) >= 5 else 0.0
    
    # f13: HS300/ZZ1000相对强弱(大盘vs小盘)
    hs300_ret5 = (hs300_c / hs300_hist['close'][-5] - 1) if len(hs300_hist['close']) >= 5 else 0.0
    zz1000_ret5 = (zz1000_hist['close'][-1] / zz1000_hist['close'][-5] - 1) if len(zz1000_hist['close']) >= 5 else 0.0
    f13 = float(hs300_ret5 - zz1000_ret5)  # 正=大盘强, 负=小盘强
    
    return np.array([1.0, f1, f2, f3, f4/50.0, f5, f6, f7/5.0, f8, f9/5.0, f10, f11*10.0, f12*10.0, f13*10.0])  # 归一化+截距


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def train_ml_model():
    """代价敏感逻辑回归：亏损样本权重2x"""
    X = np.array(g.ml_features)  # (N, 14)
    y = np.array(g.ml_labels)     # (N,)
    
    # 代价敏感：复制亏损样本(y=0)，让模型更怕亏损
    loss_mask = (y == 0)
    X_loss = X[loss_mask]
    y_loss = y[loss_mask]
    X_aug = np.vstack([X, X_loss])  # 亏损样本出现2次
    y_aug = np.concatenate([y, y_loss])
    
    # IRLS训练
    w = np.zeros(X_aug.shape[1])
    
    for iteration in range(10):
        z = np.dot(X_aug, w)
        p = sigmoid(z)
        p = np.clip(p, 0.01, 0.99)
        
        grad = np.dot(X_aug.T, (p - y_aug))
        W = p * (1 - p)
        H = np.dot(X_aug.T * W, X_aug) + 0.01 * np.eye(X_aug.shape[1])
        
        try:
            w -= np.linalg.solve(H, grad)
        except:
            break
    
    g.ml_weights = w
    
    # 计算训练准确率(用原始数据)
    pred = sigmoid(np.dot(X, w))
    acc = np.mean((pred > 0.5) == (y > 0.5))
    # 代价敏感准确率：亏损召回率更重要
    loss_recall = np.mean((pred[loss_mask] < 0.5))  # 亏损日被正确识别的比例
    pos_rate = np.mean(y)
    log.info(f"[ML训练-代价敏感] 样本={len(y)}(增强{len(y_aug)}) 准确率={acc:.1%} 亏损召回={loss_recall:.1%} 盈利日占比={pos_rate:.1%}")


# ========== 辅助函数（原版完全保留） ==========
def get_hl_count_df(hl_list, y_day, watch_days):
    if not hl_list:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    df = get_price(hl_list, end_date=y_day, frequency='daily',
                   fields=['close', 'high_limit', 'low', 'open'],
                   count=watch_days, panel=False, fill_paused=False, skip_paused=False)
    if df.empty:
        return pd.DataFrame(index=hl_list, data={'count': 0, 'extreme_count': 0})
    df['is_limit']   = df['close'] == df['high_limit']
    df['is_yizi']    = (df['low'] == df['high_limit']) & df['is_limit']
    df['is_tzi']     = (df['open'] == df['high_limit']) & df['is_limit'] & (df['low'] < df['high_limit'])
    df['is_extreme'] = df['is_yizi'] | df['is_tzi']
    counts = df.groupby('code')[['is_limit', 'is_extreme']].sum().astype(int)
    counts.columns = ['count', 'extreme_count']
    counts = counts.reindex(hl_list, fill_value=0)
    return counts

def filter_excessive_limit_days(stock_list, y_day):
    limit_up_df = get_hl_count_df(stock_list, y_day, 5)
    qualified_stocks = limit_up_df[limit_up_df['count'] < 4].index.tolist()
    excluded = set(stock_list) - set(qualified_stocks)
    if excluded:
        log.info(f"因近5日涨停天数>=4被排除: {len(excluded)}只")
    return qualified_stocks

def filter_excessive_increase(stock_list, y_day):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='daily',
                   fields=['high', 'low'], count=5, panel=False,
                   fill_paused=False, skip_paused=True)
    if df.empty:
        return stock_list
    grp = df.groupby('code')
    max_h = grp['high'].max()
    min_l = grp['low'].min()
    chg = (max_h - min_l) / min_l
    qualified = chg[chg <= 0.4].index.tolist()
    excluded_n = len(stock_list) - len(qualified)
    if excluded_n:
        log.info(f"因近5日波动超过40%被排除: {excluded_n}只")
    return qualified

def filter_below_n_high(stock_list, y_day, days=100, min_ratio=0.9):
    if not stock_list:
        return []
    total_days = days + 1
    raw = get_price(stock_list, end_date=y_day, frequency='daily',
                    fields=['high', 'close'], count=total_days,
                    panel=False, fill_paused=False, skip_paused=True, fq='pre')
    if raw.empty:
        return []
    qualified = []
    for stock in stock_list:
        sub = raw[raw['code'] == stock]
        if len(sub) < total_days:
            continue
        sub = sub.tail(total_days)
        max_high = sub['high'].iloc[:-1].max()
        yesterday_close = sub['close'].iloc[-1]
        if yesterday_close >= max_high * min_ratio:
            qualified.append(stock)
    log.info(f"前{days}日最高价过滤: 保留{len(qualified)}/{len(stock_list)}只")
    return qualified

def calculate_zyts(s, context):
    high_prices = attribute_history(s, 101, '1d', fields=['high'], skip_paused=True)['high']
    prev_high = high_prices.iloc[-1]
    zyts_0 = next((i-1 for i, high in enumerate(high_prices[-3::-1], 2) if high >= prev_high), 100)
    return zyts_0 + 5

def get_record_sell(context, stock, reason):
    try:
        pos = context.portfolio.positions.get(stock)
        if pos is None or pos.avg_cost <= 0:
            return
        current_data = get_current_data()
        price = current_data[stock].last_price
        cost = pos.avg_cost
        pct = (price - cost) / cost
        cond = g.information.get(stock, '未知条件')
        
        if cond not in g.condition_stats:
            g.condition_stats[cond] = {'win': 0, 'loss': 0, 'win_pct': 0.0, 'loss_pct': 0.0}
        
        st = g.condition_stats[cond]
        if pct >= 0:
            st['win'] += 1
            st['win_pct'] += pct
        else:
            st['loss'] += 1
            st['loss_pct'] += pct
        
        name = g.name_cache.get(stock, '未知')
        log.info(f"[卖出统计] {stock}({name}) 条件={cond} 收益={pct:.2%} 原因={reason}")
        
        lines = ['[条件盈亏汇总]']
        for c, st in g.condition_stats.items():
            total = st['win'] + st['loss']
            avg_win = st['win_pct'] / st['win'] if st['win'] > 0 else 0
            avg_loss = st['loss_pct'] / st['loss'] if st['loss'] > 0 else 0
            lines.append(f"  {c}: 盈{st['win']}笔(均{avg_win:.2%}) 亏{st['loss']}笔(均{avg_loss:.2%}) 共{total}笔")
        log.info('\n'.join(lines))
    except Exception as e:
        log.error(f"get_record_sell出错: {e}")

def get_stocks_with_high_increase(initial_list, y_day):
    price_data = get_price(
        initial_list, end_date=y_day, frequency='1d',
        fields=['close'], count=2, panel=False,
        fill_paused=False, skip_paused=True
    )
    if price_data.empty:
        return []
    df = price_data.pivot(index='time', columns='code', values='close')
    if len(df) < 2:
        return []
    pct = df.pct_change().iloc[-1]
    result = pct[pct > 0.07].index.tolist()
    return result

def prepare_stock_list(context):
    by_date = get_trade_days(end_date=context.previous_date, count=50)[0]
    all_s = get_all_securities(['stock'], date=by_date).index
    c_data = get_current_data()
    base_stocks = [
        s for s in all_s 
        if s[0] not in ('3', '4', '8', '9') 
        and not s.startswith('68')
        and not c_data[s].is_st 
        and not c_data[s].paused
        and '退' not in c_data[s].name 
        and 'ST' not in c_data[s].name
    ]
    return base_stocks

def filter_excessive_limit_up(stock_list, y_day):
    extreme_hl_df = get_hl_count_df(stock_list, y_day, 10)
    qualified_stocks = extreme_hl_df[extreme_hl_df['extreme_count'] < 3].index.tolist()
    excluded = set(stock_list) - set(qualified_stocks)
    if excluded:
        log.info(f"因前10日有3+一字/T字涨停被排除: {len(excluded)}只")
    return qualified_stocks
