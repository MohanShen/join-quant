# Clone from JoinQuant
# postId: 814e303a5eac7e9f4e41d52dc8062744
# backtestId: 43914a094aaf26bd7f94043fe93f4672
# title: 基金筛选与轮动策略 V2.0

# 基金筛选与轮动
# 版本：V2.0
# 作者：星
# 创建日期：2026-3-18
# 最后修改：2026-3-18
# 策略思想：基于信息比率稳定性 + 近期动量筛选基金，动态权重分配，
#           流动性过滤，分批止盈 + 止损。


from jqdata import *
import pandas as pd
import numpy as np

# ==================== 策略参数（可调） ====================
g = {
    # 基金池重建间隔（交易日）
    'rebalance_interval': 60,
    # 止盈/止损检查间隔（交易日）
    'check_interval': 10,
    # 每次选取的基金数量
    'top_n': 10,
    # 止盈阈值（三档）
    'profit_levels': [0.15, 0.20, 0.25],   # 15%, 20%, 25%
    'sell_ratios': [1/3, 1/3, 1/3],         # 每档卖出比例（最后一档清仓）
    # 止损阈值
    'stop_loss': -0.10,                      # -10%
    # 流动性过滤：日均成交额下限（万元）
    'min_avg_amount': 500,                    # 500万元
    # 动量窗口（天）
    'momentum_window': 60,
    # 综合评分权重（IR稳定性 vs 近期动量）
    'weight_ir': 0.6,
    'weight_mom': 0.4,
    # 以下为内部状态变量
    'fund_pool': {},                          # 当前基金池 {code: weight}
    'days_since_last_rebalance': 0,           # 距离上次重建的天数
    'stop_win_level': {},                      # 记录各基金止盈阶段 {code: level}
}

def initialize(context):
    """初始化函数"""
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    # 设置基金交易费用
    set_order_cost(OrderCost(open_commission=0.0001, close_commission=0.0001,
                             close_tax=0, min_commission=0), type='fund')
    set_slippage(FixedSlippage(0.01))
    # 过滤订单相关INFO日志
    log.set_level('order', 'error')

    # 立即构建初始基金池
    rebuild_fund_pool(context)

    # 定时任务
    run_daily(market_open, time='9:30')
    run_daily(after_close, time='after_close', reference_security='000300.XSHG')

def market_open(context):
    """每日开盘交易逻辑"""
    # 先止损，再分批止盈，最后调整持仓
    check_stop_loss(context)
    check_profit_taking(context)      # 分批止盈
    sell_non_pool_holdings(context)
    buy_pool_funds(context)

def after_close(context):
    """收盘后更新计数器，重建基金池"""
    g['days_since_last_rebalance'] += 1
    if g['days_since_last_rebalance'] >= g['rebalance_interval']:
        rebuild_fund_pool(context)
        g['days_since_last_rebalance'] = 0

def check_stop_loss(context):
    """止损检查：亏损超过阈值则清仓"""
    if g['days_since_last_rebalance'] % g['check_interval'] != 0:
        return
    for code in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[code]
        if pos.total_amount == 0:
            continue
        cost = pos.acc_avg_cost
        price = get_current_data()[code].last_price
        ret = price / cost - 1
        if ret <= g['stop_loss']:
            order_target(code, 0)
            # 从基金池和止盈记录中移除
            if code in g['fund_pool']:
                del g['fund_pool'][code]
            if code in g['stop_win_level']:
                del g['stop_win_level'][code]
            log.info('止损卖出 %s，收益率 %.2f%%', code, ret * 100)

def check_profit_taking(context):
    """分批止盈检查"""
    if g['days_since_last_rebalance'] % g['check_interval'] != 0:
        return
    levels = g['profit_levels']
    sell_ratios = g['sell_ratios']

    for code in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[code]
        if pos.total_amount == 0:
            continue
        # 初始化止盈阶段
        if code not in g['stop_win_level']:
            g['stop_win_level'][code] = 0

        cost = pos.acc_avg_cost
        price = get_current_data()[code].last_price
        ret = price / cost - 1

        current_level = g['stop_win_level'][code]
        # 从当前阶段往后检查是否触发更高档位
        for i in range(current_level, len(levels)):
            if ret >= levels[i]:
                # 触发第i档止盈
                if i == len(levels) - 1:   # 最后一档，清仓
                    order_target(code, 0)
                    del g['stop_win_level'][code]
                    if code in g['fund_pool']:
                        del g['fund_pool'][code]
                    log.info('止盈清仓 %s，收益率 %.2f%%', code, ret * 100)
                else:
                    # 卖出相应比例
                    sell_shares = int(pos.total_amount * sell_ratios[i])
                    if sell_shares > 0:
                        # 调整为100的整数倍
                        sell_shares = (sell_shares // 100) * 100
                        if sell_shares > 0:
                            order(code, -sell_shares)   # 卖出
                            log.info('分批止盈 %s 第%d档，卖出 %d 份，收益率 %.2f%%',
                                     code, i+1, sell_shares, ret * 100)
                    # 更新止盈阶段
                    g['stop_win_level'][code] = i + 1
                break   # 只触发最高档

def sell_non_pool_holdings(context):
    """卖出不在基金池的持仓"""
    for code in list(context.portfolio.positions.keys()):
        if code not in g['fund_pool']:
            if context.portfolio.positions[code].total_amount > 0:
                order_target(code, 0)
                log.info('卖出非池中基金 %s', code)

def buy_pool_funds(context):
    """买入基金池中未持仓或持仓量为0的基金"""
    total_value = context.portfolio.total_value
    for code, weight in g['fund_pool'].items():
        # 如果已有持仓且持仓量>0，跳过
        if code in context.portfolio.positions and context.portfolio.positions[code].total_amount > 0:
            continue
        # 确认可交易
        try:
            if get_current_data()[code].last_price is None:
                continue
        except:
            continue

        target_value = int(weight * total_value)
        if target_value > 0:
            order_target_value(code, target_value)
            # 重置该基金的止盈阶段（新买入）
            g['stop_win_level'][code] = 0
            log.info('买入基金 %s，目标市值 %d', code, target_value)

def rebuild_fund_pool(context):
    """重建基金池：综合评分 + 流动性过滤 + 动态权重"""
    log.info('开始重建基金池，日期：%s', context.current_dt)

    # 获取综合评分DataFrame（索引为code，包含score列）
    scored_df = get_composite_score(context)
    if scored_df.empty:
        log.warning('未选出任何基金，基金池保持不变')
        return

    # 流动性过滤：剔除日均成交额低于阈值的基金
    filtered = filter_by_liquidity(scored_df, context)
    if filtered.empty:
        log.warning('通过流动性过滤的基金为空，基金池保持不变')
        return

    # 取前top_n只
    final_codes = filtered.head(g['top_n']).index.tolist()

    # 计算动态权重：基于得分归一化
    scores = filtered.loc[final_codes, 'score']
    total_score = scores.sum()
    weights = (scores / total_score).tolist()

    # 更新基金池
    g['fund_pool'] = {code: w for code, w in zip(final_codes, weights)}
    log.info('基金池更新完毕，包含基金：%s', list(g['fund_pool'].keys()))

def get_composite_score(context):
    """
    计算每只基金的复合评分：
    score = weight_ir * IR稳定性得分 + weight_mom * 动量得分
    IR稳定性得分 = 1 / (排名方差 + 1e-6)   # 方差越小得分越高
    动量得分 = 过去momentum_window天的超额收益（基金收益-基准收益）均值，再归一化到[0,1]
    """
    window_len = 60
    total_days = 545
    today = context.current_dt

    # 获取所有LOF/ETF基金
    all_funds = get_all_securities(['lof', 'etf'])
    earliest_start = get_trade_days(end_date=today, count=total_days)[0]
    valid_codes = []
    for code in all_funds.index:
        info = get_security_info(code)
        if info.start_date <= earliest_start:
            valid_codes.append(code)

    if not valid_codes:
        return pd.DataFrame()

    # 获取过去total_days个交易日
    trading_days = get_trade_days(end_date=today, count=total_days)
    num_windows = total_days // window_len

    # 计算IR稳定性（排名方差）
    rank_df = pd.DataFrame(index=valid_codes)
    for i in range(num_windows):
        start = trading_days[i*window_len]
        end = trading_days[i*window_len + window_len - 1]
        ir_list = []
        for code in valid_codes:
            ir = compute_ir(code, start, end)
            ir_list.append(ir)
        ir_series = pd.Series(ir_list, index=valid_codes)
        rank_df[f'win_{i}'] = ir_series.rank(ascending=False, method='min')

    rank_df['variance'] = rank_df.var(axis=1)
    # IR稳定性得分：方差倒数（越大越稳定）
    rank_df['ir_score'] = 1 / (rank_df['variance'] + 1e-6)

    # 计算近期动量（过去momentum_window天超额收益均值）
    mom_window = g['momentum_window']
    mom_start = trading_days[-mom_window]
    mom_end = today

    excess_returns = []
    for code in valid_codes:
        er = compute_avg_excess_return(code, mom_start, mom_end)
        excess_returns.append(er)
    excess_series = pd.Series(excess_returns, index=valid_codes)

    # 动量得分：将超额收益归一化到[0,1]
    min_er = excess_series.min()
    max_er = excess_series.max()
    if max_er > min_er:
        mom_score = (excess_series - min_er) / (max_er - min_er)
    else:
        mom_score = pd.Series(0.5, index=valid_codes)

    # 综合评分
    rank_df['mom_score'] = mom_score
    rank_df['score'] = (g['weight_ir'] * rank_df['ir_score'] +
                        g['weight_mom'] * rank_df['mom_score'])
    # 按得分降序排序
    rank_df.sort_values('score', ascending=False, inplace=True)
    return rank_df[['score']]

def compute_ir(code, start, end):
    """计算单只基金在区间内的信息比率"""
    fund = get_price(code, start, end, '1d', ['close'], fq='post')
    bench = get_price('000300.XSHG', start, end, '1d', ['close'], fq='post')
    if fund.empty or bench.empty:
        return np.nan
    fund_ret = fund['close'].pct_change().dropna()
    bench_ret = bench['close'].pct_change().dropna()
    combined = pd.concat([fund_ret, bench_ret], axis=1, join='inner')
    if len(combined) < 2:
        return np.nan
    excess = combined.iloc[:,0] - combined.iloc[:,1]
    return excess.mean() / (excess.std() + 1e-6)

def compute_avg_excess_return(code, start, end):
    """计算基金相对于沪深300的平均日超额收益"""
    fund = get_price(code, start, end, '1d', ['close'], fq='post')
    bench = get_price('000300.XSHG', start, end, '1d', ['close'], fq='post')
    if fund.empty or bench.empty:
        return 0
    fund_ret = fund['close'].pct_change().dropna()
    bench_ret = bench['close'].pct_change().dropna()
    combined = pd.concat([fund_ret, bench_ret], axis=1, join='inner')
    if len(combined) == 0:
        return 0
    excess = combined.iloc[:,0] - combined.iloc[:,1]
    return excess.mean()

def filter_by_liquidity(df, context):
    """
    流动性过滤：剔除日均成交额低于 min_avg_amount（万元）的基金。
    使用过去60天的平均成交额（万元）作为流动性指标。
    """
    codes = df.index.tolist()
    liquid_codes = []
    end_date = context.current_dt
    start_date = get_trade_days(end_date=end_date, count=60)[0]

    for code in codes:
        # 获取过去60天的成交额（单位：元）
        df_amount = get_price(code, start_date, end_date, '1d', fields=['money'], skip_paused=True)
        if df_amount.empty:
            continue
        avg_amount = df_amount['money'].mean() / 10000   # 转换为万元
        if avg_amount >= g['min_avg_amount']:
            liquid_codes.append(code)

    if not liquid_codes:
        return pd.DataFrame()
    return df.loc[liquid_codes]