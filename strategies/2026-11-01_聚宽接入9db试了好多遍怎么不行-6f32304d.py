# Clone from JoinQuant
# postId: 6f32304d7579501b8d7b7108bd59a228
# backtestId: 886b6de7a3932ac8e0594393ba4b8186
# title: 聚宽接入9db试了好多遍怎么不行

# 克隆自聚宽文章：https://www.joinquant.com/post/71608
# 标题：短线情绪门控 ，回测 3425 倍，核心设计和瓶颈复盘
# 作者：hanswang

# 克隆自聚宽文章：https://www.joinquant.com/post/71613
# 标题：三马105-五福35warmup优化后
# 作者：kakamijac

import datetime
import math
import json
import hashlib
import prettytable
import numpy as np
import pandas as pd
from datetime import timedelta
from jqdata import *
from jqfactor import *
from prettytable import PrettyTable
from types import SimpleNamespace

def initialize(context):
    set_params(context)
    set_backtest(context)
    set_strategy_params(context)
    if g.portfolio_value_proportion[2] > 0 and not (
        g.portfolio_value_proportion == [0, 0, 1, 0]
    ):
        init_range_bound_status(context)
    log.set_level("order", "error")


# 基础参数设置
def set_params(context):
    """
    资金分配比例：[小市值, ETF反弹, ETF轮动, 白马攻防]
    注意：ETF反弹策略仅适用于2023.9月后（中证2000ETF上市时间）
    """
    #g.portfolio_value_proportion = [0.35, 0.1, 0.35, 0.2]  # 小市值/ETF反弹/ETF轮动/白马攻防 (实盘)
    # g.portfolio_value_proportion = [0.4, 0.2, 0.4, 0]  # 小市值/ETF反弹/ETF轮动 (实盘/短回测)
    g.portfolio_value_proportion = [0, 0, 1, 0]  # 小市值/ETF轮动 (用于长回测)
    # g.portfolio_value_proportion = [0.35, 0, 0.35, 0.3]  # 小市值/ETF轮动/白马 (用于长回测)
    #g.portfolio_value_proportion = [1, 0, 0, 0]

    g.starting_cash = context.portfolio.total_value
    g.stock_strategy = {}
    g.strategy_holdings = {1: [], 2: [], 3: [], 4: []}
	
    # 【核心重构：独立虚拟子账户系统】
    g.sub_account = {}
    for i in range(1, 5):
        initial_capital = g.starting_cash * g.portfolio_value_proportion[i-1]
        g.sub_account[i] = {
            'initial_capital': initial_capital, # 初始分配本金（用于计算总收益率）
            'cash': initial_capital,            # 该策略专用的可用现金（买卖只能动用这部分钱）
            'total_value': initial_capital      # 该策略的总资产（现金 + 持仓市值）
        }
	
    # 暂存一个ETF反弹的初始比例
    g.strategy_ETF_2000_proportion = g.portfolio_value_proportion[1]
    g.strategy_ETF_2000_proportion_reset = None  # 用于检测拨正
    capital_balance_2(context)  # 首次就进行一次检测
	
	    # 由于已经完全隔离资金，废弃原有的混合挪账逻辑
    g.strategy_value_data = {1:0, 2:0, 3:0, 4:0}
    # 策略1「选股本身」累计已实现盈亏（卖出回款 − 对应成本），用于 record(小市值选股)，与组合槽位市值无关
    g.xsz_pnl_realized_cumulative = 0.0


""" ====================== 核心交易引擎 (隔离专用) ====================== """

def trade_for_strategy(context, security, target_value, strategy_id):
    """
    完全隔离的底层下单引擎：利用真实物理资金变化精准维护虚拟账本
    """
    if target_value < 0: target_value = 0

    curr_data = get_current_data()[security]
    if curr_data.paused: return None
    current_price = curr_data.last_price
    if current_price == 0: return None

    # 计算当前持仓价值
    pos = context.portfolio.positions.get(security)
    current_amount = pos.total_amount if pos else 0
    current_value = current_amount * current_price

    # 差额
    delta_value = target_value - current_value

    if abs(delta_value) < getattr(g, "min_money", 10):
        return None

    is_fund = security.startswith('5') or security.startswith('1')

    # 【卖出操作】
    if delta_value < 0:
        sell_amount = int(abs(delta_value) / current_price)
        if pos and sell_amount > pos.closeable_amount:
            sell_amount = pos.closeable_amount
        if sell_amount <= 0: return None

        avg_cost_before = pos.avg_cost if pos else 0
        cash_before = context.portfolio.available_cash
        
        order_obj = order(security, -sell_amount)
        if order_obj:
            if order_obj.filled > 0:
                # 真实回款 = 下单后增加的物理资金
                cash_after = context.portfolio.available_cash
                real_deal_money = cash_after - cash_before
                
                # 保底（防止聚宽底层结算时延）
                if real_deal_money <= 0:
                    fee_rate = 0.0002 if is_fund else 0.0013
                    real_deal_money = order_obj.price * order_obj.filled * (1 - fee_rate)

                # 策略1：累计已实现盈亏（与 ETF 轮动资金无关，仅股票/ETF 买卖价差）
                if strategy_id == 1 and avg_cost_before > 0:
                    cost_sold = avg_cost_before * order_obj.filled
                    g.xsz_pnl_realized_cumulative = float(
                        getattr(g, "xsz_pnl_realized_cumulative", 0.0)
                    ) + (real_deal_money - cost_sold)
                
                g.sub_account[strategy_id]['cash'] += real_deal_money
                
                # 仓位清退清理
                if pos.total_amount - order_obj.filled <= 0:
                    if security in g.strategy_holdings[strategy_id]:
                        g.strategy_holdings[strategy_id].remove(security)
                    if security in g.stock_strategy:
                        del g.stock_strategy[security]
                        
                log.info(f"💰[策略{strategy_id} 卖出] {format_stock_code(security)} 真实回笼资金: {real_deal_money:.2f}")
        return order_obj

    # 【买入操作】
    if delta_value > 0:
        # 防护壁垒：最多只能用本策略钱包里的钱！
        available_cash = g.sub_account[strategy_id]['cash']
        buy_value = min(delta_value, available_cash)

        if buy_value < getattr(g, "min_money", 10):
            return None

        # 买入扣费预留 (ETF万二，股票万七) 防止废单
        fee_reserve = 1.0002 if is_fund else 1.0007
        buy_amount = int((buy_value / fee_reserve) / current_price / 100) * 100
        if buy_amount <= 0: return None

        cash_before = context.portfolio.available_cash
        
        order_obj = order(security, buy_amount)
        if order_obj:
            if order_obj.filled > 0:
                cash_after = context.portfolio.available_cash
                real_cost_money = cash_before - cash_after
                
                if real_cost_money <= 0:
                    real_cost_money = order_obj.price * order_obj.filled * fee_reserve
                    
                # 精准扣除账户现金（包含真实的滑点与手续费）
                g.sub_account[strategy_id]['cash'] -= real_cost_money
                
                # 登记策略归属
                if security not in g.strategy_holdings[strategy_id]:
                    g.strategy_holdings[strategy_id].append(security)
                g.stock_strategy[security] = strategy_id
                
                log.info(f"🛒[策略{strategy_id} 买入] {format_stock_code(security)} 真实扣费资金: {real_cost_money:.2f}")
        return order_obj
    return None

# ----- 兼容旧代码的接口 -----
def open_position(context, security, value, strategy_id):
    return trade_for_strategy(context, security, value, strategy_id)

def close_position(context, security):
    sid = g.stock_strategy.get(security, 3) 
    return trade_for_strategy(context, security, 0, sid)


def _sync_strategy_1_sub_account_cash(context, strategy_value_budget):
    """
    将策略1虚拟现金对齐为：名义权益预算 − 策略1持仓市值。
    多子策略并存时，若仅依赖成交流水累加子账户，易与全组合市值×比例漂移，导致 trade_for_strategy
    用子账户现金限买、与 小市值 的「全账户×比例」预算不一致；同步后 [1,0,0,0] 与 [0.5,0,0.5,0] 下
    策略1的收益率曲线与仓位逻辑可一致（同比例缩放下）。
    """
    if g.portfolio_value_proportion[0] <= 0:
        return
    hv = sum(
        pos.value
        for pos in context.portfolio.positions.values()
        if pos.security in g.strategy_holdings[1]
    )
    g.sub_account[1]["cash"] = max(0.0, float(strategy_value_budget) - float(hv))


def smart_order_target_value(security, target_value, context):
    """专门供给策略3 (ETF轮动) 调用的接口"""
    current_data = get_current_data()
    security_name = get_security_name(security)
    if current_data[security].paused:
        log.info(f"{security} {security_name}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {security_name}: 当前涨停，跳过交易")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {security_name}: 当前跌停，跳过交易")
        return False
    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"{security} {security_name}: 当前价格为0，跳过交易")
        return False
    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < g.min_money:
        log.info(f"{security} {security_name}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过")
        return False
    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {security_name}: 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)
    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            # 同步维护策略3虚拟现金（仅用于收益归因显示，不影响真实下单）
            filled = getattr(order_result, "filled", 0) or 0
            deal_price = getattr(order_result, "price", current_price) or current_price
            commission = getattr(order_result, "commission", 0) or 0
            tax = getattr(order_result, "tax", 0) or 0
            if filled > 0:
                deal_value = filled * deal_price
                if amount_diff > 0:
                    g.sub_account[3]['cash'] -= (deal_value + commission + tax)
                else:
                    g.sub_account[3]['cash'] += (deal_value - commission - tax)
                if g.sub_account[3]['cash'] < 0:
                    g.sub_account[3]['cash'] = 0

            if amount_diff > 0:
                if security not in g.strategy_holdings[3]:
                    g.strategy_holdings[3].append(security)
                g.stock_strategy[security] = 3
                log.info(f"📦 买入{security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}")
            else:
                pos_after = context.portfolio.positions.get(security, None)
                if (pos_after is None or pos_after.total_amount <= 0) and security in g.strategy_holdings[3]:
                    g.strategy_holdings[3].remove(security)
                    if security in g.stock_strategy:
                        del g.stock_strategy[security]
                log.info(f"📤 卖出{security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}")
            return True
        log.warning(f"下单失败: {security} {security_name}，数量: {amount_diff}")
        return False
    return False


def setup_wufu35_globals():
    """五福闹新春v3.5全局变量设置（来自wf35最终版）"""

    # ========== 固定ETF池（wf35完整版） ==========
    g.fixed_etf_pool = [
#大宗商品ETF：
        '518880.XSHG',  # (黄金ETF) [ETF]-成交额：54.60亿元-上市日期：2013-07-29
        '161226.XSHE',  # (国投白银LOF) [LOF]-成交额：21.54亿元-上市日期：2015-08-17
        '159980.XSHE',  # (有色ETF大成) [ETF]-成交额：23.57亿元-上市日期：2019-12-24
        '501018.XSHG',  # (南方原油LOF) [LOF]-成交额：1.34亿元-上市日期：2016-06-28
        '159985.XSHE',  # (豆粕ETF) [ETF]-成交额：0.67亿元
#海外ETF：       
        '513100.XSHG',  # (纳指ETF) [ETF]-成交额：4.24亿元-上市日期：2013-05-15
        '159509.XSHE',  # (纳指科技ETF景顺) [ETF]-成交额：5.65亿元-上市日期：2023-08-08
        '513290.XSHG',  # (纳指生物) [ETF]-成交额：1.28亿元-上市日期：2022-08-29        
        '513500.XSHG',  # (标普500) [ETF]-成交额：2.22亿元-上市日期：2014-01-15
        '159518.XSHE',  # (标普油气ETF嘉实) [ETF]-成交额：5.35亿元-上市日期：2023-11-15
        '159502.XSHE',  # (标普生物科技ETF嘉实) [ETF]-成交额：4.00亿元-上市日期：2024-01-10        
        '159529.XSHE',  # (标普消费ETF) [ETF]-成交额：2.25亿元-上市日期：2024-02-02
        '513400.XSHG',  # (道琼斯) [ETF]-成交额：1.09亿元-上市日期：2024-02-02
        '520830.XSHG',  # (沙特ETF) [ETF]-成交额：1.16亿元-上市日期：2024-07-16
        '513520.XSHG',  # (日经ETF) [ETF]-成交额：1.11亿元-上市日期：2019-06-25
        '513030.XSHG',  # (德国ETF) [ETF]-成交额：0.77亿元
#港股ETF：
        '513090.XSHG',  # (香港证券) [ETF]-成交额：68.32亿元-上市日期：2020-03-26
        '513180.XSHG',  # (恒指科技) [ETF]-成交额：61.72亿元-上市日期：2021-05-25
        '513120.XSHG',  # (HK创新药) [ETF]-成交额：48.95亿元-上市日期：2022-07-12
        '513330.XSHG',  # (恒生互联) [ETF]-成交额：37.01亿元-上市日期：2021-02-08
        '513750.XSHG',  # (港股非银) [ETF]-成交额：23.06亿元-上市日期：2023-11-27
        '159892.XSHE',  # (恒生医药ETF) [ETF]-成交额：12.25亿元-上市日期：2021-10-19
        '159605.XSHE',  # (中概互联ETF) [ETF]-成交额：5.14亿元-上市日期：2021-12-02
        '513190.XSHG',  # (H股金融) [ETF]-成交额：5.07亿元-上市日期：2023-10-11
        '510900.XSHG',  # (恒生中国) [ETF]-成交额：3.73亿元-上市日期：2012-10-22
        '513630.XSHG',  # (香港红利) [ETF]-成交额：3.69亿元-上市日期：2023-12-08
        '513920.XSHG',  # (港股通央企红利) [ETF]-成交额：3.11亿元-上市日期：2024-01-05
        '159323.XSHE',  # (港股通汽车ETF) [ETF]-成交额：2.02亿元-上市日期：2025-01-08
        '513970.XSHG',  # (恒生消费) [ETF]-成交额：1.25亿元-上市日期：2023-04-21
#指数ETF：        
        '510500.XSHG',  # (中证500ETF) [ETF]-成交额：263.30亿元-上市日期：2013-03-15
        '512100.XSHG',  # (中证1000ETF) [ETF]-成交额：32.30亿元-上市日期：2016-11-04
        '563300.XSHG',  # (中证2000) [ETF]-成交额：3.34亿元-上市日期：2023-09-14        
        '510300.XSHG',  # (沪深300ETF) [ETF]-成交额：253.91亿元-上市日期：2012-05-28
        '512050.XSHG',  # (A500E) [ETF]-成交额：151.68亿元-上市日期：2024-11-15        
        '510760.XSHG',  # (上证ETF) [ETF]-成交额：1.10亿元-上市日期：2020-09-09        
        '159915.XSHE',  # (创业板ETF易方达) [ETF]-成交额：129.05亿元-上市日期：2011-12-09
        '159949.XSHE',  # (创业板50ETF) [ETF]-成交额：15.23亿元-上市日期：2016-07-22
        '159967.XSHE',  # (创业板成长ETF) [ETF]-成交额：3.27亿元-上市日期：2019-07-15        
        '588080.XSHG',  # (科创板50) [ETF]-成交额：123.46亿元-上市日期：2020-11-16
        '588220.XSHG',  # (科创100) [ETF]-成交额：4.99亿元-上市日期：2023-09-15
        '511380.XSHG',  # (可转债ETF) [ETF]-成交额：165.76亿元-上市日期：2020-04-07
#行业ETF：
        '513310.XSHG',  # (中韩芯片) [ETF]-成交额：38.68亿元-上市日期：2022-12-22
        '588200.XSHG',  # (科创芯片) [ETF]-成交额：37.94亿元-上市日期：2022-10-26
        '159852.XSHE',  # (软件ETF) [ETF]-成交额：36.26亿元-上市日期：2021-02-09
        '512880.XSHG',  # (证券ETF) [ETF]-成交额：34.01亿元-上市日期：2016-08-08
        '159206.XSHE',  # (卫星ETF) [ETF]-成交额：32.60亿元-上市日期：2025-03-14
        '512400.XSHG',  # (有色金属ETF) [ETF]-成交额：31.27亿元-上市日期：2017-09-01
        '512980.XSHG',  # (传媒ETF) [ETF]-成交额：30.96亿元-上市日期：2018-01-19
        '159516.XSHE',  # (半导体设备ETF) [ETF]-成交额：28.21亿元-上市日期：2023-07-27
        '512480.XSHG',  # (半导体) [ETF]-成交额：16.29亿元-上市日期：2019-06-12
        '515880.XSHG',  # (通信ETF) [ETF]-成交额：13.46亿元-上市日期：2019-09-06
        '562500.XSHG',  # (机器人) [ETF]-成交额：12.92亿元-上市日期：2021-12-29
        '159218.XSHE',  # (卫星产业ETF) [ETF]-成交额：12.74亿元-上市日期：2025-05-22
        '159869.XSHE',  # (游戏ETF) [ETF]-成交额：12.42亿元-上市日期：2021-03-05
        '159870.XSHE',  # (化工ETF) [ETF]-成交额：12.30亿元-上市日期：2021-03-03
        '159326.XSHE',  # (电网设备ETF) [ETF]-成交额：12.02亿元-上市日期：2024-09-09
        '159851.XSHE',  # (金融科技ETF) [ETF]-成交额：11.79亿元-上市日期：2021-03-19
        '560860.XSHG',  # (工业有色) [ETF]-成交额：11.71亿元-上市日期：2023-03-13
        '159363.XSHE',  # (创业板人工智能ETF华宝) [ETF]-成交额：10.63亿元-上市日期：2024-12-16
        '588170.XSHG',  # (科创半导) [ETF]-成交额：10.28亿元-上市日期：2025-04-08
        '159755.XSHE',  # (电池ETF) [ETF]-成交额：10.02亿元-上市日期：2021-06-24
        '512170.XSHG',  # (医疗ETF) [ETF]-成交额：9.54亿元-上市日期：2019-06-17
        '512800.XSHG',  # (银行ETF) [ETF]-成交额：9.48亿元-上市日期：2017-08-03
        '159819.XSHE',  # (人工智能ETF易方达) [ETF]-成交额：9.40亿元-上市日期：2020-09-23
        '512710.XSHG',  # (军工龙头) [ETF]-成交额：9.39亿元-上市日期：2019-08-26
        '159638.XSHE',  # (高端装备ETF嘉实) [ETF]-成交额：8.92亿元-上市日期：2022-08-12
        '517520.XSHG',  # (黄金股) [ETF]-成交额：8.73亿元-上市日期：2023-11-01
        '515980.XSHG',  # (人工智能) [ETF]-成交额：8.73亿元-上市日期：2020-02-10
        '159995.XSHE',  # (芯片ETF) [ETF]-成交额：8.45亿元-上市日期：2020-02-10
        '159227.XSHE',  # (航空航天ETF) [ETF]-成交额：8.42亿元-上市日期：2025-05-16
        '512660.XSHG',  # (军工ETF) [ETF]-成交额：7.78亿元-上市日期：2016-08-08
        '512690.XSHG',  # (酒ETF) [ETF]-成交额：6.74亿元-上市日期：2019-05-06
        '516150.XSHG',  # (稀土基金) [ETF]-成交额：6.41亿元-上市日期：2021-03-17
        '512890.XSHG',  # (红利低波) [ETF]-成交额：6.03亿元-上市日期：2019-01-18
        '588790.XSHG',  # (科创智能) [ETF]-成交额：5.92亿元-上市日期：2025-01-09
        '159992.XSHE',  # (创新药ETF) [ETF]-成交额：5.63亿元-上市日期：2020-04-10
        '512070.XSHG',  # (证券保险) [ETF]-成交额：5.50亿元-上市日期：2014-07-18
        '562800.XSHG',  # (稀有金属) [ETF]-成交额：5.49亿元-上市日期：2021-09-27
        '512010.XSHG',  # (医药ETF) [ETF]-成交额：5.22亿元-上市日期：2013-10-28
        '515790.XSHG',  # (光伏ETF) [ETF]-成交额：4.95亿元-上市日期：2020-12-18
        '510880.XSHG',  # (红利ETF) [ETF]-成交额：4.90亿元-上市日期：2007-01-18
        '159928.XSHE',  # (消费ETF) [ETF]-成交额：4.71亿元-上市日期：2013-09-16
        '159883.XSHE',  # (医疗器械ETF) [ETF]-成交额：4.44亿元-上市日期：2021-04-30
        '159998.XSHE',  # (计算机ETF) [ETF]-成交额：3.93亿元-上市日期：2020-04-13
        '515220.XSHG',  # (煤炭ETF) [ETF]-成交额：3.92亿元-上市日期：2020-03-02
        '561980.XSHG',  # (芯片设备) [ETF]-成交额：3.89亿元-上市日期：2023-09-01
        '515400.XSHG',  # (大数据) [ETF]-成交额：3.54亿元-上市日期：2021-01-20
        '515120.XSHG',  # (创新药) [ETF]-成交额：3.54亿元-上市日期：2021-01-04
        '159566.XSHE',  # (储能电池ETF易方达) [ETF]-成交额：3.05亿元-上市日期：2024-02-08
        '515050.XSHG',  # (5GETF) [ETF]-成交额：3.04亿元-上市日期：2019-10-16
        '516510.XSHG',  # (云计算ETF) [ETF]-成交额：2.95亿元-上市日期：2021-04-07
        '159256.XSHE',  # (创业板软件ETF华夏) [ETF]-成交额：2.89亿元-上市日期：2025-08-04
        '159766.XSHE',  # (旅游ETF) [ETF]-成交额：2.57亿元-上市日期：2021-07-23
        '512200.XSHG',  # (地产ETF) [ETF]-成交额：2.53亿元-上市日期：2017-09-25
        '513350.XSHG',  # (油气ETF) [ETF]-成交额：2.48亿元-上市日期：2023-11-28
        '159583.XSHE',  # (通信设备ETF) [ETF]-成交额：2.47亿元-上市日期：2024-07-08
        '159732.XSHE',  # (消费电子ETF) [ETF]-成交额：2.39亿元-上市日期：2021-08-23
        '516160.XSHG',  # (新能源) [ETF]-成交额：2.26亿元-上市日期：2021-02-04
        '516520.XSHG',  # (智能驾驶) [ETF]-成交额：2.22亿元-上市日期：2021-03-01
        '562590.XSHG',  # (半导材料) [ETF]-成交额：1.94亿元-上市日期：2023-10-18
        '515030.XSHG',  # (新汽车) [ETF]-成交额：1.93亿元-上市日期：2020-03-04
        '512670.XSHG',  # (国防ETF) [ETF]-成交额：1.84亿元-上市日期：2019-08-01
        '561330.XSHG',  # (矿业ETF) [ETF]-成交额：1.81亿元-上市日期：2022-11-01
        '516190.XSHG',  # (文娱ETF) [ETF]-成交额：1.67亿元-上市日期：2021-09-17
        '159840.XSHE',  # (锂电池ETF工银) [ETF]-成交额：1.61亿元-上市日期：2021-08-20
        '159611.XSHE',  # (电力ETF) [ETF]-成交额：1.52亿元-上市日期：2022-01-07
        '159981.XSHE',  # (能源化工ETF) [ETF]-成交额：1.48亿元-上市日期：2020-01-17
        '159865.XSHE',  # (养殖ETF) [ETF]-成交额：1.40亿元-上市日期：2021-03-08
        '561360.XSHG',  # (石油ETF) [ETF]-成交额：1.36亿元-上市日期：2023-10-31
        '159667.XSHE',  # (工业母机ETF) [ETF]-成交额：1.32亿元-上市日期：2022-10-26
        '515170.XSHG',  # (食品饮料ETF) [ETF]-成交额：1.30亿元-上市日期：2021-01-13
        '513360.XSHG',  # (教育ETF) [ETF]-成交额：1.09亿元-上市日期：2021-06-17
        '159825.XSHE',  # (农业ETF) [ETF]-成交额：1.05亿元-上市日期：2020-12-29
        '515210.XSHG',  # (钢铁ETF) [ETF]-成交额：1.03亿元-上市日期：2020-03-02
    ]
    g.filtered_fixed_pool = []
    g.dynamic_etf_pool = []
    g.merged_etf_pool = []
    g.ranked_etfs_result = []
    g.positions = {}
    g.target_etfs_list = []
    g.etf_names_dict = {}
    g.cache_date = None
    g.yesterday_close_cache = {}
    # ========== 策略核心参数 ==========
    g.holdings_num = 1
    g.defensive_etf = "511880.XSHG"
    g.min_money = 10
    g.lookback_days = 25
    g.min_score_threshold = 0
    g.max_score_threshold = 5
    g.score_threshold_ratio = 0.9
    g.enable_dynamic_score_threshold = False
    g.normal_score_threshold_ratio = 0.88
    g.range_score_threshold_ratio = 0.92
    g.score_threshold_ratio_min = 0.82
    g.score_threshold_ratio_max = 0.95
    g.use_short_momentum_period = False
    g.short_momentum_lookback = 21
    g.short_momentum_min_score = 0
    g.short_momentum_max_score = 6
    g.enable_r2_filter = True
    g.r2_threshold = 0.4
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 1.8
    g.enable_loss_filter = True
    g.loss = 0.97
    g.enable_premium_filter = False
    g.max_premium_rate = 30
    g.laplace_s_param = 0.05
    g.laplace_min_slope = 0.002
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002
    # ========== 震荡期参数 ==========
    g.enable_range_bound_mode = True
    g.current_filter = '正常期'
    g.risk_state = '正常期'
    g.lookback_high_low_days = 20
    g.risk_benchmark = '510300.XSHG'
    g.enable_bias_trigger = True
    g.bias_threshold = 0.08
    g.ma_period = 20
    g.enable_rsi_trigger = True
    g.rsi_overbought = 70
    g.rsi_pullback = 65
    g.previous_rsi = None
    g.enable_stop_loss_trigger = True
    g.stop_loss_triggered_today = False
    g.enable_low_point_rise_trigger = True
    g.low_point_rise_threshold = 0.04
    g.enable_stable_signal_trigger = True
    g.drawdown_recovery = 0.02
    g.max_range_bound_days = 20
    g.stable_days = 0
    g.filter_switch_cooldown = 3
    g.last_switch_date = None
    g.range_bound_start_date = None
    g.range_bound_days_count = 0
    g.previous_drawdown = None
    g.max_portfolio_value = 0
    g.drawdown_threshold = 0.03
    g.drawdown_records = []
    g.use_fixed_stop_loss = True
    g.fixedStopLossThreshold = 0.95
    g.use_pct_stop_loss = False
    g.pct_stop_loss_threshold = 0.95
    g.avg_etf_money_threshold = None
    g.enable_step1_full_ranking_log = False
    g.enable_chase_whipsaw_audit = True
    g.latest_selection_audit = None
    g.prev_selection_audit = None
    g.prev_day_sold_etfs = []
    g.prev_day_bought_etfs = []
    g.today_switch_buffer_audit = None
    g.prev_switch_buffer_audit = None
    g.switch_buffer_effect_events = []
    g.enable_chase_summary_log = True
    g.chase_events = []
    g.enable_long_delta_gate = False
    g.long_delta_gate_min = 0.5
    g.long_delta_gate_max = 3
    g.enable_short_delta_gate = False
    g.short_delta_gate_min = 0
    g.short_delta_gate_max = 5
    g.enable_smoothed_momentum_input = False
    g.smoothed_ma_window = 5
    g.smoothed_momentum_only_in_range = True
    g.enable_range_r2_veto = False
    g.r2_threshold_range_bound = 0.9
    g.enable_range_momentum_floor = False
    g.range_momentum_min = 0.0
    g.range_momentum_max = 2.0
    g.enable_range_short_momentum_limits = True
    g.range_short_momentum_min = 0.0
    g.range_short_momentum_max = 5.0
    g.enable_switch_hysteresis = False
    g.switch_buffer_normal = 0.10
    g.switch_buffer_range = 0.40
    g.enable_dual_positive_momentum = True
    g.dual_positive_only_in_range = True
    g.whipsaw_options_only_in_range = True
    g.log_whipsaw_filter_detail = True
    # ========== 预热校准参数 ==========
    g.enable_warmup = True
    g.enable_deep_warmup = True
    g.warmup_trade_days = 180
    g.warmup_min_required_days = 60
    g.warmup_use_daily_proxy = True
    g.enable_warmup_trade_simulation = True
    g.warmup_simulation_trade_days = 120
    g.enable_warmup_anchor_replay = True
    g.warmup_anchor_start_date = None
    g.warmup_anchor_min_days = 40
    g.warmup_simulate_minute_stoploss = True
    g.enable_warmup_trace_log = True
    g.warmup_trace_last_n_days = 25
    g.enable_warmup_fingerprint_log = True
    g.enable_warmup_state_reconcile = True
    g.warmup_replay_strict_trade_rules = True
    g.warmup_simulate_order_costs = True
    g.warmup_commission_rate = 0.0001
    g.warmup_min_commission = 5.0
    g.warmup_match_main_slippage = True
    g.warmup_slippage_ratio = 0.0001
    g.warmup_done = False
    g.warmup_virtual_positions = {}
    g.warmup_virtual_cash = None
    g.warmup_pending_sync = False
    g.warmup_sync_target_etfs = []
    g.warmup_sync_max_candidates = 3
    g.deep_warmup_reduce_log = True
    g.enable_warmup_path_audit_log = True
    g.enable_warmup_stoploss_low_vs_close_diag = True
    g.warmup_stoploss_trigger_price_mode = 'intrabar_low'
    g.warmup_path_audit_start = None
    g.warmup_path_audit_end = None
    g.warmup_path_audit_default_month = 3


def init_range_bound_status(context):
    """首次运行时，根据历史数据判断当前是否处于震荡期"""
    if not g.enable_range_bound_mode:
        return
    log.info("🔍 【首次运行】初始化震荡期状态...")
    try:
        if context.previous_date is None:
            log.warning("【首次运行】无法获取前一个交易日，保持正常期")
            return
        end_date = context.previous_date
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback, 
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            log.warning(f"【首次运行】数据不足(需{max(g.ma_period, g.lookback_high_low_days)}天，实际{len(df) if df is not None else 0}天)，保持正常期")
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        if len(close) >= g.lookback_high_low_days:
            recent_high = np.max(high[-g.lookback_high_low_days:])
            recent_low = np.min(low[-g.lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        ma = np.mean(close[-g.ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        current_rsi = wufu35_calculate_rsi(close, period=14)
        should_enter_range_bound = False
        signals = []
        if g.enable_bias_trigger and bias > g.bias_threshold:
            should_enter_range_bound = True
            signals.append(f"乖离率{bias:.2%}>{g.bias_threshold:.0%}")
        if g.enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = wufu35_calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback:
                should_enter_range_bound = True
                signals.append(f"RSI超买回落{prev_rsi:.1f}→{current_rsi:.1f}")
        if should_enter_range_bound:
            g.current_filter = '震荡期'           # 切换到震荡期（高斯滤波器）
            g.risk_state = '震荡期'               # 风险状态：震荡期
            g.range_bound_start_date = end_date
            g.range_bound_days_count = 0
            log.info(f"🔔 【首次运行】初始化进入震荡期: {'; '.join(signals)}")
        else:
            g.current_filter = '正常期'           # 正常期（拉普拉斯滤波器）
            g.risk_state = '正常期'               # 风险状态：正常期
            if len(close) >= g.lookback_high_low_days:
                g.previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            else:
                g.previous_drawdown = 0
            g.previous_rsi = current_rsi
            log.info(f"📌 【首次运行】初始状态: 正常期(拉普拉斯滤波器), 乖离率: {bias:.2%}, RSI: {current_rsi:.1f}, 从低点涨幅: {rise_from_low:.2%}")
    except Exception as e:
        log.warning(f"【首次运行】初始化震荡期状态异常: {e}，保持正常期")



def morning_routine(context):
    """晨间准备流水线（09:00执行）：持仓检查 → 回撤监控 → 流动性阈值计算 → 动态池更新 → 固定池过滤 → 合并池"""
    log.info("★" * 80)
    log.info("▶️ 【晨间流水线】启动...")
    log.info("【持仓检查】检查当前持仓状态...")
    check_positions(context)    
    log.info("【回撤监控】监控策略回撤...")
    monitor_drawdown(context)
    log.info("【流动性阈值】计算全市场ETF流动性阈值...")
    calculate_global_etf_threshold(context)
    log.info("【动态池更新】更新行业ETF动态池...")
    update_sector_pool(context)
    log.info("【固定池过滤】过滤固定ETF池流动性...")
    filter_fixed_pool_by_volume(context)
    log.info("【合并池】合并固定池与动态池...")
    daily_merge_etf_pools(context)
    log.info("⏸️ 【晨间流水线】执行完毕！")

def afternoon_routine(context):
    """午后交易流水线（13:10执行）"""

    log.info("▶️ 【午后交易流水线】启动...")
    log.info("【震荡期退出检查】检查是否需要退出震荡期...")
    check_and_exit_range_bound_mode(context)
    log.info("【震荡期进入检查】检查是否需要进入震荡期...")
    check_and_enter_range_bound_mode(context)
    log.info("【动量计算】计算ETF动量得分与排序...")
    g.today_switch_buffer_audit = None
    calculate_and_log_ranked_etfs(context)
    if g.portfolio_value_proportion != [0, 0, 1, 0]:
        log.info("【持仓同步】同步策略3登记持仓与账户真实持仓...")
        sync_strategy3_holdings_from_portfolio(context)
    log.info("【卖出执行】执行卖出操作...")
    execute_sell_trades(context)
    log.info("【买入执行】执行买入操作...")
    execute_buy_trades(context)
    log.info("⏸️ 【午后交易流水线】执行完毕！")

def reset_daily_flags(context):
    """收盘流水线（15:10执行）"""

    g.cache_date = None
    g.yesterday_close_cache = {}
    if g.current_filter == "震荡期" and g.range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
        g.range_bound_days_count = len(trade_days) - 1
        log.info("📊 震荡期已持续 {} 个交易日".format(g.range_bound_days_count))
    log.info("🔄 收盘缓存重置完成")

def check_positions(context):
    """盘前持仓检查"""
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 【持仓检查】{security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")

def monitor_drawdown(context):
    """回撤监控：当策略回撤超过阈值时，记录"""
    try:
        current_value = context.portfolio.total_value
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
                    'current_filter': g.current_filter,
                    'risk_state': g.risk_state
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
                log.info(f"  当前滤波器: {g.current_filter}  |  风险状态: {g.risk_state}")
                log.info(f"  持仓: {', '.join(positions_info) if positions_info else '空仓'}")
                log.info(f"{'='*70}\n")
    except Exception as e:
        log.error(f"【回撤监控】计算异常: {e}")
# ==================== 流动性阈值计算 ====================

def calculate_global_etf_threshold(context):
    """计算全市场ETF流动性阈值"""
    log.info("【全局阈值更新】开始计算全市场ETF流动性门槛")
    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            log.warning("未找到任何场内ETF，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        log.info(f"全市场ETF总数: {len(etf_list)}只")
        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]
        df = get_price(security=etf_list, start_date=start_day, end_date=context.previous_date, frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or df.empty:
            log.warning("无法获取历史成交额数据，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        daily_totals = df.groupby('time')['money'].sum()
        daily_counts = df[df['money'] > 0].groupby('time')['code'].nunique()
        for day, money in daily_totals.items():
            count = daily_counts.get(day, 0)
            log.info(f"  {day.date()} 全市场ETF总成交额: {money/1e8:.2f}亿元 ({count}只ETF有成交)")
        if len(daily_totals) < 3:
            log.warning(f"仅有{len(daily_totals)}个有效交易日，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        avg_total_money = daily_totals.mean()
        threshold = avg_total_money / 20000
        g.avg_etf_money_threshold = threshold
        log.info(f"【全局阈值更新完成】近{len(daily_totals)}日全市场ETF日均总成交额={avg_total_money/1e8:.2f}亿元，阈值={threshold/1e4:.0f}万元({threshold:,.0f}元)")
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}，使用保守阈值1000万")
        g.avg_etf_money_threshold = 10000000
# ==================== 动态池更新 ====================

def update_sector_pool(context):
    """更新行业ETF动态池"""
    log.info("【动态池更新】开始执行")
    if g.avg_etf_money_threshold is None:
        log.info("【动态池更新】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    # 基金公司名称列表
    FUND_COMPANIES = sorted(list(set([
        '易方达', '广发', '华夏', '华安', '嘉实', '富国', '招商', '鹏华', '南方', '汇添富', '国泰', '平安',
        '银华', '天弘', '建信', '工银', '华泰柏瑞', '博时', '景顺长城', '景顺', '华宝', '申万菱信', '万家', '中欧',
        '兴证全球', '浙商', '诺安', '前海开源', '泰康', '泰达宏利', '农银汇理', '交银', '东方红', '财通', '华商',
        '国联', '永赢', '金鹰', '德邦', '创金合信', '西部利得', '圆信永丰', '泓德', '汇安', '诺德', '恒生前海',
        '华润元大', '大成', '海富通', '摩根', '华泰', '中信', '中银', '兴全', '国信', '长城', '中金', '浙商证券',
        '东海', '东吴', '浦银安盛', '信达澳亚', '中加', '中航', '中融', '中邮', '中庚', '中信保诚', '中信建投',
        '中银国际', '中银证券', '九泰', '交银施罗德', '光大保德信', '兴银', '农银', '国投瑞银', '国海富兰克林',
        '国联安', '国金', '太平', '方正富邦', '民生加银', '汇丰晋信', '银河', '长信', '长安', '长盛', '长江证券', '鹏扬'
    ])), key=len, reverse=True)
    # 噪音词列表
    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)
    # 特别分组
    SPECIAL_GROUPS = sorted([
        {'name': '香港组', 'keywords': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS科技'], key=len, reverse=True),
         'remove_words': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS'], key=len, reverse=True)},
        {'name': '科创组', 'keywords': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True),
         'remove_words': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创', '债券', '债汇', '债指', '债沪', '债易', '债基', '债兴', '债摩', '债', 'AAA'], key=len, reverse=True)},
        {'name': '创业组', 'keywords': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True),
         'remove_words': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True)},
        {'name': '美指组', 'keywords': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True),
         'remove_words': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True)}
    ], key=lambda x: max(len(kw) for kw in x['keywords']), reverse=True)
    # 排除关键词
    exclude_keywords = sorted(list(set([
        '300', '500', '1000', '2000', '800', '30', '50', '100', '180', '200',
        '沪深', '中证', '上证', '深证', '深成', 'A50', 'A100', 'A500', '深100',
        '短融', '可转债', '转债', '双债', '利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债',
        '信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债', '科创债', '科债', '科创AAA',
        '自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流',
        '货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数',
        '全指现金', '现金全指', 'ESG', 'MSCI', 'MS', '债',
    ])), key=len, reverse=True)
    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        g.etf_names_dict = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"获取全市场ETF列表失败: {e}")
        return
    log.info(f"【动态池更新】全市场ETF总数: {len(etf_list)}只")
    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0
    # 分类ETF
    for code in etf_list:
        try:
            name = g.etf_names_dict.get(code, str(code))
            is_special = False
            matched_group = None
            for group in SPECIAL_GROUPS:
                for kw in group['keywords']:
                    if kw in name:
                        is_special = True
                        matched_group = group['name']
                        break
                if is_special:
                    break
            is_excluded = False
            for k in exclude_keywords:
                if k in name:
                    is_excluded = True
                    excluded_count += 1
                    break
            if not is_excluded:
                if is_special:
                    special_etfs.append(code)
                    special_group_map[code] = matched_group
                else:
                    normal_etfs.append(code)
        except Exception:
            continue
    group_counts = {}
    for code in special_etfs:
        group_name = special_group_map.get(code, '未知')
        group_counts[group_name] = group_counts.get(group_name, 0) + 1
    log.info(f"【动态池更新】特别组分布: {group_counts}")
    log.info(f"【动态池更新】进入特别组: {len(special_etfs)}只")
    log.info(f"【动态池更新】进入普通组: {len(normal_etfs)}只")
    log.info(f"【动态池更新】排除ETF: {excluded_count}只")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold
    def filter_by_liquidity(etf_codes, group_name):
        """按流动性过滤ETF"""
        if not etf_codes:
            return pd.Series(dtype=float), 0
        try:
            price_data = get_price(etf_codes, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
            if price_data is None or price_data.empty:
                return pd.Series(dtype=float), len(etf_codes)
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / TRADE_DAYS_COUNT
            qualified_series = avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
            filtered_out = len(etf_codes) - len(qualified_series)
            return qualified_series, filtered_out
        except Exception:
            return pd.Series(dtype=float), len(etf_codes)
    normal_qualified, normal_filtered_out = filter_by_liquidity(normal_etfs, "普通组")
    special_qualified, special_filtered_out = filter_by_liquidity(special_etfs, "特别组")
    normal_sorted = normal_qualified.index.tolist()
    special_sorted = special_qualified.index.tolist()
    log.info(f"【动态池更新】特别组流动性过滤: {len(special_etfs)}→{len(special_sorted)}只")    
    log.info(f"【动态池更新】普通组流动性过滤: {len(normal_etfs)}→{len(normal_sorted)}只")
    if not normal_sorted and not special_sorted:
        log.warning("【动态池更新】无ETF通过流动性过滤")
        g.dynamic_etf_pool = []
        return
    def get_remove_words_for_etf(_, is_special, matched_group_name):
        if not is_special:
            return []
        for group in SPECIAL_GROUPS:
            if group['name'] == matched_group_name:
                return group['remove_words']
        return []
    def clean_name(original_name, is_special=False, matched_group_name=None):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        if is_special and matched_group_name:
            for word in get_remove_words_for_etf(original_name, is_special, matched_group_name):
                cleaned = cleaned.replace(word, '')
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()
    normal_industry_groups = {}
    for code in normal_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            money = normal_qualified[code]
            cleaned = clean_name(original_name, is_special=False)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            if industry_key not in normal_industry_groups:
                normal_industry_groups[industry_key] = []
            normal_industry_groups[industry_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': '普通'
            })
        except Exception:
            continue
    special_industry_groups = {}
    for code in special_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            money = special_qualified[code]
            cleaned = clean_name(original_name, is_special=True, matched_group_name=matched_group)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            group_key = f"{matched_group}_{industry_key}"
            if group_key not in special_industry_groups:
                special_industry_groups[group_key] = []
            special_industry_groups[group_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': matched_group, 'display_group': matched_group
            })
        except Exception:
            continue
    final_pool_info = []
    for industry_key, items in normal_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    for group_key, items in special_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    final_pool_info_sorted = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    top_100 = final_pool_info_sorted[:100]
    g.dynamic_etf_pool = [item['code'] for item in top_100]
    log.info(f"【动态池更新完成】动态池共{len(g.dynamic_etf_pool)}只ETF")
    if len(g.dynamic_etf_pool) <= 10:
        for item in top_100[:10]:
            log.info(f"  {item['code']} {item['original_name']} 日均成交额: {item['money']/1e8:.2f}亿")
# ==================== 固定池流动性过滤 ====================

def filter_fixed_pool_by_volume(context):
    """每日对固定ETF池进行流动性过滤"""
    log.info("【固定池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        log.info("【固定池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.fixed_etf_pool:
        log.info("【固定池过滤】固定池为空，跳过过滤")
        return
    dynamic_threshold = g.avg_etf_money_threshold
    log.info(f"【固定池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.fixed_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("【固定池过滤】无法获取成交额数据，跳过过滤")
            g.filtered_fixed_pool = g.fixed_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_fixed_pool = qualified.index.tolist()
        removed = set(g.fixed_etf_pool) - set(new_fixed_pool)
        if removed:
            removed_info = []
            for code in removed:
                try:
                    name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                    money = avg_daily_money.get(code, 0)
                    removed_info.append(f"{name}({code}) {money/1e8:.2f}亿")
                except:
                    removed_info.append(code)
            log.info(f"【固定池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_fixed_pool = new_fixed_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        kept_info = []
        for code, money in sorted_qualified.items():
            try:
                name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                kept_info.append(f"{name}({code})日均{money/1e8:.2f}亿")
            except:
                kept_info.append(f"{code}日均{money/1e8:.2f}亿")
        log.info(f"【固定池过滤】保留高流动性ETF({len(new_fixed_pool)}只)")
    except Exception as e:
        log.warning(f"【固定池过滤】异常: {e}")
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
        
# ==================== 合并ETF池 ====================

def daily_merge_etf_pools(context):
    """每日合并固定池和动态池"""
    if not hasattr(g, 'filtered_fixed_pool'):
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    log.info("【合并ETF池】开始执行")
    log.info(f"【合并池统计】固定池: {len(g.filtered_fixed_pool)}只, 动态池: {len(g.dynamic_etf_pool)}只, 合并后: {len(merged)}只")
    g.merged_etf_pool = merged


# ==================== Warmup预热系统函数 ====================

class WarmupPortfolio(object):
    """预热期虚拟账户"""
    def __init__(self, cash):
        self.available_cash = float(cash)
        self.total_value = float(cash)
        self.positions = {}


def _parse_checkpoint_date(val):
    if val is None or val == '':
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val)[:10]
    return datetime.strptime(s, '%Y-%m-%d').date()


def _warmup_path_audit_active(td):
    """是否对回放日 td 打印路径/止损/状态机审计日志。"""
    if not getattr(g, 'enable_warmup_path_audit_log', False):
        return False
    if td is None:
        return False
    start = _parse_checkpoint_date(getattr(g, 'warmup_path_audit_start', None))
    end = _parse_checkpoint_date(getattr(g, 'warmup_path_audit_end', None))
    if start is not None or end is not None:
        if start is not None and td < start:
            return False
        if end is not None and td > end:
            return False
        return True
    dm = int(getattr(g, 'warmup_path_audit_default_month', 3))
    return getattr(td, 'month', None) == dm


def _warmup_log_path_audit_banner():
    """说明深度预热相对主回测执行了哪些环节（便于判断差异是否来自「部分策略未仿真」）。"""
    if not getattr(g, 'enable_warmup_path_audit_log', False):
        return
    if getattr(g, '_warmup_path_audit_banner_done', False):
        return
    g._warmup_path_audit_banner_done = True
    log.info(
        "📋【预热路径审计·范围说明】回放内每交易日执行："
        "09:00 流动性阈值与合并池 → 09:31–14:56 按分钟线仿真固定/跌幅止损(仅虚拟仓) → "
        "13:10 震荡退出/进入 → 13:10 全量动量排序与一次仿真调仓(含佣金近似) → "
        "EOD 震荡日计数与状态对账。"
        "【主回测有、预热未逐 bar 复现的环节】every_bar 其它逻辑、真实 order 撮合与滑点、"
        "以及未接入本回放循环的策略分支；虚拟持仓/成本若与主路径分叉，止损日与震荡相位可能差 1 个交易日。"
    )


def _json_safe_value(v):
    """将对象转换为适合日志/JSON输出的安全值。"""
    if v is None:
        return None
    if isinstance(v, (str, int, bool)):
        return v
    if isinstance(v, float):
        if math.isnan(v):
            return 'NaN'
        if math.isinf(v):
            return 'Infinity' if v > 0 else '-Infinity'
        return float(v)
    if isinstance(v, (datetime, date)):
        return str(v)
    if isinstance(v, dict):
        return {str(k): _json_safe_value(val) for k, val in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_json_safe_value(x) for x in v]
    if isinstance(v, np.generic):
        return _json_safe_value(v.item())
    if hasattr(v, '__dict__'):
        try:
            return _json_safe_value(vars(v))
        except Exception:
            return str(v)
    return str(v)


def _warmup_maybe_guard_filter(context):
    """深度预热回放：震荡期状态机一致性守卫（不影响非预热路径）。"""
    if not getattr(g, '_warmup_replay_mode', False):
        return
    if not getattr(g, 'enable_warmup_state_reconcile', True):
        return
    _warmup_guard_filter_consistency(context)


def _warmup_guard_filter_consistency(context):
    """修正 current_filter / risk_state / 震荡期日期与计数之间的明显不一致。"""
    td = context.current_dt.date() if context is not None and hasattr(context, 'current_dt') else None
    fixes = []
    cf = getattr(g, 'current_filter', None)
    if cf not in ('正常期', '震荡期'):
        g.current_filter = '正常期'
        cf = '正常期'
        fixes.append('filter_invalid->正常期')
    rs = getattr(g, 'risk_state', None)
    if rs != cf:
        g.risk_state = cf
        fixes.append('risk_state_sync')
    if cf == '震荡期':
        if getattr(g, 'range_bound_start_date', None) is None and td is not None:
            g.range_bound_start_date = td
            fixes.append('range_start_filled')
    else:
        if getattr(g, 'range_bound_start_date', None) is not None:
            g.range_bound_start_date = None
            fixes.append('range_start_clr')
        rc = int(getattr(g, 'range_bound_days_count', 0) or 0)
        if rc != 0:
            g.range_bound_days_count = 0
            fixes.append('range_cnt_reset')
    if fixes:
        log.info(f"【预热对齐修正】td={td} guard: {'; '.join(fixes)}")


def _warmup_eod_reconcile_state(td):
    """深度预热：收盘后对震荡期计数与风险状态再对账一次。"""
    if not getattr(g, '_warmup_replay_mode', False):
        return
    if not getattr(g, 'enable_warmup_state_reconcile', True):
        return
    fixes = []
    cf = getattr(g, 'current_filter', '正常期')
    if getattr(g, 'risk_state', None) != cf:
        g.risk_state = cf
        fixes.append('risk_state')
    if cf == '震荡期' and getattr(g, 'range_bound_start_date', None) is not None:
        tds = get_trade_days(start_date=g.range_bound_start_date, end_date=td)
        if tds is not None and len(tds) > 0:
            want = len(tds) - 1
            cur = int(getattr(g, 'range_bound_days_count', 0) or 0)
            if cur != want:
                g.range_bound_days_count = want
                fixes.append(f'range_cnt->{want}')
    elif cf == '正常期':
        if int(getattr(g, 'range_bound_days_count', 0) or 0) != 0:
            g.range_bound_days_count = 0
            fixes.append('range_cnt->0')
        if getattr(g, 'range_bound_start_date', None) is not None:
            g.range_bound_start_date = None
            fixes.append('range_start_clr')
    if fixes:
        log.info(f"【预热对齐-EOD】td={td} {'; '.join(fixes)}")


def _warmup_finite_positive(x):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v) or v <= 0:
        return None
    return v


def _warmup_security_trade_constraints(security, trade_date):
    """
    深度预热：用当日日线字段推断停牌与涨跌停价，规则与 smart_order_target_value 一致。
    无 high_limit/low_limit 时用前收盘价按 10% 涨跌幅推算（与多数 ETF 一致）。
    """
    if not getattr(g, 'warmup_replay_strict_trade_rules', True):
        return {'paused': False, 'high_limit': None, 'low_limit': None, 'has_limits': False}
    cache = getattr(g, '_warmup_trade_constraints_day_cache', None)
    if isinstance(cache, dict) and security in cache:
        return cache[security]
    result = None
    try:
        df = get_price(
            security,
            start_date=trade_date,
            end_date=trade_date,
            frequency='daily',
            fields=['paused', 'high_limit', 'low_limit', 'pre_close'],
            panel=False,
            skip_paused=False,
        )
    except Exception:
        df = None
    if df is None or df.empty:
        result = None
    else:
        row = df.iloc[-1]
        paused = False
        if 'paused' in df.columns:
            pv = row.get('paused')
            paused = bool(pv) if not pd.isna(pv) else False
        hl = _warmup_finite_positive(row.get('high_limit') if 'high_limit' in df.columns else None)
        ll = _warmup_finite_positive(row.get('low_limit') if 'low_limit' in df.columns else None)
        pre = _warmup_finite_positive(row.get('pre_close') if 'pre_close' in df.columns else None)
        if pre is None:
            try:
                pdf = get_price(
                    security,
                    end_date=trade_date,
                    count=2,
                    frequency='daily',
                    fields=['close'],
                    panel=False,
                    skip_paused=False,
                )
                if pdf is not None and len(pdf) >= 2:
                    pre = _warmup_finite_positive(pdf['close'].iloc[-2])
            except Exception:
                pre = None
        if hl is None and pre is not None:
            hl = round(pre * 1.1, 3)
        if ll is None and pre is not None:
            ll = round(pre * 0.9, 3)
        has_limits = hl is not None and ll is not None
        result = {'paused': paused, 'high_limit': hl, 'low_limit': ll, 'pre_close': pre, 'has_limits': has_limits}
    if isinstance(cache, dict):
        cache[security] = result
    return result


def _warmup_price_triggers_trade_block(price, constraints):
    """与 smart_order_target_value 一致：停牌、涨停价、跌停价均不撮合。"""
    if not constraints:
        return False
    if constraints.get('paused'):
        return True
    p = _coerce_scalar_price(price)
    if p is None or not np.isfinite(p) or p <= 0:
        return True
    hl = constraints.get('high_limit')
    ll = constraints.get('low_limit')
    if hl is not None and p >= hl:
        return True
    if ll is not None and p <= ll:
        return True
    return False


def _coerce_scalar_price(x):
    """将单价强制为 Python float，避免 ndarray 参与比较触发 ambiguous truth value。"""
    if x is None:
        return None
    try:
        arr = np.asarray(x, dtype=float).ravel()
        if arr.size == 0:
            return None
        return float(arr[0])
    except Exception:
        return None


def _replay_decision_price(etf, context, hist_last_close):
    """深度预热：用截至当日 13:10 的分钟价近似 get_current_data().last_price。"""
    try:
        df = get_price(
            etf,
            start_date=context.current_dt.date(),
            end_date=context.current_dt,
            frequency='1m',
            fields=['close'],
            panel=False,
            fill_paused=False,
        )
        if df is not None and len(df) > 0:
            v = float(df['close'].iloc[-1])
            if np.isfinite(v) and v > 0:
                return v
    except Exception:
        pass
    hl = _coerce_scalar_price(hist_last_close)
    if hl is not None and np.isfinite(hl) and hl > 0:
        return hl
    return None


def _make_deep_warmup_context(td, prev_date, warmup_portfolio):
    ctx = type('DeepWarmupCtx', (), {})()
    ctx.current_dt = datetime.combine(td, datetime.min.time()) + timedelta(hours=13, minutes=10)
    ctx.previous_date = prev_date
    ctx.portfolio = warmup_portfolio
    return ctx


def _deep_warmup_apply_eod_range_counter(td):
    """模拟收盘(15:10)对震荡期计数器的更新。"""
    if g.current_filter == '震荡期' and g.range_bound_start_date is not None:
        tds = get_trade_days(start_date=g.range_bound_start_date, end_date=td)
        if tds is not None and len(tds) > 0:
            g.range_bound_days_count = len(tds) - 1


def _deep_warmup_sync_virtual_positions(warmup_portfolio):
    """按当日 13:10 排序结果更新虚拟持仓，使滞回/保留持仓与长回测路径一致。"""
    warmup_portfolio.positions.clear()
    ranked = getattr(g, 'ranked_etfs_result', [])
    targets = []
    if ranked:
        for i in range(min(g.holdings_num, len(ranked))):
            targets.append(ranked[i]['etf'])
    else:
        targets = [g.defensive_etf]
    for etf in targets:
        warmup_portfolio.positions[etf] = SimpleNamespace(
            total_amount=1, avg_cost=0.0, price=1.0
        )


def _trade_days_as_list(raw):
    """聚宽 get_trade_days 可能返回 list / ndarray，统一为按日期顺序的 list。"""
    if raw is None:
        return []
    try:
        if hasattr(raw, 'tolist'):
            raw = raw.tolist()
        seq = list(raw)
    except Exception:
        return []
    return seq


def _warmup_unlock_closeable_amount():
    """仿真交易日开始时，将持仓可卖数量解锁为总持仓。"""
    for _, pos in getattr(getattr(g, '_warmup_sim_portfolio', None), 'positions', {}).items():
        if hasattr(pos, 'total_amount'):
            pos.closeable_amount = int(getattr(pos, 'total_amount', 0) or 0)


def _warmup_order_commission(notional):
    """与 initialize 中 OrderCost(open/close_commission≈0.0001, min_commission=5) 同量级，用于虚拟账户现金流与持仓成本。"""
    if not getattr(g, 'warmup_simulate_order_costs', True):
        return 0.0
    if notional is None or notional <= 0:
        return 0.0
    rate = float(getattr(g, 'warmup_commission_rate', 0.0001))
    mn = float(getattr(g, 'warmup_min_commission', 5.0))
    return max(float(notional) * rate, mn)


def _warmup_execution_slippage_price(raw_price, side):
    """
    与 PriceRelatedSlippage(0.0001) 同向近似：买入成交价略高、卖出略低。
    涨跌停校验仍应对「回放基准价」raw_price 进行，通过后再用本函数得到撮合价。
    """
    if raw_price is None:
        return None
    p = _coerce_scalar_price(raw_price)
    if p is None or p <= 0:
        return None
    if not getattr(g, 'warmup_match_main_slippage', True):
        return float(p)
    r = float(getattr(g, 'warmup_slippage_ratio', 0.0001))
    pv = float(p)
    if side == 'buy':
        return pv * (1.0 + r)
    if side == 'sell':
        return max(pv * (1.0 - r), 1e-6)
    return pv


def _warmup_get_replay_trade_price(etf, dt_for_price, prev_date):
    """获取仿真成交价格，优先分钟13:10价格，回退到上一日收盘。"""
    try:
        ctx = type('WarmupPriceCtx', (), {})()
        ctx.current_dt = dt_for_price
        ctx.previous_date = prev_date
        p = _replay_decision_price(etf, ctx, None)
        p = _coerce_scalar_price(p)
        if p is not None and np.isfinite(p) and p > 0:
            return float(p)
    except Exception:
        pass
    try:
        df = get_price(etf, end_date=prev_date, count=1, frequency='daily', fields=['close'], panel=False)
        if df is not None and len(df) > 0:
            p = float(df['close'].iloc[-1])
            if np.isfinite(p) and p > 0:
                return p
    except Exception:
        pass
    return None


def _warmup_stoploss_bar_eval_price(row, mdf, mode):
    """
    预热分钟止损：单根 K 线上用于和止损线比较的「有效价」。
    - intrabar_low: min(low, close)，无有效 low 时退回 close（对齐主路径 every_bar 的 last_price 常先于收盘触底）。
    - close: 仅 close（历史行为）。
    """
    m = (mode or 'intrabar_low').strip().lower()
    c = _coerce_scalar_price(row.get('close'))
    if c is None or c <= 0:
        return None
    if m == 'close':
        return float(c)
    lo = _coerce_scalar_price(row.get('low')) if mdf is not None and 'low' in getattr(mdf, 'columns', []) else None
    if lo is not None and lo > 0:
        return min(float(lo), float(c))
    return float(c)


def _warmup_simulate_sell_all(etf, warmup_portfolio, price, reason="rebalance"):
    pos = warmup_portfolio.positions.get(etf)
    if pos is None:
        return False
    total = int(getattr(pos, 'total_amount', 0) or 0)
    closeable = int(getattr(pos, 'closeable_amount', total) or 0)
    sellable = min(total, closeable)
    if sellable <= 0 or price is None or price <= 0:
        return False
    td = getattr(g, '_warmup_replay_current_td', None)
    if (
        getattr(g, '_warmup_replay_mode', False)
        and getattr(g, 'warmup_replay_strict_trade_rules', True)
        and td is not None
    ):
        cons = _warmup_security_trade_constraints(etf, td)
        sn = get_security_name(etf)
        if cons is None:
            log.info(f"【仿真交易】卖出跳过 {etf} {sn}: 无日线数据，无法校验停牌/涨跌停")
            return False
        if cons.get('paused'):
            log.info(f"【仿真交易】卖出跳过 {etf} {sn}: 今日停牌")
            return False
        px = _coerce_scalar_price(price)
        if _warmup_price_triggers_trade_block(px, cons):
            hl, ll = cons.get('high_limit'), cons.get('low_limit')
            if hl is not None and px is not None and px >= hl:
                log.info(f"【仿真交易】卖出跳过 {etf} {sn}: 当前涨停，跳过交易")
            elif ll is not None and px is not None and px <= ll:
                log.info(f"【仿真交易】卖出跳过 {etf} {sn}: 当前跌停，跳过交易")
            else:
                log.info(f"【仿真交易】卖出跳过 {etf} {sn}: 价格异常或触达涨跌停边界")
            return False
    exec_price = _warmup_execution_slippage_price(price, 'sell')
    if exec_price is None or exec_price <= 0:
        return False
    gross = float(sellable) * float(exec_price)
    comm = _warmup_order_commission(gross)
    comm = min(comm, gross)
    warmup_portfolio.available_cash += gross - comm
    remaining = total - sellable
    if remaining > 0:
        pos.total_amount = remaining
        pos.closeable_amount = 0
    else:
        warmup_portfolio.positions.pop(etf, None)
    log.debug(f"【仿真交易】卖出 {etf} 数量={sellable} 价(含滑点)={exec_price:.4f} 原因={reason}")
    return True


def _warmup_simulate_buy_target_value(etf, warmup_portfolio, target_value, price, reason="rebalance"):
    if price is None or price <= 0 or target_value <= 0:
        return False
    td = getattr(g, '_warmup_replay_current_td', None)
    if (
        getattr(g, '_warmup_replay_mode', False)
        and getattr(g, 'warmup_replay_strict_trade_rules', True)
        and td is not None
    ):
        cons = _warmup_security_trade_constraints(etf, td)
        sn = get_security_name(etf)
        if cons is None:
            log.info(f"【仿真交易】买入跳过 {etf} {sn}: 无日线数据，无法校验停牌/涨跌停")
            return False
        if cons.get('paused'):
            log.info(f"【仿真交易】买入跳过 {etf} {sn}: 今日停牌")
            return False
        px = _coerce_scalar_price(price)
        if _warmup_price_triggers_trade_block(px, cons):
            hl, ll = cons.get('high_limit'), cons.get('low_limit')
            if hl is not None and px is not None and px >= hl:
                log.info(f"【仿真交易】买入跳过 {etf} {sn}: 当前涨停，跳过交易")
            elif ll is not None and px is not None and px <= ll:
                log.info(f"【仿真交易】买入跳过 {etf} {sn}: 当前跌停，跳过交易")
            else:
                log.info(f"【仿真交易】买入跳过 {etf} {sn}: 价格异常或触达涨跌停边界")
            return False
    exec_price = _warmup_execution_slippage_price(price, 'buy')
    if exec_price is None or exec_price <= 0:
        return False
    cash = float(getattr(warmup_portfolio, 'available_cash', 0.0) or 0.0)
    if cash < g.min_money:
        return False
    tv = float(target_value)
    alloc = min(cash, tv)
    target_amount = int(alloc / exec_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and tv > 0:
        target_amount = 100
    if target_amount <= 0:
        return False
    trade_value = target_amount * exec_price
    if 0 < trade_value < g.min_money:
        return False
    if trade_value < g.min_money:
        return False
    comm = _warmup_order_commission(trade_value)
    total_pay = trade_value + comm
    if cash < total_pay:
        return False
    warmup_portfolio.available_cash -= total_pay
    pos = warmup_portfolio.positions.get(etf)
    if pos is None:
        pos = SimpleNamespace(total_amount=0, closeable_amount=0, avg_cost=0.0, price=exec_price)
        warmup_portfolio.positions[etf] = pos
    old_amount = int(getattr(pos, 'total_amount', 0) or 0)
    old_cost = float(getattr(pos, 'avg_cost', 0.0) or 0.0)
    new_amount = old_amount + target_amount
    if new_amount > 0:
        pos.avg_cost = ((old_amount * old_cost) + total_pay) / new_amount
    pos.total_amount = new_amount
    pos.closeable_amount = int(getattr(pos, 'closeable_amount', 0) or 0)
    pos.price = exec_price
    log.debug(f"【仿真交易】买入 {etf} 数量={target_amount} 价(含滑点)={exec_price:.4f} 原因={reason}")
    return True


def _warmup_pick_targets_from_rank(context):
    """仿真交易使用与实盘一致的目标选择优先级：排名 -> 防御ETF。"""
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    if ranked_etfs:
        return [m['etf'] for m in ranked_etfs[:max(1, int(getattr(g, 'holdings_num', 1)))]]
    if check_defensive_etf_available(context):
        return [g.defensive_etf]
    return []


def _warmup_rank_top_brief(k=3):
    ranked = getattr(g, 'ranked_etfs_result', [])
    out = []
    for item in ranked[:k]:
        if not isinstance(item, dict):
            continue
        out.append(
            f"{item.get('etf','?')}({item.get('etf_name','?')})"
            f"/L={_json_safe_value(item.get('momentum_score'))}"
            f"/S={_json_safe_value(item.get('short_momentum_score'))}"
            f"/R2={_json_safe_value(item.get('r_squared'))}"
        )
    return out


def _warmup_holdings_brief(warmup_portfolio):
    res = []
    for sec, pos in getattr(warmup_portfolio, 'positions', {}).items():
        total = int(getattr(pos, 'total_amount', 0) or 0)
        closeable = int(getattr(pos, 'closeable_amount', 0) or 0)
        avg = float(getattr(pos, 'avg_cost', 0.0) or 0.0)
        if total > 0:
            res.append(f"{sec}:amt={total},closeable={closeable},avg={avg:.4f}")
    res.sort()
    return res


def _warmup_trace_fingerprint(td, pre_filter, post_filter, pre_is_range, post_is_range,
                              pre_range_count, post_range_count, pre_stoploss, post_stoploss,
                              stoploss_events, target_etfs, rank_brief, rebalance_result,
                              holdings_after, warmup_portfolio):
    payload = {
        'td': str(td),
        'pre_filter': pre_filter,
        'post_filter': post_filter,
        'pre_is_range': bool(pre_is_range),
        'post_is_range': bool(post_is_range),
        'pre_range_count': int(pre_range_count),
        'post_range_count': int(post_range_count),
        'pre_stoploss': bool(pre_stoploss),
        'post_stoploss': bool(post_stoploss),
        'stoploss_events': _json_safe_value(stoploss_events),
        'target_etfs': _json_safe_value(target_etfs),
        'rank_top3': _json_safe_value(rank_brief),
        'rebalance': _json_safe_value(rebalance_result),
        'holdings_after': _json_safe_value(holdings_after),
        'cash_after': _json_safe_value(getattr(warmup_portfolio, 'available_cash', None)),
        'range_reason': _json_safe_value(getattr(g, 'today_switch_buffer_audit', None)),
    }
    s = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:16], payload


def _warmup_apply_rebalance(context, warmup_portfolio, target_etfs):
    """仿真交易在13:10执行一次调仓。"""
    target_set = set(target_etfs)
    dt_for_price = context.current_dt
    prev_date = context.previous_date
    sold = []
    bought = []
    for etf in list(warmup_portfolio.positions.keys()):
        if etf in target_set:
            continue
        price = _warmup_get_replay_trade_price(etf, dt_for_price, prev_date)
        if _warmup_simulate_sell_all(etf, warmup_portfolio, price, reason="not_in_target"):
            sold.append(etf)
    current_holdings = [sec for sec, pos in warmup_portfolio.positions.items() if getattr(pos, 'total_amount', 0) > 0]
    need_buy = [etf for etf in target_etfs if etf not in current_holdings]
    remain_slots = max(0, g.holdings_num - len(current_holdings))
    need_buy = need_buy[:remain_slots]
    if not need_buy:
        return {'sold': sold, 'bought': bought}
    n_buy = len(need_buy)
    cash0 = warmup_portfolio.available_cash
    allocated_value_per_etf = cash0 // n_buy
    for i, etf in enumerate(need_buy):
        if i < n_buy - 1:
            target_value = float(allocated_value_per_etf)
        else:
            target_value = (
                float(warmup_portfolio.available_cash)
                if warmup_portfolio.available_cash >= g.min_money
                else float(allocated_value_per_etf)
            )
        price = _warmup_get_replay_trade_price(etf, dt_for_price, prev_date)
        if _warmup_simulate_buy_target_value(etf, warmup_portfolio, target_value, price, reason="target_buy"):
            bought.append(etf)
    return {'sold': sold, 'bought': bought}


def _warmup_simulate_intraday_stoploss(td, prev_date, warmup_portfolio):
    """仿真分钟级止损：遍历盘中分钟线，触发则卖出并置 stop_loss_triggered_today=True。"""
    holdings = [sec for sec, pos in warmup_portfolio.positions.items() if getattr(pos, 'total_amount', 0) > 0]
    audit = _warmup_path_audit_active(td)
    if not holdings:
        if audit:
            log.info(f"📋【预热止损审计】td={td} 无持仓，跳过分钟止损仿真")
        return []
    triggered_events = []
    start_dt = datetime.combine(td, datetime.min.time()) + timedelta(hours=9, minutes=31)
    end_dt = datetime.combine(td, datetime.min.time()) + timedelta(hours=14, minutes=56)
    for etf in holdings:
        pos = warmup_portfolio.positions.get(etf)
        if pos is None:
            continue
        closeable = int(getattr(pos, 'closeable_amount', getattr(pos, 'total_amount', 0)) or 0)
        if closeable <= 0:
            if audit:
                sn = get_security_name(etf)
                log.info(
                    f"📋【预热止损审计】td={td} {etf} {sn} 跳过: closeable=0 "
                    f"(主路径分钟止损同样要求可卖量>0；常见于前一日刚买入的T+1)"
                )
            continue
        mdf = None
        for _fields in (['close', 'low'], ['close']):
            try:
                mdf = get_price(
                    etf,
                    start_date=start_dt,
                    end_date=end_dt,
                    frequency='1m',
                    fields=_fields,
                    panel=False,
                    fill_paused=False,
                )
                if mdf is not None and len(mdf) > 0:
                    break
            except Exception:
                mdf = None
        if mdf is None or len(mdf) == 0:
            if audit:
                log.info(f"📋【预热止损审计】td={td} {etf} 跳过: 无有效分钟线")
            continue
        min_close = None
        min_low = None
        low_diag = bool(getattr(g, 'enable_warmup_stoploss_low_vs_close_diag', False))
        for _, row in mdf.iterrows():
            p = _coerce_scalar_price(row.get('close'))
            if p is None or p <= 0:
                continue
            pv = float(p)
            if min_close is None or pv < min_close:
                min_close = pv
            if low_diag:
                lo = _coerce_scalar_price(row.get('low')) if 'low' in mdf.columns else None
                if lo is None or lo <= 0:
                    lo = p
                lv = float(lo)
                if min_low is None or lv < min_low:
                    min_low = lv
        fixed_stop = None
        pct_stop = None
        avg_c = float(getattr(pos, 'avg_cost', 0.0) or 0.0)
        if g.use_fixed_stop_loss:
            fixed_stop = avg_c * float(g.fixedStopLossThreshold)
        if g.use_pct_stop_loss:
            try:
                ddf = get_price(etf, end_date=prev_date, count=1, frequency='daily', fields=['close'], panel=False)
                if ddf is not None and len(ddf) > 0:
                    pct_stop = float(ddf['close'].iloc[-1]) * float(g.pct_stop_loss_threshold)
            except Exception:
                pct_stop = None
        sl_mode = getattr(g, 'warmup_stoploss_trigger_price_mode', 'intrabar_low')
        triggered_price = None
        for _, row in mdf.iterrows():
            p = _warmup_stoploss_bar_eval_price(row, mdf, sl_mode)
            if p is None:
                continue
            if fixed_stop is not None and p <= fixed_stop:
                triggered_price = p
                break
            if pct_stop is not None and p <= pct_stop:
                triggered_price = p
                break
        if triggered_price is None:
            if audit:
                sn = get_security_name(etf)
                fs = f"{fixed_stop:.4f}" if fixed_stop is not None else "—"
                ps = f"{pct_stop:.4f}" if pct_stop is not None else "—"
                mn = f"{min_close:.4f}" if min_close is not None else "—"
                thr = float(getattr(g, 'fixedStopLossThreshold', 0) or 0)
                extra = ""
                if low_diag and fixed_stop is not None and min_low is not None:
                    mlow = f"{min_low:.4f}"
                    if min_low <= fixed_stop and (min_close is None or min_close > fixed_stop):
                        extra = (
                            f" min_1m_low≈{mlow} | ⚠️低价已穿固定止损线但分钟收盘最低价仍高于线——"
                            f"与主路径 every_bar 使用 last_price 可能在盘中先行触发一致，属口径差异线索"
                        )
                    elif min_low <= fixed_stop:
                        extra = f" min_1m_low≈{mlow}(低价亦穿线，若长测仍未触发请核对虚拟avg_cost)"
                    else:
                        extra = f" min_1m_low≈{mlow}"
                log.info(
                    f"📋【预热止损审计】td={td} {etf} {sn} 未触发: avg_cost={avg_c:.4f} closeable={closeable} "
                    f"fixed_stop_line={fs}(×{thr}) pct_vs_yest_close={ps} min_1m_close≈{mn} bars={len(mdf)}"
                    f"{extra} | 虚拟仓与主仓不一致时请先查 13:10 仿真是否拒单(涨停等)"
                )
            continue
        replay_td = getattr(g, '_warmup_replay_current_td', None)
        if (
            getattr(g, 'warmup_replay_strict_trade_rules', True)
            and replay_td is not None
        ):
            cons = _warmup_security_trade_constraints(etf, replay_td)
            if cons and not cons.get('paused'):
                tp = _coerce_scalar_price(triggered_price)
                if _warmup_price_triggers_trade_block(tp, cons):
                    if audit:
                        log.info(
                            f"📋【预热止损审计】td={td} {etf} 分钟价={float(triggered_price):.4f} 已穿止损线，"
                            f"但严格规则下视为涨跌停/不可撮合，跳过仿真卖出"
                        )
                    continue
        if _warmup_simulate_sell_all(etf, warmup_portfolio, triggered_price, reason="minute_stoploss"):
            g.stop_loss_triggered_today = True
            triggered_events.append({'etf': etf, 'price': float(triggered_price)})
            if audit:
                log.info(
                    f"📋【预热止损审计】td={td} {etf} 触发并仿真卖出 price={float(triggered_price):.4f} "
                    f"avg_cost={avg_c:.4f} trigger_mode={sl_mode}"
                )
        elif audit:
            log.info(
                f"📋【预热止损审计】td={td} {etf} 分钟价已穿止损但 _warmup_simulate_sell_all 未成交(规则/数据拒绝)"
            )
    return triggered_events


def run_deep_warmup_preprocess(context):
    """
    深度预热：按交易日顺序执行"仿真交易回放"，优先复现真实交易路径：
    晨间更新池子 -> 分钟级止损仿真 -> 13:10状态机与选股 -> 13:10调仓 -> 收盘计数更新。
    回放区间：previous_date 起向前 warmup_simulation_trade_days（约束在[90,180]）个交易日。
    """
    if not getattr(g, 'enable_deep_warmup', False):
        return
    if getattr(g, 'warmup_done', False):
        return
    if context.previous_date is None:
        return
    g._warmup_path_audit_banner_done = False
    saved_whipsaw_log = getattr(g, 'log_whipsaw_filter_detail', True)
    try:
        prev_d = _parse_checkpoint_date(context.previous_date)
        warmup_days = int(getattr(g, 'warmup_trade_days', 180))
        sim_days = int(getattr(g, 'warmup_simulation_trade_days', warmup_days))
        sim_days = max(90, min(180, sim_days))
        if not getattr(g, 'enable_warmup_trade_simulation', True):
            sim_days = warmup_days
        min_days = int(getattr(g, 'warmup_min_required_days', 60))
        use_anchor_replay = bool(getattr(g, 'enable_warmup_anchor_replay', False))
        anchor_start = _parse_checkpoint_date(getattr(g, 'warmup_anchor_start_date', None))
        anchor_min_days = int(getattr(g, 'warmup_anchor_min_days', 40))
        anchor_mode_active = False
        if use_anchor_replay and anchor_start is None:
            auto_anchor_days = _trade_days_as_list(get_trade_days(end_date=prev_d, count=sim_days))
            if auto_anchor_days:
                anchor_start = auto_anchor_days[0]
        if use_anchor_replay and anchor_start is not None and anchor_start <= prev_d:
            raw_td = get_trade_days(start_date=anchor_start, end_date=prev_d)
            trade_days = _trade_days_as_list(raw_td)
            anchor_mode_active = True
            log.info(f"📎 【深度预热】锚点全路径回放: {anchor_start} ~ {prev_d}，共{len(trade_days)}个交易日")
        else:
            raw_td = get_trade_days(end_date=prev_d, count=sim_days)
            trade_days = _trade_days_as_list(raw_td)
            if use_anchor_replay:
                log.warning("【深度预热】锚点回放未生效（起点为空或晚于previous_date），回退为最近N日回放")
        required_days = anchor_min_days if anchor_mode_active else min_days
        if len(trade_days) < required_days:
            log.warning(
                f"【深度预热】可用交易日不足（{len(trade_days)}<{required_days}），"
                f"回退为首次震荡期初始化+普通预热"
            )
            g.warmup_done = True
            init_range_bound_status(context)
            run_warmup_preprocess(context)
            return
        if anchor_mode_active and len(trade_days) < min_days:
            log.info(
                f"📎 【深度预热】锚点回放交易日{len(trade_days)}小于全局阈值{min_days}，"
                f"按锚点阈值{required_days}继续执行"
            )
        log.info(f"📎 【深度预热】仿真交易回放: 最近{len(trade_days)}个交易日")
        log.info(f"📎 【深度预热】分钟止损仿真: {'启用' if getattr(g, 'warmup_simulate_minute_stoploss', True) else '禁用'}")
        _warmup_log_path_audit_banner()
        warmup_portfolio = WarmupPortfolio(
            getattr(context.portfolio, 'starting_cash', context.portfolio.total_value)
        )
        g._warmup_sim_portfolio = warmup_portfolio
        g._warmup_replay_mode = True
        if getattr(g, 'deep_warmup_reduce_log', True):
            g.log_whipsaw_filter_detail = False
        last_target = None
        last_candidates = []
        trace_enabled = bool(getattr(g, 'enable_warmup_trace_log', False))
        fingerprint_enabled = bool(getattr(g, 'enable_warmup_fingerprint_log', True))
        trace_last_n = max(1, int(getattr(g, 'warmup_trace_last_n_days', 25)))
        total_days = len(trade_days)
        for day_idx, td in enumerate(trade_days, start=1):
            pair = get_trade_days(end_date=td, count=2)
            prev_date = pair[0] if pair is not None and len(pair) >= 2 else None
            if prev_date is None:
                continue
            g._warmup_replay_current_td = td
            g._warmup_trade_constraints_day_cache = {}
            _warmup_unlock_closeable_amount()
            if getattr(g, 'enable_warmup_state_reconcile', True):
                g.stop_loss_triggered_today = False
            pre_filter = getattr(g, 'current_filter', None)
            pre_is_range = bool(getattr(g, 'is_range_bound', False))
            pre_range_count = int(getattr(g, 'range_bound_days_count', 0))
            pre_stoploss = bool(getattr(g, 'stop_loss_triggered_today', False))
            holdings_before = _warmup_holdings_brief(warmup_portfolio)
            fake_context = _make_deep_warmup_context(td, prev_date, warmup_portfolio)
            fake_context.current_dt = datetime.combine(td, datetime.min.time()) + timedelta(hours=9, minutes=0)
            calculate_global_etf_threshold(fake_context)
            update_sector_pool(fake_context)
            filter_fixed_pool_by_volume(fake_context)
            daily_merge_etf_pools(fake_context)
            stoploss_events = []
            if getattr(g, 'warmup_simulate_minute_stoploss', True):
                stoploss_events = _warmup_simulate_intraday_stoploss(td, prev_date, warmup_portfolio)
            fake_context.current_dt = datetime.combine(td, datetime.min.time()) + timedelta(hours=13, minutes=10)
            check_and_exit_range_bound_mode(fake_context)
            check_and_enter_range_bound_mode(fake_context)
            g.today_switch_buffer_audit = None
            calculate_and_log_ranked_etfs(fake_context)
            target_etfs = _warmup_pick_targets_from_rank(fake_context)
            rebalance_result = _warmup_apply_rebalance(fake_context, warmup_portfolio, target_etfs)
            _deep_warmup_apply_eod_range_counter(td)
            _warmup_eod_reconcile_state(td)
            if _warmup_path_audit_active(td):
                rb_start = getattr(g, 'range_bound_start_date', None)
                span_rb = None
                if rb_start is not None:
                    try:
                        raw_span = get_trade_days(start_date=rb_start, end_date=td)
                        if raw_span is not None and len(raw_span) > 0:
                            span_rb = len(raw_span) - 1
                    except Exception:
                        span_rb = None
                log.info(
                    "📋【预热状态审计·日终】"
                    f"td={td} filter={getattr(g, 'current_filter', None)} "
                    f"risk_state={getattr(g, 'risk_state', None)} "
                    f"range_bound_start={rb_start} span_trade_days_minus1={span_rb} "
                    f"range_bound_days_count={getattr(g, 'range_bound_days_count', None)} "
                    f"last_switch_date={getattr(g, 'last_switch_date', None)} "
                    f"stoploss_events={stoploss_events} "
                    f"(注:13:10进入震荡若消费止损标志，g.stop_loss_triggered_today 可能被清零，以 stoploss_events 为准) "
                    f"targets={target_etfs} rebalance={rebalance_result} "
                    f"v_cash={_json_safe_value(getattr(warmup_portfolio, 'available_cash', None))} "
                    f"v_holdings={_warmup_holdings_brief(warmup_portfolio)}"
                )
            if trace_enabled and day_idx > total_days - trace_last_n:
                post_filter = getattr(g, 'current_filter', None)
                post_is_range = bool(getattr(g, 'is_range_bound', False))
                post_range_count = int(getattr(g, 'range_bound_days_count', 0))
                post_stoploss = bool(getattr(g, 'stop_loss_triggered_today', False))
                rank_brief = _warmup_rank_top_brief(3)
                holdings_after = _warmup_holdings_brief(warmup_portfolio)
                log.info(
                    "🔍【预热追踪】"
                    f"day={day_idx}/{total_days} td={td} prev={prev_date} "
                    f"filter:{pre_filter}->{post_filter} range:{pre_is_range}->{post_is_range} "
                    f"range_cnt:{pre_range_count}->{post_range_count} "
                    f"stoploss_flag:{pre_stoploss}->{post_stoploss} "
                    f"pool_sz={len(getattr(g, 'merged_etf_pool', []) or [])} "
                    f"liq_th={_json_safe_value(getattr(g, 'global_etf_liquidity_threshold', None))}"
                )
                log.info(
                    "🔍【预热追踪】"
                    f"td={td} stoploss_events={stoploss_events} "
                    f"target={target_etfs} top3={rank_brief}"
                )
                log.info(
                    "🔍【预热追踪】"
                    f"td={td} rebalance={rebalance_result} "
                    f"holdings_before={holdings_before} holdings_after={holdings_after} "
                    f"cash={_json_safe_value(getattr(warmup_portfolio, 'available_cash', None))}"
                )
                if fingerprint_enabled:
                    fp, fp_payload = _warmup_trace_fingerprint(
                        td, pre_filter, post_filter, pre_is_range, post_is_range,
                        pre_range_count, post_range_count, pre_stoploss, post_stoploss,
                        stoploss_events, target_etfs, rank_brief, rebalance_result,
                        holdings_after, warmup_portfolio
                    )
                    log.info(f"🧬【预热指纹】td={td} fp={fp}")
                    log.info(
                        "🧬【预热指纹详情】"
                        f"td={td} core={_json_safe_value(fp_payload)}"
                    )
            ranked = getattr(g, 'ranked_etfs_result', [])
            if ranked:
                last_target = ranked[0]['etf']
                last_candidates = [m['etf'] for m in ranked[: getattr(g, 'warmup_sync_max_candidates', 3)]]
            else:
                last_target = g.defensive_etf
                last_candidates = [g.defensive_etf]
        g.warmup_virtual_positions = {
            k: v for k, v in warmup_portfolio.positions.items()
        }
        g.warmup_virtual_cash = warmup_portfolio.available_cash
        g.warmup_done = True
        if last_target:
            g.warmup_pending_sync = True
            ordered_sync = []
            for etf in [last_target] + (last_candidates or []):
                if etf and etf not in ordered_sync:
                    ordered_sync.append(etf)
            g.warmup_sync_target_etfs = ordered_sync[
                : max(1, int(getattr(g, 'warmup_sync_max_candidates', 3)))
            ]
            log.info(
                f"✅ 【深度预热】完成，共回放{len(trade_days)}个交易日；"
                f"当前滤波器={g.current_filter}，震荡期计数={getattr(g, 'range_bound_days_count', 0)}；"
                f"启动后同步主目标: {g.warmup_sync_target_etfs[0]}，备选: {g.warmup_sync_target_etfs[1:]}"
            )
        else:
            g.warmup_pending_sync = False
            g.warmup_sync_target_etfs = []
            log.info(f"✅ 【深度预热】完成，共回放{len(trade_days)}个交易日；未形成可同步目标持仓")
    except Exception as e:
        g.warmup_done = True
        g.warmup_pending_sync = False
        g.warmup_sync_target_etfs = []
        log.warning(f"【深度预热】异常，回退为首次震荡期初始化+普通预热: {e}")
        init_range_bound_status(context)
        run_warmup_preprocess(context)
    finally:
        g.log_whipsaw_filter_detail = saved_whipsaw_log
        g._warmup_replay_mode = False
        g._warmup_sim_portfolio = None
        g._warmup_replay_current_td = None
        g._warmup_trade_constraints_day_cache = None


def _warmup_pick_target_etfs(replay_date, max_candidates=3):
    """预热模式下用日线代理挑选目标ETF与备选（用于校准状态，不替代实盘选股）"""
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        return []
    lookback = int(max(g.lookback_days, g.short_momentum_lookback) + 5)
    candidates = []
    for etf in g.merged_etf_pool:
        try:
            df = get_price(etf, end_date=replay_date, count=lookback, frequency='daily', fields=['close'], panel=False)
            if df is None or len(df) < g.lookback_days + 1:
                continue
            closes = df['close'].values
            score, _, r2 = calculate_momentum_score(closes, g.lookback_days)
            if score is None:
                continue
            if not (g.min_score_threshold <= score <= g.max_score_threshold):
                continue
            if g.enable_r2_filter and (r2 is None or r2 <= g.r2_threshold):
                continue
            candidates.append((etf, score))
        except Exception:
            continue
    if not candidates:
        return []
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [c[0] for c in candidates[:max(1, int(max_candidates))]]


def run_warmup_preprocess(context):
    """在回测/实盘启动前做预热回放，尽量让状态机延续到当前起点。"""
    if not getattr(g, 'enable_warmup', False):
        return
    if getattr(g, 'warmup_done', False):
        return
    if context.previous_date is None:
        return
    try:
        warmup_days = int(getattr(g, 'warmup_trade_days', 180))
        min_days = int(getattr(g, 'warmup_min_required_days', 60))
        trade_days = get_trade_days(end_date=context.previous_date, count=warmup_days)
        if trade_days is None or len(trade_days) < min_days:
            log.warning(f"【预热】可用交易日不足（{len(trade_days) if trade_days is not None else 0}天），跳过预热")
            g.warmup_done = True
            return
        warmup_portfolio = WarmupPortfolio(getattr(context.portfolio, 'starting_cash', context.portfolio.total_value))
        last_target = None
        last_candidates = []
        for td in trade_days:
            pair = get_trade_days(end_date=td, count=2)
            prev_date = pair[0] if pair is not None and len(pair) >= 2 else td
            fake_context = type('WarmupContext', (), {})()
            fake_context.current_dt = datetime.combine(td, datetime.min.time()) + timedelta(hours=13, minutes=10)
            fake_context.previous_date = prev_date
            fake_context.portfolio = warmup_portfolio
            calculate_global_etf_threshold(fake_context)
            update_sector_pool(fake_context)
            filter_fixed_pool_by_volume(fake_context)
            daily_merge_etf_pools(fake_context)
            check_and_exit_range_bound_mode(fake_context)
            check_and_enter_range_bound_mode(fake_context)
            picked = _warmup_pick_target_etfs(td, getattr(g, 'warmup_sync_max_candidates', 3))
            target = picked[0] if picked else None
            if target is None and check_defensive_etf_available(fake_context):
                target = g.defensive_etf
            last_target = target
            last_candidates = picked[:] if picked else []
            if target and target not in last_candidates:
                last_candidates.insert(0, target)
            current_positions = list(warmup_portfolio.positions.keys())
            for held in current_positions:
                if held != target:
                    warmup_portfolio.positions.pop(held, None)
            if target and target not in warmup_portfolio.positions:
                warmup_portfolio.positions[target] = {'total_amount': 1, 'avg_cost': 0}
        g.warmup_virtual_positions = dict(warmup_portfolio.positions)
        g.warmup_virtual_cash = warmup_portfolio.available_cash
        g.warmup_done = True
        if last_target:
            g.warmup_pending_sync = True
            ordered_sync = []
            for etf in [last_target] + last_candidates:
                if etf and etf not in ordered_sync:
                    ordered_sync.append(etf)
            g.warmup_sync_target_etfs = ordered_sync[:max(1, int(getattr(g, 'warmup_sync_max_candidates', 3)))]
            log.info(
                f"✅ 【预热】完成，共回放{len(trade_days)}个交易日；"
                f"启动后同步主目标: {g.warmup_sync_target_etfs[0]}，备选: {g.warmup_sync_target_etfs[1:]}"
            )
        else:
            g.warmup_pending_sync = False
            g.warmup_sync_target_etfs = []
            log.info(f"✅ 【预热】完成，共回放{len(trade_days)}个交易日；未形成可同步目标持仓")
    except Exception as e:
        g.warmup_done = True
        g.warmup_pending_sync = False
        g.warmup_sync_target_etfs = []
        log.warning(f"【预热】回放异常，已跳过预热: {e}")


# ==================== 震荡收割(Whipsaw)辅助函数 ====================

def _whipsaw_global_period_ok():
    """总开关 whipsaw_options_only_in_range：为 True 时，各项震荡收割子逻辑仅在震荡期才允许启用"""
    if not getattr(g, 'whipsaw_options_only_in_range', True):
        return True
    return getattr(g, 'current_filter', '正常期') == '震荡期'

def _use_smoothed_momentum_prices():
    """方法1：是否对动量输入价序列做均线平滑"""
    if not getattr(g, 'enable_smoothed_momentum_input', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    if getattr(g, 'smoothed_momentum_only_in_range', True):
        return getattr(g, 'current_filter', '正常期') == '震荡期'
    return True

def _use_range_long_momentum_limits():
    """方法3：是否启用震荡期长期动量区间（与全局 min/max 取交集）"""
    if not getattr(g, 'enable_range_momentum_floor', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    return getattr(g, 'current_filter', '正常期') == '震荡期'

def _use_range_short_momentum_limits():
    """震荡期短期动量区间开关：启用且当前为震荡期（受 whipsaw_options_only_in_range 约束）"""
    if not getattr(g, 'enable_range_short_momentum_limits', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    return getattr(g, 'current_filter', '正常期') == '震荡期'

def _dual_positive_filter_should_apply():
    """方法5：双正筛是否参与过滤"""
    if not getattr(g, 'enable_dual_positive_momentum', False):
        return False
    if not _whipsaw_global_period_ok():
        return False
    if getattr(g, 'dual_positive_only_in_range', True):
        return getattr(g, 'current_filter', '正常期') == '震荡期'
    return True

def _effective_r2_threshold():
    """动态 R² 阈值：方法2 — 震荡期使用更高 R²（需总开关+enable_range_r2_veto）"""
    base = getattr(g, 'r2_threshold', 0.4)
    if not getattr(g, 'enable_range_r2_veto', False):
        return base
    if not _whipsaw_global_period_ok():
        return base
    if getattr(g, 'current_filter', '正常期') != '震荡期':
        return base
    return getattr(g, 'r2_threshold_range_bound', 0.85)

def get_price_at_1310(etf, target_date):
    """获取指定ETF在target_date的13:10价格（1分钟线最后价）"""
    try:
        t1310 = datetime.combine(target_date, datetime.strptime("13:10:00", "%H:%M:%S").time())
        minute_df = get_price(etf, start_date=target_date, end_date=t1310, frequency='1m', fields=['close'], panel=False, skip_paused=False)
        if minute_df is None or minute_df.empty:
            return None
        px = minute_df['close'].iloc[-1]
        if pd.isna(px) or px <= 0:
            return None
        return float(px)
    except Exception:
        return None

def get_effective_score_threshold_ratio(score_key, top_10):
    """计算动态候选池阈值比例（按市场状态）"""
    ratio = getattr(g, 'score_threshold_ratio', 0.9)
    notes = []
    if getattr(g, 'enable_dynamic_score_threshold', False):
        if getattr(g, 'current_filter', '正常期') == '震荡期':
            ratio = getattr(g, 'range_score_threshold_ratio', ratio)
        else:
            ratio = getattr(g, 'normal_score_threshold_ratio', ratio)
        notes.append(f"状态基准={ratio:.3f}")
    ratio = min(max(ratio, getattr(g, 'score_threshold_threshold_min', 0.82)), getattr(g, 'score_threshold_ratio_max', 0.95))
    return ratio, notes

def get_filter_block_reasons(metrics, use_short_momentum):
    """返回ETF被过滤/受限的原因列表（用于诊断日志）"""
    reasons = []
    score_key = 'short_momentum_score' if use_short_momentum else 'momentum_score'
    score = metrics.get(score_key, float('-inf'))
    if use_short_momentum:
        min_threshold = float(metrics.get('effective_short_min_score_threshold', g.short_momentum_min_score))
        max_threshold = float(metrics.get('effective_short_max_score_threshold', g.short_momentum_max_score))
    else:
        min_threshold = float(metrics.get('effective_min_score_threshold', g.min_score_threshold))
        max_threshold = float(metrics.get('effective_max_score_threshold', g.max_score_threshold))
    if score < min_threshold:
        reasons.append(f"{'短期' if use_short_momentum else '原'}动量得分低于下限({score:.4f}<{min_threshold:.4f})")
    if score > max_threshold:
        reasons.append(f"{'短期' if use_short_momentum else '原'}动量得分高于上限({score:.4f}>{max_threshold:.4f})")
    if not metrics.get('passed_whipsaw_short_band', True):
        sm = metrics.get('short_momentum_score')
        lo = float(metrics.get('effective_short_min_score_threshold', g.short_momentum_min_score))
        hi = float(metrics.get('effective_short_max_score_threshold', g.short_momentum_max_score))
        sm_str = f"{sm:.4f}" if sm is not None else "N/A"
        reasons.append(f"震荡期短期动量区间未满足({sm_str} ∉ [{lo:.4f},{hi:.4f}])")
    if g.enable_r2_filter and not metrics.get('passed_r2', False):
        eff_r2 = metrics.get('effective_r2_threshold', getattr(g, 'r2_threshold', 0.4))
        reasons.append(f"R²未达标({metrics.get('r_squared', float('nan')):.3f}<=有效阈值{eff_r2:.3f})")
    if metrics.get('dual_positive_filter_active', False) and not metrics.get('passed_dual_positive', False):
        reasons.append("长短动量双正未满足(需长、短动量得分均>0)")
    if g.enable_volume_check and not metrics.get('passed_volume', False):
        vr = metrics.get('volume_ratio')
        vr_str = f"{vr:.2f}" if vr is not None else "N/A"
        reasons.append(f"成交量比未达标({vr_str}>={g.volume_threshold:.2f}或不可用)")
    if g.enable_loss_filter and not metrics.get('passed_loss', False):
        day_ratios = metrics.get('day_ratios', [])
        min_ratio = min(day_ratios) if day_ratios else float('nan')
        reasons.append(f"短期风控未达标(近3日最小比值{min_ratio:.4f}<{g.loss:.4f})")
    if g.enable_premium_filter and not metrics.get('passed_premium', False):
        premium = metrics.get('premium_rate')
        premium_str = f"{premium:.2f}%" if premium is not None else "N/A"
        reasons.append(f"溢价率未达标({premium_str}>{g.max_premium_rate:.2f}%)")
    if g.enable_range_bound_mode and not metrics.get('passed_filter', False):
        reasons.append(f"动态滤波未达标(当前{g.current_filter})")
    return reasons

def get_trade_block_reasons(security, current_data, replay_price=None, replay_trade_date=None):
    """返回标的当前可交易性限制原因（用于诊断，不直接影响筛选）"""
    reasons = []
    try:
        if current_data is not None:
            if security not in current_data:
                return ["实时行情缺失(无法判断停牌/涨跌停)"]
            cd = current_data[security]
            if getattr(cd, 'paused', False):
                reasons.append("停牌")
            last_price = getattr(cd, 'last_price', None)
            high_limit = getattr(cd, 'high_limit', None)
            low_limit = getattr(cd, 'low_limit', None)
            if last_price is None or np.isnan(last_price) or last_price <= 0:
                reasons.append("最新价异常")
            if high_limit is not None and last_price is not None and last_price >= high_limit:
                reasons.append("涨停")
            if low_limit is not None and last_price is not None and last_price <= low_limit:
                reasons.append("跌停")
            return reasons
        if (
            replay_trade_date is not None
            and replay_price is not None
            and getattr(g, '_warmup_replay_mode', False)
            and getattr(g, 'warmup_replay_strict_trade_rules', True)
        ):
            cons = _warmup_security_trade_constraints(security, replay_trade_date)
            if cons is None:
                return ["回放/预热:无日线数据(无法判断停牌涨跌停)"]
            if cons.get('paused'):
                reasons.append("停牌")
                return reasons
            lp = _coerce_scalar_price(replay_price)
            if lp is None or not np.isfinite(lp) or lp <= 0:
                reasons.append("最新价异常")
                return reasons
            if _warmup_price_triggers_trade_block(lp, cons):
                hl = cons.get('high_limit')
                ll = cons.get('low_limit')
                if hl is not None and lp >= hl:
                    reasons.append("涨停")
                elif ll is not None and lp <= ll:
                    reasons.append("跌停")
                else:
                    reasons.append("价格触达涨跌停边界(与主回测一致跳过)")
            return reasons
        if current_data is None:
            return ["回放/预热模式无实时行情(跳过停牌涨跌停判断)"]
    except Exception as e:
        reasons.append(f"可交易性检查异常:{e}")
    return reasons

def get_filter_pass_status(metrics, use_short_momentum):
    """返回审计用过滤通过状态明细"""
    score_key = 'short_momentum_score' if use_short_momentum else 'momentum_score'
    score = metrics.get(score_key, float('-inf'))
    if use_short_momentum:
        min_threshold = float(metrics.get('effective_short_min_score_threshold', g.short_momentum_min_score))
        max_threshold = float(metrics.get('effective_short_max_score_threshold', g.short_momentum_max_score))
    else:
        min_threshold = float(metrics.get('effective_min_score_threshold', g.min_score_threshold))
        max_threshold = float(metrics.get('effective_max_score_threshold', g.max_score_threshold))
    momentum_pass = (score >= min_threshold and score <= max_threshold)
    eff_r2 = metrics.get('effective_r2_threshold', getattr(g, 'r2_threshold', 0.4))
    dual_line = ""
    if metrics.get('dual_positive_filter_active', False):
        dual_line = f"长短双正(Whipsaw): {'✅' if metrics.get('passed_dual_positive', False) else '❌'}；"
    status = [
        f"{'短期' if use_short_momentum else '原'}动量阈值: {'✅' if momentum_pass else '❌'} ({score:.4f} in [{min_threshold:.4f},{max_threshold:.4f}])",
        f"{dual_line}R²过滤(有效阈值{eff_r2:.3f}): {'✅' if (not g.enable_r2_filter or metrics.get('passed_r2', False)) else '❌'}",
        f"成交量过滤: {'✅' if (not g.enable_volume_check or metrics.get('passed_volume', False)) else '❌'}",
        f"短期风控过滤: {'✅' if (not g.enable_loss_filter or metrics.get('passed_loss', False)) else '❌'}",
        f"溢价率过滤: {'✅' if (not g.enable_premium_filter or metrics.get('passed_premium', False)) else '❌'}",
        f"动态滤波过滤({g.current_filter}): {'✅' if (not g.enable_range_bound_mode or metrics.get('passed_filter', False)) else '❌'}",
    ]
    return status

def summarize_chase_events():
    """汇总放强追弱/放弱追强事件统计，用于收盘诊断面板"""
    events = getattr(g, 'chase_events', [])
    if not events:
        return ["【放强追弱统计】暂无事件样本（尚未出现可复盘的真实换仓）"]
    total = len(events)
    whipsaw_events = [e for e in events if e.get('event_type') == '放强追弱']
    chase_events = [e for e in events if e.get('event_type') == '放弱追强']
    whipsaw_count = len(whipsaw_events)
    chase_count = len(chase_events)
    spread_values = [e.get('spread', 0.0) for e in events]
    avg_spread = float(np.mean(spread_values)) if spread_values else 0.0
    median_spread = float(np.median(spread_values)) if spread_values else 0.0
    lines = [
        "📊 ========== 放强追弱事件统计面板（累计） ==========",
        f"样本总数: {total} | 放强追弱: {whipsaw_count} ({(whipsaw_count / total):.2%}) | 放弱追强: {chase_count} ({(chase_count / total):.2%})",
        f"收益差spread(买入-卖出继续持有): 均值={avg_spread:.2%}, 中位数={median_spread:.2%}",
    ]
    reason_counts = {}
    for e in whipsaw_events:
        reasons = e.get('selection_reasons') or []
        if not reasons:
            reason_counts['无明确未选最强原因'] = reason_counts.get('无明确未选最强原因', 0) + 1
            continue
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    if reason_counts:
        lines.append("放强追弱-未选最强原因分组：")
        sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        for reason, cnt in sorted_reasons[:8]:
            lines.append(f"  - {reason}: {cnt}次")
    state_stats = {}
    for e in events:
        state = e.get('filter_state', '未知')
        if state not in state_stats:
            state_stats[state] = {'total': 0, 'whipsaw': 0, 'chase': 0}
        state_stats[state]['total'] += 1
        if e.get('event_type') == '放强追弱':
            state_stats[state]['whipsaw'] += 1
        else:
            state_stats[state]['chase'] += 1
    if state_stats:
        lines.append("按市场状态分组：")
        for state, stat in state_stats.items():
            total_state = stat['total']
            whipsaw_ratio = (stat['whipsaw'] / total_state) if total_state else 0
            lines.append(
                f"  - {state}: 样本{total_state}，放强追弱{stat['whipsaw']}({whipsaw_ratio:.2%})，放弱追强{stat['chase']}"
            )
    lines.append("====================================================")
    return lines

def summarize_switch_buffer_effect_events():
    """汇总差值门控拦截复盘统计（累计）"""
    events = getattr(g, 'switch_buffer_effect_events', [])
    if not events:
        return ["【差值门控拦截统计】暂无复盘样本（尚未形成次日13:10对比）"]
    total = len(events)
    benefits = [e.get('benefit', 0.0) for e in events]
    win_count = len([x for x in benefits if x > 0])
    loss_count = len([x for x in benefits if x < 0])
    avg_benefit = float(np.mean(benefits)) if benefits else 0.0
    median_benefit = float(np.median(benefits)) if benefits else 0.0
    p25 = float(np.percentile(benefits, 25)) if len(benefits) >= 2 else avg_benefit
    p75 = float(np.percentile(benefits, 75)) if len(benefits) >= 2 else avg_benefit
    valid_ret_events = [
        e for e in events
        if np.isfinite(e.get('keep_ret', float('nan')))
        and np.isfinite(e.get('blocked_ret', float('nan')))
        and e.get('keep_ret', float('nan')) > -1
        and e.get('blocked_ret', float('nan')) > -1
    ]
    keep_curve = [1.0 + e.get('keep_ret', 0.0) for e in valid_ret_events]
    blocked_curve = [1.0 + e.get('blocked_ret', 0.0) for e in valid_ret_events]
    keep_cum_ret = float(np.prod(keep_curve) - 1.0) if keep_curve else 0.0
    blocked_cum_ret = float(np.prod(blocked_curve) - 1.0) if blocked_curve else 0.0
    cum_excess_ret = keep_cum_ret - blocked_cum_ret
    valid_delta_events = [e for e in events if np.isfinite(e.get('switch_delta', float('nan')))]
    delta_values = [e.get('switch_delta') for e in valid_delta_events]
    avg_delta = float(np.mean(delta_values)) if delta_values else 0.0
    median_delta = float(np.median(delta_values)) if delta_values else 0.0
    long_d = [e.get('long_delta_keep_block') for e in events if np.isfinite(e.get('long_delta_keep_block', float('nan')))]
    short_d = [e.get('short_delta_keep_block') for e in events if np.isfinite(e.get('short_delta_keep_block', float('nan')))]
    avg_long_d = float(np.mean(long_d)) if long_d else float('nan')
    avg_short_d = float(np.mean(short_d)) if short_d else float('nan')
    lines = [
        "🧪 ========== 差值门控拦截效果面板（累计） ==========",
        f"样本总数: {total} | 拦截有利: {win_count} ({(win_count / total):.2%}) | 拦截不利: {loss_count} ({(loss_count / total):.2%})",
        f"收益差benefit(保留-不拦截): 均值={avg_benefit:.2%}, 中位数={median_benefit:.2%}, P25={p25:.2%}, P75={p75:.2%}",
        (
            f"累计收益(按复盘样本复利): 实际拦截后={keep_cum_ret:.2%}, "
            f"若不拦截={blocked_cum_ret:.2%}, 超额(拦截-不拦截)={cum_excess_ret:.2%}"
            if keep_curve else
            "累计收益(按复盘样本复利): 暂无有效收益样本"
        ),
        f"switch_delta分布: 有效样本{len(delta_values)}/{total}, 均值={avg_delta:.4f}, 中位数={median_delta:.4f}",
        (
            f"长期差值(保留-放弃): 有效样本{len(long_d)}/{total}, 均值={avg_long_d:.4f}"
            if np.isfinite(avg_long_d) else
            "长期差值(保留-放弃): 无有效样本"
        ),
        (
            f"短期差值(保留-放弃): 有效样本{len(short_d)}/{total}, 均值={avg_short_d:.4f}"
            if np.isfinite(avg_short_d) else
            "短期差值(保留-放弃): 无有效样本"
        ),
    ]
    state_stats = {}
    for e in events:
        state = e.get('filter_state', '未知')
        if state not in state_stats:
            state_stats[state] = {'total': 0, 'win': 0, 'sum': 0.0}
        state_stats[state]['total'] += 1
        if e.get('benefit', 0.0) > 0:
            state_stats[state]['win'] += 1
        state_stats[state]['sum'] += e.get('benefit', 0.0)
    lines.append("按市场状态分组：")
    for state, stat in state_stats.items():
        avg_state = stat['sum'] / stat['total'] if stat['total'] else 0.0
        lines.append(
            f"  - {state}: 样本{stat['total']}，有利{stat['win']}({(stat['win'] / stat['total']):.2%})，均值{avg_state:.2%}"
        )
    lines.append("====================================================")
    return lines

def format_chase_snapshot_line(label, d, snap):
    """格式化放强追弱/放弱追强诊断日志单行"""
    if snap['long_score'] is None:
        return f"  - {label}({d})13:10: 数据不足，无法计算长短动量"
    volume_ratio_str = "{:.2f}".format(snap['volume_ratio']) if snap['volume_ratio'] is not None else "N/A"
    short_risk_str = "{:.4f}".format(snap['short_risk']) if snap['short_risk'] is not None else "N/A"
    premium_str = "{:.2f}%".format(snap['premium_rate']) if snap['premium_rate'] is not None else "N/A"
    laplace_slope_str = "{:.4f}".format(snap['laplace_slope']) if snap['laplace_slope'] is not None else "N/A"
    gaussian_slope_str = "{:.4f}".format(snap['gaussian_slope']) if snap['gaussian_slope'] is not None else "N/A"
    passed_laplace = (snap['laplace_slope'] is not None and snap['laplace_slope'] > g.laplace_min_slope)
    passed_gaussian = (snap['gaussian_slope'] is not None and snap['gaussian_slope'] > g.gaussian_min_slope)
    return (
        f"  - {label}({d})13:10: 长期动量={snap['long_score']:.4f}, 长期年化={snap['long_ann']:.2%}, 长期R²={snap['long_r2']:.3f}; "
        f"短期动量={snap['short_score']:.4f}, 短期年化={snap['short_ann']:.2%}, 短期R²={snap['short_r2']:.3f}; "
        f"R²: {snap['long_r2']:.3f} {'✅' if snap['passed_r2'] else '❌'}，"
        f"成交量比值: {volume_ratio_str} {'✅' if snap['passed_volume'] else '❌'}，"
        f"短期风控: {short_risk_str} {'✅' if snap['passed_short_risk'] else '❌'}，"
        f"溢价率: {premium_str} {'✅' if snap['passed_premium'] else '❌'}，"
        f"拉普拉斯斜率: {laplace_slope_str} {'✅' if passed_laplace else '❌'}，"
        f"高斯斜率: {gaussian_slope_str} {'✅' if passed_gaussian else '❌'}"
    )

def build_momentum_snapshot_for_dates(etf, target_dates):
    """计算指定ETF在多个日期13:10时点的长短动量与评分快照（用于诊断日志）"""
    snapshots = []
    if not target_dates:
        return snapshots
    lookback_need = max(g.lookback_days, g.short_momentum_lookback, g.volume_lookback) + 5
    for d in target_dates:
        item = {'date': d, 'long_score': None, 'long_ann': None, 'long_r2': None,
                'short_score': None, 'short_ann': None, 'short_r2': None,
                'volume_ratio': None, 'short_risk': None, 'premium_rate': None,
                'laplace_slope': None, 'gaussian_slope': None,
                'passed_r2': False, 'passed_volume': False, 'passed_short_risk': False,
                'passed_premium': False}
        try:
            trade_pair = get_trade_days(end_date=d, count=2)
            if len(trade_pair) < 2:
                snapshots.append(item)
                continue
            prev_trade_day = trade_pair[-2]
            hist_df = get_price(etf, end_date=prev_trade_day, count=lookback_need, frequency='1d', fields=['close', 'volume'], panel=False, skip_paused=False)
            if hist_df is None or hist_df.empty:
                snapshots.append(item)
                continue
            hist_closes = hist_df['close'].values
            hist_volumes = hist_df['volume'].values if 'volume' in hist_df.columns else np.array([])
            if len(hist_closes) < lookback_need:
                snapshots.append(item)
                continue
            t1310 = datetime.combine(d, datetime.strptime("13:10:00", "%H:%M:%S").time())
            minute_df = get_price(etf, start_date=d, end_date=t1310, frequency='1m', fields=['close', 'volume'], panel=False, skip_paused=False)
            if minute_df is None or minute_df.empty:
                snapshots.append(item)
                continue
            current_price = minute_df['close'].iloc[-1]
            if pd.isna(current_price) or current_price <= 0:
                snapshots.append(item)
                continue
            today_vol = float(minute_df['volume'].sum()) if 'volume' in minute_df.columns else 0.0
            price_series = np.append(hist_closes, float(current_price))
            long_score, long_ann, long_r2 = calculate_momentum_score(price_series, g.lookback_days)
            short_score, short_ann, short_r2 = calculate_momentum_score(price_series, g.short_momentum_lookback)
            volume_ratio = None
            if hist_volumes is not None and len(hist_volumes) >= g.volume_lookback:
                past_n_days_vol = hist_volumes[-g.volume_lookback:]
                if np.all(~np.isnan(past_n_days_vol)) and np.all(past_n_days_vol > 0):
                    avg_volume = np.mean(past_n_days_vol)
                    if avg_volume > 0:
                        projected_today_vol = today_vol * (240.0 / 130.0)
                        volume_ratio = projected_today_vol / avg_volume
            short_risk = None
            if len(price_series) >= 4:
                day1 = price_series[-1] / price_series[-2]
                day2 = price_series[-2] / price_series[-3]
                day3 = price_series[-3] / price_series[-4]
                short_risk = min(day1, day2, day3)
            premium_rate = None
            try:
                close_df = get_price(etf, start_date=d, end_date=d, fields=['close'], panel=False)
                nav_df = get_extras('unit_net_value', etf, start_date=d, end_date=d)
                if close_df is not None and len(close_df) > 0 and nav_df is not None and len(nav_df) > 0:
                    close_px = float(close_df['close'].iloc[-1])
                    nav = float(nav_df.iloc[-1].values[0])
                    if nav > 0:
                        premium_rate = (close_px - nav) / nav * 100
            except Exception:
                premium_rate = None
            laplace_slope = None
            gaussian_slope = None
            if len(price_series) >= 10:
                try:
                    laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                    if len(laplace_values) >= 2:
                        laplace_slope = laplace_values[-1] - laplace_values[-2]
                    g1, g2 = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
                    gaussian_slope = g1 - g2
                except Exception:
                    pass
            item.update({
                'long_score': long_score, 'long_ann': long_ann, 'long_r2': long_r2,
                'short_score': short_score, 'short_ann': short_ann, 'short_r2': short_r2,
                'volume_ratio': volume_ratio,
                'short_risk': short_risk,
                'premium_rate': premium_rate,
                'laplace_slope': laplace_slope,
                'gaussian_slope': gaussian_slope,
                'passed_r2': (long_r2 is not None and long_r2 > g.r2_threshold),
                'passed_volume': (volume_ratio is not None and volume_ratio < g.volume_threshold),
                'passed_short_risk': (short_risk is not None and short_risk >= g.loss),
                'passed_premium': (premium_rate is not None and premium_rate <= g.max_premium_rate),
            })
        except Exception:
            pass
        snapshots.append(item)
    return snapshots

# ==================== 震荡期检查 ====================

def check_and_exit_range_bound_mode(context):
    """在13:10检查是否需要退出震荡期"""
    try:
        if not g.enable_range_bound_mode:
            return
        if g.current_filter != '震荡期':
            return
        log.info("🔍 【震荡期退出检查】开始检测退出条件...")
        lookback = max(g.ma_period, g.lookback_high_low_days) + 30
        end_date = context.previous_date
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback, frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days):
            log.warning("【震荡期退出检查】数据不足，跳过检查")
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        if len(close) >= g.lookback_high_low_days:
            recent_high = np.max(high[-g.lookback_high_low_days:])
            recent_low = np.min(low[-g.lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        recovery_signals = []
        ma = np.mean(close[-g.ma_period:])
        current_rsi = wufu35_calculate_rsi(close, period=14)
        log.info(f"📊 【震荡期数据】当前价: {current_price:.3f}, 近{g.lookback_high_low_days}日高点: {recent_high:.3f}, 低点: {recent_low:.3f}")
        log.info(f"📊 【震荡期数据】回撤: {current_drawdown:.2%}, 从低点涨幅: {rise_from_low:.2%}")
        if g.enable_low_point_rise_trigger:
            if rise_from_low >= g.low_point_rise_threshold:
                recovery_signals.append(f"从近{g.lookback_high_low_days}日低点上涨{rise_from_low:.2%}≥{g.low_point_rise_threshold:.0%}")
                log.info(f"✅ 【退出条件触发】从低点上涨: {rise_from_low:.2%}")
        if g.enable_stable_signal_trigger:
            if current_price > ma:
                recovery_signals.append("价格站上均线")
                log.info(f"✅ 【企稳信号】价格站上均线({ma:.3f})")
            if len(close) >= 2 and close[-1] > close[-2]:
                recovery_signals.append("价格回升")
                log.info(f"✅ 【企稳信号】当日价格上涨: {((close[-1]/close[-2]-1)*100):.2f}%")
            if g.previous_drawdown is not None and current_drawdown < g.previous_drawdown:
                recovery_signals.append(f"回撤收窄({current_drawdown:.2%}<{g.previous_drawdown:.2%})")
                log.info(f"✅ 【企稳信号】回撤收窄: {g.previous_drawdown:.2%}→{current_drawdown:.2%}")
            if current_rsi is not None and g.previous_rsi is not None and current_rsi > g.previous_rsi:
                recovery_signals.append(f"RSI回升({current_rsi:.1f})")
                log.info(f"✅ 【企稳信号】RSI回升: {g.previous_rsi:.1f}→{current_rsi:.1f}")
            drawdown_safe = current_drawdown < g.drawdown_recovery
            if drawdown_safe:
                g.stable_days += 1
                log.info(f"📊 【企稳计数】连续企稳天数: {g.stable_days}")
            else:
                g.stable_days = 0
        g.previous_drawdown = current_drawdown
        g.previous_rsi = current_rsi
        range_bound_days = 0
        if hasattr(g, 'range_bound_start_date') and g.range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = len(trade_days) - 1
            if range_bound_days >= g.max_range_bound_days:
                recovery_signals.append(f"震荡期满({range_bound_days}个交易日)")
                log.info(f"✅ 【退出条件触发】震荡期已满{range_bound_days}天")
        low_point_rise_condition = g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold
        stable_signal_condition = False
        if g.enable_stable_signal_trigger:
            drawdown_safe = current_drawdown < g.drawdown_recovery
            stable_signal_condition = drawdown_safe and len(recovery_signals) >= 2 and g.stable_days >= 2
        force_condition = range_bound_days >= g.max_range_bound_days
        should_recover = low_point_rise_condition or stable_signal_condition or force_condition
        if should_recover:
            can_switch = True
            if g.last_switch_date is not None:
                trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
                days_since_switch = len(trade_days) - 1
                if days_since_switch < g.filter_switch_cooldown:
                    can_switch = False
                    log.info(f"⏳ 【震荡期退出】冷却期中，距上次切换 {days_since_switch} 天")
            if can_switch:
                g.current_filter = '正常期'
                g.risk_state = '正常期'
                g.last_switch_date = context.current_dt.date()
                g.range_bound_start_date = None
                g.range_bound_days_count = 0
                g.stable_days = 0
                log.info(f"🔔 【退出震荡期】切换回拉普拉斯滤波器: {'; '.join(recovery_signals)}")
            else:
                log.info("⏳ 【震荡期退出】冷却期内，暂不切换")
        else:
            log.info("📌 【震荡期退出检查】未满足退出条件，保持震荡期(高斯滤波器)")
    except Exception as e:
        log.warning(f"【震荡期退出检查】判断出错: {e}")
    finally:
        _warmup_maybe_guard_filter(context)


# ==================== 进入震荡期检查 ====================

def check_and_enter_range_bound_mode(context):
    """在13:10检查是否需要进入震荡期"""
    try:
        if not g.enable_range_bound_mode:
            return
        log.info("🔍 【震荡期检查】开始检测进入条件...")
        can_switch = True
        if g.last_switch_date is not None:
            trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
            days_since_switch = len(trade_days) - 1
            if days_since_switch < g.filter_switch_cooldown:
                can_switch = False
                log.info(f"⏳ 【震荡期检查】冷却期中，距上次切换 {days_since_switch} 天 (需{g.filter_switch_cooldown}天)")
        if g.current_filter == '震荡期':  # 当前已是震荡期则返回
            log.info(f"📌 【震荡期检查】当前已在震荡期，滤波器: 高斯")
            return
        if not can_switch:
            return
        risk_signals = []
        try:
            lookback = max(g.ma_period, g.lookback_high_low_days) + 10
            end_date = context.previous_date
            df = get_price(g.risk_benchmark, end_date=end_date, count=lookback, frequency='daily', fields=['close'], panel=False)
            if df is not None and len(df) >= max(g.ma_period, g.lookback_high_low_days):
                close = df['close'].values
                current_price = close[-1]
                # 条件1: 乖离率过大
                if g.enable_bias_trigger:
                    ma = np.mean(close[-g.ma_period:])
                    bias = (current_price - ma) / ma if ma > 0 else 0
                    if bias > g.bias_threshold:
                        risk_signals.append(f"乖离率过大({bias:.2%}>{g.bias_threshold:.0%})")
                        log.info(f"⚠️ 【条件触发】乖离率: {bias:.2%} (阈值>{g.bias_threshold:.0%})")
                # 条件2: RSI超买回落
                if g.enable_rsi_trigger:
                    current_rsi = wufu35_calculate_rsi(close, period=14)
                    if len(close) >= 15 and current_rsi is not None:
                        prev_rsi = wufu35_calculate_rsi(close[:-1], period=14)
                        if prev_rsi is not None:
                            if prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback and current_rsi < prev_rsi:
                                risk_signals.append(f"RSI超买回落({prev_rsi:.1f}→{current_rsi:.1f})")
                                log.info(f"⚠️ 【条件触发】RSI超买回落: {prev_rsi:.1f}→{current_rsi:.1f}")
        except Exception as e:
            log.warning(f"【震荡期检查】获取基准数据异常: {e}")
        # 条件3: 持仓ETF触发止损
        if g.enable_stop_loss_trigger and g.stop_loss_triggered_today:
            risk_signals.append("今日触发止损")
            log.info(f"⚠️ 【条件触发】今日已触发止损")
            g.stop_loss_triggered_today = False  # 检查后清零
        if len(risk_signals) > 0:
            g.current_filter = '震荡期'           # 切换到震荡期（高斯滤波器）
            g.risk_state = '震荡期'               # 风险状态：震荡期
            g.last_switch_date = context.current_dt.date()
            g.range_bound_start_date = context.current_dt.date()
            g.range_bound_days_count = 0
            g.stable_days = 0
            log.info(f"🔔 【进入震荡期】切换到高斯滤波器: {'; '.join(risk_signals)}")
        else:
            log.info("✅ 【震荡期检查】未满足进入条件，保持正常期(拉普拉斯滤波器)")
    finally:
        _warmup_maybe_guard_filter(context)
# ==================== 动量得分计算 ====================

def calculate_and_log_ranked_etfs(context):
    """计算合并池中的标的动量得分"""
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.warning("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        return
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list

def calculate_momentum_score(price_series, lookback_days):
    """计算动量得分（100%还原 np.polyfit 权重逻辑和原版 R² 算法）"""
    if len(price_series) < lookback_days + 1:
        return None, None, None
    recent_price_series = price_series[-(lookback_days + 1):]
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    W = weights ** 2  # np.polyfit底层实际生效的权重是传入参数的平方
    W_sum = np.sum(W)
    x_bar = np.sum(W * x) / W_sum
    y_bar = np.sum(W * y) / W_sum
    dx = x - x_bar
    dy = y - y_bar
    variance_x = np.sum(W * dx**2)
    if variance_x == 0:
        return 0, 0, 0
    slope = np.sum(W * dx * dy) / variance_x
    intercept = y_bar - slope * x_bar
    annualized_returns = math.exp(slope * 250) - 1
    y_pred = slope * x + intercept
    ss_res = np.sum(weights * (y - y_pred) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2) 
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0
    momentum_score = annualized_returns * r_squared
    return momentum_score, annualized_returns, r_squared


def calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    """计算单个ETF的所有动量指标"""
    try:
        current_price = _coerce_scalar_price(current_price)
        if current_price is None or current_price <= 0:
            return None
        price_series = np.append(hist_closes, current_price)
        if len(price_series) < max(g.lookback_days, g.short_momentum_lookback) * 0.8:
            return None
        smoothed_used = False
        price_for_momentum = price_series
        if _use_smoothed_momentum_prices():
            w = max(1, int(getattr(g, 'smoothed_ma_window', 5)))
            price_for_momentum = pd.Series(price_series).rolling(window=w, min_periods=1).mean().values
            smoothed_used = True
        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_for_momentum, g.lookback_days)
        if momentum_score is None:
            return None
        short_momentum_score, short_annualized_returns, short_r_squared = calculate_momentum_score(price_for_momentum, g.short_momentum_lookback)
        effective_r2_threshold = _effective_r2_threshold()
        passed_r2 = r_squared > effective_r2_threshold
        effective_min_score = float(getattr(g, 'min_score_threshold', 0))
        effective_max_score = float(getattr(g, 'max_score_threshold', 5))
        effective_short_min = float(getattr(g, 'short_momentum_min_score', 0))
        effective_short_max = float(getattr(g, 'short_momentum_max_score', 6))
        if _use_range_long_momentum_limits():
            r_lo = float(getattr(g, 'range_momentum_min', getattr(g, 'range_momentum_floor', 0)))
            r_hi = float(getattr(g, 'range_momentum_max', effective_max_score))
            effective_min_score = max(effective_min_score, r_lo)
            effective_max_score = min(effective_max_score, r_hi)
        if _use_range_short_momentum_limits():
            rs_lo = float(getattr(g, 'range_short_momentum_min', 0))
            rs_hi = float(getattr(g, 'range_short_momentum_max', effective_short_max))
            effective_short_min = max(effective_short_min, rs_lo)
            effective_short_max = min(effective_short_max, rs_hi)
        passed_momentum = (effective_min_score <= momentum_score <= effective_max_score)
        passed_short_momentum = (
            effective_short_min <= short_momentum_score <= effective_short_max
            if short_momentum_score is not None else False)
        if _use_range_short_momentum_limits():
            passed_whipsaw_short_band = passed_short_momentum
        else:
            passed_whipsaw_short_band = True
        dual_pos_active = _dual_positive_filter_should_apply()
        passed_dual_positive = (momentum_score > 0 and short_momentum_score > 0) if short_momentum_score is not None else False
        volume_ratio = get_volume_ratio(hist_volumes, today_vol, context, g.volume_lookback)
        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False
        premium_rate, passed_premium = calculate_premium_rate(etf, context)
        laplace_value = 0
        laplace_slope = 0
        passed_laplace = False
        gaussian_value = 0
        gaussian_slope = 0
        passed_gaussian = False
        if len(price_series) >= 10:
            try:
                laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                if len(laplace_values) >= 2:
                    laplace_value = laplace_values[-1]
                    laplace_slope = laplace_values[-1] - laplace_values[-2]
                    passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
                g1, g2 = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
                gaussian_value = g1
                gaussian_slope = g1 - g2
                passed_gaussian = (current_price > g1 and gaussian_slope > g.gaussian_min_slope)
            except Exception as e:
                pass
        # 根据当前模式选择使用的滤波器
        if g.current_filter == '正常期':      # 正常期（拉普拉斯滤波器）
            filter_value = laplace_value
            filter_slope = laplace_slope
            passed_filter = passed_laplace
        else:                               # 震荡期（高斯滤波器）
            filter_value = gaussian_value
            filter_slope = gaussian_slope
            passed_filter = passed_gaussian
        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'short_momentum_score': short_momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'effective_r2_threshold': effective_r2_threshold,
            'effective_min_score_threshold': effective_min_score,
            'effective_max_score_threshold': effective_max_score,
            'effective_short_min_score_threshold': effective_short_min,
            'effective_short_max_score_threshold': effective_short_max,
            'passed_whipsaw_short_band': passed_whipsaw_short_band,
            'smoothed_momentum_used': smoothed_used,
            'passed_dual_positive': passed_dual_positive,
            'dual_positive_filter_active': dual_pos_active,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'premium_rate': premium_rate,
            'passed_momentum': passed_momentum,
            'passed_short_momentum': passed_short_momentum,
            'passed_r2': passed_r2,
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter,
            'passed_premium': passed_premium,
            'laplace_value': laplace_value,
            'laplace_slope': laplace_slope,
            'gaussian_value': gaussian_value,
            'gaussian_slope': gaussian_slope,
            'passed_laplace': passed_laplace,
            'passed_gaussian': passed_gaussian,
            'filter_value': filter_value,
            'filter_slope': filter_slope,
            'passed_filter': passed_filter,
        }
    except Exception as e:
        log.debug(f"【指标计算】{etf} {etf_name} 计算失败: {e}")
        return None

def get_volume_ratio(hist_volumes, today_vol, context, lookback_days=None):
    """计算成交量比（动态计算已交易时间）"""
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
        now = context.current_dt
        elapsed_minutes = (now.hour - 9) * 60 + now.minute - 30
        if now.hour >= 13:
            elapsed_minutes -= 90
        elapsed_minutes = max(1, min(elapsed_minutes, 240))
        projected_today_vol = today_vol * (240.0 / elapsed_minutes)
        return projected_today_vol / avg_volume if avg_volume > 0 else 0
    except Exception:
        return None
# ==================== 溢价率计算 ====================

def calculate_premium_rate(etf, context):
    """计算ETF溢价率"""
    try:
        etf_price = getattr(g, 'etf_yesterday_close_batch', {}).get(etf)
        if etf_price is None or pd.isna(etf_price):
            etf_price_df = get_price(etf, start_date=context.previous_date, end_date=context.previous_date, fields=['close'])
            if etf_price_df is None or len(etf_price_df) == 0:
                return None, False
            etf_price = etf_price_df['close'].iloc[-1]
        nav = getattr(g, 'etf_yesterday_nav_batch', {}).get(etf)
        if nav is None or pd.isna(nav):
            nav_df = get_extras('unit_net_value', etf, start_date=context.previous_date, end_date=context.previous_date)
            if nav_df is None or len(nav_df) == 0:
                return None, False
            nav = nav_df.iloc[-1].values[0]
        if nav <= 0 or pd.isna(nav):
            return None, False
        premium_rate = (etf_price - nav) / nav * 100
        passed_premium = premium_rate <= g.max_premium_rate
        return premium_rate, passed_premium
    except Exception as e:
        return None, True  # 异常时默认通过溢价率校验
    
# ==================== 滤波器函数 ====================

def gaussian_filter(price, sigma=1.2):
    """高斯滤波器（震荡期使用）"""
    n = len(price)
    G = np.zeros(n)
    for t in range(n):
        weights = np.array([np.exp(-((i+1)**2) / (2 * sigma**2)) for i in range(t+1)])
        weights = weights[::-1]
        weights = weights / np.sum(weights)
        G[t] = np.sum(price[:t+1] * weights)
    return G


def gaussian_filter_last_two(price, sigma=1.2):
    """仅计算高斯滤波所需的最后两个点（效率优化）"""
    n = len(price)
    if n < 2: 
        return 0, 0
    idx_1 = np.arange(n)
    weights_1 = np.exp(-((idx_1+1)**2) / (2 * sigma**2))[::-1]
    weights_1 /= np.sum(weights_1)
    g1 = np.sum(price * weights_1)
    price_2 = price[:-1]
    idx_2 = np.arange(n-1)
    weights_2 = np.exp(-((idx_2+1)**2) / (2 * sigma**2))[::-1]
    weights_2 /= np.sum(weights_2)
    g2 = np.sum(price_2 * weights_2)
    return g1, g2


def laplace_filter(price, s=0.05):
    """拉普拉斯滤波器（正常期使用）"""
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L

def wufu35_calculate_rsi(close, period=14):
    """计算RSI值"""
    try:
        if len(close) < period + 1:
            return None
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except:
        return None
# ==================== 过滤条件应用 ====================

def apply_filters(metrics_list):
    """根据开关应用所有过滤条件"""
    use_short_momentum = g.use_short_momentum_period
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], not use_short_momentum),
        ('短期动量', lambda m: m['passed_short_momentum'], use_short_momentum),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
        ('溢价率', lambda m: m['passed_premium'], g.enable_premium_filter),
        ('动态滤波', lambda m: m['passed_filter'], g.enable_range_bound_mode),
        ('震荡期短期动量区间(Whipsaw)', lambda m: m.get('passed_whipsaw_short_band', True), True),
        ('长短动量双正(Whipsaw)', lambda m: (not m.get('dual_positive_filter_active', False)) or m.get('passed_dual_positive', False), True),
    ]
    whipsaw_step_tags = ('长短动量双正(Whipsaw)', '震荡期短期动量区间(Whipsaw)',)
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            before_count = len(filtered)
            filtered = [m for m in filtered if condition(m)]
            after_count = len(filtered)
            if before_count > after_count:
                log.debug(f"【过滤条件】{name}: 通过 {after_count}/{before_count}")
                if getattr(g, 'log_whipsaw_filter_detail', True):
                    if name in whipsaw_step_tags:
                        tag = "【Whipsaw·方法5】" if "双正" in name else "【Whipsaw·方法3·短期区间】"
                        log.info(f"{tag}{name}: 剔除 {before_count - after_count} 只，剩余 {after_count}/{before_count}")
                    elif name == 'R²' and g.enable_r2_filter:
                        log.info(f"【Whipsaw·方法2·R²过滤步骤】剔除 {before_count - after_count} 只，剩余 {after_count}/{before_count}（有效阈值见单券指标）")
                    elif name == '动量得分' and not use_short_momentum:
                        log.info(f"【Whipsaw·方法3·长期动量步骤】剔除 {before_count - after_count} 只，剩余 {after_count}/{before_count}（含震荡期区间）")
                    elif name == '短期动量' and use_short_momentum:
                        log.info(f"【Whipsaw·方法3·短期动量步骤】剔除 {before_count - after_count} 只，剩余 {after_count}/{before_count}（含震荡期区间若启用）")
    return filtered


def get_final_ranked_etfs(context):
    """主筛选函数，从合并池中选出最终排名ETF"""
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = context.previous_date
    log.info(f"【动量得分计算】使用合并池，合计{len(etf_set)}只ETF")
    log.info(f"【当前滤波器】{'拉普拉斯(正常期)' if g.current_filter == '正常期' else '高斯(震荡期)'}")
    use_short_momentum = g.use_short_momentum_period
    log.info(f"【动量模式】{'使用短期动量得分(21天,0-6分)' if use_short_momentum else '使用动量得分(25天,0-5分)'}")
    if getattr(g, 'log_whipsaw_filter_detail', True):
        if _use_smoothed_momentum_prices():
            log.info(f"【Whipsaw·方法1】动量输入使用均线平滑：MA窗口={getattr(g, 'smoothed_ma_window', 5)}")
        eff_r2 = _effective_r2_threshold()
        base_r2 = getattr(g, 'r2_threshold', 0.4)
        if getattr(g, 'enable_range_r2_veto', False) and eff_r2 > base_r2:
            log.info(f"【Whipsaw·方法2】R²一票否决加强：有效阈值 {eff_r2:.3f}（基础阈值 {base_r2:.3f}）")
        if _use_range_long_momentum_limits():
            log.info(
                f"【Whipsaw·方法3】震荡期长期动量区间：有效范围 "
                f"[{max(g.min_score_threshold, getattr(g, 'range_momentum_min', 0)):.4f}, "
                f"{min(g.max_score_threshold, getattr(g, 'range_momentum_max', g.max_score_threshold)):.4f}]"
            )
        if _use_range_short_momentum_limits():
            log.info(
                f"【Whipsaw·方法3b】震荡期短期动量区间：有效范围 "
                f"[{max(g.short_momentum_min_score, getattr(g, 'range_short_momentum_min', 0)):.4f}, "
                f"{min(g.short_momentum_max_score, getattr(g, 'range_short_momentum_max', g.short_momentum_max_score)):.4f}]"
            )
        if _dual_positive_filter_should_apply():
            log.info("【Whipsaw·方法5】长短动量双正筛：启用（长、短期动量得分须均 > 0）")
        if getattr(g, 'enable_switch_hysteresis', False):
            bn, br = getattr(g, 'switch_buffer_normal', 0.1), getattr(g, 'switch_buffer_range', 0.4)
            log.info(f"【Whipsaw·方法4】换仓滞回：正常期缓冲={bn:.0%}，震荡期缓冲={br:.0%}（新标的评分须 > 持仓×(1+缓冲)）")
    lookback = max(g.lookback_days, g.short_momentum_lookback, g.volume_lookback) + 20
    today = context.current_dt.date()
    replay = getattr(g, '_warmup_replay_mode', False)
    current_data = None if replay else get_current_data()
    replay_paused = {}
    if replay and getattr(g, 'warmup_replay_strict_trade_rules', True):
        try:
            ep = list(etf_set)
            pdf = get_price(
                ep,
                start_date=today,
                end_date=today,
                frequency='daily',
                fields=['paused'],
                panel=False,
                skip_paused=False,
            )
            if pdf is not None and not pdf.empty and 'code' in pdf.columns:
                for code, grp in pdf.groupby('code'):
                    replay_paused[code] = bool(grp['paused'].iloc[-1])
            elif pdf is not None and not pdf.empty and 'paused' in pdf.columns:
                replay_paused[ep[0]] = bool(pdf['paused'].iloc[-1])
        except Exception:
            replay_paused = {}
    safe_lookback = lookback + 20
    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d', fields=['close', 'volume'], panel=False)
    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        log.warning("【动量计算】无法获取历史价格数据")
        return []
    g.etf_yesterday_close_batch = {}
    g.etf_yesterday_nav_batch = {}
    try:
        y_price_df = get_price(etf_set, start_date=end_date, end_date=end_date, fields=['close'], panel=False)
        if y_price_df is not None and not y_price_df.empty:
            g.etf_yesterday_close_batch = y_price_df.groupby('code')['close'].last().to_dict()
        nav_df = get_extras('unit_net_value', etf_set, start_date=end_date, end_date=end_date)
        if nav_df is not None and not nav_df.empty:
            g.etf_yesterday_nav_batch = nav_df.iloc[-1].to_dict()
    except Exception as e:
        log.warning(f"【动量计算】批量获取溢价率数据异常: {e}")
    today_vols = today_vol_df.groupby('code')['volume'].sum() if (today_vol_df is not None and not today_vol_df.empty) else pd.Series(dtype=float)
    close_pivot = hist_df.pivot(index='time', columns='code', values='close')
    volume_pivot = hist_df.pivot(index='time', columns='code', values='volume')
    for etf in etf_set:
        if replay:
            if replay_paused.get(etf, False):
                continue
        elif current_data[etf].paused:
            continue
        if etf not in close_pivot.columns:
            continue
        raw_closes = close_pivot[etf].values
        raw_volumes = volume_pivot[etf].values
        valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)
        hist_closes = raw_closes[valid_mask]
        hist_volumes = raw_volumes[valid_mask]
        hist_closes = hist_closes[-lookback:]
        hist_volumes = hist_volumes[-lookback:]
        if len(hist_closes) < max(g.lookback_days, g.short_momentum_lookback):
            continue
        etf_name = get_security_name(etf)
        hist_last = _coerce_scalar_price(hist_closes[-1]) if len(hist_closes) else None
        if replay:
            current_price = _replay_decision_price(etf, context, hist_last)
            current_price = _coerce_scalar_price(current_price)
            if current_price is None or current_price <= 0:
                continue
        else:
            current_price = current_data[etf].last_price
        today_vol = today_vols.get(etf, 0)
        metrics = calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                continue
            all_metrics.append(metrics)
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
        short_score = item.get('short_momentum_score')
        if pd.isna(short_score) or (isinstance(short_score, float) and np.isnan(short_score)):
            item['short_momentum_score'] = float('-inf')
    if use_short_momentum:
        all_metrics.sort(key=lambda x: x.get('short_momentum_score', float('-inf')), reverse=True)
    else:
        all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    log_buffer = []
    log_buffer.append("")
    if getattr(g, 'enable_step1_full_ranking_log', False):
        log_buffer.append(f">>> 第一步：所有ETF按{'短期' if use_short_momentum else '原'}动量得分从大到小排序 <<<")
        for m in all_metrics[:100]:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
            short_score_str = f"{m['short_momentum_score']:.4f}" if m['short_momentum_score'] != float('-inf') else "nan"
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
                f"短期动量: {fmt_status(short_score_str, m['passed_short_momentum'])}，"
                f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
                f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
                f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
                f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
                f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}，"
                f"高斯斜率: {m['gaussian_slope']:.4f} {fmt_status('', m['passed_gaussian'])}"
            )
            log_buffer.append(line)
    filtered_list = apply_filters(all_metrics)
    if use_short_momentum:
        filtered_list.sort(key=lambda x: x.get('short_momentum_score', float('-inf')), reverse=True)
    else:
        filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    top_10 = filtered_list[:10]
    log_buffer.append("")
    log_buffer.append(f">>> 第二步：符合全部过滤条件的ETF按{'短期' if use_short_momentum else '原'}动量得分从大到小排序(前10名) <<<")
    if top_10:
        for m in top_10:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
            short_score_str = f"{m['short_momentum_score']:.4f}" if m['short_momentum_score'] != float('-inf') else "nan"
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
                f"短期动量: {fmt_status(short_score_str, m['passed_short_momentum'])}，"
                f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
                f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
                f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
                f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
                f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}，"
                f"高斯斜率: {m['gaussian_slope']:.4f} {fmt_status('', m['passed_gaussian'])}"
            )
            log_buffer.append(line)
    else:
        log_buffer.append("（无符合条件的ETF）")
        full_log = "\n".join(log_buffer)
        log.info(full_log)
        return []
    score_key = 'short_momentum_score' if use_short_momentum else 'momentum_score'
    effective_ratio, ratio_notes = get_effective_score_threshold_ratio(score_key, top_10)
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        score_threshold = reference_score * effective_ratio
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：选取{'短期' if use_short_momentum else '原'}动量得分≥第{g.holdings_num}名({top_10[g.holdings_num - 1]['etf_name']})得分{reference_score:.4f}×{effective_ratio:.3f}={score_threshold:.4f}的ETF <<<")
        if ratio_notes:
            for note in ratio_notes:
                log_buffer.append(f"  - 阈值调节: {note}")
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：前10名不足{g.holdings_num}只，全部作为候选池 <<<")
        candidate_pool = top_10[:]
    log_buffer.append(f"【候选池】共{len(candidate_pool)}只ETF（按{'短期' if use_short_momentum else '原'}动量得分排序）：")
    for i, item in enumerate(candidate_pool):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")
    log_buffer.append("")
    log_buffer.append(">>> 第四步：结合当前持仓进行调整 <<<")
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    log_buffer.append(f"当前持仓ETF：{current_holdings}")
    candidate_dict = {item['etf']: item for item in candidate_pool}
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    log_buffer.append(f"其中存在于候选池中的持仓ETF：{[item['etf'] for item in retained]}")
    if len(retained) >= g.holdings_num:
        retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
        log_buffer.append(f"保留的持仓ETF数量({len(retained)})超过目标持仓数({g.holdings_num})，将从保留的ETF中按{'短期' if use_short_momentum else '原'}动量得分取前{g.holdings_num}只作为最终目标。")
    else:
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
    # 方法4：换仓滞回 — 新标的须在排序评分上明显优于持仓（默认震荡期用更宽缓冲）
    if getattr(g, 'enable_switch_hysteresis', False) and g.holdings_num == 1 and final_result:
        hs_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
        if hs_holdings:
            hs_current = hs_holdings[0]
            hs_target = final_result[0]['etf']
            if hs_current != hs_target:
                in_range = getattr(g, 'current_filter', '正常期') == '震荡期'
                hbuf = getattr(g, 'switch_buffer_range', 0.40) if in_range else getattr(g, 'switch_buffer_normal', 0.10)
                hs_cur_metric = next((m for m in filtered_list if m['etf'] == hs_current), None)
                if hs_cur_metric is None:
                    hs_cur_metric = next((m for m in all_metrics if m['etf'] == hs_current), None)
                if hs_cur_metric is not None:
                    t_sc = final_result[0].get(score_key, float('-inf'))
                    c_sc = hs_cur_metric.get(score_key, float('-inf'))
                    hurdle = c_sc * (1.0 + hbuf)
                    t_nm = final_result[0].get('etf_name', hs_target)
                    c_nm = hs_cur_metric.get('etf_name', hs_current)
                    log_buffer.append(
                        f"🔎 【Whipsaw·方法4】换仓滞回: 缓冲={hbuf:.0%}({'震荡期' if in_range else '正常期'}), "
                        f"要求 {score_key}(目标) > {hurdle:.4f} (= {score_key}(持仓){c_sc:.4f}×(1+{hbuf:.0%}))"
                    )
                    if np.isfinite(t_sc) and np.isfinite(c_sc):
                        if t_sc <= hurdle:
                            log_buffer.append(
                                f"⏸️ 【Whipsaw·方法4】滞回拦截换仓: 保留 {c_nm}({hs_current})，"
                                f"{t_nm}({hs_target}) {score_key}={t_sc:.4f} 未超过门槛 {hurdle:.4f}"
                            )
                            if getattr(g, 'log_whipsaw_filter_detail', True):
                                log.info(
                                    f"【Whipsaw·方法4】换仓被滞回带拦截: 目标 {hs_target} {score_key}={t_sc:.4f} ≤ 门槛 {hurdle:.4f} "
                                    f"(持仓 {hs_current} {score_key}={c_sc:.4f}, 缓冲={hbuf:.0%})"
                                )
                            final_result = [hs_cur_metric]
                        else:
                            log_buffer.append(
                                f"✅ 【Whipsaw·方法4】滞回通过: {t_nm} {score_key}={t_sc:.4f} > {hurdle:.4f}"
                            )
                    else:
                        log_buffer.append("ℹ️ 【Whipsaw·方法4】滞回跳过: 评分非有限值")
                else:
                    log_buffer.append(f"ℹ️ 【Whipsaw·方法4】滞回跳过: 持仓 {hs_current} 无指标记录")
    swap_delta_gate_on = getattr(g, 'enable_long_delta_gate', False) or getattr(g, 'enable_short_delta_gate', False)
    if swap_delta_gate_on and g.holdings_num == 1 and final_result:
        current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
        if current_holdings:
            current_etf = current_holdings[0]
            target_etf = final_result[0]['etf']
            if current_etf != target_etf:
                current_metric = next((m for m in filtered_list if m['etf'] == current_etf), None)
                metric_source = "filtered_list"
                if current_metric is None:
                    current_metric = next((m for m in all_metrics if m['etf'] == current_etf), None)
                    metric_source = "all_metrics"
                if current_metric is not None:
                    target_score = final_result[0].get(score_key, float('-inf'))
                    current_score = current_metric.get(score_key, float('-inf'))
                    target_name = final_result[0].get('etf_name', target_etf)
                    current_name = current_metric.get('etf_name', current_etf)
                    log_buffer.append(
                        f"🔎 换仓差值门控: 目标={target_name}({target_etf}), 当前持仓={current_name}({current_etf}), "
                        f"评分键={score_key}, 持仓评分来源={metric_source}"
                    )
                    if np.isfinite(target_score) and np.isfinite(current_score):
                        switch_delta = target_score - current_score
                        denom = abs(current_score) if abs(current_score) > 1e-8 else float('nan')
                        switch_delta_rel = (switch_delta / denom) if np.isfinite(denom) else float('nan')
                        keep_long_momentum = current_metric.get('momentum_score', float('nan'))
                        blocked_long_momentum = final_result[0].get('momentum_score', float('nan'))
                        keep_short_momentum = current_metric.get('short_momentum_score', float('nan'))
                        blocked_short_momentum = final_result[0].get('short_momentum_score', float('nan'))
                        long_delta_keep_block = (
                            keep_long_momentum - blocked_long_momentum
                            if (np.isfinite(keep_long_momentum) and np.isfinite(blocked_long_momentum))
                            else float('nan')
                        )
                        short_delta_keep_block = (
                            keep_short_momentum - blocked_short_momentum
                            if (np.isfinite(keep_short_momentum) and np.isfinite(blocked_short_momentum))
                            else float('nan')
                        )
                        enable_long_delta_gate = getattr(g, 'enable_long_delta_gate', False)
                        long_delta_gate_min = getattr(g, 'long_delta_gate_min', -999.0)
                        long_delta_gate_max = getattr(g, 'long_delta_gate_max', 999.0)
                        enable_short_delta_gate = getattr(g, 'enable_short_delta_gate', False)
                        short_delta_gate_min = getattr(g, 'short_delta_gate_min', -999.0)
                        short_delta_gate_max = getattr(g, 'short_delta_gate_max', 999.0)
                        long_delta_gate_ok = (not enable_long_delta_gate) or (
                            np.isfinite(long_delta_keep_block)
                            and long_delta_keep_block > long_delta_gate_min
                            and long_delta_keep_block < long_delta_gate_max
                        )
                        short_delta_gate_ok = (not enable_short_delta_gate) or (
                            np.isfinite(short_delta_keep_block)
                            and short_delta_keep_block > short_delta_gate_min
                            and short_delta_keep_block < short_delta_gate_max
                        )
                        log_buffer.append(
                            f"   - 评分差: target-current = {target_score:.4f} - {current_score:.4f} = {switch_delta:.4f}"
                        )
                        log_buffer.append(
                            "   - 动量差值(保留-放弃): "
                            f"long={long_delta_keep_block:.4f}, short={short_delta_keep_block:.4f}"
                        )
                        log_buffer.append(
                            "   - 门控: "
                            f"长期={'开' if enable_long_delta_gate else '关'}"
                            f"[{long_delta_gate_min:.4f},{long_delta_gate_max:.4f}] "
                            f"=> {'通过' if long_delta_gate_ok else '不通过'}; "
                            f"短期={'开' if enable_short_delta_gate else '关'}"
                            f"[{short_delta_gate_min:.4f},{short_delta_gate_max:.4f}] "
                            f"=> {'通过' if short_delta_gate_ok else '不通过'}"
                        )
                        if np.isfinite(switch_delta_rel):
                            log_buffer.append(
                                f"   - 相对评分差: (target-current)/|current| = {switch_delta_rel:.2%}"
                            )
                        if long_delta_gate_ok and short_delta_gate_ok:
                            g.today_switch_buffer_audit = {
                                'decision_date': str(context.current_dt.date()),
                                'score_key': score_key,
                                'kept_etf': current_etf,
                                'kept_name': current_name,
                                'keep_score': current_score,
                                'keep_long_momentum': current_metric.get('momentum_score', float('nan')),
                                'keep_short_momentum': current_metric.get('short_momentum_score', float('nan')),
                                'blocked_target_etf': target_etf,
                                'blocked_target_name': target_name,
                                'blocked_target_score': target_score,
                                'blocked_target_long_momentum': blocked_long_momentum,
                                'blocked_target_short_momentum': blocked_short_momentum,
                                'long_delta_keep_block': long_delta_keep_block,
                                'short_delta_keep_block': short_delta_keep_block,
                                'switch_delta': switch_delta,
                                'switch_delta_rel': switch_delta_rel,
                                'enable_long_delta_gate': enable_long_delta_gate,
                                'enable_short_delta_gate': enable_short_delta_gate,
                                'long_delta_gate_min': long_delta_gate_min,
                                'long_delta_gate_max': long_delta_gate_max,
                                'short_delta_gate_min': short_delta_gate_min,
                                'short_delta_gate_max': short_delta_gate_max,
                                'metric_source': metric_source,
                                'filter_state': getattr(g, 'current_filter', '未知'),
                            }
                            final_result = [current_metric]
                            log_buffer.append(
                                f"⏸️ 差值门控拦截: 长期/短期差值均在设定区间内，保留当前持仓 {current_etf}"
                            )
                        else:
                            log_buffer.append(
                                "ℹ️ 差值门控未拦截: 已启用的门控未全部通过，允许换仓"
                            )
                    else:
                        log_buffer.append(
                            f"ℹ️ 差值门控跳过: 评分非有限值 (目标={target_score}, 当前={current_score})"
                        )
                else:
                    log_buffer.append(
                        f"ℹ️ 差值门控跳过: 当前持仓 {current_etf} 不在 filtered_list/all_metrics 中"
                    )
    log_buffer.append(f"【最终目标】共{len(final_result)}只ETF：")
    for i, item in enumerate(final_result):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']})")
    if getattr(g, 'enable_chase_whipsaw_audit', False):
        # 审计“放强追弱”：对比“动量阈值内最强”与最终目标（仅记录，不影响交易）
        g.latest_selection_audit = None
        if all_metrics and final_result:
            overall_best = all_metrics[0]
            threshold_best = None
            for m in all_metrics:
                if use_short_momentum:
                    if m.get('passed_short_momentum', False):
                        threshold_best = m
                        break
                else:
                    if m.get('passed_momentum', False):
                        threshold_best = m
                        break
            if threshold_best is None:
                threshold_best = overall_best
            raw_best = threshold_best
            chosen = final_result[0]
            raw_score = raw_best.get(score_key, float('-inf'))
            chosen_score = chosen.get(score_key, float('-inf'))
            score_gap = raw_score - chosen_score
            if raw_best['etf'] == chosen['etf']:
                g.latest_selection_audit = {
                    'date': context.current_dt.date(),
                    'score_key': score_key,
                    'raw_best_etf': raw_best['etf'],
                    'raw_best_name': raw_best['etf_name'],
                    'raw_best_score': raw_score,
                    'chosen_etf': chosen['etf'],
                    'chosen_name': chosen['etf_name'],
                    'chosen_score': chosen_score,
                    'score_gap': score_gap,
                    'reasons': ["审计未触发:阈值内最强即最终目标"],
                }
            elif score_gap <= 0:
                g.latest_selection_audit = {
                    'date': context.current_dt.date(),
                    'score_key': score_key,
                    'raw_best_etf': raw_best['etf'],
                    'raw_best_name': raw_best['etf_name'],
                    'raw_best_score': raw_score,
                    'chosen_etf': chosen['etf'],
                    'chosen_name': chosen['etf_name'],
                    'chosen_score': chosen_score,
                    'score_gap': score_gap,
                    'reasons': ["审计未触发:阈值内最强与最终目标分差≤0"],
                }
            if raw_best['etf'] != chosen['etf'] and score_gap > 0:
                if replay:
                    _rp = _replay_decision_price(raw_best['etf'], context, None)
                    raw_trade_blocks = get_trade_block_reasons(
                        raw_best['etf'],
                        current_data,
                        replay_price=_rp,
                        replay_trade_date=context.current_dt.date(),
                    )
                else:
                    raw_trade_blocks = get_trade_block_reasons(raw_best['etf'], current_data)
                raw_filter_blocks = get_filter_block_reasons(raw_best, use_short_momentum)
                raw_pass_all_filters = len(raw_filter_blocks) == 0
                block_reasons = []
                if not raw_pass_all_filters:
                    block_reasons = list(raw_filter_blocks)
                elif raw_best['etf'] not in {c['etf'] for c in candidate_pool}:
                    block_reasons.append(f"未进入候选池(需≥第{g.holdings_num}名×{effective_ratio:.3f})")
                else:
                    block_reasons.append("被持仓保留机制挤出最终目标")
                if raw_trade_blocks:
                    block_reasons.extend([f"可交易性受限:{r}" for r in raw_trade_blocks])
                if not block_reasons:
                    block_reasons = ["其他约束导致未入选"]
                g.latest_selection_audit = {
                    'date': context.current_dt.date(),
                    'score_key': score_key,
                    'raw_best_etf': raw_best['etf'],
                    'raw_best_name': raw_best['etf_name'],
                    'raw_best_score': raw_score,
                    'chosen_etf': chosen['etf'],
                    'chosen_name': chosen['etf_name'],
                    'chosen_score': chosen_score,
                    'score_gap': score_gap,
                    'reasons': block_reasons,
                }
                log_buffer.append("")
                log_buffer.append(">>> 诊断：放强追弱风险审计 <<<")
                log_buffer.append(
                    f"原始最强: {raw_best['etf_name']}({raw_best['etf']}) {score_key}={raw_score:.4f}；"
                    f"最终目标: {chosen['etf_name']}({chosen['etf']}) {score_key}={chosen_score:.4f}；"
                    f"差值={score_gap:.4f}"
                )
                if overall_best['etf'] != raw_best['etf']:
                    log_buffer.append(
                        f"  - 说明: 全样本最高分为{overall_best['etf_name']}({overall_best['etf']}) "
                        f"{score_key}={overall_best.get(score_key, float('-inf')):.4f}，"
                        f"但超出动量阈值范围，故审计基准改用阈值内最强"
                    )
                log_buffer.append(f"  - raw_best通过全部过滤: {'是' if raw_pass_all_filters else '否'}")
                for status_line in get_filter_pass_status(raw_best, use_short_momentum):
                    log_buffer.append(f"  - 过滤状态: {status_line}")
                if raw_trade_blocks:
                    log_buffer.append(f"  - raw_best可交易性: ❌ {'，'.join(raw_trade_blocks)}")
                else:
                    log_buffer.append("  - raw_best可交易性: ✅ 可交易")
                for reason in block_reasons:
                    log_buffer.append(f"  - 未选最强原因: {reason}")
    log_buffer.append("==================================================")
    full_log = "\n".join(log_buffer)
    log.info(full_log)
    return final_result

# ==================== 交易执行 ====================

# ========== 三马原保留函数（包含pure_wufu_mode判断）==========
def smart_order_target_value(security, target_value, context):
    """专门供给策略3 (ETF轮动) 调用的接口"""
    current_data = get_current_data()
    security_name = get_security_name(security)
    if current_data[security].paused:
        log.info(f"{security} {security_name}: 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {security_name}: 当前涨停，跳过交易")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {security_name}: 当前跌停，跳过交易")
        return False
    current_price = current_data[security].last_price
    if current_price == 0:
        log.info(f"{security} {security_name}: 当前价格为0，跳过交易")
        return False
    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < g.min_money:
        log.info(f"{security} {security_name}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过")
        return False
    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {security_name}: 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)
    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            # 同步维护策略3虚拟现金（仅用于收益归因显示，不影响真实下单）
            filled = getattr(order_result, "filled", 0) or 0
            deal_price = getattr(order_result, "price", current_price) or current_price
            commission = getattr(order_result, "commission", 0) or 0
            tax = getattr(order_result, "tax", 0) or 0
            if filled > 0:
                deal_value = filled * deal_price
                if amount_diff > 0:
                    g.sub_account[3]['cash'] -= (deal_value + commission + tax)
                else:
                    g.sub_account[3]['cash'] += (deal_value - commission - tax)
                if g.sub_account[3]['cash'] < 0:
                    g.sub_account[3]['cash'] = 0

            if amount_diff > 0:
                if security not in g.strategy_holdings[3]:
                    g.strategy_holdings[3].append(security)
                g.stock_strategy[security] = 3
                log.info(f"📦 买入{security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}")
            else:
                pos_after = context.portfolio.positions.get(security, None)
                if (pos_after is None or pos_after.total_amount <= 0) and security in g.strategy_holdings[3]:
                    g.strategy_holdings[3].remove(security)
                    if security in g.stock_strategy:
                        del g.stock_strategy[security]
                log.info(f"📤 卖出{security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}")
            return True
        log.warning(f"下单失败: {security} {security_name}，数量: {amount_diff}")
        return False
    return False



def execute_sell_trades(context):
    """卖出交易逻辑"""
    log.info("========== 卖出操作开始 ==========")
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    target_etfs = []
    if ranked_etfs:
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
            log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}")
    else:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
            etf_name = get_security_name(g.defensive_etf)
            log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
        else:
            log.info("💤 无最终目标(空仓模式)")
            target_etfs = []
            
    g.target_etfs_list = target_etfs
    target_set = set(target_etfs)
    sell_count = 0

    pure_wufu_mode = (g.portfolio_value_proportion == [0, 0, 1, 0])
    position_keys = (
        list(context.portfolio.positions.keys())
        if pure_wufu_mode
        else list(g.strategy_holdings[3])
    )
    for security in position_keys:
        position = context.portfolio.positions.get(security)
        if position and position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            success = smart_order_target_value(security, 0, context)
            if success:
                sell_count += 1
                log.info(f"✅ 已成功卖出: {security} {security_name}")
                
    log.info(f"本次共计划卖出{sell_count}只ETF。")
    log.info("========== 卖出操作完成 ==========")



def execute_buy_trades(context):
    """买入交易逻辑"""
    log.info("========== 买入操作开始 ==========")
    target_etfs = g.target_etfs_list
    if not target_etfs: 
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        log.info("========== 买入操作完成 ==========")
        return
        
    pure_wufu_mode = (g.portfolio_value_proportion == [0, 0, 1, 0])
    current_strategy3_positions = (
        set(context.portfolio.positions.keys())
        if pure_wufu_mode
        else set(g.strategy_holdings[3])
    )
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_strategy3_positions]
    actual_holding_count = len(current_strategy3_positions)
    
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    
    if num_etfs_to_buy <= 0: 
        log.info(f"策略3实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        log.info("========== 买入操作完成 ==========")
        return
        
    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    
    if pure_wufu_mode:
        available_cash = context.portfolio.available_cash
    else:
        strategy3_target_value = context.portfolio.total_value * g.portfolio_value_proportion[2]
        strategy3_hold_value = sum(
            context.portfolio.positions[sec].value
            for sec in current_strategy3_positions
            if sec in context.portfolio.positions and context.portfolio.positions[sec].total_amount > 0
        )
        strategy3_available_cash = max(0, strategy3_target_value - strategy3_hold_value)
        available_cash = min(context.portfolio.available_cash, strategy3_available_cash)
    allocated_value_per_etf = (
        available_cash // num_etfs_to_buy
        if pure_wufu_mode
        else available_cash / num_etfs_to_buy
    )
    
    log.info(f"策略3可用现金: {available_cash:.2f}, 分配给每只ETF的资金: {allocated_value_per_etf:.2f}")
    if allocated_value_per_etf < g.min_money:
        log.info(f"单只ETF分配金额{allocated_value_per_etf:.2f}小于最小交易额{g.min_money:.2f}，无法买入")
        log.info("========== 买入操作完成 ==========")
        return
    
    for i, etf in enumerate(etfs_to_buy):
        target_value_for_this_etf = allocated_value_per_etf
        
        if pure_wufu_mode:
            if i == len(etfs_to_buy) - 1 and context.portfolio.available_cash >= g.min_money:
                target_value_for_this_etf = context.portfolio.available_cash
        else:
            if i == len(etfs_to_buy) - 1 and available_cash >= g.min_money:
                strategy3_hold_value = sum(
                    context.portfolio.positions[sec].value
                    for sec in current_strategy3_positions
                    if sec in context.portfolio.positions and context.portfolio.positions[sec].total_amount > 0
                )
                strategy3_target_value = context.portfolio.total_value * g.portfolio_value_proportion[2]
                remaining_target = max(0, strategy3_target_value - strategy3_hold_value)
                target_value_for_this_etf = min(context.portfolio.available_cash, remaining_target)
            
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
        else:
            log.info(f"❌ ETF {etf} 下单失败")
            
    log.info("========== 买入操作完成 ==========")



def minute_level_stop_loss(context):
    """分钟级固定比例止损"""
    if not g.use_fixed_stop_loss:
        return
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
        
    current_data = get_current_data()
    pure_wufu_mode = (g.portfolio_value_proportion == [0, 0, 1, 0])
    security_iter = (
        list(context.portfolio.positions.keys())
        if pure_wufu_mode
        else list(g.strategy_holdings[3])
    )
    for security in security_iter:
        position = context.portfolio.positions.get(security)
        if not position or position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        cost_price = position.avg_cost
        if cost_price <= 0:
            continue
        if current_price <= cost_price * g.fixedStopLossThreshold:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"🚨 【分钟级固定止损】{security} {security_name} 触发止损，亏损: {loss_percent:.2f}%")
            success = smart_order_target_value(security, 0, context)
            if success and g.enable_stop_loss_trigger:
                g.stop_loss_triggered_today = True
                log.info(f"✅ 【止损触发】记录今日止损，将在13:10检查并进入震荡期")



def minute_level_pct_stop_loss(context):
    """分钟级当日跌幅止损"""
    if not g.use_pct_stop_loss:
        return
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
        
    current_data = get_current_data()
    current_date = context.current_dt.date()
    if not hasattr(g, 'cache_date') or g.cache_date != current_date:
        g.yesterday_close_cache = {}
        g.cache_date = current_date
        
    pure_wufu_mode = (g.portfolio_value_proportion == [0, 0, 1, 0])
    security_iter = (
        list(context.portfolio.positions.keys())
        if pure_wufu_mode
        else list(g.strategy_holdings[3])
    )
    for security in security_iter:
        position = context.portfolio.positions.get(security)
        if not position or position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        yesterday_close = getattr(g, 'yesterday_close_cache', {}).get(security)
        if yesterday_close is None:
            try:
                close_series = attribute_history(security, 1, '1d', ['close'], skip_paused=False)
                if len(close_series['close']) == 0: continue
                yesterday_close = close_series['close'][-1]
                if yesterday_close <= 0: continue
                g.yesterday_close_cache[security] = yesterday_close
            except Exception:
                continue
                
        current_price = current_data[security].last_price
        if current_price <= 0: continue
        
        stop_price = yesterday_close * g.pct_stop_loss_threshold
        if current_price <= stop_price:
            security_name = get_security_name(security)
            daily_loss = (current_price / yesterday_close - 1) * 100
            log.info(f"🚨 【分钟级跌幅止损】{security} {security_name} 触发止损，当日跌幅: {daily_loss:.2f}%")
            success = smart_order_target_value(security, 0, context)
            if success and g.enable_stop_loss_trigger:
                g.stop_loss_triggered_today = True
                log.info(f"✅ 【止损触发】记录今日止损，将在13:10检查并进入震荡期")


# ==================== 辅助函数 ====================

def get_security_name(security):
    """安全获取证券名称"""
    try:
        if hasattr(g, 'etf_names_dict') and security in g.etf_names_dict:
            return g.etf_names_dict[security]
        return get_security_info(security).display_name
    except Exception:
        return "未知名称"

def check_defensive_etf_available(context):
    """检查防御性ETF是否可交易"""
    defensive_etf = g.defensive_etf
    if getattr(g, '_warmup_replay_mode', False):
        if not getattr(g, 'warmup_replay_strict_trade_rules', True):
            return True
        td = getattr(g, '_warmup_replay_current_td', None)
        if td is None:
            td = context.current_dt.date()
        price = _replay_decision_price(defensive_etf, context, None)
        price = _coerce_scalar_price(price)
        if price is None or not np.isfinite(price) or price <= 0:
            log.info(f"防御性ETF {defensive_etf} 预热回放: 无有效价格")
            return False
        cons = _warmup_security_trade_constraints(defensive_etf, td)
        if cons is None:
            return False
        if cons.get('paused'):
            log.info(f"防御性ETF {defensive_etf} 今日停牌")
            return False
        if _warmup_price_triggers_trade_block(price, cons):
            hl = cons.get('high_limit')
            if hl is not None and price >= hl:
                log.info(f"防御性ETF {defensive_etf} 当前涨停")
            else:
                log.info(f"防御性ETF {defensive_etf} 当前跌停")
            return False
        return True
    current_data = get_current_data()
    if current_data[defensive_etf].paused:
        log.info(f"防御性ETF {defensive_etf} 今日停牌")
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        log.info(f"防御性ETF {defensive_etf} 当前涨停")
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        log.info(f"防御性ETF {defensive_etf} 当前跌停")
        return False
    return True


def sync_strategy3_holdings_from_portfolio(context):
    """
    终极修复：识别账户里没有被其他策略认领的持仓，绝不因为跌出股票池而删除标记！
    """
    if not hasattr(g, 'strategy_holdings'):
        g.strategy_holdings = {1: [], 2: [], 3: [], 4: []}
    if not hasattr(g, 'stock_strategy'):
        g.stock_strategy = {}

    # 1. 清理已经卖空，但没来得及删掉标记的股票
    for sid in list(g.strategy_holdings.keys()):
        for sec in g.strategy_holdings[sid][:]:
            pos = context.portfolio.positions.get(sec)
            if not pos or pos.total_amount == 0:
                g.strategy_holdings[sid].remove(sec)
                if sec in g.stock_strategy:
                    del g.stock_strategy[sec]

    # 2. 识别未标记的幽灵仓，自动归属
    for sec, pos in context.portfolio.positions.items():
        if pos.total_amount > 0 and sec not in g.stock_strategy:
            # 策略1的防守ETF
            if sec == getattr(g, 'xsz_buy_etf', None):
                g.strategy_holdings[1].append(sec)
                g.stock_strategy[sec] = 1
            # 策略2的专属ETF
            elif sec in getattr(g, 'etf_pool_2', []):
                g.strategy_holdings[2].append(sec)
                g.stock_strategy[sec] = 2
            # 剩下只要是以5或15开头的(绝大概率是ETF)，统统兜底给策略3
            elif sec.startswith('5') or sec.startswith('15'):
                g.strategy_holdings[3].append(sec)
                g.stock_strategy[sec] = 3
                log.warning(f"🔄 【防漏仓修复】捕获幽灵ETF {sec}，强制归还给策略3！")
            # 其他(通常是股票)给策略1
            else:
                g.strategy_holdings[1].append(sec)
                g.stock_strategy[sec] = 1
                log.warning(f"🔄 【防漏仓修复】捕获幽灵股票 {sec}，强制归还给策略1！")
                
    # 去重
    for sid in [1, 2, 3, 4]:
        g.strategy_holdings[sid] = list(dict.fromkeys(g.strategy_holdings[sid]))



def _patch_wufu35_smart_order_for_strategy3():
    """五福原版 smart_order_target_value 不维护 strategy_holdings；此处包装以兼容三马统计。"""
    if getattr(g, "_wufu35_sotv_wrapped", False):
        return
    if "smart_order_target_value" not in globals():
        return
    _orig = smart_order_target_value
    g._wufu35_sotv_wrapped = True

    def _wrapped(security, target_value, context):
        ok = _orig(security, target_value, context)
        if not ok:
            return False
        # 不依赖下单后瞬时持仓状态（回测/撮合存在时序），
        # 按目标仓位意图维护策略3归属，避免漏标或误删。
        if target_value <= 0:
            # 仅当账户中已无该持仓时才删除归属标记，避免“已报单卖出但持仓尚未清零”导致未标记幽灵仓
            pos = context.portfolio.positions.get(security)
            if (not pos) or pos.total_amount <= 0:
                if security in g.strategy_holdings[3]:
                    g.strategy_holdings[3].remove(security)
                if security in g.stock_strategy:
                    del g.stock_strategy[security]
            else:
                if security not in g.strategy_holdings[3]:
                    g.strategy_holdings[3].append(security)
                g.stock_strategy[security] = 3
                log.info(
                    f"[策略3登记] {security} 卖出报单已提交但仓位未清零，暂保留策略3标记，"
                    f"当前仓位={pos.total_amount}"
                )
        else:
            if security not in g.strategy_holdings[3]:
                g.strategy_holdings[3].append(security)
            g.stock_strategy[security] = 3
        return True

    globals()["smart_order_target_value"] = _wrapped

""" ====================== 基础配置 ====================== """




# 策略参数设置
def set_strategy_params(context):
    # 统一最小交易金额兜底：即使关闭策略3，也要保证其他策略可访问该参数
    g.min_money = getattr(g, "min_money", 10)
    """策略1 小市值 参数"""
    g.avoid_trade_april = False  # 是否在1、4月份避免交易小市值策略（避开高风险月份）
    # ======== 【修复代码】添加默认初始化，防止盘中启动报错 ========
    if g.avoid_trade_april and context.current_dt.month in [1, 4]:
        g.trading_signal = False
    else:
        g.trading_signal = True
    # ================================================================g.huanshou_check = False  # 放量换手检测，Ture是日频判断是否放量，False则不然
    g.huanshou_check = False  # 放量换手检测，Ture是日频判断是否放量，False则不然
    g.xsz_version = "v3"  # 市值选用版本 可选值: v1/v2/v3 具体逻辑自己看代码吧, 写不下
    g.enable_dynamic_stock_num = True  # 启用动态选股数量 3~6
    g.xsz_stock_num = 5  # 默认的持股数量, 启用动态后会被覆盖为 3~6
    g.yesterday_HL_list = []  # 昨日涨停股票
    g.target_list = []  # 目标持仓股票
    # 与小市值.py一致默认银华日利；与策略3防御ETF冲突时在 setup_wufu35_globals 之后改为国债ETF
    g.xsz_buy_etf = "511880.XSHG"

    # ========== 动态资金管理 ========== 打开以后，2年收益提升，回撤不变；10年收益降低，回撤降低
    # 根据市场波动率动态调整仓位，高波动时降低仓位，低波动时增加仓位
    g.enable_dynamic_position = False  # 是否启用基于波动率的动态仓位管理
    g.volatility_lookback = 20  # 波动率计算回溯期（交易日）
    g.base_position_ratio = 1.0  # 基准仓位比例（正常市场环境）
    g.volatility_threshold_low = 0.015  # 低波动率阈值（增加仓位）典型值: 0.01-0.02
    g.volatility_threshold_high = 0.035  # 高波动率阈值（降低仓位）典型值: 0.03-0.04
    g.position_ratio_min = 0.5  # 最小仓位比例（高波动时）
    g.position_ratio_max = 1.0  # 最大仓位比例（低波动时）

    # ========== 止损检查 ==========
    g.run_stoploss = True  # 是否进行止损
    g.stoploss_strategy = 3  # 1=固定止损，2=市场趋势止损，3=联合1+2策略
    g.stoploss_limit = 0.09  # 固定止损线（亏损9%止损）
    g.stoploss_market = 0.05  # 市场趋势止损参数（大盘跌5%清仓）

    # ========== ATR动态止损 ==========关闭ATR，2年收益提升，回撤不变；10年收益降低，回撤降低
    # ATR止损根据市场波动自动调整止损距离，比固定止损更灵活
    # 示例：成本价10元，ATR=0.5，倍数=2，则止损价=10-0.5*2=9元
    g.enable_atr_stop_loss = True  # 是否启用ATR动态止损（可与上述止损并用）
    g.atr_period = 14  # ATR计算周期（交易日）典型值: 10-20
    g.atr_multiplier = 2.0  # ATR止损倍数，值越大止损越宽松。典型值: 1.5-3.0
    g.atr_stop_prices = {}  # 存储每只股票的ATR止损价（自动维护，无需手动设置）

    # ========== 成本保护止损 ==========打开后，收益提升一点点，两年回撤不变
    # 盈利后动态上移止损线，保护已获利润
    # 示例：成本价10元，盈利15%（当前价11.5元）-> 止损线上移到10元（保护本金）
    #       成本价10元，盈利30%（当前价13元）-> 止损线上移到11元（保护10%利润）
    g.enable_cost_protection = True  # 是否启用成本保护止损
    g.cost_protection_profit_threshold_1 = 0.15  # 第一档盈利阈值（15%），触发后止损线上移到成本价
    g.cost_protection_profit_threshold_2 = 0.30  # 第二档盈利阈值（30%），触发后止损线上移到+10%
    g.cost_protection_stop_line_1 = 0.00  # 第一档止损线（成本价，0%）
    g.cost_protection_stop_line_2 = 0.10  # 第二档止损线（+10%利润）

    # ========== 一致性风控（新增）========== 不开收益更高，回撤更低
    # 基于微盘股（最小5%市值）的市场一致性指标，用于控制回撤
    g.enable_consistency_control = False  # 是否启用一致性风控
    g.consistency_signal = False  # False=满仓 True=清仓，初始满仓
    g.consistency_boll_period = 120  # 布林带计算周期（交易日）
    g.consistency_threshold_mean = 0.8  # 默认一致性均值（历史数据不足时使用）
    g.consistency_threshold_std = 0.05  # 默认一致性标准差（历史数据不足时使用）
    g.mini_cosi_list = []  # 存储微盘股一致性数据历史
	
# 异常处理窗口期检查
    g.check_after_no_buy = True     # 【修改此处】将其改为 True 开启冷却检查
    g.no_buy_stocks = {}            # 检查卖出的股票记录字典 {stock: date}
    g.no_buy_after_day = 2          # 止损后不买入的时间窗口(3个交易日)	
	

    # 顶背离检查
    g.DBL_control = True  # 小市值大盘顶背离记录（用于风险控制）
    g.dbl = []
    g.check_macd_divergence_days = 10  # 顶背离检测窗口期长度, 窗口内不仅买入
    # 异常处理窗口期检查
    # 成交额宽度检查
    g.check_defense = False  # 成交额宽度检查
    g.industries = ["组20"]  # 高位防御板块
    g.defense_signal = None
    g.cnt_defense_signal = []  # 择时次数
    g.cnt_bank_signal = []  # 组20择时次数
    g.history_defense_date_list = []
    g.position_highs = {}

    """ 策略2 ETF反弹 参数 """
    g.limit_days = 2  # 最少持仓周期
    g.n_days = 5  # 持仓周期
    g.holding_days = 0
    g.buy_list = []
    # etf池子，优先级从高到低
    g.etf_pool_2 = [
        "159536.XSHE",  # 中证2000
        "159629.XSHE",  # 中证1000
        "159922.XSHE",  # 中证500
        "159919.XSHE",  # 沪深300
        "159783.XSHE",  # 双创50
    ]

    """ 策略3 《五福闹新春》v3.5（与五福35.py 同源，setup_wufu35_globals） """
    if g.portfolio_value_proportion[2] > 0:
        setup_wufu35_globals()
    if g.portfolio_value_proportion[0] > 0 and g.portfolio_value_proportion[2] > 0:
        if g.xsz_buy_etf == getattr(g, "defensive_etf", None):
            log.warn(
                f"[策略冲突] 策略1空仓ETF({g.xsz_buy_etf})与策略3防御ETF重复，"
                f"已自动改为 511010.XSHG"
            )
            g.xsz_buy_etf = "511010.XSHG"
    g.m_days = getattr(g, "lookback_days", 25)
    g.m_score = getattr(g, "min_score_threshold", 0)

    """ 策略4 白马攻防 参数 """
    g.check_out_lists = []
    g.market_temperature = "warm"
    g.stock_num_2 = 5  # 目标持股数量
    g.roe = 10  # ROE权重
    g.roa = 6  # ROA权重




def set_backtest(context=None):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)

    pure_wufu_mode = (g.portfolio_value_proportion == [0, 0, 1, 0])
    if pure_wufu_mode:
        set_benchmark("510300.XSHG")
    else:
        set_benchmark("159919.XSHE")
    set_slippage(FixedSlippage(0.002), type="stock")
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    if pure_wufu_mode:
        cost_configs = [
            ("stock", 0.0005, 0.85 / 10000, 5),
            ("fund", 0, 0.0001, 5),
            ("mmf", 0, 0, 0),
        ]
    else:
        cost_configs = [
            ("stock", 0.0005, 0.85 / 10000, 5),
            ("fund", 0, 0.0002, 5),
            ("mmf", 0, 0, 0),
        ]
    for asset_type, close_tax, commission, min_comm in cost_configs:
        set_order_cost(
            OrderCost(
                open_tax=0,
                close_tax=close_tax,
                open_commission=commission,
                close_commission=commission,
                close_today_commission=commission if (pure_wufu_mode and asset_type == "fund") else 0,
                min_commission=min_comm,
            ),
            type=asset_type,
        )


""" ====================== 策略1: 小市值 ====================== """


# v1 选股模块 (双市值+行业分散)
def get_small_cap_stocks_v1(context):
    # 获取股票所属行业
    def filter_industry_stock(stock_list):
        result = get_industry(security=stock_list)
        selected_stocks = []
        industry_list = []
        for stock_code, info in result.items():
            industry_name = info["sw_l2"]["industry_name"]
            if industry_name not in industry_list:
                industry_list.append(industry_name)
                selected_stocks.append(stock_code)
                log.info(
                    f"[选股] 行业信息: {industry_name} (股票: {stock_code} {get_security_info(stock_code).display_name})"
                )
                if len(industry_list) == 10:
                    break
        return selected_stocks

    initial_list = filter_stocks(context, get_index_stocks("399101.XSHE"))

    q = (
        query(valuation.code)
        .filter(valuation.code.in_(initial_list))
        .order_by(valuation.circulating_market_cap.asc())
        .limit(50)
    )
    initial_list = list(get_fundamentals(q).code)

    q = (
        query(valuation.code)
        .filter(valuation.code.in_(initial_list))
        .order_by(valuation.market_cap.asc())
    )
    initial_list = list(get_fundamentals(q).code)
    initial_list = initial_list[:30]
    final_list = filter_industry_stock(initial_list)[: g.xsz_stock_num]
    log.info(
        f"[选股v1] 选出的股票: {[f'{i} {get_security_info(i).display_name}' for i in final_list]}"
    )
    return final_list


# v2 选股模块 (国九+roa+roe)
def get_small_cap_stocks_v2(context):
    initial_list = filter_stocks(context, get_index_stocks("399101.XSHE"))

    # 修复：正确使用聚宽基本面表查询方式
    q = (
        query(
            valuation.code,
            valuation.market_cap,
            income.np_parent_company_owners,
            income.net_profit,
            income.operating_revenue,
            valuation.turnover_ratio,
        )
        .filter(
            valuation.code.in_(initial_list),
            valuation.market_cap.between(5, 50),
            income.np_parent_company_owners > 0,
            income.net_profit > 0,
            income.operating_revenue > 1e8,
            fundamentals.indicator.roe > 0.15,
            fundamentals.indicator.roa > 0.10,
        )
        .order_by(valuation.market_cap.asc())
        .limit(50)
    )
    df = get_fundamentals(q)
    if df.empty:
        return []
    final_list = list(df.code)
    last_prices = history(1, "1d", "close", final_list, df=False)
    # 价格过滤
    return [
        stock
        for stock in final_list
        if stock in context.portfolio.positions or last_prices[stock] <= 20
    ][: g.xsz_stock_num]



# ====================== 顶级防弹版：九项年报排雷系统 ======================
def apply_nine_point_audit(context, stock_list):
    """
    九项排雷检查表逻辑实现 (终极修复版：解决财报空窗期与时间开关问题)
    """
    if not stock_list:
        return []

    import datetime
    yesterday = context.previous_date
    #current_date = context.current_dt.date()
    
    # =========================================================
    # ==== 【新增优化】：时间开关，2024年5月之前不启用该排雷逻辑 ====
    # =========================================================
    #start_audit_date = datetime.date(2025, 1, 1)
    #if current_date < start_audit_date:
    #    return stock_list

    curr_year = yesterday.year
    curr_month = yesterday.month
    
    # =========================================================
    # ==== 【新增优化】：动态获取报告期，解决1-4月财报取不到的问题 ====
    # =========================================================
    # A股规定上一年年报最晚在当年4月30日披露。如果在4月底之前，大概率取不到去年的年报，只能往后退取前年的年报
    if curr_month <= 4:
        report_year = curr_year - 2
    else:
        report_year = curr_year - 1
        
    report_date_str = f"{report_year}-12-31" 
    
    # 1. 批量获取基础财务指标 (聚宽的 get_fundamentals(date=yesterday) 会自动获取PIT最新数据，这里不受影响)
    q = query(
        valuation.code, indicator.adjusted_profit, income.net_profit,
        cash_flow.subtotal_operate_cash_inflow, cash_flow.subtotal_operate_cash_outflow,
        balance.good_will, balance.equities_parent_company_owners,
        balance.total_liability, balance.total_assets,
        balance.shortterm_loan, balance.cash_equivalents
    ).filter(valuation.code.in_(stock_list))
    
    fund_df = get_fundamentals(q, date=yesterday)
    if not fund_df.empty:
        fund_df = fund_df.set_index('code')
        fund_df.fillna(0, inplace=True)
    else:
        return stock_list

    final_list = []
    
    # 监管时代容忍度（因为已经限定了2024年5月后才执行，所以统一采用严苛标准：容忍度为2）
    max_tolerance = 2
    
    for stock in stock_list:
        score = 0
        hit_reasons = [] 
        
        try:
            stock_name = get_security_info(stock).display_name if get_security_info(stock) else ""

            # --- 1. 披露时间检查 (修复使用 end_date 和 动态年份判定) ---
            if hasattr(finance, 'STK_INCOME_STATEMENT'):
                q_time = query(finance.STK_INCOME_STATEMENT.pub_date).filter(
                    finance.STK_INCOME_STATEMENT.code == stock,
                    finance.STK_INCOME_STATEMENT.end_date == report_date_str,  
                    finance.STK_INCOME_STATEMENT.pub_date <= yesterday
                ).limit(1)
                time_df = finance.run_query(q_time)
                if not time_df.empty:
                    actual_date = time_df['pub_date'].iloc[0]
                    if isinstance(actual_date, str):
                        actual_date = datetime.datetime.strptime(actual_date, '%Y-%m-%d').date()
                    elif isinstance(actual_date, datetime.datetime) or hasattr(actual_date, 'date'):
                        actual_date = actual_date.date()
                    
                    # 【核心修复】：判断迟发应该是判断 report_year 的下一年
                    if actual_date and actual_date > datetime.date(report_year + 1, 4, 20):
                        score += 1
                        hit_reasons.append("年报迟发(>4.20)")

            # --- 2. 业绩预告检查 (修复使用 end_date) ---
            if hasattr(finance, 'STK_FIN_FORCAST'): 
                q_forcast = query(finance.STK_FIN_FORCAST).filter(
                    finance.STK_FIN_FORCAST.code == stock,
                    finance.STK_FIN_FORCAST.end_date == report_date_str,  
                    finance.STK_FIN_FORCAST.pub_date <= yesterday
                ).limit(1)
                forcast_df = finance.run_query(q_forcast)
                if not forcast_df.empty:
                    type_id = forcast_df['type_id'].iloc[0]
                    if type_id in [3, 4, 5, 9, 10]: 
                        score += 1
                        hit_reasons.append("业绩预告不良(预减/亏损等)")

            # --- 3. 审计意见检查 (修复使用 end_date) ---
            if hasattr(finance, 'STK_AUDIT_OPINION'):
                q_audit = query(finance.STK_AUDIT_OPINION).filter(
                    finance.STK_AUDIT_OPINION.code == stock,
                    finance.STK_AUDIT_OPINION.end_date == report_date_str,  
                    finance.STK_AUDIT_OPINION.pub_date <= yesterday 
                ).limit(1)
                audit_df = finance.run_query(q_audit)
                if not audit_df.empty:
                    opinion_id = audit_df['opinion_type_id'].iloc[0]
                    if opinion_id in [3, 4, 5]: 
                        log.info(f"[排雷剔除] 💥 {stock}({stock_name}) 触发一票否决: 审计意见异常")
                        continue 

            # --- 财务硬指标判定 (4-7项) ---
            if stock in fund_df.index:
                row = fund_df.loc[stock]
                adj_p = row['adjusted_profit']
                net_p = row['net_profit']
                cash_net = row['subtotal_operate_cash_inflow'] - row['subtotal_operate_cash_outflow']
                
                if adj_p < 0 or (net_p != 0 and adj_p / net_p < 0.5):
                    score += 1
                    hit_reasons.append("主业存疑(扣非<0或占比低)")
                    
                if net_p > 0 and cash_net < 0:
                    score += 1
                    hit_reasons.append("现金流异常(净利>0但现金流<0)")
                    
                equity = row['equities_parent_company_owners']
                gw = row['good_will']
                if equity > 0 and (gw / equity) > 0.3:
                    score += 1
                    hit_reasons.append("高危资产(商誉占净资产>30%)")
                    
                t_liab = row['total_liability']
                t_assets = row['total_assets']
                st_loan = row['shortterm_loan']
                cash_val = row['cash_equivalents']
                
                debt_ratio = (t_liab / t_assets) if t_assets > 0 else 0
                if debt_ratio > 0.70 or st_loan > cash_val:
                    score += 1
                    hit_reasons.append(f"资金链紧绷(负债率{(debt_ratio*100):.0f}%)")

            # --- 8. 大股东风险 (质押率) ---
            if hasattr(finance, 'STK_SHARES_PLEDGE'):
                q_pledge = query(finance.STK_SHARES_PLEDGE).filter(
                    finance.STK_SHARES_PLEDGE.code == stock,
                    finance.STK_SHARES_PLEDGE.pub_date <= yesterday
                ).order_by(finance.STK_SHARES_PLEDGE.pub_date.desc()).limit(1)
                pledge_df = finance.run_query(q_pledge)
                if not pledge_df.empty:
                    ratio_col = 'pledge_proportion' if 'pledge_proportion' in pledge_df.columns else ('pledge_ratio' if 'pledge_ratio' in pledge_df.columns else None)
                    if ratio_col is not None:
                        val = pledge_df[ratio_col].iloc[0]
                        if pd.notna(val) and val > 80:
                            score += 1
                            hit_reasons.append("大股东高质押(>80%)")

            # --- 9. 监管信号 (立案调查) ---
            if hasattr(finance, 'STK_INVESTIGATION'):
                q_inv = query(finance.STK_INVESTIGATION).filter(
                    finance.STK_INVESTIGATION.code == stock,
                    finance.STK_INVESTIGATION.pub_date >= f"{curr_year-1}-01-01",
                    finance.STK_INVESTIGATION.pub_date <= yesterday  
                ).limit(1)
                inv_df = finance.run_query(q_inv)
                if not inv_df.empty:
                    score += 1
                    hit_reasons.append("曾遭监管立案调查")


            # 结果判定与日志打印
            if score > 0:
                log.info(f"[排雷透视] 🔍 {stock}({stock_name}) 累计踩中 {score} 项: {' | '.join(hit_reasons)}")

            # 动态阈值拦截
            if score < max_tolerance:  
                final_list.append(stock)
            else:
                log.info(f"[排雷剔除] 🛡️ {stock}({stock_name}) 踩雷 {score} 项，超过当前时代容忍度({max_tolerance})，已精准拦截!")
                
        except Exception as e:
            log.error(f"[排雷报错] 股票 {stock} 在计算时发生代码异常: {e}")
            final_list.append(stock)
            
    return final_list


""" ====================== 策略1：选股逻辑 ====================== """

def get_small_cap_stocks_v3(context):
    initial_list = filter_stocks(context, get_index_stocks("399101.XSHE"))

    q = (
        query(
            valuation.code,
            valuation.market_cap,
            income.net_profit,
            income.operating_revenue,
        )
        .filter(
            valuation.code.in_(initial_list),
            valuation.market_cap.between(10, 100), #这里修改小市值的盘子范围
            income.operating_revenue > 1e8,
            indicator.roe > 0,
            indicator.roa > 0,
            income.net_profit > 2000000,
        )
        .order_by(valuation.market_cap.asc())
        .limit(g.xsz_stock_num * 5)
    )
    candidate_list = list(get_fundamentals(q).code)
    
    current_date = context.current_dt.date()
    
    # =========================================================
    # ==== 【新增优化】：时间开关，2025年1月之前不启用该排雷逻辑 ====
    # =========================================================
    start_audit_date = datetime.date(2025, 1, 1)
    
    if current_date > start_audit_date:
        audited_list = apply_nine_point_audit(context, candidate_list)
    else:
        #audited_list = candidate_list
        audited_list = filter_audit(context, candidate_list)
        
    final_list = bonus_filter(context, audited_list)
	
    # ==== 【新增代码】在此处加入止损冷却过滤 ====
    final_list = filter_cooldown_stocks(context, final_list)
    # ==========================================	
    
    if not final_list:
        return [g.xsz_buy_etf]
        
    last_prices = history(1, unit="1d", field="close", security_list=final_list)
    return [s for s in final_list if s in g.strategy_holdings[1] or last_prices[s][-1] <= 50][: g.xsz_stock_num]


	
	
	

# 核心风控：微盘股10%指数一致性检查（蒋氏一致性）- 从xsz_yi_zhi_xing.py集成
def mini_consistency_check(context, signal):
    """
    一致性风控检查：基于微盘股（最小5%市值）的市场一致性指标

    核心逻辑：
    1. 筛选全市场有效标的（非停牌/非ST/非退市/非科创板/上市>20天）
    2. 选取市值最小的5%标的作为微盘股样本池
    3. 计算微盘股涨跌幅中位数和标准差
    4. 计算一致性比例：在[m-std, m+std]区间内的股票占比
    5. 使用120日布林带计算一致性动态阈值
    6. 牛熊判断：上证指数>240日均线=牛市关闭检查，否则开启

    风控规则：
    - 大跌（中位数<-2%）+ 高一致性（>=上轨） → 清仓（返回True）
    - 大涨（中位数>2%）+ 低一致性（>=均值） → 满仓（返回False）
    - 其他情况 → 保持原信号

    参数:
        context: 聚宽上下文
        signal: 当前一致性信号（False=满仓，True=清仓）

    返回:
        True: 触发清仓信号
        False: 不触发清仓信号（保持满仓）
    """
    today_date = context.current_dt.date()
    last_date = context.previous_date
    all_data = get_current_data()

    # 步骤1：筛选有效标的：全市场非停牌/非ST/非退市/非科创板/上市超20天
    stock_list = list(get_all_securities(["stock"]).index)
    total_stock_cnt = len(stock_list)
    stock_list = [code for code in stock_list if not all_data[code].paused]
    stock_list = [code for code in stock_list if not all_data[code].is_st]
    stock_list = [code for code in stock_list if "退" not in all_data[code].name]
    stock_list = [code for code in stock_list if code[0:3] != "688"]
    stock_list = [
        code
        for code in stock_list
        if (today_date - get_security_info(code).start_date).days > 20
    ]
    filter_stock_cnt = len(stock_list)

    # 步骤2：选取市值最小的5%标的作为微盘股样本池
    q = (
        query(valuation.code, valuation.market_cap)
        .filter(valuation.code.in_(stock_list))
        .order_by(valuation.market_cap.asc())
    )
    df_val = get_fundamentals(q)
    sample_stock_cnt = round(0.05 * total_stock_cnt)
    stock_list = list(df_val["code"])[:sample_stock_cnt]

    # 步骤3：计算微盘股样本池的涨跌幅中位数/标准差/一致性比例
    df_chg = get_money_flow(
        stock_list, end_date=last_date, fields="change_pct", count=1
    )
    chg_med = np.median(df_chg.change_pct)
    chg_std = np.std(df_chg.change_pct)
    df_temp = df_chg[
        (df_chg.change_pct < (chg_med + chg_std))
        & (df_chg.change_pct > (chg_med - chg_std))
    ]
    consistency_stock_cnt = len(df_temp)

    # 计算当日一致性比例并存储
    consistency_last = consistency_stock_cnt / sample_stock_cnt
    g.mini_cosi_list.append(consistency_last)

    # 牛熊判断：上证指数站上年线=牛市，关闭一致性检查；反之熊市开启
    df_index = get_price(
        "399101.XSHE",
        end_date=last_date,
        frequency="1d",
        fields="close",
        count=250,
        panel=False,
    )
    if df_index["close"].values[-1] > df_index["close"].values.mean():
        log.info("[一致性风控] 牛市判定，关闭一致性风控检查")
        return False
    else:
        log.info("[一致性风控] 熊市判定，打开一致性风控检查")

    # 计算一致性的120日布林带上下轨
    if len(g.mini_cosi_list) >= g.consistency_boll_period:
        cosistency_mean = np.mean(g.mini_cosi_list[-g.consistency_boll_period :])
        cosistency_std = np.std(g.mini_cosi_list[-g.consistency_boll_period :])
    else:
        cosistency_mean = g.consistency_threshold_mean
        cosistency_std = g.consistency_threshold_std
    cosistency_upper = cosistency_mean + cosistency_std

    # 打印一致性风控关键数据
    log.info(
        f"[一致性风控] {last_date} 微盘股-涨跌幅中位数:{chg_med:.4f},标准差:{chg_std:.4f},"
        f"当日一致性:{consistency_last:.4f},一致性均值:{cosistency_mean:.4f},一致性上轨:{cosistency_upper:.4f}"
    )

    # 布林带风控规则：大跌+高一致性=清仓，大涨+低一致性=满仓，其余保持原信号
    if chg_med < -2 and consistency_last >= cosistency_upper:
        log.warn("[一致性风控] 触发清仓信号：大跌+高一致性 → 清仓")
        return True
    elif chg_med > 2 and consistency_last >= cosistency_mean:
        log.info("[一致性风控] 触发满仓信号：大涨+低一致性 → 满仓")
        return False
    else:
        log.info("[一致性风控] 无信号，维持原持仓状态")
        return signal


# 小市值早盘变量预处理
def prepare_small_cap_strategy(context):
    # 根据配置决定是否在1、4月份避免交易
    if g.avoid_trade_april:
        g.trading_signal = False if context.current_dt.month in [1, 4] else True
    else:
        g.trading_signal = True

    # 更新一致性风控信号（新增）
    if g.enable_consistency_control:
        g.consistency_signal = mini_consistency_check(context, g.consistency_signal)

    g.yesterday_HL_list = []
    # 获取昨日涨停列表
    if g.strategy_holdings[1]:
        df = get_price(
            g.strategy_holdings[1],
            end_date=context.previous_date,
            fields=["close", "high_limit", "low_limit"],
            frequency="daily",
            count=1,
            panel=False,
            fill_paused=False,
        )
        g.yesterday_HL_list = list(df[df["close"] == df["high_limit"]].code)


# 计算市场波动率（基于大盘指数）
def calculate_market_volatility(context):
    """
    计算市场波动率，使用沪深300或其他大盘指数
    返回值：波动率（标准差）
    """
    index_code = "000300.XSHG"  # 沪深300指数
    df = get_price(
        index_code,
        end_date=context.previous_date,
        count=g.volatility_lookback + 1,
        frequency="daily",
        fields=["close"],
    )
    if len(df) < g.volatility_lookback:
        return None

    # 计算日收益率
    returns = df["close"].pct_change().dropna()
    # 计算波动率（标准差）
    volatility = returns.std()
    return volatility


# 根据波动率计算动态仓位比例
def calculate_dynamic_position_ratio(context):
    """
    根据市场波动率动态调整仓位比例
    低波动 -> 增加仓位（最高100%）
    正常波动 -> 基准仓位（100%）
    高波动 -> 降低仓位（最低50%）
    """
    if not g.enable_dynamic_position:
        return g.base_position_ratio

    volatility = calculate_market_volatility(context)
    if volatility is None:
        log.info("[动态仓位] 波动率数据不足，使用基准仓位")
        return g.base_position_ratio

    # 根据波动率区间调整仓位
    if volatility < g.volatility_threshold_low:
        # 低波动率，可以适当增加仓位
        position_ratio = g.position_ratio_max
        level = "低波动"
    elif volatility > g.volatility_threshold_high:
        # 高波动率，降低仓位控制风险
        position_ratio = g.position_ratio_min
        level = "高波动"
    else:
        # 正常波动率，线性插值
        # volatility 在 [low, high] 之间，position_ratio 在 [max, min] 之间
        ratio_range = g.position_ratio_max - g.position_ratio_min
        volatility_range = g.volatility_threshold_high - g.volatility_threshold_low
        position_ratio = g.position_ratio_max - (
            (volatility - g.volatility_threshold_low) / volatility_range * ratio_range
        )
        level = "正常波动"

    log.info(
        f"[动态仓位] 市场波动率: {volatility:.4f} ({level}) -> 仓位比例: {position_ratio:.2%}"
    )
    return position_ratio


# 计算ATR（平均真实波幅）
def calculate_atr(security, context, period=14):
    """
    计算ATR指标
    ATR = Average True Range，衡量价格波动幅度
    """
    df = get_price(
        security,
        end_date=context.previous_date,
        count=period + 1,
        frequency="daily",
        fields=["high", "low", "close"],
    )

    if len(df) < period + 1:
        return None

    # 计算真实波幅（True Range）
    # TR = max(high - low, abs(high - pre_close), abs(low - pre_close))
    df["pre_close"] = df["close"].shift(1)
    df["tr1"] = df["high"] - df["low"]
    df["tr2"] = abs(df["high"] - df["pre_close"])
    df["tr3"] = abs(df["low"] - df["pre_close"])
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

    # 计算ATR（使用简单移动平均）
    atr = df["tr"].iloc[-period:].mean()
    return atr


# 更新ATR止损价格
def update_atr_stop_prices(context):
    """
    为持仓股票更新ATR止损价格
    止损价 = 买入价 - (ATR × 倍数)
    """
    if not g.enable_atr_stop_loss:
        return

    current_positions = context.portfolio.positions
    for stock in current_positions.keys():
        if stock in g.strategy_holdings[1]:
            # 如果这只股票还没有止损价，计算并设置
            if stock not in g.atr_stop_prices:
                atr = calculate_atr(stock, context, g.atr_period)
                if atr:
                    avg_cost = current_positions[stock].avg_cost
                    # 止损价 = 成本价 - ATR倍数 * ATR
                    stop_price = avg_cost - (g.atr_multiplier * atr)
                    g.atr_stop_prices[stock] = stop_price
                    log.info(
                        f"[ATR止损] {format_stock_code(stock)} 成本: {avg_cost:.2f}, "
                        f"ATR: {atr:.2f}, 止损价: {stop_price:.2f}"
                    )
            else:
                # 已有止损价，可以选择使用跟踪止损（trailing stop）
                # 这里实现简单版本：如果价格上涨，止损价也向上调整
                current_price = current_positions[stock].price
                atr = calculate_atr(stock, context, g.atr_period)
                if atr:
                    trailing_stop = current_price - (g.atr_multiplier * atr)
                    # 止损价只能上移，不能下移（保护利润）
                    if trailing_stop > g.atr_stop_prices[stock]:
                        old_stop = g.atr_stop_prices[stock]
                        g.atr_stop_prices[stock] = trailing_stop
                        log.info(
                            f"[ATR止损] {format_stock_code(stock)} 跟踪止损价调整: "
                            f"{old_stop:.2f} -> {trailing_stop:.2f}"
                        )


# ATR动态止损检查
def check_atr_stop_loss(context):
    """
    检查是否触发ATR止损
    """
    if not g.enable_atr_stop_loss:
        return

    current_positions = context.portfolio.positions
    for stock in list(current_positions.keys()):
        if stock in g.strategy_holdings[1] and stock in g.atr_stop_prices:
            current_price = current_positions[stock].price
            stop_price = g.atr_stop_prices[stock]

            if current_price <= stop_price:
                avg_cost = current_positions[stock].avg_cost
                loss_pct = (current_price - avg_cost) / avg_cost * 100
                log.warn(
                    f"[ATR止损] {format_stock_code(stock)} 触发止损 "
                    f"当前价: {current_price:.2f}, 止损价: {stop_price:.2f}, "
                    f"亏损: {loss_pct:.2f}%"
                )
                close_position(context, stock)

                # ==== 【新增代码】记录止损日期 ====
                if g.check_after_no_buy:
                    g.no_buy_stocks[stock] = context.current_dt.date()
                # ===============================				
				
                # 清除止损价记录
                del g.atr_stop_prices[stock]


# 小市值卖出
def strategy_1_sell(context):
    log.info("=" * 100)
    log.info(f"[策略1] 日期: {context.current_dt.date()}")
    g.target_list = []

    # 一致性风控检查（新增）：如果触发清仓信号，则不允许调仓
    if g.enable_consistency_control and g.consistency_signal:
        log.warn("[策略1] 一致性风控触发清仓信号，暂停调仓")
        return

    if g.DBL_control:
        # 首次运行检测最近10日顶背离
        if len(g.dbl) < 10:
            for i in range(9, -1, -1):
                check_macd_divergence(context, end_days=0 - i)
    if g.DBL_control and 1 in g.dbl[-g.check_macd_divergence_days :]:
        log.warn(f"[策略1] 近{g.check_macd_divergence_days}日检测到大盘顶背离，暂停调仓以控制风险")
        return

    # 检测空仓期（根据配置决定是否在1、4月份避免交易）
    if g.avoid_trade_april:
        month = context.current_dt.month
        if month in [1, 4]:
            g.trading_signal = False
    if not g.trading_signal:
        return

    if g.check_defense and g.defense_signal:
        log.warn("[策略1] 触发成交额宽度检查信号，暂停调仓以控制风险")
        return

    # 动态调整选股数量
    diff = None
    if g.enable_dynamic_stock_num:
        ma_para = 10  # 设置MA参数
        today = context.previous_date
        start_date = today - timedelta(days=ma_para * 2)
        index_df = get_price(
            "399101.XSHE", start_date=start_date, end_date=today, frequency="daily"
        )
        index_df["ma"] = index_df["close"].rolling(window=ma_para).mean()
        last_row = index_df.iloc[-1]
        diff = last_row["close"] - last_row["ma"]
        g.xsz_stock_num = (
            3
            if diff >= 500
            else 3
            if 200 <= diff < 500
            else 4
            if -200 <= diff < 200
            else 5
            if -500 <= diff < -200
            else 6
        )
    # 选择要启用的选股版本
    g.target_list = {
        "v1": get_small_cap_stocks_v1,
        "v2": get_small_cap_stocks_v2,
        "v3": get_small_cap_stocks_v3,
    }[g.xsz_version](context)[: g.xsz_stock_num]
    log.info(
        f"[策略1] 小市值{g.xsz_version} 目标持股数: {g.xsz_stock_num} [diff:{str(diff)[:6]}] 目标持仓: {g.target_list}"
    )

    # 卖出不在目标列表中的股票（除昨日涨停股）
    sell_list = [
        s
        for s in g.strategy_holdings[1]
        if s not in g.target_list and s not in g.yesterday_HL_list
    ]
    hold_list = [
        s
        for s in g.strategy_holdings[1]
        if s in g.target_list or s in g.yesterday_HL_list
    ]

    if sell_list:
        if hold_list:
            log.info(
                f"[策略1] 当前持有: {[format_stock_code(stock) for stock in hold_list]}"
            )
        log.info(
            f"[策略1] 计划卖出: {[format_stock_code(stock) for stock in sell_list]}"
        )
    for stock in sell_list:
        close_position(context, stock)


def strategy_1_buy(context):
    # 一致性风控检查（与 小市值.py 一致）
    if g.enable_consistency_control and g.consistency_signal:
        log.warn("[策略1] 一致性风控触发清仓信号，暂停买入")
        return

    if not g.trading_signal:
        if g.xsz_buy_etf not in context.portfolio.positions:
            log.info("[策略1] 小市值清仓时期, 买入ETF")
            def_budget = context.portfolio.total_value * g.portfolio_value_proportion[0]
            _sync_strategy_1_sub_account_cash(context, def_budget)
            open_position(
                context,
                g.xsz_buy_etf,
                def_budget,
                1,
            )
            if g.xsz_buy_etf not in g.strategy_holdings[1]:
                g.strategy_holdings[1].append(g.xsz_buy_etf)
                g.stock_strategy[g.xsz_buy_etf] = 1
        return

    position_ratio = calculate_dynamic_position_ratio(context)

    strategy_value = (
        context.portfolio.total_value * g.portfolio_value_proportion[0] * position_ratio
    )
    current_value = sum(
        [
            pos.value
            for pos in context.portfolio.positions.values()
            if pos.security in g.strategy_holdings[1]
        ]
    )
    available_cash = max(0, strategy_value - current_value)
    _sync_strategy_1_sub_account_cash(context, strategy_value)

    buy_list = [s for s in g.target_list if s not in g.strategy_holdings[1][:]]
    if buy_list and available_cash > 0:
        cash_per_stock = available_cash / len(buy_list)
        for stock in buy_list:
            open_position(context, stock, cash_per_stock, 1)

    # 买入后更新ATR止损价
    if g.enable_atr_stop_loss:
        update_atr_stop_prices(context)


def close_account(context):
    if not g.trading_signal:
        if g.strategy_holdings[1] and g.xsz_buy_etf not in g.strategy_holdings[1]:
            for stock in g.strategy_holdings[1][:]:
                log.warn(f"[策略1] 进入清仓期间，卖出 {format_stock_code(stock)}")
                close_position(context, stock)


# 检查昨日涨停股今日表现
def check_small_cap_limit_up(context):
    # 获取当前持仓
    holdings = g.strategy_holdings[1][:]  # 只检查策略1
    if holdings:
        now_time = context.current_dt
        if g.yesterday_HL_list:
            # 对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
            for stock in g.yesterday_HL_list:
                current_data = get_price(
                    stock,
                    end_date=now_time,
                    frequency="1m",
                    fields=["close", "high_limit"],
                    skip_paused=False,
                    fq="pre",
                    count=1,
                    panel=False,
                    fill_paused=True,
                )
                if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                    log.info(f"[策略1] {format_stock_code(stock)} 涨停打开，卖出")
                    close_position(context, stock)
                else:
                    log.info(f"[策略1] {stock} 继续涨停，继续持有")


def _release_cash_for_small_cap(context, required_cash):
    """保留兼容入口：多策略模式下禁止策略1动用策略3资金。"""
    return 0


# 止盈止损
def sell_small_cap_stocks(context):
    if g.run_stoploss:
        current_positions = context.portfolio.positions

        # ATR动态止损（优先级最高）
        if g.enable_atr_stop_loss:
            check_atr_stop_loss(context)

        # 固定止损线 + 成本保护止损 (策略1或3)
        if g.stoploss_strategy in [1, 3]:
            for stock in list(current_positions.keys()):
                if stock in g.strategy_holdings[1]:
                    price = current_positions[stock].price
                    avg_cost = current_positions[stock].avg_cost
                    profit_ratio = (price - avg_cost) / avg_cost

                    # 100%翻倍止盈（保持不变）
                    if price >= avg_cost * 2:
                        log.info(f"[策略1] {format_stock_code(stock)} 收益100%止盈，卖出")
                        close_position(context, stock)
                        # 清除ATR止损价记录
                        if stock in g.atr_stop_prices:
                            del g.atr_stop_prices[stock]
                    # 成本保护止损逻辑
                    elif g.enable_cost_protection:
                        # 确定当前适用的止损线
                        if profit_ratio >= g.cost_protection_profit_threshold_2:
                            # 盈利 >= 30%，止损线上移到 +10%
                            stop_loss_line = g.cost_protection_stop_line_2
                            trigger_name = f"成本保护止损(盈利{profit_ratio:.1%}，止损线{stop_loss_line:.1%})"
                        elif profit_ratio >= g.cost_protection_profit_threshold_1:
                            # 盈利 >= 15%，止损线上移到成本价（0%）
                            stop_loss_line = g.cost_protection_stop_line_1
                            trigger_name = f"成本保护止损(盈利{profit_ratio:.1%}，止损线{stop_loss_line:.1%})"
                        else:
                            # 未达盈利阈值，使用原始固定止损线（-9%）
                            stop_loss_line = -g.stoploss_limit
                            trigger_name = "固定止损"

                        # 检查是否触发止损
                        if profit_ratio < stop_loss_line:
                            log.warn(
                                f"[策略1] {format_stock_code(stock)} 触发{trigger_name}，"
                                f"成本:{avg_cost:.2f} 现价:{price:.2f} 盈亏:{profit_ratio:.2%}，卖出"
                            )
                            close_position(context, stock)
							
                            # ==== 【新增代码】记录止损日期 ====
                            if g.check_after_no_buy:
                                g.no_buy_stocks[stock] = context.current_dt.date()
                            # ===============================
							
                            # 清除ATR止损价记录
                            if stock in g.atr_stop_prices:
                                del g.atr_stop_prices[stock]
                    # 如果未启用成本保护，使用原始固定止损
                    elif price < avg_cost * (1 - g.stoploss_limit):
                        log.warn(f"[策略1] {format_stock_code(stock)} 触发固定止损，卖出")
                        close_position(context, stock)
						
                        # ==== 【新增代码】记录止损日期 ====
                        if g.check_after_no_buy:
                            g.no_buy_stocks[stock] = context.current_dt.date()
                        # ===============================						
						
                        # 清除ATR止损价记录
                        if stock in g.atr_stop_prices:
                            del g.atr_stop_prices[stock]

        # 市场趋势止损 (策略2或3)
        if g.stoploss_strategy in [2, 3]:
            stock_df = get_price(
                security=get_index_stocks("399101.XSHE"),
                end_date=context.previous_date,
                frequency="daily",
                fields=["close", "open"],
                count=1,
                panel=False,
            )
            down_ratio = (stock_df["close"] / stock_df["open"] - 1).mean()
            if down_ratio <= -g.stoploss_market:
                log.warn(f"[策略1] 大盘惨跌，平均降幅 {down_ratio:.2%}")
                for stock in g.strategy_holdings[1][:]:
                    close_position(context, stock)
                    # 清除ATR止损价记录
                    if stock in g.atr_stop_prices:
                        del g.atr_stop_prices[stock]


""" ====================== 策略2: ETF反弹 ====================== """


# 原始中证2000策略
def trade_zz2000_etf(context):
    to_buy = False
    etf_index = "159536.XSHE"
    # 获取近3日的历史数据
    df = get_price(
        etf_index,
        end_date=context.previous_date,
        count=3,
        frequency="daily",
        fields=["high"],
    )
    df = df.reset_index()
    if len(df) < 3:
        return

    pre3_high_max = df["high"].max()

    # 获取当前盘中实时数据
    current_data = get_current_data()
    today_open = current_data[etf_index].day_open
    today_close = current_data[etf_index].last_price

    # 策略条件判断，开盘相比最高价下跌2% & 最新价相比开盘价涨1%
    if today_open / pre3_high_max < 0.98 and today_close / today_open > 1.01:
        to_buy = True

    # 已经持仓, 检查是否继续持有
    if etf_index in context.portfolio.positions:
        position = context.portfolio.positions[etf_index]
        trade_date = position.init_time
        holding_days = (
            len(get_trade_days(start_date=trade_date, end_date=context.current_dt)) - 1
        )
        if not to_buy and holding_days >= 2:
            close_position(etf_index)
            log.info(f"[策略2] 卖出：{etf_index}, 持仓{holding_days}天")
    elif to_buy:
        strategy_value = g.sub_account[2]['total_value']
        open_position(context, etf_index, strategy_value, 2)


def strategy_2_sell(context):
    cur_date = str(context.current_dt.date())
    if cur_date <= "2023-10-01":
        return

    g.buy_list = []
    sell_list = []
    sell_for_money_list = []
    # 获取近3日的历史数据
    for etf in g.etf_pool_2:
        df = get_price(
            etf,
            end_date=context.previous_date,
            count=4,
            frequency="daily",
            fields=["high", "close"],
        )
        df = df.reset_index()
        if len(df) < 4:
            return
        pre_high_max = df["high"].max()
        yestoday_close = df["close"].iloc[-1]
        # 获取当前盘中实时数据
        current_data = get_current_data()
        today_open = current_data[etf].day_open
        today_close = current_data[etf].last_price
        # 买入条件判断，开盘相比最高价下跌2% & 最新价相比开盘价涨1%
        if today_open / pre_high_max < 0.98 and today_close / today_open > 1.01:
            g.buy_list.append(etf)
        # 卖出条件判断，当前价格小于昨日收盘价
        if today_close < yestoday_close:
            sell_list.append(etf)

    # 保留最佳标的
    if g.buy_list:
        g.buy_list.sort(key=lambda x: g.etf_pool_2.index(x))
        selected_etf = g.buy_list[0]
        g.buy_list = [selected_etf]
        current_holdings = g.strategy_holdings[2]
        if current_holdings and g.etf_pool_2.index(
            current_holdings[0]
        ) < g.etf_pool_2.index(selected_etf):
            # 如果有持仓，且持有的ETF不是高优先级ETF，则清仓
            sell_for_money_list.append(current_holdings[0])

    for etf in g.strategy_holdings[2]:
        position = context.portfolio.positions[etf]
        security = position.security  # 股票代码
        trade_date = position.init_time
        holding_days = (
            len(get_trade_days(start_date=trade_date, end_date=context.current_dt)) - 1
        )
        if (
            (security in sell_list and holding_days >= g.limit_days)
            or (holding_days >= g.n_days)
            or (security in sell_for_money_list)
        ):
            close_position(security)
            log.info(f"[策略2] 卖出：{security}，持股 {holding_days}天")
    if not g.buy_list:
        log.info("[策略2] 今日无反弹可购买选项")


def strategy_2_buy(context):
    cur_date = str(context.current_dt.date())
    if cur_date <= "2023-10-01":
        return

    g.buy_list = list(set(g.buy_list) - set(g.strategy_holdings[2]))
    if len(g.buy_list) > 0:
        target_value_per_etf = g.sub_account[2]['total_value'] / len(g.buy_list)
        for etf in g.buy_list:
            open_position(context, etf, target_value_per_etf, 2)



""" ====================== 策略4: 白马攻防 ====================== """


def adjust_blue_chip_position(context):
    if not g.check_out_lists:
        prepare_blue_chip_before_open(context)
    buy_stocks = g.check_out_lists
    log.info(
        f"[策略4] 白马目标调仓: {','.join([f'{format_stock_code(i)}' for i in buy_stocks])}"
    )
    # 卖出不在目标列表中的股票（只处理本策略持仓）
    for stock in g.strategy_holdings[4][:]:
        current_data = get_current_data()
        if stock not in buy_stocks:
            if current_data[stock].last_price >= current_data[stock].high_limit:
                continue
            close_position(context, stock)
            log.info(f"[策略4] 白马策略调出: {stock}")

# 买入新标的
    position_count = len([s for s in context.portfolio.positions.keys() if s in g.strategy_holdings[4]])
    if len(buy_stocks) > position_count:
        # 直接使用策略4子账户的总资产
        value = g.sub_account[4]['total_value'] / g.stock_num_2
        
        current_data = get_current_data()
        valid_buy_stocks = [s for s in buy_stocks if not (current_data[s].last_price >= current_data[s].high_limit or current_data[s].last_price <= current_data[s].low_limit)]
        
        for stock in valid_buy_stocks:
            if stock not in g.strategy_holdings[4]:
                if open_position(context, stock, value, 4):
                    if len(g.strategy_holdings[4]) >= g.stock_num_2:
                        break


# 市场温度判断
def calculate_market_temperature(context):
    # 数据回滚两年判断市场温度
    if not hasattr(g, "market_temperature"):
        long_index300 = list(
            attribute_history("000300.XSHG", 220 * 3, "1d", ("close",), df=False)[
                "close"
            ]
        )
        g.market_temperature = "cold"
        for back_day in range(220, len(long_index300)):
            index300 = long_index300[back_day - 220 : back_day]
            market_height = (mean(index300[-5:]) - min(index300)) / (
                max(index300) - min(index300)
            )
            if market_height < 0.20:
                g.market_temperature = "cold"
            elif market_height > 0.80:
                g.market_temperature = "hot"
            elif max(index300[-60:]) / min(index300) > 1.20:
                g.market_temperature = "warm"
    # 当前一年的温度判断
    index300 = attribute_history("000300.XSHG", 220, "1d", ("close",), df=True).drop(
        pd.to_datetime("2024-10-08"), errors="ignore"
    )
    index300 = index300["close"].tolist()
    market_height = (mean(index300[-5:]) - min(index300)) / (
        max(index300) - min(index300)
    )
    if market_height < 0.20:
        g.market_temperature = "cold"
    elif index300[-1] == min(index300):
        g.market_temperature = "cold"
    elif market_height > 0.90:
        g.market_temperature = "hot"
    elif index300[-1] == max(index300):
        g.market_temperature = "hot"
    elif max(index300[-60:]) / min(index300) > 1.20:
        g.market_temperature = "warm"


# 开盘前运行函数
def prepare_blue_chip_before_open(context):
    calculate_market_temperature(context)
    g.check_out_lists = []
    current_data = get_current_data()
    all_stocks = get_index_stocks("000300.XSHG")
    all_stocks = [
        stock
        for stock in all_stocks
        if not (
            (
                current_data[stock].last_price
                > round(
                    context.portfolio.total_value
                    * g.portfolio_value_proportion[0]
                    * 0.95
                    / g.stock_num_2
                    / 100,
                    2,
                )
            )
            #or (current_data[stock].day_open == current_data[stock].high_limit)
            #or (current_data[stock].day_open == current_data[stock].low_limit)
            or current_data[stock].paused
            or current_data[stock].is_st
            or ("ST" in current_data[stock].name)
            or ("*" in current_data[stock].name)
            or ("退" in current_data[stock].name)
            or (stock.startswith("30"))
            or (stock.startswith("68"))
            or (stock.startswith("8"))
            or (stock.startswith("4"))
        )
    ]
    last_prices = history(1, unit="1d", field="close", security_list=all_stocks)
    all_stocks = [
        stock for stock in all_stocks if last_prices[stock][-1] <= 100
    ]  # 过滤高价股

    q = None
    if g.market_temperature == "cold":
        q = (
            query(valuation.code, indicator.roe, indicator.roa)
            .filter(
                valuation.pb_ratio > 0,
                valuation.pb_ratio < 1,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit
                > 2.0,
                indicator.inc_return > 1.5,
                indicator.inc_net_profit_year_on_year > -15,
                valuation.code.in_(all_stocks),
            )
            .order_by((indicator.roa / valuation.pb_ratio).desc())
            .limit(50)
        )
    elif g.market_temperature == "warm":
        q = (
            query(valuation.code, indicator.roe, indicator.roa)
            .filter(
                valuation.pb_ratio > 0,
                valuation.pb_ratio < 1,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit
                > 1.0,
                indicator.inc_return > 2.0,
                indicator.inc_net_profit_year_on_year > 0,
                valuation.code.in_(all_stocks),
            )
            .order_by((indicator.roa / valuation.pb_ratio).desc())
            .limit(50)
        )
    elif g.market_temperature == "hot":
        q = (
            query(valuation.code, indicator.roe, indicator.roa)
            .filter(
                valuation.pb_ratio > 3,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 0.5,
                indicator.inc_return > 3.0,
                indicator.inc_net_profit_year_on_year > 20,
                valuation.code.in_(all_stocks),
            )
            .order_by(indicator.roa.desc())
            .limit(50)  # *10
        )

    df = get_fundamentals(q)
    df.index = df["code"].values

    roe_inv_rank = df["roe"].rank(ascending=False)
    roa_inv_rank = df["roa"].rank(ascending=False)

    df["point"] = g.roe * roe_inv_rank + g.roa * roa_inv_rank

    df = df.sort_values(by="point")

    check_out_lists = list(df.code)
    # 动量趋势过滤，剔除太高和太低的
    check_out_lists2 = moment_rank(check_out_lists, 25, -1.0, 10.5)
    # 顺序还是按照动量趋滤前原来的顺序
    check_out_lists = [x for x in check_out_lists if x in check_out_lists2]
    g.check_out_lists = check_out_lists[: g.stock_num_2]
    log.info(f"[策略4] 今日市场温度：{g.market_temperature}")
    log.info(f"[策略4] 今日白马股票池：{g.check_out_lists}")


# 动量计算
def moment_rank(stock_pool, days, ll, hh):
    def mom(_stock):
        y = np.log(attribute_history(_stock, days, "1d", ["close"], df=False)["close"])
        n = len(y)
        x = np.arange(n)
        weights = np.linspace(1, 2, n)
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        residuals = y - (slope * x + intercept)
        weighted_residuals = weights * residuals**2
        r_squared = 1 - (
            np.sum(weighted_residuals) / np.sum(weights * (y - np.mean(y)) ** 2)
        )
        return annualized_returns * r_squared

    score_list = []
    for stock in stock_pool:
        score = mom(stock)
        score_list.append(score)
    df = pd.DataFrame(index=stock_pool, data={"score": score_list})
    df = df.sort_values(by="score", ascending=False)  # 降序
    df = df[(df["score"] > ll) & (df["score"] < hh)]
    rank_list = list(df.index)
    return rank_list


""" ====================== 辅助的定时执行函数 ====================== """

def smart_open_15(context, security, value):
    if value < g.min_money: return
    curr_data = get_current_data()[security]
    if curr_data.paused or curr_data.last_price >= curr_data.high_limit: return
    
    cur_val = context.portfolio.positions[security].value if security in context.portfolio.positions else 0
    if abs(cur_val - value) > value * 0.05 or cur_val == 0:
        if order_target_value(security, value):
            if security not in g.strategy_holdings[3]:
                g.strategy_holdings[3].append(security)
                g.stock_strategy[security] = 3
            g.position_highs[security] = curr_data.last_price

def smart_close_15(security):
    curr_data = get_current_data()[security]
    if curr_data.paused or curr_data.last_price <= curr_data.low_limit: return
    o = order_target_value(security, 0)
    if o:
        if hasattr(o, "price") and hasattr(o, "avg_cost") and hasattr(o, "amount"):
            try:
                g.strategy_value[3] += (o.price - o.avg_cost) * o.amount
            except (TypeError, ValueError):
                pass
        if security in g.strategy_holdings[3]:
            g.strategy_holdings[3].remove(security)
        if security in g.position_highs:
            del g.position_highs[security]
        if security in g.stock_strategy:
            del g.stock_strategy[security]

def check_atr_stop_loss_15(context):
    if not g.use_atr_stop_loss: return
    for s in g.strategy_holdings[3][:]:
        if g.atr_exclude_defensive and s == g.defensive_etf: continue
        h = attribute_history(s, g.atr_period + 5, '1d', ['high', 'low', 'close'])
        tr = np.maximum(h['high'].values[1:] - h['low'].values[1:], 
                        np.maximum(abs(h['high'].values[1:] - h['close'].values[:-1]), 
                                   abs(h['low'].values[1:] - h['close'].values[:-1])))
        atr = np.mean(tr[-g.atr_period:])
        curr_p = get_current_data()[s].last_price
        g.position_highs[s] = max(g.position_highs.get(s, 0), curr_p)
        base_p = g.position_highs[s] if g.atr_trailing_stop else context.portfolio.positions[s].avg_cost
        if curr_p <= (base_p - g.atr_multiplier * atr):
            log.info(f"🚨 ATR止损: {s}")
            smart_close_15(s)

def calculate_rsi_15(prices, period):
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period]); avg_loss = np.mean(losses[:period])
    rsi = [100 - (100 / (1 + avg_gain/avg_loss)) if avg_loss != 0 else 100]
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi.append(100 - (100 / (1 + avg_gain/avg_loss)) if avg_loss != 0 else 100)
    return np.array(rsi)

def get_annualized_returns_15(price_series, days):
    y = np.log(price_series[-days-1:])
    slope, _ = np.polyfit(np.arange(len(y)), y, 1, w=np.linspace(1, 2, len(y)))
    return math.exp(slope * 250) - 1

def get_best_defensive_asset(context):
    """比较防御池中的资产，选出过去20天涨幅最好的"""
    best_etf = g.etf3_defensive_pool[0]
    max_ret = -999.0
    
    for etf in g.etf3_defensive_pool:
        try:
            # 获取过去20天数据
            df = attribute_history(etf, 20, '1d', ['close'])
            if len(df) > 10:
                # 简单计算区间涨幅
                ret = (df['close'][-1] / df['close'][0]) - 1
                if ret > max_ret:
                    max_ret = ret
                    best_etf = etf
        except:
            continue
            
    return best_etf

# 大盘顶背离
def check_macd_divergence(context, market_index="399101.XSHE", end_days=0):
    """
    大盘顶背离检测：通过MACD判断市场潜在反转风险
    目的：在大盘出现顶背离（上涨乏力）时提前减仓，规避系统性下跌
    """
    # 把第一次9:31执行的给忽略掉, 第一次9:49会回溯过去10天, 避免第一次造成干扰(其实也不会, 但看日志会看的不会有困惑)
    if not g.dbl and "9:31" in str(context.current_dt.time()):
        return

    def detect_divergence():
        """检测顶背离（价格新高但MACD指标走弱，预示趋势反转）
        条件：
        1. 价格创新高（后高>前高）
        2. MACD指标未创新高（后低<前低）
        3. MACD由正转负（趋势转弱）
        4. DIF处于下降趋势（近期均值<前期均值）
        """
        fast, slow, sign = 12, 26, 9  # MACD参数
        rows = (fast + slow + sign) * 5  # 确保足够数据量（约1年）
        # 获取历史收盘价数据
        grid = attribute_history(market_index, rows + 10, fields=["close"]).dropna()
        if end_days < 0:
            grid = grid.iloc[:end_days]

        if len(grid) < rows:
            log.warn(f"[顶背离] {market_index} 数据不足 {rows} 天，无法检测顶背离")
            return False

        try:
            # 计算MACD指标
            grid["dif"], grid["dea"], grid["macd"] = mcad(grid.close, fast, slow, sign)

            # 寻找死叉点（MACD由正转负的时刻）
            mask = (grid["macd"] < 0) & (grid["macd"].shift(1) >= 0)
            if mask.sum() < 2:
                log.warn(f"[顶背离] {market_index} 死叉点不足2个，无法检测顶背离")
                return False

            # 取最近两个死叉点（前一个与当前）
            key2, key1 = mask[mask].index[-2], mask[mask].index[-1]

            # 顶背离核心条件
            price_cond = grid.close[key2] < grid.close[key1]  # 价格创新高（后高>前高）
            dif_cond = grid.dif[key2] > grid.dif[key1] > 0  # DIF未创新高（后低<前高）且为正
            macd_cond = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]  # MACD由正转负

            # 趋势验证：DIF近期处于下降趋势（近10日均值<前10日均值）
            if len(grid["dif"]) > 20:
                recent_avg = grid["dif"].iloc[-10:].mean()  # 近10日DIF均值
                prev_avg = grid["dif"].iloc[-20:-10].mean()  # 前10日DIF均值
                trend_cond = recent_avg < prev_avg
            else:
                trend_cond = False

            return price_cond and dif_cond and macd_cond and trend_cond

        except Exception as e:
            log.error(f"[顶背离] {market_index} 顶背离检测错误: {e}")
            return False

    if market_index != "399101.XSHE":
        res = 1 if detect_divergence() else 0
        if res:
            log.warn(f"[顶背离] {market_index} 触发顶背离了!!!!! 快跑 !!!!!")
        return res

    if detect_divergence():
        g.dbl.append(1)
        log.warn(f"[顶背离] ⚠️ 检测到{market_index}顶背离信号（价格新高但MACD走弱），清仓非涨停股票")

        current_data = get_current_data()

        for stock in g.strategy_holdings[1][:]:
            if current_data[stock].last_price < current_data[stock].high_limit:
                log.warn(f"[顶背离] {stock} 因大盘顶背离清仓（非涨停股）")
                close_position(context, stock)
    else:
        g.dbl.append(0)


def preload_etf_data(etf_pool, days=250):
    """
    批量预加载所有ETF的历史数据（性能优化）

    参数:
        etf_pool: ETF列表
        days: 需要获取的历史天数

    返回:
        data_cache: 数据缓存字典 {stock: dict{'hist': DataFrame, 'current_price': float}}
    """
    log.info(f"[ETF轮动] 正在批量加载 {len(etf_pool)} 个ETF的历史数据（{days}天）...")
    data_cache = {}
    current_data = get_current_data()

    for etf in etf_pool:
        try:
            # 一次性获取所有需要的字段
            hist_data = attribute_history(etf, days, "1d", ["close", "high", "low", "volume"])
            if not hist_data.empty:
                # 添加当前价格到数据中
                current_price = current_data[etf].last_price
                data_cache[etf] = {
                    'hist': hist_data,
                    'current_price': current_price
                }
        except Exception as e:
            log.error(f"[ETF轮动] 加载{etf}数据失败: {e}")
            continue

    log.info(f"[ETF轮动] 数据加载完成，成功加载 {len(data_cache)} 个ETF的数据")
    return data_cache

# 动量计算（使用缓存数据）
def filter_moment_rank(stock_pool, days, ll, hh, data_cache, show_print=True):
    """
    动量得分计算（使用缓存数据）

    参数:
        stock_pool: 股票列表
        days: 参考天数
        ll: 得分下限
        hh: 得分上限
        data_cache: 预加载的数据缓存
        show_print: 是否打印结果
    """
    log.debug("[ETF轮动] 计算动量得分" + "*" * 60)

    scores_data = pd.DataFrame(
        index=stock_pool, columns=["annualized_returns", "r2", "score"]
    )
    print_info = {}

    for code in stock_pool:
        try:
            # 从缓存中获取数据
            if code not in data_cache:
                continue

            cached_data = data_cache[code]
            hist_data = cached_data['hist']
            current_price = cached_data['current_price']

            if hist_data.empty or len(hist_data) < days:
                continue

            # 使用最近days天的数据
            recent_data = hist_data.tail(days)
            prices = np.append(recent_data["close"].values, current_price)
            log_prices = np.log(prices)
            x_values = np.arange(len(log_prices))
            weights = np.linspace(1, 2, len(log_prices))

            slope, intercept = np.polyfit(x_values, log_prices, 1, w=weights)
            annualized_return = math.exp(slope * 250) - 1
            scores_data.loc[code, "annualized_returns"] = annualized_return

            ss_res = np.sum(
                weights * (log_prices - (slope * x_values + intercept)) ** 2
            )
            ss_tot = np.sum(weights * (log_prices - np.mean(log_prices)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            scores_data.loc[code, "r2"] = r2

            momentum_score = annualized_return * r2
            scores_data.loc[code, "score"] = momentum_score

            if (
                min(
                    prices[-1] / prices[-2],
                    prices[-2] / prices[-3],
                    prices[-3] / prices[-4],
                )
                < 0.97
            ):
                scores_data.loc[code, "score"] = 0
            print_info[code] = scores_data.loc[code, "score"]

        except Exception as e:
            log.error(f"[ETF轮动] 计算{code}动量得分失败: {e}")
            scores_data.loc[code, "score"] = 0

    valid_etfs = scores_data[
        (scores_data["score"] > ll) & (scores_data["score"] < hh)
    ].sort_values("score", ascending=False)
    rank_list = valid_etfs.index.tolist()
    if show_print and rank_list:
        for i in rank_list:
            log.debug(f"[ETF轮动] {format_stock_code(i)} ({print_info[i]:.4f})")
    return rank_list

# 尾盘记录各个策略的收益
def make_record(context):
    positions = context.portfolio.positions
    current_data = get_current_data()
    # 模拟盘热更新或恢复旧状态时，g 里可能没有这个字段，先做兜底初始化避免策略暂停。
    g.xsz_pnl_realized_cumulative = float(
        getattr(g, "xsz_pnl_realized_cumulative", 0.0)
    )
    
    for sid in range(1, 5):
        # 1. 计算该子策略当前持仓的总市值
        holdings_value = 0
        for stock in g.strategy_holdings.get(sid, []):
            pos = positions.get(stock)
            if pos and pos.total_amount > 0:
                holdings_value += pos.total_amount * current_data[stock].last_price
                
        # 2. 刷新子账户总资产 = 子账户现金 + 子账户持仓市值
        g.sub_account[sid]['total_value'] = g.sub_account[sid]['cash'] + holdings_value
        g.strategy_value_data[sid] = holdings_value  # 用于UI打印展示市值
        
        # 3. 记录日志给聚宽收益图表
        if g.portfolio_value_proportion[sid-1] > 0:
            returns = (g.sub_account[sid]['total_value'] / g.sub_account[sid]['initial_capital'] - 1) * 100
            
            # 统一口径：小市值仅表示“选股本身盈亏/策略1初始本金”，不再记录槽位权益收益，
            # 避免在 [0.5,0,0.5,0] 下被组合总资产再平衡放大而出现误读。
            if sid == 1:
                unrealized = 0.0
                for stk in g.strategy_holdings.get(1, []):
                    p = positions.get(stk)
                    if p and p.total_amount > 0:
                        unrealized += float(p.value) - float(p.avg_cost) * float(
                            p.total_amount
                        )
                ic = float(g.sub_account[1]["initial_capital"])
                total_pnl = float(g.xsz_pnl_realized_cumulative) + unrealized
                pure_pct = (total_pnl / ic * 100.0) if ic > 0 else 0.0
                record(小市值=round(pure_pct, 2))
            elif sid == 2:
                record(ETF反弹=round(returns, 2))
            elif sid == 3:
                record(ETF轮动=round(returns, 2))
            elif sid == 4:
                record(白马攻防=round(returns, 2))

    # 删除会导致严重混乱的历史资金平衡操作
    # 彻底让4个策略各自安好

def print_summary(context):
    """打印当前投资组合的总资产和持仓详情"""
    total_value = round(context.portfolio.total_value, 2)

    current_stocks = context.portfolio.positions
    if not current_stocks:
        log.info(f"[持仓] 当前总资产: {total_value} 休息ing")
        return

    # 创建表格
    table = PrettyTable(
        [
            " 所属策略 ",
            " 股票代码 ",
            " 股票名称 ",
            " 持仓数量 ",
            " 持仓价格 ",
            " 当前价格 ",
            " 盈亏数额 ",
            " 盈亏比例 ",
            " 股票市值 ",
            " 仓位占比 ",
        ]
    )
    table.hrules = prettytable.ALL

    total_market_value = 0
    for stock in current_stocks:
        current_shares = current_stocks[stock].total_amount  # 持仓数量
        current_price = round(get_current_data()[stock].last_price, 3)  # 当前价格
        avg_cost = round(current_stocks[stock].avg_cost, 3)  # 持仓平均成本

        # 计算盈亏比例
        profit_ratio = (current_price - avg_cost) / avg_cost if avg_cost != 0 else 0
        profit_ratio_percent = f"{profit_ratio * 100:.2f}%"  # 转为百分比并保留两位小数
        profit_ratio_percent += f" {'↑' if profit_ratio > 0 else '↓'}"
        # 计算盈亏数额
        profit_amount = round((current_price - avg_cost) * current_shares, 2)

        # 计算市值
        market_value = round(current_shares * current_price, 2)
        total_market_value += market_value  # 累加总市值

        # 处理股票代码：移除后缀
        stock_code = stock.split(".")[0]  # 只保留股票代码部分

        # 添加到表格
        table.add_row(
            [
                g.stock_strategy.get(stock, "未标记"),
                stock_code,
                format_stock_code(stock),
                current_shares,
                avg_cost,
                current_price,
                profit_amount,
                profit_ratio_percent,
                market_value,
                f"{market_value / context.portfolio.total_value * 100:.2f}%",
            ]
        )

    # 账户总资产
    total_value = context.portfolio.total_value
    # 汇总
    if g.strategy_value_data[1]:
        table.add_row(
            [
                "小市值",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                f"{g.strategy_value_data[1]:.2f}",
                f"{g.strategy_value_data[1] / total_value * 100:.2f}%",
            ]
        )
    if g.strategy_value_data[2]:
        table.add_row(
            [
                "ETF反弹",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                f"{g.strategy_value_data[2]:.2f}",
                f"{g.strategy_value_data[2] / total_value * 100:.2f}%",
            ]
        )
    if g.strategy_value_data[3]:
        table.add_row(
            [
                "ETF轮动",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                f"{g.strategy_value_data[3]:.2f}",
                f"{g.strategy_value_data[3] / total_value * 100:.2f}%",
            ]
        )
    if g.strategy_value_data[4]:
        table.add_row(
            [
                "白马攻防",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                f"{g.strategy_value_data[4]:.2f}",
                f"{g.strategy_value_data[4] / total_value * 100:.2f}%",
            ]
        )
    table.add_row(["总市值", "", "", "", "", "", "", "", f"{total_market_value:.2f}", ""])
    table.add_row(["总资产", "", "", "", "", "", "", "", f"{total_value:.2f}", ""])

    log.info(f"[持仓] 当前总资产\n{table}")


# 小市值换手检测
def check_small_cap_turnover(context):
    huanshou(context, stock_list=g.strategy_holdings[1][:])


# ETF轮动日内止损检测
def etf_stop_loss_by_cur_day(context):
    holdings = set(g.strategy_holdings[3])
    # 检测日内亏损
    stop_loss_by_cur_day(holdings, ratio=g.stoploss_limit_by_cur_day)


""" ====================== 公共函数 ====================== """


def filter_cooldown_stocks(context, stock_list):
    """
    过滤处于止损冷却期（小黑屋）的股票
    """
    if not g.check_after_no_buy:
        return stock_list

    current_date = context.current_dt.date()
    valid_stocks = []
    
    for stock in stock_list:
        if stock in g.no_buy_stocks:
            stop_date = g.no_buy_stocks[stock]
            # 计算距离止损日已经过去的交易日天数
            trade_days = get_trade_days(start_date=stop_date, end_date=current_date)
            passed_days = len(trade_days) - 1  # 减去止损当天
            
            if passed_days < g.no_buy_after_day:
                log.info(f"[冷却过滤] {format_stock_code(stock)} 于 {stop_date} 止损，距今 {passed_days} 个交易日，仍在 {g.no_buy_after_day} 天冷却期内，跳过。")
                continue
            else:
                # 冷却期已过，从小黑屋中释放
                del g.no_buy_stocks[stock]
        
        valid_stocks.append(stock)
        
    return valid_stocks


def stop_loss_by_cur_day(stock_list, ratio=-0.03):
    for stock in stock_list:
        cur_ratio = cal_cur_to_open_ratio(stock)
        if cur_ratio < ratio:
            log.warn(
                f"[日内止损] {format_stock_code(stock)} 距离开盘跌幅 {cur_ratio * 100:.2f}% 清仓处理"
            )
            close_position(context, stock)


""" ====================== 模块工具函数 ====================== """


# 展示优化
def format_stock_code(stock_code):
    try:
        stock_info = get_security_info(stock_code)
    except Exception:
        return f"{stock_code[:6]}"
    return f"{stock_code[:6]}({stock_info.display_name}) "


# 筛选审计意见
def filter_audit(context, code_list):
    # 获取审计意见，近三年内如果有不合格(report_type为3、4、5、7)的审计意见则返回False，否则返回True
    final_list = []
    """
    审计意见类型编码
        类型编码 审计意见类型
        1 	     无保留
        2 	     无保留带解释性说明
        3        保留意见
        4        拒绝/无法表示意见
        5        否定意见
        6 	     未经审计
        7 	     保留带解释性说明
        10 	     经审计（不确定具体意见类型）
        11       无保留带持续经营重大不确定性
    """
    for stock in code_list:
        previous_date = context.previous_date
        last_year = (
            previous_date.replace(year=previous_date.year - 3, month=1, day=1)
        ).strftime("%Y-%m-%d")
        q = query(
            finance.STK_AUDIT_OPINION.code,
            finance.STK_AUDIT_OPINION.pub_date,
            finance.STK_AUDIT_OPINION,
        ).filter(
			finance.STK_AUDIT_OPINION.code == stock,
			finance.STK_AUDIT_OPINION.pub_date >= last_year,
			finance.STK_AUDIT_OPINION.pub_date <= context.previous_date  # 增加上限，阻断未来函数
        )
        df = finance.run_query(q)
        values_to_check = [3, 4, 5, 7]
        if not df["opinion_type_id"].isin(values_to_check).any():
            final_list.append(stock)
    return final_list


# 获取红利列表
def bonus_filter(context, stock_list):
    year = context.previous_date.year
    start_date = datetime.datetime(year=year, month=1, day=1)
    end_date = context.previous_date
    if end_date.month in [5]:
        q = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.company_name,
            finance.STK_XR_XD.board_plan_pub_date,
            finance.STK_XR_XD.bonus_amount_rmb,
            finance.STK_XR_XD.bonus_ratio_rmb,
        ).filter(
            finance.STK_XR_XD.board_plan_pub_date > start_date,
            finance.STK_XR_XD.implementation_pub_date <= end_date,
            finance.STK_XR_XD.bonus_ratio_rmb > 0,
            finance.STK_XR_XD.code.in_(stock_list),
        )
        expected_bonus_df = finance.run_query(q)

        if len(expected_bonus_df) > 0:
            bonus_list = expected_bonus_df["code"].unique().tolist()
            price_df = history(
                1,
                unit="1d",
                field="close",
                security_list=bonus_list,
                df=True,
                skip_paused=False,
                fq=None,
            )
            price_df = price_df.T
            price_df.rename(columns={price_df.columns[0]: "Close_now"}, inplace=True)
            price_df["code"] = price_df.index
            expected_bonus_df = pd.merge(
                expected_bonus_df, price_df, on=("code",), how="left"
            )
            expected_bonus_df["bonus_ratio"] = (
                expected_bonus_df["bonus_ratio_rmb"]
            ) / expected_bonus_df["Close_now"]
            expected_bonus_df = expected_bonus_df.sort_values(
                by="bonus_ratio", ascending=True
            )
            bonus_list = expected_bonus_df["code"].unique().tolist()
        else:
            bonus_list = []
    else:
        reprot_date = datetime.datetime(year=year - 1, month=12, day=31)
        q = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.company_name,
            finance.STK_XR_XD.a_registration_date,
            finance.STK_XR_XD.bonus_amount_rmb,
            finance.STK_XR_XD.bonus_ratio_rmb,
        ).filter(
            finance.STK_XR_XD.report_date == reprot_date,
            finance.STK_XR_XD.bonus_type == "年度分红",
            finance.STK_XR_XD.implementation_pub_date <= end_date,
            finance.STK_XR_XD.board_plan_bonusnote == "不分配不转增",
            finance.STK_XR_XD.code.in_(stock_list),
        )

        no_year_bonus = finance.run_query(q)
        no_year_bonus_list = no_year_bonus["code"].unique().tolist()
        # 排除今年不分红的股票
        bonus_list = [code for code in stock_list if code not in no_year_bonus_list]
        bonus_list = short_by_market_cap(context, bonus_list)

    if len(bonus_list) < g.xsz_stock_num:
        bonus_list.extend(
            [
                x
                for x in short_by_market_cap(context, stock_list)
                if x not in bonus_list
            ][: g.xsz_stock_num - len(bonus_list)]
        )
    return bonus_list


# 计算RSI指标
def calculate_rsi(code, period=14):
    """计算RSI指标"""
    df = attribute_history(
        code,
        125,
        "1d",
        [
            "close",
        ],
        skip_paused=True,
        df=True,
        fq="pre",
    )
    prices = df["close"].values
    deltas = np.diff(prices)
    seed = deltas[: period + 1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    if down == 0:
        return 100
    rs = up / down
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi


#  基础过滤各种股票
def filter_stocks(context, stock_list):
    current_data = get_current_data()
    # 涨跌停和最近价格的判断
    last_prices = history(1, unit="1m", field="close", security_list=stock_list)
    # 过滤标准
    filtered_stocks = []
    for stock in stock_list:
        if current_data[stock].paused:  # 停牌
            continue
        if current_data[stock].is_st:  # ST
            continue
        if "退" in current_data[stock].name:  # 退市
            continue
        if (
            stock.startswith("30")
            or stock.startswith("68")
            or stock.startswith("8")
            or stock.startswith("4")
        ):  # 市场类型
            continue
        if not (
            stock in context.portfolio.positions
            or last_prices[stock][-1] < current_data[stock].high_limit
        ):  # 涨停
            continue
        if not (
            stock in context.portfolio.positions
            or last_prices[stock][-1] > current_data[stock].low_limit
        ):  # 跌停
            continue
        # 次新股过滤
        start_date = get_security_info(stock).start_date
        if context.previous_date - start_date < timedelta(days=375):
            continue
        filtered_stocks.append(stock)
    return filtered_stocks


# 计算最新价格对比开盘价格的比值
def cal_cur_to_open_ratio(security):
    current_data = get_current_data()
    last_price = current_data[security].last_price
    day_open = current_data[security].day_open
    return (last_price - day_open) / day_open


# 计算MACD指标
def mcad(close, short=12, long=26, m=9):
    """计算 MACD 指标
    用于判断趋势强度和潜在反转点，由 DIF、DEA、MACD 柱组成

    参数:
        close: 收盘价序列
        short: 短期EMA周期（默认12）
        long: 长期EMA周期（默认26）
        m: 信号周期（默认9）

    返回:
        DIF: 短期EMA与长期EMA的差值
        DEA: DIF的M期EMA
        MACD: (DIF-DEA)*2（放大波动）
    """

    # 计算指数移动平均线
    def ema(series, n):
        """计算指数移动平均线（Exponential Moving Average）
        用于平滑价格波动，反映近期价格趋势，权重随时间递减

        参数:
            series: 价格序列（如收盘价）
            N: 计算周期

        返回:
            EMA序列
        """
        return pd.Series.ewm(series, span=n, min_periods=n - 1, adjust=False).mean()

    dif = ema(close, short) - ema(close, long)
    dea = ema(dif, m)
    return dif, dea, (dif - dea) * 2


# 换手检测
def huanshou(context, stock_list):
    # 换手率计算
    def huanshoulv(_stock, is_avg=False):
        if is_avg:
            # 计算平均换手率
            end_date = context.previous_date
            df_volume = get_price(
                _stock,
                end_date=end_date,
                frequency="daily",
                fields=["volume"],
                count=20,
            )
            df_cap = get_valuation(
                _stock, end_date=end_date, fields=["circulating_cap"], count=1
            )
            circulating_cap = (
                df_cap["circulating_cap"].iloc[0] if not df_cap.empty else 0
            )
            if circulating_cap == 0:
                return 0.0
            df_volume["turnover_ratio"] = df_volume["volume"] / (
                circulating_cap * 10000
            )
            return df_volume["turnover_ratio"].mean()
        else:
            # 计算实时换手率
            date_now = context.current_dt
            df_vol = get_price(
                _stock,
                start_date=date_now.date(),
                end_date=date_now,
                frequency="1m",
                fields=["volume"],
                skip_paused=False,
                fq="pre",
                panel=True,
                fill_paused=False,
            )
            volume = df_vol["volume"].sum()
            date_pre = context.previous_date
            df_circulating_cap = get_valuation(
                _stock, end_date=date_pre, fields=["circulating_cap"], count=1
            )
            circulating_cap = (
                df_circulating_cap["circulating_cap"].iloc[0]
                if not df_circulating_cap.empty
                else 0
            )
            if circulating_cap == 0:
                return 0.0
            turnover_ratio = volume / (circulating_cap * 10000)
            return turnover_ratio

    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in stock_list:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        rt = huanshoulv(stock, False)
        avg = huanshoulv(stock, True)
        if avg == 0:
            continue
        r = rt / avg
        action, icon = "", ""
        if avg < 0.003:
            action, icon = "缩量", "❄️"
        elif rt > expand and r > 2:
            action, icon = "放量", "🔥"
        if action:
            log.warn(
                f"[换手] {action} {format_stock_code(stock)}  换手率:{rt:.2%}  均:{avg:.2%} 倍率:x{r:.1f} {icon}"
            )
            close_position(context, stock)


# 成交量宽度防御检测
def check_defense_trigger(context):
    """改进后的防御条件检查"""

    # 计算宽度
    def get_market_breadth(ma_days):
        required_days = ma_days + 10
        end_date = context.current_dt.replace(hour=14, minute=49)

        # 获取行业分类数据
        sw_l1 = get_industries("sw_l1", date=context.current_dt.date())
        industry_stocks = {}
        for idx, row in sw_l1.iterrows():
            ind_stocks = get_industry_stocks(idx, date=end_date)
            industry_stocks[row["name"]] = ind_stocks  # 存储行业对应的股票列表

        # 获取所有股票
        all_stocks = []
        for stocks in industry_stocks.values():
            all_stocks.extend(stocks)
        all_stocks = list(set(all_stocks))  # 去重

        # 获取价格和成交额数据
        data = get_bars(
            all_stocks,
            end_dt=end_date,
            count=required_days,
            unit="1d",
            fields=["date", "close", "volume", "money"],
            include_now=True,
            df=True,
        )

        # 处理价格数据：用level_1作为索引（行号），level_0作为股票代码列
        price_reset = data.reset_index()
        price_data = price_reset.pivot(
            index="level_1", columns="level_0", values="close"
        )  # 按要求的透视表写法

        # 计算移动平均和站上均线的股票占比
        ma = price_data.rolling(window=ma_days).mean()
        above_ma = price_data > ma

        # 核心逻辑：按透视表处理20日成交金额，计算平均值后再分组
        # 1. 重置索引并创建成交额透视表（行=行号，列=股票代码，值=成交额）
        money_reset = data.reset_index()
        money_pivot = money_reset.pivot(
            index="level_1", columns="level_0", values="money"
        )  # 成交额透视表

        recent_20d_money_pivot = money_pivot.tail(20)  # 关键：直接从透视表取最近20天

        avg_money = recent_20d_money_pivot.mean().reset_index()  # 按列求平均
        avg_money.columns = ["code", "avg_money"]  # 重命名列：股票代码、平均成交额

        # 4. 按平均成交额排序并分为20组
        avg_money = avg_money.sort_values("avg_money", ascending=False)
        # 使用qcut进行分组，处理可能的重复值
        avg_money["money_group"] = pd.qcut(
            avg_money["avg_money"],
            20,
            labels=[f"组{i + 1}" for i in range(20)],
            duplicates="drop",
        )

        # 5. 创建成交额分组字典（组名: 股票列表）
        money_groups = {
            group: group_df["code"].tolist()
            for group, group_df in avg_money.groupby("money_group")
        }

        # 6. 计算每个成交额组站上均线的股票比例
        group_scores = pd.DataFrame(index=price_data.index)
        for group, stocks in money_groups.items():
            valid_stocks = list(set(above_ma.columns) & set(stocks))
            if valid_stocks:
                group_scores[group] = (
                    100 * above_ma[valid_stocks].sum(axis=1) / len(valid_stocks)
                )

        # 7. 计算近3天各组平均站上均线比例
        recent_group_data = group_scores[-3:].mean()
        _sorted_ma_data = recent_group_data.sort_values(ascending=False)

        # 8. 处理涨跌幅数据和每日指标
        df = data.reset_index().rename(
            columns={"level_0": "symbol", "level_1": "index"}
        )
        df["pct_change"] = df.groupby(["symbol"])["close"].pct_change()

        trade_days = get_trade_days(end_date=context.current_dt, count=3)
        by_date = trade_days[0]
        df = df[df.date >= by_date]

        grouped = df.groupby("date")
        _result = pd.DataFrame(
            {
                "up_ratio": grouped["pct_change"].apply(lambda x: (x > 0).mean()),
                "down_over": grouped["pct_change"].apply(
                    lambda x: (x <= -0.0985).sum()
                ),
            }
        ).reset_index()
        return _sorted_ma_data, _result

    # 计算趋势指标
    def calculate_trend_indicators(index_symbol="399101.XSHE"):
        """计算趋势指标: 过去3天内只要有一天处于高位，则视为高位，避免边界问题）"""
        # 参数设置
        high_lookback = 60  # 近期高点观察窗口
        high_proximity = 0.95  # 接近高点的阈值（95%）
        check_days = 2  # 检查过去1天的状态

        end_date = context.current_dt.replace(hour=14, minute=49)

        # 获取历史数据（需要包含足够天数，用于计算过去5天的指标）
        # 为了计算过去5天的指标，需要多获取high_lookback天数据（避免边界问题）
        total_days_needed = high_lookback + 10
        data = get_bars(
            index_symbol,
            end_dt=end_date,
            count=total_days_needed,
            unit="1d",
            fields=["date", "close", "high", "avg", "volume"],
            include_now=True,
            df=True,
        )

        data["date"] = pd.to_datetime(data["date"])

        # 计算过去每天的is_high状态
        _past_is_high_list = []

        # 遍历过去2天
        for i in range(-check_days, 0):
            # 数据切片，每次60天，不包含最后一天
            valid_data = data.iloc[:i][-high_lookback:]
            current_day_price = valid_data["close"].iloc[-1]

            # 计算当天的接近高点状态
            day_max_high = valid_data["high"].max()
            day_close_to_high = current_day_price >= (day_max_high * high_proximity)

            # 当天的is_high
            day_is_high = day_close_to_high
            _past_is_high_list.append(day_is_high)

        # 当前天的指标（最后一天）
        current_data = data[-high_lookback:]
        current_price = current_data["close"].iloc[-1]
        max_high = current_data["high"].max()
        close_to_high = current_price >= (max_high * high_proximity)

        # 将当前天加入列表，
        _past_is_high_list.append(close_to_high)

        # 新的is_high只要有一天为True，则为True
        _is_high = any(_past_is_high_list)

        return _is_high, _past_is_high_list

    cur_date_str = str(context.current_dt.date())
    if g.history_defense_date_list and cur_date_str <= g.history_defense_date_list[-1]:
        if cur_date_str in g.history_defense_date_list:
            g.defense_signal = True
            log.info("[防御] 组20防御: True, 处于历史触发范围内")
        else:
            g.defense_signal = False
            log.info("[防御] 触发防御: False, 未处于历史触发范围内")
    else:
        if g.defense_signal:
            sorted_ma_data, result = get_market_breadth(20)
            up_ratio = result.iloc[-3:]["up_ratio"].mean()
            avg_score = sorted_ma_data["组1"]
            defense_in_top = any(
                [ind in sorted_ma_data.index[:3] for ind in g.industries]
            )
            bank_exit_signal = not defense_in_top
            g.defense_signal = not bank_exit_signal
            log.info(
                f"[防御] 组20防御: {g.defense_signal} "
                f"组1宽度:{avg_score:.1f} "
                f"涨跌比:{up_ratio:.2f} "
                f"组20防御次数:{sum(g.cnt_bank_signal)} "
                f"top宽度:{sorted_ma_data.index[:5].tolist()}"
            )
        else:
            is_high, past_is_high_list = calculate_trend_indicators()
            if is_high:
                sorted_ma_data, result = get_market_breadth(20)
                defense_in_top = any(
                    [ind in sorted_ma_data.index[:2] for ind in g.industries]
                )
                avg_score = sorted_ma_data[
                    [ind not in g.industries for ind in sorted_ma_data.index]
                ].mean()
                above_average = avg_score < 60
                up_ratio = result.iloc[-3:]["up_ratio"].mean()
                above_ratio = up_ratio < 0.5
                is_bank_defense = defense_in_top and above_average and above_ratio
                g.defense_signal = is_bank_defense
                if is_bank_defense:
                    g.cnt_bank_signal.append(is_bank_defense)
                log.info(
                    f"[防御] 组20防御: {is_bank_defense} "
                    f"高位:{is_high}{past_is_high_list} "
                    f"组1宽度:{avg_score:.1f} "
                    f"涨跌比:{up_ratio:.2f} "
                    f"top宽度:{sorted_ma_data.index[:5].tolist()} "
                )
            else:
                g.defense_signal = False
                log.info(f"[防御] 触发防御: {g.defense_signal} 高位:{is_high}{past_is_high_list}")

    # 检测到需要防御进行空仓, 只空仓小市值的票
    now_time = context.current_dt
    if g.defense_signal:
        for stock in g.strategy_holdings[1][:]:
            current_data = get_price(
                stock,
                end_date=now_time,
                frequency="1m",
                fields=["close", "high_limit"],
                skip_paused=False,
                fq="pre",
                count=1,
                panel=False,
                fill_paused=True,
            )
            # 已涨停不清仓
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                close_position(context, stock)


def capital_balance_2(context):
    """资金已经完全隔离进入4个独立子账户，无需再做动态转移"""
    pass


def short_by_market_cap(context, stock_list):
    short_q = (
        query(valuation.code, valuation.market_cap)
        .filter(
            valuation.code.in_(stock_list),
            valuation.day == context.previous_date,
        )
        .order_by(valuation.market_cap.asc())
    )
    short_df = get_fundamentals(short_q)
    short_list = short_df["code"].unique().tolist()
    return short_list


""" ====================== 执行入口, 定时任务下发 ====================== """


def after_code_changed(context):
    unschedule_all()

    if g.portfolio_value_proportion[0] > 0:
        run_daily(prepare_small_cap_strategy, "9:05")
        if g.check_defense and g.defense_signal is None:
            check_defense_trigger(context)
        if g.DBL_control:
            run_daily(check_macd_divergence, "9:31")
        run_weekly(strategy_1_sell, 2, "09:40")
        run_weekly(strategy_1_buy, 2, "09:45")
        run_daily(sell_small_cap_stocks, time="10:00")
        # ATR止损价日常更新
        if g.enable_atr_stop_loss:
            run_daily(update_atr_stop_prices, "10:30")
            run_daily(update_atr_stop_prices, "14:00")
        if g.huanshou_check:
            run_daily(check_small_cap_turnover, "10:30")
        run_daily(check_small_cap_limit_up, "14:00")
        if g.check_defense:
            run_daily(check_defense_trigger, "14:50")
        run_daily(close_account, "14:50")

    # 策略2 ETF反弹策略
    if g.strategy_ETF_2000_proportion > 0:
        run_daily(capital_balance_2, "14:45")
        run_daily(strategy_2_sell, "14:49")
        run_daily(strategy_2_buy, "14:50")

# 策略3 五福闹新春 v3.5（与五福35.py 相同）
    if g.portfolio_value_proportion[2] > 0:
        if "morning_routine" not in globals() or "afternoon_routine" not in globals():
            log.error("【五福35】缺少 morning_routine/afternoon_routine，请保留文件头部五福内嵌段。")
        else:
            log.set_level("system", "error")
            log.set_level("strategy", "info")
            run_daily(morning_routine, time="09:00")
            # 【修改点】：不再区分纯净模式，强制在 13:10 执行
            run_daily(afternoon_routine, time="13:10")
            run_daily(reset_daily_flags, time="15:10")
            run_daily(minute_level_stop_loss, time="every_bar")
            run_daily(minute_level_pct_stop_loss, time="every_bar")

    # 策略4 白马策略
    if g.portfolio_value_proportion[3] > 0:
        run_monthly(prepare_blue_chip_before_open, 1, time="9:30")
        run_monthly(adjust_blue_chip_position, 1, time="10:40")

    run_daily(make_record, "15:01")
    run_daily(print_summary, "15:02")

