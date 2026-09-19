/**
 * Tests for the consolidation pieces (docs/consolidation-plan.md §1–§4).
 *
 * Each case is written as the lesson that produced it, because every one of these came from a
 * bug measured in this repo rather than from an abstract requirement.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const { universeOf, horizonOf, typeKey } = require('../utils/wiki-type-build');
const { check, NOISE_PP } = require('../utils/type-integrate-check');
const { lint, TOLERANCE } = require('../utils/wiki-concept-lint');
const consumption = require('../utils/consumption');

// ── type axes ────────────────────────────────────────────────────────────────

test('universeOf', async t => {
  await t.test('a defensive bond sleeve does not make an ETF book a bond fund', () => {
    // The first implementation was priority-ordered first-match, so one 511880 money-market
    // line relabelled four ETF/hybrid families as 债券.
    const src = `
      etf_pool = ['510300.XSHG','159915.XSHE']
      unit_net_value = get_extras('unit_net_value', etf_pool)
      # 空仓时买入 511880 货币ETF 做防守
      g.bond = '511880.XSHG'`;
    assert.strictEqual(universeOf(src), 'ETF');
  });

  await t.test('a benchmark is not a universe', () => {
    // set_benchmark('000300') appears in nearly every strategy and was enough to make two
    // pure ETF-discount books look like large-cap hybrids.
    const src = `
      set_benchmark('000300.XSHG')
      run_daily(f, reference_security='000300.XSHG')
      etf_pool = get_all_securities(['etf'])
      df = get_extras('unit_net_value', etf_pool)
      premium = unit_net_value`;
    assert.strictEqual(universeOf(src), 'ETF');
  });

  await t.test('calls a genuinely two-sleeve book 混合', () => {
    const src = ('q = query(valuation.code).order_by(valuation.market_cap.asc())\n最小市值\n微盘\n399101\n'
               + 'unit_net_value\netf_pool\nunit_net_value\netf_pool\nunit_net_value');
    assert.strictEqual(universeOf(src), '混合');
  });

  await t.test('never calls 微盘 + 小盘 a hybrid — same market, different cut', () => {
    const src = '最小市值\n微盘\n399101\n小市值\nsmall_cap\n中证1000';
    assert.notStrictEqual(universeOf(src), '混合');
  });

  await t.test('falls back to 全A when the evidence is too thin to name', () => {
    assert.strictEqual(universeOf('def initialize(context): pass'), '全A');
  });
});

test('horizonOf buckets measured turnover', () => {
  assert.strictEqual(horizonOf(0.0078), 'H-low');    // 三进兵, the lowest measured
  assert.strictEqual(horizonOf(0.09), 'H-mid');
  assert.strictEqual(horizonOf(0.3061), 'H-high');   // 打板短线, the highest measured
  assert.strictEqual(horizonOf(null), 'H-unknown');
  assert.strictEqual(typeKey({ universe: 'ETF', horizon: 'H-mid' }), 'ETF-H-mid');
});

// ── the integration guard ────────────────────────────────────────────────────

const member = (o) => ({ family: 'f', annual: 50, sharpe: 2.6, maxdd: 12, objective: 0.38,
                         realizability: 3, ...o });

test('type integration guard', async t => {
  await t.test('rejects a blend that does not beat its best member', () => {
    // The 七星高照 worked example: it clears the gate at 0.4814 while its small-cap leg
    // alone scores 0.5984. Passing the gate is necessary and meaningless.
    const r = check({
      weights: 'equal',
      candidate: { annual: 56.67, sharpe: 3.17, maxdd: 8.53, objective: 0.4814 },
      members: [member({ family: '小市值腿', annual: 70, sharpe: 2.85, objective: 0.5984, realizability: 2 }),
                member({ family: 'ETF轮动腿', annual: 34, sharpe: 1.60, objective: null, realizability: 4 })],
    });
    assert.strictEqual(r.verdict, 'reject');
    assert.ok(r.reasons.some(x => /does not beat the best member/.test(x)));
  });

  await t.test('flags the diversification signature: sharpe up, return not up', () => {
    const r = check({
      weights: 'equal',
      candidate: { annual: 49, sharpe: 3.4, maxdd: 8, objective: 0.60 },
      members: [member({ annual: 50, sharpe: 2.6, objective: 0.38 }),
                member({ annual: 45, sharpe: 2.4, objective: 0.33 })],
    });
    assert.ok(r.flags.includes('diversification-explained'));
    assert.strictEqual(r.verdict, 'keep-with-caveat');
  });

  await t.test('keeps a blend that raises BOTH return and objective', () => {
    const r = check({
      weights: 'equal',
      candidate: { annual: 62, sharpe: 3.0, maxdd: 10, objective: 0.52 },
      members: [member({ annual: 50, sharpe: 2.6, objective: 0.38 }),
                member({ annual: 45, sharpe: 2.4, objective: 0.33 })],
    });
    assert.strictEqual(r.verdict, 'keep');
    assert.ok(!r.flags.includes('diversification-explained'));
  });

  await t.test('rejects optimised weights that beat equal weight by less than noise', () => {
    const r = check({
      weights: { a: 0.7, b: 0.3 }, equalWeightObjective: 0.519,
      candidate: { annual: 62, sharpe: 3.0, maxdd: 10, objective: 0.52 },
      members: [member({ annual: 50, objective: 0.38 }), member({ annual: 45, objective: 0.33 })],
    });
    assert.strictEqual(r.verdict, 'reject');
    assert.ok(r.reasons.some(x => x.includes(`${NOISE_PP}pp`)));
  });

  await t.test('rejects optimised weights submitted with no equal-weight baseline', () => {
    const r = check({
      weights: { a: 0.7, b: 0.3 },
      candidate: { annual: 62, sharpe: 3.0, maxdd: 10, objective: 0.52 },
      members: [member({ objective: 0.38 }), member({ objective: 0.33 })],
    });
    assert.strictEqual(r.verdict, 'reject');
  });

  await t.test('inherits the WORST member realizability, not the average', () => {
    const r = check({
      weights: 'equal',
      candidate: { annual: 62, sharpe: 3.0, maxdd: 10, objective: 0.52 },
      members: [member({ objective: 0.38, realizability: 5 }),
                member({ objective: 0.33, realizability: 1 })],   // an untradeable leg
    });
    assert.strictEqual(r.verdict, 'reject');
    assert.ok(r.flags.includes('realizability=1'));
  });

  await t.test('needs at least two members to be an integration at all', () => {
    assert.strictEqual(check({ candidate: {}, members: [member({})] }).verdict, 'invalid');
  });
});

// ── consumption ledger ───────────────────────────────────────────────────────

test('consumption ledger', async t => {
  await t.test('rejects an unknown kind or stage rather than writing junk', () => {
    assert.throws(() => consumption.record({ key: 'k', kind: 'nope', stage: 'study' }), /unknown kind/);
    assert.throws(() => consumption.record({ key: 'k', kind: 'family', stage: 'nope' }), /unknown stage/);
    assert.throws(() => consumption.record({ kind: 'family', stage: 'study' }), /key is required/);
  });

  await t.test('is seeded and exposes the stages the loops read', () => {
    const stages = new Set(consumption.events().map(e => e.stage));
    assert.ok(stages.has('normalize'), 'normalize events missing');
    assert.ok(stages.has('study'), 'study events missing');
    assert.ok(stages.has('enhance'), 'enhance events missing');
  });

  await t.test('enhance events are keyed by FAMILY, not by session tag', () => {
    // The seed first keyed them 'jul12', which answered nothing: the ledger exists to say
    // whether a FAMILY has been enhanced.
    const keys = consumption.events({ stage: 'enhance' }).map(e => e.key);
    assert.ok(keys.includes('小市值'), `expected 小市值 among enhance keys, got ${keys.join(',')}`);
    assert.ok(!keys.includes('jul12'), 'session tag leaked back in as a key');
  });

  await t.test('consumed() answers the "already done" question as a set', () => {
    assert.ok(consumption.consumed('study', 'family').size >= 14);
  });
});

// ── concept lint ─────────────────────────────────────────────────────────────

test('concept lint', async t => {
  const rows = lint();

  await t.test('covers every concept page', () => {
    const n = fs.readdirSync(path.join(ROOT, 'wiki/concepts')).filter(f => f.endsWith('.md')).length;
    assert.strictEqual(rows.length, n);
  });

  await t.test('computes drift and keeps a tolerance', () => {
    assert.ok(TOLERANCE > 0 && TOLERANCE < 1);
    for (const r of rows) {
      assert.ok(Number.isFinite(r.drift) && r.drift >= 0, `${r.name} drift is not a number`);
      assert.ok(Number.isInteger(r.actual));
    }
  });

  await t.test('reports rather than silently rewriting', () => {
    // The count also appears in page prose, so a silent frontmatter fix would leave the page
    // contradicting itself. lint() must be pure.
    const before = fs.readFileSync(path.join(ROOT, 'wiki/concepts/仓位管理.md'), 'utf8');
    lint();
    assert.strictEqual(fs.readFileSync(path.join(ROOT, 'wiki/concepts/仓位管理.md'), 'utf8'), before);
  });
});

// ── type pages ───────────────────────────────────────────────────────────────

test('generated type pages', async t => {
  const dir = path.join(ROOT, 'wiki/types');

  await t.test('exist and are generated, not hand-written', { skip: !fs.existsSync(dir) }, () => {
    const files = fs.readdirSync(dir).filter(f => f.endsWith('.md'));
    assert.ok(files.length >= 2);
    for (const f of files) {
      const t2 = fs.readFileSync(path.join(dir, f), 'utf8');
      assert.match(t2, /generatedBy: utils\/wiki-type-build\.js/);
      assert.match(t2, /^families: \[/m);
    }
  });

  await t.test('place every family in exactly one cell, and no cell holds them all', { skip: !fs.existsSync(dir) }, () => {
    const seen = [];
    for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.md'))) {
      const line = (fs.readFileSync(path.join(dir, f), 'utf8').match(/^families: \[(.*)\]$/m) || [])[1] || '';
      for (const m of line.matchAll(/\[\[([^\]]+)\]\]/g)) seen.push(m[1]);
    }
    const famCount = fs.readdirSync(path.join(ROOT, 'wiki/families')).filter(f => f.endsWith('.md')).length;
    assert.strictEqual(seen.length, famCount, 'a family is missing or double-counted');
    assert.strictEqual(new Set(seen).size, seen.length, 'a family appears in two cells');
    const biggest = Math.max(...fs.readdirSync(dir).filter(f => f.endsWith('.md')).map(f =>
      ((fs.readFileSync(path.join(dir, f), 'utf8').match(/^familyCount: (\d+)$/m) || [])[1] | 0)));
    assert.ok(biggest < famCount, 'one cell holds every family — the axes separate nothing');
  });
});
