# Clone from JoinQuant
# postId: 4fb61c9d88ec606bda8f84b0e9f53851
# backtestId: 20e6ad67cedb97029ee19538811a7141
# title: 多策略动态调整仓位-模拟盘效果好

# 克隆自聚宽文章：https://www.joinquant.com/post/57647
# 标题：ST弱转强加入10和1加强版-clone
# 作者：futures hh

# 克隆自聚宽文章：https://www.joinquant.com/post/57581
# 标题：10和1多策略基于波动性和相关性动态调整策略比例
# 作者：金刚王

# 克隆自聚宽文章：https://www.joinquant.com/post/57581
# 标题：多策略根据波动性和相关性动态调整策略比例
# 作者：金刚王

# 克隆自聚宽文章：https://www.joinquant.com/post/53303
# 标题：多策略最终版
# 作者：z i

# 克隆自聚宽文章：https://www.joinquant.com/post/53303
# 标题：多策略最终版
# 作者：韭 皇

import math
import datetime
import numpy as np
import pandas as pd
from jqdata import *
import statsmodels.api as sm
from tabulate import tabulate
from sklearn.cluster import KMeans
from collections import OrderedDict
from jqfactor import get_factor_values

LOG_ENABLED = False   # 金融数据日志 False True
global_sold_stock_record = {}# 全局卖出记录

TURNOVER_TIMING_STRATEGIES = []  # 换手率择时
NEW_TIMING_STRATEGIES = [] #[1, 4]  # 需要应用宽度择时的子策略
STIR_UP_INDUSTRY_STRATEGIES = [0]  # 需要应用搅屎棍行业清仓的子策略
EMPTY_POSITION_STRATEGIES = [0] #[4, 5, 6, 9, 10]# 1、4月需要空仓的子策略
TIMING_STRATEGIES = []  # 需要应用择时的子策略


def initialize(context):
    set_benchmark("000300.XSHG")
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    log.set_level("order", "error")
    strategy_configs = [

        (0, "微盘", wp_Strategy, 0.5),

        (1, "核心", hx_Strategy, 0.5),

    ]
    
    """
 [
        (0, "现金", None, 0),
        (1, "破净", pj_Strategy, 0.05),
        (2, "周期", zq_Strategy, 0.05),
        (3, "红利", hl_Strategy, 0.1),
        (4, "微盘", wp_Strategy, 0.2),
        (5, "成长", cz_Strategy, 0.1),
        (6, "大妈", dm_Strategy, 0.1),
        (7, "全天", qt_Strategy, 0.05),
        (8, "核心", hx_Strategy, 0.1),
        (9, "因子", yz_Strategy, 0.05),
        (10, "测试", cs_Strategy, 0.05),
        (11, "相关", xg_Strategy, 0.05),
        (12, "弱转强", rzq_Strategy, 0.1)  # 新增弱转强策略
    ]
    """

    g.portfolio_value_proportion = [config[3] for config in strategy_configs]
    set_subportfolios([SubPortfolioConfig(context.portfolio.starting_cash * prop, "stock") 
    for prop in g.portfolio_value_proportion])

    # 初始化策略
    g.strategys = {}
    for index, name, strategy_class, proportion in strategy_configs:
        if strategy_class:
            subportfolio_index = int(index)
            g.strategys[name] = strategy_class(context, subportfolio_index=subportfolio_index, name=name)


    # 设置调仓
    run_monthly(balance_subportfolios, 1, "9:02")  # 资金平衡
    run_monthly(adjust_strategy_proportions, 1, "9:01")  # 每月动态调整策略比例
    run_daily(record_all_strategies_daily_value, "15:01")  # 记录收益
    run_daily(update_stock_lists, "9:01")  # 金融数据日志更新
    run_weekly(calculate_and_log_volatility_and_correlation, 1, "15:30")  # 记录波动相关
    run_daily(check_width_timing, "14:50")  # 宽度清仓
    run_daily(check_turnover_timing, "14:20")  # 换手清仓




    # 核心策略调仓设置
    if g.portfolio_value_proportion[1] > 0:
        run_daily(adjust_hx_strategy, "10:05")
    # 微盘策略调仓设置
    if g.portfolio_value_proportion[0] > 0:
        run_daily(prepare_wp_strategy, "9:06")
        run_weekly(adjust_wp_strategy, 1, "14:50")
        run_daily(check_wp_limit_up, "14:55")
        
    """
    # 破净策略调仓设置
    if g.portfolio_value_proportion[1] > 0:
        run_daily(prepare_pj_strategy, "9:03")
        run_monthly(adjust_pj_strategy, 1, "9:30")
        run_daily(check_pj_limit_up, "14:00")
        run_daily(check_pj_limit_up, "14:50")

    # 周期策略调仓设置
    if g.portfolio_value_proportion[2] > 0:
        run_daily(prepare_zq_strategy, "9:04")
        run_monthly(adjust_zq_strategy, 1, "9:35")
        run_daily(check_zq_limit_up, "14:05")

    # 红利策略调仓设置
    if g.portfolio_value_proportion[3] > 0:
        run_daily(prepare_hl_strategy, "9:05")
        run_monthly(adjust_hl_strategy, 1, "9:40")
        run_daily(check_hl_limit_up, "14:10")

    # 微盘策略调仓设置
    if g.portfolio_value_proportion[4] > 0:
        run_daily(prepare_wp_strategy, "9:06")
        run_weekly(adjust_wp_strategy, 1, "14:50")
        run_daily(check_wp_limit_up, "14:55")

    # 成长策略调仓设置
    if g.portfolio_value_proportion[5] > 0:
        run_daily(prepare_cz_strategy, "9:07")
        run_weekly(adjust_cz_strategy, 1, "11:02")
        run_daily(check_cz_limit_up, "14:02")

    # 大妈策略调仓设置
    if g.portfolio_value_proportion[6] > 0:
        run_daily(prepare_dm_strategy, "9:08")
        run_weekly(adjust_dm_strategy, 1, "11:03")
        run_daily(check_dm_limit_up, "14:03")

    # 全天策略调仓设置
    if g.portfolio_value_proportion[7] > 0:
        run_monthly(adjust_qt_strategy, 1, "10:00")

    # 核心策略调仓设置
    if g.portfolio_value_proportion[1] > 0:
        run_daily(adjust_hx_strategy, "10:05")

    # 因子策略调仓设置
    if g.portfolio_value_proportion[9] > 0:
        run_daily(prepare_yz_strategy, "9:09")
        run_monthly(adjust_yz_strategy, 1, "11:04")
        run_daily(check_yz_limit_up, "14:04")

    # 测试策略调仓设置
    if g.portfolio_value_proportion[10] > 0:
        run_daily(prepare_cs_strategy, "9:10")
        run_monthly(adjust_cs_strategy, 1, "10:50")
        run_daily(check_cs_limit_up, "13:50")

    # 相关策略调仓设置
    if g.portfolio_value_proportion[11] > 0:
        run_daily(prepare_xg_strategy, "9:11")
        run_monthly(adjust_xg_strategy, 1, "10:10")
        run_daily(check_xg_limit_up, "14:10")
        
    # 弱转强策略调仓设置
    if g.portfolio_value_proportion[12] > 0:
        run_daily(prepare_rzq_strategy, "9:25")
        run_daily(adjust_rzq_strategy, "9:30")
        run_daily(check_rzq_strategy, "13:00")
        run_daily(check_rzq_strategy, "14:00")
        run_daily(dieting_rzq, "every_bar")
        """
# 破净策略
def prepare_pj_strategy(context): g.strategys["破净"].prepare(context)
def adjust_pj_strategy(context): g.strategys["破净"].adjust(context)
def check_pj_limit_up(context):
    sold_stocks = g.strategys["破净"].check(context)
    if sold_stocks:g.strategys["破净"].buy_after_sell(context, sold_stocks)

# 周期策略
def prepare_zq_strategy(context): g.strategys["周期"].prepare(context)
def adjust_zq_strategy(context): g.strategys["周期"].adjust(context)
def check_zq_limit_up(context):
    sold_stocks = g.strategys["周期"].check(context)
    if sold_stocks:g.strategys["周期"].buy_after_sell(context, sold_stocks)

# 红利策略
def prepare_hl_strategy(context): g.strategys["红利"].prepare(context)
def adjust_hl_strategy(context): g.strategys["红利"].adjust(context)
def check_hl_limit_up(context):
    sold_stocks = g.strategys["红利"].check(context)
    if sold_stocks:g.strategys["红利"].buy_after_sell(context, sold_stocks)

# 微盘策略
def prepare_wp_strategy(context): g.strategys["微盘"].prepare(context)
def adjust_wp_strategy(context): g.strategys["微盘"].adjust(context)
def check_wp_limit_up(context):
    sold_stocks = g.strategys["微盘"].check(context)
    if sold_stocks:g.strategys["微盘"].buy_after_sell(context, sold_stocks)

# 成长策略
def prepare_cz_strategy(context): g.strategys["成长"].prepare(context)
def adjust_cz_strategy(context): g.strategys["成长"].adjust(context)
def check_cz_limit_up(context):
    sold_stocks = g.strategys["成长"].check(context)
    if sold_stocks:g.strategys["成长"].buy_after_sell(context, sold_stocks)

# 大妈策略
def prepare_dm_strategy(context): g.strategys["大妈"].prepare(context)
def adjust_dm_strategy(context): g.strategys["大妈"].adjust(context)
def check_dm_limit_up(context):
    sold_stocks = g.strategys["大妈"].check(context)
    if sold_stocks:g.strategys["大妈"].buy_after_sell(context, sold_stocks)

# 全天策略
def adjust_qt_strategy(context): g.strategys["全天"].adjust(context)

# 核心策略
def adjust_hx_strategy(context): g.strategys["核心"].adjust(context)

# 因子策略
def prepare_yz_strategy(context): g.strategys["因子"].prepare(context)
def adjust_yz_strategy(context): g.strategys["因子"].adjust(context)
def check_yz_limit_up(context):
    sold_stocks = g.strategys["因子"].check(context)
    if sold_stocks:g.strategys["因子"].buy_after_sell(context, sold_stocks)

# 测试策略
def prepare_cs_strategy(context): g.strategys["测试"].prepare(context)
def adjust_cs_strategy(context): g.strategys["测试"].adjust(context)
def check_cs_limit_up(context):
    sold_stocks = g.strategys["测试"].check(context)
    if sold_stocks:g.strategys["测试"].buy_after_sell(context, sold_stocks)

# 相关策略
def prepare_xg_strategy(context): g.strategys["相关"].prepare(context)
def adjust_xg_strategy(context): g.strategys["相关"].adjust(context)
def check_xg_limit_up(context):
    sold_stocks = g.strategys["相关"].check(context)
    if sold_stocks:g.strategys["相关"].buy_after_sell(context, sold_stocks)
   
# 弱转强策略的调用函数
def prepare_rzq_strategy(context): 
    g.strategys["弱转强"].prepare(context)
    
def adjust_rzq_strategy(context): 
    g.strategys["弱转强"].adjust(context)
    
def check_rzq_strategy(context):
    g.strategys["弱转强"].check(context)
    
def dieting_rzq(context):
    g.strategys["弱转强"].dieting_check(context)     
        

# 全局择时指标配置（用哪个开哪个False True，全部开启运算爆表）
GLOBAL_TIMING_CONFIG = {
    "exclude_industries": {"enabled": False, "value": ["000000"]}, # 过滤行业
    "industry_score":     {"enabled": False, "value": (-100, 100)}, # 行业宽度分
    "industry_diff":      {"enabled": False, "value": (-100, 100)}, # 5日行业平均差
    "pe":                 {"enabled": False, "value": (-100, 100)}, # 市盈率PE
    "pb":                 {"enabled": False, "value": (-100, 100)}, # 市净率PB
    "roa":                {"enabled": False, "value": (-100, 100)}, # 总资产收益率ROA
    "roe":                {"enabled": False, "value": (-100, 100)}, # 净资产收益率ROE
    "turnover":           {"enabled": False, "value": (5, 15)},     # 换手率
    "turnover_diff":      {"enabled": False, "value": (-100, 100)}, # 5日换手平均差
    "pct_change":         {"enabled": False, "value": (-100,100)},  # 涨幅
    "pct_change_5d":      {"enabled": False, "value": (-100, 100)}, # 5日涨幅平均差
    "market_cap":         {"enabled": True, "value": (30, 1000)}    # 市值范围（亿）
}



# 中央数据管理器==========================================================
class DataManager:
    def __init__(self, max_cache_size = 100):
        self.cache = OrderedDict()
        self.max_cache_size = max_cache_size

    def get_data(self, key, func, *args, **kwargs):
        if key not in self.cache:
            if len(self.cache) >= self.max_cache_size:
                self.cache.popitem(last = False)
            self.cache[key] = func(*args, **kwargs)
        self.cache.move_to_end(key)
        return self.cache[key]
data_manager = DataManager()


#过滤条件==========================================================
# 过滤20天内卖出的股票
def filter_recently_sold(stocks, current_date):
    return [stock for stock in stocks if
            stock not in global_sold_stock_record or (current_date - global_sold_stock_record[stock]).days >= 20]

# 过滤20天内涨停过的股票
def filter_limit_up_stocks(context, stocks):
    end_date = context.previous_date
    start_date = end_date - datetime.timedelta(days=20)
    new_stocks = []
    for stock in stocks:
        try:
            df = get_price(stock, start_date=start_date, end_date=end_date, frequency='daily', fields=['close', 'high_limit'])
            if not any(df['close'] == df['high_limit']):
                new_stocks.append(stock)
        except Exception as e:
            print(f"获取 {stock} 价格数据时出错: {e}")
    return new_stocks

# 过滤20天内涨幅超过20%的股票
def filter_over_20_percent_increase(context, stocks):
    end_date = context.previous_date
    start_date = end_date - datetime.timedelta(days=20)
    new_stocks = []
    for stock in stocks:
        try:
            prices = get_price(stock, start_date=start_date, end_date=end_date, frequency='daily', fields=['close'])
            start_price = prices['close'].iloc[0]
            end_price = prices['close'].iloc[-1]
            increase_percent = (end_price - start_price) / start_price * 100
            if increase_percent <= 20:
                new_stocks.append(stock)
        except Exception as e:
            print(f"获取 {stock} 价格数据时出错: {e}")
    return new_stocks
    
# 行业股票数量限制
def filter_stocks_by_industry(stocks, industry_info, max_industry_stocks):
    selected_stocks = []
    industry_count = {}
    for stock in stocks:
        industry = industry_info[stock]
        if industry not in industry_count:
            industry_count[industry] = 0
        if industry_count[industry] < max_industry_stocks:
            selected_stocks.append(stock)
            industry_count[industry] += 1
    return selected_stocks
# 1、4月空仓择时==========================================================
def empty_position_in_jan_apr(context, strategy):
    current_month = context.current_dt.month
    if current_month in [1, 4]:
        index = int(strategy.subportfolio_index)
        subportfolio = context.subportfolios[index]
        for security in list(subportfolio.long_positions.keys()):
            strategy.close_position(security) 
        strategy.hold_list = []
        return True
    return False      
    
#换手率择时==========================================================
def check_turnover_timing(context):
    for strategy_name, strategy in g.strategys.items():
        if strategy.subportfolio_index in TURNOVER_TIMING_STRATEGIES:
            subportfolio = context.subportfolios[strategy.subportfolio_index]
            holdings = list(subportfolio.long_positions.keys())
            if not holdings:
                continue

            try:
                all_prices = get_price(holdings, end_date=context.previous_date, frequency="1d", fields=["close", "volume"], count=6, panel=False)
            except ValueError as e:
                continue

            df = get_fundamentals(
                query(valuation.code, valuation.circulating_cap)
               .filter(valuation.code.in_(holdings)),
                date=context.previous_date
            )
            all_circulating_cap = dict(zip(df['code'], df['circulating_cap'])) if not df.empty else {}

            all_volume = {}
            all_volume_5d = {}
            all_turnover = {}
            all_turnover_5d = {}
            all_turnover_diff = {}

            for stock in holdings:
                try:
                    # 使用 loc 方法代替 at 方法
                    all_volume[stock] = all_prices.loc[all_prices['code'] == stock, 'volume'].iloc[:1].values[0]
                    all_volume_5d[stock] = all_prices.loc[all_prices['code'] == stock, 'volume'].iloc[:5].mean()

                    circulating_cap = all_circulating_cap.get(stock)
                    if circulating_cap and circulating_cap > 0:
                        all_turnover[stock] = all_volume[stock] / (circulating_cap * 10000)
                        all_turnover_5d[stock] = all_volume_5d[stock] / (circulating_cap * 10000)
                        all_turnover_diff[stock] = ((all_turnover[stock] - all_turnover_5d[stock]) / all_turnover_5d[stock] * 100) if all_turnover_5d[stock] else 0
                    else:
                        all_turnover[stock] = None
                        all_turnover_5d[stock] = None
                        all_turnover_diff[stock] = None
                except (KeyError, IndexError):
                    all_turnover[stock] = None
                    all_turnover_5d[stock] = None
                    all_turnover_diff[stock] = None

            min_turnover_diff, max_turnover_diff = GLOBAL_TIMING_CONFIG["turnover_diff"]["value"]
            for stock in holdings:
                turnover_diff = all_turnover_diff.get(stock)
                if turnover_diff is not None and (turnover_diff < min_turnover_diff or turnover_diff > max_turnover_diff):
                    strategy.close_position(stock)
                    strategy.hold_list = [s for s in strategy.hold_list if s != stock]
                    global_sold_stock_record[stock] = context.current_dt.date()
#搅屎棍择时 ==========================================================
def check_stir_up_industry(context, strategy):
    stocks = data_manager.get_data(
        f"index_stocks_000985_{context.previous_date.strftime('%Y-%m')}",
        get_index_stocks,
        "000985.XSHG"
    )
    prices = data_manager.get_data(
        f"market_breadth_prices_{stocks}_{context.previous_date.strftime('%Y-%m')}",
        get_price,
        stocks, end_date=context.previous_date, frequency="1d", fields=["close"], count=21, panel=False
    )
    prices["date"] = pd.DatetimeIndex(prices.time).date
    close_pivot = prices.pivot(index="code", columns="date", values="close").dropna(axis=0)
    ma20 = close_pivot.rolling(window=20, axis=1).mean().iloc[:, -1:]
    bias = close_pivot.iloc[:, -1:] > ma20
    industry_names = strategy.getStockIndustry(stocks)
    bias["industry_name"] = industry_names
    industry_scores = (bias.groupby("industry_name").sum() * 100.0 / bias.groupby("industry_name").count()).round().iloc[:, -1]
    top_industry = industry_scores.nlargest(1).index[0]

    stir_up_industries = ["银行I"]
    if top_industry in stir_up_industries and strategy.subportfolio_index in STIR_UP_INDUSTRY_STRATEGIES:
        index = int(strategy.subportfolio_index)
        subportfolio = context.subportfolios[index]
        for security in list(subportfolio.long_positions.keys()):
            strategy.close_position(security)
        strategy.hold_list = []
        return True
    return False

#宽度分择时==========================================================
# 宽度分择时==========================================================
def check_width_timing(context):
    for strategy_name, strategy in g.strategys.items():
        if strategy.subportfolio_index in NEW_TIMING_STRATEGIES:
            # 获取指数成分股
            stocks = data_manager.get_data(
                f"index_stocks_000985_{context.previous_date.strftime('%Y-%m')}",
                get_index_stocks,
                "000985.XSHG"
            )
            # 获取前一交易日及前6个交易日的价格数据
            prices = data_manager.get_data(
                f"market_breadth_prices_{stocks}_{context.previous_date.strftime('%Y-%m-%d')}",
                get_price,
                stocks, end_date=context.previous_date, frequency="1d", fields=["close"], count=7, panel=False
            )
            prices["date"] = pd.DatetimeIndex(prices.time).date
            close_pivot = prices.pivot(index="code", columns="date", values="close").dropna(axis=0)
            # 计算前5个交易日宽度总分平均值
            prev_5_days_close_pivot = close_pivot.iloc[:, -6:-1]
            prev_5_days_ma5 = prev_5_days_close_pivot.rolling(window=5, axis=1).mean().iloc[:, -1:]
            prev_5_days_bias = prev_5_days_close_pivot.iloc[:, -1:] > prev_5_days_ma5
            prev_5_days_daily_scores = (prev_5_days_bias.sum() * 100.0 / prev_5_days_bias.count()).round()
            prev_5_days_avg_score = prev_5_days_daily_scores.iloc[-1]

            # 计算当天的宽度分（使用实时数据）
            current_data = get_current_data()
            current_prices = pd.Series({stock: current_data[stock].last_price for stock in stocks if stock in current_data})
            current_ma5 = close_pivot.iloc[:, -5:].mean(axis=1)
            valid_stocks = current_prices.index.intersection(current_ma5.index)
            current_prices = current_prices[valid_stocks]
            current_ma5 = current_ma5[valid_stocks]
            current_bias = current_prices > current_ma5

            
            # 修改：添加对valid_stocks是否为空的检查
            if len(valid_stocks) == 0:
                log.warning(f"valid_stocks为空，跳过{strategy_name}的宽度择时计算")
                continue  # 跳过当前策略的计算
            current_bias = current_prices > current_ma5
            current_score = (current_bias.sum() * 100.0 / current_bias.count()).round()
            # 修改：简化条件判断
            if current_bias.count() > 0:  # 只有存在有效股票时才计算分数
                current_score = (current_bias.sum() * 100.0 / current_bias.count()).round()
            else:
                current_score = 0  # 无有效股票时分数为0
                log.warning(f"current_bias.count()为0，设置current_score为0")

            # 判断是否需要空仓
            if current_score < prev_5_days_avg_score * 0.8:
                index = int(strategy.subportfolio_index)
                subportfolio = context.subportfolios[index]
                for security in list(subportfolio.long_positions.keys()):
                    strategy.close_position(security)
                strategy.hold_list = []
            
# 计算股息率并筛选股票列表==========================================================
def calculate_dividend_ratio(context, stock_list, sort, p1, p2):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365)
    interval = 1000
    list_len = len(stock_list)
    q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)])
    )
    df = finance.run_query(q)
    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[interval * (i + 1):min(list_len, interval * (i + 2))])
            )
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    dividend = df.fillna(0)
    dividend = dividend.set_index('code')
    dividend = dividend.groupby('code').sum()
    temp_list = list(dividend.index)
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1)
    cap = cap.set_index('code')
    DR = pd.concat([dividend, cap], axis=1, sort=False)
    DR['dividend_ratio'] = (DR['bonus_amount_rmb'] / 10000) / DR['market_cap']
    DR = DR.sort_values(by=['dividend_ratio'], ascending=sort)
    return list(DR.index)[int(p1 * len(DR)):int(p2 * len(DR))]


# 资金平衡函数==========================================================
def balance_subportfolios(context):
    for i in range(1, len(g.portfolio_value_proportion)):
        target = g.portfolio_value_proportion[i] * context.portfolio.total_value
        value = context.subportfolios[i].total_value
        deviation = abs((value - target) / target) if target!= 0 else 0
        if deviation > 0.2:
            if context.subportfolios[i].available_cash > 0 and target < value:
                transfer_cash(from_pindex=i, to_pindex=0, cash=min(value - target, context.subportfolios[i].available_cash))
            if target > value and context.subportfolios[0].available_cash > 0:
                transfer_cash(from_pindex=0, to_pindex=i, cash=min(target - value, context.subportfolios[0].available_cash))

# 记录收益==========================================================
def record_all_strategies_daily_value(context):
    for strategy in g.strategys.values():
        strategy.record_daily_value(context)
        
#记录波动相关==========================================================
def calculate_and_log_volatility_and_correlation(context):
    strategy_names = list(g.strategys.keys())
    num_strategies = len(strategy_names)

    # 收集各策略的每日资产价值
    value_df = pd.DataFrame()
    for name in strategy_names:
        strategy = g.strategys[name]
        value_df[name] = strategy.portfolio_value['total_value']

    # 计算波动性
    volatility = value_df.pct_change().std() * np.sqrt(252)  # 年化波动率
    volatility = volatility.round(2)

    # 计算相关性
    correlation = value_df.pct_change().corr()
    correlation = correlation.round(2)

    # 根据波动性和相关性优化比例
    inv_volatility = 1 / volatility
    suggested_proportions = inv_volatility / inv_volatility.sum()
    
    # 考虑相关性进行调整
    if len(correlation) > 1:  # 至少需要两个策略才能计算相关性
        # 计算每个策略与其他策略的平均相关性
        avg_correlation = correlation.mean()
        # 相关性低的策略获得更高的权重
        correlation_adjustment = 1 - avg_correlation
        correlation_adjustment = correlation_adjustment / correlation_adjustment.sum()
        # 综合波动率和相关性（各占50%权重）
        suggested_proportions = 0.5 * suggested_proportions + 0.5 * correlation_adjustment
        
    suggested_proportions = suggested_proportions.round(2)
    
    # 存储建议比例以便下次调整时使用
    g.suggested_proportions = suggested_proportions

    # 构建合并后的数据
    combined_data = [["策略名称", "波动性", "原始比例", "建议比例"]]
    for i, name in enumerate(strategy_names):
        if i == 0:  # 跳过现金策略
            continue
        original_ratio = g.portfolio_value_proportion[i]
        suggested_ratio = suggested_proportions[name] if name in suggested_proportions else 0
        if abs(original_ratio - suggested_ratio) > 0.2:
            mark = "*"
        else:
            mark = ""
        original_ratio_str = str(original_ratio) if not pd.isnull(original_ratio) else "nan"
        suggested_ratio_str = str(suggested_ratio) if not pd.isnull(suggested_ratio) else "nan"
        volatility_value = volatility[name] if name in volatility else "nan"
        combined_data.append([name, volatility_value, original_ratio_str, suggested_ratio_str + mark])

    if combined_data:
        combined_table = tabulate(combined_data, headers="firstrow", tablefmt="plain")
        log.info("\n" + combined_table)
    else:
        log.info("合并后的数据列表为空")

    # 输出相关性日志
    correlation_data = [[""] + strategy_names]
    for i in range(num_strategies):
        row = [strategy_names[i]] + list(correlation.iloc[i])
        row = [str(x) if not pd.isnull(x) else "nan" for x in row]
        correlation_data.append(row)
    if correlation_data:
        correlation_table = tabulate(correlation_data, headers="firstrow", tablefmt="plain")
        log.info("\n" + correlation_table)
    else:
        log.info("相关性列表为空")
        
# 新增: 每月动态调整策略比例
def adjust_strategy_proportions(context):
    # 如果没有建议比例，则跳过
    if not hasattr(g, 'suggested_proportions') or g.suggested_proportions is None:
        log.info("没有可用的建议比例数据，跳过调整")
        return
    
    suggested_proportions = g.suggested_proportions
    strategy_names = list(g.strategys.keys())
    
    # 确保portfolio_value_proportion已初始化
    if not hasattr(g, 'portfolio_value_proportion') or g.portfolio_value_proportion is None:
        log.warning("portfolio_value_proportion未初始化，使用默认比例")
        # 创建默认比例 - 平均分配除空策略外的所有策略
        active_strategies = [name for name in strategy_names]
        default_proportion = 1.0 / len(active_strategies) if active_strategies else 0
        g.portfolio_value_proportion = [default_proportion for _ in strategy_names]
    
    # 打印调整前的策略比例
    original_proportions = {}
    for i, name in enumerate(strategy_names):
        original_proportions[name] = g.portfolio_value_proportion[i]
    
    log.info(f"调整前的策略比例: {original_proportions}")
    
    # 过滤掉无效的建议比例(nan或0波动率的策略)
    valid_suggestions = {}
    for name in strategy_names:
        if name in suggested_proportions.index and not pd.isna(suggested_proportions[name]) and suggested_proportions[name] > 0:
            valid_suggestions[name] = suggested_proportions[name]
    
    # 如果没有有效建议，跳过
    if not valid_suggestions:
        log.info("没有有效的建议比例，跳过调整")
        return
    
    # 归一化有效建议比例 - 修复计算方式
    values_list = list(valid_suggestions.values())  # 转换为列表
    total_value = sum(values_list)  # 计算总和
    
    if total_value <= 0:
        log.info("所有有效建议比例总和为零，跳过调整")
        return
        
    normalized_suggestions = {k: v/total_value for k, v in valid_suggestions.items()}
    
    # 仅当建议比例与当前比例差异较大时才调整
    need_adjustment = False
    for name, suggested_proportion in normalized_suggestions.items():
        strategy_index = strategy_names.index(name)
        current_proportion = g.portfolio_value_proportion[strategy_index]
        if abs(current_proportion - suggested_proportion) > 0.05:  # 5%以上的差异才调整
            need_adjustment = True
            break
    
    if not need_adjustment:
        log.info("策略比例差异较小，无需调整")
        return
    
    log.info("开始动态调整策略比例...")
    
    # 计算新的比例
    new_proportions = g.portfolio_value_proportion.copy()
    
    # 对于有效策略，更新为建议比例
    total_valid_proportion = 0
    for i, name in enumerate(strategy_names):
        if name in normalized_suggestions:
            new_proportions[i] = normalized_suggestions[name]
            total_valid_proportion += normalized_suggestions[name]
    
    # 对于无效策略，按原比例分配剩余资金
    if total_valid_proportion < 1.0 and total_valid_proportion > 0:
        remaining_proportion = 1.0 - total_valid_proportion
        
        # 计算无效策略的原始总比例
        invalid_strategies = [name for name in strategy_names if name not in normalized_suggestions]
        original_invalid_total = sum(original_proportions[name] for name in invalid_strategies)
        
        # 如果原始比例不为零，按比例分配
        if original_invalid_total > 0:
            for name in invalid_strategies:
                i = strategy_names.index(name)
                new_proportions[i] = remaining_proportion * (original_proportions[name] / original_invalid_total)
        # 否则平均分配
        elif invalid_strategies:
            for name in invalid_strategies:
                i = strategy_names.index(name)
                new_proportions[i] = remaining_proportion / len(invalid_strategies)
    
    # 确保总和为1
    total_new = sum(new_proportions)
    if abs(total_new - 1) > 0.001:  # 允许一点舍入误差
        log.warning(f"新比例总和为{total_new}，进行归一化")
        new_proportions = [p / total_new for p in new_proportions]
    
    # 更新全局比例
    g.portfolio_value_proportion = new_proportions
    
    # 创建比较表格数据
    table_data = [["策略名称", "调整前比例", "调整后比例", "变化"]]
    for i, name in enumerate(strategy_names):
        before = original_proportions[name]
        after = g.portfolio_value_proportion[i]
        change = after - before
        change_str = f"{change:.2%}" if abs(change) > 0.001 else "-"
        table_data.append([name, f"{before:.2%}", f"{after:.2%}", change_str])
    
    # 使用tabulate输出格式化表格
    adjustment_table = tabulate(table_data, headers="firstrow", tablefmt="plain")
    log.info(f"\n月度策略比例调整 ({context.current_dt.strftime('%Y-%m-%d')}):\n{adjustment_table}")
    
    # 调用资金平衡函数来实际执行调整
    balance_subportfolios(context)




# 全局择时过滤函数==========================================================
def global_timing_filter(context, stocks):
    if not stocks:
        return []
    try:
        all_prices = get_price(stocks, end_date=context.previous_date, frequency="1d", fields=["close", "volume"], count=6, panel=False)
    except ValueError as e:
        return []

    all_industry = get_industry(stocks)
    all_prices.set_index('code', inplace=True)
    df = get_fundamentals(
        query(valuation.code, valuation.pe_ratio, valuation.pb_ratio, indicator.roe, indicator.roa, valuation.market_cap, valuation.circulating_cap)
       .filter(valuation.code.in_(stocks)),
        date=context.previous_date
    )
    all_pe = dict(zip(df['code'], df['pe_ratio'])) if not df.empty else {}
    all_pb = dict(zip(df['code'], df['pb_ratio'])) if not df.empty else {}
    all_roe = dict(zip(df['code'], df['roe'])) if not df.empty else {}
    all_roa = dict(zip(df['code'], df['roa'])) if not df.empty else {}
    all_market_cap = dict(zip(df['code'], df['market_cap'])) if not df.empty else {}
    all_circulating_cap = dict(zip(df['code'], df['circulating_cap'])) if not df.empty else {}

    all_volume = {}
    all_volume_5d = {}
    all_turnover = {}
    all_turnover_5d = {}
    all_pct_change = {}
    all_pct_change_5d = {}

    for stock in stocks:
        try:
            close_prices = all_prices.at[stock, 'close'][:2]
            prev_close = close_prices[0]
            curr_close = close_prices[1]
            all_pct_change[stock] = round((curr_close - prev_close) / prev_close * 100, 2)
            all_volume[stock] = all_prices.at[stock, 'volume'][:1][0]
            all_volume_5d[stock] = all_prices.at[stock, 'volume'][:5].mean()

            circulating_cap = all_circulating_cap.get(stock)
            if circulating_cap and circulating_cap > 0:
                all_turnover[stock] = all_volume[stock] / (circulating_cap * 10000)
                all_turnover_5d[stock] = all_volume_5d[stock] / (circulating_cap * 10000)
            else:
                all_turnover[stock] = None
                all_turnover_5d[stock] = None

            close_prices_5d = pd.Series(all_prices.at[stock, 'close'][:5])
            all_pct_change_5d[stock] = round((close_prices_5d.pct_change().dropna().mean()) * 100, 2)
        except KeyError:
            all_pct_change[stock] = 0
            all_volume[stock] = None
            all_volume_5d[stock] = None
            all_turnover[stock] = None
            all_turnover_5d[stock] = None
            all_pct_change_5d[stock] = 0

    def calculate_industry_scores(stocks, industry_code_dict, end_date):
        industry_scores = {}
        for stock in stocks:
            industry_code = industry_code_dict[stock]
            if industry_code and industry_code not in industry_scores:
                try:
                    stocks_in_industry = get_industry_stocks(industry_code)
                    prices = get_price(stocks_in_industry, end_date=end_date, frequency="1d", fields=["close"], count=21, panel=False)
                    prices["date"] = pd.DatetimeIndex(prices.time).date
                    close_pivot = prices.pivot(index="code", columns="date", values="close").dropna(axis=0)
                    ma20 = close_pivot.rolling(window=20, axis=1).mean().iloc[:, -1:]
                    bias = close_pivot.iloc[:, -1:] > ma20
                    score = (bias.sum() * 100.0 / bias.count()).round().iloc[0]
                    industry_scores[industry_code] = score
                except Exception as e:
                    log.error(f"行业代码: {industry_code}, 错误: {e}")
        return industry_scores

    industry_code_dict = {stock: all_industry.get(stock, {}).get("sw_l1", {}).get("industry_code", "") for stock in stocks}
    industry_scores = {}
    five_day_avg_industry_scores = {}
    if GLOBAL_TIMING_CONFIG["industry_score"]["enabled"] or GLOBAL_TIMING_CONFIG["industry_diff"]["enabled"]:
        industry_scores = calculate_industry_scores(stocks, industry_code_dict, context.previous_date)
        for i in range(1, 6):
            end_date = context.previous_date - datetime.timedelta(days=i)
            daily_industry_scores = calculate_industry_scores(stocks, industry_code_dict, end_date)
            for industry_code, score in daily_industry_scores.items():
                if industry_code not in five_day_avg_industry_scores:
                    five_day_avg_industry_scores[industry_code] = []
                five_day_avg_industry_scores[industry_code].append(score)
        for industry_code in five_day_avg_industry_scores:
            five_day_avg_industry_scores[industry_code] = sum(five_day_avg_industry_scores[industry_code]) / len(five_day_avg_industry_scores[industry_code])

    filtered_stocks = []
    for stock in stocks:
        industry_code = industry_code_dict.get(stock)
        if GLOBAL_TIMING_CONFIG["exclude_industries"]["enabled"] and industry_code in GLOBAL_TIMING_CONFIG["exclude_industries"]["value"]:
            continue

        industry_score = industry_scores.get(industry_code, 0)
        industry_diff = industry_score - five_day_avg_industry_scores.get(industry_code, 0)
        pe = all_pe.get(stock)
        pb = all_pb.get(stock)
        roa = all_roa.get(stock)
        roe = all_roe.get(stock)
        turnover = all_turnover.get(stock)
        turnover_diff = ((turnover - all_turnover_5d.get(stock)) / all_turnover_5d.get(stock) * 100) if all_turnover_5d.get(stock) else 0
        pct_change = all_pct_change.get(stock)
        pct_change_5d = all_pct_change_5d.get(stock)
        market_cap = all_market_cap.get(stock)

        conditions = []

        if GLOBAL_TIMING_CONFIG["industry_score"]["enabled"]:
            min_score, max_score = GLOBAL_TIMING_CONFIG["industry_score"]["value"]
            conditions.append(min_score < industry_score < max_score)
        if GLOBAL_TIMING_CONFIG["industry_diff"]["enabled"]:
            min_diff, max_diff = GLOBAL_TIMING_CONFIG["industry_diff"]["value"]
            conditions.append(min_diff < industry_diff < max_diff)
        if GLOBAL_TIMING_CONFIG["pe"]["enabled"]:
            min_pe, max_pe = GLOBAL_TIMING_CONFIG["pe"]["value"]
            conditions.append(min_pe < pe < max_pe)
        if GLOBAL_TIMING_CONFIG["pb"]["enabled"]:
            min_pb, max_pb = GLOBAL_TIMING_CONFIG["pb"]["value"]
            conditions.append(min_pb < pb < max_pb)
        if GLOBAL_TIMING_CONFIG["roa"]["enabled"]:
            min_roa, max_roa = GLOBAL_TIMING_CONFIG["roa"]["value"]
            conditions.append(min_roa < roa < max_roa)
        if GLOBAL_TIMING_CONFIG["roe"]["enabled"]:
            min_roe, max_roe = GLOBAL_TIMING_CONFIG["roe"]["value"]
            conditions.append(min_roe < roe < max_roe)
        if GLOBAL_TIMING_CONFIG["turnover"]["enabled"]:
            min_turnover, max_turnover = GLOBAL_TIMING_CONFIG["turnover"]["value"]
            conditions.append(min_turnover / 100 < turnover < max_turnover / 100)
        if GLOBAL_TIMING_CONFIG["turnover_diff"]["enabled"]:
            min_turnover_diff, max_turnover_diff = GLOBAL_TIMING_CONFIG["turnover_diff"]["value"]
            conditions.append(min_turnover_diff < turnover_diff < max_turnover_diff)
        if GLOBAL_TIMING_CONFIG["pct_change"]["enabled"]:
            min_pct_change, max_pct_change = GLOBAL_TIMING_CONFIG["pct_change"]["value"]
            conditions.append(min_pct_change < pct_change < max_pct_change)
        if GLOBAL_TIMING_CONFIG["pct_change_5d"]["enabled"]:
            min_pct_change_5d, max_pct_change_5d = GLOBAL_TIMING_CONFIG["pct_change_5d"]["value"]
            conditions.append(min_pct_change_5d < pct_change_5d < max_pct_change_5d)
        if GLOBAL_TIMING_CONFIG["market_cap"]["enabled"]:
            min_market_cap, max_market_cap = GLOBAL_TIMING_CONFIG["market_cap"]["value"]
            conditions.append(min_market_cap < market_cap < max_market_cap)

        if all(conditions):
            filtered_stocks.append(stock)

    return filtered_stocks

# 金融数据日志==========================================================
def update_stock_lists(context):
    def log_stock_info():
        if not LOG_ENABLED:
            return
        # 这里只查询启动的子策略（资金大于0）
        all_strategies = [name for name, strategy in g.strategys.items() if g.portfolio_value_proportion[strategy.subportfolio_index] > 0]
        all_stocks = []
        all_holdings = {}
        all_industry = {}
        all_prices = pd.DataFrame()
        all_pe = {}
        all_pb = {}
        all_roe = {}
        all_roa = {}
        all_volume = {}
        all_volume_5d = {}
        all_turnover = {}
        all_turnover_5d = {}
        all_pct_change = {}
        all_pct_change_5d = {}
        all_market_cap = {}
        all_circulating_cap = {}

        for strategy_name in all_strategies:
            strategy = g.strategys[strategy_name]
            # 跳过不需要股票筛选的策略
            if isinstance(strategy, (qt_Strategy, hx_Strategy, xg_Strategy)):
                continue
            stocks = strategy.select(context) if hasattr(strategy,'select') else strategy.filter(context)
            all_stocks.extend(stocks)
            all_holdings[strategy_name] = set(strategy.hold_list)

        # 批量获取行业信息
        if all_stocks and LOG_ENABLED:
            all_industry = get_industry(all_stocks)

        # 批量获取价格数据
        if all_stocks and LOG_ENABLED:
            all_prices = get_price(all_stocks, end_date=context.previous_date, frequency="1d", fields=["close", "volume"], count=6, panel=False)
            all_prices.set_index('code', inplace=True)
        else:
            all_prices = pd.DataFrame()

        # 批量获取 PE、PB、ROE、ROA、市值、流通股本数据
        if all_stocks and LOG_ENABLED:
            df = get_fundamentals(
                query(valuation.code, valuation.pe_ratio, valuation.pb_ratio, indicator.roe, indicator.roa, valuation.market_cap, valuation.circulating_cap)
               .filter(valuation.code.in_(all_stocks)),
                date=context.previous_date
            )
            all_pe = dict(zip(df['code'], df['pe_ratio'])) if not df.empty else {}
            all_pb = dict(zip(df['code'], df['pb_ratio'])) if not df.empty else {}
            all_roe = dict(zip(df['code'], df['roe'])) if not df.empty else {}
            all_roa = dict(zip(df['code'], df['roa'])) if not df.empty else {}
            all_market_cap = dict(zip(df['code'], df['market_cap'])) if not df.empty else {}
            all_circulating_cap = dict(zip(df['code'], df['circulating_cap'])) if not df.empty else {}
        else:
            all_pe = {}
            all_pb = {}
            all_roe = {}
            all_roa = {}
            all_market_cap = {}
            all_circulating_cap = {}

        # 计算涨跌幅、5 日平均成交量、5 日平均换手率、5 日平均涨幅
        if all_stocks and LOG_ENABLED:
            for stock in all_stocks:
                try:
                    close_prices = all_prices.at[stock, 'close'][:2]
                    prev_close = close_prices[0]
                    curr_close = close_prices[1]
                    all_pct_change[stock] = round((curr_close - prev_close) / prev_close * 100, 2)
                    all_volume[stock] = all_prices.at[stock, 'volume'][:1][0]
                    all_volume_5d[stock] = all_prices.at[stock, 'volume'][:5].mean()

                    circulating_cap = all_circulating_cap.get(stock)
                    if circulating_cap and circulating_cap > 0:
                        all_turnover[stock] = all_volume[stock] / (circulating_cap * 10000)
                        all_turnover_5d[stock] = all_volume_5d[stock] / (circulating_cap * 10000)
                    else:
                        all_turnover[stock] = None
                        all_turnover_5d[stock] = None

                    close_prices_5d = pd.Series(all_prices.at[stock, 'close'][:5])
                    all_pct_change_5d[stock] = round((close_prices_5d.pct_change().dropna().mean()) * 100, 2)
                except KeyError:
                    all_pct_change[stock] = 0
                    all_volume[stock] = None
                    all_volume_5d[stock] = None
                    all_turnover[stock] = None
                    all_turnover_5d[stock] = None
                    all_pct_change_5d[stock] = 0

        def calculate_industry_scores(stocks, industry_code_dict, end_date):
            if not LOG_ENABLED:
                return {}, 0
            industry_scores = {}
            total_score = 0
            for stock in stocks:
                industry_code = industry_code_dict[stock]
                if industry_code and industry_code not in industry_scores:
                    try:
                        stocks_in_industry = get_industry_stocks(industry_code)
                        prices = get_price(stocks_in_industry, end_date=end_date, frequency="1d", fields=["close"], count=21, panel=False)
                        prices["date"] = pd.DatetimeIndex(prices.time).date
                        close_pivot = prices.pivot(index="code", columns="date", values="close").dropna(axis=0)
                        ma20 = close_pivot.rolling(window=20, axis=1).mean().iloc[:, -1:]
                        bias = close_pivot.iloc[:, -1:] > ma20
                        score = (bias.sum() * 100.0 / bias.count()).round().iloc[0]
                        industry_scores[industry_code] = score
                        total_score += score
                    except Exception as e:
                        log.error(f"行业代码: {industry_code}, 错误: {e}")
            if industry_scores:
                total_score = int(total_score / len(industry_scores))
            return industry_scores, total_score

        def print_stock_info(stocks, industry_dict, industry_code_dict, holdings, prices, pe_dict, pb_dict, roe_dict, roa_dict, volume_dict, volume_5d_dict, turnover_dict, turnover_5d_dict, pct_change_dict, pct_change_5d_dict, market_cap_dict, title, indent=""):
            if not LOG_ENABLED:
                return
            # 计算当前行业分
            industry_scores, total_score = calculate_industry_scores(stocks, industry_code_dict, context.previous_date)
            # 计算 5 日行业分平均值
            five_day_avg_industry_scores = {}
            for i in range(1, 6):
                end_date = context.previous_date - datetime.timedelta(days=i)
                daily_industry_scores, _ = calculate_industry_scores(stocks, industry_code_dict, end_date)
                for industry_code, score in daily_industry_scores.items():
                    if industry_code not in five_day_avg_industry_scores:
                        five_day_avg_industry_scores[industry_code] = []
                    five_day_avg_industry_scores[industry_code].append(score)
            for industry_code in five_day_avg_industry_scores:
                five_day_avg_industry_scores[industry_code] = sum(five_day_avg_industry_scores[industry_code]) / len(five_day_avg_industry_scores[industry_code])

            # 获取最高的 3 个行业排行
            sorted_industries = sorted(industry_scores.items(), key=lambda item: item[1], reverse=True)[:3]
            top_3_industries = []
            for code, score in sorted_industries:
                industry_name = next((industry_dict.get(stock, "未知行业") for stock, info in all_industry.items() if info.get("sw_l1", {}).get("industry_code") == code), "未知行业")
                top_3_industries.append(f"{industry_name}: {score}")
            top_3_str = ", ".join(top_3_industries)

            log.info(f"{indent}===================={title}====================总分{total_score} 最高3行业: {top_3_str}")
            header = ["#", "代码", "名称", "行业", "行业分", "行业差%", "PE", "PB", "ROA", "ROE", "换手率", "换手差%", "涨幅", "涨幅差%", "市值", "持仓"]  # 缩短表头
            data = []
            if stocks:
                for i, stock in enumerate(stocks, 1):
                    mark = "√" if stock in holdings else ""
                    stock_name = get_security_info(stock).display_name
                    industry = industry_dict[stock]
                    industry_code = industry_code_dict[stock]
                    score = industry_scores.get(industry_code, 0)
                    five_day_avg_score = five_day_avg_industry_scores.get(industry_code, 0)
                    industry_diff = score - five_day_avg_score
                    industry_diff_str = f"{round(industry_diff, 2):.2f}%"

                    pct_change = pct_change_dict.get(stock, 0)
                    pct_change_5d = pct_change_5d_dict.get(stock, 0)
                    pe = pe_dict.get(stock)
                    pb = pb_dict.get(stock)
                    roe = roe_dict.get(stock)
                    roa = roa_dict.get(stock)
                    volume = volume_dict.get(stock)
                    volume_5d = volume_5d_dict.get(stock)
                    turnover = turnover_dict.get(stock)
                    turnover_5d = turnover_5d_dict.get(stock)
                    market_cap = market_cap_dict.get(stock)

                    pe_str = f"{round(pe, 0) if pe and pe > 0 else '亏'}"
                    pb_str = f"{round(pb, 2):.2f}" if pb else 'N/A'
                    roe_str = f"{round(roe, 2):.2f}" if roe else 'N/A'
                    roa_str = f"{round(roa, 2):.2f}" if roa else 'N/A'
                    turnover_diff = ((turnover - turnover_5d) / turnover_5d * 100) if turnover_5d else 0
                    turnover_diff_str = f"{round(turnover_diff, 2):.2f}%"
                    turnover_str = f"{round(turnover * 100, 2):.2f}%" if turnover else 'N/A'
                    pct_change_str = f"{round(pct_change, 2):.2f}%"
                    pct_change_5d_str = f"{round(pct_change_5d, 2):.2f}%"
                    market_cap_str = f"{round(market_cap, 2):.2f}" if market_cap else 'N/A'
                    row = [i, stock, stock_name, industry, f"{score:.0f}", industry_diff_str, pe_str, pb_str, roa_str, roe_str, turnover_str, turnover_diff_str, pct_change_str, pct_change_5d_str, market_cap_str, mark]  # 移除排名列的空字符串
                    data.append(row)
            if data:
                table = tabulate(data, headers=header, tablefmt="simple", stralign="center", numalign="center")  # 使用 "simple" 格式，居中对齐
                log.info("\n" + table)
            else:
                log.info(f"{indent}{title}列表为空")

        for i, strategy_name in enumerate(all_strategies):
            if LOG_ENABLED:
                strategy = g.strategys[strategy_name]
                # 跳过不需要股票筛选的策略
                if isinstance(strategy, (qt_Strategy, hx_Strategy, xg_Strategy)):
                    continue
                stocks = strategy.select(context) if hasattr(strategy,'select') else strategy.filter(context)
                industry_dict = {stock: all_industry.get(stock, {}).get("sw_l1", {}).get("industry_name", "未知行业") for stock in stocks}
                industry_code_dict = {stock: all_industry.get(stock, {}).get("sw_l1", {}).get("industry_code", "") for stock in stocks}
                print_stock_info(stocks, industry_dict, industry_code_dict, all_holdings[strategy_name], all_prices, all_pe, all_pb, all_roe, all_roa, all_volume, all_volume_5d, all_turnover, all_turnover_5d, all_pct_change, all_pct_change_5d, all_market_cap, strategy_name, indent=" " * i)

    log_stock_info()


# 策略类基类---------------------------------------------------------------
class Strategy:
    def __init__(self, context, subportfolio_index, name):
        self.context = context  # 保存上下文对象
        self.subportfolio_index = subportfolio_index
        self.name = name
        self.stock_sum = 1
        self.hold_list = []
        self.limit_up_list = []
        self.portfolio_value = pd.DataFrame(columns=['date', 'total_value'])
        self.starting_cash = None
        self.sold_stock_record = {}
        self.exclude_days = 20  # 默认值，可在子策略中覆盖
        self.max_industry_stocks = 1  # 默认值，可在子策略中覆盖
        self.min_volume = 5000  # 默认最小交易量
        self.debug_mode = False  # 添加调试模式标志

    def filter_basic_stock(self, context, stock_list):
        current_data = get_current_data()
        stock_list = [
            stock for stock in stock_list
            if not (
                stock.startswith(('3', '68', '4', '8'))
                or current_data[stock].paused
                or current_data[stock].is_st
                or 'ST' in current_data[stock].name
                or '*' in current_data[stock].name
                or '退' in current_data[stock].name
                or current_data[stock].day_open == current_data[stock].high_limit
                or current_data[stock].day_open == current_data[stock].low_limit
                or current_data[stock].last_price >= current_data[stock].high_limit * 0.97
                or current_data[stock].last_price <= current_data[stock].low_limit * 1.04
                or (context.current_dt.date() - get_security_info(stock).start_date).days < 365
            ) and current_data[stock].last_price < 30
        ]
        current_date = context.current_dt.date()
        stock_list = filter_recently_sold(stock_list, current_date)#过滤20天卖出的
        #stock_list = filter_limit_up_stocks(context, stock_list)#过滤20天涨停过的
        stock_list = filter_over_20_percent_increase(context, stock_list)#过滤20天涨幅超过20%的
        return stock_list

    def getStockIndustry(self, stocks):
        return pd.Series({stock: info["sw_l1"]["industry_name"] for stock, info in data_manager.get_data(
            f"industry_{stocks}", get_industry, stocks
        ).items() if "sw_l1" in info})
        
    def record_daily_value(self, context):
        subportfolio = context.subportfolios[self.subportfolio_index]
        new_data = {'date': context.current_dt.date(), 'total_value': subportfolio.total_value}
        self.portfolio_value = self.portfolio_value.append(new_data, ignore_index=True)
        if self.starting_cash is None:
            self.starting_cash = subportfolio.total_value
        if self.starting_cash == 0:
            returns = 0
        else:
            returns = (subportfolio.total_value / self.starting_cash - 1) * 100
        rounded_returns = round(returns, 1)
        record(**{self.name +'': rounded_returns})

    def _prepare(self, context):
        self.hold_list = list(context.subportfolios[self.subportfolio_index].long_positions.keys())
        if self.hold_list:
            df = get_price(self.hold_list, end_date=context.previous_date, frequency="daily", fields=["close", "high_limit"],
                           count=1, panel=False, fill_paused=False)
            self.limit_up_list = list(df[df["close"] == df["high_limit"]].code)
        else:
            self.limit_up_list = []

    def _check(self, context):
        self._prepare(context)
        sold_stocks = []
        if self.limit_up_list:
            current_data = get_current_data()
            for stock in self.limit_up_list:
                if current_data[stock].last_price < current_data[stock].high_limit:
                    if self.close_position(stock):
                        sold_stocks.append(stock)
                        self.sold_stock_record[stock] = context.current_dt.date()
                        # 更新全局卖出记录
                        global_sold_stock_record[stock] = context.current_dt.date()
        return sold_stocks

    def _adjust(self, context, target):
        subportfolio = context.subportfolios[self.subportfolio_index]
        for security in self.hold_list:
            if security not in target and security not in self.limit_up_list:
                self.close_position(security)
        position_count = len(subportfolio.long_positions)
        if len(target) == 0 or self.stock_sum - position_count == 0:
            return
        buy_num = min(len(target), self.stock_sum - position_count)
        value = subportfolio.available_cash / buy_num
        for security in target:
            if security not in list(subportfolio.long_positions.keys()):
                if self.open_position(security, value):
                    if position_count == len(target):
                        break

    def order_target_value_(self, security, value):
        return order_target_value(security, value, pindex=self.subportfolio_index)

    def open_position(self, security, value):
        order = self.order_target_value_(security, value)
        return order is not None and order.filled > 0

    def close_position(self, security):
        """安全关闭仓位，检查可平仓数量"""
        # 使用保存的上下文
        subportfolio = self.context.subportfolios[self.subportfolio_index]
        position = subportfolio.long_positions.get(security)
        
        # 检查实际可平仓数量
        if not position or position.closeable_amount <= 0:
            if self.debug_mode:
                log.warning(f"跳过平仓 {security}: 无可平仓数量")
            return False
            
        # 执行平仓
        order = self.order_target_value_(security, 0)
        success = order is not None and order.filled == order.amount
        
        if self.debug_mode and success:
            log.info(f"成功平仓 {security} | 数量:{order.filled}")
        elif self.debug_mode and not success:
            log.warning(f"平仓失败 {security}")
            
        return success
        
    
    def select(self, context):
        stocks = self.select_stocks(context)
        if self.subportfolio_index in TIMING_STRATEGIES:
            stocks = global_timing_filter(context, stocks)
        industry_info = self.getStockIndustry(stocks) if hasattr(self, 'getStockIndustry') else None
        current_date = context.current_dt.date()
        # 使用拆分后的函数
        stocks = filter_recently_sold(stocks, current_date)
        selected_stocks = filter_stocks_by_industry(stocks, industry_info, self.max_industry_stocks)
        if selected_stocks:
            limit = self.stock_sum * 2
            selected_stocks = selected_stocks[:limit]
        return selected_stocks

    def prepare(self, context):
        self._prepare(context)

    def adjust(self, context):
        if self.subportfolio_index in EMPTY_POSITION_STRATEGIES and empty_position_in_jan_apr(context, self):
            return
        if check_stir_up_industry(context, self):
            return
        target = self.select(context)
        self._adjust(context, target[:self.stock_sum])
        self.record_daily_value(context)

    def check(self, context):
        return self._check(context)

    def buy_after_sell(self, context, sold_stocks):
        if self.subportfolio_index in EMPTY_POSITION_STRATEGIES and context.current_dt.month in [1, 4]:
            return
        target = self.select(context)
        self._adjust(context, target[:self.stock_sum])

    def adjust_portfolio(self, context, target_values):
        subportfolio = context.subportfolios[self.subportfolio_index]
        current_data = get_current_data()
        hold_list = list(subportfolio.long_positions.keys())

        # 清仓被调出的
        for stock in hold_list:
            if stock not in target_values:
                self.close_position(stock)

        # 先卖出
        for stock, target in target_values.items():
            value = subportfolio.long_positions[stock].value if stock in subportfolio.long_positions else 0
            minV = current_data[stock].last_price * 100
            if value - target > self.min_volume and minV < value - target:
                self.order_target_value_(stock, target)

        # 后买入
        for stock, target in target_values.items():
            value = subportfolio.long_positions[stock].value if stock in subportfolio.long_positions else 0
            minV = current_data[stock].last_price * 100
            if (
                target - value > self.min_volume
                and minV < subportfolio.available_cash
                and minV < target - value
            ):
                self.order_target_value_(stock, target)

        self.record_daily_value(context)



    
# 破净
class pj_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 1
        self.exclude_days = 20  # 多久不再买入卖出的股票
        self.max_industry_stocks = 1  # 每个行业最多选的股票数

    def select_stocks(self, context):
        month = context.previous_date.strftime("%Y-%m")
        all_stocks = data_manager.get_data(
            f"all_stocks_{month}",
            get_all_securities,
            "stock",
            date=context.previous_date
        ).index.tolist()
        stocks = self.filter_basic_stock(context, all_stocks)
        q = query(
            valuation.code, valuation.market_cap, valuation.pe_ratio, income.total_operating_revenue
        ).filter(
            valuation.pb_ratio < 1,
            cash_flow.subtotal_operate_cash_inflow > 1e6,
            indicator.adjusted_profit > 1e6,
            indicator.roa > 0.15,
            indicator.inc_net_profit_year_on_year > 0,
            valuation.code.in_(stocks)
        ).order_by(
            indicator.roa.desc()
        )
        stocks = get_fundamentals(q)["code"].tolist()
        return stocks


# 周期
class zq_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 4
        self.exclude_days = 20  # 多久不再买入卖出的股票
        self.max_industry_stocks = 1  # 每个行业最多选的股票数

    def select_stocks(self, context):
        yesterday = context.previous_date
        all_stocks = data_manager.get_data(
            f"all_stocks_{yesterday.strftime('%Y-%m')}",
            get_all_securities,
            "stock",
            date=yesterday
        ).index.tolist()
        stocks = self.filter_basic_stock(context, all_stocks)
        stocks = [stock for stock in stocks if (yesterday - get_security_info(stock).start_date) > datetime.timedelta(250)]
        stocks_df = get_fundamentals(
            query(valuation.code)
            .filter(
                valuation.code.in_(stocks),
                valuation.market_cap > 500,  # 总市值大于500亿
                valuation.pe_ratio < 20,  # 市盈率小于20
                indicator.roa > 0,  # ROA大于0
                indicator.gross_profit_margin > 30,  # 销售毛利率大于30%
            )
            .order_by(valuation.market_cap.desc())  # 按市值从大到小排序
        )
        return list(stocks_df.code)


# 红利---------------------------------------------------------------
class hl_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 4
        self.m_days = 24
        self.days = 250
        self.exclude_days = 20  # 多久不再买入卖出的股票
        self.max_industry_stocks = 1  # 每个行业最多选的股票数

    def select_stocks(self, context):
        month = context.previous_date.strftime("%Y-%m")
        all_stocks = data_manager.get_data(
            f"all_stocks_{month}",
            get_all_securities,
            "stock",
            date=context.previous_date
        ).index.tolist()
        stocks = self.filter_basic_stock(context, all_stocks)
        stocks = [stock for stock in stocks if (context.previous_date - get_security_info(stock).start_date) > datetime.timedelta(self.days)]
        # 调用公共函数计算股息率并筛选股票
        stocks = calculate_dividend_ratio(context, stocks, False, 0, 0.10)
        df = get_fundamentals(query(
            valuation.code,
            valuation.circulating_market_cap
        ).filter(
            valuation.code.in_(stocks),
            valuation.pe_ratio.between(0, 25),
            indicator.inc_return > 3,
            indicator.inc_total_revenue_year_on_year > 5,
            indicator.inc_net_profit_year_on_year > 11,
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year > 0.08,
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year < 1.9
        ))
        stocks = list(df.code)
        return stocks



# 微盘---------------------------------------------------------------
class wp_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 6
        self.max_industry_stocks = 1
        self.exclude_days = 20  # 缓冲时间

    def select_stocks(self, context):
        month = context.current_dt.strftime("%Y-%m")
        stocks = data_manager.get_data(
            f"index_stocks_399101_{month}",
            get_index_stocks,
            "399101.XSHE",
            context.current_dt
        )
        stocks = self.filter_basic_stock(context, stocks)
        q = query(
            valuation.code
        ).filter(
            valuation.code.in_(stocks),
        ).order_by(
            valuation.market_cap.asc()  # 根据市值从小到大排序
        )
        stocks = get_fundamentals(q)["code"].tolist()
        return stocks



# 成长---------------------------------------------------------------
class cz_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 6
        self.max_industry_stocks = 1
        self.limit_days = 20
        self.exclude_days = 20  # 多久不再买入卖出的股票
        self.history_hold_list = []
        self.not_buy_again_list = []

    # 选股模块
    def get_single_factor_list(self, context, stock_list, jqfactor, sort, p1, p2):
        yesterday = context.previous_date
        s_score = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].dropna().sort_values(ascending=sort)
        return s_score.index[int(p1 * len(stock_list)):int(p2 * len(stock_list))].tolist()

    def sorted_by_circulating_market_cap(self, stock_list, n_limit_top=None):
        q = query(
            valuation.code,
        ).filter(
            valuation.code.in_(stock_list),
            indicator.eps > 0
        ).order_by(
            valuation.circulating_market_cap.asc()
        )
        if n_limit_top is not None:
            q = q.limit(n_limit_top)
        return get_fundamentals(q)['code'].tolist()

    def get_stock_list(self, context):
        initial_list = self.filter_basic_stock(context, get_all_securities(date=context.previous_date).index.tolist())
        # 1. SG 营业收入增长率, 从大到小的前10%；再按流通市值升序
        sg_list = self.get_single_factor_list(context, initial_list, 'sales_growth', False, 0, 0.1)
        sg_list = self.sorted_by_circulating_market_cap(sg_list)
        
        # 2. MS 复合增长率, 从大到小的前10%；按流通市值升序
        factor_list = [
            'operating_revenue_growth_rate',  # 营业收入增长率
            'total_profit_growth_rate',  # 利润总额增长率
            'net_profit_growth_rate',  # 净利润增长率
            'earnings_growth',  # 5年盈利增长率
        ]
        factor_values = get_factor_values(initial_list, factor_list, end_date=context.previous_date, count=1)
        df = pd.DataFrame(index=initial_list)
        for factor in factor_list:
            df[factor] = factor_values[factor].iloc[0]

        df['total_score'] = 0.1 * df['operating_revenue_growth_rate'] + 0.35 * df['total_profit_growth_rate'] + 0.15 * df[
            'net_profit_growth_rate'] + 0.4 * df['earnings_growth']
        ms_list = df.sort_values(by=['total_score'], ascending=False).index[:int(0.1 * len(df))].tolist()
        ms_list = self.sorted_by_circulating_market_cap(ms_list)

        # 3: PEG，升序前20%\TURNOVER_VOLATILITY，升序前50%；再按流通市值升序
        peg_list = self.get_single_factor_list(context, initial_list, 'PEG', True, 0, 0.2)
        peg_list = self.get_single_factor_list(context, peg_list, 'turnover_volatility', True, 0, 0.5)
        peg_list = self.sorted_by_circulating_market_cap(peg_list)

        # 1、2、3的并集；再按流通市值升序
        union_list = list(set(sg_list).union(set(ms_list)).union(set(peg_list)))
        union_list = self.sorted_by_circulating_market_cap(union_list)
        return union_list

    def get_recent_limit_up_stock(self, context, stock_list, limit_days):
        end_date = context.previous_date
        start_date = end_date - datetime.timedelta(days=limit_days)
        limit_up_list = []
        for stock in stock_list:
            df = get_price(stock, start_date=start_date, end_date=end_date, frequency='daily', fields=['close', 'high_limit', 'paused'])
            limit_up = df[(df['close'] == df['high_limit']) & (df['paused'] == 0)]
            if not limit_up.empty:
                limit_up_list.append(stock)
        return limit_up_list

    def select_stocks(self, context):
        # 选股
        target_list = self.get_stock_list(context)
        recent_limit_up_list = self.get_recent_limit_up_stock(context, target_list, self.limit_days)
        black_list = list(set(self.not_buy_again_list).intersection(set(recent_limit_up_list)))
        target_list = [stock for stock in target_list if stock not in black_list]

        # 最近20天的MA20的斜率，去掉过小的
        h_ma = history(20 + 20, '1d', 'close', target_list).rolling(window=20).mean().iloc[20:]
        X = np.arange(len(h_ma))
        tmp_target_list = []
        for stock in target_list:
            try:
                MA_N_Arr = h_ma[stock].values
                MA_N_Arr = MA_N_Arr - MA_N_Arr[0]  # 截距归零
                slope = round(sm.OLS(MA_N_Arr, X).fit().params[0] * 100, 1)
                remove_it = False
                if slope < - 2:
                    if stock not in self.hold_list:
                        remove_it = True
                if not remove_it:
                    tmp_target_list.append(stock)
            except Exception as e:
                print(f"计算 {stock} 的MA20斜率时出错: {e}")
        target_list = tmp_target_list
        return target_list

# 大妈---------------------------------------------------------------
class dm_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 6
        self.max_industry_stocks = 1
        self.exclude_days = 20  # 多久不再买入卖出的股票

    def select_stocks(self, context):
        month = context.current_dt.strftime("%Y-%m")
        all_stocks = data_manager.get_data(
            f"all_stocks_{month}",
            get_all_securities,
            "stock",
            date=context.current_dt
        ).index.tolist()
        stocks = self.filter_basic_stock(context, all_stocks)
        # 调用公共函数计算股息率并筛选股票
        stocks = calculate_dividend_ratio(context, stocks, False, 0, 0.25)
        stocks = self.get_peg(context, stocks)
        # 价格限制
        current_data = get_current_data()
        stocks = [stock for stock in stocks if current_data[stock].last_price < 9]
        return stocks

    def get_peg(self, context, stocks):
        q = query(
            valuation.code,
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year,
            indicator.roe / valuation.pb_ratio,
            indicator.roe
        ).filter(
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year > -3,
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year < 3,
            valuation.code.in_(stocks)
        )
        df_fundamentals = get_fundamentals(q, date=None)
        stocks = list(df_fundamentals.code)
        df = get_fundamentals(query(valuation.code).filter(valuation.code.in_(stocks)).order_by(valuation.market_cap.asc()))
        return list(df.code)


# 全天---------------------------------------------------------------
class qt_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.min_volume = 2000
        self.etf_pool = [
            "511010.XSHG",  # 国债ETF
            "518880.XSHG",  # 黄金ETF
            "513100.XSHG",  # 纳指ETF
            "512820.XSHG",  # 银行ETF
            "159980.XSHE",  # 有色金属ETF
            "162411.XSHE",  # 华宝油气LOF
            "159985.XSHE",  # 豆粕ETF
        ]
        self.rates = [0.4, 0.15, 0.15, 0.15, 0.05, 0.05, 0.05]

    def adjust(self, context):
        subportfolio = context.subportfolios[self.subportfolio_index]
        total_value = subportfolio.total_value
        target_values = {etf: total_value * rate for etf, rate in zip(self.etf_pool, self.rates)}
        self.adjust_portfolio(context, target_values)


# 核心
class hx_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.etf_pool = ['518880.XSHG', '513100.XSHG', '159915.XSHE', '510180.XSHG']
        self.m_days = 25
        
    def initialize_refresh(self):
        """初始化持仓刷新设置"""
        # 首次刷新持仓
        self.ctx.portfolio.refresh_positions()
        # 设置每日刷新
        self.ctx.run_daily(self.refresh_positions, time='before_open')
        
    def refresh_positions(self, context):
        """每日开盘前刷新持仓数据"""
        context.logger.info("刷新持仓数据...")
        context.portfolio.refresh_positions()
        
    def adjust_position(self, context, target_values):
        """仓位调整函数（包含保护逻辑）"""
        for security, target_value in target_values.items():
            # 获取当前价格
            current_price = context.current_prices.get(security)
            if current_price is None:
                context.logger.warning(f"无法获取{security}的当前价格，跳过")
                continue
                
            # 开仓保护
            if target_value > 0:
                # 计算目标股数
                target_shares = int(target_value / current_price)
                
                # 跳过不足100股的委托
                if target_shares < 100:
                    context.logger.info(f"跳过{security}：目标价值{target_value}元不足100股")
                    continue
                
                # 执行开仓
                order_target_value(security, target_value)
            
            # 平仓保护
            elif target_value == 0:
                position = context.portfolio.positions.get(security)
                
                # 检查可平仓数量
                if position and position.closeable_amount > 0:
                    # 执行平仓
                    order_target_value(security, 0)
                    context.logger.info(f"平仓{security}：数量{position.closeable_amount}")
                else:
                    # 记录详细原因
                    if not position:
                        context.logger.info(f"跳过{security}：无持仓")
                    else:
                        context.logger.info(f"跳过{security}：可平仓数量={position.closeable_amount}")
                        
   
    def MOM(self, context, etf):
        y = np.log(attribute_history(etf, self.m_days, '1d', ['close'])['close'].values)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope = np.polyfit(x, y, 1, w=weights)[0]
        residuals = y - (slope * x + np.polyfit(x, y, 1, w=weights)[1])
        
        annualized_returns = np.exp(slope*250) - 1
        r_squared = 1 - (np.sum(weights*residuals**2) / 
                        np.sum(weights*(y - np.mean(y))**2))
        return annualized_returns * r_squared

    def get_rank(self, context):
        scores = {etf: self.MOM(context, etf) for etf in self.etf_pool}
        df = pd.Series(scores).to_frame('score')
        return df.query('0 < score <= 5').sort_values('score', ascending=False).index.tolist()

    def adjust(self, context):
        sub = context.subportfolios[self.subportfolio_index]
        target_list = self.get_rank(context)[:1]
        
        # 卖出逻辑
        for etf in set(sub.long_positions) - set(target_list):
            self.close_position(etf)
            print(f'卖出{etf}')
        
        # 买入逻辑
        need_buy = set(target_list) - set(sub.long_positions)
        if need_buy:
            cash_per = sub.available_cash / len(need_buy)
            for etf in need_buy:
                self.open_position(etf, cash_per) and print(f'买入{etf}')
                
        self.record_daily_value(context)
        
    
        
#因子
class yz_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 5
        self.max_industry_stocks = 1
        self.exclude_days = 20  # 多久不再买入卖出的股票
        self.factor_list = [
            (#ARBR-SGAI-NPtTORttm-RPps
                [
                    'ARBR', #情绪类因子 ARBR
                    'SGAI', #质量类因子 销售管理费用指数
                    'net_profit_to_total_operate_revenue_ttm', #质量类因子 净利润与营业总收入之比
                    'retained_profit_per_share' #每股指标因子 每股未分配利润
                ],
                [-3.894481386287797e-19, 6.051549381361553e-05, -0.00013489470173496827,
                 -0.0006228721291235472]
            ),
            (#P1Y-TPtCR-VOL120
                [
                    'Price1Y', #动量类因子 当前股价除以过去一年股价均值再减1
                    'total_profit_to_cost_ratio', #质量类因子 成本费用利润率
                    'VOL120' #情绪类因子 120日平均换手率
                ],
                [-0.007686604605324844, -0.001064082235156668, -0.0006372186835828526]
            ),
            (#PNF-TPtCR-ITR
                [
                    'price_no_fq', #技术指标因子 不复权价格因子
                    'total_profit_to_cost_ratio', #质量类因子 成本费用利润率
                    'inventory_turnover_rate' #质量类因子 存货周转率
                ],
                [-0.00022239096483198066, -0.0003400190412564607, -1.2360751761544718e-08]
            ),
            (#DtA-OCtORR-DAVOL20-PNF-SG
                [
                    'debt_to_assets', #风格因子 资产负债率
                    'operating_cost_to_operating_revenue_ratio', #质量类因子 销售成本率
                    'DAVOL20', #情绪类因子 20日平均换手率与120日平均换手率之比
                    'price_no_fq', #技术指标因子 不复权价格因子
                    'sales_growth' #风格因子 5年营业收入增长率
                ],
                [-0.0013461722141220884, 0.001285717224773847, -0.003021350121015241,
                 -0.00023334854089909846, 0.0002343967416749908]
            ),
            (#TVSTD6-CFpsttm-SR120-NONPttm
                [
                    'TVSTD6', #情绪类因子 6日成交金额的标准差
                    'cashflow_per_share_ttm', #每股指标因子 每股现金流量净额
                    'sharpe_ratio_120', #风险类因子 120日夏普率
                    'non_operating_net_profit_ttm' #基础科目及衍生类因子 营业外收支净额TTM
                ],
                [-6.694922635779981e-11, -0.00016142377647805555, -0.0005529870175398643,
                 9.167393894186556e-12]
            )
        ]

    def select_stocks(self, context):
        month = context.previous_date.strftime("%Y-%m")
        all_stocks = data_manager.get_data(
            f"all_stocks_{month}",
            get_all_securities,
            "stock",
            date=context.previous_date
        ).index.tolist()
        stocks = self.filter_basic_stock(context, all_stocks)

        final_stocks = []
        for factor_list, coef_list in self.factor_list:
            factor_values = get_factor_values(stocks, factor_list, end_date=context.previous_date, count=1)
            df = pd.DataFrame(index=stocks, columns=factor_values.keys())
            for i in range(len(factor_list)):
                df[factor_list[i]] = list(factor_values[factor_list[i]].T.iloc[:, 0])
            df = df.dropna()
            df['total_score'] = 0
            for i in range(len(factor_list)):
                df['total_score'] += coef_list[i] * df[factor_list[i]]
            df = df.sort_values(by=['total_score'], ascending=False)
            sub_stocks = list(df.index)[:int(0.1 * len(list(df.index)))]
            final_stocks.extend(sub_stocks)

        # 去重
        final_stocks = list(set(final_stocks))

        # 按市值升序排序，这里模仿小市值策略关注小市值股票
        q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(final_stocks)).order_by(valuation.market_cap.asc())
        stocks = get_fundamentals(q)["code"].tolist()

        return stocks

 
        
# 测试
class cs_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 6
        self.max_industry_stocks = 1
        self.exclude_days = 20


    def select_stocks(self, context):
        month = context.current_dt.strftime("%Y-%m")
        stocks = data_manager.get_data(
            f"index_stocks_399101_{month}",
            get_index_stocks,
            "399101.XSHE",
            context.current_dt
        )
        stocks = self.filter_basic_stock(context, stocks)
        q = query(
            valuation.code
        ).filter(
            valuation.code.in_(stocks),
        ).order_by(
            valuation.market_cap.asc()  # 根据市值从小到大排序
        )
        stocks = get_fundamentals(q)["code"].tolist()
        return stocks

        
# 相关
class xg_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = None

    def filter(self, context):
        yesterday = context.previous_date
        df = get_all_securities(["etf"], yesterday)
        # 筛选成立时间超过一定天数的基金
        df = df[df["start_date"] < (yesterday - datetime.timedelta(days=1850))]

        df1 = pd.DataFrame()
        df2 = pd.DataFrame(columns=["sharpe_ratio"], dtype=float)
        for code in df.index:
            data = get_price(code, end_date=yesterday, count=1250)
            if data["money"].mean() > 2e7 and data["close"].iloc[-1] < 90:
                returns = data["close"].pct_change().dropna()
                sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252)  # 年化夏普比率
                if sharpe_ratio > 0.6:
                    df2.loc[code, "sharpe_ratio"] = sharpe_ratio
                    df1[code] = data["close"]

        # 步骤 1：计算每日收益率
        returns_df = df1.pct_change().dropna()

        # 步骤 2：计算相关性矩阵
        correlation_matrix = returns_df.corr()

        # 步骤 3：聚类分析
        num_clusters = min(len(df2), 50)
        kmeans = KMeans(n_clusters=num_clusters, random_state=42)
        clusters = kmeans.fit_predict(returns_df.T)

        # 将聚类结果添加到DataFrame中
        etf_codes = returns_df.columns
        cluster_df = pd.DataFrame({"code": etf_codes, "cluster": clusters})
        cluster_df = cluster_df.set_index("code")
        cluster_df = cluster_df.join(df2, how="left")

        # 步骤 4：选择每个类别中成交量最大的ETF
        selected_etfs = cluster_df.groupby("cluster")["sharpe_ratio"].idxmax().tolist()
        selected_etfs_df = returns_df[selected_etfs]

        # 步骤 5：筛选低相关性ETF
        def filter_low_correlation(etfs, correlation_matrix, threshold):
            selected = []
            for etf in etfs.columns:
                if all(correlation_matrix.loc[etf, selected].abs() < threshold):
                    selected.append(etf)
            return selected

        final_etfs = filter_low_correlation(
            selected_etfs_df, correlation_matrix, threshold=0.4
        )
        return final_etfs

    def select(self, context):
        return self.filter(context)

    def prepare(self, context):
        self._prepare(context)

    def adjust(self, context):
        if self.subportfolio_index in EMPTY_POSITION_STRATEGIES and empty_position_in_jan_apr(context, self):
            return
        targets = self.select(context)
        subportfolio = context.subportfolios[self.subportfolio_index]
        target_values = {target: 1 / len(targets) * subportfolio.total_value for target in targets}
        self.adjust_portfolio(context, target_values)

    def check(self, context):
        return self._check(context)

    def buy_after_sell(self, context, sold_stocks):
        if self.subportfolio_index in EMPTY_POSITION_STRATEGIES and context.current_dt.month in [1, 4]:
            return
        self.adjust(context)
        
# 弱转强策略类
class rzq_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_num = 4
        self.today_list = []  # 当日候选股
        self.dieting = []  # 跌停股列表
        self.buy_dates = {}  # 买入日期记录
        self.sold_today = set()  # 当日已卖出
        self.processing_sell = set()  # 处理中的卖出
        self.debug_mode = False
        self.data_cache = {}
        self.last_update_date = None
        self.actual_positions = {}  # 自维护持仓
        self.last_positions_update = None

    def prepare(self, context):
        """9:25准备候选股"""
        # 清除每日记录
        self.dieting = []
        self.sold_today = set()
        self.processing_sell = set()
        self.today_list = []
        
        # 缓存管理
        current_date = context.current_dt.date()
        if current_date != self.last_update_date:
            self.data_cache = {}
            self.last_update_date = current_date
        
        # 获取ST股列表
        stk_list = self.get_st(context)
        if not stk_list:
            return
            
        # 国九条筛选
        if self.today_is_between(context):
            stk_list = self.GJT_filter_stocks(stk_list)
        
        # 技术指标筛选
        stk_list = self.filter_stocks(context, stk_list)
        if not stk_list:
            return
            
        # 融资券筛选
        stk_list = self.rzq_list(context, stk_list)
        if not stk_list:
            return
            
        # 低开筛选
        cache_key = f"open_close_{context.previous_date}"
        if cache_key not in self.data_cache:
            df_history = get_price(
                stk_list, 
                end_date=context.previous_date, 
                frequency='daily', 
                fields=['close'], 
                count=1, 
                panel=False
            ).set_index('code')
            self.data_cache[cache_key] = df_history
        
        df_history = self.data_cache[cache_key]
        current_data = get_current_data()
        df = df_history.copy()
        df['open_now'] = [current_data[s].day_open for s in stk_list if s in df.index]
        
        # 筛选低开股票 (1%-5%低开范围)
        df = df[(df['open_now']/df['close'] < 1.05) & 
                (df['open_now']/df['close'] > 0.99)]
        
        if df.empty:
            return
            
        # 换手率筛选
        cache_key = f"valuation_{context.previous_date}"
        if cache_key not in self.data_cache:
            df_valuation = get_valuation(
                df.index.tolist(),
                start_date=context.previous_date, 
                end_date=context.previous_date, 
                fields=['turnover_ratio', 'market_cap', 'circulating_market_cap']
            )
            self.data_cache[cache_key] = df_valuation.set_index('code')
        
        df_valuation = self.data_cache[cache_key]
        df = df.join(df_valuation[['turnover_ratio']], how='inner')
        df = df.sort_values(by='turnover_ratio', ascending=False)
        self.today_list = df.index.tolist()
        self.update_positions(context)
        if self.debug_mode:
            log.info(f"候选股票数: {len(self.today_list)}")

    def adjust(self, context):
        """9:30执行买入"""
        if not self.is_trading_time(context):
            return
            
        self.update_positions(context)
        target = self.today_list
        
        if not target:
            return
            
        # 计算可买数量
        hold_count = len(self.actual_positions)
        num = max(0, min(self.stock_num - hold_count, len(target)))
        
        if num <= 0:
            return
            
        # 过滤不可交易股票
        current_data = get_current_data()
        valid_target = []
        for stock in target[:num*2]:
            try:
                if (stock not in self.actual_positions and
                    stock not in self.sold_today and
                    stock not in self.processing_sell and
                    not current_data[stock].paused and
                    current_data[stock].low_limit < current_data[stock].last_price < current_data[stock].high_limit):
                    valid_target.append(stock)
                    if len(valid_target) >= num:
                        break
            except Exception as e:
                if self.debug_mode:
                    log.warning(f"股票{stock}状态检查失败: {e}")
    
        if not valid_target:
            return
            
        # 资金分配
        subportfolio = context.subportfolios[self.subportfolio_index]
        cash_per_stock = subportfolio.available_cash / num
        
        # 执行买入
        for stock in valid_target[:num]:
            try:
                current_price = current_data[stock].last_price
                max_amount = int(cash_per_stock / current_price / 100) * 100
                if max_amount <= 0:
                    continue
                    
                # 科创板特殊处理
                if stock.startswith('688'):
                    high_limit = current_data[stock].high_limit
                    protect_price = min(current_price * 1.02, high_limit)
                    order_id = order(stock, max_amount, style=LimitOrderStyle(protect_price), pindex=self.subportfolio_index)
                else:
                    order_id = order(stock, max_amount, pindex=self.subportfolio_index)
                
                if order_id:
                    self.actual_positions[stock] = True
                    self.buy_dates[stock] = context.current_dt.date()
                    if self.debug_mode:
                        log.info(f"买入 {stock} | 数量:{max_amount} 价格:{current_price:.2f}")
            except Exception as e:
                log.error(f"买入失败 {stock}: {e}")

    def check(self, context):
        """13:00/14:00执行卖出"""
        if not self.is_trading_time(context):
            return
            
        self.update_positions(context)
        hold_list = list(self.actual_positions.keys())
        
        if not hold_list:
            return
            
        # 批量获取历史数据
        cache_key = f"history_{context.previous_date}"
        if cache_key not in self.data_cache:
            df_history = get_price(
                hold_list, 
                end_date=context.previous_date, 
                frequency='daily', 
                fields=['close', 'high_limit'], 
                count=1, 
                panel=False
            ).set_index('code')
            self.data_cache[cache_key] = df_history
        
        df_history = self.data_cache[cache_key]
        current_data = get_current_data()
        today = context.current_dt.date()
        
        to_sell = []
        for stock in hold_list:
            try:
                if stock in self.sold_today or stock in self.processing_sell:
                    continue
                    
                # 检查T+1限制
                buy_date = self.buy_dates.get(stock)
                if buy_date == today:
                    continue
                    
                
                # 获取持仓和价格
                pos = context.portfolio.positions[stock]
                if not pos or pos.total_amount <= 0:
                    continue
                
                # 检查实际可平仓数量
                pos = self.safe_get_position(context, stock)
                if not pos or pos.closeable_amount <= 0:
                    continue
                
                last_price = current_data[stock].last_price
                high_limit = current_data[stock].high_limit
                low_limit = current_data[stock].low_limit
                
                if stock not in df_history.index:
                    continue
                    
                hist_data = df_history.loc[stock]
                close_price = hist_data['close']
                history_high_limit = hist_data['high_limit']
                
                # 计算收益率
                ret = (last_price / pos.avg_cost - 1) * 100
                
                # 卖出条件
                cond1 = last_price != high_limit  # 未涨停
                cond2_1 = ret < -3  # 亏损超过3%
                cond2_2 = ret > 0  # 有盈利
                cond2_3 = close_price == history_high_limit  # 昨日涨停
                
                should_sell = cond1 and (cond2_1 or cond2_2 or cond2_3)
                
                if should_sell and last_price > low_limit:  # 未跌停
                    to_sell.append(stock)
            except Exception as e:
                log.error(f"卖出评估异常 {stock}: {e}")
    
        # 执行卖出
        for stock in to_sell:
            try:
                self.processing_sell.add(stock)
                pos = context.portfolio.positions[stock]
                
                # 科创板特殊处理
                if stock.startswith('688'):
                    low_limit = current_data[stock].low_limit
                    protect_price = max(current_data[stock].last_price * 0.98, low_limit)
                    order_target(stock, 0, style=LimitOrderStyle(protect_price), pindex=self.subportfolio_index)
                else:
                    order_target(stock, 0, pindex=self.subportfolio_index)
                
                # 更新状态
                self.sold_today.add(stock)
                if stock in self.actual_positions:
                    del self.actual_positions[stock]
                self.processing_sell.remove(stock)
                
                # 记录日志
                current_price = get_current_data()[stock].last_price
                if self.debug_mode:
                    log.info(f"卖出 {stock} | 数量:{pos.total_amount} 成本:{pos.avg_cost:.2f} 现价:{current_price:.2f} 盈亏:{(current_price/pos.avg_cost-1)*100:.2f}%")
            except Exception as e:
                log.error(f"卖出执行异常 {stock}: {e}")
                if stock in self.processing_sell:
                    self.processing_sell.remove(stock)
        
        self.update_positions(context)

    def dieting_check(self, context):
        """全天监控跌停股"""
        if not self.is_trading_time(context):
            return
            
        self.update_positions(context)
        current_data = get_current_data()
        
        # 检测跌停股票
        for s in list(self.actual_positions.keys()):
            if s in self.sold_today or s in self.processing_sell:
                continue
                
            # 检查实际可平仓数量
            pos = self.safe_get_position(context, s)
            if not pos:
                if s in self.actual_positions:
                    del self.actual_positions[s]
                continue
            
            
            if s not in self.dieting:
                try:
                    dtj = current_data[s].low_limit
                    zxj = current_data[s].last_price
                    # 这里是添加跌停股票的位置
                    if zxj == dtj and s not in self.dieting:  # 添加安全检查
                        self.dieting.append(s)  # 使用列表所以用 append 而不是 add
                        if self.debug_mode:
                            log.info(f"股票 {s} 跌停，加入监控列表")
                    
                except Exception as e:
                    log.error(f"检查跌停 {s} 时出错: {e}")
        
        # 检查跌停打开的股票
        if self.dieting:
            for s in self.dieting[:]:
                try:
                    # 检查是否已卖出或正在处理
                    if s in self.sold_today or s in self.processing_sell:
                        self.safe_remove_from_dieting(s)
                        continue
                    
                    pos = self.safe_get_position(context, s)
                    if not pos:
                        self.dieting.remove(s)
                        continue
                        
                    dtj = current_data[s].low_limit
                    zxj = current_data[s].last_price
                    
                    # 跌停打开时卖出
                    if zxj > dtj:
                        # 检查T+1规则
                        today = context.current_dt.date()
                        if s in self.buy_dates and self.buy_dates[s] == today:
                            continue
                        
                        # 获取实际可平仓数量
                        pos = self.safe_get_position(context, s)
                        if not pos or pos.closeable_amount <= 0:  # 添加可平仓数量检查
                            # 安全移除
                            if s in self.dieting:
                                self.dieting.remove(s)
                            continue
                            
                        
                        self.processing_sell.add(s)
                        # 科创板特殊处理
                        if s.startswith('688'):
                            low_limit = current_data[s].low_limit
                            protect_price = max(zxj * 0.98, low_limit)
                            order_target(s, 0, style=LimitOrderStyle(protect_price), pindex=self.subportfolio_index)
                        else:
                            order_target(s, 0, pindex=self.subportfolio_index)
                            
                        self.sold_today.add(s)
                        if s in self.actual_positions:
                            del self.actual_positions[s]
                        self.processing_sell.remove(s)
                      
                        # 卖出后安全移除 - 插入在这里
                        self.safe_remove_from_dieting(s)
                        
                        if self.debug_mode:
                            log.info(f"跌停打开卖出完成:{s}")
                except Exception as e:
                    log.error(f"处理跌停股票 {s} 时出错: {e}")
                    if s in self.processing_sell:
                        self.processing_sell.remove(s)
                    # 异常时安全移除
                    self.safe_remove_from_dieting(s)
                   
    def safe_remove_from_dieting(self, s):
        """安全从跌停列表中移除股票"""
        try:
            if s in self.dieting:
                self.dieting.remove(s)
            if s in self.processing_sell:
                self.processing_sell.remove(s)
        except Exception as e:
            if self.debug_mode:
                log.warning(f"安全移除 {s} 失败: {e}")
                
    def update_positions(self, context):
        """更新持仓状态"""
        current_time = context.current_dt
        if self.last_positions_update and (current_time - self.last_positions_update).seconds < 60:
            return
            
        self.last_positions_update = current_time
        new_positions = {}
        
        # 获取实际持仓
        subportfolio = context.subportfolios[self.subportfolio_index]
        for stock, pos in subportfolio.long_positions.items():
            try:
                if pos.total_amount > 0:
                    new_positions[stock] = pos
                    if stock not in self.buy_dates:
                        self.buy_dates[stock] = pos.init_time.date()
            except Exception as e:
                if self.debug_mode:
                    log.warning(f"持仓处理异常 {stock}: {e}")
        
        # 更新实际持仓
        self.actual_positions = new_positions
        
        # 清理已卖出的持仓记录
        for stock in list(self.buy_dates.keys()):
            if stock not in new_positions:
                del self.buy_dates[stock]
                
    def safe_get_position(self, context, stock):
        """安全获取持仓信息"""
        try:
            subportfolio = context.subportfolios[self.subportfolio_index]
            if stock in subportfolio.long_positions:
                pos = subportfolio.long_positions[stock]
                if pos.total_amount > 0:
                    return pos
            elif stock in self.actual_positions:
                del self.actual_positions[stock]
        except Exception as e:
            log.error(f"持仓获取异常 {stock}: {e}")
        return None

    def is_trading_time(self, context):
        """判断交易时间"""
        now = context.current_dt
        hour, minute = now.hour, now.minute
        
        # 上午交易时间
        if (hour == 9 and minute >= 30) or (10 <= hour < 11) or (hour == 11 and minute <= 30):
            return True
            
        # 下午交易时间
        if (13 <= hour < 15) or (hour == 14 and minute <= 55):
            return True
            
        return False
        
    # ========== 弱转强辅助函数 ==========
    def today_is_between(self, context):
        today = context.current_dt.strftime('%m-%d')
        if ('01-15' <= today) and (today <= '01-31'):
            return True
        elif ('04-15' <= today) and (today <= '04-30'):
            return True     
        elif ('12-15' <= today) and (today <= '12-31'):
            return True 
        else:
            return False
            
    def get_st(self, context):
        yesterday = context.previous_date
        stockList = get_all_securities(types='stock', date=yesterday).index
        st_data = get_extras('is_st', stockList, count=1, end_date=yesterday)
        st_data = st_data.T
        st_data.columns = ['is_st']
        st_data = st_data[st_data['is_st'] == True]
        return st_data.index.tolist()    
            
    def GJT_filter_stocks(self, stocks):
        """国九条筛选 (示例实现)"""
        q = query(
            valuation.code,
            income.np_parent_company_owners,
            income.net_profit,
            income.operating_revenue,
            indicator.roe,
            indicator.roa
        ).filter(
            valuation.code.in_(stocks),
            income.np_parent_company_owners > 0,
            income.net_profit > 0,
            income.operating_revenue > 1e8,
            indicator.roe > 0,
            indicator.roa > 0
        )
        df = get_fundamentals(q)
        return df['code'].tolist() if 'code' in df.columns else []
        
    def filter_stocks(self, context, stocks):
        """技术指标筛选"""
        if not stocks:
            return []
        
        # 获取历史数据 (11天)
        df = get_price(
            stocks,
            count=11,
            frequency='1d',
            fields=['close', 'low', 'volume'],
            end_date=context.previous_date,
            panel=False
        )
        
        if df.empty:
            return []
        
        # 向量化计算
        df['prev_low'] = df.groupby('code')['low'].shift(1)
        df['prev_volume'] = df.groupby('code')['volume'].shift(1)
        df['ma10'] = df.groupby('code')['close'].transform(lambda x: x.rolling(10).mean())
        
        # 筛选最新一天
        last_day = df.groupby('code').last().reset_index()
        
        # 应用条件
        cond = (
            (last_day['close'] > last_day['prev_low']) &
            (last_day['close'] > last_day['ma10']) &
            (last_day['volume'] > last_day['prev_volume']) &
            (last_day['volume'] < 10 * last_day['prev_volume']) &
            (last_day['close'] > 1) &
            last_day['prev_low'].notna() &
            last_day['prev_volume'].notna()
        )
        
        return last_day[cond]['code'].tolist()
        
    def rzq_list(self, context, initial_list): 
        """融资券列表筛选"""
        if not initial_list:
            return []
        
        # 日期计算
        date = context.previous_date
        date_1 = date - datetime.timedelta(days=1)  # 前日
        date_2 = date - datetime.timedelta(days=2)  # 大前日
       
        # 昨日不涨停
        h1_list = self.get_ever_hl_stock(initial_list, date)
        # 前日涨停过滤
        elements_to_remove = self.get_hl_stock(initial_list, date_1)
        zb_list = [stock for stock in h1_list if stock in elements_to_remove]
        return zb_list
        
    def get_ever_hl_stock(self, initial_list, date):
        """筛选不涨停"""
        df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','high','high_limit'], count=1, panel=False)
        df = df.dropna()
        cd2 = df['close'] != df['high_limit']
        return list(df[cd2].code)
        
    def get_hl_stock(self, initial_list, date):
        """筛选出涨停的股票"""
        df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','low','high_limit'], count=1, panel=False)
        df = df.dropna()
        df = df[df['close'] == df['high_limit']]
        return list(df.code)
