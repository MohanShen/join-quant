# Clone from JoinQuant
# postId: 65fb64dd095d477f7e8b4e92d3689a8a
# backtestId: 3bf96d40e1c7626a14d1ba2fef648f99
# title: 稳健策略||年化62%低回撤 牛市进攻熊市保命

# 五策略合围题材热点

import pandas as pd
import numpy as np
import datetime as dt
from datetime import datetime, timedelta
from jqdata import *
from jqlib.technical_analysis import *

import math
from io import StringIO
from six import BytesIO

# ==============================================================================
# 全局参数设置
# ==============================================================================
# 资金分配比例 (A策略:B策略:ETF反弹:ETF轮动:C策略)
STRATEGY_A_WEIGHT = 0.2
STRATEGY_B_WEIGHT = 0.2
STRATEGY_ETF2_WEIGHT = 0.1
STRATEGY_ETF3_WEIGHT = 0.2
STRATEGY_SAN_YANG_WEIGHT = 0.3

# ==============================================================================
# 概念成分快照日期（修复2b：规避概念成分未来函数）
# 概念成分文件(cpt_ind.csv / cpt_ind_stocks.csv)是单一时点静态快照。
# 请填成该文件实际生成/导出的日期；早于该日期的回测将回退到"当日历史行业分类"，
# 以避免在早期回测里用到"未来才归属的概念成分"。
# ==============================================================================
CONCEPT_SNAPSHOT_DATE = dt.datetime.strptime('2024-09-28', '%Y-%m-%d').date()
# --- MODIFICATION START ---
# 全局风控参数
CHECK_RISK = False  #风控开关
GLOBAL_DRAWDOWN_THRESHOLD = 0.07  # 触发风控的最大回撤 (7%)
GLOBAL_RECOVERY_THRESHOLD = 0.05  # 解除风控的回撤水平 (5%)
RISK_ON_CAPITAL_RATIO = 0.3      # 风控状态下，每个策略的可用资金比例 (30%)
RISK_ON_STOCK_NUM_RATIO = 0.5     # 风控状态下，每个策略的持股数量比例 (50%)
# --- MODIFICATION END ---


# ==============================================================================
# 策略基类：统一管理下单和虚拟账户
# ==============================================================================
class BaseStrategy:
    def __init__(self, name, weight):
        self.name = name
        self.weight = weight
        self.context = None
        
        # 策略独立资产
        self.cash = 0.0
        self.positions = {} # 格式: {code: amount}
        
        # --- MODIFICATION START ---
        # 风控相关属性
        self.in_risk_control = False
        self.original_stock_num = None
        self.risk_on_start_date = None
        # --- MODIFICATION END ---

    def initialize(self, context):
        """初始化策略，设置上下文并分配初始资金"""
        self.context = context
        # 使用策略自身权重计算初始资金
        self.cash = context.portfolio.available_cash * self.weight
        log.info(f"[{self.name}] 初始化完成，初始资金: {self.cash:.2f}")

    def order_target_value_(self, security, value):
        """
        执行下单并更新策略的虚拟资产。
        功能增强：
        1. 下单前检查标的是否停牌，提前拦截无效订单
        2. 卖出订单失败时，同步实际账户持仓到虚拟账户
        """
        current_data = get_current_data()
        # 提前检查：标的停牌直接返回失败，避免无效下单
        if current_data[security].paused:
            log.warning(f"[{self.name}] 证券 {security} 处于停牌状态，取消下单")
            return None

        price = current_data[security].last_price

        if value == 0:
            # 卖出逻辑
            if security in self.positions:
                # 1. 执行实际卖出订单（聚宽底层接口）
                order = order_target_value(security, 0)

                # 2. 根据订单结果处理虚拟账户
                if order is not None and str(order.status) == 'held':
                    # 订单成功：更新虚拟账户现金和持仓
                    amount_to_sell = self.positions[security]
                    sell_value = amount_to_sell * price
                    self.cash += sell_value
                    del self.positions[security]
                    log.debug(f"[{self.name}] 虚拟账户卖出 {security} {amount_to_sell}股，回收现金 {sell_value:.2f}，剩余现金 {self.cash:.2f}")
                else:
                    # 订单失败：检查实际账户持仓，同步虚拟账户
                    log.warning(f"[{self.name}] 卖出订单失败，开始同步实际持仓")
                    actual_pos = self.context.portfolio.positions.get(security)
                    if not actual_pos or actual_pos.closeable_amount <= 0:
                        # 实际无可用持仓：删除虚拟账户错误持仓
                        if security in self.positions:
                            del self.positions[security]
                        log.warning(f"[{self.name}] 实际账户无 {security} 可用持仓，已删除虚拟持仓")
                    else:
                        # 实际有持仓但下单失败（如权限问题）：保留虚拟持仓待重试
                        log.warning(f"[{self.name}] 实际账户有 {security} 持仓({actual_pos.closeable_amount}股)，但下单失败，建议检查权限")
                
                return order
            else:
                log.warning(f"[{self.name}] 尝试卖出非虚拟持仓股票 {security}")
                return None
        else:
            # 买入逻辑（保持原有逻辑，新增资金校验）
            if value > self.cash:
                log.warning(f"[{self.name}] 策略资金不足，无法买入 {security}。需要 {value:.2f}, 可用 {self.cash:.2f}")
                return None
    
            # 计算可买入股数（ETF默认100股起买，适配A股规则）
            shares_to_buy = int(value / price / 100) * 100
            if shares_to_buy <= 0:
                log.warning(f"[{self.name}] 无法买入 {security}：价格{price:.2f}元，可用资金{self.cash:.2f}元（需至少100股）")
                return None

            # 执行买入订单并更新虚拟账户
            order = order_target_value(security, value)
            #log.info(f"order.status 的值为{order.status}")
            if order is not None and str(order.status) == 'held':
                actual_cost = shares_to_buy * price
                self.cash -= actual_cost
                self.positions[security] = self.positions.get(security, 0) + shares_to_buy
        
                log.debug(f"[{self.name}] 虚拟账户买入 {security} {shares_to_buy}股，花费 {actual_cost:.2f}，剩余现金 {self.cash:.2f}")
            else:
                log.debug(f"[{self.name}] 虚拟账户买入 {security}失败")
            return order
    def open_position(self, security, value):
        """按价值开仓"""
        order = self.order_target_value_(security, value)
        return order is not None

    def close_position(self, security):
        """平仓"""
        if security in self.positions:
            log.info(f"[{self.name}] 卖出[{security}]")
            return self.order_target_value_(security, 0)
        else:
            log.warning(f"[{self.name}] 尝试卖出非持仓股票 {security}")
            return None

    def get_strategy_cash(self):
        """获取策略可用现金"""
        return self.cash

    def get_strategy_positions(self):
        """获取策略持仓列表"""
        return list(self.positions.keys())
        
    # --- MODIFICATION START ---
    def force_reduce_risk(self):
        """
        全局风控模块调用的方法，强制策略降低风险。
        1. 立即清仓所有持仓。
        2. 标记风控状态，并记录开始日期。
        3. 保存原始的持股数量设置。
        """
        if self.in_risk_control:
            return
            
        log.warning(f"[{self.name}] 进入全局风控状态！")
        self.in_risk_control = True
        self.risk_on_start_date = self.context.current_dt.date()
        
        # 保存原始的股票数量设置
        if hasattr(self, 'stock_sum'):
            self.original_stock_num = self.stock_sum
            # 立即将持股数量减半
            self.stock_sum = max(1, int(self.stock_sum * risk_on_STOCK_NUM_RATIO))
            log.warning(f"[{self.name}] 持股数量已减半，从 {self.original_stock_num} 变为 {self.stock_sum}")

        # 立即清仓
        for stock in self.get_strategy_positions():
            self.close_position(stock)
            
    def resume_normal_risk(self):
        """
        当全局风控解除时，恢复策略的正常风险水平。
        """
        if not self.in_risk_control:
            return
            
        log.info(f"[{self.name}] 退出全局风控状态，恢复正常操作。")
        self.in_risk_control = False
        self.risk_on_start_date = None
        
        # 恢复原始的股票数量设置
        if self.original_stock_num is not None:
            self.stock_sum = self.original_stock_num
            log.info(f"[{self.name}] 持股数量已恢复为 {self.stock_sum}")
            self.original_stock_num = None
            
    def get_effective_cash(self):
        """
        获取在当前风控状态下，策略实际可用于投资的资金。
        """
        if self.in_risk_control:
            # 检查是否已满足一周的清仓期
            if self.risk_on_start_date is None or (self.context.current_dt.date() - self.risk_on_start_date).days >= 7:
                # 清仓期满，允许使用部分资金
                effective_cash = self.cash * RISK_ON_CAPITAL_RATIO
                log.debug(f"[{self.name}] 风控状态，清仓期满，可用资金: {effective_cash:.2f} (总资金: {self.cash:.2f})")
                return effective_cash
            else:
                # 清仓期内，不允许使用任何资金
                log.debug(f"[{self.name}] 风控状态，清仓期内，禁止买入。")
                return 0.0
        else:
            # 正常状态，使用全部资金
            return self.cash
    # --- MODIFICATION END ---


# ==============================================================================
# 策略A: 基于概念热点和小市值的选股策略
# ==============================================================================
class StrategyA(BaseStrategy):
    def __init__(self, name, weight):
        super().__init__(name, weight)
        self.init_globals()

    def init_globals(self):
        # ... (StrategyA 的 init_globals 内容不变)
        self.isbull = False
        self.MA = ['399008.XSHE', 10]
        self.threshold = 0.003
        self.turnover = [True,0,10]
        self.exdowm = True
        self.trading_signal = True
        self.run_stoploss = False
        self.filter_audit = True
        self.filter_bons = False
        self.adjust_num = False
        self.hold_list = []
        self.yesterday_HL_list = []
        self.target_list = []
        self.pass_months = [1,4]
        self.pass_half = False
        self.limitup_stocks = []
        self.min_mv = 6
        self.max_mv = 200
        self.stock_num = 6
        self.reason_to_sell = {}
        self.stoploss_strategy = 3
        self.stoploss_limit = 0.09
        self.stoploss_market = 0.05
        self.highest = 60
        self.etf = '511880.XSHG'
        self.eend_date = 2
        self.re_date = 2
        self.today = None
        self.auc_date = None
        self.end_date = None
        self.enn_date = None
        self.watch_days = 1
        self.remove_concept_with_more_than_N_stocks = 300

    def initialize(self, context):
        super().initialize(context)
        set_option('avoid_future_data', True)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=1/10000, close_commission=1/10000, close_today_commission=0, min_commission=5),type='stock')
        log.set_level('order', 'error')
        log.set_level('system', 'error')
        log.set_level('strategy', 'debug')

    def get_bull_bear_signal_minute(self):
        nowindex = self.get_close_price(self.MA[0], 1, '1m')
        MAold = (attribute_history(self.MA[0], self.MA[1] - 1, '1d', 'close', True, fq='post')['close'].sum() + nowindex) / self.MA[1]
        if self.isbull:
            if nowindex * (1 + self.threshold) <= MAold:
                self.isbull = False
        else:
            if nowindex > MAold * (1 + self.threshold):
                self.isbull = True

    def get_close_price(self, security, n, unit='1d'):
        return attribute_history(security, n, unit, 'close', fq='post')['close'][0]

    def prepare_stock_list(self):
        if STRATEGY_A_WEIGHT == 0:
            return 
        self.hold_list = list(self.positions.keys())
        self.limitup_stocks = []
        if self.hold_list:
            df = get_price(self.hold_list, end_date=self.context.previous_date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False)
            df = df[df['close'] == df['high_limit']]
            self.yesterday_HL_list = list(df.code)
        else:
            self.yesterday_HL_list = []
        self.trading_signal = self.today_is_between()

    def get_stock_list(self):
        if STRATEGY_A_WEIGHT == 0:
            return 
        final_list = []
        self.get_bull_bear_signal_minute()
        if self.isbull:
            log.info(f'[{self.name}] 当前为牛市')
            MKT_index = self.get_stocks_list2()
            log.info(f'[{self.name}] 最热概念小市值, 数量: {len(MKT_index)}')
            initial_list = self.filter_stocks(MKT_index)
        else:
            log.info(f'[{self.name}] 当前为熊市')
            MKT_index = '399101.XSHE'
            initial_list = self.filter_stocks(get_index_stocks(MKT_index))

        q = query(
            valuation.code,
            valuation.market_cap,
        ).filter(
            valuation.code.in_(initial_list),
            valuation.market_cap.between(self.min_mv, self.max_mv),
        ).order_by(valuation.market_cap.asc()).limit(self.stock_num*3)

        df = get_fundamentals(q)
        if self.filter_audit:
            df['audit'] = df['code'].apply(lambda x: self.filter_audit_func(x))
            df = df[df['audit'] == True]

        final_list = list(df.code)

        if len(final_list) == 0:
            log.info(f'[{self.name}] 无适合股票，买入ETF')
            return [self.etf]
        else:
            last_prices = history(1, unit='1d', field='close', security_list=final_list)
            return [stock for stock in final_list if stock in self.hold_list or last_prices[stock][-1] <= self.highest]

    def weekly_adjustment(self):
        context = self.context
        if self.trading_signal and STRATEGY_A_WEIGHT > 0:
            if self.adjust_num:
                new_num = self.adjust_stock_num()
            else:
                new_num = self.stock_num
            if new_num == 0:
                self.buy_security([self.etf], 1)
                log.info(f'[{self.name}] MA指示指数大跌，持有银华日利ETF')
            else:
                if self.stock_num != new_num:
                    self.stock_num = new_num
                    log.info(f'[{self.name}] 持仓数量修改为{new_num}')
                self.target_list = self.get_stock_list()[:self.stock_num]
                log.info(f'[{self.name}] 待买入股票: {str(self.target_list)}')

                sell_list = [stock for stock in self.hold_list if stock not in self.target_list and stock not in self.yesterday_HL_list]
                log.info(f'[{self.name}] 卖出: {str(sell_list)}')
                for stock in sell_list:
                    self.close_position(stock)

                buy_list = [stock for stock in self.target_list if stock not in self.hold_list]
                self.buy_security(buy_list, len(buy_list))
        else:
            non_etf_holdings = [stock for stock in self.hold_list if stock != self.etf]
            if non_etf_holdings:
                for stock in non_etf_holdings:
                    self.close_position(stock)
            if self.etf not in self.hold_list:
                self.buy_security([self.etf], 1)
            log.info(f'[{self.name}] 该月份为空仓月份，持有银华日利ETF')

    def check_limit_up(self):
        context = self.context
        now_time = context.current_dt
        if self.yesterday_HL_list:
            for stock in self.yesterday_HL_list:
                current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
                if current_data.iloc[0,0] < current_data.iloc[0,1]:
                    log.info(f'[{self.name}] [{stock}]涨停打开，卖出')
                    self.close_position(stock)
                    self.reason_to_sell[stock] = 'limitup'
                    self.limitup_stocks.append(stock)
                else:
                    log.info(f'[{self.name}] [{stock}]涨停，继续持有')

    def check_remain_amount(self):
        context = self.context
        stoploss_list = [k for k, v in self.reason_to_sell.items() if v == 'stoploss']
        uplimit_list = [k for k, v in self.reason_to_sell.items() if v == 'limitup']
        self.hold_list = self.get_strategy_positions()

        # --- MODIFICATION START ---
        # 使用考虑风控的有效资金
        effective_cash = self.get_effective_cash()
        if len(self.hold_list) < self.stock_num and effective_cash > 0:
        # --- MODIFICATION END ---
            num_stocks_to_buy = min(len(uplimit_list), self.stock_num - len(self.hold_list))
            target_list = [stock for stock in self.target_list if stock not in self.limitup_stocks][:num_stocks_to_buy]
            log.info(f'[{self.name}] 有余额可用{round(effective_cash,2)}元。买入{str(target_list)}')
            self.buy_security(target_list, len(target_list))
            if len(stoploss_list) != 0:
                log.info(f'[{self.name}] 有余额可用{round(effective_cash,2)}元。买入货币基金{str(self.etf)}')
                self.buy_security([self.etf], len(stoploss_list))

        self.reason_to_sell = {}

    def trade_afternoon(self):
        if self.trading_signal:
            self.check_limit_up()
            self.check_remain_amount()

    def sell_stocks(self):
        if self.run_stoploss:
            current_positions = self.get_strategy_positions()
            if self.stoploss_strategy == 1 or self.stoploss_strategy == 3:
                for stock in current_positions:
                    pos = self.context.portfolio.positions[stock]
                    price = pos.price
                    avg_cost = pos.avg_cost
                    if price >= avg_cost * 2:
                        self.close_position(stock)
                        log.info(f'[{self.name}] 收益100%止盈,卖出{stock}')
                    elif price < avg_cost * (1 - self.stoploss_limit):
                        self.close_position(stock)
                        log.info(f'[{self.name}] 收益止损,卖出{stock}')
                        self.reason_to_sell[stock] = 'stoploss'
            if self.stoploss_strategy == 2 or self.stoploss_strategy == 3:
                stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=self.context.previous_date, frequency='daily', fields=['close', 'open'], count=1, panel=False)
                down_ratio = (1 - stock_df['close'] / stock_df['open']).mean()
                if down_ratio >= self.stoploss_market:
                    log.debug(f'[{self.name}] 大盘惨跌,平均降幅{down_ratio:.2%}')
                    for stock in current_positions:
                        self.close_position(stock)
                        self.reason_to_sell[stock] = 'stoploss'

    def adjust_stock_num(self):
        ma_para = 10
        today = self.context.previous_date
        start_date = today - datetime.timedelta(days = ma_para*2)
        index_df = get_price('399101.XSHE', start_date=start_date, end_date=today, frequency='daily')
        index_df['ma'] = index_df['close'].rolling(window=ma_para).mean()
        last_row = index_df.iloc[-1]
        diff = last_row['close'] - last_row['ma']
        result = 3 if diff >= 500 else \
                 3 if 200 <= diff < 500 else \
                 4 if -200 <= diff < 200 else \
                 5 if -500 <= diff < -200 else \
                 6
        return result

    def filter_stocks(self, stock_list):
        current_data = get_current_data()
        last_prices = history(1, unit='1m', field='close', security_list=stock_list)
        filtered_stocks = []
        for stock in stock_list:
            if current_data[stock].paused:
                continue
            if current_data[stock].is_st:
                continue
            if '退' in current_data[stock].name:
                continue
            if stock.startswith('68') or stock.startswith('8') or stock.startswith('4') or stock.startswith('3'):
                continue
            if not (stock in self.get_strategy_positions() or last_prices[stock][-1] < current_data[stock].high_limit):
                continue
            if not (stock in self.get_strategy_positions() or last_prices[stock][-1] > current_data[stock].low_limit):
                continue
            start_date = get_security_info(stock).start_date
            if self.context.previous_date - start_date < timedelta(days=200):
                continue
            filtered_stocks.append(stock)
        return filtered_stocks

    def filter_audit_func(self, code):
        lstd = self.context.previous_date
        last_year = (lstd.replace(year=lstd.year - 3, month=1, day=1)).strftime('%Y-%m-%d')
        q=query(finance.STK_AUDIT_OPINION).filter(finance.STK_AUDIT_OPINION.code==code,finance.STK_AUDIT_OPINION.pub_date>=last_year)
        df=finance.run_query(q)
        df['report_type'] = df['report_type'].astype(str)
        contains_nums = df['report_type'].str.contains(r'2|3|4|5')
        return not contains_nums.any()

    def buy_security(self, target_list, num):
        if num == 0 or not target_list:
            return
        # --- MODIFICATION START ---
        # 使用考虑风控的有效资金
        strategy_cash = self.get_effective_cash()
        # --- MODIFICATION END ---
        if strategy_cash <= 0:
            log.info(f'[{self.name}] 策略资金不足或处于风控期，无法买入。')
            return
            
        value = strategy_cash / num
        value = min(value, strategy_cash)
        
        for stock in target_list:
            self.open_position(stock, value)
            log.info(f'[{self.name}] 买入[{stock}]（{value}元）')
            strategy_cash -= value
            if strategy_cash <= 0:
                break

    def today_is_between(self):
        if self.pass_half:
            current_date = self.context.current_dt
            month = current_date.month
            day = current_date.day
            if (month == 12 and day >= 15) or (month == 1 and day <= 15):
                return False
            elif (month == 3 and day >= 15) or (month == 4 and day <= 15):
                return False
            else:
                return True
        else:
            month = self.context.current_dt.month
            if month in self.pass_months :
                return False
            else:
                return True

    def close_account(self):
        if self.trading_signal == False:
            for stock in self.get_strategy_positions():
                if stock != self.etf:
                    self.close_position(stock)
                    log.info(f'[{self.name}] 卖出[{stock}]')

    def low_stock(self, stock_list):
        zt_count = {stock: 0 for stock in stock_list}
        for stock in stock_list:
            df = get_price(stock, end_date=self.context.previous_date, count=20, frequency='daily',
                           fields=['pre_close', 'low'], fq='post', panel=False)
            for index, row in df.iterrows():
                if row['low'] == row['pre_close'] * 0.9:
                    zt_count[stock] += 1
        L_list = [stock for stock, count in zt_count.items() if count == 0]
        return L_list

    def get_stocks_list2(self):
        if STRATEGY_A_WEIGHT == 0:
            return 
        log.info(f'[{self.name}] ========================================================= 获取最有辨识度的股票')
        self.today = self.context.current_dt.date().strftime('%Y-%m-%d')
        log.info(f'[{self.name}] {self.today}')
        yesterday = self.context.previous_date
        self.auc_date = get_trade_days(count=10,end_date=yesterday)[-1].strftime('%Y-%m-%d')
        self.end_date = get_trade_days(count=10,end_date=yesterday)[-2].strftime('%Y-%m-%d')
        self.enn_date = get_trade_days(count=10,end_date=yesterday)[-3].strftime('%Y-%m-%d')
        self.end_date = dt.datetime.strptime(self.end_date, '%Y-%m-%d').strftime('%Y-%m-%d')
        self.auc_date = dt.datetime.strptime(self.auc_date, '%Y-%m-%d').strftime('%Y-%m-%d')
        self.enn_date = dt.datetime.strptime(self.enn_date, '%Y-%m-%d').strftime('%Y-%m-%d')

        category = self.Category(as_of_date=self.context.previous_date)
        category.concept_category['name'] = category.concept_category['code'].apply(self.get_stock_name)

        # 修复2b：概念文件是单一时点静态快照。早于快照日的回测会用到"未来成分"，
        # 因此回退到"当日历史行业分类"（get_industry 已按日期取数，无时点偏差）
        if self.context.previous_date < CONCEPT_SNAPSHOT_DATE:
            log.warning(f'[{self.name}] 回测日早于概念快照日({CONCEPT_SNAPSHOT_DATE})，改用历史行业分类，规避概念成分未来函数')
            category.concept_category = category.industry_category.copy()
            # 修复：行业分类只有 code/category 两列，回退后补充 name 列，避免下方 KeyError: 'name'
            category.concept_category['name'] = category.concept_category['code'].apply(self.get_stock_name)
        category.concept_category = category.concept_category[category.concept_category['name'] != 'Unknown']
        category.concept_category.reset_index(drop=True, inplace=True)

        categories_to_drop = [
            '标普道琼斯中国','富时罗素','MSCI','CIPS概念','ST','st', 
            '融资融券','融券','融资' 
            '注册制次新股','新股与次新股',
            '可转债',
            '沪股通','深股通',
            '昨日涨停','昨日连板','昨日首板','昨日触板',
            '科创企业同股同权',
            '北京冬奥会', '房价上涨',     
        ]
        category.concept_category = category.concept_category[~category.concept_category['category'].isin(categories_to_drop)]
        pattern = '|'.join([f'.*{word}.*' for word in categories_to_drop])
        category.concept_category = category.concept_category[~category.concept_category['category'].str.contains(pattern, na=False)]
        df_stock_score = self.stocks_score(category)
        
        df_category_score = category.category_score_and_pct_attacking(df_score=df_stock_score, df_category=category.concept_category, count=self.watch_days, daily_top_filter=5)  

        if len(df_category_score) < 5:
            log.warning(f'[{self.name}] 有效概念不足5个，无法进行交集计算。')
            return []

        stocks_in_hot_concept1 = category.find_stocks_by_category(df_category_score['category'].iloc[0], fuzzy_match=True)
        stocks_in_hot_concept2 = category.find_stocks_by_category(df_category_score['category'].iloc[1], fuzzy_match=True)
        stocks_in_hot_concept3 = category.find_stocks_by_category(df_category_score['category'].iloc[2], fuzzy_match=True)
        
        hot_stocks_intersection1 = list(set(stocks_in_hot_concept1).intersection(set(stocks_in_hot_concept2)))
        hot_stocks_intersection2 = list(set(stocks_in_hot_concept1).intersection(set(stocks_in_hot_concept3)))
        hot_stocks_intersection3 = list(set(stocks_in_hot_concept2).intersection(set(stocks_in_hot_concept3)))
        stocks_in_hot_concept = hot_stocks_intersection1 + hot_stocks_intersection2 + hot_stocks_intersection3
        stocks_in_hot_concept = list(set(stocks_in_hot_concept))
        
        if self.exdowm and stocks_in_hot_concept:
            stocks_in_hot_concept = self.low_stock(stocks_in_hot_concept)
            
        if hasattr(self, 'turnover') and self.turnover[0] and stocks_in_hot_concept:
            try:
                turnover_ratios = get_valuation(stocks_in_hot_concept, fields=['turnover_ratio'], end_date=self.end_date, count=1)
                if turnover_ratios is not None and not turnover_ratios.empty:
                    min_turnover_ratio = 3.0
                    stocks_in_hot_concept = turnover_ratios[
                        turnover_ratios['turnover_ratio'] >= min_turnover_ratio
                    ]['code'].tolist()
                    log.info(f'[{self.name}] 换手率筛选后剩余股票数量: {len(stocks_in_hot_concept)}')
            except Exception as e:
                log.error(f'[{self.name}] 换手率筛选出错: {e}')
        
        return stocks_in_hot_concept

    def stocks_score(self, category):
        if self.eend_date == 1:
            e_date = self.auc_date
        else:
            e_date = self.end_date
        df_stock_score = category.score_by_return(return_days=1, return_filter=0.09, end_dt=e_date, count=self.watch_days, debug=True)
        return df_stock_score

    def get_stock_name(self, stock_code):
        security_info = get_security_info(stock_code)
        if security_info is not None:
            return security_info.display_name
        else:
            log.warning(f'[{self.name}] 接收到证券代码{stock_code}，get_stock_name找不到证券名字')
            return 'Unknown'

    class Category:
        def __init__(self, as_of_date=None, industries_type='sw_l3'):
            self.as_of_date = as_of_date if as_of_date is not None else dt.date.today()
            self.industries_type = industries_type
            self.industry_category = self.stock_industry(industries_type=industries_type)
            self.concept_category = self.stock_concepts_and_industry_ths_20240928()

        def stock_concepts_and_industry_ths_20240928(self, keep_concept_with_below_N_stocks=200):
            from jqfactor import get_factor_values
            concept_stocks_file = g.concept_stocks_file
            concepts_file = g.concepts_file
            try:
                concept_stocks = pd.read_csv(BytesIO(read_file(concept_stocks_file)))
                concepts = pd.read_csv(BytesIO(read_file(concepts_file)))
            except Exception as e:
                log.error(f"读取同花顺概念失败: {e}")
                return pd.DataFrame(columns=['code', 'category'])
            
            merged_df = concept_stocks.merge(concepts[['Unnamed: 0', 'name', 'type']], 
                                            left_on='index', right_on='Unnamed: 0', how='left')
            merged_df['name'].fillna('未知概念/行业', inplace=True)
            merged_df['stock'] = merged_df['stock'].str.replace('.SZ', '.XSHE', regex=False)
            merged_df['stock'] = merged_df['stock'].str.replace('.SH', '.XSHG', regex=False)
            merged_df = merged_df[~merged_df['stock'].str.startswith(('8', '4', '68', '9','3'))]
            final_df = merged_df[['stock', 'name']]
            final_df.columns = ['code', 'category']
            return final_df

        def stock_concepts_ths_20240831(self, keep_concept_with_below_N_stocks=200):
            print ('采用同花顺股票概念库')
            concept_stocks_file = 'concept_stocks_20241209.csv'
            concepts_file = 'concepts_20241209.csv'
            concept_stocks = pd.read_csv(StringIO(concept_stocks_file))
            concepts = pd.read_csv(StringIO(concepts_file))
            merged_df = concept_stocks.merge(concepts[['concept_thscode', 'concept_name']], 
                                            left_on='concept', right_on='concept_thscode', how='left')
            merged_df['concept_name'].fillna('未知概念', inplace=True)
            merged_df['stock'] = merged_df['stock'].str.replace('.SZ', '.XSHE', regex=False)
            merged_df['stock'] = merged_df['stock'].str.replace('.SH', '.XSHG', regex=False)
            df = merged_df[['stock', 'concept_name']]
            df.columns = ['code', 'category']
            df.head(10)
            return df
        
        def stock_concepts_jq(self, keep_concept_with_below_N_stocks = 200):
            print ('采用聚宽股票概念库')
            q = query(jy.LC_ConceptList.ConceptCode, jy.LC_ConceptList.ConceptName)
            dict_concept = jy.run_query(q).set_index('ConceptCode')['ConceptName'].to_dict()
            stocks = jy.run_query(query(jy.SecuMain.InnerCode, jy.SecuMain.SecuCode).filter(jy.SecuMain.SecuCategory == 1,
                                                                                            jy.SecuMain.SecuMarket.in_(
                                                                                                [83, 90]),
                                                                                            jy.SecuMain.ListedState.in_(
                                                                                                [1])))
            s_code = stocks.set_index("InnerCode")['SecuCode']
            dfs = []
            min_id = 9953668143482
            while len(dfs) < 30 and min_id > 0:
                q = query(
                    jy.LC_COConcept
                ).filter(jy.LC_COConcept.IndiState == 1, jy.LC_COConcept.ID < min_id).order_by(jy.LC_COConcept.ID.desc())
                df = jy.run_query(q)
                min_id = df.ID.min()
                if len(df) > 0:
                    dfs.append(df)
                else:
                    break
            df = pd.concat(dfs, ignore_index=True)
            sc = df.groupby('InnerCode').apply(
                lambda dx: ",".join([dict_concept[code] for code in dx.ConceptCode.unique()]))
            df_concept = pd.DataFrame({"concept": sc, 'code': s_code})
            df_concept['symbol'] = df_concept.code.map(normalize_code, na_action='ignore')
            s_concept = df_concept.dropna().set_index('symbol')['concept']
            df = pd.DataFrame(s_concept.str.split(',').tolist(), index=s_concept.index).stack()
            df = df.reset_index([0, 'symbol'])
            df.columns = ['code', 'category']
            return df

        def remove_category_with_stocks_more_than_N(self, N=300):
            category_counts = self.concept_category.groupby('category')['code'].nunique()
            valid_categories = category_counts[category_counts <= N].index
            self.concept_category = self.concept_category[self.concept_category['category'].isin(valid_categories)]

        def stock_industry(self, stocks_list=None, industries_type="sw_l3"):
            if stocks_list is None:
                stocks_list = list(get_all_securities(types=['stock'], date=self.as_of_date).index)
            # get_industry 按回测日期返回当日真实行业归属，消除行业成分的未来时点偏差
            stocks_industry_dict = get_industry(stocks_list, date=self.as_of_date)
            stocks_industry_df = pd.DataFrame(stocks_industry_dict).T[[industries_type]]
            stocks_industry_df[industries_type] = stocks_industry_df[industries_type].dropna().apply(
                lambda x: x['industry_name'])
            df_category = stocks_industry_df[[industries_type]].dropna().reset_index()
            df_category.columns = ['code', 'category']
            return df_category
        
        def score_by_return(self, stock_list=None, return_days=1, return_filter=0.099,
                                end_dt=dt.datetime.now(), count=60, debug=False):
            if stock_list is None:
                stock_list = list(get_all_securities(types=['stock'], date=end_dt).index)   # 按回测日期取当日真实上市股，消除幸存者偏差
            stock_list = [stock for stock in stock_list if stock[0] != '4' and stock[0] != '8' and stock[0] != '9' and stock[:2] != '68']
            close = get_price(stock_list, end_date=end_dt, count=count + return_days, fields=['close'], panel=False, fq='post')
            close = close.pivot(index='time', columns='code', values='close')
            df_return = (close / close.shift(return_days) - 1).iloc[return_days:]
            df_filter = (df_return > return_filter).astype(int)
            df_filter.index = df_return.index.strftime('%Y-%m-%d')
            return df_filter.T

        def score_by_attack(self, stock_list=None, return_days=1, return_filter=0.099,
                            end_dt=dt.datetime.now(), count=60, debug=False):
            if stock_list is None:
                stock_list = list(get_all_securities(types=['stock'], date=end_dt).index)
            stock_list = [stock for stock in stock_list if stock[0] != '4' and stock[0] != '8' and stock[0] != '3' and stock[0] != '9' and stock[:2] != '68']
            prices = get_price(stock_list, end_date=end_dt, count=count + return_days, fields=['pre_close', 'high'], panel=False, fq='post')
            if debug:
                print(f'get_price获取{end_dt}的行情数据：')
                print(prices.head())
            prices['attack'] = (prices['high'] > (1 + return_filter) * prices['pre_close']).astype(int)
            prices['time'] = prices['time'].dt.strftime('%Y-%m-%d')
            df_attack = prices.pivot(index='code', columns='time', values='attack')
            return df_attack
            
        def score_by_return_at_dt(self, stock_list=None, return_days=1, return_filter=0.099,
                                  end_dt=dt.datetime.now(), count=6, debug=False):
            if stock_list is None:
                stock_list = list(get_all_securities(types=['stock'], date=end_dt).index)
            stock_list = [stock for stock in stock_list if stock[0] != '4' and stock[0] != '8' and stock[0] != '9' and stock[0] != '3' and stock[:2] != '68']
            if isinstance(end_dt, str):
                try:
                    end_dt = dt.datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    end_dt = dt.datetime.strptime(end_dt, '%Y-%m-%d')
                    end_dt = end_dt.replace(hour=23, minute=59, second=59)
            dfb = get_bars(stock_list, count=count + return_days, unit='1d', fields=['date', 'close'],
                           include_now=True, end_dt=end_dt, fq_ref_date=end_dt.date(), df=True)
            df_flattened = dfb.reset_index()
            df_flattened.rename(columns={'level_0': 'stock_code'}, inplace=True)
            df_flattened.drop(columns=['level_1'], inplace=True)
            recent_dates = df_flattened['date'].sort_values().unique()[-count:]
            df_flattened = df_flattened[df_flattened['date'].isin(recent_dates)]
            if debug: 
                print(f'get_bar获取{end_dt}的行情数据：')
                print(df_flattened.head(10))
            df_flattened['pct_change'] = df_flattened.groupby('stock_code')['close'].pct_change(return_days)
            df_return = df_flattened.pivot(index='stock_code', columns='date', values='pct_change').iloc[return_days:]
            df_return.columns = pd.to_datetime(df_return.columns).strftime('%Y-%m-%d')
            df_filter = (df_return > return_filter).astype(int)
            return df_filter

        def score_by_bias(self, stock_list=None, ma_len=20, end_date=dt.datetime.now(), count=510):
            if stock_list is None:
                stock_list = list(get_all_securities(types=['stock'], date=end_date).index)
            stock_list = [stock for stock in stock_list if stock[0] != '4' and stock[0] != '8' and stock[0] != '9' and stock[0] != '3' and stock[:2] != '68']
            close = get_price(stock_list, end_date=end_date, count=count + ma_len + 1, fields=['close'], fq='post')['close']
            ma = close.rolling(ma_len).mean()
            return (close > ma).astype(int).iloc[-count:].T

        def category_score_and_pct_attacking(self, df_score, df_category=None, count=60, daily_top_filter=30, top_N=10):
            if df_category is None or df_category.empty:
                return pd.DataFrame()
            code_category_dict = df_category.groupby('code').apply(lambda dx: list(dx['category'].unique())).to_dict()
            dats = df_score.columns
            dat_cat_dict = {}
            for i in range(0, len(dats)):
                codes = list(df_score[df_score[dats[i]] > 0].index)
                s_score = df_score[dats[i]]
                category_count_dict = {}
                for code in codes:
                    if code in code_category_dict:
                        categories = code_category_dict[code]
                        for category in categories:
                            if category not in category_count_dict:
                                category_count_dict[category] = float(s_score[code])
                            else:
                                category_count_dict[category] += float(s_score[code])
                dat_cat_dict[dats[i]] = category_count_dict
            df_category_score = pd.DataFrame.from_dict(dat_cat_dict, orient='index').fillna(0).tail(count).T
            stock_count_dict = df_category.groupby('category')['code'].nunique().to_dict()
            all_results = []
            total_days = len(df_category_score.columns)
            for index, date in enumerate(df_category_score.columns):
                pct_of_attack_dict = {}
                for category in df_category_score.index:
                    score = df_category_score.at[category, date]
                    stock_count = stock_count_dict.get(category, 1)
                    pct_of_attack = 100 * score / stock_count if stock_count > 0 else 0
                    pct_of_attack_dict[category] = round(pct_of_attack, 2)
                df_daily = pd.DataFrame({
                    'category': df_category_score.index,
                    'date': date,
                    'score': df_category_score[date].values,
                    'stock_count': [stock_count_dict.get(category, 0) for category in df_category_score.index],
                    'pct_of_attack': [pct_of_attack_dict.get(category, 0) for category in df_category_score.index]
                })
                df_daily = df_daily.sort_values(by='score', ascending=False).head(daily_top_filter)
                all_results.append(df_daily)
            df_attack = pd.concat(all_results, ignore_index=True)
            return df_attack

        def find_stocks_by_category(self, category_value, fuzzy_match=True):
            category_df = self.concept_category
            if category_df is None or category_df.empty:
                raise ValueError("概念数据未正确加载，请检查 self.concept_category")
            if fuzzy_match:
                filtered_df = category_df[category_df['category'].str.contains(category_value, case=False, na=False)]
            else:
                filtered_df = category_df[category_df['category'] == category_value]
            if filtered_df.empty:
                print(f"未找到概念 '{category_value}' 的成分股，可能是概念名称不正确或不在数据中。")
                return []
            return filtered_df['code'].unique().tolist()

        def lead_stocks_in_category(self, category_value, end_date=dt.datetime.now(), watch_days=60, top_N=10, fuzzy_match=True, draw_chart=True):
            if not fuzzy_match:
                concept_stocks = self.concept_category[self.concept_category['category'] == category_value]['code'].unique()
            else:
                concept_stocks = self.concept_category[self.concept_category['category'].str.contains(category_value)]['code'].unique()
            concept_stocks = [
                code if code.endswith('.XSHG') or code.endswith('.XSHE') 
                else (code + '.XSHG' if code.startswith('6') else code + '.XSHE')
                for code in concept_stocks
            ]
            if len(concept_stocks) == 0:
                print(f"没有找到属于 {category_value} 的股票（模糊搜索：{fuzzy_match}）")
                return []
            try:
                close_prices = get_price(concept_stocks, end_date=end_date, count=watch_days + 1, fields=['close'], panel=True)['close']
            except Exception as e:
                print(f"获取价格数据时发生错误: {e}")
                return []
            if close_prices.empty:
                print("警告：没有获取到有效的价格数据，请检查输入参数！")
                return []
            close_prices = close_prices.fillna(method='ffill').fillna(0)
            df_return = (close_prices / close_prices.shift(1) - 1).iloc[1:]
            df_attack = (df_return > 0.09).astype(int)
            valid_stocks = df_return.columns[df_return.notna().any()].tolist()
            df_return = df_return[valid_stocks]
            df_attack = df_attack[valid_stocks]
            if df_return.empty:
                print("警告：所有股票都没有有效的涨幅数据，请检查是否是刚上市的股票。")
                return []
            attack_counts = df_attack.sum(axis=0).sort_values(ascending=False).head(top_N)
            lead_stocks_by_attack = attack_counts.index
            stock_cumulative_returns = {}
            for stock in lead_stocks_by_attack:
                stock_cumulative_return = close_prices[stock].pct_change().cumsum().iloc[-watch_days:]
                stock_cumulative_returns[stock] = stock_cumulative_return.iloc[-1]
            sorted_stocks_by_return = sorted(stock_cumulative_returns.items(), key=lambda x: x[1], reverse=True)
            if draw_chart: 
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(12, 6))
                lines = []
                labels_by_return = []
                for stock, _ in sorted_stocks_by_return:
                    stock_name = get_stock_name(stock)
                    stock_return = close_prices[stock].pct_change().cumsum().iloc[-watch_days:]
                    line, = ax.plot(stock_return.index, stock_return.values, label=f'{stock} ({stock_name})')
                    lines.append(line)
                    labels_by_return.append(f'{stock} ({stock_name})')
                ax.legend(lines, labels_by_return, title='按累计收益排序', loc='upper left', bbox_to_anchor=(1.05, 1))
                ax.set_title(f'概念板块 {category_value} 中累计收益最多的{top_N}只股票')
                ax.set_xlabel('Date')
                ax.set_ylabel('累计收益')
                ax.grid(True)
                plt.tight_layout()
                try:
                    plt.show()
                except Exception as e:
                    print(f"绘制图表时发生错误: {e}")
            return list(lead_stocks_by_attack)


# ==============================================================================
# 策略B: 中小板弱转强策略
# ==============================================================================
class StrategyB(BaseStrategy):
    def __init__(self, name, weight):
        super().__init__(name, weight)
        self.init_globals()

    def init_globals(self):
        self.stock_num = 6
        self.down = 0.4
        self.avoid_jan_apr_dec = True
        self.ma_period = 10
        self.volume_ratio_threshold = 10
        self.stop_loss_ma_period = 7
        self.min_operating_revenue = 1e8
        self.min_net_profit = 0
        self.min_roe = 0
        self.min_roa = 0
        self.open_down_threshold = 0.95
        self.open_up_threshold = 1.01
        self.today_list = []
        self.buy_dates = {}
        self.dieting_stocks = []
        self.dieting = []
        self.yesterday_high_dict = {}

    def initialize(self, context):
        super().initialize(context)

    def prepare(self):
        if STRATEGY_B_WEIGHT == 0:
            return 
        context = self.context
        if self.avoid_jan_apr_dec and self.is_avoid_period():
            log.info(f'[{self.name}] 当前处于1、4、12月空仓期，今日不交易')
            self.today_list = []
            return
            
        self.dieting = []
        current_data = get_current_data()
        self.yesterday_high_dict = {}
        self.today_list = []
        stk_list = self.get_st()
        
        initial_constituents = len(stk_list)
        
        stk_list = self.rzq_list(stk_list)
        if len(stk_list) == 0:
            return
        
        stk_list = self.GJT_filter_stocks(stk_list)
        if len(stk_list) == 0:
            return
        
        stk_list = self.filter_stocks(stk_list)
        if len(stk_list) == 0:
            return
        
        df = get_price(
            stk_list,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close'],
            count=1,
            panel=False,
            fill_paused=False,
            skip_paused=True
        ).set_index('code')
        
        open_now_values = []
        for s in stk_list:
            try:
                open_now_values.append(current_data[s].day_open)
            except KeyError as e:
                log.info(f'[{self.name}] 警告: 股票 {s} 的数据不可用, 错误: {e}')
                open_now_values.append(None)
        
        df['open_now'] = open_now_values
        df = df.dropna(subset=['open_now'])
        df = df[(df['open_now'] / df['close']) < self.open_up_threshold]
        df = df[(df['open_now'] / df['close']) > self.open_down_threshold]
        stk_list = list(df.index)
        
        hold_list = self.get_strategy_positions()
        stk_list = list(set(stk_list) - set(hold_list))
        
        if len(stk_list) == 0:
            return
        
        df_val = get_valuation(
            stk_list,
            start_date=context.previous_date,
            end_date=context.previous_date,
            fields=['turnover_ratio', 'market_cap', 'circulating_market_cap']
        )
        
        df.index = df.index.astype(str)
        df_val['code'] = df_val['code'].astype(str)
        
        df_combined = pd.merge(df.reset_index(), df_val, on='code')
        df_combined['factor'] = df_combined['turnover_ratio'] * (df_combined['open_now'] / df_combined['close'])
        df_sorted = df_combined.sort_values(by='factor', ascending=False)
        self.today_list = list(df_sorted['code'])
        
        remaining_positions = self.stock_num - len(hold_list)
        log.info(f'[{self.name}] 今日成分股数量：{initial_constituents}只，候选股票数量：{len(self.today_list)}只，可买仓位：{remaining_positions}个')
        
        if len(self.today_list) <= 10 and len(self.today_list) > 0:
            try:
                stock_names = [get_security_info(code).display_name + f"({code})" for code in self.today_list]
                log.info(f'[{self.name}] 候选股票：{", ".join(stock_names)}')
            except:
                log.info(f'[{self.name}] 候选股票：{", ".join(self.today_list)}')
        elif len(self.today_list) > 10:
            try:
                stock_names = [get_security_info(code).display_name + f"({code})" for code in self.today_list[:10]]
                log.info(f'[{self.name}] 前10只候选股票：{", ".join(stock_names)}')
            except:
                log.info(f'[{self.name}] 前10只候选股票：{", ".join(self.today_list[:10])}')

    def sell(self):
        hold_list = self.get_strategy_positions()
        if not hold_list:
            return
            
        current_data = get_current_data()
        yesterday = self.context.previous_date
        
        ma_data = history(self.stop_loss_ma_period, 
                            unit='1d', 
                            field='close', 
                            security_list=hold_list,
                            ).mean()

        df_history = get_price(
            hold_list,
            end_date=yesterday,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1,
            panel=False
        )
        
        df_history['avg_cost'] = [self.context.portfolio.positions[s].avg_cost for s in hold_list]
        df_history['price'] = [self.context.portfolio.positions[s].price for s in hold_list]
        df_history['today_high_limit'] = [current_data[s].high_limit for s in hold_list]
        df_history['today_low_limit'] = [current_data[s].low_limit for s in hold_list]
        df_history['last_price'] = [current_data[s].last_price for s in hold_list]
        df_history['ma'] = [ma_data.get(s, 0) for s in hold_list]
        df_history['closeable_amount'] = [self.context.portfolio.positions[s].closeable_amount for s in hold_list]
        
        cond1 = (df_history['last_price'] != df_history['today_high_limit'])
        cond2_1 = df_history['last_price'] < df_history['ma']
        ret_matrix = (df_history['price'] / df_history['avg_cost'] - 1) * 100
        cond2_2 = ret_matrix > 0
        cond2_3 = (df_history['close'] == df_history['high_limit'])
        sell_condition = cond1 & (cond2_1 | cond2_2 | cond2_3)
        
        sell_list = df_history[
            sell_condition & 
            (df_history['last_price'] > df_history['today_low_limit']) &
            (df_history['closeable_amount'] > 0)
        ].code.tolist()
        
        for s in sell_list:
            position = self.context.portfolio.positions[s]
            if position.closeable_amount > 0 and current_data[s].last_price > current_data[s].low_limit:
                avg_cost = position.avg_cost
                current_price = position.price
                try:
                    stock_name = get_security_info(s).display_name
                except:
                    stock_name = s
                self.close_position(s)
                log.info(f'[{self.name}] 卖出 {stock_name}({s}) | 成本价:{avg_cost:.2f} 现价:{current_price:.2f}')

    def buy(self):
        if self.avoid_jan_apr_dec and self.is_avoid_period():
            return
            
        target = self.filter_stocks_by_b_s(self.today_list)
        
        hold_list = self.get_strategy_positions()
        num = self.stock_num - len(hold_list)
        if num == 0:
            return
        target = [x for x in target if x not in hold_list][:num]
        if len(target) > 0:
            # --- MODIFICATION START ---
            # 使用考虑风控的有效资金
            strategy_cash = self.get_effective_cash()
            # --- MODIFICATION END ---
            if strategy_cash <= 0:
                log.info(f'[{self.name}] 策略资金不足或处于风控期，无法买入。')
                return
                
            cash_per_stock = strategy_cash / num
            current_data = get_current_data()
            for stock in target:
                if current_data[stock].paused or \
                current_data[stock].last_price == current_data[stock].low_limit or \
                current_data[stock].last_price == current_data[stock].high_limit:
                    continue
                try:
                    stock_name = get_security_info(stock).display_name
                except:
                    stock_name = stock
                price = current_data[stock].last_price
                if price <= 0:
                    continue
                shares = int(cash_per_stock / price / 100) * 100
                if shares <= 0:
                    continue
                    
                order_value(stock, shares * price)
                log.info (f'[{self.name}] 买入 {stock_name}({stock})')
                self.buy_dates[stock] = self.context.current_dt.date()
                
                self.cash -= shares * price
                self.positions[stock] = self.positions.get(stock, 0) + shares
                log.debug(f'[{self.name}] 虚拟账户买入 {stock} {shares}股，花费 {shares * price:.2f}，剩余现金 {self.cash:.2f}')

    def is_avoid_period(self):
        today_str = self.context.current_dt.strftime('%m-%d')
        avoid_periods = [
            ('01-15', '01-31'),
            ('04-15', '04-30'),
            ('12-15', '12-31')
        ]
        
        for start, end in avoid_periods:
            if start <= today_str <= end:
                return True
        return False

    def filter_stocks_by_b_s(self, stock_list):
        date = self.context.current_dt.strftime("%Y-%m-%d")
        valid_stocks = []
        df = get_call_auction(stock_list, start_date=date, end_date=date)
        if df is None or df.empty:
            return valid_stocks
        df['sellmoney'] = \
                df['a1_p']*df['a1_v'] + \
                df['a2_p']*df['a2_v'] + \
                df['a3_p']*df['a3_v'] + \
                df['a4_p']*df['a4_v'] + \
                df['a5_p']*df['a5_v']
        df['buymoney'] = \
                df['b1_p']*df['b1_v'] + \
                df['b2_p']*df['b2_v'] + \
                df['b3_p']*df['b3_v'] + \
                df['b4_p']*df['b4_v'] + \
                df['b5_p']*df['b5_v']
        stocks = df[df['buymoney'] > df['sellmoney']].code.tolist()
        valid_stocks = [stock for stock in stock_list if stock in stocks]
        return valid_stocks

    def today_is_between(self):
        today = self.context.current_dt.strftime('%m-%d')
        if ('01-01' <= today) and (today <= '12-31'):
            return True
        elif ('01-01' <= today) and (today <= '12-31'):
            return True     
        elif ('01-01' <= today) and (today <= '12-31'):
            return True 
        else:
            return False
            
    def get_st(self):
        stocks = get_index_stocks('399101.XSHE', date=self.context.previous_date)
        st_data = get_extras('is_st', stocks, count=1, end_date=self.context.previous_date)
        st_data = st_data.T
        st_data.columns = ['is_st']
        st_data = st_data[st_data['is_st'] == False]
        filtered_stocks = st_data.index.tolist()
        return filtered_stocks    

    def get_shifted_date(self, date, days, days_type='T'):
        d_date = self.transform_date(date, 'd')
        yesterday = d_date + dt.timedelta(-1)
        if days_type == 'N':
            shifted_date = yesterday + dt.timedelta(days+1)
        if days_type == 'T':
            td = get_trade_days(end_date=date,count=-days)
            shifted_date = td[0]
        return str(shifted_date)
    
    def transform_date(self, date, date_type):
        if type(date) == str:
            str_date = date
            dt_date = dt.datetime.strptime(date, '%Y-%m-%d')
            d_date = dt_date.date()
        elif type(date) == dt.datetime:
            str_date = date.strftime('%Y-%m-%d')
            dt_date = date
            d_date = dt_date.date()
        elif type(date) == dt.date:
            str_date = date.strftime('%Y-%m-%d')
            dt_date = dt.datetime.strptime(str_date, '%Y-%m-%d')
            d_date = date
        dct = {'str':str_date, 'dt':dt_date, 'd':d_date}
        return dct[date_type]    
        
    def get_ever_hl_stock(self, initial_list, date):
        df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','high','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
        df = df.dropna()
        cd2 = df['close'] != df['high_limit']
        df = df[cd2]
        hl_list = list(df.code)
        return hl_list        
            
    def get_hl_stock(self, initial_list, date):
        df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','low','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
        df = df.dropna()
        df = df[df['close'] == df['high_limit']]
        hl_list = list(df.code)
        return hl_list

    def rzq_list(self, initial_list): 
        yesterday = self.context.previous_date
        df = get_price(initial_list, end_date=yesterday, frequency='daily', fields=['close','high_limit'], count=2, panel=False, fill_paused=False, skip_paused=False)
        df = df[(df.close==df.high_limit)]
        df.drop_duplicates(subset=['code'],keep=False,inplace=True)
        df = df[df.time!=self.transform_date(yesterday, 'dt')]
        zb_list = df.code.tolist()
        return zb_list
        
    def filter_stocks(self, stocks):
        yesterday = self.context.previous_date
        group = get_price(
            stocks,
            count=self.ma_period,
            frequency='1d',
            fields=['close', 'low', 'volume'],
            end_date=yesterday,
            panel=False
        ).groupby('code')       
        last_df = group.nth(-1)[['close','volume']]
        prev_df = group.nth(-2)[['low','volume']].add_prefix('prev_')
        mean_df = group['close'].apply(lambda x:x.mean())
        mean_df = mean_df.rename('ma')
        out_df = last_df.join(prev_df)
        out_df = out_df.join(mean_df)
        out_df = out_df[
            (out_df.close>out_df.ma) & 
            (out_df.close>out_df.prev_low) &
            (out_df.volume>out_df.prev_volume) &
            (out_df.volume<self.volume_ratio_threshold * out_df.prev_volume) &
            (out_df.close>1)]
        valid_stocks = out_df.index.tolist()
        return valid_stocks
            
    def GJT_filter_stocks(self, stocks):
        q = query(
            valuation.code,
        ).filter(
            valuation.code.in_(stocks),
            income.np_parent_company_owners > self.min_net_profit,
            income.net_profit > self.min_net_profit,
            income.operating_revenue > self.min_operating_revenue,
        )
        df = get_fundamentals(q)
        final_list = list(df.code)
        return final_list

    def check_dieting(self):
        if not hasattr(self, 'dieting_stocks'):
            self.dieting_stocks = []
            
        current_holdings = self.get_strategy_positions()
        if len(self.dieting_stocks) == 0:
            current_data = get_current_data()
            for stock in current_holdings:
                position = self.context.portfolio.positions[stock]
                if (current_data[stock].last_price <= current_data[stock].low_limit and 
                    position.closeable_amount > 0 and 
                    stock not in self.dieting_stocks):
                    self.dieting_stocks.append(stock)
            return
            
        current_data = get_current_data()
        to_remove = []
        
        for stock in self.dieting_stocks:
            if stock not in current_holdings:
                to_remove.append(stock)
                continue
                
            position = self.context.portfolio.positions[stock]
            if position.closeable_amount <= 0:
                continue
                
            if (current_data[stock].last_price > current_data[stock].low_limit):
                try:
                    stock_name = get_security_info(stock).display_name
                except:
                    stock_name = stock
                cost_price = position.avg_cost
                current_price = current_data[stock].last_price
                
                if cost_price > 0:
                    profit_rate = (current_price / cost_price - 1) * 100
                    log.info(f'[{self.name}] 跌停打开，止损卖出：{stock_name}({stock}) | 成本价：{cost_price:.2f}元 | 现价：{current_price:.2f}元 | 盈亏：{profit_rate:+.2f}%')
                
                self.close_position(stock)
                to_remove.append(stock)
        
        for stock in to_remove:
            if stock in self.dieting_stocks:
                self.dieting_stocks.remove(stock)

    def print_date_separator(self):
        log.info("=" * 60)


# ==============================================================================
# 策略C: ETF反弹策略
# ==============================================================================
class StrategyETF2(BaseStrategy):
    def __init__(self, name, weight):
        super().__init__(name, weight)
        self.init_globals()

    def init_globals(self):
        self.limit_days = 2
        self.n_days = 5
        self.holding_days = 0
        self.buy_list = []
        self.etf_pool_2 = [
            '159536.XSHE',  # 中证2000
            '159629.XSHE',  # 中证1000
            '159922.XSHE',  # 中证500
            '159919.XSHE',  # 沪深300
            '159783.XSHE'  # 双创50
        ]

    def initialize(self, context):
        super().initialize(context)

    def strategy_2_sell(self):
        self.buy_list = []
        sell_list = []
        sell_for_money_list = []
        # 获取近3日的历史数据
        for etf in self.etf_pool_2:
            df = get_price(etf, end_date=self.context.previous_date, count=4, frequency='daily', fields=['high', 'close'])
            df = df.reset_index()
            if len(df) < 4:
                return
            pre_high_max = df['high'].max()
            yestoday_close = df['close'].iloc[-1]
            # 获取当前盘中实时数据
            current_data = get_current_data()
            today_open = current_data[etf].day_open
            today_close = current_data[etf].last_price
            # 买入条件判断，开盘相比最高价下跌2% & 最新价相比开盘价涨1%
            if today_open / pre_high_max < 0.98 and today_close / today_open > 1.01:
                self.buy_list.append(etf)
            # 卖出条件判断，当前价格小于昨日收盘价
            if today_close < yestoday_close:
                sell_list.append(etf)

        # 保留最佳标的
        if self.buy_list:
            self.buy_list.sort(key=lambda x: self.etf_pool_2.index(x))
            selected_etf = self.buy_list[0]
            self.buy_list = [selected_etf]
            log.info(f"[{self.name}] 选出：{self.buy_list}")
            current_holdings = self.get_strategy_positions()
            if current_holdings and self.etf_pool_2.index(current_holdings[0]) < self.etf_pool_2.index(selected_etf):
                # 如果有持仓，且持有的ETF不是高优先级ETF，则清仓
                sell_for_money_list.append(current_holdings[0])

        for etf in self.get_strategy_positions():
            position = self.context.portfolio.positions[etf]
            securities = position.security  # 股票代码
            trade_date = position.init_time
            
            # --- 修改开始：增加对 trade_date 的检查 ---
            if trade_date is None:
                log.warning(f"[{self.name}] 无法计算持仓天数，因为仓位 {securities} 的开仓时间(init_time)为None。可能该仓位从未成交。")
                # 我们可以选择卖出这个有问题的仓位，或者跳过
                # 这里选择卖出，以清理可能存在的异常状态
                self.close_position(securities)
                continue # 跳过本次循环的剩余部分，处理下一个持仓
            # --- 修改结束 ---

            # 计算持仓天数
            held_days = len(get_trade_days(start_date=trade_date, end_date=self.context.current_dt)) - 1
            
            # --- 修改开始：增加对 held_days 计算结果的检查 ---
            if held_days < 0:
                log.warning(f"[{self.name}] 持仓天数计算异常，结果为负数。证券: {securities}，可能是日期参数问题。")
                held_days = 0 # 赋予一个默认值，防止后续逻辑出错
            # --- 修改结束 ---

            if (securities in sell_list and held_days >= self.limit_days) or (held_days >= self.n_days) or \
                    (securities in sell_for_money_list):
                self.close_position(securities)
                log.info(f"[{self.name}] 卖出：{securities}，持股{securities} {held_days}天")
        if self.buy_list:
            log.info(f"[{self.name}] 存在反弹可购买选项: {self.buy_list}")
        else:
            log.info(f"[{self.name}] 策略2今日无反弹可购买选项")
            
    def strategy_2_buy(self):
        self.buy_list = list(set(self.buy_list) - set(self.get_strategy_positions()))
        if len(self.buy_list) > 0:
            # --- MODIFICATION START ---
            # 使用考虑风控的有效资金
            cash = self.get_effective_cash()
            # --- MODIFICATION END ---
            if cash < 100:
                log.warn(f'[{self.name}] cash不足:{cash}')
            else:
                for etf in self.buy_list:
                    log.info(f"[{self.name}] 符合策略2买入条件：{etf}")
                    self.open_position(etf, cash)


# ==============================================================================
# 策略D: ETF轮动策略 (已替换为新策略)
# ==============================================================================
class StrategyETF3(BaseStrategy):
    def __init__(self, name, weight):
        super().__init__(name, weight)
        self.init_globals()

    def init_globals(self):
        # 核心资产轮动策略参数
        self.stock_sum = 1
        self.etf_pool = [
            # 境外
            "513100.XSHG",  # 纳指ETF
            "513520.XSHG",  # 日经ETF
            "513030.XSHG",  # 德国ETF
            # 商品
            "518880.XSHG",  # 黄金ETF
            "159980.XSHE",  # 有色ETF
            "159985.XSHE",  # 豆粕ETF
            "501018.XSHG",  # 南方原油
            # 债券
            # "511090.XSHG",  # 30年国债ETF
            # 国内
            "513130.XSHG",  # 恒生科技
            "510180.XSHG",
            "159915.XSHE",
            "512290.XSHG",
            "588120.XSHG",
            "515070.XSHG",
            
            "159851.XSHE",
            "159637.XSHE",
            "159550.XSHE",
            "512710.XSHG",
            "159692.XSHE",
        ]
        
        self.m_days = 25  # 动量参考天数

    def filter(self):
        """
        核心评分逻辑，完全按照新策略实现，未做任何改动。
        """
        data = pd.DataFrame(index=self.etf_pool, columns=["annualized_returns", "r2", "score"])
        current_data = get_current_data()
        for etf in self.etf_pool:
            df = get_price(etf, end_date=self.context.previous_date, count=self.m_days, frequency='daily',
                           fields=['close', 'high'], fq='post', panel=False)
            prices = np.append(df["close"].values, current_data[etf].last_price)

            # 设置参数
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))

            # 计算年化收益率
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1

            # 计算R²
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0

            # 计算得分
            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]

            # 过滤近3日跌幅超过5%的ETF
            if min(prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4]) < 0.95:
                data.loc[etf, "score"] = 0

        # 过滤ETF，并按得分降序排列
        data = data.query("0 < score < 6").sort_values(by="score", ascending=False)
        
        return data.index.tolist()

    def trade(self):
        """
        调仓逻辑，已修改为使用BaseStrategy的方法进行交易，确保持仓和资金隔离。
        """
        # 1. 使用新策略的核心逻辑筛选出目标ETF
        target_etfs = self.filter()[:self.stock_sum]
        
        if not target_etfs:
            log.info(f"[{self.name}] 无符合条件的ETF，清空持仓。")
            # 如果没有目标，清空当前策略的所有持仓
            for etf in self.get_strategy_positions():
                self.close_position(etf)
            return
            
        selected_etf = target_etfs[0]
        current_holdings = self.get_strategy_positions()
        
        # 2. 计算当前策略可用的有效资金
        strategy_cash = self.get_effective_cash()
        log.debug(f"[{self.name}] 可用资金: {strategy_cash:.2f}")
        
        # 3. 如果已经持有最优ETF，则不操作
        if current_holdings and current_holdings[0] == selected_etf:
            log.debug(f"[{self.name}] 当前持仓 {selected_etf} 为最优，不调仓。")
            return
            
        # 4. 如果持有其他ETF，则先清仓
        for etf in current_holdings:
            if etf != selected_etf:
                log.info(f"[{self.name}] 准备调仓：卖出 {etf}")
                self.close_position(etf)
        
        # 5. 买入新选中的ETF
        # 卖出后需要重新获取现金，因为self.cash在close_position中已更新
        strategy_cash_after_sell = self.get_effective_cash()
        if strategy_cash_after_sell > 0:
            log.info(f"[{self.name}] 买入最优ETF: {selected_etf}，金额: {strategy_cash_after_sell:.2f}")
            self.open_position(selected_etf, strategy_cash_after_sell)
        else:
            log.warning(f"[{self.name}] 资金不足或处于风控期，无法买入 {selected_etf}。")

# ==============================================================================
# 策略E: 低位三连阳首板（次日买）—— 融合自 V14 低位三连阳首板优化
# ==============================================================================
class StrategySanYang(BaseStrategy):
    """第5策略：低位三连阳首板，次日买入。保留V14单仓集中特征（最多持1只，单仓可用满策略资金）。"""

    def __init__(self, name, weight):
        super().__init__(name, weight)
        self.init_globals()

    def init_globals(self):
        # V14 参数
        self.max_position_pct = 1.0       # 单仓最大比例（100%，保持V14单仓集中）
        self.max_hold_count = 1            # 最大持仓数量（1只）
        self.min_turnover = 5e8            # 最小成交额（元）
        self.max_turnover = 30e8           # 最大成交额（元）
        self.max_price_rise = 0.05         # 前两日涨幅上限
        self.dynamic_stop_loss = -0.07     # 动态止损线（默认-7%）
        self.market_risk_off = False       # 大盘风险信号
        self.cost = {}                     # 记录买入成本价 {code: avg_cost}

        # 状态存储（原 V14 的 g 变量，改为策略实例属性实现隔离）
        self.information = {}              # 买入日期记录 {code: {buy_date}}
        self.sold_stocks = set()
        self.base_stocks = []
        self.today_pick = []
        self.pick_cache_date = ''
        self.minute_sell_cache = {}
        self.close_sell_cache = {}
        self.today_high = {}

    def initialize(self, context):
        # 不重复设置全局滑点/费用，沿用主 initialize 的全局配置，避免覆盖其他策略
        super().initialize(context)

    # ---------- 选股逻辑 ----------
    def get_stock_list(self):
        """主选股函数：首板 -> 波动过滤 -> 市值 -> 量价 -> 竞价"""
        target_list = self.prepare_stock_list()
        print(f"[三连阳] 首板标的数量: {len(target_list)}只")
        if not target_list:
            return []
        y_day = self.context.previous_date
        t_now = self.context.current_dt.strftime("%Y-%m-%d")
        target_list = self.filter_high_volatility(target_list, y_day)
        print(f"[三连阳] 过滤近5日波动>20%后: {len(target_list)}只")
        if not target_list:
            return []
        target_list = self.filter_market_cap(target_list, y_day)
        print(f"[三连阳] 市值过滤后: {len(target_list)}只")
        if not target_list:
            return []
        target_list = self.filter_volume_price(target_list, y_day)
        print(f"[三连阳] 量价过滤后: {len(target_list)}只")
        if not target_list:
            return []
        target_list = self.filter_auction(target_list, y_day, t_now)
        print(f"[三连阳] 最终选中: {target_list} (共{len(target_list)}只)")
        return target_list

    def filter_market_cap(self, stock_list, y_day):
        if not stock_list:
            return []
        df = get_valuation(stock_list, start_date=y_day, end_date=y_day,
                           fields=['market_cap', 'circulating_market_cap'])
        if df.empty:
            return []
        df.set_index('code', inplace=True)
        return df[(df.market_cap >= 30) & (df.circulating_market_cap <= 300)].index.tolist()

    def filter_volume_price(self, stock_list, y_day):
        if not stock_list:
            return []
        df = get_price(stock_list, end_date=y_day, frequency='1d',
                       fields=['close', 'open', 'high', 'volume', 'money'],
                       count=35, skip_paused=True, fq='pre', panel=False)
        if df.empty:
            print("[三连阳量价] 历史数据不足")
            return []
        candidates = []
        for code, group in df.groupby('code'):
            if len(group) < 6:
                continue
            group = group.sort_values('time').reset_index(drop=True)
            last = group.iloc[-1]
            d_b1 = group.iloc[-2]
            d_b2 = group.iloc[-3]
            d_b3 = group.iloc[-4]
            # 条件1：成交额范围
            if last.money < self.min_turnover or last.money > self.max_turnover:
                continue
            # 条件2：放量要求 - 昨日成交量 >= 前日成交量 * 2
            if d_b1.volume <= 0 or last.volume < d_b1.volume * 2:
                continue
            # 条件3：前天成交量 <= 大前天成交量 * 2
            if d_b2.volume <= 0 or d_b1.volume > d_b2.volume * 2:
                continue
            # 条件4：爆量限制
            if len(group) >= 31:
                prev_vols = group.volume.iloc[-6:-1].values
                if len(prev_vols) == 5 and prev_vols.min() > 0:
                    avg_vol, min_vol = prev_vols.mean(), prev_vols.min()
                    if (last.volume > avg_vol * 8 or last.volume > min_vol * 12) and last.close > group.high.iloc[-31:-1].max():
                        continue
            # 条件5：双阳线要求 - T-2和T-3均为阳线
            if not (d_b1.close > d_b1.open and d_b2.close > d_b2.open):
                continue
            # 条件6：数据异常检查
            if d_b2.close == 0 or d_b3.close == 0:
                continue
            # 条件7：短期涨幅限制 - 前两日涨幅均 < max_price_rise
            g1 = (d_b1.close - d_b2.close) / d_b2.close
            g2 = (d_b2.close - d_b3.close) / d_b3.close
            if g1 >= self.max_price_rise or g2 >= self.max_price_rise:
                continue
            candidates.append(code)
        return candidates

    def filter_auction(self, stock_list, y_day, t_now):
        """集合竞价过滤：竞价量>=昨3% 且 竞价涨幅0%~6%"""
        if not stock_list:
            return []
        hist_df = get_price(stock_list, end_date=y_day, frequency='1d',
                            fields=['close', 'volume'], count=1,
                            skip_paused=True, panel=False)
        if hist_df.empty:
            return []
        hist_map = hist_df.set_index('code')[['close', 'volume']].to_dict('index')
        start = t_now + ' 09:15:00'
        end = t_now + ' 09:26:00'
        sbgk = []
        for s in stock_list:
            if s not in hist_map:
                continue
            h = hist_map[s]
            lc, lv = h['close'], h['volume']
            if lc <= 0 or lv <= 0:
                continue
            try:
                auction = get_call_auction(s, start_date=start, end_date=end,
                                           fields=['time', 'volume', 'current'])
                if auction.empty:
                    continue
                al = auction.iloc[-1]
                if al.volume / lv < 0.03:
                    continue
                ratio = al.current / lc
                if ratio <= 1.0 or ratio >= 1.06:
                    continue
                sbgk.append(s)
            except:
                continue
        return sbgk

    def check_market_risk(self, y_day):
        """大盘风控：沪深300连跌3日且5日跌幅>5%则暂停开仓"""
        try:
            hs300 = get_price('000300.XSHG', end_date=y_day, frequency='1d',
                              fields=['close'], count=10, skip_paused=True)
            if hs300 is None or len(hs300) < 10:
                return False
            closes = hs300['close'].values
            daily_returns = np.diff(closes) / closes[:-1]
            down_days = 0
            for ret in reversed(daily_returns):
                if ret < 0:
                    down_days += 1
                else:
                    break
            ret_5d = (closes[-1] - closes[-5]) / closes[-5] if closes[-5] > 0 else 0
            if down_days >= 3 and ret_5d < -0.05:
                print(f"[三连阳大盘风控] 沪深300连跌{down_days}天, 5日收益{ret_5d*100:.1f}%, 暂停开仓")
                return True
            return False
        except Exception as e:
            print(f"[三连阳大盘风控] 检查失败: {e}")
            return False

    def update_dynamic_stop_loss(self, y_day):
        """动态止损：波动率<15%→-5%；15%~25%→-7%；>25%→-10%"""
        try:
            hs300 = get_price('000300.XSHG', end_date=y_day, frequency='1d',
                              fields=['close'], count=20, skip_paused=True)
            if hs300 is None or len(hs300) < 10:
                self.dynamic_stop_loss = -0.07
                return
            closes = hs300['close'].values
            returns = np.diff(closes) / closes[:-1]
            volatility = np.std(returns) * np.sqrt(252)
            if volatility < 0.15:
                self.dynamic_stop_loss = -0.05
            elif volatility < 0.25:
                self.dynamic_stop_loss = -0.07
            else:
                self.dynamic_stop_loss = -0.10
            print(f"[三连阳动态止损] 波动率{volatility*100:.1f}%, 止损线{self.dynamic_stop_loss*100:.0f}%")
        except Exception as e:
            self.dynamic_stop_loss = -0.07
            print(f"[三连阳动态止损] 计算失败，使用默认-7%: {e}")

    def get_buy(self):
        """买入：09:27执行。一字板跳过；单仓集中（最多1只）"""
        c_data = get_current_data()
        t_date = self.context.current_dt.strftime('%Y%m%d')
        y_day = self.context.previous_date
        self.update_dynamic_stop_loss(y_day)
        self.market_risk_off = self.check_market_risk(y_day)
        if self.market_risk_off:
            print("[三连阳买入] 大盘风险信号，今日暂停开仓")
            return
        holdings = self.get_strategy_positions()
        if len(holdings) >= self.max_hold_count:
            print(f"[三连阳买入] 持仓已达上限 {self.max_hold_count} 只")
            return
        if self.pick_cache_date != t_date:
            self.today_pick = self.get_stock_list()
            self.pick_cache_date = t_date
        qualified = [s for s in self.today_pick if s not in holdings]
        print(f"[三连阳买入] 候选标的(排除持仓后): {qualified}")
        if not qualified:
            return
        slots = self.max_hold_count - len(holdings)
        to_buy = qualified[:slots]
        cash = self.get_effective_cash()
        if cash <= 0:
            print("[三连阳买入] 策略资金不足或处于风控期，无法买入")
            return
        per_stock = min(cash / len(to_buy), cash)   # 单仓集中：每只最多用满策略资金
        print(f"[三连阳买入] 当前持仓{len(holdings)}只，可再买{slots}只，每只分配{per_stock:.2f}")
        for s in to_buy:
            cd = c_data[s]
            op = cd.day_open
            if op >= cd.high_limit * 0.99:
                print(f"  [三连阳买入跳过] {s}: 一字板无法买入")
                continue
            if cd.paused:
                print(f"  [三连阳买入跳过] {s}: 停牌，无法买入")
                continue
            if op <= 0:
                print(f"  [三连阳买入跳过] {s}: 开盘价无效，无法买入")
                continue
            # V14原逻辑：09:27盘前以开盘价市价下单（订单09:30才撮合，返回open而非held），
            # 因此不依赖基类 order_target_value_ 的 held 判定，直接按开盘价乐观记录虚拟账户，
            # 保证首板次日"竞价买入"逻辑连续；若实际未成交，尾盘卖出时的同步机制会自动纠偏。
            shares = int(per_stock / op / 100) * 100
            if shares < 100:
                print(f"  [三连阳买入跳过] {s}: 资金不足1手")
                continue
            order = order_value(s, per_stock, MarketOrderStyle(op))
            if order is not None:
                self.cash -= shares * op
                self.positions[s] = self.positions.get(s, 0) + shares
                self.information[s] = {'buy_date': t_date}
                self.cost[s] = op
                print(f"  [三连阳买入下单] {s}: 开盘价{op:.2f}, 计划金额{per_stock:.2f}, 预计{shares}股, 订单{order}")
            else:
                print(f"  [三连阳买入失败] {s}: 下单未受理")

    def get_close_sell(self):
        """尾盘止盈止损：11:25/13:30/14:55。涨停持有、盈利>20%放宽止损"""
        t_date = self.context.current_dt.strftime("%Y%m%d")
        hold = [s for s in self.positions if self.information.get(s, {}).get('buy_date') != t_date]
        print(f"[三连阳尾盘] 可卖标的: {hold}")
        if not hold:
            return
        metrics = self.close_sell_cache
        c_data = get_current_data()
        for s in hold:
            if s not in metrics:
                continue
            cd = c_data[s]
            cp = cd.last_price
            yc = metrics[s]['y_close']
            ma5 = metrics[s]['ma5']
            dg = (cp - yc) / yc
            avg_cost = self.cost.get(s, 0)
            pp = (cp - avg_cost) / avg_cost if avg_cost > 0 else 0
            print(f"  [三连阳持仓检查] {s}: 现价{cp:.2f}, 成本{avg_cost:.2f}, 收益{pp*100:.2f}%, 当日涨跌{dg*100:.2f}%, MA5={ma5:.2f}")
            # 当日涨停时坚决持有（让利润奔跑）
            if cp >= cd.high_limit * 0.99:
                print(f"[三连阳持有] {s}: 当日涨停，继续持有")
                continue
            sell, reason = False, ""
            # 盈利持有逻辑 - 盈利>20%后放宽止损到-10%
            if pp > 0.20:
                if pp <= -0.10:
                    sell, reason = True, f"盈利回吐至-10% ({pp*100:.2f}%)"
                elif dg < -0.05:
                    sell, reason = True, f"盈利股当日跌幅>5% ({dg*100:.2f}%)"
            else:
                # 标准止损
                if pp > 0.5:
                    sell, reason = True, "收益>50%"
                if dg < -0.02:
                    sell, reason = True, f"当日涨幅<-2% ({dg*100:.2f}%)"
                elif cp < cd.day_open * 0.96:
                    sell, reason = True, f"当前价<开盘价的-4% ({cp:.2f}<{cd.day_open*0.96:.2f})"
                elif pp <= self.dynamic_stop_loss:
                    sell, reason = True, f"收益<={self.dynamic_stop_loss*100:.0f}% ({pp*100:.2f}%)"
                elif cp < ma5 * 0.97:
                    sell, reason = True, f"跌破5日均线-3% ({cp:.2f}<{ma5*0.97:.2f})"
            if sell:
                self.close_position(s)
                self.cost.pop(s, None)
                print(f"    [三连阳卖出] {s}: {reason}，清仓")
            else:
                print(f"    [三连阳持有] {s}: 无卖出条件触发")

    def get_minute_sell(self):
        """每分钟线性止盈：9:30-11:25。昨日收跌标的冲高回撤清仓"""
        ct = self.context.current_dt.time()
        if ct < dt.time(9, 30) or ct > dt.time(11, 25):
            return
        t_date = self.context.current_dt.strftime("%Y%m%d")
        hold = [s for s in self.positions if self.information.get(s, {}).get('buy_date') != t_date]
        if not hold:
            return
        c_data = get_current_data()
        for s in hold:
            cache = self.minute_sell_cache.get(s)
            if not cache or cache['date'] != self.context.previous_date:
                continue
            cd = c_data[s]
            cp = cd.last_price
            if cp >= cd.high_limit * 0.99:
                continue
            if cache['y_day_gain'] >= 0:
                continue
            th = self.today_high.get(s, 0)
            if cp > th:
                self.today_high[s] = cp
                th = cp
            chr = (th - cache['y_close']) / cache['y_close'] if cache['y_close'] > 0 else 0
            if chr > 0.03:
                lt = max(0.005, 0.02 - (chr - 0.01) * 0.5)
                if cp < th * (1 - lt):
                    self.close_position(s)
                    self.cost.pop(s, None)
                    self.today_high.pop(s, None)
                    print(f"[三连阳线性止盈] {s}: 昨日跌幅{cache['y_day_gain']*100:.2f}%, 冲高{chr*100:.2f}%, 回撤{(1-cp/th)*100:.2f}% > {lt*100:.2f}%, 清仓")

    def filter_high_volatility(self, stock_list, y_day):
        """近5日波动>20%过滤"""
        if not stock_list:
            return []
        df = get_price(stock_list, end_date=y_day, frequency='1d',
                       fields=['high', 'low'], count=5, panel=False,
                       skip_paused=True, fill_paused=False)
        if df.empty:
            return stock_list
        grp = df.groupby('code')
        chg = (grp['high'].max() - grp['low'].min()) / grp['low'].min()
        return chg[chg <= 0.2].index.tolist()

    def prepare_stock_list(self):
        """首板过滤：昨日涨停且前一日未涨停"""
        y_day = self.context.previous_date
        if not self.base_stocks:
            self.prepare_base_stocks()
        df = get_price(self.base_stocks, end_date=y_day, frequency='1d',
                       fields=['close', 'high_limit'], count=2, panel=False,
                       skip_paused=True, fill_paused=False, fq='pre')
        if len(df) < 2:
            return []
        df['is_limit'] = np.isclose(df.close, df.high_limit, rtol=0.005, atol=0.01)
        groups = df[df.is_limit].groupby('time')['code'].apply(set)
        if len(groups) >= 2:
            return list(groups.iloc[-1] - groups.iloc[-2])
        elif len(groups) == 1:
            return list(groups.iloc[-1])
        return []

    def prepare_base_stocks(self):
        """基础股票池：剔除ST/退市/次新/北交所/科创板"""
        by_date = get_trade_days(end_date=self.context.previous_date, count=50)[0]
        all_s = get_all_securities(['stock'], date=by_date).index
        cd = get_current_data()
        self.base_stocks = [s for s in all_s if not (
            s[0] in '3489' or s[:2] == '68' or
            cd[s].is_st or cd[s].paused or
            '退' in cd[s].name or 'ST' in cd[s].name
        )]
        print(f"[三连阳基础池] 筛选完成，共{len(self.base_stocks)}只")

    def precompute_minute_sell_cache(self):
        """盘前预计算缓存：分钟止盈用 y_close/y_day_gain，尾盘用 y_close/ma5"""
        pos = list(self.positions.keys())
        if not pos:
            self.minute_sell_cache = {}
            self.close_sell_cache = {}
            return
        df2 = get_price(pos, end_date=self.context.previous_date, frequency='1d',
                        fields=['close'], count=2, panel=False,
                        skip_paused=False, fill_paused=True)
        for s, sub in df2.groupby('code')['close']:
            if len(sub) >= 2:
                yc, pc = sub.iloc[-1], sub.iloc[-2]
                self.minute_sell_cache[s] = {
                    'y_close': yc,
                    'prev_close': pc,
                    'y_day_gain': (yc - pc) / pc if pc > 0 else 0,
                    'date': self.context.previous_date
                }
        df5 = get_price(pos, end_date=self.context.previous_date, frequency='1d',
                        fields=['close'], count=5, panel=False,
                        skip_paused=False, fill_paused=True)
        self.close_sell_cache = {}
        for s, sub in df5.groupby('code')['close']:
            if len(sub) >= 2:
                self.close_sell_cache[s] = {
                    'y_close': sub.iloc[-1],
                    'ma5': sub.mean()
                }
        self.today_high.clear()

    def after_trading_end(self):
        """收盘清理缓存"""
        self.sold_stocks.clear()
        cur = set(self.positions.keys())
        self.information = {k: v for k, v in self.information.items() if k in cur}
        self.minute_sell_cache = {k: v for k, v in self.minute_sell_cache.items() if k in cur}
        self.close_sell_cache = {k: v for k, v in self.close_sell_cache.items() if k in cur}
        self.today_high.clear()


# ==============================================================================
# 多策略控制器
# ==============================================================================
class MultiStrategyController:
    def __init__(self):
        self.strategies = []
        self.context = None
        # --- MODIFICATION START ---
        # 全局风控属性
        self.global_max_drawdown = 0.0
        self.peak_nav = 0.0
        self.in_global_risk = False
        # --- MODIFICATION END ---

    def add_strategy(self, strategy_instance):
        self.strategies.append(strategy_instance)

    def initialize(self, context):
        self.context = context
        for strategy in self.strategies:
            strategy.initialize(context)
        # --- MODIFICATION START ---
        # 初始化峰值净值
        self.peak_nav = context.portfolio.total_value
        # --- MODIFICATION END ---

    def run_strategy_function(self, function_name, *args, **kwargs):
        for strategy in self.strategies:
            func = getattr(strategy, function_name, None)
            if func and callable(func):
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    log.error(f"执行策略 '{strategy.name}' 的函数 '{function_name}' 时出错: {e}")
                    
    # --- MODIFICATION START ---
    def check_global_risk(self):
        """
        全局风控主函数，在每日收盘前运行。
        计算整体组合的回撤，并根据阈值触发或解除风控。
        """
        if not CHECK_RISK:
            return 
        
        context = self.context
        current_nav = context.portfolio.total_value

        # 更新峰值净值
        if current_nav > self.peak_nav:
            self.peak_nav = current_nav
            log.debug(f"全局峰值净值更新为: {self.peak_nav:.2f}")

        # 计算当前回撤
        current_drawdown = (self.peak_nav - current_nav) / self.peak_nav
        self.global_max_drawdown = max(self.global_max_drawdown, current_drawdown)
        
        log.info(f"全局组合监控 | 当前净值: {current_nav:.2f} | 峰值净值: {self.peak_nav:.2f} | 当前回撤: {current_drawdown:.2%} | 最大回撤: {self.global_max_drawdown:.2%}")

        # 触发风控条件
        if current_drawdown >= GLOBAL_DRAWDOWN_THRESHOLD:
            if not self.in_global_risk:
                log.warning(f"!!! 全局回撤达到 {current_drawdown:.2%}，超过阈值 {GLOBAL_DRAWDOWN_THRESHOLD:.2%}，启动全局风控 !!!")
                self.in_global_risk = True
                # 通知所有策略进入风控状态
                for strategy in self.strategies:
                    strategy.force_reduce_risk()
            else:
                log.warning(f"全局风控已启动，当前回撤 {current_drawdown:.2%}。")
        
        # 解除风控条件
        elif self.in_global_risk and current_drawdown <= GLOBAL_RECOVERY_THRESHOLD:
            log.info(f"全局回撤修复至 {current_drawdown:.2%}，低于解除阈值 {GLOBAL_RECOVERY_THRESHOLD:.2%}，解除全局风控。")
            self.in_global_risk = False
            # 通知所有策略恢复正常状态
            for strategy in self.strategies:
                strategy.resume_normal_risk()
    # --- MODIFICATION END ---


# --- 策略A的任务函数 ---
def strategy_a_prepare_stock_list(context):
    g.controller.strategies[0].prepare_stock_list()

def strategy_a_trade_afternoon(context):
    g.controller.strategies[0].trade_afternoon()

def strategy_a_sell_stocks(context):
    g.controller.strategies[0].sell_stocks()

def strategy_a_close_account(context):
    g.controller.strategies[0].close_account()

def strategy_a_weekly_adjustment(context):
    g.controller.strategies[0].weekly_adjustment()


# --- 策略B的任务函数 ---
def strategy_b_prepare(context):
    g.controller.strategies[1].prepare()

def strategy_b_buy(context):
    g.controller.strategies[1].buy()

def strategy_b_sell(context):
    g.controller.strategies[1].sell()

def strategy_b_check_dieting(context):
    g.controller.strategies[1].check_dieting()

def strategy_b_print_date_separator(context):
    g.controller.strategies[1].print_date_separator()

# --- 策略ETF2的任务函数 ---
def strategy_etf2_sell(context):
    g.controller.strategies[2].strategy_2_sell()

def strategy_etf2_buy(context):
    g.controller.strategies[2].strategy_2_buy()

# --- 策略ETF3的任务函数 ---
def strategy_etf3_trade(context):
    g.controller.strategies[3].trade()

# --- MODIFICATION START ---
# --- 全局风控任务函数 ---
def check_global_risk(context):
    """调用控制器的全局风控检查函数"""
    g.controller.check_global_risk()
# --- MODIFICATION END ---

# --- 策略E（三连阳首板）的任务函数 ---
def strategy_c_prepare_base_stocks(context):
    g.controller.strategies[4].prepare_base_stocks()

def strategy_c_precompute(context):
    g.controller.strategies[4].precompute_minute_sell_cache()

def strategy_c_get_buy(context):
    g.controller.strategies[4].get_buy()

def strategy_c_get_close_sell(context):
    g.controller.strategies[4].get_close_sell()

def strategy_c_get_minute_sell(context):
    g.controller.strategies[4].get_minute_sell()

def after_trading_end(context):
    """收盘清理：清理由第5策略（三连阳首板）维护的缓存"""
    g.controller.strategies[4].after_trading_end()


# ==============================================================================
# 聚宽策略主入口
# ==============================================================================
g.controller = None

def initialize(context):
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.001), type="fund")
    set_slippage(FixedSlippage(0.002), type="stock")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=3 / 10000,
        close_commission=3 / 10000,
        close_today_commission=0,
        min_commission=5,
    ), type="stock")
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=3 / 10000,
        close_commission=3 / 10000,
        close_today_commission=0,
        min_commission=5
    ), type='fund')
    
    global g
    g.controller = MultiStrategyController()
    
    strategy_a = StrategyA("策略A-概念热点", STRATEGY_A_WEIGHT)
    g.controller.add_strategy(strategy_a)
    
    strategy_b = StrategyB("策略B-弱转强", STRATEGY_B_WEIGHT)
    g.controller.add_strategy(strategy_b)
    
    strategy_etf2 = StrategyETF2("策略ETF2-反弹", STRATEGY_ETF2_WEIGHT)
    g.controller.add_strategy(strategy_etf2)

    strategy_etf3 = StrategyETF3("策略ETF3-轮动", STRATEGY_ETF3_WEIGHT)
    g.controller.add_strategy(strategy_etf3)

    strategy_san_yang = StrategySanYang("策略E-三连阳首板", STRATEGY_SAN_YANG_WEIGHT)
    g.controller.add_strategy(strategy_san_yang)
    
    g.controller.initialize(context)
    g.concept_stocks_file = 'cpt_ind_stocks.csv'
    g.concepts_file = 'cpt_ind.csv'
    
    if STRATEGY_A_WEIGHT > 0:
        run_daily(strategy_a_prepare_stock_list, '9:26')
        run_daily(strategy_a_trade_afternoon, time='14:00', reference_security='399101.XSHE')
        run_daily(strategy_a_sell_stocks, time='11:20')
        run_daily(strategy_a_close_account, '14:30')
    
    if g.controller.strategies[0].re_date == 1:
        run_daily(strategy_a_weekly_adjustment, '14:30')
    elif g.controller.strategies[0].re_date == 2:
        run_weekly(strategy_a_weekly_adjustment, 3, '14:30')
    else:
        run_daily(strategy_a_weekly_adjustment, '14:45')
    
    if STRATEGY_B_WEIGHT > 0:
        run_daily(strategy_b_prepare, time="09:26")
        run_daily(strategy_b_buy, time="09:30:05")
        run_daily(strategy_b_sell, time='13:00')
        run_daily(strategy_b_sell, time='14:55')
        run_daily(strategy_b_check_dieting, time="every_bar")
        run_daily(strategy_b_print_date_separator, time="15:05")
    if STRATEGY_ETF2_WEIGHT > 0:
        run_daily(strategy_etf2_sell, '14:49')
        run_daily(strategy_etf2_buy, '14:50')
    if STRATEGY_ETF3_WEIGHT > 0: 
        run_daily(strategy_etf3_trade, '10:00')

    if STRATEGY_SAN_YANG_WEIGHT > 0:
        run_weekly(strategy_c_prepare_base_stocks, 1, '09:10')
        run_daily(strategy_c_precompute, time='09:10')
        run_daily(strategy_c_get_buy, time='09:27')
        run_daily(strategy_c_get_close_sell, time='11:25')
        run_daily(strategy_c_get_close_sell, time='13:30')
        run_daily(strategy_c_get_close_sell, time='14:55')
        run_daily(strategy_c_get_minute_sell, time='every_bar')

    # --- MODIFICATION START ---
    # 每日收盘前运行全局风控检查
    run_daily(check_global_risk, time='14:55')
    # --- MODIFICATION END ---

    log.info("策略初始化完成，所有任务已调度。")

# ==============================================================================
# 辅助函数
# ==============================================================================
def get_stock_name(security):
    try:
        stock_info = get_security_info(security)
        return stock_info.display_name
    except Exception:
        return "未上市"
