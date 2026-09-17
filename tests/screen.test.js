/**
 * Tests for the screening rubric (screen/screen.md epoch 1).
 *
 * The formula and the hard rejects are the parts that must behave identically on every run —
 * that is what "consistent screening" means. Both encode lessons measured on this corpus, so
 * the cases below are written as those lessons rather than as abstract arithmetic.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const { priorityOf, bandOf, validateVerdict } = require('../utils/screen-score');
const { hardReject, heldFamilies, MECHANISM } = require('../utils/screen-prefilter');

const ROOT = path.join(__dirname, '..');
const ctx = { hashes: new Set(), copied: new Set() };
const ID32 = 'a'.repeat(32);
const post = (o = {}) => ({ key: 'k1', title: '小市值轮动策略', tags: [], backtestId: ID32, ...o });

test('priorityOf', async t => {
  await t.test('weights marginal information heaviest', () => {
    // same total axis points, but concentrated in M vs in S
    assert.ok(priorityOf({ M: 5, S: 1, R: 3, H: 3 }) > priorityOf({ M: 1, S: 5, R: 3, H: 3 }));
  });

  await t.test('a novel, tradeable, honest post reaches fetch-now', () => {
    const p = priorityOf({ M: 5, S: 4, R: 4, H: 5 });
    assert.strictEqual(p, 36);
    assert.strictEqual(bandOf(p), 'fetch-now');
  });

  await t.test('the realizability veto sinks an untradeable top scorer', () => {
    // the ETF-discount book: objective 3.595 on the harness, dies under mild friction
    const p = priorityOf({ M: 3, S: 5, R: 1, H: 3 });
    assert.strictEqual(p, 2);
    assert.strictEqual(bandOf(p), 'drop');
  });

  await t.test('the veto beats every other axis being maxed', () => {
    assert.strictEqual(priorityOf({ M: 5, S: 5, R: 0, H: 5 }), 2);
  });

  await t.test('the 36th variant of a held family never reaches the fetch queue', () => {
    // Nothing NEW to learn. Even maxed on every other axis it stays at `hold`:
    // weighting alone left this at 28 = fetch-now, which is why the M ladder exists.
    assert.strictEqual(bandOf(priorityOf({ M: 1, S: 5, R: 3, H: 4 })), 'hold');
    assert.strictEqual(bandOf(priorityOf({ M: 1, S: 5, R: 5, H: 5 })), 'hold');
    assert.strictEqual(priorityOf({ M: 1, S: 5, R: 5, H: 5 }), 17);
  });

  await t.test('one step of novelty above that re-opens the top band', () => {
    assert.strictEqual(bandOf(priorityOf({ M: 2, S: 5, R: 5, H: 5 })), 'fetch-now');
  });

  await t.test('M=0 caps at drop however strong the rest', () => {
    assert.strictEqual(priorityOf({ M: 0, S: 5, R: 5, H: 5 }), 3);
    assert.strictEqual(bandOf(3), 'drop');
  });

  await t.test('rejects out-of-range or non-integer axes', () => {
    assert.throws(() => priorityOf({ M: 6, S: 1, R: 1, H: 1 }), /0-5/);
    assert.throws(() => priorityOf({ M: 2.5, S: 1, R: 1, H: 1 }), /0-5/);
    assert.throws(() => priorityOf({ M: -1, S: 1, R: 1, H: 1 }), /0-5/);
  });
});

test('bandOf covers the thresholds', () => {
  assert.strictEqual(bandOf(40), 'fetch-now');
  assert.strictEqual(bandOf(28), 'fetch-now');
  assert.strictEqual(bandOf(27), 'fetch');
  assert.strictEqual(bandOf(18), 'fetch');
  assert.strictEqual(bandOf(17), 'hold');
  assert.strictEqual(bandOf(8), 'hold');
  assert.strictEqual(bandOf(7), 'drop');
  assert.strictEqual(bandOf(0), 'drop');
});

test('validateVerdict', async t => {
  const ok = { key: 'k', M: 5, S: 4, R: 4, H: 5, priority: 36, band: 'fetch-now',
               family: '小市值', mechanism: 'x', why: 'y' };

  await t.test('accepts a conforming verdict', () => {
    assert.deepStrictEqual(validateVerdict(ok), []);
  });

  await t.test('catches a priority that does not match its own axes', () => {
    assert.match(validateVerdict({ ...ok, priority: 99 })[0], /priority 99 != formula 36/);
  });

  await t.test('catches a band inconsistent with the priority', () => {
    const errs = validateVerdict({ ...ok, band: 'drop' });
    assert.ok(errs.some(e => /band "drop"/.test(e)));
  });

  await t.test('requires the narrative fields', () => {
    assert.ok(validateVerdict({ ...ok, mechanism: '' }).some(e => /missing mechanism/.test(e)));
  });
});

test('hardReject (screen.md §2)', async t => {
  await t.test('drops a post with neither backtest nor research payload', () => {
    assert.match(hardReject(post({ backtestId: '' }), ctx), /^R1/);
  });

  await t.test('keeps a research post with no backtest', () => {
    assert.strictEqual(hardReject(post({ backtestId: '', notebookPath: '/nb.ipynb' }), ctx), null);
    assert.strictEqual(hardReject(post({ backtestId: '', tags: ['研报分享'] }), ctx), null);
  });

  await t.test('drops platform API docs', () => {
    assert.match(hardReject(post({ tags: ['文章', '函数'] }), ctx), /^R4/);
  });

  await t.test('drops what is already fetched, by stable key', () => {
    assert.match(hardReject(post({ uniqueKey: 'u1' }), { ...ctx, copied: new Set(['u1']) }), /^R3/);
  });

  await t.test('drops an exact duplicate source', () => {
    assert.match(hardReject(post({ contentHash: 'h1' }), { ...ctx, hashes: new Set(['h1']) }), /^R2/);
  });

  await t.test('does NOT drop a post merely because the title looks vague', () => {
    // An earlier R5 dropped 287 of 549 strategies including 五福/三马/七星 variants — a held
    // family with 4 gate-passes. A hard reject must be a known fact, not a guess.
    for (const title of ['五福51-三状态V2版', '三马105-五福35-修复版', '大道无形我无道',
                         '低换手红利策略', '更新后的代码']) {
      assert.strictEqual(hardReject(post({ title }), ctx), null, `wrongly dropped: ${title}`);
    }
  });

  await t.test('drops only a genuinely empty title', () => {
    assert.match(hardReject(post({ title: '   ' }), ctx), /^R5/);
  });
});

test('the mechanism regex is a hint, and covers family lineages', () => {
  for (const t of ['五福51-三状态V2版', '三马105修复版', '七星ETF轮动', '低换手红利策略']) {
    assert.ok(MECHANISM.test(t), `hint missed a real mechanism: ${t}`);
  }
});

test('heldFamilies reads real member counts for axis M', () => {
  const h = heldFamilies();
  assert.ok(Object.keys(h).length >= 10, 'expected the 14 family pages');
  assert.ok(h['小市值'] > 20, 'small-cap should be the largest held family');
});

test('the frozen rubric and calibration set are present', async t => {
  await t.test('screen.md declares an epoch', () => {
    const s = fs.readFileSync(path.join(ROOT, 'screen/screen.md'), 'utf8');
    assert.match(s, /- \*\*epoch\*\*: \d+/);
  });

  await t.test('calibration posts leak no outcome', () => {
    const posts = JSON.parse(fs.readFileSync(path.join(ROOT, 'screen/calibration/posts.json'), 'utf8'));
    assert.strictEqual(posts.length, 104);
    for (const p of posts) {
      for (const leak of ['gate', 'obj', 'annual', 'sharpe']) {
        assert.ok(!(leak in p), `posts.json leaks ${leak}`);
      }
    }
  });

  await t.test('the sealed key covers every post', () => {
    const posts = JSON.parse(fs.readFileSync(path.join(ROOT, 'screen/calibration/posts.json'), 'utf8'));
    const key = JSON.parse(fs.readFileSync(path.join(ROOT, 'screen/calibration/answers.sealed.json'), 'utf8'));
    assert.strictEqual(Object.keys(key).length, posts.length);
    for (const p of posts) assert.ok(key[p.ref], `no answer for ${p.ref}`);
    const pass = Object.values(key).filter(v => v.gate === 'pass').length;
    assert.strictEqual(pass, 23, 'base rate changed — the reference numbers no longer apply');
  });
});
