# Clone from JoinQuant
# postId: e8e578c31d6944ac3fae2a1f0f5c1fc9
# backtestId: 726b253dec23e30f5120b3e750ed4438
# title: 红利ETF反转策略，含email发送，年化16%胜率100%

# 导入函数库
from jqdata import *
from jqfactor import get_factor_values
import datetime
import math
from scipy.optimize import minimize
import numpy as np
import pandas as pd
import time
import datetime
import talib as talib
import smtplib
from email.mime.text import MIMEText
from email.header import Header

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    # set_benchmark("515080.XSHG")
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 开启动态复权模式(真实价格)
    set_option("use_real_price", True)
    # 输出内容到日志 log.info()
    log.info("初始函数开始运行且全局只运行一次")
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level("order", "error")
    # 固定滑点设置ETF 0.001(即交易对手方一档价)
    set_slippage(FixedSlippage(0.002), type="fund")
    # 股票交易总成本0.3%(含固定滑点0.02)
    set_slippage(FixedSlippage(0.02), type="stock")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5,
        ),
        type="stock",
    )
    # 设置货币ETF交易佣金0
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.000,
            open_commission=0.0000,
            close_commission=0.0000,
            close_today_commission=0,
            min_commission=0,
        ),
        type="mmf",
    )
    # 全局变量
    g.fill_stock = "511880.XSHG"  # 货币ETF,用于现金管理
    g.strategys = {}
    g.portfolio_value_proportion = [1]
    g.positions = {i: {} for i in range(len(g.portfolio_value_proportion))}  # 记录每个子策略的持仓股票
    g.smtp_host = 'smtp.qq.com'
    g.smtp_port = 465
    g.smtp_user = 'xxxxx@qq.com'#改成自己的qq邮箱
    g.smtp_pass = 'wkftnfosfprsbjfe'#改成自己邮箱生成的授权码
    g.smtp_receiver = 'xxxxx@qq.com'
    
    
    g.value = 0
    # 子策略执行计划
    if g.portfolio_value_proportion[0] > 0:
        run_daily(ETF_Revert_adjust,"9:31")
    # 每日剩余资金购买货币ETF
    run_daily(end_trade, "14:55")


def process_initialize(context):
    print("重启程序")
    g.strategys["ETF反转策略"] = ETF_Revert_Strategy(context, index=0, name="ETF反转策略")


# 买入货币ETF
# 尾盘处理
def end_trade(context):
    current_data = get_current_data()

    # 卖出未记录的股票（比如送股）
    keys = [key for d in g.positions.values() if isinstance(d, dict) for key in d.keys()]
    for stock in context.portfolio.positions:
        if stock not in keys and stock != g.fill_stock and current_data[stock].last_price < current_data[stock].high_limit:
            if order_target_value(stock, 0):
                log.info(f"卖出{stock}因送股未记录在持仓中")



# 卖出货币ETF换现金
def get_cash(context, value):
    if g.fill_stock not in context.portfolio.positions:
        return
    current_data = get_current_data()
    amount = math.ceil(value / current_data[g.fill_stock].last_price / 100) * 100
    position = context.portfolio.positions[g.fill_stock].closeable_amount
    if amount >= 100:
        order(g.fill_stock, -min(amount, position))

def ETF_Revert_adjust(context):
    g.strategys["ETF反转策略"].adjust()
    record(value = g.value)



# 策略基类
class Strategy:

    def __init__(self, context, index, name):
        self.context = context
        self.index = index
        self.name = name
        self.stock_sum = 1
        self.hold_list = []
        self.min_volume = 2000
        self.buy_info = []
        self.sell_info = []
        self.send_mail = False
        self.open_count = 0
    # 获取策略当前持仓市值
    def get_total_value(self):
        if not g.positions[self.index]:
            return 0
        return sum(self.context.portfolio.positions[key].price * value for key, value in g.positions[self.index].items())

    # 检查昨日涨停票
    def _check(self):
        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())
        # 获取昨日涨停列表
        if self.hold_list != []:
            df = get_price(
                self.hold_list,
                end_date=self.context.previous_date,
                frequency="daily",
                fields=["close", "high_limit"],
                count=1,
                panel=False,
                fill_paused=False,
            )
            df = df[df["close"] == df["high_limit"]]
            if list(df.code) != []:
                # 对昨日涨停股票观察到尾盘如不涨停则提前卖出
                for stock in list(df.code):
                    self.order_target_value_(stock, 0)

    # 调仓(等权购买输入列表中的标的)
    def _adjust(self, target):
        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())
        portfolio = self.context.portfolio

        # 调仓卖出
        for stock in self.hold_list:
            if stock not in target:
                self.order_target_value_(stock, 0)
                log.info(f"卖出{stock}")

        # 调仓买入
        count = len(set(target) - set(self.hold_list))
        if count == 0 or self.stock_sum <= len(self.hold_list):
            return

        # 目标市值
        target_value = portfolio.total_value * g.portfolio_value_proportion[self.index]

        # 当前市值
        position_value = self.get_total_value()

        # 可用现金:当前现金 + 货币ETF市值
        available_cash = portfolio.available_cash + (portfolio.positions[g.fill_stock].value if g.fill_stock in portfolio.positions else 0)

        # 买入股票的总市值
        value = max(0, min(target_value - position_value, available_cash))

        # 卖出部分货币ETF获取现金
        if value > portfolio.available_cash:
            get_cash(self.context, value - portfolio.available_cash)

        # 等价值买入每一个未买入的标的
        for security in target:
            if security not in self.hold_list:
                self.order_target_value_(security, value / count)
                log.info(f"买入{security}")
    # 调仓(target为字典，key为股票代码，value为目标市值)
    def _adjust2(self, targets):

        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())
        current_data = get_current_data()
        portfolio = self.context.portfolio

        # 清仓被调出的
        for stock in self.hold_list:
            if stock not in targets:
                self.order_target_value_(stock, 0)

        # 先卖出
        for stock, target in targets.items():
            price = current_data[stock].last_price
            value = g.positions[self.index].get(stock, 0) * price
            if value - target > self.min_volume and value - target > price * 100:
                self.order_target_value_(stock, target)

        # 后买入
        for stock, target in targets.items():
            price = current_data[stock].last_price
            value = g.positions[self.index].get(stock, 0) * price
            if target - value > self.min_volume and target - value > price * 100:
                if target - value > portfolio.available_cash:
                    get_cash(self.context, target - value - portfolio.available_cash)
                if portfolio.available_cash > price * 100:
                    self.order_target_value_(stock, target)
    
    def _adjust3(self, target):
        # 获取已持有列表
        open_times = 2
        self.hold_list = list(g.positions[self.index].keys())
        portfolio = self.context.portfolio
        target_value = portfolio.total_value * g.portfolio_value_proportion[self.index]
        position_value = self.get_total_value()
        if open_times == 1:
            value = target_value
        elif open_times == 2:
            value = round(target_value/3,0)
        elif open_times == 3:
            value = round(target_value/6,0)
        

        if len(self.hold_list) > 0 and target==[]:
            # 调仓卖出
            for stock in self.hold_list:
                if stock not in target:
                    self.order_target_value_(stock, 0)
                    self.open_count = 0
                    log.info(f"卖出{stock}")

        elif target!=[] and len(target) == 1:
            if self.open_count < open_times:
                long_positions_dict = portfolio.long_positions
                for position in list(long_positions_dict.values()):  
                    if position.price >= position.avg_cost*0.97:
                        #print("买入价格和持仓价格接近，不买入")
                        return
           
                for security in target:
                    self.open_count += 1
                    final_value = 0
                    if self.open_count == 1:
                        final_value = value
                    elif self.open_count == 2:
                        final_value = value * 3
                    elif self.open_count == 3:
                        final_value = value * 6
                    
                    
                    self.order_target_value_(security, final_value)
                    log.info(f"买入{security} 市值：{final_value}")
        # 买入股票的总市值
        #print(f"position_value:{position_value},open_count:{self.open_count}")
            
   
          
    
    # 自定义下单(涨跌停不交易)
    def order_target_value_(self, security, value):
        current_data = get_current_data()

        # 检查标的是否停牌、涨停、跌停
        if current_data[security].paused:
            log.info(f"{security}: 今日停牌")
            return False

        # 检查是否涨停
        if current_data[security].last_price == current_data[security].high_limit:
            log.info(f"{security}: 当前涨停")
            return False

        # 检查是否跌停
        if current_data[security].last_price == current_data[security].low_limit:
            log.info(f"{security}: 当前跌停")
            return False

        # 获取当前标的的价格
        price = current_data[security].last_price

        # 获取当前策略的持仓数量
        current_position = g.positions[self.index].get(security, 0)

        # 计算目标持仓数量
        target_position = (int(value / price) // 100) * 100 if price != 0 else 0

        # 计算需要调整的数量
        adjustment = target_position - current_position

        # 检查是否当天买入卖出
        closeable_amount = self.context.portfolio.positions[security].closeable_amount if security in self.context.portfolio.positions else 0
        if adjustment < 0 and closeable_amount == 0:
            log.info(f"{security}: 当天买入不可卖出")
            return False

         # 下单并更新持仓
        if adjustment != 0 and order(security, adjustment):
            if adjustment > 0:
                self.buy_info.append(f"买入: {security},金额: {adjustment}")
            else:
                self.sell_info.append(f"卖出: {security},金额: {adjustment}")
            # 更新持仓数量
            g.positions[self.index][security] = target_position
            # 如果目标持仓为零，移除该证券
            if target_position == 0:
                g.positions[self.index].pop(security, None)
            # 更新持有列表
            self.hold_list = list(g.positions[self.index].keys())
            #print(f"{self.name},{self.buy_info},{self.sell_info}")
            if self.send_mail:
                self.notify_trade(self.buy_info,self.sell_info)
            self.buy_info = []
            self.sell_info = []
            return True

        else:
            return False

    # 基础过滤(过滤科创北交、ST、停牌、次新股)
    def filter_basic_stock(self, stock_list):

        current_data = get_current_data()
        return [
            stock
            for stock in stock_list
            if not current_data[stock].paused
            and not current_data[stock].is_st
            and "ST" not in current_data[stock].name
            and "*" not in current_data[stock].name
            and "退" not in current_data[stock].name
            and not (stock[0] == "4" or stock[0] == "8" or stock[:2] == "68")
            and not self.context.previous_date - get_security_info(stock).start_date < datetime.timedelta(375)
        ]

    # 过滤当前时间涨跌停的股票
    def filter_limitup_limitdown_stock(self, stock_list):
        current_data = get_current_data()
        return [
            stock
            for stock in stock_list
            if current_data[stock].last_price < current_data[stock].high_limit and current_data[stock].last_price > current_data[stock].low_limit
        ]

    # 判断今天是在空仓月
    def is_empty_month(self):
        month = self.context.current_dt.month
        return month in self.pass_months
    #发送开平仓通知邮件
    def notify_trade(self,buy_info,sell_info):
        if not (buy_info or sell_info):
            log.info("没有交易操作,无需发送邮件")
            return  
        log.info(f"有交易操作,发送邮件")
    
        current_data = get_current_data()
        current_time = self.context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
        total_value = self.context.portfolio.total_value
    
        # 获取当前持仓信息
        holding_info = []
        for stock in self.context.portfolio.positions:
            position = self.context.portfolio.positions[stock]
            stock_name = current_data[stock].name
            market_value = position.price * position.total_amount
            holding_info.append(
                f"{stock}({stock_name}): "
                f"持仓 {position.total_amount} 份, "
                f"市值 {market_value:,.2f}, "
                f"占比 {(market_value/total_value*100):,.2f}%"
            )
    
        # 构建邮件内容
        title = f"{self.email_title} ({current_time})：\n\n"
        email_content = f"仓位变动通知 ({current_time})：\n\n"
        email_content +=f"策略名称：{self.name}\n\n"
        if sell_info:
            email_content += "卖出操作：\n" + "\n".join(sell_info) + "\n\n"
        if buy_info:
            email_content += "买入操作：\n" + "\n".join(buy_info) + "\n\n"
    
        email_content += f"当前总资产: {total_value:,.2f}\n"
        email_content += f"可用现金: {self.context.portfolio.available_cash:,.2f}\n\n"
    
        if holding_info:
            email_content += "当前持仓：\n" + "\n".join(holding_info)
        else:
            email_content += "当前无持仓"
    
        self.send_email(title, email_content)

    def send_email(self,subject, content, max_retries=3):
        """
        发送邮件函数，带重试机制
        """
        for attempt in range(max_retries):
            try:
                # 创建邮件内容
                msg = MIMEText(content, 'plain', 'utf-8')
                msg['Subject'] = Header(subject, 'utf-8')
                msg['From'] = g.smtp_user
                msg['To'] = g.smtp_receiver
    
                # 创建SMTP连接
                smtp = smtplib.SMTP_SSL(g.smtp_host, g.smtp_port, timeout=10)  # 添加超时设置
    
                try:
                    # 登录
                    smtp.login(g.smtp_user, g.smtp_pass)
    
                    # 发送邮件
                    smtp.sendmail(g.smtp_user, g.smtp_receiver, msg.as_string())
    
                    log.info("邮件发送成功")
                    return True
    
                except smtplib.SMTPAuthenticationError:
                    log.error("邮件发送失败：邮箱账号或授权码错误")
                    return False
    
                except smtplib.SMTPException as e:
                    log.error(f"SMTP错误：{str(e)}")
                    if attempt <  max_retries - 1:  # 如果不是最后一次尝试
                        continue
                    return False
    
                finally:
                    try:
                        smtp.quit()
                    except:
                        pass
    
            except Exception as e:
                log.error(f"邮件发送失败（第{attempt + 1}次尝试）：{str(e)}")
                if attempt <  max_retries - 1:  # 如果不是最后一次尝试
                    import time
                    time.sleep(2)  # 等待2秒后重试
                    continue
                return False
    
        return False 



# 全天候ETF策略
class ETF_Revert_Strategy(Strategy):

    def __init__(self, context, index, name):
        super().__init__(context, index, name)
        set_benchmark("510880.XSHG")
        # 设定红利ETF
        g.security = '510880.XSHG'
        
        # 设定均线周期为200日
        g.ma_window = 144
        # 设定买入比例（低于均线的比例）
        g.buy_ratio = 1
        # 设定卖出比例（高于均线的比例）
        g.sell_ratio = 1.05
        self.email_title = "ETF反转策略仓位变动通知"
        self.send_mail = False
        self.stop_loss_data = self.context.current_dt.date() - timedelta(days=30)
    # 调仓
    def adjust(self):
        security = g.security
        ma_window = g.ma_window
        buy_ratio = g.buy_ratio
        sell_ratio = g.sell_ratio
        stocks = []
        stocks.append(g.security)
        date_s1 = self.context.previous_date
        date_s2 = date_s1 - datetime.timedelta(3)
        # 获取ETF的收盘价数据

        close_data = attribute_history(security, count=ma_window, unit='1d',
            fields=['close'],skip_paused=True, df=True, fq='pre')
        
        
        
        # 计算144日均线
        ma_144 = close_data['close'].mean()
        
        current_price = close_data['close'][-1]
        g.value = 0
        long_positions_dict = self.context.portfolio.long_positions
        for position in list(long_positions_dict.values()):  
            g.value = position.value
       
        rsi = talib.RSI(close_data['close'], timeperiod=6)[-1] #6日周期
        rsi = int(rsi)
        
       
        targets = []
       
        
        # 价格小于144日均线以下5%，全仓买入
        if current_price <= ma_144 * buy_ratio and rsi < 30 :
        #if crsi[-1] < db[-1]:
            targets = stocks
            self._adjust3(targets)
            
            
        # 价格大于144日均线以上10%，清空持仓
        elif current_price >= ma_144 * sell_ratio and rsi > 70 :
        #elif crsi[-1] < ub[-1] and crsi[-2]>ub[-2]:
            targets = []
            self._adjust3(targets)
        
        
       
                    
        
        
