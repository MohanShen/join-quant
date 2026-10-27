# ===== VALIDATED STRATEGY (run-family archive) — join-quant epoch 9 =====
# expId:            xp-val-liq1-e9
# ideaId:           q-e9-liq-1  (the fill-feasibility floor; write-up in wiki/families/多因子ML.md §2/§6)
# baseExpId:        study/多因子ML/baseline-e6.py  (= py2to3(strategies/2026-06-28_高质量稳定上涨策略-d02cde29.py)
#                   + the frozen OVERRIDE, 43002 chars, re-verified byte-identical before this run)
# family:           多因子ML   (source base: strategies/2026-06-28_高质量稳定上涨策略-d02cde29.py)
# mutation:         ONE mechanical change, applied at this book's three stock-selection sites — a per-sleeve
#                   DYNAMIC fill-feasibility floor. Liquidity measure: median of 20 daily money bars ending at
#                   context.previous_date, so today's bar is never queried (no lookahead). Floor, recomputed on
#                   EVERY call from LIVE equity:
#                       context.portfolio.total_value x STRATEGY_ALLOCATION[sleeve] / n_slots / order_volume_ratio
#                   Sites: (1) small_cap_get_stocks' return, (2) etf_trade's ranked candidate list before the
#                   [:target_num] slice (both auto and fixed branches), (3) white_horse_select_big/small's returns.
#                   Nothing else moves: ranking, momentum windows, timing, thresholds and the cost block are
#                   verbatim. A data-fetch failure logs a LOUD LIQFLOOR ERROR rather than silently passing through,
#                   so "the floor removed nothing" can never be confused with "the floor never ran".
#                   Built by study/多因子ML/build-e9-liq.js (asserted edits).
# free_parameters:  NONE. order_volume_ratio=0.05 and capital=1e6 are harness pins; n_slots (6 / 1 / 20) and the
#                   0.35 / 0.40 / 0.25 sleeve weights are the book's own. LIQ_FLOOR_MULT = 1.0 is the feasibility
#                   MINIMUM, not a comfort level, and the floor compounds with equity instead of being a static
#                   threshold (the rule 五福闹新春 q-e9-liq established: compute off the day's total_value, never
#                   off initial capital). The floor does NOT exempt existing holdings, so its Delta is
#                   full-strength rather than a lower bound.
# train_objective:  1.5643   (TRAIN 2024-01-01..2024-12-31: total 165.79% / annual 165.79% / maxDD 9.36% / sharpe 5.89;
#                   base d02cde29 on the same bench: 1.4731 / annual 156.71% / maxDD 9.40% / sharpe 5.45)
# val_objective:    1.1211   (VAL   2025-01-01..2025-12-31: total 119.67% / annual 120.15% / maxDD 8.04% / sharpe 6.98)
# sharpe_val:       6.98
# gate_val:         pass     (sharpe 6.98 >= 1.0, epoch-9 stageGate('validate'); objective (120.15-8.04)/100 = 1.1211)
# harness_epoch:    9
# ranAt:            2026-10-27
# val_runId:        xp-val-liq1-e9   (algorithmId 28c60b460f2655483cf2ee564e8a07c7)
# val_curve:        data/series/study_多因子ML_variants_q-e9-liq-1__val__e9.json  (243d, 2025-01-02..2025-12-31)
# source_file:      study/多因子ML/variants/q-e9-liq-1.py — the EXACT file the VAL ran. Everything below this
#                   header is byte-identical to it: sha256 e955f897a377aebd68f9b75352615e7ff6a251dc7070a5d7efb13e5e06c870a5
#                   (54210 bytes, verified at archive time). No re-build, no re-pin, no edit.
# realizability:    2   (realizabilityScope: xp-val-liq1-e9 — R=2 was MEASURED on this exact book, by q-e9-liq-1)
#
# flags / honest caveats — carry these with any quotation of the numbers above:
#   ⚠  零滑点台. Every figure here is measured on the frozen ZERO-SLIPPAGE bench. The floor closes the
#      "could this fill at all" leg of realism and nothing else; slippage and market impact are still absent.
#   ⚠⚠ QUOTE TRAIN AND VAL AS A PAIR: 1.5643 / sharpe 5.89 (2024) and 1.1211 / sharpe 6.98 (2025).
#      The VAL sharpe is HIGHER than TRAIN. Verified NOT a scrape artefact: the stored curve reproduces
#      total 119.67 / annual 120.15 / maxDD 8.04 exactly, and the rise is a VOLATILITY effect — curve-derived
#      annualised vol 17.3% in 2025 against 29.1% in 2024 (the scrape's implied 120.15/6.98 = 17.2% agrees).
#      JQ's sharpe runs above a simple arithmetic ratio on BOTH windows (6.98 vs 4.80; 5.89 vs 3.65), so the
#      relationship is consistent across windows rather than a 2025-only anomaly.
#   ⚠⚠ 48% of TRAIN log-growth sits in Sep-Oct 2024, and the floor RAISES that concentration slightly
#      (48.4% -> 49.6%). Whether the 2024 level is repeatable is NOT settled — the criteria are study
#      q-e9-2 (etf weight -> 0) and q-e9-4 (white_horse -> 0), both unrun, and both must henceforth be
#      scored against THIS book's 1.5643, not the base's 1.4731.
#   ⚠⚠ The etf sleeve carries 40% of the weight and its 动量 edge is status: REFUTED (study q-e6-2: with etf
#      zeroed over 2023, total 26.94 -> 35.37 and sharpe 1.56 -> 2.49; that leg's contribution lived entirely
#      in 2022, from a pool a 2026 author assembled). The family's only measured edge is 规模因子 on the
#      small_cap sleeve (q-e9-1: 35% of the weight supplying 62.4% of annual).
#   ⚠⚠ CAPACITY IS UNMEASURED. liq-1 tested the 1x feasibility point ONLY; study/多因子ML/variants/q-e9-liq-2.py
#      (5x) and q-e9-liq-3.py (10x) are BUILT AND UNRUN. No capacity claim in either direction is permitted —
#      "sharpe 6.98 leaves huge headroom to the 1.0 gate" is NOT capacity evidence (capacity is what a book can
#      ABSORB, not how much sharpe it has spare; 大小盘轮动's product was self-corrected to R=2 on this same rule).
#      Bottleneck located: at 1x the floor removed names on 97/242 etf calls but 0/73 small_cap and 0/223
#      white_horse calls, so any capacity reading must be reported PER SLEEVE.
#   ⚠⚠ There is NO OUT-OF-SAMPLE evidence for this book. The 2026 holdout is untouched; this bench has 1 of 2
#      OOS tests left. The repo's only two OOS results to date are both negative (大小盘轮动 -0.21,
#      红利低频 -0.51), so TRAIN -> VAL holding up is not evidence that 2026 will.
#   ⚠  Three realism legs stay OPEN beyond fills (family frontmatter realism): the daily bar collapses this
#      book's intraday stop-losses into a close-time check, so intraday drawdown is structurally invisible;
#      the etf pool is hand-written in 2026 and its SELECTION-level hindsight is untested (q-e9-pool-sel) —
#      only the LISTING half is closed, and measured to be a pool PENALTY not a bonus (q-e9-pit: +0.1212 on
#      the base); and ~3.8pp of drawdown protection hangs on an n=2 January/April calendar rule (q-3).
#   ⚠  Sibling candidates NOT chosen, and why: q-e9-pit (point-in-time pool) scores HIGHER on TRAIN (1.5943),
#      but its entire +0.0300 edge over this book comes from KEEPING two names this floor rejects (159652,
#      501018) — selecting it would be selecting return from fills measured as infeasible. The union candidate
#      xp-e9-1 is measurement-IDENTICAL to this book (242/242 days bit-identical, rho 1.000000) and carries a
#      build-time-frozen 2024 pool cutoff that a --window val run would wrongly keep applying.
#   Full write-up: wiki/families/多因子ML.md §1/§2/§4/§6 (q-e9-liq-1, q-e9-pit, q-e9-pool, xp-e9-1, xp-val-liq1-e9).
# ================================================================================

# ============================================================================
# q-e9-liq-1 变体：多因子ML 冠军 d02cde29 —— 逐仓「可成交下限」(fill-feasibility floor)（可成交最小值，1x —— 本次要跑的那个）
#
# 【为什么跑这一测】
#   本家族在 integrate-eligible 被 REJECTED，唯一阻断是 realizability: 1，owner=none ——
#   没有任何别的阶段会去清它。而那个 1 是 prose：realizabilityBasis 引的是一句关于 headline
#   「水平」不可达的话，与「日线 bar 撑不起这笔成交」是两回事；realizability-lint 在本书上零 flag。
#   本测把猜测换成测量，无论数字落在哪一边。
#
# 【父本】
#   study/多因子ML/baseline-e6.py  sha256 fa3e86afc68ce6fe514554c0a4f25f7aa2418edf440fa79ae75fb22445a1dcad  (43002 chars)
#   == py2to3(strategies/2026-06-28_高质量稳定上涨策略-d02cde29.py) + 当前 frozen OVERRIDE，逐字相同。
#   父本实测（epoch 9, TRAIN 2024-01-01..2024-12-31）：
#     objective 1.4731 / sharpe 5.45 / annual 156.71 / maxDD 9.40
#   曲线：data/series/2026-06-28_高质量稳定上涨策略-d02cde29__train__e9.json（242 点，2024-01-02..2024-12-31，final cum 156.71）
#   ⇒ 对照不欠 backtest。本变体与父本只差「可成交下限」一个维度。
#
# 【地板算术 —— 由 harness 推出，不是我们挑的数，且没有自由参数】
#   harness epoch 9: costs.capital = 1000000, costs.orderVolumeRatio = 0.05
#   某仓要在「一只标的」上建 V 元的仓，而一天最多只能吃掉该标的成交额的 order_volume_ratio，
#   所以要求该标的日成交额 >= V / order_volume_ratio。V 本身逐日由 LIVE 市值算出：
#     V = context.portfolio.total_value x STRATEGY_ALLOCATION[sleeve] / n_slots
#   因此地板随净值复利自动放大（本书 2024 年 +156.71%，年末约为年初的 2.5 倍），
#   不是一个静态阈值。按 1e6 本金折算到年初：
#     small_cap    alloc 0.35 /  6 槽 ⇒ 1.167e+6 CNY/日  （= 可成交下限本身）
#     etf          alloc 0.4 /  1 槽 ⇒ 8.000e+6 CNY/日  （= 可成交下限本身）
#     white_horse  alloc 0.25 / 20 槽 ⇒ 2.500e+5 CNY/日  （= 可成交下限本身）
#   LIQ_FLOOR_MULT = 1.0  —— 恰为可成交最小值，不是一个「舒适水位」。
#
# 【流动性度量】
#   get_price(codes, count=20, end_date=context.previous_date, fields=['money'], frequency='1d')
#   的 20 bar 中位数。用中位数而不是均值：一天的放量不得把一只平常没量的标的放进来。
#   end_date 是前一交易日 ⇒ 今天要成交的那根 bar 永不被查询，无未来函数。
#   取数失败 → log.error 一条 LIQFLOOR ERROR 并原样返回（LOUD，不静默跳过）：静默失败会
#   逐字复现父本，和「地板什么都没剔掉」不可区分 —— 而后者恰恰是 大小盘轮动 / b3751277 的
#   liq-1 实际得到的答案，必须可信。
#
# 【三处选股点（本书三仓各一处），别无其他】
#   (1) small_cap：small_cap_get_stocks 的 return 之前，行业分散之后、[:stock_num*2] 之前
#       （周二调仓与 small_cap_check_remain 补仓两个调用点自动都被覆盖）
#   (2) etf     ：etf_trade 里排序后的候选名单上、[:target_num] 切片之前（auto/fixed 两支都插）
#   (3) white_horse：white_horse_select_big 与 white_horse_select_small 的 return
#   逐仓打 LIQFLOOR 行（sleeve / site / date / floor / in / out / removedFrac / slots / removed），
#   归因因此免费附带。用 log.error 而不是 log.info，因为本书有三处 log.set_level。
#
# 【刻意不碰】
#   动量/ATR 动态窗口/溢价率扣分、小市值的市值排序与行业分散、白马的三档市场温度与因子筛，
#   止损、空仓月、调度表、三个成本 pin 与文件尾部 frozen OVERRIDE，全部逐字不动。
#   white_horse_adjust 的 else 支（config['foreign_etfs'] 四只宽基）没有被地板筛 —— 它不是
#   dispatch 指名的选股点，且是四只大 ETF；这一点明写出来，不是遗漏。
#
# ⚠ 【这是 STRICT 版，不是 buy-side 下界】
#   与 study/ETF动量/variants/q-e9-3_liq-1.py 的约定一致：不对已持仓名字豁免。被地板剔除的
#   名字会从 target_list 消失，于是下一次调仓的卖出逻辑会把它卖掉。这是「拿不进来的名字也
#   拿不住」的严格读法，而不是 五福闹新春 q-e9-liq 的买入侧下界读法。
#
# 【判据（跑前固定，两个方向都已写死）】
#   INERT：三仓每次 rebalance 的 removedFrac 全为 0 且与父本曲线 max|Δcum| == 0
#          ⇒ R=1 的「成交」这一条被测量否证，fills 上挣到 R>=2（另三条 realism 腿
#          —— 事后池、日线止损坍塌、n=2 日历规则 —— 仍然开放，所以只能挣到 2，绝不是 3）
#   BITES：sharpe < 1.0 或 Δobjective < -0.6 ⇒ R=1 由测量确证，本家族继续按证据被拒
#   其余  ⇒ partial：报逐仓 removedFrac 分布，并指出是哪一仓在咬
# ============================================================================
# Clone from JoinQuant
# postId: d02cde29e649c9e8056582149cebf276
# backtestId: 195f89912425ad2135fd7b9cf49687d5
# title: 高质量稳定上涨策略

# 克隆自聚宽文章：https://www.joinquant.com/post/1399
# 标题：【量化课堂】多因子策略入门
# 作者：JoinQuant量化课堂

# 克隆自聚宽文章：https://www.joinquant.com/post/15002
# 标题：价值选股与RSRS择时
# 作者：K线放荡不羁

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import datetime
import math
from datetime import time
import talib
from prettytable import PrettyTable
import warnings
warnings.filterwarnings("ignore")

# ==================== 全局配置 ====================
STRATEGY_ALLOCATION = {
    'etf': 0.4,
    'small_cap': 0.35,
    'white_horse': 0.25
}
# ETF轮动策略配置
ETF_CONFIG = {
    'etf_pool': [
        "513100.XSHG", 
        '159525.XSHE',
        "513130.XSHG", 
        '159915.XSHE',
        '159628.XSHE',
        "588120.XSHG", 
        "513520.XSHG",
        "513030.XSHG", 
        "518880.XSHG",
        "161226.XSHE",
        "159985.XSHE",
        "501018.XSHG",
        "159652.XSHE", 
        "511090.XSHG",
    ],
    'target_num': 1,
    'm25_days': 25,
    'auto_day': True,
    'min_days': 20,
    'max_days': 60,
    'premium_threshold': 5.0
}
# 小市值策略配置
SMALL_CAP_CONFIG = {
    'market_index': '399100.XSHE',
    'stock_num': 6,
    'up_price': 20,
    'pass_april': True,
    'run_stoploss': True,
    'stoploss_strategy': 3,
    'stoploss_limit': 0.91,
    'stoploss_market': 0.95,
    'no_trading_buy': ['600036.XSHG']
}
# 白马策略配置
WHITE_HORSE_CONFIG = {
    'stock_num': 20,
    'max_stock_price': 50,
    'stop_loss_ratio': 0.94,
    'recent_days': 10,
    'buy_stock_count': 20,
    'foreign_etfs': [
        '513520.XSHG', 
        '513100.XSHG', 
        '159934.XSHE',
        '515180.XSHG'
    ]
}
# ==================== q-e9-liq-1: 可成交下限（fill-feasibility floor） ====================
# 全部由 harness epoch 9 推出：costs.capital = 1000000, costs.orderVolumeRatio = 0.05。
# 这两个常量在 JQ 服务器上跑，读不到 harness/config/epoch-9.json，所以是 builder 写进来的
# 字面量；build-e9-liq.js 从 utils/harness-config 读出同一个值并断言，绝不手抄。
LIQ_ORDER_VOLUME_RATIO = 0.05      # harness costs.orderVolumeRatio（由 frozen OVERRIDE 钉住）
LIQ_LOOKBACK = 20                  # 20 bar 中位成交额
LIQ_FLOOR_MULT = 1.0                 # 1.0 = 可成交最小值本身，没有余量，没有自由参数
LIQ_SLOTS = {'small_cap': 6, 'etf': 1, 'white_horse': 20}  # 每仓的槽位数


def liq_floor_for(context, sleeve):
    """逐仓、逐次调用的 DYNAMIC 地板，没有自由参数。

    某仓要在一只标的上建 V 元的仓：
        V = context.portfolio.total_value * STRATEGY_ALLOCATION[sleeve] / LIQ_SLOTS[sleeve]
    一天最多吃掉该标的成交额的 LIQ_ORDER_VOLUME_RATIO，所以要求日成交额 >= V / ratio。
    随净值复利自动放大，不是静态阈值。
    """
    slots = float(max(1, LIQ_SLOTS[sleeve]))
    pos = float(context.portfolio.total_value) * float(STRATEGY_ALLOCATION[sleeve]) / slots
    return pos / float(LIQ_ORDER_VOLUME_RATIO) * float(LIQ_FLOOR_MULT)


def filter_liquidity_floor(context, sleeve, site, stock_list):
    """保留 20 bar 中位日成交额 >= 本仓地板的名字。

    中位数而非均值：一天放量不得放进一只平常没量的标的。
    end_date=context.previous_date ⇒ 今天要成交的那根 bar 永不被查询。
    每次调用打一条 LIQFLOOR 行，用 log.error 以穿过本书的三处 log.set_level。
    """
    stock_list = list(stock_list)
    n_in = len(stock_list)
    floor = liq_floor_for(context, sleeve)
    if n_in == 0:
        log.error('LIQFLOOR sleeve=%s site=%s date=%s floor=%.0f in=0 out=0 removedFrac=NA slots=0 removed=- status=empty' % (
            sleeve, site, str(context.previous_date), floor))
        return []
    try:
        df = get_price(stock_list, count=LIQ_LOOKBACK, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        keep = [s for s in stock_list if (s in med.index) and (med[s] >= floor)]
    except Exception as e:
        # LOUD，绝不静默：静默失败会逐字复现父本，和「地板什么都没剔掉」不可区分 ——
        # 而后者正是 大小盘轮动 / b3751277 的 liq-1 得到的答案，必须可信。
        log.error('LIQFLOOR ERROR sleeve=%s site=%s date=%s floor=%.0f in=%d exc=%s' % (
            sleeve, site, str(context.previous_date), floor, n_in, str(e)))
        return stock_list
    removed = [s for s in stock_list if s not in keep]
    log.error('LIQFLOOR sleeve=%s site=%s date=%s floor=%.0f in=%d out=%d removedFrac=%.4f slots=%d removed=%s status=ok' % (
        sleeve, site, str(context.previous_date), floor, n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(LIQ_SLOTS[sleeve], len(keep)),
        ';'.join(removed) or '-'))
    return keep

# ==================== 初始化函数 ====================
def initialize(context):
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_benchmark('000300.XSHG')
    
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=1/10000, close_commission=1/10000,
        close_today_commission=0, min_commission=5
    ), type='stock')
    
    set_slippage(FixedSlippage(0.0001), type='fund')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.0002, close_commission=0.0002,
        close_today_commission=0, min_commission=1
    ), type='fund')
    
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    
    # ========== 先初始化全局变量 ==========
    init_globals(context)
    
    # ========== 然后再调度任务 ==========
    schedule_tasks(context)
    
    log.info("=" * 80)
    log.info("多策略组合系统初始化完成")
    log.info(f"ETF轮动: {STRATEGY_ALLOCATION['etf']:.0%} | "
             f"小市值: {STRATEGY_ALLOCATION['small_cap']:.0%} | "
             f"白马: {STRATEGY_ALLOCATION['white_horse']:.0%}")
    log.info("=" * 80)

def init_globals(context):
    """初始化全局变量"""
    initial_cash = context.portfolio.starting_cash
    
    # 股票归属追踪
    g.stock_strategy = {}
    
    # 各策略累计净值(包含已实现盈亏)
    g.strategy_value = {
        'etf': initial_cash * STRATEGY_ALLOCATION['etf'],
        'small_cap': initial_cash * STRATEGY_ALLOCATION['small_cap'],
        'white_horse': initial_cash * STRATEGY_ALLOCATION['white_horse']
    }
    
    # 初始资金(用于计算收益率)
    g.strategy_starting_cash = {
        'etf': initial_cash * STRATEGY_ALLOCATION['etf'],
        'small_cap': initial_cash * STRATEGY_ALLOCATION['small_cap'],
        'white_horse': initial_cash * STRATEGY_ALLOCATION['white_horse']
    }
    
    # 各策略持仓列表
    g.strategy_holdings = {
        'etf': [],
        'small_cap': [],
        'white_horse': []
    }
    
    # ETF策略特有变量
    g.etf = {
        'positions': {}
    }
    
    # 小市值策略特有变量
    g.small_cap = {
        'yesterday_hl_list': [],
        'target_list': [],
        'not_buy_again': [],
        'reason_to_sell': '',
        'no_trading_today': False,
        'no_trading_hold_signal': False
    }
    
    # 白马策略特有变量
    g.white_horse = {
        'yesterday_limit_up': [],
        'market_temp': 'warm',
        'signal': 'big',
        'rebound_stocks': {}
    }
def schedule_tasks(context):
    """调度任务"""
    run_daily(daily_prepare, '9:05')
    
    if STRATEGY_ALLOCATION['etf'] > 0:
        run_daily(etf_trade, '9:31')
    
    if STRATEGY_ALLOCATION['small_cap'] > 0:
        run_daily(small_cap_check_no_trading_month, '9:35')
        run_daily(small_cap_stoploss, '10:00')
        run_weekly(small_cap_weekly_adjust, 2, '10:30')
        run_daily(small_cap_check_afternoon, '14:25')
        run_daily(small_cap_check_afternoon, '14:55')
        run_daily(small_cap_close_account, '14:50')
    
    if STRATEGY_ALLOCATION['white_horse'] > 0:
        run_monthly(white_horse_signal, 1, '9:00')
        run_weekly(white_horse_clear_rebound, 5, '9:35')
        run_daily(white_horse_adjust, '9:35')
        run_daily(white_horse_stop_loss, '14:00')
        run_daily(white_horse_stop_loss, '14:30')
        run_daily(white_horse_stop_loss, '14:50')
    
    #run_daily(daily_settlement, '15:00')
def daily_prepare(context):
    """每日开盘前准备"""
    log.info(f"{'='*30}{context.current_dt.strftime('%Y-%m-%d')} 开盘准备{'='*30}")
    
    # 更新持仓列表
    for strategy_name in ['etf', 'small_cap', 'white_horse']:
        g.strategy_holdings[strategy_name] = []
    
    for stock in context.portfolio.positions.keys():
        strategy = g.stock_strategy.get(stock)
        if strategy:
            g.strategy_holdings[strategy].append(stock)
    
    # 小市值：昨日涨停
    if g.strategy_holdings['small_cap']:
        df = get_price(
            g.strategy_holdings['small_cap'],
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1, panel=False, fill_paused=False
        )
        if not df.empty:
            g.small_cap['yesterday_hl_list'] = list(df[df['close'] >= df['high_limit'] * 0.997].code)
    
    g.small_cap['no_trading_today'] = is_no_trading_month(context)

    # 白马：昨日涨停
    if g.strategy_holdings['white_horse']:
        df = get_price(
            g.strategy_holdings['white_horse'],
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1, panel=False, fill_paused=False
        )
        if not df.empty:
            g.white_horse['yesterday_limit_up'] = list(df[df['close'] >= df['high_limit'] * 0.997].code)


# ==================== 策略专用交易函数 ====================
def strategy_open_position(context, strategy_name, security, value):
    """策略买入"""
    # 计算可用资金
    strategy_total = context.portfolio.total_value * STRATEGY_ALLOCATION[strategy_name]
    current_holdings_value = sum([
        context.portfolio.positions[s].value 
        for s in g.strategy_holdings[strategy_name]
        if s in context.portfolio.positions
    ])
    available = max(0, strategy_total - current_holdings_value)
    
    # 调整买入金额
    if value > available:
        value = available * 0.95
    
    current_price = get_current_data()[security].last_price
    if value < current_price * 100:
        return False
    
    order = order_target_value(security, value)
    if order and order.filled > 0:
        g.stock_strategy[security] = strategy_name
        g.strategy_holdings[strategy_name].append(security)
        log.info(f"[{strategy_name}] 买入 {security} 数量:{order.filled} 金额:{value:.0f}")
        return True
    return False
    
def strategy_open_position_add(context, strategy_name, security, value):
    """策略买入(买入)"""
    order = order_value(security, value)
    if order and order.filled > 0:
        g.stock_strategy[security] = strategy_name
        if value > 0:
            g.strategy_holdings[strategy_name].append(security)
        return order
    return order
    
def strategy_close_position(context, strategy_name, position):
    """策略卖出"""
    security = position.security
    order = order_target_value(security, 0)
    
    if order and order.status == OrderStatus.held:
        # 计算已实现盈亏
        pnl = (order.price - order.avg_cost) * order.amount
        g.strategy_value[strategy_name] += pnl
        
        # 清理
        if security in g.stock_strategy:
            del g.stock_strategy[security]
        if security in g.strategy_holdings[strategy_name]:
            g.strategy_holdings[strategy_name].remove(security)
        
        log.info(f"[{strategy_name}] 卖出 {security} 盈亏:{pnl:.2f}")
        return True
    return False


# ==================== ETF轮动策略 ====================
def etf_trade(context):
    """ETF轮动主交易函数"""
    config = ETF_CONFIG
    
    # 获取目标ETF列表
    if config['auto_day']:
        target_list, rank_info = etf_get_rank_auto(context, return_info=True)
        # q-e9-liq-1: 可成交下限，作用在排序后的候选名单上、[:target_num] 切片之前
        target_list = filter_liquidity_floor(context, 'etf', 'rank_auto', target_list)
        target_list = target_list[:config['target_num']]
    else:
        target_list, rank_info = etf_get_rank_fixed(context, return_info=True)
        # q-e9-liq-1: 同上（本书 auto_day=True，这一支不会跑，插上以免两支语义不一致）
        target_list = filter_liquidity_floor(context, 'etf', 'rank_fixed', target_list)
        target_list = target_list[:config['target_num']]
    
    if rank_info:
        log.info("[ETF轮动] 动量评分排行:")
        for i, (etf, score) in enumerate(rank_info[:5], 1):
            etf_name = get_security_info(etf).display_name
            log.info(f"  {i}. {etf} {etf_name:10s} 得分:{score:.4f}")

    if not target_list:
        log.warning("[ETF轮动] 无符合条件的标的")
        return
    
    current_holdings = g.strategy_holdings['etf'][:]
    
    # 卖出不在目标列表的持仓
    for stock in current_holdings:
        if stock not in target_list and stock in context.portfolio.positions:
            pos = context.portfolio.positions[stock]
            strategy_close_position(context, 'etf', pos)
    
    # 买入新标的
    if len(g.strategy_holdings['etf']) < config['target_num']:
        strategy_total = context.portfolio.total_value * STRATEGY_ALLOCATION['etf']
        current_holdings_value = sum([
            context.portfolio.positions[s].value 
            for s in g.strategy_holdings['etf']
            if s in context.portfolio.positions
        ])
        available = max(0, strategy_total - current_holdings_value)
        
        if available > 0 and (config['target_num'] - len(g.strategy_holdings['etf'])) > 0:
            value_per_stock = available / (config['target_num'] - len(g.strategy_holdings['etf']))
            
            for stock in target_list:
                if stock not in g.strategy_holdings['etf']:
                    strategy_open_position(context, 'etf', stock, value_per_stock)
                    if len(g.strategy_holdings['etf']) >= config['target_num']:
                        break

def etf_get_rank_fixed(context, return_info=False):
    """固定周期动量评分"""
    config = ETF_CONFIG
    data = pd.DataFrame(index=config['etf_pool'], 
                       columns=["annualized_returns", "r2", "score"])
    current_data = get_current_data()
    
    for etf in config['etf_pool']:
        try:
            df = attribute_history(etf, config['m25_days'], "1d", ["close", "high"])
            if len(df) < config['m25_days']:
                continue
            
            prices = np.append(df["close"].values, current_data[etf].last_price)
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1
            
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0
            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]
            
            if len(prices) >= 4:
                if min(prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]) < 0.95:
                    data.loc[etf, "score"] = 0
            
            premium_rate = get_etf_premium_rate(context, etf)
            if premium_rate >= config['premium_threshold']:
                data.loc[etf, "score"] -= 1
                
        except Exception as e:
            continue
    
    data = data.query("0 < score < 6").sort_values(by="score", ascending=False)
    
    if return_info:
        rank_info = [(idx, row['score']) for idx, row in data.iterrows()]
        return data.index.tolist(), rank_info
    return data.index.tolist()

def etf_get_rank_auto(context, return_info=False):
    """动态周期动量评分（基于波动率）"""
    config = ETF_CONFIG
    data = pd.DataFrame(index=config['etf_pool'], 
                       columns=["annualized_returns", "r2", "score"])
    current_data = get_current_data()
    
    for etf in config['etf_pool']:
        try:
            df = attribute_history(etf, config['max_days']+10, "1d", ["close", "high", "low"])
            
            if len(df) < (config['max_days']+10) or \
               df["low"].isna().sum() > config['max_days'] or \
               df["close"].isna().sum() > config['max_days'] or \
               df["high"].isna().sum() > config['max_days']:
                continue
            
            long_atr = talib.ATR(df["high"], df["low"], df["close"], timeperiod=config['max_days'])
            short_atr = talib.ATR(df["high"], df["low"], df["close"], timeperiod=config['min_days'])
            
            lookback = int(config['min_days'] + 
                          (config['max_days'] - config['min_days']) * 
                          (1 - min(0.9, short_atr[-1]/long_atr[-1])))
            
            prices = np.append(df["close"].values, current_data[etf].last_price)
            prices = prices[-lookback:]
            
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1
            
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0
            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]
            
            con1 = min(prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]) < 0.95
            con2 = (prices[-1] < prices[-2]) & (prices[-2] < prices[-3]) & \
                   (prices[-3] < prices[-4]) & (prices[-1]/prices[-4] < 0.95)
            
            if con1 or con2:
                data.loc[etf, "score"] = 0
            
            premium_rate = get_etf_premium_rate(context, etf)
            if premium_rate >= config['premium_threshold']:
                data.loc[etf, "score"] -= 1
                
        except Exception as e:
            continue
    
    data = data.sort_values(by="score", ascending=False).reset_index()
    data = data.query("0 < score < 6").sort_values(by="score", ascending=False)
    
    if return_info:
        rank_info = [(row['index'], row['score']) for _, row in data.iterrows()]
        return data['index'].tolist(), rank_info
    return data['index'].tolist()

def get_etf_premium_rate(context, etf_code):
    """计算ETF溢价率"""
    try:
        etf_price = get_price(etf_code, start_date=context.previous_date, 
                             end_date=context.previous_date).iloc[-1]['close']
        iopv = get_extras('unit_net_value', etf_code, 
                         start_date=context.previous_date, 
                         end_date=context.previous_date).iloc[-1].values[0]
        
        if iopv is not None and iopv != 0:
            premium_rate = (etf_price - iopv) / iopv * 100
        else:
            premium_rate = 0
        
        return premium_rate
    except Exception as e:
        return 0

# ==================== 小市值399100策略 ====================
def small_cap_weekly_adjust(context):
    """周二调仓"""
    config = SMALL_CAP_CONFIG
    
    # 空仓月份处理
    if g.small_cap['no_trading_today']:
        if len(g.strategy_holdings['small_cap']) > 0 and not g.small_cap['no_trading_hold_signal']:
            for stock in g.strategy_holdings['small_cap'][:]:
                if stock in context.portfolio.positions:
                    pos = context.portfolio.positions[stock]
                    strategy_close_position(context, 'small_cap', pos)
            
            # 买入空仓期持有品种
            small_cap_buy_stocks(context, config['no_trading_buy'])
            g.small_cap['no_trading_hold_signal'] = True
        return
    
    # 正常调仓
    if g.small_cap['no_trading_hold_signal']:
        for stock in g.strategy_holdings['small_cap'][:]:
            if stock in context.portfolio.positions:
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
        g.small_cap['no_trading_hold_signal'] = False
    
    # 清空记录
    g.small_cap['not_buy_again'] = []
    
    # 获取目标股票池
    g.small_cap['target_list'] = small_cap_get_stocks(context)
    target_list = g.small_cap['target_list'][:config['stock_num']*2]
    
    log.info(f"[小市值] 目标池: {target_list}")
    
    # 卖出不在目标池的股票
    for stock in g.strategy_holdings['small_cap'][:]:
        if (stock not in target_list) and (stock not in g.small_cap['yesterday_hl_list']):
            if stock in context.portfolio.positions:
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
                log.info(f"[小市值] 卖出 {stock}")
        else:
            log.info(f"[小市值] 持有 {stock}")
    
    # 买入
    small_cap_buy_stocks(context, target_list)
    
    # 记录已买入
    g.small_cap['not_buy_again'] = g.strategy_holdings['small_cap'][:]


def small_cap_get_stocks(context):
    """小市值选股"""
    config = SMALL_CAP_CONFIG
    
    # 获取指数成分股
    initial_list = get_index_stocks(config['market_index'])
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    
    # 按流通市值排序
    q = query(
        valuation.code
    ).filter(
        valuation.code.in_(initial_list)
    ).order_by(
        valuation.circulating_market_cap.asc()
    ).limit(200)
    initial_list = list(get_fundamentals(q).code)
    
    # 过滤涨跌停
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    
    # 按总市值排序
    q = query(
        valuation.code, 
        indicator.eps
    ).filter(
        valuation.code.in_(initial_list)
    ).order_by(
        valuation.market_cap.asc()
    )
    df = get_fundamentals(q)
    stock_list = list(df.code)[:100]
    
    # 行业分散
    stock_list = small_cap_get_stock_industry(stock_list)
    # q-e9-liq-1: 可成交下限（切片之前 ⇒ 被剔掉的名字由下一名顶上，而不是留空槽）
    stock_list = filter_liquidity_floor(context, 'small_cap', 'get_stocks', stock_list)
    final_list = stock_list[:config['stock_num']*2]
    
    log.info(f'[小市值] 今日前10: {final_list}')
    return final_list

def small_cap_get_stock_industry(stocks):
    """行业分散选股"""
    result = get_industry(security=stocks)
    selected_stocks = []
    industry_list = []
    
    for stock_code, info in result.items():
        industry_name = info['sw_l2']['industry_name']
        if industry_name not in industry_list:
            industry_list.append(industry_name)
            selected_stocks.append(stock_code)
            if len(industry_list) == 10:
                break
    return selected_stocks

def small_cap_check_no_trading_month(context):
    """检查空仓月份并买入指定ETF"""
    if not g.small_cap['no_trading_today']:
        # 非空仓月份，如果持有空仓ETF则清仓
        if g.small_cap['no_trading_hold_signal']:
            no_trading_etf = SMALL_CAP_CONFIG['no_trading_buy']
            for etf in no_trading_etf:
                if etf in g.strategy_holdings['small_cap'] and etf in context.portfolio.positions:
                    pos = context.portfolio.positions[etf]
                    strategy_close_position(context, 'small_cap', pos)
                    log.info(f"[小市值] 退出空仓月份，卖出 {etf}")
            g.small_cap['no_trading_hold_signal'] = False
        return
    
    # 空仓月份逻辑
    no_trading_etf = SMALL_CAP_CONFIG['no_trading_buy']
    has_no_trading_etf = False
    for etf in no_trading_etf:
        if etf in g.strategy_holdings['small_cap']:
            has_no_trading_etf = True
            break

    # 如果没有持有空仓期ETF，则买入
    if not has_no_trading_etf:
        log.info("[小市值] 空仓月份，买入指定ETF")
        small_cap_buy_stocks(context, no_trading_etf)
        g.small_cap['no_trading_hold_signal'] = True



def small_cap_buy_stocks(context, target_list, cash=0, buy_number=0):
    """小市值买入"""
    config = SMALL_CAP_CONFIG
    
    position_count = len(g.strategy_holdings['small_cap'])
    target_num = config['stock_num']
    
    # 筛选符合条件的股票
    qualified_stocks = [s for s in target_list if s not in g.strategy_holdings['small_cap']]
    if not qualified_stocks:
        return
    
    # ✅ 计算可用资金
    if cash == 0:
        strategy_total = context.portfolio.total_value * STRATEGY_ALLOCATION['small_cap']
        current_holdings_value = sum([
            context.portfolio.positions[s].value 
            for s in g.strategy_holdings['small_cap']
            if s in context.portfolio.positions
        ])
        cash = max(0, strategy_total - current_holdings_value)
    
    if buy_number == 0:
        buy_number = target_num
    
    bought_num = 0
    
    if target_num > position_count and cash > 0:
        value = cash / (target_num - position_count)
        for stock in qualified_stocks:
            if stock not in g.strategy_holdings['small_cap']:
                if bought_num < buy_number:
                    if strategy_open_position(context, 'small_cap', stock, value):
                        g.small_cap['not_buy_again'].append(stock)
                        bought_num += 1
                        if len(g.strategy_holdings['small_cap']) == target_num:
                            break

def small_cap_stoploss(context):
    """小市值止损"""
    strategy = g.small_cap
    config = SMALL_CAP_CONFIG
    
    if not config['run_stoploss']:
        return
    
    stoploss_type = config['stoploss_strategy']
    stock_df = get_price(
        security=get_index_stocks(config['market_index']),
        end_date=context.previous_date,
        frequency='daily',
        fields=['close', 'open'],
        count=1, panel=False
    )
    down_ratio = (stock_df['close'] / stock_df['open']).mean()
    
    if down_ratio <= config['stoploss_market']:
        strategy['reason_to_sell'] = 'stoploss'
        log.info(f"[小市值] 大盘惨跌 {down_ratio:.2%}")
        for stock in g.strategy_holdings['small_cap'][:]:
            if stock in context.portfolio.positions:
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
    else:
        for stock in g.strategy_holdings['small_cap'][:]:
            pos = context.portfolio.positions[stock]
            
            if pos.avg_cost <= 0:
                log.warning(f"[小市值] {stock} 持仓成本为0，跳过")
                continue
            
            if pos.price < pos.avg_cost * config['stoploss_limit']:
                strategy_close_position(context, 'small_cap', pos)
                log.info(f"[小市值] 止损 {stock}")
                strategy['reason_to_sell'] = 'stoploss'



def small_cap_check_afternoon(context):
    """小市值下午检查"""
    strategy = g.small_cap
    
    if strategy['no_trading_today']:
        return
    
    small_cap_check_limit_up(context)
    small_cap_check_remain(context)
    
def small_cap_check_limit_up(context):
    """检查涨停股"""
    strategy = g.small_cap
    now_time = context.current_dt
    
    if not strategy['yesterday_hl_list']:
        return
    
    for stock in strategy['yesterday_hl_list'][:]:
        if stock not in g.strategy_holdings['small_cap']:
            continue
        
        if stock not in context.portfolio.positions:
            continue
        
        pos = context.portfolio.positions[stock]
        if pos.closeable_amount <= 0:
            continue
        
        current_data = get_price(
            stock, end_date=now_time,
            frequency='1m', fields=['close', 'high_limit'],
            count=1, panel=False, fill_paused=True
        )
        
        if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
            log.info(f"[小市值] 涨停打开 {stock}")
            strategy_close_position(context, 'small_cap', pos)
            strategy['reason_to_sell'] = 'limitup'

def small_cap_check_remain(context):
    """检查余额补仓"""
    strategy = g.small_cap
    config = SMALL_CAP_CONFIG
    
    if strategy['reason_to_sell'] == 'limitup':
        if len(g.strategy_holdings['small_cap']) < config['stock_num']:
            target_list = small_cap_get_stocks(context)
            target_list = [s for s in target_list if s not in strategy['not_buy_again']]
            target_list = target_list[:min(config['stock_num'], len(target_list))]
            log.info(f"[小市值] 补仓 {target_list}")
            small_cap_buy_stocks(context, target_list)
        
        strategy['reason_to_sell'] = ''
    else:
        strategy['reason_to_sell'] = ''

def small_cap_close_account(context):
    """小市值清仓检查"""
    strategy = g.small_cap
    
    if not strategy['no_trading_today']:
        return
    
    if len(g.strategy_holdings['small_cap']) > 0:
        for stock in g.strategy_holdings['small_cap'][:]:
            if stock in context.portfolio.positions:
                if stock in SMALL_CAP_CONFIG['no_trading_buy']:
                    continue
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'small_cap', pos)
        
        # 买入空仓期持有品种
        if SMALL_CAP_CONFIG['no_trading_buy']:
            small_cap_buy_stocks(context, SMALL_CAP_CONFIG['no_trading_buy'])


def small_cap_prepare(context):
    """小市值准备（已在daily_prepare中处理）"""
    pass


# ==================== 大小择时白马策略 ====================

def white_horse_prepare(context):
    """白马策略准备（已在daily_prepare中处理）"""
    pass

def white_horse_signal(context):
    """白马策略月度信号生成"""
    strategy = g.white_horse
    config = WHITE_HORSE_CONFIG
    
    today = context.current_dt
    dt_last = context.previous_date
    N = config['recent_days']
    
    # 获取大盘股(沪深300前20)
    B_stocks = get_index_stocks('000300.XSHG', dt_last)
    B_stocks = filter_kcbj_stock(B_stocks)
    B_stocks = filter_st_stock(B_stocks)
    B_stocks = filter_new_stock(context, B_stocks)
    
    q = query(
        valuation.code, 
        valuation.circulating_market_cap
    ).filter(
        valuation.code.in_(B_stocks)
    ).order_by(
        valuation.circulating_market_cap.desc()
    ).limit(20)
    Blst = list(get_fundamentals(q).code)
    
    # 获取小盘股(创业板指后20)
    S_stocks = get_index_stocks('399101.XSHE', dt_last)
    S_stocks = filter_kcbj_stock(S_stocks)
    S_stocks = filter_st_stock(S_stocks)
    S_stocks = filter_new_stock(context, S_stocks)
    
    q = query(
        valuation.code, 
        valuation.circulating_market_cap
    ).filter(
        valuation.code.in_(S_stocks)
    ).order_by(
        valuation.circulating_market_cap.asc()
    ).limit(20)
    Slst = list(get_fundamentals(q).code)
    
    # 计算大盘股表现
    B_ratio = get_price(Blst, end_date=dt_last, frequency='1d', 
                       fields=['close'], count=N, panel=False)
    B_ratio = B_ratio.pivot(index='time', columns='code', values='close')
    change_BIG = (B_ratio.iloc[-1] / B_ratio.iloc[0] - 1) * 100
    A1 = np.array(change_BIG)
    A1 = np.nan_to_num(A1)
    B_mean = np.mean(A1)
    
    # 计算小盘股表现
    S_ratio = get_price(Slst, end_date=dt_last, frequency='1d', 
                       fields=['close'], count=N, panel=False)
    S_ratio = S_ratio.pivot(index='time', columns='code', values='close')
    change_SMALL = (S_ratio.iloc[-1] / S_ratio.iloc[0] - 1) * 100
    A1 = np.array(change_SMALL)
    A1 = np.nan_to_num(A1)
    S_mean = np.mean(A1)
    
    # 信号判断
    old_signal = strategy['signal']
    if B_mean > S_mean and B_mean > 0:
        if B_mean > 5:
            strategy['signal'] = 'small'
            log.info('[白马] 大市值到头，切换小盘')
        else:
            strategy['signal'] = 'big'
            log.info('[白马] 大盘占优')
    elif B_mean < S_mean and S_mean > 0:
        strategy['signal'] = 'small'
        log.info('[白马] 小盘占优')
    else:
        log.info('[白马] 切换外盘ETF')
        strategy['signal'] = 'etf'
    
    if old_signal != strategy['signal']:
        log.info(f"[白马] 信号变化: {old_signal} -> {strategy['signal']}")

def white_horse_adjust(context):
    """白马策略调仓"""
    strategy = g.white_horse
    config = WHITE_HORSE_CONFIG
    
    # 根据信号选股
    if strategy['signal'] == 'big':
        target_list = white_horse_select_big(context)
    elif strategy['signal'] == 'small':
        target_list = white_horse_select_small(context)
    else:
        target_list = config['foreign_etfs']
    
    # 过滤
    target_list = filter_limitup_stock(context, target_list)
    target_list = filter_limitdown_stock(context, target_list)
    target_list = filter_paused_stock(target_list)
    
    for stock in g.strategy_holdings['white_horse'][:]:
        if (stock not in target_list) and (stock not in strategy['yesterday_limit_up']):
            if stock in context.portfolio.positions:
                position = context.portfolio.positions[stock]
                strategy_close_position(context, 'white_horse', position)
    
    # 买入逻辑
    position_count = len(g.strategy_holdings['white_horse'])
    target_buy_count = config['buy_stock_count'] - position_count
    
    if target_buy_count > 0:
        strategy_total = context.portfolio.total_value * STRATEGY_ALLOCATION['white_horse']
        current_holdings_value = sum([
            context.portfolio.positions[s].value 
            for s in g.strategy_holdings['white_horse']
            if s in context.portfolio.positions
        ])
        available = max(0, strategy_total - current_holdings_value)
        if available > 0:
            value_per_stock = available / target_buy_count
            bought_count = 0
            log.info(f"[白马] 可用金额: {available} ，每只股票分配资金：{value_per_stock} 当前持仓 {current_holdings_value}")
            for stock in target_list:
                if stock not in g.strategy_holdings['white_horse']:
                    if strategy_open_position_add(context, 'white_horse', stock, value_per_stock):
                        bought_count += 1
                        if bought_count >= target_buy_count:
                            break



def white_horse_select_big(context):
    """白马股选股（大盘）"""
    strategy = g.white_horse
    config = WHITE_HORSE_CONFIG
    
    white_horse_assess_market_temp(context)
    all_stocks = get_index_stocks("000300.XSHG")
    
    # 基础过滤
    all_stocks = [s for s in all_stocks if not (
        get_current_data()[s].paused or
        get_current_data()[s].is_st or
        'ST' in get_current_data()[s].name or
        '*' in get_current_data()[s].name or
        '退' in get_current_data()[s].name or
        s.startswith(('30', '68', '8', '4'))
    )]
    
    if strategy['market_temp'] == "cold":
        q = query(
            valuation.code
        ).filter(
            valuation.pb_ratio.between(0, 1),
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit > 2.0,
            indicator.inc_return > 1.5,
            indicator.inc_net_profit_year_on_year > -15,
            valuation.code.in_(all_stocks)
        ).order_by(
            (indicator.roa/valuation.pb_ratio).desc()
        ).limit(config['stock_num'] + 1)
    
    elif strategy['market_temp'] == "warm":
        q = query(
            valuation.code
        ).filter(
            valuation.pb_ratio.between(0, 1),
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit > 1.0,
            indicator.inc_return > 2.0,
            indicator.inc_net_profit_year_on_year > 0,
            valuation.code.in_(all_stocks)
        ).order_by(
            (indicator.roa/valuation.pb_ratio).desc()
        ).limit(config['stock_num'] + 1)
    
    else:  # hot
        q = query(
            valuation.code
        ).filter(
            valuation.pb_ratio > 3,
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit > 0.5,
            indicator.inc_return > 3.0,
            indicator.inc_net_profit_year_on_year > 20,
            valuation.code.in_(all_stocks)
        ).order_by(
            indicator.roa.desc()
        ).limit(config['stock_num'] + 1)
    
    # q-e9-liq-1: 可成交下限
    return filter_liquidity_floor(context, 'white_horse', 'select_big', list(get_fundamentals(q).code))

def white_horse_select_small(context):
    """小盘股选股"""
    config = WHITE_HORSE_CONFIG
    
    stocks = get_index_stocks('399101.XSHE')
    stocks = filter_kcbj_stock(stocks)
    stocks = filter_st_stock(stocks)
    stocks = filter_new_stock(context, stocks)
    
    # 两步选股法
    q1 = query(
        valuation.code, 
        valuation.market_cap
    ).filter(
        valuation.code.in_(stocks),
        valuation.market_cap.between(5, 60)
    ).order_by(
        valuation.market_cap.asc()
    ).limit(100)
    df_fun = get_fundamentals(q1)
    initial_list = list(df_fun.code)
    
    q2 = query(
        valuation.code, 
        valuation.market_cap
    ).filter(
        valuation.code.in_(initial_list)
    ).order_by(
        valuation.market_cap.asc()
    ).limit(50)
    df_fun = get_fundamentals(q2)
    final_list = list(df_fun.code)
    
    # 价格过滤
    current_data = get_current_data()
    # q-e9-liq-1: 可成交下限
    return filter_liquidity_floor(context, 'white_horse', 'select_small', [s for s in final_list 
           if s in context.portfolio.positions or current_data[s].last_price <= config['max_stock_price']])

def white_horse_assess_market_temp(context):
    """市场温度评估"""
    strategy = g.white_horse
    
    index300 = attribute_history('000300.XSHG', 220, '1d', ('close'), df=False)['close']
    market_height = (np.mean(index300[-5:]) - min(index300)) / (max(index300) - min(index300))
    
    old_temp = strategy['market_temp']
    if market_height < 0.20:
        strategy['market_temp'] = "cold"
    elif market_height > 0.90:
        strategy['market_temp'] = "hot"
    elif max(index300[-60:]) / min(index300) > 1.20:
        strategy['market_temp'] = "warm"
    
    if old_temp != strategy['market_temp']:
        log.info(f"[白马] 市场温度: {old_temp} -> {strategy['market_temp']}")
    
    if context.run_params.type != 'sim_trade':
        temp_value = 200 if strategy['market_temp'] == "cold" else \
                    300 if strategy['market_temp'] == "warm" else 400

def white_horse_stop_loss(context):
    """白马策略止损"""
    strategy = g.white_horse
    config = WHITE_HORSE_CONFIG
    
    num = 0
    now_time = context.current_dt
    
    current_hold_list = g.strategy_holdings['white_horse'][:]
    current_limit_up_list = strategy['yesterday_limit_up'][:]
    
    # 检查昨日涨停股
    if current_limit_up_list:
        for stock in current_limit_up_list:
            if stock not in context.portfolio.positions:
                continue
            
            current_data = get_price(stock, end_date=now_time, frequency='1m',
                                   fields=['close', 'high_limit'], count=1, panel=False)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                log.info(f"[白马] 涨停打开 {stock}")
                pos = context.portfolio.positions[stock]
                strategy_close_position(context, 'white_horse', pos)
                num += 1
    
    # 普通止损
    SS = []
    S = []
    for stock in current_hold_list:
        if stock not in context.portfolio.positions:
            continue
        
        pos = context.portfolio.positions[stock]
        
        if pos.avg_cost <= 0:
            log.warning(f"[白马] {stock} 持仓成本为0，跳过止损检查")
            continue
        
        if pos.price < pos.avg_cost * config['stop_loss_ratio']:
            strategy_close_position(context, 'white_horse', pos)
            log.info(f"[白马] 止损 {stock}")
            num += 1
        else:
            S.append(stock)
            ret = (pos.price - pos.avg_cost) / pos.avg_cost
            SS.append(ret)
    
    # ========== 补跌逻辑 ==========
    if num >= 1 and len(SS) > 0:
        rebound_num = min(3, len(SS))
        worst = sorted(zip(SS, S))[:rebound_num]
        
        # 计算可用现金
        total_available_cash = context.portfolio.available_cash
        strategy_available_cash = total_available_cash * STRATEGY_ALLOCATION['white_horse']
        
        if strategy_available_cash > 0:
            cash_per_stock = strategy_available_cash / rebound_num
            for perf, stock in worst:
                if stock not in strategy['rebound_stocks']:
                    # 记录补跌前的持仓数量
                    pos = context.portfolio.positions[stock]
                    original_amount = pos.total_amount
                    
                    order = strategy_open_position_add(context,'white_horse', stock, cash_per_stock)
                    if order and order.filled > 0:
                        # 记录补跌增加的数量（而非金额）
                        added_amount = order.filled
                        strategy['rebound_stocks'][stock] = {
                            'original_amount': original_amount,
                            'added_amount': added_amount
                        }
                        log.info(f"[白马] 补跌买入 {stock} 数量:{added_amount} 金额:{cash_per_stock:.0f}")


def white_horse_clear_rebound(context):
    """清理补跌股票"""
    strategy = g.white_horse
    
    if strategy['rebound_stocks']:
        strategy['rebound_stocks'].clear()
        
        
# ==================== 通用工具函数 ====================
def filter_new_stock(context, stock_list):
    """过滤次新股"""
    yesterday = context.previous_date
    return [stock for stock in stock_list 
           if (yesterday - get_security_info(stock).start_date) >= datetime.timedelta(days=375)]

def filter_kcbj_stock(stock_list):
    """过滤科创北交股票"""
    return [s for s in stock_list if not s.startswith(('30', '68', '8', '4'))]

def filter_st_stock(stock_list):
    """过滤ST股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list
           if not current_data[stock].is_st
           and 'ST' not in current_data[stock].name
           and '*' not in current_data[stock].name
           and '退' not in current_data[stock].name]

def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_limitup_stock(context, stock_list):
    """过滤涨停股票"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list 
           if stock in context.portfolio.positions.keys()
           or last_prices[stock][-1] < current_data[stock].high_limit]

def filter_limitdown_stock(context, stock_list):
    """过滤跌停股票"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list 
           if stock in context.portfolio.positions.keys()
           or last_prices[stock][-1] > current_data[stock].low_limit]

def is_no_trading_month(context):
    """判断是否为空仓月份"""
    if not SMALL_CAP_CONFIG['pass_april']:
        return False
    today = context.current_dt.strftime('%m-%d')
    return (('04-01' <= today <= '04-30') or 
            ('01-01' <= today <= '01-30'))


# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====
