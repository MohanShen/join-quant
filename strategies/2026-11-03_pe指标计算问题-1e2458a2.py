# Clone from JoinQuant
# postId: 1e2458a2973d701dca23fc3fe9d4c6bc
# backtestId: e5a0dbceb4277fbb6ff34b56993519db
# title: pe指标计算问题

# 导入函数库
import jqdata

# 初始化函数，设定基准等等
def initialize(context):

    run_daily(market_open, time='open', reference_security='000300.XSHG')


def market_open(context):
    code = '000937.XSHE'
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2005Q4') 
    net_profit1 = df['np_parent_company_owners'][0]
    
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2006Q1') 
    net_profit2 = df['np_parent_company_owners'][0]
    
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2006Q2') 
    net_profit3 = df['np_parent_company_owners'][0]
    
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2006Q3') 
    net_profit4 = df['np_parent_company_owners'][0]
    
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),date='2007-02-01') 
    
    print "000937, 在2007-02-01的pe计算结果不一致"
    print "最新季报时间为 %s"%df['statDate'][0]
    print "pe_ttm为 ",df['pe_ratio'][0]
    print "pe_ttm计算为",df['market_cap'][0] / (net_profit1 + net_profit2 + net_profit3 + net_profit4) * 10**8
    print "__________________________________________________________________\n"
    
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2006Q4') 
    net_profit1 = df['np_parent_company_owners'][0]
    
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2007Q1') 
    net_profit2 = df['np_parent_company_owners'][0]
    
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2007Q2') 
    net_profit3 = df['np_parent_company_owners'][0]
    
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2007Q3') 
    net_profit4 = df['np_parent_company_owners'][0]
    
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),date='2008-02-01') 
    print "000937, 在2008-02-01的pe计算结果一致"
    print "最新季报时间为 %s"%df['statDate'][0]
    print "pe_ttm为 ",df['pe_ratio'][0]
    print "pe_ttm计算为",df['market_cap'][0] / (net_profit1 + net_profit2 + net_profit3 + net_profit4) * 10**8
    print "__________________________________________________________________\n"
    code = '601939.XSHG'

    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2016Q3') 
    net_profit1 = df['np_parent_company_owners'][0]
    mv1 = df['market_cap'][0]
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2016Q4') 
    net_profit2 = df['np_parent_company_owners'][0]
    mv2 = df['market_cap'][0]
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2017Q1') 
    net_profit3 = df['np_parent_company_owners'][0]
    mv3 = df['market_cap'][0]
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2017Q2') 
    net_profit4 = df['np_parent_company_owners'][0]
    mv4 = df['market_cap'][0]
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),date='2017-09-22') 
    print "601939在2017年9月22日的pe计算结果不一致"
    print "最新季报时间为 %s"%df['statDate'][0]
    print "pe_ttm为 ",df['pe_ratio'][0]
    print "pe_ttm计算为",df['market_cap'][0] / (net_profit1 + net_profit2 + net_profit3 + net_profit4) * 10**8
    print "__________________________________________________________________\n"
    
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2015Q3') 
    net_profit1 = df['np_parent_company_owners'][0]
    mv1 = df['market_cap'][0]
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2015Q4') 
    net_profit2 = df['np_parent_company_owners'][0]
    mv2 = df['market_cap'][0]
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2016Q1') 
    net_profit3 = df['np_parent_company_owners'][0]
    mv3 = df['market_cap'][0]
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),statDate='2016Q2') 
    net_profit4 = df['np_parent_company_owners'][0]
    mv4 = df['market_cap'][0]
    df = get_fundamentals(query(valuation, income).filter(valuation.code==code),date='2016-09-22') 
    
    print "601939在2016年9月22日的pe计算结果一致"
    print "最新季报时间为 %s"%df['statDate'][0]
    print "pe_ttm为 ",df['pe_ratio'][0]
    print "pe_ttm计算为",df['market_cap'][0] / (net_profit1 + net_profit2 + net_profit3 + net_profit4) * 10**8
    print "\n"
