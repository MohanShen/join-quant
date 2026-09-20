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

// ── versioned harness config (epoch 3) ───────────────────────────────────────
// The windows used to live in seven files and the cost line in four, and they had already
// drifted. These guard the single source of truth.

const harness = require('../utils/harness-config');

test('harness config', async t => {
  await t.test('an epoch is active and self-consistent', () => {
    const c = harness.config();
    assert.strictEqual(c.status, 'active');
    assert.ok(Number.isInteger(c.epoch) && c.epoch >= 3);
  });

  await t.test('windows do not overlap and run in order', () => {
    const tr = harness.window('train'), va = harness.window('val'), ho = harness.window('holdout');
    assert.ok(tr.end < va.start, 'train must end before val starts');
    assert.ok(va.end < ho.start, 'val must end before the reserve starts');
  });

  await t.test('epoch 3 extends val to two years and moves the reserve', () => {
    assert.strictEqual(harness.window('val').start, '2024-01-01');
    assert.strictEqual(harness.window('val').end, '2025-12-31');
    assert.strictEqual(harness.oosCutoff(), '2026-01-01');
  });

  await t.test('train is unchanged, so epoch-2 TRAIN results stay comparable', () => {
    assert.strictEqual(harness.window('train').start, '2022-01-01');
    assert.strictEqual(harness.window('train').end, '2023-12-31');
  });

  await t.test('the rolling end resolves to a real date, not the literal "today"', () => {
    assert.match(harness.window('holdout').end, /^\d{4}-\d{2}-\d{2}$/);
  });

  await t.test('unknown window names return null rather than a silent default', () => {
    assert.strictEqual(harness.window('nope'), null);
  });

  await t.test('gate and objective reproduce rows already in the ledger', () => {
    // 高质量稳定上涨策略: annual 56.98, maxdd 9.61, sharpe 3.21
    assert.strictEqual(harness.objective(56.98, 9.61, 3.21), 0.4737);
    assert.strictEqual(harness.gate(3.21), true);
  });

  await t.test('epoch 5 keeps the score when the gate fails', () => {
    // 网格交易策略, sharpe 1.19: used to be erased to DQ, which threw away the difference
    // between a near-miss and a disaster and left five families with no number at all.
    assert.strictEqual(harness.objective(33.79, 19.68, 1.19), 0.1411);
    assert.strictEqual(harness.gate(1.19), false);
  });

  await t.test('the gate is 1.5 and still rejects unusable input', () => {
    assert.strictEqual(harness.gate(1.5), true);
    assert.strictEqual(harness.gate(1.49), false);
    assert.strictEqual(harness.gate('not a number'), false);
  });

  await t.test('integration holds a higher bar than the other stages', () => {
    assert.strictEqual(harness.stageThreshold('study'), 1.5);
    assert.strictEqual(harness.stageThreshold('integrate'), 2.0);
    assert.strictEqual(harness.stageGate('integrate', 1.8), false);
    assert.strictEqual(harness.stageGate('study', 1.8), true);
  });

  await t.test('the Python literals still match — they cannot read the JSON', () => {
    // strategy_template.py and the injected OVERRIDE execute on JoinQuant's servers, so they
    // must stay literal. This is the only thing keeping them honest.
    assert.deepStrictEqual(harness.verify(), []);
  });

  await t.test('the previous epoch is kept, so old results stay attached to their rules', () => {
    const prev = JSON.parse(fs.readFileSync(path.join(ROOT, 'harness/config/epoch-2.json'), 'utf8'));
    assert.strictEqual(prev.status, 'historical');
    assert.strictEqual(prev.windows.val.end, '2024-12-31');
  });

  await t.test('the OOS budget tightened with the shorter reserve', () => {
    const prev = JSON.parse(fs.readFileSync(path.join(ROOT, 'harness/config/epoch-2.json'), 'utf8'));
    assert.ok(harness.config().oosPolicy.maxTestsPerEpoch < prev.oosPolicy.maxTestsPerEpoch);
  });
});

test('epoch 4 execution pins (carried into epoch 5)', async t => {
  const lit = harness.pythonLiterals();

  await t.test('the config declares all three pins', () => {
    const c = harness.config().costs;
    assert.strictEqual(c.orderVolumeRatio, 0.05);
    assert.strictEqual(c.avoidFutureData, true);
    assert.ok(c.fundOrderCost, 'fund order cost missing');
  });

  await t.test('literals are generated for each pin', () => {
    assert.match(lit.orderVolumeRatio, /order_volume_ratio', 0\.05/);
    assert.match(lit.avoidFutureData, /avoid_future_data', True/);
    assert.match(lit.fundOrderCost, /type='fund'/);
  });

  await t.test('both frozen Python blocks carry them', () => {
    assert.deepStrictEqual(harness.verify(), []);
  });

  await t.test('the fund-cost rebinding is guarded — unguarded it broke every strategy', () => {
    // set_order_cost is not bound at module scope in every JQ runtime; rebinding it without a
    // guard raised NameError at import and the strategy came back compile-error.
    const src = fs.readFileSync(path.join(ROOT, 'utils/strategy-normalize.js'), 'utf8');
    const i = src.indexOf('__jq_set_order_cost = set_order_cost');
    assert.ok(i > 0, 'fund-cost rebinding not found');
    assert.ok(src.lastIndexOf('try:', i) > src.lastIndexOf('def ', i) - 500,
      'the rebinding must sit inside a try/except NameError');
  });

  await t.test('the ledger records which epoch measured each row', () => {
    const head = fs.readFileSync(path.join(ROOT, 'harness/normalize-train.tsv'), 'utf8').split('\n')[0];
    assert.ok(head.split('\t').includes('epoch'), 'ledger has no epoch column');
  });

  await t.test('superseded epochs are sealed and comparability is stated', () => {
    for (const n of [2, 3, 4]) {
      const e = JSON.parse(fs.readFileSync(path.join(ROOT, `harness/config/epoch-${n}.json`), 'utf8'));
      assert.strictEqual(e.status, 'historical', `epoch ${n} is not sealed`);
    }
    // Epoch 5 changed only SCORING, so epoch-4 measurements stay valid; epoch<=3 do not.
    assert.match(harness.config().comparability.trainResultsFromEarlierEpochs, /not comparable/i);
  });
});

test('the integration round is not silently erased', async t => {
  const fsx = require('fs');
  const pathx = require('path');
  const R = pathx.join(__dirname, '..');

  await t.test('wiki-type-build carries the 整合回合 section across a regenerate', () => {
    // That section is APPENDED by the round and exists nowhere else on the page. The builder
    // used to overwrite unconditionally, so the next `node utils/wiki-type-build.js` would
    // have deleted a measured integration result — the same class of loss wiki-family-build
    // guards against for §3 metrics.
    const src = fsx.readFileSync(pathx.join(R, 'utils/wiki-type-build.js'), 'utf8');
    assert.match(src, /ROUND_HEADING/);
    assert.match(src, /ROUND_PLACEHOLDER/);
    assert.ok(!/fs\.writeFileSync\(path\.join\(TYPE_DIR, `\$\{k\}\.md`\), render\(k, g\)\);/.test(src),
      'unconditional overwrite would discard recorded rounds');
  });

  await t.test('a recorded round survives on disk', () => {
    const p = pathx.join(R, 'wiki/types/全A-H-low.md');
    if (!fsx.existsSync(p)) return;
    const t2 = fsx.readFileSync(p, 'utf8');
    if (t2.includes('int-001')) {
      assert.ok(!t2.includes('本节由整合回合追加；当前无记录'),
        'a page with a recorded round must not also carry the empty placeholder');
    }
  });
});

test('compile-error detection ignores the editor’s own source', async t => {
  const fsx = require('fs');
  const pathx = require('path');
  const src = fsx.readFileSync(
    pathx.join(__dirname, '..', 'utils/strategy-post-backtest.js'), 'utf8');

  await t.test('the scan strips the Ace editor before matching', () => {
    // Measured incident: the frozen cost block uses `try/except NameError` (set_order_cost is
    // not bound at module scope in every JQ runtime — CLAUDE.md). Ace renders that text into
    // document.body.innerText, the detector matched its own strategy's source, and a healthy
    // backtest was killed ~40s in and reported as compile-error.
    assert.match(src, /cloneNode\(true\)/);
    assert.match(src, /ace_editor/);
  });

  await t.test('it no longer reads the raw body', () => {
    const fn = src.slice(src.indexOf('async function detectCompileError'));
    const body = fn.slice(0, fn.indexOf('\n}'));
    assert.ok(!/document\.body\.innerText\s*\)\s*\.match/.test(body),
      'matching raw body text re-introduces the false positive');
  });
});

test('factorlib is wired as a hypothesis source, with the bench boundary enforced', async t => {
  const fsx = require('fs');
  const pathx = require('path');
  const R = pathx.join(__dirname, '..');
  const fl = require('../utils/factorlib-query');

  await t.test('the snapshot loads and carries its own provenance', () => {
    const rows = fl.load();
    assert.ok(rows.length > 100, `expected the 285-factor snapshot, got ${rows.length}`);
    const p = fl.provenance();
    assert.ok(p.universe && p.universe !== '?', 'provenance must name the universe it was measured on');
    assert.ok(p.range && p.range !== '?');
  });

  await t.test('every call prints the different-bench warning', () => {
    // The boundary has to travel with the data. An agent that greps one row must still be
    // told these numbers are from zz500/3y on JQ's cost model, not our epoch-5 bench.
    const b = fl.banner();
    assert.match(b, /DIFFERENT BENCH/);
    assert.match(b, /never write them into/i);
  });

  await t.test('the survivor count is still the measured 6 of 285', () => {
    // If a re-ingest changes this, the priors quoted to the ideator and critic are stale.
    const rows = fl.load();
    const surv = fl.query(rows, { survivors: true });
    assert.strictEqual(rows.length, 285, 'snapshot size changed — re-check the quoted priors');
    assert.strictEqual(surv.length, 6, 'survivor count changed — update the ideator/critic priors');
  });

  await t.test('survivors are the low-turnover end of the board', () => {
    const rows = fl.load();
    const surv = fl.query(rows, { survivors: true });
    const med = a => a.slice().sort((x, y) => x - y)[Math.floor(a.length / 2)];
    const tOf = r => parseFloat(r.turnover_top);
    assert.ok(med(surv.map(tOf)) < med(rows.map(tOf).filter(Number.isFinite)),
      'the claim "survivors are low-turnover" no longer holds');
  });

  await t.test('queries filter without reordering away the post-cost ranking', () => {
    const rows = fl.load();
    const hits = fl.query(rows, { category: '动量' });
    assert.ok(hits.length > 0);
    for (let i = 1; i < hits.length; i++) {
      const a = parseFloat(hits[i - 1].top_ex_annual_cost);
      const b = parseFloat(hits[i].top_ex_annual_cost);
      if (Number.isFinite(a) && Number.isFinite(b)) assert.ok(a >= b, 'not ranked post-cost');
    }
  });

  await t.test('the ideator and critic both carry the boundary, not just the tool', () => {
    const ide = fsx.readFileSync(pathx.join(R, '.claude/agents/autoenhance-ideator.md'), 'utf8');
    const cri = fsx.readFileSync(pathx.join(R, '.claude/agents/autoenhance-critic.md'), 'utf8');
    assert.match(ide, /factorlib-query/);
    assert.match(ide, /HYPOTHESIS source/);
    assert.match(ide, /external-factor|external factor/);
    assert.match(cri, /external-factor/);
    assert.match(cri, /No borrowed numbers/);
  });
});

test('epoch 6 pins the stock order cost', async t => {
  const h = require('../utils/harness-config');
  const sc = require('../utils/stockcost-affected');

  await t.test('the active epoch declares a stock cost table', () => {
    const c = h.config();
    assert.strictEqual(c.epoch, 6);
    assert.ok(c.costs.stockOrderCost, 'epoch 6 must declare costs.stockOrderCost');
  });

  await t.test('it reproduces what the deprecated set_commission MEANT', () => {
    // PerTrade(buy 0.0003, sell 0.0013) = 0.03% each way + 0.1% stamp on the sell. The bench's
    // intent is unchanged; epoch 6 only makes it apply, because set_commission is 已废弃 and
    // a strategy's own set_order_cost(type='stock') won outright.
    const s = h.config().costs.stockOrderCost;
    assert.strictEqual(s.openCommission, 0.0003);
    assert.strictEqual(s.closeCommission, 0.0003);
    assert.strictEqual(s.closeTax, 0.001);
  });

  await t.test('the literal is generated and both Python blocks carry it', () => {
    const lit = h.pythonLiterals();
    assert.match(lit.stockOrderCost, /type='stock'/);
    assert.deepStrictEqual(h.verify(), [], 'frozen Python must match the config');
  });

  await t.test('the OVERRIDE intercepts stock as well as fund', () => {
    const src = fs.readFileSync(path.join(__dirname, '..', 'utils/strategy-normalize.js'), 'utf8');
    assert.match(src, /__t == 'fund'/);
    assert.match(src, /__t == 'stock'/);
    // The old shape forwarded everything that was not 'fund' to the author's settings.
    assert.ok(!/if k\.get\('type'\) == 'fund' or \(len\(a\) > 1 and a\[1\] == 'fund'\):/.test(src),
      'the fund-only wrapper is what let author stock costs through');
  });

  await t.test('epoch-5 rows are no longer valid measurements', () => {
    // Costs changed, so this bump is explicitly NOT measurement-preserving.
    assert.strictEqual(h.measurementValid('5'), false);
    assert.strictEqual(h.measurementValid('6'), true);
  });
});

test('the epoch-6 re-measure set is narrowed to what actually changed', async t => {
  const sc = require('../utils/stockcost-affected');
  const r = sc.classify();

  await t.test('strategies that never set a stock cost are unaffected', () => {
    // They ran on JQ's default (万3 + 0.1% stamp), which is exactly what epoch 6 pins.
    assert.ok(r.unset.length > 0);
  });

  await t.test('bench-equivalent declarations are a no-op', () => {
    assert.ok(r.equivalent.length > 0);
    for (const f of r.equivalent.slice(0, 5)) assert.strictEqual(typeof f, 'string');
  });

  await t.test('only differing declarations are affected', () => {
    assert.ok(r.affected.length > 0 && r.affected.length < r.unset.length,
      'a change that touches everything would not be worth narrowing');
    for (const a of r.affected.slice(0, 5)) {
      const d = a.declared;
      const same = d.open === r.bench.open && d.close === r.bench.close &&
                   (d.ctax == null || d.ctax === r.bench.ctax);
      assert.ok(!same, `${a.file} was classified affected but matches the bench`);
    }
  });

  await t.test('a missing close_tax counts as bench default, not as a difference', () => {
    // Omitting it leaves JQ's 0.1% stamp in place, which IS the bench value.
    const d = sc.declaredStockCost(
      "set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')");
    assert.strictEqual(d.ctax, null);
  });

  await t.test('fractional literals like 2.5/10000 parse', () => {
    assert.ok(Math.abs(sc.num('2.5/10000') - 0.00025) < 1e-12);
    assert.strictEqual(sc.num('0.0003'), 0.0003);
  });
});
