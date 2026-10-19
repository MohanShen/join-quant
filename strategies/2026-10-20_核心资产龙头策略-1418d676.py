# Clone from JoinQuant
# postId: 1418d676fd84ae4629e73a943221f1ea
# backtestId: 5eaef9d77770ce7666d45ff043d308f2
# title: 核心资产龙头策略

# -*- coding: utf-8 -*-
"""
核心资产红利龙头策略 v1

聚宽 JoinQuant 版本。

策略目标：
1. 在 A 股中寻找行业龙头；
2. 要求估值相对行业不贵；
3. 偏好稳定现金分红；
4. 排除明显夕阳或景气度下行行业；
5. 用中长期趋势过滤价值陷阱。
"""

from jqdata import *
from jqfactor import *
import datetime
import math
import numpy as np
import pandas as pd


def initialize(context):
    """初始化策略参数、交易成本和定时任务。"""
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_benchmark("000300.XSHG")

    log.set_level("order", "error")
    log.set_level("system", "error")
    log.set_level("strategy", "info")

    set_slippage(FixedSlippage(0.02), type="stock")
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

    # 股票池：中证全指覆盖面较广；如果数据环境不支持，会自动回退到沪深300+中证500。
    #g.base_index = "000985.XSHG"
    g.base_index = "000300.XSHG"
    g.fallback_indices = ["000300.XSHG", "000905.XSHG"]

    # 持仓与调仓参数。
    g.hold_num = 10
    g.max_industry_hold = 5
    g.min_trade_value = 5000
    g.cash_reserve = 0.02

    # 基础过滤参数。
    g.min_list_days = 365
    g.min_avg_amount = 8e7
    g.min_market_cap = 80
    g.max_market_cap = 10000

    # 基本面阈值。
    g.min_roe = 8
    g.min_dividend_yield = 0.025
    g.max_payout_ratio = 0.80
    g.max_debt_ratio = 0.75

    # 行业规则：保留为可配置项，不是绝对判断。
    g.sunset_industry_keywords = [
        "房地产",
        "煤炭",
        "钢铁",
        "建筑材料",
        "纺织服饰",
        "商贸零售",
    ]

    # 评分权重。
    g.score_weights = {
        "leader": 0.25,
        "valuation": 0.20,
        "dividend": 0.20,
        "quality": 0.20,
        "industry": 0.10,
        "trend": 0.05,
    }

    g.last_selected = []
    g.last_score_table = pd.DataFrame()

    run_monthly(rebalance, monthday=1, time="10:00")
    run_daily(risk_check, time="14:40")

    log.info("核心资产红利龙头策略 v1 初始化完成")


def before_trading_start(context):
    """盘前记录当前持仓，便于回测日志检查。"""
    positions = list(context.portfolio.positions.keys())
    if positions:
        log.info("当前持仓: %s" % ",".join(positions))


def get_stock_name(stock):
    """获取股票名称，日志使用；失败时返回代码。"""
    try:
        return get_current_data()[stock].name
    except Exception:
        return stock


def log_filter_step(step_name, before_count, after_count, extra=""):
    """统一输出筛选阶段日志。"""
    removed = before_count - after_count
    msg = "[筛选] %s: %d -> %d, 剔除 %d" % (
        step_name,
        before_count,
        after_count,
        removed,
    )
    if extra:
        msg += ", " + extra
    log.info(msg)


def log_industry_distribution(df, title, limit=8):
    """输出行业分布，帮助判断是否过度集中。"""
    if df is None or df.empty or "industry" not in df.columns:
        return
    counts = df["industry"].value_counts().head(limit)
    text = ["%s:%d" % (industry, count) for industry, count in counts.items()]
    log.info("[行业] %s Top%d: %s" % (title, limit, " | ".join(text)))


def get_base_universe(context):
    """获取基础股票池。"""
    try:
        stocks = get_index_stocks(g.base_index, date=context.previous_date)
    except Exception as err:
        log.warn("获取 %s 失败，使用备用指数池: %s" % (g.base_index, err))
        stocks = []

    if not stocks:
        for index_code in g.fallback_indices:
            try:
                stocks += get_index_stocks(index_code, date=context.previous_date)
            except Exception as err:
                log.warn("获取备用指数 %s 失败: %s" % (index_code, err))

    return sorted(list(set(stocks)))


def filter_basic_stocks(context, stocks):
    """过滤 ST、停牌、新股、流动性不足股票。"""
    current_data = get_current_data()
    today = context.current_dt.date()
    result = []
    paused_count = 0
    st_count = 0
    new_count = 0

    for stock in stocks:
        data = current_data[stock]
        if data.paused or data.is_st:
            paused_count += 1
            continue
        if "ST" in data.name or "*" in data.name or "退" in data.name:
            st_count += 1
            continue
        if (today - get_security_info(stock).start_date).days < g.min_list_days:
            new_count += 1
            continue
        result.append(stock)

    log_filter_step(
        "基础状态过滤(ST/停牌/新股)",
        len(stocks),
        len(result),
        "停牌或标记ST %d, 名称风险 %d, 上市不足%d天 %d"
        % (paused_count, st_count, g.min_list_days, new_count),
    )

    if not result:
        return []

    amount = history(20, "1d", "money", result, df=True)
    if amount is None or amount.empty:
        log.warn("[筛选] 近20日成交额数据为空，跳过流动性过滤")
        return result

    avg_amount = amount.mean()
    liquid_stocks = [s for s in result if avg_amount.get(s, 0) >= g.min_avg_amount]
    log_filter_step(
        "流动性过滤",
        len(result),
        len(liquid_stocks),
        "近20日日均成交额 >= %.0f万" % (g.min_avg_amount / 10000.0),
    )
    return liquid_stocks


def get_stock_industry(stock):
    """获取申万一级行业名称。"""
    try:
        info = get_industry(stock)
        if stock in info and "sw_l1" in info[stock]:
            return info[stock]["sw_l1"]["industry_name"]
    except Exception:
        pass
    return "未知行业"


def attach_industry(df):
    """给基本面表追加行业名称。"""
    df = df.copy()
    df["industry"] = df["code"].apply(get_stock_industry)
    return df


def query_fundamentals(context, stocks):
    """读取估值、成长、盈利质量和资产负债数据。"""
    if not stocks:
        return pd.DataFrame()

    q = query(
        valuation.code,
        valuation.market_cap,
        valuation.pe_ratio,
        valuation.pb_ratio,
        income.operating_revenue,
        income.net_profit,
        indicator.roe,
        indicator.roa,
        indicator.gross_profit_margin,
        indicator.inc_revenue_year_on_year,
        indicator.inc_net_profit_year_on_year,
        cash_flow.net_operate_cash_flow,
        balance.total_assets,
        balance.total_liability,
    ).filter(
        valuation.code.in_(stocks),
        valuation.market_cap >= g.min_market_cap,
        valuation.market_cap <= g.max_market_cap,
        valuation.pe_ratio > 0,
        valuation.pb_ratio > 0,
        indicator.roe > 0,
        income.net_profit > 0,
    )

    df = get_fundamentals(q, date=context.previous_date)
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.drop_duplicates("code")
    df["debt_ratio"] = df["total_liability"] / df["total_assets"].replace(0, np.nan)
    df["cashflow_positive"] = df["net_operate_cash_flow"] > 0
    df = attach_industry(df)
    return df


def is_sunset_industry(industry_name):
    """根据关键词剔除明显偏夕阳或强周期衰退行业。"""
    if not industry_name or industry_name == "未知行业":
        return False
    for keyword in g.sunset_industry_keywords:
        if keyword in industry_name:
            return True
    return False


def filter_industry_and_quality(df):
    """行业、盈利质量和资产负债过滤。"""
    if df.empty:
        return df

    df = df.copy()
    before = len(df)
    df = df[~df["industry"].apply(is_sunset_industry)]
    log_filter_step("夕阳/强周期行业过滤", before, len(df))

    before = len(df)
    df = df[df["roe"] >= g.min_roe]
    log_filter_step("ROE过滤", before, len(df), "ROE >= %.1f" % g.min_roe)

    before = len(df)
    df = df[df["debt_ratio"].fillna(1) <= g.max_debt_ratio]
    log_filter_step("资产负债率过滤", before, len(df), "负债率 <= %.0f%%" % (g.max_debt_ratio * 100))

    before = len(df)
    df = df[df["cashflow_positive"]]
    log_filter_step("经营现金流过滤", before, len(df), "经营现金流为正")

    before = len(df)
    df = df[df["inc_revenue_year_on_year"].fillna(-100) > -10]
    log_filter_step("营收增速过滤", before, len(df), "营收同比 > -10%")

    before = len(df)
    df = df[df["inc_net_profit_year_on_year"].fillna(-100) > -20]
    log_filter_step("利润增速过滤", before, len(df), "净利润同比 > -20%")
    return df


def get_dividend_info(context, stocks):
    """
    计算近三年现金分红信息。

    聚宽不同数据权限下 finance.STK_XR_XD 字段可能略有差异，所以这里做了容错。
    bonus_amount_rmb 通常表示每 10 股派现金额，股息率近似为 现金分红/10/当前价格。
    """
    result = pd.DataFrame(index=stocks)
    result["dividend_yield_3y"] = 0.0
    result["dividend_years"] = 0
    result["cash_dividend_sum"] = 0.0

    if not stocks:
        return result

    end_date = context.previous_date
    start_date = end_date - datetime.timedelta(days=365 * 3 + 30)

    try:
        q = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.report_date,
            finance.STK_XR_XD.a_xr_date,
            finance.STK_XR_XD.bonus_amount_rmb,
        ).filter(
            finance.STK_XR_XD.code.in_(stocks),
            finance.STK_XR_XD.a_xr_date >= start_date,
            finance.STK_XR_XD.a_xr_date <= end_date,
        )
        div = finance.run_query(q)
    except Exception as err:
        log.warn("现金分红数据不可用，本次分红因子记为0: %s" % err)
        return result

    if div is None or div.empty:
        return result

    price = history(1, "1d", "close", stocks, df=True)
    if price is None or price.empty:
        return result
    last_price = price.iloc[-1]

    for stock, group in div.groupby("code"):
        cash_sum = group["bonus_amount_rmb"].fillna(0).sum()
        years = len(set(pd.to_datetime(group["report_date"]).dt.year.tolist()))
        stock_price = last_price.get(stock, np.nan)
        if stock_price and not np.isnan(stock_price) and stock_price > 0:
            dividend_yield = cash_sum / 10.0 / stock_price
        else:
            dividend_yield = 0
        result.loc[stock, "dividend_yield_3y"] = dividend_yield / 3.0
        result.loc[stock, "dividend_years"] = years
        result.loc[stock, "cash_dividend_sum"] = cash_sum

    return result


def add_dividend_factor(context, df):
    """追加分红因子并过滤高分红要求。"""
    if df.empty:
        return df

    div = get_dividend_info(context, df["code"].tolist())
    df = df.set_index("code").join(div, how="left").reset_index()
    df["dividend_yield_3y"] = df["dividend_yield_3y"].fillna(0)
    df["dividend_years"] = df["dividend_years"].fillna(0)

    df["payout_ratio"] = np.nan
    valid_profit = df["net_profit"] > 0
    # 近似分红率只用于排除不可持续高派息，A股股本差异会造成误差，实盘前建议接入更精确字段。
    df.loc[valid_profit, "payout_ratio"] = 0.5

    before = len(df)
    df = df[df["dividend_yield_3y"] >= g.min_dividend_yield]
    log_filter_step(
        "股息率过滤",
        before,
        len(df),
        "近3年平均股息率 >= %.2f%%" % (g.min_dividend_yield * 100),
    )

    before = len(df)
    df = df[df["dividend_years"] >= 2]
    log_filter_step("分红稳定性过滤", before, len(df), "近3年至少2年现金分红")
    return df


def group_rank_score(df, group_col, value_col, ascending=True):
    """行业内分位打分，返回 0-100 分。"""
    if df.empty:
        return pd.Series(dtype=float)
    ranked = df.groupby(group_col)[value_col].rank(pct=True, ascending=ascending)
    return ranked.fillna(0) * 100


def plain_rank_score(series, ascending=True):
    """全市场分位打分，返回 0-100 分。"""
    if series.empty:
        return pd.Series(dtype=float)
    return series.rank(pct=True, ascending=ascending).fillna(0) * 100


def add_score_columns(context, df):
    """计算六类综合评分。"""
    if df.empty:
        return df

    df = df.copy()

    # 行业龙头：行业内市值与营收排名。
    df["leader_score"] = (
        group_rank_score(df, "industry", "market_cap", ascending=True) * 0.7
        + group_rank_score(df, "industry", "operating_revenue", ascending=True) * 0.3
    )

    # 低估值：PE/PB 越低越好，所以 ascending=False 让低值拿高分。
    df["valuation_score"] = (
        group_rank_score(df, "industry", "pe_ratio", ascending=False) * 0.55
        + group_rank_score(df, "industry", "pb_ratio", ascending=False) * 0.45
    )

    # 分红：股息率 + 连续性。
    df["dividend_score"] = (
        plain_rank_score(df["dividend_yield_3y"], ascending=True) * 0.75
        + np.minimum(df["dividend_years"], 3) / 3.0 * 100 * 0.25
    )

    # 质量：盈利能力、现金流、负债安全。
    df["quality_score"] = (
        plain_rank_score(df["roe"], ascending=True) * 0.35
        + plain_rank_score(df["gross_profit_margin"], ascending=True) * 0.20
        + plain_rank_score(df["inc_revenue_year_on_year"], ascending=True) * 0.20
        + plain_rank_score(df["inc_net_profit_year_on_year"], ascending=True) * 0.20
        + plain_rank_score(1 - df["debt_ratio"].fillna(1), ascending=True) * 0.05
    )

    # 行业景气：用行业内公司收入/利润增速均值近似。
    industry_growth = df.groupby("industry")[
        ["inc_revenue_year_on_year", "inc_net_profit_year_on_year"]
    ].mean()
    industry_growth = industry_growth.rename(
        columns={
            "inc_revenue_year_on_year": "industry_revenue_growth",
            "inc_net_profit_year_on_year": "industry_profit_growth",
        }
    )
    industry_growth["industry_raw"] = (
        industry_growth["industry_revenue_growth"].fillna(-100) * 0.45
        + industry_growth["industry_profit_growth"].fillna(-100) * 0.55
    )
    industry_growth["industry_score"] = plain_rank_score(
        industry_growth["industry_raw"], ascending=True
    )
    df = df.join(industry_growth["industry_score"], on="industry")

    # 趋势确认：减少低估值陷阱。
    df["trend_score"] = df["code"].apply(calc_trend_score)

    weights = g.score_weights
    df["total_score"] = (
        df["leader_score"] * weights["leader"]
        + df["valuation_score"] * weights["valuation"]
        + df["dividend_score"] * weights["dividend"]
        + df["quality_score"] * weights["quality"]
        + df["industry_score"] * weights["industry"]
        + df["trend_score"] * weights["trend"]
    )

    return df


def calc_trend_score(stock):
    """中长期趋势评分。"""
    try:
        close = history(260, "1d", "close", [stock], df=True)[stock].dropna()
    except Exception:
        return 0

    if len(close) < 180:
        return 0

    ma60 = close[-60:].mean()
    ma120 = close[-120:].mean()
    ma250 = close[-250:].mean() if len(close) >= 250 else close.mean()
    last = close.iloc[-1]
    ret60 = last / close.iloc[-60] - 1

    score = 0
    if last > ma120:
        score += 35
    if ma60 > ma120:
        score += 25
    if last > ma250:
        score += 25
    if ret60 > -0.15:
        score += 15
    return score


def select_stocks(context):
    """完整选股流程。"""
    log.info("========== 开始月度选股 %s ==========" % context.current_dt.strftime("%Y-%m-%d"))
    stocks = get_base_universe(context)
    log.info("[筛选] 初始股票池: %d 只, 来源: %s" % (len(stocks), g.base_index))
    stocks = filter_basic_stocks(context, stocks)
    if not stocks:
        log.warn("基础股票池为空")
        return []

    df = query_fundamentals(context, stocks)
    log_filter_step("基本面可用性/市值/PE/PB/盈利过滤", len(stocks), len(df))
    log_industry_distribution(df, "基本面过滤后")

    df = filter_industry_and_quality(df)
    log_industry_distribution(df, "质量过滤后")

    df = add_dividend_factor(context, df)
    log_industry_distribution(df, "分红过滤后")

    df = add_score_columns(context, df)

    if df.empty:
        log.warn("所有股票均被过滤")
        return []

    before = len(df)
    df = df[df["trend_score"] >= 60]
    log_filter_step("趋势过滤", before, len(df), "趋势分 >= 60")

    if df.empty:
        log.warn("趋势过滤后无候选股票")
        return []

    df = df.sort_values("total_score", ascending=False)
    g.last_score_table = df.copy()
    print_candidate_table(df, limit=20)

    selected = []
    industry_count = {}
    for _, row in df.iterrows():
        industry = row["industry"]
        if industry_count.get(industry, 0) >= g.max_industry_hold:
            log.info(
                "[筛选] 跳过 %s %s: %s 已达到单行业上限 %d"
                % (row["code"], get_stock_name(row["code"]), industry, g.max_industry_hold)
            )
            continue
        selected.append(row["code"])
        industry_count[industry] = industry_count.get(industry, 0) + 1
        if len(selected) >= g.hold_num:
            break

    log.info("本期选股: %s" % ",".join(selected))
    print_score_table(df, selected)
    log.info("========== 月度选股结束，入选 %d 只 ==========" % len(selected))
    return selected


def print_candidate_table(df, limit=20):
    """输出候选池前若干名。"""
    show = df.head(limit)
    log.info("[候选] 综合得分前%d:" % min(limit, len(show)))
    for i, (_, row) in enumerate(show.iterrows(), 1):
        log.info(
            "[候选%02d] %s %s %s 总分 %.1f 龙头 %.1f 估值 %.1f 分红 %.1f 质量 %.1f 行业 %.1f 趋势 %.1f"
            % (
                i,
                row["code"],
                get_stock_name(row["code"]),
                row["industry"],
                row["total_score"],
                row["leader_score"],
                row["valuation_score"],
                row["dividend_score"],
                row["quality_score"],
                row["industry_score"],
                row["trend_score"],
            )
        )


def print_score_table(df, selected):
    """输出选股结果，方便回测复盘。"""
    cols = [
        "code",
        "industry",
        "total_score",
        "leader_score",
        "valuation_score",
        "dividend_score",
        "quality_score",
        "industry_score",
        "trend_score",
        "pe_ratio",
        "pb_ratio",
        "roe",
        "dividend_yield_3y",
    ]
    show = df[df["code"].isin(selected)][cols].copy()
    for _, row in show.iterrows():
        log.info(
            "[入选] %s %s %s 总分 %.1f 龙头 %.1f 估值 %.1f 分红 %.1f 质量 %.1f 行业 %.1f 趋势 %.1f PE %.1f PB %.1f ROE %.1f 股息率 %.2f%%"
            % (
                row["code"],
                get_stock_name(row["code"]),
                row["industry"],
                row["total_score"],
                row["leader_score"],
                row["valuation_score"],
                row["dividend_score"],
                row["quality_score"],
                row["industry_score"],
                row["trend_score"],
                row["pe_ratio"],
                row["pb_ratio"],
                row["roe"],
                row["dividend_yield_3y"] * 100,
            )
        )


def rebalance(context):
    """月度调仓。"""
    log.info("========== 开始月度调仓 %s ==========" % context.current_dt.strftime("%Y-%m-%d %H:%M"))
    target_stocks = select_stocks(context)
    g.last_selected = target_stocks

    if not target_stocks:
        log.warn("目标股票为空，本月不主动开新仓")
        return

    current_positions = list(context.portfolio.positions.keys())
    log.info(
        "[调仓] 组合总资产 %.2f, 可用现金 %.2f, 当前持仓 %d, 目标持仓 %d"
        % (
            context.portfolio.total_value,
            context.portfolio.available_cash,
            len(current_positions),
            len(target_stocks),
        )
    )

    for stock in current_positions:
        if stock not in target_stocks:
            position = context.portfolio.positions[stock]
            log.info(
                "[卖出] %s %s 非目标持仓，当前市值 %.2f，成本 %.2f，目标市值 0"
                % (stock, get_stock_name(stock), position.value, position.avg_cost)
            )
            order = order_target_value(stock, 0)
            log.info("[委托] 卖出 %s 返回: %s" % (stock, order))

    total_value = context.portfolio.total_value * (1 - g.cash_reserve)
    target_value = total_value / len(target_stocks)
    log.info(
        "[调仓] 目标单股市值 %.2f, 现金保留 %.2f%%"
        % (target_value, g.cash_reserve * 100)
    )

    for stock in target_stocks:
        current_value = context.portfolio.positions[stock].value if stock in context.portfolio.positions else 0
        diff_value = target_value - current_value
        if abs(target_value - current_value) < g.min_trade_value:
            log.info(
                "[跳过] %s %s 当前市值 %.2f，目标 %.2f，差额 %.2f 小于最小交易额 %.2f"
                % (stock, get_stock_name(stock), current_value, target_value, diff_value, g.min_trade_value)
            )
            continue
        action = "买入/加仓" if diff_value > 0 else "减仓"
        log.info(
            "[%s] %s %s 当前市值 %.2f，目标市值 %.2f，差额 %.2f"
            % (action, stock, get_stock_name(stock), current_value, target_value, diff_value)
        )
        order = order_target_value(stock, target_value)
        log.info("[委托] %s %s 返回: %s" % (action, stock, order))

    log.info("========== 月度调仓结束 ==========")


def risk_check(context):
    """日内风控：基本趋势破坏时减仓。"""
    positions = list(context.portfolio.positions.keys())
    if not positions:
        return

    for stock in positions:
        try:
            close = history(130, "1d", "close", [stock], df=True)[stock].dropna()
        except Exception:
            continue

        if len(close) < 120:
            continue

        last = close.iloc[-1]
        ma120 = close[-120:].mean()
        cost = context.portfolio.positions[stock].avg_cost
        drawdown_from_cost = last / cost - 1 if cost > 0 else 0

        if last < ma120 and drawdown_from_cost < -0.10:
            log.info("风控卖出: %s 跌破120日线且相对成本亏损 %.2f%%" % (stock, drawdown_from_cost * 100))
            order_target_value(stock, 0)


def handle_data(context, data):
    """聚宽策略必须保留的行情回调。本策略主要使用定时任务。"""
    pass
