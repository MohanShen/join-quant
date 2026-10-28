# Clone from JoinQuant
# postId: 0074e69664af0a56455ed171557d2cbf
# backtestId: 40651841bdad89578e618c102f4c6750
# title: 上市公司发布股价波动风险提示性公告的买入策略

# 导入函数库
from jqdata import *
from six import StringIO
from datetime import datetime, timedelta

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 有持仓股票时运行
    run_daily(sell, time='every_bar', reference_security='000300.XSHG')

# 开盘时运行函数
def market_open(context):
    notice = pd.read_csv(StringIO(read_file('notice.csv')))
    notice.drop([notice.columns[0]], axis=1, inplace=True)
    list = notice.index
    # print(notice)
    for i in list:
        start_date = datetime.strptime(notice['date'][i], '%Y-%m-%d')
        end_date = start_date + timedelta(days=8)
        g.date = get_trade_days(start_date, end_date)
        if g.date[1]  == context.current_dt.date(): # date[1]就是公告的第二个工作日买进，不是第二天买进
            buy(context, notice['code'][i])

def sell(context):
    # 持仓时间超过一天或达到9%就卖出
    g.holdstocks = context.portfolio.positions.keys()
    if len(g.holdstocks) != 0:
        for i in g.holdstocks:
            start = context.portfolio.positions[i].init_time.date()
            hold_time = len(get_trade_days(start_date=start, end_date=context.current_dt.date())) # 持仓时间
            current_price = context.portfolio.positions[i].price
            order_price = context.portfolio.positions[i].avg_cost
            # if hold_time >= 1:
            if current_price >= order_price * 1.09 or current_price <= order_price * 0.95:
                order_target_value(i, 0)
            else:
                if hold_time >= 5:
                    order_target_value(i, 0)
                        
def buy(context, stock):
    start_date = get_security_info(stock).start_date # 获取股票上市日期
    current_date = context.current_dt.date()
    start_cash = context.portfolio.starting_cash # 初始资金
    avail_cash = context.portfolio.available_cash # 可用资金
    name = get_security_info(stock).display_name
    
    df = get_price(stock, start_date=g.date[0], end_date=g.date[0], fields=['open', 'close'])
    
    if 'ST' not in name:
        if df['close'][0]/df['open'][0] > 1:
            if (current_date - start_date) > timedelta(days=250): # 过滤掉上市时间小于250天的次新股
                if avail_cash > start_cash/2 :
                    order_value(stock, start_cash/2) # 如果可用资金大于初始资金的五分之一，就买入初始资金的五分之一
                else:
                    order_value(stock, avail_cash) # 否则用可用的剩余资金买入
                print(name)
                print(df)
   
   
   