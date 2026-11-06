# Clone from JoinQuant
# postId: 9342722ec41799b442f203262926acbb
# backtestId: 5e00f28273461ab12dcba33d29e0dbdd
# title: 机器学习排序模型的 A 股主板小市值量化选股策略

# ============================================================
# ss_v4 小市值 ML 选股策略（聚宽回测/模拟盘）
#
# 策略逻辑：
#   - 股票池：A股主板小市值（60xxxx/00xxxx，剔除ST/创业板/科创板/北交所）
#   - 选股：LGBMRanker 截面排序 + 多维因子（价值/质量/动量/波动率）
#   - 调仓：周频（每周一 9:30）
#   - 风控：趋势过滤（MA20/MA60）+ ATR 动态止损 + Buy-Hold 规则
#   - 牛熊通用：熊市通过趋势过滤自动降仓（不切换策略）
#
# 使用前提：
#   - 已将 ss_v4_model.json 上传到聚宽研究环境根目录
#   - 如模型未上传，自动降级为基本面规则选股
#
# 来源：
#   AQR 2024 "Virtue of Complexity"（复杂模型 Sharpe 提升 50-100%）
#   中国证券报 2025 排序学习（夏普提升 66%，换手率降低 46%）
#   Faber 2007/2013 趋势过滤（MA 三级信号）
#   Robeco 2023 Buy-Hold 成本缓解
#   Moreira-Muir 2016 波动率管理仓位
# ============================================================

from jqdata import *
import numpy as np
import pandas as pd
import json
import os
import tempfile
import datetime

# ============================================================
# 路径常量（与训练脚本完全一致）
# ============================================================
STRATEGY_PREFIX = 'ss'
STRATEGY_VERSION = 'v4'
MODEL_FILE = f'{STRATEGY_PREFIX}_{STRATEGY_VERSION}_model.json'

# ============================================================
# 策略参数（来源：strategy_profile_smallcap.md 二、核心方法论参数配置）
# ============================================================
MAX_POSITIONS = 5           # 最大持仓数（集中持仓，高弹性）
MAX_INDUSTRY_COUNT = 2      # 单行业最大持仓数
MAX_SINGLE_WEIGHT = 0.30    # 单股最大权重 30%
BUY_CUTOFF_PCT = 0.05       # 买入门槛：排名前 5%（新建仓）
SELL_CUTOFF_PCT = 0.30      # 卖出门槛：跌出前 30% 才卖（Buy-Hold 规则）
RANKER_WEIGHT = 0.6         # LGBMRanker 集成权重 60%，Ridge 40%

# 风控参数
ATR_STOP_MULTIPLIER = 2.0   # ATR 止损倍数
HARD_STOP_PCT = -0.10       # 硬止损 -10%
TRAILING_TRIGGER = 0.12     # 移动止盈触发：浮盈 > 12%
TRAILING_STOP_PCT = 0.05    # 从最高点回落 5% 止盈
MIN_HOLD_DAYS = 2           # 最短持仓 2 天
TREND_INDEX = '000300.XSHG' # 趋势参考指数（沪深300）

# 因子族映射（用于调试）
FACTOR_FAMILY_MAP = {
    'ep': '价值', 'bp': '价值', 'sp': '价值', 'cfp': '价值',
    'ebit_ev': '价值', 'composite_value': '价值',
    'roe': '质量', 'roa': '质量', 'acca': '质量',
    'ocf_to_debt': '质量', 'debt_ratio': '质量',
    'gross_margin': '质量', 'net_profit_margin': '质量',
    'mom_5d': '动量', 'mom_20d': '动量', 'mom_60d': '动量',
    'mom_120d': '动量', 'reversal_5_20': '动量',
    'industry_rel_mom_20d': '动量',
    'vol_20d': '波动率', 'vol_60d': '波动率',
    'downside_vol_20d': '波动率', 'vol_ratio': '波动率',
    'amihud_20d': '流动性', 'turnover_20d': '流动性',
    'vol_compression': '流动性',
    'mktcap_accel': '创新', 'earnings_surprise': '创新',
    'price_efficiency': '创新',
}

# ============================================================
# 股票池函数（与数据采集脚本完全一致，复制粘贴）
# ============================================================
def get_stock_pool(date):
    """
    A股主板股票池（强制过滤）
    ⚠️ 此函数与 ss_v4_数据采集.py 完全一致，不得修改
    """
    all_stocks = get_all_securities('stock', date)
    stocks = [s for s in all_stocks.index
              if s.startswith('60') or s.startswith('00')]
    try:
        st_info = get_extras('is_st', stocks, end_date=date, count=1).iloc[0]
        stocks = [s for s in stocks if not st_info.get(s, True)]
    except:
        pass
    stocks = [s for s in stocks
              if 'ST' not in all_stocks.loc[s, 'display_name']]
    stocks = [s for s in stocks
              if (pd.Timestamp(date) - pd.Timestamp(all_stocks.loc[s, 'start_date'])).days > 90]
    return stocks


def get_smallcap_pool(date, top_pct=0.50):
    """
    小市值股票池
    ⚠️ 此函数与 ss_v4_数据采集.py 完全一致，不得修改
    """
    stocks = get_stock_pool(date)
    if not stocks:
        return []
    q = query(valuation.code, valuation.circulating_market_cap).filter(
        valuation.code.in_(stocks))
    df = get_fundamentals(q, date=str(date))
    if df.empty:
        return stocks
    threshold = df['circulating_market_cap'].quantile(top_pct)
    small_stocks = df[df['circulating_market_cap'] <= threshold]['code'].tolist()
    return small_stocks


# ============================================================
# 因子计算函数（与数据采集脚本完全一致，复制粘贴）
# ⚠️ 训练/回测一致性：此函数不得与数据采集脚本有任何差异
# ============================================================
def calc_factors(stock_list, date):
    """
    计算所有因子
    ⚠️ 此函数与 ss_v4_数据采集.py 完全一致，不得修改
    来源：factor_engineering_v2.md 一、因子体系设计
    """
    if not stock_list:
        return pd.DataFrame()
    date_str = str(date)
    factors = pd.DataFrame(index=stock_list)

    # 价值因子族
    try:
        q = query(
            valuation.code, valuation.pe_ratio, valuation.pb_ratio,
            valuation.ps_ratio, valuation.pcf_ratio,
            valuation.market_cap, valuation.circulating_market_cap,
            income.operating_profit,   # 用于计算 EBIT/EV
        ).filter(valuation.code.in_(stock_list))
        val_df = get_fundamentals(q, date=date_str).set_index('code')
        factors['ep'] = (1.0 / val_df['pe_ratio'].replace(0, np.nan)).reindex(stock_list)
        factors['bp'] = (1.0 / val_df['pb_ratio'].replace(0, np.nan)).reindex(stock_list)
        factors['sp'] = (1.0 / val_df['ps_ratio'].replace(0, np.nan)).reindex(stock_list)
        factors['cfp'] = (1.0 / val_df['pcf_ratio'].replace(0, np.nan)).reindex(stock_list)
        factors['log_mktcap'] = np.log(val_df['circulating_market_cap'].replace(0, np.nan)).reindex(stock_list)
        # EBIT/EV（用营业利润近似 EBIT，市值近似 EV）
        factors['ebit_ev'] = (
            val_df['operating_profit'] /
            (val_df['market_cap'].replace(0, np.nan) * 1e8)
        ).reindex(stock_list)
        for col in ['ep', 'bp', 'sp']:
            z = (factors[col] - factors[col].mean()) / (factors[col].std() + 1e-8)
            factors[col + '_z'] = z
        factors['composite_value'] = factors[['ep_z', 'bp_z', 'sp_z']].mean(axis=1)
        factors.drop(columns=['ep_z', 'bp_z', 'sp_z'], inplace=True)
    except Exception as e:
        log.warn(f"价值因子计算失败: {e}")

    try:
        q2 = query(
            indicator.code, indicator.roe, indicator.roa,
            indicator.gross_profit_margin, indicator.net_profit_margin,
        ).filter(indicator.code.in_(stock_list))
        ind_df = get_fundamentals(q2, date=date_str).set_index('code')
        factors['roe'] = ind_df['roe'].reindex(stock_list)
        factors['roa'] = ind_df['roa'].reindex(stock_list)
        factors['gross_margin'] = ind_df['gross_profit_margin'].reindex(stock_list)
        factors['net_profit_margin'] = ind_df['net_profit_margin'].reindex(stock_list)
    except Exception as e:
        log.warn(f"质量因子计算失败: {e}")

    # ACCA + OCF/负债 + 资产负债率（合并一次 query）
    # ⚠️ indicator 表无 ocf_to_debt / debt_to_equity_ratio，改用 balance/cash_flow 手动计算
    try:
        q3 = query(
            balance.code,
            balance.total_assets,
            balance.total_liability,
            cash_flow.net_operate_cash_flow,
            income.net_profit,
        ).filter(balance.code.in_(stock_list))
        acc_df = get_fundamentals(q3, date=date_str).set_index('code')
        acca = (acc_df['net_profit'] - acc_df['net_operate_cash_flow']) / \
               (acc_df['total_assets'].replace(0, np.nan))
        factors['acca'] = -acca.reindex(stock_list)
        factors['ocf_to_debt'] = (
            acc_df['net_operate_cash_flow'] /
            acc_df['total_liability'].replace(0, np.nan)
        ).reindex(stock_list)
        factors['debt_ratio'] = -(acc_df['total_liability'] /
                                   acc_df['total_assets'].replace(0, np.nan)
                                   ).reindex(stock_list)
    except Exception as e:
        log.warn(f"ACCA/OCF/负债率因子计算失败: {e}")

    try:
        prices = get_price(stock_list, end_date=date_str, count=130,
                           fields=['close'], panel=False)
        if not prices.empty:
            close_pivot = prices.pivot(index='time', columns='code', values='close')
            def safe_mom(n):
                if len(close_pivot) > n:
                    return (close_pivot.iloc[-1] / close_pivot.iloc[-n] - 1).reindex(stock_list)
                return pd.Series(np.nan, index=stock_list)
            factors['mom_5d'] = safe_mom(5)
            factors['mom_20d'] = safe_mom(20)
            factors['mom_60d'] = safe_mom(60)
            factors['mom_120d'] = safe_mom(120)
            if len(close_pivot) > 20:
                factors['reversal_5_20'] = (
                    close_pivot.iloc[-1] / close_pivot.iloc[-5] - 1
                ).reindex(stock_list) - (
                    close_pivot.iloc[-1] / close_pivot.iloc[-20] - 1
                ).reindex(stock_list)
            if 'mom_20d' in factors.columns:
                try:
                    ind_map = get_industry(stock_list, date=date_str)
                    ind_series = pd.Series({
                        s: ind_map.get(s, {}).get('sw_l1', {}).get('industry_name', 'unknown')
                        for s in stock_list})
                    ind_med = factors['mom_20d'].groupby(ind_series).transform('median')
                    factors['industry_rel_mom_20d'] = factors['mom_20d'] - ind_med
                except:
                    pass
    except Exception as e:
        log.warn(f"动量因子计算失败: {e}")

    try:
        prices2 = get_price(stock_list, end_date=date_str, count=65,
                            fields=['close', 'high', 'low', 'volume', 'money'],
                            panel=False)
        if not prices2.empty:
            pv = prices2.pivot(index='time', columns='code', values='close')
            vv = prices2.pivot(index='time', columns='code', values='volume')
            mv = prices2.pivot(index='time', columns='code', values='money')
            ret = pv.pct_change().dropna()
            if len(ret) >= 20:
                factors['vol_20d'] = ret.iloc[-20:].std().reindex(stock_list)
            if len(ret) >= 60:
                factors['vol_60d'] = ret.iloc[-60:].std().reindex(stock_list)
            if len(ret) >= 20:
                factors['vol_ratio'] = (ret.iloc[-5:].std() / (ret.iloc[-20:].std() + 1e-8)).reindex(stock_list)
                down_ret = ret.iloc[-20:].clip(upper=0)
                factors['downside_vol_20d'] = down_ret.std().reindex(stock_list)
                vol_5 = ret.iloc[-5:].std()
                vol_20 = ret.iloc[-20:].std()
                factors['vol_compression'] = (vol_5 / (vol_20 + 1e-8)).reindex(stock_list)
            if len(pv) >= 20 and not mv.empty:
                amihud = (ret.abs() / (mv.iloc[-20:] + 1e-8)).mean()
                factors['amihud_20d'] = amihud.reindex(stock_list)
            if not vv.empty and len(vv) >= 20:
                factors['turnover_20d'] = vv.iloc[-20:].mean().reindex(stock_list)
    except Exception as e:
        log.warn(f"波动率/流动性因子计算失败: {e}")

    try:
        if 'mom_20d' in factors.columns and 'mom_5d' in factors.columns:
            # 用价格动量差近似市值加速度：5日动量 - 20日动量
            factors['mktcap_accel'] = factors['mom_5d'] - factors['mom_20d']
    except Exception as e:
        log.warn(f"市值加速度因子计算失败: {e}")

    try:
        if 'roe' in factors.columns:
            prev_date = (pd.Timestamp(date) - pd.DateOffset(months=3)).strftime('%Y-%m-%d')
            q_prev = query(indicator.code, indicator.roe).filter(indicator.code.in_(stock_list))
            prev_df = get_fundamentals(q_prev, date=prev_date).set_index('code')
            if not prev_df.empty:
                factors['earnings_surprise'] = (factors['roe'] - prev_df['roe'].reindex(stock_list))
    except Exception as e:
        log.warn(f"盈利惊喜因子计算失败: {e}")

    try:
        if 'mom_20d' in factors.columns:
            factors['price_efficiency'] = -factors['mom_20d']
    except:
        pass

    if 'log_mktcap' in factors.columns:
        factors = factors.drop(columns=['log_mktcap'])

    return factors


# ============================================================
# 三层偏差修正（与数据采集脚本完全一致）
# ============================================================
def mad_winsorize(series, n=5):
    """MAD 去极值"""
    median = series.median()
    mad = (series - median).abs().median()
    upper = median + n * 1.4826 * mad
    lower = median - n * 1.4826 * mad
    return series.clip(lower=lower, upper=upper)


def apply_bias_correction_realtime(factor_df, stock_list, date):
    """
    实时三层偏差修正（回测时截面计算）
    ⚠️ 必须与训练时的偏差修正完全一致
    来源：strategy_profile_smallcap.md 三、改进2：三层偏差修正
    """
    from sklearn.linear_model import LinearRegression

    corrected = pd.DataFrame(index=factor_df.index)

    # 获取行业和市值（用于中性化）
    try:
        ind_map = get_industry(stock_list, date=str(date))
        ind_series = pd.Series({
            s: ind_map.get(s, {}).get('sw_l1', {}).get('industry_code', 'unknown')
            for s in stock_list
        })
        ind_dummies = pd.get_dummies(ind_series, prefix='ind').astype(float)
    except:
        ind_dummies = pd.DataFrame(index=stock_list)

    try:
        q = query(valuation.code, valuation.circulating_market_cap).filter(
            valuation.code.in_(stock_list))
        mc_df = get_fundamentals(q, date=str(date)).set_index('code')
        log_mc = np.log(mc_df['circulating_market_cap'].replace(0, np.nan)).reindex(stock_list)
    except:
        log_mc = pd.Series(np.nan, index=stock_list)

    X_parts = []
    if not ind_dummies.empty:
        X_parts.append(ind_dummies)
    if log_mc.notna().sum() > 10:
        X_parts.append(log_mc.rename('log_mc').to_frame())
    X_reg = pd.concat(X_parts, axis=1, sort=False).reindex(stock_list).fillna(0) if X_parts else None

    for col in factor_df.columns:
        series = factor_df[col].copy()

        # Step 1: MAD 去极值
        series = mad_winsorize(series, n=5)

        # Step 2: 行业 + 市值中性化
        if X_reg is not None:
            valid = series.notna() & X_reg.notna().all(axis=1)
            if valid.sum() >= 30:
                try:
                    reg = LinearRegression(fit_intercept=True)
                    reg.fit(X_reg[valid].values, series[valid].values)
                    residual = series.copy()
                    residual[valid] = series[valid] - reg.predict(X_reg[valid].values)
                    series = residual
                except:
                    pass

        # Step 3: Z-score 标准化
        mean = series.mean()
        std = series.std()
        if std > 1e-8:
            series = (series - mean) / std

        corrected[col] = series

    return corrected


# ============================================================
# 模型集成预测
# ============================================================
def ensemble_predict(X):
    """
    LGBMRanker + Ridge 集成预测（纯 numpy，无版本依赖）
    来源：local_training.md 五、聚宽策略侧加载 JSON 模型
    """
    # Ranker 预测
    ranker_pred = np.zeros(len(X))
    total_w = 0
    for m in g.wf_models:
        pred = m['booster'].predict(X)
        ranker_pred += m['weight'] * pred
        total_w += m['weight']
    ranker_pred /= (total_w + 1e-8)
    r_mean, r_std = ranker_pred.mean(), ranker_pred.std()
    ranker_std = (ranker_pred - r_mean) / (r_std + 1e-8) if r_std > 0 else ranker_pred

    # Ridge 预测（纯矩阵乘法，无 sklearn 依赖）
    ridge_pred = X @ g.ridge_coef + g.ridge_intercept
    rd_mean, rd_std = ridge_pred.mean(), ridge_pred.std()
    ridge_std = (ridge_pred - rd_mean) / (rd_std + 1e-8) if rd_std > 0 else ridge_pred

    return RANKER_WEIGHT * ranker_std + (1 - RANKER_WEIGHT) * ridge_std


# ============================================================
# 趋势过滤（Faber 2007/2013）
# ============================================================
def calc_trend_position(end_date=None):
    """
    MA20/MA60 三级趋势信号 → 仓位 0%/50%/80%/100%
    牛熊通用，替代原有牛熊切换逻辑
    来源：strategy_profile_smallcap.md 二、风控仓位逻辑
    """
    try:
        if end_date is None:
            end_date = str(datetime.date.today())
        idx_prices = get_price(TREND_INDEX, end_date=str(end_date),
                               count=130, fields=['close'])
        if idx_prices.empty or len(idx_prices) < 60:
            return 1.0
        close = idx_prices['close']
        ma20 = close.iloc[-20:].mean()
        ma60 = close.iloc[-60:].mean()
        current = close.iloc[-1]

        # 三级信号
        signals = 0
        if current > ma20:
            signals += 1
        if current > ma60:
            signals += 1
        if ma20 > ma60:
            signals += 1

        # 信号数 → 仓位
        position_map = {0: 0.0, 1: 0.50, 2: 0.80, 3: 1.0}
        return position_map.get(signals, 1.0)
    except:
        return 1.0


# ============================================================
# 降级选股（模型加载失败时使用）
# ============================================================
def fallback_stock_selection(stock_list, date):
    """
    基本面规则选股（降级方案）：ROE>5% + PE<50 + 小市值
    来源：需求4.6
    """
    try:
        q = query(
            valuation.code,
            valuation.pe_ratio,
            valuation.circulating_market_cap,
            indicator.roe,
        ).filter(
            valuation.code.in_(stock_list),
            indicator.roe > 5,
            valuation.pe_ratio > 0,
            valuation.pe_ratio < 50,
        )
        df = get_fundamentals(q, date=str(date))
        if df.empty:
            return stock_list[:MAX_POSITIONS]
        # 按市值升序（小市值优先）
        df = df.sort_values('circulating_market_cap')
        return df['code'].head(MAX_POSITIONS).tolist()
    except:
        return stock_list[:MAX_POSITIONS]


# ============================================================
# initialize
# ============================================================
def initialize(context):
    # 基础设置
    set_benchmark('399101.XSHE')   # 中证1000
    set_option('use_real_price', True)
    if context.run_params.type == 'backtest':
        set_option('avoid_future_data', True)

    set_slippage(FixedSlippage(0.02))
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.0005,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5
    ), type='stock')

    # 加载 JSON 格式模型（无版本依赖）
    g.model_loaded = False
    try:
        import lightgbm as lgb
        model_data = json.loads(read_file(MODEL_FILE))
        g.wf_models = model_data['wf_models']
        g.ridge_coef = np.array(model_data['ridge_coef'])
        g.ridge_intercept = float(model_data['ridge_intercept'])
        g.feature_list = model_data['feature_names']
        g.config = model_data['config']

        # ⭐ 预加载 lgb.Booster（写临时文件，兼容聚宽旧版 LightGBM 2.2.2）
        for i, m in enumerate(g.wf_models):
            tmp_path = os.path.join(tempfile.gettempdir(), f'ss_v4_lgb_{i}.txt')
            with open(tmp_path, 'w') as f:
                f.write(m['model_str'])
            m['booster'] = lgb.Booster(model_file=tmp_path)

        g.model_loaded = True
        log.info(f"✅ 模型加载成功: 特征{len(g.feature_list)}个, WF模型{len(g.wf_models)}个")
    except Exception as e:
        log.warn(f"⚠️ 模型加载失败: {e}，将使用基本面规则降级选股")
        g.wf_models = []
        g.ridge_coef = None
        g.ridge_intercept = None
        g.feature_list = []

    # 状态变量
    g.hold_days = {}          # 持仓天数
    g.highest_prices = {}     # 持仓最高价（移动止盈用）
    g.yesterday_HL_list = []  # 昨日涨停股票
    g.last_scores = {}        # 上次调仓的得分（Buy-Hold 用）

    # 定时任务
    run_daily(prepare_daily, '9:05')
    run_weekly(weekly_rebalance, 1, '9:30')   # 每周一 9:30 调仓
    run_daily(intraday_risk_check, '14:00')   # 盘中风控
    run_daily(check_limit_up, '14:10')        # 涨停检查
    run_daily(update_state, '14:50')          # 更新状态


# ============================================================
# 每日准备
# ============================================================
def prepare_daily(context):
    """更新涨停列表"""
    try:
        current_positions = list(context.portfolio.positions.keys())
        if not current_positions:
            g.yesterday_HL_list = []
            return
        prices = get_price(current_positions,
                           end_date=str(context.previous_date),
                           count=1,
                           fields=['close', 'high_limit'],
                           panel=False)
        if prices.empty:
            g.yesterday_HL_list = []
            return
        hl = prices[prices['close'] >= prices['high_limit']]['code'].tolist()
        g.yesterday_HL_list = hl
    except:
        g.yesterday_HL_list = []


# ============================================================
# 周频调仓（核心）
# ============================================================
def weekly_rebalance(context):
    """
    每周一 9:30 调仓
    来源：strategy_profile_smallcap.md 二、调度任务
    """
    date = context.previous_date
    log.info(f"📅 周频调仓: {date}")

    # 1. 趋势过滤仓位（牛熊通用）
    trend_position = calc_trend_position(end_date=str(date))
    log.info(f"  趋势过滤仓位: {trend_position:.0%}")

    if trend_position == 0:
        log.info("  ⚠️ 趋势信号为0，清仓等待")
        for stock in list(context.portfolio.positions.keys()):
            if context.portfolio.positions[stock].closeable_amount > 0:
                order_target(stock, 0)
        return

    # 2. 获取股票池
    stock_list = get_smallcap_pool(date)
    if len(stock_list) < 20:
        log.warn(f"  ⚠️ 股票池过小 ({len(stock_list)} 只)，跳过调仓")
        return

    # 3. 计算因子 + 三层偏差修正 + 模型预测
    if g.model_loaded:
        try:
            factor_df = calc_factors(stock_list, date)
            if factor_df.empty:
                raise ValueError("因子计算返回空")

            # 对齐特征列（与训练时一致）
            for col in g.feature_list:
                if col not in factor_df.columns:
                    factor_df[col] = np.nan
            factor_df = factor_df[g.feature_list]

            # 三层偏差修正
            corrected_df = apply_bias_correction_realtime(factor_df, stock_list, date)

            # 模型预测
            X = corrected_df.fillna(0).values
            X = np.nan_to_num(X)
            scores = ensemble_predict(X)
            score_series = pd.Series(scores, index=corrected_df.index)

        except Exception as e:
            log.warn(f"  ⚠️ ML 预测失败: {e}，降级为规则选股")
            g.model_loaded = False
            score_series = None
    else:
        score_series = None

    # 4. 选股
    if score_series is not None:
        # ML 选股：截面排名
        rank_pct = score_series.rank(pct=True)
        g.last_scores = score_series.to_dict()

        # Buy-Hold 规则（Robeco 2023）
        current_positions = list(context.portfolio.positions.keys())
        target_list = []

        # 已持有股票：排名跌出前 SELL_CUTOFF_PCT 才卖
        hold_keep = [s for s in current_positions
                     if s in rank_pct.index and rank_pct[s] >= (1 - SELL_CUTOFF_PCT)]

        # 新买入：排名前 BUY_CUTOFF_PCT
        buy_candidates = rank_pct[rank_pct >= (1 - BUY_CUTOFF_PCT)].sort_values(ascending=False)

        # 行业约束
        target_list = list(hold_keep)
        ind_map = {}
        try:
            ind_info = get_industry(stock_list, date=str(date))
            for s in stock_list:
                ind_map[s] = ind_info.get(s, {}).get('sw_l1', {}).get('industry_name', 'unknown')
        except:
            pass

        ind_count = {}
        for s in target_list:
            ind = ind_map.get(s, 'unknown')
            ind_count[ind] = ind_count.get(ind, 0) + 1

        for s in buy_candidates.index:
            if len(target_list) >= MAX_POSITIONS:
                break
            if s in target_list:
                continue
            ind = ind_map.get(s, 'unknown')
            if ind_count.get(ind, 0) < MAX_INDUSTRY_COUNT:
                target_list.append(s)
                ind_count[ind] = ind_count.get(ind, 0) + 1

        if not target_list:
            target_list = buy_candidates.index[:MAX_POSITIONS].tolist()

    else:
        # 降级：基本面规则选股
        target_list = fallback_stock_selection(stock_list, date)
        log.info(f"  📋 降级选股: {target_list}")

    log.info(f"  目标持仓 ({len(target_list)} 只): {target_list}")

    # 5. 计算目标仓位
    total_value = context.portfolio.total_value * trend_position
    n = len(target_list)
    if n == 0:
        return

    # 等权分配（可选：按信号强度加权）
    weight_per_stock = min(MAX_SINGLE_WEIGHT, 1.0 / n)

    # 6. 先卖出不在目标列表的股票
    for stock in list(context.portfolio.positions.keys()):
        if stock not in target_list:
            pos = context.portfolio.positions[stock]
            if pos.closeable_amount <= 0:
                continue
            if stock in g.yesterday_HL_list:
                continue
            if g.hold_days.get(stock, 999) < MIN_HOLD_DAYS:
                continue
            order_target(stock, 0)
            log.info(f"  卖出: {stock}")

    # 7. 买入目标股票
    for stock in target_list:
        target_value = total_value * weight_per_stock
        order_target_value(stock, target_value)
        if stock not in context.portfolio.positions or \
           context.portfolio.positions[stock].total_amount == 0:
            g.hold_days[stock] = 0


# ============================================================
# 盘中风控（ATR 止损 + 移动止盈）
# ============================================================
def intraday_risk_check(context):
    """
    ATR 动态止损 + 移动止盈
    来源：strategy_profile_smallcap.md 二、风控参数
    """
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.closeable_amount <= 0 or pos.avg_cost <= 0:
            continue

        current_price = pos.price
        avg_cost = pos.avg_cost
        pnl_pct = (current_price - avg_cost) / avg_cost

        # 硬止损
        if pnl_pct < HARD_STOP_PCT:
            log.info(f"🛑 [{stock}] 硬止损: 亏损{pnl_pct:.2%}")
            order_target(stock, 0)
            continue

        # ATR 动态止损
        try:
            prices = get_price(stock, end_date=str(context.current_dt.date()),
                               count=20, fields=['close', 'high', 'low'])
            if len(prices) >= 14:
                tr = np.maximum(
                    prices['high'] - prices['low'],
                    np.maximum(
                        abs(prices['high'] - prices['close'].shift(1)),
                        abs(prices['low'] - prices['close'].shift(1))
                    )
                ).dropna()
                atr = tr.mean()
                stop_price = avg_cost - ATR_STOP_MULTIPLIER * atr
                hard_stop = avg_cost * (1 + HARD_STOP_PCT)
                stop_price = max(stop_price, hard_stop)

                if current_price < stop_price:
                    log.info(f"⚠️ [{stock}] ATR止损: {current_price:.2f} < {stop_price:.2f}")
                    order_target(stock, 0)
                    continue
        except:
            pass

        # 移动止盈
        if stock not in g.highest_prices:
            g.highest_prices[stock] = current_price
        else:
            g.highest_prices[stock] = max(g.highest_prices[stock], current_price)

        if pnl_pct > TRAILING_TRIGGER:
            trail_price = g.highest_prices[stock] * (1 - TRAILING_STOP_PCT)
            if current_price < trail_price:
                log.info(f"📈 [{stock}] 移动止盈: 最高{g.highest_prices[stock]:.2f}, "
                         f"当前{current_price:.2f}")
                order_target(stock, 0)


# ============================================================
# 涨停检查
# ============================================================
def check_limit_up(context):
    """检查持仓中的涨停股票，记录到 g.yesterday_HL_list"""
    try:
        current_positions = list(context.portfolio.positions.keys())
        if not current_positions:
            return
        prices = get_price(current_positions,
                           end_date=str(context.current_dt.date()),
                           count=1,
                           fields=['close', 'high_limit'],
                           panel=False)
        if prices.empty:
            return
        hl = prices[prices['close'] >= prices['high_limit']]['code'].tolist()
        g.yesterday_HL_list = hl
        if hl:
            log.info(f"  涨停股票: {hl}")
    except:
        pass


# ============================================================
# 更新状态
# ============================================================
def update_state(context):
    """更新持仓天数和最高价"""
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.total_amount > 0:
            g.hold_days[stock] = g.hold_days.get(stock, 0) + 1
            current_price = pos.price
            if stock not in g.highest_prices:
                g.highest_prices[stock] = current_price
            else:
                g.highest_prices[stock] = max(g.highest_prices[stock], current_price)

    # 清理已卖出股票的状态
    current_positions = set(context.portfolio.positions.keys())
    for stock in list(g.hold_days.keys()):
        if stock not in current_positions:
            del g.hold_days[stock]
    for stock in list(g.highest_prices.keys()):
        if stock not in current_positions:
            del g.highest_prices[stock]
