# Clone from JoinQuant
# postId: 320f81d5d949368ca5bd85c0e86f17fd
# backtestId: 3588c419c4a036dc905d8a0fcea62d76
# title: 纯干货-教你从0到1搭建机器学习选股策略

# ==============================================================
# 文件名：多因子选股策略
# 运行环境：聚宽【策略环境】
# 回测区间：2025-01-01 到 2026-05-21
# 基准：399101.XSHE（中证小市值指数）
#
# 使用前提：
#   必须先在研究环境运行 train_model_jq.py，生成 model_lgb_week.pkl
#   策略中 read_file 会自动读取研究环境保存的模型文件
# ==============================================================

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import pickle
from sklearn.preprocessing import StandardScaler


# ============================================================
# 初始化函数
# ============================================================
def initialize(context):
    # 基准设置
    set_benchmark('399101.XSHE')
    # 使用真实价格
    set_option('use_real_price', True)
    # 开启防未来函数检查
    set_option("avoid_future_data", True)
    # 滑点（万分之三）
    set_slippage(FixedSlippage(3/10000))
    # 交易成本
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5
    ), type='stock')
    # 只显示错误级别的订单日志
    log.set_level('order', 'error')

    # 全局变量
    g.stock_num_min = 3   # 最小持股数
    g.stock_num_max = 6   # 最大持股数
    g.hold_list = []      # 当前持仓
    g.yesterday_HL_list = []  # 昨日涨停股

    # 加载模型（必须与 train_model_jq.py 中 MODEL_FILE 一致）
    g.model = pickle.loads(read_file('model_lgb_week.pkl'))
    log.info('模型加载成功')

    # 因子列表（必须与训练时 FACTOR_LIST 完全一致，顺序也要一致）
    g.factor_list = [
        'account_receivable_turnover_days', 'BBIC', 'VROC12', 'TVMA6',
        'EBIT', 'cash_earnings_to_price_ratio', 'net_non_operating_income_to_total_profit',
        'operating_revenue_growth_rate', 'net_working_capital', 'VR', 'fixed_asset_ratio',
        'Variance120', 'VDEA', 'WVAD', 'MAWVAD', 'surplus_reserve_fund_per_share',
        'inventory_turnover_days', 'net_operating_cash_flow_coverage', 'current_ratio',
        'Skewness20', 'intangible_asset_ratio', 'MLEV', 'Kurtosis20', 'debt_to_equity_ratio',
        'VOL10', 'DAVOL10', 'inventory_turnover_rate', 'long_debt_to_working_capital_ratio',
        'ATR6', 'capital_reserve_fund_per_share', 'Kurtosis120', 'Skewness120',
        'debt_to_tangible_equity_ratio', 'VMACD', 'momentum', 'AR',
        'current_asset_turnover_rate', 'operating_profit_to_total_profit',
        'equity_to_fixed_asset_ratio', 'book_to_price_ratio', 'ACCA',
        'net_operate_cash_flow_per_share', 'net_profit_growth_rate',
        'adjusted_profit_to_total_profit', 'asset_impairment_loss_ttm', 'ARBR',
        'accounts_payable_turnover_rate', 'non_recurring_gain_loss',
        'account_receivable_turnover_rate', 'VEMA26', 'VOSC', 'cube_of_size',
        'growth', 'earnings_yield', 'beta', 'arron_down_25', 'single_day_VPT_12',
        'Volume1M', 'arron_up_25', 'MASS', 'single_day_VPT', 'Rank1M',
        'cash_flow_to_price_ratio'
    ]

    # 调度任务
    run_daily(prepare_stock_list, '9:05')     # 每天更新持仓和涨停列表
    run_weekly(weekly_adjustment, 1, '9:30')  # 每周一调仓
    run_daily(check_limit_up, '14:00')        # 每天检查涨停是否打开


# ============================================================
# 截面预处理函数
# 【关键】必须与训练脚本 cross_section_preprocess 完全一致。
# 模型训练时每个截面都做了：去极值→填充→Z-Score标准化。
# 推理时不做这一步，模型的分裂阈值与原始因子值不匹配，预测结果无效。
# ============================================================
def cross_section_preprocess(df_factor):
    result = df_factor.copy().astype(float)

    # 1. 去极值（截面内1%~99%分位数截断）
    for col in result.columns:
        q1  = result[col].quantile(0.01)
        q99 = result[col].quantile(0.99)
        result[col] = result[col].clip(lower=q1, upper=q99)

    # 2. 填充缺失值（截面中位数）
    result = result.fillna(result.median())

    # 3. Z-Score 标准化
    scaler = StandardScaler()
    arr = scaler.fit_transform(result)
    result = pd.DataFrame(arr, index=result.index, columns=result.columns)

    return result


# ============================================================
# 每日准备：更新持仓和涨停列表
# ============================================================
def prepare_stock_list(context):
    g.hold_list = list(context.portfolio.positions.keys())

    if g.hold_list:
        df = get_price(
            g.hold_list,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1,
            panel=False,
            fill_paused=False
        )
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []


# ============================================================
# 选股函数：用模型对当日候选股票打分，取前N名
# ============================================================
def get_stock_list(context):
    yesterday = context.previous_date

    # --- 第一步：构建候选股票池（过滤不可交易的股票）---
    stocks = get_index_stocks('399101.XSHE', yesterday)
    stocks = filter_kcbj_stock(stocks)        # 去掉科创北交创业板
    stocks = filter_st_stock(stocks)           # 去掉ST
    stocks = filter_paused_stock(stocks)       # 去掉停牌
    stocks = filter_new_stock(context, stocks) # 去掉新股
    stocks = filter_limitup_stock(context, stocks)   # 去掉涨停（买不进）
    stocks = filter_limitdown_stock(context, stocks) # 去掉跌停（不持有）

    if len(stocks) < g.stock_num_min:
        log.info('候选股票数量不足{}只，跳过本周调仓'.format(g.stock_num_min))
        return []

    # --- 第二步：获取因子数据 ---
    factor_data = get_factor_values(stocks, g.factor_list, end_date=yesterday, count=1)

    df_raw = pd.DataFrame(index=stocks, columns=g.factor_list, dtype=float)
    for factor in g.factor_list:
        # reindex 确保行顺序与 stocks 一致，防止因子与股票错位
        df_raw[factor] = factor_data[factor].iloc[0].reindex(stocks).values

    # --- 第三步：截面预处理（必须与训练时完全一致）---
    df_processed = cross_section_preprocess(df_raw)
    log.info('候选股票数={}, 截面预处理完成'.format(len(df_processed)))

    # --- 第四步：模型打分并排序 ---
    scores = g.model.predict(df_processed)

    df_score = pd.DataFrame({'score': scores}, index=stocks)
    df_score = df_score.sort_values('score', ascending=False)

    # --- 第五步：动态确定持股数量（3~6只）---
    stock_num = min(g.stock_num_max, max(g.stock_num_min, len(df_score)))
    selected = df_score.index.tolist()[:stock_num]

    log.info('本周选股：{}'.format(selected))
    return selected


# ============================================================
# 每周调仓
# ============================================================
def weekly_adjustment(context):
    target_list = get_stock_list(context)

    # 卖出不在目标列表的持仓（昨日涨停的除外，等涨停打开再卖）
    for stock in g.hold_list:
        if stock not in target_list and stock not in g.yesterday_HL_list:
            log.info('卖出 [{}]'.format(stock))
            close_position(context.portfolio.positions[stock])
        else:
            log.info('继续持有 [{}]'.format(stock))

    # 买入目标列表中的新股票
    position_count = len(context.portfolio.positions)
    target_num = len(target_list)

    if target_num > position_count:
        available_cash = context.portfolio.cash
        buy_count = target_num - position_count
        if buy_count > 0:
            value_per_stock = available_cash / buy_count
            for stock in target_list:
                if context.portfolio.positions[stock].total_amount == 0:
                    if open_position(stock, value_per_stock):
                        if len(context.portfolio.positions) == target_num:
                            break


# ============================================================
# 每日检查昨日涨停是否打开
# ============================================================
def check_limit_up(context):
    now_time = context.current_dt
    for stock in g.yesterday_HL_list:
        current_data = get_price(
            stock,
            end_date=now_time,
            frequency='1m',
            fields=['close', 'high_limit'],
            skip_paused=False,
            fq='pre',
            count=1,
            panel=False,
            fill_paused=True
        )
        if len(current_data) > 0 and current_data.iloc[0]['close'] < current_data.iloc[0]['high_limit']:
            log.info('[{}] 涨停打开，卖出'.format(stock))
            close_position(context.portfolio.positions[stock])
        else:
            log.info('[{}] 仍在涨停，继续持有'.format(stock))


# ============================================================
# 交易工具函数
# ============================================================
def open_position(security, value):
    order = order_target_value(security, value)
    if order is not None and order.filled > 0:
        return True
    return False


def close_position(position):
    order = order_target_value(position.security, 0)
    if order is not None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False


# ============================================================
# 股票过滤函数
# ============================================================
def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].paused]


def filter_st_stock(stock_list):
    """过滤ST及退市风险股票"""
    current_data = get_current_data()
    return [s for s in stock_list
            if not current_data[s].is_st
            and 'ST' not in current_data[s].name
            and '*' not in current_data[s].name
            and '退' not in current_data[s].name]


def filter_kcbj_stock(stock_list):
    """过滤科创板(68开头)和北交所(4/8开头)，保留创业板(3开头)"""
    # 与训练脚本 filter_kcbj 保持完全一致，不过滤创业板。
    # 原因：399101.XSHE 含大量创业板股票，过滤后样本不足30只。
    return [s for s in stock_list if not (
        s[0] == '4' or s[0] == '8' or s[:2] == '68'
    )]


def filter_limitup_stock(context, stock_list):
    """过滤涨停股（非持仓中的）"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [s for s in stock_list
            if s in context.portfolio.positions.keys()
            or last_prices[s][-1] < current_data[s].high_limit]


def filter_limitdown_stock(context, stock_list):
    """过滤跌停股（非持仓中的）"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [s for s in stock_list
            if s in context.portfolio.positions.keys()
            or last_prices[s][-1] > current_data[s].low_limit]


def filter_new_stock(context, stock_list):
    """过滤上市不足375天的新股"""
    yesterday = context.previous_date
    return [s for s in stock_list
            if not yesterday - get_security_info(s).start_date < datetime.timedelta(days=375)]
