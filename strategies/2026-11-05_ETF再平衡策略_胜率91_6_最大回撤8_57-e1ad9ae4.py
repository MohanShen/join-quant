# Clone from JoinQuant
# postId: e1ad9ae48564e02ff3b0c60b0de1197f
# backtestId: 587864c13d01e3a635fb4f255a21703b
# title: ETF再平衡策略，胜率91.6%，最大回撤8.57%

# 克隆自聚宽文章：https://www.joinquant.com/post/75217
# 标题：「长盈智选」：既要高收益，更要低回撤——11年最大回撤12%
# 作者：次仁多吉

# 克隆自聚宽文章：https://www.joinquant.com/post/82071
# 标题：永久组合
# 作者：nnn349864

# 全天候动态再平衡策略（3资产 + 估值评分，等权分配）
# 资产：纳指、黄金、大宗商品LOF
# 价格触发±18%再平衡；再平衡时0分清仓，1分和2分资产等权买入
# 防未来函数、真实价格，每月1日盘后报告

import math

def initialize(context):
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)

    # ---------- 可调参数 ----------
    g.risk_assets = [
        '513100.XSHG',  # 纳指ETF
        '518880.XSHG',  # 黄金ETF
        '159985.XSHE',  # 豆粕ETF
    ]
    g.bond_etf = '511260.XSHG'           # 10年国债（仅估值极端情况使用）
    g.equal_weight = 1.0 / len(g.risk_assets)   # 默认等权（首次建仓时使用）
    g.price_threshold = 0.10         # 价格触发再平衡阈值 ±18%
    g.cash_buffer = 0.0

    # 估值评分参数
    g.ma_period = 250                    # 年线周期
    g.overvalued_ratio = 1.30            # 价格高于MA的倍数，判定高估
    g.undervalued_ratio = 0.70           # 价格低于MA的倍数，判定低估

    g.last_rebalance_prices = {}         # 上次再平衡后的各资产价格
    g.initialized = False

    # 统计
    g.rebalance_count = 0
    g.liquidation_count = 0             # 因评分0分导致的清仓次数
    g.init_prices = {}                  # 后复权基准价（净值收益率）

    # 调度
    run_daily(check_and_rebalance, time='10:00')
    run_monthly(monthly_report, monthday=1, time='after_close')
    set_benchmark('000300.XSHG')

    g.etf_names = {}
    for sec in g.risk_assets + [g.bond_etf]:
        info = get_security_info(sec)
        g.etf_names[sec] = info.name if info else sec

    log.info('=== 全天候动态再平衡策略（估值评分，等权分配）初始化 ===')
    for sec in g.risk_assets:
        log.info('  %s %s  默认权重: %.2f%%', g.etf_names[sec], sec, g.equal_weight*100)
    log.info('估值评分：MA%d偏离>%.0f%%高估(0分)，<%.0f%%低估(2分)，其余正常(1分)',
             g.ma_period, (g.overvalued_ratio-1)*100, (1-g.undervalued_ratio)*100)
    log.info('价格触发阈值：±%.0f%%，再平衡时保留资产等权分配', g.price_threshold*100)


def get_usable_price(security, max_lookback=5):
    """获取可用价格：实时价优先，无效则回溯最近收盘价（静默）"""
    cd = get_current_data()
    if security in cd:
        price = cd[security].last_price
        if price is not None and not math.isnan(price) and price > 0:
            return price
    try:
        df = attribute_history(security, max_lookback, '1d', ['close'], skip_paused=True)
        if df is not None and not df.empty:
            for i in range(len(df)-1, -1, -1):
                price = df['close'].iloc[i]
                if not math.isnan(price) and price > 0:
                    return price
    except:
        pass
    return None


def get_post_price(security):
    """获取最近交易日的后复权收盘价，失败返回None"""
    try:
        df = attribute_history(security, 1, '1d', 'close', fq='post', skip_paused=True)
        if df is not None and not df.empty:
            price = df['close'].iloc[-1]
            if not math.isnan(price) and price > 0:
                return price
    except:
        pass
    return None


def get_valuation_score(context, security):
    """返回0(高估)、1(正常)、2(低估)"""
    try:
        df = attribute_history(security, g.ma_period, '1d', ['close'], skip_paused=True)
        if df is not None and len(df) == g.ma_period:
            ma = df['close'].mean()
            price = get_usable_price(security)
            if price is None:
                return 1  # 默认正常
            ratio = price / ma
            if ratio > g.overvalued_ratio:
                return 0
            elif ratio < g.undervalued_ratio:
                return 2
            else:
                return 1
    except:
        pass
    return 1


def check_and_rebalance(context):
    total_value = context.portfolio.total_value
    investable = total_value * (1 - g.cash_buffer)

    # 首次建仓 / 补仓
    missing = [sec for sec in g.risk_assets if sec not in g.last_rebalance_prices]
    if not g.initialized or missing:
        log.info('首次建仓/补仓，按默认等权分配仓位')
        force_rebalance_default(context, investable)
        for sec in g.risk_assets:
            p = get_usable_price(sec)
            if p:
                g.last_rebalance_prices[sec] = p
        if not g.initialized:
            for sec in g.risk_assets:
                post_p = get_post_price(sec)
                if post_p and sec not in g.init_prices:
                    g.init_prices[sec] = post_p
                    log.info('%s 后复权基准价：%.4f', sec, post_p)
        g.initialized = True
        return

    # 价格触发检查
    trigger = False
    for sec in g.risk_assets:
        base = g.last_rebalance_prices.get(sec)
        cur = get_usable_price(sec)
        if base is None or cur is None:
            continue
        change = (cur - base) / base
        if abs(change) >= g.price_threshold:
            log.info('触发再平衡！%s 涨跌幅 %.2f%%', g.etf_names[sec], change*100)
            trigger = True
            break

    if trigger:
        g.rebalance_count += 1
        log.info('执行第 %d 次再平衡（估值评分，等权分配）', g.rebalance_count)
        force_rebalance_with_score(context, investable)
        for sec in g.risk_assets:
            p = get_usable_price(sec)
            if p:
                g.last_rebalance_prices[sec] = p


def force_rebalance_default(context, investable):
    """默认等权分配（首次建仓、补仓时使用）"""
    target_per = investable * g.equal_weight
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.risk_assets:
            if context.portfolio.positions[sec].total_amount > 0:
                order_target(sec, 0)
    for sec in g.risk_assets:
        price = get_usable_price(sec)
        if price is None:
            log.warning('%s 无有效价格，跳过', sec)
            continue
        target_shares = int(target_per / price / 100) * 100
        if target_shares <= 0:
            if context.portfolio.positions[sec].total_amount > 0:
                order_target(sec, 0)
                log.info('清仓 %s（默认建仓不足1手）', g.etf_names[sec])
            continue
        order_target(sec, target_shares)
        log.info('建仓 %s %s -> %d 股', g.etf_names[sec], sec, target_shares)
    log.info('默认等权建仓完成。')


def force_rebalance_with_score(context, investable):
    """基于估值评分：0分清仓，1分/2分资产等权买入"""
    # 计算评分
    scores = {}
    for sec in g.risk_assets:
        scores[sec] = get_valuation_score(context, sec)
        log.info('%s 估值评分：%d', g.etf_names[sec], scores[sec])

    # 0分资产强制清仓
    for sec in g.risk_assets:
        if scores[sec] == 0:
            order_target(sec, 0)
            g.liquidation_count += 1
            log.info('清仓 %s（高估0分）', g.etf_names[sec])

    # 保留资产（1分或2分）
    retained = [sec for sec in g.risk_assets if scores[sec] > 0]

    if len(retained) == 0:
        # 全部0分，全仓国债
        log.info('所有资产均为高估，全仓转入国债')
        for sec in g.risk_assets:
            order_target(sec, 0)
        order_target_value(g.bond_etf, investable)
        return

    # 清空国债（如果有）
    if g.bond_etf in context.portfolio.positions and context.portfolio.positions[g.bond_etf].total_amount > 0:
        order_target(g.bond_etf, 0)

    # 等权分配
    weight = 1.0 / len(retained)
    for sec in retained:
        target_value = investable * weight
        price = get_usable_price(sec)
        if price is None:
            log.warning('%s 无有效价格，跳过', sec)
            continue
        target_shares = int(target_value / price / 100) * 100
        if target_shares <= 0:
            if context.portfolio.positions[sec].total_amount > 0:
                order_target(sec, 0)
                log.info('清仓 %s（等权分配后不足1手）', g.etf_names[sec])
            continue
        current_shares = context.portfolio.positions[sec].total_amount if sec in context.portfolio.positions else 0
        if current_shares != target_shares:
            order_target(sec, target_shares)
            log.info('调仓 %s %s -> %d 股 (约%.2f元)', g.etf_names[sec], sec, target_shares, target_shares*price)
        else:
            log.info('保持 %s %s 仓位不变', g.etf_names[sec], sec)

    log.info('等权再平衡完成（保留 %d 只资产）。', len(retained))


def monthly_report(context):
    total_value = context.portfolio.total_value
    start_cash = context.portfolio.starting_cash
    total_return = (total_value / start_cash - 1) * 100

    log.info('==================== 月度报告 %s ====================', 
             context.current_dt.strftime('%Y-%m-%d'))
    log.info('总资产: %.2f  总收益率: %.2f%%', total_value, total_return)
    log.info('累计触发再平衡次数: %d', g.rebalance_count)
    log.info('因高估(0分)导致清仓次数: %d', g.liquidation_count)

    for sec in g.risk_assets + [g.bond_etf]:
        pos = context.portfolio.positions[sec] if sec in context.portfolio.positions else None
        if pos and pos.total_amount > 0:
            if pos.avg_cost > 0:
                profit_pct = (pos.price / pos.avg_cost - 1) * 100
            else:
                profit_pct = 0.0
            net_ret = 'N/A'
            if sec in g.init_prices and g.init_prices[sec] > 0:
                cur_post = get_post_price(sec)
                if cur_post:
                    net_ret = '%.2f%%' % ((cur_post / g.init_prices[sec] - 1) * 100)
            log.info('  %s %s  持股数: %d  市值: %.2f  投入收益率: %.2f%%  净值涨幅: %s',
                     g.etf_names[sec], sec, pos.total_amount, pos.value, profit_pct, net_ret)
        else:
            net_ret = 'N/A'
            if sec in g.init_prices and g.init_prices[sec] > 0:
                cur_post = get_post_price(sec)
                if cur_post:
                    net_ret = '%.2f%%' % ((cur_post / g.init_prices[sec] - 1) * 100)
            log.info('  %s %s  无持仓  净值涨幅: %s', g.etf_names[sec], sec, net_ret)
    log.info('====================================================')


def handle_data(context, data):
    pass