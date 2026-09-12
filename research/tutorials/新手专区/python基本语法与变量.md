---
title: "python基本语法与变量"
category: 新手专区
learners: 14404
postedAt: 2018-06-12 19:27:07
source: 量化课堂 (/study)
fetchedAt: 2026-09-12T16:26:56.986Z
# NOTE: postId/studyId are re-minted per request and are NOT recorded —
#       title + category is this lesson's stable handle.
---

# python基本语法与变量

本文是[量化交易零基础入门教程](https://www.joinquant.com/post/13149)中的一篇，点击蓝字链接可查看该系列详情。

------

### 摘要

- python是什么
- python的基础语法
- 变量与赋值
- Python 保留字符
- 打印 print
- 全局变量
- 基本数据类型-数字与字符串
- 算术运算
- 查看数据类型 type
- 数据类型-列表与字典
- 自测与自学

------
- 前文讲解了量化交易中策略运行的基本框架以及实现方法，其中虽然给出一个简单策略的完整代码，但只是初步认识，想完全看懂并自己写需要掌握python这门编程语言。
- 一般常见的python教程都是针对程序员的，所以很多内容在做量化写策略时都往往用不到。而本教程则是以量化的情景从零讲解python编程，所以将更适合想学做量化策略的人。
- 当然，对如果想更完备而全面的学习python语言的人，不妨看下这个文章（可能会繁杂些，也可能更适合你）：[python教程合集](https://www.joinquant.com/post/10760)

- 我们将以前文策略代码为例进行讲解，如下：
        
        def initialize(context):
            run_daily(period,time='every_bar')
            g.security = '000001.XSHE'
        
        def period(context):
            order(g.security, 100)

### python是什么

- python是与计算机交流的一种语言。我们把想让计算机做的事情用python写出来，就如同前文那样的一行行代码，从而，计算机才能理解并去按我们的想法去做。这是一种通俗易懂的理解，但已经足够了。想了解更多专业角度的介绍就自行搜索了解吧。

- Python2与Python3
    - Python语言本身也是如同自然语言般在不断变化的，升级到python3.0版本时出现了较大的变化，以至于python分为了python2与python3两个不互相兼容的版本。
    - 由于世界上有很多流行功能函数库对python3的支持并非很好，而有些量化过程中策略或系统可能会用到，所以我们用python2来写策略，而且聚宽做策略回测代码也只支持python2。（聚宽投资研究功能中支持使用python3）
    - 不过对写策略来说，python2与python3的区别并不明显。具体区别见[python官方文档](https://wiki.python.org/moin/Python2orPython3)。

### python的基础语法

- 大小写敏感
    - 比较容易理解，就是字母的大写与小写是区分的，所以如果你把前文例子的代码中的若干个字母从小写变成大写，系统会报错。
- 要用英文符号
    - 之前讲过，冒号、逗号、分号、括号、引号等各种符号必须用英文的，中文的会不识别而报错。
- 注释
    - 为了让代码的便于交流理解，通常都会在代码中写入注释用以说明代码，注释是给人看的，所以计算机会忽略（顺便提下，空行也会被忽略），用中文记录思路也没关系。**强烈建议**养成写注释的好习惯。注释的方法有二：
    - (#)会把所在行的其后的所有内容设定为注释，如下
            
            # 注释样例
            # 这是一一个每天买平安银行的策略

            # 初始化
            def initialize(context):
                run_daily(period,time='every_bar')
                # 设定要买入的股票是平安银行
                g.security = '000001.XSHE'
            # 周期循环
            def period(context):
                #买入100股平安银行
                order(g.security, 100)
    - 三个单引号(''')或三个双引号(""")会把之间的内容设定为注释，以单引号为例如下：
            
            '''
            注释样例
            这是一一个每天买平安银行的策略
            是我写的：）
            '''
            '''初始化'''
            def initialize(context):
                run_daily(period,time='every_bar')
                g.security = '000001.XSHE'
            '''周期循环'''
            def period(context):
                '''买入100股平安银行'''
                order(g.security, 100)
- 行与缩进
    - 之前讲过，代码缩进的时候要对齐，缩进方法是四个空格或一个tab键(推荐用tab)，不要混着用。比如例子中周期循环部分除第一句都是要缩进的。
    - 缩进的含义是这样的，有些语句是要包含其他连续若干条语句才成立的，这些语句通过缩进表示这种被包含的关系。如下：
            
            # initialize这条语句包含了其下的两条语句
            def initialize(context):
                # 这两条语句是要被其上的initialize包含的，要缩进
                run_daily(period,time='every_bar')
                g.security = '000001.XSHE'
- 一行写多条语句
    - 一般习惯是一行只写一条语句，如果要一行写多条语句要用分号隔开，不常用但要认识，如下，我把例子中原本的第二行与第三行写在一行了（比较长排版可能会自动换行显示）。
    
            def initialize(context):
                run_daily(period,time='every_bar');g.security = '000001.XSHE'

- 一条语句写在多行
    - 有时一条语句可能就会很长，为了便于阅读会用斜杠（不是除号，是从左上到右下的）分隔后写在多行。如下，例子的第二行代码被斜杠分隔后写在两行。

            def initialize(context):
                run_daily(period,\
                time='every_bar')
                g.security = '000001.XSHE'



### 变量与赋值
- 我们在之前的例子中见过这样一行语句

        g.security = '000001.XSHE'

- 当时没细讲，含义是把'000001.XSHE'这个字符串赋值给名为g.security的变量(security是英文证券的意思)。

- **变量**通俗的理解是，计算机中存放数据的有名字的盒子。另外变量名字是在赋值语句中定义的。

- **赋值**，即赋予变量数据，写法是等号，含义是把等号右边的数据（或变量里的数据）放入左边的变量中去。用法如下：
    
        # 用法： 变量名 = 数据或变量

        a=1
        b='你好'
        
        # 把a中的数据1赋值给了c
        c=a  
        # 把b中的数据'你好'赋值给了a,此时a中的1被替换了
        a=b
        
### Python 保留字符
- 有些名字被系统所占用不能用作变量名，或任何其他标识符名称，如下：

        and	    exec	not     assert	finally	continue
        break	for	    pass    class	from	print
        or      global	raise   def	    if	    return
        del	    import	try     elif	in	    while
        else	is	    with    except	lambda	yield
        
### 打印 print

- print是非常常用而重要的语句，它能把变量里的内容在日志中打印输出出来，通过它我们能了解程序运行的细节。 用法如下：

        # 用法： print(变量名)
        a=1
        print(a)
        b='你好'
        print(b)
        
- 如下图，把代码放到周期循环里后，点编译运行执行代码，每个交易日都打印了a、b，因为运行了两个交易日，所以打印了2组a、b。注意，**后面的例子都可以这个方法来执行**。
        
    ![print用法.png](https://image.joinquant.com/d3a79a150a17a845d3ab43c0a4539fb8)

- print也可以直接打印数据，如下
        
        # 用法： print(数据)
        print(1)
        print('你好')
- 为了能在日志中看出打印内容的含义，可以采用如下方法，此方法经常用于记录策略的运行情况。
        
        # 用法：print("说明、解释等,用%s表示变量的位置" % (变量或数据))
        
        a=1
        b='hello'

        print("a=%s" % （a))
        print("b=%s" % (b))
        print("%s是你好的意思" % (b))
        #\n是在所在位置换行的意思，能让日志在日期信息的下一行开始打印
        print("\na=%s" % (a))
        
        # 用之前的方法执行后结果如下：
        2016-06-01 09:30:00 - INFO  - a=1
        2016-06-01 09:30:00 - INFO  - b=hello
        2016-06-01 09:30:00 - INFO  - hello是你好的意思
        2016-06-01 09:30:00 - INFO  - 
        a=1
        
### 全局变量

- 你可能会发现初始化里的变量与周期循环里的变量是不通的，比如你运行如下的代码会报错：

        def initialize(context):
            run_daily(period,time='every_bar')
            a=1
        def period(context):
            print(a)

- 报错信息如下，含义是a没有被定义      
    
        NameError: global name 'a' is not defined

- 为了让变量能在全局被使用，需要在变量前加'g.'，使之成为**全局变量**。所以，把刚刚的代码中的a改为全局变量就能正确运行了。

        def initialize(context):
            run_daily(period,time='every_bar')
            g.a=1
        def period(context):
            print(g.a)

### 基本数据类型-数字与字符串
- 对计算机来说，不同的数据往往需要不同的操作与存储要求，因此在赋值时python会自动为数据分类，从而对不同的数据采取不同的应对方法。比如，数字可以数学运算，但文本就不可以，字母可以转换大小写，数字不行。

- 数字（Number）
    - 数字就是数字，可以做诸如加减乘除的计算操作，具体可分为多种类型，比如股价一般就是浮点数型。因为在赋值变量的时候，python会自动调整变量类型。所以需要关注数字类型的时候并不多。
    - 数字具体分为int（整数）、float（浮点数，即 包含小数位）、bool（布尔值，即True和False，True是1，False是0）等。 
    
            a = 3      # 整数
            b = 3.1415 # 浮点数
            c = True   # 布尔值

- 字符串（String）
    -  字符串可以理解为文本或文字，不能像数字进行数学运算，有其特别的操作，比如股票代码、股票名称一般都是字符串。
    - Python 可使用引号( ' )、双引号( " )、三引号( ''' 或 """ ) 来表示字符串，引号的开始与结束必须的相同类型的。如下，不妨用刚讲的print打印下看看。

            # 其中三引号可以由多行组成来编写多行文本
            a = '九歌'
            b = "袅袅兮秋风"
            c ="""袅袅兮秋风，
            洞庭波兮木叶下。
            ——屈原《九歌》""" 

### 算术运算
- 数字变量之间是可以进行算术运算的，如下：
    
        a=3.0
        b=2.0
        
        # 为了查看结果我用了print打印
        # 加
        print("a+b=%s" % (a+b))
        # 减
        print("a-b=%s" % (a-b))
        # 乘
        print("a*b=%s" % (a*b))
        # 除
        print("a/b=%s" % (a/b))
        # a除以b的商的整数部分
        print("a//b=%s" % (a//b))
        # a的b次幂，即指数运算
        print("a**b=%s" % (a**b))
        # a除以b的余数，即取余运算，为了打印“%”百分号要用两个百分号代表“%”百分号
        print("a%%b=%s" % (a%b)) 
        
        # 用之前的方法执行后结果如下，日期信息省去了
        a+b=5.0
        a-b=1.0
        a*b=6.0
        a/b=1.5
        a//b=1.0
        a**b=9.0
        a%b=1.0
- 注意如果两个整数类型进行计算，结果默认还是整数。如下：
        
        # 这样写没有.0，系统会默认当成整数
        a=3
        b=2
        
        # 为了查看结果我用了print打印
        # 加
        print("a+b=%s" % (a+b))
        # 减
        print("a-b=%s" % (a-b))
        # 乘
        print("a*b=%s" % (a*b))
        # 除
        print("a/b=%s" % (a/b))
        # a除以b的商的整数部分
        print("a//b=%s" % (a//b))
        # a的b次幂，即指数运算
        print("a**b=%s" % (a**b))
        # a除以b的余数，即取余运算，为了打印“%”百分号要用两个百分号代表“%”百分号
        print("a%%b=%s" % (a%b)) 
        
        # 用之前的方法执行后结果如下，日期信息省去了
        a+b=5
        a-b=1
        a*b=6
        a/b=1 # 3/2=1.5 .5被省略了
        a//b=1
        a**b=9
        a%b=1
        

### 查看数据类型 type 
- type语句可以，告诉我们变量里存放的是什么类型的数据。用法如下：
            
            # 用法：type(变量名)
            a=1
            b='1'
            # 为了看到结果需要用print把结果在日志中打印
            print(type(a))
            print(type(b))

            # 用之前的方法执行后结果如下，可以看到a是int即整数，b是str即字符串。
            2016-06-01 09:30:00 - INFO  - 
            2016-06-01 09:30:00 - INFO  - 

### 数据类型-列表与字典
- 为了更方便的取用数据，在最基本的数据类型-数字与字符串基础上，还有其他的数据类型，他们往往具有更复杂的结构更便捷的功能。比如接下来要介绍的列表（List）、字典（Dictionary），不过这里的内容实在是繁多，此处只介绍最常用的内容，其他内容后续用到再讲。

- 列表（list）
    - 列表数据类型能方便我们操作一组数据。比如一组股价、一组股票名等。
    - 建立方法如下：

            # 建立一个list： 变量名=[数据或变量名，数据或变量名，......]
            
            a=[1,1,2,3,5,8,13,21]
            b=['000001.XSHE','002043.XSHE','002582.XSHE','600000.XSHG']
            c=[1,2,'good',[1,2,'luck'],a,b]
            
            # 值得注意的是例子中的c，c是一个list，其中的包含了6个元素，其中有数字（1,2），有字符串（'good'）,以及三个list（[1,2,'luck'],a,b）。
            # 因此你应该知道，list中可混合的存放多种数据类型，list中放一个list也行。
    
    - 选取list中的某个元素的用法如下：
            
            # 方法： list类型的变量[位置（或称下标或索引）]
            # 索引从0开始
            # 可以用负数代表倒数第几
            
            c=[1,2,3,4]
            
            # 为了看到结果我们用print打印
            print(c[0])
            print(c[1])
            print(c[2])
            print(c[-1])
            
            # 用之前的方法执行后结果如下:(前面的日期以后就不写了)
            1
            2
            3
            4
            
    - 选取list中的一段的用法如下：
            
            # 方法： list类型的变量[起点索引:终点索引]
            # 起点索引省略则默认为0
            # 终点索引省略则默认为最后的索引
            # 注意此时的结果仍是一个list
            
            c=[1,2,3,4]
            
            # 为了看到结果我们用print打印
            print(c[2:3])
            print(c[:-1])
            print(c[3:])
            print(c[:])
            
            # 执行后结果如下:
            [3]
            [1, 2, 3]
            [4]
            [1, 2, 3, 4]
    
- 字典（dictionary）
    - 字典数据类型同样能方便我们操作一组数据，与list不同的是我们可以为这组数据自定义地建立索引。
    - 建立方法如下：
        
            # 建立方法: 变量名={索引名:数据,索引名:数据,....}
            # dict中的索引也叫键(key)，数据也叫值(value)

            a={'平安银行':'000001.XSHE','浦发银行':'600000.XSHG'}
            b={'开盘价':10.0,'收盘价':11.0,'涨跌幅':0.10}
    - 选取dict中的某个key的值方法如下：
            
            # 选取方法 dict类型的变量[key]
            a={'平安银行':'000001.XSHE','浦发银行':'600000.XSHG'}
            
            # 为了看到结果我们用print打印
            print(a['平安银行'])
            
            # 执行后结果如下:
            000001.XSHE
    - 选取dict中的所有key与所有value
            
            # 选取dict中的所有key: dict类型变量.keys()
            # 选取dict中的所有value: dict类型变量.values()
            # 注意返回的结果是list类型的
            
            a={'平安银行':'000001.XSHE','浦发银行':'600000.XSHG'}
            b=a.keys()
            c=a.values()
            
            # 为了看到结果我们用print打印
            print("a.keys()=%s" % (a.keys()))
            print("b=%s" % (b))
            print("c=%s" % (c))
            # list中的中文难以正常显示，需如下这样单独打印
            print("b[0]=%s" % (b[0]))
            
            # 执行后结果如下:
            a.keys()=['\xe5\xb9\xb3\xe5\xae\x89\xe9\x93\xb6\xe8\xa1\x8c', '\xe6\xb5\xa6\xe5\x8f\x91\xe9\x93\xb6\xe8\xa1\x8c']
            b=['\xe5\xb9\xb3\xe5\xae\x89\xe9\x93\xb6\xe8\xa1\x8c', '\xe6\xb5\xa6\xe5\x8f\x91\xe9\x93\xb6\xe8\xa1\x8c']
            c=['000001.XSHE', '600000.XSHG']
            b[0]=平安银行
            
            # 可以看到，list中的中文难以正常显示。
            # 而且结果都是list（有中括号）
	

### 自测与自学
- 实践下本文中的各个例子
- 了解下list与dict的更多用法。参考资料：[列表](https://www.joinquant.com/post/1970)、[字典](https://www.joinquant.com/post/1971)
- 以下代码打印结果是？

        a=1
        b=2
        c=a+b
        b=a+c
        a=b+c
        print(a+b+c)
        
- 以下代码的打印结果是？

        lt=[1,2,[3,4],5]
        print(lt[1])
        print(lt[1] lt[2][1])


---
[查看下一篇](https://www.joinquant.com/post/13153)
