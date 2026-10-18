# Clone from JoinQuant
# postId: 8cc0c05b533fa72d37047ace149b98ad
# backtestId: 8dca7322b8c920978e9dbf68773b78c9
# title: 首席质量因子 - Gross Profitability

#enable_profile()
#version 1.41
import numpy as np
import talib
import pandas
import scipy as sp
import scipy.optimize
import datetime as dt
from scipy import linalg as sla
from scipy import spatial
from jqdata import gta
from jqdata import *
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import statsmodels.api as sm

def initialize(context):
    #用沪深 300 做回报基准
    set_benchmark('000300.XSHG')
    # 滑点、真实价格
    set_slippage(FixedSlippage(0.000))
    set_option('use_real_price', True)

    # 关闭部分log
    log.set_level('order', 'error')

def after_code_changed(context):
    g.quantlib = quantlib()
    # 定义风险敞口
    g.quantlib.fun_set_var(context, 'riskExposure', 0.03)
    # 正态分布概率表，标准差倍数以及置信率
    # 1.96, 95%; 2.06, 96%; 2.18, 97%; 2.34, 98%; 2.58, 99%; 5, 99.9999%
    g.quantlib.fun_set_var(context, 'confidencelevel', 1.96)
    #g.quantlib.fun_set_var(context, 'confidencelevel', 2.58)
    # 调仓参数
    g.quantlib.fun_set_var(context, 'hold_cycle', 30)
    g.quantlib.fun_set_var(context, 'hold_periods', 0)
    g.quantlib.fun_set_var(context, 'stock_list', [])
    g.quantlib.fun_set_var(context, 'position_price', {})
    g.quantlib.fun_set_var(context, 'version', 1.3)

    if context.version < 1.3:
        context.hold_periods = 0
        context.riskExposure = 0.03
        context.version = 1.3

def before_trading_start(context):
    # 定义股票池
    moneyfund = ['511880.XSHG','511010.XSHG','511220.XSHG']
    fund = []
    # 上市不足 60 天的剔除掉
    context.moneyfund = g.quantlib.fun_delNewShare(context, moneyfund, 60)
    context.fund = g.quantlib.fun_delNewShare(context, fund, 60)

    # 记录盘前收益
    context.returns = {}
    context.returns['algo_before_returns'] = context.portfolio.returns

def handle_data(context, data):

    # 引用 lib
    g.GP        = Gross_Profitability_lib()
    g.quantlib  = quantlib()
    context.msg = ""

    # 检查是否需要调仓
    rebalance_flag, context.position_price, context.hold_periods, msg = \
        g.quantlib.fun_needRebalance('GP algo ', context.moneyfund, context.stock_list, context.position_price, \
            context.hold_periods, context.hold_cycle, 0.25)
    context.msg += msg

    statsDate = context.current_dt.date()
    trade_style = False    # True 会交易进行类似 100股的买卖，False 则只有在仓位变动 >25% 的时候，才产生交易
    if rebalance_flag:
        stock_list, bad_stock_list = [], []
        GP_stock_list = g.GP.fun_get_stock_list(context, 5, statsDate, bad_stock_list, stock_list)
        stock_list = stock_list + GP_stock_list
        # 分配仓位
        equity_ratio, bonds_ratio = g.quantlib.fun_assetAllocationSystem(stock_list, context.moneyfund, statsDate)

        risk_ratio = 0
        if len(equity_ratio.keys()) >= 1:
            risk_ratio = context.riskExposure / len(equity_ratio.keys())
        # 分配头寸，根据预设的风险敞口，计算交易时的比例
        position_ratio = g.quantlib.fun_calPosition(equity_ratio, bonds_ratio, 1.0, risk_ratio, context.moneyfund, context.portfolio.portfolio_value, context.confidencelevel, statsDate)
        trade_style = True
        context.stock_list = position_ratio.keys()

        # 更新待购价格
        context.position_price = g.quantlib.fun_update_positions_price(position_ratio)
        # 卖掉已有且不在待购清单里的股票
        for stock in context.portfolio.positions.keys():
            if stock not in position_ratio:
                position_ratio[stock] = 0
        context.position_ratio = position_ratio
        print position_ratio

    # 调仓，执行交易
    g.quantlib.fun_do_trade(context, context.position_ratio, context.moneyfund, trade_style)

class Gross_Profitability_lib():
    def fun_get_stock_list(self, context, hold_number, statsDate=None, bad_stock_list=[], candidate=[]):
        df = get_fundamentals(
            query(valuation.code, valuation.market_cap, valuation.pe_ratio, valuation.ps_ratio, valuation.pb_ratio)
        )

        # 1) 总市值全市场从大到小前80%
        fCap = df.sort(['market_cap'], ascending=[False])
        fCap = fCap.reset_index(drop = True)
        fCap = fCap[0:int(len(fCap)*0.8)]
        sListCap = list(fCap['code'])

        # 2）市盈率全市场从小到大前40%（剔除市盈率为负的股票）
        fPE = df.sort(['pe_ratio'], ascending=[True])
        fPE = fPE.reset_index(drop = True)
        fPE = fPE[fPE.pe_ratio > 0]
        fPE = fPE.reset_index(drop = True)
        fPE = fPE[0:int(len(fPE)*0.4)]
        sListPE = list(fPE['code'])

        # 3）pb全市场从小到大前40%（剔除pb为负的股票）
        fPB = df.sort(['pb_ratio'], ascending=[True])
        fPB = fPB.reset_index(drop = True)
        fPB = fPB[fPB.pb_ratio > 0]
        fPB = fPB.reset_index(drop = True)
        fPB = fPB[0:int(len(fPB)*0.4)]
        sListPB = list(fPB['code'])

        # 4）市收率小于2.5
        fPS = df[df.ps_ratio < 2.5]
        sListPS = list(fPS['code'])

        # 5）同时满足上述3条的股票，按照股息率从大到小排序，选出股息率最高的 n 只股票
        good_stocks = list(set(sListCap) & set(sListPE) & set(sListPS) & set(sListPB))
        #print len(good_stocks)
        GP_ratio = {}

        df = get_fundamentals(
            query(income.code, income.total_operating_revenue, income.total_operating_cost, balance.total_assets),
            date = statsDate - dt.timedelta(1)
        )

        df = df.fillna(value = 0)
        df = df[df.total_operating_revenue > 0]
        df = df.reset_index(drop = True)
        df = df[df.total_assets > 0]
        df = df.reset_index(drop = True)
        df = df[df.code.isin(good_stocks)]
        df = df.reset_index(drop = True)
        df['GP'] = 1.0*(df['total_operating_revenue'] - df['total_operating_cost']) / df['total_assets']

        df = df.drop(['total_assets', 'total_operating_revenue', 'total_operating_cost'], axis=1)
        df = df.sort(columns='GP', ascending=False)
        #print df.head(10)
        stock_list = list(df['code'])

        positions_list = context.portfolio.positions.keys()
        stock_list = g.quantlib.unpaused(stock_list, positions_list)
        stock_list = g.quantlib.remove_st(stock_list, statsDate)

        stock_list = stock_list[:hold_number*10]
        stock_list = g.quantlib.remove_limit_up(stock_list, positions_list)

        return stock_list[:hold_number]

class quantlib():

    def fun_set_var(self, context, var_name, var_value):
        if var_name not in dir(context):
            setattr(context, var_name, var_value)

    def fun_check_price(self, algo_name, stock_list, position_price, gap_trigger):
        flag = False
        msg = ""
        if stock_list:
            h = history(1, '1d', 'close', stock_list, df=False)
            for stock in stock_list:
                curPrice = h[stock][0]
                if stock not in position_price:
                    position_price[stock] = curPrice
                oldPrice = position_price[stock]
                if oldPrice != 0:
                    deltaprice = abs(curPrice - oldPrice)
                    if deltaprice / oldPrice > gap_trigger:
                        msg = algo_name + "需要调仓: " + stock + "，现价: " + str(curPrice) + " / 原价格: " + str(oldPrice) + "\n"
                        flag = True
                        return flag, position_price, msg
        return flag, position_price, msg

    def fun_needRebalance(self, algo_name, moneyfund, stock_list, position_price, hold_periods, hold_cycle, gap_trigger):
        msg = ""
        msg += algo_name + "离下次调仓还剩 " + str(hold_periods) + " 天\n"
        rebalance_flag = False
        
        stocks_count = 0
        for stock in stock_list:
            if stock not in moneyfund:
                stocks_count += 1
        if stocks_count == 0:
            msg += algo_name + "调仓，因为持股数为 0 \n"
            rebalance_flag = True
        elif hold_periods == 0:
            msg += algo_name + "调仓，因为持股天数剩余为 0 \n"
            rebalance_flag = True
        if not rebalance_flag:
            rebalance_flag, position_price, msg2 = self.fun_check_price(algo_name, stock_list, position_price, gap_trigger)
            msg += msg2
        
        if rebalance_flag:
            hold_periods = hold_cycle
        else:
            hold_periods -= 1

        return rebalance_flag, position_price, hold_periods, msg

    # 更新持有股票的价格，每次调仓后跑一次
    def fun_update_positions_price(self, ratio):
        position_price = {}
        if ratio:
            h = history(1, '1m', 'close', ratio.keys(), df=False)
            for stock in ratio.keys():
                if ratio[stock] > 0:
                    position_price[stock] = round(h[stock][0], 3)
        return position_price

    def fun_assetAllocationSystem(self, stock_list, moneyfund, statsDate=None):
        def __fun_getEquity_ratio(__stocklist, type, limit_up=1.0, limit_low=0.0, statsDate=None):
            __ratio = {}
            if __stocklist:
                if type == 1: #风险平价 历史模拟法
                    __ratio = self.fun_calStockWeight_by_risk(1.96, __stocklist, limit_up, limit_low, statsDate)
                elif type == 2: #最小方差配仓
                    __ratio = self.fun_calStockWeight(__stocklist, limit_up, limit_low)
                elif type == 3: #马科维奇算法配仓
                    __ratio = self.fun_cal_Weight_by_Markowitz(__stocklist)
                elif type == 5: # 风险平价 方差-协方差法
                    __ratio = self.fun_calWeight_by_RiskParity(__stocklist, statsDate)
                else: #等权重
                    for stock in __stocklist:
                        __ratio[stock] = 1.0/len(__stocklist)

            return __ratio

        equity_ratio = __fun_getEquity_ratio(stock_list, 0, 1.0, 0.0, statsDate)
        bonds_ratio  = __fun_getEquity_ratio(moneyfund, 0, 1.0, 0.0, statsDate)

        return equity_ratio, bonds_ratio

    def fun_calPosition(self, equity_ratio, bonds_ratio, algo_ratio, risk_ratio, moneyfund, portfolio_value, confidencelevel, statsDate=None):
        '''
        equity_ratio 资产配仓结果
        bonds_ratio 债券配仓结果
        algo_ratio 策略占市值的百分比
        risk_ratio 每个标的承受的风险系数
        '''
        trade_ratio = equity_ratio # 例子，简单处理，略过
        return trade_ratio

    def fun_do_trade(self, context, trade_ratio, moneyfund, trade_style):

        def __fun_tradeBond(context, stock, curPrice, Value):
            curValue = float(context.portfolio.positions[stock].total_amount * curPrice)
            deltaValue = abs(Value - curValue)
            if deltaValue > (curPrice*200):
                if Value > curValue:
                    cash = context.portfolio.cash
                    if cash > (curPrice*200):
                        self.fun_trade(context, stock, Value)
                else:
                    self.fun_trade(context, stock, Value)

        def __fun_tradeStock(context, curPrice, stock, ratio, trade_style):
            total_value = context.portfolio.portfolio_value
            if stock in moneyfund:
                __fun_tradeBond(context, stock, curPrice, total_value * ratio)
            else:
                curValue = context.portfolio.positions[stock].total_amount * curPrice
                Quota = total_value * ratio
                if Quota:
                    if abs(Quota - curValue) / Quota >= 0.25 or trade_style:
                        if Quota > curValue:
                            #if curPrice > context.portfolio.positions[stock].avg_cost:
                            self.fun_trade(context, stock, Quota)
                        else:
                            self.fun_trade(context, stock, Quota)
                else:
                    if curValue > 0:
                        self.fun_trade(context, stock, Quota)
    
        trade_list = trade_ratio.keys()
        myholdstock = context.portfolio.positions.keys()
        stock_list = list(set(trade_list).union(set(myholdstock)))
        total_value = context.portfolio.portfolio_value
    
        # 已有仓位
        holdDict = {}
        h = history(1, '1d', 'close', stock_list, df=False)
        for stock in myholdstock:
            tmpW = round((context.portfolio.positions[stock].total_amount * h[stock])/total_value, 2)
            holdDict[stock] = float(tmpW)
    
        # 对已有仓位做排序
        tmpDict = {}
        for stock in holdDict:
            if stock in trade_ratio:
                tmpDict[stock] = round((trade_ratio[stock] - holdDict[stock]), 2)
        tradeOrder = sorted(tmpDict.items(), key=lambda d:d[1], reverse=False)

        # 交易已有仓位的股票，从减仓的开始，腾空现金
        _tmplist = []
        for idx in tradeOrder:
            stock = idx[0]
            __fun_tradeStock(context, h[stock][-1], stock, trade_ratio[stock], trade_style)
            _tmplist.append(stock)

        # 交易新股票
        for i in range(len(trade_list)):
            stock = trade_list[i]
            if len(_tmplist) != 0 :
                if stock not in _tmplist:
                    __fun_tradeStock(context, h[stock][-1], stock, trade_ratio[stock], trade_style)
            else:
                __fun_tradeStock(context, h[stock][-1], stock, trade_ratio[stock], trade_style)

    def unpaused(self, stock_list, positions_list):
        current_data = get_current_data()
        tmpList = []
        for stock in stock_list:
            if not current_data[stock].paused or stock in positions_list:
                tmpList.append(stock)
        return tmpList

    def remove_st(self, stock_list, statsDate):
        current_data = get_current_data()
        return [s for s in stock_list if not current_data[s].is_st]

    # 剔除涨停板的股票（如果没有持有的话）
    def remove_limit_up(self, stock_list, positions_list):
        h = history(1, '1m', 'close', stock_list, df=False, skip_paused=False, fq='pre')
        h2 = history(1, '1m', 'high_limit', stock_list, df=False, skip_paused=False, fq='pre')
        tmpList = []
        for stock in stock_list:
            if h[stock][0] < h2[stock][0] or stock in positions_list:
                tmpList.append(stock)

        return tmpList

    # 剔除上市时间较短的产品
    def fun_delNewShare(self, context, equity, deltaday):
        deltaDate = context.current_dt.date() - dt.timedelta(deltaday)
    
        tmpList = []
        for stock in equity:
            if get_security_info(stock).start_date < deltaDate:
                tmpList.append(stock)
    
        return tmpList

    def fun_trade(self, context, stock, value):
        self.fun_setCommission(context, stock)
        order_target_value(stock, value)

    def fun_setCommission(self, context, stock):
        if stock in context.moneyfund:
            set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0, close_commission=0, close_today_commission=0, min_commission=0), type='fund')
        else:
            set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
