# Clone from JoinQuant
# postId: 9498d93fe9feeb169ad93a2c5fbe524d
# backtestId: 20f194e6d643acaf3a3884c5ac1dc4ee
# title: 多ETF网格交易策略-年化10.61%

# ETF百分比网格策略
# 基于自动网格策略修改，适用于ETF交易

# 导入聚宽函数库
from jqdata import *
import math

# 配置参数
CONFIG = {
    # 网格参数
    'GRID_PERCENTAGE': 0.025,           # 网格间距：2.5%
    'POSITION_RATIO': 0.05,             # 每次交易占单只ETF分配资产比例：5%（1/20）
    'ETF_ALLOCATION_RATIO': 0.10,       # 每只ETF资金分配比例：10%
    'INITIAL_POSITION_RATIO': 0.8,      # 初始建仓比例：50%（可调整）

    # ETF组合配置 - 覆盖不同风格和板块，实现风险分散
    'ETF_PORTFOLIO': [
        '512000.XSHG',  # 券商ETF
        '513050.XSHG',  # 互联网ETF
        '512710.XSHG',  # 军工ETF
        '159928.XSHE',  # 消费ETF
        '512480.XSHG',  # 半导体ETF
        '159949.XSHE',  # 创业板50ETF
        '510880.XSHG',  # 红利ETF
        '510500.XSHG',  # 中证500
        '518880.XSHG',  # 黄金ETF
        '513100.XSHG',  # 纳指ETF
    ]
}

# CONFIG = {
#     # 网格参数
#     'GRID_PERCENTAGE': 0.025,           # 网格间距
#     'POSITION_RATIO': 0.05,             # 每次交易占单只ETF分配资产比例
#     'ETF_ALLOCATION_RATIO': 1,          # 每只ETF资金分配比例
#     'INITIAL_POSITION_RATIO': 0.5,      # 初始建仓比例：50%（可调整）

#     # ETF组合配置 - 覆盖不同风格和板块，实现风险分散
#     'ETF_PORTFOLIO': [
#         '601888.XSHG',
#     ]
# }

# 初始化函数
def initialize(context):
    """策略初始化函数，在策略启动时调用一次"""
    # 设置基准为沪深300指数
    set_benchmark('000300.XSHG')

    # 开启动态复权模式（真实价格）
    set_option('use_real_price', True)

    # 设置交易费用（ETF基金）
    set_order_cost(OrderCost(
        open_tax=0,                # 开仓印花税
        close_tax=0,               # 平仓印花税，卖出时收取千分之一
        open_commission=0.0001,    # 开仓佣金，万分之三
        close_commission=0.0001,   # 平仓佣金，万分之三
        min_commission=0           # 最低佣金，5元
    ), type='etf')

    # 设置滑点
    set_slippage(FixedSlippage(0.002))

    # 设置每分钟运行一次（1分钟级别回测）
    run_daily(execute_multi_etf_grid_strategy, time='every_bar')

    # 初始化多ETF网格状态管理
    g.etf_grids = {}  # 存储每只ETF的网格状态
    g.initial_positions = {}  # 存储每只ETF的初始建仓状态

    # 为每只ETF初始化网格状态
    for etf_code in CONFIG['ETF_PORTFOLIO']:
        g.etf_grids[etf_code] = {
            'last_grid_buy': None,
            'last_grid_sell': None,
            'grid_initialized': False
        }
        g.initial_positions[etf_code] = False

    log.info("=== 多ETF网格策略初始化 ===")
    total_capital = context.portfolio.total_value
    log.info("总资产: {:.2f}元".format(total_capital))
    log.info("ETF数量: {}只".format(len(CONFIG['ETF_PORTFOLIO'])))
    log.info("每只ETF分配: {:.2f}元".format(total_capital * CONFIG['ETF_ALLOCATION_RATIO']))
    log.info("初始建仓比例: {:.1f}%".format(CONFIG['INITIAL_POSITION_RATIO']*100))
    log.info("初始建仓金额: {:.2f}元".format(total_capital * CONFIG['ETF_ALLOCATION_RATIO'] * CONFIG['INITIAL_POSITION_RATIO']))
    log.info("单笔交易金额: {:.2f}元".format(total_capital * CONFIG['ETF_ALLOCATION_RATIO'] * CONFIG['POSITION_RATIO']))
    log.info("网格间距: {:.1f}%".format(CONFIG['GRID_PERCENTAGE']*100))

    # 输出ETF组合信息
    for etf_code in CONFIG['ETF_PORTFOLIO']:
        log.info("  - {}".format(etf_code))


# 盘前处理函数
def before_trading_start(context):
    """每日交易开始前调用，用于初始化当日数据"""
    try:
        # 检查所有ETF的网格参数是否已初始化
        for etf_code in CONFIG['ETF_PORTFOLIO']:
            if not g.etf_grids[etf_code]['grid_initialized']:
                initialize_etf_grid_params(context, etf_code)

        # 输出网格状态概览
        log.info("=== 网格状态概览 ===")
        for etf_code in CONFIG['ETF_PORTFOLIO']:
            grid_info = g.etf_grids[etf_code]

            if grid_info['grid_initialized']:
                log.info("{} - 买入基准: {:.4f}, 卖出基准: {:.4f}".format(
                    etf_code, grid_info['last_grid_buy'], grid_info['last_grid_sell']))
            else:
                log.warning("{} - 网格参数未初始化".format(etf_code))

    except Exception as e:
        log.error("盘前处理异常: {}".format(str(e)))


# handle_data函数已移除，使用execute_multi_etf_grid_strategy统一处理所有逻辑


# 盘后处理函数
def after_trading_end(context):
    """每日交易结束后调用"""
    try:
        log.info("=== 交易日结束 - 组合总览 ===")
        log.info("总资产: {:.2f}元".format(context.portfolio.total_value))
        log.info("可用资金: {:.2f}元".format(context.portfolio.available_cash))

        # 记录各ETF持仓情况
        total_position_value = 0
        for etf_code in CONFIG['ETF_PORTFOLIO']:
            position = context.portfolio.positions[etf_code]
            current_price = get_current_price_history(etf_code)
            if current_price:
                position_value = position.total_amount * current_price
                total_position_value += position_value

                log.info("{}: {}股, 价格: {:.4f}元, 市值: {:.2f}元".format(
                    etf_code, position.total_amount, current_price, position_value))

                # 记录网格状态
                grid_info = g.etf_grids[etf_code]
                if grid_info['grid_initialized']:
                    log.info("  网格状态 - 买入基准: {:.4f}, 卖出基准: {:.4f}".format(
                        grid_info['last_grid_buy'], grid_info['last_grid_sell']))
            else:
                log.warning("{} 无法获取当前价格".format(etf_code))

        log.info("持仓总市值: {:.2f}元".format(total_position_value))
        if context.portfolio.total_value > 0:
            log.info("仓位比例: {:.2f}%".format((total_position_value/context.portfolio.total_value)*100))

    except Exception as e:
        log.error("盘后处理异常: {}".format(str(e)))


# 对数网格计算函数
def calculate_log_grid(center_price, grid_percentage=0.025):
    """
    计算对数网格的买入和卖出价格
    使用对数方法确保网格完全对称，避免漂移
    """
    try:
        # 计算对数网格间距
        grid_size = math.log(1 + grid_percentage)

        # 在对数空间进行加减运算
        ln_center = math.log(center_price)
        ln_sell = ln_center + grid_size
        ln_buy = ln_center - grid_size

        # 转换回价格空间
        sell_price = math.exp(ln_sell)
        buy_price = math.exp(ln_buy)

        return sell_price, buy_price

    except Exception as e:
        log.error(f"对数网格计算异常: {str(e)}")
        # 降级到线性计算
        sell_price = center_price * (1 + grid_percentage)
        buy_price = center_price * (1 - grid_percentage)
        return sell_price, buy_price


# 初始化单个ETF网格参数
def initialize_etf_grid_params(context, etf_code):
    """初始化单个ETF的网格参数"""
    try:
        # 获取当前价格
        current_price = get_current_price_history(etf_code)
        if current_price is None:
            current_price = 1.0  # 默认价格

        # 使用对数网格设置初始位置（买入基准=当前价格，卖出基准=当前价格+2.5%）
        g.etf_grids[etf_code]['last_grid_buy'] = current_price
        g.etf_grids[etf_code]['last_grid_sell'] = current_price * (1 + CONFIG['GRID_PERCENTAGE'])
        g.etf_grids[etf_code]['grid_initialized'] = True

        log.info("网格初始化 - {}, 当前价格: {:.4f}, 买入基准: {:.4f}, 卖出基准: {:.4f}".format(
            etf_code, current_price, g.etf_grids[etf_code]['last_grid_buy'], g.etf_grids[etf_code]['last_grid_sell']))

    except Exception as e:
        log.error("{}网格参数初始化异常: {}".format(etf_code, str(e)))
        # 使用默认值
        current_price = 1.0
        g.etf_grids[etf_code]['last_grid_buy'] = current_price
        g.etf_grids[etf_code]['last_grid_sell'] = current_price * (1 + CONFIG['GRID_PERCENTAGE'])
        g.etf_grids[etf_code]['grid_initialized'] = True


# 获取动态总资产
def get_dynamic_total_capital(context):
    """获取动态总资产"""
    return context.portfolio.total_value


# 设置单个ETF初始持仓
def setup_etf_initial_position(context, etf_code):
    """设置单个ETF的初始持仓"""
    try:
        # 获取当前价格
        current_price = get_current_price_history(etf_code)
        if current_price is None:
            log.warning("{} 无法获取当前价格，跳过初始建仓".format(etf_code))
            g.initial_positions[etf_code] = True
            return

        # 使用配置的初始建仓比例进行建仓
        total_capital = get_dynamic_total_capital(context)
        etf_allocation_value = total_capital * CONFIG['ETF_ALLOCATION_RATIO']
        initial_value = etf_allocation_value * CONFIG['INITIAL_POSITION_RATIO']

        # 计算可买入股数，ETF需要为100的倍数
        raw_shares = initial_value / current_price
        initial_shares = int(raw_shares / 100) * 100  # 向下取整到100的倍数

        # 确保至少交易100股
        if initial_shares < 100:
            initial_shares = 100

        if initial_shares >= 100:
            order_id = order(etf_code, initial_shares)
            if order_id:
                g.initial_positions[etf_code] = True
                log.info("✅ {}初始建仓完成 - 数量: {}股, 金额: {:.2f}元, 订单ID: {}".format(
                    etf_code, initial_shares, initial_shares * current_price, order_id))
            else:
                log.error("{}初始建仓失败".format(etf_code))
        else:
            log.warning("{}资金不足，无法进行初始建仓 - 需要: {}股".format(etf_code, initial_shares))
            g.initial_positions[etf_code] = True  # 防止重复尝试

    except Exception as e:
        log.error("{}初始建仓异常: {}".format(etf_code, str(e)))


# 执行多ETF网格交易策略
def execute_multi_etf_grid_strategy(context):
    """执行多ETF网格交易策略主逻辑"""
    try:
        # 设置所有ETF的初始持仓（仅在第一次运行时）
        for etf_code in CONFIG['ETF_PORTFOLIO']:
            if not g.initial_positions[etf_code]:
                setup_etf_initial_position(context, etf_code)

        # 遍历所有ETF执行网格策略
        for etf_code in CONFIG['ETF_PORTFOLIO']:
            # 确保该ETF网格已初始化
            if not g.etf_grids[etf_code]['grid_initialized']:
                continue

            # 获取当前价格
            current_price = get_current_price_history(etf_code)
            if current_price is None:
                continue

            # 计算网格触发价格（基于2.5%间距）
            sell_trigger, _ = calculate_log_grid(g.etf_grids[etf_code]['last_grid_sell'], CONFIG['GRID_PERCENTAGE'])
            _, buy_trigger = calculate_log_grid(g.etf_grids[etf_code]['last_grid_buy'], CONFIG['GRID_PERCENTAGE'])

            log.info("{}网格监控 | 当前: {:.4f} | 买入触发: <{:.4f} | 卖出触发: >{:.4f}".format(
                etf_code, current_price, buy_trigger, sell_trigger))

            # 检查是否触发卖出
            if current_price >= sell_trigger:
                execute_etf_sell(context, etf_code, current_price, sell_trigger)

            # 检查是否触发买入
            elif current_price <= buy_trigger:
                execute_etf_buy(context, etf_code, current_price, buy_trigger)

    except Exception as e:
        log.error("多ETF网格策略执行异常: {}".format(str(e)))


# 执行单个ETF卖出操作
def execute_etf_sell(context, etf_code, current_price, trigger_price):
    """执行单个ETF的网格卖出操作"""
    try:
        # 计算本次交易股数（该ETF分配资产的1/20）
        total_capital = get_dynamic_total_capital(context)
        etf_allocation_value = total_capital * CONFIG['ETF_ALLOCATION_RATIO']
        trade_value = etf_allocation_value * CONFIG['POSITION_RATIO']

        # 计算交易股数，ETF需要为100的倍数
        raw_shares = trade_value / trigger_price
        trade_shares = int(raw_shares / 100) * 100  # 向下取整到100的倍数

        # 确保至少交易100股
        if trade_shares < 100:
            trade_shares = 100

        # 获取当前持仓
        position = context.portfolio.positions[etf_code]

        if position.total_amount >= trade_shares and trade_shares > 0:
            # 计算可卖出数量
            sellable_amount = position.closeable_amount

            if sellable_amount >= trade_shares:
                # 执行卖出
                order_id = order(etf_code, -trade_shares)

                if order_id:
                    # 使用对数网格更新位置
                    g.etf_grids[etf_code]['last_grid_sell'] = trigger_price
                    _, g.etf_grids[etf_code]['last_grid_buy'] = calculate_log_grid(trigger_price, CONFIG['GRID_PERCENTAGE'])

                    log.info("✅ {}网格卖出 - 价格: {:.4f}, 触发价: {:.4f}, 数量: {}股, 金额: {:.2f}元, 订单ID: {}".format(
                        etf_code, current_price, trigger_price, trade_shares, trade_shares * trigger_price, order_id))

                    # 更新后的网格状态
                    log.info("{}网格更新 - 新买入基准: {:.4f}, 新卖出基准: {:.4f}".format(
                        etf_code, g.etf_grids[etf_code]['last_grid_buy'], g.etf_grids[etf_code]['last_grid_sell']))
                else:
                    log.warning("❌ {}网格卖出失败 - 价格: {:.4f}".format(etf_code, current_price))
            else:
                log.warning("❌ {}可卖出数量不足 - 可卖: {}股, 需要: {}股".format(
                    etf_code, sellable_amount, trade_shares))
        else:
            log.warning("❌ {}持仓不足 - 当前持仓: {}股, 需要: {}股".format(
                etf_code, position.total_amount, trade_shares))

    except Exception as e:
        log.error("{}网格卖出异常: {}".format(etf_code, str(e)))


# 执行单个ETF买入操作
def execute_etf_buy(context, etf_code, current_price, trigger_price):
    """执行单个ETF的网格买入操作"""
    try:
        # 计算本次交易股数（该ETF分配资产的1/20）
        total_capital = get_dynamic_total_capital(context)
        etf_allocation_value = total_capital * CONFIG['ETF_ALLOCATION_RATIO']
        trade_value = etf_allocation_value * CONFIG['POSITION_RATIO']

        # 计算交易股数，ETF需要为100的倍数
        raw_shares = trade_value / trigger_price
        trade_shares = int(raw_shares / 100) * 100  # 向下取整到100的倍数

        # 确保至少交易100股
        if trade_shares < 100:
            trade_shares = 100

        # 检查可用资金
        available_cash = context.portfolio.available_cash
        required_cash = trigger_price * trade_shares

        if available_cash >= required_cash and trade_shares > 0:
            # 执行买入
            order_id = order(etf_code, trade_shares)

            if order_id:
                # 使用对数网格更新位置
                g.etf_grids[etf_code]['last_grid_buy'] = trigger_price
                g.etf_grids[etf_code]['last_grid_sell'], _ = calculate_log_grid(trigger_price, CONFIG['GRID_PERCENTAGE'])

                log.info("✅ {}网格买入 - 价格: {:.4f}, 触发价: {:.4f}, 数量: {}股, 金额: {:.2f}元, 订单ID: {}".format(
                    etf_code, current_price, trigger_price, trade_shares, trade_shares * trigger_price, order_id))

                # 更新后的网格状态
                log.info("{}网格更新 - 新买入基准: {:.4f}, 新卖出基准: {:.4f}".format(
                    etf_code, g.etf_grids[etf_code]['last_grid_buy'], g.etf_grids[etf_code]['last_grid_sell']))
            else:
                log.warning("❌ {}网格买入失败 - 价格: {:.4f}".format(etf_code, current_price))
        else:
            log.warning("❌ {}资金不足 - 可用: {:.2f}元, 需要: {:.2f}元".format(
                etf_code, available_cash, required_cash))

    except Exception as e:
        log.error("{}网格买入异常: {}".format(etf_code, str(e)))


# 辅助函数：获取历史价格（用于没有data参数的函数）
def get_current_price_history(security):
    """使用attribute_history获取最新价格"""
    try:
        hist = attribute_history(security, 1, '1m', ['close'])
        if len(hist) > 0:
            return hist['close'][0]
        return None
    except Exception as e:
        log.error("获取历史价格异常: {}".format(str(e)))
        return None


