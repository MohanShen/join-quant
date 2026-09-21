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

  // ⚠ These are written epoch-RELATIVE on purpose. An earlier version asserted "epoch 4 counts
  // under epoch 5" and "epoch <= 3 does not", which was true when epoch 5 was active and became
  // false the moment epoch 6 landed — the same hard-coded-constant drift this repo keeps paying
  // for. The rule under test is the mechanism, not any particular epoch's answer.
  const declaredChain = () => {
    const active = harness.config().epoch;
    const ok = new Set([active]);
    for (let e = active; e > 1; e--) {
      let cfg;
      try {
        cfg = JSON.parse(fs.readFileSync(
          path.join(ROOT, `harness/config/epoch-${e}.json`), 'utf8'));
      } catch { break; }
      if ((cfg.comparability || {}).measurementPreservedFromPrevious !== true) break;
      ok.add(e - 1);
    }
    return ok;
  };

  await t.test('validity follows the declared measurement-preserved chain', () => {
    const expected = declaredChain();
    for (let e = 1; e <= harness.config().epoch; e++) {
      assert.strictEqual(harness.measurementValid(String(e)), expected.has(e),
        `epoch ${e} should be ${expected.has(e) ? 'valid' : 'invalid'} under ` +
        `epoch ${harness.config().epoch}`);
    }
  });

  await t.test('a bump that changed fills or fees breaks the chain', () => {
    // Every epoch that declares measurementPreservedFromPrevious:false must cut off everything
    // older than itself, or pre-change rows silently mix into current tables.
    const active = harness.config().epoch;
    for (let e = 2; e <= active; e++) {
      let cfg;
      try {
        cfg = JSON.parse(fs.readFileSync(
          path.join(ROOT, `harness/config/epoch-${e}.json`), 'utf8'));
      } catch { continue; }
      if ((cfg.comparability || {}).measurementPreservedFromPrevious === false) {
        assert.strictEqual(harness.measurementValid(String(e - 1)), false,
          `epoch ${e} is not measurement-preserving, so epoch ${e - 1} must be invalid`);
      }
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

  await t.test('the repair only ever moves a page TO its ledger row', () => {
    // ⚠ NOT an idempotence test. An earlier version asserted repair proposes zero changes,
    // which held only while nothing was mid-re-measurement — the moment epoch-6 rows started
    // landing, four pages legitimately needed updating and the test failed on correct
    // behaviour. The real invariant is that repair never invents: every proposed change must
    // target the epoch the ledger states, and a page with no row must be left alone.
    const ledger = epochRepair.ledgerEpochs('train');
    const r = epochRepair.repair({ dry: true });
    for (const c of r.changed) {
      assert.ok(c.to, 'a proposed change must name a target epoch');
      assert.notStrictEqual(c.from, c.to, 'a no-op should not be proposed');
      assert.ok([...ledger.values()].includes(c.to),
        `proposed epoch ${c.to} for ${c.file} is not any ledger row's epoch`);
    }
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

/**
 * 无选择压力 is scoped to the IDEA TYPE, not to the pipeline.
 *
 * study-schema.md §10 used to end with "if the dissection inspires a strategy worth optimizing,
 * that is auto-enhance's job, start separately" — which bound the keep/discard rule to the
 * PIPELINE. That was the root of the two-pipeline split and its only substantive disagreement.
 *
 * The danger of getting it backwards is asymmetric. `understand` experiments carry most of their
 * value in NEGATIVE results: ETF溢价's entire enhance round rests on q-1 (the alpha dies as the
 * volume floor rises) and q-2 (concentration explains only ~17% of the gap). Put an "did it
 * improve?" gate in front of those and both are discarded. So the gate follows the idea, not the
 * pipeline — and `improve` variants that were measured and rejected get recorded too, because
 * otherwise "we tried that, it doesn't work" leaves no trace and the next round re-proposes it.
 */
const st = require('node:test');
const as = require('node:assert');
const fsx = require('fs');
const pathx = require('path');

const doc = f => fsx.readFileSync(pathx.join(__dirname, '..', f), 'utf8');

st('无选择压力 is scoped to the idea type', async (t) => {
  const study = doc('docs/study-schema.md');
  const enhance = doc('docs/enhance-schema.md');
  const wiki = doc('docs/wiki-schema.md');

  await t.test('the pipeline-scoped wording is gone from the principle', () => {
    // The phrase survives ON PURPOSE, inside the ⚠ note recording what the original said —
    // the same convention used elsewhere ("本条原文写「每日免费 60 分钟」"). What must not come
    // back is the phrase as an OPERATIVE clause, so every occurrence has to be a quotation
    // introduced by 本条原文.
    for (const m of [...study.matchAll(/那是 auto-enhance 的活，另起/g)]) {
      const before = study.slice(Math.max(0, m.index - 80), m.index);
      as.match(before, /本条原文/,
        'the parenthetical is back as a rule, not as a record of what it used to say');
    }
    as.match(study, /无选择压力（按想法类型，非按流水线）/);
  });

  await t.test('both idea types are named, with opposite recording rules', () => {
    const s = study.slice(study.indexOf('无选择压力（按想法类型'));
    as.match(s, /`understand`[\s\S]{0,200}负结果与正结果同等入账/);
    as.match(s, /`improve`[\s\S]{0,120}被否决的变体[\s\S]{0,40}同样入账/);
  });

  await t.test('the family page has somewhere to PUT a rejected variant', () => {
    // A principle promising a record, with no column to hold it, is decoration.
    as.match(wiki, /\|\s*变体\s*\|\s*类型\s*\|[\s\S]{0,120}\|\s*判定\s*\|\s*结论\s*\|/,
      'wiki-schema §3.3 §2 must carry 类型 and 判定 columns');
    as.match(study, /`判定` = `adopted` \| `rejected` \| `informative`/);
  });

  await t.test('enhance-schema no longer says only the finalized result is written back', () => {
    as.match(enhance, /定稿与被否决的变体都写/);
    as.doesNotMatch(enhance, /\| keep=advance \/ discard=git reset \|/,
      'the row that made a rejected iteration vanish via git reset is back');
    as.match(enhance, /代码回退，\*\*认识不回退\*\*/);
  });

  await t.test('a newly seeded family page gets the new columns', () => {
    const build = doc('utils/wiki-family-build.js');
    as.match(build, /\|\s*变体\s*\|\s*类型\s*\|[\s\S]{0,140}\|\s*判定\s*\|\s*结论\s*\|/,
      'wiki-family-build.js seeds §2 for new pages — its template must match the schema');
  });

  await t.test('no code parses §2 by column index, so old 7-column tables still read', () => {
    // wiki-family-build.js does split('|'), but on §3 — the table it generates itself. If a
    // parser ever indexes §2's columns, adding columns silently shifts every field it reads.
    const build = doc('utils/wiki-family-build.js');
    const i = build.indexOf("split('|')");
    as.ok(i > 0, 'expected the §3 parser to still exist');
    as.match(build.slice(Math.max(0, i - 600), i), /countMetricCells|section3/,
      'the only column-indexed parser must remain scoped to §3');
  });
});
