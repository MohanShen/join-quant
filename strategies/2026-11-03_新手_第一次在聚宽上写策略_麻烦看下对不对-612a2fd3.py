# Clone from JoinQuant
# postId: 612a2fd3e4084f13d8418c095e3db214
# backtestId: 2e3af20f71e2f2aced37c129313f816b
# title: 新手，第一次在聚宽上写策略，麻烦看下对不对？

# 导入聚宽函数库
import jqdata

def initialize(context):
    # 初始化此策略
    # 设置我们要操作的股票池
    g.stocks = ['510300.XSHG','513100.XSHG']
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 资金数量
    g.money = [0.0, 0.0]

g.days = 0
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    #每10天交易一次
    g.days += 1
    if g.days >= 10:
        g.days = 0
        return None
    # 循环每只股票
    i = 0
    for security in g.stocks:
        # 得到股票之前3天的平均价
        vwap = data[security].vwap(3)
        # 得到上一时间点股票收盘价
        price = data[security].close
        # 得到当前资金余额
        cash = context.portfolio.available_cash/2.0 + g.money[i]
        # 得到可以买的股票数量
        num = int(cash/price/100)*100
        if num >= 100:
            order(security, num)
            money = num*price
            g.money[i] = cash - money
        i += 1
        log.info("Buying %s %d" % (security, num))
        

        # 如果上一时间点价格小于三天平均价*0.995，并且持有该股票，卖出
        #if price < vwap * 0.995 and context.portfolio.positions[security].closeable_amount > 0:
            # 下入卖出单
        #    order(security,-100)
            # 记录这次卖出
        #    log.info("Selling %s" % (security))
        # 如果上一时间点价格大于三天平均价*1.005，并且有现金余额，买入
        #elif price > vwap * 1.005 and cash > 0:
            # 下入买入单
        #    order(security,100)
            # 记录这次买入
        #    log.info("Buying %s" % (security))