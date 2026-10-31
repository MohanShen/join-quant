# Clone from JoinQuant
# postId: 5e82f8245b659d34016be9055a2473bf
# backtestId: 510511ae8f459f6ef8c6a846fec15a93
# title: 几张表的代码不一致

stocks = list(get_all_securities(['stock']).index)
# stocks = get_index_stocks('000300.XSHG')
# stocks = get_index_stocks('399102.XSHE')

df1=get_fundamentals(query(balance.code,balance.capital_reserve_fund,balance.retained_profit,valuation.circulating_market_cap).filter(balance.code.in_(stocks)))
df2=get_fundamentals(query(valuation.code,valuation.capitalization).filter(valuation.code.in_(stocks)))#函数默认的就是取动态回测时间最近的季度数据

print(len(df1))
print(len(df2))
print(len(df1['capital_reserve_fund']))
print(len(df2['capitalization']))#将不同的表放在一个query，代码就相同了
print(len(df1['circulating_market_cap']))

# print('\n%s'%df1['code'])
# print('\n%s'%df2['code'])

df3=get_fundamentals(query(balance.code,balance.capital_reserve_fund,balance.retained_profit))
df4=get_fundamentals(query(valuation.code,valuation.capitalization,valuation.circulating_market_cap))

print(len(df3['code']));print(len(df4['code']))
print(len(df3['capital_reserve_fund']))
print(len(df4['circulating_market_cap']))

#发现in_()如果在000300和399102倒是相同的，但是在全市场代码就不同了
#不用in_()，valuation.code与balance.code代码数量也不一样