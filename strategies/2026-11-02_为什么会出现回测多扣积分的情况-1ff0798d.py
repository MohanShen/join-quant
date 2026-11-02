# Clone from JoinQuant
# postId: 1ff0798d62c6babfa053dc218ec3dc83
# backtestId: 697a2769f6de6fd85fdfd3a4f6d105ba
# title: 为什么会出现回测多扣积分的情况

# 克隆自聚宽文章：https://www.joinquant.com/post/28263
# 标题：xgboost利用高频因子择时选股+lstm选股
# 作者：拟合即亏损

# 克隆自聚宽文章：https://www.joinquant.com/post/27835
# 标题：基于lstm的择时策略
# 作者：healerlq

# 导入函数库
from jqlib.technical_analysis import *
from jqdata import *
import pandas as pd
import numpy as np
import datetime

#from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split
import tensorflow as tf

import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler

from keras.models import Sequential
from keras.layers import LSTM,Dense,Dropout
from numpy import concatenate
from sklearn.metrics import mean_squared_error,mean_absolute_error,r2_score

from keras import backend as K
from keras import optimizers
from keras.layers.core import Dense, Activation, Dropout

import xgboost as xgb
import pandas as pd

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    #set_benchmark('000300.XSHG')
    set_benchmark('000300.XSHG')
    #设置标的股票
    g.days=0
    g.security = '000300.XSHG'
    g.lookback=10
    start_date = datetime.datetime(2010,1,1)
    end_date = datetime.datetime(2019,1,1)
    stocks = g.security
    df= get_data_from_date(start_date,end_date,stocks)
    result = minmax(df,0.8,g.lookback)
    scaler = result['scaler']
    x_train,x_test,y_train,y_test = result['x_train'],result['x_test'],result['y_train'],result['y_test'] 
    model = lstm_model(x_train,y_train,x_test,y_test)
    g.model = model
    g.scaler = scaler
    #选择xgboost模型训练所用数据时段，生成xgboost模型
    g.bst = xgboost_model(start_date='2017-05-01', end_date='2019-05-01')
    #根据回测时段选择生成的预选股数据,生成因子列表
    g.ind_factor = backtest_data_gen(start_date='2019-03-01', end_date='2020-05-20') 
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')


    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘时运行
    run_daily(market_open, time='close', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')


## 开盘时运行函数
def market_open(context):
    g.days+=1
    #获取xgboost选择的股票
    stock_dataframe = xgboost_target_stock_list_gen(context.previous_date,g.ind_factor, g.bst)
    security = g.security
    # 获取股票近10天的相关数据
    stock_list=stock_dataframe.iloc[:10].reset_index().code.tolist()
    status_today = stock_dataframe.mean()[0]
    log.info('今日积极指数为：',status_today)
    df_new = get_price(security,end_date=context.current_dt,count=10)
    df_new= df_new[['close','open', 'high', 'low', 'volume', 'money']]
    # 取得预测得到的收盘价数据
    model = g.model
    scaler = g.scaler
    #start_date = datetime.datetime(2009,1,1)
    #end_date = datetime.datetime(2015,1,5)
    #pred_close = lstm(start_date,end_date,10,df_new)
    pred_close = lstm(scaler,model,df_new)
    #获取最新的收盘价数据
    close_new = df_new['close'][-1]
    
    
    # 取得当前的现金
    cash = context.portfolio.available_cash
    capital = context.portfolio.portfolio_value
    # 如果预测出的收盘价高于今天的收盘价, 则全仓买入
    if (close_new > pred_close) and (cash > 0):
        # 记录这次买入
        log.info("价格高于均价 1%%, 买入 %s" % (security))
        # 用所有 cash 买入股票
        # order_value(security, cash)
        if status_today>-0.05 and g.days%2==0:
            for stock in context.portfolio.positions:
                if stock  not in stock_list  :
                    order_target(stock, 0) #调整stock的持仓为0，即卖出
            for stock in stock_list:
                order_target_value(stock, capital/10)
        # if status_today<0.02 and status_today>-0.02:
        #     for stock in context.portfolio.positions:
        #         if stock  not in stock_list  :
        #             order_target(stock, 0) #调整stock的持仓为0，即卖出
        #     for stock in stock_list[:5]:
        #         order_target_value(stock, capital/10)
        if status_today<-0.05:
            for stock in context.portfolio.positions:
                order_target(stock, 0)
            
    # 如果上一时间点价格低于五天平均价, 则空仓卖出
    elif close_new < pred_close and context.portfolio.positions[security].closeable_amount > 0:
        # 记录这次卖出
        for stock in context.portfolio.positions:
            order_target(stock, 0)
        log.info("价格低于均价, 卖出 %s" % (security))
        # 卖出所有股票,使这只股票的最终持有量为0

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')

##lstm
def lstm(scaler,model,df_new):
    stocks = g.security
    #df= get_data_from_date(start_date,end_date,stocks)
    #result = minmax(df,0.8,lookback)
    #scaler = result['scaler']
    #x_train,x_test,y_train,y_test = result['x_train'],result['x_test'],result['y_train'],result['y_test'] 
    #model = lstm_model(x_train,y_train,x_test,y_test)
    new_data = scaler.transform(df_new)
    new_data = new_data[: g.lookback, 1:]
    new_data = np.reshape(new_data,[1,new_data.shape[0],new_data.shape[1]])
    y_pred = pred(model,new_data,scaler)
    return y_pred
    
#==================lstm会用到的函数=======================
def get_factors_one_stock(stocks,date):
    
    '''
    获取一只股票一天的因子数据集
    input:
    stocks:一只股票
    date:日期
    output:
    df:dataframe,各个因子一天的数值
    '''
    
    
    if type(date) != str:
        date = datetime.datetime.strftime(date,'%Y-%m-%d')
    
    price = get_price(stocks,end_date=date,count=1)
    price.index = [date]
    price = price[['close','open', 'high', 'low', 'volume', 'money']]
    return price

def get_data_from_date(start_date,end_date,stocks):
    '''
    获取时间轴数据
    '''
    trade_date = get_trade_days(start_date=start_date,end_date=end_date)
    df = get_factors_one_stock(stocks,trade_date[0])
    for date in trade_date[1:]:
        df1 = get_factors_one_stock(stocks,date)
        df = pd.concat([df,df1])
    return df

def minmax(df,train_rate,lookback):
    
    num=int(df.shape[0] * train_rate)
    data_train,data_test=df.iloc[:num,:],df.iloc[num:,:]
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaler.fit(data_train)
    data_train = scaler.transform(data_train)
    data_test = scaler.transform(data_test)
    x_train = np.array([data_train[i : i + lookback, 1:] for i in range(data_train.shape[0] - lookback)])
    y_train = np.array([data_train[i + lookback,0] for i in range(data_train.shape[0]- lookback)])
    x_test = np.array([data_test[i : i + lookback, 1:] for i in range(data_test.shape[0]- lookback)])
    y_test = np.array([data_test[i + lookback,0] for i in range(data_test.shape[0] - lookback)])
    
    np.random.seed(1)
    np.random.shuffle(x_train)
    np.random.seed(1)
    np.random.shuffle(y_train)
    
    len_train = len(x_train)
    len_test = len(x_test)
    n_input = len(df.columns)-1
    x_train = np.reshape(x_train,[len_train,lookback,n_input])
    y_train = np.reshape(y_train,[len_train,1])
    
    x_test = np.reshape(x_test,[len_test,lookback,n_input])
    y_test = np.reshape(y_test,[len_test,1])
    
    result={'scaler':scaler,'x_train':x_train,'y_train':y_train,'x_test':x_test,'y_test':y_test}
    return result

def lstm_model(x_train,y_train,x_test,y_test):
    model = Sequential()
    model.add(LSTM(64, input_shape=(x_train.shape[1], x_train.shape[2])))
    model.add(Dropout(0.2))
    model.add(Dense(1))
    model.add(Activation('linear'))
    model.compile(loss='mse', optimizer='adam')
    history = model.fit(x_train, y_train, epochs=50, batch_size=100, validation_data=(x_test, y_test), verbose=2,shuffle=False)

    return model


def pred(model,new_data,scaler):
    y_pred = model.predict(new_data)
    inv_y_test = concatenate((y_pred,new_data[:,-1]), axis=1)
    inv_y = scaler.inverse_transform(inv_y_test)

    return inv_y[0][0]
    
    
    
def apply_func(data,func):
    return data.groupby(level=1, sort=False).apply(func)
def time_rank(data):
    return pd.Series(data).rank().iloc[-1]
def ALPHA006(data):
    def alpha006(data):
        r =data.reset_index().rolling(10)
        return pd.DataFrame(np.array(r[['open','volume']].corr().loc[(slice(None),'open'),'volume']),index=data.index)
    return -data.groupby(level=1, sort=False).apply(alpha006)
def ALPHA003(data):
    #demand rank,but use 'ALPHA(data)',rather than 'apply_func(data_rank,ALPHA013)'
    def alpha003(data):
        r =data.reset_index().rolling(10)
        alpha003 = pd.DataFrame(np.array(r[['open_rank','volume_rank']].corr().loc[(slice(None),'open_rank'),'volume_rank']),index=data.index)
        return alpha003
    return -data.groupby(level=1, sort=False).apply(alpha003)
def ALPHA004(data):
    #demand rank
    r = pd.DataFrame(data_single['low_rank'].rolling(5).apply(time_rank))
    return r
def ALPHA013(data):
    #demand rank,but use 'ALPHA(data)',rather than 'apply_func(data_rank,ALPHA013)'
    def alpha013(data):
        r =data.reset_index().rolling(5)
        alpha013 = pd.DataFrame(np.array(r[['close_rank','volume_rank']].cov().loc[(slice(None),'close_rank'),'volume_rank']),index=data.index)
        return alpha013
    return -apply_func(data,alpha013).groupby(level=1, sort=False).rank()
def ALPHA014(data):
     #demand rank,but use 'ALPHA(data)',rather than 'apply_func(data_rank,ALPHA013)'
    def alpha014(data):
        r = data['open'].diff(1)/data['open']
        t = pd.DataFrame(r.rolling(3).apply(lambda x:x[2]-x[0]))
        return t
    t1 = apply_func(data,alpha014).groupby(level=1, sort=False).rank()
    r2 = data.reset_index().rolling(10)
    t2 = pd.DataFrame(np.array(r2[['open','volume']].corr().loc[(slice(None),'open'),'volume']),index=data.index)
    return -pd.DataFrame(pd.concat([t1,t2],axis=1).apply(lambda x :x['open']*x[0],axis=1))
def ALPHA015(data):
     #demand rank,but use 'ALPHA(data)',rather than 'apply_func(data_rank,ALPHA013)'

    def alpha015(data):
        r =data.reset_index().rolling(3)
        alpha015 = pd.DataFrame(np.array(r[['high_rank','volume_rank']].corr().loc[(slice(None),'high_rank'),'volume_rank']),index=data.index)
        return alpha015
    return -apply_func(data,alpha015).groupby(level=1, sort=False).rank().rolling(3).sum()
def ALPHA016(data):
    #demand rank,but use 'ALPHA(data)',rather than 'apply_func(data_rank,ALPHA013)'
    def alpha016(data):
        r =data.reset_index().rolling(5)
        alpha013 = pd.DataFrame(np.array(r[['high_rank','volume_rank']].cov().loc[(slice(None),'high_rank'),'volume_rank']),index=data.index)
        return alpha013
    return -apply_func(data,alpha016).groupby(level=1, sort=False).rank()
def ALPHA027(data):
    #未完成
    def alpha027(data):
        r =data.reset_index().rolling(6)
        alpha015 = pd.DataFrame(np.array(r[['vwap_rank','volume_rank']].corr().loc[(slice(None),'vwap_rank'),'volume_rank']),index=data.index).rolling(2).sum()
        return alpha015
    t1 = apply_func(data,alpha027).groupby(level=1, sort=False).rank()
    return t1
def ALPHA028(data):
    #未完成
    def alpha028(data):
        t=pd.DataFrame(data['volume'].rolling(20).mean())
        t.columns=['adv20']

        r=pd.concat([data,t],axis=1)
#         r=r.dropna()
        data_single1 = r
        r =data_single1.reset_index().rolling(5)
        return pd.DataFrame(pd.Series(np.array(r[['adv20','low']].corr().loc[(slice(None),'low'),'adv20']),index=data.index)+(data_single1['high']+data_single1['low'])/2-data_single1['close'])
    def alpha028_1(data1):
        return data1/sum(abs(data1))
#     .groupby(level=0, sort=False).apply(alpha028_1)
    return -apply_func(data,alpha028)
def ALPHA040(data):
    def alpha040_1(data):
        
        return pd.DataFrame(data['high'].rolling(10).std())
    def alpha040_2(data):
        r =data.reset_index().rolling(10)
        alpha040 = pd.DataFrame(np.array(r[['high','volume']].corr().loc[(slice(None),'volume'),'high']),index=data.index)
        return alpha040 
    t1 = apply_func(data,alpha040_1).groupby(level=1, sort=False).rank()
    t2 = apply_func(data,alpha040_2)
    t3 = -pd.DataFrame(pd.concat([t1,t2],axis=1).apply(lambda x:x[0]*x['high'],axis=1))
#     t3 = -pd.DataFrame(t1*t2)
    return t3
def ALPHA042(data):
    t1 = (data['vwap']-data['close']).groupby(level=1, sort=False).rank()
    t2 = (data['vwap']+data['close']).groupby(level=1, sort=False).rank()
    t3 = pd.DataFrame(t1/t2)
    return t3
def ALPHA044(data):
    def alpha044(data):
        r =data.reset_index().rolling(5)
        return pd.DataFrame(np.array(r[['high','volume_rank']].corr().loc[(slice(None),'high'),'volume_rank']),index=data.index)
    return -data.groupby(level=1, sort=False).apply(alpha044)
def ALPHA_MA5(data):
    def alphaMA(data):
        
        return pd.DataFrame(data['close'].rolling(5).mean()/data['close'])
    return apply_func(data,alphaMA)
    
    
def shift_data(data,n):
    def shiftshift(data):
        return data.shift(n)
    return apply_func(data,shiftshift)
def xgboost_model(start_date='2017-05-01', end_date='2019-05-01'):
    ind_factor_lag12 = backtest_data_gen(start_date=start_date, end_date=end_date)
    stock_list = get_index_stocks('000300.XSHG', date=None)
    data_pre = get_price(stock_list, start_date=start_date, end_date=end_date, frequency='daily', fields=None, skip_paused=False, fq='pre', count=None,panel=False)
    data = data_pre.set_index(['time','code']).sort_index().rename(columns = {'money':'amount'})
    def pct_change(data):
        def PCt(data):
            return pd.DataFrame(data['close'].diff(1)/data['close'])
        return data.groupby(level=1, sort=False).apply(PCt)
    data_pct_change = pct_change(data)
    ind_res = pd.concat([ind_factor_lag12,data_pct_change.groupby(level=1,sort=False).shift(-1)],axis=1)
    ind_res = ind_res.dropna()
    ind_res.columns=['ALPHA006',
                 'ALPHA003',
                 'ALPHA013',
                 'ALPHA014',
                 'ALPHA015',
                 'ALPHA016',
                 'ALPHA027',
                 'ALPHA028',
                 'ALPHA040',
                 'ALPHA042',
                 'ALPHA044',
                 'ALPHA_MA5',
                 'ALPHA006lag',
                 'ALPHA003lag',
                 'ALPHA013lag',
                 'ALPHA014lag',
                 'ALPHA015lag',
                 'ALPHA016lag',
                 'ALPHA027lag',
                 'ALPHA028lag',
                 'ALPHA040lag',
                 'ALPHA042lag',
                 'ALPHA044lag',
                 'ALPHA_MA5lag',
                 'ALPHA006lag2',
                 'ALPHA003lag2',
                 'ALPHA013lag2',
                 'ALPHA014lag2',
                 'ALPHA015lag2',
                 'ALPHA016lag2',
                 'ALPHA027lag2',
                 'ALPHA028lag2',
                 'ALPHA040lag2',
                 'ALPHA042lag2',
                 'ALPHA044lag2',
                 'ALPHA_MA5lag2',
                 'ALPHA006lag3',
                 'ALPHA003lag3',
                 'ALPHA013lag3',
                 'ALPHA014lag3',
                 'ALPHA015lag3',
                 'ALPHA016lag3',
                 'ALPHA027lag3',
                 'ALPHA028lag3',
                 'ALPHA040lag3',
                 'ALPHA042lag3',
                 'ALPHA044lag3',
                 'ALPHA_MA5lag3',
                 'pct_change']
    ind_res['pct']=ind_res['pct_change'].apply(lambda x :1 if x>0 else 0)
    log.info('训练集已构建')
    x_train = np.array(ind_res.iloc[:,:-2])
    y_train = np.array(ind_res.iloc[:,-1])
    dtrain = xgb.DMatrix(x_train,label=y_train)
    params = {
        'gamma':0.1,    # 用于控制是否后剪枝的参数，越大越保守，一般0.1 0.2的样子
        'lambda':2,  # 控制模型复杂度的权重值的L2 正则化项参数，参数越大，模型越不容易过拟合
        'subsample':0.95, 
        'max_depth':4,
        'objective':'multi:softprob',
        'num_class':2,
    #     随机采样训练样本
    #     对于正负样本不均衡时的0-1分类而言，假设h在0.01附近，min_child_weight为1
    #     意味着叶子节点中最少需要包含100个样本。这个参数非常影响结果，
    #     控制叶子节点中二阶导的和的最小值，该参数值越小，越容易过拟合
        'eval_metric':'auc'
    }
    num_round=20
    bst = xgb.train(params, dtrain, num_round)
    log.info('模型训练完成')
    return bst

def backtest_data_gen(start_date='2018-05-01', end_date='2020-05-20') :
    stock_list = get_index_stocks('000300.XSHG', date=None)
    data_pre = get_price(stock_list, start_date=start_date, end_date=end_date, frequency='daily', fields=None, skip_paused=False, fq='pre', count=None,panel=False)
    data = data_pre.set_index(['time','code']).sort_index().rename(columns = {'money':'amount'})
    data_A= data.copy()
    data_A['vwap']=data_A['amount']/data_A['volume']
    data_rank = pd.concat([data_A,data_A.groupby(level=0,sort=False).rank()],axis=1,join='inner').sort_values(['time','code'])
    data_rank .columns=['open', 'high', 'low', 'close', 'volume', 'amount','vwap', 'open_rank', 'high_rank',
           'low_rank', 'close_rank', 'volume_rank', 'amount_rank','vwap_rank']
    ind = pd.concat([ALPHA006(data_rank),
                 ALPHA003(data_rank),
                 ALPHA013(data_rank),
                 ALPHA014(data_rank),
                 ALPHA015(data_rank),
                 ALPHA016(data_rank),
                 ALPHA027(data_rank),
                 ALPHA028(data_rank),
                 ALPHA040(data_rank),
                 ALPHA042(data_rank),
                 ALPHA044(data_rank),
                 ALPHA_MA5(data_rank)],axis =1)
    ind_factor = ind.dropna(axis=0)
    ind_factor_lag12 = pd.concat([ind_factor,shift_data(ind_factor,1),shift_data(ind_factor,2),shift_data(ind_factor,3)],axis=1)
    return ind_factor_lag12
def xgboost_target_stock_list_gen(target_datetime,data_test_gen,bst):
    data_test_gen_date = data_test_gen.loc[(target_datetime,slice(None)),:]
    data_test =  np.array(data_test_gen_date)
    dtest = xgb.DMatrix(data_test)
    y_pred = bst.predict(dtest)
    return pd.DataFrame(y_pred[:,1]-0.5,index=data_test_gen_date.index).sort_values(by=0,ascending=False)


















