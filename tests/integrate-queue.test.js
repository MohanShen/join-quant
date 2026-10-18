/**
 * The universe round's queue, INCREMENTAL model (integrate-queue Revision 4, user spec 2026-10-16).
 *
 * Integration used to enumerate every PAIR of families in a universe. That treated a universe as
 * a static set, had no notion of what it had already delivered, and so offered the same pairs
 * round after round while a round's own result changed nothing about the next one.
 *
 * Now a universe holds a set of PROMOTED candidates and families arrive ONE AT A TIME after
 * clearing /run-family. The three outcomes, each pinned below:
 *
 *   1. nothing promoted overlaps it  -> promoted automatically (an EMPTY set needs no judgement
 *      at all, which the queue reports as `seed`);
 *   2. an overlapping incumbent and the merge is better -> merged candidate promoted, incumbent
 *      SUPERSEDED;
 *   3. an overlapping incumbent and the merge fails -> incumbent unchanged, ARRIVAL rejected
 *      until that family has a new best variant.
 *
 * ⚠ Sequence is load-bearing: the first arrival defines what everything after it must beat, so
 * arrivals are ordered by CHAMPION TRAIN SHARPE, highest first.
 */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const harness = require('../utils/harness-config');

/**
 * A complete fixture universe: family pages, strategy pages, a ledger, a consumption file (for
 * the VAL lookup) and an empty promoted register. Every path is env-redirected, because these
 * stores are TRACKED and a test must never append probe rows to the real ones.
 */
function world(families) {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'iq-'));
  const famDir = path.join(d, 'families'); fs.mkdirSync(famDir);
  const pageDir = path.join(d, 'pages'); fs.mkdirSync(pageDir);
  const ep = harness.config().epoch;

  const ledger = ['sourceFile\tpostId\ttitle\tstatus\tstart\tend\tdays\ttotal_pct\tannual_pct\tsharpe\tmaxdd_pct\tobjective\tgate\tepoch'];
  const consumption = ['key\tkind\tstage\trunId\tat\toutcome\tnote\tmembers\tmemberHash\tepoch'];

  for (const [name, f] of Object.entries(families)) {
    const edges = (f.edges || [['e-' + name, 'measured']])
      .map(([n, st]) => `  - name: ${n}\n    status: ${st}`).join('\n');
    fs.writeFileSync(path.join(famDir, name + '.md'),
      `---\nfamily: ${name}\nuniverse: ${f.u}\n` +
      (f.parent ? `parent: [[${f.parent}]]\n` : '') +
      (f.R == null ? '' : `realizability: ${f.R}\n`) +
      `base: [[${f.base || name + '-base'}]]\nbestVariant: [[${f.best || f.base || name + '-base'}]]\n` +
      `bestObjective: ${f.obj}\nmemberCount: 1\nrealism: "${f.realism || ''}"\n` +
      `edge:\n${edges}\nstatus: active\n---\n\n# ${name}\n`);

    const src = `strategies/${name}.py`;
    fs.writeFileSync(path.join(pageDir, name + '.md'),
      `---\nfamily: ${name}\nsourceFile: ${src}\n---\n`);
    if (f.champion !== false) {
      ledger.push([src, '', name, 'normalized', '', '', '729', '100',
                   f.annual ?? 50, f.sharpe, f.maxdd ?? 10, f.obj, 'pass',
                   f.championEpoch ?? ep].join('\t'));
    }
    if (f.val != null) {
      // ⚠ Mirror the real convention: a product's VAL is recorded as `<expId>-val`. Without this
      // a fixture with a product blocks at the VAL/candidate match and never reaches the check
      // the test is actually about.
      const runId = f.product ? `${f.product.expId}-val` : `${name}-val`;
      consumption.push([name, 'family', 'validate', runId, '2026-10-01T00:00:00Z',
                        `sharpe ${f.val}`, '', '', '', f.valEpoch ?? ep].join('\t'));
    }
  }
  fs.writeFileSync(path.join(d, 'ledger.tsv'), ledger.join('\n') + '\n');
  fs.writeFileSync(path.join(d, 'consumption.tsv'), consumption.join('\n') + '\n');

  // VAL-window curves. `valOn: 'base'` writes study_<fam>_baseline__val__eN (the family's own
  // base met the window); `valOn: 'candidate'` writes enhance_candidates_<fam>-imp-1__val__eN
  // (a CONSTRUCTED book met it, which is never a ledger row and so never the champion).
  // ⚠ The product shelf MUST be redirected too. Without this the gate reads the real
  // validated_strategies/, so a fixture family named like a real one would silently inherit its
  // product — and a test would pass or fail for reasons outside the fixture.
  const shelfDir = path.join(d, 'shelf'); fs.mkdirSync(shelfDir);
  for (const [name, f] of Object.entries(families)) {
    if (!f.product) continue;
    const pr = f.product;
    fs.writeFileSync(path.join(shelfDir, `${pr.expId}.py`),
      `# family:           ${name}   (source base: strategies/${name}.py)\n` +
      `# expId:            ${pr.expId}\n` +
      `# harness_epoch:    ${pr.epoch ?? harness.config().epoch}\n` +
      `# train_objective:  ${pr.obj}\n` +
      `# sharpe_val:       ${pr.sharpeVal ?? 2.0}\n` +
      `# gate_val:         ${pr.gateVal ?? 'pass'}     (asserted by the fixture)\n`);
  }

  const sdir = path.join(d, 'series'); fs.mkdirSync(sdir);
  const curve = JSON.stringify({ dates: ['2024-01-02'], cum: [1], benchCum: [0], points: 1 });
  for (const [name, f] of Object.entries(families)) {
    if (f.valOn === 'base') fs.writeFileSync(path.join(sdir, `study_${name}_baseline__val__e${ep}.json`), curve);
    if (f.valOn === 'candidate') fs.writeFileSync(path.join(sdir, `enhance_candidates_${name}-imp-1__val__e${ep}.json`), curve);
  }
  return { dir: d, famDir, pageDir, series: sdir, shelf: shelfDir,
           ledger: path.join(d, 'ledger.tsv'),
           consumption: path.join(d, 'consumption.tsv'),
           promoted: path.join(d, 'promoted.tsv') };
}

const MODULES = ['../utils/integrate-queue', '../utils/integrate-eligible', '../utils/promoted',
                 '../utils/val-budget', '../utils/consumption', '../utils/backtest-series'];

/** Run `fn` with the fixture's stores in force, with the modules reloaded around it. */
function inWorld(w, fn) {
  const envs = {
    JQ_FAMILIES_DIR: w.famDir, JQ_STRATEGY_PAGES: w.pageDir, JQ_LEDGER: w.ledger,
    JQ_CONSUMPTION_FILE: w.consumption, JQ_PROMOTED_FILE: w.promoted, JQ_SERIES_DIR: w.series,
    JQ_VALIDATED_DIR: w.shelf,
    JQ_REFUSALS_FILE: path.join(w.dir, 'refusals.tsv'),
  };
  const prev = {};
  for (const k of Object.keys(envs)) { prev[k] = process.env[k]; process.env[k] = envs[k]; }
  for (const m of MODULES) delete require.cache[require.resolve(m)];
  try {
    return fn({
      queue: require('../utils/integrate-queue'),
      eligible: require('../utils/integrate-eligible'),
      promoted: require('../utils/promoted'),
    });
  } finally {
    for (const k of Object.keys(envs)) {
      if (prev[k] === undefined) delete process.env[k]; else process.env[k] = prev[k];
    }
    for (const m of MODULES) delete require.cache[require.resolve(m)];
  }
}

const row = (u, rows) => rows.find(r => r.universe === u);

// ── the /run-family exit gate ────────────────────────────────────────────────

test('the /run-family exit gate', async t => {
  await t.test('a family with a champion, a passing VAL and R>=2 is eligible', () => {
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base' } });
    inWorld(w, ({ eligible }) => {
      const a = eligible.assess('A');
      assert.strictEqual(a.status, 'eligible');
      assert.strictEqual(a.eligible, true);
    });
  });

  await t.test('never validated BLOCKS — integration may not take a TRAIN-only number', () => {
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, R: 3 } });
    inWorld(w, ({ eligible }) => {
      const a = eligible.assess('A');
      assert.strictEqual(a.status, 'blocked');
      assert.match(a.why, /never validated/);
    });
  });

  await t.test('a FAILING VAL rejects, and a stale-epoch VAL blocks', () => {
    const failed = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 0.9, R: 3, valOn: 'base' } });
    inWorld(failed, ({ eligible }) => {
      const a = eligible.assess('A');
      assert.strictEqual(a.status, 'rejected');
      assert.match(a.why, /did not pass/);
    });
    // Epoch 2 predates the execution pins, so its VAL is not a current result.
    const stale = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 9.9, valEpoch: 2, R: 3, valOn: 'base' } });
    inWorld(stale, ({ eligible }) => {
      const a = eligible.assess('A');
      assert.strictEqual(a.status, 'blocked');
      assert.match(a.why, /active epoch does not accept/);
    });
  });

  await t.test('R=1 is REJECTED — rule 4 therefore never has to bind at the judge', () => {
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 1, valOn: 'base' } });
    inWorld(w, ({ eligible }) => {
      const a = eligible.assess('A');
      assert.strictEqual(a.status, 'rejected');
      assert.match(a.why, /realizability 1 < 2/);
    });
  });

  await t.test('UNKNOWN realizability BLOCKS, it does not permit', () => {
    // Same rule the VAL budget applies to an unknown epoch: blocking is visible and a human
    // clears it with one edit, whereas permitting silently ships an unrealizable book.
    // ⚠ It must not be inferred from the 不可实现 regex either — 打板短线 does not match it and
    // was still scored 1 on evidence.
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: null, valOn: 'base' } });
    inWorld(w, ({ eligible }) => {
      const a = eligible.assess('A');
      assert.strictEqual(a.status, 'blocked');
      assert.match(a.why, /no realizability:/);
    });
  });

  await t.test('a champion on a superseded bench blocks', () => {
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, championEpoch: 2, valOn: 'base' } });
    inWorld(w, ({ eligible }) => {
      assert.match(eligible.assess('A').why, /no candidate: nothing on the product shelf/);
    });
  });

  await t.test('a VAL that ran on a DIFFERENT book does not validate the champion', () => {
    // ⚠⚠ The live defect, 2026-10-16. The gate checked "has a champion" and "has a passing VAL"
    // INDEPENDENTLY, and 大小盘轮动 satisfied each with a different book: champion = base
    // 2f5bc859 (objective 0.4567) while its one VAL (dxp-imp-1-val) ran on
    // enhance/candidates/dxp-imp-1.py (0.6623), proven by the stored curve
    // enhance_candidates_dxp-imp-1__val__e6. 混合 had been SEEDED on that, so an irreversible OOS
    // test was about to be spent on a book nothing had validated.
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'candidate' } });
    inWorld(w, ({ eligible }) => {
      const a = eligible.assess('A');
      assert.strictEqual(a.status, 'blocked');
      assert.match(a.why, /did not validate the CANDIDATE/);
      });
  });

  await t.test('the CANDIDATE is the validated PRODUCT when the shelf has one', () => {
    // ⚠⚠ The bug this fixes. `championOf` reads the normalize LEDGER, which tracks only INGESTED
    // strategies/*.py — so a book the research loop BUILT can never appear there. For 大小盘轮动
    // the shelf holds dxp-imp-1 at train_objective 0.6623 against the base's 0.4567, validated and
    // archived; the gate promoted the BASE instead and then reported the family as unsettled.
    const w = world({
      A: { u: 'U', obj: 0.4567, sharpe: 2.68, val: 1.88, R: 3, valOn: 'base',
           product: { expId: 'A-imp-1', obj: 0.6623, sharpeVal: 1.88 } },
    });
    inWorld(w, ({ eligible }) => {
      const a = eligible.assess('A');
      assert.ok(a.product, 'the shelf product must be found');
      assert.strictEqual(a.candidate.kind, 'product');
      assert.strictEqual(a.candidate.expId, 'A-imp-1');
      assert.notStrictEqual(a.candidate.sourceFile, a.member.sourceFile,
        'the product outranks the best ingested member');
    });
  });

  await t.test('a product on a stale bench, or one whose VAL failed, is not usable', () => {
    const stale = [1, 2, 3, 4, 5].find(e => !harness.measurementValid(e));
    const w = world({
      A: { u: 'U', obj: 0.45, sharpe: 2.6, val: 1.88, R: 3, valOn: 'base',
           product: { expId: 'A-old', obj: 0.9, epoch: stale ?? 2 } },
    });
    inWorld(w, ({ eligible }) => {
      assert.match(eligible.assess('A').why, /not usable on this bench/);
    });
    const failed = world({
      A: { u: 'U', obj: 0.45, sharpe: 2.6, val: 1.88, R: 3, valOn: 'base',
           product: { expId: 'A-bad', obj: 0.9, gateVal: 'fail' } },
    });
    inWorld(failed, ({ eligible }) => {
      assert.match(eligible.assess('A').why, /not usable on this bench/);
    });
  });

  await t.test('realizability scored on the BASE does not transfer to a product', () => {
    // Measured case: 大小盘轮动's R=2 came from liq-1 on the BASE, while its product is
    // always-small — which the family's own realism calls worse on capacity. One number on the
    // page cannot describe two books, so the scope has to be named.
    const w = world({
      A: { u: 'U', obj: 0.45, sharpe: 2.6, val: 1.88, R: 2, valOn: 'base',
           product: { expId: 'A-imp-1', obj: 0.66 } },
    });
    inWorld(w, ({ eligible }) => {
      const a = eligible.assess('A');
      assert.strictEqual(a.status, 'blocked');
      assert.match(a.why, /scored for this family's BASE/);
      assert.match(a.why, /realizabilityScope: A-imp-1/);
    });
  });

  await t.test('a VAL runId that INFIXES the val token still matches its product', () => {
    // Observed conventions: dxp-imp-1-val (suffix), pt-val-base-e6 and dbdx-VAL-base-e6 (infix).
    // A plain includes(expId) falsely rejected two correctly-recorded VALs.
    const norm = { u: 'U', obj: 0.45, sharpe: 2.6, R: 3, valOn: 'base' };
    for (const [runId, expId] of [['pt-val-base-e6', 'pt-base-e6'], ['dbdx-VAL-base-e6', 'dbdx-base-e6']]) {
      const w = world({ A: { ...norm, val: 2.0, product: { expId, obj: 0.9 } } });
      // rewrite the fixture's VAL runId to the observed shape
      const f = w.consumption;
      fs.writeFileSync(f, fs.readFileSync(f, 'utf8').replace(`${expId}-val`, runId));
      fs.writeFileSync(path.join(w.famDir, 'A.md'),
        fs.readFileSync(path.join(w.famDir, 'A.md'), 'utf8')
          .replace('realizability: 3', `realizability: 3\nrealizabilityScope: ${expId}`));
      inWorld(w, ({ eligible }) => {
        const a = eligible.assess('A');
        assert.strictEqual(a.status, 'eligible', `${runId} should match ${expId}: ${a.why}`);
      });
    }
  });

  await t.test('a VAL on the base validates the champion only when base == bestVariant', () => {
    // PT多策略's shape: the VAL ran on the base (fa0d3bd9) while the champion is a different
    // member (c70281d3). The base's held-out number says nothing about the champion.
    const same = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base',
                              base: 'b1', best: 'b1' } });
    inWorld(same, ({ eligible }) => {
      assert.strictEqual(eligible.assess('A').status, 'eligible');
    });
    const differ = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base',
                                base: 'b1', best: 'other-member' } });
    inWorld(differ, ({ eligible }) => {
      const a = eligible.assess('A');
      assert.strictEqual(a.status, 'blocked');
      assert.match(a.why, /ran on this family's BASE/);
    });
  });
});

// ── the promoted register ───────────────────────────────────────────────────

test('the promoted register', async t => {
  await t.test('replays promote then supersede, and stamps the epoch itself', () => {
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base' } });
    inWorld(w, ({ promoted }) => {
      promoted.record({ universe: 'U', action: 'promote', candidateId: 'c1', sharpe: 2.0 });
      assert.strictEqual(promoted.current('U').length, 1);
      // A caller must not be able to choose the epoch — that would launder a stale promotion.
      assert.strictEqual(String(promoted.current('U')[0].epoch), String(harness.config().epoch));
      promoted.record({ universe: 'U', action: 'promote', candidateId: 'merged-1',
                        kind: 'merged', members: ['A', 'B'], sharpe: 2.6 });
      promoted.record({ universe: 'U', action: 'supersede', candidateId: 'c1' });
      const cur = promoted.current('U');
      assert.deepStrictEqual(cur.map(c => c.candidateId), ['merged-1']);
      assert.deepStrictEqual(cur[0].members, ['A', 'B']);
    });
  });

  await t.test('orders strongest sharpe first — the multi-overlap merge target', () => {
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base' } });
    inWorld(w, ({ promoted }) => {
      promoted.record({ universe: 'U', action: 'promote', candidateId: 'weak', sharpe: 1.6 });
      promoted.record({ universe: 'U', action: 'promote', candidateId: 'strong', sharpe: 3.1 });
      assert.deepStrictEqual(promoted.current('U').map(c => c.candidateId), ['strong', 'weak']);
    });
  });

  await t.test('a reject demands a reason, and is keyed to the CANDIDATE not the family', () => {
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base' } });
    inWorld(w, ({ promoted }) => {
      assert.throws(() => promoted.record({ universe: 'U', action: 'reject', candidateId: 'x' }),
        /needs a note/);
      promoted.record({ universe: 'U', action: 'reject', candidateId: 'champ-v1', note: 'merge lost both years' });
      assert.strictEqual(promoted.isRejected('U', 'champ-v1'), true);
      // The spec: rejected "until the next time this family has a new best variant". A new
      // champion is a new candidateId, so it is automatically a new attempt — no expiry rule.
      assert.strictEqual(promoted.isRejected('U', 'champ-v2'), false);
    });
  });

  await t.test('an unknown action is refused rather than silently appended', () => {
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base' } });
    inWorld(w, ({ promoted }) => {
      assert.throws(() => promoted.record({ universe: 'U', action: 'ship', candidateId: 'x' }),
        /action must be one of/);
    });
  });
});

// ── the three outcomes ──────────────────────────────────────────────────────

test('the incremental round', async t => {
  await t.test('an empty universe SEEDS its first eligible arrival, no judgement needed', () => {
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base' } });
    inWorld(w, ({ queue }) => {
      const r = row('U', queue.build());
      assert.strictEqual(r.action, 'seed');
      assert.strictEqual(r.arrival.family, 'A');
      assert.strictEqual(r.promoted.length, 0);
    });
  });

  await t.test('arrivals are ordered by CHAMPION SHARPE — sequence defines the bar', () => {
    const w = world({
      Weak:   { u: 'U', obj: 0.9, sharpe: 1.7, val: 2.1, R: 3, valOn: 'base' },
      Strong: { u: 'U', obj: 0.2, sharpe: 4.4, val: 2.1, R: 3, valOn: 'base' },
    });
    inWorld(w, ({ queue }) => {
      const r = row('U', queue.build());
      // ⚠ Strong leads DESPITE a far lower objective: the order key is sharpe, not objective.
      assert.deepStrictEqual(r.arrivals.map(a => a.family), ['Strong', 'Weak']);
      assert.strictEqual(r.arrival.family, 'Strong');
    });
  });

  await t.test('with something promoted, the action is INTEGRATE — overlap is the agent\'s call', () => {
    const w = world({
      A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base' },
      B: { u: 'U', obj: 0.4, sharpe: 1.8, val: 2.1, R: 3, valOn: 'base' },
    });
    inWorld(w, ({ queue, promoted }) => {
      promoted.record({ universe: 'U', action: 'promote', candidateId: 'strategies/A.py', sharpe: 2.0 });
      const r = row('U', queue.build());
      assert.strictEqual(r.action, 'integrate');
      assert.strictEqual(r.arrival.family, 'B', 'A is already promoted, so B is the arrival');
      assert.deepStrictEqual(r.promoted.map(c => c.candidateId), ['strategies/A.py']);
    });
  });

  await t.test('outcome 3: a rejected arrival leaves the queue until a NEW champion', () => {
    const w = world({
      A: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base' },
      B: { u: 'U', obj: 0.4, sharpe: 1.8, val: 2.1, R: 3, valOn: 'base' },
    });
    inWorld(w, ({ queue, promoted }) => {
      promoted.record({ universe: 'U', action: 'promote', candidateId: 'strategies/A.py', sharpe: 2.0 });
      promoted.record({ universe: 'U', action: 'reject', candidateId: 'strategies/B.py',
                        note: 'merge failed per-year domination in 2023' });
      const r = row('U', queue.build());
      assert.strictEqual(r.action, 'idle');
      assert.strictEqual(r.arrival, null);
      assert.ok(r.dispositioned.some(d => d.family === 'B' && /rejected at this champion/.test(d.state)),
        'the rejection must be visible, with the reopening rule stated');
      // The incumbent is untouched by a failed merge.
      assert.deepStrictEqual(r.promoted.map(c => c.candidateId), ['strategies/A.py']);
    });
  });

  await t.test('an ineligible family never becomes an arrival, and says why', () => {
    const w = world({
      Good: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base' },
      NoVal: { u: 'U', obj: 0.9, sharpe: 9.9, R: 3 },
      Unreal: { u: 'U', obj: 0.9, sharpe: 8.8, val: 2.1, R: 1, valOn: 'base' },
    });
    inWorld(w, ({ queue }) => {
      const r = row('U', queue.build());
      // Both ineligible ones outrank Good on sharpe and must still not lead.
      assert.strictEqual(r.arrival.family, 'Good');
      const by = new Map(r.notEligible.map(x => [x.family, x]));
      assert.strictEqual(by.get('NoVal').status, 'blocked');
      assert.strictEqual(by.get('Unreal').status, 'rejected');
    });
  });

  await t.test('a universe with no eligible family is IDLE, and points upstream', () => {
    const w = world({ A: { u: 'U', obj: 0.5, sharpe: 2.0, R: 3 } });
    inWorld(w, ({ queue }) => {
      const r = row('U', queue.build());
      assert.strictEqual(r.action, 'idle');
      assert.match(r.why, /gate is upstream/);
    });
  });

  await t.test('--next prefers a free SEED over a backtest-spending INTEGRATE', () => {
    const w = world({
      A: { u: 'Seeded', obj: 0.5, sharpe: 5.0, val: 2.1, R: 3, valOn: 'base' },
      B: { u: 'Seeded', obj: 0.4, sharpe: 4.0, val: 2.1, R: 3, valOn: 'base' },
      C: { u: 'Fresh', obj: 0.3, sharpe: 1.6, val: 2.1, R: 3, valOn: 'base' },
    });
    inWorld(w, ({ queue, promoted }) => {
      promoted.record({ universe: 'Seeded', action: 'promote', candidateId: 'strategies/A.py', sharpe: 5.0 });
      const n = queue.next();
      assert.strictEqual(n.action, 'seed');
      assert.strictEqual(n.universe, 'Fresh', 'the free action comes first even at lower sharpe');
    });
  });

  await t.test('a parent/child pair is refused structurally against the promoted set', () => {
    // ⚠ Edge NAMES cannot catch this. 五福闹新春 declares `parent: [[ETF动量]]` and their measured
    // edges are named 趋势择时 vs 动量, so the pair read as the most attractive "combine" in the
    // universe while being a FORK of one family.
    const w = world({
      Parent: { u: 'U', obj: 0.5, sharpe: 2.0, val: 2.1, R: 3, valOn: 'base', edges: [['动量', 'measured']] },
      Child: { u: 'U', obj: 0.6, sharpe: 1.9, val: 2.1, R: 3, parent: 'Parent', valOn: 'base',
               edges: [['趋势择时', 'measured']] },
    });
    inWorld(w, ({ queue, promoted }) => {
      promoted.record({ universe: 'U', action: 'promote', candidateId: 'strategies/Parent.py',
                        members: ['Parent'], sharpe: 2.0 });
      const r = row('U', queue.build());
      assert.strictEqual(r.arrival.family, 'Child');
      assert.ok(r.lineageRefused.length >= 1, 'the lineage must be refused deterministically');
      assert.match(r.lineageRefused[0].why, /same lineage/);
      assert.match(r.lineageRefused[0].why, /parent: \[\[Parent\]\]/);
    });
  });
});

/**
 * The gate must say WHO can clear a block, or the funnel's last stage waits in silence.
 *
 * Measured 2026-10-17: 8 of 13 families were `blocked` in `integrate-eligible` while
 * `family-queue` reported **0 due**. A family researched to exhaustion but never finalised on VAL
 * has no new members and a consumption row, so it reads `done` — and the only thing that can
 * perform the missing step is the research loop. Four families sat there with nothing in the
 * pipeline able to notice.
 */
test('the exit gate names the owner of every block', async (t) => {
  const el = require('../utils/integrate-eligible');
  const rows = el.all();

  await t.test('every non-eligible row carries an owner from the fixed set', () => {
    const OWNERS = new Set(['research', 'normalize', 'human', 'none']);
    for (const r of rows) {
      if (r.eligible) continue;
      assert.ok(OWNERS.has(r.owner),
        `${r.family}: owner "${r.owner}" is not one of ${[...OWNERS].join('/')}`);
    }
  });

  await t.test('a measured REJECTION is owned by nobody, so nothing reopens it', () => {
    // An R=1 family re-entered every day would spin the loop forever on a decision already taken.
    for (const r of rows.filter(x => x.status === 'rejected')) {
      assert.strictEqual(r.owner, 'none', `${r.family}: a rejection must not be reopened`);
    }
  });

  await t.test('a VAL on a bench the active epoch rejects asks the BUDGET who owns it', () => {
    // sameBench(valEpoch, active) false => a fresh VAL is allowed => research can clear it.
    // An unrecorded epoch is UNKNOWN, unknown blocks, so only a human override moves it. Keeping
    // that rule in val-budget rather than re-deriving it here is what stops the two drifting.
    const src = fs.readFileSync(path.join(__dirname, '../utils/integrate-eligible.js'), 'utf8');
    assert.match(src, /require\('\.\/val-budget'\)\.check\(family\)\.allowed/);
  });

  await t.test('family-queue reopens research-owned blocks and nothing else', () => {
    const q = require('../utils/family-queue').build();
    const reopened = q.due.filter(f => f.reason === 'integrate-blocked').map(f => f.family);
    const researchOwned = rows.filter(r => !r.eligible && r.owner === 'research').map(r => r.family);
    // ⚠⚠ PRECEDENCE, added 2026-10-18: the COVERAGE GUARD outranks this reopening.
    //
    // Two invariants meet here. This one exists because a research-owned block that nothing
    // reopens strands a family in silence (8 of 13 were blocked while the queue read 0 due). The
    // guard exists because epoch 9 invalidated every row and the chain picked 小市值 with 37
    // members and ONE measured — a 1-of-37 champion.
    //
    // The guard wins, for a reason specific to the two failure shapes: the stranding it replaced
    // was PERMANENT and INVISIBLE, whereas this hold is TEMPORARY (only the normalize stage can
    // satisfy it, and it always can) and REPORTED. So the assertion below demands that the hold
    // be visible — if it ever became silent, it would be the very failure this test was written
    // for, and that is what must not happen.
    const held = new Map(q.all.filter(f => f.reason === 'awaiting-measurement').map(f => [f.family, f]));
    for (const f of researchOwned) {
      if (held.has(f)) {
        const h = held.get(f);
        assert.ok(h.awaitingMeasurement > h.validMembers,
          `${f} is held but its coverage does not justify it`);
        assert.match(h.note, /awaiting measurement/,
          `${f} is held and MUST say so — a silent hold is the stranding this test exists for`);
        continue;
      }
      assert.ok(reopened.includes(f), `${f} is research-owned and must be reopened`);
    }
    for (const f of reopened) {
      assert.ok(researchOwned.includes(f),
        `${f} was reopened but its block is not research-owned — the loop would do nothing`);
    }
  });

  await t.test('a reopened family carries the gate sentence, not a staleness note', () => {
    const q = require('../utils/family-queue').build();
    for (const f of q.due.filter(x => x.reason === 'integrate-blocked')) {
      assert.ok(f.note && f.note.length > 10, `${f.family}: the dispatched session needs the why`);
      assert.strictEqual(f.gateOwner, 'research');
    }
  });

  await t.test('the wrapper tells the session a gate block is a NARROW job', () => {
    // A resumed session told only "continuing after a budget stop" would reopen the generator
    // loop and re-buy findings the family already holds.
    const sh = fs.readFileSync(path.join(__dirname, '../scripts/run-family.sh'), 'utf8');
    assert.match(sh, /FQ_REASON" = "integrate-blocked"/);
    assert.match(sh, /Do NOT open the generator loop/);
    assert.match(sh, /\$GATE_NOTE/, 'the note has to reach both the new and resumed prompts');
  });
});
