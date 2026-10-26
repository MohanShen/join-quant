# Clone from JoinQuant
# postId: 87ae2f80ea789bb556ef769c15015e63
# backtestId: 06d6797da1082958d02017db40b06248
# title: 动态因子策略探讨

'''
版本：面向对象重构 二八择时小市值v2.0.7
期：2017.1.4
原作者：Morningstar
修改者：晚起的小虫
'''
import pandas as pd
from six import StringIO
import time
from datetime import timedelta

import cPickle as pickle

#from api import *
#from webtrader import WebTrader
#from MailSenderHTML import MailSenderHTML
#from HTMLConcat import HTMLConcat

from pandas import Series, DataFrame
import numpy as np
import statsmodels.api as sm
import scipy.stats as scs
import matplotlib.pyplot as plt


# 登陆券商
def loading():
    timeNow= time.strftime("%H:%M:%S",time.localtime(time.time()))
    timeStart = "09:20:00"
    timeEnd = "18:00:00"
    log.info("timeNow: %s" % timeNow)
    log.info("(timeStart < timeNow): %s" % (timeStart < timeNow))
    log.info("(timeNow < timeEnd): %s" % (timeNow < timeEnd))

    
    if (timeStart < timeNow) and (timeNow < timeEnd):
        ''' 登陆 '''
        g.__user = use('xq')
        g.__user.prepare('xq_mutifactor.txt')

# 是否当日或者调试
def beforeProcess(context):
    # 计算自然日
    todayDate = datetime.date.today() 
    today = datetime.datetime.strptime(str(todayDate),'%Y-%m-%d')
    # 系统日期与自然日对比
    g.isToday = False#context.current_dt>=today
    g.isTradeDebug = False
    log.info(40*"-")
    log.info("g.isToday: %s" % g.isToday)
    log.info("g.isTradeDebug: %s" % g.isTradeDebug)
    log.info(40*"-")
    
            

'''选择规则组合成一个量化策略'''
def select_strategy():
    '''
    策略选择设置说明:
    策略由以下步骤规则组合，组合而成:
    1.持仓股票的处理规则
    2.调仓条件判断规则
    3.Query选股规则 (可选，有些规则可能不需要这个)
    4.股票池过滤规则 (可选，有些规则可能不需要这个)
    5.调仓规则
    6.其它规则(如统计)
    
    每个步骤的规则组合为一个二维数组
    一维指定由什么规则组成，注意顺序，程序将会按顺序创建，按顺序执行。
    不同的规则组合可能存在一定的顺序关系。
    二维指定具体规则配置，由 [0.是否启用，1.描述，2.规则实现类名，3.规则传递参数(dict)]] 组成。
    注：所有规则类都必需继承自Rule类或Rule类的子类
    '''
    # 规则配置list下标描述变量。提高可读性与未来添加更多规则配置。
    g.cs_enabled,g.cs_memo,g.cs_class_name,g.cs_param = range(4)
    

    # 0.是否启用，1.描述，2.规则实现类名，3.规则传递参数(dict)]
    period = 1                                     # 调仓频率
    g.buyStockCount = 9                         # 购买股数
    num = 1
    rank_num = 1
    # 配置 1.持仓股票的处理规则 (这里主要配置是否进行个股止损止盈)
    g.position_stock_config = [
        [False,'个股止损','Stop_loss_stocks',{
            'period':period                     # 调仓频率，日
            },],
        [False,'个股止盈','Stop_profit_stocks',
            {'period':period ,                  # 调仓频率，日
            }]
    ]
        
    # 配置 2.调仓条件判断规则 
    g.adjust_condition_config = [
        [True,'指数最高低价比值止损','Stop_loss_by_price',{
            'index':'000001.XSHG',                  # 使用的指数,默认 '000001.XSHG'
             'day_count':160,                       # 可选 取day_count天内的最高价，最低价。默认160
             'multiple':2.2                         # 可选 最高价为最低价的multiple倍时，触 发清仓
            }],
        [False,'指数三乌鸦止损','Stop_loss_by_3_black_crows',{
            'index':'000001.XSHG',                  # 使用的指数,默认 '000001.XSHG'
             'dst_drop_minute_count':60,            # 可选，在三乌鸦触发情况下，一天之内有多少分钟涨幅<0,则触发止损，默认60分钟
            }],
        [False,'28择时','Stop_loss_by_28_index',{
                    'index2' : '000016.XSHG',       # 大盘指数
                    'index8' : '399333.XSHE',       # 小盘指数
                    'index_growth_rate': 0.01,      # 判定调仓的二八指数20日增幅
                    'dst_minute_count_28index_drop': 120 # 符合条件连续多少分钟则清仓
                }],
        [True,'调仓时间','Time_condition',{
                'hour': 14,                    # 调仓时间,小时
                'minute' : 50                   # 调仓时间，分钟
            }],
        [True,'28择时','Index28_condition',{    # 该调仓条件可能会产生清仓行为
                'index2' : '000300.XSHG',       # 大盘指数
                'index8' : '000905.XSHG',       # 小盘指数
                'index_growth_rate': 0.01,      # 判定调仓的二八指数20日增幅
            }],
        [True,'调仓日计数器','Period_condition',{
                'period' : period ,             # 调仓频率,日
            }],
    ]
        
    # 配置 3.Query选股规则
    g.pick_stock_by_query_config = [
        [False,'选取小市值','Pick_small_cap',{}],
        [False,'过滤PE','Filter_pe',{
            'pe_min':0                          # 最小PE
            ,'pe_max':200                       # 最大PE
            }],
        [False,'过滤EPS','Filter_eps',{
            'eps_min':0                         # 最小EPS
            }],
        [False,'初选股票数量','Filter_limite',{
            'pick_stock_count':100              # 备选股票数目
            }]
    ]
    
    # 配置 4.股票池过滤规则
    g.filter_stock_list_config = [
        [False,'选取SZ50','Pick_SZ50',{}],
        [False,'选取A50','Pick_A50',{}],
        [True,'选取多因子','Pick_multifactorial',{}],
        [True,'过滤创业板','Filter_gem',{}],
        [True,'过滤ST','Filter_st',{}],
        [True,'过滤停牌','Filter_paused_stock',{}],
        [True,'过滤涨停','Filter_limitup',{}],
        [True,'过滤跌停','Filter_limitdown',{}],
        [False,'过滤n日增长率为负的股票','Filter_growth_is_down',{
            'day_count':20                      # 判断多少日内涨幅
            }],
        [False,'过滤黑名单','Filter_blacklist',{}],
        
        [False,'股票评分','Filter_rank',{
            'rank_stock_count': g.buyStockCount + rank_num              # 评分股数
            }],
        [False,'发提醒邮件','Send_mail',{}],     # 发邮件
        [True,'获取最终选股数','Filter_buy_count',{
            'buy_count': g.buyStockCount + num                     # 最终入选股票数
            }],
    ]
        
    # 配置 5.调仓规则
    g.adjust_position_config = [
        [True,'卖出股票','Sell_stocks',{}],
        [True,'买入股票','Buy_stocks',{
            'buy_count': g.buyStockCount                      # 最终买入股票数
            }]                     
    ]
    
    g.send_mail_config = [
        [True,'发提醒邮件','Send_mail',{}]     # 发邮件
    ]
    
    # 配置 6.其它规则
    g.other_config = [
        [True,'统计','Stat',{}]
    ]

# 创建一个规则执行器，并初始化一些通用事件
def create_rule(class_name,params):
    '''
    在这借用eval函数，把规则配置里的字符串类名实例化。
    eval函数说明：将字符串当成有效Python表达式来求值，并返回计算结果
    x = 1
    y = eval('x+1')
    则结果为 y==2
    '''
    obj = eval(class_name)(params)
    obj.on_open_position = open_position
    obj.on_close_position = close_position
    obj.on_clear_position = clear_position
    return obj
    
# 根据规则配置创建规则执行器
def create_rules(config):
    # config里 0.是否启用，1.描述，2.规则实现类名，3.规则传递参数(dict)]
    return [create_rule(c[g.cs_class_name],c[g.cs_param]) for c in config if c[g.cs_enabled]]

def initialize(context):
    log.info("==> initialize @ %s"%(str(context.current_dt)))
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    
    select_strategy()
    '''-----1.持仓股票的处理规则:-----'''
    g.position_stock_rules = create_rules(g.position_stock_config)

    '''-----2.调仓条件判断规则:-----'''
    g.adjust_condition_rules = create_rules(g.adjust_condition_config)

    '''-----3.Query选股规则:-----'''
    g.pick_stock_by_query_rules = create_rules(g.pick_stock_by_query_config)

    '''-----4.股票池过滤规则:-----'''
    g.filter_stock_list_rules = create_rules(g.filter_stock_list_config)
    
    '''-----5.调仓规则:器-----'''
    g.adjust_position_rules = create_rules(g.adjust_position_config)
    
    '''-----发邮件规则-----'''
    g.send_mail_rules = create_rules(g.send_mail_config)
    
    '''-----6.其它规则:-------'''
    g.other_rules = create_rules(g.other_config)
    
    # 把所有规则合并排重生成一个总的规则收录器。以方便各处共同调用的
    g.all_rules = list(set(g.position_stock_rules 
            + g.adjust_condition_rules
            + g.pick_stock_by_query_rules
            + g.filter_stock_list_rules
            + g.adjust_position_rules
            + g.other_rules
        ))
        
    for rule in g.all_rules:
        rule.initialize(context)

    # 打印规则参数
    log_param()

# 按分钟回测
def handle_data(context, data):
    # 执行其它辅助规则
    for rule in g.other_rules:
        rule.handle_data(context,data)

    # 持仓股票动作的执行,目前为个股止损止盈
    for rule in g.position_stock_rules:
        rule.handle_data(context,data)

    # ----------这部分当前本策略其实并没有啥用，扩展用--------------
    # 这里执行选股器调仓器的handle_data主要是为了扩展某些选股方式可能需要提前处理数据。
    # 举例：动态获取黑名单，可以调仓前一段时间先执行。28小市值规则这里都是空动作。
    for rule in g.pick_stock_by_query_rules:
        rule.handle_data(context,data)
    
    for rule in g.filter_stock_list_rules:
        rule.handle_data(context,data)
    
    # 调仓器的分钟处理
    for rule in g.adjust_position_rules:
        rule.handle_data(context,data)
    # -----------------------------------------------------------
    
    # 判断是否满足调仓条件，所有规则以and 逻辑执行
    for rule in g.adjust_condition_rules:
        rule.handle_data(context,data)
        if not rule.can_adjust:
            return
    # ---------------------调仓--------------------------
    log.info("handle_data: ==> 满足条件进行调仓")
    # 调仓前预处理
    for rule in g.all_rules:
        rule.before_adjust_start(context,data)
        
    # Query 选股
    q = None
    for rule in g.pick_stock_by_query_rules:
        q = rule.filter(context,data,q)
    
    # 过滤股票列表
    stock_list = list(get_fundamentals(q)['code']) if q != None else []
    for rule in g.filter_stock_list_rules:
        stock_list = rule.filter(context,data,stock_list)
        
        
    log.info("handle_data: 选股后可买股票: %s" %(stock_list))
    
    # 执行调仓
    for rule in g.adjust_position_rules:
        rule.adjust(context,data,stock_list)
    
    # 调仓后处理
    for rule in g.all_rules:
        rule.after_adjust_end(context)
    # ----------------------------------------------------

# 开盘
def before_trading_start(context):
    log.info("==========================================================================")
    # 雪球，用于交易
    g.weight = 0
    beforeProcess(context)
    print "多因子回测开始"
    get_multifactorial(context)
    print "多因子回测结束"
    
    for rule in g.all_rules:
        rule.before_trading_start(context)

# 收盘
def after_trading_end(context):
    for rule in g.all_rules:
        rule.after_trading_end(context)
    
    # 得到当前未完成订单
    orders = get_open_orders()
    for _order in orders.values():
        log.info("canceled uncompleted order: %s" %(_order.order_id))

# 进程启动(一天一次)
def process_initialize(context):
    # 变量实例化
    beforeProcess(context)
    print "多因子回测开始"
    get_multifactorial(context)
    print "多因子回测结束"
    
    for rule in g.all_rules:
        rule.process_initialize(context)

# 这里示例进行模拟更改回测时，如何调整策略,基本通用代码。
def after_code_changed(context):
    # # 因为是示例，在不是模拟里更新回测代码的时候，是不需要的，所以直接退出
    # return
    
    # 调整策略通用实例代码
    # 获取新策略
    select_strategy()
    # 按新策略顺序重整规则列表，如果对象之前存在，则移到新列表，不存在则新建。
    # 不管之前旧的规则列表是什么顺序，一率按新列表重新整理。
    def check_chang(rules,config):
        nl = []
        for c in config:
        # 按顺序循环处理新规则
            if not c[g.cs_enabled]: # 不使用则跳过
                continue
            # 查找旧规则是否存在
            find_old = None
            for old_r in rules:
                if old_r.__name__ == c[g.cs_class_name]:
                    find_old = old_r
                    break
            if find_old != None:
                # 旧规则存在则添加到新列表中,并调用规则的更新函数，更新参数。
                nl.append(find_old)
                find_old.update_params(context,c[g.cs_param])
            else:
                # 旧规则不存在，则创建并添加
                new_r = create_rule(c[g.cs_class_name],c[g.cs_param])
                nl.append(new_r)
                # 调用初始化时该执行的函数
                for rule in g.all_rules:
                    rule.initialize(context)
        return nl
    
    # 重整所有规则
    g.position_stock_rules      = check_chang(g.position_stock_rules,g.position_stock_config)
    g.adjust_condition_rules    = check_chang(g.adjust_condition_rules,g.adjust_condition_config)
    g.pick_stock_by_query_rules = check_chang(g.pick_stock_by_query_rules,g.pick_stock_by_query_config)
    g.filter_stock_list_rules   = check_chang(g.filter_stock_list_rules,g.filter_stock_list_config)
    g.adjust_position_rules     = check_chang(g.adjust_position_rules,g.adjust_position_config)
    g.send_mail_rules           = check_chang(g.send_mail_rules,g.send_mail_config)
    g.other_rules               = check_chang(g.other_rules,g.other_config)
    
    # 重新生成所有规则的list
    g.all_rules = list(set(
            g.position_stock_rules 
            + g.adjust_condition_rules
            + g.pick_stock_by_query_rules
            + g.filter_stock_list_rules
            + g.adjust_position_rules
            + g.send_mail_rules
            + g.other_rules
        ))
        
# 显示策略组成
def log_param():
    def get_rules_str(rules):
        return '\n'.join(['   %d.%s '%(i+1,str(r)) for i,r in enumerate(rules)]) + '\n'
    s = '\n---------------------策略一览：规则组合与参数----------------------------\n'
    s += '一、持仓股票的处理规则:\n'  + get_rules_str(g.position_stock_rules)
    s += '二、调仓条件判断规则:\n'    + get_rules_str(g.adjust_condition_rules)
    s += '三、Query选股规则:\n'       + get_rules_str(g.pick_stock_by_query_rules)
    s += '四、股票池过滤规则:\n'      + get_rules_str(g.filter_stock_list_rules)
    s += '五、调仓规则:\n'            + get_rules_str(g.adjust_position_rules)
    s += '  发邮件规则:\n'            + get_rules_str(g.send_mail_rules)
    s += '六、其它规则:\n'            + get_rules_str(g.other_rules)
    s += '--------------------------------------------------------------------------'
    print s

''' ==============================持仓操作函数，共用================================'''
# 开仓，买入指定价值的证券
# 报单成功并成交（包括全部成交或部分成交，此时成交量大于0），返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），返回False
# 报单成功，触发所有规则的when_buy_stock函数
def open_position(sender,security, value):
    order = order_target_value_(sender,security, value)
    if order != None and order.filled > 0:
        for rule in g.all_rules:
            rule.when_buy_stock(security,order)
            
        # 雪球买入
        if (g.isToday or g.isTradeDebug):
            loading()
            try:
                g.__user.adjust_weight(security[:6],g.weight)
            except Exception, e:
                log.info('股票代码: %s ' % security[:6] + e.message)
            
        return True
    return False

# 平仓，卖出指定持仓
# 平仓成功并全部成交，返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），或者报单非全部成交，返回False
# 报单成功，触发所有规则的when_sell_stock函数
def close_position(sender,position,is_normal = True):
    security = position.security
    order = order_target_value_(sender,security, 0) # 可能会因停牌失败
    if order != None:
        if order.filled > 0:
            for rule in g.all_rules:
                rule.when_sell_stock(position,order,is_normal)
                
            # 雪球卖出
            if (g.isToday or g.isTradeDebug):
                loading()
                try:
                    g.__user.adjust_weight(security[:6],0)
                except Exception, e:
                    log.info('股票代码: %s ' % security[:6] + e.message)
                
            return True
    return False

# 清空卖出所有持仓
# 清仓时，调用所有规则的 when_clear_position
def clear_position(sender,context):
    # 用于发邮件
    g.position = context.portfolio.positions.keys()
    g.stocks_to_buy = []
    
    if context.portfolio.positions:
        sender.log_info("==> 清仓，卖出所有股票")
        for stock in context.portfolio.positions.keys():
            position = context.portfolio.positions[stock]
            close_position(sender,position,False)
    for rule in g.all_rules:
        rule.when_clear_position(context)        
    # 调仓后处理
    for rule in g.all_rules:
        rule.after_adjust_end(context)

# 自定义下单
# 根据Joinquant文档，当前报单函数都是阻塞执行，报单函数（如order_target_value）返回即表示报单完成
# 报单成功返回报单（不代表一定会成交），否则返回None
def order_target_value_(sender,security, value):
    if value == 0:
        sender.log_debug("Selling out %s" % (security))
    else:
        sender.log_debug("Order %s to value %f" % (security, value))
        
    # 如果股票停牌，创建报单会失败，order_target_value 返回None
    # 如果股票涨跌停，创建报单会成功，order_target_value 返回Order，但是报单会取消
    # 部成部撤的报单，聚宽状态是已撤，此时成交量>0，可通过成交量判断是否有成交
    return order_target_value(security, value)

''' ==============================规则基类================================'''
class Rule(object):
    # 每个子类必需写__name__,以修改策略时，方便判断规则器是否存在。
    __name__='Base'
    # 持仓操作的事件
    on_open_position = None
    on_close_position = None
    on_clear_position = None
    
    def __init__(self,params):
        pass
    def initialize(self,context):
        pass
    def handle_data(self,context, data):
        pass
    def before_trading_start(self,context):
        pass
    def after_trading_end(self,context):
        pass
    def process_initialize(self,context):
        pass
    def after_code_changed(self,context):
        pass
    # 卖出股票时调用的函数
    # price为当前价，amount为发生的股票数,is_normail正常规则卖出为True，止损卖出为False
    def when_sell_stock(self,position,order,is_normal):
        pass
    # 买入股票时调用的函数
    # price为当前价，amount为发生的股票数
    def when_buy_stock(self,stock,order):
        pass
    # 清仓时调用的函数
    def when_clear_position(self,context):
        pass
    # 调仓前调用
    def before_adjust_start(self,context,data):
        pass
    # 调仓后调用用
    def after_adjust_end(slef,context):
        pass
    # 更改参数
    def update_params(self,context,params):
        pass
    
    # 持仓操作事件的简单判断处理，方便使用。
    def open_position(self,security, value):
        if self.on_open_position != None:
            return self.on_open_position(self,security,value)
    def close_position(self,position,is_normal = True):
        if self.on_close_position != None:
            return self.on_close_position(self,position,is_normal = True)
    def clear_position(self,context):
        if self.on_clear_position != None:
            self.on_clear_position(self,context)
    # 为日志显示带上是哪个规则器输出的
    def log_info(self,msg):
        log.info('%s: %s'%(self.__name__,msg))
    def log_warn(self,msg):
        log.warn('%s: %s'%(self.__name__,msg))
    def log_debug(self,msg):
        log.debug('%s: %s'%(self.__name__,msg))
 
'''==============================调仓条件判断器基类=============================='''
class Adjust_condition(Rule):
    __name__='Adjust_condition'
    # 返回能否进行调仓
    @property
    def can_adjust(self):
        return True
        
'''==============================选股 query过滤器基类=============================='''
class Filter_query(Rule):
    __name__='Filter_query'
    def filter(self,context,data,q):
        return None
'''==============================选股 stock_list过滤器基类=============================='''
class Filter_stock_list(Rule):
    __name__='Filter_stock_list'
    def filter(self,context,data,stock_list):
        return None
'''==============================调仓的操作基类=============================='''
class Adjust_position(Rule):
    __name__='Adjust_position'
    def adjust(self,context,data,buy_stocks):
        pass

'''-------------------------调仓时间控制器-----------------------'''
class Time_condition(Adjust_condition):
    __name__='Time_condition'
    def __init__(self,params):
        # 配置调仓时间（24小时分钟制）
        self.hour = params.get('hour',9)
        self.minute = params.get('minute',30)
    def update_params(self,context,params):
        self.hour = params.get('hour',self.hour)
        self.minute = params.get('minute',self.minute)
        pass
    
    @property   
    def can_adjust(self):
        return self.t_can_adjust

    def handle_data(self,context, data):
        hour = context.current_dt.hour
        minute = context.current_dt.minute
        self.t_can_adjust = hour == self.hour and minute == self.minute
        pass
    

    def __str__(self):
        return '调仓时间控制器: [调仓时间: %d:%d]'%(
                self.hour,self.minute)
'''-------------------------调仓日计数器-----------------------'''
class Period_condition(Adjust_condition):
    __name__='Period_condition'
    def __init__(self,params):
        # 调仓日计数器，单位：日
        self.period = params.get('period',3)
        self.day_count = 0
        self.t_can_adjust = False
        
    def update_params(self,context,params):
        self.period  = params.get('period',self.period )
        
    @property   
    def can_adjust(self):
        return self.t_can_adjust

    def handle_data(self,context, data):
        self.log_info("调仓日计数 [%d]"%(self.day_count))
        self.t_can_adjust = self.day_count % self.period == 0
        self.day_count += 1
        pass
    
    def before_trading_start(self,context):
        self.t_can_adjust = False
        pass
    def when_sell_stock(self,position,order,is_normal):
        if not is_normal: 
            # 个股止损止盈时，即非正常卖股时，重置计数，原策略是这么写的
            self.day_count = 0
        pass
    # 清仓时调用的函数
    def when_clear_position(self,context):
        self.day_count = 0
        pass
    
    def __str__(self):
        return '调仓日计数器:[调仓频率: %d日] [调仓日计数 %d]'%(
                self.period,self.day_count)
'''-------------------------28指数涨幅调仓判断器----------------------'''
class Index28_condition(Adjust_condition):
    __name__='Index28_condition'
    def __init__(self,params):
        self.index2 = params.get('index2','')
        self.index8 = params.get('index8','')
        self.index_growth_rate = params.get('index_growth_rate',0.01)
        self.t_can_adjust = False
    
    def update_params(self,context,params):
        self.index2 = params.get('index2',self.index2)
        self.index8 = params.get('index8',self.index8)
        self.index_growth_rate = params.get('index_growth_rate',self.index_growth_rate)
        
    @property    
    def can_adjust(self):
        return self.t_can_adjust

    def handle_data(self,context, data):
        # 回看指数前20天的涨幅
        gr_index2 = get_growth_rate(self.index2)
        gr_index8 = get_growth_rate(self.index8)
        self.log_info("当前%s指数的20日涨幅 [%.2f%%]" %(get_security_info(self.index2).display_name, gr_index2*100))
        self.log_info("当前%s指数的20日涨幅 [%.2f%%]" %(get_security_info(self.index8).display_name, gr_index8*100))
        if gr_index2 <= self.index_growth_rate and gr_index8 <= self.index_growth_rate:
            self.clear_position(context)
            self.t_can_adjust = False
        else:
            self.t_can_adjust = True
        pass
    
    def before_trading_start(self,context):
        pass
    
    def __str__(self):
        return '28指数择时:[大盘指数:%s %s] [小盘指数:%s %s] [判定调仓的二八指数20日增幅 %.2f%%]'%(
                self.index2,get_security_info(self.index2).display_name,
                self.index8,get_security_info(self.index8).display_name,
                self.index_growth_rate * 100)

'''------------------小市值选股器-----------------'''
class Pick_small_cap(Filter_query):
    __name__='Pick_small_cap'
    def filter(self,context,data,q):
        #return query(valuation).order_by(valuation.market_cap.asc())
        return query(valuation).order_by(valuation.market_cap.desc())
        #return query(valuation).order_by(valuation.circulating_market_cap.asc())
    def __str__(self):
        return '按市值倒序选取股票'

class Pick_multifactorial(Filter_query):
    __name__='Pick_multifactorial'
    def filter(self,context,data,q):
        print "选股开始"
        today = context.current_dt
        end = today.strftime('%Y-%m-%d') 
        
        #factors = g.resultFac.index.tolist()
        factors = [g.fac]
        
        q = query(valuation.code) # 股票代码
        
        # 对每一个因子进行判断
        for factor in factors:
            if factor == "CMC":
                q = q.add_column(valuation.circulating_market_cap) # CMC 流通市值
            if factor == "MC":
                q = q.add_column(valuation.market_cap) # MC 总市值 
            if factor == "CMC/C":
                q = q.add_column(valuation.circulating_market_cap/valuation.capitalization*10000) # CMC/C 流通市值（亿）/总股本(万) （收盘价） 
            if factor == "TOE/MC":
                q = q.add_column(balance.total_owner_equities/valuation.market_cap/100000000) # TOE/MC 每元所有者权益
            if factor == "PB":
                q = q.add_column(valuation.pb_ratio) # PB 市净率
            if factor == "NP/MC":
                q = q.add_column(income.net_profit/valuation.market_cap/100000000) # NP/MC 每元所有者净利润
            if factor == "TP/MC":
                q = q.add_column(income.total_profit/valuation.market_cap/100000000) # TP/MC 每元利润总额
            if factor == "TA/MC":
                q = q.add_column(balance.total_assets/valuation.market_cap/100000000) # TA/MC 每元资产总额
            if factor == "OP/MC":
                q = q.add_column(income.operating_profit/valuation.market_cap/100000000) # OP/MC 每元营业利润
            if factor == "CRF/MC":
                q = q.add_column(balance.capital_reserve_fund/valuation.market_cap/100000000) # CRF/MC 每元资本公积
            if factor == "PS":
                q = q.add_column(valuation.ps_ratio) # PS 市销率
            if factor == "OR/MC":
                q = q.add_column(income.operating_revenue/valuation.market_cap/100000000) # OR/MC 每元营业收入
            if factor == "RP/MC":
                q = q.add_column(balance.retained_profit/valuation.market_cap/100000000) # RP/MC 每元未分配利润
            if factor == "TL/TA":
                q = q.add_column(balance.total_liability/balance.total_sheet_owner_equities)# TL/TA 资产负债率
            if factor == "TCA/TCL":
                q = q.add_column(balance.total_current_assets/balance.total_current_liability) # TCA/TCL  流动比率
            if factor == "PE":
                q = q.add_column(valuation.pe_ratio) # PE 市盈率
            if factor == "OR*ROA/NP":
                q = q.add_column(income.operating_revenue*indicator.roa/income.net_profit) # OR*ROA/NP  总资产周转率
            if factor == "GPM":
                q = q.add_column(indicator.gross_profit_margin) # GPM 销售毛利率
            if factor == "IRYOY":
                q = q.add_column(indicator.inc_revenue_year_on_year) # IRYOY  营业收入同比增长率(%) 
            if factor == "IRA":
                q = q.add_column(indicator.inc_revenue_annual) # IRA 营业收入环比增长率(%)
            if factor == "INPYOY":
                q = q.add_column(indicator.inc_net_profit_year_on_year) # INPYOY 净利润同比增长率(%)
            if factor == "INPA":
                q = q.add_column(indicator.inc_net_profit_annual) # INPA  净利润环比增长率(%) 
            if factor == "NPM":
                q = q.add_column(indicator.net_profit_margin) # NPM  销售净利率(%) 
            if factor == "OPTTR":
                q = q.add_column(indicator.operation_profit_to_total_revenue) # OPTTR  营业利润/营业总收入(%) 
            if factor == "C":
                q = q.add_column(valuation.capitalization)# C 总股本
            if factor == "CC":
                q = q.add_column(valuation.circulating_cap) # CC 流通股本(万股)
            if factor == "PR":
                q = q.add_column(valuation.pcf_ratio) # PR 市现率
            if factor == "PRL":
                q = q.add_column(valuation.pe_ratio_lyr) # PRL 市盈率LYR
            if factor == "ROE":
                q = q.add_column(indicator.roe) # ROE  净资产收益率ROE(%) 
            if factor == "ROA":
                q = q.add_column(indicator.roa) # ROA  总资产净利率ROA(%) 
            if factor == "EPS":
                q = q.add_column(indicator.eps) # EPS 每股盈余
        
        
        fdf = get_fundamentals(q, date=end)
        fdf.index = fdf['code']
        fdf.columns = ['code'] + factors
        # 行：选择全部，列，选择之后全部
        fdf = fdf.iloc[:,1:]
        
        #log.info( "g.resultFac: %s" % g.resultFac)
        #log.info( "factors: %s" % factors)
        #log.info( "fdf: %s" % fdf)
        
         
        score_stock = fdf[g.fac].order(ascending = g.ascending).index.tolist()[:100]
        
        return score_stock
        
    def __str__(self):
        return '多因子选股'
        
class Pick_SZ50(Filter_query):
    __name__='Pick_SZ50'
    def filter(self,context,data,stock_list):
        stock_list_SZ50 = get_index_stocks('000016.XSHG')
        return [stock for stock in stock_list if stock in stock_list_SZ50]
    def __str__(self):
        return '限定上证50指数成分股'
        
class Pick_A50(Filter_query):
    __name__='Pick_A50'
    def filter(self,context,data,stock_list):
        body = read_file("FTSE_China_A50_Index_Constituents.txt")
        stock_pd_A50 = pd.read_csv(StringIO(body))
        stock_list_A50 = []
        for code in stock_pd_A50.code.tolist():
            stock_list_A50.append(normalize_code(code))
        
        return [stock for stock in stock_list if stock in stock_list_A50]
    def __str__(self):
        return '限定新华富时A50指数成分股'

class Send_mail(Rule):
    __name__='Send_mail'
    
    # 调仓后调用用
    def after_adjust_end(slef,context):
        #g.isToday = True # 用于测试邮件提醒
        if (g.isToday or g.isTradeDebug):
            g.today_stock = get_all_securities(['stock'])
            g.over_rise_rank = g.buyStockCount
            
            # 邮件发送类
            g.__mailSenderHTML = MailSenderHTML(context,g)
            # 邮件正文组合类
            g.__htmlConcat = HTMLConcat(context,g)
            
            # 邮件提醒
            subject = str(context.current_dt) + " 动态因子策略"
            msg_mail = g.__htmlConcat.getNoticeMultifactor(g, log)
            
            orders = get_orders()
            if len(orders.values()) <= 0:
                subject += "（无）"
                pass
            else:
                subject += "（下单）"
                msg_mail += g.__htmlConcat.getOrdersHTML(orders, g)
                
            # 发送邮件
            g.__mailSenderHTML.sendMail(subject,msg_mail)

    
    def __str__(self):
        return '发送邮件'
            
class Filter_pe(Filter_query):
    __name__='Filter_pe'
    def __init__(self,params):
        self.pe_min = params.get('pe_min',0)
        self.pe_max = params.get('pe_max',200)
        
    def update_params(self,context,params):
        self.pe_min = params.get('pe_min',self.pe_min)
        self.pe_max = params.get('pe_max',self.pe_max)
        
    def filter(self,context,data,q):
        return q.filter(
            valuation.pe_ratio > self.pe_min,
            valuation.pe_ratio < self.pe_max
            )
    def __str__(self):
        return '根据PE范围选取股票： [ %d < pe < %d]'%(self.pe_min,self.pe_max)
        
class Filter_eps(Filter_query):
    __name__='Filter_eps'
    def __init__(self,params):
        self.eps_min = params.get('eps_min',0)
    def update_params(self,context,params):
        self.eps_min = params.get('eps_min',self.eps_min)
    def filter(self,context,data,q):
        return q.filter(
            indicator.eps > self.eps_min,
            )
    def __str__(self):
        return '根据EPS范围选取股票： [ %d < eps ]'%(self.eps_min)
    
class Filter_limite(Filter_query):
    __name__='Filter_limite'
    def __init__(self,params):
        self.pick_stock_count = params.get('pick_stock_count',0)
    def update_params(self,context,params):
        self.pick_stock_count = params.get('pick_stock_count',self.pick_stock_count)
    def filter(self,context,data,q):
        return q.limit(self.pick_stock_count)
    def __str__(self):
        return '初选股票数量: %d'%(self.pick_stock_count)

class Filter_gem(Filter_stock_list):
    __name__='Filter_gem'
    def filter(self,context,data,stock_list):
        return [stock for stock in stock_list if stock[0:3] != '300']
    def __str__(self):
        return '过滤创业板股票'
        
class Filter_paused_stock(Filter_stock_list):
    __name__='Filter_paused_stock'
    def filter(self,context,data,stock_list):
        current_data = get_current_data()
        return [stock for stock in stock_list if not current_data[stock].paused]
    def __str__(self):
        return '过滤停牌股票'
    
class Filter_limitup(Filter_stock_list):
    __name__='Filter_limitup'
    def filter(self,context,data,stock_list):
        threshold = 1.00
        return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or data[stock].close < data[stock].high_limit * threshold]
    def __str__(self):
        return '过滤涨停股票'
        
class Filter_limitdown(Filter_stock_list):
    __name__='Filter_limitdown'
    def filter(self,context,data,stock_list):
        threshold = 1.00
        return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or data[stock].close > data[stock].low_limit * threshold]
    def __str__(self):
        return '过滤跌停股票' 

class Filter_st(Filter_stock_list):
    __name__='Filter_st'
    def filter(self,context,data,stock_list):
        current_data = get_current_data()
        return [stock for stock in stock_list
            if not current_data[stock].is_st
            and not current_data[stock].name.startswith('退')]
    def __str__(self):
        return '过滤ST股票'

class Filter_growth_is_down(Filter_stock_list):
    __name__='Filter_growth_is_down'
    def __init__(self,params):
        self.day_count = params.get('day_count',20)
    def update_params(self,context,params):
        self.day_count = params.get('day_count',self.day_count)
    def filter(self,context,data,stock_list):
        return [stock for stock in stock_list if get_growth_rate(stock, self.day_count) > 0]
    def __str__(self):
        return '过滤n日增长率为负的股票'
 
class Filter_blacklist(Filter_stock_list):
    __name__='Index28_condition'
    def __get_blacklist(self):
        # 黑名单一览表，更新时间 2016.7.10 by 沙米
        # 科恒股份、太空板业，一旦2016年继续亏损，直接面临暂停上市风险
        blacklist = ["600656.XSHG", "300372.XSHE", "600403.XSHG", "600421.XSHG", "600733.XSHG", "300399.XSHE",
                     "600145.XSHG", "002679.XSHE", "000020.XSHE", "002330.XSHE", "300117.XSHE", "300135.XSHE",
                     "002566.XSHE", "002119.XSHE", "300208.XSHE", "002237.XSHE", "002608.XSHE", "000691.XSHE",
                     "002694.XSHE", "002715.XSHE", "002211.XSHE", "000788.XSHE", "300380.XSHE", "300028.XSHE",
                     "000668.XSHE", "300033.XSHE", "300126.XSHE", "300340.XSHE", "300344.XSHE", "002473.XSHE"]
        return blacklist
        
    def filter(self,context,data,stock_list):
        blacklist = self.__get_blacklist()
        return [stock for stock in stock_list if stock not in blacklist]
    def __str__(self):
        return '过滤黑名单股票'
        
class Filter_rank(Filter_stock_list):
    __name__='Filter_rank'
    def __init__(self,params):
        self.rank_stock_count = params.get('rank_stock_count',20)
    def update_params(self,context,params):
        self.rank_stock_count = params.get('self.rank_stock_count',self.rank_stock_count)
    def filter(self,context,data,stock_list):
        if len(stock_list) > self.rank_stock_count:
            stock_list = stock_list[:self.rank_stock_count]
        
        dst_stocks = {}
        for stock in stock_list:
            h = attribute_history(stock, 130, unit='1d', fields=('close', 'high', 'low'), skip_paused=True)
            low_price_130 = h.low.min()
            high_price_130 = h.high.max()
    
            avg_15 = data[stock].mavg(15, field='close')
            cur_price = data[stock].close

            score = (cur_price-low_price_130) + (cur_price-high_price_130) + (cur_price-avg_15)
            dst_stocks[stock] = score
            
        df = pd.DataFrame(dst_stocks.values(), index=dst_stocks.keys())
        df.columns = ['score']
        df = df.sort(columns='score', ascending=True)
        return list(df.index)
        
    def __str__(self):
        return '股票评分排序 [评分股数: %d ]'%(self.rank_stock_count)
        
class Filter_buy_count(Filter_stock_list):
    __name__='Filter_buy_count'
    def __init__(self,params):
        self.buy_count = params.get('buy_count',6)
    def update_params(self,context,params):
        self.buy_count = params.get('buy_count',self.buy_count)
    def filter(self,context,data,stock_list):
        # 用于发邮件
        g.position = context.portfolio.positions.keys()
        print "g.position %s" % g.position
        g.stocks_to_buy = stock_list[:30]
        
        if len(stock_list) > self.buy_count:
            return stock_list[:self.buy_count]
        else:
            return stock_list
    def __str__(self):
        return '获取最终待购买股票数:[ %d ]'%(self.buy_count)
        
'''---------------卖出股票规则--------------'''        
class Sell_stocks(Adjust_position):
    __name__='Sell_stocks'
    def adjust(self,context,data,buy_stocks):
        # 卖出不在待买股票列表中的股票
        # 对于因停牌等原因没有卖出的股票则继续持有
        for stock in context.portfolio.positions.keys():
            if stock not in buy_stocks:
                self.log_info("stock [%s] in position is not buyable" %(stock))
                position = context.portfolio.positions[stock]
                self.close_position(position)
            else:
                self.log_info("stock [%s] is already in position" %(stock))
    def __str__(self):
        return '股票调仓卖出规则：卖出不在buy_stocks的股票'
    
'''---------------买入股票规则--------------'''  
class Buy_stocks(Adjust_position):
    __name__='Buy_stocks'
    def __init__(self,params):
        self.buy_count = params.get('buy_count',6)
    def update_params(self,context,params):
        self.buy_count = params.get('buy_count',self.buy_count)
    def adjust(self,context,data,buy_stocks):
        # 买入股票
        # 始终保持持仓数目为g.buy_stock_count
        # 根据股票数量分仓
        # 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配
        position_count = len(context.portfolio.positions)
        if self.buy_count > position_count:
            value = context.portfolio.cash / (self.buy_count - position_count)
            # 雪球，每份购买的资金占总的权益比例
            g.weight = value / context.portfolio.total_value * 100
            #log.info("weight %s" % g.weight)
            
            for stock in buy_stocks:
                if context.portfolio.positions[stock].total_amount == 0:
                    if self.open_position(stock, value):
                        if len(context.portfolio.positions) == self.buy_count:
                            break
        pass
    def __str__(self):
        return '股票调仓买入规则：现金平分式买入股票达目标股票数'
    
'''---------------个股止损--------------'''
class Stop_loss_stocks(Rule):
    __name__='Stop_loss_stocks'
    # get_period_func 为获取period的函数,无传入参数，传出参数为period
    # on_close_position_func 卖出股票时触发的事件，传入参数为 stock,无返回
    def __init__(self,params):
        self.last_high = {}
        self.period = params.get('period',3)
        self.pct_change = {}
    def update_params(self,context,params):
        self.period = params.get('period',self.period)
    # 个股止损
    def handle_data(self,context, data):
        for stock in context.portfolio.positions.keys():
            cur_price = data[stock].close
            xi = attribute_history(stock, 2, '1d', 'high', skip_paused=True)
            ma = xi.max()
            if self.last_high[stock] < cur_price:
                self.last_high[stock] = cur_price

            threshold = self.__get_stop_loss_threshold(stock, self.period)
            #log.debug("个股止损阈值, stock: %s, threshold: %f" %(stock, threshold))
            if cur_price < self.last_high[stock] * (1 - threshold):
                self.log_info("==> 个股止损, stock: %s, cur_price: %f, last_high: %f, threshold: %f" 
                    %(stock, cur_price, self.last_high[stock], threshold))
    
                position = context.portfolio.positions[stock]
                self.close_position(position,False)
    
    # 获取个股前n天的m日增幅值序列
    # 增加缓存避免当日多次获取数据
    def __get_pct_change(self,security, n, m):
        pct_change = None
        if security in self.pct_change.keys():
            pct_change = self.pct_change[security]
        else:
            h = attribute_history(security, n, unit='1d', fields=('close'), skip_paused=True)
            pct_change = h['close'].pct_change(m) # 3日的百分比变比（即3日涨跌幅）
            self.pct_change[security] = pct_change
        return pct_change
        
    # 计算个股回撤止损阈值
    # 即个股在持仓n天内能承受的最大跌幅
    # 算法：(个股250天内最大的n日跌幅 + 个股250天内平均的n日跌幅)/2
    # 返回正值
    def __get_stop_loss_threshold(self,security, n = 3):
        pct_change = self.__get_pct_change(security, 250, n)
        #log.debug("pct of security [%s]: %s", pct)
        maxd = pct_change.min()
        #maxd = pct[pct<0].min()
        avgd = pct_change.mean()
        #avgd = pct[pct<0].mean()
        # maxd和avgd可能为正，表示这段时间内一直在增长，比如新股
        bstd = (maxd + avgd) / 2
    
        # 数据不足时，计算的bstd为nan
        if not isnan(bstd):
            if bstd != 0:
                return abs(bstd)
            else:
                # bstd = 0，则 maxd <= 0
                if maxd < 0:
                    # 此时取最大跌幅
                    return abs(maxd)
    
        return 0.099 # 默认配置回测止损阈值最大跌幅为-9.9%，阈值高貌似回撤降低

    def when_sell_stock(self,position,order,is_normal):
        if position.security in self.last_high:
            self.last_high.pop(position.security)
        pass
    
    def when_buy_stock(self,stock,order):
        if order.status == OrderStatus.held and order.filled == order.amount:
            # 全部成交则删除相关证券的最高价缓存
            self.last_high[stock] = get_close_price(stock, 1, '1m')
        pass
    
    def after_trading_end(self,context):
        self.pct_change = {}
        pass
                
    def __str__(self):
        return '个股止损器:[当前缓存价格数: %d ]'%(len(self.__last_high))
        
''' ----------------------个股止盈------------------------------'''
class Stop_profit_stocks(Rule):
    __name__='Stop_profit_stocks'
    def __init__(self,params):
        self.last_high = {}
        self.period = params.get('period',3)
        self.pct_change = {}
    def update_params(self,context,params):
        self.period = params.get('period',self.period)    
    # 个股止盈
    def handle_data(self,context, data):
        for stock in context.portfolio.positions.keys():
                position = context.portfolio.positions[stock]
                cur_price = data[stock].close
                threshold = self.__get_stop_profit_threshold(stock, self.period)
                #log.debug("个股止盈阈值, stock: %s, threshold: %f" %(stock, threshold))
                if cur_price > position.avg_cost * (1 + threshold):
                    self.log_info("==> 个股止盈, stock: %s, cur_price: %f, avg_cost: %f, threshold: %f" 
                        %(stock, cur_price, self.last_high[stock], threshold))
        
                    position = context.portfolio.positions[stock]
                    self.close_position(position,False)

    # 获取个股前n天的m日增幅值序列
    # 增加缓存避免当日多次获取数据
    def __get_pct_change(self,security, n, m):
        pct_change = None
        if security in self.pct_change.keys():
            pct_change = self.pct_change[security]
        else:
            h = attribute_history(security, n, unit='1d', fields=('close'), skip_paused=True)
            pct_change = h['close'].pct_change(m) # 3日的百分比变比（即3日涨跌幅）
            self.pct_change[security] = pct_change
        return pct_change
    
    # 计算个股止盈阈值
    # 算法：个股250天内最大的n日涨幅
    # 返回正值
    def __get_stop_profit_threshold(self,security, n = 3):
        pct_change = self.__get_pct_change(security, 250, n)
        maxr = pct_change.max()
        
        # 数据不足时，计算的maxr为nan
        # 理论上maxr可能为负
        if (not isnan(maxr)) and maxr != 0:
            return abs(maxr)
        return 0.30 # 默认配置止盈阈值最大涨幅为30%
    
    def when_sell_stock(self,position,order,is_normal):
        if order.status == OrderStatus.held and order.filled == order.amount:
            # 全部成交则删除相关证券的最高价缓存
            if position.security in self.last_high:
                self.last_high.pop(position.security)
        pass
    
    def when_buy_stock(self,stock,order):
        self.last_high[stock] = get_close_price(stock, 1, '1m')
        pass
    
    def after_trading_end(self,context):
        self.pct_change = {}
        pass
    def __str__(self):
        return '个股止盈器:[当前缓存价格数: %d ]'%(len(self.__last_high))

''' ----------------------最高价最低价比例止损------------------------------'''
class Stop_loss_by_price(Adjust_condition):
    __name__='Stop_loss_by_price'
    def __init__(self,params):
        self.index = params.get('index','000001.XSHG')
        self.day_count = params.get('day_count',160)
        self.multiple = params.get('multiple',2.2)
        self.is_day_stop_loss_by_price = False
    def update_params(self,context,params):
        self.index = params.get('index',self.index)
        self.day_count = params.get('day_count',self.day_count)
        self.multiple = params.get('multiple',self.multiple)

    def handle_data(self,context, data):
        # 大盘指数前130日内最高价超过最低价2倍，则清仓止损
        # 基于历史数据判定，因此若状态满足，则当天都不会变化
        # 增加此止损，回撤降低，收益降低
    
        if not self.is_day_stop_loss_by_price:
            h = attribute_history(self.index, self.day_count, unit='1d', fields=('close', 'high', 'low'), skip_paused=True)
            low_price_130 = h.low.min()
            high_price_130 = h.high.max()
            if high_price_130 > self.multiple * low_price_130 and h['close'][-1]<h['close'][-4]*1 and  h['close'][-1]> h['close'][-100]:
                # 当日第一次输出日志
                self.log_info("==> 大盘止损，%s指数前130日内最高价超过最低价2倍, 最高价: %f, 最低价: %f" %(get_security_info(self.index).display_name, high_price_130, low_price_130))
                self.is_day_stop_loss_by_price = True
    
        if self.is_day_stop_loss_by_price:
            self.clear_position(context)

    def before_trading_start(self,context):
        self.is_day_stop_loss_by_price = False
        pass
    def __str__(self):
        return '大盘高低价比例止损器:[指数: %s] [参数: %s日内最高最低价: %s倍] [当前状态: %s]'%(
                self.index,self.day_count,self.multiple,self.is_day_stop_loss_by_price)
        
    @property
    def can_adjust(self):
        return not self.is_day_stop_loss_by_price

''' ----------------------三乌鸦止损------------------------------'''
class Stop_loss_by_3_black_crows(Adjust_condition):
    __name__='Stop_loss_by_3_black_crows'
    def __init__(self,params):
        self.index = params.get('index','000001.XSHG')
        self.dst_drop_minute_count = params.get('dst_drop_minute_count',60)
        # 临时参数
        self.is_last_day_3_black_crows = False
        self.t_can_adjust = True
        self.cur_drop_minute_count = 0
    def update_params(self,context,params):
        self.index = params.get('index',self.index )
        self.dst_drop_minute_count = params.get('dst_drop_minute_count',self.dst_drop_minute_count)
        
    def initialize(self,context):
        pass
    
    def handle_data(self,context, data):
        # 前日三黑鸦，累计当日每分钟涨幅<0的分钟计数
        # 如果分钟计数超过一定值，则开始进行三黑鸦止损
        # 避免无效三黑鸦乱止损
        if self.is_last_day_3_black_crows:
            if get_growth_rate(self.index, 1) < 0:
                self.cur_drop_minute_count += 1
    
            if self.cur_drop_minute_count >= self.dst_drop_minute_count:
                if self.cur_drop_minute_count == self.dst_drop_minute_count:
                    self.log_info("==> 超过三黑鸦止损开始")
                
                self.clear_position(context)
                self.t_can_adjust = False
        else:
            self.t_can_adjust = True
        pass
    
    def before_trading_start(self,context):
        self.is_last_day_3_black_crows = is_3_black_crows(self.index)
        if self.is_last_day_3_black_crows:
            self.log_info("==> 前4日已经构成三黑鸦形态")
        pass
    
    def after_trading_end(self,context):
        self.is_last_day_3_black_crows = False
        self.cur_drop_minute_count = 0
        pass
    
    def __str__(self):
        return '大盘三乌鸦止损器:[指数: %s] [跌计数分钟: %d] [当前状态: %s]'%(
            self.index,self.dst_drop_minute_count,self.is_last_day_3_black_crows)
        
    @property
    def can_adjust(self):
        return self.t_can_adjust

''' ----------------------28指数值实时进行止损------------------------------'''
class Stop_loss_by_28_index(Adjust_condition):
    __name__='Stop_loss_by_28_index'
    def __init__(self,params):
        self.index2 = params.get('index2','')
        self.index8 = params.get('index8','')
        self.index_growth_rate = params.get('index_growth_rate',0.01)
        self.dst_minute_count_28index_drop = params.get('dst_minute_count_28index_drop',120)
        # 临时参数
        self.t_can_adjust = True
        self.minute_count_28index_drop = 0
    def update_params(self,context,params):
        self.index2 = params.get('index2',self.index2)
        self.index8 = params.get('index8',self.index8)
        self.index_growth_rate = params.get('index_growth_rate',self.index_growth_rate)
        self.dst_minute_count_28index_drop = params.get('dst_minute_count_28index_drop',self.dst_minute_count_28index_drop)     
    def initialize(self,context):
        pass
    
    def handle_data(self,context, data):
        # 回看指数前20天的涨幅
        gr_index2 = get_growth_rate(self.index2)
        gr_index8 = get_growth_rate(self.index8)
    
        if gr_index2 <= self.index_growth_rate and gr_index8 <= self.index_growth_rate:
            if (self.minute_count_28index_drop == 0):
                self.log_info("当前二八指数的20日涨幅同时低于[%.2f%%], %s指数: [%.2f%%], %s指数: [%.2f%%]" \
                    %(self.index_growth_rate*100, 
                    get_security_info(self.index2).display_name, 
                    gr_index2*100, 
                    get_security_info(self.index8).display_name, 
                    gr_index8*100))
    
            self.minute_count_28index_drop += 1
        else:
            # 不连续状态归零
            if self.minute_count_28index_drop < self.dst_minute_count_28index_drop:
                self.minute_count_28index_drop = 0
    
        if self.minute_count_28index_drop >= self.dst_minute_count_28index_drop:
            if self.minute_count_28index_drop == self.dst_minute_count_28index_drop:
                self.log_info("==> 当日%s指数和%s指数的20日增幅低于[%.2f%%]已超过%d分钟，执行28指数止损" \
                    %(get_security_info(self.index2).display_name, get_security_info(self.index8).display_name, self.index_growth_rate*100, self.dst_minute_count_28index_drop))
    
            self.clear_position(context)
            self.t_can_adjust = False
        else:
            self.t_can_adjust = True
        pass
    
    def after_trading_end(self,context):
        self.t_can_adjust = False
        self.minute_count_28index_drop = 0
        pass
    
    def __str__(self):
        return '28指数值实时进行止损:[大盘指数: %s %s] [小盘指数: %s %s] [判定调仓的二八指数20日增幅 %.2f%%] [连续 %d 分钟则清仓] '%(
                self.index2,get_security_info(self.index2).display_name,
                self.index8,get_security_info(self.index8).display_name,
                self.index_growth_rate * 100,
                self.dst_minute_count_28index_drop)
        
    @property
    def can_adjust(self):
        return self.t_can_adjust

''' ----------------------统计类----------------------------'''
class Stat(Rule):
    __name__='Stat'
    def __init__(self,params):
        # 加载统计模块
        self.trade_total_count = 0
        self.trade_success_count = 0
        self.statis = {'win': [], 'loss': []}
        
    def after_trading_end(self,context):
        self.report(context)
    def when_sell_stock(self,position,order,is_normal):
        if order.filled > 0:
            # 只要有成交，无论全部成交还是部分成交，则统计盈亏
            self.watch(position.security, order.filled, position.avg_cost, position.price)
            
    def reset(self):
        self.trade_total_count = 0
        self.trade_success_count = 0
        self.statis = {'win': [], 'loss': []}

    # 记录交易次数便于统计胜率
    # 卖出成功后针对卖出的量进行盈亏统计
    def watch(self, stock, sold_amount, avg_cost, cur_price):
        self.trade_total_count += 1
        current_value = sold_amount * cur_price
        cost = sold_amount * avg_cost

        percent = round((current_value - cost) / cost * 100, 2)
        if current_value > cost:
            self.trade_success_count += 1
            win = [stock, percent]
            self.statis['win'].append(win)
        else:
            loss = [stock, percent]
            self.statis['loss'].append(loss)

    def report(self, context):
        cash = context.portfolio.cash
        totol_value = context.portfolio.portfolio_value
        position = 1 - cash/totol_value
        self.log_info("收盘后持仓概况:%s" % str(list(context.portfolio.positions)))
        self.log_info("仓位概况:%.2f" % position)
        self.print_win_rate(context.current_dt.strftime("%Y-%m-%d"), context.current_dt.strftime("%Y-%m-%d"), context)

    # 打印胜率
    def print_win_rate(self, current_date, print_date, context):
        if str(current_date) == str(print_date):
            win_rate = 0
            if 0 < self.trade_total_count and 0 < self.trade_success_count:
                win_rate = round(self.trade_success_count / float(self.trade_total_count), 3)

            most_win = self.statis_most_win_percent()
            most_loss = self.statis_most_loss_percent()
            starting_cash = context.portfolio.starting_cash
            total_profit = self.statis_total_profit(context)
            if len(most_win)==0 or len(most_loss)==0:
                return

            s = '\n------------绩效报表------------'
            s += '\n交易次数: {0}, 盈利次数: {1}, 胜率: {2}'.format(self.trade_total_count, self.trade_success_count, str(win_rate * 100) + str('%'))
            s += '\n单次盈利最高: {0}, 盈利比例: {1}%'.format(most_win['stock'], most_win['value'])
            s += '\n单次亏损最高: {0}, 亏损比例: {1}%'.format(most_loss['stock'], most_loss['value'])
            s += '\n总资产: {0}, 本金: {1}, 盈利: {2}, 盈亏比率：{3}%'.format(starting_cash + total_profit, starting_cash, total_profit, total_profit / starting_cash * 100)
            s += '\n--------------------------------'
            self.log_info(s)

    # 统计单次盈利最高的股票
    def statis_most_win_percent(self):
        result = {}
        for statis in self.statis['win']:
            if {} == result:
                result['stock'] = statis[0]
                result['value'] = statis[1]
            else:
                if statis[1] > result['value']:
                    result['stock'] = statis[0]
                    result['value'] = statis[1]

        return result

    # 统计单次亏损最高的股票
    def statis_most_loss_percent(self):
        result = {}
        for statis in self.statis['loss']:
            if {} == result:
                result['stock'] = statis[0]
                result['value'] = statis[1]
            else:
                if statis[1] < result['value']:
                    result['stock'] = statis[0]
                    result['value'] = statis[1]

        return result

    # 统计总盈利金额    
    def statis_total_profit(self, context):
        return context.portfolio.portfolio_value - context.portfolio.starting_cash
    def __str__(self):
        return '策略绩效统计'       
'''~~~~~~~~~~~~~~~~~~~~~~~~~~~基础函数~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~'''
def is_3_black_crows(stock):
    # talib.CDL3BLACKCROWS

    # 三只乌鸦说明来自百度百科
    # 1. 连续出现三根阴线，每天的收盘价均低于上一日的收盘
    # 2. 三根阴线前一天的市场趋势应该为上涨
    # 3. 三根阴线必须为长的黑色实体，且长度应该大致相等
    # 4. 收盘价接近每日的最低价位
    # 5. 每日的开盘价都在上根K线的实体部分之内；
    # 6. 第一根阴线的实体部分，最好低于上日的最高价位
    #
    # 算法
    # 有效三只乌鸦描述众说纷纭，这里放宽条件，只考虑1和2
    # 根据前4日数据判断
    # 3根阴线跌幅超过4.5%（此条件忽略）

    h = attribute_history(stock, 4, '1d', ('close','open'), skip_paused=True, df=False)
    h_close = list(h['close'])
    h_open = list(h['open'])

    if len(h_close) < 4 or len(h_open) < 4:
        return False
    
    # 一阳三阴
    if h_close[-4] > h_open[-4] \
        and (h_close[-1] < h_open[-1] and h_close[-2]< h_open[-2] and h_close[-3] < h_open[-3]):
        #and (h_close[-1] < h_close[-2] and h_close[-2] < h_close[-3]) \
        #and h_close[-1] / h_close[-4] - 1 < -0.045:
        return True
    return False
    

# 获取股票n日以来涨幅，根据当前价计算
# n 默认20日
def get_growth_rate(security, n=20):
    lc = get_close_price(security, n)
    #c = data[security].close
    c = get_close_price(security, 1, '1m')
    
    if not isnan(lc) and not isnan(c) and lc != 0:
        return (c - lc) / lc
    else:
        log.error("数据非法, security: %s, %d日收盘价: %f, 当前价: %f" %(security, n, lc, c))
        return 0

# 获取前n个单位时间当时的收盘价
def get_close_price(security, n, unit='1d'):
    return attribute_history(security, n, unit, ('close'), True)['close'][0]
    
#-------------------------------------------------------------------------------------------
#-------------------------------------------------------------------------------------------
#-------------------------------------------------------------------------------------------
#-------------------------------------------------------------------------------------------
#多因子部分内容
#-------------------------------------------------------------------------------------------
#-------------------------------------------------------------------------------------------
#-------------------------------------------------------------------------------------------
#-------------------------------------------------------------------------------------------

# 得到因子数据
def get_factors(fdate,factors):
    #stock_set = get_index_stocks('000300.XSHG',fdate)
    q = query(
        valuation.code, # 股票代码
        valuation.circulating_market_cap, # CMC 流通市值
        valuation.market_cap, # MC 总市值 
        valuation.circulating_market_cap/valuation.capitalization*10000, # CMC/C 流通市值（亿）/总股本(万) （收盘价） 
        balance.total_owner_equities/valuation.market_cap/100000000, # TOE/MC 每元所有者权益
        valuation.pb_ratio, # PB 市净率
        income.net_profit/valuation.market_cap/100000000, # NP/MC 每元所有者净利润
        income.total_profit/valuation.market_cap/100000000, # TP/MC 每元利润总额
        balance.total_assets/valuation.market_cap/100000000, # TA/MC 每元资产总额
        income.operating_profit/valuation.market_cap/100000000, # OP/MC 每元营业利润
        balance.capital_reserve_fund/valuation.market_cap/100000000, # CRF/MC 每元资本公积
        valuation.ps_ratio, # PS 市销率
        income.operating_revenue/valuation.market_cap/100000000, # OR/MC 每元营业收入
        balance.retained_profit/valuation.market_cap/100000000, # RP/MC 每元未分配利润
        balance.total_liability/balance.total_sheet_owner_equities,# TL/TA 资产负债率
        
        balance.total_current_assets/balance.total_current_liability, # TCA/TCL  流动比率
        valuation.pe_ratio, # PE 市盈率
        income.operating_revenue*indicator.roa/income.net_profit, # OR*ROA/NP  总资产周转率        
        indicator.gross_profit_margin, # GPM 销售毛利率
        
        indicator.inc_revenue_year_on_year, # IRYOY  营业收入同比增长率(%) 
        indicator.inc_revenue_annual, # IRA 营业收入环比增长率(%)
        indicator.inc_net_profit_year_on_year, # INPYOY 净利润同比增长率(%)
        indicator.inc_net_profit_annual, # INPA  净利润环比增长率(%) 
        indicator.net_profit_margin, # NPM  销售净利率(%) 
        indicator.operation_profit_to_total_revenue, # OPTTR  营业利润/营业总收入(%) 
        valuation.capitalization,# C 总股本
        valuation.circulating_cap, # CC 流通股本(万股)
        valuation.pcf_ratio, # PR 市现率
        valuation.pe_ratio_lyr, # PRL 市盈率LYR
        indicator.roe, # ROE  净资产收益率ROE(%) 
        indicator.roa, # ROA  总资产净利率ROA(%) 
        
        indicator.eps # EPS 每股盈余
        
        
        ).filter(
        #valuation.code.in_(stock_set),
        valuation.circulating_market_cap
    )
    fdf = get_fundamentals(q, date=fdate)
    #print fdf
    fdf.index = fdf['code']
    fdf.columns = ['code'] + factors
    # 行：选择全部，列，选择之后全部
    return fdf.iloc[:,1:]

# 计算股票回报
def caculate_port_return(port,startdate,enddate,CMC):
    close1 = get_price(port, startdate, startdate, 'daily', ['close'])
    close2 = get_price(port, enddate, enddate, 'daily',['close'])
    # 个股一个月涨跌幅*流通市值，得到一个月流通市值涨跌额
    # 所有股票一个月流通市值涨跌额加总，得到一个月流通市值总涨跌额
    # 一个月流通市值总涨跌额 和 一个月前流通市值之比，得到流通市值涨跌幅度
    weighted_m_return = ((close2['close'].ix[0,:]/close1['close'].ix[0,:]-1)*CMC).sum()/(CMC.ix[port].sum()) 
    return weighted_m_return

# 计算基准回报
def caculate_benchmark_return(startdate,enddate):
    close1 = get_price(['000001.XSHG'],startdate,startdate,'daily',['close'])['close']
    close2 = get_price(['000001.XSHG'],enddate, enddate, 'daily',['close'])['close']
    benchmark_return = (close2.ix[0,:]/close1.ix[0,:]-1).sum()
    return benchmark_return

# 得到收益情况
def get_return_values(date_list, factors, values_return_dict_history):
    try:
        date_history = values_return_dict_history.keys()
        result = values_return_dict_history
    except:
        date_history = []
        result = {} 
    date_temp_list = [ i for i in date_list[:-1] if i not in date_history ]
    if len(date_temp_list) == 0:
        return values_return_dict_history
    
    # 只要date_temp_list在date_list中有上一个，就增加
    for date in date_temp_list:
        if date_list.index(date) > 0 :
            date_add = date_list[date_list.index(date)-1]
            date_temp_list = [date_add] + date_temp_list
    log.info("date_temp_list2: %s" % date_temp_list)
    # 如果date_temp_list的最后一个在data_list中也是最后一个，则去掉
    if  date_list.index(date_temp_list[-1]) == len(date_list) - 1 :
        date_temp_list.remove(date_temp_list[-1])
        
    log.info("date_temp_list3: %s" % date_temp_list)
    for date in date_temp_list:
        startdate = date_list[date_list.index(date)]
        enddate = date_list[date_list.index(date) + 1]
        # 如果已经存在，则不计算
        if enddate in result.keys():
            log.info("enddate %s in result.keys()" % enddate)
            continue
        
        log.info("回测日期: %s" % enddate)
        
        # 因子列表
        fdf = get_factors(startdate,factors)

        # 流通市值
        CMC = fdf['CMC']

        # 5个组合
        df = DataFrame(np.zeros(6*len(factors)).reshape(6,len(factors)),index = ['port1','port2','port3','port4','port5','benchmark'],columns = factors)

        for fac in factors:
            # 根据因子升序排序
            score = fdf[fac].order()

            # 将股票划分为5部分
            port1 = list(score.index)[: len(score)/5]
            port2 = list(score.index)[ len(score)/5+1: 2*len(score)/5]
            port3 = list(score.index)[ 2*len(score)/5+1: -2*len(score)/5]
            port4 = list(score.index)[ -2*len(score)/5+1: -len(score)/5]
            port5 = list(score.index)[ -len(score)/5+1: ]

            # 获得每一部分的收益
            df.ix['port1',fac] = caculate_port_return(port1,startdate,enddate,CMC)
            df.ix['port2',fac] = caculate_port_return(port2,startdate,enddate,CMC)
            df.ix['port3',fac] = caculate_port_return(port3,startdate,enddate,CMC)
            df.ix['port4',fac] = caculate_port_return(port4,startdate,enddate,CMC)
            df.ix['port5',fac] = caculate_port_return(port5,startdate,enddate,CMC)

            # 获得指数的收益
            df.ix['benchmark',fac] = caculate_benchmark_return(startdate,enddate)

        # 赋值给字典
        result[enddate]=df

    values_return_dict = result
    
    return values_return_dict

# 因子有效性检验
def effect_test(values_return, factors):
    total_return = {} # 总回报
    annual_return = {} # 年化符合收益
    excess_return = {} # 超额收益
    win_prob = {} # 胜率
    loss_prob = {} # 负率
    effect_test = {} # 有效性检验

    MinCorr = 0.3 # 最小相关阀值
    Minbottom = -0.05 # 最小超额亏损
    Mintop = 0.05 # 最小超额收益
    for fac in factors:
        effect_test[fac] = {} # 每个因子的有效性检验建立字典
        monthly = values_return[:,:,fac] # 获得各个月回报
        #print "fac ：%s" % fac

        total_return[fac] = (monthly+1).T.cumprod().iloc[-1,:]-1 # 总收益
        annual_return[fac] = total_return[fac] # 计算一年
        excess_return[fac] = annual_return[fac]- annual_return[fac][-1] # 减去指数收益，获得超额收益
        #判断因子有效性
        #1.年化收益与组合序列的相关性 大于 阀值
        # 一找你的有效性检验字典-收益相关性
        effect_test[fac]['corr'] = annual_return[fac][0:5].corr(Series([1,2,3,4,5],index = annual_return[fac][0:5].index))

        #2.高收益组合跑赢概率
        #因子小，收益小，port1是输家组合，port5是赢家组合
        if total_return[fac][0] < total_return[fac][-2]:
            loss_excess = monthly.iloc[0,:]-monthly.iloc[-1,:] # 相对指数，每个月的超额损失
            loss_prob[fac] = loss_excess[loss_excess<0].count()/float(len(loss_excess)) # 出现超额损失的概率
            win_excess = monthly.iloc[-2,:]-monthly.iloc[-1,:] # 相对指数，每个月的超额收益
            win_prob[fac] = win_excess[win_excess>0].count()/float(len(win_excess)) # 出现超额收益的概率

            # 因子的有效性检验字典-胜负率
            effect_test[fac]['prob_win'] = win_prob[fac]
            effect_test[fac]['prob_lose'] = loss_prob[fac]

            # 超额收益
            # 因子的有效性检验字典-赢家组合的年化收益，输家组合的年化收益
            effect_test[fac]["excess_return_win"] = excess_return[fac][-2]*100
            effect_test[fac]["excess_return_lose"] = excess_return[fac][0]*100

        #因子小，收益大，port1是赢家组合，port5是输家组合
        else:
            loss_excess = monthly.iloc[-2,:]-monthly.iloc[-1,:] # 相对指数，每个月的超额损失
            loss_prob[fac] = loss_excess[loss_excess<0].count()/float(len(loss_excess)) # 出现超额损失的概率
            win_excess = monthly.iloc[0,:]-monthly.iloc[-1,:] # 相对指数，每个月的超额收益
            win_prob[fac] = win_excess[win_excess>0].count()/float(len(win_excess)) # 出现超额收益的概率

            # 因子的有效性检验字典-胜负率
            effect_test[fac]['prob_win'] = win_prob[fac]
            effect_test[fac]['prob_lose'] = loss_prob[fac]

            #超额收益
            # 因子的有效性检验字典-赢家组合的年化收益，输家组合的年化收益
            effect_test[fac]["excess_return_win"] = excess_return[fac][0]*100
            effect_test[fac]["excess_return_lose"] = excess_return[fac][-2]*100

    #effect_test[1]记录因子相关性，>0.5或<-0.5合格
    #effect_test[2]记录【赢家组合超额收益，输家组合超额收益】
    #effect_test[3]记录赢家组合跑赢概率和输家组合跑输概率。【>0.5,>0.4】合格(因实际情况，跑输概率暂时不考虑)
    effect_test_df = DataFrame(effect_test)
    effect_test_df_T = effect_test_df.T

    # 条件1 相关性绝对值大于0.5,值越大越有效
    #effect_test_df_T = effect_test_df_T[abs(effect_test_df_T['corr']) > 0.5]

    # 条件3 胜率大于0.5，胜率越大效果越好
    #effect_test_df_T = effect_test_df_T[effect_test_df_T['prob_win'] > 0.4]

    return effect_test_df_T

def caculate_score(scores_return_panel, date_score, effect_test_df_T, effective_factors):
    # 有效因子年，半年，季，月，周 回报结果
    timesOfReturn = ['year','halfyear','season','month','week']
    score_df = DataFrame(np.zeros(len(effective_factors)*len(timesOfReturn)).reshape(len(effective_factors),len(timesOfReturn)),index = effective_factors,columns = timesOfReturn)
    for fac in effective_factors:
        # 相关度为负数，因子小收益大；相关度为正数，因子大收益大
        if effect_test_df_T.ix[fac,"corr"] < 0:
            strCorr = "port1"
        else:
            strCorr = "port5"
        returns = []
        date_list = scores_return_panel.items.tolist()
        for date in date_score[:-1]:
            i = date_list.index(date)+1
            returns.append((scores_return_panel[date_list[i:],strCorr,fac].T+1).cumprod()[scores_return_panel.items.tolist()[-1]]-1)
            
        score_df.ix[fac] = returns

    # 因子回报排名
    for column in timesOfReturn:
        score_df = score_df.sort(columns=[column], ascending=[False])
        score_df.reset_index(range(1,len(score_df) + 1), inplace = True)
        score_df.index = score_df.index + 1
        score_df[column + '_rank'] = score_df.index
        if column == 'year':
            score_df.rename(columns={"index":"Factors"}, inplace = True)
        else:
            score_df.drop(['index'], axis=1, inplace=True)
        score_df['year_rank'] = score_df.index

    # 计分
    score_df['score'] = score_df['year_rank']*0.1 + score_df['halfyear_rank']*0.2 +  score_df['season_rank']*0.4 + score_df['month_rank']*0.3 + score_df['week_rank']*0.15 
    score_df = score_df.sort(columns=['score'], ascending=[True])   
    
    return score_df

def get_multifactorial(context):    
    
    # 今天和一年前的今天
    #today = pd.datetime.today()
    today = context.current_dt
    yearBefore = today-timedelta(days=365)
    start = yearBefore.strftime('%Y-%m-%d')  # 开始日期
    end = today.strftime('%Y-%m-%d')  # 截止日期
    
    # 获得一年的交易日列表
    date_df = get_price('000001.XSHG', start_date=start, end_date=end, frequency='daily', fields=['close'], fq=None)
    date_list = date_df.index.tolist()
    
    # 计分日期 date_score
    i = -2
    date_score = [date_list[1]]# 1年前
    date_score.append(date_list[-120 + i]) # 半年度前
    date_score.append(date_list[-60 + i]) # 1季度前
    date_score.append(date_list[-20 + i]) # 1月前
    date_score.append(date_list[-5 + i]) # 1周前
    date_score.append(date_list[i]) # 当日
    
    # 因子
    #factors = ['CMC','MC','CMC/C','TOE/MC','PB','NP/MC','TP/MC','TA/MC','OP/MC','CRF/MC','PS','OR/MC','RP/MC','TL/TA','TCA/TCL','PE','OR*ROA/NP','GPM']
    g.factors = ['CMC','MC','CMC/C','TOE/MC','PB','NP/MC','TP/MC','TA/MC','OP/MC','CRF/MC','PS','OR/MC','RP/MC','TL/TA','TCA/TCL','PE','OR*ROA/NP','GPM','IRYOY','IRA','INPYOY','INPA','NPM','OPTTR','C','CC','PR','PRL','ROE','ROA','EPS']
    
    # 每月回报
    try:
        values_return_dict = get_return_values(date_list, g.factors, g.values_return_dict_history)
    except:
        # 读取文件
        body = read_file("values_return_dict_history_20170429.pkl")
        g.values_return_dict_history = pickle.load(StringIO(body))
        values_return_dict = get_return_values(date_list, g.factors, g.values_return_dict_history)
    
    # 记录历史，方便回测
    g.values_return_dict_history = values_return_dict
    # 文件写入
    #使用pickle模块从文件中重构python对象
    content = pickle.dumps(g.values_return_dict_history) # 该方法返回字符串
    write_file('values_return_dict_history_20170429.pkl', content, append=False)
    print "序列化保存对象：g.values_return_dict_history"
    
    # 变成panel
    values_return_panel = pd.Panel(values_return_dict)[date_list[1:],:,:]
    
    # 得到年、季、月、周、日收益
    indexStart = date_list.index(date_score[0]) # 第一个日期
    indexEnd = date_list.index(date_score[-1]) # 最后一个日期
    # 获得date_score对应的日期
    scores_return_panel = pd.Panel(g.values_return_dict_history)[date_list[indexStart:indexEnd+1],:,:]
    
    # 因子检验
    effect_test_df_T = effect_test(values_return_panel, g.factors)
    # 有效因子
    effective_factors = effect_test_df_T.index.tolist()
    # 计算得分
    score_df = caculate_score(scores_return_panel, date_score, effect_test_df_T, effective_factors)
    
    # 前三个
    fac_num = len(g.factors)*0.25
    list = score_df['Factors'].tolist()[:int(fac_num)]
    effect_test_df_T['ascending'] = effect_test_df_T['corr'] < 0
    g.resultFac = effect_test_df_T['ascending'].T[list]
    #log.info("g.resultFac: %s"% g.resultFac)
    
    try:
        log.info( "上次因子：g.fac: %s" % g.fac)
        log.info( "上次排序：g.ascending: %s" % g.ascending)
    except:
        log.info("无上次因子和排序，第一次运行。")
        g.fac = ""
        
    if g.fac not in list:
        g.fac = g.resultFac.index[0]
    #g.fac = g.resultFac.index[0]
    g.ascending = g.resultFac.ix[g.fac]
    log.info( "本次因子：g.fac: %s" % g.fac)
    log.info( "本次排序：g.ascending: %s" % g.ascending)

    