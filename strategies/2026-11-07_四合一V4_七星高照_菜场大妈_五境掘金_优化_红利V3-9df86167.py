# Clone from JoinQuant
# postId: 9df861671b8e8049016bc77b56712de3
# backtestId: 739790c5960a2504f7cbe7214a04f777
# title: 四合一V4：七星高照+菜场大妈+五境掘金[优化]+红利V3

# ==================== 组合策略（整合11、12、13、14） ====================
import numpy as np
import pandas as pd
from jqdata import *
import datetime
from datetime import time
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


# ========== 策略11：微盘股指数择时（原a.txt） ==========
class Strategy11(BaseStrategy):
    def __init__(self, pindex, initial_cash):
        super().__init__('微盘股择时', pindex, initial_cash)

        # ── 基础参数 ──
        self.stock_num = 10
        self.choice = []
        self.just_sold_dict = {}
        self.just_sold_list = []
        self.clear_just_sold_cycle = 12
        self.ma_day_1 = 10
        self.ma_day_2 = 26
        self.pass_month = []
        self.min_mv = 10          # 市值下限（亿元）
        self.max_mv = 100         # 市值上限（亿元）
        self.sell_limit = 1.27    # 止盈27%
        self.buy_limit = 1.1      # 买入条件：股价 ≤ 均线×1.1
        self.loss_percent = 0.15  # 止损15%
        self.low_price = 2
        self.high_price = 10.0
        self.high_price_multiplier = 0.8

        # ── 微盘股指数参数 ──
        self.n_stocks = 200
        self.initial_index_value = 1000.0
        self.ema_period = 26

        # ── 回撤深度档位 ──
        self.dd_thresholds = [-0.06, -0.12, -0.20]   # -6%, -12%, -20%

        # ── 通道仓位状态 ──
        self.channel_position = 0.0
        self.index_series = []          # 半日频指数数据列表
        self.index_components = None
        self.prev_pm_close = None
        self.prev_pm_close_avg = None
        self.current_index_value = None
        self.last_rebalance_month = None

        # ── 回撤状态 ──
        self.drawdown_cycles = []
        self.current_drawdown = 0.0
        self.running_max = None
        self.in_drawdown_cycle = False
        self.current_cycle_max_dd = 0.0

        # ── EMA通道日志 ──
        self.latest_ema_upper = 0.0
        self.latest_ema_lower = 0.0
        self.latest_zone = -1
        self.channel_trigger_reason = 'base'

        # ── 信号执行状态 ──
        self.pending_signal = None

        # ── 其它临时变量 ──
        self.am_close_today = None
        self.am_close_avg_today = None
        self.high_limit_list = []

        # 预热将在外部调用 warmup
        self.is_warmed = False

    # ---------- 预热 ----------
    def warmup(self, context):
        """回溯2个月历史数据构建初始指数序列"""
        if self.is_warmed:
            return
#        log.info("[策略11预热] 开始回溯2个月历史数据计算微盘股指数...")
        today = context.current_dt.date()
        start_date = today - datetime.timedelta(days=75)
        start_str = start_date.strftime('%Y-%m-%d')
        trading_days = list(get_trade_days(start_date=start_str, end_date=today.strftime('%Y-%m-%d')))
        if len(trading_days) < 5:
#            log.warn("[策略11预热] 交易日不足，跳过")
            self.current_index_value = self.initial_index_value
            self.is_warmed = True
            return

        current_value = self.initial_index_value
        current_components = None
        prev_pm_close = None
        prev_pm_close_avg = None
        last_month = None
        warmup_data = []

        for i, date in enumerate(trading_days):
            if date == today:
                continue
            date_str = date.strftime('%Y-%m-%d')
            current_month = date.month
            if current_month != last_month or current_components is None:
                prev_date_str = trading_days[i-1].strftime('%Y-%m-%d') if i > 0 else date_str
                components = self._get_components_by_date(prev_date_str, self.n_stocks)
                if components:
                    current_components = components
                    last_month = current_month
                    if i > 0 and prev_date_str != date_str:
                        _, prev_pm, _ = self._get_halfday_prices(current_components, prev_date_str, is_today=False)
                        if prev_pm is not None and not prev_pm.empty:
                            prev_pm_close = prev_pm['close']
                            prev_pm_close_avg = prev_pm['close'].mean()

            if not current_components:
                continue

            am_data, pm_data, success = self._get_halfday_prices(current_components, date_str, is_today=False)
            if not success:
                continue

            am_close = am_data['close'] if am_data is not None else None
            pm_close = pm_data['close'] if pm_data is not None else None

            def _avg(df, field):
                return df[field].mean() if df is not None and not df.empty else np.nan

            am_ohlc_avg = {'open': _avg(am_data, 'open'), 'high': _avg(am_data, 'high'),
                           'low': _avg(am_data, 'low'), 'close': _avg(am_data, 'close')}
            pm_ohlc_avg = {'open': _avg(pm_data, 'open'), 'high': _avg(pm_data, 'high'),
                           'low': _avg(pm_data, 'low'), 'close': _avg(pm_data, 'close')}

            # AM
            am_ret, am_valid, new_val = self._calc_one_bar_close(current_components, am_close, prev_pm_close, current_value)
            am_val_before = current_value
            current_value = new_val
            am_ohlc_o = am_ohlc_h = am_ohlc_l = np.nan
            if prev_pm_close_avg is not None and not np.isnan(prev_pm_close_avg) and prev_pm_close_avg > 0:
                base = prev_pm_close_avg
                am_ohlc_o = am_val_before * (1 + (am_ohlc_avg['open'] - base) / base)
                am_ohlc_h = am_val_before * (1 + (am_ohlc_avg['high'] - base) / base)
                am_ohlc_l = am_val_before * (1 + (am_ohlc_avg['low'] - base) / base)
            warmup_data.append({
                'datetime': pd.Timestamp(f"{date_str} 11:30:00"),
                'date': date,
                'session': 'AM',
                'ohlc_open': am_ohlc_o, 'ohlc_high': am_ohlc_h,
                'ohlc_low': am_ohlc_l, 'ohlc_close': current_value,
            })

            # PM
            pm_ret, pm_valid, new_val = self._calc_one_bar_close(current_components, pm_close, am_close, current_value)
            pm_val_before = current_value
            current_value = new_val
            pm_ohlc_o = pm_ohlc_h = pm_ohlc_l = np.nan
            am_close_avg = am_ohlc_avg['close']
            if am_close_avg is not None and not np.isnan(am_close_avg) and am_close_avg > 0:
                base = am_close_avg
                pm_ohlc_o = pm_val_before * (1 + (pm_ohlc_avg['open'] - base) / base)
                pm_ohlc_h = pm_val_before * (1 + (pm_ohlc_avg['high'] - base) / base)
                pm_ohlc_l = pm_val_before * (1 + (pm_ohlc_avg['low'] - base) / base)
            warmup_data.append({
                'datetime': pd.Timestamp(f"{date_str} 15:00:00"),
                'date': date,
                'session': 'PM',
                'ohlc_open': pm_ohlc_o, 'ohlc_high': pm_ohlc_h,
                'ohlc_low': pm_ohlc_l, 'ohlc_close': current_value,
            })

            prev_pm_close = pm_close
            prev_pm_close_avg = pm_ohlc_avg['close']

            if (i+1) % 20 == 0:
                log.info(f"[策略11预热] 已处理 {i+1}/{len(trading_days)} 个交易日，指数={current_value:.2f}")

        self.index_series = warmup_data
        self.index_components = current_components
        self.prev_pm_close = prev_pm_close
        self.prev_pm_close_avg = prev_pm_close_avg
        self.current_index_value = current_value
        self.last_rebalance_month = last_month if last_month is not None else today.month

        self._calc_drawdown()
        self._identify_drawdown_cycles()
        log.info(f"[策略11预热] 识别到 {len(self.drawdown_cycles)} 个回撤周期")
        self._update_channel_and_position()
        log.info(f"[策略11预热] 完成，共{len(warmup_data)}根bar，指数={current_value:.2f}，仓位={self.channel_position:.0%}")
        self.is_warmed = True

    # ---------- 指数计算辅助 ----------
    def _get_components_by_date(self, date_str, n_stocks):
        all_stocks_info = get_all_securities(['stock'])
        q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(all_stocks_info.index))
        market_cap_df = get_fundamentals(q, date=date_str)
        if market_cap_df is None or market_cap_df.empty:
            return []
        market_cap_df = market_cap_df.dropna(subset=['market_cap'])
        current_date = pd.to_datetime(date_str)
        three_months_ago = current_date - pd.DateOffset(months=3)
        valid_codes = []
        for code in market_cap_df['code']:
            try:
                info = all_stocks_info.loc[code]
                start_date = pd.to_datetime(info['start_date'])
                name = info['display_name']
                if start_date > three_months_ago or '退' in name:
                    continue
                valid_codes.append(code)
            except:
                continue
        market_cap_df = market_cap_df[market_cap_df['code'].isin(valid_codes)]
        market_cap_df = market_cap_df.sort_values('market_cap', ascending=True)
        return market_cap_df.head(n_stocks)['code'].tolist()

    def _get_halfday_prices(self, components, date_str, is_today=False, context=None):
        if not components:
            log.warn(f"[DEBUG] components为空, date={date_str}")
            return None, None, False
    
        date_obj = pd.to_datetime(date_str)
        log.info(f"[DEBUG] _get_halfday_prices: date={date_str}, is_today={is_today}, 成分股={len(components)}")
    
        if is_today:
            if context is None:
                log.error("[DEBUG] 当日模式需传入context")
                return None, None, False
            log.info(f"[DEBUG] 当日模式，用get_price获取分钟数据至 {context.current_dt}")
            try:
                # 获取 open, high, low, close
                pdf = get_price(components, end_date=context.current_dt, frequency='1m',
                                count=240, fields=['open','high','low','close'], skip_paused=False, panel=False)
                if pdf is None or pdf.empty:
                    log.warn(f"[DEBUG] get_price返回空")
                    return None, None, False
                pdf['time'] = pd.to_datetime(pdf['time'])
                day_df = pdf[pdf['time'].dt.date == date_obj.date()]
                if day_df.empty:
                    log.warn(f"[DEBUG] 当日无分钟数据")
                    return None, None, False
    
                am_df = day_df[(day_df['time'].dt.time >= datetime.time(9,30)) & (day_df['time'].dt.time <= datetime.time(11,30))]
                pm_df = day_df[(day_df['time'].dt.time >= datetime.time(13,0)) & (day_df['time'].dt.time <= datetime.time(15,0))]
                log.info(f"[DEBUG] AM数据{len(am_df)}行, PM数据{len(pm_df)}行")
    
                # 聚合：open取第一个，high取最大，low取最小，close取最后一个
                am_result = am_df.groupby('code').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last'
                }) if not am_df.empty else None
    
                pm_result = pm_df.groupby('code').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last'
                }) if not pm_df.empty else None
    
                success = (am_result is not None or pm_result is not None)
                log.info(f"[DEBUG] 聚合完成 AM:{len(am_result) if am_result is not None else 0}只 PM:{len(pm_result) if pm_result is not None else 0}只")
                return am_result, pm_result, success
            except Exception as e:
                log.error(f"[DEBUG] 当日异常: {str(e)}")
                return None, None, False
    
        else:
            # ---------- 历史模式 ----------
            # 跳过今日数据，避免 avoid_future_data
            if date_obj.date() == datetime.datetime.now().date():
                log.warn(f"[DEBUG] 历史模式跳过今日 {date_str}")
                return None, None, False
    
            log.info(f"[DEBUG] 历史模式，获取120m K线: {date_str}")
            start_ext = (date_obj - pd.Timedelta(days=1)).strftime('%Y-%m-%d') + ' 09:00:00'
            end_ext = date_str + ' 15:10:00'
            all_am, all_pm = [], []
            batch_size = 100
            fields = ['open', 'high', 'low', 'close', 'volume']
    
            for i in range(0, len(components), batch_size):
                batch = components[i:i+batch_size]
                try:
                    pdf = get_price(batch, start_date=start_ext, end_date=end_ext,
                                    frequency='120m', fields=fields, skip_paused=False, panel=False)
                    if pdf is None or pdf.empty:
                        continue
                    pdf['time'] = pd.to_datetime(pdf['time'])
                    day_df = pdf[pdf['time'].dt.date == date_obj.date()]
                    if day_df.empty:
                        continue
                    am_bar = day_df[(day_df['time'].dt.hour == 11) & (day_df['time'].dt.minute == 30)]
                    pm_bar = day_df[(day_df['time'].dt.hour == 15) & (day_df['time'].dt.minute == 0)]
                    if am_bar.empty or pm_bar.empty:
                        times = sorted(day_df['time'].unique())
                        if am_bar.empty and len(times) >= 1:
                            am_bar = day_df[day_df['time'] == times[0]]
                        if pm_bar.empty and len(times) >= 2:
                            pm_bar = day_df[day_df['time'] == times[1]]
                    if not am_bar.empty:
                        all_am.append(am_bar.set_index('code')[fields])
                    if not pm_bar.empty:
                        all_pm.append(pm_bar.set_index('code')[fields])
                except Exception as e:
                    log.error(f"[DEBUG] 批次异常: {str(e)}")
                    continue
    
            am_result = pd.concat(all_am) if all_am else None
            pm_result = pd.concat(all_pm) if all_pm else None
            success = (am_result is not None or pm_result is not None)
            log.info(f"[DEBUG] 历史完成 AM:{len(am_result) if am_result is not None else 0}行 PM:{len(pm_result) if pm_result is not None else 0}行")
            return am_result, pm_result, success

    def _calc_one_bar_close(self, components, close_data, prev_close_data, current_value):
        bar_return = 0.0
        if close_data is not None and prev_close_data is not None:
            common = close_data.index.intersection(prev_close_data.index)
            if len(common) > 0:
                rets = (close_data.loc[common] - prev_close_data.loc[common]) / prev_close_data.loc[common]
                rets = rets.replace([np.inf, -np.inf], np.nan).dropna()
                if len(rets) > 0:
                    bar_return = rets.mean()
        new_value = current_value * (1 + bar_return)
        return bar_return, len(rets) if 'rets' in locals() else 0, new_value

    # ---------- 回撤计算 ----------
    def _calc_drawdown(self):
        if not self.index_series:
            return
        running_max = self.index_series[0]['ohlc_close']
        self.index_series[0]['running_max'] = running_max
        self.index_series[0]['drawdown'] = 0.0
        for i in range(1, len(self.index_series)):
            close = self.index_series[i]['ohlc_close']
            if close > running_max:
                running_max = close
            dd = (close - running_max) / running_max if running_max > 0 else 0.0
            self.index_series[i]['running_max'] = running_max
            self.index_series[i]['drawdown'] = dd
        self.running_max = running_max
        self.current_drawdown = self.index_series[-1]['drawdown']

    def _identify_drawdown_cycles(self):
        self.drawdown_cycles = []
        if not self.index_series:
            return
        in_dd = False
        dd_start_idx = 0
        max_dd = 0.0
        for idx, rec in enumerate(self.index_series):
            dd = rec['drawdown']
            if dd < 0 and not in_dd:
                in_dd = True
                dd_start_idx = idx
                max_dd = dd
            elif dd < max_dd and in_dd:
                max_dd = dd
            elif dd >= -1e-9 and in_dd:
                in_dd = False
                self.drawdown_cycles.append({
                    'start_idx': dd_start_idx, 'end_idx': idx,
                    'max_drawdown': max_dd,
                    'start_dt': self.index_series[dd_start_idx]['datetime'],
                    'end_dt': self.index_series[idx]['datetime'],
                })
        if in_dd:
            self.drawdown_cycles.append({
                'start_idx': dd_start_idx, 'end_idx': len(self.index_series)-1,
                'max_drawdown': max_dd,
                'start_dt': self.index_series[dd_start_idx]['datetime'],
                'end_dt': self.index_series[-1]['datetime'],
            })

    def _get_drawdown_zone(self, current_dd):
        thresholds = self.dd_thresholds
        sell_keeps = [0.0, 1.0/3, 2.0/3, 1.0]
        buy_targets = [1.0/3, 2.0/3, 1.0, 1.0]
        if current_dd >= thresholds[0]:
            zone = 0
        elif current_dd >= thresholds[1]:
            zone = 1
        elif current_dd >= thresholds[2]:
            zone = 2
        else:
            zone = 3
        return zone, sell_keeps[zone], buy_targets[zone]

    def _calc_base_ema_position(self, close_array, upper_array, lower_array):
        n = len(close_array)
        if n == 0:
            return 0.0
        pos = 0.0
        for i in range(n):
            c = close_array[i]
            if c > upper_array[i]:
                pos = 1.0
            elif c < lower_array[i]:
                pos = 0.0
        return pos

    def _calc_target_position_in_dd(self, close, upper, lower, current_dd, old_pos):
        zone, sell_keep, buy_target = self._get_drawdown_zone(current_dd)
        new_pos = old_pos
        trigger_reason = 'base'
        if close > upper:
            new_pos = 1.0
            trigger_reason = 'upper'
        if close < lower:
            new_pos = sell_keep
            trigger_reason = 'lower'
        return new_pos, zone, trigger_reason

    def _update_channel_and_position(self):
        if len(self.index_series) < 5:
            return
        df = pd.DataFrame(self.index_series)
        close = df['ohlc_close'].values
        upper = df['ohlc_high'].ewm(span=self.ema_period, adjust=False).mean().values
        lower = df['ohlc_low'].ewm(span=self.ema_period, adjust=False).mean().values
        c_cur = close[-1]
        upper_cur = upper[-1]
        lower_cur = lower[-1]
        old_pos = self.channel_position
        self.current_drawdown = df['drawdown'].iloc[-1] if 'drawdown' in df.columns else 0.0
        self.running_max = df['running_max'].iloc[-1] if 'running_max' in df.columns else c_cur
        self.in_drawdown_cycle = self.current_drawdown < 0
        if self.in_drawdown_cycle:
            new_pos, zone, trigger_reason = self._calc_target_position_in_dd(
                c_cur, upper_cur, lower_cur, self.current_drawdown, old_pos
            )
            self.current_cycle_max_dd = min(self.current_cycle_max_dd, self.current_drawdown)
        else:
            new_pos = self._calc_base_ema_position(close, upper, lower)
            self.current_cycle_max_dd = 0.0
            if c_cur > upper_cur:
                trigger_reason = 'upper'
            elif c_cur < lower_cur:
                trigger_reason = 'lower'
            else:
                trigger_reason = self.channel_trigger_reason
        self.channel_position = new_pos
        self.channel_trigger_reason = trigger_reason
        self.latest_ema_upper = upper_cur
        self.latest_ema_lower = lower_cur
        self.latest_zone = zone if self.in_drawdown_cycle else -1

    # ---------- 定时任务（由外部调度） ----------
    def update_index_am(self, context):
        if not self.is_warmed:
            self.warmup(context)
            return
        today_str = context.current_dt.strftime('%Y-%m-%d')
        current_month = context.current_dt.month
    
        log.info(f"[DEBUG-AM] 开始 update_index_am, today={today_str}, 成分股={len(self.index_components) if self.index_components else 0}")
    
        # 月初调仓
        if current_month != self.last_rebalance_month or self.index_components is None:
            log.info(f"[DEBUG-AM] 触发月初调仓: current_month={current_month}, last={self.last_rebalance_month}")
            trading_days = list(get_trade_days(end_date=today_str, count=2))
            prev_date_str = trading_days[-2].strftime('%Y-%m-%d') if len(trading_days)>=2 else today_str
            components = self._get_components_by_date(prev_date_str, self.n_stocks)
            if components:
                self.index_components = components
                self.last_rebalance_month = current_month
                if prev_date_str != today_str:
                    log.info(f"[DEBUG-AM] 获取前一日PM数据: {prev_date_str}")
                    _, prev_pm, _ = self._get_halfday_prices(self.index_components, prev_date_str, is_today=False)
                    if prev_pm is not None and not prev_pm.empty:
                        self.prev_pm_close = prev_pm['close']
                        self.prev_pm_close_avg = prev_pm['close'].mean()
                        log.info(f"[DEBUG-AM] 前一日PM数据获取成功, 股票数={len(prev_pm)}")
                    else:
                        log.warn(f"[DEBUG-AM] 前一日PM数据获取失败")
                log.info(f"[策略11] {today_str} 月初调仓，成分股{len(components)}只")
    
        if not self.index_components:
            log.warn(f"[DEBUG-AM] index_components 为空，无法获取数据")
            return
    
        log.info(f"[DEBUG-AM] 开始获取当日AM数据: {today_str}")
        am_data, _, success = self._get_halfday_prices(self.index_components, today_str, is_today=True, context=context)
        if not success or am_data is None:
            log.warn(f"[策略11AM] {today_str} 获取上午数据失败")
            return
        log.info(f"[DEBUG-AM] 当日AM数据获取成功, 股票数={len(am_data)}")
        am_close = am_data['close']
        old_pos = self.channel_position
        def _avg(df, field):
            return df[field].mean() if df is not None and not df.empty else np.nan
        am_ret, am_valid, new_val = self._calc_one_bar_close(
            self.index_components, am_close, self.prev_pm_close, self.current_index_value
        )
        am_val_before = self.current_index_value
        self.current_index_value = new_val
        am_ohlc_o = am_ohlc_h = am_ohlc_l = np.nan
        if self.prev_pm_close_avg is not None and not np.isnan(self.prev_pm_close_avg) and self.prev_pm_close_avg > 0:
            base = self.prev_pm_close_avg
            am_ohlc_o = am_val_before * (1 + (_avg(am_data, 'open') - base) / base)
            am_ohlc_h = am_val_before * (1 + (_avg(am_data, 'high') - base) / base)
            am_ohlc_l = am_val_before * (1 + (_avg(am_data, 'low') - base) / base)
        self.index_series.append({
            'datetime': pd.Timestamp(f"{today_str} 11:30:00"),
            'date': context.current_dt.date(),
            'session': 'AM',
            'ohlc_open': am_ohlc_o, 'ohlc_high': am_ohlc_h,
            'ohlc_low': am_ohlc_l, 'ohlc_close': self.current_index_value,
        })
        self.am_close_today = am_close
        self.am_close_avg_today = _avg(am_data, 'close')
        self._calc_drawdown()
        old_trigger = self.channel_trigger_reason
        old_zone = self.latest_zone
        self._update_channel_and_position()
        new_pos = self.channel_position
        dd_info = f"回撤={self.current_drawdown*100:+.2f}%"
        zone_labels = ['0~-6%', '-6%~-12%', '-12%~-20%', '<-20%']
        dd_info += f" 区间={zone_labels[self.latest_zone]}" if self.in_drawdown_cycle else " 周期外"
        log.info(f"[策略11AM] {today_str} 11:30 指数={self.current_index_value:.2f} "
                 f"EMA上={self.latest_ema_upper:.2f} 下={self.latest_ema_lower:.2f} "
                 f"仓位:{old_pos:.0%}→{new_pos:.0%} {dd_info}")
        # 生成AM信号
        if abs(new_pos - old_pos) > 0.001:
            if self.in_drawdown_cycle:
                new_reason = self.channel_trigger_reason
                new_zone = self.latest_zone
                reason_changed = (new_reason != old_trigger)
                zone_advanced = (new_zone > old_zone)
                if new_pos > old_pos:
                    if (reason_changed and new_reason == 'upper') or (new_reason == 'lower' and zone_advanced):
                        self.pending_signal = {'action': 'buy', 'target_pos': new_pos, 'time': 'AM'}
                        log.info(f"[信号] AM买入(突破上轨)" if new_reason=='upper' else f"[信号] AM买入(回撤加深{zone_labels[old_zone]}→{zone_labels[new_zone]})")
                else:
                    if reason_changed and new_reason == 'lower':
                        self.pending_signal = {'action': 'sell', 'target_pos': new_pos, 'time': 'AM'}
                        log.info(f"[信号] AM卖出(跌破下轨)")
            else:
                if new_pos > old_pos:
                    self.pending_signal = {'action': 'buy', 'target_pos': new_pos, 'time': 'AM'}
                    log.info(f"[信号] AM买入")
                else:
                    self.pending_signal = {'action': 'sell', 'target_pos': new_pos, 'time': 'AM'}
                    log.info(f"[信号] AM卖出")

    def update_index_pm(self, context):
        if not self.is_warmed:
            return
        today_str = context.current_dt.strftime('%Y-%m-%d')
        if not self.index_components:
            log.warn(f"[DEBUG-PM] index_components 为空")
            return
    
        log.info(f"[DEBUG-PM] 开始获取当日PM数据: {today_str}")
        _, pm_data, success = self._get_halfday_prices(self.index_components, today_str, is_today=True, context=context)
        if not success or pm_data is None:
            log.warn(f"[策略11PM] {today_str} 获取下午数据失败")
            return
        log.info(f"[DEBUG-PM] 当日PM数据获取成功, 股票数={len(pm_data)}")
        pm_close = pm_data['close']
        am_close = getattr(self, 'am_close_today', None)
        old_pos = self.channel_position
        def _avg(df, field):
            return df[field].mean() if df is not None and not df.empty else np.nan
        pm_ret, pm_valid, new_val = self._calc_one_bar_close(
            self.index_components, pm_close, am_close, self.current_index_value
        )
        pm_val_before = self.current_index_value
        self.current_index_value = new_val
        pm_ohlc_o = pm_ohlc_h = pm_ohlc_l = np.nan
        am_close_avg = getattr(self, 'am_close_avg_today', None)
        if am_close_avg is not None and not np.isnan(am_close_avg) and am_close_avg > 0:
            base = am_close_avg
            pm_ohlc_o = pm_val_before * (1 + (_avg(pm_data, 'open') - base) / base)
            pm_ohlc_h = pm_val_before * (1 + (_avg(pm_data, 'high') - base) / base)
            pm_ohlc_l = pm_val_before * (1 + (_avg(pm_data, 'low') - base) / base)
        self.index_series.append({
            'datetime': pd.Timestamp(f"{today_str} 15:00:00"),
            'date': context.current_dt.date(),
            'session': 'PM',
            'ohlc_open': pm_ohlc_o, 'ohlc_high': pm_ohlc_h,
            'ohlc_low': pm_ohlc_l, 'ohlc_close': self.current_index_value,
        })
        self.prev_pm_close = pm_close
        self.prev_pm_close_avg = _avg(pm_data, 'close')
        self._calc_drawdown()
        old_trigger = self.channel_trigger_reason
        old_zone = self.latest_zone
        self._update_channel_and_position()
        new_pos = self.channel_position
        dd_info = f"回撤={self.current_drawdown*100:+.2f}%"
        zone_labels = ['0~-6%', '-6%~-12%', '-12%~-20%', '<-20%']
        dd_info += f" 区间={zone_labels[self.latest_zone]}" if self.in_drawdown_cycle else " 周期外"
        log.info(f"[策略11PM] {today_str} 15:00 指数={self.current_index_value:.2f} "
                 f"EMA上={self.latest_ema_upper:.2f} 下={self.latest_ema_lower:.2f} "
                 f"仓位:{old_pos:.0%}→{new_pos:.0%} {dd_info}")
        if abs(new_pos - old_pos) > 0.001:
            if self.in_drawdown_cycle:
                new_reason = self.channel_trigger_reason
                new_zone = self.latest_zone
                reason_changed = (new_reason != old_trigger)
                zone_advanced = (new_zone > old_zone)
                if new_pos > old_pos:
                    if (reason_changed and new_reason == 'upper') or (new_reason == 'lower' and zone_advanced):
                        self.pending_signal = {'action': 'buy', 'target_pos': new_pos, 'time': 'PM'}
                        log.info(f"[信号] PM买入(突破上轨)" if new_reason=='upper' else f"[信号] PM买入(回撤加深{zone_labels[old_zone]}→{zone_labels[new_zone]})")
                else:
                    if reason_changed and new_reason == 'lower':
                        self.pending_signal = {'action': 'sell', 'target_pos': new_pos, 'time': 'PM'}
                        log.info(f"[信号] PM卖出(跌破下轨)")
            else:
                if new_pos > old_pos:
                    self.pending_signal = {'action': 'buy', 'target_pos': new_pos, 'time': 'PM'}
                    log.info(f"[信号] PM买入")
                else:
                    self.pending_signal = {'action': 'sell', 'target_pos': new_pos, 'time': 'PM'}
                    log.info(f"[信号] PM卖出")

    def execute_am_signal(self, context):
        """13:05 执行AM信号"""
        if self.pending_signal is None or self.pending_signal['time'] != 'AM':
            return
        signal = self.pending_signal
        self.pending_signal = None
        target_pos = signal.get('target_pos', 1.0 if signal['action']=='buy' else 0.0)
        log.info(f"[执行] 13:05 AM信号 {signal['action']} 目标仓位{target_pos:.0%}")
        self._adjust_position(context, target_pos)

    def execute_pm_signal(self, context):
        """9:35 执行PM信号（次日）"""
        if self.pending_signal is None or self.pending_signal['time'] != 'PM':
            return
        signal = self.pending_signal
        self.pending_signal = None
        target_pos = signal.get('target_pos', 1.0 if signal['action']=='buy' else 0.0)
        log.info(f"[执行] 9:35 PM信号 {signal['action']} 目标仓位{target_pos:.0%}")
        self._adjust_position(context, target_pos)

    def monthly_rebalance(self, context):
        """每月第1天10:00 满仓状态下月度调仓"""
        if self.channel_position < 1.0:
            log.info(f"[月度调仓] {context.current_dt.date()} 仓位{self.channel_position:.0%}，非满仓跳过")
            return
        log.info(f"[月度调仓] {context.current_dt.date()} 满仓，月度调仓")
        self.update_dynamic_high_price(context)
        self.my_Trader(context)
        self.go_Trader(context)

    def prepare_stock_list(self, context):
        """9:05 记录昨日涨停"""
        self.high_limit_list = []
        sp = context.subportfolios[self.pindex]
        hold_list = list(sp.positions.keys())
        if hold_list:
            df = get_price(hold_list, end_date=context.previous_date, frequency='daily',
                           fields=['close', 'high_limit'], count=1, panel=False)
            self.high_limit_list = df[df['close'] == df['high_limit']]['code'].tolist()

    def clear_just_sold(self, context):
        """开盘清理冷却列表"""
        if self.just_sold_dict:
            for key in list(self.just_sold_dict.keys()):
                self.just_sold_dict[key] += 1
                if self.just_sold_dict[key] % self.clear_just_sold_cycle == 0:
                    del self.just_sold_dict[key]
            self.just_sold_list = list(self.just_sold_dict.keys())

    def check_limit_up(self, context):
        """13:30 涨停打开卖出 + 补仓"""
        sp = context.subportfolios[self.pindex]
        current_data = get_current_data()
        position_count = len(sp.positions)
        if self.channel_position > 0 and self.stock_num > position_count and position_count != 0:
            self.my_Trader(context)
            if self.choice:
                supplement_candidates = [s for s in self.choice if s not in sp.positions and s not in self.just_sold_list]
                if supplement_candidates:
                    reserved_slots = len(sp.positions)
                    target_slots = self.stock_num
                    for stock in supplement_candidates:
                        remain_slots = target_slots - reserved_slots
                        if remain_slots <= 0:
                            break
                        current_price = current_data[stock].last_price
                        if current_price <= self.ma(stock, self.ma_day_2) * self.buy_limit:
                            target_per_stock = sp.total_value * self.channel_position / self.stock_num
                            psize = min(sp.available_cash / remain_slots, target_per_stock)
                            order_value(stock, psize, pindex=self.pindex)
                            reserved_slots += 1
                            log.info(f'补仓 {stock} {current_data[stock].name}')
        if self.high_limit_list:
            for stock in self.high_limit_list:
                if current_data[stock].last_price < current_data[stock].high_limit:
                    order_target(stock, 0, pindex=self.pindex)
                    log.info(f'涨停打开卖出 {stock}')
                    self.just_sold_append(stock)

    def after_market_close(self, context):
        """收盘日志"""
        sp = context.subportfolios[self.pindex]
        current_pos = sp.positions_value / sp.total_value if sp.total_value > 0 else 0.0
        hold_count = len(sp.positions)
        log.info(f"[策略11收盘] 实际仓位={current_pos:.2%} 目标仓位={self.channel_position:.2%} "
                 f"持股={hold_count}/{self.stock_num} 回撤={self.current_drawdown*100:+.2f}%")

    # ---------- 核心交易函数 ----------
    def _adjust_position(self, context, target_pos):
        sp = context.subportfolios[self.pindex]
        total_value = sp.total_value
        current_hold_value = sum(p.value for p in sp.positions.values())
        log.info(f"[调仓] 当前持仓市值={current_hold_value:.0f} 目标={total_value*target_pos:.0f} (比例{target_pos:.0%})")
        if target_pos <= 0.001:
            self._sell_all(context)
            return
        if target_pos >= 0.999:
            self.update_dynamic_high_price(context)
            self._scale_to_full(context)
            return
        if current_hold_value > total_value * target_pos:
            ratio = (total_value * target_pos) / current_hold_value if current_hold_value > 0 else 0
            for stock in list(sp.positions.keys()):
                p = sp.positions[stock]
                new_amount = int(p.total_amount * ratio / 100) * 100
                if new_amount < p.total_amount:
                    order_target(stock, new_amount, pindex=self.pindex)
                    log.info(f'部分卖出 {stock} 保留{ratio*100:.0f}%')
                    self.just_sold_append(stock)
        elif current_hold_value < total_value * target_pos:
            self.update_dynamic_high_price(context)
            self._scale_to_target(context, target_pos)

    def _scale_to_full(self, context):
        sp = context.subportfolios[self.pindex]
        if not sp.positions:
            self.my_Trader(context)
            self.go_Trader(context)
            return
        total_value = sp.total_value
        target_per_stock = total_value / self.stock_num
        current_data = get_current_data()
        for stock in list(sp.positions.keys()):
            p = sp.positions[stock]
            if p.value < target_per_stock:
                order_target_value(stock, target_per_stock, pindex=self.pindex)
                log.info(f'加仓 {stock} 目标市值{target_per_stock:.0f}')

    def _scale_to_target(self, context, target_pos):
        sp = context.subportfolios[self.pindex]
        if not sp.positions:
            self.my_Trader(context)
            choice = self.choice
            total_value = sp.total_value
            psize = total_value * target_pos / self.stock_num
            current_data = get_current_data()
            for stock in choice:
                if stock not in sp.positions:
                    current_price = current_data[stock].last_price
                    if current_price <= self.ma(stock, self.ma_day_2) * self.buy_limit:
                        order_value(stock, psize, pindex=self.pindex)
                        if len(sp.positions) == self.stock_num:
                            break
            return
        total_value = sp.total_value
        target_value = total_value * target_pos
        current_hold_value = sum(p.value for p in sp.positions.values())
        invest_cash = min(target_value - current_hold_value, sp.available_cash)
        if invest_cash <= 0:
            return
        target_per_stock = target_value / self.stock_num
        current_data = get_current_data()
        for stock in list(sp.positions.keys()):
            p = sp.positions[stock]
            if p.value < target_per_stock:
                order_target_value(stock, target_per_stock, pindex=self.pindex)
                if sp.available_cash <= 0:
                    break

    def _sell_all(self, context):
        sp = context.subportfolios[self.pindex]
        current_data = get_current_data()
        for stock in list(sp.positions.keys()):
            order_target(stock, 0, pindex=self.pindex)
            log.info(f'清仓卖出 {stock}')
            self.just_sold_append(stock)

    # ---------- 选股（菜场大妈框架） ----------
    def my_Trader(self, context):
        self.update_dynamic_high_price(context)
        dt_last = context.previous_date
        stocks = get_all_securities('stock', dt_last).index.tolist()
        stocks = self.filter_kcbj_stock(stocks)
        stocks = self.get_dividend_ratio_filter_list(context, stocks, False, 0, 0.25)
        stocks = self.get_pe_filter(context, stocks)
        stocks = self.guojiutiao(context, stocks)
        choice = self.filter_st_stock(stocks)
        choice = self.filter_paused_stock(choice)
        choice = self.filter_limitup_stock(context, choice)
        choice = self.filter_limitdown_stock(context, choice)
        choice = self.filter_highprice_stock(context, choice)
        choice = self.filter_highprice_in_shorttime(context, choice)
        choice = [item for item in choice if item not in self.just_sold_list]
        self.choice = choice[:self.stock_num]

    def go_Trader(self, context):
        sp = context.subportfolios[self.pindex]
        current_data = get_current_data()
        choice = self.choice
        for stock in list(sp.positions.keys()):
            if stock not in choice:
                order_target(stock, 0, pindex=self.pindex)
                log.info(f'Sell {stock}')
                self.just_sold_append(stock)
        position_count = len(sp.positions)
        if self.stock_num > position_count:
            psize = sp.available_cash / (self.stock_num - position_count)
            for stock in choice:
                if stock not in sp.positions:
                    current_price = current_data[stock].last_price
                    if current_price <= self.ma(stock, self.ma_day_2) * self.buy_limit:
                        order_value(stock, psize, pindex=self.pindex)
                        log.info(f'Buy {stock}')
                        if len(sp.positions) == self.stock_num:
                            break

    # ---------- 选股过滤函数 ----------
    def get_pe_filter(self, context, stocks):
        q = query(valuation.code, valuation.pe_ratio, valuation.pb_ratio,
                  valuation.market_cap, indicator.inc_net_profit_year_on_year
                  ).filter(valuation.code.in_(stocks),
                           valuation.pe_ratio > 0,
                           valuation.pb_ratio < 3,
                           indicator.inc_net_profit_year_on_year != None
                           ).order_by(valuation.market_cap.asc())
        df = get_fundamentals(q, date=None)
        df['peg'] = df['pe_ratio'] / df['inc_net_profit_year_on_year']
        df = df[df['peg'] < 0]
        return list(df.code)

    def get_dividend_ratio_filter_list(self, context, stock_list, sort, p1, p2):
        time1 = context.previous_date
        time0 = time1 - datetime.timedelta(days=365)
        interval = 1000
        list_len = len(stock_list)
        q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date,
                  finance.STK_XR_XD.bonus_amount_rmb
                  ).filter(finance.STK_XR_XD.a_registration_date >= time0,
                           finance.STK_XR_XD.a_registration_date <= time1,
                           finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
        df = finance.run_query(q)
        if list_len > interval:
            df_num = list_len // interval
            for i in range(df_num):
                q2 = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date,
                           finance.STK_XR_XD.bonus_amount_rmb
                           ).filter(finance.STK_XR_XD.a_registration_date >= time0,
                                    finance.STK_XR_XD.a_registration_date <= time1,
                                    finance.STK_XR_XD.code.in_(stock_list[interval*(i+1):min(list_len, interval*(i+2))]))
                temp_df = finance.run_query(q2)
                df = pd.concat([df, temp_df], ignore_index=True)
        dividend = df.fillna(0)
        dividend = dividend.set_index('code')
        dividend = dividend.groupby('code').sum()
        temp_list = list(dividend.index)
        q3 = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(temp_list))
        cap = get_fundamentals(q3, date=time1)
        cap = cap.set_index('code')
        DR = pd.concat([dividend, cap], axis=1, sort=False)
        DR['dividend_ratio'] = (DR['bonus_amount_rmb'] / 10000) / DR['market_cap']
        DR = DR.sort_values(by=['dividend_ratio'], ascending=sort)
        final_list = list(DR.index)[int(p1*len(DR)):int(p2*len(DR))]
        return final_list

    def guojiutiao(self, context, stock_list):
        q = query(valuation.code, valuation.market_cap,
                  income.np_parent_company_owners, income.net_profit, income.operating_revenue
                  ).filter(valuation.code.in_(stock_list),
                           valuation.market_cap.between(self.min_mv, self.max_mv),
                           income.np_parent_company_owners > 0,
                           income.net_profit > 0,
                           income.operating_revenue > 1e8
                           ).order_by(valuation.market_cap.asc())
        df = get_fundamentals(q)
        return list(df.code)

    def filter_kcbj_stock(self, stock_list):
        return [s for s in stock_list if s[0] not in ('4','8') and s[:3] != '688']

    def filter_paused_stock(self, stock_list):
        current_data = get_current_data()
        return [s for s in stock_list if not current_data[s].paused]

    def filter_st_stock(self, stock_list):
        current_data = get_current_data()
        return [s for s in stock_list if not current_data[s].is_st
                and 'ST' not in current_data[s].name
                and '*' not in current_data[s].name
                and '退' not in current_data[s].name]

    def filter_limitup_stock(self, context, stock_list):
        last_prices = history(1, unit='1m', field='close', security_list=stock_list)
        current_data = get_current_data()
        sp = context.subportfolios[self.pindex]
        return [s for s in stock_list if s in sp.positions.keys()
                or last_prices[s][-1] < current_data[s].high_limit * 0.97]

    def filter_limitdown_stock(self, context, stock_list):
        last_prices = history(1, unit='1m', field='close', security_list=stock_list)
        current_data = get_current_data()
        sp = context.subportfolios[self.pindex]
        return [s for s in stock_list if s in sp.positions.keys()
                or last_prices[s][-1] > current_data[s].low_limit * 1.04]

    def filter_highprice_stock(self, context, stock_list):
        last_prices = history(1, unit='1m', field='close', security_list=stock_list)
        sp = context.subportfolios[self.pindex]
        return [s for s in stock_list if s in sp.positions.keys()
                or (last_prices[s][-1] > self.low_price and last_prices[s][-1] < self.high_price)]

    def filter_highprice_in_shorttime(self, context, stock_list):
        last_prices = history(1, unit='1m', field='close', security_list=stock_list)
        sp = context.subportfolios[self.pindex]
        return [s for s in stock_list if s in sp.positions.keys()
                or last_prices[s][-1] < self.ma(s, self.ma_day_2) * self.buy_limit]

    # ---------- 工具 ----------
    def ma(self, stock, n):
        hist = attribute_history(stock, n, '1d', ['close'])
        return hist['close'].mean()

    def just_sold_append(self, stock):
        self.just_sold_dict[stock] = 0
        self.just_sold_list = list(self.just_sold_dict.keys())

    def update_dynamic_high_price(self, context):
        today = context.current_dt.date()
        pre_month_end = today.replace(day=1) - datetime.timedelta(days=1)
        trade_days = get_trade_days(end_date=pre_month_end, count=1)
        if len(trade_days) == 0:
            return
        last_trade_day = trade_days[-1]
        q = query(valuation.code, valuation.market_cap).filter(
            valuation.market_cap >= self.min_mv,
            valuation.market_cap <= self.max_mv
        )
        df = get_fundamentals(q, date=last_trade_day)
        if df.empty:
            return
        codes = list(df.code)
        price_df = get_price(codes, end_date=last_trade_day, frequency='daily',
                             fields=['close'], count=1, panel=False)
        if price_df.empty:
            return
        avg_price = price_df['close'].mean()
        new_high = round(avg_price * self.high_price_multiplier, 2)
        new_high = max(new_high, 10.0)
        self.high_price = new_high
        log.info(f"[动态股价] 上月均价={avg_price:.2f}元×{self.high_price_multiplier:.1f}={new_high:.2f}元")

    # ---------- trade（组合调度入口，不做实质操作） ----------
    def trade(self, context):
        # 本策略所有操作由独立定时任务完成，此处仅用于日志占位
        pass


# ======================================================================
# ========== 策略12：融合红利低波 + 低相关ETF轮动（b.txt） ==========
# ======================================================================
class Strategy12(BaseStrategy):
    def __init__(self, pindex, initial_cash):   # 不再接收 target_weight
        super().__init__('融合红利轮动', pindex, initial_cash)
        # ---------- 原b.txt参数 ----------
        self.cash_etf = '511880.XSHG'
        self.etf_pool = [
            '510300.XSHG',  # 沪深300
            '510500.XSHG',  # 中证500
            '159915.XSHE',  # 创业板
            '513100.XSHG',  # 纳指
            '159920.XSHE',  # 恒生
            '518880.XSHG',  # 黄金
            '511010.XSHG',  # 国债
            '512400.XSHG',  # 有色金属
            '159985.XSHE',  # 豆粕
        ]
        self.lookback_days = 120
        self.short_days = 60
        self.vol_days = 20
        self.max_hold = 4
        self.position_ratio = 0.95
        self.max_single_weight = 0.35
        self.min_long_momentum = -0.03
        self.min_short_momentum = -0.06
        self.min_score = -0.02
        self.max_vol = 0.045
        self.max_dd = 0.30
        self.corr_penalty = 0.18
        self.min_list_days = 180

        # 红利ETF择时参数
        self.dividend_etf = '512890.XSHG'
        self.ma_length = 250
        self.buy_threshold = 0.985
        self.sell_threshold = 1.095

        # 状态变量
        self.mode = 'rotation'          # 'rotation' 或 'dividend'
        self.last_rotation_rebalance_date = None

    # ---------- 辅助函数（从b.txt移植） ----------
    def _is_listed(self, context, code):
        try:
            info = get_security_info(code)
            if info is None:
                return False
            if info.start_date + datetime.timedelta(days=self.min_list_days) > context.previous_date:
                return False
            return True
        except:
            return False

    def _can_buy(self, code):
        try:
            data = get_current_data()[code]
            if data.paused:
                return False
            if data.last_price >= data.high_limit:
                return False
            return True
        except:
            return False

    def _can_sell(self, code):
        try:
            data = get_current_data()[code]
            if data.paused:
                return False
            if data.last_price <= data.low_limit:
                return False
            return True
        except:
            return False

    @staticmethod
    def _calc_returns(closes):
        result = []
        for i in range(1, len(closes)):
            prev = float(closes[i-1])
            now = float(closes[i])
            if prev > 0:
                result.append(now/prev - 1.0)
        return result

    @staticmethod
    def _calc_corr(a, b):
        n = min(len(a), len(b))
        if n < 20:
            return 0.0
        x = a[-n:]
        y = b[-n:]
        avg_x = sum(x) / n
        avg_y = sum(y) / n
        cov = 0.0
        var_x = 0.0
        var_y = 0.0
        for i in range(n):
            dx = x[i] - avg_x
            dy = y[i] - avg_y
            cov += dx * dy
            var_x += dx * dx
            var_y += dy * dy
        if var_x <= 0 or var_y <= 0:
            return 0.0
        return cov / math.sqrt(var_x * var_y)

    @staticmethod
    def _calc_vol(returns):
        if len(returns) == 0:
            return 0.02
        avg = sum(returns) / len(returns)
        var = sum((r - avg) ** 2 for r in returns) / len(returns)
        return math.sqrt(var)

    @staticmethod
    def _calc_max_dd(closes):
        if len(closes) == 0:
            return 0.0
        high = closes[0]
        max_dd = 0.0
        for price in closes:
            if price > high:
                high = price
            if high > 0:
                dd = 1.0 - price / high
                if dd > max_dd:
                    max_dd = dd
        return max_dd

    def _calc_signal(self, context, code):
        count = self.lookback_days + 1
        try:
            df = get_price(code, end_date=context.previous_date, count=count,
                           frequency='daily', fields=['close'], panel=False)
            if df is None or len(df) < count:
                return None
            closes = [float(x) for x in df['close']]
            close = closes[-1]
            if close <= 0:
                return None
            base120 = closes[0]
            base60 = closes[-self.short_days - 1]
            if base120 <= 0 or base60 <= 0:
                return None
            ret120 = close / base120 - 1.0
            ret60 = close / base60 - 1.0
            returns = self._calc_returns(closes)
            vol = self._calc_vol(returns[-self.vol_days:])
            max_dd = self._calc_max_dd(closes)
            score = ret120 * 0.55 + ret60 * 0.45 - vol * 1.8 - max_dd * 0.15
            return {
                'ret120': ret120,
                'ret60': ret60,
                'vol': vol,
                'max_dd': max_dd,
                'score': score,
                'returns': returns
            }
        except Exception as e:
            log.info('计算信号异常: %s %s' % (code, e))
            return None

    def _average_corr(self, code, selected, signals):
        total = 0.0
        count = 0
        for other in selected:
            corr = self._calc_corr(signals[code]['returns'], signals[other]['returns'])
            if corr < -0.5:
                corr = -0.5
            total += corr
            count += 1
        return total / count if count > 0 else 0.0

    def _build_signals(self, context):
        result = {}
        for code in self.etf_pool:
            if not self._is_listed(context, code):
                continue
            sig = self._calc_signal(context, code)
            if sig is None:
                continue
            if sig['vol'] > self.max_vol:
                continue
            if sig['max_dd'] > self.max_dd:
                continue
            if sig['ret120'] < self.min_long_momentum and sig['ret60'] < self.min_short_momentum:
                continue
            if sig['score'] < self.min_score:
                continue
            result[code] = sig
        return result

    def _select_low_corr_etfs(self, signals):
        candidates = sorted(signals.keys(), key=lambda x: signals[x]['score'], reverse=True)
        selected = []
        while len(selected) < self.max_hold:
            best_code = None
            best_score = -999999.0
            for code in candidates:
                if code in selected:
                    continue
                base_score = signals[code]['score']
                if len(selected) == 0:
                    final_score = base_score
                else:
                    avg_corr = self._average_corr(code, selected, signals)
                    final_score = base_score - avg_corr * self.corr_penalty
                if final_score > best_score:
                    best_score = final_score
                    best_code = code
            if best_code is None:
                break
            selected.append(best_code)
        return selected

    def _build_weights(self, selected, signals):
        raw = {}
        raw_sum = 0.0
        for code in selected:
            vol = signals[code]['vol']
            if vol < 0.005:
                vol = 0.005
            momentum_bonus = 1.0 + max(0.0, signals[code]['score'])
            value = momentum_bonus / vol
            raw[code] = value
            raw_sum += value
        if raw_sum <= 0:
            return {self.cash_etf: 0.98}
        weights = {}
        used = 0.0
        for code in selected:
            w = raw[code] / raw_sum * self.position_ratio
            if w > self.max_single_weight:
                w = self.max_single_weight
            weights[code] = w
            used += w
        return weights

    def _trade_to_weights(self, context, weights):
        sp = context.subportfolios[self.pindex]
        total_value = sp.total_value
        # 先清掉不在目标中的持仓
        for code, pos in sp.positions.items():
            if pos.total_amount <= 0:
                continue
            if code not in weights:
                if self._can_sell(code):
                    order_target_value(code, 0, pindex=self.pindex)
        # 买入目标
        for code, w in weights.items():
            target_value = total_value * w
            if self._can_buy(code) or (code in sp.positions and sp.positions[code].total_amount > 0):
                order_target_value(code, target_value, pindex=self.pindex)

    def _dividend_signal(self, context):
        try:
            hist_close = attribute_history(self.dividend_etf, self.ma_length, '1d', ['close'], skip_paused=True)
            if len(hist_close) < self.ma_length:
                return None
            ma250 = hist_close['close'].mean()
            hist_hl = attribute_history(self.dividend_etf, 1, '1d', ['high', 'low'], skip_paused=True)
            if hist_hl.empty:
                return None
            prev_low = hist_hl['low'].iloc[0]
            prev_high = hist_hl['high'].iloc[0]
            ratio_low = prev_low / ma250
            ratio_high = prev_high / ma250
            return ratio_low, ratio_high, ma250
        except Exception as e:
            log.info('红利信号计算异常: %s' % e)
            return None

    def _clear_all_positions(self, context):
        sp = context.subportfolios[self.pindex]
        for code, pos in sp.positions.items():
            if pos.total_amount > 0:
                order_target(code, 0, pindex=self.pindex)
                log.info('清仓 %s' % code)

    def _rebalance(self, context):
        """轮动模式下的组合再平衡"""
        signals = self._build_signals(context)
        if len(signals) == 0:
            log.info('没有有效ETF，切换到货币ETF')
            self._trade_to_weights(context, {self.cash_etf: 0.98})
            return
        selected = self._select_low_corr_etfs(signals)
        if len(selected) == 0:
            log.info('没有选出低相关组合，切换到货币ETF')
            self._trade_to_weights(context, {self.cash_etf: 0.98})
            return
        weights = self._build_weights(selected, signals)
        used = sum(weights.values())
        cash_weight = 0.98 - used
        if cash_weight > 0.02:
            weights[self.cash_etf] = cash_weight
        log.info('入选ETF: %s' % selected)
        log.info('目标权重: %s' % weights)
        self._trade_to_weights(context, weights)

    def _daily_check(self, context):
        """每日检查红利信号，决定是否切换模式"""
        current_data = get_current_data()
        if current_data[self.dividend_etf].paused:
            log.info('红利ETF停牌，跳过今日信号检查')
            return
        sig = self._dividend_signal(context)
        if sig is None:
            return
        ratio_low, ratio_high, ma250 = sig
        log.info('[红利信号] 日期:%s 低偏离:%.4f 高偏离:%.4f MA250:%.4f' %
                 (context.current_dt.strftime('%Y-%m-%d'), ratio_low, ratio_high, ma250))

        if self.mode == 'rotation':
            if ratio_low < self.buy_threshold:
                log.info('【买入红利】低偏离 %.4f < %.3f，清仓轮动组合，全仓买入 %s' %
                         (ratio_low, self.buy_threshold, self.dividend_etf))
                self._clear_all_positions(context)
                order_target_value(self.dividend_etf, context.subportfolios[self.pindex].total_value, pindex=self.pindex)
                self.mode = 'dividend'
            else:
                log.info('轮动模式：红利无买入信号，继续持有轮动组合')
        else:  # dividend mode
            if ratio_high > self.sell_threshold:
                log.info('【卖出红利】高偏离 %.4f > %.3f，清仓 %s，切换回轮动模式' %
                         (ratio_high, self.sell_threshold, self.dividend_etf))
                order_target(self.dividend_etf, 0, pindex=self.pindex)
                self.mode = 'rotation'
                self._rebalance(context)
                self.last_rotation_rebalance_date = context.current_dt.date()
            else:
                log.info('红利模式：无卖出信号，继续持有红利ETF')

    # ---------- 主交易入口 ----------
    def trade(self, context):
        # 每日执行一次信号检查和月度再平衡（在14:50统一触发）
        self._daily_check(context)
        # 如果是每月1号且处于轮动模式，执行月度再平衡（避免重复）
        if context.current_dt.day == 1 and self.mode == 'rotation':
            if self.last_rotation_rebalance_date != context.current_dt.date():
                self._rebalance(context)
                self.last_rotation_rebalance_date = context.current_dt.date()


# ======================================================================
# ========== 策略13：五境掘金全球ETF轮动（a.txt） ==========
# ======================================================================
class Strategy13(BaseStrategy):
    def __init__(self, pindex, initial_cash):
        super().__init__('五境掘金ETF轮动', pindex, initial_cash)
        # ---------- 原a.txt参数 ----------
        self.etf_pool = [
            '159915.XSHE',   # 创业板
            '159941.XSHE',   # 纳指
            '518880.XSHG',   # 黄金
            '162719.XSHE',   # 广发石油
            '513030.XSHG'    # 德国30
        ]
        self.gain_days = 20          # 涨幅计算天数
        self.min_gain = 2.0          # 涨幅下限(%)
        self.max_gain = 20.0         # 涨幅上限(%)，过热过滤
        self.bias20_max = 14.0
        self.bias60_max = 25.0
        self.bias250_max = 60.0
        self.cooldown_days = 5
        self.stop_loss_pct = -6.0
        self.sell_rank = 4
        self.last_sell_record = {}

    # ---------- 辅助函数（从a.txt移植） ----------
    def _check_etf(self, security, context):
        try:
            df = attribute_history(security, 300, '1d', ['close'], skip_paused=True, df=True)
            if df is None or len(df) < 250:
                return None
            closes = df['close'].values
            current = closes[-1]
            n = self.gain_days + 1
            ret_gain = (current / closes[-n] - 1) * 100
            ma20 = np.mean(closes[-20:])
            bias20 = (current / ma20 - 1) * 100
            ma60 = np.mean(closes[-60:])
            bias60 = (current / ma60 - 1) * 100
            ma250 = np.mean(closes[-250:])
            bias250 = (current / ma250 - 1) * 100
            return ret_gain, bias20, bias60, bias250
        except Exception as e:
            log.debug('{} 计算异常: {}'.format(security, e))
            return None

    def _filter_and_rank(self, context, current_dt):
        qualified = []
        for etf in self.etf_pool:
            res = self._check_etf(etf, context)
            if res is None:
                continue
            ret_gain, b20, b60, b250 = res
            if (ret_gain > self.min_gain) and (ret_gain < self.max_gain) and \
               (b20 < self.bias20_max) and (b60 < self.bias60_max) and (b250 < self.bias250_max):
                qualified.append((etf, ret_gain))
        if not qualified:
            return []
        qualified.sort(key=lambda x: x[1], reverse=True)
        return [etf for etf, _ in qualified]

    def _get_current_hold(self, context):
        sp = context.subportfolios[self.pindex]
        for etf in self.etf_pool:
            if etf in sp.positions and sp.positions[etf].total_amount > 0:
                return etf
        return None

    def _cooling_check(self, etf, today):
        if etf not in self.last_sell_record:
            return False
        last = self.last_sell_record[etf]
        trade_days = get_trade_days(start_date=last, end_date=today)
        diff = len(trade_days) - 1
        return diff <= self.cooldown_days

    def _stop_loss_triggered(self, security, context):
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

    # ---------- 主交易入口 ----------
    def trade(self, context):
        today = context.current_dt.date()
        if context.current_dt.year < 2021:
            return

        # 日志：显示各标的涨幅和乖离率
        all_indicators = []
        for etf in self.etf_pool:
            res = self._check_etf(etf, context)
            if res is not None:
                ret_gain, b20, b60, b250 = res
                all_indicators.append((etf, ret_gain, b20, b60, b250))
        all_indicators.sort(key=lambda x: x[1], reverse=True)
        log.info('=== {}日涨幅/乖离率排名 ==='.format(self.gain_days))
        for rank, (etf, ret_gain, b20, b60, b250) in enumerate(all_indicators, 1):
            qualified_tag = '✓' if (ret_gain > self.min_gain and ret_gain < self.max_gain and
                                    b20 < self.bias20_max and b60 < self.bias60_max and b250 < self.bias250_max) else '✗'
            log.info('  #{} {} {} | {}日涨幅={:.1f}% 20日乖离={:.1f}% 60日乖离={:.1f}% 250日乖离={:.1f}%'.format(
                rank, etf, qualified_tag, self.gain_days, ret_gain, b20, b60, b250))

        # 冷却期记录
        if self.last_sell_record:
            log.info('=== 冷却期记录 ===')
            for etf, sell_date in self.last_sell_record.items():
                trade_days = get_trade_days(start_date=sell_date, end_date=today)
                diff = len(trade_days) - 1
                remaining = self.cooldown_days - diff if diff < self.cooldown_days else 0
                status = '冷却中(剩余{}个交易日)' if diff <= self.cooldown_days else '已解除'
                log.info('  {} | 卖出日={} 已过{}个交易日 {}'.format(etf, sell_date, diff, status.format(remaining) if diff <= self.cooldown_days else status))
        else:
            log.info('=== 冷却期记录：无 ===')

        # 当前持仓
        current_hold = self._get_current_hold(context)

        # 获得当日合格排名
        ranked_list = self._filter_and_rank(context, context.current_dt)

        # 目标品种（无合格ETF时空仓）
        target = ranked_list[0] if ranked_list else None

        # 判断是否需要调仓
        need_trade = False
        if current_hold is None:
            need_trade = True
        elif current_hold != target:
            if self._stop_loss_triggered(current_hold, context):
                need_trade = True
                log.info('触发止损: {}'.format(current_hold))
            else:
                res = self._check_etf(current_hold, context)
                if res is None:
                    need_trade = True
                else:
                    ret_gain, b20, b60, b250 = res
                    cond_self = (ret_gain > self.min_gain) and (ret_gain < self.max_gain) and \
                                (b20 < self.bias20_max) and (b60 < self.bias60_max) and (b250 < self.bias250_max)
                    rank = ranked_list.index(current_hold) + 1 if current_hold in ranked_list else len(ranked_list) + 1
                    if (not cond_self) or (rank >= self.sell_rank):
                        need_trade = True

        if not need_trade:
            return

        # 调仓：清空所有ETF持仓
        sp = context.subportfolios[self.pindex]
        for etf in self.etf_pool:
            if etf in sp.positions and sp.positions[etf].total_amount > 0:
                log.info('清仓 ETF: {}'.format(etf))
                self.last_sell_record[etf] = today
                order_target(etf, 0, pindex=self.pindex)

        # 买入目标（空仓则持有现金）
        if target is None:
            log.info('无合格ETF，空仓持有现金')
            return
        else:
            if self._cooling_check(target, today):
                log.info('{} 在冷却期内，暂不买入，今日空仓'.format(target))
                return
            total_value = sp.total_value
            if total_value > 0:
                order_target_value(target, total_value, pindex=self.pindex)
                log.info('买入 {}，金额 {:.2f}'.format(target, total_value))


# ========== 策略14：多因子ETF动量 ==========
class Strategy14(BaseStrategy):
    # ... 保持不变（原代码） ...
    def __init__(self, pindex, initial_cash):
        super().__init__('多因子ETF动量', pindex, initial_cash)
        self.overseas_etf_pool = ["513100.XSHG","513290.XSHG","513500.XSHG","159529.XSHE",
                                  "513400.XSHG","513520.XSHG","513030.XSHG","513080.XSHG",
                                  "513310.XSHG","513730.XSHG","159792.XSHE","513130.XSHG",
                                  "513050.XSHG","159920.XSHE","513690.XSHG","511380.XSHG",
                                  "511010.XSHG","511220.XSHG"]
        self.commodity_etf_pool = ["518880.XSHG","159980.XSHE","159985.XSHE","501018.XSHG",
                                   "161226.XSHE","159981.XSHE","512400.XSHG"]
        self.domestic_etf_pool = ["510300.XSHG","510500.XSHG","510050.XSHG","510210.XSHG",
                                  "159915.XSHE","588080.XSHG","512100.XSHG","563360.XSHG",
                                  "563300.XSHG","512890.XSHG","159967.XSHE","588020.XSHG",
                                  "512040.XSHG","159201.XSHE","515790.XSHG","563230.XSHG",
                                  "515880.XSHG","512660.XSHG","561380.XSHG","159667.XSHE",
                                  "159559.XSHE","159819.XSHE","159381.XSHE","159732.XSHE",
                                  "159995.XSHE","512220.XSHG"]
        self.etf_pool = self.overseas_etf_pool + self.commodity_etf_pool + self.domestic_etf_pool
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
            if self._check_profit_protection(etf, context):
                return None, "触发盈利保护"
            if self.enable_premium_filter:
                prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
                premium, _, _ = self._get_premium_rate(etf, prev_date)
                if premium is not None and premium > self.premium_threshold:
                    return None, f"溢价率{premium*100:.2f}%超阈值"
            if self.enable_volume_check:
                vol_ratio = self._get_volume_ratio(etf, context)
                if vol_ratio is not None:
                    annualized = self._get_annualized_returns(price_series, self.lookback_days)
                    if annualized > self.volume_return_limit:
                        return None, f"成交量放量 {vol_ratio:.2f}倍"
            if len(price_series) >= self.short_lookback_days + 1:
                short_return = price_series[-1] / price_series[-(self.short_lookback_days + 1)] - 1
                short_annualized = (1 + short_return) ** (250 / self.short_lookback_days) - 1
            else:
                short_annualized = 0
            if self.use_short_momentum_filter and short_annualized < self.short_momentum_threshold:
                return None, f"短期年化{short_annualized*100:.2f}% < {self.short_momentum_threshold*100:.0f}%"
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
            if len(price_series) >= 4:
                day1 = price_series[-1] / price_series[-2]
                day2 = price_series[-2] / price_series[-3]
                day3 = price_series[-3] / price_series[-4]
                if min(day1, day2, day3) < self.loss:
                    return None, f"近3日有单日跌幅超{self.loss*100:.0f}%"
            if not (self.min_score_threshold < score < self.max_score_threshold):
                return None, f"得分{score:.4f}超出阈值"
            metrics = {
                'etf': etf, 'etf_name': name, 'annualized_returns': annualized_returns,
                'r_squared': r_squared, 'score': score, 'current_price': current_price,
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
            filtered_log = {}
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
            log.info('[策略14] 排名计算完成，有效ETF %d只' % len(ranked))
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
        self.drawdown_selled_today = set()
        self.trade_log['sell_records'] = []
        ranked = self._get_cached_rankings(context)
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
        defensive_available = not get_current_data()[self.defensive_etf].paused
        if not target_etfs and defensive_available and self.defensive_etf not in self.drawdown_selled_today:
            target_etfs = [self.defensive_etf]
            log.info('[策略14] 进入防御模式')
        current_positions = list(sp.positions.keys())
        for sec in current_positions:
            if sec not in target_etfs:
                pos = sp.positions.get(sec)
                if pos and pos.total_amount > 0:
                    log.info('[策略14] 卖出 %s' % sec)
                    self._order(sec, -pos.closeable_amount)
        if target_etfs:
            total_val = sp.total_value
            target_per = total_val / len(target_etfs)
            for etf in target_etfs:
                current_val = 0
                pos = sp.positions.get(etf)
                if pos:
                    current_val = pos.total_amount * pos.price
                if abs(current_val - target_per) > target_per * 0.05 or current_val == 0:
                    price = get_current_data()[etf].last_price
                    if price is None or price <= 0:
                        continue
                    max_shares = int(sp.available_cash // (price * 100) * 100)
                    target_shares = int(target_per // (price * 100) * 100)
                    shares = min(max_shares, target_shares)
                    if shares >= 100:
                        self._order(etf, shares)
                        self.buy_date[etf] = current_date
                        log.info('[策略14] 买入 %s %d股 金额%.2f' % (etf, shares, shares*price))
                    else:
                        log.info('[策略14] %s 资金不足或不满足最小单位，跳过' % etf)
        else:
            log.info('[策略14] 无目标，保持空仓')


# ========== 全局定时任务代理（策略11） ==========
def s11_update_index_am(context):
    g.s11.update_index_am(context)

def s11_update_index_pm(context):
    g.s11.update_index_pm(context)

def s11_execute_am_signal(context):
    g.s11.execute_am_signal(context)

def s11_execute_pm_signal(context):
    g.s11.execute_pm_signal(context)

def s11_monthly_rebalance(context):
    g.s11.monthly_rebalance(context)

def s11_prepare_stock_list(context):
    g.s11.prepare_stock_list(context)

def s11_clear_just_sold(context):
    g.s11.clear_just_sold(context)

def s11_check_limit_up(context):
    g.s11.check_limit_up(context)

def s11_after_market_close(context):
    g.s11.after_market_close(context)


# ========== 主组合策略 ==========
def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('system', 'error')
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0003,
                             close_commission=0.0003, min_commission=5), type='stock')
    set_slippage(FixedSlippage(0.001))

    # ---------- 仓位比例设置（四个策略独立） ----------
    g.strategy_weights = [0.2, 0.2, 0.3, 0.3]  # 策略11,12,13,14
    total_cash = context.portfolio.starting_cash
    weights = np.array(g.strategy_weights) / np.sum(g.strategy_weights)

    cash_0 = total_cash * weights[0]   # 策略11
    cash_1 = total_cash * weights[1]   # 策略12
    cash_2 = total_cash * weights[2]   # 策略13
    cash_3 = total_cash * weights[3]   # 策略14

    set_subportfolios([
        SubPortfolioConfig(cash=cash_0, type='stock'),
        SubPortfolioConfig(cash=cash_1, type='stock'),
        SubPortfolioConfig(cash=cash_2, type='stock'),
        SubPortfolioConfig(cash=cash_3, type='stock'),
    ])

    # 创建策略实例（每个策略独立子账户）
    g.strategies = [
        Strategy11(0, cash_0),
        Strategy12(1, cash_1),
        Strategy13(2, cash_2),
        Strategy14(3, cash_3),
    ]

    # 将策略11单独挂到g上，供全局函数调用
    g.s11 = g.strategies[0]

    # 为策略11预热
    g.s11.warmup(context)

    # ---------- 注册定时任务（使用全局函数） ----------
    run_daily(main_trade, time='14:00')

    # 策略11专用定时任务
    run_daily(s11_update_index_am, time='11:35', reference_security='000300.XSHG')
    run_daily(s11_update_index_pm, time='15:05', reference_security='000300.XSHG')
    run_daily(s11_execute_am_signal, time='13:05', reference_security='000300.XSHG')
    run_daily(s11_execute_pm_signal, time='9:35', reference_security='000300.XSHG')
    run_monthly(s11_monthly_rebalance, 1, time='10:00')
    run_daily(s11_prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    run_daily(s11_clear_just_sold, time='open')
    run_daily(s11_check_limit_up, time='13:30')
    run_daily(s11_after_market_close, time='after_close', reference_security='000300.XSHG')


def main_trade(context):
    for st in g.strategies:
        try:
            st.trade(context)
        except Exception as e:
            log.error('[%s] 交易异常: %s' % (st.name, str(e)))