# Clone from JoinQuant
# postId: 64e80be97dd10f69a213e3ecee460ee1
# backtestId: c2e9a06243cd59085d5ca71f7c772078
# title: 均线策略改进测试

# 导入函数库
import jqdata
from bee_stock_analysis_system import cache_pool

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    
    g.security = '000001.XSHE'
    g.cash=100000
    g.choice=0
    g.first_run=True

    g.ma_params={'m_short':8,'m_long':16,'analysis_field':'close'}
    g.macd_params={'alpha': 2, 'longperiod': 26, 'shortperiod': 12, 'signalperiod': 9,
                                            'analysis_field': 'close'}
    #初始化实时计算系统，ma最小计算单元1d,执行频率1d
    g.bee_stock_sys=cache_pool(block_unit=30,size=30,real_bar_unit=1,
    isMA=True,MA_Params=g.ma_params,
    isMACD=False,MACD_Params=g.macd_params,isKDJ=False)
    

def handle_data(context, data):
    log.info(str('函数运行时间(handle_data(context, data)):'+str(context.current_dt)))
    if data[g.security] is not None:
        bar_unit=data[g.security]
        if g.first_run:
            g.bee_stock_sys.add_data(bar_unit)
            g.bee_stock_sys.history_ma(attribute_history(g.security, g.ma_params['m_long'], '30m', (g.ma_params['analysis_field']),df=False))
            g.first_run=False
        else:
            g.bee_stock_sys.add_data(bar_unit)
        choice=g.bee_stock_sys.check()
        if choice!=0:
            g.choice=choice
        if g.choice>0:
             # 记录这次买入
            log.info("价格高于均价 1%%, 买入 %s" % (g.security))
            # 用所有 cash 买入股票
            order_value(g.security, g.cash)
    
        elif g.choice<0:
            # 记录这次卖出
            log.info("价格低于均价, 卖出 %s" % (g.security))
            # 卖出所有股票,使这只股票的最终持有量为0
            order_target(g.security, 0)
        
        
