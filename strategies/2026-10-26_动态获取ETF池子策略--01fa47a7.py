# Clone from JoinQuant
# postId: 01fa47a7fb2233e8c602a78618e34545
# backtestId: 24dc612af75e4acdb9729dd5d656ec84
# title: 动态获取ETF池子策略-

# 克隆自聚宽文章：https://www.joinquant.com/post/61912
# 标题：分享一个年化100低回撤的ETF轮动策略
# 作者：xiaolang1

# 克隆自聚宽文章：https://www.joinquant.com/post/57343
# 标题：多策略10.02社区学习版（更适合量化交易）
# 作者：O_iX

# 导入函数库
from jqdata import *
from jqfactor import get_factor_values
import datetime
import math, requests
from scipy.optimize import minimize
from scipy.linalg import inv
import uuid
# 必须在代码开头添加这行（导入datetime模块并取别名dt）
import datetime as dt  

from jqdata import *
import pandas as pd
import math


# ------------------------------------------------------------------------------
# 辅助函数1：get_all_etfs（移除交易日判断，修复end_date筛选）
# ------------------------------------------------------------------------------
# 处理日期相关函数（你的原函数）
def transform_date(date, date_type):
    if type(date) == str:
        str_date = date
        dt_date = dt.datetime.strptime(date, '%Y-%m-%d')
        d_date = dt_date.date()
    elif type(date) == dt.datetime:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = date
        d_date = dt_date.date()
    elif type(date) == dt.date:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = dt.datetime.strptime(str_date, '%Y-%m-%d')
        d_date = date
    dct = {'str': str_date, 'dt': dt_date, 'd': d_date}
    return dct[date_type]
    
    
def get_all_etfs(context):
    """筛选全市场ETF（上市≥6个月、未退市）"""
    current_date = context.current_dt.strftime("%Y-%m-%d")
    current_datetime = pd.to_datetime(current_date)
    log.info(f"【get_all_etfs】开始筛选{current_date}的ETF")

    # 步骤1：获取全市场所有基金数据
    try:
        all_funds = get_all_securities(["fund"], date=current_date)
        log.info(f"【get_all_etfs】步骤1：获取全市场基金 → 总数量：{len(all_funds)}")
        if all_funds.empty:
            log.error(f"【get_all_etfs】步骤1失败：无基金数据")
            return []
    except Exception as e:
        log.error(f"【get_all_etfs】步骤1报错：{str(e)}")
        return []

    # 步骤2：筛选ETF类型
    etf_df = all_funds[all_funds["type"] == "etf"].copy()
    log.info(f"【get_all_etfs】步骤2：筛选ETF → 数量：{len(etf_df)}")
    if etf_df.empty:
        log.error(f"【get_all_etfs】步骤2失败：无ETF类型基金")
        return []

    # 步骤3：计算上市天数
    try:
        etf_df["start_date_dt"] = pd.to_datetime(etf_df["start_date"])
        etf_df["listing_days"] = (current_datetime - etf_df["start_date_dt"]).dt.days
        log.info(f"【get_all_etfs】步骤3：计算上市天数 → 完成（{len(etf_df)}只）")
    except Exception as e:
        log.error(f"【get_all_etfs】步骤3报错：{str(e)}")
        return []

    # 步骤4：筛选上市≥180天的ETF
    min_listing_days = 180
    etf_df_listing = etf_df[etf_df["listing_days"] >= min_listing_days].copy()
    log.info(f"【get_all_etfs】步骤4：筛选上市≥{min_listing_days}天 → 剩余{len(etf_df_listing)}只")
    if etf_df_listing.empty:
        log.warning(f"【get_all_etfs】步骤4警告：无满足上市时间的ETF")
        return []

    # 步骤5：筛选未退市的ETF（end_date晚于当前日期）
    try:
        etf_df_listing["end_date_dt"] = pd.to_datetime(etf_df_listing["end_date"], errors="coerce")
        etf_df_final = etf_df_listing[
            (etf_df_listing["end_date_dt"].notna()) &
            (etf_df_listing["end_date_dt"] > current_datetime)
        ].copy()
        log.info(f"【get_all_etfs】步骤5：筛选未退市ETF → 最终{len(etf_df_final)}只")
        if etf_df_final.empty:
            log.warning(f"【get_all_etfs】步骤5警告：无未退市ETF")
            return []
    except Exception as e:
        log.error(f"【get_all_etfs】步骤5报错：{str(e)}")
        return []

    # 最终结果
    final_codes = etf_df_final.index.tolist()
    log.info(f"【get_all_etfs】完成：共{len(final_codes)}只ETF")
    return final_codes

# ------------------------------------------------------------------------------
# 辅助函数：计算ETF的成交额（完全匹配attribute_history参数）
# ------------------------------------------------------------------------------
def calculate_etf_volume(code, days=30, unit="1d"):
    """
    计算ETF的历史成交额（适配聚宽attribute_history参数）
    参数：
        code: ETF代码
        days: 取过去days天的数据（count参数）
        unit: 时间单位，默认"1d"（日线）
    返回：
        包含成交额的DataFrame，无数据则返回None
    """
    try:
        # 严格按照官方参数：用count指定天数，无end_date参数
        price_data = attribute_history(
            security=code,
            count=days,  # 取过去days天的数据（不含当天）
            unit=unit,
            fields=["money"],  # 成交额字段
            skip_paused=True,  # 跳过停牌日
            df=True,  # 返回DataFrame
            fq="pre"  # 前复权（默认）
        )
        # 日志：显示实际获取的日期范围（方便验证是否符合预期）
        if not price_data.empty:
            start_date = price_data.index[0].strftime("%Y-%m-%d")
            end_date = price_data.index[-1].strftime("%Y-%m-%d")
            # log.debug(f"【calculate_etf_volume】{code}获取{start_date}至{end_date}共{len(price_data)}天数据")
        return price_data
    except Exception as e:
        log.error(f"【calculate_etf_volume】{code}获取数据失败：{str(e)}")
        return None
# ------------------------------------------------------------------------------
# 辅助函数2：get_etf_shares_from_official（移除交易日判断和重试逻辑）
# ------------------------------------------------------------------------------
def get_etf_shares_from_official(query_date, etf_codes=None):
    """
    从聚宽finance.FUND_SHARE_DAILY表查询获取场内内基金份额数据（严格匹配官方字段）
    参数：
        query_date: 查询日期（格式"YYYY-MM-DD"）
        etf_codes: 可选，ETF代码列表，限制查询范围
    返回：
        包含code/name/shares的DataFrame，无数据则返回None
    """
    log.info(f"【get_etf_shares】查询{query_date}的场内内基金份额数据")
    
    try:
        # 1. 构造查询（只包含表中存在的字段）
        base_query = query(
            finance.FUND_SHARE_DAILY.code,        # 基金代码
            finance.FUND_SHARE_DAILY.name,        # 基金简称
            finance.FUND_SHARE_DAILY.shares       # 基金份额（份）
        ).filter(
            finance.FUND_SHARE_DAILY.date == query_date  # 筛选日期
        )
        
        # 2. 若指定ETF代码列表，缩小查询范围
        if etf_codes and len(etf_codes) > 0:
            log.info(f"【get_etf_shares】限制查询{len(etf_codes)}只ETF（示例：{etf_codes[:3]}）")
            base_query = base_query.filter(finance.FUND_SHARE_DAILY.code.in_(etf_codes))
        
        # 3. 执行查询（限制最大4000条，避免数据量过大）
        share_data = finance.run_query(base_query.limit(4000))
        log.info(f"【get_etf_shares】查询完成，返回{len(share_data)}条数据")
        
        if not share_data.empty:
            # 可选：添加市场信息（根据exchange_code区分沪深市场）
            share_data["market"] = share_data["code"].apply(
                lambda x: "XSHG" if x.endswith(".XSHG") else "XSHE" if x.endswith(".XSHE") else None
            )
            return share_data
        else:
            log.warning(f"【get_etf_shares】{query_date}无份额数据")
            return None
    
    except Exception as e:
        log.error(f"【get_etf_shares】查询失败：{str(e)}")
        return None


# ------------------------------------------------------------------------------
# 辅助函数3：get_etf_leaders_by_volume（兜底方案）
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# 兜底函数：get_etf_leaders_by_volume（完全适配API）
# ------------------------------------------------------------------------------
def get_etf_leaders_by_volume(context, min_proxy_size=10, min_avg_volume=5000, target_index_map=None):
    current_date = context.current_dt.strftime("%Y-%m-%d")
    log.info(f"【get_etf_leaders_by_volume】开始兜底方案（{current_date}）")

    # 1. 获取ETF列表
    etf_codes = get_all_etfs(context)
    log.info(f"【get_etf_leaders_by_volume】步骤1：ETF数量：{len(etf_codes)}")
    if not etf_codes:
        log.error(f"【get_etf_leaders_by_volume】步骤1失败：无ETF")
        return []

    # 2. 计算成交额
    etf_metrics = {}
    for code in etf_codes:
        price_data = calculate_etf_volume(code, days=30)
        if price_data is None or price_data.empty:
            log.warning(f"【get_etf_leaders_by_volume】{code}无成交额数据，跳过")
            continue
        if len(price_data) < 20:
            log.warning(f"【get_etf_leaders_by_volume】{code}有效交易日不足20天，跳过")
            continue

        total_money = price_data["money"].sum()
        avg_volume_30d = (total_money / len(price_data)) / 10000
        avg_volume_20d = (price_data["money"].tail(20).sum() / 20) / 10000
        estimated_size = (avg_volume_20d * 30) / 10000

        etf_metrics[code] = {
            "近30日日均成交额(万元)": round(avg_volume_30d, 2),
            "估算规模(亿元)": round(estimated_size, 2)
        }

    etf_metrics_df = pd.DataFrame.from_dict(etf_metrics, orient="index")
    if etf_metrics_df.empty:
        log.error(f"【get_etf_leaders_by_volume】步骤2失败：无有效成交额数据")
        return []
    log.info(f"【get_etf_leaders_by_volume】步骤2完成：有效ETF数量{len(etf_metrics_df)}")

    # 3. 匹配跟踪指数（只识别含"ETF"的名称）
    # 步骤6：匹配跟踪指数（扩大关键词范围）
    etf_name_to_index = {
        # ==================================================
        # 一、具体策略型ETF（优先级最高，避免被通用关键词覆盖）
        # ==================================================
        # 增强类
        "增强500": "000905.XSHG",        # 增强500 → 中证500指数
        "上50增强": "000016.XSHG",       # 上50增强 → 上证50指数
        "科创增强": "000688.XSHG",       # 科创增强 → 科创50指数
        "科100增": "000688.XSHG",        # 科100增 → 科创50指数
        
        # 低波/红利/股息类
        "低波红利": "000821.XSHG",       # 低波红利 → 低波指数
        "高股息": "000015.XSHG",         # 高股息 → 红利指数
        
        # ==================================================
        # 二、中证2000相关（具体名称优先）
        # ==================================================
        "ZZ2000": "000847.XSHG",         # ZZ2000 → 中证2000指数
        "2000指数": "000847.XSHG",       # 2000指数 → 中证2000指数
        "中证2000": "000847.XSHG",       # 中证2000 → 中证2000指数
        
        # ==================================================
        # 三、科创类（全覆盖，具体名称在前）
        # ==================================================
        "科创指基": "000688.XSHG",       # 科创指基 → 科创50指数
        "科创ETF": "000688.XSHG",        # 科创ETF → 科创50指数
        "上证科创": "000688.XSHG",       # 上证科创 → 科创50指数
        "科创信息": "000688.XSHG",       # 科创信息 → 科创50指数
        "科创成长": "000688.XSHG",       # 科创成长 → 科创50指数
        "科100ETF": "000688.XSHG",       # 科100ETF → 科创50指数
        "科创龙头": "000688.XSHG",       # 科创龙头 → 科创50指数
        "科创新能": "000688.XSHG",       # 科创新能 → 科创50指数
        "科创指数": "000688.XSHG",       # 科创指数 → 科创50指数
        "科创新材": "000688.XSHG",       # 科创新材 → 科创50指数
        "科创技术": "000688.XSHG",       # 科创技术 → 科创50指数
        "科创五零": "000688.XSHG",       # 科创五零 → 科创50指数
        "科创策略": "000688.XSHG",       # 科创策略 → 科创50指数
        "科创创业": "399296.XSHE",       # 科创创业 → 双创指数
        "创创ETF": "399006.XSHE",        # 创创ETF → 创业板指
        "科创芯": "000632.XSHG",         # 科创芯 → 半导体指数
        "芯片科创": "000632.XSHG",       # 芯片科创 → 半导体指数
        
        # ==================================================
        # 四、行业/主题ETF（具体名称优先）
        # ==================================================
        # 资源类
        "稀有金属": "000819.XSHG",       # 稀有金属 → 有色金属指数
        "有色金属": "000819.XSHG",       # 有色金属 → 有色金属指数
        "油气资源": "CL.NYMEX",          # 油气资源 → 原油指数
        "原油": "CL.NYMEX",              # 原油 → 原油指数
        "油气": "CL.NYMEX",              # 油气 → 原油指数
        
        # 新能源/电力
        "电池基金": "884031.WI",         # 电池基金 → 储能指数
        "储能": "884031.WI",             # 储能 → 储能指数
        "绿色电力": "000922.XSHG",       # 绿色电力 → 电力指数
        "电力": "000922.XSHG",           # 电力 → 电力指数
        "光伏": "884045.WI",             # 光伏 → 光伏指数
        "碳中和E": "000928.XSHG",        # 碳中和E → 双碳指数
        
        # 其他行业
        "现代农业": "000940.XSHG",       # 现代农业 → 农牧指数
        "农牧": "000940.XSHG",           # 农牧 → 农牧指数
        "电信ETF": "000916.XSHG",        # 电信ETF → 公用事业指数
        "公用事业": "000916.XSHG",       # 公用事业 → 公用事业指数
        "机器人": "884089.WI",           # 机器人 → 机器人指数
        "信创": "8841619.WI",            # 信创 → 信创指数
        "汽车": "000800.XSHG",           # 汽车 → 汽车指数
        "基建": "399995.XSHE",           # 基建 → 基建指数
        
        # 半导体/科技
        "半导体": "000632.XSHG",         # 半导体 → 半导体指数
        "芯片": "000632.XSHG",           # 芯片 → 半导体指数
        "集成电路": "000632.XSHG",       # 集成电路 → 半导体指数
        
        # 医疗/消费
        "生物医药": "000933.XSHG",       # 生物医药 → 生物医药指数
        "创新药": "000933.XSHG",         # 创新药 → 生物医药指数
        "医疗": "399989.XSHE",           # 医疗 → 医疗指数
        "消费": "000036.XSHG",           # 消费 → 消费指数
        
        # ==================================================
        # 五、宽基指数（通用名称在后，避免覆盖具体策略）
        # ==================================================
        # 沪深宽基
        "沪深300": "000300.XSHG",        # 沪深300 → 沪深300指数
        "上证50": "000016.XSHG",         # 上证50 → 上证50指数
        "中证500": "000905.XSHG",        # 中证500 → 中证500指数
        "中证1000": "000852.XSHG",       # 中证1000 → 中证1000指数
        "国证2000": "399303.XSHE",       # 国证2000 → 国证2000指数
        "创业板指": "399006.XSHE",       # 创业板指 → 创业板指
        "创业板综": "399102.XSHE",       # 创业板综 → 创业板综
        "创业板": "399006.XSHE",         # 创业板 → 创业板指
        "科创板50": "000688.XSHG",       # 科创板50 → 科创50指数
        "上证180": "000010.XSHG",        # 上证180 → 上证180指数
        "深证100": "399004.XSHE",        # 深证100 → 深证100指数
        "深证50": "399001.XSHE",         # 深证50 → 深证50指数
        "深主板50": "399001.XSHE",       # 深主板50 → 深证50指数
        "A50": "000016.XSHG",            # A50 → 上证50指数
        "A100": "000847.XSHG",           # A100 → 中证2000指数
        
        # 宽基简写（最后匹配，避免覆盖具体名称）
        "300": "000300.XSHG",            # 300 → 沪深300指数
        "50": "000016.XSHG",             # 50 → 上证50指数
        "500": "000905.XSHG",            # 500 → 中证500指数
        "1000": "000852.XSHG",           # 1000 → 中证1000指数
        "2000": "000847.XSHG",           # 2000 → 中证2000指数
        "180": "000010.XSHG",            # 180 → 上证180指数
        "100": "399004.XSHE",            # 100 → 深证100指数
        
        # ==================================================
        # 六、海外指数
        # ==================================================
        "纳指": "IXIC",                  # 纳指 → 纳斯达克指数
        "纳斯达克": "IXIC",              # 纳斯达克 → 纳斯达克指数
        "标普500": "SPX",                # 标普500 → 标普500指数
        "标普生物科技": "SPX.BIO",       # 标普生物科技 → 标普生物科技指数
        "美国50": "SPX",                 # 美国50 → 标普500指数
        "德国": "GDAXI",                 # 德国 → 德国DAX指数
        "沙特": "TASI.SR",               # 沙特 → 沙特TASI指数
        
        # ==================================================
        # 七、港股指数
        # ==================================================
        "恒生科技": "HSTECH.HK",         # 恒生科技 → 恒生科技指数
        "恒生港股通": "HSCEI.HK",         # 恒生港股通 → 恒生国企指数
        "港股国企": "HSCEI.HK",          # 港股国企 → 恒生国企指数
        "恒生红利": "HSHKDIV.HK",        # 恒生红利 → 恒生红利指数
        "恒生生物科技": "HSCI.BIOTECH",  # 恒生生物科技 → 恒生生物科技指数
        "中概互联": "KWEB",              # 中概互联 → 中概互联指数
        "港股互联网": "HSTECH.HK",       # 港股互联网 → 恒生科技指数
        
        # ==================================================
        # 八、商品指数
        # ==================================================
        "黄金": "AU9999.XSGE",           # 黄金 → 黄金指数
        
        # ==================================================
        # 九、策略指数（红利/低波等，通用关键词）
        # ==================================================
        "红利": "000015.XSHG",           # 红利 → 红利指数
        "低波": "000821.XSHG",           # 低波 → 低波指数
        "价值": "000015.XSHG",           # 价值 → 红利指数
        "成长": "000016.XSHG",           # 成长 → 上证50指数
        "增强": ""                       # 增强类（依赖基础指数关键词）
    }
    etf_metrics_df["跟踪指数"] = None
    for code in etf_metrics_df.index:
        try:
            etf_name = get_security_info(code).display_name
            for name_key, index_code in etf_name_to_index.items():
                if name_key in etf_name:  # 只匹配明确含"ETF"的名称
                    etf_metrics_df.loc[code, "跟踪指数"] = index_code
                    break
        except Exception as e:
            log.warning(f"【get_etf_leaders_by_volume】{code}匹配指数失败：{str(e)}")





    etf_metrics_df_matched = etf_metrics_df.dropna(subset=["跟踪指数"])
    if etf_metrics_df_matched.empty:
        log.error(f"【get_etf_leaders_by_volume】步骤3失败：无匹配指数的ETF")
        return []

    # 4. 筛选达标ETF并选龙头（只保留沪深市场ETF）
    etf_filtered = etf_metrics_df_matched[
        (etf_metrics_df_matched["估算规模(亿元)"] >= min_proxy_size) |
        (etf_metrics_df_matched["近30日日均成交额(万元)"] >= min_avg_volume)
    ]
    # 强制过滤：只保留上交所和深交所的ETF
    etf_filtered = etf_filtered[
        etf_filtered.index.str.endswith(".XSHG") | 
        etf_filtered.index.str.endswith(".XSHE")
    ]
    if target_index_map and len(target_index_map) > 0:
        target_index_codes = list(target_index_map.values())
        etf_filtered = etf_filtered[etf_filtered["跟踪指数"].isin(target_index_codes)]
    if etf_filtered.empty:
        log.warning(f"【get_etf_leaders_by_volume】无达标ETF")
        return []

    etf_leaders = etf_filtered.groupby("跟踪指数", group_keys=False).apply(
        lambda x: x.sort_values(by=["估算规模(亿元)", "近30日日均成交额(万元)"], ascending=False).iloc[0]
    )
    final_etf_codes = etf_leaders.index.tolist()  # 返回ETF代码
    log.info(f"【get_etf_leaders_by_volume】完成：{len(final_etf_codes)}只龙头")
    return final_etf_codes

# ------------------------------------------------------------------------------
# 核心函数：get_etf_leaders_final（移除交易日判断）
# ------------------------------------------------------------------------------
# --------------------------
# 核心函数：筛选ETF龙头
# --------------------------
# 修改后（将默认值改为规模50亿和成交2亿）
def get_etf_leaders_final(context, min_size=30, min_avg_volume=10000, target_index_map=None):
    current_dt = context.current_dt
    current_date = transform_date(current_dt, 'str')
    current_date_d = transform_date(current_dt, 'd')
    prev_date_d = current_date_d + dt.timedelta(days=-1)
    prev_date = transform_date(prev_date_d, 'str')
    log.info(f"\n===== 【筛选龙头】开始（{current_date}） =====")
    log.info(f"当前日期：{current_date}，上一自然日：{prev_date}")

    # 步骤1：获取基础ETF列表
    etf_codes = get_all_etfs(context)
    log.info(f"步骤1：基础ETF数量：{len(etf_codes)}（示例：{etf_codes[:3] if etf_codes else '无'}）")
    if not etf_codes:
        log.error("步骤1失败：无符合条件的基础ETF")
        return []

    # 步骤2：获取份额数据
    share_data = get_etf_shares_from_official(current_date, etf_codes)
    if share_data is None or share_data.empty:
        log.error("步骤2失败：份额数据为空，将切换兜底方案")
        return get_etf_leaders_by_volume(context, min_size, min_avg_volume, target_index_map)
    log.info(f"步骤2：获取份额数据成功，共{len(share_data)}条（示例代码：{share_data['code'].tolist()[:3]}）")

    # 步骤3：获取净值数据
    try:
        nav_data = get_extras("unit_net_value", etf_codes, end_date=prev_date, count=1, df=True)
        nav_latest = nav_data.iloc[0].dropna().to_dict()
        log.info(f"步骤3：获取净值数据成功，共{len(nav_latest)}条（示例代码：{list(nav_latest.keys())[:3]}）")
        if not nav_latest:
            log.error("步骤3失败：净值数据为空，切换兜底方案")
            return get_etf_leaders_by_volume(context, min_size, min_avg_volume, target_index_map)
    except Exception as e:
        log.error(f"步骤3失败：获取净值出错 → {str(e)}，切换兜底方案")
        return get_etf_leaders_by_volume(context, min_size, min_avg_volume, target_index_map)

    # 步骤4：计算规模
    share_dict = dict(zip(share_data["code"], share_data["shares"]))
    etf_size_dict = {}
    for code in share_dict:
        if code in nav_latest:
            size = (share_dict[code] * nav_latest[code]) / 100000000  # 亿元
            etf_size_dict[code] = round(size, 2)
    log.info(f"步骤4：计算规模完成，有效ETF数量：{len(etf_size_dict)}（示例：{list(etf_size_dict.keys())[:3]}）")
    if not etf_size_dict:
        log.error("步骤4失败：无有效规模数据，切换兜底方案")
        return get_etf_leaders_by_volume(context, min_size, min_avg_volume, target_index_map)

    # 步骤5：计算成交额
    etf_metrics = {}
    for i, code in enumerate(etf_size_dict.keys()):
        # if i % 50 == 0:  # 每50个打印一次进度
        #     log.info(f"步骤5：正在计算成交额（{i+1}/{len(etf_size_dict)}）→ 当前代码：{code}")
        price_data = calculate_etf_volume(code, days=30)
        if price_data is None or price_data.empty:
            log.warning(f"步骤5：{code}无成交额数据，跳过")
            continue
        if len(price_data) < 20:
            log.warning(f"步骤5：{code}有效交易日不足20天（实际{len(price_data)}天），跳过")
            continue
        total_money = price_data["money"].sum()
        avg_volume = (total_money / len(price_data)) / 10000  # 万元
        etf_metrics[code] = {
            "规模(亿元)": etf_size_dict[code],
            "近30日日均成交额(万元)": round(avg_volume, 2),
            "跟踪指数": None
        }
    log.info(f"步骤5：计算成交额完成，有效ETF数量：{len(etf_metrics)}（示例：{list(etf_metrics.keys())[:3]}）")
    if not etf_metrics:
        log.error("步骤5失败：无有效成交额数据，切换兜底方案")
        return get_etf_leaders_by_volume(context, min_size, min_avg_volume, target_index_map)

    # 步骤6：匹配跟踪指数
    etf_name_to_index = {    # ==================================================
        # 1. 债券/转债类
        # ==================================================
        "基准国债": "000010.XSHG",       # 基准国债 → 上证180（暂归宽基，或替换为国债指数）
        "国债30年": "000010.XSHG",       # 国债30年 → 上证180
        "上证转债": "000016.XSHG",       # 上证转债 → 上证50
        "城投ETF": "000016.XSHG",       # 城投ETF → 上证50
        "十年国债": "000010.XSHG",       # 十年国债 → 上证180
        "短融ETF": "000016.XSHG",        # 短融ETF → 上证50
        "转债ETF": "000016.XSHG",        # 转债ETF → 上证50
        "政金债": "000010.XSHG",         # 政金债 → 上证180
        "国债政金": "000010.XSHG",       # 国债政金 → 上证180
    
        # ==================================================
        # 2. 金融类（证券/银行/保险）
        # ==================================================
        "券商ETF": "000016.XSHG",       # 券商ETF → 上证50
        "证券保险": "000016.XSHG",       # 证券保险 → 上证50
        "中证证券": "000016.XSHG",       # 中证证券 → 上证50
        "证券ETF": "000016.XSHG",       # 证券ETF → 上证50
        "证券基金": "000016.XSHG",       # 证券基金 → 上证50
        "证券龙头": "000016.XSHG",       # 证券龙头 → 上证50
        "证券行业": "000016.XSHG",       # 证券行业 → 上证50
        "证券先锋": "000016.XSHG",       # 证券先锋 → 上证50
        "保险证券": "000016.XSHG",       # 保险证券 → 上证50
        "银行指数": "000016.XSHG",       # 银行指数 → 上证50
        "银行基金": "000016.XSHG",       # 银行基金 → 上证50
        "银行FUND": "000016.XSHG",      # 银行FUND → 上证50
        "银行ETF": "000016.XSHG",        # 银行ETF → 上证50
        "银行股基": "000016.XSHG",       # 银行股基 → 上证50
        "银行股": "000016.XSHG",         # 银行股 → 上证50
        "银行指基": "000016.XSHG",       # 银行指基 → 上证50
    
        # ==================================================
        # 3. 科技/互联网/AI类
        # ==================================================
        "信息ETF": "000971.XSHG",        # 信息ETF → 计算机指数
        "AIETF": "8841619.WI",           # AIETF → 信创指数
        "科技30": "000971.XSHG",         # 科技30 → 计算机指数
        "互联网30": "HSTECH.HK",         # 互联网30 → 恒生科技
        "传媒ETF": "8841619.WI",         # 传媒ETF → 信创指数
        "文娱ETF": "8841619.WI",         # 文娱ETF → 信创指数
        "游戏传媒": "8841619.WI",        # 游戏传媒 → 信创指数
        "游戏动漫": "8841619.WI",        # 游戏动漫 → 信创指数
        "智能驾驶": "884031.WI",         # 智能驾驶 → 储能指数（归为新能源相关）
        "智能制造ETF": "884089.WI",     # 智能制造 → 机器人指数
        "大数据": "8841619.WI",          # 大数据 → 信创指数
        "数据ETF": "8841619.WI",         # 数据ETF → 信创指数
    
        # ==================================================
        # 4. 港股/海外指数类
        # ==================================================
        "港股科技": "HSTECH.HK",         # 港股科技 → 恒生科技
        "科技HK": "HSTECH.HK",           # 科技HK → 恒生科技
        "HK互联网": "HSTECH.HK",         # HK互联网 → 恒生科技
        "恒指科技": "HSTECH.HK",         # 恒指科技 → 恒生科技
        "恒科技": "HSTECH.HK",           # 恒科技 → 恒生科技
        "HK新经济": "HSTECH.HK",         # HK新经济 → 恒生科技
        "香港科技": "HSTECH.HK",         # 香港科技 → 恒生科技
        "HS科技": "HSTECH.HK",           # HS科技 → 恒生科技
        "HKC科技": "HSTECH.HK",          # HKC科技 → 恒生科技
        "香港证券": "HSCEI.HK",          # 香港证券 → 恒生国企
        "港股非银": "HSCEI.HK",          # 港股非银 → 恒生国企
        "港股分红": "HSHKDIV.HK",        # 港股分红 → 恒生红利
        "恒指ETF": "HSCEI.HK",           # 恒指ETF → 恒生国企
        "225ETF": "N225",                # 225ETF → 日经225
        "日经ETF": "N225",               # 日经ETF → 日经225
        "日经225": "N225",               # 日经225 → 日经225
        "东证ETF": "N225",               # 东证ETF → 日经225
        "道琼斯": "DJI",                 # 道琼斯 → 道指
        "标普ETF": "SPX",                # 标普ETF → 标普500
        "法国ETF": "FCHI",               # 法国ETF → 法国CAC40
        "东南亚": "FTSE.ASEAN",          # 东南亚 → 东盟指数（暂定义）
    
        # ==================================================
        # 5. 行业类（军工/地产/消费等）
        # ==================================================
        "中证军工": "399967.XSHE",       # 中证军工 → 军工指数
        "军工ETF": "399967.XSHE",        # 军工ETF → 军工指数
        "国防ETF": "399967.XSHE",        # 国防ETF → 军工指数
        "军工基金": "399967.XSHE",       # 军工基金 → 军工指数
        "军工龙头": "399967.XSHE",       # 军工龙头 → 军工指数
        "国防军工": "399967.XSHE",       # 国防军工 → 军工指数
        "地产ETF": "000016.XSHG",        # 地产ETF → 上证50
        "华夏地产": "000016.XSHG",       # 华夏地产 → 上证50
        "食品饮料": "000036.XSHG",       # 食品饮料 → 消费指数
        "食品ETF": "000036.XSHG",        # 食品ETF → 消费指数
        "酒ETF": "000036.XSHG",          # 酒ETF → 消费指数
        "钢铁ETF": "000913.XSHG",        # 钢铁ETF → 钢铁指数
        "煤炭ETF": "000820.XSHG",        # 煤炭ETF → 煤炭指数
        "电子ETF": "000632.XSHG",        # 电子ETF → 半导体指数
        "电子龙头": "000632.XSHG",       # 电子龙头 → 半导体指数
        "新能车": "884031.WI",           # 新能车 → 储能指数
        "智慧电车": "884031.WI",         # 智慧电车 → 储能指数
        "汽配ETF": "884031.WI",          # 汽配ETF → 储能指数（汽车配件）
        "环保ETF": "000928.XSHG",        # 环保ETF → 双碳指数
        "稀土基金": "000819.XSHG",       # 稀土基金 → 有色金属指数
        "稀土ETF": "000819.XSHG",        # 稀土ETF → 有色金属指数
        "稀金属": "000819.XSHG",         # 稀金属 → 有色金属指数
        "矿业ETF": "000819.XSHG",        # 矿业ETF → 有色金属指数
        "石化ETF": "CL.NYMEX",           # 石化ETF → 原油指数
        "石油ETF": "CL.NYMEX",           # 石油ETF → 原油指数
        "化工ETF": "000986.XSHG",        # 化工ETF → 化工指数
        "化工龙头": "000986.XSHG",       # 化工龙头 → 化工指数
        "农业ETF": "000940.XSHG",        # 农业ETF → 农牧指数
        "农业": "000940.XSHG",           # 农业 → 农牧指数
        "畜牧养殖": "000940.XSHG",       # 畜牧养殖 → 农牧指数
        "养殖ETF": "000940.XSHG",        # 养殖ETF → 农牧指数
        "建材ETF": "399995.XSHE",        # 建材ETF → 基建指数
        "物流ETF": "399995.XSHE",        # 物流ETF → 基建指数（归为基建产业链）
        "机械ETF": "399995.XSHE",        # 机械ETF → 基建指数
        "家电ETF": "000036.XSHG",        # 家电ETF → 消费指数
        "消电ETF": "000036.XSHG",        # 消电ETF（消费电子）→ 消费指数
        "教育ETF": "000036.XSHG",        # 教育ETF → 消费指数（归为服务消费）
    
        # ==================================================
        # 6. 主题/策略类（碳中和/ESG/国企等）
        # ==================================================
        "碳中和基": "000928.XSHG",       # 碳中和基 → 双碳指数
        "碳中和": "000928.XSHG",         # 碳中和 → 双碳指数
        "绿电ETF": "000922.XSHG",        # 绿电ETF → 电力指数
        "可持续": "000928.XSHG",         # 可持续 → 双碳指数
        "ESGETF": "000928.XSHG",         # ESGETF → 双碳指数
        "沪深ESG": "000928.XSHG",        # 沪深ESG → 双碳指数
        "战略新兴": "000688.XSHG",       # 战略新兴 → 科创50指数
        "国企方达": "000016.XSHG",       # 国企方达 → 上证50
        "国企富国": "000016.XSHG",       # 国企富国 → 上证50
        "添富国企": "000016.XSHG",       # 添富国企 → 上证50
        "中国国企": "000016.XSHG",       # 中国国企 → 上证50
        "央创ETF": "000016.XSHG",        # 央创ETF（央企创新）→ 上证50
        "央调ETF": "000016.XSHG",        # 央调ETF（央企调整）→ 上证50
        "质量ETF": "000016.XSHG",        # 质量ETF → 上证50
        "长三角": "399004.XSHE",         # 长三角 → 深证100
        "杭州湾区": "399004.XSHE",       # 杭州湾区 → 深证100
        "湾区ETF": "399004.XSHE",        # 湾区ETF → 深证100
        "长江ETF": "399004.XSHE",        # 长江ETF → 深证100
        "长江保护": "399004.XSHE",       # 长江保护 → 深证100
        "张江ETF": "000688.XSHG",        # 张江ETF（科创园区）→ 科创50
        "共赢ETF": "000300.XSHG",        # 共赢ETF → 沪深300
        "之江凤凰": "000688.XSHG",       # 之江凤凰（科创相关）→ 科创50
    
        # ==================================================
        # 7. MSCI相关
        # ==================================================
        "MSCI易基": "MSCI.CHINA",         # MSCI易基 → MSCI中国
        "MSCI基金": "MSCI.CHINA",         # MSCI基金 → MSCI中国
        "建信MSCI": "MSCI.CHINA",        # 建信MSCI → MSCI中国
        "景顺MSCI": "MSCI.CHINA",        # 景顺MSCI → MSCI中国
        "MSCI国际": "MSCI.CHINA",        # MSCI国际 → MSCI中国
        "MSCI中国": "MSCI.CHINA",        # MSCI中国 → MSCI中国
        "MSCIETF": "MSCI.CHINA",         # MSCIETF → MSCI中国
        "MSCIAETF": "MSCI.CHINA",        # MSCIAETF → MSCI中国
        "浦银MSCI": "MSCI.CHINA",        # 浦银MSCI → MSCI中国
        "MSCI招商": "MSCI.CHINA",        # MSCI招商 → MSCI中国
        "MSCIA股": "MSCI.CHINA",         # MSCIA股 → MSCI中国
    
        # ==================================================
        # 8. 其他补充
        # ==================================================
        "800ETF": "000906.XSHG",         # 800ETF → 中证800指数
        "ZZ800ETF": "000906.XSHG",       # ZZ800ETF → 中证800指数
        "新药ETF": "000933.XSHG",        # 新药ETF → 生物医药指数
        "生科ETF": "000933.XSHG",        # 生科ETF → 生物医药指数
        "疫苗龙头": "000933.XSHG",       # 疫苗龙头 → 生物医药指数
        "电池ETF": "884031.WI",          # 电池ETF → 储能指数
        "浙江国资": "000016.XSHG",       # 浙江国资 → 上证50
        "电信主题": "000916.XSHG",       # 电信主题 → 公用事业指数
        "金ETF": "AU9999.XSGE",          # 金ETF → 黄金指数
        "增强ETF": "",                   # 增强ETF（依赖基础指数关键词）
        
        "513890.XSHG": "HSTECH.HK",    # HK科技
        "513980.XSHG": "HSTECH.HK",    # 科技港股
        "513990.XSHG": "HSCEI.HK",     # 港股通综
        "515000.XSHG": "000971.XSHG",  # 科技ETF
        "515010.XSHG": "000016.XSHG",  # 华夏证券
        #新能源与汽车类
        
            # ==================================================
        # 一、具体策略型ETF（优先级最高，避免被通用关键词覆盖）
        # ==================================================
        # 增强类
        "增强500": "000905.XSHG",        # 增强500 → 中证500指数
        "上50增强": "000016.XSHG",       # 上50增强 → 上证50指数
        "科创增强": "000688.XSHG",       # 科创增强 → 科创50指数
        "科100增": "000688.XSHG",        # 科100增 → 科创50指数
        
        # 低波/红利/股息类
        "低波红利": "000821.XSHG",       # 低波红利 → 低波指数
        "高股息": "000015.XSHG",         # 高股息 → 红利指数
        
        # ==================================================
        # 二、中证2000相关（具体名称优先）
        # ==================================================
        "ZZ2000": "000847.XSHG",         # ZZ2000 → 中证2000指数
        "2000指数": "000847.XSHG",       # 2000指数 → 中证2000指数
        "中证2000": "000847.XSHG",       # 中证2000 → 中证2000指数
        
        # ==================================================
        # 三、科创类（全覆盖，具体名称在前）
        # ==================================================
        "科创指基": "000688.XSHG",       # 科创指基 → 科创50指数
        "科创ETF": "000688.XSHG",        # 科创ETF → 科创50指数
        "上证科创": "000688.XSHG",       # 上证科创 → 科创50指数
        "科创信息": "000688.XSHG",       # 科创信息 → 科创50指数
        "科创成长": "000688.XSHG",       # 科创成长 → 科创50指数
        "科100ETF": "000688.XSHG",       # 科100ETF → 科创50指数
        "科创龙头": "000688.XSHG",       # 科创龙头 → 科创50指数
        "科创新能": "000688.XSHG",       # 科创新能 → 科创50指数
        "科创指数": "000688.XSHG",       # 科创指数 → 科创50指数
        "科创新材": "000688.XSHG",       # 科创新材 → 科创50指数
        "科创技术": "000688.XSHG",       # 科创技术 → 科创50指数
        "科创五零": "000688.XSHG",       # 科创五零 → 科创50指数
        "科创策略": "000688.XSHG",       # 科创策略 → 科创50指数
        "科创创业": "399296.XSHE",       # 科创创业 → 双创指数
        "创创ETF": "399006.XSHE",        # 创创ETF → 创业板指
        "科创芯": "000632.XSHG",         # 科创芯 → 半导体指数
        "芯片科创": "000632.XSHG",       # 芯片科创 → 半导体指数
        
        # ==================================================
        # 四、行业/主题ETF（具体名称优先）
        # ==================================================
        # 资源类
        "稀有金属": "000819.XSHG",       # 稀有金属 → 有色金属指数
        "有色金属": "000819.XSHG",       # 有色金属 → 有色金属指数
        "油气资源": "CL.NYMEX",          # 油气资源 → 原油指数
        "原油": "CL.NYMEX",              # 原油 → 原油指数
        "油气": "CL.NYMEX",              # 油气 → 原油指数
        
        # 新能源/电力
        "电池基金": "884031.WI",         # 电池基金 → 储能指数
        "储能": "884031.WI",             # 储能 → 储能指数
        "绿色电力": "000922.XSHG",       # 绿色电力 → 电力指数
        "电力": "000922.XSHG",           # 电力 → 电力指数
        "光伏": "884045.WI",             # 光伏 → 光伏指数
        "碳中和E": "000928.XSHG",        # 碳中和E → 双碳指数
        
        # 其他行业
        "现代农业": "000940.XSHG",       # 现代农业 → 农牧指数
        "农牧": "000940.XSHG",           # 农牧 → 农牧指数
        "电信ETF": "000916.XSHG",        # 电信ETF → 公用事业指数
        "公用事业": "000916.XSHG",       # 公用事业 → 公用事业指数
        "机器人": "884089.WI",           # 机器人 → 机器人指数
        "信创": "8841619.WI",            # 信创 → 信创指数
        "汽车": "000800.XSHG",           # 汽车 → 汽车指数
        "基建": "399995.XSHE",           # 基建 → 基建指数
        
        # 半导体/科技
        "半导体": "000632.XSHG",         # 半导体 → 半导体指数
        "芯片": "000632.XSHG",           # 芯片 → 半导体指数
        "集成电路": "000632.XSHG",       # 集成电路 → 半导体指数
        
        # 医疗/消费
        "生物医药": "000933.XSHG",       # 生物医药 → 生物医药指数
        "创新药": "000933.XSHG",         # 创新药 → 生物医药指数
        "医疗": "399989.XSHE",           # 医疗 → 医疗指数
        "消费": "000036.XSHG",           # 消费 → 消费指数
        
        # ==================================================
        # 五、宽基指数（通用名称在后，避免覆盖具体策略）
        # ==================================================
        # 沪深宽基
        "沪深300": "000300.XSHG",        # 沪深300 → 沪深300指数
        "上证50": "000016.XSHG",         # 上证50 → 上证50指数
        "中证500": "000905.XSHG",        # 中证500 → 中证500指数
        "中证1000": "000852.XSHG",       # 中证1000 → 中证1000指数
        "国证2000": "399303.XSHE",       # 国证2000 → 国证2000指数
        "创业板指": "399006.XSHE",       # 创业板指 → 创业板指
        "创业板综": "399102.XSHE",       # 创业板综 → 创业板综
        "创业板": "399006.XSHE",         # 创业板 → 创业板指
        "科创板50": "000688.XSHG",       # 科创板50 → 科创50指数
        "上证180": "000010.XSHG",        # 上证180 → 上证180指数
        "深证100": "399004.XSHE",        # 深证100 → 深证100指数
        "深证50": "399001.XSHE",         # 深证50 → 深证50指数
        "深主板50": "399001.XSHE",       # 深主板50 → 深证50指数
        "A50": "000016.XSHG",            # A50 → 上证50指数
        "A100": "000847.XSHG",           # A100 → 中证2000指数
        
        # 宽基简写（最后匹配，避免覆盖具体名称）
        "300": "000300.XSHG",            # 300 → 沪深300指数
        "50": "000016.XSHG",             # 50 → 上证50指数
        "500": "000905.XSHG",            # 500 → 中证500指数
        "1000": "000852.XSHG",           # 1000 → 中证1000指数
        "2000": "000847.XSHG",           # 2000 → 中证2000指数
        "180": "000010.XSHG",            # 180 → 上证180指数
        "100": "399004.XSHE",            # 100 → 深证100指数
        
        # ==================================================
        # 六、海外指数
        # ==================================================
        "纳指": "IXIC",                  # 纳指 → 纳斯达克指数
        "纳斯达克": "IXIC",              # 纳斯达克 → 纳斯达克指数
        "标普500": "SPX",                # 标普500 → 标普500指数
        "标普生物科技": "SPX.BIO",       # 标普生物科技 → 标普生物科技指数
        "美国50": "SPX",                 # 美国50 → 标普500指数
        "德国": "GDAXI",                 # 德国 → 德国DAX指数
        "沙特": "TASI.SR",               # 沙特 → 沙特TASI指数
        
        # ==================================================
        # 七、港股指数
        # ==================================================
        "恒生科技": "HSTECH.HK",         # 恒生科技 → 恒生科技指数
        "恒生港股通": "HSCEI.HK",         # 恒生港股通 → 恒生国企指数
        "港股国企": "HSCEI.HK",          # 港股国企 → 恒生国企指数
        "恒生红利": "HSHKDIV.HK",        # 恒生红利 → 恒生红利指数
        "恒生生物科技": "HSCI.BIOTECH",  # 恒生生物科技 → 恒生生物科技指数
        "中概互联": "KWEB",              # 中概互联 → 中概互联指数
        "港股互联网": "HSTECH.HK",       # 港股互联网 → 恒生科技指数
        
        # ==================================================
        # 八、商品指数
        # ==================================================
        "黄金": "AU9999.XSGE",           # 黄金 → 黄金指数
        
        # ==================================================
        # 九、策略指数（红利/低波等，通用关键词）
        # ==================================================
        "红利": "000015.XSHG",           # 红利 → 红利指数
        "低波": "000821.XSHG",           # 低波 → 低波指数
        "价值": "000015.XSHG",           # 价值 → 红利指数
        "成长": "000016.XSHG",           # 成长 → 上证50指数
        
        # 补充科创类ETF映射（核心修改）
        # "科创创业": "399296.XSHE",    # 科创创业 → 双创指数（创成长）
        "科创增强": "000688.XSHG",    # 科创增强 → 科创50指数
        "科100增": "000688.XSHG",     # 科100增 → 科创50指数（科创100暂归为科创50）
        "科创新能": "000688.XSHG",    # 科创新能 → 科创50指数
        "科创指数": "000688.XSHG",    # 科创指数 → 科创50指数
        "科创芯": "000632.XSHG",      # 科创芯 → 半导体指数（000632）
        "智能电车": "000941.XSHG",        # 智能电车、智慧电车（新能源汽车）
        "电动车": "000941.XSHG",          # 电动车、电动汽车、新能汽车
        "锂电池": "884031.WI",            # 锂电池、电池ETF、电池基金
        "光伏50": "884045.WI",            # 光伏50、光伏龙头
        "绿电50": "000922.XSHG",          # 绿电50、绿色电力、绿电ETF
        "双碳": "000928.XSHG",            # 双碳ETF、碳中和、碳中和基
        "碳60": "000928.XSHG",            # 碳60ETF、碳中和E
        "低碳": "000928.XSHG",            # 低碳ETF
        #金融与宽基类
        
        
        "证券公司": "000950.XSHG",        # 证券公司、证券指数、证券先锋
        "银行优选": "000016.XSHG",        # 银行优选（银行归金融）
        "A50": "000016.XSHG",             # A50指数、中国A50、中证A50
        "1000基金": "000852.XSHG",        # 1000基金、1000鹏华、中证1000
        "2000基金": "000847.XSHG",        # 2000基金、2000ETF、中证2000
        "漂亮50": "000016.XSHG",          # 漂亮50（上证50）
        "核心50": "000016.XSHG",          # 核心50（上证50）
        "300成长": "000300.XSHG",         # 300成长、300价值E（沪深300）
        "500质量": "000905.XSHG",         # 500质量、500增（中证500）
        "A股ETF": "000001.XSHG",          # A股ETF（上证综指）
        
        #科创板与双创类
        "科创50": "000688.XSHG",          # 科创50、科创50E、科创板50
        "科创板": "000688.XSHG",          # 科创板、上证科创、科创指数
        "科创100": "000688.XSHG",         # 科创100、科100ETF、科创100Z
        "双创": "399296.XSHE",            # 双创ETF、双创基金、双创50
        "创50ETF": "399006.XSHE",         # 创50ETF（创业板指）
        "科创生物": "000688.XSHG",        # 科创生物（科创板医药）
        # 跨境与商品类
        "沪港深": "HSI.HK",               # 沪港深、沪港深E（恒生指数）
        "AH500": "HSI.HK",                # AH500ETF、AH300ETF（恒生指数）
        "互联网50": "HSI.HK",             # 互联网50、互联网（港股互联网）
        "黄金股票": "AU9999.XSGE",        # 黄金股票、黄金股（黄金指数）
        "上海金": "AU9999.XSGE",          # 上海金、金ETF、黄金基金
        "沙特ETF": "TASI.SR",             # 沙特ETF（沙特阿拉伯指数）
        # 其他细分主题
        "物流快递": "000036.XSHG",        # 物流快递、物流ETF（交通运输）
        "交运ETF": "000036.XSHG",         # 交运ETF（交通运输）
        "影视ETF": "000971.XSHG",         # 影视ETF、游戏动漫、游戏传媒
        "养老ETF": "399989.XSHE",         # 养老ETF（医疗保健）
        "基建ETF": "399995.XSHE",         # 基建ETF、基建50（建筑指数）
        "工程机械": "399995.XSHE",        # 工程机械、机械ETF
        "机器人": "884089.WI",            # 机器人YH、机器人产业
        "高端制造": "884089.WI",          # 高端制造、智能制造ETF
        "电信50": "000916.XSHG",          # 电信50、电信ETF、电信主题
        "信息安全": "000971.XSHG",        # 信息安全（计算机）
        "汽车零件": "000800.XSHG",        # 汽车零件、汽配ETF（汽车指数）
        "新材ETF": "000909.XSHG",         # 新材ETF（材料指数）
        
        # 三、医药与消费类
        
        "生物ETF": "000933.XSHG",         # 生物ETF、生科ETF（生物医药）
        "医服ETF": "399989.XSHE",         # 医服ETF、医疗创新（医疗服务）
        "中药": "000933.XSHG",            # 中药ETF、中药基金
        "创新药50": "000933.XSHG",        # 创新药50、创新药ETF、创新药企
        "创新药HK": "HSCEI.HK",           # 创新药HK（港股医药）
        "生物疫苗": "000933.XSHG",        # 生物疫苗、疫苗龙头
        "保健ETF": "399989.XSHE",         # 保健ETF（医疗保健）
        "医疗50": "399989.XSHE",          # 医疗50（医疗指数）
        "消服ETF": "000036.XSHG",         # 消服ETF（消费服务）
        "食品50": "000036.XSHG",          # 食品50（食品饮料）
        "家电基金": "000036.XSHG",        # 家电基金、家电ETF（可选消费）
        "国货ETF": "000036.XSHG",         # 国货ETF（消费）
        "消电50": "000036.XSHG",          # 消电50、消电ETF（消费电子）
        "旅游ETF": "000036.XSHG",         # 旅游ETF（休闲服务）
        #科技与高端制造类
        "装备": "000928.XSHG",            # 装备ETF（归为能源设备）
        "物联网": "000971.XSHG",          # 物联网、物联网ETF沪港深（计算机）
        "芯片50": "000632.XSHG",          # 芯片50、芯片龙头、芯片设备（半导体）
        "芯片基金": "000632.XSHG",        # 芯片基金、芯片科创
        "云计算": "000971.XSHG",          # 云计算、云计算50、云计算ETF沪港深
        "数据产业": "000971.XSHG",        # 数据产业（计算机）
        "AI50": "000971.XSHG",            # AI50（人工智能归计算机）
        "集成电路": "000632.XSHG",        # 集成电路（半导体）
        "半导设备": "000632.XSHG",        # 半导设备（半导体）
        "数字ETF": "000971.XSHG",         # 数字ETF（数字经济归计算机）
        "信创50": "000971.XSHG",          # 信创50、信创ETF（信息技术）
        "科创芯片": "000688.XSHG",        # 科创芯片（科创板半导体）
            # 新增：细分宽基指数
        "深证100": "399004.XSHE",        # 深证100（含深100ETF、深证100ETF）
        "中小100": "399005.XSHE",        # 中小板100指数
        "深成指": "399001.XSHE",         # 深证成指（深成ETF、深证成指ETF）
        "深成": "399001.XSHE",           # 简写“深成”
        "中创400": "399628.XSHE",        # 中创400指数
        "创业板50": "399673.XSHE",       # 创业板50指数
        "创大盘": "399293.XSHE",         # 创业板大盘指数
        "基本面120": "000012.XSHG",      # 基本面120指数
        "央视50": "399550.XSHE",         # 央视50指数
        "F60": "399001.XSHE",            # 深F60（暂映射深证成指）
    
        # 新增：细分行业/主题指数
        "医疗器械": "399989.XSHE",       # 医疗器械（归为医疗指数）
        "软件": "000971.XSHG",           # 软件（归为计算机指数）
        "TMT": "000971.XSHG",            # TMT（科技、媒体、通信，归为计算机）
        "消费": "000036.XSHG",           # 消费（含消费ETF、可选消费）
        "医药": "000933.XSHG",           # 医药（含医药ETF、医药卫生）
        "能源": "000928.XSHG",           # 能源（能源ETF、能源化工）
        "金融": "000914.XSHG",           # 金融（金融ETF、金融地产）
        "金融地产": "000914.XSHG",       # 金融地产
        "材料": "000909.XSHG",           # 材料ETF
        "信息技术": "000971.XSHG",       # 信息技术ETF
        "有色": "000819.XSHG",           # 有色ETF（归为有色金属）
        "央企": "000042.XSHG",           # 央企ETF（归为央企指数）
        "民企": "000851.XSHG",           # 民企ETF（归为民企指数）
    
        # 新增：港股/跨境指数
        "恒生": "HSI.HK",                # 恒生ETF（恒生指数）
        "H股": "HSCEI.HK",               # H股ETF（恒生国企指数）
        "恒生中国企业": "HSCEI.HK",      # 恒生中国企业ETF
    
        # 新增：商品/债券指数
        "豆粕": "M.DCE",                 # 豆粕ETF
        "地债": "000012.XSHG",           # 地方债ETF（暂映射国债指数，可替换为专用指数）
        "债券": "000012.XSHG",           # 通用债券指数映射
        "沪深300ETF": "000300.XSHG",
        "上证50ETF": "000016.XSHG",
        "中证500ETF": "000905.XSHG",
        "创业板ETF": "399006.XSHE",
        "科创板50ETF": "000688.XSHG",
        "纳指ETF": "IXIC",
        "黄金ETF": "AU9999.XSGE",
        "医疗ETF": "399989.XSHE",
        "恒生科技ETF": "HSTECH",
        "原油ETF": "CL.NYMEX"
    }
    for code in etf_metrics:
        try:
            etf_name = get_security_info(code).display_name
                # 过滤货币ETF（名称含"货币"或"快线"）
            if "货币" in etf_name or "快线" in etf_name:
                log.info(f"步骤6：过滤货币ETF {code}（名称：{etf_name}）")
                continue  # 跳过货币ETF
         
        
            etf_metrics[code]["name"] = etf_name  # 记录名称用于日志
            matched = False
            for name_key, index_code in etf_name_to_index.items():
                if name_key in etf_name:
                    etf_metrics[code]["跟踪指数"] = index_code
                    matched = True
                    break
            # if not matched:
            #     # log.warning(f"步骤6：{code}（名称：{etf_name}）未匹配到任何指数")
        except Exception as e:
            log.warning(f"步骤6：{code}获取名称失败 → {str(e)}")

    # 转换为DataFrame并筛选有指数的ETF
    etf_metrics_df = pd.DataFrame.from_dict(etf_metrics, orient="index")
    etf_metrics_df_matched = etf_metrics_df.dropna(subset=["跟踪指数"])
    log.info(f"步骤6：匹配指数完成，有指数的ETF数量：{len(etf_metrics_df_matched)}（示例：{etf_metrics_df_matched.index.tolist()[:3]}）")
    if etf_metrics_df_matched.empty:
        log.error("步骤6失败：无匹配到指数的ETF，切换兜底方案")
        return get_etf_leaders_by_volume(context, min_size, min_avg_volume, target_index_map)

    # 步骤7：筛选达标ETF（规模+成交额+沪深市场）
    # 步骤7：筛选达标ETF（原有代码不变）
    etf_filtered = etf_metrics_df_matched[
        (etf_metrics_df_matched["规模(亿元)"] >= min_size) &
        (etf_metrics_df_matched["近30日日均成交额(万元)"] >= min_avg_volume) &
        (etf_metrics_df_matched.index.str.endswith(".XSHG") | etf_metrics_df_matched.index.str.endswith(".XSHE"))
    ]
    # 应用目标指数过滤（原有代码不变）
    if target_index_map and len(target_index_map) > 0:
        target_index_codes = list(target_index_map.values())
        etf_filtered = etf_filtered[etf_filtered["跟踪指数"].isin(target_index_codes)]
        log.info(f"步骤7：应用目标指数过滤后，剩余ETF数量：{len(etf_filtered)}（目标指数：{target_index_codes}）")
    else:
        log.info(f"步骤7：未应用目标指数过滤，达标ETF数量：{len(etf_filtered)}")
    if etf_filtered.empty:
        log.error(f"步骤7失败：无达标ETF，切换兜底方案")
        return get_etf_leaders_by_volume(context, min_size, min_avg_volume, target_index_map)
    
    
    # 新增：步骤7.5 二次筛选（规模前20 → 成交额前10）
    log.info(f"步骤7.5：开始二次筛选（规模前100 → 成交额前80）")
    # 按规模降序取前20
    etf_top20_by_size = etf_filtered.sort_values(by="规模(亿元)", ascending=False).head(100)
    log.info(f"步骤7.5：规模前100的ETF → {etf_top20_by_size.index.tolist()}")
    # 从这20只中按成交额降序取前10
    etf_top10_by_volume = etf_top20_by_size.sort_values(by="近30日日均成交额(万元)", ascending=False).head(80)
    log.info(f"步骤7.5：成交额前80的ETF → {etf_top10_by_volume.index.tolist()}")
    # 更新etf_filtered为这10只，后续分组从这10只中选
    etf_filtered = etf_top10_by_volume
    if etf_filtered.empty:
        log.error("步骤7.5失败：二次筛选后无ETF，切换兜底方案")
        return get_etf_leaders_by_volume(context, min_size, min_avg_volume, target_index_map)   


    
    
    # 步骤8：分组选龙头
    # 步骤8：分组选龙头
    def select_group_leader(group):
        """显式函数：按规模和成交额排序，选择每组龙头并打印日志"""
        index_code = group["跟踪指数"].iloc[0]
        etf_in_group = group.index.tolist()
        log.info(f"步骤8：处理指数[{index_code}]，组内共{len(etf_in_group)}只ETF → {etf_in_group}")
        
        sorted_group = group.sort_values(
            by=["规模(亿元)", "近30日日均成交额(万元)"], 
            ascending=False
        )
        top3 = sorted_group.head(10).index.tolist()
        log.info(f"步骤8：指数[{index_code}]排序前10 → {top3}（按规模/成交额降序）")
        
        leader = sorted_group.iloc[0]
        log.info(
            f"步骤8：指数[{index_code}]选中龙头 → {leader.name} "
            f"（规模：{leader['规模(亿元)']}亿，成交额：{leader['近30日日均成交额(万元)']}万）"
        )
        return leader
    
    # 步骤8：分组选龙头（使用之前定义的select_group_leader函数）
    etf_leaders = etf_filtered.groupby("跟踪指数", group_keys=False).apply(select_group_leader)
    log.info(f"步骤8：分组后原始龙头数量：{len(etf_leaders)}只")
    
    # 新增：若超过10只，按综合得分（规模+成交额）取前10
    if len(etf_leaders) > 10:
        log.info(f"步骤8：龙头数量超过10只，按综合得分取前10")
        # 计算综合得分（规模和成交额各占50%权重，标准化后相加）
        etf_leaders["规模标准化"] = etf_leaders["规模(亿元)"] / etf_leaders["规模(亿元)"].max()
        etf_leaders["成交额标准化"] = etf_leaders["近30日日均成交额(万元)"] / etf_leaders["近30日日均成交额(万元)"].max()
        etf_leaders["综合得分"] = etf_leaders["规模标准化"] * 0.5 + etf_leaders["成交额标准化"] * 0.5
        # 按综合得分降序取前10
        etf_leaders = etf_leaders.sort_values(by="综合得分", ascending=False).head(10)
    
    log.info(f"步骤8：所有指数分组选龙头完成，最终保留{len(etf_leaders)}只龙头ETF")
    final_etf_codes = etf_leaders.index.tolist()
    log.info(f"\n===== 【筛选龙头】成功！最终龙头ETF：{final_etf_codes} =====")
    
    return final_etf_codes
    
    
# ------------------------------------------------------------------------------
























# -------------------- 运行调度函数 --------------------
def initialize(context):

    set_option("avoid_future_data", True)  # 打开防未来函数
    set_option("use_real_price", True)  # 开启动态复权模式(真实价格)
    log.info("初始函数开始运行且全局只运行一次")  # 输出内容到日志 log.info()
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    set_slippage(FixedSlippage(0.0001), type="fund")
    set_slippage(FixedSlippage(0.003), type="stock")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5,
        ),
        type="stock",
    )
    # 设置货币ETF交易佣金0
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0,
            close_commission=0,
            close_today_commission=0,
            min_commission=0,
        ),
        type="mmf",
    )
    # 全局变量
    g.strategys = {}
    g.portfolio_value_proportion = [1]  # 测试版
    g.positions = {i: {} for i in range(len(g.portfolio_value_proportion))}  # 记录每个子策略的持仓股票
    
    # 全天候权重
    g.weights = {}
    
      # 新增：每天9:20更新ETF池
    run_daily(update_etf_pool, "09:20")  # 新增这一行

    if g.portfolio_value_proportion[0] > 0:
        run_daily(etf_rotation_adjust, "09:35")
    # 每日剩余资金购买货币ETF
    run_daily(end_trade, "14:59")
    
    
# 新增：单独的ETF池更新函数
def update_etf_pool(context):
    log.info("\n===== 【ETF池更新】开始（9:20） =====")
    # 获取核心策略实例
    strategy = g.strategys["核心资产轮动策略"]
    
    # 重新计算ETF池
    new_etf_pool = get_etf_leaders_final(
        context=context,
        min_size=10,
        min_avg_volume=5000,
        target_index_map=strategy.target_index_map
    )
    log.info(f"动态筛选的ETF池原始结果：{new_etf_pool}")
    
    # 指数代码转换为ETF代码
    index_to_etf = strategy.get_index_to_etf_map()
    converted_etfs = []
    for code in new_etf_pool:
        converted_code = index_to_etf.get(code, code)
        converted_etfs.append(converted_code)
    log.info(f"指数代码转换后：{converted_etfs}")
    
    # 过滤有效ETF
    valid_etfs = []
    for etf in converted_etfs:
        if etf.endswith((".XSHG", ".XSHE")):
            etf_info = get_security_info(etf)
            if etf_info is not None and etf_info.type == "etf":
                valid_etfs.append(etf)
                log.info(f"保留有效ETF：{etf}（名称：{etf_info.display_name}）")
            else:
                log.warning(f"ETF {etf} 被过滤（非ETF类型或信息无效）")
        else:
            log.warning(f"非沪深ETF {etf} 被过滤")
    log.info(f"过滤后（仅沪深有效ETF）：{valid_etfs}")
    
    # 兜底处理
    if not valid_etfs:
        log.error("过滤后ETF池为空！触发兜底方案")
        valid_etfs = ["510300.XSHG", "510050.XSHG", "159915.XSHE"]
    
    # 更新策略的ETF池
    strategy.etf_pool = valid_etfs
    log.info("===== 【ETF池更新】完成 =====")


def process_initialize(context):
    print("重启程序")
    g.strategys = {
        name: cls(context, index=idx, name=name)
        for name, cls, idx in [
            ("核心资产轮动策略", Etf_Rotation_Strategy, 0),
        ]
    }


# 尾盘处理
def end_trade(context):
    marked = {s for d in g.positions.values() for s in d}
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if stock not in marked:
            price = current_data[stock].last_price
            pos = context.portfolio.positions[stock].total_amount
            if my_order(stock, -pos, price, 0):
                log.info(f"卖出{stock}因送股未记录在持仓中", price, pos)

def my_order(security, vol, price, target_position):
    o = order(security, vol)
    return o


def etf_rotation_adjust(context):
    g.strategys["核心资产轮动策略"].adjust()

# -------------------- 策略基类 --------------------
class Strategy:

    def __init__(self, context, index, name):
        self.context = context
        self.index = index
        self.name = name
        self.stock_sum = 1#买几只
        self.hold_list = []
        self.min_money = 500  # 最小交易额(限制手续费)

    # 获取持仓市值
    def get_total_value(self):
        if not g.positions[self.index]:
            return 0
        return sum(self.context.portfolio.positions[key].price * value for key, value in g.positions[self.index].items())

    # 调仓(targets为字典，key为股票代码，value为目标市值)
    def _adjust(self, targets):
        current_data = get_current_data()

        # 输出信息
        strategy_data = {
            "strategy_name": self.name,
            "strategy_id": self.index,
            "stocks": [{"stock_name": current_data[stock].name, "stock_code": stock, "weight": weight} for stock, weight in targets.items()],
        }

        # log.info(strategy_data)

        # 获取已持有列表
        self.hold_list = list(g.positions[self.index].keys())
        portfolio = self.context.portfolio

        # 获取目标策略市值
        target_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]

        # 清仓被调出的
        for stock in self.hold_list:
            if stock not in targets:
                self.order_target_value_(stock, 0)

        # 先卖出
        for stock, weight in targets.items():
            target = target_value * weight
            price = current_data[stock].last_price
            value = g.positions[self.index].get(stock, 0) * price
            if value - target > max(self.min_money, price * 100):
                self.order_target_value_(stock, target)

        # 后买入
        for stock, weight in targets.items():
            target = target_value * weight
            price = current_data[stock].last_price
            value = g.positions[self.index].get(stock, 0) * price
            if min(target - value, portfolio.available_cash) > max(self.min_money, price * 100):
                self.order_target_value_(stock, target)

    # 自定义下单(涨跌停不交易)
    def order_target_value_(self, security, value):
        current_data = get_current_data()

        # 检查标的是否停牌、涨停、跌停
        if current_data[security].paused:
            log.info(f"{security}: 今日停牌")
            return False

        if current_data[security].last_price == current_data[security].high_limit:
            log.info(f"{security}: 当前涨停")
            return False

        if current_data[security].last_price == current_data[security].low_limit:
            log.info(f"{security}: 当前跌停")
            return False

        # 获取当前标的的价格
        price = current_data[security].last_price

        # 获取当前策略的持仓数量
        current_position = g.positions[self.index].get(security, 0)
        
        # 所有策略中持仓数量
        current_position_all = self.context.portfolio.positions[security].total_amount if security in self.context.portfolio.positions else 0

        # 计算目标持仓数量
        target_position = (int(value / price) // 100) * 100 if price != 0 else 0

        # 计算需要调整的数量
        adjustment = target_position - current_position
        
        target_position_all = current_position_all + adjustment

        # 检查是否当天买入卖出
        closeable_amount = self.context.portfolio.positions[security].closeable_amount if security in self.context.portfolio.positions else 0
        if adjustment < 0 and closeable_amount == 0:
            log.info(f"{security}: 当天买入不可卖出")
            return False

        # 下单并更新持仓
        if adjustment != 0:
            # o = order(security, adjustment)
            o = my_order(security, adjustment, price, target_position_all)
            if o:
                # 更新持仓数量
                filled = o.filled if o.is_buy else -o.filled
                g.positions[self.index][security] = filled + current_position
                # 如果当前持仓为零，移除该证券
                if g.positions[self.index][security] == 0:
                    g.positions[self.index].pop(security, None)
                # 更新持有列表
                self.hold_list = list(g.positions[self.index].keys())
                return True
        return False

    # 检查持仓中曾经涨停但当前未涨停的股票
    def _check(self):
        hold = list(g.positions[self.index].keys())
        if not hold:
            return []
        current_data = get_current_data()
        filtered = self.filter_limitup_stock(hold, 3)
        return [s for s in hold if s not in filtered and current_data[s].last_price < current_data[s].high_limit]

    # 识别无法交易的股票（停牌、涨跌停）
    def filter_untradeable_stock(self, stocks):
        current_data = get_current_data()
        return [
            stock
            for stock in stocks
            if current_data[stock].paused or current_data[stock].last_price in (current_data[stock].high_limit, current_data[stock].low_limit)
        ]

    # 根据调仓逻辑计算最终保留的股票列表
    def get_adjusted_stocks(self, selected, sell):
        fixed = self.filter_untradeable_stock(list(g.positions[self.index].keys()))
        sum = len(self.def_stocks) if selected == self.def_stocks else self.stock_sum - len(fixed)
        return fixed + [s for s in selected if s not in fixed and s not in sell][:sum]

# 核心资产轮动策略
# 核心资产轮动策略
class Etf_Rotation_Strategy(Strategy):
    def __init__(self, context, index, name):
        super().__init__(context, index, name)

        self.stock_sum = 1
        self.m_days = 25  # 动量参考天数
        
        # 修正：确保指数代码对应到正确的ETF名称关键词
        self.target_index_map = {
            # 科创类补充映射
            "科创新材": "000688.XSHG",    # 科创新材 → 科创50指数
            "科创技术": "000688.XSHG",    # 科创技术 → 科创50指数
            "科创五零": "000688.XSHG",    # 科创五零 → 科创50指数
            "芯片科创": "000632.XSHG",    # 芯片科创 → 半导体指数
            "创创ETF": "399006.XSHE",     # 创创ETF → 创业板指
            "科创策略": "000688.XSHG",    # 科创策略 → 科创50指数
            "科创创业": "399296.XSHE",    # 科创创业 → 双创指数
            "科创增强": "000688.XSHG",    # 科创增强 → 科创50指数
            "科100增": "000688.XSHG",     # 科100增 → 科创50指数
            "科创新能": "000688.XSHG",    # 科创新能 → 科创50指数
            "科创指数": "000688.XSHG",    # 科创指数 → 科创50指数
            "科创芯": "000632.XSHG",      # 科创芯 → 半导体指数
                    # 新增宽基指数
            "中证1000": "000852.XSHG",
            "A50": "000016.XSHG",
            "深证100": "399004.XSHE",
            # 新增行业指数
            "光伏": "884045.WI",
            "储能": "884031.WI",
            "基建": "399995.XSHE",
            # 新增港股指数
            "恒生生物科技": "HSCI.BIOTECH",
            "中概互联": "KWEB",
                    # 补充日志中出现的指数类型
            "国证2000": "399303.XSHE",
            "中证2000": "000847.XSHG",
            "半导体": "000632.XSHG",
            "机器人": "884089.WI",
            "信创": "8841619.WI",
            "标普生物": "SPX.BIO",
            "德国DAX": "GDAXI",
            "沙特": "TASI.SR",
            "红利": "000015.XSHG",
            #####################
            "纳指": "IXIC",          # 对应ETF名称含"纳指"或"纳斯达克"
            "日经225": "N225",       # 对应ETF名称含"日经225"
            "德国DAX": "GDAXI",      # 对应ETF名称含"德国DAX"
            "黄金": "AU9999.XSGE",   # 对应ETF名称含"黄金"
            "有色金属": "000819.XSHG",# 对应ETF名称含"有色金属"
            "豆粕": "M.DCE",         # 对应ETF名称含"豆粕"
            "原油": "CL.NYMEX",      # 对应ETF名称含"原油"
            "恒生科技": "HSTECH.HK", # 对应ETF名称含"恒生科技"
            "上证180": "000010.XSHG",# 对应ETF名称含"上证180"
            "创业板指": "399006.XSHE",# 对应ETF名称含"创业板"
            "生物医药": "000933.XSHG",# 对应ETF名称含"生物医药"
            "科创板50": "000688.XSHG" # 对应ETF名称含"科创板50"
        }
        
        self.etf_pool = None  # 延迟初始化

    # 指数代码到对应龙头ETF代码的映射（手动确认有效ETF）
    def get_index_to_etf_map(self):
        return {
            "KWEB": "513050.XSHG",         # 中概互联指数 → 华夏中概互联网ETF（沪深市场）
            "000300.XSHG": "510300.XSHG",  # 沪深300指数 → 沪深300ETF
            "000016.XSHG": "510050.XSHG",  # 上证50指数 → 上证50ETF
            "399006.XSHE": "159915.XSHE",  # 创业板指数 → 创业板ETF
            "000688.XSHG": "588000.XSHG",  # 科创板50指数 → 科创板50ETF
            "IXIC": "513100.XSHG",         # 纳斯达克指数 → 纳指ETF
            "AU9999.XSGE": "518880.XSHG",  # 黄金指数 → 黄金ETF
            "HSTECH.HK": "513130.XSHG",    # 恒生科技指数 → 恒生科技ETF
            "CL.NYMEX": "161129.XSHG",     # 原油指数 → 原油ETF
            "000933.XSHG": "512290.XSHG",  # 生物医药指数 → 生物医药ETF
            # 补充缺失的指数→ETF映射（核心修改）
            # ==================================================
            # 一、核心宽基指数
            # ==================================================
            "000300.XSHG": "510300.XSHG",    # 沪深300指数 → 华泰柏瑞沪深300ETF（规模最大）
            "000016.XSHG": "510050.XSHG",    # 上证50指数 → 华夏上证50ETF（标杆产品）
            "000905.XSHG": "510500.XSHG",    # 中证500指数 → 南方中证500ETF（流动性最佳）
            "000852.XSHG": "159845.XSHE",    # 中证1000指数 → 华夏中证1000ETF（规模领先）
            "000847.XSHG": "159633.XSHE",    # 中证2000指数 → 国泰中证2000ETF（首只产品）
            "399303.XSHE": "159975.XSHE",    # 国证2000指数 → 广发国证2000ETF（代表性产品）
            "399006.XSHE": "159915.XSHE",    # 创业板指 → 易方达创业板ETF（规模最大）
            "399102.XSHE": "159910.XSHE",    # 创业板综指 → 融通创业板综ETF（唯一跟踪产品）
            "000688.XSHG": "588000.XSHG",    # 科创板50指数 → 华夏科创板50ETF（标杆产品）
            "000010.XSHG": "510180.XSHG",    # 上证180指数 → 华安上证180ETF（流动性最佳）
            "399004.XSHE": "159901.XSHE",    # 深证100指数 → 易方达深证100ETF（经典产品）
            "399001.XSHE": "159943.XSHE",    # 深证成指 → 嘉实深证成指ETF（规模领先）
            "399296.XSHE": "159967.XSHE",    # 双创指数（科创创业）→ 南方双创ETF（首只产品）
            "000906.XSHG": "510110.XSHG",    # 中证800指数 → 大成中证800ETF（代表性产品）
    
            # ==================================================
            # 二、行业/主题指数
            # ==================================================
            # 科技类
            "000632.XSHG": "512480.XSHG",    # 半导体指数 → 国联安半导体ETF（龙头）
            "000971.XSHG": "159998.XSHE",    # 计算机指数 → 华夏计算机ETF（规模最大）
            "000909.XSHG": "515880.XSHG",    # 通信指数 → 国泰通信ETF（流动性最佳）
            "8841619.WI": "159891.XSHE",     # 信创指数 → 华夏信创ETF（代表性产品）
            "884089.WI": "562500.XSHG",      # 机器人指数 → 南方机器人ETF（主流产品）
            
            # 周期类
            "000819.XSHG": "512400.XSHG",    # 有色金属指数 → 南方有色金属ETF（龙头）
            "000820.XSHG": "515220.XSHG",    # 煤炭指数 → 国泰煤炭ETF（规模领先）
            "000913.XSHG": "515210.XSHG",    # 钢铁指数 → 国泰钢铁ETF（流动性最佳）
            "000986.XSHG": "516020.XSHG",    # 化工指数 → 华夏化工ETF（代表性产品）
            
            # 消费/医药类
            "000036.XSHG": "159928.XSHE",    # 消费指数 → 汇添富消费ETF（标杆产品）
            "000933.XSHG": "512290.XSHG",    # 生物医药指数 → 国泰生物医药ETF（龙头）
            "399989.XSHE": "512170.XSHG",    # 医疗指数 → 易方达医疗ETF（规模最大）
            
            # 新能源/基建类
            "884045.WI": "515790.XSHG",      # 光伏指数 → 华泰柏瑞光伏ETF（龙头）
            "884031.WI": "159840.XSHE",      # 储能指数 → 鹏华储能ETF（主流产品）
            "000922.XSHG": "159619.XSHE",    # 电力指数 → 广发电力ETF（代表性产品）
            "399995.XSHE": "512680.XSHG",    # 基建指数 → 广发基建工程ETF（龙头）
            
            # 金融类
            "000015.XSHG": "510880.XSHG",    # 红利指数 → 华泰柏瑞红利ETF（经典产品）
            "000916.XSHG": "515980.XSHG",    # 公用事业指数 → 华夏公用事业ETF（流动性佳）
    
            # ==================================================
            # 三、海外指数
            # ==================================================
            "IXIC": "513100.XSHG",           # 纳斯达克100指数 → 国泰纳斯达克100ETF（规模最大）
            "SPX": "513500.XSHG",            # 标普500指数 → 博时标普500ETF（流动性最佳）
            "DJI": "513030.XSHG",            # 道琼斯工业指数 → 华安道琼斯ETF（代表性产品）
            "N225": "513000.XSHG",           # 日经225指数 → 易方达日经225ETF（主流产品）
            "FCHI": "513080.XSHG",           # 法国CAC40指数 → 华安法国CAC40ETF（唯一产品）
            "GDAXI": "513030.XSHG",          # 德国DAX指数 → 华安德国DAXETF（代表性产品）
    
            # ==================================================
            # 四、港股指数
            # ==================================================
            "HSTECH.HK": "513130.XSHG",      # 恒生科技指数 → 华夏恒生科技ETF（龙头）
            "HSCEI.HK": "510900.XSHG",       # 恒生国企指数 → 华夏恒生国企ETF（标杆产品）
            "HSI.HK": "510900.XSHG",         # 恒生指数 → 华夏恒生ETF（规模最大）
            "HSHKDIV.HK": "513690.XSHG",     # 恒生红利指数 → 华泰柏瑞恒生红利ETF（主流）
            "HSCI.BIOTECH": "513290.XSHG",   # 恒生生物科技指数 → 华夏恒生生物科技ETF
    
            # ==================================================
            # 五、商品指数
            # ==================================================
            "AU9999.XSGE": "518880.XSHG",    # 黄金指数 → 华安黄金ETF（规模最大）
            "CL.NYMEX": "161129.XSHG",       # 原油指数 → 易方达原油LOF（主流产品）
            "AG9999.XSGE": "159987.XSHE",    # 白银指数 → 华安白银ETF（代表性产品）
        }

    def filter(self):
        # 先过滤掉非ETF代码
        valid_etfs = [etf for etf in self.etf_pool if etf.endswith((".XSHG", ".XSHE"))]
        data = pd.DataFrame(index=valid_etfs, columns=["annualized_returns", "r2", "score"])
        current_data = get_current_data()
        for etf in valid_etfs:
            try:
                df = attribute_history(etf, self.m_days, "1d", ["close", "high"])
                prices = np.append(df["close"].values, current_data[etf].last_price)

                # 设置参数
                y = np.log(prices)
                x = np.arange(len(y))
                weights = np.linspace(1, 2, len(y))

                # 计算年化收益率
                slope, intercept = np.polyfit(x, y, 1, w=weights)
                data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1

                # 计算R²
                ss_res = np.sum(weights * (y - (slope * x + intercept)) **2)
                ss_tot = np.sum(weights * (y - np.mean(y))** 2)
                data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0

                # 计算得分
                data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]

                # 过滤近3日跌幅超过5%的ETF
                if len(prices) >=4 and min(prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]) < 0.95:
                    data.loc[etf, "score"] = 0
            except:
                data.loc[etf, "score"] = 0

        # 过滤ETF，并按得分降序排列
        data = data.query("0 < score < 6").sort_values(by="score", ascending=False)
        return data.index.tolist()

    # 调仓方法（修复后）
    def adjust(self):
        log.info("\n===== 【核心策略】开始调仓 =====")
        # 不再重新计算ETF池，直接使用早上9:20更新的结果
        if not self.etf_pool:
            log.warning("ETF池为空，不调仓")
            return
        
        log.info(f"开始计算动量得分（ETF池共{len(self.etf_pool)}只）")
        targets = self.filter()[:self.stock_sum]
        log.info(f"动量得分最高的{self.stock_sum}只ETF：{targets}")
        
        if targets:
            self._adjust({etf: round(1 / len(targets), 3) for etf in targets})
        else:
            log.warning("无有效目标ETF，不调仓")
        log.info("===== 【核心策略】调仓结束 =====\n")