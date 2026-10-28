# Clone from JoinQuant
# postId: a40bc39b8dd63ebf4ecaf5b233f7fec7
# backtestId: f5c926776a065e530579413114282938
# title: 各位大神帮我看一下这个策略的问题在哪

# -*- coding: utf-8 -*-
"""
高股息低杠杆小市值轮动策略 V2.0
基于 V1.0 纯小市值策略，增加三重质量过滤：
  1. 高股息过滤：只保留股息率前 50%
  2. 低杠杆过滤：资产负债率 < 50%
  3. PB估值过滤：PB < 3

平台：聚宽(JoinQuant)
调仓：每周二 9:40
持仓：8只，等额分配
风控：止损12% + 涨停破板 + 1月/4月空仓
"""
from typing import Any, List, Dict, Optional
from datetime import datetime, timedelta

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd


# ============================================================
# 数据获取工具
# ============================================================
class DataHelper:

    @staticmethod
    def get_price_safe(
        security: Any,
        end_date: Any,
        frequency: str,
        fields: List[str],
        count: int,
        panel: bool = False,
        skip_paused: bool = True,
        fq: Optional[str] = None,
        fill_paused: bool = False
    ) -> Optional[pd.DataFrame]:
        try:
            df = get_price(
                security,
                end_date=end_date,
                frequency=frequency,
                fields=fields,
                count=count,
                panel=panel,
                skip_paused=skip_paused,
                fq=fq,
                fill_paused=fill_paused
            )
            return df
        except Exception as e:
            log.error(f"获取 {security} 的价格数据时出错: {e}")
            return None

    @staticmethod
    def get_history_safe(
        security: Any,
        unit: str,
        field: str,
        count: int
    ) -> Optional[Dict[str, List[float]]]:
        try:
            data = history(count, unit=unit, field=field, security_list=security)
            return data
        except Exception as e:
            log.error(f"获取 {security} 的历史数据时出错: {e}")
            return None


# ============================================================
# 主策略类
# ============================================================
class HighDivSmallCapStrategy:

    def __init__(self) -> None:
        # ---- 基础参数 ----
        self.stock_num: int = 8            # 持股数量
        self.up_price: float = 100.0       # 股价上限（几乎不过滤）

        # ---- 风控参数 ----
        self.stoploss_strategy: int = 3    # 止损策略：3=联合止损（大盘+个股）
        self.stoploss_limit: float = 0.88  # 个股止损线（亏12%就卖）
        self.stoploss_market: float = 0.94 # 大盘止损线
        self.pass_april: bool = True       # 1月+4月空仓开关
        self.HV_control: bool = False      # 异常放量检测（默认关闭）

        # ---- ★ 新增：质量过滤参数 ★ ----
        self.dividend_filter_enabled: bool = True    # 高股息过滤开关
        self.dividend_keep_ratio: float = 0.5        # 保留股息率前50%
        self.leverage_filter_enabled: bool = True    # 低杠杆过滤开关
        self.max_debt_ratio: float = 0.5             # 最大资产负债率50%
        self.pb_filter_enabled: bool = True           # PB估值过滤开关
        self.max_pb: float = 3.0                      # 最大PB = 3

        # ---- 运行状态 ----
        self.no_trading_today_signal: bool = False
        self.reason_to_sell: str = ''
        self.state: Dict[str, Any] = {
            'buy_signal': False,
            'sell_signal': False,
            'risk_level': 'normal'
        }

    def initialize(self, context: Any) -> None:
        set_option('avoid_future_data', True)
        set_benchmark('000001.XSHG')
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(3 / 10000))
        set_order_cost(OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=2.5 / 10000,
            close_commission=2.5 / 10000,
            close_today_commission=0,
            min_commission=5
        ), type='stock')
        log.set_level('order', 'error')
        log.set_level('system', 'error')
        log.set_level('strategy', 'debug')

    # ============================================================
    # ★ 新增：高股息过滤 ★
    # ============================================================
    def filter_by_dividend(self, stock_list: List[str], context: Any) -> List[str]:
        """
        只保留股息率最高的前 self.dividend_keep_ratio（默认50%）
        股息率 = 近一年每股分红总额 / 当前股价

        原理：能持续分红的公司，说明真的在赚钱，不是纯概念炒作
        """
        if not self.dividend_filter_enabled:
            return stock_list
        if len(stock_list) == 0:
            return stock_list

        try:
            # 查询过去一年的分红记录（除权除息表）
            one_year_ago = context.current_dt - timedelta(days=365)
            q_dividend = query(
                finance.STK_XR_XD.code,
                finance.STK_XR_XD.bonus_amount_rmb,
                finance.STK_XR_XD.ex_dividend_date
            ).filter(
                finance.STK_XR_XD.code.in_(stock_list),
                finance.STK_XR_XD.ex_dividend_date >= one_year_ago
            )
            df_div = finance.run_query(q_dividend)

            if df_div is None or df_div.empty:
                log.info("高股息过滤：过去一年无分红记录，保留全部候选股")
                return stock_list

            # 汇总每只股票近一年每股总分红
            div_sum = df_div.groupby('code')['bonus_amount_rmb'].sum().to_dict()

            # 获取当前股价，计算股息率
            current_data = get_current_data()
            yields = {}
            for stock in stock_list:
                total_div = div_sum.get(stock, 0)
                if total_div > 0 and stock in current_data:
                    price = current_data[stock].last_price
                    if price and price > 0:
                        yields[stock] = total_div / price  # 股息率

            # 如果没有可计算的股息率，保留全部
            if not yields:
                log.info("高股息过滤：无法计算股息率，保留全部候选股")
                return stock_list

            # 按股息率从高到低排序，保留前 keep_ratio
            sorted_stocks = sorted(yields.keys(), key=lambda s: yields[s], reverse=True)
            keep_count = max(1, int(len(sorted_stocks) * self.dividend_keep_ratio))
            kept = sorted_stocks[:keep_count]

            log.info(f"高股息过滤：{len(stock_list)} → {len(kept)} 只（保留前{int(self.dividend_keep_ratio*100)}%）")
            return kept

        except Exception as e:
            log.error(f"高股息过滤出错: {e}，跳过此过滤")
            return stock_list

    # ============================================================
    # ★ 新增：低杠杆过滤 ★
    # ============================================================
    def filter_by_leverage(self, stock_list: List[str], context: Any) -> List[str]:
        """
        只保留资产负债率低于 self.max_debt_ratio（默认50%）
        资产负债率 = 总负债 / 总资产

        原理：负债低的公司抗风险能力强，不容易暴雷退市
        """
        if not self.leverage_filter_enabled:
            return stock_list
        if len(stock_list) == 0:
            return stock_list

        try:
            q = query(
                balance.code,
                balance.total_assets,
                balance.total_liability
            ).filter(
                balance.code.in_(stock_list)
            )
            df = get_fundamentals(q, date=context.previous_date)

            if df is None or df.empty:
                log.info("低杠杆过滤：无法获取财务数据，保留全部")
                return stock_list

            kept = []
            for _, row in df.iterrows():
                assets = row.get('total_assets')
                liability = row.get('total_liability')
                if assets and assets > 0 and liability is not None:
                    debt_ratio = liability / assets
                    if debt_ratio <= self.max_debt_ratio:
                        kept.append(row['code'])
                        log.debug(f"股票 {row['code']} 资产负债率: {debt_ratio*100:.1f}%，通过")
                    else:
                        log.debug(f"股票 {row['code']} 资产负债率: {debt_ratio*100:.1f}%，超标排除")
                else:
                    # 数据不完整，保守保留
                    kept.append(row['code'])

            log.info(f"低杠杆过滤：{len(stock_list)} → {len(kept)} 只（资产负债率<{int(self.max_debt_ratio*100)}%）")
            return kept

        except Exception as e:
            log.error(f"低杠杆过滤出错: {e}，跳过此过滤")
            return stock_list

    # ============================================================
    # ★ 新增：PB估值过滤 ★
    # ============================================================
    def filter_by_pb(self, stock_list: List[str], context: Any) -> List[str]:
        """
        只保留市净率(PB) < self.max_pb 的股票（默认3倍）
        PB = 股价 / 每股净资产

        原理：PB太高意味着市场给了太多溢价，买贵了风险大
        """
        if not self.pb_filter_enabled:
            return stock_list
        if len(stock_list) == 0:
            return stock_list

        try:
            q = query(
                valuation.code,
                valuation.pb_ratio
            ).filter(
                valuation.code.in_(stock_list)
            )
            df = get_fundamentals(q, date=context.previous_date)

            if df is None or df.empty:
                log.info("PB过滤：无法获取估值数据，保留全部")
                return stock_list

            kept = []
            for _, row in df.iterrows():
                pb = row.get('pb_ratio')
                if pb is not None and pb < self.max_pb:
                    kept.append(row['code'])
                    log.debug(f"股票 {row['code']} PB: {pb:.2f}，通过")
                elif pb is not None:
                    log.debug(f"股票 {row['code']} PB: {pb:.2f}，超过限制{self.max_pb}排除")
                else:
                    kept.append(row['code'])  # 数据缺失保守保留

            log.info(f"PB过滤：{len(stock_list)} → {len(kept)} 只（PB<{self.max_pb}）")
            return kept

        except Exception as e:
            log.error(f"PB过滤出错: {e}，跳过此过滤")
            return stock_list

    # ============================================================
    # 原有六层过滤（保留自 V1.0）
    # ============================================================
    def filter_new_stock(self, context: Any, stock_list: List[str]) -> List[str]:
        """过滤上市不满375天的新股"""
        yesterday = context.previous_date
        return [stock for stock in stock_list
                if not (yesterday - get_security_info(stock).start_date < timedelta(days=375))]

    def filter_kcbj_stock(self, stock_list: List[str]) -> List[str]:
        """过滤科创板和北交所"""
        return [stock for stock in stock_list
                if stock[0] not in ('4', '8') and not stock.startswith('68')]

    def filter_st_stock(self, stock_list: List[str]) -> List[str]:
        """过滤ST股"""
        current_data = get_current_data()
        return [stock for stock in stock_list
                if (not current_data[stock].is_st)
                and ('ST' not in current_data[stock].name)
                and ('*' not in current_data[stock].name)
                and ('退' not in current_data[stock].name)]

    def filter_paused_stock(self, stock_list: List[str]) -> List[str]:
        """过滤停牌股"""
        current_data = get_current_data()
        return [stock for stock in stock_list if not current_data[stock].paused]

    def filter_limitup_stock(self, context: Any, stock_list: List[str]) -> List[str]:
        """过滤涨停股"""
        history_data = DataHelper.get_history_safe(stock_list, unit='1m', field='close', count=1)
        current_data = get_current_data()
        if history_data is None:
            return stock_list
        return [stock for stock in stock_list
                if stock in context.portfolio.positions.keys()
                or (history_data.get(stock, [0])[-1] < current_data[stock].high_limit)]

    def filter_limitdown_stock(self, context: Any, stock_list: List[str]) -> List[str]:
        """过滤跌停股"""
        history_data = DataHelper.get_history_safe(stock_list, unit='1m', field='close', count=1)
        current_data = get_current_data()
        if history_data is None:
            return stock_list
        return [stock for stock in stock_list
                if stock in context.portfolio.positions.keys()
                or (history_data.get(stock, [float('inf')])[-1] > current_data[stock].low_limit)]

    # ============================================================
    # 核心选股流程（★ 关键修改：在市值排序前增加质量过滤）
    # ============================================================
    def get_stock_list(self, context: Any) -> List[str]:
        """
        完整选股流程：
        1. 获取中小板指数成分股
        2. 六层安全过滤（新股/KCB/ST/停牌/涨停/跌停）
        3. ★ 高股息过滤（新增）
        4. ★ 低杠杆过滤（新增）
        5. ★ PB估值过滤（新增）
        6. 按市值从小到大排序
        7. 取前 2*stock_num 只作为候选池
        """
        # 第1步：股票池
        MKT_index: str = '399101.XSHE'  # 中小板综合指数
        initial_list: List[str] = get_index_stocks(MKT_index)

        # 第2步：六层安全过滤
        initial_list = self.filter_new_stock(context, initial_list)
        initial_list = self.filter_kcbj_stock(initial_list)
        initial_list = self.filter_st_stock(initial_list)
        initial_list = self.filter_paused_stock(initial_list)
        initial_list = self.filter_limitup_stock(context, initial_list)
        initial_list = self.filter_limitdown_stock(context, initial_list)

        log.info(f"六层过滤后剩余: {len(initial_list)} 只")

        # 第3步：★ 高股息过滤
        initial_list = self.filter_by_dividend(initial_list, context)

        # 第4步：★ 低杠杆过滤
        initial_list = self.filter_by_leverage(initial_list, context)

        # 第5步：★ PB估值过滤
        initial_list = self.filter_by_pb(initial_list, context)

        log.info(f"质量过滤后剩余: {len(initial_list)} 只")

        # 第6步：按市值从小到大排序
        if len(initial_list) == 0:
            log.warning("过滤后无可用股票！")
            return []

        q = query(valuation.code, indicator.eps) \
            .filter(valuation.code.in_(initial_list)) \
            .order_by(valuation.market_cap.asc())
        df = get_fundamentals(q)
        stock_list: List[str] = list(df.code)

        # 第7步：取前 2倍持股数 作为候选池
        final_list: List[str] = stock_list[:min(2 * self.stock_num, len(stock_list))]
        log.info(f"初选候选股票: {final_list}")

        # 打印候选池的财务信息（方便复盘）
        if final_list:
            info_query = query(
                valuation.code,
                valuation.pb_ratio,
                income.pubDate,
                income.statDate,
                income.operating_revenue,
                indicator.eps
            ).filter(valuation.code.in_(final_list))
            df_info = get_fundamentals(info_query)
            for _, row in df_info.iterrows():
                log.info(
                    f"股票 {row['code']}："
                    f"PB {row.get('pb_ratio', 'N/A')}，"
                    f"报告日期 {row.get('pubDate', 'N/A')}，"
                    f"营业收入 {row.get('operating_revenue', 'N/A')}，"
                    f"EPS {row.get('eps', 'N/A')}"
                )

        return final_list

    # ============================================================
    # 以下功能保留自 V1.0，未修改
    # ============================================================

    def prepare_stock_list(self, context: Any) -> None:
        """准备每日持仓清单"""
        g.hold_list = [position.security for position in list(context.portfolio.positions.values())]
        if g.hold_list:
            df = DataHelper.get_price_safe(
                g.hold_list,
                end_date=context.previous_date,
                frequency='daily',
                fields=['close', 'high_limit', 'low_limit'],
                count=1,
                panel=False,
                fill_paused=False
            )
            if df is not None and not df.empty:
                g.yesterday_HL_list = list(df[df['close'] == df['high_limit']]['code'])
            else:
                g.yesterday_HL_list = []
        else:
            g.yesterday_HL_list = []

        self.no_trading_today_signal = self.today_is_between(context)

    def check_holdings_yesterday(self, context: Any) -> None:
        """检查昨日持仓"""
        positions = context.portfolio.positions
        if not positions:
            log.info("昨日没有持仓数据。")
            return
        log.info("== 昨日持仓股票交易数据 ==")
        for stock, position in positions.items():
            try:
                df = DataHelper.get_price_safe(
                    stock,
                    end_date=context.previous_date,
                    frequency="daily",
                    fields=['open', 'close'],
                    count=1,
                    panel=False
                )
                if df is None or df.empty:
                    continue
                open_price: float = df.iloc[0]['open']
                close_price: float = df.iloc[0]['close']
                change_pct: float = (close_price / open_price - 1) * 100
                log.info(
                    f"股票 {stock}：持仓 {position.total_amount} 股，"
                    f"开盘 {open_price:.2f}，收盘 {close_price:.2f}，涨跌幅 {change_pct:.2f}%"
                )
            except Exception as e:
                log.error(f"处理股票 {stock} 数据时出错: {e}")

    def weekly_adjustment(self, context: Any) -> None:
        """每周二调仓（核心操作）"""
        if not self.no_trading_today_signal:
            g.not_buy_again = []

            g.target_list = self.get_stock_list(context)
            target_list: List[str] = g.target_list[:self.stock_num]
            log.info(f"每周调仓目标股票: {target_list}")

            # 卖出不在目标池中的股票
            for stock in g.hold_list:
                if stock not in target_list and stock not in g.yesterday_HL_list:
                    log.info(f"卖出股票 {stock}")
                    position = context.portfolio.positions[stock]
                    self.close_position(position)
                else:
                    log.info(f"继续持有股票 {stock}")

            # 买入新目标
            self.buy_security(context, target_list)

            # 记录已买入的，当日不重复买
            for position in list(context.portfolio.positions.values()):
                if position.security not in g.not_buy_again:
                    g.not_buy_again.append(position.security)

    def sell_stocks(self, context: Any) -> None:
        """止损检查（每天10:00）"""
        if self.stoploss_strategy == 3:
            # 联合止损：先检查大盘
            stock_list = get_index_stocks('399101.XSHE')
            df = DataHelper.get_price_safe(
                stock_list,
                end_date=context.previous_date,
                frequency='daily',
                fields=['close', 'open'],
                count=1,
                panel=False
            )
            if df is not None and not df.empty:
                down_ratio = (df['close'] / df['open']).mean()
                if down_ratio <= self.stoploss_market:
                    self.reason_to_sell = 'stoploss'
                    log.debug(f"大盘跌幅达到 {down_ratio:.2%}，执行平仓操作。")
                    for stock in list(context.portfolio.positions.keys()):
                        order_target_value(stock, 0)
                else:
                    # 大盘没触发，逐个检查个股
                    for stock in list(context.portfolio.positions.keys()):
                        pos = context.portfolio.positions[stock]
                        if pos.price < pos.avg_cost * self.stoploss_limit:
                            order_target_value(stock, 0)
                            log.debug(f"股票 {stock} 触及止损线，执行卖出。")
                            self.reason_to_sell = 'stoploss'

    def check_limit_up(self, context: Any) -> None:
        """涨停破板检查"""
        now_time = context.current_dt
        if g.yesterday_HL_list:
            for stock in g.yesterday_HL_list:
                current_data = DataHelper.get_price_safe(
                    stock,
                    end_date=now_time,
                    frequency='1m',
                    fields=['close', 'high_limit'],
                    count=1,
                    panel=False,
                    fill_paused=True
                )
                if current_data is not None and not current_data.empty:
                    if current_data.iloc[0]['close'] < current_data.iloc[0]['high_limit']:
                        log.info(f"股票 {stock} 涨停破板，执行卖出。")
                        position = context.portfolio.positions[stock]
                        self.close_position(position)
                        self.reason_to_sell = 'limitup'

    def check_remain_amount(self, context: Any) -> None:
        """涨停破板后补仓"""
        if self.reason_to_sell == 'limitup':
            g.hold_list = [position.security for position in list(context.portfolio.positions.values())]
            if len(g.hold_list) < self.stock_num:
                target_list = self.filter_not_buy_again(g.target_list)
                target_list = target_list[:min(self.stock_num, len(target_list))]
                log.info(f"补仓需求：可用资金 {round(context.portfolio.cash, 2)}，候选补仓股票: {target_list}")
                self.buy_security(context, target_list)
                self.reason_to_sell = ''
            else:
                log.info("未检测到需要补仓的情况。")

    def trade_afternoon(self, context: Any) -> None:
        """下午交易"""
        if not self.no_trading_today_signal:
            self.check_limit_up(context)
            self.check_remain_amount(context)

    def today_is_between(self, context: Any) -> bool:
        """判断是否为空仓日（1月+4月）"""
        today_str = context.current_dt.strftime('%m-%d')
        if self.pass_april:
            if ('04-01' <= today_str <= '04-30') or ('01-01' <= today_str <= '01-30'):
                return True
            else:
                return False
        else:
            return False

    def close_account(self, context: Any) -> None:
        """空仓日清仓"""
        if self.no_trading_today_signal:
            if g.hold_list:
                for stock in g.hold_list:
                    position = context.portfolio.positions[stock]
                    self.close_position(position)
                    log.info(f"空仓日平仓，卖出股票 {stock}。")

    def filter_not_buy_again(self, stock_list: List[str]) -> List[str]:
        """过滤当日已买入的股票"""
        return [stock for stock in stock_list if stock not in g.not_buy_again]

    def order_target_value_(self, security: str, value: float) -> Any:
        """下单"""
        if value != 0:
            log.debug(f"正在为 {security} 下单，目标金额 {value}")
        try:
            order = order_target_value(security, value)
            return order
        except Exception as e:
            log.error(f"股票 {security} 下单时出错，目标金额 {value}，错误信息: {e}")
            return None

    def open_position(self, security: str, value: float) -> bool:
        """开仓"""
        order = self.order_target_value_(security, value)
        if order is not None and order.filled > 0:
            return True
        return False

    def close_position(self, position: Any) -> bool:
        """平仓"""
        security = position.security
        order = self.order_target_value_(security, 0)
        if order is not None and order.status == OrderStatus.held and order.filled == order.amount:
            return True
        return False

    def buy_security(self, context: Any, target_list: List[str]) -> None:
        """买入股票"""
        position_count = len(context.portfolio.positions)
        target_num = len(target_list)
        if target_num > position_count:
            try:
                value = context.portfolio.cash / (target_num - position_count)
            except ZeroDivisionError as e:
                log.error(f"资金分摊时除零错误: {e}")
                return
            for stock in target_list:
                if context.portfolio.positions[stock].total_amount == 0:
                    if self.open_position(stock, value):
                        log.info(f"已买入股票 {stock}，分配资金 {value:.2f}")
                        g.not_buy_again.append(stock)
                    if len(context.portfolio.positions) == target_num:
                        break

    def print_position_info(self, context: Any) -> None:
        """打印持仓信息"""
        for position in list(context.portfolio.positions.values()):
            securities: str = position.security
            cost: float = position.avg_cost
            price: float = position.price
            ret: float = 100 * (price / cost - 1)
            value: float = position.value
            amount: int = position.total_amount
            print(f"股票: {securities}")
            print(f"成本价: {cost:.2f}")
            print(f"现价: {price:.2f}")
            print(f"涨跌幅: {ret:.2f}%")
            print(f"持仓: {amount}")
            print(f"市值: {value:.2f}")
            print("--------------------------------------")
        print("********** 持仓信息打印结束 **********")


# ============================================================
# 定时任务调度函数
# ============================================================
strategy = HighDivSmallCapStrategy()

def prepare_stock_list_func(context: Any) -> None:
    strategy.prepare_stock_list(context)

def check_holdings_yesterday_func(context: Any) -> None:
    strategy.check_holdings_yesterday(context)

def weekly_adjustment_func(context: Any) -> None:
    strategy.weekly_adjustment(context)

def sell_stocks_func(context: Any) -> None:
    strategy.sell_stocks(context)

def trade_afternoon_func(context: Any) -> None:
    strategy.trade_afternoon(context)

def close_account_func(context: Any) -> None:
    strategy.close_account(context)

def print_position_info_func(context: Any) -> None:
    strategy.print_position_info(context)


# ============================================================
# 初始化入口
# ============================================================
def initialize(context: Any) -> None:
    # 全局变量
    g.hold_list: List[str] = []
    g.yesterday_HL_list: List[str] = []
    g.target_list: List[str] = []
    g.not_buy_again: List[str] = []

    strategy.initialize(context)

    # 定时任务
    run_daily(prepare_stock_list_func, time='9:05')
    run_daily(check_holdings_yesterday_func, time='9:00')
    run_weekly(weekly_adjustment_func, 2, time='9:40')      # 周二调仓
    run_daily(sell_stocks_func, time='10:00')                # 止损检查
    run_daily(trade_afternoon_func, time='14:30')            # 下午交易
    run_daily(close_account_func, time='14:50')              # 空仓日清仓
    run_weekly(print_position_info_func, 5, time='15:10')   # 周五打印持仓


# ============================================================
# 代码修改后重置
# ============================================================
def after_code_changed(context):
    g.hold_list: List[str] = []
    g.yesterday_HL_list: List[str] = []
    g.target_list: List[str] = []
    g.not_buy_again: List[str] = []

