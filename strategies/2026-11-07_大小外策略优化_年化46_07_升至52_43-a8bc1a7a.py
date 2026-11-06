# Clone from JoinQuant
# postId: a8bc1a7a953f1c743d8b2ae351095544
# backtestId: 1331c112be3a73a3aaa7d91508a6ddc3
# title: 大小外策略优化：年化46.07%升至52.43%

# -*- coding: utf-8 -*-
# I01 排名缓冲整手修复
# 实验: 相同整手修复加已存在G05持仓排名缓冲
# 对照: I00；分钟/100万元/空仓；日期见运行说明。
I_SOURCE_PARENT = 'G05'
I_SOURCE_SHA256 = '12f268db7e8bd5f77ee2d31b493f3331fea7ab69629b023aa274587c98de8b35'
I_MOTHER_SHA256 = 'fea1240fae4e934019cac7ff355cb88f642eb512f25db03c8fc87594ba82408e'
I_METHOD = 'repair_interaction'

# 克隆自聚宽文章：https://www.joinquant.com/post/68121
# 标题：最强大小外-修复波动率版-11年收益265倍回撤16.39
# 作者：rbq2025

# 克隆自聚宽文章：https://www.joinquant.com/post/67762
# 标题：15年至26/3/1回撤17.3% 年化60% 最强大小外
# 作者：CGJK

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import warnings
import datetime as dt
from jqlib.technical_analysis import *

warnings.filterwarnings("ignore")

def initialize(context):
    g.b_variant = 'I01'
    g.b_build = '9d464be8c17c063c'
    g.b_counts = {}
    g.i_buy_slippage = 0.0
    b_audit('BUILD', mother=I_MOTHER_SHA256, build=g.b_build, variant=g.b_variant,
            source_parent=I_SOURCE_PARENT, source_parent_sha256=I_SOURCE_SHA256, method=I_METHOD,
            contract='minute; initial_cash=1000000; see I run matrix',
            actual_start=str(context.current_dt), initial_value=context.portfolio.total_value)
    run_daily(b_end_day, '15:10')
    # ==================================================
    # 【可调试参数配置区】所有参数均已接入逻辑，可直接调试
    # ==================================================
    # --- 基础持仓参数（原始值）---
    g.stock_num = 3                      # 单类选股核心标的数
    g.bei_num = 3                        # 小盘股备选倍数
    g.highest = 50                       # 小盘股最高价限制
    g.buy_stock_count = 6                # 最终买入标的数量
    
    # --- 择时信号参数（原始值）---
    g.signal_lookback_days = 10          # 大小盘择时回看天数（N）
    g.monthly_adjust_growth_threshold = 15  # 月度调仓涨幅阈值（%）
    
    # --- 止损参数（原始值）---
    g.fixed_stop_loss_ratio = 0.90       # 固定止损比例（亏损10%）
    g.trailing_stop_ratio = 0.90         # 移动止损比例（回撤10%）
    g.stop_loss_replenish_max = 4        # 止损后回补最大标的数
    
    # --- 市场广度择时参数（原始值）---
    g.market_breadth_threshold = 0.35    # 市场广度悲观阈值（<35%上涨）
    g.market_breadth_lookback = 21       # 市场广度均线回看天数
    
    # --- ETF动量参数（原始值）---
    g.etf_momentum_days = 20             # ETF动量回看天数
    g.etf_min_listed_days = 20           # ETF最小上市天数
    
    # --- 微盘股质量过滤参数（原始值）---
    g.small_net_profit_margin_min = 0.0  # 小盘股最小净利率（>0）
    g.small_debt_to_asset_max = 0.8      # 小盘股最大资产负债率（<80%）
    
    # --- 小盘股选股参数（原始值）---
    g.small_cap_min = 10                  # 小盘股最小市值（亿）
    g.small_cap_max = 30                 # 小盘股最大市值（亿）
    g.small_cap_initial_count = 100      # 小盘股初筛数量
    g.small_cap_final_count = 50         # 小盘股精选数量
    g.small_parent_profit_min = 0.0      # 小盘股归母净利润下限
    g.small_net_profit_min = 0.0         # 小盘股净利润下限
    g.small_revenue_min = 1e8            # 小盘股营收下限（元）
    
    # --- 大盘股BIG策略参数（原始值）---
    g.big_pe_min = 0                     # 大盘股最小PE
    g.big_pe_max = 30                    # 大盘股最大PE
    g.big_ps_min = 0                     # 大盘股最小PS
    g.big_ps_max = 8                     # 大盘股最大PS
    g.big_pcf_max = 10                   # 大盘股最大PCF
    g.big_eps_min = 0.3                  # 大盘股最小EPS
    g.big_roe_min = 0.1                  # 大盘股最小ROE
    g.big_net_margin_min = 0.1           # 大盘股最小净利率
    g.big_gross_margin_min = 0.3         # 大盘股最小毛利率
    g.big_rev_growth_min = 0.25          # 大盘股最小营收增速
    
    # --- 大盘股ROIC策略参数（原始值）---
    g.roic_cap_min = 300                 # ROIC策略最小市值（亿）
    g.roic_pe_min = 0                    # ROIC策略最小PE
    g.roic_pe_max = 50                   # ROIC策略最大PE
    g.roic_eps_min = 0.12                # ROIC策略最小EPS
    g.roic_roa_min = 0.15                # ROIC策略最小ROA
    g.roic_debt_eq_max = 0.5             # ROIC策略最大产权比率
    g.roic_total_rev_growth_min = 0.3    # ROIC策略最小总营收增速
    g.roic_rev_growth_min = 0.2          # ROIC策略最小营收增速
    g.roic_retained_profit_min = 0       # ROIC策略最小留存收益
    g.roic_min = 0.10                    # ROIC策略最小ROIC
    
    # --- 大盘股BM策略参数（原始值）---
    g.bm_cap_min = 100                   # BM策略最小市值（亿）
    g.bm_cap_max = 900                   # BM策略最大市值（亿）
    g.bm_pb_min = 0                      # BM策略最小PB
    g.bm_pb_max = 10                     # BM策略最大PB
    g.bm_pcf_max = 4                     # BM策略最大PCF
    g.bm_eps_min = 0.3                   # BM策略最小EPS
    g.bm_roe_min = 0.2                   # BM策略最小ROE
    g.bm_net_margin_min = 0.1            # BM策略最小净利率
    g.bm_rev_growth_min = 0.2            # BM策略最小营收增速
    g.bm_op_profit_growth_min = 0.1      # BM策略最小营业利润增速
    
    # --- 白马股策略参数（原始值）---
    # 冷市场
    g.wh_cold_pb_min = 0
    g.wh_cold_pb_max = 1
    g.wh_cold_op_cash_min = 0
    g.wh_cold_adjusted_profit_min = 0
    g.wh_cold_cash_profit_ratio_min = 2.0
    g.wh_cold_return_inc_min = 1.5
    g.wh_cold_profit_growth_min = -15    # 百分比，非小数
    # 暖市场
    g.wh_warm_pb_min = 0
    g.wh_warm_pb_max = 1
    g.wh_warm_op_cash_min = 0
    g.wh_warm_adjusted_profit_min = 0
    g.wh_warm_cash_profit_ratio_min = 1.0
    g.wh_warm_return_inc_min = 2.0
    g.wh_warm_profit_growth_min = 0      # 百分比
    # 热市场
    g.wh_hot_pb_min = 3
    g.wh_hot_op_cash_min = 0
    g.wh_hot_adjusted_profit_min = 0
    g.wh_hot_cash_profit_ratio_min = 0.5
    g.wh_hot_return_inc_min = 3.0
    g.wh_hot_profit_growth_min = 20      # 百分比
    
    # --- 市场温度参数（原始值）---
    g.market_temp_lookback = 220         # 市场温度回看天数
    g.market_temp_short_ma = 5           # 市场温度短期均线天数
    g.market_temp_cold = 0.20            # 冷市场阈值
    g.market_temp_hot = 0.90             # 热市场阈值
    g.market_temp_warm_ratio = 1.20      # 暖市场涨幅比阈值
    g.market_temp_warm_window = 60       # 暖市场判断窗口期（天）
    
    # --- ETF池配置（原始值）---
    g.foreign_ETF = [
        '518880.XSHG', '513030.XSHG', '513100.XSHG', '164824.XSHE',
        '159866.XSHE', '513520.XSHG', '513730.XSHG', '515180.XSHG', '563020.XSHG',
    ]
    
    # ================== 优化策略开关（原始值）==================
    g.opt_market_breadth = False     # 开启市场广度择时
    g.opt_etf_momentum = True       # 2. ETF动量排序增强开关
    g.opt_small_quality = True      # 3. 微盘股财务质量过滤开关
    g.opt_trailing_stop = False      # 4. 移动止损开关
    g.opt_volatility_scaling = True # 5. 波动率风险均衡开关
    # =============================================================

    # --- 波动率风险均衡参数 ---
    g.volatility_lookback = 40       # 波动率回看天数

    # --- 基础设置（完全原始）---
    set_benchmark('513100.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0001, close_commission=0.0001,
                             close_today_commission=0, min_commission=5), type='stock')
    log.set_level('order', 'error')

    # --- 原始全局变量（完全原始）---
    g.no_trading_today_signal = False
    g.market_temperature = "warm"
    g.singal = 'etf'  # 保留原始拼写错误，避免逻辑偏差
    g.ETF_pool = []
    g.hold_list = []
    g.yesterday_HL_list = []
    g.bought_stocks = {}

    # --- 定时任务（完全原始）---
    run_daily(prepare_stock_list, '9:05')
    run_monthly(singal, 1, '9:00')
    run_weekly(clear, 1, '10:20')
    run_monthly(monthly_adjustment, 1, '10:30')
    run_daily(stop_loss, '14:30')
    run_daily(stop_loss, '14:50')

# ----------------- 优化功能模块（最终修复：市场广度日期逻辑）-----------------
def get_market_breadth_score(context):
    """修复未来数据问题：仅使用上一个交易日的已收盘数据"""
    all_stocks = get_index_stocks('000905.XSHG') 
    # 核心修复：end_date改为上一个交易日（context.previous_date），而非当日
    # context.previous_date是聚宽内置的“上一个已收盘的交易日”，无未来数据风险
    h = get_price(
        all_stocks, 
        count=g.market_breadth_lookback, 
        end_date=context.previous_date,  # 最终修复：使用上一个交易日
        fields=['close']
    )['close']
    # 处理可能的空值（部分股票停牌导致）
    h = h.fillna(method='ffill').fillna(method='bfill')
    ma20 = h.mean()  
    current_price = h.iloc[-1]
    breadth = (current_price > ma20).sum() / len(all_stocks)
    return breadth

def filter_small_quality(stock_list):
    """微盘股质量过滤：剔除亏损、高负债标的"""
    q = query(valuation.code).filter(
        valuation.code.in_(stock_list),
        indicator.net_profit_to_total_revenue > g.small_net_profit_margin_min,
        balance.total_liability / balance.total_assets < g.small_debt_to_asset_max
    )
    df = get_fundamentals(q)
    return list(df.code)

def get_ranked_etfs(etf_list, context):
    """对ETF池按动量排序"""
    end_dt = context.previous_date
    prices = b_price_matrix(etf_list, context, g.etf_momentum_days)
    if prices.empty:
        b_audit('BOUNDARY_EMPTY_ETF')
        return []
    returns = (prices.iloc[-1] / prices.iloc[0] - 1).sort_values(ascending=False)
    return list(returns.index)

# ----------------- 核心执行函数（无新增修改）-----------------
def clear(context):
    if g.bought_stocks:
        for stock, amount in list(g.bought_stocks.items()):
            if stock in context.portfolio.positions:
                b_order_value(stock, -amount)
        b_audit('MOTHER_CLEAR_BOOK', book=dict(g.bought_stocks))
        g.bought_stocks.clear()

def prepare_stock_list(context):
    g.hold_list = [p.security for p in list(context.portfolio.positions.values())]
    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        if df is None or df.empty:
            g.yesterday_HL_list = []
            b_audit('BOUNDARY_EMPTY_PREPARE')
            return
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []

def stop_loss(context):
    num = 0
    now_time = context.current_dt
    
    # 涨停破位卖出逻辑
    if g.yesterday_HL_list:
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'],
                                     skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data is not None and not current_data.empty and current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                o = b_order_target_value(stock, 0)
                num += c_exit_increment(o, 'high_limit_open', stock)

    ss_vals = []
    ss_codes = []
    for stock in g.hold_list:
        if stock in context.portfolio.positions:
            pos = context.portfolio.positions[stock]
            
            if not np.isfinite(pos.avg_cost) or pos.avg_cost <= 0:
                b_audit('BOUNDARY_INVALID_COST', code=stock)
                continue
            # 止损逻辑判断
            is_stop = False
            if g.opt_trailing_stop:
                h = attribute_history(stock, 20, '1d', ['high'])['high'].max()
                if pos.price < h * g.trailing_stop_ratio: is_stop = True
            elif pos.price < pos.avg_cost * g.fixed_stop_loss_ratio:
                is_stop = True
            
            # 只记录止损命中或距成本止损线2个百分点内的持仓，保留完整浮点精度。
            if is_stop or abs(pos.price / pos.avg_cost - g.fixed_stop_loss_ratio) <= 0.02:
                threshold = h * g.trailing_stop_ratio if g.opt_trailing_stop else pos.avg_cost * g.fixed_stop_loss_ratio
                b_audit('STOP_CHECK', code=stock, price=float(pos.price), avg_cost=float(pos.avg_cost),
                        threshold=float(threshold), stopped=bool(is_stop), trailing=bool(g.opt_trailing_stop))
            if is_stop:
                o = b_order_target_value(stock, 0)
                num += c_exit_increment(o, 'stop_loss', stock)
            else:
                ss_codes.append(stock)
                ss_vals.append((pos.price - pos.avg_cost) / pos.avg_cost)

    # 止损后回补逻辑
    if num >= 1 and ss_vals:
        k = min(g.stop_loss_replenish_max, len(ss_vals))
        idx = np.argsort(np.array(ss_vals))[:k]
        cash = context.portfolio.cash / k if k > 0 else 0
        b_audit('MOTHER_REFILL', selected=[ss_codes[int(i)] for i in idx], budget=cash, num=num)
        for i in idx:
            s = ss_codes[int(i)]
            if cash > 0:
                o = b_order_value(s, cash)
                c_record_refill(s, cash, o)

def singal(context):  # 保留原始拼写错误
    dt_last = context.previous_date
    N = g.signal_lookback_days
    
    # 市场广度择时（已传入context，使用上一个交易日数据）
    if g.opt_market_breadth:
        breadth = get_market_breadth_score(context)
        if breadth < g.market_breadth_threshold:
            g.singal = 'etf'
            g.ETF_pool = fun_delNewShare(context, g.foreign_ETF, g.etf_min_listed_days)
            return

    # 大小盘股票池筛选
    B_stocks = filter_new_stock(context, filter_st_stock(filter_kcbj_stock(get_index_stocks('000300.XSHG', dt_last))))
    S_stocks = filter_new_stock(context, filter_st_stock(filter_kcbj_stock(get_index_stocks('399101.XSHE', dt_last))))

    q = query(valuation.code, valuation.circulating_market_cap).filter(valuation.code.in_(B_stocks)).order_by(valuation.circulating_market_cap.desc())
    Blst = list(get_fundamentals(q, date=dt_last).code)[:20]

    q = query(valuation.code, valuation.circulating_market_cap).filter(valuation.code.in_(S_stocks)).order_by(valuation.circulating_market_cap.asc())
    Slst = list(get_fundamentals(q, date=dt_last).code)[:20]

    # 大小盘涨幅计算
    B_ratio = b_price_matrix(Blst, context, N)
    if B_ratio.empty:
        b_audit('BOUNDARY_EMPTY_SIGNAL', side='B_ratio')
        return
    change_BIG = (B_ratio.iloc[-1] / B_ratio.iloc[0] - 1) * 100
    B_mean = np.mean(np.nan_to_num(np.array(change_BIG)))

    S_ratio = b_price_matrix(Slst, context, N)
    if S_ratio.empty:
        b_audit('BOUNDARY_EMPTY_SIGNAL', side='S_ratio')
        return
    change_SMALL = (S_ratio.iloc[-1] / S_ratio.iloc[0] - 1) * 100
    S_mean = np.mean(np.nan_to_num(np.array(change_SMALL)))

    b_audit('SIGNAL_INPUT', big=B_mean, small=S_mean)

    # 信号判断
    if B_mean > S_mean and B_mean > 0:
        g.singal = d_big_leading_signal(B_mean, S_mean)
    elif B_mean < S_mean and S_mean > 0:
        g.singal = 'small'
    else:
        g.singal = 'etf'
        deltaday = g.etf_min_listed_days
        target_etf_pool = g.foreign_ETF
        if g.opt_etf_momentum:
            target_etf_pool = get_ranked_etfs(g.foreign_ETF, context)
        g.ETF_pool = fun_delNewShare(context, target_etf_pool, deltaday)
        if not g.ETF_pool:
            g.ETF_pool = fun_delNewShare(context, ['511010.XSHG'], deltaday)

def monthly_adjustment(context):
    dt_last = context.previous_date
    
    # 重新获取大小盘基准数据
    B_stocks = filter_new_stock(context, filter_st_stock(filter_kcbj_stock(get_index_stocks('000300.XSHG', dt_last))))
    S_stocks = filter_new_stock(context, filter_st_stock(filter_kcbj_stock(get_index_stocks('399101.XSHE', dt_last))))
    
    # 涨幅计算逻辑
    q_b = query(valuation.code).filter(valuation.code.in_(B_stocks)).order_by(valuation.circulating_market_cap.desc()).limit(20)
    Blst = list(get_fundamentals(q_b, date=dt_last).code)
    q_s = query(valuation.code).filter(valuation.code.in_(S_stocks)).order_by(valuation.circulating_market_cap.asc()).limit(20)
    Slst = list(get_fundamentals(q_s, date=dt_last).code)
    
    # 获取涨幅数据
    B_mean = b_month_mean(b_price_matrix(Blst, context, 10))
    S_mean = b_month_mean(b_price_matrix(Slst, context, 10))

    target_list = []

    # 策略路由逻辑（决定选股池）
    if (B_mean > g.monthly_adjust_growth_threshold) or (S_mean > g.monthly_adjust_growth_threshold):
        if B_mean >= S_mean:
            t1 = White_Horse(context)
            t2 = ROIC_BIG(context, B_stocks)
            t3 = BIG(context, B_stocks)
            t4 = BM(context, B_stocks)

            # --- 修改开始：均衡抽取逻辑 + 打印调试 ---
            combined_lists = [t1, t2, t3, t4]
            merged_list = []
            
            # 轮询抽取：依次从四个池子取第1名，再取第2名...
            for i in range(g.buy_stock_count):
                for sub_list in combined_lists:
                    if i < len(sub_list):
                        stock = sub_list[i]
                        if stock not in merged_list:
                            merged_list.append(stock)
                if len(merged_list) >= g.buy_stock_count:
                    break
            
            target_list = merged_list[:g.buy_stock_count]

            # 打印选股差异检查日志
            print("=" * 60)
            print(f"【调仓日志】时间: {context.current_dt.strftime('%Y-%m-%d')}")
            print(f"【市场状态】大盘涨幅(B_mean): {B_mean:.2f}%, 小盘涨幅(S_mean): {S_mean:.2f}%")
            print(f"【逻辑触发】触发大盘股均衡抽取 (Round Robin)")
            print(f"【子池数量】白马:{len(t1)}, ROIC:{len(t2)}, BIG:{len(t3)}, BM:{len(t4)}")
            print(f"【最终选股】{target_list}")
            print("=" * 60)
            # --- 修改结束 ---         
            
            #target_list = list(dict.fromkeys(t1 + t2 + t3 + t4))[:g.buy_stock_count]
        else:
            choice_s = S_stocks
            if g.opt_small_quality:
                choice_s = filter_small_quality(S_stocks)
            target_list = d_small_targets(SMALL(context, choice_s))
    else:
        if g.singal == 'big':
            target_list = d_big_targets(context, B_stocks)
        elif g.singal == 'small':
            choice_s = S_stocks
            if g.opt_small_quality:
                choice_s = filter_small_quality(S_stocks)
            target_list = d_small_targets(SMALL(context, choice_s))
        else:
            target_list = (g.ETF_pool if g.ETF_pool else g.foreign_ETF)[:g.buy_stock_count]

    growth_override = (B_mean > g.monthly_adjust_growth_threshold) or (S_mean > g.monthly_adjust_growth_threshold)
    actual_route = ('big' if B_mean >= S_mean else 'small') if growth_override else g.singal
    b_audit('MONTH_ROUTE', route=actual_route, signal=g.singal, growth_override=growth_override)
    b_audit('TARGET_RAW', targets=target_list, signal=g.singal, big=B_mean, small=S_mean)
    target_list = b_valid_targets(context, target_list)

    # 标的过滤（涨跌停、停牌）
    target_list = filter_limitup_stock(context, target_list)
    target_list = filter_limitdown_stock(context, target_list)
    target_list = filter_paused_stock(target_list)

    b_audit('TARGET_TRADABLE', targets=target_list)

    # 1. 卖出逻辑：不在目标池且未涨停的股票清仓
    for stock in list(context.portfolio.positions.keys()):
        if (stock not in target_list) and (stock not in g.yesterday_HL_list):
            close_position_logged(context.portfolio.positions[stock])

    # 2. 买入逻辑
    # 找出真正需要新买入的标的
    to_buy = [s for s in target_list if s not in context.portfolio.positions]
    need_count = len(to_buy)

    if need_count > 0:
        cash = context.portfolio.cash * 0.999
        b_audit('MONTH_CASH_BUFFER', before=context.portfolio.cash, after=cash,
                changed=(cash != context.portfolio.cash))
        
        # --- 情况 A: 开启真正的波动率风险均衡 ---
        if g.opt_volatility_scaling:
            # 获取历史价格（回看天数 + 1，用于计算收益率）
            h = b_price_matrix(to_buy, context, g.volatility_lookback + 1)
            
            # 计算日收益率的标准差（波动率）
            vols = d_allocation_risk(h)
            
            # 容错处理：如果某股票停牌或新上市无波动数据，填充为平均波动率，防止除以0
            vols = vols.fillna(vols.mean()).replace(0, vols.mean())
            
            # 如果依然全部为空（例如所有股票都是新股），则退化为等权重
            if vols.isna().all() or not np.isfinite(vols).all() or (vols <= 0).any():
                b_audit('BOUNDARY_INVALID_VOL')
                avg_value = cash / need_count
                for stock in to_buy:
                    open_position(stock, avg_value)
            else:
                # 计算波动率倒数
                inv_vols = 1.0 / vols
                # 归一化得到权重权重
                weights = inv_vols / inv_vols.sum()
                
                b_audit('NEW_BUY_WEIGHTS', codes=to_buy, weights=d_finite_dict(weights), budget=cash)
                for stock in to_buy:
                    target_value = cash * weights[stock]
                    open_position(stock, target_value)
                    
        # --- 情况 B: 未开启波动率均衡，执行等权重均分 ---
        else:
            avg_value = cash / need_count
            for stock in to_buy:
                open_position(stock, avg_value)

# ----------------- 选股子函数（无修改）-----------------
def get_stock_list(context):
    MKT_index = '399101.XSHE'
    initial_list = get_index_stocks(MKT_index)
    initial_list = filter_new_stock(context, filter_st_stock(filter_kcbj_stock(initial_list)))
    q = query(valuation.code, valuation.market_cap).filter(
        valuation.code.in_(initial_list), 
        valuation.market_cap.between(g.small_cap_min, g.small_cap_max)
    ).order_by(valuation.market_cap.asc())
    df_fun = get_fundamentals(q)[:g.small_cap_initial_count]
    initial_list = filter_paused_stock(list(df_fun.code))
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(initial_list)).order_by(valuation.market_cap.asc())
    df_fun = get_fundamentals(q)[:g.small_cap_final_count]
    return list(df_fun.code)

def get_stock_list_2(context):
    MKT_index = '399101.XSHE'
    initial_list = get_index_stocks(MKT_index)
    initial_list = filter_new_stock(context, filter_st_stock(filter_kcbj_stock(initial_list)))
    q = query(
        valuation.code, valuation.market_cap, income.np_parent_company_owners, 
        income.net_profit, income.operating_revenue
    ).filter(
        valuation.code.in_(initial_list), 
        valuation.market_cap.between(g.small_cap_min, g.small_cap_max), 
        income.np_parent_company_owners > g.small_parent_profit_min, 
        income.net_profit > g.small_net_profit_min, 
        income.operating_revenue > g.small_revenue_min
    ).order_by(valuation.market_cap.asc()).limit(g.small_cap_final_count)
    df = get_fundamentals(q)
    final_list = list(df.code)
    if not final_list:
        return []
    last_prices = history(1, unit='1d', field='close', security_list=final_list)
    return [s for s in final_list if (s in g.hold_list) or (s in last_prices and not last_prices.empty and last_prices[s].iloc[-1] <= g.highest)]

def SMALL(context, choice):
    target_list_1 = get_stock_list(context)
    target_list_2 = get_stock_list_2(context)
    target_list = list(dict.fromkeys(target_list_1 + target_list_2))[:g.stock_num * g.bei_num]
    df = get_fundamentals(query(valuation.code, indicator.roe, indicator.roa).filter(valuation.code.in_(target_list)).order_by(valuation.market_cap.asc()))
    return d_small_rank(context, df.set_index('code').index.tolist())

def BIG(context, choice):
    df = get_fundamentals(query(valuation.code).filter(
        valuation.code.in_(choice), 
        valuation.pe_ratio_lyr.between(g.big_pe_min, g.big_pe_max),
        valuation.ps_ratio.between(g.big_ps_min, g.big_ps_max), 
        valuation.pcf_ratio < g.big_pcf_max, 
        indicator.eps > g.big_eps_min, 
        indicator.roe > g.big_roe_min,
        indicator.net_profit_margin > g.big_net_margin_min, 
        indicator.gross_profit_margin > g.big_gross_margin_min, 
        indicator.inc_revenue_year_on_year > g.big_rev_growth_min,
    ).order_by(valuation.market_cap.desc()).limit(g.stock_num))
    return df.set_index('code').index.tolist()

def ROIC_BIG(context, choice):
    df = get_fundamentals(query(valuation.code).filter(
        valuation.code.in_(choice), 
        valuation.market_cap > g.roic_cap_min,
        valuation.pe_ratio.between(g.roic_pe_min, g.roic_pe_max), 
        indicator.eps > g.roic_eps_min, 
        indicator.roa > g.roic_roa_min,
        (balance.total_liability / balance.total_sheet_owner_equities) < g.roic_debt_eq_max,
        indicator.inc_total_revenue_year_on_year > g.roic_total_rev_growth_min, 
        indicator.inc_revenue_year_on_year > g.roic_rev_growth_min,
        balance.retained_profit > g.roic_retained_profit_min
    )).set_index('code').index.tolist()
    df = filter_roic(context, df)
    q = query(valuation.code).filter(valuation.code.in_(df)).order_by(balance.retained_profit.desc())
    return list(get_fundamentals(q).code)[:g.stock_num]

def BM(context, choice):
    df = get_fundamentals(query(valuation.code).filter(
        valuation.code.in_(choice), 
        valuation.market_cap.between(g.bm_cap_min, g.bm_cap_max),
        valuation.pb_ratio.between(g.bm_pb_min, g.bm_pb_max), 
        valuation.pcf_ratio < g.bm_pcf_max, 
        indicator.eps > g.bm_eps_min, 
        indicator.roe > g.bm_roe_min,
        indicator.net_profit_margin > g.bm_net_margin_min, 
        indicator.inc_revenue_year_on_year > g.bm_rev_growth_min, 
        indicator.inc_operation_profit_year_on_year > g.bm_op_profit_growth_min,
    ).order_by(valuation.market_cap.asc()).limit(g.stock_num))
    return df.set_index('code').index.tolist()

def White_Horse(context):
    Market_temperature(context)
    current_data = get_current_data()
    all_stocks = get_index_stocks("000300.XSHG")
    # 股票过滤逻辑（保留原始硬编码，非核心参数）
    all_stocks = [s for s in all_stocks if not (current_data[s].day_open == current_data[s].high_limit or current_data[s].day_open == current_data[s].low_limit or 
                  current_data[s].paused or current_data[s].is_st or 'ST' in current_data[s].name or '*' in current_data[s].name or '退' in current_data[s].name or
                  s.startswith('30') or s.startswith('68') or s.startswith('8') or s.startswith('4'))]

    # 白马股筛选（参数化）
    if g.market_temperature == "cold":
        q = query(valuation.code).filter(
            valuation.pb_ratio.between(g.wh_cold_pb_min, g.wh_cold_pb_max), 
            cash_flow.subtotal_operate_cash_inflow > g.wh_cold_op_cash_min, 
            indicator.adjusted_profit > g.wh_cold_adjusted_profit_min,
            cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > g.wh_cold_cash_profit_ratio_min, 
            indicator.inc_return > g.wh_cold_return_inc_min,
            indicator.inc_net_profit_year_on_year > g.wh_cold_profit_growth_min, 
            valuation.code.in_(all_stocks)
        ).order_by((indicator.roa / valuation.pb_ratio).desc()).limit(g.buy_stock_count + 1)
    elif g.market_temperature == "warm":
        q = query(valuation.code).filter(
            valuation.pb_ratio.between(g.wh_warm_pb_min, g.wh_warm_pb_max), 
            cash_flow.subtotal_operate_cash_inflow > g.wh_warm_op_cash_min, 
            indicator.adjusted_profit > g.wh_warm_adjusted_profit_min,
            cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > g.wh_warm_cash_profit_ratio_min, 
            indicator.inc_return > g.wh_warm_return_inc_min,
            indicator.inc_net_profit_year_on_year > g.wh_warm_profit_growth_min, 
            valuation.code.in_(all_stocks)
        ).order_by((indicator.roa / valuation.pb_ratio).desc()).limit(g.buy_stock_count + 1)
    else:
        q = query(valuation.code).filter(
            valuation.pb_ratio > g.wh_hot_pb_min, 
            cash_flow.subtotal_operate_cash_inflow > g.wh_hot_op_cash_min, 
            indicator.adjusted_profit > g.wh_hot_adjusted_profit_min,
            cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > g.wh_hot_cash_profit_ratio_min, 
            indicator.inc_return > g.wh_hot_return_inc_min,
            indicator.inc_net_profit_year_on_year > g.wh_hot_profit_growth_min, 
            valuation.code.in_(all_stocks)
        ).order_by(indicator.roa.desc()).limit(g.buy_stock_count + 1)
    return list(get_fundamentals(q).code)

def Market_temperature(context):
    # 市场温度计算（参数化）
    index300 = attribute_history('000300.XSHG', g.market_temp_lookback, '1d', ('close'), df=False)['close']
    if len(index300) < 2 or not np.isfinite(index300).all() or max(index300) <= min(index300):
        b_audit('BOUNDARY_MARKET_TEMPERATURE')
        return
    market_height = (np.mean(index300[-g.market_temp_short_ma:]) - min(index300)) / (max(index300) - min(index300))
    if market_height < g.market_temp_cold: 
        g.market_temperature = "cold"
    elif market_height > g.market_temp_hot: 
        g.market_temperature = "hot"
    elif max(index300[-g.market_temp_warm_window:]) / min(index300) > g.market_temp_warm_ratio: 
        g.market_temperature = "warm"

# ----------------- 辅助工具函数（无修改）-----------------
def filter_roic(context, stock_list):
    yesterday = context.previous_date
    res = []
    for stock in stock_list:
        factor = get_factor_values(stock, 'roic_ttm', end_date=yesterday, count=1)['roic_ttm']
        if factor is None or factor.empty:
            b_audit('BOUNDARY_EMPTY_ROIC', code=stock)
            continue
        roic = factor.iloc[0, 0]
        if roic > g.roic_min: 
            res.append(stock)
    return res

def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].paused]

def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [s for s in stock_list if (not current_data[s].is_st) and ('ST' not in current_data[s].name) and ('*' not in current_data[s].name) and ('退' not in current_data[s].name)]

def filter_kcbj_stock(stock_list):
    return [s for s in stock_list if not (s[0] in ['4', '8'] or s[:2] == '68' or s[0] == '3')]

def filter_limitup_stock(context, stock_list):
    if not stock_list:
        return []
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [s for s in stock_list if (s in context.portfolio.positions) or (s in last_prices and not last_prices.empty and last_prices[s].iloc[-1] < current_data[s].high_limit)]

def filter_limitdown_stock(context, stock_list):
    if not stock_list:
        return []
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [s for s in stock_list if (s in context.portfolio.positions) or (s in last_prices and not last_prices.empty and last_prices[s].iloc[-1] > current_data[s].low_limit)]

def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [s for s in stock_list if get_security_info(s) is not None and not (yesterday - get_security_info(s).start_date < dt.timedelta(days=375))]

def open_position(security, value):
    if np.isfinite(value) and value > 0 and not i_can_buy_lot(security, value, 'new_target'):
        return False
    o = b_order_target_value(security, value)
    return (o is not None) and (o.filled > 0)

def close_position_logged(position):
    o = b_order_target_value(position.security, 0)
    return (o is not None and o.status == OrderStatus.held)

def fun_delNewShare(context, equity, deltaday):
    deltaDate = context.current_dt.date() - dt.timedelta(deltaday)
    return [stock for stock in equity if get_security_info(stock) is not None and get_security_info(stock).start_date < deltaDate]

# B公共层只做观测和无有效数据时的边界处理，不移植A00整套行为。
def b_audit(event, **values):
    g.b_counts[event] = g.b_counts.get(event, 0) + 1
    if values.get('changed'):
        key = event + '_CHANGED'
        g.b_counts[key] = g.b_counts.get(key, 0) + 1
    log.info('[I][%s][%s] %s' % (g.b_variant, event, str(values)))

def b_price_matrix(stocks, context, count):
    stocks = list(dict.fromkeys(stocks))
    if not stocks:
        return pd.DataFrame()
    available = []
    for s in stocks:
        info = get_security_info(s)
        if info is not None and info.start_date <= context.previous_date:
            available.append(s)
    if not available:
        b_audit('BOUNDARY_NO_LISTED_PRICE', codes=stocks)
        return pd.DataFrame(columns=stocks, dtype=float)
    raw = get_price(available, end_date=context.previous_date, count=count,
                    frequency='daily', fields=['close'], panel=False, fq='pre',
                    skip_paused=False, fill_paused=True)
    if raw is None or raw.empty:
        b_audit('BOUNDARY_EMPTY_PRICE', codes=stocks)
        return pd.DataFrame(columns=stocks, dtype=float)
    # Preserve missing columns/NaNs; unlike A00, do not drop ETF NaN rankings.
    return raw.pivot(index='time', columns='code', values='close').sort_index().reindex(columns=stocks)

def b_month_mean(prices):
    if len(prices) < 10:
        b_audit('BOUNDARY_SHORT_MONTH_PRICE', rows=len(prices))
        return 0.0
    value = prices.ffill().pct_change(9, fill_method=None).iloc[-1].mean() * 100
    return float(value) if np.isfinite(value) else 0.0

def b_valid_targets(context, stocks):
    result = []
    for s in stocks:
        info = get_security_info(s)
        if info is not None and info.start_date <= context.previous_date and info.end_date >= context.current_dt.date():
            result.append(s)
    if result != stocks:
        b_audit('BOUNDARY_INVALID_TARGET', before=stocks, after=result)
    return result

def b_order_target_value(security, value):
    if not np.isfinite(value) or value < 0:
        b_audit('BOUNDARY_INVALID_ORDER', code=security, value=str(value))
        return None
    o = order_target_value(security, value)
    b_audit('ORDER_TARGET', code=security, requested=value,
            filled=0 if o is None else o.filled,
            status='none' if o is None else str(o.status))
    return o

def b_order_value(security, value):
    if not np.isfinite(value):
        b_audit('BOUNDARY_INVALID_ORDER', code=security, value=str(value))
        return None
    if value > 0 and not i_can_buy_lot(security, value, 'increment'):
        return None
    o = order_value(security, value)
    b_audit('ORDER_VALUE', code=security, requested=value,
            filled=0 if o is None else o.filled,
            status='none' if o is None else str(o.status))
    return o

def b_end_day(context):
    total = context.portfolio.total_value
    exposure = sum(p.value for p in context.portfolio.positions.values()) / total if total > 0 else 0.0
    record(exposure=exposure, position_count=len(context.portfolio.positions))
    b_audit('DAY_END', date=str(context.current_dt), exposure=exposure,
            cash=context.portfolio.cash, temporary_cash=dict(g.bought_stocks), counts=dict(g.b_counts))


# C轮因果诊断：订单仍在原调用点提交；下列函数不获取新行情。
def c_exit_increment(order, reason, code):
    sold = order is not None and order.filled > 0
    eligible = True
    b_audit('EXIT_REFILL_GATE', code=code, reason=reason, sold=sold,
            eligible=eligible, changed=(eligible != True),
            filled=0 if order is None else order.filled)
    return int(eligible)

def c_record_refill(code, requested, order):
    existed = code in g.bought_stocks
    before = g.bought_stocks.get(code, 0.0)
    filled_value = float(order.filled * order.price) if order is not None and order.filled > 0 else 0.0
    if code not in g.bought_stocks:
        g.bought_stocks[code] = requested
    after = g.bought_stocks.get(code, 0.0)
    mother_after = before if existed else requested
    b_audit('REFILL_RECEIPT', code=code, requested=requested,
            filled=0 if order is None else order.filled, filled_value=filled_value,
            book_before=before, book_after=after,
            changed=(abs(after - mother_after) > 1e-8))


# D轮接口：对照版保持C01输出，每个候选只替换其中一个函数。
def d_small_rank(context, base):
    # Retain exactly the original candidate set, and only use completed daily data.
    if len(base) < 2:
        b_audit('SMALL_REVERSAL_FALLBACK', reason='few_candidates')
        return base
    prices = b_price_matrix(base, context, 21).reindex(columns=base)
    if len(prices) < 21 or prices.isna().any().any() or not np.isfinite(prices.values).all() or (prices <= 0).any().any():
        b_audit('SMALL_REVERSAL_FALLBACK', reason='incomplete_21_day_prices')
        return base
    change = prices.iloc[-1] / prices.iloc[0] - 1
    # Original base is ascending market-cap order. Lower recent return ranks better.
    size_rank = pd.Series(np.arange(1, len(base) + 1), index=base, dtype=float) / len(base)
    reversal_rank = change.rank(method='average', ascending=True, pct=True)
    score = 0.60 * size_rank + 0.40 * reversal_rank
    after = score.sort_values(kind='mergesort').index.tolist()
    before_selected = base[:g.buy_stock_count]
    after_selected = after[:g.buy_stock_count]
    b_audit('SMALL_REVERSAL', before=before_selected, after=after_selected,
            returns=d_finite_dict(change), scores=d_finite_dict(score),
            changed=(after_selected != before_selected),
            membership_changed=(set(after_selected) != set(before_selected)))
    return after

def d_small_targets(ranked):
    before = ranked[:g.buy_stock_count]
    parent_targets = ranked[:min(4, g.buy_stock_count)]
    holding_set = set(g.hold_list)
    retained = [stock for stock in ranked[:5] if stock in holding_set][:min(4, g.buy_stock_count)]
    after = list(retained)
    for stock in ranked:
        if len(after) >= min(4, g.buy_stock_count):
            break
        if stock not in after:
            after.append(stock)
    # Keep current signal order; retention only changes membership when a fifth-ranked holding is kept.
    after = [stock for stock in ranked if stock in set(after)]
    b_audit('HOLDING_RANK_BUFFER', retained=retained, retention_rank=5,
            parent_targets=parent_targets, targets=after, changed=(parent_targets != after),
            membership_changed=(set(parent_targets) != set(after)))
    b_audit('SMALL_TARGET_COUNT', before=before, after=after, changed=(after != before))
    return after

def d_big_leading_signal(big, small):
    before = 'small' if big > 5 else 'big'
    after = before
    b_audit('STYLE_BIG_LEADING', big=float(big), small=float(small), before=before,
            after=after, changed=(after != before))
    return after

def d_big_targets(context, big_stocks):
    white = White_Horse(context)
    before = white[:g.buy_stock_count]
    after = before
    b_audit('BIG_MODELS', before=before, after=after, changed=(after != before))
    return after

def d_allocation_risk(prices):
    returns = prices.ffill().pct_change(fill_method=None)
    total = returns.std()
    risk = total
    b_audit('RISK_ESTIMATE', total=d_finite_dict(total), risk=d_finite_dict(risk), changed=False)
    return risk

def d_finite_dict(series):
    return {str(k): float(v) if np.isfinite(v) else None for k, v in series.items()}


def i_can_buy_lot(security, value, caller):
    # Current universe: main-board A shares and exchange-listed ETF/LOF, 100-share minimum.
    # Does not round/increase budgets or suppress platform errors. Sells never call this guard.
    quote = get_current_data()[security]
    price = float(quote.last_price)
    if not np.isfinite(price) or price <= 0:
        b_audit('BUY_SKIP_INVALID_QUOTE', code=security, caller=caller, price=str(price))
        return False
    minimum = 100.0 * price * (1.0 + g.i_buy_slippage)
    if value + 1e-8 < minimum:
        b_audit('BUY_SKIP_MIN_LOT', code=security, caller=caller, requested=float(value),
                quote=price, minimum_value=minimum, lot=100, changed=True)
        return False
    return True
