// GATEKEEPER, 2026-10-30 — retarget `q-e9-champ-emptymonth` onto the NEW champion 02fdafaa, mark
// the two other open entries' targets as superseded, and record one hard reject so it is not
// re-proposed. Idempotent: re-running rewrites the same fields and skips the already-present reject.
//
// Why a script and not a hand edit: queue.json is the handoff surface between the gatekeeper and
// the executor, and the family already keeps its queue writes reproducible (queue-init.js,
// queue-e9.js, record-*.js). A hand edit of a 58KB JSON is how a field silently goes missing.

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '../..');
const P = path.join(ROOT, 'study/小市值/queue.json');
const q = JSON.parse(fs.readFileSync(P, 'utf8'));

const CHAMP = 'strategies/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa.py';
const CTRL_MONTHLY = '01 0.00 / 02 +35.34 / 03 +19.03 / 04 +5.64 / 05 -1.26 / 06 -13.17 / '
  + '07 +15.61 / 08 +21.17 / 09 +27.12 / 10 +19.66 / 11 +19.25 / 12 +13.39';

const CONTROL = [
  `CONTROL = the NEW champion's own epoch-9 ledger row: ${CHAMP},`,
  'objective 3.0172 / sharpe 8.22 / annual 320.35 / maxDD 18.63, 365 days, curve on disk',
  '(data/series/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa__train__e9.json).',
  '! The gatekeeper reproduced 3.0172 / 320.35 / 18.63 from that curve before queueing this, so the',
  '  control needs no re-measure (orchestrator ruling 1 still holds: the builder uses the same',
  '  exported py2to3 + OVERRIDE path the normalizer used, so a one-edit variant is directly',
  '  comparable to 3.0172).',
  `! CONTROL monthly table (gatekeeper, free, from the stored curve): ${CTRL_MONTHLY}`,
  "! CONTROL maxDD window = 2024-05-07 -> 2024-06-24, 18.63%. The year's drawdown is NOT in January,",
  '  so a maxDD that moves INTO January is the sharpest single observable this run offers.',
].join('\n');

const SECONDARY = [
  'PRE-REGISTERED FREE SECONDARY READ (standing orchestrator ruling 3) — recompute the variant\'s',
  "objective EXCLUDING December 2024 from its stored curve, against the control's Jan-Nov figure.",
  'CONTROL, recomputed by the gatekeeper from the stored e9 curve:',
  '  full 2024  total 320.35 | annual 320.35 | maxDD 18.63 | objective 3.0172  (reproduces the ledger)',
  '  Jan-Nov    total 270.70 | annual 316.85 (365/335) | maxDD 18.63 | objective 2.9822',
  '  December alone +13.39%; Delta objective (full - JanNov) = +0.0350.',
  "!! DIFFERENT FROM THE OLD CHAMPION: 0a7de9fa's December was 28.1% of its year's LOG-growth, so the",
  '   December-dependence worry that motivated ruling 3 does NOT bite on 02fdafaa. Here the secondary',
  '   read is a free confirmation rather than the main risk. Report it anyway — un-skipping January',
  "   changes the compounding base for every later month, so the variant's December share can move",
  "   even though the control's is small.",
  '! maxDD is 18.63 in BOTH slices (window 05-07 -> 06-24), so the Jan-Nov read moves return only.',
  "!! Annualize over the SLICE'S CALENDAR SPAN (365 full / 335 Jan-Nov), never over the curve's own",
  '   trading-day count, and compute BOTH sides with the one formula.',
  'This is a ROBUSTNESS FALSIFIER, never an adoption metric — and nothing on this entry is adoptable.',
].join('\n');

const HYPOTHESIS = [
  '主张（可被单一结果推翻）：日历空仓不是 3.0172 的收益主体。',
  '',
  'PRIMARY 预注册证伪项 —— 标的是变体的 2024-01 单月收益 r_jan，不是 Δobjective。看到任何数字前锁定：',
  '  (a) r_jan >= 0       ⇒ 主张成立，且是本轮最有价值的意外：这本书自己选出来的 1 月名字本来没事，',
  '                         那条规则什么也没买到，于是「三本头名 2024-01 都恰好 0.0%」不能被读作事后性，',
  '                         2 月反弹的捕获（+35.34%）才是优势所在。',
  '  (b) -10% < r_jan < 0 ⇒ 部分成立：本书选股对踩踏有一定抵抗力，这条日历规则比横截面暗示的值钱得少。',
  '  (c) r_jan <= -10%    ⇒ 主张被推翻。本书自己的名字确实会被 2024-01 微盘踩踏抓住，作者那条',
  '                         「1 月不开仓」大约值这么多 —— 一个有日期、不会重复的 HINDSIGHT QUANTUM。',
  '',
  'SECONDARY（量级）：Δobjective。中心点估计 ≈ -0.75 ~ -0.85，由 pre-2024 四本在 2024-01 的 -16%~-22%',
  '推出：若 r_jan ≈ -18% 且其余 11 个月不变，total 320.35% → ≈245%，maxDD 由 18.63 抬到 ~20，',
  'objective ≈ 2.25。沿用被取代版本的那条线以便两版判定可比：Δobjective <= -0.5 ⇒ 主张被推翻。',
  '',
  '⚠ 不要把大 Δobjective 读成「这条日历规则是个大 edge」。Δobjective 随本书的收益水平线性放大 —— 一个',
  '  -18% 的 1 月在一本 320% 的书上机械地就值约 0.76 的 objective。可外推、可与 pre-2024 四本直接比的量',
  '  是 r_jan；Δobjective 只是它在这本书水平上的投影。',
  '⚠⚠ 任何方向都不开 improve。2024-01 是一个有日期、不重复的事件，Δ 是事后性配额而不是可采纳的改进；',
  '  原书已经站在「跳过 1 月」那一侧，所以本条在结构上只能往下测。与 q-e9-champ-dbl 同类：必须按 n=1 报，',
  '  不得报成 risk control。',
].join('\n');

const WHY = [
  'CHAMPION 换了。bestVariant 从 0a7de9fa（2.6282）变成 02fdafaa（objective 3.0172 / sharpe 8.22 /',
  'maxDD 18.63，epoch 9，365d，曲线在盘），是 4 个新成员之一。这是新 champion 身上最便宜也最直接的事后性',
  '测量：一行改动、1-3 分钟。',
  '',
  'NEW FREE EVIDENCE —— postedAt 全库回填（CLAUDE.md 2026-10-27）第一次让「作者可见性」可算。本族 45 个',
  'epoch-9 成员中 42 个有发帖日：pre-2024 4 本中位 objective -0.3562、过闸率 0%；2024-25 10 本 1.3571 /',
  '100%；2026 28 本 0.7041 / 68%。',
  '⚠ 竞争解释（regime 而非 hindsight）已被 orchestrator 测过并且大体胜出：那 4 本 pre-2024 在 2024-01',
  '  亏 -16%~-22%（微盘踩踏），其中 2 本全年总收益为正（d695b821 +30.3%、94d9f1ce +9.9%），只是被',
  '  objective 的回撤项打掉。所以这个横截面不得被记成「事后性解释了排名」。',
  '但它定位到一个机制：三本头名（02fdafaa / 0d022129 / 0a7de9fa）2024-01 都恰好赚 0.0%（空仓），然后吃下',
  '+35.34% / +33.98% / +8.6% 的 2 月反弹。本条把那个 0.0% 换成「照常持微盘」，看它值多少 —— 这是把一个',
  '横截面相关性变成一次本书内部因果测量的唯一办法。',
  '',
  'VAL 已 BLOCKED（already-validated；2026-10-27 那次跑在旧 champion 上，sharpe 0.83 未过），本轮不可能',
  'finalise 任何东西，所以归因型 understand 正是这些分钟该买的东西。',
].join('\n');

const DESIGN = [
  'SINGLE EDIT —— py2to3 后第 42 行，全行精确匹配：',
  '  `    g.pass_april = True  # 是否四月空仓`',
  '  -> `    g.pass_april = False  # q-e9-champ-emptymonth: 日历空仓关闭（归因）— 相对原书的唯一改动`',
  'gatekeeper 已核：py2to3 后该行在全文恰好 1 处匹配；today_is_between（L540-548）在 g.pass_april is',
  'False 时无条件 return False，所以一行同时关掉 01-01..01-30 与 04-01..04-30 两段。',
  '不改 close_account / close_no_trading_hold / weekly_adjustment / g.no_trading_buy 的任何代码路径 ——',
  '让空仓机器照常求值并恒为 False。',
  '明确不做：不换月份、不加月份、不只去掉 1 月留下 4 月。q-e6-4（STALE, epoch 6）关掉的正是「调月份」这个',
  'improve 旋钮，而一年期 TRAIN 上调月份只会更纯粹地拟合当年。本条只做归因，不做调参。',
  '',
  '⚠⚠ 一次翻转动了两条不同的事后性通道，报告必须分开归因 —— 分月表免费做到，不需要第二次回测：',
  ' (1) 2024-01 是真现金，control 0.00%。它之所以是纯现金而不是持防守篮子，是因为回测起点 2024-01-02 时',
  '     g.hold_list 为空，close_account 的 len(g.hold_list) != 0 不成立，g.no_trading_hold_signal 整个',
  '     1 月都没被置 True —— 这是窗口起点的产物，不是作者写下的意图。',
  ' (2) 2024-04 不是现金，是一个 2026 年手挑的三名防守篮子：',
  "     g.no_trading_buy = ['600036.XSHG' 招商银行, '518880.XSHG' 黄金ETF, '600900.XSHG' 长江电力]（L61），",
  '     由 close_account 在该段第一个有持仓的交易日买入，再由 weekly_adjustment L146 的',
  '     close_no_trading_hold 在恢复后的第一次调仓卖掉（close_no_trading_hold 没有被任何 run_* 挂过，只在',
  '     weekly_adjustment 里被调用 —— 已核）。control 的 4 月 +5.64% 来自这个篮子，不是来自现金。',
  '  所以「日历空仓」实际上是「1 月现金 + 4 月手挑防守篮子」，两种不同的事后面，Δobjective 是两者之和。',
  '  只有分月表能把它们分开；若 4 月通道贡献可观，那是一条独立的事后性发现（手挑名字），必须单独归因，',
  '  不得折进「1 月规则」。',
  '',
  'BUILDER（沿用本族已验证的形状，照 study/小市值/build-bbi-0a7de9fa.js）：',
  '  study/小市值/build-emptymonth-02fdafaa.js —— py2to3(raw) + 一次整行替换 + OVERRIDE。断言：',
  '  edit site 恰好 1 处；撤销该行后与 py2to3(raw) 逐字节相同（对 PRE-OVERRIDE 文本断言，不要切片 —— ',
  '  build-liq-5a70adc1 的假「第 840 行差异」就是切片造成的）；g.no_trading_buy / def today_is_between /',
  '  def close_account / close_no_trading_hold(context) 原文保留。输出 variants/02fdafaa-emptymonth.py，',
  '  --window train。',
  '',
  'EXECUTOR 必须报告（不是只报 Δobjective）：',
  ' 1. 变体的 12 行分月收益表，尤其 2024-01 与 2024-02 —— 通道要看得见，不要靠推断。',
  `    CONTROL: ${CTRL_MONTHLY}`,
  ' 2. 2024-04 单月收益（手挑篮子通道），与 control +5.64% 对照。',
  ' 3. maxDD 的数值**与它发生的窗口**。control 是 18.63%，窗口 2024-05-07 -> 2024-06-24 —— 全年回撤不在',
  '    1 月。若变体的 maxDD 窗口移进 1 月，就说明这本书的低回撤是一条日历规则买来的；若仍在 5-6 月，',
  '    Δ 就只走收益项。',
  ' 4. 1 月单月的峰谷回撤（不是全年 maxDD），以便和 pre-2024 四本的 -16%~-22% 直接比。',
  ' 5. Jan-Nov 稳健性读数（见 secondaryRead）。',
].join('\n');

const entry = q.find(e => e.id === 'q-e9-champ-emptymonth');
if (!entry) throw new Error('q-e9-champ-emptymonth not found — refusing to invent it');

entry.rank = 26.4;
entry.status = 'active';
entry.title = '归因日历空仓（g.pass_april）：新 champion 02fdafaa 的 3.0172 里有多少是'
  + '「2026 年的作者知道 2024 年 1 月发生了什么」';
entry.hypothesis = HYPOTHESIS;
entry.why = WHY;
entry.design = DESIGN;
entry.edgeRef = '规模';
entry.edgeRefNote = '无 edge —— 日历空仓不属于本族任一 measured edge（规模 / 低开反转）。本条测的就是它占了'
  + '多少，所以是 off-mechanism check；按 understand 判，两个方向都是信息。';
entry.control = CONTROL;
entry.secondaryRead = SECONDARY;
entry.result = null;
entry.from = [
  `ledger: ${CHAMP} @epoch9 objective 3.0172 / sharpe 8.22 / annual 320.35 / maxDD 18.63 / 365d `
    + '(gatekeeper reproduced all three from the stored curve)',
  "SUPERSEDES this entry's own earlier version (same id, was rank 28, targeted the OLD champion "
    + '0a7de9fa: EMPTY_MONTHS=[1,4] -> [], control 2.6282) — see the `supersedes` field for the ruling',
  'q-e6-4 (STALE closure, epoch 6 — it closed the "move the months" IMPROVE knob on base 7a1c225f, '
    + 'and its reasoning is WINDOW-level ("would only fit 2022"), which the contract makes reopenable. '
    + 'This entry is an ATTRIBUTION ablation on the champion, not that knob — not a duplicate)',
  'postedAt repo-wide backfill (CLAUDE.md 2026-10-27): the author-post-date cross-section over this '
    + "family's 45 epoch-9 members (42 dated), computed by the orchestrator",
  "orchestrator's test of the rival explanation: the 4 pre-2024 books lose -16% to -22% in 2024-01 and "
    + '2 of them have POSITIVE total return for the year ⇒ the cross-section is substantially REGIME, '
    + 'not hindsight',
  'q-e9-champ-dbl (this family: a dated single-event contribution must be reported as n=1 and never as '
    + 'risk control)',
  'ETF动量 / 七星高照 「池子是一个 2026 年事后写的池子」 — the MECHANISM-class hindsight argument shape, '
    + 'which survives a bench change',
];
entry.supersedes = {
  target: 'strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py (EMPTY_MONTHS = [1,4] -> [])',
  oldControl: 'objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00, 365d. Its 2024-01 was '
    + "+0.11% (it parked in the 511880 money ETF) against 02fdafaa's exact 0.00% (true cash).",
  ruling: 'RETARGET, do not keep both. 0a7de9fa is no longer the family candidate, and the two books '
    + 'implement the SAME channel (a 2026-authored calendar rule that sits out 2024-01), so measuring '
    + 'it on the superseded book buys strictly less for the same 1-3 minutes. One attribution of the '
    + 'live headline beats two of a dead one.',
  scopeBound: "HONEST BOUND: the result is about 02fdafaa only. 0a7de9fa's January is a money-ETF park "
    + '(+0.11%) rather than true cash and its names differ, so its hindsight quantum is NOT this one '
    + 'and must never be quoted from it. Nothing in the loop needs that number — it is no longer the '
    + 'candidate — so the gap is RECORDED, not queued.',
};
entry.gatekeeperRanking = 'Ranked 26.4, ahead of 26.5 (liq-2/liq-3) and 27 (bench-lastprice), for three '
  + 'reasons: (i) both of those are written against the SUPERSEDED champion 0a7de9fa and need a '
  + 'retarget before they are worth minutes, while this entry IS the retarget; (ii) the evidence '
  + 'prompting it is brand new and free (postedAt, 2026-10-27) and nothing else in the queue consumes '
  + 'it; (iii) VAL is BLOCKED, so nothing is finalisable this round and attribution of the LIVE '
  + 'headline is the highest-information thing 1-3 backtest minutes can buy. Cost: ONE 365-day run.';

// ── the two other open entries still point at the superseded champion ───────
const staleNote = 'TARGET SUPERSEDED (gatekeeper, 2026-10-30): written against 0a7de9fa, which is no '
  + 'longer the family champion — bestVariant is now 02fdafaa (objective 3.0172 / sharpe 8.22 / '
  + 'maxDD 18.63, epoch 9). The QUESTION is still live; the TARGET and every control figure quoted '
  + 'here are not. Retarget before spending minutes, and do NOT dispatch this as written.';
for (const id of ['q-e9-champ-liq-2', 'q-e9-bench-lastprice']) {
  const e = q.find(x => x.id === id);
  if (!e) throw new Error('missing ' + id);
  e.targetStale = staleNote;
}
q.find(x => x.id === 'q-e9-champ-liq-2').targetStale += ' Extra cost note: liq-2/liq-3 were BUILT '
  + 'against 0a7de9fa (study/小市值/build-liq-0a7de9fa.js FLOORS), so a retarget is a rebuild, not a '
  + 'dispatch — and the capacity question itself changes, because 02fdafaa holds g.stock_num 6 rather '
  + "than 0a7de9fa's 2, so its per-name position (and therefore its feasibility floor) is ~3x smaller.";
q.find(x => x.id === 'q-e9-bench-lastprice').targetStale += ' NOTE for whoever retargets it: 02fdafaa '
  + 'DOES read intraday prices for decisions (get_current_data()[s].last_price / high_limit at L297 and '
  + "L449; history(1, unit='1m') at L346/L356/L375), so the bench-semantics question transfers to the "
  + "new champion intact, and its free STEP 0 (read the stored run's own log) is unchanged in kind.";

// ── one hard reject, recorded so it is not re-proposed ──────────────────────
const REJECT_ID = 'q-e9-d695b821-codepitfall';
if (!q.some(e => e.id === REJECT_ID)) {
  q.push({
    id: REJECT_ID,
    kind: 'understand',
    rank: 99,
    status: 'dropped',
    title: 'REJECTED: 在 d695b821 上找它标题声称的「选择股票代码的奇葩坑」',
    hypothesis: 'REJECTED BEFORE QUEUEING —— 写不出可证伪的缺陷主张。标题声称存在一个代码选择坑，但源码里'
      + "唯一的候选是 L131-133 的 startswith('4') / startswith('8') 板块排除，那看起来就是普通的北交所"
      + '过滤；realizability-lint 对本文件干净。要写出一条可证伪的假设，先得有一个具体的缺陷主张，现在没有。',
    why: 'HARD REJECT，理由记录在案以免被重新提出。本族已经为一条基于猜测的规则付过代价（CLAUDE.md：一条'
      + '猜测式硬拒规则永久丢掉了 549 个策略里的 287 个），而本族自己的 100x 单位 bug（q-e6-13）是从一本'
      + '**已被测量**的书里读出来的，不是猜出来的。d695b821 的 objective -0.1481 既不是候选也不进任何表，'
      + '在它身上做缺陷搜捕的期望信息量接近零。若将来要重开：先给出一个具体的缺陷主张（哪一行、改成什么、'
      + '预期哪个方向），再写条目 ——「标题说有个坑」不是主张。',
    design: 'none — rejected, nothing to run',
    from: [
      'orchestrator 2026-10-30: read the source, could not confirm a defect; lint clean; explicitly '
        + 'asked that no defect hunt be queued on a guess',
      'ledger: d695b821 @epoch9 objective -0.1481 / annual 30.27 / sharpe 0.52 / maxDD 45.08 / 365d',
      'q-e6-13 / q-e6-19 (this family\'s unit-bug precedent: it was READ out of a book that had '
        + 'already been measured, not guessed from a title)',
      'CLAUDE.md: a pre-measurement reject must be a known fact, never a guess',
    ],
    edgeRef: null,
    result: 'dropped by the gatekeeper on 2026-10-30 — no falsifiable defect claim exists to test. '
      + 'd695b821 is still worth RECORDING: it is the family\'s only member whose author saw neither '
      + 'TRAIN nor VAL (posted 2023-03-20), total return +30.27% with a -15.86% January hole and '
      + 'maxDD 45.08 sinking its objective — the cleanest single datapoint that the pre-2024 cohort\'s '
      + 'failure is a DRAWDOWN story, not a return story.',
  });
}

fs.writeFileSync(P, JSON.stringify(q, null, 2) + '\n');
console.log('[gate] written; entries =', q.length);
