# Clone from JoinQuant
# postId: 1587c799ecebd986f9b0de4a5cc1f5b8
# backtestId: 98648a3b393d9a29f20261aeea91557a
# title: 年化20%+|滚IC吃贴水策略

# 导入函数库
from jqdata import *
import datetime


## 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000852.XSHG')
    # 上证50，沪深300，中证500，中证1000
    g.etfs = ["000016.XSHG","000300.XSHG","000905.XSHG","000852.XSHG"]
    g.contracts = ["IH","IF","IC","IM"]
    g.contract = ""
    g.margin = 0.15 # 保证金比例
    g.safety = 0.20 # 通常需要在保证金基础上预留额外的资金作为安全垫
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    log.info('初始函数开始运行且全局只运行一次')

    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', g.margin)
    set_slippage(StepRelatedSlippage(0.00001))
    run_daily(before_market_open, "09:30")
    run_daily(trade, "10:00")


## 开盘前运行函数
def before_market_open(context):
    # 长持IM
    g.contract = get_dominant_future(g.contracts[3], date=context.current_dt)
    # 基差
    close1 = attribute_history(g.contract, 1, '1d', ['close']).values[0]
    close2 = attribute_history(g.etfs[3], 1, '1d', ['close']).values[0]
    record(基差=close1-close2)
    return
    
    # 计算动量
    ranks,scores = get_rank()
    record(score=scores[0])
    for etf,code in zip(g.etfs, g.contracts):
        if ranks[0] == etf:
            g.contract = get_dominant_future(code, date=context.current_dt)
            log.info(f"今日最强动量：{etf}[{round(scores[0],3)}]，选择股指：{g.contract}")
            break

def trade(context):
    end_date = get_security_info(g.contract).end_date
    if end_date <= context.current_dt.date() and len(context.portfolio.long_positions)>0: # 非交割日且当前有持仓
        return
    for position in context.portfolio.long_positions.values():
        if position.security != g.contract:
            if close_long_position(position):
                log.info(f'已平仓{position.security}多头')
            else:
                log.info(f'平仓{position.security}多头失败或未完全平仓')
        else:
            log.info(f'继续持有{position.security}多头')
    
    # 开新仓位
    if len(context.portfolio.long_positions) < 1 and g.contract: # 未持仓才开仓
        # 根据保证金计算可开仓手数，
        close = attribute_history(g.contract, 1, '1d', ['close']).values[0]
        # 这是一手需要的最少资金
        unit = close * 200 * (g.margin+g.safety)
        num = int(context.portfolio.available_cash // unit)
        if num >= 1: # 最少1手可开仓
            order_ = order_target(g.contract, num, side='long')
            if order_ != None:
                log.info(f'买入{g.contract}多头{num}手')
            else:
                log.error(f'买入{g.contract}多头委托创建失败或下单数量为0')
        else:
            log.warning(f"可用资金不足以开仓：{context.portfolio.available_cash}, {close},{unit}")

def close_long_position(position):
    security = position.security
    order = order_target_value(security, 0, side='long')  
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False


# 动量因子：基于年化收益和判定系数打分的动量因子轮动
def get_rank():
    momentum_day = 30 #动量的天数，设置的太短轮动时间会很快，交易过于频繁，设置太长，灵敏度又很差，一个月左右较为合适。
    score_list = []
    values = []
    for etf in g.etfs:
        df = attribute_history(etf, momentum_day, '1d', ['close'])
        y = df['log'] = np.log(df.close)
        x = df['num'] = np.arange(df.log.size)
        slope, intercept = np.polyfit(x, y, 1)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
        score = annualized_returns * r_squared
        score_list.append(score)
        
    df = pd.DataFrame(index=g.etfs, data={'score':score_list})
    df = df.sort_values('score', ascending=False)
    rank_list = list(df.index)
    score_list = list(df.score)
    return rank_list,score_list
