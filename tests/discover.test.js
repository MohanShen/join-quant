/**
 * Tests for the discovery classifier and the jq-http geo-block guard.
 *
 * These cover the two bugs that silently broke Pipeline 1:
 *   1. a geo-block HTML page being read as an empty result set, and
 *   2. the post filter discarding every notebook / attachment / research post.
 * Both are pure functions, so nothing here touches the network.
 */

const test = require('node:test');
const assert = require('node:assert');

const { isStrategyPost, isResourcePost, resourceKind } = require('../utils/strategy-discover');
const { isGeoBlocked } = require('../utils/jq-http');

const ID32 = 'a'.repeat(32);
const tagsOf = post => (post.tagInfo || []).map(t => t.name);
const post = (over = {}) => ({ postId: 'p1', title: 't', backtestId: '', tagInfo: [], ...over });
const tag = name => ({ tagKey: '1', name });

test('isStrategyPost', async t => {
  await t.test('accepts a post with a 32-char backtestId', () => {
    const p = post({ backtestId: ID32, tagInfo: [tag('策略')] });
    assert.strictEqual(isStrategyPost(p, tagsOf(p)), true);
  });

  await t.test('rejects a post with no backtest', () => {
    const p = post({ tagInfo: [tag('策略')] });
    assert.strictEqual(isStrategyPost(p, tagsOf(p)), false);
  });

  await t.test('rejects a truncated backtestId', () => {
    const p = post({ backtestId: 'abc123' });
    assert.strictEqual(isStrategyPost(p, tagsOf(p)), false);
  });

  await t.test('rejects the 文章+函数 junk combination', () => {
    const p = post({ backtestId: ID32, tagInfo: [tag('文章'), tag('函数')] });
    assert.strictEqual(isStrategyPost(p, tagsOf(p)), false);
  });
});

test('isResourcePost', async t => {
  await t.test('keeps a shared research notebook', () => {
    const p = post({ notebookPath: '/user/x/nb.ipynb', notebookCloneCount: '12' });
    assert.strictEqual(isResourcePost(p, tagsOf(p)), true);
    assert.strictEqual(resourceKind(p, tagsOf(p)), 'notebook');
  });

  await t.test('keeps a file attachment', () => {
    const p = post({ fileKey: 'k', fileName: 'report.pdf', fileType: 'pdf' });
    assert.strictEqual(isResourcePost(p, tagsOf(p)), true);
    assert.strictEqual(resourceKind(p, tagsOf(p)), 'file');
  });

  await t.test('keeps 研报分享, which the old filter dropped outright', () => {
    const p = post({ tagInfo: [tag('研报分享')] });
    assert.strictEqual(isResourcePost(p, tagsOf(p)), true);
    assert.strictEqual(resourceKind(p, tagsOf(p)), 'research-report');
  });

  await t.test('keeps 研报复现', () => {
    const p = post({ tagInfo: [tag('研报复现')] });
    assert.strictEqual(resourceKind(p, tagsOf(p)), 'research-replication');
  });

  await t.test('reports every kind a post satisfies', () => {
    const p = post({ notebookPath: '/nb', fileKey: 'k', tagInfo: [tag('研报分享')] });
    assert.strictEqual(resourceKind(p, tagsOf(p)), 'notebook+file+research-report');
  });

  await t.test('ignores an ordinary strategy post with no research payload', () => {
    const p = post({ backtestId: ID32, tagInfo: [tag('策略'), tag('选股')] });
    assert.strictEqual(isResourcePost(p, tagsOf(p)), false);
  });

  await t.test('still rejects junk even when it carries a notebook', () => {
    const p = post({ notebookPath: '/nb', tagInfo: [tag('文章'), tag('函数')] });
    assert.strictEqual(isResourcePost(p, tagsOf(p)), false);
  });
});

test('a post can be both a strategy and a resource', () => {
  const p = post({ backtestId: ID32, notebookPath: '/nb', tagInfo: [tag('策略')] });
  assert.strictEqual(isStrategyPost(p, tagsOf(p)), true);
  assert.strictEqual(isResourcePost(p, tagsOf(p)), true);
});

test('isGeoBlocked', async t => {
  await t.test('detects the region interstitial', () => {
    assert.strictEqual(isGeoBlocked('<title>当前地区暂不支持访问</title>'), true);
  });

  await t.test('passes ordinary JSON through', () => {
    assert.strictEqual(isGeoBlocked('{"data":{"list":[]}}'), false);
  });

  await t.test('tolerates a non-string body', () => {
    assert.strictEqual(isGeoBlocked(null), false);
    assert.strictEqual(isGeoBlocked(undefined), false);
  });
});

// ── Stable post identity ─────────────────────────────────────────────────────
// JoinQuant re-mints postId/backtestId on every request; only uniqueKey is
// stable. These guard the keying that keeps the stores from growing duplicates.

const { postKey, legacyKey, upsert } = require('../utils/strategy-discover');

test('postKey', async t => {
  await t.test('prefers uniqueKey when present', () => {
    assert.strictEqual(postKey({ uniqueKey: 'u1', postId: 'p1', title: 't' }), 'u1');
  });

  await t.test('ignores a changing postId', () => {
    const a = postKey({ uniqueKey: 'u1', postId: 'AAA', title: 't' });
    const b = postKey({ uniqueKey: 'u1', postId: 'BBB', title: 't' });
    assert.strictEqual(a, b);
  });

  await t.test('falls back to a deterministic title+author digest', () => {
    const a = postKey({ title: 'x', author: 'bob', postId: 'AAA' });
    const b = postKey({ title: 'x', author: 'bob', postId: 'BBB' });
    assert.strictEqual(a, b);
    assert.match(a, /^lk_[0-9a-f]{30}$/);
  });

  await t.test('separates same title by different authors', () => {
    assert.notStrictEqual(
      postKey({ title: 'x', author: 'bob' }),
      postKey({ title: 'x', author: 'ada' })
    );
  });

  await t.test('reads the author out of a raw listV2 row', () => {
    assert.strictEqual(
      postKey({ title: 'x', user: { name: 'bob' } }),
      postKey({ title: 'x', author: 'bob' })
    );
  });
});

test('upsert', async t => {
  await t.test('adds a new row once', () => {
    const m = {};
    assert.strictEqual(upsert(m, { uniqueKey: 'u1', title: 't' }), true);
    assert.strictEqual(upsert(m, { uniqueKey: 'u1', title: 't' }), false);
    assert.strictEqual(Object.keys(m).length, 1);
  });

  await t.test('does not re-add the same post under a fresh postId', () => {
    const m = {};
    upsert(m, { uniqueKey: 'u1', postId: 'AAA', title: 't' });
    upsert(m, { uniqueKey: 'u1', postId: 'BBB', title: 't' });
    assert.strictEqual(Object.keys(m).length, 1);
  });

  await t.test('upgrades a legacy title+author row to its real uniqueKey', () => {
    const legacy = { title: 't', author: 'bob' };
    const m = { [legacyKey(legacy)]: legacy };
    const fresh = { uniqueKey: 'u1', title: 't', author: 'bob' };
    assert.strictEqual(upsert(m, fresh), true);
    assert.deepStrictEqual(Object.keys(m), ['u1']);   // legacy row retired, not duplicated
  });

  await t.test('leaves unrelated legacy rows alone', () => {
    const other = { title: 'other', author: 'ada' };
    const m = { [legacyKey(other)]: other };
    upsert(m, { uniqueKey: 'u1', title: 't', author: 'bob' });
    assert.strictEqual(Object.keys(m).length, 2);
  });
});

/**
 * 问答 (cate=10) deferral in the strategy queue.
 *
 * Why this exists: on 2026-11-03 all 20 of that day's fetches were cate=10 help-desk posts
 * ("新手求救，交易无法正常执行", "布林带代码问题", "获取数据缺失") and the normalizer spent
 * real backtest minutes measuring them. A help-desk post ATTACHES a backtest in order to ask
 * about it, so no payload rule catches it.
 *
 * The rule must stay a DEFERRAL: Q&A yielded the O'Neil pocket-pivot idea, so the row stays in
 * the store and an explicit screening verdict overrides.
 */
const { applyVerdicts, QA_CATE } = require('../utils/strategy-discover');
const fsQA = require('node:fs');

// An unscreened item: a uniqueKey that cannot collide with a real screen/verdicts.json entry.
let qaSeq = 0;
const unscreened = (over = {}) => ({
  postId: 'qa' + (++qaSeq),
  uniqueKey: 'test-unscreened-key-' + qaSeq + '-' + Math.random().toString(36).slice(2),
  title: 't' + qaSeq,
  _score: 1,
  ...over,
});

test('QA_CATE is 10 — 问答, the help-desk tab', () => {
  assert.strictEqual(QA_CATE, 10);
});

test('unscreened cate=10 is kept out of the STRATEGY queue', () => {
  const items = [unscreened({ cate: 10 }), unscreened({ cate: 3 }), unscreened({ cate: 14 })];
  const r = applyVerdicts(items, { deferQA: true });
  assert.strictEqual(r.deferredQA, 1, 'the one cate=10 post is deferred');
  assert.strictEqual(r.ordered.length, 2, 'only the 文章 and 精华 posts remain queued');
  assert.ok(!r.ordered.some(i => Number(i.cate) === 10), 'no cate=10 survives in the queue');
});

test('the deferral is OPT-IN — the RESOURCE queue keeps its Q&A', () => {
  // cate=10 is where debunking and pitfall discussion lives, and resources cost no backtest
  // minutes. Defaulting this on would strip the most useful material from the one queue
  // that wants it.
  const items = [unscreened({ cate: 10 }), unscreened({ cate: 3 })];
  const r = applyVerdicts(items);                       // no options = the resource path
  assert.strictEqual(r.deferredQA, 0, 'nothing is deferred without deferQA');
  assert.strictEqual(r.ordered.length, 2, 'the Q&A post stays queued');
});

test('an unknown or missing cate is NEVER deferred', () => {
  // A guess-based reject already cost this repo 287 of 549 strategies. Unknown must pass.
  const items = [unscreened({}), unscreened({ cate: null }), unscreened({ cate: undefined })];
  const r = applyVerdicts(items, { deferQA: true });
  assert.strictEqual(r.deferredQA, 0);
  assert.strictEqual(r.ordered.length, 3, 'every unknown-cate post stays queued');
});

test('a screening verdict OVERRIDES the cate rule (structural)', () => {
  // The cate check must sit INSIDE the no-verdict branch, so a screener's fetch-now/fetch
  // judgement on a Q&A post still reaches the queue. Asserted on the source because the
  // verdicts come from a file on disk.
  const src = fsQA.readFileSync(require.resolve('../utils/strategy-discover'), 'utf8');
  const fn = src.slice(src.indexOf('function applyVerdicts'));
  const body = fn.slice(0, fn.indexOf('\n}'));
  const noVerdict = body.indexOf('if (!verdict)');
  const qaCheck = body.indexOf('QA_CATE');
  const bandCheck = body.indexOf("verdict.band === 'fetch-now'");
  assert.ok(noVerdict >= 0 && qaCheck >= 0 && bandCheck >= 0, 'all three branches present');
  assert.ok(qaCheck > noVerdict && qaCheck < bandCheck,
    'the cate=10 check lives inside the no-verdict branch, before the band check');
});

test('only buildCopyQueue opts in; buildResourceQueue must not', () => {
  const src = fsQA.readFileSync(require.resolve('../utils/strategy-discover'), 'utf8');
  const copy = src.slice(src.indexOf('function buildCopyQueue'));
  const resource = src.slice(src.indexOf('function buildResourceQueue'));
  assert.ok(/applyVerdicts\(deduped,\s*\{\s*deferQA:\s*true/.test(copy.slice(0, copy.indexOf('\n}'))),
    'buildCopyQueue passes deferQA: true');
  assert.ok(!/deferQA/.test(resource.slice(0, resource.indexOf('\n}'))),
    'buildResourceQueue never passes deferQA — Q&A is the point of the resource layer');
});

test('the deferral is reported, never silent', () => {
  // A silent hold recreates the invisible-stranding failure this repo has hit repeatedly.
  const src = fsQA.readFileSync(require.resolve('../utils/strategy-discover'), 'utf8');
  assert.ok(/deferredQA > 0/.test(src) && /问答 deferred/.test(src),
    'buildCopyQueue logs the deferred count');
});
