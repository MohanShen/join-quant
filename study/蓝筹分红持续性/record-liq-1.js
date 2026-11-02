// One-shot recorder for liq-1 (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
const fs = require('fs');
const path = require('path');
const rq = require('../../utils/research-queue');
const FAM = '蓝筹分红持续性';
const PAGE = path.join(__dirname, '../../wiki/families', FAM + '.md');
if (rq.findings(FAM).some(f => f.qId === 'liq-1')) { console.log('already recorded'); process.exit(0); }

rq.recordFinding(FAM, {
  qId: 'liq-1',
  type: 'understand',
  component_or_param: 'realizability at the book\'s own feasibility floor: on the reference book dxpit, filter_liquidity_floor right after controlReport (before the cascade) keeps qualifiers whose 20-bar MEDIAN daily money ending previous_date is >= 4e6 (= 1e6 / 5 slots / order_volume_ratio 0.05); LIQMIN (every qualifier\'s median) + LIQFLOOR + DXMON logs; one asserted behavioural edit (build-liq.js)',
  metric_delta: 'vs dxpit: obj 0.2630->0.2630 (Δ0); sharpe 2.02->2.02; maxDD 14.61->14.61; total 40.91->40.91; curve bit-identical (242 pts, max|Δcum|=0, orchestrator-verified)',
  window: 'TRAIN 2024 e9',
  finding: 'Floor BINDS ONCE, on a name the book never selects. LIQFLOOR in==out on 11/12 rebalances; Oct rebalance (2024-10-08, previous_date 2024-09-30) in=51 out=50, removing 601211.XSHG 国泰君安 (20-bar median money 0 — no trading in the window, i.e. suspended around its merger with 海通) which is in no month\'s bten in dxpit. DXMON bfive/bten identical to dxpit in all 12 months (only Oct n_qual 51->50 differs; recorder diffed both logs), curve bit-identical. 0 ERROR lines; 12 LIQMIN + 12 LIQFLOOR present (instrumentation fired). Capacity from LIQMIN (recorder recompute): minimum 20d median money over every name in bten in every month = 601229 122.4M (prev 2023-12-29), ~30x the 4e6 floor and ~22x the year-end-capital floor ~5.6e6 (1.409M/5/0.05); every bten name clears 4e7 (10x) in every month. Path-independent ladder over bten: 4e7 removes 0 names in 12/12 months; 2e8 removes 1-3 bten names in 6 of 12 months (prev Dec-29 2, Mar 1, Jun 1, Jul 1, Aug 3, Sep 1 — executor said 7/12, log gives 6); 1e9 removes 5-10 of 10 every month. All-qualifier monthly minimum excluding 601211-Sep is 71.1M (Dec-29) .. 257.4M (Sep-30), so the u-e9-dxew basket (~4e5/name floor at ~50 names) also clears in every month except the same suspended 601211 in Oct. DECLARED RULE gives R=2 literally: the floor removed >=1 qualifier (clause R=2-binds: sharpe 2.02 >= 1.0, Δobj 0 > -0.05); R=3 requires inert AND bten >= 4e7, and only the first leg fails, because of one zero-volume non-selected name.',
  confidence: 'high',
  flags: '⚠零滑点高估 (bench is zero-slippage; a 5-name HS300 book at 1M is small, but impact at 2e8+ is not modelled); regime-specific (2024, one TRAIN year; 2024-09 rally inflated volumes); floor models DECLINING an unfillable name, not partial fills; R=2 by the declared rule, NOT upgraded post hoc',
  description: 'build study/蓝筹分红持续性/build-liq.js -> variants/liq-1.py; algorithmId 4106e8e92e3bd505d9aff07b19bfec73; curve study_蓝筹分红持续性_variants_liq-1__train__e9 (242 pts, final cum 40.91, bit-identical to dxpit, orchestrator-verified); raw log variants/liq-1.log.txt (97 lines: 12 LIQMIN, 12 LIQFLOOR, 12 DXMON, 0 ERROR). Recorder verified from the log: the one removal (601211, median 0, Oct), bten min 601229 122.4M, 4e7/2e8/1e9 ladder counts, DXMON equality with dxpit.log.txt. Corrected executor: 2e8 binds in 6/12 months, not 7.',
  implication: 'SATISFIES the exit gate\'s realizability requirement for dxpit: realizability 2 with realizabilityScope = study/蓝筹分红持续性/variants/dxpit.py, so the §4 [阻塞 exit gate] item is closed and the only remaining gate precondition for the family is the VAL itself (on dxpit, the honest-dividend book; the raw base stays disqualified). R stays 2, not 3: the declared rule binds on the 601211 removal, and reaching R=3 needs capacity EVIDENCE (liq-2), not a reinterpretation of the rule after the number. liq-2 is UNBLOCKED with its rung fixed by its own declared rule: 4e7 is inert on bten by log, so the lowest informative rung is 2e8 (removes bten names in 6/12 months, ~¥50M book) and 1e9 is not run — it is OPTIONAL for the gate (bounds capacity for integration / the dxpit-vs-dxew choice) and must not block VAL. Closes 「is the HS300 dividend book fillable at 1M」 on this bench: do not re-propose a 1x/4e7 floor run. The dxew basket is also cleared at its own floor by the same log, so liquidity is no longer a reason to prefer one book over the other; STAR-board protective-price orders remain the basket\'s real execution gap. Edge statuses untouched: this is not an edge.test.',
  spawned: 'liq-2',
  edgeRef: '股息率',
});

// ── queue ──
const q = rq.load(FAM);
const by = id => q.find(x => x.id === id);
const STAMP = 'recorder 2026-11-01 (liq-1): ';
const l1 = by('liq-1');
l1.status = 'done';
l1.verdict = 'informative';
l1.result = 'R=2 by the declared rule: 4e6 floor removes one qualifier once (601211, median money 0 = suspended, Oct rebalance prev 2024-09-30; never in bten), bfive/bten identical to dxpit 12/12, curve bit-identical (0.2630/2.02/14.61). bten min median 601229 122.4M (~30x floor); 4e7 inert on bten; 2e8 removes bten names in 6/12 months; 1e9 removes 5-10/10 every month. dxew basket floor (~4e5) also clear except 601211. algorithmId 4106e8e92e3bd505d9aff07b19bfec73, curve study_蓝筹分红持续性_variants_liq-1__train__e9.';
l1.note = STAMP + 'done; realizability: 2 written with scope dxpit.py. ' + (l1.note || '');
const l2 = by('liq-2');
l2.status = 'queued';
l2.floor = 2e8;
l2.optional = true;
l2.note = STAMP + 'UNBLOCKED; precondition met (liq-1 R=2). Rung fixed by its own declared rule from liq-1 LIQMIN: 2e8 is the lowest rung that removes >=1 qualifier (bten names in 6/12 months: prev Dec-29 x2, Mar, Jun, Jul, Aug x3, Sep), so run 2e8 ONLY; 1e9 not run. OPTIONAL — not an exit-gate precondition (realizability already scored); it bounds capacity (~¥50M) for integration and the dxpit-vs-dxew choice, and is the only evidence that could later justify R=3. Do not let it block VAL. ' + (l2.note || '');
rq.save(FAM, q);

// ── family page ──
let t = fs.readFileSync(PAGE, 'utf8');
const oldComment = '# ⚠ realizability 故意未设：从未测量。未知 BLOCK 而非 PERMIT，所以本族在 exit gate 上显示 blocked，\n' +
                   '# 这是正确状态。键整个省略而不是写成空值（空值会被 frontmatter.field() 读成下一行）。\n';
if (!t.includes(oldComment)) throw new Error('frontmatter comment not found — page changed, refusing');
const fm =
  'realizability: 2\n' +
  'realizabilityBasis: "liq-1（epoch 9, TRAIN 2024, 2026-11-01）测于 dxpit（诚实分红参照书 = 本族候选）：在 controlReport 之后、级联之前加 20 日中位成交额地板 4e6/日（1e6/5 槽/0.05，设计规模可行性下限），12 次调仓 11 次 LIQFLOOR in==out；唯一一次移除是 10 月调仓（previous_date 2024-09-30）的 601211 国泰君安——20 日中位成交额 0（停牌），从未进入 bten。bfive/bten 12/12 月与 dxpit 相同，曲线逐位相同（242 天 max|Δcum| 0；0.2630/2.02/14.61），0 条 ERROR。按事先声明的规则判 R=2（地板移除了 ≥1 名而书仍过闸）；R=3 要求惰性且 bten 全部 ≥4e7，只因一个停牌、未被选中的名字不成立——**不事后上调**，R=3 需 liq-2 的容量证据而非改读规则。容量（LIQMIN，与路径无关）：任何月份任何 bten 名字的最低中位成交额 = 601229 1.224e8（2023-12-29），约为 4e6 地板的 30×、年末资本地板 ~5.6e6 的 22×；4e7（10×）对 bten 惰性；2e8 在 6/12 月移除 1-3 名 bten（~¥50M 规模开始受限，未测其对 sharpe 的影响）；1e9 每月移除 5-10/10。dxew 篮子（~4e5/名）同一日志下亦通过（除同一停牌名）。⚠ 零滑点台：冲击成本未建模，地板模型是「放弃无法成交的名字」而非部分成交；2024 单年。⚠ 科创板：dxpit 无 688 名字不受影响，但 dxpers / dxew 实测科创板市价单被拒（需保护价），任何放宽门槛或用篮子形态的书须用带保护价的委托，否则其书不是其声明的持仓——该分数不自动适用于那些书。"\n' +
  'realizabilityScope: "study/蓝筹分红持续性/variants/dxpit.py"\n' +
  'realizabilityScopeBasis: "分数测于 dxpit（liq-1 = dxpit + 一处地板编辑，build-liq.js），不是原始 base 94888e61（有前视、不可作候选）。VAL 归档后若产品 expId 不同，须把本键改为该 expId（integrate-eligible 按 expId 或 sourceFile 精确匹配），并核验产品正文与 dxpit.py 相同。"\n';
t = t.replace(oldComment, fm);

// §2 row — append after the last row of the §2 table
const row = '| liq-1 可成交性地板 4e6（realizability） | understand | 参照书 dxpit 在 controlReport 之后、级联之前过滤 20 日中位成交额 < 4e6 的合格名（1e6/5/0.05），记 LIQMIN/LIQFLOOR/DXMON；一处断言改动（`build-liq.js`） | research-liq-1 (e9) | 0 | 0 | 0 | informative | **R=2（按事先声明规则，不事后上调）**：曲线与 dxpit 逐位相同；11/12 月 in==out，唯一移除为 10 月停牌的 601211（中位成交额 0，从未在 bten）；bten 最低中位 601229 1.22e8（~30× 地板），4e7 对 bten 惰性，2e8 在 6/12 月移除 bten 名字，1e9 每月移除 5-10 名。→ exit gate 的 realizability 已满足（scope dxpit.py）；liq-2 解锁、定在 2e8、可选不阻塞 VAL |\n';
const s2 = t.indexOf('## 2. 变体');
const s3 = t.indexOf('\n## 3.');
const sec2 = t.slice(s2, s3);
const lastRowEnd = s2 + sec2.trimEnd().length + 1;
t = t.slice(0, lastRowEnd) + row + t.slice(lastRowEnd);

// §4 gaps — append at end of §4
const gaps = '\n- **[2026-11-01 liq-1 已答 → 已关：本台] realizability 未测**：上面的 [阻塞 exit gate] 条关闭，`realizability: 2`、scope = dxpit.py。不要再提 1×/4e7 地板运行。\n' +
  '- **[可选 / 不阻塞] liq-2 容量点 2e8**：按其自身规则定档（4e7 惰性、2e8 是最低会移除名字的一档）。只用于界定容量（~¥50M）、dxpit vs dxew 选择与整合，也是将来唯一能支持 R=3 的证据；**不得**阻塞 VAL。\n' +
  '- **[VAL 前提更新]** realizability 已测 → dxpit 的 VAL 现在只剩「花不花」的判断。VAL 后归档到 validated_strategies/ 时须把 `realizabilityScope` 改为产品 expId（gate 精确匹配），并核验产品正文 = dxpit.py。\n' +
  '- **[约束 / 可成交性] 分数只覆盖 dxpit 形态**：dxew 篮子同一日志下也过 ~4e5 地板，但其科创板市价单被拒问题（7-9 月 4 次）未解决；若改选篮子书须先加保护价委托并重新确认 scope。\n';
const s5 = t.indexOf('\n## 5.');
t = t.slice(0, s5).trimEnd() + '\n' + gaps + t.slice(s5);
fs.writeFileSync(PAGE, t);

const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch);
console.log(q.slice().sort((a, b) => a.rank - b.rank).map(e => `${e.id}\t${e.status}\trank ${e.rank}`).join('\n'));
