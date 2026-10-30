// Step-0 (new-members) finding for the 2026-10-30 re-invocation. Zero cost. Idempotent by qId.
//   node -e "require('./study/打板短线/record-nm6.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-10-30', type: 'probe',
  component_or_param: '新成员 e1053979 年化68.63%，回撤16.82连板策略（git 7fc2c3c：b518f737 连板龙头 代码体的 V5.8，加竞价量比过滤 5%–12%、市场情绪门控、热门概念；09:2x 竞价入场、MarketOrderStyle(day_open)）。epoch 9：obj −0.0844 / annual 32.20 / sharpe 0.56 / maxDD 40.64，DQ；769 行，活跃日 151/241',
  metric_delta: '2024 曲线逐半年（零成本）：H1 −39.0（maxDD 39.0）/ H2 +116.7（25.3）；逐季 −28.0 / −15.2 / +37.1 / +58.0。对照同窗：基类 +933 / −13、竞价擒龙 +876 / −5、低开腿 +136 / +0.5、弱转强单独 29048a4f −13 / +138',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9 归一化行与曲线切片）',
  finding: '连板（二板及以上接力）书在 2024 的形状与基类血统（首板）相反：上半年亏 39%、下半年赚 117%，与弱转强单独成书（29048a4f）同向。所以「上半年肥尾、下半年退潮」不是涨停事件本身的性质，而是**首板高开 / 低开**这两条腿的性质；二板以上与弱转强在 2024 下半年赚钱、上半年亏钱。基类自己的弱转强腿例外（u-e9-rzq：在基类的仓位与过滤下它仍是 H1 肥尾 + H2 亏损）——即「哪条腿在哪半年赚」取决于那本书的过滤与仓位，不能从腿的名字推出。本书 DQ（sharpe 0.56、回撤 41%），不改变家族任何结论；与 b518f737（epoch 6 DQ）同一血统',
  confidence: 'med（形状读数直接；跨书推断只到方向）',
  flags: 'zero-cost · step-0-exit · 连板-lineage（b518f737）· opposite-half-year-shape · DQ · R1-family',
  description: '数据：harness/normalize-train.tsv e9 行；data/series/<slug>__train__e9.json 切片；源码 grep（get_continue_count_df / compute_market_emotion / sell_check_open）；git show 7fc2c3c',
  implication: '关闭对 e1053979 的单独研究：DQ、同血统、家族 R=1 终局拒绝（valReopened: 9 但先前 basis 仍绑定，不花 VAL）。把 edge 块 regime 注记的措辞收窄为「首板高开 / 低开腿的上半年肥尾」而不是「涨停事件的上半年肥尾」——这在 §4 记为措辞修正，不改 status（涨停动量延续 仍 measured：来源是涨停事件，u-nolimit；季节形状属于腿）。不打开实验：要在同台上证明「二板以上 = 下半年腿」需要在基类里加一条二板腿，那是新书不是消融，且产出无处可去',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
