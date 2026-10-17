# Clone from JoinQuant
# postId: c913387f8d6cdb8096b29e839f5675fa
# backtestId: 47daf74fa7d82f051de5292ebf38ddec
# title: 哈利-布朗永久投资组合-平均年化11%，最大回撤11%

# coding: utf-8
"""
聚宽回测策略：红利低波/短融/油气历史平替 + 纳指回撤加仓（保守版）

组合原始权重：
1. 红利低波 ETF 12.5%
2. 安信稳健增值替代 30% = 85% 短融 ETF + 15% 红利低波 ETF
3. 短融 ETF 25%
4. 纳指 100 ETF 12.5%
5. 标普油气 ETF 10%
6. 黄金 ETF 10%

合并后原始权重：
- 红利历史平替：17.0%         # 上证红利 ETF 510880.XSHG
- 现金/短融历史平替：50.5%    # 华宝添益 511990.XSHG
- 纳指 100 ETF：12.5%         # 513100.XSHG
- 油气历史平替：10.0%         # 华宝油气 LOF 162411.XSHE
- 黄金 ETF：10.0%             # 518880.XSHG

纳指回撤加仓规则：
- 回撤口径：纳指 ETF 相对本年度最高价的跌幅。
- 跌 10%：纳指目标权重提升至 25.0%，华宝添益减少 12.5%。
- 跌 20%：纳指目标权重提升至 37.5%，华宝添益减少 25.0%。
- 跌 30% 或更深：不再继续加仓，纳指最高目标权重保持 37.5%。

纳指新高减仓规则：
- 新高口径：纳指 ETF 创回测以来历史新高。
- 每次创历史新高，组合目标权重恢复到原始权重。

其他规则：
- 加仓后不做年度再平衡，维持加仓后的目标权重。
- 跨年只重置“本年度最高价”，不重置“历史最高价”，也不恢复原始权重。
"""

from jqdata import *


def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)

    set_benchmark("513100.XSHG")
    set_slippage(PriceRelatedSlippage(0.002), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.00005,
            close_commission=0.00005,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    log.set_level("order", "error")

    # 为拉长回测历史，使用更早成立/上市的历史平替。
    g.dividend_lowvol = "510880.XSHG"  # 上证红利 ETF，替代 512890 红利低波 ETF
    g.short_bond = "511990.XSHG"       # 华宝添益，替代 511360 短融 ETF
    g.nasdaq = "513100.XSHG"           # 纳指 100 ETF
    g.oil_gas = "162411.XSHE"          # 华宝油气 LOF，替代 513350 标普油气 ETF
    g.gold = "518880.XSHG"             # 黄金 ETF

    g.asset_names = {
        g.dividend_lowvol: "上证红利ETF",
        g.short_bond: "华宝添益",
        g.nasdaq: "纳指100ETF",
        g.oil_gas: "华宝油气LOF",
        g.gold: "黄金ETF",
    }
    g.assets = [
        g.dividend_lowvol,
        g.short_bond,
        g.nasdaq,
        g.oil_gas,
        g.gold,
    ]

    g.base_weights = {
        g.dividend_lowvol: 0.125 + 0.30 * 0.15,
        g.short_bond: 0.30 * 0.85 + 0.25,
        g.nasdaq: 0.125,
        g.oil_gas: 0.10,
        g.gold: 0.10,
    }

    # 保守版：纳指最高只加到 37.5%。
    # 跌幅按纳指 ETF 相对本年度最高价计算。
    g.nasdaq_drawdown_steps = [
        (-0.20, 0.375),
        (-0.10, 0.250),
    ]

    g.current_target_weights = g.base_weights.copy()
    g.nasdaq_year_peak_price = None
    g.nasdaq_peak_year = None
    g.nasdaq_all_time_peak_price = None
    g.initialized_position = False
    g.min_trade_value = 1000

    # 每个交易日检查。首次运行建仓；之后只在纳指历史新高或年度回撤触发时调仓。
    run_daily(daily_check_and_trade, time="10:30")


def daily_check_and_trade(context):
    today = context.current_dt.date()
    price = get_last_close(context, g.nasdaq)
    if price is None or price <= 0:
        log.info("无法获取纳指 ETF 上一交易日收盘价，跳过回撤检查")
        return

    if not g.initialized_position:
        initial_rebalance(context, price)
        return

    if g.nasdaq_peak_year != today.year:
        g.nasdaq_peak_year = today.year
        g.nasdaq_year_peak_price = price
        log.info("进入新年份，仅重置纳指年度高点为 %.4f，不做年度再平衡" % price)

    if g.nasdaq_year_peak_price is None or g.nasdaq_year_peak_price <= 0:
        g.nasdaq_year_peak_price = price
    if g.nasdaq_all_time_peak_price is None or g.nasdaq_all_time_peak_price <= 0:
        g.nasdaq_all_time_peak_price = price

    if price > g.nasdaq_all_time_peak_price:
        g.nasdaq_all_time_peak_price = price
        reset_to_base_on_new_high(context, price)
        return

    if price > g.nasdaq_year_peak_price:
        g.nasdaq_year_peak_price = price

    drawdown = price / g.nasdaq_year_peak_price - 1.0
    target_nasdaq_weight = get_target_nasdaq_weight(drawdown)
    current_target_nasdaq_weight = g.current_target_weights.get(g.nasdaq, 0)
    if target_nasdaq_weight <= current_target_nasdaq_weight + 1e-8:
        return

    target = g.current_target_weights.copy()
    extra_nasdaq_weight = target_nasdaq_weight - current_target_nasdaq_weight
    available_short_weight = target.get(g.short_bond, 0)
    move_weight = min(extra_nasdaq_weight, available_short_weight)

    if move_weight <= 0:
        log.info("短融目标权重不足，无法继续加仓纳指")
        return

    target[g.short_bond] -= move_weight
    target[g.nasdaq] += move_weight
    g.current_target_weights = normalize_weights(target)

    log.info(
        "纳指年度回撤 %.2f%%，纳指目标权重提升至 %.2f%%，华宝添益降至 %.2f%%"
        % (
            drawdown * 100,
            g.current_target_weights[g.nasdaq] * 100,
            g.current_target_weights[g.short_bond] * 100,
        )
    )
    rebalance_to_weights(context, g.current_target_weights)


def initial_rebalance(context, nasdaq_price):
    g.current_target_weights = g.base_weights.copy()
    g.nasdaq_peak_year = context.current_dt.date().year
    g.nasdaq_year_peak_price = nasdaq_price
    g.nasdaq_all_time_peak_price = nasdaq_price
    g.initialized_position = True

    log.info("策略首次建仓，使用原始权重：%s" % format_weights(g.current_target_weights))
    rebalance_to_weights(context, g.current_target_weights)


def reset_to_base_on_new_high(context, nasdaq_price):
    if weights_equal(g.current_target_weights, g.base_weights):
        log.info("纳指创历史新高 %.4f，当前已是原始权重" % nasdaq_price)
        return

    g.current_target_weights = g.base_weights.copy()
    log.info("纳指创历史新高 %.4f，组合恢复原始权重：%s" % (
        nasdaq_price,
        format_weights(g.current_target_weights),
    ))
    rebalance_to_weights(context, g.current_target_weights)


def get_target_nasdaq_weight(drawdown):
    for threshold, target_weight in g.nasdaq_drawdown_steps:
        if drawdown <= threshold:
            return target_weight
    return g.current_target_weights.get(g.nasdaq, g.base_weights[g.nasdaq])


def rebalance_to_weights(context, target):
    total_value = context.portfolio.total_value

    # 先卖后买，避免现金不足。
    for security in g.assets:
        target_value = total_value * target.get(security, 0)
        current_value = position_value(context, security)
        if current_value > target_value and current_value - target_value >= g.min_trade_value:
            log.info("卖出调仓 %s 至 %.2f" % (asset_label(security), target_value))
            safe_order_target_value(security, target_value)

    for security in g.assets:
        target_value = total_value * target.get(security, 0)
        current_value = position_value(context, security)
        if target_value > current_value and target_value - current_value >= g.min_trade_value:
            log.info("买入调仓 %s 至 %.2f" % (asset_label(security), target_value))
            safe_order_target_value(security, target_value)


def safe_order_target_value(security, target_value):
    try:
        order_target_value(security, target_value)
        return True
    except Exception as exc:
        log.info("下单失败 %s target=%.2f，原因：%s" % (asset_label(security), target_value, exc))
        return False


def get_last_close(context, security):
    """取上一交易日收盘价，避免聚宽盘中回测 last_price 为空。"""
    df = get_price(
        security,
        count=1,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close"],
        skip_paused=True,
        fq="pre",
    )
    if df is None or len(df) == 0 or "close" not in df.columns:
        return None
    price = df["close"].iloc[-1]
    if price is None or price <= 0:
        return None
    return price


def position_value(context, security):
    if security not in context.portfolio.positions:
        return 0.0
    return context.portfolio.positions[security].value


def normalize_weights(weights):
    clean = {}
    for security in g.assets:
        weight = weights.get(security, 0)
        clean[security] = weight if weight > 0 else 0

    total = sum_values(clean.values())
    if total <= 0:
        return clean

    for security in clean:
        clean[security] = clean[security] / total
    return clean


def weights_equal(left, right):
    for security in g.assets:
        if abs(left.get(security, 0) - right.get(security, 0)) > 1e-8:
            return False
    return True


def format_weights(weights):
    parts = []
    for security in g.assets:
        parts.append("%s %.2f%%" % (asset_label(security), weights.get(security, 0) * 100))
    return ", ".join(parts)


def asset_label(security):
    return g.asset_names.get(security, security)


def sum_values(values):
    total = 0.0
    for value in values:
        total += value
    return total
