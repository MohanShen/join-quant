# study variant u-2 — family: 向导式低波价值 — LOGGING-ONLY probe of the ATR unit + per-stage survivors
# built from study/向导式低波价值/baseline.py by study/向导式低波价值/build-u-2.js; every insertion is marked # PROBE
# source: strategies/2026-10-29_向导式_ATR指标择时测试_0_0_1-8b9cb8e2.py
# construction: py2to3(source) + utils/strategy-normalize OVERRIDE, no edit (identical to the normalizer's submission)
# built: 2026-11-01 by study/向导式低波价值/build-baseline.js
# Clone from JoinQuant
# postId: 8b9cb8e2ce67b2e9708004cc61a5ef01
# backtestId: 970fb30cb560ce5eff524ff666b98339
# title: 向导式 ATR指标择时测试 0.0.1

from kuanke.wizard import *
from jqdata import *
import numpy as np
import pandas as pd
import talib
import datetime

## 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 设定滑点
    set_slippage(FixedSlippage(0.02))
    # True为开启动态复权模式，使用真实价格交易
    set_option('use_real_price', True) 
    # 设定成交量比例
    set_option('order_volume_ratio', 1)
    # 股票类交易手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    # 个股最大持仓比重
    g.security_max_proportion = 1
    # 选股频率
    g.check_stocks_refresh_rate = 10
    # 买入频率
    g.buy_refresh_rate = 10
    # 卖出频率
    g.sell_refresh_rate = 10
    # 最大建仓数量
    g.max_hold_stocknum = 5

    # 选股频率计数器
    g.check_stocks_days = 0 
    # 买卖交易频率计数器
    g.buy_trade_days=0
    g.sell_trade_days=0 
    # 获取未卖出的股票
    g.open_sell_securities = [] 
    # 卖出股票的dict
    g.selled_security_list={}
    
    # 股票筛选初始化函数
    check_stocks_initialize()
    # 股票筛选排序初始化函数
    check_stocks_sort_initialize()
    # 出场初始化函数
    sell_initialize()
    # 入场初始化函数
    buy_initialize()
    # 风控初始化函数
    risk_management_initialize()

    # 关闭提示
    log.set_level('order', 'error')

    # 运行函数
    run_daily(sell_every_day,'open') #卖出未卖出成功的股票
    run_daily(risk_management, 'every_bar') #风险控制
    run_daily(check_stocks, 'open') #选股
    run_daily(trade, 'open') #交易  
    run_daily(selled_security_list_count, 'after_close') #卖出股票日期计数 
    run_daily(_probe_final, 'after_close')  # PROBE u-2: logging only
      

## 股票筛选初始化函数
def check_stocks_initialize():
    # 是否过滤停盘
    g.filter_paused = True
    # 是否过滤退市  
    g.filter_delisted = True
    # 是否只有ST
    g.only_st = False
    # 是否过滤ST
    g.filter_st = True
    # 股票池
    g.security_universe_index = ["000300.XSHG"]
    g.security_universe_user_securities = []
    # 行业列表
    g.industry_list = ["801010","801020","801030","801040","801050","801080","801110","801120","801130","801140","801150","801160","801170","801180","801200","801210","801230","801710","801720","801730","801740","801750","801760","801770","801780","801790","801880","801890"]
    # 概念列表
    g.concept_list = []

## 股票筛选排序初始化函数
def check_stocks_sort_initialize():
    # 总排序准则： desc-降序、asc-升序
    g.check_out_lists_ascending = 'desc'

## 出场初始化函数
def sell_initialize():
    # 设定是否卖出buy_lists中的股票
    g.sell_will_buy = True

    # 固定出仓的数量或者百分比
    g.sell_by_amount = None
    g.sell_by_percent = None

## 入场初始化函数
def buy_initialize():
    # 是否可重复买入
    g.filter_holded = False

    # 委托类型
    g.order_style_str = 'by_cap_mean'
    g.order_style_value = 100

## 风控初始化函数
def risk_management_initialize():
    # 策略风控信号
    g.risk_management_signal = True

    # 策略当日触发风控清仓信号
    g.daily_risk_management = True

    # 单只最大买入股数或金额
    g.max_buy_value = None
    g.max_buy_amount = None


## 卖出未卖出成功的股票
def sell_every_day(context):
    g.open_sell_securities = list(set(g.open_sell_securities))
    open_sell_securities = [s for s in context.portfolio.positions.keys() if s in g.open_sell_securities]
    if len(open_sell_securities)>0:
        for stock in open_sell_securities:
            order_target_value(stock, 0)
    g.open_sell_securities = [s for s in g.open_sell_securities if s in context.portfolio.positions.keys()]
    return

## 风控
def risk_management(context):
    ### _风控函数筛选-开始 ###
    ### _风控函数筛选-结束 ###
    return

## 股票筛选
def check_stocks(context):
    if g.check_stocks_days%g.check_stocks_refresh_rate != 0:
        # 计数器加一
        g.check_stocks_days += 1
        return
    # 股票池赋值
    g.check_out_lists = get_security_universe(context, g.security_universe_index, g.security_universe_user_securities)
    _probe_stage(context, 'universe', g.check_out_lists)  # PROBE
    # 行业过滤
    g.check_out_lists = industry_filter(context, g.check_out_lists, g.industry_list)
    _probe_stage(context, 'industry', g.check_out_lists)  # PROBE
    # 概念过滤
    g.check_out_lists = concept_filter(context, g.check_out_lists, g.concept_list)
    _probe_stage(context, 'concept', g.check_out_lists)  # PROBE
    # 过滤ST股票
    g.check_out_lists = st_filter(context, g.check_out_lists)
    _probe_stage(context, 'st', g.check_out_lists)  # PROBE
    # 过滤退市股票
    g.check_out_lists = delisted_filter(context, g.check_out_lists)
    _probe_stage(context, 'delisted', g.check_out_lists)  # PROBE
    # 财务筛选
    g.check_out_lists = financial_statements_filter(context, g.check_out_lists)
    _probe_stage(context, 'pe', g.check_out_lists)  # PROBE
    # 行情筛选
    g.check_out_lists = situation_filter(context, g.check_out_lists)
    _probe_stage(context, 'situation', g.check_out_lists)  # PROBE
    # 技术指标筛选
    g.check_out_lists = technical_indicators_filter(context, g.check_out_lists)
    _probe_stage(context, 'technical', g.check_out_lists)  # PROBE
    # 形态指标筛选函数
    g.check_out_lists = pattern_recognition_filter(context, g.check_out_lists)
    _probe_stage(context, 'pattern', g.check_out_lists)  # PROBE
    # 其他筛选函数
    g.check_out_lists = other_func_filter(context, g.check_out_lists)
    _probe_stage(context, 'other', g.check_out_lists)  # PROBE

    # 排序
    input_dict = get_check_stocks_sort_input_dict()
    g.check_out_lists = check_stocks_sort(context,g.check_out_lists,input_dict,g.check_out_lists_ascending)
    _probe_stage(context, 'sort', g.check_out_lists)  # PROBE

    # 计数器归一
    g.check_stocks_days = 1
    return

## 交易函数
def trade(context):
   # 初始化买入列表
    buy_lists = []

    # 买入股票筛选
    if g.buy_trade_days%g.buy_refresh_rate == 0:
        # 获取 buy_lists 列表
        buy_lists = g.check_out_lists
        _probe_stage(context, 'b_in', buy_lists)  # PROBE
        # 过滤ST股票
        buy_lists = st_filter(context, buy_lists)
        _probe_stage(context, 'b_st', buy_lists)  # PROBE
        # 过滤停牌股票
        buy_lists = paused_filter(context, buy_lists)
        _probe_stage(context, 'b_paused', buy_lists)  # PROBE
        # 过滤退市股票
        buy_lists = delisted_filter(context, buy_lists)
        _probe_stage(context, 'b_delisted', buy_lists)  # PROBE
        # 过滤涨停股票
        buy_lists = high_limit_filter(context, buy_lists)
        _probe_stage(context, 'b_highlimit', buy_lists)  # PROBE
        _probe_atr(context, buy_lists, 'ATRU')  # PROBE

        ### _入场函数筛选-开始 ###
        buy_lists = [security for security in buy_lists if ATR_judge_xiaoyu(security, 0.15, 14)]
        _probe_stage(context, 'b_atr', buy_lists)  # PROBE
        _probe_order(context, buy_lists)  # PROBE
        ### _入场函数筛选-结束 ###

    # 卖出操作
    if g.sell_trade_days%g.sell_refresh_rate != 0:
        # 计数器加一
        g.sell_trade_days += 1
    else:
        # 卖出股票
        sell(context, buy_lists)
        # 计数器归一
        g.sell_trade_days = 1


    # 买入操作
    if g.buy_trade_days%g.buy_refresh_rate != 0:
        # 计数器加一
        g.buy_trade_days += 1
    else:
        # 卖出股票
        buy(context, buy_lists)
        # 计数器归一
        g.buy_trade_days = 1

## 卖出股票日期计数
def selled_security_list_count(context):
    g.daily_risk_management = True
    if len(g.selled_security_list)>0:
        for stock in g.selled_security_list.keys():
            g.selled_security_list[stock] += 1

##################################  选股函数群 ##################################

## 财务指标筛选函数
def financial_statements_filter(context, security_list):
    ### _财务指标筛选函数-开始 ###
    security_list = financial_data_filter_qujian(security_list, valuation.pe_ratio, (6,11))
    ### _财务指标筛选函数-结束 ###

    # 返回列表
    return security_list

## 行情筛选函数
def situation_filter(context, security_list):
    ### _行情筛选函数-开始 ###
    ### _行情筛选函数-结束 ###

    # 返回列表
    return security_list

## 技术指标筛选函数
def technical_indicators_filter(context, security_list):
    ### _技术指标筛选函数-开始 ###
    ### _技术指标筛选函数-结束 ###

    # 返回列表
    return security_list

## 形态指标筛选函数
def pattern_recognition_filter(context, security_list):
    ### _形态指标筛选函数-开始 ###
    ### _形态指标筛选函数-结束 ###

    # 返回列表
    return security_list

## 其他方式筛选函数
def other_func_filter(context, security_list):
    ### _其他方式筛选函数-开始 ###
    ### _其他方式筛选函数-结束 ###

    # 返回列表
    return security_list

# 获取选股排序的 input_dict
def get_check_stocks_sort_input_dict():
    input_dict = {
        }
    # 返回结果
    return input_dict

##################################  交易函数群 ##################################
# 交易函数 - 出场
def sell(context, buy_lists):
    # 获取 sell_lists 列表
    init_sl = context.portfolio.positions.keys()
    sell_lists = context.portfolio.positions.keys()

    # 判断是否卖出buy_lists中的股票
    if not g.sell_will_buy:
        sell_lists = [security for security in sell_lists if security not in buy_lists]
    
    ### _出场函数筛选-开始 ###
    _probe_atr(context, list(context.portfolio.positions.keys()), 'ATRH')  # PROBE
    sell_lists = [security for security in sell_lists if ATR_judge_dayu(security, 0.35, 14)]
    ### _出场函数筛选-结束 ###
    
    # 卖出股票
    if len(sell_lists)>0:
        for stock in sell_lists:
            sell_by_amount_or_percent_or_none(context,stock, g.sell_by_amount, g.sell_by_percent, g.open_sell_securities)
    
    # 获取卖出的股票, 并加入到 g.selled_security_list中
    selled_security_list_dict(context,init_sl)
    
    return

# 交易函数 - 入场
def buy(context, buy_lists):
    # 风控信号判断
    if not g.risk_management_signal:
        return
    
    # 判断当日是否触发风控清仓止损
    if not g.daily_risk_management:
        return
    # 判断是否可重复买入
    buy_lists = holded_filter(context,buy_lists)
    
    # 获取最终的 buy_lists 列表
    Num = g.max_hold_stocknum - len(context.portfolio.positions)
    buy_lists = buy_lists[:Num]
    log.info('BUYN date=%s num=%d codes=%s' % (context.current_dt.strftime('%Y-%m-%d'), Num, ','.join(buy_lists)))  # PROBE

    # 买入股票
    if len(buy_lists)>0:
        # 分配资金
        result = order_style(context,buy_lists,g.max_hold_stocknum, g.order_style_str, g.order_style_value)
        for stock in buy_lists:
            if len(context.portfolio.positions) < g.max_hold_stocknum:
                # 获取资金
                Cash = result[stock]
                # 判断个股最大持仓比重
                value = judge_security_max_proportion(context,stock,Cash,g.security_max_proportion)
                # 判断单只最大买入股数或金额
                amount = max_buy_value_or_amount(stock,value,g.max_buy_value,g.max_buy_amount)
                # 下单
                order(stock, amount, MarketOrderStyle())
    return

###################################  公用函数群 ##################################
## 排序
def check_stocks_sort(context,security_list,input_dict,ascending='desc'):
    if (len(security_list) == 0) or (len(input_dict) == 0):
        return security_list
    else:
        # 生成 key 的 list
        idk = list(input_dict.keys())
        # 生成矩阵
        a = pd.DataFrame()
        for i in idk:
            b = get_sort_dataframe(security_list, i, input_dict[i])
            a = pd.concat([a,b],axis = 1)
        # 生成 score 列
        a['score'] = a.sum(1,False)
        # 根据 score 排序
        if ascending == 'asc':# 升序
            a = a.sort(['score'],ascending = True)
        elif ascending == 'desc':# 降序
            a = a.sort(['score'],ascending = False)
        # 返回结果
        return list(a.index)

## 过滤同一标的继上次卖出N天不再买入
def filter_n_tradeday_not_buy(security, n=0):
    try:
        if (security in g.selled_security_list.keys()) and (g.selled_security_list[security]<n):
            return False
        return True
    except:
        return True

## 是否可重复买入
def holded_filter(context,security_list):
    if not g.filter_holded:
        security_list = [stock for stock in security_list if stock not in context.portfolio.positions.keys()]
    # 返回结果
    return security_list

## 卖出股票加入dict
def selled_security_list_dict(context,security_list):
    selled_sl = [s for s in security_list if s not in context.portfolio.positions.keys()]
    if len(selled_sl)>0:
        for stock in selled_sl:
            g.selled_security_list[stock] = 0

## 过滤停牌股票
def paused_filter(context, security_list):
    if g.filter_paused:
        current_data = get_current_data()
        security_list = [stock for stock in security_list if not current_data[stock].paused]
    # 返回结果
    return security_list

## 过滤退市股票
def delisted_filter(context, security_list):
    if g.filter_delisted:
        current_data = get_current_data()
        security_list = [stock for stock in security_list if not (('退' in current_data[stock].name) or ('*' in current_data[stock].name))]
    # 返回结果
    return security_list


## 过滤ST股票
def st_filter(context, security_list):
    if g.only_st:
        current_data = get_current_data()
        security_list = [stock for stock in security_list if current_data[stock].is_st]
    else:
        if g.filter_st:
            current_data = get_current_data()
            security_list = [stock for stock in security_list if not current_data[stock].is_st]
    # 返回结果
    return security_list

# 过滤涨停股票
def high_limit_filter(context, security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not (current_data[stock].day_open >= current_data[stock].high_limit)]
    # 返回结果
    return security_list

# 获取股票股票池
def get_security_universe(context, security_universe_index, security_universe_user_securities):
    temp_index = []
    for s in security_universe_index:
        if s == 'all_a_securities':
            temp_index += list(get_all_securities(['stock'], context.current_dt.date()).index)
        else:
            temp_index += get_index_stocks(s)
    for x in security_universe_user_securities:
        temp_index += x
    return  sorted(list(set(temp_index)))

# 行业过滤
def industry_filter(context, security_list, industry_list):
    if len(industry_list) == 0:
        # 返回股票列表
        return security_list
    else:
        securities = []
        for s in industry_list:
            temp_securities = get_industry_stocks(s)
            securities += temp_securities
        security_list = [stock for stock in security_list if stock in securities]
        # 返回股票列表
        return security_list

# 概念过滤
def concept_filter(context, security_list, concept_list):
    if len(concept_list) == 0:
        return security_list
    else:
        securities = []
        for s in concept_list:
            temp_securities = get_concept_stocks(s)
            securities += temp_securities
        security_list = [stock for stock in security_list if stock in securities]
        # 返回股票列表
        return security_list

#自定义函数

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


# ===== PROBE u-2 helpers (logging only; read-only data calls, no state used by the strategy) =====
_PROBE_FULL_DATES = ['2024-11-04']
_PROBE = {'first': None, 'open0': None}

def _probe_d(context):
    return context.current_dt.strftime('%Y-%m-%d')

def _probe_full(context):
    d = _probe_d(context)
    if _PROBE['first'] is None:
        _PROBE['first'] = d
    return d == _PROBE['first'] or d in _PROBE_FULL_DATES

def _probe_chunks(tag, d, lst):
    lst = list(lst)
    for i in range(0, len(lst), 40):
        log.info('%s date=%s part=%d codes=%s' % (tag, d, i // 40, ','.join(lst[i:i + 40])))

def _probe_pe(lst):
    try:
        if len(lst) == 0:
            return {}
        df = get_fundamentals(query(valuation.code, valuation.pe_ratio).filter(valuation.code.in_(list(lst))))
        return dict(zip(df['code'], df['pe_ratio']))
    except Exception as e:
        log.info('PROBEERR pe %s' % e)
        return {}

def _probe_stage(context, stage, lst):
    d = _probe_d(context)
    lst = list(lst)
    nsz = len([c for c in lst if c.endswith('.XSHE')])
    log.info('CNT date=%s stage=%s n=%d sz=%d' % (d, stage, len(lst), nsz))
    if _probe_full(context) or (stage not in ('universe', 'industry', 'concept', 'st', 'delisted') and len(lst) <= 120):
        _probe_chunks('LIST stage=%s' % stage, d, lst)
    if stage == 'delisted' and _probe_full(context):
        pe = _probe_pe(lst)
        items = ['%s:%s' % (c, ('%.2f' % pe[c]) if (c in pe and pe[c] is not None) else 'NA') for c in lst]
        _probe_chunks('PEU', d, items)

def _probe_atr(context, lst, tag):
    d = _probe_d(context)
    lst = list(lst)
    pe = _probe_pe(lst)
    for c in lst:
        try:
            h = attribute_history(c, 60, '1d', ['high', 'low', 'close'])
            hi = np.array(h['high'].values, dtype=float)
            lo = np.array(h['low'].values, dtype=float)
            cl = np.array(h['close'].values, dtype=float)
            a15 = talib.ATR(hi[-15:], lo[-15:], cl[-15:], 14)[-1]
            a60 = talib.ATR(hi, lo, cl, 14)[-1]
            close = cl[-1]
            x = ATR_judge_xiaoyu(c, 0.15, 14)
            y = ATR_judge_dayu(c, 0.35, 14)
            pv = pe.get(c)
            log.info('%s date=%s code=%s close=%.4f atr15=%.5f atr60=%.5f rel15=%.5f rel60=%.5f pe=%s xiaoyu=%s dayu=%s nb=%d' % (
                tag, d, c, close, a15, a60, a15 / close, a60 / close,
                ('%.3f' % pv) if pv is not None else 'NA', x, y, len(cl)))
        except Exception as e:
            log.info('PROBEERR atr %s %s %s' % (tag, c, e))

def _probe_order(context, lst):
    d = _probe_d(context)
    lst = list(lst)
    log.info('ORDER date=%s n=%d codes=%s' % (d, len(lst), ','.join(lst[:15])))
    if _PROBE['open0'] is None:
        _PROBE['open0'] = lst
        cd = get_current_data()
        for c in lst:
            try:
                log.info('OPEN0 date=%s code=%s open=%.4f' % (d, c, cd[c].day_open))
            except Exception as e:
                log.info('PROBEERR open0 %s %s' % (c, e))

def _probe_final(context):
    d = _probe_d(context)
    end = None
    try:
        end = context.run_params.end_date
        end = end.strftime('%Y-%m-%d') if hasattr(end, 'strftime') else str(end)[:10]
    except Exception:
        end = '2024-12-31'
    if d != end:
        return
    names = list(_PROBE['open0'] or []) + list(context.portfolio.positions.keys())
    seen = set()
    for c in names:
        if c in seen:
            continue
        seen.add(c)
        try:
            h = attribute_history(c, 1, '1d', ['close'])
            lp = get_current_data()[c].last_price
            log.info('CLOSEN date=%s code=%s ah_close=%.4f ah_date=%s last_price=%.4f held=%s' % (
                d, c, float(h['close'].values[-1]), str(h.index[-1])[:10], lp, c in context.portfolio.positions))
        except Exception as e:
            log.info('PROBEERR closen %s %s' % (c, e))
