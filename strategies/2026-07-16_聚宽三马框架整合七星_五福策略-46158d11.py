# Clone from JoinQuant
# postId: 46158d1180355b9fd56df5771e0494b3
# backtestId: 1215f1ad470a0ce61b2cabe776ee0f7b
# title: 聚宽三马框架整合七星+五福策略

# 克隆自聚宽文章：https://www.joinquant.com/post/70738
# 标题：三马105-五福5.1v3-修复版-11年收益659倍回撤14%
# 作者：rbq2025

# 克隆自聚宽文章：https://www.joinquant.com/post/71733
# 标题：五福5.1v3-三状态V2版-11年484倍回撤20.5
# 作者：rbq2025

# 克隆自聚宽文章：https://www.joinquant.com/post/71413
# 标题：【五福5.1v3】五福闹新春-拟合ETF池最严厉的父亲
# 作者：烟花三月ETF

# 克隆自聚宽文章：https://www.joinquant.com/post/63661
# 标题：三马v10.2 测试框架 - 纯小市值v3（仅1/4月指数条件空仓版）
# 作者：Cibo

# 克隆自聚宽文章：https://www.joinquant.com/post/67039
# 标题：三马持续优化版 - v10.5
# 作者：Charlessssss

# 克隆自聚宽文章：https://www.joinquant.com/post/63661
# 原作者：Cibo
# 当前作者：Charlessssss
#
# 集成一致性指标版本 - 基于v10.5 缓存加速版
# 新增功能：将微盘股一致性指标（蒋氏一致性）集成到小市值策略风控体系中
# 新增功能：五福5.1v3策略缓存加速（减少重复数据获取和计算）
# 来源策略：
#   - https://www.joinquant.com/post/47349 - 韶华研究之十九，一致性用在微盘控制回撤
#   - https://www.joinquant.com/post/66998 - 三马优化版 v10.4缓存加速版

"""
三驾马车优化版 v10.5 + 一致性风控集成 + 五福5.1v3缓存加速

策略组合：
- 策略1：小市值策略 + 一致性风控
- 策略2：ETF反弹策略 (仅适用于2023.9月后)
- 策略3：《五福5.1v3》五福闹新春（与五福5.1.py 同源，聚宽 69702）
- 策略4：白马攻防 v2.0

v10.5 更新：
- 新增：五福5.1v3策略缓存加速
  - 批量预加载所有ETF历史数据（250天）
  - RSRS Beta值缓存机制（每日只需计算一次）
  - 五重过滤流程优化（按计算复杂度排序）
- 优化：五福5.1v3 ETF池保持原有配置
  - 多样性市场：上证180、德国DAX、纳指、日经225
  - 大宗商品：自然资源、黄金、原油LOF、豆粕期货、国债
  - 科技成长：创业板、科创100、半导体、金融科技、港股科技、新能源车
  - 蓝筹高股息：港股红利、上证180

v10.4 更新：成本保护止损
- 盈利>=15%：止损线上移到成本价(0%)，锁定本金
- 盈利>=30%：止损线上移至+10%，保护部分利润

一致性风控功能：
- 基于微盘股（最小5%市值）的市场一致性指标
- 使用120日布林带动态计算一致性阈值
- 牛熊市场自动切换：牛市关闭一致性检查，熊市开启
- 触发条件：大跌+高一致性 → 清仓；大涨+低一致性 → 满仓
"""
import datetime
import math
import prettytable
import numpy as np
import pandas as pd
from datetime import timedelta
from jqdata import *
from jqfactor import *
from prettytable import PrettyTable



def initialize(context):
    set_params(context)
    set_backtest(context)
    setup_wufu35_globals()  # v5.1新增：初始化五福5.1v3策略参数
    setup_qixing_globals()  # 七星策略初始化（策略2）
    set_strategy_params(context)
    if g.portfolio_value_proportion[2] > 0 and not (
        g.portfolio_value_proportion == [0, 0, 1, 0]
    ):
        init_range_bound_status(context)
    # 七星策略首次运行震荡期状态初始化
    if g.portfolio_value_proportion[1] > 0:
        qixing_init_range_bound_status(context)
    log.set_level("order", "error")


# 基础参数设置
def set_params(context):
    """
    资金分配比例：[小市值, 七星策略, 五福5.1v3, 白马攻防]
    注意：策略2已替换为七星策略（基于60倍七星高照+高斯+拉普拉斯）
    """
    # g.portfolio_value_proportion = [0.35, 0.1, 0.35, 0.2]  # 小市值/七星/五福5.1v3/白马攻防 (实盘)
    # g.portfolio_value_proportion = [0.4, 0.2, 0.4, 0]  # 小市值/七星/五福5.1v3 (实盘/短回测)
    g.portfolio_value_proportion = [0, 0.5, 0.5, 0]  # 七星/五福5.1v3 (用于长回测)
    # g.portfolio_value_proportion = [0, 0, 1, 0]  # 纯五福5.1v3模式（与原版五福策略一致）
    # g.portfolio_value_proportion = [0.35, 0, 0.35, 0.3]  # 小市值/五福5.1v3/白马 (用于长回测)
    # g.portfolio_value_proportion = [1, 0, 0, 0]  # 纯小市值模式（仅运行策略1）

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
        if order_obj and order_obj.filled > 0:
            # 真实回款 = 下单后增加的物理资金（聚宽自动处理手续费）
            cash_after = context.portfolio.available_cash
            real_deal_money = cash_after - cash_before
            
            # 保底（防止聚宽底层结算时延）
            if real_deal_money <= 0:
                real_deal_money = order_obj.price * order_obj.filled

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
                    
            log.info(f"💰[策略{strategy_id} 卖出] {format_stock_code(security)} 回笼资金: {real_deal_money:.2f}")
        return order_obj

    # 【买入操作】
    if delta_value > 0:
        # 防护壁垒：最多只能用本策略钱包里的钱！
        available_cash = g.sub_account[strategy_id]['cash']
        buy_value = min(delta_value, available_cash)

        if buy_value < getattr(g, "min_money", 10):
            return None

        # 使用order_target_value让聚宽自动处理滑点和手续费
        cash_before = context.portfolio.available_cash
        
        order_obj = order_target_value(security, buy_value)
        if order_obj and order_obj.filled > 0:
            cash_after = context.portfolio.available_cash
            real_cost_money = cash_before - cash_after
            
            # 如果聚宽未返回实际扣款，使用目标价值作为近似
            if real_cost_money <= 0:
                real_cost_money = buy_value
                
            # 扣除账户现金（聚宽已自动处理滑点与手续费）
            g.sub_account[strategy_id]['cash'] -= real_cost_money
            
            # 登记策略归属
            if security not in g.strategy_holdings[strategy_id]:
                g.strategy_holdings[strategy_id].append(security)
            g.stock_strategy[security] = strategy_id
            
            log.info(f"🛒[策略{strategy_id} 买入] {format_stock_code(security)} 扣费资金: {real_cost_money:.2f}")
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


def smart_order_target_value(security, target_value, context, exit_reason='午盘清仓'):
    """专门供给策略3 (五福5.1v3) 调用的接口"""
    current_data = get_current_data()
    security_name = get_security_name(security)

    # ========== 1. 买入初步资金检查（仅对买入操作） ==========
    if target_value > 0:
        available_cash = context.portfolio.available_cash
        if target_value > available_cash:
            target_value = available_cash
        if target_value < g.min_money:
            log.info(f"{security} {security_name}: 目标金额{target_value:.2f}小于最小交易额{g.min_money}，跳过")
            return False

    # ========== 2. 通用交易限制 ==========
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

    # ========== 3. 买入时使用预估成交价（包含佣金+滑点）计算股数 ==========
    # 佣金和滑点费率（买入方向）
    buy_commission_rate = 0.0001   # 买入佣金
    slippage_rate = 0.0001         # 滑点（价格相关滑点）
    estimated_price = current_price * (1 + buy_commission_rate + slippage_rate)
    
    if target_value > 0:
        # 用预估价格计算可买股数，确保实际花费不超可用现金
        target_amount = int(target_value / estimated_price)
        target_amount = (target_amount // 100) * 100
        if target_amount <= 0 and target_value > 0:
            target_amount = 100
        # 二次校验：用实时可用现金和当前价格严格限制（兜底）
        max_shares = int(context.portfolio.available_cash / current_price)
        max_shares = (max_shares // 100) * 100
        if max_shares < target_amount:
            log.info(f"{security} {security_name}: 现金可买{max_shares}股，原计划{target_amount}股，已调低")
            target_amount = max_shares
        if target_amount <= 0:
            log.info(f"{security} {security_name}: 现金不足买100股，跳过")
            return False
    else:
        # 卖出时不需要考虑资金，直接按目标数量0计算
        target_amount = 0

    # ========== 4. 获取当前持仓 ==========
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price

    # 小额交易过滤
    if 0 < trade_value < g.min_money:
        log.info(f"{security} {security_name}: 交易金额{trade_value:.2f}小于最小交易额{g.min_money}，跳过")
        return False

    # 卖出时检查可卖股数
    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {security_name}: 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)

    avg_cost_before = 0.0
    if current_position and getattr(current_position, 'avg_cost', None):
        try:
            avg_cost_before = float(current_position.avg_cost)
        except Exception:
            avg_cost_before = 0.0

    # ========== 5. 执行下单 ==========
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
                log.info(f"📦 买入{security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f} (预估含成本价: {estimated_price:.3f})")
            else:
                regime_now = getattr(g, 'market_regime', '')
                regime_str = f"{regime_now}" if regime_now else "—"
                log.info(
                    f"📤 卖出{security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}，"
                    f"原因: {exit_reason}，市场状态: {regime_str}"
                )
                pos_after = context.portfolio.positions.get(security)
                amt_after = pos_after.total_amount if pos_after else 0
                if amt_after <= 0:
                    record_etf_roundtrip_on_sell(
                        context, security, float(abs(amount_diff)),
                        avg_cost_before, float(current_price), exit_reason
                    )
                if security in g.strategy_holdings[3]:
                    g.strategy_holdings[3].remove(security)
                if security in g.stock_strategy:
                    del g.stock_strategy[security]
            return True
        else:
            log.warning(f"下单失败: {security} {security_name}，数量: {amount_diff}")
            return False
    return False


def setup_wufu35_globals():
    """与 五福5.1v3.py initialize 中 g 变量段一致（不含 set_option / run_daily）。"""
    # ==================== ETF池定义 ====================
    # 全球/海外ETF池（含大宗商品和海外市场ETF）
    g.global_etf_pool = [
#大宗商品ETF：
        '518880.XSHG',  # (黄金ETF) [ETF]-日均成交额：51.35亿元-上市日期：2013-07-29
        '501018.XSHG',  # (南方原油) [LOF]-日均成交额：24.38亿元-上市日期：2016-06-28
        '161226.XSHE',  # (国投白银LOF) [LOF]-日均成交额：5.44亿元-上市日期：2015-08-17
        '159985.XSHE',  # (豆粕ETF华夏) [ETF]-日均成交额：4.63亿元-上市日期：2019-12-05
        '159980.XSHE',  # (有色ETF大成) [ETF]-日均成交额：3.84亿元-上市日期：2019-12-24
#海外ETF：       
        '513310.XSHG',  # (中韩芯片) [ETF]-日均成交额：59.37亿元-上市日期：2022-12-22
        '159518.XSHE',  # (标普油气ETF嘉实) [ETF]-日均成交额：27.93亿元-上市日期：2023-11-15
        '159509.XSHE',  # (纳指科技ETF景顺) [ETF]-日均成交额：7.24亿元-上市日期：2023-08-08
        '513100.XSHG',  # (纳指ETF) [ETF]-日均成交额：5.02亿元-上市日期：2013-05-15
        '513520.XSHG',  # (日经ETF) [ETF]-日均成交额：3.72亿元-上市日期：2019-06-25
        '513500.XSHG',  # (标普500) [ETF]-日均成交额：2.89亿元-上市日期：2014-01-15
        '159502.XSHE',  # (标普生物科技ETF嘉实) [ETF]-日均成交额：1.80亿元-上市日期：2024-01-10
        '513400.XSHG',  # (道琼斯) [ETF]-日均成交额：1.70亿元-上市日期：2024-02-02
        '513030.XSHG',  # (德国ETF) [ETF]-日均成交额：0.95亿元-上市日期：2014-09-05
        '513290.XSHG',  # (纳指生物) [ETF]-日均成交额：0.78亿元-上市日期：2022-08-29
        '520830.XSHG',  # (沙特ETF) [ETF]-日均成交额：0.62亿元-上市日期：2024-07-16
        '159529.XSHE',  # (标普消费ETF景顺) [ETF]-日均成交额：0.50亿元-上市日期：2024-02-02
        '513400.XSHG',  # (道琼斯ETF) [ETF]-日均成交额：0.2亿元-上市日期：2024-02-29
        '164824.XSHE',  # (印度基金LOF) [ETF]-日均成交额：0.50亿元-上市日期：2018-08-31
        '513850.XSHG',  # 美国50ETF
        "513080.XSHG",  # 法国ETF
        "513730.XSHG",  # 东南亚ETF
        "511380.XSHG",  # 可转债ETF
        "511010.XSHG",  # 国债ETF
        "511220.XSHG",  # 城投债E
]
    # 中国ETF池（含港股、指数、行业ETF）
    g.china_etf_pool = [
#港股ETF：
        '513090.XSHG',  # (香港证券) [ETF]-日均成交额：54.24亿元-上市日期：2020-03-26
        '513120.XSHG',  # (HK创新药) [ETF]-日均成交额：52.34亿元-上市日期：2022-07-12
        '513180.XSHG',  # (恒指科技) [ETF]-日均成交额：36.66亿元-上市日期：2021-05-25
        '513330.XSHG',  # (恒生互联) [ETF]-日均成交额：20.45亿元-上市日期：2021-02-08
        '513750.XSHG',  # (港股非银) [ETF]-日均成交额：9.55亿元-上市日期：2023-11-27
        '159892.XSHE',  # (恒生医药ETF华夏) [ETF]-日均成交额：7.90亿元-上市日期：2021-10-19
        '513190.XSHG',  # (H股金融) [ETF]-日均成交额：3.74亿元-上市日期：2023-10-11
        '159605.XSHE',  # (中概互联ETF广发) [ETF]-日均成交额：3.19亿元-上市日期：2021-12-02
        '513630.XSHG',  # (香港红利) [ETF]-日均成交额：2.84亿元-上市日期：2023-12-08
        '159323.XSHE',  # (港股通汽车ETF华夏) [ETF]-日均成交额：1.98亿元-上市日期：2025-01-08
        '510900.XSHG',  # (恒生中国) [ETF]-日均成交额：1.46亿元-上市日期：2012-10-22
        '513920.XSHG',  # (央企40) [ETF]-日均成交额：1.38亿元-上市日期：2024-01-05
        '513970.XSHG',  # (恒生消费) [ETF]-日均成交额：0.82亿元-上市日期：2023-04-21
#指数ETF：        
        '511380.XSHG',  # (转债ETF) [ETF]-日均成交额：115.92亿元-上市日期：2020-04-07
        '512050.XSHG',  # (A500E) [ETF]-日均成交额：48.05亿元-上市日期：2024-11-15
        '510500.XSHG',  # (500ETF) [ETF]-日均成交额：45.45亿元-上市日期：2013-03-15
        '159915.XSHE',  # (创业板ETF易方达) [ETF]-日均成交额：43.55亿元-上市日期：2011-12-09
        '510300.XSHG',  # (300ETF) [ETF]-日均成交额：34.60亿元-上市日期：2012-05-28
        '512100.XSHG',  # (1000ETF) [ETF]-日均成交额：25.26亿元-上市日期：2016-11-04
        '159949.XSHE',  # (创业板50ETF华安) [ETF]-日均成交额：16.52亿元-上市日期：2016-07-22
        '588080.XSHG',  # (科创板50) [ETF]-日均成交额：13.32亿元-上市日期：2020-11-16
        '159967.XSHE',  # (创业板成长ETF华夏) [ETF]-日均成交额：5.29亿元-上市日期：2019-07-15
        '588220.XSHG',  # (科创100F) [ETF]-日均成交额：5.01亿元-上市日期：2023-09-15
        '563300.XSHG',  # (中证2000) [ETF]-日均成交额：4.13亿元-上市日期：2023-09-14
        '510760.XSHG',  # (上证ETF) [ETF]-日均成交额：1.45亿元-上市日期：2020-09-09
#行业ETF：
        '588200.XSHG',  # (科创芯片) [ETF]-日均成交额：28.07亿元-上市日期：2022-10-26
        '515880.XSHG',  # (通信ETF) [ETF]-日均成交额：22.39亿元-上市日期：2019-09-06
        '159981.XSHE',  # (能源化工ETF建信) [ETF]-日均成交额：21.63亿元-上市日期：2020-01-17
        '512880.XSHG',  # (证券ETF) [ETF]-日均成交额：16.21亿元-上市日期：2016-08-08
        '513350.XSHG',  # (油气ETF) [ETF]-日均成交额：15.66亿元-上市日期：2023-11-28
        '159326.XSHE',  # (电网设备ETF华夏) [ETF]-日均成交额：14.86亿元-上市日期：2024-09-09
        '159516.XSHE',  # (半导体设备ETF国泰) [ETF]-日均成交额：14.23亿元-上市日期：2023-07-27
        '159206.XSHE',  # (卫星ETF永赢) [ETF]-日均成交额：13.87亿元-上市日期：2025-03-14
        '512480.XSHG',  # (半导体) [ETF]-日均成交额：13.07亿元-上市日期：2019-06-12
        '159363.XSHE',  # (创业板人工智能ETF华宝) [ETF]-日均成交额：10.50亿元-上市日期：2024-12-16
        '159870.XSHE',  # (化工ETF鹏华) [ETF]-日均成交额：10.03亿元-上市日期：2021-03-03
        '512400.XSHG',  # (有色ETF) [ETF]-日均成交额：9.97亿元-上市日期：2017-09-01
        '159755.XSHE',  # (电池ETF广发) [ETF]-日均成交额：8.58亿元-上市日期：2021-06-24
        '588170.XSHG',  # (科创半导) [ETF]-日均成交额：7.74亿元-上市日期：2025-04-08
        '159992.XSHE',  # (创新药ETF银华) [ETF]-日均成交额：7.59亿元-上市日期：2020-04-10
        '159995.XSHE',  # (芯片ETF华夏) [ETF]-日均成交额：7.51亿元-上市日期：2020-02-10
        '512890.XSHG',  # (红利低波) [ETF]-日均成交额：6.79亿元-上市日期：2019-01-18
        '515220.XSHG',  # (煤炭ETF) [ETF]-日均成交额：6.44亿元-上市日期：2020-03-02
        '159566.XSHE',  # (储能电池ETF易方达) [ETF]-日均成交额：6.31亿元-上市日期：2024-02-08
        '159819.XSHE',  # (人工智能ETF易方达) [ETF]-日均成交额：6.26亿元-上市日期：2020-09-23
        '512800.XSHG',  # (银行ETF) [ETF]-日均成交额：6.13亿元-上市日期：2017-08-03
        '512690.XSHG',  # (酒ETF) [ETF]-日均成交额：5.99亿元-上市日期：2019-05-06
        '515050.XSHG',  # (5GETF) [ETF]-日均成交额：5.93亿元-上市日期：2019-10-16
        '562500.XSHG',  # (机器人) [ETF]-日均成交额：5.83亿元-上市日期：2021-12-29
        '512170.XSHG',  # (医疗ETF) [ETF]-日均成交额：5.63亿元-上市日期：2019-06-17
        '517520.XSHG',  # (黄金股) [ETF]-日均成交额：5.01亿元-上市日期：2023-11-01
        '159869.XSHE',  # (游戏ETF华夏) [ETF]-日均成交额：4.77亿元-上市日期：2021-03-05
        '512070.XSHG',  # (证券保险) [ETF]-日均成交额：4.61亿元-上市日期：2014-07-18
        '159611.XSHE',  # (电力ETF广发) [ETF]-日均成交额：4.42亿元-上市日期：2022-01-07
        '562800.XSHG',  # (稀有金属) [ETF]-日均成交额：4.39亿元-上市日期：2021-09-27
        '515120.XSHG',  # (创新药) [ETF]-日均成交额：4.34亿元-上市日期：2021-01-04
        '512010.XSHG',  # (医药ETF) [ETF]-日均成交额：4.27亿元-上市日期：2013-10-28
        '510880.XSHG',  # (红利ETF) [ETF]-日均成交额：3.97亿元-上市日期：2007-01-18
        '515790.XSHG',  # (光伏ETF) [ETF]-日均成交额：3.87亿元-上市日期：2020-12-18
        '515980.XSHG',  # (人工智能) [ETF]-日均成交额：3.78亿元-上市日期：2020-02-10
        '512660.XSHG',  # (军工ETF) [ETF]-日均成交额：3.75亿元-上市日期：2016-08-08
        '159928.XSHE',  # (消费ETF汇添富) [ETF]-日均成交额：3.66亿元-上市日期：2013-09-16
        '512710.XSHG',  # (军工龙头) [ETF]-日均成交额：3.60亿元-上市日期：2019-08-26
        '560860.XSHG',  # (工业有色) [ETF]-日均成交额：3.57亿元-上市日期：2023-03-13
        '515030.XSHG',  # (新汽车) [ETF]-日均成交额：3.33亿元-上市日期：2020-03-04
        '159766.XSHE',  # (旅游ETF富国) [ETF]-日均成交额：3.30亿元-上市日期：2021-07-23
        '159218.XSHE',  # (卫星ETF招商) [ETF]-日均成交额：3.21亿元-上市日期：2025-05-22
        '159852.XSHE',  # (软件ETF嘉实) [ETF]-日均成交额：3.19亿元-上市日期：2021-02-09
        '516160.XSHG',  # (新能源) [ETF]-日均成交额：3.07亿元-上市日期：2021-02-04
        '516150.XSHG',  # (稀土基金) [ETF]-日均成交额：3.03亿元-上市日期：2021-03-17
        '159227.XSHE',  # (航空航天ETF华夏) [ETF]-日均成交额：2.98亿元-上市日期：2025-05-16
        '159583.XSHE',  # (通信ETF富国) [ETF]-日均成交额：2.93亿元-上市日期：2024-07-08
        '588790.XSHG',  # (科创智能) [ETF]-日均成交额：2.62亿元-上市日期：2025-01-09
        '159865.XSHE',  # (养殖ETF国泰) [ETF]-日均成交额：2.44亿元-上市日期：2021-03-08
        '512980.XSHG',  # (传媒ETF) [ETF]-日均成交额：2.43亿元-上市日期：2018-01-19
        '159851.XSHE',  # (金融科技ETF华宝) [ETF]-日均成交额：2.27亿元-上市日期：2021-03-19
        '561360.XSHG',  # (石油ETF) [ETF]-日均成交额：2.04亿元-上市日期：2023-10-31
        '561980.XSHG',  # (芯片设备) [ETF]-日均成交额：2.01亿元-上市日期：2023-09-01
        '562590.XSHG',  # (半导材料) [ETF]-日均成交额：1.76亿元-上市日期：2023-10-18
        '512200.XSHG',  # (地产ETF) [ETF]-日均成交额：1.71亿元-上市日期：2017-09-25
        '159732.XSHE',  # (消费电子ETF华夏) [ETF]-日均成交额：1.62亿元-上市日期：2021-08-23
        '159667.XSHE',  # (工业母机ETF国泰) [ETF]-日均成交额：1.58亿元-上市日期：2022-10-26
        '516510.XSHG',  # (云计算) [ETF]-日均成交额：1.49亿元-上市日期：2021-04-07
        '159840.XSHE',  # (锂电池ETF工银) [ETF]-日均成交额：1.42亿元-上市日期：2021-08-20
        '159998.XSHE',  # (计算机ETF天弘) [ETF]-日均成交额：1.30亿元-上市日期：2020-04-13
        '159825.XSHE',  # (农业ETF富国) [ETF]-日均成交额：1.15亿元-上市日期：2020-12-29
        '512670.XSHG',  # (国防ETF) [ETF]-日均成交额：1.12亿元-上市日期：2019-08-01
        '159883.XSHE',  # (医疗器械ETF永赢) [ETF]-日均成交额：1.05亿元-上市日期：2021-04-30
        '515210.XSHG',  # (钢铁ETF) [ETF]-日均成交额：1.01亿元-上市日期：2020-03-02
        '515400.XSHG',  # (大数据) [ETF]-日均成交额：0.94亿元-上市日期：2021-01-20
        '159256.XSHE',  # (创业板软件ETF华夏) [ETF]-日均成交额：0.83亿元-上市日期：2025-08-04
        '561330.XSHG',  # (矿业ETF) [ETF]-日均成交额：0.83亿元-上市日期：2022-11-01
        '515170.XSHG',  # (食品饮料) [ETF]-日均成交额：0.67亿元-上市日期：2021-01-13
        '159638.XSHE',  # (高端装备ETF嘉实) [ETF]-日均成交额：0.56亿元-上市日期：2022-08-12
        '516520.XSHG',  # (智能驾驶) [ETF]-日均成交额：0.47亿元-上市日期：2021-03-01
        '513360.XSHG',  # (教育ETF) [ETF]-日均成交额：0.43亿元-上市日期：2021-06-17
        '516190.XSHG',  # (文娱ETF) [ETF]-日均成交额：0.18亿元-上市日期：2021-09-17
    ]
    # 固定ETF池 = 全球池 + 中国池（正常期使用）
    g.fixed_etf_pool = g.global_etf_pool + g.china_etf_pool
    
    g.avg_etf_money_threshold = None  # v5.1原版：ETF流动性阈值
    g.global_liquidity_threshold_divisor = 20000  # v5.1原版：全市场流动性分母
    g.filtered_fixed_pool = []
    g.dynamic_etf_pool = []
    g.merged_etf_pool = []
    g.ranked_etfs_result = []
    g.filtered_global_pool = []  # v5.1原版：走弱期过滤后的全球池
    g.positions = {}
    g.target_etfs_list = []
    g.etf_names_dict = {}
    g.cache_date = None
    g.yesterday_close_cache = {}
    g.holdings_num = 1
    g.defensive_etf = "511880.XSHG"
    g.min_money = 10
    g.lookback_days = 25
    g.min_score_threshold = 0
    g.max_score_threshold = 5
    g.score_threshold_ratio = 0.9
    
    # v5.1 新增：三态市场判断相关参数
    g.market_regime = '震荡期'
    g.is_a_share_weak = False
    g.regime_prev_day = None           # 上一交易日早盘判定结果（用于切换/反复跳跃日志）
    g.regime_prev_prev_day = None      # 上上交易日早盘判定结果
    g.regime_flip_flop_count = 0       # 「隔日跳回」A→B→A 累计次数（整个回测）
    g.regime_switch_confirm_days = 2
    g.regime_switch_pending_raw = None    # 待确认的指标状态
    g.regime_switch_pending_streak = 0    # 已连续多少个交易日指标均为 pending_raw
    g.regime_last_change_date = None      # 最近一次生效状态切换日
    g.normal_ma_lookback = 10          # 正常期广度：站上 MA10 的指数个数
    g.regime_ma20_lookback = 20        # 走弱判定用的 MA20 周期（日）
    g.weak_period_ma_lookback = 10     # 保留变量名，与 normal_ma_lookback 一致
    # 六指数齐备时：below_ma20 计数 ≥ 此值 → 走弱期；above_ma10 计数 ≥ 此值 → 正常期（且未触发走弱）
    g.regime_weak_below_ma20_min = 4   # 默认 6 即「六指均跌破 MA20」
    g.regime_normal_above_ma10_min = 4
    
    # 震荡期高斯滤波（对齐五福5.1v3）
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002  # 绝对斜率 g1-g2 时的阈值（gaussian_use_relative_slope=False）
    # True：斜率改为 (g1-g2)/g2，与拉普拉斯相对斜率口径一致，便于低价标的公平比较；False：沿用原绝对差
    g.gaussian_use_relative_slope = True
    g.gaussian_min_slope_relative = 0.0013  # 相对斜率阈值（仅 gaussian_use_relative_slope=True 时参与比较）
    
    # 回测全周期：各状态累计交易日与当日净值复利因子（收盘 after_close 更新）
    g.regime_day_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_return_factors = {'正常期': 1.0, '震荡期': 1.0, '走弱期': 1.0}
    # 有上一日净值可比时：各状态下日收益为正/负/平的天数，及日收益率算术累加（不含首日）
    g.regime_win_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_loss_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_flat_counts = {'正常期': 0, '震荡期': 0, '走弱期': 0}
    g.regime_sum_pos_daily_ret = {'正常期': 0.0, '震荡期': 0.0, '走弱期': 0.0}
    g.regime_sum_neg_daily_ret = {'正常期': 0.0, '震荡期': 0.0, '走弱期': 0.0}
    g.prev_eod_portfolio_value = None
    
    # 【重要】禁用v3.5旧版震荡期模式，使用v5.1三态市场判断
    g.enable_range_bound_mode = False
    
    # v3.5 兼容属性（避免旧代码报错，实际不使用）
    g.current_filter = '震荡期'  # 默认值，不会被实际使用
    g.range_bound_start_date = None
    g.risk_state = '正常'
    
    # v5.1 新增：持仓数动态调整
    g.holdings_num_normal = 1
    g.holdings_num_oscillation = 1
    g.holdings_num_weak = 1
    
    # v5.1 新增：短期动量
    g.use_short_momentum_period = False
    g.short_momentum_lookback = 21
    g.short_momentum_min_score = 0
    g.short_momentum_max_score = 6
    g.pending_sm3up_sell_followups = []
    g.last_metrics_by_etf_code = {}
    g.trade_entry_open = {}
    g.trade_roundtrip_history = []
    # 卖出原因分类统计（P0-1）：数据缺失 / 过滤失败 / 排名落后
    g.exit_reason_stats = {
        'total': 0,
        'by_bucket': {'missing_data': 0, 'filter_fail': 0, 'rank_lag': 0, 'other': 0},
        'by_regime': {},
        'by_detail': {},
    }
    
    # v5.1 新增：Whipsaw震荡收割相关
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
    g.range_short_momentum_max = 6.0
    g.enable_switch_hysteresis = False
    g.switch_buffer_normal = 0.10
    g.switch_buffer_range = 0.40
    g.enable_dual_positive_momentum = True
    g.dual_positive_only_in_range = True
    g.whipsaw_options_only_in_range = True
    g.log_whipsaw_filter_detail = True
    g.log_pool_update_details = False
    g.log_first_step_ranking = False
    
    # v5.1 新增：防频换增强
    g.normal_max_days_not_rank1 = 5
    g.normal_max_days_not_topk = 5
    g.oscillation_max_days_not_topk = 5
    g.normal_not_rank1_streak = 0
    g.normal_streak_hold_code = None
    g.normal_not_topk_streaks = {}
    g.oscillation_anti_churn_enabled = True
    g.weak_anti_churn_enabled = True
    
    # v5.1 新增：组合回撤分级动作
    g.enable_drawdown_risk_actions = False  # 【已禁用】全局风控已关闭
    g.drawdown_threshold = 0.03  # v5.1新增：回撤预警阈值（3%）
    g.max_portfolio_value = 0  # v5.1新增：组合最高市值（用于回撤计算）
    g.drawdown_records = []  # v5.1原版：回撤记录
    g.dd_half_position_threshold = 0.10
    g.dd_switch_defensive_threshold = 0.12
    g.dd_flat_threshold = 0.20
    g.dd_partial_close_keep_fraction = 0.50
    g.dd_action_cooldown_date = None
    g.dd_reset_peak_after_action = True
    g.dd_monitor_time = '10:31'
    g.dd_valuation_use_mtm_last_price = True
    
    # v5.1 新增：止损买回冷却
    g.enable_stop_loss_rebuy_cooldown = True
    g.stop_loss_rebuy_cooldown_trade_days = 2
    g.stop_loss_rebuy_cutoff_time = '13:10'
    g.stop_loss_rebuy_first_allowed_date = {}
    
    # v5.1 原版：固定止损和百分比止损
    g.use_fixed_stop_loss = True
    g.fixedStopLossThreshold = 0.92
    g.use_pct_stop_loss = False
    g.pct_stop_loss_threshold = 0.95
    
    # v5.1 新增：动量上限软处理
    g.enable_momentum_soft_cap = False
    g.momentum_soft_cap_penalty = 0.05
    g.momentum_soft_cap_normal_only = True
    # 防御切换确认（默认关闭）：
    # 当日无排名结果且目标为防御ETF时，需要连续 N 个交易日信号成立才切换
    g.enable_defensive_switch_confirm = False
    g.defensive_switch_confirm_days = 2
    g.defensive_switch_pending_streak = 0
    g.defensive_switch_last_signal_date = None
    
    # v5.1 新增：日志开关
    g.log_market_status_details = False
    
    # v5.1 新增：量比缓冲带
    g.enable_volume_threshold_buffer = True
    g.volume_threshold_buffer = 0.1
    
    # v5.1 新增：MA过滤
    g.enable_ma_filter = True
    g.ma_lookback = 10
    g.ma_threshold = 1.0
    
    # v5.1 新增：拉普拉斯滤波
    g.enable_laplace_filter = True
    g.laplace_s_param = 0.05  # 拉普拉斯平滑参数
    g.laplace_min_slope = 0.002  # 拉普拉斯最小斜率
    
    # 【必需】ETF排序相关参数（v5.1原版）
    g.volume_lookback = 5  # v5.1原版：成交量回看天数
    g.enable_r2_filter = True  # 启用R²过滤
    g.r2_threshold = 0.4  # R²阈值
    g.enable_volume_check = True  # 启用成交量检查
    g.volume_threshold = 1.8  # v5.1原版：成交量比值阈值
    g.enable_loss_filter = True  # 启用短期风控过滤
    g.loss = 0.97  # v5.1原版：单日最大跌幅阈值（1-0.97=3%）
    g.enable_premium_filter = False  # v5.1原版：禁用溢价率过滤
    g.max_premium_rate = 30  # v5.1原版：最大溢价率（%）
    
    g.use_fixed_stop_loss = True
    g.fixedStopLossThreshold = 0.92
    g.use_pct_stop_loss = False
    g.pct_stop_loss_threshold = 0.95
    g.avg_etf_money_threshold = None
    g.global_liquidity_threshold_divisor = 20000
    g.filtered_global_pool = []


# ==================== 七星策略初始化（策略2） ====================
def setup_qixing_globals():
    """七星策略参数初始化（基于七星.py）"""
    # ---------- ETF池 ----------
    g.qixing_etf_pool_bak = [
        "518880.XSHG",   # 黄金ETF
        "159985.XSHE",   # 豆粕ETF
        "501018.XSHG",   # 南方原油
        "161226.XSHE",   # 白银LOF
        "513100.XSHG",   # 纳指ETF
        "159915.XSHE",   # 创业板ETF
        "511220.XSHG",   # 城投债ETF
    ]
    # 大ETF池
    g.qixing_etf_pool = [
        # 大宗商品ETF
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色ETF（跟踪有色金属板块）
        "159985.XSHE",  # 豆粕ETF（跟踪豆粕期货价格）
        "501018.XSHG",  # 南方原油（投资原油相关资产）
        '161226.XSHE',  # 白银LOF
        "159981.XSHE",  # 能源化工ETF
        # 国际ETF
        "513100.XSHG",  # 纳指ETF
        "159509.XSHE",  # 纳指科技ETF
        "513290.XSHG",  # 纳指生物ETF
        "513500.XSHG",  # 标普500ETF
        "159529.XSHE",  # 标普消费
        "513400.XSHG",  # 道琼斯ETF
        "513520.XSHG",  # 日经225ETF
        "513030.XSHG",  # 德国30ETF
        "513080.XSHG",  # 法国ETF
        "513310.XSHG",  # 中韩半导体ETF
        "513730.XSHG",  # 东南亚ETF
        # 香港ETF
        "159792.XSHE",  # 港股互联ETF
        "513130.XSHG",  # 恒生科技
        "513050.XSHG",  # 中概互联网ETF
        "159920.XSHE",  # 恒生ETF
        "513690.XSHG",  # 港股红利
        # 指数ETF
        "510300.XSHG",  # 沪深300ETF
        "510500.XSHG",  # 中证500ETF
        "510050.XSHG",  # 上证50ETF
        "510210.XSHG",  # 上证ETF
        "159915.XSHE",  # 创业板ETF
        "588080.XSHG",  # 科创50
        "512100.XSHG",  # 中证1000ETF
        "563360.XSHG",  # A500-ETF
        "563300.XSHG",  # 中证2000ETF
        # 风格ETF
        "512890.XSHG",  # 红利低波ETF
        "159967.XSHE",  # 创业板成长ETF
        "512040.XSHG",  # 价值ETF
        "159201.XSHE",  # 自由现金流ETF
        # 债券ETF
        "511380.XSHG",  # 可转债ETF
        "511010.XSHG",  # 国债ETF
        "511220.XSHG",  # 城投债ETF
    ]
    
    # ---------- 核心参数 ----------
    g.qixing_lookback_days = 25               # 动量计算周期
    g.qixing_holdings_num = 1                 # 候选数量
    g.qixing_defensive_etf = "511880.XSHG"    # 防御ETF（货币基金）
    g.qixing_min_money = 5000                 # 最小交易金额

    # ---------- 【新增】流动性过滤参数（20日日均成交额） ----------
    g.qixing_enable_liquidity_filter = True                      # 流动性过滤总开关
    g.qixing_liquidity_lookback_days = 20                        # 成交额回看周期（交易日）
    g.qixing_liquidity_threshold = 20000000                      # 日均成交额阈值（2000万元，单位：元）

    # ---------- 盈利保护参数 ----------
    g.qixing_enable_profit_protection = True                      # 盈利保护开关
    g.qixing_profit_protection_lookback = 1                       # 盈利保护回看周期（天）
    g.qixing_profit_protection_threshold = 0.05                   # 盈利保护回撤阈值（5%）
    g.qixing_profit_protection_check_times = ['11:00']            # 盈利保护检查时间点

    g.qixing_loss = 0.97                      # 近3日单日跌幅阈值（排除）

    g.qixing_min_score_threshold = 0          # 最低得分
    g.qixing_max_score_threshold = 100.0      # 最高得分

    # ---------- 成交量过滤 ----------
    g.qixing_enable_volume_check = True
    g.qixing_volume_lookback = 5
    g.qixing_volume_threshold = 2
    g.qixing_volume_return_limit = 1          # 年化收益>100%时启用放量过滤

    # ---------- 短期动量过滤 ----------
    g.qixing_use_short_momentum_filter = True
    g.qixing_short_lookback_days = 10
    g.qixing_short_momentum_threshold = 0.0

    # ---------- 溢价率过滤 ----------
    g.qixing_enable_premium_filter = True      # 是否启用溢价率过滤
    g.qixing_premium_threshold = 0.20          # 溢价率阈值（20%）

    # ---------- 运行时变量 ----------
    g.qixing_rankings_cache = {'date': None, 'data': None}   # 排名缓存

    # ---------- 震荡期参数 ----------
    g.qixing_enable_range_bound_mode = True      # 震荡期模式开关
    g.qixing_current_filter = '正常期'           # 当前滤波器：'正常期'=拉普拉斯, '震荡期'=高斯
    g.qixing_risk_state = '正常期'               # 风险状态
    g.qixing_lookback_high_low_days = 20         # 近N个交易日高低点回看
    g.qixing_risk_benchmark = '510300.XSHG'      # 风险基准ETF
    # 滤波器参数（正常期拉普拉斯，震荡期高斯）
    g.qixing_laplace_s_param = 0.05
    g.qixing_laplace_min_slope = 0.001
    g.qixing_gaussian_sigma = 1.2
    g.qixing_gaussian_min_slope = 0.002
    # 进入震荡期条件
    g.qixing_enable_bias_trigger = True          # 乖离率过大触发
    g.qixing_bias_threshold = 0.10               # 乖离率阈值（10%）
    g.qixing_ma_period = 20                      # 均线周期
    g.qixing_enable_rsi_trigger = True           # RSI超买回落触发
    g.qixing_rsi_overbought = 75
    g.qixing_rsi_pullback = 60
    g.qixing_previous_rsi = None
    g.qixing_enable_stop_loss_trigger = False    # 盈利保护触发止损信号开关
    g.qixing_stop_loss_triggered_today = False
    g.qixing_stop_loss_triggered_date = None
    # 退出震荡期条件
    g.qixing_enable_low_point_rise_trigger = True
    g.qixing_low_point_rise_threshold = 0.03     # 从低点上涨3%退出
    g.qixing_enable_stable_signal_trigger = True
    g.qixing_drawdown_recovery = 0.03            # 回撤收窄阈值
    g.qixing_max_range_bound_days = 15           # 最大震荡期天数
    g.qixing_stable_days = 0
    # 震荡期控制
    g.qixing_filter_switch_cooldown = 2          # 切换冷却期（交易日）
    g.qixing_last_switch_date = None
    g.qixing_range_bound_start_date = None
    g.qixing_range_bound_days_count = 0
    g.qixing_previous_drawdown = None


# ==================== 七星策略核心辅助函数 ====================
def qixing_check_liquidity(security, context, lookback=None, threshold=None):
    """
    检查ETF的日均成交额是否达标
    参数:
        security: ETF代码
        context: 上下文
        lookback: 回看天数，默认g.qixing_liquidity_lookback_days
        threshold: 日均成交额阈值，默认g.qixing_liquidity_threshold（单位：元）
    返回:
        bool: True表示流动性达标，False表示不达标（需过滤）
        avg_amount: 日均成交额（元），用于日志输出
    """
    # 若开关关闭，直接返回达标
    if not g.qixing_enable_liquidity_filter:
        return True, 0

    lookback = lookback or g.qixing_liquidity_lookback_days
    threshold = threshold or g.qixing_liquidity_threshold

    try:
        # 获取过去N个交易日的成交额数据（不含当日，无未来函数）
        hist = attribute_history(security, lookback, '1d', ['money'], skip_paused=True)
        # 数据不足（上市不满N天），直接判定不达标
        if hist.empty or len(hist) < lookback:
            log.debug(f"{security} {qixing_get_name(security)} 历史数据不足{lookback}天，流动性不达标")
            return False, 0
        
        # 计算日均成交额
        avg_amount = hist['money'].mean()
        # 低于阈值，判定不达标
        if avg_amount < threshold:
            return False, avg_amount
        # 达标
        return True, avg_amount

    except Exception as e:
        log.warning(f"{security} {qixing_get_name(security)} 流动性检查异常: {e}，判定为不达标")
        return False, 0


def qixing_profit_protection_check(context):
    """
    独立执行的盈利保护检查函数
    遍历所有持仓，若触发盈利保护则卖出
    """
    if not g.qixing_enable_profit_protection:
        log.debug("七星盈利保护模块已关闭，跳过检查")
        return

    log.info("========== 七星盈利保护独立检查开始 ==========")
    for sec in list(context.portfolio.positions.keys()):
        # 只处理ETF池中的标的和防御ETF
        if sec not in g.qixing_etf_pool and sec != g.qixing_defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if qixing_check_profit_protection(sec, context):
                if qixing_smart_order_target_value(sec, 0, context):
                    log.info(f"🛡️ 七星盈利保护卖出（独立检查）：{sec} {qixing_get_name(sec)}")
                    # 触发止损信号，用于震荡期进入判断
                    if getattr(g, 'qixing_enable_stop_loss_trigger', False):
                        g.qixing_stop_loss_triggered_today = True
                        g.qixing_stop_loss_triggered_date = context.current_dt.date()
                        log.info("【七星盈利保护触发】记录止损信号，将在震荡期检查时使用")
    log.info("========== 七星盈利保护独立检查完成 ==========")


def qixing_check_profit_protection(security, context, lookback=None, threshold=None):
    """
    检查是否触发盈利保护（从最近N日最高点回撤超过阈值）
    参数:
        security: ETF代码
        context: 上下文
        lookback: 回看天数，默认g.qixing_profit_protection_lookback
        threshold: 回撤阈值，默认g.qixing_profit_protection_threshold
    返回:
        bool: True表示应触发盈利保护（卖出/排除），False表示安全
    """
    # 若开关关闭，直接返回安全
    if not g.qixing_enable_profit_protection:
        return False

    lookback = lookback or g.qixing_profit_protection_lookback
    threshold = threshold or g.qixing_profit_protection_threshold

    # 获取最近N日的最高价（不包括当天）
    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback:
        log.debug(f"{security} {qixing_get_name(security)} 历史数据不足{lookback}天，无法检查盈利保护")
        return False

    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price

    if current_price <= max_high * (1 - threshold):
        log.info(f"🔻 {security} {qixing_get_name(security)} 触发盈利保护：当前价{current_price:.3f}，最近{lookback}日最高{max_high:.3f}，回撤{(1 - current_price/max_high)*100:.2f}% > {threshold*100:.0f}%")
        return True
    else:
        return False


def qixing_get_premium_rate(code, date, max_back_days=5):
    """
    获取指定日期的溢价率，若当天无净值则向前搜索最多max_back_days个交易日
    参数:
        code: 基金代码
        date: 日期，datetime.date 对象
        max_back_days: 最大回退天数
    返回:
        premium_rate: 溢价率（小数形式），None 表示获取失败
        price: 场内交易价格
        net_value: 基金净值
    """
    # 获取场内交易价格（给定日期）
    price_data = get_price(
        code,
        start_date=date,
        end_date=date,
        frequency='daily',
        fields=['close']
    )
    if price_data.empty:
        log.debug(f"{date} {code} 无交易价格数据")
        return None, None, None
    price = price_data['close'].iloc[0]

    # 获取净值，先尝试指定日期，若失败则向前搜索交易日
    net_value = None
    used_date = date
    # 获取从date往前max_back_days个交易日的列表（扩大范围确保包含足够交易日）
    start_date = date - datetime.timedelta(days=max_back_days*2)
    trade_days = get_trade_days(start_date=start_date, end_date=date)
    # 转换为 Python date 对象
    trade_days = [pd.to_datetime(d).date() for d in trade_days]
    # 倒序搜索，从date开始向前
    for dt in reversed(trade_days):
        if dt > date:  # 忽略大于date的日期
            continue
        # 尝试获取净值的两种方式
        net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            used_date = dt
            break
        # 备用方法
        try:
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == code,
                finance.FUND_NET_VALUE.day == dt
            )
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
                used_date = dt
                break
        except:
            continue

    if net_value is None:
        log.debug(f"{code} 在{date}及前{max_back_days}个交易日均无净值数据")
        return None, None, None

    premium_rate = (price - net_value) / net_value
    if used_date != date:
        log.debug(f"{code} 使用{used_date}的净值{net_value:.4f}代替{date}的净值计算溢价率")
    return premium_rate, price, net_value


def qixing_get_name(security):
    """获取证券名称，带异常处理"""
    try:
        return get_current_data()[security].name
    except:
        return "未知"


def qixing_calculate_rsi(close, period=14):
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


def qixing_laplace_filter(price, s=0.05):
    """拉普拉斯滤波器（正常期使用）"""
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


def qixing_gaussian_filter_last_two(price, sigma=1.2):
    """仅计算高斯滤波最后两个点（震荡期使用，效率优化）"""
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


def qixing_get_risk_benchmark_state(context):
    """获取风险基准的日线+盘中融合状态，用于震荡期判断"""
    required_days = max(g.qixing_ma_period, g.qixing_lookback_high_low_days)
    lookback = required_days + 30
    end_date = getattr(context, 'previous_date', None)
    if end_date is None:
        return None
    df = get_price(g.qixing_risk_benchmark, end_date=end_date, count=lookback,
                   frequency='daily', fields=['close', 'high', 'low'], panel=False)
    if df is None or len(df) < required_days:
        return None
    daily_close = df['close'].values.astype(float)
    daily_high = df['high'].values.astype(float)
    daily_low = df['low'].values.astype(float)
    current_price = float(daily_close[-1])
    intraday_high = current_price
    intraday_low = current_price
    data_source = '昨日日线'
    try:
        today = context.current_dt.date()
        minute_df = get_price(
            g.qixing_risk_benchmark, start_date=today, end_date=context.current_dt,
            frequency='1m', fields=['close', 'high', 'low'],
            panel=False, fill_paused=False
        )
        if minute_df is not None and not minute_df.empty:
            minute_close = minute_df['close'].dropna()
            minute_high = minute_df['high'].dropna()
            minute_low = minute_df['low'].dropna()
            if not minute_close.empty:
                current_price = float(minute_close.iloc[-1])
                intraday_high = float(minute_high.max()) if not minute_high.empty else current_price
                intraday_low = float(minute_low.min()) if not minute_low.empty else current_price
                data_source = '当日盘中'
    except Exception:
        pass
    if current_price <= 0:
        try:
            current_data = get_current_data()
            live_price = current_data[g.qixing_risk_benchmark].last_price
            if live_price is not None and live_price > 0:
                current_price = float(live_price)
                intraday_high = max(intraday_high, current_price)
                intraday_low = min(intraday_low, current_price)
                data_source = '实时快照'
        except Exception:
            current_price = float(daily_close[-1])
    close_series = np.append(daily_close, current_price)
    high_series = np.append(daily_high, max(intraday_high, current_price))
    low_series = np.append(daily_low, min(intraday_low, current_price))
    recent_high = np.max(high_series[-g.qixing_lookback_high_low_days:])
    recent_low = np.min(low_series[-g.qixing_lookback_high_low_days:])
    ma = np.mean(close_series[-g.qixing_ma_period:])
    current_rsi = qixing_calculate_rsi(close_series, period=14)
    previous_rsi = qixing_calculate_rsi(daily_close, period=14)
    return {
        'close_series': close_series,
        'high_series': high_series,
        'low_series': low_series,
        'current_price': current_price,
        'recent_high': recent_high,
        'recent_low': recent_low,
        'ma': ma,
        'current_rsi': current_rsi,
        'previous_rsi': previous_rsi,
        'data_source': data_source,
    }


def qixing_is_fresh_stop_loss_signal(context):
    """判断止损信号是否仍在有效期内"""
    signal_date = getattr(g, 'qixing_stop_loss_triggered_date', None)
    if signal_date is None:
        return False
    today = context.current_dt.date()
    previous_date = getattr(context, 'previous_date', None)
    if signal_date == today:
        return True
    if previous_date is not None and signal_date == previous_date:
        return True
    g.qixing_stop_loss_triggered_today = False
    g.qixing_stop_loss_triggered_date = None
    return False


def qixing_init_range_bound_status(context):
    """首次运行时，根据历史数据判断当前是否处于震荡期"""
    if not g.qixing_enable_range_bound_mode:
        return
    log.info("【七星首次运行】初始化震荡期状态...")
    try:
        if context.previous_date is None:
            log.warning("【七星首次运行】无法获取前一个交易日，保持正常期")
            return
        end_date = context.previous_date
        lookback = max(g.qixing_ma_period, g.qixing_lookback_high_low_days) + 30
        df = get_price(g.qixing_risk_benchmark, end_date=end_date, count=lookback,
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(g.qixing_ma_period, g.qixing_lookback_high_low_days):
            log.warning("【七星首次运行】数据不足，保持正常期")
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        if len(close) >= g.qixing_lookback_high_low_days:
            recent_high = np.max(high[-g.qixing_lookback_high_low_days:])
            recent_low = np.min(low[-g.qixing_lookback_high_low_days:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        ma = np.mean(close[-g.qixing_ma_period:])
        bias = (current_price - ma) / ma if ma > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        current_rsi = qixing_calculate_rsi(close, period=14)
        should_enter = False
        signals = []
        if g.qixing_enable_bias_trigger and bias > g.qixing_bias_threshold:
            should_enter = True
            signals.append(f"乖离率{bias:.2%}>{g.qixing_bias_threshold:.0%}")
        if g.qixing_enable_rsi_trigger and current_rsi is not None and len(close) >= 15:
            prev_rsi = qixing_calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.qixing_rsi_overbought and current_rsi < g.qixing_rsi_pullback:
                should_enter = True
                signals.append(f"RSI超买回落{prev_rsi:.1f}->{current_rsi:.1f}")
        if should_enter:
            g.qixing_current_filter = '震荡期'
            g.qixing_risk_state = '震荡期'
            g.qixing_range_bound_start_date = end_date
            g.qixing_range_bound_days_count = 0
            log.info(f"【七星首次运行】初始化进入震荡期: {'; '.join(signals)}")
        else:
            g.qixing_current_filter = '正常期'
            g.qixing_risk_state = '正常期'
            if len(close) >= g.qixing_lookback_high_low_days:
                g.qixing_previous_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
            else:
                g.qixing_previous_drawdown = 0
            g.qixing_previous_rsi = current_rsi
            rsi_str = f"{current_rsi:.1f}" if current_rsi is not None else "N/A"
            log.info(f"【七星首次运行】初始状态: 正常期, 乖离率: {bias:.2%}, RSI: {rsi_str}, 从低点涨幅: {rise_from_low:.2%}")
    except Exception as e:
        log.warning(f"【七星首次运行】初始化震荡期状态异常: {e}，保持正常期")


def qixing_check_and_exit_range_bound_mode(context):
    """检查是否需要退出震荡期"""
    if not g.qixing_enable_range_bound_mode:
        return
    if g.qixing_current_filter != '震荡期':
        return
    log.info("【七星震荡期退出检查】开始检测退出条件...")
    try:
        benchmark_state = qixing_get_risk_benchmark_state(context)
        if benchmark_state is None:
            log.warning("【七星震荡期退出检查】数据不足，跳过")
            return
        close = benchmark_state['close_series']
        current_price = benchmark_state['current_price']
        recent_high = benchmark_state['recent_high']
        recent_low = benchmark_state['recent_low']
        current_drawdown = (recent_high - current_price) / recent_high if recent_high > 0 else 0
        rise_from_low = (current_price - recent_low) / recent_low if recent_low > 0 else 0
        recovery_signals = []
        ma = benchmark_state['ma']
        current_rsi = benchmark_state['current_rsi']
        log.info(f"【七星震荡期数据】当前价: {current_price:.3f}, 近{g.qixing_lookback_high_low_days}日高点: {recent_high:.3f}, 低点: {recent_low:.3f}")
        log.info(f"【七星震荡期数据】回撤: {current_drawdown:.2%}, 从低点涨幅: {rise_from_low:.2%}")
        if g.qixing_enable_low_point_rise_trigger:
            if rise_from_low >= g.qixing_low_point_rise_threshold:
                recovery_signals.append(f"从低点上涨{rise_from_low:.2%}>={g.qixing_low_point_rise_threshold:.0%}")
                log.info(f"【七星退出条件触发】从低点上涨: {rise_from_low:.2%}")
        if g.qixing_enable_stable_signal_trigger:
            if current_price > ma:
                recovery_signals.append("价格站上均线")
            if len(close) >= 2 and close[-1] > close[-2]:
                recovery_signals.append("价格回升")
            if g.qixing_previous_drawdown is not None and current_drawdown < g.qixing_previous_drawdown:
                recovery_signals.append(f"回撤收窄({current_drawdown:.2%}<{g.qixing_previous_drawdown:.2%})")
            if current_rsi is not None and g.qixing_previous_rsi is not None and current_rsi > g.qixing_previous_rsi:
                recovery_signals.append(f"RSI回升({current_rsi:.1f})")
            drawdown_safe = current_drawdown < g.qixing_drawdown_recovery
            if drawdown_safe:
                g.qixing_stable_days += 1
                log.info(f"【七星企稳计数】连续企稳天数: {g.qixing_stable_days}")
            else:
                g.qixing_stable_days = 0
        g.qixing_previous_drawdown = current_drawdown
        g.qixing_previous_rsi = current_rsi
        range_bound_days = 0
        if g.qixing_range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.qixing_range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = len(trade_days) - 1
            if range_bound_days >= g.qixing_max_range_bound_days:
                recovery_signals.append(f"震荡期满({range_bound_days}天)")
                log.info(f"【七星退出条件触发】震荡期已满{range_bound_days}天")
        low_point_condition = g.qixing_enable_low_point_rise_trigger and rise_from_low >= g.qixing_low_point_rise_threshold
        stable_condition = False
        if g.qixing_enable_stable_signal_trigger:
            drawdown_safe = current_drawdown < g.qixing_drawdown_recovery
            stable_condition = drawdown_safe and len(recovery_signals) >= 2 and g.qixing_stable_days >= 2
        force_condition = range_bound_days >= g.qixing_max_range_bound_days
        should_recover = low_point_condition or stable_condition or force_condition
        if should_recover:
            can_switch = True
            if g.qixing_last_switch_date is not None:
                trade_days = get_trade_days(start_date=g.qixing_last_switch_date, end_date=context.current_dt.date())
                days_since = len(trade_days) - 1
                if days_since < g.qixing_filter_switch_cooldown:
                    can_switch = False
                    log.info(f"【七星震荡期退出】冷却期中，距上次切换{days_since}天")
            if can_switch:
                g.qixing_current_filter = '正常期'
                g.qixing_risk_state = '正常期'
                g.qixing_last_switch_date = context.current_dt.date()
                g.qixing_range_bound_start_date = None
                g.qixing_range_bound_days_count = 0
                g.qixing_stable_days = 0
                log.info(f"【七星退出震荡期】切换回拉普拉斯滤波器: {'; '.join(recovery_signals)}")
        else:
            log.info("【七星震荡期退出检查】未满足退出条件，保持震荡期(高斯滤波器)")
    except Exception as e:
        log.warning(f"【七星震荡期退出检查】判断出错: {e}")


def qixing_check_and_enter_range_bound_mode(context):
    """检查是否需要进入震荡期"""
    if not g.qixing_enable_range_bound_mode:
        return
    log.info("【七星震荡期进入检查】开始检测...")
    stop_loss_signal_active = qixing_is_fresh_stop_loss_signal(context)
    can_switch = True
    if g.qixing_last_switch_date is not None:
        trade_days = get_trade_days(start_date=g.qixing_last_switch_date, end_date=context.current_dt.date())
        days_since = len(trade_days) - 1
        if days_since < g.qixing_filter_switch_cooldown:
            can_switch = False
            log.info(f"【七星震荡期检查】冷却期中，距上次切换{days_since}天")
    if g.qixing_current_filter == '震荡期':
        log.info("【七星震荡期检查】当前已在震荡期")
        return
    if not can_switch:
        return
    risk_signals = []
    try:
        benchmark_state = qixing_get_risk_benchmark_state(context)
        if benchmark_state is not None:
            close = benchmark_state['close_series']
            current_price = benchmark_state['current_price']
            # 条件1: 乖离率过大
            if g.qixing_enable_bias_trigger:
                ma = benchmark_state['ma']
                bias = (current_price - ma) / ma if ma > 0 else 0
                if bias > g.qixing_bias_threshold:
                    risk_signals.append(f"乖离率过大({bias:.2%}>{g.qixing_bias_threshold:.0%})")
                    log.info(f"【七星条件触发】乖离率: {bias:.2%} (数据源:{benchmark_state['data_source']})")
            # 条件2: RSI超买回落
            if g.qixing_enable_rsi_trigger:
                current_rsi = benchmark_state['current_rsi']
                if len(close) >= 15 and current_rsi is not None:
                    prev_rsi = benchmark_state['previous_rsi']
                    if prev_rsi is not None:
                        if prev_rsi > g.qixing_rsi_overbought and current_rsi < g.qixing_rsi_pullback and current_rsi < prev_rsi:
                            risk_signals.append(f"RSI超买回落({prev_rsi:.1f}->{current_rsi:.1f})")
                            log.info(f"【七星条件触发】RSI超买回落: {prev_rsi:.1f}->{current_rsi:.1f}")
    except Exception as e:
        log.warning(f"【七星震荡期检查】获取基准数据异常: {e}")
    # 条件3: 盈利保护触发止损
    if g.qixing_enable_stop_loss_trigger and stop_loss_signal_active:
        risk_signals.append("盈利保护触发止损")
        log.info("【七星条件触发】盈利保护触发止损信号")
    if len(risk_signals) > 0:
        g.qixing_current_filter = '震荡期'
        g.qixing_risk_state = '震荡期'
        g.qixing_last_switch_date = context.current_dt.date()
        g.qixing_range_bound_start_date = context.current_dt.date()
        g.qixing_range_bound_days_count = 0
        g.qixing_stable_days = 0
        g.qixing_stop_loss_triggered_today = False
        g.qixing_stop_loss_triggered_date = None
        log.info(f"【七星进入震荡期】切换到高斯滤波器: {'; '.join(risk_signals)}")
    else:
        log.info("【七星震荡期检查】未满足进入条件，保持正常期(拉普拉斯滤波器)")


def qixing_check_range_bound(context):
    """震荡期检查入口（定时调度，在卖出前执行）"""
    if not g.qixing_enable_range_bound_mode:
        return
    log.info("========== 七星震荡期检查开始 ==========")
    log.info(f"当前状态: {g.qixing_current_filter}")
    qixing_check_and_exit_range_bound_mode(context)
    qixing_check_and_enter_range_bound_mode(context)
    log.info(f"检查后状态: {g.qixing_current_filter}")
    # 状态变更后清除排名缓存，确保卖出时重新计算
    g.qixing_rankings_cache = {'date': None, 'data': None}
    log.info("========== 七星震荡期检查完成 ==========")


def qixing_reset_range_bound_daily(context):
    """收盘后重置震荡期相关的每日标志"""
    if g.qixing_current_filter == '震荡期' and g.qixing_range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.qixing_range_bound_start_date, end_date=context.current_dt.date())
        g.qixing_range_bound_days_count = len(trade_days) - 1
        log.info(f"七星震荡期已持续 {g.qixing_range_bound_days_count} 个交易日")
    log.debug("七星收盘震荡期标志重置完成")


# ==================== 七星策略动量计算和排名函数 ====================
def qixing_get_cached_rankings(context):
    """获取缓存的ETF排名，保证同一交易日内多次调用结果一致"""
    today = context.current_dt.date()
    if g.qixing_rankings_cache['date'] != today:
        log.info("七星重新计算ETF排名...")
        ranked = qixing_get_ranked_etfs(context)
        g.qixing_rankings_cache = {'date': today, 'data': ranked}
    else:
        log.debug("七星使用缓存的ETF排名")
    return g.qixing_rankings_cache['data']


def qixing_get_ranked_etfs(context):
    """
    计算所有ETF的动量得分，应用所有过滤条件，返回按得分降序的列表
    """
    etf_metrics = []
    for etf in g.qixing_etf_pool:
        # 停牌过滤
        if get_current_data()[etf].paused:
            log.debug(f"{etf} {qixing_get_name(etf)} 停牌，跳过")
            continue

        metrics = qixing_calculate_momentum_metrics(context, etf)
        if metrics is not None:
            # 得分范围过滤
            if g.qixing_min_score_threshold < metrics['score'] < g.qixing_max_score_threshold:
                etf_metrics.append(metrics)
            else:
                log.debug(f"{etf} {metrics['etf_name']} 得分{metrics['score']:.2f}超出阈值，过滤")

    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def qixing_calculate_momentum_metrics(context, etf):
    """
    计算单只ETF的动量指标，应用所有过滤条件
    返回字典：etf, etf_name, annualized_returns, r_squared, score, current_price, short_annualized
    """
    try:
        name = qixing_get_name(etf)
        # 获取足够历史数据
        lookback = max(g.qixing_lookback_days, g.qixing_short_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < g.qixing_lookback_days:
            log.debug(f"{etf} {name} 历史数据不足{len(prices)}天，跳过")
            return None

        # 价格序列（含当天）
        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        # ===== 【新增】流动性检查（20日日均成交额），不达标直接排除 =====
        liquidity_pass, avg_amount = qixing_check_liquidity(etf, context)
        if not liquidity_pass:
            log.info(f"🚫 {etf} {name} 流动性不达标，过去{g.qixing_liquidity_lookback_days}日日均成交额{avg_amount/10000:.2f}万元 < 阈值{g.qixing_liquidity_threshold/10000:.0f}万元，从排名中排除")
            return None

        # ===== 1. 盈利保护检查（排除） =====
        if qixing_check_profit_protection(etf, context):
            log.info(f"🚫 {etf} {name} 触发盈利保护，从排名中排除")
            return None

        # ===== 2. 溢价率过滤（提前至排名阶段，获取失败则跳过过滤）=====
        if g.qixing_enable_premium_filter:
            # 获取前一个交易日（用于净值数据）
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = qixing_get_premium_rate(etf, prev_date)
            if premium is not None:
                if premium > g.qixing_premium_threshold:
                    log.info(f"🚫 {etf} {name} 溢价率{premium*100:.2f}% > {g.qixing_premium_threshold*100:.0f}%，从排名中排除")
                    return None
            else:
                # 无法获取溢价率，跳过该过滤条件（不过滤）
                log.debug(f"{etf} {name} 无法获取溢价率，跳过溢价率过滤")

        # ===== 3. 成交量过滤（排除） =====
        if g.qixing_enable_volume_check:
            vol_ratio = qixing_get_volume_ratio(context, etf)
            if vol_ratio is not None:
                annualized = qixing_get_annualized_returns(price_series, g.qixing_lookback_days)
                if annualized > g.qixing_volume_return_limit:
                    log.info(f"📉 {etf} {name} 成交量放量{vol_ratio:.1f}倍，且年化{annualized*100:.1f}% > 阈值{g.qixing_volume_return_limit*100:.1f}%，过滤")
                    return None

        # ===== 4. 短期动量过滤（排除） =====
        if len(price_series) >= g.qixing_short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.qixing_short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.qixing_short_lookback_days) - 1
        else:
            short_annualized = 0

        if g.qixing_use_short_momentum_filter and short_annualized < g.qixing_short_momentum_threshold:
            log.debug(f"{etf} {name} 短期动量{short_annualized*100:.1f}% < 阈值{g.qixing_short_momentum_threshold*100:.1f}%，过滤")
            return None

        # ===== 5. 长期动量计算（得分） =====
        recent = price_series[-(g.qixing_lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1

        # R²（趋势稳定性）
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        score = annualized_returns * r_squared

        # ===== 6. 近3日单日跌幅过滤（排除） =====
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if min(day1, day2, day3) < g.qixing_loss:
                log.info(f"⚠️ {etf} {name} 近3日有单日跌幅超{(1-g.qixing_loss)*100:.1f}%，直接排除")
                return None

        # ===== 7. 动态滤波器过滤（震荡期机制） =====
        if g.qixing_enable_range_bound_mode and len(price_series) >= 10:
            try:
                laplace_values = qixing_laplace_filter(price_series, s=g.qixing_laplace_s_param)
                laplace_slope = laplace_values[-1] - laplace_values[-2] if len(laplace_values) >= 2 else 0
                passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.qixing_laplace_min_slope)
                g1_val, g2_val = qixing_gaussian_filter_last_two(price_series, sigma=g.qixing_gaussian_sigma)
                gaussian_slope = g1_val - g2_val
                passed_gaussian = (current_price > g1_val and gaussian_slope > g.qixing_gaussian_min_slope)
                if g.qixing_current_filter == '正常期':
                    passed_filter = passed_laplace
                    filter_name = '拉普拉斯'
                else:
                    passed_filter = passed_gaussian
                    filter_name = '高斯'
                if not passed_filter:
                    log.debug(f"{etf} {name} 未通过{filter_name}滤波器({g.qixing_current_filter})，过滤")
                    return None
            except Exception as e:
                log.debug(f"{etf} {name} 滤波器计算异常: {e}")

        return {
            'etf': etf,
            'etf_name': name,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'current_price': current_price,
            'short_annualized': short_annualized,
        }

    except Exception as e:
        log.warning(f"计算{etf} {qixing_get_name(etf)}时出错: {e}")
        return None


def qixing_get_annualized_returns(price_series, lookback_days):
    """计算加权年化收益率"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def qixing_get_volume_ratio(context, security, lookback=None, threshold=None):
    """计算当日成交量与过去N日均量的比值，若超过阈值则返回比值，否则None"""
    lookback = lookback or g.qixing_volume_lookback
    threshold = threshold or g.qixing_volume_threshold
    try:
        name = qixing_get_name(security)
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()

        # 获取当日分钟成交量累计
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        if ratio > threshold:
            log.debug(f"{security} {name} 成交量比{ratio:.2f} > {threshold}")
            return ratio
        return None
    except Exception as e:
        log.warning(f"七星成交量计算失败 {security}: {e}")
        return None


# ==================== 七星策略交易执行函数 ====================
def qixing_check_positions(context):
    """每日开盘检查持仓状态，仅用于日志"""
    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 七星持仓：{sec} {qixing_get_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")


def qixing_check_defensive_etf_available(context):
    """检查防御ETF是否可交易（未停牌、未涨跌停）"""
    data = get_current_data()
    etf = g.qixing_defensive_etf
    if data[etf].paused:
        log.debug(f"七星防御ETF {etf} {qixing_get_name(etf)} 停牌")
        return False
    if data[etf].last_price >= data[etf].high_limit:
        log.debug(f"七星防御ETF {etf} {qixing_get_name(etf)} 涨停")
        return False
    if data[etf].last_price <= data[etf].low_limit:
        log.debug(f"七星防御ETF {etf} {qixing_get_name(etf)} 跌停")
        return False
    return True


def qixing_smart_order_target_value(security, target_value, context):
    """
    智能下单：根据目标市值调整持仓，处理停牌、涨跌停、最小交易金额、T+1
    """
    data = get_current_data()
    name = qixing_get_name(security)

    if data[security].paused:
        log.info(f"{security} {name} 停牌，跳过")
        return False

    price = data[security].last_price
    if price == 0:
        log.info(f"{security} {name} 当前价格0，跳过")
        return False

    target_amount = int(target_value / price)
    # 按100股整数倍调整
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount

    # 根据交易方向检查涨跌停
    if diff > 0:  # 买入
        if data[security].last_price >= data[security].high_limit:
            log.info(f"{security} {name} 涨停，跳过买入")
            return False
    elif diff < 0:  # 卖出
        if data[security].last_price <= data[security].low_limit:
            log.info(f"{security} {name} 跌停，跳过卖出")
            return False

    # 最小交易金额检查
    trade_val = abs(diff) * price
    if 0 < trade_val < g.qixing_min_money:
        log.info(f"{security} {name} 交易金额{trade_val:.2f} < {g.qixing_min_money}，跳过")
        return False

    # T+1处理
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            log.info(f"{security} {name} 当天买入不可卖出")
            return False
        diff = -min(abs(diff), closeable)

    if diff != 0:
        order_result = order(security, diff)
        if order_result:
            log.info(f"{'📥 买入' if diff>0 else '📤 卖出'} {security} {name} 数量{abs(diff)} 价格{price:.3f}")
            return True
        else:
            log.warning(f"七星下单失败: {security} {name} 数量{diff}")
            return False
    return False


def qixing_etf_sell_trade(context):
    """卖出不符合条件的持仓（排名变化、溢价率过高）"""
    log.info("========== 七星卖出操作开始 ==========")

    ranked = qixing_get_cached_rankings(context)
    # 确定目标ETF列表（得分前N名且满足得分阈值）
    target_etfs = []
    for m in ranked[:g.qixing_holdings_num]:
        if m['score'] >= g.qixing_min_score_threshold:
            target_etfs.append(m['etf'])
    # 若没有目标ETF且防御可用，则把防御ETF作为目标（供卖出判断用）
    defensive_available = qixing_check_defensive_etf_available(context)
    if not target_etfs and defensive_available:
        target_etfs = [g.qixing_defensive_etf]

    target_set = set(target_etfs)

    # 卖出不在目标列表的持仓
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.qixing_etf_pool and sec != g.qixing_defensive_etf:
            continue
        if sec not in target_set:
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                if qixing_smart_order_target_value(sec, 0, context):
                    log.info(f"📤 七星卖出不在目标的持仓：{sec} {qixing_get_name(sec)}")

    log.info("========== 七星卖出操作完成 ==========")


def qixing_etf_buy_trade(context):
    """买入符合条件的ETF，等权分配，按排名顺序逐个尝试直到凑够持仓数量"""
    log.info("========== 七星买入操作开始 ==========")

    ranked = qixing_get_cached_rankings(context)
    # 打印排名前5的指标（调试用）
    log.info("=== 七星ETF排名前5 ===")
    for i, m in enumerate(ranked[:5]):
        log.info(f"排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f} 年化{m['annualized_returns']*100:.2f}% R²={m['r_squared']:.4f}")

    # ---------- 确定目标ETF列表：依次尝试排名靠前的ETF ----------
    target_etfs = []
    prev_date = None
    if g.qixing_enable_premium_filter:
        # 获取前一个交易日用于溢价率计算
        prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]

    for m in ranked:   # 按得分从高到低遍历所有ETF
        if len(target_etfs) >= g.qixing_holdings_num:
            break   # 已凑够目标持仓数量
        etf = m['etf']

        # 通过所有检查，加入目标列表
        target_etfs.append(etf)
        log.info(f"🎯 七星目标ETF {len(target_etfs)}: {etf} {m['etf_name']} 得分{m['score']:.4f}")

    # ---------- 防御模式判断 ----------
    if not target_etfs:
        if qixing_check_defensive_etf_available(context):
            target_etfs = [g.qixing_defensive_etf]
            log.info(f"🛡️ 七星进入防御模式，选择防御ETF：{g.qixing_defensive_etf} {qixing_get_name(g.qixing_defensive_etf)}")
        else:
            log.info("💤 七星无目标ETF且防御不可用，保持空仓")
            return

    # 检查是否有持仓需要先卖出（不在目标列表的持仓）
    current_etf_pos = [s for s in context.portfolio.positions if s in g.qixing_etf_pool or s == g.qixing_defensive_etf]
    to_sell = [s for s in current_etf_pos if s not in target_etfs]
    if to_sell:
        to_sell_names = [qixing_get_name(s) for s in to_sell]
        log.info(f"七星尚有持仓需要卖出：{list(zip(to_sell, to_sell_names))}，等待卖出完成再买入")
        return

    # 等权分配
    total_val = context.portfolio.total_value
    target_per_etf = total_val / len(target_etfs)

    for etf in target_etfs:
        current_val = 0
        if etf in context.portfolio.positions:
            pos = context.portfolio.positions[etf]
            if pos.total_amount > 0:
                current_val = pos.total_amount * pos.price
        # 5%容差调仓
        if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
            if qixing_smart_order_target_value(etf, target_per_etf, context):
                action = "买入" if current_val < target_per_etf else "调仓"
                log.info(f"📦 七星{action}：{etf} {qixing_get_name(etf)} 目标金额{target_per_etf:.2f}")

    log.info("========== 七星买入操作完成 ==========")


# ---------- 五福5.1v3（策略3内嵌，聚宽单文件）来源：69702 ----------

# ==================== 首次运行震荡期状态初始化 ====================
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

# ==================== 任务流水线 ====================
def morning_routine(context):
    """晨间准备流水线（09:00执行）：持仓检查 → 流动性阈值计算"""
    log.info("★" * 80)
    log.info("▶️ 【晨间流水线】启动...")
    log.info("【持仓检查】检查当前持仓状态...")
    check_positions(context)
    log.info(
        f"【回撤监控】已移至盘中定时任务（默认 {getattr(g, 'dd_monitor_time', '10:31')}），"
        "避免开盘前无连续竞价价；QDII/LOF 请以该时点场内价口径为准。"
    )
    if getattr(g, 'log_pool_update_details', False):
        log.info("【流动性阈值】计算全市场ETF流动性阈值...")
    calculate_global_etf_threshold(context)
    log.info("⏸️ 【晨间流水线】执行完毕！")


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
                log.warning(f"🔄 【防漏仓修复】捕获幽灵ETF {sec}，强制归还给五福5.1v3！")
            # 其他(通常是股票)给策略1
            else:
                g.strategy_holdings[1].append(sec)
                g.stock_strategy[sec] = 1
                log.warning(f"🔄 【防漏仓修复】捕获幽灵股票 {sec}，强制归还给策略1！")
                
    # 去重
    for sid in [1, 2, 3, 4]:
        g.strategy_holdings[sid] = list(dict.fromkeys(g.strategy_holdings[sid]))


def log_pending_short_momentum_3up_followups(context):
    """短期动量跟踪日志（v5.1，暂为空实现）"""
    pass


def midday_routine(context):
    """早盘流水线（09:40后执行）：根据市场状态更新ETF池"""
    log.info("★" * 80)
    log.info("▶️ 【早盘流水线】启动...")
    
    today = context.current_dt.date()
    
    if g.market_regime == '走弱期':
        log.info(f"🔴 【走弱期池更新】仅对全球/海外ETF池进行流动性过滤...")
        filter_global_pool_by_volume(context)
        g._filtered_global_pool_date = today  # 标记更新日期
        log.info(f"【走弱期池更新完成】过滤后全球池: {len(g.filtered_global_pool)}只")
    else:
        log.info(f"🟢 【{g.market_regime}池更新】执行动态池更新、固定池过滤、合并池...")
        if getattr(g, 'log_pool_update_details', False):
            log.info("【动态池更新】更新行业ETF动态池（各行业流动性最佳ETF）...")
        update_sector_pool(context)
        if getattr(g, 'log_pool_update_details', False):
            log.info("【固定池过滤】过滤固定ETF池流动性...")
        filter_fixed_pool_by_volume(context)
        if getattr(g, 'log_pool_update_details', False):
            log.info("【合并池】合并固定池与动态池...")
        daily_merge_etf_pools(context)
        g._merged_etf_pool_date = today  # 标记更新日期
        log.info(f"【{g.market_regime}池更新完成】合并池: {len(g.merged_etf_pool)}只")
    
    log.info("⏸️ 【早盘流水线】执行完毕！")


def refresh_holdings_num_by_regime(context):
    """根据市场状态动态调整持仓数（v5.1）"""
    regime = getattr(g, 'market_regime', '震荡期')
    prev = int(getattr(g, 'holdings_num', 1))
    target_map = {
        '正常期': int(getattr(g, 'holdings_num_normal', prev)),
        '震荡期': int(getattr(g, 'holdings_num_oscillation', prev)),
        '走弱期': int(getattr(g, 'holdings_num_weak', prev)),
    }
    new_holdings = max(1, target_map.get(regime, prev))
    g.holdings_num = new_holdings
    if new_holdings != prev:
        log.info(f"🧭 【持仓数切换】状态={regime}，holdings_num: {prev} → {new_holdings}")
    else:
        log.info(f"🧭 【持仓数】状态={regime}，holdings_num={new_holdings}")


def _afternoon_prepare_and_rank(context):
    """午盘共用：复盘跟踪、动量排序（不含买卖）。
    改进版：根据当前市场状态动态更新ETF池，确保数据最新
    """
    log_pending_short_momentum_3up_followups(context)

    # 根据当前市场状态动态更新ETF池
    current_regime = g.market_regime
    
    if current_regime == '走弱期':
        # 检查filtered_global_pool是否是今天更新的
        last_update_date = getattr(g, '_filtered_global_pool_date', None)
        today = context.current_dt.date()
        
        if last_update_date != today or not hasattr(g, 'filtered_global_pool') or not g.filtered_global_pool:
            # 需要重新过滤
            log.info(f"🔄 【走弱期】检测到ETF池需要更新，重新过滤全球池...")
            filter_global_pool_by_volume(context)
            g._filtered_global_pool_date = today
        
        # 使用过滤后的全球池
        if hasattr(g, 'filtered_global_pool') and g.filtered_global_pool:
            g.merged_etf_pool = list(set(g.filtered_global_pool))
        else:
            g.merged_etf_pool = list(set(g.global_etf_pool))
        g.merged_etf_pool.sort()
        log.info(f"🔴 【走弱期】使用过滤后全球/海外ETF池，共{len(g.merged_etf_pool)}只")
    else:
        # 正常期/震荡期：检查merged_etf_pool是否是今天更新的
        last_update_date = getattr(g, '_merged_etf_pool_date', None)
        today = context.current_dt.date()
        
        if last_update_date != today or not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
            # 需要重新更新
            log.info(f"🔄 【{current_regime}】检测到ETF池需要更新，重新执行池更新流程...")
            if getattr(g, 'log_pool_update_details', False):
                log.info("【动态池更新】更新行业ETF动态池（各行业流动性最佳ETF）...")
            update_sector_pool(context)
            if getattr(g, 'log_pool_update_details', False):
                log.info("【固定池过滤】过滤固定ETF池流动性...")
            filter_fixed_pool_by_volume(context)
            if getattr(g, 'log_pool_update_details', False):
                log.info("【合并池】合并固定池与动态池...")
            daily_merge_etf_pools(context)
            g._merged_etf_pool_date = today
        
        log.info(f"🟢 【{current_regime}】使用合并池，共{len(g.merged_etf_pool)}只")
    
    refresh_holdings_num_by_regime(context)
    log.info("【动量计算】计算ETF动量得分与排序...")
    calculate_and_log_ranked_etfs(context)


def afternoon_routine(context):
    """原逻辑：13:08 同刻先卖后买（已提前2分钟）。"""
    sell_time = getattr(g, 'afternoon_sell_time', '13:08')
    log.info(f"▶️ 【午盘流水线】{sell_time} 启动...")
    _afternoon_prepare_and_rank(context)
    
    # 非纯五福模式时同步持仓
    if g.portfolio_value_proportion != [0, 0, 1, 0]:
        log.info("【持仓同步】同步五福5.1v3登记持仓与账户真实持仓...")
        sync_strategy3_holdings_from_portfolio(context)
    
    log.info("【卖出执行】执行卖出操作...")
    execute_sell_trades(context)
    log.info("【买入执行】执行买入操作...")
    execute_buy_trades(context)
    log.info(f"⏸️ 【午盘流水线】{sell_time} 执行完毕！")


def reset_daily_flags(context):
    """收盘流水线（15:10执行）：重置价格缓存"""
    # 重置价格缓存（防止次日止损计算使用错误数据）
    g.cache_date = None
    g.yesterday_close_cache = {}
    log.info("🔄 收盘缓存重置完成")


# ==================== 持仓检查 ====================
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

# ==================== 退出震荡期检查 ====================
# ==================== 动量得分计算 ====================
def calculate_and_log_ranked_etfs(context):
    """计算合并池中的标的动量得分（v5.1完整版）"""
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.warning("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        g.last_metrics_by_etf_code = {}
        return
    
    # 调用完整的ETF排序函数
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
    W = weights ** 2
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
        price_series = np.append(hist_closes, current_price)
        if len(price_series) < max(g.lookback_days, g.short_momentum_lookback) * 0.8:
            return None
        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_series, g.lookback_days)
        if momentum_score is None:
            return None
        short_momentum_score, short_annualized_returns, short_r_squared = calculate_momentum_score(price_series, g.short_momentum_lookback)
        
        # v5.1新增：计算momentum_rank_score（软封顶处理）
        effective_min_score = float(getattr(g, 'min_score_threshold', 0))
        effective_max_score = float(getattr(g, 'max_score_threshold', 5))
        momentum_rank_score = momentum_score
        soft_cap_enabled = bool(getattr(g, 'enable_momentum_soft_cap', False))
        soft_cap_normal_only = bool(getattr(g, 'momentum_soft_cap_normal_only', True))
        regime = getattr(g, 'market_regime', '震荡期')
        apply_soft_cap = soft_cap_enabled and ((not soft_cap_normal_only) or regime == '正常期')
        if apply_soft_cap and momentum_score > effective_max_score:
            penalty = float(getattr(g, 'momentum_soft_cap_penalty', 0.2))
            penalty = max(0.0, min(1.0, penalty))
            momentum_rank_score = effective_max_score + (momentum_score - effective_max_score) * penalty
        else:
            momentum_rank_score = momentum_score
        
        passed_momentum = (g.min_score_threshold <= momentum_score <= g.max_score_threshold)
        passed_short_momentum = (g.short_momentum_min_score <= short_momentum_score <= g.short_momentum_max_score) if short_momentum_score is not None else False
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
        
        # v5.1新增：MA均线过滤（走弱期启用）
        passed_ma = True
        ma_value = None
        if len(price_series) >= g.ma_lookback:
            ma_value = np.mean(price_series[-g.ma_lookback:])
            passed_ma = current_price > ma_value * g.ma_threshold
        else:
            passed_ma = False
        
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
        if g.current_filter == '正常期':
            filter_value = laplace_value
            filter_slope = laplace_slope
            passed_filter = passed_laplace
        else:
            filter_value = gaussian_value
            filter_slope = gaussian_slope
            passed_filter = passed_gaussian
        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'momentum_rank_score': momentum_rank_score,  # v5.1新增
            'short_momentum_score': short_momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'premium_rate': premium_rate,
            'passed_momentum': passed_momentum,
            'passed_short_momentum': passed_short_momentum,
            'passed_r2': r_squared > g.r2_threshold,
            'passed_ma': passed_ma,  # v5.1新增
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter,
            'passed_premium': passed_premium,
            'ma_value': ma_value,  # v5.1新增
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
        return None, True


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
    """根据开关应用所有过滤条件（v5.1完整版）"""
    regime = getattr(g, 'market_regime', '震荡期')
    use_short_momentum = g.use_short_momentum_period
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], True),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter and regime != '走弱期'),
        ('均线', lambda m: m['passed_ma'], g.enable_ma_filter and regime == '走弱期'),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
        ('溢价率', lambda m: m['passed_premium'], g.enable_premium_filter),
        ('拉普拉斯滤波', lambda m: m['passed_laplace'], g.enable_laplace_filter and regime == '正常期'),
        ('高斯滤波', lambda m: m['passed_gaussian'], regime == '震荡期'),
    ]
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            before_count = len(filtered)
            filtered = [m for m in filtered if condition(m)]
            after_count = len(filtered)
            if before_count > after_count:
                log.debug(f"【过滤条件】{name}: 通过 {after_count}/{before_count}")
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
    lookback = max(g.lookback_days, g.short_momentum_lookback, g.volume_lookback) + 20
    today = context.current_dt.date()
    current_data = get_current_data()
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
        if current_data[etf].paused:
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
        current_price = current_data[etf].last_price
        today_vol = today_vols.get(etf, 0)
        metrics = calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                continue
            all_metrics.append(metrics)
    g.last_metrics_by_etf_code = {m['etf']: m for m in all_metrics}
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
        rank_score = item.get('momentum_rank_score', score)
        if pd.isna(rank_score) or (isinstance(rank_score, float) and np.isnan(rank_score)):
            item['momentum_rank_score'] = float('-inf')
        short_score = item.get('short_momentum_score')
        if pd.isna(short_score) or (isinstance(short_score, float) and np.isnan(short_score)):
            item['short_momentum_score'] = float('-inf')
    # v5.1关键修复：使用momentum_rank_score排序（而非momentum_score）
    all_metrics.sort(key=lambda x: x.get('momentum_rank_score', float('-inf')), reverse=True)
    log_buffer = []
    log_buffer.append("")
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
    # v5.1关键修复：过滤后也使用momentum_rank_score排序
    filtered_list.sort(key=lambda x: x.get('momentum_rank_score', float('-inf')), reverse=True)
    top_10 = filtered_list[:10]
    log_buffer.append("")
    log_buffer.append(f">>> 第二步：符合全部过滤条件的ETF按动量得分从大到小排序(前10名) <<<")
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
    # v5.1关键修复：使用momentum_rank_score作为排序键
    score_key = 'momentum_rank_score'
    regime = getattr(g, 'market_regime', '震荡期')
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        # v5.1新增：根据市场状态动态调整阈值比例
        ratio = g.score_threshold_ratio if regime != '走弱期' else 1.0
        score_threshold = reference_score * ratio
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：选取动量得分≥第{g.holdings_num}名({top_10[g.holdings_num - 1]['etf_name']})得分{reference_score:.4f}×{ratio}={score_threshold:.4f}的ETF <<<")
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：前10名不足{g.holdings_num}只，全部作为候选池 <<<")
        candidate_pool = top_10[:]
    log_buffer.append(f"【候选池】共{len(candidate_pool)}只ETF（按动量得分排序）：")
    for i, item in enumerate(candidate_pool):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")
    log_buffer.append("")
    log_buffer.append(">>> 第四步：结合当前持仓进行调整 <<<")
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    log_buffer.append(f"当前持仓ETF：{current_holdings}")
    candidate_dict = {item['etf']: item for item in candidate_pool}

    # v5.1新增：防频换逻辑（避免频繁换股）
    # 注意：不在此因「非防频换适用状态」清空 streak。否则指数+冷却下常日不适用，streak 永无法累加。
    # streak 仅在防频换分支内：重返第1/换股/出池/无仓/候选池空 时清零；不适用日仅「暂停累加」。

    regime_allows_anti_churn = (
        regime == '正常期'
        or (regime == '震荡期' and getattr(g, 'oscillation_anti_churn_enabled', False))
        or (regime == '走弱期' and getattr(g, 'weak_anti_churn_enabled', False))
    )
    use_regime_anti_churn = (
        regime_allows_anti_churn and g.holdings_num >= 1 and len(candidate_pool) > 0
    )
    if not use_regime_anti_churn:
        _nr = int(getattr(g, 'normal_not_rank1_streak', 0))
        why = []
        if not regime_allows_anti_churn:
            if regime == '震荡期':
                why.append("震荡期防频换关闭(g.oscillation_anti_churn_enabled=False)")
            elif regime == '走弱期':
                why.append("走弱期防频换关闭(g.weak_anti_churn_enabled=False)")
            else:
                why.append(f"状态【{regime}】不适用防频换")
        if g.holdings_num < 1:
            why.append(f"holdings_num={g.holdings_num}")
        if len(candidate_pool) == 0:
            why.append("候选池为空")
        if why:
            log.info(
                f"【防频换】本日不执行: {'; '.join(why)}。streak 保持不重置(当前={_nr})，走原合并逻辑。"
            )
    if use_regime_anti_churn:
        max_days_single = int(getattr(g, 'normal_max_days_not_rank1', 5))
        AC = (
            '【震荡期防频换】'
            if regime == '震荡期'
            else ('【走弱期防频换】' if regime == '走弱期' else '【正常期防频换】')
        )
        rank1_etf = filtered_list[0]['etf']
        rank1_name = filtered_list[0]['etf_name']
        new_first = candidate_pool[0]
        pool_codes = set(candidate_dict.keys())
        topk = max(1, int(getattr(g, 'holdings_num', 1)))

        if g.holdings_num > 1:
            # 多持仓模式：候选池内且排名进入TopK则保留；候选池外立即替换；
            # 候选池内但排名未进TopK时，达到max_days再替换，防止频繁抖动。
            if regime == '震荡期':
                max_days = int(getattr(g, 'oscillation_max_days_not_topk', max_days_single))
            else:
                max_days = int(getattr(g, 'normal_max_days_not_topk', max_days_single))
            streaks = dict(getattr(g, 'normal_not_topk_streaks', {}) or {})
            ranked_codes = [item['etf'] for item in filtered_list]
            rank_map = {code: idx + 1 for idx, code in enumerate(ranked_codes)}
            retained = []
            must_replace = []
            watch_replace = []

            for h in current_holdings:
                if h not in pool_codes:
                    must_replace.append((h, "掉出候选池"))
                    streaks.pop(h, None)
                    continue
                r = rank_map.get(h)
                if r is None:
                    must_replace.append((h, "不在过筛排序表"))
                    streaks.pop(h, None)
                    continue
                if r <= topk:
                    retained.append(candidate_dict[h])
                    streaks[h] = 0
                else:
                    streaks[h] = int(streaks.get(h, 0)) + 1
                    watch_replace.append((h, r, streaks[h]))

            # 先保留应保留，再按规则把超出TopK且达阈值的持仓替换
            for h, r, s in watch_replace:
                if s >= max_days:
                    must_replace.append((h, f"连续{s}日未进Top{topk}"))
                    streaks.pop(h, None)
                else:
                    retained.append(candidate_dict[h])
                    log_buffer.append(
                        f"{AC}{h} 名次={r} 未进Top{topk} streak={s}/{max_days}，暂继续持有"
                    )

            if must_replace:
                rs = "；".join([f"{h}({reason})" for h, reason in must_replace])
                log_buffer.append(f"{AC}触发替换: {rs}")
                log.info(f"{AC}多持仓替换触发: {rs}")

            target_count = max(1, int(g.holdings_num))
            retained_codes = {item['etf'] for item in retained}
            fill_pool = [item for item in candidate_pool if item['etf'] not in retained_codes]
            final_result = retained + fill_pool[:max(0, target_count - len(retained))]
            final_result = final_result[:target_count]

            for item in final_result:
                streaks.setdefault(item['etf'], 0)

            # 清理不在当前持仓目标中的旧键，避免字典无限增长
            active_codes = {item['etf'] for item in final_result}
            streaks = {k: v for k, v in streaks.items() if k in active_codes}
            g.normal_not_topk_streaks = streaks
            # 单持仓变量在多持仓场景不再使用，清零避免混淆日志
            g.normal_not_rank1_streak = 0
            g.normal_streak_hold_code = None

            log_buffer.append(
                f"{AC}多持仓防频换完成：保留{len(retained)}只，最终目标{len(final_result)}/{target_count}只，TopK={topk}"
            )
            log.info(
                f"{AC}多持仓防频换: 保留{len(retained)} 目标{len(final_result)}/{target_count} TopK={topk}"
            )
        else:
            # 单持仓模式防频换逻辑
            def _rank_in_filtered_list(flist, etf_code):
                """返回ETF在filtered_list中的排名（从1开始），不存在返回None"""
                for idx, item in enumerate(flist):
                    if item.get('etf') == etf_code:
                        return idx + 1
                return None

            max_days = max_days_single
            H = current_holdings[0] if len(current_holdings) == 1 else (current_holdings[0] if current_holdings else None)
            rH = _rank_in_filtered_list(filtered_list, H) if H else None

            if not H:
                final_result = [new_first]
                g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = new_first['etf']
                t = f"{AC}无持仓 → 目标为候选池第1名"
                log_buffer.append(t)
                log.info(f"{t}: {new_first['etf']} {new_first['etf_name']}")
            elif H not in pool_codes or rH is None:
                reason = "掉出候选池" if H not in pool_codes else "不在过筛排序表"
                final_result = [new_first]
                g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = new_first['etf']
                t = f"{AC}立即换股({reason})：{H} → 候选池第1 {new_first['etf']} {new_first['etf_name']}"
                log_buffer.append(t)
                log.info(t)
            elif rH == 1:
                g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = H
                final_result = [candidate_dict[H]]
                t = (
                    f"{AC}持仓即为过筛动量第1名 → 继续持有 streak已清零 | "
                    f"持仓 {H} {candidate_dict[H]['etf_name']}"
                )
                log_buffer.append(t)
                log.info(t)
            else:
                if g.normal_streak_hold_code != H:
                    g.normal_not_rank1_streak = 0
                g.normal_streak_hold_code = H
                g.normal_not_rank1_streak = int(getattr(g, 'normal_not_rank1_streak', 0)) + 1
                streak = g.normal_not_rank1_streak
                log_buffer.append(
                    f"{AC}持仓在候选池内，过筛名次={rH}/第1名={rank1_etf}({rank1_name})，"
                    f"连续未登首 streak={streak}/{max_days}"
                )
                log.info(
                    f"{AC} {H} {candidate_dict[H]['etf_name']} "
                    f"名次{rH} 未登首{streak}/{max_days}天 候选池内 | 今日第1名 {rank1_etf}"
                )
                if streak >= max_days:
                    final_result = [new_first]
                    g.normal_not_rank1_streak = 0
                    g.normal_streak_hold_code = new_first['etf']
                    t = (
                        f"{AC}⭐已满{max_days}个交易日未重返第1名 → 换股为候选池第1 "
                        f"{new_first['etf']} {new_first['etf_name']}"
                    )
                    log_buffer.append(t)
                    log.info(t)
                else:
                    final_result = [candidate_dict[H]]
                    t = (
                        f"{AC}继续持有 {H} {candidate_dict[H]['etf_name']} "
                        f"（streak {streak}/{max_days}，未满不换）"
                    )
                    log_buffer.append(t)
                    log.info(t)
    else:
        # 防频换不适用，使用原有逻辑
        anti_churn_candidate_pool_empty = (
            g.holdings_num == 1
            and len(candidate_pool) == 0
            and (
                regime == '正常期'
                or (regime == '震荡期' and getattr(g, 'oscillation_anti_churn_enabled', False))
                or (regime == '走弱期' and getattr(g, 'weak_anti_churn_enabled', False))
            )
        )
        if anti_churn_candidate_pool_empty:
            g.normal_not_rank1_streak = 0
            g.normal_streak_hold_code = None
            g.normal_not_topk_streaks = {}
            msg = "【防频换】候选池为空，回退原合并逻辑，streak已清零"
            log_buffer.append(msg)
            log.info(msg)
        retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
        log_buffer.append(f"其中存在于候选池中的持仓ETF：{[item['etf'] for item in retained]}")
        if len(retained) >= g.holdings_num:
            retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
            final_result = retained_sorted[:g.holdings_num]
            log_buffer.append(f"保留的持仓ETF数量({len(retained)})超过目标持仓数({g.holdings_num})，将从保留的ETF中按动量得分取前{g.holdings_num}只作为最终目标。")
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
    # v5.1新增：Whipsaw滞回机制（避免频繁换仓）
    if getattr(g, 'enable_switch_hysteresis', False) and g.holdings_num == 1 and final_result:
        hs_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
        if hs_holdings:
            hs_current = hs_holdings[0]
            hs_target = final_result[0]['etf']
            if hs_current != hs_target:
                in_range = regime == '震荡期'
                hbuf = float(getattr(g, 'switch_buffer_range', 0.40)) if in_range else float(getattr(g, 'switch_buffer_normal', 0.10))
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
                        f"🔎 【Whipsaw·滞回】缓冲={hbuf:.0%}({'震荡期' if in_range else '正常期'}), "
                        f"要求 {score_key}(目标)>{hurdle:.4f} (=持仓{c_sc:.4f}×(1+{hbuf:.0%}))"
                    )
                    if np.isfinite(t_sc) and np.isfinite(c_sc):
                        if t_sc <= hurdle:
                            log_buffer.append(
                                f"⏸️ 【Whipsaw·滞回】拦截换仓 → 保留 {c_nm}({hs_current})"
                            )
                            if getattr(g, 'log_whipsaw_filter_detail', True):
                                log.info(
                                    f"【Whipsaw·滞回】拦截换仓: 目标 {hs_target} {score_key}={t_sc:.4f} ≤ 门槛 {hurdle:.4f} "
                                    f"(持仓 {hs_current} {score_key}={c_sc:.4f})"
                                )
                            final_result = [hs_cur_metric]
                        else:
                            log_buffer.append(f"✅ 【Whipsaw·滞回】通过: {t_nm} {score_key}={t_sc:.4f} > {hurdle:.4f}")
                    else:
                        log_buffer.append("ℹ️ 【Whipsaw·滞回】跳过: 评分非有限值")
                else:
                    log_buffer.append(f"ℹ️ 【Whipsaw·滞回】跳过: 持仓 {hs_current} 无指标记录")
    log_buffer.append(f"【最终目标】共{len(final_result)}只ETF：")
    for i, item in enumerate(final_result):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']})")
    log_buffer.append("==================================================")
    
    # v5.1原版：保存今日过滤结果和候选池信息（用于卖出原因生成）
    g.today_filtered_codes = [m.get('etf') for m in filtered_list if isinstance(m, dict) and m.get('etf')]
    g.today_filtered_rank_map = {m.get('etf'): (i + 1) for i, m in enumerate(filtered_list) if isinstance(m, dict) and m.get('etf')}
    g.today_candidate_pool_codes = [m.get('etf') for m in candidate_pool if isinstance(m, dict) and m.get('etf')]
    g.today_candidate_score_threshold = score_threshold if 'score_threshold' in locals() else None
    
    full_log = "\n".join(log_buffer)
    log.info(full_log)
    return final_result


# ==================== 交易执行 ====================
def execute_sell_trades(context):
    """卖出交易逻辑（v5.1完整版，适配多策略环境）"""
    log.info("========== 卖出操作开始 ==========")
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    
    # 适配多策略环境：根据模式选择持仓列表
    pure_wufu_mode = (g.portfolio_value_proportion == [0, 0, 1, 0])
    current_positions = (
        list(context.portfolio.positions.keys())
        if pure_wufu_mode
        else list(g.strategy_holdings[3])
    )
    current_holdings_nonzero = [
        s for s in current_positions 
        if context.portfolio.positions.get(s) and context.portfolio.positions[s].total_amount > 0
    ]
    
    target_etfs = []
    # 注意：ranked_etfs_result 是“最终目标结果”，不是候选池本身；候选池与过滤名单需单独保存
    filtered_codes_today = list(getattr(g, 'today_filtered_codes', []) or [])
    candidate_codes_today = list(getattr(g, 'today_candidate_pool_codes', []) or [])
    
    if ranked_etfs:
        g.defensive_switch_pending_streak = 0
        g.defensive_switch_last_signal_date = None
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
            log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}")
    else:
        if check_defensive_etf_available(context):
            # 防御切换确认：避免单日噪声导致立刻从风险资产切防御
            if getattr(g, 'enable_defensive_switch_confirm', False):
                today = context.current_dt.date()
                if g.defensive_switch_last_signal_date != today:
                    g.defensive_switch_pending_streak = int(getattr(g, 'defensive_switch_pending_streak', 0)) + 1
                    g.defensive_switch_last_signal_date = today
                need_days = max(1, int(getattr(g, 'defensive_switch_confirm_days', 1)))
                already_defensive = (len(current_holdings_nonzero) == 1 and current_holdings_nonzero[0] == g.defensive_etf)
                if already_defensive or g.defensive_switch_pending_streak >= need_days:
                    target_etfs = [g.defensive_etf]
                    etf_name = get_security_name(g.defensive_etf)
                    log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
                else:
                    target_etfs = current_holdings_nonzero[:]
                    log.info(
                        f"🕒 防御切换确认中：{g.defensive_switch_pending_streak}/{need_days}，"
                        f"暂不切换防御ETF，维持当前持仓"
                    )
            else:
                target_etfs = [g.defensive_etf]
                etf_name = get_security_name(g.defensive_etf)
                log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
        else:
            g.defensive_switch_pending_streak = 0
            g.defensive_switch_last_signal_date = None
            log.info("💤 无最终目标(空仓模式)")
            target_etfs = []
    
    # 非动量排行场景（防御模式 / 策略空仓）的统一卖出原因前缀
    if (not ranked_etfs) and target_etfs:
        # 无排名结果但有防御标的 → 切换到防御ETF
        etf_name = get_security_name(target_etfs[0])
        base_exit_reason = f"防御模式卖出：腾出仓位切换至防御ETF {target_etfs[0]} {etf_name}（午盘清仓）"
    elif (not ranked_etfs) and (not target_etfs):
        # 今日无任何目标 → 策略选择空仓
        base_exit_reason = "策略空仓卖出：今日无目标ETF，全部持仓午盘清仓"
    else:
        base_exit_reason = ""
    
    g.target_etfs_list = target_etfs
    target_set = set(target_etfs)
    sell_count = 0
    
    for security in current_positions:
        position = context.portfolio.positions.get(security)
        if position and position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            exit_bucket = 'other'
            exit_detail = '防御/空仓/非动量调仓'
            # 针对不同场景生成更细化的卖出原因
            if ranked_etfs:
                # 正常动量调仓场景：进一步区分几种情况
                try:
                    target_desc = ", ".join(target_etfs) if target_etfs else "无"
                except Exception:
                    target_desc = "—"
                if security not in candidate_codes_today:
                    # 1) 已不在今日候选池：要进一步区分是“被过滤掉”还是“过筛但未达候选门槛/未入Top10”
                    if security not in filtered_codes_today:
                        met = getattr(g, 'last_metrics_by_etf_code', {}).get(security)
                        fail_detail = explain_filter_failures_for_etf(security, met)
                        exit_reason = (
                            "动量调仓卖出：已被第二步过滤剔除，真实原因="
                            f"{fail_detail}；不在今日目标ETF列表（今日目标: {target_desc}），且午盘清仓"
                        )
                        exit_detail = str(fail_detail)
                        if '无指标记录' in str(fail_detail):
                            exit_bucket = 'missing_data'
                        else:
                            exit_bucket = 'filter_fail'
                    else:
                        met = getattr(g, 'last_metrics_by_etf_code', {}).get(security) or {}
                        sc = met.get('momentum_rank_score', met.get('momentum_score'))
                        rk = (getattr(g, 'today_filtered_rank_map', {}) or {}).get(security)
                        th = getattr(g, 'today_candidate_score_threshold', None)
                        if th is not None and sc is not None:
                            detail = f"通过过滤但未入候选池：排序分{sc:.4f} < 候选门槛{th:.4f}"
                        elif rk is not None:
                            detail = f"通过过滤但未入候选池：过滤后排名第{rk}（仅Top10参与候选池）"
                        else:
                            detail = "通过过滤但未入候选池：未达到候选池入选规则"
                        exit_reason = (
                            f"动量调仓卖出：{detail}；不在今日目标ETF列表（今日目标: {target_desc}），且午盘清仓"
                        )
                        exit_bucket = 'rank_lag'
                        exit_detail = detail
                else:
                    # 2) 仍在候选池，但动量排名落后，没进入前N名目标
                    exit_reason = (
                        f"动量调仓卖出：仍在今日候选池但未进入前{g.holdings_num}名目标ETF，"
                        f"今日目标: {target_desc}，且午盘清仓"
                    )
                    exit_bucket = 'rank_lag'
                    exit_detail = f"仍在候选池但未进入前{g.holdings_num}名"
            else:
                # 防御模式 / 策略空仓 等统一使用 base_exit_reason
                exit_reason = base_exit_reason or "午盘清仓"

            success = smart_order_target_value(security, 0, context, exit_reason=exit_reason)
            if success:
                sell_count += 1
                _record_exit_reason_stat(exit_bucket, exit_detail, getattr(g, 'market_regime', '未知'))
                log.info(f"✅ 已成功卖出: {security} {security_name}")
    
    log.info(f"本次共计划卖出{sell_count}只ETF。")
    log.info("========== 卖出操作完成 ==========")


def _filter_stop_loss_rebuy_cooldown(context, candidate_etfs):
    """买入候选中剔除仍在冷却内的标的（v5.1原版）"""
    if not getattr(g, 'enable_stop_loss_rebuy_cooldown', False):
        return list(candidate_etfs)
    fa_map = getattr(g, 'stop_loss_rebuy_first_allowed_date', None) or {}
    today = context.current_dt.date()
    out = []
    for c in candidate_etfs:
        fa = fa_map.get(c)
        if fa is None:
            out.append(c)
            continue
        fd = fa.date() if hasattr(fa, 'date') else fa
        if today < fd:
            log.info(
                f"⏸️ 【止损买回冷却】跳过买入 {c} {get_security_name(c)}，最早允许 {fd}"
            )
            continue
        out.append(c)
    return out


def _coerce_scalar_price(x):
    """将价格值转换为标量浮点数（处理numpy数组等情况）"""
    if x is None:
        return None
    try:
        arr = np.asarray(x, dtype=float).ravel()
        if arr.size == 0:
            return None
        return float(arr[0])
    except Exception:
        return None


def record_buy_trade_entry(context, etf_code):
    """买入成功后记录开仓快照，供卖出复盘配对。"""
    try:
        cd = get_current_data()
        px = _coerce_scalar_price(cd[etf_code].last_price) if etf_code in cd else None
        pos = context.portfolio.positions.get(etf_code)
        met = getattr(g, 'last_metrics_by_etf_code', {}).get(etf_code)
        if met is None:
            met = snapshot_momentum_for_security(context, etf_code) or {}
        g.trade_entry_open[etf_code] = {
            'code': etf_code,
            'name': get_security_name(etf_code),
            'buy_datetime': context.current_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'buy_date': str(context.current_dt.date()),
            'buy_price_last': px,
            'buy_avg_cost': float(pos.avg_cost) if pos and pos.avg_cost else None,
            'buy_amount': int(pos.total_amount) if pos else None,
            'buy_long_m': met.get('momentum_score'),
            'buy_short_m': met.get('short_momentum_score'),
            'buy_r2': met.get('r_squared'),
            'buy_regime': getattr(g, 'market_regime', ''),
            'buy_annual_ret': met.get('annualized_returns'),
        }
    except Exception as e:
        log.warning(f"【交易记录】买入快照异常 {etf_code}: {e}")


def _effective_laplace_min_slope():
    """返回当前状态应使用的拉普拉斯斜率阈值（支持正常期单独放宽）。"""
    base = float(getattr(g, 'laplace_min_slope', 0.002))
    if (
        getattr(g, 'enable_p0_state_tuning_patch', False)
        and getattr(g, 'market_regime', '震荡期') == '正常期'
    ):
        return float(getattr(g, 'normal_laplace_min_slope_override', base))
    return base


def explain_filter_failures_for_etf(etf_code, metrics=None):
    """返回该ETF在当日过滤步骤中未通过的真实原因（含阈值与数值）。"""
    try:
        m = metrics or getattr(g, 'last_metrics_by_etf_code', {}).get(etf_code)
        if not isinstance(m, dict):
            return "无指标记录"
        regime = getattr(g, 'market_regime', '震荡期')
        reasons = []

        # 1) 动量得分区间
        if not m.get('passed_momentum', True):
            sc = m.get('momentum_score')
            lo = m.get('effective_min_score_threshold')
            hi = m.get('effective_max_score_threshold')
            reasons.append(f"动量得分不在区间[{lo:.4f},{hi:.4f}] (score={sc:.4f})" if sc is not None else "动量得分不达标")

        # 2) R² 过滤（走弱期须 weak_apply_r2_filter，与 v3-1「走弱不做 R²」对齐时可置 False）
        if getattr(g, 'enable_r2_filter', False) and (
            regime != '走弱期' or getattr(g, 'weak_apply_r2_filter', False)
        ):
            if not m.get('passed_r2', True):
                r2 = m.get('r_squared')
                th = m.get('effective_r2_threshold', getattr(g, 'r2_threshold', None))
                if r2 is None or (isinstance(r2, float) and (np.isnan(r2) or np.isinf(r2))):
                    reasons.append("R²无效/缺失")
                else:
                    reasons.append(f"R²不足 (r2={float(r2):.3f} ≤ 阈值{float(th):.3f})" if th is not None else f"R²不足 (r2={float(r2):.3f})")

        # 3) 走弱期均线过滤（须 weak_apply_ma_filter）
        if (
            getattr(g, 'enable_ma_filter', False)
            and regime == '走弱期'
            and getattr(g, 'weak_apply_ma_filter', False)
        ):
            if not m.get('passed_ma', True):
                px = m.get('current_price')
                ma = m.get('ma_value')
                th = float(getattr(g, 'ma_threshold', 1.0))
                if px is not None and ma is not None:
                    reasons.append(f"均线过滤未过 (现价{px:.3f} ≤ MA×{th:.2f}={ma*th:.3f})")
                else:
                    reasons.append("均线过滤未过")

        # 4) 成交量过滤（走弱期须 weak_apply_volume_filter）
        if getattr(g, 'enable_volume_check', False) and (
            regime != '走弱期' or getattr(g, 'weak_apply_volume_filter', False)
        ):
            if not m.get('passed_volume', True):
                vr = m.get('volume_ratio')
                thr = float(m.get('effective_volume_threshold', getattr(g, 'volume_threshold', 0)))
                if vr is None:
                    reasons.append("成交量比值缺失/不可算")
                else:
                    reasons.append(f"成交量比值未过 (量比{float(vr):.2f} ≥ 阈值{thr:.2f}，需<{thr:.2f})")

        # 5) 短期风控（走弱期须 weak_apply_loss_filter）
        if getattr(g, 'enable_loss_filter', False) and (
            regime != '走弱期' or getattr(g, 'weak_apply_loss_filter', False)
        ):
            if not m.get('passed_loss', True):
                ratios = m.get('day_ratios') or []
                min_ratio = min(ratios) if ratios else None
                loss_th = float(getattr(g, 'loss', 0))
                if min_ratio is not None:
                    reasons.append(f"短期风控未过 (近3日最差日涨跌比{float(min_ratio):.4f} < 阈值{loss_th:.4f})")
                else:
                    reasons.append("短期风控未过")

        # 6) 溢价率过滤（走弱期须 weak_apply_premium_filter）
        if getattr(g, 'enable_premium_filter', False) and (
            regime != '走弱期' or getattr(g, 'weak_apply_premium_filter', False)
        ):
            if not m.get('passed_premium', True):
                pr = m.get('premium_rate')
                max_pr = float(getattr(g, 'max_premium_rate', 0))
                if pr is None:
                    reasons.append("溢价率缺失/不可算")
                else:
                    reasons.append(f"溢价率超阈值 (溢价{float(pr):.2f}% > {max_pr:.2f}%)")

        # 7) 拉普拉斯（正常期；走弱期仅当 weak_apply_laplace_filter）
        if getattr(g, 'enable_laplace_filter', False) and (
            regime == '正常期'
            or (regime == '走弱期' and getattr(g, 'weak_apply_laplace_filter', False))
        ):
            if not m.get('passed_laplace', True):
                slope = m.get('laplace_slope')
                min_s = _effective_laplace_min_slope()
                es = m.get('effective_laplace_s')
                if slope is not None:
                    suf = f", s={float(es):.4f}" if es is not None else ""
                    reasons.append(f"拉普拉斯滤波未过{suf} (斜率{slope:.4f} ≤ 最小{min_s:.4f} 或 现价≤滤波值)")
                else:
                    reasons.append("拉普拉斯滤波未过")

        # 8) 震荡期高斯
        if regime == '震荡期':
            if not m.get('passed_gaussian', True):
                slope = m.get('gaussian_slope')
                if getattr(g, 'gaussian_use_relative_slope', False):
                    min_s = float(getattr(g, 'gaussian_min_slope_relative', 0.001))
                else:
                    min_s = float(getattr(g, 'gaussian_min_slope', 0))
                if slope is not None:
                    reasons.append(f"高斯滤波未过 (斜率{slope:.4f} ≤ 最小{min_s:.4f} 或 现价≤滤波值)")
                else:
                    reasons.append("高斯滤波未过")

        # 9) 震荡期短动量区间（如启用）
        if not m.get('passed_whipsaw_short_band', True):
            sms = m.get('short_momentum_score')
            lo = m.get('effective_short_min_score_threshold')
            hi = m.get('effective_short_max_score_threshold')
            if sms is not None and lo is not None and hi is not None:
                reasons.append(f"短期动量不在区间[{lo:.4f},{hi:.4f}] (short={sms:.4f})")
            else:
                reasons.append("短期动量区间未过")

        # 10) 长短动量双正（如启用）
        if m.get('dual_positive_filter_active', False) and (not m.get('passed_dual_positive', True)):
            lm = m.get('momentum_score')
            sm = m.get('short_momentum_score')
            reasons.append(f"长短动量双正未过 (长={lm:.4f} 短={sm:.4f} 需均>0)" if lm is not None and sm is not None else "长短动量双正未过")

        return "；".join(reasons) if reasons else "通过全部过滤条件"
    except Exception:
        return "过滤原因解析失败"


def _ensure_exit_reason_stats():
    """确保卖出原因统计结构可用（兼容旧缓存字段）。"""
    if not isinstance(getattr(g, 'exit_reason_stats', None), dict):
        g.exit_reason_stats = {}
    s = g.exit_reason_stats
    s.setdefault('total', 0)
    if not isinstance(s.get('by_bucket'), dict):
        s['by_bucket'] = {}
    for k in ('missing_data', 'filter_fail', 'rank_lag', 'other'):
        s['by_bucket'].setdefault(k, 0)
    if not isinstance(s.get('by_regime'), dict):
        s['by_regime'] = {}
    if not isinstance(s.get('by_detail'), dict):
        s['by_detail'] = {}


def _record_exit_reason_stat(bucket, detail, regime):
    _ensure_exit_reason_stats()
    s = g.exit_reason_stats
    b = bucket if bucket in ('missing_data', 'filter_fail', 'rank_lag', 'other') else 'other'
    r = regime if regime in ('正常期', '震荡期', '走弱期') else '未知'
    d = detail if detail else '未细分'
    s['total'] = int(s.get('total', 0)) + 1
    s['by_bucket'][b] = int(s['by_bucket'].get(b, 0)) + 1
    by_r = s['by_regime'].setdefault(
        r, {'missing_data': 0, 'filter_fail': 0, 'rank_lag': 0, 'other': 0, 'total': 0}
    )
    by_r[b] = int(by_r.get(b, 0)) + 1
    by_r['total'] = int(by_r.get('total', 0)) + 1
    s['by_detail'][d] = int(s['by_detail'].get(d, 0)) + 1


def get_short_momentum_3day_pattern(context, security):
    """
    返回短期动量近三个交易日的方向模式（如：增增增/增减增）及三个动量值。
    价格序列为日 K（仅交易日）收盘价 + 当日当前价；三个端点为连续三个交易日递进，非自然日。
    """
    try:
        cur = _get_intraday_price_with_fallback(context, security)
        if cur is None or cur <= 0:
            return "N/A", []

        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        # 需要保证可构造「前交易日、昨交易日、今交易日(当前价)」三组短期动量输入（日 K 仅含交易日）
        bars = max(short_lb + 10, 40)
        df = attribute_history(security, bars, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < short_lb + 4:
            return "N/A", []

        hist = df['close'].values.astype(float)
        price_series = np.append(hist, cur)

        # 三个观测点：前交易日、昨交易日、今交易日（按交易日递进；最后一根为当日盘中价）
        ends = [len(price_series) - 3, len(price_series) - 2, len(price_series) - 1]
        vals = []
        for end in ends:
            sub = price_series[:end + 1]
            if len(sub) < short_lb + 1:
                vals.append(None)
                continue
            sm, _, _ = calculate_momentum_score(sub, short_lb)
            vals.append(sm)

        if len(vals) != 3 or any(v is None for v in vals):
            return "N/A", vals
        if not all(_scalar_momentum_finite(v) for v in vals):
            return "N/A", vals
        pattern = build_short_momentum_3day_pattern_str(vals)
        return pattern, vals
    except Exception:
        return "N/A", []


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
    # v5.1原版：过滤止损买回冷却
    etfs_to_buy = _filter_stop_loss_rebuy_cooldown(context, etfs_to_buy)
    actual_holding_count = len(current_strategy3_positions)
    
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    
    if num_etfs_to_buy <= 0: 
        log.info(f"五福5.1v3实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
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
    
    log.info(f"五福5.1v3可用现金: {available_cash:.2f}, 分配给每只ETF的资金: {allocated_value_per_etf:.2f}")
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
            
        success = smart_order_target_value(etf, target_value_for_this_etf, context, exit_reason='策略买入')
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
            record_buy_trade_entry(context, etf)  # v5.1新增：记录买入快照
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
            success = smart_order_target_value(security, 0, context, exit_reason='分钟级固定止损')
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
            success = smart_order_target_value(security, 0, context, exit_reason='分钟级跌幅止损')
            if success and g.enable_stop_loss_trigger:
                g.stop_loss_triggered_today = True
                log.info(f"✅ 【止损触发】记录今日止损，将在13:10检查并进入震荡期")


def record_etf_roundtrip_on_sell(context, security, sold_amount, avg_cost_before, sell_price, exit_reason):
    """清仓后：复盘日志 + 写入 trade_roundtrip_history。"""
    name = get_security_name(security)
    entry = getattr(g, 'trade_entry_open', {}).pop(security, None) or {}
    sell_snap = snapshot_momentum_for_security(context, security) or {}
    sell_fee = 0.0001
    cost_basis = sold_amount * avg_cost_before if avg_cost_before and sold_amount else 0.0
    proceeds = sold_amount * sell_price * (1.0 - sell_fee) if sold_amount and sell_price else 0.0
    pnl_abs = proceeds - cost_basis
    pnl_pct = (pnl_abs / cost_basis * 100.0) if cost_basis > 1e-9 else float('nan')

    buy_dt = entry.get('buy_datetime', '—')
    sell_dt = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    bl = entry.get('buy_long_m')
    bs = entry.get('buy_short_m')
    sl = sell_snap.get('momentum_score')
    ss = sell_snap.get('short_momentum_score')
    # 年化收益等额外参数（便于卖出复盘）
    buy_annual_ret = entry.get('buy_annual_ret')
    sell_annual_ret = sell_snap.get('annualized_returns')
    sell_short_annual_ret = sell_snap.get('short_annualized_returns')
    sell_sm_pattern, sell_sm_vals = get_short_momentum_3day_pattern(context, security)
    if sell_sm_pattern == "N/A" and isinstance(sell_sm_vals, (list, tuple)) and len(sell_sm_vals) == 3:
        if all(_scalar_momentum_finite(v) for v in sell_sm_vals):
            _fix_pat = build_short_momentum_3day_pattern_str(sell_sm_vals)
            if _fix_pat != "N/A":
                sell_sm_pattern = _fix_pat

    # 短动量近三个交易日连续走强（与 get_short_momentum_3day_pattern 中「增增增」一致）→ 下一交易日 13:10 复盘区间收益
    if sell_sm_pattern == "增增增":
        fu = _first_trading_day_after(context.current_dt.date())
        if fu:
            g.pending_sm3up_sell_followups.append({
                'code': security,
                'name': name,
                'sell_date': str(context.current_dt.date()),
                'sell_price_1310': float(sell_price),
                'followup_date': fu,
                'exit_reason': exit_reason,
            })
            log.info(
                f"【短动量三连涨卖出】{name}({security}) 已纳入下一交易日 13:10 区间收益跟踪 "
                f"(卖价≈{float(sell_price):.4f} 复盘日={fu})"
            )

    rec = {
        'code': security,
        'name': name,
        'buy_datetime': buy_dt,
        'sell_datetime': sell_dt,
        'buy_date': entry.get('buy_date', ''),
        'exit_reason': exit_reason,
        'buy_long_m': bl,
        'buy_short_m': bs,
        'sell_long_m': sl,
        'sell_short_m': ss,
        'buy_r2': entry.get('buy_r2'),
        'sell_r2': sell_snap.get('r_squared'),
        'buy_regime': entry.get('buy_regime'),
        'sell_regime': sell_snap.get('market_regime', getattr(g, 'market_regime', '')),
        'buy_annual_ret': buy_annual_ret,
        'sell_annual_ret': sell_annual_ret,
        'sell_short_annual_ret': sell_short_annual_ret,
        'avg_cost': avg_cost_before,
        'sell_price': sell_price,
        'sold_amount': sold_amount,
        'pnl_abs': pnl_abs,
        'pnl_pct': pnl_pct,
    }
    if not hasattr(g, 'trade_roundtrip_history'):
        g.trade_roundtrip_history = []
    g.trade_roundtrip_history.append(rec)

    def _fmt_m(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return 'N/A'
        return f"{float(v):.4f}"

    def _fmt_pct(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return 'N/A'
        return f"{float(v) * 100:.2f}%"

    def _fmt_3vals(vals):
        if not vals or len(vals) != 3:
            return "N/A"
        out = []
        for v in vals:
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                out.append("N/A")
            else:
                out.append(f"{float(v):.4f}")
        return " -> ".join(out)

    def _label_sm_pattern(pattern):
        """将短动量模式粗略归类为：持续走强 / 持续走弱 / 震荡。"""
        if not pattern or pattern == "N/A":
            return "未知"
        # 典型强/弱趋势：全增或全减
        if pattern.count("增") == len(pattern) and "增" in pattern:
            return "持续走强"
        if pattern.count("减") == len(pattern) and "减" in pattern:
            return "持续走弱"
        # 其他混合情况统一视为震荡
        return "震荡"

    # 当天计划买入的目标标的（用于对比：卖出标的 vs 今日买入标的）
    target_lines = []
    try:
        today_targets = list(getattr(g, 'target_etfs_list', []) or [])
    except Exception:
        today_targets = []
    if today_targets:
        ranked = getattr(g, 'ranked_etfs_result', []) or []
        ranked_map = {}
        try:
            ranked_map = {m.get('etf'): m for m in ranked if isinstance(m, dict) and m.get('etf')}
        except Exception:
            ranked_map = {}
        for t in today_targets[:max(1, int(getattr(g, 'holdings_num', 1)))]:
            t_name = get_security_name(t)
            met = ranked_map.get(t) or getattr(g, 'last_metrics_by_etf_code', {}).get(t)
            if met is None:
                met = snapshot_momentum_for_security(context, t) or {}
            # 兼容两种键名：momentum_score / short_momentum_score 与 sell_xxx 使用的 annualized_returns / r_squared
            t_lm = met.get('momentum_score')
            t_sm = met.get('short_momentum_score')
            t_r2 = met.get('r_squared')
            t_ar = met.get('annualized_returns')
            t_sar = met.get('short_annualized_returns')
            t_reg = met.get('market_regime', getattr(g, 'market_regime', ''))
            t_sm_pattern, t_sm_vals = get_short_momentum_3day_pattern(context, t)
            if t_sm_pattern == "N/A" and isinstance(t_sm_vals, (list, tuple)) and len(t_sm_vals) == 3:
                if all(_scalar_momentum_finite(v) for v in t_sm_vals):
                    _tp = build_short_momentum_3day_pattern_str(t_sm_vals)
                    if _tp != "N/A":
                        t_sm_pattern = _tp
            target_lines.append(
                f"  今日买入标的(目标): {t_name}({t})  |  长动量={_fmt_m(t_lm)}  短动量={_fmt_m(t_sm)}  "
                f"R²={_fmt_m(t_r2)}  市场状态={t_reg or '—'}  年化≈{_fmt_pct(t_ar)}  短期年化≈{_fmt_pct(t_sar)}  "
                f"短动量近三日(均为交易日)={t_sm_pattern} [{_label_sm_pattern(t_sm_pattern)}] "
                f"({_fmt_3vals(t_sm_vals)})"
            )
    else:
        target_lines.append("  今日买入标的(目标): 无（空仓/无目标）")

    log.info(
        f"\n{'=' * 72}\n"
        f"📋 【卖出复盘】{name}({security})  |  原因: {exit_reason}  |  卖出市场状态: {rec['sell_regime']}\n"
        f"  买入时间: {buy_dt}  →  卖出时间: {sell_dt}\n"
        f"  买入时 长动量={_fmt_m(bl)}  短动量={_fmt_m(bs)}  R²={_fmt_m(entry.get('buy_r2'))}  市场状态={entry.get('buy_regime', '—')}\n"
        f"  卖出时 长动量={_fmt_m(sl)}  短动量={_fmt_m(ss)}  R²={_fmt_m(sell_snap.get('r_squared'))}  市场状态={rec['sell_regime']}\n"
        f"  卖出标的短动量近三日(均为交易日): {sell_sm_pattern} [{_label_sm_pattern(sell_sm_pattern)}] "
        f"({_fmt_3vals(sell_sm_vals)})\n"
        f"{chr(10).join(target_lines)}\n"
        f"  买入时 年化收益≈{_fmt_pct(buy_annual_ret)}  卖出时 年化收益≈{_fmt_pct(sell_annual_ret)}  卖出时 短期年化≈{_fmt_pct(sell_short_annual_ret)}\n"
        f"  数量={sold_amount:.0f}  成本均价≈{avg_cost_before:.4f}  卖出价≈{sell_price:.4f}\n"
        f"  本次估算盈亏: {pnl_abs:,.2f} 元 ({pnl_pct:.2f}%)\n"
        f"  单次往返收益总结: 代码={security}, 名称={name}, 收益={pnl_abs:,.2f}元, 收益率={pnl_pct:.2f}%, "
        f"原因={exit_reason}, 买入状态={entry.get('buy_regime', '—')}, 卖出状态={rec['sell_regime']}, "
        f"买入长/短动量={_fmt_m(bl)}/{_fmt_m(bs)}, 卖出长/短动量={_fmt_m(sl)}/{_fmt_m(ss)}\n"
        f"{'=' * 72}"
    )


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
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
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
    g.huanshou_check = False  # 放量换手检测
    g.xsz_version = "v3"  # 固定使用v3版本
    g.enable_dynamic_stock_num = True  # 启用动态选股数量 3~6
    g.xsz_stock_num = 5  # 默认持股数量
    g.yesterday_HL_list = []  # 昨日涨停股票
    g.target_list = []  # 目标持仓股票
    g.xsz_buy_etf = "511880.XSHG"  # 空仓时购买ETF
    
    # 止损检查
    g.run_stoploss = True  # 是否进行止损
    g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
    g.stoploss_limit = 0.09  # 止损线
    g.stoploss_market = 0.05  # 市场趋势止损参数
    
    # 顶背离检查
    g.DBL_control = True  # 小市值大盘顶背离记录
    g.dbl = []
    g.check_dbl_days = 10  # 顶背离检测窗口期
    
    # 异常处理窗口期检查
    g.check_after_no_buy = False  # 检查后不再买入时间
    g.no_buy_stocks = {}  # 检查卖出的股票
    g.no_buy_after_day = 3  # 止损后不买入的时间窗口
    
    # 成交额宽度检查（默认关闭，如需开启可设为True）
    g.check_defense = False
    g.industries = ["组20"]
    g.defense_signal = None
    g.cnt_defense_signal = []
    g.cnt_bank_signal = []
    g.history_defense_date_list = []

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

    """ 策略3 《五福5.1v3》五福闹新春（与五福5.1v3.py 同源，setup_wufu35_globals） """
    if g.portfolio_value_proportion[2] > 0:
        setup_wufu35_globals()
    if g.portfolio_value_proportion[0] > 0 and g.portfolio_value_proportion[2] > 0:
        if g.xsz_buy_etf == getattr(g, "defensive_etf", None):
            log.warn(
                f"[策略冲突] 策略1空仓ETF({g.xsz_buy_etf})与五福5.1v3防御ETF重复，"
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

    # v5.1原版：根据模式选择基准
    pure_wufu_mode = (g.portfolio_value_proportion == [0, 0, 1, 0])
    if pure_wufu_mode:
        set_benchmark("510300.XSHG")
    else:
        # 小市值策略原版使用沪深300指数作为基准
        set_benchmark("000300.XSHG")
    
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
                    hit_reasons.append("高危资产(商誉占净资��>30%)")
                    
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


""" ====================== 指数趋势条件判断函数（仅1/4月生效） ======================"""

def check_market_condition(context):
    """
    【仅1月、4月生效】判断市场是否满足交易条件：
    沪深300、中证500、中证1000的5天、20天均上涨，且5天涨幅 > 20天涨幅
    其他月份直接返回True，不做指数判断，正常交易
    """
    # 第一步：先判断当前月份，非1月、4月直接允许交易
    current_month = context.current_dt.month
    if current_month not in [1, 4]:
        log.info(f"✅ 当前为{current_month}月，不触发指数空仓判断，正常执行小市值交易")
        return True
    
    # 仅1月、4月执行以下指数共振判断
    log.info(f"⚠️ 当前为{current_month}月，启动指数共振交易条件校验")
    # 定义需要检查的指数列表
    index_list = [
        '000300.XSHG',  # 沪深300
        '000905.XSHG',  # 中证500
        '000852.XSHG'   # 中证1000
    ]
    
    # 获取前一交易日（避免使用未来数据）
    end_date = context.previous_date
    # 需要获取21天数据（计算20天涨幅需要21个收盘价）
    count = 21
    
    try:
        # 批量获取三个指数的收盘价数据
        price_data = get_price(
            index_list,
            end_date=end_date,
            count=count,
            frequency='daily',
            fields=['close'],
            panel=False
        )
        
        # 遍历检查每个指数
        for index_code in index_list:
            # 提取当前指数的收盘价序列
            index_prices = price_data[price_data['code'] == index_code]['close'].values
            
            if len(index_prices) < count:
                log.warn(f"⚠️ {index_code} 数据不足，保守进入空仓")
                return False
            
            # 计算近5天涨幅（(最新价 - 5天前价) / 5天前价）
            ret_5 = (index_prices[-1] - index_prices[-5]) / index_prices[-5]
            # 计算近20天涨幅
            ret_20 = (index_prices[-1] - index_prices[-20]) / index_prices[-20]
            
            # 打印指数趋势信息（方便调试回测）
            index_name = get_security_info(index_code).display_name
            log.info(f"📊 {index_name}: 近5天涨幅 {ret_5:.2%}, 近20天涨幅 {ret_20:.2%}")
            
            # 检查条件：5天涨>0，20天涨>0，5天涨>20天涨
            if not (ret_5 > 0 and ret_20 > 0 and ret_5 > ret_20):
                log.warn(f"❌ {index_name} 不满足趋势条件，{current_month}月进入空仓")
                return False
        
        # 所有指数都满足条件
        log.info(f"✅ 所有指数满足趋势条件，{current_month}月可以进行小市值交易")
        return True
        
    except Exception as e:
        log.warn(f"⚠️ 指数趋势判断出错: {e}，{current_month}月保守进入空仓")
        return False


""" ====================== 策略1: 小市值v3核心逻辑 ======================"""

def get_small_cap_stocks_v3(context):
    initial_list = filter_stocks(context, get_index_stocks('399101.XSHE'))

    q = query(
        valuation.code,
        valuation.market_cap,
        income.net_profit,
        income.operating_revenue
    ).filter(
        valuation.code.in_(initial_list),
        valuation.day == context.previous_date,  # 新增：使用前一交易日估值
        valuation.market_cap.between(10, 100),
        income.operating_revenue > 1e8,
        indicator.roe > 0,
        indicator.roa > 0,
        income.net_profit > 2000000,
    ).order_by(valuation.market_cap.asc()).limit(g.xsz_stock_num * 5)
    candidate_list = list(get_fundamentals(q, date=context.previous_date).code)
    
    current_date = context.current_dt.date()
    
    # =========================================================
    # ==== 【新增优化】：时间开关，2025年1月之前不启用该排雷逻辑 ====
    # =========================================================
    start_audit_date = datetime.date(2025, 1, 1)
    
    if current_date >= start_audit_date:
        log.info(f"📅 当前日期{current_date}已达到2025-01-01，启用九项年报排雷系统")
        audited_list = apply_nine_point_audit(context, candidate_list)
    else:
        log.info(f"📅 当前日期{current_date}早于2025-01-01，使用基础审计意见过滤")
        audited_list = filter_audit(context, candidate_list)
        
    final_list = bonus_filter(context, audited_list)
	
    # ==== 【新增代码】在此处加入止损冷却过滤 ====
    final_list = filter_cooldown_stocks(context, final_list)
    # ==========================================	
    
    if not final_list:
        return [g.xsz_buy_etf]
        
    last_prices = history(1, unit='1d', field='close', security_list=final_list)
    return final_list


	
	
	

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
    # 核心修改：仅1/4月执行指数条件判断，其他月份直接允许交易
    g.trading_signal = check_market_condition(context)
    
    g.yesterday_HL_list = []
    # 获取昨日涨停列表
    if g.strategy_holdings[1]:
        df = get_price(g.strategy_holdings[1],
                       end_date=context.previous_date,
                       fields=['close', 'high_limit', 'low_limit'],
                       frequency='daily',
                       count=1,
                       panel=False,
                       fill_paused=False)
        g.yesterday_HL_list = list(df[df['close'] == df['high_limit']].code)


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
    print("-" * 45 + f"{str(context.current_dt.date())}" + "-" * 45)
    g.target_list = []
    
    # 顶背离信号检测（原逻辑完全保留）
    if g.DBL_control:
        if len(g.dbl) < 10:
            for i in range(9, -1, -1):
                check_dbl(context, end_days=0 - i)
    if g.DBL_control and 1 in g.dbl[-g.check_dbl_days:]:
        print(f"近{g.check_dbl_days}日检测到大盘顶背离，暂停调仓以控制风险")
        return

    # 交易信号判断（完全由prepare_xsz的指数条件+月份控制）
    if not g.trading_signal:
        return

    # 成交额宽度检查（原逻辑完全保留）
    if g.check_defense and g.defense_signal:
        print("触发成交额宽度检查信号，暂停调仓以控制风险")
        return

    # 动态调整选股数量（原逻辑完全保留）
    diff = None
    if g.enable_dynamic_stock_num:
        ma_para = 10
        today = context.previous_date
        start_date = today - timedelta(days=ma_para * 2)
        index_df = get_price('399101.XSHE', start_date=start_date, end_date=today, frequency='daily')
        index_df['ma'] = index_df['close'].rolling(window=ma_para).mean()
        last_row = index_df.iloc[-1]
        diff = last_row['close'] - last_row['ma']
        g.xsz_stock_num = 3 if diff >= 500 else \
            3 if 200 <= diff < 500 else \
                4 if -200 <= diff < 200 else \
                    5 if -500 <= diff < -200 else \
                        6
    
    # 使用v3选股（原逻辑完全保留）
    g.target_list = get_small_cap_stocks_v3(context)[:g.xsz_stock_num]
    print(f'小市值v3 目标持股数: {g.xsz_stock_num} [diff:{str(diff)[:6]}] 目标持仓: {g.target_list}')

    # 卖出不在目标列表中的股票（除昨日涨停股，原逻辑完全保留）
    sell_list = [s for s in g.strategy_holdings[1] if s not in g.target_list and s not in g.yesterday_HL_list]
    hold_list = [s for s in g.strategy_holdings[1] if s in g.target_list or s in g.yesterday_HL_list]

    if sell_list:
        hold_list and print("当前持有 %s" % ([format_stock_code(stock) for stock in hold_list]))
        sell_list and print("计划卖出 %s" % ([format_stock_code(stock) for stock in sell_list]))
    for stock in sell_list:
        close_position(context, stock)


def strategy_1_buy(context):
    if not g.trading_signal:
        if g.xsz_buy_etf not in context.portfolio.positions:
            print("小市值空仓时期, 买入ETF")
            open_position(context, g.xsz_buy_etf, context.portfolio.total_value * g.portfolio_value_proportion[0], 1)
        return

    # 计算可用资金（原逻辑完全保留）
    strategy_value = context.portfolio.total_value * g.portfolio_value_proportion[0]
    current_value = sum(
        [pos.value for pos in context.portfolio.positions.values() if pos.security in g.strategy_holdings[1]])
    available_cash = max(0, strategy_value - current_value)

    # 买入新标的（原逻辑完全保留）
    buy_list = [s for s in g.target_list if s not in g.strategy_holdings[1][:]]
    if buy_list and available_cash > 0:
        cash_per_stock = available_cash / len(buy_list)
        for stock in buy_list:
            open_position(context, stock, cash_per_stock, 1)


def close_account(context):
    if not g.trading_signal:
        if g.strategy_holdings[1] and g.xsz_buy_etf not in g.strategy_holdings[1]:
            for stock in g.strategy_holdings[1][:]:
                print(f"🤕🤕🤕 进入空仓期间 卖出 {format_stock_code(stock)}")
                close_position(context, stock)


# 检查昨日涨停股今日表现
def check_small_cap_limit_up(context):
    holdings = g.strategy_holdings[1][:]
    if holdings and g.yesterday_HL_list:
        now_time = context.current_dt
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'],
                                     skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                print(f"🥵🥵🥵 {format_stock_code(stock)} 涨停打开，卖出")
                close_position(context, stock)
            else:
                print(f"🤗🤗🤗 {stock} 继续涨停，继续持有")


def _release_cash_for_small_cap(context, required_cash):
    """保留兼容入口：多策略模式下禁止策略1动用策略3资金。"""
    return 0


# 止盈止损
def sell_small_cap_stocks(context):
    if g.run_stoploss:
        current_positions = context.portfolio.positions
        # 个股止盈止损
        if g.stoploss_strategy in [1, 3]:
            for stock in current_positions.keys():
                if stock in g.strategy_holdings[1]:
                    price = current_positions[stock].price
                    avg_cost = current_positions[stock].avg_cost
                    # 收益100%止盈
                    if price >= avg_cost * 2:
                        print(f"🤑🤑🤑 收益100%止盈,卖出 {format_stock_code(stock)}")
                        close_position(context, stock)
                    # 止损线止损
                    elif price < avg_cost * (1 - g.stoploss_limit):
                        print(f"🤬🤬🤬 收益止损,卖出 {format_stock_code(stock)}")
                        close_position(context, stock)
        # 市场大跌止损
        if g.stoploss_strategy in [2, 3]:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'),
                                 end_date=context.previous_date,
                                 frequency='daily',
                                 fields=['close', 'open'],
                                 count=1,
                                 panel=False)
            down_ratio = abs((stock_df['close'] / stock_df['open'] - 1).mean())
            if down_ratio >= g.stoploss_market:
                print(f"🤡🤡🤡 大盘惨跌,平均降幅 {down_ratio:.2%}")
                for stock in g.strategy_holdings[1][:]:
                    close_position(context, stock)


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
# 大盘顶背离检测
def check_dbl(context, market_index='399101.XSHE', end_days=0):
    if not g.dbl and "9:31" in str(context.current_dt.time()):
        return

    def detect_divergence():
        fast, slow, sign = 12, 26, 9
        rows = (fast + slow + sign) * 5
        grid = attribute_history(market_index, rows + 10, fields=['close']).dropna()
        if end_days < 0:
            grid = grid.iloc[:end_days]
        if len(grid) < rows:
            return False

        try:
            grid['dif'], grid['dea'], grid['macd'] = mcad(grid.close, fast, slow, sign)
            mask = (grid['macd'] < 0) & (grid['macd'].shift(1) >= 0)
            if mask.sum() < 2:
                return False
            key2, key1 = mask[mask].index[-2], mask[mask].index[-1]

            price_cond = grid.close[key2] < grid.close[key1]
            dif_cond = grid.dif[key2] > grid.dif[key1] > 0
            macd_cond = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]

            if len(grid['dif']) > 20:
                recent_avg = grid['dif'].iloc[-10:].mean()
                prev_avg = grid['dif'].iloc[-20:-10].mean()
                trend_cond = recent_avg < prev_avg
            else:
                trend_cond = False
            return price_cond and dif_cond and macd_cond and trend_cond
        except Exception as e:
            print(f"{market_index} 顶背离检测错误: {e}")
            return False

    if detect_divergence():
        g.dbl.append(1)
        print(f"⚠️⚠️⚠️⚠️⚠️ 检测到{market_index}顶背离信号，清仓非涨停股票")
        current_data = get_current_data()
        for stock in g.strategy_holdings[1][:]:
            if current_data[stock].last_price < current_data[stock].high_limit:
                print(f"{stock} 因大盘顶背离清仓（非涨停股）")
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
    log.info(f"[五福5.1v3] 正在批量加载 {len(etf_pool)} 个ETF的历史数据（{days}天）...")
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
            log.error(f"[五福5.1v3] 加载{etf}数据失败: {e}")
            continue

    log.info(f"[五福5.1v3] 数据加载完成，成功加载 {len(data_cache)} 个ETF的数据")
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
    log.debug("[五福5.1v3] 计算动量得分" + "*" * 60)

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
            log.error(f"[五福5.1v3] 计算{code}动量得分失败: {e}")
            scores_data.loc[code, "score"] = 0

    valid_etfs = scores_data[
        (scores_data["score"] > ll) & (scores_data["score"] < hh)
    ].sort_values("score", ascending=False)
    rank_list = valid_etfs.index.tolist()
    if show_print and rank_list:
        for i in rank_list:
            log.debug(f"[五福5.1v3] {format_stock_code(i)} ({print_info[i]:.4f})")
    return rank_list


def _sub_account_structure_ok():
    sa = getattr(g, "sub_account", None)
    if not isinstance(sa, dict):
        return False
    for i in range(1, 5):
        row = sa.get(i)
        if not isinstance(row, dict):
            return False
        for k in ("initial_capital", "cash", "total_value"):
            if k not in row:
                return False
    return True


def _ensure_make_record_globals(context):
    """
    模拟盘热更新 / 恢复会话后，g 可能不完整；补齐 make_record 依赖字段，避免 AttributeError。
    不调用完整 set_params，以免清空 stock_strategy、strategy_holdings 等运行时状态。
    """
    pv = getattr(g, "portfolio_value_proportion", None)
    pv_ok = isinstance(pv, (list, tuple)) and len(pv) >= 4

    need = (
        not _sub_account_structure_ok()
        or getattr(g, "strategy_value_data", None) is None
        or not pv_ok
        or getattr(g, "strategy_holdings", None) is None
    )
    if not need:
        return

    log.warning(
        "[make_record] 子账户相关全局缺失或损坏，已按当前参数与总资产重建虚拟子账户（热更新兜底）。"
    )
    if not pv_ok:
        g.portfolio_value_proportion = [0.5, 0, 0.5, 0]
    if getattr(g, "starting_cash", None) is None:
        g.starting_cash = context.portfolio.total_value
    if getattr(g, "strategy_holdings", None) is None:
        g.strategy_holdings = {1: [], 2: [], 3: [], 4: []}
    if getattr(g, "strategy_value_data", None) is None:
        g.strategy_value_data = {1: 0, 2: 0, 3: 0, 4: 0}

    g.sub_account = {}
    for i in range(1, 5):
        initial_capital = float(g.starting_cash) * float(
            g.portfolio_value_proportion[i - 1]
        )
        g.sub_account[i] = {
            "initial_capital": initial_capital,
            "cash": initial_capital,
            "total_value": initial_capital,
        }
    g.xsz_pnl_realized_cumulative = float(
        getattr(g, "xsz_pnl_realized_cumulative", 0.0)
    )


# 尾盘记录各个策略的收益
def make_record(context):
    _ensure_make_record_globals(context)
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
                record(五福5_1v3=round(returns, 2))
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
                "五福5.1v3",
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


# 五福5.1v3日内止损检测
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
        # 5月分支：筛选当年发布的分红预案（正确逻辑，无reprot_date变量）
        q = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.company_name,
            finance.STK_XR_XD.board_plan_pub_date,
            finance.STK_XR_XD.bonus_amount_rmb,
            finance.STK_XR_XD.bonus_ratio_rmb,
        ).filter(
            finance.STK_XR_XD.board_plan_pub_date > start_date,
            finance.STK_XR_XD.board_plan_pub_date <= end_date,  # 新增：预案必须已发布
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
        # 非5月分支：筛选上一年度不分配不转增的股票（reprot_date仅在此处定义）
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
            finance.STK_XR_XD.board_plan_pub_date <= end_date,  # 新增：预案必须已发布
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
    """资金已经完全隔离进入4个独��子账户，无需再做动态转移"""
    pass


# ==================== 五福v5.1 三态市场判断核心函数 ====================

def resolve_market_regime(context):
    """三态判定（六指数）：①below_ma20 计数≥weak_min→走弱；②否则 above_ma10≥normal_min→正常；③其余→震荡。
    生效状态切换：指标与生效不一致时，需连续 regime_switch_confirm_days 个交易日指标口径一致才切换。"""
    # 中证2000 官方为 932000；聚宽 convert_security 报「找不到标的」，故第六条改用国证2000 399303.XSHE（小盘广度近似）。
    indexes = {
        '沪深300': '000300.XSHG',
        '深证综指(399101)': '399101.XSHE',
        '创业板': '399006.XSHE',
        '中证A500': '000510.XSHG',
        '中证1000': '000852.XSHG',
        '国证2000(代中证2000)': '399303.XSHE',
    }
    n_index = len(indexes)
    bars_need = max(g.regime_ma20_lookback, g.normal_ma_lookback) + 1
    below_ma20 = 0
    above_ma10 = 0
    n_ok = 0
    log_details = bool(getattr(g, 'log_market_status_details', False))
    for name, code in indexes.items():
        df = attribute_history(code, bars_need, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < g.regime_ma20_lookback:
            if log_details:
                log.warning(f"📊 【市场状态】{name}({code})数据不足，跳过")
            continue
        cur = df['close'][-1]
        ma10 = df['close'][-g.normal_ma_lookback:].mean()
        ma20 = df['close'][-g.regime_ma20_lookback:].mean()
        if cur < ma20:
            below_ma20 += 1
        if cur > ma10:
            above_ma10 += 1
        n_ok += 1
        st_m10 = "⬆️" if cur > ma10 else ("⬇️" if cur < ma10 else "➡️")
        st_m20 = "⬇️" if cur < ma20 else ("⬆️" if cur > ma20 else "➡️")
        if log_details:
            log.info(
                f"📊 【市场状态】{name}({code}): 收盘{cur:.2f} / MA{g.normal_ma_lookback}={ma10:.2f}{st_m10} "
                f"/ MA{g.regime_ma20_lookback}={ma20:.2f}{st_m20}"
            )
    weak_min = int(getattr(g, 'regime_weak_below_ma20_min', 6))
    normal_min = int(getattr(g, 'regime_normal_above_ma10_min', 3))
    if n_ok < n_index:
        raw_regime = '震荡期'
        if log_details:
            log.warning(f"📊 【市场状态】六指数未齐({n_ok}/{n_index})，指标口径默认震荡期")
    elif below_ma20 >= weak_min:
        raw_regime = '走弱期'
    elif above_ma10 >= normal_min:
        raw_regime = '正常期'
    else:
        raw_regime = '震荡期'

    today = context.current_dt.date()
    effective_before = getattr(g, 'market_regime', '震荡期')
    last_change = getattr(g, 'regime_last_change_date', None)
    n_need = int(getattr(g, 'regime_switch_confirm_days', 2))
    if n_need < 1:
        n_need = 1

    log.info(
        f"📊 【市场状态·指标】below_ma20={below_ma20}/{n_ok} (走弱阈值≥{weak_min}), "
        f"above_ma10={above_ma10}/{n_ok} (正常阈值≥{normal_min}) → 【{raw_regime}】"
    )

    if last_change is None:
        g.market_regime = raw_regime
        g.regime_last_change_date = today
        g.is_a_share_weak = raw_regime == '走弱期'
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
        log.info(f"📌 【状态切换】回测首日/首次：生效【{g.market_regime}】")
    elif raw_regime == effective_before:
        g.market_regime = raw_regime
        g.is_a_share_weak = raw_regime == '走弱期'
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
    elif n_need <= 1:
        g.market_regime = raw_regime
        g.regime_last_change_date = today
        g.is_a_share_weak = raw_regime == '走弱期'
        g.regime_switch_pending_raw = None
        g.regime_switch_pending_streak = 0
        log.info(f"✅ 【状态切换】确认天数=1，指标切换立即生效 【{effective_before}】→【{raw_regime}】")
    else:
        pending = getattr(g, 'regime_switch_pending_raw', None)
        streak = int(getattr(g, 'regime_switch_pending_streak', 0))
        if pending == raw_regime:
            streak += 1
            g.regime_switch_pending_streak = streak
            g.regime_switch_pending_raw = raw_regime
        else:
            streak = 1
            g.regime_switch_pending_streak = 1
            g.regime_switch_pending_raw = raw_regime
            log.info(
                f"🔔 【状态切换·待确认】指标【{raw_regime}】≠ 生效【{effective_before}】，"
                f"已连续 1/{n_need} 个交易日为该指标（需连续{n_need}日一致才切换）"
            )
        if streak >= n_need:
            g.market_regime = raw_regime
            g.regime_last_change_date = today
            g.is_a_share_weak = raw_regime == '走弱期'
            g.regime_switch_pending_raw = None
            g.regime_switch_pending_streak = 0
            log.info(
                f"✅ 【状态切换·已确认】指标连续{streak}个交易日为【{raw_regime}】，"
                f"生效切换 【{effective_before}】→【{raw_regime}】"
            )
        else:
            g.market_regime = effective_before
            g.is_a_share_weak = effective_before == '走弱期'
            log.info(
                f"⏳ 【状态切换·待确认】指标【{raw_regime}】，生效仍为【{effective_before}】"
                f"（进度 {streak}/{n_need} 个交易日）"
            )

    log.info(f"📊 【市场状态·生效】→ 【{g.market_regime}】")
    record(
        正常期标记=1 if g.market_regime == '正常期' else 0,
        震荡期标记=1 if g.market_regime == '震荡期' else 0,
        走弱期标记=1 if g.market_regime == '走弱期' else 0,
    )
    log_regime_transition_chain(context)
    return g.market_regime


def log_regime_transition_chain(context):
    """打印相邻交易日状态切换；检测「隔日跳回」如 正常→震荡→正常。"""
    new = g.market_regime
    day_str = context.current_dt.strftime('%Y-%m-%d')
    prev = getattr(g, 'regime_prev_day', None)
    prev2 = getattr(g, 'regime_prev_prev_day', None)

    if prev is not None and prev2 is not None:
        if new == prev2 and new != prev:
            if not hasattr(g, 'regime_flip_flop_count'):
                g.regime_flip_flop_count = 0
            g.regime_flip_flop_count = int(g.regime_flip_flop_count) + 1
            n = g.regime_flip_flop_count
            log.info(
                f"🔀 【状态反复·隔日跳回】第{n}次（回测累计）{day_str}: {prev2} → {prev} → {new} "
                f"（首尾同为【{new}】，中间为【{prev}】）"
            )

    if prev is not None:
        if new != prev:
            log.info(f"🔁 【状态切换】{day_str}: {prev} → {new}")
        else:
            log.info(f"⏺ 【状态延续】{day_str}: 连续【{new}】")
    else:
        log.info(f"📌 【状态首日】{day_str}: 【{new}】")

    g.regime_prev_prev_day = prev
    g.regime_prev_day = new


def check_weak_period_daily(context):
    """每日早盘09:40执行：判定市场状态并更新ETF池"""
    resolve_market_regime(context)
    midday_routine(context)


def drawdown_monitor_routine(context):
    """组合回撤监控：在连续竞价后执行，用场内 last_price 估值"""
    log.info("★" * 40)
    log.info(f"▶️ 【回撤监控·盘中】{context.current_dt.strftime('%H:%M')} 启动…")
    monitor_drawdown(context)
    log.info("⏸️ 【回撤监控·盘中】执行完毕！")


# ==================== 五福v5.1 ETF池管理函数 ====================

def calculate_global_etf_threshold(context):
    """计算全市场ETF流动性门槛"""
    if getattr(g, 'log_pool_update_details', False):
        log.info("【全局阈值更新】开始计算全市场ETF流动性门槛")
    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            log.warning("未找到任何场内ETF，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        if getattr(g, 'log_pool_update_details', False):
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
        if getattr(g, 'log_pool_update_details', False):
            for day, money in daily_totals.items():
                count = daily_counts.get(day, 0)
                log.info(f"  {day.date()} 全市场ETF总成交额: {money/1e8:.2f}亿元 ({count}只ETF有成交)")
        if len(daily_totals) < 3:
            log.warning(f"仅有{len(daily_totals)}个有效交易日，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        avg_total_money = daily_totals.mean()
        div = float(getattr(g, 'global_liquidity_threshold_divisor', 20000))
        if div <= 0:
            div = 20000
        threshold = avg_total_money / div
        g.avg_etf_money_threshold = threshold
        if getattr(g, 'log_pool_update_details', False):
            log.info(
                f"【全局阈值更新完成】近{len(daily_totals)}日全市场ETF日均总成交额={avg_total_money/1e8:.2f}亿元，"
                f"分母={div:g}，阈值={threshold/1e4:.0f}万元({threshold:,.0f}元)"
            )
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}，使用保守阈值1000万")
        g.avg_etf_money_threshold = 10000000


def filter_global_pool_by_volume(context):
    """过滤全球/海外ETF池的流动性"""
    log.info("【全球池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        log.info("【全球池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.global_etf_pool:
        log.info("【全球池过滤】全球池为空，跳过过滤")
        g.filtered_global_pool = []
        return
    dynamic_threshold = g.avg_etf_money_threshold
    log.info(f"【全球池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.global_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("【全球池过滤】无法获取成交额数据，使用原始全球池")
            g.filtered_global_pool = g.global_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_global_pool = qualified.index.tolist()
        removed = set(g.global_etf_pool) - set(new_global_pool)
        if removed:
            removed_info = []
            for code in removed:
                try:
                    name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                    money = avg_daily_money.get(code, 0)
                    removed_info.append(f"{name}({code}) {money/1e8:.2f}亿")
                except:
                    removed_info.append(code)
            log.info(f"【全球池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_global_pool = new_global_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        log.info(f"【全球池过滤】保留高流动性ETF({len(new_global_pool)}只)")
    except Exception as e:
        log.warning(f"【全球池过滤】异常: {e}")
        g.filtered_global_pool = g.global_etf_pool[:]


def filter_fixed_pool_by_volume(context):
    """过滤固定ETF池的流动性"""
    if getattr(g, 'log_pool_update_details', False):
        log.info("【固定池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        if getattr(g, 'log_pool_update_details', False):
            log.info("【固定池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.fixed_etf_pool:
        if getattr(g, 'log_pool_update_details', False):
            log.info("【固定池过滤】固定池为空，跳过过滤")
        return
    dynamic_threshold = g.avg_etf_money_threshold
    if getattr(g, 'log_pool_update_details', False):
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
            if getattr(g, 'log_pool_update_details', False):
                log.info(f"【固定池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_fixed_pool = new_fixed_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        if getattr(g, 'log_pool_update_details', False):
            log.info(f"【固定池过滤】保留高流动性ETF({len(new_fixed_pool)}只)")
    except Exception as e:
        log.warning(f"【固定池过滤】异常: {e}")
        g.filtered_fixed_pool = g.fixed_etf_pool[:]


def update_sector_pool(context):
    """更新行业ETF动态池（v5.1完整版）：从全市场ETF中按行业分组，每个行业选取流动性最佳的ETF"""
    if getattr(g, 'log_pool_update_details', False):
        log.info("【动态池更新】开始执行")
    if g.avg_etf_money_threshold is None:
        if getattr(g, 'log_pool_update_details', False):
            log.info("【动态池更新】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    
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
    
    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)
    
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
        df_etf = get_all_securities(['etf'])
        etf_list = df_etf.index.tolist()
        g.etf_names_dict = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"获取全市场ETF列表失败: {e}")
        return
    
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新】全市场ETF总数: {len(etf_list)}只")
    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0
    
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
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新】特别组分布: {group_counts}")
        log.info(f"【动态池更新】进入特别组: {len(special_etfs)}只")
        log.info(f"【动态池更新】进入普通组: {len(normal_etfs)}只")
        log.info(f"【动态池更新】排除ETF: {excluded_count}只")
    
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold
    
    def filter_by_liquidity(etf_codes, group_name):
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
    if getattr(g, 'log_pool_update_details', False):
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
    if getattr(g, 'log_pool_update_details', False):
        log.info(f"【动态池更新完成】动态池共{len(g.dynamic_etf_pool)}只ETF")
    if getattr(g, 'log_pool_update_details', False) and len(g.dynamic_etf_pool) <= 10:
        for item in top_100[:10]:
            log.info(f"  {item['code']} {item['original_name']} 日均成交额: {item['money']/1e8:.2f}亿")


def daily_merge_etf_pools(context):
    """合并固定池与动态池"""
    if not hasattr(g, 'filtered_fixed_pool'):
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    if getattr(g, 'log_pool_update_details', False):
        log.info("【合并ETF池】开始执行")
        log.info(f"【合并池统计】固定池: {len(g.filtered_fixed_pool)}只, 动态池: {len(g.dynamic_etf_pool)}只, 合并后: {len(merged)}只")
    g.merged_etf_pool = merged


# ==================== 五福v5.1 动量计算核心函数 ====================


def _first_trading_day_after(d):
    """严格晚于 d 的第一个交易日（d 为卖出当日）。"""
    try:
        tds = get_trade_days(start_date=d, count=60)
        if tds is None or len(tds) == 0:
            return None
        for x in tds:
            xd = x.date() if hasattr(x, 'date') else x
            if xd > d:
                return xd
        return None
    except Exception:
        return None


def _scalar_momentum_finite(v):
    """动量得分是否为有限数值"""
    if v is None:
        return False
    try:
        x = float(np.asarray(v, dtype=float).ravel()[0])
        return math.isfinite(x)
    except Exception:
        return False


def build_short_momentum_3day_pattern_str(vals, eps=1e-12):
    """
    由三个递进端点上的短期动量得分生成三位模式（与 get_short_momentum_3day_pattern 约定一致：p1 p2 p2）。
    """
    if not vals or len(vals) != 3:
        return "N/A"
    if not all(_scalar_momentum_finite(v) for v in vals):
        return "N/A"
    try:
        v0 = float(np.asarray(vals[0], dtype=float).ravel()[0])
        v1 = float(np.asarray(vals[1], dtype=float).ravel()[0])
        v2 = float(np.asarray(vals[2], dtype=float).ravel()[0])
    except Exception:
        return "N/A"
    d1, d2 = v1 - v0, v2 - v1

    def _dir(d):
        if d > eps:
            return "增"
        if d < -eps:
            return "减"
        return "平"

    p1, p2 = _dir(d1), _dir(d2)
    return f"{p1}{p2}{p2}"



def _get_intraday_price_with_fallback(context, security):
    """获取当前时点价格：优先get_current_data，回退到分钟收盘价"""
    # 1) 优先 current_data
    try:
        cd = get_current_data()
        if security in cd:
            cur = float(cd[security].last_price)
            if cur is not None and cur > 0:
                return cur
    except Exception:
        pass
    # 2) 回退到分钟收盘价
    try:
        dt = getattr(context, 'current_dt', None)
        dfm = get_price(
            security,
            end_date=dt,
            count=1,
            frequency='1m',
            fields=['close'],
            panel=False,
            skip_paused=False
        )
        if dfm is not None and not dfm.empty:
            if 'close' in dfm.columns:
                cur = float(dfm['close'].iloc[-1])
            else:
                cur = float(dfm.iloc[-1, -1])
            if cur is not None and cur > 0:
                return cur
    except Exception:
        pass
    return None


def snapshot_momentum_for_security(context, security):
    """卖出复盘：与持仓当日框架一致的长/短动量快照"""
    try:
        cur = _get_intraday_price_with_fallback(context, security)
        if cur is None or cur <= 0:
            return None
        short_lb = int(getattr(g, 'short_momentum_lookback', 21))
        need = max(g.lookback_days, short_lb)
        bars = max(need + 25, 35)
        df = attribute_history(security, bars, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < need:
            return None
        hist = df['close'].values.astype(float)
        price_series = np.append(hist, cur)
        lm, lar, lr2 = calculate_momentum_score(price_series, g.lookback_days)
        sm, sar, sr2 = calculate_momentum_score(price_series, short_lb)
        return {
            'momentum_score': lm,
            'short_momentum_score': sm,
            'annualized_returns': lar,
            'short_annualized_returns': sar,
            'r_squared': lr2,
            'short_r_squared': sr2,
            'price': cur,
            'market_regime': getattr(g, 'market_regime', ''),
        }
    except Exception:
        return None


def _portfolio_mtm_total_value(context):
    """计算组合MTM总市值（使用场内last_price估值）"""
    try:
        total = context.portfolio.cash
        cd = get_current_data()
        for sec, pos in context.portfolio.positions.items():
            if pos.total_amount > 0 and sec in cd:
                px = float(cd[sec].last_price)
                if px > 0:
                    total += pos.total_amount * px
        return total
    except Exception:
        return context.portfolio.total_value


def monitor_drawdown(context):
    """组合回撤监控（v5.1版本）"""
    try:
        current_value = _portfolio_mtm_total_value(context)
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        if g.max_portfolio_value <= 0:
            return
        current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
        if current_drawdown < g.drawdown_threshold:
            return

        record = {
            'date': context.current_dt.strftime('%Y-%m-%d'),
            'drawdown': current_drawdown,
            'portfolio_value': current_value,
            'max_value': g.max_portfolio_value,
            'market_regime': getattr(g, 'market_regime', ''),
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
        log.info(f"  市场状态: {getattr(g, 'market_regime', '')}")
        log.info(f"  持仓: {', '.join(positions_info) if positions_info else '空仓'}")

        # 组合回撤分级动作（可选）
        if not getattr(g, 'enable_drawdown_risk_actions', False):
            return

        today = context.current_dt.date()
        if getattr(g, 'dd_action_cooldown_date', None) == today:
            return

        th_flat = float(getattr(g, 'dd_flat_threshold', 0.20))
        th_def = float(getattr(g, 'dd_switch_defensive_threshold', 0.15))
        th_half = float(getattr(g, 'dd_half_position_threshold', 0.10))
        warn = float(getattr(g, 'drawdown_threshold', 0.03))
        
        if not (th_flat > th_def > th_half > warn):
            log.warning("【组合回撤动作】阈值链不合法，已跳过动作")
            return

        acted = False
        exit_tag = f"组合回撤{current_drawdown:.2%}"

        if current_drawdown >= th_flat:
            log.warning(f"🛑 【组合回撤·全部清仓】{current_drawdown:.2%} ≥ {th_flat:.0%}")
            ok_any = False
            for sec in list(context.portfolio.positions.keys()):
                pos = context.portfolio.positions.get(sec)
                if pos and pos.total_amount > 0:
                    order_target_value(sec, 0)
                    ok_any = True
            acted = ok_any
        elif current_drawdown >= th_def:
            log.warning(f"🛡️ 【组合回撤·切防御清仓】{current_drawdown:.2%} ≥ {th_def:.0%}")
            def_etf = getattr(g, 'defensive_etf', None)
            ok_any = False
            for sec in list(context.portfolio.positions.keys()):
                if sec == def_etf:
                    continue
                pos = context.portfolio.positions.get(sec)
                if pos and pos.total_amount > 0:
                    order_target_value(sec, 0)
                    ok_any = True
            acted = ok_any
        elif current_drawdown >= th_half:
            keep_frac = float(getattr(g, 'dd_partial_close_keep_fraction', 0.5))
            log.warning(f"⚠️ 【组合回撤·减仓】{current_drawdown:.2%} ≥ {th_half:.0%}，可卖部分保留 {keep_frac:.0%}")
            for sec in list(context.portfolio.positions.keys()):
                pos = context.portfolio.positions.get(sec)
                if pos and pos.total_amount > 0:
                    target = pos.total_amount * pos.last_sale_price * keep_frac
                    order_target_value(sec, target)
            acted = True

        if acted:
            g.dd_action_cooldown_date = today
            if getattr(g, 'dd_reset_peak_after_action', True):
                nv = _portfolio_mtm_total_value(context)
                g.max_portfolio_value = max(nv, 1.0)
                log.info(f"【组合回撤动作】已执行，冷却至次日；峰值已重置为当前净值≈{g.max_portfolio_value:,.0f}")
    except Exception as e:
        log.error(f"【回撤监控】计算异常: {e}")


# ==================== 五福v5.1 交易执行函数 ====================

# v5.1的交易执行函数已禁用，使用原有的v3.5版本（已适配子账户资金管理）
# def execute_sell_trades(context):
#     """执行卖出操作（v5.1版本 - 已禁用）"""
#     pass
#
# def execute_buy_trades(context):
#     """执行买入操作（v5.1版本 - 已禁用）"""
#     pass


def short_by_market_cap(context, stock_list):
    short_q = query(
        valuation.code,
        valuation.market_cap,
    ).filter(
        valuation.code.in_(stock_list),
        valuation.day == context.previous_date,
    ).order_by(valuation.market_cap.asc())
    # 修复：添加date参数，避免使用未来财务数据
    short_df = get_fundamentals(short_q, date=context.previous_date)
    short_list = short_df['code'].unique().tolist()
    return short_list


""" ====================== 执行入口, 定时任务下发 ====================== """


def after_code_changed(context):
    unschedule_all()

    if g.portfolio_value_proportion[0] > 0:
        run_daily(prepare_small_cap_strategy, "9:05")
        if g.check_defense and g.defense_signal is None:
            check_defense_trigger(context)
        if g.DBL_control:
            run_daily(check_dbl, "9:31")
        run_weekly(strategy_1_sell, 2, "09:40")
        run_weekly(strategy_1_buy, 2, "09:40:02")
        run_daily(sell_small_cap_stocks, time="10:00")
        if g.huanshou_check:
            run_daily(check_small_cap_turnover, "10:30")
        run_daily(check_small_cap_limit_up, "14:00")
        if g.check_defense:
            run_daily(check_defense_trigger, "14:50")
        run_daily(close_account, "14:50")

    # 策略2 七星策略（替换原ETF反弹策略）
    if g.portfolio_value_proportion[1] > 0:
        log.info("【七星策略】注册调度任务...")
        # 开盘检查持仓
        run_daily(qixing_check_positions, time='09:10')
        # 盈利保护独立检查（11:00）
        for check_time in getattr(g, 'qixing_profit_protection_check_times', ['11:00']):
            run_daily(qixing_profit_protection_check, time=check_time)
            log.info(f"【七星策略】已注册盈利保护检查时间：{check_time}")
        # 震荡期检查（在卖出前执行）
        run_daily(qixing_check_range_bound, time='13:53')
        # 收盘重置震荡期标志
        run_daily(qixing_reset_range_bound_daily, time='15:10')
        # 卖出和买入操作（与七星.py保持一致）
        run_daily(qixing_etf_sell_trade, time='13:08')
        run_daily(qixing_etf_buy_trade, time='13:09')
        log.info("【七星策略】调度任务注册完成")

# 策略3 五福5.1v3（升级为v5.1版本）
    if g.portfolio_value_proportion[2] > 0:
        if "morning_routine" not in globals() or "afternoon_routine" not in globals():
            log.error("【五福5.1v3】缺少 morning_routine/afternoon_routine，请保留文件头部五福内嵌段。")
        else:
            log.set_level("system", "error")
            log.set_level("strategy", "info")
            # 设置五福5.1v3的交易时间为13:08（提前2分钟）
            g.afternoon_sell_time = '13:08'
            run_daily(morning_routine, time="09:00")
            # v5.1 新增：三态市场判断在09:40执行
            run_daily(check_weak_period_daily, time="09:40")
            # v5.1 新增：早盘ETF池更新在09:45执行（市场状态判定后）
            run_daily(midday_routine, time="09:45")
            # v5.1 新增：回撤监控在10:31执行（避免开盘前无连续竞价价）
            run_daily(drawdown_monitor_routine, time=getattr(g, 'dd_monitor_time', '10:31'))
            # 【修改点】：不再区分纯净模式，强制在 13:08 执行（提前2分钟）
            run_daily(afternoon_routine, time="13:08")
            run_daily(reset_daily_flags, time="15:10")
            run_daily(minute_level_stop_loss, time="every_bar")
            run_daily(minute_level_pct_stop_loss, time="every_bar")

    # 策略4 白马策略
    if g.portfolio_value_proportion[3] > 0:
        run_monthly(prepare_blue_chip_before_open, 1, time="9:30")
        run_monthly(adjust_blue_chip_position, 1, time="10:40")

    run_daily(make_record, "15:01")
    run_daily(print_summary, "15:02")


    if g.portfolio_value_proportion[3] > 0:
        run_monthly(prepare_blue_chip_before_open, 1, time="9:30")
        run_monthly(adjust_blue_chip_position, 1, time="10:40")

    run_daily(make_record, "15:01")
    run_daily(print_summary, "15:02")


    if g.portfolio_value_proportion[3] > 0:
        run_monthly(prepare_blue_chip_before_open, 1, time="9:30")
        run_monthly(adjust_blue_chip_position, 1, time="10:40")

    run_daily(make_record, "15:01")
    run_daily(print_summary, "15:02")


