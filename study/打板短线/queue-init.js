// Seeds study/打板短线/queue.json for the epoch-6 round. Idempotent: skips ids already present.
//   node -e "require('./study/打板短线/queue-init.js')"
// Grounding: the 2026-08 study (baseline / q-1..q-5, epoch 2, 2022 sub-window) and the two
// zero-cost epoch-6 findings recorded first (e6-ledger-audit, e6-dup). The pre-wipe family page's
// §4.6 handoff list (git a6195c6) is the source of u-rzq-deconf / u-barprice / u-2023.
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.load(F).map(e => e.id));
const ideas = [
  {
    id: 'baseline-e6', kind: 'understand', rank: 1, from: ['baseline', 'q-3', 'e6-ledger-audit'], edgeRef: null,
    title: '基类 439385b4 在 epoch 6 上的锚点（ledger 在任何 epoch 都没有它的行；2026-08 的 6 条 finding 全在 pin 之前）',
    hypothesis: '源码不调 set_slippage / set_commission / set_order_cost，已设 avoid_future_data；唯一可能绑定的 pin 是 order_volume_ratio=0.05——¥1M 按当日候选数等分、标的前日成交额 ≥¥5.5e8/¥3e8，预期不绑定。预期 total 424.33 / annual 129.24 / sharpe 2.58 / maxDD 32.56 复现（容差 0.5pp，含已知 ~0.15pp 重跑漂移），obj 0.9668，在 1.5 闸门下 PASS。证伪：任一指标偏离 >0.5pp（则成交量上限在打板成交上绑定，q-1..q-5 变成跨 epoch 读数）；或 no-trades',
    why: '家族在 epoch 6 上 0 过闸、且账本里唯一「过闸」的历史行属于一个从未被本 epoch 量过的基类；每个后续 Δ 都对它量。复现则 6 条 epoch-2 finding 直接升为同台读数，不必重跑（≈16 JQ 分钟/次）',
    design: 'study/打板短线/baseline-e6.py = py2to3(源码) + live OVERRIDE（build-e6.js）；--window train --max-poll-min 50',
  },
  {
    id: 'u-2023', kind: 'understand', rank: 2, from: ['q-3', 'baseline-e6'], edgeRef: '涨停动量延续',
    title: '2023 单年子窗：q-3 只用总回报反解出 2023 ≈ −3.35%，sharpe / maxDD / win_ratio / avg_position_days 全部未知——边缘为什么在第二年消失',
    hypothesis: '2023 total 在 −3.35% ± 3pp 内复现算术反解；stats 的 avg_position_days 与 2022 的 1.51 天相近（机器仍在转，只是接力不再赚），而 win_ratio 明显低于 69.87%。证伪：2023 total > +10%（反解错误，需重查 baseline-e6 的两年拆分）；或 avg_position_days ≫ 1.51（2023 是被套牢而不是接力失效）',
    why: '「整段业绩只属于 2022」是这个家族最重要、也最未被解释的事实；2023 的机理指标决定 improve 该往 regime 门控（imp-3）还是往腿的取舍（imp-1）走。≈8 JQ 分钟',
    design: '不造 variant：baseline-e6.py --start 2023-01-01 --end 2023-12-31（run.js 的 argv[4]/[5]）；结果记为信息性单年读数，不与 TRAIN objective 并列',
  },
  {
    id: 'u-nolimit', kind: 'understand', rank: 3, from: ['q-4', 'q-3'], edgeRef: '涨停动量延续',
    title: 'edge 的对照：把「昨日首板」候选池换成「昨日涨 7%–9.9% 但未触及涨停」的同规则票——收益是涨停事件本身，还是那套过滤',
    hypothesis: '若 涨停动量延续 是来源，对照本的 annual 应 < 基类的一半（同 TRAIN 或同 2022 子窗）；若对照本 ≥ 基类的一半，边缘不在涨停事件而在成交额 / 市值 / 竞价量比 / 左压那套筛子，edge 改判 refuted 并转 proposed 的新名字。两条腿都要换：hl_list → 未触板的强势票，hl_list2（曾涨停未封）→ 最高价达 +7% 但收盘低于 +7% 的票',
    why: '现有 edge 的 evidence（q-4：三池不等权）只回答「哪条腿」，不回答「是否因为涨停」；这是唯一直接证伪 edge 名字的实验',
    design: 'variants/u-nolimit.py：get_hl_stock / get_ever_hl_stock2 各加一个 near-miss 版本（close/pre_close ≥1.07 且 close<high_limit；high/pre_close ≥1.07 且 close/pre_close <1.07），prepare_stock_list 改调它们；其余过滤一行不动。先跑 2022 子窗对照 q-3 锚点（≈8 分钟）',
  },
  {
    id: 'u-rzq-deconf', kind: 'understand', rank: 4, from: ['q-4'], edgeRef: '涨停动量延续',
    title: 'q-4 的去混淆重跑：弱转强腿保留在第 46 行的计数里、只在下单循环里跳过——把「少一条腿」与「单票仓位变大」拆开',
    hypothesis: '若该腿的独立贡献仍 ≥ 终值的三分之一（q-4 合成读数是 48%），「肥右尾在弱转强腿」成立且可作为 imp-1 的前提；证伪：独立贡献 < 15% 终值（q-4 的量级主要是集中度效应）',
    why: 'imp-1（只跑弱转强腿）的全部依据是 q-4，而 q-4 打包了两件事；不拆开就做 improve 会把集中度当成 alpha',
    design: 'variants/u-rzq-deconf.py（build-e6.js：g.rzq_skip + 循环内 continue，两处一个概念）；--window train（≈16 分钟）或 2022 子窗（≈8 分钟）对照',
  },
  {
    id: 'u-barprice', kind: 'understand', rank: 5, from: ['q-1'], edgeRef: null,
    title: '日线台究竟按哪根 bar 价成交：把第 50 行改成荒谬的 MarketOrderStyle(0.01)',
    hypothesis: '仍与锚点逐位相同 ⇒ 价格参数被丢弃，成交价 = JQ 日线模式规则（开盘价），q-1 的「execution-fiction」应改写为「显式参数冗余、成交在开盘价」；成交全部落空 / 异常 ⇒ 参数其实被读取，q-1 需重新解释。仓库级结论',
    why: 'q-1 只证明了「忽略」，没有定位价位；本家族全部业绩建立在什么价位上仍未写定。⚠ 实际上 09:26 竞价价 ≈ 开盘价，所以「按开盘价成交」并非虚构——这正是要用探针钉死的',
    design: '复制 baseline-e6.py，仅第 50 行 MarketOrderStyle(current_data[s].day_open) → MarketOrderStyle(0.01)；2022 子窗对照 q-3 锚点（≈8 分钟）',
  },
  {
    id: 'dbdx-imp-1', kind: 'improve', rank: 6, from: ['q-4', 'u-rzq-deconf'], edgeRef: '涨停动量延续',
    title: '只跑弱转强腿：qualified_stocks = rzq_stocks',
    hypothesis: 'q-4：该腿 ~17% 笔数、~一半终值；若它独立承重（u-rzq-deconf），单腿书应 obj ≥ 基类且两年同号不差于基类（2023 不得比基类的 2023 更差）。证伪：obj < 基类，或 2023 更差——那 q-4 的一半终值是集中度而非腿的 alpha',
    why: 'edge 的先验指向这条腿；这是唯一 on-mechanism 的选腿 improve。排在 u-rzq-deconf 之后',
    design: 'enhance/candidates/dbdx-imp-1.py（build-e6.js，一行）；--window train，逐年拆分',
  },
  {
    id: 'dbdx-imp-2', kind: 'improve', rank: 7, from: ['q-2'], edgeRef: '涨停动量延续',
    title: '把资金周转推到极限：次日无条件卖出（T+1 强制离场），去掉 MA5 与「浮盈即止盈」两条件',
    hypothesis: 'q-2：MA5 止损首先是资金周转引擎（1.51 天/轮），不是回撤压制器。若接力边缘只在隔夜一跳，强制 T+1 离场应 annual ≥ 基类且 maxDD 更浅；证伪：annual 掉 >30%（持有到第 2–3 天的那部分收益是承重的）',
    why: '直接检验 edge 的时间尺度（隔夜 vs 数日），同时是最简单的规则，减少一整套手调条件',
    design: 'variants：sell() 改为对所有持仓 order_target_value(s, 0)（保留 closeable_amount 检查）；--window train',
  },
  {
    id: 'dbdx-imp-3', kind: 'improve', rank: 8, from: ['q-3', 'u-2023'], edgeRef: '涨停动量延续',
    title: '情绪门控：昨日涨停家数（或首板池大小）低于阈值时不开新仓',
    hypothesis: '2022 +442% / 2023 ≈ −3%（q-3）说明边缘依赖打板情绪 regime；用 len(hl_list) 的 20 日均值做门控，若 2023 抬到 ≥0 而 2022 保留 ≥70% 的 annual，则门控是 on-mechanism 的改进；证伪：2022 损失 >30% 或 2023 仍为负',
    why: '唯一直接针对「第二年消失」的 improve；依赖 u-2023 的机理读数决定阈值形式，故排最后',
    design: '等 u-2023 落定再写 variant；阈值只取一个先验值（不扫），逐年拆分记账',
  },
];
let n = 0;
for (const i of ideas) if (!have.has(i.id)) { rq.add(F, i); n++; }
console.log(`queue-init: added ${n}, total ${rq.load(F).length}`);
