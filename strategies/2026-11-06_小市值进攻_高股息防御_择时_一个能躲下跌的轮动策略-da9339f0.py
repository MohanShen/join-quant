# Clone from JoinQuant
# postId: da9339f07e1d35b1679564178864878b
# backtestId: 917b155a01b51ac286bb7c444ae91b58
# title: 小市值进攻 + 高股息防御，择时：一个能躲下跌的轮动策略

# -*- coding: utf-8 -*-
"""
聚宽策略：小狮子择时 + 小市值进攻 / 高股息低波动防御（融合版）

【整体逻辑】
  1) 每个交易日 9:30 用「中小板综指 399101 收盘价 vs MA20」判断方向（取到上一交易日，无未来函数）；
  2) 看多 → 进攻端：小市值轮动（默认 100 只，每 5 个交易日调仓）；
  3) 看空 → 防御端：高股息 + 低波动 + 行业分散（默认 10 只，每 60 自然日调仓）；
  4) 信号翻转时全仓切换；切换当天卖不掉的（停牌/跌停）记入待清残仓，之后每日重试。

【原始出处】
  进攻端：开心果《持仓95只大容量小市值，媲美金元顺安元启》
          https://www.joinquant.com/post/39814
  择时：  「小狮子」系列择时（社区共识包括一四月空仓、399101 均线等）
          https://www.joinquant.com/post/63762

【融合时的关键改动】
  - 两端原本都用 g.stock_num / g.last_rebalance_date / g.high_limit_list，直接拼会互相覆盖，
    已统一改为 atk_ / def_ 前缀。
  - 统一成本口径：印花税按 2023-08-28 减半后的 0.05%，佣金万1，滑点统一为百分比滑点。
  - 修复「年内多次分红只取首笔」与「单只标的取不到收盘价序列」两处缺陷。

【绩效优化版改动（针对回测短板：回撤 23.4% / 夏普 0.73 / 胜率 0.42）】
  1. 择时加滞后带（1%）+ 双向连续 2 日确认：均线附近的反复横跳切换减半；
  2. 急跌熔断：399101 单日跌 4% 或 5 日累跌 7% 当日即切防御，不等 MA20 慢信号，
     专治 2026/02~06 微盘危机这类快跌；
  3. 进攻端排名缓冲（1.5 倍）：持仓仍进前 1.5×目标数排名就不卖，换手大幅下降，
     费后收益与胜率同步改善；
  4. 流动性过滤：候选池剔除近 5 日日均成交额 < 2000 万的袖珍票，降低滑点与踩踏风险。

【V3 改动（依据 2022-01~2026-09 交易记录 position.csv 归因）】
  归因结论：防御端占 54% 交易日但年化仅 5%、波动 17%（普跌中高股息照样跌）；
  攻防切换 49 次（2026 年 9 次），典型假翻多：切回进攻后 5 日 -4%~-6%。
  1. 防御端仓位改革：股票只占总资产 60%（def_position_ratio），其余买 511010 国债 ETF，
     防御端波动约减半，普跌段不再"防御端照样大亏"；
  2. 翻多加严（不对称门槛）：升破 MA20×(1+2%) 连续 3 日才翻多（翻空仍为跌破 1% 下方 2 日），
     拦截交易记录中反复出现的假翻多；
  3. 切换冷却期 10 个交易日（急跌熔断不受限），全仓切换频率再砍一半；
  4. 进攻端排名缓冲 1.5 倍 → 2.0 倍，换手进一步下降。

⚠️ 下方「内置函数还原」6 行不可删除：from jqdata import * 会把 numpy 的
   sum/max/min/abs/round/all/any 带进全局、遮蔽 Python 内置函数，
   其中 max/min 被遮蔽后 max(a, b) 会抛 AxisError，且不报错时结果也会错。
"""

from jqdata import *
from jqdata import finance, get_trade_days   # 这两个不在 import * 的导出里，必须具名导入

import builtins as _builtins
sum = _builtins.sum
max = _builtins.max
min = _builtins.min
abs = _builtins.abs
round = _builtins.round
all = _builtins.all
any = _builtins.any
sorted = _builtins.sorted

import numpy as np
import pandas as pd
import datetime as dt


# =====================================================================
# 初始化
# =====================================================================
def initialize(context):
    log.set_level('order', 'error')

    # ---------- 引擎级设置 ----------
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    # 统一费率：佣金万1，印花税 0.05%（2023-08-28 减半后，仅卖出单边），无最低佣金
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                             open_commission=0.0001, close_commission=0.0001,
                             close_today_commission=0, min_commission=0),
                   type='stock')
    set_slippage(PriceRelatedSlippage(0.002))

    # ---------- 择时参数 ----------
    g.timing_index = '399101.XSHE'  # 中小板综指
    g.ma_window = 20                # 均线窗口（交易日）
    g.ma_buffer = 0.01              # 翻空缓冲带：跌破 MA*(1-b) 才计翻空天数
    g.ma_confirm_days = 2           # 连续 N 日收于翻空带下方才确认看空
    g.reentry_buffer = 0.02         # 翻多缓冲带（比翻空更严）：升破 MA*(1+2%) 才计翻多天数，
                                    # 针对交易记录中"切回进攻后 5 日 -4%~-6%"的假翻多
    g.reentry_confirm_days = 3      # 连续 N 日收于翻多带上方才翻多
    g.switch_cooldown = 10          # 切换冷却期（交易日）：两次切换最少间隔，急跌熔断不受限
    g.crash_drop_1d = 0.04          # 急跌熔断：指数单日跌幅 >= 4% 立即切防御
    g.crash_drop_5d = 0.07          # 急跌熔断：指数 5 日累计跌幅 >= 7% 立即切防御
    g.risk_off = False              # 当前方向是否看空（每日 9:30 更新）
    g.below_days = 0                # 连续收于翻空带下方的天数
    g.above_days = 0                # 连续收于翻多带上方的天数（翻多计数器）

    # ---------- 进攻端（小市值）参数 ----------
    # 持仓数随资金自适应：A 股一手 100 股，若本金不足却硬扛 100 只，
    # 单只金额会低于一手价格、一只都买不进（如 10 万 ÷ 100 = 1000 元/只）。
    g.atk_stock_num_max = 20       # 持仓数上限（资金充足时）
    g.atk_stock_num_min = 3         # 持仓数下限
    g.atk_per_stock_min = 5000      # 单只最小目标金额（元）：10万→约19只，100万→100只
    g.atk_min_mv = 10               # 市值下限（亿元）
    g.atk_cash_buffer = 0.02        # 现金缓冲，覆盖手续费与滑点
    g.atk_ocf_threshold = 5         # 经营现金流/营业利润 阈值，单位 %
    g.atk_rebal_days = 5            # 每 n 个交易日调仓一次
    g.atk_keep_ratio = 2.0          # 排名缓冲区倍数：已持仓股只要还在目标数 2 倍的排名内就不卖
    g.atk_min_money = 2000 * 10000  # 流动性下限：近 5 日日均成交额（元），剔除成交冷清的袖珍票

    # ---------- 防御端（高股息+低波动+行业分散）参数 ----------
    # 交易记录归因：防御端年化仅 5% 但波动 17%（高股息股在普跌中照样跌），
    # 故股票仓位降至 def_position_ratio，剩余资金买国债 ETF 做真正的防御底仓
    g.def_position_ratio = 0.6      # 防御端股票总仓位（占总资产比例）
    g.def_cash_asset = '511010.XSHG'  # 剩余资金买入的防御底仓（国债 ETF）
    g.def_stock_num = 10            # 目标持仓数量
    g.def_rebal_days = 60           # 调仓间隔（自然日）
    g.def_min_trade_value = 5000    # 单只买入额度低于此值视为碎片，跳过
    g.industry_pct = 0.25           # 单一一级行业持仓数占比上限（industry_neutral=False 时生效）
    g.min_list_days = 365           # 上市天数下限
    g.dy_top_n = 200                # 股息率排名取前 N
    g.dy_max = 0.15                 # 股息率上限（0.15 = 15%）
    g.rel_window = 120              # 相对涨幅窗口（交易日）
    g.vol_window = 250              # 波动率窗口（交易日）
    # 质量过滤：剔除伪高股息 / 借钱分红 / 周期顶部
    g.min_roe = 0.0                 # ROE 下限（%）
    g.max_debt_ratio = 70.0         # 资产负债率上限（%）
    g.min_ocf_to_profit = 0.8       # 经营现金流/净利润 下限
    g.div_cont_years = 3            # 连续分红考察年数
    g.div_drop_ratio = 0.5          # 最近年度分红不低于上年的该比例，否则视为骤降
    # 降换手
    g.keep_num = 25                 # 已持仓且仍排进前 keep_num 名的锁定不卖
    g.min_hold_days = 60            # 买入后至少锁定天数
    g.industry_neutral = True       # True 按行业等权轮转分配名额
    g.check_profit_decline = True   # 剔除近 3 年净利润连续下滑
    # 板块剔除开关
    g.exclude_st = True
    g.exclude_bj = True
    g.exclude_kcb = False
    g.exclude_cyb = False

    # ---------- 状态 ----------
    g.mode = None                   # 当前模式：'attack' / 'defense'
    g.stale_codes = []              # 切换时未卖出的残仓，每日重试
    g.atk_last_rebal = None         # 上次进攻端调仓日
    g.atk_high_limit_list = []      # 昨日涨停且当日未停牌的进攻端持仓
    g.pending_refill = 0            # 进攻端待补仓数量
    g.def_last_rebal = None         # 上次防御端调仓日
    g.last_switch_day = None        # 上次攻防切换日（用于冷却期）
    g.def_hold_start = {}           # 防御端：code -> 首次买入日期
    g.def_target = []               # 防御端最近一次的目标池（用于残仓补回）
    g.today_bought = 0              # 当日买入只数
    g.today_limit_sold = 0          # 当日涨停打开卖出只数

    run_daily(prepare_stock_list, time='9:05')
    run_daily(open_trade, time='9:30')
    run_daily(check_limit_up, time='14:00')
    run_daily(after_market_close, time='after_close')


# =====================================================================
# 一、择时与主入口
# =====================================================================
def open_trade(context):
    """每日 9:30 统一入口：先更新择时信号，再按当前模式推进"""
    g.today_bought = 0
    g.today_limit_sold = 0

    update_timing(context)
    cleared = sanitize_stale(context)     # 先清切换残留

    want = 'defense' if g.risk_off else 'attack'
    if g.mode != want:
        switch_mode(context, want)
        return

    # 残仓刚被清掉会留出资金缺口，立刻补回，避免干等到下一次调仓
    if cleared > 0:
        if g.mode == 'attack':
            g.pending_refill += cleared
        elif g.def_target:
            rebalance_portfolio(context, g.def_target, g.def_stock_num)

    if g.mode == 'attack':
        attack_daily(context)
    else:
        defense_daily(context)


def update_timing(context):
    """
    399101 收盘价 vs MA20 的状态机更新（每日只调用一次），不对称门槛 + 冷却期：
      - 翻空（进攻→防御）：连续 ma_confirm_days 日收于 MA*(1-翻空带) 下方，
        或触发急跌熔断（熔断不受冷却期限制）；
      - 翻多（防御→进攻）：连续 reentry_confirm_days 日收于 MA*(1+翻多带) 上方，
        且距上次切换 >= switch_cooldown 个交易日；
      - 翻多比翻空难，是针对交易记录中"假翻多 → 切回进攻就挨打"的核心修正。
    """
    px = get_price(g.timing_index, end_date=context.previous_date,
                   count=g.ma_window + 6, frequency='daily',
                   fields=['close'], fq='pre', panel=False)
    s = get_close_series(px, g.timing_index)
    if s is None or len(s) < g.ma_window + 1:
        g.risk_off = False           # 数据不足时不臆断，保持进攻
        g.below_days = 0
        g.above_days = 0
        return
    ma = s.iloc[-g.ma_window:].mean()
    close = s.iloc[-1]
    ret_1d = close / s.iloc[-2] - 1.0
    ret_5d = close / s.iloc[-6] - 1.0 if len(s) >= 6 else 0.0

    # 冷却期：距上次切换不足 switch_cooldown 个交易日则不允许常规翻转
    cool_ok = True
    if g.last_switch_day is not None:
        days = len(get_trade_days(start_date=g.last_switch_day,
                                  end_date=context.current_dt.date())) - 1
        cool_ok = days >= g.switch_cooldown

    if g.risk_off:
        # 空头状态：只认"升破翻多上沿且满确认天数 + 过冷却期"的翻多信号
        if close > ma * (1 + g.reentry_buffer):
            g.above_days += 1
        else:
            g.above_days = 0
        if g.above_days >= g.reentry_confirm_days and cool_ok:
            g.risk_off = False
            g.below_days = 0
            g.last_switch_day = context.current_dt.date()
            log.info('择时翻转：连续 %d 日升破 MA%d 上沿(+%.0f%%) → 看多（进攻）'
                     % (g.above_days, g.ma_window, g.reentry_buffer * 100))
    else:
        # 多头状态：跌破翻空下沿计数 + 急跌熔断
        below = close < ma * (1 - g.ma_buffer)
        g.below_days = g.below_days + 1 if below else 0
        crash = (ret_1d <= -g.crash_drop_1d) or (ret_5d <= -g.crash_drop_5d)
        if (g.below_days >= g.ma_confirm_days and cool_ok) or crash:
            g.risk_off = True
            g.above_days = 0
            g.last_switch_day = context.current_dt.date()
            if crash and not (g.below_days >= g.ma_confirm_days and cool_ok):
                log.info('择时熔断：单日 %.2f%% / 5日 %.2f%% → 看空（防御，熔断不受冷却限制）'
                         % (ret_1d * 100, ret_5d * 100))
    tag = '看空（防御）' if g.risk_off else '看多（进攻）'
    log.info('择时：%s 收盘 %.2f，MA%d %.2f，下方 %d 日 / 上方 %d 日 → %s'
             % (g.timing_index, close, g.ma_window, ma,
                g.below_days, g.above_days, tag))


def switch_mode(context, want):
    """全仓切换：清空现有持仓，再按新的一端建仓"""
    log.info('★ 择时信号翻转：%s → %s' % (g.mode, want))

    g.stale_codes = []
    for code in list(context.portfolio.positions.keys()):
        cd = get_current_data()[code]
        if cd.paused or cd.last_price <= cd.low_limit:
            g.stale_codes.append(code)      # 停牌 / 跌停卖不出，次日重试
            continue
        order_target_value(code, 0)
        if code in context.portfolio.positions:   # 确认成交
            g.stale_codes.append(code)

    g.mode = want
    g.pending_refill = 0
    g.atk_high_limit_list = []

    if g.stale_codes:
        log.info('切换时未能卖出 %d 只（停牌/跌停），次日继续尝试：%s'
                 % (len(g.stale_codes), g.stale_codes))

    if want == 'attack':
        g.atk_last_rebal = context.current_dt.date()
        my_Trader(context)
    else:
        defense_daily(context, force=True)


def sanitize_stale(context):
    """每日重试卖出切换时没卖掉的残仓，返回本次成功卖出的只数"""
    if not g.stale_codes:
        return 0
    still = []
    cleared = 0
    for code in g.stale_codes:
        if code not in context.portfolio.positions:
            continue
        cd = get_current_data()[code]
        if cd.paused or cd.last_price <= cd.low_limit:
            still.append(code)
            continue
        order_target_value(code, 0)
        if code in context.portfolio.positions:
            still.append(code)
        else:
            cleared += 1
    if cleared > 0:
        log.info('残仓清理：卖出 %d 只，剩余 %d 只' % (cleared, len(still)))
    g.stale_codes = still
    return cleared


# =====================================================================
# 二、进攻端：小市值轮动
# =====================================================================
def atk_target_num(context):
    """进攻端目标持仓数：随总资产自适应，保证单只金额不低于 atk_per_stock_min"""
    budget = context.portfolio.total_value * (1 - g.atk_cash_buffer)
    n = int(budget / g.atk_per_stock_min)
    if n < g.atk_stock_num_min:
        n = g.atk_stock_num_min
    if n > g.atk_stock_num_max:
        n = g.atk_stock_num_max
    return n


def atk_cand_num(context):
    """候选池规模：目标数的 120%，且至少多 5 只"""
    n = atk_target_num(context)
    return max(int(n * 1.2), n + 5)


def atk_keep_pool_size(context):
    """排名缓冲区大小：目标数的 keep_ratio 倍（已持仓股跌出该区才卖出）"""
    n = atk_target_num(context)
    return max(int(n * g.atk_keep_ratio), n + 5)


def affordable(context, codes, per_amount):
    """剔除当前买不起一手的标的，避免清仓后一只都买不进"""
    cd_all = get_current_data()
    out = []
    for s in codes:
        cd = cd_all[s]
        if cd.paused or cd.last_price <= 0 or cd.last_price >= cd.high_limit:
            continue
        if cd.last_price * 100 > per_amount:
            continue
        out.append(s)
    return out


def attack_daily(context):
    if atk_is_rebalance_day(context):
        g.pending_refill = 0             # 调仓本身就会买满，缺口一笔勾销
        my_Trader(context)
        g.atk_last_rebal = context.current_dt.date()
        return

    if g.pending_refill <= 0:
        return
    target = atk_target_num(context)
    if len(context.portfolio.positions) >= target:
        g.pending_refill = 0
        return

    choice = select_stocks(context)
    done = buy_to_target(context, choice, target, flex=True)
    left = g.pending_refill - done
    g.pending_refill = left if left > 0 else 0
    if g.pending_refill > 0:
        log.info('补仓未完成，剩余 %d 只顺延至下一交易日' % g.pending_refill)


def atk_is_rebalance_day(context):
    """距上次进攻端调仓已跨过 atk_rebal_days 个交易日"""
    if g.atk_last_rebal is None:
        return True
    days = get_trade_days(start_date=g.atk_last_rebal,
                          end_date=context.current_dt.date())
    return len(days) - 1 >= g.atk_rebal_days


def my_Trader(context):
    ranked = select_stocks(context)
    if not ranked:
        log.info('进攻端无符合条件的标的，维持现状')
        return

    target = atk_target_num(context)
    keep_pool = set(ranked[:atk_keep_pool_size(context)])

    # 卖出：跌出排名缓冲区、且昨日未涨停的持仓才清掉。
    # 持仓只要仍在前 keep_pool_size 名就继续持有，避免每期调仓全进全出磨损收益。
    for s in list(context.portfolio.positions):
        if (s not in keep_pool) and (s not in g.atk_high_limit_list):
            order_target_value(s, 0)
            log.info('卖出[%s]（跌出排名缓冲区）' % s)

    per_amount = context.portfolio.total_value / target * (1 - g.atk_cash_buffer)
    buyable = affordable(context, ranked, per_amount)
    if not buyable and len(context.portfolio.positions) == 0:
        log.info('候选池无买得起的标的（单只预算 %.0f 元），本次不调仓' % per_amount)
        return
    log.info('进攻端目标 %d 只，单只预算约 %.0f 元，缓冲区 %d 只，可买 %d 只'
             % (target, per_amount, len(keep_pool), len(buyable)))

    buy_to_target(context, buyable, target)


def select_stocks(context):
    """
    进攻端选股：全市场 -> 板块/ST/停牌过滤 -> 基本面筛选 -> 流动性过滤，
    返回按市值升序的候选池。池子长度覆盖到排名缓冲区（> 目标数），
    供 my_Trader 做排名缓冲判断。
    """
    stocks = get_all_securities('stock', context.previous_date).index.tolist()
    stocks = filter_kcbj_stock(stocks)
    stocks = filter_st_stock(stocks)
    df = get_fundamentals(query(
        valuation.code
    ).filter(
        valuation.code.in_(stocks),
        valuation.market_cap > g.atk_min_mv,
        valuation.pb_ratio > 0,
        indicator.inc_return > 0,
        indicator.inc_total_revenue_year_on_year > 0,
        indicator.inc_net_profit_year_on_year > 0,
        indicator.ocf_to_operating_profit > g.atk_ocf_threshold,
    ).order_by(
        valuation.market_cap.asc()
    ).limit(
        max(atk_cand_num(context), atk_keep_pool_size(context))
    ))
    codes = list(df.code)
    return filter_liquidity(codes, context.previous_date, g.atk_min_money)


def filter_liquidity(codes, ref_date, min_money):
    """剔除近 5 日日均成交额低于 min_money（元）的标的，降低滑点损耗与流动性风险"""
    if not codes or min_money <= 0:
        return codes
    px = get_price(codes, end_date=ref_date, count=5, frequency='daily',
                   fields=['money'], skip_paused=False, fill_paused=False,
                   panel=False)
    if px is None or len(px) == 0:
        return codes
    if 'code' in px.columns and 'money' in px.columns:
        avg_money = px.dropna(subset=['money']).groupby('code')['money'].mean()
        return [c for c in codes if avg_money.get(c, 0) >= min_money]
    return codes


def buy_to_target(context, choice, target_num, flex=False):
    """
    按 choice（市值升序）把持仓补到 target_num 只，返回实际成交只数。
    flex=False：每只按总资产均分的目标金额买入（正常调仓）；
    flex=True ：按「可用现金 / 剩余待买数量」分配（小幅补仓，尽量少留闲置现金）。
    停牌、涨停、买不起一手的标的自动跳过，继续看下一只。
    """
    if not choice:
        return 0
    current_data = get_current_data()
    base_value = context.portfolio.total_value / target_num * (1 - g.atk_cash_buffer)
    bought = 0
    for s in choice:
        hold_num = len(context.portfolio.positions)
        if hold_num >= target_num:
            break
        if s in context.portfolio.positions:
            continue
        cd = current_data[s]
        if cd.paused or cd.last_price <= 0:
            continue
        if cd.last_price >= cd.high_limit:          # 涨停买不进
            continue
        cash = context.portfolio.available_cash
        if flex:
            cap = cash / (target_num - hold_num) * 0.995
        else:
            cap = cash * 0.995
        money = base_value if base_value < cap else cap
        if money < cd.last_price * 100:             # 不足一手 → 跳过，继续看下一只
            continue
        order_value(s, money)
        if s in context.portfolio.positions:        # 确认成交（涨停/资金不足会失败）
            bought += 1
            g.today_bought += 1
            log.info('买入[%s]（%.2f元）' % (s, money))
    return bought


def prepare_stock_list(context):
    """9:05：记录昨日涨停且当日未停牌的进攻端持仓（调仓时跳过卖出）"""
    g.atk_high_limit_list = []
    hold_list = list(context.portfolio.positions)
    if hold_list:
        df = get_price(hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit', 'paused'],
                       count=1, panel=False)
        g.atk_high_limit_list = df.query('close==high_limit and paused==0')['code'].tolist()


def check_limit_up(context):
    """14:00：昨日涨停持仓若打开涨停则卖出，并登记次日补仓数量（仅进攻端）"""
    if g.mode != 'attack':
        return
    current_data = get_current_data()
    sold = 0
    for stock in list(g.atk_high_limit_list):
        if stock not in context.portfolio.positions:
            continue
        cd = current_data[stock]
        if cd.paused:
            log.info('[%s]停牌，跳过' % stock)
            continue
        if cd.last_price < cd.high_limit:
            order_target_value(stock, 0)
            if stock not in context.portfolio.positions:   # 确认成交（跌停可能卖不出）
                sold += 1
                log.info('[%s]涨停打开，卖出' % stock)
        else:
            log.info('[%s]涨停，继续持有' % stock)
    if sold > 0:
        g.pending_refill += sold
        g.today_limit_sold += sold
        log.info('今日涨停打开卖出 %d 只，次日 9:30 按选股规则补足' % sold)


def filter_kcbj_stock(stock_list):
    """剔除科创板(68x)、北交所(4x/8x/920x)"""
    return [s for s in stock_list
            if not (s[:2] == '68' or s.startswith(('4', '8', '92')))]


def filter_st_stock(stock_list):
    """剔除 ST/*ST/退市/停牌"""
    current_data = get_current_data()
    return [s for s in stock_list if not (
        current_data[s].paused or
        current_data[s].is_st or
        'ST' in current_data[s].name or
        '*' in current_data[s].name or
        '退' in current_data[s].name)]


# =====================================================================
# 三、防御端：高股息 + 低波动 + 行业分散
# =====================================================================
def defense_daily(context, force=False):
    date = context.current_dt.date()
    if not force and g.def_last_rebal is not None \
            and (date - g.def_last_rebal).days < g.def_rebal_days:
        return

    df = select_dividend_pool(context, date)
    if df is None or len(df) == 0:
        log.info('防御端无合格标的，保持现状并在下一交易日重试')
        return                              # 不更新调仓日，次日重试

    g.def_last_rebal = date
    log.info('==== 防御端调仓 %s ====' % date)
    defense_trade(context, df, date)


def select_dividend_pool(context, date):
    """
    防御端选股（步骤 1~7）：
      1) PE>0 基础池 → 2) 自算 TTM 股息率 → 3) 上市天数 → 4) 剔 ST →
      5) 剔板块 → 6) 质量过滤（含近3年净利润不连续下滑）→ 7) 相对涨幅 → 波动率排序
    返回按 (波动率升序, 股息率降序) 排序好的 DataFrame，列 ['code','vol','dy']；
    任一环节无标的时返回 None。
    """
    # 1) 全市场 PE>0 作为基础池（get_fundamentals 默认仅返回 100 行，必须加 limit）
    q = query(valuation.code, valuation.pe_ratio).filter(valuation.pe_ratio > 0).limit(5000)
    fund = get_fundamentals(q, date=context.previous_date)
    if fund is None or len(fund) == 0:
        log.info('防御端：无 PE>0 的标的')
        return None
    base_pool = list(fund['code'])

    # 2) 自算 TTM 股息率（数据源：finance.STK_XR_XD 分红送股表）
    #    bonus_ratio_rmb = 每10股派息(元) → 每股派息 = /10
    #    只取"已实施方案"且 A股除权日落在滚动 12 个月内的现金分红
    #    finance.run_query 单次返回有行数上限，故按基础池分块（每 500 只）查询后合并
    one_year_ago = date - dt.timedelta(days=365)
    three_years_ago = date - dt.timedelta(days=365 * g.div_cont_years)
    div_records = []
    for i in range(0, len(base_pool), 500):
        chunk = base_pool[i:i + 500]
        try:
            d = finance.run_query(
                query(
                    finance.STK_XR_XD.code,
                    finance.STK_XR_XD.bonus_ratio_rmb,
                    finance.STK_XR_XD.a_xr_date,
                ).filter(
                    finance.STK_XR_XD.code.in_(chunk),
                    finance.STK_XR_XD.a_xr_date >= three_years_ago,
                    finance.STK_XR_XD.a_xr_date <= date,
                    finance.STK_XR_XD.plan_progress == '实施方案'
                )
            )
        except Exception as e:
            log.warning('分红查询异常(块 %d): %s' % (i, e))
            d = None
        if d is not None and len(d) > 0:
            div_records.append(d)

    if not div_records:
        log.info('防御端：近三年无已实施分红数据')
        return None
    div_all = pd.concat(div_records, ignore_index=True)
    div_all = div_all.dropna(subset=['bonus_ratio_rmb', 'a_xr_date'])
    div_all['dps'] = div_all['bonus_ratio_rmb'] / 10.0   # 每股现金分红
    div_all['yr'] = div_all['a_xr_date'].apply(lambda x: x.year)

    # TTM 股息率：近一年每股分红合计 / 现价
    ttm_mask = (div_all['a_xr_date'] >= one_year_ago) & (div_all['a_xr_date'] <= date)
    ttm_dps = div_all[ttm_mask].groupby('code')['dps'].sum()

    # 分红连续性：近 N 年至少两年派息，且最近年度未骤降
    div_ok = check_dividend_continuity(div_all, date, g.div_cont_years, g.div_drop_ratio)

    div_codes = [c for c in base_pool if c in ttm_dps.index and c in div_ok]
    if len(div_codes) == 0:
        log.info('防御端：近一年无分红或分红不连续的标的')
        return None

    # 用前一交易日收盘价（不复权，避免未来函数；与现金分红口径一致）
    price = get_price(div_codes, end_date=context.previous_date, count=1,
                      fields=['close'], skip_paused=False, fill_paused=False,
                      fq=None, panel=False)

    dy_list = []
    for c in div_codes:
        try:
            ser = get_close_series(price, c)
            if ser is None or len(ser) == 0:
                continue
            p = float(ser.iloc[-1])
            if pd.isna(p) or p <= 0:
                continue
            dy = float(ttm_dps[c]) / p
            if g.dy_max > dy > 0:
                dy_list.append((c, dy))
        except Exception:
            continue
    if len(dy_list) == 0:
        log.info('防御端：无股息率符合条件标的')
        return None

    # 股息率全市场排名前 dy_top_n
    dy_list.sort(key=lambda x: x[1], reverse=True)
    dy_list = dy_list[:g.dy_top_n]
    candidates = [c for c, _ in dy_list]
    dy_map = {c: dy for c, dy in dy_list}

    # 3) 上市天数
    all_sec = get_all_securities(types=['stock'], date=date)
    candidates = [c for c in candidates
                  if c in all_sec.index
                  and (date - all_sec.loc[c, 'start_date']).days > g.min_list_days]

    # 4) 剔除 ST（状态锚定上一交易日）
    if g.exclude_st and candidates:
        st_df = get_extras('is_st', candidates, end_date=context.previous_date)
        st_map = st_df.iloc[0].to_dict()
        candidates = [c for c in candidates if not st_map.get(c, False)]

    # 5) 剔除特定板块
    candidates = [c for c in candidates if not excluded_by_board(c)]

    # 5.5) 质量过滤：ROE>0、资产负债率<上限、经营现金流覆盖
    candidates = quality_filter(candidates, context.previous_date)
    if len(candidates) == 0:
        log.info('防御端：质量过滤后无候选标的')
        return None

    # 5.6) 剔除近3年净利润连续下滑
    if g.check_profit_decline:
        candidates = filter_profit_decline(candidates, context.previous_date)
        if len(candidates) == 0:
            log.info('防御端：净利润连续下滑过滤后无候选标的')
            return None

    # 6) 相对上证指数涨幅 > 0
    candidates = filter_relative_gain(candidates, context.previous_date, g.rel_window)
    if len(candidates) == 0:
        log.info('防御端：无相对涨幅为正的标的')
        return None

    # 7) 波动率升序 + 股息率降序
    vol = get_volatility(candidates, context.previous_date, g.vol_window)
    df = pd.DataFrame({'code': candidates})
    df['vol'] = df['code'].map(vol)
    df['dy'] = df['code'].map(dy_map)
    df = df.dropna(subset=['vol'])
    df = df.sort_values(by=['vol', 'dy'], ascending=[True, False])
    return df


def defense_trade(context, df, date):
    """构建防御端目标持仓并执行交易"""
    positions = context.portfolio.positions
    locked = get_locked_positions(context, date)

    final = build_target_with_buffer(
        df, list(positions.keys()),
        g.def_stock_num, g.keep_num, g.industry_pct, date, locked
    )

    log.info('防御端：本期入选 %d 只（锁定 %d 只）：%s' % (len(final), len(locked), final))
    if locked:
        log.info('锁定股票（持股未满 %d 天）：%s' % (g.min_hold_days, locked))

    g.def_target = list(final)
    rebalance_portfolio(context, final, g.def_stock_num)


def get_locked_positions(context, date):
    """维护防御端首次买入日期，返回因最小持股天数被锁定的股票；同时清理已清仓记录。
    国债 ETF 底仓不算股票持仓，不参与锁仓与目标池构建。"""
    positions = context.portfolio.positions
    for code in list(positions.keys()):
        if code == g.def_cash_asset:
            continue
        if code not in g.def_hold_start:
            g.def_hold_start[code] = date
    for code in list(g.def_hold_start.keys()):
        if code not in positions:
            del g.def_hold_start[code]

    locked = []
    if g.min_hold_days > 0:
        for code in positions.keys():
            if code == g.def_cash_asset:
                continue
            start = g.def_hold_start.get(code)
            if start is not None and (date - start).days < g.min_hold_days:
                locked.append(code)
    return locked


def rebalance_portfolio(context, target_list, target_num):
    """
    防御端交易（V3）：
      1) 先卖出不在目标池的持仓（国债 ETF 底仓除外，由末尾统一调平）；
      2) 股票总仓位 = 总资产 × def_position_ratio，把持仓补到 target_num 只，
         从目标池中尚未持有的标的里按选股顺序取，均权分配股票预算；
      3) 剩余资金全部买入国债 ETF——防御端波动从 17% 降到约 10%，
         普跌行情里不再"防御端照样大亏"。
    """
    # 1) 先卖出
    for code in list(context.portfolio.positions.keys()):
        if code not in target_list and code != g.def_cash_asset:
            order_target_value(code, 0)

    if not target_list:
        return

    # 2) 还差多少只（国债 ETF 不算股票持仓）
    positions = context.portfolio.positions
    n_hold = len([c for c in positions if c != g.def_cash_asset])
    n_needed = max(target_num - n_hold, 0)

    # 3) 从目标池里挑尚未持有的
    to_buy = [c for c in target_list if c not in positions][:n_needed]
    n_buy = len(to_buy)

    # 4) 股票预算 = 总资产 × 防御仓位比例；现金不足时按现金，均权分配
    if n_buy > 0:
        stock_budget = context.portfolio.total_value * g.def_position_ratio
        cash = min(context.portfolio.available_cash, stock_budget) * 0.998
        per_amount = cash / n_buy
        if per_amount < g.def_min_trade_value:
            log.info('防御端股票预算不足，均权额度 %.0f < 碎片阈值，跳过买入' % per_amount)
        else:
            log.info('防御端当前持仓 %d 只，需买入 %d 只，股票预算 %.0f（占 %.0f%%），每只约 %.0f 元'
                     % (n_hold, n_buy, stock_budget, g.def_position_ratio * 100, per_amount))
            buy_date = context.current_dt.date()
            for code in to_buy:
                if code in context.portfolio.positions:
                    continue
                order_value(code, per_amount)
                if code in context.portfolio.positions:      # 确认成交
                    g.today_bought += 1
                    if code not in g.def_hold_start:
                        g.def_hold_start[code] = buy_date

    # 5) 剩余资金买入国债 ETF 底仓（每次调仓后把闲置现金调平进去）
    if g.def_cash_asset:
        left = context.portfolio.available_cash
        if left > 10000:
            cd = get_current_data()
            etf_cd = cd.get(g.def_cash_asset)
            if etf_cd is None or not (etf_cd.paused or etf_cd.last_price <= 0):
                order_value(g.def_cash_asset, left * 0.995)


# ---------------------- 防御端工具函数 ----------------------
def get_close_series(price, code):
    """
    从 get_price 的任意返回结构中取某只标的的收盘价 Series，兼容多种结构：
      - dict / Panel / 长表(time+code) / 宽表(columns=代码) /
        MultiIndex 列 / MultiIndex 行 / 单标的(index=日期, columns=['close']) / 紧凑快照
    取不到或为空返回 None。
    """
    # 1) dict 形式
    if isinstance(price, dict):
        df = price.get(code)
        if df is None:
            return None
        if isinstance(df, pd.Series):
            return df
        if 'close' in df:
            return df['close']
        return None

    # 2) 非 DataFrame（如 Panel）尝试直接下标
    if not isinstance(price, pd.DataFrame):
        try:
            return price[code]['close']
        except Exception:
            return None

    # 3) 长表(tidy)：columns 含 'time'/'code'
    if 'code' in price.columns and 'time' in price.columns:
        sub = price[price['code'] == code].sort_values('time')
        if len(sub) == 0:
            return None
        if 'close' in sub.columns:
            return sub['close']
        return sub[sub.columns[-1]]

    # 4) 宽表：columns 直接就是代码
    if code in price.columns:
        s = price[code]
        if isinstance(s, pd.Series):
            return s
        return pd.Series(s) if hasattr(s, 'iloc') else None

    # 5) 单标的：index 为日期，columns 为字段（如 ['close']）
    #    —— 原实现缺这一支，单只标的取价会直接返回 None
    if not isinstance(price.columns, pd.MultiIndex) and 'close' in price.columns:
        return price['close']

    # 6) columns 是 MultiIndex
    if isinstance(price.columns, pd.MultiIndex):
        for lvl in range(price.columns.nlevels):
            if code in price.columns.get_level_values(lvl):
                sub = price.xs(code, level=lvl, axis=1)
                if isinstance(sub, pd.Series):
                    return sub
                if 'close' in sub.columns:
                    return sub['close']
                if sub.shape[1] == 1:
                    return sub.iloc[:, 0]
                return None

    # 7) index 是 MultiIndex
    if isinstance(price.index, pd.MultiIndex):
        for lvl in range(price.index.nlevels):
            if code in price.index.get_level_values(lvl):
                sub = price.xs(code, level=lvl)
                if isinstance(sub, pd.Series):
                    return sub
                if 'close' in sub.columns:
                    return sub['close']
                if sub.shape[1] == 1:
                    return sub.iloc[:, 0]
                return None

    # 8) index 即标的代码（count=1 的紧凑快照表）
    if 'close' in price.columns and code in price.index:
        try:
            v = price.loc[code]
            if isinstance(v, pd.Series):
                return v['close'] if 'close' in v.index else v.iloc[0]
            return pd.Series([v]) if v == v else None
        except Exception:
            return None
    return None


def excluded_by_board(code):
    """根据代码判断是否属于需剔除的板块"""
    num = code.split('.')[0]
    if g.exclude_bj and code.endswith('.XBJ'):
        return True
    if g.exclude_kcb and num.startswith('688'):
        return True
    if g.exclude_cyb and (num.startswith('300') or num.startswith('301') or num.startswith('302')):
        return True
    return False


def filter_relative_gain(codes, date, days):
    """保留 days 日超额收益（个股 - 上证指数）> 0 的标的"""
    price = get_price(
        codes + ['000001.XSHG'], end_date=date, count=days + 1,
        frequency='daily', fields=['close'], skip_paused=False, fill_paused=False,
        fq='pre', panel=False
    )
    idx = get_close_series(price, '000001.XSHG')
    if idx is None or len(idx) < days + 1:
        return codes                      # 指数取不到时不做这一步，避免误杀
    idx_ret = (idx.iloc[-1] - idx.iloc[0]) / idx.iloc[0]
    keep = []
    for code in codes:
        try:
            s = get_close_series(price, code)
            if s is None or len(s) < days + 1:
                continue
            if pd.isna(s.iloc[0]) or s.iloc[0] == 0 or pd.isna(s.iloc[-1]):
                continue
            stock_ret = (s.iloc[-1] - s.iloc[0]) / s.iloc[0]
            if stock_ret - idx_ret > 0:
                keep.append(code)
        except Exception:
            continue
    return keep


def get_volatility(codes, date, days):
    """计算 days 日年化波动率 = 日收益标准差 * sqrt(242)"""
    price = get_price(
        codes, end_date=date, count=days + 1,
        frequency='daily', fields=['close'], skip_paused=False, fill_paused=False,
        fq='pre', panel=False
    )
    vols = {}
    for code in codes:
        try:
            s = get_close_series(price, code)
            if s is None:
                vols[code] = np.nan
                continue
            rets = s.pct_change().dropna()
            vols[code] = rets.std() * np.sqrt(242) if len(rets) >= 20 else np.nan
        except Exception:
            vols[code] = np.nan
    return vols


def build_target_with_buffer(df, holdings, target_num, keep_num, limit_pct, date, must_keep=None):
    """
    构建防御端目标持仓，兼顾行业分散、持仓缓冲与强制锁仓：
      - 排名前 keep_num 构成"保护区"，已持仓且仍在保护区内的优先保留，降低换手；
      - must_keep（未满足最小持股天数）强制保留，不受行业限制；
      - industry_neutral=True  → 按行业等权轮转分配名额（各行业数量最多差 1）
        industry_neutral=False → 单一行业 <= limit_pct * target_num
    """
    ranked = list(df['code'])
    if not ranked:
        return []

    must_keep = set(must_keep or [])
    zone = set(ranked[:keep_num])
    holdings_set = set(holdings)

    ind_cache = {}

    def ind_of(code):
        if code not in ind_cache:
            try:
                info = get_industry(code, date)
                ind_cache[code] = info['jq_l1']['industry_code'] \
                    if (info and 'jq_l1' in info) else code
            except Exception:
                ind_cache[code] = code
        return ind_cache[code]

    rank_pos = {c: i for i, c in enumerate(ranked)}
    ind_groups = {}
    for c in ranked:
        ind_groups.setdefault(ind_of(c), []).append(c)

    selected = []
    selected_set = set()
    ind_count = {}

    def add(code):
        selected.append(code)
        selected_set.add(code)
        ic = ind_of(code)
        ind_count[ic] = ind_count.get(ic, 0) + 1

    # 0) must_keep 强制保留（锁仓优先，不受行业限制）
    for c in ranked:
        if c in must_keep and len(selected) < target_num:
            add(c)
    # must_keep 中已不在候选池内的也保留，避免被动卖出
    for c in must_keep:
        if c not in selected_set and len(selected) < target_num:
            add(c)

    if g.industry_neutral:
        # 按行业等权轮转：每轮从"当前已选数量最少"的行业挑 1 只
        while len(selected) < target_num:
            cands = []
            for ic, codes in ind_groups.items():
                remain = [c for c in codes if c not in selected_set]
                if not remain:
                    continue
                cands.append((ind_count.get(ic, 0), rank_pos[remain[0]], ic, remain))
            if not cands:
                break
            cands.sort(key=lambda x: (x[0], x[1]))
            _, _, _ic, remain = cands[0]
            pick = None
            for c in remain:
                if c in holdings_set and c in zone:
                    pick = c
                    break
            if pick is None:
                for c in remain:
                    if c in holdings_set:
                        pick = c
                        break
            if pick is None:
                pick = remain[0]
            add(pick)
    else:
        max_per_ind = limit_pct * target_num
        protected = [c for c in holdings if c in zone]

        def try_add(code, cap):
            ic = ind_of(code)
            if ind_count.get(ic, 0) + 1 <= cap:
                add(code)
                return True
            return False

        for c in protected:
            if len(selected) >= target_num:
                break
            if c in selected_set:
                continue
            try_add(c, max_per_ind)
        for c in ranked:
            if len(selected) >= target_num:
                break
            if c in selected_set:
                continue
            try_add(c, max_per_ind)
        # 兜底：逐步放宽行业上限，保证凑够 target_num
        relax = 1.0
        while len(selected) < target_num and relax <= target_num:
            for c in protected:
                if len(selected) >= target_num:
                    break
                if c in selected_set:
                    continue
                try_add(c, max_per_ind + relax)
            for c in ranked:
                if len(selected) >= target_num:
                    break
                if c in selected_set:
                    continue
                try_add(c, max_per_ind + relax)
            relax += 1.0

    return selected


def check_dividend_continuity(div_all, date, cont_years, drop_ratio):
    """
    返回通过连续性检验的股票集合：
      - 近 cont_years 个自然年内至少 2 年实际派息（历史不足时按可用年数计）；
      - 最近两个"有分红"的年份相邻时，最新年合计派息不低于前一年的 drop_ratio 倍，
        过滤一次性高分红 / 周期顶部的"伪高股息"。
    注意：同一自然年可能分红多次，必须按年合计（原先取首笔是错的）。
    """
    ok = set()
    if div_all is None or len(div_all) == 0:
        return ok

    recent_years = list(range(date.year - cont_years + 1, date.year + 1))
    year_dps = div_all.groupby(['code', 'yr'])['dps'].sum()   # 年内多次分红按合计

    for code, grp in div_all.groupby('code'):
        try:
            dps_map = year_dps.loc[code].to_dict()
        except Exception:
            continue
        avail = [y for y in recent_years if y in dps_map]
        paid = [y for y in avail if dps_map.get(y, 0) > 0]
        need = min(2, len(avail))
        if len(paid) < need:
            continue

        # 骤降检查：比较最近两个"有分红"的年份
        paid_sorted = sorted(y for y, v in dps_map.items() if v > 0)
        if len(paid_sorted) >= 2:
            y_new, y_old = paid_sorted[-1], paid_sorted[-2]
            d_new = dps_map.get(y_new, 0)
            d_old = dps_map.get(y_old, 0)
            if d_old > 0 and d_new < drop_ratio * d_old:
                continue
        ok.add(code)
    return ok


def quality_filter(codes, date):
    """
    质量过滤：ROE>0、资产负债率<上限、经营现金流/净利润>下限。
    任一子查询失败时该子条件降级为"不剔除"（保守通过），避免崩溃与误杀。
    """
    if not codes:
        return codes

    # ROE（indicator 表）
    roe_map = {}
    try:
        for i in range(0, len(codes), 500):
            chunk = codes[i:i + 500]
            f = get_fundamentals(
                query(indicator.code, indicator.roe).filter(indicator.code.in_(chunk)),
                date=date
            )
            if f is None or len(f) == 0:
                continue
            for _, r in f.iterrows():
                roe_map[r['code']] = r.get('roe')
    except Exception as e:
        log.warning('ROE 查询失败，跳过 ROE 过滤: %s' % e)
        roe_map = {}

    # 资产负债率 = 总负债 / 总资产
    debt_map = {}
    try:
        for i in range(0, len(codes), 500):
            chunk = codes[i:i + 500]
            f = get_fundamentals(
                query(balance.code, balance.total_liability, balance.total_assets
                      ).filter(balance.code.in_(chunk)),
                date=date
            )
            if f is None or len(f) == 0:
                continue
            for _, r in f.iterrows():
                tl = r.get('total_liability')
                ta = r.get('total_assets')
                if tl is not None and ta not in (None, 0) \
                        and not pd.isna(tl) and not pd.isna(ta):
                    debt_map[r['code']] = tl / ta
    except Exception as e:
        log.warning('负债率查询失败，跳过负债率过滤: %s' % e)
        debt_map = {}

    # 经营现金流覆盖 = 经营净额 / 净利润
    cf_map, np_map = {}, {}
    try:
        for i in range(0, len(codes), 500):
            chunk = codes[i:i + 500]
            fc = get_fundamentals(
                query(cash_flow.code, cash_flow.net_cash_flows_oper_act
                      ).filter(cash_flow.code.in_(chunk)),
                date=date
            )
            if fc is not None and len(fc) > 0:
                for _, r in fc.iterrows():
                    cf_map[r['code']] = r.get('net_cash_flows_oper_act')
            fn = get_fundamentals(
                query(income.code, income.net_profit).filter(income.code.in_(chunk)),
                date=date
            )
            if fn is not None and len(fn) > 0:
                for _, r in fn.iterrows():
                    np_map[r['code']] = r.get('net_profit')
    except Exception as e:
        log.warning('现金流查询失败，跳过现金流覆盖过滤: %s' % e)
        cf_map, np_map = {}, {}

    good = []
    for c in codes:
        roe = roe_map.get(c)
        if roe is not None and not pd.isna(roe) and not (roe > g.min_roe):
            continue
        debt = debt_map.get(c)
        if debt is not None and not (debt < g.max_debt_ratio / 100.0):
            continue
        cf = cf_map.get(c)
        np_ = np_map.get(c)
        if (cf is not None and np_ is not None and not pd.isna(cf) and not pd.isna(np_)
                and np_ > 0 and not (cf / np_ > g.min_ocf_to_profit)):
            continue
        good.append(c)
    return good


def filter_profit_decline(codes, ref_date):
    """
    剔除"近 3 年净利润连续下滑"的标的。
    取每年年报口径（statDate='YYYY'），保证口径一致；
    任一年份数据缺失则该股保留；整体查询失败时降级为"不剔除"。
    """
    if not codes:
        return codes

    years = [ref_date.year - 1, ref_date.year - 2, ref_date.year - 3]
    np_by_year = {}

    for y in years:
        try:
            for i in range(0, len(codes), 500):
                chunk = codes[i:i + 500]
                f = get_fundamentals(
                    query(income.code, income.net_profit).filter(income.code.in_(chunk)),
                    statDate=str(y)
                )
                if f is None or len(f) == 0:
                    continue
                for _, r in f.iterrows():
                    v = r.get('net_profit')
                    if v is not None and not pd.isna(v):
                        np_by_year.setdefault(r['code'], {})[y] = float(v)
        except Exception as e:
            log.warning('净利润历史查询失败(%d年): %s' % (y, e))

    if not np_by_year:
        return codes

    keep = []
    dropped = 0
    for c in codes:
        d = np_by_year.get(c)
        if d is None:
            keep.append(c)
            continue
        p1, p2, p3 = d.get(years[0]), d.get(years[1]), d.get(years[2])
        if p1 is None or p2 is None or p3 is None:
            keep.append(c)                 # 数据不全不剔除
            continue
        if p1 < p2 and p2 < p3:
            dropped += 1                   # 连续两年下滑 → 剔除
            continue
        keep.append(c)

    if dropped:
        log.info('近3年净利润连续下滑，剔除 %d 只' % dropped)
    return keep


# =====================================================================
# 四、收盘汇总
# =====================================================================
def after_market_close(context):
    mode_name = '进攻(小市值)' if g.mode == 'attack' else '防御(高股息)'
    log.info('【%s】今日买入 %d 只，涨停卖出 %d 只，持仓 %d 只'
             % (mode_name, g.today_bought, g.today_limit_sold,
                len(context.portfolio.positions)))
