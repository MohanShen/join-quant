# Clone from JoinQuant
# postId: f65972254f10be6963b5c684df458d7e
# backtestId: f0f7700a930e014150f8fd2a7a380234
# title: 请大神帮我补一个转换中文名字的代码

    # 自学与自测
    #  生成上证指数分分股列表
stock_list=get_index_stocks("000016.XSHG","2022-07-5")
    # 选择流通市值最大的5个股票
df=get_fundamentals(query(valuation,).\
    filter(valuation.code.in_(stock_list))\
    .order_by(valuation.circulating_market_cap.desc())\
    .limit(5))
print(df)
    #选取代码列
print(df.loc[:,'code'])
    # 怎么把这个列表转换成中文名字，看了一些API，没看明白