# Clone from JoinQuant
# postId: 6941bfbeb4f8ed72175c9aad284faa28
# backtestId: 0f66f0e01733cced7a145e39480f11f3
# title: 为什么限价单卖出按比限价低的价格成交了？

# 初始化函数，设定要操作的股票、基准等等

def initialize(context):
    set_option('use_real_price', True)
    df = get_all_securities(["stock"],"2016-10-01")
    df = df[df.display_name!=""]
    df = df[df.end_date > context.previous_date]
    context.sec_list = [i for i in df.index]
    context.bought = {}
    
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次

def before_trading_start(context):
    log.info("new_day_begin===============================")
    for stock in context.bought:
        item = context.bought[stock]
        #print item
        order(stock, -item["count"], LimitOrderStyle(item["price"]))
        log.info("sell limit %s at %s",stock, item["price"])
        
    
    
    high_data = history( 5, '1d', 'high', security_list = context.sec_list, fq=None)
    low_data = history( 5, '1d', 'low', security_list = context.sec_list, fq=None)
    mean_data = (high_data + low_data) / 2
    #print mean_data
    for stock in mean_data.columns:
        #print stock
        c_down = True
        for day in range(4):
            if mean_data.iloc[day][stock] <= mean_data.iloc[day + 1][stock]:
                c_down = False
        
        if not c_down:
            continue
        
        buy_price = mean_data.iloc[-1][stock]
        buy_amount = 100
        can_buy = True
        
        cd = get_current_data()
        if cd[stock].paused:
            can_buy = False
            
        if stock in context.bought:
            can_buy = False
            
        while buy_price * buy_amount < 1800:
            buy_amount += 100
            
        if buy_price * buy_amount > context.portfolio.available_cash:
            can_buy = False
            
        if can_buy:
            order(stock, buy_amount, LimitOrderStyle(buy_price)) 
        else:
            #log.info("%s条件不满足，不再购买", stock)
            pass

def handle_data(context, data):
    pass

def after_trading_end(context):
    orders = get_orders()
    for my_order in orders.values():
        if my_order.is_buy and my_order.filled != 0:
            if my_order.security not in context.bought:
                context.bought[my_order.security] = {}
            context.bought[my_order.security]["count"] = my_order.filled
            context.bought[my_order.security]["price"] = my_order.price * 1.015
            log.info("buy %s %s at %s",my_order.security, my_order.filled, my_order.price)
        elif my_order.is_buy == False and my_order.filled != 0:
            if context.bought[my_order.security]["count"] > my_order.filled:
                context.bought[my_order.security]["count"] -= my_order.filled
            else:
                del context.bought[my_order.security]
            log.info("sell %s %s at %s",my_order.security, my_order.filled, my_order.price)
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
            
    
    
    
  