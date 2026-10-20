# Clone from JoinQuant
# postId: c65b0c1e699181d40d89ea5e90eaa1cc
# backtestId: 1d7d7b23aa55adf9017a85a05161fe0b
# title: 一个适合上班族懒人定投的资产配置策略（年化13%）

from jqdata import *

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.001))

    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.0003, close_commission=0.0003,
        min_commission=5
    ), type='fund')


    g.assets = [
        {'code': '518880.XSHG', 'name': '黄金ETF', 'ratio': 0.15},
        {'code': '159985.XSHE', 'name': '豆粕ETF', 'ratio': 0.05},
        {'code': '501018.XSHG', 'name': '南方原油ETF', 'ratio': 0.05},
        {'code': '512890.XSHG', 'name': '红利ETF', 'ratio': 0.25},
        {'code': '159941.XSHE', 'name': '纳指ETF', 'ratio': 0.20},
        {'code': '511220.XSHG', 'name': '城投债ETF', 'ratio': 0.30}
    ]
    

    run_daily(rebalance,  time='14:00')


def rebalance(context):
    total_value = context.portfolio.total_value
    min_trade_value = 3000

    for asset in g.assets:
        asset_code = asset['code']
        target_ratio = asset['ratio']
        target_value = total_value * target_ratio
        current_position = context.portfolio.positions.get(asset_code, None)

        if current_position is None or current_position.amount == 0:
            continue

        current_value = current_position.value
        diff = current_value - target_value
        if current_value > target_value * 1.01 and diff > min_trade_value:
            order_target_value(asset_code, target_value)

    for asset in g.assets:
        asset_code = asset['code']
        asset_name = asset['name']
        target_ratio = asset['ratio']
        target_value = total_value * target_ratio
        current_position = context.portfolio.positions.get(asset_code, None)

        if current_position is None or current_position.amount == 0:
            if target_value > min_trade_value:
                order_target_value(asset_code, target_value)
        else:
            current_value = current_position.value
            diff = target_value - current_value
            if current_value < target_value * 0.99 and diff > min_trade_value:
                order_target_value(asset_code, target_value)

    log.info(f'调仓完成')