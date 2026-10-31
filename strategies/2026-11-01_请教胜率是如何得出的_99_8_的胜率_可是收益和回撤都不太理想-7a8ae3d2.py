# Clone from JoinQuant
# postId: 7a8ae3d2baca80a645395a850f687c11
# backtestId: e90142e7778252fc355012e961054549
# title: 请教胜率是如何得出的？99.8%的胜率，可是收益和回撤都不太理想

'''
仓位控制：根据市场趋势，如果处于上升初期（连续两周），加仓；末期（3个月），减仓；
     如果处于下降初期（连续两周），减仓；末期（3个月），加仓。
     选项二：根据指数均线，如果低于均线，加仓，高于均线，减仓
     公式：delta = 1 - (latest market index / market index ma(n))
           f* (目标仓位) = delta * 2
           fc (仓位变化) = [f* - fp(前一日)] * 20% # 按照20%的速率向目标仓位靠拢
           
'''
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = ['000001.XSHE','000002.XSHE', '000004.XSHE', '002002.XSHE', '002004.XSHE', '600001.XSHG', '600101.XSHG', '600004.XSHG']
    g.ma_length = 120
    g.ref_index = '000300.XSHG'
    #set_benchmark(g.security)
    # 初始化此策略
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    set_universe(g.security)

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    #security = g.security
    # 取得过去n天的平均价格
    average_price = data[g.ref_index].mavg(g.ma_length, 'close')
    # 取得上一时间点价格
    current_price = data[g.ref_index].close
    # 取得当前的现金
    cash = context.portfolio.cash

    # 计算n日均价与上一交易日的差值
    delta = 1 - current_price / average_price
    print 'delta=' + str(delta)
    tgt_pct = 0.5 + delta
    cur_pct = (context.portfolio.total_value - context.portfolio.cash) / context.portfolio.total_value
    if cur_pct == 0 :
        pct_chg = tgt_pct
    else:
        pct_chg = (tgt_pct - cur_pct ) * 0.001
    if cur_pct + pct_chg < 0:
        pct_chg = - cur_pct # 最低仓位为0
    elif cur_pct + pct_chg > 1:
        pct_chg = 1 - cur_pct
    print 'percent change = ' + str(pct_chg)
    print 'new percent = ' + str(cur_pct + pct_chg)
    # 下单调整仓位
    if pct_chg != 0:
        for security in g.security:
            order_value(security, context.portfolio.total_value * pct_chg)
    # 画出上一时间点价格
    record(holding_pct = cur_pct + pct_chg)
