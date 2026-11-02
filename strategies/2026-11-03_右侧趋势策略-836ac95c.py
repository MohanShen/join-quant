# Clone from JoinQuant
# postId: 836ac95c6539037bfbd3e5ec9a4679ed
# backtestId: e4864178b8f8a3e5063ba6f7fe5e175b
# title: 右侧趋势策略

# -*- coding: utf-8 -*-
from jqdata import *
import datetime

def initialize(context):
    set_option('use_real_price', True)
    set_benchmark('000300.XSHG')

    # ====================== 修复：支持多只持仓独立记录 ======================
    context.hold_info = {}  # 多持仓管理（只加这一行）

    g.index_etf_map = {
        "399283.XSHE": ["算力硬件", "159559.XSHE"],
        "399967.XSHE": ["军工", "512660.XSHG"],
        "399417.XSHE": ["新能源车", "160225.XSHE"],
        "399998.XSHE": ["煤炭", "515220.XSHG"],
        "000819.XSHG": ["有色金属", "512400.XSHG"],
        "399265.XSHE": ["创新药", "159858.XSHE"],
        "399977.XSHE": ["光伏", "516290.XSHG"],
        "000685.XSHG": ["芯片", "589100.XSHG"],
        "399389.XSHE": ["通信设备", "515880.XSHG"],
        "399284.XSHE": ["人工智能", "515070.XSHG"],
        "000097.XSHG": ["工业母机", "159667.XSHE"],
    }
    log.info("=== 全行业ETF策略启动 ===")
    run_daily(strategy_run, time='14:45')

def get_1445_price_ma10_ma20(stock, context):
    today = context.current_dt
    try:
        prev9 = get_price(stock, count=9, end_date=today - datetime.timedelta(days=1), fields='close')['close'].tolist()
        prev19 = get_price(stock, count=19, end_date=today - datetime.timedelta(days=1), fields='close')['close'].tolist()
        min_df = get_price(stock, frequency='minute', end_date=today, fields='close').between_time('14:45', '14:45')
        if min_df.empty:
            return None, None, None
        p1445 = min_df['close'].iloc[-1]
        ma10 = (sum(prev9) + p1445) / 10
        ma20 = (sum(prev19) + p1445) / 20
        return p1445, ma10, ma20
    except:
        return None, None, None

def check_sell_signal(stock, context):
    try:
        df = get_price(stock, count=30, end_date=context.current_dt.date(), fields='close')
        close = df['close']
        ma10 = close.rolling(10).mean()
        ma20 = close.rolling(20).mean()

        cond1 = close.iloc[-3] < ma10.iloc[-3]
        cond2 = close.iloc[-2] < ma10.iloc[-2]
        p1445, ma10_1445, ma20_1445 = get_1445_price_ma10_ma20(stock, context)
        if p1445 is None:
            return False, False
        cond3 = p1445 < ma10_1445
        half_sell = cond1 and cond2 and cond3

        clear_cond1 = close.iloc[-3] < ma20.iloc[-3]
        clear_cond2 = close.iloc[-2] < ma20.iloc[-2]
        clear_cond3 = p1445 < ma20_1445
        clear_sell = clear_cond1 and clear_cond2 and clear_cond3
        return half_sell, clear_sell
    except:
        return False, False

def scan_strongest_etf(context):
    today = context.current_dt.date()
    log.info("\n====================全指数20日线校验====================")
    index_codes = list(g.index_etf_map.keys())
    temp_list = []
    for idx_code in index_codes:
        try:
            industry, etf = g.index_etf_map[idx_code]
            df = get_price(idx_code, count=30, end_date=today, fields='close')
            close = df['close'].dropna()
            if len(close) < 20: continue
            ma20 = close.rolling(20).mean()
            ma20_up = ma20.iloc[-1] > ma20.iloc[-2]
            log.info(f"【指数】{industry:<12}{idx_code}|MA20抬头:{ma20_up}")
            if ma20_up:
                temp_list.append([idx_code, industry, etf])
        except:
            continue
    if not temp_list:
        log.info("→无指数满足MA20抬头")
        return None, None

    final_list = []
    log.info("\n====================ETF价格校验====================")
    for idx_code, industry, etf_code in temp_list:
        try:
            df = get_price(etf_code, count=30, end_date=today, fields='close')
            close = df['close']
            ma20 = close.rolling(20).mean()
            c2 = close.iloc[-2]
            c3 = close.iloc[-3]
            m2 = ma20.iloc[-2]
            m3 = ma20.iloc[-3]
            etf_ma20_up = ma20.iloc[-1] > ma20.iloc[-2]
            cond1 = (c3 > m3) and (c2 > m2) and etf_ma20_up
            if not cond1: continue
            p1445, _, ma20_now = get_1445_price_ma10_ma20(etf_code, context)
            if p1445 and p1445 > ma20_now:
                rise20 = (close.iloc[-1] / close.iloc[-21] - 1) * 100
                final_list.append([etf_code, industry, rise20])
                log.info(f"✅{industry} {etf_code} 满足条件 | 20日涨幅:{rise20:.1f}%")
        except:
            continue
    if not final_list:
        log.info("→无ETF满足买入条件")
        return None, None
    final_list.sort(key=lambda x: x[2], reverse=True)
    best_code, best_name, best_rise = final_list[0]
    log.info(f"\n🏆最优标的：{best_code} {best_name} | 涨幅:{best_rise:.1f}%")
    return best_code, best_name

# ====================== 主策略（只修复多持仓判断，其余100%不动） ======================
def strategy_run(context):
    log.info(f"\n📅{context.current_dt.date()} 14:45执行")
    hold_list = [s for s in context.portfolio.positions if context.portfolio.positions[s].total_amount > 0]

    # ====================== 修复：所有持仓，每天全部判断卖出 ======================
    for code in hold_list:
        if code not in context.hold_info:
            continue
        info = context.hold_info[code]
        buy_date = info['buy_date']

        if (context.current_dt.date() - buy_date).days < 2:
            log.info(f"→{code} 买入未满2日，锁仓")
            continue

        half_sell, clear_sell = check_sell_signal(code, context)
        pos = context.portfolio.positions[code].closeable_amount

        if clear_sell:
            order_target(code, 0)
            context.hold_info.pop(code, None)
            log.info(f"❌{code} 清仓")
        elif half_sell and not info['sold_half'] and pos > 0:
            order(code, -pos // 2)
            context.hold_info[code]['sold_half'] = True
            log.info(f"⚠️{code} 减半")

    # ====================== 买入逻辑：完全不动 ======================
    hold_list = [s for s in context.portfolio.positions if context.portfolio.positions[s].total_amount > 0]
    if len(hold_list) >= 2:
        return

    log.info("📤尝试买入标的")
    code, name = scan_strongest_etf(context)
    if code and code not in hold_list:
        buy_value = context.portfolio.total_value / 3
        order_value(code, buy_value)
        context.hold_info[code] = {
            'name': name,
            'buy_date': context.current_dt.date(),
            'sold_half': False
        }
        log.info(f"🚀买入：{name} {code} (1/3仓)")