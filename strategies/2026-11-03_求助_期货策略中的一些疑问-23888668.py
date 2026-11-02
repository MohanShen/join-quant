# Clone from JoinQuant
# postId: 23888668e147fe1901fd45b5a9998e81
# backtestId: 6687c2500330ead9c9a8e71a6f63c363
# title: 【求助】期货策略中的一些疑问

# 导入函数库
from jqdata import *

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
    run_daily( market_open, time='9:30', reference_security='IF8888.CCFX')


## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    ## 获取要操作的股票(g.为全局变量)
      # 获取当期可交易期货合约
    g.PVC_current = get_future_contracts('V')[1]
    g.JM_current =get_future_contracts('JM')[1]
    g.JT_current = get_future_contracts('J')[1]

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))

    ## 交易

    # 当月合约
    PVC='V9999.XDCE'
    JT='J9999.XDCE'
    JM='JM9999.XDCE'
  
  
    PVC_close = get_price(PVC,start_date='2016-01-01', end_date=context.current_dt.date(), frequency='daily', fields=['close'])
    JT_close = get_price(JT,start_date='2016-01-01', end_date=context.current_dt.date(), frequency='daily', fields=['close'])
    JM_close = get_price(JM,start_date='2016-01-01', end_date=context.current_dt.date(), frequency='daily', fields=['close'])
    diff_price=JM_close-0.6468*PVC_close+0.2048*JT_close
    los=1.75 #止损系数
    ope=0.8 #开仓系数
    ear=0.05 #止盈系数
    diff=diff_price[:-1]
    prev=diff_price.iloc[len(diff_price)-1,0]
    upp=diff.describe().loc['mean','close']+ope*diff.describe().loc['std','close']
    low=diff.describe().loc['mean','close']-ope*diff.describe().loc['std','close']
    stopup=diff.describe().loc['mean','close']+los*diff.describe().loc['std','close']
    stoplow=diff.describe().loc['mean','close']-los*diff.describe().loc['std','close']
    z1=diff.describe().loc['mean','close']+ear*diff.describe().loc['std','close']
    z2=diff.describe().loc['mean','close']-ear*diff.describe().loc['std','close']



    # 判断差值大于upp，且空仓
    if (prev > upp):
        if (len(context.portfolio.short_positions) == 0) and (len(context.portfolio.long_positions) == 0):
            log.info('开仓---差值：', prev)
            # 做空
            order(g.JM_current, 10, side='short')
            order(g.JT_current, 2, side='short')
            # 做多
            order(g.PVC_current, 6, side='long')
    # 如有持仓，并且基差缩小至z1内，则平仓
    if (prev < z1):
        if(len(context.portfolio.short_positions) > 0) and (len(context.portfolio.long_positions) > 0):
            log.info('平仓---差值：', prev)
            # 平仓
            order_target(g.JM_current, 0, side='short')
            order_target(g.JT_current, 0, side='short')
            order_target(g.PVC_current, 0, side='long')
    #有持仓并触及平仓线，平仓    
    if (prev > stopup): 
        if(len(context.portfolio.short_positions) > 0) and (len(context.portfolio.long_positions) > 0):
            log.info('平仓---差值：', prev)
            # 平仓
            order_target(g.JM_current, 0, side='short')
            order_target(g.JT_current, 0, side='short')
            order_target(g.PVC_current, 0, side='long')
   
   # 判断差值小于ulow，且空仓
    if (prev < low):
        if (len(context.portfolio.short_positions) == 0) and (len(context.portfolio.long_positions) == 0):
            log.info('开仓---差值：', prev)
            # 做空
            order(g.JM_current, 10, side='long')
            order(g.JT_current, 2, side='long')
            # 做多
            order(g.PVC_current, 6, side='short')
    # 如有持仓，并且基差缩小至z2内，则平仓
    if (prev > z2):
        if(len(context.portfolio.short_positions) > 0) and (len(context.portfolio.long_positions) > 0):
            log.info('平仓---差值：', prev)
            # 平仓
            order_target(g.JM_current, 0, side='long')
            order_target(g.JT_current, 0, side='long')
            order_target(g.PVC_current, 0, side='short')
    #有持仓并触及平仓线，平仓    
    if (prev < stoplow): 
        if(len(context.portfolio.short_positions) > 0) and (len(context.portfolio.long_positions) > 0):
            log.info('平仓---差值：', prev)
            # 平仓
            order_target(g.JM_current, 0, side='long')
            order_target(g.JT_current, 0, side='long')
            order_target(g.PVC_current, 0, side='short')


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
