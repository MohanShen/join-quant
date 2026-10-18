# Clone from JoinQuant
# postId: e0629c868750d8882be642e85363bec6
# backtestId: 24ce522aa2bd9152f2e90cbca0658bd2
# title: 用「净利润增速」选股的聚宽策略：逻辑其实很朴素

# -*- coding: utf-8 -*-
# ============================================================================
# >>> 本文件【就是】聚宽策略本体：请全选复制到聚宽「策略编辑器」中运行 <<<
#
#   ⚠ 目录内的 test_*.py 与 smoke_test_full_run.py 都是【本地验证脚本】，
#     它们会去读取本文件在本地磁盘上的路径；粘到聚宽必然报
#     FileNotFoundError: '...net_profit_growth_strategy.py'。
#     只有本文件（net_profit_growth_strategy.py）可以粘进聚宽。
#
#   本文件自包含：仅依赖 datetime / numpy / pandas / jqdata，
#   不读取任何本地文件，不依赖 sys.path 上的任何模块。
# ============================================================================
"""
==============================================================================
策略名称：净利润增速因子（TTM 口径）多因子选股策略
改编来源：源达信息《从因子到策略：净利润增速因子的十年回测研究》
          —— 金融工程研究，分析师 吴起涤（A0190523020001），2026-07-23
适配平台：JoinQuant（聚宽）回测 / 模拟交易
==============================================================================

【研报核心逻辑】
1) 因子定义 —— TTM 净利润同比增速（含少数股东损益）

       增速 = (本期 TTM 净利润 - 去年同期 TTM 净利润) / |去年同期 TTM 净利润|

   TTM 口径的优势：滚动 12 个月，规避单季数据的季节性与财务结算周期噪音；
   且相邻两期 TTM 存在多个季度重合样本，信号更平滑。

2) 因子实证特征（研报 IC 检测结论）
   - 中小盘优于大盘：中证 1000 平均 RankIC 0.0621 / RankICIR 0.6066，最强
   - 行业：家用电器、采掘、电气设备最强；传媒、农林牧渔、房地产最弱
   - 市值：61~113 亿区间最优（市值组 3/4），整体呈倒 U 型
   => 本策略股票池取【中证全指】；如需聚焦最优市值区间，打开 g.use_cap_filter

3) 组合构建（研报"多因子组合策略"）
   Step1 剔除 ST、退市公司
   Step2 剔除营业收入同比增速 < 10% 的公司（确保收入与利润双升）
   Step3 剔除 PEG < 0 或 PEG > 3 的公司（为成长支付的价格留安全边际）
   Step4 每月末调仓（非交易日顺延至最后一个交易日），按净利润增速因子降序取前 5 只等权

【研报回测结果 2014.04.30 ~ 2026.06.30（Wind 口径，未计交易费用）】
   总回报 2649.07% | 相对沪深300 超额 2518.38% | 年化 31.15%
   年化波动 35.53% | Sharpe 0.83 | Alpha 23.99% | Beta 1.0118
   跟踪误差 1.78% | 最大回撤 -62.52%

==============================================================================
【增补规则一：回避月空仓 —— 1 月与 4 月不持有股票】
------------------------------------------------------------------------------
动机：
    A 股存在两个日历效应偏弱的月份，而研报的持仓区间恰好把两者都暴露在外：
      - 1 月：跨年资金面偏紧，上年末排名结算与新年度配置切换交织，方向性差；
      - 4 月：年报与一季报密集披露带来业绩"踩雷"风险，叠加 4·19 魔咒、
        缴税大月与 5 月前的资金面收紧。
    故增补"回避月空仓"规则：只做时间维度的风险回避，不改动因子定义、
    过滤链与选股数量。

规则：
    1) 回避月（g.avoid_months，默认 [1, 4]）内不持有股票；
    2) 切换动作在"回避窗口"内以尾盘（g.avoid_trade_time，默认 14:50）完成；
       窗口默认自回避月前一月最后一个交易日起算（g.avoid_exit_ahead=True），
       即提前在月末尾盘换仓，不把月末的隔夜跳空风险带进回避月；
    3) 每月末为因子调仓日（非交易日顺延至月末最后一个交易日）。若调仓日落在
       回避月内，仍按逻辑重建股票仓位（g.avoid_keep_rebalance=True），实际股票
       暴露仅回避月最后一个交易日，等价于"次月开始持仓"；
    4) 离开回避月后的首个交易日自动"恢复建仓"，采用当时最早可用的定期报告
       口径 —— 2 月恢复用上年三季报（年报此时尚在披露期），5 月恢复用当年
       一季报，详见 _resume_period()。

==============================================================================
【增补规则二：始终持有10%避险 ETF —— 非回避月10% / 回避月100%】
------------------------------------------------------------------------------
始终将 etf_target_pct（默认10%）的资金等权配置到 g.hedge_etfs：

    红利ETF      510880.XSHG   上证红利（红利 / 价值风格暴露）
    黄金ETF      518880.XSHG   商品，与股债相关性低
    标普500ETF   513500.XSHG   美股大盘
    纳斯达克ETF  513100.XSHG   美股科技
    中证500ETF   510500.XSHG   A 股中盘
    沪深300ETF   510300.XSHG   A 股大盘

配置规则：
    - 非回避月：90%股票（等权）+ 10%避险 ETF（等权）
    - 回避月：100%避险 ETF（由 avoid_month_guard 将股票清仓并加仓ETF）
    - 避险 ETF 每年再平衡一次（等权分配），与月度股票调仓独立

设计意图：
    把"空仓"从"持币"升级为"低相关多资产组合"—— 6 只 ETF 覆盖 A 股大/中盘、
    美股大盘 + 科技、红利风格与黄金商品。单一资产在回避月的表现并不确定，
    但组合整体波动显著低于本策略本身（5 只中小盘等权），从而在规避回避月
    风险的同时保留收益补偿。非回避月保留10%底仓，提供持续的分散化收益。

费用口径（必须与股票分开设置）：
    场内 ETF 无印花税、仅收佣金，且必须用 type='fund'；若沿用股票的
    type='stock' 会错误扣取印花税并高估成本。

==============================================================================
【防未来函数设计】
------------------------------------------------------------------------------
核心原则：
    所有"参与决策"的数据，其可见时点必须 <= 信息可见日 as_of（默认 T-1）。
    唯一例外是交易可行性数据（停牌 / ST / 涨跌停），必须用当日实时状态，
    否则无法判断当天能不能下单 —— 但这类数据只用于"能不能买"，
    绝不参与排序、打分或因子计算。

时点审计表：
  | 数据点                | 接口与约束                                  | 可见时点 |
  |----------------------|--------------------------------------------|---------|
  | 指数成分股            | get_index_stocks(date=as_of)               | T-1     |
  | 估值 PE / 市值        | get_fundamentals(date=as_of)               | T-1     |
  | 营收同比增速          | get_fundamentals(date=as_of)               | T-1     |
  | 定期报告累计净利润     | finance.STK_INCOME_STATEMENT               | 公告日   |
  |                      |   .filter(pub_date <= as_of)               |         |
  |                      |   同报告期多版本 -> 取 pub_date 最新         |         |
  | 指数均线              | get_price(end_date=as_of, ...)             | T-1     |
  | 上市日期              | get_all_securities(date=as_of)             | T-1     |
  | 停牌 / ST / 涨跌停     | get_current_data()  <- 必须用当日，仅用于可行性 | 当日  |

四道防线：
  1) set_option('avoid_future_data', True)
     —— 注意：它只对 get_price / history 等行情接口生效，
        对 get_fundamentals 与 finance.run_query **完全无效**，必须自行约束。
  2) _data_asof(context) 统一产出信息可见日，且内置断言
        assert as_of < context.current_dt.date()   # 机制性杜绝未来函数
        可用 g.data_lag_days 再额外滞后 N 个交易日。
  3) 财务数据一律带 pub_date <= as_of 过滤，绝不使用"报告期"裸数据。
  4) g.audit_future_data = True 时，每次调仓打印完整时点审计表，可逐条核对。
==============================================================================
"""

import datetime

import numpy as np
import pandas as pd
from jqdata import finance


# ============================================================================
# 一、初始化
# ============================================================================
def initialize(context):
    """策略初始化：账户设置、全局参数、定时任务"""

    # ------------------------- 账户与撮合 -------------------------
    set_benchmark('000300.XSHG')                  # 基准：沪深 300（对齐研报）
    set_option('use_real_price', True)            # 使用真实价格（前复权）
    set_option('avoid_future_data', True)         # 开启防未来函数
    # 滑点：按成交额比例，近似冲击成本。研报未计交易费用，
    # 若需完全对齐研报口径，可改为 set_slippage(FixedSlippage(0))
    set_slippage(PriceRelatedSlippage(0.00246))
    set_order_cost(OrderCost(close_tax=0.001,          # 印花税（卖出）
                             open_commission=0.0003,   # 买入佣金
                             close_commission=0.0003,  # 卖出佣金
                             min_commission=5),        # 最低佣金 5 元
                   type='stock')
    # ETF（场内基金）费率必须单独设置：ETF 无印花税、仅收佣金，且聚宽中
    # ETF 属于"基金"类别 —— 若沿用 type='stock' 会错误扣取印花税并高估成本。
    set_order_cost(OrderCost(open_tax=0,               # 开仓无印花税
                             close_tax=0,              # 平仓无印花税
                             open_commission=0.0002,   # 买入佣金万二
                             close_commission=0.0002,  # 卖出佣金万二
                             close_today_commission=0, # 日内平仓无额外费用
                             min_commission=5),        # 最低佣金 5 元
                   type='fund')
    log.set_level('order', 'error')
    log.set_level('system', 'error')

    # ------------------------- 策略参数 -------------------------
    g.index_code = '000985.XSHG'        # 股票池：中证全指（研报 IC 检测口径）
    g.stock_num = 8                     # 研报：按因子降序取前 5 只，等权

    g.min_revenue_grow = 10.0           # 研报 Step2：营业收入同比增速 >= 10 (%)
    g.peg_low, g.peg_high = 0.0, 3.0    # 研报 Step3：PEG ∈ (0, 3]

    # —— 以下为工程化风控/可选开关，非研报原文，默认设置已尽量贴近研报 ——
    g.min_listed_days = 260              # 剔除上市不足 60 个自然日的次新股
    g.min_prev_profit = 1e5             # 上年同期 TTM 净利润绝对值 < 10 万元时剔除
                                        # （分母过小会使增速极度失真）
    g.use_cap_filter = False            # True 时限定在研报最优市值区间选股
    g.cap_low, g.cap_high = 61e8, 113e8  # 61 亿 ~ 113 亿（研报市值组 3/4）
    g.use_timing = False                # True 时启用中证全指 MA20 择时（研报未含）
    g.timing_ma = 20

    # ------------------------- 回避月空仓（1 月 / 4 月）-------------------------
    g.use_avoid_months = True           # True 时启用"回避月空仓"规则
    g.avoid_months = [1, 4]             # 回避月份列表：1 月与 4 月不持有股票
    g.avoid_exit_ahead = True           # True：自回避月前一月最后一个交易日尾盘切换
                                        # False：自回避月首个交易日尾盘切换
    g.avoid_keep_rebalance = True       # True：调仓日仍按逻辑建仓（推荐）
                                        # False：调仓日一并回避，顺延至回避月后首个交易日
    g.avoid_trade_time = '14:50'        # 空仓规则的执行时点（尾盘）；必须晚于 g.trade_time
    g.avoid_mode = False                # 运行态：是否已把资金切出股票（进入回避模式）

    # ------------------------- 避险 ETF 组合（始终持有10%，回避月加仓至100%）-------------------------
    g.use_hedge_etf = True              # True：始终持有 etf_target_pct 比例的避险 ETF
                                        #       回避月内加仓至100%，非回避月维持10%
                                        # False：回避月简单持币（研报式空仓）
    g.hedge_etfs = [
        '510880.XSHG',   # 红利ETF（华泰柏瑞上证红利）
        '518880.XSHG',   # 黄金ETF（华安黄金易）
        '513500.XSHG',   # 标普500ETF（博时标普500）
        '513100.XSHG',   # 纳斯达克100ETF（国泰纳指100）
        '510500.XSHG',   # 中证500ETF（南方中证500）
        '510300.XSHG',   # 沪深300ETF（华泰柏瑞沪深300）
    ]
    g.etf_target_pct = 0.10             # 始终保持10%资金在避险ETF中（含回避月与非回避月）
    g.etf_rebalance_interval = 365      # ETF年度再平衡间隔（天）
    g.last_etf_rebalance_date = None    # 上次ETF再平衡日期

    # ------------------------- 防未来函数 -------------------------
    g.data_lag_days = 0                 # 额外滞后交易日数：0 = 用 T-1 数据（默认）
                                        # 设为 1 表示用 T-2，用于规避"公告当日可见性"争议
    g.audit_future_data = True          # True 时每次调仓打印时点审计表
    g.trade_time = '09:35'              # 调仓时点。所有选股数据均取自 T-1 及更早，
                                        # 故在 09:35 以当时价格成交不构成未来函数

    # ------------------------- 调仓日历（每月末）-------------------------
    # 月份 -> 该月调仓时采用的最新定期报告期所在月份
    #   1~3 月 → 上年三季报 (9-30)：年报尚在披露期，取上年三季报最稳妥
    #   4~7 月 → 当年一季报 (3-31)：4/30 后已基本披露完
    #   8 月   → 当年半年报 (6-30)：8/31 后已基本披露完
    #   9~12月 → 当年三季报 (9-30)：10/31 后已基本披露完
    g.rebalance_plan = {
        1: 9, 2: 9, 3: 9,             # 上年三季报（年报尚未出齐）
        4: 3, 5: 3, 6: 3, 7: 3,       # 当年一季报
        8: 6,                          # 当年半年报
        9: 9, 10: 9, 11: 9, 12: 9,    # 当年三季报
    }
    g.done_months = set()              # 本年度「已完成调仓的月份」集合（{1,2,...}），防重复触发
    g.rebalanced_dates = set()          # 「实际发生调仓的交易日」集合。
                                        # 空仓守卫靠它判断"今日是否已调仓"。

    run_daily(rebalance_scheduler, g.trade_time)       # 调仓（默认 09:35）
    # 回避月空仓：必须晚于调仓调度，以便读取 g.rebalanced_dates 判断"今日是否已调仓"，
    # 避免在回避月出现"先清仓再买回"的重复交易（无谓成本）。
    run_daily(avoid_month_guard, g.avoid_trade_time)   # 空仓（默认 14:50 尾盘）


# ============================================================================
# 二、调仓调度
# ============================================================================
def rebalance_scheduler(context):
    """调仓日历调度：每月末调仓 + 回避月后的"恢复建仓" + 避险ETF年度再平衡

    实现要点：
      run_daily 仅在交易日触发；
      每月末最后一个交易日触发调仓（_is_last_trade_day_of_month）；
      同一月份只调仓一次（g.done_months 防重复）；
      避险 ETF 每年再平衡一次（等权分配 etf_target_pct 比例资金）；
      若 g.avoid_keep_rebalance = False，则落在回避月的那一期
      不建仓，顺延至回避月结束后的首个交易日执行。
    """
    today = context.current_dt.date()
    rebalanced = False          # 本次调度是否已执行过一次调仓

    mm = today.month
    end_month = g.rebalance_plan.get(mm)
    if end_month is None:
        return

    # ---------- 回避月内不调仓股票（由 avoid_month_guard 管理ETF） ----------
    # 回避月期间由 avoid_month_guard 将ETF加仓至100%，无需执行ETF年度再平衡
    if g.use_avoid_months and mm in g.avoid_months:
        return

    # ---------- 避险 ETF 年度再平衡（非回避月的交易日均可触发） ----------
    _etf_annual_rebalance(context, today)

    # ---------- 检查是否为本月最后交易日且本月尚未调仓 ----------
    if mm not in g.done_months and _is_last_trade_day_of_month(today):

        # ---------- 分支 A：调仓日也回避 -> 顺延至回避月后首个交易日 ----------
        if (not g.avoid_keep_rebalance) and (mm in g.avoid_months):
            tgt_month, tgt_year = mm, today.year
            for _ in range(12):                 # 跳过连续的回避月
                tgt_month = tgt_month % 12 + 1
                if tgt_month == 1:
                    tgt_year += 1
                if tgt_month not in g.avoid_months:
                    break
            if not (today.year == tgt_year and today.month == tgt_month):
                return
            if not _is_first_trade_day_of_month(today):
                return
            g.done_months.add(mm)
            g.rebalanced_dates.add(today)
            log.info('【调仓】%s 因回避月 %s 顺延，于回避月后首个交易日执行 %d 年 %d 月调仓'
                     % (today, g.avoid_months, today.year, mm))
            do_rebalance(context, today.year, end_month)
            rebalanced = True

        # ---------- 分支 B：常规月末调仓 ----------
        else:
            # 1~3 月用上年财报口径，4~12 月用当年口径
            year = today.year - 1 if mm <= 3 else today.year
            g.done_months.add(mm)
            g.rebalanced_dates.add(today)
            log.info('【调仓】%s 月末触发 %d 年 %d 月调仓（%d 期财报）'
                     % (today, year, mm, end_month))
            do_rebalance(context, year, end_month)
            rebalanced = True

    # ---------- 恢复建仓：离开回避月后的首个交易日，把资金从避险组合切回股票 ----------
    # 用 rebalanced 标志做互斥：若同一交易日已执行计划调仓（如顺延后的 5 月初），
    # 就绝不再走恢复分支，避免同一交易日重复调仓两次。
    if (not rebalanced) and g.use_avoid_months and g.avoid_mode \
            and (today.month not in g.avoid_months):
        y_off, em = _resume_period(today)
        log.info('【恢复建仓】%s 已离开回避月 %s，按 %d 年 %d 期财报口径重建股票仓位'
                 % (today, g.avoid_months, today.year + y_off, em))
        do_rebalance(context, today.year + y_off, em)
        g.rebalanced_dates.add(today)


def avoid_month_guard(context):
    """回避月避险（默认 1 月、4 月）：在回避窗口内尾盘把股票换成避险组合

    时点安排：
      本函数在 g.avoid_trade_time（默认 14:50 尾盘）运行，晚于调仓调度
      （g.trade_time，09:35），因此可直接读取 g.rebalanced_dates 判断
      "今日是否已调仓"，从而避免在调仓日与回避月重叠时出现"先清仓再买回"的重复交易。

    状态机（g.avoid_mode）：
      False -- 进入回避窗口 --> 卖出全部股票 + ETF加仓至100% --> True
      True  -- 离开回避月 --> 由 rebalance_scheduler 的"恢复建仓"分支切回 --> False
      True  -- 仍在回避窗口内 --> 直接返回，不产生任何委托（避免每日重复下单）

    与 _do_trade 的配合：
      - 非回避月：_do_trade 维持"90%股票+10%ETF"配置；
      - 回避月：本函数清仓股票并将ETF从10%加仓至100%；
      - 离开回避月：_do_trade 恢复为"90%股票+10%ETF"，并重置 avoid_mode。

    与研报的关系：
      本规则只做时间维度的风险回避，不改变因子定义、过滤链与选股数量。

    与防未来函数的关系：
      本函数只依据"当前日历"决定是否切换，不读取任何行情或财务数据，
      因此不涉及数据可见性问题，无需经过 _data_asof 闸门。
    """
    if not g.use_avoid_months:
        return

    today = context.current_dt.date()

    # 今日已触发计划调仓 -> 交由调仓逻辑接管，不重复交易
    if g.avoid_keep_rebalance and _rebalanced_today(today):
        return

    if not _in_avoid_window(today):
        return

    # 已处于回避模式 -> 每月只在窗口首次开启时切换一次，之后不再交易
    if g.avoid_mode:
        return

    if g.use_hedge_etf:
        _switch_to_hedge(context)
    else:
        if context.portfolio.positions:
            log.info('【回避月空仓】%s 处于回避窗口（回避月 %s），尾盘清仓'
                     % (today, g.avoid_months))
            _liquidate(context)
        g.avoid_mode = True


def _switch_to_hedge(context):
    """回避月避险切换：卖出全部股票，把资金加仓到 g.hedge_etfs（含已有的10%底仓）

    与 _do_trade 的关系：
      - _do_trade 在非回避月维持"90%股票+10%ETF"配置；
      - 本函数在回避月将股票清仓，把全部资金归入ETF（100%），
        已有的10%底仓通过 order_target_value 自然加仓，无需特殊处理。

    实现要点：
      - 先剔除不可交易的 ETF（停牌 / 代码不存在），按剩余数量等权，
        避免因个别 ETF 无法下单而导致资金闲置；
      - 若全部 ETF 都不可交易，则退化为持币，但仍标记 avoid_mode，
        避免每日重复重试；
      - 卖出时用 except_codes 保留 ETF 自身，防止无谓的来回交易。
    """
    cd = get_current_data()
    available = []
    for code in g.hedge_etfs:
        try:
            if cd[code].paused:
                continue
        except Exception:
            log.warning('【避险】ETF %s 无法访问（未上市或代码有误），本次跳过' % code)
            continue
        available.append(code)

    if not available:
        log.warning('【避险】避险 ETF 全部不可交易，本次退化为持币')
        _liquidate(context)
        g.avoid_mode = True
        return

    # 先清掉股票仓位（保留 ETF 自身）
    _liquidate(context, except_codes=available)

    # 等权买入（按切换后的总资产均分）
    value = context.portfolio.total_value / len(available)
    for code in available:
        order_target_value(code, value)

    g.avoid_mode = True
    log.info('【避险切换】%s 尾盘把资金等权配置到 %d 只 ETF，单只目标市值 %.0f 元'
             % (context.current_dt.date(), len(available), value))


def _etf_annual_rebalance(context, today):
    """避险 ETF 年度再平衡：每年将 etf_target_pct 资金等权分配到各 ETF

    触发条件：
      - 尚未执行过年度再平衡（g.last_etf_rebalance_date is None）；或
      - 距上次再平衡已超过 g.etf_rebalance_interval 天（默认365天）。

    实现要点：
      - 与月度调仓独立：无论是否在回避月均可执行；
      - 仅调整 ETF 仓位至等权，不影响股票持仓；
      - 若全部 ETF 不可交易，则跳过本次再平衡。
    """
    if g.last_etf_rebalance_date is not None:
        days_since = (today - g.last_etf_rebalance_date).days
        if days_since < g.etf_rebalance_interval:
            return

    cd = get_current_data()
    available = []
    for code in g.hedge_etfs:
        try:
            if not cd[code].paused:
                available.append(code)
        except Exception:
            pass

    if not available:
        log.warning('【ETF年度再平衡】全部 ETF 不可交易，跳过')
        return

    total = context.portfolio.total_value
    etf_total = total * g.etf_target_pct
    value = etf_total / len(available)
    for code in available:
        order_target_value(code, value)

    g.last_etf_rebalance_date = today
    log.info('【ETF年度再平衡】%s %d 只 ETF 等权分配 %.0f 元（总资产 %.0f%%）'
             % (today, len(available), value, g.etf_target_pct * 100))


def _rebalanced_today(today):
    """判断「今日」是否已执行过调仓（读取 scheduler 写入的 g.rebalanced_dates）

    为什么用 g.rebalanced_dates 而非 g.done_months：
      done_months 按月粒度记录（{1,2,...}），一旦写入某月，该月内后续交易日都会
      被误判为"今日已调仓"。但恢复建仓需要精确到「具体交易日」判断（避免同日
      重复调仓），故必须用 g.rebalanced_dates（实际调仓发生的交易日集合）精确判断。
    """
    return today in g.rebalanced_dates


# ============================================================================
# 三、核心调仓逻辑
# ============================================================================
def do_rebalance(context, year, end_month):
    """执行一次完整调仓：定报告期 → 定股票池 → 三重过滤 → 排序取前 N → 等权交易

    参数:
        year      : 调仓年份（决定报告期区间，而非收盘看数据日）
        end_month : 最新定期报告期所在月份（3 = 一季报，9 = 三季报）
    """
    # ---------- 1) 定位报告期（TTM 三期还原所需） ----------
    #   TTM(R)  = YTD(R)  + FY(R年-1) - YTD(R-1年)
    #   TTM(R1) = YTD(R1) + FY(R年-2) - YTD(R-2年)
    R = _quarter_end(year, end_month)          # 最新报告期
    R1 = _shift_year(R, -1)                    # 去年同期
    R2 = _shift_year(R, -2)                    # 前年同期
    FY1 = datetime.date(year - 1, 12, 31)      # 上一年年报
    FY2 = datetime.date(year - 2, 12, 31)      # 上上年年报
    log.info('【报告期】最新 %s ｜ 同比基准 %s ｜ 年报 %s / %s'
             % (R, R1, FY1, FY2))

    # ---------- 2) 锁定信息可见日（防未来函数第一道闸门） ----------
    as_of = _data_asof(context)
    _audit_future_data(context, as_of)

    # ---------- 3) 股票池 ----------
    universe = _get_universe(as_of)
    universe = _filter_basic(context, universe, as_of)
    if not universe:
        log.warning('【警告】基础过滤后股票池为空，本次调仓跳过')
        return

    # ---------- 4) 基本面粗筛（研报 Step2）----------
    df = _query_fundamentals(universe, as_of)
    if df.empty:
        log.info('【选股】无满足"营收增速 ≥ %.1f%%"的标的，清仓' % g.min_revenue_grow)
        _do_trade(context, [])
        return

    # ---------- 5) 计算 TTM 净利润同比增速（策略核心因子）----------
    growth = _calc_ttm_growth(
        _fetch_ytd_net_profit(df['code'].tolist(), [R, R1, R2, FY1, FY2], as_of),
        R, R1, R2, FY1, FY2
    )
    if growth.empty:
        log.warning('【警告】未取到财务数据，本次调仓跳过')
        return
    df = df.merge(growth, on='code', how='inner')
    df = df.dropna(subset=['ttm_growth'])
    if df.empty:
        log.info('【选股】因子有效样本为 0，清仓')
        _do_trade(context, [])
        return

    # ---------- 6) PEG 约束（研报 Step3）----------
    # PEG = PE(TTM) / 净利润增速(%)；增速为小数，故 ×100 转为百分数
    df['peg'] = df['pe_ratio'] / (df['ttm_growth'] * 100.0)
    mask = (df['peg'] > g.peg_low) & (df['peg'] <= g.peg_high)

    # 可选：限定在研报最优市值区间（61~113 亿）
    if g.use_cap_filter:
        mask &= (df['market_cap'] >= g.cap_low) & (df['market_cap'] <= g.cap_high)

    df = df[mask]
    if df.empty:
        log.info('【选股】PEG 过滤后无标的，清仓')
        _do_trade(context, [])
        return

    # ---------- 7) 按因子降序取前 N（研报 Step4）----------
    df = df.sort_values('ttm_growth', ascending=False)
    targets = df['code'].head(g.stock_num).tolist()

    # ---------- 8) 市场择时（可选，默认关闭）----------
    if not _market_timing_ok(as_of):
        log.info('【择时】指数位于 MA%d 之下，本期空仓' % g.timing_ma)
        targets = []

    # ---------- 9) 下单 ----------
    top = df.head(g.stock_num)
    for _, row in top.iterrows():
        log.info('  候选 %s | TTM净利润增速 %8.2f%% | PE %7.2f | PEG %5.2f | 市值 %8.1f 亿'
                 % (row['code'], row['ttm_growth'] * 100, row['pe_ratio'],
                    row['peg'], row['market_cap'] / 1e8))
    _do_trade(context, targets)


# ============================================================================
# 四、数据获取与防未来函数闸门
# ============================================================================
def _data_asof(context):
    """统一产出「信息可见日」as_of —— 所有决策数据的硬边界

    规则：
      1. 默认取 context.previous_date（上一交易日），从源头隔绝当日数据；
      2. g.data_lag_days 可再额外滞后 N 个交易日，用于规避"公告当日是否可见"争议；
      3. 内置断言 as_of < 当前交易日 —— 从机制上杜绝未来函数，
         任何人把 as_of 改成当前日都会立刻抛错，而不是静默回测出漂亮曲线。
    """
    as_of = context.previous_date

    if g.data_lag_days > 0:
        # get_trade_days 返回升序数组，days[0] 即 as_of 向前第 N 个交易日
        days = get_trade_days(end_date=as_of, count=g.data_lag_days + 1)
        if days is not None and len(days) > g.data_lag_days:
            as_of = days[0]

    if as_of >= context.current_dt.date():
        raise ValueError(
            '【防未来函数校验失败】as_of=%s 不早于当前交易日 %s，请检查 _data_asof / data_lag_days'
            % (as_of, context.current_dt.date()))
    return as_of


def _audit_future_data(context, as_of):
    """打印数据时点审计表，逐条核对每个取数点的可见性"""
    if not g.audit_future_data:
        return
    today = context.current_dt.date()
    log.info('====== 防未来函数审计 ======')
    log.info('  当前交易日          : %s' % today)
    log.info('  信息可见日 as_of     : %s   (相对 T-1 再滞后 %d 个交易日)'
             % (as_of, g.data_lag_days))
    log.info('  指数成分股          : get_index_stocks(date=%s)' % as_of)
    log.info('  估值 / 营收增速      : get_fundamentals(date=%s)' % as_of)
    log.info('  定期报告累计净利润    : finance.STK_INCOME_STATEMENT'
             ', pub_date <= %s' % as_of)
    log.info('  指数均线            : get_price(end_date=%s)' % as_of)
    log.info('  上市日期            : get_all_securities(date=%s)' % as_of)
    log.info('  停牌/ST/涨跌停       : get_current_data() 当日实时 '
             '—— 仅用于交易可行性，不参与排序')
    log.info('============================')


def _get_universe(as_of):
    """获取股票池（中证全指成分股）；指数取数失败时回退为全市场"""
    try:
        stocks = get_index_stocks(g.index_code, date=as_of)
        if stocks:
            return list(stocks)
    except Exception as e:
        log.warning('【警告】%s 成分股获取失败(%s)，回退为全市场' % (g.index_code, e))
    return list(get_all_securities('stock', date=as_of).index)


def _query_fundamentals(codes, as_of, batch=800):
    """基本面粗筛：营收同比增速 >= 门槛 且 PE > 0

    说明：
      - 聚宽 indicator 表的同比增速为【单季度同比】口径（与该表默认单季披露一致），
        与研报所用的 Wind 累计口径存在细微差异，属于平台数据口径限制；
      - 分批查询，规避 get_fundamentals 单次返回行数上限。
    """
    frames = []
    for i in range(0, len(codes), batch):
        chunk = codes[i:i + batch]
        q = query(
            valuation.code,
            valuation.pe_ratio,               # PE(TTM)
            valuation.market_cap,             # 总市值（原值，单位：元）
            valuation.circulating_market_cap,  # 流通市值
            indicator.inc_revenue_year_on_year   # 营业收入同比增长率(%)
        ).filter(
            valuation.code.in_(chunk),
            indicator.inc_revenue_year_on_year >= g.min_revenue_grow,
            valuation.pe_ratio > 0            # 排除亏损股（PE 无意义）
        )
        d = get_fundamentals(q, date=as_of)
        if d is not None and not d.empty:
            frames.append(d)

    if not frames:
        return pd.DataFrame(columns=['code', 'pe_ratio', 'market_cap',
                                     'circulating_market_cap',
                                     'inc_revenue_year_on_year'])
    return pd.concat(frames, ignore_index=True)


def _fetch_ytd_net_profit(codes, end_dates, as_of):
    """从合并利润表取定期报告【累计】净利润（YTD，含少数股东损益）

    为什么用 finance.STK_INCOME_STATEMENT 而不是 income 表：
      该表是上市公司定期公告披露的原始报表数据，口径明确为"年初至今累计"，
      可直接套用 TTM 还原公式；而 get_fundamentals 的 income/indicator 表
      口径曾在单季/累计之间调整，用于 TTM 还原存在口径风险。

    注意：
      - 逐个报告期查询，避免 date 字段使用 in_() 带来的类型匹配风险，
        同时每组返回行数远低于 finance.run_query 单次 5000 行的上限；
      - 同一 (code, end_date) 可能因财报修正存在多版本：取公告日最新版本，
        并优先保留 report_type = 0（本期）记录；
      - pub_date <= as_of 严格约束，杜绝未来函数；
      - 取数后再做一次 pandas 侧校验（纵深防御），拦截任何漏网的未来公告。
    """
    as_of_str = as_of.strftime('%Y-%m-%d')
    frames = []

    for ed in end_dates:
        ed_str = ed.strftime('%Y-%m-%d')
        for i in range(0, len(codes), 2000):
            chunk = codes[i:i + 2000]
            q = query(
                finance.STK_INCOME_STATEMENT.code,
                finance.STK_INCOME_STATEMENT.end_date,
                finance.STK_INCOME_STATEMENT.net_profit,
                finance.STK_INCOME_STATEMENT.pub_date,
                finance.STK_INCOME_STATEMENT.report_type
            ).filter(
                finance.STK_INCOME_STATEMENT.code.in_(chunk),
                finance.STK_INCOME_STATEMENT.end_date == ed_str,
                finance.STK_INCOME_STATEMENT.pub_date <= as_of_str
            )
            d = finance.run_query(q)
            if d is not None and not d.empty:
                frames.append(d)

    if not frames:
        return pd.DataFrame(columns=['code', 'end_date', 'net_profit'])

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=['net_profit', 'end_date'])

    # 二次校验（纵深防御）：即使数据库侧过滤失效，也绝不放过未来公告
    if not df.empty and 'pub_date' in df.columns:
        pub = pd.to_datetime(df['pub_date'])
        leaked = int((pub > pd.Timestamp(as_of)).sum())
        if leaked:
            log.warning('【防未来函数】拦截 %d 条 pub_date > as_of(%s) 的财务记录'
                        % (leaked, as_of))
            df = df[pub <= pd.Timestamp(as_of)]

    # 同一报告期多版本 -> 取公告日最新
    df = df.sort_values('pub_date').drop_duplicates(
        ['code', 'end_date', 'report_type'], keep='last')
    # report_type = 0（本期）优先
    df = df.sort_values('report_type').drop_duplicates(
        ['code', 'end_date'], keep='first')
    return df[['code', 'end_date', 'net_profit']]


# ============================================================================
# 五、因子计算
# ============================================================================
def _calc_ttm_growth(df, R, R1, R2, FY1, FY2):
    """由累计净利润还原 TTM 净利润并计算同比增速

        TTM(R)  = YTD(R)  + FY(上年年报) - YTD(去年同期)
        TTM(R1) = YTD(R1) + FY(前年年报) - YTD(前年同期)
        增速    = (TTM(R) - TTM(R1)) / |TTM(R1)|

    分母取绝对值，与研报公式一致（可正确处理同比基数亏损转盈利的情形）。
    返回 DataFrame[code, ttm_growth]。
    """
    empty = pd.DataFrame(columns=['code', 'ttm_growth'])
    if df is None or df.empty:
        return empty

    df = df.copy()
    df['end_date'] = pd.to_datetime(df['end_date']).dt.strftime('%Y-%m-%d')

    pv = df.pivot_table(index='code', columns='end_date',
                        values='net_profit', aggfunc='last')
    cols = [d.strftime('%Y-%m-%d') for d in (R, R1, R2, FY1, FY2)]
    for c in cols:
        if c not in pv.columns:
            pv[c] = np.nan

    ytd_r, ytd_r1, ytd_r2, fy1, fy2 = (pv[c] for c in cols)

    ttm_now = ytd_r + fy1 - ytd_r1
    ttm_prev = ytd_r1 + fy2 - ytd_r2

    denom = ttm_prev.abs()
    # 基期规模过小（绝对值 < 10 万元）时增速数值失真，直接置为 NaN 剔除
    valid = denom >= g.min_prev_profit
    growth = np.where(valid, (ttm_now - ttm_prev) / denom.replace(0, np.nan), np.nan)

    return pd.DataFrame({'code': pv.index, 'ttm_growth': growth})


# ============================================================================
# 六、过滤器
# ============================================================================
def _filter_basic(context, stocks, as_of):
    """基础过滤：剔除停牌、ST/退市、涨跌停、次新股

    时点约定（防未来函数的关键分界）：
      - 上市日期 -> get_all_securities(date=as_of)，走信息可见日，属"决策数据"；
      - 停牌 / ST / 涨跌停 -> get_current_data() 当日实时。
        这三项属于"交易可行性数据"：不滞后才能反映今天到底能不能下单。
        它们只决定"这只股票能不能买"，绝不参与因子排序或打分，
        因此不构成未来函数（但绝不能把当日价格交给排序逻辑使用）。
    """
    cd = get_current_data()

    sec = get_all_securities('stock', date=as_of)
    start_map = sec['start_date'].to_dict()

    out = []
    for s in stocks:
        d = cd[s]
        if d.paused:                       # 停牌（当日状态）
            continue
        if d.is_st:                        # ST / *ST（当日状态）
            continue
        name = d.name or ''
        if ('ST' in name.upper()) or ('退' in name):
            continue
        if d.last_price <= 0:              # 无有效价格
            continue
        if d.last_price >= d.high_limit:   # 涨停无法买入（当日状态）
            continue
        if d.last_price <= d.low_limit:    # 跌停无法买入（当日状态）
            continue
        st = start_map.get(s)
        if st is not None and (as_of - st).days < g.min_listed_days:
            continue
        out.append(s)
    return out


# ============================================================================
# 七、交易执行与择时
# ============================================================================
def _liquidate(context, except_codes=()):
    """清仓：卖出除 except_codes 之外的全部持仓

    被 _do_trade（剔除不在目标列表中的持仓）与 avoid_month_guard（整仓清空）复用。
    """
    except_set = set(except_codes)
    for code in list(context.portfolio.positions.keys()):
        if code not in except_set:
            order_target_value(code, 0)


def _do_trade(context, targets):
    """等权调仓：卖出非目标持仓，买入目标股票，始终保留 etf_target_pct 在避险 ETF

    资产配置：
      - targets 非空：股票90%（等权）+ ETF 10%（等权）
      - targets 为空：仅保留 ETF 10%，其余为现金
      - 回避月内：avoid_month_guard 会将股票清仓并加仓 ETF 至100%，
        离开回避月后由本函数恢复为 90/10 配置。

    防未来函数：本函数不读取任何行情或财务数据，只读取 portfolio 状态。
    """
    cd = get_current_data()
    today = context.current_dt.date()
    etf_pct = g.etf_target_pct  # 0.10

    # --- 1) 确定可交易的避险 ETF ---
    available_etfs = []
    for code in g.hedge_etfs:
        try:
            if not cd[code].paused:
                available_etfs.append(code)
        except Exception:
            pass

    # --- 2) 卖出不在目标列表且非避险 ETF 的持仓 ---
    etf_set = set(available_etfs)
    target_set = set(targets)
    sell_codes = [c for c in context.portfolio.positions
                  if c not in target_set and c not in etf_set]
    for code in sell_codes:
        order_target_value(code, 0)

    g.avoid_mode = False

    total = context.portfolio.total_value

    # --- 3) 调整避险 ETF 至目标比例（等权）---
    if available_etfs:
        etf_target_each = total * etf_pct / len(available_etfs)
        for code in available_etfs:
            order_target_value(code, etf_target_each)

    # --- 4) 等权买入目标股票（占总资产 1-etf_pct）---
    if targets:
        stock_total = total * (1.0 - etf_pct)
        value = stock_total / len(targets)
        for code in targets:
            order_target_value(code, value)
        log.info('【持仓】股票 %d 只，单只 %.0f 元 ｜ ETF %d 只，单只 %.0f 元（%.0f%%）'
                 % (len(targets), value, len(available_etfs),
                    total * etf_pct / max(len(available_etfs), 1), etf_pct * 100))
    else:
        log.info('【持仓】无股票目标，仅保留 %d 只避险 ETF（%.0f%%）'
                 % (len(available_etfs), etf_pct * 100))


def _market_timing_ok(as_of):
    """择时开关（默认关闭）：中证全指收盘价站上 MA20 才允许建仓

    时点：显式使用 end_date=as_of，取截至信息可见日的均线，
          不使用 attribute_history 的隐式时点，便于审计。
    """
    if not g.use_timing:
        return True
    try:
        df = get_price(g.index_code, end_date=as_of, count=g.timing_ma,
                       frequency='1d', fields=['close'], panel=False)
        if df is None or len(df) < g.timing_ma:
            log.warning('【择时】指数数据不足 %d 根，本次按通过处理' % g.timing_ma)
            return True
        return float(df['close'].iloc[-1]) > float(df['close'].mean())
    except Exception as e:
        log.warning('【择时】取数失败(%s)，本次按通过处理' % e)
        return True


# ============================================================================
# 八、工具函数
# ============================================================================
_QUARTER_END = {3: (3, 31), 6: (6, 30), 9: (9, 30), 12: (12, 31)}


def _quarter_end(year, month):
    """返回指定年、指定季末月份对应的报告期日期"""
    m, d = _QUARTER_END[month]
    return datetime.date(year, m, d)


def _shift_year(ts, n):
    """报告期按年平移（本策略仅使用 3-31 / 6-30 / 9-30 / 12-31，无闰日风险）"""
    return ts.replace(year=ts.year + n)


def _is_first_trade_day_of_month(d):
    """判断 d 是否为其所在月的第一个交易日

    取截至 d 的最后两个交易日，若二者跨月且次日即 d，则 d 为当月首个交易日。
    失败时打警告而非静默 —— 日历判定一旦静默失效，会连带让"提前切换"等
    依赖它的规则悄悄失灵。
    """
    try:
        days = get_trade_days(end_date=d, count=2)
    except Exception as e:
        log.warning('【日历】get_trade_days(end_date=%s, count=2) 失败：%s' % (d, e))
        return False
    if days is None or len(days) < 2:
        log.warning('【日历】get_trade_days 返回不足 2 个交易日，无法判定 %s 是否月初' % d)
        return False
    return days[0].month != days[-1].month and days[-1] == d


def _is_last_trade_day_of_month(d):
    """判断 d 是否为其所在月的最后一个交易日

    双路径实现，任一路径失败都不会静默返回 False：
      路径一（主）：get_trade_days(start_date=d, count=2)
                    —— 聚宽文档支持「start_date(含) 往后 count 个交易日」，
                       若第二个交易日已跨月，则 d 为当月最后一个交易日；
      路径二（回退）：get_trade_days(end_date=d+31天, count=25)
                    —— 只用 end_date + count 形态，向前取一整段日历后判断
                       d 之后是否还存在本月的交易日。
    """
    # ---------- 路径一：向后看点（主）----------
    try:
        days = get_trade_days(start_date=d, count=2)
        if days is not None and len(days) >= 2 and days[0] == d:
            return days[1].month != d.month
        log.warning('【日历】路径一返回异常（%s），改用回退路径判定 %s'
                    % ('None' if days is None else list(days), d))
    except Exception as e:
        log.warning('【日历】路径一 get_trade_days(start_date=%s, count=2) 失败：%s，改用回退路径'
                    % (d, e))

    # ---------- 路径二：向前看点（回退）----------
    try:
        end = d + datetime.timedelta(days=31)
        days = get_trade_days(end_date=end, count=25)
        if days is not None and len(days) > 0:
            nxt = [x for x in days if x > d]
            return (not nxt) or (nxt[0].month != d.month)
        log.warning('【日历】路径二返回空，无法判定 %s 是否月末交易日' % d)
    except Exception as e:
        log.warning('【日历】路径二 get_trade_days(end_date=%s) 也失败：%s' % (end, e))

    log.warning('【日历】两条路径均无法判定 %s 是否为月末交易日，本次按"非月末"处理' % d)
    return False


def _in_avoid_window(today):
    """判断 today 是否落在"回避月空仓窗口"内

    窗口定义：
      - 回避月（g.avoid_months）内的任一交易日；或
      - g.avoid_exit_ahead 为 True 时，回避月前一月的最后一个交易日
        （提前一日切换，不把月末隔夜跳空风险带进回避月）。
    """
    if today.month in g.avoid_months:
        return True
    if g.avoid_exit_ahead and _is_last_trade_day_of_month(today):
        nxt = today.month % 12 + 1
        if nxt in g.avoid_months:
            return True
    return False


def _resume_period(today):
    """恢复建仓时采用哪个定期报告期：返回 (年份偏移, 报告期月份)

    按"法定披露截止日"推定当前时点最早可用的定期报告，避免用到未披露的数据：
        年报 / 一季报 截止 4/30 ｜ 半年报 截止 8/31 ｜ 三季报 截止 10/31

    因此：
        2 月恢复 -> 上年三季报（9-30）：年报此时仍在披露期，取年报会大面积取空；
        5 月恢复 -> 当年一季报（3-31）：4/30 之后已基本披露完。
    这个映射与 g.avoid_months 的具体取值无关，任何"离开回避月即恢复"的场景都适用。
    """
    if today.month <= 4:
        return -1, 9          # 用上年三季报
    if today.month <= 8:
        return 0, 3           # 用当年一季报
    if today.month <= 10:
        return 0, 6           # 用当年半年报
    return 0, 9               # 用当年三季报

