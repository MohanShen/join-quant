/**
 * type-integrate-check.js — the guard on a type-level integration candidate.
 *
 * Why a guard exists at all (docs/consolidation-plan.md §4.1). Blending raises Sharpe
 * mechanically whenever member correlation is below one, and the harness gate IS a Sharpe
 * threshold. This repo has measured it twice:
 *
 *   七星高照 — the blend scored sharpe 3.17 against 2.85 and 1.60 for its two legs, with
 *              volatility BELOW both. It clears the gate at objective 0.4814; one leg alone
 *              is disqualified. The study flagged that the headline is carried by the other leg.
 *   红利低频 — a two-factor conjunction returned 23.41% against 11.75% for the sum of its legs,
 *              at lower risk than either.
 *
 * So an integration round with no guard produces gate passes at will and adds no edge.
 *
 * The rules, applied here:
 *   0. THE STAGE GATE. `harness.stageGate('integrate', sharpe)` — necessary, never sufficient.
 *      ⚠⚠ This was MISSING. The guard applied rules 1-4 and never asked whether the candidate
 *      cleared the gate, so on the ETF round-2 candidates (2026-10-16) it returned `keep` at
 *      sharpe 0.94 and 0.91 against a threshold of 1.5 — only the agent's own reading caught it.
 *      Rule 1's slogan ("beat the MEMBER, not the gate") exists to stop a gate PASS being
 *      mistaken for success; it was never a licence to skip the gate. A companion flag,
 *      `all-parents-below-gate`, says when no parent clears it — a warning and NOT a veto,
 *      because a blend can mechanically exceed both parents whenever correlation < 1.
 *   1. BEAT THE BEST MEMBER, not the gate. Clearing the gate is necessary and meaningless.
 *      ⚠ Since harness epoch 7 this is a PER-YEAR comparison — the candidate's worst TRAIN
 *      calendar year against the most consistent member's worst TRAIN year (`harness.md` §4.1).
 *      It needs stored curves; without them it falls back to the pooled rule and SAYS SO.
 *   2. DECLARE THE DIVERSIFICATION SHARE. If the candidate's return does not exceed its
 *      members' while its Sharpe does, the gain is risk-side — that is diversification, not edge.
 *   3. EQUAL WEIGHT FIRST. An optimised weight must beat equal weight by more than measurement
 *      noise: re-running the same strategy moves annual return by ~0.15pp, so under 1pp is zero.
 *   4. CAPACITY IS ADDITIVE, EDGE IS NOT. The candidate inherits the WORST realizability of any
 *      member, never the average.
 *
 * ⚠ Limits of what this can decide. The ledger stores annual/sharpe/maxdd, not return series,
 * so correlation and a true variance decomposition are NOT computable here. Rule 2 is therefore
 * a *signature* test, not an attribution: it detects the classic diversification pattern
 * (Sharpe up, return not up). A candidate that passes still deserves the analyst's own
 * decomposition before it is called an edge.
 *
 * Usage:
 *   node utils/type-integrate-check.js <candidate.json>
 *
 * candidate.json:
 *   { "type": "小盘-H-high", "expId": "int-001", "weights": "equal" | {...},
 *     "candidate": { "annual": 61.2, "sharpe": 3.1, "maxdd": 12.0, "objective": 0.492 },
 *     "members":   [ { "family": "ETF动量", "annual": 51.1, "sharpe": 2.52, "maxdd": 12.71,
 *                      "objective": 0.383, "realizability": 3 }, … ],
 *     "equalWeightObjective": 0.478 }
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const LEDGER = () => process.env.JQ_LEDGER || path.join(ROOT, 'harness/normalize-train.tsv');
const PAGES = () => process.env.JQ_STRATEGY_PAGES || path.join(ROOT, 'wiki/strategies');

/**
 * sourceFile -> family. The assignment lives only on the strategy pages (`family:`), never in the
 * ledger, and is never auto-written — see CLAUDE.md on `family-match.js`.
 */
function familyIndex() {
  const idx = {};
  let names = [];
  try { names = fs.readdirSync(PAGES()).filter(f => f.endsWith('.md')); } catch { return idx; }
  for (const f of names) {
    const t = fs.readFileSync(path.join(PAGES(), f), 'utf8');
    const fam = (t.match(/^family:\s*(.*)$/m) || [])[1];
    const src = (t.match(/^sourceFile:\s*(.*)$/m) || [])[1];
    if (fam && src) idx[src.trim()] = fam.trim();
  }
  return idx;
}

/**
 * A family's CHAMPION: its best-objective row measured under an epoch the active one accepts.
 *
 * ⚠⚠ Why the guard derives this instead of trusting `members[].objective`. The bar is NOT a
 * caller input — rule 1 asks whether the merge beats what the universe would otherwise ship, and
 * what a universe otherwise ships is its best family's CHAMPION (that is literally what PROMOTE
 * does). The ETF round-2 agent supplied each family's study BASELINE as the member, which is the
 * right thing to DECOMPOSE a pipeline from and the wrong thing to be judged against:
 *
 *     ETF动量   base obj 0.1868 sharpe 1.41 worst-year -0.0072
 *               CHAMPION 0.4725 sharpe 2.23 worst-year +0.3673
 *     七星高照   base obj 0.1252 sharpe 1.21 worst-year -0.0651
 *               CHAMPION 0.3365 sharpe 2.54
 *
 * So the round ran against a bar of -0.0072 when the real alternative was +0.3673, and its
 * candidates were reported as +0.0274 uplift when against the champion they lose by ~0.35. It
 * also made both parents look like gate failures (1.41 / 1.21) when every ETF champion clears
 * 1.5. Same shape as the missing rule 0: the guard believed whatever it was handed.
 *
 * Deliberately reads the LEDGER and not `component-scan.members()`, which skips rows that have no
 * stored curve — that would have silently picked a lesser row as 七星高照's champion (its real one
 * has no curve) and understated the bar all over again, which is the very bug being fixed.
 */
function championOf(family, idx) {
  const harness = require('./harness-config');
  let text;
  try { text = fs.readFileSync(LEDGER(), 'utf8'); } catch { return null; }
  let best = null;
  for (const line of text.split('\n').slice(1)) {
    if (!line.trim()) continue;
    const c = line.split('\t');
    if (c[3] !== 'normalized') continue;
    if ((idx[c[0]] || null) !== family) continue;
    if (!harness.measurementValid(c[13] || null)) continue;
    const obj = c[11] === 'DQ' ? null : parseFloat(c[11]);
    if (!Number.isFinite(obj)) continue;
    if (!best || obj > best.objective) {
      best = { family, sourceFile: c[0], objective: obj,
               annual: parseFloat(c[8]), sharpe: parseFloat(c[9]), maxdd: parseFloat(c[10]),
               epoch: c[13] || null };
    }
  }
  return best;
}

/** Measured re-run noise in this repo: the same file shifted annual return by ~0.15pp. */
const NOISE_PP = 1.0;

/**
 * Load each member's stored daily curve and decompose the blend, when the curves exist.
 *
 * A member points at its series with `sourceFile` (+ optional `epoch`), the same identity the
 * ledger uses — never a backtestId, which JQ re-mints per request. Returns null when fewer
 * than two members have a curve, which is the signal to fall back to the signature test.
 */
function decomposeMembers(members) {
  try {
    const series = require('./backtest-series');
    const { diversification } = require('./component-scan');
    const loaded = [];
    for (const m of members) {
      if (!m.sourceFile) continue;
      const rec = series.load(m.seriesKey
        || series.seriesKey(m.sourceFile, m.window || 'train', m.epoch || require('./harness-config').config().epoch));
      if (rec) loaded.push(rec);
    }
    if (loaded.length < 2) return null;
    return diversification(loaded, null);
  } catch { return null; }
}

/**
 * Resolve one participant's stored curve. `sourceFile` is the ledger's identity — never a
 * backtestId, which JQ re-mints per request — and the epoch is resolved through
 * `loadComparable`, so a scoring-only bump does not orphan a curve measured one epoch ago.
 */
function curveOf(p) {
  if (!p) return null;
  const series = require('./backtest-series');
  if (p.seriesKey) return series.load(p.seriesKey);
  if (!p.sourceFile) return null;
  return series.loadComparable(p.sourceFile, p.window || 'train', p.epoch).rec;
}

/**
 * Rule 1 on the epoch-7 basis: the candidate's WORST TRAIN year must beat the best member's
 * worst TRAIN year, on the same (annual − maxDrawdown)/100 metric computed WITHIN each year.
 *
 * Why a maximin rather than "win every year": per-year domination lets one member own the bar
 * in 2022 and another own it in 2023, so a candidate can be rejected for losing to a PAIR that
 * no single member matches — which is not a comparison against any real alternative. The
 * maximin compares the most consistent member against the candidate's own weakest year.
 *
 * Returns null when the split cannot be built for the candidate or for EVERY member. Partial
 * member coverage is also a null: a bar computed over a subset silently omits whichever member
 * might have set it, and the strongest member is exactly the one most likely to be missing.
 */
function worstYearRule(c, members) {
  const cs = require('./component-scan');
  const candRec = curveOf({ ...(c.candidate || {}), window: 'train' });
  if (!candRec) return { ok: false, why: 'the candidate has no stored TRAIN curve' };

  const candWorst = cs.worstYear(candRec, 'train');
  if (!candWorst) return { ok: false, why: 'the candidate curve does not cover every TRAIN year' };

  const perMember = [];
  for (const m of members) {
    const rec = curveOf({ ...m, window: 'train' });
    const w = rec && cs.worstYear(rec, 'train');
    if (!w) return { ok: false, why: `member ${m.family} has no usable TRAIN curve` };
    perMember.push({ family: m.family, worst: w });
  }
  if (!perMember.length) return { ok: false, why: 'no members carry a curve' };

  const best = perMember.reduce((a, b) => (b.worst.objective > a.worst.objective ? b : a));
  return {
    ok: true,
    candWorst,
    bestMember: best.family,
    bestWorst: best.worst,
    beats: candWorst.objective > best.worst.objective,
    perMember,
  };
}

function check(c) {
  const harness = require('./harness-config');
  const members = c.members || [];
  if (members.length < 2) {
    return { verdict: 'invalid', reasons: ['an integration candidate needs at least 2 members'] };
  }

  const num = v => (v == null || isNaN(parseFloat(v)) ? null : parseFloat(v));

  const cand = c.candidate || {};
  const reasons = [];
  const flags = [];
  let verdict = 'keep';

  // Resolve the BAR from each family's champion, keeping the caller's realizability call (that
  // one IS a reading of the family page, not a ledger fact). The caller's figures are kept for
  // reporting so an understated bar is visible rather than quietly corrected.
  const idx = familyIndex();
  const resolved = members.map(m => {
    const champ = m.family ? championOf(m.family, idx) : null;
    const supplied = { objective: num(m.objective), sharpe: num(m.sharpe), annual: num(m.annual),
                       maxdd: num(m.maxdd), sourceFile: m.sourceFile || null,
                       epoch: m.epoch == null ? null : m.epoch };
    // The champion wins when we can resolve one; otherwise the caller's figure, flagged.
    const use = champ || { ...supplied, family: m.family };
    return { family: m.family, supplied, champion: champ, use,
             realizability: m.realizability == null ? 5 : Number(m.realizability),
             window: m.window || 'train', seriesKey: m.seriesKey || null };
  });

  const UNDERSTATED_PP = 0.01;   // 1pp of objective — comfortably above re-run noise (~0.0015)
  for (const r of resolved) {
    if (!r.champion) {
      flags.push(`champion-unresolved:${r.family}`);
      reasons.push(`⚠ could not resolve a CHAMPION for ${r.family} from the ledger (no row ` +
                   `valid under epoch ${harness.config().epoch}), so the bar falls back to the ` +
                   "figure you supplied. Verify it IS the family's best before trusting the verdict.");
      continue;
    }
    const gap = (r.champion.objective ?? -Infinity) - (r.supplied.objective ?? -Infinity);
    if (Number.isFinite(gap) && gap > UNDERSTATED_PP) {
      flags.push(`member-below-champion:${r.family}`);
      reasons.push(`⚠⚠ the member you supplied for ${r.family} (objective ${r.supplied.objective}, ` +
                   `sharpe ${r.supplied.sharpe}) is NOT its champion (${r.champion.objective}, ` +
                   `sharpe ${r.champion.sharpe}, ${r.champion.sourceFile}). The bar is what the ` +
                   'universe would otherwise SHIP, so the champion sets it — judged against the ' +
                   'champion instead. Build from the base if that is what decomposes; be judged ' +
                   'against the best.');
    }
  }

  const barMembers = resolved.map(r => ({ ...r.use, family: r.family }));
  const bestMember = barMembers.reduce((a, b) =>
    ((num(b.objective) ?? -Infinity) > (num(a.objective) ?? -Infinity) ? b : a));
  // ⚠ Two different aggregates, kept apart on purpose:
  //   bar-side  (barMembers / champions) — rule 1: what the universe would otherwise ship.
  //   leg-side  (supplied)               — rule 2: attribution among the things combined.
  // Collapsing them is how the bar got understated in the first place.
  const bestSharpe = Math.max(...resolved.map(r => r.supplied.sharpe ?? -Infinity));
  const maxAnnual = Math.max(...resolved.map(r => r.supplied.annual ?? -Infinity));
  const worstR = Math.min(...resolved.map(r => r.realizability));

  // Rule 0 — the STAGE GATE. Necessary, never sufficient.
  //
  // ⚠⚠ The guard never checked this. It applied rules 1-4 and returned `keep` for a candidate
  // whose sharpe was nowhere near the bar: measured on the ETF round-2 candidates (2026-10-16),
  // etf-m2-c1 and c2 were returned as KEEP at sharpe 0.94 and 0.91 against a threshold of 1.5.
  // Only the agent's own reading caught it. The doctrine "beat the best MEMBER, not the gate"
  // was written to stop a gate pass being mistaken for success — it was never a licence to skip
  // the gate, and the guard is the one place that cannot be relied on to remember that.
  const gateMin = harness.stageThreshold('integrate');
  const candSharpe = num(cand.sharpe);
  if (!harness.stageGate('integrate', cand.sharpe)) {
    verdict = 'reject';
    flags.push('below-stage-gate');
    reasons.push(`sharpe ${cand.sharpe} is below the integrate stage gate of ${gateMin} — ` +
                 'a candidate that fails the gate is not shippable whatever it does to the bar');
  }

  // Whether the PARENTS could ever produce a usable merge. Not a veto: a blend can mechanically
  // exceed both parents' sharpe whenever their correlation is below 1 — that is the exact trap
  // rule 2 exists for — so "both parents fail" does not imply the candidate must. But a round
  // whose every parent fails the gate is spending backtest minutes on a ceiling it cannot clear,
  // and it should see that said out loud rather than infer it from three rejections.
  // ⚠ Measured on the CHAMPIONS, not on whatever legs the caller merged. Judged on the supplied
  // legs this fired for ETF round 2 (bases at sharpe 1.41 / 1.21) while every ETF champion clears
  // 1.5 — a false alarm that would have read as "this universe is hopeless" when the truth was
  // "you merged the wrong things". The `member-below-champion` flag says that instead.
  const belowGate = barMembers.filter(m => !harness.stageGate('integrate', m.sharpe));
  if (belowGate.length === barMembers.length) {
    flags.push('all-parents-below-gate');
    reasons.push(`⚠ every family CHAMPION is below the ${gateMin} gate ` +
                 `(${barMembers.map(m => `${m.family} ${m.sharpe}`).join(', ')}) — no merge of ` +
                 'these parents is usable unless it clears a bar no champion reaches, which is ' +
                 'precisely the pattern rule 2 treats as risk-side rather than edge');
  }

  // Rule 1 — beat the best member. WHAT "beat" means is the active epoch's call.
  const bar = harness.integrateBar();
  const beatsPooled = (num(cand.objective) ?? -Infinity) > (num(bestMember.objective) ?? -Infinity);
  let rule1 = null;

  // Against the CHAMPIONS, not the legs the caller merged — the bar is the alternative the
  // universe would otherwise ship.
  if (bar.basis === 'worstTrainYear') rule1 = worstYearRule(c, barMembers);

  if (rule1 && rule1.ok) {
    flags.push('bar=worstTrainYear');
    reasons.push(`worst TRAIN year: candidate ${rule1.candWorst.year} at ` +
                 `${rule1.candWorst.objective} (annual ${rule1.candWorst.annualPct}%, maxDD ` +
                 `${rule1.candWorst.maxddPct}%) vs the most consistent member ${rule1.bestMember} ` +
                 `${rule1.bestWorst.year} at ${rule1.bestWorst.objective}`);
    if (!rule1.beats) {
      verdict = 'reject';
      reasons.push(`worst-year objective ${rule1.candWorst.objective} does not beat ` +
                   `${rule1.bestMember} at ${rule1.bestWorst.objective}`);
    }
    // The pooled comparison stays VISIBLE but no longer vetoes: it is almost purely annual
    // return (r=0.9698) and annual return over TRAIN is substantially a 2022 measurement
    // (2022 supplies a median 62% of log-growth), so a merge that buys consistency rather
    // than level loses on it by construction. Epoch 7 demoted it to evidence.
    if (!beatsPooled) {
      flags.push('pooled-objective-lower');
      reasons.push(`⚠ pooled objective ${cand.objective} is below ${bestMember.family}'s ` +
                   `${bestMember.objective} — under epoch ${harness.config().epoch} that is ` +
                   'reported, not a rejection (bar.pooledIsVeto=false); the candidate wins on ' +
                   'consistency and gives up level, so say which one the round was after');
    }
  } else {
    // Fallback is the POOLED rule, and it must announce itself. A bar that quietly relaxes
    // because a file was missing is worse than one that is simply strict.
    flags.push('bar=pooled-fallback');
    if (rule1 && rule1.why) {
      reasons.push(`⚠ could not apply the epoch-${harness.config().epoch} worst-year bar — ` +
                   `${rule1.why}; falling back to the pooled objective. Capture the missing ` +
                   'curve (node utils/series-backfill.js --dry) and re-run before trusting this.');
    }
    if (!beatsPooled) {
      verdict = 'reject';
      reasons.push(`objective ${cand.objective} does not beat the best member ` +
                   `${bestMember.family} at ${bestMember.objective}`);
    }
  }

  // Rule 2 — diversification share.
  //
  // Two levels of evidence. When the members' daily curves are stored (utils/backtest-series.js)
  // this is a real ATTRIBUTION: the decomposition says how much of the Sharpe is risk-side.
  // Without curves it falls back to the SIGNATURE test it has always been — sharpe up, return
  // not up — which detects the pattern but cannot quantify it.
  // ⚠ Rule 2 stays on the SUPPLIED legs, deliberately — it asks whether the candidate's sharpe
  // gain is explained by diversification among the things actually combined. That is a
  // different question from rule 1's bar, which is the alternative we would otherwise ship.
  const decomp = decomposeMembers(members);
  const sharpeUp = (num(cand.sharpe) ?? 0) > bestSharpe;
  const returnUp = (num(cand.annual) ?? 0) > maxAnnual;

  if (decomp) {
    flags.push(`meanCorr=${decomp.meanCorr}`, `diversificationRatio=${decomp.ratio}`);
    const noDiv = decomp.sharpeNoDiversification;
    reasons.push(`decomposition over ${decomp.overlapDays} shared days: mean member correlation ` +
                 `${decomp.meanCorr}, diversification ratio ${decomp.ratio}; at ρ=1 the same ` +
                 `returns would earn sharpe ${noDiv} against the candidate's ${cand.sharpe}`);
    // ⚠ Only meaningful ABOVE the risk-free rate. A negative excess return divided by the
    // LARGER rho=1 volatility moves toward zero, so stripping diversification would RAISE the
    // reported Sharpe and the test below would read backwards.
    const excessPositive = decomp.blend && (decomp.blend.annualPct / 100) > 0.04;
    // If the candidate only clears the bar thanks to the risk side, say so — that is the
    // manufactured pass this guard exists to catch (七星高照: blend 3.17 vs legs 2.85 / 1.60).
    if (excessPositive && noDiv != null && num(cand.sharpe) != null && noDiv < bestSharpe) {
      flags.push('diversification-explained');
      reasons.push(`strip the diversification and sharpe (${noDiv}) falls below the best member's ` +
                   `${bestSharpe} — the gain is risk-side, not edge`);
      if (verdict === 'keep') verdict = 'keep-with-caveat';
    }
  } else if (sharpeUp && !returnUp) {
    flags.push('diversification-explained', 'no-series');
    reasons.push(`sharpe rose (${cand.sharpe} > ${bestSharpe}) while annual did not ` +
                 `(${cand.annual} <= ${maxAnnual}) — that is the diversification signature, ` +
                 'not evidence of edge; store the members\' series for a real decomposition');
    if (verdict === 'keep') verdict = 'keep-with-caveat';
  }

  // Rule 3 — optimised weights must clear the noise floor
  if (c.weights && c.weights !== 'equal') {
    const ew = num(c.equalWeightObjective);
    if (ew == null) {
      verdict = 'reject';
      reasons.push('optimised weights submitted without an equal-weight baseline to compare against');
    } else {
      const gainPP = ((num(cand.objective) ?? 0) - ew) * 100;
      if (gainPP < NOISE_PP) {
        verdict = 'reject';
        reasons.push(`optimised weights beat equal weight by ${gainPP.toFixed(2)}pp, ` +
                     `below the ${NOISE_PP}pp measurement-noise floor — use equal weight`);
      }
    }
  }

  // Rule 4 — realizability is inherited at its worst
  if (worstR <= 1) {
    verdict = 'reject';
    reasons.push(`a member has realizability ${worstR}; the blend inherits it (capacity is ` +
                 'additive, edge is not)');
  }
  flags.push(`realizability=${worstR}`);

  return {
    verdict, reasons, flags,
    stageGate: { min: gateMin, candidate: candSharpe, passes: harness.stageGate('integrate', cand.sharpe) },
    bar: bar.basis,
    barApplied: rule1 && rule1.ok ? 'worstTrainYear' : 'pooled',
    // The binding comparison under the active epoch, when it could be made.
    worstYear: rule1 && rule1.ok ? {
      candidate: rule1.candWorst, member: rule1.bestMember, memberWorst: rule1.bestWorst,
      uplift: Number((rule1.candWorst.objective - rule1.bestWorst.objective).toFixed(4)),
      perMember: rule1.perMember,
    } : null,
    // The pooled comparison, kept for continuity with pre-epoch-7 rounds.
    bestMember: bestMember.family,
    bestMemberObjective: num(bestMember.objective),
    uplift: (num(cand.objective) ?? 0) - (num(bestMember.objective) ?? 0),
  };
}

if (require.main === module) {
  const f = process.argv[2];
  if (!f) { console.error('usage: node utils/type-integrate-check.js <candidate.json>'); process.exit(2); }
  const c = JSON.parse(fs.readFileSync(f, 'utf8'));
  const r = check(c);
  console.log(`[integrate] ${c.type || '?'} ${c.expId || ''} -> ${r.verdict.toUpperCase()}`);
  console.log(`  stage gate       : sharpe ${r.stageGate.candidate} vs ${r.stageGate.min} -> ` +
              `${r.stageGate.passes ? 'pass' : 'FAIL (necessary, not sufficient)'}`);
  console.log(`  bar applied      : ${r.barApplied}${r.barApplied === r.bar ? '' : `  (epoch asks for ${r.bar})`}`);
  if (r.worstYear) {
    const w = r.worstYear;
    console.log(`  worst TRAIN year : candidate ${w.candidate.year} ${w.candidate.objective} ` +
                `vs ${w.member} ${w.memberWorst.year} ${w.memberWorst.objective}`);
    console.log(`  worst-year uplift: ${w.uplift >= 0 ? '+' : ''}${w.uplift.toFixed(4)}   <- the binding comparison`);
    for (const m of w.perMember) {
      console.log(`      ${m.family.padEnd(14)} worst ${m.worst.year}  objective ${m.worst.objective}`);
    }
  }
  console.log(`  pooled (evidence): best member ${r.bestMember} ${r.bestMemberObjective}, ` +
              `uplift ${r.uplift >= 0 ? '+' : ''}${r.uplift.toFixed(4)}`);
  console.log(`  flags            : ${r.flags.join(', ')}`);
  for (const reason of r.reasons) console.log(`  - ${reason}`);
  process.exitCode = r.verdict === 'reject' || r.verdict === 'invalid' ? 1 : 0;
}

module.exports = { check, NOISE_PP };
