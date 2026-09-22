// Seeds study/趋势技术/queue.json for the epoch-6 round. Idempotent: skips ids already present.
//   node study/趋势技术/queue-init.js
const rq = require('../../utils/research-queue');
const F = '趋势技术';
const have = new Set(rq.load(F).map(e => e.id));
const ideas = [
  {
    id: 'e6-1', kind: 'understand', rank: 1, from: ['baseline', 'q-struct'], edgeRef: null,
    title: '去掉 08:00 的未来函数后，基类在 epoch 6 上还剩什么（清洁锚点）',
    hypothesis: 'epoch-2 的 sharpe 1.94 / annual 41.96 主要来自 08:00 读到当日收盘（RPS、MA20）与当日开盘（池过滤）；清洁书年化 < epoch-2 的一半且过不了 1.5 闸门。证伪：清洁书 sharpe ≥ 1.5 且年化 ≥ 30%',
    why: 'epoch-6 归一化对基类返回 no-trades，而 avoid_future_data=True 是唯一能清空一本书的 pin；q-struct 早已点名 get_price end_date=today 与 08:00 的 day_open>0。没有这个数字，家族没有 epoch-6 基线，任何 understand/improve 都无处比较',
    design: 'variants/e6-1_clean.py：4 处改动一个概念——check_market_trend / get_batch_close_prices / calculate_single_rps 的 end_date 改 context.previous_date，池过滤删 day_open>0；09:30 执行路径不动',
  },
  {
    id: 'u-2', kind: 'understand', rank: 2, from: ['q-lineage'], edgeRef: '趋势择时',
    title: '清洁书上关掉大盘 MA20 闸门（edge 趋势择时 的 test；q-lineage 排队最高的受控消融）',
    hypothesis: '闸门在 2022 熊市里是收益来源：关掉后年化下降 ≥10pp 或 maxDD 上升 ≥5pp。证伪：关掉后 objective ≥ 清洁基类',
    why: '子代 33b1b1e3 相对祖先 995abb4d 记录的唯一增量就是「+大盘趋势控制」，但那是两份文件的归档行对比（未受控）；在同一本清洁书上关掉才是干净的读数',
    design: 'variants/u-2_clean-no-gate.py：e6-1 + g.market_trend_bull = True',
  },
  {
    id: 'u-3', kind: 'understand', rank: 3, from: ['q-1', 'q-struct'], edgeRef: '动量',
    title: '清洁书上把 RPS 入场/出场带镜像到弱端（edge 动量 的 test）',
    hypothesis: '横截面 20 日相对强度在沪深300 内有延续：镜像书（日 8–15 / 周 <20 / 月 <25，出场 <4 或 >20）年化 < 清洁基类的 75%。证伪：镜像书年化 ≥ 清洁基类的 75%',
    why: 'q-1 已测排序方向几乎惰性（−4pp），说明选择由 RPS 带定义；带本身是否携带信息从未测过。因子看板的先验：动量类因子扣成本后全部深负',
    design: 'variants/u-3_clean-mirror.py：e6-1 + 6 个阈值常量镜像 + 周/月比较符翻转',
  },
  {
    id: 'u-4', kind: 'understand', rank: 4, from: ['q-struct'], edgeRef: '动量',
    title: '清洁书上去掉周/月 RPS 确认（多周期是过滤还是装饰）',
    hypothesis: '周/月确认把候选池收窄到「多周期同强」的票，去掉后池子变大、笔数上升、年化下降。证伪：去掉后 objective 在清洁基类 ±0.03 内',
    why: '基类命名为「多周期」，但 q-struct 只审计了结构，没有量化周/月两道阈值各自的贡献',
    design: 'variants/u-4_clean-day-only.py：e6-1 + 周/月条件恒真',
  },
  {
    id: 'u-5', kind: 'understand', rank: 5, from: ['u-2'], edgeRef: '趋势择时',
    title: '控制组：同一 MA20 闸门只开在沪深300 ETF（510300）上——选股腿是否多余',
    hypothesis: 'u-2 显示 RPS 腿自身比指数差 11pp；若指数择时器 objective ≥ 清洁书（−0.1636），选股腿净为负，家族退化为 MA20 指数择时器。证伪：择时器 objective < 清洁书 −0.05',
    why: 'u-2 把家族唯一的收益部件指向闸门，但闸门在原文里只挡入场、不清仓；一个显式的指数择时器是「这本书的全部价值就是 MA20 开关」的直接检验',
    design: 'variants/u-5_clean-index-timer.py：e6-1 + buy_list 换成 510300 + 收盘 ≤ MA20 时清仓（两处一个概念）；基金费用由 OVERRIDE 钉死',
  },
  {
    id: 'qsjs-imp-1', kind: 'improve', rank: 6, from: ['u-2', 'e6-1'], edgeRef: '趋势择时',
    title: '闸门同时作为出场：沪深300 收盘 ≤ MA20 时清仓（清洁 RPS 书上）',
    hypothesis: 'u-2 说闸门是唯一挣钱的部件，而原文只让它挡入场、持仓要等 RPS 退出；把它变成出场应压 maxDD（20.03）并抬 objective ≥ +0.05。证伪：objective ≤ 清洁书',
    why: 'on-mechanism：作用在已 measured 的 趋势择时 上；不碰负 alpha 的选股腿（u-2/u-3 已关闭那条方向）',
    design: 'enhance/candidates/qsjs-imp-1.py：e6-1 + market_open 里一段「非多头则 order_target 0」（与 u-5 的出场块相同，但买的仍是 RPS 股票）',
  },
  {
    id: 'u-6', kind: 'understand', rank: 7, from: ['u-4', 'u-3'], edgeRef: '动量',
    title: '有周/月确认时，20 日带的紧度还重要吗（日带下沿 85→50、出场下限 80→50 同动）',
    hypothesis: 'u-4 说周/月确认值 31pp；若 20 日带只是装饰，放宽后 objective 在清洁书 ±0.05 内（edge = 长周期动量）；若 20 日强度也承重，放宽后年化下降 ≥10pp',
    why: 'u-3 镜像同时翻了三个周期，u-4 只去了长周期——20 日带自身的贡献两者都没单独分出来；这决定 动量 edge 的描述是「12 个月动量」还是「多周期共振」',
    design: 'variants/u-6_clean-loose-day-band.py：e6-1 + day_rps_low 85→50 + sell_rps_low 80→50（出场下限必须低于入场下沿，否则新仓次日即卖）',
  },
  {
    id: 'e6-1a', kind: 'understand', rank: 9, from: ['baseline'], edgeRef: null,
    title: '平台语义探针：只删 08:00 的 day_open 池过滤，get_price end_date=today 保留',
    hypothesis: '若 avoid_future_data 把 end_date=today 的 get_price 截断到昨日，则本变体 == e6-1（no-trades 的唯一成因是 day_open 过滤）；若它抛异常，则再次 no-trades',
    why: '两种平台语义下 e6-1 都是正确的清洁书，所以这个探针只值一个「哪一行清空了书」的答案；排最后，预算有余才跑',
    design: 'variants/e6-1a_pool-only.py：只删 day_open>0 一行',
  },
];
let n = 0;
for (const i of ideas) if (!have.has(i.id)) { rq.add(F, i); n++; }
console.log(`queue-init: added ${n}, total ${rq.load(F).length}`);
