# Clone from JoinQuant
# postId: b779374336dca85d50a377d2c46e8277
# backtestId: caa7c9de0aeda53e8e9e9a412b38df7f
# title: 如何获取竞价期间，不同时间的匹配价格呢

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    g.stock =  '002862.XSHE'
    g.stock = '601698.XSHG'
    
    run_daily(check_price, "9:20")
    run_daily(check_price, "9:23")
    run_daily(check_price, "9:25")
    run_daily(check_later, "9:30")
    run_daily(check_price, "9:32:30")

def check_later(context):
    date = context.current_dt.strftime("%Y-%m-%d")
    start_time = date + " 9:20:00"
    last_end_time = ""
    for i in range(1, 7):
        minute = 20 + i
        if len(last_end_time) > 0:
            start_time = last_end_time
        end_time = date + " 9:" + str(minute) + ":00"
        last_end_time = end_time
        list_info(context, start_time, end_time)

def list_info(context, start_time, end_time):
    fileds = ['current', 'volume', 'money','b1_p','a1_p','b5_v']
    au = get_call_auction(g.stock, start_date=start_time, end_date=end_time, fields=fileds)
    print(f"calc au data {start_time} {end_time}")
    print(au)

def check_price(context):
    current_data = get_current_data()
    item = current_data[g.stock]
    day_open = item.day_open
    last_price = item.last_price
    print("check_price day_open %f last price %f" % (day_open, last_price))
    
    fileds = ['current', 'volume', 'money','b1_p','a1_p','b5_v']
    date = context.current_dt.strftime("%Y-%m-%d")
    start_time = date + " 9:20:00"
    end_time = context.current_dt.strftime("%Y-%m-%d  %H:%M:%S")
    print(start_time, end_time)
    au = get_call_auction(g.stock, start_date=start_time, end_date=end_time, fields=fileds)
    print(au)

