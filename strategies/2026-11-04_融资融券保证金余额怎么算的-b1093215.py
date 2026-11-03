# Clone from JoinQuant
# postId: b1093215de039457758d9d1181222e0c
# backtestId: a0e03eaa65aa6a6e98bf377f01b3ed45
# title: 融资融券保证金余额怎么算的

# 克隆自聚宽文章：https://www.joinquant.com/post/5844
# 标题：融资融券功能介绍及Demo演示
# 作者：JoinQuant-PM

# 导入聚宽函数库
import jqdata

def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 设置账户类型: 融资融券账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.cash, type='stock_margin')])
    
    ### 融资相关设定 ###
    # 设定融资利率: 年化8%, 默认8%
    set_option('margincash_interest_rate', 0)
    # 设置融资保证金比率: 150%, 默认100%
    set_option('margincash_margin_rate', 1)
    
    ### 融券相关设定 ###
    # 设定融券利率: 年化10%, 默认10%
    set_option('marginsec_interest_rate', 0.10)
    # 设定融券保证金比率: 150%, 默认100%
    set_option('marginsec_margin_rate', 1.5)

    # 判定股票是否可融资融券
    validate(context)
    
    ## 运行函数
    run_daily(trade, time='open')
    run_daily(output_info, time='after_close')

def validate(context):
    # 判定股票是否可融资
    log.info('平安银行可融资：','000001.XSHE' in get_margincash_stocks())
    log.info('中国银行可融资：','601988.XSHG' in get_margincash_stocks())
    log.info('*ST金源不可融资：','000408.XSHE' not in get_margincash_stocks())

    # 判定股票是否可融券
    log.info('平安银行可融券：','000001.XSHE' in get_marginsec_stocks())
    log.info('中国银行可融券：','601988.XSHG' in get_marginsec_stocks())
    log.info('*ST金源不可融券：','000408.XSHE' not in get_marginsec_stocks())

    # 查询融资融券余额
    df = jqdata.get_mtss(['000001.XSHE','601988.XSHG'], end_date=context.current_dt.date(), fields=["date", "sec_code", "fin_value", "sec_value"], count=5)
    log.info('中国银行的融资余额为：', df[df.sec_code == '601988.XSHG']['fin_value'].values[-1])
    log.info('平安银行的融券余额为：', df[df.sec_code == '000001.XSHE']['sec_value'].values[-1])
    log.info('##############################################################')
    
def trade(context):
    # 确定时间是周几
    weekday = context.current_dt.isoweekday()
    log.info("今天是周 %s" % weekday)
    # 融资买入的股票代码（中国银行）
    rz_stock = '601988.XSHG'
    # 融券卖出的股票代码（平安银行）
    rq_stock = '000001.XSHE'

    # 操作判定
    if weekday in (1,):
        # 融资操作
        log.info("融资买入1000股中国银行")
        margincash_open(rz_stock, 1000)

        # 融券操作
        log.info("融券卖出1000股平安银行")
        #marginsec_open(rq_stock, 1000)
        
    elif weekday == 3:
        # 融资操作
        log.info("卖券还款1000股中国银行")
        margincash_close(rz_stock, 1000)

        # 融券操作
        log.info("买券还券1000股平安银行")
        marginsec_close(rq_stock, 1000)
        
    elif weekday == 4:
        # 融资操作
        log.info("直接还钱50000元")
        margincash_direct_refund(50000)

        # 融券操作
        log.info("买入1000股平安银行, 然后直接还券1000股平安银行")
        order(rq_stock, 1000, side='long')
        marginsec_direct_refund(rq_stock, 1000) 

def output_info(context):
    # 查看融资融券账户相关相关信息(更多请见API-对象-SubPortfolio)
    p = context.portfolio.subportfolios[0]
    log.info('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')
    log.info('查看融资融券账户相关相关信息(更多请见API-对象-SubPortfolio)：')
    log.info('总资产：',p.total_value)
    log.info('净资产：',p.net_value)
    log.info('总负债：',p.total_liability)
    log.info('融资负债：',p.cash_liability)
    log.info('融券负债：',p.sec_liability)
    log.info('利息总负债：',p.interest)
    log.info('可用保证金：',p.available_margin)
    log.info('维持担保比例：',p.maintenance_margin_rate)
    log.info('账户所属类型：',p.type)
    log.info('##############################################################')


    
    
    
