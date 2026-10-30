# Clone from JoinQuant
# postId: 39b24b3ea368fefc46bfa215bd9d023b
# backtestId: e7fcd8cc16ee00a4a9e526b2a1799a1c
# title: 仓位查询结果与实际情况不一致

# 导入函数库
import jqdata
import datetime
import time
import math
import urllib.request

import numpy as np
import talib
import math
import operator

from csv import DictReader
from sys import version_info
from six import StringIO

g_symbol_begin = 0
g_symbol_count = 20

g_run_period = 'day' # day minute

g_is_testback = True 
g_config_task_id = '00017'
g_config_website = 'https://inteliter.github.io'
g_config_signal_dir = 'DAC4CA77-48E4-4471-9063-A90DD0F05496'
g_config_signal_file = 'testback.csv'

g_config_symbol_file = '%s/signal/symbol-shizhi-3700.csv' % (g_config_website)
g_config_symbol_file_local = 'config/symbol-senario-000.csv'

g_use_special_symbol = True

# 仓位管理
g_max_cash_rate = 1.0
g_balance_rate = g_max_cash_rate / 30
g_balance_rate_per_symbol = g_balance_rate * 6
#g_balance_per_order = 100000
g_min_available_cash_rate = 1.0 - g_max_cash_rate * 0.95
g_balance_dynamic_rate = 0.35

g_special_symbols_xx = [
    '603338.XSHG', '300014.XSHE', '600887.XSHG', '600763.XSHG', '601100.XSHG',
    '002179.XSHE', '300142.XSHE', '600048.XSHG', '600585.XSHG', '000002.XSHE',
    '000001.XSHE', '600036.XSHG', '600741.XSHG', '601799.XSHG', '600346.XSHG',
    '600009.XSHG', '002142.XSHE', '603605.XSHG', '601888.XSHG', '002475.XSHE',
    '600872.XSHG', '002311.XSHE', '002032.XSHE', '600690.XSHG', '000651.XSHE',
    '000333.XSHE', '600436.XSHG', '000661.XSHE', '300015.XSHE', '000538.XSHE',
    '600276.XSHG', '000858.XSHE', '600519.XSHG', '000895.XSHE', '603288.XSHG',
    ]

g_special_symbols = [
    '600519.XSHG', 
    '601888.XSHG', 
    '000333.XSHE', 
    '000858.XSHE', 
    '000651.XSHE'
    ]

def initialize(context):
    log.info('========================================================')
    log.info('%s initialize', datetime_to_string(context.current_dt))

    if g_use_special_symbol and (len(g_special_symbols) == 1):
        set_benchmark(g_special_symbols[0])
    else:
        set_benchmark('000300.XSHG')
        
    set_option('use_real_price', True)
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    g.available_cash_rate = 1.0

    if (g_use_special_symbol):
        initialize_quant_special_action(g_special_symbols)
    else:
        initialize_quant_action(g_use_remote_file)

    #for hour in range(0, 24, 1):
    #    for minute in range(0, 60, 5):
    #        run_daily(timer_event, time=('%02d:%02d'%(hour, minute)), reference_security='000300.XSHG')
            
    for hour in range(9, 15, 1):
        for minute in range(29, 60, 30):
            run_daily(timer_event, time=('%02d:%02d'%(hour, minute)), reference_security='000300.XSHG')
           
    if g_is_testback:
        #url = '%s/signal/%s/%s/%s' % (g_config_website, g_config_task_id, g_config_signal_dir, g_config_signal_file)
        #g.signals = read_remote_csv(url)
        
        url = 'signal/testback/%s' % g_config_signal_file
        g.signals = read_csv(url)
        
        # TODO test
        log.info(url)
        for i in range(0, min(10, len(g.signals)), 1):
            signal = g.signals[i]
            #log.info('%r' % signal)
            log.info('%s %s %s %s' % (signal['time'], signal['symbol'], signal['trend'], signal['type']))

def initialize_quant_special_action(symbols):
    g.action_manager = QActionManager()
    idx = 0
    for symbol in symbols:
        #if (symbol in g_omited_symbols):
        #    continue        
        action = QuantAction(symbol, idx)
        g.action_manager.AddQuantAction(action)
        idx += 1
        
def initialize_quant_action(use_remote_file):
    g.action_manager = QActionManager()
    if (use_remote_file):
        symbols = read_remote_csv(g_config_symbol_file)
    else:
        symbols = read_csv(g_config_symbol_file_local) 

    for i in range(g_symbol_begin, g_symbol_begin + g_symbol_count, 1):
        if (i >= len(symbols)):
            break

        vid = int(symbols[i]['id'])
        exchange = symbols[i]['exchange']
        symbol = '%06d.%s' % (vid, exchange)
        #if (symbol in g_omited_symbols):
        #    continue

        action = QuantAction(symbol, i)
        g.action_manager.AddQuantAction(action)

def timer_event(context):
    now = context.current_dt.hour * 60 + context.current_dt.minute
    tmbeg1 = 9 * 60 + 30
    tmend1 = 11 * 60 + 30
    tmbeg2 = 13 * 60
    tmend2 = 15 * 60
    if not((tmbeg1 <= now <= tmend1) or (tmbeg2 <= now <= tmend2)):  
        #log.info(datetime_to_string(context.current_dt))
        return
    
    # 股票正常交易时间
    g.could_trade_benchmark = check_for_benchmark_rsi('000300.XSHG', 90, 50, 100, True)
    g.action_manager.HandleData(context)
    
def handle_data(context, data):
    pass


#============================================================================================
class OrderInfo(object):
    def __init__(self):
        self.contract = ''
        self.strategy_id = ''
        self.order_id = ''
        self.type = 'buy'
        self.side = 'long'
        self.amount = 0
        self.value = 0.0
        self.balance_rate = 0.0


class QuantAction(object):
    def __init__(self, symbol, strategy_id):
        self.symbol = symbol
        self.strategy_id = strategy_id
        self.balance_rate = 0.0
        
        self.last_price = 0.0
        self.remote_order = OrderInfo()
        self.orders = []
        self.error_count = 0

    def GetLastPrice(self, timeframe):
        vperiod = '1m'
        if (timeframe == 'day'):
            vperiod = '1d'

        df = attribute_history(self.symbol, 1, vperiod, ['close'])
        if (df['close'] is None):
            return -1.0

        vclose = df['close'][-1]
        return vclose
        
    def VerifyOrderStatus(self, context):
        local_amount = 0
        for xorder in self.orders:
            local_amount += xorder.amount
            
        # TODO bug 查询当前每只股票的手数和仓位，实际的仓位已经是空仓状态，但是amount和value的值都不为零
        if (self.remote_order.amount != local_amount) or (self.error_count != 0):
            log.error('%s order\'s %s amount[%d %d] value[%.0f]' %  (datetime_to_string(context.current_dt), 
                self.symbol, self.remote_order.amount, local_amount, self.remote_order.value))
                
            vorder = order_target_value(self.symbol, 0, side='long')
            if (vorder is not None and vorder.status == OrderStatus.held):
                self.orders = []
                g.available_cash_rate += self.balance_rate
                self.balance_rate = 0.0
                self.error_count = 0
                return False
        else:
            log.info('%s order\'s %s amount[%d %d] value[%.0f]' %  (datetime_to_string(context.current_dt), 
                self.symbol, self.remote_order.amount, local_amount, self.remote_order.value))
                
        return True
        
        
    def HandleData(self, context):
        #log.info('%s QuantAction.HandleData(...)' % datetime_to_string(context.current_dt))
        self.last_price = self.GetLastPrice(g_run_period)
        if self.last_price <= 0.0:
            return
        
        excecuted_signal_indexs = []
        for idx in range(0, len(g.signals), 1):
            signal = g.signals[idx]
            symbol = signal['symbol']
            if (self.symbol != symbol):
                continue
        
            has_enough_cash = False
            if (g.available_cash_rate >= g_min_available_cash_rate) and (self.balance_rate < g_balance_rate_per_symbol):
                has_enough_cash = True
                
            could_trade = True
                
            order_type = signal['type']
            order_side = signal['trend']
            order_id = signal['order_id']
            strategy_id = signal['strategy_id']
            
            order_time = string_to_datetime(signal['time'])
            if order_time < context.current_dt:
                excecuted_signal_indexs.append(idx)
                continue
            if order_time > context.current_dt:
                break
            
            log.info('%s %s %s %s' % (signal['time'], signal['symbol'], signal['trend'], signal['type']))
            
            excecuted_signal_indexs.append(idx)
            
            balance_rate = g_balance_rate
            if not(g.could_trade_benchmark):
                balance_rate *= g_balance_dynamic_rate
            
            if (order_type == 'buy') and could_trade and has_enough_cash:
                self.OpenOrder(context, strategy_id, order_id, balance_rate, order_type, order_side)
            elif order_type == 'sell':
                self.CloseOrder(context, strategy_id, order_id)
            
        for idx in range(len(excecuted_signal_indexs) - 1, -1, -1):
            del g.signals[idx]
    
        
    def OpenOrder(self, context, strategy_id, order_id, balance_rate, order_type, order_side):
        vbalance = context.portfolio.total_value
        last_price = self.last_price
        amount = value_to_amount(vbalance * balance_rate, last_price)
        if (amount < 100):
            return

        vorder = order(self.symbol, amount, side=order_side)
        #vorder = order_target_value(self.symbol, vbalance * balance_rate, side=self.order.side)
        if (vorder is not None and vorder.status == OrderStatus.held):
            log.info('%s buy  order[%s %s %d %r] ok.' % (datetime_to_string(context.current_dt), self.symbol, order_side, amount, vorder.status))
            
            xorder = OrderInfo()
            xorder.contract = symbol
            xorder.strategy_id = strategy_id
            xorder.order_id = order_id
            xorder.type = order_type
            xorder.side = order_side
            xorder.amount = amount
            xorder.balance_rate = balance_rate
            self.orders.append(xorder)

            self.balance_rate += balance_rate
            g.available_cash_rate -= balance_rate
        else:
            log.error('%s buy  order[%s %s %d] error.' % (datetime_to_string(context.current_dt), self.symbol, order_side, amount))
            self.error_count += 1

    def CloseOrder(self, context,  strategy_id, order_id):
        found = False
        found_idx = 0
        amount = 0
        for xorder in self.orders:
            if (strategy_id == xorder.strategy_id) and (order_id == xorder.order_id):
                amount = xorder.amount
                #symbol = xorder.contract
                order_side = xorder.side
                found = True
                break

            found_idx += 1
        
        if not(found):
            return
        else:
            del self.orders[found_idx]
            
        vorder = order(self.symbol, -amount, side=order_side)
        #vorder = order_target_value(self.symbol, 0, side=self.order.side)
        if (vorder is not None and vorder.status == OrderStatus.held):
            log.info('%s sell order[%s %s %d %r] ok.' % (datetime_to_string(context.current_dt), self.symbol, order_side, amount, vorder.status))
            
            self.balance_rate -= xorder.balance_rate
            g.available_cash_rate += xorder.balance_rate
        else:
            log.info('%s sell order[%s %s %d] error.' % (datetime_to_string(context.current_dt), self.symbol, order_side, amount))
            self.error_count += 1

    
class QActionManager(object):
    def __init__(self):
        self.actions = []
        
        
    def AddQuantAction(self, action):
        self.actions.append(action)
        log.info('QActionManager::AddQauntAction => symbol[%s]' % action.symbol)
    
    
    def HandleData(self, context):
        total_value = context.portfolio.total_value
        available_cash = context.portfolio.available_cash
        g.available_cash_rate = available_cash / total_value
        
        position_dict = context.portfolio.long_positions
        for position in list(position_dict.values()):
            for action in self.actions:
                if (action.symbol == position.security):
                    action.remote_order.amount = position.total_amount + position.locked_amount
                    action.remote_order.value = position.value
                    break

        for action in self.actions:
            if action.VerifyOrderStatus(context):
                action.HandleData(context)

#============================================================================================
def check_for_benchmark_rsi(symbol, period, rsi_min, rsi_max, show_rsi):
    df = attribute_history(symbol, period + 1, '1d', ['close'])
    close = [float(x) for x in df['close']]
    if (math.isnan(close[0]) or math.isnan(close[-1])):
        return False

    rsi = talib.RSI(np.array(close), timeperiod=period)[-1]
    if (show_rsi):
        record(RSI=max(0, (rsi - 50)))
    return (rsi_min < rsi < rsi_max)


#============================================================================================
# 公共函数.资金手数转换
def value_to_amount(value, price):
    amount = round(value / price * 0.01) * 100
    return amount
    
# 公共函数.CSV文件读写
def get_remote_file_content(url):
    rsp = urllib.request.urlopen(url)
    text = rsp.read()
    return text

def read_csv(filename):
    try:    
        vdata = read_file(filename)
    except:
        return []

    buffer = StringIO()
    if version_info.major < 3:
        buffer.write(vdata)
    else:
        buffer.write(vdata.decode())

    buffer.seek(0)
    return list(DictReader(buffer))
    
def read_remote_csv(url):
    try:
        vdata = get_remote_file_content(url)
    except:
        return []

    buffer = StringIO()
    if version_info.major < 3:
        buffer.write(vdata)
    else:
        buffer.write(vdata.decode())

    buffer.seek(0)
    return list(DictReader(buffer))  

# 公共函数.时间转换
def datetime_to_string(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def datetime_to_datestring(dt):
    return dt.strftime("%Y-%m-%d")

def string_to_datetime(st):
    return datetime.datetime.strptime(st, "%Y-%m-%d %H:%M:%S")

def string_to_timestamp(st):
    return time.mktime(time.strptime(st, "%Y-%m-%d %H:%M:%S"))

def timestamp_to_string(sp):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sp))

def datetime_to_timestamp(dt):
    return time.mktime(dt.timetuple())

def timestamp_to_struct(sp):
    return time.localtime(sp)    