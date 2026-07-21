# Clone from JoinQuant
# postId: 58ec97d9f7513dcee0baff80fc3bee2e
# backtestId: 9d80178dec57a6b0d4a94f53068936a0
# title: 【更新V2】52.5%年化，回撤17%--七星+红利+宽基

# 七星高照ETF轮动 + 红利低波成长 + 四方轮动ETF动量轮动 - 三策略组合
# 框架版本: V7.20260701.0200
# 子策略0: 七星高照ETF轮动 (index=0, 40%)
# 子策略1: 红利低波成长 (index=1, 30%)
# 子策略2: 四方轮动ETF动量轮动 (index=2, 30%)
#
# 此文件为自包含单文件，可直接上传聚宽回测
# 不含: Redis信号、邮件通知
#
# 七星策略逻辑：多因子ETF动量评分（WLS拟合+R²+溢价率+成交量+短期动量），日频轮动+盈利保护
# 红利策略逻辑：基本面过滤(PE/ROE/营收增长/利润增长)+股息率选股，月频调仓
# 四方策略逻辑：黄金/纳指/创业板/红利低波ETF 25日动量评分，日频轮动+择时优化
#
# 回测基准: 000300.XSHG (沪深300)

FRAMEWORK_VERSION = "V7.20260701.0200"

import pandas as pd
import datetime
import numpy as np
import math
from prettytable import PrettyTable
from jqdata import *

# ==================== 组合配置 ====================

PORTFOLIO_PROPORTION = [0.4, 0.3, 0.3]  # [七星高照, 红利低波成长, 四方轮动] 资金分配比例
DRAWDOWN_WARNING_THRESHOLD = 0.6  # 虚拟权益低于初始资本的60%时发出风控警告
CASH_BUFFER_RATIO = 0.995  # 买入时预留手续费的比例

# ==================== 资金再平衡配置 ====================
ENABLE_CAPITAL_REBALANCE = True            # 总开关（已启用，经回测验证稳定性更优）
CAPITAL_REBALANCE_MIN_INTERVAL = 50       # 最小再平衡间隔（交易日数）：过了之后每天检查偏差
CAPITAL_REBALANCE_DEVIATION = 0.25        # 相对偏移率阈值（最大相对偏移>25%才执行）

# ==================== 交易成本配置 ====================
# 滑点（stock/fund均使用比例滑点 PriceRelatedSlippage）
STOCK_SLIPPAGE = 0.002                      # 股票比例滑点0.2%（10元股滑0.02元, 50元股滑0.1元）
FUND_SLIPPAGE = 0.001                       # ETF比例滑点0.1%

# 佣金（stock/fund统一万1，实盘费率）
OPEN_COMMISSION = 0.0001                    # 买入佣金万1
CLOSE_COMMISSION = 0.0001                   # 卖出佣金万1
MIN_COMMISSION = 5                          # 最低佣金5元（不免5）

# 印花税
STOCK_CLOSE_TAX = 0.0005                    # 股票卖出印花税万5（2023.8.28后标准，基金无印花税）

# ==================== 七星策略配置 ====================

QIXING_REBALANCE_TIME = "14:09"
QIXING_PROFIT_CHECK_TIMES = ['09:45', '10:25', '11:00', '13:10']  # 盈利保护检查时间点
QIXING_MINUTE_PROFIT_COOLDOWN = 15  # 盈利保护触发后冷却时间（分钟）
QIXING_DEFENSIVE_ETF = "511880.XSHG"
QIXING_HOLDINGS_NUM = 1
QIXING_LOOKBACK_DAYS = 25
QIXING_MIN_MONEY = 1000
QIXING_ENABLE_PROFIT_PROTECTION = True
QIXING_PROFIT_PROTECTION_THRESHOLD = 0.05
QIXING_LOSS = 0.97
QIXING_ENABLE_PREMIUM_FILTER = True
QIXING_PREMIUM_THRESHOLD = 0.20
QIXING_ENABLE_VOLUME_CHECK = True
QIXING_VOLUME_THRESHOLD = 2
QIXING_USE_SHORT_MOMENTUM_FILTER = True
QIXING_SHORT_LOOKBACK_DAYS = 10
QIXING_MIN_SCORE_THRESHOLD = 0.0
QIXING_MAX_SCORE_THRESHOLD = float('inf')
QIXING_ETF_POOL = [
    # 大宗商品ETF
    "518880.XSHG",  # 黄金ETF
    "159980.XSHE",  # 有色ETF
    "159985.XSHE",  # 豆粕ETF
    "501018.XSHG",  # 南方原油
    "161226.XSHE",  # 白银LOF
    "159981.XSHE",  # 能源化工ETF
    # 国际ETF
    "513100.XSHG",  # 纳指ETF
    "513300.XSHG",  # 纳斯达克ETF
    "159509.XSHE",  # 纳指科技ETF
    "513290.XSHG",  # 纳指生物ETF
    "513500.XSHG",  # 标普500ETF
    "159529.XSHE",  # 标普消费
    "513400.XSHG",  # 道琼斯ETF
    "159577.XSHE",  # 美国50ETF
    "513520.XSHG",  # 日经225ETF
    "513030.XSHG",  # 德国30ETF
    "513080.XSHG",  # 法国ETF
    "513310.XSHG",  # 中韩半导体ETF
    "513730.XSHG",  # 东南亚科技ETF
    "159687.XSHE",  # 亚太精选ETF
    # 香港ETF
    "159792.XSHE",  # 港股互联ETF
    "513130.XSHG",  # 恒生科技
    "513050.XSHG",  # 中概互联网ETF
    "159920.XSHE",  # 恒生ETF
    "513690.XSHG",  # 港股红利
    "520550.XSHG",  # 港股红利低波
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
    "515100.XSHG",  # 红利低波100ETF
    "159967.XSHE",  # 创业板成长ETF
    "512040.XSHG",  # 价值ETF
    "159201.XSHE",  # 自由现金流ETF
    # 债券ETF
    "511380.XSHG",  # 可转债ETF
    "511010.XSHG",  # 国债ETF
    "511220.XSHG",  # 城投债ETF
]

# ==================== 红利低波成长策略配置 ====================

DIVIDEND_STOCK_NUM = 5                     # 目标持仓股票数量
DIVIDEND_MIN_MONEY = 1000                  # 最小下单金额
DIVIDEND_PE_RANGE = (5, 50)                # PE过滤范围
DIVIDEND_ROE_RANGE = (5, 100)              # ROE过滤范围
DIVIDEND_REVENUE_GROWTH_RANGE = (5, 100)   # 营收同比增长率过滤范围
DIVIDEND_PROFIT_GROWTH_RANGE = (10, 100)   # 利润同比增长率过滤范围
DIVIDEND_RATIO_TOP_PCT = 0.10              # 股息率取前N%
DIVIDEND_RATIO_MIN = 0.03                  # 股息率最低阈值

# ==================== 四方轮动策略配置 ====================

SIFANG_ETF_POOL = [
    "518880.XSHG",  # 黄金ETF
    "513100.XSHG",  # 纳指ETF
    "159915.XSHE",  # 创业板ETF
    "515100.XSHG",  # 红利低波100ETF
]
SIFANG_LOOKBACK_DAYS = 25                  # 动量回望天数
SIFANG_MIN_SCORE = 0.05                    # 最低动量评分
SIFANG_POSITION_STOP_LOSS = 0.08           # 个股止损比例
SIFANG_MAX_DRAWDOWN_THRESHOLD = 0.10       # 最大回撤阈值（触发清仓）
SIFANG_STOP_LOSS_COOLDOWN_DAYS = 3         # 止损后冷却天数
SIFANG_DRAWDOWN_EARLY_WARNING_RATIO = 0.6  # 回撤达阈值的60%时进入警戒区间（不做动作，仅跳过早期无意义计算）



# ==================== 持仓归属系统 ====================

def register_security_ownership(security, strategy_idx):
    if not hasattr(g, 'security_ownership'):
        g.security_ownership = {}
    if security not in g.security_ownership:
        g.security_ownership[security] = {strategy_idx}
    else:
        g.security_ownership[security].add(strategy_idx)


def get_security_owners(security):
    return getattr(g, 'security_ownership', {}).get(security, set())


def unregister_security_ownership(security, strategy_idx):
    if hasattr(g, 'security_ownership') and security in g.security_ownership:
        g.security_ownership[security].discard(strategy_idx)
        if not g.security_ownership[security]:
            del g.security_ownership[security]


# ==================== Strategy基类 ====================

class Strategy:
    """多策略组合框架基类 — 提供统一交易接口和虚拟子账户管理。"""

    version = ""

    def __init__(self, context, index, name, display_name):
        self.context = context
        self.index = index
        self.name = name
        self.display_name = display_name
        self.stock_sum = 1
        self.buffer_sum = 1
        self.hold_list = []
        self.min_money = 1000
        self.current_targets = {}
        self.enable_rebalance = True
        self.rebalance_threshold_pct = 0  # 调仓百分比容差（0=不启用，0.05=5%容差）

    # ==================== 账户查询 ====================

    def get_total_value(self):
        if not g.positions[self.index]:
            return 0
        total = 0
        for key, value in g.positions[self.index].items():
            pos = self.context.portfolio.positions.get(key)
            if pos and pos.total_amount > 0:
                total += pos.price * value
        return total

    def get_strategy_available_cash(self):
        virtual_cash = g.strategy_virtual_cash.get(self.index, 0)
        real_avail = self.context.portfolio.available_cash
        return max(0, min(virtual_cash, real_avail))

    def get_portfolio_value(self):
        return g.strategy_virtual_equity.get(self.index, 0)

    def get_virtual_cash(self):
        return g.strategy_virtual_cash.get(self.index, 0)

    def get_virtual_equity(self):
        return g.strategy_virtual_equity.get(self.index, 0)

    def get_avg_cost(self, security, fallback=0.0):
        """获取策略对某标的的平均成本"""
        pos = self.context.portfolio.positions.get(security)
        default = pos.avg_cost if pos and pos.total_amount > 0 else fallback
        return g.strategy_avg_cost[self.index].get(security, default)

    # ==================== 停牌/涨跌停检测 ====================

    def _is_suspended(self, security):
        today = self.context.current_dt.date()
        cache = getattr(g, '_suspended_cache', None)
        if cache is None or cache[0] != today:
            g._suspended_cache = (today, {})
            cache = g._suspended_cache
        if security in cache[1]:
            return cache[1][security]
        cd = get_current_data()[security]
        result = False
        if cd.paused:
            result = True
        elif not cd.last_price or cd.last_price <= 0:
            result = True
        else:
            try:
                bars = attribute_history(security, 5, '1m', ['volume'], skip_paused=False)
                if len(bars['volume']) > 0 and max(bars['volume']) <= 0:
                    result = True
            except Exception:
                pass
        cache[1][security] = result
        return result

    def filter_basic_stock(self, stocks, current_data=None):
        if current_data is None:
            current_data = get_current_data()
        return [stock for stock in stocks
                if not current_data[stock].paused
                and not current_data[stock].is_st
                and current_data[stock].last_price > 0
                and current_data[stock].last_price < current_data[stock].high_limit
                and current_data[stock].last_price > current_data[stock].low_limit]

    def filter_limitup_stock(self, stocks, current_data=None):
        if current_data is None:
            current_data = get_current_data()
        return [stock for stock in stocks
                if not current_data[stock].paused
                and current_data[stock].last_price < current_data[stock].high_limit]

    def get_untradeable_stock(self, stocks, current_data=None):
        if current_data is None:
            current_data = get_current_data()
        return [stock for stock in stocks
                if current_data[stock].paused
                or current_data[stock].last_price in (
                    current_data[stock].high_limit,
                    current_data[stock].low_limit)]

    def _is_tradeable(self, security, current_data=None):
        """判断标的是否可交易（不停牌、不涨跌停）"""
        if self._is_suspended(security):
            return False
        if current_data is None:
            current_data = get_current_data()
        price = current_data[security].last_price
        if price <= 0:
            return False
        if price == current_data[security].high_limit or price == current_data[security].low_limit:
            return False
        return True

    def get_security_name(self, security):
        """获取证券简称"""
        try:
            return get_security_info(security).display_name
        except Exception:
            try:
                return get_current_data()[security].name
            except Exception:
                return security

    def format_security(self, security):
        """格式化单只证券的日志展示"""
        return "{}({})".format(security, self.get_security_name(security))

    def get_holdings(self):
        """返回策略持仓字典的副本"""
        return dict(g.positions[self.index])

    def has_position(self, security):
        """判断策略是否持有某标的"""
        return security in g.positions[self.index] and g.positions[self.index][security] > 0

    def format_security_list(self, securities):
        """格式化证券列表的日志展示"""
        if not securities:
            return "无"
        return " / ".join([self.format_security(s) for s in securities])

    # ==================== 框架统一交易方法 ====================

    def _execute_trade(self, security, adjustment, prev_avg_cost=None, trigger="rebalance"):
        idx = self.index
        o = order(security, adjustment)
        if o is None or o.filled <= 0:
            return o

        commission_fee = getattr(o, 'commission', 0.0)
        if o.is_buy:
            g.strategy_realized_pnl[idx] -= commission_fee
            cost = o.price * o.filled + commission_fee
            g.strategy_virtual_cash[idx] -= cost
            old_amount = g.positions[idx].get(security, 0)
            old_cost = g.strategy_avg_cost[idx].get(security, 0.0)
            new_avg = (old_amount * old_cost + o.filled * o.price) / (old_amount + o.filled) if (old_amount + o.filled) > 0 else o.price
            g.strategy_avg_cost[idx][security] = new_avg
            g.positions[idx][security] = old_amount + o.filled
            register_security_ownership(security, idx)
            log.info("【资金追踪】策略[%d]买入%s %d股，花费=%.2f，虚拟现金=%.2f" % (idx, security, o.filled, cost, g.strategy_virtual_cash[idx]))
        else:
            realized = (o.price - prev_avg_cost) * o.filled - commission_fee
            g.strategy_realized_pnl[idx] += realized
            proceeds = o.price * o.filled - commission_fee
            g.strategy_virtual_cash[idx] += proceeds
            new_virtual = g.positions[idx].get(security, 0) - o.filled
            if new_virtual <= 0:
                g.positions[idx].pop(security, None)
                g.strategy_avg_cost[idx].pop(security, None)
                unregister_security_ownership(security, idx)
            else:
                g.positions[idx][security] = new_virtual
            log.info("【盈亏追踪】策略[%d]卖出%s %d股，已实现盈亏=%+.2f，回收现金=%.2f，虚拟现金=%.2f" % (idx, security, o.filled, realized, proceeds, g.strategy_virtual_cash[idx]))
        return o

    def sell_(self, security, sell_amount=None, trigger="rebalance", check_limit=False, current_data=None):
        idx = self.index
        if check_limit:
            if self._is_suspended(security):
                return None
            if current_data is None:
                current_data = get_current_data()
            price = current_data[security].last_price
            if price == current_data[security].high_limit or price == current_data[security].low_limit:
                return None

        my_amount = g.positions[idx].get(security, 0)
        if my_amount <= 0:
            return None
        pos = self.context.portfolio.positions.get(security)
        if pos is None or pos.total_amount <= 0:
            return None
        amount = sell_amount if sell_amount is not None else my_amount
        amount = min(amount, my_amount, pos.closeable_amount)
        if amount <= 0:
            return None
        prev_avg_cost = g.strategy_avg_cost[idx].get(security, pos.avg_cost if pos else 0.0)
        return self._execute_trade(security, -amount, prev_avg_cost=prev_avg_cost, trigger=trigger)

    def buy_(self, security, target_value, trigger="rebalance", check_limit=False, target_shares_override=None, current_data=None):
        idx = self.index
        if current_data is None:
            current_data = get_current_data()
        price = current_data[security].last_price

        if check_limit:
            if self._is_suspended(security):
                return None
            if price == current_data[security].high_limit or price == current_data[security].low_limit:
                return None

        if price <= 0:
            return None
        if target_shares_override is not None:
            target_shares = target_shares_override
        else:
            target_shares = int(target_value / price / 100) * 100
        if target_shares <= 0:
            return None
        virtual_cash = g.strategy_virtual_cash.get(idx, 0)
        affordable_shares = int(virtual_cash * CASH_BUFFER_RATIO / price / 100) * 100
        buy_shares = min(target_shares, affordable_shares)
        if buy_shares <= 0:
            log.info("【资金追踪】策略[%d]买入%s可用资金不足，目标%d股，可买%d股" % (idx, security, target_shares, affordable_shares))
            return None
        return self._execute_trade(security, buy_shares, trigger=trigger)

    def update_equity(self):
        update_strategy_virtual_equity(self.context, self.index)

    def reconcile(self):
        reconcile_strategy_positions(self.context, self.index)

    def pre_rebalance(self, context):
        """调仓前风控钩子，子类可重写。在 run_rebalance 的 reconcile 之后、rebalance 之前调用。"""
        pass

    def intraday_check(self, context):
        """盘中风控钩子，子类可重写。由调度层在盘中定时调用。"""
        pass

    def run_rebalance(self, context):
        """统一调仓入口：更新权益→对账→风控→执行策略调仓"""
        self.context = context
        # 再平衡持仓调整：首次下单时统一执行
        if g._pending_rebalance:
            execute_rebalance_holdings(context)
        self.update_equity()
        self.reconcile()
        self.pre_rebalance(context)
        self.rebalance(context)

    def _sell(self, targets, current_data=None):
        if current_data is None:
            current_data = get_current_data()
        self.hold_list = list(g.positions[self.index].keys())
        fixed = self.get_untradeable_stock(self.hold_list)
        target_value = self.get_virtual_equity()

        for stock in list(self.hold_list):
            if stock not in targets:
                self.order_target_value_(stock, 0, trigger="rotation_sell", current_data=current_data)

        if self.enable_rebalance:
            for stock, weight in targets.items():
                if stock in fixed:
                    continue
                target = target_value * weight
                price = current_data[stock].last_price
                real_pos = self.context.portfolio.positions.get(stock)
                real_amount = real_pos.total_amount if real_pos else 0
                value = real_amount * price
                if value - target > max(self.min_money, price * 100):
                    self.order_target_value_(stock, target, trigger="rotation_sell", current_data=current_data)

    def _buy(self, targets, current_data=None):
        if current_data is None:
            current_data = get_current_data()
        self.hold_list = list(g.positions[self.index].keys())
        fixed = self.get_untradeable_stock(self.hold_list)
        target_value = self.get_virtual_equity()

        for stock, weight in targets.items():
            if stock in fixed:
                continue
            target = target_value * weight
            price = current_data[stock].last_price
            real_pos = self.context.portfolio.positions.get(stock)
            current_amount = real_pos.total_amount if real_pos else 0
            value = current_amount * price

            if self.rebalance_threshold_pct > 0:
                # 百分比容差模式：偏离超过阈值或空仓时才调仓
                if abs(value - target) > target * self.rebalance_threshold_pct or value == 0:
                    self.order_target_value_(stock, target, trigger="rotation_buy", current_data=current_data)
            elif self.enable_rebalance:
                if min(target - value, self.get_strategy_available_cash()) > max(self.min_money, price * 100):
                    self.order_target_value_(stock, target, trigger="rotation_buy", current_data=current_data)
            else:
                if current_amount == 0:
                    if target > max(self.min_money, price * 100):
                        self.order_target_value_(stock, target, trigger="rotation_buy", current_data=current_data)

    def _adjust(self, targets):
        current_data = get_current_data()
        self._sell(targets, current_data=current_data)
        self._buy(targets, current_data=current_data)

    def _rebalance_by_hands(self, hands, stock_prices):
        """按手数精确下单：先卖后买，手数由 allocate_equal_capital 精确计算。

        与 _adjust（权重路径）不同，此方法直接按手数下单，避免权重→市值的精度损失，
        适用于股票策略（1手价格高，权重路径会导致资金闲置）。

        参数:
            hands: dict {stock_code: target_hands}
            stock_prices: dict {stock_code: last_price}
        """
        current_data = get_current_data()

        # 1. 卖出：不在目标中的持仓
        for stock in list(g.positions[self.index].keys()):
            if stock not in hands:
                self.order_target_value_(stock, 0, trigger="rotation_sell", current_data=current_data)

        # 2. 卖出：目标手数少于当前持仓
        for stock, target_hands in hands.items():
            current_amount = g.positions[self.index].get(stock, 0)
            target_amount = target_hands * 100
            if current_amount > target_amount:
                sell_amount = current_amount - target_amount
                self.sell_(stock, sell_amount=sell_amount, trigger="rotation_sell")

        # 3. 买入：目标手数多于当前持仓
        for stock, target_hands in hands.items():
            current_amount = g.positions[self.index].get(stock, 0)
            target_amount = target_hands * 100
            if target_amount > current_amount:
                buy_shares = target_amount - current_amount
                self.buy_(stock, buy_shares * stock_prices[stock], trigger="rotation_buy",
                          target_shares_override=buy_shares, current_data=current_data)

    def order_target_value_(self, security, value, trigger="rebalance", current_data=None):
        if self._is_suspended(security):
            return False
        if current_data is None:
            current_data = get_current_data()
        price = current_data[security].last_price
        if price == current_data[security].high_limit:
            return False
        if price == current_data[security].low_limit:
            return False

        real_pos = self.context.portfolio.positions.get(security)
        my_current_amount = g.positions[self.index].get(security, 0)
        real_total = real_pos.total_amount if real_pos else 0
        my_current_amount = min(my_current_amount, real_total)
        target_position = (int(value / price) // 100) * 100 if price != 0 else 0
        if target_position <= 0 and value > 0:
            target_position = 100
        adjustment = target_position - my_current_amount

        closeable_amount = real_pos.closeable_amount if real_pos else 0
        if adjustment < 0 and closeable_amount == 0:
            return False

        if adjustment > 0:
            affordable_shares = int((self.get_strategy_available_cash() * CASH_BUFFER_RATIO) / price / 100) * 100
            adjustment = min(adjustment, affordable_shares)
            if adjustment <= 0:
                return False

        trade_val = abs(adjustment) * price
        if 0 < trade_val < self.min_money:
            return False

        if adjustment < 0:
            adjustment = -min(abs(adjustment), closeable_amount)

        if adjustment != 0:
            prev_avg_cost = g.strategy_avg_cost[self.index].get(security, real_pos.avg_cost if real_pos else 0.0)
            o = self._execute_trade(security, adjustment, prev_avg_cost=prev_avg_cost, trigger=trigger)
            if o is not None and o.filled > 0:
                self.hold_list = list(g.positions[self.index].keys())
                return True
        return False

    def get_record_kwargs(self, context):
        """记录子策略累计收益率到聚宽自定义参数（基类通用实现）"""
        idx = self.index
        initial = context.portfolio.starting_cash * g.portfolio_value_proportion[idx]
        equity = g.strategy_virtual_equity.get(idx, initial)
        return {'%s_return' % self.name: (equity / initial - 1) * 100} if initial > 0 else {}

    # ==================== 通用数值计算工具 ====================

    @staticmethod
    def _wls_fit(x, y, w):
        """加权线性拟合闭式解。返回 (slope, intercept, r_squared)。
        避免 np.polyfit 的 Vandermonde + QR 开销，对 25-45 点数组更高效。"""
        w = np.asarray(w, dtype=float)
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        w_sum = w.sum()
        wx_mean = (w * x).sum() / w_sum
        wy_mean = (w * y).sum() / w_sum

        x_centered = x - wx_mean
        y_centered = y - wy_mean
        wx = w * x_centered
        wy = w * y_centered

        slope = (wx * wy).sum() / (wx * x_centered).sum()
        intercept = wy_mean - slope * wx_mean

        fitted = slope * x + intercept
        ss_res = (w * (y - fitted) ** 2).sum()
        ss_tot = (w * (y - wy_mean) ** 2).sum()
        r_squared = max(0.0, min(1.0, 1.0 - ss_res / ss_tot)) if ss_tot > 0 else 0.0

        return slope, intercept, r_squared

    @staticmethod
    def allocate_equal_capital(stock_prices, total_value, cash_buffer_ratio=0.995):
        """股票等额资金分配：在1手约束下让每只股票持有尽量相等的资金，资金不足时贪心选股。

        算法：
        1. 先保证每只候选股各买1手（资金不够时按价格从低到高贪心选择）
        2. 按可用资金/N 等分预算，计算每只可买手数
        3. 排除等分预算不够1手的股票后重新分配
        4. 超支从持仓市值最高的减1手（使资金更接近等额）
        5. 剩余资金给持仓市值最低的加1手（使资金更接近等额）

        参数:
            stock_prices: dict {stock_code: last_price}
            total_value: 策略可用总市值
            cash_buffer_ratio: 预留手续费比例

        返回:
            dict {stock_code: hands} 或空 dict
        """
        if not stock_prices:
            return {}

        usable = total_value * cash_buffer_ratio

        # 1. 计算所有候选股各买1手的总成本
        total_1lot_cost = sum(p * 100 for p in stock_prices.values())

        if total_1lot_cost <= usable:
            affordable_list = list(stock_prices.keys())
        else:
            # 2. 资金不够所有候选股各买1手：按价格从低到高贪心选择
            sorted_stocks = sorted(stock_prices.items(), key=lambda x: x[1])
            affordable_list = []
            cumulative_cost = 0
            for stock, price in sorted_stocks:
                lot_cost = price * 100
                if cumulative_cost + lot_cost <= usable:
                    affordable_list.append(stock)
                    cumulative_cost += lot_cost
            if not affordable_list:
                return {}
            total_1lot_cost = sum(stock_prices[s] * 100 for s in affordable_list)

        # 3. 等额资金分配：按可用资金/N 计算每只股票可买手数
        ideal_per_stock = usable / len(affordable_list)
        hands = {}
        spent = 0
        for stock in affordable_list:
            price = stock_prices[stock]
            ideal_hands = int(ideal_per_stock / price / 100)
            if ideal_hands >= 1:
                hands[stock] = ideal_hands
                spent += ideal_hands * price * 100

        # 4. 排除不够1手的股票后重新分配
        while len(hands) < len(affordable_list):
            affordable_list = list(hands.keys())
            if not affordable_list:
                return {}
            ideal_per_stock = usable / len(affordable_list)
            hands = {}
            spent = 0
            for stock in affordable_list:
                price = stock_prices[stock]
                ideal_hands = int(ideal_per_stock / price / 100)
                if ideal_hands >= 1:
                    hands[stock] = ideal_hands
                    spent += ideal_hands * price * 100

        # 5. 超支从持仓市值最高的减1手
        while spent > usable:
            sorted_desc = sorted(affordable_list, key=lambda s: hands[s] * stock_prices[s], reverse=True)
            reduced = False
            for stock in sorted_desc:
                if hands[stock] > 1:
                    hands[stock] -= 1
                    spent -= stock_prices[stock] * 100
                    reduced = True
                    break
            if not reduced:
                break

        # 6. 剩余资金给持仓市值最低的加1手
        remaining = usable - spent
        while remaining > 0:
            sorted_asc = sorted(affordable_list, key=lambda s: hands[s] * stock_prices[s])
            added = False
            for stock in sorted_asc:
                lot_cost = stock_prices[stock] * 100
                if lot_cost <= remaining:
                    hands[stock] += 1
                    remaining -= lot_cost
                    added = True
                    break
            if not added:
                break

        return hands

    # ==================== 股票通用过滤 ====================

    def _filter_kcb_stock(self, stock_list):
        """过滤科创板(68)和北交所(4/8)股票"""
        return [stock for stock in stock_list
                if stock[0] != '4' and stock[0] != '8' and stock[:2] != '68']

    def _filter_new_stock(self, stock_list, days=250):
        """过滤上市不足指定天数的次新股"""
        yesterday = self.context.previous_date
        return [stock for stock in stock_list
                if not (yesterday - get_security_info(stock).start_date < datetime.timedelta(days))]


# ==================== 持仓对账与虚拟权益 ====================

def _calc_virtual_equity(context, idx, current_data=None):
    if current_data is None:
        current_data = get_current_data()

    strat_floating_pnl = 0.0
    strat_mkt_val = 0.0
    for security, my_amount in g.positions.get(idx, {}).items():
        my_amount = int(my_amount or 0)
        if my_amount <= 0:
            continue
        pos = context.portfolio.positions.get(security)
        if not pos or pos.total_amount <= 0:
            continue
        actual = min(my_amount, pos.total_amount)
        curr_p = current_data[security].last_price
        cost_p = g.strategy_avg_cost[idx].get(security, pos.avg_cost)
        strat_floating_pnl += actual * (curr_p - cost_p)
        strat_mkt_val += actual * curr_p

    initial_capital = context.portfolio.starting_cash * g.portfolio_value_proportion[idx]
    current_equity = initial_capital + g.strategy_realized_pnl[idx] + strat_floating_pnl
    # 再平衡调整量：资金再平衡时通过此字段调整各策略可用权益
    current_equity += g.strategy_rebalance_adjustment.get(idx, 0.0)
    virtual_cash = current_equity - strat_mkt_val

    return current_equity, virtual_cash


def reconcile_strategy_positions(context, idx, current_data=None):
    if idx not in g.positions:
        g.positions[idx] = {}

    if current_data is None:
        current_data = get_current_data()

    for sec in list(g.positions[idx].keys()):
        pos = context.portfolio.positions.get(sec)
        if not pos or pos.total_amount <= 0:
            del g.positions[idx][sec]
            g.strategy_avg_cost.get(idx, {}).pop(sec, None)
            unregister_security_ownership(sec, idx)

    for security, pos in context.portfolio.positions.items():
        if not pos or pos.total_amount <= 0:
            continue

        owners = get_security_owners(security)
        if idx not in owners:
            continue

        actual_total = pos.total_amount

        if len(owners) <= 1:
            tracked = g.positions[idx].get(security, 0)
            if tracked <= 0:
                g.positions[idx][security] = actual_total
            else:
                g.positions[idx][security] = min(tracked, actual_total)
        else:
            total_tracked = 0
            for oid in owners:
                total_tracked += g.positions.get(oid, {}).get(security, 0)

            if total_tracked <= 0:
                my_amount = _calc_shared_amount(pos, idx)
                g.positions[idx][security] = my_amount
            elif total_tracked != actual_total:
                diff = actual_total - total_tracked
                round_lot = 100
                distributed = 0
                for i, oid in enumerate(sorted(owners)):
                    old_amt = g.positions.get(oid, {}).get(security, 0)
                    if i == len(owners) - 1:
                        new_amt = old_amt + diff - distributed
                    else:
                        share = int(round(diff * old_amt / total_tracked / round_lot)) * round_lot if total_tracked > 0 else 0
                        distributed += share
                        new_amt = old_amt + share
                    new_amt = max(0, min(new_amt, actual_total))
                    g.positions.setdefault(oid, {})[security] = new_amt

    equity, vcash = _calc_virtual_equity(context, idx, current_data=current_data)
    g.strategy_virtual_equity[idx] = equity
    g.strategy_virtual_cash[idx] = vcash


def _calc_shared_amount(pos, idx):
    owners = get_security_owners(pos.security)
    if not owners:
        return pos.total_amount
    return pos.total_amount // len(owners) // 100 * 100


def update_strategy_virtual_equity(context, idx):
    equity, vcash = _calc_virtual_equity(context, idx)
    g.strategy_virtual_equity[idx] = equity
    g.strategy_virtual_cash[idx] = vcash


# ==================== 日开盘调度 ====================

def _daily_open_reset(context):
    log.info("框架版本: %s" % getattr(g, '_framework_version', '(未设置)'))

    current_data = get_current_data()
    for idx in range(len(g.portfolio_value_proportion)):
        if g.portfolio_value_proportion[idx] > 0:
            reconcile_strategy_positions(context, idx, current_data=current_data)

    for idx in range(len(g.portfolio_value_proportion)):
        if g.portfolio_value_proportion[idx] > 0:
            initial = context.portfolio.starting_cash * g.portfolio_value_proportion[idx]
            current = g.strategy_virtual_equity.get(idx, initial)
            if current < initial * DRAWDOWN_WARNING_THRESHOLD:
                log.warning("【风控警告】策略[%d]虚拟权益=%.2f（初始=%.2f）低于%.0f%%" % (
                    idx, current, initial, DRAWDOWN_WARNING_THRESHOLD * 100))


# ==================== 收盘持仓报表 ====================

def print_summary(context):
    log.info("=" * 50 + " 每日多策略持仓与收益明细 " + "=" * 50)
    pt = PrettyTable(["策略分类/标的代码", "标的名称", "持仓数量", "当前价格", "持仓成本", "浮动盈亏(%)", "浮动盈亏(元)", "持仓市值(元)"])
    pt.align = "r"
    pt.align["策略分类/标的代码"] = "l"
    pt.align["标的名称"] = "c"

    current_data = get_current_data()
    total_market_value = 0

    for strategy in g.strategys.values():
        idx = strategy.index
        strategy_name = strategy.display_name
        holdings = g.positions[idx]

        # 使用统一方法更新权益（不再手工计算，避免与_calc_virtual_equity冗余）
        update_strategy_virtual_equity(context, idx)
        current_virtual_equity = g.strategy_virtual_equity[idx]

        # 单次遍历：同时计算市值 + 收集行数据
        strat_mkt_val = 0.0
        rows = []
        for stock, amount in holdings.items():
            if amount == 0 or stock not in context.portfolio.positions:
                continue
            pos = context.portfolio.positions.get(stock)
            if not pos or pos.total_amount <= 0:
                continue
            curr_p = current_data[stock].last_price
            cost_p = g.strategy_avg_cost[idx].get(stock, pos.avg_cost)
            market_val = amount * curr_p
            strat_mkt_val += market_val
            float_pnl_val = amount * (curr_p - cost_p)
            float_pnl_pct = ((curr_p / cost_p) - 1) * 100 if cost_p > 0 else 0
            rows.append(["  " + stock, current_data[stock].name, amount,
                         "%.3f" % curr_p, "%.3f" % cost_p, "%+.2f%%" % float_pnl_pct, "%.2f" % float_pnl_val, "%.2f" % market_val])

        total_market_value += strat_mkt_val

        initial_capital = context.portfolio.starting_cash * g.portfolio_value_proportion[idx]
        yest_virtual_equity = g.strategy_last_virtual_equity[idx]

        daily_ret = ((current_virtual_equity / yest_virtual_equity) - 1) * 100 if yest_virtual_equity > 0 else 0
        cum_ret = ((current_virtual_equity / initial_capital) - 1) * 100 if initial_capital > 0 else 0

        pt.add_row([
            "【%s】" % strategy_name, "当日: %+.2f%%" % daily_ret, "",
            "累计: %+.2f%%" % cum_ret, "", "权益:", "", "%.2f" % current_virtual_equity
        ])

        if not rows:
            pt.add_row(["  [ 空仓防守避险中 ]", "-", "-", "-", "-", "-", "-", "-"])
        else:
            for r in rows:
                pt.add_row(r)
        pt.add_row(["-" * 24, "-" * 10, "-" * 10, "-" * 10, "-" * 10, "-" * 12, "-" * 12, "-" * 14])

    log.info("\n" + pt.get_string())

    overall_total = context.portfolio.total_value
    if not hasattr(g, 'overall_last_value'):
        g.overall_last_value = context.portfolio.starting_cash

    overall_daily_ret = (overall_total / g.overall_last_value - 1) * 100
    overall_cum_ret = (overall_total / context.portfolio.starting_cash - 1) * 100

    g.overall_last_value = overall_total
    for idx in g.strategy_last_virtual_equity:
        g.strategy_last_virtual_equity[idx] = g.strategy_virtual_equity[idx]

    log.info("【资金汇总】 总资产: %.2f | 账户余额: %.2f | 持仓总市值: %.2f" % (overall_total, context.portfolio.available_cash, total_market_value))
    log.info("【全局表现】 今日总资产涨跌: %+.2f%% | 账户累计净收益: %+.2f%%" % (overall_daily_ret, overall_cum_ret))

    record_kwargs = {}
    for strategy in g.strategys.values():
        record_kwargs.update(strategy.get_record_kwargs(context))
    if record_kwargs:
        record(**record_kwargs)


# ==================== 在线更新恢复 ====================
# after_code_changed 仅实盘使用，回测时聚宽会误触发导致双重初始化
# 如需实盘，请恢复此函数（参考框架参考目录中的完整实现）


# ==================== 资金再平衡 ====================

def capital_rebalance(context):
    """资金再平衡：将各策略虚拟权益调整到目标比例

    机制：通过 strategy_rebalance_adjustment 调整各策略的可用权益，
    不直接修改 realized_pnl 或 initial_capital。
    下次 _calc_virtual_equity 自动生效。

    持仓调整延迟到首次下单时统一执行（execute_rebalance_holdings）。

    自适应触发：过了最小间隔后每天检查偏差，偏差达标才执行。
    触发条件：距上次再平衡的交易日数 >= CAPITAL_REBALANCE_MIN_INTERVAL
    且最大相对偏移率 > CAPITAL_REBALANCE_DEVIATION
    """
    if not ENABLE_CAPITAL_REBALANCE or CAPITAL_REBALANCE_MIN_INTERVAL <= 0:
        return

    # 累计交易日计数器+1
    g._trade_day_counter += 1

    # 检查是否达到最小再平衡间隔
    days_since_last = g._trade_day_counter - g._last_rebalance_trade_count
    if days_since_last < CAPITAL_REBALANCE_MIN_INTERVAL:
        return

    n = len(g.portfolio_value_proportion)
    target_props = list(g.portfolio_value_proportion)

    # 1. 先强制刷新所有策略的虚拟权益
    for i in range(n):
        if target_props[i] > 0:
            update_strategy_virtual_equity(context, i)

    # 2. 计算总权益
    total_equity = sum(g.strategy_virtual_equity.get(i, 0) for i in range(n))
    if total_equity <= 0:
        return

    # 3. 检查偏差（相对偏移率：|actual_pct - target_pct| / target_pct）
    max_rel_dev = 0
    for i in range(n):
        if target_props[i] <= 0:
            continue
        current_pct = g.strategy_virtual_equity.get(i, 0) / total_equity
        rel_dev = abs(current_pct - target_props[i]) / target_props[i]
        max_rel_dev = max(max_rel_dev, rel_dev)

    if max_rel_dev < CAPITAL_REBALANCE_DEVIATION:
        log.info("【资金再平衡】已过最小间隔%d天，但最大相对偏移%.1f%% < 阈值%.0f%%，继续等待" % (
            days_since_last, max_rel_dev * 100, CAPITAL_REBALANCE_DEVIATION * 100))
        # 不重置计数器！明天继续检查偏差
        return

    # 4. 保存再平衡前权益（供 execute_rebalance_holdings 计算缩放比例）
    g._pre_rebalance_equity = {i: g.strategy_virtual_equity.get(i, 0) for i in range(n)}

    # 5. 执行资金调整
    for i in range(n):
        if target_props[i] <= 0:
            continue
        target_equity = total_equity * target_props[i]
        current_equity = g.strategy_virtual_equity.get(i, 0)
        diff = target_equity - current_equity  # 正=需注入，负=需抽出

        if abs(diff) < total_equity * 0.01:
            continue

        # 更新调整量（累加，因为可能多次再平衡）
        old_adj = g.strategy_rebalance_adjustment.get(i, 0.0)
        g.strategy_rebalance_adjustment[i] = old_adj + diff

        # 同步更新虚拟权益和虚拟现金
        g.strategy_virtual_equity[i] = target_equity
        g.strategy_virtual_cash[i] += diff

        # 同步更新 last_equity，避免当日收益率跳变
        g.strategy_last_virtual_equity[i] = target_equity

        # 获取策略名
        strategy = None
        for s in g.strategys.values():
            if s.index == i:
                strategy = s
                break
        display_name = strategy.display_name if strategy else "策略[%d]" % i
        log.info("【资金再平衡】%s: 权益 %.0f → %.0f (%+.0f, 占比 %.0f%% → %.0f%%)" % (
            display_name, current_equity, target_equity, diff,
            current_equity / total_equity * 100, target_props[i] * 100
        ))

    # 6. 设置待处理标记，延迟到首次下单时统一调整持仓
    g._pending_rebalance = True
    g._last_rebalance_trade_count = g._trade_day_counter
    log.info("【资金再平衡】资金池调整完成，持仓调整待首次下单时统一执行，间隔%d天，总权益=%.0f" % (
        days_since_last, total_equity))


def execute_rebalance_holdings(context):
    """统一调整所有策略持仓：按新虚拟资金等比例缩放，先卖后买

    在 run_rebalance 首次调用时触发（由 _pending_rebalance 标记驱动）。
    对每个策略的现有持仓，按新虚拟权益/旧虚拟权益的比例缩放：
    - 缩放比例 < 1 的策略（被抽资金）：先卖出超额持仓
    - 缩放比例 > 1 的策略（被注资金）：后买入增配持仓
    """
    if not g._pending_rebalance:
        return

    g._pending_rebalance = False  # 先清除标记，防止递归

    n = len(g.portfolio_value_proportion)
    target_props = list(g.portfolio_value_proportion)
    current_data = get_current_data()

    # 1. 收集每个策略的缩放比例
    scale_info = {}  # {strategy_index: (scale_ratio, old_equity, new_equity, strategy)}
    pre_equity = getattr(g, '_pre_rebalance_equity', {})
    for s in g.strategys.values():
        i = s.index
        if target_props[i] <= 0:
            continue
        new_equity = g.strategy_virtual_equity.get(i, 0)
        old_equity = pre_equity.get(i, new_equity)  # 再平衡前的权益
        scale_ratio = new_equity / old_equity if old_equity > 0 else 1.0
        scale_info[i] = (scale_ratio, old_equity, new_equity, s)

    # 2. 先卖：处理缩放比例 < 1 的策略
    for i, (scale_ratio, old_eq, new_eq, strategy) in scale_info.items():
        if scale_ratio >= 1.0:
            continue  # 只处理被抽资金的策略
        for stock in list(g.positions[i].keys()):
            real_pos = context.portfolio.positions.get(stock)
            real_total = real_pos.total_amount if real_pos else 0
            my_amount = min(g.positions[i].get(stock, 0), real_total)
            if my_amount <= 0:
                continue
            target_amount = int(my_amount * scale_ratio / 100) * 100  # 取整到100股
            if target_amount >= my_amount:
                continue
            target_value = target_amount * current_data[stock].last_price
            strategy.order_target_value_(stock, target_value, trigger="rebalance_sell",
                                         current_data=current_data)
        log.info("【资金再平衡·持仓调整】%s: 卖出完成 (缩放%.1f%%, 权益 %.0f→%.0f)" % (
            strategy.display_name, scale_ratio * 100, old_eq, new_eq))

    # 3. 后买：处理缩放比例 > 1 的策略
    for i, (scale_ratio, old_eq, new_eq, strategy) in scale_info.items():
        if scale_ratio <= 1.0:
            continue  # 只处理被注资金的策略
        available_cash = strategy.get_strategy_available_cash()
        if available_cash <= 0:
            continue
        # 按现有持仓比例分配新增资金
        positions_value = {}
        total_pos_value = 0
        for stock in g.positions[i].keys():
            real_pos = context.portfolio.positions.get(stock)
            real_total = real_pos.total_amount if real_pos else 0
            my_amount = min(g.positions[i].get(stock, 0), real_total)
            if my_amount <= 0:
                continue
            price = current_data[stock].last_price
            pos_value = my_amount * price
            positions_value[stock] = pos_value
            total_pos_value += pos_value

        if total_pos_value <= 0:
            continue

        # 等额分配新增资金，避免按市值比例分配形成追涨杀跌正反馈
        n_positions = len(positions_value)
        buy_budget = available_cash / n_positions * CASH_BUFFER_RATIO
        for stock, pos_value in positions_value.items():
            if buy_budget < strategy.min_money:
                continue
            target_value = pos_value + buy_budget
            strategy.order_target_value_(stock, target_value, trigger="rebalance_buy",
                                         current_data=current_data)

        log.info("【资金再平衡·持仓调整】%s: 买入完成 (缩放%.1f%%, 权益 %.0f→%.0f)" % (
            strategy.display_name, scale_ratio * 100, old_eq, new_eq))

    log.info("【资金再平衡】持仓统一调整完成（先卖后买）")


# ==================== 初始化模板 ====================

def initialize_template(context, framework_version="V7.0",
                        portfolio_proportion=None,
                        benchmark_code="000300.XSHG"):
    if portfolio_proportion is None:
        portfolio_proportion = [0.4, 0.3, 0.3]
    set_benchmark(benchmark_code)
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    log.set_level("order", "error")
    log.set_level("system", "error")

    # stock slippage & commission
    set_slippage(PriceRelatedSlippage(STOCK_SLIPPAGE), type="stock")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=STOCK_CLOSE_TAX,
        open_commission=OPEN_COMMISSION, close_commission=CLOSE_COMMISSION,
        close_today_commission=0, min_commission=MIN_COMMISSION
    ), type="stock")

    # fund slippage & commission
    set_slippage(PriceRelatedSlippage(FUND_SLIPPAGE), type="fund")
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=OPEN_COMMISSION, close_commission=CLOSE_COMMISSION,
        close_today_commission=0, min_commission=MIN_COMMISSION
    ), type="fund")

    g.strategys = {}
    g.portfolio_value_proportion = list(portfolio_proportion)
    n_strategies = len(portfolio_proportion)
    g.positions = {i: {} for i in range(n_strategies)}
    g.strategy_realized_pnl = {i: 0.0 for i in range(n_strategies)}
    g.strategy_virtual_equity = {}
    g.strategy_last_virtual_equity = {}
    g.strategy_virtual_cash = {}
    g.strategy_avg_cost = {i: {} for i in range(n_strategies)}

    # 资金再平衡全局状态
    g.strategy_rebalance_adjustment = {i: 0.0 for i in range(n_strategies)}
    g._last_rebalance_trade_count = 0
    g._trade_day_counter = 0
    g._pending_rebalance = False

    for i, prop in enumerate(g.portfolio_value_proportion):
        initial_cap = context.portfolio.starting_cash * prop
        g.strategy_virtual_equity[i] = initial_cap
        g.strategy_last_virtual_equity[i] = initial_cap
        g.strategy_virtual_cash[i] = initial_cap

    g.overall_last_value = context.portfolio.starting_cash
    g.security_ownership = {}

    log.info("框架初始化完成 版本=%s 策略数=%d 比例=%s" % (framework_version, n_strategies, str(portfolio_proportion)))

    g._framework_version = framework_version


# ==================== 收盘清理 ====================

def end_trade(context):
    # 清理已不在投资组合中的过期持仓记录
    for idx in range(len(g.portfolio_value_proportion)):
        if g.portfolio_value_proportion[idx] > 0:
            for sec in list(g.positions[idx].keys()):
                pos = context.portfolio.positions.get(sec)
                if not pos or pos.total_amount == 0:
                    g.positions[idx].pop(sec, None)
                    g.strategy_avg_cost[idx].pop(sec, None)

    # 处理无归属持仓和零股
    marked = {s for d in g.positions.values() for s in d}
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions.get(stock)
        if not pos:
            continue
        if stock not in marked:
            # 无归属的持仓，清仓
            if pos.closeable_amount > 0:
                order(stock, -pos.closeable_amount)
            g.security_ownership.pop(stock, None)
        elif pos.total_amount < 100:
            owners = get_security_owners(stock)
            if not owners:
                # 有标记但无归属，清仓
                if pos.closeable_amount > 0:
                    order(stock, -pos.closeable_amount)
                g.security_ownership.pop(stock, None)
            else:
                # 有归属的零股：尝试卖出
                if pos.closeable_amount > 0:
                    order(stock, -pos.closeable_amount)
                    for pid in list(g.positions.keys()):
                        g.positions[pid].pop(stock, None)
                    g.security_ownership.pop(stock, None)


# ==================== 七星高照ETF轮动策略 ====================

class QixingStrategy(Strategy):
    version = "V7.20260701.0200"

    def __init__(self, context, index, name, display_name):
        super().__init__(context, index, name, display_name)
        self.etf_pool = list(QIXING_ETF_POOL)
        self.defensive_etf = QIXING_DEFENSIVE_ETF
        self.lookback_days = QIXING_LOOKBACK_DAYS
        self.holdings_num = QIXING_HOLDINGS_NUM
        self.enable_rebalance = True
        self.min_money = QIXING_MIN_MONEY
        self.enable_profit_protection = QIXING_ENABLE_PROFIT_PROTECTION
        self.profit_protection_lookback = 1
        self.profit_protection_threshold = QIXING_PROFIT_PROTECTION_THRESHOLD
        self.loss = QIXING_LOSS
        self.min_score_threshold = QIXING_MIN_SCORE_THRESHOLD
        self.max_score_threshold = QIXING_MAX_SCORE_THRESHOLD
        self.enable_volume_check = QIXING_ENABLE_VOLUME_CHECK
        self.volume_lookback = 5
        self.volume_threshold = QIXING_VOLUME_THRESHOLD
        self.volume_return_limit = 1
        self.use_short_momentum_filter = QIXING_USE_SHORT_MOMENTUM_FILTER
        self.short_lookback_days = QIXING_SHORT_LOOKBACK_DAYS
        self.short_momentum_threshold = 0.0
        self.enable_premium_filter = QIXING_ENABLE_PREMIUM_FILTER
        self.premium_threshold = QIXING_PREMIUM_THRESHOLD
        self.rankings_cache = {'date': None, 'data': None}
        self.rebalance_threshold_pct = 0.05  # 5%容差避免频繁小额调仓
        self._batch_prices = {}
        self._momentum_highs = {}
        self._batch_nav = {}
        self._profit_check_cooldown_until = None  # 盈利保护触发后的冷却截止时间

    def _check_defensive_etf_available(self):
        return self._is_tradeable(self.defensive_etf)

    def _check_profit_protection(self, security, lookback=None, threshold=None, current_data=None):
        if not self.enable_profit_protection:
            return False
        lookback = lookback or self.profit_protection_lookback
        threshold = threshold or self.profit_protection_threshold

        cache = self._momentum_highs.get(security, {})
        cached_highs = cache.get('recent_highs', None)
        if cached_highs is not None and len(cached_highs) >= lookback:
            max_high = max(cached_highs[-lookback:])
        else:
            hist = attribute_history(security, lookback, '1d', ['high'])
            if hist.empty or len(hist) < lookback:
                return False
            max_high = hist['high'].max()

        if current_data is None:
            current_data = get_current_data()
        current_price = current_data[security].last_price
        if current_price <= max_high * (1 - threshold):
            log.info("【七星盈利保护】%s %s 触发盈利保护：当前价%.3f，最近%d日最高%.3f，回撤%.2f%% > %.0f%%" % (
                security, self.get_security_name(security), current_price, lookback, max_high,
                (1 - current_price / max_high) * 100, threshold * 100))
            return True
        return False

    def _get_premium_rate(self, code, date, max_back_days=5):
        # 优先从批量价格缓存获取收盘价
        batch = self._batch_prices
        if code in batch and len(batch[code][0]) > 0:
            price = float(batch[code][0][-1])
        else:
            price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
            if price_data.empty:
                return None, None, None
            price = price_data['close'].iloc[0]

        net_value = None

        batch_nav = self._batch_nav
        if batch_nav and code in batch_nav:
            net_value = batch_nav[code]

        if net_value is None:
            start_date = date - datetime.timedelta(days=max_back_days * 2)
            trade_days = get_trade_days(start_date=start_date, end_date=date)
            trade_days = [pd.to_datetime(d).date() for d in trade_days]
            for dt in reversed(trade_days):
                if dt > date:
                    continue
                net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
                if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
                    net_value = net_data[code].iloc[0]
                    break
                try:
                    q = query(finance.FUND_NET_VALUE).filter(
                        finance.FUND_NET_VALUE.code == code,
                        finance.FUND_NET_VALUE.day == dt
                    )
                    net_df = finance.run_query(q)
                    if not net_df.empty:
                        net_value = net_df['net_value'].iloc[0]
                        break
                except Exception:
                    continue
        if net_value is None:
            return None, None, None
        premium_rate = (price - net_value) / net_value
        return premium_rate, price, net_value

    def _get_volume_ratio(self, security):
        try:
            hist = attribute_history(security, self.volume_lookback, '1d', ['volume'])
            if hist.empty or len(hist) < self.volume_lookback:
                return None
            avg_vol = hist['volume'].mean()
            today = self.context.current_dt.date()
            df_vol = get_price(security, start_date=today, end_date=self.context.current_dt,
                               frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
            if df_vol is None or df_vol.empty:
                return None
            current_vol = df_vol['volume'].sum()
            ratio = current_vol / avg_vol if avg_vol > 0 else 0
            if ratio > self.volume_threshold:
                return ratio
            return None
        except Exception:
            return None

    def _calculate_momentum_metrics(self, etf, current_data=None):
        try:
            name = self.get_security_name(etf)
            lookback = max(self.lookback_days, self.short_lookback_days) + 20

            batch = self._batch_prices
            if etf in batch and len(batch[etf][0]) >= self.lookback_days:
                closes, highs_arr = batch[etf]
                prices = pd.DataFrame({'close': closes, 'high': highs_arr})
            else:
                prices = attribute_history(etf, lookback, '1d', ['close', 'high'])

            if len(prices) < self.lookback_days:
                return None

            if current_data is None:
                current_data = get_current_data()
            current_price = current_data[etf].last_price
            price_series = np.append(prices["close"].values, current_price)

            if self._check_profit_protection(etf, current_data=current_data):
                log.info("【七星排名】%s %s 触发盈利保护，从排名中排除" % (etf, name))
                return None

            if self.enable_premium_filter:
                prev_date = get_trade_days(end_date=self.context.current_dt.date(), count=2)[0]
                premium, _, _ = self._get_premium_rate(etf, prev_date)
                if premium is not None:
                    if premium > self.premium_threshold:
                        log.info("【七星排名】%s %s 溢价率%.2f%% > %.0f%%，从排名中排除" % (
                            etf, name, premium * 100, self.premium_threshold * 100))
                        return None

            # 提前做主WLS拟合，复用于volume_check和评分计算
            recent = price_series[-(self.lookback_days + 1):]
            y = np.log(recent)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            slope, intercept, r_squared = self._wls_fit(x, y, weights)
            annualized_returns = math.exp(slope * 250) - 1

            if self.enable_volume_check:
                vol_ratio = self._get_volume_ratio(etf)
                if vol_ratio is not None:
                    if annualized_returns > self.volume_return_limit:
                        log.info("【七星排名】%s %s 成交量放量%.1f倍，且年化%.1f%% > 阈值%.1f%%，过滤" % (
                            etf, name, vol_ratio, annualized_returns * 100, self.volume_return_limit * 100))
                        return None

            if len(price_series) >= self.short_lookback_days + 1:
                short_return = price_series[-1] / price_series[-(self.short_lookback_days + 1)] - 1
                short_annualized = (1 + short_return) ** (250 / self.short_lookback_days) - 1
            else:
                short_annualized = 0

            if self.use_short_momentum_filter and short_annualized < self.short_momentum_threshold:
                return None

            score = annualized_returns * r_squared

            if len(price_series) >= 4:
                day1 = price_series[-1] / price_series[-2]
                day2 = price_series[-2] / price_series[-3]
                day3 = price_series[-3] / price_series[-4]
                if min(day1, day2, day3) < self.loss:
                    log.info("【七星排名】%s %s 近3日有单日跌幅超%.1f%%，直接排除" % (
                        etf, name, (1 - self.loss) * 100))
                    return None

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
            log.warning("计算%s %s时出错: %s" % (etf, self.get_security_name(etf), e))
            return None

    def _get_cached_rankings(self):
        today = self.context.current_dt.date()
        if self.rankings_cache['date'] != today:
            log.info("重新计算ETF排名...")
            ranked = self._get_ranked_etfs()
            self.rankings_cache = {'date': today, 'data': ranked}
        return self.rankings_cache['data']

    def _get_ranked_etfs(self):
        eligible_etfs = [etf for etf in self.etf_pool if not self._is_suspended(etf)]
        lookback = max(self.lookback_days, self.short_lookback_days) + 20

        if eligible_etfs:
            try:
                price_panel = history(lookback, '1d', ['close', 'high'], eligible_etfs, fq='pre', skip_paused=True)
                self._batch_prices = {}
                for etf in eligible_etfs:
                    if etf in price_panel and len(price_panel[etf]) >= self.lookback_days:
                        df = price_panel[etf]
                        self._batch_prices[etf] = (df['close'].values, df['high'].values)
                        highs = df['high'].values[-max(self.profit_protection_lookback, 5):]
                        self._momentum_highs.setdefault(etf, {})['recent_highs'] = highs
            except Exception:
                self._batch_prices = {}
        else:
            self._batch_prices = {}

        if self.enable_premium_filter and eligible_etfs:
            try:
                prev_date = get_trade_days(end_date=self.context.current_dt.date(), count=2)[0]
                start_date = prev_date - datetime.timedelta(days=10)
                nav_df = get_extras('unit_net_value', eligible_etfs, start_date=start_date, end_date=prev_date, df=True)
                self._batch_nav = {}
                if not nav_df.empty:
                    for etf in eligible_etfs:
                        col = nav_df.get(etf)
                        if col is not None and not col.dropna().empty:
                            self._batch_nav[etf] = col.dropna().iloc[-1]
            except Exception:
                self._batch_nav = {}
        else:
            self._batch_nav = {}

        current_data = get_current_data()
        etf_metrics = []
        for etf in eligible_etfs:
            metrics = self._calculate_momentum_metrics(etf, current_data=current_data)
            if metrics is not None:
                if self.min_score_threshold < metrics['score'] < self.max_score_threshold:
                    etf_metrics.append(metrics)
        etf_metrics.sort(key=lambda x: x['score'], reverse=True)
        return etf_metrics

    def _determine_targets(self, ranked):
        target_etfs = []
        for m in ranked[:self.holdings_num]:
            if m['score'] >= self.min_score_threshold:
                target_etfs.append(m['etf'])

        if not target_etfs:
            if self._check_defensive_etf_available():
                log.info("【七星防御】进入防御模式，选择防御ETF：%s" % self.defensive_etf)
                return [self.defensive_etf], True
            return None, None
        return target_etfs, False

    def rebalance(self, context):
        self.context = context

        ranked = self._get_cached_rankings()

        log.info("=== 七星ETF排名前5 ===")
        for i, m in enumerate(ranked[:5]):
            log.info("排名%d: %s %s 得分%.4f 年化%.2f%% R²=%.4f" % (
                i + 1, m['etf'], m['etf_name'], m['score'], m['annualized_returns'] * 100, m['r_squared']))

        target_etfs, defensive_mode = self._determine_targets(ranked)

        if target_etfs is None:
            log.info("【七星轮动】无目标ETF且防御不可用，保持空仓")
            self._adjust({})
            return

        weight = 1.0 / len(target_etfs)
        targets = {etf: weight for etf in target_etfs}

        # 实盘优化：先卖后买，同bar完成（ETF资金T+0可用）
        self._adjust(targets)

        self.current_targets = targets

    def intraday_check(self, context):
        """盘中风控：盈利保护检查"""
        self.profit_check(context)

    def profit_check(self, context):
        self.context = context
        if not self.enable_profit_protection:
            return

        triggered = []
        current_data = get_current_data()
        holdings = self.get_holdings()
        for sec, amount in holdings.items():
            if sec not in self.etf_pool and sec != self.defensive_etf:
                continue
            if amount > 0:
                if self._check_profit_protection(sec, current_data=current_data):
                    triggered.append(sec)

        if triggered:
            log.info("========== 七星盈利保护独立检查：触发 %d 只 ==========" % len(triggered))
            # 从当前目标中移除触发标的，通过_adjust统一执行卖出和再平衡
            remaining_keys = [s for s in self.current_targets.keys() if s not in triggered]
            if remaining_keys:
                # 等权分配，不依赖原始权重值
                weight = 1.0 / len(remaining_keys)
                remaining_targets = {s: weight for s in remaining_keys}
            else:
                remaining_targets = {}
            if not remaining_targets and self._check_defensive_etf_available():
                remaining_targets = {self.defensive_etf: 1.0}
                log.info("【七星盈利保护】全部触发，进入防御ETF：%s" % self.defensive_etf)
            self._adjust(remaining_targets)
            self.current_targets = remaining_targets
            for sec in triggered:
                log.info("【七星盈利保护】卖出：%s %s" % (sec, self.get_security_name(sec)))
            # 设置冷却期，避免短时间内反复触发
            self._profit_check_cooldown_until = context.current_dt + datetime.timedelta(minutes=QIXING_MINUTE_PROFIT_COOLDOWN)


# ==================== 红利低波成长策略 ====================

class DividendGrowthStrategy(Strategy):
    """红利低波成长策略

    选股逻辑：
    1. 基础过滤：剔除次新/科创北证/ST/停牌
    2. 基本面过滤：PE 5~50, ROE 5~100, 营收增长 5~100, 利润增长 10~100
    3. 股息率过滤：取top 10%，阈值3%
    4. 取前 stock_num 只等权持有

    调仓频率：月频（每月1日）
    风控：涨停打开卖出
    """

    version = "V7.20260701.0200"

    def __init__(self, context, index, name, display_name):
        super().__init__(context, index, name, display_name)
        self.stock_num = DIVIDEND_STOCK_NUM
        self.enable_rebalance = True
        self.high_limit_list = []
        self.min_money = DIVIDEND_MIN_MONEY

    def get_targets(self, context):
        """选股并返回目标持仓权重字典 {stock: weight}

        资金适配：根据策略可用资金和当前股价，动态过滤买不起1手的股票，
        并调整持仓数量确保每只至少能买100股。
        """
        self.context = context
        today = context.current_dt

        # 1. 基础过滤
        initial_list = get_all_securities('stock', today).index.tolist()
        initial_list = self._filter_new_stock(initial_list, 250)
        initial_list = self._filter_kcb_stock(initial_list)
        initial_list = self.filter_basic_stock(initial_list)

        # 2. 基本面过滤
        stock_list = initial_list
        df = get_fundamentals(query(
            valuation.code,
        ).filter(
            valuation.code.in_(stock_list),
            valuation.pe_ratio.between(*DIVIDEND_PE_RANGE),
            indicator.inc_return.between(*DIVIDEND_ROE_RANGE),
            indicator.inc_total_revenue_year_on_year.between(*DIVIDEND_REVENUE_GROWTH_RANGE),
            indicator.inc_net_profit_year_on_year.between(*DIVIDEND_PROFIT_GROWTH_RANGE),
        ))
        stock_list = list(df.code)
        if not stock_list:
            log.info("【%s】基本面过滤后无标的（PE/ROE/营收增长/利润增长条件）" % self.display_name)
            return {}

        # 3. 股息率过滤
        stock_list = self._get_dividend_ratio_filter(stock_list, False, 0.00, DIVIDEND_RATIO_TOP_PCT, DIVIDEND_RATIO_MIN)
        candidate_list = stock_list[:min(self.stock_num, len(stock_list))]

        if not candidate_list:
            log.info("【%s】股息率过滤后无符合条件的标的，空仓" % self.display_name)
            return {}

        # 4. 资金适配：先确保每只候选股各买1手，剩余资金按手数分配尽量用完
        strategy_value = self.get_portfolio_value()
        current_data = get_current_data()

        # 计算每只候选股的1手价格
        stock_prices = {}
        for stock in candidate_list:
            price = current_data[stock].last_price
            if price > 0:
                stock_prices[stock] = price

        if not stock_prices:
            log.info("【%s】无有效报价的候选股，空仓" % self.display_name)
            return {}

        # 调用基类资金适配方法
        hands = self.allocate_equal_capital(stock_prices, strategy_value, CASH_BUFFER_RATIO)

        if not hands:
            log.info("【%s】资金不足或无有效报价，空仓" % self.display_name)
            return {}

        # 缓存手数和价格，供 rebalance 直接按手数精确下单
        self._cached_hands = hands
        self._cached_stock_prices = stock_prices

        # 计算权重（用于日志和 current_targets 记录）
        targets = {}
        for stock, h in hands.items():
            targets[stock] = (h * stock_prices[stock] * 100) / strategy_value

        log.info("【%s】资金分配: %s" % (
            self.display_name,
            {s: '%d手' % h for s, h in hands.items()}))

        log.info("【%s】选股完成: %s (资金适配: %d/%d, 可用=%.0f)" % (
            self.display_name, list(hands.keys()), len(hands), len(candidate_list),
            strategy_value * CASH_BUFFER_RATIO))
        return targets

    def prepare_stock_list(self, context):
        """09:01盘前选股：准备涨停列表和目标持仓"""
        self.context = context
        self._prepare_high_limit_list(context)
        self._cached_targets = self.get_targets(context)

    def rebalance(self, context):
        """月频调仓：按手数精确下单，避免权重路径的资金闲置"""
        self.context = context
        targets = getattr(self, '_cached_targets', None)
        hands = getattr(self, '_cached_hands', None)
        stock_prices = getattr(self, '_cached_stock_prices', None)

        if targets is None:
            targets = self.get_targets(context)
            hands = getattr(self, '_cached_hands', None)
            stock_prices = getattr(self, '_cached_stock_prices', None)

        if not targets:
            self._adjust({})
            self.current_targets = {}
        elif hands and stock_prices:
            # 股票策略：按手数精确下单
            self._rebalance_by_hands(hands, stock_prices)
            self.current_targets = targets
        else:
            # 兜底：走权重路径
            self._adjust(targets)
            self.current_targets = targets

        self._cached_targets = None
        self._cached_hands = None
        self._cached_stock_prices = None

    def intraday_check(self, context):
        """盘中风控：涨停打开检查"""
        self.check_limit_up(context)

    def check_limit_up(self, context):
        """盘中检查：昨日涨停股若涨停打开则卖出并重新平衡"""
        self.context = context
        # 每天更新昨日涨停列表（prepare_stock_list 仅月频调用，此处补齐日频更新）
        self._prepare_high_limit_list(context)
        if not self.high_limit_list:
            return
        current_data = get_current_data()
        opened = []
        for s in self.high_limit_list:
            if self.has_position(s):
                if current_data[s].last_price < current_data[s].high_limit:
                    opened.append(s)
                    log.info("【%s】%s 涨停打开，卖出" % (self.display_name, s))
                else:
                    log.info("【%s】%s 涨停，继续持有" % (self.display_name, s))
        if opened:
            remaining_keys = [s for s in self.current_targets.keys() if s not in opened]
            if remaining_keys:
                # 优先走手数精确路径，避免权重路径的资金闲置
                stock_prices = {s: current_data[s].last_price for s in remaining_keys if current_data[s].last_price > 0}
                strategy_value = self.get_portfolio_value()
                if stock_prices:
                    hands = self.allocate_equal_capital(stock_prices, strategy_value, CASH_BUFFER_RATIO)
                    if hands:
                        self._rebalance_by_hands(hands, stock_prices)
                        targets = {}
                        for stock, h in hands.items():
                            targets[stock] = (h * stock_prices[stock] * 100) / strategy_value
                        self.current_targets = targets
                        return
                # 兜底：走权重路径
                weight = 1.0 / len(remaining_keys)
                updated_targets = {s: weight for s in remaining_keys}
            else:
                updated_targets = {}
            self._adjust(updated_targets)
            self.current_targets = updated_targets

    def get_untradeable_stock(self, stocks):
        """重写基类方法：涨停股也加入不可交易列表"""
        untradeable = super().get_untradeable_stock(stocks)
        for stock in self.high_limit_list:
            if stock not in untradeable:
                untradeable.append(stock)
        return untradeable

    def _prepare_high_limit_list(self, context):
        """准备昨日涨停列表（用于调仓时跳过卖出和盘中检查）"""
        self.high_limit_list = []
        hold_list = list(self.get_holdings().keys())
        if hold_list:
            try:
                df = get_price(hold_list, end_date=context.previous_date, frequency='daily',
                              fields=['close', 'high_limit'], count=1, panel=False,
                              fill_paused=False, skip_paused=False).dropna()
                df = df[df['close'] == df['high_limit']]
                self.high_limit_list = list(df.code)
            except Exception:
                pass

    # ==================== 过滤函数 ====================

    def _get_dividend_ratio_filter(self, stock_list, sort, p1, p2, threshold):
        """根据最近一年分红除以当前总市值计算股息率并筛选"""
        time1 = self.context.previous_date
        time0 = time1 - datetime.timedelta(days=365)
        interval = 1000
        list_len = len(stock_list)

        if list_len == 0:
            return []

        # 分批查询，避免聚宽finance API的in_列表长度限制
        n_batches = (list_len + interval - 1) // interval
        dfs = []
        for b in range(n_batches):
            start = interval * b
            end = min(list_len, interval * (b + 1))
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
            ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[start:end]))
            dfs.append(finance.run_query(q))
        df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

        dividend = df.fillna(0)
        dividend = dividend.set_index('code')
        dividend = dividend.groupby('code').sum()
        temp_list = list(dividend.index)

        if not temp_list:
            return []

        q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(temp_list))
        cap = get_fundamentals(q, date=time1)
        cap = cap.set_index('code')

        df = pd.concat([dividend, cap], axis=1, sort=False)
        df['dividend_ratio'] = (df['bonus_amount_rmb'] / 10000) / df['market_cap']
        df = df.sort_values(by=['dividend_ratio'], ascending=sort)
        df = df[int(p1 * len(df)):int(p2 * len(df))]
        df = df[df['dividend_ratio'] > threshold]
        return list(df.index)


# ==================== 四方轮动策略子类 ====================

class SifangStrategy(Strategy):
    """四方轮动ETF动量轮动策略 — 择时优化终版"""
    version = "V7.20260701.0200"

    def __init__(self, context, index, name, display_name):
        super().__init__(context, index, name, display_name)
        self.pool = list(SIFANG_ETF_POOL)
        self.window = SIFANG_LOOKBACK_DAYS
        self.min_score = SIFANG_MIN_SCORE
        self.position_stop_loss_pct = SIFANG_POSITION_STOP_LOSS
        self.max_drawdown_threshold = SIFANG_MAX_DRAWDOWN_THRESHOLD
        self.stop_loss_cooldown_days = SIFANG_STOP_LOSS_COOLDOWN_DAYS
        self.max_equity = 0
        self.stop_loss_first_allowed_date = {}
        self.dd_action_cooldown_date = None
        self._x = np.arange(self.window)

    def _record_stop_loss_cooldown(self, security):
        """止损后登记买回冷却期"""
        stop_day = self.context.current_dt.date()
        n = self.stop_loss_cooldown_days
        arr = get_trade_days(start_date=stop_day, count=n + 10)
        if len(arr) < n + 2:
            return
        # 统一用 pd.Timestamp 转换，避免 numpy.datetime64 没有 .date() 方法导致的类型不一致
        first_allow = pd.Timestamp(arr[n + 1]).date()
        self.stop_loss_first_allowed_date[security] = first_allow
        log.info("【止损冷却】{}最早可买回日{}".format(self.format_security(security), first_allow))

    def pre_rebalance(self, context):
        """调仓前风控：持仓止损 + 回撤清仓"""
        self._sifang_risk_check(context)

    def rebalance(self, context):
        """每日调仓入口：轮动交易"""
        self.context = context
        self._sifang_trade(context)

    def _sifang_risk_check(self, context):
        """风控检查：持仓止损 + 回撤清仓"""
        current_data = get_current_data()
        idx = self.index

        # === 持仓级止损：单标的亏损达阈值强制卖出 ===
        for stock in list(self.get_holdings().keys()):
            if stock not in context.portfolio.positions:
                continue
            pos = context.portfolio.positions[stock]
            if pos.total_amount <= 0:
                continue
            current_price = current_data[stock].last_price
            if current_price <= 0:
                continue
            cost_p = self.get_avg_cost(stock, pos.avg_cost)
            loss_pct = (current_price / cost_p - 1)
            if loss_pct <= -self.position_stop_loss_pct:
                log.info("【持仓止损】{}亏损{:.2%}<={:.0%}，卖出".format(
                    self.format_security(stock), loss_pct, -self.position_stop_loss_pct))
                self.order_target_value_(stock, 0, trigger="stop_loss")
                self._record_stop_loss_cooldown(stock)

        # 止损后对账并更新权益，确保回撤计算准确
        self.reconcile()
        self.update_equity()

        # === 组合级回撤清仓 ===
        # 兜底用本策略初始资金（按比例系数缩放），避免权益清零后 max_equity 被错误拉高到全账户水平
        initial = context.portfolio.starting_cash * g.portfolio_value_proportion[self.index]
        current_value = self.get_portfolio_value() or initial
        if self.max_equity == 0:
            self.max_equity = current_value
        self.max_equity = max(self.max_equity, current_value)

        if self.max_equity <= 0:
            return

        current_drawdown = (self.max_equity - current_value) / self.max_equity

        # 当日已执行过回撤动作则跳过
        if self.dd_action_cooldown_date == context.current_dt.date():
            return

        if current_drawdown < self.max_drawdown_threshold * SIFANG_DRAWDOWN_EARLY_WARNING_RATIO:
            return  # 回撤不大，无需动作

        # 清仓动作
        if current_drawdown >= self.max_drawdown_threshold:
            log.info("【回撤清仓】回撤{:.2%}>={:.0%}，全部清仓".format(current_drawdown, self.max_drawdown_threshold))
            current_holdings = list(self.get_holdings().keys())
            for stock in current_holdings:
                if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
                    self.order_target_value_(stock, 0, trigger="drawdown_liquidation")
                    self._record_stop_loss_cooldown(stock)
            # 清仓后重置max_equity，避免永远无法重新入场
            self.max_equity = current_value
            self.dd_action_cooldown_date = context.current_dt.date()

    def _sifang_trade(self, context):
        """每日计算ETF动量得分，选择得分最高的ETF全仓持有"""
        idx = self.index

        # 剔除停牌标的
        valid_pool = [s for s in self.pool if not self._is_suspended(s)]
        if not valid_pool:
            log.info("【选股】资产池无有效标的，跳过本次扫描。")
            return

        # 止损买回冷却过滤
        if self.stop_loss_first_allowed_date:
            today = context.current_dt.date()
            filtered_pool = []
            for s in valid_pool:
                fa = self.stop_loss_first_allowed_date.get(s)
                if fa is not None and today < fa:
                    log.info("【止损冷却】{}仍在冷却期，最早可买回{}".format(self.format_security(s), fa))
                    continue
                filtered_pool.append(s)
            valid_pool = filtered_pool
            if not valid_pool:
                log.info("【止损冷却】所有候选标的均在冷却期，跳过")
                return

        # 批量获取价格数据（1次API调用替代N次attribute_history）
        batch_data = {}
        if valid_pool:
            try:
                price_panel = history(self.window, '1d', ['close'], valid_pool, fq='pre', skip_paused=True)
                for code in valid_pool:
                    if code in price_panel and len(price_panel[code]) >= self.window:
                        batch_data[code] = price_panel[code]['close'].values
            except Exception:
                batch_data = {}
            # 回退：对未获取到的标的逐个调用attribute_history
            for code in valid_pool:
                if code not in batch_data:
                    try:
                        df = attribute_history(code, self.window, '1d', ['close'])
                        if df is not None and len(df) >= self.window:
                            batch_data[code] = df['close'].values
                    except Exception:
                        pass

        # 计算动量得分（使用_wls_fit替代scipy.linregress）
        score_list = []
        x = self._x
        w = np.ones(self.window)  # OLS = 等权WLS
        for code in valid_pool:
            if code not in batch_data:
                log.info("【选股】{}历史数据不足，跳过。".format(self.format_security(code)))
                continue
            y = np.log(batch_data[code])
            slope, _, r_squared = self._wls_fit(x, y, w)
            annualized_ret = math.exp(slope * 250) - 1
            score = annualized_ret * r_squared
            score_list.append({
                "code": code,
                "name": self.get_security_name(code),
                "score": score,
                "ret": annualized_ret,
                "r2": r_squared
            })

        if not score_list:
            log.info("【选股】无有效动量得分，跳过本次交易。")
            return

        # 排序与信号生成
        df_rank = pd.DataFrame(score_list).sort_values("score", ascending=False)
        log.info("\n【选股】因子评分看板：\n{}".format(
            df_rank[["code", "name", "score", "ret", "r2"]].to_string(index=False)
        ))

        target_etf = df_rank.iloc[0]["code"]
        target_score = float(df_rank.iloc[0]["score"])

        # 得分质量过滤
        if target_score < self.min_score or target_score <= 0:
            reason = "最高得分{:.4f}<阈值{:.4f}".format(target_score, self.min_score) if target_score < self.min_score else "最高得分{:.4f}<=0".format(target_score)
            log.info("【得分过滤】{}，趋势不明确，空仓".format(reason))
            self._adjust({})
            return

        # 通过_adjust统一执行持仓切换
        current_holdings = list(self.get_holdings().keys())
        log.info("【信号】持仓切换：{} -> 目标ETF：{}；目标得分：{:.4f}。".format(
            self.format_security_list(current_holdings),
            self.format_security(target_etf),
            target_score
        ))

        self._adjust({target_etf: 1.0})
        log.info("【交易】全仓买入：{}；目标市值：{:.2f}。".format(
            self.format_security(target_etf),
            self.get_portfolio_value()
        ))


# ==================== 调度封装 ====================

def qixing_profit_check(context):
    """七星盈利保护检查（带冷却机制）"""
    s = g.strategys.get("qixing_strategy")
    if not s or not s.enable_profit_protection:
        return
    if g.portfolio_value_proportion[0] <= 0:
        return
    # 检查冷却期
    if s._profit_check_cooldown_until is not None and context.current_dt < s._profit_check_cooldown_until:
        return
    s.intraday_check(context)


def qixing_rebalance(context):
    s = g.strategys.get("qixing_strategy")
    if s:
        s.run_rebalance(context)


def dividend_growth_prepare(context):
    """盘前选股调度（09:01）"""
    s = g.strategys.get("dividend_growth_strategy")
    if s:
        g._dividend_growth_first_run = False  # 月频已执行，无需日频补执行
        s.prepare_stock_list(context)


def dividend_growth_rebalance(context):
    """月频调仓调度（09:35）"""
    s = g.strategys.get("dividend_growth_strategy")
    if s:
        s.run_rebalance(context)


def dividend_growth_check_limit(context):
    """盘中涨停检查调度（含非1号启动时首次强制执行）"""
    s = g.strategys.get("dividend_growth_strategy")
    if not s:
        return
    # 非1号启动时，月频调度不会触发，在首个交易日强制执行选股+调仓
    # 走完整 run_rebalance 钩子链：update_equity → reconcile → execute_rebalance_holdings → pre_rebalance → rebalance
    if getattr(g, '_dividend_growth_first_run', False):
        s.prepare_stock_list(context)
        s.run_rebalance(context)
        g._dividend_growth_first_run = False
        return
    s.intraday_check(context)


def sifang_rebalance(context):
    """09:50 四方轮动（风控+交易合一）"""
    s = g.strategys.get("sifang")
    if s:
        s.run_rebalance(context)


# ==================== 事件处理 ====================

def on_event(context, event):
    """除权除息事件处理：调整虚拟持仓数量和成本价"""
    if event.name == "Dividends":
        for d in event.dividends:
            scale = d.get("scale_factor", 1)
            if scale != 1:
                code = event.security.code
                for pid, pos in g.positions.items():
                    if code in pos:
                        old = pos[code]
                        new_amount = int(old * scale)
                        new_amount = (new_amount // 100) * 100
                        if new_amount > 0:
                            pos[code] = new_amount
                            # 同步调整成本价：总成本不变，单价 = 总成本 / 新数量
                            old_cost = g.strategy_avg_cost.get(pid, {}).get(code, 0)
                            if old_cost > 0 and new_amount > 0:
                                g.strategy_avg_cost[pid][code] = old_cost * old / new_amount
                        else:
                            pos.pop(code, None)
                            g.strategy_avg_cost.get(pid, {}).pop(code, None)
                # 除权后对账
                for idx in range(len(g.portfolio_value_proportion)):
                    if g.portfolio_value_proportion[idx] > 0:
                        reconcile_strategy_positions(context, idx)


# ==================== 入口函数 ====================

def process_initialize(context):
    g.strategys = {
        name: cls(context, index=idx, name=name, display_name=display_name)
        for display_name, name, cls, idx in [
            ("七星高照ETF轮动", "qixing_strategy", QixingStrategy, 0),
            ("红利低波成长", "dividend_growth_strategy", DividendGrowthStrategy, 1),
            ("四方轮动ETF动量", "sifang", SifangStrategy, 2),
        ]
    }


def initialize(context):
    """聚宽入口函数：初始化框架 + 注册调度。"""
    initialize_template(context, framework_version=FRAMEWORK_VERSION,
                       portfolio_proportion=PORTFOLIO_PROPORTION,
                       benchmark_code="000300.XSHG")

    # 统一创建策略实例
    process_initialize(context)

    # 注册调度
    if g.portfolio_value_proportion[0] > 0:
        run_daily(qixing_rebalance, QIXING_REBALANCE_TIME)
        for check_time in QIXING_PROFIT_CHECK_TIMES:
            run_daily(qixing_profit_check, check_time)

    if g.portfolio_value_proportion[1] > 0:
        g._dividend_growth_first_run = True  # 非1号启动时，首个交易日强制执行选股+调仓
        run_monthly(dividend_growth_prepare, 1, '09:01')
        run_monthly(dividend_growth_rebalance, 1, '09:35')
        run_daily(dividend_growth_check_limit, '10:00')

    if g.portfolio_value_proportion[2] > 0:
        run_daily(sifang_rebalance, "09:50")

    # 框架默认调度
    run_daily(_daily_open_reset, "09:00")
    run_daily(print_summary, "15:06")
    run_daily(end_trade, "14:59")

    # 资金再平衡调度（09:25，在子策略日常调仓前执行）
    if ENABLE_CAPITAL_REBALANCE and CAPITAL_REBALANCE_MIN_INTERVAL > 0:
        run_daily(capital_rebalance, '09:25')
        log.info("资金再平衡已启用：最小间隔%d交易日，相对偏移阈值%.0f%%" % (
            CAPITAL_REBALANCE_MIN_INTERVAL, CAPITAL_REBALANCE_DEVIATION * 100))

    log.info("七星+红利低波成长+四方轮动 三策略组合启动！版本: %s 比例: %s" % (FRAMEWORK_VERSION, PORTFOLIO_PROPORTION))
