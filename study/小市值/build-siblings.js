// Builds units-FIXED copies of the two 低开剥头皮 siblings that share the base's 100x tick-unit
// error (q-e6-19's bounded re-measure list).
//
// ## Why a builder and not an edit
//
// `strategies/` is the immutable raw layer — CLAUDE.md forbids modifying it, and for a good
// reason: the ledger's rows are claims about what the AUTHOR wrote. Fixing the source in place
// would silently change what every past row refers to. So the fix is a derived artifact, exactly
// as `q-13_fix-bid-units` was for the base.
//
// ## The bug, and why the edit is one line
//
// `get_current_tick`'s `a1_v`/`b1_v` is in SHARES; all three books multiply by 100 as if it were
// LOTS, so the advertised gate 「买一档金额 > 5万」 really means `money > 500` and rejects almost
// nothing. Corroborated by two unrelated authors in the same corpus who compute depth money with
// no `*100` (`61c9c428.py:568`, `c18c86c5.py:1206`).
//
// ⚠ The two siblings read the **ask** side (`a1_*`) while the base reads the **bid** (`b1_p`/`b1_v`
// behind variables still named `a1_*`). Opposite directions; the `*100` is on both. The fix does
// not change which side is read — that would be a second change, and one experiment changes one
// thing.
//
// ## What each output is for
//
//   <id>-ctl.py   the book as written, at the ACTIVE epoch. The control. Needed because the only
//                 existing rows for these two are epoch 2, which epoch 8 does not accept — so a
//                 corrected number would otherwise have nothing comparable to sit beside.
//   <id>-fix.py   the same book with the units corrected.
//
// Both carry `OVERRIDE` (the frozen pins), or `strategy-post-backtest.js` refuses with
// UNPINNED-STOP — it does not inject them.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const OUT = path.join(__dirname, 'variants');

/** Exactly-one-match edit, borrowed from build-e6.js: a silent 0 or 2 would invalidate the result. */
function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

const NOTE = '  # fix: a1_v/b1_v is quoted in SHARES, so the hundred-fold scaling was wrong (q-e6-13/19)\n';

const SIBLINGS = {
  // §3 #2, epoch-2 objective 1.2810. Line 212, 8-space indent, bare names.
  'q-e8-1_8dbd994c': {
    src: 'strategies/2026-06-04_一个年化180_逻辑奇怪但是却有效的小市值-8dbd994c.py',
    fix: s => edit(s,
      '        money = a1_p * a1_v * 100\n',
      '        money = a1_p * a1_v' + NOTE),
  },
  // §3 #5, epoch-2 objective 0.9411. Line 123, 12-space indent, dict access.
  'q-e8-2_5e874b5b': {
    src: 'strategies/2026-06-21_低开小市值_年化105_最大回撤20-5e874b5b.py',
    fix: s => edit(s,
      "            money = tick['a1_p'] * tick['a1_v'] * 100\n",
      "            money = tick['a1_p'] * tick['a1_v']" + NOTE),
  },
};

fs.mkdirSync(OUT, { recursive: true });
const built = [];
for (const [id, spec] of Object.entries(SIBLINGS)) {
  const raw = py2to3(fs.readFileSync(path.join(ROOT, spec.src), 'utf8'));
  const fixed = spec.fix(raw);
  if (fixed === raw) throw new Error(`${id}: the fix changed nothing`);
  // ⚠ Assert the scaling is really gone from the money line, not merely that the string replaced —
  // a mis-anchored edit could leave a second occurrence behind.
  // ⚠⚠ Test the CODE side of the line only. The first version of this guard matched its own
  // explanatory comment ("the *100 was a 100x overstatement") and refused a correct build — a
  // check that reads prose as code is worse than no check, because it fails on the right answer.
  const stray = fixed.split('\n')
    .map(l => l.split('#')[0])
    .filter(l => /money\s*=.*\*\s*100\b/.test(l));
  if (stray.length) throw new Error(`${id}: a *100 money line survives: ${stray.join(' | ')}`);
  fs.writeFileSync(path.join(OUT, `${id}-ctl.py`), raw + OVERRIDE);
  fs.writeFileSync(path.join(OUT, `${id}-fix.py`), fixed + OVERRIDE);
  built.push(id);
}
console.log('built control + fixed for:', built.join(', '));
console.log('out:', path.relative(ROOT, OUT));
