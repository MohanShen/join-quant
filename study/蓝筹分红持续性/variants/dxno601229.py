# Clone from JoinQuant
# postId: 94888e61be61ce9dce51c6d30d0327d3
# backtestId: c8365d0b74826c671c96201aace59832
# title: 蓝筹大盘分红策略【超稳健】

# 导入函数库
from jqdata import *
import pandas as pd
import numpy as np
# 初始化函数，设定基准等等
def initialize(context):
    set_option("avoid_future_data", True)
    set_param()
    
    run_monthly(main,1,time='9:30')
    
def main(context):
    #1、设置大股票池,返回df，包括code、statDate
    df=getBigStocks()
    #2、财报质量控制,返回code,lrzl,yszzl,zcfzl,ejdtb,ejdhb
    df=controlReport(df, context.current_dt.date())  # u-e9-dxpit: pass d0
    _dxn_pre(context, df)  # u-e9-dxno601229 obs
    if 'code' in df.columns: df=df[df.code!='601229.XSHG'].reset_index(drop=True)  # u-e9-dxno601229
    #3、设置下单列表
    setSmallStocks(df)
    _dxn_mon(context, df)  # u-e9-dxno601229 obs
    #4、下单
    orderStock(context)

#1、设置大股票池,返回df，包括code、statDate    
def getBigStocks():
    stocks = get_index_stocks('000300.XSHG')
    q=query(
               income.statDate,
               income.code
             ).filter(
                #income.net_profit>100000000,
                valuation.pe_ratio>0,
                income.code.in_(stocks)#,
                #income.code.in_(['601918.XSHG','601899.XSHG','601958.XSHG','600170.XSHG',
                #    '600631.XSHE','600585.XSHG','600023.XSHG','000333.XSHE','002157.XSHE',
                #    '600104.XSHG'])
                 )
                 
    rets=get_fundamentals(q)#.reset_index(drop=True)
    return rets
def controlReport(df, d0):  # u-e9-dxpit: d0 = rebalance date
    df_qc=pd.DataFrame()
    for i in range(0,len(df)):
        statDate=df.loc[i].statDate
        q=int(int(statDate[5:7]) / 3)
        year=int(statDate[:4])
        statqs=[]
        for kk in range(0,12):
            statq=str(year) + 'q' + str(q)
            statqs.append(statq)
            q=q -1
            if q==0 : 
                q=4
                year= year - 1
        code=df.loc[i].code
        #只看现金分红
        gx=finance.run_query(query(finance.STK_XR_XD.bonus_amount_rmb,finance.STK_XR_XD.report_date).filter(
            finance.STK_XR_XD.code==code,
            finance.STK_XR_XD.report_date<=statDate,
            # u-e9-dxpit: announcement bound (dxla null rule), BEFORE the 12-row limit
            (finance.STK_XR_XD.board_plan_pub_date<=d0) | ((finance.STK_XR_XD.board_plan_pub_date==None) & (
                (finance.STK_XR_XD.shareholders_plan_pub_date<=d0) | (finance.STK_XR_XD.implementation_pub_date<=d0) |
                ((finance.STK_XR_XD.shareholders_plan_pub_date==None) & (finance.STK_XR_XD.implementation_pub_date==None))))
            ).order_by(finance.STK_XR_XD.report_date.desc()).limit(12))
       
        gx=gx.fillna(0)
        #统计分红
        one_year=0.0
        two_year=0.0
        three_year=0.0
        for j in range(0,len(gx)):
            report_date=gx.loc[j].report_date
            q=report_date.month//3
            year=report_date.year
            statq=str(year) + 'q' + str(q)
            if statq in (statqs[0],statqs[1],statqs[2],statqs[3]):
                one_year=one_year+gx.loc[j].bonus_amount_rmb
            if statq in (statqs[4],statqs[5],statqs[6],statqs[7]):
                two_year=two_year+gx.loc[j].bonus_amount_rmb
            if statq in (statqs[8],statqs[9],statqs[10],statqs[11]):
                three_year=three_year+gx.loc[j].bonus_amount_rmb
         #市值
        qcap=query(valuation.market_cap).filter(valuation.code==code)
        market_cap=get_fundamentals(qcap).loc[0,'market_cap']*10000 
        
        comp_value=market_cap*0.02
        if one_year>comp_value and two_year>comp_value*0.8 and three_year>comp_value*0.64 and (one_year+two_year+three_year)>market_cap*0.1:
            cc=pd.DataFrame([[code,one_year/market_cap,two_year/market_cap,three_year/market_cap]],columns=['code','gxl','gxl2','gxl3']) 
            df_qc=df_qc.append(cc,ignore_index=True)
    
 
    return df_qc.reset_index(drop=True)

def setSmallStocks(df):
    log.info(df.shape[0])
    if df.shape[0]<=g.stock_num*2: 
        g.bten=[]
        g.bfive=[]
        return 
    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*16)
    if len(df)<g.stock_num*4:
        df=df.head(len(df) -g.stock_num*2)
    df=df.sort_values(by='gxl2',ascending=False).head(g.stock_num*8)
    df=df.sort_values(by='gxl3',ascending=False).head(g.stock_num*4)
    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*2)
    #
    g.bten=list(df.head(g.stock_num*2)['code'])
    g.bfive=list(df.head(g.stock_num)['code'])
    #moreinfo(df)
def orderStock(context):
    
    bfive=g.bfive
    bten=g.bten
    
    all_value=context.portfolio.total_value
    for sell_code in context.portfolio.long_positions.keys():
        if sell_code not in bfive:
            #卖掉
            log.info('sell all:',sell_code)
            order_target_value(sell_code,0)
        #else:
        #    log.info('sell part:'+sell_code)
        #    order_target_value(sell_code,all_value/g.stock_num)
            
    for buy_code in bten:
        if buy_code not in context.portfolio.long_positions.keys():
            cash_value=context.portfolio.available_cash
            buy_value=all_value/g.stock_num
    
            if cash_value > buy_value/2 :
                log.info('buy:'+buy_code+'   ' +str(buy_value))
                order_target_value(buy_code,buy_value)
                       
def set_param():
    g.bten=[]
    g.bfive=[]
    g.stock_num = 5
    g.fin=pd.DataFrame()
     #显示所有列
    pd.set_option('display.max_columns', None)
    #显示所有行
    pd.set_option('display.max_rows', None)
    #设置value的显示长度为100，默认为50
    pd.set_option('max_colwidth',100)
   

    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    
     ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

def giveScore():
    '''
    #给环比打分
    #scored_list['ejdhb'][scored_list['ejdhb']>1.5]=1.5
    scored_list=scored_list.sort_values(by='ejdhb', ascending=False).reset_index(drop=True)
    scored_list=scored_list.head(40)
    
    #给同比打分
    #scored_list['ejdtb'][scored_list['ejdtb']>1.5]=1.5
    scored_list=scored_list.sort_values(by='ejdtb', ascending=False).reset_index(drop=True)
    scored_list=scored_list.head(20)
    
    scored_list=scored_list.sort_values(by='kfsyl', ascending=True).reset_index(drop=True)
    scored_list['kfsyl_score']=100 - scored_list.index*100/20
    scored_list=scored_list.sort_values(by='ejdhb', ascending=False).reset_index(drop=True)
    scored_list['ejdhb_score']=100 - scored_list.index*100/20
    scored_list=scored_list.sort_values(by='ejdtb', ascending=False).reset_index(drop=True)
    scored_list['ejdtb_score']=100 - scored_list.index*100/20
    
    #算总分
    scored_list['all_score']=scored_list['kfsyl_score'] + scored_list['ejdhb_score']*0.5+scored_list['ejdtb_score']*0.3
     
    scored_list=scored_list.sort_values(by='all_score', ascending=False).reset_index(drop=True)
    '''
    

#行业控制   
def cc_industry(stock_list):
    '''
    stocks=list(stock_list['code'])
    
    compinfo=finance.run_query(
        query(
            finance.STK_COMPANY_INFO.code,
            finance.STK_COMPANY_INFO.short_name,
            finance.STK_COMPANY_INFO.industry_2,
            finance.STK_COMPANY_INFO.industry_id).filter(
                finance.STK_COMPANY_INFO.code.in_(stocks)
                ))
                
    stock_list=pd.merge(stock_list,compinfo,on='code')
    
    
    p=dict.fromkeys(set(compinfo['industry_id']),0)
    rets=pd.DataFrame()
    
    for index in list(stock_list.index):
        industry_id=stock_list.loc[index].industry_id
        num=p.get(industry_id,0)
        if num<2: 
           rets=rets.append(stock_list.loc[index])
        p[industry_id]=num+1
        
    return rets
    '''
## 
def  moreinfo(df):
    code=list(df.code)
    
    compinfo=finance.run_query(query(finance.STK_COMPANY_INFO.code,finance.STK_COMPANY_INFO.short_name,finance.STK_COMPANY_INFO.industry_id
        ).filter(finance.STK_COMPANY_INFO.code.in_(code)))
    dd=pd.merge(df,compinfo)
    log.info(dd)
    
    
    
 

# ===== u-e9-dxno601229 observation helpers (nothing below feeds an order) =====
_DXN_REF_BFIVE = {'2024-01-02': ['601088.XSHG', '601169.XSHG', '600015.XSHG', '601229.XSHG', '601006.XSHG'],
    '2024-02-01': ['601166.XSHG', '600585.XSHG', '601229.XSHG', '601328.XSHG', '601006.XSHG'],
    '2024-03-01': ['601166.XSHG', '600585.XSHG', '601229.XSHG', '000895.XSHE', '601169.XSHG'],
    '2024-04-01': ['601919.XSHG', '601166.XSHG', '600188.XSHG', '601006.XSHG', '601229.XSHG'],
    '2024-05-06': ['000983.XSHE', '600188.XSHG', '601919.XSHG', '601229.XSHG', '601166.XSHG'],
    '2024-06-03': ['000983.XSHE', '600188.XSHG', '601166.XSHG', '000651.XSHE', '601939.XSHG'],
    '2024-07-01': ['000983.XSHE', '600188.XSHG', '601229.XSHG', '000895.XSHE', '000651.XSHE'],
    '2024-08-01': ['000983.XSHE', '600188.XSHG', '601229.XSHG', '000895.XSHE', '601166.XSHG'],
    '2024-09-02': ['600016.XSHG', '000983.XSHE', '600188.XSHG', '601006.XSHG', '600015.XSHG'],
    '2024-10-08': ['601229.XSHG', '600016.XSHG', '000983.XSHE', '600188.XSHG', '601328.XSHG'],
    '2024-11-01': ['000983.XSHE', '601229.XSHG', '600016.XSHG', '600188.XSHG', '601818.XSHG'],
    '2024-12-02': ['000983.XSHE', '600188.XSHG', '601229.XSHG', '600016.XSHG', '601818.XSHG']}

def _dxn_pre(context, df):
    try:
        _in = 1 if ('code' in df.columns and '601229.XSHG' in list(df['code'])) else 0
        log.info('DXNO date=%s in_qual=%d n_qual_pre=%d' % (str(context.current_dt.date()), _in, df.shape[0]))
    except Exception as _e:
        log.error('DXN-ERR pre err=%r' % (_e,))

def _dxn_mon(context, df):
    try:
        _d = str(context.current_dt.date())
        _ref = _DXN_REF_BFIVE.get(_d)
        _ov = -1 if _ref is None else len([c for c in g.bfive if c in _ref])
        _empty = 1 if df.shape[0] <= g.stock_num*2 else 0
        _in = [c for c in g.bfive if _ref is not None and c not in _ref]
        _out = [c for c in (_ref or []) if c not in g.bfive]
        log.info('DXMON date=%s n_qual=%d empty=%d bfive=%s bten=%s ref_overlap=%d ref_bfive=%s in=%s out=%s' % (_d, df.shape[0], _empty, ','.join(g.bfive), ','.join(g.bten), _ov, ','.join(_ref or []), ','.join(_in), ','.join(_out)))
    except Exception as _e:
        log.error('DXN-ERR mon err=%r' % (_e,))
# ===== end u-e9-dxno601229 observation helpers =====


# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====
