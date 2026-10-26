// q-e9-champ-dbl — ABLATION of the MACD 顶背离 risk overlay on the 小市值 family's epoch-9
// champion `strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py`
// (control: objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00, 365 days).
//
// ## What is being tested
//
// `detect_divergence` (L592) carries ~6 undeclared free parameters on a 12-month TRAIN:
// MACD 12/26/9, the `macd < -0.03` 死叉 threshold, the "≥2 死叉 points" comparison, the
// 10-vs-20-day DIF trend test, and the 4-day suspension window at L263. It acts through TWO
// paths and ONE ablation closes both:
//
//   L366  `if detect_divergence(MARKET_INDEX, context):`  -> the 9:00 `dapan` liquidation of
//         every non-limit-up holding
//   L263  `if True in g.dbl[-4:]:`                        -> suspension of that week's rebalance
//
// ## Insertion site — ONE line, an INSERT
//
// `return False` becomes the first STATEMENT of `detect_divergence`, immediately after its
// docstring (which ends at L599) and before the anchor line below:
//
//   L600  `    fast, slow, sign = 12, 26, 9  # MACD参数`
//
// Consequences, all verified against the source rather than assumed:
//   * `detect_divergence` has exactly ONE call site (L366 — the `def` line is the only other
//     textual match), so the insert cannot leak into a second behaviour;
//   * `g.dbl` has exactly ONE reader (L263), and `dapan`'s else branch (L380
//     `g.dbl.append(False)`) still runs every day, so the list stays POPULATED with all-False and
//     L263 keeps being EVALUATED — the suspension path is disabled, not deleted;
//   * the whole MACD body below the insert is kept verbatim (dead, not removed), so the diff
//     against py2to3(raw) is a single added line.
//
// ## Firing counts came FREE, from an earlier run's log — no instrumentation added
//
// `dapan` logs both branches on every trading day (L368 WARNING 「⚠️ 检测到大盘顶背离信号…」,
// L381 INFO 「未检测到大盘顶背离，市场趋势正常」) and L264 logs the suspension. `detect_divergence`
// is called ONLY on `MARKET_INDEX` ('399101.XSHE', L28) and reads ONLY that index's closes, so its
// firing DATES are path-independent: they are identical in the control and in any variant that
// leaves the detector intact.
// Read off the stored bbi-off run (backtestId 6f429b1a21be9e9e9534306d5fc74557, 6,947 log lines,
// paged at limit=2000 — one fetch returns only 100 lines, so the loop must page to exhaustion):
//   fired 1 (2024-12-17 09:00) | not fired 241 | rebalance suspended 1 (2024-12-17 10:45)
//   | 「因大盘顶背离清仓」 2 positions
// So the overlay fires ONCE in 2024, inside the December that supplies 28.1% of the year's
// log-growth. The variant's own log is the positive control: it must show 242 「未检测到」 and 0
// 「检测到大盘顶背离信号」, which is how we tell "disabled" from "never reached".
//
// ⚠ This is NOT the 2-name concentration experiment (rank 32) and must not be merged with it;
// q-e6-18's lesson is that two deltas on this book do not add.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;

const TAG = 'dbl-off';

// Line-exact, both directions. Matching whole lines (never substrings) is what keeps the undo
// assertion below a real check rather than a tautology.
const ANCHOR = '    fast, slow, sign = 12, 26, 9  # MACD参数';
const INSERT = '    return False  # q-e9-champ-dbl: 顶背离机器整体停用 (ablation) — ONLY change vs the raw book';

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /0a7de9fa/.test(f));
if (!src) throw new Error('0a7de9fa not found in strategies/');

// ⚠ The comparison baseline is py2to3(raw), NOT the on-disk file: the variant is built on the
// py2to3 output, which is also what the normalizer measured the control on.
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));
const lines = raw.split('\n');

if (lines.filter(l => l === ANCHOR).length !== 1) {
  throw new Error('expected exactly 1 anchor line for the insert — refusing');
}
if (lines.includes(INSERT)) throw new Error('the insert line is already present — refusing');

// The structural facts the design rests on. Each is checked, not assumed: if any has moved, the
// one-line insert no longer closes both paths and the experiment would be uninterpretable.
const DEF = 'def detect_divergence(stock, context):';
const DOCEND = 599; // 1-based: the closing `"""` of detect_divergence's docstring
const facts = {
  'def line': lines.filter(l => l === DEF).length === 1,
  'one call site': lines.filter(l => /detect_divergence\(/.test(l)).length === 2, // def + L366
  'call site is dapan L366': lines.filter(l => l === '    if detect_divergence(MARKET_INDEX, context):').length === 1,
  'one g.dbl reader': lines.filter(l => l === '    if True in g.dbl[-4:]:').length === 1,
  'else branch appends False': lines.filter(l => l === '        g.dbl.append(False)').length === 1,
  'docstring closes just above the anchor': lines[DOCEND - 1] === '    """'
    && lines[DOCEND] === ANCHOR,
  'detector reads only MARKET_INDEX': lines.filter(l => /detect_divergence\(/.test(l) && !l.startsWith('def'))
    .every(l => l.includes('MARKET_INDEX')),
};
for (const [k, ok] of Object.entries(facts)) {
  if (!ok) throw new Error(`structural precondition failed: ${k} — refusing`);
}

// The three log lines the firing counts are read from must survive, or the run cannot be read.
const LOGS = [
  '        log.warning("⚠️ 检测到大盘顶背离信号（价格新高但MACD走弱），清仓非涨停股票")',
  '        log.info("未检测到大盘顶背离，市场趋势正常")',
  '        log.info("近5日检测到大盘顶背离，暂停调仓以控制风险")',
];

const body = lines
  .flatMap(l => (l === ANCHOR ? [INSERT, l] : [l]))
  .join('\n');

if (!body.includes(INSERT)) throw new Error('the insert did not land');
if (body.split('\n').length !== lines.length + 1) throw new Error('the edit changed more than one line — refusing');
if (!body.includes(ANCHOR)) throw new Error('the MACD body was removed rather than bypassed — refusing');
for (const need of LOGS) {
  if (!body.includes(need)) throw new Error(`missing log line needed to count firings: ${need.trim()}`);
}

// ⚠⚠ The ONLY difference from py2to3(raw) must be the inserted line. Assert on `body` — the
// PRE-OVERRIDE text — never on a slice of the final file: cutting the output at a marker is
// ambiguous against the file's own trailing newlines (the false "line 840 of an 839-line file").
const undone = body.split('\n').filter(l => l !== INSERT).join('\n');
if (undone !== raw) {
  const a = undone.split('\n'), b = lines;
  const first = a.findIndex((l, i) => l !== b[i]);
  throw new Error('undoing the edit does not reproduce py2to3(raw) byte-for-byte '
                + `(first difference at line ${first + 1} of ${b.length}) — refusing`);
}

const out = body + OVERRIDE;
const file = path.join(OUT, `variants/0a7de9fa-${TAG}.py`);
fs.writeFileSync(file, out);

console.log(`[dbl] built variants/0a7de9fa-${TAG}.py  (epoch ${harness.config().epoch})`);
console.log(`[dbl] ONE insert at L${DOCEND + 1}: ${INSERT.trim()}`);
console.log('[dbl] verified: 1 call site (L366), 1 g.dbl reader (L263), else-branch append(False) '
          + 'intact => both paths disabled, both still evaluated');
console.log('[dbl] undo reproduces py2to3(raw) byte-for-byte (pre-OVERRIDE comparison)');
console.log("[dbl] control = the champion's own epoch-9 row: objective 2.6282 / sharpe 7.07 / "
          + 'annual 276.82 / maxDD 14.00 (Jan-Nov objective 1.6888)');
console.log('[dbl] PRE-REGISTERED: hypothesis |Δobjective| < 0.3; falsifier |Δ| > 0.3 or gate '
          + 'fail (<1.0) => the champion is substantially a TIMING book; |Δ| < 0.05 => the overlay '
          + 'is inert and the stripped book is strictly simpler (~6 fewer DoF)');
console.log('[dbl] free prior from the bbi-off log: the overlay fired ONCE in 2024 (12-17), '
          + 'suspended ONE rebalance, liquidated 2 positions');
