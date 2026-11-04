# Clone from JoinQuant
# postId: bf9bd2e72b55c146d256926ed24e6529
# backtestId: e209d767a9a26ebbeab8c1fadb2fc0d8
# title: 全球大类ETF轮动：年化68%，距9月历史新高回撤2.6%

# 克隆自聚宽文章：https://www.joinquant.com/post/75990
# 作者：chukuangren

import numpy as np
import pandas as pd
import math


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.001))

    # 修改点 1：补上 type='fund'，修复聚宽 API 报错
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0, open_commission=0.00005,
                  close_commission=0.00005, close_today_commission=0, min_commission=5),
        type='fund'
    )

    g.etf_pool = [
        '518880.XSHG',  # (黄金ETF) 
        '501018.XSHG',  # (南方原油) 
        '513100.XSHG',  # (纳指ETF) 
        '513520.XSHG',  # (日经ETF)
        '513030.XSHG',  # (德国ETF) 
        '159781.XSHE',  # 双创50ETF，回测可用159915.X创业板替代
        "159985.XSHE",  # 豆粕ETF
        "511010.XSHG",  # 国债ETF
    ]
    g.m_days = 20
    g.accel_w = 0.5  # 修改点 2：聚宽不支持 os.environ，直接写死

    # 预加载ETF中文名映射
    g.etf_names = {}
    for code in g.etf_pool:
        try:
            info = get_security_info(code)
            g.etf_names[code] = getattr(info, 'display_name', '') or code
        except Exception:
            g.etf_names[code] = code
    log.info("[初始化] ETF池共{}只: {}".format(len(g.etf_pool), g.etf_names))

    run_daily(trade, '09:40')


def metrics(etf):
    df = attribute_history(etf, g.m_days, '1d', ['close'])
    y = np.log(df['close'].values)
    n = len(y)
    x = np.arange(n)
    w = np.linspace(1, 2, n)

    # 线性拟合（加权）
    slope, intercept = np.polyfit(x, y, 1, w=w)
    ann_ret = math.exp(slope) ** 250 - 1
    resid = y - (slope * x + intercept)

    # 修改点 3：R² 改用标准加权 R²（分母用加权均值）
    y_mean_w = np.average(y, weights=w)
    ss_res = np.sum(w * resid ** 2)
    ss_tot = np.sum(w * (y - y_mean_w) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0

    # 修改点 4：二次拟合也加上权重 w，与线性拟合时间敏感度对称
    c = np.polyfit(x, y, 2, w=w)
    accel = c[0]

    mom = ann_ret * r2
    return dict(mom=mom, accel=accel, r2=r2, ann_ret=ann_ret)


def get_rank(etf_pool):
    recs = {e: metrics(e) for e in etf_pool}

    # 修改点 5：资格闸改为显式过滤逻辑
    # 保留 MOM ∈ (0,10] 的基线兼容，同时显式过滤趋势散乱或收益为负的品种
    elig = []
    for e in etf_pool:
        mom = recs[e]['mom']
        r2 = recs[e]['r2']
        ann_ret = recs[e]['ann_ret']
        if 0 < mom <= 10 and r2 > 0 and ann_ret > 0:
            elig.append(e)

    if not elig:
        return [], recs

    mom_rank = {e: i for i, e in enumerate(sorted(elig, key=lambda e: recs[e]['mom'], reverse=True))}
    acc_rank = {e: i for i, e in enumerate(sorted(elig, key=lambda e: recs[e]['accel'], reverse=True))}
    w = g.accel_w
    key = {e: (1 - w) * mom_rank[e] + w * acc_rank[e] for e in elig}  # 越小越好
    ranked = sorted(elig, key=lambda e: key[e])
    return ranked, recs


def trade(context):
    target_num = 1

    # 获取排名和全部指标数据
    ranked_list, recs = get_rank(g.etf_pool)

    # 【新增】打印排名前三的标的及其动量得分
    log.info("=" * 50)
    log.info("[排名] {} 共{}只入池, 合格{}只".format(
        context.current_dt.strftime('%Y-%m-%d'), len(g.etf_pool), len(ranked_list)))

    if ranked_list:
        top_n = min(3, len(ranked_list))
        for i, etf in enumerate(ranked_list[:top_n]):
            r = recs[etf]
            name = g.etf_names.get(etf, etf)
            log.info("  #{} {}({}) | 动量分={:.4f} | 年化={:.2f}% | R²={:.4f} | 加速度={:.6f}".format(
                i + 1, name, etf, r['mom'], r['ann_ret'] * 100, r['r2'], r['accel']))
    else:
        # 没有合格标的时，打印全部ETF的得分用于诊断
        log.info("  [无合格标的] 打印全部ETF指标诊断:")
        sorted_all = sorted(g.etf_pool, key=lambda e: recs[e]['mom'], reverse=True)
        for etf in sorted_all:
            r = recs[etf]
            name = g.etf_names.get(etf, etf)
            fail_reasons = []
            if r['mom'] <= 0:
                fail_reasons.append("动量<=0")
            if r['mom'] > 10:
                fail_reasons.append("动量>10")
            if r['r2'] <= 0:
                fail_reasons.append("R²<=0")
            if r['ann_ret'] <= 0:
                fail_reasons.append("年化<=0")
            reason = "未入选: " + ", ".join(fail_reasons) if fail_reasons else "入选"
            log.info("  {}({}) | 动量分={:.4f} | 年化={:.2f}% | R²={:.4f} | {}".format(
                name, etf, r['mom'], r['ann_ret'] * 100, r['r2'], reason))
    log.info("=" * 50)

    # 执行交易
    target_list = ranked_list[:target_num]
    hold_list = list(context.portfolio.positions)

    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)

    hold_list = list(context.portfolio.positions)
    if len(hold_list) < target_num:
        value = context.portfolio.available_cash / (target_num - len(hold_list))
        for etf in target_list:
            # 修改点 6：用 in 判断避免 KeyError
            if etf not in context.portfolio.positions:
                order_target_value(etf, value)


