# Clone from JoinQuant
# postId: 0593c701415e4d04ec0761be9dfe2114
# backtestId: 1fa08387024c79aa76fbdedd87bcf416
# title: 大类ETF轮动回测

import numpy as np
import pandas as pd
import talib
import math  # 原克隆文漏了这行：math.exp 在 get_rank / get_rank2 中用到，缺失会 NameError 崩溃


#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 设置滑点 https://www.joinquant.com/view/community/detail/a31a822d1cfa7e83b1dda228d4562a70
    set_slippage(FixedSlippage(0.001))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, close_commission=0.0002, close_today_commission=0, min_commission=1), type='fund')
    # 过滤一定级别的日志
    log.set_level('system', 'error')

    # ================= 参数 =================
    # 股票池由原 9 只扩容到 62 只（与 ETF轮动_池B_63只.py 同一份名单，仅删除无效标的 159579）
    g.etf_pool = [
        # —— 原克隆文 9 只（跨资产） ——
        "513100.XSHG",  # 纳指ETF
        "513520.XSHG",  # 日经ETF
        "513030.XSHG",  # 德国ETF
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色ETF
        "501018.XSHG",  # 南方原油
        "511090.XSHG",  # 30年国债ETF
        "512890.XSHG",  # 红利低波
        "159915.XSHE",  # 创业板100
        # —— 用户新增 6 只（原 159579.XSHE 已剔除：聚宽判为无效标的） ——
        "515220.XSHG",  # 煤炭ETF
        "588710.XSHG",  # 科创半导体
        "159792.XSHE",  # 港股通互联网
        "513080.XSHG",  # 法国ETF
        "159985.XSHE",  # 豆粕ETF
        # —— EBK 导入 48 只 ——
        "512880.XSHG",  # 证券ETF
        "588200.XSHG",  # 科创芯片ETF
        "515880.XSHG",  # 通信ETF
        "159516.XSHE",  # 半导体设备ETF
        "513180.XSHG",  # 恒生科技ETF
        "588080.XSHG",  # 科创50ETF
        "588170.XSHG",  # 科创半导体ETF
        "159995.XSHE",  # 芯片ETF
        "563360.XSHG",  # A500ETF
        "512170.XSHG",  # 医疗ETF
        "510880.XSHG",  # 红利ETF
        "159570.XSHE",  # 港股通创新药ETF
        "159819.XSHE",  # 人工智能ETF
        "512480.XSHG",  # 半导体ETF
        "512400.XSHG",  # 有色金属ETF
        "513090.XSHG",  # 香港证券ETF
        "159992.XSHE",  # 创新药ETF
        "159326.XSHE",  # 电网设备ETF
        "159530.XSHE",  # 机器人ETF
        "159206.XSHE",  # 卫星ETF
        "159509.XSHE",  # 纳指科技ETF
        "159781.XSHE",  # 科创创业ETF
        "159928.XSHE",  # 消费ETF
        "159201.XSHE",  # 自由现金流ETF
        "512070.XSHG",  # 证券保险ETF
        "512690.XSHG",  # 酒ETF
        "159870.XSHE",  # 化工ETF
        "513310.XSHG",  # 中韩半导体ETF
        "512800.XSHG",  # 银行ETF
        "517520.XSHG",  # 黄金股ETF
        "159869.XSHE",  # 游戏ETF
        "159611.XSHE",  # 电力ETF
        "513650.XSHG",  # 标普500ETF
        "512710.XSHG",  # 军工龙头ETF
        "159865.XSHE",  # 养殖ETF
        "516150.XSHG",  # 稀土ETF
        "515790.XSHG",  # 光伏ETF
        "159796.XSHE",  # 电池ETF
        "159566.XSHE",  # 储能电池ETF
        "515230.XSHG",  # 软件ETF
        "513530.XSHG",  # 港股通红利ETF
        "159608.XSHE",  # 稀有金属ETF
        "560280.XSHG",  # 工程机械ETF
        "516510.XSHG",  # 云计算ETF
        "560080.XSHG",  # 中药ETF
        "515030.XSHG",  # 新能源车ETF
        "159667.XSHE",  # 工业母机ETF
        "513950.XSHG",  # 恒生红利ETF
    ]
    # 池子预处理：仅做格式清洗，不判存在性！
    # 坑：get_security_info(code) 在 initialize 会按"回测起点"判断该 ETF 是否已上市，
    #     上市日晚于回测起点的 ETF 会返回 None -> 被误判为无效而剔除
    #     （如 588710 科创半导体 2025-06-04 上市，回测起点设 2021/2022 时必被误杀）。
    #     因此存在性 / 取数能否成功一律交给运行时 attribute_history 的 try/except 跳过。
    _cleaned = []
    for _c in g.etf_pool:
        _code = str(_c).split()[0].split('(')[0].strip()   # 防粘贴时带 "515220.XSHG (MTETF)" 这类注释
        if len(_code) >= 6 and _code[-5:] in ('.XSHG', '.XSHE'):
            _cleaned.append(_code)
        else:
            log.warn("跳过格式非法标的: %s -> 清洗后: %s" % (_c, _code))
    g.etf_pool = _cleaned

    g.m_days = 25 # 默认动量参考天数
    g.auto_day = True # 是否自动根据历史波动率动态调整动量的lookback天数
    g.min_days = 20 # 最小lookback天数
    g.max_days = 60 # 最大lookback天数

    # 分仓持仓数：取动量排名前 N 只等权持有（原为"只买最高分 1 只"）
    g.target_num = 3
    # 同集群去重上限：同类型最多保留只数
    g.max_per_cluster = 2

    # ================= 风控开关（全部集中在这里，回测时改一行即可消融） =================
    g.RISK = {
        'moat':   True,   # M1 换仓门槛：新候选须达到基准 ×(1+switch_gap) 才允许换仓
        'buffer': True,   # M2 Top-N 缓冲：持仓只要还在动量前 buffer_n 名内就不卖
        'brake':  True,   # 阶段2 组合级回撤刹车（两级）
        'recover_gate': True,  # ★v8（M1）：恢复满仓须"沪深300 > MA10"（外生趋势确认）
    }
    g.switch_gap = 0.15   # M1 门槛系数（0.15 = 候选须高出基准 15% 才值得换；
                          #              0.0 = 只要求不低于基准；彻底关闭 M1 用 g.RISK['moat']=False）
    g.buffer_n   = 5      # M2 缓冲区宽度（须 >= g.target_num；设成 = g.target_num 等于关闭缓冲）

    # —— v7「只增不减」修正参数 ——
    # G1：M1 门槛基准打折 + 死仓豁免。治基线里"最弱持仓永远换不掉"的死锁
    #     （24 年 9 月连续 5 次门槛不足，锁死死仓、错过主升 6~7 个交易日）。
    g.moat_keep_frac = 1.0    # 基准 = max(被换出持仓分, moat_keep_frac × 缓冲内最弱持仓分)
                              # ★默认 1.0 = **完全等于基线**（max(hs, keep_min)），不打折。
                              #   设 0.5 才启用"基准打折"：实测会放开 271/317 = 85% 的拦截
                              #   （换手显著上升、方向未知），属**激进实验**，请单独回测后再定。
    g.moat_dead      = 0.05   # 【默认开】持仓分 ≤ 该值视为"死仓"，无条件换出（不看门槛）
                              # 实测全周期放开 79 次（占基线 317 次拦截的 25%）
                              # 设 -1.0 可关闭该豁免
    # G2：同日二次切换保护 —— 9:50 刚把敞口从 1/3 恢复满仓的日子，
    #     14:50 不再因同一波日内噪声又降回去（消掉"恢复当日又降仓"的 0 天抖动）。
    g.brake_same_day_guard = True
    g.last_restore_date    = None   # 最近一次"敞口恢复到 100%"的日期
    # G2 可选加强：降仓最短维持交易日数。1 = 与基线行为完全一致（触发次日即可恢复）；
    #              2 = 至少连续降仓 2 个交易日（消"降 1 天就恢复"的 1 天抖动，代价是敞口略降）。
    g.brake_min_hold  = 1
    g.reduce_days     = 0     # 当前这一轮降仓已持续的交易日数（供 brake_min_hold 判断）

    # —— ★v8（M1）恢复端"外生趋势确认"参数 ——
    # 问题（24~26 日志铁证）：恢复线 = 触发线（同为 -6%）。13 次"减仓→恢复"的恢复读数
    #   全部落在 -4.88% ~ -5.99%，净值弹回 0.1pp 就立刻满仓买回；其中 9/13 在 ≤2 个
    #   交易日内又被打回降仓，最极端两例是"恢复满仓次日即清仓"
    #   （2026-06-22 恢复 → 06-23 清仓；2026-07-16 恢复 → 07-17 清仓）。
    #   => 卖在 -6%、买回在 -5%、再跌到 -8%，一轮往返白付摩擦，粗估 -20pp。
    # 修法：触发线 / 清仓线 / 冷却 / 阈值**全部不动**，只把"恢复满仓"收紧为
    #   「dd > -brake_l1  且  沪深300 收盘 > 其 ma_n 日均线」。
    #   判据是**市场指数**（外生），不是组合自身净值 => 不会像 v3(T1) 那样
    #   "降仓→净值恢复慢→摸不到自己的线→自锁"。
    g.recover_index     = '000300.XSHG'   # 判据来源（= 基准沪深300，外生）
    g.recover_ma_n      = 10      # 趋势线周期：沪深300 收盘 > MA(该值) 才允许恢复（试 5/10/20/60）
    g.recover_ma_margin = 0.0     # 可选偏离度缓冲：(px/ma - 1) 须 > 该值（0 = 只要站上）
    # ▸ 安全阀（默认开）：净值已回到"距峰值 3% 以内"时，无论指数在哪都直接恢复。
    #   理由：这套池子大量海外/黄金/红利资产，沪深300 不能完全代表其趋势；
    #   若组合创新高而沪深300 长期在 MA10 下方，纯指数闸会把组合**长期锁在 1/3**。
    #   阀值取得足够深（3%），所以**不会**削弱 M1 —— 24~26 的 13 次往返读数全部落在
    #   -4.88%~-5.99%，都仍在 -3% 之外，照样被拦。设 -1 关闭（= 纯指数闸）。
    g.recover_force_dd  = 0.03

    # —— 阶段2 刹车参数 ——
    g.brake_l1       = 0.06    # 一级：净值距峰值回撤 6% -> 敞口降至 g.brake_l1_scale
    g.brake_l2       = 0.09    # 二级：净值距峰值回撤 9% -> 全清仓 + 冷却 g.brake_cool 个交易日
    g.brake_l1_scale = 1.0 / 3.0   # 一级刹车后的总敞口
    g.brake_cool     = 7       # 冷却交易日数（回场条件：不设，冷却结束自动恢复）
    g.brake_intraday = True    # 14:50 补检（只卖不买）
    g.peak_nav       = None    # 净值峰值锚
    g.cooldown_left  = 0       # 剩余冷却交易日
    g.brake_state    = 'normal'  # normal / reduced / cooldown
    g.last_expo      = 1.0     # 上一交易日生效的敞口（用于判断"敞口档位是否变化，需否再平衡"）

    # 最近一次排名的分数表（由 get_rank / get_rank2 写入，供 _build_targets 做门槛判定）
    g.last_scores = {}

    # —— 同集群去重：按 ETF 简称关键词聚类，同类型最多保留 g.max_per_cluster 只 ——
    # 名称来源优先用内置静态表 _ETF_NAME_HINT（确定性最高，不受 initialize 绑回测起点影响），
    # 表外的新增 ETF 再退回 get_security_info 查询。
    try:
        _names = {}
        for _c in g.etf_pool:
            _nm = _ETF_NAME_HINT.get(_c, '')
            if not _nm:
                try:
                    _info = get_security_info(_c)
                    _nm = _info.display_name if _info is not None else ''
                except Exception:
                    _nm = ''
            _names[_c] = _nm or ''
        g.etf_pool = _dedup_by_cluster(g.etf_pool, _names, g.max_per_cluster)
    except Exception as e:
        log.warn("集群去重跳过（名称获取失败，池子保持不变）: %s" % e)

    run_daily(trade, '9:50')          # 主检：每天 9:50 决定目标组合
    if g.brake_intraday:
        run_daily(brake_monitor, '14:50')   # 补检：只做刹车（降敞口/清仓），绝不建仓


# 基于年化收益和判定系数打分的动量因子轮动 https://www.joinquant.com/post/26142
def get_rank(etf_pool):
    data = pd.DataFrame(index=etf_pool, columns=["annualized_returns", "r2", "score"])
    current_data = get_current_data()
    for etf in etf_pool:
        # 获取数据（容错：取不到的标的直接跳过，避免单只坏代码中断整日运行）
        try:
            df = attribute_history(etf, g.m_days, "1d", ["close", "high"])
        except Exception as e:
            log.warn("跳过无法取数的标的 %s: %s" % (etf, e))
            continue
        if df is None or len(df) < 4:
            continue
        prices = np.append(df["close"].values, current_data[etf].last_price)

        # 设置参数
        y = np.log(prices)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))

        # 计算年化收益率
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1

        # 计算R²
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0

        # 计算得分
        data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]

        # 过滤近3日跌幅超过5%的ETF
        if min(prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4]) < 0.95:
            data.loc[etf, "score"] = 0

    # log.info(data)

    # 过滤ETF，并按得分降序排列
    data = data.query("0 < score < 6").sort_values(by="score", ascending=False)
    # 记录分数表（供换仓门槛使用）
    g.last_scores = {str(_k): float(_v) for _k, _v in data["score"].items()}

    return data.index.tolist()

def get_etf_premium_rate_real(context,etf_code):
    """
    在实盘中计算ETF基金的溢价率
    etf_code: ETF代码，如 '510050.XSHG'
    """
    try:
        # 获取当前数据对象
        etf_price = get_price(etf_code, start_date=context.previous_date, end_date=context.previous_date).iloc[-1]['close']
        iopv = get_extras('unit_net_value',etf_code, start_date=context.previous_date, end_date=context.previous_date).iloc[-1].values[0]

        #  计算溢价率
        if iopv is not None and iopv != 0:
            premium_rate = (etf_price - iopv) / iopv * 100
        else:
            premium_rate = 0
    except Exception:
        # 容错：拿不到净值/价格的新品种（如部分 QDII）按"无溢价"处理，不阻塞排名
        return 0, None, None

    return premium_rate, etf_price, iopv

def get_rank2(context,etf_pool):
    data = pd.DataFrame(index=etf_pool, columns=["annualized_returns", "r2", "score"])
    current_data = get_current_data()
    for etf in etf_pool:
        # 获取数据（容错：取不到的标的直接跳过）
        try:
            df = attribute_history(etf, g.max_days+10, "1d", ["close", "high", "low"])
        except Exception as e:
            log.warn("跳过无法取数的标的 %s: %s" % (etf, e))
            continue
        if df is None or len(df) < g.min_days:
            continue

        # 过滤历史数据不足的标的
        if len(df) < (g.max_days+10) or df["low"].isna().sum() > g.max_days  or df["close"].isna().sum() > g.max_days or df["high"].isna().sum() > g.max_days:
            continue

        # 基于ATR
        long_atr = talib.ATR(df["high"], df["low"], df["close"], timeperiod=g.max_days)
        short_atr = talib.ATR(df["high"], df["low"], df["close"], timeperiod=g.min_days)
        # print(long_atr[-1])
        # print(short_atr[-1])
        lookback = int(g.min_days + (g.max_days - g.min_days) * (1 - min(0.9, short_atr[-1]/long_atr[-1])))


        # 原文是基于每日收盘收益率标准差来计算波动率
        # https://mp.weixin.qq.com/s/bzMeZA97uB9O0GtCcxHHsw?click_id=3
        # df['return'] = df['close'].pct_change()
        # long_vol = float(np.std(df['return'][:], ddof=1))
        # short_vol = float(np.std(df['return'][-g.min_days:], ddof=1))
        # # print(long_vol)
        # # print(short_vol)
        # lookback = int(g.min_days + (g.max_days - g.min_days) * (1 - min(0.9, short_vol/long_vol)))

        prices = np.append(df["close"].values, current_data[etf].last_price)
        prices = prices[-lookback:]
        # log.info(f"{etf} lookback days :{lookback}, {len(prices)}")

        # 设置参数
        y = np.log(prices)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))

        # 计算年化收益率
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1

        # 计算R²
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0

        # 计算得分
        data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]

        # 风控
        # 三天内有一天跌超5%
        con1 = min(prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4]) < 0.95
        # 三天内每天都跌，总共跌超4%
        con2 = (prices[-1]< prices[-2])&(prices[-2]< prices[-3])&(prices[-3]< prices[-4])&(prices[-1]/prices[-4]< 0.95)
                # 三天内每天都跌，总共跌超4%
        con3 = (prices[-2]< prices[-3])&(prices[-3]< prices[-4])&(prices[-4]< prices[-5])&(prices[-2]/prices[-5]< 0.95)
        # 后面也可以增加其他情况，比如近4天，近5天等
        # 过滤近期跌幅过大的ETF
        if con1|con2|con3:
            data.loc[etf, "score"] = 0 
        # print(prices,etf)
        # 过滤溢价率超过6%的
        if get_etf_premium_rate_real(context,etf)[0]>=5:
            data.loc[etf, "score"] = data.loc[etf, "score"]-1

    # log.info(data)

    # 过滤ETF，并按得分降序排列
    data = data.sort_values(by="score", ascending=False).reset_index()
    # data['name'] = data['index'].apply(lambda x:get_security_info(x).display_name)
    # data['premium_rate'] = data['index'].apply(lambda x:get_etf_premium_rate_real(context,x)[0])
    # print(data[['index','name','score','premium_rate']])
    data = data.query("0 < score < 6").sort_values(by="score", ascending=False)
    # 记录分数表（供换仓门槛使用）
    g.last_scores = {str(_k): float(_v) for _k, _v in zip(data['index'], data['score'])}

    return data['index'].tolist()


# ============ 同集群去重（按 ETF 简称关键词聚类，同类型最多保留 N 只） ============
# 关键词按「越具体越靠前」排列，避免 "科创芯片" 被宽泛的 "科创" 抢走。
# 名称来源：内置静态表（已知 ETF），表外的标的自回退到 get_security_info。
# 注：已按用户要求删除「美股海外」簇（不再对纳指/标普/日经/德国/海外/QDII 去重）。
_ETF_NAME_HINT = {
    "513100.XSHG": "纳指ETF",              "513520.XSHG": "日经ETF",
    "513030.XSHG": "德国ETF",              "518880.XSHG": "黄金ETF",
    "159980.XSHE": "有色ETF",              "501018.XSHG": "南方原油",
    "511090.XSHG": "30年国债ETF",          "512890.XSHG": "红利低波ETF",
    "159915.XSHE": "创业板ETF",            "515220.XSHG": "煤炭ETF",
    "588710.XSHG": "科创半导体设备ETF",
    "159792.XSHE": "港股通互联网ETF",      "513080.XSHG": "法国ETF",
    "159985.XSHE": "豆粕ETF",              "512880.XSHG": "证券ETF",
    "588200.XSHG": "科创芯片ETF",          "515880.XSHG": "通信ETF",
    "159516.XSHE": "半导体设备ETF",        "513180.XSHG": "恒生科技ETF",
    "588080.XSHG": "科创50ETF",            "588170.XSHG": "科创半导体ETF",
    "159995.XSHE": "芯片ETF",              "563360.XSHG": "A500ETF",
    "512170.XSHG": "医疗ETF",              "510880.XSHG": "红利ETF",
    "159570.XSHE": "港股通创新药ETF",      "159819.XSHE": "人工智能ETF",
    "512480.XSHG": "半导体ETF",            "512400.XSHG": "有色金属ETF",
    "513090.XSHG": "香港证券ETF",          "159992.XSHE": "创新药ETF",
    "159326.XSHE": "电网设备ETF",          "159530.XSHE": "机器人ETF",
    "159206.XSHE": "卫星ETF",              "159509.XSHE": "纳指科技ETF",
    "159781.XSHE": "科创创业ETF",          "159928.XSHE": "消费ETF",
    "159201.XSHE": "自由现金流ETF",        "512070.XSHG": "证券保险ETF",
    "512690.XSHG": "酒ETF",                "159870.XSHE": "化工ETF",
    "513310.XSHG": "中韩半导体ETF",        "512800.XSHG": "银行ETF",
    "517520.XSHG": "黄金股ETF",            "159869.XSHE": "游戏ETF",
    "159611.XSHE": "电力ETF",              "513650.XSHG": "标普500ETF",
    "512710.XSHG": "军工龙头ETF",          "159865.XSHE": "养殖ETF",
    "516150.XSHG": "稀土ETF",              "515790.XSHG": "光伏ETF",
    "159796.XSHE": "电池ETF",              "159566.XSHE": "储能电池ETF",
    "515230.XSHG": "软件ETF",              "513530.XSHG": "港股通红利ETF",
    "159608.XSHE": "稀有金属ETF",          "560280.XSHG": "工程机械ETF",
    "516510.XSHG": "云计算ETF",            "560080.XSHG": "中药ETF",
    "515030.XSHG": "新能源车ETF",          "159667.XSHE": "工业母机ETF",
    "513950.XSHG": "恒生红利ETF",
}

# ⚠ 注：'互联网科技' 簇的关键词较宽（含"科技"），会把 恒生科技/纳指科技/通信/人工智能/
#    机器人/软件/云计算 都归为一类，同类型只留 2 只 -> 会剔掉其中大部分。
#    若希望保留跨市场/跨主题差异，把该簇拆细或提高 g.max_per_cluster 即可。
_CLUSTER_KEYWORDS = [
    ('芯片半导体', ['芯片', '半导体', '集成电路']),
    ('医药医疗',   ['医药', '医疗', '生物', '创新药', '中药', '疫苗']),
    ('新能源光伏', ['光伏', '锂电', '电池', '储能', '新能源']),
    ('互联网科技', ['互联网', '软件', '计算机', '通信', '电子', '人工智能',
                    '算力', '云计算', '科技', '信息', '大数据', '机器人']),
    ('军工国防',   ['军工', '国防', '航天', '航空']),
    ('证券金融',   ['证券', '银行', '金融', '保险', '地产']),
    ('周期资源',   ['有色', '稀土', '金属', '资源', '钢铁', '煤炭', '石油', '油气', '能源', '化工']),
    ('消费食品',   ['消费', '食品', '酒', '农业', '家电', '旅游', '养殖']),
    ('红利价值',   ['红利', '价值', '低波', '国企', '央企', '现金流']),
    ('债券',       ['债']),

    ('港股',       ['港股', '恒生']),
    ('科创',       ['科创']),
    ('宽基',       ['创业板', '中证', '沪深', 'A50', '深证', '上证']),
]

def _cluster_of(name):
    for cluster, kws in _CLUSTER_KEYWORDS:
        for kw in kws:
            if kw in name:
                return cluster
    return name or '__其他__'

def _dedup_by_cluster(pool, names, max_per_cluster):
    kept = []
    cnt = {}
    for c in pool:
        nm = names.get(c, '') or ''
        if not nm:
            # 取不到名称则各自独立成簇，保证绝不误删
            cl = '__无名_' + c
        else:
            cl = _cluster_of(nm)
        n = cnt.get(cl, 0)
        if n >= max_per_cluster:
            log.warn("去重剔除（[%s] 已保留 %d 只）: %s %s" % (cl, max_per_cluster, c, nm))
            continue
        cnt[cl] = n + 1
        kept.append(c)
    log.info("集群去重：%d -> %d 只（同类型上限 %d）" % (len(pool), len(kept), max_per_cluster))
    return kept


def _disp(code):
    """安全获取证券简称（取不到返回空串，避免打印时抛异常）"""
    try:
        _i = get_security_info(code)
        return _i.display_name if _i is not None else ''
    except Exception:
        return ''


# ============ 组合级回撤刹车（阶段2） ============
def _brake_action(dd):
    """
    纯函数：按回撤档位返回刹车动作（便于离线单测，不依赖聚宽环境）。
      dd <= -g.brake_l2  -> 'clear'   全清仓 + 冷却
      dd <= -g.brake_l1  -> 'reduce'  敞口降至 g.brake_l1_scale
      否则                -> 'hold'    不动
    """
    if dd <= -g.brake_l2:
        return 'clear'
    if dd <= -g.brake_l1:
        return 'reduce'
    return 'hold'


def _peak_update(nav):
    """更新净值峰值锚，返回当前回撤（负数）"""
    if g.peak_nav is None or nav > g.peak_nav:
        g.peak_nav = nav
    return nav / g.peak_nav - 1.0


def _index_trend_ok(context):
    """
    ★v8（M1）：恢复满仓的"外生趋势确认"。

    返回 True  = 沪深300 站在 MA(n) 之上（或开关关闭 / 取数失败一律放行）=> 允许恢复满仓。
    返回 False = 指数在均线之下 => 维持 1/3 敞口，暂不恢复。

    设计要点：
      * **判据外生**：只看市场指数（g.recover_index），不看组合自身净值，
        因此不会出现 v3(T1) 式的"降仓 -> 净值恢复慢 -> 摸不到线 -> 自锁"。
      * **容错放行**：任何取数/计算异常都返回 True —— 风控计算失败绝不能把组合锁死。
      * **无未来函数**：只用 attribute_history（默认不含当日），按 T-1 收盘与 T-1..T-n 均线判定。
    """
    if not bool(g.RISK.get('recover_gate', True)):
        return True
    try:
        n = int(getattr(g, 'recover_ma_n', 10))
        if n <= 1:
            return True
        df = attribute_history(g.recover_index, n + 1, '1d', ['close'])
        if df is None or len(df) < n:
            return True
        arr = df['close'].values
        px = float(arr[-1])
        ma = float(np.mean(arr[-n:]))
        if px <= 0 or ma <= 0 or math.isnan(px) or math.isnan(ma):
            return True
        return (px / ma - 1.0) > float(getattr(g, 'recover_ma_margin', 0.0))
    except Exception:
        return True


def _exposure(context):
    """
    计算当前应生效的总敞口，并在状态切换时打日志。
    返回 (敞口, 当前回撤)；若触发二级清仓则敞口为 None（调用方须立即清仓并 return）。
    """
    nav = context.portfolio.total_value
    dd = _peak_update(nav)
    act = _brake_action(dd)

    if act == 'clear':
        return None, dd
    if act == 'reduce':
        if g.brake_state != 'reduced':
            log.info('⚠ 组合回撤 %.2f%% ≤ -%.0f%%：敞口降至 %.0f%%'
                     % (dd * 100, g.brake_l1 * 100, g.brake_l1_scale * 100))
            g.reduce_days = 0        # ★v7（G2）：新一次降仓，计数归零
        g.brake_state = 'reduced'
        return g.brake_l1_scale, dd
    if g.brake_state == 'reduced':
        # ★v7（G2）：恢复线仍是同一条 -brake_l1（与基线完全一致，不做滞回、不做连续确认）。
        #            这里只加"降仓最短维持"这一层，默认 brake_min_hold = 1 -> 基线的
        #            "触发次日即可恢复"行为完全不变；设 2 才要求至少连续降仓 2 个交易日。
        g.reduce_days += 1
        if g.reduce_days < int(getattr(g, 'brake_min_hold', 1)):
            return g.brake_l1_scale, dd
        # ★v8（M1）：恢复端"外生趋势确认" —— 净值站回 -brake_l1 之上还不够，
        #            还必须 沪深300 站上 MA(n)。挡掉"刚恢复就再跌"的往返
        #            （24~26 实测 13 次恢复中 9 次 2 个交易日内又被打回降仓）。
        #            注意：触发线 / 清仓线 / 冷却 / 阈值一律未动，这里只卡"恢复"这一端。
        # ★v8（M1）安全阀：净值已回到"距峰值 recover_force_dd 以内"就直接恢复，不看指数。
        #   防的是"组合靠海外/黄金/红利创新高、而沪深300 长期在 MA10 下方"时被锁死 1/3。
        #   取 3% 足够深 => 24~26 的 13 次往返读数（-4.88%~-5.99%）仍全部被拦，不削弱 M1。
        #   g.recover_force_dd = -1 可关闭安全阀（退回纯指数闸）。
        _forced = dd > -float(getattr(g, 'recover_force_dd', 0.03))
        if (not _index_trend_ok(context)) and (not _forced):
            if g.reduce_days % 5 == 1:   # 限频打印，避免逐日刷屏
                log.info('回撤已修复至 %.2f%% 但 %s 未站上 MA%d：暂不恢复满仓，维持 %.0f%% 敞口'
                         % (dd * 100, g.recover_index, int(getattr(g, 'recover_ma_n', 10)),
                            g.brake_l1_scale * 100))
            return g.brake_l1_scale, dd
        _tag = '安全阀放行 dd>-%.0f%%' % (float(getattr(g, 'recover_force_dd', 0.03)) * 100)             if _forced else ('沪深300 站上 MA%d' % int(getattr(g, 'recover_ma_n', 10)))
        log.info('组合回撤修复至 %.2f%%（已连续降仓 %d 个交易日，%s）：敞口恢复 100%%'
                 % (dd * 100, g.reduce_days, _tag))
        g.last_restore_date = context.current_dt.date()   # ★v7（G2）：供 14:50 同日保护使用
    g.brake_state = 'normal'
    g.reduce_days = 0
    return 1.0, dd


def _sell_all(context, tag):
    for etf in _holds(context):
        order_target_value(etf, 0)
        print('卖出' + str(etf) + _disp(etf) + '（%s）' % tag)


def _enter_cooldown(context, nav, tag, dd):
    """触发二级刹车：清仓 + 进入冷却 + 重置峰值锚（避免回场即二次触发 -> 永久空仓）"""
    _sell_all(context, tag)
    g.cooldown_left = g.brake_cool
    g.peak_nav = nav            # ★ 关键：峰值锚重置到当前净值
    g.brake_state = 'cooldown'
    g.last_expo = 1.0
    g.reduce_days = 0           # ★v7（G2）：清仓后降仓计数归零
    log.info('⚠ %s 组合回撤 %.2f%% ≤ -%.0f%%：清仓，冷却 %d 个交易日'
             % (tag, dd * 100, g.brake_l2 * 100, g.brake_cool))


# ============ 目标组合构建（M1 换仓门槛 v2 + M2 Top-N 缓冲） ============
def _holds(context):
    """当前真实持仓（数量 > 0）。显式过滤掉已清仓的 0 仓位，避免误判。"""
    pos = context.portfolio.positions
    out = []
    for _c in pos:
        try:
            if pos[_c].amount > 0:
                out.append(_c)
        except Exception:
            pass
    return out


def _can_order(context, etf, target_value):
    """
    ★v7（G3）：下单前做"最小 100 股 / 价格有效"检查。

    基线的问题：511090（30 年国债，单价约 110 元）在敞口降到 1/3 时，
    目标金额只有约 9,600 元 -> 只能算得 87 股 < 100 股，
    聚宽直接报"订单委托失败"，**白占一个仓位**（24 年 08-09 / 08-12 各一次）。

    规则：目标增仓金额不足 100 股（或取不到有效价 / 停牌）就返回 False，跳过下单。
    """
    try:
        pos = None
        try:
            pos = context.portfolio.positions.get(etf)
        except Exception:
            pos = None

        px = None
        if pos is not None:
            _p = getattr(pos, 'price', None)
            if _p is not None and float(_p) > 0:
                px = float(_p)
        if px is None or px <= 0:
            df = attribute_history(etf, 1, '1d', ['close'])
            if df is None or len(df) == 0:
                return False
            px = float(df['close'].values[-1])
        if px is None or px <= 0 or math.isnan(px):
            return False

        cur = float(getattr(pos, 'amount', 0) or 0) * px if pos is not None else 0.0
        delta = float(target_value) - cur
        if delta > 0 and delta < px * 100:
            return False          # 加仓量不足 100 股 -> 放弃这一单（避免"委托失败"白占位）
        return True
    except Exception:
        return True               # 检查本身出任何问题一律放行，绝不因风控阻断交易


def _build_targets(ranked, scores, hold):
    """
    返回本次要持有的目标代码列表（长度 <= g.target_num）。

    M2 缓冲：持仓只要还在 ranked[:g.buffer_n] 内，就直接保住，不参与换仓。
    M1 门槛（v2）：掉出缓冲区的持仓 h，只有当"最前面的新候选 c 的分数 >= base×(1+gap)"
                  时才被替换，其中 base = max(h 的分数, 缓冲区内最弱持仓的分数)。
                  —— v1 只用 h 的分数当基准，而 h 已掉出前 5 名（分数天然很低甚至=0），
                     门槛恒成立、从不触发；改用"取大"后门槛才有约束力。
    被排名过滤掉的持仓（分数=0，如触发 3 日急跌过滤）视为可以换出；
    若此时没有候选可换，则该仓位直接空出（持币）。
    """
    tgt_num = g.target_num
    if not ranked:
        return []                       # 全池无合格标的 -> 清仓（与原版行为一致）

    use_buffer = bool(g.RISK.get('buffer', True))
    buf_n = max(tgt_num, int(g.buffer_n)) if use_buffer else tgt_num

    keep  = [e for e in ranked[:buf_n] if e in hold]                     # 缓冲区内持仓：先保住
    drop  = [e for e in hold if e not in keep]                           # 掉出缓冲区的持仓
    cands = [e for e in ranked if (e not in keep and e not in hold)]     # 真正的新候选

    moat_on = bool(g.RISK.get('moat', True))
    gap = float(g.switch_gap) if moat_on else 0.0
    # M1 门槛基准：缓冲区内最弱持仓的分数（v2 的核心）
    keep_min = min([float(scores.get(e, 0.0)) for e in keep], default=0.0)
    # ★v7（G1）两项修正，专治"死仓锁死"：
    #   基线 v2 用 base = max(hs, keep_min)：组合里只要有一只强票，最弱的持仓就永远换不掉。
    #   实测代价：全周期 317 次拦截，其中 24 年 09-12~09-20 连续 5 次把已走平到 0.000 分的
    #   德国ETF（513030）锁死，不让换 0.341 分的电池ETF（159796），晚了 6~7 个交易日才进主升。
    #     ① 死仓豁免（**默认开**）：持仓分 ≤ moat_dead（默认 0.05）-> 无条件换出，不看门槛
    #     ② 基准打折（**默认关**，frac=1.0 时与基线完全一致）：keep_ref = moat_keep_frac × keep_min
    keep_ref = keep_min * float(getattr(g, 'moat_keep_frac', 1.0))
    dead_th  = float(getattr(g, 'moat_dead', 0.05))

    final = list(keep)
    while len(final) < tgt_num:
        if cands:
            c = cands[0]
            if drop:
                h = drop[0]
                hs = float(scores.get(h, 0.0))
                cs = float(scores.get(c, 0.0))
                # ★ v7（G1）：取"被换出的"和"打折后的最弱保留"的较大者。
                # 例外1：is_dead（hs ≤ moat_dead，含 hs<=0 被排名过滤的情况）必须换出，
                #        不适用门槛（否则硬风控会被 M1 挡回去，且死仓会被永久锁死）。
                # 例外2：g.RISK['moat']=False 时整条门槛关闭（不设 base，直接换）。
                is_dead = hs <= dead_th
                base = 0.0 if not moat_on else (hs if is_dead else max(hs, keep_ref))
                if moat_on and (not is_dead) and cs < base * (1.0 + gap):
                    # 门槛不足：候选只是勉强挤进来，为这点优势换仓不划算，保留原持仓
                    log.info('门槛不足，保留 %s(%.3f) 不换 %s(%.3f) [基准%.3f]'
                             % (h, hs, c, cs, base))
                    final.append(drop.pop(0))
                    continue
                drop.pop(0)
            cands.pop(0)
            final.append(c)
        elif drop:
            # 候选已耗尽：仍有效（未被过滤掉）的持仓继续持有，被过滤的空出仓位（持币）
            h = drop.pop(0)
            if float(scores.get(h, 0.0)) > 0:
                final.append(h)
        else:
            break

    return final[:tgt_num]


# 交易：动量 Top-N 等权分仓 + M1/M2 + 阶段2 刹车
def trade(context):
    target_num = g.target_num

    # ---------- 0) 组合级回撤刹车（阶段2） ----------
    expo = 1.0
    if g.RISK.get('brake', True):
        nav = context.portfolio.total_value

        # 冷却期：只卖不买，逐日递减（run_daily 只在交易日触发 => 精确 7 个交易日）
        if g.cooldown_left > 0:
            g.cooldown_left -= 1
            _sell_all(context, '冷却期清仓')
            if g.cooldown_left == 0:
                g.peak_nav = context.portfolio.total_value   # 峰值锚重置，回场后从 dd=0 起算
                g.brake_state = 'normal'
                g.last_expo = 1.0
                log.info('冷却结束（%d 个交易日）：峰值锚已重置，下一交易日起恢复正常建仓' % g.brake_cool)
            return

        expo, dd = _exposure(context)
        if expo is None:
            _enter_cooldown(context, nav, '日检', dd)
            return

    # ---------- 1) 取动量排名（已过滤 + 按分数降序）与分数表 ----------
    if g.auto_day:
        ranked = get_rank2(context, g.etf_pool)
    else:
        ranked = get_rank(context, g.etf_pool)
    scores = getattr(g, 'last_scores', None) or {}

    hold = _holds(context)

    # ---------- 2) 构建目标组合（M1 换仓门槛 + M2 Top-N 缓冲） ----------
    target_list = _build_targets(ranked, scores, hold)

    # 想看每天的目标组合与分数，取消下面这行注释即可
    # log.info('目标组合: %s' % [(e, round(scores.get(e, 0.0), 3)) for e in target_list])

    # ---------- 3) 卖出：不在目标组合内则清仓 ----------
    for etf in hold:
        if etf not in target_list:
            order_target_value(etf, 0)
            print('卖出' + str(etf) + _disp(etf))

    # ---------- 4) 买入：按"等权 × 敞口"建仓 ----------
    #     常态（expo 未变）：已持有的不动，只补新标的，避免每日微调
    #     敞口档位变化（1.0 <-> 1/3）：对全部目标做一次再平衡，否则敞口根本降不下来
    tv = context.portfolio.total_value
    held_now = _holds(context)
    per = tv * expo / target_num
    need_rebal = abs(expo - getattr(g, 'last_expo', 1.0)) > 1e-9
    for etf in target_list:
        if (not need_rebal) and (etf in held_now):
            continue
        # ★v7（G3）：最小 100 股 / 价格检查，避免"委托失败"白占仓位
        if not _can_order(context, etf, per):
            print('跳过下单%s%s（目标 %.0f 元不足 100 股或价格无效）' % (etf, _disp(etf), per))
            continue
        order_target_value(etf, per)
        print('%s%s%s（目标权重 %.1f%%）'
              % ('调仓' if etf in held_now else '买入', etf, _disp(etf), 100.0 * expo / target_num))
    g.last_expo = expo


# ============ 14:50 补检：只做刹车，不建仓 ============
def brake_monitor(context):
    """
    9:50 单点采样会漏掉"早盘尚可、午后跳水"的行情。
    本函数只执行刹车动作（降敞口 / 清仓），绝不建仓 —— 避免早盘冲高时被动买入。
    """
    if (not g.RISK.get('brake', True)) or (not g.brake_intraday):
        return
    if g.cooldown_left > 0:
        return

    nav = context.portfolio.total_value
    dd = _peak_update(nav)
    act = _brake_action(dd)

    if act == 'clear':
        _enter_cooldown(context, nav, '14:50', dd)
    elif act == 'reduce' and g.brake_state != 'reduced':
        # ★v7（G2）：同日二次切换保护 —— 9:50 刚把敞口从 1/3 恢复到 100%，
        #            14:50 若因同一波日内噪声又降回去，等于白付一次往返摩擦
        #            （24 年 6 次抖动里 4 次是"恢复当日又降仓"）。
        #            只挡 'reduce'；上面的 'clear'（-9% 清仓）仍优先执行，不放弃尾部保护。
        if bool(getattr(g, 'brake_same_day_guard', True)) and \
                getattr(g, 'last_restore_date', None) == context.current_dt.date():
            log.info('14:50 同日恢复保护：今日 9:50 已恢复满仓，本次不再降敞口')
            return
        g.reduce_days = 0        # ★v7（G2）：本轮降仓计数归零
        per = nav * g.brake_l1_scale / g.target_num
        for etf in _holds(context):
            try:
                if context.portfolio.positions[etf].value > per * 1.01:
                    order_target_value(etf, per)
                    print('卖出' + str(etf) + _disp(etf) + '（14:50 回撤降敞口）')
            except Exception:
                pass
        g.brake_state = 'reduced'
        g.last_expo = g.brake_l1_scale
        log.info('⚠ 14:50 组合回撤 %.2f%% ≤ -%.0f%%：敞口降至 %.0f%%'
                 % (dd * 100, g.brake_l1 * 100, g.brake_l1_scale * 100))