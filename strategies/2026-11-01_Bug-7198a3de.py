# Clone from JoinQuant
# postId: 7198a3de9f53572f5c093c4cd37064bc
# backtestId: 7d9efad0f04d29702b369b11b7657ea0
# title: Bug？

# 定义一个全局变量, 保存要操作的指数
#userIndex = ['000016.XSHG']

def initialize(context):
    g.stocks = ['601166.XSHG','600000.XSHG']
    
    # 设置查询对象
    g.q = query(
        valuation.code, valuation.pe_ratio,valuation.pb_ratio
    ).filter(valuation.code.in_(g.stocks))
    
    set_universe(g.stocks)
    

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    
    df = get_fundamentals(g.q, context.current_dt)
    
    
    # 画出PE均值的曲线
    #record(PE=df['pe_ratio'])
    # 画出PB均值的曲线
    record(PE_XY=df['pe_ratio'][0])
    #record(PB_XY=df['pb_ratio'][0]/df['pb_ratio'][1])
    record(PE_PF=df['pe_ratio'][1])
    
