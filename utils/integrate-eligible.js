/**
 * integrate-eligible.js — the `/run-family` EXIT gate: may this family supply a candidate to
 * integration at all?
 *
 * User specification, 2026-10-16. Integration used to take any family carrying a measured edge,
 * which meant it could be handed a TRAIN-only number, or a book its own page says cannot be
 * traded, and then spend the round discovering that at the judge. Three requirements now have to
 * be met BEFORE a family reaches the integration step, so that step never has to re-litigate them:
 *
 *   1. a CHAMPION measured under an epoch the active one still accepts;
 *   2. a VALIDATION that PASSED — the one VAL per (family, epoch) cleared `stageGate('validate')`;
 *   3. REALIZABILITY >= 2, agent-scored and recorded on the family page.
 *
 * Requirement 3 is why integration's rule 4 becomes automatic: nothing with an untradeable leg
 * can arrive. The check stays in the guard as defence in depth, but it should never bind.
 *
 * ## Unknown BLOCKS, it does not permit
 *
 * A family with no `realizability:` is reported `blocked`, not eligible. Same rule the VAL budget
 * applies to its own unknown epoch, and for the same reason: blocking is visible and a human
 * clears it with one edit, whereas permitting silently lets an unrealizable book into the set a
 * universe ships. ⚠ Do NOT infer the score from the `不可实现` regex alone — 打板短线 does not
 * match it and was scored 1 on evidence (it buys the next-day open of yesterday's limit-ups, and
 * a sealed 一字板 cannot be bought at any price).
 *
 * Usage:
 *   const el = require('./integrate-eligible');
 *   el.assess('红利低频')     // { eligible, why, champion, val, realizability }
 *   node utils/integrate-eligible.js        # the whole library, grouped
 */

const fs = require('fs');
const path = require('path');
const harness = require('./harness-config');

const ROOT = path.resolve(__dirname, '..');
const FAM_DIR = () => process.env.JQ_FAMILIES_DIR || path.join(ROOT, 'wiki/families');
const PAGES = () => process.env.JQ_STRATEGY_PAGES || path.join(ROOT, 'wiki/strategies');
const LEDGER = () => process.env.JQ_LEDGER || path.join(ROOT, 'harness/normalize-train.tsv');

/** Minimum agent-scored realizability. 1 == fills a daily bar cannot honour. */
const MIN_REALIZABILITY = 2;

const fmField = (t, k) => {
  const m = t.match(new RegExp(`^${k}:\\s*(.*)$`, 'm'));
  return m ? m[1].trim() : '';
};

/** sourceFile -> family, from the strategy pages (the only place the assignment lives). */
function familyIndex() {
  const idx = {};
  let names = [];
  try { names = fs.readdirSync(PAGES()).filter(f => f.endsWith('.md')); } catch { return idx; }
  for (const f of names) {
    const t = fs.readFileSync(path.join(PAGES(), f), 'utf8');
    const fam = fmField(t, 'family'), src = fmField(t, 'sourceFile');
    if (fam && src) idx[src] = fam;
  }
  return idx;
}

/** The family's best-objective row measured under a comparable epoch. */
function championOf(family, idx) {
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
      best = { sourceFile: c[0], objective: obj, annual: parseFloat(c[8]),
               sharpe: parseFloat(c[9]), maxdd: parseFloat(c[10]), epoch: c[13] || null };
    }
  }
  return best;
}

/**
 * The family's one validation, if it both exists and PASSED.
 *
 * ⚠ `outcome` on a VAL consumption row is free text written by whichever loop recorded it
 * ("sharpe 2.05"), not a structured field — so the sharpe is parsed out of it and compared to the
 * live threshold rather than trusting a `pass`/`fail` word that may not be there.
 */
function validationOf(family) {
  let prior = [];
  try { prior = require('./val-budget').priorValidations(family); } catch { return { has: false }; }
  if (!prior.length) return { has: false };
  const last = prior[prior.length - 1];
  const comparable = harness.measurementValid(last.epoch || null);
  const m = String(last.outcome || '').match(/-?\d+(\.\d+)?/);
  const sharpe = m ? parseFloat(m[0]) : null;
  return {
    has: true, runId: last.runId, epoch: last.epoch || null, outcome: last.outcome,
    comparable, sharpe,
    passed: comparable && sharpe != null && harness.stageGate('validate', sharpe),
  };
}

/**
 * Is there a stored VAL-window curve under the CHAMPION's own key?
 *
 * Proof-by-artifact rather than by bookkeeping: `consumption.tsv` records that a VAL happened and
 * under which runId, but not which FILE it ran — whereas the series key is
 * `seriesKey(sourceFile, 'val', epoch)`, so a curve under the champion's key can only have come
 * from running the champion. When it is absent, the VAL-window curves that DO exist usually name
 * the book that was validated instead, which is the more useful half of the message.
 */
function championValidated(family, pageText) {
  let series;
  try { series = require('./backtest-series'); } catch { return { confirmed: false, why: 'no series module' }; }

  const base = (pageText.match(/^base:\s*\[\[([^\]]+)\]\]/m) || [])[1] || null;
  const best = (pageText.match(/^bestVariant:\s*\[\[([^\]]+)\]\]/m) || [])[1] || null;

  // Which book did the VAL actually run? The series key encodes it.
  const valKeys = series.list().filter(k => /__val__/.test(k));
  const mine = valKeys.filter(k => k.includes(`_${family}_`) || k.startsWith(`study_${family}_`));
  const onBase = mine.some(k => /^study_.+_baseline/.test(k));
  const onCandidate = valKeys.filter(k => /^enhance_candidates_/.test(k));

  if (onBase && base && best && base === best) {
    return { confirmed: true, ranOn: mine.join(', '),
             why: `the VAL ran on this family's study baseline, and base == bestVariant (${base}), ` +
                  'so the book that met the held-out window IS the champion' };
  }
  if (onBase && base && best && base !== best) {
    return { confirmed: false, ranOn: mine.join(', '),
             why: `the VAL ran on this family's BASE (${base}) but the champion is a different ` +
                  `member (${best}) — the base's held-out number says nothing about the champion` };
  }
  if (!mine.length && onCandidate.length) {
    return { confirmed: false, ranOn: onCandidate.join(', '),
             why: 'the only VAL-window curves are CONSTRUCTED candidates under enhance/candidates/, ' +
                  'which are never ledger rows and therefore never the champion' };
  }
  return { confirmed: false, ranOn: mine.join(', ') || null,
           why: 'no VAL-window curve can be tied to this champion' };
}

function assess(family) {
  const p = path.join(FAM_DIR(), `${family}.md`);
  if (!fs.existsSync(p)) return { family, eligible: false, status: 'unknown-family', why: 'no family page' };
  const t = fs.readFileSync(p, 'utf8');
  const universe = fmField(t, 'universe') || null;
  const rRaw = fmField(t, 'realizability');
  const realizability = rRaw === '' ? null : parseInt(rRaw, 10);
  const champion = championOf(family, familyIndex());
  const val = validationOf(family);

  const fail = (status, why) => ({ family, universe, status, eligible: false, why,
                                   champion, val, realizability });

  if (!universe) return fail('blocked', 'no universe: on the family page');
  if (!champion) {
    return fail('blocked',
      `no champion measured under epoch ${harness.config().epoch} — re-measure before integrating`);
  }
  if (!val.has) return fail('blocked', 'never validated — /run-family must finalize on VAL first');
  if (!val.comparable) {
    return fail('blocked', `its VAL (${val.runId}) was measured at epoch ${val.epoch}, which the ` +
                           'active epoch does not accept');
  }
  if (!val.passed) {
    return fail('rejected', `VAL ${val.runId} did not pass the ${harness.stageThreshold('validate')} ` +
                            `threshold (outcome: ${val.outcome})`);
  }

  // ⚠⚠ Did the VAL validate THIS champion, or a different book?
  //
  // This gate used to check "has a champion" and "has a passing VAL" INDEPENDENTLY, which silently
  // accepted a family whose validation was run on something else. Measured 2026-10-16:
  // 大小盘轮动's champion is the base 2f5bc859 (objective 0.4567) while its one VAL,
  // `dxp-imp-1-val`, ran on `enhance/candidates/dxp-imp-1.py` — the always-small variant
  // (objective 0.6623), a different file. Its own page says that adoption rests on TRAIN only
  // (「采纳依据只在 TRAIN」) and that imp-1's VAL drew down 36% where the base drew 18%. So the
  // family had no agreed candidate at all, and the gate was about to let an irreversible OOS test
  // be spent on a book nothing had validated.
  //
  // The evidence is the stored VAL-window curve: its key is seriesKey(sourceFile, 'val', epoch),
  // so a curve under the CHAMPION's key is proof the champion itself met the held-out window.
  // ⚠ Absence is treated as BLOCKING, not as permission — consistent with the unknown-blocks rule
  // the VAL budget uses. A human clears it in one command; permitting silently pairs a number with
  // a book that never produced it.
  const vc = championValidated(family, t);
  if (!vc.confirmed) {
    return fail('blocked',
      `its one VAL (${val.runId}) did not validate the CHAMPION: ${vc.why}. A validation of a ` +
      'different book is not a validation of this one, so the family has no agreed candidate to ' +
      'carry forward. Settle it on ONE book, or re-validate the champion (which needs the human ' +
      'VAL override, since the budget is spent).');
  }
  if (realizability == null || Number.isNaN(realizability)) {
    // Unknown blocks rather than permits — see the header.
    return fail('blocked', 'no realizability: on the family page. An agent must score it with ' +
                           'evidence; unknown blocks so that it is visible rather than assumed');
  }
  if (realizability < MIN_REALIZABILITY) {
    return fail('rejected', `realizability ${realizability} < ${MIN_REALIZABILITY} — a book whose ` +
                            'fills a daily bar cannot honour must not enter the shipping set');
  }
  return { family, universe, status: 'eligible', eligible: true,
           why: `champion ${champion.sourceFile} (sharpe ${champion.sharpe}), VAL ${val.runId} ` +
                `sharpe ${val.sharpe}, realizability ${realizability}`,
           champion, val, realizability };
}

/** Every family, assessed. Eligible ones first, ordered by CHAMPION TRAIN SHARPE (the run order). */
function all() {
  let names = [];
  try { names = fs.readdirSync(FAM_DIR()).filter(f => f.endsWith('.md')); } catch { return []; }
  const out = names.map(f => assess(f.replace(/\.md$/, '')));
  return out.sort((a, b) => {
    if (a.eligible !== b.eligible) return a.eligible ? -1 : 1;
    const sa = (a.champion && a.champion.sharpe) ?? -Infinity;
    const sb = (b.champion && b.champion.sharpe) ?? -Infinity;
    return sb - sa;
  });
}

if (require.main === module) {
  const rows = all();
  const groups = { eligible: [], rejected: [], blocked: [], 'unknown-family': [] };
  for (const r of rows) (groups[r.status] || (groups[r.status] = [])).push(r);
  console.log(`[eligible] /run-family exit gate — champion + passing VAL + realizability >= ${MIN_REALIZABILITY}`);
  console.log(`[eligible] active epoch ${harness.config().epoch}\n`);
  console.log(`■ ELIGIBLE (${groups.eligible.length}) — ordered by champion TRAIN sharpe, which is the run order`);
  for (const r of groups.eligible) {
    console.log(`   ${r.family.padEnd(12)} [${r.universe}]  sharpe ${r.champion.sharpe}  R=${r.realizability}`);
    console.log(`       ${r.why}`);
  }
  for (const k of ['rejected', 'blocked', 'unknown-family']) {
    if (!groups[k] || !groups[k].length) continue;
    console.log(`\n■ ${k.toUpperCase()} (${groups[k].length})`);
    for (const r of groups[k]) console.log(`   ${r.family.padEnd(12)} ${r.why}`);
  }
}

module.exports = { assess, all, championOf, validationOf, championValidated,
                   familyIndex, MIN_REALIZABILITY };
