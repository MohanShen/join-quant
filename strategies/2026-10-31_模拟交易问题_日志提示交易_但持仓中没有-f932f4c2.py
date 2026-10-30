# Clone from JoinQuant
# postId: f932f4c28d81d93384fe6985f99bd60b
# backtestId: 3ceca2442506410d993800b02896f372
# title: 模拟交易问题，日志提示交易，但持仓中没有

# 导入函数库
import jqdata

import time

def weekly(context):
    print 'weekly %s %s' % (context.current_dt, context.current_dt.isoweekday())


def monthly(context):
    print 'monthly %s %s' % (context.current_dt, context.current_dt.month)
    


# 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    global stocks
    stocks = ['000001.XSHE']
    
    global buystocksl
    buystocksl = ['000001.XSHE']
    
    global surebuystocks
    surebuystocks = []
    
    global stockdict 
    stockdict = { 'abc': 456 }
    
    global stockdicthigh 
    stockdicthigh = { 'abc': 456 }
    
    
    

    #将所有股票列表转换成数组
    tmp_stocks = get_concept_stocks('GN028')
    stocks.extend(tmp_stocks)
    
    tmp_stocks = get_concept_stocks('GN030')
    stocks.extend(tmp_stocks)
    tmp_stocks = get_concept_stocks('GN034')
    stocks.extend(tmp_stocks)
    tmp_stocks = get_concept_stocks('GN030')
    stocks.extend(tmp_stocks)
    tmp_stocks = get_concept_stocks('GN240')
    stocks.extend(tmp_stocks)
    
    tmp_stocks = get_concept_stocks('GN101')
    stocks.extend(tmp_stocks)
    tmp_stocks = get_concept_stocks('GN184')   
    stocks.extend(tmp_stocks)
    
    
    tmp_stocks = get_concept_stocks('GN057')
    stocks.extend(tmp_stocks)
    tmp_stocks = get_concept_stocks('GN074')
    stocks.extend(tmp_stocks)
    
    tmp_stocks = get_concept_stocks('GN109')
    stocks.extend(tmp_stocks)
    
    tmp_stocks = get_concept_stocks('GN092')
    stocks.extend(tmp_stocks)
    
    '''
    
    tmp_stocks = get_concept_stocks('GN127')
    stocks.extend(tmp_stocks)
    tmp_stocks = get_concept_stocks('GN153')
    stocks.extend(tmp_stocks)
    tmp_stocks = get_concept_stocks('GN178')
    stocks.extend(tmp_stocks)
    tmp_stocks = get_concept_stocks('GN208')
    stocks.extend(tmp_stocks)
   
    
   '''
    tmplist = list(set(stocks))
    tmplist.sort(key=stocks.index)
   # tmp_stocks = list(get_all_securities(['stock']).index)
   # log.info(len(tmp_stocks))
    tmp_stocks = tmplist
    stocks=[]
    for stock in tmp_stocks:
         Mdata = attribute_history(stock, 10, '1d', ('open'))
         if len(Mdata) > 0 :
           stocks.append(stock)
    log.info(stocks)
    global totalcash 
    totalcash= 100000
    # 000001(股票:平安银行)
   # g.security = '603896.XSHG'
    # 设定沪深300作为基准
    set_benchmark('510050.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    run_daily(daily, '9:40')
def daily(context):
     buystocks = ['']
     '''
     global surebuystocks
     for bstock in surebuystocks: 
          order_value(bstock, totalcash*0.3)
     surebuystocks=[]
     '''
     global stocks
     for stock in stocks:
        g.security = stock
        security = g.security
        # 获取股票的收盘价
        Mdata = attribute_history(security, 150, '1d', ('open','close', 'high','low','volume', 'factor'), skip_paused=True, df=False, fq='pre')
        if len(Mdata) == 0 :
           continue
        
        # 取得过去150天的平均价格
        MA5 = max(Mdata['high'])
        
        factor = Mdata['factor'][-1]
        #print("30days Max price:",MA5)
        Mdata1 = attribute_history(security, 20, '1d', ('close','volume'), skip_paused=True, df=False, fq='pre')
        MI5 = Mdata1['close'].mean()
       # print("20days avg price:",MI5)
        
        # 平均交易量
        avgvolume= Mdata1['volume'].mean();
        #print("30days avg volume:",avgvolume)
        
        # 取得上一时间点价格
        
        current_data = get_current_data()
        
        current_price = Mdata['high'][-1]
        
        low_price = Mdata['close'][-1]
        
        current_volume = Mdata['volume'][-1]
        last_volume = Mdata['volume'][-2]
        
        # 取得当前的现金
        cash = context.portfolio.cash
        #利润率
        cashradio=0
        
        #最大回撤比例
        highradio=0
        #pe
        pe_radio=-1
        
        
        
        if context.portfolio.positions.has_key(security) :
            if(factor<1):
                stockdict[security] = stockdict[security]*factor
                if(stockdicthigh.has_key(security)):
                    stockdicthigh[security] = stockdicthigh[security]*factor
            cashradio = (low_price  - stockdict[security])/stockdict[security]
            
            
            if stockdicthigh.has_key(security):
                if current_price > stockdicthigh[security]:
                    stockdicthigh[security] = current_price
                highradio = (stockdicthigh[security] - low_price)/stockdicthigh[security]      
            else :
                stockdicthigh[security] = current_price
            q = query(valuation).filter( valuation.code == security)
            df = get_fundamentals(q, time.strftime('%Y-%m-%d',time.localtime(time.time())))
            pe_radio = df['pe_ratio'][0]
            log.info("stock %s, cashradio %s, price %s, hold price %s, factor %s, highest price %s, highradio %s, pe_radio %s" % (security, cashradio,current_data[security].last_price ,stockdict[security],factor,stockdicthigh[security],highradio,df['pe_ratio'][0]))
       
       
       
        # 如果上一时间点价格高出五天平均价1%, 则全仓买入
        if current_price >= 1.0*MA5 and current_volume>1.5*avgvolume and current_volume > last_volume :
            
            q = query(valuation).filter( valuation.code == security)
            df = get_fundamentals(q, time.strftime('%Y-%m-%d',time.localtime(time.time())))
            pe_radio = df['pe_ratio'][0]
            market_cap = df['market_cap'][0]
            
            if pe_radio > 0 and pe_radio < 40 and market_cap > 300:
                # 用所有 cash 买入股票
                if context.portfolio.transferable_cash>totalcash*0.3:
                    global buystocksl
                    #log.info(buystocksl) security in buystocksl and
                    if  current_data[security].paused != True and not context.portfolio.positions.has_key(security):
                        order_value(security, totalcash*0.3)
                        #surebuystocks.append(security)
                        stockdict[security]=low_price
                # 记录这次买入
                        log.info("Buying %s, now price %s" % (security, stockdict[security]))
                buystocks.append(security)
        # 如果上一时间点价格低于五天平均价, 则空仓卖出
        elif (highradio > 0.08 or cashradio<-0.1  ) and context.portfolio.positions[security].closeable_amount > 0:
            # 卖出所有股票,使这只股票的最终持有量为0
            order_target(security, 0)
            stockdicthigh[security] =0
            # 记录这次卖出
            log.info("Selling %s" % (security)) 
            
     log.info(buystocks)
     #global buystocksl
     buystocksl = ['000001.XSHE']
     buystocksl=buystocks
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
#def handle_data(context, data):
   
       # record(stock_price=low_price)
