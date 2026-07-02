# Clone from JoinQuant
# postId: 5511f8f0ee9015ab04c4bf864d9faba6
# backtestId: a8fa945dc8be63eec819a10f49c17df6
# title: 穿越牛熊周期-多策略组合-20至今年化103.20%

"""
描述：本策略整合了6个子策略，通过组合优化和每日资金动态平衡实现风险分散和收益增强

策略构成：
1. ST弱转强策略（10%）：利用ST股票的弱转强形态进行短线交易（设置权重上限30%）
2. 高股息+PEG+扣非净利润增速策略（18%）：价值投资策略，筛选高股息成长股
3. ETF轮动策略（22%）：基于动量和均线过滤的ETF轮动
4. 单因子微盘股策略（18%）：专注小市值股票的单一因子策略
5. 国九条小市值策略（22%）：结合国九条政策筛选优质小盘股
6. 科技股策略（10%）：沿用国九条基本面框架，在科技行业和主题概念中筛选优质小盘股

风险提示：ST策略历史收益高但未来可能因涨跌幅限制取消而失效，已设置保护机制
"""

from jqdata import *
from jqfactor import get_factor_values
from jqlib.technical_analysis import *
import pandas as pd
import numpy as np
import datetime as dt
import datetime
import math
from scipy.optimize import minimize


STRATEGY_COLUMNS = ["st", "dividend", "etf", "microcap", "microcap_gjt", "tech"]
STRATEGY_NAMES = ["ST策略", "高股息策略", "ETF轮动策略", "单因子小市值", "国九条小市值", "科技股策略"]
STRATEGY_NAME_TO_INDEX = {
    "ST策略": 1,
    "高股息策略": 2,
    "ETF轮动策略": 3,
    "单因子小市值": 4,
    "国九条小市值": 5,
    "科技股策略": 6,
}


# ==============================
# 一、组合层初始化
# ==============================


def initialize(context):
    """
    初始化函数：设置交易参数、创建子账户
    """
    # 基本设置
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    log.set_level("order", "error")
    log.set_level("system", "error")
    log.set_level("strategy", "debug")

    # 设置交易成本和滑点
    set_slippage(PriceRelatedSlippage(0.0012), type="stock")
    set_slippage(PriceRelatedSlippage(0.0012), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5,
        ),
        type="stock",
    )
    set_order_cost(
        OrderCost(
            open_tax=0,           # 买入印花税：0
            close_tax=0,          # 卖出印花税：0（ETF免征）
            open_commission=0.0001,  # 买入佣金：万分之0.5
            close_commission=0.0001, # 卖出佣金：万分之0.5
            close_today_commission=0, # 今仓佣金：0
            min_commission=0.1,       # 最低佣金：0.1元（很多券商免5）
        ),
        type="fund"  # 关键：使用fund类型而非stock
    )
    # 货币ETF免佣
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0,
            close_commission=0,
            close_today_commission=0,
            min_commission=0,
        ),
        type="mmf",
    )

    # ===== 多策略组合变量 =====
    # 0号子账户：资金中枢，不交易；1~6是6个子策略
    g.portfolio_value_proportion = [0, 0.10, 0.18, 0.22, 0.18, 0.22, 0.10]
    g.risk_free_rate = 0.03
    g.rebalancing = 1  # 每1个月做一次最优配比
    g.rebalancing_cnt = 0

    # 创建7个子账户：0~6
    set_subportfolios(
        [
            SubPortfolioConfig(
                context.portfolio.starting_cash * g.portfolio_value_proportion[i],
                "stock",
            )
            for i in range(len(g.portfolio_value_proportion))
        ]
    )

    # ===== 储存6个策略信息 =====
    # ST策略
    g.st_today_list = []
    # 高股息策略
    g.dividend_hold_list = []
    # 单因子小市值
    g.microcap_stock_pool = []
    # 国九条小市值
    g.gjt_check_out_lists = []
    g.gjt_sell_stock_list = []
    g.gjt_blacklist = []
    g.gjt_buy_stock_list = []
    g.gjt_ZT = []
    g.gjt_notbuy = []
    # 科技股策略
    g.tech_check_out_lists = []
    g.tech_sell_stock_list = []
    g.tech_blacklist = []
    g.tech_buy_stock_list = []
    g.tech_ZT = []
    g.tech_notbuy = []

    # 记录6个子策略净值轨迹
    g.strategys_values = pd.DataFrame(columns=STRATEGY_COLUMNS)

    # ===== 组合层：记录子策略净值 & 权重优化 =====
    run_daily(get_strategys_values, "18:00")
    run_weekly(calculate_optimal_weights, 1, "19:00")

    # ===== 子策略调度 =====
    # 1. ST策略：7:25选股，9:23买入，11:25卖出
    run_daily(st_prepare, "07:25")
    run_daily(st_buy, "09:23")
    run_daily(st_sell, "11:25")

    # 2. 高股息策略：月初+月中+业绩披露窗口日频
    run_monthly(dividend_adjust, 1, "09:40")
    run_monthly(dividend_adjust, 11, "09:40")
    run_daily(dividend_adjust_in_earnings_window, "09:40")

    # 3. ETF轮动策略：7:00晨报，11:25调仓
    run_daily(etf_morning_report, "07:00")
    run_daily(etf_adjust, "11:25")

    # 4. 单因子小市值：9:00更新池，10:30调仓
    run_daily(microcap_update_pool, "09:00", reference_security="000300.XSHG")
    run_daily(microcap_adjust, "10:30", reference_security="000300.XSHG")

    # 5. 国九条小市值：10:31选股，10:40交易，13:55跌停板尾盘处理
    run_daily(gjt_check_stocks, "10:31")
    run_daily(gjt_main_pick, "10:40")
    run_daily(gjt_trade, "10:40")
    run_daily(gjt_no_zt_sell, "13:55")

    # 6. 科技股策略：复用国九条执行框架，股票池限定科技行业和概念
    run_daily(tech_check_stocks, "10:31")
    run_daily(tech_main_pick, "10:40")
    run_daily(tech_trade, "10:40")
    run_daily(tech_no_zt_sell, "13:55")


def get_strategy(strategy_name, context):
    """
    根据策略名称获取策略实例

    Args:
        strategy_name: 策略名称
        context: 上下文对象

    Returns:
        策略实例
    """
    if strategy_name == "ST策略":
        return ST_Strategy(context, 1, strategy_name)
    elif strategy_name == "高股息策略":
        return Dividend_Strategy(context, 2, strategy_name)
    elif strategy_name == "ETF轮动策略":
        return ETF_Rotation_Strategy(context, 3, strategy_name)
    elif strategy_name == "单因子小市值":
        return Microcap_SingleFactor_Strategy(context, 4, strategy_name)
    elif strategy_name == "国九条小市值":
        return Microcap_GJT_Strategy(context, 5, strategy_name)
    elif strategy_name == "科技股策略":
        return Tech_Stock_Strategy(context, 6, strategy_name)
    else:
        log.error(f"未知策略名称: {strategy_name}")
        return None


# ==== 组合层调度包装函数 ====


def st_prepare(context):
    """ST策略选股准备"""
    strategy = get_strategy("ST策略", context)
    strategy.prepare(context)


def st_buy(context):
    """ST策略买入执行"""
    strategy = get_strategy("ST策略", context)
    strategy.buy(context)


def st_sell(context):
    """ST策略卖出执行"""
    strategy = get_strategy("ST策略", context)
    strategy.sell(context)


def dividend_adjust(context):
    """高股息策略调仓"""
    strategy = get_strategy("高股息策略", context)
    strategy.adjust(context)


def dividend_adjust_in_earnings_window(context):
    """业绩披露窗口期调仓"""
    strategy = get_strategy("高股息策略", context)
    strategy.adjust_in_earnings_window(context)


def etf_morning_report(context):
    """ETF轮动策略晨报"""
    strategy = get_strategy("ETF轮动策略", context)
    strategy.morning_report(context)


def etf_adjust(context):
    """ETF轮动策略调仓"""
    strategy = get_strategy("ETF轮动策略", context)
    strategy.adjust(context)


def microcap_update_pool(context):
    """单因子小市值策略更新股票池"""
    strategy = get_strategy("单因子小市值", context)
    strategy.update_pool(context)


def microcap_adjust(context):
    """单因子小市值策略调仓"""
    strategy = get_strategy("单因子小市值", context)
    strategy.adjust(context)


def gjt_check_stocks(context):
    """国九条小市值策略检查股票"""
    strategy = get_strategy("国九条小市值", context)
    strategy.check_stocks(context)


def gjt_main_pick(context):
    """国九条小市值策略选股"""
    strategy = get_strategy("国九条小市值", context)
    strategy.main_pick(context)


def gjt_trade(context):
    """国九条小市值策略交易"""
    strategy = get_strategy("国九条小市值", context)
    strategy.trade(context)


def gjt_no_zt_sell(context):
    """国九条小市值策略非涨停卖出"""
    strategy = get_strategy("国九条小市值", context)
    strategy.no_zt_sell(context)


def tech_check_stocks(context):
    """科技股策略检查股票"""
    strategy = get_strategy("科技股策略", context)
    strategy.check_stocks(context)


def tech_main_pick(context):
    """科技股策略选股"""
    strategy = get_strategy("科技股策略", context)
    strategy.main_pick(context)


def tech_trade(context):
    """科技股策略交易"""
    strategy = get_strategy("科技股策略", context)
    strategy.trade(context)


def tech_no_zt_sell(context):
    """科技股策略非涨停卖出"""
    strategy = get_strategy("科技股策略", context)
    strategy.no_zt_sell(context)


# ==============================
# 二、组合层：子策略净值记录 & 权重优化
# ==============================


def get_strategys_values(context):
    """
    记录各子策略每日净值
    用于后续的组合权重优化
    """
    df = g.strategys_values
    data = dict(
        zip(
            df.columns,
            [context.subportfolios[i + 1].total_value for i in range(len(df.columns))],
        )
    )
    df.loc[len(df)] = data
    if len(df) > 250:
        df = df.drop(0)


def calculate_optimal_weights(context, alpha=0.5):
    """
    计算最优策略权重
    使用VASR(Variance-Adjusted Sharpe Ratio)作为优化目标

    Args:
        context: 上下文对象
        alpha: 风险厌恶系数，越高越厌恶风险
    """
    df = g.strategys_values
    g.rebalancing_cnt += 1

    # 检查是否满足再平衡条件
    if len(df) < 250 or not g.rebalancing_cnt % g.rebalancing == 0:
        return

    # 记录当前权重
    current_weights = [
        round(context.subportfolios[i].total_value / context.portfolio.total_value, 3)
        for i in range(len(g.portfolio_value_proportion))
    ]
    weights_str = ", ".join(
        [f"账户{i}: {weight:.1%}" for i, weight in enumerate(current_weights)]
    )
    log.info(f"目前仓位比例: {weights_str}")

    # 计算收益率和协方差矩阵
    returns = df.pct_change().dropna()
    if returns.empty:
        return

    annualized_returns = returns.mean() * 252
    cov_matrix = returns.cov() * 252

    def negative_vasr(weights):
        """计算负的VASR（用于最小化）"""
        portfolio_return = np.dot(weights, annualized_returns)
        portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        if portfolio_volatility == 0:
            return 0
        sharpe_ratio = (portfolio_return - g.risk_free_rate) / portfolio_volatility
        vasr = sharpe_ratio / (1 + alpha * portfolio_volatility)
        return -vasr

    # 优化约束条件
    constraints = [
        {"type": "eq", "fun": lambda x: np.sum(x) - 1},  # 权重和为1
        {"type": "ineq", "fun": lambda x: x - 0.05},  # 最小权重5%
    ]

    # 添加权重变化约束（避免极端调仓）
    last_best_weights = g.portfolio_value_proportion[1:]
    constraints.append(
        {"type": "ineq", "fun": lambda x: 0.1 - np.abs(x - last_best_weights)}
    )

    num_strategies = len(returns.columns)
    initial_weights = np.array([1.0 / num_strategies] * num_strategies)
    initial_weights = np.maximum(initial_weights, 0.05)

    # 执行优化
    result = minimize(
        negative_vasr,
        initial_weights,
        method="SLSQP",
        constraints=constraints,
    )

    if not result.success:
        return

    best_weights = result.x.tolist()
    g.portfolio_value_proportion = [0] + best_weights
    log.info(f"最佳权重: {[round(i, 3) for i in best_weights]}")


# ==============================
# 三、策略基类（子账户管理 + 通用过滤）
# ==============================


class Strategy:
    """
    策略基类
    提供子账户管理、通用股票过滤等功能
    所有子策略都继承自此类
    """

    def __init__(self, context, subportfolio_index, name):
        """
        初始化策略

        Args:
            context: 上下文对象
            subportfolio_index: 子账户索引
            name: 策略名称
        """
        self.subportfolio_index = subportfolio_index
        self.name = name
        self.subportfolio = context.subportfolios[self.subportfolio_index]
        self.stock_sum = 1  # 默认持仓股票数
        self.hold_list = []  # 持仓列表
        self.limit_up_list = []  # 昨日涨停列表
        self.fill_stock = "511880.XSHG"  # 货币ETF，用于资金闲置

    def _prepare(self, context):
        """
        更新持仓和昨日涨停列表
        每个交易日开始前调用
        """
        self.hold_list = list(
            context.subportfolios[self.subportfolio_index].long_positions.keys()
        )
        if self.hold_list:
            df = get_price(
                self.hold_list,
                end_date=context.previous_date,
                frequency="daily",
                fields=["close", "high_limit"],
                count=1,
                panel=False,
                fill_paused=False,
            )
            df = df[df["close"] == df["high_limit"]]
            self.limit_up_list = list(df.code)
        else:
            self.limit_up_list = []

        log.debug(
            f"[{self.name}] 持仓: {len(self.hold_list)}只, "
            f"昨日涨停: {len(self.limit_up_list)}只"
        )

    def _check(self, context):
        """检查昨日涨停票：涨停打开就卖出"""
        if self.limit_up_list:
            current_data = get_current_data()
            for stock in self.limit_up_list:
                if current_data[stock].last_price < current_data[stock].high_limit:
                    log.info(f"[{self.name}] 涨停打开，卖出 {stock}")
                    self.order_target_value_(stock, 0)

    def _adjust(self, context, target):
        """
        通用调仓函数：等权买入目标股票

        Args:
            context: 上下文对象
            target: 目标股票列表
        """
        # 卖出不在目标且不是昨日涨停的
        for security in self.hold_list:
            if (security not in target) and (security not in self.limit_up_list):
                log.info(f"[{self.name}] 调出持仓 {security}")
                self.order_target_value_(security, 0)

        # 调整子账户间资金
        self.balance_subportfolios(context)

        # 买入目标股票
        current_positions = list(self.subportfolio.long_positions.keys())
        candidates = [s for s in target if s not in current_positions]
        count = len(candidates)
        if count == 0 or self.stock_sum <= len(current_positions):
            log.info(f"[{self.name}] 无新股票可买入或已达持仓上限")
            return

        # 计算可用资金
        target_total = (
            g.portfolio_value_proportion[self.subportfolio_index]
            * context.portfolio.total_value
        )
        value_to_use = max(
            0,
            min(
                target_total - self.subportfolio.positions_value,
                self.subportfolio.available_cash,
            ),
        )
        if value_to_use <= 0:
            log.info(f"[{self.name}] 无可用资金: {value_to_use:.2f}")
            return

        value_per = value_to_use / count

        log.info(f"[{self.name}] 买入{candidates}，每只{value_per:.2f}")

        for security in candidates:
            self.order_target_value_(security, value_per)

    def order_target_value_(self, security, value):
        """
        子账户内下单函数

        Args:
            security: 股票代码
            value: 目标市值

        Returns:
            下单结果
        """
        current_data = get_current_data()
        if current_data[security].paused:
            log.info(f"[{self.name}] {security} 今日停牌，跳过")
            return 0

        style = None
        if security.startswith("688"):
            last_price = current_data[security].last_price
            if last_price <= 0:
                log.info(f"[{self.name}] {security} 当前价格无效，跳过")
                return 0
            if value == 0:
                limit_price = max(current_data[security].low_limit, last_price * 0.98)
            else:
                limit_price = min(current_data[security].high_limit, last_price * 1.02)
            style = MarketOrderStyle(limit_price)
            log.info(f"[{self.name}] {security} 科创板市价单保护限价: {limit_price:.2f}")

        if value == 0:
            # 卖出
            amount = self.subportfolio.long_positions.get(security, None)
            if amount:
                log.info(f"[{self.name}] 卖出 {security}，持仓{amount.closeable_amount}股")
        else:
            # 买入
            price = current_data[security].last_price
            if price > 0:
                shares = int(value / price / 100) * 100
                log.info(
                    f"[{self.name}] 买入 {security}，目标市值{value:.2f}，"
                    f"价格{price:.2f}，约{shares}股"
                )

        if style is not None:
            return order_target_value(
                security, value, style=style, pindex=self.subportfolio_index
            )
        return order_target_value(security, value, pindex=self.subportfolio_index)

    def get_net_values(self, amount):
        """
        子账户净值修正
        资金在0号和子账户之间划转时使用

        Args:
            amount: 划转金额，正数表示划入，负数表示划出
        """
        df = g.strategys_values
        if df.empty:
            return

        col_idx = self.subportfolio_index - 1
        last_idx = len(df) - 1
        old_last = df.iloc[last_idx, col_idx]
        df.iloc[last_idx, col_idx] = old_last + amount
        new_last = df.iloc[last_idx, col_idx]

        if old_last == 0:
            return

        for i in range(last_idx - 1, -1, -1):
            df.iloc[i, col_idx] = new_last * df.iloc[i, col_idx] / old_last

        log.debug(
            f"[{self.name}] 净值调整: {old_last:.2f} -> {new_last:.2f}, " f"变动{amount:.2f}"
        )

    def balance_subportfolios(self, context):
        """
        子账户与0号账户间资金平衡
        确保每个子账户的资金比例符合目标
        """
        target = (
            g.portfolio_value_proportion[self.subportfolio_index]
            * context.portfolio.total_value
        )
        value = self.subportfolio.total_value

        log.debug(
            f"[{self.name}] 资金平衡检查: 目标{target:.2f}, "
            f"当前{value:.2f}, 差值{target - value:.2f}"
        )

        # 仓位过高：向0号账户划出资金
        cash = self.subportfolio.transferable_cash
        if cash > 0 and target < value:
            amount = min(value - target, cash)
            if amount > 100:  # 小额不调整
                transfer_cash(self.subportfolio_index, 0, amount)
                self.get_net_values(-amount)
                log.info(f"[{self.name}] 划出资金到0号账户: {amount:.2f}")

        # 仓位过低：从0号账户划入资金
        cash0 = context.subportfolios[0].transferable_cash
        if target > value and cash0 > 0:
            amount = min(target - value, cash0)
            if amount > 100:  # 小额不调整
                transfer_cash(0, self.subportfolio_index, amount)
                self.get_net_values(amount)
                log.info(f"[{self.name}] 从0号账户划入资金: {amount:.2f}")

    def filter_basic_stock(self, context, stock_list):
        """
        通用基础过滤（ST/科创/北交/次新）

        Args:
            context: 上下文对象
            stock_list: 待过滤股票列表

        Returns:
            过滤后的股票列表
        """
        current_data = get_current_data()
        res = []
        for stock in stock_list:
            info = current_data[stock]
            if info.paused:
                continue
            if info.is_st or "ST" in info.name or "*" in info.name or "退" in info.name:
                continue
            # 科创 / 北交 / 创业板过滤
            if stock[0] == "4" or stock[0] == "8" or stock[:2] == "68":
                continue
            if context.previous_date - get_security_info(
                stock
            ).start_date < datetime.timedelta(375):
                continue
            res.append(stock)
        return res

    def filter_limitup_limitdown_stock(self, context, stock_list):
        """
        过滤涨跌停股票

        Args:
            context: 上下文对象
            stock_list: 待过滤股票列表

        Returns:
            过滤后的股票列表
        """
        current_data = get_current_data()
        res = []
        for stock in stock_list:
            if stock in self.subportfolio.long_positions:
                res.append(stock)
                continue
            if (
                current_data[stock].last_price < current_data[stock].high_limit
                and current_data[stock].last_price > current_data[stock].low_limit
            ):
                res.append(stock)
        return res


# ==============================
# 四、子策略1：ST弱转强策略（20%）
# ==============================


class ST_Strategy(Strategy):
    """
    ST弱转强策略
    策略逻辑：筛选ST股票中技术形态呈现弱转强的标的
    特点：高风险高收益，适合短线交易
    """

    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 3  # 最多持仓5只
        log.info(f"[{self.name}] 初始化完成，最大持仓{self.stock_sum}只")

    def transform_date(self, date, date_type):
        """日期格式转换"""
        if isinstance(date, str):
            str_date = date
            dt_date = dt.datetime.strptime(date, "%Y-%m-%d")
            d_date = dt_date.date()
        elif isinstance(date, dt.datetime):
            str_date = date.strftime("%Y-%m-%d")
            dt_date = date
            d_date = dt_date.date()
        elif isinstance(date, dt.date):
            str_date = date.strftime("%Y-%m-%d")
            dt_date = dt.datetime.strptime(str_date, "%Y-%m-%d")
            d_date = date
        dct = {"str": str_date, "dt": dt_date, "d": d_date}
        return dct[date_type]

    def get_shifted_date(self, date, days, days_type="T"):
        """获取偏移日期"""
        d_date = self.transform_date(date, "d")
        yesterday = d_date + dt.timedelta(-1)
        if days_type == "N":
            shifted_date = yesterday + dt.timedelta(days + 1)
        else:
            all_trade_days = [
                i.strftime("%Y-%m-%d") for i in list(get_all_trade_days())
            ]
            if str(yesterday) in all_trade_days:
                shifted_date = all_trade_days[
                    all_trade_days.index(str(yesterday)) + days + 1
                ]
            else:
                for i in range(100):
                    last_trade_date = yesterday - dt.timedelta(i)
                    if str(last_trade_date) in all_trade_days:
                        shifted_date = all_trade_days[
                            all_trade_days.index(str(last_trade_date)) + days + 1
                        ]
                        break
        return str(shifted_date)

    def get_st(self, context):
        """获取所有ST股"""
        yesterday = context.previous_date
        stock_list = get_all_securities(types="stock", date=yesterday).index
        st_data = get_extras("is_st", stock_list, count=1, end_date=yesterday)
        st_data = st_data.T
        st_data.columns = ["is_st"]
        st_data = st_data[st_data["is_st"] == True]
        return st_data.index.tolist()

    def get_relative_position_df(self, stock_list, date, watch_days, ratio):
        """处于近n天相对高位"""
        if stock_list:
            df = get_price(
                stock_list,
                end_date=date,
                fields=["high", "low", "close"],
                count=watch_days,
                fill_paused=False,
                skip_paused=False,
                panel=False,
            ).dropna()
            close = df.groupby("code")["close"].last()
            high = df.groupby("code")["high"].max()
            low = df.groupby("code")["low"].min()
            result = pd.DataFrame(
                {"rp": (close - low) / (high - low)}, index=close.index
            )
        else:
            result = pd.DataFrame(columns=["rp"])
        result = result[result["rp"] >= ratio]
        return list(result.index)

    def filter_stocks(self, context, stocks):
        """
        技术面过滤
        条件：
        1. 近20日处于相对高位（rp>=0.6）
        2. 昨日收盘价 > 前一日最低价
        3. 昨日收盘价 > 昨日跌停价
        4. 昨日收盘价 > 10日均线
        5. 昨日成交量 < 10 * 前一日成交量
        6. 昨日收盘价 > 1元
        """
        yesterday = context.previous_date

        # 先做相对高位过滤
        stocks = self.get_relative_position_df(stocks, yesterday, 20, 0.6)
        if not stocks:
            log.info(f"[{self.name}] 相对高位过滤后无股票")
            return []

        # 取最近11天的日线数据
        df = get_price(
            stocks,
            end_date=yesterday,
            frequency="1d",
            fields=["close", "low", "volume", "money", "low_limit"],
            count=11,
            panel=False,
        )

        if df is None or df.empty:
            log.info(f"[{self.name}] 获取价格数据失败")
            return []

        df = df.reset_index()
        valid_stocks = []
        grouped = df.groupby("code")

        for code, sub in grouped:
            sub = sub.sort_values("time")

            if len(sub) < 2:
                continue

            sub["ma10"] = sub["close"].rolling(10).mean()

            last = sub.iloc[-1]  # 昨天
            prev = sub.iloc[-2]  # 前天

            if pd.isna(last["ma10"]):
                continue

            cond = (
                (last["close"] > prev["low"])
                and (last["close"] > last["low_limit"])  # 昨收 > 前一日最低
                and (last["close"] > last["ma10"])  # 昨收 > 昨日跌停价
                and (last["volume"] < 10 * prev["volume"])  # 昨收 > 10日均线
                and (last["close"] > 1)  # 昨量 < 10 * 前一日量  # 股价 > 1元
            )

            if cond:
                valid_stocks.append(code)

        log.info(f"[{self.name}] 技术面过滤: 从{len(stocks)}到{len(valid_stocks)}只")
        return valid_stocks

    def get_ever_hl_stock(self, initial_list, date):
        """昨日不涨停股票"""
        df = get_price(
            initial_list,
            end_date=date,
            frequency="daily",
            fields=["close", "high", "high_limit"],
            count=1,
            panel=False,
            fill_paused=False,
            skip_paused=False,
        )
        df = df.dropna()
        df = df[df["close"] != df["high_limit"]]
        return list(df.code)

    def get_hl_stock(self, initial_list, date):
        """昨日涨停股票"""
        df = get_price(
            initial_list,
            end_date=date,
            frequency="daily",
            fields=["close", "high_limit"],
            count=1,
            panel=False,
            fill_paused=False,
            skip_paused=False,
        )
        df = df.dropna()
        df = df[df["close"] == df["high_limit"]]
        return list(df.code)

    def rzq_list(self, context, initial_list):
        """昨日不涨停 + 前日涨停过滤"""
        date = context.previous_date
        date_str = self.transform_date(date, "str")
        date_1 = self.get_shifted_date(date_str, -1, "T")
        h1_list = self.get_ever_hl_stock(initial_list, date_str)
        hl_pre = self.get_hl_stock(initial_list, date_1)
        return [stock for stock in h1_list if stock in hl_pre]

    def prepare(self, context):
        """ST策略选股准备"""
        log.info(f"[{self.name}] 开始选股 - 日期: {context.current_dt.strftime('%Y-%m-%d')}")

        date = context.previous_date
        date_str = self.transform_date(date, "str")
        g.st_today_list = []

        # 1. 基础ST池
        stk_list = self.get_st(context)
        if not stk_list:
            log.info(f"[{self.name}] 无ST股票")
            return

        log.info(f"[{self.name}] 初始ST股票池: {len(stk_list)}只")

        # 2. 技术过滤
        stk_list = self.filter_stocks(context, stk_list)
        if not stk_list:
            log.info(f"[{self.name}] 技术过滤后无股票")
            return

        log.info(f"[{self.name}] 技术过滤后: {len(stk_list)}只")

        # 3. 昨日不涨停、前日涨停过滤
        stk_list = self.rzq_list(context, stk_list)
        if not stk_list:
            log.info(f"[{self.name}] 弱转强过滤后无股票")
            return

        log.info(f"[{self.name}] 弱转强过滤后: {len(stk_list)}只")

        # 4. 按换手率排序，取前5*3只做池子
        df = get_valuation(
            stk_list,
            end_date=date_str,
            count=1,
            fields=["turnover_ratio"],
        )
        df = df.sort_values(by="turnover_ratio", ascending=False)
        g.st_today_list = list(df.code)[: self.stock_sum * 3]

        log.info(f"[{self.name}] 筛选后股池数 {len(g.st_today_list)}，股池: {g.st_today_list}")

    def sell(self, context):
        """ST策略卖出逻辑"""
        log.info(f"[{self.name}] 开始卖出检查")

        subpf = context.subportfolios[self.subportfolio_index]
        hold_list = [
            stock
            for stock in list(subpf.positions.keys())
            if stock not in g.st_today_list
        ]
        if not hold_list:
            log.info(f"[{self.name}] 无不在今日股池的持仓")
            return

        log.info(f"[{self.name}] 检查卖出: {hold_list}")

        current_data = get_current_data()
        yesterday = context.previous_date
        df_history = get_price(
            hold_list,
            end_date=yesterday,
            frequency="daily",
            fields=["money", "close", "high", "high_limit", "low_limit"],
            count=1,
            panel=False,
        )
        df_history["avg_cost"] = [subpf.positions[s].avg_cost for s in hold_list]
        df_history["price"] = [subpf.positions[s].price for s in hold_list]
        df_history["hl"] = [current_data[s].high_limit for s in hold_list]
        df_history["ll"] = [current_data[s].low_limit for s in hold_list]
        df_history["last_price"] = [current_data[s].last_price for s in hold_list]

        # 条件1：未涨停
        cond1 = df_history["last_price"] != df_history["hl"]
        # 条件2：盈亏 + 昨涨停等逻辑
        ret_matrix = (df_history["price"] / df_history["avg_cost"] - 1) * 100
        cond2_1 = ret_matrix < -3  # 亏损超过3%
        cond2_2 = ret_matrix >= 0  # 不亏钱
        cond2_4 = df_history["close"] == df_history["high_limit"]  # 昨日涨停
        sell_condition = cond1 & (cond2_1 | cond2_2 | cond2_4)

        sell_list = df_history[
            sell_condition & (df_history["last_price"] > df_history["low_limit"])
        ].code.tolist()

        log.info(f"[{self.name}] 符合卖出条件: {sell_list}")

        for s in sell_list:
            if subpf.positions[s].closeable_amount > 0:
                self.order_target_value_(s, 0)
                log.info(f"[{self.name}] 卖出 {s}")

        log.info(f"[{self.name}] 卖出逻辑执行完成")

    def buy(self, context):
        """ST策略买入逻辑"""
        subpf = context.subportfolios[self.subportfolio_index]
        log.info("=" * 30 + f" [{self.name}] 开始执行买入逻辑 " + "=" * 30)

        target = g.st_today_list
        if not target:
            log.info(f"[{self.name}] 股票池为空，退出买入")
            return

        log.info(f"[{self.name}] 候选股票池: {target}")

        current_data = get_current_data()

        # 1. 获取昨日收盘价
        df = get_price(
            target,
            end_date=context.previous_date,
            frequency="daily",
            fields=["close"],
            count=1,
            panel=False,
            fill_paused=False,
            skip_paused=True,
        ).set_index("code")
        if df.empty:
            log.info(f"[{self.name}] 无昨日收盘价，退出买入")
            return

        # 2. 获取集合竞价价（9:23~9:25），失败则退化为day_open
        current_date_str = context.current_dt.strftime("%Y-%m-%d")
        try:
            ca = get_call_auction(
                target,
                start_date=current_date_str,
                end_date=current_date_str,
                fields=["time", "current"],
            )
            if ca is None or ca.empty:
                df["price_924"] = [current_data[s].day_open for s in df.index]
                log.info(f"[{self.name}] 无集合竞价数据，使用开盘价")
            else:
                ca["time"] = pd.to_datetime(ca["time"])
                mask = (ca["time"].dt.hour == 9) & (
                    ca["time"].dt.minute.between(23, 25)
                )
                filtered = ca[mask]
                if filtered.empty:
                    df["price_924"] = [current_data[s].day_open for s in df.index]
                    log.info(f"[{self.name}] 无9:23-9:25集合竞价数据，使用开盘价")
                else:
                    latest = (
                        filtered.sort_values(["code", "time"]).groupby("code").last()
                    )
                    price_924 = latest["current"].to_dict()
                    df["price_924"] = [price_924.get(s, None) for s in df.index]
        except Exception as e:
            log.error(f"[{self.name}] 获取集合竞价数据出错: {e}，改用开盘价")
            df["price_924"] = [current_data[s].day_open for s in df.index]

        df = df.dropna(subset=["price_924"])
        if df.empty:
            log.info(f"[{self.name}] 无有效集合竞价价格，退出买入")
            return

        # 3. 涨跌幅过滤
        df["pct_change"] = (df["price_924"] / df["close"] - 1) * 100
        df = df[(df["pct_change"] >= -4.9) & (df["pct_change"] <= 1.5)]
        candidates = list(df.index)
        if not candidates:
            log.info(f"[{self.name}] 无符合涨跌幅条件标的")
            return

        log.info(f"[{self.name}] 涨跌幅过滤后: {candidates}")

        # 4. 只对"新股票"建仓：老持仓不调仓
        hold_list = list(subpf.positions.keys())
        num_can_buy = self.stock_sum - len(hold_list)
        if num_can_buy <= 0:
            log.info(f"[{self.name}] 已持满 {self.stock_sum} 只，不再买入")
            return

        new_stocks = [s for s in candidates if s not in hold_list][:num_can_buy]
        if not new_stocks:
            log.info(f"[{self.name}] 候选股均已持有，不再新开仓")
            return

        log.info(f"[{self.name}] 可新开仓股票: {new_stocks}")

        # 5. 关键仓位逻辑：每只新买入固定 = 子账户总市值 / self.stock_sum
        sub_total_value = subpf.total_value
        target_per_stock_value = sub_total_value / float(self.stock_sum)

        log.info(
            f"[{self.name}] 子账户总市值: {sub_total_value:.2f} | "
            f"计划新开 {len(new_stocks)} 只 | "
            f"单只建仓目标市值: {target_per_stock_value:.2f}"
        )

        # 6. 下单（只对新标的开仓）
        for stock in new_stocks:
            if current_data[stock].paused:
                log.info(f"[{self.name}] 跳过 {stock}：停牌")
                continue
            if current_data[stock].last_price in (
                current_data[stock].low_limit,
                current_data[stock].high_limit,
            ):
                log.info(f"[{self.name}] 跳过 {stock}：涨跌停")
                continue

            self.order_target_value_(stock, target_per_stock_value)
            pct_change = df.loc[stock]["pct_change"]
            log.info(
                f"[{self.name}] 新建仓 {stock}："
                f"目标市值 {target_per_stock_value:.2f}，"
                f"集合竞价涨跌幅 {pct_change:.2f}%"
            )

        log.info("=" * 30 + f" [{self.name}] 买入逻辑执行完毕 " + "=" * 30)


# ==============================
# 五、子策略2：高股息策略（15%）
# ==============================


# 业绩披露窗口
EARNINGS_WINDOWS = [
    ((4, 25), (4, 30)),
    ((8, 25), (8, 30)),
    ((10, 25), (10, 31)),
]


def is_in_earnings_window(d):
    """检查是否在业绩披露窗口"""
    m, day = d.month, d.day
    for (sm, sd), (em, ed) in EARNINGS_WINDOWS:
        if sm == em and m == sm and sd <= day <= ed:
            return True
    return False


def calc_adjusted_profit_yoy(codes, ref_date):
    """计算扣非净利润同比增长率"""
    if not codes:
        return {}

    q_now = query(indicator.code, indicator.adjusted_profit).filter(
        indicator.code.in_(codes)
    )
    df_now = get_fundamentals(q_now, date=ref_date)
    now_map = (
        {row["code"]: row["adjusted_profit"] for _, row in df_now.iterrows()}
        if (df_now is not None and not df_now.empty)
        else {}
    )

    past_date = ref_date - datetime.timedelta(days=365)
    q_old = query(indicator.code, indicator.adjusted_profit).filter(
        indicator.code.in_(codes)
    )
    df_old = get_fundamentals(q_old, date=past_date)
    old_map = (
        {row["code"]: row["adjusted_profit"] for _, row in df_old.iterrows()}
        if (df_old is not None and not df_old.empty)
        else {}
    )

    yoy = {}
    for c in codes:
        cur = now_map.get(c, None)
        old = old_map.get(c, None)
        if (cur is None) or (old is None) or (old <= 0):
            yoy[c] = None
        else:
            try:
                yoy[c] = (cur - old) / abs(old) * 100.0
            except Exception:
                yoy[c] = None
    return yoy


def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2):
    """获取股息率筛选列表"""
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365 * 2)
    interval = 1000
    list_len = len(stock_list)

    q = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.a_registration_date,
        finance.STK_XR_XD.bonus_amount_rmb,
    ).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[: min(list_len, interval)]),
    )
    df = finance.run_query(q)

    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(
                finance.STK_XR_XD.code,
                finance.STK_XR_XD.a_registration_date,
                finance.STK_XR_XD.bonus_amount_rmb,
            ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(
                    stock_list[interval * (i + 1) : min(list_len, interval * (i + 2))]
                ),
            )
            temp_df = finance.run_query(q)
            df = df.append(temp_df)

    dividend = df.fillna(0)
    dividend = dividend.groupby("code").sum()
    temp_list = list(dividend.index)

    q = query(valuation.code, valuation.market_cap).filter(
        valuation.code.in_(temp_list)
    )
    cap = get_fundamentals(q, date=time1)
    cap = cap.set_index("code")

    DR = pd.concat([dividend, cap], axis=1)
    DR["dividend_ratio"] = (DR["bonus_amount_rmb"] / 10000) / DR["market_cap"]
    DR = DR.sort_values(by=["dividend_ratio"], ascending=sort)

    final_list = list(DR.index)[int(p1 * len(DR)) : int(p2 * len(DR))]
    return final_list


def peg_stock_by_adjusted_profit(context, stock_list, pegmin, pegmax):
    """PEG筛选"""
    if not stock_list:
        return []

    q = query(valuation.code, valuation.pe_ratio).filter(valuation.code.in_(stock_list))
    df_pe = get_fundamentals(q, date=context.previous_date)
    if df_pe is None or df_pe.empty:
        return []

    pe_map = {row["code"]: row["pe_ratio"] for _, row in df_pe.iterrows()}
    yoy_map = calc_adjusted_profit_yoy(stock_list, context.previous_date)

    res = []
    for code in stock_list:
        pe = pe_map.get(code, None)
        gr = yoy_map.get(code, None)
        if pe is None or gr is None:
            continue
        if gr <= 0:
            continue
        try:
            peg = pe / gr
        except Exception:
            continue
        if pegmin < peg < pegmax:
            res.append(code)
    return res


def filter_kcbj_stock(stock_list):
    """过滤科创板、北交所股票"""
    res = []
    for stock in stock_list:
        if stock[0] in ["4", "8"] or stock[:2] == "68":
            continue
        res.append(stock)
    return res


def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].paused]


def filter_st_stock(stock_list):
    """过滤ST股票"""
    current_data = get_current_data()
    return [
        s
        for s in stock_list
        if (not current_data[s].is_st)
        and ("ST" not in current_data[s].name)
        and ("*" not in current_data[s].name)
        and ("退" not in current_data[s].name)
    ]


def filter_limitup_stock(context, stock_list):
    """过滤涨停股票"""
    current_data = get_current_data()
    res = []
    for stock in stock_list:
        if stock in context.portfolio.positions.keys():
            res.append(stock)
        else:
            if current_data[stock].day_open < current_data[stock].high_limit:
                res.append(stock)
    return res


def filter_limitdown_stock(context, stock_list):
    """过滤跌停股票"""
    last_prices = history(1, unit="1m", field="close", security_list=stock_list)
    current_data = get_current_data()
    res = []
    for stock in stock_list:
        if stock in context.portfolio.positions.keys():
            res.append(stock)
        else:
            if last_prices[stock][-1] > current_data[stock].low_limit:
                res.append(stock)
    return res


def filter_excluded_industries(stock_list):
    """过滤特定行业"""
    excluded_codes = ["801180"]  # 房地产
    excluded_stocks = set()
    for code in excluded_codes:
        try:
            stocks = get_industry_stocks(code)
            excluded_stocks |= set(stocks)
        except Exception:
            pass
    return [s for s in stock_list if s not in excluded_stocks]


class Dividend_Strategy(Strategy):
    """
    高股息策略
    策略逻辑：筛选高股息、低PEG、扣非净利润增长的股票
    特点：价值投资，适合中长期持有
    """

    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 3  # 持仓3只股票
        log.info(f"[{self.name}] 初始化完成，最大持仓{self.stock_sum}只")

    def adjust_in_earnings_window(self, context):
        """业绩披露窗口触发调仓"""
        today = context.current_dt.date()
        if is_in_earnings_window(today):
            log.info(f"[{self.name}] 业绩披露窗口触发调仓")
            self.adjust(context)

    def adjust(self, context):
        """高股息策略调仓"""
        log.info(f"[{self.name}] 开始调仓 - 日期: {context.current_dt.strftime('%Y-%m-%d')}")

        # 全市场选股
        dt_last = context.previous_date
        stocks = get_all_securities("stock", dt_last).index.tolist()
        choice = filter_kcbj_stock(stocks)
        choice = filter_st_stock(choice)
        choice = filter_paused_stock(choice)
        choice = filter_limitup_stock(context, choice)
        choice = filter_limitdown_stock(context, choice)

        log.info(f"[{self.name}] 基础过滤后股票数: {len(choice)}")

        # 高股息前10%
        stock_list = get_dividend_ratio_filter_list(context, choice, False, 0, 0.1)
        log.info(f"[{self.name}] 高股息筛选后: {len(stock_list)}只")

        # PEG筛选
        stock_list = peg_stock_by_adjusted_profit(context, stock_list, 0.1, 2)
        log.info(f"[{self.name}] PEG筛选后: {len(stock_list)}只")

        # 行业过滤
        stock_list = filter_excluded_industries(stock_list)
        log.info(f"[{self.name}] 行业过滤后: {len(stock_list)}只")

        # 基本面筛选
        q = query(
            valuation.code,
            indicator.inc_total_revenue_year_on_year,
            indicator.inc_return,
        ).filter(
            valuation.code.in_(stock_list),
            indicator.inc_total_revenue_year_on_year > 4,
            indicator.inc_return > 4.5,
        )
        df = get_fundamentals(q)
        if df is None or df.empty:
            log.info(f"[{self.name}] 基本面筛选后无标的")
            return

        yoy_map = calc_adjusted_profit_yoy(list(df["code"]), context.previous_date)

        def _ok_adj_yoy(code):
            v = yoy_map.get(code, None)
            return (v is not None) and (v > 8.0)

        df = df[df["code"].apply(_ok_adj_yoy)].copy()
        if df.empty:
            log.info(f"[{self.name}] 扣非净利增速>8%后无标的")
            return

        stockset = list(df["code"])
        stock_list = stockset[: self.stock_sum]

        log.info(f"[{self.name}] 最终选股结果: {stock_list}")
        current_data = get_current_data()

        # 显示选股详细信息
        for code in stock_list:
            name = current_data[code].name if code in current_data else "未知"
            log.info(f"[{self.name}] 选中: {code} - {name}")

        # 卖出：不在stock_list且涨停打开的
        for s in list(self.subportfolio.positions.keys()):
            if (s not in stock_list) and (
                current_data[s].last_price < current_data[s].high_limit
            ):
                log.info(f"[{self.name}] 卖出 {s} - {current_data[s].name}")
                self.order_target_value_(s, 0)

        # 买入：等权
        position_count = len(self.subportfolio.positions)
        if self.stock_sum > position_count:
            psize = self.subportfolio.available_cash / (self.stock_sum - position_count)
            log.info(f"[{self.name}] 每只买入金额: {psize:.2f}")

            for s in stock_list:
                if s not in self.subportfolio.positions:
                    log.info(f"[{self.name}] 买入 {s} - {current_data[s].name}")
                    self.order_target_value_(s, psize)
                    if len(self.subportfolio.positions) == self.stock_sum:
                        break

        log.info(
            f"[{self.name}] 调仓完成，当前持仓: " f"{list(self.subportfolio.positions.keys())}"
        )


# ==============================
# 六、子策略3：ETF轮动策略（25%）
# ==============================


class ETF_Rotation_Strategy(Strategy):
    """
    ETF轮动策略
    策略逻辑：基于动量和均线过滤选择表现最好的ETF
    特点：低换手率，趋势跟踪
    """

    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 1  # 只持有一只ETF
        self.etf_pool = [
            "513100.XSHG",
            "159509.XSHE",
            "513520.XSHG",
            "513030.XSHG",  # 跨境/海外ETF
            "518880.XSHG",
            "159980.XSHE",
            "159985.XSHE",
            "159981.XSHE",
            "501018.XSHG",  # 商品ETF
            "511090.XSHG",  # 债券ETF
            "513130.XSHG",
            "513690.XSHG",
            "510180.XSHG",
            "159915.XSHE",
            "510410.XSHG",  # 宽基/行业ETF
            "515650.XSHG",
            "512290.XSHG",
            "588120.XSHG",
            "515070.XSHG",
            "159851.XSHE",  # 行业ETF
            "159637.XSHE",
            "516160.XSHG",
            "159550.XSHE",
            "512710.XSHG",
            "159692.XSHE",  # 行业ETF
            "512480.XSHG",
            "515250.XSHG",
            "159378.XSHE",
            "516510.XSHG",  # 行业ETF
            "515050.XSHG",
            "159995.XSHE",
            "515790.XSHG",
            "515000.XSHG",  # 科技/新能源ETF
        ]
        self.m_days = 25  # 动量计算天数
        self.min_money = 500  # 最小交易金额
        self.enable_volume_check = True  # 启用成交量检查
        self.volume_lookback = 5  # 成交量回看天数
        self.volume_threshold = 2.0  # 成交量阈值
        self.ma_filter_days = 20  # 均线过滤天数
        self.enable_ma_filter = True  # 启用均线过滤
        self.last_ma_log_date = None  # 最后均线日志日期
        self.last_ma_detail_log_date = None  # 最后均线详情日志日期

        log.info(f"[{self.name}] 初始化完成，ETF池{len(self.etf_pool)}只，动量天数{self.m_days}")

    def compute_momentum(self, context, etf_list):
        """计算ETF动量得分"""
        if not etf_list:
            return pd.DataFrame(columns=["annualized_returns", "r2", "score"])

        data = pd.DataFrame(
            index=etf_list,
            columns=["annualized_returns", "r2", "score"],
        )
        current_data = get_current_data()

        for etf in etf_list:
            try:
                df = attribute_history(etf, self.m_days, "1d", ["close", "high"])
                if df is None or df.empty:
                    continue

                prices = np.append(df["close"].values, current_data[etf].last_price)
                if len(prices) < 5:
                    continue

                y = np.log(prices)
                x = np.arange(len(y))
                weights = np.linspace(1, 2, len(y))  # 加权回归，近期权重更高
                slope, intercept = np.polyfit(x, y, 1, w=weights)
                annualized_returns = math.exp(slope * 250) - 1
                data.loc[etf, "annualized_returns"] = annualized_returns

                # 计算R²
                ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
                ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot else 0
                data.loc[etf, "r2"] = r2
                score = annualized_returns * r2

                # 如果近期有大幅下跌，分数设为0
                if (
                    len(prices) >= 4
                    and min(
                        prices[-1] / prices[-2],
                        prices[-2] / prices[-3],
                        prices[-3] / prices[-4],
                    )
                    < 0.95
                ):
                    score = 0
                data.loc[etf, "score"] = score
            except Exception as e:
                log.warning(f"[{self.name}] 计算 {etf} 动量失败: {e}")
                continue
        return data

    def get_single_score(self, context, etf):
        """获取单只ETF的动量得分"""
        df = self.compute_momentum(context, [etf])
        if etf in df.index:
            return df.loc[etf, "score"]
        return None

    def filter_below_ma(self, context, stocks, days=20, log_details=True):
        """过滤低于均线的股票"""
        if not stocks:
            return []

        current_data = get_current_data()
        filtered = []

        for stock in stocks:
            try:
                hist = attribute_history(stock, days, "1d", ["close"])
                if len(hist) < days:
                    continue

                ma_n = hist["close"].mean()
                price = current_data[stock].last_price

                if price >= ma_n:
                    filtered.append(stock)
                else:
                    if log_details:
                        log.debug(
                            f"[{self.name}] 过滤 {stock}: "
                            f"当前价 {price:.2f} < {days}日均价 {ma_n:.2f}"
                        )
            except Exception as e:
                if log_details:
                    log.warning(f"[{self.name}] 均线过滤失败 {stock}: {e}")
        return filtered

    def momentum_filter(self, context):
        """动量过滤：选择动量最强的ETF"""
        stocks = self.etf_pool
        if self.enable_ma_filter:
            today = context.current_dt.date()
            log_details = self.last_ma_detail_log_date != today
            stocks = self.filter_below_ma(
                context, stocks, self.ma_filter_days, log_details
            )
            if self.last_ma_log_date != today:
                log.debug(f"[{self.name}] 均线过滤后剩余 {len(stocks)} / {len(self.etf_pool)}")
                self.last_ma_log_date = today
            if log_details:
                self.last_ma_detail_log_date = today

        if not stocks:
            return []

        data = self.compute_momentum(context, stocks)
        data = data.query("0 < score < 5").sort_values(by="score", ascending=False)
        return data.index.tolist()

    def get_volume_ratio(self, context, security, lookback_days, threshold):
        """计算成交量比率"""
        try:
            hist = attribute_history(security, lookback_days, "1d", ["volume"])
            if hist.empty or len(hist) < lookback_days:
                return None

            avg_volume = hist["volume"].mean()
            today = context.current_dt.date()
            df_vol = get_price(
                security,
                start_date=today,
                end_date=context.current_dt,
                frequency="1m",
                fields=["volume"],
                skip_paused=False,
                fq="pre",
                panel=False,
                fill_paused=False,
            )
            if df_vol is None or df_vol.empty:
                return None

            current_volume = df_vol["volume"].sum()
            ratio = current_volume / avg_volume
            return ratio if ratio > threshold else None
        except Exception as e:
            log.warning(f"[{self.name}] 成交量检测失败 {security}: {e}")
            return None

    def morning_report(self, context):
        """ETF动量晨报"""
        data = self.compute_momentum(context, self.etf_pool)
        if data.empty:
            log.info(f"[{self.name}] 动量晨报：无数据")
            return

        data = data.sort_values(by="score", ascending=False)
        current_data = get_current_data()

        log.info("=" * 40 + f" [{self.name}] ETF动量晨报 " + "=" * 40)
        count = 0
        for code, row in data.iterrows():
            score = row.get("score")
            if pd.isna(score) or score <= 0:
                continue

            try:
                name = get_security_info(code).display_name
            except Exception:
                name = current_data[code].name if code in current_data else ""

            score_str = f"{score:.4f}" if score is not None else "N/A"
            annual_return = row.get("annualized_returns", 0)
            r2 = row.get("r2", 0)

            log.info(
                f"{code} | {name:10} | 动量得分: {score_str:8} | "
                f"年化收益: {annual_return:6.2%} | R²: {r2:.3f}"
            )
            count += 1
            if count >= 10:  # 只显示前10名
                break
        log.info("=" * 40 + " 晨报结束 " + "=" * 40)

    def adjust(self, context):
        """ETF轮动策略调仓"""
        log.info(f"[{self.name}] 开始调仓")

        self._prepare(context)
        targets = self.momentum_filter(context)[: self.stock_sum]

        if not targets:
            log.info(f"[{self.name}] 无目标ETF")
            return

        log.info(f"[{self.name}] 目标ETF: {targets}")

        subpf = self.subportfolio
        current_data = get_current_data()
        hold_list = list(subpf.long_positions.keys())

        # 1. 放量优先卖出
        if self.enable_volume_check:
            for stock in hold_list[:]:
                ratio = self.get_volume_ratio(
                    context, stock, self.volume_lookback, self.volume_threshold
                )
                if ratio is not None:
                    score = self.get_single_score(context, stock)
                    score_str = f"{score:.4f}" if score is not None else "N/A"
                    try:
                        name = get_security_info(stock).display_name
                    except Exception:
                        name = current_data[stock].name

                    log.info(
                        f"[{self.name}] 卖出 {stock} | {name} | "
                        f"动量 {score_str} | 放量比值 {ratio:.2f}"
                    )
                    self.order_target_value_(stock, 0)
                    if stock in hold_list:
                        hold_list.remove(stock)

        # 2. 不在目标池的卖出
        for stock in hold_list:
            if stock not in targets:
                score = self.get_single_score(context, stock)
                score_str = f"{score:.4f}" if score is not None else "N/A"
                try:
                    name = get_security_info(stock).display_name
                except Exception:
                    name = current_data[stock].name

                log.info(
                    f"[{self.name}] 卖出 {stock} | {name} | " f"动量 {score_str} | 理由：不在目标池"
                )
                self.order_target_value_(stock, 0)

        # 3. 买入/补仓
        total_value = context.portfolio.total_value
        target_total = (
            total_value * g.portfolio_value_proportion[self.subportfolio_index]
        )
        if target_total <= 0:
            log.info(f"[{self.name}] 目标市值为0，跳过买入")
            return

        self.balance_subportfolios(context)
        subpf = self.subportfolio

        for stock in targets:
            weight = 1.0 / len(targets)
            target_value = target_total * weight
            self.order_target_value_(stock, target_value)

            try:
                name = get_security_info(stock).display_name
            except Exception:
                name = current_data[stock].name

            log.info(f"[{self.name}] 买入 {stock} | {name} | 目标市值 {target_value:.2f}")

        log.info(f"[{self.name}] 调仓完成")


# ==============================
# 七、子策略4：单因子微盘股策略（15%）
# ==============================


def filter_limitup_stock_micro(context, stock_list):
    """过滤涨停股票（微盘股专用）"""
    last_prices = history(1, unit="1m", field="close", security_list=stock_list)
    current_data = get_current_data()
    res = []
    for stock in stock_list:
        if stock in context.portfolio.positions.keys():
            res.append(stock)
        else:
            if last_prices[stock][-1] < current_data[stock].high_limit:
                res.append(stock)
    return res


def filter_limitdown_stock_micro(context, stock_list):
    """过滤跌停股票（微盘股专用）"""
    last_prices = history(1, unit="1m", field="close", security_list=stock_list)
    current_data = get_current_data()
    res = []
    for stock in stock_list:
        if stock in context.portfolio.positions.keys():
            res.append(stock)
        else:
            if last_prices[stock][-1] > current_data[stock].low_limit:
                res.append(stock)
    return res


def filter_new_stock_micro(context, stock_list):
    """过滤次新股（上市不足375天）"""
    yesterday = context.previous_date
    return [
        stock
        for stock in stock_list
        if yesterday - get_security_info(stock).start_date
        >= datetime.timedelta(days=375)
    ]


class Microcap_SingleFactor_Strategy(Strategy):
    """
    单因子微盘股策略
    策略逻辑：专注于小市值股票，使用单一因子（成交额）进行选股
    特点：高风险高波动，适合风险偏好较高的投资者
    """

    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.stock_sum = 1  # 只持有一只股票
        log.info(f"[{self.name}] 初始化完成，专注小市值股票")

    def update_pool(self, context):
        """更新股票池：选择小市值股票"""
        zxz_index = "399101.XSHE"  # 中小板指数
        zxz_stocks = get_index_stocks(zxz_index)
        filtered = filter_new_stock_micro(context, zxz_stocks)
        filtered = filter_kcbj_stock(filtered)
        filtered = filter_st_stock(filtered)

        log.info(f"[{self.name}] 基础过滤后股票数: {len(filtered)}")

        # 筛选小市值股票
        df = get_fundamentals(
            query(
                valuation.code,
                valuation.market_cap,
                valuation.circulating_market_cap,
            ).filter(valuation.code.in_(filtered))
        )

        # 选择总市值最小的23只和流通市值最小的99只，取交集
        df_market = df.sort_values("market_cap", ascending=True).head(23)
        df_circ = df.sort_values("circulating_market_cap", ascending=True).head(99)
        market_set = set(df_market["code"].tolist())
        circ_set = set(df_circ["code"].tolist())
        common = market_set & circ_set
        g.microcap_stock_pool = list(common)

        log.info(f"[{self.name}] 更新股票池: {len(g.microcap_stock_pool)}只")
        if len(g.microcap_stock_pool) > 0:
            log.info(f"[{self.name}] 股票池示例: {g.microcap_stock_pool[:5]}")

    def select_stock(self, context):
        """选择股票：基于20日平均成交额"""
        stock_list = g.microcap_stock_pool
        if not stock_list:
            log.info(f"[{self.name}] 股票池为空")
            return None

        stock_list = filter_paused_stock(stock_list)
        stock_list = filter_limitup_stock_micro(context, stock_list)
        stock_list = filter_limitdown_stock_micro(context, stock_list)

        log.info(f"[{self.name}] 交易过滤后股票数: {len(stock_list)}")

        # 1、4、12月进行基本面过滤
        today = context.current_dt.date()
        if today.month in [1, 4, 12]:
            fundamentals = get_fundamentals(
                query(
                    valuation.code,
                    income.net_profit,
                    indicator.roa,
                ).filter(
                    valuation.code.in_(stock_list),
                    income.net_profit > 0,
                    indicator.roa > 0,
                ),
                date=context.previous_date,
            )
            stock_list = fundamentals["code"].tolist()
            log.info(f"[{self.name}] 基本面过滤后股票数: {len(stock_list)}")
            if not stock_list:
                return None

        # 计算20日平均成交额，选择最小的
        amount_dict = {}
        for stock in stock_list:
            df = get_price(
                stock,
                end_date=context.previous_date,
                frequency="daily",
                fields="money",
                count=20,
                skip_paused=True,
            )
            if df is None or df.empty:
                continue
            amount_dict[stock] = df["money"].mean()

        if not amount_dict:
            log.info(f"[{self.name}] 无成交额数据")
            return None

        sorted_stocks = sorted(amount_dict.keys(), key=lambda x: amount_dict[x])
        selected = sorted_stocks[0]

        # 显示选择结果
        current_data = get_current_data()
        name = current_data[selected].name if selected in current_data else "未知"
        avg_amount = amount_dict[selected] / 10000  # 转换为万元
        log.info(
            f"[{self.name}] 选中股票: {selected} - {name}, " f"20日均成交额: {avg_amount:.2f}万元"
        )

        return selected

    def adjust(self, context):
        """单因子小市值策略调仓"""
        log.info(f"[{self.name}] 开始调仓")

        subpf = self.subportfolio
        hold_list = list(subpf.long_positions.keys())
        target_stock = self.select_stock(context)

        if not target_stock:
            log.info(f"[{self.name}] 无目标股票，保持现有持仓")
            return

        # 如果当前没有持仓，直接买入
        if not hold_list:
            value = subpf.total_value
            self.order_target_value_(target_stock, value)

            current_data = get_current_data()
            name = (
                current_data[target_stock].name
                if target_stock in current_data
                else "未知"
            )
            log.info(f"[{self.name}] 首次建仓: {target_stock} - {name}，金额: {value:.2f}")
            return

        # 比较当前持仓和目标股票的涨幅
        current_stock = hold_list[0]
        current_df = get_price(
            current_stock,
            end_date=context.previous_date,
            count=6,
            frequency="1d",
            fields="close",
        )
        target_df = get_price(
            target_stock,
            end_date=context.previous_date,
            count=6,
            frequency="1d",
            fields="close",
        )

        if current_df is None or len(current_df) < 2:
            log.info(f"[{self.name}] 当前持仓无价格数据")
            return
        if target_df is None or len(target_df) < 2:
            log.info(f"[{self.name}] 目标股票无价格数据")
            return

        current_pct = (current_df["close"][-1] - current_df["close"][0]) / current_df[
            "close"
        ][0]
        target_pct = (target_df["close"][-1] - target_df["close"][0]) / target_df[
            "close"
        ][0]

        current_data = get_current_data()
        current_name = (
            current_data[current_stock].name if current_stock in current_data else "未知"
        )
        target_name = (
            current_data[target_stock].name if target_stock in current_data else "未知"
        )

        # 如果目标股票表现更好，则换仓
        if target_pct < current_pct:
            self.order_target_value_(current_stock, 0)
            log.info(
                f"[{self.name}] 卖出 {current_stock} - {current_name} "
                f"涨幅{current_pct * 100:.2f}% > "
                f"目标 {target_stock} - {target_name} 涨幅{target_pct * 100:.2f}%"
            )
            value = self.subportfolio.total_value
            self.order_target_value_(target_stock, value)
            log.info(f"[{self.name}] 买入 {target_stock} - {target_name}，金额: {value:.2f}")
        else:
            log.info(
                f"[{self.name}] 不换仓：当前 {current_stock} - {current_name} "
                f"涨幅{current_pct * 100:.2f}% >= "
                f"目标 {target_stock} - {target_name} 涨幅{target_pct * 100:.2f}%"
            )

        log.info(f"[{self.name}] 调仓完成")


# ==============================
# 八、子策略5：国九条小市值策略（22%）——简化版
# ==============================


def get_security_universe_all(context):
    """获取全市场股票"""
    return list(get_all_securities(["stock"], context.current_dt.date()).index)


def get_current_data_safe(current_data, security):
    """安全获取当前行情对象，无法识别的证券返回None。"""
    try:
        return current_data[security]
    except Exception:
        return None


def paused_filter(context, security_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    securities = []
    for s in security_list:
        data = get_current_data_safe(current_data, s)
        if data is not None and not data.paused:
            securities.append(s)
    return securities


def delisted_filter(context, security_list):
    """过滤退市股票"""
    current_data = get_current_data()
    securities = []
    for s in security_list:
        data = get_current_data_safe(current_data, s)
        if data is not None and not (("退" in data.name) or ("*" in data.name)):
            securities.append(s)
    return securities


def st_filter(context, security_list):
    """过滤ST股票"""
    current_data = get_current_data()
    securities = []
    for s in security_list:
        data = get_current_data_safe(current_data, s)
        if data is not None and not data.is_st and "ST" not in data.name:
            securities.append(s)
    return securities


def industry_filter(context, security_list, industry_list):
    """行业过滤"""
    if not industry_list:
        return security_list

    securities = []
    for s in industry_list:
        try:
            temp = get_industry_stocks(s)
            securities += temp
        except Exception:
            pass
    return [stock for stock in security_list if stock in securities]


def get_industry_stocks_by_names(industry_names, date_value=None):
    """按聚宽行业名称匹配行业代码，并获取行业成分股。"""
    industry_names = [str(name) for name in industry_names if name]
    if not industry_names:
        return []

    stocks = []
    for industry_type in ["sw_l1", "sw_l2", "sw_l3", "jq_l1", "jq_l2"]:
        try:
            industries = get_industries(industry_type, date=date_value)
        except Exception:
            continue
        if industries is None or industries.empty:
            continue

        for code, row in industries.iterrows():
            try:
                industry_name = str(row.get("name", ""))
            except Exception:
                industry_name = ""
            if not any(name in industry_name for name in industry_names):
                continue
            try:
                stocks.extend(get_industry_stocks(code, date=date_value))
            except Exception:
                pass

    return list(dict.fromkeys(stocks))


def get_concept_stocks_by_names(concept_names, date_value=None):
    """按聚宽概念名称匹配概念代码，并获取概念成分股。"""
    concept_names = [str(name) for name in concept_names if name]
    if not concept_names:
        return []

    try:
        concepts = get_concepts(date=date_value)
    except Exception:
        return []
    if concepts is None or concepts.empty:
        return []

    stocks = []
    for code, row in concepts.iterrows():
        try:
            concept_name = str(row.get("name", ""))
        except Exception:
            concept_name = ""
        if not any(name in concept_name for name in concept_names):
            continue
        try:
            stocks.extend(get_concept_stocks(code, date=date_value))
        except Exception:
            pass

    return list(dict.fromkeys(stocks))


class Microcap_GJT_Strategy(Strategy):
    """
    国九条小市值策略
    策略逻辑：结合国九条政策，筛选符合政策导向的小市值股票
    特点：政策驱动，注重基本面和行业选择
    """

    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        # 个股最大持仓比（这里由子账户控制，不额外限制）
        self.security_max_proportion = 1
        self.max_hold_stocknum = 3  # 最大持仓3只
        self.sell_rank = 7  # 卖出排名阈值
        self.industry_list = [  # 允许的行业列表
            "801120",
            "801150",
            "801980",
            "801010",
            "801130",
            "801140",
            "801200",
            "801210",  # 消费、医疗
            "801030",
            "801050",
            "801070",
            "801090",
            "801730",
            "801740",
            "801880",
            "801890",  # 制造、科技
            "801750",
            "801760",
            "801770",
            "801080",
            "801100",
            "801220",  # 服务、其他
        ]
        self.check_stocks_days = 1  # 检查天数计数器
        self.check_stocks_refresh_rate = 1  # 检查刷新率
        self.buy_refresh_rate = 1  # 买入刷新率
        self.sell_refresh_rate = 1  # 卖出刷新率
        self.buy_trade_days = 1  # 买入交易日计数器
        self.sell_trade_days = 1  # 卖出交易日计数器

        log.info(
            f"[{self.name}] 初始化完成，最大持仓{self.max_hold_stocknum}只，"
            f"关注行业{len(self.industry_list)}个"
        )

    def check_stocks(self, context):
        """检查股票：基础过滤"""
        if self.check_stocks_days % self.check_stocks_refresh_rate != 0:
            self.check_stocks_days += 1
            return

        log.info(f"[{self.name}] 开始股票检查")

        stock_universe = get_security_universe_all(context)
        stock_universe = industry_filter(context, stock_universe, self.industry_list)
        stock_universe = st_filter(context, stock_universe)
        stock_universe = paused_filter(context, stock_universe)
        stock_universe = delisted_filter(context, stock_universe)
        g.gjt_check_out_lists = [s for s in stock_universe if s not in g.gjt_blacklist]
        self.check_stocks_days = 1

        log.info(f"[{self.name}] 股票检查完成，候选股票: {len(g.gjt_check_out_lists)}只")

    def main_pick(self, context):
        """主选股逻辑"""
        # 只保留深市中小板（000开头）
        check_list = [s for s in g.gjt_check_out_lists if s.startswith("0")]

        log.info(f"[{self.name}] 深市中小板股票: {len(check_list)}只")

        # 基本面筛选：净利润为正，营收过亿，按市值排序
        q = (
            query(valuation.code)
            .filter(
                valuation.code.in_(check_list),
                income.np_parent_company_owners > 0,
                income.net_profit > 0,
                indicator.adjusted_profit > 0,
                income.operating_revenue > 1e8,
            )
            .order_by(valuation.market_cap.asc())
            .limit(self.max_hold_stocknum * 5)
        )

        df = get_fundamentals(q)
        if df is None or df.empty:
            log.info(f"[{self.name}] 基本面筛选后无股票")
            g.gjt_sell_stock_list = []
            g.gjt_buy_stock_list = []
            return

        final_list = df["code"].tolist()
        stockset = final_list[:20]
        stockset = [s for s in stockset if s not in g.gjt_notbuy]

        log.info(f"[{self.name}] 基本面筛选后股票: {stockset}")

        # 卖出列表逻辑
        subpf = self.subportfolio
        g.gjt_sell_stock_list = []
        g.gjt_ZT = []
        sell_stock_list1 = list(subpf.positions.keys())
        current_data = get_current_data()

        for stock in sell_stock_list1:
            df2 = attribute_history(
                stock,
                count=2,
                unit="1d",
                fields=[
                    "open",
                    "close",
                    "volume",
                    "high",
                    "low",
                    "money",
                    "high_limit",
                    "low_limit",
                    "paused",
                ],
                fq="pre",
            )
            if current_data[stock].paused:
                continue
            elif df2["close"][-1] == df2["high_limit"][-1]:
                g.gjt_ZT.append(stock)  # 昨日涨停
            elif (stock not in stockset[: self.sell_rank]) and (stock not in g.gjt_ZT):
                g.gjt_sell_stock_list.append(stock)

        # 买入列表逻辑
        g.gjt_buy_stock_list = []
        for stock in stockset[: self.max_hold_stocknum]:
            if stock not in g.gjt_sell_stock_list:
                g.gjt_buy_stock_list.append(stock)

        log.info(f"[{self.name}] 卖出列表: {g.gjt_sell_stock_list}")
        log.info(f"[{self.name}] 买入列表: {g.gjt_buy_stock_list}")
        log.info(f"[{self.name}] 涨停列表: {g.gjt_ZT}")

    def no_zt_sell(self, context):
        """非涨停卖出：检查涨停是否打开"""
        current_data = get_current_data()

        for stock in g.gjt_ZT:
            df2 = attribute_history(
                stock, count=1, unit="1m", fields=["close", "high_limit"], fq="pre"
            )
            if df2["close"][-1] == df2["high_limit"][-1]:
                continue
            else:
                self.order_target_value_(stock, 0)
                g.gjt_notbuy.append(stock)
                log.info(f"[{self.name}] 涨停打开，卖出 {stock}，加入不买入列表")

    def trade(self, context):
        """交易执行"""
        log.info(f"[{self.name}] 开始交易")

        subpf = self.subportfolio
        buy_lists = []

        # 买入逻辑
        if self.buy_trade_days % self.buy_refresh_rate == 0:
            buy_lists = g.gjt_buy_stock_list
            current_data = get_current_data()
            buy_lists = [
                s
                for s in buy_lists
                if not (current_data[s].last_price >= current_data[s].high_limit)
            ]
            log.info(f"[{self.name}] 最终买入列表: {buy_lists}")

        # 卖出逻辑
        if self.sell_trade_days % self.sell_refresh_rate != 0:
            self.sell_trade_days += 1
        else:
            sell_lists = g.gjt_sell_stock_list
            for stock in sell_lists:
                log.info(f"[{self.name}] 卖出 {stock}")
                self.order_target_value_(stock, 0)
            self.sell_trade_days = 1

        # 买入执行
        if self.buy_trade_days % self.buy_refresh_rate != 0:
            self.buy_trade_days += 1
        else:
            num = self.max_hold_stocknum - len(subpf.positions)
            buy_lists = buy_lists[:num]

            for stock in buy_lists:
                if stock in subpf.positions:
                    continue
                if len(subpf.positions) < self.max_hold_stocknum:
                    value = subpf.cash / (self.max_hold_stocknum - len(subpf.positions))
                    self.order_target_value_(stock, value)

                    current_data = get_current_data()
                    name = current_data[stock].name if stock in current_data else "未知"
                    log.info(f"[{self.name}] 买入 {stock} - {name}，金额: {value:.2f}")

            self.buy_trade_days = 1

        log.info(f"[{self.name}] 交易完成，当前持仓: {list(subpf.positions.keys())}")


class Tech_Stock_Strategy(Microcap_GJT_Strategy):
    """
    科技股策略
    策略逻辑：沿用国九条小市值基本面筛选，股票池限定在科技行业和科技主题概念。
    """

    def __init__(self, context, subportfolio_index, name):
        super().__init__(context, subportfolio_index, name)
        self.allowed_prefixes = ("0", "3", "6")
        self.industry_names = ["电子", "计算机", "通信", "传媒", "国防军工"]
        self.concept_names = ["半导体", "机器人", "人工智能", "商业航天", "存储半导体", "光通信"]
        log.info(
            f"[{self.name}] 科技股票池初始化完成，行业{len(self.industry_names)}个，"
            f"概念{len(self.concept_names)}个"
        )

    def check_stocks(self, context):
        """检查股票：科技行业和概念股票池过滤"""
        if self.check_stocks_days % self.check_stocks_refresh_rate != 0:
            self.check_stocks_days += 1
            return

        log.info(f"[{self.name}] 开始科技股票检查")

        date_value = context.current_dt.date()
        industry_stocks = get_industry_stocks_by_names(self.industry_names, date_value)
        concept_stocks = get_concept_stocks_by_names(self.concept_names, date_value)
        stock_universe = list(dict.fromkeys(industry_stocks + concept_stocks))
        if not stock_universe:
            log.info(f"[{self.name}] 科技行业/概念股票池为空，退回全市场后按代码前缀过滤")
            stock_universe = get_security_universe_all(context)

        stock_universe = [s for s in stock_universe if s.startswith(self.allowed_prefixes)]
        stock_universe = st_filter(context, stock_universe)
        stock_universe = paused_filter(context, stock_universe)
        stock_universe = delisted_filter(context, stock_universe)
        g.tech_check_out_lists = [s for s in stock_universe if s not in g.tech_blacklist]
        self.check_stocks_days = 1

        log.info(
            f"[{self.name}] 科技股票检查完成，行业池={len(industry_stocks)}只，"
            f"概念池={len(concept_stocks)}只，候选股票={len(g.tech_check_out_lists)}只"
        )

    def main_pick(self, context):
        """主选股逻辑"""
        check_list = [s for s in g.tech_check_out_lists if s.startswith(self.allowed_prefixes)]

        log.info(f"[{self.name}] 科技候选股票: {len(check_list)}只")

        q = (
            query(valuation.code)
            .filter(
                valuation.code.in_(check_list),
                income.np_parent_company_owners > 0,
                income.net_profit > 0,
                indicator.adjusted_profit > 0,
                income.operating_revenue > 1e8,
            )
            .order_by(valuation.market_cap.asc())
            .limit(self.max_hold_stocknum * 5)
        )

        df = get_fundamentals(q)
        if df is None or df.empty:
            log.info(f"[{self.name}] 基本面筛选后无股票")
            g.tech_sell_stock_list = []
            g.tech_buy_stock_list = []
            return

        final_list = df["code"].tolist()
        stockset = final_list[:20]
        stockset = [s for s in stockset if s not in g.tech_notbuy]

        log.info(f"[{self.name}] 基本面筛选后股票: {stockset}")

        subpf = self.subportfolio
        g.tech_sell_stock_list = []
        g.tech_ZT = []
        sell_stock_list1 = list(subpf.positions.keys())
        current_data = get_current_data()

        for stock in sell_stock_list1:
            df2 = attribute_history(
                stock,
                count=2,
                unit="1d",
                fields=[
                    "open",
                    "close",
                    "volume",
                    "high",
                    "low",
                    "money",
                    "high_limit",
                    "low_limit",
                    "paused",
                ],
                fq="pre",
            )
            if current_data[stock].paused:
                continue
            elif df2["close"][-1] == df2["high_limit"][-1]:
                g.tech_ZT.append(stock)
            elif (stock not in stockset[: self.sell_rank]) and (stock not in g.tech_ZT):
                g.tech_sell_stock_list.append(stock)

        g.tech_buy_stock_list = []
        for stock in stockset[: self.max_hold_stocknum]:
            if stock not in g.tech_sell_stock_list:
                g.tech_buy_stock_list.append(stock)

        log.info(f"[{self.name}] 卖出列表: {g.tech_sell_stock_list}")
        log.info(f"[{self.name}] 买入列表: {g.tech_buy_stock_list}")
        log.info(f"[{self.name}] 涨停列表: {g.tech_ZT}")

    def no_zt_sell(self, context):
        """非涨停卖出：检查涨停是否打开"""
        for stock in g.tech_ZT:
            df2 = attribute_history(
                stock, count=1, unit="1m", fields=["close", "high_limit"], fq="pre"
            )
            if df2["close"][-1] == df2["high_limit"][-1]:
                continue
            self.order_target_value_(stock, 0)
            g.tech_notbuy.append(stock)
            log.info(f"[{self.name}] 涨停打开，卖出 {stock}，加入不买入列表")

    def trade(self, context):
        """交易执行"""
        log.info(f"[{self.name}] 开始交易")

        subpf = self.subportfolio
        buy_lists = []

        if self.buy_trade_days % self.buy_refresh_rate == 0:
            buy_lists = g.tech_buy_stock_list
            current_data = get_current_data()
            buy_lists = [
                s
                for s in buy_lists
                if not (current_data[s].last_price >= current_data[s].high_limit)
            ]
            log.info(f"[{self.name}] 最终买入列表: {buy_lists}")

        if self.sell_trade_days % self.sell_refresh_rate != 0:
            self.sell_trade_days += 1
        else:
            for stock in g.tech_sell_stock_list:
                log.info(f"[{self.name}] 卖出 {stock}")
                self.order_target_value_(stock, 0)
            self.sell_trade_days = 1

        if self.buy_trade_days % self.buy_refresh_rate != 0:
            self.buy_trade_days += 1
        else:
            num = self.max_hold_stocknum - len(subpf.positions)
            buy_lists = buy_lists[:num]

            for stock in buy_lists:
                if stock in subpf.positions:
                    continue
                if len(subpf.positions) < self.max_hold_stocknum:
                    value = subpf.cash / (self.max_hold_stocknum - len(subpf.positions))
                    self.order_target_value_(stock, value)

                    current_data = get_current_data()
                    name = current_data[stock].name if stock in current_data else "未知"
                    log.info(f"[{self.name}] 买入 {stock} - {name}，金额: {value:.2f}")

            self.buy_trade_days = 1

        log.info(f"[{self.name}] 交易完成，当前持仓: {list(subpf.positions.keys())}")