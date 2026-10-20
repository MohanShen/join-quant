# Clone from JoinQuant
# postId: e03a2ef18247dbe1deb858eaa0fd89ce
# backtestId: 89e1382835d9689bbb9893a471747b16
# title: 四合一：七星高照+搅屎棍+五境掘金+红利

# ==================== 组合策略（整合11、12、13、14） ====================
import numpy as np
import pandas as pd
from jqdata import *
import datetime
import math
import time
from functools import wraps
from scipy.optimize import minimize

# ---------- 基类 ----------
class BaseStrategy:
    def __init__(self, name, pindex, initial_cash):
        self.name = name
        self.pindex = pindex
        self.initial_cash = initial_cash

    # ----- 通用辅助方法 -----
    def _is_suspended(self, code):
        cd = get_current_data()[code]
        return cd is None or cd.paused

    def _is_limit_up(self, code, price=None):
        if self._is_suspended(code):
            return False
        cd = get_current_data()[code]
        if cd is None or cd.high_limit is None:
            return False
        if price is None:
            price = cd.last_price
        return price is not None and price >= cd.high_limit - 0.001

    def _is_limit_down(self, code, price=None):
        if self._is_suspended(code):
            return False
        cd = get_current_data()[code]
        if cd is None or cd.low_limit is None:
            return False
        if price is None:
            price = cd.last_price
        return price is not None and price <= cd.low_limit + 0.001

    def _trading_days_diff(self, start, end):
        if start is None or end is None:
            return 0
        if start >= end:
            return 0
        days = get_trade_days(start, end)
        return len(days) - 1

    def _calendar_days_diff(self, start, end):
        if start is None or end is None:
            return 0
        if start >= end:
            return 0
        return (end - start).days

    def _order(self, security, amount, price=None):
        """通用下单函数，处理停牌、涨跌停，并获取买一价卖出"""
        if amount == 0:
            return True
        cd = get_current_data()[security]
        if cd.paused:
            return False
        if amount > 0 and cd.last_price >= cd.high_limit:
            return False
        if amount < 0 and cd.last_price <= cd.low_limit:
            return False

        if price is None:
            price = cd.last_price

        if amount < 0:
            tick = get_current_tick(security)
            if tick is not None:
                bid_price = getattr(tick, 'b1_p', 0)
                if bid_price and bid_price > 0:
                    price = bid_price

        # 价格保护
        if price < cd.low_limit:
            price = cd.low_limit
        elif price > cd.high_limit:
            price = cd.high_limit

        order(security, amount, style=LimitOrderStyle(price), pindex=self.pindex)
        return True

    def trade(self, context):
        raise NotImplementedError


# ========== 策略11：搅屎棍+全天候（整合原11.txt） ==========
class Strategy11(BaseStrategy):
    def __init__(self, pindex, initial_cash):
        super().__init__('搅屎棍+全天候', pindex, initial_cash)
        # 搅屎棍参数
        self.stoploss_limit = 0.07
        self.market_stoploss = 0.05
        self.stock_sum = 6
        self.num = 1
        self.pass_months = [1, 4]
        self.min_volume = 2000
        self.min_volume_etf = 100

        # 全天候参数
        self.confidencelevel = 1.96
        self.rebalanced_asset_values = {}
        self.raise_rate = -1
        self.period = 1
        self.run_count = 0
        self.pool = {
            'stock': {
                'rate': 0.7,
                'codes': [
                    {
                        '513600.XSHG': datetime.datetime(2017, 5, 7),
                        '159509.XSHE': datetime.datetime(2017, 5, 7),
                        '513850.XSHG': datetime.datetime(2017, 5, 7),
                        '513800.XSHG': datetime.datetime(2017, 5, 7),
                        '513030.XSHG': datetime.datetime(2017, 5, 7),
                        '164824.XSHE': datetime.datetime(2017, 5, 7),
                    },
                ]
            },
            'goods': {
                'rate': 0.3,
                'codes': [
                    {
                        '161226.XSHE': datetime.datetime(2017, 5, 7),
                        '160216.XSHE': datetime.datetime(2017, 5, 7),
                        '501018.XSHG': datetime.datetime(2017, 5, 7),
                    }
                ]
            }
        }
        self.stock_map_asset = self._init_stock_map_asset()
        self.fill_stock = '511880.XSHG'  # 货币ETF
        self.hold_list = []
        self.buy_dates = {}
        self.high_prices = {}

    def _init_stock_map_asset(self):
        stock_map = {}
        for asset in self.pool:
            for code_group in self.pool[asset]['codes']:
                for code in code_group:
                    stock_map[code] = asset
        return stock_map

    # ---- 搅屎棍专用函数 ----
    def getStockIndustry(self, stocks):
        industry = get_industry(stocks)
        return pd.Series({stock: info["sw_l1"]["industry_name"] for stock, info in industry.items() if "sw_l1" in info})

    def get_market_breadth(self):
        yesterday = self.context.previous_date if hasattr(self, 'context') else None
        if yesterday is None:
            return []
        stocks = get_index_stocks("000985.XSHG")
        count = 1
        h = get_price(
            stocks,
            end_date=yesterday,
            frequency="1d",
            fields=["close"],
            count=count + 20,
            panel=False,
        )
        h["date"] = pd.DatetimeIndex(h.time).date
        df_close = h.pivot(index="code", columns="date", values="close").dropna(axis=0)
        df_ma20 = df_close.rolling(window=20, axis=1).mean().iloc[:, -count:]
        df_bias = df_close.iloc[:, -count:] > df_ma20
        df_bias["industry_name"] = self.getStockIndustry(stocks)
        df_ratio = ((df_bias.groupby("industry_name").sum() * 100.0) / df_bias.groupby("industry_name").count()).round()
        top_values = df_ratio.loc[:, yesterday].nlargest(self.num)
        return top_values.index.tolist()

    def filter_basic_stock(self, stock_list):
        current_data = get_current_data()
        yesterday = self.context.previous_date
        return [
            stock
            for stock in stock_list
            if not current_data[stock].paused
            and not current_data[stock].is_st
            and "ST" not in current_data[stock].name
            and "*" not in current_data[stock].name
            and "退" not in current_data[stock].name
            and not (stock[0] == "4" or stock[0] == "8" or stock[:2] == "68")
            and not yesterday - get_security_info(stock).start_date < datetime.timedelta(375)
        ]

    def filter_limitup_limitdown_stock(self, stock_list):
        current_data = get_current_data()
        return [
            stock
            for stock in stock_list
            if current_data[stock].last_price < current_data[stock].high_limit and current_data[stock].last_price > current_data[stock].low_limit
        ]

    def filter(self):
        stocks = get_index_stocks("399101.XSHE")
        stocks = self.filter_basic_stock(stocks)
        stocks = (
            get_fundamentals(
                query(
                    valuation.code,
                )
                .filter(
                    valuation.code.in_(stocks),
                    indicator.adjusted_profit > 0,
                )
                .order_by(valuation.market_cap.asc())
            )
            .head(20)
            .code
        )
        stocks = self.filter_limitup_limitdown_stock(stocks)
        return stocks

    def select(self):
        I = self.get_market_breadth()
        industries = {"银行I", "煤炭I", "采掘I", "钢铁I"}
        if industries.intersection(I):
            return []
        else:
            return self.filter()

    def is_empty_month(self):
        month = self.context.current_dt.month
        return month in self.pass_months

    # ---- 全天候专用函数 ----
    def get_trade_target(self):
        dt = self.context.current_dt
        ret = []
        for asset in self.pool:
            stock_pool = self.pool[asset]['codes']
            target_stocks = []
            for stocks in stock_pool:
                cur_stocks_isOK = False
                for start_dt in stocks.values():
                    if dt >= start_dt:
                        cur_stocks_isOK = True
                        break
                if cur_stocks_isOK:
                    target_stocks = list(stocks.keys())
                    break
            ret.extend(target_stocks)
        return ret

    def cal_stocks_ratio(self, asset_alloc):
        def getdailyreturn(stock, freq, lag):
            hStocks = history(lag, freq, 'close', stock, df=True)
            dailyReturns = hStocks.resample('D').last().pct_change().fillna(0).values
            return dailyReturns

        def get_stock_ES(stock, freq, lag, confidencelevel):
            if confidencelevel == 1.96:
                a = (1 - 0.95)
            elif confidencelevel == 2.06:
                a = (1 - 0.96)
            elif confidencelevel == 2.18:
                a = (1 - 0.97)
            elif confidencelevel == 2.34:
                a = (1 - 0.98)
            elif confidencelevel == 2.58:
                a = (1 - 0.99)
            elif confidencelevel == 5:
                a = (1 - 0.99999)
            else:
                a = (1 - 0.95)
            dailyReturns = getdailyreturn(stock, freq, lag)
            dailyReturns = sorted(dailyReturns.flatten())
            quantile = int(lag * a)
            if quantile == 0:
                return 0
            sum_returns = sum(dailyReturns[:quantile])
            return -sum_returns / quantile if quantile != 0 else 0

        def stock_risk_ES(stock):
            es = get_stock_ES(stock, '1d', 120, self.confidencelevel)
            return es if not np.isnan(es) else 0

        total_ratio = 0
        stock_ratio = {}
        for stock in asset_alloc:
            es = stock_risk_ES(stock)
            stock_ratio[stock] = 1.0 / es if es != 0 else 0
            total_ratio += stock_ratio[stock]
        new_asset_ratio = {}
        for stock in asset_alloc:
            new_asset_ratio[stock] = stock_ratio[stock] / total_ratio if total_ratio != 0 else 0
        return new_asset_ratio

    def balance(self):
        asset_alloc = self.get_trade_target()
        sp = self.context.subportfolios[self.pindex]
        strategy_value = sp.total_value
        target_weights = self.cal_stocks_ratio(asset_alloc)
        targets = {stock: strategy_value * weight for stock, weight in target_weights.items()}
        self.rebalanced_asset_values = targets.copy()
        return targets

    def adjust_etf(self, targets):
        """全天候调仓ETF"""
        sp = self.context.subportfolios[self.pindex]
        current_data = get_current_data()
        # 清仓被调出的
        for stock in list(sp.positions.keys()):
            if stock not in targets and stock != self.fill_stock:
                if sp.positions[stock].total_amount > 0:
                    self._order(stock, -sp.positions[stock].closeable_amount)
        # 先卖出（若目标小于当前）
        for stock, target in targets.items():
            pos = sp.positions.get(stock)
            if pos and pos.total_amount > 0:
                value = pos.total_amount * pos.price
                if value - target > self.min_volume_etf and value - target > current_data[stock].last_price * 100:
                    self._order(stock, -pos.closeable_amount)
        # 后买入
        for stock, target in targets.items():
            pos = sp.positions.get(stock)
            current_value = pos.total_amount * pos.price if pos else 0
            if target - current_value > self.min_volume_etf and target - current_value > current_data[stock].last_price * 100:
                cash_needed = target - current_value
                if cash_needed > sp.available_cash:
                    # 卖出货币ETF凑现金
                    if self.fill_stock in sp.positions:
                        self._order(self.fill_stock, -sp.positions[self.fill_stock].closeable_amount)
                if sp.available_cash > current_data[stock].last_price * 100:
                    self._order(stock, int(target / current_data[stock].last_price // 100 * 100))

    def check(self):
        """搅屎棍每日涨停检查"""
        sp = self.context.subportfolios[self.pindex]
        hold_list = [s for s in sp.positions if s != self.fill_stock and sp.positions[s].total_amount > 0]
        if hold_list:
            df = get_price(
                hold_list,
                end_date=self.context.previous_date,
                frequency="daily",
                fields=["close", "high_limit"],
                count=1,
                panel=False,
                fill_paused=False,
            )
            df = df[df["close"] == df["high_limit"]]
            for stock in list(df.code):
                self._order(stock, -sp.positions[stock].closeable_amount)
                log.info(f"搅屎棍：{stock} 涨停打开止损卖出")

    def trade(self, context):
        self.context = context
        sp = context.subportfolios[self.pindex]
    
        # 每日检查涨停打开
        self.check()
    
        weekday = context.current_dt.weekday()
        log.info('[策略11] 当前星期: %d, 空仓月: %s' % (weekday, self.is_empty_month()))
    
        if weekday == 3:  # 周四
            log.info('[策略11] 执行调仓')
            if not self.is_empty_month():
                target = self.select()
                log.info('[策略11] 选股结果: %s' % target)
                if target:
                    # 清仓不在目标中的
                    for stock in list(sp.positions.keys()):
                        if stock != self.fill_stock and stock not in target:
                            log.info('[策略11] 卖出不在目标的 %s' % stock)
                            self._order(stock, -sp.positions[stock].closeable_amount)
    
                    # 等权买入目标（不超过 stock_sum 只）
                    count = len(target)
                    if count > self.stock_sum:
                        target = target[:self.stock_sum]
                    cash_per = sp.available_cash / len(target) if target else 0
                    log.info('[策略11] 目标: %s, 可用现金: %.2f, 每只分配: %.2f' % (target, sp.available_cash, cash_per))
    
                    for stock in target:
                        pos = sp.positions.get(stock)
                        if pos is None or pos.total_amount == 0:
                            price = get_current_data()[stock].last_price
                            if price is None or price <= 0:
                                log.info('[策略11] %s 价格无效，跳过' % stock)
                                continue
                            shares = int(cash_per // (price * 100) * 100)
                            if shares > 0:
                                log.info('[策略11] 买入 %s, 价格%.2f, 数量%d' % (stock, price, shares))
                                self._order(stock, shares)
                            else:
                                log.info('[策略11] %s 资金不足购买100股，需要%.2f元，可用%.2f元' % (stock, price*100, cash_per))
                        else:
                            log.info('[策略11] %s 已持有，跳过' % stock)
                else:
                    # 无目标，清仓所有非货币ETF
                    log.info('[策略11] 无目标，清仓所有持仓')
                    for stock in list(sp.positions.keys()):
                        if stock != self.fill_stock:
                            self._order(stock, -sp.positions[stock].closeable_amount)
            else:
                # 空仓月，执行全天候策略
                log.info('[策略11] 空仓月，执行全天候')
                targets = self.balance()
                self.adjust_etf(targets)
        else:
            log.info('[策略11] 非周四，跳过调仓')


# ========== 策略12：红利低波250日均线偏离度（原12.txt） ==========
class Strategy12(BaseStrategy):
    def __init__(self, pindex, initial_cash, target_weight):
        super().__init__('红利低波偏离度', pindex, initial_cash)
        self.etf = '512890.XSHG'
        self.ma_length = 250
        self.buy_threshold = 0.988
        self.sell_threshold = 1.092
        self.target_weight = target_weight
        self.money_fund = '511880.XSHG'      # 识别货币ETF，用于释放资金

    def _release_cash(self, context, needed_amount):
        """从策略13的持仓中释放现金，确保可用现金至少达到 needed_amount"""
        sp = context.subportfolios[self.pindex]
        if sp.available_cash >= needed_amount:
            return True
        shortage = needed_amount - sp.available_cash
        log.info('[策略12] 需要释放现金 %.2f' % shortage)

        # 遍历所有持仓（除策略12自身标的）
        for code, pos in list(sp.positions.items()):
            if code == self.etf:
                continue          # 不动策略12的持仓
            if pos.total_amount == 0:
                continue

            # 优先卖出非货币ETF（策略13的持仓）
            if code != self.money_fund:
                price = get_current_data()[code].last_price
                if price <= 0:
                    continue
                value = pos.total_amount * price
                if value > 0:
                    shares_to_sell = int(shortage // price) + 1
                    shares_to_sell = (shares_to_sell // 100) * 100   # 100股整数倍
                    shares_to_sell = min(shares_to_sell, pos.total_amount)
                    if shares_to_sell > 0:
                        log.info('[策略12] 卖出 %s 释放资金，数量 %d' % (code, shares_to_sell))
                        self._order(code, -shares_to_sell)
                        shortage -= shares_to_sell * price
                        if shortage <= 0:
                            return True
            # 如果还不够，再卖货币ETF
            else:
                price = get_current_data()[code].last_price
                if price <= 0:
                    continue
                value = pos.total_amount * price
                if value > 0:
                    shares_to_sell = int(shortage // price) + 1
                    shares_to_sell = (shares_to_sell // 100) * 100
                    shares_to_sell = min(shares_to_sell, pos.total_amount)
                    if shares_to_sell > 0:
                        log.info('[策略12] 卖出货币ETF %s 释放资金，数量 %d' % (code, shares_to_sell))
                        self._order(code, -shares_to_sell)
                        shortage -= shares_to_sell * price
                        if shortage <= 0:
                            return True
        if shortage > 0:
            log.warning('[策略12] 无法释放足够现金，缺口 %.2f' % shortage)
        return shortage <= 0

    def trade(self, context):
        sp = context.subportfolios[self.pindex]
        current_data = get_current_data()
        if current_data[self.etf].paused:
            return

        # 计算信号
        hist_close = attribute_history(self.etf, self.ma_length, '1d', ['close'], skip_paused=True)
        if len(hist_close) < self.ma_length:
            return
        ma250 = hist_close['close'].mean()

        hist_hl = attribute_history(self.etf, 1, '1d', ['high', 'low'], skip_paused=True)
        if hist_hl.empty:
            return
        prev_low = hist_hl['low'].iloc[0]
        prev_high = hist_hl['high'].iloc[0]

        ratio_low = prev_low / ma250
        ratio_high = prev_high / ma250

        pos = sp.positions.get(self.etf)
        current_value = pos.total_amount * pos.price if pos else 0
        target_value = sp.total_value * self.target_weight

        # 买入信号
        if ratio_low < self.buy_threshold:
            if current_value < target_value * 0.95:
                buy_amount = target_value - current_value
                # 释放资金
                if self._release_cash(context, buy_amount):
                    log.info('[策略12] 买入信号，目标市值 %.2f，当前 %.2f' % (target_value, current_value))
                    price = current_data[self.etf].last_price
                    if price and price > 0:
                        max_shares = int(sp.available_cash // (price * 100) * 100)
                        target_shares = int(target_value // (price * 100) * 100)
                        shares = min(max_shares, target_shares)
                        if shares >= 100:
                            self._order(self.etf, shares - (pos.total_amount if pos else 0))
                        else:
                            log.info('[策略12] 资金不足100股，跳过')
                else:
                    log.info('[策略12] 无法释放足够现金，暂不买入')
        # 卖出信号
        elif ratio_high > self.sell_threshold:
            if current_value > 0:
                log.info('[策略12] 卖出信号，清仓释放资金给策略13')
                self._order(self.etf, -pos.closeable_amount)
        else:
            if current_value > 0:
                log.debug('[策略12] 持有中，不动')
            else:
                log.debug('[策略12] 空仓，资金由策略13使用')

# ========== 策略13：5只ETF动量轮动（原13.txt） ==========
class Strategy13(BaseStrategy):
    def __init__(self, pindex, initial_cash):
        super().__init__('5ETF动量轮动', pindex, initial_cash)
        self.etf_pool = [
            '159915.XSHE',   # 创业板
            '159941.XSHE',   # 纳指ETF
            '518880.XSHG',   # 黄金ETF
            '162719.XSHE',   # 广发石油（LOF）
            '513030.XSHG'    # 德国30
        ]
        self.min_gain = 2
        self.bias20_max = 18.0
        self.bias60_max = 35.0
        self.bias250_max = 50.0
        self.cooldown_days = 10
        self.stop_loss_pct = -8.0
        self.cash_etf = '511880.XSHG'
        self.last_sell_record = {}
        self.s12_code = '512890.XSHG'   # 策略12标的，需排除

    # ---------- 辅助方法 ----------
    def check_etf(self, security):
        """计算ETF的20日涨幅、20/60/250日乖离率"""
        try:
            df = attribute_history(security, 300, '1d', ['close'], skip_paused=True, df=True)
            if df is None or len(df) < 250:
                return None
            closes = df['close'].values
            current = closes[-1]
            ret20 = (current / closes[-21] - 1) * 100
            ma20 = np.mean(closes[-20:])
            bias20 = (current / ma20 - 1) * 100
            ma60 = np.mean(closes[-60:])
            bias60 = (current / ma60 - 1) * 100
            ma250 = np.mean(closes[-250:])
            bias250 = (current / ma250 - 1) * 100
            return ret20, bias20, bias60, bias250
        except:
            return None

    def filter_and_rank(self, context):
        """筛选符合条件的ETF并按20日涨幅降序排列"""
        qualified = []
        for etf in self.etf_pool:
            res = self.check_etf(etf)
            if res is None:
                continue
            ret20, b20, b60, b250 = res
            if (ret20 > self.min_gain) and (b20 < self.bias20_max) and (b60 < self.bias60_max) and (b250 < self.bias250_max):
                qualified.append((etf, ret20))
        if not qualified:
            return []
        qualified.sort(key=lambda x: x[1], reverse=True)
        return [etf for etf, _ in qualified]

    def cooling_check(self, etf, today):
        """检查是否在冷却期内"""
        if etf not in self.last_sell_record:
            return False
        last = self.last_sell_record[etf]
        trade_days = get_trade_days(start_date=last, end_date=today)
        diff = len(trade_days) - 1
        return diff <= self.cooldown_days

    def stop_loss_triggered(self, security, context):
        """检查是否触发止损（当前价低于成本价8%）"""
        sp = context.subportfolios[self.pindex]
        pos = sp.positions.get(security)
        if pos is None or pos.total_amount == 0:
            return False
        avg_cost = pos.avg_cost
        if avg_cost <= 0:
            return False
        current_data = get_current_data()
        if security in current_data:
            current_price = current_data[security].last_price
        else:
            df = attribute_history(security, 1, '1d', ['close'], skip_paused=True, df=True)
            if df is None or len(df) == 0:
                return False
            current_price = df['close'].iloc[-1]
        ret = (current_price - avg_cost) / avg_cost * 100
        return ret <= self.stop_loss_pct

    # ---------- 主交易函数 ----------
    def trade(self, context):
        sp = context.subportfolios[self.pindex]
        today = context.current_dt.date()
        if context.current_dt.year < 2021:
            return

        # 计算策略12占用的市值
        s12_pos = sp.positions.get(self.s12_code)
        s12_value = s12_pos.total_amount * s12_pos.price if s12_pos else 0
        s13_total_value = sp.total_value - s12_value   # 策略13可用总资产

        if s13_total_value <= 0:
            log.info('[策略13] 无可用资金（策略12占用全部）')
            return

        # 当前策略13的持仓（排除s12_code）
        s13_holdings = []
        for code, pos in sp.positions.items():
            if code != self.s12_code and pos.total_amount > 0:
                s13_holdings.append(code)

        # 选股
        ranked_list = self.filter_and_rank(context)
        if not ranked_list:
            target = self.cash_etf
        else:
            target = ranked_list[0]

        # 判断当前持有的目标
        current_hold = None
        for etf in self.etf_pool:
            if etf in s13_holdings:
                current_hold = etf
                break
        if current_hold is None and self.cash_etf in s13_holdings:
            current_hold = self.cash_etf

        # 是否需要调仓
        need_trade = False
        if current_hold is None:
            need_trade = True
        elif current_hold != target:
            if current_hold != self.cash_etf:
                if self.stop_loss_triggered(current_hold, context):
                    need_trade = True
                    log.info('[策略13] 触发止损: {}'.format(current_hold))
                else:
                    res = self.check_etf(current_hold)
                    if res is None:
                        need_trade = True
                    else:
                        ret20, b20, b60, b250 = res
                        cond_self = (ret20 > self.min_gain) and (b20 < self.bias20_max) and (b60 < self.bias60_max) and (b250 < self.bias250_max)
                        rank = ranked_list.index(current_hold) + 1 if current_hold in ranked_list else len(ranked_list) + 1
                        if (not cond_self) or (rank >= 4):
                            need_trade = True
            else:
                need_trade = True

        if not need_trade:
            return

        # ---------- 清仓策略13的所有持仓（不影响512890） ----------
        for etf in self.etf_pool:
            if etf in sp.positions and sp.positions[etf].total_amount > 0:
                log.info('[策略13] 清仓 {}'.format(etf))
                self.last_sell_record[etf] = today
                self._order(etf, -sp.positions[etf].closeable_amount)
        if self.cash_etf in sp.positions and sp.positions[self.cash_etf].total_amount > 0:
            self._order(self.cash_etf, -sp.positions[self.cash_etf].closeable_amount)

        # ---------- 买入目标（使用 s13_total_value 作为资金上限） ----------
        if target == self.cash_etf:
            cash = sp.available_cash
            cash = min(cash, s13_total_value)
            if cash > 0:
                price = get_current_data()[self.cash_etf].last_price
                shares = int(cash // (price * 100) * 100)
                if shares >= 100:
                    self._order(self.cash_etf, shares)
                    log.info('[策略13] 买入银华日利，金额 %.2f' % (shares * price))
        else:
            if self.cooling_check(target, today):
                log.info('[策略13] {} 在冷却期内，暂不买入'.format(target))
                return
            price = get_current_data()[target].last_price
            if price and price > 0:
                shares = int(s13_total_value // (price * 100) * 100)
                if shares >= 100 and shares * price <= sp.available_cash:
                    self._order(target, shares)
                    log.info('[策略13] 买入 {}，数量 {}'.format(target, shares))
                else:
                    log.info('[策略13] 资金不足或金额不够，跳过')

# ========== 策略14：多因子ETF动量（原14.txt） ==========
class Strategy14(BaseStrategy):
    def __init__(self, pindex, initial_cash):
        super().__init__('多因子ETF动量', pindex, initial_cash)
        # ETF池分类
        self.overseas_etf_pool = [
            "513100.XSHG", "513290.XSHG", "513500.XSHG", "159529.XSHE",
            "513400.XSHG", "513520.XSHG", "513030.XSHG", "513080.XSHG",
            "513310.XSHG", "513730.XSHG", "159792.XSHE", "513130.XSHG",
            "513050.XSHG", "159920.XSHE", "513690.XSHG", "511380.XSHG",
            "511010.XSHG", "511220.XSHG"
        ]
        self.commodity_etf_pool = [
            "518880.XSHG", "159980.XSHE", "159985.XSHE", "501018.XSHG",
            "161226.XSHE", "159981.XSHE", "512400.XSHG"
        ]
        self.domestic_etf_pool = [
            "510300.XSHG", "510500.XSHG", "510050.XSHG", "510210.XSHG",
            "159915.XSHE", "588080.XSHG", "512100.XSHG", "563360.XSHG",
            "563300.XSHG", "512890.XSHG", "159967.XSHE", "588020.XSHG",
            "512040.XSHG", "159201.XSHE", "515790.XSHG", "563230.XSHG",
            "515880.XSHG", "512660.XSHG", "561380.XSHG", "159667.XSHE",
            "159559.XSHE", "159819.XSHE", "159381.XSHE", "159732.XSHE",
            "159995.XSHE", "512220.XSHG"
        ]
        self.etf_pool = self.overseas_etf_pool + self.commodity_etf_pool + self.domestic_etf_pool

        # 核心参数
        self.lookback_days = 25
        self.holdings_num = 1
        self.defensive_etf = '511010.XSHG'
        self.min_money = 5000
        self.loss = 0.97
        self.min_score_threshold = 0
        self.max_score_threshold = 100.0
        self.volume_lookback = 5
        self.volume_threshold = 2
        self.volume_return_limit = 1
        self.short_lookback_days = 10
        self.short_momentum_threshold = 0.0
        self.premium_threshold = 0.20
        self.intraday_drawdown_threshold = 0.02
        self.enable_premium_filter = False
        self.enable_volume_check = True
        self.use_short_momentum_filter = True
        self.profit_protection_threshold = 0.05
        self.profit_protection_lookback = 1

        # 状态
        self.rankings_cache = {'date': None, 'data': None}
        self.drawdown_selled_today = set()
        self.buy_date = {}
        self.trade_log = {'sell_records': []}
        self.high_prices = {}

    def _get_name(self, security):
        try:
            return get_current_data()[security].name
        except:
            return "未知"

    def _check_profit_protection(self, security, context):
        sp = context.subportfolios[self.pindex]
        pos = sp.positions.get(security)
        if pos is None or pos.total_amount == 0:
            return False
        hist = attribute_history(security, self.profit_protection_lookback, '1d', ['high'])
        if hist.empty or len(hist) < self.profit_protection_lookback:
            return False
        max_high = hist['high'].max()
        current_price = get_current_data()[security].last_price
        if current_price <= max_high * (1 - self.profit_protection_threshold):
            return True
        return False

    def _get_premium_rate(self, code, date):
        price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
        if price_data.empty:
            return None, None, None
        price = price_data['close'].iloc[0]
        net_value = None
        use_date = date
        for _ in range(3):
            net_data = get_extras('unit_net_value', code, start_date=use_date, end_date=use_date, df=True)
            if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
                net_value = net_data[code].iloc[0]
                break
            try:
                q = query(finance.FUND_NET_VALUE).filter(
                    finance.FUND_NET_VALUE.code == code,
                    finance.FUND_NET_VALUE.day == use_date
                )
                net_df = finance.run_query(q)
                if not net_df.empty:
                    net_value = net_df['net_value'].iloc[0]
                    break
            except:
                pass
            trade_days = get_trade_days(end_date=use_date, count=2)
            if len(trade_days) < 2:
                break
            use_date = trade_days[0]
        if net_value is None:
            return None, None, None
        premium_rate = (price - net_value) / net_value
        return premium_rate, price, net_value

    def _get_volume_ratio(self, security, context):
        hist = attribute_history(security, self.volume_lookback, '1d', ['volume'])
        if hist.empty or len(hist) < self.volume_lookback:
            return None
        avg_vol = hist['volume'].mean()
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        return ratio if ratio > self.volume_threshold else None

    def _get_annualized_returns(self, price_series, lookback_days):
        recent = price_series[-(lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, _ = np.polyfit(x, y, 1, w=weights)
        return math.exp(slope * 250) - 1

    def _calculate_momentum_metrics(self, etf, context):
        try:
            name = self._get_name(etf)
            lookback = max(self.lookback_days, self.short_lookback_days) + 20
            prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
            if len(prices) < self.lookback_days:
                return None, f"历史数据不足{len(prices)}天"
    
            current_price = get_current_data()[etf].last_price
            price_series = np.append(prices["close"].values, current_price)
    
            # 盈利保护
            if self._check_profit_protection(etf, context):
                return None, "触发盈利保护"
    
            # 溢价率过滤
            if self.enable_premium_filter:
                prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
                premium, _, _ = self._get_premium_rate(etf, prev_date)
                if premium is not None and premium > self.premium_threshold:
                    return None, f"溢价率{premium*100:.2f}%超阈值"
    
            # 成交量过滤
            if self.enable_volume_check:
                vol_ratio = self._get_volume_ratio(etf, context)
                if vol_ratio is not None:
                    annualized = self._get_annualized_returns(price_series, self.lookback_days)
                    if annualized > self.volume_return_limit:
                        return None, f"成交量放量 {vol_ratio:.2f}倍"
    
            # 短期动量过滤
            if len(price_series) >= self.short_lookback_days + 1:
                short_return = price_series[-1] / price_series[-(self.short_lookback_days + 1)] - 1
                short_annualized = (1 + short_return) ** (250 / self.short_lookback_days) - 1
            else:
                short_annualized = 0
            if self.use_short_momentum_filter and short_annualized < self.short_momentum_threshold:
                return None, f"短期年化{short_annualized*100:.2f}% < {self.short_momentum_threshold*100:.0f}%"
    
            # 长期动量
            recent = price_series[-(self.lookback_days + 1):]
            y = np.log(recent)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            annualized_returns = math.exp(slope * 250) - 1
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0
            score = annualized_returns * r_squared
    
            # 近3日跌幅过滤
            if len(price_series) >= 4:
                day1 = price_series[-1] / price_series[-2]
                day2 = price_series[-2] / price_series[-3]
                day3 = price_series[-3] / price_series[-4]
                if min(day1, day2, day3) < self.loss:
                    return None, f"近3日有单日跌幅超{self.loss*100:.0f}%"
    
            # 得分阈值
            if not (self.min_score_threshold < score < self.max_score_threshold):
                return None, f"得分{score:.4f}超出阈值"
    
            metrics = {
                'etf': etf,
                'etf_name': name,
                'annualized_returns': annualized_returns,
                'r_squared': r_squared,
                'score': score,
                'current_price': current_price,
                'short_annualized': short_annualized,
            }
            return metrics, "通过"
        except Exception as e:
            return None, f"异常: {str(e)[:50]}"

    def _get_cached_rankings(self, context):
        today = context.current_dt.date()
        if self.rankings_cache['date'] != today:
            active_pool = self.etf_pool
            ranked = []
            filtered_log = {}   # 收集过滤原因
            for etf in active_pool:
                if get_current_data()[etf].paused:
                    filtered_log[etf] = "停牌"
                    continue
                metrics, reason = self._calculate_momentum_metrics(etf, context)
                if metrics is not None and self.min_score_threshold < metrics['score'] < self.max_score_threshold:
                    ranked.append(metrics)
                else:
                    filtered_log[etf] = reason if reason else "得分不达标"
            ranked.sort(key=lambda x: x['score'], reverse=True)
            self.rankings_cache = {'date': today, 'data': ranked}
    
            # ===== 打印汇总日志，便于排查 =====
            log.info('[策略14] 排名计算完成，有效ETF %d只，过滤详情（前10）:' % len(ranked))
            for i, (etf, reason) in enumerate(list(filtered_log.items())[:10]):
                log.info('   %s: %s' % (etf, reason))
            if len(ranked) == 0:
                log.warning('[策略14] 无ETF入选，将进入防御模式')
            else:
                log.info('[策略14] 排名前3: %s' % [m['etf'] for m in ranked[:3]])
        return self.rankings_cache['data']

    def _check_intraday_drawdown(self, security, context):
        try:
            df = get_price(security, start_date=context.current_dt.date(), end_date=context.current_dt,
                           frequency='1m', fields=['high', 'close'], skip_paused=True, fq='pre')
            if df is None or df.empty:
                return False
            day_high = df['high'].max()
            current = df['close'].iloc[-1]
            if day_high <= 0:
                return False
            drawdown = (day_high - current) / day_high
            return drawdown >= self.intraday_drawdown_threshold
        except:
            return False

    def trade(self, context):
        sp = context.subportfolios[self.pindex]
        current_date = context.current_dt.date()
    
        # 每日开盘重置（用于当日回撤禁止买回）
        self.drawdown_selled_today = set()
        self.trade_log['sell_records'] = []
    
        # 获取排名
        ranked = self._get_cached_rankings(context)
        if ranked:
            log.info('[策略14] 排名前3: %s' % [m['etf'] for m in ranked[:3]])
    
        # 计算目标ETF列表
        target_etfs = []
        for m in ranked:
            if len(target_etfs) >= self.holdings_num:
                break
            etf = m['etf']
            if self._check_profit_protection(etf, context):
                continue
            if etf in self.drawdown_selled_today:
                continue
            if self._check_intraday_drawdown(etf, context):
                continue
            target_etfs.append(etf)
    
        # 防御模式
        defensive_available = not get_current_data()[self.defensive_etf].paused
        if not target_etfs and defensive_available and self.defensive_etf not in self.drawdown_selled_today:
            target_etfs = [self.defensive_etf]
            log.info('[策略14] 进入防御模式')
    
        # 当前所有持仓（排除货币ETF？策略14可能持有货币ETF作为现金管理，但这里简化：所有非目标都卖出）
        # 获取所有持仓（包括国债、ETF等）
        current_positions = list(sp.positions.keys())
        # 如果当前持仓中有任何不在目标中的，全部卖出
        for sec in current_positions:
            if sec not in target_etfs:
                pos = sp.positions.get(sec)
                if pos and pos.total_amount > 0:
                    log.info('[策略14] 卖出 %s' % sec)
                    self._order(sec, -pos.closeable_amount)
    
        # 买入目标（等权）
        if target_etfs:
            total_val = sp.total_value
            target_per = total_val / len(target_etfs)
            for etf in target_etfs:
                # 检查当前持仓（可能还有残留，但已被清空，所以可忽略）
                current_val = 0
                pos = sp.positions.get(etf)
                if pos:
                    current_val = pos.total_amount * pos.price
                # 如果差值较大或当前为0，则买入
                if abs(current_val - target_per) > target_per * 0.05 or current_val == 0:
                    price = get_current_data()[etf].last_price
                    if price is None or price <= 0:
                        continue
                    # 计算可买数量（向下取整到100股），但不能超过可用现金
                    max_shares = int(sp.available_cash // (price * 100) * 100)
                    target_shares = int(target_per // (price * 100) * 100)
                    shares = min(max_shares, target_shares)
                    if shares >= 100:
                        self._order(etf, shares)
                        self.buy_date[etf] = current_date
                        log.info('[策略14] 买入 %s %d股 金额%.2f' % (etf, shares, shares*price))
                    else:
                        log.info('[策略14] %s 资金不足或不满足最小单位，跳过 (需要%.2f元，可用%.2f元)' % (etf, target_per, sp.available_cash))
        else:
            # 无目标，若持有国债或货币则不动？但按逻辑应空仓（除了货币基金），但策略14没有货币基金持仓，所以可以空仓。
            # 但为了安全，不强制空仓，因为可能持有现金。
            log.info('[策略14] 无目标，保持空仓')


# ========== 主组合策略 ==========
def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('system', 'error')
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0003,
                             close_commission=0.0003, min_commission=5), type='stock')
    set_slippage(FixedSlippage(0.001))

# ---------- 仓位比例设置（可自由修改） ----------
    g.strategy_weights = [0.2, 0.2, 0.3, 0.3]  # 分别对应 策略11, 12, 13, 14
    
    total_cash = context.portfolio.starting_cash
    weights = np.array(g.strategy_weights) / np.sum(g.strategy_weights)
    
    # 创建3个子账户（策略12和13共享子账户1，实现资金自动流转）
    cash_0 = total_cash * weights[0]                     # 策略11
    cash_1 = total_cash * (weights[1] + weights[2])      # 策略12 + 13（共享）
    cash_2 = total_cash * weights[3]                     # 策略14
    
    set_subportfolios([
        SubPortfolioConfig(cash=cash_0, type='stock'),
        SubPortfolioConfig(cash=cash_1, type='stock'),
        SubPortfolioConfig(cash=cash_2, type='stock'),
    ])
    
    # 策略12在共享子账户中的目标权重（始终占账户1的 2/(2+3)=40%）
    s12_ratio = weights[1] / (weights[1] + weights[2]) if (weights[1] + weights[2]) > 0 else 0.4
    
    g.strategies = [
        Strategy11(0, cash_0),
        Strategy12(1, cash_1 * s12_ratio, s12_ratio),   # 传入目标权重
        Strategy13(1, cash_1 * (1 - s12_ratio)),        # 策略13自动适应剩余资金
        Strategy14(2, cash_2),
    ]

    run_daily(main_trade, time='14:50')

def main_trade(context):
    for st in g.strategies:
        try:
            st.trade(context)
        except Exception as e:
            log.error('[%s] 交易异常: %s' % (st.name, str(e)))