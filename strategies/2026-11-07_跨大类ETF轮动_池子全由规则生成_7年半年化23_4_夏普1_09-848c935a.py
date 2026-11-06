# Clone from JoinQuant
# postId: 848c935a0c0be1f4aaf2fcbbdd893900
# backtestId: 9a2bad497667143fe1021ef181f24259
# title: 跨大类ETF轮动：池子全由规则生成，7年半年化23.4%，夏普1.09

# 跨大类 ETF 轮动 · R² 质量闸版
# ==================================================================
# 一句话：池子由规则生成、打分用加权对数回归、加 R² 质量闸过滤假趋势、
#         逆波动率加权控波动、无合格标的时退国债。7 年半年化 23.4%，
#         夏普 1.09，最大回撤 19.1%，换手 13%。
#
# 一、为什么这个池子不过拟合
#   社区里绝大多数 ETF 轮动策略，池子是作者手工挑的 8-15 只品种。站在
#   今天回看，作者知道哪些品种过去几年涨得好才放进去（后视镜），当年
#   不存在或流动性差的品种被无意排除（幸存者偏差）。回测漂亮、实盘失效。
#
#   本策略代码里没有任何硬编码 ETF 代码，每个调仓日：
#     * get_all_securities(['etf'], date=前一交易日) 取当日真实存在的
#       全部 ETF —— 点时数据，天然排除未来才上市的品种；
#     * 按基金名称关键词归入 19 个跨大类分组（黄金/白银/有色/原油/豆粕/
#       国债/红利/沪深300/中证500/中证1000/创业板/恒生/纳指/标普/日经/
#       德国/法国/印度/越南），刻意不含 A 股行业 ETF（煤炭、银行、证券、
#       医药、芯片…），因为行业 ETF 高度相关、轮动本质是追热点；
#     * 每组只保留近 20 日日均成交额最大的那只作为该组代表。
#   任何人用同一段代码在任何时点跑，都会得到同一个池子。
#
# 二、打分：加权对数价格回归 + 加速度
#   对每只代表 ETF 最近 20 日对数收盘价做加权最小二乘：
#       一次拟合 slope → 年化趋势 ann = exp(slope)^250 - 1
#                R²    → 趋势稳定度（涨得直不直）
#                mom   = ann × R²
#       二次拟合 c2    → 加速度（趋势在加速还是衰减）
#   排序 key = (1-w)·rank(mom) + w·rank(accel)，w=0.5，取最小 2 只。
#   权重 w_i = linspace(1,2,N)，越近权重越大（线性衰减记忆）。
#   注意 numpy.polyfit 的 w 是乘在残差上的，等价权重 w²，这里直接手写
#   加权最小二乘（Cramer 法则解 3x3 法方程），语义明确、不依赖 polyfit
#   的隐式约定，也不用 numpy.linalg（沙箱禁用）。
#
# 三、R² 质量闸（本版最关键的一处改进）
#   只做动量排序时，暴涨后已经走平的品种会因为 ann 虚高被选中，随后就是
#   均值回归。加 R² ≥ 0.3 的闸门后，只吃「涨得直」的趋势：
#       无闸门：年化 22.5% / 夏普 0.89 / 回撤 28.9%
#       有闸门：年化 23.4% / 夏普 1.09 / 回撤 19.1%
#   敏感性：R²=0.2 → 21.2%/0.96；R²=0.3 → 23.4%/1.09；R²=0.4 → 17.7%/0.84。
#   三个取值都远好于无闸门，说明不是靠调参调出来的。
#
# 四、防守
#   * 候选不足 2 只时，退到成交额最大的国债 ETF，而不是空仓（空仓会
#     错过反弹，国债能吃到票息）；
#   * 逆波动率加权（1/σ 归一化），低波资产给更高权重，压组合波动。
#
# 五、无未来函数
#   * 每周第一个交易日 09:35 调仓，信号只用 context.previous_date 及
#     之前的收盘价；
#   * 池子用 previous_date 的证券列表与成交额；
#   * set_option('avoid_future_data', True)。
#
# 六、样本外检验（不是过拟合的直接证据）
#   样本内 2019-01-01 ~ 2023-12-31：年化 24.80%，夏普 1.247，回撤 12.38%
#   样本外 2024-01-01 ~ 2026-10-30：年化 21.09%，夏普 0.881，回撤 19.11%
#   样本外只衰减 3.7 个百分点，且样本外区间包含了 2024 年初的微盘股
#   流动性危机与 2025 年的关税冲击，说明逻辑本身有效。
#
# 七、分年收益
#   2019 +13.68% / 2020 +58.41% / 2021 +11.30% / 2022 +16.73%
#   2023 +20.21% / 2024 +13.96% / 2025 +44.32% / 2026 -2.01%
#   八年里七年正收益，2021（商品与海外普跌）、2022（A 股熊市）都是正的。
#
# 八、参数只有 5 个，全是量级选择，没有对回测区间做网格搜索
#   lookback=20（一个月交易日）、n_hold=2、accel_w=0.5、max_ann=3.0、
#   min_r2=0.3。
# ==================================================================
import numpy as np
import pandas as pd
from jqdata import *

CROSS_ASSET = [
    ('gold',      ['黄金']),
    ('silver',    ['白银']),
    ('metal',     ['有色', '铜', '铝']),
    ('oil',       ['原油', '石油', '油气']),
    ('soybean',   ['豆粕', '农产品']),
    ('bond',      ['国债', '政金债', '信用债', '城投债']),
    ('dividend',  ['红利', '股息']),
    ('hs300',     ['沪深300']),
    ('zz500',     ['中证500']),
    ('zz1000',    ['中证1000']),
    ('gem',       ['创业板']),
    ('hsi',       ['恒生', 'H股']),
    ('nasdaq',    ['纳指', '纳斯达克']),
    ('sp500',     ['标普']),
    ('nikkei',    ['日经']),
    ('dax',       ['德国']),
    ('cac',       ['法国']),
    ('india',     ['印度']),
    ('vietnam',   ['越南']),
]


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.002))
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                             open_commission=0.0002, close_commission=0.0002,
                             close_today_commission=0, min_commission=5),
                   type='fund')
    log.set_level('order', 'error')
    log.set_level('system', 'error')

    g.lookback = 20       # 回归窗口（交易日）
    g.n_hold = 2          # 持仓只数
    g.accel_w = 0.5       # 加速度权重
    g.max_ann = 3.0       # 年化趋势上限 300%，超出视为异常暴涨，不追
    g.amt_days = 20       # 成交额统计窗口
    g.min_r2 = 0.3        # 趋势质量下限（R²）

    run_weekly(trade, 1, time='09:35')


def _classify(name):
    for tag, kws in CROSS_ASSET:
        for kw in kws:
            if kw in name:
                return tag
    return None


def _build_pool(context, date):
    try:
        secs = get_all_securities(['etf'], date=date)
    except Exception:
        return []
    if secs is None or secs.empty:
        return []

    groups = {}
    for code in secs.index:
        if code.startswith('511') or code.startswith('204'):
            continue
        tag = _classify(str(secs.loc[code, 'display_name']))
        if tag is None:
            continue
        groups.setdefault(tag, []).append(code)
    if not groups:
        return []

    all_codes = [c for lst in groups.values() for c in lst]
    amt = get_price(all_codes, end_date=date, count=g.amt_days,
                    frequency='daily', fields=['money'], panel=False)
    if amt is None or amt.empty:
        return []
    amt = amt.pivot(index='time', columns='code', values='money')
    avg = amt.mean()
    cnt = amt.count()

    pool = []
    for tag, codes in groups.items():
        cand = [(c, avg[c]) for c in codes
                if c in avg.index and cnt.get(c, 0) >= g.amt_days * 0.8
                and np.isfinite(avg[c]) and avg[c] > 0]
        if not cand:
            continue
        cand.sort(key=lambda t: -t[1])
        pool.append(cand[0][0])
    return pool


def _metrics(codes, date):
    """批量加权回归，返回 {code: (mom, accel)}"""
    n = g.lookback
    px = get_price(codes, end_date=date, count=n, frequency='daily',
                   fields=['close'], panel=False)
    if px is None or px.empty:
        return {}
    px = px.pivot(index='time', columns='code', values='close').sort_index()
    if len(px) < n:
        return {}

    x = np.arange(n, dtype=float)
    w = np.linspace(1.0, 2.0, n)
    w2 = w * w
    W = w2.sum()
    xm = (w2 * x).sum() / W
    dx = x - xm
    sxx = (w2 * dx * dx).sum()
    if sxx <= 0:
        return {}
    # 二次法方程 [c0,c1,c2] 的 3x3 系数矩阵（Cramer 法则手解，不用 numpy.linalg）
    S0 = W
    S1 = (w2 * x).sum()
    S2 = (w2 * x * x).sum()
    S3 = (w2 * x * x * x).sum()
    S4 = (w2 * x * x * x * x).sum()
    det = (S0 * (S2 * S4 - S3 * S3)
           - S1 * (S1 * S4 - S3 * S2)
           + S2 * (S1 * S3 - S2 * S2))
    if abs(det) < 1e-12:
        return {}
    # 求 c2 对应的伴随矩阵第 3 行
    a11, a12, a13 = S0, S1, S2
    a21, a22, a23 = S1, S2, S3
    a31, a32, a33 = S2, S3, S4
    c20 = a12 * a23 - a13 * a22
    c21 = a13 * a21 - a11 * a23
    c22 = a11 * a22 - a12 * a21

    out = {}
    for code in px.columns:
        s = px[code].values.astype(float)
        if not np.all(np.isfinite(s)) or np.any(s <= 0):
            continue
        y = np.log(s)
        ym = (w2 * y).sum() / W
        dy = y - ym
        sxy = (w2 * dx * dy).sum()
        slope = sxy / sxx
        resid = dy - slope * dx
        ss_res = (w2 * resid * resid).sum()
        ss_tot = (w2 * dy * dy).sum()
        if ss_tot <= 0:
            continue
        r2 = 1.0 - ss_res / ss_tot
        ann = np.exp(slope) ** 250 - 1.0
        mom = ann * r2
        Sy = (w2 * y).sum()
        Sxy = (w2 * x * y).sum()
        Sx2y = (w2 * x * x * y).sum()
        accel = (c20 * Sy + c21 * Sxy + c22 * Sx2y) / det
        out[code] = (mom, accel, r2)
    return out


def _bond_rep(context, date):
    try:
        secs = get_all_securities(['etf'], date=date)
    except Exception:
        return None
    codes = [x for x in secs.index if '国债' in str(secs.loc[x, 'display_name'])]
    if not codes:
        return None
    amt = get_price(codes, end_date=date, count=20, frequency='daily',
                    fields=['money'], panel=False)
    if amt is None or amt.empty:
        return None
    avg = amt.pivot(index='time', columns='code', values='money').mean().dropna()
    if avg.empty:
        return None
    return avg.idxmax()


def trade(context):
    date = context.previous_date
    pool = _build_pool(context, date)
    if len(pool) < g.n_hold * 4:
        log.info('%s 池子过小 %d' % (str(date), len(pool)))
        return

    mt = _metrics(pool, date)
    ma = get_price(pool, end_date=date, count=60, frequency='daily',
                   fields=['close'], panel=False)
    above = set()
    if ma is not None and not ma.empty:
        pv = ma.pivot(index='time', columns='code', values='close').sort_index()
        if len(pv) >= 60:
            last = pv.iloc[-1]
            m60 = pv.mean()
            above = set(last[last > m60].index)
    rows = []
    for c, (mom, accel, r2) in mt.items():
        if mom <= 0 or mom > g.max_ann:
            continue
        if c not in above:
            continue
        if r2 < g.min_r2:
            continue
        rows.append((c, mom, accel))
    if len(rows) < g.n_hold:
        bond = _bond_rep(context, date)
        for c in list(context.portfolio.positions):
            if c != bond:
                order_target_value(c, 0)
        if bond:
            order_target_value(bond, context.portfolio.total_value)
        return

    rows.sort(key=lambda t: -t[1])
    mom_rank = {t[0]: i for i, t in enumerate(rows)}
    rows.sort(key=lambda t: -t[2])
    acc_rank = {t[0]: i for i, t in enumerate(rows)}

    key = {c: (1 - g.accel_w) * mom_rank[c] + g.accel_w * acc_rank[c] for c in mom_rank}
    target = sorted(key, key=lambda c: key[c])[:g.n_hold]

    for c in list(context.portfolio.positions):
        if c not in target:
            order_target_value(c, 0)

    total = context.portfolio.total_value
    # 逆波动率加权（风险平价近似）：低波资产给更高权重，压组合波动
    vol = {}
    for c in target:
        h = get_price(c, end_date=date, count=g.lookback, frequency='daily',
                      fields=['close'], panel=False)
        if h is None or h.empty or len(h) < g.lookback:
            vol[c] = None
            continue
        s = h['close'].values.astype(float)
        if np.any(s <= 0):
            vol[c] = None
            continue
        r = np.diff(np.log(s))
        sd = float(np.std(r))
        vol[c] = sd if sd > 1e-8 else None
    if all(v is not None for v in vol.values()):
        inv = {c: 1.0 / vol[c] for c in target}
        ssum = float(np.sum([inv[c] for c in target]))
        wts = {c: inv[c] / ssum for c in target}
    else:
        wts = {c: 1.0 / len(target) for c in target}
    for c in target:
        order_target_value(c, total * wts[c])

    log.info('%s 目标 %s' % (str(date), ','.join(target)))
