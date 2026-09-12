---
title: "【API解析】|关于order/trader对象及订单处理"
category: 新手专区
learners: 7323
postedAt: 2019-06-11 14:10:12
source: 量化课堂 (/study)
fetchedAt: 2026-09-12T16:26:47.165Z
# NOTE: postId/studyId are re-minted per request and are NOT recorded —
#       title + category is this lesson's stable handle.
---

# 【API解析】|关于order/trader对象及订单处理

** 获取/整理order等对象的示例:**
https://www.joinquant.com/algorithm/apishare/get?apiId=1758
https://www.joinquant.com/view/community/detail/7bcdf9608532e09bbdceedd1d7709300?type=1

# 1,订单处理
具体撮合方式参见api:   https://www.joinquant.com/help/api/help?name=api#订单处理
非交易时间下单会等待交易时间再进行撮合,每天16:00对所有未完成订单信息进行撤销(期货交易所将夜盘归于下一个交易日)
当撮合完成时有一个类似于以下的 info(标识order StockOrder,order FutureOrder等等)  :

```
order StockOrder(entrust_id=1536139611 security=600741.XSHG mode=OrderAmount: _amount=100 style=MarketOrderStyle side=long margin=False entrust_time=2016-06-01 09:30:00 error=) trade price: 12.78, amount:100, commission: 5.0
```
### order下单后，持仓/可用资金是不是立即变化?
这个和下单方式有关，查看我们的[订单处理]( https://www.joinquant.com/help/api/help?name=api#订单处理)  
所有市价单下单之后同步完成(也即 order_XXX 系列函数返回时完成), context.portfolio 会同步变化  
限价单，下单之后 context.portfolio.available_cash 和 context.portfolio.positions 不会同步变化  ,以order StockOrder出现的时间为准。
无论市价单还是限价单,买入时仓位资金会同步变化(如果已下单,未成交,会冻结对应的资金到locked_cash),卖出时每产生一个Trade对象(交易)账户资金同步变化一次。


# 2,交易函数
https://www.joinquant.com/help/api/help?name=api#交易函数

下限价单指定style=LimitOrderStyle(目标价位) 即可, 买入时不能高于目标价位, 卖出时不能低于目标价位, 如果不满足, 则等待满足后再交易,注意股票的交易单位为每手100股。

下单失败可以查看日志中对应时间点的warning,有详细说明  
下单可能的失败原因:    
1.标的数量经调整后变成0 (请看下面的说明)
2.标的停牌
3.标的成交量不足以交易(涨停,跌停等)
4.标的未上市或者退市
5.标的不存在
6.为股票、基金开了空单
7.选择了不存在的仓位号，如没有建立多个仓位，而设定pindex的数大于0  

当订单直接变为废单时,下单函数会返回None而不是order对象,此时直接调用order对象的属性会引发报错`'NoneType' object has no attribute XXX`  
 
 解决方法:
```
 Order = order('000001.XSHE',1000)
 if not Order:
     print('下单失败')
 if Order:
     print(Order.filled)  #打印已成交数量
```
注意:
因为下列原因, 有时候实际买入或者卖出的股票数量跟您设置的不一样，这个时候我们会在您的log中添加警告信息。
1.卖出时会根据您持有股票的数量来限制您卖出的数量
2.我们会遵守A股交易规则: 每次交易数量只能是100的整数倍, 但是卖光所有股票时不受这个限制
3.在下单时会根据您当前的可用资金,成交量等对下单股数进行调整。
4.您在触发下单信息时自己打印的成交记录(信息)并不是特别可靠,请以实际结果及日志信息为准
 系统会在每天16:00取消所有未完成交易(撤单),查询get_orders(status=OrderStatus.canceled)需要在16点至17点之间查询。


下单失败可以查看日志中对应时间点的warning,有详细说明  


关于下单函数的说明请查看API或者 [【API解析】| 关于下单函数的说明](https://www.joinquant.com/post/16457)

ps:(图片显示有点迷糊,右键点击图片,选择'在新标签页中打开图片'即可浏览高清图片)
![Img]( https://image.joinquant.com/78edfa8559517539185601d4d5e8d8be)


# 3order对象
api链接:https://www.joinquant.com/help/api/help?name=api#对象
** 每天17:00会对今天产生的order对象全部进行归类,往后调用get_orders获取的order对象归属于第二天(get_orders仅可以获取当天的order对象)。所以保存起来的orderID不要在17:00之后或第二天通过get_orders调用,可能引起异常。模拟交易由于会重启进程,所以order对象也不可以在当天17点之后调用; 如果需要在交易日结束后获取这些对象,请在17:00之前对这些对象轴的数据进行提取 , 使用全局变量保存为字典等**
注意这是一个对象,获取对象中的各种属性可以用UserOrder.order_id等方法,order对象的表示形式类似于(标识UserOrder):
(注意获取的order对象是否是如下形式,有时由于大家的获取方式会获得一个包含多个order对象的列表/字典,应该先提取对象,再获取对象属性)
```
UserOrder({'status': open, 'style': LimitOrderStyle: _limit_price=7.58, 'order_id': 1536135521, 'price': 0.0, 'pindex': 0, 'amount': 100, 'action': u'open', 'security': '000001.XSHE', 'side': u'long', 'filled': 0, 'add_time': datetime.datetime(2016, 6, 1, 9, 30)})
```
关于order对象中的avg_cost和price: (avg_cost通过 order.avg_cost 获取,直接打印order是不显示的)    
卖单中: price指的是单个订单的平均成交价,avg_cost指的是这只股票从开始持仓到卖出时的平均成交价(平均持仓成本)  
买单中: 两者都是订单的平均成交价  

ps:一般我们用的都是order对象,注意和trade对象进行区分
```
def initialize(context):
    run_daily(func2, time='every_bar')

def func(context):
    orders = order('000001.XSHE', 100)
    print(orders)
    print(orders.order_id)
    print(orders.status)
    print(orders.price)
    print('='*50)

def func2(context):
    orders = order('000001.XSHE', 100)
    print(orders)
    if orders is None:
        print("失败...")
    else:
        print(orders.is_buy)
        print(orders.status)
        print(orders.price)
    print('='*50)
```  

# 4,OrderStatus对象
通过 order对象.status 获取到的结果是一个[枚举对象](https://pypi.python.org/pypi/enum34)。如果想查询状态是否是某种状态,需要获取具体的属性或者和status对象直接进行比较,如果直接使用对象和字符串比较将产生错误。如下代码得到的结果是一样的:
```
g.Order_class.status.name=='open'
g.Order_class.status.value==0
g.Order_class.status==OrderStatus.open
```
由于(回测/模拟)16点会撤销未完成订单,17点后通过get_orders等获取的order对象归属于下一交易日,所以查询时需要注意这两个时间点。
盘后获取当天未完成订单(包括盘后自动撤销的限价单):
```
def func(context):  #16:00之后,17点之前运行
    order_dict = get_orders(status = OrderStatus.canceled)
```
# 5,获取trader中的信息
```
## 收盘后运行函数  
def after_market_close(context):
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    print('-'*50)
```
