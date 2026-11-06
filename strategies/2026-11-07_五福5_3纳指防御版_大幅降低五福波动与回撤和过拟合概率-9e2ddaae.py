# Clone from JoinQuant
# postId: 9e2ddaae1ffe901a08296d9c0a9dbbab
# backtestId: 293794fb76da61102bf3b331e961b3d9
# title: 五福5.3纳指防御版，大幅降低五福波动与回撤和过拟合概率

# ============================================================================
# 五福 v5.3-ndx_defense —— 沪深300 三均线衰退期 · 纳指防御版
# 基于 v5.2-select_time 修改（原作者：烟花三月ETF / 本篇整理：量化Mark）
#
# 【本版改三件事：怎么判衰退期 + 怎么退出衰退期 + 衰退期买什么】
#   衰退期判定：沪深300 指数（000300.XSHG）的「A股前一交易日收盘价」
#               同时大于 ma5 / ma10 / ma20 → 正常期；
#               只要有任意一条没站上（含恰好等于）→ 衰退期。
#               （5.2 原逻辑是「4 个指数里至少 3 个低于 MA10」，本版换成单指数三均线，
#                 与 5.3-redLV-defence 的判定口径逐字一致）
#   退出迟滞：进入即时（掉下均线当天就进），退出需「连续 2 日站上全部均线」才确认。
#              同样与 5.3-redLV-defence 逐字一致 —— 两版只差「衰退期买什么」。
#   基准：set_benchmark = 159941.XSHE（纳指ETF广发）—— zane 的机会成本。
#         只影响回测报告里的基准曲线，不参与任何交易决策。
#   衰退期标的：跳过全部动量计算，在 g.ndx_etf_pool（13 只纳指类 ETF）里挑
#               「溢价率最低」的 1 只买入；13 只全部不可交易则回退 518880（黄金ETF）。
#   正常期行为：与 v5.2 完全一致 —— 单标的，买入动量得分最高的那 1 只 ETF（holdings_num = 1）。
#
# 【与另外两个版本的关系】
#   · 与 5.3-redLV-defence：**判定规则完全相同**，只有「衰退期买什么」不同
#     （redLV 买 515450 红利低波50ETF，本版买最低溢价纳指 ETF）。两者是一组干净的 A/B 对照。
#   · 与 5.3-muti / 5.2：正常期的动量选股口径逐字一致。
#
# 【改动清单】
#   1. check_recession_period：判定改为沪深300 单指数 × ma5/ma10/ma20 三均线；
#      删除 5.2 的「4 指数投票」与「最长走弱 20 个交易日强制退出」上限
#   1b. 新增退出迟滞：g.recession_exit_confirm_days = 2
#       （进入即时，退出需连续 2 日站上全部均线；与 5.3-redLV-defence 同一套参数）
#   2. 变量改名：g.is_a_share_weak → g.is_recession，g.weak_target_etf → g.recession_target_etf，
#      select_weak_period_target → select_recession_target（语义已从「走弱期」变为「衰退期」）
#   3. 新增 g.recession_index / g.recession_index_name / g.recession_ma_list
#   4. 新增 g.ndx_etf_pool（13 只纳指类 ETF）与 g.ndx_etf_names（日志用的中文简称）
#   5. 新增 g.ndx_fallback_etf = '518880.XSHG'（衰退期纳指全不可交易时的兜底）
#   6. 新增溢价率计算：溢价率 = 当日现价 ÷ 最近可得单位净值 − 1（get_extras('unit_net_value')）
#   7. 删除 5.2 的 filter_global_pool_by_volume 与 g.filtered_global_pool
#      —— 衰退期不进入动量流程，这条链路在 5.2 里只服务于「走弱期用全球池选股」，本版已无用途
#   8. midday_routine：衰退期跳过全球池 / 固定池 / 动态池更新（衰退期不再需要动量池）
#   9. afternoon_routine：衰退期走 select_recession_target()，不做任何动量计算
#  10. execute_sell_trades：衰退期目标来自 g.recession_target_etf，正常期仍取动量第 1 名
#  11. 其余逻辑（交易成本、日内趋势判断、分钟级止损、停牌/涨跌停/T+1、资金分配）
#      与 5.2 逐字一致，未做任何改动
#  12. set_benchmark 由 510300.XSHG 改为 159941.XSHE（纳指ETF广发，机会成本）
#
# 【已知特性 / 假设】
#   A. ⚠️ 「同时站上三条均线」看起来更严，实测结果却是**衰退期占多数**。
#      用 510300 代理沪深300、2020-02 ~ 2026-09 共 1568 个交易日实测（已含 2 日退出确认）：
#      衰退期占 74.0%，状态切换 220 次 ≈ 34.2 次/年（完整往返 17.1 次/年），单次持续中位 6 天。
#      再叠加 QDII 高溢价（2026-09-17 实测该池溢价率 9.37%~26.08%，价差 16.71 个百分点），
#      「衰退期买纳指」实际上是**大部分时间都在买 QDII**。回测时务必先看衰退期的时间占比。
#   B. 迟滞只加在退出侧：进入即时，退出需连续 g.recession_exit_confirm_days（默认 2）日确认。
#      实测（无迟滞 → 连续2日确认）完整往返 22.7 → 17.1 次/年，切换次数降 25%。
#      ⚠️ 迟滞参数必须与 5.3-redLV-defence 保持同步，否则 A/B 对照里混入了判定口径差异。
#   C. 判定用「A股前一交易日收盘价」，09:40 时当天日线还没走完 —— 无未来函数。
#   D. 聚宽没有实时 IOPV 接口，溢价率只能用「当日现价 ÷ 最近可得单位净值 − 1」近似。
#      QDII 净值**本来就滞后**，滞后 1~2 个美股交易日 + 中美假期错位是常态，不是数据异常。
#      实测（2026-09-16 收盘）：行情源显示 159941 是「净值 1.461，净值日期 2026-09-15」，
#      广发官网 9/16 的申赎清单引用的还是 9/14 的净值 1.4715。
#      所以算出来的溢价率含这段期间的纳指涨跌，**绝对值会整体偏移**。
#      但 13 只跟踪同一指数、共用同一个滞后因子 g（π_i = P_i/(NAV_i×g) − 1），
#      g 是公共正数因子，**同池排序完全不受影响**，所以「谁最低」这个结论可信。
#      实测佐证（2026-09-17）：池内 12 只净值日期是 9/16、513100 是 9/15，
#      两种口径排名仍 13/13 完全一致，最大偏差 0.083 个百分点。
#      日志会逐只打印净值日期，并单独提示「池内净值日期不一致」的情况。
#   E. 池内 159509（景顺纳指科技）跟踪的是「纳斯达克科技市值加权指数」，
#      与其余 12 只跟踪的「纳斯达克100指数」并非同一指数。按需求原样纳入池子。
#      它溢价率常年遥遥领先（2026-09-17 实测 26.08%，全池最高），
#      所以几乎不会被「选最低」选中，放在池里无害；哪天它真跌到最低说明它真便宜了。
#   F. 衰退期买入仍走完整的日内趋势判断流程（13:10 判断 → 13:40/14:10/14:40 复检 → 14:55 强买），
#      与正常期一致，不做「13:10 直接市价买入」。
#   G. 正常期动量池仍包含 g.global_etf_pool（海外/大宗 ETF，v5.2 原逻辑）。
#      本版只把「衰退期」的选股方式换掉，正常期口径未改。
#   H. 正常期无候选时的防御标的仍是 511880（货币 ETF，v5.2 原逻辑），与衰退期的 518880 是两回事。
#   I. 判定指数（沪深300）与衰退期标的（纳指 ETF）分属两个市场，这是本版的关键前提：
#      衰退期持仓与基准（510300）完全不相关，收益曲线的差异才有信息量。
# ============================================================================

import numpy as np
import math
import pandas as pd
from jqdata import *
from datetime import datetime, date, timedelta


def initialize(context):
    set_option("avoid_future_data", True)                               # 避免未来数据：防止回测中使用未来信息导致虚高收益
    set_option("use_real_price", True)                                  # 开启动态复权：正确处理分红、送股等事件，使用真实价格

    # ==================== 交易成本（按真实券商口径设定，与 5.2 / 5.3-muti 统一） ====================
    g.commission_rate = 0.00005      # 佣金：万分之0.5（双边）
    g.min_commission = 0.5           # 最低佣金：0.5 元 / 笔
    g.stamp_tax = 0                  # 印花税：ETF/LOF 免征
    g.slippage_tick = 0.001          # 单边滑点：ETF 最小价格变动单位（价格精度 0.001 元）
    # 【重要】聚宽的滑点参数是【双边价差】：
    #     买入成交价 = 最新价 + 双边价差/2
    #     卖出成交价 = 最新价 - 双边价差/2
    #   因此这里传 2×tick，才得到「买入比现价高 1 个最小变动单位（1.612→1.613）、卖出低 1 个」。
    #   若直接写 FixedSlippage(0.001)，单边只有 0.0005，会被聚宽四舍五入回 1.612，等于没设滑点。
    set_slippage(FixedSlippage(g.slippage_tick * 2), type="fund")
    set_order_cost(OrderCost(
        open_tax=g.stamp_tax,                       # 买入印花税：0
        close_tax=g.stamp_tax,                      # 卖出印花税：0
        open_commission=g.commission_rate,          # 买入佣金：万分之0.5
        close_commission=g.commission_rate,         # 卖出佣金：万分之0.5
        close_today_commission=g.commission_rate,   # 平今佣金：ETF 无此概念，与买卖保持一致
        min_commission=g.min_commission             # 最低佣金：0.5 元
    ), type="fund")

    log.set_level('order', 'error')                                     # 订单日志级别：只显示错误信息
    log.set_level('system', 'error')                                    # 系统日志级别：只显示错误信息
    log.set_level('strategy', 'info')                                   # 策略日志级别：显示普通信息及以上
    log.info("【五福闹新春】v5.3-ndx_defense！")

    # ==================== ETF池定义 ====================
    # 全球/海外ETF池（含大宗商品和海外市场ETF）
    g.global_etf_pool = [
        # 大宗商品ETF：
        '518880.XSHG',  # (黄金ETF) [ETF]-日均成交额：51.35亿元-上市日期：2013-07-29
        '501018.XSHG',  # (南方原油) [LOF]-日均成交额：24.38亿元-上市日期：2016-06-28
        '161226.XSHE',  # (国投白银LOF) [LOF]-日均成交额：5.44亿元-上市日期：2015-08-17
        '159985.XSHE',  # (豆粕ETF华夏) [ETF]-日均成交额：4.63亿元-上市日期：2019-12-05
        '159980.XSHE',  # (有色ETF大成) [ETF]-日均成交额：3.84亿元-上市日期：2019-12-24
        # 海外ETF：
        '513310.XSHG',  # (中韩芯片) [ETF]-日均成交额：59.37亿元-上市日期：2022-12-22
        '159518.XSHE',  # (标普油气ETF嘉实) [ETF]-日均成交额：27.93亿元-上市日期：2023-11-15
        '159509.XSHE',  # (纳指科技ETF景顺) [ETF]-日均成交额：7.24亿元-上市日期：2023-08-08
        '513100.XSHG',  # (纳指ETF) [ETF]-日均成交额：5.02亿元-上市日期：2013-05-15
        '513520.XSHG',  # (日经ETF) [ETF]-日均成交额：3.72亿元-上市日期：2019-06-25
        '513500.XSHG',  # (标普500) [ETF]-日均成交额：2.89亿元-上市日期：2014-01-15
        '159502.XSHE',  # (标普生物科技ETF嘉实) [ETF]-日均成交额：1.80亿元-上市日期：2024-01-10
        '513400.XSHG',  # (道琼斯) [ETF]-日均成交额：1.70亿元-上市日期：2024-02-02
        '513030.XSHG',  # (德国ETF) [ETF]-日均成交额：0.95亿元-上市日期：2014-09-05
        '513290.XSHG',  # (纳指生物) [ETF]-日均成交额：0.78亿元-上市日期：2022-08-29
        '520830.XSHG',  # (沙特ETF) [ETF]-日均成交额：0.62亿元-上市日期：2024-07-16
        '159529.XSHE',  # (标普消费ETF景顺) [ETF]-日均成交额：0.50亿元-上市日期：2024-02-02
    ]
    # 中国ETF池（含港股、指数、行业ETF）
    g.china_etf_pool = [
        # 港股ETF：
        '513090.XSHG',  # (香港证券) [ETF]-日均成交额：54.24亿元-上市日期：2020-03-26
        '513120.XSHG',  # (HK创新药) [ETF]-日均成交额：52.34亿元-上市日期：2022-07-12
        '513180.XSHG',  # (恒指科技) [ETF]-日均成交额：36.66亿元-上市日期：2021-05-25
        '513330.XSHG',  # (恒生互联) [ETF]-日均成交额：20.45亿元-上市日期：2021-02-08
        '513750.XSHG',  # (港股非银) [ETF]-日均成交额：9.55亿元-上市日期：2023-11-27
        '159892.XSHE',  # (恒生医药ETF华夏) [ETF]-日均成交额：7.90亿元-上市日期：2021-10-19
        '513190.XSHG',  # (H股金融) [ETF]-日均成交额：3.74亿元-上市日期：2023-10-11
        '159605.XSHE',  # (中概互联ETF广发) [ETF]-日均成交额：3.19亿元-上市日期：2021-12-02
        '513630.XSHG',  # (香港红利) [ETF]-日均成交额：2.84亿元-上市日期：2023-12-08
        '159323.XSHE',  # (港股通汽车ETF华夏) [ETF]-日均成交额：1.98亿元-上市日期：2025-01-08
        '510900.XSHG',  # (恒生中国) [ETF]-日均成交额：1.46亿元-上市日期：2012-10-22
        '513920.XSHG',  # (央企40) [ETF]-日均成交额：1.38亿元-上市日期：2024-01-05
        '513970.XSHG',  # (恒生消费) [ETF]-日均成交额：0.82亿元-上市日期：2023-04-21
        # 指数ETF：
        '511380.XSHG',  # (转债ETF) [ETF]-日均成交额：115.92亿元-上市日期：2020-04-07
        '512050.XSHG',  # (A500E) [ETF]-日均成交额：48.05亿元-上市日期：2024-11-15
        '510500.XSHG',  # (500ETF) [ETF]-日均成交额：45.45亿元-上市日期：2013-03-15
        '159915.XSHE',  # (创业板ETF易方达) [ETF]-日均成交额：43.55亿元-上市日期：2011-12-09
        '510300.XSHG',  # (300ETF) [ETF]-日均成交额：34.60亿元-上市日期：2012-05-28
        '512100.XSHG',  # (1000ETF) [ETF]-日均成交额：25.26亿元-上市日期：2016-11-04
        '159949.XSHE',  # (创业板50ETF华安) [ETF]-日均成交额：16.52亿元-上市日期：2016-07-22
        '588080.XSHG',  # (科创板50) [ETF]-日均成交额：13.32亿元-上市日期：2020-11-16
        '159967.XSHE',  # (创业板成长ETF华夏) [ETF]-日均成交额：5.29亿元-上市日期：2019-07-15
        '588220.XSHG',  # (科创100F) [ETF]-日均成交额：5.01亿元-上市日期：2023-09-15
        '563300.XSHG',  # (中证2000) [ETF]-日均成交额：4.13亿元-上市日期：2023-09-14
        '510760.XSHG',  # (上证ETF) [ETF]-日均成交额：1.45亿元-上市日期：2020-09-09
        # 行业ETF：
        '588200.XSHG',  # (科创芯片) [ETF]-日均成交额：28.07亿元-上市日期：2022-10-26
        '515880.XSHG',  # (通信ETF) [ETF]-日均成交额：22.39亿元-上市日期：2019-09-06
        '159981.XSHE',  # (能源化工ETF建信) [ETF]-日均成交额：21.63亿元-上市日期：2020-01-17
        '512880.XSHG',  # (证券ETF) [ETF]-日均成交额：16.21亿元-上市日期：2016-08-08
        '513350.XSHG',  # (油气ETF) [ETF]-日均成交额：15.66亿元-上市日期：2023-11-28
        '159326.XSHE',  # (电网设备ETF华夏) [ETF]-日均成交额：14.86亿元-上市日期：2024-09-09
        '159516.XSHE',  # (半导体设备ETF国泰) [ETF]-日均成交额：14.23亿元-上市日期：2023-07-27
        '159206.XSHE',  # (卫星ETF永赢) [ETF]-日均成交额：13.87亿元-上市日期：2025-03-14
        '512480.XSHG',  # (半导体) [ETF]-日均成交额：13.07亿元-上市日期：2019-06-12
        '159363.XSHE',  # (创业板人工智能ETF华宝) [ETF]-日均成交额：10.50亿元-上市日期：2024-12-16
        '159870.XSHE',  # (化工ETF鹏华) [ETF]-日均成交额：10.03亿元-上市日期：2021-03-03
        '512400.XSHG',  # (有色ETF) [ETF]-日均成交额：9.97亿元-上市日期：2017-09-01
        '159755.XSHE',  # (电池ETF广发) [ETF]-日均成交额：8.58亿元-上市日期：2021-06-24
        '588170.XSHG',  # (科创半导) [ETF]-日均成交额：7.74亿元-上市日期：2025-04-08
        '159992.XSHE',  # (创新药ETF银华) [ETF]-日均成交额：7.59亿元-上市日期：2020-04-10
        '159995.XSHE',  # (芯片ETF华夏) [ETF]-日均成交额：7.51亿元-上市日期：2020-02-10
        '512890.XSHG',  # (红利低波) [ETF]-日均成交额：6.79亿元-上市日期：2019-01-18
        '515220.XSHG',  # (煤炭ETF) [ETF]-日均成交额：6.44亿元-上市日期：2020-03-02
        '159566.XSHE',  # (储能电池ETF易方达) [ETF]-日均成交额：6.31亿元-上市日期：2024-02-08
        '159819.XSHE',  # (人工智能ETF易方达) [ETF]-日均成交额：6.26亿元-上市日期：2020-09-23
        '512800.XSHG',  # (银行ETF) [ETF]-日均成交额：6.13亿元-上市日期：2017-08-03
        '512690.XSHG',  # (酒ETF) [ETF]-日均成交额：5.99亿元-上市日期：2019-05-06
        '515050.XSHG',  # (5GETF) [ETF]-日均成交额：5.93亿元-上市日期：2019-10-16
        '562500.XSHG',  # (机器人) [ETF]-日均成交额：5.83亿元-上市日期：2021-12-29
        '512170.XSHG',  # (医疗ETF) [ETF]-日均成交额：5.63亿元-上市日期：2019-06-17
        '517520.XSHG',  # (黄金股) [ETF]-日均成交额：5.01亿元-上市日期：2023-11-01
        '159869.XSHE',  # (游戏ETF华夏) [ETF]-日均成交额：4.77亿元-上市日期：2021-03-05
        '512070.XSHG',  # (证券保险) [ETF]-日均成交额：4.61亿元-上市日期：2014-07-18
        '159611.XSHE',  # (电力ETF广发) [ETF]-日均成交额：4.42亿元-上市日期：2022-01-07
        '562800.XSHG',  # (稀有金属) [ETF]-日均成交额：4.39亿元-上市日期：2021-09-27
        '515120.XSHG',  # (创新药) [ETF]-日均成交额：4.34亿元-上市日期：2021-01-04
        '512010.XSHG',  # (医药ETF) [ETF]-日均成交额：4.27亿元-上市日期：2013-10-28
        '510880.XSHG',  # (红利ETF) [ETF]-日均成交额：3.97亿元-上市日期：2007-01-18
        '515790.XSHG',  # (光伏ETF) [ETF]-日均成交额：3.87亿元-上市日期：2020-12-18
        '515980.XSHG',  # (人工智能) [ETF]-日均成交额：3.78亿元-上市日期：2020-02-10
        '512660.XSHG',  # (军工ETF) [ETF]-日均成交额：3.75亿元-上市日期：2016-08-08
        '159928.XSHE',  # (消费ETF汇添富) [ETF]-日均成交额：3.66亿元-上市日期：2013-09-16
        '512710.XSHG',  # (军工龙头) [ETF]-日均成交额：3.60亿元-上市日期：2019-08-26
        '560860.XSHG',  # (工业有色) [ETF]-日均成交额：3.57亿元-上市日期：2023-03-13
        '515030.XSHG',  # (新汽车) [ETF]-日均成交额：3.33亿元-上市日期：2020-03-04
        '159766.XSHE',  # (旅游ETF富国) [ETF]-日均成交额：3.30亿元-上市日期：2021-07-23
        '159218.XSHE',  # (卫星ETF招商) [ETF]-日均成交额：3.21亿元-上市日期：2025-05-22
        '159852.XSHE',  # (软件ETF嘉实) [ETF]-日均成交额：3.19亿元-上市日期：2021-02-09
        '516160.XSHG',  # (新能源) [ETF]-日均成交额：3.07亿元-上市日期：2021-02-04
        '516150.XSHG',  # (稀土基金) [ETF]-日均成交额：3.03亿元-上市日期：2021-03-17
        '159227.XSHE',  # (航空航天ETF华夏) [ETF]-日均成交额：2.98亿元-上市日期：2025-05-16
        '159583.XSHE',  # (通信ETF富国) [ETF]-日均成交额：2.93亿元-上市日期：2024-07-08
        '588790.XSHG',  # (科创智能) [ETF]-日均成交额：2.62亿元-上市日期：2025-01-09
        '159865.XSHE',  # (养殖ETF国泰) [ETF]-日均成交额：2.44亿元-上市日期：2021-03-08
        '512980.XSHG',  # (传媒ETF) [ETF]-日均成交额：2.43亿元-上市日期：2018-01-19
        '159851.XSHE',  # (金融科技ETF华宝) [ETF]-日均成交额：2.27亿元-上市日期：2021-03-19
        '561360.XSHG',  # (石油ETF) [ETF]-日均成交额：2.04亿元-上市日期：2023-10-31
        '561980.XSHG',  # (芯片设备) [ETF]-日均成交额：2.01亿元-上市日期：2023-09-01
        '562590.XSHG',  # (半导材料) [ETF]-日均成交额：1.76亿元-上市日期：2023-10-18
        '512200.XSHG',  # (地产ETF) [ETF]-日均成交额：1.71亿元-上市日期：2017-09-25
        '159732.XSHE',  # (消费电子ETF华夏) [ETF]-日均成交额：1.62亿元-上市日期：2021-08-23
        '159667.XSHE',  # (工业母机ETF国泰) [ETF]-日均成交额：1.58亿元-上市日期：2022-10-26
        '516510.XSHG',  # (云计算) [ETF]-日均成交额：1.49亿元-上市日期：2021-04-07
        '159840.XSHE',  # (锂电池ETF工银) [ETF]-日均成交额：1.42亿元-上市日期：2021-08-20
        '159998.XSHE',  # (计算机ETF天弘) [ETF]-日均成交额：1.30亿元-上市日期：2020-04-13
        '159825.XSHE',  # (农业ETF富国) [ETF]-日均成交额：1.15亿元-上市日期：2020-12-29
        '512670.XSHG',  # (国防ETF) [ETF]-日均成交额：1.12亿元-上市日期：2019-08-01
        '159883.XSHE',  # (医疗器械ETF永赢) [ETF]-日均成交额：1.05亿元-上市日期：2021-04-30
        '515210.XSHG',  # (钢铁ETF) [ETF]-日均成交额：1.01亿元-上市日期：2020-03-02
        '515400.XSHG',  # (大数据) [ETF]-日均成交额：0.94亿元-上市日期：2021-01-20
        '159256.XSHE',  # (创业板软件ETF华夏) [ETF]-日均成交额：0.83亿元-上市日期：2025-08-04
        '561330.XSHG',  # (矿业ETF) [ETF]-日均成交额：0.83亿元-上市日期：2022-11-01
        '515170.XSHG',  # (食品饮料) [ETF]-日均成交额：0.67亿元-上市日期：2021-01-13
        '159638.XSHE',  # (高端装备ETF嘉实) [ETF]-日均成交额：0.56亿元-上市日期：2022-08-12
        '516520.XSHG',  # (智能驾驶) [ETF]-日均成交额：0.47亿元-上市日期：2021-03-01
        '513360.XSHG',  # (教育ETF) [ETF]-日均成交额：0.43亿元-上市日期：2021-06-17
        '516190.XSHG',  # (文娱ETF) [ETF]-日均成交额：0.18亿元-上市日期：2021-09-17
    ]
    # 固定ETF池 = 全球池 + 中国池（正常期使用）
    g.fixed_etf_pool = g.global_etf_pool + g.china_etf_pool

    # ==================== 【本版新增】纳指池（衰退期专用） ====================
    # 13 只场内纳斯达克类 ETF。衰退期跳过动量选股，只在这 13 只里挑溢价率最低的 1 只。
    g.ndx_etf_pool = [
        '159941.XSHE',  # 纳指ETF广发     —— 广发纳斯达克100ETF(QDII)
        '513100.XSHG',  # 纳指ETF国泰     —— 国泰纳斯达克100ETF(QDII)
        '159509.XSHE',  # 纳指科技ETF景顺 —— 景顺长城纳斯达克科技市值加权ETF(QDII)【跟踪的是纳指科技，非纳指100】
        '513300.XSHG',  # 纳斯达克ETF华夏 —— 华夏纳斯达克100ETF(QDII)
        '159501.XSHE',  # 纳指ETF嘉实     —— 嘉实纳斯达克100ETF(QDII)
        '159632.XSHE',  # 纳斯达克ETF华安 —— 华安纳斯达克100ETF(QDII)
        '159659.XSHE',  # 纳斯达克100ETF招商 —— 招商纳斯达克100ETF(QDII)
        '159513.XSHE',  # 纳斯达克100ETF大成 —— 大成纳斯达克100ETF(QDII)
        '159696.XSHE',  # 纳指ETF易方达   —— 易方达纳斯达克100ETF(QDII)
        '159660.XSHE',  # 纳指ETF汇添富   —— 汇添富纳斯达克100ETF(QDII)
        '513110.XSHG',  # 纳指ETF华泰柏瑞 —— 华泰柏瑞纳斯达克100ETF(QDII)
        '513390.XSHG',  # 纳指100ETF博时  —— 博时纳斯达克100ETF(QDII)
        '513870.XSHG',  # 纳指ETF富国     —— 富国纳斯达克100ETF(QDII)
    ]
    # 日志用中文简称（硬编码，避免依赖 get_all_securities，回测日志更易读）
    g.ndx_etf_names = {
        '159941.XSHE': '纳指ETF广发',
        '513100.XSHG': '纳指ETF国泰',
        '159509.XSHE': '纳指科技ETF景顺*',
        '513300.XSHG': '纳斯达克ETF华夏',
        '159501.XSHE': '纳指ETF嘉实',
        '159632.XSHE': '纳斯达克ETF华安',
        '159659.XSHE': '纳斯达克100ETF招商',
        '159513.XSHE': '纳斯达克100ETF大成',
        '159696.XSHE': '纳指ETF易方达',
        '159660.XSHE': '纳指ETF汇添富',
        '513110.XSHG': '纳指ETF华泰柏瑞',
        '513390.XSHG': '纳指100ETF博时',
        '513870.XSHG': '纳指ETF富国',
    }
    # 衰退期兜底：纳指池 13 只全部不可交易时买入黄金ETF
    g.ndx_fallback_etf = '518880.XSHG'
    # 取单位净值时回看的交易日数（取区间内最后一个非空净值）。
    # 为什么给到 10：聚宽官方文档写明「净值数据(get_extras) 盘后17点到下一交易日9点更新」，
    # 而 QDII 基金本身净值披露就滞后 T+2~T+3，社区实测确有「当天仍取不到 3 天前净值」的情况。
    # 窗口给宽一点，是为了保证总能兜到最近一期已披露的净值，而不是因为窗口里恰好全是 NaN 而被剔除。
    g.ndx_nav_lookback = 10
    g.recession_target_etf = None        # 衰退期选中的目标ETF，由 select_recession_target 写入

    # ==================== 衰退期判定配置 ====================
    # 判定标的：沪深300 指数（单一指数，替换 5.2 的「4 指数投票」）
    g.recession_index = '000300.XSHG'
    g.recession_index_name = '沪深300'
    # 需要「同时站上」的全部均线周期。任意一条没站上 → 衰退期。
    # 与 5.3-redLV-defence 完全一致。
    g.recession_ma_list = [5, 10, 20]
    # 【退出迟滞】进入衰退期是即时的（掉下均线当天就进），
    # 但退出需要「连续 N 日站上全部均线」才确认，避免在均线附近来回穿越造成无效换仓。
    g.recession_exit_confirm_days = 2
    g.recession_recovery_days = 0        # 运行态：已连续站上全部均线的天数

    g.avg_etf_money_threshold = None
    g.filtered_fixed_pool = []
    g.dynamic_etf_pool = []
    g.merged_etf_pool = []
    g.ranked_etfs_result = []
    g.global_threshold_divisor = 20000  # 全市场ETF流动性阈值除数，资金大建议改为3000避免买到盘子小的etf
    g.is_recession = False               # 沪深300 未同时站上三均线 → True
    g.weak_start_date = None             # 衰退期起始日（仅用于日志展示「已持续 N 天」）
    g.weak_days_count = 0                # 已持续交易日数（仅用于日志展示）
    g.holdings_num = 1                   # 持仓数量：与 5.2 一致，单标的满仓
    g.pending_buy_etfs = []              # 待趋势确认的买入ETF列表
    g.trend_lookback_minutes = 30        # 趋势判断回看分钟数
    g.trend_slope_threshold = 0.001      # 趋势判断斜率阈值(每分钟涨跌幅%，归一化后)
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
    g.max_portfolio_value = 0
    g.drawdown_threshold = 0.03
    g.drawdown_records = []
    g.use_fixed_stop_loss = True
    g.fixedStopLossThreshold = 0.95

    # 基准 = zane 的机会成本：159941（纳指ETF广发，跟踪纳斯达克100）。
    # 只影响回测报告里的基准曲线，不参与任何交易决策。
    set_benchmark("159941.XSHE")

    # ==================== 定时任务 ====================
    run_daily(morning_routine, time='09:00')            # 09:00 晨间流水线：持仓检查→回撤监控→流动性阈值计算
    run_daily(check_recession_daily, time='09:40')     # 09:40 衰退期判断+池子更新
    run_daily(afternoon_routine, time='13:10')          #  动量计算/纳指选择（需早于卖出时间）
    run_daily(sell_routine, time='13:10')               #  卖出流水线（需早于买入时间）
    run_daily(buy_routine, time='13:10')                #  买入流水线（含趋势判断）
    run_daily(check_pending_buys_trend, time='13:40')   # 13:40 待买ETF趋势复检
    run_daily(check_pending_buys_trend, time='14:10')   # 14:10 待买ETF趋势复检
    run_daily(check_pending_buys_trend, time='14:40')   # 14:40 待买ETF趋势复检
    run_daily(force_buy_pending, time='14:55')          # 14:55 强制买入剩余待买ETF
    run_daily(reset_daily_flags, time='15:10')          # 15:10 收盘流水线：重置价格缓存
    run_daily(minute_level_stop_loss, time='every_bar') # 分钟级固定止损

    log.info(f"""
【策略参数初始化完成】v5.3-ndx_defense（沪深300三均线 · 连续2日退出确认 · 纳指防御）
=== 交易成本 ===
- 佣金: 万分之{g.commission_rate*10000:.1f}（双边），最低 {g.min_commission} 元/笔
- 印花税: {g.stamp_tax:.1%}（ETF 免征）
- 滑点: 绝对滑点 {g.slippage_tick} 元/边（FixedSlippage 传双边 {g.slippage_tick*2}）
        即买入价 ≈ 最新价+{g.slippage_tick}，卖出价 ≈ 最新价-{g.slippage_tick}
=== ETF池配置 ===
- 全球/海外ETF池: {len(g.global_etf_pool)}只（仅正常期使用）
- 国内ETF池: {len(g.china_etf_pool)}只
- 固定池合计: {len(g.fixed_etf_pool)}只（仅正常期使用）
- 纳指池: {len(g.ndx_etf_pool)}只（衰退期专用）
=== 衰退期判定（本版核心改动 1）===
- 判定标的: {g.recession_index} {g.recession_index_name}（单一指数，替换 5.2 的 4 指数投票）
- 判定均线: {', '.join('MA' + str(p) for p in g.recession_ma_list)}
- 正常期条件: 前一交易日收盘价 同时大于 全部 {len(g.recession_ma_list)} 条均线
- 衰退期条件: 任意一条均线未站上（含收盘价恰好等于均线）
- 退出确认: 需连续 {g.recession_exit_confirm_days} 个交易日站上全部均线（进入不做确认）
- 最长期限: 无上限（跌破均线就一直防御）
- 数据口径: 09:40 取 attribute_history('1d')，即 A股前一交易日收盘价，无未来函数
=== 衰退期纳指防御（本版核心改动 2）===
- 衰退期行为: 跳过动量计算，买入纳指池中「溢价率最低」的1只
- 溢价率口径: 当日13:10现价 ÷ 最近可得单位净值 − 1（get_extras('unit_net_value')）
- 净值回看: 最近{g.ndx_nav_lookback}个交易日内的最后一个非空净值
- 买入时点: 与正常期一致，走完整日内趋势流程（13:10 → 13:40/14:10/14:40 → 14:55 强买）
- 全池不可交易时兜底: {g.ndx_fallback_etf} 黄金ETF
=== 动量得分过滤（仅正常期生效）===
- 周期: {g.lookback_days}天
- 得分阈值: [{g.min_score_threshold}, {g.max_score_threshold}]
- 调仓系数: {g.score_threshold_ratio}
=== 过滤条件（仅正常期生效）===
- R²过滤: {'启用' if g.enable_r2_filter else '禁用'} (阈值>{g.r2_threshold:.1f})
- 成交量过滤: {'启用' if g.enable_volume_check else '禁用'} (近{g.volume_lookback}日均量比<{g.volume_threshold:.1f})
- 短期风控: {'启用' if g.enable_loss_filter else '禁用'} (近3日单日跌幅<{1-g.loss:.0%})
- 注: 5.2 原有的「走弱期 MA 过滤」本版永不触发（衰退期不进入动量流程），配置保留未删
=== 止损机制 ===
- 分钟级固定比例止损: {'启用' if g.use_fixed_stop_loss else '禁用'} (成本价×{g.fixedStopLossThreshold:.0%})
=== 买入趋势判断 ===
- 趋势判断回看: 最近{g.trend_lookback_minutes}分钟分钟线
- 判断方法: 归一化线性回归斜率（每分钟涨跌幅% > {g.trend_slope_threshold}为上涨趋势）
- 数据不足(<5根): 默认无上涨趋势(等待)
- 复检时间: 13:10 → 13:40 → 14:10 → 14:40
- 强制买入: 14:55（无论趋势强制买入剩余待买ETF）
=== 其他配置 ===
- 持仓数量: {g.holdings_num}只
- 正常期无候选时防御ETF: {g.defensive_etf}（货币ETF，v5.2 原逻辑）
- 衰退期全池不可交易兜底ETF: {g.ndx_fallback_etf}（黄金ETF）
- 最小交易额: {g.min_money}元
- 基准: 159941.XSHE（纳指ETF广发，zane 的机会成本）
- 基准: 510300.XSHG
""")


def check_recession_daily(context):
    check_recession_period(context)
    midday_routine(context)


def morning_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【晨间流水线】启动...")
    log.info("【持仓检查】检查当前持仓状态...")
    check_positions(context)
    log.info("【回撤监控】监控策略回撤...")
    monitor_drawdown(context)
    log.info("【流动性阈值】计算全市场ETF流动性阈值...")
    calculate_global_etf_threshold(context)
    log.info("⏸️ 【晨间流水线】执行完毕！")


def midday_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【早盘流水线】启动...")
    if g.is_recession:
        # 【本版改动】衰退期不做动量选股，动量池已无用途，直接跳过全部池更新
        log.info("🔴 【衰退期】不做动量选股，跳过全球池/固定池/动态池更新（省去大量行情请求）")
    else:
        log.info(f"🟢 【正常期池更新】执行动态池更新、固定池过滤、合并池...")
        log.info("【动态池更新】更新行业ETF动态池（各行业流动性最佳ETF）...")
        update_sector_pool(context)
        log.info("【固定池过滤】过滤固定ETF池流动性...")
        filter_fixed_pool_by_volume(context)
        log.info("【合并池】合并固定池与动态池...")
        daily_merge_etf_pools(context)
        log.info(f"【正常期池更新完成】合并池: {len(g.merged_etf_pool)}只")
    log.info("⏸️ 【早盘流水线】执行完毕！")


def afternoon_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【午盘流水线】启动...")
    if g.is_recession:
        log.info("🔴 【沪深300衰退期】跳过动量计算，改为在纳指池中挑选溢价率最低的1只")
        select_recession_target(context)
    else:
        log.info("🟢 【正常期】使用合并池做动量选股，共{}只".format(len(getattr(g, 'merged_etf_pool', []))))
        log.info("【动量计算】计算ETF动量得分与排序...")
        calculate_and_log_ranked_etfs(context)
    log.info("⏸️ 【午盘流水线】执行完毕！")


def sell_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【卖出流水线】启动...")
    execute_sell_trades(context)
    log.info("⏸️ 【卖出流水线】执行完毕！")


def buy_routine(context):
    log.info("★" * 80)
    log.info("▶️ 【买入流水线】启动（含趋势判断）...")
    g.pending_buy_etfs = []  # 重置待买列表

    target_etfs = g.target_etfs_list
    if not target_etfs:
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        log.info("⏸️ 【买入流水线】执行完毕！")
        return

    current_positions = set(context.portfolio.positions.keys())
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        log.info("⏸️ 【买入流水线】执行完毕！")
        return

    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    g.pending_buy_etfs = list(etfs_to_buy)
    log.info(f"计划买入ETF: {etfs_to_buy}，开始趋势判断（下跌趋势将等待30分钟复检，14:55强制买入）...")
    execute_buy_with_trend(context, force=False)

    if g.pending_buy_etfs:
        log.info(f"⏳ 等待趋势确认的ETF: {g.pending_buy_etfs}，将在13:40/14:10/14:40再次判断，14:55强制买入")
    log.info("⏸️ 【买入流水线】执行完毕！")


def reset_daily_flags(context):
    g.cache_date = None
    g.yesterday_close_cache = {}
    g.pending_buy_etfs = []
    g.recession_target_etf = None            # 【本版新增】收盘清空，防止极端情况下隔日残留旧目标
    log.info("🔄 收盘缓存重置完成")


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
                    'is_recession': g.is_recession
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
                log.info(f"  沪深300状态: {'衰退期' if g.is_recession else '正常期'}")
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
        threshold = avg_total_money / g.global_threshold_divisor
        g.avg_etf_money_threshold = threshold
        log.info(f"【全局阈值更新完成】近{len(daily_totals)}日全市场ETF日均总成交额={avg_total_money/1e8:.2f}亿元，阈值={threshold/1e4:.0f}万元({threshold:,.0f}元)")
    except Exception as e:
        log.warning(f"计算全局阈值异常: {e}，使用保守阈值1000万")
        g.avg_etf_money_threshold = 10000000


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
    top_300 = final_pool_info_sorted[:300]
    g.dynamic_etf_pool = [item['code'] for item in top_300]
    log.info(f"【动态池更新完成】动态池共{len(g.dynamic_etf_pool)}只ETF")
    if len(g.dynamic_etf_pool) <= 10:
        for item in top_300[:10]:
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
        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'current_price': current_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'passed_momentum': passed_momentum,
            'passed_r2': passed_r2,
            'passed_ma': passed_ma,
            'passed_volume': volume_ratio is not None and volume_ratio < g.volume_threshold,
            'passed_loss': passed_loss_filter,
            'ma_value': ma_value,
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


def check_recession_period(context):
    """
    衰退期判定（本版核心改动 1）

    规则：沪深300 指数（g.recession_index）的「A股前一交易日收盘价」
          同时大于 g.recession_ma_list 里的全部均线（默认 ma5 / ma10 / ma20）→ 正常期；
          只要有任意一条没站上（含恰好等于）→ 衰退期。

    与 5.2 原逻辑的差异：
      · 5.2：4 个指数（大盘/小盘/创业板/中证A500）投票，>=3 个低于 MA10 进走弱期，
             >=3 个站上 MA10 退出，进出条件不同（带迟滞）；
      · 本版：只看沪深300 一个指数，要求同时站上 ma5/ma10/ma20 三条线才叫正常期。
      · 进入即时、退出带迟滞：掉下均线当天就进衰退期；回正常期需要
        「连续 g.recession_exit_confirm_days（默认 2）个交易日站上全部均线」才确认。
        迟滞只加在退出侧 —— 掉下均线要立刻躲，回到均线上方多等一天成本很低。
      · 删掉了 5.2 的「最长走弱 20 个交易日强制退出」上限。
      · 判定口径与 5.3-redLV-defence 完全一致，两个版本只有「衰退期买什么」不同。

    ⚠️ 实测提醒：要求「同时站上三条」看起来更严，实际结果是**衰退期占多数**。
       用 510300 代理沪深300、2020-02~2026-09 共 1568 个交易日实测：
         无迟滞      ：衰退期占 64.7%，切换 292 次 ≈ 45.4 次/年，单次持续中位 3 天
         连续2日确认 ：衰退期占 74.0%，切换 220 次 ≈ 34.2 次/年，单次持续中位 6 天

    数据口径：09:40 调用 attribute_history('1d')，默认 include_now=False，
              取到的是「A股前一交易日收盘价」，不含当日未走完的日线，无未来函数。
    容错：若指数数据不足，沿用上一交易日的状态，不因取数失败而误切仓。
    """
    code = g.recession_index
    name = g.recession_index_name
    today = context.current_dt.date()
    need = max(g.recession_ma_list)

    df = attribute_history(code, need + 1, '1d', ['close'], skip_paused=False)
    if df is None or len(df) < 2:
        log.warning(f"【衰退期判断】{name}({code})取不到足够日线数据，沿用上一交易日状态："
                    f"{'衰退期' if g.is_recession else '正常期'}")
        return g.is_recession

    close_series = df['close'].dropna()
    if len(close_series) < need:
        log.warning(f"【衰退期判断】{name}({code})有效收盘价仅 {len(close_series)} 根（需>={need}），"
                    f"沿用上一交易日状态：{'衰退期' if g.is_recession else '正常期'}")
        return g.is_recession

    current_price = close_series.iloc[-1]
    log.info(f"📊 【衰退期判断】{name}({code}) 前一交易日收盘 {current_price:.2f}")

    above_all = True
    for period in g.recession_ma_list:
        ma_val = close_series.iloc[-period:].mean()
        is_above = current_price > ma_val
        above_all = above_all and is_above
        if ma_val > 0:
            diff_pct = (current_price - ma_val) / ma_val * 100
        else:
            diff_pct = 0.0
        log.info(f"    vs MA{period:<2d} {ma_val:>8.2f} → {'⬆️ 站上' if is_above else '⬇️ 低于'}"
                 f"（差 {diff_pct:+.2f}%）")

    # ---- 退出迟滞：进入即时，退出需连续 N 日站上全部均线 ----
    if above_all:
        g.recession_recovery_days += 1
    else:
        g.recession_recovery_days = 0

    if g.is_recession:
        # 已在衰退期：只有「站上全部均线」且连续天数达标，才回正常期
        new_state = not (above_all and g.recession_recovery_days >= g.recession_exit_confirm_days)
    else:
        # 正常期：掉下均线当天立即进衰退期，进入不做确认
        new_state = (not above_all)
    changed = (new_state != g.is_recession)

    # 先切状态、再算持续天数，保证日志里的「已持续 N 天」含当日
    g.is_recession = new_state
    if new_state:
        if changed:
            g.weak_start_date = today
    else:
        g.weak_start_date = None

    # 持续天数仅用于日志展示（本版已删除强制退出上限）
    if g.is_recession and g.weak_start_date is not None:
        g.weak_days_count = len(get_trade_days(start_date=g.weak_start_date, end_date=today))
    else:
        g.weak_days_count = 0

    if changed and new_state:
        log.info("🔴 【衰退期进入】沪深300 未同时站上全部均线 → 转入衰退期，开始买入低溢价纳指")
    elif changed and not new_state:
        log.info("🟢 【衰退期退出】沪深300 已同时站上全部均线 → 回到正常期，恢复动量选股")
    elif new_state and above_all:
        log.info(f"⏳ 【退出确认中】已连续 {g.recession_recovery_days}/{g.recession_exit_confirm_days} "
                 f"日站上全部均线，未达确认天数 → 维持衰退期")
    elif new_state:
        log.info(f"🔴 【衰退期延续】沪深300 仍未同时站上全部均线，已持续 {g.weak_days_count} 个交易日")
    else:
        log.info("🟢 【正常期延续】沪深300 同时站上全部均线")

    if g.is_recession:
        log.info(f"📊 【衰退期判断】最终状态: 🔴 衰退期（已持续 {g.weak_days_count} 个交易日，无上限）")
        record(衰退期状态=1)
        record(衰退期天数=g.weak_days_count)
    else:
        log.info("📊 【衰退期判断】最终状态: 🟢 正常期")
        record(衰退期状态=0)
        record(衰退期天数=0)
    return g.is_recession


def apply_filters(metrics_list):
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], True),
        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter and not g.is_recession),
        ('均线', lambda m: m['passed_ma'], g.enable_ma_filter and g.is_recession),
        ('成交量', lambda m: m['passed_volume'], g.enable_volume_check),
        ('短期风控', lambda m: m['passed_loss'], g.enable_loss_filter),
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
    log.info(f"【动量得分计算】使用合并池，合计{len(etf_set)}只ETF")
    log.info(f"【当前状态】{'🔴 沪深300衰退期' if g.is_recession else '🟢 正常期'}")

    lookback = max(g.lookback_days, g.volume_lookback, g.ma_lookback) + 20
    today = context.current_dt.date()
    current_data = get_current_data()
    safe_lookback = lookback + 20

    hist_df = get_price(etf_set, count=safe_lookback, end_date=end_date, frequency='1d', fields=['close', 'volume'], panel=False)
    today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt, frequency='1m', fields=['volume'], panel=False, fill_paused=False)

    if hist_df is None or hist_df.empty:
        log.warning("【动量计算】无法获取历史价格数据")
        return []

    today_vols = today_vol_df.groupby('code')['volume'].sum() if (today_vol_df is not None and not today_vol_df.empty) else pd.Series(dtype=float)
    close_pivot = hist_df.pivot(index='time', columns='code', values='close')
    volume_pivot = hist_df.pivot(index='time', columns='code', values='volume')

    # ========== 遍历ETF计算动量得分 ==========
    for etf in etf_set:
        if current_data[etf].paused:
            continue
        if is_temporarily_suspended(etf, context):
            log.debug(f"{etf} {get_security_name(etf)} 盘中临时停牌，跳过计算")
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

    # 按动量得分排序
    all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)

    # ========== 第一步：输出所有ETF排序表格 ==========
    log_buffer = []
    log_buffer.append("")
    log_buffer.append(">>> 第一步：所有ETF按动量得分从大到小排序 <<<")
    for m in all_metrics[:100]:
        def fmt_status(value_str, passed):
            return f"{value_str} {'✅' if passed else '❌'}"
        score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
        r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
        vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
        min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
        loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
        ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
        line = (
            f"{m['etf']} {m['etf_name']}: "
            f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
            f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
            f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
            f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
            f"短期风控: {fmt_status(loss_val, m['passed_loss'])}"
        )
        log_buffer.append(line)

    # ========== 第二步：应用过滤条件 ==========
    filtered_list = apply_filters(all_metrics)
    filtered_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    top_10 = filtered_list[:10]
    log_buffer.append("")
    log_buffer.append(">>> 第二步：符合全部过滤条件的ETF按动量得分从大到小排序(前10名) <<<")
    if top_10:
        for m in top_10:
            def fmt_status(value_str, passed):
                return f"{value_str} {'✅' if passed else '❌'}"
            score_str = f"{m['momentum_score']:.4f}" if m['momentum_score'] != float('-inf') else "nan"
            r2_str = f"{m['r_squared']:.3f}" if not pd.isna(m['r_squared']) else "nan"
            vol_val = f"{m['volume_ratio']:.2f}" if m['volume_ratio'] is not None else "N/A"
            min_ratio = min(m['day_ratios']) if m['day_ratios'] else 'N/A'
            loss_val = f"{min_ratio:.4f}" if isinstance(min_ratio, float) and not pd.isna(min_ratio) else str(min_ratio)
            ma_str = f"MA{g.ma_lookback}: {m['ma_value']:.2f}" if m['ma_value'] is not None else "MA:N/A"
            line = (
                f"{m['etf']} {m['etf_name']}: "
                f"动量得分: {fmt_status(score_str, m['passed_momentum'])}，"
                f"R²: {fmt_status(r2_str, m['passed_r2'])}，"
                f"均线: {fmt_status(ma_str, m['passed_ma'])}，"
                f"成交量比值: {fmt_status(vol_val, m['passed_volume'])}，"
                f"短期风控: {fmt_status(loss_val, m['passed_loss'])}"
            )
            log_buffer.append(line)
    else:
        log_buffer.append("（无符合条件的ETF）")
        full_log = "\n".join(log_buffer)
        log.info(full_log)
        return []

    # ========== 第三步：确定候选池 ==========
    score_key = 'momentum_score'
    if len(top_10) >= g.holdings_num:
        reference_score = top_10[g.holdings_num - 1].get(score_key, float('-inf'))
        ratio = g.score_threshold_ratio if not g.is_recession else 1.0
        score_threshold = reference_score * ratio
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：选取动量得分≥第{g.holdings_num}名({top_10[g.holdings_num - 1]['etf_name']})得分{reference_score:.4f}×{g.score_threshold_ratio}={score_threshold:.4f}的ETF <<<")
        candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
    else:
        log_buffer.append("")
        log_buffer.append(f">>> 第三步：前10名不足{g.holdings_num}只，全部作为候选池 <<<")
        candidate_pool = top_10[:]

    log_buffer.append(f"【候选池】共{len(candidate_pool)}只ETF（按动量得分排序）：")
    for i, item in enumerate(candidate_pool):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")

    # ========== 第四步：结合当前持仓进行调整 ==========
    log_buffer.append("")
    log_buffer.append(">>> 第四步：结合当前持仓进行调整 <<<")
    current_holdings = [sec for sec, pos in context.portfolio.positions.items() if pos.total_amount > 0]
    log_buffer.append(f"当前持仓ETF：{current_holdings}")

    candidate_dict = {item['etf']: item for item in candidate_pool}
    retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
    log_buffer.append(f"其中存在于候选池中的持仓ETF：{[item['etf'] for item in retained]}")

    if len(retained) >= g.holdings_num:
        retained_sorted = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        final_result = retained_sorted[:g.holdings_num]
        log_buffer.append(f"保留的持仓ETF数量({len(retained)})超过目标持仓数({g.holdings_num})，将从保留的ETF中按动量得分取前{g.holdings_num}只作为最终目标。")
    else:
        need = g.holdings_num - len(retained)
        remaining_pool = [item for item in candidate_pool if item['etf'] not in {r['etf'] for r in retained}]
        additional = remaining_pool[:need]
        final_result = retained + additional
        log_buffer.append(f"保留持仓ETF {len(retained)}只，还需补充{need}只。")
        if retained:
            log_buffer.append("保留的ETF（按原有顺序）：")
            for item in retained:
                log_buffer.append(f"  {item['etf_name']}({item['etf']})")
        if additional:
            log_buffer.append("补充的ETF（按动量得分排序）：")
            for i, item in enumerate(additional):
                log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']}) {score_key}: {item.get(score_key, 0):.4f}")

    log_buffer.append(f"【最终目标】共{len(final_result)}只ETF：")
    for i, item in enumerate(final_result):
        log_buffer.append(f"  {i+1}. {item['etf_name']}({item['etf']})")
    log_buffer.append("==================================================")

    full_log = "\n".join(log_buffer)
    log.info(full_log)
    return final_result


# ============================================================================
# 【本版新增】衰退期纳指防御：溢价率计算 + 目标选择
# ============================================================================

def get_latest_nav_map(etf_codes, context):
    """
    取每只ETF最近可得的单位净值。
    返回 {etf: (净值, 净值日期字符串)}，取最近 g.ndx_nav_lookback 个交易日内的最后一个非空值。

    【为什么这样取】
    聚宽没有实时 IOPV，只能拿基金单位净值。QDII 基金净值本来就滞后，而且滞后多少天不确定：

    1) 聚宽官方文档（JQData使用说明）写明：
       「净值数据(get_extras) —— 上市至今，盘后17点到下一交易日9点更新」
       即 13:10 回测时，前一交易日的净值理论上已经入库。
    2) 但 QDII 基金**自己**披露就滞后 T+2~T+3 个交易日
       （跨境结算 + 时差，见《证券投资基金信息披露管理办法》口径）。
       社区实测案例：某 QDII 基金 2021-09-07 当天，9/2、9/3、9/6 的净值仍是 NaN。
    3) 实测 2026-09-16 收盘：行情源显示 159941 是「净值 1.461，净值日期 2026-09-15」，
       广发官网 9/16 的申赎清单里引用的还是 9/14 的净值 1.4715。

    所以「净值日期 ≠ 前一交易日」是**常态，不是数据异常**——有周末、有中美假期错位、
    还有 QDII 本身的披露滞后。本函数因此不假设日期对齐，而是取
    「最近 g.ndx_nav_lookback 个交易日内最后一个非空值」，两种入库口径（按净值日期 /
    按公布日期）都能正确兜到最新一期。
    """
    result = {}
    try:
        start = get_trade_days(end_date=context.previous_date, count=g.ndx_nav_lookback)[0]
        df = get_extras('unit_net_value', etf_codes, start_date=start, end_date=context.previous_date)
    except Exception as e:
        log.warning(f"【溢价率】获取单位净值失败：{e}")
        return result
    if df is None or len(df) == 0:
        log.warning("【溢价率】单位净值为空")
        return result

    # 兼容两种返回格式：宽表（索引=日期，列=证券）与长表（含 time/code/unit_net_value 列）
    if 'unit_net_value' in getattr(df, 'columns', []):
        try:
            df = df.pivot(index='time', columns='code', values='unit_net_value')
        except Exception:
            return result

    for etf in etf_codes:
        if etf not in df.columns:
            continue
        series = df[etf].dropna()          # 关键：dropna 后取最后一期，自动跳过尚未披露的 NaN
        if len(series) == 0:
            continue
        result[etf] = (float(series.iloc[-1]), str(series.index[-1])[:10])
    return result


def get_ndx_name(etf):
    if hasattr(g, 'ndx_etf_names') and etf in g.ndx_etf_names:
        return g.ndx_etf_names[etf]
    return get_security_name(etf)


def is_etf_tradable(etf, context, data=None):
    """判断ETF当前是否可正常交易。返回 (是否可交易, 不可交易的原因)"""
    data = data if data is not None else get_current_data()
    try:
        d = data[etf]
    except Exception:
        return False, "取不到行情"
    if d.paused:
        return False, "全天停牌"
    price = d.last_price
    if price is None or price <= 0:
        return False, "无有效现价"
    if d.high_limit and price >= d.high_limit:
        return False, f"涨停({price:.3f})"
    if d.low_limit and price <= d.low_limit:
        return False, f"跌停({price:.3f})"
    if is_temporarily_suspended(etf, context):
        return False, "盘中临时停牌"
    return True, ""


def select_recession_target(context):
    """
    衰退期目标选择：在纳指池中挑「溢价率最低」的1只。
    溢价率 = 当日13:10现价 ÷ 最近可得单位净值 − 1
    13只全部不可交易时，回退到 g.ndx_fallback_etf（518880 黄金ETF）。
    结果写入 g.recession_target_etf。
    """
    log.info("【衰退期纳指防御】开始筛选纳指池（共{}只）".format(len(g.ndx_etf_pool)))
    data = get_current_data()
    nav_map = get_latest_nav_map(g.ndx_etf_pool, context)
    log.info(f"【溢价率】取得 {len(nav_map)}/{len(g.ndx_etf_pool)} 只ETF的单位净值")

    rows = []
    for etf in g.ndx_etf_pool:
        name = get_ndx_name(etf)
        ok, reason = is_etf_tradable(etf, context, data)
        if not ok:
            log.info(f"  ⛔ {etf} {name} 不可交易（{reason}），剔除")
            continue
        nav_info = nav_map.get(etf)
        if nav_info is None or nav_info[0] <= 0:
            log.info(f"  ⛔ {etf} {name} 取不到有效单位净值，剔除")
            continue
        nav, nav_date = nav_info
        price = data[etf].last_price
        rows.append({
            'etf': etf,
            'name': name,
            'price': price,
            'nav': nav,
            'nav_date': nav_date,
            'premium': price / nav - 1,
        })

    rows.sort(key=lambda r: r['premium'])

    prev_date_str = str(context.previous_date)[:10]
    log_buffer = []
    log_buffer.append("")
    log_buffer.append(">>> 衰退期：纳指池按溢价率从低到高排序（溢价率 = 13:10现价 ÷ 最近可得单位净值 − 1）<<<")
    if rows:
        for i, r in enumerate(rows):
            mark = "  ← 选中" if i == 0 else ""
            log_buffer.append(
                f"  {i+1:>2}. {r['etf']} {r['name']}: "
                f"现价 {r['price']:.3f} / 净值 {r['nav']:.4f} (净值日期 {r['nav_date']}) "
                f"→ 溢价率 {r['premium']:+.2%}{mark}"
            )
            if r['etf'] == '159509.XSHE':
                log_buffer.append("      * 159509 跟踪的是纳斯达克科技市值加权指数，与其余12只的纳指100不是同一指数，溢价率不完全可比")
    else:
        log_buffer.append("  （纳指池中无一只可交易）")

    if rows:
        best = rows[0]
        g.recession_target_etf = best['etf']

        # ---- 净值滞后说明（QDII 净值滞后是常态，不是异常，只做如实展示）----
        nav_dates = sorted({r['nav_date'] for r in rows})
        try:
            lag_days = (pd.Timestamp(prev_date_str) - pd.Timestamp(best['nav_date'])).days
        except Exception:
            lag_days = None
        lag_desc = f"{lag_days} 个自然日" if lag_days is not None else "未知"
        if lag_days:
            log_buffer.append(
                f"  ℹ️ 净值日期 {best['nav_date']}，A股前一交易日 {prev_date_str}，滞后 {lag_desc}。"
                f"溢价率因此含这段期间的美股涨跌，绝对值会整体偏移；"
                f"但13只跟踪同一指数，偏移是公共项，**同池排序不受影响**。"
            )
        else:
            log_buffer.append(f"  ℹ️ 净值日期 {best['nav_date']}，与A股前一交易日同日，无滞后。")
        # ---- 真正需要提示的：池内净值日期不一致，跨ETF比较才有偏 ----
        if len(nav_dates) > 1:
            lagging = [f"{r['name']}={r['nav_date']}" for r in rows if r['nav_date'] != nav_dates[-1]]
            log_buffer.append(
                f"  ⚠️ 池内净值日期不一致（最新 {nav_dates[-1]}），以下标的净值更旧，与其余标的的溢价率不完全可比：{lagging}"
            )

        log_buffer.append(f">>> 【衰退期最终目标】{best['etf']} {best['name']}（溢价率 {best['premium']:+.2%}）<<<")
        record(目标溢价率=round(best['premium'] * 100, 4))
        log.info("\n".join(log_buffer))
        log.info(f"✅ 【衰退期目标】买入溢价率最低的纳指：{best['etf']} {best['name']}，溢价率 {best['premium']:+.2%}")
    else:
        g.recession_target_etf = None
        log.info("\n".join(log_buffer))
        # 纳指池全部不可交易 → 回退兜底标的
        ok, reason = is_etf_tradable(g.ndx_fallback_etf, context, data)
        if ok:
            g.recession_target_etf = g.ndx_fallback_etf
            log.info(f"🛡️ 【衰退期兜底】纳指池无一只可交易，回退买入 {g.ndx_fallback_etf} {get_security_name(g.ndx_fallback_etf)}")
        else:
            log.info(f"💤 【衰退期兜底】纳指池与兜底标的 {g.ndx_fallback_etf} 均不可交易（{reason}），今日空仓")
    return g.recession_target_etf


def execute_sell_trades(context):
    log.info("========== 卖出操作开始 ==========")
    if g.is_recession:
        # 【本版改动】衰退期：目标来自 select_recession_target 选出的「低溢价纳指」
        target_etfs = [g.recession_target_etf] if getattr(g, 'recession_target_etf', None) else []
        if target_etfs:
            etf = target_etfs[0]
            log.info(f"确定最终目标（衰退期·纳指防御）: {etf} {get_ndx_name(etf)}")
        else:
            log.info("💤 衰退期且纳指池与兜底标的均不可交易，今日空仓")
    else:
        ranked_etfs = getattr(g, 'ranked_etfs_result', [])
        target_etfs = []
        if ranked_etfs:
            for metrics in ranked_etfs[:g.holdings_num]:
                target_etfs.append(metrics['etf'])
                log.info(f"确定最终目标: {metrics['etf']} {metrics['etf_name']}")
        else:
            if check_defensive_etf_available(context):
                target_etfs = [g.defensive_etf]
                etf_name = get_security_name(g.defensive_etf)
                log.info(f"🛡️ 确定最终目标(防御模式): {g.defensive_etf} {etf_name}")
            else:
                log.info("💤 无最终目标(空仓模式)")
                target_etfs = []
    g.target_etfs_list = target_etfs

    current_positions = list(context.portfolio.positions.keys())
    target_set = set(target_etfs)
    sell_count = 0
    for security in current_positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            success = smart_order_target_value(security, 0, context)
            if success:
                sell_count += 1
                log.info(f"✅ 已成功卖出: {security} {security_name}")
    log.info(f"本次共计划卖出{sell_count}只ETF。")
    log.info("========== 卖出操作完成 ==========")


def execute_buy_trades(context):
    log.info("========== 买入操作开始 ==========")
    target_etfs = g.target_etfs_list
    if not target_etfs:
        log.info("根据计算的结果，今日无目标ETF，保持空仓")
        log.info("========== 买入操作完成 ==========")
        return

    current_positions = set(context.portfolio.positions.keys())
    etfs_to_buy = [etf for etf in target_etfs if etf not in current_positions]
    actual_holding_count = len(current_positions)
    max_buy_count = max(0, g.holdings_num - actual_holding_count)
    num_etfs_to_buy = min(len(etfs_to_buy), max_buy_count)
    if num_etfs_to_buy <= 0:
        log.info(f"当前实际持仓数量({actual_holding_count})已达到或超过目标({g.holdings_num})，无需买入")
        log.info("========== 买入操作完成 ==========")
        return

    etfs_to_buy = etfs_to_buy[:num_etfs_to_buy]
    log.info(f"当前实际持仓: {actual_holding_count}只, 目标持仓: {g.holdings_num}只, 本次计划买入: {num_etfs_to_buy}只")

    # 动态分配资金，避免可用现金为负
    for i, etf in enumerate(etfs_to_buy):
        remaining_cash = context.portfolio.available_cash
        if remaining_cash < g.min_money:
            log.info(f"可用现金 {remaining_cash:.2f} 不足最小交易额 {g.min_money:.2f}，停止买入")
            break
        remaining_to_buy = len(etfs_to_buy) - i
        target_value_for_this_etf = remaining_cash // remaining_to_buy
        # 最后一笔可使用剩余全部现金，但确保不小于最小交易额
        if target_value_for_this_etf < g.min_money and remaining_cash >= g.min_money:
            target_value_for_this_etf = remaining_cash
        log.info(f"为 {etf} 分配目标金额: {target_value_for_this_etf:.2f} 元 (剩余现金 {remaining_cash:.2f}, 待买数量 {remaining_to_buy})")
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
        else:
            log.info(f"❌ ETF {etf} 下单失败")
    log.info("========== 买入操作完成 ==========")


def check_intraday_trend(security, context):
    """
    判断ETF盘中短期趋势
    基于最近N分钟分钟线收盘价的线性回归斜率（归一化处理）
    返回True表示上涨趋势，False表示下跌趋势
    """
    try:
        minute_data = get_price(
            security,
            end_date=context.current_dt,
            count=g.trend_lookback_minutes,
            frequency='1m',
            fields=['close'],
            skip_paused=False,
            fq='pre'
        )
        if minute_data is None or minute_data.empty:
            log.info(f"【趋势判断】{security} 无分钟数据，默认上涨趋势")
            return True
        closes = minute_data['close'].values
        # 过滤掉价格为0的无效数据（停牌时段）
        closes = closes[closes > 0]
        if len(closes) < 5:
            log.info(f"【趋势判断】{security} 有效分钟数据不足({len(closes)}根)，默认没有上涨趋势")
            return False
        # 线性回归斜率判断趋势方向
        x = np.arange(len(closes))
        slope = np.polyfit(x, closes, 1)[0]
        # 斜率归一化：转为每分钟涨跌幅(%)，消除价格量纲影响，便于跨标的比较
        mean_price = closes.mean()
        slope_pct = slope / mean_price * 100 if mean_price > 0 else 0
        # 归一化斜率 > 阈值 才判定为上涨趋势
        is_uptrend = slope_pct > g.trend_slope_threshold
        trend_desc = "上涨" if is_uptrend else "下跌"
        log.info(f"【趋势判断】{security} 最近{len(closes)}分钟归一化斜率={slope_pct:.6f}%/min(阈值{g.trend_slope_threshold})，判定为{trend_desc}趋势")
        return is_uptrend
    except Exception as e:
        log.info(f"【趋势判断】{security} 异常: {e}，默认上涨趋势")
        return True


def execute_buy_with_trend(context, force=False):
    """
    带趋势判断的买入执行函数
    force=False: 仅买入上涨趋势的ETF，下跌趋势的保留在待买列表
    force=True:  强制买入所有待买ETF（用于14:55）
    """
    if not g.pending_buy_etfs:
        return
    # 过滤掉已持仓的ETF
    current_positions = set(context.portfolio.positions.keys())
    g.pending_buy_etfs = [etf for etf in g.pending_buy_etfs if etf not in current_positions]
    if not g.pending_buy_etfs:
        return

    current_time = context.current_dt.strftime('%H:%M')
    mode_desc = "强制买入" if force else "趋势判断"
    log.info(f"========== 买入操作开始（{mode_desc} {current_time}）==========")

    # 区分：本次买入的ETF 和 仍待等待的ETF
    etfs_to_buy_now = []
    still_pending = []
    for etf in g.pending_buy_etfs:
        etf_name = get_security_name(etf)
        if force:
            etfs_to_buy_now.append(etf)
            log.info(f"⏰ {current_time} 强制买入 {etf} {etf_name}")
        else:
            is_uptrend = check_intraday_trend(etf, context)
            if is_uptrend:
                etfs_to_buy_now.append(etf)
                log.info(f"📈 {current_time} {etf} {etf_name} 趋势上涨，立即买入")
            else:
                still_pending.append(etf)
                log.info(f"📉 {current_time} {etf} {etf_name} 趋势下跌，等待下次判断")

    # 动态分配资金：本次买入 + 仍待等待 的ETF均分可用现金
    total_count = len(etfs_to_buy_now) + len(still_pending)
    for i, etf in enumerate(etfs_to_buy_now):
        remaining_cash = context.portfolio.available_cash
        if remaining_cash < g.min_money:
            log.info(f"可用现金 {remaining_cash:.2f} 不足最小交易额 {g.min_money:.2f}，停止买入")
            break
        remaining_to_buy = total_count - i
        target_value_for_this_etf = remaining_cash // remaining_to_buy
        # 最后一笔可使用剩余全部现金，但确保不小于最小交易额
        if target_value_for_this_etf < g.min_money and remaining_cash >= g.min_money:
            target_value_for_this_etf = remaining_cash
        etf_name = get_security_name(etf)
        log.info(f"为 {etf} {etf_name} 分配目标金额: {target_value_for_this_etf:.2f} 元 (剩余现金 {remaining_cash:.2f}, 总待买 {remaining_to_buy})")
        success = smart_order_target_value(etf, target_value_for_this_etf, context)
        if success:
            log.info(f"✅ ETF {etf} 下单成功")
        else:
            log.info(f"❌ ETF {etf} 下单失败")

    g.pending_buy_etfs = still_pending
    if still_pending:
        log.info(f"⏳ 仍待趋势确认的ETF: {still_pending}")
    else:
        log.info("✅ 所有待买ETF已处理完毕")
    log.info(f"========== 买入操作完成（{mode_desc}）==========")


def check_pending_buys_trend(context):
    """13:40/14:10/14:40 趋势复检：对待买ETF重新判断趋势"""
    if not g.pending_buy_etfs:
        return
    log.info("★" * 80)
    log.info("▶️ 【趋势复检】检查待买ETF趋势...")
    execute_buy_with_trend(context, force=False)
    if g.pending_buy_etfs:
        log.info(f"⏳ 仍在等待的ETF: {g.pending_buy_etfs}")
    log.info("⏸️ 【趋势复检】执行完毕！")


def force_buy_pending(context):
    """14:55 强制买入所有剩余待买ETF（无论趋势）"""
    if not g.pending_buy_etfs:
        return
    log.info("★" * 80)
    log.info("▶️ 【14:55强制买入】强制买入所有待买ETF...")
    execute_buy_with_trend(context, force=True)
    log.info("⏸️ 【14:55强制买入】执行完毕！")


def is_temporarily_suspended(security, context, minute_count=10):
    """
    判断ETF是否盘中临时停牌
    通过检查最近N分钟是否有成交来判断，若无成交则视为临时停牌
    """
    try:
        # 获取最近N分钟的分钟线数据
        minute_data = get_price(
            security,
            end_date=context.current_dt,
            count=minute_count,
            frequency='1m',
            fields=['volume'],
            skip_paused=False,
            fq='pre'
        )
        # 无数据或数据为空，视为停牌
        if minute_data is None or minute_data.empty:
            return True
        # 最近N分钟成交量都为0，视为临时停牌
        if (minute_data['volume'] == 0).all():
            return True
        return False
    except Exception as e:
        log.debug(f"临时停牌检测异常 {security}: {e}")
        return False  # 异常时默认认为正常，避免误判


def smart_order_target_value(security, target_value, context):
    """
    智能下单：根据目标市值调整持仓，处理停牌、涨跌停、最小交易金额、T+1
    """
    data = get_current_data()
    name = get_security_name(security)

    # ========== 1. 全天停牌检测 ==========
    if data[security].paused:
        log.info(f"{security} {name} 全天停牌，跳过交易")
        return False
    # ========== 2. 盘中临时停牌检测 ==========
    if is_temporarily_suspended(security, context):
        log.info(f"{security} {name} 盘中临时停牌，跳过交易")
        return False
    price = data[security].last_price
    if price == 0:
        log.info(f"{security} {name} 当前价格为0，跳过交易")
        return False

    # ========== 3. 买入时使用预估成交价（绝对滑点 + 佣金）计算股数 ==========
    if target_value > 0:
        estimated_price = price + g.slippage_tick                      # 绝对滑点：买入成交价 ≈ 最新价 + 1 个最小变动单位
        unit_cost = estimated_price * (1 + g.commission_rate)          # 每股实际占用现金（含佣金）
        safe_value = max(0.0, target_value - g.min_commission)         # 预留最低佣金
        target_amount = int(safe_value / unit_cost)
        target_amount = (target_amount // 100) * 100
        if target_amount <= 0:
            target_amount = 100
        # 二次校验：用实时可用现金严格限制（兜底，同样含滑点与佣金）
        max_shares = int(max(0.0, context.portfolio.available_cash - g.min_commission) / unit_cost)
        max_shares = (max_shares // 100) * 100
        if max_shares < target_amount:
            target_amount = max_shares
        if target_amount <= 0:
            log.info(f"{security} {name}: 现金不足买100股，跳过")
            return False
    else:
        target_amount = 0

    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount

    # ========== 4. 涨跌停检测（统一：涨停跌停都不交易） ==========
    if data[security].last_price >= data[security].high_limit:
        log.info(f"{security} {name} 当前涨停，跳过交易")
        return False
    if data[security].last_price <= data[security].low_limit:
        log.info(f"{security} {name} 当前跌停，跳过交易")
        return False

    trade_val = abs(diff) * price
    if 0 < trade_val < g.min_money:
        log.info(f"{security} {name} 交易金额{trade_val:.2f} < {g.min_money}，跳过")
        return False

    # ========== 5. T+1检查（仅卖出时） ==========
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            log.info(f"{security} {name} 当天买入不可卖出(T+1)")
            return False
        diff = -min(abs(diff), closeable)

    # ========== 6. 执行下单 ==========
    if diff != 0:
        order_result = order(security, diff)
        if order_result:
            if diff > 0:
                log.info(f"📥 买入 {security} {name} 数量{abs(diff)} 价格{price:.3f} (预估含成本价: {estimated_price:.3f})")
            else:
                log.info(f"📤 卖出 {security} {name} 数量{abs(diff)} 价格{price:.3f}")
            return True
        else:
            log.warning(f"下单失败: {security} {name}，数量{diff}")
            return False
    return False


def minute_level_stop_loss(context):
    if not g.use_fixed_stop_loss:
        return
    current_time = context.current_dt.strftime('%H:%M')
    if not (('09:40' < current_time < '10:29') or ('10:40' < current_time < '11:30') or ('13:00' < current_time < '14:57')):
        return
    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0 or position.closeable_amount <= 0:
            continue
        current_price = current_data[security].last_price
        if current_price <= 0:
            continue
        cost_price = position.avg_cost
        if cost_price <= 0:
            continue
        if current_price <= cost_price * g.fixedStopLossThreshold:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"🚨 【分钟级固定止损】{security} {security_name} 触发止损，亏损: {loss_percent:.2f}%")
            smart_order_target_value(security, 0, context)


def get_security_name(security):
    try:
        if hasattr(g, 'ndx_etf_names') and security in g.ndx_etf_names:
            return g.ndx_etf_names[security]
        if hasattr(g, 'etf_names_dict') and security in g.etf_names_dict:
            return g.etf_names_dict[security]
        return get_security_info(security).display_name
    except Exception:
        return "未知名称"


def check_defensive_etf_available(context):
    ok, reason = is_etf_tradable(g.defensive_etf, context)
    if not ok:
        log.info(f"防御性ETF {g.defensive_etf} 不可交易（{reason}）")
    return ok


def trade(context):
    pass
