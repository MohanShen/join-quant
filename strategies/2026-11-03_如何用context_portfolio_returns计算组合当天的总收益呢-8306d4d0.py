# Clone from JoinQuant
# postId: 8306d4d03a8f3f05ee36e3dc7f5dc004
# backtestId: 04c59898025aaf47ea26804f9e79e226
# title: 如何用context.portfolio.returns计算组合当天的总收益呢？

# # 导入函数库
import jqdata
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn import linear_model,preprocessing
from jqfactor import standardlize
import math
import talib as tb

g.data = []
data = range(1500)
g.df = pd.DataFrame(data,columns=['series'])
print(len(g.df))
g.deal={}
g.ini_posed={}
g.sec=[]

def initialize(context):
    subscribe("000005.XSHE", 'tick')
    set_option('use_real_price', True)
    log.info('初始函数开始运行且全局只运行一次')
    log.set_level('order', 'error')
    set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=0), type='stock')
    set_slippage(FixedSlippage(0.0))
    #run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
    run_daily(market_open, time='close', reference_security='000300.XSHG')
    #tick预测肯定选择历史某一天预测当天的，而不是跨天，跨天怎么预测？那得多长一个？又不是一上来开单

    sec=get_all_securities("stock").index.tolist()[::3] 
    g.sample=sec
    # g.avgcost={};g.toppositive={}
    # for item in g.sample:
    #     g.avgcost[item]=[];
    #     g.toppositive[item]=0.
    #     g.deal[item]=False;
    #     g.ini_posed[item]=False
    set_benchmark("000300.XSHG");
    if len(g.sample)==1:
        set_benchmark(g.sample[0])
    
    #避免幸存者误差，股票上市和退市日期都要在测试期内
    g.dft = get_all_securities("stock",context.run_params.end_date).loc[sec];
    g.dft=g.dft[g.dft.end_date>context.run_params.end_date]
    g.dft=g.dft.start_date
    g.dft=pd.Series([i.strftime("%Y-%m-%d") for i in g.dft],index=g.dft.index);

def before_market_open(context):  #这里不提供策略和交易等方法，只是数据处理和股票刷选
    date=context.current_dt.strftime("%Y-%m-%d")
    if date[5:7] in ["01","02"]:
        date_shouldbe = str(int(date[:4])-1)+"-"+str(int(date[5:7])+12- 2 ) + date[7:]
    else :
        date_shouldbe = date[:5] + str(int(date[5:7])- 2 ).zfill(2) + date[7:]
    
    qlfd = g.dft[g.dft <= date_shouldbe]
    g.sec.extend(list(qlfd.index))
    if g.sample!=[]:
        g.sec=list(set(g.sec)&set(g.sample))
    else:
        g.sec=list(set(g.sec)&set(get_all_securities("stock",date).index))
    
def handle_tick(context, tick):  #类似open_market是打开市场，但除了打开和跑常规策略和交易还通过两一个参数提供一些额外的open和before open不可以提供的定制数据方法,
    row = [tick.datetime, tick.code, tick.current, tick.b1_p, tick.a1_p, tick.a1_v*100, tick.a2_v*100, tick.a3_v*100, 
    tick.a4_v*100,tick.a5_v*100,tick.b1_v*100, tick.b2_v*100, tick.b3_v*100, tick.b4_v*100, tick.b5_v*100]
    g.data.append(row)
    #时间在右上方的平台按钮设置
    #g.data = g.data.fillna(g.data.mean())
    # print(row)

def market_open(context):
    # print(g.data)
    l = len(g.data)
    print(l)
    # print(g.data)
    g.data = pd.DataFrame(g.data)
    # print(g.data)
    g.data = g.data.fillna(g.data.mean())
    g.data = g.data.replace(0,mean(g.data))
    g.data = np.array(g.data)
    g.data = g.data.tolist()
    a1 = [x[0] for x in g.data]
    a2 = [x[1] for x in g.data]
    a3 = [x[2] for x in g.data]
    a4 = [x[3] for x in g.data]
    a5 = [x[4] for x in g.data]
    a6 = [x[5] for x in g.data]
    a7 = [x[6] for x in g.data]
    a8 = [x[7] for x in g.data]
    a9 = [x[8] for x in g.data]
    a10 = [x[9] for x in g.data]
    a11 = [x[10] for x in g.data]
    a12 = [x[11] for x in g.data]
    a13 = [x[12] for x in g.data]
    a14 = [x[13] for x in g.data]
    a15 = [x[14] for x in g.data]
    b6 = [0];b7 = [0];b8 = [0];b9 = [0];b10 = [0];b11 = [0];b12 = [0];b13 = [0];b14 = [0];b15 = [0];
    b6.extend(a6);b7.extend(a7);b8.extend(a8);b9.extend(a9);b10.extend(a10);b11.extend(a11);b12.extend(a12);
    b13.extend(a13);b14.extend(a14);b15.extend(a15);
    b6.pop();b7.pop();b8.pop();b9.pop();b10.pop();b11.pop();b12.pop();b13.pop();b14.pop();b15.pop()
    #print(len(a6),len(b6))
    #print(b6)
    b6 = map(lambda (x,y):x-y,zip(a6,b6)); 
    b7 = map(lambda (x,y):x-y,zip(a7,b7)); 
    b8 = map(lambda (x,y):x-y,zip(a8,b8)); 
    b9 = map(lambda (x,y):x-y,zip(a9,b9)); 
    b10 = map(lambda (x,y):x-y,zip(a10,b10)); 
    b11 = map(lambda (x,y):x-y,zip(a11,b11)); 
    b12 = map(lambda (x,y):x-y,zip(a12,b12)); 
    b13 = map(lambda (x,y):x-y,zip(a13,b13)); 
    b14 = map(lambda (x,y):x-y,zip(a14,b14)); 
    b15 = map(lambda (x,y):x-y,zip(a15,b15)); 
    #print(a6)
    factor1 = (np.array(b11)+np.array(b12)+np.array(b13)+\
    np.array(b14)+np.array(b15))-(np.array(b6)+np.array(b7)+\
    np.array(b8)+np.array(b9)+np.array(b10))
    factor1[0]=0
    factor1 = standardlize(factor1, inf2nan=True, axis=1)
    g.df['DiffCumOI'] = pd.Series(factor1)
    ##构建第二个因子，买一量对数差
    b = [0]
    for i in range(l-1):
        factor2 = math.log10(a11[i+1]) - math.log10(a11[i])
        b.append(factor2)
    b = standardlize(np.array(b), inf2nan=True, axis=1)
    g.df['买1量对数差'] = pd.DataFrame(b)
    ##构建第三个因子，卖一量对数差
    c = [0]
    for i in range(l-1):
        factor3 = math.log10(a6[i+1]) - math.log10(a6[i])
        c.append(factor3)
    c = standardlize(np.array(c), inf2nan=True, axis=0)
    g.df['卖1量对数差'] = pd.DataFrame(c)
    #构建第四个因子，买一价格对数差
    d = [0]
    for i in range(l-1):
        factor4 = math.log10(a4[i+1])-math.log10(a4[i])
        d.append(factor4)
    d = standardlize(np.array(d), inf2nan=True, axis=0)
    g.df['买1价格对数收益'] = pd.DataFrame(d)
    #构建第五个因子，卖一价格对数差
    e = [0]
    for i in range(l-1):
        factor5 = math.log10(a5[i+1])-math.log10(a5[i])
        e.append(factor5)
    e = standardlize(np.array(e), inf2nan=True, axis=0)
    g.df['卖1价格对数收益'] = pd.DataFrame(e)
    #构建第六个因子--买一价格的一阶滞后收益
    h = [0]
    h0 = g.df['买1价格对数收益'].values.tolist()
    h = h+h0 
    g.df['买1价格的一阶滞后收益'] = h[:(len(h)-1)]                        #可能报错，不是dataframe
    #构建第七个因子-有效均价的变化率,这个指标是利用调整后的前后期均价求得,不用再标准化
    f = [0]
    for i in range(l-1):
        factor61 = (a4[i+1]*a11[i+1]+a5[i+1]*a6[i+1])/(a11[i+1]+a6[i+1])
        factor62 = (a4[i]*a11[i]+a5[i]*a6[i])/(a11[i]+a6[i])
        factor6 = factor61/factor62 -1
        f.append(factor6)
    f = np.array(f)
    g.df['mideffective prices chg'] = pd.DataFrame(f)
    ##构建y变量
    k = [0]
    for i in range(l-1):
         midpchg =math.log(a3[i+1]/a3[i])  #链式索引,这里可以是未来5分粥后的数据减去现在的得到一个变化率
         k.append(midpchg)                                     #前面的和这里的索引i可以拉长，增加预测长度
    k =np.array(k)
    g.df['mipricechg'] = pd.DataFrame(k)
    # print(g.df)

    # # 建立线性模型
    df1 = g.df.iloc[0:22,:]
    x = df1[['买1量对数差','卖1量对数差','买1价格对数收益','卖1价格对数收益','买1价格的一阶滞后收益','mideffective prices chg','DiffCumOI']]
    y = df1[['mipricechg']]
    xy = x.join(y)
    print(xy.corr())
    # # 拟合
    #regre = linear_model.Lasso()
    regre = linear_model.LinearRegression()
    a = regre.fit(x,y) # 调用模型的fit方法，对模型进行训练，也是求解参数的过程
    b = regre.score(x,y)  #对模型进行检验
    print ("截距b: ",regre.intercept_)
    print ('x的系数值a：',regre.coef_)
    print('拟合优度：',b)

    # # #预测
    df2 = g.df.iloc[40:79,]
    #print(len(df2))
    x = df2[['买1量对数差','卖1量对数差','买1价格对数收益','卖1价格对数收益','买1价格的一阶滞后收益','mideffective prices chg','DiffCumOI']]
    y_Pre = regre.predict(x)
    y_Orig = df2[['mipricechg']]
    x1 = range(0,39)
    x2 = range(0,39)
    print('y_Pre_max', y_Pre)
    
    #交易下单
    
    
    
    
    
    
    
    
    
    g.data=[]
    #不是每个tick都有交易，流动性有些比较差；所以只在有交易的tick下才会有交易
