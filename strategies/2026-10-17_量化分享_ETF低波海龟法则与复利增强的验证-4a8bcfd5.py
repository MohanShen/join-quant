# Clone from JoinQuant
# postId: 4a8bcfd5092334a3a73493475f007f7a
# backtestId: bb63d032b576af1c71febb6ad20a157a
# title: 【量化分享】ETF低波海龟法则与复利增强的验证

# 克隆自聚宽文章：https://www.joinquant.com/post/78820
# 标题：开源一个年化超25%的ETF策略
# 作者：ETF量化老司机
#
# 本版本在原策略基础上增加：
#   1. 基于持仓成本的止盈，卖出利润的一半
#   2. ATR/N 计算
#   3. 每上涨1N加仓1个Unit，最多4个Unit
#   4. 加仓前10条检查
#   5. 4N止损
#   6. 初始仓位 3/4，加仓间距用最新 N
#   7. 止盈阈值30%，最短持有期20天
#   8. 避险资产只留国债ETF，阈值放宽到0.40
#   9. 去掉大盘风控，allow_safe 只看波动率中位数
#  10. 复利增强：止盈后允许用现金继续加仓，不转国债
# ============================================================================

import numpy as np
import pandas as pd

from jqdata import *


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.0001))
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0,
                  open_commission=0.0002, close_commission=0.0002,
                  close_today_commission=0, min_commission=5),
        type='fund')
    log.set_level('system', 'error')

    # ===== 资产分类 =====
    # 风险资产（权益类 + 商品 + 海外）
    g.all_risk_etfs = {
        "159915.XSHE": "创业板ETF",
        '510880.XSHG': "红利ETF",
        '510050.XSHG': '50ETF',
        '512100.XSHG': '1000ETF',
        '159768.XSHE': '房地产ETF银华',
        '515220.XSHG': '煤炭ETF',
        '159928.XSHE': '消费ETF',
        '512800.XSHG': '银行ETF',
        '159995.XSHE': '芯片ETF',
        '159870.XSHE': '化工ETF',
        '513090.XSHG': '香港证券ETF',
        "518880.XSHG": "黄金ETF",
        "513100.XSHG": "纳指ETF",
        "159985.XSHE": "豆粕ETF",
    }
    # 避险资产（只留国债ETF，剔除货币ETF）
    g.safe_etfs = {
        '511010.XSHG': '国债ETF',
        '511260.XSHG': '十年国债ETF',
    }

    g.lookback = 60
    g.min_sample_ratio = 0.8
    g.topup_band = 0.95
    g.min_hold_days = 20
    g.switch_threshold = 0.1
    g.hold_days = 0

    # ===== 止盈参数 =====
    g.take_profit_cost_threshold = 0.30
    g.take_profit_sell_profit_ratio = 0.5
    g.take_profit_armed = True
    g.take_profit_done = False

    # ===== ATR/N 与加仓参数 =====
    g.atr_period = 20
    g.max_units = 4
    g.initial_units = 3
    g.add_interval_n = 1.0
    g.unit_value_ratio = 1.0 / g.max_units
    g.units = 0
    g.last_entry_price = None
    g.entry_n = None
    g.stop_price = None
    g.stop_atr_mult = 4.0
    g.risk_per_unit_ratio = 0.01
    g.max_total_risk_ratio = 0.04
    g.max_market_risk_ratio = 0.06
    g.min_trade_value = 1000

    # ===== 避险判断 =====
    g.risk_vol_median_threshold = 0.40
    g.in_safe_asset = False

    run_daily(rebalance_trade, '09:35')


def etf_name(code):
    return (g.all_risk_etfs.get(code) or
            g.safe_etfs.get(code) or code)


def get_vol_rank(context, candidates):
    """返回按 60 日年化波动率升序排列的 Series"""
    etfs = list(candidates.keys())
    if not etfs:
        return pd.Series(dtype=float)
    df = get_price(
        etfs,
        end_date=context.previous_date,
        count=g.lookback + 1,
        frequency='daily',
        fields=['close'],
        panel=False
    )
    if 'time' in df.columns:
        df = df.sort_values(['code', 'time'])
    df['log_ret'] = df.groupby('code')['close'].transform(
        lambda x: np.log(x / x.shift(1))
    )
    grp = df.groupby('code')['log_ret']
    counts = grp.count()
    need = int(g.lookback * g.min_sample_ratio)
    valid = counts[counts >= need].index
    dropped = [c for c in counts.index if c not in valid]
    if dropped:
        log.info("样本不足剔除（<%d 个有效收益率）：%s" % (
            need, "、".join(f"{etf_name(c)}({counts[c]})" for c in dropped)))
    vol = grp.std().mul(np.sqrt(252)).loc[valid].dropna().sort_values()
    return vol


def get_atr_n(context, code):
    """计算 N = TR 的 20 日 EMA"""
    df = get_price(
        code,
        end_date=context.previous_date,
        count=g.atr_period + 1,
        frequency='daily',
        fields=['high', 'low', 'close'],
        panel=False
    )
    if df is None or len(df) < g.atr_period + 1:
        return None
    if 'time' in df.columns:
        df = df.sort_values('time')
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    tr_list = []
    for i in range(1, len(df)):
        h = high[i]
        l = low[i]
        pdc = close[i - 1]
        tr = max(h - l, abs(h - pdc), abs(l - pdc))
        tr_list.append(tr)
    if len(tr_list) < g.atr_period:
        return None
    n = np.mean(tr_list[:g.atr_period])
    for tr in tr_list[g.atr_period:]:
        n = (19 * n + tr) / 20
    return n


def open_position(context, code, note):
    """初始建仓：买入 initial_units 个 Unit，设置 N 和止损"""
    n = get_atr_n(context, code)
    if n is None or n <= 0:
        log.warn(f"{etf_name(code)} 无法计算N，放弃建仓")
        return False
    price = get_current_data()[code].last_price
    if price is None or np.isnan(price) or price <= 0:
        return False
    total_value = context.portfolio.total_value
    target_value = total_value * g.unit_value_ratio * g.initial_units
    target_value = min(target_value, context.portfolio.available_cash)
    if target_value < g.min_trade_value:
        log.warn(f"可用资金不足，放弃建仓：{target_value:.0f}")
        return False
    order_target_value(code, target_value)
    g.units = g.initial_units
    g.last_entry_price = price
    g.entry_n = n
    g.stop_price = price - g.stop_atr_mult * n
    g.hold_days = 0
    g.take_profit_done = False
    g.take_profit_armed = True
    g.in_safe_asset = False
    log.info(
        f"{note}：{etf_name(code)} {g.initial_units} Unit，金额 {target_value:,.0f}，"
        f"N={n:.4f}，止损={g.stop_price:.4f}（{g.stop_atr_mult:.0f}N）"
    )
    return True


def buy_safe_asset(context, code):
    """全仓买入避险资产（国债ETF），不设止损、不加仓"""
    price = get_current_data()[code].last_price
    if price is None or np.isnan(price) or price <= 0:
        return False
    total_value = context.portfolio.total_value
    order_target_value(code, total_value)
    g.units = g.max_units
    g.last_entry_price = None
    g.entry_n = None
    g.stop_price = None
    g.hold_days = 0
    g.take_profit_done = False
    g.take_profit_armed = True
    g.in_safe_asset = True
    log.info(f"避险买入：{etf_name(code)}，金额 {total_value:,.0f}")
    return True


def check_take_profit(context, code):
    """
    基于持仓成本止盈，卖出利润的一半。
    复利增强：止盈后不再转国债，资金留在账户里，
    允许后续用现金继续加仓。返回 True 表示已止盈。
    """
    if g.in_safe_asset:
        return False
    if code not in context.portfolio.positions:
        return False
    pos = context.portfolio.positions[code]
    if pos.total_amount <= 0:
        return False
    current_price = get_current_data()[code].last_price
    if current_price is None or np.isnan(current_price) or current_price <= 0:
        return False
    cost = pos.avg_cost
    if cost <= 0:
        return False
    ret = current_price / cost - 1
    if ret < g.take_profit_cost_threshold:
        g.take_profit_armed = True
        return False
    if not g.take_profit_armed:
        return False

    profit = pos.total_amount * (current_price - cost)
    if profit <= 0:
        return False
    sell_value = profit * g.take_profit_sell_profit_ratio
    sell_value = min(sell_value, pos.total_amount * current_price)
    sell_shares = int(sell_value / current_price / 100) * 100
    if sell_shares <= 0:
        log.info(f"止盈触发但不足一手：{etf_name(code)} 收益率 {ret:.2%}")
        return False

    sell_value = sell_shares * current_price
    target_value = pos.total_amount * current_price - sell_value
    order_target_value(code, target_value)

    g.take_profit_armed = False
    # 关键：不再设置 take_profit_done = True 阻止加仓，
    # 而是允许后续用现金继续加仓
    g.take_profit_done = False

    log.info(
        f"止盈：{etf_name(code)} 成本 {cost:.4f} 现价 {current_price:.4f}，"
        f"收益率 {ret:.2%}，利润约 {profit:,.0f}，"
        f"卖出利润一半 {sell_value:,.0f}，剩余市值 {target_value:,.0f}，"
        f"现金留在账户，后续可继续加仓"
    )
    return True


def check_stop_loss(context, code):
    """价格跌破止损价则清仓"""
    if g.in_safe_asset:
        return False
    if g.stop_price is None:
        return False
    price = get_current_data()[code].last_price
    if price is None or np.isnan(price) or price <= 0:
        return False
    if price <= g.stop_price:
        log.info(
            f"止损：{etf_name(code)} 价格 {price:.4f} <= "
            f"止损 {g.stop_price:.4f}，清仓"
        )
        order_target_value(code, 0)
        g.units = 0
        g.last_entry_price = None
        g.entry_n = None
        g.stop_price = None
        return True
    return False


def check_add_position(context, code):
    """
    检查并执行加仓，加仓间距用最新 N。
    复利增强：允许用现金继续加仓，止盈后不再阻止。
    """
    if g.in_safe_asset:
        return False
    if g.units >= g.max_units:
        return False
    if g.last_entry_price is None:
        return False

    price = get_current_data()[code].last_price
    if price is None or np.isnan(price) or price <= 0:
        return False

    current_n = get_atr_n(context, code)
    if current_n is None or current_n <= 0:
        return False

    trigger_price = g.last_entry_price + g.add_interval_n * current_n
    if price < trigger_price:
        return False

    # 加仓金额：优先用 Unit 计算，但受可用现金限制
    total_value = context.portfolio.total_value
    add_value = total_value * g.unit_value_ratio
    add_value = min(add_value, context.portfolio.available_cash)

    if add_value < g.min_trade_value:
        log.info(f"加仓资金不足：{add_value:.0f}")
        return False
    if g.units + 1 > g.max_units:
        return False

    pos = context.portfolio.positions[code]
    cur_shares = pos.total_amount
    add_shares = int(add_value / price / 100) * 100
    if add_shares <= 0:
        return False
    new_shares = cur_shares + add_shares

    new_stop = price - g.stop_atr_mult * current_n
    if new_stop <= 0:
        return False

    total_risk_ratio = (g.units + 1) * g.risk_per_unit_ratio
    if total_risk_ratio > g.max_total_risk_ratio:
        log.info(f"加仓后单品种总风险 {total_risk_ratio:.2%} 超限")
        return False
    if total_risk_ratio > g.max_market_risk_ratio:
        log.info(f"加仓后同市场组风险 {total_risk_ratio:.2%} 超限")
        return False

    cd = get_current_data()[code]
    if cd.paused:
        log.info("标的停牌，不加仓")
        return False

    log.info(
        f"加仓检查通过：{etf_name(code)} 现价 {price:.4f} >= "
        f"上次入场 {g.last_entry_price:.4f} + 1N({current_n:.4f})，"
        f"加 {add_shares} 份，Unit {g.units}->{g.units + 1}，"
        f"总风险 {total_risk_ratio:.2%}"
    )

    order_target_value(code, new_shares * price)
    g.units += 1
    g.last_entry_price = price
    g.entry_n = current_n
    g.stop_price = new_stop
    log.info(
        f"加仓完成：{etf_name(code)}，现 {g.units} Unit，"
        f"止损上移至 {g.stop_price:.4f}（4N）"
    )
    return True


def rebalance_trade(context):
    # 1. 计算风险资产波动率中位数
    risk_vol = get_vol_rank(context, g.all_risk_etfs)
    risk_vol_median = risk_vol.median() if len(risk_vol) > 0 else 0

    # 2. 判断是否允许避险（只看波动率中位数，去掉大盘风控）
    allow_safe = risk_vol_median > g.risk_vol_median_threshold
    log.info(f"风险资产波动率中位数 {risk_vol_median:.2%}；允许避险：{allow_safe}")

    # 3. 确定候选池
    if allow_safe:
        candidates = {**g.all_risk_etfs, **g.safe_etfs}
    else:
        candidates = g.all_risk_etfs

    vol = get_vol_rank(context, candidates)
    if len(vol) == 0:
        log.warn("无有效标的，今日不交易")
        return

    best = vol.index[0]
    best_vol = vol.iloc[0]

    top3 = "，".join(f"{etf_name(c)} {vol[c]:.1%}" for c in vol.index[:3])
    log.info(f"波动率最低三只：{top3}")

    # 4. 当前持仓
    held = [c for c in context.portfolio.positions
            if context.portfolio.positions[c].total_amount > 0]

    if len(held) > 1:
        for c in held[1:]:
            order_target_value(c, 0)
            log.warn(f"清理多余持仓：{etf_name(c)}({c})")
        held = held[:1]

    # 5. 空仓 → 建仓
    if not held:
        if best in g.safe_etfs:
            buy_safe_asset(context, best)
        else:
            open_position(context, best, "建仓")
        return

    cur = held[0]
    is_safe_cur = cur in g.safe_etfs

    # 6. 如果当前持有避险资产，检查是否应该换回风险资产
    if is_safe_cur:
        # 风控解除：波动率中位数 <= 0.40，allow_safe=False
        if not allow_safe:
            risk_vol_only = get_vol_rank(context, g.all_risk_etfs)
            if len(risk_vol_only) > 0:
                risk_best = risk_vol_only.index[0]
                risk_best_vol = risk_vol_only.iloc[0]
                log.info(f"风控解除，换回风险资产：{etf_name(risk_best)} "
                         f"波动率 {risk_best_vol:.2%}")
                order_target_value(cur, 0)
                g.in_safe_asset = False
                g.units = 0
                g.last_entry_price = None
                g.entry_n = None
                g.stop_price = None
                open_position(context, risk_best, "换回")
                return
        log.info(f"继续持有避险资产：{etf_name(cur)}")
        return

    # 7. 当前持有风险资产
    if check_stop_loss(context, cur):
        return
    if check_take_profit(context, cur):
        # 复利增强：止盈后不 return，继续往下走，尝试加仓
        pass

    g.hold_days += 1

    # 8. 如果当前持仓仍是最低波动，尝试加仓
    # 复利增强：止盈后仍允许加仓，只要满足加仓条件
    if cur == best:
        if check_add_position(context, cur):
            return
        log.info(f"当前持仓 {etf_name(cur)} 仍是最低波动，"
                 f"未触发加仓条件或资金不足，继续持有")
        return

    # 9. 当前持仓不在有效池，或波动率切换
    if cur not in vol.index:
        log.info(f"当前持仓 {etf_name(cur)} 已不在有效池，无条件换出")
        order_target_value(cur, 0)
        g.units = 0
        g.last_entry_price = None
        g.entry_n = None
        g.stop_price = None
        if best in g.safe_etfs:
            buy_safe_asset(context, best)
        else:
            open_position(context, best, "换入")
        return

    cur_vol = vol[cur]

    # 最短持有期
    if g.hold_days < g.min_hold_days:
        log.info(f"最短持有期未满：{etf_name(cur)} 已持有 {g.hold_days}/"
                 f"{g.min_hold_days} 日，"
                 f"{etf_name(best)}({best_vol:.2%}) 更低但不换")
        return

    # 波动率切换阈值
    if best_vol < cur_vol * (1 - g.switch_threshold):
        log.info(f"换仓：{etf_name(cur)} {cur_vol:.2%} → "
                 f"{etf_name(best)} {best_vol:.2%}")
        order_target_value(cur, 0)
        g.units = 0
        g.last_entry_price = None
        g.entry_n = None
        g.stop_price = None
        if best in g.safe_etfs:
            buy_safe_asset(context, best)
        else:
            open_position(context, best, "换入")
    else:
        log.info(f"抑制换手：{etf_name(best)} {best_vol:.2%} 仅比持仓 "
                 f"{etf_name(cur)} {cur_vol:.2%} 相对低 "
                 f"{1 - best_vol / cur_vol:.1%}，未达阈值 "
                 f"{g.switch_threshold:.0%}，继续持有")