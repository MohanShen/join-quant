# Clone from JoinQuant
# postId: f8ab6f9df5787773fad0a39b5edcede4
# backtestId: d8cbc42e18244ac3a68ff2f31712751f
# title: 关于下单时常被不明原因取消的问题，想请教

# Inspired from: https://www.joinquant.com/post/1401
# 标题：Turtle Strategy that monitors multiple stocks
# 作者：Michael Hsia

import pandas as pd

class TurtleSystemManager():
    def __init__(self, short_in_date=20, short_out_date=10, long_in_date=55, long_out_date=20):
        self.system = [
            TurtleSystem(short_in_date, short_out_date, True), 
            TurtleSystem(long_in_date, long_out_date, False)
        ]
        
    def update_turtle_params(self, context):
        for pindex in range(len(context.subportfolios)):
            total_value = context.subportfolios[pindex].total_value
            for symbol in context.subportfolios[pindex].long_positions.keys():
                self.system[pindex].update_turtle_params_by_symbol(symbol, total_value)
            
    def start_running(self, context, symbol, current_price):
        for pindex in range(len(context.subportfolios)):
            cash = context.subportfolios[pindex].available_cash
            total_value = context.subportfolios[pindex].total_value
            # log.warning('[System {}] - Cash: {}'.format(pindex, cash))
            
            if symbol not in context.subportfolios[pindex].long_positions.keys():
                donchian_high_price = max(attribute_history(symbol, self.system[pindex].in_date, '1d', ('high', 'close'))['high'])
                # log.warning('[System {}] - [{}] Current/High Price: {}/{}'.format(pindex, symbol, current_price, donchian_high_price))
                self.system[pindex].update_turtle_params_by_symbol(symbol, total_value)
                # TODO
                # Improved the performance by adding a further filter, namely that the 40-day moving average is greater than the 200-day moving average
                if current_price > donchian_high_price:
                    self.system[pindex].market_in(
                        symbol,
                        pindex
                    )
            else:
                stop_loss_price = context.subportfolios[pindex].long_positions[symbol].acc_avg_cost
                avg_cost = context.subportfolios[pindex].long_positions[symbol].acc_avg_cost
                position = context.subportfolios[pindex].long_positions[symbol].closeable_amount
                previous_purchased_price = self.system[pindex].get_previous_purchased_price_by_symbol(symbol)
                system_N = self.system[pindex].get_N_from_turtle_params_by_symbol(symbol)
                donchian_low_price = min(attribute_history(symbol, self.system[pindex].out_date, '1d', ('low', 'close'))['low'])
                if current_price >= (previous_purchased_price + 0.5 * system_N):
                    # 每上涨0.5N，加仓一个单元  
                    self.system[pindex].market_add(
                        symbol,
                        pindex
                    )

                if current_price < donchian_low_price:
                    # 若当前价格低于前out_date天的收盘价的最小值, 则卖掉所有持仓
                    self.system[pindex].market_out(
                        symbol, 
                        position,
                        pindex
                    )
                    if current_price >= avg_cost:
                        self.system[pindex].previous_state_winning = True
                        log.debug('[System {}] - [{}] This trade is a winning trade'.format(pindex, symbol))
                    else:
                        self.system[pindex].previous_state_winning = False
                        log.debug('[System {}] - [{}] This trade is a losing trade'.format(pindex, symbol))

                    
                if (current_price - stop_loss_price) < (-2 * system_N):
                    self.system[pindex].market_stop_loss(
                        symbol,
                        position,
                        pindex
                    )
                    self.system[pindex].previous_state_winning = False
                    log.debug('[System {}] - [{}] This trade is a losing trade'.format(pindex, symbol))

    
class TurtleSystem():
    TURTLE_N = 'N'
    TURTLE_DOLLAR_VOLATILITY = 'DOLLAR_VOLATILITY'
    TURTLE_UNIT = 'UNIT'
    
    def __init__(self, in_date, out_date, ignore_state=False):
        self.in_date = in_date
        self.out_date = out_date
        self.ignore_state = ignore_state
        self.system_positions = {}
        self.turtle_params = {}
        self.previous_state_winning = False  # True: winning, False, lossing
        self.ignore_state = True
        self.dollars_per_share = 1           # dollars_per_share是标的股票每波动一个最小单位，1手股票的总价格变化量。
                                             # 在国内最小变化量是0.01元，所以就是0.01 × 100=1
        self.number_days = 20                # 计算N值的天数
        self.unit_limit = 4                  # 4 for the lnog direction
        
    def market_in(self, symbol, pindex):
        # System 1 breakout entry signals would be ignored if the last breakout would have resulted in a winning trade
        # All breakouts for System 2 would be taken whether the previous breakout had been a winner or not.
        if not self.ignore_state and self.previous_state_winning:
            # 假如是系统1，就要看之前的trade是win的话，本次就不进入市场了
            self.remove_turtle_params_by_symbol(symbol)
            log.debug("[System {}] - [{}] Exit as previous trade is win trade".format(pindex, symbol))
            return
        
        log.info("[System {}] - [{}] - 入仓".format(pindex, symbol))
        self.add_position_by_symbol(
            symbol, 
            pindex
        )

    def market_add(self, symbol, pindex):
        log.info("[System {}] - [{}] - 加仓".format(pindex, symbol))
        self.add_position_by_symbol(symbol, pindex)

    def market_out(self, symbol, position, pindex):
        log.info("[System {}] - [{}] - 减仓".format(pindex, symbol))
        self.reduce_position_by_symbol(
            symbol, 
            position,
            False,
            pindex
        )

    def market_stop_loss(self, symbol, position, pindex):
        log.debug('[System {}] - [{}] 开始止损'.format(pindex, symbol))
        
        self.reduce_position_by_symbol(
            symbol, 
            position,
            True,
            pindex
        )
        
    def add_position_by_symbol(self, symbol, pindex):
        if self.system_positions.get(symbol, None) == None:
            self.system_positions[symbol] = {}
            self.system_positions[symbol]['unit'] = 0
            self.system_positions[symbol]['previous_purchased_price'] = 0
        
        if self.system_positions[symbol]['unit'] >= self.unit_limit:
            log.debug('[System {}] - [{}] reaching unit limit: {}/{}'.format(
                pindex,
                symbol, 
                self.system_positions[symbol]['unit'],
                self.unit_limit
            ))
            return
        
        position = self.get_unit_from_turtle_params_by_symbol(symbol)
        
        # res = order(symbol, position, style=MarketOrderStyle(), pindex=pindex)
        res = order(symbol, position, pindex=pindex)
        
        if res is not None:
            if res.status not in [OrderStatus.canceled, OrderStatus.rejected]:
                self.system_positions[symbol]['unit'] += 1
                self.system_positions[symbol]['previous_purchased_price'] = res.price
            else:
                log.warning('[System {}] - [{}] order failed: {}.'.format(pindex, symbol, res))
        else:
            log.warning('[System {}] - [{}] order failed.'.format(pindex, symbol))

    def reduce_position_by_symbol(self, symbol, position, stop_loss_flag, pindex):
        if self.system_positions.get(symbol, None) == None:
            log.warning('Reduce position failed. It does not exist')
            return

        # res = order_target(symbol, 0, style=LimitOrderStyle(current_price), pindex=pindex)
        res = order(symbol, -position, style=MarketOrderStyle(), pindex=pindex)

        if res is not None:
            self.system_positions[symbol]['unit'] = 0
            self.remove_position_by_symbol_if_empty(symbol)        
        # if res is not None:
        #     if stop_loss_flag:
        #         self.system_positions[symbol]['unit'] = 0
        #         self.remove_position_by_symbol_if_empty(symbol)
        #     else:
        #         self.system_positions[symbol]['unit'] -= 1
        #         self.remove_position_by_symbol_if_empty(symbol)
        else:
            log.debug('[System {}] - [{}] Order Failed.'.format(pindex, symbol))
        
    def remove_position_by_symbol_if_empty(self, symbol):
        if self.system_positions.get(symbol, None) == None:
            return True
        
        # if (self.system_positions[symbol]['position'] == 0) or (self.system_positions[symbol]['unit'] == 0):
        if self.system_positions[symbol]['unit'] == 0:
            self.system_positions.pop(symbol)
            self.remove_turtle_params_by_symbol(symbol)
            return True

        log.warning('Unit of [{}] is not empty'.format(symbol))
        return False
        
    def get_previous_purchased_price_by_symbol(self, symbol):
        if self.system_positions.get(symbol, None) is None:
            raise Exception(' [{}] - System position param does not exist'.format(symbol))
            # log.warning('N of [{}] does not exist'.format(symbol))
            # return None
        if self.system_positions[symbol].get('previous_purchased_price', None) is None:
            raise Exception('[{}] - N does not exist'.format(symbol))
            # log.warning('N of [{}] does not exist'.format(symbol))
            # return None
        return self.system_positions[symbol]['previous_purchased_price']
            
    def update_turtle_params_by_symbol(self, symbol, account_value):
        if not self.is_turtle_params_existed_by_symbol(symbol):
            self.turtle_params[symbol] = {}

        df = attribute_history(
            count=self.number_days + 1, 
            unit='1d',
            fields=['low', 'close', 'high'], 
            security=symbol, 
            df=True
        )
        
        df['pdc'] = df['close'].shift(1)
        df['h_l'] = (df['high'] - df['low']).abs()
        df['h_pdc'] = (df['high'] - df['pdc']).abs()
        df['pdc_l'] = (df['pdc'] - df['low']).abs()
        N = df[['h_l', 'h_pdc', 'pdc_l']].max(axis=1)[1:].mean()
        del df
        
        # 若损失率大于g.loss_rate，则调整（减小）可持有现金和总价值
        # if value < (1 - g.loss_rate) * starting_cash:
        #     cash *= g.adjust_rate
        #     value *= g.adjust_rate
        
        self.turtle_params[symbol][self.TURTLE_N] = N
        self.turtle_params[symbol][self.TURTLE_DOLLAR_VOLATILITY] = self.dollars_per_share * self.turtle_params[symbol][self.TURTLE_N]
        self.turtle_params[symbol][self.TURTLE_UNIT] = (account_value * 0.01) / self.turtle_params[symbol][self.TURTLE_DOLLAR_VOLATILITY]
        
        return True
        
    def get_N_from_turtle_params_by_symbol(self, symbol):
        if not self.is_turtle_params_existed_by_symbol(symbol):
            raise Exception('N of [{}] does not exist'.format(symbol))
            # log.warning('N of [{}] does not exist'.format(symbol))
            # return False
        if self.turtle_params[symbol].get(self.TURTLE_N, None) is None:
            raise Exception('N of [{}] does not exist'.format(symbol))
            # log.warning('N of [{}] does not exist'.format(symbol))
            # return False
        return self.turtle_params[symbol][self.TURTLE_N]
    
    def get_unit_from_turtle_params_by_symbol(self, symbol):
        if not self.is_turtle_params_existed_by_symbol(symbol):
            raise Exception('N of [{}] does not exist'.format(symbol))
            # log.warning('N of [{}] does not exist'.format(symbol))
            # return False
        
        return self.turtle_params[symbol][self.TURTLE_UNIT]
        
    def is_turtle_params_existed_by_symbol(self, symbol):
        if self.turtle_params.get(symbol, None) is None:
            return False
        else:
            return True
    
    def remove_turtle_params_by_symbol(self, symbol):
        if self.is_turtle_params_existed_by_symbol(symbol):
            self.turtle_params.pop(symbol)

'''
================================================================================
总体回测前
================================================================================
'''


#总体回测前要做的事情
def initialize(context):
    # set_benchmark('000300.XSHG')
    set_benchmark('601698.XSHG')
    set_params()        #1设置策参数

    set_option('use_real_price',True) #用真实价格交易
    set_option("avoid_future_data", True) #避免使用未来数据
    log.set_level('order','error') # 设置报错等级

    # Set up two separate systems:
    # subportfolios[0] is system 1 in the turtle strategy
    # and subportfolios[1] is the system 2
    set_subportfolios(
        [SubPortfolioConfig(cash=context.portfolio.starting_cash * g.ratio_system1, type='stock'), 
        SubPortfolioConfig(cash=context.portfolio.starting_cash * (1 - g.ratio_system1), type='stock')]
    )
    
    # 系统1入市的trailing date
    SHORT_IN_DATE = 20
    # 系统1 exiting market trailing date
    SHORT_OUT_DATE = 10
    # 系统2入市的trailing date
    LONG_IN_DATE = 55
    # 系统2 exiting market trailing date
    LONG_OUT_DATE = 20
    
    g.turtle = TurtleSystemManager(
        SHORT_IN_DATE, 
        SHORT_OUT_DATE, 
        LONG_IN_DATE, 
        LONG_OUT_DATE,
    )
    
#1
#设置策略参数
def set_params():
    # 可承受的最大损失率
    g.loss_rate = 0.2
    # 若超过最大损失率，则调整率为：
    g.adjust_rate = 0.9
    # 系统1所配金额占总金额比例
    g.ratio_system1 = 0.8
    # Capacity in portfolio
    g.capacity = 25
    


'''
================================================================================
每天开盘前
================================================================================
'''
#每天开盘前要做的事情
def before_trading_start(context):
    set_slip_fee(context) 
    set_tradable_stocks(context)
    g.turtle.update_turtle_params(context)


#4 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 

    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')


#5 From 300 SH, pick turnover_ratio top 3 from each sector
def set_tradable_stocks(context):
    # Test one scenario
    test = True
    
    stocks300SH = get_index_stocks(normalize_code('000300.sh'))
    stocks300SHDf = get_fundamentals(
        query(
            valuation, 
        ).filter(
            valuation.code.in_(stocks300SH), 
            valuation.turnover_ratio > 0
        ),
    )
    
    INDUSTRY_AUTH = 'jq_l1'
    # INDUSTRY_AUTH = 'zjw'
    ind = get_industry(security=stocks300SHDf['code'].tolist())
    try:
        stocks300SHDf['industry_name'] = [ind[x][INDUSTRY_AUTH]['industry_name'] for x in ind]
        stocks300SHDf['industry_code'] = [ind[x][INDUSTRY_AUTH]['industry_code'] for x in ind]
    except Exception as e:
        print(ind)
        raise Exception
    
    df = stocks300SHDf.sort_values(['turnover_ratio'], ascending=False)
    target_list = df.groupby(['industry_name']).head(4)
    g.security = target_list['code'].tolist()
    
    if test:
        g.security = ['601698.XSHG']
        # print(len(g.security))

'''
================================================================================
每天交易时
================================================================================
'''
# 按分钟回测
def handle_data(context, data):
    # 15 minutes timer
    timer = 5
    
    if context.current_dt.minute % timer != 0:
        return
    elif (context.current_dt.hour == 9) and (context.current_dt.minute == 0):
        return
    
    # 若损失率大于g.loss_rate，则调整（减小）可持有现金和总价值
    # if value < (1 - g.loss_rate) * context.portfolio.starting_cash:
    #     cash *= g.adjust_rate
    #     value *= g.adjust_rate
    
    for pindex in range(len(context.subportfolios)):
        # log.info('')
        pass
    
    for sec in g.security:
        current_price = data[sec].price
        g.turtle.start_running(context, sec, current_price)

'''
================================================================================
每天收盘后
================================================================================
'''
def after_trading_end(context):
    # log.debug("====================")
    # for pindex in range(len(context.subportfolios)):
    #     log.debug("[System {}]".format(pindex))
    #     log.debug("Turtle params: ")
    #     for key,value in g.turtle.system[pindex].turtle_params.items():
    #         log.debug('{key}:{value}'.format(key = key, value = value))
    #     log.debug("System positions: ")
    #     for key,value in g.turtle.system[pindex].system_positions.items():
    #         log.debug('{key}:{value}'.format(key = key, value = value))
    # log.debug("====================")
        
    return

'''
================================================================================
策略结束后
================================================================================
'''
def on_strategy_end(context):
    log.debug("====================")
    for pindex in range(len(context.subportfolios)):
        log.debug("[System {}]".format(pindex))
        log.debug("Total Value: {}".format(context.subportfolios[pindex].total_value))
