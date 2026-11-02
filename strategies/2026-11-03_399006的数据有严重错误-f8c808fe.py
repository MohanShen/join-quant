# Clone from JoinQuant
# postId: f8c808fee3060bef2277d36de385b041
# backtestId: 45dce21b9daab48af863ed1659fe8a07
# title: 399006的数据有严重错误

def initialize(context):
    g.benchmark = '399006.XSHE'

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    pass


