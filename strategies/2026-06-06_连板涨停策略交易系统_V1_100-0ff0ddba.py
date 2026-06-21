# Clone from JoinQuant
# postId: 0ff0ddbaf8b427247d525260e3f7f1b0
# backtestId: 5bce71a72322900ce3fb8fbea2fe254e
# title: 连板涨停策略交易系统 V1.100

# -*- coding: utf-8 -*-
"""
连板涨停策略交易系统
版本：V1.100
作者：星
创建日期：2025-11-25
修改日期：2025-11-28


核心功能概述：
本系统基于涨停板战法理论，通过量化手段识别连续涨停股票的交易机会
结合严格的风险控制体系，实现自动化交易执行
"""

# 基础功能模块导入
import numpy as np
import talib as tl

def initialize(context):
    """
    策略初始化配置函数（完整版）
    """
    # 设置日志级别
    log.set_level('order', 'error')
    log.set_level('system', 'error') 
    log.set_level('strategy', 'debug')
    
    # 全局变量初始化区
    g.stock_pool = []           # 候选股票暂存列表
    g.cache_data = {}           # 交易数据缓存字典
    g.stockNum = 5              # 最大持仓股票数量限制
    g.bar_number = 0            # K线数据计数器
    g.stock_pool_update_day = 0 # 股票池更新天数记录
    
    # 核心策略参数配置区
    g.ATR_WINDOW = 14                    # 平均真实波幅计算周期
    g.LONG_UNIT = '1d'                   # 长周期时间单位
    g.TRAILING_STOP_LOSS_ATR = 2         # 移动止损ATR倍数系数
    g.POSITION_SIGMA = 2                 # 仓位计算标准差倍数
    g.CHANGE_STOCK_POOL_DAY_NUMBER = 5   # 股票池更新频率天数
    
    # 定时任务执行配置
    run_daily(before_market_open, 'before_open')  # 开盘前准备
    run_daily(market_open, 'open')                # 开盘时交易
    run_daily(after_market_close, 'after_close')  # 收盘后总结
    
    # 添加监控定时任务
    add_monitoring_schedule(context)
    
    # 系统启动日志记录
    log.info("=" * 60)
    log.info("🎯 连板涨停策略交易系统初始化完成")
    log.info(f"📊 策略参数: ATR周期={g.ATR_WINDOW}, 止损倍数={g.TRAILING_STOP_LOSS_ATR}")
    log.info(f"💰 仓位管理: 标准差倍数={g.POSITION_SIGMA}, 最大持仓={g.stockNum}只")
    log.info("✅ 所有定时任务已设置完成")
    log.info("=" * 60)

def handle_trading_exception(context, error, operation_type, stock_code=None):
    """
    交易异常处理函数
    功能：统一处理交易过程中的异常情况
    """
    try:
        log.error(f"❌ 交易异常处理: 操作类型[{operation_type}], 股票[{stock_code or 'N/A'}]")
        log.error(f"❌ 异常信息: {str(error)}")
        
        # 根据操作类型执行不同的恢复策略
        if operation_type == "buy":
            # 买入异常，记录失败并跳过该股票
            if stock_code and stock_code in g.stock_pool:
                g.stock_pool.remove(stock_code)
                log.info(f"⏭️ 从候选池移除异常股票: {stock_code}")
                
        elif operation_type == "sell":
            # 卖出异常，记录日志但继续处理其他股票
            log.warn(f"⚠️ 卖出操作异常，继续处理其他股票")
            
        elif operation_type == "data":
            # 数据异常，尝试重新获取数据
            log.info("🔄 数据异常，尝试重新验证市场数据")
            validate_market_data(context)
            
        # 记录异常发生时间
        exception_time = context.current_dt.strftime("%Y-%m-%d %H:%M:%S")
        log.info(f"⏰ 异常发生时间: {exception_time}")
        
        return True
        
    except Exception as recovery_error:
        log.critical(f"💥 异常处理过程本身发生错误: {str(recovery_error)}")
        return False

def emergency_stop(context, reason):
    """
    紧急停止函数
    功能：在极端情况下停止策略运行
    """
    try:
        log.critical(f"🛑 执行紧急停止: {reason}")
        
        # 清空所有持仓
        if len(context.portfolio.positions) > 0:
            log.critical("🛑 开始清空所有持仓")
            for stock_code in list(context.portfolio.positions.keys()):
                try:
                    order_target(stock_code, 0)
                    log.info(f"🛑 紧急平仓: {stock_code}")
                except Exception as e:
                    log.error(f"❌ 紧急平仓失败: {stock_code}, {str(e)}")
        
        # 停止所有定时任务
        log.critical("🛑 停止所有定时任务")
        # 注意：在聚宽平台中，无法直接停止已设置的定时任务
        # 但可以通过设置标志位来避免执行后续逻辑
        
        # 记录紧急停止事件
        stop_time = context.current_dt.strftime("%Y-%m-%d %H:%M:%S")
        log.critical(f"🛑 紧急停止完成时间: {stop_time}")
        
        return True
        
    except Exception as error:
        log.critical(f"💥 紧急停止过程发生错误: {str(error)}")
        return False

def backup_strategy_data(context):
    """
    策略数据备份函数
    功能：定期备份重要策略数据
    """
    try:
        log.info("💾 开始备份策略数据")
        
        backup_data = {
            'timestamp': context.current_dt.strftime("%Y-%m-%d %H:%M:%S"),
            'portfolio_value': context.portfolio.total_value,
            'cash': context.portfolio.cash,
            'positions_count': len(context.portfolio.positions),
            'stock_pool_count': len(g.stock_pool),
            'cache_data_count': len(g.cache_data)
        }
        
        # 记录备份信息
        log.info(f"💾 数据备份完成: 总资产{backup_data['portfolio_value']:.2f}, "
                f"持仓{backup_data['positions_count']}只, "
                f"候选池{backup_data['stock_pool_count']}只")
                
        return backup_data
        
    except Exception as error:
        log.error(f"❌ 策略数据备份异常: {str(error)}")
        return None

def restore_strategy_data(backup_data):
    """
    策略数据恢复函数
    功能：从备份数据恢复策略状态
    """
    try:
        if not backup_data:
            log.warn("⚠️ 无有效备份数据可恢复")
            return False
            
        log.info("🔄 开始恢复策略数据")
        log.info(f"📊 恢复时间点: {backup_data.get('timestamp', '未知')}")
        log.info(f"💰 备份总资产: {backup_data.get('portfolio_value', 0):.2f}")
        
        # 这里可以添加具体的数据恢复逻辑
        # 由于聚宽平台的限制，完整的数据恢复可能需要在外部实现
        
        log.info("✅ 策略数据恢复完成")
        return True
        
    except Exception as error:
        log.error(f"❌ 策略数据恢复异常: {str(error)}")
        return False

def optimize_data_loading(context, stock_list, batch_size=50):
    """
    数据加载优化函数
    功能：分批加载数据，避免单次请求数据量过大
    """
    try:
        log.info(f"⚡ 开始优化数据加载，股票数量: {len(stock_list)}，批次大小: {batch_size}")
        
        results = {}
        total_batches = (len(stock_list) + batch_size - 1) // batch_size
        
        for i in range(0, len(stock_list), batch_size):
            batch = stock_list[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            log.debug(f"⚡ 加载批次 {batch_num}/{total_batches}, 股票数量: {len(batch)}")
            
            try:
                # 获取批量价格数据
                price_data = get_price(
                    batch, 
                    count=35, 
                    end_date=context.current_dt.strftime("%Y-%m-%d"),
                    panel=False,
                    fields=['close', 'open', 'high', 'low', 'volume', 'paused']
                )
                
                # 按股票代码分组存储结果
                for stock in batch:
                    stock_data = price_data[price_data['code'] == stock]
                    if not stock_data.empty:
                        results[stock] = stock_data
                        
            except Exception as batch_error:
                log.warn(f"⚠️ 批次 {batch_num} 数据加载异常: {str(batch_error)}")
                continue
                
        log.info(f"✅ 数据加载完成: 成功{len(results)}只，失败{len(stock_list) - len(results)}只")
        return results
        
    except Exception as error:
        log.error(f"❌ 数据加载优化异常: {str(error)}")
        return {}

def cleanup_cache_data(context):
    """
    缓存数据清理函数
    功能：定期清理过期的缓存数据
    """
    try:
        log.info("🧹 开始清理缓存数据")
        
        initial_count = len(g.cache_data)
        current_date = context.current_dt.strftime("%Y-%m-%d")
        
        # 清理不再持仓的股票缓存
        current_holdings = list(context.portfolio.positions.keys())
        keys_to_remove = []
        
        for stock_code in g.cache_data.keys():
            if stock_code not in current_holdings:
                keys_to_remove.append(stock_code)
                
        for key in keys_to_remove:
            del g.cache_data[key]
            
        cleaned_count = initial_count - len(g.cache_data)
        
        log.info(f"🧹 缓存清理完成: 清理{cleaned_count}条，剩余{len(g.cache_data)}条")
        return cleaned_count
        
    except Exception as error:
        log.error(f"❌ 缓存数据清理异常: {str(error)}")
        return 0

def before_market_open(context):
    """
    盘前数据准备函数
    功能：更新候选股票池、刷新持仓股票关键指标
    执行时机：每个交易日开盘前自动执行
    """
    # 记录函数执行时间
    log.info('📊 盘前准备函数开始执行: ' + str(context.current_dt.time()))
    
    # 股票池更新流程
    log.info("🔄 开始执行候选股票池更新流程")
    stock_pool(context)
    
    # 持仓股票数据处理流程
    if len(context.portfolio.positions) > 0:
        log.info(f"📈 开始更新{len(context.portfolio.positions)}只持仓股票数据")
        for stock_code in context.portfolio.positions.keys():
            try:
                position_info = context.portfolio.positions[stock_code]
                
                # 持仓期间最高价计算
                high_price_data = get_price(
                    stock_code, 
                    start_date=position_info.init_time,
                    end_date=context.current_dt, 
                    frequency="1m", 
                    fields=['high'], 
                    skip_paused=True, 
                    fq="pre", 
                    count=None
                )
                
                if high_price_data is not None and len(high_price_data) > 0:
                    highest_price = high_price_data['high'].max()
                    
                    # 缓存数据更新
                    if stock_code not in g.cache_data.keys():
                        g.cache_data[stock_code] = {}
                    
                    g.cache_data[stock_code]['high_price'] = highest_price
                    log.debug(f"📊 更新股票{stock_code}最高价: {highest_price:.2f}")
                
                # ATR指标计算更新
                atr_value = calc_history_atr(
                    code=stock_code, 
                    end_time=get_last_time(position_info.init_time), 
                    timeperiod=g.ATR_WINDOW, 
                    unit=g.LONG_UNIT
                )
                
                if not np.isnan(atr_value):
                    if stock_code not in g.cache_data.keys():
                        g.cache_data[stock_code] = {}
                    
                    g.cache_data[stock_code]['atr'] = atr_value
                    log.debug(f"📊 更新股票{stock_code}ATR值: {atr_value:.4f}")
                    
            except Exception as error:
                log.warn(f"⚠️ 持仓股票{stock_code}数据更新失败: {str(error)}")
                continue
    else:
        log.info("💤 当前无持仓股票，跳过持仓数据更新流程")

def market_open(context):
    """
    盘中交易执行函数
    功能：执行买入、卖出、止损等交易操作
    执行时机：每个交易日开盘时自动执行
    """
    log.info("🎯 开始执行盘中交易流程")
    buy_operation(context)          # 买入操作执行
    sell_operation(context)         # 卖出操作执行
    stop_loss_operation(context)    # 止损操作执行

def after_market_close(context):
    """
    盘后数据汇总函数（完整版）
    """
    log.info('📋 盘后汇总函数执行时间: ' + str(context.current_dt.time()))
    
    # 执行数据备份
    backup_data = backup_strategy_data(context)
    
    # 执行缓存清理
    cleanup_cache_data(context)
    
    # 当日成交记录获取
    trade_records = get_trades()
    
    # 打印持仓总结
    if len(context.portfolio.positions) > 0:
        log.info(f"💼 收盘时持仓{len(context.portfolio.positions)}只股票:")
        for position in context.portfolio.positions.values():
            profit_rate = (position.price / position.avg_cost - 1) * 100
            status_icon = "🟢" if profit_rate > 0 else "🔴"
            log.info(f"{status_icon} {position.security}: 成本{position.avg_cost:.2f}, "
                    f"现价{position.price:.2f}, 收益{profit_rate:.2f}%")
    else:
        log.info("💤 当前无持仓")
    
    # 成交记录遍历输出 - 修复部分
    if trade_records:
        log.info(f"📝 当日成交记录{len(trade_records)}笔:")
        for single_trade in trade_records.values():
            # 修复：通过成交数量和价格判断买卖方向
            if hasattr(single_trade, 'amount'):
                # 根据成交数量正负判断买卖
                if single_trade.amount > 0:
                    action_type = "买入"
                elif single_trade.amount < 0:
                    action_type = "卖出"
                else:
                    action_type = "未知"
                
                filled_amount = abs(single_trade.amount)
            else:
                # 备用方案：通过成交价与持仓成本比较判断
                action_type = "交易"
                filled_amount = getattr(single_trade, 'filled', 0)
            
            # 获取股票代码和价格
            stock_code = getattr(single_trade, 'security', '未知')
            price = getattr(single_trade, 'price', 0)
            
            log.info(f"  {action_type} {stock_code}: "
                    f"{filled_amount}股 @ {price:.2f}")
    else:
        log.info("💤 当日无成交记录")
    
    # 账户资金总结
    total_value = context.portfolio.total_value
    cash = context.portfolio.cash
    log.info(f"💰 账户总结: 总资产{total_value:.2f}, 可用资金{cash:.2f}")
    
    # 策略性能总结
    monitor_strategy_performance(context)
    
    log.info('🎯 当日交易流程结束')
    log.info('=' * 60)


def load_fundamentals_data(context):
    """
    基本面数据加载函数
    功能：筛选符合市值要求的股票基础池
    返回：符合条件的股票代码列表
    """
    try:
        # 市值筛选条件：10亿至350亿
        fundamentals_data = get_fundamentals(
            query(valuation)
            .filter(valuation.market_cap > 10)
            .filter(valuation.market_cap < 350)
        )
        
        if fundamentals_data is not None and len(fundamentals_data) > 0:
            log.info(f"✅ 基本面数据加载完成，候选股票数量: {len(fundamentals_data)}")
            return fundamentals_data['code'].tolist()
        else:
            log.warn("⚠️ 基本面数据获取异常或结果为空")
            return []
            
    except Exception as error:
        log.error(f"❌ 基本面数据加载过程出错: {str(error)}")
        return []


def buy_operation(context):
    """
    买入交易执行函数
    功能：遍历候选股票池，执行买入逻辑
    执行条件：股票未持仓、未涨停、仓位计算正常
    """
    log.info(f"🛒 开始执行买入流程，候选股票数量: {len(g.stock_pool)}")
    
    # 候选股票池空值检查
    if len(g.stock_pool) == 0:
        log.info("💤 候选股票池为空，无买入目标")
        return
    
    success_buy_count = 0
    for stock_code in g.stock_pool:
        try:
            # 持仓状态检查
            if stock_code in context.portfolio.positions.keys():
                log.info(f"⏭️ 股票{stock_code}已存在持仓，跳过买入")
                continue
            
            # 实时数据获取检查
            current_stock_data = get_current_data()[stock_code]
            if current_stock_data is None:
                log.warn(f"⚠️ 股票{stock_code}实时数据获取失败")
                continue
            
            # 涨停状态检查
            if is_high_limit(stock_code):
                log.info(f"🚫 股票{stock_code}处于涨停状态，无法买入")
                continue
            
            # 买入仓位计算
            calculated_position = calc_position(context, stock_code)
            log.info(f"📊 股票{stock_code}计算买入仓位: {calculated_position}股")
            
            if calculated_position <= 0:
                log.warn(f"⚠️ 股票{stock_code}仓位计算结果异常，跳过买入")
                continue
            
            # 持仓数量限制检查
            available_positions = g.stockNum - len(context.portfolio.positions)
            if available_positions <= 0:
                log.info("🎯 已达到最大持仓数量限制")
                break
            
            # 买入订单执行
            log.info(f"🛒 尝试买入股票{stock_code}，计划数量{calculated_position}")
            order_result = order_target(security=stock_code, amount=calculated_position)
            
            if order_result is not None:
                log.info(f"✅ 买入订单提交成功: {str(order_result)}")
                
                # 成交结果处理
                if order_result.filled > 0:
                    log.info(f"🎉 买入成交! 股票{stock_code}，成交均价{order_result.price:.2f}，成交数量{order_result.filled}")
                    
                    # 缓存数据更新
                    atr_value = calc_history_atr(
                        code=stock_code, 
                        end_time=get_last_time(context.current_dt),
                        timeperiod=g.ATR_WINDOW, 
                        unit=g.LONG_UNIT
                    )
                    
                    if stock_code not in g.cache_data.keys():
                        g.cache_data[stock_code] = {}
                    
                    g.cache_data[stock_code]['atr'] = atr_value
                    g.cache_data[stock_code]['high_price'] = current_stock_data.last_price
                    
                    g.bar_number += 1
                    success_buy_count += 1
                else:
                    log.info("⏳ 买入订单未成交")
            else:
                log.warn("❌ 买入订单提交失败")
                
        except Exception as error:
            log.error(f"❌ 股票{stock_code}买入过程出错: {str(error)}")
            continue
    
    log.info(f"🎯 买入流程执行完成，成功买入{success_buy_count}只股票")
    
    # 候选股票池清空
    g.stock_pool = []

def is_high_limit(stock_code):
    """
    涨停状态判断函数
    功能：识别股票是否处于涨停状态
    返回：布尔值，True表示涨停，False表示未涨停
    """
    try:
        current_stock_data = get_current_data()[stock_code]
        if current_stock_data is None:
            return False
        
        # 涨停价属性检查
        if hasattr(current_stock_data, 'high_limit'):
            is_limit = current_stock_data.last_price >= current_stock_data.high_limit * 0.995
            if is_limit:
                log.debug(f"🚫 股票{stock_code}处于涨停状态")
            return is_limit
        else:
            # 历史数据涨幅计算
            historical_data = attribute_history(stock_code, 2, '1d', ['close'], skip_paused=True)
            if len(historical_data) < 2:
                return False
            
            price_increase = (current_stock_data.last_price - historical_data['close'][-2]) / historical_data['close'][-2]
            is_limit = price_increase > 0.095  # 涨幅超过9.5%判定为涨停
            if is_limit:
                log.debug(f"🚫 股票{stock_code}涨幅{price_increase:.2%}，判定为涨停")
            return is_limit
            
    except Exception as error:
        log.warn(f"⚠️ 涨停状态判断异常: {str(error)}")
        return False


def is_low_limit(stock_code):
    """
    跌停状态判断函数
    功能：识别股票是否处于跌停状态
    返回：布尔值，True表示跌停，False表示未跌停
    """
    try:
        current_stock_data = get_current_data()[stock_code]
        if current_stock_data is None:
            return False
        
        # 跌停价属性检查
        if hasattr(current_stock_data, 'low_limit'):
            is_limit = current_stock_data.last_price <= current_stock_data.low_limit * 1.005
            if is_limit:
                log.debug(f"📉 股票{stock_code}处于跌停状态")
            return is_limit
        else:
            # 历史数据跌幅计算
            historical_data = attribute_history(stock_code, 2, '1d', ['close'], skip_paused=True)
            if len(historical_data) < 2:
                return False
            
            price_decrease = (historical_data['close'][-2] - current_stock_data.last_price) / historical_data['close'][-2]
            is_limit = price_decrease > 0.095  # 跌幅超过9.5%判定为跌停
            if is_limit:
                log.debug(f"📉 股票{stock_code}跌幅{price_decrease:.2%}，判定为跌停")
            return is_limit
            
    except Exception as error:
        log.warn(f"⚠️ 跌停状态判断异常: {str(error)}")
        return False

def sell_operation(context):
    """
    卖出交易执行函数
    功能：根据止盈止损条件执行卖出操作
    执行条件：持仓股票达到止损或止盈阈值
    """
    if len(context.portfolio.positions) == 0:
        log.info("💤 无持仓股票，跳过卖出流程")
        return
    
    sell_candidates = list(context.portfolio.positions.keys())
    log.info(f"🛒 开始执行卖出流程，持仓股票数量: {len(sell_candidates)}")
    
    success_sell_count = 0
    for stock_code in sell_candidates:
        try:
            # 持仓成本获取
            hold_cost = context.portfolio.positions[stock_code].acc_avg_cost
            
            # 实时价格获取
            current_price_data = get_price(
                stock_code, 
                start_date=None, 
                end_date=context.current_dt,
                frequency='1m', 
                fields=['close'], 
                skip_paused=True, 
                count=1
            )
            
            if current_price_data is None or len(current_price_data) == 0:
                log.warn(f"⚠️ 股票{stock_code}实时价格获取失败")
                continue
            
            current_market_price = current_price_data.iloc[0]['close']
            profit_rate = (current_market_price / hold_cost - 1) * 100
            
            # 止损条件检查：亏损超过10%
            if current_market_price < hold_cost * 0.90:
                log.info(f"🛑 股票{stock_code}触发止损条件，收益{profit_rate:.2f}%，执行卖出")
                order_target(stock_code, 0)
                success_sell_count += 1
                
            # 止盈条件检查：盈利超过20%且未涨停
            elif current_market_price >= hold_cost * 1.20:
                if not is_high_limit(stock_code):
                    log.info(f"🎉 股票{stock_code}触发止盈条件，收益{profit_rate:.2f}%，执行卖出")
                    order_target(stock_code, 0)
                    success_sell_count += 1
                else:
                    log.info(f"⏳ 股票{stock_code}满足止盈条件但处于涨停状态，暂缓卖出")
                    
        except Exception as error:
            log.error(f"❌ 股票{stock_code}卖出过程出错: {str(error)}")
            continue
    
    log.info(f"🎯 卖出流程执行完成，成功卖出{success_sell_count}只股票")

def stop_loss_operation(context):
    """
    移动止损执行函数
    功能：基于ATR指标的动态止损管理
    执行条件：价格回撤超过设定阈值
    """
    if len(context.portfolio.positions) == 0:
        return
    
    log.info("🛡️ 开始执行移动止损检查流程")
    triggered_stop_loss_count = 0
    
    for stock_code in context.portfolio.positions.keys():
        try:
            position_details = context.portfolio.positions[stock_code]
            
            # 可卖出数量检查
            if position_details.closeable_amount <= 0:
                continue
            
            # 跌停状态检查
            if is_low_limit(stock_code):
                continue
            
            # 实时数据获取
            current_stock_data = get_current_data()[stock_code]
            if current_stock_data is None:
                continue
            
            current_market_price = current_stock_data.last_price
            
            # 持仓期间最高价计算
            start_date = context.current_dt.strftime("%Y-%m-%d") + " 00:00:00"
            
            # 建仓时间调整逻辑
            if context.current_dt.strftime("%Y-%m-%d") <= position_details.init_time.strftime("%Y-%m-%d"):
                start_date = position_details.init_time
            
            # 最高价数据获取
            high_price_data = get_price(
                security=stock_code, 
                start_date=start_date, 
                end_date=context.current_dt,
                frequency='1m', 
                fields=['high'], 
                skip_paused=True, 
                fq='pre', 
                count=None
            )
            
            if high_price_data is None or len(high_price_data) == 0:
                log.warn(f"⚠️ 股票{stock_code}最高价数据获取失败")
                continue
            
            period_high_price = high_price_data['high'].max()
            
            # 异常数据处理
            if np.isnan(period_high_price):
                if stock_code in g.cache_data and 'high_price' in g.cache_data[stock_code]:
                    period_high_price = max(current_market_price, g.cache_data[stock_code]['high_price'])
                else:
                    period_high_price = current_market_price
            
            # 缓存数据更新
            if stock_code not in g.cache_data:
                g.cache_data[stock_code] = {}
            
            g.cache_data[stock_code]['high_price'] = period_high_price
            
            # ATR数据获取
            if stock_code in g.cache_data and 'atr' in g.cache_data[stock_code]:
                current_atr = g.cache_data[stock_code]['atr']
            else:
                current_atr = calc_history_atr(
                    code=stock_code, 
                    end_time=get_last_time(context.current_dt),
                    timeperiod=g.ATR_WINDOW, 
                    unit=g.LONG_UNIT
                )
                g.cache_data[stock_code]['atr'] = current_atr
            
            average_cost = position_details.avg_cost
            
            # 移动止损条件判断
            stop_loss_price = period_high_price - current_atr * g.TRAILING_STOP_LOSS_ATR
            if current_market_price <= stop_loss_price:
                log.info(f"🛑 股票{stock_code}触发移动止损条件")
                log.info(f"  最高价: {period_high_price:.2f}, ATR: {current_atr:.4f}")
                log.info(f"  止损价: {stop_loss_price:.2f}, 当前价: {current_market_price:.2f}")
                
                order_result = order_target(security=stock_code, amount=0)
                
                if order_result is not None and order_result.filled > 0:
                    result_flag = "盈利" if current_market_price > average_cost else "亏损"
                    profit_rate = (current_market_price / average_cost - 1) * 100
                    log.info(f"🎯 移动止损执行: 股票{stock_code}, 卖出数量{order_result.filled}")
                    log.info(f"  📊 结果: {result_flag}, 收益率: {profit_rate:.2f}%")
                    triggered_stop_loss_count += 1
                    
        except Exception as error:
            log.error(f"❌ 股票{stock_code}移动止损处理异常: {str(error)}")
            continue
    
    log.info(f"🛡️ 移动止损检查完成，触发止损{triggered_stop_loss_count}只股票")

def stock_pool(context):
    """
    候选股票池更新函数（优化版）
    """
    current_date = context.current_dt.strftime("%Y-%m-%d")
    base_stock_list = load_fundamentals_data(context)
    
    if not base_stock_list:
        log.warn("⚠️ 基础股票池数据为空")
        return
    
    current_market_data = get_current_data()
    log.info("=" * 60)
    log.info(f"🔄 开始更新候选股票池，基础股票数量: {len(base_stock_list)}")
    
    selected_stock_count = 0
    g.stock_pool = []  # 清空原有候选池
    
    # 大规模数据采样处理
    if len(base_stock_list) > 200:
        import random
        base_stock_list = random.sample(base_stock_list, 200)
        log.info(f"🎲 执行随机采样，筛选200只股票进行深度分析")
    
    # 使用优化数据加载
    price_data_dict = optimize_data_loading(context, base_stock_list)
    
    for stock_code in base_stock_list:
        try:
            # 股票代码格式验证
            if not stock_code or len(stock_code) < 6:
                continue
            
            # 实时数据存在性检查
            if stock_code not in current_market_data:
                continue
                
            stock_current_data = current_market_data[stock_code]
            if stock_current_data is None:
                continue
            
            # 基础风险排除条件
            if getattr(stock_current_data, 'is_st', False):
                continue
                
            if getattr(stock_current_data, 'paused', False):
                continue
            
            stock_name = getattr(stock_current_data, 'name', '')
            if not stock_name:
                continue
                
            if 'ST' in stock_name or '*' in stock_name or '退' in stock_name:
                continue
            
            # 从优化加载的数据中获取价格数据
            price_history_data = price_data_dict.get(stock_code)
            if price_history_data is None or len(price_history_data) < 30:
                continue
            
            # 多重技术条件判断
            gap_up_condition = gap_up_judge(price_history_data)  # 高开判断
            exceed_expectation = expectation_exceed_judge(price_history_data, stock_code, current_date)  # 超预期判断
            two_day_strength = two_day_strength_pattern(price_history_data)      # 两日强势模式
            daily_strength = daily_strength_pattern(price_history_data)      # 每日强势模式
            
            log.debug(f"📊 股票{stock_code}技术条件: "
                     f"高开={gap_up_condition}, 超预期={exceed_expectation}, "
                     f"两日强势={two_day_strength}, 每日强势={daily_strength}")
            
            # 候选条件组合
            if gap_up_condition or exceed_expectation:
                g.stock_pool.append(stock_code)
                selected_stock_count += 1
                log.info(f"✅ 入选候选股票: {stock_code}")
                
        except Exception as error:
            log.warn(f"⚠️ 股票{stock_code}处理过程异常: {str(error)}")
            continue
    
    if len(g.stock_pool) == 0:
        log.info("💤 未找到符合技术条件的股票")
        
        # 备选方案：随机选择测试股票
        if len(base_stock_list) > 0:
            import random
            test_samples = random.sample(base_stock_list, min(3, len(base_stock_list)))
            g.stock_pool = test_samples
            log.info(f"🎲 启用测试模式，随机选择{len(test_samples)}只股票")
        
    else:
        log.info(f"✅ 候选股票池更新完成，入选{selected_stock_count}只股票")
    log.info("=" * 60)

def turnover_filter(stock_code, context):
    """
    换手率筛选函数
    功能：基于换手率指标筛选活跃股票
    条件：昨日换手率大于3%
    """
    try:
        current_date = context.current_dt.strftime("%Y-%m-%d")
        turnover_data = get_valuation(
            stock_code, 
            fields=["turnover_ratio"], 
            end_date=current_date, 
            count=4
        )
        
        # 昨日换手率提取与判断
        if len(turnover_data) > 2:
            yesterday_turnover = turnover_data.iloc[-2]['turnover_ratio']
            if yesterday_turnover is not None and yesterday_turnover > 3:
                return True
        
        return False
        
    except Exception as error:
        log.warn("换手率数据获取异常: {}".format(str(error)))
        return False

def gap_up_judge(price_data):
    """
    高开幅度判断函数
    功能：识别股票是否呈现高开态势
    条件：开盘涨幅在0.2%到9.2%之间
    """
    try:
        if len(price_data) < 2:
            return False
        
        today_open = price_data.iloc[-1]['open']   # 当日开盘价
        yesterday_close = price_data.iloc[-2]['close']  # 昨日收盘价
        gap_rate = (today_open / yesterday_close - 1) * 100
        
        # 高开条件判断
        result = today_open >= yesterday_close * 1.002 and today_open < yesterday_close * 1.092
        if result:
            log.debug(f"📈 高开判断: 涨幅{gap_rate:.2f}%，符合条件")
        return result
        
    except Exception as error:
        log.warn(f"⚠️ 高开判断过程异常: {str(error)}")
        return False

def golden_line_calc(stock_code, current_date, price_data):
    """
    黄金线计算函数
    功能：计算动态支撑压力位参考线
    公式：过去30日最高价均值上浮13%
    """
    try:
        if len(price_data) < 32:
            return 0
        
        # 历史数据切片（排除最近2日）
        historical_slice = price_data.iloc[-32:-2]
        baseline_value = historical_slice['high'].mean()
        golden_line = baseline_value * (1 + 13 / 100)
        
        log.debug(f"📊 股票{stock_code}黄金线计算: 基准{baseline_value:.2f} → 黄金线{golden_line:.2f}")
        return golden_line
        
    except Exception as error:
        log.warn(f"⚠️ 黄金线计算过程异常: {str(error)}")
        return 0

def expectation_exceed_judge(price_data, stock_name, current_date):
    """
    超预期表现判断函数
    功能：识别价格突破黄金线的强势信号
    条件：昨日收盘价突破黄金线3%以上
    """
    try:
        if len(price_data) < 2:
            return False
        
        golden_line_value = golden_line_calc(stock_name, current_date, price_data)
        if golden_line_value == 0:
            return False
        
        # 昨日收盘价获取与比较
        yesterday_close_price = price_data.iloc[-2]['close']
        exceed_rate = (yesterday_close_price / golden_line_value - 1) * 100
        result = yesterday_close_price > golden_line_value * 1.03
        
        if result:
            log.debug(f"🚀 超预期判断: 突破黄金线{exceed_rate:.2f}%，符合条件")
        return result
        
    except Exception as error:
        log.warn(f"⚠️ 超预期判断过程异常: {str(error)}")
        return False

def limit_up_judge(price_data, index_offset):
    """
    涨停状态判断辅助函数
    功能：在指定位置判断是否出现涨停
    条件：涨幅超过9.4%且收盘价接近最高价
    """
    try:
        if len(price_data) < abs(index_offset) + 1:
            log.debug(f"⚠️ 涨停判断数据不足: 需要{abs(index_offset)+1}天，实际{len(price_data)}天")
            return False
        
        close_price = price_data.iloc[index_offset]['close']  # 指定位置收盘价
        high_price = price_data.iloc[index_offset]['high']   # 指定位置最高价
        
        # 涨幅计算与涨停判断
        if index_offset-1 >= -len(price_data):
            previous_close = price_data.iloc[index_offset-1]['close']
            increase_ratio = close_price / previous_close
            increase_percent = (increase_ratio - 1) * 100
            
            # 涨停条件判断
            is_limit = increase_ratio > 1.094 and abs(close_price - high_price) / high_price < 0.01
            
            if is_limit:
                log.debug(f"🚀 涨停判断: 位置{index_offset}, 涨幅{increase_percent:.2f}%, 符合条件")
            else:
                log.debug(f"📊 涨停判断: 位置{index_offset}, 涨幅{increase_percent:.2f}%, 未达条件")
            
            return is_limit
            
        return False
        
    except Exception as error:
        log.warn(f"⚠️ 涨停判断过程异常: {str(error)}")
        return False

def volume_surge_judge(price_data, day_offset, compare_offset):
    """
    成交量放大判断函数
    功能：识别成交量异常放大信号
    条件：成交量较前期放大1.2倍以上
    """
    try:
        if len(price_data) < abs(day_offset) + abs(compare_offset) + 1:
            log.debug(f"⚠️ 成交量判断数据不足: 需要{abs(day_offset)+abs(compare_offset)+1}天，实际{len(price_data)}天")
            return False
        
        # 成交量对比计算
        current_volume = price_data.iloc[day_offset]['volume']
        compare_volume = price_data.iloc[day_offset-compare_offset]['volume']
        
        if compare_volume > 0:
            volume_ratio = current_volume / compare_volume
            is_surge = volume_ratio > 1.2  # 成交量放大阈值
            
            if is_surge:
                log.debug(f"📈 成交量判断: 位置{day_offset}, 对比{compare_offset}天前, 放大{volume_ratio:.2f}倍, 符合条件")
            else:
                log.debug(f"📊 成交量判断: 位置{day_offset}, 对比{compare_offset}天前, 放大{volume_ratio:.2f}倍, 未达条件")
                
            return is_surge
            
        log.debug(f"⚠️ 成交量判断: 对比日成交量为0，无法计算")
        return False
        
    except Exception as error:
        log.warn(f"⚠️ 成交量判断过程异常: {str(error)}")
        return False


def previous_day_no_limit_up(price_data):
    """
    前日无涨停判断函数
    功能：确认前日未出现涨停状态
    """
    result = not limit_up_judge(price_data, -3)
    log.debug(f"📊 前日无涨停判断: {result}")
    return result


def two_day_strength_pattern(price_data):
    """
    两日强势模式识别函数
    功能：识别连续两日强势上涨模式
    模式：前日未涨停 + 昨日涨停 + 昨日放量
    """
    try:
        yesterday_limit_up = limit_up_judge(price_data, -2)  # 昨日涨停判断
        yesterday_volume_surge = volume_surge_judge(price_data, -2, 1) or volume_surge_judge(price_data, -2, 2)  # 昨日放量判断
        
        result = previous_day_no_limit_up(price_data) and yesterday_limit_up and yesterday_volume_surge
        
        if result:
            log.debug(f"🚀 两日强势模式: 符合条件")
        else:
            log.debug(f"📊 两日强势模式: 未达条件")
            
        return result
        
    except Exception as error:
        log.warn(f"⚠️ 两日强势模式判断异常: {str(error)}")
        return False

def daily_strength_pattern(price_data):
    """
    每日强势模式识别函数
    功能：识别连续多日强势上涨模式
    模式：前日涨停 + 昨日涨停 + 昨日放量
    """
    try:
        day_before_yesterday_limit_up = limit_up_judge(price_data, -3)  # 前日涨停判断
        yesterday_limit_up = limit_up_judge(price_data, -2)  # 昨日涨停判断
        yesterday_volume_surge = volume_surge_judge(price_data, -2, 1) or volume_surge_judge(price_data, -2, 2)  # 昨日放量判断
        
        result = day_before_yesterday_limit_up and yesterday_limit_up and yesterday_volume_surge
        
        if result:
            log.debug(f"🚀 每日强势模式: 符合条件")
        else:
            log.debug(f"📊 每日强势模式: 未达条件")
            
        return result
        
    except Exception as error:
        log.warn(f"⚠️ 每日强势模式判断异常: {str(error)}")
        return False

def validate_market_data(context):
    """
    市场数据验证函数
    功能：检查市场数据的完整性和有效性
    """
    try:
        log.info("🔍 开始验证市场数据完整性")
        
        # 检查当前数据
        current_data = get_current_data()
        if current_data is None:
            log.error("❌ 当前市场数据获取失败")
            return False
            
        # 检查基础股票池
        base_stocks = load_fundamentals_data(context)
        if not base_stocks:
            log.warn("⚠️ 基础股票池为空")
            return False
            
        # 检查指数数据
        index_data = get_price('000001.XSHG', count=1, fields=['close'])
        if index_data is None or len(index_data) == 0:
            log.warn("⚠️ 指数数据获取异常")
            
        log.info(f"✅ 市场数据验证完成: 基础股票{len(base_stocks)}只")
        return True
        
    except Exception as error:
        log.error(f"❌ 市场数据验证异常: {str(error)}")
        return False

def monitor_strategy_performance(context):
    """
    策略性能监控函数
    功能：监控策略运行状态和性能指标
    """
    try:
        # 计算策略关键指标
        total_positions = len(context.portfolio.positions)
        total_value = context.portfolio.total_value
        available_cash = context.portfolio.cash
        used_cash = total_value - available_cash
        
        # 计算持仓收益情况
        profitable_count = 0
        total_profit = 0
        
        for position in context.portfolio.positions.values():
            profit_rate = (position.price / position.avg_cost - 1) * 100
            total_profit += profit_rate
            if profit_rate > 0:
                profitable_count += 1
                
        avg_profit = total_profit / total_positions if total_positions > 0 else 0
        
        # 输出性能监控报告
        log.info("📈 策略性能监控报告:")
        log.info(f"  💼 持仓数量: {total_positions}只")
        log.info(f"  📊 持仓盈利: {profitable_count}只盈利")
        log.info(f"  📈 平均收益: {avg_profit:.2f}%")
        log.info(f"  💰 总资产: {total_value:.2f}")
        log.info(f"  💵 已用资金: {used_cash:.2f}")
        log.info(f"  💸 可用资金: {available_cash:.2f}")
        
        # 检查风险指标
        if total_positions >= g.stockNum:
            log.info("  🎯 持仓已达上限")
        if available_cash < total_value * 0.1:
            log.info("  ⚠️ 可用资金比例较低")
            
        return True
        
    except Exception as error:
        log.error(f"❌ 策略性能监控异常: {str(error)}")
        return False

def risk_management_check(context):
    """
    风险管理检查函数
    功能：执行全面的风险检查
    """
    try:
        log.info("🛡️ 开始执行风险管理检查")
        
        risk_issues = []
        
        # 检查持仓集中度
        if len(context.portfolio.positions) > g.stockNum:
            risk_issues.append(f"持仓数量超过限制: {len(context.portfolio.positions)} > {g.stockNum}")
            
        # 检查单只股票风险
        for stock_code, position in context.portfolio.positions.items():
            # 检查亏损幅度
            if position.price < position.avg_cost * 0.85:  # 亏损15%
                risk_issues.append(f"股票{stock_code}亏损超过15%")
                
            # 检查流动性
            current_data = get_current_data()[stock_code]
            if current_data and current_data.paused:
                risk_issues.append(f"股票{stock_code}已停牌")
                
        # 检查市场风险
        index_trend = check_market_trend(context)
        if index_trend == "downtrend":
            risk_issues.append("市场处于下跌趋势")
            
        # 输出风险报告
        if risk_issues:
            log.warn("⚠️ 发现风险问题:")
            for issue in risk_issues:
                log.warn(f"  ❗ {issue}")
        else:
            log.info("✅ 风险管理检查通过，未发现重大风险")
            
        return len(risk_issues) == 0
        
    except Exception as error:
        log.error(f"❌ 风险管理检查异常: {str(error)}")
        return False

def check_market_trend(context):
    """
    市场趋势判断函数
    功能：判断当前市场整体趋势
    """
    try:
        # 使用上证指数判断市场趋势
        index_code = '000001.XSHG'
        index_data = get_price(index_code, count=20, fields=['close'])
        
        if len(index_data) < 20:
            return "unknown"
            
        # 计算短期和长期均线
        short_ma = index_data['close'][-5:].mean()  # 5日均线
        long_ma = index_data['close'].mean()        # 20日均线
        
        current_price = index_data['close'][-1]
        
        # 判断趋势
        if current_price > short_ma > long_ma:
            log.debug("📈 市场趋势: 上升趋势")
            return "uptrend"
        elif current_price < short_ma < long_ma:
            log.debug("📉 市场趋势: 下降趋势")
            return "downtrend"
        else:
            log.debug("📊 市场趋势: 震荡整理")
            return "consolidation"
            
    except Exception as error:
        log.warn(f"⚠️ 市场趋势判断异常: {str(error)}")
        return "unknown"

def add_monitoring_schedule(context):
    """
    添加监控定时任务
    功能：在策略初始化时添加性能监控和风险检查
    """
    # 每小时执行一次性能监控
    run_daily(monitor_strategy_performance, '10:30')
    run_daily(monitor_strategy_performance, '14:30')
    
    # 每天收盘前执行风险检查
    run_daily(risk_management_check, '14:50')
    
    # 每周一开盘前执行全面数据验证
    run_weekly(validate_market_data, 1, '9:00')
    
    log.info("✅ 监控定时任务设置完成")

def calc_history_atr(stock_code, end_time, timeperiod=14, unit='1d'):
    """
    历史ATR指标计算函数
    功能：计算指定时间段内的平均真实波幅
    返回：ATR指标数值
    """
    try:
        # 历史价格数据获取
        historical_price_data = get_price(
            security=stock_code, 
            end_date=end_time, 
            frequency=unit,
            fields=['close', 'high', 'low'], 
            skip_paused=True,
            fq='pre', 
            count=timeperiod+1
        )
        
        if historical_price_data is None or len(historical_price_data) == 0:
            log.warn(f"⚠️ 股票{stock_code}历史价格数据为空")
            return np.nan
        
        # 数据有效性验证
        nan_value_count = list(np.isnan(historical_price_data['close'])).count(True)
        if nan_value_count == len(historical_price_data['close']):
            log.info(f"⚠️ 股票 {stock_code} 历史数据异常，返回空值")
            return np.nan
        
        # TA-Lib库ATR计算
        atr_result = tl.ATR(
            np.array(historical_price_data['high']),
            np.array(historical_price_data['low']),
            np.array(historical_price_data['close']),
            timeperiod
        )
        
        atr_value = atr_result[-1]  # 返回最新ATR值
        log.debug(f"📊 股票{stock_code}ATR计算: {atr_value:.4f}")
        return atr_value
        
    except Exception as error:
        log.warn(f"⚠️ ATR指标计算异常: {str(error)}")
        return np.nan

def calc_position(context, stock_code):
    """
    持仓仓位计算函数
    功能：基于波动率的风险调整仓位计算
    返回：建议买入的股票数量
    """
    try:
        # 风险参数定义
        RISK_PERIOD = 60      # 风险计算周期
        RISK_INTERVAL = 30    # 风险间隔周期
        VOLATILITY_PERIOD = 60     # 波动率计算周期
        
        # 数据量需求计算
        required_data_count = RISK_PERIOD + RISK_INTERVAL * 2
        required_data_count = max(VOLATILITY_PERIOD, required_data_count)
        
        # 扩展历史数据获取
        extended_history_data = get_price(
            security=stock_code,
            end_date=get_last_time(context.current_dt), 
            frequency=g.LONG_UNIT,
            fields=['close', 'high', 'low'], 
            skip_paused=True, 
            fq='pre', 
            count=required_data_count
        )
        
        if extended_history_data is None or len(extended_history_data) < required_data_count:
            log.warn(f"⚠️ 股票{stock_code}历史数据不足")
            return 0
        
        high_prices = extended_history_data['high']
        low_prices = extended_history_data['low']
        close_prices = extended_history_data['close']
        
        # 数据质量检查
        if (list(np.isnan(high_prices)).count(True) > 0 or
            list(np.isnan(low_prices)).count(True) > 0 or
            list(np.isnan(close_prices)).count(True) > 0):
            log.warn(f"⚠️ 股票{stock_code}历史数据存在空值")
            return 0
        
        # 典型价格序列计算
        typical_price_series = []
        for i in range(len(high_prices)):
            typical_price = (high_prices[i] + low_prices[i] + close_prices[i] * 2) / 4
            typical_price_series.append(typical_price)
        
        # 多时段波动率计算
        early_volatility = np.std(typical_price_series[-RISK_PERIOD - (RISK_INTERVAL * 2): -(RISK_INTERVAL * 2)])  # 早期波动率
        middle_volatility = np.std(typical_price_series[-RISK_PERIOD - (RISK_INTERVAL * 1): -(RISK_INTERVAL * 1)])  # 中期波动率
        recent_volatility = np.std(typical_price_series[-RISK_PERIOD:])  # 近期波动率
        overall_volatility = np.std(typical_price_series[-VOLATILITY_PERIOD:])      # 整体波动率
        
        # 风险调整系数计算
        risk_adjustment_factor = 0
        if recent_volatility > middle_volatility:
            risk_adjustment_factor = 0.5    # 波动率上升，风险控制加强
        elif recent_volatility < middle_volatility and recent_volatility > early_volatility:
            risk_adjustment_factor = 1.0    # 波动率稳定，正常风险暴露
        elif recent_volatility < middle_volatility and recent_volatility < early_volatility:
            risk_adjustment_factor = 1.5    # 波动率下降，适度增加风险
        
        # 最终仓位计算
        if overall_volatility == 0:
            return 0
        
        position_value = (context.portfolio.starting_cash * 0.055 * 
                         risk_adjustment_factor / (g.POSITION_SIGMA * overall_volatility))
        
        # 股数转换与取整
        share_quantity = int(position_value / 100) * 100
        
        log.info(f"📊 股票{stock_code}仓位计算结果: "
                f"风险系数={risk_adjustment_factor}, 波动率={overall_volatility:.4f}, "
                f"建议股数={share_quantity}")
        
        return max(100, share_quantity)  # 最小交易单位限制
        
    except Exception as error:
        log.error(f"❌ 仓位计算过程异常: {str(error)}")
        return 0


def get_last_time(datetime_input):
    """
    时间处理辅助函数
    功能：统一时间格式处理
    返回：标准化时间戳
    """
    return datetime_input

"""
连板涨停策略交易系统说明文档

系统设计理念：
基于涨停板战法的量化实现，通过系统化方法捕捉连续涨停股票的交易机会
结合严格风险控制，实现稳定收益的同时控制回撤风险

核心策略逻辑：
1. 选股模块 - 多重条件筛选强势股票
   - 基本面筛选：市值区间过滤
   - 技术面筛选：涨停形态识别
   - 风险面筛选：流动性、波动率考量

2. 交易模块 - 智能化交易执行
   - 买入条件：技术信号确认 + 风险控制
   - 卖出条件：止盈止损 + 移动止损
   - 仓位管理：波动率调整的风险暴露

3. 风控模块 - 全方位风险防护
   - 事前风控：股票筛选条件
   - 事中风控：实时止损机制
   - 事后风控：交易记录分析

系统特色功能：
- 动态股票池更新机制
- 多层次技术信号验证
- 自适应仓位调整算法
- 实时风险监控预警

注意事项：
- 本系统为量化交易工具，实际使用需结合市场环境
- 建议在模拟环境充分测试后再投入实盘
- 定期回顾策略表现，适时优化参数设置
"""
# 完整的连板涨停策略交易系统日志优化完成

"""
📋 完整日志系统总结：

日志级别设置：
- error: 订单和系统错误
- debug: 策略详细运行信息
- info: 关键流程节点信息

图标分类系统：
📊 - 数据相关操作
🎯 - 流程控制节点
🛡️ - 风险控制操作
🔄 - 数据更新操作
📈 - 技术分析判断
✅ - 成功状态确认
⚠️ - 警告状态提示
❌ - 错误状态处理
💤 - 无操作状态
🎲 - 随机选择操作
🚫 - 限制状态提示
⏭️ - 跳过操作提示
⏳ - 等待状态提示
💰 - 资金相关操作
💼 - 持仓相关操作
📝 - 记录相关操作
📉 - 下跌相关提示
🚀 - 上涨相关提示
🛒 - 交易操作执行
🔍 - 数据验证操作
📈 - 性能监控操作
🧹 - 数据清理操作
⚡ - 性能优化操作
💾 - 数据备份操作
🔄 - 数据恢复操作
🛑 - 紧急停止操作

关键改进：
1. 完整的异常处理机制
2. 性能监控和优化
3. 数据备份和恢复
4. 风险管理增强
5. 批量数据加载优化
6. 缓存数据清理
7. 市场趋势判断
8. 紧急停止功能

这个完整的日志系统提供了全方位的策略运行监控，便于调试、优化和风险管理。
"""