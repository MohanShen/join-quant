# Clone from JoinQuant
# postId: 8de9c8bd942565b1e015bcb1c202f728
# backtestId: 3870c9b45f9648a546e3a277441b94e9
# title: 全市场ETF轮动策略

# -*- coding: utf-8 -*-
# 克隆自聚宽文章：https://www.joinquant.com/post/79968
# 标题：五福ETF候选池改成点时动态池：6328%→1570%
# 作者：Smart_Trader_AFA

# 克隆自聚宽文章：https://www.joinquant.com/post/78826
# 标题：五福52V3-多ETF-2015年至今收益126倍回撤25%
# 作者：rbq2025
#
# ---- 改进（只改一处）----
# 原版用一份硬编码的"固定ETF池"（约120只，含大量2022-2025年才上市、
# 且事后涨得好/流动性高的标的），属于用未来信息选池。
# 本版仅使用按回测当日时点动态构建的ETF池（get_all_securities(date=...)+流动性过滤），
# 其余逻辑（S1抄底、S2五福轮动、择时、容器）与原版一致。

# 克隆自聚宽文章：https://www.joinquant.com/post/78044
# 标题：乖离率抄底v3五福c06/1.5.4版
# 作者：大鱼飞飞

#乖离率抄底v2五福C06.-1.5.10.-rbq2025
# 1.5.10 实盘修复：CapitalAllocator 含 lambda、_CTX 为模块级变量，模拟/实盘隔日重启无法 pickle；
#          process_initialize/after_code_changed 重建分配器并回填 context（initialize 只跑一次）
# 1.5.9 S1/S2加入运行时相关性守卫；S1等权仓位上限，S2按动量得分加权并限制单只仓位
# 1.5.8 按2026-08沪深所LOF退市新规，从筛选池剔除商品期货/QDII/迷你LOF
# 1.5.7 分策略累计收益/回撤：卖出记已实现，15:01 打日志并 record 到回测曲线
# 1.5.6 修复无主残留锁死 bottom：close_position 余股不清归属；日检清幽灵仓；S1 空仓即回 rot
# 1.5.5 S1 抄底按 MAX_HOLD 等权持有多只：入场价按标的记账，仓位未满可补仓，全部卖完才回 rot
# 1.5.4 修复 yy_corr_pair 尾部相关计算的 pandas FutureWarning：union索引先取交集再 .loc
# 1.5.3 调度时间参数化：S2卖出/买入/趋势复检/强制买入时间抽到顶部参数，改时间无需动调度代码
# 1.5.2 回测前修复：S1买入未成交不进bottom；open_position按filled>0登记+MIN_OPEN_GRANT参数化；
#          排名日志分段输出/限条数；建池轻量化(跟踪指数表/全ETF按日缓存、相关性批量取价)

# 克隆自聚宽文章：https://www.joinquant.com/post/77965
# 标题：170倍变594倍，抄底+五福 融合策略
# 作者：zzob

# -*- coding: utf-8 -*-
"""
融合策略：S1 乖离率抄底(高优先级) + S2 五福C06轮动(低优先级)，基于多策略容器框架。
========================================================
机制（对应 zzob 已实证的"抄底切换优于减半"）：
  - 平时（rot 模式）：S2 五福C06 满仓轮动，可借用 S1 空仓资金打满仓位。
  - S1 深跌抄底信号触发（先超跌-16% 后企稳，T-1 数据判定）：
      -> 进入 bottom 模式，清空 S2 全部持仓，按 MAX_HOLD 等权买入最多 N 只抄底标的。
  - S1 抄底卖出信号触发（止损/止盈/时间上限）：
      -> 仅卖出触发的标的；S1 全部清空后回到 rot 模式，S2 下个交易日恢复轮动。

容器层：CapitalAllocator（空闲资金池 + 优先级借还）+ 归属簿记 + 下单收口。
下单一律经 open_position/close_position（带策略归属 sid），绝不过手 order_target_value。
信号均用 T-1 及以前数据，set_option("avoid_future_data", True) 禁止未来函数。

子策略来源：
  - S1: correct_etf_strategy.py 乖离率抄底（正确基线参数）
  - S2: c06.py 五福C06（当前回测版，2248行完整逻辑）
"""

"""
融合策略：S1 乖离率抄底 + S2 五福C06轮动，多策略容器框架。
【优化】S2 走弱期判定改为"分基准独立判定"：
  - 每只ETF按自己的参照基准（A股/港股/美股/原油/黄金/日股/欧股/债券）
    决定走强市还是弱市过滤流程。
  - 不再用A股大盘一个开关决定所有ETF。
"""
from jqdata import *
import numpy as np
import math
import pandas as pd
import json
import re
import datetime as _dt
from datetime import datetime, date, timedelta


# =====================================================================
# S1 模块级参数
# =====================================================================
__version__ = "1.2.0"

# -------------------- ETF池构建参数 --------------------
EXCLUDE_MONEY = True
EXCLUDE_BOND = True
EXCLUDE_DIVIDEND = False
EXCLUDE_CROSS = False
EXCLUDE_COMMODITY = False

MIN_LIST_DAYS = 180
AVG_MONEY_DAYS = 20

EXCLUDE_MINI = True
MINI_SCALE = 2.0
EXCLUDE_LIQUIDITY = True
MIN_MONEY = 1000

CONSTITUENT_OVERLAP = 0.90
WEIGHT_OVERLAP = 0.90

CORR_LOOKBACK = 120
CORR_SPEARMAN_TH = 0.90
CORR_TAIL_TH = 0.90
CORR_SPEARMAN_TH_PCT = int(CORR_SPEARMAN_TH * 100)
CORR_TAIL_TH_PCT = int(CORR_TAIL_TH * 100)

SHOW_FULL_POOL = False

# -------------------- 策略交易参数 --------------------
MAX_HOLD = 2
BIAS_SORT_DAYS = 50
BIAS_BUY_DAYS = 20
BUY_BIAS_TH = -16
SELL_BIAS_TH = 0
STOP_LOSS_PCT = 0.15
SELL_PROFIT_PCT = 0.03
HOLD_MAX_DAYS = 30
RUN_TIME = "09:35"
POOL_UPDATE_MONTHLY = True
POOL_REFRESH_MONTHS = 3

TREND_FILTER_MODE = 0
TREND_LOOKBACK = 5
OVERSOLD_LOOKBACK = 5

# -------------------- 融合调度时间参数 --------------------
S2_SELL_TIME = "13:10"
S2_BUY_TIME = "13:30"
S2_CHECK_TIMES = ["13:40", "14:10", "14:40"]
S2_FORCE_TIME = "14:55"

# -------------------- LOF退市新规 --------------------
EXCLUDE_LOF_DELIST = True
LOF_DELIST_RULE_DATE = _dt.date(2015, 1, 1)
LOF_DELIST_NAV_DAYS = 60
LOF_DELIST_NAV_WAN = 1000
LOF_COMMODITY_FUTURES_KEYWORDS = ['期货', '白银', '豆粕', '能源化工', '大宗商品', '有色金属', '商品']
LOF_QDII_KEYWORDS = [
    'QDII', '原油', '油气', '石油', '黄金', '贵金属',
    '标普', '纳指', '纳斯达克', '道琼斯', '日经', '东证', '德国', '法国', '英国', '欧洲',
    '美国', '美股', '印度', '越南', '沙特', '巴西', '韩国', '全球', '海外', '亚太',
    '香港', '港股', '恒生', '中概',
]
LOF_QDII_EXCLUDE_KEYWORDS = ['港股通', '沪港深', '沪深港', '深港通', '黄金股']
LOF_DELIST_KEEP_CODES = []
LOF_DELIST_DROP_CODES = []
LOF_DELIST_AUDIT_LOG = True


# =====================================================================
# 【优化】标的 → 参照基准 映射表
# =====================================================================
BENCHMARK_A_SHARE_300   = '000300.XSHG'
BENCHMARK_A_SHARE_500   = '000905.XSHG'
BENCHMARK_A_SHARE_1000  = '000852.XSHG'
BENCHMARK_A_GEM         = '399006.XSHE'
BENCHMARK_A_STAR        = '000688.XSHG'
BENCHMARK_HK_TECH       = 'HSTECH.HI'
BENCHMARK_HK_HSI        = 'HSI.HI'
BENCHMARK_US_NASDAQ     = 'IXIC.GI'
BENCHMARK_US_SP500      = 'SPX.GI'
BENCHMARK_JP_N225       = 'N225.GI'
BENCHMARK_EU_DAX        = 'GDAXI.GI'
BENCHMARK_OIL_WTI       = 'CL.NYM'
BENCHMARK_GOLD          = 'GC.CMX'
BENCHMARK_SOYBEAN       = 'ZS.CBT'
BENCHMARK_COPPER        = 'HG.CMX'
BENCHMARK_BOND_CN       = '000012.XSHG'

# 若外盘代码取不到数据，可改为国内代理ETF：
#   纳指 → 513100.XSHG
#   原油 → 162411.XSHE
#   黄金 → 518880.XSHG
#   日经 → 513520.XSHG
# 下面规则表已优先使用国内代理，最稳。
_BENCHMARK_RULES = [
    # ---- 商品 ----
    (['原油', '石油', '油气', '能源化工', '天然气'], '162411.XSHE'),
    (['豆粕', '农产品'], '159985.XSHE'),
    (['黄金', '白银', '贵金属'], '518880.XSHG'),
    (['有色', '铜', '铝', '稀有金属', '矿业'], '512400.XSHG'),
    # ---- 外盘 ----
    (['纳斯达克', '纳指', '纳100'], '513100.XSHG'),
    (['标普', '道琼斯', '美国', '美股'], '513500.XSHG'),
    (['日经', '东证', '日本'], '513520.XSHG'),
    (['德国', '法国', '英国', '欧洲'], '513030.XSHG'),
    (['恒生科技', '恒指科技', 'HS科技', '港股科技', '恒生互联', '中概', '恒生医药'],
     '513130.XSHG'),
    (['恒生', '恒指', '港股', '港股通', 'H股', '香港', '香港证券', '港股非银'],
     '159920.XSHE'),
    # ---- 债券 ----
    (['国债', '政金债', '国开债', '利率债', '信用债', '城投债', '公司债',
      '短融', '转债', '可转债', '地债'], '511010.XSHG'),
    # ---- A股细分 ----
    (['创业板', '创成长', '创50'], BENCHMARK_A_GEM),
    (['科创', '科创板', '科创创业', '双创'], BENCHMARK_A_STAR),
    (['中证500', '500ETF', '中证1000', '1000ETF', '中证2000', '2000ETF'],
     BENCHMARK_A_SHARE_1000),
]


def classify_benchmark(etf_code, etf_name=None):
    """给ETF返回其参照基准代码。未命中规则时返回沪深300。"""
    name = etf_name or ''
    if not name:
        try:
            name = get_security_name(etf_code)
        except Exception:
            name = ''
    for keywords, bench in _BENCHMARK_RULES:
        for kw in keywords:
            if kw in name:
                return bench
    return BENCHMARK_A_SHARE_300


def _benchmark_get_close_series(bench_code, end_date, count):
    try:
        df = get_price(bench_code, end_date=end_date, count=count,
                       frequency='daily', fields=['close'],
                       skip_paused=True, panel=False)
        if df is None or len(df) == 0:
            return None
        return df['close'].values
    except Exception:
        return None


def compute_benchmark_weak(bench_code, context, ma_lookback=10):
    """单基准走弱：收盘 < MA(ma_lookback)。取不到数据 fail-open（返回False）。"""
    need = ma_lookback + 2
    closes = _benchmark_get_close_series(bench_code, context.previous_date, need)
    if closes is None or len(closes) < ma_lookback:
        return False, None, None
    last = float(closes[-1])
    ma = float(np.mean(closes[-ma_lookback:]))
    return last < ma, last, ma


def update_benchmark_weak_states(context):
    """每天调用一次：刷新所有基准的走弱状态。"""
    if not hasattr(g, 'benchmark_weak') or g.benchmark_weak is None:
        g.benchmark_weak = {}
    if not hasattr(g, 'benchmark_last') or g.benchmark_last is None:
        g.benchmark_last = {}

    all_benches = set([b for _, b in _BENCHMARK_RULES]) | {BENCHMARK_A_SHARE_300}
    for bench in all_benches:
        weak, last, ma = compute_benchmark_weak(bench, context, g.weak_period_ma_lookback)
        g.benchmark_weak[bench] = weak
        g.benchmark_last[bench] = (last, ma)

    key_benches = [BENCHMARK_A_SHARE_300, '513130.XSHG', '513100.XSHG',
                   '162411.XSHE', '518880.XSHG', '511010.XSHG']
    parts = []
    for b in key_benches:
        w = g.benchmark_weak.get(b, False)
        parts.append(f"{b}={'弱' if w else '正'}")
    log.info(f"📊 【分基准走弱判定】{' | '.join(parts)}")


def get_etf_weak_state(etf_code, etf_name=None):
    bench = classify_benchmark(etf_code, etf_name)
    return bool(getattr(g, 'benchmark_weak', {}).get(bench, False)), bench


# =====================================================================
# 容器框架
# =====================================================================
class CapitalAllocator:
    def __init__(self, strategies, used_of, sell_some):
        self.strategies = strategies
        self.used_of = used_of
        self.sell_some = sell_some

    def idle_pool(self, total_value):
        used_all = sum(self.used_of(s) for s in self.strategies)
        return max(0.0, total_value - used_all)

    def usable(self, sid, total_value):
        base = total_value * self.strategies[sid]["base_ratio"]
        others_idle = 0.0
        for o, acc in self.strategies.items():
            if o == sid:
                continue
            others_idle += max(0.0, total_value * acc["base_ratio"] - self.used_of(o))
        return base + others_idle

    def ensure_nominal(self, sid, total_value):
        acc = self.strategies[sid]
        base_value = total_value * acc["base_ratio"]
        shortage = max(0.0, base_value - self.idle_pool(total_value) - self.used_of(sid))
        if shortage <= 1e-9:
            return 0.0
        lower = sorted(
            (s for s in self.strategies if self.strategies[s]["priority"] < acc["priority"]),
            key=lambda s: self.strategies[s]["priority"],
        )
        reclaimed = 0.0
        for other in lower:
            if shortage <= 1e-9:
                break
            over = max(0.0, self.used_of(other) - total_value * self.strategies[other]["base_ratio"])
            if over <= 1e-9:
                continue
            got = self.sell_some(other, min(over, shortage))
            reclaimed += got
            shortage -= got
        return reclaimed


_CTX = {}
def context_holder():
    return _CTX.get("ctx")

def set_context(context):
    _CTX["ctx"] = context

def allocator_init(context):
    g.accounts = {}
    g.stock_owner = {}
    g.__allocator = None
    g.strategy_realized = {}
    g.strategy_peak = {}
    g.strategy_max_dd = {}
    g.strategy_max_dd_date = {}
    g.strategy_prev_equity = {}

def _allocator_used_of(sid):
    return _used_of(context_holder(), sid)

def _allocator_sell_some(sid, amt):
    return _sell_some(context_holder(), sid, amt)

def rebuild_allocator():
    alloc = CapitalAllocator(
        strategies=g.accounts,
        used_of=_allocator_used_of,
        sell_some=_allocator_sell_some,
    )
    g.__allocator = alloc
    _CTX["allocator"] = alloc

def register_strategy(sid, base_ratio, priority=1, enabled=True):
    g.accounts[sid] = {
        "base_ratio": base_ratio,
        "priority": priority,
        "enabled": enabled,
        "holdings": [],
    }
    if not hasattr(g, 'strategy_realized') or g.strategy_realized is None:
        g.strategy_realized = {}
        g.strategy_peak = {}
        g.strategy_max_dd = {}
        g.strategy_max_dd_date = {}
        g.strategy_prev_equity = {}
    g.strategy_realized.setdefault(sid, 0.0)
    g.strategy_peak.setdefault(sid, 0.0)
    g.strategy_max_dd.setdefault(sid, 0.0)
    g.strategy_max_dd_date.setdefault(sid, '')
    g.strategy_prev_equity.setdefault(sid, 0.0)
    rebuild_allocator()

def _used_of(context, sid):
    if context is None:
        return 0.0
    acc = g.accounts[sid]
    total = 0.0
    for s in list(acc["holdings"]):
        pos = context.portfolio.positions.get(s)
        if pos:
            total += pos.value
    return total

def _sell_some(context, sid, amount):
    if context is None:
        return 0.0
    acc = g.accounts[sid]
    released = 0.0
    for s in list(acc["holdings"]):
        if amount - released <= 1e-9:
            break
        pos = context.portfolio.positions.get(s)
        if not pos or pos.closeable_amount <= 0:
            continue
        if pos.value <= (amount - released):
            close_position(s)
            released += pos.value
        else:
            target = pos.value - (amount - released)
            avg_cost = pos.avg_cost
            order = my_order_target_value(s, target)
            _book_realized_from_order(sid, order, avg_cost)
            released += amount - released
    return released


MIN_OPEN_GRANT = 5000

def _get_allocator():
    alloc = _CTX.get("allocator")
    if alloc is None:
        try:
            alloc = g.__allocator
        except AttributeError:
            alloc = None
    if alloc is None:
        rebuild_allocator()
        alloc = _CTX.get("allocator")
    return alloc

def open_position(context, security, value, sid):
    set_context(context)
    total = context.portfolio.total_value
    acc = g.accounts[sid]
    if not acc["enabled"]:
        return None
    allocator = _get_allocator()
    allocator.ensure_nominal(sid, total)
    grant = min(value, allocator.usable(sid, total))
    if grant < MIN_OPEN_GRANT:
        log.info("【容器·买入放弃】%s 可批额度 %.2f < 最小 %.0f", security, grant, MIN_OPEN_GRANT)
        return None
    order = my_order_target_value(security, grant)
    if order:
        filled = getattr(order, 'filled', 0)
        if filled > 0:
            if security not in acc["holdings"]:
                acc["holdings"].append(security)
            g.stock_owner[security] = sid
        else:
            log.info("【容器·买入未成交】%s 订单未成交(filled=0)，不登记归属", security)
    return order

def close_position(security):
    sid = g.stock_owner.get(security)
    ctx = context_holder()
    avg_cost = 0.0
    if ctx is not None:
        pos = ctx.portfolio.positions.get(security)
        if pos is not None:
            avg_cost = pos.avg_cost
    order = my_order_target_value(security, 0)
    _book_realized_from_order(sid, order, avg_cost)
    remaining = None
    if ctx is not None:
        pos = ctx.portfolio.positions.get(security)
        remaining = pos.total_amount if pos is not None else 0
    if remaining is None:
        return order
    if remaining <= 0:
        if sid is not None:
            acc = g.accounts[sid]
            if security in acc["holdings"]:
                acc["holdings"].remove(security)
            g.stock_owner.pop(security, None)
    elif order:
        filled = getattr(order, 'filled', 0)
        log.info("【容器·卖出未清完】%s 成交%g股，仍持仓%g，保留归属 sid=%s",
                 security, filled, remaining, sid)
    return order


_STRATEGY_LABEL = {1: 'S1抄底', 2: 'S2轮动'}


def _book_realized_from_order(sid, order, avg_cost):
    if sid is None or order is None:
        return 0.0
    filled = getattr(order, 'filled', 0) or 0
    if filled <= 0:
        return 0.0
    fill_price = getattr(order, 'price', 0) or 0
    if fill_price <= 0 or avg_cost is None:
        return 0.0
    commission = getattr(order, 'commission', 0) or 0
    pnl = (fill_price - avg_cost) * filled - commission
    if not hasattr(g, 'strategy_realized') or g.strategy_realized is None:
        g.strategy_realized = {}
    g.strategy_realized[sid] = g.strategy_realized.get(sid, 0.0) + pnl
    return pnl


def _strategy_unrealized_and_mkt(context, sid):
    unrealized = 0.0
    mkt = 0.0
    seen = set()
    for sec, owner in list(getattr(g, 'stock_owner', {}).items()):
        if owner != sid or sec in seen:
            continue
        seen.add(sec)
        pos = context.portfolio.positions.get(sec)
        if pos is None or pos.total_amount <= 0:
            continue
        unrealized += (pos.price - pos.avg_cost) * pos.total_amount
        mkt += pos.value
    acc = g.accounts.get(sid)
    if acc:
        for sec in list(acc.get('holdings', [])):
            if sec in seen:
                continue
            pos = context.portfolio.positions.get(sec)
            if pos is None or pos.total_amount <= 0:
                continue
            unrealized += (pos.price - pos.avg_cost) * pos.total_amount
            mkt += pos.value
    return unrealized, mkt


def make_record(context):
    if not hasattr(g, 'strategy_realized') or g.strategy_realized is None:
        g.strategy_realized = {}
        g.strategy_peak = {}
        g.strategy_max_dd = {}
        g.strategy_max_dd_date = {}
        g.strategy_prev_equity = {}

    starting_cash = context.portfolio.starting_cash
    total_value = context.portfolio.total_value
    total_ret = total_value / starting_cash - 1.0 if starting_cash > 0 else 0.0
    max_port = getattr(g, 'max_portfolio_value', 0.0) or 0.0
    if total_value > max_port:
        g.max_portfolio_value = total_value
        max_port = total_value
    port_dd = (max_port - total_value) / max_port if max_port > 0 else 0.0
    today = context.current_dt.strftime('%Y-%m-%d')
    mode = getattr(g, 'mode', 'rot')

    rec = {}
    lines = [
        "【分策略绩效】%s  模式=%s  账户净值=%.0f  累计=%+.2f%%  回撤=%.2f%%" % (
            today, mode, total_value, total_ret * 100, port_dd * 100),
    ]

    for sid, acc in g.accounts.items():
        if not acc.get("enabled") or acc.get("base_ratio", 0) <= 0:
            continue
        nominal0 = starting_cash * acc["base_ratio"]
        unrealized, mkt = _strategy_unrealized_and_mkt(context, sid)
        realized = g.strategy_realized.get(sid, 0.0)
        equity = nominal0 + realized + unrealized
        ret = equity / nominal0 - 1.0 if nominal0 > 0 else 0.0

        peak = g.strategy_peak.get(sid, 0.0) or 0.0
        if peak <= 0:
            peak = max(nominal0, equity)
        if equity > peak:
            peak = equity
        g.strategy_peak[sid] = peak
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = g.strategy_max_dd.get(sid, 0.0) or 0.0
        if dd > max_dd:
            max_dd = dd
            g.strategy_max_dd_date[sid] = today
        g.strategy_max_dd[sid] = max_dd

        prev = g.strategy_prev_equity.get(sid, 0.0) or 0.0
        day_pnl = equity - prev if prev > 0 else (realized + unrealized)
        g.strategy_prev_equity[sid] = equity

        label = _STRATEGY_LABEL.get(sid, '策略%d' % sid)
        lines.append(
            "  %s  权益=%.0f  累计=%+.2f%%  当日盈亏=%+.0f  已实现=%+.0f  浮盈=%+.0f  "
            "回撤=%.2f%%  最大回撤=%.2f%%(%s)  持仓市值=%.0f" % (
                label, equity, ret * 100, day_pnl, realized, unrealized,
                dd * 100, max_dd * 100, g.strategy_max_dd_date.get(sid, '-') or '-',
                mkt)
        )
        rec['策略%d' % sid] = round(ret * 100, 2)
        rec['策略%d回撤' % sid] = round(dd * 100, 2)
        rec['策略%d最大回撤' % sid] = round(max_dd * 100, 2)

    rec['账户累计'] = round(total_ret * 100, 2)
    rec['账户回撤'] = round(port_dd * 100, 2)
    for line in lines:
        log.info(line)
    try:
        record(**rec)
    except Exception:
        pass


def schedule(context, plan):
    for fn, mode, t in plan:
        if mode == "daily":
            run_daily(fn, t)
        elif mode == "weekly":
            run_weekly(fn, 2, t)
        elif mode == "monthly":
            run_monthly(fn, 1, t)


def my_order_target_value(security, value):
    o = order_target_value(security, value)
    return o
    
# =====================================================================
# S1 乖离率抄底子策略
# =====================================================================

def s1_init_state(context):
    g.etf_pool = []
    g.last_pool_refresh_month = 0
    g.entry_price = {}
    g.entry_date = {}
    g.MAX_HOLD          = getattr(g, 'MAX_HOLD', MAX_HOLD)
    g.BIAS_SORT_DAYS    = getattr(g, 'BIAS_SORT_DAYS', BIAS_SORT_DAYS)
    g.BIAS_BUY_DAYS     = getattr(g, 'BIAS_BUY_DAYS', BIAS_BUY_DAYS)
    g.BUY_BIAS_TH       = getattr(g, 'BUY_BIAS_TH', BUY_BIAS_TH)
    g.SELL_BIAS_TH      = getattr(g, 'SELL_BIAS_TH', SELL_BIAS_TH)
    g.STOP_LOSS_PCT     = getattr(g, 'STOP_LOSS_PCT', STOP_LOSS_PCT)
    g.SELL_PROFIT_PCT   = getattr(g, 'SELL_PROFIT_PCT', SELL_PROFIT_PCT)
    g.HOLD_MAX_DAYS     = getattr(g, 'HOLD_MAX_DAYS', HOLD_MAX_DAYS)
    g.TREND_FILTER_MODE = getattr(g, 'TREND_FILTER_MODE', TREND_FILTER_MODE)
    g.TREND_LOOKBACK    = getattr(g, 'TREND_LOOKBACK', TREND_LOOKBACK)
    g.OVERSOLD_LOOKBACK = getattr(g, 'OVERSOLD_LOOKBACK', OVERSOLD_LOOKBACK)

    g.s1_enable_corr_filter = False
    g.s1_corr_use_raw_pearson = True
    g.s1_corr_threshold = 0.8
    g.s1_corr_lookback_days = 60
    g.s1_log_corr_detail = True
    g.s1_corr_candidate_multiplier = 10

    g.s1_enable_position_mgmt = False
    g.s1_max_single_position = 0.5
    g.s1_single_etf_max_position = 0.9
    g.s1_log_position_detail = True

    log.info("正在初始化S1 ETF股票池（完整版v2.2.3），请稍候...")
    g.etf_pool = build_etf_pool(context.previous_date)
    g.etf_pool = filter_delisting_lofs(g.etf_pool, context, 'S1池')
    g.last_pool_refresh_month = context.current_dt.month


# ---------- LOF 退市新规 ----------
def _lof_delist_asof(context=None, asof_date=None):
    if context is not None:
        return context.current_dt.date()
    if asof_date is not None:
        return pd.Timestamp(asof_date).date()
    return None


def lof_delist_rule_active(context=None, asof_date=None):
    if not EXCLUDE_LOF_DELIST:
        return False
    asof = _lof_delist_asof(context, asof_date)
    if asof is None:
        return False
    return asof >= LOF_DELIST_RULE_DATE


def _lof_security_name(code):
    d = getattr(g, 'etf_names_dict', None) or {}
    if code in d:
        return str(d[code] or '')
    try:
        return str(get_security_info(code).display_name or '')
    except Exception:
        return str(code)


def _lof_security_type(code):
    cache = getattr(g, '_lof_type_cache', None)
    if cache is None:
        g._lof_type_cache = {}
        cache = g._lof_type_cache
    if code in cache:
        return cache[code]
    t = ''
    try:
        t = str(getattr(get_security_info(code), 'type', '') or '').lower()
    except Exception:
        t = ''
    cache[code] = t
    return t


def _lof_code_suspect(code, name=''):
    if 'LOF' in str(name).upper():
        return True
    parts = str(code).split('.')
    prefix = parts[0]
    mkt = parts[-1] if len(parts) > 1 else ''
    if mkt == 'XSHE':
        return prefix[:2] == '16'
    if mkt == 'XSHG':
        return prefix[:3] in ('500', '501', '502', '505', '506')
    return False


def is_lof_fund(code, name=''):
    t = _lof_security_type(code)
    if t:
        return t == 'lof'
    return _lof_code_suspect(code, name or _lof_security_name(code))


def _lof_onexchange_nav_wan_list(code, end_date, days):
    end_ts = pd.Timestamp(end_date)
    try:
        nav = get_extras('unit_net_value', [code], end_date=end_ts, count=days)
    except Exception:
        nav = None
    if nav is None or (hasattr(nav, 'empty') and nav.empty):
        return []
    if isinstance(nav, pd.DataFrame):
        if code in nav.columns:
            nav_s = nav[code]
        elif len(nav.columns) == 1:
            nav_s = nav.iloc[:, 0]
        else:
            return []
    else:
        return []

    shares_map = {}
    try:
        start_d = (end_ts - _dt.timedelta(days=int(days * 2.2 + 10))).strftime('%Y-%m-%d')
        end_d = end_ts.strftime('%Y-%m-%d')
        q = (query(finance.FUND_SHARE_DAILY)
             .filter(finance.FUND_SHARE_DAILY.code == code,
                     finance.FUND_SHARE_DAILY.date >= start_d,
                     finance.FUND_SHARE_DAILY.date <= end_d))
        sh = finance.run_query(q)
        if sh is not None and len(sh) > 0:
            for d, s in zip(sh['date'], sh['shares']):
                try:
                    shares_map[str(pd.Timestamp(d).date())] = float(s)
                except Exception:
                    continue
    except Exception:
        pass
    if not shares_map:
        return []

    out = []
    for dt, nv in nav_s.dropna().items():
        try:
            nv = float(nv)
        except Exception:
            continue
        if nv <= 0:
            continue
        ds = str(pd.Timestamp(dt).date())
        shv = shares_map.get(ds)
        if shv is None:
            continue
        out.append(float(shv) * nv / 10000.0)
    return out[-days:]


def _lof_mini_scale_hit(code, end_date):
    cache = getattr(g, '_lof_mini_cache', None)
    if cache is None:
        g._lof_mini_cache = {}
        cache = g._lof_mini_cache
    key = (str(code), str(pd.Timestamp(end_date).date()))
    if key in cache:
        return cache[key]
    hit = False
    try:
        vals = _lof_onexchange_nav_wan_list(code, end_date, LOF_DELIST_NAV_DAYS)
        if len(vals) >= LOF_DELIST_NAV_DAYS:
            hit = all(v < LOF_DELIST_NAV_WAN for v in vals[-LOF_DELIST_NAV_DAYS:])
    except Exception:
        hit = False
    cache[key] = hit
    return hit


def _lof_name_hit(name, keywords):
    if not name:
        return False
    for kw in keywords:
        if kw and kw in name:
            return True
    return False


def classify_lof_delist_reason(code, name='', end_date=None):
    if code in LOF_DELIST_KEEP_CODES:
        return None
    if code in LOF_DELIST_DROP_CODES:
        return '人工指定退市'
    if not _lof_code_suspect(code, name):
        return None
    name = name or _lof_security_name(code)
    if not is_lof_fund(code, name):
        return None
    n = str(name)
    if n.lstrip().startswith('*'):
        return '场内简称*退市标识'
    n_up = n.upper()
    if _lof_name_hit(n, LOF_COMMODITY_FUTURES_KEYWORDS):
        return '商品期货LOF'
    if 'QDII' in n_up or (_lof_name_hit(n, LOF_QDII_KEYWORDS)
                          and not _lof_name_hit(n, LOF_QDII_EXCLUDE_KEYWORDS)):
        return 'QDII LOF'
    if end_date is not None and _lof_mini_scale_hit(code, end_date):
        return f'场内净值连续{LOF_DELIST_NAV_DAYS}日<{LOF_DELIST_NAV_WAN}万'
    return None


def filter_delisting_lofs(codes, context=None, tag='', asof_date=None, names=None, silent=False):
    if not codes:
        return []
    codes = list(codes)
    if not lof_delist_rule_active(context, asof_date):
        return codes
    end_date = None
    if context is not None:
        end_date = context.previous_date
    elif asof_date is not None:
        end_date = asof_date
    names = names or {}
    kept = []
    dropped = []
    for code in codes:
        reason = classify_lof_delist_reason(code, names.get(code, ''), end_date)
        if reason:
            nm = names.get(code) or _lof_security_name(code)
            dropped.append(f"{nm}({code}){reason}")
        else:
            kept.append(code)
    if dropped and not silent:
        label = tag or '筛选池'
        log.info(f"【LOF退市新规】{label}剔除{len(dropped)}只: " + "；".join(dropped[:20]))
    return kept


def log_lof_delist_audit(context):
    if not (EXCLUDE_LOF_DELIST and LOF_DELIST_AUDIT_LOG):
        return
    pool = list(getattr(g, 'fixed_etf_pool', []) or [])
    suspects = [c for c in pool if _lof_code_suspect(c)]
    log.info(f"【LOF退市新规·自检】固定池{len(pool)}只，其中疑似LOF {len(suspects)}只，"
             f"其余为ETF不在新规范围；规则生效日 {LOF_DELIST_RULE_DATE}")
    end_date = context.previous_date
    for code in suspects:
        nm = _lof_security_name(code)
        t = _lof_security_type(code) or '未知'
        reason = classify_lof_delist_reason(code, nm, end_date)
        log.info(f"  {nm}({code}) type={t} -> {reason or '保留'}")


# =====================================================================
# S2 子策略状态初始化
# =====================================================================
def s2_init_state(context):
    log.info("[机制测试] C06_C03加入V6.6强弱市过滤 | 【优化】分基准独立走弱判定")
    log.info("【五福v1.2】择时执行 + opt2_v4 + H72 + H78a 方案B(MA+R²) 启动！")

    g.global_etf_pool = []
    g.china_etf_pool = []
    g.fixed_etf_pool = []

    g.avg_etf_money_threshold = None
    g.filtered_fixed_pool = []
    g.dynamic_etf_pool = []
    g.merged_etf_pool = []
    g.ranked_etfs_result = []
    g.filtered_global_pool = []

    # --- 全局A股走弱（兼容旧字段）---
    g.is_a_share_weak = False
    g.weak_period_ma_lookback = 10
    g.weak_start_date = None
    g.weak_days_count = 0
    g.max_weak_days = 20

    # --- 【优化】分基准走弱状态 ---
    g.benchmark_weak = {}
    g.benchmark_last = {}
    g.etf_benchmark_cache = {}

    g.holdings_num = 3
    g.defensive_etf = "511880.XSHG"
    g.min_money = 10
    g.target_etfs_list = []
    g.pending_buy_etfs = []
    g.target_position_values = {}

    g.s2_enable_corr_filter = True
    g.s2_corr_use_raw_pearson = True
    g.s2_corr_threshold = 0.8
    g.s2_corr_lookback_days = 60
    g.s2_log_corr_detail = True

    g.s2_enable_position_mgmt = True
    g.s2_position_weight_metric = 'score'
    g.s2_position_weight_power = 1.5
    g.s2_max_single_position = 0.5
    g.s2_single_etf_max_position = 0.9
    g.s2_log_position_detail = True
    g._runtime_corr_cache_date = None
    g._runtime_corr_cache = {}
    g.etf_names_dict = {}
    g.cache_date = None
    g.yesterday_close_cache = {}
    g.trend_lookback_minutes = 30
    g.trend_slope_threshold = 0.001
    g.trend_r2_threshold = 0.3

    g.lookback_days = 25
    g.min_score_threshold = 0
    g.max_score_threshold = 5
    g.score_threshold_ratio = 0.9

    g.enable_r2_filter = True
    g.r2_threshold = 0.4
    g.enable_ma_filter = True
    g.ma_lookback = 10
    g.ma_threshold = 1.0
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 1.8
    g.enable_loss_filter = True
    g.loss = 0.97
    g.enable_premium_filter = False
    g.max_premium_rate = 30
    g.enable_laplace_filter = False
    g.laplace_s_param = 0.05
    g.laplace_min_slope = 0.002
    g.dynamic_pool_top_n = 150
    g.liquidity_threshold_divisor = 15000

    g.max_portfolio_value = 0
    g.drawdown_threshold = 0.03
    g.drawdown_records = []

    g.use_fixed_stop_loss = False
    g.fixedStopLossThreshold = 0.95
    g.use_pct_stop_loss = False
    g.pct_stop_loss_threshold = 0.95

    g.enable_super_mainline = True
    g.mainline_score_min = 5.0
    g.mainline_score_max = 20.0
    g.mainline_days = 5
    g.mainline_min_r2 = 0.85
    g.mainline_min_r2_avg = 0.90
    g.mainline_min_volume_avg = 1.8
    g.mainline_min_score_up_days = 4
    g.mainline_min_positive_laplace_days = 5
    g.mainline_min_score_growth = 2.0

    g.enable_mainline_retain = True
    g.mainline_retain_min_r2 = 0.85
    g.mainline_retain_min_lap_slope = 0.0

    g.enable_regime_p0 = True
    g.regime_breadth_ma = 20
    g.regime_breadth_high = 0.55
    g.regime_breadth_structural = 0.50
    g.regime_breadth_low = 0.35
    g.regime_liquidity_min_yi = 20000.0
    g.regime_liquidity_lookback = 20
    g.regime_p0_log = []

    g.enable_choppy_detection = True
    g.choppy_lookback = 10
    g.choppy_max_ret = 0.010
    g.is_choppy = False
    g.enable_volume_divergence_filter = True
    g.vd_lookback = 5
    g.vd_price_up_threshold = 0.02
    g.vd_vol_down_threshold = -0.10

    g.weak_momentum_lookback = 25
    g.weak_momentum_lookback_base = 25
    g.weak_momentum_lookback_short = 23
    g.enable_dynamic_weak_lookback = True
    g.r2_lookback_for_signal_quality = 25
    g.r2_threshold_for_signal_quality = 0.4
    g.r2_threshold_exit = 0.38
    g.r2_hysteresis_enter_days = 2
    g.r2_hysteresis_exit_days = 2
    g.r2_signal_aggregation = "mean"
    g.r2_dynamic_tag = "H72"
    g.r2_high_streak = 0
    g.r2_low_streak = 0
    g.r2_dyn_days_23 = 0
    g.r2_dyn_days_25 = 0
    g.r2_dyn_switch_count = 0

    g.enable_weak_r2_filter = True

    log.info(f"""
【策略参数初始化完成 · 优化版v1.2】
=== 分基准走弱判定 ===
- 每只ETF按自己的参照基准（A股/港股/美股/原油/黄金/日股/欧股/债券）独立判定
- 走弱期：收盘 < MA{g.weak_period_ma_lookback}
- 走弱期宽松过滤（仅动量+R²），正常期严格过滤（全套）
=== S2 参数 ===
- 持仓数量: {g.holdings_num}只
- 动量周期: {g.lookback_days}天
- 得分阈值: [{g.min_score_threshold}, {g.max_score_threshold}]
""")


# ---------- S1/S2 共用：运行时相关性守卫与仓位管理 ----------
def _fetch_close_panel_for_runtime_corr(codes, lookback, end_date):
    if not codes:
        return pd.DataFrame()
    try:
        raw = get_price(
            list(codes), end_date=end_date, count=int(lookback),
            frequency='daily', fields=['close'], panel=False,
        )
        if raw is None or raw.empty:
            return pd.DataFrame()
        price_df = raw.pivot(index='time', columns='code', values='close')
        price_df = price_df.dropna(thresh=max(2, int(lookback * 0.7)), axis=1)
        return price_df.ffill().dropna()
    except Exception as e:
        log.warning(f"【相关性守卫】取价失败，按数据不足放行: {e}")
        return pd.DataFrame()


def compute_runtime_corr_matrix(price_df, use_raw_pearson=True):
    if price_df is None or price_df.empty or price_df.shape[1] < 1:
        return pd.DataFrame()
    if price_df.shape[1] == 1:
        code = price_df.columns[0]
        return pd.DataFrame([[1.0]], index=[code], columns=[code])
    returns_df = np.log(price_df / price_df.shift(1)).dropna()
    if returns_df.empty:
        return pd.DataFrame()
    base_corr = returns_df.corr()
    if use_raw_pearson:
        return base_corr
    cum_returns = price_df / price_df.iloc[0] - 1
    vols = returns_df.std() * np.sqrt(252)
    curve_diff = np.mean(
        np.abs(cum_returns.values[:, :, None] - cum_returns.values[:, None, :]),
        axis=0,
    )
    ret_factor = np.exp(-curve_diff)
    vol_arr = vols.values
    vol_min = np.minimum(vol_arr[:, None], vol_arr[None, :])
    vol_max = np.maximum(vol_arr[:, None], vol_arr[None, :])
    vol_max[vol_max == 0] = 1e-9
    adj = base_corr.values * ret_factor * (vol_min / vol_max)
    codes = price_df.columns.tolist()
    return pd.DataFrame(adj, index=codes, columns=codes)


def _runtime_corr_config(sid):
    prefix = 's1' if sid == SID_S1 else 's2'
    return {
        'enabled': bool(getattr(g, f'{prefix}_enable_corr_filter', False)),
        'raw': bool(getattr(g, f'{prefix}_corr_use_raw_pearson', True)),
        'threshold': float(getattr(g, f'{prefix}_corr_threshold', 0.8)),
        'lookback': int(getattr(g, f'{prefix}_corr_lookback_days', 60)),
        'detail': bool(getattr(g, f'{prefix}_log_corr_detail', False)),
        'label': prefix.upper(),
    }


def get_runtime_corr_matrix_cached(context, codes, sid):
    cfg = _runtime_corr_config(sid)
    today = context.current_dt.date()
    if getattr(g, '_runtime_corr_cache_date', None) != today:
        g._runtime_corr_cache_date = today
        g._runtime_corr_cache = {}
    key = (sid, tuple(sorted(set(codes))), cfg['raw'], cfg['lookback'])
    cache = getattr(g, '_runtime_corr_cache', {})
    if key in cache:
        return cache[key]
    price_df = _fetch_close_panel_for_runtime_corr(key[1], cfg['lookback'], context.previous_date)
    corr = compute_runtime_corr_matrix(price_df, cfg['raw'])
    cache[key] = corr
    g._runtime_corr_cache = cache
    if cfg['detail'] and not corr.empty:
        mode = '原始Pearson' if cfg['raw'] else '修正P_adj'
        log.info(f"【{cfg['label']}相关性】矩阵{corr.shape[0]}×{corr.shape[1]}，"
                 f"{mode}，回看{cfg['lookback']}日")
    return corr


def _pair_runtime_corr(code_a, code_b, corr):
    if corr is None or corr.empty:
        return None
    if code_a not in corr.index or code_b not in corr.columns:
        return None
    try:
        val = float(corr.loc[code_a, code_b])
        return None if pd.isna(val) else val
    except Exception:
        return None


def apply_correlation_guard_codes(context, ordered_codes, already_codes, need, sid):
    if need <= 0 or not ordered_codes:
        return []
    cfg = _runtime_corr_config(sid)
    if not cfg['enabled']:
        return list(ordered_codes[:need])
    all_codes = list(dict.fromkeys(list(already_codes) + list(ordered_codes)))
    corr = get_runtime_corr_matrix_cached(context, all_codes, sid)
    chosen = list(already_codes)
    selected = []
    for code in ordered_codes:
        if len(selected) >= need:
            break
        max_corr = None
        conflict = None
        for held in chosen:
            value = _pair_runtime_corr(code, held, corr)
            if value is not None and (max_corr is None or value > max_corr):
                max_corr, conflict = value, held
        if max_corr is not None and max_corr >= cfg['threshold']:
            if cfg['detail']:
                log.info(f"【{cfg['label']}相关性】跳过 {code} {get_security_name(code)}："
                         f"与 {conflict} {get_security_name(conflict)} 相关性"
                         f"{max_corr:.3f}≥{cfg['threshold']:.3f}")
            continue
        selected.append(code)
        chosen.append(code)
    return selected


def apply_correlation_guard_metrics(context, ordered_metrics, already_selected, need, sid):
    metric_map = {m['etf']: m for m in ordered_metrics}
    selected_codes = apply_correlation_guard_codes(
        context,
        [m['etf'] for m in ordered_metrics],
        [m['etf'] for m in already_selected],
        need,
        sid,
    )
    return [metric_map[c] for c in selected_codes]


def _apply_position_cap(weights, cap):
    if not weights:
        return {}
    cap = max(0.0, min(1.0, float(cap)))
    w = dict(weights)
    uncapped = set(w)
    for _ in range(len(w) + 1):
        over = [code for code in uncapped if w[code] > cap + 1e-12]
        if not over:
            break
        excess = float(np.sum([w[code] - cap for code in over]))
        for code in over:
            w[code] = cap
            uncapped.discard(code)
        subtotal = float(np.sum([w[code] for code in uncapped]))
        if not uncapped or subtotal <= 0:
            break
        for code in uncapped:
            w[code] += excess * w[code] / subtotal
    return {code: min(value, cap) for code, value in w.items()}


def compute_s1_target_values(context, target_etfs):
    n = len(target_etfs)
    if n == 0:
        return {}
    total_val = context.portfolio.total_value * 0.995
    weights = {code: 1.0 / n for code in target_etfs}
    if getattr(g, 's1_enable_position_mgmt', False):
        cap = (g.s1_single_etf_max_position if n == 1 else g.s1_max_single_position)
        weights = _apply_position_cap(weights, cap)
    else:
        cap = 1.0
    targets = {code: total_val * weights[code] for code in target_etfs}
    if getattr(g, 's1_log_position_detail', False):
        log.info(f"【S1仓位】等权分配，目标{n}只，单只上限{cap:.0%}")
        for code in target_etfs:
            log.info(f"  {code} {get_security_name(code)} 权重{weights[code]:.1%} 目标{targets[code]:.0f}元")
    return targets


def compute_s2_target_values(context, target_etfs):
    n = len(target_etfs)
    if n == 0:
        return {}
    total_val = context.portfolio.total_value
    if not getattr(g, 's2_enable_position_mgmt', False):
        return {code: total_val / n for code in target_etfs}
    metric_map = {m['etf']: m for m in (getattr(g, 'ranked_etfs_result', []) or [])}
    key = {'score': 'momentum_score', 'long': 'annualized_returns'}.get(
        getattr(g, 's2_position_weight_metric', 'score'), 'momentum_score')
    power = float(getattr(g, 's2_position_weight_power', 1.0))
    raw = {}
    for code in target_etfs:
        try:
            value = max(float(metric_map.get(code, {}).get(key, 0.0)), 0.0)
        except (TypeError, ValueError):
            value = 0.0
        raw[code] = value ** power if value > 0 else 0.0
    total_raw = float(np.sum(list(raw.values())))
    if total_raw <= 0:
        weights = {code: 1.0 / n for code in target_etfs}
        basis = '指标非正，等权兜底'
    else:
        weights = {code: raw[code] / total_raw for code in target_etfs}
        basis = f'{key}^{power:g}'
    cap = g.s2_single_etf_max_position if n == 1 else g.s2_max_single_position
    weights = _apply_position_cap(weights, cap)
    targets = {code: total_val * weights[code] for code in target_etfs}
    if getattr(g, 's2_log_position_detail', False):
        invested = float(np.sum(list(weights.values())))
        log.info(f"【S2仓位】依据{basis}，单只上限{cap:.0%}")
        for code in target_etfs:
            metric = metric_map.get(code, {}).get(key, 0.0)
            log.info(f"  {code} {get_security_name(code)} 权重{weights[code]:.1%} "
                     f"目标{targets[code]:.0f}元 ({key}={metric})")
        if invested < 0.999:
            log.info(f"  受上限约束，投资{invested:.1%}，剩余{1-invested:.1%}留现金")
    return targets
    
# =====================================================================
# 流水线
# =====================================================================
def check_weak_period_daily(context):
    if g.mode == 'bottom':
        return
    check_a_share_weak_period(context)
    if getattr(g, 'enable_choppy_detection', False):
        check_choppy_market(context)
    midday_routine(context)


def check_choppy_market(context):
    if not getattr(g, 'enable_choppy_detection', False):
        return
    indexes = ['000300.XSHG', '399101.XSHE', '399006.XSHE', '000510.XSHG']
    choppy_count = 0
    details = []
    for code in indexes:
        try:
            df = attribute_history(code, g.choppy_lookback + 1, '1d', ['close'], skip_paused=False)
            if df is None or len(df) < g.choppy_lookback + 1:
                details.append(f"{code}:数据不足")
                continue
            ret_10d = float(df['close'].iloc[-1] / df['close'].iloc[0] - 1)
            details.append(f"{code}:{ret_10d:+.2%}")
            if abs(ret_10d) < g.choppy_max_ret:
                choppy_count += 1
        except Exception:
            details.append(f"{code}:异常")
    was_choppy = bool(getattr(g, 'is_choppy', False))
    g.is_choppy = (choppy_count >= 3)
    if g.is_choppy and not was_choppy:
        log.info(f"🟡 【震荡市检测】{choppy_count}/4 指数近10日涨跌幅<{g.choppy_max_ret:.0%}，进入震荡模式 | {', '.join(details)}")
    elif not g.is_choppy and was_choppy:
        log.info(f"🟢 【震荡市检测】退出震荡模式 | {', '.join(details)}")


def check_volume_price_divergence(hist_closes, hist_volumes, context):
    if not getattr(g, 'enable_volume_divergence_filter', False):
        return True, {'reason': 'disabled'}
    if hist_closes is None or hist_volumes is None:
        return True, {'reason': 'no_data'}
    if len(hist_closes) < g.vd_lookback + 1 or len(hist_volumes) < g.vd_lookback + 1:
        return True, {'reason': 'insufficient_data'}
    try:
        price_change = float(hist_closes[-1] / hist_closes[-g.vd_lookback - 1] - 1)
        recent_vol = float(np.mean(hist_volumes[-3:]))
        earlier_vol = float(np.mean(hist_volumes[-g.vd_lookback - 1:-3]))
        if earlier_vol <= 0:
            return True, {'reason': 'earlier_vol_zero'}
        vol_change = float(recent_vol / earlier_vol - 1)
        is_divergence = (price_change > g.vd_price_up_threshold and vol_change < g.vd_vol_down_threshold)
        return (not is_divergence), {
            'price_change': price_change,
            'vol_change': vol_change,
            'is_divergence': is_divergence,
            'reason': 'divergence' if is_divergence else 'ok'
        }
    except Exception:
        return True, {'reason': 'error'}


def morning_routine(context):
    build_dynamic_global_pool(context)
    if g.mode == 'bottom':
        return
    log.info("★" * 80)
    log.info("▶️ 【晨间流水线】启动...")
    log.info("【持仓检查】检查当前持仓状态...")
    check_positions(context)
    if getattr(g, 'use_pct_stop_loss', False):
        log.info("【昨收缓存】批量缓存持仓昨收，供分钟止损使用...")
        _refresh_yesterday_close_cache(context)
    log.info("【回撤监控】监控策略回撤...")
    monitor_drawdown(context)
    log.info("【流动性阈值】计算全市场ETF流动性阈值...")
    calculate_global_etf_threshold(context)
    log.info("⏸️ 【晨间流水线】执行完毕！")


def midday_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【早盘流水线】启动...")

    if g.is_a_share_weak:
        log.info(f"🔴 【A股走弱】点时动态构建全球/海外ETF池并做流动性过滤...")
        build_dynamic_global_pool(context)
        filter_global_pool_by_volume(context)
        log.info(f"【A股走弱】过滤后全球池: {len(g.filtered_global_pool)}只")
    else:
        log.info(f"🟢 【A股正常】执行动态池更新、固定池过滤、合并池...")
        log.info("【动态池更新】更新行业ETF动态池（各行业流动性最佳ETF）...")
        update_sector_pool(context)
        log.info("【固定池过滤】过滤固定ETF池流动性...")
        filter_fixed_pool_by_volume(context)
        log.info("【合并池】合并固定池与动态池...")
        daily_merge_etf_pools(context)
        log.info(f"【A股正常】合并池: {len(g.merged_etf_pool)}只")

    log.info("⏸️ 【早盘流水线】执行完毕！")


def afternoon_routine(context):
    """【优化】不再用A股走弱一刀切，改为候选池=正常池∪全球池，
    逐只在 apply_filters 里按自己基准决定过滤严格度。"""
    if g.mode == 'bottom':
        return
    log.info("▶️ 【午盘流水线】启动...")

    normal_pool = list(getattr(g, 'merged_etf_pool', []) or [])
    global_pool = []
    try:
        build_dynamic_global_pool(context)
        filter_global_pool_by_volume(context)
        global_pool = list(getattr(g, 'filtered_global_pool', []) or [])
    except Exception as e:
        log.warning(f"【全球池】并入候选失败: {e}")

    merged = list(set(normal_pool) | set(global_pool))
    merged.sort()
    merged = filter_delisting_lofs(merged, context, '午盘合并池')
    g.merged_etf_pool = merged

    log.info(f"🟢 【午盘候选池】正常池{len(normal_pool)}只 + 全球池{len(global_pool)}只 "
             f"→ 合并后{len(merged)}只（逐只按自己的基准过滤）")

    log.info("【动量计算】计算ETF动量得分与排序...")
    calculate_and_log_ranked_etfs(context)
    log.info("【卖出执行】执行卖出操作...")
    execute_sell_trades(context)
    log.info(f"⏸️ 【午盘流水线·卖出】执行完毕！（买入将于{S2_BUY_TIME}单独执行）")


def reset_daily_flags(context):
    g.cache_date = None
    g.yesterday_close_cache = {}
    g.pending_buy_etfs = []
    g.etf_benchmark_cache = {}   # 【优化】每天清一次
    log.info("🔄 收盘缓存重置完成")


# =====================================================================
# R²动态走弱动量窗口 H72
# =====================================================================
def adjust_weak_momentum_lookback(context):
    """【优化】只基于A股大盘基准调整全局弱市动量窗口。
    其他基准的动量窗口由 calculate_all_metrics_for_etf 里按自己的 benchmark 决定。"""
    if not getattr(g, "enable_dynamic_weak_lookback", False):
        return
    try:
        # 只针对A股大盘基准的池子做 R² 均值判断
        etf_pool = [c for c in (getattr(g, 'merged_etf_pool', []) or [])
                    if classify_benchmark(c) in (BENCHMARK_A_SHARE_300,
                                                  BENCHMARK_A_GEM,
                                                  BENCHMARK_A_STAR,
                                                  BENCHMARK_A_SHARE_1000)]
        if not etf_pool:
            return
        lookback_days = g.r2_lookback_for_signal_quality
        end_date = context.previous_date
        r2_values = []
        for etf in etf_pool:
            try:
                df = get_price(etf, end_date=end_date, count=lookback_days + 1,
                               frequency="daily", fields=["close"], panel=False)
                if df is None or df.empty or len(df) < lookback_days + 1:
                    continue
                price_series = df["close"].values
                y = np.log(price_series)
                x = np.arange(len(y))
                weights = np.linspace(1, 2, len(y))
                W = weights ** 2
                W_sum = np.sum(W)
                x_bar = np.sum(W * x) / W_sum
                y_bar = np.sum(W * y) / W_sum
                dx = x - x_bar
                dy = y - y_bar
                variance_x = np.sum(W * dx ** 2)
                if variance_x == 0:
                    continue
                slope = np.sum(W * dx * dy) / variance_x
                intercept = y_bar - slope * x_bar
                y_pred = slope * x + intercept
                ss_res = np.sum(weights * (y - y_pred) ** 2)
                ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
                r_squared = 1 - ss_res / ss_tot if ss_tot else 0
                r2_values.append(r_squared)
            except Exception:
                continue
        if not r2_values:
            return

        agg = getattr(g, "r2_signal_aggregation", "mean")
        if agg == "median":
            pool_r2 = float(np.median(r2_values))
        else:
            pool_r2 = float(np.mean(r2_values))
        thr_hi = g.r2_threshold_for_signal_quality
        thr_lo = getattr(g, "r2_threshold_exit", 0.38)
        need_enter = int(getattr(g, "r2_hysteresis_enter_days", 2))
        need_exit = int(getattr(g, "r2_hysteresis_exit_days", 2))
        tag = getattr(g, "r2_dynamic_tag", "H72")

        if pool_r2 > thr_hi:
            g.r2_high_streak = getattr(g, "r2_high_streak", 0) + 1
            g.r2_low_streak = 0
        elif pool_r2 < thr_lo:
            g.r2_low_streak = getattr(g, "r2_low_streak", 0) + 1
            g.r2_high_streak = 0
        else:
            g.r2_high_streak = 0
            g.r2_low_streak = 0

        old_lookback = g.weak_momentum_lookback
        new_lookback = old_lookback
        reason = "hold"
        if old_lookback == g.weak_momentum_lookback_base and g.r2_high_streak >= need_enter:
            new_lookback = g.weak_momentum_lookback_short
            reason = "enter_23"
        elif old_lookback == g.weak_momentum_lookback_short and g.r2_low_streak >= need_exit:
            new_lookback = g.weak_momentum_lookback_base
            reason = "exit_23"

        switched = new_lookback != old_lookback
        if switched:
            g.weak_momentum_lookback = new_lookback
            g.r2_dyn_switch_count = getattr(g, "r2_dyn_switch_count", 0) + 1

        if g.weak_momentum_lookback == g.weak_momentum_lookback_short:
            g.r2_dyn_days_23 = getattr(g, "r2_dyn_days_23", 0) + 1
        else:
            g.r2_dyn_days_25 = getattr(g, "r2_dyn_days_25", 0) + 1

        if g.is_a_share_weak or switched:
            log.info(f"[R2动态{tag}] date={context.current_dt.date()} weak={int(g.is_a_share_weak)} "
                     f"pool_r2={pool_r2:.4f} agg={agg} hi={g.r2_high_streak}/{need_enter} "
                     f"lo={g.r2_low_streak}/{need_exit} reason={reason} "
                     f"lb={g.weak_momentum_lookback} switched={int(switched)}")
            try:
                record(r2_avg=pool_r2, r2_weak_lb=float(g.weak_momentum_lookback))
            except Exception:
                pass
    except Exception as e:
        log.info(f"[R2动态{tag}] adjust 异常: {e}")


def check_positions(context):
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 【持仓检查】{security} {security_name}, 数量: {position.total_amount}, "
                     f"成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")


def monitor_drawdown(context):
    try:
        current_value = context.portfolio.total_value
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        if g.max_portfolio_value > 0:
            current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
            if current_drawdown >= g.drawdown_threshold:
                rec = {
                    'date': context.current_dt.strftime('%Y-%m-%d'),
                    'drawdown': current_drawdown,
                    'portfolio_value': current_value,
                    'max_value': g.max_portfolio_value,
                    'is_weak': g.is_a_share_weak
                }
                positions_info = []
                for security in context.portfolio.positions:
                    position = context.portfolio.positions[security]
                    if position.total_amount > 0:
                        security_name = get_security_name(security)
                        positions_info.append(f"{security_name}:{position.total_amount}股")
                rec['positions'] = positions_info
                g.drawdown_records.append(rec)
                log.info(f"【回撤预警】回撤达到 {current_drawdown:.2%} (阈值: {g.drawdown_threshold:.0%})")
    except Exception as e:
        log.error(f"【回撤监控】计算异常: {e}")


def calculate_global_etf_threshold(context):
    log.info("【全局阈值更新】开始计算全市场ETF流动性门槛")
    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            g.avg_etf_money_threshold = 10000000
            return
        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]
        df = get_price(security=etf_list, start_date=start_day, end_date=context.previous_date,
                       frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or df.empty:
            g.avg_etf_money_threshold = 10000000
            return
        daily_totals = df.groupby('time')['money'].sum()
        if len(daily_totals) < 3:
            g.avg_etf_money_threshold = 10000000
            return
        avg_total_money = daily_totals.mean()
        threshold = avg_total_money / g.liquidity_threshold_divisor
        g.avg_etf_money_threshold = threshold
        log.info(f"【全局阈值更新完成】近{len(daily_totals)}日全市场ETF日均总成交额="
                 f"{avg_total_money/1e8:.2f}亿元，阈值={threshold/1e4:.0f}万元")
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}，使用保守阈值1000万")
        g.avg_etf_money_threshold = 10000000


# ---------- 动态全球池 ----------
GLOBAL_POOL_KEYWORDS = [
    '黄金', '豆粕', '有色', '油气', '原油', '石油', '纳指', '纳斯达克', '标普',
    '日经', '道琼斯', '德国', '法国', '沙特', '中韩', '越南', '印度', '美国',
    '海外', '全球',
]
GLOBAL_POOL_EXCLUDE = ['债', '国债', '信用', '城投', '转债', '货币', '现金', '短融', '利率', '红利低波']


def build_dynamic_global_pool(context):
    try:
        df = get_all_securities(['etf', 'lof'], date=context.previous_date)
        names = df['display_name'].to_dict()
    except Exception as e:
        log.warning(f"【动态全球池】获取ETF列表失败: {e}")
        g.global_etf_pool = []
        return
    out = []
    for code in df.index:
        nm = names.get(code, '')
        if any(k in nm for k in GLOBAL_POOL_EXCLUDE):
            continue
        if any(k in nm for k in GLOBAL_POOL_KEYWORDS):
            out.append(code)
    g.global_etf_pool = out
    log.info(f"【动态全球池】时点={context.previous_date}，按关键词构建，共{len(out)}只")


def filter_global_pool_by_volume(context):
    log.info("【全球池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        calculate_global_etf_threshold(context)
    if not g.global_etf_pool:
        g.filtered_global_pool = []
        return
    dynamic_threshold = g.avg_etf_money_threshold
    log.info(f"【全球池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.global_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT,
                               frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            g.filtered_global_pool = filter_delisting_lofs(g.global_etf_pool[:], context, '全球池')
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_global_pool = qualified.index.tolist()
        g.filtered_global_pool = filter_delisting_lofs(new_global_pool, context, '全球池')
        log.info(f"【全球池过滤】保留高流动性ETF({len(g.filtered_global_pool)}只)")
    except Exception as e:
        log.warning(f"【全球池过滤】异常: {e}")
        g.filtered_global_pool = filter_delisting_lofs(g.global_etf_pool[:], context, '全球池')


def update_sector_pool(context):
    log.info("【动态池更新】开始执行")
    if g.avg_etf_money_threshold is None:
        calculate_global_etf_threshold(context)

    FUND_COMPANIES = sorted(list(set([
        '易方达', '广发', '华夏', '华安', '嘉实', '富国', '招商', '鹏华', '南方', '汇添富', '国泰', '平安',
        '银华', '天弘', '建信', '工银', '华泰柏瑞', '博时', '景顺长城', '景顺', '华宝', '申万菱信', '万家', '中欧',
        '兴证全球', '浙商', '诺安', '前海开源', '泰康', '泰达宏利', '农银汇理', '交银', '东方红', '财通', '华商',
        '国联', '永赢', '金鹰', '德邦', '创金合信', '西部利得', '圆信永丰', '泓德', '汇安', '诺德', '恒生前海',
        '华润元大', '大成', '海富通', '摩根', '华泰', '中信', '中银', '兴全', '国信', '长城', '中金', '浙商证券',
        '东海', '东吴', '浦银安盛', '信达澳亚', '中加', '中航', '中融', '中邮', '中庚', '中信保诚', '中信建投',
        '中银国际', '中银证券', '九泰', '交银施罗德', '光大保德信', '兴银', '农银', '国投瑞银', '国海富兰克林',
        '国联安', '国金', '太平', '方正富邦', '民生加银', '汇丰晋信', '银河', '长信', '长安', '长盛', '长江证券', '鹏扬'
    ])), key=len, reverse=True)

    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)

    SPECIAL_GROUPS = sorted([
        {'name': '香港组', 'keywords': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS科技'], key=len, reverse=True),
         'remove_words': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS'], key=len, reverse=True)},
        {'name': '科创组', 'keywords': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True),
         'remove_words': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创', '债券', '债汇', '债指', '债沪', '债易', '债基', '债兴', '债摩', '债', 'AAA'], key=len, reverse=True)},
        {'name': '创业组', 'keywords': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True),
         'remove_words': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True)},
        {'name': '美指组', 'keywords': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True),
         'remove_words': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True)}
    ], key=lambda x: max(len(kw) for kw in x['keywords']), reverse=True)

    exclude_keywords = sorted(list(set([
        '300', '500', '1000', '2000', '800', '30', '50', '100', '180', '200',
        '沪深', '中证', '上证', '深证', '深成', 'A50', 'A100', 'A500', '深100',
        '短融', '可转债', '转债', '双债', '利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债',
        '信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债', '科创债', '科债', '科创AAA',
        '自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流',
        '货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数',
        '全指现金', '现金全指', 'ESG', 'MSCI', 'MS', '债',
    ])), key=len, reverse=True)

    try:
        df_etf = get_all_securities(['etf'])
        etf_list = df_etf.index.tolist()
        g.etf_names_dict = df_etf['display_name'].to_dict()
        etf_list = filter_delisting_lofs(etf_list, context, '动态池', names=g.etf_names_dict)
    except Exception as e:
        log.warning(f"获取全市场ETF列表失败: {e}")
        return

    log.info(f"【动态池更新】全市场ETF总数: {len(etf_list)}只")
    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0

    for code in etf_list:
        try:
            name = g.etf_names_dict.get(code, str(code))
            is_special = False
            matched_group = None
            for group in SPECIAL_GROUPS:
                for kw in group['keywords']:
                    if kw in name:
                        is_special = True
                        matched_group = group['name']
                        break
                if is_special:
                    break
            is_excluded = False
            for k in exclude_keywords:
                if k in name:
                    is_excluded = True
                    excluded_count += 1
                    break
            if not is_excluded:
                if is_special:
                    special_etfs.append(code)
                    special_group_map[code] = matched_group
                else:
                    normal_etfs.append(code)
        except Exception:
            continue

    log.info(f"【动态池更新】进入特别组: {len(special_etfs)}只")
    log.info(f"【动态池更新】进入普通组: {len(normal_etfs)}只")

    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold

    def filter_by_liquidity(etf_codes):
        if not etf_codes:
            return pd.Series(dtype=float)
        try:
            price_data = get_price(etf_codes, end_date=end_date, count=TRADE_DAYS_COUNT,
                                   frequency='daily', fields=['money'], panel=False)
            if price_data is None or price_data.empty:
                return pd.Series(dtype=float)
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / TRADE_DAYS_COUNT
            return avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
        except Exception:
            return pd.Series(dtype=float)

    normal_qualified = filter_by_liquidity(normal_etfs)
    special_qualified = filter_by_liquidity(special_etfs)
    normal_sorted = normal_qualified.index.tolist()
    special_sorted = special_qualified.index.tolist()

    if not normal_sorted and not special_sorted:
        g.dynamic_etf_pool = []
        return

    def get_remove_words(matched_group_name):
        for group in SPECIAL_GROUPS:
            if group['name'] == matched_group_name:
                return group['remove_words']
        return []

    def clean_name(original_name, is_special=False, matched_group_name=None):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        if is_special and matched_group_name:
            for word in get_remove_words(matched_group_name):
                cleaned = cleaned.replace(word, '')
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()

    normal_industry_groups = {}
    for code in normal_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            money = normal_qualified[code]
            cleaned = clean_name(original_name, is_special=False)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            normal_industry_groups.setdefault(industry_key, []).append({
                'code': code, 'original_name': original_name, 'money': money,
            })
        except Exception:
            continue

    special_industry_groups = {}
    for code in special_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            money = special_qualified[code]
            cleaned = clean_name(original_name, is_special=True, matched_group_name=matched_group)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            group_key = f"{matched_group}_{industry_key}"
            special_industry_groups.setdefault(group_key, []).append({
                'code': code, 'original_name': original_name, 'money': money,
            })
        except Exception:
            continue

    final_pool_info = []
    for _, items in normal_industry_groups.items():
        final_pool_info.append(sorted(items, key=lambda x: x['money'], reverse=True)[0])
    for _, items in special_industry_groups.items():
        final_pool_info.append(sorted(items, key=lambda x: x['money'], reverse=True)[0])

    final_pool_info_sorted = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    top_n = getattr(g, 'dynamic_pool_top_n', 100)
    top_100 = final_pool_info_sorted[:top_n]
    g.dynamic_etf_pool = [item['code'] for item in top_100]
    log.info(f"【动态池更新完成】动态池共{len(g.dynamic_etf_pool)}只ETF")


def filter_fixed_pool_by_volume(context):
    log.info("【固定池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        calculate_global_etf_threshold(context)
    if not g.fixed_etf_pool:
        return
    dynamic_threshold = g.avg_etf_money_threshold
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.fixed_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT,
                               frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            g.filtered_fixed_pool = filter_delisting_lofs(g.fixed_etf_pool[:], context, '固定池')
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_fixed_pool = qualified.index.tolist()
        g.filtered_fixed_pool = filter_delisting_lofs(new_fixed_pool, context, '固定池')
        log.info(f"【固定池过滤】保留高流动性ETF({len(g.filtered_fixed_pool)}只)")
    except Exception as e:
        log.warning(f"【固定池过滤】异常: {e}")
        g.filtered_fixed_pool = filter_delisting_lofs(g.fixed_etf_pool[:], context, '固定池')


def daily_merge_etf_pools(context):
    if not hasattr(g, 'filtered_fixed_pool'):
        g.filtered_fixed_pool = filter_delisting_lofs(g.fixed_etf_pool[:], context, '固定池')
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    merged = filter_delisting_lofs(merged, context, '合并池')
    log.info(f"【合并池】固定池{len(g.filtered_fixed_pool)}只 + 动态池{len(g.dynamic_etf_pool)}只 "
             f"→ {len(merged)}只")
    g.merged_etf_pool = merged
    
RANK_LOG_TOP_N = 30
LOG_SEGMENT_LINES = 30


def log_in_segments(lines, max_lines=LOG_SEGMENT_LINES):
    for i in range(0, len(lines), max_lines):
        log.info("\n".join(lines[i:i + max_lines]))


def calculate_and_log_ranked_etfs(context):
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.warning("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        return
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list


def calculate_momentum_score(price_series, lookback_days):
    if len(price_series) < lookback_days + 1:
        return None, None, None
    recent_price_series = price_series[-(lookback_days + 1):]
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    W = weights ** 2
    W_sum = np.sum(W)
    x_bar = np.sum(W * x) / W_sum
    y_bar = np.sum(W * y) / W_sum
    dx = x - x_bar
    dy = y - y_bar
    variance_x = np.sum(W * dx**2)
    if variance_x == 0:
        return 0, 0, 0
    slope = np.sum(W * dx * dy) / variance_x
    intercept = y_bar - slope * x_bar
    annualized_returns = math.exp(slope * 250) - 1
    y_pred = slope * x + intercept
    ss_res = np.sum(weights * (y - y_pred) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0
    momentum_score = annualized_returns * r_squared
    return momentum_score, annualized_returns, r_squared


def get_series_ending_at(hist_closes, current_price, offset):
    hist = np.asarray(hist_closes, dtype=float)
    if offset == 0:
        return np.append(hist, float(current_price))
    cut = offset - 1
    if cut == 0:
        return hist
    if len(hist) <= cut:
        return None
    return hist[:-cut]


def get_historical_volume_ratio(hist_volumes, offset, lookback_days):
    try:
        vols = np.asarray(hist_volumes, dtype=float)
        idx = len(vols) - offset
        if idx <= 0 or idx >= len(vols):
            return None
        start = idx - lookback_days
        if start < 0:
            return None
        base = vols[start:idx]
        if len(base) < lookback_days or np.any(base <= 0) or np.any(np.isnan(base)):
            return None
        avg = np.mean(base)
        return vols[idx] / avg if avg > 0 else None
    except Exception:
        return None


def evaluate_super_mainline(hist_closes, hist_volumes, current_price, current_volume_ratio):
    if not getattr(g, 'enable_super_mainline', False):
        return False, {'reason': 'disabled'}
    days = int(getattr(g, 'mainline_days', 5))
    if hist_closes is None or hist_volumes is None:
        return False, {'reason': 'no_hist'}

    scores = []
    r2_values = []
    volume_ratios = []
    laplace_slopes = []

    for offset in range(days - 1, -1, -1):
        series = get_series_ending_at(hist_closes, current_price, offset)
        if series is None or len(series) < int(g.lookback_days * 0.8):
            return False, {'reason': f'series_short@offset{offset}'}
        score, _, r2 = calculate_momentum_score(series, g.lookback_days)
        if score is None or r2 is None or pd.isna(score) or pd.isna(r2):
            return False, {'reason': f'score_nan@offset{offset}'}
        scores.append(score)
        r2_values.append(r2)

        try:
            lap_values = laplace_filter(series, s=g.laplace_s_param)
            lap_slope = lap_values[-1] - lap_values[-2] if len(lap_values) >= 2 else 0
        except Exception:
            lap_slope = 0
        laplace_slopes.append(lap_slope)

        if offset == 0:
            volume_ratios.append(current_volume_ratio)
        else:
            volume_ratios.append(get_historical_volume_ratio(hist_volumes, offset, g.volume_lookback))

    valid_vrs = [v for v in volume_ratios if v is not None and not pd.isna(v)]
    if len(valid_vrs) < 3:
        return False, {'reason': 'volume_none'}
    if len(valid_vrs) < len(volume_ratios):
        fallback_v = float(np.mean(valid_vrs))
        volume_ratios = [fallback_v if (v is None or pd.isna(v)) else float(v) for v in volume_ratios]

    current_score = scores[-1]
    current_r2 = r2_values[-1]
    r2_avg = float(np.mean(r2_values))
    volume_avg = float(np.mean(volume_ratios))
    score_up_days = sum(1 for i in range(1, len(scores)) if scores[i] >= scores[i - 1])
    positive_laplace_days = sum(1 for v in laplace_slopes if v > 0)
    start_score = scores[0]
    score_growth = current_score / start_score if start_score > 0 else (float('inf') if current_score > 0 else 0)

    fails = []
    if not (g.mainline_score_min < current_score <= g.mainline_score_max):
        fails.append('score_range')
    if current_r2 < g.mainline_min_r2:
        fails.append('r2_cur')
    if r2_avg < g.mainline_min_r2_avg:
        fails.append('r2_avg')
    if volume_avg < g.mainline_min_volume_avg:
        fails.append('vol_avg')
    if score_up_days < g.mainline_min_score_up_days:
        fails.append('score_up')
    if positive_laplace_days < g.mainline_min_positive_laplace_days:
        fails.append('lap_pos')
    if score_growth < g.mainline_min_score_growth:
        fails.append('score_growth')
    passed = not fails
    return passed, {
        'scores': scores, 'r2_values': r2_values, 'volume_ratios': volume_ratios,
        'laplace_slopes': laplace_slopes, 'current_score': current_score,
        'current_r2': current_r2, 'r2_avg': r2_avg, 'volume_avg': volume_avg,
        'score_up_days': score_up_days, 'positive_laplace_days': positive_laplace_days,
        'score_growth': score_growth, 'reason': 'pass' if passed else '+'.join(fails),
    }


def calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    try:
        price_series = np.append(hist_closes, current_price)

        # 【优化】按ETF自己的基准决定动量窗口
        bench = g.etf_benchmark_cache.get(etf)
        if bench is None:
            bench = classify_benchmark(etf, etf_name)
            g.etf_benchmark_cache[etf] = bench
        is_bench_weak = bool(getattr(g, 'benchmark_weak', {}).get(bench, False))

        mom_lb = g.lookback_days
        if is_bench_weak and getattr(g, "enable_dynamic_weak_lookback", False):
            mom_lb = g.weak_momentum_lookback

        if len(price_series) < mom_lb * 0.8:
            return None
        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_series, mom_lb)
        if momentum_score is None:
            return None
        passed_momentum = (g.min_score_threshold <= momentum_score <= g.max_score_threshold)
        volume_ratio = get_volume_ratio(hist_volumes, today_vol, context, g.volume_lookback)

        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False

        passed_r2 = r_squared > g.r2_threshold

        passed_ma = True
        ma_value = None
        if len(price_series) >= g.ma_lookback:
            ma_value = np.mean(price_series[-g.ma_lookback:])
            passed_ma = current_price > ma_value * g.ma_threshold
        else:
            passed_ma = False

        premium_rate, passed_premium = calculate_premium_rate(etf, context)

        laplace_value = 0
        laplace_slope = 0
        passed_laplace = False
        if len(price_series) >= 10:
            try:
                laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
                if len(laplace_values) >= 2:
                    laplace_value = laplace_values[-1]
                    laplace_slope = laplace_values[-1] - laplace_values[-2]
                    passed_laplace = (current_price > laplace_values[-1] and
                                      laplace_slope > g.laplace_min_slope)
            except Exception:
                pass

        passed_mainline, mainline_info = evaluate_super_mainline(
            hist_closes, hist_volumes, current_price, volume_ratio)

        passed_volume_divergence, vd_info = check_volume_price_divergence(
            hist_closes, hist_volumes, context)

        return {
            'etf': etf, 'etf_name': etf_name,
            'benchmark': bench, 'benchmark_weak': is_bench_weak,
            'momentum_score': momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'premium_rate': premium_rate,
            'passed_momentum': passed_momentum,
            'passed_r2': passed_r2,
            'passed_ma': passed_ma,
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter,
            'passed_premium': passed_premium,
            'ma_value': ma_value,
            'laplace_value': laplace_value,
            'laplace_slope': laplace_slope,
            'passed_laplace': passed_laplace,
            'passed_mainline': passed_mainline,
            'mainline_info': mainline_info,
            'passed_volume_divergence': passed_volume_divergence,
            'vd_info': vd_info,
        }
    except Exception as e:
        log.debug(f"【指标计算】{etf} {etf_name} 计算失败: {e}")
        return None


def get_volume_ratio(hist_volumes, today_vol, context, lookback_days=None):
    if lookback_days is None:
        lookback_days = g.volume_lookback
    try:
        if hist_volumes is None or len(hist_volumes) < lookback_days:
            return None
        past_n_days_vol = hist_volumes[-lookback_days:]
        if np.any(np.isnan(past_n_days_vol)) or np.any(past_n_days_vol == 0):
            return None
        avg_volume = np.mean(past_n_days_vol)
        if avg_volume == 0:
            return None
        now = context.current_dt
        elapsed_minutes = (now.hour - 9) * 60 + now.minute - 30
        if now.hour >= 13:
            elapsed_minutes -= 90
        elapsed_minutes = max(1, min(elapsed_minutes, 240))
        projected_today_vol = today_vol * (240.0 / elapsed_minutes)
        return projected_today_vol / avg_volume if avg_volume > 0 else 0
    except Exception:
        return None


def calculate_premium_rate(etf, context):
    try:
        etf_price = getattr(g, 'etf_yesterday_close_batch', {}).get(etf)
        if etf_price is None or pd.isna(etf_price):
            etf_price_df = get_price(etf, start_date=context.previous_date,
                                     end_date=context.previous_date, fields=['close'])
            if etf_price_df is None or len(etf_price_df) == 0:
                return None, False
            etf_price = etf_price_df['close'].iloc[-1]
        nav = getattr(g, 'etf_yesterday_nav_batch', {}).get(etf)
        if nav is None or pd.isna(nav):
            nav_df = get_extras('unit_net_value', etf,
                                start_date=context.previous_date,
                                end_date=context.previous_date)
            if nav_df is None or len(nav_df) == 0:
                return None, False
            nav = nav_df.iloc[-1].values[0]
        if nav <= 0 or pd.isna(nav):
            return None, False
        premium_rate = (etf_price - nav) / nav * 100
        passed_premium = premium_rate <= g.max_premium_rate
        return premium_rate, passed_premium
    except Exception:
        return None, True


def laplace_filter(price, s=0.05):
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


# =====================================================================
# Regime P0
# =====================================================================
def _compute_hs300_breadth(context):
    try:
        stocks = get_index_stocks('000300.XSHG', date=context.previous_date)
        if not stocks:
            return None
        stocks = list(stocks)
        w = int(getattr(g, 'regime_breadth_ma', 20))
        df = get_price(stocks, end_date=context.previous_date, count=w,
                       frequency='daily', fields=['close'], panel=False, skip_paused=True)
        if df is None or len(df) == 0:
            return None
        cur = get_current_data()
        above = 0
        total = 0
        for code in stocks:
            sub = df[df['code'] == code] if 'code' in df.columns else df[df.index == code]
            if sub is None or len(sub) < w:
                continue
            closes = sub['close'].values if 'close' in sub.columns else sub.values
            if len(closes) < w:
                continue
            ma = float(np.mean(closes[-w:]))
            px = cur[code].last_price if code in cur else float(closes[-1])
            if px is None or pd.isna(px) or ma <= 0:
                continue
            total += 1
            if px > ma:
                above += 1
        if total < 50:
            return None
        return float(above) / float(total)
    except Exception as e:
        log.debug(f"[RegimeP0] breadth error: {e}")
        return None


def _compute_market_liquidity_yi(context):
    try:
        lb = int(getattr(g, 'regime_liquidity_lookback', 20))
        idx = ['000001.XSHG', '399001.XSHE']
        df = get_price(idx, end_date=context.previous_date, count=lb,
                       frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or len(df) == 0:
            return None
        if 'time' in df.columns:
            daily = df.groupby('time')['money'].sum()
        else:
            daily = df['money']
        if len(daily) == 0:
            return None
        return float(daily.mean()) / 1e8
    except Exception as e:
        log.debug(f"[RegimeP0] liquidity error: {e}")
        return None


def _compute_trend_votes(context):
    indexes = {'大盘': '000300.XSHG', '小盘': '399101.XSHE',
               '创业板': '399006.XSHE', '中证A500': '000510.XSHG'}
    above_count = 0
    below_count = 0
    for name, code in indexes.items():
        df = attribute_history(code, g.weak_period_ma_lookback + 1, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < g.weak_period_ma_lookback:
            continue
        current_price = df['close'][-1]
        ma_val = df['close'][-g.weak_period_ma_lookback:].mean()
        if current_price > ma_val:
            above_count += 1
        elif current_price < ma_val:
            below_count += 1
    return above_count, below_count


def _classify_regime_p0(above_count, below_count, breadth, liquidity_yi):
    liq_min = float(getattr(g, 'regime_liquidity_min_yi', 20000.0))
    b_high = float(getattr(g, 'regime_breadth_high', 0.55))
    b_struct = float(getattr(g, 'regime_breadth_structural', 0.50))
    b_low = float(getattr(g, 'regime_breadth_low', 0.35))

    liquidity_ok = liquidity_yi is not None and liquidity_yi >= liq_min
    trend_ok = above_count >= 2
    trend_weak = below_count >= 3

    if breadth is not None and breadth < b_low:
        return 'DEFENSIVE', 2
    if not liquidity_ok:
        return 'DEFENSIVE', 2
    if trend_ok or (breadth is not None and breadth >= b_high):
        return 'NORMAL', 0
    if trend_weak and breadth is not None and breadth >= b_struct:
        return 'STRUCTURAL', 1
    if trend_weak and breadth is not None and breadth < b_low:
        return 'DEFENSIVE', 2
    return 'NORMAL', 0


def compute_regime_p0_daily(context):
    if g.mode == 'bottom':
        return
    if not getattr(g, 'enable_regime_p0', False):
        return
    above_count, below_count = _compute_trend_votes(context)
    breadth = _compute_hs300_breadth(context)
    liquidity_yi = _compute_market_liquidity_yi(context)
    regime_name, regime_code = _classify_regime_p0(above_count, below_count, breadth, liquidity_yi)
    legacy_weak = bool(getattr(g, 'is_a_share_weak', False))
    mismatch = legacy_weak and regime_name in ('NORMAL', 'STRUCTURAL')

    entry = {
        'date': context.current_dt.strftime('%Y-%m-%d'),
        'regime': regime_name,
        'regime_code': regime_code,
        'breadth': None if breadth is None else round(breadth, 4),
        'liquidity_yi': None if liquidity_yi is None else round(liquidity_yi, 1),
        'trend_above': above_count,
        'trend_below': below_count,
        'legacy_weak': int(legacy_weak),
        'legacy_mismatch': int(mismatch),
    }
    g.regime_p0_log.append(entry)
    log.info(f"[REGIME_P0] {json.dumps(entry, ensure_ascii=False)}")
    log.info(f"📊 【RegimeP0】{regime_name} | 宽度={entry['breadth']} 流动性={entry['liquidity_yi']}亿 "
             f"| 趋势 上/下={above_count}/{below_count} | 原走弱期={legacy_weak} "
             f"| 错配={'是' if mismatch else '否'}")
    record(regime_p0=regime_code,
           breadth_p0=0.0 if breadth is None else float(breadth),
           liquidity_p0=0.0 if liquidity_yi is None else float(liquidity_yi),
           trend_below_p0=float(below_count),
           legacy_weak_p0=1.0 if legacy_weak else 0.0,
           regime_mismatch_p0=1.0 if mismatch else 0.0)


# =====================================================================
# 走弱期判断
# =====================================================================
def check_a_share_weak_period(context):
    """保留原A股4指数投票逻辑（用于兼容旧字段），
    同时刷新所有基准的走弱状态。"""
    today = context.current_dt.date()
    indexes = {
        '大盘': '000300.XSHG',
        '小盘': '399101.XSHE',
        '创业板': '399006.XSHE',
        '中证A500': '000510.XSHG'
    }
    above_count = 0
    below_count = 0
    for name, code in indexes.items():
        df = attribute_history(code, g.weak_period_ma_lookback + 1, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < g.weak_period_ma_lookback:
            log.warning(f"📊 【走弱期判断】{name}({code})数据不足，跳过")
            continue
        current_price = df['close'][-1]
        ma_val = df['close'][-g.weak_period_ma_lookback:].mean()
        is_above = current_price > ma_val
        is_below = current_price < ma_val
        if is_above:
            above_count += 1
        if is_below:
            below_count += 1
        status_emoji = "⬆️站上" if is_above else ("⬇️低于" if is_below else "➡️持平")
        log.info(f"📊 【走弱期判断】{name}({code}): 收盘{current_price:.2f} / "
                 f"MA{g.weak_period_ma_lookback} {ma_val:.2f} → {status_emoji}")

    weak_condition_met = (below_count >= 3)
    exit_condition_met = (above_count >= 3)
    log.info(f"📊 【走弱期判断】低于MA: {below_count}/4, 站上MA: {above_count}/4")

    if g.is_a_share_weak and g.weak_start_date is not None:
        g.weak_days_count = len(get_trade_days(start_date=g.weak_start_date, end_date=today))
    else:
        g.weak_days_count = 0
    max_days_exceeded = (g.weak_days_count >= g.max_weak_days)

    if g.is_a_share_weak:
        if max_days_exceeded:
            log.info(f"🔔 【走弱期退出】已达最大持续天数{g.max_weak_days}，强制退出")
            g.is_a_share_weak = False
            g.weak_start_date = None
            g.weak_days_count = 0
        elif exit_condition_met:
            log.info(f"🟢 【走弱期退出】满足退出条件")
            g.is_a_share_weak = False
            g.weak_start_date = None
            g.weak_days_count = 0
        elif weak_condition_met:
            g.weak_start_date = today
            g.weak_days_count = 0
            log.info(f"🟡 【走弱期延续】重置计数器")
        else:
            log.info(f"🔴 【走弱期中】{g.weak_days_count}/{g.max_weak_days}")
    else:
        if weak_condition_met:
            log.info(f"🔴 【走弱期进入】")
            g.is_a_share_weak = True
            g.weak_start_date = today
            g.weak_days_count = 0
        else:
            log.info(f"🟢 【正常期中】")

    status_emoji = "🔴" if g.is_a_share_weak else "🟢"
    log.info(f"📊 【走弱期判断】{status_emoji} 最终状态: 走弱期={g.is_a_share_weak}")
    record(走弱期状态=1 if g.is_a_share_weak else 0)

    # 【优化】刷新所有基准的走弱状态
    update_benchmark_weak_states(context)

    if getattr(g, "enable_dynamic_weak_lookback", False):
        adjust_weak_momentum_lookback(context)
    return g.is_a_share_weak


# =====================================================================
# 【优化】apply_filters：按每只ETF自己的基准决定过滤流程
# =====================================================================
def apply_filters(metrics_list):
    """每只ETF按自己的参照基准决定走强市还是弱市过滤流程。
    - 自己基准弱 → 只留动量 + R²
    - 自己基准正常 → 全套严格过滤
    """
    result = []
    bench_weak_stats = {}
    bench_normal_stats = {}

    for m in metrics_list:
        etf = m['etf']
        name = m.get('etf_name', '')
        bench = m.get('benchmark') or g.etf_benchmark_cache.get(etf)
        if bench is None:
            bench = classify_benchmark(etf, name)
            g.etf_benchmark_cache[etf] = bench
        is_weak = bool(getattr(g, 'benchmark_weak', {}).get(bench, False))
        m['benchmark'] = bench
        m['benchmark_weak'] = is_weak

        if is_weak:
            bench_weak_stats[bench] = bench_weak_stats.get(bench, 0) + 1
            checks = [
                ('动量得分', m['passed_momentum'], True),
                ('R²', m['passed_r2'], g.enable_r2_filter),
            ]
        else:
            bench_normal_stats[bench] = bench_normal_stats.get(bench, 0) + 1
            checks = [
                ('动量得分', m['passed_momentum'], True),
                ('R²', m['passed_r2'], g.enable_r2_filter),
                ('均线', m['passed_ma'], g.enable_ma_filter),
                ('成交量', m['passed_volume'], g.enable_volume_check),
                ('短期风控', m['passed_loss'], g.enable_loss_filter),
                ('溢价率', m['passed_premium'], g.enable_premium_filter),
                ('拉普拉斯滤波', m['passed_laplace'], g.enable_laplace_filter),
                ('量价背离', m.get('passed_volume_divergence', True),
                 g.enable_volume_divergence_filter and g.is_choppy),
            ]
        passed = True
        for _, cond, enabled in checks:
            if enabled and not cond:
                passed = False
                break
        if passed:
            result.append(m)

    if bench_weak_stats or bench_normal_stats:
        parts = []
        for b, cnt in sorted(bench_weak_stats.items(), key=lambda x: -x[1])[:6]:
            parts.append(f"{b}=弱({cnt}只)")
        for b, cnt in sorted(bench_normal_stats.items(), key=lambda x: -x[1])[:6]:
            parts.append(f"{b}=正({cnt}只)")
        log.info(f"📊 【分基准过滤】{' | '.join(parts)}")
    return result

def get_final_ranked_etfs(context):
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = context.previous_date
    log.info(f"【动量得分计算】使用合并池，合计{len(etf_set)}只ETF")
    log.info(f"【当前状态】A股走弱={'🔴' if g.is_a_share_weak else '🟢'} | "
             f"按每只ETF自己的基准过滤")

    mom_lb = g.weak_momentum_lookback if (
        g.is_a_share_weak and getattr(g, "enable_dynamic_weak_lookback", False)
    ) else g.lookback_days
    lookback = max(mom_lb, g.volume_lookback, g.ma_lookback) + 20
    today = context.current_dt.date()
    current_data = get_current_data()
    safe_lookback = lookback + 20

    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d',
                        fields=['close', 'volume', 'paused'], panel=False, skip_paused=False)
    if hist_df is not None and (not hist_df.empty) and 'paused' in hist_df.columns:
        paused_flag = pd.to_numeric(hist_df['paused'], errors='coerce').fillna(0)
        hist_df = hist_df.loc[paused_flag < 1]

    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt,
                             frequency='1m', fields=['volume'], panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        log.warning("【动量计算】无法获取历史价格数据")
        return []

    g.etf_yesterday_close_batch = {}
    g.etf_yesterday_nav_batch = {}
    try:
        y_price_df = get_price(etf_set, start_date=end_date, end_date=end_date,
                               fields=['close'], panel=False)
        if y_price_df is not None and not y_price_df.empty:
            g.etf_yesterday_close_batch = y_price_df.groupby('code')['close'].last().to_dict()
            if getattr(g, 'cache_date', None) == context.current_dt.date():
                ycache = getattr(g, 'yesterday_close_cache', None) or {}
                for k, v in g.etf_yesterday_close_batch.items():
                    if pd.notna(v) and float(v) > 0:
                        ycache[str(k)] = float(v)
                g.yesterday_close_cache = ycache
        nav_df = get_extras('unit_net_value', etf_set, start_date=end_date, end_date=end_date)
        if nav_df is not None and not nav_df.empty:
            g.etf_yesterday_nav_batch = nav_df.iloc[-1].to_dict()
    except Exception as e:
        log.warning(f"【动量计算】批量获取溢价率数据异常: {e}")

    today_vols = today_vol_df.groupby('code')['volume'].sum() if (
        today_vol_df is not None and not today_vol_df.empty) else pd.Series(dtype=float)
    close_pivot = hist_df.pivot(index='time', columns='code', values='close')
    volume_pivot = hist_df.pivot(index='time', columns='code', values='volume')

    for etf in etf_set:
        if current_data[etf].paused:
            continue
        if etf not in close_pivot.columns:
            continue
        raw_closes = close_pivot[etf].values
        raw_volumes = volume_pivot[etf].values
        valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)
        hist_closes = raw_closes[valid_mask]
        hist_volumes = raw_volumes[valid_mask]
        hist_closes = hist_closes[-lookback:]
        hist_volumes = hist_volumes[-lookback:]
        if len(hist_closes) < g.lookback_days:
            continue
        etf_name = get_security_name(etf)
        current_price = current_data[etf].last_price
        today_vol = today_vols.get(etf, 0)
        metrics = calculate_all_metrics_for_etf(
            etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                continue
            all_metrics.append(metrics)

    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
    all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)

    log_buffer = []
    log_buffer.append("")
    log_buffer.append(">>> 第一步：所有ETF按动量得分从大到小排序 <<<")
    for m in all_metrics[:RANK_LOG_TOP_N]:
        def fmt_status(value_str, passed):
            return f"{value_str} {'✅' if passed else '❌'}"
        score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
        r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
        vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
        min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
        loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
        premium_str = f"{m['premium_rate']:.2f}%" if m['premium_rate'] is not None else "N/A"
        ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
        line = (
            f"{m['etf']} {m['etf_name']}: "
            f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
            f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
            f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
            f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
            f"短期风控: {fmt_status(loss_val, m['passed_loss'])}，"
            f"溢价率: {fmt_status(premium_str, m['passed_premium'])}，"
            f"拉普拉斯斜率: {m['laplace_slope']:.4f} {fmt_status('', m['passed_laplace'])}，"
            f"B型主线: {'✅' if m.get('passed_mainline') else '❌'}，"
            f"基准: {m.get('benchmark','?')}{'(弱)' if m.get('benchmark_weak') else '(正)'}"
        )
        log_buffer.append(line)

    filtered_list = apply_filters(all_metrics)

    # B型主线补充
    if getattr(g, 'enable_super_mainline', False):
        normal_codes = {m['etf'] for m in filtered_list}
        mainline_list = [
            m for m in all_metrics
            if m.get('passed_mainline')
            and m['etf'] not in normal_codes
            and (not g.enable_loss_filter or m['passed_loss'])
            and (not g.enable_premium_filter or m['passed_premium'])
            and (not (g.enable_ma_filter and m.get('benchmark_weak')) or m['passed_ma'])
        ]
        filtered_list = filtered_list + mainline_list
        log_buffer.append("")
        log_buffer.append(f">>> B型阶梯主线：满足条件的ETF {len(mainline_list)}只 <<<")

        # B型主线持仓延续
        if getattr(g, 'enable_mainline_retain', True):
            held_codes_set = {sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0}
            already_codes = {m['etf'] for m in filtered_list}
            retain_list = []
            for m in all_metrics:
                if m['etf'] not in held_codes_set:
                    continue
                if m['etf'] in already_codes:
                    continue
                score_val = m.get('momentum_score', 0)
                if score_val is None or pd.isna(score_val):
                    continue
                if score_val <= g.mainline_score_max:
                    continue
                r2_val = m.get('r_squared')
                lap_slope = m.get('laplace_slope', 0)
                if r2_val is None or pd.isna(r2_val) or r2_val < g.mainline_retain_min_r2:
                    continue
                if lap_slope is None or pd.isna(lap_slope) or lap_slope <= g.mainline_retain_min_lap_slope:
                    continue
                if g.enable_loss_filter and not m['passed_loss']:
                    continue
                if g.enable_premium_filter and not m['passed_premium']:
                    continue
                if g.enable_ma_filter and m.get('benchmark_weak') and not m['passed_ma']:
                    continue
                retain_list.append(m)
            if retain_list:
                for m in retain_list:
                    m['mainline_retained'] = True
                filtered_list = filtered_list + retain_list
                log_buffer.append(f">>> B型主线持仓延续：{len(retain_list)}只 <<<")

    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    top_10 = filtered_list[:10]

    log_buffer.append("")
    log_buffer.append(">>> 第二步：符合全部过滤条件的ETF(前10名) <<<")
    for m in top_10:
        log_buffer.append(
            f"{m['etf']} {m['etf_name']}: score={m['momentum_score']:.4f}, "
            f"基准={m.get('benchmark','?')}{'(弱)' if m.get('benchmark_weak') else '(正)'}"
        )

    if not top_10:
        log_buffer.append("（无符合条件的ETF）")
        log_in_segments(log_buffer)
        return []

    score_key = 'momentum_score'
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        ratio = g.score_threshold_ratio if not g.is_a_share_weak else 1.0
        score_threshold = reference_score * ratio
        candidate_pool = [item for item in top_10
                           if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        candidate_pool = top_10[:]

    log_buffer.append(f"【候选池】共{len(candidate_pool)}只ETF")

    current_holdings = [sec for sec, pos in context.portfolio.positions.items()
                        if pos.total_amount > 0]
    candidate_dict = {item['etf']: item for item in candidate_pool}
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]

    if len(retained) >= g.holdings_num:
        retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
    else:
        need = g.holdings_num - len(retained)
        remaining_pool = [item for item in candidate_pool
                          if item['etf'] not in {r['etf'] for r in retained}]
        additional = apply_correlation_guard_metrics(
            context, remaining_pool, retained, need, SID_S2)
        final_result = retained + additional

    log_buffer.append(f"【最终目标】共{len(final_result)}只ETF：")
    for i, item in enumerate(final_result):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) "
                          f"基准={item.get('benchmark','?')}")
    log_buffer.append("==================================================")
    log_in_segments(log_buffer)
    return final_result

def execute_sell_trades(context):
    if g.mode == 'bottom':
        return
    log.info("========== 卖出操作开始 ==========")
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    target_etfs = []

    if ranked_etfs:
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
            log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}")
    else:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
            etf_name = get_security_name(g.defensive_etf)
            log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
        else:
            target_etfs = []

    g.target_etfs_list = target_etfs
    current_positions = list(g.accounts[SID_S2]['holdings'])
    target_set = set(target_etfs)
    sell_count = 0

    for security in current_positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            success = smart_order_target_value(security, 0, context)
            if success:
                sell_count += 1
                log.info(f"✅ 已成功卖出: {security} {security_name}")

    log.info(f"本次共计划卖出{sell_count}只ETF。")
    log.info("========== 卖出操作完成 ==========")


def execute_buy_trades(context):
    if g.mode == 'bottom':
        return
    log.info("========== 买入操作开始（择时趋势判断）==========")
    g.pending_buy_etfs = []
    target_etfs = g.target_etfs_list

    if not target_etfs:
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        return

    current_positions = set(g.accounts[SID_S2]['holdings'])
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)

    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})")
        return

    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    log.info(f"当前实际持仓: {actual_holding_count}只, 目标: {g.holdings_num}只, "
             f"本次计划买入: {num_etfs_to_buy}只")

    g.pending_buy_etfs = list(etfs_to_buy)
    log.info(f"计划买入ETF: {g.pending_buy_etfs}，先执行首次趋势判断；"
             f"若不满足，将在{'/'.join(S2_CHECK_TIMES)}复检，{S2_FORCE_TIME}强制买入")
    execute_buy_with_trend(context, force=False)

    if g.pending_buy_etfs:
        log.info(f"⏳ 等待趋势确认的ETF: {g.pending_buy_etfs}")


def check_intraday_trend(security, context):
    try:
        minute_data = get_price(security, end_date=context.current_dt,
                                count=g.trend_lookback_minutes, frequency='1m',
                                fields=['close'], skip_paused=False, fq='pre')
        if minute_data is None or minute_data.empty:
            return True
        closes = minute_data['close'].values
        closes = closes[closes > 0]
        if len(closes) < 5:
            return False
        n = len(closes)
        x = np.arange(n)
        weights = np.linspace(0.5, 2.0, n)
        w = weights / weights.sum()
        x_bar = np.sum(w * x)
        y_bar = np.sum(w * closes)
        dx = x - x_bar
        dy = closes - y_bar
        variance_x = np.sum(w * dx**2)
        slope = np.sum(w * dx * dy) / variance_x if variance_x != 0 else 0
        mean_price = y_bar if y_bar > 0 else closes.mean()
        slope_pct = slope / mean_price * 100 if mean_price > 0 else 0
        y_pred = slope * x + (y_bar - slope * x_bar)
        ss_res = np.sum(w * (closes - y_pred)**2)
        ss_tot = np.sum(w * (closes - y_bar)**2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        passed_slope = slope_pct > g.trend_slope_threshold
        passed_r2 = r2 > g.trend_r2_threshold
        is_uptrend = passed_slope and passed_r2
        log.info(f"【趋势判断】{security} 最近{n}分钟 | "
                 f"斜率={slope_pct:.6f}%/min{'✓' if passed_slope else '✗'} | "
                 f"R²={r2:.3f}{'✓' if passed_r2 else '✗'} | "
                 f"判定: {'上涨' if is_uptrend else '未确认'}")
        return is_uptrend
    except Exception as e:
        log.info(f"【趋势判断】{security} 异常: {e}，默认上涨")
        return True


def execute_buy_with_trend(context, force=False):
    if g.mode == 'bottom':
        return
    if not g.pending_buy_etfs:
        return
    current_positions = set(g.accounts[SID_S2]['holdings'])
    g.pending_buy_etfs = [etf for etf in g.pending_buy_etfs if etf not in current_positions]
    if not g.pending_buy_etfs:
        return

    current_time = context.current_dt.strftime('%H:%M')
    mode_desc = "强制买入" if force else "趋势判断"
    log.info(f"========== 买入操作开始（{mode_desc} {current_time}）==========")

    etfs_to_buy_now = []
    still_pending = []
    for etf in g.pending_buy_etfs:
        etf_name = get_security_name(etf)
        if force:
            etfs_to_buy_now.append(etf)
            log.info(f"⏰ {current_time} 强制买入 {etf} {etf_name}")
        else:
            if check_intraday_trend(etf, context):
                etfs_to_buy_now.append(etf)
                log.info(f"📈 {current_time} {etf} {etf_name} 趋势上涨，立即买入")
            else:
                still_pending.append(etf)
                log.info(f"📉 {current_time} {etf} {etf_name} 趋势未确认")

    total_count = len(etfs_to_buy_now) + len(still_pending)
    if getattr(g, 's2_enable_position_mgmt', False):
        g.target_position_values = compute_s2_target_values(context, g.target_etfs_list)

    for i, etf in enumerate(etfs_to_buy_now):
        remaining_cash = context.portfolio.available_cash
        if remaining_cash < g.min_money:
            log.info(f"可用现金 {remaining_cash:.2f} 不足最小交易额")
            break
        remaining_to_buy = total_count - i
        target_value_for_this_etf = remaining_cash // remaining_to_buy
        if target_value_for_this_etf < g.min_money and remaining_cash >= g.min_money:
            target_value_for_this_etf = remaining_cash
        if getattr(g, 's2_enable_position_mgmt', False):
            target_value_for_this_etf = g.target_position_values.get(
                etf, target_value_for_this_etf)

        etf_name = get_security_name(etf)
        log.info(f"为 {etf} {etf_name} 分配目标金额: {target_value_for_this_etf:.2f} 元")
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
        else:
            log.info(f"❌ ETF {etf} 下单失败")

    g.pending_buy_etfs = still_pending
    if still_pending:
        log.info(f"⏳ 仍待趋势确认的ETF: {still_pending}")
    else:
        log.info("✅ 所有待买ETF已处理完毕")


def check_pending_buys_trend(context):
    if g.mode == 'bottom':
        return
    if not g.pending_buy_etfs:
        return
    log.info("★" * 80)
    log.info("▶️ 【趋势复检】")
    execute_buy_with_trend(context, force=False)
    if g.pending_buy_etfs:
        log.info(f"⏳ 仍在等待的ETF: {g.pending_buy_etfs}")


def force_buy_pending(context):
    if g.mode == 'bottom':
        return
    if not g.pending_buy_etfs:
        return
    log.info("★" * 80)
    log.info("▶️ 【强制买入】")
    execute_buy_with_trend(context, force=True)


def smart_order_target_value(security, target_value, context):
    current_data = get_current_data()
    security_name = get_security_name(security)

    if target_value > 0:
        available_cash = context.portfolio.available_cash
        if target_value > available_cash:
            target_value = available_cash
        if target_value < g.min_money:
            log.info(f"{security} {security_name}: 目标金额{target_value:.2f}小于最小交易额，跳过")
            return False

    if current_data[security].paused:
        log.info(f"{security} {security_name}: 今日停牌，跳过")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} {security_name}: 涨停，跳过")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} {security_name}: 跌停，跳过")
        return False

    current_price = current_data[security].last_price
    if current_price == 0:
        return False

    buy_commission_rate = 0.0001
    slippage_rate = 0.0001
    estimated_price = current_price * (1 + buy_commission_rate + slippage_rate)

    if target_value > 0:
        target_amount = int(target_value / estimated_price)
        target_amount = (target_amount // 100) * 100
        if target_amount <= 0 and target_value > 0:
            target_amount = 100
        max_shares = int(context.portfolio.available_cash / current_price)
        max_shares = (max_shares // 100) * 100
        if max_shares < target_amount:
            target_amount = max_shares
        if target_amount <= 0:
            return False
    else:
        target_amount = 0

    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price

    if 0 < trade_value < g.min_money:
        return False

    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} {security_name}: T+1不可卖")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)

    if amount_diff != 0:
        if amount_diff > 0:
            order_result = open_position(context, security, target_value, SID_S2)
        else:
            order_result = close_position(security)
        if order_result:
            if amount_diff > 0:
                log.info(f"📦 买入{security} {security_name}，数量: {amount_diff}，"
                         f"价格: {current_price:.3f}")
            else:
                log.info(f"📤 卖出{security} {security_name}，数量: {abs(amount_diff)}，"
                         f"价格: {current_price:.3f}")
            return True
        else:
            log.warning(f"下单失败: {security} {security_name}")
            return False
    return False


def minute_level_stop_loss(context):
    if g.mode == 'bottom':
        return
    if not g.use_fixed_stop_loss:
        return
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    current_data = get_current_data()
    for security in list(g.accounts[SID_S2]['holdings']):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        cost_price = position.avg_cost
        if cost_price <= 0:
            continue
        if current_price <= cost_price * g.fixedStopLossThreshold:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"🚨 【分钟级固定止损】{security} {security_name} 亏损: {loss_percent:.2f}%")
            smart_order_target_value(security, 0, context)


def _refresh_yesterday_close_cache(context):
    g.cache_date = context.current_dt.date()
    holdings = []
    try:
        holdings.extend(list(g.accounts.get(SID_S2, {}).get('holdings') or []))
    except Exception:
        pass
    try:
        for sec, pos in context.portfolio.positions.items():
            if pos is not None and pos.total_amount > 0:
                holdings.append(sec)
    except Exception:
        pass
    holdings = list(dict.fromkeys(holdings))
    cache = {}
    if holdings:
        try:
            df = get_price(holdings, start_date=context.previous_date,
                           end_date=context.previous_date, frequency='daily',
                           fields=['close'], panel=False, skip_paused=False)
            if df is not None and len(df) > 0 and 'code' in df.columns:
                raw = df.groupby('code')['close'].last().to_dict()
                cache = {str(k): float(v) for k, v in raw.items()
                         if pd.notna(v) and float(v) > 0}
        except Exception:
            cache = {}
    batch = getattr(g, 'etf_yesterday_close_batch', None) or {}
    for k, v in batch.items():
        if k not in cache and pd.notna(v) and float(v) > 0:
            cache[k] = float(v)
    g.yesterday_close_cache = cache


def minute_level_pct_stop_loss(context):
    if g.mode == 'bottom':
        return
    if not g.use_pct_stop_loss:
        return
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    current_data = get_current_data()
    current_date = context.current_dt.date()
    if getattr(g, 'cache_date', None) != current_date or not getattr(g, 'yesterday_close_cache', None):
        _refresh_yesterday_close_cache(context)
    for security in list(g.accounts[SID_S2]['holdings']):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        yesterday_close = getattr(g, 'yesterday_close_cache', {}).get(security)
        if yesterday_close is None:
            yesterday_close = (getattr(g, 'etf_yesterday_close_batch', None) or {}).get(security)
        if yesterday_close is None or yesterday_close <= 0:
            continue
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        stop_price = yesterday_close * g.pct_stop_loss_threshold
        if current_price <= stop_price:
            security_name = get_security_name(security)
            daily_loss = (current_price / yesterday_close - 1) * 100
            log.info(f"🚨 【分钟级跌幅止损】{security} {security_name} 跌幅: {daily_loss:.2f}%")
            smart_order_target_value(security, 0, context)


def get_security_name(security):
    try:
        if hasattr(g, 'etf_names_dict') and security in g.etf_names_dict:
            return g.etf_names_dict[security]
        return get_security_info(security).display_name
    except Exception:
        return "未知名称"


def check_defensive_etf_available(context):
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    if current_data[defensive_etf].paused:
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        return False
    return True


def trade(context):
    pass


# =====================================================================
# S1 交易入口
# =====================================================================
def _get_display_width(text):
    width = 0
    for c in str(text):
        width += 2 if ord(c) > 127 else 1
    return width


def _format_table(df):
    cols = df.columns.tolist()
    col_widths = {}
    for col in cols:
        max_w = _get_display_width(col)
        for val in df[col]:
            max_w = max(max_w, _get_display_width(val))
        col_widths[col] = max_w + 2
    numeric_cols = [c for c in cols if any(k in c for k in ['乖离率', '排名', '%', '规模', '成交额'])]
    header_cells, sep_cells = [], []
    for col in cols:
        w = col_widths[col]
        cell = str(col)
        pad = w - _get_display_width(cell)
        header_cells.append(cell + " " * pad)
        sep_cells.append("-" * w)
    header_line = "| " + " | ".join(header_cells) + " |"
    sep_line = "| " + " | ".join(sep_cells) + " |"
    data_lines = []
    for _, row in df.iterrows():
        row_cells = []
        for col in cols:
            w = col_widths[col]
            val = row[col]
            if col in numeric_cols:
                try:
                    cell = f"{float(val):.2f}"
                except Exception:
                    cell = str(val)
            else:
                cell = str(val)
            pad = w - _get_display_width(cell)
            row_cells.append((" " * pad + cell) if col in numeric_cols else (cell + " " * pad))
        data_lines.append("| " + " | ".join(row_cells) + " |")
    return "\n".join([header_line, sep_line] + data_lines)


_step_counter = [0]


def yy_step(msg):
    _step_counter[0] += 1


def yy_sub(msg):
    log.info(f"  {msg}")


# 关键词列表
MONEY_KEYWORDS = ['货币', '现金', '快线', '快钱', '理财金', '保证金', '财富宝', '日利', '添益']
BOND_KEYWORDS = ['国债', '信用债', '城投债', '短融', '可转债', '转债', '政金债', '国开债', '金融债', '公司债', '地方债']
STAR_BROAD_KEYWORDS = ['科创5', '科创1', '科创2', '科创综', '科创价格', '科创创业50', '双创50', '双创']
SMART_BETA_KEYWORDS = ['红利', '高股息', '价值', '成长', '低波', '质量']
REAL_INDUSTRY_KEYWORDS = [
    '银行', '证券', '保险', '券商', '地产', '房地产', '医药', '医疗', '消费', '白酒', '食品', '酒',
    '科技', '芯片', '半导体', '集成电路', '电子', '计算机', '软件', '信创', '通信', '传媒', 'tmt',
    '5g', '人工智能', 'ai', '云计算', '大数据', '物联网', '卫星', '电网', '金融',
    '新能源', '新能车', '电车', '光伏', '锂电', '电池', '汽车', '军工', '国防', '有色', '稀土', '稀有',
    '科创', '创新药', '中药', '疫苗', '信息安全', '数字经济', '影视', '新材料',
    '煤炭', '钢铁', '石油', '油气', '化工', '农业', '畜牧', '养殖', '粮食', '基建', '建筑', '能源', '资源', '船舶',
    '建材', '家电', '纺织', '旅游', '酒店', '游戏', '动漫', '机器人',
    '高端制造', '工业', '机械', '电力', '公用', '水务', '环保', '物流', '交运', '港口',
    '航运', '航空', '铁路', '公路', '教育', '养老', '健康',
]
CROSS_BORDER_KEYWORDS = [
    '纳斯达克', '纳指', '标普', '道琼斯', '恒指', '恒生', '港股', '中概',
    '德国', '日本', '东证', '日经', '越南', '印度', '海外', '全球',
    '美国', '亚太', '欧洲', '法国', '英国', '沙特', '巴西', '东南亚', '新兴亚洲',
    '香港', 'h股',
]
CROSS_BORDER_EXCLUDE = ['中国a', '中国a股']

ASSET_CLASS_KEYWORDS = {
    '股票-宽基': ['300', '500', '1000', '2000', '800', '50', '100', '180', '380', '创业板', '科创5', '科创1',
                '科创2', '科创综', '中证a', 'a50', '沪深', '上证', '深证', '深成', '全指', '综指', '龙头',
                'msci中国a', '超大盘', '民企', '专精特新', '战略新兴', '成渝', '长江'],
    '债券': ['债', '城投', '短融', '国债', '转债', '信用', '国开', '金融债', '企业债', '政金'],
    '商品': ['黄金', '金etf', '金基金', '上海金', '金9999', '中银黄金', '白银', '豆粕', '能源化工',
             '天然气', '商品', '原油', '有色期'],
    '股票-行业': ['银行', '证券', '保险', '券商', '地产', '房地产', '医药', '医疗', '消费', '白酒', '食品', '酒',
                '科技', '芯片', '半导体', '集成电路', '电子', '信息', '计算机', '软件', '信创', '通信', '传媒', 'tmt',
                '5g', '人工智能', 'ai', '云计算', '大数据', '物联网', '卫星', '电网', '金融',
                '新能源', '新能车', '电车', '光伏', '锂电', '电池', '汽车', '军工', '国防', '有色', '稀土', '稀有',
                '科创芯片', '科创ai', '科创生物', '科创半导', '科创材料', '科创新能', '科创机械', '科创信息',
                '创新药', '中药', '疫苗', '信息安全', '数字经济', '影视', '新材料',
                '煤炭', '钢铁', '石油', '油气', '化工', '农业', '畜牧', '养殖', '粮食', '基建', '建筑', '能源', '资源', '船舶',
                '建材', '家电', '纺织', '旅游', '酒店', '游戏', '动漫', '机器人', '央企', '国企', '碳中和',
                '高端制造', '工业', '机械', '电力', '公用', '水务', '环保', '物流', '交运', '港口',
                '航运', '航空', '铁路', '公路', '教育', '养老', '健康'],
    '跨境': ['纳斯达克', '纳指', '标普', '道琼斯', '恒指', '恒生', '港股', '中概', '德国', '日本', '东证', '日经',
             '越南', '印度', '海外', '全球', '美国', '亚太', '欧洲', '法国', '英国', '沙特', '巴西',
             '东南亚', '新兴亚洲', '香港', 'h股'],
    '股票-股息红利': ['红利', '高股息', '价值', '成长', '低波', '质量'],
    'REITs': ['reit'],
    '货币': ['货币', '现金'],
}

SUBCLASS_KEYWORDS = {
    '股票-行业': [
        ('银行', ['银行']),
        ('电子通信', ['信息', '科技', '通信', '电子', '5g', '物联网', '信息技术', '计算机', '软件',
                     '云计算', '大数据', '信创', '信息安全', '数字经济', '人工智能', 'ai',
                     '卫星', 'tmt', '传媒']),
        ('证券保险', ['证券', '券商', '保险', '非银', '证保', '金融']),
        ('医药', ['医药', '医疗', '生物', '创新药', '中药', '疫苗', '医疗器械', '药']),
        ('食品饮料', ['白酒', '食品', '饮料', '酒']),
        ('半导体', ['芯片', '半导体', '集成电路']),
        ('新能源', ['新能源', '新能', '光伏', '锂电', '电池', '碳中和', '绿色电力', '新能车', '新汽车', '电车']),
        ('军工', ['军工', '国防', '航天', '航空']),
        ('有色', ['有色', '稀土', '稀有', '金属', '矿业']),
        ('能源煤炭', ['煤炭', '石油', '油气', '能源', '资源']),
        ('化工', ['化工', '石化', '材料']),
        ('农业', ['农业', '畜牧', '养殖', '粮食', '农牧']),
        ('地产建筑', ['地产', '房地产', '基建', '建筑', '建材']),
        ('公用环保', ['电力', '公用', '环保', '水务', '电网']),
        ('消费', ['家电', '消费', '旅游', '零售', '纺织', '养老', '教育', '酒店']),
        ('传媒游戏', ['传媒', '游戏', '影视', '动漫', '文娱']),
        ('机械制造', ['机械', '装备', '制造', '机器人', '机床', '船舶', '汽车', '高端',
                     '工业', '智能', '物流', '交运', '运输', '航运', '港口', '铁路', '公路']),
        ('钢铁', ['钢铁']),
        ('央企国企', ['央企', '国企', '央创']),
        ('贵金属', ['黄金']),
    ],
    '跨境': [
        ('中概', ['中概', '中国互联网']),
        ('港股', ['港股', '恒生', '恒指', '香港', 'h股']),
        ('美股', ['纳斯达克', '纳指', '标普', '道琼斯', '美国']),
        ('日本', ['日经', '东证']),
        ('欧股', ['德国', '法国']),
        ('中东', ['沙特']),
        ('新兴市场', ['东南亚', '新兴亚洲', '亚太', '巴西', '印度', '越南', '全球']),
    ],
    '股票-宽基': [
        ('科创板', ['科创', '双创']),
        ('创业板', ['创业']),
        ('小盘', ['1000', '2000', '中创', '民企', '中小']),
        ('策略', ['esg', '龙头', '创新100', '科技',
                 '专精特新', '央企', '互联网', '基本面', '央视', '漂亮', '凤凰', '治理', '可持续', '核心',
                 '战略新兴']),
        ('中盘', ['500']),
        ('大盘', ['300', 'a500', 'a50', '50', '100', '180', '800', '超大盘', '沪深', '中证a', 'a股', '全指', '综指', '深成']),
        ('主题区域', ['湾区', '长三角', '杭州湾', '浙江', '湖北', '成渝', '长江', '之江', '张江', '一带一路']),
    ],
    '股票-股息红利': [
        ('策略', ['红利', '高股息', '价值', '成长', '低波', '质量']),
    ],
    '债券': [
        ('利率债', ['国债', '政金', '国开']),
        ('可转债', ['转债']),
        ('地方债', ['地债', '地方债']),
        ('短融', ['短融']),
        ('信用债', ['城投', '公司债', '信用', '企业债', '科创债', '金融债']),
    ],
    '商品': [
        ('商品期货', ['上期有色金属', '期货']),
        ('贵金属', ['黄金', '金']),
        ('农产品', ['豆粕']),
        ('能化', ['能源化工', '原油', '油气']),
    ],
}


# ---------- S1 池构建核心函数 ----------
def yy_resolve_end_date(end_date):
    if end_date is None:
        today = _dt.date.today()
        days = get_trade_days(start_date=(today - _dt.timedelta(days=30)).strftime('%Y-%m-%d'),
                              end_date=today.strftime('%Y-%m-%d'))
        if len(days) == 0:
            raise RuntimeError('无法获取交易日历')
        return pd.Timestamp(days[-1]).date()
    return pd.Timestamp(end_date).date()


def yy_get_all_etfs(date):
    date = pd.Timestamp(date).date()
    cache = getattr(g, '_all_etfs_cache', {})
    if cache.get('date') == date and cache.get('df') is not None:
        return cache['df']
    all_funds = get_all_securities(['fund'], date=date)
    etfs = all_funds[all_funds['type'] == 'etf'].copy()
    etfs = etfs.reset_index()
    etfs = etfs.rename(columns={etfs.columns[0]: 'code'})
    g._all_etfs_cache = {'date': date, 'df': etfs}
    return etfs


def yy_name_hit(name, keywords):
    if not name:
        return False
    for kw in keywords:
        if kw in name:
            return True
    return False


def yy_filter_basic(etfs_df, date):
    df = etfs_df.copy()
    stats = {'money': 0, 'bond': 0, 'new': 0}
    if EXCLUDE_MONEY:
        n_before = len(df)
        mask_money = df['display_name'].apply(lambda x: yy_name_hit(str(x), MONEY_KEYWORDS))
        df = df[~mask_money]
        stats['money'] = n_before - len(df)
    if EXCLUDE_BOND:
        n_before = len(df)
        mask_bond = df['display_name'].apply(lambda x: yy_name_hit(str(x), BOND_KEYWORDS))
        df = df[~mask_bond]
        stats['bond'] = n_before - len(df)
    if MIN_LIST_DAYS > 0:
        cutoff = pd.Timestamp(date) - pd.Timedelta(days=MIN_LIST_DAYS)
        mask_new = pd.to_datetime(df['start_date']) > cutoff
        stats['new'] = int(mask_new.sum())
        df = df[~mask_new]
    if EXCLUDE_LOF_DELIST and lof_delist_rule_active(asof_date=date):
        n_before = len(df)
        if n_before > 0:
            name_map = {}
            if 'display_name' in df.columns:
                name_map = dict(zip(df['code'].astype(str), df['display_name'].astype(str)))
            kept_codes = set(filter_delisting_lofs(
                df['code'].tolist(), None, 'S1基础池', asof_date=date, names=name_map))
            df = df[df['code'].isin(kept_codes)]
    return df, stats


def _yy_load_fund_invest_target_raw():
    raw = getattr(g, '_index_table_raw', None)
    if raw is not None:
        return raw
    PAGE = 4000
    chunks = []
    offset = 0
    while True:
        q = (query(finance.FUND_INVEST_TARGET).limit(PAGE).offset(offset))
        part = finance.run_query(q)
        if part is None or len(part) == 0:
            break
        chunks.append(part)
        if len(part) < PAGE:
            break
        offset += PAGE
    raw = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    g._index_table_raw = raw
    return raw


def yy_fetch_traced_index_table(end_date):
    asof = pd.Timestamp(end_date).normalize()
    asof_key = str(asof.date())
    cache = getattr(g, '_index_table_cache', {})
    if cache.get('date') == asof_key and cache.get('df') is not None:
        return cache['df']
    df = _yy_load_fund_invest_target_raw()
    empty_cols = ['code', 'name', 'traced_index_name', 'traced_index_code']
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=empty_cols)
    work = df.copy()
    if 'pub_date' in work.columns:
        pub = pd.to_datetime(work['pub_date'], errors='coerce')
        work = work[pub.isna() | (pub <= asof)]
    if 'start_date' in work.columns:
        start = pd.to_datetime(work['start_date'], errors='coerce')
        work = work[start.isna() | (start <= asof)]
    if 'end_date' in work.columns:
        end_ts = pd.to_datetime(work['end_date'], errors='coerce')
        work = work[end_ts.isna() | (end_ts > asof)]
    sort_cols = [c for c in ('start_date', 'pub_date') if c in work.columns]
    if sort_cols:
        work = work.sort_values(sort_cols)
    active = work.drop_duplicates(subset=['code'], keep='last')
    out = active.reindex(columns=empty_cols)
    g._index_table_cache = {'date': asof_key, 'df': out}
    return out


def yy_fetch_one_price(code, end, count):
    try:
        px = get_price(code, end_date=end, count=count, frequency='daily',
                       fields=['close', 'money'], skip_paused=True, fq=None, panel=False)
    except Exception:
        return None
    if px is None or len(px) == 0:
        return None
    close_col = px['close']
    if hasattr(close_col, 'iloc'):
        close_val = float(close_col.iloc[-1])
        money_val = float(px['money'].mean()) / 1e4
    else:
        return None
    return {'code': code, 'close': close_val, 'avg_money_wan': money_val}


def yy_fetch_market_data(codes, end_date):
    end = pd.Timestamp(end_date).strftime('%Y-%m-%d')
    records = []
    for code in codes:
        rec = yy_fetch_one_price(code, end, AVG_MONEY_DAYS)
        if rec is not None:
            records.append(rec)
    if len(records) == 0:
        return pd.DataFrame(columns=['close', 'avg_money_wan'])
    return pd.DataFrame(records).set_index('code')


def yy_query_share_day(d):
    chunks = []
    offset = 0
    while True:
        q = (query(finance.FUND_SHARE_DAILY)
             .filter(finance.FUND_SHARE_DAILY.date == d)
             .limit(4000).offset(offset))
        part = finance.run_query(q)
        if part is None or len(part) == 0:
            break
        chunks.append(part)
        if len(part) < 4000:
            break
        offset += 4000
    if len(chunks) == 0:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


def yy_probe_latest_she_date(end_date):
    probe_code = '159915.XSHE'
    try:
        q = (query(finance.FUND_SHARE_DAILY.date)
             .filter(finance.FUND_SHARE_DAILY.code == probe_code)
             .order_by(finance.FUND_SHARE_DAILY.date.desc())
             .limit(1))
        df = finance.run_query(q)
        if df is not None and len(df) > 0:
            return str(df['date'].iloc[0])[:10]
    except Exception:
        pass
    for back in range(0, 181):
        d = (pd.Timestamp(end_date) - _dt.timedelta(days=back)).strftime('%Y-%m-%d')
        try:
            probe = finance.run_query(
                query(finance.FUND_SHARE_DAILY.code)
                .filter(finance.FUND_SHARE_DAILY.date == d,
                        finance.FUND_SHARE_DAILY.code == probe_code)
                .limit(1))
        except Exception:
            continue
        if probe is not None and len(probe) > 0:
            return d
    return None


def yy_update_shares_map(shares_map, df):
    for c, s in zip(df['code'].astype(str), df['shares']):
        shares_map[c] = s
        shares_map[c.split('.')[0]] = s


def yy_fetch_scale(codes, end_date):
    shares_map = {}
    for back in range(0, 16):
        d = (pd.Timestamp(end_date) - _dt.timedelta(days=back)).strftime('%Y-%m-%d')
        df_day = yy_query_share_day(d)
        if len(df_day) == 0:
            continue
        yy_update_shares_map(shares_map, df_day)
        break

    has_she = any(str(c).endswith('.XSHE') for c in shares_map.keys())
    if not has_she:
        she_date = yy_probe_latest_she_date(end_date)
        if she_date:
            df_she = yy_query_share_day(she_date)
            df_she = df_she[df_she['code'].astype(str).str.endswith('.XSHE')]
            yy_update_shares_map(shares_map, df_she)

    missing = [c for c in codes
               if shares_map.get(c) is None
               and shares_map.get(str(c).split('.')[0]) is None]
    if len(missing) > 0:
        for code in missing:
            try:
                fund_data = get_fund_info(code, end_date)
                if fund_data is not None and 'fund_share' in fund_data.columns:
                    share_series = fund_data['fund_share'].dropna()
                    if len(share_series) > 0:
                        shares_map[code] = float(share_series.iloc[-1]) * 10000
            except Exception:
                continue
    rows = []
    for code in codes:
        s = shares_map.get(code)
        if s is None:
            s = shares_map.get(str(code).split('.')[0])
        rows.append({'code': code, 'shares': s})
    return pd.DataFrame(rows).set_index('code')


def yy_make_index_key(row):
    code = str(row.get('traced_index_code') or '').strip()
    name = str(row.get('traced_index_name') or '').strip()
    if code.lower() in ('', 'none', 'nan'):
        code = ''
    if name.lower() in ('', 'none', 'nan'):
        name = ''
    if code:
        return code
    if name:
        return 'NAME:' + name
    return None


def yy_index_display(row):
    code = str(row.get('traced_index_code') or '').strip()
    name = str(row.get('traced_index_name') or '').strip()
    if code.lower() in ('none', 'nan'):
        code = ''
    if name.lower() in ('none', 'nan'):
        name = ''
    if name and code and ('(' not in name):
        return f"{name}({code})"
    return name or code or '未知指数'


def yy_dedup_by_index(df):
    work = df.copy()
    work['index_key'] = work.apply(yy_make_index_key, axis=1)
    unknown_mask = work['index_key'].isna()
    work.loc[unknown_mask, 'index_key'] = 'UNKNOWN:' + work.loc[unknown_mask, 'code']
    work = work.sort_values(['规模_亿'], ascending=False, na_position='last')
    kept_codes = []
    for key, grp in work.groupby('index_key', sort=False):
        members = grp.sort_values(['规模_亿'], ascending=False, na_position='last')
        winner = members.iloc[0]
        kept_codes.append(winner['code'])
    kept = work[work['code'].isin(kept_codes)].copy()
    dropped = work[~work['code'].isin(kept_codes)].copy()
    return kept, dropped, pd.DataFrame()


def yy_normalize_index_code(code):
    code = str(code or '').strip()
    if code.lower() in ('', 'none', 'nan'):
        return ''
    return re.sub(r'CNY\d*$', '', code)


def yy_extract_index_code(name):
    name = str(name or '').strip()
    m = re.search(r'\(([0-9A-Za-z.\-]+)\)\s*$', name)
    return m.group(1) if m else ''


def yy_normalize_index_name(name):
    name = str(name or '').strip()
    if name.lower() in ('', 'none', 'nan'):
        return ''
    name = re.sub(r'\([^)]*\)$', '', name).strip()
    name = re.sub(r'(CNY|CPR)\d*$', '', name).strip()
    name = re.sub(r'^[沪深](?=[A-Za-z0-9])', '', name)
    return name


def yy_sort_by_rank(df):
    return df.sort_values(['规模_亿'], ascending=False, na_position='last')


def yy_group_keep_largest(df, key_col):
    work = df.copy()
    work[key_col] = work[key_col].fillna('').astype(str)
    empty_mask = work[key_col] == ''
    work.loc[empty_mask, key_col] = 'SINGLE:' + work.loc[empty_mask, 'code']
    work = yy_sort_by_rank(work)
    keep_codes = []
    details = []
    for key, grp in work.groupby(key_col, sort=False):
        winner = grp.iloc[0]
        keep_codes.append(winner['code'])
        if len(grp) > 1:
            losers = grp.iloc[1:]
            details.append({
                'key': key, 'kept_code': winner['code'],
                'kept_name': winner['display_name'],
                'kept_scale_yi': winner['规模_亿'],
                'dropped': [(r['code'], r['display_name']) for _, r in losers.iterrows()],
            })
    kept = work[work['code'].isin(keep_codes)].copy()
    kept = kept.drop(columns=[key_col])
    return kept, details


def yy_dedup_by_alias(df):
    work = df.copy()
    work['_alias_code'] = work['traced_index_code'].apply(yy_normalize_index_code)
    work, details_code = yy_group_keep_largest(work, '_alias_code')
    work['_alias_name'] = work['traced_index_name'].apply(yy_normalize_index_name)
    work, details_name = yy_group_keep_largest(work, '_alias_name')
    return work, details_code + details_name


def yy_corr_pair(ra, rb):
    s_corr = np.nan
    t_corr = np.nan
    idx = ra.index.intersection(rb.index)
    if len(idx) >= 30:
        a = ra.loc[idx]
        b = rb.loc[idx]
        try:
            s_corr = a.corr(b, method='spearman')
        except Exception:
            s_corr = np.nan
    if not np.isfinite(s_corr):
        s_corr = 0.0
    a_tail = ra[ra <= ra.quantile(0.10)]
    b_tail = rb[rb <= rb.quantile(0.10)]
    tail_idx = a_tail.index.union(b_tail.index)
    common_tail = tail_idx.intersection(ra.index).intersection(rb.index)
    if len(common_tail) >= 10:
        a_t = ra.loc[common_tail]
        b_t = rb.loc[common_tail]
        try:
            t_corr = a_t.corr(b_t, method='pearson')
        except Exception:
            t_corr = np.nan
        if not np.isfinite(t_corr):
            t_corr = 0.5
    else:
        t_corr = 0.5
    return round(s_corr * 100), round(t_corr * 100)


def yy_corr_merge(df, end_date):
    work = df.copy()
    codes = work['code'].tolist()
    rets = {}
    end_str = pd.Timestamp(end_date).strftime('%Y-%m-%d')
    try:
        px_all = get_price(codes, end_date=end_str, count=CORR_LOOKBACK,
                           frequency='daily', fields=['close'], skip_paused=True,
                           fq=None, panel=False)
        if px_all is not None and not px_all.empty:
            for c, grp in px_all.groupby('code'):
                close = grp['close'].dropna()
                if len(close) < 30:
                    continue
                r = close.pct_change().dropna()
                if len(r) >= 30:
                    rets[c] = r
        else:
            raise ValueError("empty batch")
    except Exception:
        rets = {}
        for c in codes:
            try:
                px = get_price(c, end_date=end_str, count=CORR_LOOKBACK,
                               frequency='daily', fields=['close'],
                               skip_paused=True, fq=None, panel=False)
            except Exception:
                continue
            if px is None or len(px) < 30:
                continue
            close = px['close'][px['close'].notna()]
            if len(close) < 30:
                continue
            r = close.pct_change().dropna()
            if len(r) >= 30:
                rets[c] = r
    work['_has_ret'] = work['code'].isin(rets)
    details = []
    boundary = []
    groups = list(work.groupby(['asset_class', 'subclass'], sort=False))
    for (asset, subclass), grp in groups:
        grp = grp[grp['_has_ret']]
        if len(grp) < 2:
            continue
        grp = grp.sort_values('规模_亿', ascending=False, na_position='last')
        reps = []
        for _, r in grp.iterrows():
            code = r['code']
            placed = False
            cand_boundary = []
            for rep, rep_name, members in reps:
                s_corr, t_corr = yy_corr_pair(rets[rep], rets[code])
                if s_corr >= CORR_SPEARMAN_TH_PCT or t_corr >= CORR_TAIL_TH_PCT:
                    members.append((code, r['display_name'], s_corr, t_corr))
                    placed = True
                    break
                if s_corr >= CORR_SPEARMAN_TH_PCT - 10 or t_corr >= CORR_TAIL_TH_PCT - 10:
                    cand_boundary.append((code, r['display_name'], rep, rep_name, s_corr, t_corr, asset, subclass))
            if not placed:
                boundary.extend(cand_boundary)
                reps.append((code, r['display_name'], []))
        for rep, rep_name, members in reps:
            if not members:
                continue
            winner = grp[grp['code'] == rep].iloc[0]
            members.sort(key=lambda m: -max(m[2], m[3]))
            details.append({
                'kept_code': winner['code'], 'kept_name': winner['display_name'],
                'kept_asset': asset, 'kept_subclass': subclass,
                'kept_scale_yi': winner['规模_亿'], 'dropped': members,
            })
    drop_codes = {m[0] for d in details for m in d['dropped']}
    kept = work[~work['code'].isin(drop_codes)].copy()
    kept = kept.drop(columns=['_has_ret'])
    return kept, details, boundary


def yy_index_candidates(code):
    code = str(code or '').strip()
    lower = code.lower()
    if lower.endswith('.xshg') or lower.endswith('.xshe') or lower.endswith('.csi'):
        return [code]
    return [code, code + '.CSI', code + '.XSHE', code + '.XSHG']


def yy_fetch_index_weights(index_code, end_date):
    df = None
    asof = pd.Timestamp(end_date).strftime('%Y-%m-%d')
    for candidate in yy_index_candidates(index_code):
        try:
            df_try = get_index_weights(candidate, date=asof)
        except Exception:
            continue
        if df_try is not None and len(df_try) > 0:
            df = df_try
            break
    if df is None or 'weight' not in df.columns:
        return None
    if 'code' in df.columns:
        code_series = df['code'].astype(str)
    else:
        code_series = df.index.astype(str)
    w = pd.to_numeric(df['weight'], errors='coerce')
    valid = w.notna()
    w_valid = w[valid]
    total = w_valid.sum()
    if total <= 0:
        return None
    norm = w_valid / total
    return dict(zip(code_series[valid].tolist(), norm.tolist()))


def yy_fetch_fund_portfolio(etf_code, end_date):
    asof = pd.Timestamp(end_date).date()
    asof_str = asof.strftime('%Y-%m-%d')
    try:
        q = (query(finance.FUND_PORTFOLIO_STOCK)
             .filter(finance.FUND_PORTFOLIO_STOCK.code == etf_code,
                     finance.FUND_PORTFOLIO_STOCK.pub_date <= asof_str)
             .order_by(finance.FUND_PORTFOLIO_STOCK.period_end.desc(),
                       finance.FUND_PORTFOLIO_STOCK.rank.asc())
             .limit(4000))
        df = finance.run_query(q)
    except Exception:
        return None, None
    if df is None or len(df) == 0:
        return None, None

    df = df.copy()
    if 'pub_date' in df.columns:
        pub = pd.to_datetime(df['pub_date'], errors='coerce')
        df = df[pub.notna() & (pub.dt.normalize() <= pd.Timestamp(asof))]
        if len(df) == 0:
            return None, None

    if 'report_type' in df.columns:
        rt = df['report_type'].astype(str)
        is_full = rt.str.contains('年度|半年度', na=False)
    else:
        is_full = df['report_type_id'].isin([401002, 401004])
    full = df[is_full]
    if len(full) == 0:
        return None, None

    full = full.sort_values('period_end', ascending=False)
    latest_end = full['period_end'].iloc[0]
    latest = full[full['period_end'] == latest_end]

    stocks = set()
    weights = {}   # 明确是 dict

    if 'symbol' in latest.columns:
        symbols = latest['symbol'].astype(str)
        prop = pd.to_numeric(latest['proportion'], errors='coerce') if 'proportion' in latest.columns else None
        for i, sym in enumerate(symbols.tolist()):
            sym = str(sym).strip()
            norm = sym.split('.')[0] if '.' in sym else sym
            stocks.add(norm)
            if prop is not None and pd.notna(prop.iloc[i]):
                weights[norm] = float(prop.iloc[i])

    if len(stocks) == 0:
        return None, None

    # 【安全】显式遍历 dict 求和，避免 dict_values 直接参与算术
    total_w = 0.0
    if isinstance(weights, dict):
        for _v in weights.values():
            try:
                total_w += float(_v)
            except (TypeError, ValueError):
                continue

    if total_w > 0 and isinstance(weights, dict):
        weights = {k: float(v) / total_w for k, v in weights.items()}
    else:
        weights = None

    return stocks, weights

def yy_fetch_constituents(index_codes, etf_map=None, end_date=None):
    if end_date is None:
        raise ValueError('yy_fetch_constituents 必须传入 end_date')
    constituents = {}
    weights = {}
    failed = []
    asof = pd.Timestamp(end_date).strftime('%Y-%m-%d')
    for idx, code in enumerate(index_codes):
        stocks = None
        for cand in yy_index_candidates(code):
            try:
                s = get_index_stocks(cand, date=asof)
            except Exception:
                s = None
            if s is not None and len(s) > 0:
                stocks = set(s)
                break
        if stocks is None and etf_map is not None:
            etf_code = etf_map.get(code)
            if etf_code:
                fund_stocks, fund_weights = yy_fetch_fund_portfolio(etf_code, end_date)
                if fund_stocks is not None and len(fund_stocks) > 0:
                    stocks = fund_stocks
                    weights[code] = fund_weights
        if stocks is not None:
            constituents[code] = stocks
            if code not in weights or weights[code] is None:
                weights[code] = yy_fetch_index_weights(code, end_date)
        else:
            failed.append(code)
    return constituents, weights, failed


def yy_index_overlap(set_a, set_b, weights_a, weights_b):
    if len(set_a) == 0 or len(set_b) == 0:
        return 0.0, None
    inter = set_a & set_b
    count_ratio = min(len(inter) / len(set_a), len(inter) / len(set_b))
    weight_ratio = None
    if len(inter) > 0 and weights_a is not None and weights_b is not None:
        wa = sum(weights_a.get(s, 0.0) for s in inter)
        wb = sum(weights_b.get(s, 0.0) for s in inter)
        weight_ratio = min(wa, wb)
    return count_ratio, weight_ratio


def yy_is_duplicate(count_ratio, weight_ratio, count_th, weight_th):
    if count_ratio >= count_th:
        return True
    if weight_ratio is not None and weight_ratio >= weight_th:
        return True
    return False


def yy_dedup_by_constituents(df, count_th, weight_th, end_date):
    work = df.copy()
    work['_idx_code'] = work.apply(
        lambda r: (str(r.get('traced_index_code') or '')
                   if str(r.get('traced_index_code') or '').strip()
                   else yy_extract_index_code(r.get('traced_index_name'))),
        axis=1)
    work['_idx_code'] = work['_idx_code'].apply(yy_normalize_index_code)
    unique_codes = sorted(work.loc[work['_idx_code'] != '', '_idx_code'].unique().tolist())
    etf_map = {}
    for _, r in work.iterrows():
        ic = r['_idx_code']
        if ic and ic not in etf_map:
            etf_map[ic] = str(r['code']).split('.')[0]
    constituents, weights, failed = yy_fetch_constituents(unique_codes, etf_map=etf_map, end_date=end_date)
    codes = [c for c in unique_codes if c in constituents]

    def _idx_scale(c):
        vals = work.loc[work['_idx_code'] == c, '规模_亿'].dropna()
        return float(vals.max()) if len(vals) > 0 else 0.0
    sorted_codes = sorted(codes, key=_idx_scale, reverse=True)
    groups = []
    for c in sorted_codes:
        placed = False
        for rep, members in groups:
            count_r, weight_r = yy_index_overlap(constituents[rep], constituents[c],
                                                 weights.get(rep), weights.get(c))
            if yy_is_duplicate(count_r, weight_r, count_th, weight_th):
                members.append(c)
                placed = True
                break
        if not placed:
            groups.append((c, [c]))
    details = []
    drop_codes = set()
    for rep, group_codes in groups:
        if len(group_codes) == 1:
            continue
        winner = work[work['_idx_code'] == rep].iloc[0]
        losers_df = work[work['_idx_code'].isin(group_codes) & (work['_idx_code'] != rep)]
        dropped = []
        for _, r in losers_df.iterrows():
            count_r, weight_r = yy_index_overlap(constituents[rep], constituents[r['_idx_code']],
                                                 weights.get(rep), weights.get(r['_idx_code']))
            dropped.append((r['code'], r['display_name'], yy_index_display(r), count_r, weight_r))
            drop_codes.add(r['code'])
        details.append({
            'kept_code': winner['code'], 'kept_name': winner['display_name'],
            'kept_index': yy_index_display(winner), 'kept_scale_yi': winner['规模_亿'],
            'dropped': dropped,
        })
    kept = work[~work['code'].isin(drop_codes)].copy()
    kept = kept.drop(columns=['_idx_code'])
    uncovered = []
    for _, r in work[work['_idx_code'].isin(failed)].iterrows():
        uncovered.append((yy_index_display(r), r['code'], r['display_name'], 'failed'))
    for _, r in work[work['_idx_code'] == ''].iterrows():
        uncovered.append((yy_index_display(r), r['code'], r['display_name'], 'empty'))
    return kept, details, uncovered


def yy_classify_etf(name):
    if not name:
        return '其他'
    low = str(name).lower()
    for asset_class, keywords in ASSET_CLASS_KEYWORDS.items():
        if any(kw.lower() in low for kw in keywords):
            return asset_class
    return '其他'


def yy_asset_class(row):
    name = str(row.get('display_name') or '')
    idx = re.sub(r'\([^)]*\)$', '', str(row.get('index_display') or '')).strip()
    low_name = name.lower()
    low_idx = idx.lower() if idx else ''
    if yy_name_hit(low_name, STAR_BROAD_KEYWORDS) or yy_name_hit(low_idx, STAR_BROAD_KEYWORDS):
        return '股票-宽基'
    if yy_name_hit(low_name, BOND_KEYWORDS) or yy_name_hit(low_idx, BOND_KEYWORDS):
        return '债券'
    if (yy_name_hit(low_idx, ['上期有色金属', '期货'])
            or yy_name_hit(low_name, ['上期有色金属', '豆粕期货', '能源化工'])):
        return '商品'
    if yy_name_hit(low_name, ['黄金股']) or yy_name_hit(low_idx, ['黄金股', '黄金股票']):
        return '股票-行业'
    cross_hit = (yy_name_hit(low_name, CROSS_BORDER_KEYWORDS)
                 or yy_name_hit(low_idx, CROSS_BORDER_KEYWORDS))
    cross_exclude = (yy_name_hit(low_name, CROSS_BORDER_EXCLUDE)
                     or yy_name_hit(low_idx, CROSS_BORDER_EXCLUDE))
    if cross_hit and not cross_exclude:
        return '跨境'
    if yy_name_hit(low_name, SMART_BETA_KEYWORDS) or yy_name_hit(low_idx, SMART_BETA_KEYWORDS):
        return '股票-股息红利'
    cls = yy_classify_etf(name)
    if cls == '其他' and low_idx:
        idx_cls = yy_classify_etf(idx)
        if idx_cls == '股票-宽基':
            cls = '股票-宽基'
    if cls == '股票-宽基' and (yy_name_hit(low_name, REAL_INDUSTRY_KEYWORDS)
                               or yy_name_hit(low_idx, REAL_INDUSTRY_KEYWORDS)):
        return '股票-行业'
    if cls != '其他':
        return cls
    if idx and idx != '未知指数':
        idx_cls = yy_classify_etf(idx)
        if idx_cls != '其他':
            return idx_cls
    return '其他'


def yy_subclass(row):
    rules = SUBCLASS_KEYWORDS.get(str(row.get('asset_class') or ''))
    if not rules:
        return '其他'
    texts = [str(row.get('display_name') or '')]
    idx = re.sub(r'\([^)]*\)$', '', str(row.get('index_display') or '')).strip()
    if idx and idx != '未知指数':
        texts.append(idx)
    for text in texts:
        if not text or text == '未知指数':
            continue
        low = text.lower()
        for subclass, keywords in rules:
            if any(kw.lower() in low for kw in keywords):
                return subclass
    return '其他'


def build_etf_pool(end_date):
    """完整7层去重流水线，返回最终ETF代码列表。"""
    _step_counter[0] = 0
    end_date = yy_resolve_end_date(end_date)

    etfs = yy_get_all_etfs(end_date)
    n_all = len(etfs)
    etfs, basic_stats = yy_filter_basic(etfs, end_date)

    index_table = yy_fetch_traced_index_table(end_date)
    df = etfs.merge(index_table[['code', 'traced_index_name', 'traced_index_code']],
                    on='code', how='left')
    codes = df['code'].tolist()
    market = yy_fetch_market_data(codes, end_date)
    scale = yy_fetch_scale(codes, end_date)
    df = df.merge(market, on='code', how='left')
    df = df.merge(scale, on='code', how='left')
    df['规模_亿'] = df['shares'] * df['close'] / 1e8

    kept, dropped, group_stats = yy_dedup_by_index(df)
    n_after_index = len(kept)

    if EXCLUDE_MINI and MINI_SCALE > 0:
        mini_mask = kept['规模_亿'].notna() & (kept['规模_亿'] < MINI_SCALE)
        kept = kept[~mini_mask]

    if EXCLUDE_LIQUIDITY and MIN_MONEY > 0:
        liq_mask = kept['avg_money_wan'].notna() & (kept['avg_money_wan'] < MIN_MONEY)
        kept = kept[~liq_mask]

    kept, alias_details = yy_dedup_by_alias(kept)
    kept, const_details, uncovered = yy_dedup_by_constituents(
        kept, CONSTITUENT_OVERLAP, WEIGHT_OVERLAP, end_date)

    kept = yy_sort_by_rank(kept).copy()
    kept['index_display'] = kept.apply(yy_index_display, axis=1)
    kept['asset_class'] = kept.apply(yy_asset_class, axis=1)
    kept['subclass'] = kept.apply(yy_subclass, axis=1)
    kept, corr_details, corr_boundary = yy_corr_merge(kept, end_date)

    final = yy_sort_by_rank(kept).copy()
    class_exclude = []
    if EXCLUDE_DIVIDEND:
        class_exclude.append(('股票-股息红利', '股息红利'))
    if EXCLUDE_CROSS:
        class_exclude.append(('跨境', '跨境'))
    if EXCLUDE_COMMODITY:
        class_exclude.append(('商品', '商品'))
    for cls, _ in class_exclude:
        final = final[final['asset_class'] != cls]

    log.info(f'【S1池构建】场内ETF总数={n_all}，最终={len(final)}只')
    return final['code'].tolist()


# ---------- S1 交易逻辑 ----------
def calculate_bias(codes, end_date):
    records = []
    end = pd.Timestamp(end_date).strftime('%Y-%m-%d')
    max_period = max(BIAS_SORT_DAYS, BIAS_BUY_DAYS)
    fetch_count = max_period + 20
    for code in codes:
        try:
            px = get_price(code, end_date=end, count=fetch_count, frequency='daily',
                           fields=['close'], skip_paused=True, fq='pre', panel=False)
        except Exception:
            continue
        if px is None or len(px) < max_period:
            continue
        close = px['close']
        ma_buy = close.rolling(BIAS_BUY_DAYS).mean().iloc[-1]
        ma_sort = close.rolling(BIAS_SORT_DAYS).mean().iloc[-1]
        if ma_buy <= 0 or ma_sort <= 0:
            continue
        bias_buy = (close.iloc[-1] - ma_buy) / ma_buy * 100
        bias_sort = (close.iloc[-1] - ma_sort) / ma_sort * 100
        try:
            name = get_security_info(code).display_name
        except Exception:
            name = code
        records.append({
            '代码': code, '名称': name,
            '20日乖离率(%)': bias_buy, '50日乖离率(%)': bias_sort,
        })
    return pd.DataFrame(records) if records else pd.DataFrame()


def check_trend(code, end_date, mode):
    if mode == 0:
        return True
    look = TREND_LOOKBACK
    px = get_price(code, end_date=end_date, count=look + 1, frequency='daily',
                   fields=['close'], skip_paused=True, fq='pre', panel=False)
    if px is None or len(px) < look + 1:
        return True
    close = px['close']
    last = float(close.iloc[-1])
    ma = float(close.iloc[-look:].mean())
    recent_low = float(close.iloc[:-1].min())
    not_new_low = last > recent_low
    above_ma = last > ma
    if mode == 1:
        return not_new_low
    if mode == 2:
        return above_ma
    if mode == 3:
        return not_new_low and above_ma
    return True


def check_oversold_stabilized(code, end_date):
    need = 20 + OVERSOLD_LOOKBACK
    px = get_price(code, end_date=end_date, count=need, frequency='daily',
                   fields=['close'], skip_paused=True, fq='pre', panel=False)
    if px is None or len(px) < need:
        return False
    close = px['close']
    ma20 = close.rolling(20).mean()
    bias20 = (close / ma20 - 1) * 100
    was_oversold = bias20.iloc[-OVERSOLD_LOOKBACK:].min() < BUY_BIAS_TH
    if not was_oversold:
        return False
    return check_trend(code, end_date, TREND_FILTER_MODE)


def should_sell(code, entry_price, entry_date, context):
    if entry_price is None or entry_price <= 0:
        return True, '残留无入场价'
    px = get_price(code, end_date=context.previous_date, count=g.BIAS_BUY_DAYS + 1,
                   frequency='daily', fields=['close'], skip_paused=True, fq='pre', panel=False)
    if px is None or len(px) < g.BIAS_BUY_DAYS + 1:
        return False, ''
    close = px['close']
    last = float(close.iloc[-1])
    ma20 = float(close.rolling(g.BIAS_BUY_DAYS).mean().iloc[-1])
    if ma20 <= 0:
        return False, ''
    bias20 = (last / ma20 - 1) * 100
    ret = last / entry_price - 1.0
    if g.STOP_LOSS_PCT and ret <= -g.STOP_LOSS_PCT:
        return True, '深套止损'
    if g.SELL_BIAS_TH is not None and bias20 >= g.SELL_BIAS_TH and ret >= 0:
        return True, '回本止盈'
    if g.SELL_PROFIT_PCT and ret >= g.SELL_PROFIT_PCT:
        return True, '目标收益'
    if g.HOLD_MAX_DAYS and entry_date:
        ndays = get_trade_days(start_date=entry_date, end_date=context.current_dt.date())
        if len(ndays) - 1 >= g.HOLD_MAX_DAYS:
            return True, '时间'
    return False, ''


def _sync_params(context):
    for _k in ['MAX_HOLD', 'BIAS_SORT_DAYS', 'BIAS_BUY_DAYS', 'BUY_BIAS_TH',
               'SELL_BIAS_TH', 'STOP_LOSS_PCT', 'SELL_PROFIT_PCT', 'HOLD_MAX_DAYS',
               'TREND_FILTER_MODE', 'TREND_LOOKBACK', 'OVERSOLD_LOOKBACK']:
        if hasattr(g, _k):
            globals()[_k] = getattr(g, _k)
        else:
            setattr(g, _k, globals()[_k])


def _s1_refresh_pool(context):
    if POOL_UPDATE_MONTHLY:
        m = context.current_dt.month
        if (m - 1) % POOL_REFRESH_MONTHS == 0 and m != getattr(g, 'last_pool_refresh_month', 0):
            g.etf_pool = build_etf_pool(context.previous_date)
            g.last_pool_refresh_month = m
    else:
        g.etf_pool = build_etf_pool(context.previous_date)
    if g.etf_pool:
        g.etf_pool = filter_delisting_lofs(g.etf_pool, context, 'S1池')


def _iter_live_positions(context):
    live = []
    for sec, pos in context.portfolio.positions.items():
        if pos is not None and pos.total_amount > 0:
            live.append(sec)
    return live


def _collect_orphan_positions(context):
    ep = getattr(g, 'entry_price', None)
    s1_entries = set(ep.keys()) if isinstance(ep, dict) else set()
    orphans = []
    for sec in _iter_live_positions(context):
        owner = g.stock_owner.get(sec)
        if owner in (SID_S1, SID_S2):
            continue
        if sec in s1_entries:
            continue
        orphans.append(sec)
    return orphans


def _close_orphans(context, reason):
    leftover = []
    for sec in _collect_orphan_positions(context):
        close_position(sec)
        pos = context.portfolio.positions.get(sec)
        if pos is None or pos.total_amount <= 0:
            log.info("【融合·清理残留】%s 已清空 (%s)", sec, reason)
        else:
            leftover.append(sec)
    return leftover


def _close_all_s2(context):
    for sec in list(g.accounts[SID_S2]['holdings']):
        close_position(sec)
    _close_orphans(context, '进抄底前清残留')
    remaining = []
    for sec in _iter_live_positions(context):
        if g.stock_owner.get(sec) == SID_S1:
            continue
        remaining.append(sec)
    return remaining


def _s1_collect_positions(context):
    s1_real_positions = []
    seen = set()
    for sec in list(g.stock_owner.keys()):
        if g.stock_owner.get(sec) != SID_S1:
            continue
        pos = context.portfolio.positions.get(sec)
        if pos is not None and pos.total_amount > 0:
            s1_real_positions.append(sec)
            seen.add(sec)
    if g.mode == 'bottom':
        ep = getattr(g, 'entry_price', None)
        entry_codes = list(ep.keys()) if isinstance(ep, dict) else []
        for sec in entry_codes:
            if sec in seen:
                continue
            pos = context.portfolio.positions.get(sec)
            if pos is not None and pos.total_amount > 0:
                s1_real_positions.append(sec)
                seen.add(sec)
    return s1_real_positions


def _s1_entry_get(code):
    ep = getattr(g, 'entry_price', None)
    ed = getattr(g, 'entry_date', None)
    price = ep.get(code) if isinstance(ep, dict) else ep
    date = ed.get(code) if isinstance(ed, dict) else ed
    return price, date


def _s1_entry_set(code, price, date):
    if not isinstance(getattr(g, 'entry_price', None), dict):
        g.entry_price = {}
    if not isinstance(getattr(g, 'entry_date', None), dict):
        g.entry_date = {}
    g.entry_price[code] = price
    g.entry_date[code] = date


def _s1_entry_clear(code):
    if isinstance(getattr(g, 'entry_price', None), dict):
        g.entry_price.pop(code, None)
    else:
        g.entry_price = {}
    if isinstance(getattr(g, 'entry_date', None), dict):
        g.entry_date.pop(code, None)
    else:
        g.entry_date = {}


def _s1_find_targets(bias_df, context, exclude, limit):
    eligible = []
    held = set(exclude)
    if getattr(g, 's1_enable_corr_filter', False):
        multiplier = max(1, int(getattr(g, 's1_corr_candidate_multiplier', 10)))
        candidate_limit = max(limit, limit * multiplier)
    else:
        candidate_limit = limit
    for _, row in bias_df.iterrows():
        if len(eligible) >= candidate_limit:
            break
        code = row['代码']
        if code in held:
            continue
        if check_oversold_stabilized(code, context.previous_date):
            eligible.append(code)
    return apply_correlation_guard_codes(
        context, eligible, list(exclude), limit, SID_S1)


def _s1_buy_targets(context, targets):
    if not targets:
        return []
    current_s1 = _s1_collect_positions(context)
    target_universe = list(dict.fromkeys(current_s1 + list(targets)))
    target_values = compute_s1_target_values(context, target_universe)
    min_target = min([target_values.get(code, 0.0) for code in targets] or [0.0])
    if min_target < MIN_OPEN_GRANT:
        return []
    filled_codes = []
    cd = get_current_data()
    today = context.current_dt.date()
    for code in targets:
        available = context.portfolio.available_cash * 0.995
        buy_value = min(target_values.get(code, 0.0), available)
        if buy_value < MIN_OPEN_GRANT:
            continue
        order = open_position(context, code, buy_value, SID_S1)
        filled = getattr(order, 'filled', 0) if order else 0
        if filled > 0:
            _s1_entry_set(code, cd[code].day_open, today)
            filled_codes.append(code)
            log.info("【融合·S1买入】%s 成交 %g 股，目标金额 %.2f",
                     code, filled, buy_value)
    return filled_codes


def s1_bottom_check(context):
    _sync_params(context)
    _close_orphans(context, '日检')
    _s1_refresh_pool(context)
    if len(g.etf_pool) == 0:
        if g.mode == 'bottom' and not _s1_collect_positions(context):
            g.mode = 'rot'
            g.entry_price = {}
            g.entry_date = {}
            log.info("【融合·模式切换】抄底→轮动：S1持仓已清空（池为空）")
        return
    bias_df = calculate_bias(g.etf_pool, context.previous_date)
    if bias_df.empty:
        if g.mode == 'bottom' and not _s1_collect_positions(context):
            g.mode = 'rot'
            g.entry_price = {}
            g.entry_date = {}
            log.info("【融合·模式切换】抄底→轮动：S1持仓已清空（无乖离数据）")
        return
    bias_df = bias_df.sort_values(by='50日乖离率(%)', ascending=True).reset_index(drop=True)
    max_hold = max(1, int(g.MAX_HOLD))

    s1_real_positions = _s1_collect_positions(context)
    if s1_real_positions:
        for code in list(s1_real_positions):
            ep, ed = _s1_entry_get(code)
            sell, reason = should_sell(code, ep, ed, context)
            if sell:
                close_position(code)
                pos = context.portfolio.positions.get(code)
                if pos is None or pos.total_amount <= 0:
                    log.info("【融合·S1卖出】%s 触发卖出 (%s)", code, reason)
                    _s1_entry_clear(code)
        s1_real_positions = _s1_collect_positions(context)

    if not s1_real_positions:
        if g.mode == 'bottom':
            g.mode = 'rot'
            g.entry_price = {}
            g.entry_date = {}
            log.info("【融合·模式切换】抄底→轮动：S1持仓已清空")
            return
        targets = _s1_find_targets(bias_df, context, exclude=[], limit=max_hold)
        if not targets:
            return
        s2_remaining = _close_all_s2(context)
        if s2_remaining:
            log.info("【融合·抄底取消】S2清仓未完成，放弃本次抄底")
            return
        filled_codes = _s1_buy_targets(context, targets)
        if not filled_codes:
            return
        g.mode = 'bottom'
        log.info("【融合·模式切换】轮动→抄底：买入 %s", filled_codes)
        return

    g.mode = 'bottom'
    slots_left = max_hold - len(s1_real_positions)
    if slots_left <= 0:
        return
    targets = _s1_find_targets(bias_df, context, exclude=s1_real_positions, limit=slots_left)
    if not targets:
        return
    filled_codes = _s1_buy_targets(context, targets)
    if filled_codes:
        log.info("【融合·S1补仓】补入 %s，当前 %d/%d",
                 filled_codes, len(s1_real_positions) + len(filled_codes), max_hold)


# =====================================================================
# 融合调度层
# =====================================================================
SID_S1 = 1
SID_S2 = 2


def _restore_container(context):
    set_context(context)
    if not hasattr(g, 'accounts') or g.accounts is None:
        allocator_init(context)
        register_strategy(SID_S1, 0.5, priority=2)
        register_strategy(SID_S2, 0.5, priority=1)
        log.info("【容器】accounts 缺失，已重新注册 S1/S2")
        return
    for attr, default in (
        ('stock_owner', {}),
        ('strategy_realized', {}),
        ('strategy_peak', {}),
        ('strategy_max_dd', {}),
        ('strategy_max_dd_date', {}),
        ('strategy_prev_equity', {}),
        ('benchmark_weak', {}),
        ('benchmark_last', {}),
        ('etf_benchmark_cache', {}),
    ):
        if not hasattr(g, attr) or getattr(g, attr) is None:
            setattr(g, attr, default)
    if SID_S1 not in g.accounts:
        register_strategy(SID_S1, 0.5, priority=2)
    if SID_S2 not in g.accounts:
        register_strategy(SID_S2, 0.5, priority=1)
    rebuild_allocator()
    log.info("【容器】已重建 CapitalAllocator 并回填 context")


def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001,
                              close_commission=0.0001, close_today_commission=0.0001,
                              min_commission=5), type="fund")
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    set_benchmark("510300.XSHG")

    allocator_init(context)
    register_strategy(SID_S1, 0.5, priority=2)
    register_strategy(SID_S2, 0.5, priority=1)
    set_context(context)

    s1_init_state(context)
    s2_init_state(context)
    log_lof_delist_audit(context)

    g.mode = 'rot'


def process_initialize(context):
    _restore_container(context)


def after_code_changed(context):
    g.MAX_HOLD = MAX_HOLD
    if not hasattr(g, 'mode'):
        g.mode = 'rot'
    _restore_container(context)
    unschedule_all()
    run_daily(morning_routine, time='09:00')
    run_daily(s1_bottom_check, time='09:35')
    run_daily(check_weak_period_daily, time='09:40')
    run_daily(compute_regime_p0_daily, time='11:30')
    run_daily(afternoon_routine, time=S2_SELL_TIME)
    run_daily(afternoon_routine_buy, time=S2_BUY_TIME)
    for _t in S2_CHECK_TIMES:
        run_daily(check_pending_buys_trend, time=_t)
    run_daily(force_buy_pending, time=S2_FORCE_TIME)
    run_daily(reset_daily_flags, time='15:10')
    run_daily(minute_level_stop_loss, time='every_bar')
    run_daily(minute_level_pct_stop_loss, time='every_bar')
    run_daily(make_record, time='15:01')


def afternoon_routine_buy(context):
    if g.mode == 'bottom':
        return
    log.info("▶️ 【午盘·买入流水线】启动...")
    log.info("【买入执行】执行买入操作（首次趋势判断）...")
    execute_buy_trades(context)
    log.info("⏸️ 【午盘·买入流水线】执行完毕！")