# Clone from JoinQuant
# postId: 9f6f8188a84cc623f8e39f54d3c7f39c
# backtestId: d5aa141e5f44056c0f7c69cc008600e1
# title: 年化52%-回撤17%-大小盘多策略

# 克隆自聚宽文章：https://www.joinquant.com/post/52465
# 标题：7.4（修正因手续费产生的交易BUG，影响不大）
# 作者：O_iX

# 导入函数库
from jqdata import *
from jqfactor import get_factor_values, Factor, calc_factors
import datetime
import math
from scipy.optimize import minimize
import statsmodels.api as sm
from prettytable import PrettyTable
import smtplib #发邮件
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
            close_tax=0,
            open_commission=0,
            close_commission=0,
            close_today_commission=0,
            min_commission=0,
        ),
        type="mmf",
    )
    
    
    g.market_temperature = "warm"
    
    # 全局变量
    g.fill_stock = "511880.XSHG"  # 货币ETF,用于现金管理
    g.strategys = {}
    
    
    # 小、价、大、国
    
    
    g.portfolio_value_proportion = [0.35, 0.3 , 0 , 0.35]
    g.positions = {i: {} for i in range(len(g.portfolio_value_proportion))}  # 记录每个子策略的持仓股票
    
    
    
    # 小市值
    run_weekly(small_market_adjust, 1, "9:30")
    run_daily(small_market_check, "14:50")
    
    # # 大盘价值
    run_monthly(big_value_adjust, 1, "9:30")
    
    # 大盘
    # run_weekly(simple_roa_adjust, 1, "9:30")
    # run_daily(simple_roa_check, "14:50")
    
    # 国9
    run_weekly(guojiutiao_adjust, 1, "9:30")
    run_daily(guojiutiao_check, "14:50")
  
    # 成长股参数
    g.lastSignal = 'BUY'
    

    
    # 每日剩余资金购买货币ETF
    run_daily(end_trade, "14:55")
    
    
    
    
    
def process_initialize(context):
    print("重启程序")
    g.strategys["小市值"] = Small_Market_Strategy(context, index=0, name="小市值")
    g.strategys["大盘价值"] = Big_Value_Strategy(context, index=1, name="大盘价值")
    g.strategys["大盘策略"] = Simple_ROA_Strategy(context, index=2, name="大盘策略")
    g.strategys["国九"] = GuoJiuTiao_Strategy(context, index=3, name="国九")

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

    # 买入货币ETF
    amount = int(context.portfolio.available_cash / current_data[g.fill_stock].last_price)
    if amount >= 100:
        order(g.fill_stock, amount)


# 卖出货币ETF换现金
def get_cash(context, value):
    if g.fill_stock not in context.portfolio.positions:
        return
    current_data = get_current_data()
    amount = math.ceil(value / current_data[g.fill_stock].last_price / 100) * 100
    position = context.portfolio.positions[g.fill_stock].closeable_amount
    if amount >= 100:
        order(g.fill_stock, -min(amount, position))


# 小市值
def small_market_check(context):
    g.strategys["小市值"].check()

def small_market_adjust(context):
    g.strategys["小市值"].adjust()


# 大盘价值策略
def big_value_adjust(context):
    g.strategys["大盘价值"].adjust()
    

def simple_roa_before_open(context):
    g.strategys["大盘策略"].before_open()

def simple_roa_adjust(context):
    g.strategys["大盘策略"].adjust()


def simple_roa_check(context):
    g.strategys["大盘策略"].check()


def guojiutiao_adjust(context):
    g.strategys["国九"].adjust()

def guojiutiao_check(context):
    g.strategys["国九"].check()

# 策略基类
class Strategy:

    def __init__(self, context, index, name):
        self.context = context
        self.index = index
        self.name = name
        self.stock_sum = 1
        self.hold_list = []
        self.min_volume = 2000

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
            return list(df.code)
        return []

    # 调仓(等权购买target中按顺序排列固定数量的的标的)
    def _adjust(self, target):

        # 获取前stock_sum个标的
        target = target[: min(len(target), self.stock_sum)]

        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())
        portfolio = self.context.portfolio

        # 调仓卖出
        for stock in self.hold_list:
            if stock not in target:
                self.order_target_value_(stock, 0)

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
        if adjustment != 0:
            o = order(security, adjustment)
            if o:
                # 更新持仓数量
                amount = o.amount if o.is_buy else -o.amount
                g.positions[self.index][security] = amount + current_position
                # 如果目标持仓为零，移除该证券
                if target_position == 0:
                    g.positions[self.index].pop(security, None)
                # 更新持有列表
                self.hold_list = list(g.positions[self.index].keys())
                return True
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


# 小市值
class Small_Market_Strategy(Strategy):

    def __init__(self, context, index, name):
        super().__init__(context, index, name)

        self.stock_sum = 5
        # 空仓的月份
        self.pass_months = [1, 4]
        self.num = 1
        
        

    def getStockIndustry(self, stocks):
        industry = get_industry(stocks)
        return pd.Series({stock: info["sw_l1"]["industry_name"] for stock, info in industry.items() if "sw_l1" in info})

    # 获取市场宽度
    def get_market_breadth(self):
        # 指定日期防止未来数据
        yesterday = self.context.previous_date
        # 获取初始列表
        stocks = get_index_stocks("000985.XSHG")
        count = 1
        h = get_price(
            stocks,
            end_date=yesterday,
            frequency="1d",
            fields=["close"],
            count=count + 20,
            panel=False,
        )
        h["date"] = pd.DatetimeIndex(h.time).date
        df_close = h.pivot(index="code", columns="date", values="close").dropna(axis=0)
        # 计算20日均线
        df_ma20 = df_close.rolling(window=20, axis=1).mean().iloc[:, -count:]
        # 计算偏离程度
        df_bias = df_close.iloc[:, -count:] > df_ma20
        df_bias["industry_name"] = self.getStockIndustry(stocks)
        # 计算行业偏离比例
        df_ratio = ((df_bias.groupby("industry_name").sum() * 100.0) / df_bias.groupby("industry_name").count()).round()
        # 获取偏离程度最高的行业
        top_values = df_ratio.loc[:, yesterday].nlargest(self.num)
        I = top_values.index.tolist()
        return I


    # 过滤股票
    def filter(self):
        
        """月度选股：从中小板指筛选小市值股票"""
        # 构建查询：选择中小板指成分股，市值5-300亿，按市值升序排列
        q = query(
            valuation.code,
        ).filter(
            valuation.code.in_(get_index_stocks('399101.XSHE')),
            valuation.market_cap.between(5, 300)  # 市值单位：亿元
        ).order_by(
            valuation.market_cap.asc()  # 小市值优先
        )
        # 获取基本面数据
        fund_df = get_fundamentals(q)
        # 取市值最小的N*20只股票（N为目标持仓数）
        month_scope = fund_df['code'].head(self.stock_sum * 20).tolist()
        
        """从月度股票池筛选最终候选股票"""
        # 先进行基础过滤（剔除ST、新股等）
        filtered_stocks = self.filter_basic_stock(month_scope)
        # 再次查询市值数据
        q = query(
            valuation.code,
            valuation.market_cap
        ).filter(
            valuation.code.in_(filtered_stocks),
            valuation.market_cap.between(5, 300)
        ).order_by(
            valuation.market_cap.asc()  # 仍然按市值排序
        )
        fund_df = get_fundamentals(q)
        # 取市值最小的N*3只作为候选（N为目标持仓数）
        stocks = fund_df['code'].head(self.stock_sum * 3).tolist()
        
        stocks = self.filter_limitup_limitdown_stock(stocks)
        return stocks


    # 调仓
    def adjust(self):
        I = self.get_market_breadth()
        industries = {"银行I", "煤炭I", "采掘I", "钢铁I"}
        if self.is_empty_month() or industries.intersection(I):
            self._adjust([])
        else:
            self._adjust(self.filter())

    # 获取昨日涨停票
    def check(self):
        banner_stocks = self._check()
        for stock in banner_stocks:
            self.order_target_value_(stock, 0)
            

# 大盘价值
class Big_Value_Strategy(Strategy):

    def __init__(self, context, index, name):
        super().__init__(context, index, name)
        self.stock_sum = 5
        self.roe = 10
        self.roa = 6
	    
	    
	    
	    
    #  市场热度判断
    def Market_temperature(self):
        index300 = attribute_history('000300.XSHG', 220, '1d', ('close'), df=False)['close']
        market_height = (mean(index300[-5:]) - min(index300)) / (max(index300) - min(index300))
        if market_height < 0.20:
            g.market_temperature = "cold"
    
        elif market_height > 0.90:
            g.market_temperature = "hot"
    
        elif max(index300[-60:]) / min(index300) > 1.20:
            g.market_temperature = "warm"
    
        return g.market_temperature

        
    # 选股模块
    def select(self):
        g.market_temperature = self.Market_temperature()
        current_data = get_current_data()
        check_date = self.context.previous_date - datetime.timedelta(days=200)
        all_stocks = list(get_all_securities(date=check_date).index)#获取全A市场股票数据
        all_stocks = get_index_stocks("000300.XSHG") #以沪深300成分股味股票池进一步筛选
        all_stocks = self.filter_basic_stock(all_stocks)
        
        if g.market_temperature == "cold":
            q = query(
                valuation.code, 
                indicator.roe,
                indicator.roa
                ).filter(
                valuation.pb_ratio > 0,
                valuation.pb_ratio < 1,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit>2.0,
                indicator.inc_return > 1.5,
                indicator.inc_net_profit_year_on_year > -15,
            	valuation.code.in_(all_stocks)
            	).order_by(
            	(indicator.roa/valuation.pb_ratio).desc()
            ).limit(
            	self.stock_sum *10#*10
            )
        elif g.market_temperature == "warm":
            q = query(
                valuation.code, 
                indicator.roe,
                indicator.roa
                ).filter(
                valuation.pb_ratio > 0,
                valuation.pb_ratio < 1,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit>1.0,
                indicator.inc_return > 2.0,
                indicator.inc_net_profit_year_on_year > 0,
            	valuation.code.in_(all_stocks)
            	).order_by(
            	(indicator.roa/valuation.pb_ratio).desc()
            ).limit(
            	self.stock_sum *10#*10
            )
        elif g.market_temperature == "hot":
            q = query(
                valuation.code, 
                indicator.roe,
                indicator.roa
                ).filter(
    
                valuation.pb_ratio > 3,
                cash_flow.subtotal_operate_cash_inflow > 0,
                indicator.adjusted_profit > 0,
                cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit>0.5,
                indicator.inc_return > 3.0,
                indicator.inc_net_profit_year_on_year > 20,
            	valuation.code.in_(all_stocks)
            	).order_by(
            	indicator.roa.desc()
            ).limit(
            	self.stock_sum *10#*10
            )
  
        
        df = get_fundamentals(q)
        df.index = df['code'].values
        
        
          #按照因子给股票排序（相当于各因子平权）
        #pb_rank= df['pb_ratio'].rank(ascending=True)  # 升序排名（pb越低越好）
        roe_inv_rank= df['roe'].rank(ascending=False)  # 降序排名（roe越高越好）
        roa_inv_rank= df['roa'].rank(ascending=False)  # 降序排名（roa越高越好）
    
        # 应用权重计算综合得分
        df['point'] = ( self.roe * roe_inv_rank + self.roa * roa_inv_rank)
        
        
        #按得分进行排序，取指定数量的股票
        df = df.sort_values(by='point')#[:g.buy_stock_count]
        
        check_out_lists = list(df.code)
        """*****************************************************************************************"""
            
    
        #check_out_lists = list(get_fundamentals(q).code)
        # 动量趋势过滤，剔除太高和太低的
        check_out_lists2 = self.Moment_rank(check_out_lists, 25, -1.0, 10.5)
        # 顺序还是按照动量趋滤前原来的顺序
        check_out_lists = [x for x in check_out_lists if x in check_out_lists2]
        
        # check_out_lists = self.get_stock_industry(check_out_lists)
        
        stocks = check_out_lists[:self.stock_sum]
        
        return list(stocks)    

    def MOM(self,stock,days):
        df = attribute_history(stock, days, '1d', ['close'], df= False)
        y = np.log(df['close'])
        n = len(y)  
        x = np.arange(n)
        weights = np.linspace(1, 2, n)  
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        residuals = y - (slope * x + intercept)
        weighted_residuals = weights * residuals**2
        r_squared = 1 - (np.sum(weighted_residuals) / np.sum(weights * (y - np.mean(y))**2))
        score = annualized_returns * r_squared
        return score
        
    # 过滤动量
    def Moment_rank(self,stock_pool, days,ll, hh):
        score_list = []
        for stock in stock_pool:
            score = self.MOM(stock,days)
            score_list.append(score)
        df = pd.DataFrame(index=stock_pool, data={'score':score_list})
        df = df.sort_values(by='score', ascending=False)  # 降序 
        df = df[(df['score']>ll) & (df['score']<hh)]
        rank_list = list(df.index)    
        return rank_list


    # 调仓
    def adjust(self):
        self._adjust(self.select())
 

       
# 大盘策略
class Simple_ROA_Strategy(Strategy):
    def __init__(self, context, index, name):
        super().__init__(context, index, name)

        # self.stock_sum = 3
        self.stock_sum = 5
        
    def filter(self):
        stocks = get_all_securities("stock", date=self.context.previous_date).index.tolist()
        stocks = self.filter_basic_stock(stocks)
        
        q = query(
            valuation.code, valuation.market_cap, valuation.pe_ratio, income.total_operating_revenue
            ).filter(
            valuation.pb_ratio < 1,
            cash_flow.subtotal_operate_cash_inflow > 1e6,
            indicator.adjusted_profit > 1e6,
            indicator.roa > 0.15,
            indicator.inc_net_profit_year_on_year > 0,
        	valuation.code.in_(stocks)
        	).order_by(
        	indicator.roa.desc())
    
        check_out_lists = list(get_fundamentals(q).code)
        stocks = self.filter_limitup_limitdown_stock(check_out_lists)
        return stocks

    # 调仓
    def adjust(self):
        self._adjust(self.filter())

    # 检查昨日涨停票
    def check(self):
        banner_stocks = self._check()
        if banner_stocks:
            target = [stock for stock in self.filter() if stock not in banner_stocks]
            self._adjust(target)
    


    
           
# 国九条策略
class GuoJiuTiao_Strategy(Strategy):
    def __init__(self, context, index, name):
        super().__init__(context, index, name)
        
        self.stock_sum = 5  # 默认持股数量
        self.min_mv = 10  # 股票最小市值要求(亿元)
        self.max_mv = 10000  # 股票最大市值要求(亿元)
        self.pass_months = [1, 4]  # 空仓的月份
        self.stoploss_limit = 0.09  # 个股止损线
        self.stoploss_market = 0.05  # 市场趋势止损参数
        self.highest = 50  # 股票单价上限设置
        self.filter_audit = True  # 是否筛选审计意见
        self.filter_bonus = True  # 是否筛选红利
        self.expected_bonus = [5]  # 设定引入超额收益的因子的月份
    
    # 判断今天是否在空仓月
    def is_empty_month(self):
        month = self.context.current_dt.month
        return month in self.pass_months
    
    # 动态调整持仓数量
    def adjust_stock_num(self):
        # 原版
        arr_close = history(10, '1d', 'close', '399101.XSHE', df=False)['399101.XSHE']
        # arr_close = history(10, '1d', 'close', '000985.XSHG', df=False)['000985.XSHG']
        bias = 100 * (arr_close[-1] / arr_close.mean() - 1)
        # 根据差值结果返回数字
        result = \
            3 if bias >= 5 else \
                3 if 2 <= bias else \
                    4 if -2 <= bias else \
                        5 if -5 <= bias else \
                            6
        return result
    
    # 筛选审计意见
    def filter_audit_opinion(self, stock_list):
        # 剔除近三年内有不合格(opinion_type_id >2 且不是 6)审计意见的股票
        start_date = datetime.date(self.context.current_dt.year - 3, 1, 1).strftime('%Y-%m-%d')
        end_date = self.context.previous_date.strftime('%Y-%m-%d')
        q = query(finance.STK_AUDIT_OPINION).filter(
            finance.STK_AUDIT_OPINION.code.in_(stock_list),
            finance.STK_AUDIT_OPINION.report_type == 0,  # 0:财务报表审计报告
            finance.STK_AUDIT_OPINION.opinion_type_id > 2,  # 1:无保留,2:无保留带解释性说明
            finance.STK_AUDIT_OPINION.opinion_type_id != 6,  # 6:未经审计，季报
            finance.STK_AUDIT_OPINION.end_date >= start_date,
            finance.STK_AUDIT_OPINION.pub_date <= end_date
        )
        df = finance.run_query(q)
        bad_companies = df['code'].unique().tolist()
        return [s for s in stock_list if s not in bad_companies]
    
    # 筛选红利
    def bonus_filter(self, stock_list):
        year = self.context.previous_date.year
        start_date = datetime.date(year, 1, 1)
        end_date = self.context.previous_date
        
        # 在指定月份开启超额因子
        if end_date.month in self.expected_bonus:
            q = query(
                finance.STK_XR_XD.code, finance.STK_XR_XD.company_name, 
                finance.STK_XR_XD.board_plan_pub_date, finance.STK_XR_XD.bonus_amount_rmb,
                finance.STK_XR_XD.bonus_ratio_rmb
            ).filter(               
                # 董事会预案发生在今年
                finance.STK_XR_XD.board_plan_pub_date > start_date,
                # 董事会预案的发布日期小于等于前一日
                finance.STK_XR_XD.board_plan_pub_date <= end_date,
                # 人民币分红大于0
                finance.STK_XR_XD.bonus_ratio_rmb > 0,
                # 在stock_list中
                finance.STK_XR_XD.code.in_(stock_list)
            )
            expected_bonus_df = finance.run_query(q)
            
            if len(expected_bonus_df) > 0:
                bonus_list = expected_bonus_df['code'].unique().tolist()
                price_df = history(1, unit='1d', field='close', security_list=bonus_list, df=True, skip_paused=False, fq='pre')
                price_df = price_df.T
                price_df.rename(columns={price_df.columns[0]: 'Close_now'}, inplace=True)
                price_df['code'] = price_df.index
                expected_bonus_df = pd.merge(expected_bonus_df, price_df, on=('code'), how='left')
                expected_bonus_df['bonus_ratio'] = (expected_bonus_df['bonus_ratio_rmb']) / expected_bonus_df['Close_now']
                expected_bonus_df = expected_bonus_df.sort_values(by='bonus_ratio', ascending=True)
                bonus_list = expected_bonus_df['code'].unique().tolist()
            else:
                bonus_list = []
        else:
            # 平日开启非年度分红的
            report_date = datetime.date(year-1, 12, 31)
            q = query(
                finance.STK_XR_XD.code, finance.STK_XR_XD.company_name,
                finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb,
                finance.STK_XR_XD.bonus_ratio_rmb
            ).filter(
                # 年度分红
                finance.STK_XR_XD.report_date == report_date,         
                finance.STK_XR_XD.bonus_type == '年度分红',
                # 公布日期小于等于前一天
                finance.STK_XR_XD.board_plan_pub_date <= end_date,
                finance.STK_XR_XD.board_plan_bonusnote == '不分配不转增',
                finance.STK_XR_XD.code.in_(stock_list)
            )
        
            no_year_bonus = finance.run_query(q)
            no_year_bonus_list = no_year_bonus['code'].unique().tolist()
            # 排除今年不分红的股票
            bonus_list = [code for code in stock_list if code not in no_year_bonus_list]
            bonus_list = self.sort_by_market_cap(bonus_list)
           
        if len(bonus_list) < self.stock_sum:
            bonus_list.extend([x for x in stock_list if x not in bonus_list][:self.stock_sum-len(bonus_list)])
        return bonus_list
    
    # 根据市值排序
    def sort_by_market_cap(self, stock_list):
        short_q = query(
            valuation.code,
            valuation.market_cap,  # 总市值
        ).filter(
            valuation.code.in_(stock_list),
            valuation.day == self.context.previous_date,
        ).order_by(valuation.market_cap.asc())
        short_df = get_fundamentals(short_q)
        short_list = short_df['code'].unique().tolist()
        return short_list
    
    # 选股
    def select(self):
        if self.is_empty_month():
            return []
            
        # 动态调整持仓数量
        self.stock_sum = self.adjust_stock_num()
        
        # 获取中小板指数成分股
        # 原版
        initial_list = get_index_stocks('399101.XSHE')
        # initial_list = get_index_stocks('000985.XSHG')
        initial_list = self.filter_basic_stock(initial_list)
        
        # 基本面筛选
        q = query(
            valuation.code,
        ).filter(
            valuation.code.in_(initial_list),
            valuation.market_cap.between(self.min_mv, self.max_mv),  # 总市值 单位：亿元
            income.np_parent_company_owners > 0,   # 归属于母公司所有者的净利润(元)
            income.net_profit > 0,  # 净利润(元)
            income.operating_revenue > 1e8,  # 营业收入 (元)
            indicator.roe > 0,
            indicator.roa > 0,
        ).order_by(valuation.market_cap.asc()).limit(self.stock_sum * 3)
        
        df = get_fundamentals(q)
        stock_list = df['code'].tolist()
        
        # 筛选审计意见
        if self.filter_audit:
            stock_list = self.filter_audit_opinion(stock_list)
        
        # 筛选红利
        if self.filter_bonus: 
            stock_list = self.bonus_filter(stock_list)
        
        # 过滤价格高于设定值的股票
        if stock_list:
            last_prices = history(1, unit='1d', field='close', security_list=stock_list)
            stock_list = [stock for stock in stock_list if last_prices[stock][-1] <= self.highest]
        
        return stock_list[:self.stock_sum]
    
    # 止损检查
    def check_stop_loss(self):
        current_positions = self.context.portfolio.positions
        stop_loss_list = []
        
        # 个股止损
        for stock in list(g.positions[self.index].keys()):
            if stock not in current_positions:
                continue
                
            price = current_positions[stock].price
            avg_cost = current_positions[stock].avg_cost
            
            # 个股盈利止盈
            if price >= avg_cost * 2:
                self.order_target_value_(stock, 0)
                
            # 个股止损
            elif price < avg_cost * (1 - self.stoploss_limit):
                self.order_target_value_(stock, 0)
                stop_loss_list.append(stock)
        
        # 市场大跌止损
        stock_df = get_price(
            # 原版
            security=get_index_stocks('399101.XSHE'),
            # security=get_index_stocks('000985.XSHG'),
            end_date=self.context.previous_date, 
            frequency='daily',
            fields=['close', 'open'], 
            count=1, 
            panel=False
        )
        
        # 计算成分股平均涨跌，即指数涨跌幅
        down_ratio = (1 - stock_df['close'] / stock_df['open']).mean()
        
        # 市场大跌止损
        if down_ratio >= self.stoploss_market:
            for stock in list(g.positions[self.index].keys()):
                if stock in current_positions:
                    self.order_target_value_(stock, 0)
                    stop_loss_list.append(stock)
        
        return stop_loss_list
    
    # 调仓
    def adjust(self):
        target_list = self.select()
        self._adjust(target_list)
    
    # 检查
    def check(self):
        # 检查止损
        self.check_stop_loss()
        
        # 检查昨日涨停股
        banner_stocks = self._check()
        if banner_stocks:
            target = [stock for stock in self.select() if stock not in banner_stocks]
            self._adjust(target)
        else:
            for stock in banner_stocks:
                self.order_target_value_(stock, 0)

    # 调仓
    def adjust(self):
        self._adjust(self.select())


     
