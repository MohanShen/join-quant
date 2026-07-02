# Clone from JoinQuant
# postId: 36eeb73feab31e7f9b2323c3c350f11b
# backtestId: 9d3f352184055580513105958bb4e378
# title: 继上一篇文章按分钟回测版-2026年153%

# 低位3连阳首板接力 v29 - 放宽首板成交额上限
# 研究员: GPT5.5顶级研究员
#
# 单变量改动:
# - 在 v28 基线之上放宽首板日成交额上限
#
# 经济逻辑:
# - `v28` 已证明这条策略对“过强突破”原先有些过度保守
# - 那么首板日成交额上限 `30亿` 也可能在误杀一部分真正强势、但仍属于可接力区间的样本
# - 若放宽上限后收益和 Sharpe 继续提升, 说明主结构对强票的容忍度应再提高一点
#
# 实现方式:
# - 保留 v28 的所有条件
# - 仅将首板日成交额上限从 `30亿` 放宽到 `35亿`

from jqdata import *
import numpy as np
from datetime import time


def initialize(context):
    log.set_level("order", "error")
    set_option("use_real_price", True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.005))
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.0002,
            close_commission=0.0002,
            min_commission=5,
        ),
        type="stock",
    )
    set_benchmark("399303.XSHE")

    g.base_stocks = []
    g.pick_cache_date = ""
    g.today_pick = []
    g.information = {}
    g.minute_sell_cache = {}
    g.close_sell_cache = {}
    g.today_high = {}

    g.max_hold_count = 10
    g.max_position_pct = 1.0
    g.pre_breakout_amp_max = 0.06
    g.breakout_amp_ratio = 1.6
    g.first_board_money_max = 35e8

    run_weekly(prepare_base_stocks, 1, "09:10")
    run_daily(precompute_sell_cache, time="09:10")
    run_daily(buy_candidates, time="09:27")
    run_daily(intraday_take_profit, time="every_bar")
    run_daily(close_risk_control, time="11:25")
    run_daily(close_risk_control, time="13:30")
    run_daily(close_risk_control, time="14:55")


def get_stock_list(context):
    y_day = context.previous_date
    today_str = context.current_dt.strftime("%Y-%m-%d")

    candidates = detect_first_limit_up(context)
    log.info("[选股] 首板候选 %d 只" % len(candidates))
    if not candidates:
        return []

    candidates = filter_high_volatility(candidates, y_day)
    candidates = filter_market_cap(candidates, y_day)
    candidates = filter_volume_price(candidates, y_day)
    candidates = filter_auction(candidates, y_day, today_str)
    log.info("[选股] 最终入选 %s" % candidates)
    return candidates


def detect_first_limit_up(context):
    y_day = context.previous_date
    if not g.base_stocks:
        prepare_base_stocks(context)

    df = get_price(
        g.base_stocks,
        end_date=y_day,
        frequency="1d",
        fields=["close", "high_limit"],
        count=2,
        skip_paused=True,
        fill_paused=False,
        fq="pre",
        panel=False,
    )
    if df.empty or len(df) < 2:
        return []

    df["is_limit"] = np.isclose(df["close"], df["high_limit"], rtol=0.005, atol=0.01)
    groups = df[df["is_limit"]].groupby("time")["code"].apply(set)
    if len(groups) >= 2:
        return list(groups.iloc[-1] - groups.iloc[-2])
    if len(groups) == 1:
        return list(groups.iloc[-1])
    return []


def filter_high_volatility(stock_list, y_day):
    if not stock_list:
        return []

    df = get_price(
        stock_list,
        end_date=y_day,
        frequency="1d",
        fields=["high", "low"],
        count=5,
        skip_paused=True,
        fill_paused=False,
        panel=False,
    )
    if df.empty:
        return []

    grp = df.groupby("code")
    amp = (grp["high"].max() - grp["low"].min()) / grp["low"].min()
    return amp[amp <= 0.20].index.tolist()


def filter_market_cap(stock_list, y_day):
    if not stock_list:
        return []

    df = get_valuation(
        stock_list,
        start_date=y_day,
        end_date=y_day,
        fields=["market_cap", "circulating_market_cap"],
    )
    if df.empty:
        return []

    df = df.set_index("code")
    selected = df[
        (df["market_cap"] >= 30) &
        (df["circulating_market_cap"] <= 300)
    ]
    return selected.index.tolist()


def filter_volume_price(stock_list, y_day):
    if not stock_list:
        return []

    df = get_price(
        stock_list,
        end_date=y_day,
        frequency="1d",
        fields=["open", "close", "high", "low", "volume", "money"],
        count=35,
        skip_paused=True,
        fq="pre",
        panel=False,
    )
    if df.empty:
        return []

    selected = []
    for code, sub in df.groupby("code"):
        sub = sub.sort_values("time").reset_index(drop=True)
        if len(sub) < 6:
            continue

        t1 = sub.iloc[-1]
        t2 = sub.iloc[-2]
        t3 = sub.iloc[-3]
        t4 = sub.iloc[-4]

        if t1["money"] < 5e8 or t1["money"] > g.first_board_money_max:
            continue
        if t2["volume"] <= 0 or t1["volume"] < t2["volume"] * 2:
            continue
        if t3["volume"] <= 0 or t2["volume"] > t3["volume"] * 2:
            continue
        if not (t2["close"] > t2["open"] and t3["close"] > t3["open"]):
            continue
        if t3["close"] <= 0 or t4["close"] <= 0:
            continue

        g1 = (t2["close"] - t3["close"]) / t3["close"]
        g2 = (t3["close"] - t4["close"]) / t4["close"]
        if g1 >= 0.05 or g2 >= 0.05:
            continue

        # 新增: 首板前压缩, 首板日扩张
        amp1 = (t1["high"] - t1["low"]) / t1["low"] if t1["low"] > 0 else 0
        amp2 = (t2["high"] - t2["low"]) / t2["low"] if t2["low"] > 0 else 0
        amp3 = (t3["high"] - t3["low"]) / t3["low"] if t3["low"] > 0 else 0
        pre_amp = (amp2 + amp3) / 2.0
        if pre_amp <= 0:
            continue
        if pre_amp > g.pre_breakout_amp_max:
            continue
        if amp1 < pre_amp * g.breakout_amp_ratio:
            continue

        selected.append(code)

    return selected


def filter_auction(stock_list, y_day, today_str):
    if not stock_list:
        return []

    hist = get_price(
        stock_list,
        end_date=y_day,
        frequency="1d",
        fields=["close", "volume"],
        count=1,
        skip_paused=True,
        panel=False,
    )
    if hist.empty:
        return []

    hist_map = hist.set_index("code")[["close", "volume"]].to_dict("index")
    start = today_str + " 09:15:00"
    end = today_str + " 09:26:00"

    selected = []
    for stock in stock_list:
        if stock not in hist_map:
            continue
        y_close = hist_map[stock]["close"]
        y_volume = hist_map[stock]["volume"]
        if y_close <= 0 or y_volume <= 0:
            continue

        try:
            auction = get_call_auction(
                stock,
                start_date=start,
                end_date=end,
                fields=["time", "volume", "current"],
            )
        except Exception:
            continue

        if auction.empty:
            continue

        last_row = auction.iloc[-1]
        if last_row["volume"] / y_volume < 0.03:
            continue

        premium_ratio = last_row["current"] / y_close
        if premium_ratio <= 1.0 or premium_ratio >= 1.06:
            continue

        selected.append(stock)

    return selected


def buy_candidates(context):
    today_tag = context.current_dt.strftime("%Y%m%d")
    holdings = [
        stock for stock, pos in context.portfolio.positions.items()
        if pos.total_amount > 0
    ]
    if len(holdings) >= g.max_hold_count:
        return

    if g.pick_cache_date != today_tag:
        g.today_pick = get_stock_list(context)
        g.pick_cache_date = today_tag

    to_buy = [stock for stock in g.today_pick if stock not in holdings]
    if not to_buy:
        return

    slots = g.max_hold_count - len(holdings)
    to_buy = to_buy[:slots]
    each_cash = min(
        context.portfolio.available_cash / len(to_buy),
        context.portfolio.total_value * g.max_position_pct,
    )

    current_data = get_current_data()
    for stock in to_buy:
        data = current_data[stock]
        if data.paused or data.day_open <= 0:
            continue

        shares = int(each_cash / data.day_open / 100) * 100
        if shares < 100:
            continue

        order_value(stock, each_cash, MarketOrderStyle(data.day_open))
        g.information[stock] = {"buy_date": today_tag}


def intraday_take_profit(context):
    current_time = context.current_dt.time()
    if current_time < time(9, 30) or current_time > time(11, 25):
        return

    today_tag = context.current_dt.strftime("%Y%m%d")
    current_data = get_current_data()

    for stock, pos in context.portfolio.positions.items():
        if pos.total_amount <= 0:
            continue
        if g.information.get(stock, {}).get("buy_date") == today_tag:
            continue
        cache = g.minute_sell_cache.get(stock)
        if not cache or cache["date"] != context.previous_date:
            continue

        data = current_data[stock]
        if data.paused or pos.closeable_amount <= 0:
            continue

        current_price = data.last_price
        if current_price >= data.high_limit * 0.99 or cache["y_day_gain"] >= 0:
            continue

        today_high = max(g.today_high.get(stock, 0), current_price)
        g.today_high[stock] = today_high

        rally = (today_high - cache["y_close"]) / cache["y_close"] if cache["y_close"] > 0 else 0
        if rally <= 0.03:
            continue

        drawdown_limit = max(0.005, 0.02 - (rally - 0.01) * 0.5)
        if current_price < today_high * (1 - drawdown_limit):
            order_target_value(stock, 0)
            g.today_high.pop(stock, None)


def close_risk_control(context):
    today_tag = context.current_dt.strftime("%Y%m%d")
    current_data = get_current_data()

    for stock, pos in context.portfolio.positions.items():
        if pos.total_amount <= 0 or pos.closeable_amount <= 0:
            continue
        if g.information.get(stock, {}).get("buy_date") == today_tag:
            continue
        if stock not in g.close_sell_cache:
            continue

        data = current_data[stock]
        if data.paused:
            continue

        last_price = data.last_price
        if last_price >= data.high_limit * 0.99:
            continue

        y_close = g.close_sell_cache[stock]["y_close"]
        ma5 = g.close_sell_cache[stock]["ma5"]
        day_gain = (last_price - y_close) / y_close if y_close > 0 else 0
        pnl = (last_price - pos.avg_cost) / pos.avg_cost if pos.avg_cost > 0 else 0

        should_sell = (
            pnl > 0.5 or
            day_gain < -0.02 or
            last_price < data.day_open * 0.96 or
            pnl <= -0.07 or
            last_price < ma5 * 0.97
        )
        if should_sell:
            order_target_value(stock, 0)


def prepare_base_stocks(context):
    ref_date = get_trade_days(end_date=context.previous_date, count=50)[0]
    universe = get_all_securities(["stock"], date=ref_date).index.tolist()
    current_data = get_current_data()

    selected = []
    for stock in universe:
        data = current_data[stock]
        if stock[0] in "3489" or stock[:2] == "68":
            continue
        if data.is_st or data.paused:
            continue
        if "ST" in data.name or "退" in data.name:
            continue
        selected.append(stock)

    g.base_stocks = selected


def precompute_sell_cache(context):
    positions = list(context.portfolio.positions.keys())
    g.minute_sell_cache = {}
    g.close_sell_cache = {}
    g.today_high = {}

    if not positions:
        return

    df2 = get_price(
        positions,
        end_date=context.previous_date,
        frequency="1d",
        fields=["close"],
        count=2,
        skip_paused=False,
        fill_paused=True,
        panel=False,
    )
    if not df2.empty:
        for stock, closes in df2.groupby("code")["close"]:
            if len(closes) < 2:
                continue
            y_close = closes.iloc[-1]
            prev_close = closes.iloc[-2]
            g.minute_sell_cache[stock] = {
                "y_close": y_close,
                "prev_close": prev_close,
                "y_day_gain": (y_close - prev_close) / prev_close if prev_close > 0 else 0,
                "date": context.previous_date,
            }

    df5 = get_price(
        positions,
        end_date=context.previous_date,
        frequency="1d",
        fields=["close"],
        count=5,
        skip_paused=False,
        fill_paused=True,
        panel=False,
    )
    if not df5.empty:
        for stock, closes in df5.groupby("code")["close"]:
            if len(closes) < 2:
                continue
            g.close_sell_cache[stock] = {
                "y_close": closes.iloc[-1],
                "ma5": closes.mean(),
            }


def after_trading_end(context):
    current_positions = set(context.portfolio.positions.keys())
    g.information = {k: v for k, v in g.information.items() if k in current_positions}
    g.minute_sell_cache = {k: v for k, v in g.minute_sell_cache.items() if k in current_positions}
    g.close_sell_cache = {k: v for k, v in g.close_sell_cache.items() if k in current_positions}
    g.today_high = {}
