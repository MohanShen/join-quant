# Clone from JoinQuant
# postId: 2e055009e3630964faa3c23bb40748cd
# backtestId: fde49a8279596acdda1757da5e5b55af
# title: 查询指定指数的PE和PB的中位数历史数据的程序

# 该程序实现查询指定指数的PE和PB的中位数
# 雪球ID：江州金猪
# 2016-6-2

def initialize(context):
    g.zs='000300.XSHG'
    # 对比标的
    set_benchmark(g.zs) 

def unpaused(stockspool):
    current_data=get_current_data()
    return [s for s in stockspool if not current_data[s].paused]

def handle_data(context, data):
    stocks=get_index_stocks(g.zs)
    stocks=unpaused(stocks) #剔除停牌股
    p1 = get_fundamentals(query(
        valuation.pe_ratio
    ).order_by(
        # 按PE升序排列
        valuation.pe_ratio.asc()
    ).filter(
        valuation.code.in_(stocks),
        valuation.pe_ratio>0,
    ))
    ls=int(len(p1)/2)  
    pe=p1['pe_ratio'].values[ls]
    record(pe = pe)
    
    p2 = get_fundamentals(query(
        valuation.pb_ratio
    ).order_by(
        # 按PB升序排列
        valuation.pb_ratio.asc()
    ).filter(
        valuation.code.in_(stocks),
        valuation.pb_ratio>0,
    ))
    
    ls=int(len(p2)/2)  
    pb=p2['pb_ratio'].values[ls]
    record(pb = pb*20) #为了在一张图上同时显示PE和PB，而把PB按比例放大20倍 
    log.info("PE: ",pe,"  PB:",pb)