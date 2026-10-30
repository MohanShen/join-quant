# Clone from JoinQuant
# postId: 7b325e8915bcf901e94acd8fa8876185
# backtestId: 9ba08e27365b1f52cb07ba067ea26de6
# title: 写了过滤停牌股，但是还会选出停牌股欣泰电器~

def handle_data(context, data):
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    stock_list = select_stock(context)
    if hour == 9 and minute == 30:
        get_open_price(context, stock_list)
        print(get_open_price(context, stock_list))
    
def get_open_price(context, stock_list):
    open_dict = {}
    for stock in stock_list:
        h = attribute_history(stock, count=1, unit='1d', fields='open', skip_paused=True, df=True, fq='pre')
        open_dict[stock] = h['open']
    return open_dict
    
def select_stock(context):
    all_stock_list = get_all_stock(context)
    stock_list = filter_st_stock(all_stock_list)
    stock_list = filter_paused_stock(stock_list)
    stock_list = filter_by_fundamentals(context, stock_list)
    return stock_list
    
# 获取全部股票    
def get_all_stock(context):
    all_stock_list = list(get_all_securities(types='stock', date=context.current_dt).index)
    return all_stock_list
  
# 过滤ST，*ST，退
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if \
        not current_data[stock].is_st \
        and 'ST' not in current_data[stock].name \
        and '*' not in current_data[stock].name \
        and '退' not in current_data[stock].name]
        
# 过滤停牌股,当日停牌
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if \
        not current_data[stock].paused]
    
        
# 财务数据滤股
def filter_by_fundamentals(context, stock_list):
    all_stock_list = get_all_stock(context)
    q = query(valuation.code)
    q = q.filter(valuation.code.in_(all_stock_list))
    q = q.filter(valuation.circulating_market_cap<50)
    q = q.filter(valuation.pe_ratio<100)
    q = q.order_by(valuation.circulating_market_cap.asc())
    q = q.limit(10)
    df = get_fundamentals(q)
    stock_list = list(df['code'])
    return stock_list
    


    