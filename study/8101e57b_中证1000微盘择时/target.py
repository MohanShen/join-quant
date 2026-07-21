# Clone from JoinQuant
# postId: 8101e57b409625161bee7d845a97b60c
# backtestId: 13faa4f65e72f3377d6b302def175270
# title: 中证1000交易策略——低风偏爱好者食用

# 微盘股市场择时策略
# 基于全市场市值最小100只股票的相对位置、涨跌幅、均线等指标判断市场择时

from jqdata import *
import numpy as np
import pandas as pd
import talib

def initialize(context):
    set_benchmark('000852.XSHG')  # 中证1000作为基准
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, 
                             close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    log.set_level('order', 'error')
    
    # 全局变量
    g.micro_cap_count = 100  # 微盘股数量
    g.timing_history = []  # 择时信号历史
    g.position_pct = 0  # 当前仓位百分比
    
    # 每日计算择时信号
    run_daily(calculate_timing_signal, '9:10')
    run_daily(adjust_position, '9:35')
    run_daily(record_timing_data, '15:00')


def get_micro_cap_stocks(context):
    """获取全市场市值最小的100只微盘股"""
    yesterday = context.previous_date
    
    # 获取全A股
    all_stocks = list(get_all_securities(['stock'], date=yesterday).index)
    
    # 过滤
    all_stocks = filter_st_stock(all_stocks)
    all_stocks = filter_kcbj_stock(all_stocks)
    all_stocks = filter_paused_stock(all_stocks)
    all_stocks = filter_new_stock(context, all_stocks)
    
    # 按市值排序，取最小100只
    q = query(
        valuation.code,
        valuation.market_cap
    ).filter(
        valuation.code.in_(all_stocks)
    ).order_by(
        valuation.market_cap.asc()
    ).limit(g.micro_cap_count)
    
    df = get_fundamentals(q, date=yesterday)
    
    if df is None or df.empty:
        return []
    
    return list(df['code'].values)


def calculate_timing_signal(context):
    """
    计算微盘股市场择时信号
    
    核心指标：
    1. 相对位置：当前价格相对于60日高低点的位置
    2. 周期涨跌幅：5日、10日、20日涨跌幅
    3. 均线系统：5日、10日、20日均线排列
    4. 市场宽度：100只微盘股中在10日线上方的占比
    5. 成交量：相对于20日均量的放大倍数
    """
    try:
        log.info("=" * 80)
        log.info(f"【微盘股市场择时分析】{context.previous_date}")
        log.info("=" * 80)
        
        # 获取微盘股池
        micro_stocks = get_micro_cap_stocks(context)
        
        if not micro_stocks:
            log.warning("未获取到微盘股数据")
            g.position_pct = 0
            return
        
        log.info(f"微盘股数量: {len(micro_stocks)}")
        
        # 获取价格数据（60天用于计算相对位置）
        df_price = get_price(
            micro_stocks,
            end_date=context.previous_date,
            count=61,
            frequency='daily',
            fields=['close', 'high', 'low', 'volume'],
            panel=False
        )
        
        if df_price.empty:
            log.warning("未获取到价格数据")
            g.position_pct = 0
            return
        
        # 计算各项指标
        signal_data = []
        
        for stock in micro_stocks:
            stock_data = df_price[df_price['code'] == stock].sort_values('time')
            
            if len(stock_data) < 61:
                continue
            
            closes = stock_data['close'].values
            highs = stock_data['high'].values
            lows = stock_data['low'].values
            volumes = stock_data['volume'].values
            
            current_price = closes[-1]
            
            # 1. 相对位置（0-100）
            high_60 = np.max(highs)
            low_60 = np.min(lows)
            if high_60 > low_60:
                relative_position = (current_price - low_60) / (high_60 - low_60) * 100
            else:
                relative_position = 50
            
            # 2. 周期涨跌幅
            return_5d = (closes[-1] / closes[-6] - 1) * 100 if len(closes) >= 6 else 0
            return_10d = (closes[-1] / closes[-11] - 1) * 100 if len(closes) >= 11 else 0
            return_20d = (closes[-1] / closes[-21] - 1) * 100 if len(closes) >= 21 else 0
            
            # 3. 均线系统
            ma5 = np.mean(closes[-5:])
            ma10 = np.mean(closes[-10:])
            ma20 = np.mean(closes[-20:])
            
            above_ma5 = 1 if current_price > ma5 else 0
            above_ma10 = 1 if current_price > ma10 else 0
            above_ma20 = 1 if current_price > ma20 else 0
            ma_alignment = 1 if ma5 > ma10 > ma20 else 0  # 多头排列
            
            # 4. 成交量
            avg_volume_20 = np.mean(volumes[-20:])
            volume_ratio = volumes[-1] / avg_volume_20 if avg_volume_20 > 0 else 1
            
            signal_data.append({
                'code': stock,
                'relative_position': relative_position,
                'return_5d': return_5d,
                'return_10d': return_10d,
                'return_20d': return_20d,
                'above_ma5': above_ma5,
                'above_ma10': above_ma10,
                'above_ma20': above_ma20,
                'ma_alignment': ma_alignment,
                'volume_ratio': volume_ratio
            })
        
        if not signal_data:
            log.warning("未计算出有效信号")
            g.position_pct = 0
            return
        
        df_signal = pd.DataFrame(signal_data)
        
        # ===== 综合择时信号计算 =====
        
        # 指标1：平均相对位置（0-100）
        avg_position = df_signal['relative_position'].mean()
        
        # 指标2：平均涨跌幅
        avg_return_5d = df_signal['return_5d'].mean()
        avg_return_10d = df_signal['return_10d'].mean()
        avg_return_20d = df_signal['return_20d'].mean()
        
        # 指标3：市场宽度（在10日线上方的占比）
        market_breadth_10 = df_signal['above_ma10'].mean() * 100
        
        # 指标4：多头排列占比
        ma_alignment_pct = df_signal['ma_alignment'].mean() * 100
        
        # 指标5：平均成交量比
        avg_volume_ratio = df_signal['volume_ratio'].mean()
        
        # ===== 打印分析结果 =====
        log.info(f"【相对位置】平均: {avg_position:.1f}% (0=底部, 100=顶部)")
        log.info(f"【周期涨跌幅】5日: {avg_return_5d:.2f}%, 10日: {avg_return_10d:.2f}%, 20日: {avg_return_20d:.2f}%")
        log.info(f"【市场宽度】10日线上方: {market_breadth_10:.1f}%")
        log.info(f"【均线排列】多头排列: {ma_alignment_pct:.1f}%")
        log.info(f"【成交量】相对20日均量: {avg_volume_ratio:.2f}倍")
        
        # ===== 择时信号判断 =====
        position_score = 0  # 仓位评分（0-100）
        
        # 规则1：相对位置（权重30%）
        if avg_position < 20:
            position_score += 30  # 底部区域，满分
            log.info("✅ 相对位置: 底部区域(+30分)")
        elif avg_position < 40:
            position_score += 20
            log.info("✅ 相对位置: 偏低区域(+20分)")
        elif avg_position < 60:
            position_score += 10
            log.info("⚠️ 相对位置: 中性区域(+10分)")
        elif avg_position < 80:
            position_score += 5
            log.info("⚠️ 相对位置: 偏高区域(+5分)")
        else:
            position_score += 0
            log.info("❌ 相对位置: 顶部区域(+0分)")
        
        # 规则2：市场宽度（权重30%）
        if market_breadth_10 > 70:
            position_score += 30
            log.info("✅ 市场宽度: 强势(+30分)")
        elif market_breadth_10 > 50:
            position_score += 20
            log.info("✅ 市场宽度: 中性偏强(+20分)")
        elif market_breadth_10 > 30:
            position_score += 10
            log.info("⚠️ 市场宽度: 中性偏弱(+10分)")
        else:
            position_score += 0
            log.info("❌ 市场宽度: 弱势(+0分)")
        
        # 规则3：短期动量（权重20%）
        if avg_return_5d > 3:
            position_score += 20
            log.info("✅ 短期动量: 强势(+20分)")
        elif avg_return_5d > 0:
            position_score += 10
            log.info("✅ 短期动量: 偏强(+10分)")
        elif avg_return_5d > -3:
            position_score += 5
            log.info("⚠️ 短期动量: 偏弱(+5分)")
        else:
            position_score += 0
            log.info("❌ 短期动量: 弱势(+0分)")
        
        # 规则4：均线排列（权重10%）
        if ma_alignment_pct > 60:
            position_score += 10
            log.info("✅ 均线排列: 多头主导(+10分)")
        elif ma_alignment_pct > 40:
            position_score += 5
            log.info("⚠️ 均线排列: 中性(+5分)")
        else:
            position_score += 0
            log.info("❌ 均线排列: 空头主导(+0分)")
        
        # 规则5：成交量（权重10%）
        if avg_volume_ratio > 1.5:
            position_score += 10
            log.info("✅ 成交量: 放量(+10分)")
        elif avg_volume_ratio > 1.0:
            position_score += 5
            log.info("⚠️ 成交量: 正常(+5分)")
        else:
            position_score += 0
            log.info("❌ 成交量: 缩量(+0分)")
        
        # ===== 仓位决策 =====
        if position_score >= 80:
            g.position_pct = 1.0
            signal_desc = "🚀 强烈看多"
        elif position_score >= 60:
            g.position_pct = 0.7
            signal_desc = "📈 看多"
        elif position_score >= 40:
            g.position_pct = 0.5
            signal_desc = "➖ 中性"
        elif position_score >= 20:
            g.position_pct = 0.3
            signal_desc = "📉 看空"
        else:
            g.position_pct = 0.0
            signal_desc = "🚨 强烈看空"
        
        log.info("=" * 80)
        log.info(f"【综合评分】{position_score}/100 → {signal_desc} → 建议仓位: {g.position_pct*100:.0f}%")
        log.info("=" * 80)
        
        # 记录到全局变量
        g.timing_history.append({
            'date': context.previous_date,
            'score': position_score,
            'position_pct': g.position_pct,
            'avg_position': avg_position,
            'market_breadth': market_breadth_10,
            'return_5d': avg_return_5d,
            'return_10d': avg_return_10d
        })
        
        # 记录到回测图表
        record(择时评分=position_score)
        record(建议仓位=g.position_pct * 100)
        record(相对位置=avg_position)
        record(市场宽度=market_breadth_10)
        
    except Exception as e:
        log.error(f"计算择时信号失败: {str(e)}")
        import traceback
        log.error(traceback.format_exc())
        g.position_pct = 0


def adjust_position(context):
    """根据择时信号调整仓位"""
    try:
        target_value = context.portfolio.total_value * g.position_pct
        
        # 使用中证1000ETF作为标的
        etf = '159845.XSHE'  # 中证1000ETF
        
        current_data = get_current_data()
        
        # 检查是否停牌
        if current_data[etf].paused:
            log.warning(f"{etf} 停牌，无法调仓")
            return
        
        # 当前持仓市值
        current_value = context.portfolio.positions[etf].value if etf in context.portfolio.positions else 0
        
        # 计算差额
        diff = abs(target_value - current_value)
        
        # 如果差额超过5%才调仓（避免频繁交易）
        if diff > context.portfolio.total_value * 0.05:
            order_target_value(etf, target_value)
            log.info(f"调仓: {etf} → 目标市值: {target_value:.2f}元 (仓位{g.position_pct*100:.0f}%)")
        
    except Exception as e:
        log.error(f"调仓失败: {str(e)}")


def record_timing_data(context):
    """记录择时数据（用于盘后分析）"""
    if g.timing_history:
        latest = g.timing_history[-1]
        log.info(f"今日择时: 评分{latest['score']}, 仓位{latest['position_pct']*100:.0f}%")


# ===== 辅助函数 =====

def filter_st_stock(stock_list):
    """过滤ST股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


def filter_kcbj_stock(stock_list):
    """过滤科创板、北交所"""
    return [stock for stock in stock_list 
            if not (stock[0] in {'4', '8'} or stock[:2] == '68' or stock[0] == '3')]


def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def filter_new_stock(context, stock_list):
    """过滤次新股（上市不足1年）"""
    yesterday = context.previous_date
    return [stock for stock in stock_list 
            if (yesterday - get_security_info(stock).start_date).days >= 375]

