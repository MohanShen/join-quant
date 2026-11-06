# Clone from JoinQuant
# postId: 30a4b90a63514adf0f70bebaa9698044
# backtestId: 4a5fcc5ed2134f57a8bc0d4264fe8ac9
# title: A股情绪和游资打板的关系20261023

# 克隆自聚宽文章：https://www.joinquant.com/post/80039
# 标题：今天看到的一个离谱的策略，两个月几乎10倍
# 作者：Zlwink

# 克隆自聚宽文章：https://www.joinquant.com/post/79913
# 标题：强者恒强策略从8月13到现在实时模拟收益54.45%
# 作者：hl0000



# -*- coding: utf-8 -*-
# ==================== 策略名称：强者恒强 V6.2-市场门控·资金最大化·A5开盘先卖（自动交易 + 手动跟单提示） ====================
# 修改记录：
#   2026-10-14：V6.2-A5 复装 —— V6.1 + 恢复「09:30 开盘未涨停的自有持仓先卖」（SELL_930_A5_MODE='on'）；
#               回款当日用于定盘买入 ⇒ 满仓档每天都能买满 3 只；开关 off 即回 V6.1 行为。
#   2026-10-14：V6.1-市场门控·资金最大化 —— V6.0 + 去掉股票金额限制（CASH_MAX_MODE='on'）；
#               当日仍 ≤3 只，单只/当日/总持仓金额全不限，每只预算=可用现金÷本轮只数（吃满资金）。
#   2026-10-14：V6.0-市场门控 —— V5.0 + 4 道开盘前市场门（D4 大盘MA20 / D5 市场宽度 / D1 全球共振防御 / D3 走弱期不买）；
#               命中即"今日不开新仓"，卖出/止损链路不变；四道各自独立开关（默认全 True），见「市场门控开关」块。
#   2026-10-14：V5.0 —— 买入/卖出全面对齐 PTrade V25 实盘：定盘 09:30:15（15 秒）+ 预热冻结榜单；
#               卖出 A1-A4 拆除、A5 停用、方向分流 on、炸板尺/均线尺 on、统一裁决、
#               破板回落 0.5%×6 秒、当日卖出禁买回、复牌禁买、金额口径 1.2 万/3.6 万/7.2 万
#   2026-06-17：手动跟单时间改为09:30:16，与首次自动买入同步；候选股日志换手率改为现价
#   2026-06-13：增加手动跟单提示（09:31输出候选股），同时保留自动交易
#   2026-06-10：精简日志输出；增加行业概念显示
#   2026-06-16：优化手动跟单日志输出，仅显示前12只候选股且每只一行显示
#   2026-06-17：新增09:33:16手动跟单买点，输出候选股（第二次提示）
# ============================================================
# ============================================================
# ★★ V5.0 = 全面对齐 PTrade V25 实盘口径（2026-10-14，用户要求"早盘买入模式 + 卖出逻辑全面参考 V25"）
#   确认版本：搜索 "V5.0" 或 "OPEN_DIRECTION_MODE" / "RULE_V232_MODE"
#   ① 【买点 15 秒定盘】DECIDE_SECOND 09:30:16 → **09:30:15**（= 实盘 live_early_start，用户：早盘买入15秒前后）；
#      09:30:00~09:30:15 每 3 秒【预热】全池强度排序（只算不下单），定盘格用最后一轮预热排序直接报单
#      （对齐 V25 RANK_FROZEN_AT_OPEN / WARM_TOP_N 口径）。Tick 频率回测走 handle_tick；分钟频率回测自动退回 09:31。
#   ② 【金额口径对齐 V25（用户 2026-10-11）】单只 12000 / 当日 ≤36000 / 总持仓 ≤72000（V4.1 为 1 万/4 万/4 万）。
#   ③ 【卖出 A 类出场拆除（V24.9 口径，依据 9,273 笔样本）】A1 止损 −4% / A2 止盈 +19% / A3 超期 3 日 /
#      A4 放量下跌 —— **整段删除**；A5「09:30 开盘未涨停卖」**停用**（只打日志，交方向分流）；A6 11:30 兜底保留。
#   ④ 【卖出·开盘方向分流 v20.2（OPEN_DIRECTION_MODE='on'）】09:30:03 起每格判"俯冲"：
#      俯冲（当日最低 ≤ 开盘×(1−0.2%) 且 现价<开盘 / 或贴跌停）→ 立刻卖；
#      其余进冲高监控：触发线=开盘×(1+2%)，触发后自最高回落 0.5% 卖；未触发自当日最高回落 0.5% 卖；
#      11:30 仍未触发 → 现价卖（A6 兜底）。毛刺过滤 v21.3（破位≠真跌：现价<盘中均价 或 连续 2 格确认才卖）。
#   ⑤ 【炸板尺/均线尺 v23.3（RULE_V232_MODE='on'）+ 统一裁决】当日曾触板(最高≥涨停×0.995) → 炸板尺
#      （回封/在回升=强势不卖；破新低/回升停滞/贴跌停/窗口到期=卖；前 2 格只记 L0 防插针）；
#      未触板 → 均线尺（均价相对开盘下移 ≥0.3% 才卖）；炸板尺判"不卖" ⇒ 抑制全部卖出路；
#      现价 ≥ 涨停×0.999 一律不卖。
#   ⑥ 【破板回落对齐 V22.8】阈值 1.5% → **0.5%**，确认 15 秒 → **6 秒**（v23.2 闸门同步接入）。
#   ⑦ 【当日卖出后禁止买回 v20.1（REBUY_GUARD_MODE='on'）】修"卖飞又买回"白亏 2~4% 价差。
#   ⑧ 【复牌票禁买 v22.2（RESUME_FILTER_MODE='on'）】昨日=复牌首日的候选剔除。
#   ⑨ 聚宽适配：盘中均价 wavg_px ≈ 当日累计成交额÷累计成交量（1 分钟 bar 求和，15 秒节流缓存）；
#      取不到均价时毛刺过滤退化为"连续 2 格确认"。tick 频率=3 秒一格；分钟频率=1 分钟一格（语义等价、更保守）。
# ★★ V6.2-A5 复装（开盘先卖） = V6.1 + 【09:30 开盘未涨停的自有持仓先卖】（2026-10-14 用户拍板）
#   确认版本：搜索 "V6.2" / "SELL_930_A5_MODE" / "a5_open_sell"
#   【为什么】满仓档（CASH_MAX_MODE='on'）第 1 天吃光现金，第 2 天起定盘可用资金不足 1 手 → 天天 0 笔；
#     而 A5「09:30 开盘未涨停卖」自 V24.9 起停用 ⇒ 开盘不卖、无回款 ⇒ "先卖后买"只剩买。
#   【本版】复装 A5：09:30/09:31 定盘之前，把【策略自购、非今日买入、开盘未涨停】的持仓先卖掉，
#     回款当日即可用于定盘买入（A 股规则：股票 T+1 不可卖，卖出所得资金当日可用）。
#     开关 SELL_930_A5_MODE（默认 'on'）= 'off' 一键回 V6.1 行为（开盘不主动卖，交方向分流）。
#   【已知代价（用户知情）】A5 当年因"卖飞"被停用（9,273 笔样本：有 A 类口径 −0.093% vs 无 A 类 +0.176%）；
#     且回测下 09:30 那格不存在（聚宽回测 run_daily 最早 09:31）⇒ **回测里 A5 实际卖在 09:31 那根 bar**，
#     实盘/模拟才是 09:30:03 的真实盘口价。
#   【附带效果】A5 卖掉的票当日受 REBUY_GUARD 约束 → 当天不会再买回（不会"卖飞又追回"）。
#   【未改动】四道市场门、资金最大化口径（CASH_MAX_RESERVE）、方向分流/炸板尺/均线尺/破板回落/A6 全部与 V6.1 一致。
# ★★ V6.1-市场门控·资金最大化 = V6.0 + 【去掉股票金额限制】（2026-10-14，用户要求）
#   确认版本：搜索 "V6.1" / "CASH_MAX_MODE"
#   【口径】CASH_MAX_MODE = 'on'（默认）：当日新建仓**仍 ≤ 3 只**（MAX_BUY_PER_DAY_STOCKS），
#     但 单只金额 / 当日买入金额 / 总持仓金额 三个上限**全部取消** →
#     每只预算按「剩余只数」逐只重算：第 1 只=现金×0.995÷3、第 2 只=现金×0.995÷2、最后一只吃掉余下大部分现金
#     （均 100 股整数倍向下取整）⇒ 三只合计≈吃满可用资金。
#     'off' = 一键回到 V6.0 / V5.0 原口径（单只 1.2 万 / 当日 3.6 万 / 总持仓 7.2 万）。
#   【未改动】四道市场门（D1/D3/D4/D5）、卖出引擎、竞价增强、选股过滤、限价与笼子 全部与 V6.0 一致；
#     MAX_BUY_RANK（只买全池强度前 5 名）与 MAX_BUY_PER_DAY_STOCKS（3 只）**保持不变**。
# ★★ V6.0-市场门控 = V5.0 + 【开盘前市场判定 · 4 道门】（2026-10-14，用户指定移植 五福5.2 的 D1/D3/D4/D5）
#   确认版本：搜索 "V6.0" / "enable_market_ma20_gate" / "market_gate_precheck"
#   【主诉求】判定走弱期就不开仓 —— 判据全部取【昨日及更早】收盘数据（attribute_history 不含当日 /
#     get_price end_date=previous_date）⇒ 09:00 盘前即可定论，回测无未来函数。
#   D4 大盘MA20门控 = 沪深300 昨收 < MA20                          → 今日不开新仓
#   D5 市场宽度门控 = 全市场收盘>MA20 的占比 < 30%                  → 仓位乘数=0，今日不开新仓
#   D1 全球共振防御 = 走弱期 且 513100/513500/513520 过半跌破 MA10   → 清空候选池
#        （强者恒强是买个股的、没有货币防御 ETF 通道 ⇒ 只清空候选池，**不买 511880**）
#   D3 走弱期降频   = 走弱期                                        → 今日不开新仓
#        ⚠ 强者恒强全天只有 09:30:15 一次定盘买入（STOP_BUY_AFTER_OPEN=True），没有 13:40/14:10/14:40
#          趋势复检与 14:55 强制买入窗口 ⇒ D3 在本版等价合并为「走弱期当日不买」（开关独立保留）。
#   【落点】buy_decision() 开头一道闸 = 覆盖 tick 定盘(09:30:15) 与分钟兜底(09:31/32/33/37/10:29) 全部买入路径；
#     盘前在 before_market_open() 末尾先判先打日志（09:00 就能看到结论）。
#   【开关】enable_market_ma20_gate / breadth_gate / global_weak_defense / weak_freq_reduce —— 见「市场门控开关」块，
#     改那一行即可逐道上/逐道关；initialize 会把它们镜像到 g（运行期改 g.xxx 同样生效，g 优先）。
#   【未改动】卖出引擎（方向分流/炸板尺/均线尺/破板回落/A6 兜底）、竞价增强、选股过滤、金额口径 全部与 V5.0 一致。
#   【本版已知代价】D5 用 breadth_universe=stock（≈5000 只 A 股 × 21 日）盘前取一次数；想快就把该常量改成
#     '300'（沪深300 成分）或 'etf'；日志里带「有效 N 只 / 取数 xxms」，可据此判断是否拖慢盘前。
#   任何一道门取数失败 = 该道门不拦（放行），并打 ⚠️ 日志（不会因为接口抽风而整天不买）。
# ★★ V4.0 = 对齐 PTrade 实盘 V19.1（2026-09-23，历史）
#   ① 回测套用实盘口径：BACKTEST_UNLIMITED=False ② 取消"每只 ≤100 股"试仓封顶
#   ③ tick 级破板回落监控（持续 N 秒防插针）④ 三条校准日志
# ============================================================
# 【V3.1 · 2026-09-21 · 回测无限制档（用户要求）】
#   BACKTEST_UNLIMITED = False（【V4.0】当前值 = 实盘 V19.1 口径）：
#     单只 ≈1 万 / 当日 ≤3 只 / 总持仓 ≤4 万 / 股数不封顶。
#   True = 回测"无限制档"（旧档，用于看策略原始爆发力）：
#     不限制只数/金额/股数，仓位 = 本轮可用资金等权分配；
#     买入范围仍按强度排序只取前 MAX_BUY_RANK=5 名。
#   ★ 两档的收益曲线不可直接比（实盘口径最多只用 4 万/10 万本金 → 曲线被稀释）。
# ============================================================
# 【V3.0 · 2026-09-21 · 对齐 PTrade v18 口径（用户确认）】
#   ① 当日新建仓 ≤ 3 只（MAX_BUY_PER_DAY_STOCKS）
#   ② 全天只买"全池强度排序前 5 名"（MAX_BUY_RANK），可买宇宙在定盘那一格冻结
#   ③ 股数不封顶（MAX_SHARES_PER_STOCK=0；【V4.0】与实盘 A 方案一致）
#   ④ 总持仓金额 ≤ 4 万元（MAX_TOTAL_POSITION_AMOUNT）；单只目标 1 万（MIN_AMOUNT_PER_STOCK 仅用于名额估算）
#   ⑤ 持仓只数不限（BASE_MAX_HOLD=0）—— 原 max_stock_num / dynamic_asset_tiers 已删除
#   ⑥ 定盘那一格排序+报单，买完即停（STOP_BUY_AFTER_OPEN）：不再每分钟补单/追价
#   卖出沿用 V2.4：只卖策略自己买的票（SELL_ONLY_OWN）+ 开盘未涨停卖 + 破板回落 + 止损止盈
#   聚宽限制：回测里 run_daily 最早 09:31 触发 → 定盘落在 09:31 那一格（实盘为 09:30）
# ============================================================
# 【回测版 V2.4 · 2026-09-18 · V16 移植 + 每日复位 + 自诊断 + 修 avoid_future_data 拦截】相对原始聚宽版的改动（规则不变，只做口径校准）：
#   ① 回测成本修正：原来 `context.order_cost = OrderCost(...)` 在聚宽**不生效**（正确写法是
#      set_order_cost），且参数为佣金万3、印花税千1 → 已改为 佣金万1 / 每笔最低5元 /
#      卖出印花税0.05% / 过户费0.001%双向，与本人实盘账户（国金证券）一致；
#   ② 金额口径：单只上限 1.2 万元、当日合计上限 3.6 万元（与实盘一致）；
#   ③ 限价加交易所价格笼子（限价 ≤ 现价×1.02，超过柜台会废单），并保留涨停封顶；
#   ④ 只卖"策略自己买入的票"（SELL_ONLY_OWN，默认 True）+ SELL_SKIP_CODES 排除名单；
#   ⑤ 新增「竞价增强」模块（规则 ①竞价涨幅≥+2% ②竞价额分级门槛 ③板块内额前1/3 ④剔除一字/竞价涨停
#      ⑤★三项命中数），默认 **shadow 只记录不拦截** —— 回测跑一遍即可拿到"过闸 vs 被闸"的对照样本；
#      想验证"开闸是否更好"，把 AUCTION_GATE_MODE 改成 'on' 再跑一遍同一区间即可。
#   ⑥ run_daily 时间统一成 HH:MM；⑦ 回测默认关闭 Redis 信号推送。
#
# 【回测口径提醒】聚宽分钟数据第一根K线是 09:31，"竞价额"用**开盘首分钟成交额**近似（含竞价成交，
#   比实盘快照的纯竞价额偏高），取不到时该条自动记为"未判定"，绝不拦票。
# 【建议回测设置】区间：近 3~6 个月；初始资金 10 万；频率：分钟；基准 000300.XSHG；
#   撮合：use_real_price=True（已设）；滑点 PriceRelatedSlippage(0.002) 已在 initialize 设置。
# ============================================================

# ==================== 回测版新增开关（2026-09-18） ====================
# ---- 【V2.0】对齐 PTrade v16 的执行层常量 ----
OPEN_CAGE_RESERVE = 0.01              # 笼子安全余量（元）：限价 ≤ 现价×1.02 − 0.01
SPIKE_TOL_HIGH = 1.002                # 限价 ≤ 当日最高成交价×(1+0.2%)（不追当日新高）
SPIKE_TOL_HIGH_ON = False             # 【V2.3】默认关闭：聚宽是分钟K线无 tick 毛刺，
                                      #   开着会把限价压到贴着现价 → 回测里挂单不成交
OPEN_BUY_N = 3                        # 定盘一次报满前 3 只
OPEN_ONLY_REQUESTED = True            # 09:30~09:33 只重报"定盘名单"内的票

TARGET_AMOUNT_PER_STOCK = 12000.0     # 【V5.0】单只目标金额（对齐 V25：用户 2026-10-11 单只不超过 1.2 万）
MAX_BUY_AMOUNT_PER_DAY = 36000.0      # 【V5.0】当日合计买入上限（对齐 V25：3 只 × 1.2 万）
# ==================== 【V6.1·资金最大化口径】（用户 2026-10-14 要求） ====================
# 'on'  = 去掉全部「股票金额限制」：当日新建仓 **仍 ≤ MAX_BUY_PER_DAY_STOCKS（3）只**，
#         单只金额 / 当日买入金额 / 总持仓金额 三个上限**全部取消**；
#         每只预算 = 本轮可用现金 ÷ 本轮只数（100 股整数倍向下取整）⇒ 吃满可用资金。
# 'off' = 回到 V6.0 / V5.0 原口径（单只 1.2 万 / 当日 3.6 万 / 总持仓 7.2 万）。
CASH_MAX_MODE = 'on'
# 现金预留：每只预算 = 可用现金 × 本系数 ÷ 剩余只数（留一点付佣金/过户费，避免最后一只因手续费不足废单）
#   1.0 = 一分不留（激进，可能废单）｜0.995 = 留 0.5%（默认，10 万上仅 ~500 元）
CASH_MAX_RESERVE = 0.995
# ---- 【V3.0 = PTrade v18 口径（用户 2026-09-21 确认）】----
MAX_BUY_RANK = 5                      # 只买"全池强度排序前 5 名"
MAX_BUY_PER_DAY_STOCKS = 3            # 当日新建仓上限（只数）
MAX_TOTAL_POSITION_AMOUNT = 72000.0   # 【V5.0】总持仓金额上限（对齐 V25：7.2 万 = 两天满仓）
MAX_SHARES_PER_STOCK = 0              # 【V4.0】0 = 不封顶股数（= 实盘 A 方案）；填 100 可回到试仓
BASE_MAX_HOLD = 0                     # 持仓只数上限：0 = 不限
SCOUT_AMOUNT_PER_STOCK = 12000.0      # 【V5.0】只数名额估算 = 单只目标（对齐 V25）
MIN_AMOUNT_PER_STOCK = 5000.0         # 仅用于名额估算
STOP_BUY_AFTER_OPEN = True            # 定盘那一格买完后当日不再买入
# ---- 【V3.1 回测专用：不做限制】----
#   用户 2026-09-21 要求：回测版去掉"持股要求"与"金额限制"，让它按强度排序自己买，
#   目的是跑出策略本来的选股能力（不被实盘小账户的闸门掩盖）。
#   True  = 不计持仓只数、不计当日只数、不计总金额、不计单只金额、不封股数；
#           仓位 = 本轮可用资金 ÷ 本轮要买只数（等权，100 股整数倍）
#   False = 回到 V3.0 口径（当日≤3 只 / 总持仓≤4万 / 单只≤100股）
BACKTEST_UNLIMITED = False       # 【V4.0】False = 套用实盘 V19.1 口径（单只1万/当日3只/总4万）
OPEN_CAGE_MAX = 1.02                  # 交易所价格笼子：限价必须 ≤ 现价 × 1.02，否则废单
OPEN_CAGE_MIN = 0.98                  # 下限（卖出方向），保留备用
SELL_ONLY_OWN = True                  # True = 只卖策略自己买入的票（保护手工持仓）
SELL_SKIP_CODES = []                  # 永不卖出名单，例：['159582.XSHE', '513330.XSHG']
# ==================== 【V6.0·市场门控】开盘前市场判定（4 道独立开关，默认全 True） ====================
# 真源 = 本块常量（改这一行即可开关）；initialize() 会把它们镜像到 g，运行期改 g.xxx 也生效（g 优先）。
# 判据一律取【昨日(含)以前】的日线数据 → 盘前可算、回测无未来函数；取不到数据 = 不拦（放行）。
enable_market_ma20_gate = True      # [D4] 沪深300 昨收 < MA20 → 今日不开新仓
market_index = '000300.XSHG'        # 大盘指数（可改 '000001.XSHG' 上证）
market_ma20_lookback = 20           # [D4] 均线周期
enable_breadth_gate = True          # [D5] 全市场收盘>MA20 占比 < 阈值 → 仓位乘数=0，今日不开新仓
breadth_universe = 'stock'          # [D5] 'stock'=全市场A股(≈5000只,慢) | '300'=沪深300成分(快) | 'etf'=全市场ETF
breadth_ma_lookback = 20            # [D5] 多头判定均线周期
breadth_min_ratio = 0.30            # [D5] 多头占比阈值（30%）
enable_global_weak_defense = True   # [D1] 走弱期 且 海外代理过半跌破 MA10 → 清空候选池
global_weak_proxy = ['513100.XSHG', '513500.XSHG', '513520.XSHG']   # 纳指ETF / 标普500ETF / 日经ETF
enable_weak_freq_reduce = True      # [D3] 走弱期 → 今日不开新仓（强者恒强无下午补买窗口，等价合并）
weak_period_ma_lookback = 10        # 走弱期 / 全球共振 的均线周期
weak_indexes = {'大盘': '000300.XSHG', '小盘': '399101.XSHE',
                '创业板': '399006.XSHE', '中证A500': '000510.XSHG'}   # 走弱期：≥3/4 低于 MA10 进入，≥3/4 站上退出

# ==================== 【V5.0】卖出引擎开关（全面对齐 PTrade V25 实盘口径） ====================
# A1 止损 / A2 止盈 / A3 超期 / A4 放量下跌 = 已整段删除（V24.9，依据 9,273 笔样本：
#    无 A 类口径均值 +0.176% vs 有 A 类 −0.093%，A1 触发样本胜率 0%）
# A5 09:30 开盘未涨停卖 = 【V6.2 复装】（SELL_930_A5_MODE='on'，用户 2026-10-14 拍板）；A6 11:30 兜底 = 保留
#   'on'  = 定盘之前先卖出自有持仓（开盘未涨停的），回款当日用于买入 —— 每天都买得到 3 只
#   'off' = 回到 V6.1 行为：开盘不主动卖，自有持仓交方向分流/炸板尺/均线尺
SELL_930_A5_MODE = 'on'
# 开盘价距涨停 > 本比例 = 未涨停（不卖一字/秒板）—— 对齐 V24.4 停用前的 A5 口径（0.5%）
A5_MIN_GAP_TO_LIMIT = 0.005
REBUY_GUARD_MODE = 'on'               # 【v20.1】'on'=当日卖出后禁止买回 | 'dry'=只记录 | 'off'=旧行为
RESUME_FILTER_MODE = 'on'             # 【v22.2】'on'=复牌首日候选剔除 | 'dry'=只记录 | 'off'=不过滤
# ---- 开盘方向分流（v20.2/v21.4，实盘已切 on）----
OPEN_DIRECTION_MODE = 'on'            # 'on'=真改行为 | 'dry'=只记录 | 'off'=V20.1 旧行为
OPEN_DIRECTION_DIVE_PCT = 0.2         # 破位线：现价 ≤ 开盘×(1−0.2%) 且 现价<开盘 → 俯冲立刻卖
DIVE_AT_LIMIT_DOWN_MODE = 'on'        # 开盘即跌停也立刻报卖单（v22.4）
DIVE_FILTER_MODE = 'on'               # 【v21.3】毛刺过滤：破位≠真跌（'on'真拦 | 'dry'只记录 | 'off'关闭）
DIVE_CONFIRM_TICKS = 2                # 连续 N 格仍破位即确认卖出（tick 模式≈6 秒；分钟模式≈2 分钟）
DIVE_REQUIRE_2TICK = 'on'             # 【v23.0】'on'=必须连续 2 格破位才卖（防 3 秒内回封洗出）
OPEN_DIRECTION_TRIGGER_BASE = 'open'  # 冲高触发基准：'open'（开盘×1.02）
OPEN_DIRECTION_FALLBACK_STALL_PCT = 0.5  # 未触发兜底：自当日最高回落 0.5% 即卖（11:30 硬截止）
OPEN_DIRECTION_DEADLINE = '11:30'     # A6 兜底时点：仍未触发 → 现价卖
OPEN_DIRECTION_SCOPE = 'all'          # 'all'=全部自有持仓走完整分流（v21.4.3 实测最优）
OPEN_DIRECTION_START = '09:30:03'     # 【v20.3】方向监控起点：开盘后第一个有信息的 tick
# ---- 炸板尺/均线尺 + 统一裁决（v23.3）----
RULE_V232_MODE = 'on'                 # 'on'=真按新规则 | 'dry'=只打日志不拦 | 'off'=关闭
V232_TRIGGER_GAP_PCT = 0.5            # 进入观察：现价跌破 涨停价×(1−0.5%)
V232_SEAL_GAP_PCT = 0.1               # 回封(强势)：现价 ≥ 涨停价×(1−0.1%)（也用于"贴近涨停不卖"闸门）
V232_RECOVER_RATIO = 0.5              # 回升(强势)：回升率=(现价−L0)/(涨停价−L0) ≥ 0.5 且 连续 2 格抬高
V232_OBSERVE_MAX_SEC = 8              # 窗口主判据=2 个格，时间只做兜底(秒)防跳格
V232_CONFIRM_TICKS = 2                # 窗口主判据：2 个格（tick 模式=2 个 tick；分钟模式=2 分钟）
V232_STALL_TICKS = 3                  # 回升停滞：连续 3 格价格不再抬高
V232_STALL_DROP_PCT = 0.5             # 回升停滞且回落：现价 ≤ T0价×(1−0.5%)
V232_NEW_LOW_PCT = 1.5                # 现价 ≤ L0×(1−1.5%) ⇒ 弱势卖（L0=进观察起的最低现价）
V232_MA_FOLLOW_PCT = 0.3              # 均线尺：均价相对开盘下移 ≥ 0.3% ⇒ 真跌卖；否则毛刺不卖
# ---- 买侧毛刺护栏（v13）----
SPIKE_MAX_VS_LAST = 1.005             # 买入限价 ≤ 快照现价×(1+0.5%)（不追出 0.5% 以上）

# ---- 竞价增强（用户 2026-09-18 提供的规则）----
AUCTION_GATE_MODE = 'shadow'          # 'off' 关闭 | 'shadow' 只记录不拦（默认）| 'on' 按①②④过滤
AUCTION_MIN_GAIN = 2.0                # ① 竞价涨幅下限（%）
AUCTION_MIN_GAIN_STAR = 4.0           # ⑤ 竞价涨幅命中★的下限（%）
AUCTION_AMT_TIERS = ((10.0, 2000000.0), (30.0, 3000000.0), (0.0, 5000000.0))  # ② (股价上限, 竞价额门槛)
AUCTION_STAR_MV = (30e8, 80e8)        # ⑤ 流通市值甜点区（30–80 亿）
AUCTION_BLOCK_MIN_SAMPLE = 5          # ③ 板块内做排名过滤的最小样本数

# ==================== 策略参数配置 ====================
STRATEGY_PARAMS = {
    # ---------- 持仓管理 ----------
    # 【V3.0】持仓只数上限已删除（用户口径：持仓只数不限，只限当日新建仓 ≤3 只与总持仓 ≤4 万）
    
    # ---------- 止损止盈 ----------
    # 【V5.0】A1 止损 / A2 止盈 / A3 超期 参数已整段删除（对齐 V25/V24.9：代码不存在）
    'break_drop_ratio': 0.5,          # 【V5.0】破板回落阈值 1.5 → 0.5（v22.8：海欣食品 −1.4% 会被 1.5 漏掉）
    'tick_break_monitor': True,       # tick/秒级破板回落监控
    'tick_break_confirm_sec': 6,      # 【V5.0】回落持续 N 秒仍低于阈值才卖（15 → 6，v22.8；0=立即卖）
    'tick_break_every_sec': 3,        # tick 模式下的巡检节流（秒）
    
    # ---------- 买入条件 ----------
    'min_open_ratio': 0,
    'max_open_ratio': 8.0,
    'min_turnover_rate': 2,
    'min_volume_ratio': 1.2,
    'min_volume_ratio_open': 1.2,   # 【V2.0】开盘 5 分钟内的量比门槛（V16 口径）
    'min_volume_growth': 1.0,
    'ma_period': 5,
    'premium_bull': 1.015,      # 【V2.0】对齐 PTrade v16（原 1.022）
    'premium_bear': 1.010,      # 【V2.0】对齐 PTrade v16（原 1.018）
    'premium_normal': 1.012,    # 【V2.0】对齐 PTrade v16（原 1.019）
    'auction_drop_threshold': 0.3,
    'open_drop_threshold': -0.5,
    
    # ---------- 选股过滤 ----------
    'filter_continuous_gain': {
        'main': {'days': 5, 'max_gain': 60.0},
        'gem': {'days': 3, 'max_gain': 72.0},
        'star': {'days': 3, 'max_gain': 72.0},
    },
    'filter_after_1430_gain': {
        'main': 5.0,
        'gem': 8.0,
        'star': 8.0,
    },
    'filter_amplitude': {
        'main': 16.0,
        'gem': 20.0,
        'star': 20.0,
    },
    'filter_turnover': {
        'main': 24.0,
        'gem': 28.0,
        'star': 28.0,
    },
    'limit_up_threshold': 8.5,
    'strong_stock_min': 6.0,
    'strong_stock_max': 8.5,
    'loose_limit_up_threshold': 8.0,
    'ultra_loose_threshold': 5.0,
    'filter_double_in_month': 95,
    'filter_shrink_rise': True,
    'filter_limit_down_3d': True,
    'filter_st_stock': True,
    'filter_beijing': True,
    'filter_kcb': True,
    'filter_risk_stock': True,
    'risk_open_threshold_main': 5.0,
    'risk_open_threshold_gem_star': 6.0,
    
    # ---------- 市场环境动态参数 ----------
    'market_env_adjust': {
        'bull': {
            'min_open_ratio_offset': 1,
            'max_open_ratio_offset': -1,
            'min_turnover_rate_offset': 1,
            # 【V5.0】stop_profit_ratio_offset 已删（A2 止盈已拆除）
        },
        'bear': {
            'min_open_ratio_offset': -0.5,
            'max_open_ratio_offset': 1,
            'min_turnover_rate_offset': -0.5,
            # 【V5.0】stop_loss_ratio_offset 已删（A1 止损已拆除）
        }
    },
    'hs300_bull_threshold': 1,
    'hs300_bear_threshold': -1,
    'limit_up_count_bull': 80,
    'limit_up_count_bear': 30,
   
    # ---------- 时间参数 ----------
    'time_auction_filter': '09:26:00',
    'time_set_only_buy_false': '09:30:00',
    'time_sell_only': '09:30:05',
    'time_set_only_buy_true': '09:30:10',
    'time_buy_start': '09:30:16',
    'time_buy_second': '09:31:00',
    'time_buy_third': '09:32:00',
    'time_buy_fourth': '09:37:00',
    'time_buy_fifth': '10:29:00',
    'manual_signal_time': '09:30:15',          # 手动跟单提示时间（V5.0 与定盘同步）
    'manual_buy_time': '09:33:16',             # 【新增】手动跟单买点（第二次输出候选股）
    'time_sell_check_interval': 2,
    'time_sell_check_exclude': [(14,56),(14,57),(14,58),(14,59)],
}
   

from jqdata import *
import datetime
import pandas as pd
import time

# ==================== 信号推送（Redis 桥接，可开关） ====================
# 用途：聚宽端产生买卖信号 -> Redis -> 本地 QMT 桥接脚本 -> xtquant 实盘下单
# 注意：聚宽云端策略环境对第三方包和外网访问有限制，若 import redis 失败或
#       连不上 Redis，会自动降级为仅日志提示（不影响策略本身运行）。
#       生产环境请将 redis_host 改为公网 Redis（阿里云/腾讯云等）或自建中转。
SIGNAL_PUSH = {
    'enabled': False,          # 【回测版】回测环境无 Redis，默认关闭信号推送
    'redis_host': '127.0.0.1',   # 聚宽云端请改为公网 Redis 地址
    'redis_port': 6379,
    'redis_db': 0,
    'queue': 'jq:signals',       # 与本地 listen_signals.py 的 SIGNAL_QUEUE 一致
}
_r = None

def _get_redis():
    """惰性创建 Redis 连接；失败返回 None 并停用推送（不阻塞策略）"""
    global _r
    if _r is None:
        try:
            import redis as _redis
            _r = _redis.Redis(host=SIGNAL_PUSH['redis_host'],
                              port=SIGNAL_PUSH['redis_port'],
                              db=SIGNAL_PUSH['redis_db'],
                              decode_responses=True)
            _r.ping()
            log.info("Redis 信号推送已连接: %s:%s", SIGNAL_PUSH['redis_host'], SIGNAL_PUSH['redis_port'])
        except Exception as e:
            log.warn("Redis 连接失败，信号推送停用（策略不受影响）: %s", str(e)[:60])
            _r = False
    return _r if _r else None

def push_signal(action, symbol, volume, price=0, order_type='market', remark=''):
    """推送交易信号到 Redis（symbol 为聚宽格式，桥接端自动转 xtquant 格式）"""
    if not SIGNAL_PUSH['enabled']:
        return
    client = _get_redis()
    if client is None:
        return
    try:
        import json
        signal = {
            'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
            'strategy': 'qiangzhe_hengqiang',
            'symbol': symbol,
            'action': action,          # 'BUY' / 'SELL'
            'order_type': order_type,  # 'market' 市价 / 'limit' 限价
            'price': price,
            'volume': volume,
            'remark': remark,
        }
        client.lpush(SIGNAL_PUSH['queue'], json.dumps(signal, ensure_ascii=False))
        log.info("信号已推送: %s %s %s股 @%s (%s)", action, symbol, volume, price if price else "市价", remark)
    except Exception as e:
        log.warn("信号推送失败: %s", str(e)[:60])

# ==================== 辅助函数 ====================
def get_stock_industry_and_concept(stock_code, query_date):
    cache_key = f"{stock_code}_{query_date}"
    CACHE_TTL = 21600
    if hasattr(g, 'concept_cache') and cache_key in g.concept_cache:
        cached_data, cached_ts = g.concept_cache[cache_key]
        if time.time() - cached_ts < CACHE_TTL:
            return cached_data
    result = {'industry_name': '未知行业', 'concepts': [], 'display_str': ''}
    try:
        industry_df = get_industry(stock_code, date=query_date)
        if stock_code in industry_df:
            industry_info = industry_df[stock_code]
            for level in ['sw_l3', 'sw_l2', 'sw_l1', 'jq_l2', 'jq_l1']:
                val = industry_info.get(level)
                if val:
                    if isinstance(val, str):
                        result['industry_name'] = val
                        break
                    elif isinstance(val, list) and len(val) > 0:
                        item = val[0]
                        if isinstance(item, dict):
                            name = item.get('industry_name')
                            if name:
                                result['industry_name'] = name
                                break
                    elif isinstance(val, dict):
                        name = val.get('industry_name')
                        if name:
                            result['industry_name'] = name
                            break
        concept_df = get_concept(stock_code, date=query_date)
        if stock_code in concept_df:
            concept_data = concept_df[stock_code].get('jq_concept', [])
            if concept_data:
                concepts = []
                for item in concept_data:
                    if isinstance(item, dict):
                        concept_name = item.get('concept_name')
                        if concept_name:
                            concepts.append(concept_name)
                    elif isinstance(item, str):
                        concepts.append(item)
                result['concepts'] = concepts[:5]
        concept_str = '、'.join(result['concepts']) if result['concepts'] else '无概念'
        result['display_str'] = f'[{result["industry_name"]}] [{concept_str}]'
    except:
        result['display_str'] = '[行业获取失败] [概念获取失败]'
    if not hasattr(g, 'concept_cache'):
        g.concept_cache = {}
    g.concept_cache[cache_key] = (result, time.time())
    return result

def _once_log(tag, msg):
    """同一类信息每天只打一次，避免刷屏"""
    try:
        if getattr(g, tag, False):
            return
        setattr(g, tag, True)
    except Exception:
        pass
    log.info(msg)


def st_gate_check(stock, context):
    """【V2.0】ST / 退市 三道校验（对齐 V16 v8），命中或无法确认即拦下。
    返回 (是否拦下, 原因)"""
    try:
        cd = get_current_data()[stock]
    except Exception as e:
        # 【V2.3】取不到实时状态时**放行**（原来直接拦下：数据异常会把全天买单全拦死）
        _once_log('st_gate_nodata', '⚠️ ST校验取不到实时状态，放行: %s | %s' % (stock, str(e)[:30]))
        return False, ''
    if cd is None:
        return False, ''
    if getattr(cd, 'is_st', False):
        return True, '实时状态 ST'
    try:
        nm = get_security_info(stock).display_name
    except Exception:
        nm = ''
    if nm and ('ST' in nm or '退' in nm):
        return True, f'名称含ST/退({nm})'
    try:
        hl, ll = cd.high_limit, cd.low_limit
        if hl and ll and hl > 0 and ll > 0:
            band = (hl - ll) / ((hl + ll) / 2.0) * 100
            if band <= 6.5:
                return True, f'5%涨跌停档({band:.1f}%)'
    except Exception:
        pass
    return False, ''


# ==================== 【V3.2】无未来函数取数助手 ====================
# 背景：`get_price(..., end_date=context.current_dt, count=1, frequency='1d')` 在分钟回测里
#   会把"当日"这根日线（含当天最终 close / 全天 volume）喂给策略 → 未来函数
#   （实测现象：排序退化成"今日涨幅榜"、卖出价=当日收盘价）。
# 统一口径：
#   · 现价 / 今开  → get_current_data() 快照（分钟级，正确）
#   · 昨收 / 历史  → attribute_history（只返回**已完成**的日线，不含当日）
#   · 今日累计量   → 1 分钟 bar 从 09:30 求和到当前时刻
def _last_px(stock):
    """现价（分钟级快照）。取不到返回 0。"""
    try:
        return float(get_current_data()[stock].last_price or 0)
    except Exception:
        return 0.0


def _day_open(stock):
    """今日开盘价（快照 day_open）。"""
    try:
        return float(get_current_data()[stock].day_open or 0)
    except Exception:
        return 0.0


def _pre_close(stock, context=None):
    """昨收。优先 attribute_history（不含当日）；兜底用 get_price(昨日)。取不到返回 0。"""
    try:
        h = attribute_history(stock, 1, '1d', ['close'], skip_paused=True, df=False)
        if h is not None and 'close' in h and len(h['close']) > 0:
            v = float(h['close'][-1])
            if v > 0:
                return v
    except Exception:
        pass
    if context is not None:
        try:
            days = get_trade_days(end_date=context.current_dt.date(), count=2)
            if days is not None and len(days) >= 2:
                df = get_price(stock, end_date=days[-2], count=1, fields=['close'], fq='pre')
                if df is not None and len(df) > 0:
                    return float(df['close'].iloc[0])
        except Exception:
            pass
    return 0.0


def _today_vol_upto_now(stock, context):
    """今日**到当前为止**累计成交量。
    【V5.0a】优先 tick 缓存的当日累计量（tick.frequency 下 09:31 前无 1 分钟 bar，
    15 秒定盘时 bar 求和恒为 0 → 量比恒 0.00）；tick 缓存缺失/过期 → 1 分钟 bar 兜底。"""
    try:
        _tp = getattr(g, '_tick_px', {}).get(stock)
        if _tp and float(_tp.get('vol') or 0) > 0:
            _age = _sec_of(context.current_dt.strftime('%H:%M:%S')) - _sec_of(_tp.get('t', ''))
            if 0 <= _age <= 15:
                return float(_tp['vol'])
    except Exception:
        pass
    try:
        d = context.current_dt.date()
        _start = datetime.datetime.combine(d, datetime.time(9, 30))
        df = get_price(stock, start_date=_start, end_date=context.current_dt, frequency='1m',
                       fields=['volume'], fq='pre', skip_paused=True)
        if df is None or len(df) == 0:
            return 0.0
        return float(df['volume'].sum())
    except Exception:
        return 0.0


def _pace_volume_ratio(stock, context):
    """【V5.0a】节奏量比（真量比口径）：（今日累计量 ÷ 已开盘分钟数）÷（5日均量 ÷ 240）。
    · 已开盘分钟数用**秒级精确值**（tick 15 秒定盘 = 0.25 分钟；原取整钳到 1 分钟会低估 4 倍）
    · 今日累计量走 _today_vol_upto_now（tick 缓存优先，09:31 前无 1 分钟 bar）
    返回 (量比, 已开盘分钟数)；取不到返回 (0.0, 0.0)。"""
    try:
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return 0.0, 0.0
        avg_vol = get_price(stock, end_date=trade_days[0], count=5,
                            fields=['volume'], fq='pre')['volume'].mean()
        today_vol = _today_vol_upto_now(stock, context)
        if avg_vol is None or float(avg_vol) <= 0 or today_vol <= 0:
            return 0.0, 0.0
        now_t = context.current_dt.time()
        _elapsed = (now_t.hour * 3600 + now_t.minute * 60 + now_t.second) - (9 * 3600 + 30 * 60)
        _mins = max(_elapsed, 1) / 60.0
        if _mins > 240:
            _mins = 240.0
        return today_vol * (240.0 / _mins) / float(avg_vol), _mins
    except Exception:
        return 0.0, 0.0


def _last_trade_days(context, n):
    """最近 n 个交易日（含今日），返回 list；取不到返回 []。用 [-1]=今日 [-2]=昨日 [-3]=前日。"""
    try:
        d = get_trade_days(end_date=context.current_dt.date(), count=n)
        return list(d) if d is not None else []
    except Exception:
        return []


def get_stock_board(stock):
    try:
        code = stock.split('.')[0]
        suffix = stock.split('.')[1] if '.' in stock else ''
        if (code.startswith('60') and suffix == 'XSHG') or \
           ((code.startswith('000') or code.startswith('001')) and suffix == 'XSHE'):
            return 'main'
        elif code.startswith(('300', '301', '302')) and suffix == 'XSHE':
            return 'gem'
        elif code.startswith('688') and suffix == 'XSHG':
            return 'star'
        else:
            return 'unknown'
    except:
        return 'unknown'

def calculate_continuous_gain(stock, end_date, days):
    try:
        hist = get_price(stock, end_date=end_date, count=days+1, fields=['close'], fq='pre', skip_paused=True)
        if len(hist) < days + 1:
            return -999
        start_price = hist['close'].iloc[0]
        end_price = hist['close'].iloc[-1]
        total_gain = (end_price - start_price) / start_price * 100
        return round(total_gain, 2)
    except:
        return -999

def filter_by_continuous_gain(stock, end_date):
    try:
        stock_name = get_security_info(stock).display_name
    except:
        stock_name = "未知名称"
    board = get_stock_board(stock)
    cfg = g.filter_continuous_gain.get(board)
    if not cfg:
        return True, "未知板块，跳过涨幅过滤", stock_name
    check_days = cfg['days']
    max_gain = cfg['max_gain']
    total_gain = calculate_continuous_gain(stock, end_date, check_days)
    if total_gain == -999:
        return True, f"无法计算{check_days}天涨幅，跳过过滤", stock_name
    elif total_gain > max_gain:
        return False, f"{board}连续{check_days}天涨幅{total_gain}% > {max_gain}%", stock_name
    else:
        return True, f"{board}连续{check_days}天涨幅{total_gain}% ≤ {max_gain}%", stock_name

def filter_after_1430_gain(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        gain_thresholds = g.filter_after_1430_gain
        if board not in gain_thresholds:
            return True, "未知板块，跳过尾盘涨幅过滤", stock_name
        threshold = gain_thresholds[board]

        date_obj = pd.Timestamp(date)
        time_1430 = pd.Timestamp.combine(date_obj.date(), pd.Timestamp('14:30:00').time())
        end_time = pd.Timestamp.combine(date_obj.date(), pd.Timestamp('15:00:00').time())

        min1_data = get_price(stock, start_date=time_1430, end_date=end_time, frequency='1m', fields=['close'], fq='pre', skip_paused=True)
        if min1_data.empty or len(min1_data) < 2:
            min5_data = get_price(stock, start_date=time_1430, end_date=end_time, frequency='5m', fields=['close'], fq='pre', skip_paused=True)
            if min5_data.empty or len(min5_data) < 2:
                daily_data = get_price(stock, end_date=date, count=1, fields=['open','close'], fq='pre')
                if daily_data.empty:
                    return True, "无尾盘数据，默认通过", stock_name
                price_1430 = daily_data['open'].iloc[0]
                price_close = daily_data['close'].iloc[0]
            else:
                price_1430 = min5_data['close'].iloc[0]
                price_close = min5_data['close'].iloc[-1]
        else:
            price_1430 = min1_data['close'].iloc[0]
            price_close = min1_data['close'].iloc[-1]

        gain = (price_close - price_1430) / price_1430 * 100
        gain = round(gain, 2)

        if gain > threshold:
            log.error(f"❌ 尾盘过滤淘汰: {stock} {stock_name} | {board} | 14:30后涨幅{gain}% > {threshold}%")
            return False, f"{board}14:30后涨幅{gain}% > {threshold}%", stock_name
        else:
            return True, f"{board}14:30后涨幅{gain}% ≤ {threshold}%", stock_name
    except:
        return True, f"过滤异常，默认通过", "未知名称"

def filter_by_amplitude(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        amp_thresholds = g.filter_amplitude
        if board not in amp_thresholds:
            return True, "未知板块，跳过振幅过滤", stock_name
        threshold = amp_thresholds[board]
        hist = attribute_history(stock, 1, '1d', fields=['high', 'low', 'close'], skip_paused=True, df=True)
        if hist.empty:
            return True, "无振幅数据", stock_name
        high = hist['high'].iloc[-1]
        low = hist['low'].iloc[-1]
        close = hist['close'].iloc[-1]
        if close == 0:
            return True, "昨日收盘价为0", stock_name
        amplitude = (high - low) / close * 100
        amplitude = round(amplitude, 2)
        if amplitude >= threshold:
            return False, f"{board}昨日振幅{amplitude}% ≥ {threshold}%", stock_name
        else:
            return True, f"{board}昨日振幅{amplitude}% < {threshold}%", stock_name
    except:
        return True, f"振幅异常", stock_name

def filter_by_turnover(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        turnover_thresholds = g.filter_turnover
        if board not in turnover_thresholds:
            return True, "未知板块，跳过换手率过滤", stock_name
        threshold = turnover_thresholds[board]
        turnover = None
        try:
            turnover_df = get_money_flow(stock, start_date=date, end_date=date)
            if not turnover_df.empty and 'turnover_rate' in turnover_df.columns:
                turnover = turnover_df['turnover_rate'].iloc[0]
        except:
            pass
        if turnover is None:
            try:
                vol_data = attribute_history(stock, 1, '1d', fields=['volume'], skip_paused=True, df=True)
                if vol_data.empty:
                    return False, "无成交量数据", stock_name
                volume = vol_data['volume'].iloc[-1]
                q = query(valuation.circulating_cap).filter(valuation.code == stock)
                df = get_fundamentals(q, date=date)
                if df.empty:
                    return False, "无流通股本", stock_name
                float_share = df['circulating_cap'].iloc[0] * 10000
                if float_share <= 0:
                    return False, "流通股本异常", stock_name
                turnover = volume / float_share * 100
            except:
                return False, "计算异常", stock_name
        if turnover is None:
            return False, "无法获取换手率", stock_name
        turnover = round(float(turnover), 2)
        if turnover >= threshold:
            return False, f"{board}昨日换手率{turnover}% ≥ {threshold}%", stock_name
        else:
            return True, f"{board}昨日换手率{turnover}% < {threshold}%", stock_name
    except:
        log.error(f"换手率过滤异常 {stock}")
        return False, "过滤异常", stock_name

def is_double_in_month(stock, context):
    try:
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return False
        yesterday = trade_days[0]
        hist = attribute_history(stock, 20, '1d', fields=['close'], skip_paused=True, df=True)
        if len(hist) < 20:
            return False
        old_price = hist['close'].iloc[0]
        today_price = hist['close'].iloc[-1]
        if old_price <= 0:
            return False
        gain = (today_price - old_price) / old_price * 100
        return gain >= g.filter_double_in_month
    except:
        return False

def has_limit_down_in_last_3days(stock, date):
    if not g.filter_limit_down_3d:
        return True, "未启用过滤", ""
    try:
        stock_name = get_security_info(stock).display_name
        hist = attribute_history(stock, 3, '1d', fields=['close', 'low_limit'], skip_paused=True, df=True)
        if len(hist) < 3:
            return True, "无足够数据", stock_name
        for i in range(len(hist)):
            close = hist['close'].iloc[i]
            low_limit = hist['low_limit'].iloc[i]
            if close <= low_limit * 1.005:
                return False, f"近3日有跌停", stock_name
        return True, "近3日无跌停", stock_name
    except:
        return True, f"跌停异常", stock_name

def is_continuous_shrink_rise(stock, date):
    if not g.filter_shrink_rise:
        return True, "未启用过滤", ""
    try:
        stock_name = get_security_info(stock).display_name
        hist = attribute_history(stock, 3, '1d', fields=['close', 'volume'], skip_paused=True, df=True)
        if len(hist) < 3:
            return True, "无足够数据", stock_name
        for i in range(1, 3):
            if hist['close'].iloc[i] <= hist['close'].iloc[i-1]:
                return True, "非连续上涨", stock_name
        for i in range(1, 3):
            if hist['volume'].iloc[i] >= hist['volume'].iloc[i-1]:
                return True, "非连续缩量", stock_name
        return False, "连续3日缩量上涨", stock_name
    except:
        return True, f"缩量异常", stock_name

def is_risk_stock(context, stock):
    if not g.filter_risk_stock:
        return False
    try:
        stock_name = get_security_info(stock).display_name
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return False
        yesterday = trade_days[0]
        df = attribute_history(stock, 3, '1d', fields=['close', 'volume', 'high_limit'], skip_paused=True, df=True)
        if df is None or len(df) < 3:
            return False
        close_yest = df['close'].iloc[-1]
        vol_yest = df['volume'].iloc[-1]
        vol_beyest = df['volume'].iloc[-2]
        high_limit = df['high_limit'].iloc[-1]
        is_limit_up = (close_yest >= high_limit - 0.01)
        is_vol_big = (vol_yest >= vol_beyest * 1.8)
        df20 = attribute_history(stock, 20, '1d', fields=['close'], skip_paused=True, df=True)
        if df20 is not None and len(df20) >= 20:
            rise_rate = (df20['close'].iloc[-1] / df20['close'].iloc[0] - 1)
        else:
            rise_rate = 0
        is_high = (rise_rate > 0.30)
        is_danger_yest = is_limit_up and is_vol_big and is_high
        if not is_danger_yest:
            return False
        current_data = get_current_data()[stock]
        open_price = current_data.day_open
        pre_close = close_yest
        open_rate = (open_price / pre_close - 1) * 100
        board = get_stock_board(stock)
        if board == 'main':
            threshold = g.risk_open_threshold_main
        else:
            threshold = g.risk_open_threshold_gem_star
        if open_rate >= threshold:
            log.info(f"⚠️ 风险股票 {stock} {stock_name}：昨日高位放量涨停+今日高开{open_rate:.1f}%")
            return True
        return False
    except:
        return False

def is_limit_up_simple(stock, date):
    try:
        hist = get_price(stock, end_date=date, count=2, fields=['close','high_limit'], fq='pre')
        if len(hist) < 2:
            return False
        yc = hist['close'].iloc[-1]
        yl = hist['high_limit'].iloc[-1]
        pc = hist['close'].iloc[-2]
        change = (yc - pc)/pc*100
        if change > g.limit_up_threshold or abs(yc - yl)/yl < 0.006:
            return True
        return False
    except:
        return False

def is_strong_stock(stock, date):
    try:
        hist = get_price(stock, end_date=date, count=2, fields=['close'], fq='pre')
        if len(hist) < 2:
            return False
        change = (hist['close'].iloc[-1] - hist['close'].iloc[-2])/hist['close'].iloc[-2] * 100
        return g.strong_stock_min <= change < g.strong_stock_max
    except:
        return False

def find_limit_up_loose(stocks, date):
    limit_stocks = []
    for stock in stocks:
        try:
            if g.filter_st_stock and is_st_stock(stock):
                continue
            if g.filter_beijing and '.BJ' in stock:
                continue
            if g.filter_kcb and get_stock_board(stock) == 'star':
                continue
            hist = get_price(stock, end_date=date, count=2, fields=['close','high'], fq='pre')
            if len(hist) < 2:
                continue
            yc = hist['close'].iloc[-1]
            yh = hist['high'].iloc[-1]
            pc = hist['close'].iloc[-2]
            change = (yc - pc)/pc*100
            if change > g.loose_limit_up_threshold or (abs(yh - yc)/yc < 0.01 and change > g.strong_stock_min):
                pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, date)
                if not pass_filter:
                    continue
                pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, date)
                if not pass_1430_filter:
                    continue
                pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, date)
                if not pass_amp_filter:
                    continue
                pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, date)
                if not pass_turnover_filter:
                    continue
                pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, date)
                if not pass_limitdown_filter:
                    continue
                pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, date)
                if not pass_shrink_filter:
                    continue
                limit_stocks.append(stock)
        except:
            continue
    return limit_stocks

def find_limit_up_ultra_loose(stocks, date):
    limit_stocks = []
    for stock in stocks:
        try:
            if g.filter_st_stock and is_st_stock(stock):
                continue
            if g.filter_beijing and '.BJ' in stock:
                continue
            if g.filter_kcb and get_stock_board(stock) == 'star':
                continue
            hist = get_price(stock, end_date=date, count=2, fields=['close'], fq='pre')
            if len(hist) < 2:
                continue
            change = (hist['close'].iloc[-1] - hist['close'].iloc[-2])/hist['close'].iloc[-2] * 100
            if change > g.ultra_loose_threshold:
                pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, date)
                if not pass_filter:
                    continue
                pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, date)
                if not pass_1430_filter:
                    continue
                pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, date)
                if not pass_amp_filter:
                    continue
                pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, date)
                if not pass_turnover_filter:
                    continue
                pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, date)
                if not pass_limitdown_filter:
                    continue
                pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, date)
                if not pass_shrink_filter:
                    continue
                limit_stocks.append(stock)
        except:
            continue
    return limit_stocks

def is_st_stock(stock):
    try:
        name = get_security_info(stock).display_name
        return 'ST' in name or '*ST' in name or '退' in name
    except:
        return True

def is_limit_up_down(stock):
    try:
        # 【V3.2】原实现不传 end_date → 取到"当日"（未来函数；09:26 盘前还会被 avoid_future_data 拦）
        #   改用 attribute_history（只返回已完成日线）
        data = attribute_history(stock, 1, '1d', ['open', 'high_limit', 'low_limit'],
                                 skip_paused=True, df=False)
        if data is None or 'open' not in data or len(data['open']) == 0:
            return True
        op = data['open'][-1]
        hl = data['high_limit'][-1]
        ll = data['low_limit'][-1]
        if abs(op - hl) < 0.001 or abs(op - ll) < 0.001:
            return True
        return False
    except:
        return True

def check_basic_quality(stock, context):
    try:
        if is_limit_up_down(stock):
            return False
        # 【V3.2】今日开盘走快照（原来 get_price 日线口径：盘前取不到当日、盘中拿到的是含当日最终值的 bar）
        _snap_open = _day_open(stock)
        return _snap_open > 0          # 有今开 = 可交易（原判断 not today_tick.empty）
    except:
        return False

def calculate_turnover_rate(stock, date):
    try:
        vol_data = get_price(stock, end_date=date, count=1, fields=['volume'], fq='pre')
        if vol_data.empty:
            return 0.0
        volume = vol_data['volume'].iloc[0]
        stock_info = get_security_info(stock)
        float_share = stock_info.float_share if hasattr(stock_info, 'float_share') else 0
        if float_share == 0:
            return 0.0
        return (volume / (float_share * 10000)) * 100
    except:
        return 0.0

def check_turnover_volume(stock, context):
    try:
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=3)
        if len(trade_days) < 3:
            return True, "无足够数据"
        # 【V3.2】原来把 trade_days[0] 当昨日、[1] 当前日 —— count=3 时返回 [前日,昨日,今日]，
        #   两个都错位 → 换手率读的是前日、成交量对比只剩 1 根（iloc[-2] 越界被吞 → 该项检查实际是死的）。
        #   统一用负索引：[-2]=昨日、[-3]=前日（与 count 无关，不会错位）。
        yesterday = trade_days[-2]
        day_before_yesterday = trade_days[-3]
        turnover_df = get_money_flow(stock, start_date=yesterday, end_date=yesterday)
        if turnover_df.empty or 'turnover_rate' not in turnover_df.columns:
            turnover_rate = calculate_turnover_rate(stock, yesterday)
        else:
            turnover_rate = turnover_df['turnover_rate'].iloc[0]
        if 0 < turnover_rate < g.min_turnover_rate:
            return False, f"换手率{turnover_rate:.2f}% < {g.min_turnover_rate}%"
        vol_df = get_price(stock, start_date=day_before_yesterday, end_date=yesterday, fields=['volume'], fq='pre')
        if len(vol_df) < 2:
            return True, "无成交量数据"
        # 【V3.3】守卫 0/0（停牌/无量日会算成 NaN 并刷 RuntimeWarning）
        _v_prev = float(vol_df['volume'].iloc[-2])
        vol_growth = (float(vol_df['volume'].iloc[-1]) / _v_prev) if _v_prev > 0 else 0.0
        if vol_growth < g.min_volume_growth:
            return False, f"成交量增长{vol_growth:.2f} < {g.min_volume_growth}"
        if context.current_dt.time() > datetime.time(9, 30):
            try:
                # 【V2.0 修正 · 对齐 V16】"节奏量比"：今日累计量 ÷ 已开盘分钟数 × 240 = 折算全天量，
                # 再比 5 日均量。【V5.0a】走 _pace_volume_ratio 统一口径 —— 分钟数秒级精确
                # （15 秒定盘 = 0.25 分钟，原钳到 1 分钟会低估 4 倍），今日累计量 tick 缓存优先。
                volume_ratio, _mins = _pace_volume_ratio(stock, context)
                if 0 < volume_ratio:
                    _thr = g.min_volume_ratio_open if _mins <= 5 else g.min_volume_ratio
                    if volume_ratio < _thr:
                        return False, f"量比{volume_ratio:.2f} < {_thr}"
            except Exception:
                pass
        return True, "量能达标"
    except:
        return True, "量能校验异常"

def get_current_change(stock, context):
    try:
        # 【V3.2】现价走快照、昨收走 attribute_history（原来两个都用"当日日线"=未来函数）
        current_price = _last_px(stock)
        yesterday_close = _pre_close(stock, context)
        if current_price <= 0 or yesterday_close <= 0:
            return 0
        return (current_price - yesterday_close) / yesterday_close * 100
    except:
        return 0

def is_real_time_drop(context, stock):
    try:
        stock_name = get_security_info(stock).display_name
        current_data = get_current_data()[stock]
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return False, "无昨日数据"
        yesterday_close = get_price(stock, end_date=trade_days[0], count=1, fields=['close'], fq='pre')['close'].iloc[0]
        open_price = current_data.day_open
        current_price = current_data.last_price
        if open_price <= 0 or current_price <= 0:
            return False, "价格异常"
        open_ratio = (open_price - yesterday_close) / yesterday_close * 100
        drop_ratio = (open_price - current_price) / open_price * 100
        if open_ratio > 0 and current_price < open_price and drop_ratio > g.auction_drop_threshold:
            log.debug(f"❌ 实时高开低走：{stock} {stock_name} 高开{open_ratio:.1f}%，开盘回落{drop_ratio:.1f}%")
            return True, f"回落{drop_ratio:.1f}%"
        return False, f"高开{open_ratio:.1f}%"
    except:
        return False, "检测异常"

# 【V5.0】check_volume_drop（A4 放量下跌判据）已整段删除（对齐 V25/V24.9）

# ==================== 买入条件检查 ====================
def check_buy_condition(stock, context):
    """返回 (是否可买, 原因, 辅助数据)"""
    try:
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
        if len(trade_days) < 2:
            return False, "无昨日数据", {}
        yesterday = trade_days[-2]
        yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
        if yesterday_data.empty:
            return False, "无数据/停牌", {}
        # 【V3.2】现价/今开走快照（原来读"当日日线 open/close" → current_ratio = 当日最终涨幅 = 未来函数）
        open_p = _day_open(stock)
        last_p = _last_px(stock)
        yes_close = float(yesterday_data['close'].iloc[0])
        if open_p <= 0 or last_p <= 0 or yes_close <= 0:
            return False, "无数据/停牌", {}
        open_ratio = (open_p - yes_close) / yes_close * 100
        current_ratio = (last_p - yes_close) / yes_close * 100
        
        vol_ok, vol_msg = check_turnover_volume(stock, context)
        if not vol_ok:
            return False, vol_msg, {}
        
        is_drop, drop_msg = is_real_time_drop(context, stock)
        if is_drop:
            return False, f"高开低走 {drop_msg}", {}
        
        if not (g.min_open_ratio <= open_ratio <= g.max_open_ratio):
            return False, f"开盘涨幅{open_ratio:.2f}% 不在区间", {}
        
        if current_ratio > g.max_open_ratio + 2:
            return False, f"实时涨幅{current_ratio:.2f}% > {g.max_open_ratio+2}%", {}
        
        if is_double_in_month(stock, context):
            return False, "近一个月翻倍", {}
        
        extra = {
            'open_ratio': open_ratio,
            'current_ratio': current_ratio,
            'yesterday_close': yes_close,
            'open_price': open_p,
            'current_price': last_p,
            'vol_msg': vol_msg,
        }
        if g.market_env == "bull":
            extra['premium'] = g.premium_bull
        elif g.market_env == "bear":
            extra['premium'] = g.premium_bear
        else:
            extra['premium'] = g.premium_normal
        return True, "满足买入条件", extra
    except Exception as e:
        return False, f"检查异常:{str(e)[:30]}", {}

# ==================== 手动跟单提示函数（优化版：前12只，一行一只） ====================
def manual_signal(context):
    """输出最终候选股清单，供手动跟单参考（仅显示前12只，紧凑一行）"""
    if not g.candidate_stocks:
        log.info("⚠️ 【手动跟单】当前无候选股，跳过输出")
        return
    
    log.info("=" * 60)
    log.info(f"📢 【手动跟单提示】时间: {context.current_dt.strftime('%H:%M:%S')}")
    log.info("下面列出满足实时买入条件的股票（前12只），可手动下单（策略也将自动买入部分）")
    log.info("-" * 60)
    
    buy_list = []
    query_date = context.current_dt.date()
    for stock in g.candidate_stocks:
        if stock in context.portfolio.positions or stock in g.bought_stocks:
            continue
        can_buy, reason, extra = check_buy_condition(stock, context)
        if not can_buy:
            continue
        try:
            stock_name = get_security_info(stock).display_name
            board = get_stock_board(stock)
            current_data = get_current_data()[stock]
            current_price = current_data.last_price
            high_limit = current_data.high_limit
            suggested_limit = min(current_price * extra['premium'], high_limit)
            concept_info = get_stock_industry_and_concept(stock, query_date)
            concept_display = concept_info['display_str']
            # 量比【V5.0a】走 _pace_volume_ratio 统一口径（真量比：折算全天量 ÷ 5 日均量；
            # 09:30:15 定盘时今日累计量取 tick 缓存，分钟数秒级精确 → 不再恒为 0.00）
            try:
                volume_ratio, _ = _pace_volume_ratio(stock, context)
            except:
                volume_ratio = 0
            buy_list.append({
                'code': stock,
                'name': stock_name,
                'board': board,
                'price': current_price,
                'open_price': extra['open_price'],           # 新增：开盘价
                'gain': extra['current_ratio'],
                'open_gain': extra['open_ratio'],
                'volume_ratio': volume_ratio,
                'suggested_limit': suggested_limit,
                'high_limit': high_limit,
                'concept': concept_display,
                'reason': reason
            })
        except Exception as e:
            continue
    buy_list.sort(key=lambda x: x['gain'] - x['open_gain'], reverse=True)
    
    if not buy_list:
        log.info("✅ 暂无股票满足实时买入条件")
        log.info("=" * 60)
        return
    
    display_limit = 12   # 只显示前12只
    total = len(buy_list)
    log.info(f"🎯 共筛选出 {total} 只可买入股票（按拉升强度排序），仅显示前 {display_limit} 只:")
    for idx, item in enumerate(buy_list[:display_limit], 1):
        # 修改输出：增加开盘价显示
        log.info(f"【{idx}】{item['code']} {item['name']:4s} | 涨幅:{item['gain']:5.2f}% (开:{item['open_gain']:5.2f}%) | 量比:{item['volume_ratio']:5.2f} 开盘:{item['open_price']:.2f} 现价:{item['price']:.2f} | {item['concept']}")
    
    if total > display_limit:
        log.info(f"  ... 其余 {total - display_limit} 只已省略，可调整手动跟单阈值或放宽过滤条件查看详情")
    
    log.info("💡 提示: 策略将自动买入部分股票，也可根据上述信息手动下单")
    log.info("=" * 60)

# ==================== 自动交易函数 ====================
def _amount_slots(context):
    """剩余额度能再买几只。BACKTEST_UNLIMITED=True 时不做金额限制 → 给足名额。"""
    if BACKTEST_UNLIMITED:
        return 999
    # 【V6.1】资金最大化档：金额限制全部取消 → 名额不再受金额约束（只数仍由 MAX_BUY_PER_DAY_STOCKS 管）
    if CASH_MAX_MODE == 'on':
        return 999
    try:
        used = 0.0
        for _s, _p in context.portfolio.positions.items():
            used += float(getattr(_p, 'value', 0) or 0)
        avail = max(0.0, MAX_TOTAL_POSITION_AMOUNT - used)
        n = int(avail // TARGET_AMOUNT_PER_STOCK)
        if avail - n * TARGET_AMOUNT_PER_STOCK >= MIN_AMOUNT_PER_STOCK:
            n += 1
        return n
    except Exception:
        return 0


def _slots_left(context):
    """总名额 = min(只数名额, 金额名额)。BACKTEST_UNLIMITED=True → 10000（等于不限）。"""
    if BACKTEST_UNLIMITED:
        return 10000
    n_cnt = 10 ** 9 if BASE_MAX_HOLD <= 0 else max(0, BASE_MAX_HOLD - len(context.portfolio.positions))
    return max(0, min(n_cnt, _amount_slots(context)))


def _strength_now(stock, context):
    """【V3.1 修3】强度 =（现价 − 今开）/ 昨收 × 100。
    取数口径与 `check_buy_condition` / 手动跟单列表**完全一致**（那两处已被聚宽验证过）：
      · 今日 现价/今开：get_price(end_date=当前时刻, count=1, fields=['open','close'])
      · 昨收：get_trade_days(end_date=今日, count=2)[0] + get_price(end_date=昨日, count=1)
    ⚠️ 曾经写错（get_price(count=2, end_date=今天) 在 09:30 返回【前天,昨天】）→ 把昨天开盘当今开，
       排序全乱 → 可买宇宙挑出 -10% 的票。这个口径必须保持不变。"""
    try:
        # 【V3.2】现价/今开走快照、昨收走"不含当日"的历史 —— 原来这段读的是"当日日线 open/close"
        #   （= 当日最终收盘口径，就是未来函数本身）。
        open_p = _day_open(stock)
        last_p = _last_px(stock)
        yes_close = _pre_close(stock, context)
        if yes_close <= 0 or open_p <= 0:
            return None
        return (last_p - open_p) / yes_close * 100.0
    except Exception:
        return None


def _pool_rank(context, stocks):
    """全池强度排序（强度高→低），与 PTrade v18 的排序口径一致。"""
    out = []
    for stk in stocks:
        _sv = _strength_now(stk, context)
        if _sv is not None:
            out.append((stk, _sv))
    out.sort(key=lambda kv: kv[1], reverse=True)
    return out


def buy_decision(context):
    """【V3.1 回测版】定盘那一格：全池强度排序 → 只买前 MAX_BUY_RANK 名 → 通过买入条件的
    按强度依次下单（BACKTEST_UNLIMITED=True 时：不限制只数/金额/股数，仓位=可用资金等权）→
    买完即停，之后当日不再买入。"""
    # 【V6.0·市场门控】开盘前市场判定命中 → 今日不开新仓（卖出/止损链路完全不受影响）
    try:
        _gb, _gwhy = market_gate_blocked(context)
    except Exception as _e:
        _gb, _gwhy = False, ""
        log.info("⚠️ 【V6.0·市场门控】判定异常（不拦，放行）：%s" % str(_e)[:60])
    if _gb:
        if not getattr(g, 'gate_block_logged', False):
            g.gate_block_logged = True
            log.info("🛑 【V6.0·市场门控】%s → 今日不开新仓（持仓卖出/止损照常）" % _gwhy)
        return
    if STOP_BUY_AFTER_OPEN and getattr(g, 'open_buy_done', False):
        _once_log('buy_done', '🛑 当日买入已结束（定盘那一格已完成）→ 本轮不买')
        return
    cash = context.portfolio.available_cash
    if cash < 1000:
        log.info("🚫 不买：可用资金不足 %.0f 元" % cash)
        return
    if (not BACKTEST_UNLIMITED) and g.bought_today_count >= MAX_BUY_PER_DAY_STOCKS:
        return
    slots = _slots_left(context)
    if slots <= 0:
        return
    # 【V5.0·v20.1】当日已卖出的票禁止买回（修"卖飞又买回"白亏 2~4% 价差）
    _sold_today = _sold_today_codes()
    available_stocks = [s for s in g.rebuy_candidates
                        if s not in context.portfolio.positions and s not in g.bought_stocks
                        and s not in _sold_today]
    if not available_stocks:
        log.info("🚫 不买：候选池里没有可下单的标的（候选%d只，持仓%d只，今日已买%d只）"
                 % (len(g.rebuy_candidates), len(context.portfolio.positions),
                    getattr(g, 'bought_today_count', 0)))
        return

    # ① 全池强度排序（当天第一次买入决策时算一次并冻结 → "只买前 N 名"）
    if not getattr(g, 'top_rank_codes', None):
        _ranked = _pool_rank(context, available_stocks)
        g.top_rank_codes = [c for c, _ in _ranked[:int(MAX_BUY_RANK)]]
        log.info("🔝 可买宇宙（全池强度前%d名，共排序 %d 只）: %s"
                 % (int(MAX_BUY_RANK), len(_ranked),
                    '、'.join('%s(强度%+.2f)' % (c, v) for c, v in _ranked[:int(MAX_BUY_RANK)]) or '（空）'))
    _uni = set(g.top_rank_codes or [])
    if not _uni:
        # 【V3.1 降级】强度排序取不到任何值（数据接口异常/停牌全池）→ 不做"前 5 名"过滤，
        #   否则会整天一笔不买，且日志会让人以为是"选不出票"。宁可放宽，也要留下记录。
        log.info("⚠️ 全池强度排序取不到值 → 本次跳过『只买前%d名』过滤（候选 %d 只按原顺序买入）"
                 % (int(MAX_BUY_RANK), len(available_stocks)))
    else:
        available_stocks = [s for s in available_stocks if s in _uni]
        if not available_stocks:
            log.info("🚫 可买宇宙为空（候选都不在前%d名内）→ 本轮不买" % int(MAX_BUY_RANK))
            return

    buy_candidates = []
    for stock in available_stocks:
        _reb, _rbw = v20_rebuy_blocked(stock)        # 【V5.0·v20.1】禁买回守卫
        if _reb:
            log.info("🚫 跳过 %s：%s" % (stock, _rbw))
            continue
        if is_double_in_month(stock, context):
            continue
        is_drop, _ = is_real_time_drop(context, stock)
        if is_drop:
            continue
        buy_signal, reason, extra = check_buy_condition(stock, context)
        if buy_signal:
            buy_candidates.append((stock, reason, extra))
        else:
            log.info("   ✗ %s 未通过买入条件：%s" % (stock, str(reason)[:60]))
    if not buy_candidates:
        log.info("🚫 不买：可买宇宙内 %d 只全部未通过买入条件" % len(available_stocks))
        return

    def get_gain_diff(item):
        stock, _, extra = item
        return extra.get('current_ratio', 0) - extra.get('open_ratio', 0)

    buy_candidates.sort(key=get_gain_diff, reverse=True)
    if BACKTEST_UNLIMITED:
        final_buy_num = len(buy_candidates)                      # 不限制只数：通过条件的全买
    else:
        final_buy_num = int(min(slots, MAX_BUY_PER_DAY_STOCKS - g.bought_today_count,
                                len(buy_candidates)))
    log.info("📊 买入漏斗: 待买池%d只 → 通过买入条件%d只 → 本轮要买%d只%s"
             % (len(available_stocks), len(buy_candidates), final_buy_num,
                '（回测无限制：等权分配可用资金）' if BACKTEST_UNLIMITED else
                '（名额%d / 当日剩%d）' % (slots, MAX_BUY_PER_DAY_STOCKS - g.bought_today_count)))
    if final_buy_num <= 0:
        return

    # ② 一次报满（同一格内排序 + 报单）
    g.sizing_n = final_buy_num
    _done = []
    for i, (stock, reason, extra) in enumerate(buy_candidates[:final_buy_num]):
        # 【V6.1·资金最大化】逐只按「剩余只数」重算预算：第 1 只 用 现金÷3、第 2 只 用 现金÷2、
        #   最后一只 用掉余下全部现金 ⇒ 三只合计≈吃满可用资金（只在资金最大化档生效，不影响其它档）
        if CASH_MAX_MODE == 'on' and not BACKTEST_UNLIMITED:
            g.sizing_n = max(1, final_buy_num - i)
        if execute_buy(stock, context, extra):
            _done.append(stock)
    if getattr(g, 'open_requested', None) is None:
        g.open_requested = set(_done)

    # ③ 定盘结束 → 当日不再买入（"排序后立即买，不能慢"）
    if STOP_BUY_AFTER_OPEN:
        g.open_buy_done = True
        log.info("🛑 定盘完成（同一格内排序+报单，已报 %d 只）→ 当日买入结束，之后不再尝试买入" % len(_done))


def execute_buy(stock, context, extra):
    # 【V3.1 修2·务必保留】先给这两个量默认值：它们只在 BACKTEST_UNLIMITED=False 的分支里
    #   被重新赋值，先定义可保证任何日志/表达式引用它们时都不会再出现
    #   "local variable 'day_left' referenced before assignment"（聚宽实测踩过）。
    day_left = 0.0
    total_left = 0.0
    try:
        if stock in context.portfolio.positions or stock in g.bought_stocks:
            return False
        # 【V5.0·v20.1】execute_buy 最内层兜底：当日已卖出的票禁止买回
        _reb, _rbw = v20_rebuy_blocked(stock)
        if _reb:
            log.info("🚫 买入兜底拦截 %s：%s" % (stock, _rbw))
            return False
        current_data = get_current_data()[stock]
        current_price = current_data.last_price
        high_limit = current_data.high_limit
        if current_price >= high_limit - 0.001:
            stock_name = get_security_info(stock).display_name
            log.info(f"🚫 放弃买入 {stock} {stock_name}：已涨停")
            return False
        if current_price <= 0:
            return False
        available_cash = context.portfolio.available_cash
        if available_cash < 100 or _slots_left(context) <= 0:
            return False
        # 【V3.1】仓位规则
        #   BACKTEST_UNLIMITED=True（回测）：不做任何金额/股数限制 → 本轮可用资金等权分配
        #   False：单只 ≤ TARGET_AMOUNT_PER_STOCK、当日 ≤ MAX_BUY_AMOUNT_PER_DAY、
        #          总持仓 ≤ MAX_TOTAL_POSITION_AMOUNT、股数 ≤ MAX_SHARES_PER_STOCK
        _n = max(1, int(getattr(g, 'sizing_n', 1) or 1))
        _why = ''
        if BACKTEST_UNLIMITED:
            # 【V3.1】回测无限制：不做金额/股数限制，本轮可用资金等权分配
            budget = available_cash / _n
            buy_amount = int(budget / current_price / 100) * 100
            _why = "可用 %.0f 元 / 本轮 %d 只 → 每股预算 %.0f 元" % (available_cash, _n, budget)
        elif CASH_MAX_MODE == 'on':
            # 【V6.1·资金最大化】去掉全部「股票金额限制」：当日只数仍 ≤ MAX_BUY_PER_DAY_STOCKS，
            #   单只金额 / 当日金额 / 总持仓金额 三个上限全取消 → 每只预算 = 本轮可用现金 ÷ 本轮只数（吃满资金）
            budget = available_cash * CASH_MAX_RESERVE / _n
            buy_amount = int(budget / current_price / 100) * 100
            if MAX_SHARES_PER_STOCK > 0:
                _cap_sh = max(100, int(MAX_SHARES_PER_STOCK / 100) * 100)
                buy_amount = min(buy_amount, _cap_sh)
            _why = ("资金最大化档：可用 %.0f 元 × 预留%.3f / 本轮 %d 只 → 每股预算 %.0f 元（无单只/当日/总持仓金额上限）"
                    % (available_cash, CASH_MAX_RESERVE, _n, budget))
        else:
            used_val = 0.0
            for _s2, _p2 in context.portfolio.positions.items():
                used_val += float(getattr(_p2, 'value', 0) or 0)
            total_left = MAX_TOTAL_POSITION_AMOUNT - used_val
            day_left = MAX_BUY_AMOUNT_PER_DAY - float(getattr(g, 'bought_amount_today', 0.0) or 0.0)
            budget = min(TARGET_AMOUNT_PER_STOCK, day_left, total_left, available_cash)
            buy_amount = int(budget / current_price / 100) * 100
            if MAX_SHARES_PER_STOCK > 0:
                _cap_sh = max(100, int(MAX_SHARES_PER_STOCK / 100) * 100)
                buy_amount = min(buy_amount, _cap_sh)
            _why = ("单只上限 %.0f / 当日剩余 %.0f / 总持仓剩余 %.0f / 可用 %.0f"
                    % (TARGET_AMOUNT_PER_STOCK, day_left, total_left, available_cash))
            if buy_amount * current_price > TARGET_AMOUNT_PER_STOCK * 1.2:
                log.info(f"🚫 放弃买入 {stock}：{buy_amount}股 × {current_price:.2f} = "
                         f"{buy_amount * current_price:.0f} 元，超过单只上限 {TARGET_AMOUNT_PER_STOCK:.0f} 元")
                return False
        if buy_amount < 100:
            # 【V3.1 修·务必保留】原来这里引用了只在 else 分支赋值的 day_left →
            #   聚宽实测报 "local variable 'day_left' referenced before assignment"，
            #   3 只票全部买入失败。现在改用两分支都赋值的 _why。
            log.info("🚫 放弃买入 %s：资金/预算不足（%s）" % (stock, _why))
            return False
        # 【V2.0】ST 三道校验（对齐 V16 v8）：实时状态 / 名称 / 涨跌停 5% 档
        _st_bad, _st_why = st_gate_check(stock, context)
        if _st_bad:
            log.info(f"🚫 买入请求已拦截(ST校验): {stock} | {_st_why}")
            return False
        premium = extra.get('premium', g.premium_normal)
        # 【V2.0】限价 = min(现价×溢价, 涨停价, 笼子(现价×1.02−0.01) [, 当日最高×1.002])
        #   笼子对齐交易所规则（超 ±2% 会废单）；"不追当日新高"是 tick 级防护，
        #   聚宽分钟K线没有毛刺，默认关闭（SPIKE_TOL_HIGH_ON=False），开着会让限价贴太紧、挂单不成交。
        _caps = [('溢价%.3f' % premium, current_price * premium),
                 ('涨停', high_limit),
                 ('笼子', current_price * OPEN_CAGE_MAX - OPEN_CAGE_RESERVE),
                 ('毛刺护栏', current_price * SPIKE_MAX_VS_LAST)]   # 【V5.0·v13】限价 ≤ 现价×1.005，不追尖峰
        if SPIKE_TOL_HIGH_ON:
            try:
                # ⚠ 本分支默认关闭（SPIKE_TOL_HIGH_ON=False）。若打开请注意：这里读的是"当日最高"（含全天），
                #   属于未来函数，回测下应改为快照 high 或直接保持关闭。
                _hi = get_price(stock, end_date=context.current_dt, count=1, fields=['high'],
                                frequency='1m', fq='pre')
                if _hi is not None and len(_hi) > 0:
                    _hi_px = float(_hi['high'].iloc[-1])
                    if _hi_px >= current_price > 0:
                        _caps.append(('当日高%.3f' % SPIKE_TOL_HIGH, _hi_px * SPIKE_TOL_HIGH))
            except Exception:
                pass
        _caps = [(k, c) for k, c in _caps if c and c > 0]
        if not _caps:
            log.info(f"🚫 放弃买入 {stock}：限价算不出来（现价{current_price} 涨停{high_limit}）")
            return False
        _pick = min(_caps, key=lambda kv: kv[1])
        limit_price = _pick[1]
        # 【V2.3 诊断】下单前把关键数字全打出来，任何一环不对都能一眼看出
        # 【V3.3】无限制档下 day_left 恒为 0，原来印"当日剩余额度0"会误导（看着像额度用完了）
        log.info("🎯 下单: %s | 现价%.3f 涨停%.3f 限价%.3f(受限于%s) %d股 金额%.0f | 可用资金%.0f 当日剩余额度%.0f(≤0=不限制)"
                 % (stock, current_price, high_limit, limit_price, _pick[0],
                    buy_amount, limit_price * buy_amount, available_cash,
                    (-1 if (BACKTEST_UNLIMITED or CASH_MAX_MODE == 'on') else day_left)))
        order_id = order(stock, buy_amount, LimitOrderStyle(limit_price))
        if order_id:
            stock_name = get_security_info(stock).display_name
            log.info(f"📥 已报单: {stock} {stock_name} | {buy_amount}股 @ 限价{limit_price:.3f} | 委托号{order_id}")
            g.hold_days[stock] = 0
            g.bought_stocks.add(stock)
            g.bought_today_count += 1
            g.own_codes.add(stock)                                  # 【回测版】记下"这是我买的"
            g.bought_amount_today = float(getattr(g, 'bought_amount_today', 0.0) or 0.0) \
                + limit_price * buy_amount                          # 【回测版】累计当日金额
            g.order_pending.add(stock)                              # 【V2.3】待成交核对
            # 【V5.0】Tick 频率回测：把新买入的票也订上 tick（卖出监控要用它的逐格行情）
            try:
                if TICK_MODE_ENABLE:
                    subscribe([stock], 'tick')
            except Exception:
                pass
            push_signal('BUY', stock, buy_amount, limit_price, 'limit', '自动买入')
            return True
        # 【V2.3 诊断】聚宽 order() 被拒时返回空 —— 原来这里静默返回，日志里什么都看不到
        log.info("❌ 委托被拒/未生成: %s | 现价%.3f 限价%.3f %d股 金额%.0f 可用%.0f"
                 % (stock, current_price, limit_price, buy_amount,
                    limit_price * buy_amount, available_cash))
        log.info("   常见原因: ①资金不足 ②限价超出涨跌停 ③标的停牌/未上市 ④股数不是100整数倍 "
                 "⑤超出当日买入额度 ⑥回测频率不是分钟（run_daily 分钟时点不生效）")
        return False
    except Exception as e:
        log.error(f"❌ 买入失败{stock}: {str(e)[:30]}")
        return False

# ==================== 【V6.0·市场门控】开盘前市场判定（4 道门 + 统一裁决） ====================
# 判据一律取【昨日(含)以前】的日线（attribute_history 不含当日 / get_price end_date=previous_date）
#   → 09:00 盘前即可判定，回测无未来函数；任何一步取数失败 = 该道门不拦（放行），并打 ⚠️ 日志。
# 收敛点：buy_decision() 开头一道闸 —— 覆盖 tick 定盘(09:30:15) 与分钟兜底(09:31/32/33/37/10:29) 全部买入路径。


def _gate_cfg(name, default=None):
    """[V6.0] 读门控配置：优先 g（initialize 已镜像，运行期可改），否则读模块常量。"""
    _v = getattr(g, name, None)
    if _v is None:
        _v = globals().get(name, default)
    return default if _v is None else _v


def _gate_ma_state(code, lookback):
    """[V6.0] 昨收 vs MA(lookback)：(昨收, 均线, 是否低于?)；数据不足/异常 → (None, None, None)"""
    try:
        _n = int(lookback)
        df = attribute_history(code, _n + 1, '1d', ['close'], skip_paused=False)
        if df is None or len(df) < _n:
            return None, None, None
        cur = float(df['close'].iloc[-1])
        ma = float(df['close'].iloc[-_n:].mean())
        if ma <= 0 or cur <= 0:
            return None, None, None
        return cur, ma, bool(cur < ma)
    except Exception as e:
        log.warn("⚠️ 【市场门控】%s 均线取数失败：%s" % (str(code), str(e)[:40]))
        return None, None, None


def check_market_ma20_gate(context):
    """[D4] 大盘 MA20 门控：沪深300 昨收 < MA20 → True（当日禁开新仓）"""
    if not bool(_gate_cfg('enable_market_ma20_gate', True)):
        return False
    _idx = _gate_cfg('market_index', '000300.XSHG')
    _lb = int(_gate_cfg('market_ma20_lookback', 20))
    cur, ma, weak = _gate_ma_state(_idx, _lb)
    if weak is None:
        log.info("⚪ 【D4·MA20门控】%s 数据不足 → 本道门不拦（放行）" % str(_idx))
        return False
    log.info("📉 【D4·MA20门控】%s 昨收 %.2f vs MA%d %.2f → %s"
             % (str(_idx), cur, _lb, ma, '低于，禁开新仓' if weak else '站上，正常交易'))
    return weak


def calc_market_breadth(context):
    """[D5] 全市场多头占比：收盘价 > MA(lookback) 的标的占比。返回 (占比, 有效样本数)。
    按 previous_date 缓存 —— 同一天只算一次（buy_decision 一天会被调用多次）。"""
    _end = getattr(context, 'previous_date', None) or context.current_dt.date()
    _c = getattr(g, '_breadth_cache', None)
    if _c and len(_c) >= 3 and _c[0] == _end:
        return _c[1], _c[2]
    _ratio, _n = None, 0
    t0 = time.time()
    _uni = str(_gate_cfg('breadth_universe', 'stock'))
    _lb = int(_gate_cfg('breadth_ma_lookback', 20))
    try:
        if _uni == 'etf':
            secs = list(get_all_securities(['etf'], date=_end).index)
        elif _uni == '300':
            secs = list(get_index_stocks('000300.XSHG', date=_end))
        else:
            secs = list(get_all_securities(['stock'], date=_end).index)
        if not secs:
            log.info("⚠️ 【D5·市场宽度】%s 标的清单为空 → 本道门不拦（放行）" % _uni)
        else:
            df = get_price(secs, end_date=_end, count=_lb + 1, frequency='1d',
                           fields=['close'], panel=False, skip_paused=True)
            if df is None or df.empty:
                log.info("⚠️ 【D5·市场宽度】%s 取数为空 → 本道门不拦（放行）" % _uni)
            else:
                _piv = df.pivot(index='time', columns='code', values='close')
                if len(_piv) < _lb:
                    log.info("⚠️ 【D5·市场宽度】%s 有效交易日 %d < %d → 本道门不拦（放行）"
                             % (_uni, len(_piv), _lb))
                else:
                    _ma = _piv.iloc[-_lb:].mean()
                    _last = _piv.iloc[-1]
                    _valid = _last.notna() & _ma.notna()
                    _n = int(_valid.sum())
                    if _n > 0:
                        _ratio = float((_last[_valid] > _ma[_valid]).sum()) / _n
    except Exception as e:
        log.warn("⚠️ 【D5·市场宽度】计算异常 → 本道门不拦（放行）：%s" % str(e)[:60])
        _ratio, _n = None, 0
    try:
        g._breadth_cache = (_end, _ratio, _n)
    except Exception:
        pass
    log.info("📊 【D5·市场宽度】%s 收盘>MA%d 占比 %s（有效 %d 只，取数 %.0fms）"
             % (_uni, _lb,
                ('%.1f%%' % (_ratio * 100)) if _ratio is not None else '无法计算',
                _n, (time.time() - t0) * 1000.0))
    return _ratio, _n


def check_global_weak(context):
    """[D1] 全球共振：海外代理池过半跌破 MA(weak_period_ma_lookback) → True"""
    if not bool(_gate_cfg('enable_global_weak_defense', True)):
        return False
    _lb = int(_gate_cfg('weak_period_ma_lookback', 10))
    _pool = list(_gate_cfg('global_weak_proxy', []) or [])
    _below, _total = 0, 0
    for _c in _pool:
        _cur, _ma, _weak = _gate_ma_state(_c, _lb)
        if _weak is None:
            continue
        _total += 1
        _below += 1 if _weak else 0
    if _total > 0 and _below >= ((_total + 1) // 2):
        log.info("🌍 【D1·全球共振】海外代理 %d/%d 跌破 MA%d → 全球同步走弱" % (_below, _total, _lb))
        return True
    log.info("🌏 【D1·全球共振】海外代理 %d/%d 跌破 MA%d → 未共振" % (_below, _total, _lb))
    return False


def check_a_share_weak_period(context):
    """[走弱期] 4 大指数（大盘/小盘/创业板/中证A500）：≥3/4 收盘 < MA10 → 进入走弱期；
    ≥3/4 站上 → 退出；其余维持原状态（跨日状态，与五福5.2 同口径）。"""
    _lb = int(_gate_cfg('weak_period_ma_lookback', 10))
    _idx = _gate_cfg('weak_indexes', {}) or {}
    _above, _below = 0, 0
    for _name, _code in list(_idx.items()):
        _cur, _ma, _weak = _gate_ma_state(_code, _lb)
        if _weak is None:
            log.info("📊 【走弱期判断】%s(%s) 数据不足，跳过该指数" % (str(_name), str(_code)))
            continue
        if _weak:
            _below += 1
        else:
            _above += 1
        log.info("📊 【走弱期判断】%s(%s): 昨收%.2f / MA%d %.2f → %s"
                 % (str(_name), str(_code), _cur, _lb, _ma, '⬇️低于' if _weak else '⬆️站上'))
    _weak_now = (_below >= 3)
    _exit_now = (_above >= 3)
    if getattr(g, 'is_a_share_weak', False):
        if _exit_now:
            g.is_a_share_weak = False
            g.weak_start_date = None
            g.weak_days_count = 0
            log.info("🟢 【走弱期退出】≥3/4 指数站上 MA%d → 退出走弱期" % _lb)
        else:
            log.info("🔴 【走弱期中】已持续 %s 个交易日" % str(getattr(g, 'weak_days_count', 0)))
    else:
        if _weak_now:
            g.is_a_share_weak = True
            g.weak_start_date = context.current_dt.date()
            g.weak_days_count = 0
            log.info("🔴 【走弱期进入】%d/4 指数低于 MA%d → 进入走弱期" % (_below, _lb))
        else:
            log.info("🟢 【正常期】低于 MA%d 的指数 %d/4，未满足进入条件" % (_lb, _below))
    if getattr(g, 'is_a_share_weak', False):
        try:
            _sd = getattr(g, 'weak_start_date', None)
            if _sd is not None:
                g.weak_days_count = len(get_trade_days(start_date=_sd,
                                                      end_date=context.current_dt.date()))
        except Exception:
            pass
    try:
        record(走弱期状态=(1 if getattr(g, 'is_a_share_weak', False) else 0))
    except Exception:
        pass
    return bool(getattr(g, 'is_a_share_weak', False))


def market_gate_precheck(context):
    """[V6.0] 开盘前市场判定（4 道门统一裁决）。每天只算一次（按 previous_date 缓存），日志只打一遍。
    返回 verdict：{'date','weak','d4','d5','d5_ratio','d5_n','d1','d3','block','why'}
    block = d3(走弱期) 或 d4 或 d5 或 d1 → 今日不开新仓（卖出/止损照常）。"""
    _date = getattr(context, 'previous_date', None) or context.current_dt.date()
    _v = getattr(g, 'market_gate', None)
    if _v is not None and _v.get('date') == _date:
        return _v
    weak = check_a_share_weak_period(context)
    d4 = check_market_ma20_gate(context)
    d5 = False
    _ratio, _n = (None, 0)
    if bool(_gate_cfg('enable_breadth_gate', True)):
        _ratio, _n = calc_market_breadth(context)
        _thr = float(_gate_cfg('breadth_min_ratio', 0.30))
        if _ratio is not None and _ratio < _thr:
            d5 = True
            log.info("🛑 【D5·市场宽度门控】多头占比 %.1f%%（%d只）< %.0f%% → 仓位乘数=0，今日不开新仓"
                     % (_ratio * 100, _n, _thr * 100))
    d3 = bool(weak) and bool(_gate_cfg('enable_weak_freq_reduce', True))
    d1 = False
    if bool(weak) and bool(_gate_cfg('enable_global_weak_defense', True)):
        d1 = check_global_weak(context)
    _why = []
    if d3:
        _why.append('走弱期(D3)')
    if d4:
        _why.append('沪深300<MA%d(D4)' % int(_gate_cfg('market_ma20_lookback', 20)))
    if d5:
        _why.append('市场宽度%.1f%%<%.0f%%(D5)'
                    % (_ratio * 100, float(_gate_cfg('breadth_min_ratio', 0.30)) * 100))
    if d1:
        _why.append('全球共振(D1)')
    _block = bool(d1 or d3 or d4 or d5)
    _v = {'date': _date, 'weak': bool(weak), 'd4': bool(d4), 'd5': bool(d5),
          'd5_ratio': _ratio, 'd5_n': _n, 'd1': bool(d1), 'd3': bool(d3),
          'block': _block, 'why': '、'.join(_why)}
    g.market_gate = _v
    if _block:
        log.info("🛑 【V6.0·市场门控】今日不开新仓：%s（持仓卖出/止损照常，不受影响）" % _v['why'])
    else:
        log.info("✅ 【V6.0·市场门控】四道门全过：走弱期=%s | D4=%s | D5=%s | D1=%s → 正常交易"
                 % ('是' if weak else '否', '拦' if d4 else '过',
                    '拦' if d5 else '过', '拦' if d1 else '过'))
    if bool(weak) and bool(_gate_cfg('enable_weak_freq_reduce', True)):
        log.info("ℹ️ 【D3·走弱期降频】强者恒强全天只有 09:30:15 一次定盘买入，无 13:40/14:10/14:40 "
                 "趋势复检与 14:55 强制买入窗口 → 本道门等价合并为「走弱期当日不买」")
    return _v


def market_gate_blocked(context):
    """[V6.0] 买入闸：返回 (是否禁买, 原因)。D1 命中时先执行「清空候选池」。"""
    _v = market_gate_precheck(context)
    if not _v:
        return False, ''
    if _v.get('d1'):
        _n = len(getattr(g, 'rebuy_candidates', []) or []) + len(getattr(g, 'candidate_stocks', []) or [])
        try:
            g.rebuy_candidates = []
            g.candidate_stocks = []
        except Exception:
            pass
        if _n and not getattr(g, 'gate_d1_cleared', False):
            g.gate_d1_cleared = True
            log.info("🛡️ 【D1·全球共振防御】清空候选池 %d 只 → 今日不开新仓（本版不买入货币防御ETF 511880）" % _n)
    if not _v.get('block'):
        return False, ''
    return True, _v.get('why', '')

# ==================== 策略核心初始化及卖出等 ====================
def initialize(context):
    # 【V3.0】v18 口径新增状态（每日在 before_market_open 复位）
    _v61_hdr = ("🧩 聚宽版 V6.2-市场门控·A5开盘先卖（基座 V6.1，金额限制=%s）build=2026-10-14-V6.2 | "
                % ("关闭：单只/当日/总持仓金额均不限，每只预算=可用现金÷本轮只数" if CASH_MAX_MODE == 'on'
                   else "开启：单只%.0f元 / 总持仓%.0f元" % (TARGET_AMOUNT_PER_STOCK, MAX_TOTAL_POSITION_AMOUNT)))
    _amt61 = ("口径：单只不限 / 当日≤%d只 / 总持仓不限 / 股数不封顶 | " % MAX_BUY_PER_DAY_STOCKS
              if CASH_MAX_MODE == 'on' else
              "口径：单只≈%.0f元 / 当日≤%d只 / 总持仓≤%.0f元 / 股数不封顶 | "
              % (TARGET_AMOUNT_PER_STOCK, MAX_BUY_PER_DAY_STOCKS, MAX_TOTAL_POSITION_AMOUNT))
    log.info(_v61_hdr + _amt61 +
             "买入：预热 09:30:00 起 → 定盘 09:30:15（15 秒）排序+同格报单 → 之后全天不再买 | "
             "卖出：A1-A4 已拆除，A5=%s，方向分流=%s（俯冲0.2%%/触发+2%%回落0.5%%/未触发兜底0.5%%/%s兜底）| "
             "炸板尺/均线尺=%s | 破板回落 %.1f%%×%d 秒 | 当日卖出禁买回=%s | 复牌禁买=%s"
             % (
                ('复装(开盘未涨停先卖)' if SELL_930_A5_MODE == 'on' else '停用'),
                OPEN_DIRECTION_MODE, OPEN_DIRECTION_DEADLINE, RULE_V232_MODE,
                STRATEGY_PARAMS['break_drop_ratio'], int(STRATEGY_PARAMS['tick_break_confirm_sec']),
                REBUY_GUARD_MODE, RESUME_FILTER_MODE))
    g.top_rank_codes = []
    g.open_buy_done = False
    g.sizing_n = 1                 # 【V3.1】本轮要买的只数（等权分配用）
    log.info("="*50)
    log.info("🚀 策略名称：强者恒强（自动交易 + 手动跟单提示）")
    log.info("✅ 策略将自动选股、自动买入/卖出，并在定盘(09:30:15)和09:33输出候选股供手动跟单")
    log.info("="*50)
    
    # 加载策略参数
    for key, value in STRATEGY_PARAMS.items():
        if key == 'filter_continuous_gain':
            g.filter_continuous_gain = value
        elif key == 'filter_after_1430_gain':
            g.filter_after_1430_gain = value
        elif key == 'filter_amplitude':
            g.filter_amplitude = value
        elif key == 'filter_turnover':
            g.filter_turnover = value
        elif key == 'market_env_adjust':
            g.market_env_adjust = value
        elif key == 'time_sell_check_exclude':
            g.time_sell_check_exclude = value
        else:
            setattr(g, key, value)
    
    g.concept_cache = {}
    
    # 【回测版修正】聚宽的券商成本必须用 set_order_cost 才会生效；
    # 口径 = 本人实盘账户：佣金万1 / 每笔最低5元 / 卖出印花税 0.05% / ETF 免印花税
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.0005,          # 卖出印花税 0.05%
        open_commission=0.0001,    # 佣金万1
        close_commission=0.0001,
        close_today_commission=0,
        min_commission=5           # 每笔最低 5 元
    ), type='stock')
    set_slippage(PriceRelatedSlippage(0.002))      # 追价损耗近似（实盘限价=现价×(1+溢价)）
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    # 【V2.4 重要】**不要**开 avoid_future_data！
    #   开了之后聚宽禁止在开盘前读当日数据，而本策略的「竞价过滤 / 可交易性判断」必须用当日开盘价
    #   → 全部候选被判不合格（日志表现为：竞价过滤统计 通过 0 | 区间不符 0 | 风险股 0 | 其他 N）
    #   → 可买池恒为 0 → 全程不交易。原始聚宽版没设这一项，所以它天天能买。
    # set_option('avoid_future_data', True)

    # 【回测版】新增状态（只卖自己的票 / 当日金额 / 竞价增强对照）
    g.own_codes = set()
    g.bought_amount_today = 0.0
    g.auction_gate_today = []
    g.own_skip_logged = False
    g.order_pending = set()        # 【V2.3】当日已报单待成交的代码（收盘核对用）
    g.st_gate_nodata = False
    # 【V2.0】对齐 V16 的状态
    g.tier_locked = False
    g.sell_requested = set()
    g.open_requested = None
    g.dispatch_stamp = ""
    g.filter_done = False
    g.morning_done = False

    
    g.candidate_stocks = []
    g.hold_days = {}
    g.has_limit_up = set()
    g.bought_stocks = set()
    g.rebuy_candidates = []
    g.bought_today_count = 0
    g.market_env = "normal"
    g.only_buy = False
    g.break_limit_sold_stocks = []
    g.sold_today = []
    g.checked_today = {}
    # 【V6.0·市场门控】配置镜像到 g（运行期可改 g.xxx）+ 门控状态初始化
    for _gk in ('enable_market_ma20_gate', 'market_index', 'market_ma20_lookback',
                'enable_breadth_gate', 'breadth_universe', 'breadth_ma_lookback', 'breadth_min_ratio',
                'enable_global_weak_defense', 'global_weak_proxy',
                'enable_weak_freq_reduce', 'weak_period_ma_lookback', 'weak_indexes'):
        try:
            setattr(g, _gk, globals()[_gk])
        except Exception:
            pass
    g.is_a_share_weak = False     # 走弱期状态（跨日持久；只有 ≥3/4 指数站上 MA10 才退出）
    g.weak_start_date = None
    g.weak_days_count = 0
    g.market_gate = None          # 当日门控裁决（按 previous_date 缓存，每天一次）
    g._breadth_cache = None
    g.gate_block_logged = False
    g.gate_d1_cleared = False
    log.info(("🚦 【V6.0·市场门控】D4大盘MA20=%s(%s) | D5市场宽度=%s(%s<%.0f%%) | D1全球共振防御=%s(%s) | "
              "D3走弱期不买=%s | 走弱期=4 大指数 MA%d 中 ≥3/4 低于")
             % ('on' if enable_market_ma20_gate else 'off', market_index,
                'on' if enable_breadth_gate else 'off', breadth_universe, breadth_min_ratio * 100,
                'on' if enable_global_weak_defense else 'off',
                '/'.join([str(c)[:6] for c in global_weak_proxy]),
                'on' if enable_weak_freq_reduce else 'off', weak_period_ma_lookback))
    g.debug = True
    
    # 定时任务
    run_daily(before_market_open, time='before_open')
    # 【回测版】时间统一归一化为 HH:MM（聚宽的 run_daily 只认分钟；秒级串会被截断/报错）
    def _hm(t):
        t = str(t)
        return t[:5] if len(t) >= 5 and t[2] == ':' else t

    # 【V2.0】唯一调度入口（对齐 V16 v16）：只注册 scheduler 一个函数，
    # 长持仓破板巡检由 handle_data（引擎分钟回调，零注册）承担 —— 不再同一函数注册上百次。
    for _t in SCHEDULE_TIMES:
        run_daily(scheduler, time=_t)
    run_daily(after_market_close, time='after_close')

# ==================== 【V2.0】唯一调度入口 ====================
SCHEDULE_TIMES = ('09:26', '09:30', '09:31', '09:32', '09:33', '09:37', '10:29')
# 【V3.3】定盘时点 —— 聚宽【回测】的最小调度粒度是**整分钟**：
#   · 09:30:00 那一格只能拿到集合竞价价 → "开盘后涨了多少"= 0 或噪声 → 强度排序劣化成乱序；
#   · 09:31 那一格能拿到"开盘后约 1 分钟"的价格 → 排序才有信息（对应实盘 09:30:16 的口径）。
#   ⚠ 回测里做不到 09:30:16（秒级），秒级只在模拟盘/实盘（PTrade/QMT）有。
DECIDE_TIME = '09:31'
# 【V3.4】秒级定盘（Tick 频率回测）—— 依据聚宽官方文档《运行频率 / Tick 级策略专用函数》：
#   · 聚宽回测/模拟**支持 Tick 频率**；股票 tick 自 2017-01-01 起、**每 3 秒一次快照**（含买五卖五）
#   · **Tick 频率下 handle_data 与 run_daily(func,'every_bar') 不会被调用** → 必须 subscribe + handle_tick
#   · Tick 级需权限（会员/积分兑换）；且必须 set_option('use_real_price', True)（本文件已设）
#   · run_daily 的**定时**回调（time='09:26'/'09:30'…）在 Tick 频率下仍会触发
TICK_MODE_ENABLE = True                      # 盘前订阅候选股 tick（非 tick 频率下自动跳过）
DECIDE_SECOND = datetime.time(9, 30, 15)     # 【V5.0】秒级定盘：首个 ≥ 09:30:15 的 tick（对齐实盘 live_early_start=15 秒，用户：早盘买入15秒前后）
WARM_START_SEC = datetime.time(9, 30, 0)     # 【V5.0】预热起点：09:30:00 起只算排序不下单（对齐 V25 live_warm_start）
WARM_POOL_RANK_CACHE = 20                    # 预热缓存"全池排序"条数（对齐 V25）


def _build_long_hold_times(interval, exclude):
    out = []
    for hour in range(10, 15):
        for minute in range(0, 60, interval):
            if (hour, minute) in exclude:
                continue
            if 11 * 60 + 30 < hour * 60 + minute < 13 * 60:
                continue
            out.append('%02d:%02d' % (hour, minute))
    return frozenset(out)


LONG_HOLD_CHECK_TIMES = _build_long_hold_times(
    STRATEGY_PARAMS['time_sell_check_interval'],
    tuple(STRATEGY_PARAMS['time_sell_check_exclude']))


def _morning_batch(context):
    """09:30 那一格：**只做卖出**（先关买 → 卖出一轮 → 开买）。
    【V3.3】跟单提示与买入已挪到 09:31 —— 回测里 09:30:00 只能拿到集合竞价价，
    此时"开盘后涨了多少"还不存在，排序会退化成噪声（强度全挤在 +1.0 附近）。"""
    try:
        set_only_buy_False(context)
        sell_only_930(context)
        set_only_buy_True(context)
    except Exception as e:
        log.info("⚠️ 早盘任务异常: %s" % str(e)[:60])
    g.morning_done = True


def _catch_up(context):
    """【V2.1 回测适配】聚宽【回测】里分钟级 run_daily 最早 09:31 才触发（09:26/09:30 不执行）
    → 竞价过滤没跑、可买池为空，买入环节无票可买（这就是"回测一笔都不交易"的根因）。
    这里在任意一次更晚的调度触发时补跑早盘任务；模拟/实盘下 09:26/09:30 已跑过 → 空操作。"""
    if getattr(g, 'morning_done', False):
        return
    log.info("⏱ 早盘补跑（聚宽回测里 09:26/09:30 的 run_daily 不触发）")
    if not getattr(g, 'filter_done', False):
        auction_filter(context)
        g.filter_done = True
    _subscribe_ticks(context)              # 【V3.4】tick 频率下订阅候选股
    _morning_batch(context)
    log.info("📋 补跑后：候选池 %d 只 | 可买池 %d 只 | 持仓 %d 只"
             % (len(g.candidate_stocks), len(g.rebuy_candidates),
                len(context.portfolio.positions)))


def _dispatch(context, data=None):
    """唯一调度实现：按当前时间分支；run_daily 与 handle_data 都调它，同一分钟只执行一次"""
    hm = context.current_dt.strftime('%H:%M')
    if hm not in SCHEDULE_TIMES:
        return
    if getattr(g, 'dispatch_stamp', '') == hm:
        return
    g.dispatch_stamp = hm
    if hm == '09:26':
        auction_filter(context)
        g.filter_done = True
        _subscribe_ticks(context)          # 【V3.4】tick 频率下订阅候选股
    elif hm == '09:30':
        if not getattr(g, 'filter_done', False):
            auction_filter(context)
            g.filter_done = True
        _morning_batch(context)            # 【V3.3】09:30 只卖出，不买
    elif hm == DECIDE_TIME:                # 【V3.3】09:31 兜底定盘（分钟频率回测用）
        _catch_up(context)
        if not getattr(g, 'open_buy_done', False):
            manual_signal(context)         # 【V3.4】tick 模式已在 09:30:16 定盘 → 不重复打跟单表
        market_open(context)
    elif hm == '09:33':
        _catch_up(context)
        market_open(context)
    else:
        _catch_up(context)
        market_open(context)


def scheduler(context):
    """run_daily 唯一注册入口"""
    _dispatch(context)


def handle_data(context, data=None):
    """引擎分钟回调（不注册）：① 长持仓破板巡检（10:00~14:54 每 2 分钟）
    ② 调度兜底（run_daily 漏触发时补上，同一分钟只跑一次）"""
    hm = context.current_dt.strftime('%H:%M')
    if hm in LONG_HOLD_CHECK_TIMES:
        check_break_limit_drop_for_long_hold(context)
    # 【V4.0】破板回落监控（分钟频率回测：每分钟一次；Tick 频率下本函数不被调用，走 handle_tick）
    if '09:30' <= hm <= '14:56' and bool(STRATEGY_PARAMS.get('tick_break_monitor', True)):
        tick_break_monitor(context)
    # 【V5.0】方向分流引擎（分钟频率=每分钟一格；Tick 频率下走 handle_tick）
    if '09:30' <= hm <= '14:56':
        v20_engine(context)
    _dispatch(context)


def _subscribe_ticks(context):
    """【V3.4】订阅候选股 tick —— 仅 Tick 频率回测/模拟有效；其它频率会抛错 → 自动跳过。"""
    if not TICK_MODE_ENABLE or getattr(g, 'tick_subscribed', False):
        return
    try:
        _lst = list(g.candidate_stocks or [])[:600]
        if not _lst:
            return
        subscribe(_lst, 'tick')
        g.tick_subscribed = True
        log.info("📡 已订阅 %d 只候选股的 tick（Tick 频率下走 handle_tick 秒级定盘）" % len(_lst))
    except Exception as _e:
        log.info("ℹ️ tick 订阅跳过（当前不是 Tick 频率，跑分钟回测请忽略本行）: %s" % str(_e)[:70])


def _warm_rank(context):
    """【V5.0】预热（对齐 V25 live_warm_start）：09:30:00~09:30:15 每 3 秒刷一轮全池强度排序，
    只算不下单 —— 让 concept/价格缓存全热，并给定盘格提供"最后一轮排序"冻结榜单。"""
    try:
        if getattr(g, 'open_buy_done', False):
            return
        _pool = [s for s in (g.rebuy_candidates or [])
                 if s not in context.portfolio.positions and s not in g.bought_stocks]
        if not _pool:
            return
        _ranked = _pool_rank(context, _pool)
        g.warm_rank_cache = [c for c, _ in _ranked[:int(WARM_POOL_RANK_CACHE)]]
        if not getattr(g, 'warm_logged', False):
            g.warm_logged = True
            log.info("🔥【V5.0 预热】开始（09:30:00~09:30:15 每 3 秒刷排序，只算不下单）｜全池 %d 只" % len(_ranked))
    except Exception:
        pass


def _apply_warm_rank(context):
    """【V5.0】定盘格用"最后一轮预热排序"冻结可买宇宙（对齐 V25 RANK_FROZEN_AT_OPEN）。
    预热榜单为空/异常 → 交回 buy_decision 现场重算（兜底）。"""
    try:
        if getattr(g, 'top_rank_codes', None):
            return
        _warm = list(getattr(g, 'warm_rank_cache', None) or [])
        if not _warm:
            return
        _excl = set(context.portfolio.positions.keys()) | set(g.bought_stocks)
        _top = [c for c in _warm if c not in _excl][:int(MAX_BUY_RANK)]
        if _top:
            g.top_rank_codes = _top
            log.info("🧊【V5.0】定盘用预热冻结榜单（全池强度前%d名）: %s"
                     % (len(_top), '、'.join(_top)))
    except Exception:
        pass


def handle_tick(context, tick):
    """【V3.4→V5.0】Tick 频率专用回调 —— 秒级定盘（对齐实盘 live_early_start=09:30:15）。
    聚宽文档：Tick 频率下 handle_data 与 run_daily('every_bar') 不会被调用（定时 run_daily 仍触发）。"""
    try:
        now = context.current_dt
        hm = now.strftime('%H:%M')
        # ⓪ 维护 tick 价格缓存（供 _rt_of 取当日最高/最低/现价，无未来函数）
        try:
            if not hasattr(g, '_tick_px'):
                g._tick_px = {}
            code = getattr(tick, 'code', None)
            if code:
                _tp = g._tick_px.setdefault(code, {})
                _tp['t'] = now.strftime('%H:%M:%S')
                _cur = float(getattr(tick, 'current', 0) or getattr(tick, 'last_price', 0) or 0)
                if _cur > 0:
                    _tp['last'] = _cur
                for k in ('high', 'low', 'open', 'pre_close', 'high_limit', 'low_limit'):
                    _v = getattr(tick, k, None)
                    if _v and float(_v) > 0:
                        _key = {'pre_close': 'pre', 'high_limit': 'up', 'low_limit': 'dn'}.get(k, k)
                        if k in ('high', 'low') and float(_tp.get(_key, 0) or 0) > 0:
                            _tp[_key] = max(_tp[_key], float(_v)) if k == 'high' \
                                else min(_tp[_key], float(_v))
                        else:
                            _tp[_key] = float(_v)
                # 【V5.0a】tick 快照的 volume/money = 当日累计成交量/额 —— 09:31 前 1 分钟 bar
                # 尚未闭合，量比/盘中均价只能靠它（tick 频率回测 15 秒定盘的关键数据源）
                try:
                    _tv = float(getattr(tick, 'volume', 0) or 0)
                    if _tv > 0:
                        _tp['vol'] = _tv
                    _tm = float(getattr(tick, 'money', 0) or 0)
                    if _tm > 0:
                        _tp['money'] = _tm
                except Exception:
                    pass
        except Exception:
            pass
        # ① 竞价过滤（首个 ≥09:26 的 tick）
        if not getattr(g, 'filter_done', False) and hm >= '09:26':
            auction_filter(context)
            g.filter_done = True
        # ② 09:30 卖出（首个 ≥09:30:00 的 tick）—— 与实盘一致：开盘先卖，再定盘买
        if not getattr(g, 'morning_done', False) and hm >= '09:30':
            _morning_batch(context)
        # ③'【V5.0】预热（09:30:00~09:30:15）：每 3 秒刷全池强度排序（只算不下单）
        if (not getattr(g, 'open_buy_done', False)) and WARM_START_SEC <= now.time() < DECIDE_SECOND:
            _ts = now.strftime('%H:%M:%S')
            if getattr(g, '_warm_stamp', '') != _ts:
                g._warm_stamp = _ts
                _warm_rank(context)
        # ③ 【秒级定盘】首个 ≥09:30:15 的 tick：跟单提示 + 排序 + 报单（同一 tick 内完成，不拖到下一分钟）
        if (not getattr(g, 'open_buy_done', False)) and now.time() >= DECIDE_SECOND:
            log.info("🎯【Tick 定盘】首个 ≥09:30:15 的 tick = %s" % now.strftime('%H:%M:%S'))
            _apply_warm_rank(context)          # 【V5.0】用预热冻结榜单
            manual_signal(context)
            market_open(context)
            # 【V5.0·v21.2 先买后卖】委托已打出 → 本格再处置 09:30 延后的自有持仓
            v20_direction_route(context)
        # ④ 长持仓破板巡检（按分钟去重，避免每个 tick 都跑）
        if hm in LONG_HOLD_CHECK_TIMES and getattr(g, 'tick_break_stamp', '') != hm:
            g.tick_break_stamp = hm
            check_break_limit_drop_for_long_hold(context)
        # ⑤ 【V4.0】破板回落监控（秒级；按 TICK_BREAK_EVERY_SEC 节流；阈值0.5%/确认6秒=v22.8）
        if '09:30' <= hm <= '14:56' and bool(STRATEGY_PARAMS.get('tick_break_monitor', True)):
            _sec = now.hour * 3600 + now.minute * 60 + now.second
            _step = max(3, int(STRATEGY_PARAMS.get('tick_break_every_sec', 3) or 3))
            if _sec - int(getattr(g, '_tick_scan_sec', -10 ** 9)) >= _step:
                g._tick_scan_sec = _sec
                tick_break_monitor(context)
        # ⑥ 【V5.0】方向分流引擎（俯冲/冲高监控/A6 11:30 兜底；内部含统一裁决）
        if '09:30' <= hm <= '14:56':
            v20_engine(context)
    except Exception as e:
        log.info("⚠️ handle_tick 异常: %s" % str(e)[:80])


def set_only_buy_True(context):
    g.only_buy = True

def set_only_buy_False(context):
    g.only_buy = False

def adjust_params_by_market(context):
    try:
        # 【V3.2】原来 count=2 却用 trade_days[1] 当"前日" → 取到的是**今日**（未来函数/盘前取不到）。
        #   改成 count=3 + 负索引：[-2]=昨日、[-3]=前日。
        trade_days = get_trade_days(end_date=context.current_dt.date(), count=3)
        if len(trade_days) < 3:
            raise ValueError("无足够交易日")
        yesterday = trade_days[-2]
        day_before = trade_days[-3]
        hs300_yest = get_price('000300.XSHG', end_date=yesterday, count=1, fields=['close'], fq='pre')
        hs300_before = get_price('000300.XSHG', end_date=day_before, count=1, fields=['close'], fq='pre')
        if hs300_yest.empty or hs300_before.empty:
            raise ValueError("沪深300数据缺失")
        hs300_change = (hs300_yest['close'].iloc[0] - hs300_before['close'].iloc[0]) / hs300_before['close'].iloc[0] * 100
        all_stocks = [code for code in get_all_securities(['stock']).index if '.BJ' not in code]
        limit_up_count = 0
        for stock in all_stocks[:500]:
            if is_limit_up_simple(stock, yesterday):
                limit_up_count += 1
        if hs300_change > g.hs300_bull_threshold and limit_up_count > g.limit_up_count_bull:
            g.market_env = "bull"
            adj = g.market_env_adjust['bull']
            g.min_open_ratio = max(0, STRATEGY_PARAMS['min_open_ratio'] + adj['min_open_ratio_offset'])
            g.max_open_ratio = STRATEGY_PARAMS['max_open_ratio'] + adj['max_open_ratio_offset']
            g.min_turnover_rate = max(1, STRATEGY_PARAMS['min_turnover_rate'] + adj['min_turnover_rate_offset'])
            # 【V5.0】止损止盈动态调整已删（A1/A2 拆除）
        elif hs300_change < g.hs300_bear_threshold and limit_up_count < g.limit_up_count_bear:
            g.market_env = "bear"
            adj = g.market_env_adjust['bear']
            g.min_open_ratio = max(0, STRATEGY_PARAMS['min_open_ratio'] + adj['min_open_ratio_offset'])
            g.max_open_ratio = STRATEGY_PARAMS['max_open_ratio'] + adj['max_open_ratio_offset']
            g.min_turnover_rate = max(1, STRATEGY_PARAMS['min_turnover_rate'] + adj['min_turnover_rate_offset'])
        else:
            g.market_env = "normal"
            g.min_open_ratio = STRATEGY_PARAMS['min_open_ratio']
            g.max_open_ratio = STRATEGY_PARAMS['max_open_ratio']
            g.min_turnover_rate = STRATEGY_PARAMS['min_turnover_rate']
        log.info(f"市场环境：{g.market_env} | 开盘涨幅：{g.min_open_ratio}%~{g.max_open_ratio}% | 换手率：{g.min_turnover_rate}%")
    except Exception as e:
        log.warn(f"动态参数调整失败，使用默认参数：{str(e)[:50]}")
        g.market_env = "normal"
        g.min_open_ratio = STRATEGY_PARAMS['min_open_ratio']
        g.max_open_ratio = STRATEGY_PARAMS['max_open_ratio']
        g.min_turnover_rate = STRATEGY_PARAMS['min_turnover_rate']

def before_market_open(context):
    log.info("="*50)
    log.info(f"📅 新交易日开始：{context.current_dt.strftime('%Y-%m-%d')}")
    log.info("盘前选股开始")
    g.candidate_stocks = []
    g.has_limit_up.clear()
    g.bought_stocks.clear()
    g.rebuy_candidates = []
    g.bought_today_count = 0
    g.only_buy = False
    g.break_limit_sold_stocks = []
    g.sold_today = []
    # 【V2.2】每日复位（关键修复）：V2.0/V2.1 把这些状态只写在 initialize 里，
    # 而聚宽回测的 initialize 整个回测只跑一次 → 第 2 天起 filter_done/morning_done 一直是 True
    # （竞价过滤再也不跑、可买池天天为空）、open_requested 残留昨天的名单 → 每天都 0 成交。
    # 注：own_codes（策略自购代码）是跨日状态，**不在这里清**。
    g.filter_done = False
    g.morning_done = False
    g.dispatch_stamp = ""
    g.open_requested = None
    g.sell_requested = set()
    g.tier_locked = False          # （已无读取方，保留兼容）
    g.top_rank_codes = []          # 【V3.0】可买宇宙（全池前 5 名）每日重算
    g.open_buy_done = False        # 【V3.0】定盘是否已完成（完成后当日不再买入）
    
    g.auction_gate_today = []
    g.bought_amount_today = 0.0
    g.own_skip_logged = False
    g.order_pending = set()
    g.st_gate_nodata = False
    g._tick_break_since = {}      # 【V4.0】破板回落确认计时
    g._sold_watch = []            # 【V4.0】卖出后 60 秒回看队列
    g._tick_scan_sec = 0          # 【V4.0】tick 巡检节流
    # 【V5.0】卖出引擎每日复位
    g.v20_dir_deferred = {}       # v20.2 延后名单
    g.v20_watch = {}              # v20 冲高监控
    g.v20_dive_prev = {}          # v21.3 毛刺过滤状态
    g.v232 = {}                   # v23.3 炸板尺/均线尺状态
    g._wavg_cache = {}            # 盘中均价缓存
    g._tick_px = {}               # tick 价格缓存
    g.warm_rank_cache = []        # 预热冻结榜单
    g.warm_logged = False
    g._warm_stamp = ''
    # 【V5.0】Tick 频率：把隔夜持仓也订上 tick（卖出监控需要逐格行情）
    try:
        if TICK_MODE_ENABLE and not getattr(g, '_pos_subbed', False):
            _hold = [c for c in context.portfolio.positions.keys()
                     if c not in SELL_SKIP_CODES]
            if _hold:
                subscribe(_hold[:100], 'tick')
            g._pos_subbed = True
    except Exception:
        pass
    if hasattr(g, 'checked_today'):
        del g.checked_today
    g.checked_today = {}
    # 【V6.0·市场门控】每日复位（注意：走弱期 g.is_a_share_weak 是跨日状态，**不在这里复位**）
    g.market_gate = None
    g._breadth_cache = None
    g.gate_block_logged = False
    g.gate_d1_cleared = False
    adjust_params_by_market(context)
    total_asset = context.portfolio.total_value
    # 【V3.0】持仓只数不限：这里只打印真闸门口径（原来读已删除的档位函数 → 会 NameError）
    if CASH_MAX_MODE == 'on':
        log.info("盘前动态配置：总资产%.2f → 持仓只数 不限，当日新建仓 ≤%d 只，"
                 "金额不受限（资金最大化档：单只预算=可用现金÷本轮只数）"
                 % (total_asset, int(MAX_BUY_PER_DAY_STOCKS)))
    else:
        log.info("盘前动态配置：总资产%.2f → 持仓只数 不限，当日新建仓 ≤%d 只，总持仓金额 ≤%.0f 元"
                 % (total_asset, int(MAX_BUY_PER_DAY_STOCKS), MAX_TOTAL_POSITION_AMOUNT))
    trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
    if len(trade_days) < 2:
        log.info("无昨日交易日，今日跳过选股")
        return
    yesterday = trade_days[0]
    log.info(f"使用前一个交易日数据: {yesterday}")
    
    current_tradable_stocks = [
        code for code in get_all_securities(['stock'], date=context.current_dt.date()).index
        if (not g.filter_beijing or '.BJ' not in code)
    ]
    current_tradable_stocks = [
        code for code in current_tradable_stocks
        if (get_stock_board(code) in ("main", "gem")) or (not g.filter_kcb and get_stock_board(code) == "star")
    ]
    log.info("今日可交易A股数量: {}".format(len(current_tradable_stocks)))
    limit_up_stocks = []
    batch_size = 1000
    for i in range(0, len(current_tradable_stocks), batch_size):
        batch_stocks = current_tradable_stocks[i:i+batch_size]
        for stock in batch_stocks:
            try:
                if g.filter_st_stock and is_st_stock(stock):
                    continue
                if g.filter_kcb and get_stock_board(stock) == 'star':
                    continue
                if is_limit_up_simple(stock, yesterday) or is_strong_stock(stock, yesterday):
                    pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, yesterday)
                    if not pass_filter:
                        continue
                    pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, yesterday)
                    if not pass_1430_filter:
                        continue
                    pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, yesterday)
                    if not pass_amp_filter:
                        continue
                    pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, yesterday)
                    if not pass_turnover_filter:
                        continue
                    pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, yesterday)
                    if not pass_limitdown_filter:
                        continue
                    pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, yesterday)
                    if not pass_shrink_filter:
                        continue
                    limit_up_stocks.append(stock)
            except:
                continue
    log.info("核心识别强势股: {}只".format(len(limit_up_stocks)))
    if len(limit_up_stocks) == 0:
        limit_up_stocks = find_limit_up_loose(current_tradable_stocks[:1500], yesterday)
        log.info("宽松识别后强势股: {}只".format(len(limit_up_stocks)))
    if len(limit_up_stocks) == 0:
        limit_up_stocks = find_limit_up_ultra_loose(current_tradable_stocks[:1500], yesterday)
        log.info("超宽松识别后强势股: {}只".format(len(limit_up_stocks)))
    g.candidate_stocks = limit_up_stocks.copy()
    g.rebuy_candidates = limit_up_stocks.copy()
    
    if g.candidate_stocks:
        log.info(f"📋 【盘前候选股名单】共 {len(g.candidate_stocks)} 只")
    else:
        log.info("⚠️ 盘前未选出任何候选股")
    # 【V6.0·市场门控】开盘前市场判定（judged on 昨日及更早数据 ⇒ 09:00 即可定论）
    #   这里只做"判定 + 打日志"；真正的"不开新仓"由 buy_decision() 开头那道闸执行。
    try:
        market_gate_precheck(context)
    except Exception as _e:
        log.info("⚠️ 【V6.0·市场门控】盘前判定异常（不拦，放行）：%s" % str(_e)[:60])

# ==================== 【回测版】竞价增强模块 ====================
# 规则（用户 2026-09-18 提供）：
#   ① 竞价涨幅 ≥ +2%
#   ② 竞价额过股价分级门槛（<10元 200万 / 10–30元 300万 / >30元 500万）
#   ③ 板块样本 ≥5 只时要求板块内竞价额排前 1/3（样本 <5 只不做排名）
#   ④ 一字/竞价即涨停剔除
#   ⑤ ★ 三项命中数：竞价涨幅≥+4% / 板块内额前1/3 / 流通市值 30–80 亿（只标注不剔除）
# 聚宽优势：板块（get_industry）与流通市值（get_fundamentals）都能取到 → ③⑤ 可完整判定。
def _aq_amt_of(stock, context):
    """竞价额近似：开盘首分钟成交额（聚宽分钟数据第一根含竞价成交）。
    取不到（或拿到的不是今天的bar）→ 返回 0 = 未判定，不参与拦截。"""
    try:
        df = get_price(stock, end_date=context.current_dt, count=1, frequency='1m',
                       fields=['money'], fq='pre', skip_paused=True)
        if df is not None and len(df) > 0:
            d = df.index[-1]
            if hasattr(d, 'date') and d.date() == context.current_dt.date():
                return float(df['money'].iloc[-1])
    except Exception:
        pass
    return 0.0


def _aq_block_of(stock, date):
    """板块归属（聚宽 get_industry）"""
    try:
        d = get_industry(stock, date=date)
        if isinstance(d, dict):
            for k in ('sw_l1', 'sw_l2', 'zjw', 'jq_l1'):
                v = d.get(k)
                if isinstance(v, dict):
                    name = v.get('industry_name') or v.get('industry_code')
                    if name:
                        return str(name)
    except Exception:
        pass
    return ''


def _aq_mv_map(stocks, date):
    """批量取流通市值（元）"""
    try:
        q = query(valuation.code, valuation.circulating_market_cap).filter(
            valuation.code.in_(list(stocks)))
        df = get_fundamentals(q, date=date)
        if df is not None and len(df) > 0:
            return dict((r['code'], float(r['circulating_market_cap']) * 1e8)
                        for _, r in df.iterrows())
    except Exception:
        pass
    return {}


def auction_gate(context, stocks):
    """竞价增强判定：记录到 g.auction_gate_today；mode='on' 时返回过滤后的名单"""
    if AUCTION_GATE_MODE == 'off' or not stocks:
        return stocks
    date = context.current_dt.date()
    cd = get_current_data()
    rec, blocks = [], {}
    for stock in list(stocks):
        try:
            cur = cd[stock]
            pre = cur.pre_close if hasattr(cur, 'pre_close') else 0
            open_px = cur.day_open
            if not pre or pre <= 0 or not open_px or open_px <= 0:
                continue
            gain = (open_px / pre - 1) * 100
            amt = _aq_amt_of(stock, context)
            high_limit = cur.high_limit
            one_word = bool(high_limit and open_px >= high_limit - 0.001)
            why = []
            if one_word:
                why.append('④一字/竞价涨停')
            if gain < AUCTION_MIN_GAIN:
                why.append('①涨幅%.2f%%<%.2f%%' % (gain, AUCTION_MIN_GAIN))
            thr = AUCTION_AMT_TIERS[-1][1]
            for cap_px, need in AUCTION_AMT_TIERS:
                if cap_px <= 0 or open_px <= cap_px:
                    thr = need
                    break
            if amt <= 0:
                why.append('②竞价额未判定')
            elif amt < thr:
                why.append('②额%.0f万<%.0f万' % (amt / 1e4, thr / 1e4))
            blk = _aq_block_of(stock, date)
            item = {'code': stock, 'gain': gain, 'amt': amt, 'block': blk, 'ratio': None,
                    'stars': 0, 'mv': 0.0, 'ok': not why, 'why': '、'.join(why)}
            rec.append(item)
            if blk:
                blocks.setdefault(blk, []).append(stock)
        except Exception as e:
            log.info("⚠️ 竞价判定异常 %s: %s" % (stock, str(e)[:40]))
    # ③ 板块内竞价额排名（样本 ≥5 才过滤）
    amt_of = dict((r['code'], r['amt']) for r in rec)
    for blk, members in blocks.items():
        if len(members) < AUCTION_BLOCK_MIN_SAMPLE:
            continue
        members.sort(key=lambda s: -amt_of.get(s, 0))
        for pos, s in enumerate(members, 1):
            for r in rec:
                if r['code'] == s:
                    r['ratio'] = float(pos) / len(members)
                    if r['ratio'] > 1.0 / 3.0 and r['ok']:
                        r['ok'] = False
                        r['why'] = (r['why'] + '、' if r['why'] else '') + \
                            '③板块%s内排%d/%d' % (blk, pos, len(members))
    # ⑤ ★
    mv_map = _aq_mv_map([r['code'] for r in rec], date)
    for r in rec:
        r['mv'] = mv_map.get(r['code'], 0.0)
        n = 0
        if r['gain'] >= AUCTION_MIN_GAIN_STAR:
            n += 1
        if r['ratio'] is not None and r['ratio'] <= 1.0 / 3.0:
            n += 1
        if r['mv'] > 0 and AUCTION_STAR_MV[0] <= r['mv'] <= AUCTION_STAR_MV[1]:
            n += 1
        r['stars'] = n
    g.auction_gate_today = rec
    ok_list = [r for r in rec if r['ok']]
    log.info("🧪 竞价增强[%s] 判定 %d 只 → 过①②③④ %d 只 | ★★★ %d | ★★ %d"
             % (AUCTION_GATE_MODE, len(rec), len(ok_list),
                len([r for r in rec if r['stars'] >= 3]), len([r for r in rec if r['stars'] == 2])))
    for r in sorted(rec, key=lambda x: -x['stars'])[:8]:
        if r['stars'] > 0:
            log.info("   %s %s | 涨幅%+.2f%% 额%.0f万 板块%s 排%s 市值%.1f亿"
                     % ('★' * r['stars'], r['code'], r['gain'], r['amt'] / 1e4,
                        r['block'] or '未判定',
                        ('%d%%' % round(r['ratio'] * 100)) if r['ratio'] is not None else '-',
                        r['mv'] / 1e8 if r['mv'] else 0))
    if AUCTION_GATE_MODE == 'on':
        out = [r['code'] for r in ok_list]
        log.info("🚦 竞价增强已生效：候选 %d → %d 只" % (len(stocks), len(out)))
        return out
    return stocks



# ==================== 【V4.1】买入侧「龙头过滤」（判据与 PTrade V21 一致） ====================
# 回测里要测这条规则，把 LEADER_FILTER_MODE 改成 'on'；'dry' 只记录不改候选（默认，保守）
LEADER_FILTER_MODE = 'dry'        # 'off' = 完全不过滤｜'dry' = 只记录｜'on' = 真过滤
LEADER_MIN_BOARDS = 2             # 连板数下限
LEADER_TURNOVER_MAX = 10.0        # 昨日换手率上限(%)；<= 0 = 不看换手
LEADER_FAILSAFE_KEEP = True       # 连板取不到且池内没到下限 → 不过滤（不一致清空候选池）


def jq21_board_count(stock):
    """截至【昨日】的连续涨停天数（0 = 昨日未涨停）。取不到返回 None。
    用 attribute_history（只返回已完成日线）+ high_limit 字段，不含当日，无未来函数。"""
    try:
        df = attribute_history(stock, 12, '1d', ['close', 'high_limit'], skip_paused=True, df=True)
        if df is None or len(df) < 2:
            return None
        cl = [float(x) for x in list(df['close'])]
        hl = list(df['high_limit'])
        thr = getattr(g, 'limit_up_threshold', 9.5)
        n = 0
        j = len(cl) - 1
        while j >= 1:
            pc = cl[j - 1]
            if pc <= 0:
                break
            lim = float(hl[j]) if hl[j] is not None else 0.0
            hit = (lim > 0 and abs(cl[j] - lim) / lim <= 0.006) or ((cl[j] - pc) / pc * 100 > thr)
            if not hit:
                break
            n += 1
            j -= 1
        return n
    except Exception:
        return None


def jq21_prev_turnover(stock, yest):
    """昨日换手率(%)；取不到返回 None（放行）"""
    try:
        v = float(calculate_turnover_rate(stock, yest) or 0.0)
        return v if 0 < v < 1000 else None
    except Exception:
        return None


def jq21_leader_filter(stocks, yest):
    """池内龙头过滤 → (保留列表, 统计)。fail-safe：连板取不到且池内未达下限 → 原样返回。"""
    st = dict(n=len(stocks), maxb=0, unknown=0, boards={}, turn={}, dropped=[], turn_dropped=[])
    if LEADER_FILTER_MODE == 'off' or not stocks:
        return list(stocks), st
    boards = {}
    for c in stocks:
        b = jq21_board_count(c)
        if b is None:
            st['unknown'] += 1
        else:
            boards[c] = b
    st['boards'] = boards
    maxb = max(boards.values()) if boards else 0
    st['maxb'] = maxb
    if maxb < int(LEADER_MIN_BOARDS):
        if st['unknown'] > 0 and LEADER_FAILSAFE_KEEP:
            st['note'] = '无法判定（%d 只取不到连板且池内最高 %d）→ 不过滤' % (st['unknown'], maxb)
            return list(stocks), st
        st['note'] = '池内最高连板 %d < 下限 %d → 空池' % (maxb, int(LEADER_MIN_BOARDS))
        st['dropped'] = list(stocks)
        return [], st
    keep = [c for c in stocks if boards.get(c, -1) == maxb]
    st['dropped'] = [c for c in stocks if boards.get(c, -1) != maxb]
    if LEADER_TURNOVER_MAX and LEADER_TURNOVER_MAX > 0:
        k2 = []
        for c in keep:
            t = jq21_prev_turnover(c, yest)
            st['turn'][c] = t
            if t is None or t < float(LEADER_TURNOVER_MAX):
                k2.append(c)
            else:
                st['turn_dropped'].append(c)
        keep = k2
    st['kept'] = list(keep)
    return list(keep), st


def jq21_leader_report(st, before, after):
    if LEADER_FILTER_MODE == 'off':
        return
    tag = '本应' if LEADER_FILTER_MODE == 'dry' else '已'
    tmax = float(LEADER_TURNOVER_MAX) if (LEADER_TURNOVER_MAX and LEADER_TURNOVER_MAX > 0) else 0.0
    log.info("🐲 【龙头过滤·%s】池 %d 只 → %s保留 %d 只｜池内最高连板 %d（下限 %d）%s"
             % (LEADER_FILTER_MODE, st['n'], tag, len(after), st['maxb'], int(LEADER_MIN_BOARDS),
                ('｜换手上限 %.1f%%' % tmax) if tmax else '｜不看换手'))
    if st.get('note'):
        log.info("🐲 【龙头过滤】%s" % st['note'])
    if LEADER_FILTER_MODE == 'dry' and st['n'] > 0 and after:
        log.info("🐲 【龙头过滤·dry明细】%s保留: %s"
                 % (tag, ', '.join('%s(连板%s)' % (c, st['boards'].get(c, '?')) for c in after[:10])))


def auction_filter(context):
    log.info("="*50)
    log.info("9:26 竞价过滤")
    if g.filter_kcb:
        g.candidate_stocks = [s for s in g.candidate_stocks if get_stock_board(s) != 'star']
    
    final_stocks = []
    range_filter_count = 0
    risk_filter_count = 0
    other_filter_count = 0
    current_date = context.current_dt.date()
    
    for stock in g.candidate_stocks:
        if not check_basic_quality(stock, context):
            other_filter_count += 1
            continue
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知"
        is_risk = False
        try:
            board = get_stock_board(stock)
            trade_days = get_trade_days(end_date=current_date, count=2)
            if len(trade_days) < 2:
                other_filter_count += 1
                continue
            yesterday = trade_days[0]
            hist = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
            if hist.empty:
                other_filter_count += 1
                continue
            close_yest = hist['close'].iloc[0]
            current_data = get_current_data()[stock]
            open_price = current_data.day_open
            open_ratio = (open_price - close_yest) / close_yest * 100
            
            if not (g.min_open_ratio <= open_ratio <= g.max_open_ratio):
                is_risk = True
                range_filter_count += 1
            
            if not is_risk:
                vol_hist = attribute_history(stock, 3, '1d', fields=['close', 'volume', 'high_limit'], skip_paused=True, df=True)
                if len(vol_hist) >= 3:
                    vol_yest = vol_hist['volume'].iloc[-1]
                    vol_beyest = vol_hist['volume'].iloc[-2]
                    high_limit = vol_hist['high_limit'].iloc[-1]
                    is_limit_up = abs(close_yest - high_limit) / high_limit < 0.006
                    is_vol_big = vol_yest >= vol_beyest * 1.8
                    if is_limit_up and is_vol_big:
                        if board == 'main':
                            threshold = g.risk_open_threshold_main
                        else:
                            threshold = g.risk_open_threshold_gem_star
                        if open_ratio >= threshold:
                            is_risk = True
                            risk_filter_count += 1
        except:
            is_risk = True
            other_filter_count += 1
        
        if not is_risk:
            final_stocks.append(stock)
    
    # 【回测版】竞价增强（默认 shadow 只记录；'on' 才真正过滤候选池）
    try:
        _gate = auction_gate(context, final_stocks)
        if AUCTION_GATE_MODE == 'on':
            final_stocks = _gate
    except Exception as e:
        log.info("⚠️ 竞价增强异常（已忽略）: %s" % str(e)[:60])
    # 【V5.0·v22.2】复牌票禁买（昨日=复牌首日的候选剔除）
    try:
        final_stocks = v5_resume_filter(final_stocks, context)
    except Exception as _e:
        log.info("⚠️ 复牌过滤异常（已忽略）: %s" % str(_e)[:60])
    # 【V4.1】买入侧龙头过滤（off = 完全跳过，保证与 V4.0 行为一致）
    if LEADER_FILTER_MODE != 'off':
        try:
            _td = get_trade_days(end_date=context.current_dt.date(), count=2)
            _yest = _td[0] if _td is not None and len(_td) > 0 else None
            _before = list(final_stocks)
            _keep, _st = jq21_leader_filter(_before, _yest)
            if LEADER_FILTER_MODE == 'on':
                final_stocks = list(_keep)
            jq21_leader_report(_st, _before, _keep)
        except Exception as _e:
            log.info("⚠️ 龙头过滤异常（已忽略，不影响候选池）: %s" % str(_e)[:80])
    g.candidate_stocks = list(final_stocks)
    g.rebuy_candidates = list(final_stocks)
    log.info(f"竞价过滤统计：通过 {len(final_stocks)} 只 | 区间不符 {range_filter_count} | 风险股 {risk_filter_count} | 其他 {other_filter_count}")
    if not final_stocks and g.candidate_stocks and other_filter_count >= len(g.candidate_stocks):
        log.info("   ⚠️ 全部候选死在『其他』层 = check_basic_quality 未通过（最常见原因："
                 "开盘前读不到当日数据 → 检查是否开了 set_option('avoid_future_data', True)）")
    
    if final_stocks:
        log.info(f"🎯 【最终候选股名单】共 {len(final_stocks)} 只")
    else:
        log.info("⚠️ 竞价过滤后无候选股")

# ==================== 【V5.0】卖出引擎（全面对齐 PTrade V25 实盘口径） ====================
# 结构：A6 兜底与方向分流（v20）→ 炸板尺/均线尺与统一裁决（v232）→ 卖出相关函数（原有）
# 聚宽适配：快照/1 分钟 bar 取数（无未来函数）；"格" = tick 频率下 3 秒、分钟频率下 1 分钟

def _sec_of(t):
    """'HH:MM[:SS]' → 当天秒数"""
    try:
        p = str(t).split(':')
        return int(p[0]) * 3600 + int(p[1]) * 60 + (int(p[2]) if len(p) > 2 else 0)
    except Exception:
        return 0


def _pre_close_cached(stock, context):
    """昨收带日内缓存（昨收一天不变；tick 模式下每格查 attribute_history 太贵）"""
    try:
        _c = getattr(g, '_pre_close_cache', None)
        if _c is None:
            _c = g._pre_close_cache = {}
        _d = str(context.current_dt.date())
        _v = _c.get((_d, stock))
        if _v is not None:
            return _v
        _v = _pre_close(stock, context)
        if _v and _v > 0:
            _c[(_d, stock)] = _v
        return _v
    except Exception:
        return _pre_close(stock, context)


def _rt_of(stock, context):
    """统一行情口径（无未来函数）：昨收/今开/现价/当日最高/当日最低/涨停/跌停。
    当日最高最低：优先 tick 缓存（handle_tick 逐格维护），否则用 1 分钟 bar 累计。"""
    out = {'pre': 0.0, 'open': 0.0, 'last': 0.0, 'high': 0.0, 'low': 0.0,
           'up': 0.0, 'dn': 0.0, 'wavg': 0.0}
    try:
        cd = get_current_data()[stock]
        out['open'] = float(cd.day_open or 0)
        out['last'] = float(cd.last_price or 0)
        out['up'] = float(cd.high_limit or 0)
        out['dn'] = float(cd.low_limit or 0)
    except Exception:
        pass
    out['pre'] = _pre_close_cached(stock, context)
    # tick 缓存（本格新鲜度：同一秒内有效）
    _tp = getattr(g, '_tick_px', {}).get(stock)
    _nows = context.current_dt.strftime('%H:%M:%S')
    if _tp and _tp.get('t') == _nows:
        for k in ('last', 'high', 'low', 'open'):
            if float(_tp.get(k) or 0) > 0:
                out[k] = float(_tp[k])
        if float(_tp.get('pre') or 0) > 0:
            out['pre'] = float(_tp['pre'])
        if float(_tp.get('up') or 0) > 0:
            out['up'] = float(_tp['up'])
    # 当日最高/最低：1 分钟 bar 累计（tick 缓存缺失/过期时）
    if out['high'] <= 0 or out['low'] <= 0:
        try:
            _d = context.current_dt.date()
            _st = datetime.datetime.combine(_d, datetime.time(9, 30))
            df = get_price(stock, start_date=_st, end_date=context.current_dt, frequency='1m',
                           fields=['high', 'low'], fq='pre', skip_paused=True)
            if df is not None and len(df) > 0:
                if out['high'] <= 0:
                    out['high'] = float(df['high'].max() or 0)
                if out['low'] <= 0:
                    out['low'] = float(df['low'].min() or 0)
        except Exception:
            pass
    out['wavg'] = _wavg_of(stock, context)
    return out


def _wavg_of(stock, context):
    """盘中均价近似 = 当日累计成交额 ÷ 累计成交量。
    【V5.0a】优先 tick 缓存（money/vol，09:31 前 1 分钟 bar 不存在）；15 秒节流缓存。
    取不到返回 0（= 未判定：毛刺过滤退化为'连续 2 格确认'路径）。"""
    try:
        _nows = context.current_dt.strftime('%H:%M:%S')
        _c = getattr(g, '_wavg_cache', {})
        _hit = _c.get(stock)
        if _hit and (_nows[0:4] == _hit[0] or
                     (_sec_of(_nows) - _hit[1]) < 15):
            return _hit[2]
        v = 0.0
        # ① tick 缓存优先（tick 频率回测 15 秒定盘关键数据源）
        try:
            _tp = getattr(g, '_tick_px', {}).get(stock)
            if _tp and float(_tp.get('money') or 0) > 0 and float(_tp.get('vol') or 0) > 0:
                _age = _sec_of(_nows) - _sec_of(_tp.get('t', ''))
                if 0 <= _age <= 15:
                    v = float(_tp['money']) / float(_tp['vol'])
        except Exception:
            v = 0.0
        # ② 1 分钟 bar 兜底（分钟频率回测 / tick 缓存缺失）
        if v <= 0:
            _d = context.current_dt.date()
            _st = datetime.datetime.combine(_d, datetime.time(9, 30))
            df = get_price(stock, start_date=_st, end_date=context.current_dt, frequency='1m',
                           fields=['money', 'volume'], fq='pre', skip_paused=True)
            if df is not None and len(df) > 0:
                _m = float(df['money'].sum())
                _v = float(df['volume'].sum())
                if _m > 0 and _v > 0:
                    v = _m / _v
        _c[stock] = (_nows[0:4], _sec_of(_nows), v)
        g._wavg_cache = _c
        return v
    except Exception:
        return 0.0


# ---------------- 【v20.1】当日卖出后禁止买回 ----------------
def _sold_today_codes():
    """当日已报出卖单的代码集合（数据源 = g.sold_today，execute_sell 成功后 append）"""
    out = set()
    try:
        for _x in (getattr(g, 'sold_today', None) or []):
            _c = _x.get('code') if isinstance(_x, dict) else None
            if _c:
                out.add(_c)
    except Exception:
        pass
    return out


def v20_rebuy_blocked(stock):
    """【v20.1】该票今天是否已被卖掉 → 买入侧应否拦下。返回 (是否拦下, 原因)。"""
    try:
        if REBUY_GUARD_MODE == 'off':
            return (False, '')
        if stock not in _sold_today_codes():
            return (False, '')
        if REBUY_GUARD_MODE == 'dry':
            log.info("🧪【v20.1·dry】今日已卖出 → 本应禁止买回：%s" % stock)
            return (False, '')
        return (True, '今日已卖出（禁止当日买回）')
    except Exception:
        return (False, '')


# ---------------- 【v20.2/v20.3】开盘方向分流 ----------------
def _v22_dive_judge(op, last, low, dn):
    """【v22.4】俯冲判定。破位线 = 当日最低（缺失时用现价）≤ 开盘×(1−DIVE_PCT%)；
    触发条件 = 现价跌破开盘，或（DIVE_AT_LIMIT_DOWN_MODE='on' 时）已贴跌停。"""
    try:
        if op <= 0:
            return False
        _thr = op * (1 - OPEN_DIRECTION_DIVE_PCT / 100.0)
        _on = str(DIVE_AT_LIMIT_DOWN_MODE) == 'on'
        _at_down = bool(_on and dn > 0 and last > 0 and last <= dn * 1.001)
        _hit = (low > 0 and low <= _thr) or (low <= 0 and last > 0 and last <= _thr) or _at_down
        if not _hit:
            return False
        if last < op:
            return True
        return _at_down
    except Exception:
        return False


def _v20_dive_filter(stock, op, last, dived, wavg):
    """【v21.3】毛刺过滤：破位 ≠ 真跌。返回 (实际应卖, 说明)。
    确认条件（满足任一）：① 现价 < 盘中均价（成交重心已下移）② 连续 DIVE_CONFIRM_TICKS 格仍破位。"""
    try:
        if str(DIVE_FILTER_MODE) == 'off':
            return dived, ''
        _st = getattr(g, 'v20_dive_prev', None)
        if _st is None:
            _st = g.v20_dive_prev = {}
        _grid = context_grid_id(context)
        if not dived:
            _st[stock] = (_grid, False, 0, False, '')
            return False, ''
        _rec = _st.get(stock)
        if _rec is not None and _rec[0] == _grid:
            return _rec[3], _rec[4]                     # 同一格多入口复用
        _streak = (_rec[2] + 1) if (_rec is not None and _rec[1]) else 1
        _need = max(1, int(DIVE_CONFIRM_TICKS or 2))
        _avg_ok = (wavg > 0 and last < wavg)
        _streak_ok = (_streak >= _need)
        _ok = bool(_streak_ok) if str(DIVE_REQUIRE_2TICK) == 'on' else bool(_avg_ok or _streak_ok)
        _tag = ('第%d格破位｜现价%.3f｜均价%s｜%s'
                % (_streak, last, ('%.3f' % wavg) if wavg > 0 else '取不到',
                   '✅均价确认→卖' if _avg_ok else ('✅连续%d格确认→卖' % _need if _streak_ok
                                                else '🧪疑似毛刺→保留')))
        _st[stock] = (_grid, True, _streak, _ok, _tag)
        if str(DIVE_FILTER_MODE) == 'on':
            return _ok, _tag
        return True, _tag                               # dry：真实决定照旧
    except Exception:
        return dived, ''


def context_grid_id(context):
    """当前"格"ID（tick 频率=每 3 秒一格、分钟频率=每分钟一格，均以时间串区分）—— 用于同格去重"""
    try:
        return context.current_dt.strftime('%H:%M:%S')
    except Exception:
        return ''


def v20_dir_should_defer(context, stock, rt):
    """【v20.2】09:30 岔路口：自有持仓（非今日买入、开盘未涨停）延后 → 交方向分流。
    'off' → False（旧行为照卖）；'on' → True（延后）。"""
    try:
        if OPEN_DIRECTION_MODE == 'off':
            return False
        if stock in g.bought_stocks:                    # T+1：今日买入不可卖
            return False
        if stock not in getattr(g, 'own_codes', set()):
            return False
        op = float((rt or {}).get('open') or 0)
        last = float((rt or {}).get('last') or 0)
        if op <= 0:
            return False
        if OPEN_DIRECTION_MODE == 'on':
            g.v20_dir_deferred[stock] = {'open': op, 'last': last}
            log.info("⏸【v20.2】自有持仓延后到方向分流：%s | 今开%.3f 现价%.3f（开盘%+.2f%%）"
                     % (stock, op, last, (last / op - 1) * 100 if op else 0))
            return True
        return False
    except Exception:
        return False


def v20_direction_route(context):
    """【v20.2】定盘格（≥09:30:15）处置延后持仓：俯冲 → 立刻卖；其余 → 进冲高监控。"""
    try:
        if OPEN_DIRECTION_MODE == 'off':
            return
        _df = getattr(g, 'v20_dir_deferred', None) or {}
        if not _df:
            return
        for stock in list(_df.keys()):
            try:
                pos = context.portfolio.positions.get(stock)
                if pos is None or float(getattr(pos, 'total_amount', 0) or 0) <= 0:
                    _df.pop(stock, None)
                    continue
                rt = _rt_of(stock, context)
                op, last = rt['open'], rt['last']
                if op <= 0 or last <= 0:
                    _df.pop(stock, None)
                    continue
                dived = _v22_dive_judge(op, last, rt['low'], rt['dn'])
                dived, _dz = _v20_dive_filter(stock, op, last, dived, rt['wavg'])
                if _dz:
                    log.info("🧪【v21.3】%s 毛刺过滤：%s" % (stock, _dz))
                if dived:
                    if v232_gate(context, stock, op, last, rt['high'], rt['low'], rt['wavg'], rt['up'], rt['dn']):
                        log.info("📤【v20.2】判定俯冲 → 立刻卖出：%s | 今开%.3f 最低%.3f 现价%.3f"
                                 % (stock, op, rt['low'], last))
                        v20_do_sell(context, stock, '开盘俯冲%.2f%%' % ((last / op - 1) * 100))
                    _df.pop(stock, None)
                    continue
                _trig = round(op * (1 + EARLY_EXIT_TRIGGER_PCT_REF / 100.0), 2)
                g.v20_watch[stock] = {'trig': _trig, 'arm': False, 'hi': 0.0}
                log.info("🎯【v20.2】非俯冲 → 进冲高监控：%s | 今开%.3f 现价%.3f（开盘%+.2f%%）触发线%.3f"
                         "触发后回落%.1f%% 卖；未触发自最高回落%.1f%% 卖；%s 兜底现价卖"
                         % (stock, op, last, (last / op - 1) * 100, _trig,
                            EARLY_EXIT_PULLBACK_PCT_REF, OPEN_DIRECTION_FALLBACK_STALL_PCT,
                            OPEN_DIRECTION_DEADLINE))
                _df.pop(stock, None)
            except Exception:
                _df.pop(stock, None)
    except Exception as e:
        log.info("⚠️ v20_direction_route 异常: %s" % str(e)[:60])


EARLY_EXIT_TRIGGER_PCT_REF = 2.0     # 冲高触发：现价 ≥ 基准 × (1 + 2%)（对齐 V25 v20.4）
EARLY_EXIT_PULLBACK_PCT_REF = 0.5    # 触发后从最高回落 0.5% → 卖出（对齐 V25 v21.4.3）


def v20_dir_autowatch(context):
    """【v20.3】09:30:03 起每格：把自有持仓纳入方向监控 + 判"俯冲"（含毛刺过滤）。"""
    try:
        if OPEN_DIRECTION_MODE == 'off':
            return
        _sold = _sold_today_codes()
        for stock in list(context.portfolio.positions.keys()):
            try:
                pos = context.portfolio.positions.get(stock)
                if pos is None or float(getattr(pos, 'total_amount', 0) or 0) <= 0:
                    continue
                if stock in g.bought_stocks or stock in _sold:
                    continue
                if stock not in getattr(g, 'own_codes', set()):
                    continue
                if stock in getattr(g, 'sell_requested', set()):
                    continue
                rt = _rt_of(stock, context)
                op, last, up = rt['open'], rt['last'], rt['up']
                if op <= 0 or last <= 0:
                    continue
                if up > 0 and last >= up - 0.001:       # 贴板/一字：不卖不挂（留破板回落管）
                    continue
                dived = _v22_dive_judge(op, last, rt['low'], rt['dn'])
                dived, _dz = _v20_dive_filter(stock, op, last, dived, rt['wavg'])
                if stock not in g.v20_watch and not dived:
                    _trig = round(op * (1 + EARLY_EXIT_TRIGGER_PCT_REF / 100.0), 2)
                    g.v20_watch[stock] = {'trig': _trig, 'arm': False, 'hi': 0.0}
                    log.info("🎯【v20.3】开盘接管冲高监控：%s | 今开%.3f 现价%.3f（开盘%+.2f%%）触发线%.3f"
                             % (stock, op, last, (last / op - 1) * 100, _trig))
                if dived:
                    if v232_gate(context, stock, op, last, rt['high'], rt['low'], rt['wavg'], rt['up'], rt['dn']):
                        log.info("📤【v20.3】俯冲（每格判）→ 立刻卖出：%s | 今开%.3f 最低%.3f 现价%.3f（开盘%+.2f%%）"
                                 % (stock, op, rt['low'], last, (last / op - 1) * 100))
                        v20_do_sell(context, stock, '开盘俯冲%.2f%%' % ((last / op - 1) * 100))
                        g.v20_watch.pop(stock, None)
            except Exception:
                continue
    except Exception as e:
        log.info("⚠️ v20_dir_autowatch 异常: %s" % str(e)[:60])


def v20_do_sell(context, stock, why):
    """【v20】方向分流卖出出口：'on' 真下单（走 execute_sell 自带三道守卫），dry 只打印。"""
    try:
        if OPEN_DIRECTION_MODE != 'on':
            log.info("🧪【v20·dry】本应卖出 %s（原因：%s）—— 模拟模式，未下单" % (stock, why))
            return False
        log.info("📤【v20】卖出 %s（原因：%s）" % (stock, why))
        return execute_sell(stock, context)
    except Exception as e:
        log.info("⚠️ v20_do_sell 异常: %s" % str(e)[:60])
        return False


def v20_engine(context):
    """【V5.0】方向分流总入口（每格调一次，tick=3 秒 / 分钟=1 分钟）：
    ① 定盘后补跑 v20_direction_route；② 09:30:03~11:30 autowatch；③ 冲高监控逐格跟踪。"""
    try:
        if OPEN_DIRECTION_MODE == 'off':
            return
        now = context.current_dt
        t = now.strftime('%H:%M:%S')
        sec = _sec_of(t)
        dsec = _sec_of(OPEN_DIRECTION_DEADLINE + ':00')
        # ① 定盘（≥09:30:15）后补处置延后名单
        if getattr(g, 'v20_dir_deferred', None) and now.time() >= DECIDE_SECOND:
            v20_direction_route(context)
        if sec < _sec_of(OPEN_DIRECTION_START + ':00'):
            return
        # ② 纳入监控 + 俯冲判定（09:30:03 ~ 11:30）
        if sec <= dsec:
            v20_dir_autowatch(context)
        # ③ 冲高监控逐格跟踪
        _w = getattr(g, 'v20_watch', None) or {}
        for stock in list(_w.keys()):
            try:
                _it = _w[stock]
                pos = context.portfolio.positions.get(stock)
                if pos is None or float(getattr(pos, 'total_amount', 0) or 0) <= 0:
                    _w.pop(stock, None)
                    continue
                rt = _rt_of(stock, context)
                op, last, high = rt['open'], rt['last'], rt['high']
                if last <= 0:
                    continue
                if sec >= dsec:
                    # 【v23.3·F3】A6 兜底：11:30 到点未触发 → 现价卖（受统一裁决约束）
                    if v232_gate_any(context, stock, '%s兜底' % OPEN_DIRECTION_DEADLINE):
                        log.info("⏰【v20】%s 到点未触发冲高 → 兜底卖出：%s | 已触发=%s 现价%.3f 触发线%.3f"
                                 % (OPEN_DIRECTION_DEADLINE, stock, _it.get('arm'), last, _it.get('trig', 0)))
                        v20_do_sell(context, stock, '%s兜底' % OPEN_DIRECTION_DEADLINE)
                    _w.pop(stock, None)
                    continue
                # 当日最高累计（未触发也跟踪）
                if high > 0:
                    _it['hi'] = max(float(_it.get('hi', 0.0)), high)
                if float(_it.get('hi', 0.0)) <= 0:
                    _it['hi'] = last
                # 未触发：自当日最高回落 ≥ FALLBACK% → 卖（v20.5-A）
                if not _it.get('arm'):
                    _fb = float(OPEN_DIRECTION_FALLBACK_STALL_PCT or 0)
                    _hi = float(_it.get('hi', 0.0))
                    if _fb > 0 and _hi > 0:
                        _fbpb = (_hi - last) / _hi * 100
                        if _fbpb >= _fb:
                            if v232_gate_any(context, stock, '未触发兜底回落'):
                                log.info("📤【v20.5】未触发兜底（自当日最高%.3f 回落%.2f%%≥%.1f%%）→ 卖出：%s 现价%.3f"
                                         % (_hi, _fbpb, _fb, stock, last))
                                v20_do_sell(context, stock, '未触发兜底回落%.2f%%' % _fbpb)
                            _w.pop(stock, None)
                            continue
                    if last >= float(_it.get('trig', 0)) > 0:
                        _it['arm'] = True
                        _it['hi'] = max(last, high)
                        log.info("⚡【v20】冲高触发：%s 现价%.3f ≥ 触发线%.3f → 跟踪最高价，回落%.1f%% 即卖"
                                 % (stock, last, _it.get('trig', 0), EARLY_EXIT_PULLBACK_PCT_REF))
                    else:
                        continue
                if high > 0:
                    _it['hi'] = max(float(_it.get('hi', 0.0)), high)
                _it['hi'] = max(float(_it.get('hi', 0.0)), last)
                _hi = float(_it.get('hi', 0.0))
                _pb = (_hi - last) / _hi * 100 if _hi > 0 else 0.0
                if _pb >= EARLY_EXIT_PULLBACK_PCT_REF:
                    # 【v23.2】统一裁决（arm 后冲高回落路）
                    if v232_gate(context, stock, op, last, high, rt['low'], rt['wavg'], rt['up'], rt['dn'], rise=True):
                        log.info("📤【v20】冲高回落卖出：%s | 触发后最高%.3f 现价%.3f 回落%.2f%%(阈值%.1f%%)"
                                 % (stock, _hi, last, _pb, EARLY_EXIT_PULLBACK_PCT_REF))
                        v20_do_sell(context, stock, '冲高回落%.2f%%' % _pb)
                    _w.pop(stock, None)
            except Exception:
                continue
    except Exception as e:
        log.info("⚠️ v20_engine 异常: %s" % str(e)[:60])


# ---------------- 【v23.3】炸板尺 / 均线尺 + 统一裁决 ----------------
def _v232_state():
    _all = getattr(g, 'v232', None)
    if not isinstance(_all, dict):
        _all = g.v232 = {}
    return _all


def _v233_log_once(_st, key, text):
    try:
        _seen = _st.setdefault('logged', set())
        if key in _seen:
            return
        _seen.add(key)
        log.info(text)
    except Exception:
        pass


def _v232_reset_obs(_st):
    for k in ('t0', 'obs_start', 'obs_n', 'T0px', 'L0', 'streak_up', 'stall_n', 'last_px', 'exited'):
        _st.pop(k, None)


def _v233_mark_pending(_st, stock, sec, rule):
    """【F10】判卖后置 sticky 挂起：该格若被吞，下一格直接继续判卖。"""
    try:
        _st['sell_pending'] = True
        _st['pending_rule'] = rule
        _st['pending_sec'] = sec
    except Exception:
        pass


def _v233_pending_alive(context, stock, _st):
    """卖出挂起是否仍有效：持仓还在且未过 V233_PENDING_WARN_SEC。"""
    try:
        if stock not in context.portfolio.positions:
            _st['sell_pending'] = False
            return False
        _sec0 = float(_st.get('pending_sec') or 0)
        _sec = _sec_of(context.current_dt.strftime('%H:%M:%S'))
        if _sec0 > 0 and _sec - _sec0 > float(V233_PENDING_WARN_SEC):
            _st['sell_pending'] = False
            return False
        return True
    except Exception:
        return False


V233_PENDING_WARN_SEC = 600          # 【F10】卖出挂起超时（秒）


def _v232_eval(_st, stock, op, last, high, low, wavg, up_px, dn_px, _t):
    """【v23.3】两把尺子核心判定。返回 (should_sell, rule, detail)：
        True → 卖；False → 本格不卖；None → 判不出来 → 交回旧逻辑。
    总开关：当日曾触板（当日最高 ≥ 涨停×0.995）→ A 炸板尺；否则 → B 均线尺。
    【F1】L0 = 进入观察那一刻起的最低现价（绝不用当日最低）；卖出线用"上一格为止的 L0"。
    【防插针】前 2 格只记 L0、不判弱势卖出。"""
    _op = float(op or 0)
    _last = float(last or 0)
    _w = float(wavg or 0)
    _up = float(up_px or 0)
    _dn = float(dn_px or 0)
    _hi = float(high or 0)
    _sec = float(_sec_of(_t))
    if _hi > float(_st.get('hist_high') or 0):
        _st['hist_high'] = _hi
    _hist = max(_hi, float(_st.get('hist_high') or 0))
    # 【F2】触板信息缺失 ⇒ 交回旧逻辑（不判方向）
    if _up <= 0 or _hist <= 0:
        _v233_log_once(_st, 'nodata',
                       "⚠️【v23.3】%s ｜ 触板信息缺失 ⇒ 本格交回旧逻辑" % stock)
        return None, 'nodata', '触板信息缺失'
    _touch = bool(_hist >= _up * 0.995)                 # 总开关：当日曾触板
    _st['touch'] = _touch
    if not _touch:
        # ==================== B 均线尺（未触板的票）====================
        if _w <= 0 or _op <= 0:
            return None, '均线', '均价/开盘取不到 → 交回旧逻辑'
        _drop = (_op - _w) / _op * 100.0
        _v = bool(_drop >= float(V232_MA_FOLLOW_PCT))
        return _v, '均线', '均价%.3f vs 开盘%.3f 下移%.2f%%(阈值%.2f%%)' % (_w, _op, _drop, V232_MA_FOLLOW_PCT)
    # ==================== A 炸板尺（曾触板的票）====================
    # ④ 贴跌停：硬例外，最高优先
    if _dn > 0 and _last > 0 and _last <= _dn * 1.001:
        log.info("📤【v23.3】%s 卖出（原因：贴跌停）" % stock)
        _v233_mark_pending(_st, stock, _sec, '贴跌停')
        return True, '贴跌停', '现价%.3f ≤ 跌停价%.3f×1.001' % (_last, _dn)
    # ① 回封：强势，不卖，退出观察（清观察态 ⇒ 日后再破位用新低点重新观察）
    if _last > 0 and _last >= _up * (1 - V232_SEAL_GAP_PCT / 100.0):
        _v233_log_once(_st, 'seal',
                       "🟢【v23.3】%s ｜ 回封（现价%.3f ≥ 涨停%.3f×(1−%.2f%%)）→ 不卖，退出观察"
                       % (stock, _last, _up, V232_SEAL_GAP_PCT))
        _v232_reset_obs(_st)
        _st['exited'] = True
        return False, '回封', '现价%.3f ≥ 涨停价×(1−%.2f%%)' % (_last, V232_SEAL_GAP_PCT)
    # 是否已进入观察
    if not _st.get('t0'):
        _trig = _up * (1 - V232_TRIGGER_GAP_PCT / 100.0)
        if _trig > 0 and _last > 0 and _last < _trig:
            _st['t0'] = _t
            _st['obs_start'] = _sec
            _st['obs_n'] = 1
            _st['T0px'] = _last
            _st['L0'] = _last                        # 【F1】L0 = 进观察那一刻的现价
            _st['streak_up'] = 0
            _st['stall_n'] = 0
            _st['last_px'] = _last
            _st['exited'] = False
            log.info("🚨【v23.3】%s ｜ 尺=炸板 ｜ 进入观察（现价%.3f 跌破%.3f=涨停%.3f×(1−%.2f%%)）"
                     % (stock, _last, _trig, _up, V232_TRIGGER_GAP_PCT))
            return False, '炸板', '进入观察'
        return None, '炸板', '未跌破触发线 → 交回旧逻辑'
    # ---- 观察期内 ----
    _st['obs_n'] = int(_st.get('obs_n', 1) or 1) + 1
    _L0prev = float(_st.get('L0') or 0)
    if _L0prev <= 0:
        _L0prev = _last
    _st['L0'] = min(_L0prev, _last) if _last > 0 else _L0prev
    _L0 = float(_st.get('L0') or 0)
    _T0 = float(_st.get('T0px') or 0)
    _obs_sec = _sec - float(_st.get('obs_start') or _sec)
    _rec = 0.0
    if _up > _L0 > 0 and _last > 0:
        _rec = (_last - _L0) / (_up - _L0)
    _prev = float(_st.get('last_px') or 0)
    if _last > _prev > 0:
        _st['streak_up'] = int(_st.get('streak_up', 0) or 0) + 1
        _st['stall_n'] = 0
    else:
        _st['streak_up'] = 0
        _st['stall_n'] = int(_st.get('stall_n', 0) or 0) + 1
    _st['last_px'] = _last
    _up_n = int(_st.get('streak_up', 0) or 0)
    _slog = ('现价%.3f ｜ L0=%.3f ｜ 回升率%.1f%% ｜ 连续抬高%d格 ｜ 已观察%.0fs ｜ T0价%.3f'
             % (_last, _L0, _rec * 100.0, _up_n, _obs_sec, _T0))
    # ② 在回升（强势）：回升率达标 且 连续 2 格抬高 → 不卖
    if _rec >= float(V232_RECOVER_RATIO) and _up_n >= 2:
        return False, '回升', '回升率%.1f%% ≥ %.0f%% 且连续2格抬高 ｜ %s' % (_rec * 100, V232_RECOVER_RATIO * 100, _slog)
    # 【防插针】前 2 格只建 L0、不判弱势卖出
    if int(_st.get('obs_n', 0) or 0) <= 2:
        return False, '炸板', '观察中（前2格只记 L0）｜ %s' % _slog
    # 弱势① 破新低（卖出线用"上一格为止的 L0"）
    if _L0prev > 0 and _last > 0 and _last <= _L0prev * (1 - V232_NEW_LOW_PCT / 100.0):
        log.info("📤【v23.3】%s 卖出（原因：跌破 L0 新低）" % stock)
        _v233_mark_pending(_st, stock, _sec, '新低')
        return True, '新低', '现价%.3f ≤ L0(上一格)%.3f×(1−%.2f%%) ｜ %s' % (_last, _L0prev, V232_NEW_LOW_PCT, _slog)
    # 弱势③ 回升停滞（卖）
    if (int(_st.get('stall_n', 0) or 0) >= int(V232_STALL_TICKS) and _T0 > 0 and _last > 0
            and _last <= _T0 * (1 - float(V232_STALL_DROP_PCT) / 100.0)):
        log.info("📤【v23.3】%s 卖出（原因：回升停滞且回落）" % stock)
        _v233_mark_pending(_st, stock, _sec, '回升停滞')
        return True, '回升停滞', '连续%d格不再抬高 且 现价%.3f ≤ T0价%.3f×(1−%.2f%%) ｜ %s' \
            % (int(V232_STALL_TICKS), _last, _T0, float(V232_STALL_DROP_PCT), _slog)
    # 弱势④ 窗口到期（主判据 = 格数，时间兜底）
    if int(_st.get('obs_n', 0) or 0) > int(V232_CONFIRM_TICKS) or _obs_sec > float(V232_OBSERVE_MAX_SEC):
        log.info("📤【v23.4】%s 卖出（原因：观察窗口到期）" % stock)
        _v233_mark_pending(_st, stock, _sec, '窗口到期')
        return True, '窗口到期', '格 %d/%d ｜ 自炸板%.0fs/%ds ｜ %s' \
            % (int(_st.get('obs_n', 0) or 0), int(V232_CONFIRM_TICKS), _obs_sec, V232_OBSERVE_MAX_SEC, _slog)
    return False, '炸板', '观察中 ｜ %s' % _slog


def v232_decision(context, stock, op, last, high, low, wavg, up_px, dn_px):
    """【v23.3】两把尺子判定入口（同格缓存：一格内多条路重复调用只推进一次状态）。
    【F10】卖出挂起（sticky）⇒ 继续判卖；【F11】时钟缺失 ⇒ (None,'no_clock') 交回旧逻辑。"""
    try:
        if str(RULE_V232_MODE) == 'off':
            return None, 'off', 'MODE=off → 交回旧逻辑'
        _t = context.current_dt.strftime('%H:%M:%S')
        if not _t:
            return None, 'no_clock', '时钟缺失'
        _all = _v232_state()
        _st = _all.get(stock)
        if not isinstance(_st, dict):
            _st = _all[stock] = {}
        if _st.get('sell_pending') and _v233_pending_alive(context, stock, _st):
            return True, '挂起待成交', '卖出已挂起（原判据=%s）' % (_st.get('pending_rule') or '-')
        if _st.get('_ck_tick') == _t and _st.get('_ck_val') is not None:
            return _st['_ck_val']                        # 同一格内重复查询 → 复用
        _val = _v232_eval(_st, stock, op, last, high, low, wavg, up_px, dn_px, _t)
        _st['_ck_tick'] = _t
        _st['_ck_val'] = _val
        return _val
    except Exception as e:
        return None, 'err', repr(e)[:80]


def v232_gate(context, stock, op, last, high, low, wavg, up_px, dn_px, rise=False):
    """【v23.3】统一裁决 —— 俯冲/破位、破板回落、arm 后冲高回落 三条路共用。
    返回 True = 允许按原逻辑卖；False = 本格抑制该路卖出。
    rise=True（冲高回落路）仅当「炸板尺处于 观察/回升」才抑制；未触板/已回封不受影响。"""
    try:
        if str(RULE_V232_MODE) == 'off':
            return True
        _sw, _rule, _dtl = v232_decision(context, stock, op, last, high, low, wavg, up_px, dn_px)
        if _sw is not False or str(RULE_V232_MODE) != 'on':
            return True
        _obs = _rule in ('炸板', '回升', '回封')         # 炸板尺"判不卖且处于观察/回升/回封"
        if rise and not _obs:
            return True
        if _obs:
            _st = _v232_state().get(stock)
            if isinstance(_st, dict):
                _t = context.current_dt.strftime('%H:%M:%S')
                if _st.get('sup_log') != _t:
                    _st['sup_log'] = _t
                    log.info("🔒【v23.2】%s ｜ 炸板尺不卖 ⇒ 已抑制 俯冲/破板回落/冲高回落 三条路" % stock)
        return False
    except Exception:
        return True


def v232_gate_any(context, stock, reason):
    """【v23.3·F3】统一裁决补全 —— 给 11:30 兜底 / 未触发兜底回落 / 破板回落（09:30 + 2 分钟）加同一道闸门。
    取数失败/判不出来 ⇒ 放行（宁可卖也不卡死）；现价贴近涨停(≥涨停×0.999) ⇒ 一律不卖。"""
    try:
        if str(RULE_V232_MODE) != 'on':
            return True
        rt = _rt_of(stock, context)
        _op, _last = rt['open'], rt['last']
        _up = rt['up']
        # 贴近涨停（回封票）⇒ 一律不卖
        if _up > 0 and _last > 0 and _last >= _up * (1 - V232_SEAL_GAP_PCT / 100.0):
            _st = _v232_state().setdefault(stock, {})
            _v233_log_once(_st, 'sup233',
                           "🔒【v23.3】%s ｜ 现价%.3f 贴近涨停%.3f ⇒ 已抑制 %s" % (stock, _last, _up, reason))
            return False
        _sw, _rule, _dtl = v232_decision(context, stock, _op, _last, rt['high'], rt['low'],
                                         rt['wavg'], _up, rt['dn'])
        if _sw is not False:
            return True                      # 卖 / nodata / 判不出来 → 放行
        if _rule in ('炸板', '回升', '回封'):
            _st = _v232_state().setdefault(stock, {})
            _v233_log_once(_st, 'sup233',
                           "🔒【v23.3】%s ｜ 炸板尺不卖 ⇒ 已抑制 %s" % (stock, reason))
            return False
        return True
    except Exception:
        return True


# ---------------- 【v22.2】复牌票禁买 ----------------
def v5_resume_filter(stocks, context):
    """复牌首日候选剔除：昨日（最近交易日）有日线、前一交易日没有 ⇒ 昨日 = 复牌首日。"""
    if RESUME_FILTER_MODE == 'off' or not stocks:
        return list(stocks)
    try:
        _td = get_trade_days(end_date=context.current_dt.date(), count=2)
        if _td is None or len(_td) < 2:
            return list(stocks)
        _yest, _prev = _td[-1], _td[-2]
        keep, dropped = [], []
        for s in stocks:
            try:
                h = attribute_history(s, 2, '1d', ['close'], skip_paused=True, df=True)
                # len==1 ⇒ 只有昨日有日线 = 复牌首日
                if h is not None and len(h) == 1:
                    dropped.append(s)
                    continue
                keep.append(s)
            except Exception:
                keep.append(s)
        if dropped:
            log.info("🚫【v22.2·复牌禁买】剔除 %d 只（昨日=复牌首日）: %s"
                     % (len(dropped), '、'.join(dropped[:8])))
            return keep
        return list(stocks)
    except Exception as e:
        log.info("⚠️ 复牌过滤异常（放行）: %s" % str(e)[:60])
        return list(stocks)


# ==================== 卖出相关函数 ====================
def a5_open_sell(context):
    """【V6.2·A5 复装】09:30（回测=09:31 那根 bar）开盘未涨停 → 卖出自有持仓，回款当日可用于定盘买入。
    条件（对齐 V24.4 停用前的 A5 口径）：
      ① 非今日买入（T+1 不可卖）② 属策略自购名单 g.own_codes（SELL_ONLY_OWN，不碰手工持仓）
      ③ 不在 SELL_SKIP_CODES ④ 有可卖数量（幽灵持仓跳过）
      ⑤ 开盘价距涨停 > A5_MIN_GAP_TO_LIMIT（0.5%）才算"未涨停"；一字/秒板不卖
      ⑥ 位置：在本函数所在的 sell_only_930() 最前面 ⇒ 早于破板回落与方向分流；卖出后该票不再进分流。
    返回实际卖出只数。"""
    if SELL_930_A5_MODE != 'on':
        return 0
    _n = 0
    for stock in list(context.portfolio.positions.keys()):
        try:
            if stock in SELL_SKIP_CODES:
                continue
            if stock in getattr(g, 'bought_stocks', set()):        # 今日买入 → T+1 不可卖
                continue
            if stock not in getattr(g, 'own_codes', set()):        # 只卖策略自己买的票
                continue
            pos = context.portfolio.positions.get(stock)
            if pos is None or float(getattr(pos, 'total_amount', 0) or 0) <= 0:
                continue
            rt = _rt_of(stock, context)
            hl = float(rt.get('up') or 0)
            op = float(rt.get('open') or 0)
            if not (hl > 0 and op > 0):
                log.info("⚠️【A5·开盘先卖】%s 取不到涨停价/今开 → 本轮不卖" % stock)
                continue
            if abs(op - hl) / hl <= A5_MIN_GAP_TO_LIMIT:
                log.info("🔒【A5·开盘先卖】%s 开盘已涨停（今开%.3f vs 涨停%.3f）→ 不卖" % (stock, op, hl))
                continue
            if execute_sell(stock, context):
                _n += 1
            else:
                log.info("⚠️【A5·开盘先卖】%s 卖出未生成（可能已报过卖单/无持仓）" % stock)
        except Exception as _e:
            log.info("⚠️【A5·开盘先卖】%s 异常：%s" % (stock, str(_e)[:50]))
    log.info("🧨【A5·开盘先卖】卖出 %d 只 | 卖后可用资金 %.2f（当日可用于定盘买入）"
             % (_n, context.portfolio.available_cash))
    return _n


def sell_only_930(context):
    log.info("=== 9:30 专属卖出开始 ===")
    # 【V6.2·A5 复装】开盘未涨停的自有持仓先卖 → 回款当日用于定盘买入（"先卖后买"的资金来源）
    try:
        a5_open_sell(context)
    except Exception as _e:
        log.info("⚠️【A5·开盘先卖】异常（已忽略，不影响后续）：%s" % str(_e)[:60])
    # 破板回落（09:30 版，受统一裁决约束）
    check_break_limit_drop(context)
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        # 【v17.6】幽灵持仓（amount=0）跳过
        try:
            pos = context.portfolio.positions.get(stock)
            if pos is None or float(getattr(pos, 'total_amount', 0) or 0) <= 0:
                log.info("👻 跳过幽灵持仓（amount=0，无需卖出）: %s" % stock)
                continue
        except Exception:
            pass
        try:
            rt = _rt_of(stock, context)
            hl = rt['up']
            op = rt['open']
            if hl > 0 and op > 0 and abs(op - hl) / hl > 0.005:
                # 【v20.2】方向分流：自有持仓先不卖，等 09:30:03 起按"开盘方向"分流
                if v20_dir_should_defer(context, stock, rt):
                    continue
                # 【V6.2】A5 打开时，这类票在本函数开头就已卖掉；走到这里说明被 A5 跳过
                #   （开盘涨停 / 取不到价 / 非自有 / 幽灵持仓）→ 一律延后交方向分流处理。
                log.info("⏭【V6.2】9:30 开盘未涨停但未卖（A5=%s）：%s —— 交方向分流"
                         % (SELL_930_A5_MODE, stock))
        except Exception:
            continue
    sell_decision(context)
    log.info(f"卖出后可用资金：{context.portfolio.available_cash:.2f}")

def check_break_limit_drop_for_long_hold(context):
    for stock in list(context.portfolio.positions.keys()):
        hold_days = g.hold_days.get(stock, 0)
        if hold_days <= 1:
            continue
        try:
            rt = _rt_of(stock, context)
            last = rt['last']
            today_high = rt['high']
            high_limit = rt['up']
            if high_limit > 0 and today_high >= high_limit * 0.995:
                g.has_limit_up.add(stock)
            # 【v24.4】last<=0（停牌/快照缺失）时 drop_ratio 恒=100% ⇒ 必须守卫，防误卖
            if stock in g.has_limit_up and today_high > 0 and last > 0:
                drop_ratio = (today_high - last) / today_high * 100
                if drop_ratio >= g.break_drop_ratio:
                    # 【v23.3·F3】统一裁决补全：炸板尺判"不卖" ⇒ 抑制 破板回落（2 分钟版）
                    if not v232_gate_any(context, stock, '2分钟破板回落'):
                        continue
                    execute_sell(stock, context)
                    if stock not in g.break_limit_sold_stocks:
                        g.break_limit_sold_stocks.append(stock)
        except Exception:
            continue

def tick_break_monitor(context):
    """【V4.0】破板回落监控（tick/秒级）——
    与 09:30 的 check_break_limit_drop() **同一套判据**（触板 = 当日最高 ≥ 涨停价×99.5%；
    自当日最高回落 ≥ break_drop_ratio%），区别只有频率与"确认窗口"：
      · tick 频率回测：逐 tick 检查（≈实盘 3 秒级）；分钟频率回测：每分钟一次；
      · TICK_BREAK_CONFIRM_SEC = 15：回落要**持续 15 秒**仍低于阈值才卖，防"插针"被洗出去
        （分钟频率下等价于"下一根分钟仍跌破"，比实盘更保守）。
    当日买入的票（g.bought_stocks）不卖（T+1）；SELL_SKIP_CODES 名单不碰。
    """
    try:
        if not bool(STRATEGY_PARAMS.get('tick_break_monitor', True)):
            return
        cd = get_current_data()
        now = context.current_dt
        sec_now = now.hour * 3600 + now.minute * 60 + now.second
        if not hasattr(g, '_tick_break_since'):
            g._tick_break_since = {}
        if not hasattr(g, '_sold_watch'):
            g._sold_watch = []
        _cf = int(STRATEGY_PARAMS.get('tick_break_confirm_sec', 15) or 0)
        # 卖出后 60 秒回看（校准"确认秒数该不该改"）
        try:
            _keep = []
            for _it in g._sold_watch:
                if sec_now - int(_it.get('sec', 0)) >= 60:
                    _px = 0.0
                    try:
                        _px = float(cd[_it['stock']].last_price or 0)
                    except Exception:
                        _px = 0.0
                    if _px > 0:
                        log.info("🔍 破板卖出回看: %s 卖出%.3f → 60秒后%.3f (%+.2f%%)"
                                 % (_it['stock'], _it['px'], _px,
                                    (_px / _it['px'] - 1) * 100 if _it['px'] else 0.0))
                else:
                    _keep.append(_it)
            g._sold_watch = _keep
        except Exception:
            pass
        for stock in list(context.portfolio.positions.keys()):
            if stock in g.bought_stocks or stock in (SELL_SKIP_CODES or []):
                g._tick_break_since.pop(stock, None)
                continue
            try:
                d = cd[stock]
                if d is None:
                    continue
                last = float(d.last_price or 0)
                hi = float(d.high or 0)
                hl = float(d.high_limit or 0)
                if hl > 0 and hi >= hl * 0.995:
                    g.has_limit_up.add(stock)
                if stock not in g.has_limit_up or hi <= 0 or last <= 0:
                    g._tick_break_since.pop(stock, None)
                    continue
                drop = (hi - last) / hi * 100
                if drop < float(g.break_drop_ratio):
                    if g._tick_break_since.pop(stock, None) is not None:
                        log.info("↩️ 破板回落·撤销: %s | 回落已回到 %.2f%%(<阈值%.1f%%) 现价%.2f"
                                 % (stock, drop, float(g.break_drop_ratio), last))
                    continue
                if _cf > 0:
                    _since = g._tick_break_since.get(stock)
                    if _since is None:
                        g._tick_break_since[stock] = sec_now
                        log.info("⏳ 破板回落·待确认: %s | 现价%.2f 自当日最高%.2f 回落%.2f%%(阈值%.1f%%)"
                                 " → 持续 %d 秒仍低于阈值才卖"
                                 % (stock, last, hi, drop, float(g.break_drop_ratio), _cf))
                        continue
                    if sec_now - _since < _cf:
                        continue
                # 【V5.0·v23.2】统一裁决（破板回落路）：炸板尺/均线尺判"不卖" ⇒ 本格不卖
                try:
                    _d0 = cd[stock]
                    if not v232_gate(context, stock, float(_d0.day_open or 0), last, hi, 0.0,
                                     _wavg_of(stock, context), hl, float(_d0.low_limit or 0)):
                        continue
                except Exception:
                    pass
                log.info("📤 破板回落卖出(秒级): %s | 当日最高%.2f 现价%.2f 回落%.2f%%(阈值%.1f%%)"
                         % (stock, hi, last, drop, float(g.break_drop_ratio)))
                if execute_sell(stock, context):
                    g._tick_break_since.pop(stock, None)
                    try:
                        g._sold_watch.append({'stock': stock, 'px': last, 'sec': sec_now})
                    except Exception:
                        pass
            except Exception as _e1:
                continue
    except Exception as e:
        log.info("⚠️ tick_break_monitor 异常: %s" % str(e)[:80])


def check_break_limit_drop(context):
    """破板回落检查：今日触板后从高点回落≥阈值 立即卖（仅非当日买入持仓；受统一裁决约束）"""
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        try:
            rt = _rt_of(stock, context)
            last = rt['last']
            today_high = rt['high']
            high_limit = rt['up']
            if high_limit > 0 and today_high >= high_limit * 0.995:
                g.has_limit_up.add(stock)
            # 【v24.4】last<=0（停牌/快照缺失）时 drop_ratio 恒=100% ⇒ 必须守卫，防误卖
            if stock in g.has_limit_up and today_high > 0 and last > 0:
                drop_ratio = (today_high - last) / today_high * 100
                if drop_ratio >= g.break_drop_ratio:
                    # 【v23.3·F3】统一裁决补全：炸板尺判"不卖" ⇒ 抑制 破板回落（09:30 版）
                    if not v232_gate_any(context, stock, '破板回落(09:30)'):
                        continue
                    execute_sell(stock, context)
                    if stock not in g.break_limit_sold_stocks:
                        g.break_limit_sold_stocks.append(stock)
        except Exception:
            continue

def sell_decision(context):
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        if should_sell(stock, context):
            execute_sell(stock, context)

def should_sell(stock, context):
    """【V5.0】A1 止损 / A2 止盈 / A3 超期 / A4 放量下跌 已整段删除（对齐 V25/V24.9，
    依据 9,273 笔样本：无 A 类口径均值 +0.176% vs 有 A 类 −0.093%，A1 触发样本胜率 0%）。
    出场现由 B 类（破位/冲高回落/未触发兜底/炸板尺/均线尺）+ A6 11:30 兜底 负责（见 v20_engine）。"""
    try:
        pos = context.portfolio.positions.get(stock)
        if pos is None:
            return True
        if getattr(pos, 'avg_cost', 0) <= 0:
            return True
        last = _last_px(stock)
        # 【v24.7】行情断/无价 ⇒ 不再判卖（原 return True 会触发无价清仓）
        if last <= 0:
            return False
        return False
    except Exception:
        return True

def execute_sell(stock, context):
    # 【V2.0】同一票当日只报一次卖单（对齐 V16 v10：原来 sell_only_930 与 market_open 都会报，导致重复卖）
    if stock in getattr(g, 'sell_requested', set()):
        log.info("↻ 已报过卖单，跳过重复卖出: %s" % stock)
        return False
    # 【回测版】只卖"策略自己买入的票"（保护账户里的手工持仓）
    if SELL_ONLY_OWN and stock not in SELL_SKIP_CODES and \
            stock not in getattr(g, 'own_codes', set()):
        if not getattr(g, 'own_skip_logged', False):
            g.own_skip_logged = True
            try:
                nm = get_security_info(stock).display_name
            except Exception:
                nm = stock
            log.info("🛡 跳过卖出（不是策略买的，不碰你的持仓）: %s %s" % (stock, nm))
        return False
    try:
        for od in get_open_orders():
            if od.security == stock and od.status == OrderStatus.NOT_FILLED:
                cancel_order(od.order_id)
    except:
        pass
    try:
        # 【V3.2】卖出参考价改用快照现价 —— 原来读"当日收盘"→ 回测卖出价≈收盘价、收益虚高
        current_price = _last_px(stock)
        if current_price <= 0:
            return False
        pos = context.portfolio.positions.get(stock)
        if pos is None:
            return False
        avg_cost = pos.avg_cost
        hold_days = g.hold_days.get(stock, 0) + 1
        profit_ratio = (current_price - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
        stock_name = get_security_info(stock).display_name
        order_target(stock, 0)
        try:
            push_signal('SELL', stock, int(pos.total_amount), current_price, 'market', '卖出')
        except Exception:
            pass
        try:
            g.sell_requested.add(stock)          # 【V2.0】记下已报卖单
        except Exception:
            pass
        g.sold_today.append({
            'code': stock,
            'name': stock_name,
            'cost': avg_cost,
            'sell_price': current_price,
            'profit_ratio': profit_ratio,
            'hold_days': hold_days,
            'sell_time': context.current_dt.strftime('%H:%M:%S')
        })
        log.info(f"📤 卖出成功: {stock} {stock_name} @ {current_price:.3f} 收益:{profit_ratio:.2f}%")
        if stock in g.hold_days:
            del g.hold_days[stock]
        if stock not in g.rebuy_candidates:
            g.rebuy_candidates.append(stock)
        return True
    except Exception as e:
        log.error(f"❌ 卖出失败{stock}: {str(e)[:30]}")
        return False

def market_open(context):
    if not g.only_buy:
        check_break_limit_drop(context)
        # 【V5.0】A5「开盘未涨停卖」已停用（v24.7）—— 原循环整段删除，交方向分流
        sell_decision(context)
    buy_decision(context)
    update_hold_status(context)

def update_hold_status(context):
    for stock in context.portfolio.positions:
        try:
            current_data = get_current_data()[stock]
            if current_data is None:
                continue
            high = current_data.high
            high_limit = current_data.high_limit
            if high >= high_limit * 0.995 and stock not in g.has_limit_up:
                g.has_limit_up.add(stock)
                stock_name = get_security_info(stock).display_name
                log.info("✅ 标记涨停: {} {}".format(stock, stock_name))
        except:
            continue

def after_market_close(context):
    log.info("="*50)
    trade_days = get_trade_days(end_date=context.current_dt.date(), count=2)
    if len(trade_days) >= 2:
        today = trade_days[0]
    else:
        today = context.current_dt.date() - datetime.timedelta(days=1)
    log.info("收盘总结: {}".format(today))
    for stock in context.portfolio.positions:
        if stock not in g.bought_stocks:
            g.hold_days[stock] = g.hold_days.get(stock, 0) + 1
    if len(g.sold_today) > 0:
        log.info(f"📤 今日卖出：{len(g.sold_today)}只")
        for sell in g.sold_today:
            log.info(f"  {sell['code']} {sell['name']} | 成本:{sell['cost']:.3f} | 卖出:{sell['sell_price']:.3f} | 收益:{sell['profit_ratio']:.2f}% | 持有{sell['hold_days']}天")
    hold_stocks = list(context.portfolio.positions.keys())
    log.info(f"📈 最终持仓：{len(hold_stocks)}只")
    for stock in hold_stocks:
        try:
            pos = context.portfolio.positions[stock]
            stock_name = get_security_info(stock).display_name
            profit_ratio = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else 0
            days = g.hold_days.get(stock, 0)
            flag = "✅" if stock in g.has_limit_up else "❌"
            log.info(f"  {stock} {stock_name} | 成本:{pos.avg_cost:.3f} | 当前:{pos.price:.3f} | 收益:{profit_ratio:.2f}% | 持有{days}天 | 涨停:{flag}")
        except:
            log.info(f"  {stock} | 持仓信息获取失败")
    total_asset = context.portfolio.total_value
    cash = context.portfolio.available_cash
    log.info(f"💵 总资产：{total_asset:.2f} | 可用资金：{cash:.2f}")
    # 【V2.3】委托未成交核对（区分"没下单"与"下了单没成交"）
    try:
        _pending_left = [s for s in getattr(g, 'order_pending', set())
                         if s not in context.portfolio.positions]
        if _pending_left:
            log.info("⚠️ 已报单但未成交: %s（共%d只）—— 说明是撮合/限价问题，不是选股问题"
                     % (', '.join(_pending_left[:5]), len(_pending_left)))
        else:
            log.info("✅ 今日报单全部成交（或今日未报单）")
    except Exception:
        pass
    # 【V2.1】当日诊断：回测里最常问的"为什么没交易"一看就知道卡在哪一步
    log.info("🔍 当日诊断: 竞价过滤=%s | 候选池=%d只 | 可买池=%d只 | 今日买入=%d只 | 今日卖出=%d只"
             % ('已跑' if getattr(g, 'filter_done', False) else '未跑',
                len(g.candidate_stocks), len(g.rebuy_candidates),
                g.bought_today_count, len(g.sold_today)))
    # 【回测版】竞价增强当日对照（供回测日志统计"过闸 vs 被闸"）
    _rec = getattr(g, 'auction_gate_today', []) or []
    if _rec:
        _pass = [r for r in _rec if r['ok']]
        _fail = [r for r in _rec if not r['ok']]
        log.info("🧪 竞价增强[%s] 收盘对照: 判定%d只 | 过①②④ %d只 | 被闸 %d只 | ★★★ %d只"
                 % (AUCTION_GATE_MODE, len(_rec), len(_pass), len(_fail),
                    len([r for r in _rec if r['stars'] >= 3])))
        _bought = [s for s in g.bought_stocks]
        log.info("   今日买入: %s | 其中过闸: %d/%d"
                 % (','.join(_bought) or '无',
                    len([s for s in _bought if any(r['code'] == s and r['ok'] for r in _rec)]),
                    len(_bought)))
    log.info("="*50)