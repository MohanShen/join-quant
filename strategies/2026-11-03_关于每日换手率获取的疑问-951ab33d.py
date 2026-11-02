# Clone from JoinQuant
# postId: 951ab33d1cc2d8e24e62853d2644eddf
# backtestId: 166da1d760c10e037521d4f6ff2d853e
# title: 关于每日换手率获取的疑问

# 导入函数库
from jqdata import *
import talib 
import datetime
'''
from sqlalchemy import create_engine
eg=create_engine("mysql+mysqldb//root:270485@Sk_~7@127.0.0.1:3306/jqdata?charset=utf8")
df = pd.read_sql_query(sql, engine)

print(df)

days=get_trade_days(start_date=None, end_date='2020-11-24', count=None)
'''
def initialize(context):
    run_daily(test,time='16:00')

def test(context):
    #获取倒数10交易日的日数据df
    pricedf = get_price(security='000813.XSHE',end_date=context.current_dt, count=8,\
    frequency='1d',fields=('open', 'close', 'high','volume', 'money'),\
    skip_paused=True, fq='pre', panel=False,fill_paused=False)
    #获取倒数10交易日的换手率和市值
    exchange_rate = get_valuation('000813.XSHE', end_date=context.current_dt,\
    fields=['turnover_ratio','circulating_cap'], count=8)
    #打印检查
    print('以下为交易日数据df：')
    print(pricedf)
    print('以下为换手率和市值：')
    print(exchange_rate)

    