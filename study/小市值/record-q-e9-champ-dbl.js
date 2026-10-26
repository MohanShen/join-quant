// Recorder input for q-e9-champ-dbl (小市值, epoch 9, queue rank 31). Run via:
//   node -e "require('./study/小市值/record-q-e9-champ-dbl.js')"
//
// CONTROL = the champion's own epoch-9 ledger row
//   strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py
//   objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00, 365d  — NOT the base 7a1c225f.
// Never re-run (orchestrator ruling 1); its stored curve recomputes to 2.6281.
//
// Every figure below was recomputed by the recorder from the two stored curves
//   data/series/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa__train__e9.json
//   data/series/study_小市值_variants_0a7de9fa-dbl-off__train__e9.json
// (annualized over the ROW's 365-day span, never the curves' own 242 trading days).
const rq = require('../../utils/research-queue');

rq.recordFinding('小市值', {
  qId: 'q-e9-champ-dbl',
  type: 'ablation',
  component_or_param:
    'MACD 顶背离择时 overlay（`detect_divergence` + `g.dbl[-4:]`）—— ' +
    'study/小市值/build-dbl-0a7de9fa.js → study/小市值/variants/0a7de9fa-dbl-off.py。' +
    'CONTROL = champion [[0a7de9fa_中小盘趋势策略（年化85%）]] 自身的 epoch-9 台账行（中小盘趋势：399101 中小板综指池、' +
    'BBI 带、2 仓、周二 10:45），objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00（365d），' +
    '**不是 base 7a1c225f** —— §2 其余各行的 Δ 都对 base，两者不可并列读。' +
    '唯一改动：在 `detect_divergence` 的 docstring 之后、L600 `fast, slow, sign = 12, 26, 9` 之前插入首条语句 ' +
    '`return False`，一次关掉**两条**作用路径：L366 的 9:00 `dapan` 清非涨停持仓，与 L263 `if True in g.dbl[-4:]:` ' +
    '的 4 日暂停调仓。MACD 本体整段保留（成为死码而非被删），`dapan` 的 else 分支仍每日 `g.dbl.append(False)`，' +
    '故 `g.dbl` 仍被填满、L263 仍被求值——是「停用」而不是「删除」。' +
    'builder 断言了 7 条结构前提（唯一 def、唯一调用点 L366、唯一 g.dbl 读者 L263、else 分支完整、docstring 结束位置、' +
    '探测器只读 MARKET_INDEX、三条日志行健在），并断言撤销该插入后与 `py2to3(raw)` 在 `OVERRIDE` 之前逐字节相同。',
  metric_delta:
    'objective 2.6282 → **2.3319**（Δ **−0.2963**，保留 88.7%）‖ annual = total 276.82 → **247.19**（−29.63pp）' +
    '‖ sharpe 7.07 → **6.11**（−0.96）‖ maxDD 14.00 → **14.00**（**Δ 0.00**；两侧曲线自算均 14.01）。' +
    '曲线自算复现：control **2.6281** / dbl-off **2.3318**（各 242 天，末值 276.82 / 247.19）。' +
    '差异高度局部：242 天里只有 **11 天**的日收益不同，且**全部在十二月**；累计曲线在 2024-12-16 之前 ' +
    '**max|Δcum| = 0.000000（逐位相同）**，首次分岔正好落在 **2024-12-17**（探测器唯一一次发火那天），' +
    'max|Δcum| **37.18pp**（12-19），末端 29.63pp；日收益相关 0.9684；实现波动率 41.2% → 42.4%。' +
    '12-17..12-24 的日收益 control −0.50 / 0 / 0 / 0 / 0 / +3.62 对 dbl-off −8.32 / −1.07 / −2.43 / +3.50 / +3.70 / −0.02；' +
    '自 **12-25** 起两者重新几乎相同（|Δ| ≤ 0.03pp，残差只是权益水平不同带来的取整/现金差）。' +
    '折成末值权益：那一个 session 值 **+8.55%**（3.7682 / 3.4719），即头条累计收益 +29.63pp、objective 的 **11.3%**。' +
    '预注册 Jan–Nov 副读（335 天跨度年化）：control 1.6888 → dbl-off **1.6888**（total 159.71 / annual 182.88 / ' +
    'maxDD 14.01 两侧**全部打印位相同**）。十二月占全年对数增长 28.1% → **23.3%**。',
  window: 'train 2024-01-01→2024-12-31 (365d)',
  finding:
    '**预注册假设 |Δobjective| < 0.3 成立，但只差 0.0037**（实测 0.2963）——' +
    '这么窄的通过不是「安心」的证据，只是没有触发证伪支：' +
    '原定的 |Δ| > 0.3 支（⇒「champion 实质是一本择时书」，须拿去对照 ETF动量 / 七星高照 / 五福闹新春 三族已被证伪的 ' +
    '`趋势择时`）**未触发**，所以本条不开新的择时 edge 主张。' +
    'improve 形状的采纳支（Δ ≥ −0.05 ⇒ 采纳少约 6 个自由度的剥离版）**也不触发**：−0.2963 是真实代价，' +
    '本条不是本族历史上那次「删除即采纳」（imp-5）的形状。' +
    '**机制才是本条的结论**：这台机器在十二个月里**只发火一次** —— 2024-12-17 09:00，清 2 个持仓、暂停 1 次调仓，' +
    '其余 **241 天**日志都是「未检测到」；dbl-off 的日志是干净的正对照（242 天「未检测到」、0 次发火、0 ERROR）。' +
    '我独立复核了两条曲线在 **2024-12-16 及以前逐位相同**、首次分岔**正好**在 2024-12-17，' +
    '故 **0.2963 全部由那一个 session 产生**：control 在 −0.50% 处清仓、随后 5 天空仓（调仓被暂停），' +
    '12-24 周二调仓重新入场；dbl-off 则持仓吃完 −8.32 / −1.07 / −2.43 再接 +3.50 / +3.70 的反弹。' +
    '所以约 **6 个未申报自由度**（MACD 12/26/9、`macd < -0.03`、≥2 死叉点的比较、10 对 20 日 DIF 趋势判据、4 日暂停窗）' +
    '是由**一个交易日**供养的。' +
    '⚠ 而作为**风险装置它没有任何可测作用**：maxDD 在全年与 Jan–Nov 两个切片上**都是 14.01**，两侧相同——' +
    '年内最大回撤不在十二月，这台 overlay 一点也没削到它，它买到的只是**收益**。' +
    '⚠ **两条路径不可归因**：它们在同一天发火，且暂停调仓只是把清仓已经造成的现金继续持有到 12-24，' +
    '所以本次实验**无法**把 9:00 清仓与 4 日暂停分开——这是限制，不是结果。',
  confidence: 'high',
  flags:
    '⚠零滑点台 / single-window（epoch-9 TRAIN 只有 2024 一年）/ ' +
    '**n=1-event**（整个 Δ 由 2024-12-17 一个 session 产生，242 天里只有 11 天日收益不同、全在十二月）/ ' +
    'threshold-pass-by-0.0037（预注册 0.3 线只差 0.0037 未被触发——不得读成「择时不承重」的宽裕证据）/ ' +
    'not-risk-control（ΔmaxDD = 0.00，两个切片的 maxDD 都是 14.01）/ ' +
    'paths-not-attributable（9:00 清仓与 4 日暂停同日发火，无法分离）/ ' +
    'december-localized（Jan–Nov 副读两侧全部打印位相同 1.6888，故本条对 1–11 月完全无信息）/ ' +
    'undeclared-DoF（约 6 个自由度由一个交易日供养）/ ' +
    '⚠ 本条不测容量、不改 q-e9-champ-liq 的 R=2，也不触动任何 edge 块',
  description:
    '1 次回测（TRAIN 2024，epoch 9，365 天，242 个交易日）。对照未另跑（orchestrator ruling 1：builder 走归一化器同一条 ' +
    'py2to3 + OVERRIDE 路径，单行变体可直接对台账行 2.6282 读）。' +
    '发火次数是**免费**取得的，没有加任何探针：`dapan` 每个交易日都打两分支之一（L368 WARNING「⚠️ 检测到大盘顶背离信号…」/ ' +
    'L381 INFO「未检测到大盘顶背离，市场趋势正常」），且 `detect_divergence` 只在 MARKET_INDEX(399101.XSHE) 上调用、' +
    '只读该指数收盘价，所以发火**日期与路径无关**——control 的发火日历可以从同族另一次运行（bbi-off，6,947 行日志，' +
    'limit=2000 分页取尽）读出：fired 1（2024-12-17 09:00）/ not fired 241 / 暂停调仓 1 次 / 清仓 2 个持仓。' +
    '所有绩效数字与分岔日期由记录者对 data/series/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa__train__e9.json 与 ' +
    'data/series/study_小市值_variants_0a7de9fa-dbl-off__train__e9.json 两条存盘曲线独立复核，非取自执行者报告；' +
    'sharpe 两侧取自台账行与执行者抓取（曲线自算的 sharpe 约定不同，只用来复现 objective）。',
  implication:
    '**champion 的头条有一块 n=1 的成分，这件事从此必须随号同行**：2.6282 里的 **0.2963（11.3%）** 完全来自 ' +
    '**2024-12-17 这一个 session**（2024-12-16 之前两条曲线逐位相同），所以引用这本书的水平时，' +
    '可引用的是 2.6282 **但带一条 n=1 的十二月成分**；剥离版 2.3319 是「没有那一天」的水平，两者都过 1.0 闸门。' +
    '三条直接后果：' +
    '(1) **这套 overlay 永远不得作为风险控制被引用** —— ΔmaxDD = 0.00，全年与 Jan–Nov 两个切片的 maxDD 都是 14.01，' +
    '它是一个**收益事件**而不是回撤装置；任何「本书有顶背离保护」的说法在本台上已被测否。' +
    '(2) **不采纳剥离版，也不开择时 edge**：−0.2963 是真实代价（故不是 imp-5 式的「删除即采纳」），而 0.3 证伪线只差 ' +
    '0.0037 未触发（故也不足以主张 champion 是择时书）——两边都不动，overlay 留在 candidate 里，' +
    '但它的约 6 个自由度今后记作**由一个交易日供养的 DATED calibration**，与 BBI 的 0.9/1.3 同级，' +
    '不值得再花回测分钟去重取值（任何重取值仍须先重跑 liq-1，R≥2 测在原书上）。' +
    '(3) **「量级」这个仍开着的问题只剩一个候选**：规模 已确认是方向但与全族共享（q-e9-champ-size，保留 29.5%）、' +
    'BBI 带已被 REFUTED（q-e9-champ-bbi-off，去掉它年化反而 100.9%）、顶背离现在证明是 n=1 的收益事件而非承重机制——' +
    '于是 **rank 32 `q-e9-champ-breadth`（`g.target_stock_count` 2→4 的 2 仓集中度）是解释 2.6282 量级的最后一个未测候选**，' +
    '下一轮应当跑它；若它也不承重，则正确的结论是「量级里有一块是 2024 年十二月的单次事件 + 2 仓的尾部运气」，' +
    '而不是继续找第三个机制。⚠ 并且本条对 VAL/OOS 有一条前置后果：任何对这本书的 VAL/OOS 读数都必须把这块 n=1 ' +
    '的十二月成分带上，不得把 2.6282 当成一个稳定水平去设期望（本族 VAL 仍被 human 挡住，prior-unknown-epoch）。',
  spawned: 'q-e9-champ-breadth',
  edgeRef: '规模',
});

// ── close the queue entry (rank 31) ─────────────────────────────────────────
const entries = rq.load('小市值');
const hit = entries.find(e => e.id === 'q-e9-champ-dbl');
if (!hit) throw new Error('q-e9-champ-dbl not found in the queue — refusing to write a silent no-op');
if (hit.status !== 'answered') {
  hit.status = 'answered';
  hit.result =
    '预注册假设 |Δobjective| < 0.3 成立，但只差 **0.0037**（实测 −0.2963：objective 2.6282 → 2.3319、' +
    'sharpe 7.07 → 6.11、annual 276.82 → 247.19、maxDD 14.00 → 14.00）。' +
    '证伪支（|Δ| > 0.3 ⇒ 实质是择时书）未触发，故不开择时 edge；' +
    '采纳支（Δ ≥ −0.05 ⇒ 采纳少约 6 个自由度的剥离版）也不触发，故不采纳剥离版。' +
    '机制是本条的结论：探测器十二个月**只发火一次**（2024-12-17 09:00，清 2 仓、暂停 1 次调仓，241 天「未检测到」），' +
    '两条曲线在 2024-12-16 及以前**逐位相同**、首次分岔正好在 12-17，' +
    '所以 0.2963（objective 的 11.3%、末值权益 +8.55%）全部由**一个 session** 产生；' +
    '作为风险装置它毫无可测作用（全年与 Jan–Nov 两切片 maxDD 均 14.01），Jan–Nov 副读两侧全部打印位相同（1.6888）。' +
    '⚠ 本条的 design 要求分开陈述两条路径的归因，而实测**做不到**：9:00 清仓与 L263 的 4 日暂停同日发火，' +
    '暂停只是把清仓已造成的现金持有到 12-24 的周二调仓，故两者不可分离——记作限制而非结果。' +
    '`consequenceIfAdopted` 不生效（既非 (a) 也非 (b)），因此不开「与 liq 叠加」的新条目。' +
    '仍开着的「量级」问题由此只剩 rank 32 q-e9-champ-breadth 一个候选。';
  rq.save('小市值', entries);
}

console.log('recorded q-e9-champ-dbl; queue rank 31 -> answered');
