# Clone from JoinQuant
# postId: e0cbb7527de49d9c9746c0889781c568
# backtestId: 88c08873dd184eb839f7a934d5bd010d
# title: 一个不太理想的机器学习模型

from jqdata import *
from jqfactor import get_factor_values
import numpy as np
import pandas as pd
import pickle
import datetime
import warnings
warnings.filterwarnings("ignore")

# 初始化函数
def initialize(context):
    set_benchmark('399101.XSHE')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, 
                             close_commission=0.0003, close_today_commission=0, 
                             min_commission=5), type='stock')
    log.set_level('order', 'error')
    
    # 全局变量
    g.stock_num = 5  # 持仓数量（5只）
    g.hold_list = []  # 当前持仓列表
    g.holdings = {}   # 持仓详情（用于止损止盈）
    g.current_model = None
    g.current_factor_list = None
    g.current_month = None
    g.cumulative_stock_pool = set()  # 累计股票池
    
    # 止损止盈参数
    g.stop_loss = 0.05          # 固定止损：-5%
    g.profit_target = 0.15      # 移动止盈启动阈值：+15%
    g.drawdown_threshold = 0.05 # 利润回撤平仓阈值：5%
    
    run_daily(prepare_stock_list, '9:05')
    run_daily(check_stop_loss_take_profit, '9:30')  # 每天检查止损止盈
    run_monthly(monthly_rebalance, 1, '9:30')

# 【新增】止损止盈检查函数
def check_stop_loss_take_profit(context):
    """每天检查持仓的止损止盈"""
    current_date = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    for stock in list(g.holdings.keys()):
        if stock not in context.portfolio.positions:
            continue
            
        position = context.portfolio.positions[stock]
        if position.total_amount == 0:
            continue
        
        current_price = position.price
        entry_price = g.holdings[stock]['entry_price']
        current_profit = (current_price - entry_price) / entry_price
        
        # 更新最高收益率
        if current_profit > g.holdings[stock]['peak_profit']:
            g.holdings[stock]['peak_profit'] = current_profit
        
        # 检查是否启动移动止盈监控
        monitoring = g.holdings[stock].get('monitoring', False)
        
        if monitoring:
            # 移动止盈逻辑：利润回撤达到阈值
            drawdown = g.holdings[stock]['peak_profit'] - current_profit
            if drawdown >= g.drawdown_threshold:
                log.info(f"{current_date} 移动止盈触发 {stock} | 最高收益: {g.holdings[stock]['peak_profit']*100:.2f}% | 当前收益: {current_profit*100:.2f}%")
                order_target(stock, 0)
                del g.holdings[stock]
                continue
        elif g.holdings[stock]['peak_profit'] >= g.profit_target:
            # 达到止盈目标，启动监控
            g.holdings[stock]['monitoring'] = True
            log.info(f"{current_date} 启动移动止盈监控 {stock} | 当前收益: {current_profit*100:.2f}%")
        
        # 固定止损逻辑
        if current_profit <= -g.stop_loss:
            log.info(f"{current_date} 固定止损触发 {stock} | 亏损: {current_profit*100:.2f}%")
            order_target(stock, 0)
            del g.holdings[stock]
            continue

# 准备股票池
def prepare_stock_list(context):
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)

# DKX指标计算函数（使用shift方法，与训练代码完全一致）
def calculate_dkx(stock, date):
    """
    计算DKX指标（使用shift方法，与训练代码一致）
    """
    try:
        # 获取最近120天数据
        price_data = get_price(stock, end_date=date, count=120, frequency='daily',
                              fields=['close', 'open', 'high', 'low', 'volume'],
                              panel=False)
        
        if len(price_data) < 80:
            return None
        
        # 获取大盘数据
        index_data = get_price('399101.XSHE', end_date=date, count=120,
                              frequency='daily', fields=['close'], panel=False)
        
        if len(index_data) < 80:
            return None
        
        # 计算MID
        price_data['MID'] = (3 * price_data['close'] + price_data['low'] + 
                            price_data['open'] + price_data['high']) / 6
        
        # 计算DKX（使用shift方法）
        price_data['DKX'] = (
            20 * price_data.MID + 
            19 * price_data.MID.shift(1) + 
            18 * price_data.MID.shift(2) + 
            17 * price_data.MID.shift(3) +
            16 * price_data.MID.shift(4) + 
            15 * price_data.MID.shift(5) + 
            14 * price_data.MID.shift(6) + 
            13 * price_data.MID.shift(7) +
            12 * price_data.MID.shift(8) + 
            11 * price_data.MID.shift(9) + 
            10 * price_data.MID.shift(10) + 
            9 * price_data.MID.shift(11) +
            8 * price_data.MID.shift(12) + 
            7 * price_data.MID.shift(13) + 
            6 * price_data.MID.shift(14) + 
            5 * price_data.MID.shift(15) +
            4 * price_data.MID.shift(16) + 
            3 * price_data.MID.shift(17) + 
            2 * price_data.MID.shift(18) + 
            1 * price_data.MID.shift(19)
        ) / 210
        
        # 计算MADKX（DKX的20日均线）
        price_data['MADKX'] = price_data['DKX'].rolling(window=20).mean()
        
        # 计算MM（21日相对强度）
        A = price_data['close'] / price_data['close'].shift(21)
        B = index_data['close'] / index_data['close'].shift(21)
        price_data['MM'] = (A - B) / B
        
        # 计算YY（60日相对强度）
        D = price_data['close'] / price_data['close'].shift(60)
        F = index_data['close'] / index_data['close'].shift(60)
        price_data['YY'] = (D - F) / F
        
        # 计算成交量比率
        price_data['HHV5_V'] = price_data['volume'].rolling(5).max().shift(1)
        
        # 计算DKX收敛度
        price_data['粘合'] = (abs((price_data['DKX'] - price_data['MADKX']) / price_data['DKX']) < 0.06)
        price_data['粘合10日'] = price_data['粘合'].rolling(10).apply(lambda x: (x == True).all(), raw=False)
        
        # 计算C/O比率
        price_data['涨幅'] = price_data['close'] / price_data['open']
        
        # 计算趋势
        price_data['DKX_上穿'] = price_data['DKX'] > price_data['DKX'].shift(1)
        price_data['MADKX_上穿'] = price_data['MADKX'] > price_data['MADKX'].shift(1)
        price_data['DKX_大于_MADKX'] = price_data['DKX'] > price_data['MADKX']
        price_data['C_大于_DKX'] = price_data['close'] > price_data['DKX']
        
        latest = price_data.iloc[-1]
        
        # 检查是否有NaN
        if pd.isna(latest['DKX']) or pd.isna(latest['MADKX']) or pd.isna(latest['MM']) or pd.isna(latest['YY']):
            return None
        
        return {
            'DKX': latest['DKX'],
            'MADKX': latest['MADKX'],
            'MM': latest['MM'],
            'YY': latest['YY'],
            'vol_ratio': latest['volume'] / latest['HHV5_V'] if pd.notna(latest['HHV5_V']) and latest['HHV5_V'] > 0 else 0,
            'dkx_convergence': latest['粘合10日'] if pd.notna(latest['粘合10日']) else False,
            'price_ratio': latest['涨幅'],
            'DKX_上穿': latest['DKX_上穿'],
            'MADKX_上穿': latest['MADKX_上穿'],
            'DKX_大于_MADKX': latest['DKX_大于_MADKX'],
            'C_大于_DKX': latest['C_大于_DKX']
        }
        
    except Exception as e:
        return None

def check_dkx_condition(dkx_result):
    """
    检查是否满足DKX选股条件（完整版，与训练代码一致）
    """
    if dkx_result is None:
        return False
    
    condition = (
        dkx_result['DKX_上穿'] and                     # DKX > REF(DKX, 1)
        dkx_result['MADKX_上穿'] and                   # MADKX > REF(MADKX, 1)
        dkx_result['DKX_大于_MADKX'] and              # DKX > MADKX
        dkx_result['C_大于_DKX'] and                  # C > DKX
        dkx_result['MM'] > 0.01 and                   # MM > 0.01
        dkx_result['YY'] > 0.01 and                   # YY > 0.01
        dkx_result['vol_ratio'] > 3 and               # 成交量 > 5日最高量*3
        dkx_result['dkx_convergence'] and             # 10日粘合度<6%
        dkx_result['price_ratio'] > 1.04              # C/O > 1.04
    )
    
    return condition

def filter_dkx_stocks(stocks, date):
    """
    用DKX条件过滤股票（完整版，与训练代码一致）
    """
    filtered_stocks = []
    
    for stock in stocks:
        try:
            dkx_result = calculate_dkx(stock, date)
            if dkx_result is None:
                continue
            
            if check_dkx_condition(dkx_result):
                filtered_stocks.append(stock)
                
        except Exception as e:
            continue
    
    return filtered_stocks

# 月度调仓
def monthly_rebalance(context):
    # 使用context.previous_date避免未来数据泄露
    yesterday = context.previous_date
    current_date = context.current_dt.strftime('%Y-%m-%d')
    current_month = datetime.datetime.strptime(current_date, '%Y-%m-%d').strftime('%Y%m')
    
    log.info(f"===== 开始月度调仓：{current_date} =====")
    
    # 检查是否需要加载新模型
    if g.current_month != current_month:
        log.info(f"检测到月份变化：{g.current_month} -> {current_month}")
        log.info("加载新模型...")
        
        model_file = f'model_{current_month}.pkl'
        factor_list_file = f'factor_list_{current_month}.txt'
        
        try:
            model_data = read_file(model_file)
            g.current_model = pickle.loads(model_data)
            log.info(f"✓ 成功加载模型: {model_file}")
            
            factor_data = read_file(factor_list_file)
            g.current_factor_list = [line.strip() for line in factor_data.decode('utf-8').split('\n') if line.strip()]
            log.info(f"✓ 成功加载因子列表: {factor_list_file}, 因子数: {len(g.current_factor_list)}")
            
            g.current_month = current_month
            
        except Exception as e:
            log.error(f"✗ 加载模型失败: {e}")
            import traceback
            log.error(traceback.format_exc())
            return
    
    # 1. 获取基础股票池
    stock_list = get_stock_pool_base(yesterday)
    if len(stock_list) == 0:
        log.warning("基础股票池为空，跳过本月调仓")
        return
    
    log.info(f"基础股票池数量: {len(stock_list)}")
    
    # 2. DKX条件筛选
    log.info("执行DKX条件筛选...")
    dkx_filtered = filter_dkx_stocks(stock_list, yesterday)
    
    # 累计股票池
    g.cumulative_stock_pool.update(dkx_filtered)
    stock_list = list(g.cumulative_stock_pool)
    
    if len(stock_list) == 0:
        log.warning("DKX筛选后股票池为空，跳过本月调仓")
        return
    
    log.info(f"本月新增: {len(dkx_filtered)}只, 累计股票池: {len(stock_list)}只")
    
    # 3. 获取因子数据
    log.info("获取因子数据...")
    try:
        factor_data = get_factor_values(
            securities=stock_list,
            factors=g.current_factor_list,
            count=1,
            end_date=yesterday
        )
        
        df = pd.DataFrame(index=stock_list, columns=g.current_factor_list)
        for factor in g.current_factor_list:
            df[factor] = list(factor_data[factor].T.iloc[:, 0])
        
        log.info(f"因子数据样本数: {len(df)}")
    except Exception as e:
        log.error(f"获取因子数据失败: {e}")
        return
    
    # 4. 截面预处理
    log.info("截面预处理...")
    df = cross_section_preprocess(df, g.current_factor_list)
    
    # 5. 模型预测
    log.info("模型预测...")
    try:
        if hasattr(g.current_model, 'predict_proba'):
            scores = g.current_model.predict_proba(df[g.current_factor_list])[:, 1]
        else:
            scores = g.current_model.predict(df[g.current_factor_list])
        
        log.info(f"预测成功，得分范围: {scores.min():.4f} ~ {scores.max():.4f}")
    except Exception as e:
        log.error(f"预测失败: {e}")
        return
    
    df['score'] = list(scores)
    df = df.sort_values(by=['score'], ascending=False)
    
    # 6. 选择得分最高的股票
    target_list = df.index.tolist()[:min(g.stock_num, len(df))]
    log.info(f"目标股票数量: {len(target_list)}")
    log.info(f"目标股票: {target_list}")
    
    # 7. 调仓
    log.info("执行调仓...")
    adjust_positions(context, target_list)
    log.info(f"===== 调仓完成，持仓: {len(context.portfolio.positions)} 只 =====")

def get_stock_pool_base(date):
    """获取基础股票池（不含DKX筛选）"""
    stocks = get_index_stocks('399101.XSHE', date)
    stocks = [s for s in stocks if not s.startswith(('3','4','8','68'))]
    
    current_data = get_current_data()
    stocks = [s for s in stocks
              if not current_data[s].is_st
              and 'ST' not in current_data[s].name
              and '*' not in current_data[s].name
              and '退' not in current_data[s].name]
    
    stocks = [s for s in stocks if
              date - get_security_info(s).start_date >= datetime.timedelta(days=375)]
    
    # 市值过滤（50-450亿）
    try:
        market_cap_data = get_valuation(stocks, end_date=date, count=1, fields=['market_cap'])
        if market_cap_data is not None and len(market_cap_data) > 0:
            market_cap_data = market_cap_data.reset_index()
            code_col = 'code' if 'code' in market_cap_data.columns else market_cap_data.columns[0]
            
            df_stocks = pd.DataFrame({'code': stocks})
            df_merged = df_stocks.merge(market_cap_data, on=code_col, how='left')
            
            mc_col = 'market_cap'
            if mc_col in df_merged.columns:
                df_filtered = df_merged[(df_merged[mc_col] >= 50) & (df_merged[mc_col] <= 450)]
                stocks_filtered = df_filtered['code'].tolist()
                
                if len(stocks_filtered) < 20:
                    df_filtered = df_merged[(df_merged[mc_col] >= 30) & (df_merged[mc_col] <= 600)]
                    stocks_filtered = df_filtered['code'].tolist()
                
                if len(stocks_filtered) > 0:
                    stocks = stocks_filtered
    except Exception as e:
        log.warning(f"市值过滤失败: {e}")
    
    return stocks

# 截面预处理
def cross_section_preprocess(df, factor_cols):
    df = df.copy()
    for col in factor_cols:
        if col in df.columns:
            median_val = df[col].median()
            df[col].fillna(median_val, inplace=True)
            q1 = df[col].quantile(0.01)
            q99 = df[col].quantile(0.99)
            df[col] = df[col].clip(q1, q99)
    return df

# 调整仓位
def adjust_positions(context, target_list):
    # 调仓卖出
    for stock in g.hold_list:
        if stock not in target_list:
            log.info(f"卖出[{stock}]")
            position = context.portfolio.positions[stock]
            close_position(position)
            # 清理持仓记录
            if stock in g.holdings:
                del g.holdings[stock]
        else:
            log.info(f"已持有[{stock}]")
    
    # 真正的等权仓位：总资金 ÷ 目标持仓数量
    target_num = len(target_list)
    if target_num == 0:
        return
    
    # 计算每只股票的目标金额（总资金的等权分配）
    value_per_stock = context.portfolio.total_value / target_num
    
    log.info(f"总资金: {context.portfolio.total_value:.2f}, 目标持仓: {target_num}只, 每只目标金额: {value_per_stock:.2f}")
    
    # 买入或调整到目标金额
    for stock in target_list:
        try:
            # 获取当前价格
            p = get_price(stock, count=1, fields=['close'], end_date=context.previous_date)
            current_price = p['close'].iloc[-1]
            if np.isnan(current_price) or current_price <= 0:
                continue
            
            if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
                # 已持有，调整到目标金额
                order_target_value(stock, value_per_stock)
                log.info(f"调整 {stock} 到目标金额 {value_per_stock:.2f}")
            else:
                # 未持有，买入
                amount = int(value_per_stock / current_price / 100) * 100
                if amount < 100:
                    continue
                
                order_result = order(stock, amount)
                if order_result is not None and order_result.filled > 0:
                    # 记录持仓信息
                    g.holdings[stock] = {
                        'entry_price': current_price,
                        'peak_profit': 0,
                        'monitoring': False
                    }
                    log.info(f"买入 {stock} | 价格: {current_price:.2f} | 数量: {amount}股 | 金额: {amount*current_price:.2f}")
        except Exception as e:
            log.warning(f"处理 {stock} 失败: {e}")
            continue

# 开仓
def open_position(security, amount):
    order_result = order(security, amount)
    if order_result is not None and order_result.filled > 0:
        return True
    return False

# 平仓
def close_position(position):
    """平仓函数"""
    security = position.security
    order_result = order_target_value(security, 0)
    if order_result is not None:
        if order_result.status == OrderStatus.held and order_result.filled == order_result.amount:
            return True
    return False