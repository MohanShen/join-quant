/**
 * The universe round's queue.
 *
 * Two rules it must get right, both learned the hard way:
 *
 *  - a pair of families with the SAME edge is not an integration. 小盘's two families carry
 *    `规模因子` and `规模` — one mechanism spelled two ways — and composing them would report a
 *    diversification gain as if it were new alpha.
 *  - every universe delivers. One with no admissible pair promotes its best family instead of
 *    going silent (user's rule, 2026-10-07) — but NOT if that best family loses money. 固定篮子's
 *    best is 三进兵 at objective -0.09, and "promote the best" must not become "ship the least
 *    bad loser".
 */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

function famDir(pages) {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'iq-'));
  for (const [name, p] of Object.entries(pages)) {
    fs.writeFileSync(path.join(d, name + '.md'),
      `---\nfamily: ${name}\nuniverse: ${p.u}\nbestObjective: ${p.obj}\nmemberCount: 1\n` +
      `realism: "${p.realism || ''}"\n` +
      `edge:\n  - name: ${p.edge}\n    status: ${p.status}\n---\n\n# ${name}\n`);
  }
  return d;
}

function queueFor(pages) {
  const d = famDir(pages);
  const prev = process.env.JQ_FAMILIES_DIR;
  process.env.JQ_FAMILIES_DIR = d;
  delete require.cache[require.resolve('../utils/integrate-queue')];
  const q = require('../utils/integrate-queue');
  const rows = q.build();
  if (prev === undefined) delete process.env.JQ_FAMILIES_DIR; else process.env.JQ_FAMILIES_DIR = prev;
  return rows;
}

test('the universe round queue', async (t) => {
  const q = require('../utils/integrate-queue');

  await t.test('one edge spelled two ways is refused', () => {
    assert.ok(q.sameEdge('规模', '规模因子'), 'substring containment is the 小盘 case');
    assert.ok(q.sameEdge('动量', '动量'));
    assert.ok(!q.sameEdge('均值回归', '流动性溢价'));
    assert.ok(!q.sameEdge(null, '动量'), 'a missing edge is not a match');
  });

  await t.test('only MEASURED edges are admissible', () => {
    const rows = queueFor({
      A: { u: 'U', obj: 1, edge: 'alpha', status: 'measured' },
      B: { u: 'U', obj: 1, edge: 'beta',  status: 'refuted'  },
      C: { u: 'U', obj: 1, edge: 'gamma', status: 'proposed' },
    });
    const u = rows.find(r => r.universe === 'U');
    assert.strictEqual(u.pairs.length, 0, 'refuted and proposed edges cannot be composed');
    assert.strictEqual(u.action, 'promote');
  });

  await t.test('same-edge families promote instead of composing', () => {
    const rows = queueFor({
      A: { u: 'U', obj: 0.5, edge: '规模',     status: 'measured' },
      B: { u: 'U', obj: 1.4, edge: '规模因子', status: 'measured' },
    });
    const u = rows.find(r => r.universe === 'U');
    assert.strictEqual(u.pairs.length, 0);
    assert.strictEqual(u.refused.length, 1, 'the refusal must be reported, not silently dropped');
    assert.strictEqual(u.action, 'promote');
    assert.strictEqual(u.promote.family, 'B', 'the stronger objective is promoted');
  });

  await t.test('distinct edges compose', () => {
    const rows = queueFor({
      A: { u: 'U', obj: 1, edge: '均值回归',   status: 'measured' },
      B: { u: 'U', obj: 1, edge: '流动性溢价', status: 'measured' },
      C: { u: 'U', obj: 1, edge: '动量',       status: 'measured' },
    });
    const u = rows.find(r => r.universe === 'U');
    assert.strictEqual(u.pairs.length, 3, 'three distinct edges give three pairs');
    assert.strictEqual(u.action, 'compose');
  });

  await t.test('a losing best family is BLOCKED, never promoted', () => {
    // The whole point of the floor: objective = annual - maxdd, so negative means the drawdown
    // exceeded the return. Shipping that is not delivering.
    const rows = queueFor({ A: { u: 'U', obj: -0.09, edge: '趋势择时', status: 'measured' } });
    const u = rows.find(r => r.universe === 'U');
    assert.strictEqual(u.action, 'blocked');
    assert.strictEqual(u.promote, null);
    assert.match(u.why, /every family is either negative or declares its own headline unrealizable/);
  });

  await t.test('a singleton with a positive champion still delivers', () => {
    const rows = queueFor({ A: { u: 'U', obj: 0.46, edge: 'x', status: 'measured' } });
    const u = rows.find(r => r.universe === 'U');
    assert.strictEqual(u.action, 'promote');
    assert.strictEqual(u.promote.family, 'A');
  });
});

test('the type-level VAL budget is separate from the family one', async (t) => {
  const v = require('../utils/val-budget');

  await t.test('it is keyed per universe, and per epoch', () => {
    // One shot per (universe, epoch): composing five conjunctions and validating each until one
    // passes is selection on VAL one level up, which is the leak the family rule exists to stop.
    const src = fs.readFileSync(path.join(__dirname, '../utils/val-budget.js'), 'utf8');
    assert.match(src, /function priorValidations\(key, kind = 'family'\)/);
    assert.match(src, /kind === 'type' \? path\.resolve\(__dirname, '\.\.\/wiki\/types'\)/,
      'a type key must be checked against wiki/types, not wiki/families');
    assert.match(src, /TERMINAL for that universe/, 'the terminal rule must be stated where it is enforced');
  });

  await t.test('an unknown universe is refused rather than waved through', () => {
    const r = v.check('no-such-universe', { kind: 'type' });
    assert.strictEqual(r.allowed, false);
    assert.strictEqual(r.reason, 'unknown-type');
  });
});

test('promotion inherits the realizability discipline', async (t) => {
  await t.test('a family that declares its own headline unrealizable is not shipped', () => {
    // The ETF universe's top two both open their realism with 「⚠⚠ 头条不可实现，且已定量」.
    // Promotion SHIPS a family as the universe's answer, so it must apply the same discipline
    // integration applies at rule 4 — otherwise the round delivers a book its own page says
    // cannot be traded (PT多策略, objective 3.5952, VAL sharpe 12.82).
    const rows = queueFor({
      // same edge on both, so the pair is refused and PROMOTION is what is under test here
      Rich: { u: 'U', obj: 3.59, edge: '折价', status: 'measured',
              realism: '⚠⚠ 头条不可实现，且已定量：收益来自集合竞价成交价' },
      Modest: { u: 'U', obj: 0.68, edge: '折价', status: 'measured', realism: '⚠ 零滑点台，滑点折价小' },
    });
    const u = rows.find(r => r.universe === 'U');
    assert.strictEqual(u.action, 'promote');
    assert.strictEqual(u.promote.family, 'Modest', 'the richer book declares itself untradeable');
    assert.ok(u.skipped.some(k => k.family === 'Rich' && /unrealizable/.test(k.why)),
      'and the skip must be REPORTED — silently passing over the top family hides the finding');
  });

  await t.test('a universe where everything is unrealizable delivers nothing', () => {
    const rows = queueFor({
      A: { u: 'U', obj: 3.59, edge: '折价', status: 'measured', realism: '⚠⚠ 头条不可实现' },
      B: { u: 'U', obj: 1.56, edge: '折价', status: 'measured', realism: '⚠⚠ 头条不可实现' },
    });
    const u = rows.find(r => r.universe === 'U');
    assert.strictEqual(u.action, 'blocked');
    assert.match(u.why, /declares its own headline unrealizable/);
  });

  await t.test('a missing realism block does not block a promotion', () => {
    // The check reads one phrase out of human prose. Absence is not evidence of unrealizability.
    const rows = queueFor({ A: { u: 'U', obj: 1.0, edge: 'a', status: 'measured' } });
    assert.strictEqual(rows.find(r => r.universe === 'U').action, 'promote');
  });
});

test('a gatekeeper refusal is durable', async (t) => {
  const q = require('../utils/integrate-queue');

  await t.test('it demands a reason, not just a verdict', () => {
    assert.throws(() => q.refuse('U', 'A', 'B', 'no'), /reason of its own/,
      'the next round must be able to read WHY, or it pays for the decision again');
    assert.throws(() => q.refuse('U', 'A', '', 'a perfectly good long reason here'));
  });

  await t.test('the pair is unordered — (A,B) and (B,A) are one fact', () => {
    const src = fs.readFileSync(path.join(__dirname, '../utils/integrate-queue.js'), 'utf8');
    assert.match(src, /\[a, b\]\.sort\(\)/);
  });

  await t.test('refused pairs leave the queue but stay visible', () => {
    const src = fs.readFileSync(path.join(__dirname, '../utils/integrate-queue.js'), 'utf8');
    assert.match(src, /refused\.push\(\{ \.\.\.entry, why: gk\.why, gatekeeper: true \}\)/,
      'a gatekeeper refusal must be reported with its reason, not dropped');
  });
});
