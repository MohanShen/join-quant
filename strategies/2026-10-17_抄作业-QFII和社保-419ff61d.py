# Clone from JoinQuant
# postId: 419ff61d0e78854276e25a82a83ab497
# backtestId: 749107acab59e9300cf6ebc7607133fe
# title: 抄作业-QFII和社保

# 跟随QFII选股 + 多因子动量轮动策略

from jqdata import *
import numpy as np
import pandas as pd
import datetime
from scipy.stats import zscore

def initialize(context):
    # ================= 基础设置 =================
    set_benchmark('000985.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.002))
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001, 
        open_commission=0.0003, close_commission=0.0003, 
        close_today_commission=0, min_commission=5
    ), type='stock')
    log.set_level('order', 'error')

    # ================= 策略参数 =================
    g.qfii_pool = []                # QFII选股得出的股票池
    g.pool_size = 20                # QFII选股得出的股票池大小
    g.top_n = 2                     # 买入并持有的股票数量
    g.top_m = 3                    # 卖出判断的排名阈值，不在前M名则卖出
    g.momentum_window = 25          # 动量等指标计算窗口(交易日)
    
    # 复合Z-Score因子权重 [动量, 卡尔马比率, 线性回归R平方, 夏普比率]
    g.factor_weights = [0.0, 0.0, 1.0, 0.0] 
    
    g.stop_loss_pct = -0.3         # 止损比例：-10%
    g.stop_loss_dict = {}           # 记录止损股票及日期 {code: date}
    g.stop_loss_cooldown = 7        # 止损冷却期(天)
    
    # ================= 定时任务 =================
    # 1. 每月第一个交易日执行QFII选股
    run_monthly(select_qfii_stocks, 1, time='9:30')
    
    # 2. 每天打分，并分前后2分钟执行卖出和买入
    run_daily(calculate_scores, time='9:30')
    run_daily(sell_stocks, time='9:31')
    run_daily(buy_stocks, time='9:33')
    
    # 3. 每天清理过期的止损记录
    run_daily(clean_stop_loss_dict, time='15:00')


# ============================================================================
# 1. 选股模块 (每月执行)
# ============================================================================

def filter_all_stock2(context, stock_list):
    # 过滤次新股（新股、老股的分界日期，两种指定方法）
    # 新老股的分界日期, 自然日180天
    # by_date = context.previous_date - datetime.timedelta(days=180)
    # 新老股的分界日期，120个交易日
    by_date = get_trade_days(end_date=context.previous_date, count=375)[0]
    all_stocks = get_all_securities(date=by_date).index.tolist()
    stock_list = list(set(stock_list).intersection(set(all_stocks)))

    curr_data = get_current_data()
    return [stock for stock in stock_list if not (
            stock.startswith(( '68', '4', '8','3')) or  # 创业，科创，北交所
            curr_data[stock].paused or
            curr_data[stock].is_st or  # ST
            ('ST' in curr_data[stock].name) or
            ('*' in curr_data[stock].name) or
            ('退' in curr_data[stock].name) or
            (curr_data[stock].day_open == curr_data[stock].high_limit) or  # 涨停开盘, 其它时间用last_price
            (curr_data[stock].day_open == curr_data[stock].low_limit)  # 跌停开盘, 其它时间用last_price
    )]

def get_latest_report_date(date):
    """根据给定日期，推算最近的季度末期 (YYYY-MM-DD)"""
    year = date.year
    month = date.month
    if month >= 10:
        return f"{year}-09-30"
    elif month >= 7:
        return f"{year}-06-30"
    elif month >= 4:
        return f"{year}-03-31"
    else:
        return f"{year - 1}-12-31"

def select_qfii_stocks(context):
    """每月执行：筛选全A，并根据QFII持股占比选出Top50"""
    # 1. 获取初始股票池并复用过滤函数
    initial_pool = get_index_stocks('000985.XSHG', date=context.previous_date)
    filtered_pool = filter_all_stock2(context, initial_pool)
    
    if not filtered_pool:
        log.warning("初始股票池过滤后为空！")
        g.qfii_pool = []
        return

    # 2. 查询最新报告期的流通股东数据
    yesterday = context.previous_date
    latest_end_date = get_latest_report_date(yesterday)
    
    # 分批查询避免API限制
    batch_size = 2000
    all_dfs = []
    for i in range(0, len(filtered_pool), batch_size):
        batch = filtered_pool[i : i+batch_size]
        q = query(
            finance.STK_SHAREHOLDER_FLOATING_TOP10.code,
            finance.STK_SHAREHOLDER_FLOATING_TOP10.share_ratio,
            finance.STK_SHAREHOLDER_FLOATING_TOP10.end_date,
            finance.STK_SHAREHOLDER_FLOATING_TOP10.pub_date
        ).filter(
            finance.STK_SHAREHOLDER_FLOATING_TOP10.code.in_(batch),
            # finance.STK_SHAREHOLDER_FLOATING_TOP10.shareholder_class == '社保基金',
            finance.STK_SHAREHOLDER_FLOATING_TOP10.shareholder_class.in_(['QFII', '社保基金']),
            # finance.STK_SHAREHOLDER_FLOATING_TOP10.shareholder_name.like('%全国社保基金%'),
            finance.STK_SHAREHOLDER_FLOATING_TOP10.end_date == latest_end_date, # 优化：直接限定最新报告期，提升速度
            finance.STK_SHAREHOLDER_FLOATING_TOP10.pub_date <= yesterday # 修复：使用昨天作为截止日，避免未来数据
        )
        df = finance.run_query(q)
        if df is not None and not df.empty:
            all_dfs.append(df)
       
    if not all_dfs:
        log.warning(f"未查询到 {latest_end_date} 报告期的QFII持股数据！")
        g.qfii_pool = []
        return
        
    all_holdings_df = pd.concat(all_dfs, ignore_index=True)
    
    # 3. 按股票汇总QFII持股比例，同一股票多个QFII持仓比例相加
    qfii_ratio = all_holdings_df.groupby('code')['share_ratio'].sum()
    
    # 4. 选出占比最高的 Top 50
    qfii_ratio = qfii_ratio.sort_values(ascending=False)
    g.qfii_pool = qfii_ratio.head(g.pool_size).index.tolist()
    
    log.info(f"【月度选股】最新报告期: {latest_end_date}, QFII重仓Top50池更新完成，共 {len(g.qfii_pool)} 只股票。")


# ============================================================================
# 2. 打分模块 (每天执行 - 纯向量化计算)
# ============================================================================

def calculate_scores(context):
    """每天对QFII池进行多因子Z-Score打分"""
    if not g.qfii_pool:
        g.sorted_scores = pd.Series(dtype=float)
        return

    N = g.momentum_window
    
    # 1. 只获取一次行情数据
    prices = get_price(g.qfii_pool, end_date=context.previous_date, 
                       count=N, frequency='1d', 
                       fields=['close'], panel=False)
    
    if prices.empty or len(prices) < N:
        log.warning("行情数据长度不足，跳过打分")
        g.sorted_scores = pd.Series(dtype=float)
        return
        
    # 转为透视表，index为日期，columns为股票代码，值为close
    price_df = prices.pivot(index='time', columns='code', values='close')
    
    # ================= 向量化计算4大因子 =================
    
    # 因子1: 动量 (N日区间收益率)
    momentum = price_df.iloc[-1] / price_df.iloc[0] - 1
        
    # 因子2: 卡尔马比率 (年化收益率 / 最大回撤)
    cum_max = price_df.cummax()
    drawdown = (price_df - cum_max) / cum_max
    max_dd = drawdown.min().abs()
    ann_return = (price_df.iloc[-1] / price_df.iloc[0]) ** (250.0 / N) - 1
    # 防止除以0
    calmar = ann_return / max_dd.replace(0, np.nan)
    
    # 因子3: 线性回归R平方 (衡量趋势的稳定性)
    # 原理：一元线性回归的 R平方 等于 X和Y的皮尔逊相关系数的平方
    # X 是时间序列 0, 1, ..., N-1，Y 是价格序列
    t = np.arange(N)
    t_centered = t - t.mean()
    sum_t_sq = np.sum(t_centered ** 2)
    
    # Y的中心化
    y_mean = price_df.mean()
    y_centered = price_df.subtract(y_mean, axis=1)
    
    # 计算分子: sum((t-t_mean)*(y-y_mean))，利用矩阵乘法加速
    cross_sum = y_centered.values.T.dot(t_centered)
    sum_y_sq = (y_centered ** 2).sum().values
    
    # 相关系数 r = cross_sum / sqrt(sum_t_sq * sum_y_sq)
    denom = np.sqrt(sum_t_sq * sum_y_sq)
    # 安全除法，避免分母为0报错
    r = np.divide(cross_sum, denom, out=np.zeros_like(cross_sum), where=denom!=0)
    r2 = pd.Series(r ** 2, index=price_df.columns)
    
    # 因子4: 夏普比率 (日收益率均值 / 标准差 * sqrt(250))
    daily_returns = price_df.pct_change().dropna()
    sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(250)
    
    # ================= 组装因子矩阵 =================
    factors = pd.DataFrame({
        'momentum': momentum,
        'calmar': calmar,
        'r2': r2,
        'sharpe': sharpe
    })
    
    # ================= 复合Z-Score打分 =================
    # 先计算每个因子的横截面排名百分比，然后再做Z-Score标准化
    score_df = pd.DataFrame(index=factors.index)
    factor_names = ['momentum', 'calmar', 'r2', 'sharpe']
    
    for fname in factor_names:
        # 截面排名转换为百分位 (0~1)
        rank_pct = factors[fname].rank(pct=True)
        # 对排名进行Z-Score标准化
        score_df[fname] = zscore(rank_pct.fillna(rank_pct.mean()))
        
    # 加权求和
    weights = np.array(g.factor_weights)
    score_df['total_score'] = score_df[factor_names].dot(weights)
    
    # 降序排列
    g.sorted_scores = score_df['total_score'].sort_values(ascending=False)
 

# ============================================================================
# 3. 交易模块 (卖出买入分离)
# ============================================================================

def sell_stocks(context):
    """卖出不在Top M中的股票，以及触发止损的股票"""
    if not hasattr(g, 'sorted_scores') or g.sorted_scores.empty:
        return
        
    top_m_set = set(g.sorted_scores.head(g.top_m).index)
    
    for stock in list(context.portfolio.positions):
        # 获取当前持仓信息
        pos = context.portfolio.positions[stock]
        current_data = get_current_data()
        
        # 1. 止损判断：亏损10%
        if pos.avg_cost > 0:
            loss_pct = (pos.price - pos.avg_cost) / pos.avg_cost
            if loss_pct <= g.stop_loss_pct:
                if not current_data[stock].paused and not (current_data[stock].last_price==current_data[stock].low_limit):
                    log.info(f"【止损卖出】{stock} 亏损比例: {loss_pct*100:.2f}%")
                    order_target_value(stock, 0)
                    g.stop_loss_dict[stock] = context.current_dt.date()
                    continue
        
        # 2. 排名判断：不在 Top M 中则卖出
        if stock not in top_m_set:
            if not current_data[stock].paused and not (current_data[stock].last_price==current_data[stock].low_limit):
                log.info(f"【调仓卖出】{stock} 不在Top{g.top_m}中，当前排名得分落选。")
                order_target_value(stock, 0)


def buy_stocks(context):
    """等权买入Top N，遵守止损冷却期及仓位控制规则"""
    if not hasattr(g, 'sorted_scores') or g.sorted_scores.empty:
        return
        
    top_n_list = g.sorted_scores.head(g.top_n).index.tolist()
    log.info(f"list:{top_n_list}")
    # 过滤掉近7天内止损过的股票
    today = context.current_dt.date()
    available_top_n = []
    for stock in top_n_list:
        if stock in g.stop_loss_dict:
            days_since_stop = (today - g.stop_loss_dict[stock]).days
            if days_since_stop <= g.stop_loss_cooldown:
                continue
        available_top_n.append(stock)
        
    if not available_top_n:
        return
        
    # 获取当前未持有的目标股票
    current_holdings = set(context.portfolio.positions.keys())
    stocks_to_buy = [s for s in available_top_n if s not in current_holdings]
    log.info(f"stocks_to_buy:{stocks_to_buy}")
    if not stocks_to_buy:
        return
        
    total_value = context.portfolio.total_value
    available_cash = context.portfolio.available_cash
    
    # 仓位判断逻辑
    target_value_per_stock = total_value / g.top_n
    cash_ratio = available_cash / total_value
    threshold_ratio = 1.0 / g.top_n
    
    current_data = get_current_data()
    
    if cash_ratio > threshold_ratio:
        # 如果剩余仓位 > 1/N，则买入未持有的TopN，每只仓位为1/N
        for stock in stocks_to_buy:
            if current_data[stock].paused or (current_data[stock].last_price==current_data[stock].high_limit):
                log.info(f"因涨停或停牌【无法买】{stock}")    
                continue
            # 再次检查可用资金是否足够 1/N
            if context.portfolio.available_cash >= target_value_per_stock:
                log.info(f"【正常买入】{stock}, 目标金额: {target_value_per_stock:.2f}")
                order_target_value(stock, target_value_per_stock)
            else:
                # 资金不足以买完整的1/N，跳出循环等待下次机会或资金释放
                break
                
    elif available_cash > 5000:
        # 如果剩余仓位 < 1/N 且大于 5000，则全部用来购买未持有的TopN中的一只
        stock = stocks_to_buy[0]
        if not current_data[stock].paused and (current_data[stock].last_price==current_data[stock].high_limit):
            log.info(f"【零头买入】{stock}, 可用资金: {available_cash:.2f}")
            order_value(stock, available_cash)


# ============================================================================
# 4. 辅助模块
# ============================================================================

def clean_stop_loss_dict(context):
    """清理超过7天的止损记录，避免字典膨胀"""
    today = context.current_dt.date()
    expired_keys = [k for k, v in g.stop_loss_dict.items() if (today - v).days > g.stop_loss_cooldown]
    for k in expired_keys:
        g.stop_loss_dict.pop(k, None)
