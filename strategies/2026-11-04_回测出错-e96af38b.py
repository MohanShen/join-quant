# Clone from JoinQuant
# postId: e96af38bbc39941a324251e5e77c6a28
# backtestId: d85b286f9d1c3497f8cbd1b765633920
# title: 回测出错

# 导入函数库
from jqdata import *
from datetime import datetime,timedelta
## 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    context.sanyinzi=False
    context.zhouneixiaoying=0
    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)

    # 设置期货交易的滑点
    set_slippage(StepRelatedSlippage(2))
    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF8888.CCFX'或'IH1602.CCFX'是一样的）
    # 注意：before_open/open/close/after_close等相对时间不可用于有夜盘的交易品种，有夜盘的交易品种请指定绝对时间（如9：30）
      # 开盘前运行
    run_daily( before_market_open, time='09:00', reference_security='IF8888.CCFX')
      # 开盘时运行
    run_daily( market_open, time='09:30', reference_security='IF8888.CCFX')
      # 收盘后运行
    run_daily( after_market_close, time='15:30', reference_security='IF8888.CCFX')

    run_daily( buy_1459, time='14:59', reference_security='IF8888.CCFX')
    run_daily( sell_1000, time='10:00', reference_security='IF8888.CCFX')

def buy_1459(context):
    # 当月合约\
    if len(context.portfolio.short_positions)>0:
        order_target(get_dominant_future('IF'), 0,side='short')
    if len(context.portfolio.long_positions)>0:
        return
    IF_current_month = g.IF_current_month
    day=str(context.current_dt)[0:10]

    next_trade_day=str(get_trade_days(start_date=day, end_date=None, count=None).tolist()[1])
    next_day=str(context.current_dt + timedelta(days=1))
    pre_trade_day=str(get_trade_days(end_date=day, count=2).tolist()[0])
    
    summ=0
    #收盘折溢价
    temp=get_bars(IF_current_month, 59, unit='1m',fields=['date','money','volume','close'],
          include_now=True, end_dt=day+' 14:59:00', fq_ref_date=None,df=True)
    sum_money=sum(temp['money'])
    sum_volume=sum(temp['volume'])
    if sum_volume==0:
        shoupanzheyijia=False
    else:
        shoupanzheyijia=(sum_money/(sum_volume*300)-temp.iloc[-1]['close'])>0
    if shoupanzheyijia:
        summ=summ+1
    #买卖单不平衡度
    temp=get_ticks(IF_current_month,start_dt=day+' 14:30:00',end_dt=context.current_dt, 
    fields=['time', 'current', 'volume','money','a1_v','b1_v'],
    count=None, skip=True, df=True)
    #print(temp)
    #买量
    b=sum(temp['b1_v'])
    #卖量
    s=sum(temp['a1_v'])
    if (b+s)==0:
        bs1429_1459=False
    else:
        bs1429_1459=((b-s)/((s+b)/2))>0
    if bs1429_1459:
        summ=summ+1
    #基差变化率
    hs_df1445=get_bars('000300.XSHG', 1, unit='1m',fields=['date','open','close'],
          include_now=True, end_dt=day+' 14:45:00', fq_ref_date=None,df=True)
    
    if_df1445=get_bars(IF_current_month, 1, unit='1m',fields=['date','open','close'],
          include_now=True, end_dt=day+' 14:45:00', fq_ref_date=None,df=True)
    
    hs_df1459=get_bars('000300.XSHG', 1, unit='1m',fields=['date','open','close'],
          include_now=True, end_dt=day+' 14:59:00', fq_ref_date=None,df=True)
    
    if_df1459=get_bars(IF_current_month, 1, unit='1m',fields=['date','open','close'],
          include_now=True, end_dt=day+' 14:59:00', fq_ref_date=None,df=True)
    
    cha_1445=if_df1445['close'][0]-hs_df1445['close'][0]
    cha_1459=if_df1459['close'][0]-hs_df1459['close'][0]
    if cha_1459<cha_1445:
        jicha=True
    else:
        jicha=False
    if jicha:
        summ=summ+1
    context.sanyinzi=False
    if summ>=2:
        context.sanyinzi=True
    context.zhouneixiaoying=0
    #尾盘涨幅
    if_df1444_1459=get_bars(IF_current_month, 14, unit='1m',fields=['date','open','close'],
          include_now=True, end_dt=day+' 14:59:00', fq_ref_date=None,df=True)
    last_15min_ch=if_df1444_1459.iloc[-1]['close']>if_df1444_1459.iloc[0]['close']
    df_1459=get_bars('000300.XSHG', 1, unit='1m',fields=['date','open','close'],
          include_now=True, end_dt=day+' 14:59:00', fq_ref_date=None,df=True)
    df_preday=get_bars('000300.XSHG', 1, unit='1m',fields=['date','open','close'],
          include_now=True, end_dt=pre_trade_day+' 09:31:00', fq_ref_date=None,df=True)
    long_market=df_1459.iloc[0]['close']>df_preday.iloc[0]['open']
    def getweekday(day):
        return datetime.strptime(day, '%Y-%m-%d').weekday()+1
    next_trade_day_weekday=getweekday(next_trade_day)
    #print(next_trade_day,next_trade_day_weekday)
    if long_market:
        if next_trade_day_weekday==1 or next_trade_day_weekday==5:
            context.zhouneixiaoying=1
        elif next_trade_day_weekday==2 or next_trade_day_weekday==3:
            context.zhouneixiaoying=-1
    else:
        if next_trade_day_weekday==2 or next_trade_day_weekday==3:
            context.zhouneixiaoying=1
        elif next_trade_day_weekday==1 or next_trade_day_weekday==4:
            context.zhouneixiaoying=-1
    print(context.zhouneixiaoying,context.sanyinzi)        
    if context.zhouneixiaoying==1 or context.sanyinzi:
        order(get_dominant_future('IF'), 3)
        #print(context.portfolio.long_positions)
def sell_1000(context):
    print(context.zhouneixiaoying)
    IF_current_month = g.IF_current_month
    if len(context.portfolio.long_positions)>0:
        if context.zhouneixiaoying==-1:
            order_target(get_dominant_future('IF'), 0,side='long')
            order(get_dominant_future('IF'), 3,side='short')
        elif context.zhouneixiaoying==0:
            order_target(get_dominant_future('IF'), 0,side='long')
    else:
        if context.zhouneixiaoying==1:
            order(get_dominant_future('IF'), 3,side='long')
        elif context.zhouneixiaoying==-1:
            order(get_dominant_future('IF'), 3,side='short')
## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    ## 获取要操作的股票(g.为全局变量)
      # 获取当月沪深300指数期货合约
    g.IF_current_month = get_future_contracts('IF')[0]
      # 获取下季沪深300指数期货合约
    g.IF_next_quarter = get_future_contracts('IF')[2]

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))

    ## 交易

    # 当月合约
    IF_current_month = g.IF_current_month
    # 下季合约
    IF_next_quarter = g.IF_next_quarter
'''
    # 合约列表
    # 当月合约价格
    IF_current_month_close = get_bars(IF_current_month, count=1, unit='1d', fields=['close'])["close"]
    # 下季合约价格
    # IF_next_quarter_close = hist[IF_next_quarter][0]
    IF_next_quarter_close = get_bars(IF_next_quarter, count=1, unit='1d', fields=['close'])["close"]
    print(IF_current_month_close)
    print(IF_next_quarter_close)
    # 计算差值
    CZ = IF_current_month_close - IF_next_quarter_close

    # 获取当月合约交割日期
    end_data = get_CCFX_end_date(IF_current_month)

    # 判断差值大于80，且空仓，则做空当月合约、做多下季合约；当月合约交割日当天不开仓
    if (CZ > 80):
        if (context.current_dt.date() == end_data):
            # return
            pass
        else:
            if (len(context.portfolio.short_positions) == 0) and (len(context.portfolio.long_positions) == 0):
                log.info('开仓---差值：', CZ)
                # 做空1手当月合约
                order(IF_current_month, 1, side='short')
                # 做多1手下季合约
                order(IF_next_quarter, 1, side='long')
    # 如有持仓，并且基差缩小至70内，则平仓
    if (CZ < 70):
        if(len(context.portfolio.short_positions) > 0) and (len(context.portfolio.long_positions) > 0):
            log.info('平仓---差值：', CZ)
            # 平仓当月合约
            order_target(IF_current_month, 0, side='short')
            # 平仓下季合约
            order_target(IF_next_quarter, 0, side='long')
'''
## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # 得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')

########################## 获取期货合约信息，请保留 #################################
# 获取金融期货合约到期日
def get_CCFX_end_date(future_code):
    # 获取金融期货合约到期日
    return get_security_info(future_code).end_date


########################## 自动移仓换月函数 #################################
def position_auto_switch(context,pindex=0,switch_func=None, callback=None):
    """
    期货自动移仓换月。默认使用市价单进行开平仓。
    :param context: 上下文对象
    :param pindex: 子仓对象
    :param switch_func: 用户自定义的移仓换月函数.
        函数原型必须满足：func(context, pindex, previous_dominant_future_position, current_dominant_future_symbol)
    :param callback: 移仓换月完成后的回调函数。
        函数原型必须满足：func(context, pindex, previous_dominant_future_position, current_dominant_future_symbol)
    :return: 发生移仓换月的标的。类型为列表。
    """
    import re
    subportfolio = context.subportfolios[pindex]
    symbols = set(subportfolio.long_positions.keys()) | set(subportfolio.short_positions.keys())
    switch_result = []
    for symbol in symbols:
        match = re.match(r"(?P<underlying_symbol>[A-Z]{1,})", symbol)
        if not match:
            raise ValueError("未知期货标的：{}".format(symbol))
        else:
            dominant = get_dominant_future(match.groupdict()["underlying_symbol"])
            cur = get_current_data()
            symbol_last_price = cur[symbol].last_price
            dominant_last_price = cur[dominant].last_price
            if dominant > symbol:
                for p in (subportfolio.long_positions.get(symbol, None), subportfolio.short_positions.get(symbol, None)):
                    if p is None:
                        continue
                    if switch_func is not None:
                        switch_func(context, pindex, p, dominant)
                    else:
                        amount = p.total_amount
                        # 跌停不能开空和平多，涨停不能开多和平空。
                        if p.side == "long":
                            symbol_low_limit = cur[symbol].low_limit
                            dominant_high_limit = cur[dominant].high_limit
                            if symbol_last_price <= symbol_low_limit:
                                log.warning("标的{}跌停，无法平仓。移仓换月取消。".format(symbol))
                                continue
                            elif dominant_last_price >= dominant_high_limit:
                                log.warning("标的{}涨停，无法开仓。移仓换月取消。".format(symbol))
                                continue
                            else:
                                log.info("进行移仓换月：({0},long) -> ({1},long)".format(symbol, dominant))
                                order_target(symbol,0,side='long')
                                order_target(dominant,amount,side='long')
                                switch_result.append({"before": symbol, "after":dominant, "side": "long"})
                            if callback:
                                callback(context, pindex, p, dominant)
                        if p.side == "short":
                            symbol_high_limit = cur[symbol].high_limit
                            dominant_low_limit = cur[dominant].low_limit
                            if symbol_last_price >= symbol_high_limit:
                                log.warning("标的{}涨停，无法平仓。移仓换月取消。".format(symbol))
                                continue
                            elif dominant_last_price <= dominant_low_limit:
                                log.warning("标的{}跌停，无法开仓。移仓换月取消。".format(symbol))
                                continue
                            else:
                                log.info("进行移仓换月：({0},short) -> ({1},short)".format(symbol, dominant))
                                order_target(symbol,0,side='short')
                                order_target(dominant,amount,side='short')
                                switch_result.append({"before": symbol, "after": dominant, "side": "short"})
                                if callback:
                                    callback(context, pindex, p, dominant)
    return switch_result
