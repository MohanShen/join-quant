# Research candidate — join-quant autoresearch (epoch 2)
# expId:    jul12-020  (idea-17 Arc-3 = jul12-018 + 动量回看 20d->60d, 保持纯净无切债)
# baseExpId: jul12-018  (ETF 20d动量 top3 baseline; TRAIN score -0.1917, sharpe -0.45 DQ, annual -3%)
# harness:  research/harness.md (冻结成本 OVERRIDE 见文末; 迭代只跑 --window train)
# design:   ~13 只流动跨资产 ETF 池 -> 每只 60 日动量 close[-1]/close[-61]-1 -> 降序取 top3 等权;
#           run_weekly(weekday=1, open). 无择时/防御(始终持 top3, 慢动量去噪 leader-whipsaw).
#           跨资产避险腿(国债511010 + 黄金518880 + 海外513100/513500)是池子的核心多样性来源.
# filters:  ETF 池: 剔除停牌 ETF; §3 股票概念(ST/次新/涨跌停)对 ETF N/A. 上市<250自然日(截至2022前)
#           在 initialize 里用 get_security_info 校验并剔除(避免早期 NaN 历史污染动量), NaN 历史再兜底剔除.
# note:     ESTABLISH Arc-3 参考 objective(TRAIN); 无 bar to beat. gate sharpe>=2.5 仍计算.
#           ⚠ ETF 现实手续费与股票不同, 但 harness 成本块冻结, 照搬(一致性优先于真实性, harness §2).

import datetime


# ============================================================================
# 回测初始化
# ============================================================================
def initialize(context):
    set_params(context)
    _set_frozen_harness()   # 勿改：见 research/harness.md §2
    # 周度调仓：每周第 1 个交易日开盘
    run_weekly(rebalance, weekday=1, time='open', reference_security='000300.XSHG')


def set_params(context):
    g.hold_count = 3        # 持有动量最强的 top3
    g.mom_window = 60       # 60 日动量：close[-1]/close[-61]-1（慢动量去噪 leader-whipsaw）

    # 候选跨资产 ETF（宽基 / 行业 / 避险 债+金 / 海外）
    raw_pool = [
        '510300.XSHG',  # 沪深300
        '510500.XSHG',  # 中证500
        '512100.XSHG',  # 中证1000
        '159915.XSHE',  # 创业板
        '510880.XSHG',  # 红利
        '512880.XSHG',  # 证券
        '512010.XSHG',  # 医药
        '159928.XSHE',  # 消费
        '512480.XSHG',  # 半导体
        '511010.XSHG',  # 5年国债（避险）
        '518880.XSHG',  # 黄金（避险）
        '513100.XSHG',  # 纳指QDII（海外）
        '513500.XSHG',  # 标普500 QDII（海外）
    ]

    # 校验上市 >= 250 自然日（截至 2022-01-01），剔除过新的 ETF（否则早期 NaN 历史污染动量排名）
    cutoff = datetime.date(2021, 4, 26)   # 2022-01-01 前 250 自然日
    pool = []
    for code in raw_pool:
        try:
            info = get_security_info(code)
        except Exception:
            info = None
        if info is None:
            log.info('ETF prune (no info): %s' % code)
            continue
        if info.start_date > cutoff:
            log.info('ETF prune (too new): %s start=%s' % (code, info.start_date))
            continue
        pool.append(code)
    g.etf_pool = pool
    log.info('ETF pool kept (%d): %s' % (len(pool), pool))


def _set_frozen_harness():
    # ============ FROZEN（勿改）：research/harness.md §2 ============
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    set_benchmark('000300.XSHG')                                   # 仅显示用，不影响 objective
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(FixedSlippage(0))                                 # 零滑点（见 harness.md §2 警示）
    # ===================================================================


# ============================================================================
# 主逻辑：周度 20 日动量 top3 等权轮动
# ============================================================================
def rebalance(context):
    cd = get_current_data()
    # 剔除停牌 ETF
    pool = [c for c in g.etf_pool if not cd[c].paused]
    if not pool:
        return

    # 20 日动量：取近 mom_window+1 根日线收盘（宽表 index=日期/columns=code）
    close = history(g.mom_window + 1, unit='1d', field='close', security_list=pool, df=True)
    mom = close.iloc[-1] / close.iloc[0] - 1.0   # close[-1]/close[-21]-1
    mom = mom.dropna()                            # 丢弃历史不足/无效的 ETF
    if mom.empty:
        return

    ranked = mom.sort_values(ascending=False)     # 动量降序
    targets = list(ranked.index[:g.hold_count])
    if not targets:
        return

    # 先卖出不在 top3 的持仓（停牌不强卖）
    for s in list(context.portfolio.positions.keys()):
        if s not in targets and not cd[s].paused:
            order_target_value(s, 0)

    # 再等权买入 top3
    each = context.portfolio.total_value / g.hold_count
    for s in targets:
        order_target_value(s, each)


# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# research/harness.md §2 — force zero slippage + frozen commission regardless of
# what the raw strategy sets, even if it re-sets costs every bar.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
except NameError:
    pass
# ===== END OVERRIDE =====
