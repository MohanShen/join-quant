# Clone from JoinQuant
# postId: b48567e7becbcbe3adb5af45e4ef189d
# backtestId: 13669b38df31f2ad9e70853f017a3945
# title: 小市值的流动性问题

# 导入聚宽核心库
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import datetime

# ==================================================
# 【新增：中小板选股核心配置（可修改）】
# ==================================================
MARKET_INDEX = '399101.XSHE'  # 选股范围：中小板指（固定）
MARKET_CAP_MIN = 5  # 最小市值（亿元），可修改
MARKET_CAP_MAX = 500  # 最大市值（亿元），可修改
MONTH_POOL_MULTIPLE = 200  # 月度池数量=目标持仓数*N，可修改（建议10-30）
CANDIDATE_MULTIPLE = 30  # 候选池数量=目标持仓数*N，可修改（建议2-5）


def initialize(context):
    """策略初始化：保留原框架+新增月度选股变量"""
    # 1. 基础策略配置（不变）
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_benchmark('000300.XSHG')
    set_slippage(FixedSlippage(0))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                             open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='stock')
    log.set_level('order', 'error')

    # 2. 全局基础变量（原变量+新增月度选股变量）
    g.stock_num = 5  # 最终目标持仓数（核心参数，可修改）
    g.hold_list = []
    g.yesterday_HL_list = []  # 昨日涨停持仓
    g.loss_blacklist = {}
    g.signals = []
    g.limitup_stocks = []     # 当日涨停开板股票
    g.sell_reason = ''        # 卖出原因记录
    g.etf = '511990.XSHG'     # 货币ETF（空仓月份持有）
    # 新增：月度选股变量
    g.month_scope = []  # 月度股票池（每月1号更新）
    g.daily_orders = {}  # 当日订单记录（用于成交方向判断）

    # ==================================================
    # 【风控核心参数（不变，可修改）】
    # ==================================================
    g.empty_months = [1]          # 1月、12月空仓（可修改）
    g.stoploss_strategy = 3          # 复合止损策略（1=个股，2=大盘，3=两者）
    g.stoploss_single = 0.15         # 个股止损阈值（6%，可修改）
    g.stoploss_market = 0.04         # 大盘止损阈值（5%，可修改）
    g.take_profit_single = 2.0       # 个股止盈阈值（100%，可修改）
    g.market_index = '000300.XSHG'   # 大盘止损参考指数（沪深300，可修改）

    # ==================================================
    # 【原有：三轮因子筛选参数（保留结构，可配置）】
    # ==================================================
    # 第一轮筛选：基础财务+风险因子（可根据需求配置）
    g.factor_list_1 = [
        # 'debt_to_asset_ratio',  # 资产负债率（越小越好，方向-1）
        # 'net_profit_to_revenue_ratio',  # 净利润率（越大越好，方向1）
        # 'current_ratio'  # 流动比率（越大越好，方向1）
    ]
    g.factor_direction_1 = []  # 因子方向（1=越大越好，-1=越小越好）
    g.coef_list_1 = []       # 因子权重
    g.factor_num_1 = 100               # 第一轮最大取100只
    g.factor_ranges_1 = {}  # 因子范围过滤（如：{'debt_to_asset_ratio': (0, 0.8)}）

    # 第二轮筛选：成长+波动因子（可配置）
    g.factor_list_2 = [
        # 'operating_revenue_growth_ratio',  # 营收增长率（越大越好）
        # 'net_profit_growth_ratio'  # 净利润增长率（越大越好）
    ]
    g.factor_direction_2 = []
    g.coef_list_2 = []
    g.factor_num_2 = 30            # 第二轮最大取30只

    # 第三轮筛选：量能+估值因子（可配置）
    g.factor_list_3 = [
        # 'turnover_ratio',  # 换手率（量能，越大越好）
        # 'PEG',  # 估值（越小越好）
        # 'market_cap'  # 市值（小市值优先，方向-1）
    ]
    g.factor_direction_3 = []
    g.coef_list_3 = []
    g.factor_num_3 = 6                 # 第三轮最大取6只

    # 3. 运行时间配置（原任务+新增月度选股任务）
    run_monthly(filter_monthly, 1, time='9:00', reference_security='399101.XSHE')  # 每月1号月度选股
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')  # 持仓准备
    run_weekly(daily_adjustment,weekday=4, time='9:30', reference_security='000300.XSHG')  # 每周一调仓
    run_daily(check_limit_up, time='14:00', reference_security='000300.XSHG')  # 涨停开板处理
    run_daily(stoploss_check, time='10:00', reference_security='000300.XSHG')  # 止损止盈检查
    run_daily(close_account, time='14:50', reference_security='000300.XSHG')   # 空仓月份尾盘清仓
    run_daily(check_remain_cash, time='14:30', reference_security='000300.XSHG')  # 止损后资金再平衡
    run_daily(print_position_info, time='15:10', reference_security='000300.XSHG')  # 当日总结


# ==================================================
# 【新增：月度选股核心逻辑（可修改参数，无需改代码）】
# ==================================================
def filter_monthly(context):
    """月度选股：从中小板指筛选5-300亿市值股票，小市值优先"""
    log.info("="*50 + "【月度选股】开始" + "="*50)
    # 1. 构建基本面查询：中小板指成分股+市值5-300亿+按市值升序
    q = query(
        valuation.code,
        valuation.market_cap  # 保留市值字段，用于后续排序
    ).filter(
        valuation.code.in_(get_index_stocks(MARKET_INDEX)),  # 仅中小板指成分股
        valuation.market_cap.between(MARKET_CAP_MIN, MARKET_CAP_MAX)  # 市值范围
    ).order_by(
        valuation.market_cap.asc()  # 小市值优先（核心逻辑）
    )

    # 2. 执行查询，获取月度股票池
    try:
        fund_df = get_fundamentals(q, date=context.previous_date)
        if fund_df.empty:
            log.warning("【月度选股】无符合条件股票，沿用上月池")
            return
        # 取前N*20只（N=目标持仓数），确保后续筛选有足够候选
        pool_size = g.stock_num * MONTH_POOL_MULTIPLE
        g.month_scope = fund_df['code'].head(pool_size).tolist()
        # 打印月度池信息
        log.info(f"【月度选股】中小板指成分股总数：{len(get_index_stocks(MARKET_INDEX))}只")
        log.info(f"【月度选股】市值{MARKET_CAP_MIN}-{MARKET_CAP_MAX}亿股票数：{len(fund_df)}只")
        log.info(f"【月度选股】月度池数量：{len(g.month_scope)}只（目标持仓数*{MONTH_POOL_MULTIPLE}）")
        log.info(f"【月度选股】月度池前5只：{g.month_scope[:5]}...")
    except Exception as e:
        log.error(f"【月度选股】执行失败：{str(e)}，沿用上月池")
    log.info("="*50 + "【月度选股】结束" + "="*50)


def filter_stocks(context, stock_list):
    """基础过滤：剔除ST、次新股、涨跌停等（整合新代码逻辑）"""
    if not stock_list:
        return []
    current_data = get_current_data()
    # 获取最新1分钟收盘价（判断涨跌停）
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    filtered = []

    for stock in stock_list:
        data = current_data[stock]
        # 1. 剔除停牌股
        if data.paused:
            continue
        # 2. 剔除ST/退市股
        if data.is_st or '退' in data.name:
            continue
        # 3. 剔除创业板（30）、科创板（68）、北交所（4/8）
        if stock.startswith(('30', '68', '4', '8')):
            continue
        # 4. 剔除未持仓的涨停/跌停股（避免追高/无法买入）
        if stock not in g.hold_list:
            if last_prices[stock].iloc[-1] >= data.high_limit:  # 涨停
                continue
            if last_prices[stock].iloc[-1] <= data.low_limit:  # 跌停
                continue
        # 5. 剔除次新股（上市不满375天，比原365天更严格）
        listing_date = get_security_info(stock).start_date
        if (context.previous_date - listing_date).days < 375:
            continue
        # 6. 剔除亏损黑名单股票
        if stock in g.loss_blacklist and g.loss_blacklist[stock] > context.current_dt.date():
            continue

        filtered.append(stock)
    log.info(f"【基础过滤】输入{len(stock_list)}只 → 输出{len(filtered)}只")
    return filtered


# ==================================================
# 【原有函数：保留框架，修改选股入口为月度池】
# ==================================================
def prepare_stock_list(context):
    """持仓准备：修复参数+新增订单重置"""
    # 1. 更新持仓、昨日涨停
    g.hold_list = [pos.security for pos in context.portfolio.positions.values()]
    log.info(f"【持仓准备】当前持仓数：{len(g.hold_list)}，列表：{g.hold_list}")

    if g.hold_list:
        # 修复：get_price用security参数
        df = get_price(
            security=g.hold_list,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1,
            panel=False
        )
        g.yesterday_HL_list = list(df[df['close'] == df['high_limit']]['code']) if not df.empty else []
    else:
        g.yesterday_HL_list = []
    log.info(f"【持仓准备】昨日涨停持仓数：{len(g.yesterday_HL_list)}，列表：{g.yesterday_HL_list}")

    # 2. 重置变量
    g.limitup_stocks = []
    g.daily_orders = {}  # 重置当日订单记录

    # 3. 检查可交易状态（非空仓月）
    g.tradable = context.current_dt.month not in g.empty_months
    log.info(f"【持仓准备】当前月份{context.current_dt.month}，可交易状态：{g.tradable}（空仓月：{g.empty_months}）")

    # 4. 清理过期黑名单
    current_date = context.current_dt.date()
    expired_stocks = [(code, ban_end) for code, ban_end in g.loss_blacklist.items() if ban_end <= current_date]
    for code, ban_end in expired_stocks:
        del g.loss_blacklist[code]
        log.info(f"【亏损黑名单】{code}（{get_security_info(code).name}）禁止期结束（{ban_end}），移除")


def get_stock_list(context):
    """核心选股：入口改为月度池+保留后续筛选逻辑"""
    yesterday = context.previous_date
    current_date = context.current_dt.date()

    # ==================================================
    # 【修改：第一轮筛选 → 从月度池开始（原多指数逻辑替换）】
    # ==================================================
    log.info("="*50 + "【第一轮筛选：月度池基础过滤】" + "="*50)
    # 1. 若月度池为空，尝试重新获取
    if not g.month_scope:
        log.warning("【第一轮筛选】月度池为空，临时执行月度选股")
        filter_monthly(context)
        if not g.month_scope:
            log.error("【第一轮筛选】无月度池，终止选股")
            return []
    # 2. 基础过滤（剔除ST、次新股等）
    initial_list = filter_stocks(context, g.month_scope)
    if not initial_list:
        log.warning("【第一轮筛选】过滤后无股票，终止选股")
        return []

    # 3. 再次按市值筛选（确保市值在范围内）
    q = query(
        valuation.code,
        valuation.market_cap
    ).filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(MARKET_CAP_MIN, MARKET_CAP_MAX)
    ).order_by(
        valuation.market_cap.asc()  # 仍按小市值优先
    )
    fund_df = get_fundamentals(q, date=yesterday)
    if fund_df.empty:
        log.warning("【第一轮筛选】市值过滤后无股票，终止选股")
        return []
    # 取前N*3只作为候选（N=目标持仓数）
    candidate_size = g.stock_num * CANDIDATE_MULTIPLE
    round1_list = fund_df['code'].head(candidate_size).tolist()
    log.info(f"【第一轮筛选】市值排序后候选：{len(round1_list)}只（目标持仓数*{CANDIDATE_MULTIPLE}）")
    log.info(f"【第一轮筛选】候选前5只：{round1_list[:5]}...")

    # ==================================================
    # 【原有：第二轮因子筛选（保留结构，空配置则跳过）】
    # ==================================================
    if g.factor_list_1 and g.factor_direction_1 and g.coef_list_1:
        log.info("\n" + "="*50 + "【第二轮筛选：基础财务+风险因子】" + "="*50)
        try:
            factor_vals = get_factor_values(round1_list, g.factor_list_1, end_date=yesterday, count=1)
        except Exception as e:
            log.error(f"【第二轮筛选】获取因子失败：{str(e)}，沿用第一轮结果")
            round2_list = round1_list[:g.factor_num_2]
        else:
            # 因子处理（归一化、方向调整、得分计算）
            df = pd.DataFrame(index=round1_list, columns=g.factor_list_1)
            for factor in g.factor_list_1:
                if factor not in factor_vals or factor_vals[factor].empty:
                    log.warning(f"【第二轮筛选】因子{factor}无数据，沿用第一轮结果")
                    round2_list = round1_list[:g.factor_num_2]
                    break
                df[factor] = factor_vals[factor].T.iloc[:, 0].values
            else:
                df = df.dropna()
                if len(df) < g.factor_num_2:
                    log.warning(f"【第二轮筛选】有效股票不足，沿用第一轮结果")
                    round2_list = round1_list[:g.factor_num_2]
                else:
                    # 归一化+方向调整
                    df_norm = (df - df.min()) / (df.max() - df.min() + 1e-8)
                    for i, (factor, dir) in enumerate(zip(g.factor_list_1, g.factor_direction_1)):
                        if dir == -1:
                            df_norm[factor] = 1 - df_norm[factor]
                    # 计算得分
                    df_norm['score'] = 0
                    for factor, weight in zip(g.factor_list_1, g.coef_list_1):
                        df_norm['score'] += df_norm[factor] * weight
                    # 取前N只
                    round2_list = df_norm.sort_values('score', ascending=False).index[:g.factor_num_2].tolist()
        log.info(f"【第二轮筛选】最终候选：{len(round2_list)}只")
    else:
        log.info("\n【第二轮筛选】未配置因子，直接沿用第一轮结果")
        round2_list = round1_list[:g.factor_num_2]

    # ==================================================
    # 【原有：第三轮因子筛选（保留结构，空配置则跳过）】
    # ==================================================
    if g.factor_list_2 and g.factor_direction_2 and g.coef_list_2:
        log.info("\n" + "="*50 + "【第三轮筛选：成长+波动因子】" + "="*50)
        if len(round2_list) < g.factor_num_3:
            log.warning(f"【第三轮筛选】候选不足，沿用第二轮结果")
            round3_list = round2_list
        else:
            try:
                factor_vals = get_factor_values(round2_list, g.factor_list_2, end_date=yesterday, count=1)
            except Exception as e:
                log.error(f"【第三轮筛选】获取因子失败：{str(e)}，沿用第二轮结果")
                round3_list = round2_list[:g.factor_num_3]
            else:
                # 同第二轮因子处理逻辑
                df = pd.DataFrame(index=round2_list, columns=g.factor_list_2)
                for factor in g.factor_list_2:
                    if factor not in factor_vals or factor_vals[factor].empty:
                        log.warning(f"【第三轮筛选】因子{factor}无数据，沿用第二轮结果")
                        round3_list = round2_list[:g.factor_num_3]
                        break
                    df[factor] = factor_vals[factor].T.iloc[:, 0].values
                else:
                    df = df.dropna()
                    if len(df) < g.factor_num_3:
                        round3_list = df.index.tolist()
                    else:
                        df_norm = (df - df.min()) / (df.max() - df.min() + 1e-8)
                        for i, (factor, dir) in enumerate(zip(g.factor_list_2, g.factor_direction_2)):
                            if dir == -1:
                                df_norm[factor] = 1 - df_norm[factor]
                        df_norm['score'] = 0
                        for factor, weight in zip(g.factor_list_2, g.coef_list_2):
                            df_norm['score'] += df_norm[factor] * weight
                        round3_list = df_norm.sort_values('score', ascending=False).index[:g.factor_num_3].tolist()
        log.info(f"【第三轮筛选】最终候选：{len(round3_list)}只")
    else:
        log.info("\n【第三轮筛选】未配置因子，直接沿用第二轮结果")
        round3_list = round2_list[:g.factor_num_3]

    # ==================================================
    # 【原有：第四轮因子筛选（保留结构，空配置则跳过）】
    # ==================================================
    if g.factor_list_3 and g.factor_direction_3 and g.coef_list_3:
        log.info("\n" + "="*50 + "【第四轮筛选：量能+估值因子】" + "="*50)
        if len(round3_list) < g.stock_num:
            log.warning(f"【第四轮筛选】候选不足，沿用第三轮结果")
            final_list = round3_list
        else:
            try:
                factor_vals = get_factor_values(round3_list, g.factor_list_3, end_date=yesterday, count=1)
            except Exception as e:
                log.error(f"【第四轮筛选】获取因子失败：{str(e)}，沿用第三轮结果")
                final_list = round3_list[:g.stock_num]
            else:
                # 同前序因子处理逻辑
                df = pd.DataFrame(index=round3_list, columns=g.factor_list_3)
                for factor in g.factor_list_3:
                    if factor not in factor_vals or factor_vals[factor].empty:
                        log.warning(f"【第四轮筛选】因子{factor}无数据，沿用第三轮结果")
                        final_list = round3_list[:g.stock_num]
                        break
                    df[factor] = factor_vals[factor].T.iloc[:, 0].values
                else:
                    df = df.dropna()
                    if len(df) < g.stock_num:
                        final_list = df.index.tolist()
                    else:
                        df_norm = (df - df.min()) / (df.max() - df.min() + 1e-8)
                        for i, (factor, dir) in enumerate(zip(g.factor_list_3, g.factor_direction_3)):
                            if dir == -1:
                                df_norm[factor] = 1 - df_norm[factor]
                        df_norm['score'] = 0
                        for factor, weight in zip(g.factor_list_3, g.coef_list_3):
                            df_norm['score'] += df_norm[factor] * weight
                        final_list = df_norm.sort_values('score', ascending=False).index[:g.stock_num].tolist()
    else:
        log.info("\n【第四轮筛选】未配置因子，取前N只作为目标股")
        final_list = round3_list[:g.stock_num]

    # ==================================================
    # 【最终选股结果】
    # ==================================================
    final_list = list(set(final_list))  # 去重
    log.info(f"\n" + "="*30 + f"【最终选股结果】" + "="*30)
    log.info(f"目标股列表（{len(final_list)}只）：{final_list}")
    for i, stock in enumerate(final_list, 1):
        stock_name = get_security_info(stock).name
        # 补充市值信息
        cap_q = query(valuation.market_cap).filter(valuation.code == stock)
        cap_df = get_fundamentals(cap_q, date=yesterday)
        cap = cap_df['market_cap'].iloc[0] if not cap_df.empty else '未知'
        log.info(f"  {i}. {stock}（{stock_name}）| 市值{cap}亿元")
    return final_list


# ==================================================
# 【原有辅助函数：修复参数错误，保留所有逻辑】
# ==================================================
def daily_adjustment(context):
    """日度调仓：修复history参数"""
    log.info("=" * 50)
    log.info(f"【日度调仓】开始（{context.current_dt.date()}）")
    current_date = context.current_dt.date()

    # 1. 空仓月份处理
    if not g.tradable:
        log.info(f"【调仓-空仓月份】当前为{context.current_dt.month}月（空仓月），持有货币ETF{g.etf}")
        current_positions = [pos.security for pos in context.portfolio.positions.values()]
        for code in current_positions:
            if code != g.etf:
                close_position(context, context.portfolio.positions[code])
        if g.etf not in current_positions and context.portfolio.available_cash > 0:
            open_position(context, g.etf, context.portfolio.available_cash)
        log.info("【日度调仓】空仓月份处理完成")
        log.info("=" * 50)
        return

    # 2. 清仓黑名单股票
    current_positions = [pos.security for pos in context.portfolio.positions.values()]
    blacklist_pos = [code for code in current_positions if code in g.loss_blacklist and g.loss_blacklist[code] > current_date]
    if blacklist_pos:
        log.info(f"【调仓-黑名单清仓】{len(blacklist_pos)}只股票强制清仓")
        for code in blacklist_pos:
            pos = context.portfolio.positions[code]
            log.info(f"【调仓-黑名单清仓】{code}（{get_security_info(code).name}），禁止至{g.loss_blacklist[code]}")
            close_position(context, pos)
        current_positions = [pos.security for pos in context.portfolio.positions.values()]

    # 3. 获取目标股
    target_list = get_stock_list(context)
    if not target_list:
        log.warning("【调仓】目标股为空，跳过")
        log.info("=" * 50)
        return

    # 4. 过滤目标股（修复history参数：用security_list）
    current_data = get_current_data()
    target_list = [code for code in target_list if not current_data[code].paused]
    # 修复：history用security_list参数
    last_prices = history(1, unit='1m', field='close', security_list=target_list)
    target_list = [code for code in target_list if last_prices[code].iloc[-1] < current_data[code].high_limit]
    target_list = [code for code in target_list if last_prices[code].iloc[-1] > current_data[code].low_limit]
    if not target_list:
        log.warning("【调仓】目标股过滤后为空，跳过")
        log.info("=" * 50)
        return
    log.info(f"【调仓】过滤后目标股：{len(target_list)}只：{target_list}")

    # 5. 卖出非目标股
    for code in current_positions:
        if code not in target_list and code not in g.yesterday_HL_list:
            log.info(f"【调仓-卖出】{code}（不在目标股+非昨日涨停）")
            close_position(context, context.portfolio.positions[code])
        else:
            log.info(f"【调仓-持有】{code}（在目标股或昨日涨停）")

    # 6. 买入目标股
    cash = context.portfolio.available_cash
    if cash <= 0:
        log.warning("【调仓】无可用资金，跳过买入")
        log.info("=" * 50)
        return
    to_buy = [code for code in target_list if code not in current_positions]
    if not to_buy:
        log.info("【调仓】无新增买入股票")
        log.info("=" * 50)
        return

    cash_per_stock = cash / len(to_buy)
    log.info(f"【调仓-买入】需买{len(to_buy)}只，每只计划资金：{cash_per_stock:.2f}元")
    for code in to_buy:
        min_cash = current_data[code].day_open * 100
        if cash_per_stock < min_cash:
            log.warning(f"【调仓-买入失败】{code}资金不足（需{min_cash:.2f}元，实有{cash_per_stock:.2f}元）")
            continue
        log.info(f"【调仓-买入】{code}（{get_security_info(code).name}），资金：{cash_per_stock:.2f}元")
        open_position(context, code, cash_per_stock)

    log.info("【日度调仓】结束")
    log.info("=" * 50)


def check_limit_up(context):
    """涨停检查：不变"""
    log.info("【涨停检查】开始")
    if not g.yesterday_HL_list:
        log.info("【涨停检查】无昨日涨停持仓，跳过")
        return
    current_data = get_current_data()
    for code in g.yesterday_HL_list:
        if code not in [pos.security for pos in context.portfolio.positions.values()]:
            log.info(f"【涨停检查】{code}已不在持仓，跳过")
            continue
        current_close = current_data[code].last_price
        high_limit = current_data[code].high_limit
        if current_close < high_limit:
            log.info(f"【涨停检查】{code}涨停打开（当前{current_close} < 涨停{high_limit}），卖出")
            close_position(context, context.portfolio.positions[code])
            g.limitup_stocks.append(code)
            g.sell_reason = 'limitup'
        else:
            log.info(f"【涨停检查】{code}维持涨停（当前{current_close} = 涨停{high_limit}），持有")


def stoploss_check(context):
    """止损止盈：修复get_price参数"""
    log.info("【止损检查】开始")
    positions = context.portfolio.positions
    if not positions or not g.tradable:
        log.info("【止损检查】无持仓或非交易月，跳过")
        return
    current_data = get_current_data()

    # 1. 个股止损/止盈
    if g.stoploss_strategy in (1, 3):
        stoploss_count = 0
        takeprofit_count = 0
        for stock, pos in positions.items():
            if stock == g.etf:
                continue
            if current_data[stock].paused:
                log.info(f"【止损检查】{stock}停牌，跳过")
                continue
            profit_ratio = (pos.price - pos.avg_cost) / pos.avg_cost
            # 止盈
            if profit_ratio >= g.take_profit_single - 1:
                log.info(f"【止损检查】{stock}止盈触发（盈利{profit_ratio:.2%} ≥ 100%），清仓")
                close_position(context, pos)
                takeprofit_count += 1
                g.sell_reason = 'takeprofit'
            # 止损
            elif profit_ratio <= -g.stoploss_single:
                log.info(f"【止损检查】{stock}止损触发（亏损{profit_ratio:.2%} ≤ -6%），清仓")
                close_position(context, pos)
                g.loss_blacklist[stock] = context.current_dt.date() + datetime.timedelta(days=90)
                stoploss_count += 1
                g.sell_reason = 'stoploss'
        log.info(f"【止损检查】个股处理完成：止盈{takeprofit_count}只，止损{stoploss_count}只")

    # 2. 大盘止损（修复get_price参数：用security）
    if g.stoploss_strategy in (2, 3):
        try:
            index_data = get_price(
                security=g.market_index,  # 修复：用security参数
                end_date=context.previous_date,
                frequency='daily',
                fields=['open', 'close'],
                count=1
            )
            if not index_data.empty:
                market_drop = (index_data['close'].iloc[0] / index_data['open'].iloc[0]) - 1
                if market_drop <= -g.stoploss_market:
                    log.warning(f"【止损检查】大盘止损触发（{g.market_index}日内跌{market_drop:.2%} ≤ -5%），清仓所有股票")
                    for stock, pos in positions.items():
                        if stock != g.etf:
                            close_position(context, pos)
                    g.sell_reason = 'market_stoploss'
        except Exception as e:
            log.error(f"【止损检查】获取大盘数据失败：{str(e)}，跳过大盘止损")


def check_remain_cash(context):
    """资金再平衡：不变"""
    if not g.sell_reason or not g.tradable:
        return
    log.info(f"【资金再平衡】开始（卖出原因：{g.sell_reason}）")

    current_positions = [pos.security for pos in context.portfolio.positions.values()]
    cash = context.portfolio.available_cash

    # 1. 涨停卖出补买
    if g.sell_reason == 'limitup':
        target_list = get_stock_list(context)
        if target_list:
            to_buy = [code for code in target_list if code not in current_positions and code not in g.limitup_stocks]
            if to_buy and cash > 0:
                cash_per_stock = cash / len(to_buy)
                log.info(f"【资金再平衡】涨停卖出后补买：{to_buy}，每只{cash_per_stock:.2f}元")
                for code in to_buy:
                    current_data = get_current_data()
                    if not current_data[code].paused and current_data[code].last_price < current_data[code].high_limit:
                        open_position(context, code, cash_per_stock)
            else:
                log.info(f"【资金再平衡】无合适补买标的或无资金")
        else:
            log.info(f"【资金再平衡】无目标股，无法补买")

    # 2. 止损卖出买ETF
    elif g.sell_reason in ('stoploss', 'market_stoploss'):
        if cash > 0 and g.etf not in current_positions:
            log.info(f"【资金再平衡】止损后持有ETF，投入资金{cash:.2f}元")
            open_position(context, g.etf, cash)

    g.sell_reason = ''
    log.info(f"【资金再平衡】结束")


def close_account(context):
    """尾盘清仓：不变"""
    if g.tradable:
        return
    log.info(f"【尾盘清仓】{context.current_dt.month}月（空仓月），确保无股票持仓")
    current_positions = [pos.security for pos in context.portfolio.positions.values()]
    current_data = get_current_data()
    for code in current_positions:
        if code != g.etf and not current_data[code].paused:
            close_position(context, context.portfolio.positions[code])
            log.info(f"【尾盘清仓】卖出{code}（空仓月强制清仓）")


def open_position(context, security, value):
    """开仓：新增订单记录"""
    order = order_target_value(security, value)
    if order and order.filled > 0:
        name = get_security_info(security).name
        # 记录订单方向
        g.daily_orders[order.order_id] = {'side': 'BUY', 'code': security}
        # 记录信号
        signal = {"date": context.current_dt.date(), "action": "BUY", "code": security, "name": name, "price": order.price, "amount": order.filled}
        g.signals.append(signal)
        log.info(f"[SIGNAL] {signal['date']} | {signal['action']} | {signal['code']}（{signal['name']}）| 价格：{signal['price']:.2f}元 | 数量：{signal['amount']}股")
        return True
    return False


def close_position(context, position):
    """平仓：新增订单记录"""
    security = position.security
    order = order_target_value(security, 0)
    if order and order.filled > 0:
        name = get_security_info(security).name
        # 记录订单方向
        g.daily_orders[order.order_id] = {'side': 'SELL', 'code': security}
        # 记录信号
        signal = {"date": context.current_dt.date(), "action": "SELL", "code": security, "name": name, "price": order.price, "amount": order.filled}
        g.signals.append(signal)
        log.info(f"[SIGNAL] {signal['date']} | {signal['action']} | {signal['code']}（{signal['name']}）| 价格：{signal['price']:.2f}元 | 数量：{signal['amount']}股")
        return True
    return False


def print_position_info(context):
    """当日总结：修复成交记录判断"""
    current_date = context.current_dt.date()
    log.info("\n【1】当日成交记录：")
    trades = get_trades()
    if trades and g.daily_orders:
        for t in trades.values():
            order_id = t.order_id
            if order_id not in g.daily_orders:
                side = "未知"
                code = "未知"
            else:
                side = g.daily_orders[order_id]['side']
                code = g.daily_orders[order_id]['code']
            trade_value = t.price * t.amount
            log.info(f"成交ID：{t.trade_id} | {side} | {code}（{get_security_info(code).name if code != '未知' else '未知'}）| 价格：{t.price:.2f}元 | 数量：{t.amount}股 | 金额：{trade_value:.2f}元")
    elif trades:
        log.info("⚠️ 有成交记录，但未找到对应订单信息")
    else:
        log.info("⚠️ 当日无成交记录")

    log.info("\n【2】当日交易信号汇总（影刀专用）：")
    daily_signals = [s for s in g.signals if str(s["date"]) == str(current_date)]
    if daily_signals:
        for s in daily_signals:
            log.info(f"[SIGNAL] {s['date']} | {s['action']} | {s['code']}（{s['name']}）| 价格：{s['price']:.2f}元 | 数量：{s['amount']}股")
        g.signals = [s for s in g.signals if str(s["date"]) != str(current_date)]
    else:
        log.info("⚠️ 当日无交易信号")

    log.info("\n【3】当前持仓明细（含亏损黑名单检查）：")
    positions = context.portfolio.positions
    current_date = context.current_dt.date()
    ban_period = datetime.timedelta(days=90)
    if positions:
        total_value = 0
        total_profit = 0
        for code, pos in positions.items():
            profit_rate = round(((pos.price / pos.avg_cost) - 1) * 100, 2)
            profit = pos.value - (pos.avg_cost * pos.total_amount)
            total_value += pos.value
            total_profit += profit
            log.info(f"标的：{code}（{get_security_info(code).name}）")
            log.info(f"  - 总仓位：{pos.total_amount}股（可卖出：{pos.closeable_amount}股）")
            log.info(f"  - 持仓成本：{pos.avg_cost:.2f}元 | 当前价格：{pos.price:.2f}元")
            log.info(f"  - 持仓市值：{pos.value:.2f}元 | 浮盈率：{profit_rate}% | 浮盈：{profit:.2f}元")
            if profit_rate < -5 and code not in g.loss_blacklist:
                ban_end = current_date + ban_period
                g.loss_blacklist[code] = ban_end
                log.warning(f"  - ⚠️ 浮亏超5%，拉入黑名单！禁止至{ban_end}（{ban_period.days}天）")
            elif code in g.loss_blacklist:
                remaining = (g.loss_blacklist[code] - current_date).days
                log.info(f"  - ⚠️ 已在黑名单，剩余禁止时间：{remaining}天（截止{g.loss_blacklist[code]}）")
            else:
                log.info(f"  - ✅ 浮亏未超5%，未进黑名单")
            log.info("  - " + "-"*50)
        cash = context.portfolio.available_cash
        total_asset = total_value + cash
        log.info(f"持仓总市值：{total_value:.2f}元 | 现金：{cash:.2f}元 | 总资产：{total_asset:.2f}元 | 总浮盈：{total_profit:.2f}元")
    else:
        log.info("⚠️ 当前无持仓")

    log.info(f"\n【4】当前亏损黑名单汇总（共{len(g.loss_blacklist)}只）：")
    if g.loss_blacklist:
        for code, ban_end in g.loss_blacklist.items():
            remaining = (ban_end - current_date).days
            log.info(f"  - {code}（{get_security_info(code).name}）：禁止至{ban_end}（剩余{remaining}天）")
    else:
        log.info("  - 暂无股票在黑名单")

    log.info("="*80 + "\n")