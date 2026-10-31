# Clone from JoinQuant
# postId: 2cf9f10ccd6a5c3442414902a10430da
# backtestId: 8aa6b350d083027a0064aae5c79cfb28
# title: 分钟级别模拟交易, 延时很大

"""
用于测试模拟交易延迟的策略
"""
import time

#获取当时的星期几简称
def get_weekday(context,fmt): #'a' 或 'w'
    # %a 是数字, %w是英文简称 Sun, Mon, ..., Sat
    wk = context.current_dt.strftime("%" + fmt) 
    return wk

#获取日志文件名
def get_filename():
    #格式为: "/test/log_Mon.txt", 其中Mon是对应于每个工作日的星期几简称
    filename = "/test/log_" + g.weekday + ".txt"
    #日志文件保存在聚宽的"投资研究"中
    return filename

#打印日志并写入日志文件    
def p(context,t):
    #"理论:x年x月x日 x点x分x秒, 实际:x年x月x日 x点x分x秒 操作内容"
    s = '理论:' + context.current_dt.strftime("%Y-%m-%d %H:%M:%S") + ", 实际:" + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())  + t + '\n'
    print s
    write_file(g.logfile, s, append)

#初始化日志文件
def init_file(context):
    wk = get_weekday(context, 'a')
    if wk != g.weekday:   #每个工作日产生一个独立的日志, 周而复始
        g.weekday = wk
        g.logfile = get_filename()
        #新建日志文件(若已存在则覆盖),并写入初始头部信息
        write_file(g.logfile, "----" + context.current_dt.strftime("%c") + "-----\n", append=False)
    pass

def initialize(context):
    g.weekday = "" #周几
    init_file(context)  #每个工作日产生一个独立的日志, 周而复始
    p(context,' initialize(context)')

def before_trading_start(context):
    init_file(context)  #每个工作日产生一个独立的日志, 周而复始
    p(context,' before_trading_start(context)')

def after_trading_end(context):
    p(context,' after_trading_end(context)')
    pass

def handle_data(context, data):
    p(context,' handle_data(context, data)')