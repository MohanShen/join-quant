# Clone from JoinQuant
# postId: 162c60be54f900d1270cf21de584bc01
# backtestId: 683533e4caa9c6bed74e05fd2116c2de
# title: 求助：场外基金购买错误

# 导入函数库
from jqdata import *
import numpy as np
import pandas as pd
import talib as ta
from six import BytesIO

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
    g.window_list = 800
    #买卖时按照前多少日收益率排序
    g.window = 60
    g.buy_date=(context.current_dt-pd.to_timedelta(str(g.window)+'day')).strftime('%Y-%m-%d')
    #此为计算更新基金列表的时间
    g.t=0
    g.tc=30
    g.wight=np.array([0.25,0.25,0.5])

    g.fund_list=[]
    g.trade=True
    g.n=3
    g.rate=1
    g.fund_outof_market=get_outofmarket_fundlist()

    
def pool_adjust(context):
    change_pool=False
    if g.t%g.tc==0:
        change_pool=True
        log.info('调整基金池',context.current_dt)
    g.t+=1
    
    if change_pool:
        end_date = context.previous_date.strftime('%Y-%m-%d')
        start_date=(context.previous_date-pd.to_timedelta(str(g.window_list)+'day'))
        while start_date.isoweekday()==0 or start_date.isoweekday()==6:
            start_date=(context.previous_date-pd.to_timedelta('2 day'))
        start_date=start_date.strftime('%Y-%m-%d')
        fund_pool=get_fund_pool(g.fund_company,start_date,end_date)
        g.fund_list=get_fund_buy(fund_pool,end_date)
        print('g.fund_list',g.fund_list)
    

def market_open(context):
    g.trade=market_up()
    pool_adjust(context)
    p = context.portfolio.subportfolios[0]
    stock_hold=list(p.long_positions.keys())
    print(stock_hold)
    # 申购基金
    if g.trade and len(stock_hold)<g.n:
        cash = context.portfolio.subportfolios[0].available_cash
        if cash>1000:
            stock_to_buy=g.fund_list[:g.n]
            print(stock_to_buy)
            #判断拟购买股票是否已持有
            stock_to_buy_temp=stock_to_buy.copy()
            for each in stock_to_buy_temp:
                if each in stock_hold:
                    stock_to_buy.remove(each)
            for each in stock_to_buy:
                try:
                    o = purchase(stock_to_buy, cash/len(stock_to_buy))
                    log.info('申购',o)
                    if o!=None:
                        g.buy_date = (context.current_dt).strftime('%Y-%m-%d')
                except Exception as e:   #用Exception表示一下子抓住所有异常，这个一般情况下建议在异常最后面用，用在最后抓未知的异常
                    print(e)

    # 赎回基金
    
    if len(stock_hold)!=0:
        for key in stock_hold:
            x=p.long_positions[key].price
            c=p.long_positions[key].avg_cost
            if x/c>1.1 or x/c<0.9:
                o1 = redeem(key,p.long_positions[key].closeable_amount)
                log.info('赎回',o1)
                g.rate=g.rate*x/c
                log.info('收益率',g.rate)

            
        

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
                                                                    finance.FUND_MAIN_INFO.advisor.in_(fund_company),\
                                                                    finance.FUND_MAIN_INFO.main_code.in_(g.fund_outof_market)))
    fund_pool['start_date']=pd.to_datetime(fund_pool['start_date'])
    fund_pool['end_date']=pd.to_datetime(fund_pool['end_date'])
    fund_pool = fund_pool[fund_pool['start_date']<pd.to_datetime(start_date)+pd.to_timedelta(str(g.window_list)+'day')]
    #fund_pool = fund_pool[fund_pool['end_date']>pd.to_datetime(end_date)] 
    fund_pool = list(fund_pool['main_code'].values)
    fund_pool_a=[]
    for each in fund_pool:
        fund_pool_a.append(each+'.OF')
    fund_pool=fund_pool_a
    fund_pool_temp=fund_pool.copy()
    for each in fund_pool_temp:
        df= get_extras('acc_net_value',[each],end_date=end_date,count=g.window_list+50).dropna()
        if df.empty:
            fund_pool.remove(each)
        elif len(df.index)<g.window_list:
            fund_pool.remove(each)

    if '005960.OF' in fund_pool:
        fund_pool.remove('005960.OF')
    if '005961.OF' in fund_pool:
        fund_pool.remove('005961.OF')
    if '161832.OF' in fund_pool:
        fund_pool.remove('161832.OF') 
    if '161811.OF' in fund_pool:
        fund_pool.remove('161811.OF') 
    if '161122.OF' in fund_pool:
        fund_pool.remove('161122.OF')
    if '161833.OF' in fund_pool:
        fund_pool.remove('161833.OF') 
    if '161121.OF' in fund_pool:
        fund_pool.remove('161121.OF') 
    if '000311.OF' in fund_pool:
        fund_pool.remove('000311.OF') 
    if '000368.OF' in fund_pool:
        fund_pool.remove('000368.OF') 
    print('pool',fund_pool)
    
    return fund_pool
    
def get_return_rate(fund_pool,start_date,end_date):   #返回含‘return_rate’列的dataframe
    net_value=get_extras('acc_net_value',fund_pool,start_date,end_date)
    fund_return_rate=[]
    for each in fund_pool:
        fund_return_rate.append(net_value[each].values[-1]/net_value[each].values[0]-1)
    df = pd.DataFrame(fund_return_rate,columns=['return_rate'],index=fund_pool)
    df.dropna(inplace=True)
    df.sort_values(by = ['return_rate'],ascending=False,inplace=True)
    fund_list=list(df.index.values)
    return fund_list[:5]
    
def market_up(market_index='000300.XSHG',m=5,n=20,y=60,k=3):
    price=attribute_history(market_index,count=y*3).dropna()
    price=price['close'].values
    ma_m=ta.MA(price,m)
    ma_n=ta.MA(price,n)
    ma_y=ta.MA(price,y)
    signal=ma_m[-1]>ma_n[-1] and ma_n[-1]>ma_n[-1-k]
    return signal

def get_sharp(stock,end_date,n=240,rf=0.05):
    df= get_extras('acc_net_value',[stock],end_date=end_date,count=n).dropna()
    stock_return_rate=(1+df.pct_change().dropna()).cumprod()-1
    sharp_rate=(stock_return_rate-rf)/stock_return_rate.std()
    zscore_sharp_rate=(sharp_rate.values[-1]-sharp_rate.mean())/sharp_rate.std()
    return zscore_sharp_rate


def get_treynor(stock,end_date,market_key='000001.XSHG',rf=0.05,n=800):
    start_date=(pd.to_datetime(end_date)-pd.to_timedelta(str(n)+'day')).strftime('%Y-%m-%d')
    df= get_extras('acc_net_value',[stock],end_date=end_date,count=n).dropna()
    df.rename(columns={stock:'acc_net_value' },inplace=True)
    df1 = attribute_history(market_key,count=n)
    df_c=pd.concat([df,df1],axis=1).dropna()
    stock_return_rate =  (1 + df_c['acc_net_value'].pct_change().dropna()).cumprod()
    market_return_rate  = (1 + df_c['close'].pct_change().dropna()).cumprod()
    beta = stock_return_rate.corr(market_return_rate) * stock_return_rate.std() / market_return_rate.std()
    stock_return_rate = stock_return_rate - 1
    treynor = (stock_return_rate - rf) / beta
    zscore_treynor = (treynor.values[-1] - treynor.mean()) / treynor.std()
    return zscore_treynor

def get_max_down(stock,end_date,n=800):
    df = get_extras('acc_net_value',[stock], end_date=end_date,count=n)
    stock_return_rate = (1 + df.pct_change().dropna()).cumprod()[stock]

    max_down_list=[]
    n=len(stock_return_rate)
    for i in range(n):
        down_list = []
        for m in range(i+1):
            down_list.append(stock_return_rate[i]/stock_return_rate[m]-1)
        max_down_list.append(min(down_list))
    max_down=pd.Series(max_down_list)
    zscore_max_down = (max_down_list[-1] - max_down.mean()) / max_down.std()
    return zscore_max_down
    
def get_fund_buy(fund_list,end_date,ascending=False):
    score=[]
    for stock in fund_list:
        data = np.array([get_sharp(stock,end_date), get_treynor(stock,end_date), get_max_down(stock,end_date)])
        score.append(np.dot(data, g.wight))
    df=pd.DataFrame(score,index=fund_list,columns=['score']).sort_values(by=['score'],ascending=ascending)
    return list(df.index.values)
def get_outofmarket_fundlist():
    df=pd.read_csv(BytesIO(read_file('fund_outof_market.csv')))
    fund_outof_market=list(df['基金代码'].dropna().values)
    fund_list_withoutof=[]
    for each in fund_outof_market:
        fund_list_withoutof.append(each[:6])
    return fund_list_withoutof