# Clone from JoinQuant
# postId: f2aa5cd95410c3fbb303972848a1b214
# backtestId: 83730ef704a49f9d01917c7bda48dc84
# title: 我只说一句，为什么按照官方教程的都做不对

def initialize(context):
    run_daily(period,time='every_bar')
    g.security = '000001.XSHE'

def period(context):
    order(g.security, 100)