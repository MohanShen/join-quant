# Clone from JoinQuant
# postId: 5e914b320c686b46f7de7643bb8b9884
# backtestId: 05062ee2cb8bd2fbd017b06486570b47
# title: RSRS使用的加权最小二乘法是不是出了问题？

# 克隆自聚宽文章：https://www.joinquant.com/post/27399
# 标题：RSRS择时改进-【成交量加权-钝化-右偏】
# 作者：uuyue

# 克隆自聚宽文章：https://www.joinquant.com/post/27399
# 标题：RSRS择时改进-【成交量加权-钝化-右偏】
# 作者：uuyue

# 成交量加权的4种RSRS #
# 成交量加权-右偏标准分        vol_rsrs_right      = z_score*beta*r2
# 成交量加权-钝化-右偏标准分   vol_rsrs_right_dun  = z_score*beta*(r2**(2*std_percent))
# 成交量加权-无偏标准分        vol_rsrs            = z_score*r2
# 成交量加权-钝化-无偏标准分   vol_rsrs_dun        = z_score*(r2**(2*std_percent))

from jqdata import *
import statsmodels.api as sm
import scipy.stats as stats


def initialize(context):
    # type: (Context) -> None
    g.security = '000300.XSHG'

    # 成交量加权-右偏标准分
    g.N = 18
    g.M = 200
    g.buy = 0.85
    g.sell = -g.buy
    g.run_time = '14:00'  # 14:00

    '''
    #成交量加权-钝化-右偏标准分
    g.N = 18
    g.M = 200
    g.buy = 0.75
    g.sell = -g.buy
    g.run_time = '14:00'

    #成交量加权-无偏标准分   
    g.N = 17
    g.M = 1300
    g.buy = 0.9
    g.sell = -g.buy
    g.run_time = '9:30'  

    #成交量加权-钝化-无偏标准分    
    g.N = 16
    g.M = 1100
    g.buy = 0.7
    g.sell = -g.buy
    g.run_time = '9:30' 
    '''
    # 中间变量
    g.beta_weight = []
    g.r2_weight = []
    g.volatility = []
    g.pos = False
    g.days = 0
    g.rsrs = 0

    set_option('order_volume_ratio', 0.002)  # 成交量不得超过标的日成交量的千分之2
    set_option('use_real_price', True)  # 开启动态复权模式(真实价格)
    set_benchmark('000300.XSHG')  # 设定上证指数作为基准
    log.set_level('order', 'error')  # 过滤掉order系列API产生的比error级别低的log

    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    run_daily(market_open, time=g.run_time, reference_security='000300.XSHG')


def calc_beta_r2(highs, lows, volumes):
    # type: (np.ndarray, np.ndarray, np.ndarray) -> (float, float)
    # 成交量加权的权重列表
    weights = volumes / volumes.sum()

    # 加权最小二乘法  #sm.WLS(y, xx, weights)
    xx = sm.add_constant(lows)  # 为模型增加常数项，即回归线在y轴上的截距(括号里面写上自变量)
    model = sm.WLS(highs, xx, weights).fit()  # 加权最小二乘法
    beta = model.params[1]  # model.params.low
    r2 = model.rsquared
    return beta, r2


def init_rsrs(context):
    # type: (Context) -> None

    # 计算2005年1月5日至回测开始日期的RSRS斜率指标
    prices = get_price(g.security, '2005-05-01', context.previous_date, '1d', ['high', 'low', 'volume'])
    all_highs = prices.high.values
    all_lows = prices.low.values
    all_volumes = prices.volume.values
    #
    for i in range(0, len(all_highs) - g.N + 1):  # range(a,b)=[a,b)
        highs = all_highs[i:i + g.N]  # dataframe 不包括[a:b]中的b，相当于[a:b)
        lows = all_lows[i:i + g.N]
        volumes = all_volumes[i:i + g.N]
        #
        beta, r2 = calc_beta_r2(highs, lows, volumes)
        #
        g.beta_weight.append(beta)
        g.r2_weight.append(r2)

    # 计算2005-01-01至开盘前一天的指数日收益率的波动率
    daily_return = get_price(g.security, '2005-05-01', context.previous_date, '1d',
                             'close')['close'].pct_change()[1:].values
    for i in range(0, len(daily_return) - g.N + 1):
        std = np.std(daily_return[i:i + g.N])
        g.volatility.append(std)


def before_market_open(context):
    # type: (Context) -> None
    if g.days == 0:  # 初始化rsrs数据
        g.days = 1
        # 初始化rsrs所需数据
        init_rsrs(context)
    elif g.days == 1:
        prices = attribute_history(g.security, g.N, '1d', ['high', 'low', 'volume'], df=False)
        highs = prices['high']
        lows = prices['low']
        volumes = prices['volume']
        #
        beta, r2 = calc_beta_r2(highs, lows, volumes)
        #
        g.beta_weight.append(beta)
        g.r2_weight.append(r2)

        # 计算N日收益率的标准差、M日收益率标准差的分位数（钝化RSRS所需）
        # 用过去g.N天的数据,计算波动率,并获取它在过去g.M所处的百分位
        daily_return = attribute_history(g.security, g.N + 1, '1d', ['close'])['close'].pct_change()[1:].values
        # 计算N日收益率的标准差
        std = np.std(daily_return)
        g.volatility.append(std)

        # ---------------------------
        # 计算rsrs
        # ---------------------------
        # 标准化/归一化
        section = g.beta_weight[-g.M:]
        mu = np.mean(section)
        sigma = np.std(section)
        z_score = (section[-1] - mu) / sigma
        # 右偏标准分
        vol_rsrs_right = z_score * beta * r2  # 成交量加权-右偏标准分
        # 其它的rsrs
        vol_rsrs = z_score * r2  # 成交量加权-无偏标准分
        std_percent = stats.percentileofscore(g.volatility[-g.M:], std) / 100  # 计算M日收益率标准差的分位数
        vol_rsrs_right_dun = z_score * beta * (r2 ** (2 * std_percent))  # 钝化-成交量加权-右偏标准分
        vol_rsrs_dun = z_score * (r2 ** (2 * std_percent))  # 钝化-成交量加权-无偏标准分
        
        log.info('z_score= %.3f, beta= %.3f, r2= %.3f, std= %.3f, std_percent= %.3f' % (
            z_score, beta, r2, std, std_percent))
        log.info('成交量加权-右偏rsrs     = %.3f，成交量加权-无偏rsrs     = %.3f' % (vol_rsrs_right, vol_rsrs))
        log.info('钝化-成交量加权-右偏rsrs= %.3f，钝化-成交量加权-无偏rsrs= %.3f' % (vol_rsrs_right_dun, vol_rsrs_dun))
        
        # 成交量加权-右偏标准分        vol_rsrs_right      = z_score*beta*r2
        # 成交量加权-钝化-右偏标准分   vol_rsrs_right_dun  = z_score*beta*(r2**(2*std_percent))
        # 成交量加权-无偏标准分        vol_rsrs            = z_score*r2
        # 成交量加权-钝化-无偏标准分   vol_rsrs_dun        = z_score*(r2**(2*std_percent))
        g.rsrs = vol_rsrs_right
        log.info('g.rsrs=%.3f' % g.rsrs)


def market_open(context):
    # type: (Context) -> None
    if g.rsrs > g.buy and (not g.pos):
        log.info('buy')
        order_value(g.security, context.portfolio.available_cash)
        g.pos = True
    elif g.rsrs < g.sell and g.pos:
        log.info('sell')
        order_target(g.security, 0)
        g.pos = False
