# Clone from JoinQuant
# postId: fa95b106e3f634a2bab1748c930bc22a
# backtestId: 6d05829c447ceaaad982e41ba53fb64f
# title: 祖鲁法则：选择成长股策略

# 思路：使用4季度净利润和滚动增长率作为G，计算PEG
import jqdata
import pandas as pd

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    g.stocknum=5
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    run_monthly(reselect,1)

#按照指定的季度获取净利润之和
#statQuater：季度list,格式['2017q1]
def net_profit_quaters(statQuater,stocklist):
    q=query(income.net_profit,
            income.code,
                        ).filter(income.code.in_(stocklist)
                        )
    df=pd.DataFrame()
    for qt in statQuater:
        df_tmp=get_fundamentals(q,statDate=qt)
        df_tmp=df_tmp.set_index('code')
        df_tmp.columns=[qt]
        if len(df)==0:
            df=df_tmp
        else:
            df=pd.merge(df,df_tmp,left_index=True,right_index=True)
    return df.sum(axis=1)

#获取过去8个财报季度
def get_8_quarters(nowDate,stocklist):
    q=query(income.code,indicator.statDate
                    ).filter(income.code.in_(stocklist)
                    )
    df_tmp=get_fundamentals(q,nowDate)
    statDate=df_tmp['statDate'].max()
    year=statDate[:4]
    month=statDate[5:7]
    quarter=int(int(month)/3)
    quarters=[]
    #当年的季度
    for i in range(quarter,0,-1):
        quarters.append(year+'q'+str(i))
    #去年的季度
    for i in range(4,0,-1):
        quarters.append(str(int(year)-1)+'q'+str(i))
    #前年的季度
    for i in range(4,quarter,-1):
        quarters.append(str(int(year)-2)+'q'+str(i))
    return quarters

#查询指定日期的年度利润增长率ttm
def year_inc_net_profit_ttm(nowDate,stocklist):
    #获取过去8个财报季度
    quarters=get_8_quarters(nowDate,stocklist)
    #获取过去4个财报季度的利润和
    last_4_quarter=quarters[:4]
    pre_4_quarter=quarters[4:]
    last_4_net_profit=net_profit_quaters(last_4_quarter,stocklist)
    pre_4_net_profit=net_profit_quaters(pre_4_quarter,stocklist)
    df_result=(last_4_net_profit/pre_4_net_profit-1)*100
    df_result=df_result[df_result<50]
    return df_result

# 剔除周期性行业
def fun_remove_cycle_industry(stock_list):
    cycle_industry = [#'A01', #	农业 	1993-09-17
                      #'A02', # 林业 	1996-12-06
                      #'A03', #	畜牧业 	1997-06-11
                      #'A04', #	渔业 	1993-05-07
                      #'A05', #	农、林、牧、渔服务业 	1997-05-30
                      'B06', # 煤炭开采和洗选业 	1994-01-06
                      'B07', # 石油和天然气开采业 	1996-06-28
                      'B08', # 黑色金属矿采选业 	1997-07-08
                      'B09', # 有色金属矿采选业 	1996-03-20
                      'B11', # 开采辅助活动 	2002-02-05
                      #'C13', #	农副食品加工业 	1993-12-15
                      #C14 	食品制造业 	1994-08-18
                      #C15 	酒、饮料和精制茶制造业 	1992-10-12
                      #C17 	纺织业 	1992-06-16
                      #C18 	纺织服装、服饰业 	1993-12-31
                      #C19 	皮革、毛皮、羽毛及其制品和制鞋业 	1994-04-04
                      #C20 	木材加工及木、竹、藤、棕、草制品业 	2005-05-10
                      #C21 	家具制造业 	1996-04-25
                      #C22 	造纸及纸制品业 	1993-03-12
                      #C23 	印刷和记录媒介复制业 	1994-02-24
                      #C24 	文教、工美、体育和娱乐用品制造业 	2007-01-10
                      'C25', # 石油加工、炼焦及核燃料加工业 	1993-10-25
                      'C26', # 化学原料及化学制品制造业 	1990-12-19
                      #C27 	医药制造业 	1993-06-29
                      'C28', # 化学纤维制造业 	1993-07-28
                      'C29', # 橡胶和塑料制品业 	1992-08-28
                      'C30', # 非金属矿物制品业 	1992-02-28
                      'C31', # 黑色金属冶炼及压延加工业 	1994-01-06
                      'C32', # 有色金属冶炼和压延加工业 	1996-02-15
                      'C33', # 金属制品业 	1993-11-30
                      'C34', # 通用设备制造业 	1992-03-27
                      'C35', # 专用设备制造业 	1992-07-01
                      'C36', # 汽车制造业 	1992-07-24
                      'C37', # 铁路、船舶、航空航天和其它运输设备制造业 	1992-03-31
                      'C38', # 电气机械及器材制造业 	1990-12-19
                      #C39 	计算机、通信和其他电子设备制造业 	1990-12-19
                      #C40 	仪器仪表制造业 	1993-09-17
                      'C41', # 其他制造业 	1992-08-14
                      #C42 	废弃资源综合利用业 	2012-10-26
                      'D44', # 电力、热力生产和供应业 	1993-04-16
                      #D45 	燃气生产和供应业 	2000-12-11
                      #D46 	水的生产和供应业 	1994-02-24
                      'E47', # 房屋建筑业 	1993-04-29
                      'E48', # 土木工程建筑业 	1994-01-28
                      'E50', # 建筑装饰和其他建筑业 	1997-05-22
                      #F51 	批发业 	1992-05-06
                      #F52 	零售业 	1992-09-02
                      'G53', # 铁路运输业 	1998-05-11
                      'G54', # 道路运输业 	1991-01-14
                      'G55', # 水上运输业 	1993-11-19
                      'G56', # 航空运输业 	1997-11-05
                      'G58', # 装卸搬运和运输代理业 	1993-05-05
                      #G59 	仓储业 	1996-06-14
                      #H61 	住宿业 	1993-11-18
                      #H62 	餐饮业 	1997-04-30
                      #I63 	电信、广播电视和卫星传输服务 	1992-12-02
                      #I64 	互联网和相关服务 	1992-05-07
                      #I65 	软件和信息技术服务业 	1992-08-20
                      'J66', # 货币金融服务 	1991-04-03
                      'J67', # 资本市场服务 	1994-01-10
                      'J68', # 保险业 	2007-01-09
                      'J69', # 其他金融业 	2012-10-26
                      'K70', # 房地产业 	1992-01-13
                      #L71 	租赁业 	1997-01-30
                      #L72 	商务服务业 	1996-08-29
                      #M73 	研究和试验发展 	2012-10-26
                      'M74', # 专业技术服务业 	2007-02-15
                      #N77 	生态保护和环境治理业 	2012-10-26
                      #N78 	公共设施管理业 	1992-08-07
                      #P82 	教育 	2012-10-26
                      #Q83 	卫生 	2007-02-05
                      #R85 	新闻和出版业 	1992-12-08
                      #R86 	广播、电视、电影和影视录音制作业 	1994-02-24
                      #R87 	文化艺术业 	2012-10-26
                      #S90 	综合 	1990-12-10
                      ]

    for industry in cycle_industry:
        stocks = get_industry_stocks(industry)
        stock_list = list(set(stock_list).difference(set(stocks)))
        
        return stock_list
#剔除停牌
def unpaused( _stocklist):
    current_data = get_current_data()
    return [s for s in _stocklist if not current_data[s].paused]

def peg(nowDate,stocklist):
    #获取PE
    q_pe=query(valuation.code,valuation.pe_ratio
                    ).filter(valuation.code.in_(stocklist)
                    ).filter(valuation.pe_ratio>0).filter(valuation.pe_ratio<30)
    df_pe=get_fundamentals(q_pe)
    df_pe=df_pe.set_index('code')
    stocklist=list(df_pe.index)
    #现金流条件过滤
    q_cf=query(valuation.code,cash_flow.net_operate_cash_flow,income.net_profit
                    ).filter(valuation.code.in_(stocklist)
                    ).filter(cash_flow.net_operate_cash_flow>income.net_profit)
    df_cf=get_fundamentals(q_cf)
    df_cf=df_cf.set_index('code')
    stocklist=list(df_cf.index)    
    G=year_inc_net_profit_ttm(nowDate,stocklist)
    df_pe=df_pe['pe_ratio']
    s_result=df_pe/G
    s_result=s_result[s_result>0]
    s_result=s_result[s_result<1]
    return s_result
# 剔除上市时间较短的产品
def fun_delNewShare(self, context, equity, deltaday):
    deltaDate = context.current_dt.date() - dt.timedelta(deltaday)

    tmpList = []
    for stock in equity:
        if get_security_info(stock).start_date < deltaDate:
            tmpList.append(stock)

    return tmpList
#相对强度比沪深300大且为正
def xiangduiqiangdu(nowDate,stocklist):
    stocklist=list(stocklist)
    stocklist.append('000300.XSHG')
    df_price=history(250, unit='1d', field='close', security_list=stocklist, df=True, skip_paused=False, fq='pre')
    s_inc=df_price.ix[-1]/df_price.ix[0]
    s_inc=s_inc[s_inc>s_inc['000300.XSHG']]
    s_inc=s_inc[s_inc>1]

    return s_inc.index
def before_trading_start(context):
    pass
    
def handle_data(context, data):
    pass

def reselect(context):
    today = context.current_dt
    stock_list = list(get_all_securities(['stock'], today).index)
    stock_list=fun_remove_cycle_industry(stock_list)
    stock_list=unpaused(stock_list)
    peg_values=peg(today,stock_list)
    peg_values.sort(ascending=True,inplace=True)
    Buylist=list(peg_values.index)
    #Buylist=xiangduiqiangdu(today,peg_values.index)
    Buylist=Buylist[:g.stocknum]
    ## 卖出
    if len(context.portfolio.positions) > 0:
        for stock in context.portfolio.positions.keys():
            if stock not in Buylist:
                order_target(stock, 0)
    if len(context.portfolio.positions) < g.stocknum :
        Num = g.stocknum  - len(context.portfolio.positions)
        Cash = context.portfolio.cash/Num
    else: 
        Cash = context.portfolio.cash
    ## 买入
    if len(Buylist) > 0:
        for stock in Buylist:
           if stock not in context.portfolio.positions.keys():
               order_value(stock,Cash)
    '''
    ## 全卖出
    for stock in context.portfolio.positions.keys():
        order_target(stock, 0)
    buy_count=len(Buylist)
    if buy_count>0:
        Cash = context.portfolio.cash/buy_count
    else: 
        Cash = 0
    
    ## 买入
    if len(Buylist) > 0:
        for stock in Buylist:
           if stock not in context.portfolio.positions.keys():
               order_value(stock,Cash)
    '''