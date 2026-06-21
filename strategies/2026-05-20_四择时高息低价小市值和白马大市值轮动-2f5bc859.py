# Clone from JoinQuant
# postId: 2f5bc8596aa24d07126677f70869b556
# backtestId: 975d1e04711e7965139d1499aa5f8129
# title: 四择时高息低价小市值和白马大市值轮动

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import warnings
import datetime as dt
from jqlib.technical_analysis import *
import math
from dateutil.relativedelta import relativedelta
import numpy as np
def initialize(context):
    # ==============================================
    # 一、系统基础设置（聚宽平台核心配置）
    # ==============================================
    # 日志级别设置，仅输出错误级日志，减少日志冗余
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('history', 'error')
    # 启用真实价格交易（用前收盘价计算，避免回测虚拟价格偏差）
    set_option('use_real_price', True)
    # 启用未来数据规避，防止回测用到未来函数
    set_option("avoid_future_data", True)

    # ==============================================
    # 二、全局状态标记（运行时动态更新的状态变量）
    # ==============================================
    g.today_trade_allowed = True           # 当日交易权限开关，顶背离触发时设为False禁止开仓
    g.first_run_completed = False          # 首次运行完成标记，避免重复触发初始化逻辑
    g.signal = 'empty'                     # 择时最终信号，可选值：big(大盘白马)、small(小盘高息)、empty(空仓)
    g.market_temperature = 'warm'          # 市场温度状态，可选值：cold(冷)、warm(暖)、hot(热)，默认暖市场兜底
    g.total_return_rate = 0.0              # 账户累计总收益率，用于日志输出
    g.stock_num = 10                       # 单类选股最终持仓标的数量（大盘/小盘均用该值）
    
    # ==============================================
    # 三、MACD背离风控参数（顶底背离风控相关）
    # ==============================================
    g.dbl = []                              # 市场顶背离记录列表，记录顶背离发生状态
    g.dixl = []                             # 市场底背离记录列表，记录底背离发生状态

    # ==============================================
    # 四、市场温度与白马股选股参数
    # ==============================================
    
    # 白马股高价过滤阈值
    g.max_stock_price_2= 5000              # 白马股：最高股价过滤阈值（元），超过该值不入选
    
    # 市场温度计算核心参数
    g.market_temp_lookback = 220           # 市场温度计算回看交易日数（约1年）
    g.market_temp_short_ma = 5              # 市场温度短期均线天数
    g.market_temp_cold = 0.3                # 冷市场阈值，市场温度低于该值为冷市场
    g.market_temp_hot = 0.7                 # 热市场阈值，市场温度高于该值为热市场
    g.market_temp_warm_ratio = 1.20         # 暖市场：窗口期内最大涨幅/最低值比值阈值
    g.market_temp_warm_window = 60          # 暖市场：涨幅判断窗口期（交易日）

    # ---------- 冷市场 白马股财务筛选阈值 ----------
    g.wh_cold_pb_min = 0                     # 冷市场：市净率PB筛选下限
    g.wh_cold_pb_max = 1                     # 冷市场：市净率PB筛选上限
    g.wh_cold_op_cash_min = 0                # 冷市场：经营活动现金流入下限
    g.wh_cold_adjusted_profit_min = 0        # 冷市场：扣非净利润下限
    g.wh_cold_cash_profit_ratio_min = 2.0    # 冷市场：经营现金流/扣非净利润最低比值
    g.wh_cold_return_inc_min = 1.5           # 冷市场：净资产收益率(ROE)下限
    g.wh_cold_profit_growth_min = -15        # 冷市场：净利润同比增速下限（%）

    # ---------- 暖市场 白马股财务筛选阈值 ----------
    g.wh_warm_pb_min = 0                     # 暖市场：市净率PB筛选下限
    g.wh_warm_pb_max = 1                     # 暖市场：市净率PB筛选上限
    g.wh_warm_op_cash_min = 0                # 暖市场：经营活动现金流入下限
    g.wh_warm_adjusted_profit_min = 0        # 暖市场：扣非净利润下限
    g.wh_warm_cash_profit_ratio_min = 1.0    # 暖市场：经营现金流/扣非净利润最低比值
    g.wh_warm_return_inc_min = 2.0           # 暖市场：净资产收益率(ROE)下限
    g.wh_warm_profit_growth_min = 0          # 暖市场：净利润同比增速下限（%）

    # ---------- 热市场 白马股财务筛选阈值 ----------
    g.wh_hot_pb_min = 3                      # 热市场：市净率PB筛选下限
    g.wh_hot_op_cash_min = 0                 # 热市场：经营活动现金流入下限
    g.wh_hot_adjusted_profit_min = 0         # 热市场：扣非净利润下限
    g.wh_hot_cash_profit_ratio_min = 0.5     # 热市场：经营现金流/扣非净利润最低比值
    g.wh_hot_return_inc_min = 3.0            # 热市场：净资产收益率(ROE)下限
    g.wh_hot_profit_growth_min = 20          # 热市场：净利润同比增速下限（%）

    # ==============================================
    # 五、高息低价小盘股选股核心参数
    # ==============================================
    g.dividend_ratio_1 = 1/4                 # 高息低价股：股息率筛选区间上限（取前25%高股息标的）
    g.max_stock_price = 9                     # 高息低价股：最高股价限制（元），超过该值不入选

    # ==============================================
    # 六、持仓与交易相关状态变量
    # ==============================================
    g.BOND_CODE = '511010.XSHG'              # 避险标的：国债ETF代码，顶背离/空仓信号时买入
    g.hold_list = []                          # 当前持仓股票列表（不含国债）
    g.just_sold = []                          # 当日刚卖出的股票列表，避免当日买回
    g.high_limit_list = []                    # 当日涨停持仓股票列表，打开涨停才卖出
    g.sorted_stocks = []                      # 排序后的选股结果列表，供交易函数调用
    g.previous_portfolio_value = context.portfolio.starting_cash  # 上一交易日账户总市值，计算当日收益率
    g.order_info_dict = {}                    # 持仓订单信息字典，用于输出持仓详情
    g.previous_date = get_previous_trading_date(context.current_dt)  # 上一交易日日期，所有历史数据查询基准

    # ==============================================
    # 七、择时参数
    # ==============================================
    
    # ====================  择时开关  ====================
    g.enable_strategy_one = True
    g.enable_strategy_two = True
    g.enable_strategy_three =  True 
    
    # ==================== 择时一参数 ====================
    g.s1_lookback_days = 10          # 滚动计算涨幅的天数
    g.s1_big_mean_threshold = 4      # big_mean大于该值则选small，否则选big
    g.s1_atol = 1e-8                 # 浮点数比较精度
    g.stock_limit = 50        # 股池选取的股票数量上限
    g.signal_lookback_days = 10            # 大小盘择时：个股涨幅均值回看交易日数
    g.monthly_adjustment_growth_threshold = 15  # 月度调仓：小盘股10日涨幅触发阈值（%），超过该值启用小盘股池
    
    # ==================== 择时二参数 ====================
    g.s2_lookback_days = 20          # 沪深300/国证2000计算涨幅的天数
    g.s2_ratio_upper = 1.2           # 比值上限（>1.2选small）
    g.s2_ratio_lower = 1.0           # 比值下限（<1.0选big）
    g.s2_atol = 1e-8                 # 浮点数比较精度
    g.s2_empty_threshold = -2.0      # 空仓阈值（%）：两者涨幅均值均<该值则空仓
    
    # ==================== 择时三参数 ====================
    g.s3_small_stock_num = 50        # 选取小市值股票数量
    g.s3_valid_stock_threshold = 5   # 有效标的数量阈值（不足则兜底big）
    g.s3_price_count = 10            # 获取价格的天数
    g.s3_variance_threshold = 0.02   # 方差阈值（<0.02且均值>0选small）
    g.s3_mean_threshold = 0.0        # 均值阈值（>0选small）
    # 新增：择时三空仓阈值（小市值股票涨幅均值<该值，触发空仓）
    g.s3_empty_threshold = -1.0      # 空仓阈值（%）：归一化后均值<该值则空仓
    
    # ==============================================
    # 八、定时任务配置
    # ==============================================
    # run_daily(update_previous_date, '06:01')  # 每日更新前一交易日日期
    run_daily(signal, '06:02')                # 每日开盘前计算择时信号
    run_daily(prepare_stock_list, '06:03')    # 每日开盘前准备持仓与涨停股票列表
    # run_daily(daily_output_selected_stocks, '06:04')  # 每日输出选股列表
    run_daily(dapan, '09:30:05')              # 开盘后检测大盘顶底背离，触发风控
    run_monthly(monthly_adjustment, 1, '09:30:10')  # 每月第一个交易日执行月度调仓
    run_daily(check_limit_up_and_buy, '14:00')# 每日14点检查涨停打开卖出与补仓逻辑
    # run_daily(print_position_info, '15:10')   # 收盘后输出持仓与收益信息

    # ==============================================
    # 九、首次启动初始化执行
    # ==============================================
    # 首次运行先计算择时信号（确定big/small/empty）
    signal(context)
    # 首次运行立即执行月度调仓逻辑（根据信号调仓）
    monthly_adjustment(context)
    # 标记首次运行完成，避免重复触发
    g.first_run_completed = True  


# ----------------- 三个独立择时函数 -----------------
def strategy_one_signal(context):
    """择时一：大小盘涨幅均值博弈逻辑"""
    # 先判断开关，禁用则直接返回empty
    if not getattr(g, 'enable_strategy_one', True):
        return 'empty'
    
    s1_signal = 'empty'
    try:
        yesterday = context.previous_date
        lookback_days = g.s1_lookback_days 
        
        # 获取大小盘股票池
        big_stocks = daily_my_trader_big(context)
        small_stocks = daily_my_trader_small(context)

        # 计算滚动N日涨幅均值（N由参数控制）
        big_mean = calculate_price_mean(big_stocks, yesterday, lookback_days)
        small_mean = calculate_price_mean(small_stocks, yesterday, lookback_days)

        # 核心博弈逻辑
        if big_mean > small_mean and big_mean > 0:
            # 阈值从g.s1_big_mean_threshold读取
            s1_signal = 'small' if big_mean > g.s1_big_mean_threshold else 'big'
        elif big_mean < small_mean and small_mean > 0:
            s1_signal = 'small'
        elif np.isclose(big_mean, small_mean, atol=g.s1_atol):  # 精度参数
            if big_mean > 0 and small_mean > 0:
                s1_signal = 'big'
            else:
                s1_signal = 'empty'
        else:
            s1_signal = 'empty'
    except Exception as e:
        log.error(f"择时一逻辑计算失败: {str(e)}，设为empty")
        s1_signal = 'empty'
    return s1_signal

def strategy_two_signal(context):
    """择时二（MarioC）：沪深300 vs 国证2000比值逻辑"""
    if not getattr(g, 'enable_strategy_two', True):
        return 'neutral'
    
    s2_signal = 'neutral'
    try:
        lookback_days_s2 = g.s2_lookback_days
        yesterday = context.previous_date
        # 1. 获取指数成分股
        stockList_hs300 = get_index_stocks('000300.XSHG', yesterday)
        stockList_gz2000 = get_index_stocks('399303.XSHE', yesterday)
        
        # 2. 计算沪深300成分股N日平均涨跌幅
        mean_hs300 = 0.0
        if stockList_hs300:
            price_df = get_price(
                stockList_hs300, 
                count=lookback_days_s2, 
                end_date=yesterday, 
                fields='close', 
                panel=False,
                fq='pre'
            )
            if not price_df.empty:
                pivot_df = price_df.pivot(index='time', columns='code', values='close')
                pivot_valid = pivot_df.dropna(axis=1)
                if not pivot_valid.empty:
                    change = (pivot_valid.iloc[-1] / pivot_valid.iloc[0] - 1) * 100
                    mean_hs300 = np.mean(change)
        
        # 3. 计算国证2000成分股N日平均涨跌幅
        mean_gz2000 = 0.0
        if stockList_gz2000:
            price_df = get_price(
                stockList_gz2000, 
                count=lookback_days_s2, 
                end_date=yesterday, 
                fields='close', 
                panel=False,
                fq='pre'
            )
            if not price_df.empty:
                pivot_df = price_df.pivot(index='time', columns='code', values='close')
                pivot_valid = pivot_df.dropna(axis=1)
                if not pivot_valid.empty:
                    change = (pivot_valid.iloc[-1] / pivot_valid.iloc[0] - 1) * 100
                    mean_gz2000 = np.mean(change)
        
        # 4. 新增：先判断空仓条件（沪深300+国证2000均下跌且跌幅超阈值）
        if (mean_hs300 < g.s2_empty_threshold) and (mean_gz2000 < g.s2_empty_threshold):
            s2_signal = 'empty'  # 触发空仓
        # 5. 比值判断逻辑（仅当未触发空仓时执行）
        elif not np.isclose(mean_hs300, 0.0, atol=g.s2_atol):
            if mean_gz2000 > 0 and mean_hs300 < 0:
                s2_signal = 'small'
            elif mean_gz2000 < 0 and mean_hs300 > 0:
                s2_signal = 'big'
            else:
                if mean_gz2000 < 0 and mean_hs300 < 0:
                    ratio = abs(mean_gz2000) / abs(mean_hs300)
                else:
                    ratio = mean_gz2000 / mean_hs300
                
                if ratio > g.s2_ratio_upper:
                    s2_signal = 'small'
                elif ratio < g.s2_ratio_lower:
                    s2_signal = 'big'
                else:
                    s2_signal = 'neutral'
        else:
            s2_signal = 'neutral'
    except Exception as e:
        log.error(f"择时二逻辑计算失败: {str(e)}，设为中立")
        s2_signal = 'neutral'
    return s2_signal
    
def strategy_three_signal(context):
    """择时三（偷鸡摸狗）：小市值一致性判断逻辑"""
    if not getattr(g, 'enable_strategy_three', True):
        return 'neutral'
    
    s3_signal = 'neutral'
    try:
        yesterday = context.previous_date
        # 1. 小市值一致性判断
        stocks = get_index_stocks('399101.XSHE', yesterday)
        q = query(valuation.code).filter(valuation.code.in_(stocks)).order_by(valuation.circulating_market_cap.asc())
        df = get_fundamentals(q, date=yesterday)
        lst = list(df.code)[:g.s3_small_stock_num] if not df.empty else []
        
        if lst:
            h_ratio = get_price(
                lst, 
                count=g.s3_price_count,
                end_date=yesterday, 
                fields='close', 
                panel=False,
                fq='pre'
            )
            if not h_ratio.empty:
                pivot_df = h_ratio.pivot(index='time', columns='code', values='close')
                pivot_valid = pivot_df.dropna(axis=1)
                if len(pivot_valid.columns) >= g.s3_valid_stock_threshold:
                    change = (pivot_valid.iloc[-1] / pivot_valid.iloc[0] - 1) * 100
                    A1 = np.array(change)
                    norm = np.linalg.norm(A1) if np.linalg.norm(A1) != 0 else 1
                    normalized_array = A1 / norm
                    variance = np.var(normalized_array)
                    mean = np.mean(normalized_array)
                    
                    # 2. 先判断空仓条件（均值<空仓阈值）
                    if mean < g.s3_empty_threshold:
                        s3_signal = 'empty'  # 触发空仓
                    # 3. 核心逻辑（仅当未触发空仓时执行）
                    elif variance < g.s3_variance_threshold and mean > g.s3_mean_threshold:
                        s3_signal = 'small'
                    else:
                        s3_signal = 'big'
                else:
                    s3_signal = 'big'
            else:
                s3_signal = 'big'
        else:
            s3_signal = 'big'
    except Exception as e:
        log.error(f"择时三逻辑计算失败: {str(e)}，设为big")
        s3_signal = 'big'
    return s3_signal
    
# ----------------- 股票池函数 -----------------
def daily_my_trader_big(context):
    """大盘股池（择时一计算用）"""
    yesterday = context.previous_date
    stocks = get_index_stocks('000300.XSHG', yesterday)
    stocks = filter_kcbj_stock(stocks)
    stocks = filter_all_stock(context, stocks)
    stocks = filter_new_stock(context, stocks)
    if stocks:
        df = get_fundamentals(
            query(valuation.code)
            .filter(valuation.code.in_(stocks))
            .order_by(valuation.circulating_market_cap.desc()) 
            .limit(g.stock_limit)  
        )
        stocks = list(df.code)
    else:
        stocks = []
    return stocks


def daily_my_trader_small(context):
    """小盘股池（择时一计算用）"""
    yesterday = context.previous_date
    stocks = get_index_stocks('399303.XSHE', yesterday)
    stocks = filter_kcbj_stock(stocks)
    stocks = filter_all_stock(context, stocks)
    stocks = filter_new_stock(context, stocks)
    if stocks:
        df = get_fundamentals(
            query(valuation.code)
            .filter(valuation.code.in_(stocks))
            .order_by(valuation.circulating_market_cap.desc()) 
            .limit(g.stock_limit)  
        )
        stocks = list(df.code)
    else:
        stocks = []
    return stocks

def signal(context):
    """择时信号生成：整合三个择时逻辑，适配单择时测试场景"""

    # ==================================================
    # 第一步：调用拆分后的三个择时函数获取信号（带开关控制）
    # ==================================================
    s1_signal = strategy_one_signal(context)
    s2_signal = strategy_two_signal(context)
    s3_signal = strategy_three_signal(context)

    # ==================================================
    # 新增：收集「启用的择时」及其信号（过滤禁用择时）
    # ==================================================
    enabled_strategies = []
    # 择时一：启用且信号有效（big/small）
    if g.enable_strategy_one and s1_signal in ('big', 'small'):
        enabled_strategies.append(('择时一', s1_signal))
    # 择时二：启用且信号有效（big/small）
    if g.enable_strategy_two and s2_signal in ('big', 'small'):
        enabled_strategies.append(('择时二', s2_signal))
    # 择时三：启用且信号有效（big/small）
    if g.enable_strategy_three and s3_signal in ('big', 'small'):
        enabled_strategies.append(('择时三', s3_signal))

    # ==================================================
    # 第二步：适配单择时测试的决策规则
    # ==================================================
    final_signal = 'empty'
    decision_reason = ""
    
    # 场景1：仅启用1个择时 → 直接采用该择时的信号
    if len(enabled_strategies) == 1:
        final_signal = enabled_strategies[0][1]
        decision_reason = f"仅启用{enabled_strategies[0][0]}，直接采用其信号：{final_signal}"
    
    # 场景2：启用≥2个择时 → 投票逻辑
    elif len(enabled_strategies) >= 2:
        # 统计票数
        small_votes = [v for v in enabled_strategies if v[1] == 'small']
        big_votes = [v for v in enabled_strategies if v[1] == 'big']
        small_count = len(small_votes)
        big_count = len(big_votes)
        total_valid = len(enabled_strategies)
        
        # 投票逻辑（2/3票、1/1分歧等）
        if total_valid == 3:
            if small_count == 3:
                final_signal = 'small'
                decision_reason = "全票通过（3/3），三个择时都认为买小盘"
            elif big_count == 3:
                final_signal = 'big'
                decision_reason = "全票通过（3/3），三个择时都认为买大盘/避险"
            else:
                if small_count == 2:
                    final_signal = 'small'
                    decision_reason = f"多数通过（2/3），{[v[0] for v in small_votes]} 认为买小盘"
                else:
                    final_signal = 'big'
                    decision_reason = f"多数通过（2/3），{[v[0] for v in big_votes]} 认为买大盘/避险"
        elif total_valid == 2:
            if small_count == 2:
                final_signal = 'small'
                decision_reason = f"一致通过（2/2），{[v[0] for v in small_votes]} 认为买小盘"
            elif big_count == 2:
                final_signal = 'big'
                decision_reason = f"一致通过（2/2），{[v[0] for v in big_votes]} 认为买大盘/避险"
            else:
                # 1:1分歧 → 优先择时一
                final_signal = s1_signal if s1_signal in ('big', 'small') else 'empty'
                decision_reason = f"分歧（1:1），保留择时一信号：{final_signal}"
    
    # 场景3：无启用择时/所有启用择时信号无效 → 空仓
    else:
        final_signal = 'empty'
        decision_reason = "无启用的有效择时，空仓"

    # ==================================================
    # 第三步：信号更新逻辑
    # ==================================================
    if not hasattr(g, 'signal') or g.signal != final_signal:
        old_signal_log = getattr(g, 'signal', '无（首次启动）')
        g.signal = final_signal
        # 打印开关状态和投票信息，方便调试
#        log.info(f"择时开关状态：择时一={g.enable_strategy_one}，择时二={g.enable_strategy_two}，择时三={g.enable_strategy_three}")
#        log.info(f"启用择时的信号：{enabled_strategies}，最终信号={final_signal}，理由={decision_reason}")




def Market_temperature(context):
    """计算市场温度（白马股选股的核心依赖"""
    index300 = attribute_history('000300.XSHG', g.market_temp_lookback, '1d', ('close'), df=False)['close']
    market_height = (np.mean(index300[-g.market_temp_short_ma:]) - min(index300)) / (max(index300) - min(index300))
    if market_height < g.market_temp_cold: 
        g.market_temperature = "cold"
    elif market_height > g.market_temp_hot: 
        g.market_temperature = "hot"
    elif max(index300[-g.market_temp_warm_window:]) / min(index300) > g.market_temp_warm_ratio: 
        g.market_temperature = "warm"
    else:
        g.market_temperature = "warm"  # 兜底逻辑


def filter_white_horse_initial(context):
    """白马股初始过滤：沪深300成分股 + 通用异常过滤"""
    # 初始列表：沪深300成分股
    all_stocks = get_index_stocks("000300.XSHG")
    # 通用异常过滤
    filtered_stocks = filter_all_stock(context, all_stocks)
    # 过滤科创/北交/创业板
    filtered_stocks = filter_kcbjc_stock(filtered_stocks)
    return filtered_stocks


def filter_white_horse_financial(context, stock_list):
    """白马股财务条件过滤：按市场温度匹配规则"""
    if not stock_list:
        return [], None
    
    # 确保市场温度已计算
    if not hasattr(g, 'market_temperature'):
        Market_temperature(context)
    
    try:
        # 冷市场财务条件
        if g.market_temperature == "cold":
            q = query(
                valuation.code,
                valuation.pb_ratio,
                cash_flow.subtotal_operate_cash_inflow,
                indicator.adjusted_profit,
                indicator.inc_return,
                indicator.inc_net_profit_year_on_year,
                indicator.roa
            ).filter(
                valuation.code.in_(stock_list),
                valuation.pb_ratio.between(g.wh_cold_pb_min, g.wh_cold_pb_max), 
                cash_flow.subtotal_operate_cash_inflow > g.wh_cold_op_cash_min, 
                indicator.adjusted_profit > g.wh_cold_adjusted_profit_min,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > g.wh_cold_cash_profit_ratio_min, 
                indicator.inc_return > g.wh_cold_return_inc_min,
                indicator.inc_net_profit_year_on_year > g.wh_cold_profit_growth_min
            )
            sort_field = (indicator.roa / valuation.pb_ratio).desc()
        # 暖市场财务条件
        elif g.market_temperature == "warm":
            q = query(
                valuation.code,
                valuation.pb_ratio,
                cash_flow.subtotal_operate_cash_inflow,
                indicator.adjusted_profit,
                indicator.inc_return,
                indicator.inc_net_profit_year_on_year,
                indicator.roa
            ).filter(
                valuation.code.in_(stock_list),
                valuation.pb_ratio.between(g.wh_warm_pb_min, g.wh_warm_pb_max), 
                cash_flow.subtotal_operate_cash_inflow > g.wh_warm_op_cash_min, 
                indicator.adjusted_profit > g.wh_warm_adjusted_profit_min,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > g.wh_warm_cash_profit_ratio_min, 
                indicator.inc_return > g.wh_warm_return_inc_min,
                indicator.inc_net_profit_year_on_year > g.wh_warm_profit_growth_min
            )
            sort_field = (indicator.roa / valuation.pb_ratio).desc()
        # 热市场财务条件
        else:
            q = query(
                valuation.code,
                valuation.pb_ratio,
                cash_flow.subtotal_operate_cash_inflow,
                indicator.adjusted_profit,
                indicator.inc_return,
                indicator.inc_net_profit_year_on_year,
                indicator.roa
            ).filter(
                valuation.code.in_(stock_list),
                valuation.pb_ratio > g.wh_hot_pb_min, 
                cash_flow.subtotal_operate_cash_inflow > g.wh_hot_op_cash_min, 
                indicator.adjusted_profit > g.wh_hot_adjusted_profit_min,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > g.wh_hot_cash_profit_ratio_min, 
                indicator.inc_return > g.wh_hot_return_inc_min,
                indicator.inc_net_profit_year_on_year > g.wh_hot_profit_growth_min
            )
            sort_field = indicator.roa.desc()
        
        # 执行查询
        df = get_fundamentals(q)
        if df.empty:
            return [], sort_field
        
        return df['code'].tolist(), sort_field
    except Exception as e:
        log.error(f"白马股财务过滤失败：{str(e)}")
        return [], None


def calculate_price_mean(stocks, end_date, lookback_days):
    """统一计算股票列表的涨幅均值"""
    if not stocks:
        return 0.0
    
    try:
        price_df = get_price(
            stocks, 
            count=lookback_days, 
            end_date=end_date, 
            fields='close',
            frequency='1d', 
            panel=False
        )
        if price_df.empty:
            return 0.0
        
        price_wide = price_df.pivot(index='time', columns='code', values='close')
        price_change = (price_wide.iloc[-1] / price_wide.iloc[0] - 1) * 100
        mean_value = np.mean(np.nan_to_num(np.array(price_change)))
        return mean_value
    except Exception as e:
        log.error(f"计算涨幅均值失败: {str(e)}")
        return 0.0


def White_Horse(context):
    """白马股选股主函数"""
    # 1. 初始过滤
    stocks = filter_white_horse_initial(context)
    # 2. 计算市场温度
    Market_temperature(context)
    # 3. 财务过滤
    stocks, sort_field = filter_white_horse_financial(context, stocks)
    # 4. 高价过滤
    stocks = filter_highprice_stock_2(context, stocks)
    
    # 排序逻辑
    if stocks:
        df = get_fundamentals(
            query(valuation.code)
            .filter(valuation.code.in_(stocks))
            .order_by(sort_field)
        )
        stocks = list(df.code)
    else:
        stocks = []
    
    # 截取前N只
    g.sorted_stocks = stocks[:g.stock_num+1]  
    return g.sorted_stocks


def daily_my_trader_1(context):
    """高息低价小盘股选股主函数"""
    yesterday = context.previous_date
    stocks = get_all_securities('stock', yesterday).index.tolist()
    stocks = filter_kcbj_stock(stocks)
    stocks = get_dividend_ratio_filter_list(context, stocks, False, 0, g.dividend_ratio_1)
    stocks = get_peg(context, stocks)
    stocks = filter_all_stock(context, stocks)
    stocks = filter_highprice_stock(context, stocks)
    
    # 按市值升序排序
    if stocks:
        df = get_fundamentals(
            query(valuation.code)
            .filter(valuation.code.in_(stocks))
            .order_by(valuation.market_cap.asc())
        )
        stocks = list(df.code)
    else:
        stocks = []
    
    # 截取前N只
    g.sorted_stocks = stocks[:g.stock_num+1]  
    return g.sorted_stocks

def daily_output_selected_stocks(context):
    """每日选股列表输出"""
    log.info("="*50)
    log.info("【每日选股】开始输出当日选股列表...")
    yesterday = context.previous_date
    current_data = get_current_data()
    
    # 完全复刻月度调仓的选股逻辑
    if not g.today_trade_allowed:
        target_list = []
        log.info(f"【每日选股】当日交易权限关闭，选股列表为空")
    else:
        if g.signal == 'big':
            target_list = White_Horse(context)[:g.stock_num]
            log.info(f"【每日选股】信号=big，选取白马股前{g.stock_num}只")
        elif g.signal == 'small':
            target_list = daily_my_trader_1(context)[:g.stock_num]
            log.info(f"【每日选股】信号=small，选取小盘股前{g.stock_num}只")
        else:
            target_list = []
            log.info(f"【每日选股】信号=empty，选股列表为空")
    
    # 最终异常过滤
    target_list = filter_all_stock(context, target_list)
    log.info(f"【每日选股】最终异常过滤后：{len(target_list)}只")
    
    # 去重
    seen = set()
    selected_stocks = []
    for s in target_list:
        if s not in seen:
            seen.add(s)
            selected_stocks.append(s)
    log.info(f"【每日选股】去重后：{len(selected_stocks)}只")
    
    # 获取市值排序
    market_cap_dict = {}
    if selected_stocks:
        try:
            df = get_fundamentals(
                query(valuation.code, valuation.market_cap)
                .filter(valuation.code.in_(selected_stocks))
                .order_by(valuation.market_cap.asc())
            )
            market_cap_dict = dict(zip(df['code'], df['market_cap']))
            selected_stocks = list(df.code)
            log.info(f"【每日选股】按市值排序完成")
        except Exception as e:
            log.error(f"【每日选股】获取市值数据失败：{str(e)}")
            for s in selected_stocks:
                market_cap_dict[s] = 0.0
    
    # 输出日志
    log.info(f"【每日选股】当日选股列表总共: {len(selected_stocks)}只")    
    log.info("——————————————————————————————————")
    
    # 获取行业信息
    industry_data = {}
    try:
        industry_data = get_industry(selected_stocks, date=context.previous_date)
        log.info(f"【每日选股】获取行业信息完成")
    except Exception as e:
        log.error(f"【每日选股】获取行业信息失败：{str(e)}")
    
    # 逐只输出
    for i, stock in enumerate(selected_stocks, 1):
        try:
            name = get_security_info(stock).display_name
            market_cap = market_cap_dict.get(stock, 0.0)
            industry_info = industry_data.get(stock, {})
            jq_l2 = industry_info.get('jq_l2', {})
            industry_name = jq_l2.get('industry_name', '未知行业')
            
            log.info(f"【每日选股】第 {i}：{stock} {name} 市值: {market_cap:.2f}亿 行业: {industry_name}")
        except Exception as e:
            log.error(f"【每日选股】输出股票{stock}信息失败：{str(e)}")
    
    log.info("——————————————————————————————————")
    log.info("="*50)
    return selected_stocks


# ----------------- 交易执行核心函数 -----------------
def prepare_stock_list(context):
    """每日开盘前准备持仓与涨停列表"""
    g.just_sold = []  # 每日重置
    g.high_limit_list = []
    hold_list = list(context.portfolio.positions)
    if hold_list:
        df = get_price(hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'],
                       count=1, panel=False)
        g.high_limit_list = df[df['close'] == df['high_limit']]['code'].tolist()
    g.hold_list = hold_list


def dapan(context):
    """大盘顶底背离检测与风控"""
    # 检测国证2000顶底背离
    top_divergence, bottom_divergence = detect_divergences('399303.XSHE', context)
    
    # 顶背离触发：空仓非涨停标的，买入国债避险
    if top_divergence:
        g.dbl.append(True)
        g.today_trade_allowed = False    
        
        current_data = get_current_data()
        sell_count = 0
        # 统计需要卖出的非涨停、非国债标的
        for stock in list(context.portfolio.positions.keys()):
            if stock == g.BOND_CODE:
                continue
            if current_data[stock].last_price < current_data[stock].high_limit:
                sell_count += 1
        
        if sell_count > 0:
            sold_stocks = []
            failed_stocks = []
            for stock in list(context.portfolio.positions.keys()):
                if stock == g.BOND_CODE:
                    continue
                if current_data[stock].last_price < current_data[stock].high_limit:
                    try:
                        position = context.portfolio.positions[stock]
                        close_position(position)
                        sold_stocks.append(stock)
                    except Exception as e:
                        failed_stocks.append(stock)
            
            # 卖出后买入国债
            if len(sold_stocks) > 0:
                if not current_data[g.BOND_CODE].paused and current_data[g.BOND_CODE].last_price > 0:
                    available_cash = context.portfolio.available_cash
                    min_buy = 5000
                    actual_buy_amount = max(available_cash, min_buy) if available_cash >= min_buy else 0
                    
                    if actual_buy_amount >= min_buy:
                        try:
                            order_value(g.BOND_CODE, actual_buy_amount)
                        except Exception as e:
                            pass
    else:
        g.today_trade_allowed = True
        
    # 底背离记录
    if bottom_divergence:
        g.dixl.append(True)


def check_limit_up_and_buy(context):
    """涨停打开卖出与补仓逻辑"""
    # 空仓信号或禁止交易时直接返回
    if g.signal == 'empty' or not g.today_trade_allowed:
        return

    current_data = get_current_data()
    sold_stocks = []

    # 处理涨停打开的持仓
    if g.high_limit_list:
        for stock in g.high_limit_list.copy():
            if current_data[stock].last_price < current_data[stock].high_limit:
                if stock in context.portfolio.positions:
                    position = context.portfolio.positions[stock]
                    close_position(position)
                    sold_stocks.append(stock)
                    g.high_limit_list.remove(stock)

    # 有卖出才执行补仓
    if sold_stocks:
        # 按信号更新选股池
        if g.signal == 'big':
            White_Horse(context)
        elif g.signal == 'small':
            daily_my_trader_1(context)
        else:
            valid_stocks = []
        
        valid_stocks = g.sorted_stocks if g.signal in ('big', 'small') else []
        valid_stocks = [s for s in valid_stocks if s not in g.just_sold]

        # 计算需要补仓的数量
        stock_positions = [s for s in context.portfolio.positions if s != g.BOND_CODE]
        position_count = len(stock_positions)
        need_buy_num = max(0, g.stock_num - position_count)

        # 补仓前先卖出国债
        if need_buy_num > 0 and valid_stocks:
            if g.signal in ('big', 'small'):
                sell_bond_etf(context)
                available_cash = context.portfolio.available_cash
                stock_positions = [s for s in context.portfolio.positions if s != g.BOND_CODE]
                need_buy_num = max(0, g.stock_num - len(stock_positions))
            else:
                available_cash = context.portfolio.available_cash

            # 执行补仓
            if need_buy_num > 0 and available_cash > 0:
                per_stock_cash = available_cash / need_buy_num
                bought = 0
                for s in valid_stocks:
                    if (s not in context.portfolio.positions 
                        and current_data[s].last_price < current_data[s].high_limit
                        and current_data[s].last_price > current_data[s].low_limit
                        and not current_data[s].paused
                        and s not in g.just_sold
                    ):
                        success = open_position(s, per_stock_cash)
                        if success:
                            available_cash -= per_stock_cash
                            bought += 1
                        if bought >= need_buy_num or available_cash <= 0:
                            break


# ----------------- 交易封装函数 -----------------
def order_target_value_(security, value):
    """统一交易接口封装"""
    return order_target_value(security, value)


def open_position(security, value):
    """开仓函数"""
    name = get_security_info(security).display_name
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False


def close_position(position):
    """平仓函数，记录盈亏与刚卖出列表"""
    security = position.security
    name = get_security_info(security).display_name
    order = order_target_value_(security, 0)
    g.just_sold.append(security)
    
    if order != None and order.filled > 0:
        profit = (position.price - position.avg_cost) * position.total_amount
        profit_pct = (position.price / position.avg_cost - 1) * 100
        return True
    return False


def monthly_adjustment(context):
    """月度调仓主函数"""
    yesterday = context.previous_date
    current_data = get_current_data()
    
    # 顶背离时直接空仓
    if not g.today_trade_allowed:
        empty_all_positions(context)
        return
    
    # 买入股票前先卖出国债
    if g.signal in ('big', 'small'):
        sell_bond_etf(context)
    
    # 空仓信号：直接空仓买国债
    if g.signal == 'empty':
        empty_all_positions(context)
        return
    
    # 大盘信号：买入白马股
    elif g.signal == 'big':
        white_horse_stocks = White_Horse(context)
        # 卖出非白马、非涨停、非国债的持仓
        for stock in g.hold_list:
            if (stock not in white_horse_stocks) and (stock not in g.high_limit_list) and (stock != g.BOND_CODE):
                if stock in context.portfolio.positions:
                    close_position(context.portfolio.positions[stock])
        
        # 买入白马股
        target_list = white_horse_stocks[:g.stock_num]
        target_list = filter_all_stock(context, target_list)
        
        # 均分资金买入
        available_cash = context.portfolio.available_cash  
        position_count = len([s for s in context.portfolio.positions if s in target_list])
        if len(target_list) > position_count and available_cash > 0:
            per_stock_cash = available_cash / (len(target_list) - position_count)
            for s in target_list:
                if (s not in context.portfolio.positions 
                    and current_data[s].last_price < current_data[s].high_limit
                    and current_data[s].last_price > current_data[s].low_limit
                    and not current_data[s].paused
                    and s not in g.just_sold
                ):
                    if open_position(s, per_stock_cash):
                        available_cash -= per_stock_cash
                    if available_cash <= 0 or len(context.portfolio.positions) >= g.stock_num:
                        break
    
    # 小盘信号：买入高息低价小盘股
    elif g.signal == 'small':
        small_stocks = daily_my_trader_1(context) or []
        big_mean = calculate_price_mean(daily_my_trader_big(context), yesterday, 10)
        small_mean = calculate_price_mean(small_stocks, yesterday, 10)

        # 目标股票池
        target_list = small_stocks[:g.stock_num]
        target_list = filter_all_stock(context, target_list)

        # 卖出不在目标列表的持仓
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.high_limit_list) and (stock != g.BOND_CODE):
                if stock in context.portfolio.positions:
                    close_position(context.portfolio.positions[stock])

        # 均分资金买入
        available_cash = context.portfolio.available_cash  
        position_count = len(context.portfolio.positions)
        if len(target_list) > position_count and available_cash > 0:
            per_stock_cash = available_cash / (len(target_list) - position_count)
            for s in target_list:
                if (s not in context.portfolio.positions 
                    and current_data[s].last_price < current_data[s].high_limit
                    and current_data[s].last_price > current_data[s].low_limit
                    and not current_data[s].paused
                    and s not in g.just_sold
                ):
                    if open_position(s, per_stock_cash):
                        available_cash -= per_stock_cash
                    if available_cash <= 0 or len(context.portfolio.positions) >= g.stock_num:
                        break


def empty_all_positions(context):
    """空仓避险函数"""
    current_data = get_current_data()
    positions = context.portfolio.positions
    has_stock_position = False
    
    # 仅清空非国债持仓
    if positions:
        for security in list(positions.keys()):
            if security == g.BOND_CODE:
                continue
            try:
                close_position(positions[security])
                has_stock_position = True
            except Exception as e:
                pass       
        
        # 重置股票相关全局变量
        g.hold_list = []
        g.high_limit_list = []
        g.just_sold = []
    
    # 可用资金全部买入国债
    bond_position = positions.get(g.BOND_CODE, None)
    current_bond_value = bond_position.value if bond_position else 0.0
    available_cash = context.portfolio.available_cash
    min_buy = 5000
    
    bond_tradable = not current_data[g.BOND_CODE].paused and current_data[g.BOND_CODE].last_price > 0
    
    if available_cash >= min_buy and bond_tradable:
        actual_buy_amount = available_cash
        try:
            order_value(g.BOND_CODE, actual_buy_amount)
        except Exception as e:
            pass


# ----------------- 选股过滤工具函数 -----------------
def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2):
    """股息率筛选函数"""
    if not (0 <= p1 < p2 <= 1):
        return []
    
    time1 = context.previous_date
    time0 = time1 - relativedelta(years=1)
    batch_size = 100
    all_dividend_df = pd.DataFrame()
    
    # 分批获取分红数据
    for i in range(0, len(stock_list), batch_size):
        batch_stocks = stock_list[i:i+batch_size]
        try:
            batch_df = finance.run_query(
                query(finance.STK_XR_XD.code, finance.STK_XR_XD.bonus_amount_rmb)
                .filter(finance.STK_XR_XD.a_registration_date >= time0,
                        finance.STK_XR_XD.a_registration_date <= time1,
                        finance.STK_XR_XD.code.in_(batch_stocks))
            )
            all_dividend_df = pd.concat([all_dividend_df, batch_df], ignore_index=True)
        except Exception as e:
            continue
    
    if all_dividend_df.empty:
        return []
    
    # 获取市值数据
    try:
        cap_df = get_fundamentals(
            query(valuation.code, valuation.market_cap)
            .filter(valuation.code.in_(stock_list)),
            date=time1
        ).set_index('code')
    except Exception as e:
        return []
    
    # 计算总分红与股息率
    dividend_sum = all_dividend_df.groupby('code')['bonus_amount_rmb'].sum()
    DR = pd.DataFrame({'bonus_amount_rmb': dividend_sum})
    DR = DR.join(cap_df, how='left')
    DR['dividend_ratio'] = (DR['bonus_amount_rmb'] / 1e8) / DR['market_cap']
    
    # 异常值过滤
    DR = DR[DR['market_cap'].notna() & (DR['market_cap'] > 0)]
    DR = DR[(DR['dividend_ratio'].notna()) & 
            (DR['dividend_ratio'] >= 0) & 
            (DR['dividend_ratio'] < float('inf'))]
    
    if DR.empty:
        return []
    
    # 排序与区间筛选
    DR = DR.sort_values(by='dividend_ratio', ascending=sort)
    total = len(DR)
    start_idx = int(p1 * total)
    end_idx = int(p2 * total)
    
    # 确保至少选1只
    if start_idx >= end_idx:
        end_idx = start_idx + 1
        if end_idx > total:
            end_idx = total
    
    final_list = DR.index[start_idx:end_idx].tolist()
    return final_list


def get_peg(context, stocks):
    """PEG财务筛选"""
    query_date = context.previous_date  
    df = get_fundamentals(
        query(valuation.code).filter(
            valuation.code.in_(stocks),
            income.np_parent_company_owners > 0, 
            income.net_profit > 0, 
            income.operating_revenue > 1e8,
            indicator.roe > 0, 
            indicator.roa > 0
        ),
        date=query_date
    )
    if df is None or df.empty:
        return []
    stocks = list(df.code)
    return stocks


# ----------------- MACD指标与背离检测函数 -----------------
def EMA(series, N):
    """EMA计算函数"""
    return pd.Series.ewm(series, span=N, min_periods=N-1, adjust=False).mean()


def MACD(close, SHORT=12, LONG=26, M=9):
    """MACD指标计算"""
    DIF = EMA(close, SHORT) - EMA(close, LONG)
    DEA = EMA(DIF, M)
    MACD = (DIF - DEA) * 2
    return DIF, DEA, MACD


def detect_divergences(stock, context):
    """MACD顶底背离检测"""
    fast = 12
    slow = 26
    sign = 9
    rows = (fast + slow + sign) * 5
    
    top_divergence = False
    bottom_divergence = False
    
    # ��取历史K线
    try:
        grid = attribute_history(stock, rows, fields=['close'])
        if grid is None or len(grid) < rows:
            return top_divergence, bottom_divergence
    except Exception as e:
        return top_divergence, bottom_divergence
    
    try:
        # 计算MACD
        grid['dif'], grid['dea'], grid['macd'] = MACD(grid.close, SHORT=fast, LONG=slow, M=sign)
        
        # 死叉点（顶背离）
        dead_cross = (grid['macd'] < 0) & (grid['macd'].shift(1) > 0)
        dead_cross_points = dead_cross[dead_cross].index
        
        # 金叉点（底背离）
        gold_cross = (grid['macd'] > 0) & (grid['macd'].shift(1) < 0)
        gold_cross_points = gold_cross[gold_cross].index
        
        # 顶背离检测
        if len(dead_cross_points) >= 2:
            key2 = dead_cross_points[-2]
            key1 = dead_cross_points[-1]
            
            price_condition = grid.close[key2] < grid.close[key1]
            dif_condition = grid.dif[key2] > grid.dif[key1] > 0
            macd_condition = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]
            
            if not (pd.isna(macd_condition) or pd.isna(dif_condition)):
                is_top_divergence = price_condition and dif_condition and macd_condition
                if is_top_divergence and len(grid['dif'].values) > 20:
                    recent_avg = np.mean(grid['dif'].values[-10:])
                    prev_avg = np.mean(grid['dif'].values[-20:-10])
                    top_divergence = recent_avg < prev_avg
        
        # 底背离检测
        if len(gold_cross_points) >= 2:
            key2 = gold_cross_points[-2]
            key1 = gold_cross_points[-1]
            
            price_condition = grid.close[key2] > grid.close[key1]
            dif_condition = grid.dif[key2] < grid.dif[key1] < 0
            macd_condition = grid.macd.iloc[-2] < 0 < grid.macd.iloc[-1]
            
            if not (pd.isna(macd_condition) or pd.isna(dif_condition)):
                is_bottom_divergence = price_condition and dif_condition and macd_condition
                if is_bottom_divergence and len(grid['dif'].values) > 20:
                    recent_avg = np.mean(grid['dif'].values[-10:])
                    prev_avg = np.mean(grid['dif'].values[-20:-10])
                    bottom_divergence = recent_avg > prev_avg
    
    except Exception as e:
        pass
        
    return top_divergence, bottom_divergence


# ----------------- 股票过滤工具函数 -----------------
def filter_kcbjc_stock(stock_list):
    """过滤科创/北交/创业板股票"""
    return [stock for stock in stock_list if not (stock[0] in {'4', '8', '3'} or stock[:2] == '68')]


def filter_all_stock(context, stocks):
    """通用异常股票过滤：停牌、ST、涨跌停、退市"""
    curr_data = get_current_data()
    valid_stocks = []
    for stock in stocks:
        if (not curr_data[stock].paused
            and not curr_data[stock].is_st
            and 'ST' not in curr_data[stock].name
            and '*' not in curr_data[stock].name
            and '退' not in curr_data[stock].name
            and curr_data[stock].last_price < curr_data[stock].high_limit
            and curr_data[stock].last_price > curr_data[stock].low_limit
        ):
            valid_stocks.append(stock)
    return valid_stocks


def filter_new_stock(context, stock_list):
    """过滤上市不满1年的次新股"""
    yesterday = context.previous_date
    return [s for s in stock_list if not (yesterday - get_security_info(s).start_date < dt.timedelta(days=375))]


def filter_kcbj_stock(stock_list):
    """过滤科创/北交股票（保留创业板）"""
    return [stock for stock in stock_list if not (stock[0] in {'4', '8'} or stock[:2] == '68')]


def filter_highprice_stock(context, stock_list):
    """高息低价股：高价过滤"""
    prices = history(1, '1d', 'close', stock_list, df=False)
    return [s for s in stock_list if s in context.portfolio.positions or prices[s][-1] < g.max_stock_price]


def filter_highprice_stock_2(context, stock_list):
    """白马股：高价过滤"""
    prices = history(1, '1d', 'close', stock_list, df=False)
    return [s for s in stock_list if s in context.portfolio.positions or prices[s][-1] < g.max_stock_price_2]


def update_previous_date(context):
    """每日更新前一交易日日期"""
    try:
        prev_date = get_previous_trading_date(context.current_dt)
        if prev_date is None:
            prev_date = context.current_dt
        g.previous_date = prev_date
    except Exception as e:
        log.error(f"更新交易日失败: {str(e)}")


def get_previous_trading_date(date):
    """获取指定日期的前一交易日"""
    try:
        trade_days = get_trade_days(end_date=date, count=2)
        if len(trade_days) >= 2:
            return trade_days[0]
        elif len(trade_days) == 1:
            return trade_days[0]
        else:
            return date
    except Exception as e:
        log.error(f"获取交易日失败: {str(e)}")
        return date


def sell_bond_etf(context):
    """强制清仓国债ETF，释放资金"""
    bond_code = g.BOND_CODE
    current_data = get_current_data()
    
    # 无持仓直接返回
    bond_position = context.portfolio.positions.get(bond_code)
    if not bond_position or bond_position.total_amount == 0:
        return
    
    # 停牌无法卖出
    if current_data[bond_code].paused:
        log.warning(f"【国债ETF停牌】{bond_code} 无法卖出")
        return
    
    # 清仓
    order = order_target_value(bond_code, 0)
    
    # 重试机制
    retry_times = 2
    for i in range(retry_times + 1):
        bond_position = context.portfolio.positions.get(bond_code)
        if not bond_position or bond_position.total_amount == 0:
            break
        if i < retry_times:
            order = order_target_value(bond_code, 0)
            import time
            time.sleep(1)


def print_position_info(context):
    """收盘后输出持仓与收益信息"""
    log.info("——————————————————————————————————")
    print('证券名称\t买入日期\t买入价格\t现价\t持仓收益率')
    for position in list(context.portfolio.positions.values()):
        security = position.security
        name = get_security_info(security).display_name
        order_info = {}
        order_info['security'] = name
        order_info['买入日期'] = position.init_time.date()
        order_info['买入价格'] = position.avg_cost
        order_info['现价'] = position.price
        order_info['持仓收益率'] = (position.price / position.avg_cost - 1) * 100
        key = '{}:{}'.format(order_info['买入日期'], name)
        g.order_info_dict[key] = order_info
        print('{:<0}\t{}\t{:.2f}\t{:.2f}\t{:.2f}%'.format(
            order_info['security'],
            order_info['买入日期'],
            order_info['买入价格'],
            order_info['现价'],
            order_info['持仓收益率']
        ))
    log.info("——————————————————————————————————")
    
    # 累计收益率
    g.total_return_rate = (context.portfolio.portfolio_value - context.portfolio.starting_cash) / context.portfolio.starting_cash * 100
    print('累计收益率={:.2f}%'.format(g.total_return_rate))
    
    # 当日收益率
    if g.previous_portfolio_value:
        daily_return_rate = (context.portfolio.portfolio_value / g.previous_portfolio_value - 1) * 100
        print('今日收益率={:.2f}%'.format(daily_return_rate))
    
    # 更新上日市值
    g.previous_portfolio_value = context.portfolio.portfolio_value
    log.info("——————————————————————————————————")
