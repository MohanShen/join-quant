# Clone from JoinQuant
# postId: 42b92894d6286dde7ecc0f1546285185
# backtestId: 08cae37d47def6faac36eea783bcdc11
# title: 养家糊口|年化38回撤5以内|用经典优化模型优化权重

# 克隆自聚宽文章：https://www.joinquant.com/post/58095 
# 标题：10年11倍，最大回撤10%
# 作者：dongli
# 克隆自聚宽文章：https://www.joinquant.com/post/56156 
# 标题：多策略组合权重动态调整优化-胜率更高，夏普更高
# 作者：sharp3000
# 克隆自聚宽文章：https://www.joinquant.com/post/56106 
# 标题：多策略组合等权重优化
# 作者：STS1

from jqdata import *
from jqfactor import get_factor_values
import datetime
import math
from scipy.optimize import minimize
import pandas as pd
import numpy as np

class LogUtils:
    """日志工具类"""
    @staticmethod
    def log_strategy_info(context, strategy_name, action, details):
        """记录策略信息"""
        #log.info(f"[{strategy_name}] {action}: {details}")
        pass

    @staticmethod
    def log_trade_info(context, strategy_name, security, action, amount, price, value):
        """记录交易信息"""
        #log.info(f"[{strategy_name}] {action} {security}: 数量={amount}, 价格={price:.2f}, 市值={value:.2f}")
        pass
    
    @staticmethod
    def log_portfolio_info(context):
        """记录组合信息"""
        total_value = context.portfolio.total_value
        cash = context.portfolio.available_cash
        #log.info(f"=== 组合信息 ===")
        #log.info(f"总资产: {total_value:.2f}")
        #log.info(f"可用现金: {cash:.2f}")
        # 计算各策略持仓情况
        for i, strategy in enumerate(g.strategys.values()):
            strategy_value = strategy.get_total_value()
            proportion = strategy_value / total_value if total_value > 0 else 0
            #log.info(f"{strategy.name}: 市值={strategy_value:.2f}, 占比={proportion:.2%}")
    
    @staticmethod
    def log_performance_info(context, strategy_name, start_date=None):
        """记录策略表现"""
        try:
            if start_date is None:
                start_date = context.previous_date - datetime.timedelta(days=30)
            # 计算策略收益率
            strategy = g.strategys[strategy_name]
            current_value = strategy.get_total_value()
            initial_value = get_initial_value(strategy_name, start_date)
            if initial_value > 0:
                returns = (current_value - initial_value) / initial_value
            else:
                returns = 0.0
            LogUtils.log_strategy_info(context, strategy_name, "收益率计算", 
                f"当前价值: {current_value:.2f}, 初始价值: {initial_value:.2f}, 收益率: {returns:.2%}")
            return returns
        except Exception as e:
            LogUtils.log_strategy_info(context, strategy_name, "收益率计算失败", 
                f"错误: {str(e)}")
            return 0.0

class PortfolioManager:
    """组合管理类，负责动态调整策略权重"""
    def __init__(self, context):
        self.context = context
        self.strategy_weights = [0.3, 0.2, 0.1, 0.1, 0.3]  # 初始权重
        self.strategy_names = ["搅屎棍策略", "全天候策略", "简单ROA策略", "弱周期价投策略", "核心资产轮动策略"]
        self.volatility_window = 20  # 历史窗口
        self.max_weight = 0.3  # 单个策略最大权重
        self.min_weight = 0.05  # 单个策略最小权重
        self.last_adjust_date = None  # 上次调整日期
        self.history_values = {}  # 存储历史市值数据
    
    def get_strategy_value_at_date(self, strategy_name, date):
        """获取策略在指定日期的市值"""
        try:
            # 获取策略持仓
            strategy = g.strategys[strategy_name]
            positions = g.positions[strategy.index]
            if not positions:
                return 0.0
            # 获取持仓股票的历史价格
            stocks = list(positions.keys())
            df = get_price(stocks, end_date=date, frequency="1d", 
                         fields=["close"], count=1, panel=False)
            if df.empty:
                return 0.0
            # 计算持仓市值
            total_value = 0.0
            for stock in stocks:
                if stock in df.code.values:
                    price = df[df.code == stock]["close"].iloc[0]
                    amount = positions[stock]
                    total_value += price * amount
            return total_value
        except Exception as e:
            LogUtils.log_strategy_info(self.context, "组合管理", "历史数据获取失败", 
                f"{strategy_name}在{date}的数据获取失败: {str(e)}")
            return None

    def get_strategy_returns(self, strategy_name, window=252):
        """获取策略过去window天的收益率序列"""
        returns = []
        for i in range(window):
            date = self.context.previous_date - datetime.timedelta(days=i)
            value = self.get_strategy_value_at_date(strategy_name, date)
            if value is not None and value > 0:
                returns.append(value)
        if len(returns) < 2:
            # 输出警告信息，便于调试
            LogUtils.log_strategy_info(self.context, "组合管理", "历史数据不足", 
                f"{strategy_name} 的历史数据不足，可能影响权重计算")
            return np.array([0.0001] * window)
        returns = np.diff(returns) / returns[:-1]
        return returns

    def calculate_expected_returns(self):
        """计算各策略的预期收益（历史均值）"""
        expected_returns = []
        for name in self.strategy_names:
            r = self.get_strategy_returns(name)
            expected_returns.append(np.mean(r))
        return np.array(expected_returns)

    def calculate_covariance_matrix(self):
        """计算策略之间的协方差矩阵（年化）"""
        returns = []
        for name in self.strategy_names:
            r = self.get_strategy_returns(name)
            returns.append(r)
        # 转换为二维数组（n_days × n_strategies）
        returns = np.array(returns).T  # 形状: (window, n_assets)
        # 计算日协方差矩阵
        daily_cov = np.cov(returns, rowvar=False)  # rowvar=False 表示列是变量
        # 年化协方差矩阵
        annualized_cov = daily_cov
        # 添加正则化项（防止矩阵奇异）
        epsilon = 1e-4
        annualized_cov += np.eye(annualized_cov.shape[0]) * epsilon
        return annualized_cov

    def optimize_weights(self, mu, cov_matrix):
        """使用 Markowitz 均值-方差模型优化权重"""
        n_assets = len(mu)
        init_weights = [0.2, 0.2, 0.2, 0.2, 0.2]
    
        def objective(weights):
            return np.dot(weights.T, np.dot(cov_matrix, weights))
        #def objective(weights):
        #    portfolio_return = np.dot(weights, mu)
        #    portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        #    sharpe_ratio = portfolio_return / portfolio_volatility  # 假设无风险利率为0
        #    return -sharpe_ratio  # 最大化夏普比率
    
        constraints = (
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},  # 权重和为1
        )
        bounds = tuple((self.min_weight, self.max_weight) for _ in range(n_assets))
    
        result = minimize(objective, init_weights, method='SLSQP', bounds=bounds, constraints=constraints, tol=1e-8, options={'maxiter': 100})  # 增加最大迭代次数)
        if not result.success:
            LogUtils.log_strategy_info(self.context, "组合管理", "优化失败", 
                f"优化未收敛，原因: {result.message}")
        log.info(mu)
        log.info(cov_matrix)
        log.info(result)
        return result.x

def adjust_portfolio_weights(context):
    """使用 Markowitz 均值-方差模型调整策略权重"""
    if g.portfolio_manager.last_adjust_date is not None and \
       (context.current_dt - g.portfolio_manager.last_adjust_date).days < 20:
        LogUtils.log_strategy_info(context, "组合管理", "跳过调整", 
            f"上次调整日期: {g.portfolio_manager.last_adjust_date}, 间隔不足20天")
        return

    try:
        pm = g.portfolio_manager
        strategy_names = pm.strategy_names

        # 获取预期收益和协方差矩阵
        mu = pm.calculate_expected_returns()
        cov = pm.calculate_covariance_matrix()
        LogUtils.log_strategy_info(context, "组合管理", "预期收益", f"{mu}")
        LogUtils.log_strategy_info(context, "组合管理", "协方差矩阵", f"{cov}")
        weights = pm.optimize_weights(mu, cov)
        LogUtils.log_strategy_info(context, "组合管理", "优化权重", f"{weights}")

        # 平滑调整
        new_weights = []
        for i, name in enumerate(strategy_names):
            current_weight = pm.strategy_weights[i]
            target_weight = weights[i]
            adjustment = min(0.1, abs(target_weight - current_weight))
            if target_weight > current_weight:
                new_weight = current_weight + adjustment
            else:
                new_weight = current_weight - adjustment
            new_weight = max(pm.min_weight, min(pm.max_weight, new_weight))
            new_weights.append(new_weight)

        # 归一化
        total_weight = sum(new_weights)
        final_weights = [w / total_weight for w in new_weights]

        pm.strategy_weights = final_weights
        g.portfolio_value_proportion = final_weights
        pm.last_adjust_date = context.current_dt

        LogUtils.log_strategy_info(context, "组合管理", "权重更新", f"全局权重已更新: {final_weights}")
    except Exception as e:
        LogUtils.log_strategy_info(context, "组合管理", "权重调整失败", f"错误: {str(e)}")

# 初始化函数，设定基准等参数
def initialize(context):
    """初始化函数"""
    # 设定沪深300作为基准
    # set_benchmark("515080.XSHG")
    # 开启防未来函数
    set_option("avoid_future_data", True)
    # 开启动态复权模式(真实价格)
    set_option("use_real_price", True)
    log.info("初始函数开始运行且全局只运行一次")
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level("order", "error")
    # 固定滑点设置ETF 0.001(即交易对手方一档价)
    set_slippage(FixedSlippage(0.002), type="fund")
    # 股票交易总成本0.3%(含固定滑点0.02)
    set_slippage(FixedSlippage(0.02), type="stock")
    set_order_cost(OrderCost(open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5), type="stock")
    # 设置货币ETF交易佣金0
    set_order_cost(OrderCost(open_tax=0,
        close_tax=0,
        open_commission=0,
        close_commission=0,
        close_today_commission=0,
        min_commission=0), type="mmf")
    # 全局变量设置
    g.fill_stock = "511880.XSHG"  # 货币ETF，用于现金管理
    g.portfolio_value_proportion = [0.2, 0.2, 0.2, 0.2, 0.2]  # 等权重版
    g.positions = {i: {} for i in range(len(g.portfolio_value_proportion))}  # 记录每个子策略的持仓股票
    g.jsg_signal = True  # 搅屎棍开仓信号
    # 子策略执行计划配置
    if g.portfolio_value_proportion[0] > 0:
        run_weekly(jsg_adjust_wrapper, 1, "11:00")
        run_daily(jsg_check_wrapper, "14:50")
    if g.portfolio_value_proportion[1] > 0:
        run_monthly(all_day_adjust_wrapper, 1, "11:01")
    if g.portfolio_value_proportion[2] > 0:
        run_monthly(simple_roa_adjust_wrapper, 1, "11:02")
        run_daily(simple_roa_check_wrapper, "14:52")
    if g.portfolio_value_proportion[3] > 0:
        run_weekly(weak_cyc_adjust_wrapper, 1, "11:03")
    if g.portfolio_value_proportion[4] > 0:
        run_daily(etf_rotation_adjust_wrapper, "11:04")
    # 每日剩余资金购买货币ETF
    run_daily(end_trade, "14:59")
    g.portfolio_manager = PortfolioManager(context)
    run_monthly(adjust_portfolio_weights, 1, "10:00")  # 每月1日10:00调整权重

# 其余代码（策略类、工厂类、包装函数等）保持不变，与原始文件一致...
# 此处省略以避免重复，完整代码需包含原始策略逻辑、交易函数、日志工具等

def process_initialize(context):
    """处理初始化"""
    print("重启程序")
    StrategyFactory.create_strategies(context)

# 尾盘处理函数
def end_trade(context):
    """尾盘处理，卖出未记录股票并买入货币ETF"""
    current_data = get_current_data()

    # 卖出未记录的股票（比如送股）
    keys = [key for d in g.positions.values() if isinstance(d, dict) for key in d.keys()]
    for stock in context.portfolio.positions:
        if stock not in keys and stock != g.fill_stock and current_data[stock].last_price < current_data[stock].high_limit:
            if order_target_value(stock, 0):
                log.info(f"卖出{stock}因送股未记录在持仓中")

    # 买入货币ETF
    amount = int(context.portfolio.available_cash / current_data[g.fill_stock].last_price)
    if amount >= 100:
        order(g.fill_stock, amount)

# 卖出货币ETF换现金函数
def get_cash(context, value):
    """卖出货币ETF获取现金"""
    if g.fill_stock not in context.portfolio.positions:
        return
    current_data = get_current_data()
    amount = math.ceil(value / current_data[g.fill_stock].last_price / 100) * 100
    position = context.portfolio.positions[g.fill_stock].closeable_amount
    if amount >= 100:
        order(g.fill_stock, -min(amount, position))

# 策略接口类
class StrategyInterface:
    """策略接口类，定义策略的基本方法和属性"""

    def __init__(self, context, index, name):
        self.context = context
        self.index = index
        self.name = name
        self.stock_sum = 1
        self.hold_list = []
        self.min_volume = 2000
        self.pass_months = [1, 4]
        self.def_stocks = ["511260.XSHG", "518880.XSHG", "512800.XSHG"]  # 债券ETF、黄金ETF、银行ETF
        self.last_value = 0  # 记录上次调仓时的市值

    def get_total_value(self):
        """获取策略当前持仓市值"""
        if not g.positions[self.index]:
            return 0
        return sum(self.context.portfolio.positions[key].price * value for key, value in g.positions[self.index].items())

    def _check(self):
        """卖出非连板股票，并返回成功卖出的股票列表"""
        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())
        stocks = []
        # 获取昨日涨停、前日涨停昨日跌停列表
        if self.hold_list != []:
            df = get_price(self.hold_list, end_date=self.context.previous_date,
                frequency="daily", fields=["close", "high_limit"], count=3, panel=False, fill_paused=False)
            df = df[df["close"] == df["high_limit"]]
            for stock in df.code.drop_duplicates():
                if self.order_target_value_(stock, 0):
                    # 检查股票是否在持仓中
                    if stock in g.positions[self.index]:
                        LogUtils.log_trade_info(self.context, self.name, stock, "卖出", 
                            -g.positions[self.index][stock], 
                            self.context.portfolio.positions[stock].price,
                            self.context.portfolio.positions[stock].value)
                    stocks.append(stock)
        return stocks

    def _adjust(self, target):
        """调仓(等权购买target中按顺序排列固定数量的标的)"""
        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())

        # 调仓卖出
        for stock in self.hold_list:
            if stock not in target:
                if self.order_target_value_(stock, 0):
                    # 检查股票是否在持仓中
                    if stock in g.positions[self.index]:
                        LogUtils.log_trade_info(self.context, self.name, stock, "卖出", 
                            -g.positions[self.index][stock], 
                            self.context.portfolio.positions[stock].price,
                            self.context.portfolio.positions[stock].value)

        # 调仓买入
        target = [stock for stock in target if stock not in self.hold_list]
        sum_stock = self.stock_sum - len(self.hold_list)
        self.buy(target[: min(len(target), sum_stock)])

    def _adjust2(self, targets):
        """调仓2(targets为字典，key为股票代码，value为目标市值)"""
        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())
        current_data = get_current_data()
        portfolio = self.context.portfolio

        # 清仓被调出的
        for stock in self.hold_list:
            if stock not in targets:
                if self.order_target_value_(stock, 0):
                    # 检查股票是否在持仓中
                    if stock in g.positions[self.index]:
                        LogUtils.log_trade_info(self.context, self.name, stock, "卖出", 
                            -g.positions[self.index][stock], 
                            self.context.portfolio.positions[stock].price,
                            self.context.portfolio.positions[stock].value)

        # 先卖出
        for stock, target in targets.items():
            price = current_data[stock].last_price
            # 使用get方法安全获取持仓数量
            current_position = g.positions[self.index].get(stock, 0)
            value = current_position * price
            if value - target > self.min_volume and value - target > price * 100:
                if self.order_target_value_(stock, target):
                    # 检查股票是否在持仓中
                    if stock in g.positions[self.index]:
                        LogUtils.log_trade_info(self.context, self.name, stock, "卖出", 
                            -(g.positions[self.index][stock] - target/price), 
                            price, value - target)

        # 后买入
        for stock, target in targets.items():
            price = current_data[stock].last_price
            # 使用get方法安全获取持仓数量
            current_position = g.positions[self.index].get(stock, 0)
            value = current_position * price
            if target - value > self.min_volume and target - value > price * 100:
                if target - value > portfolio.available_cash:
                    get_cash(self.context, target - value - portfolio.available_cash)
                if portfolio.available_cash > price * 100 and portfolio.available_cash > self.min_volume:
                    if self.order_target_value_(stock, target):
                        LogUtils.log_trade_info(self.context, self.name, stock, "买入", 
                            target/price - current_position, 
                            price, target - value)

    def buy(self, target):
        """可用现金等比例买入"""
        count = len(target)
        portfolio = self.context.portfolio

        # target为空或者持仓数量已满，不进行操作
        if count == 0 or self.stock_sum <= len(self.hold_list):
            return

        # 目标市值
        target_value = portfolio.total_value * g.portfolio_value_proportion[self.index]

        # 当前市值
        position_value = self.get_total_value()

        # 可用现金：当前现金 + 货币ETF市值
        available_cash = portfolio.available_cash + (portfolio.positions[g.fill_stock].value if g.fill_stock in portfolio.positions else 0)

        # 买入股票的总市值
        value = max(0, min(target_value - position_value, available_cash))

        # 卖出部分货币ETF获取现金
        if value > portfolio.available_cash:
            get_cash(self.context, value - portfolio.available_cash)

        # 等价值买入每一个未买入的标的
        for security in target:
            if self.order_target_value_(security, value / count):
                LogUtils.log_trade_info(self.context, self.name, security, "买入", 
                    g.positions[self.index][security], 
                    self.context.portfolio.positions[security].price,
                    self.context.portfolio.positions[security].value)

    def order_target_value_(self, security, value):
        """自定义下单(涨跌停不交易)"""
        current_data = get_current_data()

        # 检查标的是否停牌、涨停、跌停
        if current_data[security].paused:
            LogUtils.log_strategy_info(self.context, self.name, "交易失败", f"{security}: 今日停牌")
            return False

        # 检查是否涨停
        if current_data[security].last_price == current_data[security].high_limit:
            LogUtils.log_strategy_info(self.context, self.name, "交易失败", f"{security}: 当前涨停")
            return False

        # 检查是否跌停
        if current_data[security].last_price == current_data[security].low_limit:
            LogUtils.log_strategy_info(self.context, self.name, "交易失败", f"{security}: 当前跌停")
            return False

        # 获取当前标的的价格
        price = current_data[security].last_price

        # 获取当前策略的持仓数量
        current_position = g.positions[self.index].get(security, 0)

        # 计算目标持仓数量
        target_position = (int(value / price) // 100) * 100 if price != 0 else 0

        # 计算需要调整的数量
        adjustment = target_position - current_position

        # 检查是否当天买入卖出
        closeable_amount = self.context.portfolio.positions[security].closeable_amount if security in self.context.portfolio.positions else 0
        if adjustment < 0 and closeable_amount == 0:
            LogUtils.log_strategy_info(self.context, self.name, "交易失败", f"{security}: 当天买入不可卖出")
            return False

        # 下单并更新持仓
        if adjustment != 0:
            o = order(security, adjustment)
            if o:
                # 更新持仓数量
                amount = o.amount if o.is_buy else -o.amount
                g.positions[self.index][security] = amount + current_position
                # 如果目标持仓为零，移除该证券
                if target_position == 0:
                    g.positions[self.index].pop(security, None)
                # 更新持有列表
                self.hold_list = list(g.positions[self.index].keys())
                return True
        return False

    def filter_basic_stock(self, stock_list):
        """基础过滤(过滤科创北交、ST、停牌、次新股)"""
        current_data = get_current_data()
        return [stock for stock in stock_list if not current_data[stock].paused and not current_data[stock].is_st and "ST" not in current_data[stock].name and "*" not in current_data[stock].name and "退" not in current_data[stock].name and not (stock[0] == "4" or stock[0] == "8" or stock[:2] == "68") and not (self.context.previous_date - get_security_info(stock).start_date < datetime.timedelta(375))]

    def filter_limitup_limitdown_stock(self, stock_list):
        """过滤当前时间涨跌停的股票"""
        current_data = get_current_data()
        return [stock for stock in stock_list if current_data[stock].last_price < current_data[stock].high_limit and current_data[stock].last_price > current_data[stock].low_limit]

    def filter_limitup_stock(self, stock_list, days):
        """过滤近几日涨停过的股票"""
        df = get_price(stock_list, end_date=self.context.previous_date, frequency="daily", fields=["close", "high_limit"], count=days, panel=False)
        df = df[df["close"] == df["high_limit"]]
        filterd_stocks = df.code.drop_duplicates().tolist()
        return [stock for stock in stock_list if stock not in filterd_stocks]

    def is_empty_month(self):
        """判断今天是否在空仓月"""
        month = self.context.current_dt.month
        return month in self.pass_months

# 策略工厂类
class StrategyFactory:
    """策略工厂类，负责创建和管理各种策略实例"""

    @staticmethod
    def create_strategies(context):
        """创建策略实例"""
        g.strategys = {
            "搅屎棍策略": JSG_Strategy(context, index=0, name="搅屎棍策略"),
            "全天候策略": All_Day_Strategy(context, index=1, name="全天候策略"),
            "简单ROA策略": Simple_ROA_Strategy(context, index=2, name="简单ROA策略"),
            "弱周期价投策略": Weak_Cyc_Strategy(context, index=3, name="弱周期价投策略"),
            "核心资产轮动策略": Etf_Rotation_Strategy(context, index=4, name="核心资产轮动策略")
        }

# 搅屎棍策略类
class JSG_Strategy(StrategyInterface):
    """搅屎棍策略类"""

    def __init__(self, context, index, name):
        super().__init__(context, index, name)
        self.stock_sum = 3
        self.num = 1
        self.pass_months = [1, 4]

    def getStockIndustry(self, stocks):
        """获取股票行业"""
        industry = get_industry(stocks)
        return pd.Series({stock: info["sw_l1"]["industry_name"] for stock, info in industry.items() if "sw_l1" in info})

    def get_market_breadth(self):
        """获取市场宽度"""
        yesterday = self.context.previous_date
        stocks = get_index_stocks("000985.XSHG")
        count = 1
        h = get_price(stocks, end_date=yesterday, frequency="1d", fields=["close"], count=count + 20, panel=False)
        h["date"] = pd.DatetimeIndex(h.time).date
        df_close = h.pivot(index="code", columns="date", values="close").dropna(axis=0)
        df_ma20 = df_close.rolling(window=20, axis=1).mean().iloc[:, -count:]
        df_bias = df_close.iloc[:, -count:] > df_ma20
        df_bias["industry_name"] = self.getStockIndustry(stocks)
        df_ratio = ((df_bias.groupby("industry_name").sum() * 100.0) / df_bias.groupby("industry_name").count()).round()
        top_values = df_ratio.loc[:, yesterday].nlargest(self.num)
        I = top_values.index.tolist()
        return I

    def filter(self):
        """过滤股票"""
        stocks = get_index_stocks("399101.XSHE")
        stocks = self.filter_basic_stock(stocks)
        stocks = self.filter_limitup_stock(stocks, 5)
        stocks = get_fundamentals(query(valuation.code).filter(valuation.code.in_(stocks), indicator.adjusted_profit > 0).order_by(valuation.market_cap.asc())).head(20).code
        stocks = self.filter_limitup_limitdown_stock(stocks)
        return stocks

    def select(self):
        """择时"""
        I = self.get_market_breadth()
        industries = {"银行I", "煤炭I", "采掘I", "钢铁I"}
        if not industries.intersection(I) and not self.is_empty_month():
            return True
        return False

    def adjust(self):
        """调仓"""
        if self.select():
            stocks = self.filter()[: self.stock_sum]
            self._adjust(stocks)
        else:
            total_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
            self._adjust2({stock: total_value / len(self.def_stocks) for stock in self.def_stocks})

    def check(self):
        """检查昨日涨停票"""
        banner_stocks = self._check()
        if banner_stocks:
            target = [stock for stock in self.filter() if stock not in banner_stocks and stock not in self.hold_list][: len(banner_stocks)]
            self.buy(target)

# 全天候ETF策略类
class All_Day_Strategy(StrategyInterface):
    """全天候ETF策略类"""

    def __init__(self, context, index, name):
        super().__init__(context, index, name)
        self.min_volume = 2000
        self.etf_pool = ["518880.XSHG", "513100.XSHG"]
        self.rates = [0.66, 0.34]

    def adjust(self):
        """调仓"""
        total_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
        targets = {etf: total_value * rate for etf, rate in zip(self.etf_pool, self.rates)}
        self._adjust2(targets)

# 简单ROA策略类
class Simple_ROA_Strategy(StrategyInterface):
    """简单ROA策略类"""

    def __init__(self, context, index, name):
        super().__init__(context, index, name)
        self.stock_sum = 1

    def filter(self):
        """过滤股票"""
        stocks = get_all_securities("stock", date=self.context.previous_date).index.tolist()
        stocks = self.filter_basic_stock(stocks)
        stocks = get_fundamentals(query(valuation.code, indicator.roa).filter(valuation.code.in_(stocks), valuation.pb_ratio > 0, valuation.pb_ratio < 1, indicator.adjusted_profit > 0)).sort_values(by="roa", ascending=False).head(10).code
        stocks = self.filter_limitup_limitdown_stock(stocks)
        return stocks

    def adjust(self):
        """调仓"""
        self._adjust(self.filter()[: self.stock_sum])

    def check(self):
        """检查昨日涨停票"""
        banner_stocks = self._check()
        if banner_stocks:
            target = [stock for stock in self.filter() if stock not in banner_stocks and stock not in self.hold_list][: len(banner_stocks)]
            self.buy(target)

# 弱周期价投策略类
class Weak_Cyc_Strategy(StrategyInterface):
    """弱周期价投策略类"""

    def __init__(self, context, index, name):
        super().__init__(context, index, name)
        self.bond_etf = "511260.XSHG"
        self.targets = {}
        self.min_volume = 10000
        self.industry_ratio = [0.2, 0.2]
        self.stock_ratio = [1]
        self.total_value = 0

    def filter_dividend(self, stocks, year, div_yield, payout_rate):
        """分红过滤"""
        if not stocks:
            return []
        time1 = self.context.previous_date
        time0 = time1 - timedelta(days=(year + 0.1) * 365)
        f = finance.STK_XR_XD
        q = query(f.code, f.bonus_amount_rmb).filter(f.code.in_(stocks), f.board_plan_pub_date >= time0, f.board_plan_pub_date <= time1)
        df = finance.run_query(q).fillna(0).set_index("code").groupby("code").sum()
        q = query(valuation.code, valuation.market_cap, valuation.pe_ratio).filter(valuation.code.in_(list(df.index)))
        cap = get_fundamentals(q, date=time1).set_index("code")
        df = pd.concat([df, cap], axis=1, sort=False)
        df["div_yield"] = df["bonus_amount_rmb"] / (df["market_cap"] * 10000) / year
        df["payout_rate"] = df["bonus_amount_rmb"] / ((df["market_cap"] * 10000) / df["pe_ratio"]) / year
        df = df.query("div_yield > @div_yield and payout_rate > @payout_rate")
        return list(df.index)

    def filter_profit(self, stocks, year, net_profit_margin, gross_profit_margin):
        """利润过滤"""
        if not stocks:
            return []
        df = get_history_fundamentals(stocks, fields=[income.operating_revenue, indicator.net_profit_margin, indicator.gross_profit_margin], watch_date=self.context.previous_date, count=4 * year, interval="1q", stat_by_year=False)
        def agg_func(group):
            revenue = group["operating_revenue"].sum()
            return pd.Series({
                "operating_revenue": revenue,
                "weighted_net_profit_margin": (group["operating_revenue"] * group["net_profit_margin"]).sum() / revenue,
                "weighted_gross_profit_margin": (group["operating_revenue"] * group["gross_profit_margin"]).sum() / revenue
            })
        df = df.groupby("code").apply(agg_func).reset_index()
        df = df.query("weighted_net_profit_margin > @net_profit_margin and weighted_gross_profit_margin > @gross_profit_margin")
        return list(df.code)

    def get_profit_vol(self, stocks, year):
        """获取净利润波动率"""
        df = get_history_fundamentals(stocks, fields=[income.net_profit], watch_date=self.context.previous_date, count=4 * year, interval="1q", stat_by_year=False)
        df["rolling_profit"] = df.groupby("code")["net_profit"].rolling(4).sum().reset_index(level=0, drop=True)
        df["growth_rate"] = df.groupby("code")["rolling_profit"].pct_change()
        return df.groupby("code")["growth_rate"].std().reset_index(name="volatility")

    def select1(self):
        """选择公用事业I行业股票"""
        stocks = get_industry_stocks("801160")
        stocks = self.filter_basic_stock(stocks)
        df = get_fundamentals(query(valuation.code, valuation.pe_ratio).filter(valuation.code.in_(stocks), cash_flow.net_operate_cash_flow > 0, cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 1.0, balance.total_liability / balance.total_assets < 0.8, valuation.market_cap > 200))
        stocks = self.filter_dividend(list(df.code), 3, 0.02, 0.4)
        stocks = self.filter_profit(stocks, 1, 20, 30)
        if not stocks:
            return
        vol = self.get_profit_vol(stocks, 3)
        df = vol.merge(df[["code", "pe_ratio"]], on="code", how="left")
        df["score"] = 1 / df["pe_ratio"] * (1 - 2 * df["volatility"])
        df = df.sort_values(by="score", ascending=False).reset_index(drop=True)
        for i, ratio in enumerate(self.stock_ratio[: len(df)]):
            self.targets[df.code[i]] = self.total_value * ratio * self.industry_ratio[0]

    def select2(self):
        """选择交通运输I行业股票"""
        stocks = get_industry_stocks("801170")
        stocks = self.filter_basic_stock(stocks)
        df = get_fundamentals(query(valuation.code, valuation.pe_ratio, indicator.roa).filter(valuation.code.in_(stocks), cash_flow.net_operate_cash_flow > 0, cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 1.0, balance.total_liability / balance.total_assets < 0.6, valuation.market_cap > 200))
        stocks = self.filter_dividend(list(df.code), 3, 0.02, 0.3)
        stocks = self.filter_profit(stocks, 1, 20, 30)
        if not stocks:
            return
        vol = self.get_profit_vol(stocks, 3)
        df = vol.merge(df[["code", "pe_ratio"]], on="code", how="left")
        df["score"] = 1 / df["pe_ratio"] * (1 - 2 * df["volatility"])
        df = df.sort_values(by="score", ascending=False).reset_index(drop=True)
        for i, ratio in enumerate(self.stock_ratio[: len(df)]):
            self.targets[df.code[i]] = self.total_value * ratio * self.industry_ratio[1]

    def adjust(self):
        """调仓"""
        self.targets = {}
        self.total_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
        self.select1()
        self.select2()
        self.targets[self.bond_etf] = self.total_value - sum(list(self.targets.values()))
        self._adjust2(self.targets)

# 核心资产轮动策略类
class Etf_Rotation_Strategy(StrategyInterface):
    """核心资产轮动策略类"""

    def __init__(self, context, index, name):
        super().__init__(context, index, name)
        self.stock_sum = 1
        self.etf_pool = ["513100.XSHG", "513520.XSHG", "513030.XSHG", "518880.XSHG", "159980.XSHE", "159985.XSHE", "501018.XSHG", "511090.XSHG", "513130.XSHG"]
        self.m_days = 25

    def get_etf_rank(self):
        """获取ETF排名"""
        data = pd.DataFrame(index=self.etf_pool, columns=["annualized_returns", "r2", "score"])
        current_data = get_current_data()
        for etf in self.etf_pool:
            df = attribute_history(etf, self.m_days, "1d", ["close", "high"])
            prices = np.append(df["close"].values, current_data[etf].last_price)
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0
            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]
            if min(prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4]) < 0.95:
                data.loc[etf, "score"] = 0
        data = data.query("0 < score < 6").sort_values(by="score", ascending=False)
        return data.index.tolist()

    def adjust(self):
        """调仓"""
        target = self.get_etf_rank()
        self._adjust(target[: min(self.stock_sum, len(target))])

# 策略包装函数
def jsg_adjust_wrapper(context):
    """搅屎棍策略调仓包装函数"""
    LogUtils.log_strategy_info(context, "搅屎棍策略", "开始调仓", "")
    g.strategys["搅屎棍策略"].adjust()
    LogUtils.log_strategy_info(context, "搅屎棍策略", "调仓完成", "")
    LogUtils.log_portfolio_info(context)
    # 更新策略权重
    g.portfolio_value_proportion = g.portfolio_manager.strategy_weights

def jsg_check_wrapper(context):
    """搅屎棍策略检查包装函数"""
    LogUtils.log_strategy_info(context, "搅屎棍策略", "开始检查", "")
    g.strategys["搅屎棍策略"].check()
    LogUtils.log_strategy_info(context, "搅屎棍策略", "检查完成", "")
    LogUtils.log_portfolio_info(context)

def all_day_adjust_wrapper(context):
    """全天候策略调仓包装函数"""
    LogUtils.log_strategy_info(context, "全天候策略", "开始调仓", "")
    g.strategys["全天候策略"].adjust()
    LogUtils.log_strategy_info(context, "全天候策略", "调仓完成", "")
    LogUtils.log_portfolio_info(context)

def simple_roa_adjust_wrapper(context):
    """简单ROA策略调仓包装函数"""
    LogUtils.log_strategy_info(context, "简单ROA策略", "开始调仓", "")
    g.strategys["简单ROA策略"].adjust()
    LogUtils.log_strategy_info(context, "简单ROA策略", "调仓完成", "")
    LogUtils.log_portfolio_info(context)

def simple_roa_check_wrapper(context):
    """简单ROA策略检查包装函数"""
    LogUtils.log_strategy_info(context, "简单ROA策略", "开始检查", "")
    g.strategys["简单ROA策略"].check()
    LogUtils.log_strategy_info(context, "简单ROA策略", "检查完成", "")
    LogUtils.log_portfolio_info(context)

def weak_cyc_adjust_wrapper(context):
    """弱周期价投策略调仓包装函数"""
    LogUtils.log_strategy_info(context, "弱周期价投策略", "开始调仓", "")
    g.strategys["弱周期价投策略"].adjust()
    LogUtils.log_strategy_info(context, "弱周期价投策略", "调仓完成", "")
    LogUtils.log_portfolio_info(context)

def etf_rotation_adjust_wrapper(context):
    """核心资产轮动策略调仓包装函数"""
    LogUtils.log_strategy_info(context, "核心资产轮动策略", "开始调仓", "")
    g.strategys["核心资产轮动策略"].adjust()
    LogUtils.log_strategy_info(context, "核心资产轮动策略", "调仓完成", "")
    LogUtils.log_portfolio_info(context)

# 注意，以下函数是必须的，且不能修改函数名称和参数数量
def before_trading_start(context):
    """开盘前准备"""
    LogUtils.log_strategy_info(context, "系统", "开始交易", f"日期: {context.current_dt}")
    LogUtils.log_portfolio_info(context)
    for strategy_name in g.strategys.keys():
        LogUtils.log_performance_info(context, strategy_name)

def after_trading_end(context):
    """收盘后处理"""
    LogUtils.log_strategy_info(context, "系统", "结束交易", f"日期: {context.current_dt}")
    LogUtils.log_portfolio_info(context)
    for strategy_name in g.strategys.keys():
        LogUtils.log_performance_info(context, strategy_name)

def get_initial_value(strategy_name, start_date):
    """获取策略在指定日期的初始价值"""
    try:
        strategy = g.strategys[strategy_name]
        positions = g.positions[strategy.index]
        
        if not positions:
            return 0.0
            
        # 获取持仓股票的历史价格
        stocks = list(positions.keys())
        df = get_price(stocks, end_date=start_date, frequency="1d", 
                     fields=["close"], count=1, panel=False)
        
        if df.empty:
            return 0.0
            
        # 计算持仓市值
        total_value = 0.0
        for stock in stocks:
            if stock in df.code.values:
                price = df[df.code == stock]["close"].iloc[0]
                amount = positions[stock]
                total_value += price * amount
                
        LogUtils.log_strategy_info(None, "组合管理", "初始价值计算", 
            f"{strategy_name}在{start_date}的初始价值: {total_value:.2f}")
            
        return total_value
        
    except Exception as e:
        LogUtils.log_strategy_info(None, "组合管理", "初始价值计算失败", 
            f"{strategy_name}在{start_date}的初始价值计算失败: {str(e)}")
        return 0.0