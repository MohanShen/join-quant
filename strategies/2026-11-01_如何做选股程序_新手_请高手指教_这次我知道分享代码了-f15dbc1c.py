# Clone from JoinQuant
# postId: f15dbc1cc5fa893ccd2d3b715f882b5a
# backtestId: 143a6e09cb4fbab46a31687474adb673
# title: 如何做选股程序。新手，请高手指教？这次我知道分享代码了

#总体回测前要做的事情
def initialize(context):    
    g.stocknum = 1000 # 财务资料选股最大数量
    g.report_year = '2015'  # 财报年份
    
    # 下跌百分数 50% 
    # 注意，如果是下跌30% ，写0.3 而不是0.7
    g.fallfromTop = 0.5   

    
def handle_data(context, data):  
    print("------- 分隔符------- "   )  
    
    df = get_fundamentals( 
        query(
          indicator.code,  indicator.roe , valuation.market_cap, valuation.pe_ratio ).filter(
         #   valuation.market_cap > 1000,
            valuation.pe_ratio >1, 
            valuation.pe_ratio < 30,
          
          # 季度表，所以只能3以上
          
            indicator.roe > 3  
     
       #  对于年报数据, 我们目前只有现金流表和利润表, 当查询其他表时, 会返回该年份最后一个季报的数据
        ).order_by(
            # 按市值降序排列
            indicator.roe.desc()
        ).limit(
            # 最多返回100个
             g.stocknum
        ),  statDate=  g.report_year )
        
    
    # 第二部，如何做一个循环 ，对每个股票代码 检测 一些
    
    current_num=len(df)
    #用一个dataframe来保存持有的股票的信息
    stockcode_List = set("")         #创建一个唯一字符的集合，存代码 
    stockcode_List.clear()  
    
    # 循环查询 股票代码 的价格
    for i in range(0,current_num):

        #获得股票代码
        security= df.code[i] 
        
        ##-- 条件1： 选择下跌的--------------
        # 历史收盘价
        history_close = attribute_history(security, 200, '1d', ('close'))
        
        # 历史最高价
        highest_price=max(history_close['close']) 
        
        #昨日收盘
        current_price = data[security].close
        
        # 收盘下跌超过 fallfromTop 50%
        if current_price < (1-g.fallfromTop) * highest_price :  
            print("下跌50%: " +get_security_info(security).display_name+" " + df.code[i] + " $" + str(current_price))  

            # 这里会根据回测，打印N天的数据 
            # 我只想要最后这天的数据，前面部分没有必要测试浪费资源，怎么弄？
            # 这里直接打印也不好，应该建立一个 集合（set，后面出现其它条件，就继续从这里set 增加add或删除 remove
            stockcode_List.add(df.code[i])
      
      
        # 条件2： -------------
        
        # 删除某些代码，为啥出错？删除本来不存在的！
        # 可以建立多个set 然后求合集
        # stockcode_List.remove('xxx')

            
    print(stockcode_List)  
            
            

            
    return
 

