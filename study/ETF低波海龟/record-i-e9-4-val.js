// One-shot recorder for i-e9-4 (TRAIN) + the family's epoch-9 VAL elhg-i-e9-4-val, 2026-11-01.
// Writes: 2 findings, queue status, family page (edge evidence, §2 rows, §4 bullets, §5 row,
// realizabilityBasis), and archives the validated book to validated_strategies/elhg-i-e9-4.py.
// Refuses to run twice.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const ROOT = path.join(__dirname, '..', '..');
const rq = require('../../utils/research-queue');
const F = 'ETF低波海龟';

const have = new Set(rq.findings(F).map(f => f.qId));
if (have.has('i-e9-4') || have.has('val-e9-i4')) { console.error('already recorded — refusing'); process.exit(2); }
const SHELF = path.join(ROOT, 'validated_strategies', 'elhg-i-e9-4.py');
if (fs.existsSync(SHELF)) { console.error('shelf file exists — refusing'); process.exit(2); }

// ── archive input: verify the exact file the VAL ran ────────────────────────────────────────
const VARIANT = path.join(ROOT, 'study', F, 'variants', 'i-e9-4.py');
const body = fs.readFileSync(VARIANT);
const SHA = crypto.createHash('sha256').update(body).digest('hex');
if (SHA !== 'ffb0319c298e7f32e6a489978cdef485630edcbbfccfd8b5196d3a1edfe57a2c') {
  console.error('variant hash changed since the VAL — refusing to archive', SHA); process.exit(2);
}
const curve = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/series/study_ETF低波海龟_variants_i-e9-4__val__e9.json')));
const last = curve.cum[curve.cum.length - 1];
if (Math.abs(last - 7.14) > 0.05 || curve.cum.length !== 243) { console.error('VAL curve disagrees', last, curve.cum.length); process.exit(2); }

// ── findings ───────────────────────────────────────────────────────────────────────────────
rq.recordFinding(F, {
  qId: 'i-e9-4', type: 'improve',
  component_or_param: 'i-e9-3 的 3 只 1/vol 构造（集合变化再平衡、逐名 20 日最短持有 + 10% 带、叠加关闭）搬到 q-e9-4 的逐日点时权益 ETF 池（不含黄金），国债腿逐字不动',
  metric_delta: 'vs q-e9-4 Δobj +0.0454 / Δsharpe +0.20 / ΔmaxDD +0.56；vs i-e9-3 Δobj −0.0104 / Δsharpe −0.44 / ΔmaxDD +0.87；行情两周 +19.35%，其余 +4.64%（rest sh 0.42）',
  window: 'train',
  finding: 'TRAIN 2024（242 点，曲线末值 24.88 经 orchestrator 校验）：total 24.88 / sharpe 1.34 / maxDD 9.90 / obj 0.1498；对照 i-e9-3（手选含金池）25.05 / 1.78 / 9.03 / 0.1602，q-e9-4（点时池单只）19.78 / 1.14 / 9.34 / 0.1044。09-24..10-08 两周 +19.35%，其余天 +4.64%（rest sharpe 0.42）。权益持仓全部是红利/银行/50 类；避险腿放行 59 天，国债持有 56 天（10-15..12-31），1/vol 使国债一入槽即占 85–95% 权重。liq-i-e9-4（下限 capital/3/0.05 = 6.67e6，20 日均额）逐位相同（max|Δcum| 0）；池自身的 2e7 20 日中位数门槛蕴含 ≥1e7 的 20 日均额，风险名字按构造惰性；国债 ≥2.82e8。',
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific (2024 单窗口；行情两周 +19.35% 承载大部分全年，rest sh 0.42); 2024 红利/银行本身是赢家; 国债腿占年末 ~2.5 个月',
  description: 'variant study/ETF低波海龟/variants/i-e9-4.py（builder study/ETF低波海龟/build-i-e9-4.js）；liq 变体 variants/liq-i-e9-4.py（builder build-liq-i-e9-4.js）；日志 logs/i-e9-4-train.log、logs/liq-i-e9-4-train.log；曲线 data/series/study_ETF低波海龟_variants_i-e9-4__train__e9.json；对照 q-e9-4 与 i-e9-3。queue 预声明：sharpe ≥ 1.0 且 ≥ q-e9-4 的 1.14 ⇒ 1.34 通过。',
  implication: '判定 adopted 为本族 epoch-9 唯一 VAL 候选（预声明 bar 通过），VAL 花在它而不是 i-e9-3/base 上（§4 VAL 决定）。但同一结果预示 VAL 的上限：分散到 3 只在权益池上只把 sharpe 从 1.14 抬到 1.34，而手选含金池上是 1.24 → 1.78 ⇒ i-e9-3 的 +0.54 大部分是黄金进槽（q-e9-7 同向），1/vol 宽度本身在无金池上只值约 +0.20；行情外 sh 0.42 才是规则在 2024 的非事件水平，1.34 里约 2/3 是一个两周 ⇒ VAL 若没有它自己的行情两周，预期水平接近 0.4 而非 1.3。liq 轴在点时池上已重跑且惰性（R≥2 对本书成立），不再是引用本书数字的阻塞。',
  spawned: 'val-e9-i4 (the VAL, spent by the orchestrator)',
  edgeRef: '低波动异象',
});

rq.recordFinding(F, {
  qId: 'val-e9-i4', type: 'validate',
  component_or_param: '本族 epoch 9 唯一一次 VAL，跑在 variants/i-e9-4.py（点时权益池 + 3 只 1/vol，叠加关闭），与 TRAIN 逐字相同；runId elhg-i-e9-4-val，algorithmId a606becc364d9fa2c01db53c0b50317e，backtestId ccc85e48bff5fa1e06b6b35f3db108de；预期在数字存在前写于 §4（sharpe 0.5–1.2）',
  metric_delta: 'TRAIN obj 0.1498 / sharpe 1.34 → VAL obj 0.0138 / sharpe 0.33；VAL vs 沪深300 +7.14% vs +17.66%（−10.52pp）',
  window: 'val',
  finding: 'VAL 2025-01-01..2025-12-31（243 点，曲线末值 7.14 与 scrape 一致）：total 7.14% / annual 7.16% / sharpe 0.33 / maxDD 5.78% ⇒ obj 0.0138，FAIL stageGate(validate)=1.0，且低于预声明区间 0.5–1.2。基准 000300 +17.66%。分季（策略 vs 300）：Q1 −1.89 vs −1.21，Q2 +4.05 vs +1.26，Q3 +3.52 vs +17.90，Q4 +1.39 vs −0.24 ⇒ 落后的 10.5pp 全部在 Q3，其余三季持平或领先。低点 −5.78%（01-13，即 maxDD 来自首两周），高点 +12.26%（11-12），年末回吐至 +7.14%。日收益对 300 相关 0.56、beta 0.38、年化波动 10.3%。日志 8 次集合变化，全部为红利/低波类权益 ETF（515300、515450、563020、510720、159581、510980、515080、159307；首日含 159611/159887），国债从未持有（0 条国债代码）。',
  confidence: 'high',
  flags: '⚠零滑点高估; VAL-spent (one per family×bench, epoch 9); regime-specific (2025：Q3 广谱上涨中红利/低波不参与); 规则参数（60 日窗/20 日持有/10% 带/0.40 阈值）仍出自 2026 作者',
  description: '曲线 data/series/study_ETF低波海龟_variants_i-e9-4__val__e9.json（243 点，含 benchCum）；日志 study/ETF低波海龟/logs/i-e9-4-val.log；VAL-SPENT 由 executor 记入 data/consumption.tsv（runId elhg-i-e9-4-val）；归档 validated_strategies/elhg-i-e9-4.py（gate_val: fail）。分季/相关由 recorder 从存储曲线计算。',
  implication: '按预声明读法：VAL < 1.0 ⇒ TRAIN 的 1.34 是 2024 防御行情 + 一个行情两周的水平，事前权益池上的低波规则没有跨年站住；本族在 epoch 9 无可交付候选 ⇒ BLOCKED 终态，**不再构造新候选去补一次 VAL**（那是在 VAL 上做选择）。更紧的读法：VAL sharpe 0.33 ≈ TRAIN 行情外 sh 0.42 ⇒ 规则的非事件水平在两年间一致约 0.3–0.4，2024 的过闸靠的是恰好抓到的那个两周，而 2025 的行情是 Q3 的慢涨、低波排序按构造不持有它 ⇒ 关闭「在此规则上调参提高 TRAIN sharpe」这个方向：任何新 TRAIN 改进只会再拟合一个事件。edge 低波动异象 保持 measured（其 test 是 TRAIN 池内/池分句测试，本次不是它的 test），但 evidence 必须写明未跨年持续，不得被引为前向已验证的 edge。避险腿在 VAL 上 0 天持有国债 ⇒ 仍未被评价。',
  spawned: 'none (family BLOCKED terminal on epoch 9; no new candidate by pre-declaration)',
  edgeRef: '低波动异象',
});

// recordFinding marks the idea `answered`; the queue's own convention for finished ideas is `done` + result.
const q = rq.load(F);
for (const e of q) {
  if (e.id === 'i-e9-4') {
    e.status = 'done';
    e.result = 'adopted as VAL candidate：点时权益池 3 只 1/vol 24.88 / sh 1.34 / maxDD 9.90 / obj 0.1498（vs q-e9-4 1.14、i-e9-3 1.78）；两周 +19.35% / 其余 +4.64%（rest sh 0.42）；liq-i-e9-4 惰性。VAL elhg-i-e9-4-val：sharpe 0.33 / obj 0.0138 FAIL（300 +17.66%，落后全在 Q3）⇒ 族 BLOCKED';
  }
}
rq.save(F, q);

// ── family page ────────────────────────────────────────────────────────────────────────────
const P = path.join(ROOT, 'wiki/families', `${F}.md`);
let t = fs.readFileSync(P, 'utf8');
const rep = (a, b) => {
  const n = t.split(a).length - 1;
  if (n !== 1) { console.error(`anchor matched ${n}×: ${a.slice(0, 60)}`); process.exit(3); }
  t = t.replace(a, b);
};

// edge evidence — prepend; status stays measured (the VAL did not run the claim's test).
rep('    evidence: "measured（2026-11-01，test 全部跑完',
  '    evidence: "⚠⚠⚠ 未跨年持续（VAL 2025，elhg-i-e9-4-val，2026-11-01）：在事前点时权益池 + 3 只 1/vol 的书 i-e9-4 上，TRAIN 2024 sharpe 1.34 → VAL 2025 sharpe **0.33** / obj 0.0138（FAIL 1.0 闸，低于预声明 0.5–1.2），+7.14% vs 沪深300 +17.66%（落后 10.5pp，全部在 Q3：+3.52% vs +17.90%）。VAL 0.33 ≈ TRAIN 行情外 sh 0.42 ⇒ 规则的非事件水平约 0.3–0.4，2024 的过闸靠一个行情两周。status 保持 measured **只因**它的 test 是 TRAIN 上的池内/池分句测试且已跑完——本 edge **不是前向已验证的 edge**，不得作为跨年成立的先验引用。 ‖ measured（2026-11-01，test 全部跑完');

// realizability basis — append the product's own liq run (scope comment stays: base score; product measured too).
rep('注意：零滑点台、单只 100% 持仓、09:35 入场，均为大流动 ETF"',
  '注意：零滑点台、单只 100% 持仓、09:35 入场，均为大流动 ETF。 ‖ liq-i-e9-4（e9 TRAIN 2024，产品 elhg-i-e9-4 = variants/i-e9-4.py，点时权益池 3 只）：下限 capital/3/0.05 = 6.67e6（20 日均额）⇒ 逐位相同（max|Δcum| 0）；池自身 2e7 20 日中位门槛蕴含 ≥1e7 均额，风险名字按构造惰性；国债 ≥2.82e8 ⇒ R=2 对产品同样成立（产品 VAL 已 FAIL，此分数不再门控任何事）"');

// §2 rows — append after the i-e9-2 row.
const lastRow = t.split('\n').find(l => l.startsWith('| i-e9-2 下行半方差排序 on base'));
if (!lastRow) { console.error('i-e9-2 row not found'); process.exit(3); }
const rowI4 = '| i-e9-4 点时权益池 3 只 1/vol on q-e9-3（`variants/i-e9-4.py`） | improve | i-e9-3 构造（3 只 1/vol、集合变化再平衡、20 日最短持有 + 10% 带、叠加关闭），手选 14 只池 → q-e9-4 逐日点时权益 ETF 池（逐字），国债腿不动。builder `build-i-e9-4.js`；liq `build-liq-i-e9-4.js` | research-i-e9-4 (e9) | +0.0454 vs q-e9-4 | +0.20 | +0.56 | **adopted**（VAL 候选） | 24.88 / sh 1.34 / maxDD 9.90 / obj 0.1498（vs i-e9-3 25.05 / 1.78 / 9.03）。两周 +19.35%，其余 +4.64%（rest sh 0.42）。权益持仓全为红利/银行/50；避险腿放行 59 天、国债持有 56 天（10-15..12-31，1/vol 下占 85–95%）。liq-i-e9-4（6.67e6）逐位相同。预声明 bar（≥1.0 且 ≥1.14）通过 ⇒ 送 VAL；VAL 见下行 |';
const rowVal = '| VAL elhg-i-e9-4-val（i-e9-4，VAL 2025） | understand (validate) | 无改动：i-e9-4 逐字跑 VAL 2025-01-01..2025-12-31；本族 epoch 9 唯一一次验证 | research-val-e9-i4 (e9) | VAL obj 0.0138（TRAIN 0.1498，异窗） | VAL sh 0.33（TRAIN 1.34） | 5.78 | **informative**（VAL FAIL） | +7.14% / annual 7.16 / sharpe 0.33 / maxDD 5.78 vs 300 +17.66%；分季 Q1 −1.89/−1.21、Q2 +4.05/+1.26、**Q3 +3.52/+17.90**、Q4 +1.39/−0.24 ⇒ 落后全在 Q3。8 次集合变化全为红利/低波权益 ETF，国债 0 天。低于预声明 0.5–1.2；VAL 0.33 ≈ TRAIN 行情外 0.42 ⇒ 2024 过闸靠一个两周。族 BLOCKED 终态，不再造候选。归档 `validated_strategies/elhg-i-e9-4.py`（gate_val: fail） |';
rep(lastRow + '\n', lastRow + '\n' + rowI4 + '\n' + rowVal + '\n');

// §4 — append after the pre-declared expectation bullet (the VAL decision's continuation line).
rep('**不论结果，不再构造新候选去补一次 VAL。**\n',
  '**不论结果，不再构造新候选去补一次 VAL。**\n' +
  '- **[VAL 结果，2026-11-01] FAIL，本族 epoch 9 BLOCKED 终态**：elhg-i-e9-4-val sharpe **0.33** / obj 0.0138（+7.14% vs 300 +17.66%），低于预声明区间下沿 0.5 ⇒ 按事先写下的读法：TRAIN 1.34 是 2024 防御行情 + 行情两周的水平，规则在事前池上没有跨年站住。VAL 预算已花，**不构造新候选**；新 VAL 只能由人工 `JQ_ALLOW_REVAL` 给出，且不应给。产品已归档 `validated_strategies/elhg-i-e9-4.py`（`gate_val: fail`）。\n' +
  '- **[VAL 新] 规则的非事件水平两年一致 ≈ 0.3–0.4**：TRAIN 行情外 sh 0.42、VAL 全年 0.33。2025 的落后全部在 Q3（+3.52% vs 300 +17.90%），Q1/Q2/Q4 持平或领先 ⇒ 规则在 2025 并未「失效」，它做的仍是它在 2024 行情外做的事（持平、低 beta 0.38），只是 2025 没有一个它恰好持有的行情两周。⇒ **关闭「在本规则上调参提高 TRAIN sharpe」方向**：任何 TRAIN 改进只会再拟合一个事件。\n' +
  '- **[VAL 新，仍未测] 国债避险腿**：VAL 上 0 天持有国债（8 次集合变化全为权益），与 14 只池上 TRAIN 的惰性同样是「未评价」而不是否定。\n' +
  '- **[VAL 新，供 OOS/下一台]** 若未来台换窗口重开本族，唯一值得重读的问题是「低波权益规则 + 一个尖峰后的避险退出」是否是可复现的结构（2024 的 10-15 起国债 56 天恰在行情顶部之后），而不是任何水平数字；须在数字存在前写下预期。\n');

// §5 provenance row.
rep('| 2026-10-31 | 注册。来源 `screen/qita/verdicts.json`，screener confidence high。零实验。 |\n',
  '| 2026-10-31 | 注册。来源 `screen/qita/verdicts.json`，screener confidence high。零实验。 |\n' +
  '| 2026-11-01 | /run-family 第 1 轮（e9）：understand q-e9-1..7 + liq-e9-1，improve i-e9-2（rejected）/ i-e9-3（adopted, 非 VAL 候选）/ i-e9-4（adopted, VAL 候选）。海龟叠加 refuted；低波动异象 measured（作用域：TRAIN 池内 + 点时池）；realizability 2（liq-e9-1、liq-i-e9-4）。 |\n' +
  '| 2026-11-01 | **VAL 花掉**（epoch 9 唯一一次）：elhg-i-e9-4-val on `variants/i-e9-4.py`，2025：sharpe 0.33 / obj 0.0138，FAIL。归档 `validated_strategies/elhg-i-e9-4.py`（gate_val: fail）。本族 epoch 9 BLOCKED 终态。 |\n');

fs.writeFileSync(P, t);

// ── archive ────────────────────────────────────────────────────────────────────────────────
const header = [
  '# ===== VALIDATED STRATEGY (run-family archive) — join-quant epoch 9 =====',
  '# expId:            elhg-i-e9-4',
  '# runId:            elhg-i-e9-4-val   (the VAL recorded in data/consumption.tsv by the executor; algorithmId a606becc364d9fa2c01db53c0b50317e, backtestId ccc85e48bff5fa1e06b6b35f3db108de)',
  '# ideaId:           i-e9-4  (adopted on TRAIN as the family VAL candidate; findings i-e9-4 + val-e9-i4)',
  '# family:           ETF低波海龟   (source base: strategies/2026-10-17_量化分享_ETF低波海龟法则与复利增强的验证-4a8bcfd5.py — NOT this book)',
  '# lineage:          base 4a8bcfd5 -> q-e9-3 (turtle overlay removed) -> i-e9-3 (3 lowest-vol, weights ∝ 1/vol, set-change rebalance)',
  '#                   -> i-e9-4 (hand-picked 14-ETF pool -> daily point-in-time A-share EQUITY ETF pool of q-e9-4: listed >=250d,',
  '#                   20d median money >=2e7, equity-name filter, 511/513/518 excluded; 152-294 names; bond leg 511010/511260 unchanged)',
  '# train_objective:  0.1498   (TRAIN 2024-01-01..2024-12-31: total 24.88% / annual 24.88% / maxDD 9.90% / sharpe 1.34)',
  '# val_objective:    0.0138   (VAL   2025-01-01..2025-12-31: total 7.14% / annual 7.16% / maxDD 5.78% / sharpe 0.33)',
  '# sharpe_val:       0.33',
  '# gate_val:         fail     (sharpe 0.33 < 1.0, epoch-9 stageGate(\'validate\'))',
  '# harness_epoch:    9',
  '# ranAt:            2026-11-01',
  '# val_curve:        data/series/study_ETF低波海龟_variants_i-e9-4__val__e9.json  (243 points, 2025-01-02..2025-12-31, has benchCum)',
  '# source_file:      study/ETF低波海龟/variants/i-e9-4.py — the EXACT file the VAL ran. Everything below this header',
  `#                   is byte-identical to it: sha256 ${SHA} (${body.length} bytes, verified at archive time).`,
  '# realizability:    2   (liq-i-e9-4 on THIS book: floor capital/3/0.05 = 6.67e6 20d avg money -> bit-identical, max|Δcum| 0;',
  '#                   the pool\'s own 2e7 20d-median gate implies >=1e7 mean, so the floor is inert by construction; bonds >=2.82e8)',
  '#',
  '# flags / honest caveats — carry these with any quotation of the numbers above:',
  '#   ⚠⚠ VAL FAILED. This family has NO candidate on epoch 9, and its one VAL per (family, bench) is SPENT. A new variant',
  '#      validated on 2025 would be selection on VAL; only a human JQ_ALLOW_REVAL could permit it, and none should.',
  '#   ⚠⚠ Expectation DECLARED BEFORE the number (family page §4): sharpe 0.5-1.2, likely below TRAIN; VAL < 1.0 => TRAIN 1.34',
  '#      was the level of 2024\'s defensive (dividend/bank) rally and the family is BLOCKED terminal. Result 0.33 is BELOW that range.',
  '#   ⚠  TRAIN 1.34 is mostly one fortnight: 2024-09-24..10-08 +19.35%, the rest of 2024 +4.64% (rest sharpe 0.42). VAL 0.33',
  '#      ~= that ex-event level, i.e. the rule\'s non-event level is ~0.3-0.4 in both years.',
  '#   ⚠  2025 shape vs 沪深300 (+17.66%): Q1 -1.89/-1.21, Q2 +4.05/+1.26, Q3 +3.52/+17.90, Q4 +1.39/-0.24 — the whole 10.5pp',
  '#      shortfall is Q3. Trough -5.78% on 2025-01-13, peak +12.26% on 2025-11-12. Daily corr to 300 0.56, beta 0.38.',
  '#   ⚠  VAL held only dividend/low-vol equity ETFs (8 set changes); the bond safe leg was NEVER held in 2025 — untested, not inert.',
  '#      In TRAIN it held bonds 56 days (10-15..12-31) at 85-95% weight once a bond entered a slot.',
  '#   ⚠  Pool is point-in-time (2025 listings cannot enter by construction), but the rule parameters (60d window, 20d hold,',
  '#      10% band, 0.40 median-vol switch) come from a post published 2026-09-11 — after both TRAIN and VAL.',
  '#   ⚠  The 低波动异象 edge is `measured` only for its TRAIN within-pool test; it did NOT persist into VAL. Do not cite it as',
  '#      forward-validated. QUOTE TRAIN AND VAL AS A PAIR: 0.1498 / sharpe 1.34 (2024) and 0.0138 / sharpe 0.33 (2025). Zero-slippage bench.',
  '# ================================================================================',
  '',
].join('\n');
fs.writeFileSync(SHELF, header + body.toString());
const check = fs.readFileSync(SHELF);
const tail = check.subarray(Buffer.byteLength(header));
if (crypto.createHash('sha256').update(tail).digest('hex') !== SHA) { console.error('archive body hash mismatch'); process.exit(4); }
console.log('archived', path.relative(ROOT, SHELF), 'body sha256 ok');
console.log(rq.load(F).map(e => e.id + ':' + e.status).join(' '));
