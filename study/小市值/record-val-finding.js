// record-val-finding.js — one-shot: append the q-e9-champ-val finding via the research-queue API.
// Kept as a file rather than inlined into `node -e` because the row's prose contains quotes,
// parentheses and ⚠ markers that shell quoting mangles.
'use strict';
const rq = require('../../utils/research-queue');

rq.recordFinding('小市值', {
  qId: 'q-e9-champ-val',
  type: 'validation',
  component_or_param: '窗口 TRAIN 2024 → VAL 2025；被跑的书是 champion [[0a7de9fa_中小盘趋势策略（年化85%）]] 的 pinned 产品快照 enhance/candidates/xsz-e9-champ.py（py2to3(raw) 逐字节 + 冻结 epoch-9 OVERRIDE，零逻辑改动；builder study/小市值/build-champ-product.js 断言 body 相等与三枚 pin）。runId xsz-e9-champ-val，orchestrator 亲跑（按契约从不委派）',
  metric_delta: '跨窗口读数、不是 Δ（两个数来自两个不同日历年）：objective 2.6282 → 0.0723 / sharpe 7.07 → 0.83 / annual 276.82% → 27.11% / maxDD 14.00% → 19.80%（TRAIN 365d vs VAL 364d）。recorder 复算 243 点曲线：末值 cum 27.03 与抓取逐位相同、自算 maxDD 19.7992（峰 2025-08-11 → 谷 2025-12-31）、年化波动 28.83%、121 涨/97 跌/24 平、最差日 −6.01%、最好日 +7.94%、Q1..Q4 = +17.85/+16.45/−4.35/−4.76、H1 +37.23%（maxDD 7.01%）/ H2 −7.43%、峰值 cum +58.39%。objective 口径：年化取 total 27.03 ⇒ 0.0723，按台账 365/364 年化 27.11 ⇒ 0.0731（两者皆已复核，结论相同；闸门判的是 sharpe）',
  window: 'val 2025-01-01→2025-12-31 (364d)',
  finding: 'champion 的 pinned 快照（零逻辑改动）在 VAL 2025 上 FAIL：sharpe 7.07 → 0.83，低于 epoch-9 的 1.0 闸门，同时 annual 276.82% → 27.11%、maxDD 14.00% → 19.80%（变差），objective 2.6282 → 0.0723。不是均匀走弱而是先强后弱：H1 2025 +37.23%（maxDD 仅 7.01%）、2025-08-11 见顶 +58.39%，随后 H2 −7.43%、Q3/Q4 皆负，且 19.80% 的回撤段 2025-08-11→2025-12-31 在窗口边缘仍未结束（故 19.80 是该段的下界而非完成值）。年化波动 28.83% 与 sharpe 0.83 相容 ⇒ 非 scrape artefact。本次 VAL 由 human 设置 JQ_ALLOW_REVAL 授予（原阻塞是 2026-09-19 jul12-005 行记了 val-pass 却无 epoch，unknown 一律挡）',
  confidence: 'high',
  flags: '⚠零滑点高估, val-fail, human-override: JQ_ALLOW_REVAL（由人设置于环境，agent 未设；consumption 行带 [JQ_ALLOW_REVAL] 标记）, drawdown-open-at-window-edge, n=1-december-component（TRAIN 的 0.2963 来自 2024-12-17 单次发火）, regime-specific: TRAIN 与 VAL 各只有一个日历年, overfit-cliff',
  description: '零逻辑改动是本行最强的一点：被验证的就是 champion 本身，没有任何可回滚的变异，所以失败归于 champion 自身的水平、而非候选构造。对照是同一本书的 epoch-9 TRAIN 台账行（2.6282 / 7.07 / 276.82 / 14.00，365d），不是本族 §2 其余各行的 baseline-e6。⚠ 本行未运行 规模 或 低开反转 任何一条 edge 的 test:，它测的是「这本书的水平能否延续到相邻一年」，不是 规模 的横截面方向（那是 q-e9-champ-size 在 TRAIN 上测的）⇒ 两条 edge 的 status 一律不动。⚠ 算术口径 sharpe（mean/sd×√252）为 1.01，与 JQ 口径 0.83 不可并列引用。⚠ spawned 的 q-e9-champ-breadth 是既有队列项（rank 32，2026-10-26 起 queued），本行只是把它指成唯一剩下的解释，并非新开',
  implication: '(a) 本族在本台上没有任何过闸的已验证候选，且 exit gate 的 block 从「一行缺 epoch 的旧账」变成一条实测结论——归档后闸门自己改口为「xsz-e9-champ epoch 9 gate fail」；并且一旦把环境里的 JQ_ALLOW_REVAL 撤掉，assess 立刻从 owner=research 变 owner=human（val-budget 报 already-validated），本族就不再被每天当 integrate-blocked 重派。所以下一步的动作是撤掉那个环境变量，不是再跑一轮 research。(b) 2.6282 这个水平不可重复，正是 q-e9-champ-dbl 的 n=1 十二月成分（0.2963 = objective 的 11.3%，ΔmaxDD 0.00）所预示的脆弱 ⇒ 今后引用本 champion 只能引 VAL 水平或剥离版，TRAIN 水平永久降级为「2024 年的一个读数」，不得用作期望。(c) 这是本仓第三次期外失败（大小盘轮动 OOS −0.21、红利低频 OOS −0.51、本次 VAL 0.83），三本在 TRAIN 上都好看 ⇒ 要怀疑的是选择流程（一年 TRAIN 选出的水平）而不是某一族；因此不得用「换一本候选再验一次」回应，那是对 VAL 的逐次选择，本台 VAL 已花尽。(d) 能改变画面的只有两件：一个 TRAIN 水平不靠单月的候选；以及仍排在队列里的 rank 32 q-e9-champ-breadth（g.target_stock_count 2→4），它是对 champion TRAIN 量级的最后一个未测解释——若它也不承重，正确结论是「量级 = 一次十二月事件 + 2 仓的尾部运气」，而不是继续找第三个机制',
  spawned: 'q-e9-champ-breadth',
  edgeRef: '规模',
});

console.log('recorded q-e9-champ-val');
