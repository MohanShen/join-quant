# Clone from JoinQuant
# postId: fb2cf5a642df783cee037e41407ac213
# backtestId: e2f843f5b3987205f7e4b427a452df66
# title: 红利低波全天候

from jqdata import *
import numpy as np
import pandas as pd
import datetime
import builtins


SCHEDULE = {
    'dividend_open_time': 'open',
    'dividend_close_time': 'close',
    'strategy1_generate_day': 1,
    'strategy1_generate_time': '9:10',
    'strategy1_sell_day': 1,
    'strategy1_sell_time': '14:20',
    'strategy1_buy_day': 1,
    'strategy1_buy_time': '14:21',
}

def initialize(context):
    # ==================================================================
    # 用户可调参数
    # ==================================================================
    g.etf = '512890.XSHG'
    
    # ---------- RSI类型 ----------
    g.use_tonghuashun_rsi = False
    
    # ---------- 买入参数 ----------
    g.cci_period = 14
    g.cci_threshold = -180
    
    # ---------- 分批买入 ----------
    g.BATCH_TIMES = 3
    g.BATCH_TARGET_PCT = 1.0
    g.BATCH_INTERVAL_DAYS = 1
    
    # ---------- 时间限制（新增） ----------
    g.min_hold_days = 3      # 买入后最少持有3个自然日才能卖出（含）
    g.min_wait_days = 2      # 卖出后最少等待2个自然日才能再次买入
    
    # ---------- 卖出参数 ----------
    g.long_term_ma = 260
    g.sell_start_ratio = 0.10
    g.sell_first_pct = 0.10
    g.sell_step_pct = 0.10
    g.sell_step_interval = 0.01
    g.forced_sell_days = 2
    g.forced_sell_pct = 0.10
    
    # ---------- RSI+布林清仓 ----------
    g.rsi_period = 12
    g.rsi_threshold = 70
    g.boll_period = 20
    g.boll_std = 2
    
    # ---------- 红利空仓期间的逆波动配置----------
    g.all_weather_assets = [
        '518880.XSHG',
        '161716.XSHE',  # 招商双债
        '159985.XSHE',  # 豆粕ETF
        '513100.XSHG',  # 纳指ETF
        '515450.XSHG',  # 红利低波ETF
    ]
    g.all_weather_bonds = {'511260.XSHG', '161716.XSHE'}
    g.all_weather_vol_lookback = 60
    g.all_weather_bond_penalty = 10.0
    g.all_weather_momentum_asset = '159915.XSHE'
    g.all_weather_roc_period = 20
    g.all_weather_roc_buy_threshold = 0.08
    g.all_weather_roc_sell_threshold = 0.0
    g.all_weather_momentum_signal = 0
    g.all_weather_cash_asset = '511880.XSHG'
    g.all_weather_active = False
    g.all_weather_targets = {}
    g.all_weather_pending_targets = {}
    g.all_weather_trade_ready = False

    # ==================================================================
    # 状态变量
    # ==================================================================
    g.initial_filled = False
    g.total_shares = 0
    g.last_sell_price_level = None
    g.no_step_days = 0
    g.is_waiting_sell = False
    g.sell_signal_day = None
    g.buy_plan_active = False
    g.buy_plan_step = 0
    g.buy_plan_total = 0.0
    g.buy_plan_amount = 0.0
    g.buy_plan_next_buy_date = None

    # 新增时间记录
    g.last_buy_date = None      # 最近一次买入（首次买入）的日期
    g.last_sell_date = None     # 最近一次清仓卖出的日期

    # 统计
    g.buy_stats = []
    g.sell_stats = []
    g.current_buy_stat = None
    g.current_sell_stat = None
    g.cycle_active = False

    # 回测结束日期
    all_hist = get_price(g.etf, count=10000, frequency='1d', fields=['close'], skip_paused=True, fq='pre')
    g.end_date = all_hist.index[-1].date() if len(all_hist) > 0 else None
    g.etf_listed_date = get_security_info(g.etf).start_date
    log.info("ETF {} 上市日期: {}".format(g.etf, g.etf_listed_date))
    set_benchmark(g.etf)

    run_daily(run_open_strategies, time=SCHEDULE['dividend_open_time'])
    run_monthly(all_weather_generate_targets, SCHEDULE['strategy1_generate_day'],
                time=SCHEDULE['strategy1_generate_time'], reference_security='000300.XSHG')
    run_monthly(all_weather_sell, SCHEDULE['strategy1_sell_day'],
                time=SCHEDULE['strategy1_sell_time'], reference_security='000300.XSHG')
    run_monthly(all_weather_buy, SCHEDULE['strategy1_buy_day'],
                time=SCHEDULE['strategy1_buy_time'], reference_security='000300.XSHG')
    run_daily(check_and_execute_sell_at_close, time=SCHEDULE['dividend_close_time'])
    run_daily(final_report, time=SCHEDULE['dividend_close_time'])


# ============================================================
# RSI计算函数（两种风格）
# ============================================================
def run_open_strategies(context):
    # 明确执行顺序：先处理红利信号，再判断是否进入空仓配置。
    check_strategy_at_open(context)
    enter_all_weather_when_flat(context)


def calc_rsi_simple(data, window):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_rsi_tonghuashun(data, window):
    delta = data.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    rsi_vals = [np.nan] * len(data)
    if len(data) <= window:
        return pd.Series(rsi_vals, index=data.index)
    avg_gain = gain.iloc[1:window+1].mean()
    avg_loss = loss.iloc[1:window+1].mean()
    for i in range(window, len(data)):
        if i == window:
            g_ = avg_gain
            l_ = avg_loss
        else:
            g_ = (g_ * (window - 1) + gain.iloc[i]) / window
            l_ = (l_ * (window - 1) + loss.iloc[i]) / window
        if l_ == 0:
            rsi = 100.0
        else:
            rsi = 100.0 - (100.0 / (1.0 + g_/l_))
        rsi_vals[i] = rsi
    return pd.Series(rsi_vals, index=data.index)


def check_strategy_at_open(context):
    """开盘时运行：初始满仓、买入计划、阶梯卖出、RSI+布林初筛"""
    # ---------- 初始满仓 ----------
    if not g.initial_filled and context.current_dt.date() >= g.etf_listed_date:
        current_price = get_current_data()[g.etf].day_open
        if current_price is not None and current_price > 0:
            cash = context.portfolio.available_cash
            if cash > 0:
                order_value(g.etf, cash)
                g.initial_filled = True
                if g.etf in context.portfolio.positions:
                    g.total_shares = context.portfolio.positions[g.etf].total_amount
                else:
                    g.total_shares = 0
                log.info(f"【初始满仓】买入，价格 {current_price:.3f}，股数 {g.total_shares}")
                return

    if not g.initial_filled:
        return

    current_price = get_current_data()[g.etf].day_open
    if current_price is None or np.isnan(current_price) or current_price <= 0:
        return

    # ---------- 获取历史数据 ----------
    need_len = max(g.cci_period, g.long_term_ma, g.rsi_period, g.boll_period) + 100
    hist_data = get_price(g.etf, end_date=context.previous_date, count=need_len,
                         frequency='1d', fields=['close', 'high', 'low'],
                         skip_paused=True, fq='pre')
    if len(hist_data) < need_len:
        return

    # ---------- 昨日CCI ----------
    tp_series = (hist_data['high'] + hist_data['low'] + hist_data['close']) / 3
    tp_ma = tp_series.rolling(window=g.cci_period).mean()
    mean_dev = tp_series.rolling(window=g.cci_period).apply(
        lambda x: np.mean(np.abs(x - x.mean())), raw=True
    )
    cci_series = (tp_series - tp_ma) / (0.015 * mean_dev)
    yesterday_cci = cci_series.iloc[-1] if len(cci_series) >= 1 else None

    # ---------- 260日均线 ----------
    ma260 = hist_data['close'].rolling(window=g.long_term_ma).mean().iloc[-1]
    if pd.isna(ma260):
        return

    # ---------- 昨日RSI ----------
    if g.use_tonghuashun_rsi:
        rsi_series = calc_rsi_tonghuashun(hist_data['close'], g.rsi_period)
    else:
        rsi_series = calc_rsi_simple(hist_data['close'], g.rsi_period)
    yesterday_rsi = rsi_series.iloc[-1] if len(rsi_series) >= 1 and not pd.isna(rsi_series.iloc[-1]) else None

    # ---------- 布林上轨 ----------
    ma_boll = hist_data['close'].rolling(window=g.boll_period).mean()
    std_boll = hist_data['close'].rolling(window=g.boll_period).std()
    upper_band = ma_boll + g.boll_std * std_boll
    yesterday_upper = upper_band.iloc[-1] if len(upper_band) >= 1 else None
    yesterday_close = hist_data['close'].iloc[-1] if len(hist_data) >= 1 else None
    day_before_close = hist_data['close'].iloc[-2] if len(hist_data) >= 2 else None
    day_before_upper = upper_band.iloc[-2] if len(upper_band) >= 2 else None

    boll_break = False
    if yesterday_upper is not None and day_before_upper is not None:
        boll_break = (yesterday_close < yesterday_upper) and (day_before_close >= day_before_upper)

    # ---------- 持仓和现金 ----------
    if g.etf in context.portfolio.positions:
        position = context.portfolio.positions[g.etf]
        current_shares = position.total_amount
    else:
        current_shares = 0
    cash = context.portfolio.available_cash

    # ==================================================================
    # 分批买入计划（新增等待卖出后冷却期检查）
    # ==================================================================
    # 检查是否满足等待期：如果上次卖出日期距今小于 min_wait_days，禁止买入
    can_buy = True
    if g.last_sell_date is not None:
        days_since_sell = (context.current_dt.date() - g.last_sell_date).days
        if days_since_sell < g.min_wait_days:
            can_buy = False
            # log.info(f"【等待期】卖出后仅{days_since_sell}天，小于{ g.min_wait_days}天，暂不触发买入")

    if not g.buy_plan_active and (cash > 0 or g.all_weather_active) and can_buy:
        if yesterday_cci is not None and yesterday_cci < g.cci_threshold:
            g.buy_plan_active = True
            g.buy_plan_step = 0
            g.buy_plan_total = context.portfolio.portfolio_value
            g.buy_plan_amount = g.buy_plan_total * (g.BATCH_TARGET_PCT / g.BATCH_TIMES)
            g.buy_plan_next_buy_date = context.current_dt.date()
            # 记录买入日期（首次触发）
            g.last_buy_date = context.current_dt.date()
            # 清除上次卖出日期（因为现在买入了）
            g.last_sell_date = None
            log.info(f"【买入计划触发】昨日CCI={yesterday_cci:.2f}，将于今日开始分批买入")

            if g.current_sell_stat is not None:
                if g.current_sell_stat['low_price'] is None:
                    g.current_sell_stat['low_price'] = current_price
                    g.current_sell_stat['low_date'] = context.current_dt.date()
                    g.current_sell_stat['days'] = (context.current_dt.date() - g.current_sell_stat['start_date']).days
                fall = (g.current_sell_stat['low_price'] - g.current_sell_stat['start_price']) / g.current_sell_stat['start_price']
                g.current_sell_stat['fall_pct'] = fall
                g.sell_stats.append(g.current_sell_stat)
                g.current_sell_stat = None

            g.current_buy_stat = {
                'start_date': context.current_dt.date(),
                'start_price': current_price,
                'high_price': current_price,
                'high_date': context.current_dt.date(),
                'days': 0,
                'rise_pct': 0.0
            }
            g.cycle_active = True

    # 资金可能仍在逆波动组合中；清完实际持仓后才开始原分批计划。
    if g.buy_plan_active and g.all_weather_active:
        if not exit_all_weather(context):
            return
        cash = context.portfolio.available_cash

    # 执行分批买入
    if g.buy_plan_active and g.buy_plan_step < g.BATCH_TIMES:
        if context.current_dt.date() >= g.buy_plan_next_buy_date:
            amount = min(g.buy_plan_amount, cash)
            if amount > 0:
                order_value(g.etf, amount)
                if g.etf in context.portfolio.positions:
                    g.total_shares = context.portfolio.positions[g.etf].total_amount
                else:
                    g.total_shares = 0
                g.buy_plan_step += 1
                log.info(f"【分批买入】第{g.buy_plan_step}批，金额{amount:.2f}")
                if g.buy_plan_step == 1:
                    g.last_sell_price_level = None
                    g.no_step_days = 0
                g.buy_plan_next_buy_date = context.current_dt.date() + datetime.timedelta(days=g.BATCH_INTERVAL_DAYS)
                if g.buy_plan_step >= g.BATCH_TIMES:
                    g.buy_plan_active = False
                    log.info("【分批买入完成】")
                return
            else:
                log.warning("【分批买入】现金不足，终止计划")
                g.buy_plan_active = False
                return

    if g.buy_plan_active and g.buy_plan_step >= g.BATCH_TIMES:
        g.buy_plan_active = False

    if g.buy_plan_active:
        return

    # 逆波动模式中的资产由独立配置管理，不套用红利卖出规则。
    if g.all_weather_active:
        return

    # ==================================================================
    # RSI+布林初筛（仅当满足持有期条件时进入等待）
    # ==================================================================
    if not g.is_waiting_sell and current_shares > 0:
        # 检查是否满足最低持有期，如果不满足则不触发卖出信号
        hold_ok = True
        if g.last_buy_date is not None:
            days_held = (context.current_dt.date() - g.last_buy_date).days
            if days_held < g.min_hold_days:
                hold_ok = False
                # log.info(f"【持有期】仅持有{days_held}天，小于{ g.min_hold_days}天，不触发RSI卖出")
        if hold_ok and (yesterday_rsi is not None and yesterday_rsi > g.rsi_threshold) and boll_break:
            g.is_waiting_sell = True
            g.sell_signal_day = context.current_dt.date()
            log.info(f"【RSI+布林初筛】昨日RSI={yesterday_rsi:.2f} > {g.rsi_threshold}且跌破上轨，等待今日收盘确认")
            g.current_sell_stat = {
                'start_date': context.current_dt.date(),
                'start_price': current_price,
                'low_price': current_price,
                'low_date': context.current_dt.date(),
                'days': 0,
                'fall_pct': 0.0
            }

    if g.is_waiting_sell:
        return

    # ==================================================================
    # 260日线阶梯卖出（检查持有期）
    # ==================================================================
    if current_shares > 0 and current_price > ma260 * (1 + g.sell_start_ratio):
        # 检查持有期
        hold_ok = True
        if g.last_buy_date is not None:
            days_held = (context.current_dt.date() - g.last_buy_date).days
            if days_held < g.min_hold_days:
                hold_ok = False
                # log.info(f"【持有期】仅持有{days_held}天，小于{ g.min_hold_days}天，不执行阶梯卖出")
        if hold_ok:
            current_level = current_price / ma260
            start_level = 1 + g.sell_start_ratio
            sell_pct = 0

            if g.last_sell_price_level is None:
                steps = int((current_level - start_level) / g.sell_step_interval)
                sell_pct = min(1.0, g.sell_first_pct + steps * g.sell_step_pct)
                g.last_sell_price_level = start_level + steps * g.sell_step_interval
                log.info(f"【首次合并卖出】超出{steps}个阶梯，卖出比例 {sell_pct:.0%}")
            else:
                steps = int((current_level - start_level) / g.sell_step_interval)
                last_steps = int((g.last_sell_price_level - start_level) / g.sell_step_interval) if g.last_sell_price_level >= start_level else -1
                new_steps = steps - last_steps
                if new_steps > 0:
                    sell_pct = new_steps * g.sell_step_pct
                    g.last_sell_price_level = start_level + steps * g.sell_step_interval
                    log.info(f"【阶梯合并卖出】新增{new_steps}个阶梯，卖出比例 {sell_pct:.0%}")
                else:
                    g.no_step_days += 1
                    log.info(f"【横盘计数】{g.no_step_days}天")
                    if g.no_step_days >= g.forced_sell_days:
                        sell_pct = g.forced_sell_pct
                        log.info(f"【强制卖出】横盘{g.no_step_days}天，卖出比例 {sell_pct:.0%}")
                        g.no_step_days = 0

            if sell_pct > 0:
                if g.current_buy_stat is not None and g.cycle_active:
                    if g.current_buy_stat['high_price'] is None:
                        g.current_buy_stat['high_price'] = current_price
                        g.current_buy_stat['high_date'] = context.current_dt.date()
                        g.current_buy_stat['days'] = (context.current_dt.date() - g.current_buy_stat['start_date']).days
                    rise = (g.current_buy_stat['high_price'] - g.current_buy_stat['start_price']) / g.current_buy_stat['start_price']
                    g.current_buy_stat['rise_pct'] = rise
                    g.buy_stats.append(g.current_buy_stat)
                    g.current_buy_stat = None
                    g.cycle_active = False

                sell_shares = int(g.total_shares * sell_pct)
                if sell_shares > 0:
                    sell_shares = min(sell_shares, current_shares)
                    order_target_value(g.etf, (current_shares - sell_shares) * current_price)
                    if g.etf in context.portfolio.positions:
                        g.total_shares = context.portfolio.positions[g.etf].total_amount
                    else:
                        g.total_shares = 0
                    # 若清仓，记录卖出日期并重置买入日期
                    if g.total_shares == 0:
                        g.last_sell_date = context.current_dt.date()
                        g.last_buy_date = None
                        g.last_sell_price_level = None
                        g.no_step_days = 0
                        g.buy_plan_active = False
                        g.buy_plan_step = 0
                        if g.current_sell_stat is not None:
                            if g.current_sell_stat['low_price'] is None:
                                g.current_sell_stat['low_price'] = current_price
                                g.current_sell_stat['low_date'] = context.current_dt.date()
                                g.current_sell_stat['days'] = (context.current_dt.date() - g.current_sell_stat['start_date']).days
                            fall = (g.current_sell_stat['low_price'] - g.current_sell_stat['start_price']) / g.current_sell_stat['start_price']
                            g.current_sell_stat['fall_pct'] = fall
                            g.sell_stats.append(g.current_sell_stat)
                            g.current_sell_stat = None
                    log.info(f"【阶梯卖出执行】卖出 {sell_shares} 股，剩余 {g.total_shares} 股")


def check_and_execute_sell_at_close(context):
    """收盘时确认RSI+布林清仓（检查持有期）"""
    if not g.is_waiting_sell:
        return

    need_len = max(g.rsi_period, g.boll_period) + 20
    hist_data = get_price(g.etf, end_date=context.current_dt, count=need_len,
                         frequency='1d', fields=['close', 'high', 'low'],
                         skip_paused=True, fq='pre')
    if len(hist_data) < 2:
        return

    today_close = hist_data['close'].iloc[-1]
    if np.isnan(today_close) or today_close <= 0:
        return

    # 今日RSI
    if g.use_tonghuashun_rsi:
        rsi_series = calc_rsi_tonghuashun(hist_data['close'], g.rsi_period)
    else:
        rsi_series = calc_rsi_simple(hist_data['close'], g.rsi_period)
    today_rsi = rsi_series.iloc[-1] if len(rsi_series) >= 1 and not pd.isna(rsi_series.iloc[-1]) else None

    # 今日布林上轨
    ma_boll = hist_data['close'].rolling(window=g.boll_period).mean()
    std_boll = hist_data['close'].rolling(window=g.boll_period).std()
    upper_band = ma_boll + g.boll_std * std_boll
    today_upper = upper_band.iloc[-1] if len(upper_band) >= 1 else None
    boll_below = today_close < today_upper if today_upper is not None else False

    if today_rsi is not None and today_rsi > g.rsi_threshold and boll_below:
        # 检查持有期
        hold_ok = True
        if g.last_buy_date is not None:
            days_held = (context.current_dt.date() - g.last_buy_date).days
            if days_held < g.min_hold_days:
                hold_ok = False
                log.info(f"【持有期限制】仅持有{days_held}天，不足{ g.min_hold_days}天，RSI清仓信号被忽略")
        if hold_ok:
            if g.etf in context.portfolio.positions:
                position = context.portfolio.positions[g.etf]
                current_shares = position.total_amount
                if current_shares > 0:
                    order_target_value(g.etf, 0)
                    g.total_shares = 0
                    # 记录卖出日期，清除买入日期
                    g.last_sell_date = context.current_dt.date()
                    g.last_buy_date = None
                    g.last_sell_price_level = None
                    g.no_step_days = 0
                    g.buy_plan_active = False
                    g.buy_plan_step = 0

                    if g.current_buy_stat is not None:
                        if g.current_buy_stat['high_price'] is None:
                            g.current_buy_stat['high_price'] = today_close
                            g.current_buy_stat['high_date'] = context.current_dt.date()
                            g.current_buy_stat['days'] = (context.current_dt.date() - g.current_buy_stat['start_date']).days
                        rise = (g.current_buy_stat['high_price'] - g.current_buy_stat['start_price']) / g.current_buy_stat['start_price']
                        g.current_buy_stat['rise_pct'] = rise
                        g.buy_stats.append(g.current_buy_stat)
                        g.current_buy_stat = None
                        g.cycle_active = False

                    if g.current_sell_stat is not None:
                        if g.current_sell_stat['low_price'] is None:
                            g.current_sell_stat['low_price'] = today_close
                            g.current_sell_stat['low_date'] = context.current_dt.date()
                            g.current_sell_stat['days'] = (context.current_dt.date() - g.current_sell_stat['start_date']).days
                        fall = (g.current_sell_stat['low_price'] - g.current_sell_stat['start_price']) / g.current_sell_stat['start_price']
                        g.current_sell_stat['fall_pct'] = fall
                        g.sell_stats.append(g.current_sell_stat)
                        g.current_sell_stat = None

                    log.info(f"【RSI+布林双重确认清仓】今日RSI={today_rsi:.2f} > {g.rsi_threshold}，清仓卖出 {current_shares} 股")
        else:
            log.info(f"【RSI+布林清仓】因持有期不足，放弃清仓")

    g.is_waiting_sell = False
    g.sell_signal_day = None


def final_report(context):
    """回测最后一天输出统计"""
    if g.end_date is None or context.current_dt.date() != g.end_date:
        return

    if g.current_buy_stat is not None:
        if g.current_buy_stat['high_price'] is None:
            current_price = get_current_data()[g.etf].close
            if current_price is not None:
                g.current_buy_stat['high_price'] = current_price
                g.current_buy_stat['high_date'] = context.current_dt.date()
                g.current_buy_stat['days'] = (context.current_dt.date() - g.current_buy_stat['start_date']).days
        if g.current_buy_stat['high_price'] is not None:
            rise = (g.current_buy_stat['high_price'] - g.current_buy_stat['start_price']) / g.current_buy_stat['start_price']
            g.current_buy_stat['rise_pct'] = rise
            g.buy_stats.append(g.current_buy_stat)
            g.current_buy_stat = None

    if g.current_sell_stat is not None:
        if g.current_sell_stat['low_price'] is None:
            current_price = get_current_data()[g.etf].close
            if current_price is not None:
                g.current_sell_stat['low_price'] = current_price
                g.current_sell_stat['low_date'] = context.current_dt.date()
                g.current_sell_stat['days'] = (context.current_dt.date() - g.current_sell_stat['start_date']).days
        if g.current_sell_stat['low_price'] is not None:
            fall = (g.current_sell_stat['low_price'] - g.current_sell_stat['start_price']) / g.current_sell_stat['start_price']
            g.current_sell_stat['fall_pct'] = fall
            g.sell_stats.append(g.current_sell_stat)
            g.current_sell_stat = None

    if g.buy_stats:
        avg_rise = np.mean([s['rise_pct'] for s in g.buy_stats]) * 100
        avg_days = np.mean([s['days'] for s in g.buy_stats])
        log.info(f"【统计】买入信号后最大涨幅平均值：{avg_rise:.2f}%，平均到达天数：{avg_days:.1f}天")
        log.info(f"【统计】买入统计样本数：{len(g.buy_stats)}")

    if g.sell_stats:
        avg_fall = np.mean([s['fall_pct'] for s in g.sell_stats]) * 100
        avg_sell_days = np.mean([s['days'] for s in g.sell_stats])
        log.info(f"【统计】卖出信号后最大跌幅平均值：{avg_fall:.2f}%，平均到达天数：{avg_sell_days:.1f}天")
        log.info(f"【统计】卖出统计样本数：{len(g.sell_stats)}")

# ============================================================
# 红利空仓配置：五合一策略1的逆波动算法，使用当前账户全部资金
# ============================================================

def all_weather_price_series(security, end_date, count, field='close'):
    data = get_price(
        security,
        end_date=end_date,
        frequency='daily',
        fields=[field],
        count=count,
    )
    if data is None or field not in data:
        return pd.Series(dtype=float)
    return data[field].dropna()


def update_all_weather_momentum_signal(context):
    closes = all_weather_price_series(
        g.all_weather_momentum_asset,
        context.previous_date,
        g.all_weather_roc_period + 1,
    )
    if len(closes) < g.all_weather_roc_period + 1:
        return g.all_weather_momentum_signal

    roc = closes.iloc[-1] / closes.iloc[0] - 1
    if roc > g.all_weather_roc_buy_threshold:
        g.all_weather_momentum_signal = 1
    elif roc < g.all_weather_roc_sell_threshold:
        g.all_weather_momentum_signal = 0
    return g.all_weather_momentum_signal


def calculate_all_weather_weights(context):
    active_assets = list(g.all_weather_assets)
    if update_all_weather_momentum_signal(context) == 1:
        active_assets.append(g.all_weather_momentum_asset)

    volatilities = {}
    for security in active_assets:
        closes = all_weather_price_series(
            security,
            context.previous_date,
            g.all_weather_vol_lookback + 1,
        )
        if len(closes) < g.all_weather_vol_lookback + 1:
            continue

        volatility = closes.pct_change().dropna().std()
        if security in g.all_weather_bonds:
            volatility *= g.all_weather_bond_penalty
        if np.isfinite(volatility) and volatility > 0:
            volatilities[security] = float(volatility)

    if not volatilities:
        return {}

    inverse_vol = {
        security: 1.0 / volatility
        for security, volatility in volatilities.items()
    }
    total_inverse_vol = builtins.sum(inverse_vol.values())
    return {
        security: value / total_inverse_vol
        for security, value in inverse_vol.items()
    }


def _all_weather_target_weights(context):
    targets = calculate_all_weather_weights(context)
    unallocated = max(0.0, 1.0 - builtins.sum(targets.values()))
    if unallocated > 0:
        targets[g.all_weather_cash_asset] = targets.get(g.all_weather_cash_asset, 0.0) + unallocated
    return targets


def _all_weather_tradeable(security, is_buy):
    current = get_current_data()[security]
    if current.paused or not np.isfinite(current.last_price):
        return False
    if is_buy and current.last_price >= current.high_limit:
        return False
    if not is_buy and current.last_price <= current.low_limit:
        return False
    return True


def _all_weather_order(context, security, value):
    order = order_target_value(security, value)
    if order is None:
        log.warning('【空仓配置】未生成订单：%s，目标市值 %.2f' % (security, value))
    return order


def _all_weather_execute_sell(context):
    total_value = context.portfolio.total_value
    current_data = get_current_data()
    for security, position in list(context.portfolio.positions.items()):
        target_value = total_value * g.all_weather_targets.get(security, 0.0)
        if position.value <= target_value or not _all_weather_tradeable(security, False):
            continue
        price = current_data[security].last_price
        if target_value == 0 or position.value - target_value > price * 100:
            _all_weather_order(context, security, target_value)


def _all_weather_execute_buy(context):
    total_value = context.portfolio.total_value
    current_data = get_current_data()
    targets = sorted(g.all_weather_targets.items(), key=lambda item: item[0] == g.all_weather_cash_asset)
    for security, weight in targets:
        position = context.portfolio.positions.get(security)
        current_value = position.value if position is not None else 0.0
        target_value = total_value * weight
        if current_value >= target_value or not _all_weather_tradeable(security, True):
            continue
        price = current_data[security].last_price
        if min(target_value - current_value, context.portfolio.available_cash) > price * 100:
            _all_weather_order(context, security, target_value)


def enter_all_weather_when_flat(context):
    """仅红利完全空仓且没有买入计划时进入；收盘清仓在次日开盘处理。"""
    if not g.initial_filled or g.all_weather_active or g.buy_plan_active:
        return
    position = context.portfolio.positions.get(g.etf)
    if position is not None and position.total_amount > 0:
        return
    g.all_weather_targets = _all_weather_target_weights(context)
    g.all_weather_pending_targets = {}
    g.all_weather_trade_ready = False
    g.all_weather_active = True
    log.info('【空仓配置】红利已空仓，进入逆波动组合')
    _all_weather_execute_sell(context)
    _all_weather_execute_buy(context)


def all_weather_generate_targets(context):
    if not g.all_weather_active or g.buy_plan_active:
        return
    g.all_weather_pending_targets = _all_weather_target_weights(context)
    g.all_weather_trade_ready = True


def all_weather_sell(context):
    if not g.all_weather_active or g.buy_plan_active or not g.all_weather_trade_ready:
        return
    g.all_weather_targets = dict(g.all_weather_pending_targets)
    _all_weather_execute_sell(context)


def all_weather_buy(context):
    if not g.all_weather_active or g.buy_plan_active or not g.all_weather_trade_ready:
        return
    _all_weather_execute_buy(context)
    g.all_weather_trade_ready = False


def exit_all_weather(context):
    """CCI已触发买入计划：先清配置，未成交的部分下次开盘继续处理。"""
    g.all_weather_pending_targets = {}
    g.all_weather_trade_ready = False
    for security, position in list(context.portfolio.positions.items()):
        if position.total_amount > 0 and _all_weather_tradeable(security, False):
            _all_weather_order(context, security, 0)
    # 根据实际持仓确认退出，不能把提交清仓订单当成清仓成交。
    if builtins.any(position.total_amount > 0 for position in context.portfolio.positions.values()):
        log.info('【空仓配置】尚有未卖出持仓，等待清完后执行红利分批买入')
        return False
    g.all_weather_active = False
    g.all_weather_targets = {}
    log.info('【空仓配置】已退出，开始执行红利分批买入')
    return True
