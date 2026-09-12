---
title: "读取context中的数据与条件判断"
category: 新手专区
learners: 14853
postedAt: 2018-06-13 11:49:48
source: 量化课堂 (/study)
fetchedAt: 2026-09-12T16:26:59.409Z
# NOTE: postId/studyId are re-minted per request and are NOT recorded —
#       title + category is this lesson's stable handle.
---

# 读取context中的数据与条件判断

本文是[量化交易零基础入门教程](https://www.joinquant.com/post/13149)中的一篇，点击蓝字链接可查看该系列详情。

------

### 摘要

- context的含义
- context的结构
- context的读取方法
- 条件判断语句
- 止损的含义及其实现方法
- 自测与自学
---

- 通过前文的讲解，我们已经能理解最开始的那个简单的策略例子，如下：
    ```    
    def initialize(context):
        run_daily(period,time='every_bar')
        g.security = '000001.XSHE'
    
    def period(context):
        order(g.security, 100)
    ```
- 接下来，我们将在此基础上进行改进与举例，学习新内容。

### context的结构

- context是一个回测系统建立的Context类型的对象，其中存储了如当前策略运行的时间点、所持有的股票、数量、持仓成本等数据。

- 对象可以理解为特殊类型的变量，对象的结构往往比我们之前见过的list与dict更复杂，被定义好的对象是有名字的，比如context是一个变量，它的变量类型是一个Context类型的对象，就像dict包括key与value，Context类型的对象也包括很多属性，而且可以嵌套另一个种类型的对象，结构见下图。图中只包括了主要与常用的内容，详细介绍可以看API文档：[Context对象](https://www.joinquant.com/api#context)

![context]( https://image.joinquant.com/3f21926604474d702db5efe2c9154cb1)
- 关于对象的知识非常复杂繁多，目前我们只需学习如何取用context中的数据就好。

### context中的数据取用方法

- 获取对象类型变量内包含的数据方法是用英文句号隔开，而当包含的是另一个对象时，只需在应用英文句号隔开即可，例子如下：

        # 打印可用资金
        print(context.portfolio.available_cash)
        # 打印运行频率
        print(context.run_params.frequency)
        # 打印当前单位时间的开始时间
        print(context.current_dt)
        
        # 执行后日志内容如下
        # 1000000.0
        # day
        # 2016-06-01 09:30:00
    ![context]( https://image.joinquant.com/79e1891ccd9745dddaddc9a2cf18fa6a)

- 当要获取的对象内的数据是另一种有结构的变量类型时，比如dict或list，正常按照该变量类型进一步取用数据即可。例如context.portfolio.positions是一个dict，我们就可以应用之前讲过的dict 的用法来使用它，例子如下，这次给出了完整代码。

        # context.portfolio.positions的含义是仓位信息，所以为了让它有数据，需要在取之前买入并持有股票。
        
        def initialize(context):
            run_daily(period,time='every_bar')
            g.security = '000001.XSHE'
    
        def period(context):
            order(g.security, 100)
            # 打印所有键
            print(context.portfolio.positions.keys())
            # 打印所有值
            print(context.portfolio.positions.values())
            # 打印g.security的开仓均价
            print(context.portfolio.positions[g.security].avg_cost)
    
        # 执行后日志内容如下
        # ['000001.XSHE']
        # [UserPosition({'avg_cost': 8.539999999999997, 'security': '000001.XSHE', 'closeable_amount': 0, 'price': 8.53, 'total_amount': 100})]
        # 8.54

- 常用的context数据写法如下，推荐自己动手试下。
    - 当前时间 context.current_dt
    - 当前时间的“年-月-日”的字符串格式 context.current_dt.strftime("%Y-%m-%d")
    - 前一个交易日 context.previous_date
    - 当前可用资金 context.portfolio.available_cash
    - 持仓价值 context.portfolio.positions_value
    - 累计收益 context.portfolio.returns
    - 当前持有股票 context.portfolio.positions.keys()
    - 当前持有的某股票的开仓均价 context.portfolio.positions['xxxxxx.xxxx'].avg_cost
    - 当前持有的某股票的可卖持仓量 context.portfolio.positions['xxxxxx.xxxx'].closeable_amount

### 条件判断

- 能够获取context的数据后，我们会考虑利用这些数据丰富策略的逻辑，但在此之前我们还要学习if条件判断语句，如下：

        # 如果 条件1成立为 True 将执行代码块1
        # 如果 条件1不成立为False，将判断条件2
        # 如果 条件2成立为 True 将执行代码块2
        # 如果 条件2还不成立为False，将执行代码块3
        
        if 条件1:
            代码块1
        elif 条件2:
            代码块2
        else:
            代码块3
        
        # 注意
        # elif 可以有多个连续写
        # 且elif和else都可以省略
        # 条件判断语句中可以嵌套条件判断语句
    
- 举几个例子：
    
        # 打印a、b中最大值
        if a&gt;=b:
            print(a)
        else:
            print(b)
        
        # 判断a的正负性   
        if a&gt;0:
            print('正')
        elif a&lt;0:
            print('负')
        elif a==0:
            print('零')
            
        # 如果当前是2018-05-04，则下单买入100股平安银行
        date=context.current_dt.strftime("%Y-%m-%d")
        if date=='2018-05-04':
            order('000001.XSHE',100)
        
        # 判断a大小情况
        if a&gt;0:
            if a&lt;1:
                print('a大于0且小于1')
            else:
                print('a大于等于1')
        else:
            print('a小于等于0')

- 条件判断语句比较简单，但还需说明的是条件的写法中用到的运算符：

        # 写条件常用运算符：
        # &lt; 小于
        # &gt; 大于
        # &lt;= 小于等于
        # &gt;= 大于等于
        # == 等于
        # != 不等于
        # and 与，即and两边条件同为真，则真
        # or 或，即or两边条件任意一个为真，则真
        # not 非，即not右侧条件为真，则假，not右侧条件为假，则真
    
        # 以判断a是否为0的几个写法为例
        # 写法1
        if a!=0:
            print('否')
        else:
            print('是')
        # 写法2    
        if a&gt;0 or a&lt;0:
            print('否')
        else:
            print('是')
        # 写法2    
        if a&gt;=0 and a=&lt;0:
            print('是')
        else:
            print('否')
        # 写法3   
        if not a==0:
            print('否')
        else:
            print('是')

### 止损
- 狭义的止损是指当亏损达到一定幅度后下单卖出该股票的操作，目的是减少进一步的亏损。广义则指在狭义的思路上衍生的复杂的减少亏损的方法。更多的情况下指狭义的止损。综合运用前文的讲过的内容我们已经可以实现当亏损达到一定幅度后下单卖出该股票的止损操作了，不妨先自己思考下再继续学习。
- 通过context的数据可以得到持有股票的成本和现价，从而可以算出该股票的盈亏情况，运用条件判断语句根据盈亏情况从而决定是否卖出股票，从而实现止损操作，代码如下：

        def initialize(context):
            run_daily(period,time='every_bar')
            g.security = '000001.XSHE'
        
        def period(context):
            # 买入股票
            order(g.security, 100)
            # 获得股票持仓成本
            cost=context.portfolio.positions['000001.XSHE'].avg_cost
            # 获得股票现价
            price=context.portfolio.positions['000001.XSHE'].price
            # 计算收益率
            ret=price/cost-1
            # 打印日志
            print('成本价：%s' % cost)
            print('现价：%s' % price)
            print('收益率：%s' % ret)
            # 如果收益率小于-0.01，即亏损达到1%则卖出股票，幅度可以自己调，一般10%
            if ret&lt;-0.01:
                order_target('000001.XSHE',0)
                print('触发止损')
- 设置回测时间为从2017-03-01到2017-03-31，初始资金为100000，频率为天。回测发现会在2017-03-20触发止损。

### 自测与自学
- 实践下文中的例子。
- 阅读API文档中Context对象，了解下其中的结构与内容。
- 写一个策略，内容为在20180301买入一个股票，在20180321卖出一个股票。股票可以自己定。
- 试着根据止损的例子实现止盈，即指当盈利达到一定幅度后下单卖出股票。
- 写一个自定义函数，功能是判断一个年份是否是闰年。闰年定义为：普通年（不能被100整除的年份）能被4整除的为闰年。（如2004年就是闰年,1999年不是闰年）；世纪年（能被100整除的年份）能被400整除的是闰年。(如2000年是闰年，1900年不是闰年)；【提示:利用取余运算（%）判断是否整除】

---
[查看下一篇](https://joinquant.com/post/13305)
