# Clone from JoinQuant
# postId: 7c1866879ff3e51aa654e066cef8ac71
# backtestId: 0828d4c1f20f96570916c0147df411ab
# title: 【数据问题】用 get_current_data()获取2018年1月8日开盘价数据错误

# 导入函数库
import jqdata

## 初始化函数，设定基准等等
def initialize(context):
    set_option('use_real_price', True)
    log.info('初始函数开始运行且全局只运行一次')
    g.tap=0.5
    g.rangeL=0
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)

    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF1512.CCFX'或'IH1602.CCFX'是一样的）
      # 开盘前运行
      # 开盘时运行
    #run_daily( show_info, time='open',reference_security='RB9999.XSGE')   
    run_daily( market_open, time='every_bar',reference_security='RB9999.XSGE')
   
      # 收盘后运行
    #run_daily( after_market_close, time='after_close', reference_security='IF1512.CCFX')
## 开盘前运行函数
def show_info(context):
    main_contact=get_dominant_future('RB')
    fu_stat=attribute_history( security=main_contact,count=1, unit='1d', fields=['high','low','close'], df=True, skip_paused=True, fq='pre')
    g.rangeL=g.tap*max(abs(fu_stat['high'][0]-fu_stat['close'][0]),abs(fu_stat['close'][0]-fu_stat['low'][0]))
    current_data = get_current_data()
    g.base=current_data[main_contact].day_open
    g.buyline=g.base+g.rangeL
    g.sellline=g.base-g.rangeL
    print(fu_stat)
    print("range:",g.rangeL)
    print("day_open:",g.base)
    print("buylie:",g.buyline)    
    print("sellline:",g.sellline)
    
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    #send_message('美好的一天~')
    ## 获取要操作的股票(g.为全局变量)
## 开盘时运行函数
def market_open(context):
    main_contact=get_dominant_future('RB')
    real_s_contact=context.portfolio.short_positions.keys()
    real_l_contact=context.portfolio.long_positions.keys()
    real_contact=(real_s_contact+real_l_contact)
    
    #如果出现主力合约换月的情况将持仓替换为主力合约
    if (real_s_contact!=[] and real_s_contact[0]!=main_contact):
        order_target(real_s_contact[0], amount=0, style=None, side='short', pindex=0) 
        order_target(main_contact, amount=1, style=None, side='short', pindex=0)          
    if (real_l_contact!=[] and real_l_contact[0]!=main_contact):
        order_target(real_contact[0], amount=0, style=None, side='long', pindex=0)   
        order_target(main_contact, amount=1, style=None, side='long', pindex=0)    
    fu_stat=get_bars(main_contact, 1, unit='1d',fields=['high','low','close'],include_now=False)
    fu_stat=attribute_history( security=main_contact,count=1, unit='1d', fields=['high','low','close'], df=True, skip_paused=True, fq='pre')
    g.rangeL=g.tap*max(abs(fu_stat['high'][0]-fu_stat['close'][0]),abs(fu_stat['close'][0]-fu_stat['low'][0]))
    current_data = get_current_data()
    g.base=current_data[main_contact].day_open
    g.buyline=g.base+g.rangeL
    g.sellline=g.base-g.rangeL
    fu_close=get_bars(security=main_contact, count=1, unit='1m', fields=['high','low'], include_now=False)
    #print("data:",fu_close)
    print("day_open:",g.base)
    #print("buylie:",g.buyline)    
    #print("sellline:",g.sellline)
    #根据主力合约进行开仓
    #if (fu_close['high'][0]>=g.buyline and real_l_contact==[]):
         #order_target(main_contact, amount=0, style=None, side='short', pindex=0)
         #order_target(main_contact, amount=1, style=None, side='long', pindex=0)
    #if fu_close['low'][0]<=g.sellline and real_s_contact==[]:
        #order_target(main_contact, amount=0, style=None, side='long', pindex=0)
        #order_target(main_contact, amount=1, style=None, side='short', pindex=0)
   

        
