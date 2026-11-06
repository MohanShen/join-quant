# Clone from JoinQuant
# postId: 990e2a594c52ef2c8f7022c506dcc3c0
# backtestId: e5410a22e0caa373a2ebd515bfa6cc82
# title: 期货大赛冠军丁伟峰期货策略思考

# 2万资金多品种日内高频轮动策略 (高爆发放纵利润版)
import numpy as np
from jqdata import *

def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(1))

    set_subportfolios([
        SubPortfolioConfig(cash=context.portfolio.starting_cash, type='futures')
    ])
    set_option('futures_margin_rate', 0.12)
    set_order_cost(OrderCost(
        open_commission=0.0001, close_commission=0.0001,
        close_today_commission=0.0001, min_commission=0
    ), type='futures')

    # ======== 扩充品种池（加入波动之王：纯碱SA、豆粕M、PTA） ========
    g.symbols = ['RB', 'MA', 'FG', 'SA', 'M', 'TA'] 
    
    g.trading_state = {}
    for s in g.symbols:
        if s in ['RB']: suffix = '.XSGE'
        elif s in ['MA', 'FG', 'TA']: suffix = '.XZCE'
        elif s in ['SA']: suffix = '.XZCE'
        elif s in ['M']: suffix = '.XDCE'
        
        g.trading_state[s] = {
            'continuous': s + '9999' + suffix,
            'position_side': 0,    
            'contract': None,      
            'entry_price': 0,
            'stop_price': 0,
            'half_closed': False # 记录是否已经平过半仓
        }

    g.signal_freq = '5m'
    g.breakout_lookback = 3      
    g.stop_ticks = 15            # 初始止损收紧到15跳
    g.breakeven_ticks = 15       # 赚15跳推保本
    g.half_close_ticks = 40      # 赚40跳平一半
    g.trail_stop_ticks = 20      # 剩下半仓，回撤20跳止盈
    
    g.daily_pnl = 0
    g.max_daily_loss_pct = 0.02  # 单日亏400元停手
    g.max_trades_per_day = 10    # 每天最多开10次（多品种轮动需要高频）
    g.daily_trades = 0
    g.today = None

    run_daily(reset_daily, time='09:00')
    run_daily(force_close_all, time='14:55')

def reset_daily(context):
    g.daily_pnl = 0
    g.daily_trades = 0
    g.today = context.current_dt.date()

def force_close_all(context):
    for s in g.symbols:
        state = g.trading_state[s]
        if state['position_side'] != 0 and state['contract']:
            side = 'long' if state['position_side'] == 1 else 'short'
            order_target(state['contract'], 0, side=side)
            state['position_side'] = 0
            log.info(f'[强平] 平仓 {s} @{context.current_dt}')

def handle_data(context, data):
    now = context.current_dt
    if g.today != now.date():
        reset_daily(context)

    t = now.time()
    in_morning = (t.hour == 9 and t.minute >= 15) or (t.hour == 10) or (t.hour == 11 and t.minute <= 30)
    in_afternoon = (t.hour == 13 and t.minute >= 30) or (t.hour == 14 and t.minute < 55)
    if not (in_morning or in_afternoon):
        return

    if g.daily_pnl <= -context.portfolio.starting_cash * g.max_daily_loss_pct:
        return
    if g.daily_trades >= g.max_trades_per_day:
        return

    for s in g.symbols:
        state = g.trading_state[s]
        continuous = state['continuous']

        cur = attribute_history(continuous, 1, '1m', ['close', 'high', 'low'], skip_paused=True)
        if len(cur) == 0: continue
        price = cur['close'].iloc[-1]
        high = cur['high'].iloc[-1]
        low = cur['low'].iloc[-1]

        if price is None or np.isnan(price): continue

        # ========== 增强版出场逻辑 ==========
        if state['position_side'] == 1:
            # 1. 触发止损
            if low <= state['stop_price']:
                order_target(state['contract'], 0, side='long')
                g.daily_pnl += (state['stop_price'] - state['entry_price']) * 10
                state['position_side'] = 0
                log.info(f'{now} [{s}]多单止损 @{price:.1f}')
                continue
            
            # 2. 移动保本：赚15跳，止损移到开仓价
            if high >= state['entry_price'] + g.breakeven_ticks and state['stop_price'] < state['entry_price']:
                state['stop_price'] = state['entry_price']
                
            # 3. 赚40跳平一半
            if high >= state['entry_price'] + g.half_close_ticks and not state['half_closed']:
                order(state['contract'], 1, side='short') # 平掉1手多单
                state['half_closed'] = True
                # 剩下的半仓，止损上移，开始移动追踪
                state['stop_price'] = high - g.trail_stop_ticks 
                log.info(f'{now} [{s}]多单平半仓止盈，剩余移动止损@{state["stop_price"]:.1f}')
            
            # 4. 剩下半仓的移动追踪
            if state['half_closed'] and high > state['stop_price'] + g.trail_stop_ticks:
                state['stop_price'] = high - g.trail_stop_ticks # 止损线跟着最高价往上移

        elif state['position_side'] == -1:
            # 1. 触发止损
            if high >= state['stop_price']:
                order_target(state['contract'], 0, side='short')
                g.daily_pnl += (state['entry_price'] - state['stop_price']) * 10
                state['position_side'] = 0
                log.info(f'{now} [{s}]空单止损 @{price:.1f}')
                continue
            
            # 2. 移动保本
            if low <= state['entry_price'] - g.breakeven_ticks and state['stop_price'] > state['entry_price']:
                state['stop_price'] = state['entry_price']
                
            # 3. 赚40跳平一半
            if low <= state['entry_price'] - g.half_close_ticks and not state['half_closed']:
                order(state['contract'], 1, side='long') # 平掉1手空单
                state['half_closed'] = True
                state['stop_price'] = low + g.trail_stop_ticks
                log.info(f'{now} [{s}]空单平半仓止盈，剩余移动止损@{state["stop_price"]:.1f}')
                
            # 4. 剩下半仓的移动追踪
            if state['half_closed'] and low < state['stop_price'] - g.trail_stop_ticks:
                state['stop_price'] = low + g.trail_stop_ticks

        # ========== 开仓逻辑 ==========
        if state['position_side'] != 0:
            continue

        bars = attribute_history(continuous, g.breakout_lookback + 1, g.signal_freq, ['high', 'low'], skip_paused=True)
        if len(bars) < g.breakout_lookback + 1: continue
        n_high = bars['high'].iloc[:-1].max()
        n_low = bars['low'].iloc[:-1].min()

        contract_now = get_dominant_future(s)
        if contract_now is None or '9999' in contract_now: continue

        # 资金不足不开仓
        margin_needed = price * 10 * 0.12
        if context.portfolio.available_cash < margin_needed * 1.5: 
            continue 

        if price > n_high:
            order(contract_now, 1, side='long') 
            state['position_side'] = 1
            state['contract'] = contract_now
            state['entry_price'] = price
            state['stop_price'] = price - g.stop_ticks
            state['half_closed'] = False
            g.daily_trades += 1
            log.info(f'{now} [{s}] 开多 @{price:.1f} 止损{state["stop_price"]:.1f}')

        elif price < n_low:
            order(contract_now, 1, side='short') 
            state['position_side'] = -1
            state['contract'] = contract_now
            state['entry_price'] = price
            state['stop_price'] = price + g.stop_ticks
            state['half_closed'] = False
            g.daily_trades += 1
            log.info(f'{now} [{s}] 开空 @{price:.1f} 止损{state["stop_price"]:.1f}')