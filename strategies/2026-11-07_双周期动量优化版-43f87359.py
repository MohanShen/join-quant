# Clone from JoinQuant
# postId: 43f873591f38d3b0fbb65ba232f50354
# backtestId: 3344a0ca4412f56a739b4468131c6dbb
# title: 双周期动量优化版

# 克隆自聚宽文章：https://www.joinquant.com/post/58963
# 标题：质疑动量 、理解动量 、Allin动量
# 作者：O_iX
# 改造：固定止损(11天冷却) + 下行波动率仓位(TARGET_VOL=0.12) + 质量因子加权(q=0.005, 双限制防碎单) v4.5
# v4.5 新增：显式成本设置（滑点0.3% + 佣金万0.5 + 最低5元，不免五）

from jqdata import *
from jqfactor import get_factor_values
import datetime
import math
from scipy.optimize import minimize
import redis
import numpy as np
import pandas as pd
import json
import time


# ==================== 固定止损配置 ====================
ENABLE_FIXED_STOP   = True
FIXED_STOP_FULL     = -0.06
FIXED_STOP_NORMAL   = -0.08
COOLDOWN_TRADE_DAYS = 11
# =====================================================

# ==================== 下行波动率仓位调节配置 ====================
ENABLE_DOWNSIDE_VOL      = True
TARGET_VOL               = 0.12
VOL_WINDOW               = 40
MIN_POSITION_RATIO       = 0.3
MAX_POSITION_RATIO       = 1.0
POSITION_RATIO_SMOOTH    = 0.88
# ================================================================

# ==================== 质量因子加权配置 ====================
ENABLE_QUALITY_ADJUST = True
QUALITY_VOL_WINDOW    = 20
QUALITY_SCALE_MIN     = 0.5
QUALITY_SCALE_MAX     = 1.5
QUALITY_EXCLUDE_SECS  = ["511880.XSHG", "511090.XSHG"]
QUALITY_NUMERATOR     = 0.005     # ★ 推荐值：0.005 / vol（回测 Sharpe 1.651，收益 995.57%）
WEIGHT_CHANGE_THRESHOLD = 0.03
# ==========================================================

# ==================== 交易成本配置（v4.5 新增） ====================
# 滑点：0.3%（跨境ETF流动性差异大，0.2%偏乐观，0.3%为中性合理值）
#       压力测试可改 0.005（0.5%），保守估计跨境ETF实盘滑点
SLIPPAGE_RATE = 0.003

# 佣金：万0.5，最低5元（不免五）
#       ETF 无印花税，仅佣金
COMMISSION_RATE = 0.00005      # 万0.5
MIN_COMMISSION  = 5            # 最低5元，不免五
# ================================================================


# -------------------- Redis配置 --------------------
REDIS_CONFIG = {
    "host": "...", "port": 123, "username": "...", "password": "...",
}


def get_redis_connection() -> redis.Redis:
    try:
        conn = redis.Redis(
            host=REDIS_CONFIG["host"], port=REDIS_CONFIG["port"], password=None,
            decode_responses=True, socket_connect_timeout=3, socket_timeout=5,
        )
        auth_response = conn.execute_command("AUTH", REDIS_CONFIG["username"], REDIS_CONFIG["password"])
        if not auth_response:
            raise redis.AuthenticationError(f"Redis ACL认证失败: {auth_response}")
        return conn
    except redis.AuthenticationError as e:
        log.error(f"Redis认证失败: {e}")
        raise
    except redis.ConnectionError as e:
        log.error(f"Redis连接失败: {e}")
        raise
    except Exception as e:
        log.error(f"未知错误: {e}")
        raise


def set_strategy_data(strategy_name, strategy_data):
    r = None
    try:
        r = get_redis_connection()
        serialized_data = json.dumps(strategy_data, ensure_ascii=False)
        r.set(strategy_name, serialized_data)
        log.info(f"策略 {strategy_name} 数据推送成功")
        return True
    except Exception as e:
        log.error(f"操作失败: {e}")
        return False
    finally:
        if r is not None:
            try:
                if hasattr(r, "connection") and r.connection:
                    r.connection.disconnect()
                if hasattr(r, "connection_pool"):
                    r.connection_pool.disconnect()
            except Exception as e:
                log.warning(f"关闭连接时出错: {e}")


def initialize(context):
    set_benchmark("510880.XSHG")
    g.redis_option = False
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    log.info("初始函数开始运行且全局只运行一次")
    log.set_level("order", "error")

    # ===== v4.5 显式成本设置 =====
    set_slippage(PriceRelatedSlippage(SLIPPAGE_RATE))
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=COMMISSION_RATE,
        close_commission=COMMISSION_RATE,
        min_commission=MIN_COMMISSION), type='fund')
    log.info(f"[DIAG-INIT-COST] 滑点={SLIPPAGE_RATE:.2%}, 佣金={COMMISSION_RATE*10000:.1f}‱, "
             f"最低={MIN_COMMISSION}元, 往返成本≈{(SLIPPAGE_RATE*2 + COMMISSION_RATE*2)*100:.2f}%")
    # =============================

    g.strategys = {}
    g.portfolio_value_proportion = [1]
    g.positions = {i: {} for i in range(len(g.portfolio_value_proportion))}

    g.fixed_stop_cooldown = {}
    g.daily_net_values = []
    g.position_ratio = 1.0
    g.last_target_weights = {}

    log.info(f"[DIAG-INIT] ENABLE_QUALITY_ADJUST={ENABLE_QUALITY_ADJUST}, "
             f"QUALITY_NUMERATOR={QUALITY_NUMERATOR}, "
             f"QUALITY_SCALE=[{QUALITY_SCALE_MIN},{QUALITY_SCALE_MAX}], "
             f"WEIGHT_CHANGE_THRESHOLD={WEIGHT_CHANGE_THRESHOLD}, "
             f"TARGET_VOL={TARGET_VOL}")

    if g.portfolio_value_proportion[0] > 0:
        run_daily(etf_rotation_adjust, "11:00")
        if ENABLE_FIXED_STOP:
            run_daily(etf_rotation_stop_loss, "14:50")
    run_daily(end_trade, "14:59")


def process_initialize(context):
    g.strategys = {
        name: cls(context, index=idx, name=name, display_name=display_name)
        for display_name, name, cls, idx in [
            ("核心资产轮动策略", "etf_rotation_strategy", Etf_Rotation_Strategy, 0),
        ]
    }


def on_event(context, event):
    if event.name == "Dividends":
        for d in event.dividends:
            scale = d.get("scale_factor", 1)
            if scale != 1:
                print(f"收到送股事件: {event.security}:{event.dividends}")
                code = event.security.code
                for pid, pos in g.positions.items():
                    if code in pos:
                        old = pos[code]
                        pos[code] = int(old * scale)
                        print(f"调整持仓: 组合 {pid}, 股票 {code}, 数量 {old} -> {pos[code]}")


def end_trade(context):
    marked = {s for d in g.positions.values() for s in d}
    for stock in context.portfolio.positions:
        if stock not in marked and order_target_value(stock, 0):
            log.info(f"卖出{stock}因送股未记录在持仓中")


def etf_rotation_adjust(context):
    g.strategys["etf_rotation_strategy"].adjust()


def etf_rotation_stop_loss(context):
    if "etf_rotation_strategy" in g.strategys:
        g.strategys["etf_rotation_strategy"].stop_loss_check()


# -------------------- 策略基类 --------------------
class Strategy:
    def __init__(self, context, index, name, display_name):
        self.context = context
        self.index = index
        self.name = name
        self.display_name = display_name
        self.stock_sum = 1
        self.hold_list = []
        self.min_money = 10000
        self.pass_months = [1, 4]
        self.def_stocks = ["511260.XSHG", "518880.XSHG", "512800.XSHG"]

    def get_total_value(self):
        if not g.positions[self.index]:
            return 0
        total = 0.0
        for key, value in g.positions[self.index].items():
            total += self.context.portfolio.positions[key].price * value
        return total

    def _adjust(self, targets):
        current_data = get_current_data()
        if g.redis_option:
            strategy_data = {
                "id": self.index, "display_name": self.display_name,
                "last_updated": int(time.time() * 1000),
                "holdings": {
                    (stock[:6] + (".SH" if stock.endswith(".XSHG") else ".SZ")): {
                        "stock_name": current_data[stock].name, "proportion": weight,
                    } for stock, weight in targets.items()
                },
            }
            set_strategy_data(self.name, strategy_data)

        self.hold_list = list(g.positions[self.index].keys())
        portfolio = self.context.portfolio
        target_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]

        for stock in self.hold_list:
            if stock not in targets:
                self.order_target_value_(stock, 0)

        for stock, weight in targets.items():
            target = target_value * weight
            price = current_data[stock].last_price
            value = g.positions[self.index].get(stock, 0) * price
            if value - target > max(self.min_money, price * 100):
                self.order_target_value_(stock, target)

        for stock, weight in targets.items():
            target = target_value * weight
            price = current_data[stock].last_price
            value = g.positions[self.index].get(stock, 0) * price
            if min(target - value, portfolio.available_cash) > max(self.min_money, price * 100):
                self.order_target_value_(stock, target)

    def order_target_value_(self, security, value):
        current_data = get_current_data()
        if current_data[security].paused:
            log.info(f"{security}: 今日停牌"); return False
        if current_data[security].last_price == current_data[security].high_limit:
            log.info(f"{security}: 当前涨停"); return False
        if current_data[security].last_price == current_data[security].low_limit:
            log.info(f"{security}: 当前跌停"); return False

        price = current_data[security].last_price
        current_position = g.positions[self.index].get(security, 0)
        target_position = (int(value / price) // 100) * 100 if price != 0 else 0
        adjustment = target_position - current_position

        closeable_amount = self.context.portfolio.positions[security].closeable_amount if security in self.context.portfolio.positions else 0
        if adjustment < 0 and closeable_amount == 0:
            log.info(f"{security}: 当天买入不可卖出"); return False

        if adjustment != 0:
            o = order(security, adjustment)
            if o:
                filled = o.filled if o.is_buy else -o.filled
                g.positions[self.index][security] = filled + current_position
                if g.positions[self.index][security] == 0:
                    g.positions[self.index].pop(security, None)
                self.hold_list = list(g.positions[self.index].keys())
                return True
        return False

    def filter_basic_stock(self, stock_list, include_kcbj=False, days=360):
        current_data = get_current_data()
        stock_list = stock_list if include_kcbj else [s for s in stock_list if not (s[0] == "4" or s[0] == "8" or s[:2] == "68")]
        return [s for s in stock_list if not current_data[s].paused and not current_data[s].is_st
                and "ST" not in current_data[s].name and "*" not in current_data[s].name and "退" not in current_data[s].name
                and not self.context.previous_date - get_security_info(s).start_date < datetime.timedelta(days)]

    def filter_limitup_limitdown_stock(self, stock_list):
        current_data = get_current_data()
        return [s for s in stock_list if current_data[s].last_price < current_data[s].high_limit and current_data[s].last_price > current_data[s].low_limit]

    def filter_limitup_stock(self, stock_list, days):
        df = get_price(stock_list, end_date=self.context.previous_date, frequency="daily",
                       fields=["close", "high_limit"], count=days, panel=False)
        df = df[df["close"] == df["high_limit"]]
        return [s for s in stock_list if s not in df.code.drop_duplicates().tolist()]

    def filter_industry(self, stocks, n):
        industry_map = {s: info.get("sw_l1", {}).get("industry_name", "") for s, info in get_industry(stocks).items()}
        counts, result = {}, []
        for s in stocks:
            ind = industry_map.get(s, "")
            if counts.get(ind, 0) < n:
                result.append(s); counts[ind] = counts.get(ind, 0) + 1
        return result

    def _check(self):
        hold = list(g.positions[self.index].keys())
        if not hold: return []
        current_data = get_current_data()
        filtered = self.filter_limitup_stock(hold, 3)
        return [s for s in hold if s not in filtered and current_data[s].last_price < current_data[s].high_limit]

    def filter_untradeable_stock(self, stocks):
        current_data = get_current_data()
        return [s for s in stocks if current_data[s].paused or current_data[s].last_price in (current_data[s].high_limit, current_data[s].low_limit)]

    def get_adjusted_stocks(self, selected, sell):
        fixed = self.filter_untradeable_stock(list(g.positions[self.index].keys()))
        sum_ = len(self.def_stocks) if selected == self.def_stocks else self.stock_sum - len(fixed)
        return fixed + [s for s in selected if s not in fixed and s not in sell][:sum_]

    def filter_financial_stocks(self, stocks):
        industry_data = get_industry(stocks)
        return [s for s in stocks if industry_data[s].get("sw_l1", {}).get("industry_name", "") not in ["银行I", "非银金融I"]]


# -------------------- 核心资产轮动策略 --------------------
class Etf_Rotation_Strategy(Strategy):
    def __init__(self, context, index, name, display_name):
        super().__init__(context, index, name, display_name)
        self.etf_pool = [
            "513100.XSHG", "513520.XSHG", "513030.XSHG",
            "518880.XSHG", "159980.XSHE", "159985.XSHE", "501018.XSHG",
            "511090.XSHG", "513130.XSHG",
        ]

    def _in_cooldown(self, sec):
        last_stop = g.fixed_stop_cooldown.get(sec)
        if last_stop is None:
            return False
        today = self.context.current_dt.date()
        try:
            trade_days = get_trade_days(start_date=last_stop, end_date=today)
            days_since = len(trade_days) - 1
        except Exception:
            return True
        if days_since > COOLDOWN_TRADE_DAYS:
            g.fixed_stop_cooldown.pop(sec, None)
            return False
        return True

    def _calc_position_ratio(self):
        if not ENABLE_DOWNSIDE_VOL:
            return 1.0
        if len(g.daily_net_values) < VOL_WINDOW:
            return g.position_ratio
        recent = g.daily_net_values[-VOL_WINDOW:]
        returns = [(recent[i] - recent[i-1]) / recent[i-1]
                   for i in range(1, len(recent)) if recent[i-1] > 0]
        if len(returns) < 2:
            return g.position_ratio
        downside = [r if r < 0 else 0.0 for r in returns]
        vol = float(np.std(downside) * np.sqrt(252))
        if vol <= 1e-8:
            raw_ratio = MAX_POSITION_RATIO
        else:
            raw_ratio = float(np.clip(TARGET_VOL / vol, MIN_POSITION_RATIO, MAX_POSITION_RATIO))
        g.position_ratio = g.position_ratio * POSITION_RATIO_SMOOTH + raw_ratio * (1 - POSITION_RATIO_SMOOTH)
        g.position_ratio = float(np.clip(g.position_ratio, MIN_POSITION_RATIO, MAX_POSITION_RATIO))
        return g.position_ratio

    # ============ 质量因子（q=0.005 / vol） ============
    def _calc_quality_factor(self, sec):
        try:
            df = get_price(sec, count=QUALITY_VOL_WINDOW + 1,
                           end_date=self.context.previous_date,
                           frequency='daily', fields=['close'])
            if df is None or len(df) < QUALITY_VOL_WINDOW + 1:
                return 1.0
            rets = df['close'].pct_change().dropna()
            if len(rets) < QUALITY_VOL_WINDOW:
                return 1.0
            vol = float(rets.std())
            if vol < 0.001:
                vol = 0.001
            quality = QUALITY_NUMERATOR / vol     # ★ 0.005 / vol
            return float(np.clip(quality, QUALITY_SCALE_MIN, QUALITY_SCALE_MAX))
        except Exception:
            return 1.0

    def _calc_quality_weights(self, targets):
        n = len(targets) if targets else 0
        if n == 0:
            return {}
        if n == 1:
            return {targets[0]: 1.0}
        # 修复：不用 any() + in，改显式循环（环境 any 可能异常）
        exclude_hit = False
        for _sec in targets:
            for _ex in QUALITY_EXCLUDE_SECS:
                if _sec == _ex:
                    exclude_hit = True
                    break
            if exclude_hit:
                break
        if exclude_hit:
            return {sec: 1.0 / n for sec in targets}
        raw = {sec: self._calc_quality_factor(sec) for sec in targets}
        total = 0.0
        for _v in raw.values():
            total += float(_v)
        if total <= 0.0:
            return {sec: 1.0 / n for sec in targets}
        return {sec: float(raw[sec]) / total for sec in targets}

    def filter(self, max_score, days):
        data = pd.DataFrame(index=self.etf_pool, columns=["annualized_returns", "r2", "score"])
        current_data = get_current_data()
        for etf in self.etf_pool:
            if self._in_cooldown(etf):
                continue
            df = attribute_history(etf, days, "1d", ["close", "high"])
            prices = np.append(df["close"].values, current_data[etf].last_price)
            y = np.log(prices)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0
            data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]
            if min(prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]) < 0.95:
                data.loc[etf, "score"] = 0
        data = data[(data["score"] > 0) & (data["score"] < max_score)].sort_values(by="score", ascending=False)
        if data.empty:
            return "511880.XSHG"
        return data.index.tolist()[0]

    def select(self):
        etf1 = self.filter(6, 25)
        etf2 = self.filter(0.5, 250)
        return [etf1, etf2] if etf1 != etf2 else [etf1]

    def adjust(self):
        targets = self.select()
        ratio = self._calc_position_ratio()

        if ENABLE_QUALITY_ADJUST:
            quality_weights = self._calc_quality_weights(targets)
        else:
            n = len(targets) if targets else 1
            quality_weights = {sec: 1.0 / n for sec in targets}

        kept_by_weight, kept_by_money = [], []
        if WEIGHT_CHANGE_THRESHOLD > 0 and g.last_target_weights and len(targets) > 1:
            total_value = self.context.portfolio.total_value
            adjusted = {}
            for sec in targets:
                new_w = quality_weights.get(sec, 0.0)
                old_w = g.last_target_weights.get(sec, 0.0)
                weight_diff = abs(new_w - old_w)
                cur_value = 0.0
                if sec in self.context.portfolio.positions:
                    cur_value = self.context.portfolio.positions[sec].value
                target_value_sec = total_value * new_w * ratio
                money_diff = abs(target_value_sec - cur_value)
                if weight_diff < WEIGHT_CHANGE_THRESHOLD:
                    adjusted[sec] = old_w
                    kept_by_weight.append(f"{sec[:6]}(Δw={weight_diff:.1%})")
                elif money_diff < self.min_money:
                    adjusted[sec] = old_w
                    kept_by_money.append(f"{sec[:6]}(Δ¥={money_diff:.0f})")
                else:
                    adjusted[sec] = new_w
            total_w = 0.0
            for _w in adjusted.values():
                total_w += float(_w)
            if total_w > 0.0:
                quality_weights = {sec: float(w) / total_w for sec, w in adjusted.items()}

        scaled_targets = {sec: quality_weights[sec] * ratio for sec in targets}
        self._adjust(scaled_targets)
        g.last_target_weights = dict(quality_weights)

        if ENABLE_DOWNSIDE_VOL or ENABLE_QUALITY_ADJUST:
            msg = (
                f"[仓位管理] ratio={ratio:.3f} "
                f"标的={list(targets)} "
                f"质量权重={[round(quality_weights[e],3) for e in targets]} "
                f"最终权重={[round(scaled_targets[e],3) for e in targets]}"
            )
            if kept_by_weight:
                msg += f" | 权重变化<{WEIGHT_CHANGE_THRESHOLD:.0%}保持: {kept_by_weight}"
            if kept_by_money:
                msg += f" | 金额变化<{self.min_money}保持: {kept_by_money}"
            log.info(msg)

    def stop_loss_check(self):
        if ENABLE_DOWNSIDE_VOL:
            g.daily_net_values.append(self.context.portfolio.total_value)
            if len(g.daily_net_values) > 200:
                g.daily_net_values = g.daily_net_values[-200:]
        if not ENABLE_FIXED_STOP:
            return
        total_value = self.context.portfolio.total_value
        hold_secs = [
            sec for sec in list(g.positions[self.index].keys())
            if sec in self.context.portfolio.positions
            and self.context.portfolio.positions[sec].total_amount > 0
        ]
        if not hold_secs:
            return
        is_full = False
        if len(hold_secs) == 1:
            pos0 = self.context.portfolio.positions[hold_secs[0]]
            if pos0.total_amount > 0 and pos0.value / total_value > 0.98:
                is_full = True
        fixed_threshold = FIXED_STOP_FULL if is_full else FIXED_STOP_NORMAL
        current_data = get_current_data()
        today = self.context.current_dt.date()
        for sec in hold_secs:
            pos = self.context.portfolio.positions[sec]
            if pos.total_amount == 0:
                continue
            entry_price = pos.avg_cost
            if entry_price is None or entry_price <= 0:
                continue
            cd = current_data[sec]
            if cd.paused:
                continue
            current_price = cd.last_price
            if current_price is None or current_price <= 0:
                continue
            if pos.closeable_amount <= 0:
                continue
            loss_pct = (current_price - entry_price) / entry_price
            if loss_pct <= fixed_threshold:
                if self.order_target_value_(sec, 0):
                    g.fixed_stop_cooldown[sec] = today
                    g.last_target_weights.pop(sec, None)
                    log.info(
                        f"【固定止损】{sec} 亏损 {loss_pct:.2%} "
                        f"(阈值 {fixed_threshold:.2%}{'，满仓' if is_full else ''}) "
                        f"→ 清仓，冷却 {COOLDOWN_TRADE_DAYS} 交易日"
                    )