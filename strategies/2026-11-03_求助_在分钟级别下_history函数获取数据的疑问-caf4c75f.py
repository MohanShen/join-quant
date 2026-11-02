# Clone from JoinQuant
# postId: caf4c75ff80ad4a0376ac07723b1947b
# backtestId: 0fd03c0387cdafec24d3caa5500b86b7
# title: 求助！在分钟级别下，history函数获取数据的疑问

def initialize(context):
    pass

def handle_data(context, data):
    code = '510300.XSHG'
    period = '1m'
    print(f"当前时间 {context.current_dt}")
    print(f"周期: {period}")
    data = history(2, period, field='close', security_list=[code], fq=None)
    print(data)
