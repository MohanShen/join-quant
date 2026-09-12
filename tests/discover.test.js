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
