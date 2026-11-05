# Clone from JoinQuant
# postId: 3a686b10a4ae368e87cb8c9e014df7e3
# backtestId: 092d14c5083f02092c3fb95e62984f05
# title: 求稳的看过来！一年只调四次仓，年化17.24%？回撤个位数

# -*- coding: utf-8 -*-
"""聚宽 v3：场内 ETF / LOF，真实调用回测撮合接口。

新建 Python 3 策略，全文粘贴；日频或分钟频率，建议 2023-01-03 起、100万元。
首个可交易日建仓，之后季度再平衡。看聚宽原生交易记录、持仓及收益报告。
14:45 减仓、14:50 买入；目标份额只在一次调仓开始时计算，最多补单5个交易日。

原文的场外组合已按用户授权替换：511520 是 7-10年政策性金融债（不只国开债）；
501305 使用同基金场内 LOF；其余采用对应 ETF / 相同指数 ETF。详情见配套说明。
保留 0.5% 现金，基金目标权重实际为下表权重乘 99.5%，份额向下取100的整倍数。
费用和滑点是回测假设；没有新增择时、止损、溢价过滤或每日定投规则。
"""
from jqdata import *
import builtins as _py
import datetime as _dt
import math as _math


# 代码、名称、原文权重、交易所上市日期（不是基金成立日期）。
INSTRUMENTS = [
    ('513100.XSHG', '国泰纳斯达克100ETF', 0.20, '2013-05-15'),
    ('518880.XSHG', '华安黄金ETF', 0.25, '2013-07-29'),
    ('511520.XSHG', '富国7-10年政金债ETF', 0.35, '2022-10-25'),
    ('512890.XSHG', '华泰柏瑞红利低波ETF', 0.05, '2019-01-18'),
    ('501305.XSHG', '汇添富港股红利LOF', 0.05, '2018-01-18'),
    ('510330.XSHG', '华夏沪深300ETF', 0.05, '2013-01-16'),
    ('159819.XSHE', '易方达人工智能ETF', 0.02, '2020-09-23'),
    ('588200.XSHG', '嘉实科创芯片ETF', 0.02, '2022-10-26'),
    ('512770.XSHG', '华夏战略新兴ETF', 0.01, '2018-08-16'),
]
WEIGHTS = {row[0]: row[2] for row in INSTRUMENTS}
CODES = [row[0] for row in INSTRUMENTS]
LOT_SIZE = 100
TICK_SIZE = 0.001
CASH_RESERVE_RATIO = 0.005
COMMISSION_RATE = 0.0003       # 双边各万分之三
MIN_COMMISSION = 5.0          # 每笔最低5元，作为可修改的保守费用假设
SLIPPAGE_SPREAD = 0.001       # 聚宽定义：双边价差0.1%，单边约0.05%
LIMIT_PRICE_BAND = 0.002      # 委托限价距当前价0.2%，不是择时条件
ORDER_VOLUME_RATIO = 0.10    # 不放宽到全市场成交量；低流动性标的可能部分成交
MAX_REBALANCE_DAYS = 5


def _date(value):
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    return _dt.datetime.strptime(_py.str(value)[:10], '%Y-%m-%d').date()


def _positive(value):
    try:
        return _math.isfinite(_py.float(value)) and value > 0
    except (TypeError, ValueError):
        return False


def _validate():
    if len(set(CODES)) != len(CODES):
        raise ValueError('场内基金代码重复')
    for code, weight in WEIGHTS.items():
        if not _positive(weight):
            raise ValueError('权重无效：%s=%r' % (code, weight))
    if _py.abs(_math.fsum(WEIGHTS.values()) - 1) > 1e-10:
        raise ValueError('权重合计必须等于1')
    if not 0 < CASH_RESERVE_RATIO < 1 or MAX_REBALANCE_DAYS < 1:
        raise ValueError('现金储备和补单天数设置无效')
    for value in (COMMISSION_RATE, MIN_COMMISSION, SLIPPAGE_SPREAD, LIMIT_PRICE_BAND):
        if not _math.isfinite(value) or value < 0:
            raise ValueError('费用、滑点和限价缓冲不能为负或非有限值')


def initialize(context):
    _validate()
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_option('order_volume_ratio', ORDER_VOLUME_RATIO)
    # 默认 stock 账户可交易场内基金；不可创建旧版的 open_fund 账户。
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                             open_commission=COMMISSION_RATE,
                             close_commission=COMMISSION_RATE,
                             close_today_commission=COMMISSION_RATE,
                             min_commission=MIN_COMMISSION), type='fund')
    set_slippage(PriceRelatedSlippage(SLIPPAGE_SPREAD), type='fund')

    # 初始化时一次核验全部代码，不通过持仓映射探测证券是否存在。
    errors, starts = [], []
    for code, name, weight, listing in INSTRUMENTS:
        official_start = _date(listing)
        try:
            info = get_security_info(code)
            if info is None:
                raise ValueError('未返回证券信息')
            platform_start = _date(info.start_date)
        except Exception as exc:
            errors.append('%s %s：%s' % (code, name, exc))
            continue
        starts.append(_py.max(official_start, platform_start))
        log.info('场内证券核验 %s %s：公告上市 %s，平台起点 %s' %
                 (code, info.display_name, official_start, platform_start))
    if errors:
        raise ValueError('以下场内证券不可用，未跳过任何标的：\n' + '\n'.join(errors))

    g.native_ready_after = _py.max(starts)
    g.native_last_quarter = None
    g.native_plan = None
    g.native_wait_logged = False
    g.native_total_fills = 0
    g.native_total_orders = 0
    g.native_rebalances = 0
    g.native_last_report = None
    g.native_peak = _py.float(context.portfolio.starting_cash)
    g.native_max_dd = 0.0
    log.info('v3 场内实际下单版：原生持仓、买卖记录和收益报告有效；'
             '完整组合在 %s 之后建仓。' % g.native_ready_after)
    run_daily(rebalance_sell, time='14:45')
    run_daily(rebalance_buy, time='14:50')
    run_daily(report_after_close, time='after_close')


def _positions(context):
    # 聚宽 Positions.get 会触发 __getitem__；只遍历实际持仓，再构造普通 dict。
    return {_py.str(code): position for code, position in context.portfolio.positions.items()}


def _amount(positions, code):
    position = positions.get(code)  # 此处已是普通 Python dict
    return _py.int(position.total_amount) if position is not None else 0


def _pending_codes():
    return {_py.str(o.security) for o in get_open_orders().values()}


def _cancel_own_orders():
    for pending in list(get_open_orders().values()):
        if _py.str(pending.security) in WEIGHTS:
            cancel_order(pending)


def _build_plan(context, quotes, quarter):
    value = _py.float(context.portfolio.total_value)
    if not _positive(value):
        raise ValueError('账户总资产无效，不能调仓')
    targets, small = {}, []
    for code in CODES:
        price = quotes[code].last_price
        if not _positive(price):
            raise ValueError('%s 缺少有效现价；没有用净值或零价格冒充成交价' % code)
        shares = _math.floor(value * (1 - CASH_RESERVE_RATIO) * WEIGHTS[code] /
                             _py.float(price) / LOT_SIZE) * LOT_SIZE
        targets[code] = _py.int(shares)
        if shares < LOT_SIZE:
            minimum = price * LOT_SIZE / (WEIGHTS[code] * (1 - CASH_RESERVE_RATIO))
            small.append('%s 至少需约 %.2f 元组合资金' % (code, minimum))
    if small:
        raise ValueError('资金不足以按原权重覆盖每个品种的一手：' + '；'.join(small))
    return dict(quarter=quarter, targets=targets,
                reserve=value * CASH_RESERVE_RATIO, attempts=0,
                last_attempt=None, last_buy=None, started=context.current_dt.date(),
                fills_before=g.native_total_fills)


def _limit_price(quote, is_buy):
    if quote.paused or not _positive(quote.last_price):
        return None
    price = _py.float(quote.last_price)
    high = getattr(quote, 'high_limit', None)
    low = getattr(quote, 'low_limit', None)
    if is_buy:
        if _positive(high) and price >= high - TICK_SIZE * 0.1:
            return None
        limit = _math.ceil(price * (1 + LIMIT_PRICE_BAND) / TICK_SIZE - 1e-9) * TICK_SIZE
        if _positive(high):
            limit = _py.min(limit, high)
    else:
        if _positive(low) and price <= low + TICK_SIZE * 0.1:
            return None
        limit = _math.floor(price * (1 - LIMIT_PRICE_BAND) / TICK_SIZE + 1e-9) * TICK_SIZE
        if _positive(low):
            limit = _py.max(limit, low)
    return _py.round(limit, 3) if limit > 0 else None


def _affordable_shares(cash, limit):
    # 同时满足比例佣金和最低佣金两种资金约束。
    if cash <= MIN_COMMISSION or not _positive(limit):
        return 0
    by_rate = cash / (limit * (1 + COMMISSION_RATE))
    by_minimum = (cash - MIN_COMMISSION) / limit
    return _py.int(_math.floor(_py.min(by_rate, by_minimum) / LOT_SIZE) * LOT_SIZE)


def _submit(code, delta, limit):
    result = order(code, delta, style=LimitOrderStyle(limit))
    if result is None:
        log.warn('委托未创建 %s 数量=%d，保留目标等待下次检查' % (code, delta))
        return False
    g.native_total_orders += 1
    log.info('已提交%s委托 %s 数量=%d 限价=%.3f；以原生成交记录为准' %
             ('买入' if delta > 0 else '卖出', code, _py.abs(delta), limit))
    return True


def rebalance_sell(context):
    today = context.current_dt.date()
    if today <= g.native_ready_after:
        if not g.native_wait_logged:
            log.info('等待完整场内组合上市：最晚上市/数据起点为 %s' % g.native_ready_after)
            g.native_wait_logged = True
        return
    quarter = (today.year, (today.month - 1) // 3)
    if g.native_last_quarter != quarter:
        _cancel_own_orders()
        g.native_plan = _build_plan(context, get_current_data(), quarter)
        g.native_last_quarter = quarter
        g.native_rebalances += 1
        log.info('启动第%d次建仓/季度调仓，冻结目标份额：%s' %
                 (g.native_rebalances, g.native_plan['targets']))
    plan = g.native_plan
    if plan is None or plan['last_attempt'] == today:
        return
    plan['attempts'] += 1
    plan['last_attempt'] = today
    quotes, positions, pending = get_current_data(), _positions(context), _pending_codes()
    for code in CODES:
        current = _amount(positions, code)
        excess = current - plan['targets'][code]
        if excess < LOT_SIZE or code in pending:
            continue
        limit = _limit_price(quotes[code], False)
        if limit is None:
            log.warn('暂不能卖出 %s：停牌、无有效价或跌停，等待补单' % code)
            continue
        closeable = _py.int(positions[code].closeable_amount)
        shares = (_py.min(excess, closeable) // LOT_SIZE) * LOT_SIZE
        if shares <= 0:
            log.warn('暂不能卖出 %s：可卖份额不足，等待下一交易日' % code)
            continue
        _submit(code, -shares, limit)


def rebalance_buy(context):
    plan = g.native_plan
    if plan is None or plan['last_attempt'] != context.current_dt.date():
        return
    if plan['last_buy'] == context.current_dt.date():
        return
    plan['last_buy'] = context.current_dt.date()
    quotes, positions, pending = get_current_data(), _positions(context), _pending_codes()
    # 仅用已有可用现金，未成交卖单不能充当买入资金。
    # 0.5% 已通过降低目标持仓留出；这里允许它支付手续费，不能再重复扣除。
    budget = _py.max(0.0, context.portfolio.available_cash)
    gaps = [(c, plan['targets'][c] - _amount(positions, c)) for c in CODES]
    gaps.sort(key=lambda item: item[1] * _py.float(quotes[item[0]].last_price)
              if _positive(quotes[item[0]].last_price) else 0.0, reverse=True)
    for code, gap in gaps:
        if gap < LOT_SIZE or code in pending:
            continue
        limit = _limit_price(quotes[code], True)
        if limit is None:
            log.warn('暂不能买入 %s：停牌、无有效价或涨停，等待补单' % code)
            continue
        budget = _py.min(budget, _py.max(0.0, context.portfolio.available_cash))
        shares = _py.min((gap // LOT_SIZE) * LOT_SIZE, _affordable_shares(budget, limit))
        if shares < LOT_SIZE:
            continue
        if _submit(code, shares, limit):
            value = shares * limit
            budget -= value + _py.max(MIN_COMMISSION, value * COMMISSION_RATE)


def _remaining(context, targets):
    positions = _positions(context)
    return {c: targets[c] - _amount(positions, c) for c in CODES
            if _py.abs(targets[c] - _amount(positions, c)) >= LOT_SIZE}


def report_after_close(context):
    today = context.current_dt.date()
    if g.native_last_report == today:
        return
    g.native_last_report = today
    trades = [t for t in get_trades().values()
              if _date(t.time) == today and _py.str(t.security) in WEIGHTS]
    g.native_total_fills += len(trades)
    if trades:
        log.info('今日原生成交 %d 笔；实际持仓 %s' %
                 (len(trades), {c: p.total_amount for c, p in _positions(context).items()}))
    value = _py.float(context.portfolio.total_value)
    g.native_peak = _py.max(g.native_peak, value)
    dd = _py.max(0.0, 1 - value / g.native_peak)
    g.native_max_dd = _py.max(g.native_max_dd, dd)
    record(actual_nav=value / context.portfolio.starting_cash,
           actual_dd_pct=dd * 100, actual_max_dd_pct=g.native_max_dd * 100,
           cash_pct=context.portfolio.available_cash / value * 100)
    plan = g.native_plan
    if plan is None:
        return
    remaining = _remaining(context, plan['targets'])
    if not remaining and not _pending_codes():
        log.info('本轮目标持仓已完成（不足一手差异按取整容差处理）')
        g.native_plan = None
    elif plan['attempts'] >= MAX_REBALANCE_DAYS:
        _cancel_own_orders()
        log.warn('本轮补单窗口结束，未完成份额：%s；保留实际持仓，下一季度重新调仓' % remaining)
        g.native_plan = None
        if g.native_total_fills == 0:
            raise RuntimeError('连续 %d 个交易日没有任何原生成交；请查看委托拒绝原因、'
                               '行情和成交量。不会把空仓标记为建仓成功。' % MAX_REBALANCE_DAYS)


def on_strategy_end(context):
    value = _py.float(context.portfolio.total_value)
    log.info('v3 场内撮合结束：提交委托%d笔、原生成交%d笔、实际总资产%.2f；'
             '累计收益%.4f%%、收盘最大回撤%.4f%%。原生报告与交易记录均可查看。' %
             (g.native_total_orders, g.native_total_fills, value,
              (value / context.portfolio.starting_cash - 1) * 100, g.native_max_dd * 100))
    if g.native_plan is not None:
        log.warn('回测在调仓执行期间结束；未完成目标：%s' %
                 _remaining(context, g.native_plan['targets']))
