# Clone from JoinQuant
# postId: 0d1bbe83e05b19c73d1bfe9f4efda477
# backtestId: 411d1cea657032b8c260eeb6b0f04be3
# title: 年化51%的晴雨双轨：小盘游击+ETF防御

# 克隆自聚宽文章：https://www.joinquant.com/post/49001
# 标题：偷鸡摸狗策略
# 作者：MarioC

# ====================================================================
# 审查修复说明（未来函数排查 + 实盘可行性评估）
# ====================================================================
# 未来函数排查结论：逐一核对了 attribute_history/get_price/get_fundamentals/
# get_index_stocks/get_all_securities/history/get_current_data 的取数边界，
# 未发现真正的未来函数漏洞（所有取数都以 previous_date/current_dt 为界）。
# 以下是本轮修复内容：
#
# [FIX-1] get_peg 调用 get_fundamentals 未传 date，依赖平台"默认取前一天"
#         的隐式规则。改为显式传入 context.previous_date，与 DDDD 里的
#         写法保持一致，避免依赖隐式默认行为。
# [FIX-2] prepare_high_limit_list 的 get_price 未传 fq 参数。close 与
#         high_limit 的相等比较依赖两者用同一复权方式，显式传 fq='pre'
#         避免未来平台默认值变化导致比较失效。
# [FIX-3] check_limit_up 补跌加仓中 `SS.index(value)` 在 SS 出现重复值
#         时永远命中第一个下标，会导致重复选中同一只股票、漏选本该
#         入选的另一只。改为按下标排序取值，避免同值歧义。
# [FIX-4] ETF 轮动买入（摸狗模式）和补跌加仓买入前补充停牌检查，避免
#         对停牌标的下单静默失败且无记录。
# [FIX-5] 新增 set_option('avoid_future_data', True) 作为未来函数的
#         平台级兜底（strategy1.py 已采用同样做法）。因为审查未发现
#         未来函数问题，预期不会改变回测结果；如果启用后报错，说明
#         存在本轮审查未覆盖到的取数点，需要进一步排查。
# [FIX-6] 新增 set_slippage / set_order_cost（股票 + 基金两档）。原策略
#         完全没有设置滑点和手续费，回测收益会明显偏乐观。这里沿用
#         strategy1.py 里已经和你确认过的同一套假设（滑点按价格0.2%，
#         佣金万1，最低5元，股票卖出印花税0.1%，基金无印花税）。
#         这套参数是通用假设，务必结合你实际的券商费率复核调整。
#         【会改变回测收益数字，且预期是显著下降，属于修复后的正常变化】
# [FIX-7] 顶层入口函数（prepare_high_limit_list / consistent /
#         check_limit_up）增加 try/except + log.error，单次取数异常
#         不会导致当天调度整体崩溃。
# [FIX-8] 硬编码参数（止损线、低价股阈值、ROE/ROA 门槛、持仓数量、
#         补跌加仓只数、ETF 现金门槛、次新股过滤天数、市场状态阈值等）
#         集中到 initialize 顶部配置区，逻辑不变，仅为了实盘调参方便。
# [FIX-9] print() 替换为 log.info，便于实盘环境下留痕排查。
# [FIX-10] 下单处补充"是否提交成功"的日志记录（order 返回 None 视为
#          提交失败），不改变下单逻辑本身。
#
# ── 未采纳自动修改的问题（保留原策略意图，未经你确认不擅自改动）──
# [待确认] 止损后"补跌"向下加仓（买入当前持仓中跌幅最大的N支）是马丁
#          格尔式摊薄逻辑，实盘资金风险较高，本轮只修复了其中的选股
#          bug（FIX-3），未改变这个加仓方向本身。
# [待确认] "偷鸡"模式一旦进入，固定持有 Counterattack_Days（默认30）天
#          后才会强制转"摸狗"，期间不会因市场状态（DDDD 信号）逆转而
#          提前退出。是否需要提前退出机制，需要你确认后再改。
# [待确认] filter_stock_basic 用股票代码前缀猜测板块（'68'/'4'/'8'/'3'）
#          较为粗糙，未改动，因为会直接影响选股范围。
# [待确认] check_limit_up 每天只在14:00检测一次涨停打开，14:00-15:00
#          之间的风险敞口未做额外监控，未改动，因为涉及下单频率，
#          需要你评估券商/交易所限速后再决定是否加密监控频次。
# ====================================================================

import warnings

from jqdata import *

warnings.filterwarnings("ignore")


def initialize(context):
    # 设置基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # ─── [FIX-5] 平台级未来函数兜底 ───
    set_option('avoid_future_data', True)
    # 设置日志级别为error
    log.set_level('order', 'error')

    # ─── [FIX-6] 滑点与手续费（原策略完全未设置，回测收益会明显偏乐观）
    # 滑点按价格0.2%双边估算，佣金万1、最低5元，股票卖出印花税0.1%，
    # 基金（ETF）无印花税。这是通用假设，请结合实际券商费率复核 ───
    set_slippage(PriceRelatedSlippage(0.002))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                              open_commission=1 / 10000, close_commission=1 / 10000,
                              close_today_commission=0, min_commission=5),
                   type='stock')
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                              open_commission=1 / 10000, close_commission=1 / 10000,
                              close_today_commission=0, min_commission=5),
                   type='fund')

    g.stock_num = 10  # 持股数量
    g.type = ''
    g.Counterattack_Days = 30  # 偷鸡持续天数
    g.Days = 0
    g.m_days = 25  # 动量参考天数

    # ─── [FIX-8] 集中管理原先散落在各函数体内的硬编码参数 ───
    g.stop_loss_ratio = 0.90       # 个股止损线：跌破成本价90%止损
    g.low_price_limit = 10         # 选股低价股阈值（元）
    g.min_roe = 0.15               # 基本面筛选：ROE下限
    g.min_roa = 0.10               # 基本面筛选：ROA下限
    g.new_stock_filter_days = 250  # 次新股过滤天数
    g.regime_variance_threshold = 0.02  # 市场状态判断：方差阈值
    g.rebalance_top_n = 3          # 补跌加仓只数
    g.etf_target_num = 1           # 摸狗模式ETF持仓只数
    g.etf_min_cash = 10000         # 摸狗模式买入ETF的最低现金门槛

    # 准备昨日涨停且正在持有的股票列表
    run_daily(prepare_high_limit_list, time='9:05', reference_security='000300.XSHG')
    # 每天调整昨日涨停股票
    run_daily(check_limit_up, time='14:00')
    run_daily(consistent, time='9:30')
    g.etf_pool = [
        '518880.XSHG',  # 黄金ETF（大宗商品）
        '513100.XSHG',  # 纳指100（海外资产）
        '159915.XSHE',  # 创业板100（成长股，科技股，中小盘）
        '510180.XSHG',  # 上证180（价值股，蓝筹股，中大盘）
    ]


def MOM(etf):
    df = attribute_history(etf, g.m_days, '1d', ['close'])
    y = np.log(df['close'].values)
    n = len(y)
    x = np.arange(n)
    weights = np.linspace(1, 2, n)
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    annualized_returns = math.pow(math.exp(slope), 250) - 1
    residuals = y - (slope * x + intercept)
    weighted_residuals = weights * residuals**2
    r_squared = 1 - (np.sum(weighted_residuals) / np.sum(weights * (y - np.mean(y))**2))
    score = annualized_returns * r_squared
    return score


def get_rank(etf_pool):
    score_list = []
    for etf in etf_pool:
        score = MOM(etf)
        score_list.append(score)
    df = pd.DataFrame(index=etf_pool, data={'score': score_list})
    df = df.sort_values(by='score', ascending=False)
    rank_list = list(df.index)
    return rank_list


def DDDD(context):
    # 你要偷鸡还是摸狗呢？
    yesterday = context.previous_date
    stocks = get_index_stocks('399101.XSHE', yesterday)
    q = query(
        valuation.code, valuation.circulating_market_cap, indicator.eps
    ).filter(
        valuation.code.in_(stocks)
    ).order_by(
        valuation.circulating_market_cap.asc()
    )
    df = get_fundamentals(q, date=yesterday)
    lst = list(df.code)[:20]
    h_ratio = get_price(lst, end_date=yesterday, frequency='1d', fields=['close'], count=2, panel=False
                        ).pivot(index='time', columns='code', values='close')
    change_BIG = (h_ratio.iloc[-1] / h_ratio.iloc[0] - 1) * 100
    A1 = np.array(change_BIG)
    norm = np.linalg.norm(A1)
    normalized_array = A1 / norm
    variance = np.var(normalized_array)
    mean = np.mean(normalized_array)
    return variance, mean


# 1-3 整体调整持仓
def consistent(context):
    # ─── [FIX-7] 顶层入口增加异常捕获，单次取数异常不影响后续调度 ───
    try:
        log.info('当前模式: %s' % g.type)  # [FIX-9] print -> log.info
        if g.type == '偷鸡':
            if g.Days < g.Counterattack_Days:
                g.Days = g.Days + 1
            if g.Days == g.Counterattack_Days:
                g.type = '摸狗'
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
                g.Days = 0
        else:
            variance, mean = DDDD(context)
            if variance < g.regime_variance_threshold and mean > 0:
                g.type = '偷鸡'
            else:
                g.type = '摸狗'

        if g.type == '摸狗':
            current_data = get_current_data()
            target_list = get_rank(g.etf_pool)[:g.etf_target_num]
            hold_list = list(context.portfolio.positions)
            for etf in hold_list:
                if etf not in target_list:
                    order_target_value(etf, 0)
                    log.info('卖出' + str(etf))  # [FIX-9] print -> log.info
                else:
                    log.info('继续持有' + str(etf))  # [FIX-9] print -> log.info
            value = context.portfolio.available_cash
            if value > g.etf_min_cash:
                for s in target_list:
                    if current_data[s].paused:  # [FIX-4] 停牌检查
                        log.info('ETF %s 停牌，跳过买入' % s)
                        continue
                    _order = order_value(s, value)
                    if _order is None:  # [FIX-10] 下单结果记录
                        log.error('ETF %s 买入委托提交失败' % s)

        if g.type == '偷鸡':
            if g.Days == 0:
                target_list = choose_stocks(context)
                current_data = get_current_data()
                for s in context.portfolio.positions:
                    if s in target_list or current_data[s].paused or current_data[s].last_price == current_data[s].high_limit:
                        continue
                    log.info('Sell: %s %s' % (s, get_current_data()[s].name))
                    order_target(s, 0)
                to_buy(context, target_list)
    except Exception as e:
        log.error('consistent 执行异常: %s' % e)


def prepare_high_limit_list(context):
    # ─── [FIX-7] 顶层入口增加异常捕获 ───
    try:
        g.high_limit_list = []
        hold_list = list(context.portfolio.positions)
        if hold_list:
            g.high_limit_list = get_price(
                hold_list, end_date=context.previous_date, frequency='daily',
                fields=['close', 'high_limit', 'paused'], fq='pre',  # [FIX-2] 显式指定复权方式
                count=1, panel=False).query('close == high_limit and paused == 0')['code'].tolist()
    except Exception as e:
        log.error('prepare_high_limit_list 执行异常: %s' % e)


def check_limit_up(context):
    # ─── [FIX-7] 顶层入口增加异常捕获 ───
    try:
        hold_list = list(context.portfolio.positions)
        num = 0
        now_time = context.current_dt
        if g.high_limit_list != []:
            for stock in g.high_limit_list:
                current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'],
                                         skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
                if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                    log.info("[%s]涨停打开，卖出" % (stock))
                    close_position(context, stock)
                    num = num + 1
                else:
                    log.info("[%s]涨停，继续持有" % (stock))
        SS = []
        S = []
        for stock in hold_list:
            if stock not in g.etf_pool:
                if stock in list(context.portfolio.positions.keys()):
                    if context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stop_loss_ratio:
                        order_target_value(stock, 0)
                        log.info("止损 Selling out %s" % (stock))  # [FIX-9] log.debug -> log.info，止损是关键决策点
                        num = num + 1
                    else:
                        S.append(stock)
                        NOW = (context.portfolio.positions[stock].price - context.portfolio.positions[stock].avg_cost) / context.portfolio.positions[stock].avg_cost
                        SS.append(np.array(NOW))
        if num >= 1:
            if len(SS) > 0:
                NNN = g.rebalance_top_n
                # ─── [FIX-3] 原来用 SS.index(value) 按值查下标，SS 出现
                # 重复值时会重复命中同一个下标，导致重复选中同一只股票、
                # 漏选另一只。改为直接对下标排序，避免同值歧义 ───
                order_idx = sorted(range(len(SS)), key=lambda i: SS[i])[:NNN]
                min_strings = [S[i] for i in order_idx]
                cash = context.portfolio.cash / NNN
                current_data = get_current_data()
                for ss in min_strings:
                    if current_data[ss].paused:  # [FIX-4] 停牌检查
                        log.info('补跌加仓标的 %s 停牌，跳过' % ss)
                        continue
                    _order = order_value(ss, cash)
                    if _order is None:  # [FIX-10] 下单结果记录
                        log.error('补跌加仓 %s 委托提交失败' % ss)
                    else:
                        log.info("补跌最多的N支 Order %s" % (ss))  # [FIX-9] log.debug -> log.info
    except Exception as e:
        log.error('check_limit_up 执行异常: %s' % e)


# 每月选股
def choose_stocks(context):
    # 2-6 过滤次新股
    by_date = context.previous_date - datetime.timedelta(days=g.new_stock_filter_days)
    stocks = get_all_securities('stock', by_date).index.tolist()
    # 4 各种过滤
    stocks = filter_stock_basic(stocks)
    # 5 低价股
    stocks = filter_high_price_stock(stocks)
    # 3 基本面筛选，并根据小市值排序
    stocks = get_peg(stocks, context.previous_date)
    # 截取不超过最大持仓数的股票量
    return stocks[:g.stock_num]


def filter_stock_basic(stock_list):
    curr_data = get_current_data()
    return [
        stock for stock in stock_list if not
        (
                stock.startswith(('68', '4', '8', '3')) or  # '3', 创业，科创，北交所
                curr_data[stock].paused or
                curr_data[stock].is_st or  # ST
                (curr_data[stock].last_price >= curr_data[stock].high_limit * 0.97) or  # 涨停开盘, 其它时间用last_price
                (curr_data[stock].last_price <= curr_data[stock].low_limit * 1.04)  # 跌停开盘, 其它时间用last_price
        )]


# 2-4 过滤股价高于阈值的股票
def filter_high_price_stock(stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list).iloc[0]
    return last_prices[last_prices < g.low_price_limit].index.tolist()


def to_buy(context, target_list):
    position_count = len(context.portfolio.positions)
    if position_count < g.stock_num:
        value = context.portfolio.available_cash / (g.stock_num - position_count)
        for s in target_list:
            if s not in context.portfolio.positions:
                log.info('buy: %s %s' % (s, get_current_data()[s].name))
                _order = order_value(s, value)
                if _order is None:  # [FIX-10] 下单结果记录
                    log.error('%s 买入委托提交失败' % s)
                if len(context.portfolio.positions) == g.stock_num:
                    break


# 基本面筛选，并根据小市值排序
def get_peg(stocks, date):
    # 基本面选股
    # ─── [FIX-1] 原来 get_fundamentals 未传 date，依赖平台隐式默认值，
    # 显式传入 context.previous_date，和 DDDD 里的取数方式保持一致 ───
    stocks = get_fundamentals(
        query(
            valuation.code,
        ).filter(
            indicator.roe > g.min_roe,
            indicator.roa > g.min_roa,
            valuation.code.in_(stocks)
        ).order_by(
            valuation.market_cap.asc()
        ),
        date=date
    )['code'].tolist()
    return stocks


# 3-3 交易模块-平仓
def close_position(context, security):
    if security in context.portfolio.positions and context.portfolio.positions[security].closeable_amount > 0:
        _order = order_target_value(security, 0)  # 可能会因停牌失败
        if _order is not None:
            if _order.status == OrderStatus.held and _order.filled == _order.amount:
                return True
    return False
