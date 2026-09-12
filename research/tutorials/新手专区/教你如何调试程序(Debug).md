---
title: "【有用功】教你如何调试程序(Debug)"
category: 新手专区
learners: 17604
postedAt: 2016-10-20 18:47:25
source: 量化课堂 (/study)
fetchedAt: 2026-09-12T16:27:09.754Z
# NOTE: postId/studyId are re-minted per request and are NOT recorded —
#       title + category is this lesson's stable handle.
---

# 【有用功】教你如何调试程序(Debug)

在编写策略中经常会遇到各种各样的错误，十分繁琐，但这又是程序化交易必不可少的一步。

下面小编就教大家如何在 JoinQuant 进行代码调试。

其实在 JoinQuant 运行出错的原因类型也就那么几点。

1. python代码格式错误，如缩进、用法不对等 —— 这个自行百度或者 google 一下错误提示就基本可以搞定
2. 数据处理的问题，如对DataFrame、list、dict操作失误造成的 —— 学习一下相关处理方法即可，可在量化课堂Python 教学中学到相关的基础知识。
3. 还有一些奇奇怪怪的问题，学习随着自己写的程序多了，见的多了，可自行解决。

如下两图所示就是错误提示：

![360反馈意见截图1761061811613696.png][1]

![360反馈意见截图17340913106866.png][2]

**调试的方法可概括为如下几点：**
一、先看一下出错代码第几行，自行查看一下，先排除是拼写或者缩进等简单错误。

二、百度 或者 google 一下错误提示代码，如查询 `python unexpected indent`, 会有非常多的结果可供参考。
当然也可以去 [Stack Overflow](http://stackoverflow.com/) 查询，十分好用，强烈推荐。

三、把错误处前后变量打印出来看一下，是不是所需要的数据对象格式不同造成的。
可以使用 print 或者 try...excpt... ，把相关的变量输出看一下。

**示例：**

如下代码：
```python
1 def initialize(context):
2    g.security = '000001.XSHE'
3    set_universe([g.security])
4    
5 def handle_data(context, data):
6     get_lists(context)
7     print 'done'
8    
9 def get_lists(context):
10    lists = get_all_securities('stock')
11    log.info(lists)
12    h = history(3, '1d', field='close', security_list = lists, df=False)
13    return [stock for stock in lists if h[stock][-1] < h[stock][0]]
```
运行之后会报错：
```python
2016-06-01 09:30:00 - INFO -             display_name  name  start_date    end_date   type
000001.XSHE         平安银行  PAYH  1991-04-03  2200-01-01  stock
000002.XSHE         万  科Ａ   WKA  1991-01-29  2200-01-01  stock
000004.XSHE         国农科技  GNKJ  1990-12-01  2200-01-01  stock
........

2016-06-01 09:30:00 - ERROR - Traceback (most recent call last):
  File "kuanke/user_space.py", line 146, in exec_msg
    return getattr(self, func)(*msg['args'], **msg['kwargs'])
  File "kuanke/user_space.py", line 319, in handle_data
    self.func_handle_data(self.user_context, user_space_api.SecuritiesData(context.current_dt))
  File "user_code.py", line 6, in handle_data
    get_lists(context)
  File "user_code.py", line 12, in get_lists
    h = history(60, '1d', field = ('close'), security_list = lists)
  File "kuanke/user_space_api.py", line 978, in history
    HistoryOptions(fq=fq, skip_paused=bool(skip_paused), df=bool(df)))
  File "/home/server/y/envs/kuanke/lib/python2.7/site-packages/functools32/functools32.py", line 380, in wrapper
    result = user_function(*args, **kwds)
  File "kuanke/user_space_api.py", line 943, in history_daily
    options=options,
  File "kuanke/user_space_utils.py", line 465, in get_price_daily_single
    a = get_all_day_data(security)
  File "/home/server/y/envs/kuanke/lib/python2.7/site-packages/functools32/functools32.py", line 380, in wrapper
    result = user_function(*args, **kwds)
  File "kuanke/user_space_utils.py", line 169, in get_all_day_data
    api_proxy.prepare_all_day_data(security)
  File "kuanke/user_space.py", line 73, in func
    raise ret
Exception: 股票"display_name"不存在
```

日志打印如上所示，看着眼花缭乱，有木有~~~~
虽说程序给出了 Exception，但明显不是看到不应该是这个问题（机器也没有那么智能）。

再看一下错误提示，发现提示程序第六行出现错误。
第六行我们调用了 `get_lists(context)` 函数，这里出现错误。
因此我们要查询一下 get_list(contest) 函数。
接着看错误提示，提示 line 12 出现错误，之后又提示了一大堆的错误。
接着我们要核查一下是不是 line 12，history 函数的问题, history 函数如下所示：

`history(count, unit='1d', field='avg', security_list=None, df=True, skip_paused=False, fq='pre')`

这种函数一般的错误就是**传入参数的格式不对**，可能是因为传参的顺序出错或者本身传入的格式就有问题。
我们对比一下程序发现，`count, unit, field`没什么错误，错误基本是 security_list 的问题。带着怀疑，我们应该打印一下 lists 看一下，是不是一个list。

为了方便，我的程序已经在第11行打印了传入的lists。
发现结果是一个多列的 DataFrame。因为我是想要返回结果的 index 数据。因此应该把 第10行改为`lists = get_all_securities('stock').index`,并输出 lists 看一下。lists 的结果如下：

```python
2015-06-01 09:30:00 - INFO - Index([u'000001.XSHE', u'000002.XSHE', u'000004.XSHE', u'000005.XSHE',
       u'000006.XSHE', u'000007.XSHE', u'000008.XSHE', u'000009.XSHE',
       u'000010.XSHE', u'000011.XSHE', 
       ...
       u'603969.XSHG', u'603979.XSHG', u'603986.XSHG', u'603988.XSHG',
       u'603989.XSHG', u'603993.XSHG', u'603996.XSHG', u'603997.XSHG',
       u'603998.XSHG', u'603999.XSHG'],
      dtype='object', length=3010)
      
2015-06-01 09:30:00 - INFO - done

2015-06-02 09:30:00 - INFO - Index([u'000001.XSHE', u'000002.XSHE', u'000004.XSHE', u'000005.XSHE',
       u'000006.XSHE', u'000007.XSHE', u'000008.XSHE', u'000009.XSHE',
       u'000010.XSHE', u'000011.XSHE', 
       ...
       u'603969.XSHG', u'603979.XSHG', u'603986.XSHG', u'603988.XSHG',
       u'603989.XSHG', u'603993.XSHG', u'603996.XSHG', u'603997.XSHG',
       u'603998.XSHG', u'603999.XSHG'],

2015-06-02 09:30:00 - INFO - done
      
......................
```

**程序运行成功**

当然在代码调试的过程中还会遇到其他各种各样的错误，需要你慢慢积累。

如   https://www.joinquant.com/post/1936   这篇帖子中的问题，程序会提示：

```python
  File "user_code.py", line 101
    def chk_position(context):
      ^
SyntaxError: invalid syntax
```

但仔细检查，并没错误，真正的错误是由于第98行最后缺少一个括号，程序认为之后的是属于98行括号内的内容。

**总结来说**，大多数的错误其实通过搜索相关错误提示是可以找到解决办法；再者通过简单的调试与分析，也可以基本解决问题。

**调试路漫漫，还望各位稍安勿躁、平心静气，毕竟修行是一辈子的事情~**


  [1]: https://image.joinquant.com/9f73f277caec4e05e037cfe3816d8dcc
  [2]: https://image.joinquant.com/f7b578a757a18814edb277fb17a419da
