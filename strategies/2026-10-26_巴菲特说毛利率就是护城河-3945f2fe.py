# Clone from JoinQuant
# postId: 3945f2fe07fba75d6d5092e01e5c321f
# backtestId: 93bf35ee944d57298bd63a89091aab12
# title: 巴菲特说毛利率就是护城河

# 导入聚宽函数库
import jqdata
import pickle
def save2file(var,varname):
	filename = "m_data/%s.dat"%varname
	write_file(filename,pickle.dumps(var))

def load4file(varname):
	filename = "m_data/%s.dat"%varname
	return pickle.loads(read_file(filename))
	
def getQList_str(year,q,cnt):
    ql = []
    q = QData(year,q)
    for i in range(0,cnt):
        ql.append(str(q - i))
    return ql

class QData:
    def __init__(self,year=None,q=None):
        if year is None and q is None:
            dt = datetime.datetime.now()
            self.year = dt.year
            self.q = dt.month / 3
        elif q is None and len(year) in (10,8):
            self.year = int (year[:4])
            if len(year) == 10:
                self.q = int(year[5:7]) / 3
            else:
                self.q = int(year[4:6]) / 3
        else:                
            self.year = year
            self.q = q
            
        self.normal()
        
    def normal(self):
        while self.q <= 0:
            self.q += 4
            self.year -= 1

    def date(self):
        tail = 30
        if self.q in (1,4):
            tail = 31
        return "%d-%02d-%02d"%(self.year,self.q*3,tail)
    
    def __sub__(self,value):
        return QData(self.year,self.q - value)

    def __str__(self):
        return "%dq%d"%(self.year,self.q)
        
def get_income(qq):
    q = query(
        income.code,
        income.pubDate,
        income.statDate,
        income.operating_cost,
        income.operating_revenue,
    )
    #fdf = get_fundamentals(q).dropna()
    fdf = get_fundamentals(q,statDate=qq).dropna(0)
    fdf.columns = [ 'code','pubDate','statDate','operating_cost','operating_revenue' ]
    fdf.index = fdf.code
    return fdf.iloc[:,1:]
    #fdf = fdf.iloc[:,-1*len(factors):]
    #print qq
#get_income('2016q2')

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    log.set_level('order','error')
    
    run_monthly(func=select_stocks, monthday=1, time='open')
    g.stock_info = {}
    g.last_year = 0
    g.choice_num = 10
    

def ValidCode(context,stocks):
    print "ValidCode b %d"%(len(stocks))
    da = g.current_data
    valid = []
    start_date = (context.current_dt - timedelta(days = int(356*5))).date()
    dead_end = (context.current_dt - timedelta(days = 30*11)).date()
    dead_begin = (context.current_dt - timedelta(days = 30*13)).date()

    for code in stocks:
        start = get_security_info(code).start_date
    #    if start > dead_begin and start < dead_end:
    #        continue
        if not da[code].is_st and \
            start < start_date :
            valid.append(code)
    print "ValidCode e %d"%(len(stocks))
    return valid
    
def select_stocks(context):
    #if context.current_dt.month % 3 != 2:
    #    return
    
    d_today = context.current_dt.strftime("%Y-%m-%d")
    g.current_data = get_current_data()
    stock_all = list(get_all_securities("stock").index.values)
    stock_all = ValidCode(context,stock_all)
    
    qqs = getQList_str(context.current_dt.year,context.current_dt.month/3,25)
    for qq in g.stock_info.keys():
        if qq not in qqs:
            del g.stock_info[qq]
            
    for qq in qqs:
        if qq not in g.stock_info:
            #print("add income %s"%qq)
            g.stock_info[qq] = get_income(qq)
            #print g.stock_info[qq].head(10)
    
    stocks = []
    grosss = []
    
    
    for code in stock_all:
        gross = 0
        cnt  = 0
        for qq in qqs:
            info = g.stock_info[qq]
            if code not in info.index:
                continue
            if info.pubDate[code] < d_today:
                gro = (info.operating_revenue[code] - info.operating_cost[code])/info.operating_revenue[code]
                if gro < 0.5:
                    break;
                gross += gro 
                cnt +=1
                if cnt == 20:
                    break
        if cnt == 20:
            stocks.append(code)
            grosss.append( gross / cnt )
    
    dfs = pd.DataFrame(data={'score':grosss},index=stocks)
    g.stock_order =dfs.sort(columns='score',ascending=False)
    g.stock_buy = list(g.stock_order.head(10).index.values)
    log.info(g.stock_order.head(10))
    run_buy(context)

def run_buy(context):
    holds = set(context.portfolio.positions.keys())
    
    g.stock_buy = [ s for s in g.stock_buy if (not g.current_data[s].paused) and \
        (g.current_data[s].day_open != g.current_data[s].high_limit) ]
    g.stock_buy = g.stock_buy[:g.choice_num]
    g.stock_sell = holds - set(g.stock_buy)
    g.stock_sell = [ s for s in g.stock_sell if (not g.current_data[s].paused) and \
        (g.current_data[s].day_open != g.current_data[s].high_limit) ]
    
    g.stock_buy = [ s for s in g.stock_buy if s not in holds ]
    
    log.info("buy:%s sell:%s"%(g.stock_buy,g.stock_sell))
    for code in g.stock_sell:
        order_target(code,0)
    
    value = context.portfolio.total_value / g.choice_num * 1.01
    for code in g.stock_buy:
        order_target_value(code, value)
                
                
            
            
    
        
    

 
