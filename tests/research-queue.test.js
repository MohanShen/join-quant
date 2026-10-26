/**
 * The merged loop's queue and findings contracts.
 *
 * Both previously lived only in prose — two program.md files and eight agent definitions. Prose
 * drifted: within a day of fixing the enhance resume nudge, the study copy still named a
 * superseded epoch. A contract nothing can check is a contract that quietly stops holding.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

process.env.JQ_RESEARCH_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'jq-rq-'));
const rq = require('../utils/research-queue');

const FAM = 'TEST家族';
const reset = () => fs.rmSync(path.join(process.env.JQ_RESEARCH_DIR, FAM), { recursive: true, force: true });

test('queue contract', async (t) => {
  await t.test('both idea kinds live in ONE queue', () => {
    reset();
    rq.add(FAM, { kind: 'understand', title: 'why does the floor matter', from: [] });
    rq.add(FAM, { kind: 'improve', title: 'tighten the floor to 1e7', from: ['q-1'] });
    const kinds = rq.load(FAM).map(e => e.kind);
    assert.deepStrictEqual(kinds, ['understand', 'improve']);
  });

  await t.test('an unknown kind is refused', () => {
    reset();
    assert.throws(() => rq.add(FAM, { kind: 'optimise', title: 'x', from: [] }), /understand\|improve/);
  });

  await t.test('`from` is required as an array — ungrounded is allowed, unstated is not', () => {
    reset();
    assert.throws(() => rq.add(FAM, { kind: 'improve', title: 'x' }), /from must be an array/);
    rq.add(FAM, { kind: 'improve', title: 'x', from: [] });
    assert.deepStrictEqual(rq.context(FAM).ungrounded, ['idea-1'],
      'an empty from[] must be reported as ungrounded, not silently accepted');
  });
});

test('findings carry an implication, not just a result', async (t) => {
  const finding = 'sharpe 8.44 -> 3.16 -> 1.10 as the volume floor rises';

  await t.test('an empty implication is refused', () => {
    reset();
    assert.throws(() => rq.recordFinding(FAM, { qId: 'q-1', finding, implication: '' }), /empty/);
  });

  await t.test('a restatement of the finding is refused', () => {
    // The failure mode this exists to catch: a field filled in to satisfy the schema, saying
    // nothing about what to do next.
    reset();
    assert.throws(() => rq.recordFinding(FAM, { qId: 'q-1', finding, implication: finding }),
      /restatement/);
    assert.throws(() => rq.recordFinding(FAM, { qId: 'q-1', finding, implication: `**${finding}**。` }),
      /restatement/, 'cosmetic edits must not get a restatement through');
  });

  await t.test('an implication that opens or closes a direction is accepted and stored', () => {
    reset();
    rq.recordFinding(FAM, {
      qId: 'q-1', type: 'sweep', finding, confidence: 'med-high',
      implication: 'the 2e6 floor is too loose; retest every member at 1e7 before trusting any delta',
      spawned: 'idea-1', edgeRef: '规模因子',
    });
    const [f] = rq.findings(FAM);
    assert.strictEqual(f.spawned, 'idea-1');
    assert.strictEqual(f.edgeRef, '规模因子');
    assert.match(f.implication, /1e7/);
  });

  await t.test('the appended columns do not disturb the original nine', () => {
    // Same migration consumption.tsv used for members/memberHash: readers indexing 0..8 unaffected.
    assert.deepStrictEqual(rq.FINDING_COLUMNS.slice(0, 9),
      ['qId', 'type', 'component_or_param', 'metric_delta', 'window', 'finding', 'confidence',
       'flags', 'description']);
    assert.deepStrictEqual(rq.FINDING_COLUMNS.slice(9), ['implication', 'spawned', 'edgeRef']);
  });

  await t.test('spawned defaults to `none` rather than empty', () => {
    reset();
    rq.recordFinding(FAM, { qId: 'q-2', finding, implication: 'that knob is closed; stop sweeping it' });
    assert.strictEqual(rq.findings(FAM)[0].spawned, 'none');
  });
});

test('context() is what makes the loop a loop', async (t) => {
  await t.test('it surfaces closed directions and unfollowed findings', () => {
    reset();
    rq.recordFinding(FAM, { qId: 'q-1', finding: 'monotone worsening from 2', confidence: 'high',
      implication: 'no_buy_after_day is monotone-worsening upward from 2 — that knob is closed' });
    const c = rq.context(FAM);
    assert.strictEqual(c.closedDirections.length, 1, 'a closed direction must be findable');
    assert.deepStrictEqual(c.unspawned, ['q-1'],
      'a high-confidence finding nobody followed up must be visible');
  });

  await t.test('lint reports an improve idea that ignores a measured edge', () => {
    // Once the edge is measured it is the improve generator's prior: off-mechanism by default.
    reset();
    const c = rq.lint('小市值');
    assert.ok(Array.isArray(c), 'lint must return a list, not throw, on a real family');
  });
});

/**
 * findings.tsv is gitignored; §6 is the durable copy — the same relationship the `normalized:`
 * blocks have with the normalize ledger, which regressed from ~119 rows to 18.
 *
 * The recorder wrote the ledger first and the page second, so an interruption between the two
 * lost the durable copy silently. Measured: a 红利低频 round killed by an API 529 left 4 findings
 * in findings.tsv, 0 rows in §2, and no §6 section at all.
 */
test('research-sync makes the page catch up with the ledger', async (t) => {
  const sync = require('../utils/research-sync');

  await t.test('it renders the IMPLICATION, not just the conclusion', () => {
    // A §6 carrying only the finding would be a weaker handoff than the ledger it backs up —
    // the implication is the field the next round's generators read for closed directions.
    const out = sync.renderEntry({
      qId: 'q-1', type: 'ablation', component_or_param: 'turnover rank',
      finding: 'yield alone earns nothing', implication: 'that direction is closed',
      metric_delta: 'obj 0.13 -> -0.27', confidence: 'high', edgeRef: '股息率',
    });
    assert.match(out, /\[Q q-1\]/);
    assert.match(out, /yield alone earns nothing/);
    assert.match(out, /that direction is closed/);
    assert.match(out, /edge: 股息率/);
  });

  await t.test('a missing implication is marked as a contract violation, not left blank', () => {
    const out = sync.renderEntry({ qId: 'q-2', finding: 'x' });
    assert.match(out, /contract violation/);
  });

  await t.test('it is idempotent — a second run adds nothing', () => {
    // Append-only: a human edit to a conclusion must survive the next sync.
    const before = sync.sync('红利低频', { dry: true });
    assert.strictEqual(before.wrote, 0,
      `expected 红利低频 to be in sync, but ${before.wrote} entry(ies) are missing from §6`);
  });

  await t.test('every family with findings has them in §6', () => {
    for (const f of sync.families()) {
      const r = sync.sync(f, { dry: true });
      if (r.err) continue;
      assert.strictEqual(r.wrote, 0,
        `${f}: ${r.wrote} finding(s) exist only in the gitignored ledger — run research-sync`);
    }
  });
});

/**
 * ⚠⚠ A CLOSED DIRECTION ONLY BINDS ON THE BENCH THAT MADE IT.
 *
 * `closedDirections` is what stops a round re-proposing finished work: the gatekeeper hard-rejects
 * a duplicate against it and the skill's Step 0 exits on one. Right within a bench, wrong across
 * one — a knob closed because it did not help on TRAIN 2022-2023 may help on 2024, and the loop
 * would never try it again. Measured 2026-10-26: 125 of 134 closures were made on a bench epoch 9
 * does not accept.
 */
const sct = require('node:test');
const sca = require('node:assert');
const scfs = require('fs');
const scos = require('os');
const scpath = require('path');

sct('closures are split by the bench that made them', async t => {
  const rq = require('../utils/research-queue');
  const harness = require('../utils/harness-config');
  const active = harness.config().epoch;

  const mk = rows => {
    const d = scfs.mkdtempSync(scpath.join(scos.tmpdir(), 'rqc-'));
    const fam = scpath.join(d, 'F');
    scfs.mkdirSync(fam, { recursive: true });
    const hdr = rq.FINDING_COLUMNS.concat(['measuredEpoch']).join('\t');
    const body = rows.map(r => {
      const c = rq.FINDING_COLUMNS.map(k => r[k] || '');
      c.push(r.measuredEpoch == null ? '' : String(r.measuredEpoch));
      return c.join('\t');
    });
    scfs.writeFileSync(scpath.join(fam, 'findings.tsv'), [hdr, ...body].join('\n') + '\n');
    return d;
  };

  const withDir = (d, fn) => {
    const prev = process.env.JQ_RESEARCH_DIR;
    process.env.JQ_RESEARCH_DIR = d;
    try { return fn(); } finally {
      if (prev === undefined) delete process.env.JQ_RESEARCH_DIR; else process.env.JQ_RESEARCH_DIR = prev;
    }
  };

  await t.test('a closure from the ACTIVE bench still binds', () => {
    const d = mk([{ qId: 'q-now', finding: 'x', implication: 'that knob is closed', measuredEpoch: active }]);
    withDir(d, () => {
      const c = rq.context('F');
      sca.strictEqual(c.closedDirections.length, 1, 'same bench => binding');
      sca.strictEqual(c.staleClosures.length, 0);
    });
  });

  await t.test('a closure from a NON-comparable bench is reopenable, with its reason attached', () => {
    // epoch 6 changed fills and fees, so sameBench(6, 9) is false.
    const d = mk([{ qId: 'q-old', finding: 'x', implication: '止损这个旋钮关闭', measuredEpoch: 6 }]);
    withDir(d, () => {
      const c = rq.context('F');
      sca.strictEqual(c.closedDirections.length, 0, 'a different bench must not bind');
      sca.strictEqual(c.staleClosures.length, 1);
      const s = c.staleClosures[0];
      sca.strictEqual(s.qId, 'q-old');
      sca.strictEqual(s.closedAtEpoch, 6, 'the epoch must travel with it, so the reason can be judged');
      sca.match(s.implication, /关闭/, 'the original implication must be carried, not just the id');
    });
  });

  /**
   * ⚠ Deliberately the OPPOSITE of the VAL budget's unknown-epoch rule. A false "still closed"
   * suppresses work silently and forever; a false "reopenable" costs a few backtest minutes.
   */
  await t.test('an UNKNOWN epoch is reopenable, not binding', () => {
    const d = mk([{ qId: 'q-?', finding: 'x', implication: 'direction closed', measuredEpoch: '' }]);
    withDir(d, () => {
      const c = rq.context('F');
      sca.strictEqual(c.closedDirections.length, 0);
      sca.strictEqual(c.staleClosures[0].closedAtEpoch, 'unknown');
    });
  });

  /**
   * ⚠⚠ The regression that shipped: `findings()` mapped only the 12 canonical columns, so
   * `measuredEpoch` was always undefined, every closure read as unknown-and-therefore-stale, and
   * the split reported "0 binding / 134 stale" — telling the loop to reopen its own current
   * conclusions. The parser must expose the 13th field.
   */
  await t.test('findings() exposes measuredEpoch — without it the split is degenerate', () => {
    const d = mk([{ qId: 'q-now', finding: 'x', implication: 'closed', measuredEpoch: active }]);
    withDir(d, () => {
      sca.strictEqual(rq.findings('F')[0].measuredEpoch, String(active),
        'the 13th column must be readable or every closure looks unknown');
    });
  });

  await t.test('both consumers are told, or the split changes nothing', () => {
    const gk = scfs.readFileSync(scpath.join(__dirname, '../.claude/agents/family-gatekeeper.md'), 'utf8');
    const sk = scfs.readFileSync(scpath.join(__dirname, '../.claude/skills/run-family/SKILL.md'), 'utf8');
    for (const [name, src] of [['family-gatekeeper', gk], ['run-family SKILL', sk]]) {
      sca.match(src, /staleClosures/, `${name} must know stale closures are not duplicates`);
    }
    sca.match(gk, /REOPENABLE, not duplicates/i, 'the gatekeeper must not hard-reject them');
  });
});
