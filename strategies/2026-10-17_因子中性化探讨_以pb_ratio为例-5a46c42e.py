# Clone from JoinQuant
# postId: 5a46c42e797d6154eafd56fdad12415c
# backtestId: dfa989cffb0b8b1cf25d4b4fb62f0597
# title: 因子中性化探讨（以pb_ratio为例）

import numpy as np
import talib
import pandas
import scipy as sp
import scipy.optimize
import datetime as dt
from scipy import linalg as sla
from scipy import spatial
from jqdata import gta

def initialize(context):
    context.lowPB_version = 1.0
    #用沪深 300 做回报基准
    set_benchmark('000300.XSHG')

    #固定滑点，0.002 元
    set_slippage(FixedSlippage(0.002))
    set_option('use_real_price', True)

    # 关闭部分log
    log.set_level('order', 'error')
    # 定义全局变量
    context.lowPB_ratio   = 1.0

    # for lowPB algorithms
    # 正态分布概率表，标准差倍数以及置信率
    # 1.96, 95%; 2.06, 96%; 2.18, 97%; 2.34, 98%; 2.58, 99%; 5, 99.9999%
    context.lowPB_confidencelevel = 1.96
    context.lowPB_hold_periods, context.lowPB_hold_cycle = 0, 30
    context.lowPB_stock_list = []
    context.lowPB_position_price = {}
    context.highDivid_enable_flag = True
    context.lowPB_version = 0.0

    g.quantlib = quantlib()
    run_daily(fun_main, '10:30')

#def handle_data(context, data):
#    pass
    
def fun_main(context):

    lowPB_trade_ratio = lowPB_algo(context, context.lowPB_ratio, context.portfolio.portfolio_value)
    # 调仓，执行交易
    if context.lowPB_hold_periods == context.lowPB_hold_cycle:
        g.quantlib.fun_do_trade(context, lowPB_trade_ratio, context.lowPB_moneyfund)

def lowPB_algo(context, lowPB_ratio, portfolio_value):
    '''
    high Divid algorithms
    输入参数：lowPB_ratio, protfolio_value
    输出参数：lowPB_trade_ratio
    自有类  : lowPB_lib
    调用类  : quantlib
    '''
    # 更新持有股票的价格，每次调仓后跑一次
    def __fun_update_positions(context, equity_ratio):
        if equity_ratio:
            context.lowPB_position_price = {}
            price = history(1, '1m', 'close', equity_ratio.keys(), df=False)
            for stock in equity_ratio.keys():
                if equity_ratio[stock] > 0 and stock not in context.lowPB_moneyfund:
                    context.lowPB_position_price[stock] = price[stock][0]

    # 引用 lib
    g.lowPB = lowPB_lib()
    # 引用 quantlib
    g.quantlib = quantlib()

    g.lowPB.fun_initialize(context)

    # rebalance_flag 用来标记是否需要调仓
    rebalance_flag = g.lowPB.fun_needRebalance(context, 0.25)

    # 配仓，分配持股比例
    if rebalance_flag:
        # 取得代购高息股列表
        context.lowPB_stock_list = g.lowPB.fun_get_stock_list(context)
        # 分配仓位
        equity_ratio, bonds_ratio = g.lowPB.fun_assetAllocationSystem(context, context.lowPB_stock_list)
        # 更新待购股票价格
        __fun_update_positions(context, equity_ratio)
    else:
        # 如果不调仓，则沿用先前的持仓比例
        equity_ratio = context.lowPB_equity_ratio
        bonds_ratio  = context.lowPB_bonds_ratio
    
    # 更新标的配仓比例
    context.lowPB_equity_ratio = equity_ratio
    context.lowPB_bonds_ratio  = bonds_ratio

    # 分配头寸
    trade_ratio = {}
    if rebalance_flag:
        # 根据预设的风险敞口，计算交易时的比例
        trade_ratio = g.lowPB.fun_calPosition(context, equity_ratio, bonds_ratio, lowPB_ratio, portfolio_value)

        # 卖掉已有且不在待购清单里的股票
        stock_list = list(get_all_securities(['stock']).index)
        for stock in context.portfolio.positions.keys():
            if stock not in trade_ratio and stock in stock_list:
                trade_ratio[stock] = 0
    else:
        # 不调仓，则沿用先前的比例
        trade_ratio = context.lowPB_trade_ratio

    context.lowPB_trade_ratio = trade_ratio

    return trade_ratio

class lowPB_lib():

    def __init__(self, _period = '1d'):
        pass
    
    def fun_initialize(self, context):
        # 定义股票池
        lowPB_equity = context.lowPB_stock_list

        lowPB_moneyfund = ['511880.XSHG']

        # 上市不足 60 天的剔除掉
        context.lowPB_equity    = g.quantlib.fun_delNewShare(context, lowPB_equity, 60)
        context.lowPB_moneyfund = g.quantlib.fun_delNewShare(context, lowPB_moneyfund, 60)

        context.lowPB_pool         = context.lowPB_equity + context.lowPB_moneyfund
        context.lowPB_hold_numbers = 10
        context.lowPB_risk_ratio   = 0.03 / context.lowPB_hold_numbers

        # 更新 初始化函数里的赋值
        if context.lowPB_version < 1.0:
            # 需更新的数值写在这
            context.lowPB_version = 1.0

    def fun_needRebalance(self, context, gap_trigger):

        def __fun_check_price(context, stock_list, gap_trigger):
            flag = False
            if stock_list:
                h = history(1, '1m', 'close', stock_list, df=False)
                for stock in stock_list:
                    curPrice = h[stock][0]
                    if stock not in context.lowPB_position_price:
                        context.lowPB_position_price[stock] = curPrice
                    oldPrice = context.lowPB_position_price[stock]
                    if oldPrice != 0:
                        deltaprice = abs(curPrice - oldPrice)
                        if deltaprice / oldPrice > gap_trigger:
                            print stock + "，现价: " + str(curPrice) + " / 原价格: " + str(oldPrice)
                            flag = True
                            return flag
            return flag

        # ------------------------------------------
        stock_list = context.lowPB_stock_list
        if len(stock_list) == 0:
            context.lowPB_hold_periods = context.lowPB_hold_cycle
            return True

        if context.lowPB_hold_periods == 0:
            context.lowPB_hold_periods = context.lowPB_hold_cycle
            return True
        else:
            context.lowPB_hold_periods -= 1

        if __fun_check_price(context, stock_list, gap_trigger):
            context.lowPB_hold_periods = context.lowPB_hold_cycle
            return True
        else:
            return False

    def fun_get_stock_list(self, context):
        today = context.current_dt
        #industry_list = g.quantlib.fun_get_industry_list()
        industry_list = ['J66', 'J67', 'J68', 'J69']

        lowPB_list = []
        lowPB_dict = {}
        for industry in industry_list:
            lowPB_dict = dict(lowPB_dict, **self.fun_get_goodstocks_from_industry(industry, today))

        lowPB_dict = sorted(lowPB_dict.items(), key=lambda d:d[1], reverse=False)

        stock_list = []
        for idx in lowPB_dict:
            stock_list.append(idx[0])

        return stock_list[:context.lowPB_hold_numbers]

    def fun_get_goodstocks_from_industry(self, industry, today):
        stock_list = get_industry_stocks(industry, today)
        df_pb = get_fundamentals(
            query(valuation.code, valuation.pb_ratio)
            .filter(valuation.code.in_(stock_list))
            .order_by(valuation.pb_ratio.asc())
        )
        #print df_pb
        pb_avg = df_pb['pb_ratio'].mean()
        pb_std = df_pb['pb_ratio'].std()
        # 标准化方法 1
        df_pb['neutralize'] = (df_pb['pb_ratio'] - pb_avg) / pb_std

        # 标准化方法 2
        pb_max = df_pb['pb_ratio'].max()
        pb_min = df_pb['pb_ratio'].min()
        df_pb['standardlize'] = (df_pb['pb_ratio'] - pb_min) / (pb_max - pb_min)
        #print df_pb
        pb_dict = {}
        tmpdict = df_pb.to_dict()
        for i in range(len(tmpdict['code'].keys())):
            # 需要看不同方法的选股结果，可以调整以下部分
            #pb_dict[tmpdict['code'][i]] = tmpdict['pb_ratio'][i]    #原始 pb_ratio
            pb_dict[tmpdict['code'][i]] = tmpdict['neutralize'][i] #标准化方法 1
            #pb_dict[tmpdict['code'][i]] = tmpdict['standardlize'][i] #标准化方法 2

        return pb_dict

    def fun_assetAllocationSystem(self, context, buylist):
        def __fun_getEquity_ratio(context, __stocklist):
            __ratio = {}
            # 按风险平价配仓
            if __stocklist:
                __ratio = g.quantlib.fun_calStockWeight_by_risk(context, 2.58, __stocklist)

            return __ratio

        equity_ratio = __fun_getEquity_ratio(context, buylist)
        bonds_ratio  = __fun_getEquity_ratio(context, context.lowPB_moneyfund)
    
        return equity_ratio, bonds_ratio

    def fun_calPosition(self, context, equity_ratio, bonds_ratio, lowPB_ratio, portfolio_value):

        #context.lowPB_risk_ratio  = 0.03
        #risk_money = context.portfolio.portfolio_value * context.lowPB_risk_ratio
        risk_ratio = 0
        for stock in equity_ratio.keys():
            if equity_ratio[stock] <> 0 and stock not in context.lowPB_moneyfund:
                risk_ratio += 1

        risk_money = context.portfolio.portfolio_value * risk_ratio * context.lowPB_risk_ratio
        #risk_money = context.portfolio.portfolio_value * risk_ratio * 0.06
        maxrisk_money = risk_money * 1.7
        equity_value = 0
        if equity_ratio:
            equity_value = g.quantlib.fun_getEquity_value(equity_ratio, risk_money, maxrisk_money, context.lowPB_confidencelevel)

        value_ratio = 0
        total_value = portfolio_value * lowPB_ratio
        if equity_value > total_value:
            bonds_value = 0
            value_ratio = 1.0 * lowPB_ratio
        else:
            value_ratio = (equity_value / total_value) * lowPB_ratio
            bonds_value = total_value - equity_value
        
        trade_ratio = {}

        for stock in equity_ratio.keys():
            if stock in trade_ratio:
                trade_ratio[stock] += round((equity_ratio[stock] * value_ratio), 3)
            else:
                trade_ratio[stock] = round((equity_ratio[stock] * value_ratio), 3)

        for stock in bonds_ratio.keys():
            if stock in trade_ratio:
                trade_ratio[stock] += round((bonds_ratio[stock] * bonds_value / total_value) * lowPB_ratio, 3)
            else:
                trade_ratio[stock] = round((bonds_ratio[stock] * bonds_value / total_value) * lowPB_ratio, 3)

        return trade_ratio

class quantlib():

    def __init__(self, _period = '1d'):
        pass

    def fun_diversity_by_industry(self, stock_list, max_num):
        if not stock_list:
            return stock_list

        industry_list = self.fun_get_industry_list()
        for industry in industry_list:
            i = 0
            stocks = get_industry_stocks(industry)
            for stock in stock_list:
                if stock in stocks:
                    i += 1
                    if i > max_num:
                        stock_list.remove(stock)

        return stock_list

    def fun_get_industry_list(self):
        industry = [
            'A01', # 农业 	1993-09-17
            'A02', # 林业 	1996-12-06
            'A03', # 畜牧业 	1997-06-11
            'A04', # 渔业 	1993-05-07
            'A05', # 农、林、牧、渔服务业 	1997-05-30
            'B06', # 煤炭开采和洗选业 	1994-01-06
            'B07', # 石油和天然气开采业 	1996-06-28
            'B08', # 黑色金属矿采选业 	1997-07-08
            'B09', # 有色金属矿采选业 	1996-03-20
            'B11', # 开采辅助活动 	2002-02-05
            'C13', # 农副食品加工业 	1993-12-15
            'C14', # 食品制造业 	1994-08-18
            'C15', # 酒、饮料和精制茶制造业 	1992-10-12
            'C17', # 纺织业 	1992-06-16
            'C18', # 纺织服装、服饰业 	1993-12-31
            'C19', # 皮革、毛皮、羽毛及其制品和制鞋业 	1994-04-04
            'C20', # 木材加工及木、竹、藤、棕、草制品业 	2005-05-10
            'C21', # 家具制造业 	1996-04-25
            'C22', # 造纸及纸制品业 	1993-03-12
            'C23', # 印刷和记录媒介复制业 	1994-02-24
            'C24', # 文教、工美、体育和娱乐用品制造业 	2007-01-10
            'C25', # 石油加工、炼焦及核燃料加工业 	1993-10-25
            'C26', # 化学原料及化学制品制造业 	1990-12-19
            'C27', # 医药制造业 	1993-06-29
            'C28', # 化学纤维制造业 	1993-07-28
            'C29', # 橡胶和塑料制品业 	1992-08-28
            'C30', # 非金属矿物制品业 	1992-02-28
            'C31', # 黑色金属冶炼及压延加工业 	1994-01-06
            'C32', # 有色金属冶炼和压延加工业 	1996-02-15
            'C33', # 金属制品业 	1993-11-30
            'C34', # 通用设备制造业 	1992-03-27
            'C35', # 专用设备制造业 	1992-07-01
            'C36', # 汽车制造业 	1992-07-24
            'C37', # 铁路、船舶、航空航天和其它运输设备制造业 	1992-03-31
            'C38', # 电气机械及器材制造业 	1990-12-19
            'C39', # 计算机、通信和其他电子设备制造业 	1990-12-19
            'C40', # 仪器仪表制造业 	1993-09-17
            'C41', # 其他制造业 	1992-08-14
            'C42', # 废弃资源综合利用业 	2012-10-26
            'D44', # 电力、热力生产和供应业 	1993-04-16
            'D45', # 燃气生产和供应业 	2000-12-11
            'D46', # 水的生产和供应业 	1994-02-24
            'E47', # 房屋建筑业 	1993-04-29
            'E48', # 土木工程建筑业 	1994-01-28
            'E50', # 建筑装饰和其他建筑业 	1997-05-22
            'F51', # 批发业 	1992-05-06
            'F52', # 零售业 	1992-09-02
            'G53', # 铁路运输业 	1998-05-11
            'G54', # 道路运输业 	1991-01-14
            'G55', # 水上运输业 	1993-11-19
            'G56', # 航空运输业 	1997-11-05
            'G58', # 装卸搬运和运输代理业 	1993-05-05
            'G59', # 仓储业 	1996-06-14
            'H61', # 住宿业 	1993-11-18
            'H62', # 餐饮业 	1997-04-30
            'I63', # 电信、广播电视和卫星传输服务 	1992-12-02
            'I64', # 互联网和相关服务 	1992-05-07
            'I65', # 软件和信息技术服务业 	1992-08-20
            'J66', # 货币金融服务 	1991-04-03
            'J67', # 资本市场服务 	1994-01-10
            'J68', # 保险业 	2007-01-09
            'J69', # 其他金融业 	2012-10-26
            'K70', # 房地产业 	1992-01-13
            'L71', # 租赁业 	1997-01-30
            'L72', # 商务服务业 	1996-08-29
            'M73', # 研究和试验发展 	2012-10-26
            'M74', # 专业技术服务业 	2007-02-15
            'N77', # 生态保护和环境治理业 	2012-10-26
            'N78', # 公共设施管理业 	1992-08-07
            'P82', # 教育 	2012-10-26
            'Q83', # 卫生 	2007-02-05
            'R85', # 新闻和出版业 	1992-12-08
            'R86', # 广播、电视、电影和影视录音制作业 	1994-02-24
            'R87', # 文化艺术业 	2012-10-26
            'S90', # 综合 	1990-12-10
            ]

        return industry

    def fun_do_trade(self, context, trade_ratio, moneyfund):
    
        def __fun_tradeStock(context, stock, ratio):
            total_value = context.portfolio.portfolio_value
            if stock in moneyfund:
                self.fun_tradeBond(context, stock, total_value * ratio)
            else:
                curPrice = history(1,'1d', 'close', stock, df=False)[stock][-1]
                curValue = context.portfolio.positions[stock].total_amount * curPrice
                Quota = total_value * ratio
                if Quota:
                    if abs(Quota - curValue) / Quota >= 0.25:
                        if Quota > curValue:
                            cash = context.portfolio.cash
                            if cash >= Quota * 0.25: # and curPrice > context.portfolio.positions[stock].avg_cost:
                                self.fun_trade(context, stock, Quota)
                        else:
                            self.fun_trade(context, stock, Quota)
                else:
                    self.fun_trade(context, stock, Quota)
    
        trade_list = trade_ratio.keys()
    
        myholdstock = context.portfolio.positions.keys()
        total_value = context.portfolio.portfolio_value
    
        # 已有仓位
        holdDict = {}
        h = history(1, '1d', 'close', myholdstock, df=False)
        for stock in myholdstock:
            tmpW = round((context.portfolio.positions[stock].total_amount * h[stock])/total_value, 2)
            holdDict[stock] = float(tmpW)
    
        # 对已有仓位做排序
        tmpDict = {}
        for stock in holdDict:
            if stock in trade_ratio:
                tmpDict[stock] = round((trade_ratio[stock] - holdDict[stock]), 2)
        tradeOrder = sorted(tmpDict.items(), key=lambda d:d[1], reverse=False)
    
        _tmplist = []
        for idx in tradeOrder:
            stock = idx[0]
            __fun_tradeStock(context, stock, trade_ratio[stock])
            _tmplist.append(stock)
    
        # 交易其他股票
        for i in range(len(trade_list)):
            stock = trade_list[i]
            if len(_tmplist) != 0 :
                if stock not in _tmplist:
                    __fun_tradeStock(context, stock, trade_ratio[stock])
            else:
                __fun_tradeStock(context, stock, trade_ratio[stock])

    def fun_getEquity_value(self, equity_ratio, risk_money, maxrisk_money, confidence_ratio):
        def __fun_getdailyreturn(stock, freq, lag):
            hStocks = history(lag, freq, 'close', stock, df=True)
            dailyReturns = hStocks.resample('D',how='last').pct_change().fillna(value=0, method=None, axis=0).values

            return dailyReturns

        def __fun_get_portfolio_dailyreturn(ratio, freq, lag):
            __portfolio_dailyreturn = []
            for stock in ratio.keys():
                if ratio[stock] != 0:
                    __dailyReturns = __fun_getdailyreturn(stock, freq, lag)
                    __tmplist = []
                    for i in range(len(__dailyReturns)):
                        __tmplist.append(__dailyReturns[i] * ratio[stock])
                    if __portfolio_dailyreturn:
                        __tmplistB = []
                        for i in range(len(__portfolio_dailyreturn)):
                            __tmplistB.append(__portfolio_dailyreturn[i]+__tmplist[i])
                        __portfolio_dailyreturn = __tmplistB
                    else:
                        __portfolio_dailyreturn = __tmplist
    
            return __portfolio_dailyreturn
    
        def __fun_get_portfolio_ES(ratio, freq, lag, confidencelevel):
            if confidencelevel == 1.96:
                a = (1 - 0.95)
            elif confidencelevel == 2.06:
                a = (1 - 0.96)
            elif confidencelevel == 2.18:
                a = (1 - 0.97)
            elif confidencelevel == 2.34:
                a = (1 - 0.98)
            elif confidencelevel == 2.58:
                a = (1 - 0.99)
            else:
                a = (1 - 0.95)
            dailyReturns = __fun_get_portfolio_dailyreturn(ratio, freq, lag)
            dailyReturns_sort =  sorted(dailyReturns)
    
            count = 0
            sum_value = 0
            for i in range(len(dailyReturns_sort)):
                if i < (lag * a):
                    sum_value += dailyReturns_sort[i]
                    count += 1
            if count == 0:
                ES = 0
            else:
                ES = -(sum_value / (lag * a))

            return ES

        def __fun_get_portfolio_VaR(ratio, freq, lag, confidencelevel):
            __dailyReturns = __fun_get_portfolio_dailyreturn(ratio, freq, lag)
            __portfolio_VaR = 1.0 * confidencelevel * np.std(__dailyReturns)

            return __portfolio_VaR

        # 每元组合资产的 VaR
        __portfolio_VaR = __fun_get_portfolio_VaR(equity_ratio, '1d', 180, confidence_ratio)

        __equity_value_VaR = 0
        if __portfolio_VaR:
            __equity_value_VaR = risk_money / __portfolio_VaR

        __portfolio_ES = __fun_get_portfolio_ES(equity_ratio, '1d', 180, confidence_ratio)

        __equity_value_ES = 0
        if __portfolio_ES:
            __equity_value_ES = maxrisk_money / __portfolio_ES

        if __equity_value_VaR == 0:
            equity_value = __equity_value_ES
        elif __equity_value_ES == 0:
            equity_value = __equity_value_VaR
        else:
            equity_value = min(__equity_value_VaR, __equity_value_ES)

        return equity_value

    def fun_calStockWeight_by_risk(self, context, confidencelevel, stocklist):
        
        def __fun_calstock_risk_ES(stock, lag, confidencelevel):
            hStocks = history(lag, '1d', 'close', stock, df=True)
            dailyReturns = hStocks.resample('D',how='last').pct_change().fillna(value=0, method=None, axis=0).values
            if confidencelevel   == 1.96:
                a = (1 - 0.95)
            elif confidencelevel == 2.06:
                a = (1 - 0.96)
            elif confidencelevel == 2.18:
                a = (1 - 0.97)
            elif confidencelevel == 2.34:
                a = (1 - 0.98)
            elif confidencelevel == 2.58:
                a = (1 - 0.99)
            elif confidencelevel == 5:
                a = (1 - 0.99999)
            else:
                a = (1 - 0.95)
            
            dailyReturns_sort =  sorted(dailyReturns)
    
            count = 0
            sum_value = 0
            for i in range(len(dailyReturns_sort)):
                if i < (lag * a):
                    sum_value += dailyReturns_sort[i]
                    count += 1
            if count == 0:
                ES = 0
            else:
                ES = -(sum_value / (lag * a))
        
            if isnan(ES):
                ES = 0

            return ES

        def __fun_calstock_risk_VaR(stock):
            hStocks = history(180, '1d', 'close', stock, df=True)
            dailyReturns = hStocks.resample('D',how='last').pct_change().fillna(value=0, method=None, axis=0).values
            VaR = 1 * 2.58 * np.std(dailyReturns)

            return VaR
            
        __risk = {}
        maxRisk = 0

        stock_list = []
        for stock in stocklist:
            #curRisk = __fun_calstock_risk_VaR(stock)
            curRisk = __fun_calstock_risk_ES(stock, 180, confidencelevel)
            #print curRisk

            if curRisk <> 0.0:
                __risk[stock] = curRisk

        __position = {}
        for stock in __risk.keys():
            __position[stock] = 1.0 / __risk[stock]

        total_position = 0
        for stock in __position.keys():
            total_position += __position[stock]

        __ratio = {}
        for stock in __position.keys():
            tmpRatio = __position[stock] / total_position
            if isnan(tmpRatio):
                tmpRatio = 0
            __ratio[stock] = round(tmpRatio, 4)
    
        return __ratio

    def fun_tradeBond(self, context, stock, Value):
        hStocks = history(1, '1d', 'close', stock, df=False)
        curPrice = hStocks[stock]
        curValue = float(context.portfolio.positions[stock].total_amount * curPrice)
        deltaValue = abs(Value - curValue)
        if deltaValue > (curPrice*100):
            if Value > curValue:
                cash = context.portfolio.cash
                if cash > (curPrice*100):
                    self.fun_trade(context, stock, Value)
            else:
                # 如果是银华日利，多卖 100 股，避免个股买少了
                if stock == '511880.XSHG':
                    Value -= curPrice*100
                self.fun_trade(context, stock, Value)

    def unpaused(self, _stocklist):
        current_data = get_current_data()
        return [s for s in _stocklist if not current_data[s].paused]
    
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
        if stock in context.lowPB_moneyfund:
            set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0, close_commission=0, close_today_commission=0, min_commission=0), type='stock')
        else:
            set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')