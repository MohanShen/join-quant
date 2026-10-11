# Clone from JoinQuant
# postId: 6a15900595a88d9231c4429fd286bcf6
# backtestId: 325494b7fe75f21a7781cadb66b3021f
# title: 从标普红利机会指数学到的 —— 限制行业比重上限，很好很强大

import numpy as np
import talib
import pandas
import datetime as dt

def initialize(context):
    #用沪深 300 做回报基准
    set_benchmark('000300.XSHG')
    # 滑点、真实价格
    set_slippage(FixedSlippage(0.000))
    set_option('use_real_price', True)

    # 关闭部分log
    log.set_level('order', 'error')

    run_daily(fun_main, '10:30')

def after_code_changed(context):

    # initialize 运行机制多变和复杂，所有变量都挪到 after_code_changed 里
    g.quantlib = quantlib()
    # 调仓参数
    g.quantlib.fun_set_var(context, 'hold_cycle', 21)
    g.quantlib.fun_set_var(context, 'hold_periods', 0)
    g.quantlib.fun_set_var(context, 'stock_list', [])
    # 分配策略的市值比例
    context.FFScore_ratio = 1.0

    # 定义股票池
    moneyfund = ['511880.XSHG']

    # 上市不足 60 天的剔除掉
    context.moneyfund = g.quantlib.fun_delNewShare(context, moneyfund, 60)

def fun_main(context):

    # 引用 lib
    g.FFScore  = FFScore_lib()

    # 检查是否需要调仓
    rebalance_flag, context.hold_periods, msg = \
        g.quantlib.fun_needRebalance('策略', context.stock_list, \
            context.hold_periods, context.hold_cycle)

    if rebalance_flag:
        statsDate = context.current_dt.date()

        # 计算策略的持仓
        position_ratio = g.FFScore.algo(context, context.FFScore_ratio, context.portfolio.portfolio_value)

        context.stock_list = position_ratio.keys()

        # 卖掉已有且不在待购清单里的股票
        for stock in context.portfolio.positions.keys():
            if stock not in position_ratio:
                position_ratio[stock] = 0
        context.position_ratio = position_ratio

    # 调仓，执行交易
    trade_style = False    # True 会交易进行类似 100股的买卖，False 则只有在仓位变动 >25% 的时候，才产生交易
    if context.hold_periods == context.hold_cycle:
        trade_style = True
    g.quantlib.fun_do_trade(context, context.position_ratio, context.moneyfund, trade_style)

class FFScore_lib():

    def __init__(self, _period = '1d'):
        pass

    def algo(self, context, algo_ratio, portfolio_value):
        '''
        FFScore algorithms
        输入参数：FFScore_ratio, protfolio_value
        输出参数：FFScore_trade_ratio
        自有类  : FFScore_lib
        调用类  : quantlib
        '''
        # 调仓
        statsDate = context.current_dt.date()
        # 取得待购列表
        stock_list = self.fun_get_stock_list(context, statsDate)

        # 分配仓位
        equity_ratio, bonds_ratio = g.quantlib.fun_assetAllocationSystem(stock_list, context.moneyfund, statsDate)

        # 根据预设的风险敞口，计算交易时的比例
        trade_ratio = g.quantlib.fun_calPosition(equity_ratio, bonds_ratio, algo_ratio, context.moneyfund, portfolio_value, statsDate)

        return trade_ratio

    def fun_get_stock_list(self, context, statsDate):
        def __cal_FFScore(stock_list, FFScore, new_list):
            for stock in stock_list:
                if stock in new_list:
                    if stock in FFScore:
                        FFScore[stock] += 1
                    else:
                        FFScore[stock] = 1
                elif stock not in FFScore:
                    FFScore[stock] = 0
            return FFScore

        df = get_fundamentals(
            query(valuation.code, valuation.pb_ratio),
            date = statsDate - dt.timedelta(1)
        )
        # 1）市净率全市场从小到大前20%（剔除市净率为负的股票）
        df = df.sort(['pb_ratio'], ascending=[True])
        df = df.reset_index(drop = True)
        df = df[df.pb_ratio > 0]
        df = df.reset_index(drop = True)
        df = df[0:int(len(df)*0.05)]  #股票太多，所以变更了比例
        stock_list = list(df['code'])

        #2) 盈利水平打分
        # 2.1 资产收益率（ROE）：收益率为正数时ROE=1，否则为0。
        df = get_fundamentals(
            query(indicator.code, indicator.roe),
            date = statsDate - dt.timedelta(1)
        )
        df = df[df.code.isin(stock_list)]
        df = df.reset_index(drop = True)
        df = df[df.roe > 0]
        df = df.reset_index(drop=True)
        list_roe = list(df['code'])

        FFScore = {}
        FFScore = __cal_FFScore(stock_list, FFScore, list_roe)
        
        #2.2 资产收益率变化（△ROA）：当期最新可得财务报告的ROA同比的变化。变化为正数时△ROA=1，否则为0。
        df = get_fundamentals(
            query(indicator.code, indicator.roa),
            date = statsDate - dt.timedelta(1)
        )
        # 此算法不严谨，先简单实现，看看大体效果
        df2 = get_fundamentals(
            query(indicator.code, indicator.roa),
            date = statsDate - dt.timedelta(365)
        )
        df = df[df.code.isin(stock_list)]
        df = df.reset_index(drop = True)
        df.index = list(df['code'])
        df = df.drop(['code'], axis=1)
        dict1 = df.to_dict()['roa']

        df2 = df2[df2.code.isin(stock_list)]
        df2 = df2.reset_index(drop = True)
        df2.index = list(df2['code'])
        df2 = df2.drop(['code'], axis=1)
        dict2 = df2.to_dict()['roa']
        
        tmpList = []
        for stock in dict1.keys():
            if stock in dict2:
                if dict1[stock] > dict2[stock]:
                    tmpList.append(stock)
        FFScore = __cal_FFScore(stock_list, FFScore, tmpList)

        # 3)财务杠杆和流动性
        # 3.1 杠杆变化（△LEVER）：杠杆通过非流动负债合计除以非流动资产合计计算，杠杆变化为当期最新可得财务报告的杠杆同比的变化。变化为负数时△LEVER=1，否则为0。
        df = get_fundamentals(
            query(balance.code, balance.total_non_current_assets, balance.total_non_current_liability),
            date = statsDate - dt.timedelta(1)
        )
        # 此算法不严谨，先简单实现，看看大体效果
        df2 = get_fundamentals(
            query(balance.code, balance.total_non_current_assets, balance.total_non_current_liability),
            date = statsDate - dt.timedelta(365)
        )
        
        df3 = get_fundamentals(
            query(balance.code, balance.total_non_current_assets, balance.total_non_current_liability),
            date = statsDate - dt.timedelta(730)
        )

        df['total_non_current_assets_before'] = df2['total_non_current_assets']
        df = df.dropna()
        df = df[df.code.isin(stock_list)]
        df['LEVER'] = 2.0*df['total_non_current_liability'] / (df['total_non_current_assets'] + df['total_non_current_assets_before'])
        df.index = list(df['code'])
        df = df.drop(['code', 'total_non_current_assets', 'total_non_current_liability', 'total_non_current_assets_before'], axis=1)
        dict1 = df.to_dict()['LEVER']

        df2['total_non_current_assets_before'] = df3['total_non_current_assets']
        df2 = df2.dropna()
        df2 = df2[df2.code.isin(stock_list)]
        df2['LEVER'] = 2.0*df2['total_non_current_liability'] / (df2['total_non_current_assets'] + df2['total_non_current_assets_before'])
        df2.index = list(df2['code'])
        df2 = df2.drop(['code', 'total_non_current_assets', 'total_non_current_liability', 'total_non_current_assets_before'], axis=1)
        dict2 = df2.to_dict()['LEVER']

        tmpList = []
        for stock in dict1.keys():
            if stock in dict2:
                if dict1[stock] < dict2[stock]:
                    tmpList.append(stock)
        FFScore = __cal_FFScore(stock_list, FFScore, tmpList)
        '''
        df = get_fundamentals(
            query(balance.code, balance.total_non_current_assets, balance.total_non_current_liability),
            date = statsDate - dt.timedelta(1)
        )
        # 此算法不严谨，先简单实现，看看大体效果
        df2 = get_fundamentals(
            query(balance.code, balance.total_non_current_assets, balance.total_non_current_liability),
            date = statsDate - dt.timedelta(365)
        )

        df = df[df.code.isin(stock_list)]
        df['LEVER'] = df['total_non_current_liability'] / df['total_non_current_assets']
        df.index = list(df['code'])
        df = df.drop(['code', 'total_non_current_assets', 'total_non_current_liability'], axis=1)
        dict1 = df.to_dict()['LEVER']

        df2 = df2[df2.code.isin(stock_list)]
        df2['LEVER'] = df2['total_non_current_liability'] / df2['total_non_current_assets']
        df2.index = list(df2['code'])
        df2 = df2.drop(['code', 'total_non_current_assets', 'total_non_current_liability'], axis=1)
        dict2 = df2.to_dict()['LEVER']

        tmpList = []
        for stock in dict1.keys():
            if stock in dict2:
                if dict1[stock] < dict2[stock]:
                    tmpList.append(stock)
        FFScore = __cal_FFScore(stock_list, FFScore, tmpList)
        '''
        # 4）运营效率
        # 4.1 流动资产周转率变化（△CATURN）： 流动资产周转率变化为当期最新可得财务报告的资产周转率同比的变化。变化为正数时△CATURN =1，否则为0。
        # 主营业务收入与流动资产的比例来反映流动资产的周转速度，来衡量企业在生产运营上对流动资产的利用效率。
        df = get_fundamentals(
            query(balance.code, balance.total_current_assets, income.total_operating_revenue, income.non_operating_revenue),
            date = statsDate - dt.timedelta(1)
        )
        # 此算法不严谨，先简单实现，看看大体效果
        df2 = get_fundamentals(
            query(balance.code, balance.total_current_assets, income.total_operating_revenue, income.non_operating_revenue),
            date = statsDate - dt.timedelta(365)
        )

        df3 = get_fundamentals(
            query(balance.code, balance.total_current_assets, income.total_operating_revenue, income.non_operating_revenue),
            date = statsDate - dt.timedelta(730)
        )

        df['total_current_assets_before'] = df2['total_current_assets']
        df = df.dropna()
        df = df[df.code.isin(stock_list)]
        df['CATURN'] = (df['total_operating_revenue'] - df['non_operating_revenue']) / (df['total_current_assets'] + df['total_current_assets_before'])
        df.index = list(df['code'])
        df = df.drop(['code', 'total_current_assets', 'total_operating_revenue', 'non_operating_revenue', 'total_current_assets_before'], axis=1)
        dict1 = df.to_dict()['CATURN']

        df2['total_current_assets_before'] = df3['total_current_assets']
        df2 = df2.dropna()
        df2 = df2[df2.code.isin(stock_list)]
        df2['CATURN'] = (df2['total_operating_revenue'] - df2['non_operating_revenue']) / (df2['total_current_assets'] + df2['total_current_assets_before'])
        df2.index = list(df2['code'])
        df2 = df2.drop(['code', 'total_current_assets', 'total_operating_revenue', 'non_operating_revenue', 'total_current_assets_before'], axis=1)
        dict2 = df2.to_dict()['CATURN']
        
        tmpList = []
        for stock in dict1.keys():
            if stock in dict2:
                if dict1[stock] > dict2[stock]:
                    tmpList.append(stock)
        FFScore = __cal_FFScore(stock_list, FFScore, tmpList)

        # 4.2 资产周转率变化（△TURN）： 资产周转率通过总资产周转率除以平均资产总值计算，资产周转率变化为当期最新可得财务报告的资产周转率同比的变化。变化为正数时△TURN =1，否则为0
        df = get_fundamentals(
            query(balance.code, income.total_operating_revenue, income.non_operating_revenue, balance.total_current_assets, balance.total_non_current_assets),
            date = statsDate - dt.timedelta(1)
        )
        df2 = get_fundamentals(
            query(balance.code, income.total_operating_revenue, income.non_operating_revenue, balance.total_current_assets, balance.total_non_current_assets),
            date = statsDate - dt.timedelta(365)
        )
        df3 = get_fundamentals(
            query(balance.code, income.total_operating_revenue, income.non_operating_revenue, balance.total_current_assets, balance.total_non_current_assets),
            date = statsDate - dt.timedelta(730)
        )

        df['total_assets'] = df['total_current_assets'] + df['total_non_current_assets']
        df2['total_assets'] = df2['total_current_assets'] + df2['total_non_current_assets']
        df3['total_assets'] = df3['total_current_assets'] + df3['total_non_current_assets']
        df['total_assets_before'] = df2['total_assets']
        df2['total_assets_before'] = df3['total_assets']
        df = df.dropna()
        df2 = df2.dropna()

        df = df[df.code.isin(stock_list)]
        df['TURN'] = (df['total_operating_revenue'] - df['non_operating_revenue']) / (df['total_assets'] + df['total_assets_before'])
        df.index = list(df['code'])
        df = df.drop(['code', 'total_operating_revenue', 'non_operating_revenue', 'total_current_assets', 'total_non_current_assets', 'total_assets', 'total_assets_before'], axis=1)
        dict1 = df.to_dict()['TURN']

        df2 = df2[df2.code.isin(stock_list)]
        df2['TURN'] = (df2['total_operating_revenue'] - df2['non_operating_revenue']) / (df2['total_assets'] + df2['total_assets_before'])
        df2.index = list(df2['code'])
        df2 = df2.drop(['code', 'total_operating_revenue', 'non_operating_revenue', 'total_current_assets', 'total_non_current_assets', 'total_assets', 'total_assets_before'], axis=1)
        dict2 = df2.to_dict()['TURN']

        tmpList = []
        for stock in dict1.keys():
            if stock in dict2:
                if dict1[stock] > dict2[stock]:
                    tmpList.append(stock)
        FFScore = __cal_FFScore(stock_list, FFScore, tmpList)

        stock_list = []
        for stock in FFScore.keys():
            if FFScore[stock] == 5:
                stock_list.append(stock)

        stock_list = g.quantlib.unpaused(stock_list)
        stock_list = g.quantlib.remove_st(stock_list, statsDate)
        stock_list = g.quantlib.fun_diversity_by_industry(stock_list, int(len(stock_list)*0.4))

        return stock_list

class quantlib():
    def __init__(self, _period = '1d'):
        pass

    def fun_set_var(self, context, var_name, var_value):
        if var_name not in dir(context):
            setattr(context, var_name, var_value)

    def fun_needRebalance(self, algo_name, stock_list, hold_periods, hold_cycle):
        msg = ""
        msg += algo_name + "离下次调仓还剩 " + str(hold_periods) + " 天\n"
        rebalance_flag = False
        
        if len(stock_list) <= 1:
            msg += algo_name + "调仓，因为持股数为 0 \n"
            rebalance_flag = True
        elif hold_periods == 0:
            msg += algo_name + "调仓，因为持股天数剩余为 0 \n"
            rebalance_flag = True

        if rebalance_flag:
            hold_periods = hold_cycle
        else:
            hold_periods -= 1

        return rebalance_flag, hold_periods, msg

    def fun_assetAllocationSystem(self, buylist, moneyfund, statsDate=None):
        def __fun_getEquity_ratio(__stocklist, statsDate):
            __ratio = {}
            if __stocklist:
                for stock in __stocklist:
                    # 等权重
                    __ratio[stock] = 1.0/len(__stocklist)

            return __ratio

        equity_ratio = __fun_getEquity_ratio(buylist, statsDate)
        bonds_ratio  = __fun_getEquity_ratio(moneyfund, statsDate)
    
        return equity_ratio, bonds_ratio

    def fun_calPosition(self, equity_ratio, bonds_ratio, algo_ratio, moneyfund, portfolio_value, statsDate=None):
        # 简化，不调整
        trade_ratio = equity_ratio

        return trade_ratio

    def fun_do_trade(self, context, trade_ratio, moneyfund, trade_style):
    
        def __fun_tradeStock(context, curPrice, stock, ratio, trade_style):
            total_value = context.portfolio.portfolio_value
            if stock in moneyfund:
                self.fun_tradeBond(context, stock, total_value * ratio)
            else:
                curValue = context.portfolio.positions[stock].total_amount * curPrice
                Quota = total_value * ratio
                if Quota:
                    if abs(Quota - curValue) / Quota >= 0.25 or trade_style:
                        if Quota > curValue:
                            if curPrice > context.portfolio.positions[stock].avg_cost:
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

    def fun_tradeBond(self, context, stock, Value):
        h = history(1, '1d', 'close', stock, df=False)
        curPrice = h[stock]
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

    def unpaused(self, stocklist):
        current_data = get_current_data()
        return [s for s in stocklist if not current_data[s].paused]

    def remove_st(self, stocklist, statsDate):
        # 去除ST，*ST
        #statsDate = statsDate.strftime("%Y-%m-%d")
        st = get_extras('is_st', stocklist, start_date=statsDate, end_date=statsDate, df=True)
        st = st.loc[statsDate]
        stocklist = list(st[st==False].index)

        return stocklist

    # 剔除上市时间较短的产品
    def fun_delNewShare(self, context, equity, deltaday):
        deltaDate = context.current_dt.date() - dt.timedelta(deltaday)
    
        tmpList = []
        for stock in equity:
            if get_security_info(stock).start_date < deltaDate:
                tmpList.append(stock)
    
        return tmpList

    def fun_diversity_by_industry(self, stock_list, max_num):
        if not stock_list:
            return stock_list

        industry_list = self.fun_get_industry(cycle=None)
        for industry in industry_list:
            i = 0
            stocks = get_industry_stocks(industry)
            for stock in stock_list:
                if stock in stocks:
                    i += 1
                    if i > max_num:
                        stock_list.remove(stock)

        return stock_list
    # 行业列表
    def fun_get_industry(self, cycle=None):
        # cycle 的参数：None取所有行业，True取周期性行业，False取非周期性行业
        industry_dict = {
            'A01':False,# 农业 	1993-09-17
            'A02':False,# 林业 	1996-12-06
            'A03':False,# 畜牧业 	1997-06-11
            'A04':False,# 渔业 	1993-05-07
            'A05':False,# 农、林、牧、渔服务业 	1997-05-30
            'B06':True, # 煤炭开采和洗选业 	1994-01-06
            'B07':True, # 石油和天然气开采业 	1996-06-28
            'B08':True, # 黑色金属矿采选业 	1997-07-08
            'B09':True, # 有色金属矿采选业 	1996-03-20
            'B11':True, # 开采辅助活动 	2002-02-05
            'C13':False, #	农副食品加工业 	1993-12-15
            'C14':False,# 食品制造业 	1994-08-18
            'C15':False,# 酒、饮料和精制茶制造业 	1992-10-12
            'C17':True,# 纺织业 	1992-06-16
            'C18':True,# 纺织服装、服饰业 	1993-12-31
            'C19':True,# 皮革、毛皮、羽毛及其制品和制鞋业 	1994-04-04
            'C20':False,# 木材加工及木、竹、藤、棕、草制品业 	2005-05-10
            'C21':False,# 家具制造业 	1996-04-25
            'C22':False,# 造纸及纸制品业 	1993-03-12
            'C23':False,# 印刷和记录媒介复制业 	1994-02-24
            'C24':False,# 文教、工美、体育和娱乐用品制造业 	2007-01-10
            'C25':True, # 石油加工、炼焦及核燃料加工业 	1993-10-25
            'C26':True, # 化学原料及化学制品制造业 	1990-12-19
            'C27':False,# 医药制造业 	1993-06-29
            'C28':True, # 化学纤维制造业 	1993-07-28
            'C29':True, # 橡胶和塑料制品业 	1992-08-28
            'C30':True, # 非金属矿物制品业 	1992-02-28
            'C31':True, # 黑色金属冶炼及压延加工业 	1994-01-06
            'C32':True, # 有色金属冶炼和压延加工业 	1996-02-15
            'C33':True, # 金属制品业 	1993-11-30
            'C34':True, # 通用设备制造业 	1992-03-27
            'C35':True, # 专用设备制造业 	1992-07-01
            'C36':True, # 汽车制造业 	1992-07-24
            'C37':True, # 铁路、船舶、航空航天和其它运输设备制造业 	1992-03-31
            'C38':True, # 电气机械及器材制造业 	1990-12-19
            'C39':False,# 计算机、通信和其他电子设备制造业 	1990-12-19
            'C40':False,# 仪器仪表制造业 	1993-09-17
            'C41':True, # 其他制造业 	1992-08-14
            'C42':False,# 废弃资源综合利用业 	2012-10-26
            'D44':True, # 电力、热力生产和供应业 	1993-04-16
            'D45':False,# 燃气生产和供应业 	2000-12-11
            'D46':False,# 水的生产和供应业 	1994-02-24
            'E47':True, # 房屋建筑业 	1993-04-29
            'E48':True, # 土木工程建筑业 	1994-01-28
            'E50':True, # 建筑装饰和其他建筑业 	1997-05-22
            'F51':False,# 批发业 	1992-05-06
            'F52':False,# 零售业 	1992-09-02
            'G53':True, # 铁路运输业 	1998-05-11
            'G54':True, # 道路运输业 	1991-01-14
            'G55':True, # 水上运输业 	1993-11-19
            'G56':True, # 航空运输业 	1997-11-05
            'G58':True, # 装卸搬运和运输代理业 	1993-05-05
            'G59':False,# 仓储业 	1996-06-14
            'H61':False,# 住宿业 	1993-11-18
            'H62':False,# 餐饮业 	1997-04-30
            'I63':False,# 电信、广播电视和卫星传输服务 	1992-12-02
            'I64':False,# 互联网和相关服务 	1992-05-07
            'I65':False,# 软件和信息技术服务业 	1992-08-20
            'J66':True, # 货币金融服务 	1991-04-03
            'J67':True, # 资本市场服务 	1994-01-10
            'J68':True, # 保险业 	2007-01-09
            'J69':True, # 其他金融业 	2012-10-26
            'K70':True, # 房地产业 	1992-01-13
            'L71':False,# 租赁业 	1997-01-30
            'L72':False,# 商务服务业 	1996-08-29
            'M73':False,# 研究和试验发展 	2012-10-26
            'M74':True, # 专业技术服务业 	2007-02-15
            'N77':False,# 生态保护和环境治理业 	2012-10-26
            'N78':False,# 公共设施管理业 	1992-08-07
            'P82':False,# 教育 	2012-10-26
            'Q83':False,# 卫生 	2007-02-05
            'R85':False,# 新闻和出版业 	1992-12-08
            'R86':False,# 广播、电视、电影和影视录音制作业 	1994-02-24
            'R87':False,# 文化艺术业 	2012-10-26
            'S90':False,# 综合 	1990-12-10
            }

        industry_list = []
        if cycle == True:
            for industry in industry_dict.keys():
                if industry_dict[industry] == True:
                    industry_list.append(industry)
        elif cycle == False:
            for industry in industry_dict.keys():
                if industry_dict[industry] == False:
                    industry_list.append(industry)
        else:
            industry_list = industry_dict.keys()

        return industry_list

    def fun_trade(self, context, stock, value):
        self.fun_setCommission(context, stock)
        order_target_value(stock, value)

    def fun_setCommission(self, context, stock):
        if stock in context.moneyfund:
            set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0, close_commission=0, close_today_commission=0, min_commission=0), type='fund')
        else:
            set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')