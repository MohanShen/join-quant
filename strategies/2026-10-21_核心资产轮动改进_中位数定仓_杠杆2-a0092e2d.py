# Clone from JoinQuant
# postId: a0092e2d949803d35307c74f683fc421
# backtestId: e5c787a4788e9e7ed71d7e87a0fb3750
# title: 核心资产轮动改进：中位数定仓+杠杆2

# 基于 wywy1995《核心资产轮动》https://www.joinquant.com/post/42673
# 原版保留：黄金518880 / 纳指513100 / 创业板159915 / 红利510880
# 原版保留：get_rank 用 25 日对数收盘对时间回归，得分=年化斜率×R²，每天只持最高的 1 只
# 相对原版只加三处：换仓需领先现持 1%；仓位=min(2, 近252日波动中位数/近20日波动)；信用账户把现金买不够的部分融资买
# 调仓 9:50，避开开盘集合竞价。不含未来函数。

import math

import numpy as np
from jqdata import *

STRATEGY_TITLE = "核心资产轮动·波动中位数定仓杠杆2"
STRATEGY_VERSION = "2026-09-02.1"
SWITCH_THR = 0.01
VOL_LOOKBACK = 20
MEDIAN_LOOKBACK = 252
POS_DEADBAND = 0.02
MAX_LEVERAGE = 2.0
MARGIN_INTEREST = 0.08
MARGIN_RATE = 1.0


def initialize(context):
    # 必须第一句开信用账户，否则仓位写成 2 也借不到钱
    set_subportfolios(
        [SubPortfolioConfig(cash=context.portfolio.starting_cash, type="stock_margin")]
    )
    set_option("margincash_interest_rate", MARGIN_INTEREST)
    set_option("margincash_margin_rate", MARGIN_RATE)
    set_benchmark("000300.XSHG")
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(FixedSlippage(0.002))
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0002,
            close_commission=0.0002,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    log.set_level("order", "error")
    log.set_level("history", "error")
    log.set_level("system", "error")

    g.etf_pool = ["518880.XSHG", "513100.XSHG", "159915.XSHE", "510880.XSHG"]
    g.m_days = 25
    g.switch_thr = SWITCH_THR
    g.last_exposure = None
    g.max_leverage = MAX_LEVERAGE

    log.info(
        "初始化|%s|版本%s|杠杆上限%.1f|融资年利率%.0f%%|保证金比例%.0f%%"
        % (
            STRATEGY_TITLE,
            STRATEGY_VERSION,
            MAX_LEVERAGE,
            MARGIN_INTEREST * 100.0,
            MARGIN_RATE * 100.0,
        )
    )
    run_daily(trade, "9:50")


def scores_map(etf_pool):
    # 对应原版 get_rank
    out = {}
    for etf in etf_pool:
        df = attribute_history(etf, g.m_days, "1d", ["close"])
        y = np.log(df["close"].values.astype(float))
        x = np.arange(y.size)
        slope, intercept = np.polyfit(x, y, 1)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        r_squared = 1 - (
            np.sum((y - (slope * x + intercept)) ** 2) / ((len(y) - 1) * np.var(y, ddof=1))
        )
        out[etf] = float(annualized_returns * r_squared)
    return out


def pick_target(sc, cur):
    # 原版直接拿第一名；这里新标的必须领先现持 1% 才换，减少来回打脸
    target = max(sc, key=sc.get)
    if cur is None:
        return target
    if target == cur:
        return cur
    if sc[target] - sc[cur] < g.switch_thr:
        return cur
    return target


def vol_now_and_median(etf):
    need = MEDIAN_LOOKBACK + VOL_LOOKBACK + 5
    df = attribute_history(etf, need, "1d", ["close"])
    closes = df["close"].values.astype(float)
    if len(closes) < VOL_LOOKBACK + 2:
        return float("nan"), float("nan")
    rets = np.diff(closes) / closes[:-1]
    vols = []
    for i in range(VOL_LOOKBACK - 1, len(rets)):
        w = rets[i - VOL_LOOKBACK + 1 : i + 1]
        vols.append(float(np.std(w, ddof=1) * math.sqrt(252)))
    if len(vols) < 60:
        return float(vols[-1]) if vols else float("nan"), float("nan")
    return float(vols[-1]), float(np.median(vols[-MEDIAN_LOOKBACK:]))


def median_exposure(etf):
    # 近波动低 → 加仓，最高 2 倍；近波动高 → 减仓。算不出时默认满仓 1 倍，不借钱
    rv, med = vol_now_and_median(etf)
    if math.isnan(rv) or rv <= 1e-8 or math.isnan(med) or med <= 1e-8:
        exposure = 1.0
    else:
        cap = float(getattr(g, "max_leverage", MAX_LEVERAGE) or MAX_LEVERAGE)
        exposure = min(cap, med / rv)
    if g.last_exposure is not None and abs(exposure - g.last_exposure) < POS_DEADBAND:
        exposure = g.last_exposure
    g.last_exposure = exposure
    return exposure, rv, med


def _equity(context):
    p = context.portfolio
    liab = float(getattr(p, "total_liability", 0) or 0)
    return float(p.total_value) - liab


def _last_price(security):
    try:
        px = get_current_data()[security].last_price
        if px is None:
            return None
        px = float(px)
        if px <= 0:
            return None
        return px
    except Exception:
        return None


def _lot_shares(px, value):
    if px is None or px <= 0:
        return 0
    return int(float(value) / float(px) / 100.0) * 100


def _pos_amount(context, security):
    pos = context.portfolio.positions.get(security)
    if pos is None:
        return 0
    return int(pos.total_amount or 0)


def _can_margin_buy(security):
    try:
        names = get_margincash_stocks()
    except Exception:
        log.info("融资名单|拉取失败")
        return False
    if not names:
        log.info("融资名单|空")
        return False
    return security in names


def _apply_target_value(context, security, target_value):
    """目标市值可以大于净资产。不在融资名单则停在现金买到的数量。"""
    target_value = max(0.0, float(target_value))
    px = _last_price(security)
    if px is None:
        log.info("下单|无现价|%s" % security)
        return
    target_shares = _lot_shares(px, target_value)
    have = _pos_amount(context, security)
    delta = target_shares - have
    if delta == 0:
        return
    if delta < 0:
        sell = -delta
        try:
            margincash_close(security, sell)
        except Exception:
            pass
        still = _pos_amount(context, security)
        extra = still - target_shares
        if extra >= 100:
            order(security, -extra)
        if target_value <= 0:
            order_target_value(security, 0)
        return
    cash = float(context.portfolio.available_cash or 0)
    cash_shares = min(delta, _lot_shares(px, cash))
    if cash_shares >= 100:
        order(security, cash_shares)
    rest = delta - cash_shares
    if rest >= 100:
        if _can_margin_buy(security):
            margincash_open(security, rest)
            log.info("融资买入|%s|股数=%d" % (security, rest))
        else:
            log.info("不可融资|%s|差额股数=%d|当天停在现金上限" % (security, rest))


def trade(context):
    # 对应原版 trade：卖掉不是第一名的，再按目标市值买入第一名
    sc = scores_map(g.etf_pool)
    holds = list(context.portfolio.positions)
    cur = holds[0] if holds else None
    target = pick_target(sc, cur)
    for etf in list(context.portfolio.positions):
        if etf != target:
            _apply_target_value(context, etf, 0)
    exposure, rv, med = median_exposure(target)
    eq = _equity(context)
    _apply_target_value(context, target, eq * exposure)
    log.info(
        "中位数定仓杠杆2|目标%s|近波动%.3f|中位%.3f|仓位%.2f|净资产%.0f"
        % (
            target,
            rv if not math.isnan(rv) else -1,
            med if not math.isnan(med) else -1,
            exposure,
            eq,
        )
    )
