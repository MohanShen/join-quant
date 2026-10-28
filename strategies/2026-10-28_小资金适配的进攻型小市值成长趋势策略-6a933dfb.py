# Clone from JoinQuant
# postId: 6a933dfb8d4b8034ce2cdd0ef09543f7
# backtestId: dc05fd3c6cbd4089a91ce83c7d15ff55
# title: 小资金适配的进攻型小市值成长趋势策略

from jqdata import *
from jqfactor import *
import numpy as np
import datetime as dt


def initialize(context):
    """
    3-5万资金适配版：
    1. 更少持仓，避免资金被切碎
    2. 更偏低价强势票，确保能更充分买入
    3. 仍以小市值成长为主线，但仓位更集中
    """
    set_benchmark("000905.XSHG")
    set_option("use_real_price", True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0))
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
    log.set_level("order", "error")

    # 根据起始资金动态决定持仓数
    start_cash = getattr(context.portfolio, "starting_cash", 0)
    if start_cash <= 35000:
        g.stock_num = 2
    elif start_cash <= 60000:
        g.stock_num = 3
    else:
        g.stock_num = 4

    # 持仓与候选池
    g.max_candidates = 260
    g.min_days_listed = 250
    g.keep_rank_multiple = 2
    g.hot_theme_sample_size = 80
    g.hot_strength_lookback = 30

    # 基本面门槛
    g.min_profit_growth = 8
    g.min_revenue_growth = 4
    g.min_roe = 5
    g.max_debt_to_assets = 0.70
    g.max_peg = 3.2

    # 小资金更适合低价、流动性足够的票
    g.min_avg_money_20 = 12000000
    g.max_volatility_20 = 0.085
    g.max_price_to_buy = 40
    g.min_breakout_60 = -0.10
    g.hot_keyword_top_n = 8
    g.hot_industry_top_n = 6
    g.hot_keyword_bonus_per_hit = 0.02
    g.hot_industry_bonus_per_hit = 0.03
    g.hot_keyword_names = []
    g.hot_industry_names = []
    g.enable_hot_keyword_bonus = True
    g.enable_hot_industry_bonus = True

    # 风控参数
    g.timing_index = "000905.XSHG"
    g.stop_loss_pct = 0.15
    g.take_profit_drawdown_pct = 0.12
    g.max_return_for_trailing = 0.28
    g.max_single_stock_weight = 0.68
    g.max_price = {}
    g.atr_period = 14
    g.atr_multiplier = 2.2
    g.atr_stop_prices = {}
    g.enable_cost_protection = True
    g.cost_protection_profit_threshold_1 = 0.15
    g.cost_protection_profit_threshold_2 = 0.30
    g.cost_protection_stop_line_1 = 0.00
    g.cost_protection_stop_line_2 = 0.10

    run_daily(before_market_open, time="09:05")
    run_weekly(weekly_rebalance, 1, time="09:35")
    run_daily(update_atr_stop_prices, time="10:05")
    run_daily(update_atr_stop_prices, time="14:05")
    run_daily(check_stop_loss, time="10:30")
    run_daily(check_stop_loss, time="14:30")
    run_daily(print_position_info, time="15:10")


def before_market_open(context):
    refresh_max_price(context)


def weekly_rebalance(context):
    if is_extreme_risk_off(context):
        clear_all_positions(context)
        log.info("当前市场极弱，执行空仓保护")
        return

    ranked_list = get_ranked_stocks(context)
    if not ranked_list:
        return

    target_list = ranked_list[:g.stock_num]
    keep_list = ranked_list[: max(g.stock_num * g.keep_rank_multiple, g.stock_num)]

    for stock in list(context.portfolio.positions.keys()):
        if stock not in keep_list:
            order_target_value_safely(stock, 0)
            g.max_price.pop(stock, None)

    total_value = context.portfolio.total_value
    weights = get_rank_weights(len(target_list))
    for stock, weight in zip(target_list, weights):
        order_target_value_safely(stock, total_value * min(weight, g.max_single_stock_weight))


def is_extreme_risk_off(context):
    prices = get_price(
        g.timing_index,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close"],
        count=130,
        panel=False,
    )
    if prices is None or len(prices) < 120:
        return False

    closes = prices["close"].values
    close_now = closes[-1]
    ma20 = closes[-20:].mean()
    ma60 = closes[-60:].mean()
    ma120 = closes[-120:].mean()
    return close_now < ma120 * 0.92 and close_now < ma60 and ma20 < ma60


def get_ranked_stocks(context):
    stock_list = get_all_securities("stock", context.previous_date).index.tolist()
    stock_list = filter_new_stock(stock_list, context.previous_date, g.min_days_listed)
    stock_list = filter_kcbj_stock(stock_list)
    stock_list = filter_st_stock(stock_list)
    stock_list = filter_paused_stock(stock_list)
    if not stock_list:
        return []

    q = query(
        valuation.code,
        valuation.market_cap,
        valuation.circulating_market_cap,
        valuation.pe_ratio,
        indicator.eps,
        indicator.inc_net_profit_year_on_year,
        indicator.inc_revenue_year_on_year,
        indicator.roe,
        balance.total_liability,
        balance.total_assets,
    ).filter(
        valuation.code.in_(stock_list),
        valuation.pe_ratio > 0,
        indicator.eps > 0,
        indicator.inc_net_profit_year_on_year > g.min_profit_growth,
        indicator.inc_revenue_year_on_year > g.min_revenue_growth,
        indicator.roe > g.min_roe,
        balance.total_assets > 0,
    ).order_by(
        valuation.market_cap.asc()
    ).limit(g.max_candidates)

    df = get_fundamentals(q, date=context.previous_date)
    if df is None or df.empty:
        return []

    df = df.dropna()
    if df.empty:
        return []

    df["debt_to_assets"] = df["total_liability"] / df["total_assets"]
    df = df[df["debt_to_assets"] < g.max_debt_to_assets]
    if df.empty:
        return []

    df["peg"] = df["pe_ratio"] / df["inc_net_profit_year_on_year"]
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    df = df[(df["peg"] > 0) & (df["peg"] < g.max_peg)]
    if df.empty:
        return []

    df = add_price_features(context, df)
    if df.empty:
        return []

    df = add_hot_theme_bonus(context, df)
    if df.empty:
        return []

    df["score"] = (
        -df["market_cap"].rank(pct=True) * 0.22
        - df["circulating_market_cap"].rank(pct=True) * 0.10
        + df["eps"].rank(pct=True) * 0.16
        + df["inc_net_profit_year_on_year"].rank(pct=True) * 0.20
        + df["inc_revenue_year_on_year"].rank(pct=True) * 0.16
        + df["roe"].rank(pct=True) * 0.04
        - df["peg"].rank(pct=True) * 0.10
        - df["close_now"].rank(pct=True) * 0.05
        + df["momentum_20"].rank(pct=True) * 0.09
        + df["momentum_60"].rank(pct=True) * 0.05
        + df["breakout_60"].rank(pct=True) * 0.06
        - df["volatility_20"].rank(pct=True) * 0.06
        + df["hot_keyword_bonus"]
        + df["hot_industry_bonus"]
    )

    df = df.sort_values("score", ascending=False)
    ranked_list = list(df["code"])
    ranked_list = filter_limitup_stock(context, ranked_list)
    ranked_list = filter_limitdown_stock(context, ranked_list)
    return ranked_list


def add_price_features(context, df):
    codes = list(df["code"])
    if not codes:
        return df.iloc[0:0]

    price_df = get_price(
        codes,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close", "money"],
        count=70,
        panel=False,
        fill_paused=False,
        skip_paused=True,
    )
    if price_df is None or price_df.empty:
        return df.iloc[0:0]

    momentum_20 = {}
    momentum_60 = {}
    breakout_60 = {}
    avg_money_20 = {}
    volatility_20 = {}
    trend_ok = {}
    close_now_map = {}

    for code in codes:
        sub = price_df[price_df["code"] == code]
        if "time" in sub.columns:
            sub = sub.sort_values("time")
        elif "datetime" in sub.columns:
            sub = sub.sort_values("datetime")
        elif "date" in sub.columns:
            sub = sub.sort_values("date")
        else:
            sub = sub.sort_index()
        if len(sub) < 61:
            continue

        close_list = list(sub["close"])
        money_list = list(sub["money"])
        close_now = close_list[-1]
        ma20 = np.mean(close_list[-20:])
        ma60 = np.mean(close_list[-60:])
        high60 = max(close_list[-60:])

        momentum_20[code] = close_now / close_list[-21] - 1 if close_list[-21] > 0 else np.nan
        momentum_60[code] = close_now / close_list[-61] - 1 if close_list[-61] > 0 else np.nan
        breakout_60[code] = close_now / high60 - 1 if high60 > 0 else np.nan
        avg_money_20[code] = np.mean(money_list[-20:])
        close_now_map[code] = close_now

        ret_20 = np.array(close_list[-21:], dtype=float)
        ret_20 = ret_20[1:] / ret_20[:-1] - 1
        volatility_20[code] = np.std(ret_20)
        trend_ok[code] = int(close_now > ma20 and ma20 > ma60)

    df["momentum_20"] = df["code"].map(momentum_20)
    df["momentum_60"] = df["code"].map(momentum_60)
    df["breakout_60"] = df["code"].map(breakout_60)
    df["avg_money_20"] = df["code"].map(avg_money_20)
    df["volatility_20"] = df["code"].map(volatility_20)
    df["close_now"] = df["code"].map(close_now_map)
    df["trend_ok"] = df["code"].map(trend_ok)

    df = df.replace([np.inf, -np.inf], np.nan).dropna(
        subset=[
            "momentum_20",
            "momentum_60",
            "breakout_60",
            "avg_money_20",
            "volatility_20",
            "close_now",
            "trend_ok",
        ]
    )
    if df.empty:
        return df

    return df[
        (df["trend_ok"] == 1)
        & (df["momentum_20"] > 0)
        & (df["momentum_60"] > -0.05)
        & (df["breakout_60"] > g.min_breakout_60)
        & (df["avg_money_20"] > g.min_avg_money_20)
        & (df["volatility_20"] < g.max_volatility_20)
        & (df["close_now"] < g.max_price_to_buy)
    ]


def add_hot_theme_bonus(context, df):
    if df.empty:
        return df

    df["hot_keyword_bonus"] = 0.0
    df["hot_industry_bonus"] = 0.0

    if (not g.enable_hot_keyword_bonus) and (not g.enable_hot_industry_bonus):
        return df

    sample_list = get_recent_strong_sample_stocks(context, list(df["code"]))
    if not sample_list:
        return df

    hot_keywords, hot_industries = get_hot_themes_from_sample(context, sample_list)
    g.hot_keyword_names = hot_keywords
    g.hot_industry_names = hot_industries

    hot_keyword_set = set(hot_keywords) if g.enable_hot_keyword_bonus else set()
    hot_industry_set = set(hot_industries) if g.enable_hot_industry_bonus else set()
    keyword_bonus_map = {}
    industry_bonus_map = {}
    current_data = get_current_data()

    for code in list(df["code"]):
        keyword_names = get_stock_keyword_theme_names(code, current_data) if g.enable_hot_keyword_bonus else []
        industry_names = get_stock_industry_names(code, context.previous_date) if g.enable_hot_industry_bonus else []

        keyword_hit_count = len(set(keyword_names) & hot_keyword_set)
        industry_hit_count = len(set(industry_names) & hot_industry_set)

        keyword_bonus_map[code] = keyword_hit_count * g.hot_keyword_bonus_per_hit
        industry_bonus_map[code] = industry_hit_count * g.hot_industry_bonus_per_hit

    df["hot_keyword_bonus"] = df["code"].map(keyword_bonus_map).fillna(0)
    df["hot_industry_bonus"] = df["code"].map(industry_bonus_map).fillna(0)
    return df


def get_hot_themes_from_sample(context, stock_list):
    keyword_counter = {}
    industry_counter = {}
    current_data = get_current_data()

    for stock in stock_list:
        if g.enable_hot_keyword_bonus:
            for keyword_name in get_stock_keyword_theme_names(stock, current_data):
                keyword_counter[keyword_name] = keyword_counter.get(keyword_name, 0) + 1

        if g.enable_hot_industry_bonus:
            for industry_name in get_stock_industry_names(stock, context.previous_date):
                industry_counter[industry_name] = industry_counter.get(industry_name, 0) + 1

    hot_keywords = sorted(keyword_counter.items(), key=lambda x: x[1], reverse=True)
    hot_industries = sorted(industry_counter.items(), key=lambda x: x[1], reverse=True)

    hot_keywords = [name for name, _ in hot_keywords[:g.hot_keyword_top_n]]
    hot_industries = [name for name, _ in hot_industries[:g.hot_industry_top_n]]
    return hot_keywords, hot_industries


def get_recent_strong_sample_stocks(context, stock_list):
    if not stock_list:
        return []

    try:
        price_df = get_price(
            stock_list,
            end_date=context.previous_date,
            frequency="daily",
            fields=["close"],
            count=g.hot_strength_lookback + 1,
            panel=False,
            fill_paused=False,
            skip_paused=True,
        )
    except:
        return []

    if price_df is None or price_df.empty:
        return []

    score_list = []
    for stock in stock_list:
        sub = price_df[price_df["code"] == stock]
        if "time" in sub.columns:
            sub = sub.sort_values("time")
        elif "datetime" in sub.columns:
            sub = sub.sort_values("datetime")
        elif "date" in sub.columns:
            sub = sub.sort_values("date")
        else:
            sub = sub.sort_index()

        if len(sub) < g.hot_strength_lookback + 1:
            continue

        close_list = list(sub["close"])
        start_price = close_list[-(g.hot_strength_lookback + 1)]
        end_price = close_list[-1]
        if start_price is None or start_price <= 0 or end_price is None or end_price <= 0:
            continue

        ret_30 = end_price / start_price - 1
        score_list.append((stock, ret_30))

    score_list = sorted(score_list, key=lambda x: x[1], reverse=True)
    return [stock for stock, _ in score_list[: g.hot_theme_sample_size]]


def get_stock_keyword_theme_names(stock, current_data):
    result = []
    name = ""
    try:
        name = current_data[stock].name
    except:
        name = ""

    if not name:
        return result

    keyword_theme_map = {
        "机器人": ["机器人", "机电", "自动化", "智能装备"],
        "人工智能": ["人工智能", "AI", "智算", "算力", "大模型", "数据", "软件", "云"],
        "芯片半导体": ["芯片", "半导体", "集成电路", "电子", "微", "光电"],
        "新能源": ["新能源", "光伏", "储能", "锂电", "电池", "新材", "风电"],
        "医药": ["医药", "医疗", "生物", "制药", "药业"],
        "军工": ["军工", "航空", "航天", "卫星", "船舶"],
        "券商": ["证券", "券商"],
        "有色资源": ["黄金", "有色", "铜", "铝", "稀土", "矿业"],
        "消费电子": ["消费电子", "声学", "显示", "触控", "通信"],
        "汽车产业链": ["汽车", "汽配", "智驾", "底盘", "热管理"],
    }

    for theme_name, keywords in keyword_theme_map.items():
        for keyword in keywords:
            if keyword in name:
                result.append(theme_name)
                break

    return list(set(result))


def get_stock_industry_names(stock, date):
    result = []
    try:
        industry_data = get_industry([stock], date)
        stock_industries = industry_data.get(stock, {}) if isinstance(industry_data, dict) else {}
        if isinstance(stock_industries, dict):
            for _, item in stock_industries.items():
                if isinstance(item, dict):
                    name = item.get("industry_name") or item.get("name")
                    if name:
                        result.append(name)
                elif isinstance(item, str):
                    result.append(item)
    except:
        return []
    return list(set(result))


def check_stop_loss(context):
    if not context.portfolio.positions:
        return

    current_data = get_current_data()
    for stock, position in list(context.portfolio.positions.items()):
        if position.closeable_amount <= 0:
            continue

        last_price = current_data[stock].last_price
        if last_price <= 0 or position.avg_cost <= 0:
            continue

        prev_max = g.max_price.get(stock, position.avg_cost)
        g.max_price[stock] = max(prev_max, last_price)

        ret = last_price / position.avg_cost - 1
        drawdown = last_price / g.max_price[stock] - 1
        dynamic_stop_line = -g.stop_loss_pct

        if g.enable_cost_protection:
            if ret >= g.cost_protection_profit_threshold_2:
                dynamic_stop_line = max(dynamic_stop_line, g.cost_protection_stop_line_2)
            elif ret >= g.cost_protection_profit_threshold_1:
                dynamic_stop_line = max(dynamic_stop_line, g.cost_protection_stop_line_1)

        atr_stop_hit = False
        if stock in g.atr_stop_prices:
            atr_stop_hit = last_price <= g.atr_stop_prices[stock]

        if ret <= dynamic_stop_line or atr_stop_hit or (
            g.max_price[stock] / position.avg_cost - 1 >= g.max_return_for_trailing
            and drawdown <= -g.take_profit_drawdown_pct
        ):
            order_target_value(stock, 0)
            g.max_price.pop(stock, None)
            g.atr_stop_prices.pop(stock, None)


def update_atr_stop_prices(context):
    if not context.portfolio.positions:
        return

    current_data = get_current_data()
    for stock, position in list(context.portfolio.positions.items()):
        if position.total_amount <= 0:
            continue

        atr = get_stock_atr(stock, context)
        last_price = current_data[stock].last_price
        if atr is None or atr <= 0 or last_price <= 0 or position.avg_cost <= 0:
            continue

        base_price = max(position.avg_cost, g.max_price.get(stock, position.avg_cost), last_price)
        trailing_stop = base_price - g.atr_multiplier * atr

        if g.enable_cost_protection:
            profit_ratio = last_price / position.avg_cost - 1
            if profit_ratio >= g.cost_protection_profit_threshold_2:
                trailing_stop = max(trailing_stop, position.avg_cost * (1 + g.cost_protection_stop_line_2))
            elif profit_ratio >= g.cost_protection_profit_threshold_1:
                trailing_stop = max(trailing_stop, position.avg_cost * (1 + g.cost_protection_stop_line_1))

        old_stop = g.atr_stop_prices.get(stock)
        if old_stop is None:
            g.atr_stop_prices[stock] = trailing_stop
        else:
            g.atr_stop_prices[stock] = max(old_stop, trailing_stop)


def get_stock_atr(stock, context):
    price_df = get_price(
        stock,
        end_date=context.previous_date,
        frequency="daily",
        fields=["high", "low", "close"],
        count=g.atr_period + 5,
        panel=False,
    )
    if price_df is None or len(price_df) < g.atr_period + 1:
        return None

    if "time" in price_df.columns:
        price_df = price_df.sort_values("time")
    elif "datetime" in price_df.columns:
        price_df = price_df.sort_values("datetime")
    elif "date" in price_df.columns:
        price_df = price_df.sort_values("date")
    else:
        price_df = price_df.sort_index()
    highs = price_df["high"].values
    lows = price_df["low"].values
    closes = price_df["close"].values

    true_ranges = []
    for i in range(1, len(price_df)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    if len(true_ranges) < g.atr_period:
        return None

    return float(np.mean(true_ranges[-g.atr_period:]))


def refresh_max_price(context):
    current_data = get_current_data()
    valid_positions = set(context.portfolio.positions.keys())

    for stock in list(g.max_price.keys()):
        if stock not in valid_positions:
            g.max_price.pop(stock, None)
            g.atr_stop_prices.pop(stock, None)

    for stock, position in context.portfolio.positions.items():
        last_price = current_data[stock].last_price
        if last_price <= 0:
            continue
        base_price = position.avg_cost if position.avg_cost > 0 else last_price
        g.max_price[stock] = max(g.max_price.get(stock, base_price), last_price)


def clear_all_positions(context):
    for stock in list(context.portfolio.positions.keys()):
        order_target_value(stock, 0)
        g.max_price.pop(stock, None)


def order_target_value_safely(stock, target_value):
    if target_value <= 0:
        order_target_value(stock, 0)
        return

    current_data = get_current_data()
    last_price = current_data[stock].last_price
    if last_price is None or last_price <= 0:
        return

    if target_value < last_price * 100:
        return

    order_target_value(stock, target_value)


def get_rank_weights(n):
    preset = {
        1: [1.00],
        2: [0.70, 0.30],
        3: [0.55, 0.27, 0.18],
        4: [0.45, 0.25, 0.18, 0.12],
    }
    if n in preset:
        return preset[n]

    raw = np.array([n - i for i in range(n)], dtype=float)
    raw = raw / raw.sum()
    return list(raw)


def filter_new_stock(stock_list, date, days):
    d = date if isinstance(date, dt.date) else date.date()
    return [stock for stock in stock_list if (d - get_security_info(stock).start_date).days >= days]


def filter_kcbj_stock(stock_list):
    return [
        stock for stock in stock_list
        if not (
            stock.startswith("4")
            or stock.startswith("8")
            or stock[:2] == "68"
            or stock[:2] == "30"
        )
    ]


def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [
        stock for stock in stock_list
        if not current_data[stock].is_st
        and "ST" not in current_data[stock].name
        and "*" not in current_data[stock].name
        and "退" not in current_data[stock].name
    ]


def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def filter_limitup_stock(context, stock_list):
    current_data = get_current_data()
    result = []
    for stock in stock_list:
        if stock in context.portfolio.positions:
            result.append(stock)
        elif current_data[stock].last_price < current_data[stock].high_limit:
            result.append(stock)
    return result


def filter_limitdown_stock(context, stock_list):
    current_data = get_current_data()
    result = []
    for stock in stock_list:
        if stock in context.portfolio.positions:
            result.append(stock)
        elif current_data[stock].last_price > current_data[stock].low_limit:
            result.append(stock)
    return result


def print_position_info(context):
    for position in context.portfolio.positions.values():
        ret = 100 * (position.price / position.avg_cost - 1)
        log.info(
            "持仓 %s 成本 %.2f 现价 %.2f 收益 %.2f%% 市值 %.2f"
            % (
                position.security,
                position.avg_cost,
                position.price,
                ret,
                position.value,
            )
        )

