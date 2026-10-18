# Clone from JoinQuant
# postId: 02c9133be60d8641e60d5eee07f7e44e
# backtestId: 4172c57e94a8fe41f171eb4824d6d6fc
# title: 固定资产投资增速也不错

# ============================================================
# 简版周度轮动：只买“固定资产投资景气排名前 g.top_n”行业中【估值最低的 g.pick_per_industry 只】个股
#   规则：每周一调仓；用 MAC_INDUSTRY_FIXED_INVEST 把固投当月同比映射到申万一级行业，
#         取景气排名前 top_n 的行业(可选先用阈值过滤)；每个入选行业先取该申万一级成分股，
#         再过硬阈值、做“增收增利”过滤(营收/净利同比均>g.growth_min%)，
#         买入其中估值最低的 g.pick_per_industry 只；等权持有，每周更新一次。
#   数据：macro.MAC_INDUSTRY_FIXED_INVEST（分行业固定资产投资·长表）
#         item_name 国标行业中文名；investment_perc 累计增长%；investment_value 累计值亿元
#   适用：聚宽(JoinQuant)回测环境
# ============================================================
import datetime
import pandas as pd
import numpy as np
from jqdata import *          # 必须显式导入，否则 get_valuation 等函数不可用(NameError)

# —— 申万一级(SW2021) -> 该行业对应的固投【精确 item_name(国标行业中文名)】映射 ——
#    【修复】改用“精确等值匹配”(去空白后)，避免子串/单字误命中(旧版每个行业都命中全部行业、取到同一均值)。
#    刻意排除汇总项(制造业/采矿业/农、林、牧、渔业/电力、热力、燃气及水…等)，避免重复计数。名称须与表中 item_name 一致。
SW_L1_FI_KEYWORDS = {
    '801010': ['农业', '林业', '畜牧业', '渔业'],                                              # 农林牧渔
    '801030': ['化学原料和化学制品制造业', '化学纤维制造业', '橡胶和塑料制品业'],            # 基础化工
    '801040': ['黑色金属冶炼和压延加工业'],                                                   # 钢铁
    '801050': ['有色金属冶炼和压延加工业', '有色金属矿采选业'],                               # 有色金属
    '801080': ['计算机、通信和其他电子设备制造业'],                                           # 电子
    '801110': ['电气机械和器材制造业'],                                                       # 家用电器
    '801120': ['农副食品加工业', '食品制造业', '酒、饮料和精制茶制造业'],                     # 食品饮料
    '801130': ['纺织业', '纺织服装、服饰业', '皮革、毛皮、羽毛及其制品和制鞋业'],            # 纺织服饰
    '801140': ['造纸及纸制品业', '家具制造业', '印刷和记录媒介复制业', '文教、工美、体育和娱乐用品制造业'],  # 轻工制造
    '801150': ['医药制造业'],                                                                 # 医药生物
    '801160': ['电力、热力生产和供应业', '燃气生产和供应业', '水的生产和供应业'],            # 公用事业
    '801170': ['铁路运输业', '道路运输业', '水上运输业', '航空运输业', '管道运输业', '装卸搬运和仓储业'],  # 交通运输
    '801180': ['房地产业'],                                                                   # 房地产
    '801200': ['批发和零售业'],                                                               # 商贸零售
    '801710': ['非金属矿物制品业'],                                                           # 建筑材料
    '801720': ['建筑业'],                                                                     # 建筑装饰
    '801730': ['电气机械和器材制造业'],                                                       # 电力设备(与家电共用国标“电气机械”，信号相同)
    '801740': ['铁路、船舶、航空航天和其他运输设备制造业'],                                   # 国防军工
    '801880': ['汽车制造业'],                                                                 # 汽车
    '801890': ['通用设备制造业', '专用设备制造业', '仪器仪表制造业'],                         # 机械设备
    '801950': ['煤炭开采和洗选业'],                                                           # 煤炭
    '801960': ['石油和天然气开采业', '石油加工、炼焦和核燃料加工业'],                         # 石油石化
}
SW_L1_NAME = {
    '801010': '农林牧渔', '801030': '基础化工', '801040': '钢铁',     '801050': '有色金属',
    '801080': '电子',     '801110': '家用电器', '801120': '食品饮料', '801130': '纺织服饰',
    '801140': '轻工制造', '801150': '医药生物', '801160': '公用事业', '801170': '交通运输',
    '801180': '房地产', '801200': '商贸零售', '801710': '建筑材料', '801720': '建筑装饰',
    '801730': '电力设备', '801740': '国防军工', '801880': '汽车',     '801890': '机械设备',
    '801950': '煤炭',     '801960': '石油石化',
}

# —— 申万一级 -> 对应的申万三级行业“名称关键词”；运行时用 get_industries('sw_l3') 动态解析 ——
#    未命中时回退到整个申万一级成分股。
SW_L1_L3_KEYWORDS = {
    '801010': ['种植', '养殖', '畜禽', '饲料', '动物保健', '农产品', '渔业', '林业', '种业'],
    '801030': ['化学原料', '化工', '农药', '化肥', '涂料', '油墨', '民爆', '氟化', '聚氨酯',
               '纤维', '涤纶', '粘胶', '氨纶', '锦纶', '橡胶', '塑料', '轮胎', '添加剂'],
    '801040': ['普钢', '特钢', '钢', '冶钢原料', '铁'],
    '801050': ['铜', '铝', '铅锌', '黄金', '稀土', '小金属', '能源金属', '工业金属', '贵金属', '有色'],
    '801080': ['半导体', '芯片', '集成电路', '分立器件', '印制电路', '被动元件', '面板',
               'LED', '光学', '消费电子', '电子化学品', '光电子', '元件', '电子'],
    '801110': ['白色家电', '空调', '冰箱', '洗衣机', '黑色家电', '彩电', '小家电', '厨房',
               '清洁电器', '个护', '厨卫', '照明', '家电'],
    '801120': ['白酒', '啤酒', '酒', '饮料', '乳品', '肉制品', '调味', '发酵', '烘焙',
               '预加工', '保健品', '零食', '熟食', '食品'],
    '801130': ['纺织', '棉纺', '印染', '辅料', '麦帽', '家纺', '服装', '饰品', '珠宝', '钟表'],
    '801140': ['纸', '印刷', '包装', '家具', '家居', '瓷砖', '地板', '文娱', '娱乐用品', '办公'],
    '801150': ['化学制剂', '原料药', '中药', '生物制品', '血液制品', '疫苗', '医疗器械',
               '医疗设备', '医疗耗材', '体外诊断', '医药商业', '医疗服务', '药店', '医药'],
    '801160': ['火电', '水电', '热力', '电能', '发电', '电力', '燃气', '水务'],
    '801170': ['铁路', '公路', '航运', '港口', '航空', '机场', '物流', '快递', '高速'],
    '801180': ['房地产', '物业', '开发', '园区', '商业地产'],
    '801200': ['百货', '超市', '专业连锁', '商业', '贸易', '电商', '零售', '珠宝', '免税', '旅游零售'],
    '801710': ['水泥', '玻璃', '玻纤', '耐火', '管材', '建材', '防水', '瓷砖', '石膏'],
    '801720': ['基建', '房建', '装修', '钢结构', '园林', '设计', '国际工程', '建筑'],
    '801730': ['电机', '电气', '配电', '电网', '风电', '光伏', '电池', '锂电', '蓄电',
               '燃料电池', '电源设备', '火电设备'],
    '801740': ['航天', '航空', '兵装', '航海', '军工', '船舶'],
    '801880': ['乘用车', '商用车', '载货', '载客', '汽车零部件', '汽车服务', '摩托车', '轮胎', '汽车'],
    '801890': ['机床', '磨具', '制冷', '通用设备', '工程机械', '农用机械', '重型设备', '楼宇',
               '专用设备', '机器人', '工控', '激光', '自动化', '仪器仪表'],
    '801950': ['煤', '焦炭', '煤炭开采'],
    '801960': ['油气开采', '炼油', '油品', '石油', '油服', '油气', '炼化'],
}

def _fi_publish_date(ym):
    """固投官方【发布日历(硬编码)】：统计月 ym('YYYY-MM') 的累计数据实际公布日期。
    统计局固投规则：次月中旬发布累计值；1-2月合并于当年3月发布；12月(全年)于次年1月发布。
    默认公布日 g.fi_publish_day=18(取月中偏后，确保当日数据确已可得，避免偷看未来)。"""
    y = int(str(ym)[:4]); m = int(str(ym)[5:7])
    pub_day = int(getattr(g, 'fi_publish_day', 18))
    if m <= 2:                                   # 1-2月合并累计 -> 当年3月发布
        return datetime.date(y, 3, pub_day)
    ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)   # 其余月次月发布；12月->次年1月
    return datetime.date(ny, nm, pub_day)

def _fi_published(ym, asof):
    """该统计月是否在 asof(调仓日, date) 当日或之前已按发布日历正式公布。"""
    try:
        return _fi_publish_date(ym) <= asof
    except Exception:
        return False

def _get_fixed_invest_map(date):
    """返回 {item_name(中文行业名): 固投同比%}。
    固投官方只发累计值(investment_value)与累计同比(investment_perc)，无直接单月数。
    默认 g.fi_use_single_month=True：用累计值+累计同比还原【当月同比】(可比口径)：
        当月同比 = (A_m - A_{m-1}) / (A_m/(1+g_m) - A_{m-1}/(1+g_{m-1})) - 1
      其中 A=累计值、g=累计同比；分母为“由官方累计同比反推的去年可比当月基数”，
      避免直接对原始累计值跨年差分因“挤水分/口径调整”而失真。
      当年首个统计月(1-2月累计)无上月可差分，退化为累计同比。设 False 则直接用官方累计同比。"""
    try:
        from jqdata import macro
        tbl = macro.MAC_INDUSTRY_FIXED_INVEST
    except Exception:
        return {}
    try:
        dt = pd.to_datetime(date).date()
        ub = dt.strftime('%Y-%m')                       # 只取不晚于当前调仓月的统计月
        # 拉取截止月及往前若干月的【累计值 + 累计同比】(同时含 item_name)
        df = macro.run_query(query(tbl.stat_month, tbl.item_name, tbl.investment_value, tbl.investment_perc)
                             .filter(tbl.stat_month <= ub)
                             .order_by(tbl.stat_month.desc()).limit(60000))
        if df is None or len(df) == 0:
            return {}
        df = df.copy()
        df['stat_month'] = df['stat_month'].astype(str)
        A = df.pivot_table(index='item_name', columns='stat_month', values='investment_value', aggfunc='last')  # 累计值
        G = df.pivot_table(index='item_name', columns='stat_month', values='investment_perc', aggfunc='last')   # 累计同比
        # 【硬编码发布日历】只保留“截至调仓日已正式公布”的统计月(防偷未来)，替代手动滞后天数
        months = sorted(m for m in A.columns if _fi_published(m, dt))
        if not months:
            log.warning("固定资产投资：截至%s无已按发布日历公布的统计月" % date)
            return {}
        use_single = getattr(g, 'fi_use_single_month', True)

        def prev_same_year(mm):                                  # 同年且 < mm 的最近一个统计月
            yy = int(mm[:4]); best = None
            for c in months:
                if int(c[:4]) == yy and c < mm:
                    best = c
            return best

        for m in reversed(months):                              # 由近及远逐月回退
            pm = prev_same_year(m)
            out = {}
            for item in A.index:
                try:
                    a_m = pd.to_numeric(A.at[item, m], errors='coerce')
                    g_m = pd.to_numeric(G.at[item, m], errors='coerce') if item in G.index else np.nan
                    if (not use_single) or pm is None:          # 累计同比(或当年首月：当月=累计)
                        if pd.notna(g_m):
                            out[str(item).strip()] = float(g_m)
                        continue
                    a_p = pd.to_numeric(A.at[item, pm], errors='coerce')
                    g_p = pd.to_numeric(G.at[item, pm], errors='coerce') if item in G.index else np.nan
                    if pd.notna(a_m) and pd.notna(a_p) and pd.notna(g_m) and pd.notna(g_p):
                        base = a_m/(1.0+g_m/100.0) - a_p/(1.0+g_p/100.0)   # 去年当月(可比基数)
                        cur  = a_m - a_p                                     # 本年当月增量
                        if base > 0:
                            out[str(item).strip()] = (cur/base - 1.0) * 100.0
                        elif pd.notna(g_m):
                            out[str(item).strip()] = float(g_m)             # 基数异常回退累计同比
                    elif pd.notna(g_m):
                        out[str(item).strip()] = float(g_m)                 # 数据不足回退累计同比
                except Exception:
                    continue
            if out:
                tag = "当月同比(累计值还原·可比口径)" if use_single else "累计同比"
                log.info("【固定资产投资】%s：采用统计月%s(发布日%s,%s)，%d个行业" % (date, m, _fi_publish_date(m).strftime('%Y-%m-%d'), tag, len(out)))
                if getattr(g, 'enable_detail_log', True):
                    log.info("【固投明细·%s】%s" % (tag, "，".join("%s=%.1f%%" % (k, v) for k, v in out.items())))
                return out
        log.warning("固定资产投资：%s 之前已发布月份均无有效数据" % ub)
        return {}
    except Exception as e:
        log.warning("固定资产投资取数失败：%s" % str(e)[:80])
        return {}

def _norm_item(s):
    """行业名归一化：去掉半/全角空格，便于精确等值匹配。"""
    return str(s).replace(' ', '').replace('　', '')

def _fi_perc_for_sw(sw_code, fi_map):
    """申万一级 -> 对应国标行业的固投累计增长均值（精确等值匹配，去空白）；无命中返回 None。"""
    names = SW_L1_FI_KEYWORDS.get(sw_code)
    if not names or not fi_map:
        return None
    nmap = {_norm_item(k): v for k, v in fi_map.items()}         # 归一化后的 {国标行业: 固投增长}
    matched = {}
    for n in names:
        key = _norm_item(n)
        if key in nmap:                                         # 精确等值命中(非子串)
            matched[n] = nmap[key]
    if getattr(g, 'enable_detail_log', True):                   # 打印每行业命中的国标行业，核对映射是否正确
        detail = "，".join("%s%.1f%%" % (nm, v) for nm, v in matched.items()) if matched else "(无命中，请核对行业名)"
        log.info("  [映射]%s <- %s" % (SW_L1_NAME.get(sw_code, sw_code), detail))
    if not matched:
        return None
    return float(np.mean(list(matched.values())))

def get_qualified_industries(date):
    """返回 {sw_code: perc}：先按阈值过滤(g.use_threshold)，再取固投累计增长排名前 g.top_n 的申万一级行业。"""
    fmap = _get_fixed_invest_map(date)
    quals = {}
    if not fmap:
        log.warning("固定资产投资数据不可用，本期无达标行业")
        return quals
    scored = {}
    for sw in SW_L1_FI_KEYWORDS:
        yv = _fi_perc_for_sw(sw, fmap)
        if yv is None:
            continue
        if getattr(g, 'use_threshold', True) and yv < g.fi_threshold:      # 排名前先用阈值过滤(可关)
            continue
        scored[sw] = yv
    top_n = int(getattr(g, 'top_n', 3))                                    # 只取固投增长排名前 top_n 的行业
    for sw, yv in sorted(scored.items(), key=lambda x: -x[1])[:top_n]:
        quals[sw] = yv
    if quals:
        desc = "，".join("%s%.1f%%" % (SW_L1_NAME.get(k, k), v) for k, v in sorted(quals.items(), key=lambda x: -x[1]))
        log.info("【达标行业】%s：固投景气排名前%d取%d个：%s" % (date, top_n, len(quals), desc))
    else:
        log.info("【达标行业】%s：无行业入选(阈值%.1f%%/前%d)，本月空仓" % (date, g.fi_threshold, top_n))
    return quals

def _sw_l3_pool(sw_code, date):
    """【修复】直接取该申万一级行业成分股。
    get_industry_stocks 原生支持申万一级代码(如 801120)，无需再用名称关键词匹配三级；
    旧版名称匹配会误命中全部三级行业(导致每个行业都拿到全市场、选出同一只股)。"""
    try:
        stocks = get_industry_stocks(sw_code, date)
    except Exception as e:
        log.warning("取行业%s成分失败：%s" % (SW_L1_NAME.get(sw_code, sw_code), str(e)[:40]))
        return []
    if getattr(g, 'enable_trade_log', True):
        log.info("  行业%s 申万一级成分股%d只" % (SW_L1_NAME.get(sw_code, sw_code), len(stocks)))
    return stocks

def _clean_industry_stocks(sw_code, date):
    """取该行业“申万三级收窄”后的成分股，剔除 科创板/北交所/新三板/B股、次新股(<90天)、ST。"""
    stocks = _sw_l3_pool(sw_code, date)
    if not stocks:
        return []
    dt = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    out = []
    for s in stocks:
        if s.startswith(('68', '4', '8', '9')):          # 排除科创板/北交所/新三板/B股
            continue
        try:
            info = get_security_info(s)
            if info is None or info.start_date > (dt - datetime.timedelta(days=90)):
                continue
        except Exception:
            continue
        out.append(s)
    if not out:
        return []
    try:
        st = get_extras('is_st', out, count=1, end_date=date).fillna(False)
        out = [s for s in out if not st[s].iloc[0]]
    except Exception:
        pass
    return out

# —— 硬阈值：剔除“估值过低估/过高估 + 财务异常”的不合理标的（财务常识；不含任何市值门槛）——
HARD_FILTER = {
    'require_pos_np_ttm':  True,    # 归母净利润 TTM > 0
    'require_pos_op_q':    True,    # 单季营业利润 > 0
    'require_pos_rev_ttm': True,    # 营业收入 TTM > 0
    'require_pos_equity':  True,    # 归母净资产 > 0
    'require_pos_cfo_ttm': False,   # 经营活动现金流 TTM > 0（默认关闭）
    'pb_min':       0.3,     'pb_max':       20.0,
    'pe_ttm_min':   3.0,     'pe_ttm_max':   150.0,
    'gross_margin_min': 0.0, 'gross_margin_max': 1.0,
    'roe_ttm_min':     -0.5, 'roe_ttm_max':      1.0,
}

def _cum_to_single(cum_values, statDates):
    """将累计值还原为单季值（同一年内作差，跨年重置）。"""
    out = []; prev_year = None; prev_val = 0.0
    for sd, v in zip(statDates, cum_values):
        try: year = int(str(sd)[:4])
        except Exception: out.append(np.nan); continue
        if year != prev_year:
            out.append(float(v) if pd.notna(v) else np.nan)
            prev_val = float(v) if pd.notna(v) else 0.0
        else:
            cur = float(v) if pd.notna(v) else np.nan
            out.append(cur - prev_val if pd.notna(cur) else np.nan)
            prev_val = cur if pd.notna(cur) else prev_val
        prev_year = year
    return pd.Series(out)

def _load_panel(stocks, date, field_objs, n=5, chunk=200):
    """按季拉取历史财务（watch_date 保证点位可见、防偷未来），返回 {code: 按statDate升序的DataFrame}。"""
    out = {}
    for i in range(0, len(stocks), chunk):
        sub = stocks[i:i+chunk]
        try:
            df = get_history_fundamentals(sub, fields=field_objs, watch_date=date, count=n, interval='1q')
            if df is None or not len(df): continue
            sc = 'statDate' if 'statDate' in df.columns else 'day'
            for code, gg in df.groupby('code'):
                out[code] = gg.sort_values(sc).reset_index(drop=True)
        except Exception as e:
            log.warn('get_history_fundamentals fail: {}'.format(e))
    return out

def _get_val(stocks, date):
    """取总市值(元)与 PB；返回 (mv_series, pb_series)。"""
    rows = []
    for i in range(0, len(stocks), 2000):
        b = stocks[i:i+2000]
        try:
            gv = get_valuation(b, end_date=date, count=1, fields=['market_cap', 'pb_ratio'])
            if gv is not None and len(gv): rows.append(gv)
        except Exception as e:
            log.warn('valuation fail: {}'.format(e))
    if not rows:
        return pd.Series(np.nan, index=stocks), pd.Series(np.nan, index=stocks)
    gv = pd.concat(rows, ignore_index=True).sort_values('day').drop_duplicates('code', keep='last').set_index('code')
    mv = pd.to_numeric(gv['market_cap'].reindex(stocks), errors='coerce') * 1e8
    pb = pd.to_numeric(gv['pb_ratio'].reindex(stocks), errors='coerce')
    return mv, pb

def apply_hard_filters(stock_list, date):
    """硬阈值筛选：剔除估值过于低估/高估及财务异常的个股；不含任何市值门槛。"""
    if not stock_list:
        return []
    stocks = list(stock_list)
    inc = _load_panel(stocks, date,
        [income.operating_profit, income.operating_revenue,
         income.operating_cost, income.np_parent_company_owners], n=5)
    bal = _load_panel(stocks, date, [balance.equities_parent_company_owners], n=1)
    mv, pb = _get_val(stocks, date)

    keep = []
    for code in stocks:
        try:
            di = inc.get(code)
            if di is None or len(di) < 1:
                continue
            sd = di['statDate'].values
            op_s = _cum_to_single(di['operating_profit'].values, sd)
            rev_s = _cum_to_single(di['operating_revenue'].values, sd)
            cost_s = _cum_to_single(di['operating_cost'].values, sd)
            npp_s = _cum_to_single(di['np_parent_company_owners'].values, sd)

            op_q = op_s.iloc[-1] if len(op_s) >= 1 else np.nan
            npp_ttm = npp_s.iloc[-4:].sum() if (len(npp_s) >= 4 and pd.notna(npp_s.iloc[-4:]).all()) else np.nan
            rev_ttm = rev_s.iloc[-4:].sum() if (len(rev_s) >= 4 and pd.notna(rev_s.iloc[-4:]).all()) else np.nan
            cost_ttm = cost_s.iloc[-4:].sum() if (len(cost_s) >= 4 and pd.notna(cost_s.iloc[-4:]).all()) else np.nan

            equity = np.nan
            db = bal.get(code)
            if db is not None and len(db) >= 1:
                eq = pd.to_numeric(db['equities_parent_company_owners'], errors='coerce').values
                if len(eq) >= 1:
                    equity = eq[-1]

            pbi = pb.get(code, np.nan)
            mvi = mv.get(code, np.nan)

            if HARD_FILTER['require_pos_np_ttm'] and not (pd.notna(npp_ttm) and npp_ttm > 0):
                continue
            if HARD_FILTER['require_pos_op_q'] and not (pd.notna(op_q) and op_q > 0):
                continue
            if HARD_FILTER['require_pos_rev_ttm'] and not (pd.notna(rev_ttm) and rev_ttm > 0):
                continue
            if HARD_FILTER['require_pos_equity'] and not (pd.notna(equity) and equity > 0):
                continue

            if not (pd.notna(pbi) and HARD_FILTER['pb_min'] <= pbi <= HARD_FILTER['pb_max']):
                continue
            pe_ttm = (mvi / npp_ttm) if (pd.notna(mvi) and pd.notna(npp_ttm) and npp_ttm > 0) else np.nan
            if pd.notna(pe_ttm) and not (HARD_FILTER['pe_ttm_min'] <= pe_ttm <= HARD_FILTER['pe_ttm_max']):
                continue

            gm = ((rev_ttm - cost_ttm) / rev_ttm) if (pd.notna(rev_ttm) and pd.notna(cost_ttm) and rev_ttm > 0) else np.nan
            if pd.notna(gm) and not (HARD_FILTER['gross_margin_min'] <= gm <= HARD_FILTER['gross_margin_max']):
                continue
            roe_ttm = (npp_ttm / equity) if (pd.notna(npp_ttm) and pd.notna(equity) and equity > 0) else np.nan
            if pd.notna(roe_ttm) and not (HARD_FILTER['roe_ttm_min'] <= roe_ttm <= HARD_FILTER['roe_ttm_max']):
                continue

            keep.append(code)
        except Exception:
            continue
    if getattr(g, 'enable_trade_log', True):
        log.info("【硬阈值筛选】%s：%d -> %d 只（剔除估值/财务异常）" % (date, len(stocks), len(keep)))
    return keep

def pick_cheapest_in_industry(sw_code, date):
    """行业内：先过硬阈值(剔除不合理标的) -> 再“增收增利”过滤 -> 取估值最低的 g.pick_per_industry 只(返回列表)。"""
    stocks = _clean_industry_stocks(sw_code, date)
    if not stocks:
        return []
    if getattr(g, 'use_hard_filter', True):               # 硬阈值：剔除估值过低/过高 + 财务异常
        stocks = apply_hard_filters(stocks, date)
        if not stocks:
            return []
    metric_col = {'pb': 'pb_ratio', 'pe_ttm': 'pe_ratio', 'ps_ttm': 'ps_ratio'}.get(g.value_metric, 'pb_ratio')
    try:
        q = query(valuation.code,
                  valuation.pb_ratio, valuation.pe_ratio, valuation.ps_ratio,
                  indicator.inc_revenue_year_on_year,        # 营业收入同比增长率(%)
                  indicator.inc_net_profit_year_on_year      # 净利润同比增长率(%)
                 ).filter(valuation.code.in_(stocks))
        df = get_fundamentals(q, date=date)                 # date= 保证点位数据、防偷未来
    except Exception as e:
        log.warning("行业%s基本面取数失败：%s" % (sw_code, str(e)[:40]))
        return []
    if df is None or df.empty:
        return []
    df = df.set_index('code')
    # —— 增收增利过滤：营收同比 且 净利同比 均 > 阈值 ——
    if getattr(g, 'require_growth', True):
        gmin = float(g.growth_min)
        rev = pd.to_numeric(df['inc_revenue_year_on_year'], errors='coerce')
        npr = pd.to_numeric(df['inc_net_profit_year_on_year'], errors='coerce')
        df = df[(rev > gmin) & (npr > gmin)]
        if df.empty:
            return []
    # —— 估值最低的前 k 只 ——
    v = pd.to_numeric(df[metric_col], errors='coerce')
    v = v[v > 0]                                          # 估值须为正(剔除亏损/异常)
    if g.require_pos_profit:
        pe = pd.to_numeric(df['pe_ratio'].reindex(v.index), errors='coerce')
        v = v[pe > 0]                                     # 价值陷阱防护：要求正盈利
    v = v.dropna()
    if v.empty:
        return []
    k = int(getattr(g, 'pick_per_industry', 3))
    return list(v.sort_values().index[:k])               # 估值最低的前 k 只 = 最便宜

def select_targets(context):
    date = context.previous_date.strftime("%Y-%m-%d")
    quals = get_qualified_industries(date)
    targets = []
    for sw in sorted(quals, key=lambda k: -quals[k]):     # 固投增长越高的行业优先
        picks = pick_cheapest_in_industry(sw, date)       # 该行业估值最低的 g.pick_per_industry 只
        if picks:
            new = [p for p in picks if p not in targets]  # 去重：同一只股票只买一次
            targets.extend(new)
            log.info("  行业%s(固投%.1f%%) 选出估值最低%d只：%s" % (SW_L1_NAME.get(sw, sw), quals[sw], len(new), new))
        else:
            log.info("  行业%s(固投%.1f%%) 无有效标的，跳过" % (SW_L1_NAME.get(sw, sw), quals[sw]))
    g.target_list = targets
    log.info("【选股结果】%s：入选行业%d个，实际选出%d只：%s" % (date, len(quals), len(targets), targets))
    return targets

def _buyable(stock):
    cd = get_current_data()
    if cd[stock].paused:
        return False
    if cd[stock].last_price >= cd[stock].high_limit:      # 涨停不追
        return False
    return True

def weekly_rebalance(context):
    targets = select_targets(context)
    hold = list(context.portfolio.positions.keys())
    # 1) 卖出不在目标里的
    for s in hold:
        if s not in targets:
            order_target_value(s, 0)
    if not targets:
        log.info("本周无达标行业/标的，已清仓")
        return
    # 2) 等权买入目标
    per = (context.portfolio.total_value * 0.99) / len(targets)
    bought = 0
    for s in targets:
        if s in hold:
            continue
        if not _buyable(s):
            log.info("  %s 停牌/涨停，跳过买入" % s)
            continue
        cd = get_current_data()[s]
        if per < cd.last_price * 100:                 # 单只额度不足1手，跳过(避免下单失败)
            log.info("  %s 额度%.0f元不足1手(约需%.0f元)，跳过" % (s, per, cd.last_price * 100))
            continue
        order_target_value(s, per)
        bought += 1
    log.info("【调仓完成】目标%d只(前%d行业×每行业%d只)，实际买入%d只，每只约%.0f元" % (len(targets), g.top_n, g.pick_per_industry, bought, per))

def initialize(context):
    set_benchmark('000985.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        close_today_commission=0, min_commission=5), type='stock')
    log.set_level('order', 'error')

    g.top_n              = 2       # 只买固投增长景气排名前 top_n 的行业(当前=前2名)
    g.pick_per_industry  = 3       # 每个入选行业买入估值最低的股票只数(当前=3只)
    g.use_threshold      = True    # True=先用阈值过滤再取排名前top_n；False=纯排名不设下限
    g.fi_threshold       = 5.0     # 固定资产投资同比阈值(%)：use_threshold=True 时的下限
    g.fi_use_single_month = True   # True=用累计值+累计同比还原“当月同比”(可比口径,最新月度景气)；False=直接用官方累计同比
    g.value_metric       = 'pb'    # 估值口径：'pb'市净率 / 'pe_ttm'市盈率TTM / 'ps_ttm'市销率
    g.require_pos_profit = True    # 价值陷阱防护：要求正盈利(pe>0)
    g.require_growth     = True    # 个股需“增收增利”：营收同比 & 净利同比 均 > g.growth_min
    g.growth_min         = 10.0    # 增收增利阈值(%)：营收、净利同比都要 > 该值(可下调到0)
    g.use_hard_filter    = True    # 硬阈值：剔除估值过低/过高、财务异常等不合理标的(见 HARD_FILTER)
    g.enable_trade_log   = True    # 过程日志开关
    g.enable_detail_log  = True    # 明细诊断日志：打印各行业固投增长 + 每行业映射命中(核对数据/映射用)
    g.fi_publish_day     = 18      # 固投【硬编码发布日历】：统计月次月的第几日视为已公布(次月中旬发布,1-2月并入3月,12月并入次年1月;防偷未来)
    g.target_list = []

    run_weekly(weekly_rebalance, 1, '9:30')     # 每周一开盘后调仓(weekday=1)
    log.info("【初始化完成】分行业固定资产投资景气排名前%d行业·每行业估值最低%d只 周度轮动" % (g.top_n, g.pick_per_industry))