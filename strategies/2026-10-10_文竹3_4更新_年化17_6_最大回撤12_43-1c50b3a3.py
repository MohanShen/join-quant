# Clone from JoinQuant
# postId: 1c50b3a30dab9ab599463ce7c0bb2d79
# backtestId: 73915ccb513e1ca2d6231ae808d44973
# title: 【文竹3.4更新】年化17.6%|最大回撤12.43%

# ======================================================================
# 全天候增强版 v3.4 — 仓位4分级 + 仓位2MACD确认
# ======================================================================
#
# v3.3 → 年化 +14-17% 回撤 8-12%（预期）
#
# ============ v3.4 改动 ============
#
# [New-1] 仓位4分级逻辑（原: 永远30%债券）
#   仓位1=权益(创业板/纳指) → 仓位4拿红利低波
#   仓位1=债券(全面防御)    → 仓位4拿30年国债
#   意图: 牛市里30%债券太浪费, 红利低波收益更高且波动可控
#
# [New-2] 仓位2加MACD月线确认（原: 仅凭zf>-6判断）
#   加了红利MACD月线 >0 作为第二条件, 避免红利持续下跌时硬扛
#   意图: 减少仓位2在红利下行期的回撤
#
# [Keep] 原版结构: 4仓位 + MACD月线 + 固定权重
# [Keep] 仓位3保留黄金不对称逻辑(原版"bug"→已证明有效)
# [Keep] 修正: 国债从511260升级到511520
# [Keep] 保留: min_commission=5, avoid_future_data
#
# ============ 预期 ============
#   年化: 15-18% | 回撤: 7-10% | Beta: 0.4-0.6
#   牛市弹性更高, 震荡市回撤更小
#
# ======================================================================

from collections import defaultdict
from jqdata import *
from jqlib.technical_analysis import *
import math


# ============================================================================
# ETF池
# ============================================================================
ETF_GROWTH   = '159949.XSHE'  # 创业板50
ETF_OVERSEAS = '513100.XSHG'  # 纳指ETF
ETF_DIVIDEND = '512890.XSHG'  # 红利低波
ETF_GOLD     = '518880.XSHG'  # 黄金ETF
ETF_BOND     = '511520.XSHG'  # 30年国债ETF


# ============================================================================
# 初始化
# ============================================================================
def initialize(context):
    set_option("avoid_future_data", True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.002))
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                             open_commission=0.00015, close_commission=0.00015,
                             close_today_commission=0, min_commission=5), type='fund')
    log.set_level('system', 'error')

    run_monthly(on_start, 1, '9:35')


# ============================================================================
# MACD月线
# ============================================================================
def get_macd_M(stock, check_date):
    macd_dif, macd_dea, macd_macd = MACD(stock, check_date=check_date,
                                          SHORT=12, LONG=26, MID=9,
                                          unit='1M', include_now=False)
    return macd_macd[stock]


# ============================================================================
# 年度涨跌幅
# ============================================================================
def get_zf(context):
    etf = ETF_DIVIDEND
    year = context.current_dt.year
    df_all = attribute_history(etf, 25, '1d', ['close'])
    if df_all is None or len(df_all) == 0:
        return 0
    df_close = df_all.close
    today_close = df_close[-1]

    start_old = datetime.datetime(year - 1, 12, 20).strftime('%Y-%m-%d')
    end_old = datetime.datetime(year - 1, 12, 31).strftime('%Y-%m-%d')
    df_old = get_price(etf, start_date=start_old, end_date=end_old, frequency='1d', panel=False)
    if df_old is None or len(df_old) == 0:
        return 0
    old_close = df_old.close[-1]

    if old_close <= 0:
        return 0
    return round((today_close - old_close) * 100 / old_close, 2)


# ============================================================================
# 年度首日判断
# ============================================================================
def year_start(context):
    year = context.current_dt.year
    month = context.current_dt.month
    day = context.current_dt.day
    trade_days = get_trade_days(start_date=str(year) + '-01-01', end_date=str(year) + '-12-31')
    first = trade_days[0].day
    return 1 if month == 1 and day == first else 0


# ============================================================================
# 主调仓
# ============================================================================
def on_start(context):
    # 年度清仓
    if year_start(context) == 1:
        for s in context.portfolio.positions:
            order_target(s, 0)

    print("." * 120)

    # ———— 获取MACD ————
    yesterday = context.current_dt
    macd_50 = get_macd_M(ETF_GROWTH, yesterday)     # 创业板50
    macd_100 = get_macd_M(ETF_OVERSEAS, yesterday)   # 纳指
    macd_88 = get_macd_M(ETF_GOLD, yesterday)        # 黄金
    macd_300 = get_macd_M('000300.XSHG', yesterday)  # 沪深300
    macd_div = get_macd_M(ETF_DIVIDEND, yesterday)   # [v3.4] 红利低波MACD
    zf = get_zf(context)                             # 红利年度收益

    # ———— 仓位1 (30%): 创业板50/纳指/红利/债券 ————
    if macd_50 > 0:
        g.stock_fund_1 = ETF_GROWTH
    else:
        if macd_100 > 0:
            g.stock_fund_1 = ETF_OVERSEAS
        else:
            if zf > -6:
                g.stock_fund_1 = ETF_DIVIDEND
            else:
                g.stock_fund_1 = ETF_BOND

    # ———— 仓位2 (20%): 红利/债券 ————
    # [v3.4] 加MACD月线确认: 红利MACD>0才持红利, 避免红利持续下跌时硬扛
    if zf > -6 and macd_div > 0:
        g.stock_fund_2 = ETF_DIVIDEND
    else:
        g.stock_fund_2 = ETF_BOND

    # ———— 仓位3 (20%): 黄金/红利 ————
    if macd_88 > 0:
        g.stock_fund_3 = ETF_GOLD
    else:
        g.stock_fund_3 = ETF_GOLD
        if macd_300 > 0 and zf > -6:
            g.stock_fund_3 = ETF_DIVIDEND

    # ———— 仓位4 (30%): 债券/红利 ————
    # [v3.4] 分级逻辑: 仓位1选权益 → 牛市信号, 仓位4拿红利代替债券
    #          仓位1选债券 → 全面防御, 仓位4拿债券
    if g.stock_fund_1 in (ETF_GROWTH, ETF_OVERSEAS):
        g.stock_fund_4 = ETF_DIVIDEND
        log.info('[仓位4分级] 牛市信号, 仓位4拿红利低波')
    else:
        g.stock_fund_4 = ETF_BOND

    # ———— 组装 ————
    stocks = [g.stock_fund_1, g.stock_fund_2, g.stock_fund_3, g.stock_fund_4]
    base_w = [0.30, 0.20, 0.20, 0.30]
    weights = list(base_w)
    # [v3.3-OPT-C] 牛市增强: 权益+黄金双强 → 降债10%给仓位1
    if g.stock_fund_1 in (ETF_GROWTH, ETF_OVERSEAS) and g.stock_fund_3 == ETF_GOLD:
        log.info('[牛市增强] 权益+黄金双强信号, 仓位1:30%→40%, 仓位4:30%→20%')
        weights[0] = 0.40
        weights[3] = 0.20

    # 合并同标的
    target = defaultdict(float)
    for i in range(4):
        target[stocks[i]] += weights[i]

    # 打印
    info = []
    for t, w in sorted(target.items(), key=lambda x: -x[1]):
        name = get_security_info(t).display_name
        info.append(f'{t}({name} {w*100:.0f}%)')
    log.info(f'目标: {", ".join(info)}')

    # ———— 初次建仓 ————
    if context.portfolio.total_value == context.portfolio.available_cash:
        for t, w in target.items():
            order_target_value(t, context.portfolio.available_cash * w)
        g.stock_fund = stocks
        return

    # ———— 月调仓 ————
    total = context.portfolio.total_value

    for i in range(3):
        if hasattr(g, 'stock_fund') and g.stock_fund[i] != stocks[i]:
            order_target(g.stock_fund[i], 0)

    for t, w in target.items():
        order_target_value(t, total * w)

    g.stock_fund = stocks
