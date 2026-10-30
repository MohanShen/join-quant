# Clone from JoinQuant
# postId: d808e7766c72714586f2ce0f23df1339
# backtestId: d426b85b9a8375185f410639e28d76f5
# title: 持仓ETF由于发生分红，被模拟盘判定为大幅下跌

# 克隆自聚宽文章：https://www.joinquant.com/post/70070
# 标题：稳健低回撤副策略研究-全天候资产轮动引擎V3.0版
# 作者：承影

"""
全天候资产轮动引擎 v3.0
——基于均线偏离度的多资产动态再平衡系统

架构：
    SignalEngine  → 信号计算层（均线偏离度 → 五档仓位映射）
    RiskBudget    → 风险预算层（现金底仓 + 风险资产上限约束）
    CashManager   → 现金管理层（场内货基自动归集/赎回）
    Executor      → 交易执行层（先卖后买 + 阈值过滤 + 滑点缓冲）
"""


"""
用法：通达信打开公式管理->新建公式，把下面的代码直接复制粘贴进去，给公式取个名称保存，
然后在k线副图选择刚才的公式名称就可以了

{==================================================}
{       动量曲线通达信指标 - 长期+短期+风控           }
{  对应PYTHON: CALCULATE_MOMENTUM_METRICS 函数       }
{==================================================}

{========== 参数设置 ==========}
N_LONG:=25;      {长期动量计算周期 G.LOOKBACK_DAYS}
N_SHORT:=10;     {短期动量计算周期 G.SHORT_LOOKBACK_DAYS}
SHORT_TH:=0;     {短期动量阈值 G.SHORT_MOMENTUM_THRESHOLD}
LOSS:=0.97;      {近3日跌幅止损线 G.LOSS}


{==================================================}
{              一、长期动量计算（加权回归）            }
{  PYTHON: NP.POLYFIT(X, LOG(价格), 1, W=WEIGHTS)   }
{==================================================}

{1. 对数价格序列}
LNP:=LN(C);

{2. 线性回归斜率（通达信SLOPE等价于NP.POLYFIT的一次拟合斜率）}
M_SLOPE:=SLOPE(LNP, N_LONG);

{3. 年化收益率 = EXP(斜率 × 250) - 1}
ANNUAL_RET:=EXP(M_SLOPE * 250) - 1;

{4. 计算R2（拟合优度）}
{   推导: R2 = CORR(X,Y)2 = SLOPE2 × VAR(X) / VAR(Y)
    其中 X 是时间轴 0~N-1, VAR(X) = (N-1)×N/12        }
STD_Y:=STD(LNP, N_LONG);
VAR_Y:=STD_Y * STD_Y;
VAR_X:=(N_LONG - 1) * N_LONG / 12;
R_SQUARED:=IF(VAR_Y > 0, M_SLOPE * M_SLOPE * VAR_X / VAR_Y, 0);

{5. 长期综合得分 = 年化收益率 × R2}
LONG_SCORE:=ANNUAL_RET * R_SQUARED;


{==================================================}
{              二、短期动量计算                        }
{  PYTHON: SHORT_RETURN = P[-1]/P[-(N+1)] - 1       }
{         SHORT_ANNUALIZED = (1+R)^(250/N) - 1      }
{==================================================}

{6. 短期收益率（N_SHORT日）}
SHORT_RET:=C / REF(C, N_SHORT) - 1;

{7. 短期年化收益率 = (1+短期收益率)^(250/短期周期) - 1}
{   通达信无幂运算符, 用 EXP(P×LN(Q)) 替代 Q^P        }
SHORT_ANNUAL:=EXP((250 / N_SHORT) * LN(C / REF(C, N_SHORT))) - 1;

{8. 短期动量过滤：年化收益 < 阈值 则不合格}
SHORT_PASS:=SHORT_ANNUAL >= SHORT_TH;


{==================================================}
{              三、短期风控过滤                        }
{  PYTHON: MIN(DAY1,DAY2,DAY3) < 0.97 → SCORE=0   }
{==================================================}

{9. 近3日每日涨跌幅}
DAY1:=C / REF(C, 1);
DAY2:=REF(C, 1) / REF(C, 2);
DAY3:=REF(C, 2) / REF(C, 3);

{10. 近3日无单日暴跌}
NO_CRASH:=MIN(MIN(DAY1, DAY2), DAY3) >= LOSS;


{==================================================}
{              四、综合输出                            }
{==================================================}

{最终得分：长期得分 × 短期过滤 × 风控过滤}
FINAL_SCORE:=IF(SHORT_PASS AND NO_CRASH, LONG_SCORE, 0);


{========== 图形输出 ==========}
长期得分:LONG_SCORE,COLORLIRED,LINETHICK1;
短期年化:SHORT_ANNUAL * LONG_SCORE,NODRAW;{仅用于副图参考}
综合得分:FINAL_SCORE,COLORRED,LINETHICK2;
0,COLORGRAY,DOTLINE;

{========== 信号标记 ==========}
{黄点：短期动量通过，但风控不通过}
DRAWICON(SHORT_PASS=1 AND NO_CRASH=0 AND LONG_SCORE>0, FINAL_SCORE, 8);

{红箭头：全部通过，得分有效}
DRAWICON(FINAL_SCORE > 0, FINAL_SCORE, 1);

"""
from jqdata import *
import numpy as np
from redistrade import *

# ================================================================
#  配置中心
# ================================================================
class Universe:
    """标的池与参数"""
    BENCHMARK = '000300.XSHG'
    MONEY_MARKET = '511880.XSHG'          # 银华日利，T+0场内货基

    # (标的代码, 基准权重, 均线周期, 标签)
    ASSETS = [
        ('512890.XSHG', 0.25, 200, 'A股红利低波'),
        ('513500.XSHG', 0.20, 200, '标普500'),
        #('601318.XSHG', 0.75, 200, '中国平安'),
        ('518880.XSHG', 0.10, 200, '黄金避险'),
    ]

    CASH_FLOOR = 0.15                      # 现金底仓比例
    REBALANCE_THRESHOLD = 0.01             # 偏离总资产1%才调仓
    CASH_BUFFER = 500                      # 现金缓冲（元）
    EXEC_TIME = '14:50'                    # 尾盘执行


class Regime:
    """
    五档偏离度 → 仓位乘数映射表
    deviation = (price - ma) / ma
    """
    BANDS = [
        # (偏离度下界, 偏离度上界, 仓位乘数)
        (-np.inf,  -0.05,  1.50),          # 深度低估：重仓抄底
        (-0.05,     0.00,  1.20),          # 轻度低估：谨慎加仓
        ( 0.00,     0.10,  1.00),          # 合理区间：标准仓位
        ( 0.10,     0.20,  0.50),          # 高估区间：减半止盈
        ( 0.20,     np.inf, 0.00),         # 泡沫区间：清仓离场
    ]

    @staticmethod
    def multiplier(deviation):
        for lo, hi, mult in Regime.BANDS:
            if lo <= deviation < hi:
                return mult
        return 0.0


# ================================================================
#  信号引擎
# ================================================================
class SignalEngine:
    """计算每个资产的目标权重"""

    @staticmethod
    def compute_targets(total_value):
        """
        返回 {code: target_value} 字典
        """
        targets = {}
        for code, base_w, ma_len, label in Universe.ASSETS:
            bars = get_bars(code, count=ma_len, unit='1d',
                           fields=['close'], include_now=False)
            if bars is None or len(bars) < ma_len:
                continue

            ma = bars['close'].mean()
            price = get_current_data()[code].last_price
            if price <= 0 or ma <= 0:
                continue

            dev = (price - ma) / ma
            mult = Regime.multiplier(dev)
            targets[code] = total_value * base_w * mult

            log.info("[信号] %s | 价格:%.3f MA%d:%.3f 偏离:%.2f%% 乘数:%.1f" %
                     (label, price, ma_len, ma, dev * 100, mult))

        return targets


# ================================================================
#  风险预算
# ================================================================
class RiskBudget:
    """确保现金底仓约束不被突破"""

    @staticmethod
    def constrain(targets, total_value, current_positions):
        """
        如果目标风险资产总额超过上限，按比例缩减
        """
        ceiling = total_value * (1.0 - Universe.CASH_FLOOR)
        raw_total = 0.0
        for v in targets.values():
            raw_total += v

        if raw_total <= ceiling or raw_total <= 0:
            return targets

        scale = ceiling / raw_total
        constrained = {k: v * scale for k, v in targets.items()}
        log.info("[风控] 风险资产 %.0f 超上限 %.0f，缩放系数 %.2f" %
                 (raw_total, ceiling, scale))
        return constrained


# ================================================================
#  现金管理器
# ================================================================
class CashManager:
    """场内货基自动归集与赎回"""

    @staticmethod
    def withdraw(context, amount_needed):
        """从货基赎回指定金额"""
        mm = Universe.MONEY_MARKET
        pos = context.portfolio.positions[mm].closeable_amount
        if pos <= 0:
            return

        price = get_current_data()[mm].last_price
        shares = min(int(amount_needed * 1.02 / price) + 1, pos)
        if shares >= 100:
            order(mm, -shares)
            log.info("[现金] 赎回货基 %d 股 释放约 %.0f 元" % (shares, shares * price))

    @staticmethod
    def sweep(context):
        """闲置资金归集到货基"""
        cash = context.portfolio.available_cash
        if cash <= 1000:
            return

        price = get_current_data()[Universe.MONEY_MARKET].last_price
        if price <= 0:
            return

        shares = int((cash - Universe.CASH_BUFFER) / price)
        if shares >= 100:
            order(Universe.MONEY_MARKET, shares)
            log.info("[现金] 归集闲资 %d 股货基 (约%.0f元)" % (shares, shares * price))


# ================================================================
#  交易执行器
# ================================================================
class Executor:
    """先卖后买 + 阈值过滤 + 货基弹药补充"""

    @staticmethod
    def rebalance(context, targets):
        total_value = context.portfolio.total_value
        threshold = total_value * Universe.REBALANCE_THRESHOLD
        current_data = get_current_data()

        # 计算每个标的的调仓差额
        orders = {}
        for code, target_val in targets.items():
            price = current_data[code].last_price
            if price <= 0:
                continue

            hold_amount = context.portfolio.positions[code].closeable_amount
            hold_value = hold_amount * price
            delta = target_val - hold_value

            if abs(delta) > threshold:
                orders[code] = {'delta': delta, 'price': price,
                                'hold': hold_amount}

        if not orders:
            return

        # Phase 1: 卖出
        for code, o in orders.items():
            if o['delta'] >= 0:
                continue
            sell_shares = min(int(abs(o['delta']) / o['price']), o['hold'])
            if sell_shares >= 100:
                order(code, -sell_shares)
                log.info("[卖出] %s %d股 (释放≈%.0f)" %
                         (code, sell_shares, sell_shares * o['price']))

        # Phase 2: 买入
        for code, o in orders.items():
            if o['delta'] <= 0:
                continue

            buy_value = o['delta']

            # 资金不足时从货基提取
            if buy_value > context.portfolio.available_cash:
                shortage = buy_value - context.portfolio.available_cash
                CashManager.withdraw(context, shortage)

            actual_cash = min(buy_value, context.portfolio.available_cash)
            buy_shares = int(actual_cash / o['price'])
            if buy_shares >= 100:
                order(code, buy_shares)
                log.info("[买入] %s %d股 (花费≈%.0f)" %
                         (code, buy_shares, buy_shares * o['price']))


# ================================================================
#  聚宽回调入口
# ================================================================

#def order_( security, amount, style=None):
#    global _orig_order
#    res = _orig_order(security, amount, style)
#    return res
    
#log.info(f"当前 order 函数: {order}")
#_orig_order = order
#order = order_
#log.info(f"当前 order 函数: {order}")
def create_redis_proxy(orig_func):
    @RedisTrade.trade_signal
    def proxy(*args, **kwargs):
        return orig_func(*args, **kwargs)
    return proxy
    
    
def initialize(context):

    RedisTrade.hook(context, 'goldminer', 0)
    
    set_option("avoid_future_data", True)
    set_benchmark(Universe.BENCHMARK)
    set_option('use_real_price', True)
    # 零摩擦：去掉佣金和滑点
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.0008, close_commission=0.0008,
        close_today_commission=0, min_commission=5
    ), type='fund')
    set_slippage(FixedSlippage(0.002))

    log.set_level('system', 'error')
    log.set_level('order', 'error')

    run_daily(on_market_pulse, time=Universe.EXEC_TIME,
              reference_security=Universe.BENCHMARK)

    log.info("=" * 60)
    log.info("全天候资产轮动引擎 v3.0 启动")
    log.info("现金底仓: %.0f%% | 风险资产: %s" %
             (Universe.CASH_FLOOR * 100,
              ', '.join([a[3] for a in Universe.ASSETS])))
    log.info("=" * 60)


def on_market_pulse(context):
    """每日尾盘主循环：信号 → 风控 → 执行 → 归集"""
    total = context.portfolio.total_value

    # 1. 信号计算
    raw_targets = SignalEngine.compute_targets(total)

    # 2. 风险预算约束
    targets = RiskBudget.constrain(raw_targets, total, context.portfolio.positions)

    # 3. 执行调仓
    Executor.rebalance(context, targets)

    # 4. 闲资归集
    CashManager.sweep(context)


def after_market_close(context):
    """收盘日志"""
    tv = context.portfolio.total_value
    cd = get_current_data()

    # 货基仓位
    mm_pos = context.portfolio.positions[Universe.MONEY_MARKET].closeable_amount
    mm_price = cd[Universe.MONEY_MARKET].last_price
    mm_val = mm_pos * mm_price
    log.info("[日报] 总资产:%.0f | 现金仓:%.1f%% (%.0f)" %
             (tv, mm_val / tv * 100, mm_val))

    # 风险资产仓位
    for code, base_w, ma_len, label in Universe.ASSETS:
        pos = context.portfolio.positions[code].closeable_amount
        price = cd[code].last_price
        val = pos * price
        log.info("[日报] %s: %.1f%% (%.0f)" % (label, val / tv * 100, val))

    log.info("-" * 60)
