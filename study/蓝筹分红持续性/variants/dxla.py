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
    _dx_enter(context)  # u-e9-dxla probe
    #1、设置大股票池,返回df，包括code、statDate
    df=getBigStocks()
    #2、财报质量控制,返回code,lrzl,yszzl,zcfzl,ejdtb,ejdhb
    df=controlReport(df)
    #3、设置下单列表
    setSmallStocks(df)
    _dx_month(context, df)  # u-e9-dxla probe
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
def controlReport(df):
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
            finance.STK_XR_XD.report_date<=statDate
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
        _dx_name(code, statDate, statqs, one_year, two_year, three_year, market_cap)  # u-e9-dxla probe
    
 
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
    
    
    
 

# ===== u-e9-dxla probe helpers (observation only; nothing below feeds an order) =====
def _dx_enter(context):
    try:
        g.dx_d0 = str(context.current_dt.date())
        g.dx_honest = []
        g.dx_cnt = {'names': 0, 'dxla_rows': 0, 'dxla_rows_nz': 0, 'flips': 0, 'ties': 0, 'nulls': 0, 'cut': 0}
        _tot = 0.0
        for _c in list(context.portfolio.long_positions.keys()):
            _p = context.portfolio.long_positions[_c]
            _tot += _p.value
            log.info('DXPOS date=%s code=%s value=%.2f' % (g.dx_d0, _c, _p.value))
        log.info('DXPOSTOT date=%s total=%.2f pos=%.2f cash=%.2f n=%d' % (g.dx_d0, context.portfolio.total_value, _tot, context.portfolio.available_cash, len(context.portfolio.long_positions)))
    except Exception as _e:
        log.error('DX-ERR enter err=%r' % (_e,))

def _dx_ds(v):
    _s = str(v)[:10]
    if len(_s) == 10 and _s[:4].isdigit():
        return _s
    return None

def _dx_sums(bon, rds, statqs):
    _o = 0.0
    _t = 0.0
    _h = 0.0
    for _j in range(len(rds)):
        _rd = rds[_j]
        _sq = str(_rd.year) + 'q' + str(_rd.month // 3)
        if _sq in (statqs[0], statqs[1], statqs[2], statqs[3]):
            _o = _o + bon[_j]
        if _sq in (statqs[4], statqs[5], statqs[6], statqs[7]):
            _t = _t + bon[_j]
        if _sq in (statqs[8], statqs[9], statqs[10], statqs[11]):
            _h = _h + bon[_j]
    return _o, _t, _h

def _dx_qual(o, t, h, mc):
    _cv = mc * 0.02
    return 1 if (o > _cv and t > _cv * 0.8 and h > _cv * 0.64 and (o + t + h) > mc * 0.1) else 0

def _dx_name(code, statDate, statqs, one_year, two_year, three_year, market_cap):
    try:
        _d0 = g.dx_d0
        g.dx_cnt['names'] += 1
        S = finance.STK_XR_XD
        _pq = finance.run_query(query(S.bonus_amount_rmb, S.report_date, S.board_plan_pub_date,
                                      S.shareholders_plan_pub_date, S.implementation_pub_date,
                                      S.a_bonus_date, S.plan_progress).filter(
            S.code == code,
            S.report_date <= statDate
            ).order_by(S.report_date.desc()).limit(16))
        _n = len(_pq)
        _bon = []
        _rds = []
        _pub = []
        _win = set(statqs[:12])
        for _j in range(_n):
            _r = _pq.iloc[_j]
            _b = _r['bonus_amount_rmb']
            try:
                _b = 0.0 if _b != _b or _b is None else float(_b)
            except Exception:
                _b = 0.0
            _bon.append(_b)
            _rd = _r['report_date']
            _rds.append(_rd)
            _bd = _dx_ds(_r['board_plan_pub_date'])
            _sd = _dx_ds(_r['shareholders_plan_pub_date'])
            _id = _dx_ds(_r['implementation_pub_date'])
            _ad = _dx_ds(_r['a_bonus_date'])
            _alt = [x for x in (_sd, _id) if x is not None]
            _p = _bd if _bd is not None else (min(_alt) if _alt else None)
            _pub.append(_p)
            if _j < 12:
                _sq = str(_rd.year) + 'q' + str(_rd.month // 3)
                if _sq in _win:
                    _fut = []
                    for _nm, _v in (('board', _bd), ('share', _sd), ('impl', _id), ('a_bonus', _ad)):
                        if _v is not None and _v > _d0:
                            _fut.append(_nm)
                    if _fut:
                        g.dx_cnt['dxla_rows'] += 1
                        if _b != 0:
                            g.dx_cnt['dxla_rows_nz'] += 1
                        log.info('DXLA date=%s code=%s statDate=%s report_date=%s bonus=%.0f board=%s share=%s impl=%s a_bonus=%s progress=%s fut=%s' % (_d0, code, statDate, str(_rd)[:10], _b, _bd, _sd, _id, _ad, _r['plan_progress'], ','.join(_fut)))
            if _p is None:
                g.dx_cnt['nulls'] += 1
                log.info('DXNULL date=%s code=%s report_date=%s pub=null' % (_d0, code, str(_rd)[:10]))
        # probe control: the probe's own unfiltered first 12 must reproduce the book's sums
        _bo, _bt, _bh = _dx_sums(_bon[:12], _rds[:12], statqs)
        if abs(_bo - one_year) > 1e-6 * max(1.0, abs(one_year)) or abs(_bt - two_year) > 1e-6 * max(1.0, abs(two_year)) or abs(_bh - three_year) > 1e-6 * max(1.0, abs(three_year)):
            g.dx_cnt['ties'] += 1
            log.error('DXTIE date=%s code=%s book=%.0f/%.0f/%.0f probe12=%.0f/%.0f/%.0f' % (_d0, code, one_year, two_year, three_year, _bo, _bt, _bh))
        # honest: drop rows announced after d0 (null pub -> known), THEN cut to 12
        _keep = [_j for _j in range(_n) if _pub[_j] is None or _pub[_j] <= _d0]
        if _n == 16 and len(_keep) < 12:
            g.dx_cnt['cut'] += 1
            log.error('DXCUT date=%s code=%s kept=%d of 16 (limit 16 may truncate the honest set)' % (_d0, code, len(_keep)))
        _keep = _keep[:12]
        _ho, _ht, _hh = _dx_sums([_bon[_j] for _j in _keep], [_rds[_j] for _j in _keep], statqs)
        _qb = _dx_qual(one_year, two_year, three_year, market_cap)
        _qh = _dx_qual(_ho, _ht, _hh, market_cap)
        if _qh:
            g.dx_honest.append((code, _ho / market_cap, _ht / market_cap, _hh / market_cap))
        if _qb != _qh:
            g.dx_cnt['flips'] += 1
            log.info('DXFLIP date=%s code=%s book=%d honest=%d book_sums=%.0f/%.0f/%.0f honest_sums=%.0f/%.0f/%.0f mcap=%.0f' % (_d0, code, _qb, _qh, one_year, two_year, three_year, _ho, _ht, _hh, market_cap))
    except Exception as _e:
        log.error('DX-ERR name date=%s code=%s err=%r' % (str(getattr(g, 'dx_d0', '?')), code, _e))

def _dx_select(df, n):
    # exact replica of setSmallStocks, returning instead of writing g
    if df.shape[0] <= n * 2:
        return [], [], 1
    df = df.sort_values(by='gxl', ascending=False).head(n * 16)
    if len(df) < n * 4:
        df = df.head(len(df) - n * 2)
    df = df.sort_values(by='gxl2', ascending=False).head(n * 8)
    df = df.sort_values(by='gxl3', ascending=False).head(n * 4)
    df = df.sort_values(by='gxl', ascending=False).head(n * 2)
    return list(df.head(n * 2)['code']), list(df.head(n)['code']), 0

def _dx_month(context, df):
    try:
        _d0 = g.dx_d0
        _n = g.stock_num
        _bten, _bfive, _be = _dx_select(df, _n)
        if _bten != list(g.bten) or _bfive != list(g.bfive):
            log.error('DXREP date=%s replica=%s/%s actual=%s/%s' % (_d0, _bfive, _bten, list(g.bfive), list(g.bten)))
        _hdf = pd.DataFrame(g.dx_honest, columns=['code', 'gxl', 'gxl2', 'gxl3'])
        _hten, _hfive, _he = _dx_select(_hdf, _n)
        log.info('DXMON date=%s n_qual_book=%d n_qual_honest=%d bfive_book=%s bfive_honest=%s bten_book=%s bten_honest=%s empty_book=%d empty_honest=%d five_diff=%d ten_diff=%d' % (
            _d0, df.shape[0], len(_hdf), ','.join(g.bfive), ','.join(_hfive), ','.join(g.bten), ','.join(_hten),
            _be, _he, 1 if list(g.bfive) != _hfive else 0, 1 if list(g.bten) != _hten else 0))
        log.info('DXCNT date=%s %s' % (_d0, ' '.join('%s=%d' % (k, g.dx_cnt[k]) for k in sorted(g.dx_cnt))))
        if df.shape[0] > 0:
            _g5 = list(df.sort_values(by='gxl', ascending=False).head(_n)['code'])
        else:
            _g5 = []
        log.info('DXG5 date=%s bfive_gxlonly=%s' % (_d0, ','.join(_g5)))
        if len(g.bfive) > 0:
            _ci = finance.run_query(query(finance.STK_COMPANY_INFO.code, finance.STK_COMPANY_INFO.industry_id,
                                          finance.STK_COMPANY_INFO.industry_1).filter(
                finance.STK_COMPANY_INFO.code.in_(list(g.bfive))))
            for _i in range(len(_ci)):
                log.info('DXIND date=%s code=%s industry_id=%s industry_1=%s' % (_d0, _ci['code'].iloc[_i], _ci['industry_id'].iloc[_i], _ci['industry_1'].iloc[_i]))
    except Exception as _e:
        log.error('DX-ERR month date=%s err=%r' % (str(getattr(g, 'dx_d0', '?')), _e))
# ===== end u-e9-dxla probe helpers =====


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
