# Clone from JoinQuant
# postId: c717b57de1483eb4cdc3a96264811f79
# backtestId: 37b85c3c8aafaf9feb0f5a5a579f04bd
# title: 失败，请大神知道

# 克隆自聚宽文章：https://www.joinquant.com/post/31819
# 标题：
# 作者：张坤

# 导入函数库
from jqdata import *
import talib
import pandas as pd
import numpy as np
import pprint
import os
import random
import time
import tensorflow as tf
import tensorflow.contrib.slim as slim

from absl import app, flags, logging


random.seed(time.time())#算法

flags = tf.app.flags
flags.DEFINE_integer("stock_count", 10, "Stock count [100]")  #zk
flags.DEFINE_integer("input_size", 1, "Input size [1]")
flags.DEFINE_integer("num_steps", 30, "Num of steps [30]")
flags.DEFINE_integer("num_layers", 1, "Num of layer [1]")
flags.DEFINE_integer("lstm_size", 128, "Size of one LSTM cell [128]")
flags.DEFINE_integer("batch_size", 64, "The size of batch images [64]")
flags.DEFINE_float("keep_prob", 0.8, "Keep probability of dropout layer. [0.8]")
flags.DEFINE_float("init_learning_rate", 0.001, "Initial learning rate at early stage. [0.001]")
flags.DEFINE_float("learning_rate_decay", 0.99, "Decay rate of learning rate. [0.99]")
flags.DEFINE_integer("init_epoch", 5, "Num. of epoches considered as early stage. [5]")
flags.DEFINE_integer("max_epoch", 50, "Total training epoches. [50]")
flags.DEFINE_integer("embed_size", None, "If provided, use embedding vector of this size. [None]")
flags.DEFINE_string("stock_symbol", None, "Target stock symbol [None]")
flags.DEFINE_integer("sample_size", 4, "Number of stocks to plot during training. [4]")
flags.DEFINE_boolean("train", False, "True for training, False for testing [False]")

FLAGS = flags.FLAGS
pp = pprint.PrettyPrinter()


DATA_DIR = "data"
LOG_DIR = "logs"
MODEL_DIR = "models"

#获取原油全部数据
g.df=finance.run_query(query(finance.FUT_GLOBAL_DAILY).filter(finance.FUT_GLOBAL_DAILY.code=='CL'))
print(type(g.df))
print(g.df)
g.test=g.df[0:1000] 



if not os.path.exists("logs"):
    os.mkdir("logs")


def show_all_variables():
    model_vars = tf.trainable_variables()
    slim.model_analyzer.analyze_vars(model_vars, print_info=True)

## 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    # 输出内容到日志 log.info()
    # log.info('初始函数开始运行且全局只运行一次')
    
    DEFAULT_CONFIG = RNNConfig()
    print ("Default configuration:", DEFAULT_CONFIG.to_dict())
    
    main_init()                 #cnn  20210401  
    
    
    # 设定全局函数
    # 数据获取周期
    context.LONGPERIOD = 25
    
    # 交易日数统计
    context.day=0
    
    # 初始资金2百万
    context.ori_cash=2000000
   

    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.0001, close_commission=0.0001,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)

    # 设置期货交易的滑点
    set_slippage(StepRelatedSlippage(2))
    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF8888.CCFX'或'IH1602.CCFX'是一样的）
    # 注意：before_open/open/close/after_close等相对时间不可用于有夜盘的交易品种，有夜盘的交易品种请指定绝对时间（如9：30）
    
    
    
    # # 指定每天收盘前10分钟运行
    # run_weekly(daily, "close - 10m") # not working 

    # # 指定每天收盘后执行
    #run_daily(daily, 'after_close')

    # # 指定在每天的10:00运行
    # run_daily(daily, '10:00')

    # 参照股指期货的时间每分钟运行一次, 必须选择分钟回测, 否则每天执行
    # run_daily(daily, 'every_bar', reference_security='IF1512.CCFX'
    
    # 开盘前运行 
    run_daily( before_market_open, time='8:30', reference_security='FG8888.XZCE')
    # 开盘时运行
    run_daily( market_open, time='9:30', reference_security='FG8888.XZCE')
    
    
    
    
    '''
    f = open('log002.txt','w')
    print("argretaeyt5yt4yy", file=f)
    f.close()
    
    write_file("log003.txt", str("awfefwg3g4hgg"))
    
    secCode = '000985.XSHG'
    sample = get_index_stocks(secCode)
    #print(len(sample))
    #print(sample)
    feasible_stocks = sample
    q_Factor = get_q_Factor(feasible_stocks)
    #print(q_Factor)
    write_file("test20389.txt", str(q_Factor))'''

# 这个函数也是必须定义的，每个交易时间间隔都要执行一次
def handle_data(context, data):

    #注意公共变量要在调用函数之前定义
    g.stocks = getStocks(context)
    # 设置所有可能要买的股票集
    set_universe(g.stocks)
    

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    # log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    ## 获取要操作的股票(g.为全局变量)
    # 获取当月指数期货合约
    g.CL = get_dominant_future('CL')
    g.AP = get_dominant_future('AP')
    g.BU = get_dominant_future('BU')
    g.FG = get_dominant_future('FG')
    g.RB = get_dominant_future('RB')
    g.Y = get_dominant_future('Y')
    g.ZC = get_dominant_future('ZC')
    g.AG = get_dominant_future('AG')
    g.P = get_dominant_future('P')
    g.TA = get_dominant_future('TA')
   
    #   设置交易天数时钟，持续统计交易天数
    context.day=context.day+1
    
    # 设置目标年收益率，后续单个期货合约的保证金上限需使用该数据
    context.inc=0.2
    
    
## 开盘时运行函数
def market_open(context):
    # log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    
    # 2018-2021测试
    future_list={g.CL}
   
    
    # 获取合约数量
    context.num=len(future_list)
    
    # future_list={g.CF}
    # 主力合约切换以后不主动平仓，如主动平仓，使用下面的代码
    # 通过以下，发现现象，贴近合约到期月份，不主动平仓，收益是增加的。这一条是否高可能性需要进一步确认。
    # for future in context.portfolio.short_positions.keys():
    #     if future not in future_list:
    #         order_target_value(future, 0, side='short')
    # for future in context.portfolio.long_positions.keys():
    #     if future not in future_list:
    #         order_target_value(future, 0, side='long')
    # 主力合约切换以后不主动平仓，如主动平仓，使用上面的代码
    # 通过以下，发现现象，贴近合约到期月份，不主动平仓，收益是增加的。这一条是否高可能性需要进一步确认。
   
    
    for future in future_list:
        deal(context,future)
   
    
def deal(context,future_code):
    # 当月合约
    current_f = future_code
    
    # 获取当前合约历史数据
    #df=attribute_history(current_f,context.LONGPERIOD)
    #df=finance.run_query(query(finance.FUT_GLOBAL_DAILY).filter(finance.FUT_GLOBAL_DAILY.day==date).limit(n))   
    df=g.df
    
    print(df.iloc[0])
    
     
    # 设定数据回溯区间
    num=12
    
    #算法
    
    
    
    
    
    
    
    # 计算成交量*成交价格
    # 估算统计成交价格=成交量*成交价格/成交总量
    df['trade']=0.25*(df['open']+df['close']+df['high']+df['low'])*df['volume']
    
    
    # 计算成交价格，当前日，前一日，前两日，前三日，
    price_0=df['trade'][context.LONGPERIOD-num:context.LONGPERIOD].sum()/df['volume'][context.LONGPERIOD-num:context.LONGPERIOD].sum()
    price_1=df['trade'][context.LONGPERIOD-1-num:context.LONGPERIOD-1].sum()/df['volume'][context.LONGPERIOD-1-num:context.LONGPERIOD-1].sum()
    price_2=df['trade'][context.LONGPERIOD-2-num:context.LONGPERIOD-2].sum()/df['volume'][context.LONGPERIOD-2-num:context.LONGPERIOD-2].sum()
    price_3=df['trade'][context.LONGPERIOD-3-num:context.LONGPERIOD-3].sum()/df['volume'][context.LONGPERIOD-3-num:context.LONGPERIOD-3].sum()
    print(price_0);print('\n')
    print(price_1);print('\n')
    print(price_2);print('\n')
    print(price_3);print('\n')
    
    # 查看空单仓位情况
    if  current_f in context.portfolio.short_positions.keys():
        cur_short =1
    else:
        cur_short =0
        
    # 查看多单仓位情况    
    if  current_f in context.portfolio.long_positions.keys():
        cur_long =1
    else:
        cur_long =0
    
    # 计算总市值以及每个品种的资金用量
    value_total = context.portfolio.total_value
    
    
    # 计算单个合约的保证金使用量，为防止回撤过大，每200个交易日内的保证金使用量不变
    value=(0.84/context.num)*context.ori_cash*(1+context.inc*int(context.day/200))
    
    
    # 根据成交价格的变动关系，判断趋势，并下单
    if price_0>price_1 and price_1>price_2 and price_2>price_3 and price_0-price_1>price_1-price_2 and price_1-price_2>price_2-price_3 and cur_long==0:
    # 开多单
        order_target_value(current_f, value, side='long')
    # 清仓
    if (price_0<price_1 or price_1<price_2 or price_2<price_3) and cur_long > 0 :
        order_target_value(current_f, 0, side='long')
     # 开空单
    if price_0<price_1 and price_1<price_2 and price_2<price_3 and price_0-price_1<price_1-price_2 and price_1-price_2<price_2-price_3 and cur_short==0:
        order_target_value(current_f, value, side='short')
    # 清仓空单
    if (price_0>price_1 or price_1>price_2 or price_2>price_3) and cur_short >0 :
        order_target_value(current_f, 0, side='short')



def get_q_Factor(feasible_stocks):
    q = query(valuation.code, 
          valuation.market_cap,#市值
          valuation.circulating_market_cap,
          balance.total_assets - balance.total_liability,#净资产
          balance.total_assets / balance.total_liability, 
          indicator.net_profit_to_total_revenue, #净利润/营业总收入
          indicator.inc_revenue_year_on_year,  #营业收入增长率（同比）
          balance.development_expenditure, #RD
          valuation.pe_ratio, #市盈率（TTM）
          valuation.pb_ratio, #市净率（TTM）
          indicator.inc_net_profit_year_on_year,#净利润增长率（同比）
          balance.dividend_payable,
          indicator.roe,
          indicator.roa,
          income.operating_profit / income.total_profit, #OPTP
          indicator.gross_profit_margin, #销售毛利率GPM
          balance.fixed_assets / balance.total_assets, #FACR
          valuation.pcf_ratio, #CFP
          valuation.ps_ratio #PS
        ).filter(
            valuation.code.in_(feasible_stocks)
        )
    return q


# ########################## 获取期货合约信息，请保留 #################################
# # 获取金融期货合约到期日
# def get_CCFX_end_date(future_code):
#     # 获取金融期货合约到期日
#     return get_security_info(future_code).end_date


# ########################## 自动移仓换月函数 #################################
# def position_auto_switch(context,pindex=0,switch_func=None, callback=None):
#     """
#     期货自动移仓换月。默认使用市价单进行开平仓。
#     :param context: 上下文对象
#     :param pindex: 子仓对象
#     :param switch_func: 用户自定义的移仓换月函数.
#         函数原型必须满足：func(context, pindex, previous_dominant_future_position, current_dominant_future_symbol)
#     :param callback: 移仓换月完成后的回调函数。
#         函数原型必须满足：func(context, pindex, previous_dominant_future_position, current_dominant_future_symbol)
#     :return: 发生移仓换月的标的。类型为列表。
#     """
#     import re
#     subportfolio = context.subportfolios[pindex]
#     symbols = set(subportfolio.long_positions.keys()) | set(subportfolio.short_positions.keys())
#     switch_result = []
#     for symbol in symbols:
#         match = re.match(r"(?P<underlying_symbol>[A-Z]{1,})", symbol)
#         if not match:
#             raise ValueError("未知期货标的：{}".format(symbol))
#         else:
#             dominant = get_dominant_future(match.groupdict()["underlying_symbol"])
#             cur = get_current_data()
#             symbol_last_price = cur[symbol].last_price
#             dominant_last_price = cur[dominant].last_price
#             if dominant > symbol:
#                 for p in (subportfolio.long_positions.get(symbol, None), subportfolio.short_positions.get(symbol, None)):
#                     if p is None:
#                         continue
#                     if switch_func is not None:
#                         switch_func(context, pindex, p, dominant)
#                     else:
#                         amount = p.total_amount
#                         # 跌停不能开空和平多，涨停不能开多和平空。
#                         if p.side == "long":
#                             symbol_low_limit = cur[symbol].low_limit
#                             dominant_high_limit = cur[dominant].high_limit
#                             if symbol_last_price <= symbol_low_limit:
#                                 log.warning("标的{}跌停，无法平仓。移仓换月取消。".format(symbol))
#                                 continue
#                             elif dominant_last_price >= dominant_high_limit:
#                                 log.warning("标的{}涨停，无法开仓。移仓换月取消。".format(symbol))
#                                 continue
#                             else:
#                                 log.info("进行移仓换月：({0},long) -> ({1},long)".format(symbol, dominant))
#                                 order_target(symbol,0,side='long')
#                                 order_target(dominant,amount,side='long')
#                                 switch_result.append({"before": symbol, "after":dominant, "side": "long"})
#                             if callback:
#                                 callback(context, pindex, p, dominant)
#                         if p.side == "short":
#                             symbol_high_limit = cur[symbol].high_limit
#                             dominant_low_limit = cur[dominant].low_limit
#                             if symbol_last_price >= symbol_high_limit:
#                                 log.warning("标的{}涨停，无法平仓。移仓换月取消。".format(symbol))
#                                 continue
#                             elif dominant_last_price <= dominant_low_limit:
#                                 log.warning("标的{}跌停，无法开仓。移仓换月取消。".format(symbol))
#                                 continue
#                             else:
#                                 log.info("进行移仓换月：({0},short) -> ({1},short)".format(symbol, dominant))
#                                 order_target(symbol,0,side='short')
#                                 order_target(dominant,amount,side='short')
#                                 switch_result.append({"before": symbol, "after": dominant, "side": "short"})
#                                 if callback:
#                                     callback(context, pindex, p, dominant)
#     return switch_result



#神经网络
class LstmRNN(object):
    def __init__(self, sess, stock_count=10,  #
                 lstm_size=128,
                 num_layers=1,
                 num_steps=30,
                 input_size=1,
                 embed_size=None,
                 logs_dir="logs",
                 plots_dir="images"):
        """
        Construct a RNN model using LSTM cell.

        Args:
            sess:
            stock_count (int): num. of stocks we are going to train with.
            lstm_size (int)
            num_layers (int): num. of LSTM cell layers.
            num_steps (int)
            input_size (int)
            keep_prob (int): (1.0 - dropout rate.) for a LSTM cell.
            embed_size (int): length of embedding vector, only used when stock_count > 1.
            checkpoint_dir (str)
        """
        self.sess = sess
        self.stock_count = stock_count

        self.lstm_size = lstm_size
        self.num_layers = num_layers
        self.num_steps = num_steps
        self.input_size = input_size

        self.use_embed = (embed_size is not None) and (embed_size > 0)
        self.embed_size = embed_size or -1

        self.logs_dir = logs_dir
        self.plots_dir = plots_dir

        self.build_graph()

    def build_graph(self):
        """
        The model asks for five things to be trained:
        - learning_rate
        - keep_prob: 1 - dropout rate
        - symbols: a list of stock symbols associated with each sample
        - input: training data X
        - targets: training label y
        """
        # inputs.shape = (number of examples, number of input, dimension of each input).
        self.learning_rate = tf.placeholder(tf.float32, None, name="learning_rate")
        self.keep_prob = tf.placeholder(tf.float32, None, name="keep_prob")

        # Stock symbols are mapped to integers.
        self.symbols = tf.placeholder(tf.int32, [None, 1], name='stock_labels')

        self.inputs = tf.placeholder(tf.float32, [None, self.num_steps, self.input_size], name="inputs")
        self.targets = tf.placeholder(tf.float32, [None, self.input_size], name="targets")

        def _create_one_cell():
            lstm_cell = tf.contrib.rnn.LSTMCell(self.lstm_size, state_is_tuple=True)
            lstm_cell = tf.contrib.rnn.DropoutWrapper(lstm_cell, output_keep_prob=self.keep_prob)
            return lstm_cell

        cell = tf.contrib.rnn.MultiRNNCell(
            [_create_one_cell() for _ in range(self.num_layers)],
            state_is_tuple=True
        ) if self.num_layers > 1 else _create_one_cell()

        if self.embed_size > 0 and self.stock_count > 1:
            self.embed_matrix = tf.Variable(
                tf.random_uniform([self.stock_count, self.embed_size], -1.0, 1.0),
                name="embed_matrix"
            )
            
            # stock_label_embeds.shape = (batch_size, embedding_size)
            stacked_symbols = tf.tile(self.symbols, [1, self.num_steps], name='stacked_stock_labels')
            stacked_embeds = tf.nn.embedding_lookup(self.embed_matrix, stacked_symbols)

            # After concat, inputs.shape = (batch_size, num_steps, input_size + embed_size)
            self.inputs_with_embed = tf.concat([self.inputs, stacked_embeds], axis=2, name="inputs_with_embed")
            self.embed_matrix_summ = tf.summary.histogram("embed_matrix", self.embed_matrix)

        else:
            self.inputs_with_embed = tf.identity(self.inputs)
            self.embed_matrix_summ = None

        print ("inputs.shape:", self.inputs.shape)
        print ("inputs_with_embed.shape:", self.inputs_with_embed.shape)

        # Run dynamic RNN
        val, state_ = tf.nn.dynamic_rnn(cell, self.inputs_with_embed, dtype=tf.float32, scope="dynamic_rnn")

        # Before transpose, val.get_shape() = (batch_size, num_steps, lstm_size)
        # After transpose, val.get_shape() = (num_steps, batch_size, lstm_size)
        val = tf.transpose(val, [1, 0, 2])

        last = tf.gather(val, int(val.get_shape()[0]) - 1, name="lstm_state")
        ws = tf.Variable(tf.truncated_normal([self.lstm_size, self.input_size]), name="w")
        bias = tf.Variable(tf.constant(0.1, shape=[self.input_size]), name="b")
        self.pred = tf.matmul(last, ws) + bias

        self.last_sum = tf.summary.histogram("lstm_state", last)
        self.w_sum = tf.summary.histogram("w", ws)
        self.b_sum = tf.summary.histogram("b", bias)
        self.pred_summ = tf.summary.histogram("pred", self.pred)

        # self.loss = -tf.reduce_sum(targets * tf.log(tf.clip_by_value(prediction, 1e-10, 1.0)))
        self.loss = tf.reduce_mean(tf.square(self.pred - self.targets), name="loss_mse_train")
        self.optim = tf.train.RMSPropOptimizer(self.learning_rate).minimize(self.loss, name="rmsprop_optim")

        # Separated from train loss.
        self.loss_test = tf.reduce_mean(tf.square(self.pred - self.targets), name="loss_mse_test")

        self.loss_sum = tf.summary.scalar("loss_mse_train", self.loss)
        self.loss_test_sum = tf.summary.scalar("loss_mse_test", self.loss_test)
        self.learning_rate_sum = tf.summary.scalar("learning_rate", self.learning_rate)

        self.t_vars = tf.trainable_variables()
        self.saver = tf.train.Saver()

    def train(self, dataset_list, config):
        """
        Args:
            dataset_list (<StockDataSet>)
            config (tf.app.flags.FLAGS)
        """
        assert len(dataset_list) > 0
        self.merged_sum = tf.summary.merge_all()

        # Set up the logs folder
        #zk
        #self.writer = tf.summary.FileWriter(os.path.join("./logs", self.model_name))
        #self.writer.add_graph(self.sess.graph)

        if self.use_embed:
            # Set up embedding visualization
            # Format: tensorflow/tensorboard/plugins/projector/projector_config.proto
            projector_config = projector.ProjectorConfig()

            # You can add multiple embeddings. Here we add only one.
            added_embed = projector_config.embeddings.add()
            added_embed.tensor_name = self.embed_matrix.name
            # Link this tensor to its metadata file (e.g. labels).
            #zk
            shutil.copyfile(os.path.join(self.logs_dir, "metadata.tsv"),
                            os.path.join(self.model_logs_dir, "metadata.tsv"))
            
            added_embed.metadata_path = "metadata.tsv"

            # The next line writes a projector_config.pbtxt in the LOG_DIR. TensorBoard will
            # read this file during startup.
            projector.visualize_embeddings(self.writer, projector_config)

        tf.global_variables_initializer().run()

        # Merged test data of different stocks.
        merged_test_X = []
        merged_test_y = []
        merged_test_labels = []

        for label_, d_ in enumerate(dataset_list):
            merged_test_X += list(d_.test_X)
            merged_test_y += list(d_.test_y)
            merged_test_labels += [[label_]] * len(d_.test_X)

        merged_test_X = np.array(merged_test_X)
        merged_test_y = np.array(merged_test_y)
        merged_test_labels = np.array(merged_test_labels)

        print ("len(merged_test_X) =", len(merged_test_X))
        print ("len(merged_test_y) =", len(merged_test_y))
        print ("len(merged_test_labels) =", len(merged_test_labels))

        test_data_feed = {
            self.learning_rate: 0.0,
            self.keep_prob: 1.0,
            self.inputs: merged_test_X,
            self.targets: merged_test_y,
            self.symbols: merged_test_labels,
        }

        global_step = 0

        num_batches = sum(len(d_.train_X) for d_ in dataset_list) // config.batch_size
        random.seed(time.time())

        # Select samples for plotting.
        sample_labels = range(min(config.sample_size, len(dataset_list)))
        sample_indices = {}
        for l in sample_labels:
            sym = dataset_list[l].stock_sym
            target_indices = np.array([
                i for i, sym_label in enumerate(merged_test_labels)
                if sym_label[0] == l])
            sample_indices[sym] = target_indices
        print (sample_indices)

        print ("Start training for stocks:", [d.stock_sym for d in dataset_list])
        for epoch in xrange(config.max_epoch):
            epoch_step = 0
            learning_rate = config.init_learning_rate * (
                config.learning_rate_decay ** max(float(epoch + 1 - config.init_epoch), 0.0)
            )

            for label_, d_ in enumerate(dataset_list):
                for batch_X, batch_y in d_.generate_one_epoch(config.batch_size):
                    global_step += 1
                    epoch_step += 1
                    batch_labels = np.array([[label_]] * len(batch_X))
                    train_data_feed = {
                        self.learning_rate: learning_rate,
                        self.keep_prob: config.keep_prob,
                        self.inputs: batch_X,
                        self.targets: batch_y,
                        self.symbols: batch_labels,
                    }
                    train_loss, _, train_merged_sum = self.sess.run(
                        [self.loss, self.optim, self.merged_sum], train_data_feed)
                    self.writer.add_summary(train_merged_sum, global_step=global_step)

                    if np.mod(global_step, len(dataset_list) * 200 / config.input_size) == 1:
                        test_loss, test_pred = self.sess.run([self.loss_test, self.pred], test_data_feed)

                        print ("Step:%d [Epoch:%d] [Learning rate: %.6f] train_loss:%.6f test_loss:%.6f" % (
                            global_step, epoch, learning_rate, train_loss, test_loss))

                        # Plot samples
                        for sample_sym, indices in sample_indices.iteritems():
                            image_path = os.path.join(self.model_plots_dir, "{}_epoch{:02d}_step{:04d}.png".format(
                                sample_sym, epoch, epoch_step))
                            sample_preds = test_pred[indices]
                            sample_truth = merged_test_y[indices]
                            self.plot_samples(sample_preds, sample_truth, image_path, stock_sym=sample_sym)

                        self.save(global_step)

        final_pred, final_loss = self.sess.run([self.pred, self.loss], test_data_feed)

        # Save the final model
        self.save(global_step)
        return final_pred

    @property
    def model_name(self):
        name = "stock_rnn_lstm%d_step%d_input%d" % (
            self.lstm_size, self.num_steps, self.input_size)

        if self.embed_size > 0:
            name += "_embed%d" % self.embed_size

        return name


    @property
    def model_logs_dir(self):
        model_logs_dir = os.path.join(self.logs_dir, self.model_name)
        if not os.path.exists(model_logs_dir):
            os.makedirs(model_logs_dir)
        return model_logs_dir

    @property
    def model_plots_dir(self):
        model_plots_dir = os.path.join(self.plots_dir, self.model_name)
        if not os.path.exists(model_plots_dir):
            os.makedirs(model_plots_dir)
        return model_plots_dir

    def save(self, step):
        model_name = self.model_name + ".model"
        self.saver.save(
            self.sess,
            os.path.join(self.model_logs_dir, model_name),
            global_step=step
        )

    def load(self):
        print(" [*] Reading checkpoints...")
        ckpt = tf.train.get_checkpoint_state(self.model_logs_dir)
        if ckpt and ckpt.model_checkpoint_path:
            ckpt_name = os.path.basename(ckpt.model_checkpoint_path)
            self.saver.restore(self.sess, os.path.join(self.model_logs_dir, ckpt_name))
            counter = int(next(re.finditer("(\d+)(?!.*\d)", ckpt_name)).group(0))
            print(" [*] Success to read {}".format(ckpt_name))
            return True, counter

        else:
            print(" [*] Failed to find a checkpoint")
            return False, 0
            
    def plot_samples(self, preds, targets, figname, stock_sym=None, multiplier=5):
        def _flatten(seq):
            return np.array([x for y in seq for x in y])

        truths = _flatten(targets)[-200:]
        preds = (_flatten(preds) * multiplier)[-200:]
        days = range(len(truths))[-200:]

        plt.figure(figsize=(12, 6))
        plt.plot(days, truths, label='truth')
        plt.plot(days, preds, label='pred')
        plt.legend(loc='upper left', frameon=False)
        plt.xlabel("day")
        plt.ylabel("normalized price")
        plt.ylim((min(truths), max(truths)))
        plt.grid(ls='--')

        if stock_sym:
            plt.title(stock_sym + " | Last %d days in test" % len(truths))

        plt.savefig(figname, format='png', bbox_inches='tight', transparent=True)
        plt.close()
        
        
        
        
#数据
class StockDataSet(object):
    def __init__(self,
                 stock_sym,
                 input_size=1,
                 num_steps=30,
                 test_ratio=0.1,
                 normalized=True,
                 close_price_only=True):
        self.stock_sym = stock_sym
        self.input_size = input_size
        self.num_steps = num_steps
        self.test_ratio = test_ratio
        self.close_price_only = close_price_only
        self.normalized = normalized

        # Read csv file
        raw_df = g.df    #zk

        # Merge into one sequence
        if close_price_only:
            self.raw_seq = raw_df['close'].tolist()
        else:
            self.raw_seq = [price for tup in raw_df[['open', 'close']].values for price in tup]

        self.raw_seq = np.array(self.raw_seq)
        self.train_X, self.train_y, self.test_X, self.test_y = self._prepare_data(self.raw_seq)

    def info(self):
        return "StockDataSet [%s] train: %d test: %d" % (
            self.stock_sym, len(self.train_X), len(self.test_y))

    def _prepare_data(self, seq):
        # split into items of input_size
        seq = [np.array(seq[i * self.input_size: (i + 1) * self.input_size])
               for i in range(len(seq) // self.input_size)]

        if self.normalized:
            seq = [seq[0] / seq[0][0] - 1.0] + [
                curr / seq[i][-1] - 1.0 for i, curr in enumerate(seq[1:])]

        # split into groups of num_steps
        X = np.array([seq[i: i + self.num_steps] for i in range(len(seq) - self.num_steps)])
        y = np.array([seq[i + self.num_steps] for i in range(len(seq) - self.num_steps)])

        train_size = int(len(X) * (1.0 - self.test_ratio))
        train_X, test_X = X[:train_size], X[train_size:]
        train_y, test_y = y[:train_size], y[train_size:]
        return train_X, train_y, test_X, test_y

    def generate_one_epoch(self, batch_size):
        num_batches = int(len(self.train_X)) // batch_size
        if batch_size * num_batches < len(self.train_X):
            num_batches += 1

        batch_indices = range(num_batches)
        random.shuffle(batch_indices)
        for j in batch_indices:
            batch_X = self.train_X[j * batch_size: (j + 1) * batch_size]
            batch_y = self.train_y[j * batch_size: (j + 1) * batch_size]
            assert set(map(len, batch_X)) == {self.num_steps}
            yield batch_X, batch_y











def load_sp500(input_size, num_steps, k=None, target_symbol=None, test_ratio=0.05):
    
    #zk
    '''
    if target_symbol is not None:
        return [
            StockDataSet(
                target_symbol,
                input_size=input_size,
                num_steps=num_steps,
                test_ratio=test_ratio)
        ]

    # Load metadata of s & p 500 stocks
    info = pd.read_csv("data/constituents-financials.csv")
    info = info.rename(columns={col: col.lower().replace(' ', '_') for col in info.columns})
    info['file_exists'] = info['symbol'].map(lambda x: os.path.exists("data/{}.csv".format(x)))
    print (info['file_exists'].value_counts().to_dict())

    info = info[info['file_exists'] == True].reset_index(drop=True)
    info = info.sort('market_cap', ascending=False).reset_index(drop=True)

    if k is not None:
        info = info.head(k)

    print ("Head of S&P 500 info:\n", info.head())

    # Generate embedding meta file
    info[['symbol', 'sector']].to_csv(os.path.join("logs/metadata.tsv"), sep='\t', index=False)
    
    return [
        StockDataSet(row['symbol'],
                     input_size=input_size,
                     num_steps=num_steps,
                     test_ratio=0.05)
        for _, row in info.iterrows()]
    '''
def prediction_by_trained_graph(graph_name, max_epoch, test_X, test_y):
    test_prediction = None
    test_loss = None

    with tf.Session() as sess:
        # Load meta graph
        graph_meta_path = os.path.join(
            MODEL_DIR, graph_name,
            'stock_rnn_model_{0}.ckpt-{1}.meta'.format(graph_name, max_epoch-1))
        checkpoint_path = os.path.join(MODEL_DIR, graph_name)

        saver = tf.train.import_meta_graph(graph_meta_path)
        saver.restore(sess, tf.train.latest_checkpoint(checkpoint_path))

        graph = tf.get_default_graph()

        test_feed_dict = {
            graph.get_tensor_by_name('inputs:0'): test_X,
            graph.get_tensor_by_name('targets:0'): test_y,
            graph.get_tensor_by_name('learning_rate:0'): 0.0
        }

        prediction = graph.get_tensor_by_name('output_layer/add:0')
        loss = graph.get_tensor_by_name('train/loss_mse:0')
        test_prediction, test_loss = sess.run([prediction, loss], test_feed_dict)

    return test_prediction, test_loss
    
class RNNConfig():
    input_size = 1
    num_steps = 30
    lstm_size = 128
    num_layers = 1
    keep_prob = 0.8

    batch_size = 64
    init_learning_rate = 0.001
    learning_rate_decay = 0.99
    init_epoch = 5
    max_epoch = 50

    def to_dict(self):
        dct = self.__class__.__dict__
        return {k: v for k, v in dct.items() if not k.startswith('__') and not callable(v)}

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return str(self.to_dict())
        
        
def build_lstm_graph_with_config(config=None):
    tf.reset_default_graph()
    lstm_graph = tf.Graph()

    if config is None:
        config = DEFAULT_CONFIG

    with lstm_graph.as_default():
        """
        The model asks for three things:
        - input: training data X
        - targets: training label y
        - learning_rate:
        """
        learning_rate = tf.placeholder(tf.float32, None, name="learning_rate")

        # Number of examples, number of input, dimension of each input
        inputs = tf.placeholder(tf.float32, [None, config.num_steps, config.input_size], name="inputs")
        targets = tf.placeholder(tf.float32, [None, config.input_size], name="targets")

        def _create_one_cell():
            lstm_cell = tf.contrib.rnn.LSTMCell(config.lstm_size, state_is_tuple=True)
            if config.keep_prob < 1.0:
                lstm_cell = tf.contrib.rnn.DropoutWrapper(lstm_cell, output_keep_prob=config.keep_prob)
            return lstm_cell

        cell = tf.contrib.rnn.MultiRNNCell(
            [_create_one_cell() for _ in range(config.num_layers)],
            state_is_tuple=True
        ) if config.num_layers > 1 else _create_one_cell()

        val, _ = tf.nn.dynamic_rnn(cell, inputs, dtype=tf.float32, scope="lilian_rnn")

        # Before transpose, val.get_shape() = (batch_size, num_steps, lstm_size)
        # After transpose, val.get_shape() = (num_steps, batch_size, lstm_size)
        val = tf.transpose(val, [1, 0, 2])

        with tf.name_scope("output_layer"):
            # last.get_shape() = (batch_size, lstm_size)
            last = tf.gather(val, int(val.get_shape()[0]) - 1, name="last_lstm_output")

            weight = tf.Variable(tf.truncated_normal([config.lstm_size, config.input_size]), name="lilian_weights")
            bias = tf.Variable(tf.constant(0.1, shape=[config.input_size]), name="lilian_biases")
            prediction = tf.matmul(last, weight) + bias

            tf.summary.histogram("last_lstm_output", last)
            tf.summary.histogram("weights", weight)
            tf.summary.histogram("biases", bias)

        with tf.name_scope("train"):
            # loss = -tf.reduce_sum(targets * tf.log(tf.clip_by_value(prediction, 1e-10, 1.0)))
            loss = tf.reduce_mean(tf.square(prediction - targets), name="loss_mse")
            optimizer = tf.train.AdamOptimizer(learning_rate)
            minimize = optimizer.minimize(loss, name="loss_mse_adam_minimize")
            tf.summary.scalar("loss_mse", loss)

        # Operators to use after restoring the model
        for op in [prediction, loss]:
            tf.add_to_collection('ops_to_restore', op)

    return lstm_graph
        
        
        
        

def main_init():
    
    #pp.pprint(flags.FLAGS.__flags)

    # gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.333)
    run_config = tf.ConfigProto()
    run_config.gpu_options.allow_growth = True
    
    with tf.Session(config=run_config) as sess:
        #print('012345abcde\n\n')
        #print(sess)
        #print('12345abcde\n\n')
        
    LstmRNN(
            sess,
            1,
            lstm_size=FLAGS.lstm_size,
            num_layers=FLAGS.num_layers,
            num_steps=FLAGS.num_steps,
            input_size=FLAGS.input_size,
            embed_size=FLAGS.embed_size,
        )
    
    
    
        
        rnn_model = LstmRNN(
            sess,
            FLAGS.stock_count,
            lstm_size=FLAGS.lstm_size,
            num_layers=FLAGS.num_layers,
            num_steps=FLAGS.num_steps,
            input_size=FLAGS.input_size,
            embed_size=FLAGS.embed_size,
        )

        show_all_variables()

        stock_data_list = load_sp500(
            FLAGS.input_size,
            FLAGS.num_steps,
            k=FLAGS.stock_count,
            target_symbol=FLAGS.stock_symbol,
        )

        
        if FLAGS.train:
            rnn_model.train(stock_data_list, FLAGS)
        else:
            if not rnn_model.load()[0]:
                raise Exception("[!] Train a model first, then run test mode")
        
       