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
 * The four rules, applied here:
 *   1. BEAT THE BEST MEMBER, not the gate. Clearing sharpe 2.5 is necessary and meaningless.
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

function check(c) {
  const members = c.members || [];
  if (members.length < 2) {
    return { verdict: 'invalid', reasons: ['an integration candidate needs at least 2 members'] };
  }

  const num = v => (v == null || isNaN(parseFloat(v)) ? null : parseFloat(v));
  const bestMember = members.reduce((a, b) => ((num(b.objective) ?? -Infinity) > (num(a.objective) ?? -Infinity) ? b : a));
  const bestSharpe = Math.max(...members.map(m => num(m.sharpe) ?? -Infinity));
  const meanAnnual = members.reduce((n, m) => n + (num(m.annual) ?? 0), 0) / members.length;
  const maxAnnual = Math.max(...members.map(m => num(m.annual) ?? -Infinity));
  const worstR = Math.min(...members.map(m => (m.realizability == null ? 5 : Number(m.realizability))));

  const cand = c.candidate || {};
  const reasons = [];
  const flags = [];
  let verdict = 'keep';

  // Rule 1 — beat the best member
  const beatsBest = (num(cand.objective) ?? -Infinity) > (num(bestMember.objective) ?? -Infinity);
  if (!beatsBest) {
    verdict = 'reject';
    reasons.push(`objective ${cand.objective} does not beat the best member ` +
                 `${bestMember.family} at ${bestMember.objective}`);
  }

  // Rule 2 — diversification share.
  //
  // Two levels of evidence. When the members' daily curves are stored (utils/backtest-series.js)
  // this is a real ATTRIBUTION: the decomposition says how much of the Sharpe is risk-side.
  // Without curves it falls back to the SIGNATURE test it has always been — sharpe up, return
  // not up — which detects the pattern but cannot quantify it.
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
  console.log(`  best member      : ${r.bestMember} (objective ${r.bestMemberObjective})`);
  console.log(`  uplift over it   : ${r.uplift >= 0 ? '+' : ''}${r.uplift.toFixed(4)}`);
  console.log(`  flags            : ${r.flags.join(', ')}`);
  for (const reason of r.reasons) console.log(`  - ${reason}`);
  process.exitCode = r.verdict === 'reject' || r.verdict === 'invalid' ? 1 : 0;
}

module.exports = { check, NOISE_PP };
