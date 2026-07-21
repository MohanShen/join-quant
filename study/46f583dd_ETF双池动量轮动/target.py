# Clone from JoinQuant
# postId: 46f583dd76e7884710faa7c774321eba
# backtestId: a365b6351e2bfc7825ef9b23277fcc5c
# title: 近4个月狂揽62%！六年11倍 ETF双池动量轮动

# 策略名称: 三部曲吃透ETF动量轮动3_终极版
# 特性：静态+动态池融合、行业分散、双均线过滤、止损、防御ETF
# 修复日期: 2026-04-10

from jqdata import *
import datetime
import math
import numpy as np
import pandas as pd


# ==================== 主题分类词典 ====================
# 基于ETF名称关键词进行主题归类，比get_industry更适合ETF
THEME_KEYWORDS = {
    "半导体": ["半导体", "芯片", "集成电路"],
    "医药": ["医药", "医疗", "创新药", "生物", "疫苗", "健康"],
    "消费": ["消费", "食品", "白酒", "家电", "零售", "酒"],
    "新能源": ["新能源", "光伏", "锂电", "风电", "碳中和", "电池", "储能"],
    "电力公用": ["电力", "绿电", "绿色电力", "公用事业", "水务", "燃气"],
    "军工": ["军工", "国防"],
    "金融": ["银行", "券商", "保险", "金融", "证券", "非银"],
    "科技信息": ["科技", "人工智能", "软件", "计算机", "互联网", "信息", "数据", "云计算"],
    "宽基": ["沪深300", "中证500", "中证1000", "上证50", "创业板", "科创",
            "中证A50", "MSCI", "红利", "价值", "成长", "龙头"],
    "跨境": ["纳斯达克", "纳指", "标普", "恒生", "日经", "德国", "法国",
            "印度", "越南", "亚太", "美国", "港股", "中概"],
    "资源能源": ["有色", "钢铁", "煤炭", "石油", "黄金", "白银", "铜", "稀土",
              "矿业", "资源", "豆粕", "能源化工", "油气", "天然气", "原油"],
    "地产基建": ["地产", "房地产", "建材", "基建", "建筑"],
    "通信": ["通信", "5G"],
    "汽车": ["汽车", "智能驾驶", "新能车", "电动车"],
    "机器人": ["机器人", "机械", "自动化", "智能制造"],
    "传媒": ["传媒", "游戏", "动漫", "影视"],
    "农业": ["农业", "养殖", "畜牧"],
    "环保": ["环保", "碳排放", "环境"],
}

# ==================== 全局配置 ====================
# 静态核心池：精选的核心宽基、行业、跨境ETF
STATIC_ETF_POOL = [
    "159206.XSHE", "159218.XSHE", "159227.XSHE", "159256.XSHE", "159323.XSHE",
    "159326.XSHE", "159363.XSHE", "159378.XSHE", "159502.XSHE", "159509.XSHE",
    "159516.XSHE", "159518.XSHE", "159529.XSHE", "159550.XSHE", "159566.XSHE",
    "159583.XSHE", "159605.XSHE", "159611.XSHE", "159637.XSHE", "159638.XSHE",
    "159667.XSHE", "159732.XSHE", "159755.XSHE", "159766.XSHE", "159819.XSHE",
    "159825.XSHE", "159840.XSHE", "159851.XSHE", "159852.XSHE", "159865.XSHE",
    "159869.XSHE", "159870.XSHE", "159883.XSHE", "159892.XSHE", "159915.XSHE",
    "159919.XSHE", "159922.XSHE", "159928.XSHE", "159949.XSHE", "159967.XSHE",
    "159980.XSHE", "159981.XSHE", "159985.XSHE", "159992.XSHE", "159995.XSHE",
    "159998.XSHE", "161226.XSHE", "501018.XSHG", "510050.XSHG", "510180.XSHG",
    "510300.XSHG", "510410.XSHG", "510500.XSHG", "510760.XSHG", "510880.XSHG",
    "510900.XSHG", "511260.XSHG", "511380.XSHG", "512000.XSHG", "512010.XSHG",
    "512050.XSHG", "512070.XSHG", "512100.XSHG", "512170.XSHG", "512200.XSHG",
    "512400.XSHG", "512480.XSHG", "512660.XSHG", "512670.XSHG", "512690.XSHG",
    "512710.XSHG", "512800.XSHG", "512880.XSHG", "512890.XSHG", "512980.XSHG",
    "513030.XSHG", "513050.XSHG", "513090.XSHG", "513100.XSHG", "513120.XSHG",
    "513130.XSHG", "513180.XSHG", "513190.XSHG", "513290.XSHG", "513300.XSHG",
    "513310.XSHG", "513330.XSHG", "513350.XSHG", "513360.XSHG", "513400.XSHG",
    "513500.XSHG", "513520.XSHG", "513630.XSHG", "513690.XSHG", "513750.XSHG",
    "513920.XSHG", "513970.XSHG", "515000.XSHG", "515030.XSHG", "515050.XSHG",
    "515120.XSHG", "515170.XSHG", "515210.XSHG", "515220.XSHG", "515250.XSHG",
    "515400.XSHG", "515650.XSHG", "515790.XSHG", "515880.XSHG", "515980.XSHG",
    "516010.XSHG", "516150.XSHG", "516160.XSHG", "516190.XSHG", "516510.XSHG",
    "516520.XSHG", "517520.XSHG", "518880.XSHG", "520830.XSHG", "560860.XSHG",
    "561330.XSHG", "561360.XSHG", "561980.XSHG", "562500.XSHG", "562590.XSHG",
    "562800.XSHG", "563300.XSHG", "588080.XSHG", "588120.XSHG", "588170.XSHG",
    "588200.XSHG", "588220.XSHG", "588790.XSHG"
]

# 策略参数配置（所有可调参数集中在此）
STRATEGY_CONFIG = {
    "stock_sum": 1,                  # 持仓数量
    "min_money": 500,                # 最小交易金额（元）
    "momentum_days": 25,             # 动量计算天数
    "enable_volume_check": True,     # 成交量过滤开关
    "volume_lookback": 5,            # 成交量回看天数
    "volume_threshold": 2.5,         # 成交量比值阈值
    "ma_short": 20,                  # 短期均线周期
    "ma_long": 60,                   # 长期均线周期
    "enable_ma_filter": True,        # 双均线过滤开关
    "stop_loss_ratio": 0.92,         # 止损比例（成本价的92%）
    "defensive_etf": "511880.XSHG",  # 防御ETF（银华日利）
    "enable_industry_diverse": False, # 行业分散开关
    "dynamic_pool_size": 150,        # 动态池大小（全市场成交额前N名）
    "dynamic_pool_min_money": 50000000, # 动态池最低日均成交额（5000万）
}

# 全局变量
g_positions = {}                     # 记录目标持仓数量
g_buy_prices = {}                    # 记录每只ETF的买入成本价（用于止损）
g_dynamic_pool = []                  # 缓存每日动态池

# ==================== 初始化函数 ====================
def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    log.set_level('order', 'info')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    
    # 滑点与手续费设置
    set_slippage(FixedSlippage(0.0001), type="fund")
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0, open_commission=0.0001,
                  close_commission=0.0001, close_today_commission=0.0001,
                  min_commission=5), type="fund")
    
    # 定时任务
    run_daily(update_dynamic_pool, "09:20")   # 盘前更新动态池
    run_daily(sell_routine, "13:09")          # 卖出
    run_daily(buy_routine, "13:10")           # 买入
    run_daily(sync_positions, "14:59")        # 收盘同步
    
    log.info("【终极版策略启动】")
    log.info(f"持仓数量: {STRATEGY_CONFIG['stock_sum']} | 动量周期: {STRATEGY_CONFIG['momentum_days']}天")
    log.info(f"止损比例: {(1-STRATEGY_CONFIG['stop_loss_ratio'])*100:.0f}% | 行业分散: {'开启' if STRATEGY_CONFIG['enable_industry_diverse'] else '关闭'}")
    log.info(f"动态池: 全市场成交额前{STRATEGY_CONFIG['dynamic_pool_size']}名 (最低日均{STRATEGY_CONFIG['dynamic_pool_min_money']/1e8:.1f}亿)")

# ==================== 动态池更新（盘前执行） ====================
def update_dynamic_pool(context):
    """每日09:00更新全市场流动性百强ETF池（使用history批量查询）"""
    global g_dynamic_pool
    config = STRATEGY_CONFIG

    log.info("--- 开始更新动态ETF池 ---")

    try:
        # 获取全市场所有ETF
        df_all_etf = get_all_securities(['etf'], date=context.current_dt)
        all_etf_codes = df_all_etf.index.tolist()
        
        # 排除防御ETF
        if config["defensive_etf"] in all_etf_codes:
            all_etf_codes.remove(config["defensive_etf"])
        
        # 使用 history 批量获取过去5日成交额
        # 注意：history 的 end_date 默认是 context.current_dt 的前一个交易日，因此不含当日数据
        df_money = history(5, '1d', 'money', all_etf_codes, df=True, skip_paused=True)
        
        if df_money is not None and not df_money.empty:
            # 计算每只ETF的日均成交额
            avg_money = df_money.mean()
            # 过滤成交额不达标的ETF
            valid_money = avg_money[avg_money > config["dynamic_pool_min_money"]]
            # 取前N名
            g_dynamic_pool = valid_money.sort_values(ascending=False).head(config["dynamic_pool_size"]).index.tolist()
        else:
            log.warning("未获取到成交额数据，使用上一交易日缓存")
            if not g_dynamic_pool:
                g_dynamic_pool = STATIC_ETF_POOL[:]
                log.warning("无缓存动态池，临时使用静态池")

        log.info(f"动态池更新完成：共 {len(g_dynamic_pool)} 只高流动性ETF")

    except Exception as e:
        log.error(f"动态池更新失败: {e}，使用上一交易日缓存")
        if not g_dynamic_pool:
            g_dynamic_pool = STATIC_ETF_POOL[:]
            log.warning("无缓存动态池，临时使用静态池")

# ==================== 辅助函数 ====================
def get_security_name(security):
    """安全获取证券名称"""
    try:
        return get_security_info(security).display_name
    except:
        return security

def get_etf_industry(security, date):
    """
    基于ETF名称的主题分类
    比 get_industry() 更适合ETF（ETF跟踪指数，不属于单一行业）
    """
    try:
        name = get_security_info(security).display_name
    except:
        return "其他"

    for theme, keywords in THEME_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return theme
    return "其他"

def order_target_value_smart(context, security, target_value):
    """智能下单至目标市值，处理停牌、涨跌停、T+1等边界情况"""
    current_data = get_current_data()
    if security not in current_data:
        return False
    
    cd = current_data[security]
    if cd.paused:
        log.info(f"⏸️ {security}({cd.name}) 停牌，跳过交易")
        return False
    if cd.last_price >= cd.high_limit:
        log.info(f"📈 {security}({cd.name}) 涨停，跳过买入")
        return False
    if cd.last_price <= cd.low_limit:
        log.info(f"📉 {security}({cd.name}) 跌停，跳过卖出")
        return False
    
    price = cd.last_price
    current_amount = g_positions.get(security, 0)
    target_amount = int(target_value / price // 100) * 100 if price > 0 else 0
    adjust_amount = target_amount - current_amount
    
    if adjust_amount == 0:
        return True
    
    # T+1卖出限制检查
    if adjust_amount < 0:
        pos = context.portfolio.positions.get(security)
        if pos is None or pos.closeable_amount < abs(adjust_amount):
            log.info(f"🔒 {security}({cd.name}) T+1限制，可卖数量不足")
            return False
    
    order_obj = order(security, adjust_amount)
    if order_obj and order_obj.filled > 0:
        # 更新本地持仓记录
        filled_amount = order_obj.filled if adjust_amount > 0 else -order_obj.filled
        g_positions[security] = current_amount + filled_amount
        if g_positions[security] <= 0:
            g_positions.pop(security, None)
            if security in g_buy_prices:
                del g_buy_prices[security]
        # 如果是买入，记录加权平均成本
        if adjust_amount > 0:
            old_cost = g_buy_prices.get(security, price)
            old_amount = current_amount
            new_cost = (old_cost * old_amount + price * filled_amount) / (old_amount + filled_amount)
            g_buy_prices[security] = new_cost
        
        action = "买入" if adjust_amount > 0 else "卖出"
        log.info(f"✅ {action} {security}({cd.name}) {abs(adjust_amount)}股 @ {price:.3f}")
        return True
    else:
        log.warning(f"❌ 下单失败 {security}，调整量 {adjust_amount}")
        return False

def get_today_volume_projection(security, context):
    """获取今日成交量投影（全天估算值）"""
    today = context.current_dt.date()
    now = context.current_dt
    df = get_price(security, start_date=today, end_date=now, frequency='1m', fields=['volume'])
    if df is None or df.empty:
        return None
    current_vol = df['volume'].sum()
    
    # 计算已交易分钟数比例
    market_open = datetime.datetime.combine(today, datetime.time(9, 30))
    lunch_start = datetime.datetime.combine(today, datetime.time(11, 30))
    lunch_end = datetime.datetime.combine(today, datetime.time(13, 0))
    
    if now < market_open:
        return 0
    if now > datetime.datetime.combine(today, datetime.time(15, 0)):
        return current_vol
    
    if now <= lunch_start:
        elapsed = (now - market_open).total_seconds() / 60
    elif now <= lunch_end:
        elapsed = 120
    else:
        elapsed = 120 + (now - lunch_end).total_seconds() / 60
    
    total_minutes = 240
    ratio = min(elapsed / total_minutes, 1.0)
    return current_vol / ratio if ratio > 0 else current_vol

# ==================== 筛选逻辑（核心） ====================
def filter_etfs(context):
    """执行多条件筛选，返回最终入选的ETF列表（含行业分散）"""
    config = STRATEGY_CONFIG
    current_data = get_current_data()
    current_date = context.current_dt.date()
    
    # ==================== 池子融合 ====================
    # 静态池 + 动态池，去重，并排除防御ETF
    combined_pool = list(set(STATIC_ETF_POOL + g_dynamic_pool))
    if config["defensive_etf"] in combined_pool:
        combined_pool.remove(config["defensive_etf"])
    
    log.info("=" * 60)
    log.info(f"【筛选开始】静态池 {len(STATIC_ETF_POOL)}只 + 动态池 {len(g_dynamic_pool)}只 -> 融合池 {len(combined_pool)}只")
    
    # ---------- Step 1: 双均线过滤 ----------
    passed_ma = []
    if config["enable_ma_filter"]:
        for etf in combined_pool:
            try:
                df = attribute_history(etf, config["ma_long"] + 1, '1d', ['close'])
                if df is None or len(df) < config["ma_long"]:
                    continue
                closes = df['close'].values
                ma_short = np.mean(closes[-config["ma_short"]:])
                ma_long = np.mean(closes[-config["ma_long"]:])
                if closes[-1] > ma_short and ma_short > ma_long:
                    passed_ma.append(etf)
            except:
                continue
        log.info(f"【均线过滤】通过 {len(passed_ma)} 只 (条件: 收盘>MA{config['ma_short']} 且 MA{config['ma_short']}>MA{config['ma_long']})")
    else:
        passed_ma = combined_pool   # 修复：关闭均线过滤时使用融合池
    
    if not passed_ma:
        log.info("【筛选结果】无ETF通过均线过滤")
        return []
    
    # ---------- Step 2: 动量评分 ----------
    score_list = []
    for etf in passed_ma:
        try:
            df = attribute_history(etf, config["momentum_days"], '1d', ['close', 'volume'])
            if df is None or len(df) < config["momentum_days"]:
                continue
            prices = df['close'].values
            current_price = current_data[etf].last_price
            prices = np.append(prices, current_price)
            
            if np.any(prices <= 0):
                continue
            
            # 成交量检查（前置）
            if config["enable_volume_check"]:
                volumes = df['volume'].values
                avg_vol = np.mean(volumes[-config["volume_lookback"]:])
                today_vol = get_today_volume_projection(etf, context)
                if today_vol is None:
                    continue
                vol_ratio = today_vol / avg_vol if avg_vol > 0 else 999
                if vol_ratio > config["volume_threshold"]:
                    continue
            
            # 加权对数回归计算动量得分
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            annual_ret = math.exp(slope * 250) - 1
            
            fitted_y = slope * x + intercept
            ss_res = np.sum(weights * (y - fitted_y) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
            score = annual_ret * r2
            
            if 0 < score < 5:
                score_list.append((etf, score, annual_ret, r2, current_price))
                
        except Exception as e:
            continue
    
    score_list.sort(key=lambda x: x[1], reverse=True)
    
    log.info(f"【动量评分】有效评分 {len(score_list)} 只 (0<score<5)")
    if score_list:
        log.info("--- 前10名 ---")
        for i, (etf, score, ret, r2, price) in enumerate(score_list[:10]):
            name = get_security_name(etf)
            industry = get_etf_industry(etf, current_date)
            log.info(f"{i+1}. {etf}({name}) 行业:{industry} 得分:{score:.4f} | 年化:{ret*100:.2f}% | R²:{r2:.3f}")
    
    # ---------- Step 3: 行业分散选取 ----------
    selected = []
    seen_industries = set()
    
    if config["enable_industry_diverse"]:
        log.info("【行业分散】开始按行业去重选取...")
        for etf, score, ret, r2, price in score_list:
            industry = get_etf_industry(etf, current_date)
            if industry in seen_industries:
                continue
            selected.append(etf)
            seen_industries.add(industry)
            name = get_security_name(etf)
            log.info(f"  ✅ 选中: {etf}({name}) - 行业:{industry} - 得分:{score:.4f}")
            if len(selected) >= config["stock_sum"]:
                break
        
        # 如果行业去重后仍不足，放宽限制补齐
        if len(selected) < config["stock_sum"]:
            log.info(f"⚠️ 行业分散后仅选中 {len(selected)} 只，放宽行业限制补齐...")
            for etf, score, ret, r2, price in score_list:
                if etf not in selected:
                    selected.append(etf)
                    name = get_security_name(etf)
                    industry = get_etf_industry(etf, current_date)
                    log.info(f"  ➕ 补选: {etf}({name}) - 行业:{industry} - 得分:{score:.4f}")
                    if len(selected) >= config["stock_sum"]:
                        break
    else:
        selected = [etf for etf, _, _, _, _ in score_list[:config["stock_sum"]]]
        log.info(f"【直接选取】前 {len(selected)} 名")
        for etf in selected:
            name = get_security_name(etf)
            log.info(f"  ✅ {etf}({name})")
    
    if not selected:
        log.info("【筛选结果】无有效标的，将使用防御ETF")
    else:
        log.info(f"【最终入选】{selected}")
    
    log.info("=" * 60)
    return selected

# ==================== 交易执行 ====================
def sell_routine(context):
    """卖出逻辑：止损 + 放量卖出 + 目标外卖出"""
    config = STRATEGY_CONFIG
    targets = get_cached_targets(context)
    current_data = get_current_data()
    
    hold_list = list(g_positions.keys())
    if not hold_list:
        log.info("【卖出】当前无持仓")
        return
    
    log.info(f"【卖出开始】当前持仓: {hold_list}")
    
    for etf in hold_list[:]:
        cd = current_data[etf]
        pos_amount = g_positions.get(etf, 0)
        if pos_amount <= 0:
            continue
        
        # 1. 固定比例止损
        cost_price = g_buy_prices.get(etf)
        if cost_price and cd.last_price <= cost_price * config["stop_loss_ratio"]:
            loss_pct = (cd.last_price / cost_price - 1) * 100
            log.info(f"🚨 【止损触发】{etf}({cd.name}) 现价{cd.last_price:.3f} <= 成本{cost_price:.3f}*{config['stop_loss_ratio']:.2f}，亏损{loss_pct:.2f}%，清仓")
            order_target_value_smart(context, etf, 0)
            continue
        
        # 2. 异常放量卖出
        if config["enable_volume_check"]:
            vol_ratio = get_volume_ratio_simple(etf, context)
            if vol_ratio and vol_ratio > config["volume_threshold"]:
                log.info(f"📊 【放量卖出】{etf}({cd.name}) 成交量比值 {vol_ratio:.2f} > {config['volume_threshold']}，清仓")
                order_target_value_smart(context, etf, 0)
                continue
        
        # 3. 不在目标列表卖出（防御ETF在无目标时会被保留）
        if etf not in targets and etf != config["defensive_etf"]:
            log.info(f"🔄 【调仓卖出】{etf}({cd.name}) 不在新目标中，清仓")
            order_target_value_smart(context, etf, 0)
    
    # 清理已清仓的记录
    for etf in list(g_positions.keys()):
        if g_positions.get(etf, 0) == 0:
            g_positions.pop(etf, None)
            if etf in g_buy_prices:
                del g_buy_prices[etf]
    
    log.info(f"【卖出完成】剩余持仓: {list(g_positions.keys())}")

def get_volume_ratio_simple(security, context):
    """简单成交量比值（用于卖出检查）"""
    try:
        df = attribute_history(security, 5, '1d', ['volume'])
        if df is None or len(df) < 5:
            return None
        avg_vol = df['volume'].mean()
        today_vol = get_today_volume_projection(security, context)
        if today_vol is None:
            return None
        return today_vol / avg_vol if avg_vol > 0 else 0
    except:
        return None

def buy_routine(context):
    """买入逻辑：等权买入目标ETF，若无目标则买入防御ETF"""
    config = STRATEGY_CONFIG
    targets = get_cached_targets(context)
    
    # 无动量目标时切换防御模式
    if not targets:
        defensive = config["defensive_etf"]
        if defensive:
            cd = get_current_data()[defensive]
            if not cd.paused and cd.last_price < cd.high_limit:
                targets = [defensive]
                log.info(f"🛡️ 【防御模式】无动量目标，买入 {defensive}({cd.name})")
            else:
                log.info("⚠️ 防御ETF不可交易，保持空仓")
                return
        else:
            log.info("【买入】无目标且无防御ETF，空仓")
            return
    
    log.info(f"【买入开始】目标: {targets}")
    
    total_value = context.portfolio.total_value
    target_value_per_etf = total_value / len(targets)
    available_cash = context.portfolio.available_cash
    
    current_data = get_current_data()
    for etf in targets:
        if etf in g_positions:
            # 已持有，检查是否需要再平衡补仓
            current_amount = g_positions[etf]
            current_value = current_amount * current_data[etf].last_price
            if current_value < target_value_per_etf * 0.85:
                log.info(f"⚖️ 【再平衡补仓】{etf} 当前市值{current_value:.0f} < 目标{target_value_per_etf:.0f}*0.85，补至目标")
                order_target_value_smart(context, etf, target_value_per_etf)
        else:
            # 新建仓
            if available_cash < max(config["min_money"], current_data[etf].last_price * 100):
                log.info(f"💰 资金不足，跳过 {etf}")
                continue
            log.info(f"🆕 【新建仓】{etf} 目标市值 {target_value_per_etf:.0f} 元")
            success = order_target_value_smart(context, etf, target_value_per_etf)
            if success:
                available_cash -= target_value_per_etf  # 粗略扣减
    
    log.info("【买入完成】")

def get_cached_targets(context):
    """带缓存的获取目标列表（避免同一交易日重复计算）"""
    today = context.current_dt.date()
    if hasattr(context, '_targets_cache') and context._targets_cache.get('date') == today:
        return context._targets_cache['targets']
    
    targets = filter_etfs(context)
    context._targets_cache = {'date': today, 'targets': targets}
    return targets

def sync_positions(context):
    """收盘同步：确保本地持仓记录与账户一致"""
    # 清理已不在账户中的持仓记录
    for etf in list(g_positions.keys()):
        pos = context.portfolio.positions.get(etf)
        if pos is None or pos.total_amount == 0:
            g_positions.pop(etf, None)
            if etf in g_buy_prices:
                del g_buy_prices[etf]
        else:
            g_positions[etf] = pos.total_amount
    
    # 补充账户有但本地没有的记录（如送股、手动买入等）
    for etf, pos in context.portfolio.positions.items():
        if pos.total_amount > 0 and etf not in g_positions:
            # 只管理属于我们池子内的标的
            all_managed = set(STATIC_ETF_POOL + [STRATEGY_CONFIG["defensive_etf"]])
            if etf in all_managed or etf in g_dynamic_pool:
                g_positions[etf] = pos.total_amount
                g_buy_prices[etf] = pos.avg_cost
                log.info(f"🔄 同步补充持仓记录: {etf} {pos.total_amount}股")