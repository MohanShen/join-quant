// q-e9-champ-emptymonth — ATTRIBUTION ablation of the CALENDAR FLAT rule (`g.pass_april`) on the
// 小市值 family's NEW epoch-9 champion
// `strategies/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa.py`
// (control: objective 3.0172 / sharpe 8.22 / annual 320.35 / maxDD 18.63, 365 days, curve on disk).
//
// ## What is being measured
//
// The author (posting in 2026) wrote a rule that sits out 01-01..01-30 and 04-01..04-30. 2024-01 is
// exactly the month the four pre-2024-posted members of this family lost -16%..-22% (the microcap
// stampede), while all three top books earn exactly 0.00% that month and then take a +34-35%
// February rebound. This variant turns the rule OFF to price that dated, non-repeating hindsight
// quantum inside the book's own name selection.
//
// ⚠ Structurally this can only ever measure DOWNWARD and NO outcome opens an improve: the book
// already sits on the "skip January" side, and 2024-01 is a single dated event. Same class as
// q-e9-champ-dbl — report as n=1, never as risk control.
//
// ## Insertion site — ONE whole line
//
//   L42  `    g.pass_april = True  # 是否四月空仓`  ->  `... = False ...`
//
// `today_is_between` (L540-548) returns False UNCONDITIONALLY when the flag is False, so this one
// line disables BOTH windows. Nothing else moves: `close_account`, `close_no_trading_hold`,
// `weekly_adjustment` and `g.no_trading_buy` keep their code paths and are still evaluated — the
// flat-month machine simply always answers False.
//
// ## ⚠⚠ ONE flip moves TWO hindsight channels — the monthly table is mandatory
//
//  (1) 2024-01 is TRUE CASH on the control (0.00%), and only as an artifact of the window's start:
//      `close_account` requires `len(g.hold_list) != 0` and the backtest opens 2024-01-02 with no
//      holdings, so the defensive basket is never bought that month.
//  (2) 2024-04 is NOT cash — it is a 2026 HAND-PICKED three-name defensive basket
//      `g.no_trading_buy = ['600036.XSHG','518880.XSHG','600900.XSHG']` (L61), worth +5.64% on the
//      control.
// So "calendar flat" is really "January cash + April hand-picked basket", two different hindsight
// surfaces, and Delta objective is their sum. Only the monthly table separates them.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;

const TAG = 'emptymonth';

// Line-exact, both directions. Matching whole lines (never substrings) is what keeps the undo
// assertion below a real check rather than a tautology.
const SITE = '    g.pass_april = True  # 是否四月空仓';
const EDITED = '    g.pass_april = False  # q-e9-champ-emptymonth: 日历空仓关闭（归因）— 相对原书的唯一改动';

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /02fdafaa/.test(f));
if (!src) throw new Error('02fdafaa not found in strategies/');

// ⚠ The comparison baseline is py2to3(raw), NOT the on-disk file: the variant is built on the
// py2to3 output, which is also what the normalizer measured the control on.
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));
const lines = raw.split('\n');

const hits = lines.filter(l => l === SITE).length;
if (hits !== 1) throw new Error(`expected exactly 1 edit site, got ${hits}`);

// The flat-month MACHINE must survive verbatim — the design is "let it evaluate and always answer
// False", not "remove it". Each of these is named in the queue entry's design block.
// ⚠ Guard on the CODE side of a line only: two builders in this family have already refused a
// CORRECT build by matching their own explanatory comment (build-siblings' stray-`*100`,
// build-universe's MARKET_INDEX count). These four anchors are code, and `codeOf` strips any
// trailing `#` comment before counting.
const codeOf = (l) => {
  const i = l.indexOf('#');
  return (i === -1 ? l : l.slice(0, i)).trimEnd();
};
const ANCHORS = [
  "    g.no_trading_buy = ['600036.XSHG','518880.XSHG','600900.XSHG']",
  'def today_is_between(context):',
  'def close_account(context):',
  'def close_no_trading_hold(context):',
  '        close_no_trading_hold(context)',
];
for (const a of ANCHORS) {
  const n = lines.filter(l => codeOf(l) === a).length;
  if (n !== 1) throw new Error(`anchor not where the design says it is (${n} matches): ${a}`);
}
// The unconditional-False branch is the whole reason ONE line suffices.
if (!raw.includes('    if g.pass_april is True:')) {
  throw new Error('today_is_between no longer gates on `g.pass_april is True` — refusing');
}

const body = lines.map(l => (l === SITE ? EDITED : l)).join('\n');

if (!body.includes(EDITED)) throw new Error('the edit did not land');
if (body.split('\n').some(l => codeOf(l) === '    g.pass_april = True')) {
  throw new Error('a `g.pass_april = True` assignment survived the edit — refusing');
}
for (const a of ANCHORS) {
  if (!body.split('\n').some(l => codeOf(l) === a)) throw new Error(`anchor lost in the edit: ${a}`);
}

// ⚠⚠ The ONLY difference from py2to3(raw) must be the swapped line. Assert on `body` — the
// PRE-OVERRIDE text — never on a slice of the final file: cutting the output at a marker is
// ambiguous against the file's own trailing newlines, and that is exactly what made
// build-liq-5a70adc1 report a false "first difference at line 840" of an 839-line file.
const undone = body.split('\n').map(l => (l === EDITED ? SITE : l)).join('\n');
if (undone !== raw) {
  const a = undone.split('\n'), b = raw.split('\n');
  const first = a.findIndex((l, i) => l !== b[i]);
  throw new Error('undoing the edit does not reproduce py2to3(raw) byte-for-byte '
                + `(first difference at line ${first + 1} of ${b.length}) — refusing`);
}

const out = body + OVERRIDE;
const file = path.join(OUT, `variants/02fdafaa-${TAG}.py`);
fs.writeFileSync(file, out);

console.log(`[emptymonth] built variants/02fdafaa-${TAG}.py  (epoch ${harness.config().epoch})`);
console.log(`[emptymonth] ONE edit: L${lines.indexOf(SITE) + 1}  ${SITE.trim()}  ->  g.pass_april = False`);
console.log('[emptymonth] kept verbatim: today_is_between / close_account / close_no_trading_hold / '
          + 'its weekly_adjustment call / g.no_trading_buy (the basket)');
console.log('[emptymonth] undo reproduces py2to3(raw) byte-for-byte (pre-OVERRIDE comparison)');
console.log('[emptymonth] control = the NEW champion\'s epoch-9 row: objective 3.0172 / sharpe 8.22 / '
          + 'annual 320.35 / maxDD 18.63 (maxDD window 2024-05-07 -> 2024-06-24)');
console.log('[emptymonth] PRIMARY PRE-REGISTERED FALSIFIER is the VARIANT\'S 2024-01 RETURN r_jan: '
          + 'r_jan >= 0 holds / -10% < r_jan < 0 partial / r_jan <= -10% REFUTED. '
          + 'Secondary: Delta objective <= -0.5 => refuted. Point estimate -0.75..-0.85.');
console.log('[emptymonth] ⚠ NO outcome opens an improve — 2024-01 is a dated non-repeating event; '
          + 'report as n=1, never as risk control.');
