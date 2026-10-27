# ============================================================================
# q-e9-3 变体：ETF动量 冠军 62c2664f —— 「点时」池（POINT-IN-TIME POOL）
#   池 = 本书 etf_pool 中的代码 ∩ { 上市日期 < 2024-01-01 }（截止日读自 harness）
#   本书池无行内日期；日期以 JQ 自身 start_date 为准（两次探针，见 build-e9-pit.js），
#   语料库内其他作者的行内注释作交叉核对（14 只重叠，全部一致）。
#   513100.XSHG  上市 2013-05-15  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2013-05-15 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   159509.XSHE  上市 2023-08-08  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2023-08-08 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   513520.XSHG  上市 2019-06-25  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2019-06-25 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   513030.XSHG  上市 2014-09-05  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2014-09-05 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   518880.XSHG  上市 2013-07-29  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2013-07-29 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   159985.XSHE  上市 2019-12-05  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2019-12-05 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   159981.XSHE  上市 2020-01-17  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2020-01-17 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   501018.XSHG  上市 2016-06-28  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2016-06-28 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   511260.XSHG  上市 2017-08-24  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]
#   513130.XSHG  上市 2021-06-01  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]
#   513690.XSHG  上市 2021-05-20  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]
#   510180.XSHG  上市 2006-05-18  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]
#   159915.XSHE  上市 2011-12-09  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2011-12-09 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   510410.XSHG  上市 2012-05-11  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]
#   515650.XSHG  上市 2019-11-11  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]
#   588120.XSHG  上市 2023-09-15  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]
#   159851.XSHE  上市 2021-03-19  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2021-03-19 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   159637.XSHE  上市 2022-09-01  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]
#   516160.XSHG  上市 2021-02-04  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2021-02-04 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   159550.XSHE  上市 >2024-12-31  [来源: JQ get_all_securities membership, probe 9d60e3059ab91919637a0c1cdb387d4b (not listed by 2024-12-31 ⇒ lists 2025+)]  ← 排除（2025+ 上市：TRAIN 不可交易，VAL 可交易）
#   515250.XSHG  上市 2021-01-08  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]
#   159378.XSHE  上市 >2024-12-31  [来源: JQ get_all_securities membership, probe 9d60e3059ab91919637a0c1cdb387d4b (not listed by 2024-12-31 ⇒ lists 2025+)]  ← 排除（2025+ 上市：TRAIN 不可交易，VAL 可交易）
#   516510.XSHG  上市 2021-04-07  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2021-04-07 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   515050.XSHG  上市 2019-10-16  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]  [语料: 2019-10-16 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]
#   515000.XSHG  上市 2019-08-16  [来源: JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41]
#   159529.XSHE  上市 2024-02-02  [来源: JQ get_all_securities membership, probe 9d60e3059ab91919637a0c1cdb387d4b]  [语料: 2024-02-02 [2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py]]  ← 排除（TRAIN 窗口内上市）
# 【刻意不碰】排名、动量窗口、择时、阈值、成本块，逐字不动。
# ============================================================================
# Clone from JoinQuant
# postId: 62c2664f4f8cdfc492b392fb73bab57d
# backtestId: eadffdf00f579fb9f668e59c5e624ec5
# title: 【三部曲吃透ETF动量3】地囚人，欲成仙，殊不知，天亦囚仙

from jqdata import *
import datetime
import math
import numpy as np
from scipy.optimize import minimize
import pandas as pd

# --- 全局配置与常量 ---
etf_pool = [
    "513100.XSHG", "159509.XSHE", "513520.XSHG", "513030.XSHG", "518880.XSHG",
    "159985.XSHE", "159981.XSHE", "501018.XSHG", "511260.XSHG", "513130.XSHG",
    "513690.XSHG", "510180.XSHG", "159915.XSHE", "510410.XSHG", "515650.XSHG",
    "588120.XSHG", "159851.XSHE", "159637.XSHE", "516160.XSHG",    # q-e9-3: 移除 159550.XSHE（上市 >= 2024-01-01）
    "515250.XSHG", "516510.XSHG", "515050.XSHG", "515000.XSHG",   # q-e9-3: 移除 159378.XSHE（上市 >= 2024-01-01）
       # q-e9-3: 移除 159529.XSHE（上市 >= 2024-01-01）
]

g_strategys = {}
g_portfolio_value_proportion = [1]
g_positions = {i: {} for i in range(len(g_portfolio_value_proportion))}
g_weights = {}
g_channel = 'etfld'

# 策略配置
g_etf_rotation = {
    "index": 0,
    "name": "核心资产轮动策略",
    "stock_sum": 1,
    "hold_list": [],
    "min_money": 500,
    "etf_pool": etf_pool,
    "m_days": 25,
    "enable_volume_check": True,
    "volume_lookback_days": 5,
    "volume_threshold": 1.0,
    "ma_filter_days": 20,
    "enable_ma_filter": False,
}

# --- 辅助函数 ---
def order_(context, security, vol):
    try:
        o = order(security, vol)
        return o
    except Exception as e:
        log.error(f"下单失败 {security}: {str(e)}")
        return None

def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    log.info("策略初始化完成")
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    
    set_slippage(FixedSlippage(0.0001), type="fund")
    set_slippage(FixedSlippage(0.003), type="stock")
    
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003,
                  close_commission=0.0003, close_today_commission=0, min_commission=5),
        type="stock",
    )
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0,
                             close_commission=0, close_today_commission=0, min_commission=0),
                   type="mmf")
    
    if g_portfolio_value_proportion[0] > 0:
        run_daily(etf_rotation_sell, "10:40")
        run_daily(etf_rotation_buy, "10:40")
    run_daily(end_trade, "14:59")

def process_initialize(context):
    global g_strategys
    g_strategys = {"核心资产轮动策略": {"index": 0, "name": "核心资产轮动策略"}}

def end_trade(context):
    """
    修改版 end_trade 函数：
    1. 检查账户持仓中是否存在本地记录没有的股票。
    2. 如果存在，判断该股票是否在ETF池中。
       - 如果在池中，则认为是送股等导致的差异，更新本地记录。
       - 如果不在池中，则认为是无关持仓，执行卖出操作。
    """
    # 获取所有策略管理的持仓股票集合
    marked = {s for d in g_positions.values() for s in d}
    current_data = get_current_data()
    
    for stock in context.portfolio.positions:
        # 发现账户持仓不在本地记录中
        if stock not in marked:
            pos = context.portfolio.positions[stock].total_amount
            price = current_data[stock].last_price
            
            # 检查该股票是否属于策略的ETF池
            if stock in etf_pool:
                # 在ETF池中，可能是送股等原因导致的数量不一致，更新本地记录
                index = g_etf_rotation["index"]  # 假设只有一个策略组，使用默认索引
                old_recorded_pos = g_positions[index].get(stock, 0)
                
                # 同步账户实际持仓到本地记录
                g_positions[index][stock] = pos
                
                # 更新策略的持有列表
                g_etf_rotation["hold_list"] = list(g_positions[index].keys())
                
                log.info(f"更新持仓记录: {stock}({current_data[stock].name}) 数量从 {old_recorded_pos} 更新为账户实际数量 {pos} (可能由送股等引起)")
            else:
                # 不在ETF池中，视为无关持仓，进行清理
                if my_order(context, stock, -pos, price, 0):
                    log.info(f"清理无关持仓: 卖出{stock}({current_data[stock].name}), 价格{price}, 数量{pos}")

def etf_rotation_order_target_value(context, security, value):
    """
    修改版 etf_rotation_order_target_value 函数：
    1. 不再依赖订单的成交数量来更新本地持仓记录。
    2. 订单执行后，直接查询账户中的实际持仓数量，并将其作为新的本地记录值。
    """
    strategy = g_etf_rotation
    current_data = get_current_data()

    if security not in current_data:
        log.info(f"{security}: 数据获取失败")
        return False
    cd = current_data[security]
    if cd.paused:
        log.info(f"{security}: 今日停牌")
        return False
    if cd.last_price == cd.high_limit:
        log.info(f"{security}: 涨停")
        return False
    if cd.last_price == cd.low_limit:
        log.info(f"{security}: 跌停")
        return False

    price = cd.last_price
    current_position = g_positions[strategy["index"]].get(security, 0)
    current_position_all = context.portfolio.positions[security].total_amount if security in context.portfolio.positions else 0

    target_position = (int(value / price) // 100) * 100 if price != 0 else 0
    adjustment = target_position - current_position

    # T+1限制检查
    closeable_amount = context.portfolio.positions[security].closeable_amount if security in context.portfolio.positions else 0
    if adjustment < 0 and closeable_amount == 0:
        log.info(f"{security}: T+1限制，无法卖出")
        return False

    if adjustment != 0:
        o = my_order(context, security, adjustment, price, target_position)
        if o:
            # --- 核心修改：订单执行后，不再基于订单成交数量更新 ---
            # 而是直接查询账户中的实际总持仓量来更新本地记录
            actual_total_amount = context.portfolio.positions[security].total_amount if security in context.portfolio.positions else 0
            g_positions[strategy["index"]][security] = actual_total_amount
            
            # 如果实际持仓为0，则从本地记录中移除
            if g_positions[strategy["index"]][security] <= 0:
                g_positions[strategy["index"]].pop(security, None)
            
            # 更新策略的持有列表
            strategy["hold_list"] = list(g_positions[strategy["index"]].keys())
            
            log.debug(f"订单执行完成: {security}. 本地持仓记录已更新为账户实际持仓: {actual_total_amount}")
            return True
    else:
        # 如果无需调整，也同步一次实际持仓，以防有细微变化
        actual_total_amount = context.portfolio.positions[security].total_amount if security in context.portfolio.positions else 0
        g_positions[strategy["index"]][security] = actual_total_amount
        if g_positions[strategy["index"]][security] <= 0:
            g_positions[strategy["index"]].pop(security, None)
        strategy["hold_list"] = list(g_positions[strategy["index"]].keys())

    return False

def my_order(context, security, vol, price, target_position):
    try:
        return order_(context, security, vol)
    except Exception as e:
        log.error(f"my_order 执行失败 {security}: {str(e)}")
        return None

def get_etf_rotation_total_value(context):
    index = g_etf_rotation["index"]
    if not g_positions[index]:
        return 0
    total_value = 0
    current_data = get_current_data()
    for key, value in g_positions[index].items():
        if key in context.portfolio.positions:
            price = context.portfolio.positions[key].price
            total_value += price * value
    return total_value

def etf_rotation_order_target_value(context, security, value):
    strategy = g_etf_rotation
    current_data = get_current_data()

    if security not in current_data:
        log.info(f"{security}: 数据获取失败")
        return False
    cd = current_data[security]
    if cd.paused:
        log.info(f"{security}: 今日停牌")
        return False
    if cd.last_price == cd.high_limit:
        log.info(f"{security}: 涨停")
        return False
    if cd.last_price == cd.low_limit:
        log.info(f"{security}: 跌停")
        return False

    price = cd.last_price
    current_position = g_positions[strategy["index"]].get(security, 0)
    current_position_all = context.portfolio.positions[security].total_amount if security in context.portfolio.positions else 0

    target_position = (int(value / price) // 100) * 100 if price != 0 else 0
    adjustment = target_position - current_position
    target_position_all = current_position_all + adjustment

    closeable_amount = context.portfolio.positions[security].closeable_amount if security in context.portfolio.positions else 0
    if adjustment < 0 and closeable_amount == 0:
        log.info(f"{security}: T+1限制，无法卖出")
        return False

    if adjustment != 0:
        o = my_order(context, security, adjustment, price, target_position_all)
        if o and hasattr(o, 'filled'):
            filled = o.filled if o.is_buy else -o.filled
            g_positions[strategy["index"]][security] = current_position + filled
            if g_positions[strategy["index"]][security] <= 0:
                g_positions[strategy["index"]].pop(security, None)
            strategy["hold_list"] = list(g_positions[strategy["index"]].keys())
            return True
    return False

def get_volume_ratio(context, security, lookback_days, threshold):
    try:
        hist_data = attribute_history(security, lookback_days, '1d', ['volume'])
        if hist_data is None or len(hist_data) < lookback_days:
            return None
        avg_volume = hist_data['volume'].mean()
        
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
            
        current_volume = df_vol['volume'].sum()
        ratio = current_volume / avg_volume if avg_volume > 0 else 0
        return ratio if ratio > threshold else None
    except:
        return None

# ==================== 关键修改：增强日志支持 ====================
def filter_below_ma_with_detail(stocks, days=20):
    """返回 (保留列表, 被剔除明细列表)"""
    if not stocks:
        return [], []
    current_data = get_current_data()
    kept = []
    removed = []  # [(code, name, price, ma)]
    
    for stock in stocks:
        try:
            hist = attribute_history(stock, days, "1d", ["close"])
            if hist is None or len(hist) < days:
                continue
            ma_n = hist["close"].mean()
            current_price = current_data[stock].last_price
            name = current_data[stock].name if stock in current_data else 'Unknown'
            
            if current_price >= ma_n:
                kept.append(stock)
            else:
                removed.append((stock, name, current_price, ma_n))
        except Exception as e:
            continue
    return kept, removed

def etf_rotation_filter(context, operation_time=""):
    """★★★ 增强日志版筛选逻辑 ★★★"""
    strategy = g_etf_rotation
    log.info(f"--- ETF筛选开始 (原始池: {len(strategy['etf_pool'])}) ---")
    
    # Step 1: 均线过滤（带详细剔除日志）
    filtered_pool = strategy["etf_pool"]
    removed_list = []
    if strategy["enable_ma_filter"]:
        filtered_pool, removed_list = filter_below_ma_with_detail(filtered_pool, strategy["ma_filter_days"])
        log.info(f"均线过滤后: {len(filtered_pool)} 只")
        
        if removed_list:
            log.info("=== 被均线过滤剔除的ETF（当前价 < MA20）===")
            for code, name, price, ma in removed_list:
                log.info(f"{code}({name}) - 当前价:{price:.4f}, MA20:{ma:.4f}")
        else:
            log.info("=== 无ETF被均线过滤剔除 ===")

    # Step 2: 计算评分（保留原始逻辑）
    data = pd.DataFrame(columns=["annualized_returns", "r2", "score"])
    current_data = get_current_data()
    
    for etf in filtered_pool:
        try:
            df = attribute_history(etf, strategy["m_days"], "1d", ["close"])
            if df is None or len(df) < strategy["m_days"]:
                continue
            prices = df["close"].values
            current_price = current_data[etf].last_price
            prices = np.append(prices, current_price)
            
            if np.any(prices <= 0):
                continue

            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            
            if np.allclose(y, y[0]):
                slope = 0.0
            else:
                slope, intercept = np.polyfit(x, y, 1, w=weights)

            annualized_returns = math.exp(slope * 250) - 1
            fitted_y = slope * x + intercept
            ss_res = np.sum(weights * (y - fitted_y) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
            score = annualized_returns * r2

            data.loc[etf] = [annualized_returns, r2, score]

        except Exception as e:
            continue

    # Step 3: 应用评分条件（0 < score < 5）
    if not data.empty:
        valid_data = data.query("0 < score < 5").sort_values(by="score", ascending=False)
    else:
        valid_data = pd.DataFrame()

    # === 新增：完整列出所有通过均线后的 ETF 评分详情 ===
    log.info(f"=== 所有通过均线过滤的ETF评分详情（共{len(data)}只）===")
    current_data = get_current_data()
    for idx in data.index:
        row = data.loc[idx]
        name = current_data[idx].name if idx in current_data else 'Unknown'
        if idx in valid_data.index:
            status = "✅ 有效"
        else:
            if row['score'] <= 0:
                reason = "score ≤ 0"
            elif row['score'] >= 5:
                reason = "score ≥ 5"
            else:
                reason = "其他"
            status = f"❌ 无效（{reason}）"
        log.info(f"{idx}({name}) - 评分:{row['score']:.6f} | 动量:{row['annualized_returns']*100:.2f}% | R²:{row['r2']:.3f} | {status}")

    selected_etfs = valid_data.index.tolist()
    log.info(f"--- 筛选结束，最终入选: {selected_etfs} ---")
    return selected_etfs

# ✅ 新增：带缓存的 ETF 目标获取函数
def get_cached_etf_targets(context):
    today = context.current_dt.date()
    if hasattr(context, 'etf_rotation_cache') and context.etf_rotation_cache.get('date') == today:
        return context.etf_rotation_cache['targets']
    
    raw_targets = etf_rotation_filter(context)
    targets = filter_liquidity_floor(context, raw_targets)[:g_etf_rotation["stock_sum"]]  # liq: ONLY change vs q-e9-3
    
    context.etf_rotation_cache = {
        'date': today,
        'targets': targets
    }
    return targets

def check_etf_rotation_holdings(context):
    strategy = g_etf_rotation
    hold = list(g_positions[strategy["index"]].keys())
    if not hold:
        return []
    current_data = get_current_data()
    return [s for s in hold if current_data[s].last_price < current_data[s].high_limit]

def etf_rotation_sell(context):
    targets = get_cached_etf_targets(context)
    
    current_data = get_current_data()
    hold_list = list(g_positions[g_etf_rotation["index"]].keys())
    original_holds = set(hold_list)

    log.info(f"=== 卖出逻辑 === 目标: {targets}, 当前持仓: {hold_list}")
    
    # 放量卖出（保留原始逻辑，含成交量过滤日志）
    if g_etf_rotation["enable_volume_check"]:
        for stock in hold_list[:]:
            vol_ratio = get_volume_ratio(context, stock, g_etf_rotation["volume_lookback_days"], g_etf_rotation["volume_threshold"])
            if vol_ratio is not None:
                current_pos = g_positions[g_etf_rotation["index"]].get(stock, 0)
                price = current_data[stock].last_price
                log.info(f"【放量卖出】{stock}({current_data[stock].name}) 放量比值:{vol_ratio:.2f}, 卖出{current_pos}股")
                etf_rotation_order_target_value(context, stock, 0)
                if stock in g_positions[g_etf_rotation["index"]]:
                    del g_positions[g_etf_rotation["index"]][stock]
                if stock in g_etf_rotation["hold_list"]:
                    g_etf_rotation["hold_list"].remove(stock)

    # 不在目标列表中则卖出
    for stock in hold_list[:]:
        if stock not in targets:
            if stock not in g_positions[g_etf_rotation["index"]]:
                continue
            current_pos = g_positions[g_etf_rotation["index"]][stock]
            log.info(f"【目标外卖出】{stock}({current_data[stock].name}), 卖出{current_pos}股")
            etf_rotation_order_target_value(context, stock, 0)
            if stock in g_positions[g_etf_rotation["index"]]:
                del g_positions[g_etf_rotation["index"]][stock]
            if stock in g_etf_rotation["hold_list"]:
                g_etf_rotation["hold_list"].remove(stock)

    # 超仓卖出（理论上不会发生）
    current_hold_in_targets = [s for s in g_positions[g_etf_rotation["index"]] if s in targets]
    if len(current_hold_in_targets) > g_etf_rotation["stock_sum"]:
        for stock in current_hold_in_targets[g_etf_rotation["stock_sum"]:]:
            etf_rotation_order_target_value(context, stock, 0)
            if stock in g_positions[g_etf_rotation["index"]]:
                del g_positions[g_etf_rotation["index"]][stock]
            if stock in g_etf_rotation["hold_list"]:
                g_etf_rotation["hold_list"].remove(stock)

    final_holds = set(g_positions[g_etf_rotation["index"]].keys())
    sold = original_holds - final_holds
    if sold:
        log.info(f"=== 卖出完成，共卖出 {len(sold)} 只: {list(sold)} ===")
    else:
        log.info("=== 无卖出操作 ===")

def etf_rotation_buy(context):
    targets = get_cached_etf_targets(context)
    
    if not targets:
        log.info("无目标ETF，跳过买入")
        return
        
    log.info(f"=== 买入逻辑 === 目标: {targets}")
    
    current_data = get_current_data()
    portfolio = context.portfolio
    hold_list = list(g_positions[g_etf_rotation["index"]].keys())
    current_hold_in_targets = [s for s in hold_list if s in targets]
    current_hold_count = len(current_hold_in_targets)
    
    total_value = portfolio.total_value
    available_cash = portfolio.available_cash
    target_value = total_value * g_portfolio_value_proportion[g_etf_rotation["index"]]

    for stock in targets:
        weight = 1 / len(targets)
        target = target_value * weight
        last_price = current_data[stock].last_price
        current_position = g_positions[g_etf_rotation["index"]].get(stock, 0)
        current_value = current_position * last_price
        
        if current_hold_count == 0:
            need_buy_value = target - current_value
            actual_buy_value = min(need_buy_value, available_cash)
            if actual_buy_value <= max(g_etf_rotation["min_money"], last_price * 100):
                log.info(f"跳过 {stock} - 金额太小 ({actual_buy_value:.2f}元)")
                continue
            log.info(f"买入 {stock}({current_data[stock].name}) - 目标金额 {target:.2f}元")
            etf_rotation_order_target_value(context, stock, target)
        else:
            if current_value < target * 0.9:
                rebalance_amount = target - current_value
                if rebalance_amount > max(g_etf_rotation["min_money"], last_price * 100):
                    log.info(f"补仓 {stock}({current_data[stock].name}) - 补仓金额 {rebalance_amount:.2f}元")
                    etf_rotation_order_target_value(context, stock, target)

def filter_limitup_stock(stocks, n):
    current_data = get_current_data()
    return [stock for stock in stocks 
            if current_data[stock].last_price != current_data[stock].high_limit]

# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====


# ---------------- liquidity floor (realizability measurement, epoch 9) ----------------
# Derivation: capital 1000000 x proportion 1 / stock_sum (=1) = 1000000
# CNY per full position. Epoch 4 pins order_volume_ratio = 0.05, so filling that position inside
# a SINGLE daily bar requires that bar's traded value >= 1000000 / 0.05 = 20000000.
# This is 10x that minimum (capacity headroom).
LIQ_FLOOR = 200000000

def filter_liquidity_floor(context, stock_list):
    """Keep names whose TRAILING-20-BAR MEDIAN daily `money` is >= LIQ_FLOOR.

    Median, not mean: one spike day must not admit a normally-illiquid name.
    Evaluated on context.previous_date, so the bar being traded today is never consulted.
    Emits one LIQFLOOR line per call via log.error, so it survives the strategy's log.set_level.
    """
    stock_list = list(stock_list)
    n_in = len(stock_list)
    if n_in == 0:
        log.error('LIQFLOOR floor=%.0f in=0 out=0 removedFrac=NA slots=0' % LIQ_FLOOR)
        return []
    try:
        df = get_price(stock_list, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        keep = [s for s in stock_list if (s in med.index) and (med[s] >= LIQ_FLOOR)]
    except Exception as e:
        # Loud, never silent: a swallowed failure reproduces the baseline exactly and is
        # indistinguishable from "the floor did nothing" — which is the one answer that must be
        # trustworthy, since that is what 大小盘轮动's and b3751277's liq-1 actually found.
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s' % (LIQ_FLOOR, n_in, str(e)))
        return stock_list
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(1, len(keep))))
    return keep
