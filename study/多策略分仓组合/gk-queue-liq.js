// gatekeeper 2026-10-31: adds liq-1 / liq-2 / u-6 to queue.json and re-ranks the open entries.
// One-shot; refuses to run twice (throws on a duplicate id).
// Usage (repo root): node -e "require('./study/多策略分仓组合/gk-queue-liq.js')"
const fs=require('fs');const path=require('path');const P=path.join(__dirname,'queue.json');
const q=JSON.parse(fs.readFileSync(P,'utf8'));
const LIMIT="⚠ 本测量回答不了的事（必须写进结论，不得省略）：地板是按**日线**成交额算的，而腿 B 在 **09:30:05** 用市价单（order_value）买一只**前天涨停、昨天开板**的小盘股。order_volume_ratio 0.05 在本台上是对**当天整根日线**的量做的上限，不是对开盘 5 秒的量；成交价是 09:30:05 的 last_price（q-e9-bench-lastprice：get_current_data 给的是实时价），且台是零滑点。所以地板惰性只排除「全天量不够吸收这一笔」，**不排除**「开盘 5 秒内按这个价拿不到这一笔」——队列深度、开盘价差、竞价后第一笔的冲击都不在日线里。另外前一日（开板日）的成交额本身被涨停事件放大，地板对这类名字天然偏松。因此：liq-1 惰性 ⇒ 只证伪「量不够」意义上的 R=1，支持 R≥2；**R=3 不能单靠 liq 挣得**（无论 liq-2 结果如何），需要一次开盘成交测试（例如把腿 B 入场推迟到 09:35/10:00 的执行延迟消融，或分钟级价差读取）——那是另一条条目，不在本条范围内。腿 B 本来就跳过 09:30:05 时 last_price==high_limit 的名字（L1081–1084），所以「一字板买不进」不是本书的问题，问题是开盘冲击成本";
const DESIGN=(K)=>"从 baseline.py（完整四腿，权重不动）出发，加一个 helper 和两处调用，用断言编辑构建（照 study/资产配置/build-u1-u3-liq1.js 的 edit() 写法：每处恰好 1 次匹配，否则抛错；新建 build-liq.js，K 作参数，一份脚本出 liq-1 / liq-2）。helper：liq_ok(leg, s, value) = 前一日成交额 attribute_history(s, 1, '1d', ['money'])（盘中调用时日线只到 previous_date，avoid_future_data 已 pin）≥ K × value / 0.05，K=" + K + "。⚠ 地板用**本笔订单的实际金额**动态计算，而不是写死 1.17e6：腿 B 原生总收益 150%，腿内现金复利，年末单笔约 ¥146k ⇒ 本身的可行性下限约 2.9e6，写死的常数会在下半年把地板低估到 1/2.5。名义参考值（开局）：腿 B / 腿 A 0.35e6/6 ≈ ¥58.3k ⇒ " + (K===1?'1.17e6':'1.17e7') + "；ETF2 整腿 1e5 ⇒ " + (K===1?'2e6':'2e7') + "；ETF3 整腿 2e5 ⇒ " + (K===1?'4e6':'4e7') + "；腿 A 的 511880 照样过地板（预期惰性）。调用点 (1) StrategyB.buy() 循环里、order_value 之前（L1094 前），不通过就 continue——与该循环已有的停牌/涨跌停跳过同一语义，空出的仓位今天不补；(2) BaseStrategy.order_target_value_ 的买入分支（value > 0）里、order_target_value 之前，不通过就 return None——覆盖腿 A、ETF2、ETF3。卖出不加地板（已有持仓总要能退出）。日志：每个买入批次一行 `LIQFLOOR <date> <leg> in=<n> out=<m> excluded=<codes|-> <code>=<prevmoney>/<floor> ...`（腿 B 每次 buy()、腿 A 每次 buy_security()、ETF 腿每笔），异常打 `LIQFLOOR ERROR` 并放行（响亮失败，不静默剔除）。" + (K===1?"另加一行只记录、不过滤的 `LIQAUCT <date> <code> auctmoney=<x> posvalue=<y>`：腿 B 的 filter_stocks_by_b_s 已经调 get_call_auction，从同一 df 取 money 列，记下每只买入名字的 09:25 竞价成交额与本笔金额之比——这是本台上离「开盘那一下的量」最近的读数，零额外回测，但它是读数不是测量，不改变 R。":"") + "断言：构建出的文件相对 baseline.py 只多出 helper + 两处调用" + (K===1?' + LIQAUCT 读数':'') + "。--window train。对照 = 已存 base 曲线 2026-07-18_多策略-题材概念-35ce65d2__train__e9。读法照 study/资产配置/liqfloor-read.js（分页读日志、按腿汇总 in/out、每名最低成交额与地板倍数、与对照的 max|Δcum|）；正则要加 leg 字段，所以复制一份到本目录改，不动 资产配置 的那份。报：每条腿的剔除次数与名字、最紧名字的成交额/地板倍数、整书账户级 sharpe/objective（整书不报腿原生值——NAV 约定只适用于单腿跑）";
const add=[
{id:'liq-1',kind:'understand',
 title:'可成交性：完整 base 书在自身仓位规模上加流动性地板（前一日成交额 ≥ 本笔金额 / 0.05），作用于腿 A、腿 B 和两条 ETF 腿的全部买入',
 hypothesis:'在本书自己的仓位规模上，日线可行性地板对整书不起作用。可证伪：任何一个买入批次出现 LIQFLOOR in≠out（有名字因前一日成交额 < 本笔金额/0.05 被跳过），或者曲线偏离对照（max|Δcum| > 0）⇒ 地板确实约束；若整书 sharpe 因此跌破 1.0 闸门 ⇒ R=1（量意义上不可成交）。先验：腿 B 买的是 399101 里刚涨停过的小盘，开板日成交额通常被放大，所以地板大概率惰性——但先验不能代替测量（大小盘轮动 惰性、ETF溢价 8.44→1.10、小市值 7/8 不可成交）',
 why:'排第一：exit gate 上 realizability 未设 ⇒ BLOCK，这是本族今天唯一能清掉的阻塞（VAL 本轮不花，§4 已定）。u-1 已把族的水平和可成交性都归到腿 B（56% 收益、原生 sharpe 4.925 ≈ base 4.96），所以必须在完整 base 书上测（R 描述 candidate=base 35ce65d2，不设 realizabilityScope），决定性的是腿 B 那一路的剔除数。成本：1 次回测，u-1b 实测 ~3 分钟墙钟、~1–2 预算分钟；地板只多一次 attribute_history/名。结果任一方向都有信息。'+LIMIT,
 design:DESIGN(1),
 from:['u-1 (family level and realizability = leg B; ~¥58k/position, 09:30:05 entry)','u-1b (734 transactions all 策略B, ~100% daily turnover, ~3 min wall)','wiki/families/多策略分仓组合 §4 [阻塞 exit gate] + [新，u-1] 腿 B 的 liq 测试还没有队列条目','study/资产配置 liq-1 (realizabilityBasis; build-u1-u3-liq1.js, liqfloor-read.js)','CLAUDE.md liq precedents (大小盘轮动 inert, b3751277 inert, ETF溢价 8.44→1.10)'],
 edgeRef:'分仓分散',rank:1,status:'active',
 note:'gatekeeper 2026-10-31：无重复——0 条 liq finding、binding closedDirections 1 条（非 realizability）、§2 无 liq 行。dispatch 本条。判读：(a) 全部 in==out 且 max|Δcum|=0 ⇒ 惰性，realizability 记 2，basis 必须照抄 ⚠ 限制（开盘 5 秒成交未测）；(b) 有剔除但整书 sharpe ≥ 1.0 ⇒ 记 2，成对引用 base 与地板后两个数；(c) 整书 sharpe < 1.0 ⇒ 记 1。不论结果，R=3 不由本条或 liq-2 授予'},
{id:'liq-2',kind:'understand',
 title:'可成交性容量：同 liq-1，地板放大到 10×（前一日成交额 ≥ 10 × 本笔金额 / 0.05，开局腿 B ≈ 1.17e7）',
 hypothesis:'本书在 10 倍资金（约 ¥1e7）下仍过 1.0 闸门。可证伪：10× 地板下整书 sharpe < 1.0，或腿 B 一路被剔除的买入批次过半（容量 < ¥1e7）。若 liq-1 已生效，本条的问题变成「容量曲线有多陡」',
 why:'容量曲线的第二个点（同 资产配置 liq-2、大小盘轮动 1e7/2e7 的读法）：区分未受损容量与过闸容量。1 次回测，~2 分钟。⚠ 它不能把 R 提到 3——上限由开盘成交的盲区决定，不由日线容量决定（liq-1 的 ⚠ 限制原样适用于本条）。价值是给 R=2 一个容量数字，并告诉后续 improve 轮这本书能放多大；若两档都惰性，说明腿 B 的名字日成交额普遍 > 3e7，这本身是关于 弱转强 候选池的事实（它不是微盘）',
 design:DESIGN(10),
 from:['liq-1','study/资产配置 liq-2 (4e7: 16/25 rebalances bound, sharpe 2.47→2.05)','大小盘轮动 liq capacity curve (2e6 inert / 1e7 pass / 2e7 fail)'],
 edgeRef:'分仓分散',rank:2,status:'blocked',
 note:'blocked-on liq-1（只为顺序：共用构建脚本，liq-1 先验证 helper 与日志格式、0 条 LIQFLOOR ERROR）。liq-1 answered 即解锁，不论方向；若 liq-1 整书已跌破 1.0（R=1），本条改 dropped，原因「1× 已不过闸，10× 无新信息」'},
{id:'u-6',kind:'understand',
 title:'规模因子 edge test（注册判据）：腿 A 单独，order_by(valuation.market_cap.asc()) → desc（L321），其余不动',
 hypothesis:'规模（取最小市值）是腿 A 熊市分支的收益来源。可证伪（家族页注册判据）：asc→desc 后腿 A 原生 sharpe 降幅 < 30%（Δ > −30%）⇒ 规模不是腿 A 的来源，规模因子 refuted；降幅 ≥ 30% ⇒ measured',
 why:'规模因子 唯一的注册判据，u-0 和 u-1a 两次写了「判据未跑、没有队列条目」——gatekeeper 补上。值一次回测：本族三条 edge 里唯一没有任何测量的一条，两个方向都改变 edge 状态（improve generator 靠它判 u-4/imp-1 一线是否 on-mechanism）；成本 ~2 分钟（腿 A 无 every_bar）。排在 u-5 之后：腿 A 只占 20.8% 收益，不是族的水平。排在 u-4 之前：u-4 测台上意外（缺 CSV 导致的 511880 回退），本条测作者写下的机制。⚠ 稀释（必须处理，否则判据偏向「不是来源」）：u-1a 里 18/18 牛市调仓日持 511880，desc 只影响 23 个熊市调仓日，那一半货基两次跑完全相同，整腿 sharpe 降幅被稀释。主读数 = 熊市分支持仓期内的腿 A 原生 sharpe（牛熊状态机 L277 不动，熊市日期集合两边相同，从日志取），整腿原生 sharpe 作次读数；两读数方向不一致时如实报，不择一',
 design:'从 u-1a 变体（A 0.35，其余 0）出发，加一条断言编辑：get_stock_list 内 L321 `.order_by(valuation.market_cap.asc())` → `.order_by(valuation.market_cap.desc())`，断言全文件恰好这一处变化（.limit(self.stock_num*3) 不动 ⇒ 过滤后池子最大的 18 只再截 6，同注册判据）。L277、L305 不动。--window train。对照 = u-1a 已存曲线 study_多策略分仓组合_variants_u-1a__train__e9。报：整腿原生 sharpe（w=0.35，NAV 约定同 u-1）、熊市分支期内原生 sharpe（先核对两次跑熊市调仓日集合一致）、desc 版选中名字的市值分位、核对牛市日仍落 511880（证明编辑没碰牛市路径）',
 from:['wiki/families/多策略分仓组合 edge[规模因子].test (registered: asc→desc, Δ > −30% ⇒ not the source)','u-0 (规模因子 status unchanged because its test has not run)','u-1a (18/18 bull days in 511880; 23 bear days on the market-cap-ascending pipeline; native 2.223)'],
 edgeRef:'规模因子',rank:4,status:'queued',
 note:'gatekeeper 2026-10-31 新增：判据已在家族页注册，无重复；无 stale closure 涉及 market_cap 方向。不依赖 u-4'},
];
for(const e of add){ if(q.find(x=>x.id===e.id)) throw new Error('dup '+e.id); q.push(e); }
const get=id=>q.find(x=>x.id===id);
const u5=get('u-5'); u5.rank=3;
u5.note+=' ‖ gatekeeper 2026-10-31 re-rank → 3（liq-1/liq-2 之后）：先清 exit gate 阻塞；本条是族水平来源（腿 B 56%）的机制测试，高于两条腿 A 测试。⚠ 预算：去掉 rzq_list 后 get_call_auction 每天跑在全部候选上，墙钟超 20 分钟先报 orchestrator；触 45 分钟帽先查 buildList 是否 完成';
const u4=get('u-4'); u4.rank=5;
u4.note+=' ‖ gatekeeper 2026-10-31 re-rank → 5：低于 u-6（u-6 测作者写下的机制，u-4 测台上缺文件造成的意外）。原 why 里「规模因子 注册判据没有队列条目」已由 u-6 补上';
const u3=get('u-3'); u3.rank=6;
u3.note=(u3.note?u3.note+' ‖ ':'')+'gatekeeper 2026-10-31 re-rank → 6：0 回测分钟，只服务 VAL 前置条件（u-1e3：ETF3 仅 16% 收益，动不了 TRAIN 水平），而 VAL 本轮不花。不占账户，可在两次回测之间顺手做，不在今天的回测关键路径上';
fs.writeFileSync(P,JSON.stringify(q,null,2)+'\n');
console.log('ok',q.length);
