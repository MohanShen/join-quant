# Clone from JoinQuant
# postId: aaee30357ddba224573a58a447f65aba
# backtestId: b33926c8633b80309f131d72f15ab204
# title: 五福闹新春V5.2动态池优化

# 克隆自聚宽文章：https://www.joinquant.com/post/74243
# 标题：已解密。五福大军别再被13:10狙击了，快跑！
# 作者：烟花三月ETF
# 策略名称：五福闹新春 v5.2
# 策略类型：ETF 动量轮动 + 大A走弱期防御
# 核心思想：
#   1. 在正常期，从“固定ETF池+动态行业ETF池”中，按加权回归动量得分选出最强ETF持仓。
#   2. 当大A（沪深300/小盘/创业板/中证A500）中多数指数跌破10日均线时，进入走弱期，只投资全球/海外ETF。
#   3. 每日13:10进行调仓：先卖出不在目标列表中的持仓，再买入目标ETF。
#   4. 配置多重风控：R²过滤、均线过滤、成交量过滤、短期跌幅过滤、固定比例止损、回撤监控。

import numpy as np
import math
import re
import pandas as pd
from jqdata import *
from datetime import datetime, date, timedelta


# ============================================================
# 初始化函数：策略启动时只执行一次，用于设置参数、ETF池、定时任务
# ============================================================
def initialize(context):
    # 避免未来数据：确保回测时不会使用当前时点之后才可获得的数据，防止虚高收益
    set_option("avoid_future_data", True)
    # 开启动态复权：用真实价格（已考虑分红、送股、拆股等）进行交易计算
    set_option("use_real_price", True)
    # 设置基金类交易的百分比滑点：买入时成交价上浮0.01%，卖出时下浮0.01%
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    # 设置基金类交易费用：免印花税，佣金万分之一（0.01%），最低5元
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001, close_commission=0.0001, close_today_commission=0.0001, min_commission=5), type="fund")
    
    # 设置日志级别，减少噪音，只关注关键信息
    log.set_level('order', 'error')      # 订单日志：只显示错误
    log.set_level('system', 'error')     # 系统日志：只显示错误
    log.set_level('strategy', 'info')    # 策略日志：显示普通信息及以上
    
    log.info("【五福闹新春】v5.2！")

    # ==================== ETF池定义 ====================
    # 动态行业池：正常期使用，全市场ETF按跟踪指数分组，各指数保留流动性最佳ETF。
    # 全球/海外ETF池：走弱期使用，直接按代码过滤流动性后参与动量计算。
    g.global_etf_pool = [
        '518880.XSHG', '501018.XSHG', '161226.XSHE', '159985.XSHE', '159980.XSHE',
        '513310.XSHG', '159518.XSHE', '159509.XSHE', '513100.XSHG', '513520.XSHG',
        '513500.XSHG', '159502.XSHE', '513400.XSHG', '513030.XSHG', '513290.XSHG',
        '520830.XSHG', '159529.XSHE',
    ]
    g.dynamic_etf_pool = []          # 动态行业池
    g.merged_etf_pool = []           # 最终用于计算动量的池子
    g.global_threshold_divisor = 20000

    # 大A走弱期相关状态变量（走弱期使用全球ETF池防御）
    g.is_a_share_weak = False
    g.weak_period_ma_lookback = 10
    g.weak_start_date = None
    g.weak_days_count = 0
    g.max_weak_days = 20

    # 交易与持仓参数
    g.holdings_num = 1                 # 目标持仓ETF数量（当前为1只，集中持仓）
    g.defensive_etf = "511880.XSHG"    # 防御性ETF（银华日利，货币型ETF），无目标且可用时作为避风港
    g.min_money = 10                   # 最小交易金额（元）
    g.target_etfs_list = []            # 当前目标ETF列表
    g.etf_names_dict = {}              # ETF代码到简称的缓存字典（display_name）
    g.cache_date = None                # 收盘价缓存日期
    g.yesterday_close_cache = {}       # 昨日收盘价缓存

    # 动量计算参数
    g.lookback_days = 25               # 动量计算回看天数
    g.min_score_threshold = 0          # 动量得分下限
    g.max_score_threshold = 5          # 动量得分上限
    g.score_threshold_ratio = 0.9      # 候选池得分阈值系数（正常期：第N名得分×0.9）

    # 过滤条件开关与阈值
    g.enable_r2_filter = True          # 是否启用R²过滤（正常期）
    g.r2_threshold = 0.4               # R²最小阈值
    g.enable_ma_filter = True          # 是否启用均线过滤（走弱期）
    g.ma_lookback = 10                 # 均线周期
    g.ma_threshold = 1.0               # 当前价需大于MA×1.0（即站上均线）
    g.enable_volume_check = True       # 是否启用成交量过滤
    g.volume_lookback = 5              # 成交量回看天数
    g.volume_threshold = 1.8           # 今日预估成交量 / 近5日平均成交量 < 1.8
    g.enable_loss_filter = True        # 是否启用短期跌幅风控
    g.loss = 0.97                      # 近3日任意一日跌幅 < 3%（即日收益率 > -3%）

    # 回撤监控参数
    g.max_portfolio_value = 0          # 历史最高净值
    g.drawdown_threshold = 0.03        # 回撤预警阈值（3%）
    g.drawdown_records = []            # 回撤记录

    # 固定比例止损参数
    g.use_fixed_stop_loss = True       # 是否启用分钟级固定止损
    g.fixedStopLossThreshold = 0.95    # 当价格跌破成本价5%时止损

    # 设置基准为沪深300ETF，用于业绩对比
    set_benchmark("510300.XSHG")

    # ==================== 定时任务 ====================
    # 聚宽 run_daily 会在指定时间触发函数（tick级回测中可用 'every_bar'）
    run_daily(morning_routine, time='09:00')            # 09:00 晨间流水线：持仓检查→回撤监控→流动性阈值计算
    run_daily(midday_routine, time='09:40')              # 09:40 动态行业池更新+固定池过滤+合并池
    run_daily(afternoon_routine, time='13:10')          # 13:10 动量计算与排序（需早于卖出时间）
    run_daily(sell_routine, time='14:10')               # 13:10 卖出流水线（需早于买入时间）
    run_daily(buy_routine, time='14:20')                # 13:10 买入流水线
    run_daily(reset_daily_flags, time='15:10')          # 15:10 收盘流水线：重置价格缓存
    run_daily(minute_level_stop_loss, time='every_bar') # 分钟级固定止损（盘中每分钟检查）

    # 输出策略初始化参数汇总，方便回测时核对
    log.info(f"""
【策略参数初始化完成】
=== ETF池配置 ===
- 正常期：全市场动态行业池（按跟踪指数分组）
- 走弱期：全球/海外ETF池（按流动性过滤）
=== 大A走弱期判定 ===
- MA均线周期: {g.weak_period_ma_lookback}日
- 进入条件: 至少3/4指数低于MA{g.weak_period_ma_lookback}
- 退出条件: 至少3/4指数站上MA{g.weak_period_ma_lookback}
- 最长持续: {g.max_weak_days}个交易日
=== 动量得分过滤 ===
- 周期: {g.lookback_days}天
- 得分阈值: [{g.min_score_threshold}, {g.max_score_threshold}]
- 调仓系数: {g.score_threshold_ratio}
=== 过滤条件 ===
- R²过滤: {'启用' if g.enable_r2_filter else '禁用'} (阈值>{g.r2_threshold:.1f})
- 均线过滤: {'启用' if g.enable_ma_filter else '禁用'} (MA{g.ma_lookback}×{g.ma_threshold})
- 成交量过滤: {'启用' if g.enable_volume_check else '禁用'} (近{g.volume_lookback}日均量比<{g.volume_threshold:.1f})
- 短期风控: {'启用' if g.enable_loss_filter else '禁用'} (近3日单日跌幅<{1-g.loss:.0%})
=== 止损机制 ===
- 分钟级固定比例止损: {'启用' if g.use_fixed_stop_loss else '禁用'} (成本价×{g.fixedStopLossThreshold:.0%})
=== 其他配置 ===
- 持仓数量: {g.holdings_num}只
- 防御ETF: {g.defensive_etf}
- 最小交易额: {g.min_money}元
- 基准: 510300.XSHG
""")


# ============================================================
# 晨间流水线（09:00）：检查持仓、监控回撤、计算全市场流动性阈值
# ============================================================
def morning_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【晨间流水线】启动...")
    log.info("【持仓检查】检查当前持仓状态...")
    check_positions(context)
    log.info("【回撤监控】监控策略回撤...")
    monitor_drawdown(context)
    log.info("【流动性阈值】计算全市场ETF流动性阈值...")
    calculate_global_etf_threshold(context)
    log.info("⏸️ 【晨间流水线】执行完毕！")


# ============================================================
# 大A走弱期判断：4个宽基指数中至少3个跌破MA10时进入走弱期
# ============================================================
def check_a_share_weak_period(context):
    today = context.current_dt.date()
    indexes = {'大盘': '000300.XSHG', '小盘': '399101.XSHE', '创业板': '399006.XSHE', '中证A500': '000510.XSHG'}
    below_count = sum(
        1 for name, code in indexes.items()
        if (lambda df: df is not None and len(df) >= g.weak_period_ma_lookback and df['close'].iloc[-1] < df['close'].iloc[-g.weak_period_ma_lookback:].mean())(
            attribute_history(code, g.weak_period_ma_lookback + 1, '1d', ['close'], skip_paused=False)
        )
    )
    above_count = sum(
        1 for name, code in indexes.items()
        if (lambda df: df is not None and len(df) >= g.weak_period_ma_lookback and df['close'].iloc[-1] > df['close'].iloc[-g.weak_period_ma_lookback:].mean())(
            attribute_history(code, g.weak_period_ma_lookback + 1, '1d', ['close'], skip_paused=False)
        )
    )
    weak_enter = (below_count >= 3)
    weak_exit = (above_count >= 3)

    if g.is_a_share_weak and g.weak_start_date:
        g.weak_days_count = len(get_trade_days(start_date=g.weak_start_date, end_date=today))
    else:
        g.weak_days_count = 0

    if g.is_a_share_weak:
        if g.weak_days_count >= g.max_weak_days or weak_exit:
            log.info(f"🟢 【走弱期退出】下方{below_count}/4, 上方{above_count}/4，退出走弱期")
            g.is_a_share_weak = False
            g.weak_start_date = None
        else:
            log.info(f"🔴 【走弱期中】低于MA10:{below_count}/4，已持续{g.weak_days_count}/{g.max_weak_days}天，使用全球ETF池")
    elif weak_enter:
        log.info(f"🔴 【走弱期进入】低于MA10:{below_count}/4，触发条件")
        g.is_a_share_weak = True
        g.weak_start_date = today
    else:
        log.info(f"🟢 【正常期】低于MA10:{below_count}/4")


# ============================================================
# 早盘流水线（09:40后）：判断走弱期 + 更新池子
# ============================================================
def midday_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【早盘流水线】启动...")
    check_a_share_weak_period(context)
    if g.is_a_share_weak:
        log.info(f"🔴 【走弱期】从全球ETF池提取目标指数，在全市场找同指数ETF并选流动性最佳...")
        try:
            from jqdata import finance
            end_date = context.previous_date
            THRESHOLD = getattr(g, 'avg_etf_money_threshold', 0) or 0

            # 第1步：查询全球ETF的跟踪指数
            q = query(
                finance.FUND_INVEST_TARGET.code,
                finance.FUND_INVEST_TARGET.traced_index_code,
                finance.FUND_INVEST_TARGET.traced_index_name,
                finance.FUND_INVEST_TARGET.start_date,
            ).filter(finance.FUND_INVEST_TARGET.code.in_(g.global_etf_pool))
            df_t = finance.run_query(q)
            target_keys = set()
            no_index_codes = set(g.global_etf_pool)
            global_lookup = {}  # code -> (idx_code, idx_name)
            if df_t is not None and not df_t.empty:
                df_t = df_t.sort_values('start_date', ascending=False)
                for code in g.global_etf_pool:
                    rows = df_t[df_t['code'] == code]
                    if not rows.empty:
                        r = rows.iloc[0]
                        k = r['traced_index_code'] or r['traced_index_name']
                        if k:
                            target_keys.add(k)
                            global_lookup[code] = (r['traced_index_code'], r['traced_index_name'])
                            no_index_codes.discard(code)

            # 第2步：全市场查询，找跟踪相同指数的ETF
            candidate_set = set(no_index_codes)  # 无指数记录的原始基金保留
            all_index_df = None
            if target_keys:
                # 查询全市场ETF的跟踪指数
                etf_list = get_all_securities(['etf'], date=context.current_dt).index.tolist()
                for i in range(0, len(etf_list), 3000):
                    batch = etf_list[i:i + 3000]
                    q2 = query(
                        finance.FUND_INVEST_TARGET.code,
                        finance.FUND_INVEST_TARGET.traced_index_code,
                        finance.FUND_INVEST_TARGET.traced_index_name,
                        finance.FUND_INVEST_TARGET.start_date,
                    ).filter(finance.FUND_INVEST_TARGET.code.in_(batch))
                    df2 = finance.run_query(q2)
                    if df2 is not None and not df2.empty:
                        if all_index_df is None:
                            all_index_df = df2
                        else:
                            all_index_df = pd.concat([all_index_df, df2])

                if all_index_df is not None and not all_index_df.empty:
                    all_index_df = all_index_df.sort_values('start_date', ascending=False)
                    latest_df = all_index_df.groupby('code').first().reset_index()
                    # 匹配目标指数
                    for _, r in latest_df.iterrows():
                        k = r['traced_index_code'] or r['traced_index_name']
                        if k and k in target_keys:
                            candidate_set.add(r['code'])

            log.info(f"【走弱期】目标指数{len(target_keys)}个，候选ETF共{len(candidate_set)}只")

            # 第3步：流动性过滤 + 按指数分组
            candidate_list = list(candidate_set)
            price_data = get_price(candidate_list, end_date=end_date, count=3, frequency='daily', fields=['money'], panel=False)
            if price_data is None or price_data.empty:
                g.merged_etf_pool = list(g.global_etf_pool)
            else:
                avg_money = price_data.groupby('code')['money'].sum() / 3
                qualified = avg_money[avg_money > THRESHOLD] if THRESHOLD > 0 else avg_money

                # 构建 code -> index_key 映射
                code_to_key = {}
                for code in no_index_codes:
                    code_to_key[code] = code  # 无指数记录，用自身代码分组
                for code in candidate_list:
                    if code not in code_to_key and all_index_df is not None:
                        rows = all_index_df[all_index_df['code'] == code]
                        if not rows.empty:
                            r = rows.sort_values('start_date', ascending=False).iloc[0]
                            k = r['traced_index_code'] or r['traced_index_name'] or code
                            code_to_key[code] = k

                index_groups = {}
                for code in qualified.index:
                    key = code_to_key.get(code, code)
                    if key not in index_groups:
                        index_groups[key] = []
                    index_groups[key].append((code, qualified[code]))

                # 每组保留流动性最佳
                g.merged_etf_pool = [sorted(items, key=lambda x: x[1], reverse=True)[0][0]
                                     for items in index_groups.values()]
                log.info(f"【走弱期池】流动性过滤+分组后: {len(g.merged_etf_pool)}只（{len(index_groups)}组）")
        except Exception as e:
            log.warning(f"【走弱期】异常: {e}，使用原始全球池")
            g.merged_etf_pool = list(g.global_etf_pool)
    else:
        log.info(f"🟢 【正常期】更新动态池...")
        update_sector_pool(context)
        g.merged_etf_pool = list(getattr(g, 'dynamic_etf_pool', []))
        log.info(f"【正常期池】动态池: {len(g.merged_etf_pool)}只")
    log.info("⏸️ 【早盘流水线】执行完毕！")


# ============================================================
# 午盘流水线（13:10）：确定最终用于计算动量的ETF池，并计算排序
# ============================================================
def afternoon_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【午盘流水线】启动...")
    log.info(f"【午盘池】使用合并池，共{len(g.merged_etf_pool)}只")
    log.info("【动量计算】计算ETF动量得分与排序...")
    calculate_and_log_ranked_etfs(context)
    log.info("⏸️ 【午盘流水线】执行完毕！")


# ============================================================
# 卖出流水线（13:10）：卖出不在目标列表中的持仓
# ============================================================
def sell_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【卖出流水线】启动...")
    execute_sell_trades(context)
    log.info("⏸️ 【卖出流水线】执行完毕！")


# ============================================================
# 买入流水线（13:10）：按目标列表买入目标ETF
# ============================================================
def buy_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【买入流水线】启动...")
    execute_buy_trades(context)
    log.info("⏸️ 【买入流水线】执行完毕！")


# ============================================================
# 收盘后重置缓存，避免跨日数据污染
# ============================================================
def reset_daily_flags(context):
    g.cache_date = None
    g.yesterday_close_cache = {}
    log.info("🔄 收盘缓存重置完成")


# ============================================================
# 检查当前持仓状态，打印每只持仓的名称、数量、成本、当前价
# 若ETF停牌，也做记录
# ============================================================
def check_positions(context):
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 【持仓检查】{security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")


# ============================================================
# 回撤监控：记录当前净值与历史最高净值的回撤，达到阈值时记录并输出预警
# ============================================================
def monitor_drawdown(context):
    try:
        current_value = context.portfolio.total_value
        # 更新历史最高净值
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        if g.max_portfolio_value > 0:
            current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
            if current_drawdown >= g.drawdown_threshold:
                record = {
                    'date': context.current_dt.strftime('%Y-%m-%d'),
                    'drawdown': current_drawdown,
                    'portfolio_value': current_value,
                    'max_value': g.max_portfolio_value,
                    'is_weak': False
                }
                positions_info = []
                for security in context.portfolio.positions:
                    position = context.portfolio.positions[security]
                    if position.total_amount > 0:
                        security_name = get_security_name(security)
                        positions_info.append(f"{security_name}:{position.total_amount}股")
                record['positions'] = positions_info
                g.drawdown_records.append(record)
                log.info(f"【回撤预警】回撤达到 {current_drawdown:.2%} (阈值: {g.drawdown_threshold:.0%})")
                log.info(f"  当前净值: {current_value:,.0f}  |  最高净值: {g.max_portfolio_value:,.0f}")
                log.info(f"  大A状态: {'走弱期' if g.is_a_share_weak else '正常期'}")
                log.info(f"  持仓: {', '.join(positions_info) if positions_info else '空仓'}")
    except Exception as e:
        log.error(f"【回撤监控】计算异常: {e}")


# ============================================================
# 计算全市场ETF流动性阈值：
# 取近3个交易日所有场内ETF的日成交额，求均值后除以global_threshold_divisor
# 该阈值用于后续过滤固定池和动态池中的低流动性ETF
# ============================================================
def calculate_global_etf_threshold(context):
    log.info("【全局阈值更新】开始计算全市场ETF流动性门槛")
    try:
        # 获取当前日期所有场内ETF列表
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            log.warning("未找到任何场内ETF，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        log.info(f"全市场ETF总数: {len(etf_list)}只")
        # 取前3个交易日（不含今天）
        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]
        # 获取成交额数据
        df = get_price(security=etf_list, start_date=start_day, end_date=context.previous_date, frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or df.empty:
            log.warning("无法获取历史成交额数据，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        # 按日汇总成交额和有效成交ETF数量
        daily_totals = df.groupby('time')['money'].sum()
        daily_counts = df[df['money'] > 0].groupby('time')['code'].nunique()
        for day, money in daily_totals.items():
            count = daily_counts.get(day, 0)
            log.info(f"  {day.date()} 全市场ETF总成交额: {money/1e8:.2f}亿元 ({count}只ETF有成交)")
        # 如果有效交易日不足3天，使用保守阈值
        if len(daily_totals) < 3:
            log.warning(f"仅有{len(daily_totals)}个有效交易日，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        avg_total_money = daily_totals.mean()
        threshold = avg_total_money / g.global_threshold_divisor
        g.avg_etf_money_threshold = threshold
        log.info(f"【全局阈值更新完成】近{len(daily_totals)}日全市场ETF日均总成交额={avg_total_money/1e8:.2f}亿元，阈值={threshold/1e4:.0f}万元({threshold:,.0f}元)")
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}，使用保守阈值1000万")
        g.avg_etf_money_threshold = 10000000


# 固定池过滤及合并函数已移除，完全采用动态池


# ============================================================
# 动态行业池更新：
# 1. 从全市场ETF中剔除债券、货币、混合等不属于行业或指数的ETF。
# 2. 基金跟踪相同指数的视为同一行业，归入同一个分组。
# 3. 在每个分组中，按近3日日均成交额保留流动性最佳的一只ETF。
# 4. 最终按成交额排序取前300只作为动态池。
# ============================================================

def update_sector_pool(context):
    log.info("【动态池更新】开始执行")
    if g.avg_etf_money_threshold is None:
        log.info("【动态池更新】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)

    try:
        df_etf = get_all_securities(['etf'])
        etf_list = df_etf.index.tolist()
        g.etf_names_dict = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"获取全市场ETF列表失败: {e}")
        return

    log.info(f"【动态池更新】全市场ETF总数: {len(etf_list)}只")

    # ============ DB查询：FUND_MAIN_INFO + FUND_INVEST_TARGET ============
    fund_type_map = {}            # main_code(6位) -> underlying_asset_type_id
    fund_full_name_map = {}       # main_code -> 基金全称
    index_map = {}                # code(完整) -> (idx_code, idx_name)
    excluded_count = 0
    excluded_list_no_index = []   # 无跟踪指数排除

    try:
        from jqdata import finance
        main_codes = [code.split('.')[0] for code in etf_list]

        # ---- FUND_MAIN_INFO ----
        fund_query = finance.run_query(
            query(finance.FUND_MAIN_INFO.main_code, finance.FUND_MAIN_INFO.underlying_asset_type_id, finance.FUND_MAIN_INFO.name)
            .filter(finance.FUND_MAIN_INFO.main_code.in_(main_codes))
        )
        if fund_query is not None and not fund_query.empty:
            for _, row in fund_query.iterrows():
                mc = row['main_code']
                fund_type_map[mc] = row['underlying_asset_type_id']
                fund_full_name_map[mc] = row['name']
        log.info(f"【动态池更新】FUND_MAIN_INFO查询成功，共获取{len(fund_type_map)}只基金的类型信息")

        # ---- FUND_INVEST_TARGET ----
        target_query = finance.run_query(
            query(finance.FUND_INVEST_TARGET.code, finance.FUND_INVEST_TARGET.traced_index_code, finance.FUND_INVEST_TARGET.traced_index_name, finance.FUND_INVEST_TARGET.start_date)
            .filter(finance.FUND_INVEST_TARGET.code.in_(etf_list))
        )
        if target_query is not None and not target_query.empty:
            target_query = target_query.sort_values('start_date', ascending=False)
            for _, row in target_query.iterrows():
                code = row['code']
                idx_code = row['traced_index_code']
                idx_name = row['traced_index_name']
                if code not in index_map:
                    index_map[code] = (idx_code, idx_name)
        log.info(f"【动态池更新】FUND_INVEST_TARGET查询成功，共获取{len(index_map)}只ETF的跟踪指数信息")
    except Exception as e:
        log.warning(f"【动态池更新】DB查询异常: {e}")
        g.dynamic_etf_pool = []
        return

    # ========== 遍历ETF：排除 + 分类 ==========
    sector_etf_list = []  # [(code, idx_group_key, money), ...]
    for code in etf_list:
        name = g.etf_names_dict.get(code, str(code))
        code_num = code.split('.')[0]
        is_excluded = False

        # 只保留有跟踪指数的ETF
        if not is_excluded and code not in index_map:
            is_excluded = True
            excluded_list_no_index.append(f"  {code} {name} [{fund_full_name_map.get(code_num, '')}]")
        if is_excluded:
            excluded_count += 1
        else:
            sector_etf_list.append(code)

    if not sector_etf_list:
        log.warning("【动态池更新】无ETF通过筛选")
        g.dynamic_etf_pool = []
        return

    # ========== 流动性数据获取 ==========
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold

    price_data = get_price(sector_etf_list, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
    if price_data is None or price_data.empty:
        log.warning("【动态池更新】无法获取成交额数据")
        g.dynamic_etf_pool = []
        return

    total_money = price_data.groupby('code')['money'].sum()
    avg_daily_money = total_money / TRADE_DAYS_COUNT

    # 流动性过滤（日均成交额 > 阈值）
    qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
    qualified_codes = qualified.index.tolist()
    log.info(f"【动态池更新】流动性过滤后: {len(sector_etf_list)}→{len(qualified_codes)}只")

    if not qualified_codes:
        log.warning("【动态池更新】无ETF通过流动性过滤")
        g.dynamic_etf_pool = []
        return

    # ========== 按跟踪指数分组，每组保留流动性最佳的一只 ==========
    index_groups = {}  # group_key -> [(code, money), ...]
    for code in qualified_codes:
        idx_code, idx_name = index_map[code]
        # 用指数代码分组，无代码时用指数名
        group_key = idx_code if idx_code else (idx_name if idx_name else code)
        if group_key not in index_groups:
            index_groups[group_key] = []
        index_groups[group_key].append((code, qualified[code]))

    final_pool_info = []
    for group_key, items in index_groups.items():
        sorted_items = sorted(items, key=lambda x: x[1], reverse=True)
        final_pool_info.append({
            'code': sorted_items[0][0],
            'money': sorted_items[0][1],
            'index_name': index_map[sorted_items[0][0]][1],
            'index_code': index_map[sorted_items[0][0]][0],
        })

    # 按成交额排序取前300只
    final_pool_info.sort(key=lambda x: x['money'], reverse=True)
    top_300 = final_pool_info[:300]
    g.dynamic_etf_pool = [item['code'] for item in top_300]

    log.info(f"【动态池更新完成】动态池共{len(g.dynamic_etf_pool)}只ETF（按跟踪指数分组，共{len(index_groups)}组）")
    if len(g.dynamic_etf_pool) <= 20:
        for item in top_300[:20]:
            log.info(f"  {item['code']} {g.etf_names_dict.get(item['code'], '')} → {item['index_code']}({item['index_name']}) 日均{item['money']/1e8:.2f}亿")


# 固定池过滤及合并函数已移除，完全采用动态池


# ============================================================
# 计算并记录排序后的ETF：调用get_final_ranked_etfs得到最终目标列表
# ============================================================
def calculate_and_log_ranked_etfs(context):
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.warning("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        return
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list


# ============================================================
# 核心动量得分计算：
# 对过去 lookback_days+1 天的收盘价取对数，做加权线性回归（权重线性递增并平方）。
# 斜率年化得到年化收益率，R²衡量趋势稳健性，最终动量得分 = 年化收益率 × R²。
# 返回：动量得分、年化收益率、R²
# ============================================================
def calculate_momentum_score(price_series, lookback_days):
    if len(price_series) < lookback_days + 1:
        return None, None, None
    # 取最近 lookback_days+1 个收盘价（包含今天）
    recent_price_series = price_series[-(lookback_days + 1):]
    # 对价格取对数，使回归对收益率线性化
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    # 权重线性递增并平方，越近期权重越高
    weights = np.linspace(1, 2, len(y))
    W = weights ** 2
    W_sum = np.sum(W)
    # 加权均值
    x_bar = np.sum(W * x) / W_sum
    y_bar = np.sum(W * y) / W_sum
    dx = x - x_bar
    dy = y - y_bar
    variance_x = np.sum(W * dx**2)
    if variance_x == 0:
        return 0, 0, 0
    # 加权线性回归斜率
    slope = np.sum(W * dx * dy) / variance_x
    intercept = y_bar - slope * x_bar
    # 斜率年化：假设一年250个交易日，对数收益率转普通收益率
    annualized_returns = math.exp(slope * 250) - 1
    y_pred = slope * x + intercept
    # 加权R²
    ss_res = np.sum(weights * (y - y_pred) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0
    # 动量得分 = 年化收益率 × R²（R²惩罚趋势不稳定的ETF）
    momentum_score = annualized_returns * r_squared
    return momentum_score, annualized_returns, r_squared


# ============================================================
# 对单只ETF计算完整指标：动量、R²、均线、成交量比、短期风控
# 返回一个字典，包含所有指标及是否通过各项过滤
# ============================================================
def calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    try:
        # 将当前价格追加到历史收盘价序列末尾
        price_series = np.append(hist_closes, current_price)
        # 若有效数据不足 lookback_days 的80%，跳过
        if len(price_series) < g.lookback_days * 0.8:
            return None
        # 计算动量得分
        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_series, g.lookback_days)
        if momentum_score is None:
            return None
        # 动量得分是否在允许范围内
        passed_momentum = (g.min_score_threshold <= momentum_score <= g.max_score_threshold)
        # 计算成交量比
        volume_ratio = get_volume_ratio(hist_volumes, today_vol, context, g.volume_lookback)

        # 短期风控：近3日任意一日跌幅是否超过3%
        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False

        # R²过滤：正常期要求趋势稳健
        passed_r2 = r_squared > g.r2_threshold

        # 均线过滤：走弱期要求当前价站上均线
        passed_ma = True
        ma_value = None
        if len(price_series) >= g.ma_lookback:
            ma_value = np.mean(price_series[-g.ma_lookback:])
            passed_ma = current_price > ma_value * g.ma_threshold
        else:
            passed_ma = False

        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'passed_momentum': passed_momentum,
            'passed_r2': passed_r2,
            'passed_ma': passed_ma,
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter,
            'ma_value': ma_value,
        }
    except Exception as e:
        log.debug(f"【指标计算】{etf} {etf_name} 计算失败: {e}")
        return None


# ============================================================
# 计算成交量比：
# 根据当前已交易时间，将今日成交量等比放大到全日，再与近lookback_days日平均成交量对比。
# 目的是避免早盘成交量低估导致误判。
# ============================================================
def get_volume_ratio(hist_volumes, today_vol, context, lookback_days=None):
    if lookback_days is None:
        lookback_days = g.volume_lookback
    try:
        if hist_volumes is None or len(hist_volumes) < lookback_days:
            return None
        past_n_days_vol = hist_volumes[-lookback_days:]
        if np.any(np.isnan(past_n_days_vol)) or np.any(past_n_days_vol == 0):
            return None
        avg_volume = np.mean(past_n_days_vol)
        if avg_volume == 0:
            return None
        # 计算当日已过去多少分钟（A股交易时间9:30-11:30, 13:00-15:00，共240分钟）
        now = context.current_dt
        elapsed_minutes = (now.hour - 9) * 60 + now.minute - 30
        if now.hour >= 13:
            elapsed_minutes -= 90
        elapsed_minutes = max(1, min(elapsed_minutes, 240))
        # 将今日成交量按已交易时间比例放大到全日
        projected_today_vol = today_vol * (240.0 / elapsed_minutes)
        return projected_today_vol / avg_volume if avg_volume > 0 else 0
    except Exception:
        return None


# 走弱期判断功能已移除


# ============================================================
# 应用过滤条件：
# - 动量得分过滤：始终启用
# - R²过滤：仅在正常期启用
# - 均线过滤：仅在走弱期启用
# - 成交量过滤：始终启用
# - 短期风控（近3日跌幅）：始终启用
# ============================================================
def apply_filters(metrics_list):
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], True),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter),
        ('均线', lambda m: m['passed_ma'], g.enable_ma_filter),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
    ]
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered


# ============================================================
# 核心函数：计算合并池中所有ETF的动量得分，并分四步确定最终目标持仓：
# 第一步：所有ETF按动量得分排序（日志输出前100名）
# 第二步：应用过滤条件，选出符合全部条件的ETF（输出前10名）
# 第三步：确定候选池（得分≥第holdings_name名得分×score_threshold_ratio）
# 第四步：结合当前持仓，保留仍在候选池中的持仓，必要时补充新ETF
# ============================================================
def get_final_ranked_etfs(context):
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = context.previous_date
    log.info(f"【动量得分计算】使用合并池，合计{len(etf_set)}只ETF")
    log.info(f"【当前状态】正常期（走弱期判断已移除）")
    # 计算所需历史数据长度，确保有足够数据用于动量、成交量、均线计算
    lookback = max(g.lookback_days, g.volume_lookback, g.ma_lookback) + 20
    today = context.current_dt.date()
    current_data = get_current_data()
    safe_lookback = lookback + 20
    # 获取历史日线收盘价和成交量
    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d', fields=['close', 'volume'], panel=False)
    # 获取今日分钟线成交量，用于计算成交量比
    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        log.warning("【动量计算】无法获取历史价格数据")
        return []
    # 汇总今日成交量
    today_vols = today_vol_df.groupby('code')['volume'].sum() if (today_vol_df is not None and not today_vol_df.empty) else pd.Series(dtype=float)
    # 透视表：日期为行，ETF代码为列
    close_pivot = hist_df.pivot(index='time', columns='code', values='close')
    volume_pivot = hist_df.pivot(index='time', columns='code', values='volume')

    # ========== 遍历ETF计算动量得分 ==========
    for etf in etf_set:
        # 跳过全天停牌或盘中临时停牌的ETF
        if current_data[etf].paused:
            continue
        if is_temporarily_suspended(etf, context):
            log.debug(f"{etf} {get_security_name(etf)} 盘中临时停牌，跳过计算")
            continue
        if etf not in close_pivot.columns:
            continue
        raw_closes = close_pivot[etf].values
        raw_volumes = volume_pivot[etf].values
        # 只保留成交量有效（非零、非NaN）的交易日
        valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)
        hist_closes = raw_closes[valid_mask]
        hist_volumes = raw_volumes[valid_mask]
        hist_closes = hist_closes[-lookback:]
        hist_volumes = hist_volumes[-lookback:]
        if len(hist_closes) < g.lookback_days:
            continue
        etf_name = get_security_name(etf)
        current_price = current_data[etf].last_price
        today_vol = today_vols.get(etf, 0)
        # 计算完整指标
        metrics = calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
        if metrics:
            # 去重：同一个ETF只保留一次
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                continue
            all_metrics.append(metrics)

    # 处理NaN动量得分：转为负无穷，避免排序出错
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')

    # 按动量得分排序
    all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)

    # ========== 第一步：输出所有ETF排序表格 ==========
    log_buffer = []
    log_buffer.append("")
    log_buffer.append(">>> 第一步：所有ETF按动量得分从大到小排序 <<<")
    for m in all_metrics[:100]:
        def fmt_status(value_str, passed):
            return f"{value_str} {'✅' if passed else '❌'}"
        score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
        r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
        vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
        min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
        loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
        ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
        line = (
            f"{m['etf']} {m['etf_name']}: "
            f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
            f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
            f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
            f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
            f"短期风控: {fmt_status(loss_val, m['passed_loss'])}"
        )
        log_buffer.append(line)

    # ========== 第二步：应用过滤条件 ==========
    filtered_list = apply_filters(all_metrics)
    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    top_10 = filtered_list[:10]
    log_buffer.append("")
    log_buffer.append(">>> 第二步：符合全部过滤条件的ETF按动量得分从大到小排序(前10名) <<<")
    if top_10:
        for m in top_10:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
                f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
                f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
                f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
                f"短期风控: {fmt_status(loss_val, m['passed_loss'])}"
            )
            log_buffer.append(line)
    else:
        log_buffer.append("（无符合条件的ETF）")
        full_log = "\n".join(log_buffer)
        log.info(full_log)
        return []

    # ========== 第三步：确定候选池 ==========
    score_key = 'momentum_score'
    if len(top_10) >= g.holdings_num:
        # 以第holdings_num名的得分为参考
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        # 正常期使用score_threshold_ratio；走弱期使用1.0（只取前holdings_num名）
        ratio = g.score_threshold_ratio
        score_threshold = reference_score * ratio
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：选取动量得分≥第{g.holdings_num}名({top_10[g.holdings_num - 1]['etf_name']})得分{reference_score:.4f}×{g.score_threshold_ratio}={score_threshold:.4f}的ETF <<<")
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：前10名不足{g.holdings_num}只，全部作为候选池 <<<")
        candidate_pool = top_10[:]

    log_buffer.append(f"【候选池】共{len(candidate_pool)}只ETF（按动量得分排序）：")
    for i, item in enumerate(candidate_pool):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")

    # ========== 第四步：结合当前持仓进行调整 ==========
    log_buffer.append("")
    log_buffer.append(">>> 第四步：结合当前持仓进行调整 <<<")
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    log_buffer.append(f"当前持仓ETF：{current_holdings}")
    candidate_dict = {item['etf']: item for item in candidate_pool}
    # 保留仍在候选池中的当前持仓
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    log_buffer.append(f"其中存在于候选池中的持仓ETF：{[item['etf'] for item in retained]}")
    if len(retained) >= g.holdings_num:
        # 若保留的持仓已足够，按动量得分取前holdings_num名
        retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
        log_buffer.append(f"保留的持仓ETF数量({len(retained)})超过目标持仓数({g.holdings_num})，将从保留的ETF中按动量得分取前{g.holdings_num}只作为最终目标。")
    else:
        # 保留持仓，从候选池补充差额
        need = g.holdings_num - len(retained)
        remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
        additional = remaining_pool[:need]
        final_result = retained + additional
        log_buffer.append(f"保留持仓ETF {len(retained)}只，还需补充{need}只。")
        if retained:
            log_buffer.append("保留的ETF（按原有顺序）：")
            for item in retained:
                log_buffer.append(f"  {item['etf_name']}({item['etf']})")
        if additional:
            log_buffer.append("补充的ETF（按动量得分排序）：")
            for i, item in enumerate(additional):
                log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")

    
    log_buffer.append(f"【最终目标】共{len(final_result)}只ETF：")
    for i, item in enumerate(final_result):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']})")
    log_buffer.append("==================================================")
    full_log = "\n".join(log_buffer)
    log.info(full_log)
    return final_result


# ============================================================
# 执行卖出：
# 1. 若动量排序结果非空，取前holdings_num名作为目标。
# 2. 若排序结果为空但防御性ETF可用，则目标为防御性ETF。
# 3. 若防御性ETF也不可用，则空仓。
# 4. 卖出所有不在目标列表中的当前持仓。
# ============================================================
def execute_sell_trades(context):
    log.info("========== 卖出操作开始 ==========")

    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    target_etfs = []
    for metrics in ranked_etfs[:g.holdings_num]:
        target_etfs.append(metrics['etf'])
        log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}")

    g.target_etfs_list = target_etfs
    current_positions = list(context.portfolio.positions.keys())
    target_set = set(target_etfs)
    sell_count = 0

    for security in current_positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            success = smart_order_target_value(security, 0, context)
            if success:
                sell_count += 1
                log.info(f"✅ 已成功卖出: {security} {security_name}")

    log.info(f"本次共计划卖出{sell_count}只ETF。")
    log.info("========== 卖出操作完成 ==========")


# ============================================================
# 执行买入：
# 1. 只买入目标列表中当前未持仓的ETF。
# 2. 控制总持仓不超过holdings_num只。
# 3. 动态分配剩余现金：每只ETF平分剩余现金，最后一笔可取全部剩余。
# 4. 若现金不足最小交易额，停止买入。
# ============================================================
def execute_buy_trades(context):
    log.info("========== 买入操作开始 ==========")
    target_etfs = g.target_etfs_list

    if not target_etfs:
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        log.info("========== 买入操作完成 ==========")
        return

    current_positions = set(context.portfolio.positions.keys())
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)

    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        log.info("========== 买入操作完成 ==========")
        return

    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    log.info(f"当前实际持仓: {actual_holding_count}只, 目标持仓: {g.holdings_num}只, 本次计划买入: {num_etfs_to_buy}只")

    # 动态分配资金：每次买入时将剩余现金平均分配给还未买入的ETF
    for i, etf in enumerate(etfs_to_buy):
        remaining_cash = context.portfolio.available_cash
        if remaining_cash < g.min_money:
            log.info(f"可用现金 {remaining_cash:.2f} 不足最小交易额 {g.min_money:.2f}，停止买入")
            break

        remaining_to_buy = len(etfs_to_buy) - i
        target_value_for_this_etf = remaining_cash // remaining_to_buy

        # 最后一笔可使用剩余全部现金，但确保不小于最小交易额
        if target_value_for_this_etf < g.min_money and remaining_cash >= g.min_money:
            target_value_for_this_etf = remaining_cash

        log.info(f"为 {etf} 分配目标金额: {target_value_for_this_etf:.2f} 元 (剩余现金 {remaining_cash:.2f}, 待买数量 {remaining_to_buy})")

        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
        else:
            log.info(f"❌ ETF {etf} 下单失败")

    log.info("========== 买入操作完成 ==========")


# ============================================================
# 判断ETF是否盘中临时停牌：
# 通过检查最近N分钟是否有成交量来判断，若无成交则视为临时停牌
# ============================================================
def is_temporarily_suspended(security, context, minute_count=10):
    """
    判断ETF是否盘中临时停牌
    通过检查最近N分钟是否有成交来判断，若无成交则视为临时停牌
    """
    try:
        # 获取最近N分钟的分钟线数据
        minute_data = get_price(
            security,
            end_date=context.current_dt,
            count=minute_count,
            frequency='1m',
            fields=['volume'],
            skip_paused=False,
            fq='pre'
        )
        # 无数据或数据为空，视为停牌
        if minute_data is None or minute_data.empty:
            return True
        # 最近N分钟成交量都为0，视为临时停牌
        if (minute_data['volume'] == 0).all():
            return True
        return False
    except Exception as e:
        log.debug(f"临时停牌检测异常 {security}: {e}")
        return False  # 异常时默认认为正常，避免误判


# ============================================================
# 智能下单函数：根据目标市值调整持仓
# 处理停牌、涨跌停、最小交易金额、T+1、滑点、佣金等实际情况
# ===========================================================
def smart_order_target_value(security, target_value, context):
    """
    智能下单：根据目标市值调整持仓，处理停牌、涨跌停、最小交易金额、T+1
    """
    data = get_current_data()
    name = get_security_name(security)
    # ========== 1. 全天停牌检测 ==========
    if data[security].paused:
        log.info(f"{security} {name} 全天停牌，跳过交易")
        return False
    # ========== 2. 盘中临时停牌检测 ==========
    if is_temporarily_suspended(security, context):
        log.info(f"{security} {name} 盘中临时停牌，跳过交易")
        return False
    price = data[security].last_price
    if price == 0:
        log.info(f"{security} {name} 当前价格为0，跳过交易")
        return False
    # ========== 3. 买入时使用预估成交价（包含佣金+滑点）计算股数 ==========
    if target_value > 0:
        buy_commission_rate = 0.0001   # 买入佣金
        slippage_rate = 0.0001         # 滑点
        estimated_price = price * (1 + buy_commission_rate + slippage_rate)
        target_amount = int(target_value / estimated_price)
        target_amount = (target_amount // 100) * 100  # ETF买卖单位为100份整数倍
        if target_amount <= 0:
            target_amount = 100
        # 二次校验：用实时可用现金和当前价格严格限制（兜底）
        max_shares = int(context.portfolio.available_cash / price)
        max_shares = (max_shares // 100) * 100
        if max_shares < target_amount:
            target_amount = max_shares
        if target_amount <= 0:
            log.info(f"{security} {name}: 现金不足买100股，跳过")
            return False
    else:
        target_amount = 0
    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount
    # ========== 4. 涨跌停检测（统一：涨停跌停都不交易） ==========
    if data[security].last_price >= data[security].high_limit:
        log.info(f"{security} {name} 当前涨停，跳过交易")
        return False
    if data[security].last_price <= data[security].low_limit:
        log.info(f"{security} {name} 当前跌停，跳过交易")
        return False
    trade_val = abs(diff) * price
    if 0 < trade_val < g.min_money:
        log.info(f"{security} {name} 交易金额{trade_val:.2f} < {g.min_money}，跳过")
        return False
    # ========== 5. T+1检查（仅卖出时） ==========
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            log.info(f"{security} {name} 当天买入不可卖出(T+1)")
            return False
        diff = -min(abs(diff), closeable)
    # ========== 6. 执行下单 ==========
    if diff != 0:
        order_result = order(security, diff)
        if order_result:
            if diff > 0:
                log.info(f"📥 买入 {security} {name} 数量{abs(diff)} 价格{price:.3f} (预估含成本价: {estimated_price:.3f})")
            else:
                log.info(f"📤 卖出 {security} {name} 数量{abs(diff)} 价格{price:.3f}")
            return True
        else:
            log.warning(f"下单失败: {security} {name}，数量{diff}")
            return False
    return False


# ============================================================
# 分钟级固定比例止损：
# 在指定交易时段内（避开开盘和收盘极端波动），检查持仓成本价与最新价。
# 若最新价 <= 成本价 × 0.95，则触发止损卖出。
# ============================================================
def minute_level_stop_loss(context):
    if not g.use_fixed_stop_loss:
        return
    current_time = context.current_dt.strftime('%H:%M')
    # 仅在以下时段执行：9:40-11:30, 13:00-14:55
    if not (('09:40' < current_time < '11:30') or ('13:00' < current_time < '14:55')):
        return
    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        # 只检查可卖出的持仓（非当日买入）
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        cost_price = position.avg_cost
        if cost_price <= 0:
            continue
        # 触发固定比例止损
        if current_price <= cost_price * g.fixedStopLossThreshold:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"🚨 【分钟级固定止损】{security} {security_name} 触发止损，亏损: {loss_percent:.2f}%")
            smart_order_target_value(security, 0, context)


# ============================================================
# 获取ETF名称：优先使用缓存字典，否则调用聚宽API
# ============================================================
def get_security_name(security):
    try:
        if hasattr(g, 'etf_names_dict') and security in g.etf_names_dict:
            return g.etf_names_dict[security]
        return get_security_info(security).display_name
    except Exception:
        return "未知名称"


# ============================================================
# 策略回测框架中的trade函数，本策略未使用
# ============================================================
def trade(context):
    pass
