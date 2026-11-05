# Clone from JoinQuant
# postId: 85a7fb5f447e650f2bf923d61dd737f4
# backtestId: 1857a31975ec53bca44649d2bb6d60ea
# title: 股市作手操盘术策略

class Trend(Enum):
    SecondaryRally    = 1
    NaturalRally      = 2
    Upward            = 3
    Downward          = 4
    NaturalReaction   = 5
    SecondaryReaction = 6
    Unknow            = 7

class CashState(Enum):
    Buy    = 1
    Sell   = 2
    Unknow = 3

def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    g.security   = '600030.XSHG'
    #g.security   = '510300.XSHG'
    g.initPrice  = 0
    g.trend      = Trend.Unknow
    g.cashState  = CashState.Unknow
    
    g.upwardPrice            = 0
    g.naturalRallyPrice      = 0
    g.naturalReactionPrice   = 0
    g.secondaryRallyPrice    = 0
    g.secondaryReactionPrice = 0
    g.downwardPrice          = 0
    g.stopPrice              = 0

    # 初始化此策略
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    set_universe([g.security])

def buyStock(context, cash, current_price):
    #if g.cashState == CashState.Sell or g.cashState == CashState.Unknow:
        #g.cashState  = CashState.Buy
    if cash > 5000:
        order_value(g.security, cash)
        g.stopPrice = 0.9*current_price
        log.info("Buying %s" % (g.security))

def SellStock(context, cash):
    if context.portfolio.positions[g.security].amount > 0:
        #g.cashState  = CashState.Sell
        order_target(g.security, 0)
        log.info("Selling %s" % (g.security))

# 上升趋势
def handleUpward(context, current_price, cash): 
    if current_price > g.upwardPrice:
        g.upwardPrice = current_price
    elif current_price < 0.94*g.upwardPrice:
        log.info("[自然回撤]")
        g.trend = Trend.NaturalRally
        g.naturalRallyPrice = current_price

# 自然回撤
def handleNaturalRally(context, current_price, cash):
    if current_price < g.naturalRallyPrice:
        g.naturalRallyPrice = current_price
        if current_price < 0.97*g.downwardPrice or current_price < 0.97*g.secondaryReactionPrice:
            g.downwardPrice = current_price
            g.trend = Trend.Downward
            SellStock(context, cash)
    elif current_price > 1.06*g.naturalRallyPrice:
        log.info("[自然回升]")
        g.trend = Trend.NaturalReaction
        g.naturalReactionPrice = current_price
        
# 自然回升
def handleNaturalReaction(context, current_price, cash):
    if current_price > g.naturalReactionPrice:
        g.naturalReactionPrice = current_price
        if current_price > 1.03*g.upwardPrice:
            buyStock(context, cash, current_price)
            log.info("[上升趋势]")
            g.upwardPrice = current_price
            g.trend = Trend.Upward
    elif current_price < 0.94*g.naturalReactionPrice:
            log.info("[次级回撤]")
            g.trend = Trend.SecondaryRally
            g.secondaryRallyPrice = current_price
            
# 次级回撤
def handleSecondaryRally(context, current_price, cash):
    if current_price < g.secondaryRallyPrice:
        g.secondaryRallyPrice = current_price
        #if current_price < 0.97*g.naturalReactionPrice:
        #    SellStock(context, cash)
        #    g.trend = Trend.Downward
        #    log.info("[下降趋势]")
        if current_price < 0.97*g.naturalRallyPrice:
            SellStock(context, cash)
            g.trend = Trend.Downward
            log.info("[下降趋势]")
    elif current_price > 1.06*g.secondaryRallyPrice:
        log.info("[次级回升]")
        g.trend = Trend.SecondaryReaction
        g.secondaryReactionPrice = current_price
        
# 次级回升
def handleSecondaryReaction(context, current_price, cash):
    if current_price > g.secondaryReactionPrice:
        g.secondaryReactionPrice = current_price
        if current_price > 1.03*g.naturalReactionPrice:
            log.info("[上升趋势]")
            buyStock(context, cash, current_price)
            g.upwardPrice = current_price
            g.trend = Trend.Upward
    elif current_price < 0.94*g.naturalReactionPrice:
            log.info("[下降趋势]")
            SellStock(context, cash)
            g.trend = Trend.Downward
            g.downwardPrice = current_price
    
# 处于下降趋势中
def handleDownward(context, current_price, cash):
    #下降趋势
    if current_price < g.downwardPrice:
        g.downwardPrice = current_price
        #SellStock(context, cash)
    elif current_price > 1.06*g.downwardPrice:
        log.info("[自然回升]")
        g.trend = Trend.NaturalReaction
        g.naturalReactionPrice = current_price

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security

    current_price = data[security].close
    cash = context.portfolio.cash

    if g.initPrice == 0:
        g.initPrice = current_price
        return

    if g.trend == Trend.Unknow:
        if current_price > 1.06*g.initPrice:
            g.trend = Trend.Upward
            g.upwardPrice = current_price
            buyStock(context, cash, current_price)
            log.info("[进入上升趋势]")
        elif current_price < 0.94*g.initPrice:
            g.trend = Trend.Downward
            g.downwardPrice = current_price
            log.info("[进入下降趋势]")
        return
    #if current_price < g.stopPrice:
        #log.info("[####止损####]")
        #SellStock(context, cash)
    if g.trend == Trend.Upward:
        #上升趋势中
        handleUpward(context, current_price, cash)
    elif g.trend == Trend.NaturalRally:
        #自然回撤
        handleNaturalRally(context, current_price, cash)
    elif g.trend == Trend.NaturalReaction:
        #自然回升
        handleNaturalReaction(context, current_price, cash)
    elif g.trend == Trend.SecondaryRally:
        #次级回撤
        handleSecondaryRally(context, current_price, cash)
    elif g.trend == Trend.SecondaryReaction:
        #次级回升
        handleSecondaryReaction(context, current_price, cash)
    elif g.trend == Trend.Downward:
        #下降趋势中
        handleDownward(context, current_price, cash)

    # 画出上一时间点价格
    record(stock_price=current_price)
