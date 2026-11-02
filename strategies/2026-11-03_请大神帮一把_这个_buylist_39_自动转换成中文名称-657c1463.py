# Clone from JoinQuant
# postId: 657c14633f31cda8ad8de181d93046aa
# backtestId: d4d418b71a06f2880d8c3f5ab61f3bb2
# title: 请大神帮一把：这个’buylist&#39;自动转换成中文名称

    # 自学与自测
    #  生成上证指数分分股列表
stock_list=get_index_stocks("000016.XSHG","2022-07-5")
    # 选择流通市值最大的5个股票
df=get_fundamentals(query(valuation,).\
    filter(valuation.code.in_(stock_list))\
    .order_by(valuation.circulating_market_cap.desc())\
    .limit(5))
print(df)

buylist=list(df['code'])    
    #选取代码列
print(df.loc[:,'code'])
    # 把这个列表转换成中文名字
    # 股票，名称
print('流通市值排名')
one = get_security_info('601398.XSHG').display_name
print("第一--%s" % (one))
two = get_security_info('601857.XSHG').display_name
print("第二--%s" % (two))
three = get_security_info('601288.XSHG').display_name
print("第三--%s" % (three))
fore = get_security_info('600519.XSHG').display_name
print("第四--%s" % (fore))
fiv = get_security_info('601318.XSHG').display_name
print("第五--%s" % (fiv))

    # 用什么代码把这个’buylist'自动转换成中文名称，以上都是手写的。






