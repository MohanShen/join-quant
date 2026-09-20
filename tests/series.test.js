/**
 * Tests for the daily-equity-curve layer: the curve math, the zero-cost backfill matcher, and
 * the component register.
 *
 * Most of these cover a real incident from the build:
 *   - annualizing each side over its OWN span matched 0 of 124 ledger rows, because the ledger
 *     annualizes over the requested window (729 days) and a curve spans the trading days that
 *     actually occurred (724);
 *   - differencing cumulative percentages instead of chaining them reports volatility of 1.362
 *     where JoinQuant reports 0.227 — a 6x error that looks plausible in isolation;
 *   - "one curve claimed by several rows" is usually 16%-duplicate strategies, not ambiguity.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const series = require('../utils/backtest-series');
const backfill = require('../utils/series-backfill');
const scan = require('../utils/component-scan');

/** A curve rising a steady 1%/day, as cumulative percent. */
const steady = (n, pct = 1) => {
  const out = [];
  let eq = 1;
  for (let i = 0; i < n; i++) { eq *= (1 + pct / 100); out.push((eq - 1) * 100); }
  return out;
};
const dates = n => Array.from({ length: n }, (_, i) =>
  new Date(Date.UTC(2022, 0, 3) + i * 86400000).toISOString().slice(0, 10));

test('dailyReturns chains, never differences', async t => {
  await t.test('recovers a constant daily return far from zero', () => {
    // The whole point: at +300% cumulative, a 1% day is still 1%. Differencing would call it 4%.
    const cum = steady(200, 1);
    const r = series.dailyReturns(cum);
    assert.strictEqual(r.length, 200, 'returns are index-aligned with the curve');
    for (const v of r) assert.ok(Math.abs(v - 0.01) < 1e-9, `expected 0.01, got ${v}`);
  });

  await t.test('counts the FIRST day — cum[0] is a return, not a starting level', () => {
    // Regression guard. Starting the loop at i=1 dropped a +21.51% opening day on
    // 以混沌之火_信息熵策略, turning +25.77% into +3.51% and annual 12.16% into 1.75%.
    const r = series.dailyReturns([21.51, 20.55]);
    assert.ok(Math.abs(r[0] - 0.2151) < 1e-9, `first day should be 21.51%, got ${r[0]}`);
  });

  await t.test('recompounding the returns reproduces the curve exactly', () => {
    const cum = [21.51, 20.55, 21.23, 25.77];
    const r = series.dailyReturns(cum);
    let eq = 1;
    for (const v of r) eq *= (1 + v);
    assert.ok(Math.abs((eq - 1) * 100 - 25.77) < 1e-9, `got ${(eq - 1) * 100}`);
  });

  await t.test('differencing the same curve would be badly wrong — the guarded bug', () => {
    const cum = steady(200, 1);
    const diffed = [];
    for (let i = 1; i < cum.length; i++) diffed.push((cum[i] - cum[i - 1]) / 100);
    const last = diffed[diffed.length - 1];
    assert.ok(last > 0.05, `differencing should blow up far from zero, got ${last}`);
  });

  await t.test('survives a -100% wipeout instead of dividing by zero', () => {
    const r = series.dailyReturns([0, -100, -100]);
    assert.strictEqual(r[1], -1, 'losing everything IS a -100% day, not a null');
    assert.strictEqual(r[2], null, 'the day AFTER a wipeout has no defined return');
  });
});

test('pearson', async t => {
  await t.test('is 1 for a series against itself', () => {
    assert.strictEqual(series.pearson([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]), 1);
  });

  await t.test('is -1 when perfectly opposed', () => {
    assert.strictEqual(series.pearson([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]), -1);
  });

  await t.test('returns null for a flat series — undefined, not zero', () => {
    // A flat leg has no variance; calling that "uncorrelated" would make it look like a
    // perfect diversifier and rank it top of every component scan.
    assert.strictEqual(series.pearson([1, 2, 3], [2, 2, 2]), null);
  });

  await t.test('returns null when there is too little overlap to mean anything', () => {
    assert.strictEqual(series.pearson([1, 2], [1, 2]), null);
  });
});

test('correlate aligns on dates, not positions', async t => {
  const n = 120;
  const A = { dates: dates(n), cum: steady(n, 1) };
  // B starts 10 days later — position-alignment would compare different days.
  const B = { dates: dates(n).slice(10), cum: steady(n - 10, 1) };

  await t.test('uses only the shared days', () => {
    const { overlapDays } = series.correlate(A, B);
    assert.ok(overlapDays > 0 && overlapDays <= n - 10,
      `overlap ${overlapDays} should be bounded by the shorter series`);
  });

  await t.test('a series correlated with itself is 1', () => {
    const { corr } = series.correlate(A, A);
    assert.strictEqual(corr, 1);
  });
});

test('seriesKey', async t => {
  await t.test('is built from the ledger identity triple, never a backtestId', () => {
    const k = series.seriesKey('strategies/2026-05-12_foo-598050b9.py', 'train', 4);
    assert.match(k, /__train__e4$/);
    assert.ok(!k.includes('strategies/'), 'the directory prefix is redundant in a key');
  });

  await t.test('is stable for the same triple', () => {
    assert.strictEqual(
      series.seriesKey('strategies/a.py', 'train', 2),
      series.seriesKey('strategies/a.py', 'train', 2));
  });

  await t.test('separates epochs, because a result belongs to the bench that made it', () => {
    assert.notStrictEqual(
      series.seriesKey('strategies/a.py', 'train', 2),
      series.seriesKey('strategies/a.py', 'train', 4));
  });
});

test('maxDrawdownPct', async t => {
  await t.test('is zero for a monotonically rising curve', () => {
    assert.strictEqual(backfill.maxDrawdownPct(steady(50, 1)), 0);
  });

  await t.test('measures the peak-to-trough fall in equity terms', () => {
    // equity 1.00 -> 1.10 -> 0.99 : a 10% fall from the peak
    const cum = [0, 10, -1];
    assert.ok(Math.abs(backfill.maxDrawdownPct(cum) - 10) < 1e-6);
  });
});

test('backfill matching', async t => {
  // The row is annualized over the REQUESTED window; the curve spans actual trading days.
  const row = { start: '2022-01-01', end: '2023-12-31', days: 729,
                total: null, annual: 33.79, maxdd: 19.68 };
  const cand = { start: '2022-01-04', end: '2023-12-29',
                 totalPct: 78.86, maxddPct: 19.67,
                 annualPct: backfill.annualize(78.86, 724) };

  await t.test('matches despite the two sides spanning different day counts', () => {
    assert.ok(backfill.matches(row, cand),
      `should match; candidate self-annualized to ${cand.annualPct.toFixed(2)} vs row ${row.annual}`);
  });

  await t.test('the curve\'s own annualization really does differ by more than the tolerance', () => {
    // This is why the match key is re-annualized rather than taken from the fingerprint.
    assert.ok(Math.abs(cand.annualPct - row.annual) > backfill.TOL_PP);
  });

  await t.test('prefers total_pct exactly when the row has one', () => {
    assert.ok(backfill.matches({ ...row, total: 78.86 }, cand));
    assert.ok(!backfill.matches({ ...row, total: 91.0 }, cand));
  });

  await t.test('rejects a different window', () => {
    assert.ok(!backfill.matches({ ...row, start: '2024-01-01', end: '2025-12-31' }, cand));
  });

  await t.test('rejects a matching return with a different drawdown', () => {
    assert.ok(!backfill.matches(row, { ...cand, maxddPct: 31.0 }));
  });
});

test('reconcile', async t => {
  const curve = { backtestId: 'b1', start: '2022-01-04', end: '2023-12-29',
                  totalPct: 78.86, maxddPct: 19.68, points: 484,
                  annualPct: backfill.annualize(78.86, 724) };
  const base = { start: '2022-01-01', end: '2023-12-31', days: 729, total: 78.86,
                 annual: 33.79, maxdd: 19.68, epoch: '2' };

  await t.test('matches a single row to a single curve', () => {
    const r = backfill.reconcile([{ ...base, sourceFile: 'strategies/only.py' }], [curve]);
    assert.strictEqual(r.matched.length, 1);
    assert.strictEqual(r.ambiguous.length, 0);
  });

  await t.test('holds back a curve claimed by two DIFFERENT strategies', () => {
    // Neither file exists on disk, so no body hash can prove them identical — and an
    // unprovable duplicate must not be assigned. A wrong curve corrupts every correlation.
    const r = backfill.reconcile([
      { ...base, sourceFile: 'strategies/does-not-exist-a.py' },
      { ...base, sourceFile: 'strategies/does-not-exist-b.py' },
    ], [curve]);
    assert.strictEqual(r.matched.length, 0);
    assert.strictEqual(r.ambiguous.length, 2);
    for (const a of r.ambiguous) assert.match(a.reason, /DIFFERENT/);
  });

  await t.test('reports a row no curve explains as unmatched, not as a guess', () => {
    const r = backfill.reconcile([{ ...base, sourceFile: 'strategies/x.py', annual: -99, total: -99 }], [curve]);
    assert.strictEqual(r.unmatched.length, 1);
    assert.strictEqual(r.matched.length, 0);
  });
});

test('diversification decomposition', async t => {
  const n = 300;
  // Deterministic pseudo-random daily returns with a `drift` added to each day.
  const mk = (seed, drift = 0.0012) => {
    let s = seed, cum = [], eq = 1;
    for (let i = 0; i < n; i++) {
      s = (s * 1103515245 + 12345) % 2147483648;
      eq *= (1 + ((s / 2147483648) - 0.5) * 0.04 + drift);
      cum.push((eq - 1) * 100);
    }
    return { dates: dates(n), cum };
  };

  await t.test('ratio is 1.0 when a series is blended with itself — no diversification', () => {
    const A = mk(7);
    const d = scan.diversification([A, A]);
    assert.ok(d, 'expected a decomposition');
    assert.ok(Math.abs(d.ratio - 1) < 1e-6, `ratio should be 1, got ${d.ratio}`);
    assert.ok(Math.abs(d.meanCorr - 1) < 1e-6, `corr should be 1, got ${d.meanCorr}`);
  });

  await t.test('ratio exceeds 1 for imperfectly correlated members', () => {
    const d = scan.diversification([mk(7), mk(91)]);
    assert.ok(d.ratio > 1, `expected a diversification benefit, got ${d.ratio}`);
    assert.ok(d.meanCorr < 1);
  });

  await t.test('at rho=1 the same returns always carry more volatility', () => {
    const d = scan.diversification([mk(7), mk(91)]);
    assert.ok(d.weightedVolPct >= d.blendVolPct);
  });

  await t.test('strips the risk-side gain when the excess return is POSITIVE', () => {
    const d = scan.diversification([mk(7), mk(91)]);
    assert.ok(d.blend.annualPct / 100 > scan.RISK_FREE,
      'this case needs a positive excess return to be the right test');
    assert.ok(d.sharpeNoDiversification <= d.blend.sharpe + 1e-9,
      `${d.sharpeNoDiversification} should not exceed ${d.blend.sharpe}`);
  });

  await t.test('⚠ the comparison INVERTS when the excess return is negative', () => {
    // Dividing a negative excess return by a LARGER volatility moves it toward zero, so
    // stripping diversification RAISES the reported Sharpe. Any rule that reads
    // "sharpeNoDiversification below the best member" as evidence of a manufactured pass is
    // therefore only valid above the risk-free rate — which is why the guard checks first.
    const d = scan.diversification([mk(7, -0.002), mk(91, -0.002)]);
    assert.ok(d.blend.annualPct / 100 < scan.RISK_FREE);
    assert.ok(d.sharpeNoDiversification > d.blend.sharpe,
      `expected the inversion: ${d.sharpeNoDiversification} vs ${d.blend.sharpe}`);
  });

  await t.test('refuses to decompose a single member', () => {
    assert.strictEqual(scan.diversification([mk(7)]), null);
  });

  await t.test('refuses when the members barely overlap', () => {
    const short = { dates: dates(10), cum: steady(10, 1) };
    assert.strictEqual(scan.diversification([short, short]), null);
  });
});

test('familyToType parses the frontmatter list', async t => {
  const map = scan.familyToType();

  await t.test('no family name keeps a stray bracket', () => {
    // `families: [[[A]], [[B]]]` is a YAML list OF wiki links, so the FIRST entry carries three
    // opening brackets. Stripping only the `[[`/`]]` pairs left `[A`, so the first family of
    // every type never matched and its strategies fell into `(untyped)` — 33 of 71 of them.
    for (const name of Object.keys(map)) {
      assert.ok(!/[[\]]/.test(name), `family name "${name}" still carries a bracket`);
    }
  });

  await t.test('maps the families the type pages actually list',
    { skip: Object.keys(map).length === 0 }, () => {
      for (const [fam, type] of Object.entries(map)) {
        assert.ok(fam.length > 0 && type.length > 0);
        assert.ok(fs.existsSync(path.join(__dirname, '..', 'wiki/types', `${type}.md`)),
          `type ${type} has no page`);
      }
    });
});

test('component register', async t => {
  const comp = require('../utils/components');

  await t.test('refuses a claim with no evidence', () => {
    // The repo has already paid for guess-based rules: a screening hard-reject built on a
    // hunch permanently discarded 287 of 549 strategies.
    assert.throws(() => comp.record({
      source: 'strategies/a.py', aspect: 'atr-stop', kind: 'exit', claim: 'looks useful',
    }), /evidence is required/);
  });

  await t.test('refuses a kind outside the vocabulary', () => {
    assert.throws(() => comp.record({
      source: 'strategies/a.py', aspect: 'x', kind: 'vibes', claim: 'c', evidence: 'e',
    }), /unknown kind/);
  });

  await t.test('refuses a nameless source or aspect', () => {
    assert.throws(() => comp.record({ aspect: 'x', kind: 'exit', claim: 'c', evidence: 'e' }), /source is required/);
    assert.throws(() => comp.record({ source: 's', kind: 'exit', claim: 'c', evidence: 'e' }), /aspect is required/);
  });

  await t.test('the tracked file keeps its column contract', { skip: !fs.existsSync(comp.FILE) }, () => {
    const head = fs.readFileSync(comp.FILE, 'utf8').split('\n')[0].split('\t');
    assert.deepStrictEqual(head, comp.COLUMNS);
  });
});

test('stored series on disk', async t => {
  const keys = series.list();

  await t.test('every stored series carries the fields a decomposition needs',
    { skip: keys.length === 0 }, () => {
      for (const k of keys.slice(0, 40)) {
        const r = series.load(k);
        assert.ok(Array.isArray(r.dates) && Array.isArray(r.cum), `${k} missing arrays`);
        assert.strictEqual(r.dates.length, r.cum.length, `${k} dates/cum length mismatch`);
        assert.ok(r.dates.length > 0, `${k} is empty`);
      }
    });

  await t.test('none is stored under a bare backtestId — ids are re-minted per request',
    { skip: keys.length === 0 }, () => {
      for (const k of keys) assert.ok(!/^[a-f0-9]{32}$/.test(k), `${k} looks like a raw id`);
    });
});
