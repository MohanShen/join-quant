# Clone from JoinQuant
# postId: 1816c8c638217776611e7df60f788dda
# backtestId: 1d6d8b73e136d86ac0542f443a1630b2
# title: 关于回测购买基金, 遇到基金分红, 导致回测不准确

# 克隆自聚宽文章：https://www.joinquant.com/post/9946
# 标题：一个简单的FOF组合
# 作者：Gyro

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)

def process_initialize(context):
    # 黄金ETF、易基岁丰、医药A，
    # 由于分级基金即将消失，华宝油气或者美国消费会接替医药A的位置。
    # 两个侧翼各占~15%。
    g.stocklist = ['159934.XSHE', '161115.XSHE', '162415.XSHE']
    set_universe(g.stocklist)

def handle_data(context, data):
    position  = context.portfolio.portfolio_value / len(g.stocklist)
    for etf in g.stocklist:
        log.info("%s %i<--%i", etf, position, context.portfolio.positions[etf].value)
        # 如果目前持仓的某个基金超过整体账户1/3 1000元的话, 那么就再平衡一下
        if abs(position - context.portfolio.positions[etf].value) > 1000:
            order_target_value(etf, position)

def after_code_changed(context):
    for stock in set(context.portfolio.positions):
        order_target(stock, 0);