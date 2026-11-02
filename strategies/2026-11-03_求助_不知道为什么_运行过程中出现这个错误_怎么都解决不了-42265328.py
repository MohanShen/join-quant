# Clone from JoinQuant
# postId: 42265328d541498c47401c14574c702f
# backtestId: e333e2856e1c794c6aaa345c29ea3893
# title: 求助，不知道为什么，运行过程中出现这个错误，怎么都解决不了

# 导入函数库
from kuanke.wizard import *
from jqdata import *
import numpy as np
import pandas as pd

# 初始化函数，设定基准等等
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option("use_real_price", True)

    ### 场外基金相关设定 ###
    # 设置账户类型: 场外基金账户
    set_subportfolios([SubPortfolioConfig(context.portfolio.cash, 'open_fund')])
    # 设置赎回到账日
    set_redeem_latency(3, 'stock_fund')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
        # 开盘时运行
    run_daily(pool_adjust,time='08:30')
    run_daily(market_open, time='open', reference_security='000300.XSHG')
        # 收盘后运行
    #run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    # 调整股票池函数

    
    g.fund_company=['易方达基金管理有限公司','南方基金管理股份有限公司','博时基金管理有限公司','招商基金管理有限公司','华夏基金管理有限公司',\
              '鹏华基金管理有限公司','工银瑞信基金管理有限公司','汇添富基金管理股份有限公司','广发基金管理有限公司','银华基金管理股份有限公司',\
              '国泰基金管理有限公司','景顺长城基金管理有限公司']
    #按照前多少日的收益率筛选股票池
    g.window_list = 360
    #买卖时按照前多少日收益率排序
    g.window = 33
    g.buy_date=(context.current_dt-pd.to_timedelta(str(g.window)+'day')).strftime('%Y-%m-%d')
    #此为计算更新基金列表的时间
    g.t=0
    g.tc=300

    g.fund_list=[]
    g.fund_to_buy=[]
    g.trade=True

    
def pool_adjust(context):
    change_pool=False
    if g.t%g.tc==0:
        change_pool=True
        log.info('调整基金池',context.current_dt)
    g.t+=1
    
    if change_pool:
        end_date = context.current_dt.strftime('%Y-%m-%d')
        start_date=(context.current_dt-pd.to_timedelta(str(g.window_list)+'day'))
        while start_date.isoweekday()==0 or start_date.isoweekday()==6:
            start_date=(context.current_dt-pd.to_timedelta('2 day'))
        start_date=start_date.strftime('%Y-%m-%d')
        fund_pool=get_fund_pool(g.fund_company,start_date,end_date)
        g.fund_list=get_return_rate(fund_pool,start_date,end_date)
def market_open(context):
    end_date = context.current_dt.strftime('%Y-%m-%d')
    start_date = g.buy_date
    p = context.portfolio.subportfolios[0]
    # 申购基金
    if g.trade:
        fund_to_buy=get_return_rate(g.fund_list,start_date,end_date)[-1]
        cash = context.portfolio.subportfolios[0].available_cash
        if cash>1000:
            o = purchase(fund_to_buy, cash)
            print('申购',o)
            if o!=None:
                g.buy_date = (context.current_dt).strftime('%Y-%m-%d')
                g.trade=False
    # 赎回基金
    
    elif len(list(p.long_positions.keys()))!=0:
        key=list(p.long_positions.keys())[0]
        x=p.long_positions[key].price
        c=p.long_positions[key].avg_cost
        if (x/c)>1.05 or (x/c<0.9):
            o1 = redeem(key,p.long_positions[key].closeable_amount)
            log.info('赎回',o1)
            g.trade=True

## 收盘后运行函数
def after_market_close(context):
    # 查看融资融券账户相关相关信息(更多请见API-对象-SubPortfolio)
    p = context.portfolio.subportfolios[0]
    log.info('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -')
    log.info('查看场外基金账户相关相关信息(更多请见API-对象-SubPortfolio)：')
    #log.info('场外基金持有份额：',p.long_positions['000311.OF'].closeable_amount)
    log.info('账户所属类型：',p.type)
    log.info('##############################################################')
#过滤基金公司和股票型基金
def get_fund_pool(fund_company,start_date,end_date):
    fund_pool=finance.run_query(query(finance.FUND_MAIN_INFO).filter(finance.FUND_MAIN_INFO.operate_mode_id=='401001',\
                                                                    finance.FUND_MAIN_INFO.underlying_asset_type_id=='402001',\
                                                                    finance.FUND_MAIN_INFO.advisor.in_(fund_company)))
    fund_pool['start_date']=pd.to_datetime(fund_pool['start_date'])
    fund_pool['end_date']=pd.to_datetime(fund_pool['end_date'])
    fund_pool = fund_pool[fund_pool['start_date']<pd.to_datetime(start_date)]
    #fund_pool = fund_pool[fund_pool['end_date']>pd.to_datetime(end_date)] 
    fund_pool = list(fund_pool['main_code'].values)
    fund_pool_a=[]
    for each in fund_pool:
        fund_pool_a.append(each+'.OF')
    return fund_pool_a
    
def get_return_rate(fund_pool,start_date,end_date):   #返回含‘return_rate’列的dataframe
    net_value=get_extras('adj_net_value',fund_pool,start_date,end_date)
    fund_return_rate=[]
    for each in fund_pool:
        fund_return_rate.append(net_value[each].values[-1]/net_value[each].values[0]-1)
    df = pd.DataFrame(fund_return_rate,columns=['return_rate'],index=fund_pool)
    df.dropna(inplace=True)
    df.sort_values(by = ['return_rate'],ascending=False,inplace=True)
    fund_list=list(df.index.values[:5])
    return fund_list

