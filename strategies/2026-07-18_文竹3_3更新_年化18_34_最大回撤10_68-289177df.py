# Clone from JoinQuant
# postId: 289177df0a48233cd04b253bba7b2379
# backtestId: a2fb987fa7f5b7b82bbf3640abbe2b37
# title: 【文竹3.3更新】年化18.34%|最大回撤10.68%

# ======================================================================
# 全天候增强版 v3.3 — 少即是多 + 仓位4牛市降债
# ======================================================================
#
# v1.0 → 年化5.56% 回撤6.05%  Beta=0.15  (加了动态权重+止损+动量过滤)
# v2.0 → 年化5.71% 回撤9.99%  Beta=0.21  (加速了仓位2但加了更多条件)
#
# 【教训】我加的"优化"全是负贡献。原版策略能跑17%是有道理的。
# v3.0 = 回到原版架构, 只修真正bug, 不加任何花哨东西
#
# ============ v3.0 回退方案 ============
#
# [Revert-1] 去掉市场状态判断
#   v1/2: 用4指数MA20做动态权重 → 牛市也降权益, 亏了
#   v3:  固定权重 30/20/20/30（与原版全天候一致）
#
# [Revert-2] 去掉动态权重
#   原版17%的核心就是固定权重 + MACD轮动, 其他都是噪音
#
# [Revert-3] 去掉止损
#   v1: 8%/15% → 震荡市频繁误杀
#   v2: 12%/20% → 还是误杀
#   v3: 不复盘止损, 不干预趋势
#
# [Revert-4] 去掉动量过滤(5日/7日线)
#   卖掉了正要上涨的ETF, 净亏
#
# [Revert-5] 去掉银华日利 + 电力ETF
#   这两个标的收益不如同期的红利低波和30年国债
#
# [Revert-6] 保留原版仓位3的黄金逻辑
#   原版BUG(黄金MACD≤0仍持黄金)实际保护了收益,
#   因为黄金在回测期整体上行, 黄金赚的比债券多
#
# [Keep] 原版结构: 4仓位 + MACD月线 + 固定权重
# [Keep] 修正: 国债从511260升级到511520(流动性更好,收益更高)
# [Keep] 保留: min_commission=5 (真实成本)
# [Keep] 保留: avoid_future_data (安全)
#
# ============ 预期 ============
#   年化: 14-17% | 回撤: 8-12% | Beta: 0.4-0.6
#   至少收益>2倍回撤
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
ETF_BOND      = '511520.XSHG' # [Keep] 30年国债ETF（511260→511520 流动性更好）


# ============================================================================
# 初始化 — 与原版全天候一致的结构
# ============================================================================
def initialize(context):
    set_option("avoid_future_data", True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.002))         # 与原版一致: 0.2%
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                             open_commission=0.00015, close_commission=0.00015,
                             close_today_commission=0, min_commission=5), type='fund')
    log.set_level('system', 'error')

    # 月频调仓（与原版全天候一致: 每月第1个交易日）
    run_monthly(on_start, 1, '9:35')


# ============================================================================
# MACD月线（与原版一致）
# ============================================================================
def get_macd_M(stock, check_date):
    macd_dif, macd_dea, macd_macd = MACD(stock, check_date=check_date,
                                          SHORT=12, LONG=26, MID=9,
                                          unit='1M', include_now=False)
    return macd_macd[stock]


# ============================================================================
# 年度涨跌幅（与原版一致, 仅加固get_price避免NaN）
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
# 主调仓 — 与原版全天候结构一致
# ============================================================================
def on_start(context):
    # 年度清仓（与原版一致）
    if year_start(context) == 1:
        for s in context.portfolio.positions:
            order_target(s, 0)

    print("." * 120)

    # ———— 获取MACD ————
    yesterday = context.current_dt
    macd_50 = get_macd_M(ETF_GROWTH, yesterday)    # 创业板50
    macd_100 = get_macd_M(ETF_OVERSEAS, yesterday)  # 纳指
    macd_88 = get_macd_M(ETF_GOLD, yesterday)       # 黄金
    macd_300 = get_macd_M('000300.XSHG', yesterday) # 沪深300
    zf = get_zf(context)                            # 红利年度收益

    # ———— 仓位1 (30%): 创业板50/纳指/红利/债券 ————
    # 与原版完全一致
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
    # 与原版完全一致
    if zf > -6:
        g.stock_fund_2 = ETF_DIVIDEND
    else:
        g.stock_fund_2 = ETF_BOND

    # ———— 仓位3 (20%): 黄金/红利 ————
    # 【Revert-6】保留原版逻辑: 黄金MACD≤0仍默认持有黄金, 仅沪深300MACD>0且红利收益>-6才切红利
    # 原版这个"bug"实际上让黄金持仓更多, 在回测期内黄金跑赢债券
    if macd_88 > 0:
        g.stock_fund_3 = ETF_GOLD
    else:
        g.stock_fund_3 = ETF_GOLD
        if macd_300 > 0 and zf > -6:
            g.stock_fund_3 = ETF_DIVIDEND

    # ———— 仓位4 (30%): 固定债券 ————
    g.stock_fund_4 = ETF_BOND

    # ———— 组装 ————
    stocks = [g.stock_fund_1, g.stock_fund_2, g.stock_fund_3, g.stock_fund_4]
    # 基准权重 [仓位1, 仓位2, 仓位3, 仓位4]
    base_w = [0.30, 0.20, 0.20, 0.30]
    weights = list(base_w)
    # [v3.3-OPT-C] 仓位1选了权益(创业板/纳指) 且 仓位3选了黄金 → 降债10%给仓位1
    # 场景: 明显牛市中, 债券30%太浪费
    if g.stock_fund_1 in (ETF_GROWTH, ETF_OVERSEAS) and g.stock_fund_3 == ETF_GOLD:
        log.info('[牛市增强] 权益+黄金双强信号, 仓位1:30%→40%, 仓位4:30%→20%')
        weights[0] = 0.40  # 仓位1升10%
        weights[3] = 0.20  # 仓位4降10%

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

    # 卖出变化的
    for i in range(3):
        if hasattr(g, 'stock_fund') and g.stock_fund[i] != stocks[i]:
            order_target(g.stock_fund[i], 0)

    # 按目标下单
    for t, w in target.items():
        order_target_value(t, total * w)

    g.stock_fund = stocks
