# Clone from JoinQuant
# postId: f4a5f8e113063718835d84cddef5de01
# backtestId: 06cf1479b3b5701a109293ca9c15db7f
# title: 风险平价后的“全天候”，现金替代组合

# 克隆自聚宽文章：https://www.joinquant.com/post/80781
# 标题：全天候养老增强策略
# 作者：狍狍

# 克隆自聚宽文章：https://www.joinquant.com/post/80498
# 标题：全天候增强策略：ETF轮动 + MACD择时的稳健配置
# 作者：资金流入
# 修改：
#   1. 第4仓国债20%，第5仓豆粕ETF 10%，第6仓南方原油ETF 10%
#   2. 使用 order_target_value 按目标市值再平衡
#   3. 年度/月度/阈值再平衡开关，调仓不清仓，直接调整持仓比例
#   4. 阈值再平衡，默认 5%
#   5. 买入失败重试：11:00、14:30 重试，连续 3 个交易日买不进则转银华日利

import math
import datetime
from collections import defaultdict
from jqdata import *
from jqlib.technical_analysis import *


# 初始化，回测开始时执行
def initialize(context):
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 设置滑点
    set_slippage(FixedSlippage(0.002))
    # 设置交易成本
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, close_commission=0.0002, close_today_commission=0,
                  min_commission=5), type='fund')
    # 过滤一定级别的日志
    log.set_level('system', 'error')
    log.set_level('order', 'error')

    # ========== 再平衡开关 ==========
    # 年度再平衡：每年第一个交易日是否按目标比例调整持仓
    g.enable_annual_rebalance = True
    # 月度再平衡：每月第一个交易日是否检查并调整持仓
    g.enable_monthly_rebalance = True
    # 阈值再平衡：开启后，月度再平衡只在偏离超过阈值时才执行
    g.enable_threshold_rebalance = True
    # 阈值：5%
    g.rebalance_threshold = 0.05

    # ========== 重试买入配置 ==========
    # 待处理标的：{code: {'target': 目标市值, 'days': 已尝试的交易日集合}}
    g.pending_info = {}
    # 连续买不进的交易日数，达到该值则改用银华日利
    g.max_retry_days = 3
    # 兜底标的：银华日利货币 ETF
    g.fallback_code = '511880.XSHG'

    # 每月第1个交易日早盘 9:35 执行主调仓
    run_monthly(on_start, 1, '9:35')
    # 每天 11:00、14:30 执行重试买入
    run_daily(retry_buy, '11:00')
    run_daily(retry_buy, '14:30')


# ---------- 价格有效性校验 ----------
def get_valid_price(cdata, code):
    """
    返回有效价格；若价格无效（None / NaN / <=0），返回 None
    """
    try:
        price = cdata[code].last_price
        if price is None:
            return None
        if isinstance(price, float) and math.isnan(price):
            return None
        if price <= 0:
            return None
        return price
    except Exception:
        return None


# ---------- 判断是否需要再平衡 ----------
def need_rebalance(context, target_values, threshold):
    """
    计算当前持仓与目标持仓的最大偏离度。
    偏离度 = |当前市值 - 目标市值| / 总资产。
    如果最大偏离度 > 阈值，返回 True。
    """
    total_value = context.portfolio.total_value
    if total_value <= 0:
        return False

    # 所有相关标的：目标持仓 + 当前持仓
    codes = set(target_values.keys()) | set(context.portfolio.positions.keys())

    max_dev = 0.0
    for code in codes:
        current_value = 0.0
        if code in context.portfolio.positions:
            current_value = context.portfolio.positions[code].value
        target_value = target_values.get(code, 0.0)
        dev = abs(current_value - target_value) / total_value
        if dev > max_dev:
            max_dev = dev

    log.info(f"当前最大偏离度: {max_dev * 100:.2f}%，阈值: {threshold * 100:.2f}%")
    return max_dev > threshold


# ---------- 逆波动率（风险平价近似） ----------
def _vol(code, n=120):
    try:
        df = attribute_history(code, n, '1d', ['close'], skip_paused=True)
        r = df['close'].pct_change().dropna()
        if len(r) < 20:
            return None
        return float(r.std() * (252 ** 0.5))
    except Exception:
        return None


def inv_vol_split(codes, total, cap=None, floor=None):
    """按 1/vol 把 total 分配到 codes；带可选上下限（capped water-filling）。"""
    n = len(codes)
    inv = []
    for c in codes:
        v = _vol(c, 120)
        inv.append(1.0 / v if (v and v > 1e-6) else 0.0)
    if sum(inv) <= 0:
        return [total / n] * n
    lo = floor if floor else 0.0
    hi = cap if cap else total
    w = [lo] * n
    free = list(range(n))
    rem = total - lo * n
    while free and rem > 1e-12:
        s = sum(inv[i] for i in free)
        if s <= 0:
            for i in free:
                w[i] += rem / len(free)
            break
        newly = []
        for i in free:
            add = rem * inv[i] / s
            if w[i] + add > hi:
                rem -= (hi - w[i])
                w[i] = hi
                newly.append(i)
        if not newly:
            for i in free:
                w[i] += rem * inv[i] / s
            rem = 0.0
        free = [i for i in free if i not in newly]
    return w


# ---------- 主调仓函数 ----------
def on_start(context):
    print("." * 120)

    # 1. 计算目标持仓
    yesterday_macd = context.current_dt
    macd_300 = get_macd_M('000300.XSHG', yesterday_macd)  # 沪深300
    macd_100 = get_macd_M('513100.XSHG', yesterday_macd)  # 纳斯达克
    macd_50 = get_macd_M('159949.XSHE', yesterday_macd)   # 创业板50
    macd_88 = get_macd_M('518880.XSHG', yesterday_macd)   # 黄金

    # 1 进攻仓（20%）
    if macd_50 > 0:
        g.stock_fund_1 = '159949.XSHE'  # 创业板50
    else:
        if macd_100 > 0:
            g.stock_fund_1 = '513100.XSHG'  # 纳斯达克
        else:
            if get_zf(context) > -6:
                g.stock_fund_1 = '510880.XSHG'  # 红利
            else:
                g.stock_fund_1 = '511010.XSHG'  # 国债ETF

    # 2 防御仓（10%）
    if get_zf(context) > -6:
        g.stock_fund_2 = '510880.XSHG'  # 红利
    else:
        g.stock_fund_2 = '511010.XSHG'  # 国债ETF

    # 3 黄金/红利仓（30%）
    if macd_88 > 0:
        g.stock_fund_3 = '518880.XSHG'  # 黄金
    else:
        g.stock_fund_3 = '518880.XSHG'  # 黄金
        if macd_300 > 0 and get_zf(context) > -6:
            g.stock_fund_3 = '510880.XSHG'  # 红利

    # 4 固定国债ETF（20%）
    g.stock_fund_4 = "511010.XSHG"

    # 5 固定豆粕ETF（10%）
    g.stock_fund_5 = "159985.XSHE"

    # 6 固定南方原油ETF（10%）
    g.stock_fund_6 = "501018.XSHG"

    cdata = get_current_data()
    stocks = [g.stock_fund_1, g.stock_fund_2, g.stock_fund_3,
              g.stock_fund_4, g.stock_fund_5, g.stock_fund_6]

    # 目标比例：20%、10%、30%、20%、10%、10%
    r_list = [0.2, 0.1, 0.3, 0.2, 0.1, 0.1]
    # 【RP1】全 6 腿按 1/vol 归一化（满仓）
    r_list = inv_vol_split(stocks, 1.0)

    # 打印目标持仓
    buy_info = defaultdict(float)
    for i in range(6):
        buy_info[stocks[i]] += r_list[i]
    print(f"目标持仓:  "
          f"{', '.join(f'{k} ({get_security_info(k).display_name} {round(v, 1)})' for k, v in buy_info.items())}")

    # 2. 计算每个标的的目标市值
    total_value = context.portfolio.total_value
    target_values = defaultdict(float)

    for i in range(6):
        code = stocks[i]
        price = get_valid_price(cdata, code)
        if price is None:
            log.warn(f"标的 {code} 当日无有效价格，跳过该仓位")
            continue
        target_values[code] += total_value * r_list[i]

    # 兜底：如果有效标的的目标市值合计不足总资产，把剩余资金转入国债ETF
    allocated = 0.0
    for v in target_values.values():
        allocated += v

    unallocated = total_value - allocated
    if unallocated > total_value * 0.005:  # 超过 0.5% 未分配才处理
        fallback = '511010.XSHG'
        if get_valid_price(cdata, fallback) is not None:
            target_values[fallback] += unallocated
            log.info(f"未分配资金 {unallocated:.2f} 转入国债ETF")

    # 3. 判断执行年度再平衡还是月度再平衡
    is_year_start = (year_start(context) == 1)

    if is_year_start and g.enable_annual_rebalance:
        log.info("执行年度再平衡")
        do_rebalance(context, target_values)
        record_pending(context, target_values)
    elif g.enable_monthly_rebalance:
        if g.enable_threshold_rebalance:
            if need_rebalance(context, target_values, g.rebalance_threshold):
                log.info(f"月度偏离超过阈值 {g.rebalance_threshold * 100:.2f}%，执行再平衡")
                do_rebalance(context, target_values)
                record_pending(context, target_values)
            else:
                log.info(f"月度偏离未超过阈值 {g.rebalance_threshold * 100:.2f}%，不调仓")
        else:
            log.info("执行月度再平衡（未启用阈值检查）")
            do_rebalance(context, target_values)
            record_pending(context, target_values)
    else:
        log.info("再平衡开关均关闭，本月不调仓")

    # 记录当前持仓列表，供打印或后续使用
    g.stock_fund = stocks


# ---------- 按目标市值再平衡，不清仓 ----------
def do_rebalance(context, target_values):
    """
    直接调整持仓到目标市值，不进行清仓操作。
    target_values: dict，{证券代码: 目标市值}
    """
    # 先卖出不在目标列表中的持仓
    for code in list(context.portfolio.positions.keys()):
        if code not in target_values:
            order_target_value(code, 0)

    # 再按目标市值调整每个标的
    for code, tv in target_values.items():
        order_target_value(code, tv)


# ---------- 记录未达成目标的标的，进入重试列表 ----------
def record_pending(context, target_values):
    g.pending_info = {}
    today = context.current_dt.date()

    for code, tv in target_values.items():
        pos = context.portfolio.positions.get(code)
        current_value = pos.value if pos else 0.0
        # 差距超过目标市值的 1%，视为未达成，需要重试
        if tv - current_value > tv * 0.01:
            g.pending_info[code] = {
                'target': tv,
                'days': set([today])
            }
            log.info(f"标的 {code} 未达目标市值 {tv:.2f}，当前 {current_value:.2f}，进入重试列表")


# ---------- 重试买入 ----------
def retry_buy(context):
    if not g.pending_info:
        return

    cdata = get_current_data()
    today = context.current_dt.date()

    for code in list(g.pending_info.keys()):
        info = g.pending_info[code]
        target_value = info['target']

        # 记录今天尝试过
        info['days'].add(today)

        # 检查是否已达成目标
        pos = context.portfolio.positions.get(code)
        current_value = pos.value if pos else 0.0
        if current_value >= target_value * 0.99:
            log.info(f"标的 {code} 已达到目标市值 {target_value:.2f}，移出重试列表")
            del g.pending_info[code]
            continue

        # 检查是否已经尝试了 3 个交易日
        if len(info['days']) >= g.max_retry_days:
            log.info(f"标的 {code} 连续 {g.max_retry_days} 个交易日未买入成功，改用银华日利")
            # 清空原标的
            order_target_value(code, 0)
            # 银华日利加仓
            fb_pos = context.portfolio.positions.get(g.fallback_code)
            fb_value = fb_pos.value if fb_pos else 0.0
            order_target_value(g.fallback_code, fb_value + target_value)
            del g.pending_info[code]
            continue

        # 尝试再次买入
        price = get_valid_price(cdata, code)
        if price is not None:
            order_target_value(code, target_value)
            log.info(f"重试买入 {code}，目标市值 {target_value:.2f}")
        else:
            log.warn(f"标的 {code} 当日仍无有效价格，继续等待")


# ---------- 获取月线MACD ----------
def get_macd_M(stock, check_date):
    macd_dif, macd_dea, macd_macd = MACD(stock, check_date=check_date, SHORT=12, LONG=26, MID=9, unit='1M',
                                         include_now=False)
    macd_list = macd_macd[stock]
    return macd_list


# ---------- 判断是否当年第一个交易日 ----------
def year_start(context):
    year = context.current_dt.year
    month = context.current_dt.month
    day = context.current_dt.day
    trade_days = get_trade_days(start_date=str(year) + '-01-01', end_date=str(year) + '-12-31')
    trade_days = trade_days[0]
    trade_days = trade_days.day
    star = 0
    if month == 1 and day == trade_days:
        star = 1
    return star


# ---------- 红利ETF年度涨跌幅 ----------
def get_zf(context):
    etf = '510880.XSHG'  # 红利
    year = context.current_dt.year
    start_date_old = datetime.datetime(year - 1, 12, 20).strftime('%Y-%m-%d')
    end_date_old = datetime.datetime(year - 1, 12, 31).strftime('%Y-%m-%d')
    df_all = attribute_history(etf, 25, '1d', ['close'])
    df_close = df_all.close
    df = df_close[-1]
    df_old = get_price(etf, start_date=start_date_old, end_date=end_date_old, frequency='1d', panel=False)
    df_old = df_old.close
    df_old = df_old[-1]
    zf = round((df - df_old) * 100 / df_old, 2)
    return zf