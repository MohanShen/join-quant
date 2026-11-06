# Clone from JoinQuant
# postId: bd94652a1f7bdbac0d03af6a43164aa5
# backtestId: b7808c9bf6f22285ff0517b23feee8c1
# title: 周一主升


import numpy as np
import pandas as pd
import math

# 初始化函数 
def initialize(context):
    set_benchmark('513100.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.001))
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001, 
                             close_commission=0.0001, close_today_commission=0, min_commission=0), type='fund')
    log.set_level('system', 'error')

    # ==================== 参数配置（与评分代码一致）====================
    g.etf_pool = [
        '159934.XSHE',  # 黄金ETF
        '513100.XSHG',  # 纳指100
        '563360.XSHG',  # 中证A500
        '159915.XSHE',  # 创业板ETF
    ]
    g.m_days = 25              # 动量参考天数
    g.target_num = 1           # 持仓数量
    g.cooldown_days = 30       # 冷静期天数
    g.cooldown_threshold = 0.25  # 冷静触发阈值：25%
    g.short_term_days = 60     # 短期涨幅检查窗口（与评分代码一致）

    # 冷静期记录 {etf_code: end_date}
    g.cooling_etfs = {}

    run_daily(trade, '9:30')

# ==================== 冷静期管理（与评分代码一致）====================

def is_in_cooldown(context, etf_code):
    """检查ETF是否在冷静期内"""
    if etf_code not in g.cooling_etfs:
        return False

    end_date = g.cooling_etfs[etf_code]
    today = pd.Timestamp(context.current_dt.date())

    if today >= end_date:
        del g.cooling_etfs[etf_code]
        log.info(f"标的{etf_code}冷静期结束，恢复交易资格")
        return False

    return True

def trigger_cooldown(context, etf_code, short_term_gain):
    """触发冷静期"""
    today = pd.Timestamp(context.current_dt.date())
    end_date = today + pd.Timedelta(days=g.cooldown_days)
    g.cooling_etfs[etf_code] = end_date
    log.info(f"【冷静期触发】{etf_code} 短期涨幅{short_term_gain:.2%}，冷静至{end_date.strftime('%Y-%m-%d')}")

def check_all_cooldown(context):
    """
    检查所有ETF（不只是持仓！）的短期涨幅
    与评分代码逻辑一致
    """
    today = pd.Timestamp(context.current_dt.date())
    triggered = []

    for etf in g.etf_pool:
        if etf in g.cooling_etfs:
            continue

        try:
            # 用 attribute_history 获取60天数据（与评分代码的 get_price 等价）
            df = attribute_history(etf, g.short_term_days + 1, '1d', ['close'])
            if len(df) < 2:
                continue

            start_price = df['close'].iloc[0]
            end_price = df['close'].iloc[-1]
            short_term_gain = (end_price / start_price) - 1

            if short_term_gain > g.cooldown_threshold:
                trigger_cooldown(context, etf, short_term_gain)
                triggered.append(etf)

        except Exception as e:
            log.error(f"检查{etf}冷静期出错: {e}")

    return triggered

def get_available_pool(context):
    """获取可用ETF池（排除冷静期内的标的）"""
    available = []
    for etf in g.etf_pool:
        if not is_in_cooldown(context, etf):
            available.append(etf)
    return available

# ==================== 动量评分（与评分代码一致）====================

def get_rank(context, etf_pool):
    """
    基于年化收益和判定系数打分的动量因子轮动
    与评分代码完全一致
    """
    score_list = []
    valid_etfs = []

    for etf in etf_pool:
        try:
            df = attribute_history(etf, g.m_days, '1d', ['close'])
            if len(df) < g.m_days * 0.8:
                continue

            y = np.log(df['close'])
            x = np.arange(len(y))
            slope, intercept = np.polyfit(x, y, 1)
            annualized_returns = math.pow(math.exp(slope), 250) - 1
            r_squared = 1 - (sum((y - (slope * x + intercept))**2) / 
                           ((len(y) - 1) * np.var(y, ddof=1)))
            score = annualized_returns * r_squared

            score_list.append(score)
            valid_etfs.append(etf)
        except Exception as e:
            log.error(f"计算[{etf}]动量得分出错: {e}")
            continue

    df = pd.DataFrame(index=valid_etfs, data={'score': score_list})
    df = df.sort_values(by='score', ascending=False)

    # 记录评分
    for etf in valid_etfs:
        if etf in df.index:
            record(**{get_etf_name(etf): round(df.loc[etf]['score'], 2)})

    if g.cooling_etfs:
        record(冷静中=len(g.cooling_etfs))

    print(df)
    return list(df.index)

def get_etf_name(etf_code):
    name_map = {
        '159934.XSHE': '黄金',
        '513100.XSHG': '纳指',
        '563360.XSHG': '价值',
        '159915.XSHE': '创业板',
    }
    return name_map.get(etf_code, etf_code)

# ==================== 交易主函数 ====================

def trade(context):
    # 第一步：检查所有ETF的冷静期（与评分代码一致，检查所有ETF不只是持仓）
    check_all_cooldown(context)

    # 第二步：获取可用ETF池
    available_pool = get_available_pool(context)

    if not available_pool:
        log.warning("所有ETF均在冷静期内，今日不交易")
        # 清仓所有持仓
        for etf in list(context.portfolio.positions.keys()):
            order_target_value(etf, 0)
        return

    # 第三步：对可用ETF进行动量评分排名
    rank_list = get_rank(context, available_pool)

    if not rank_list:
        log.warning("无可用标的，今日不交易")
        return

    # 第四步：确定目标持仓
    target_list = rank_list[:g.target_num]

    # 第五步：调仓执行
    hold_list = list(context.portfolio.positions.keys())

    # 卖出：不在目标列表中的持仓
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
            print('卖出' + str(etf))

    # 买入：目标中未持仓的
    hold_list = list(context.portfolio.positions.keys())
    if len(hold_list) < g.target_num:
        value = context.portfolio.available_cash / (g.target_num - len(hold_list))
        for etf in target_list:
            if context.portfolio.positions[etf].total_amount == 0:
                order_target_value(etf, value)
                print('买入' + str(etf))