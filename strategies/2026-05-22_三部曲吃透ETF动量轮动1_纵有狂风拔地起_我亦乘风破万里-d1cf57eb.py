# Clone from JoinQuant
# postId: d1cf57eb50bab9595ba186cf78a50c23
# backtestId: 0ff612d176226cdefa20ee375194cd2f
# title: 【三部曲吃透ETF动量轮动1】纵有狂风拔地起，我亦乘风破万里

import jqdata
import numpy as np
import pandas as pd
import math
from collections import defaultdict
from jqfactor import *

def initialize(context):
    """
    初始化函数，在整个回测/模拟中最开始执行一次
    """
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 用真实价格交易
    set_option('use_real_price', True)
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    # 1. 全局参数设置
    g.m_days = 21  # 动量计算天数
    g.max_score = 6  # 动量分数上限阈值
    g.min_score = 0
    g.score_threshold_multiplier = 1.2 # 动量分数增长阈值倍数
    
    # 用于调试的变量
    g.max_observed_score = float('-inf')
    g.yesterday_scores = {}  # 存储前一天的ETF分数
    
    # 2. ETF池设置
    # 注意：已将代码后缀从.SS/.SZ转换为聚宽的.XSHG/.XSHE
    update_etf_pool(context)

    g.safe_haven_etf = '160513.XSHE'  # 避险资产ETF

    # 3. 交易设置
    # 设置基准
    set_benchmark('159919.XSHE')
    # 使用真实价格回测，更贴近实盘
    set_option('use_real_price', True)
    # 设置交易成本：佣金万分之一，最低0.1元。聚宽中ETF/LOF同属'fund'类型
    set_order_cost(OrderCost(open_commission=0.0001, close_commission=0.0001, min_commission=0.1), type='fund')
    # 设置滑点
    set_slippage(FixedSlippage(0.000))

    # 4. 定时任务
    # 每天 9:40 执行策略的调仓逻辑
    run_daily(rebalance_logic, time='9:35')
    # 每天 10:45 执行检查逻辑，确认调仓是否成功
    run_daily(check_rebalance, time='10:35')
    # 每天 15:30 (收盘后) 记录账户信息
    run_daily(log_portfolio_info, time='15:30')
    
    log.info("策略初始化完成")

def after_code_changed(context):
    """
    代码修改后执行的函数，用于更新全局变量（如股票池）
    """
    log.info("检测到代码修改，正在更新全局变量...")
    update_etf_pool(context)
    log.info("全局变量更新完成。")

def update_etf_pool(context):
    """
    更新ETF池的全局变量
    """
    g.etf_pool = [
        '518880.XSHG',  # 黄金ETF
        '161226.XSHE',  # (白银JJ)
        '501018.XSHG',  # 南方原油etf
        '159985.XSHE',  # 豆粕etf
        '517520.XSHG',  # 黄金股
        '513520.XSHG',  # 日经ETF
        '513100.XSHG',  # 纳指ETF
        '513300.XSHG',  # (纳斯达克ETF)
        '513400.XSHG',  # (道琼斯)
        '159529.XSHE',  # (标普消费ETF)
        '513030.XSHG',  # (德国30)
        '159329.XSHE',  # (沙特ETF)
        '513130.XSHG',  # 恒生科技ETF
        '513090.XSHG',  # (香港证券etf)
        '513120.XSHG',  # (香港创新药)
        '159206.XSHE',  # (卫星ETF).
        '159218.XSHE',  # (卫星产业ETF)
        '159227.XSHE',  # (航天航空ETF)
        '159565.XSHE',  # (汽车零部件ETF)
        '562500.XSHG',  # (机器人)
        '159819.XSHE',  # (人工智能)
        '159363.XSHE',  # (创业板人工智能TFHB)
        '512480.XSHG',  # (半导体)
        '159516.XSHE',  # (半导体设备)
        '512760.XSHG',  # (存储芯片)
        '515880.XSHG',  # (通信ETF)
        '515230.XSHG',  # 软件ETF
        '515050.XSHG',  # (5GETF)
        '159786.XSHE',  # (VRETF)
        '159890.XSHE',  # (云计算ETF)
        '516160.XSHG',  # (新能源)
        '515790.XSHG',  # (光伏ETF)
        '159755.XSHE',  # (电池ETF)
        '512660.XSHG',  # (军工ETF)
        '159732.XSHE',  # (消费电子)
        '159992.XSHE',  # (创新药XY)
        '159852.XSHE',  # (软件ETF)
        '159851.XSHE',  # (金融科技ETF)
        '159869.XSHE',  # (游戏ETF)
        '516780.XSHG',  # (稀土ETF)
        '159928.XSHE',  # (消费ETF)
        '512690.XSHG',  # (酒ETF)
        '515170.XSHG',  # (食品饮料ETF)
        '512010.XSHG',  # (医药ETF)
        '512980.XSHG',  # (传媒ETF)
        '159378.XSHE',  # (通用航空ETF)
        '159611.XSHE',  # (电力ETF)
        '159766.XSHE',  # (旅游ETF)
        '515220.XSHG',  # (煤炭ETF)
        '159865.XSHE',  # (养殖ETF)
        '562800.XSHG',  # (稀有金属)
        '560860.XSHG',  # 工业有色ETF
        '510050.XSHG',  # 上证50etf
        '510300.XSHG',  # 沪深300etf
        '159922.XSHE',  # 中证500etf
        '159531.XSHE',  # 中证2000ETF
        '159915.XSHE',  # 创业板etf
        '588080.XSHG',  # (科创板50)
        '588380.XSHG',  # (双创50ETF)
        '160211.XSHE',  # 国泰小盘
        '512880.XSHG',  # 证券ETF
        '512800.XSHG',  # 银行ETF
        '510880.XSHG',  # 红利ETF
        '511090.XSHG',  # 30年国债ETF
    ]
    log.info(f"ETF池已更新，共包含 {len(g.etf_pool)} 只ETF。")


def rebalance_logic(context):
    """
    每日调仓逻辑函数，在每天9:35被调用
    """
    log.info("--- {} 触发每日调仓逻辑 ---".format(context.current_dt))
    
    # 1. 计算ETF排名，确定目标ETF
    ranked_etfs = get_etf_rank(context, g.etf_pool)
    
    # 如果有符合条件的ETF，选择排名第一的；否则，选择避险资产
    if ranked_etfs:
        target_etf = ranked_etfs[0]
        log.info(f"动量计算完成，目标ETF为: {get_security_info(target_etf).display_name} ({target_etf})")
    else:
        # target_etf = g.safe_haven_etf
        # log.info(f"无符合动量条件的ETF，切换至避险资产: {get_security_info(target_etf).display_name} ({target_etf})")
        target_etf = None
        log.info(f"无符合动量条件的ETF")

    # 执行调仓
    execute_rebalance(context, target_etf)

def check_rebalance(context):
    """
    检查调仓是否成功，若未成功则重新执行调仓
    """
    log.info("--- {} 触发调仓检查逻辑 ---".format(context.current_dt))
    
    # 重新计算ETF排名，使用最新的价格数据
    ranked_etfs = get_etf_rank(context, g.etf_pool)
    
    if ranked_etfs:
        target_etf = ranked_etfs[0]
        log.info(f"检查时的目标ETF为: {get_security_info(target_etf).display_name} ({target_etf})")
    else:
        target_etf = None
        log.info(f"检查时无符合动量条件的ETF")

    # 检查当前持仓是否与目标一致
    current_positions = list(context.portfolio.positions.keys())
    
    # 如果目标ETF已经是唯一持仓，则无需调仓
    if target_etf is not None:
        if len(current_positions) == 1 and current_positions[0] == target_etf:
            log.info(f"目标 {target_etf} 已满仓持有，调仓成功。")
            return
        else:
            log.info(f"持仓与目标不符，执行二次调仓。")
    else:
        if len(current_positions) == 0:
            log.info("当前为空仓，调仓成功。")
            return
        else:
            log.info("应为空仓但仍有持仓，执行二次调仓。")

    # 执行调仓
    execute_rebalance(context, target_etf)

def execute_rebalance(context, target_etf):
    """
    执行实际的调仓操作
    """
    current_positions = list(context.portfolio.positions.keys())
    
    # 如果目标ETF已经是唯一持仓，则无需调仓
    if len(current_positions) == 1 and current_positions[0] == target_etf:
        log.info(f"目标 {target_etf} 已满仓持有，无需调仓。")
        return

    # 卖出非目标资产
    for security in current_positions:
        if security != target_etf:
            log.info(f"卖出非目标资产: {get_security_info(security).display_name} ({security})")
            order_target(security, 0) # 卖出全部仓位
            
    # 买入目标资产
    # 使用 order_target_value 将全部资产配置到目标ETF上
    # 聚宽会自动处理卖出后资金到账和计算买入数量的过程
    if target_etf:
        log.info(f"将全部资产调仓至目标ETF: {get_security_info(target_etf).display_name} ({target_etf})")
        order_target_value(target_etf, context.portfolio.total_value)
    else:
        log.info("保持空仓状态")

def get_etf_rank(context, etf_pool):
    """
    计算ETF池中各ETF的动量得分并排名
    """
    data = pd.DataFrame(index=etf_pool, columns=["annualized_returns", "r2", "score"])
    print_data = {}
    filtered_out = []  # 记录被过滤掉的ETF
    high_score_etfs = []  # 记录超过阈值的ETF

    for etf in etf_pool:
        # 获取过去 g.m_days 的收盘价历史数据
        prices = attribute_history(etf, g.m_days, '1d', ['close'])['close']
        
        if prices.empty or len(prices) < g.m_days:
            continue

        # 核心计算逻辑：加权线性回归
        y = np.log(prices.values)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))

        try:
            # 计算年化收益率
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            annualized_returns = math.exp(slope * 250) - 1
            data.loc[etf, "annualized_returns"] = annualized_returns

            # 计算R2
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot else 0
            data.loc[etf, "r2"] = r2

            # 计算得分
            score = annualized_returns * r2
            data.loc[etf, "score"] = score
            
            # 更新最大观察到的分数
            if score > g.max_observed_score:
                g.max_observed_score = score
                
            etf_name = get_security_info(etf).display_name
            print_data[etf_name] = score

        except Exception as e:
            log.warning(f"计算ETF {etf} 得分时出错: {e}")
            continue

    # 过滤不符合条件的ETF，并按得分降序排列
    data.dropna(inplace=True)
    
    # 分别应用上下限过滤
    above_min = data.query(f"score >= {g.min_score}")
    below_max = data.query(f"score <= {g.max_score}")
    
    # 检查是否有ETF超过阈值
    above_threshold = data.query(f"score > {g.max_score}")
    
    if len(above_threshold) > 0:
        # 有ETF超过阈值，执行新逻辑
        high_score_etfs = above_threshold.index.tolist()
        log.info(f"发现 {len(high_score_etfs)} 只ETF超过阈值: {[get_security_info(etf).display_name for etf in high_score_etfs]}")
        
        # 计算前一天的分数
        yesterday_scores = {}
        for etf in high_score_etfs:
            # 获取过去 g.m_days+1 天的收盘价历史数据，以便计算t-1日分数
            prices = attribute_history(etf, g.m_days + 1, '1d', ['close'])['close']
            
            if prices.empty or len(prices) < g.m_days + 1:
                continue

            # 计算t-1日的分数（使用前g.m_days天的数据）
            yesterday_prices = prices[:-1]  # 去掉最后一天，保留前g.m_days天
            
            # 核心计算逻辑：加权线性回归
            y = np.log(yesterday_prices.values)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))

            try:
                # 计算年化收益率
                slope, intercept = np.polyfit(x, y, 1, w=weights)
                annualized_returns = math.exp(slope * 250) - 1

                # 计算R2
                ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
                ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot else 0

                # 计算t-1日得分
                yesterday_score = annualized_returns * r2
                yesterday_scores[etf] = yesterday_score
                
            except Exception as e:
                log.warning(f"计算ETF {etf} t-1日得分时出错: {e}")
                continue
        
        # 更新g.yesterday_scores
        g.yesterday_scores = yesterday_scores.copy()
        
        # 根据新逻辑筛选ETF
        qualified_etfs = []
        for etf in high_score_etfs:
            if etf in g.yesterday_scores:
                t_day_score = data.loc[etf, "score"]
                t_minus_1_score = g.yesterday_scores[etf]
                
                # 检查t日分数是否大于等于t-1日分数的1.5倍
                if t_day_score >= t_minus_1_score * g.score_threshold_multiplier:
                    qualified_etfs.append(etf)
                    log.info(f"{get_security_info(etf).display_name}({etf}): t日分数 {t_day_score:.4f} >= t-1日分数 {t_minus_1_score:.4f} * {g.score_threshold_multiplier} = {t_minus_1_score * g.score_threshold_multiplier:.4f}")
                else:
                    log.info(f"{get_security_info(etf).display_name}({etf}): t日分数 {t_day_score:.4f} < t-1日分数 {t_minus_1_score:.4f} * {g.score_threshold_multiplier} = {t_minus_1_score * g.score_threshold_multiplier:.4f}，不进入排名")
            else:
                # 如果没有前一天的分数，则使用原逻辑
                qualified_etfs.append(etf)
        
        # 对符合条件的ETF按分数降序排列
        if qualified_etfs:
            qualified_data = data.loc[qualified_etfs]
            valid_data = qualified_data.sort_values(by="score", ascending=False)
        else:
            # 如果没有符合条件的ETF，按照原逻辑处理
            valid_data = data.query(
                f"{g.min_score} <= score <= {g.max_score}"  # 仅保留符合范围的ETF
            ).sort_values(by="score", ascending=False)
    else:
        # 没有ETF超过阈值，沿用原逻辑
        valid_data = data.query(
            f"{g.min_score} <= score <= {g.max_score}"  # 仅保留符合范围的ETF
        ).sort_values(by="score", ascending=False)

    # 输出过滤信息
    if high_score_etfs:
        log.info(f"超过阈值({g.max_score})的ETF: {', '.join([f'{get_security_info(etf).display_name}({etf})' for etf in high_score_etfs])}")

    # 打印排名靠前的ETF
    top_etfs_info = []
    for etf_code in valid_data.index.tolist():
        etf_name = get_security_info(etf_code).display_name
        score_val = print_data.get(etf_name, 'N/A')
        top_etfs_info.append(f"{etf_name} ({score_val:.4f})")
        
    log.info("ETF动量评分排名: {}".format(' > '.join(top_etfs_info)))
    
    # 每周打印一次最大观察分数
    if context.current_dt.weekday() == 0:  # 周一
        log.info(f"截至今日的最大观察动量分数: {g.max_observed_score:.4f}")
        log.info(f"前一天的分数记录: {[(get_security_info(etf).display_name, g.yesterday_scores.get(etf, 'N/A')) for etf in g.yesterday_scores]}")
    
    return valid_data.index.tolist()

def log_portfolio_info(context):
    """
    每日收盘后记录并打印账户信息
    """
    log.info("="*30 + " 每日收益统计 " + "="*30)
    log.info(f"收盘总资产: {context.portfolio.total_value:.2f}")
    log.info(f"可用现金: {context.portfolio.available_cash:.2f}")
    log.info(f"持仓市值: {context.portfolio.positions_value:.2f}")
    log.info(f"累计收益率: {context.portfolio.returns:.2%}")
    
    # 打印当前持仓
    if not context.portfolio.positions:
        log.info("当前空仓")
    else:
        log.info("当前持仓:")
        for security, position in context.portfolio.positions.items():
            etf_name = get_security_info(security).display_name
            log.info(f"  {etf_name}({security}): 数量 {position.total_amount}, "
                    f"价值 {position.value:.2f}, 成本 {position.avg_cost:.3f}")
    log.info("="*75)