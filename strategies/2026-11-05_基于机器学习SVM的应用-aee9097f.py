# Clone from JoinQuant
# postId: aee9097fabe9006d7581d3548d09dddb
# backtestId: b464d52ae02931847ae53e264c09925c
# title: 基于机器学习SVM的应用

# 导入函数库
import jqdata
import numpy as np
import pandas as pd
from numpy import nan
from sklearn.svm import SVC
from sklearn.decomposition import PCA 

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000001.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    stock=get_index_stocks('000300.XSHG')[0:50]
    g.security=stock
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_monthly(before_market_open, time='before_open',monthday=1, reference_security='000001.XSHG') 
      # 开盘时运行
    run_monthly(market_open, time='open',monthday=1, reference_security='000001.XSHG')
      # 收盘后运行
    run_monthly(after_market_close, time='after_close', monthday=1,reference_security='000001.XSHG')
    
## 开盘前运行函数     
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 要操作的股票：平安银行（g.为全局变量）
    buy=0
    sell=0
    stock=g.security
    date=pd.date_range(end=str(context.current_dt),periods=60)
    output=svm_train(stock,date)
    output=output.T
    t=output[output['正确率']>70]['预测值']
    buy=t[t==-1].index
    sell=t[t==1].index
    current_security = list(context.portfolio.positions.keys())
    g.buy = list(set(buy)-set(current_security))
    # 得到卖出股票列表
    g.sell = list(set(sell))
    
    
    
## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    cash = context.portfolio.available_cash
    try:
        cash = context.portfolio.available_cash/len(g.buy)
    except:
        cash = 0
        
    # 买入股票
    for stock in g.buy:
        order_value(stock, cash)
        log.info("买入 %s" % (stock))
    for stock in g.sell:
        order_target(stock, 0)
        log.info("卖出 %s" % (stock))
 
## 收盘后运行函数  
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
def mulfactor(stock,date):
    df = get_fundamentals(query(
            valuation.code,
            valuation.market_cap,
            balance.total_liability,
            valuation.pe_ratio,
            valuation.circulating_market_cap,
            balance.total_assets,
            indicator.roe,
            indicator.roa,
            indicator.net_profit_margin,
            valuation.pb_ratio,
            valuation.ps_ratio,
            valuation.pcf_ratio,
            valuation.turnover_ratio,
            indicator.eps,
            income.total_operating_revenue,
            indicator.ocf_to_revenue,
        ).filter(
            valuation.code.in_([stock])
        ),date=date)
    value=pd.DataFrame()
    market_cap=df['market_cap']*100000000
    value['PE']=df['pe_ratio'] #
    value['PB']=df['pb_ratio']
    value['PS']=df['ps_ratio']
    value['PCF']=df['pcf_ratio']
    value['总市值']=market_cap 
    value['流通市值']=df['circulating_market_cap'] 
    value['流通市值/总市值']=df['circulating_market_cap']/market_cap 
    value['总资产']=df['total_assets'] 
    value['ROE']=df['roe'] 
    value['ROA']=df['roa'] 
    value['销售净利率']=df['net_profit_margin'] 
    value['资产负债比']=df['total_assets']/df['total_liability'] 
    value['换手率']=df['turnover_ratio']
    value['每股收益eps']=df['eps']
    value['营业总收入']=df['total_operating_revenue']
    value['经营活动产生的现金流量净额/营业收入']=df['ocf_to_revenue']
    volume = get_price(stock, count=1,end_date=date, frequency='daily', fields=['volume'])['volume'].T
    volume.columns=['volume']
    money = get_price(stock,count=1, end_date=date, frequency='daily', fields=['money'])['money'].T
    money.columns=['money']
    close = get_price(stock,count=1, end_date=date, frequency='daily', fields=['close'])['close'].T
    close.columns=['close']
    value['vloume']=list(volume)
    value['money']=list(money)
    value['close']=list(close)
    return value
def svm_train(stock,date):
    matrix = [[0]*len(stock) for i in range(2)]
    output=pd.DataFrame(matrix)
    for j in range(len(stock)):
        x_train=pd.DataFrame()
        y_train=pd.DataFrame()
        for i in range(len(date)-1):
            value=mulfactor(stock[j],date[i])
            x_train[i]=np.array(value.T.iloc[:,0])
            y_train[i]=pd.Series(get_price(stock[j],count=2, end_date=date[i+1], frequency='daily', fields=['close'])['close'].pct_change()[-1])
        x_train.index=value.columns
        x_train.columns=date[0:-1]
        y_train.index=['ret']
        y_train.columns=date[0:-1]
        x_train=x_train.T
        y_train=y_train.T
        y_train[y_train>0]=1
        y_train[y_train<0]=-1
        y_train=y_train.fillna(0)
        for i in x_train.columns:
            temp=np.median(x_train[i].dropna())
            MAD=np.median(np.abs(x_train[i]-temp).dropna())
            extreme_big=temp+3*1.4826*MAD
            extreme_small=temp-3*1.4826*MAD
            x_train[i][x_train[i]>extreme_big]=extreme_big
            x_train[i][x_train[i]<extreme_small]=extreme_small
            x_train[i]=x_train[i].fillna(temp)
            x_train[i]=(x_train[i]-np.mean(x_train[i]))/np.std(x_train[i])
            x_train[i]=x_train[i].fillna(MAD)
        x=np.array(x_train)
        pca = PCA(n_components=3)
        pca.fit(x) 
        print(pca.explained_variance_ratio_)
        x=pca.transform(x)
        y=np.array(y_train.iloc[:,0])
        p=pca.transform(np.array(mulfactor(stock[j],date[-1])))
        if y[0]==0:
            output[0,j]=0
        else:
            clf = SVC()
            clf.fit(x[0:(len(x)-len(x)/8)], y[0:(len(x)-len(x)/8)])
            output.iloc[0,j]=(sum(clf.predict(x[-len(x)/8:])==y[-len(x)/8:])*100)/(len(x)/8+1)
            pre=clf.predict(p)
            output.iloc[1,j]=pre
    output=output.iloc[:,0:len(stock)]
    output.columns=stock
    output.index=['正确率','预测值']
    return output