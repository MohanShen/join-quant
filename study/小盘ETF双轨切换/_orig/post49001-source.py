# 克隆自聚宽文章：https://www.joinquant.com/post/48284
# 标题：蛇皮走位小市值策略V1.0
# 作者：MarioC

# 克隆自聚宽文章：https://www.joinquant.com/post/45510
# 标题：5年15倍的收益，年化79.93%，可实盘，拿走不谢！
# 作者：langcheng999

import warnings

from jqdata import *

warnings.filterwarnings("ignore")


def initialize(context):
    # 设置基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 设置日志级别为error
    log.set_level('order', 'error')

    g.stock_num = 10  # 持股数量
    g.type=''
    g.Counterattack_Days=30#偷鸡持续天数
    g.Days=0
    # 准备昨日涨停且正在持有的股票列表
    run_daily(prepare_high_limit_list, time='9:05', reference_security='000300.XSHG')
    # 每天调整昨日涨停股票
    run_daily(check_limit_up, time='14:00')
    run_daily(consistent, time='9:30')
    g.m_days = 25 #动量参考天数
    g.etf_pool = [
        '518880.XSHG', #黄金ETF（大宗商品）
        '513100.XSHG', #纳指100（海外资产）
        '159915.XSHE', #创业板100（成长股，科技股，中小盘）
        '510180.XSHG', #上证180（价值股，蓝筹股，中大盘）
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
    df = pd.DataFrame(index=etf_pool, data={'score':score_list})
    df = df.sort_values(by='score', ascending=False)
    rank_list = list(df.index)    
    return rank_list
    
def DDDD(context):
    #你要偷鸡还是摸狗呢？
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
    return variance,mean

# 1-3 整体调整持仓
def consistent(context):
    print(g.type)
    if g.type=='偷鸡':
        if g.Days <g.Counterattack_Days:
            g.Days=g.Days+1
            pass
        if g.Days == g.Counterattack_Days:
            g.type='摸狗'
            for stock in context.portfolio.positions.keys():
                order_target_value(stock, 0)
            g.Days=0
    else:
        variance,mean = DDDD(context)
        if variance < 0.02 and mean>0:
            g.type='偷鸡'
        else:
            g.type='摸狗'

    if g.type=='摸狗':
        target_num = 1
        target_list = get_rank(g.etf_pool)[:target_num]
        hold_list = list(context.portfolio.positions)
        for etf in hold_list:
            if etf not in target_list:
                order_target_value(etf, 0)
                print('卖出' + str(etf))
            else:
                print('继续持有' + str(etf))
                pass
        value = context.portfolio.available_cash
        if value>10000:
            for s in target_list:
                order_value(s, value)

    if g.type=='偷鸡':
        if g.Days==0:
            target_list = choose_stocks(context)
            current_data = get_current_data()
            for s in context.portfolio.positions:
                if s in target_list or current_data[s].paused or current_data[s].last_price == current_data[s].high_limit:
                    continue
                log.info('Sell: %s %s' % (s, get_current_data()[s].name))
                order_target(s, 0)
            to_buy(context, target_list)
                        
def prepare_high_limit_list(context):
    g.high_limit_list = []
    hold_list = list(context.portfolio.positions)
    if hold_list:
        g.high_limit_list = get_price(
            hold_list, end_date=context.previous_date, frequency='daily',
            fields=['close', 'high_limit', 'paused'],
            count=1, panel=False).query('close == high_limit and paused == 0')['code'].tolist()

def check_limit_up(context):
    hold_list = list(context.portfolio.positions)
    num = 0
    now_time = context.current_dt
    if g.high_limit_list != []:
        for stock in g.high_limit_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'],
                                     skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                close_position(context,stock)
                num = num+1
            else:
                log.info("[%s]涨停，继续持有" % (stock))
    SS=[]
    S=[]
    for stock in hold_list:
        if stock not in g.etf_pool:
            if stock in list(context.portfolio.positions.keys()):
                if context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * 0.90:
                    order_target_value(stock, 0)
                    log.debug("止损 Selling out %s" % (stock))
                    num = num+1
                else:
                    S.append(stock)
                    NOW = (context.portfolio.positions[stock].price - context.portfolio.positions[stock].avg_cost)/context.portfolio.positions[stock].avg_cost
                    SS.append(np.array(NOW))
    if num >=1:
        if len(SS) > 0:
            NNN=3
            min_values = sorted(SS)[:NNN]
            min_indices = [SS.index(value) for value in min_values]
            min_strings = [S[index] for index in min_indices]
            cash = context.portfolio.cash/NNN
            for ss in min_strings:
                order_value(ss, cash)
                log.debug("补跌最多的N支 Order %s" % (ss))
# 每月选股
def choose_stocks(context):
    # 2-6 过滤次新股
    by_date = context.previous_date - datetime.timedelta(days=250)
    stocks = get_all_securities('stock', by_date).index.tolist()
    # 4 各种过滤
    stocks = filter_stock_basic(stocks)
    # 5 低价股
    stocks = filter_high_price_stock(stocks)
    # 3 基本面筛选，并根据小市值排序
    stocks = get_peg(stocks)
    # 截取不超过最大持仓数的股票量
    return stocks[:g.stock_num]


def filter_stock_basic(stock_list):
    curr_data = get_current_data()
    return [
        stock for stock in stock_list if not
        (
                stock.startswith(('68', '4', '8','3')) or  # '3', 创业，科创，北交所
                curr_data[stock].paused or
                curr_data[stock].is_st or  # ST
                (curr_data[stock].last_price >= curr_data[stock].high_limit * 0.97) or  # 涨停开盘, 其它时间用last_price
                (curr_data[stock].last_price <= curr_data[stock].low_limit * 1.04)  # 跌停开盘, 其它时间用last_price
        )]


# 2-4 过滤股价高于10元的股票
def filter_high_price_stock(stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list).iloc[0]
    return last_prices[last_prices < 10].index.tolist()


def to_buy(context, target_list):
    position_count = len(context.portfolio.positions)
    if position_count < g.stock_num:
        value = context.portfolio.available_cash / (g.stock_num - position_count)
        for s in target_list:
            if s not in context.portfolio.positions:
                log.info('buy: %s %s' % (s, get_current_data()[s].name))
                order_value(s, value)
                if len(context.portfolio.positions) == g.stock_num:
                    break


# 基本面筛选，并根据小市值排序
def get_peg(stocks):
    # 基本面选股
    stocks = get_fundamentals(
        query(
            valuation.code,
        ).filter(
            indicator.roe > 0.15,
            indicator.roa > 0.10,
            valuation.code.in_(stocks)
        ).order_by(
            valuation.market_cap.asc()  
        )
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
