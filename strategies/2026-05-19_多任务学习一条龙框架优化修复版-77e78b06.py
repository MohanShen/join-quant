# Clone from JoinQuant
# postId: 77e78b06949fb2a0dca5f0245896179b
# backtestId: eb7755b56fbf6dda252c805a18dfe300
# title: 多任务学习一条龙框架优化修复版

# 第五步:回测(样本外测试，严格对齐训练逻辑)
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import pickle
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import datetime
import io
from collections import defaultdict

# ===================== 关键新增：定义训练时的FactorPreprocessor类 =====================
class FactorPreprocessor:
    """因子预处理器：截面标准化（与训练逻辑完全一致）"""
    def __init__(self):
        self.train_means = None
        self.train_stds = None
    
    def fit(self, X, period_indices=None):
        self.train_means = np.mean(X, axis=0)
        self.train_stds = np.std(X, axis=0) + 1e-8
        return self
    
    def transform(self, X):
        if self.train_means is None or self.train_stds is None:
            raise ValueError("预处理器未拟合！请先加载参数")
        return (X - self.train_means) / self.train_stds
    
    def fit_transform(self, X, period_indices=None):
        self.fit(X, period_indices)
        return self.transform(X)
    
    def save_params(self, filepath):
        params = {'train_means': self.train_means, 'train_stds': self.train_stds}
        np.savez(filepath, **params)
    
    def load_params(self, params_dict):
        """适配回测环境：从字典加载参数（替代文件加载）"""
        self.train_means = params_dict['train_means']
        self.train_stds = params_dict['train_stds']
        return self

# ===================== 关键新增：定义训练时的MultiTaskNetV2模型结构 =====================
class MultiTaskNetV2(nn.Module):
    """改进版多任务网络（与训练逻辑完全一致）"""
    def __init__(self, in_dim, hid=128, dropout=0.3):
        super().__init__()
        
        # 共享层带Dropout和LayerNorm（训练时的结构）
        self.shared = nn.Sequential(
            nn.Linear(in_dim, hid),
            nn.LayerNorm(hid),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(hid, hid*2),
            nn.LayerNorm(hid*2),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(hid*2, hid*2),
            nn.LayerNorm(hid*2),
            nn.ReLU(),
            nn.Dropout(dropout/2)
        )
        
        # 分类头
        self.cls = nn.Sequential(
            nn.Linear(hid*2, hid),
            nn.ReLU(),
            nn.Dropout(dropout/2),
            nn.Linear(hid, 2)
        )
        
        # 回归头
        self.reg = nn.Sequential(
            nn.Linear(hid*2, hid),
            nn.ReLU(),
            nn.Dropout(dropout/2),
            nn.Linear(hid, 1)
        )
        
        # 不确定性权重参数（训练时的结构）
        self.log_sigma_cls = nn.Parameter(torch.zeros(1))
        self.log_sigma_reg = nn.Parameter(torch.zeros(1))
    
    def forward(self, x):
        z = self.shared(x)
        return self.cls(z), self.reg(z), self.log_sigma_cls, self.log_sigma_reg

# ===================== 初始化函数（核心修改） =====================
def initialize(context):
    # 基础回测设置
    set_benchmark('399101.XSHE')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, 
                             close_commission=0.0003, close_today_commission=0, min_commission=5), 
                   type='stock')
    log.set_level('order', 'error')
    
    # 全局参数设置（对齐训练逻辑）
    g.stock_num = 10
    g.hold_list = []  # 当前持仓
    g.yesterday_HL_list = []  # 昨日涨停持仓
    
    # ===================== 关键修改1：加载训练后的配置和模型 =====================
    try:
        # 1. 加载推理配置（训练时保存的inference_config.pkl）
        config_buffer = io.BytesIO(read_file('inference_config.pkl'))
        g.inference_config = pickle.load(config_buffer)
        g.selected_factors = g.inference_config['selected_factors']
        g.model_input_dim = g.inference_config['model_input_dim']
        log.info(f"加载筛选后的因子列表，共{len(g.selected_factors)}个因子")
        log.info(f"筛选因子: {g.selected_factors}")
        
        # 2. 加载预处理器参数（训练时保存的preprocessor_params.npz）
        preprocessor_buffer = io.BytesIO(read_file('preprocessor_params.npz'))
        preprocessor_params = np.load(preprocessor_buffer)
        g.preprocessor = FactorPreprocessor()
        g.preprocessor.load_params({
            'train_means': preprocessor_params['train_means'],
            'train_stds': preprocessor_params['train_stds']
        })
        log.info("预处理器参数加载成功")
        
        # 3. 加载训练好的模型（best_model.pth）
        model_buffer = io.BytesIO(read_file('best_model.pth'))
        checkpoint = torch.load(model_buffer, map_location=torch.device('cpu'))  # 回测用CPU
        
        # 初始化模型（对齐训练时的参数）
        g.model = MultiTaskNetV2(in_dim=g.model_input_dim, hid=128, dropout=0.3)
        g.model.load_state_dict(checkpoint['model_state_dict'])
        g.model.eval()  # 推理模式
        log.info(f"模型加载成功，最佳验证集AUC: {checkpoint['val_auc']:.4f}")
        
    except Exception as e:
        log.error(f"模型/配置加载失败: {str(e)}")
        raise e
    
    # ===================== 调仓逻辑设置（对齐训练的2M调仓，可根据需要调整） =====================
    run_daily(prepare_stock_list, '9:05')
    run_monthly(monthly_adjustment, 1, '9:30')  # 每月1号调仓（对齐训练的2M调仓节奏）
    run_daily(check_limit_up, '14:00')

# ===================== 1-1 准备股票池（小幅优化） =====================
def prepare_stock_list(context):
    # 更新持仓列表
    g.hold_list = [position.security for position in list(context.portfolio.positions.values())]
    
    # 更新昨日涨停持仓列表
    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []

# ===================== 1-2 选股模块（核心修改，对齐训练逻辑） =====================
def get_stock_list(context):
    yesterday = context.previous_date
    # 1. 基础股票池（对齐训练的AA股票池：000985.XSHG，剔除科创/北交/创业板）
    stocks = get_index_stocks('000985.XSHG', yesterday)
    initial_list = [stock for stock in stocks if not stock.startswith(('3', '68', '4', '8'))]
    
    # 2. 严格过滤（对齐训练逻辑）
    initial_list = filter_st_stock(initial_list, yesterday)  # 带日期的ST过滤
    initial_list = filter_new_stock(initial_list, yesterday, n=90)  # 次新股过滤（3个月）
    initial_list = filter_paused_stock(initial_list)
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    
    if len(initial_list) < g.stock_num:
        log.warning(f"有效股票数量不足{g.stock_num}，仅{len(initial_list)}只")
        return initial_list
    
    # 3. 获取因子数据（仅用筛选后的因子）
    try:
        factor_data = get_factor_values(initial_list, g.selected_factors, 
                                       end_date=yesterday, count=1)
        df_jq_factor = pd.DataFrame(index=initial_list, columns=g.selected_factors)
        for factor in g.selected_factors:
            df_jq_factor[factor] = factor_data[factor].iloc[0].values
        df_jq_factor = df_jq_factor.fillna(0)  # 缺失值填充（对齐训练）
        
        # 4. 因子预处理（关键：使用训练集的均值/std标准化，而非截面min-max）
        X = df_jq_factor[g.selected_factors].values
        X_processed = g.preprocessor.transform(X)
        
        # 5. 模型预测（对齐训练的输出处理）
        X_tensor = torch.FloatTensor(X_processed)
        loader = DataLoader(TensorDataset(X_tensor), batch_size=1024, shuffle=False)
        
        all_pred_c = []
        all_pred_r = []
        with torch.no_grad():  # 推理时禁用梯度
            for batch in loader:
                x = batch[0]
                pred_c, pred_r, _, _ = g.model(x)
                # 分类输出：取正类概率
                cls_prob = torch.softmax(pred_c, dim=1)[:, 1].numpy()
                # 回归输出：挤压维度
                reg_pred = pred_r.squeeze().numpy()
                
                all_pred_c.append(cls_prob)
                all_pred_r.append(reg_pred)
        
        # 合并预测结果
        pred_c = np.concatenate(all_pred_c)
        pred_r = np.concatenate(all_pred_r)
        
        # 6. 综合评分（分类概率+回归排名，取均值）
        df_jq_factor['pred_mean'] = (pred_c + pred_r) / 2
        # 按评分降序排序
        df_sorted = df_jq_factor.sort_values(by='pred_mean', ascending=False)
        # 选取前N只股票
        selected_list = df_sorted.index.tolist()[:min(g.stock_num, len(df_sorted))]
        
        log.info(f"选股完成，共选出{len(selected_list)}只股票: {selected_list}")
        return selected_list
        
    except Exception as e:
        log.error(f"选股失败: {str(e)}")
        return []

# ===================== 1-3 月度调仓（原weekly_adjustment重命名，逻辑优化） =====================
def monthly_adjustment(context):
    # 获取目标持仓列表
    target_list = get_stock_list(context)
    if not target_list:
        log.warning("目标持仓为空，跳过调仓")
        return
    
    # 第一步：卖出不在目标列表且非昨日涨停的股票
    for stock in g.hold_list:
        if stock not in target_list and stock not in g.yesterday_HL_list:
            log.info(f"卖出[{stock}]：不在目标列表且非昨日涨停")
            try:
                close_position(context.portfolio.positions[stock])
            except Exception as e:
                log.error(f"卖出{stock}失败: {str(e)}")
        else:
            log.info(f"继续持有[{stock}]")
    
    # 第二步：买入新标的，按等权分配
    current_hold_count = len([s for s in g.hold_list if s in target_list or s in g.yesterday_HL_list])
    need_buy_count = g.stock_num - current_hold_count
    
    if need_buy_count > 0:
        available_cash = context.portfolio.cash
        if available_cash <= 0:
            log.warning("可用现金不足，无法买入新股票")
            return
        
        # 等权分配资金
        per_stock_value = available_cash / need_buy_count
        buy_count = 0
        
        for stock in target_list:
            if buy_count >= need_buy_count:
                break
            if stock not in g.hold_list:
                log.info(f"买入[{stock}]：分配资金{per_stock_value:.2f}元")
                if open_position(stock, per_stock_value):
                    buy_count += 1

# ===================== 1-4 涨停检查（逻辑不变） =====================
def check_limit_up(context):
    if not g.yesterday_HL_list:
        return
    
    now_time = context.current_dt
    for stock in g.yesterday_HL_list:
        try:
            current_data = get_price(stock, end_date=now_time, frequency='1m',
                                     fields=['close', 'high_limit'], skip_paused=False,
                                     fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0]['close'] < current_data.iloc[0]['high_limit']:
                log.info(f"[{stock}]涨停打开，卖出")
                close_position(context.portfolio.positions[stock])
            else:
                log.info(f"[{stock}]维持涨停，继续持有")
        except Exception as e:
            log.error(f"检查{stock}涨停状态失败: {str(e)}")

# ===================== 3-1/3-2/3-3 交易模块（逻辑不变） =====================
def order_target_value_(security, value):
    if value == 0:
        log.debug(f"清仓 {security}")
    else:
        log.debug(f"下单 {security} 目标市值 {value:.2f}")
    return order_target_value(security, value)

def open_position(security, value):
    try:
        order = order_target_value_(security, value)
        if order and order.filled > 0:
            return True
    except Exception as e:
        log.error(f"开仓{security}失败: {str(e)}")
    return False

def close_position(position):
    try:
        security = position.security
        order = order_target_value_(security, 0)
        if order and order.status == OrderStatus.held and order.filled == order.amount:
            return True
    except Exception as e:
        log.error(f"平仓{security}失败: {str(e)}")
    return False

# ===================== 2-* 过滤函数（核心修改，对齐训练逻辑） =====================
def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_st_stock(stock_list, check_date):
    """过滤ST/退市股票（对齐训练逻辑，带日期过滤）"""
    # 1. 实时ST状态
    current_data = get_current_data()
    filter1 = [stock for stock in stock_list
               if not current_data[stock].is_st
               and 'ST' not in current_data[stock].name
               and '*' not in current_data[stock].name
               and '退' not in current_data[stock].name]
    # 2. 检查日期的ST状态（更严格）
    st_data = get_extras('is_st', filter1, count=1, end_date=check_date)
    filter2 = [stock for stock in filter1 if not st_data[stock][0]]
    return filter2

def filter_new_stock(stock_list, check_date, n=90):
    """过滤次新股（对齐训练逻辑，3个月=90天）"""
    check_date = pd.to_datetime(check_date)
    return [stock for stock in stock_list 
            if (check_date - pd.to_datetime(get_security_info(stock).start_date)).days > n]

def filter_limitup_stock(context, stock_list):
    """过滤涨停股票（持仓除外）"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list 
            if stock in context.portfolio.positions 
            or last_prices[stock][-1] < current_data[stock].high_limit]

def filter_limitdown_stock(context, stock_list):
    """过滤跌停股票（持仓除外）"""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list 
            if stock in context.portfolio.positions 
            or last_prices[stock][-1] > current_data[stock].low_limit]

# 移除原filter_kcbj_stock，合并到股票池初始化逻辑中