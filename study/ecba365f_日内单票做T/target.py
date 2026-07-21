# Clone from JoinQuant
# postId: ecba365f86232c7d8eebad8cab53ddac
# backtestId: 7ea8c4eabf18fa9344cf1ee0f0143ed9
# title: 日内单票做T策略

from jqdata import *
import numpy as np
import pandas as pd

# 初始化函数
def initialize(context): 
    # 1. 设定股票标的
    g.security = '000880.XSHE' 
    
    # 2. 设定沪深300作为基准
    set_benchmark('000300.XSHG') 
    
    # 3. 开启动态复权模式
    set_option('use_real_price', True) 
    
    # 4. 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    # 5. 策略参数设置
    g.trade_ratio = 1.0 / 3   # 每次交易仓位比例：1/3仓位滚动操作
    g.buy_threshold = -0.02   # 买入阈值：跌幅超过2%
    g.sell_threshold = 0.03   # 卖出阈值：涨幅超过3%
    g.position_ratio = 0.7    # 底仓占总资金的比例（70%作为底仓）
    
    # 6. 添加调试标志
    g.debug = True
    g.initialized = False      # 标记是否已完成初始化建仓
    g.init_attempted = False   # 标记是否已经尝试过建仓
    
    # 7. 记录上次交易时间，避免频繁交易
    g.last_trade_date = None
    
    # 8. 运行函数
    # 使用1分钟周期运行
    run_daily(market_open, time='every_bar')
    
    # 9. 开盘前运行，检查持仓
    run_daily(before_market_open, time='before_open')
    
    # 10. 收盘后运行，打印总结
    run_daily(after_market_close, time='after_close')
    
    # 11. 记录第一个交易日
    g.first_day = True

def before_market_open(context):
    """开盘前运行，检查账户状态"""
    security = g.security
    position = context.portfolio.positions.get(security)
    
    log.info("="*50)
    log.info("开盘前检查 - 日期: %s" % context.current_dt.strftime('%Y-%m-%d'))
    log.info("账户总资产: %.2f" % context.portfolio.total_value)
    log.info("可用现金: %.2f" % context.portfolio.available_cash)
    
    if position and position.total_amount > 0:
        log.info("当前持仓: %d股" % position.total_amount)
        log.info("可卖数量: %d股" % position.closeable_amount)
        log.info("持仓成本: %.2f" % position.avg_cost)
        log.info("持仓市值: %.2f" % (position.price * position.total_amount))
    else:
        log.info("当前无持仓")
    
    log.info("="*50)

def market_open(context):
    security = g.security
    
    try:
        # 获取当前日期和时间
        current_date = context.current_dt.strftime('%Y-%m-%d')
        current_time = context.current_dt.strftime('%H:%M')
        
        # 1. 获取昨日收盘价
        close_data = attribute_history(security, 2, '1d', ['close'])
        if len(close_data['close']) < 2:
            log.debug("获取昨日收盘价失败")
            return
        close_last = close_data['close'][-2]
        
        # 2. 获取当前最新价格 - 使用多种方法确保获取到数据
        current_price = None
        
        # 方法1：使用get_current_data()
        try:
            current_data = get_current_data()
            if security in current_data:
                current_price = current_data[security].last_price
                if current_price is not None and not np.isnan(current_price) and current_price > 0:
                    if g.debug and current_time == '09:31':
                        log.debug("方法1获取价格成功: %.2f" % current_price)
        except:
            pass
        
        # 方法2：使用attribute_history获取最新分钟数据
        if current_price is None or current_price == 0 or np.isnan(current_price):
            try:
                minute_data = attribute_history(security, 1, '1m', ['close'])
                if len(minute_data) > 0:
                    current_price = minute_data['close'][-1]
                    if current_price > 0 and g.debug and current_time == '09:31':
                        log.debug("方法2获取价格成功: %.2f" % current_price)
            except:
                pass
        
        # 方法3：使用get_price获取实时价格
        if current_price is None or current_price == 0 or np.isnan(current_price):
            try:
                price_data = get_price(security, end_date=context.current_dt, frequency='1m', fields=['close'], skip_paused=False, fq='pre', count=1)
                if price_data is not None and len(price_data) > 0:
                    current_price = price_data['close'][-1]
                    if current_price > 0 and g.debug and current_time == '09:31':
                        log.debug("方法3获取价格成功: %.2f" % current_price)
            except:
                pass
        
        # 如果所有方法都失败，则退出
        if current_price is None or current_price == 0 or np.isnan(current_price):
            if current_time == '09:31':  # 只在开盘后第一分钟提示
                log.debug("所有方法获取当前价格失败")
            return
        
        # 3. 获取账户信息
        position = context.portfolio.positions.get(security)
        total_value = context.portfolio.total_value
        available_cash = context.portfolio.available_cash
        
        total_shares = position.total_amount if position else 0
        closeable_shares = position.closeable_amount if position else 0
        
        # 4. 计算当前涨跌幅
        pct_change = (current_price - close_last) / close_last
        
        # 5. 初始化建仓 - 修改这里，移除时间限制，使用更可靠的逻辑
        if not g.initialized and not g.init_attempted:
            g.init_attempted = True  # 标记已尝试建仓，避免重复尝试
            log.info("="*50)
            log.info("【开始初始化建仓】")
            log.info("当前价格: %.2f" % current_price)
            log.info("可用现金: %.2f" % available_cash)
            
            # 计算建仓金额：总资产的70%
            init_buy_value = total_value * g.position_ratio
            min_cost = current_price * 100
            
            if init_buy_value > min_cost and available_cash > min_cost:
                # 计算可买股数（向下取整到100股）
                shares_to_buy = int(init_buy_value / current_price / 100) * 100
                
                # 确保不超过可用现金
                max_shares_by_cash = int(available_cash / current_price / 100) * 100
                shares_to_buy = min(shares_to_buy, max_shares_by_cash)
                
                if shares_to_buy >= 100:
                    log.info("建仓金额: %.2f元" % (shares_to_buy * current_price))
                    log.info("建仓数量: %d股" % shares_to_buy)
                    
                    # 执行买入
                    order(security, shares_to_buy)
                    g.initialized = True
                    g.last_trade_date = current_date
                    log.info("【建仓成功】买入 %d股，价格: %.2f" % (shares_to_buy, current_price))
                else:
                    log.warning("建仓股数不足100股: %d" % shares_to_buy)
                    log.warning("可能需要更多资金或股价过高")
            else:
                log.warning("建仓资金不足买1手，需要%.2f元" % min_cost)
                log.warning("可用现金: %.2f" % available_cash)
            log.info("="*50)
            
            # 建仓后立即返回，避免当天继续交易
            return
        
        # 6. 如果还没初始化完成，打印状态并返回
        if not g.initialized:
            if current_time == '09:31' or current_time == '10:00':
                log.debug("等待初始化建仓... 尝试状态: %s" % ("已尝试" if g.init_attempted else "未尝试"))
            return
        
        # 7. 调试信息
        if current_time.endswith(':00') or current_time.endswith(':30'):  # 每半小时打印一次
            log.debug("时间: %s, 价格: %.2f, 昨收: %.2f, 涨跌幅: %.2f%%, 持仓: %d, 现金: %.2f" % 
                     (current_time, current_price, close_last, pct_change*100, total_shares, available_cash))
        
        # 8. 检查是否同一交易日已经交易过（避免一天多次交易）
        if g.last_trade_date == current_date:
            if g.debug and current_time == '09:31':
                log.debug("本交易日已交易过，跳过")
            return
        
        # ========== 卖出逻辑 (高抛) ==========
        if pct_change >= g.sell_threshold and closeable_shares > 0:
            log.info("="*30)
            log.info("【触发卖出条件】")
            log.info("当前涨幅: %.2f%% (阈值: %.2f%%)" % (pct_change*100, g.sell_threshold*100))
            log.info("可卖持仓: %d股" % closeable_shares)
            
            # 计算卖出数量：取总仓位的1/3，向下取整到100股
            sell_amount = int(total_shares * g.trade_ratio / 100) * 100
            sell_amount = min(sell_amount, closeable_shares)  # 确保不超过可卖数量
            
            if sell_amount >= 100:
                log.info("准备卖出: %d股" % sell_amount)
                order(security, -sell_amount)
                g.last_trade_date = current_date
                log.info("【高抛成功】卖出: %d股, 价格: %.2f, 金额: %.2f" % 
                        (sell_amount, current_price, sell_amount * current_price))
            else:
                log.info("卖出数量不足100股: %d" % sell_amount)
            log.info("="*30)

        # ========== 买入逻辑 (低吸) ==========
        elif pct_change <= g.buy_threshold and available_cash > 0:
            log.info("="*30)
            log.info("【触发买入条件】")
            log.info("当前跌幅: %.2f%% (阈值: %.2f%%)" % (pct_change*100, g.buy_threshold*100))
            log.info("可用现金: %.2f" % available_cash)
            
            # 计算买入金额：目标买入总资产的1/3
            target_buy_value = total_value * g.trade_ratio
            
            # 确保不超过可用现金
            actual_buy_value = min(target_buy_value, available_cash)
            
            # 预留一点现金防滑点，实际买入95%
            actual_buy_value = actual_buy_value * 0.95
            
            # 计算最少需要多少钱买1手（100股）
            min_cost = current_price * 100
            
            if actual_buy_value > min_cost:
                # 计算实际可买股数（向下取整到100股）
                shares_to_buy = int(actual_buy_value / current_price / 100) * 100
                if shares_to_buy >= 100:
                    log.info("准备买入: %d股" % shares_to_buy)
                    order(security, shares_to_buy)
                    g.last_trade_date = current_date
                    log.info("【低吸成功】买入: %d股, 价格: %.2f, 金额: %.2f" % 
                            (shares_to_buy, current_price, shares_to_buy * current_price))
            else:
                log.info("买入金额不足买1手: %.2f < %.2f" % (actual_buy_value, min_cost))
            log.info("="*30)
        
        else:
            # 打印未触发交易的原因
            if g.debug and (current_time == '09:31' or current_time == '10:00' or current_time == '14:30'):
                if pct_change >= g.sell_threshold:
                    if closeable_shares <= 0:
                        log.debug("未卖出原因: 涨幅%.2f%%达标但无可用持仓" % (pct_change*100))
                elif pct_change <= g.buy_threshold:
                    if available_cash <= 0:
                        log.debug("未买入原因: 跌幅%.2f%%达标但现金不足" % (pct_change*100))
                else:
                    log.debug("未交易: 当前涨跌幅%.2f%%未达到阈值(需涨%.0f%%或跌%.0f%%)" % 
                            (pct_change*100, g.sell_threshold*100, abs(g.buy_threshold*100)))

    except Exception as e: 
        log.error("策略运行出错: %s" % str(e))
        import traceback
        log.error(traceback.format_exc())

def after_market_close(context):
    """收盘后打印总结"""
    security = g.security
    position = context.portfolio.positions.get(security)
    
    log.info("="*50)
    log.info("收盘总结 - %s" % context.current_dt.strftime('%Y-%m-%d'))
    log.info("账户总资产: %.2f" % context.portfolio.total_value)
    log.info("可用现金: %.2f" % context.portfolio.available_cash)
    
    if position and position.total_amount > 0:
        # 获取当前价格
        current_data = get_current_data()
        if security in current_data:
            current_price = current_data[security].last_price
            if current_price > 0:
                log.info("最终持仓: %d股" % position.total_amount)
                log.info("持仓市值: %.2f" % (current_price * position.total_amount))
                log.info("持仓成本: %.2f" % position.avg_cost)
                log.info("浮动盈亏: %.2f" % ((current_price - position.avg_cost) * position.total_amount))
    
    log.info("初始化状态: %s" % ("已完成" if g.initialized else "未完成"))
    log.info("尝试建仓: %s" % ("已尝试" if g.init_attempted else "未尝试"))
    log.info("今日交易次数: %s" % ("有交易" if g.last_trade_date == context.current_dt.strftime('%Y-%m-%d') else "无交易"))
    log.info("="*50)