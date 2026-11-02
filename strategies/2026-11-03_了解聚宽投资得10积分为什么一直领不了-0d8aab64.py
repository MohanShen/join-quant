# Clone from JoinQuant
# postId: 0d8aab64ba8593afe7f8ad3c75b4a310
# backtestId: 65c0c74d2cad49b48202b0b252b18126
# title: 了解聚宽投资得10积分为什么一直领不了

# 克隆自聚宽文章：https://www.joinquant.com/post/75138
# 标题：七星高照ETF轮动v1.7_P_Trade版（破百更新）
# 作者：云白山人

# ========================================
# 合并策略：ETF动量 +红利轮动/创业板动量
# 各占50%仓位
# 策略A：五福7.0-高收益（ETF动量轮动）
# 策略B：红利轮动 + 创业板动量双策略
# ========================================

import numpy as np
import math
import pandas as pd
from jqdata import *
from datetime import datetime, date, timedelta


def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    # ETF用基金费率
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001,
                              close_commission=0.0001, close_today_commission=0.0001,
                              min_commission=5), type="fund")
    # 股票用股票费率
    set_slippage(FixedSlippage(0.005), type='stock')
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0003,
                              close_commission=0.0003, close_today_commission=0,
                              min_commission=5), type='stock')
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    log.set_level('history', 'error')

    # ==================== 仓位分配 ====================
    g.capital_ratio = 0.5  # 每个策略各占50%

    # ==================== 策略A（ETF动量）参数 ====================
    log.info("【合并策略】策略A（ETF动量）初始化...")

    g.global_etf_pool = [
        '518880.XSHG', '501018.XSHG', '161226.XSHE', '159985.XSHE', '159980.XSHE',
        '513310.XSHG', '159518.XSHE', '159509.XSHE', '513100.XSHG', '513520.XSHG',
        '513500.XSHG', '159502.XSHE', '513400.XSHG', '513030.XSHG', '513290.XSHG',
        '520830.XSHG', '159529.XSHE',
    ]
    g.china_etf_pool = [
        '513090.XSHG', '513120.XSHG', '513180.XSHG', '513330.XSHG', '513750.XSHG',
        '159892.XSHE', '513190.XSHG', '159605.XSHE', '513630.XSHG', '159323.XSHE',
        '510900.XSHG', '513920.XSHG', '513970.XSHG',
        '511380.XSHG', '512050.XSHG', '510500.XSHG', '159915.XSHE', '510300.XSHG',
        '512100.XSHG', '159949.XSHE', '588080.XSHG', '159967.XSHE', '588220.XSHG',
        '563300.XSHG', '510760.XSHG',
        '588200.XSHG', '515880.XSHG', '159981.XSHE', '512880.XSHG', '513350.XSHG',
        '159326.XSHE', '159516.XSHE', '159206.XSHE', '512480.XSHG', '159363.XSHE',
        '159870.XSHE', '512400.XSHG', '159755.XSHE', '588170.XSHG', '159992.XSHE',
        '159995.XSHE', '512890.XSHG', '515220.XSHG', '159566.XSHE', '159819.XSHE',
        '512800.XSHG', '512690.XSHG', '515050.XSHG', '562500.XSHG', '512170.XSHG',
        '517520.XSHG', '159869.XSHE', '512070.XSHG', '159611.XSHE', '562800.XSHG',
        '515120.XSHG', '512010.XSHG', '510880.XSHG', '515790.XSHG', '515980.XSHG',
        '512660.XSHG', '159928.XSHE', '512710.XSHG', '560860.XSHG', '515030.XSHG',
        '159766.XSHE', '159218.XSHE', '159852.XSHE', '516160.XSHG', '516150.XSHG',
        '159227.XSHE', '159583.XSHE', '588790.XSHG', '159865.XSHE', '512980.XSHG',
        '159851.XSHE', '561360.XSHG', '561980.XSHG', '562590.XSHG', '512200.XSHG',
        '159732.XSHE', '159667.XSHE', '516510.XSHG', '159840.XSHE', '159998.XSHE',
        '159825.XSHE', '512670.XSHG', '159883.XSHE', '515210.XSHG', '515400.XSHG',
        '159256.XSHE', '561330.XSHG', '515170.XSHG', '159638.XSHE', '516520.XSHG',
        '513360.XSHG', '516190.XSHG',
    ]
    g.fixed_etf_pool = g.global_etf_pool + g.china_etf_pool

    g.avg_etf_money_threshold = None
    g.filtered_fixed_pool = []
    g.dynamic_etf_pool = []
    g.merged_etf_pool = []
    g.ranked_etfs_result = []
    g.filtered_global_pool = []

    g.is_a_share_weak = False
    g.weak_entry_ma_lookback = 10
    g.weak_exit_ma_lookback = 8
    g.weak_start_date = None
    g.last_weak_exit_date = None
    g.weak_days_count = 0
    g.max_weak_days = 20
    g.weak_reentry_cooldown_days = 3
    g.strong_weak_reentry_confirm_count = 4
    g.adaptive_ma_enabled = False
    g.weak_entry_below_threshold = 3

    g.enable_dispersion_filter = True
    g.dispersion_window = 5
    g.dispersion_low_threshold = 0.3
    g.dispersion_history = []

    g.enable_ma_arrangement_factor = False
    g.enable_relative_strength_factor = False

    g.holdings_num = 1
    g.pending_buy_etfs = []
    g.trend_lookback_minutes = 30
    g.trend_slope_threshold = 0.001
    g.defensive_etf = "511880.XSHG"
    g.min_money = 10
    g.target_etfs_list = []
    g.etf_names_dict = {}
    g.cache_date = None
    g.yesterday_close_cache = {}

    g.lookback_days = 25
    g.min_score_threshold = 0
    g.max_score_threshold = 5
    g.score_threshold_ratio = 0.9

    g.enable_r2_filter = True
    g.r2_threshold = 0.4
    g.enable_ma_filter = True
    g.ma_lookback = 10
    g.ma_threshold = 1.0
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 1.8
    g.enable_loss_filter = True
    g.loss = 0.97
    g.enable_premium_filter = False
    g.max_premium_rate = 30
    g.enable_laplace_filter = True
    g.laplace_s_param = 0.05
    g.laplace_s_param_normal = 0.07
    g.laplace_s_param_weak = 0.10
    g.laplace_min_slope = 0.002

    g.max_portfolio_value = 0
    g.drawdown_threshold = 0.03
    g.drawdown_records = []

    g.use_fixed_stop_loss = True
    g.fixedStopLossThreshold = 0.95
    g.use_pct_stop_loss = False
    g.pct_stop_loss_threshold = 0.95

    # ==================== 策略B（红利+创业板动量）参数 ====================
    log.info("【合并策略】策略B（红利+创业板动量）初始化...")

    g.main = {
        'sell_list': [],
        'buy_df': pd.DataFrame(),
        'high_price_dict': {},
        'buy_date': {},
        'stock_num': 6,
        'hold_list': [],
        'high_limit_list': [],
    }

    g.mom = {
        'sell_list': [],
        'buy_df': pd.DataFrame(),
        'high_price_dict': {},
        'buy_date': {},
        'stock_num': 3,
        'stop_loss': -0.10,
    }

    g.highest_value = context.portfolio.total_value
    g.portfolio_ratio = 1.0
    g.cyb_index = '399006.XSHE'
    g.cyb_stocks_cache = []

    # ==================== 调度设置 ====================
    set_benchmark("510300.XSHG")

    # 策略A调度
    run_daily(morning_routine, time='09:00')
    run_daily(check_weak_period_daily, time='09:40')
    run_daily(afternoon_routine, time='13:10')
    run_daily(buy_routine, time='13:10')
    run_daily(check_pending_buys_trend, time='13:40')
    run_daily(check_pending_buys_trend, time='14:10')
    run_daily(check_pending_buys_trend, time='14:40')
    run_daily(force_buy_pending, time='14:55')
    run_daily(reset_daily_flags, time='15:10')

    # 策略B调度
    run_daily(prepare_stock_list, '09:00')
    run_monthly(get_stock_list, 1, '09:01')
    run_daily(check_stop_loss, '09:32')
    run_monthly(my_trade, 1, '09:30')
    run_daily(check_limit_up, '10:00')

    log.info(f"""
【合并策略初始化完成】
=== 仓位分配 ===
- 策略A（ETF动量）: {g.capital_ratio:.0%}
- 策略B（红利+创业板动量）: {g.capital_ratio:.0%}
=== 策略A ETF池 ===
- 全球/海外ETF池: {len(g.global_etf_pool)}只
- 国内ETF池: {len(g.china_etf_pool)}只
- 固定池合计: {len(g.fixed_etf_pool)}只
- 持仓数量: {g.holdings_num}只
- 防御ETF: {g.defensive_etf}
=== 策略B股票策略 ===
- 红利轮动持仓: {g.main['stock_num']}只
- 创业板动量持仓: {g.mom['stock_num']}只
- 创业板止损: {g.mom['stop_loss']:.0%}
""")


# ============================================================
#                  策略A：ETF动量轮动
# ============================================================

def check_weak_period_daily(context):
    check_a_share_weak_period(context)
    midday_routine(context)


def morning_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【策略A晨间流水线】启动...")
    check_positions(context)
    monitor_drawdown(context)
    calculate_global_etf_threshold(context)
    update_adaptive_ma(context)
    log.info("⏸️ 【策略A晨间流水线】执行完毕！")


def midday_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【策略A早盘流水线】启动...")
    if g.is_a_share_weak:
        log.info(f"🔴 【走弱期池更新】仅对全球/海外ETF池进行流动性过滤...")
        filter_global_pool_by_volume(context)
        log.info(f"【走弱期池更新完成】过滤后全球池: {len(g.filtered_global_pool)}只")
    else:
        log.info(f"🟢 【正常期池更新】执行动态池更新、固定池过滤、合并池...")
        update_sector_pool(context)
        filter_fixed_pool_by_volume(context)
        daily_merge_etf_pools(context)
        log.info(f"【正常期池更新完成】合并池: {len(g.merged_etf_pool)}只")
    log.info("⏸️ 【策略A早盘流水线】执行完毕！")


def afternoon_routine(context):
    log.info("▶️ 【策略A午盘流水线】启动...")
    if g.is_a_share_weak:
        if hasattr(g, 'filtered_global_pool') and g.filtered_global_pool:
            g.merged_etf_pool = list(set(g.filtered_global_pool))
        else:
            g.merged_etf_pool = list(set(g.global_etf_pool))
        g.merged_etf_pool.sort()
        log.info(f"🔴 【大A走弱期】使用过滤后全球/海外ETF池，共{len(g.merged_etf_pool)}只")
    else:
        log.info(f"🟢 【大A正常期】使用合并池，共{len(g.merged_etf_pool)}只")
    calculate_and_log_ranked_etfs(context)
    execute_sell_trades(context)
    check_dispersion_filter(context)
    log.info("⏸️ 【策略A午盘流水线】执行完毕！")


def reset_daily_flags(context):
    g.cache_date = None
    g.yesterday_close_cache = {}
    g.pending_buy_etfs = []
    log.info("🔄 策略A收盘缓存重置完成")


def check_positions(context):
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 【持仓检查】{security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 当前价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security} {security_name} 今日停牌")


def monitor_drawdown(context):
    try:
        current_value = context.portfolio.total_value
        if current_value > g.max_portfolio_value:
            g.max_portfolio_value = current_value
        if g.max_portfolio_value > 0:
            current_drawdown = (g.max_portfolio_value - current_value) / g.max_portfolio_value
            if current_drawdown >= g.drawdown_threshold:
                record = {
                    'date': context.current_dt.strftime('%Y-%m-%d'),
                    'drawdown': current_drawdown,
                    'portfolio_value': current_value,
                    'max_value': g.max_portfolio_value,
                    'is_weak': g.is_a_share_weak
                }
                positions_info = []
                for security in context.portfolio.positions:
                    position = context.portfolio.positions[security]
                    if position.total_amount > 0:
                        security_name = get_security_name(security)
                        positions_info.append(f"{security_name}:{position.total_amount}股")
                record['positions'] = positions_info
                g.drawdown_records.append(record)
                log.info(f"【回撤预警】回撤达到 {current_drawdown:.2%} (阈值: {g.drawdown_threshold:.0%})")
                log.info(f"  当前净值: {current_value:,.0f}  |  最高净值: {g.max_portfolio_value:,.0f}")
                log.info(f"  大A状态: {'走弱期' if g.is_a_share_weak else '正常期'}")
                log.info(f"  持仓: {', '.join(positions_info) if positions_info else '空仓'}")
    except Exception as e:
        log.error(f"【回撤监控】计算异常: {e}")


def calculate_global_etf_threshold(context):
    log.info("【全局阈值更新】开始计算全市场ETF流动性门槛")
    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            log.warning("未找到任何场内ETF，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        log.info(f"全市场ETF总数: {len(etf_list)}只")
        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]
        df = get_price(security=etf_list, start_date=start_day, end_date=context.previous_date, frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or df.empty:
            log.warning("无法获取历史成交额数据，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        daily_totals = df.groupby('time')['money'].sum()
        daily_counts = df[df['money'] > 0].groupby('time')['code'].nunique()
        for day, money in daily_totals.items():
            count = daily_counts.get(day, 0)
            log.info(f"  {day.date()} 全市场ETF总成交额: {money/1e8:.2f}亿元 ({count}只ETF有成交)")
        if len(daily_totals) < 3:
            log.warning(f"仅有{len(daily_totals)}个有效交易日，使用保守阈值1000万")
            g.avg_etf_money_threshold = 10000000
            return
        avg_total_money = daily_totals.mean()
        threshold = avg_total_money / 20000
        g.avg_etf_money_threshold = threshold
        log.info(f"【全局阈值更新完成】近{len(daily_totals)}日全市场ETF日均总成交额={avg_total_money/1e8:.2f}亿元，阈值={threshold/1e4:.0f}万元({threshold:,.0f}元)")
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}，使用保守阈值1000万")
        g.avg_etf_money_threshold = 10000000


def filter_global_pool_by_volume(context):
    log.info("【全球池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        log.info("【全球池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.global_etf_pool:
        log.info("【全球池过滤】全球池为空，跳过过滤")
        g.filtered_global_pool = []
        return
    dynamic_threshold = g.avg_etf_money_threshold
    log.info(f"【全球池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.global_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("【全球池过滤】无法获取成交额数据，使用原始全球池")
            g.filtered_global_pool = g.global_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_global_pool = qualified.index.tolist()
        removed = set(g.global_etf_pool) - set(new_global_pool)
        if removed:
            removed_info = []
            for code in removed:
                try:
                    name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                    money = avg_daily_money.get(code, 0)
                    removed_info.append(f"{name}({code}) {money/1e8:.2f}亿")
                except:
                    removed_info.append(code)
            log.info(f"【全球池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_global_pool = new_global_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        log.info(f"【全球池过滤】保留高流动性ETF({len(new_global_pool)}只)")
    except Exception as e:
        log.warning(f"【全球池过滤】异常: {e}")
        g.filtered_global_pool = g.global_etf_pool[:]


def update_sector_pool(context):
    log.info("【动态池更新】开始执行")
    if g.avg_etf_money_threshold is None:
        log.info("【动态池更新】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)

    FUND_COMPANIES = sorted(list(set([
        '易方达', '广发', '华夏', '华安', '嘉实', '富国', '招商', '鹏华', '南方', '汇添富', '国泰', '平安',
        '银华', '天弘', '建信', '工银', '华泰柏瑞', '博时', '景顺长城', '景顺', '华宝', '申万菱信', '万家', '中欧',
        '兴证全球', '浙商', '诺安', '前海开源', '泰康', '泰达宏利', '农银汇理', '交银', '东方红', '财通', '华商',
        '国联', '永赢', '金鹰', '德邦', '创金合信', '西部利得', '圆信永丰', '泓德', '汇安', '诺德', '恒生前海',
        '华润元大', '大成', '海富通', '摩根', '华泰', '中信', '中银', '兴全', '国信', '长城', '中金', '浙商证券',
        '东海', '东吴', '浦银安盛', '信达澳亚', '中加', '中航', '中融', '中邮', '中庚', '中信保诚', '中信建投',
        '中银国际', '中银证券', '九泰', '交银施罗德', '光大保德信', '兴银', '农银', '国投瑞银', '国海富兰克林',
        '国联安', '国金', '太平', '方正富邦', '民生加银', '汇丰晋信', '银河', '长信', '长安', '长盛', '长江证券', '鹏扬'
    ])), key=len, reverse=True)

    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)

    SPECIAL_GROUPS = sorted([
        {'name': '香港组', 'keywords': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS科技'], key=len, reverse=True),
         'remove_words': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS'], key=len, reverse=True)},
        {'name': '科创组', 'keywords': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True),
         'remove_words': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创', '债券', '债汇', '债指', '债沪', '债易', '债基', '债兴', '债摩', '债', 'AAA'], key=len, reverse=True)},
        {'name': '创业组', 'keywords': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True),
         'remove_words': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True)},
        {'name': '美指组', 'keywords': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True),
         'remove_words': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True)}
    ], key=lambda x: max(len(kw) for kw in x['keywords']), reverse=True)

    exclude_keywords = sorted(list(set([
        '300', '500', '1000', '2000', '800', '30', '50', '100', '180', '200',
        '沪深', '中证', '上证', '深证', '深成', 'A50', 'A100', 'A500', '深100',
        '短融', '可转债', '转债', '双债', '利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债',
        '信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债', '科创债', '科债', '科创AAA',
        '自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流',
        '货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数',
        '全指现金', '现金全指', 'ESG', 'MSCI', 'MS', '债',
    ])), key=len, reverse=True)

    try:
        df_etf = get_all_securities(['etf'])
        etf_list = df_etf.index.tolist()
        g.etf_names_dict = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"获取全市场ETF列表失败: {e}")
        return

    log.info(f"【动态池更新】全市场ETF总数: {len(etf_list)}只")
    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0

    for code in etf_list:
        try:
            name = g.etf_names_dict.get(code, str(code))
            is_special = False
            matched_group = None
            for group in SPECIAL_GROUPS:
                for kw in group['keywords']:
                    if kw in name:
                        is_special = True
                        matched_group = group['name']
                        break
                if is_special:
                    break
            is_excluded = False
            for k in exclude_keywords:
                if k in name:
                    is_excluded = True
                    excluded_count += 1
                    break
            if not is_excluded:
                if is_special:
                    special_etfs.append(code)
                    special_group_map[code] = matched_group
                else:
                    normal_etfs.append(code)
        except Exception:
            continue

    group_counts = {}
    for code in special_etfs:
        group_name = special_group_map.get(code, '未知')
        group_counts[group_name] = group_counts.get(group_name, 0) + 1
    log.info(f"【动态池更新】特别组分布: {group_counts}")
    log.info(f"【动态池更新】进入特别组: {len(special_etfs)}只")
    log.info(f"【动态池更新】进入普通组: {len(normal_etfs)}只")
    log.info(f"【动态池更新】排除ETF: {excluded_count}只")

    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    dynamic_threshold = g.avg_etf_money_threshold

    def filter_by_liquidity(etf_codes, group_name):
        if not etf_codes:
            return pd.Series(dtype=float), 0
        try:
            price_data = get_price(etf_codes, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
            if price_data is None or price_data.empty:
                return pd.Series(dtype=float), len(etf_codes)
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily_money = total_money / TRADE_DAYS_COUNT
            qualified_series = avg_daily_money[avg_daily_money > dynamic_threshold].sort_values(ascending=False)
            filtered_out = len(etf_codes) - len(qualified_series)
            return qualified_series, filtered_out
        except Exception:
            return pd.Series(dtype=float), len(etf_codes)

    normal_qualified, normal_filtered_out = filter_by_liquidity(normal_etfs, "普通组")
    special_qualified, special_filtered_out = filter_by_liquidity(special_etfs, "特别组")
    normal_sorted = normal_qualified.index.tolist()
    special_sorted = special_qualified.index.tolist()
    log.info(f"【动态池更新】特别组流动性过滤: {len(special_etfs)}→{len(special_sorted)}只")
    log.info(f"【动态池更新】普通组流动性过滤: {len(normal_etfs)}→{len(normal_sorted)}只")

    if not normal_sorted and not special_sorted:
        log.warning("【动态池更新】无ETF通过流动性过滤")
        g.dynamic_etf_pool = []
        return

    def get_remove_words_for_etf(_, is_special, matched_group_name):
        if not is_special:
            return []
        for group in SPECIAL_GROUPS:
            if group['name'] == matched_group_name:
                return group['remove_words']
        return []

    def clean_name(original_name, is_special=False, matched_group_name=None):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        if is_special and matched_group_name:
            for word in get_remove_words_for_etf(original_name, is_special, matched_group_name):
                cleaned = cleaned.replace(word, '')
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()

    normal_industry_groups = {}
    for code in normal_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            money = normal_qualified[code]
            cleaned = clean_name(original_name, is_special=False)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            if industry_key not in normal_industry_groups:
                normal_industry_groups[industry_key] = []
            normal_industry_groups[industry_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': '普通'
            })
        except Exception:
            continue

    special_industry_groups = {}
    for code in special_sorted:
        try:
            original_name = g.etf_names_dict.get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            money = special_qualified[code]
            cleaned = clean_name(original_name, is_special=True, matched_group_name=matched_group)
            if cleaned == '':
                continue
            industry_key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            group_key = f"{matched_group}_{industry_key}"
            if group_key not in special_industry_groups:
                special_industry_groups[group_key] = []
            special_industry_groups[group_key].append({
                'code': code, 'original_name': original_name, 'cleaned_name': cleaned,
                'money': money, 'group_type': matched_group, 'display_group': matched_group
            })
        except Exception:
            continue

    final_pool_info = []
    for industry_key, items in normal_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])
    for group_key, items in special_industry_groups.items():
        sorted_items = sorted(items, key=lambda x: x['money'], reverse=True)
        final_pool_info.append(sorted_items[0])

    final_pool_info_sorted = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    top_100 = final_pool_info_sorted[:100]
    g.dynamic_etf_pool = [item['code'] for item in top_100]
    log.info(f"【动态池更新完成】动态池共{len(g.dynamic_etf_pool)}只ETF")
    if len(g.dynamic_etf_pool) <= 10:
        for item in top_100[:10]:
            log.info(f"  {item['code']} {item['original_name']} 日均成交额: {item['money']/1e8:.2f}亿")


def filter_fixed_pool_by_volume(context):
    log.info("【固定池过滤】开始执行")
    if getattr(g, 'avg_etf_money_threshold', None) is None:
        log.info("【固定池过滤】阈值未初始化，立即计算")
        calculate_global_etf_threshold(context)
    if not g.fixed_etf_pool:
        log.info("【固定池过滤】固定池为空，跳过过滤")
        return
    dynamic_threshold = g.avg_etf_money_threshold
    log.info(f"【固定池过滤】使用流动性门槛=日均{dynamic_threshold/1e4:.0f}万元")
    end_date = context.previous_date
    TRADE_DAYS_COUNT = 3
    try:
        price_data = get_price(g.fixed_etf_pool, end_date=end_date, count=TRADE_DAYS_COUNT, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            log.warning("【固定池过滤】无法获取成交额数据，跳过过滤")
            g.filtered_fixed_pool = g.fixed_etf_pool[:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily_money = total_money / TRADE_DAYS_COUNT
        qualified = avg_daily_money[avg_daily_money > dynamic_threshold]
        new_fixed_pool = qualified.index.tolist()
        removed = set(g.fixed_etf_pool) - set(new_fixed_pool)
        if removed:
            removed_info = []
            for code in removed:
                try:
                    name = getattr(g, 'etf_names_dict', {}).get(code, str(code))
                    money = avg_daily_money.get(code, 0)
                    removed_info.append(f"{name}({code}) {money/1e8:.2f}亿")
                except:
                    removed_info.append(code)
            log.info(f"【固定池过滤】剔除低流动性ETF({len(removed)}只)")
        g.filtered_fixed_pool = new_fixed_pool
        sorted_qualified = qualified.sort_values(ascending=False)
        log.info(f"【固定池过滤】保留高流动性ETF({len(new_fixed_pool)}只)")
    except Exception as e:
        log.warning(f"【固定池过滤】异常: {e}")
        g.filtered_fixed_pool = g.fixed_etf_pool[:]


def daily_merge_etf_pools(context):
    if not hasattr(g, 'filtered_fixed_pool'):
        g.filtered_fixed_pool = g.fixed_etf_pool[:]
    merged = list(set(g.filtered_fixed_pool + g.dynamic_etf_pool))
    merged.sort()
    log.info("【合并ETF池】开始执行")
    log.info(f"【合并池统计】固定池: {len(g.filtered_fixed_pool)}只, 动态池: {len(g.dynamic_etf_pool)}只, 合并后: {len(merged)}只")
    g.merged_etf_pool = merged


def calculate_and_log_ranked_etfs(context):
    if not hasattr(g, 'merged_etf_pool') or not g.merged_etf_pool:
        log.warning("【动量计算】合并池为空，无法计算")
        g.ranked_etfs_result = []
        return
    final_list = get_final_ranked_etfs(context)
    g.ranked_etfs_result = final_list


def calculate_momentum_score(price_series, lookback_days):
    if len(price_series) < lookback_days + 1:
        return None, None, None
    recent_price_series = price_series[-(lookback_days + 1):]
    y = np.log(recent_price_series)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    W = weights ** 2
    W_sum = np.sum(W)
    x_bar = np.sum(W * x) / W_sum
    y_bar = np.sum(W * y) / W_sum
    dx = x - x_bar
    dy = y - y_bar
    variance_x = np.sum(W * dx**2)
    if variance_x == 0:
        return 0, 0, 0
    slope = np.sum(W * dx * dy) / variance_x
    intercept = y_bar - slope * x_bar
    annualized_returns = math.exp(slope * 250) - 1
    y_pred = slope * x + intercept
    ss_res = np.sum(weights * (y - y_pred) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0
    momentum_score = annualized_returns * r_squared
    return momentum_score, annualized_returns, r_squared


def calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context):
    try:
        price_series = np.append(hist_closes, current_price)
        if len(price_series) < g.lookback_days * 0.8:
            return None
        momentum_score, annualized_returns, r_squared = calculate_momentum_score(price_series, g.lookback_days)
        if momentum_score is None:
            return None
        passed_momentum = (g.min_score_threshold <= momentum_score <= g.max_score_threshold)

        ma_arrangement_factor = 1.0
        if g.enable_ma_arrangement_factor and len(hist_closes) >= 20:
            try:
                ma5 = np.mean(hist_closes[-5:])
                ma10 = np.mean(hist_closes[-10:])
                ma20 = np.mean(hist_closes[-20:])
                if ma5 > ma10 > ma20:
                    if len(hist_closes) >= 60:
                        ma60 = np.mean(hist_closes[-60:])
                        if ma5 > ma10 > ma20 > ma60:
                            ma_arrangement_factor = 1.5
                        else:
                            ma_arrangement_factor = 1.3
                    else:
                        ma_arrangement_factor = 1.3
                elif ma5 > ma10:
                    ma_arrangement_factor = 1.1
                else:
                    ma_arrangement_factor = 0.8
                momentum_score = momentum_score * ma_arrangement_factor
            except Exception:
                ma_arrangement_factor = 1.0

        rs_improvement_factor = 1.0
        if g.enable_relative_strength_factor and len(hist_closes) >= 20:
            try:
                if not hasattr(g, '_benchmark_closes'):
                    bench_df = attribute_history('000300.XSHG', 30, '1d', ['close'], skip_paused=True)
                    if bench_df is not None and len(bench_df) >= 20:
                        g._benchmark_closes = bench_df['close'].values
                if hasattr(g, '_benchmark_closes') and len(g._benchmark_closes) >= 20:
                    stock_ret_10 = hist_closes[-1] / hist_closes[-10] - 1
                    stock_ret_prev = hist_closes[-10] / hist_closes[-20] - 1
                    bench_ret_10 = g._benchmark_closes[-1] / g._benchmark_closes[-10] - 1
                    bench_ret_prev = g._benchmark_closes[-10] / g._benchmark_closes[-20] - 1
                    current_rs = stock_ret_10 - bench_ret_10
                    prev_rs = stock_ret_prev - bench_ret_prev
                    rs_improvement = current_rs - prev_rs
                    if rs_improvement > 0.05:
                        rs_improvement_factor = 1.25
                    elif rs_improvement > 0.02:
                        rs_improvement_factor = 1.15
                    momentum_score = momentum_score * rs_improvement_factor
            except Exception:
                rs_improvement_factor = 1.0

        volume_ratio = get_volume_ratio(hist_volumes, today_vol, context, g.volume_lookback)

        passed_loss_filter = True
        day_ratios = []
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g.loss:
                passed_loss_filter = False

        passed_r2 = r_squared > g.r2_threshold

        passed_ma = True
        ma_value = None
        if len(price_series) >= g.ma_lookback:
            ma_value = np.mean(price_series[-g.ma_lookback:])
            passed_ma = current_price > ma_value * g.ma_threshold
        else:
            passed_ma = False

        premium_rate, passed_premium = calculate_premium_rate(etf, context)

        laplace_value = 0
        laplace_slope = 0
        passed_laplace = False
        if len(price_series) >= 10:
            try:
                laplace_s = g.laplace_s_param_weak if g.is_a_share_weak else g.laplace_s_param_normal
                laplace_values = laplace_filter(price_series, s=laplace_s)
                if len(laplace_values) >= 2:
                    laplace_value = laplace_values[-1]
                    laplace_slope = laplace_values[-1] - laplace_values[-2]
                    passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
            except Exception:
                pass

        return {
            'etf': etf, 'etf_name': etf_name,
            'momentum_score': momentum_score, 'annualized_returns': annualized_returns,
            'r_squared': r_squared, 'current_price': current_price,
            'volume_ratio': volume_ratio, 'day_ratios': day_ratios,
            'premium_rate': premium_rate, 'passed_momentum': passed_momentum,
            'passed_r2': passed_r2, 'passed_ma': passed_ma,
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter, 'passed_premium': passed_premium,
            'ma_value': ma_value, 'laplace_value': laplace_value,
            'laplace_slope': laplace_slope, 'passed_laplace': passed_laplace,
            'ma_arrangement_factor': ma_arrangement_factor, 'rs_improvement_factor': rs_improvement_factor,
        }
    except Exception as e:
        log.debug(f"【指标计算】{etf} {etf_name} 计算失败: {e}")
        return None


def get_volume_ratio(hist_volumes, today_vol, context, lookback_days=None):
    if lookback_days is None:
        lookback_days = g.volume_lookback
    try:
        if hist_volumes is None or len(hist_volumes) < lookback_days:
            return None
        past_n_days_vol = hist_volumes[-lookback_days:]
        if np.any(np.isnan(past_n_days_vol)) or np.any(past_n_days_vol == 0):
            return None
        avg_volume = np.mean(past_n_days_vol)
        if avg_volume == 0:
            return None
        now = context.current_dt
        elapsed_minutes = (now.hour - 9) * 60 + now.minute - 30
        if now.hour >= 13:
            elapsed_minutes -= 90
        elapsed_minutes = max(1, min(elapsed_minutes, 240))
        projected_today_vol = today_vol * (240.0 / elapsed_minutes)
        return projected_today_vol / avg_volume if avg_volume > 0 else 0
    except Exception:
        return None


def calculate_premium_rate(etf, context):
    try:
        etf_price = getattr(g, 'etf_yesterday_close_batch', {}).get(etf)
        if etf_price is None or pd.isna(etf_price):
            etf_price_df = get_price(etf, start_date=context.previous_date, end_date=context.previous_date, fields=['close'])
            if etf_price_df is None or len(etf_price_df) == 0:
                return None, False
            etf_price = etf_price_df['close'].iloc[-1]
        nav = getattr(g, 'etf_yesterday_nav_batch', {}).get(etf)
        if nav is None or pd.isna(nav):
            nav_df = get_extras('unit_net_value', etf, start_date=context.previous_date, end_date=context.previous_date)
            if nav_df is None or len(nav_df) == 0:
                return None, False
            nav = nav_df.iloc[-1].values[0]
        if nav <= 0 or pd.isna(nav):
            return None, False
        premium_rate = (etf_price - nav) / nav * 100
        passed_premium = premium_rate <= g.max_premium_rate
        return premium_rate, passed_premium
    except Exception:
        return None, True


def laplace_filter(price, s=0.05):
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


def update_adaptive_ma(context):
    if not g.adaptive_ma_enabled:
        g.weak_entry_ma_lookback = 10
        g.weak_exit_ma_lookback = 8
        g.weak_entry_below_threshold = 3
        return
    try:
        hs300_df = attribute_history('000300.XSHG', 30, '1d', ['close'])
        if hs300_df is None or len(hs300_df) < 20:
            g.weak_entry_ma_lookback = 10
            g.weak_exit_ma_lookback = 8
            g.weak_entry_below_threshold = 3
            return
        daily_ret = hs300_df['close'].pct_change().dropna()
        recent_vol = daily_ret.tail(10).std() * np.sqrt(252)
        long_vol = daily_ret.tail(20).std() * np.sqrt(252)
        if long_vol <= 0 or np.isnan(long_vol):
            vol_ratio = 1.0
        else:
            vol_ratio = recent_vol / long_vol
        if vol_ratio > 1.5:
            entry_ma, exit_ma, entry_threshold = 5, 3, 2
        elif vol_ratio > 1.2:
            entry_ma, exit_ma, entry_threshold = 7, 5, 2
        elif vol_ratio < 0.7:
            entry_ma, exit_ma, entry_threshold = 20, 18, 3
        else:
            entry_ma, exit_ma, entry_threshold = 10, 8, 3
        g.weak_entry_ma_lookback = entry_ma
        g.weak_exit_ma_lookback = exit_ma
        g.weak_entry_below_threshold = entry_threshold
    except Exception:
        g.weak_entry_ma_lookback = 10
        g.weak_exit_ma_lookback = 8
        g.weak_entry_below_threshold = 3


def check_dispersion_filter(context):
    if not g.enable_dispersion_filter:
        return
    if not hasattr(g, 'ranked_etfs_result') or not g.ranked_etfs_result:
        return
    scores = []
    for m in g.ranked_etfs_result:
        s = m.get('momentum_score')
        if s is not None and s != float('-inf') and not (isinstance(s, float) and np.isnan(s)):
            scores.append(s)
    if len(scores) < 10:
        return
    top_score = scores[0]
    mean_score = np.mean(scores[:10])
    std_score = np.std(scores[:10])
    if std_score <= 0:
        g.target_etfs_list = [g.defensive_etf]
        return
    dispersion_ratio = (top_score - mean_score) / std_score
    g.dispersion_history.append(dispersion_ratio)
    if len(g.dispersion_history) > g.dispersion_window:
        g.dispersion_history.pop(0)
    avg_dispersion = np.mean(g.dispersion_history)
    if avg_dispersion < g.dispersion_low_threshold:
        g.target_etfs_list = [g.defensive_etf]


def check_a_share_weak_period(context):
    today = context.current_dt.date()
    indexes = {
        '大盘': '000300.XSHG', '小盘': '399101.XSHE',
        '创业板': '399006.XSHE', '中证A500': '000510.XSHG'
    }
    above_count = 0
    below_count = 0
    for name, code in indexes.items():
        max_lookback = max(g.weak_entry_ma_lookback, g.weak_exit_ma_lookback)
        df = attribute_history(code, max_lookback + 1, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < max_lookback:
            continue
        current_price = df['close'][-1]
        entry_ma_val = df['close'][-g.weak_entry_ma_lookback:].mean()
        exit_ma_val = df['close'][-g.weak_exit_ma_lookback:].mean()
        if current_price > exit_ma_val:
            above_count += 1
        if current_price < entry_ma_val:
            below_count += 1

    weak_condition_met = (below_count >= g.weak_entry_below_threshold)
    exit_condition_met = (above_count >= 3)

    in_reentry_cooldown = False
    cooldown_days_count = 0
    strong_weak_condition_met = (below_count >= g.strong_weak_reentry_confirm_count)
    if (not g.is_a_share_weak) and g.last_weak_exit_date is not None:
        cooldown_days_count = len(get_trade_days(start_date=g.last_weak_exit_date, end_date=today)) - 1
        in_reentry_cooldown = cooldown_days_count < g.weak_reentry_cooldown_days

    if g.is_a_share_weak and g.weak_start_date is not None:
        g.weak_days_count = len(get_trade_days(start_date=g.weak_start_date, end_date=today))
    else:
        g.weak_days_count = 0
    max_days_exceeded = (g.weak_days_count >= g.max_weak_days)

    if g.is_a_share_weak:
        if max_days_exceeded:
            g.is_a_share_weak = False
            g.weak_start_date = None
            g.weak_days_count = 0
            g.last_weak_exit_date = today
        elif exit_condition_met:
            g.is_a_share_weak = False
            g.weak_start_date = None
            g.weak_days_count = 0
            g.last_weak_exit_date = today
        elif weak_condition_met:
            g.weak_start_date = today
            g.weak_days_count = 0
    else:
        if weak_condition_met:
            if in_reentry_cooldown:
                if strong_weak_condition_met:
                    g.is_a_share_weak = True
                    g.weak_start_date = today
                    g.weak_days_count = 0
            else:
                g.is_a_share_weak = True
                g.weak_start_date = today
                g.weak_days_count = 0

    if g.is_a_share_weak:
        record(走弱期状态=1)
    else:
        record(走弱期状态=0)
    return g.is_a_share_weak


def apply_filters(metrics_list):
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], True),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter),
        ('均线', lambda m: m['passed_ma'], g.enable_ma_filter and not g.is_a_share_weak),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check and not g.is_a_share_weak),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter and not g.is_a_share_weak),
        ('溢价率', lambda m: m['passed_premium'], g.enable_premium_filter and not g.is_a_share_weak),
        ('拉普拉斯滤波', lambda m: m['passed_laplace'], g.enable_laplace_filter and not g.is_a_share_weak),
    ]
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered


def get_final_ranked_etfs(context):
    all_metrics = []
    etf_set = list(g.merged_etf_pool)
    end_date = context.previous_date
    lookback = max(g.lookback_days, g.volume_lookback, g.ma_lookback) + 20
    current_data = get_current_data()
    safe_lookback = lookback + 20
    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d', fields=['close', 'volume'], panel=False)
    today = context.current_dt.date()
    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        return []
    g.etf_yesterday_close_batch = {}
    g.etf_yesterday_nav_batch = {}
    try:
        y_price_df = get_price(etf_set, start_date=end_date, end_date=end_date, fields=['close'], panel=False)
        if y_price_df is not None and not y_price_df.empty:
            g.etf_yesterday_close_batch = y_price_df.groupby('code')['close'].last().to_dict()
        nav_df = get_extras('unit_net_value', etf_set, start_date=end_date, end_date=end_date)
        if nav_df is not None and not nav_df.empty:
            g.etf_yesterday_nav_batch = nav_df.iloc[-1].to_dict()
    except Exception:
        pass
    today_vols = today_vol_df.groupby('code')['volume'].sum() if (today_vol_df is not None and not today_vol_df.empty) else pd.Series(dtype=float)
    close_pivot = hist_df.pivot(index='time', columns='code', values='close')
    volume_pivot = hist_df.pivot(index='time', columns='code', values='volume')
    for etf in etf_set:
        if current_data[etf].paused:
            continue
        if etf not in close_pivot.columns:
            continue
        raw_closes = close_pivot[etf].values
        raw_volumes = volume_pivot[etf].values
        valid_mask = (~np.isnan(raw_volumes)) & (raw_volumes > 0)
        hist_closes = raw_closes[valid_mask]
        hist_volumes = raw_volumes[valid_mask]
        hist_closes = hist_closes[-lookback:]
        hist_volumes = hist_volumes[-lookback:]
        if len(hist_closes) < g.lookback_days:
            continue
        etf_name = get_security_name(etf)
        current_price = current_data[etf].last_price
        today_vol = today_vols.get(etf, 0)
        metrics = calculate_all_metrics_for_etf(etf, etf_name, hist_closes, hist_volumes, current_price, today_vol, context)
        if metrics:
            if metrics['etf'] in {m['etf'] for m in all_metrics}:
                continue
            all_metrics.append(metrics)
    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or (isinstance(score, float) and np.isnan(score)):
            item['momentum_score'] = float('-inf')
    all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    filtered_list = apply_filters(all_metrics)
    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    top_10 = filtered_list[:10]
    if not top_10:
        return []
    score_key = 'momentum_score'
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        ratio = g.score_threshold_ratio if not g.is_a_share_weak else 1.0
        score_threshold = reference_score * ratio
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        candidate_pool = top_10[:]
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    candidate_dict = {item['etf']: item for item in candidate_pool}
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    if len(retained) >= g.holdings_num:
        retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
    else:
        need = g.holdings_num - len(retained)
        remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
        additional = remaining_pool[:need]
        final_result = retained + additional
    return final_result


def execute_sell_trades(context):
    log.info("========== 策略A卖出操作开始 ==========")
    ranked_etfs = getattr(g, 'ranked_etfs_result', [])
    target_etfs = []
    if ranked_etfs:
        for metrics in ranked_etfs[:g.holdings_num]:
            target_etfs.append(metrics['etf'])
    else:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
        else:
            target_etfs = []
    g.target_etfs_list = target_etfs
    current_positions = list(context.portfolio.positions.keys())
    target_set = set(target_etfs)
    sell_count = 0
    for security in current_positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0 and security not in target_set:
            # 只卖出ETF（策略A管理的），不卖股票（策略B管理的）
            if security in g.fixed_etf_pool or security in g.dynamic_etf_pool or security == g.defensive_etf:
                success = smart_order_target_value(security, 0, context)
                if success:
                    sell_count += 1
                    log.info(f"✅ 策略A已卖出ETF: {security}")
    log.info(f"策略A本次共计划卖出{sell_count}只ETF。")
    log.info("========== 策略A卖出操作完成 ==========")


def buy_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【策略A买入流水线】启动...")
    g.pending_buy_etfs = []
    target_etfs = g.target_etfs_list
    if not target_etfs:
        log.info("策略A今日无目标ETF，保持空仓")
        return
    current_positions = set(context.portfolio.positions.keys())
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    # 策略A只用50%资金
    etf_cash_budget = context.portfolio.available_cash * g.capital_ratio
    num_etfs_to_buy = min(len(etfs_to_buy), g.holdings_num)
    if num_etfs_to_buy <= 0:
        return
    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    g.pending_buy_etfs = list(etfs_to_buy)
    execute_buy_with_trend(context, force=False)


def check_intraday_trend(security, context):
    try:
        minute_data = get_price(
            security, end_date=context.current_dt,
            count=g.trend_lookback_minutes, frequency='1m',
            fields=['close'], skip_paused=False, fq='pre'
        )
        if minute_data is None or minute_data.empty:
            return True
        closes = minute_data['close'].values
        closes = closes[closes > 0]
        if len(closes) < 5:
            return False
        x = np.arange(len(closes))
        slope = np.polyfit(x, closes, 1)[0]
        mean_price = closes.mean()
        slope_pct = slope / mean_price * 100 if mean_price > 0 else 0
        return slope_pct > g.trend_slope_threshold
    except Exception:
        return True


def execute_buy_with_trend(context, force=False):
    if not g.pending_buy_etfs:
        return
    current_positions = set(context.portfolio.positions.keys())
    g.pending_buy_etfs = [etf for etf in g.pending_buy_etfs if etf not in current_positions]
    if not g.pending_buy_etfs:
        return
    etfs_to_buy_now = []
    still_pending = []
    for etf in g.pending_buy_etfs:
        if force:
            etfs_to_buy_now.append(etf)
        else:
            is_uptrend = check_intraday_trend(etf, context)
            if is_uptrend:
                etfs_to_buy_now.append(etf)
            else:
                still_pending.append(etf)
    # 策略A使用50%可用现金
    remaining_cash = context.portfolio.available_cash * g.capital_ratio
    total_count = len(etfs_to_buy_now) + len(still_pending)
    for i, etf in enumerate(etfs_to_buy_now):
        if remaining_cash < g.min_money:
            break
        remaining_to_buy = total_count - i
        target_value_for_this_etf = remaining_cash // remaining_to_buy
        if target_value_for_this_etf < g.min_money and remaining_cash >= g.min_money:
            target_value_for_this_etf = remaining_cash
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            remaining_cash -= target_value_for_this_etf
            log.info(f"✅ 策略A ETF {etf} 下单成功")
    g.pending_buy_etfs = still_pending


def check_pending_buys_trend(context):
    if not g.pending_buy_etfs:
        return
    execute_buy_with_trend(context, force=False)


def force_buy_pending(context):
    if not g.pending_buy_etfs:
        return
    execute_buy_with_trend(context, force=True)


def smart_order_target_value(security, target_value, context):
    current_data = get_current_data()
    security_name = get_security_name(security)
    if current_data[security].paused:
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        return False
    current_price = current_data[security].last_price
    if current_price == 0:
        return False
    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < g.min_money:
        return False
    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)
    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            if amount_diff > 0:
                log.info(f"📦 策略A买入{security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}")
            else:
                log.info(f"📤 策略A卖出{security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}")
            return True
        else:
            return False
    return False


def get_security_name(security):
    try:
        if hasattr(g, 'etf_names_dict') and security in g.etf_names_dict:
            return g.etf_names_dict[security]
        return get_security_info(security).display_name
    except Exception:
        return "未知名称"


def check_defensive_etf_available(context):
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    if current_data[defensive_etf].paused:
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        return False
    return True


def trade(context):
    pass


# ============================================================
#            策略B：红利轮动 + 创业板动量
# ============================================================

def prepare_stock_list(context):
    g.main['high_limit_list'] = []
    hold = list(context.portfolio.positions)
    if len(hold) > 0:
        df = get_price(hold, end_date=context.previous_date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False).dropna()
        df = df[df['close'] == df['high_limit']]
        g.main['high_limit_list'] = list(df.code)


def check_stop_loss(context):
    if context.portfolio.total_value > g.highest_value:
        g.highest_value = context.portfolio.total_value
    if g.highest_value > 0:
        drawdown = (g.highest_value - context.portfolio.total_value) / g.highest_value
        g.portfolio_ratio = 0.6 if drawdown > 0.15 else 1.0

    if not g.cyb_stocks_cache:
        g.cyb_stocks_cache = get_index_stocks(g.cyb_index)

    current_data = get_current_data()
    for s in list(context.portfolio.positions):
        p = context.portfolio.positions[s]
        if p.total_amount <= 0 or p.avg_cost <= 0:
            continue
        price = p.price
        avg_cost = p.avg_cost
        profit_rate = price / avg_cost - 1

        is_mom_stock = s in g.cyb_stocks_cache

        if is_mom_stock:
            if profit_rate < g.mom['stop_loss']:
                order_target_value(s, 0)
                print(f'【策略B动量止损】{s} 亏损超过10%，卖出')
                if s not in g.mom['sell_list']:
                    g.mom['sell_list'].append(s)
                g.mom['high_price_dict'].pop(s, None)
                g.mom['buy_date'].pop(s, None)
                continue
            if s not in g.mom['high_price_dict'] or price > g.mom['high_price_dict'][s]:
                g.mom['high_price_dict'][s] = price
            if profit_rate > 0.15:
                highest = g.mom['high_price_dict'][s]
                if (highest - price) / highest > 0.08 and profit_rate < 0.03:
                    order_target_value(s, 0)
                    print(f'【策略B动量止盈】{s} 从高点回撤8%且盈利<3%，卖出')
                    if s not in g.mom['sell_list']:
                        g.mom['sell_list'].append(s)
                    g.mom['high_price_dict'].pop(s, None)
                    g.mom['buy_date'].pop(s, None)
                    continue
        else:
            if profit_rate < -0.08:
                order_target_value(s, 0)
                print(f'【策略B主策略硬止损】{s} 亏损超过8%，卖出')
                if s not in g.main['sell_list']:
                    g.main['sell_list'].append(s)
                g.main['high_price_dict'].pop(s, None)
                g.main['buy_date'].pop(s, None)
                continue
            if s not in g.main['high_price_dict'] or price > g.main['high_price_dict'][s]:
                g.main['high_price_dict'][s] = price
            if profit_rate > 0.10:
                highest = g.main['high_price_dict'][s]
                if (highest - price) / highest > 0.05 and profit_rate < 0.02:
                    order_target_value(s, 0)
                    print(f'【策略B主策略移动止盈】{s} 从高点回撤5%且盈利<2%，卖出')
                    if s not in g.main['sell_list']:
                        g.main['sell_list'].append(s)
                    g.main['high_price_dict'].pop(s, None)
                    g.main['buy_date'].pop(s, None)
                    continue
            if hasattr(p, 'transact_time') and p.transact_time is not None:
                hold_days = (context.current_dt.date() - p.transact_time.date()).days
                if hold_days > 15 and profit_rate < 0.03:
                    order_target_value(s, 0)
                    print(f'【策略B主策略时间止损】{s} 持有{hold_days}天收益{profit_rate:.2%}，低于3%，卖出')
                    if s not in g.main['sell_list']:
                        g.main['sell_list'].append(s)
                    g.main['high_price_dict'].pop(s, None)
                    g.main['buy_date'].pop(s, None)
                    continue


def calc_bbi(code, end_date):
    df = get_price(code, end_date=end_date, frequency='daily', fields=['close'], count=24)
    if len(df) < 24:
        return None
    ma3 = df['close'].rolling(3).mean().iloc[-1]
    ma6 = df['close'].rolling(6).mean().iloc[-1]
    ma12 = df['close'].rolling(12).mean().iloc[-1]
    ma24 = df['close'].rolling(24).mean().iloc[-1]
    return (ma3 + ma6 + ma12 + ma24) / 4


def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


def filter_kcb_stock(stock_list):
    return [stock for stock in stock_list if ((stock[0] != '4') and (stock[0] != '8') and (stock[0:2] != '68'))]


def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < timedelta(days=250)]


def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2, threshold):
    time1 = context.previous_date
    time0 = time1 - timedelta(days=365)
    interval = 1000
    list_len = len(stock_list)
    if list_len == 0:
        return []
    q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
    ).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)
    if list_len > interval:
        for i in range(list_len // interval):
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
            ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[interval*(i+1):min(list_len, interval*(i+2))]))
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    dividend = df.fillna(0).set_index('code')
    dividend = dividend.groupby('code').sum()
    temp_list = list(dividend.index)
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1).set_index('code')
    df = pd.concat([dividend, cap], axis=1, sort=False)
    df['dividend_ratio'] = (df['bonus_amount_rmb']/10000) / df['market_cap']
    df = df.sort_values(by=['dividend_ratio'], ascending=sort)
    df = df[int(p1*len(df)):int(p2*len(df))]
    df = df[df['dividend_ratio'] > 0.03]
    return list(df.index)


def get_stock_list(context):
    yesterday = context.previous_date
    today = context.current_dt
    # 策略B使用50%仓位
    total_value = context.portfolio.total_value * g.portfolio_ratio * g.capital_ratio

    index_data = get_price(g.cyb_index, end_date=yesterday, frequency='daily', fields=['close'], count=20)
    if len(index_data) < 20:
        cyb_above_ma20 = True
    else:
        ma20 = index_data['close'].mean()
        current_price = index_data['close'].iloc[-1]
        cyb_above_ma20 = current_price > ma20
        print(f'【策略B创业板择时】当前{current_price:.2f}，MA20={ma20:.2f}，{"行情好" if cyb_above_ma20 else "行情差"}')

    if cyb_above_ma20:
        cash_main = total_value * 0.5
        cash_mom = total_value * 0.5
        run_mom = True
    else:
        cash_main = total_value
        cash_mom = 0
        run_mom = False
        print('【策略B创业板择时】仅执行红利策略，清空创业板持仓')

    g.cyb_stocks_cache = get_index_stocks(g.cyb_index)

    # ========== 主策略（红利轮动）选股 ==========
    main_buy_list = []
    main_sell_list = []
    initial_list = get_all_securities('stock', today).index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcb_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    stock_list = initial_list
    df_fund = get_fundamentals(query(
            valuation.code,
        ).filter(
            valuation.code.in_(stock_list),
            valuation.pe_ratio.between(5, 50),
            indicator.inc_return.between(5, 100),
            indicator.inc_total_revenue_year_on_year.between(5, 100),
            indicator.inc_net_profit_year_on_year.between(10, 100),
        ))
    stock_list = list(df_fund.code)
    stock_list = get_dividend_ratio_filter_list(context, stock_list, False, 0.00, 0.10, 0.03)
    price_df = get_price(stock_list, end_date=yesterday, frequency='daily', fields=['close'], count=24, panel=False) if len(stock_list)>0 else pd.DataFrame()
    momentum_dict = {}
    valid_stocks = []
    for code in stock_list:
        sub = price_df[price_df['code'] == code]['close'] if len(price_df)>0 else pd.Series()
        if len(sub) < 24:
            continue
        bbi = calc_bbi(code, yesterday)
        if bbi is None:
            continue
        if sub.iloc[-1] > bbi * 0.98:
            ret = (sub.iloc[-1] / sub.iloc[0]) - 1
            momentum_dict[code] = ret
            valid_stocks.append(code)
    if len(valid_stocks) == 0:
        target_list = stock_list[:g.main['stock_num']]
    else:
        sorted_momentum = sorted(momentum_dict.items(), key=lambda x: x[1], reverse=True)
        target_list = [item[0] for item in sorted_momentum[:g.main['stock_num']]]
        if len(target_list) < g.main['stock_num']:
            remaining = [s for s in valid_stocks if s not in target_list]
            for s in stock_list:
                if s in remaining and len(target_list) < g.main['stock_num']:
                    target_list.append(s)
    main_hold = list(context.portfolio.positions)
    g.main['hold_list'] = main_hold
    main_sell_list = [s for s in main_hold if s not in target_list and s not in g.main['high_limit_list']]
    main_buy_list = [s for s in target_list if s not in main_hold]

    main_buy_df = pd.DataFrame(index=[], columns=['name', 'price', 'amount', 'value'])
    if len(main_buy_list) > 0 and cash_main > 0:
        value_per = cash_main / len(main_buy_list)
        df_price = get_price(main_buy_list, end_date=yesterday, frequency='1d', count=1, fields=['close'], fq='pre', panel=False, skip_paused=False, fill_paused=True).set_index('code')
        df_price['today_buy_price'] = round(df_price['close'] * 1.002, 2)
        for s in main_buy_list:
            buy_price = df_price.loc[s, 'today_buy_price']
            amount = 100 * int(value_per / buy_price / 100)
            if amount == 0:
                continue
            main_buy_df.loc[s, 'name'] = get_security_info(s, yesterday).display_name
            main_buy_df.loc[s, 'price'] = buy_price
            main_buy_df.loc[s, 'amount'] = amount
            main_buy_df.loc[s, 'value'] = buy_price * amount

    # ========== 动量策略（创业板龙头）选股 ==========
    mom_buy_df = pd.DataFrame(index=[], columns=['name', 'price', 'amount', 'value'])
    mom_sell_list = []
    if run_mom and cash_mom > 0:
        cyb_stocks = g.cyb_stocks_cache
        cyb_stocks = filter_paused_stock(cyb_stocks)
        cyb_stocks = filter_st_stock(cyb_stocks)
        if len(cyb_stocks) > 0:
            price_df_mom = get_price(cyb_stocks, end_date=yesterday, frequency='daily', fields=['close'], count=31, panel=False)
            mom_dict = {}
            for code in cyb_stocks:
                sub = price_df_mom[price_df_mom['code'] == code]['close'] if len(price_df_mom)>0 else pd.Series()
                if len(sub) >= 31:
                    ret = (sub.iloc[-1] / sub.iloc[0]) - 1
                    mom_dict[code] = ret
            sorted_mom = sorted(mom_dict.items(), key=lambda x: x[1], reverse=True)
            target_mom = [item[0] for item in sorted_mom[:g.mom['stock_num']]]
            mom_hold = [s for s in context.portfolio.positions if s in cyb_stocks]
            g.mom['hold_list'] = mom_hold
            mom_sell_list = [s for s in mom_hold if s not in target_mom]
            mom_buy_list = [s for s in target_mom if s not in mom_hold]

            if len(mom_buy_list) > 0:
                value_per = cash_mom / len(mom_buy_list)
                df_price_mom = get_price(mom_buy_list, end_date=yesterday, frequency='1d', count=1, fields=['close'], fq='pre', panel=False, skip_paused=False, fill_paused=True).set_index('code')
                df_price_mom['today_buy_price'] = round(df_price_mom['close'] * 1.002, 2)
                for s in mom_buy_list:
                    buy_price = df_price_mom.loc[s, 'today_buy_price']
                    amount = 100 * int(value_per / buy_price / 100)
                    if amount == 0:
                        continue
                    mom_buy_df.loc[s, 'name'] = get_security_info(s, yesterday).display_name
                    mom_buy_df.loc[s, 'price'] = buy_price
                    mom_buy_df.loc[s, 'amount'] = amount
                    mom_buy_df.loc[s, 'value'] = buy_price * amount
    else:
        cyb_stocks = g.cyb_stocks_cache
        mom_hold = [s for s in context.portfolio.positions if s in cyb_stocks]
        mom_sell_list = mom_hold
        g.mom['hold_list'] = []

    g.main['sell_list'] = list(set(g.main['sell_list']) | set(main_sell_list))
    g.main['buy_df'] = main_buy_df
    g.mom['sell_list'] = list(set(g.mom['sell_list']) | set(mom_sell_list))
    g.mom['buy_df'] = mom_buy_df

    print(f'【策略B主策略】卖出：{g.main["sell_list"]}，买入：{list(g.main["buy_df"].index)}')
    print(f'【策略B动量策略】卖出：{g.mom["sell_list"]}，买入：{list(g.mom["buy_df"].index)}')


def my_trade(context):
    current_data = get_current_data()
    for s in g.main['sell_list'][:]:
        if current_data[s].last_price < current_data[s].high_limit:
            order_target_value(s, 0)
            g.main['sell_list'].remove(s)
            g.main['high_price_dict'].pop(s, None)
            g.main['buy_date'].pop(s, None)
    for s in g.mom['sell_list'][:]:
        order_target_value(s, 0)
        g.mom['sell_list'].remove(s)
        g.mom['high_price_dict'].pop(s, None)
        g.mom['buy_date'].pop(s, None)

    for s in list(g.main['buy_df'].index):
        row = g.main['buy_df'].loc[s]
        order(s, row['amount'], LimitOrderStyle(row['price']))
        g.main['buy_date'][s] = context.current_dt.date()
    for s in list(g.mom['buy_df'].index):
        row = g.mom['buy_df'].loc[s]
        order(s, row['amount'], LimitOrderStyle(row['price']))
        g.mom['buy_date'][s] = context.current_dt.date()


def check_limit_up(context):
    current_data = get_current_data()
    for s in g.main['high_limit_list'][:]:
        if current_data[s].last_price < current_data[s].high_limit:
            order_target_value(s, 0)
            print(f'【策略B涨停打开】{s} 涨停板打开，卖出')
            g.main['high_limit_list'].remove(s)
            g.main['high_price_dict'].pop(s, None)
            g.main['buy_date'].pop(s, None)
