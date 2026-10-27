# Clone from JoinQuant
# postId: b3066395ee0a70ad99e38fb306a5655f
# backtestId: 93a3e04d08bf69417d0bbf3a0842e6c4
# title: 探索多维数据极端值处理方法

from jqdata import*
import statsmodels.api as sm
import numpy as np
import pandas as pd
from sklearn import svm


#初始化策略
def initialize(context):
    set_params()
    set_backtest(context)
    run_monthly(Trade,monthday = 1)


#设定回测相关参数
def set_backtest(context):
    #设置基准股票池
    set_benchmark(g.benchmark)
    #开启真实价格
    set_option('use_real_price', True)
    #设定手续费
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')


#设定回测参数
def set_params():
    #股票基准
    g.benchmark = '000300.XSHG'
    #设定调仓周期
    g.fre = 60
    #把全部交易日加入缓存
    g.trade_days = list(get_all_trade_days())
    #KNN个数
    g.KNN_num = 5
    
'''
------------------------------------------------------------------------------------
交易函数
-------------------------------------------------------------------------------------
'''


def Trade(context):
    hold_list = up_low_predict(context)
    current_position = list(context.portfolio.long_positions.keys())
    for stock in current_position:
        if stock not in hold_list:
            order_target(stock,0)
        else:
            pass
    if len(hold_list) != 0:
        for stock in hold_list:
            order_value(stock,context.portfolio.available_cash / len(hold_list))
    else:
        for stock in current_position:
            order_target(stock,0)


'''
------------------------------------------------------------------------------------
进行数据训练
-------------------------------------------------------------------------------------
'''


#获取当前数据
def get_predict_data(context):
    current_date = context.current_dt.date()
    stock_list = get_index_stocks(g.benchmark,date = current_date)
    q = query(
    valuation.code,
    valuation.market_cap,
    (balance.total_owner_equities/valuation.market_cap/100000000.0).label("BTM"),
    indicator.roe,
    balance.total_assets.label("Inv")
    ).filter(
        valuation.code.in_(stock_list)
    )
    current_data = get_fundamentals(q,date = current_date)
    return current_data.dropna()


#进行svm训练
def SVM_classify_train(context):
    code,train_feature,train_label = get_deal_data(context)
    svm_model = svm.SVC(kernel = 'rbf')
    svm_model.fit(train_feature,train_label)
    return svm_model


#处理当前获取的特征数据
def deal_current_data(context):
    pre_deal_data = get_predict_data(context)
    code = pre_deal_data['code']
    orgin_data = pre_deal_data.iloc[:,1:]
    deal_vector,L2_mat = deal_min_dis_vector(orgin_data)
    dis_data = L2_mat.sum(axis = 1)
    train_data = Re_KNN(dis_data,g.KNN_num,L2_mat)
    return code,train_data


#通过训练模型对走势做出预测,输出持仓列表
def up_low_predict(context):
    svm_model = SVM_classify_train(context)
    stock_code,current_data = deal_current_data(context)
    predict_result = svm_model.predict(current_data)
    arg_index = np.where(predict_result == 1.0)
    try:
        if len(arg_index) > 0:
            hold_list = [stock_code[i] for i in arg_index[0]]
            return hold_list
        else:
            return []
    except KeyError:
        return []
        

'''
------------------------------------------------------------------------------------
获取训练特征数据
-------------------------------------------------------------------------------------
'''


#获取训练特征数据
def get_train_feature(stock_list,date,n):
    past_date = g.trade_days[g.trade_days.index(date) - (n+1)]
    q = query(
    valuation.code,
    valuation.market_cap,
    (balance.total_owner_equities/valuation.market_cap/100000000.0).label("BTM"),
    indicator.roe,
    balance.total_assets.label("Inv")
    ).filter(
        valuation.code.in_(stock_list)
    )
    data1 = get_fundamentals(q,date = past_date).dropna()
    return data1['code'],data1.iloc[:,1:]



#使用最近n天的收益率作为标签
def get_train_label(stock_list,date,n):
    yester_day = g.trade_days[g.trade_days.index(date) - 1]
    past_date = g.trade_days[g.trade_days.index(date) - (n+1)]
    past_price = get_price(stock_list,past_date,past_date,'1d',['close'])['close'].iloc[0,:]
    yes_price = get_price(stock_list,yester_day,yester_day,'1d',['close'])['close'].iloc[0,:]
    return ((yes_price - past_price) / past_price * 100).fillna(0)


#整合训练数据
def get_train_data(context):
    date = context.current_dt.date()
    stock_list = get_index_stocks(g.benchmark,date = date)
    code,data_df = get_train_feature(stock_list,date,g.fre)
    label = get_train_label(stock_list,date,g.fre)
    label[label >= 5] = int(1)
    label[label <= -5] = int(-1)
    label[(label != 1) & (label != -1)] = 0 
    return code,data_df,label[data_df.index]
    

#核向量寻找方法
#带有范数惩罚距离矩阵计算
def new_cal_sumdis(vector,mat):
    dis_mat = (mat - vector) ** 2
    return dis_mat / (dis_mat.mean(axis = 0) / dis_mat.mean(axis = 0).sum())


#范数惩罚方法下寻找核向量
def deal_min_dis_vector(mat):
    array_mat = array(mat)
    min_vec = array_mat[0]
    min_distance = float(new_cal_sumdis(min_vec,mat).sum(axis = 1).sum())
    for vector in array_mat:
        vec_dis = float(new_cal_sumdis(vector,mat).sum(axis = 1).sum())
        if vec_dis < min_distance:
            min_vec = vector
            min_distance = vec_dis
        else:
            pass
    return min_vec,new_cal_sumdis(min_vec,mat)
    
   
#反向KNN处理数据离群值 
def Re_KNN(dis_data,K_num,KNN_mat):
    dis_median = dis_data.median()
    dis_mean = dis_data.mean()
    KNN_mat = array(KNN_mat)
    mat_dis = array(dis_data)
    index_list = list(dis_data[dis_data > dis_median + 3 * abs(dis_mean - dis_median)].index)
    for i in list(dis_data[dis_data < dis_median - 3 * abs(dis_mean - dis_median)].index):
        index_list.append(i)
    for i in index_list:
        nn_index = (mat_dis - mat_dis[i]).argsort()[:K_num + 1]
        deal_array = array([KNN_mat[j] for j in nn_index])
        KNN_mat[i] = deal_array.mean(axis = 0)
    return KNN_mat
    
    
#获取处理好的数据
def get_deal_data(context):
    code,train_data,train_label = get_train_data(context)
    deal_vector,L2_mat = deal_min_dis_vector(train_data)
    dis_data = L2_mat.sum(axis = 1)
    train_data = Re_KNN(dis_data,g.KNN_num,L2_mat)
    return code,train_data,train_label
    
    
    
    
    
    
    
    
    