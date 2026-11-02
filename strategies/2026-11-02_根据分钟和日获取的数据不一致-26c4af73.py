# Clone from JoinQuant
# postId: 26c4af73b28de500a9e2e3e7c46e4e14
# backtestId: ad7bfac389372e45e8e6b99ca6d21327
# title: 根据分钟和日获取的数据不一致

# 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = '000001.XSHE'
    #设定沪深300作为基准
    set_benchmark('000300.XSHG')
    run_daily(test, '9:30')

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    pass
def test(context):
    security = g.security
    h_data_min = attribute_history(security, 240, unit='1m'
                    , fields=('open', 'close', 'high', 'low', 'volume')
                    , skip_paused=True)
    h_data_day = attribute_history(security, 1, unit='1d'
                        , fields=('open', 'close', 'high', 'low', 'volume')
                        , skip_paused=True)
    k = {}
    k['open'] = h_data_min['open'].iloc[0]
    k['close'] = h_data_min['close'].iloc[-1]
    k['high'] = h_data_min['high'].max()
    k['low'] = h_data_min['low'].min()
    print(k)
    print(h_data_day)
    print(h_data_min)
    print(h_data_day.iloc[0]['open'] == k['open'],
        h_data_day.iloc[0]['close'] == k['close'],
        h_data_day.iloc[0]['high'] == k['high'],
        h_data_day.iloc[0]['low'] == k['low'])
    
    
    
    
    
    