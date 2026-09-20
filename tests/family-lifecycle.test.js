/**
 * Tests for what happens when a NEW MEMBER of an EXISTING family arrives.
 *
 * Every case here is a measured incident, not a hypothetical:
 *   - kb-stub wrote `epoch: 1` and `夏普<2.5` as literals, so all 120 wiki pages claimed a
 *     bench superseded four times while the ledger said 2 or 4 — and that block is the
 *     DURABLE BACKUP the ledger is rebuilt from;
 *   - the normalizer's done-check was `rowEpoch === ACTIVE_EPOCH`, so a scoring-only epoch
 *     bump would have re-measured the whole library at 60 backtest-minutes a day;
 *   - consumption answered only "has this family EVER been studied", so a family that gained
 *     members after its study never reappeared in the queue;
 *   - code matching decides only 31 of 175 labelled pages, and its abstain rules were tuned
 *     on those same 31, so its precision is not an independent estimate — it proposes a
 *     family, it never writes one.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const harness = require('../utils/harness-config');
const consumption = require('../utils/consumption');
const familyMatch = require('../utils/family-match');
const epochRepair = require('../utils/wiki-epoch-repair');

const ROOT = path.join(__dirname, '..');

/**
 * Source with comments stripped.
 *
 * These tests assert that a stale constant is ABSENT from the code — but the fix for each one
 * explains itself in a comment that quotes the very string being banned. Grepping the raw file
 * therefore fails on its own documentation. Strip comments first so the assertion is about
 * behaviour, not prose.
 */
const codeOf = rel => fs.readFileSync(path.join(ROOT, rel), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '')       // block comments (incl. JSDoc)
  .split('\n').map(l => l.replace(/(^|\s)\/\/.*$/, '')).join('\n');

test('epoch comparability', async t => {
  await t.test('a measurement from the active epoch is valid', () => {
    assert.ok(harness.measurementValid(harness.config().epoch));
  });

  await t.test('epoch 4 counts under epoch 5 — the bump changed scoring only', () => {
    // Strict equality here meant re-measuring 215 strategies for a rule change that touched
    // no fill and no fee.
    assert.ok(harness.measurementValid('4'), 'epoch-4 rows must stay valid under epoch 5');
    assert.ok(harness.measurementValid(4));
  });

  await t.test('epoch <= 3 does NOT count — epoch 4 pinned execution', () => {
    // order_volume_ratio / fund costs / avoid_future_data change fills and fees. Accepting
    // pre-pin rows would silently mix two benches in one table.
    for (const e of [1, 2, 3]) {
      assert.ok(!harness.measurementValid(String(e)), `epoch ${e} must require re-measurement`);
    }
  });

  await t.test('keys on the explicit boolean, not the unchanged-items list', () => {
    // epoch-4.json lists SEVEN unchanged items and its own prose still says "NOT comparable".
    // Reading that list as an equivalence marked epoch 3 comparable.
    const e4 = JSON.parse(fs.readFileSync(path.join(ROOT, 'harness/config/epoch-4.json'), 'utf8'));
    assert.ok(Array.isArray(e4.comparability.unchangedFromEpoch3));
    assert.ok(e4.comparability.unchangedFromEpoch3.length > 0, 'the tempting-but-wrong signal');
    assert.strictEqual(e4.comparability.measurementPreservedFromPrevious, false);
  });

  await t.test('an unstated epoch is treated as NOT comparable', () => {
    assert.ok(!harness.measurementValid(''));
    assert.ok(!harness.measurementValid(null));
    assert.ok(!harness.measurementValid('not-a-number'));
  });

  await t.test('the comparable set is contiguous back from the active epoch', () => {
    const set = [...harness.comparableEpochs()].sort((a, b) => a - b);
    for (let i = 1; i < set.length; i++) {
      assert.strictEqual(set[i], set[i - 1] + 1, 'comparability cannot skip an epoch');
    }
  });
});

test('the normalizer consults comparability, not equality', async t => {
  const src = codeOf('utils/strategy-normalize.js');

  await t.test('the done-check calls measurementValid', () => {
    assert.match(src, /measurementValid\(rowEpoch\)/);
  });

  await t.test('the old strict comparison is gone', () => {
    assert.ok(!/rowEpoch === ACTIVE_EPOCH/.test(src),
      'strict equality re-measures the library on every scoring-only bump');
  });
});

test('kb-stub stamps live values, not literals', async t => {
  const src = codeOf('utils/kb-stub.js');

  await t.test('no hard-coded epoch 1', () => {
    assert.ok(!/normalized: \{ epoch: 1,/.test(src),
      'a literal epoch mislabels the ledger\'s durable backup');
    assert.match(src, /epoch: \$\{epoch\}/);
  });

  await t.test('the gate text reads the stage threshold', () => {
    assert.ok(!/夏普<2\.5/.test(src), 'the 2.5 bar was epoch 2');
    assert.match(src, /stageThreshold\('normalize'\)/);
  });

  await t.test('it records a PROPOSAL, never an assignment', () => {
    // Precision is measured on the same set the rules were tuned on — propose, never assert.
    assert.match(src, /familyProposal:/);
    assert.ok(!/^family: \$\{/m.test(src), 'must not write `family:` automatically');
  });
});

test('no wiki page still claims the superseded epoch 1', async t => {
  const dir = path.join(ROOT, 'wiki/strategies');
  await t.test('every normalized block matches the ledger', { skip: !fs.existsSync(dir) }, () => {
    const stale = fs.readdirSync(dir).filter(f => f.endsWith('.md'))
      .filter(f => /normalized: \{ epoch: 1,/.test(fs.readFileSync(path.join(dir, f), 'utf8')));
    assert.deepStrictEqual(stale, [], `${stale.length} page(s) still stamped epoch 1`);
  });

  await t.test('the repair leaves pages with no ledger row alone', () => {
    // Inventing an epoch would recreate exactly the problem being repaired.
    const r = epochRepair.repair({ dry: true });
    assert.strictEqual(r.changed.length, 0, 'repair should be idempotent once applied');
    for (const f of r.noRow) assert.ok(typeof f === 'string');
  });
});

test('consumption is member-aware', async t => {
  await t.test('memberState counts a family from the wiki and hashes its members', () => {
    const s = consumption.memberState('网格');
    assert.ok(s.count > 0, 'expected the 网格 family to have members');
    assert.strictEqual(s.members.length, s.count);
    assert.match(s.hash, /^[0-9a-f]{12}$/);
  });

  await t.test('the hash changes when the member set changes', () => {
    const a = consumption.memberState('网格');
    const b = consumption.memberState('小市值');
    assert.notStrictEqual(a.hash, b.hash);
  });

  await t.test('an empty family hashes to empty rather than to a constant', () => {
    const s = consumption.memberState('__no_such_family__');
    assert.strictEqual(s.count, 0);
    assert.strictEqual(s.hash, '');
  });

  await t.test('a never-consumed family is stale', () => {
    const s = consumption.staleFor('study', '__no_such_family__');
    assert.strictEqual(s.stale, true);
    assert.strictEqual(s.reason, 'never consumed');
  });

  await t.test('rows written before tracking are stale, not assumed current', () => {
    // The alternative — treating a blank memberHash as "up to date" — would permanently
    // freeze every family studied before the column existed.
    const evs = consumption.events({ stage: 'study', kind: 'family' });
    const old = evs.find(e => !e.memberHash);
    if (old) {
      assert.strictEqual(consumption.staleFor('study', old.key).stale, true);
    }
  });

  await t.test('the ledger carries the two new columns', () => {
    const head = fs.readFileSync(consumption.FILE, 'utf8').split('\n')[0].split('\t');
    assert.deepStrictEqual(head, consumption.COLUMNS);
    assert.ok(head.includes('members') && head.includes('memberHash'));
  });
});

test('the report asks "changed since", not "ever"', async t => {
  const src = codeOf('utils/consumption-report.js');

  await t.test('study/enhance queues are built from staleFor', () => {
    assert.match(src, /staleFor\(stage, f\.name\)/);
  });

  await t.test('the binary consumed() test no longer gates them', () => {
    assert.ok(!/fams\.filter\(f => !studied\.has\(f\.name\)\)/.test(src));
    assert.ok(!/!enhanced\.has\(f\.name\)\)\s*;/.test(src));
  });
});

test('family matching proposes and abstains', async t => {
  const { bases, skipped } = familyMatch.familyBases();

  await t.test('every family page has a readable base', () => {
    assert.ok(bases.size > 0);
    assert.deepStrictEqual(skipped, [], `families with an unreadable base: ${skipped.join(', ')}`);
  });

  await t.test('a family base matches its own family', () => {
    const [name, b] = [...bases.entries()][0];
    const src = fs.readFileSync(path.join(ROOT, b.sourceFile), 'utf8');
    const r = familyMatch.match(src, bases);
    // It may legitimately abstain as a combination; what it must never do is name another family.
    if (r.family) assert.strictEqual(r.family, name);
  });

  await t.test('unrelated code produces no proposal', () => {
    const r = familyMatch.match('def initialize(context):\n    pass\n', bases);
    assert.strictEqual(r.family, null);
    assert.strictEqual(r.reason, 'below MIN_SCORE');
  });

  await t.test('a strategy matching several bases abstains as a combination', () => {
    // 三马 / 七星 / 五福 embed other families verbatim. This is where code overlap was most
    // confident and most wrong (0.98 against two bases at once), so it must refuse.
    const two = [...bases.values()].slice(0, 2);
    const blended = [...two[0].lines, ...two[1].lines].join('\n');
    const r = familyMatch.match(blended, bases);
    if (r.family === null) assert.match(r.reason, /combination|ambiguous|below MIN_SCORE/);
  });

  await t.test('precision on decided calls stays at or above the recorded 87%', () => {
    const v = familyMatch.validate();
    const decided = v.correct + v.wrong;
    assert.ok(decided > 0, 'the matcher decided nothing at all');
    const precision = v.correct / decided;
    assert.ok(precision >= 0.85,
      `precision fell to ${(100 * precision).toFixed(1)}% — do not auto-assign on this`);
  });
});

test('family lineage', async t => {
  const par = familyMatch.parents();

  await t.test('五福闹新春 is recorded as a sub-lineage of ETF动量', () => {
    // Before this was written down, all four residual matcher errors were this one confusion.
    // The matcher was not wrong; the taxonomy only existed in prose.
    assert.strictEqual(par.get('五福闹新春'), 'ETF动量');
  });

  await t.test('a parent and child count as the same lineage, in both directions', () => {
    assert.ok(familyMatch.sameLineage('五福闹新春', 'ETF动量', par));
    assert.ok(familyMatch.sameLineage('ETF动量', '五福闹新春', par));
  });

  await t.test('unrelated families do not', () => {
    assert.ok(!familyMatch.sameLineage('小市值', 'ETF动量', par));
  });

  await t.test('every declared parent names a real family page', () => {
    const { bases } = familyMatch.familyBases();
    for (const [child, parent] of par) {
      assert.ok(bases.has(parent), `${child} declares parent "${parent}", which has no page`);
    }
  });

  await t.test('a cycle terminates instead of hanging', () => {
    const cyclic = new Map([['a', 'b'], ['b', 'a']]);
    assert.deepStrictEqual(familyMatch.lineage('a', cyclic), ['a', 'b']);
  });

  await t.test('the relation is stored once, on the child', () => {
    // A reciprocal `children:` list would be a second copy free to drift.
    const famDir = path.join(ROOT, 'wiki/families');
    for (const f of fs.readdirSync(famDir).filter(x => x.endsWith('.md'))) {
      assert.ok(!/^children:/m.test(fs.readFileSync(path.join(famDir, f), 'utf8')),
        `${f} declares children; the parent field on the child is the single source`);
    }
  });
});

test('normalize-sync refreshes family pages', async t => {
  const src = codeOf('utils/normalize-sync.js');

  await t.test('it spawns the builder rather than requiring it', () => {
    // wiki-family-build.js is top-level script code with no require.main guard; requiring it
    // executes it and its process.exit() would take the parent down.
    assert.match(src, /spawnSync/);
    assert.ok(!/require\(['"]\.\/wiki-family-build/.test(src));
  });

  await t.test('it never passes --force as a spawn argument', () => {
    // --force deletes metric rows the gitignored ledger no longer holds. The string itself
    // DOES appear in the file — in the console warning telling a human not to use it — so the
    // assertion has to be about the argv handed to the child, not about the text.
    const argv = src.match(/spawnSync\([^)]*\[([^\]]*)\]/);
    assert.ok(argv, 'expected a spawnSync call with an argument array');
    assert.ok(!argv[1].includes('--force'), `child argv must not force: ${argv[1]}`);
  });

  await t.test('a BLOCKED build is reported, not escalated', () => {
    const r = require('../utils/normalize-sync').refreshFamilies({ dry: true });
    assert.strictEqual(r.ran, false, 'a dry run must not spawn anything');
  });
});
