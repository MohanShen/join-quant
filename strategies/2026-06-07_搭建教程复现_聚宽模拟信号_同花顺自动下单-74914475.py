# Clone from JoinQuant
# postId: 7491447557628127022af2af8ba2623f
# backtestId: d49ece0e63b4855c4e87293bd03c7c89
# title: 搭建教程复现：聚宽模拟信号→同花顺自动下单

from jqdata import *
# ============================================
# 【聚宽跟单系统 - 配置和初始化】（完全按文档添加）
# ============================================
import numpy as np
import pandas as pd
import datetime
import math
import gc
import requests
import json
from enum import Enum
import statsmodels.api as sm
from jqfactor import get_factor_values

# ----- 服务器配置（按文档要求修改为你的云服务器地址和密钥）-----
MY_SERVER = "http://0.0.0.0:5000"
MY_SECRET = "Abc123"
# ----- 内部变量（文档要求，不要修改）-----
_jqmt_enabled = True  # True=启用跟单, False=仅模拟交易
_jqmt_session = None  # 请求会话

def _jqmt_init():
    """初始化HTTP会话（完全按文档）"""
    global _jqmt_session
    if _jqmt_session is None:
        _jqmt_session = requests.Session()
        _jqmt_session.headers.update({
            'X-Secret-Key': MY_SECRET,
            'Content-Type': 'application/json'
        })
    return _jqmt_session

def _jqmt_send_order(stock_code, is_buy, quantity, price, order_id=""):
    """发送订单到跟单服务器（完全按文档）"""
    if not _jqmt_enabled:
        return None
    try:
        session = _jqmt_init()
        data = {
            'stockCode': stock_code,
            'buySell': 'True' if is_buy else 'False',
            'orderQuantity': str(quantity),
            'averageTransactionPrice': str(price),
            'orderId': str(order_id) if order_id else ''
        }
        response = session.post(
            f"{MY_SERVER}/api/order/push",
            json=data,
            timeout=30
        )
        if response.status_code == 200:
            log.info(f"【跟单成功】{stock_code} {'买入' if is_buy else '卖出'} {quantity}股 @ {price}")
            return response.json()
        else:
            log.error(f"【跟单失败】{stock_code} 状态码:{response.status_code}")
            return None
    except Exception as e:
        log.error(f"【跟单异常】{stock_code} 错误:{e}")
        return None

def _jqmt_after_order(stock_code, is_buy, quantity, price, order_id=""):
    """订单执行后调用，发送跟单请求（完全按文档）"""
    if quantity > 0 and price > 0:
        _jqmt_send_order(stock_code, is_buy, quantity, price, order_id)
# ============================================
# 【聚宽跟单系统 - 结束】
# ============================================

SW1 = {
    '801010': '农林牧渔I','801020': '采掘I','801030': '化工I','801040': '钢铁I','801050': '有色金属I',
    '801060': '建筑建材I','801070': '机械设备I','801080': '电子I','801090': '交运设备I','801100': '信息设备I',
    '801110': '家用电器I','801120': '食品饮料I','801130': '纺织服装I','801140': '轻工制造I','801150': '医药生物I',
    '801160': '公用事业I','801170': '交通运输I','801180': '房地产I','801190': '金融服务I','801200': '商业贸易I',
    '801210': '休闲服务I','801220': '信息服务I','801230': '综合I','801710': '建筑材料I','801720': '建筑装饰I',
    '801730': '电气设备I','801740': '国防军工I','801750': '计算机I','801760': '传媒I','801770': '通信I',
    '801780': '银行I','801790': '非银金融I','801880': '汽车I','801890': '机械设备I','801950': '煤炭I',
    '801960': '石油石化I','801970': '环保I','801980': '美容护理I'
}

industry_code = ['801010','801020','801030','801040','801050','801080','801110','801120','801130','801140',
                 '801150','801160','801170','801180','801200','801210','801230','801710','801720','801730',
                 '801740','801750','801760','801770','801780','801790','801880','801890','801950','801960','801970','801980']
JSG_NAMES = ["银行I", "有色金属I", "钢铁I", "煤炭I"]
g_stock_num = 9
SMALLCAP_POOL_SIZE = 200
g_etf_pool = [
    "513100.XSHG",
    "513000.XSHG",
    "513030.XSHG",
    "518880.XSHG",
    "159980.XSHE",
    "159985.XSHE",
    "159981.XSHE",
    "501018.XSHG",
    "511090.XSHG",
    "513130.XSHG",
    "513690.XSHG",
    "510180.XSHG",
    "159915.XSHE",
    "510410.XSHG",
    "515650.XSHG",
    "512290.XSHG",
    "588120.XSHG",
    "515070.XSHG",
    "159851.XSHE",
    "159637.XSHE",
    "516160.XSHG",
    "159550.XSHE",
    "512710.XSHG",
    "159692.XSHE",
    "512480.XSHG",
    "515250.XSHG",
    "159378.XSHE",
    "516510.XSHG",
    "515050.XSHG",
    "159995.XSHE",
    "515790.XSHG",
    "515000.XSHG"
]

fixed_etfs = ["511260.XSHG", "518880.XSHG", "512800.XSHG"]
g_etf_rotation = {
    "stock_sum":1,
    "min_money": 500,
    "etf_pool": g_etf_pool,
    "m_days": 25,
    "enable_volume_check": True,
    "volume_lookback": 5,
    "volume_threshold": 2.0,
    "ma_filter_days": 20,
    "enable_ma_filter": True,
}

g.HV_control = True
g.HV_duration = 120
g.HV_ratio = 0.9

def initialize(context):
    set_benchmark('399101.XSHE')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.01))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.000086,
                             close_commission=0.000086, close_today_commission=0, min_commission=0), type='stock')
    log.set_level('order', 'error')
    
    g.hold_list = []
    g.yesterday_HL_list = []
    g.stock_num = g_stock_num
    g.etf_buy_list = []
    g.limit_days = 20
    g.history_hold_list = []
    g.not_buy_again_list = []
    g.high_limit_list = []
    g.market_width_jsg = 0
    g.market_width_smallcap = 0
    
    g.HV_control = True
    g.HV_duration = 120
    g.HV_ratio = 0.9
    
    run_daily(prepare_stock_list, time='09:05')
    run_daily(daily_timing, time='9:30')
    run_daily(check_limit_up, time='9:30')
    run_daily(select_etfs_new, time='09:26')
    run_daily(compute_realtime_market_width, time='09:26')
    
    run_daily(trade_afternoon, time='10:30')
    run_daily(trade_afternoon, time='14:50')
    
    # ----- 跟单系统初始化（完全按文档）-----
    _jqmt_init()
    log.info("【跟单系统】已初始化，服务器: " + MY_SERVER)
    # 可选：检查服务器健康状态（完全按文档）
    try:
        health = _jqmt_session.get(f"{MY_SERVER}/api/health", timeout=5)
        if health.status_code == 200:
            log.info(f"【跟单系统】服务器状态: {health.json()}")
        else:
            log.warning(f"【跟单系统】服务器异常: {health.status_code}")
    except Exception as e:
        log.warning(f"【跟单系统】无法连接服务器: {e}")

def compute_realtime_market_width(context):
    try:
        historical_date = context.previous_date
        df_ratio, jsg_mean, smallcap_mean = compute_market_width(historical_date)
        
        if df_ratio is not None:
            g.market_width_jsg = jsg_mean
            g.market_width_smallcap = smallcap_mean
            diff = smallcap_mean - jsg_mean
            avg_value = (jsg_mean + smallcap_mean) / 2
            log.info("实时市场宽度计算完成 - 日期 %s：" % historical_date)
            log.info("  市场宽度 = %.0f，小市值 = %.0f，差值 = %.0f，平均值 = %.0f" % 
                    (jsg_mean, smallcap_mean, diff, avg_value))
        else:
            log.warn("实时市场宽度计算失败，使用前一天数据")
            yesterday = context.previous_date - datetime.timedelta(days=1)
            df_ratio, jsg_mean, smallcap_mean = compute_market_width(yesterday)
            if df_ratio is not None:
                g.market_width_jsg = jsg_mean
                g.market_width_smallcap = smallcap_mean
            else:
                g.market_width_jsg = 0
                g.market_width_smallcap = 0
    except Exception as e:
        log.error("计算实时市场宽度时发生错误: %s" % str(e))
        g.market_width_jsg = 0
        g.market_width_smallcap = 0

def prepare_stock_list(context):
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        g.hold_list.append(position.security)
    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    g.hold_list = list(context.portfolio.positions)
    g.history_hold_list.append(g.hold_list)
    if len(g.history_hold_list) >= g.limit_days:
        g.history_hold_list = g.history_hold_list[-g.limit_days:]
    temp_set = set()
    for hold_list in g.history_hold_list:
        temp_set = temp_set.union(set(hold_list))
    g.not_buy_again_list = list(temp_set)
    g.high_limit_list = []
    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit', 'paused'],
                       count=1, panel=False)
        g.high_limit_list = df.query('close==high_limit and paused==0')['code'].tolist()

def select_etfs_new(context):
    strategy = g_etf_rotation
    current_month = context.current_dt.month
    
    if current_month in [11, 12]:
        g.etf_buy_list = fixed_etfs
        return
    
    filtered_pool = strategy["etf_pool"]
    if strategy["enable_ma_filter"]:
        filtered_pool = filter_below_ma(
            stocks=filtered_pool,
            days=strategy["ma_filter_days"]
        )
    data = pd.DataFrame(index=filtered_pool, 
                       columns=["annualized_returns", "r2", "score"])
    for etf in filtered_pool:
        try:
            df = attribute_history(etf, strategy["m_days"] + 1, "1d", ["close", "high"])
            if len(df) < strategy["m_days"]:
                continue
            prices = df["close"].values[-strategy["m_days"]:]
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1

            ss_res = np.sum(weights * (y - (slope * x + intercept)) **2)
            ss_tot = np.sum(weights * (y - np.mean(y))** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0

            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]

            if len(prices) >= 4 and min(prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]) < 0.95:
                data.loc[etf, "score"] = 0
        except Exception as e:
            continue
    data = data.query("0 < score < 5").sort_values(by="score", ascending=False)
    selected_etfs = data.index.tolist()[:strategy["stock_sum"]]
    g.etf_buy_list = selected_etfs
    if selected_etfs:
        log.info(f"ETF轮动选择结果: {selected_etfs}")
        for etf in selected_etfs:
            etf_name = get_security_info(etf).display_name
            score = data.loc[etf, "score"]
            log.info(f"  {etf} {etf_name} 得分: {score:.4f}")
    else:
        log.info("ETF轮动策略未选出符合条件的ETF")

def filter_below_ma(stocks, days=20):
    if not stocks:
        return []
    filtered = []
    for stock in stocks:
        try:
            hist = attribute_history(stock, days, "1d", ["close"])
            if len(hist) < days:
                continue
            ma_n = hist["close"].mean()
            current_price = hist["close"].iloc[-1]
            if current_price >= ma_n:
                filtered.append(stock)
        except Exception as e:
            continue
    return filtered

def get_volume_ratio(security, lookback_days, threshold):
    try:
        hist_data = attribute_history(security, lookback_days + 5, '1d', ['volume'])
        if hist_data.empty or len(hist_data) < lookback_days:
            return None
        if len(hist_data) > lookback_days:
            avg_volume = hist_data['volume'].iloc[-(lookback_days+1):-1].mean()
        else:
            avg_volume = hist_data['volume'].iloc[:-1].mean()
        current_volume = hist_data['volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume

        return volume_ratio if volume_ratio > threshold else None
    except Exception as e:
        return None

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
    out = []
    for stock in stock_list:
        if stock.startswith('68') or stock.startswith('4') or stock.startswith('8') or stock.startswith('30'):
            continue
        out.append(stock)
    return out

def filter_limitup_stock(context, stock_list):
    last_prices = {}
    for stock in stock_list:
        try:
            hist = attribute_history(stock, 1, '1d', ['close'])
            if not hist.empty:
                last_prices[stock] = hist['close'].iloc[-1]
        except:
            continue
    current_data = get_current_data()
    res = []
    for stock in stock_list:
        try:
            if stock in context.portfolio.positions.keys():
                res.append(stock)
            else:
                if stock in last_prices and last_prices[stock] < current_data[stock].high_limit:
                    res.append(stock)
        except Exception:
            continue
    return res

def filter_limitdown_stock(context, stock_list):
    last_prices = {}
    for stock in stock_list:
        try:
            hist = attribute_history(stock, 1, '1d', ['close'])
            if not hist.empty:
                last_prices[stock] = hist['close'].iloc[-1]
        except:
            continue
    current_data = get_current_data()
    res = []
    for stock in stock_list:
        try:
            if stock in context.portfolio.positions.keys():
                res.append(stock)
            else:
                if stock in last_prices and last_prices[stock] > current_data[stock].low_limit:
                    res.append(stock)
        except Exception:
            continue
    return res

def filter_new_stock(context, stock_list, days=375):
    res = []
    for stock in stock_list:
        try:
            hist_data = attribute_history(stock, days+10, '1d', ['close'], skip_paused=False)
            if hist_data is None or len(hist_data) < days:
                continue
            res.append(stock)
        except:
            continue
    return res

def filter_national_nine_rules_stock(context, stock_list, date):
    filtered_stocks = []
    
    for stock in stock_list:
        try:
            q = query(
                valuation.code,
                income.net_profit,
                income.total_operating_revenue,
                balance.total_assets,
                balance.total_liability,
                cash_flow.net_operate_cash_flow
            ).filter(valuation.code == stock)
            
            df = get_fundamentals(q, date=date)
            if df is None or df.empty:
                continue
                
            net_profit = df['net_profit'].iloc[0]
            operating_revenue = df['total_operating_revenue'].iloc[0]
            total_assets = df['total_assets'].iloc[0]
            total_liability = df['total_liability'].iloc[0]
            operating_cash_flow = df['net_operate_cash_flow'].iloc[0]
            
            debt_ratio = total_liability / total_assets if total_assets > 0 else 1
            profit_margin = net_profit / operating_revenue if operating_revenue > 0 else -1
            
            q_history = query(
                income.net_profit
            ).filter(income.code == stock)
            
            df_history_1 = get_fundamentals(q_history, date=date - datetime.timedelta(days=365))
            df_history_2 = get_fundamentals(q_history, date=date - datetime.timedelta(days=730))
            
            consecutive_loss = False
            if df_history_1 is not None and not df_history_1.empty and df_history_2 is not None and not df_history_2.empty:
                if df_history_1['net_profit'].iloc[0] < 0 and df_history_2['net_profit'].iloc[0] < 0:
                    consecutive_loss = True
            
            low_revenue = operating_revenue < 100000000
            high_debt = debt_ratio > 0.7
            negative_cash_flow = operating_cash_flow < 0

            if (not consecutive_loss and 
                not low_revenue and 
                not high_debt and 
                not negative_cash_flow):
                filtered_stocks.append(stock)
                
        except Exception as e:
            filtered_stocks.append(stock)
    
    return filtered_stocks

def getStockIndustry_series(stocks, date):
    previous_date = date - datetime.timedelta(days=1)
    ind = get_industry(stocks, date=previous_date)
    mapping = {}
    for stk, info in ind.items():
        if 'sw_l1' in info:
            mapping[stk] = info['sw_l1']['industry_name']
    return pd.Series(mapping)

def get_smallcap200_pool(date):
    members = get_index_stocks('399101.XSHE', date=date)
    members = filter_kcbj_stock(list(members))
    members = filter_st_stock(members)
    members = filter_paused_stock(members)
    if not members:
        return []
    q_market_cap = query(
        valuation.code, 
        valuation.market_cap
    ).filter(valuation.code.in_(members))
    df_mc = get_fundamentals(q_market_cap, date=date)
    if df_mc is None or df_mc.empty:
        return []
    q_indicator = query(
        indicator.code,
        indicator.roe,
        indicator.roa
    ).filter(indicator.code.in_(members))
    df_ind = get_fundamentals(q_indicator, date=date)
    if df_ind is None or df_ind.empty:
        return []
    df = pd.merge(df_mc, df_ind, on='code')
    df = df.dropna(subset=['market_cap', 'roe', 'roa'])
    df = df[(df['roe'] > 0.15) & (df['roa'] > 0.10)]
    if df.empty:
        return []
    df = df.set_index('code').sort_values('market_cap', ascending=True)
    top = df.head(SMALLCAP_POOL_SIZE).index.tolist()
    return top

def compute_market_width(date, lookback_days=20):
    stocks = get_index_stocks("000985.XSHG", date=date)
    if not stocks:
        return None, None, None
    count = lookback_days
    h = get_price(stocks, end_date=date, frequency='1d',
                  fields=['close'], count=count + 20, panel=False)
    if h is None or h.empty:
        return None, None, None
    h['date'] = pd.DatetimeIndex(h.time).date
    df_close = h.pivot(index='code', columns='date', values='close').dropna(axis=0, how='any')
    df_close = df_close.iloc[:, -count:]
    if df_close.shape[1] < 20:
        return None, None, None
    df_ma20 = df_close.rolling(window=20, axis=1).mean()
    df_bias = df_close.iloc[:, -1] > df_ma20.iloc[:, -1]
    industry_series = getStockIndustry_series(df_bias.index.tolist(), date)
    df_bias = df_bias.to_frame(name=df_close.columns[-1])
    df_bias['industry_name'] = industry_series
    df_bias = df_bias.dropna(subset=['industry_name'])
    grouped_sum = df_bias.groupby('industry_name').sum()
    grouped_count = df_bias.groupby('industry_name').count()
    df_ratio = (grouped_sum * 100.0) / grouped_count
    jsg_present = [name for name in JSG_NAMES if name in df_ratio.index]
    if jsg_present:
        jsg_mean = df_ratio.loc[jsg_present].mean().values[0]
    else:
        jsg_mean = 0.0
    smallcap_pool = get_smallcap200_pool(date)
    smallcap_bias = df_bias.loc[df_bias.index.isin(smallcap_pool)]
    if not smallcap_bias.empty:
        smallcap_mean = (smallcap_bias.iloc[:, 0].sum() * 100.0) / smallcap_bias.shape[0]
    else:
        common = [s for s in smallcap_pool if s in df_bias.index]
        if common:
            smallcap_mean = (df_bias.loc[common].iloc[:, 0].sum() * 100.0) / len(common)
        else:
            smallcap_mean = 0.0
    return df_ratio, float(jsg_mean), float(smallcap_mean)

def daily_timing(context):
    jsg_mean = g.market_width_jsg
    smallcap_mean = g.market_width_smallcap
    if jsg_mean == 0 and smallcap_mean == 0:
        return
    diff = smallcap_mean - jsg_mean
    avg_value = (jsg_mean + smallcap_mean) / 2
    log.info("实时市场宽度决策 - 日期 %s：" % context.current_dt.date())
    log.info("  市场宽度 = %.0f ， 小市值 = %.0f ， 差值 = %.0f ， 平均值 = %.0f" %
             (jsg_mean, smallcap_mean, diff, avg_value))
    if avg_value < 1:
        log.info("信号：平均值低于1 -> 强制防守仓位(ETF)")
        execute_etf_strategy(context)
    elif diff > 0 or avg_value > 70:
        log.info("信号：小市值强或市场强 -> 股票仓位")
        historical_date = context.previous_date
        target_list = build_target_stock_list(context, historical_date)
        for pos in list(context.portfolio.positions.values()):
            if pos.security in g.etf_buy_list or pos.security in fixed_etfs:
                order_result = order_target_value(pos.security, 0)
                # 完全按文档添加跟单调用（卖出）
                if order_result and hasattr(order_result, 'filled') and order_result.filled > 0:
                    is_buy = False
                    filled_price = order_result.price if hasattr(order_result, 'price') and order_result.price > 0 else get_current_data()[pos.security].last_price
                    _jqmt_after_order(pos.security, is_buy, order_result.filled, filled_price, str(order_result.order_id) if hasattr(order_result, 'order_id') else "")
        for pos in list(context.portfolio.positions.values()):
            stk = pos.security
            if stk not in target_list and stk not in g.yesterday_HL_list:
                order_result = order_target_value(stk, 0)
                # 完全按文档添加跟单调用（卖出）
                if order_result and hasattr(order_result, 'filled') and order_result.filled > 0:
                    is_buy = False
                    filled_price = order_result.price if hasattr(order_result, 'price') and order_result.price > 0 else get_current_data()[stk].last_price
                    _jqmt_after_order(stk, is_buy, order_result.filled, filled_price, str(order_result.order_id) if hasattr(order_result, 'order_id') else "")
        existing = set(context.portfolio.positions.keys())
        to_buy = [s for s in target_list if s not in existing]
        if to_buy:
            free_cash = context.portfolio.available_cash
            buy_num = min(len(to_buy), max(0, g.stock_num - len(existing)))
            if buy_num > 0:
                value_per = free_cash / buy_num
                for s in to_buy[:buy_num]:
                    try:
                        if s not in filter_paused_stock([s]):
                            continue
                        order_result = order_target_value(s, value_per)
                        # 完全按文档添加跟单调用（买入）
                        if order_result and hasattr(order_result, 'filled') and order_result.filled > 0:
                            is_buy = True
                            filled_price = order_result.price if hasattr(order_result, 'price') and order_result.price > 0 else get_current_data()[s].last_price
                            _jqmt_after_order(s, is_buy, order_result.filled, filled_price, str(order_result.order_id) if hasattr(order_result, 'order_id') else "")
                    except Exception as e:
                        log.error("下单失败 %s : %s" % (s, str(e)))
    else:
        log.info("信号：小市值弱或无优势 -> 防守仓位(ETF)")
        execute_etf_strategy(context)

def execute_etf_strategy(context):
    for pos in list(context.portfolio.positions.values()):
        stk = pos.security
        if (stk not in g.yesterday_HL_list) and (stk not in g.etf_buy_list) and (stk not in fixed_etfs):
            order_result = order_target_value(stk, 0)
            # 完全按文档添加跟单调用（卖出）
            if order_result and hasattr(order_result, 'filled') and order_result.filled > 0:
                is_buy = False
                filled_price = order_result.price if hasattr(order_result, 'price') and order_result.price > 0 else get_current_data()[stk].last_price
                _jqmt_after_order(stk, is_buy, order_result.filled, filled_price, str(order_result.order_id) if hasattr(order_result, 'order_id') else "")
    
    current_month = context.current_dt.month
    if current_month in [11, 12]:
        full_etf_list = fixed_etfs
    else:
        full_etf_list = list(set(g.etf_buy_list + fixed_etfs))
    
    positions_now = set(context.portfolio.positions.keys())
    etfs_to_buy = [etf for etf in full_etf_list if etf not in positions_now]
    if etfs_to_buy:
        free_cash = context.portfolio.available_cash
        if free_cash > 0:
            available_etfs = filter_paused_stock(etfs_to_buy)
            if available_etfs:
                value_per = free_cash / len(available_etfs)
                for etf in available_etfs:
                    try:
                        order_result = order_target_value(etf, value_per)
                        # 完全按文档添加跟单调用（买入ETF）
                        if order_result and hasattr(order_result, 'filled') and order_result.filled > 0:
                            is_buy = True
                            filled_price = order_result.price if hasattr(order_result, 'price') and order_result.price > 0 else get_current_data()[etf].last_price
                            _jqmt_after_order(etf, is_buy, order_result.filled, filled_price, str(order_result.order_id) if hasattr(order_result, 'order_id') else "")
                        log.info("买入ETF: %s" % etf)
                    except Exception as e:
                        log.error("买入ETF失败 %s : %s" % (etf, str(e)))
            else:
                log.info("所有需要买入的ETF都停牌，无法买入")
    else:
        log.info("所有ETF都已持仓，无需买入")

def build_target_stock_list(context, date):
    members = get_index_stocks('399101.XSHE', date)
    members = filter_kcbj_stock(list(members))
    members = filter_st_stock(members)
    members = filter_paused_stock(members)
    members = filter_limitup_stock(context, members)
    members = filter_limitdown_stock(context, members)
    members = filter_new_stock(context, members)
    
    current_month = context.current_dt.month
    if current_month in [11, 12]:
        members = filter_national_nine_rules_stock(context, members, date)
    
    if not members:
        return []
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(members))
    df_mv = get_fundamentals(q, date=date)
    if df_mv is None or df_mv.empty:
        return []
    df_mv = df_mv.dropna(subset=['market_cap']).set_index('code').sort_values('market_cap', ascending=True)
    small_candidates = df_mv.head(SMALLCAP_POOL_SIZE).index.tolist()
    q2 = query(valuation.code).filter(valuation.code.in_(small_candidates),
                                      indicator.roe > 0.15,
                                      indicator.roa > 0.10).order_by(valuation.market_cap.asc()).limit(g.stock_num*3)
    df_f = get_fundamentals(q2, date=date)
    if df_f is None or df_f.empty:
        return small_candidates[:g.stock_num]
    codes = df_f['code'].tolist()
    codes = filter_paused_stock(codes)
    codes = filter_st_stock(codes)
    return codes[:g.stock_num]

def check_limit_up(context):
    now_time = context.current_dt
    if not g.yesterday_HL_list:
        return
    stocks_to_check = g.yesterday_HL_list.copy()
    sold_stocks = [] 
    for stock in stocks_to_check:
        try:
            if stock not in context.portfolio.positions:
                g.yesterday_HL_list.remove(stock)
                continue
            current_data = get_current_data()
            if current_data[stock].paused:
                continue
            current_price = current_data[stock].last_price
            high_limit = current_data[stock].high_limit
            price_tolerance = 0.01 
            if current_price < high_limit - price_tolerance:
                current_position = context.portfolio.positions[stock].closeable_amount
                if current_position > 0:
                    log.info("[%s] 涨停打开，当前价%.2f < 涨停价%.2f，执行卖出" % 
                            (stock, current_price, high_limit))
                    order_result = order_target_value(stock, 0)
                    # 完全按文档添加跟单调用（卖出）
                    if order_result and hasattr(order_result, 'filled') and order_result.filled > 0:
                        is_buy = False
                        filled_price = order_result.price if hasattr(order_result, 'price') and order_result.price > 0 else current_price
                        _jqmt_after_order(stock, is_buy, order_result.filled, filled_price, str(order_result.order_id) if hasattr(order_result, 'order_id') else "")
                    sold_stocks.append(stock) 
                if stock in g.yesterday_HL_list:
                    g.yesterday_HL_list.remove(stock)
            else:
                if context.portfolio.positions[stock].closeable_amount > 0:
                    log.debug("[%s] 连续涨停，继续持有，当前价%.2f/涨停价%.2f" % 
                             (stock, current_price, high_limit))
                else:
                    if stock in g.yesterday_HL_list:
                        g.yesterday_HL_list.remove(stock)
        except Exception as e:
            log.error("check_limit_up 异常: %s, %s" % (stock, str(e)))
            try:
                if stock in g.yesterday_HL_list:
                    g.yesterday_HL_list.remove(stock)
            except:
                pass
    if sold_stocks:
        log.info("检测到涨停打开卖出，开始重新买入符合条件的股票")
        buy_new_stocks_after_sale(context)

def buy_new_stocks_after_sale(context):
    jsg_mean = g.market_width_jsg
    smallcap_mean = g.market_width_smallcap
    if jsg_mean == 0 and smallcap_mean == 0:
        return
    diff = smallcap_mean - jsg_mean
    avg_value = (jsg_mean + smallcap_mean) / 2
    if not (diff > 0 or avg_value > 70):
        return
    historical_date = context.previous_date
    target_list = build_target_stock_list(context, historical_date)
    if not target_list:
        return
    existing_positions = set(context.portfolio.positions.keys())
    to_buy = [s for s in target_list if s not in existing_positions]
    if not to_buy:
        return
    free_cash = context.portfolio.available_cash
    if free_cash <= 0:
        return
    available_slots = max(0, g.stock_num - len(existing_positions))
    if available_slots <= 0:
        return
    buy_num = min(len(to_buy), available_slots)
    value_per = free_cash / buy_num
    log.info("准备买入 %d 只新股票，每只分配资金: %.2f" % (buy_num, value_per))
    bought_count = 0
    for s in to_buy[:buy_num]:
        try:
            if s not in filter_paused_stock([s]):
                continue
            current_data = get_current_data()
            hist = attribute_history(s, 1, '1d', ['close'])
            if not hist.empty and hist['close'].iloc[-1] >= current_data[s].high_limit:
                continue
            order_result = order_target_value(s, value_per)
            # 完全按文档添加跟单调用（买入）
            if order_result and hasattr(order_result, 'filled') and order_result.filled > 0:
                is_buy = True
                filled_price = order_result.price if hasattr(order_result, 'price') and order_result.price > 0 else get_current_data()[s].last_price
                _jqmt_after_order(s, is_buy, order_result.filled, filled_price, str(order_result.order_id) if hasattr(order_result, 'order_id') else "")
            log.info("涨停卖出后买入新股票: %s, 金额: %.2f" % (s, value_per))
            bought_count += 1
        except Exception as e:
            log.error("涨停卖出后买入失败 %s : %s" % (s, str(e)))

def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        start_date = context.current_dt - datetime.timedelta(days=20)
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
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0: 
            continue
        
        r = rt / avg
        action, icon = '', ''
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > 0.1 and r > 2:
            action, icon = '放量', '🔥'
        
        if action:
            log.info(f"{action} {stock} {get_security_info(stock).display_name} 换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x {icon}")
            order_result = order_target_value(stock, 0)
            # 完全按文档添加跟单调用（卖出）
            if order_result and hasattr(order_result, 'filled') and order_result.filled > 0:
                is_buy = False
                filled_price = order_result.price if hasattr(order_result, 'price') and order_result.price > 0 else get_current_data()[stock].last_price
                _jqmt_after_order(stock, is_buy, order_result.filled, filled_price, str(order_result.order_id) if hasattr(order_result, 'order_id') else "")

def check_high_volume(context):
    if not g.HV_control:
        return
        
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
            
        df_volume = get_bars(stock, count=g.HV_duration, unit='1d', fields=['volume'], include_now=True, df=True)
        if len(df_volume) < g.HV_duration:
            continue
            
        if df_volume['volume'].values[-1] > g.HV_ratio * df_volume['volume'].values.max():
            log.info("[%s]天量，卖出" % stock)
            order_result = order_target_value(stock, 0)
            # 完全按文档添加跟单调用（卖出）
            if order_result and hasattr(order_result, 'filled') and order_result.filled > 0:
                is_buy = False
                filled_price = order_result.price if hasattr(order_result, 'price') and order_result.price > 0 else get_current_data()[stock].last_price
                _jqmt_after_order(stock, is_buy, order_result.filled, filled_price, str(order_result.order_id) if hasattr(order_result, 'order_id') else "")

def trade_afternoon(context):
    check_limit_up(context)
    huanshou(context)