# Clone from JoinQuant
# postId: c5d203933cd8f1060d77cfe93312eb36
# backtestId: a0f34f96b6501d4ad90ceee84e2f74bf
# title: 优化了半个月的ETF动量轮动策略

# 导入函数库
from jqdata import *
import pandas as pd
import numpy as np
import math
import datetime as dt

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('system','error')
    log.info('初始函数开始运行且全局只运行一次')
    set_slippage(PriceRelatedSlippage(0.001),type='fund')
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.0001, close_commission=0.0001, min_commission=5),
                   type='fund')
    g.defense_start_date = None
    # ===== 持仓数量 =====
    g.sum = 2
    
    # ===== ETF池 =====
    g.etf_pool = [
    # A股宽基
    '159949.XSHE',  # 创业板50 —— 保持不变
    # 科技
    '159995.XSHE',  # 芯片ETF华夏 —— [替换] 由159599改为159995
    '159559.XSHE',  # 机器人50ETF —— 保持不变
    '515880.XSHG',  # 通信ETF —— 保持不变
    '562950.XSHG',  # 消费电子ETF —— 保持不变
    '159852.XSHE',  # 软件ETF —— 保持不变
    '513310.XSHG',  # 中韩半导体ETF —— 保持不变
    '588000.XSHG',  # 科创50ETF —— 保持不变
    # 新能源/光伏
    '159875.XSHE',  # 新能源ETF嘉实 —— [替换] 由516160改为159875
    '159857.XSHE',  # 光伏ETF —— 保持不变
    # 消费
    '159928.XSHE',  # 消费ETF —— 保持不变
    # 港股
    '159920.XSHE',  # 恒生ETF —— 保持不变
    '513780.XSHG',  # 港股创新药50ETF —— 保持不变
    # 红利价值
    '510880.XSHG',  # 红利ETF —— 保持不变
    # 跨境
    '513520.XSHG',  # 日经ETF华夏 —— [替换] 由159866改为513520
    '513100.XSHG',  # 纳指ETF国泰 —— [替换] 由159660改为513100
    # 商品
    '518880.XSHG',  # 黄金ETF —— 保持不变
    '159652.XSHE',  # 有色50ETF —— 保持不变
    '159981.XSHE',  # 能源化工ETF —— [替换] 由510170改为159981
    '159985.XSHE',  # 豆粕ETF —— 保持不变
    # AI主题
    '159819.XSHE',  # 人工智能ETF易方达 —— [替换] 由517800改为159819
]
    
    # ===== 三层防御体系状态变量 =====
    g.regime = 'AGGRESSIVE'          # 当前生效的市场状态
    g.pending_regime = None          # 待确认的新状态
    g.pending_count = 0              # 连续相同信号的计数
    
    # ===== ATR止损追踪 =====
    g.high_since_entry = {}
    
    # ===== 动量周期参数 =====
    g.mom_periods = [10, 20, 40, 60]
    
    # ===== 新增全局变量 =====
    g.high_watermark = 0             # 账户历史最高净值
    g.lock_until = {}                # 锁定期 {etf: 剩余调仓日次数}
    g.weak_count = {}                # 连续弱势计数 {etf: count}
    
    # ===== 运行函数 =====
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    run_daily(trade, '9:40', reference_security='000300.XSHG')
    run_daily(daily_risk_check, '9:40', reference_security='000300.XSHG')
    
    g.position = {'ETF_HOLD': '0', 'STATUS': 0, 'HOLD_NUM': 0}


def before_market_open(context):
    log.info('函数运行时间(before_market_open)：' + str(context.current_dt.time()))
    print("持仓情况:{0}".format(g.position))


def after_market_close(context):
    log.info('函数运行时间(after_market_close)：' + str(context.current_dt.time()))


# ==================== 三层防御体系（市场为主，回撤为辅） ====================
def market_regime(context):
    """
    市场状态判断：趋势+波动率为主，账户回撤为辅
    新增：内部动量宽度择时——池中>80%品种下跌时，直接防御
    返回: 'AGGRESSIVE' / 'NEUTRAL' / 'DEFENSIVE'
    """
    # ===== 内部动量宽度判断 =====
    internal_defense = False
    negative_count = 0
    total_checked = 0
    
    for etf in g.etf_pool:
        try:
            df_ret = attribute_history(etf, 21, '1d', ['close'], skip_paused=True)
            if df_ret is not None and len(df_ret) >= 21:
                ret_20d = df_ret['close'].iloc[-1] / df_ret['close'].iloc[-21] - 1
                total_checked += 1
                if ret_20d < 0:
                    negative_count += 1
        except:
            continue
    
    if total_checked > 0:
        negative_ratio = negative_count / total_checked
        if negative_ratio > 0.50:
            internal_defense = True
            log.info(f'【内部宽度防御】池中{negative_count}/{total_checked}（{negative_ratio:.1%}）品种近20日下跌，触发防御')
    
    # ===== 内部宽度触发：立即防御，跳过防抖 =====
    if internal_defense:
        if g.regime != 'DEFENSIVE':
            old_regime = g.regime
            g.regime = 'DEFENSIVE'
            g.defense_start_date = context.current_dt
            g.pending_regime = None
            g.pending_count = 0
            log.info(f'【内部宽度】立即切换 {old_regime} → DEFENSIVE')
        return g.regime
    
    # ---- 市场原始信号 ----
    df = attribute_history('000300.XSHG', 120, '1d', ['close'])
    if df is None or len(df) < 120:
        return g.regime
    
    close = df['close']
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    
    price_above_ma20 = close.iloc[-1] > ma20.iloc[-1]
    ma20_above_ma60 = ma20.iloc[-1] > ma60.iloc[-1]
    slope_ma20 = np.polyfit(np.arange(5), ma20.iloc[-5:].values, 1)[0]
    trend_healthy = price_above_ma20 and ma20_above_ma60 and slope_ma20 > 0
    
    returns = close.pct_change().dropna()
    vol20 = returns.iloc[-20:].std() * np.sqrt(252)
    vol_hist = returns.rolling(20).std().dropna() * np.sqrt(252)
    vol_hist_500 = vol_hist.iloc[-500:] if len(vol_hist) >= 500 else vol_hist
    vol_percentile = (vol_hist_500 < vol20).mean()
    high_vol = vol_percentile > 0.80
    
    if trend_healthy and not high_vol:
        raw_signal = 'AGGRESSIVE'
    elif trend_healthy and high_vol:
        raw_signal = 'NEUTRAL'
    else:
        raw_signal = 'DEFENSIVE'
    
    # ---- 账户回撤刹车 ----
    total_value = context.portfolio.total_value
    if total_value > g.high_watermark:
        g.high_watermark = total_value
    if g.high_watermark <= 0:
        g.high_watermark = total_value
    drawdown = (g.high_watermark - total_value) / g.high_watermark if g.high_watermark > 0 else 0
    
    # 积极时回撤>15% 强制降为中性
    if raw_signal == 'AGGRESSIVE' and drawdown > 0.15:
        raw_signal = 'NEUTRAL'
        log.info(f'【回撤刹车】市场积极但账户回撤{drawdown:.2%}>15%，强制降为中性')
    # 积极/中性时回撤>25% 强制降为防御
    if raw_signal in ['AGGRESSIVE', 'NEUTRAL'] and drawdown > 0.25:
        raw_signal = 'DEFENSIVE'
        log.info(f'【回撤刹车】账户回撤{drawdown:.2%}>25%，强制防御')
    
    # ---- 防御退出保护：回撤<10%直接允许退出，或满足弹性条件 ----
    if g.regime == 'DEFENSIVE':
        if raw_signal != 'DEFENSIVE':
            if drawdown <= 0.10:
                pass
            elif drawdown <= 0.15 and trend_healthy and not high_vol:
                if g.defense_start_date is not None:
                    days_in_defense = (context.current_dt - g.defense_start_date).days
                    if days_in_defense > 30:
                        log.info(f'【弹性退出】防御已{days_in_defense}天，回撤{drawdown:.2%}且趋势健康，允许返回中性')
                    else:
                        raw_signal = 'DEFENSIVE'
                        log.info(f'【防御保护】趋势转好但防御未满30天，维持防御')
                else:
                    raw_signal = 'DEFENSIVE'
            else:
                raw_signal = 'DEFENSIVE'
                log.info(f'【防御保护】趋势转好但回撤仍{drawdown:.2%}>10%，维持防御')
    
    # ---- 连续两次确认机制 ----
    if raw_signal == g.regime:
        g.pending_regime = None
        g.pending_count = 0
        return g.regime
    else:
        if g.pending_regime == raw_signal:
            g.pending_count += 1
            if g.pending_count >= 2:
                old_regime = g.regime
                g.regime = raw_signal
                g.pending_regime = None
                g.pending_count = 0
                if g.regime == 'DEFENSIVE':
                    g.defense_start_date = context.current_dt
                log.info(f'【市场状态切换】{old_regime} → {g.regime} (回撤: {drawdown:.2%})')
                return g.regime
            else:
                return g.regime
        else:
            g.pending_regime = raw_signal
            g.pending_count = 1
            return g.regime

# ==================== ATR计算 ====================
def calc_atr(etf, period=20, end_date=None):
    try:
        price_df = get_price(etf, count=period+1, end_date=end_date, 
                            fields=['high', 'low', 'close'])
        if len(price_df) < period + 1:
            return None
        high = price_df['high']
        low = price_df['low']
        close = price_df['close']
        tr = np.maximum(high - low, 
                       np.maximum(abs(high - close.shift(1)), 
                                  abs(low - close.shift(1))))
        atr = tr.rolling(period).mean().iloc[-1]
        if np.isnan(atr) or atr <= 0:
            return None
        return atr
    except:
        return None


# ==================== 多周期动量打分 ====================
def multi_period_momentum(etf, periods, context):
    scores = []
    
    for p in periods:
        try:
            df = attribute_history(etf, p+1, '1d', ['close'], skip_paused=True)
            if df is None or len(df) < p:
                continue
            df['close'] = df['close'].fillna(0)
            if (df['close'] <= 0).any():
                continue
            
            y = np.log(df['close'].values)
            x = np.arange(len(y))
            slope, intercept = np.polyfit(x, y, 1)
            ann_ret = np.exp(slope * 250) - 1
            
            y_mean = np.mean(y)
            ss_res = np.sum((y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum((y - y_mean) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            r2_clipped = min(r2, 0.9)
            
            daily_ret = df['close'].pct_change().dropna()
            if len(daily_ret) > 0 and daily_ret.std() > 0:
                sharpe_short = daily_ret.mean() / daily_ret.std() * np.sqrt(252)
            else:
                sharpe_short = 0
            
            period_score = ann_ret * r2_clipped * max(0, sharpe_short)
            scores.append(period_score)
        except:
            continue
    
    if len(scores) == 0:
        return -999
    
    ret_signs = [1 if s > 0 else -1 for s in scores]
    consistency = sum(ret_signs) / len(ret_signs)
    raw_score = np.mean(scores)
    final_score = raw_score * (0.3 + 0.7 * consistency)
    return final_score


# ==================== ETF筛选与排名（动量+趋势质量+相对强度） ====================
def get_rank(context):
    mom_scores = []
    quality_scores = []
    rs_scores = []
    etf_list = []
    
    for etf in g.etf_pool:
        try:
            # ---- 多周期动量 ----
            mom_score = multi_period_momentum(etf, g.mom_periods, context)
            if mom_score == -999 or mom_score <= 0:
                continue
            
            # ---- 短期动量确认 ----
            df_short = attribute_history(etf, 10, '1d', ['close'], skip_paused=True)
            if df_short is None or len(df_short) < 10:
                continue
            recent_3_avg = df_short['close'].iloc[-3:].mean()
            ma5 = df_short['close'].iloc[-5:].mean()
            if recent_3_avg <= ma5:
                continue
            
            # ---- 趋势质量因子：近15日正收益天数占比 ----
            df_qual = attribute_history(etf, 16, '1d', ['close'], skip_paused=True)
            if df_qual is not None and len(df_qual) >= 16:
                daily_ret = df_qual['close'].pct_change().dropna()
                if len(daily_ret) >= 15:
                    pos_ratio = (daily_ret > 0).sum() / len(daily_ret)
                else:
                    pos_ratio = 0
            else:
                pos_ratio = 0
            
            # ---- 相对强度因子：近20日收益率 ----
            df_rs = attribute_history(etf, 21, '1d', ['close'], skip_paused=True)
            if df_rs is not None and len(df_rs) >= 21:
                ret_20d = df_rs['close'].iloc[-1] / df_rs['close'].iloc[-21] - 1
            else:
                ret_20d = 0
            
            mom_scores.append(mom_score)
            quality_scores.append(pos_ratio)
            rs_scores.append(ret_20d)
            etf_list.append(etf)
        except Exception as e:
            log.warn(f"处理 {etf} 时出错: {e}")
            continue
    
    if len(etf_list) == 0:
        return pd.DataFrame()
    
    # 百分位排名
    temp_df = pd.DataFrame({
        'etf': etf_list,
        'mom': mom_scores,
        'qual': quality_scores,
        'rs': rs_scores
    })
    temp_df['mom_rank'] = temp_df['mom'].rank(pct=True)
    temp_df['qual_rank'] = temp_df['qual'].rank(pct=True)
    temp_df['rs_rank'] = temp_df['rs'].rank(pct=True)
    
    # 新权重：动量50% + 质量25% + 相对强度25%
    temp_df['final_score'] = 0.50 * temp_df['mom_rank'] + 0.25 * temp_df['qual_rank'] + 0.25 * temp_df['rs_rank']
    
    rank_df = temp_df[['etf', 'final_score']].sort_values('final_score', ascending=False)
    return rank_df


# ==================== 交易逻辑 ====================
def trade(context):
    # 只在周一和周四调仓
    weekday = context.current_dt.weekday()
    if weekday not in [0, 3]:
        return
    
    log.info(f'===== 调仓日 {context.current_dt} =====')
    
    # 更新高水位
    total_value = context.portfolio.total_value
    if total_value > g.high_watermark:
        g.high_watermark = total_value
    if g.high_watermark <= 0:
        g.high_watermark = total_value
    
    # 获取市场状态
    regime = market_regime(context)
    log.info(f'当前市场状态: {regime}')
    
    # 获取排名
    rank_df = get_rank(context)
    if len(rank_df) == 0:
        log.info('没有符合条件的ETF')
        for etf in list(context.portfolio.positions.keys()):
            order_target_value(etf, 0)
            if etf in g.high_since_entry:
                del g.high_since_entry[etf]
        update_position_status(context)
        return
    
    current_hold = list(context.portfolio.positions.keys())
    
    # 确定候选池与资金
    if regime == 'DEFENSIVE':
        buy_candidates = ['518880.XSHG']
        available_value = total_value
        single_cap = 1.0
        log.info('防御模式：全仓黄金')
    elif regime == 'NEUTRAL':
        buy_candidates = rank_df.head(g.sum)['etf'].tolist()
        available_value = total_value * 0.7
        single_cap = 0.6
        log.info(f'中性模式：仓位降至70%，可用资金 {available_value:.2f}')
    else:  # AGGRESSIVE
        buy_candidates = rank_df.head(g.sum)['etf'].tolist()
        available_value = total_value
        single_cap = 0.6
    
    # ===== 锁定期递减：每调仓日，所有ETF锁定计数-1 =====
    expired = []
    for etf in list(g.lock_until.keys()):
        g.lock_until[etf] -= 1
        if g.lock_until[etf] <= 0:
            expired.append(etf)
    for etf in expired:
        del g.lock_until[etf]
    
    # 构建排名位置字典 (1-based)
    rank_pos = {}
    for idx, row in rank_df.iterrows():
        rank_pos[row['etf']] = idx + 1
    total_ranked = len(rank_df)
    elimination_threshold = int(0.7 * total_ranked)  # 后30%阈值
    
    # ---------- 卖出判断 ----------
    for etf in current_hold:
        # 防御模式下黄金不动
        if etf == '518880.XSHG' and regime == 'DEFENSIVE':
            continue
        
        should_sell = False
        sell_reason = ''
        
        # 不在候选前两名
        if etf not in buy_candidates:
            # 锁定期检查（评分淘汰受限，ATR已在每日风控处理）
            if etf in g.lock_until:
                log.info(f'{etf} 锁定期内（剩余{g.lock_until[etf]}次调仓），保留观察')
                continue
            
            # 评分淘汰：排名在30%之后，且连续两次确认
            if etf in rank_pos and rank_pos[etf] > elimination_threshold:
                g.weak_count[etf] = g.weak_count.get(etf, 0) + 1
                if g.weak_count[etf] < 2:
                    log.info(f'{etf} 排名{rank_pos[etf]}/{total_ranked}，首次进入后30%，待确认')
                    continue
                else:
                    should_sell = True
                    sell_reason = f'连续两次排名后30%（{rank_pos[etf]}/{total_ranked}），评分淘汰'
            else:
                # 不在30%后，但也不是前两名 → 若排名尚可则保留，否则卖出
                if etf in rank_pos and rank_pos[etf] <= elimination_threshold:
                    log.info(f'{etf} 排名{rank_pos[etf]}/{total_ranked}在前30%，保留观察')
                    continue
                else:
                    should_sell = True
                    sell_reason = '不在候选前两名且排名落后'
            
            # 重置弱势计数（若售出）
            if should_sell:
                g.weak_count.pop(etf, None)
        else:
            # 在新候选列表中，清除弱势计数
            g.weak_count.pop(etf, None)
        
        if should_sell:
            log.info(f'卖出 {etf}，原因: {sell_reason}')
            order_target_value(etf, 0)
            if etf in g.high_since_entry:
                del g.high_since_entry[etf]
            g.lock_until.pop(etf, None)
    
    # 刷新持仓
    current_hold = list(context.portfolio.positions.keys())
    
    # ---------- 买入/调整 ----------
    if len(buy_candidates) > 0:
        candidate_scores = []
        for etf in buy_candidates:
            if etf in rank_df['etf'].values:
                score = rank_df[rank_df['etf'] == etf]['final_score'].iloc[0]
            else:
                score = 0.001
            candidate_scores.append(max(score, 0.001))
        
        scores_arr = np.array(candidate_scores)
        weights = scores_arr / scores_arr.sum()
        weights = np.clip(weights, 0, single_cap)
        weights = weights / weights.sum()
        
        for i, etf in enumerate(buy_candidates):
            target_value = available_value * weights[i]
            
            if etf in context.portfolio.positions:
                pos = context.portfolio.positions[etf]
                current_value = pos.total_amount * pos.price
            else:
                current_value = 0
            
            if abs(current_value - target_value) > target_value * 0.05:
                order_target_value(etf, target_value)
                log.info(f'调整 {etf} 持仓到 {target_value:.2f} (权重 {weights[i]:.2%})')
                
                # 新买入或大幅加仓时设置锁定期（2次调仓，约3个交易日）
                if current_value < target_value * 0.5:
                    g.lock_until[etf] = 2
                    log.info(f'{etf} 设置锁定期（2次调仓）')
            
            # 初始化ATR追踪
            if etf not in g.high_since_entry and target_value > 0:
                try:
                    cur_p = get_price(etf, count=1, end_date=context.previous_date,
                                     fields=['close'])['close'].iloc[-1]
                    g.high_since_entry[etf] = cur_p
                except:
                    pass
    
    update_position_status(context)


def update_position_status(context):
    current_hold = list(context.portfolio.positions.keys())
    g.position['HOLD_NUM'] = len(current_hold)
    g.position['ETF_HOLD'] = ', '.join(current_hold) if current_hold else '0'
    g.position['STATUS'] = 1 if current_hold else 0
    if current_hold:
        log.info(f'当前持仓：{current_hold}')
        for etf in current_hold:
            pos = context.portfolio.positions[etf]
            log.info(f'{etf}: 数量{pos.total_amount}')


# ==================== 每日风控（仅ATR止损） ====================
def daily_risk_check(context):
    """每日ATR止损，不涉及评分退出"""
    current_hold = list(context.portfolio.positions.keys())
    if not current_hold:
        return
    
    regime = g.regime
    
    for etf in current_hold:
        should_sell = False
        sell_reason = ''
        
        # 防御模式黄金不触发ATR止损
        if etf == '518880.XSHG' and regime == 'DEFENSIVE':
            continue
        
        if etf in g.high_since_entry:
            position = context.portfolio.positions[etf]
            current_price = position.price if position.total_amount > 0 else None
            if current_price is not None and current_price > 0:
                if current_price > g.high_since_entry[etf]:
                    g.high_since_entry[etf] = current_price
                
                # ATR倍数：积极2.2，中性/防御1.5
                atr_mult = 2.2 if regime == 'AGGRESSIVE' else 1.5
                # 盈利移动止盈：持仓盈利超过12%时，收紧止损（系数×0.8）
                if position.avg_cost and position.avg_cost > 0:
                    profit_ratio = (current_price - position.avg_cost) / position.avg_cost
                    if profit_ratio > 0.15:
                        atr_mult *= 0.8
                        log.info(f'{etf} 盈利{profit_ratio:.2%}，止盈收紧，ATR系数调整为{atr_mult:.2f}')
                
                atr_value = calc_atr(etf, period=20, end_date=context.previous_date)
                if atr_value is not None:
                    stop_price = g.high_since_entry[etf] - atr_mult * atr_value
                    if current_price < stop_price:
                        should_sell = True
                        sell_reason = f'ATR止损 {current_price:.3f} < {stop_price:.3f}'
        
        if should_sell:
            log.info(f'【每日风控】卖出 {etf}，原因: {sell_reason}')
            order_target_value(etf, 0)
            if etf in g.high_since_entry:
                del g.high_since_entry[etf]
            g.lock_until.pop(etf, None)
            g.weak_count.pop(etf, None)