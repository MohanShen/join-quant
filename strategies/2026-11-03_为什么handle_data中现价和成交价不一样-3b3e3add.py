# Clone from JoinQuant
# postId: 3b3e3adde9277defbd0863253d413c31
# backtestId: 82a1b5c19bbcabcc91ef3d9e39eaa321
# title: 为什么handle_data中现价和成交价不一样

# 克隆自聚宽文章：https://www.joinquant.com/post/9311
# 标题：网格法自动化下注
# 作者：allen_2

def initialize(context):
    g.security = '512880.XSHG'
    g.max_price = 1.1  #股票最高价格
    g.min_price = 0.8  #股票最低价格
    
    g.buy_downratio = 0.03 #下跌买入幅度3%
    g.sell_upratio = 0.03 #上涨卖出幅度3%
    
    g.price_benchmark = 0.0  #基准价格，随之买卖的变化而变化
    
    g.start_cash_ratio = 0.5  #初始现金比例，通常取50%
    
    g.part_num = 5  #将资金/仓位分成5部分
    
    g.order_num = 0 #每次股票操作数量

    # 设置我们要操作的股票池, 这里我们只操作一支股票
    set_universe([g.security])
    
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    current_price = data[security].price
    
    if(g.order_num == 0):
        g.order_num = ((int((context.portfolio.starting_cash*g.start_cash_ratio)/current_price))/100)*100 #计算每次操作的手数,第一次计算后不再变化
    
    if(g.price_benchmark == 0.0):  
        print(current_price)
        g.price_benchmark = current_price  #刚开始，基准价格取第一天的开盘价，后续随着买卖的变化而变化
        order(security,context.portfolio.starting_cash*(1-g.start_cash_ratio)) #先买入底仓
        log.info("BUY: 买入底仓%r,交易价格%r\n",context.portfolio.long_positions[security].total_amount,context.portfolio.long_positions[security].price)

    #如果下跌3%，则买入
    if(current_price <= g.price_benchmark*(1-g.buy_downratio)):
        order(security,g.order_num)  #买入固定数量(g.order_num)的股票
        g.price_benchmark = current_price   #更新基准价为最新买入价
        
    #如果上涨3%，则卖出
    if(current_price >= g.price_benchmark*(1+g.sell_upratio)):
        order(security,0-g.order_num) #卖出固定数量(g.order_num)的股票
        g.price_benchmark = current_price   #更新基准价为最新买入价
    
    record(price_benchmark=g.price_benchmark)
