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
const ledger = require('./ledger');

const ROOT = path.resolve(__dirname, '..');
const FAM_DIR = () => process.env.JQ_FAMILIES_DIR || path.join(ROOT, 'wiki/families');
const PAGES = () => process.env.JQ_STRATEGY_PAGES || path.join(ROOT, 'wiki/strategies');
const LEDGER = () => process.env.JQ_LEDGER || path.join(ROOT, 'harness/normalize-train.tsv');
const SHELF = () => process.env.JQ_VALIDATED_DIR || path.join(ROOT, 'validated_strategies');

/** Minimum agent-scored realizability. 1 == fills a daily bar cannot honour. */
const MIN_REALIZABILITY = 2;

const { field: fmField } = require('./frontmatter');

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
  let best = null;
  // ⚠ Columns come from `utils/ledger.js`, not from numeric indices. This loop read c[8]..c[13]
  // directly, as seven other files did, so a column inserted into normalize-*.tsv would have
  // silently turned `sharpe` into `annual_pct` here — in the function that decides what a
  // universe would otherwise ship.
  for (const r of ledger.normalized()) {
    if ((idx[r.sourceFile] || null) !== family) continue;
    if (!harness.measurementValid(r.epoch)) continue;
    if (typeof r.objective !== 'number') continue;   // null, or the literal 'DQ'
    if (!best || r.objective > best.objective) {
      best = { sourceFile: r.sourceFile, objective: r.objective, annual: r.annual_pct,
               sharpe: r.sharpe, maxdd: r.maxdd_pct, epoch: r.epoch };
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
/**
 * The family's VALIDATED PRODUCT, read off the product shelf (`validated_strategies/`).
 *
 * ⚠⚠ Why this exists, and the bug it fixes. `championOf` reads the normalize LEDGER, which tracks
 * only INGESTED community strategies (`strategies/*.py`). A book the research loop BUILT can
 * therefore never appear there — so for a family whose best work is a constructed candidate, the
 * "champion" was the best ingested MEMBER, which is a different thing entirely.
 *
 * Measured 2026-10-16: 大小盘轮动's shelf holds `dxp-imp-1.py` with
 * `train_objective: 0.6623` against the base's 0.4567, `sharpe_val: 1.88`, `gate_val: pass` —
 * i.e. the family WAS settled, on TRAIN, validated and archived with full provenance. I had
 * promoted the base instead, then saw the VAL did not match it and wrongly concluded the family
 * had no agreed candidate. The family was fine; the champion definition was wrong.
 *
 * Re-measured on this bench 2026-10-16, imp-1 reproduces its claim exactly (total 226.83%,
 * annual 80.93%, sharpe 3.51, maxDD 14.70% ⇒ objective 0.6623) and dominates the base in BOTH
 * TRAIN years (3.02/3.86 against 2.38/2.82), so TRAIN selects it with no appeal to VAL.
 *
 * The shelf's own header is the link: `# family:`, `# expId:`, `# harness_epoch:`, `# gate_val:`.
 * Only an artifact measured on a comparable bench AND recorded `gate_val: pass` is usable.
 */
function shelfProductOf(family) {
  let names = [];
  try { names = fs.readdirSync(SHELF()).filter(f => f.endsWith('.py')); } catch { return null; }
  const found = [];
  for (const n of names) {
    const src = fs.readFileSync(path.join(SHELF(), n), 'utf8');
    // ⚠ The header pads its values and often appends a parenthetical gloss, e.g.
    //   `# family:   大小盘轮动   (source base: strategies/…)`
    // so the captured text is the WHOLE rest of the line. Take the first field — up to a run of
    // two spaces or an opening paren — or the comparison never matches and the shelf reads empty.
    const raw = k => ((src.match(new RegExp(`^#\\s*${k}:\\s*(.+)$`, 'm')) || [])[1] || '').trim();
    const g = k => raw(k).split(/\s{2,}|\s*\(/)[0].trim();
    if (g('family') !== family) continue;
    found.push({
      kind: 'product',
      sourceFile: `validated_strategies/${n}`,
      expId: g('expId') || n.replace(/\.py$/, ''),
      epoch: g('harness_epoch') || null,
      gateVal: g('gate_val').split(/\s+/)[0],
      objective: parseFloat(g('train_objective')),
      sharpeVal: parseFloat(g('sharpe_val')),
      // ⚠ The shelf has no dedicated TRAIN-sharpe field; it sits inside the train_objective
      // gloss, e.g. `0.6623   (TRAIN …: total 226.83% / annual 80.93% / maxDD 14.70% / sharpe 3.51…)`.
      // Without it a product sorts with `sharpe: undefined`, and arrival ORDER is the load-bearing
      // part of the incremental model — the first arrival defines what everything after must beat.
      // Falls back to the objective so an unparseable gloss can never sort a product FIRST by
      // accident; it sorts low and is visible.
      sharpe: (() => {
        const m = raw('train_objective').match(/sharpe\s+(-?\d+(?:\.\d+)?)/i);
        return m ? parseFloat(m[1]) : null;
      })(),
    });
  }
  if (!found.length) return null;
  const usable = found.filter(x => harness.measurementValid(x.epoch) && x.gateVal === 'pass');
  if (!usable.length) return { unusable: found };
  // Best TRAIN objective among usable products.
  return usable.sort((a, b) => (b.objective || -Infinity) - (a.objective || -Infinity))[0];
}

/**
 * Did the recorded VAL validate THIS candidate?
 *
 * Two shapes, because a candidate can be a shelf PRODUCT or a ledger MEMBER:
 *   - product: the VAL's `runId` must reference the product's `expId` (dxp-imp-1 -> dxp-imp-1-val).
 *   - member: the VAL must have run on the family's study baseline AND `base == bestVariant`, so
 *     that the validated book IS the champion. A VAL on an `enhance/candidates/*` book never
 *     validates a ledger member, because a constructed candidate is never a ledger row.
 *
 * ⚠ An exact series-key match can never confirm a MEMBER: a VAL runs on a pinned
 * `study/<fam>/baseline*.py`, never on the raw `strategies/*.py` the ledger keys on.
 */
function candidateValidated(family, pageText, candidate, val) {
  if (candidate && candidate.kind === 'product') {
    // ⚠ The runId convention is not one shape. Observed: `dxp-imp-1-val` and `xsz-imp-5-val`
    // SUFFIX the token, while `pt-val-base-e6` and `dbdx-VAL-base-e6` INFIX it, and `etfmom-005`
    // omits it entirely. A plain `includes(expId)` therefore missed two products whose VAL was
    // perfectly well recorded. Normalise by deleting the `val` token and collapsing separators,
    // so pt-val-base-e6 -> pt-base-e6 and dxp-imp-1-val -> dxp-imp-1.
    const norm = x => String(x || '').toLowerCase()
      .replace(/[-_]?val[-_]?/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
    const ok = norm(val.runId) === norm(candidate.expId)
      || String(val.runId || '').includes(candidate.expId);
    return ok
      ? { confirmed: true, why: `VAL ${val.runId} references the product's expId ${candidate.expId}` }
      : { confirmed: false, why: `VAL ${val.runId} does not reference the product's expId ` +
                                 `${candidate.expId}, so it validated some other book` };
  }
  let series;
  try { series = require('./backtest-series'); } catch { return { confirmed: false, why: 'no series module' }; }
  const base = (pageText.match(/^base:\s*\[\[([^\]]+)\]\]/m) || [])[1] || null;
  const best = (pageText.match(/^bestVariant:\s*\[\[([^\]]+)\]\]/m) || [])[1] || null;
  const valKeys = series.list().filter(k => /__val__/.test(k));
  const onBase = valKeys.some(k => new RegExp(`^study_${family}_baseline`).test(k));
  if (onBase && base && best && base === best) {
    return { confirmed: true, why: `the VAL ran on this family's study baseline and base == bestVariant (${base})` };
  }
  if (onBase && base && best && base !== best) {
    return { confirmed: false, why: `the VAL ran on this family's BASE (${base}) but the champion is ` +
                                    `a different member (${best})` };
  }
  return { confirmed: false, why: 'no VAL-window curve can be tied to this candidate' };
}

function assess(family) {
  const p = path.join(FAM_DIR(), `${family}.md`);
  if (!fs.existsSync(p)) {
    return { family, eligible: false, status: 'unknown-family', why: 'no family page', owner: 'none' };
  }
  const t = fs.readFileSync(p, 'utf8');
  const universe = fmField(t, 'universe') || null;
  const rRaw = fmField(t, 'realizability');
  const realizability = rRaw === '' ? null : parseInt(rRaw, 10);
  const member = championOf(family, familyIndex());
  const shelf = shelfProductOf(family);
  const product = shelf && !shelf.unusable ? shelf : null;
  // The family's CANDIDATE is its validated product when it has one; otherwise its best ingested
  // member. A product is the thing the research loop finalised, so it outranks a member even when
  // the member's ledger objective is lower — the ledger simply cannot hold a constructed book.
  const candidate = product || member;
  const val = validationOf(family);
  const realizabilityScope = fmField(t, 'realizabilityScope') || null;
  // A round that decides NOT to spend the family's one validation records it here. `valDeclined`
  // is the epoch it was decided under (provenance only — see the gate below for why it does not
  // expire); `valDeclinedBasis` is the reason, and a decline without one is reported as such
  // rather than silently trusted.
  const valDeclinedAt = fmField(t, 'valDeclined') || null;
  const valDeclinedBasis = fmField(t, 'valDeclinedBasis') || null;
  const valDeclined = !!valDeclinedAt;

  /**
   * ⚠ `owner` — WHICH STAGE can clear this block. Not decoration: `utils/family-queue.js` reopens
   * a family for research when its gate block is owned by `research`, and without it those
   * families were stranded in silence. Measured 2026-10-17: 8 of 13 families were `blocked` here
   * while the research queue read **0 due** — a family researched to exhaustion but never
   * validated reads `done` to the research queue, and nothing in the pipeline could ever notice
   * that integration was waiting on a step only `/run-family` performs.
   *
   * | owner | meaning |
   * |---|---|
   * | `research` | `/run-family` clears it unattended — a missing field, a VAL it may still spend |
   * | `normalize` | needs a measurement under the active epoch; the family itself is fine |
   * | `human` | needs a protected override (`JQ_ALLOW_REVAL`) or a judgement call |
   * | `none` | nothing to clear — a measured REJECTION, not a missing step |
   *
   * ⚠ `none` and `human` must never be reopened. An R=1 family re-entered every day would spin
   * the loop forever on a decision already taken, and a block the loop cannot clear would make
   * every run exit having done nothing — this repo's recurring failure shape.
   */
  const fail = (status, why, owner) => ({ family, universe, status, eligible: false, why, owner,
                                          candidate, member, product, val, realizability,
                                          champion: candidate });

  if (!universe) return fail('blocked', 'no universe: on the family page', 'research');
  if (!candidate) {
    return fail('blocked',
      `no candidate: nothing on the product shelf for this family, and no member measured under ` +
      `epoch ${harness.config().epoch}`, 'normalize');
  }
  if (!product && shelf && shelf.unusable) {
    return fail('blocked',
      `its shelf product(s) (${shelf.unusable.map(x => `${x.expId} epoch ${x.epoch} gate ${x.gateVal}`).join('; ')}) ` +
      'are not usable on this bench, and the best ingested member is not the finalised book — ' +
      're-measure the product or re-finalise the family', 'research');
  }
  if (!val.has) {
    // ⚠⚠⚠ "No VAL row" does NOT mean "nobody has done this step yet".
    //
    // The `owner: 'research'` reopening added 2026-10-17 treated it as a to-do, and
    // `family-queue` duly reopened four families. Checked against what those families had
    // actually recorded, it was wrong for **4 of 4** — every one had already decided not to spend
    // its one validation, with the reason written down:
    //
    //   七星高照   「BLOCKED 是正确状态，不是待办」 — champion is a cross-family blend whose
    //              realizability does not transfer, and the pit-pool precondition FAILED, so no
    //              level number including VAL can be read as mechanism evidence
    //   五福闹新春  「不配花家族唯一一次验证」 — every built candidate is dominated by member
    //              73b13d92, and the weak-period pool post-dates the VAL window
    //   多因子ML   「没有 improve 候选…留给未来的候选」 — and VAL 2024–25 is probably IN-sample
    //              for the author (post dated 2026-02, ETF pool assembled in hindsight)
    //   趋势技术   「没有候选过 1.5 闸门…留给下一个能过闸的候选」
    //
    // A dispatch would have told a session to "finalize on VAL — one run" and spent an
    // irreversible per-(family, epoch) resource on a book that family's own round judged unworthy.
    // It was caught with the run already live and the session already briefed; nothing was spent.
    //
    // Two defences, in order of how much they can be trusted:

    // 1. DERIVED. A candidate that does not clear the validate gate on TRAIN is never worth a
    //    validation, whatever anyone recorded. No field needed and nothing to keep in sync.
    //    (Catches 趋势技术, whose candidate is sharpe -0.63.)
    if (candidate.sharpe == null || !harness.stageGate('validate', candidate.sharpe)) {
      return fail('blocked',
        `never validated, and its candidate ${candidate.sourceFile} ` +
        `(sharpe ${candidate.sharpe ?? 'unknown'}) does not clear the ` +
        `${harness.stageThreshold('validate')} validate gate — so there is nothing worth the ` +
        'family\'s one validation. Not a research to-do: the loop would have to produce a ' +
        'gate-clearing candidate first, and THAT reopens via new-members.', 'none');
    }

    // 2. DECLARED. The other three declined for reasons about the DATA, not the ledger — a
    //    hindsight-selected pool, a VAL window that is the author's own sample, a candidate
    //    dominated by an existing member. None of that is derivable, so the round that decides
    //    records it and this gate honours it.
    //    ⚠ Deliberately NOT epoch-scoped. Three of the four reasons do not change when the bench
    //    changes, so expiring the decline on an epoch bump would re-dispatch a session to
    //    re-derive the same answer — the non-convergence this whole clause exists to stop. What
    //    DOES reopen the family is a new member (`family-queue`'s own `new-members` reason, which
    //    does not consult this gate), because a new member can change the champion. Clearing it
    //    otherwise is a deliberate edit.
    if (valDeclined) {
      return fail('blocked',
        `never validated, and the research loop DECLINED to spend it${valDeclinedAt ? ` (epoch ${valDeclinedAt})` : ''}: ` +
        `${valDeclinedBasis || 'no basis recorded ⚠'}. A reasoned decision, not a missing step — ` +
        'reopening it would ask the loop to spend an irreversible validation on a book it already ' +
        'judged unworthy. A new member reopens the family on its own.', 'none');
    }

    return fail('blocked', 'never validated — /run-family must finalize on VAL first', 'research');
  }
  if (!val.comparable) {
    // ⚠ Whether the loop can fix this is the VAL BUDGET's answer, not ours. A VAL on a bench the
    // active epoch rejects does NOT block a fresh one (`sameBench` is false), so research can
    // simply re-validate — but a VAL with no recorded epoch is UNKNOWN, and unknown blocks, so
    // only a human with JQ_ALLOW_REVAL can move it. Asking the budget keeps that rule in one
    // place instead of re-deriving it here and drifting.
    let canReval = false;
    try { canReval = !!require('./val-budget').check(family).allowed; } catch { canReval = false; }
    return fail('blocked', `its VAL (${val.runId}) was measured at epoch ${val.epoch}, which the ` +
                           'active epoch does not accept' +
                           (canReval ? ' — the VAL budget allows a fresh one'
                                     : ' — and the VAL budget refuses a fresh one, so this needs ' +
                                       'the human override'),
                canReval ? 'research' : 'human');
  }
  if (!val.passed) {
    return fail('rejected', `VAL ${val.runId} did not pass the ${harness.stageThreshold('validate')} ` +
                            `threshold (outcome: ${val.outcome})`, 'none');
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
  const vc = candidateValidated(family, t, candidate, val);
  if (!vc.confirmed) {
    return fail('blocked',
      `its one VAL (${val.runId}) did not validate the CANDIDATE ${candidate.sourceFile}: ${vc.why}. ` +
      'A validation of a different book is not a validation of this one. Settle the family on ONE ' +
      'book, or re-validate the candidate (which needs the human VAL override, since the budget ' +
      'is spent).', 'human');
  }
  if (realizability == null || Number.isNaN(realizability)) {
    // Unknown blocks rather than permits — see the header.
    return fail('blocked', 'no realizability: on the family page. An agent must score it with ' +
                           'evidence; unknown blocks so that it is visible rather than assumed',
                'research');
  }
  if (realizability < MIN_REALIZABILITY) {
    return fail('rejected', `realizability ${realizability} < ${MIN_REALIZABILITY} — a book whose ` +
                            'fills a daily bar cannot honour must not enter the shipping set',
                'none');
  }

  // ⚠ Realizability is a property of a BOOK, and the page carries one number. When the candidate
  // is a PRODUCT rather than the family's base, that number was scored on a different book and
  // does not automatically transfer. Measured case: 大小盘轮动's R=2 was established by liq-1 on
  // the BASE, while its product is always-small — and the family's own realism says always-small
  // is WORSE on capacity (「always-small 与去股息闸门 更甚」). `realizabilityScope:` names the book
  // the score applies to; absent, the score is taken to describe the base.
  if (candidate.kind === 'product') {
    const scopeOk = realizabilityScope
      && (realizabilityScope === candidate.expId || realizabilityScope === candidate.sourceFile);
    if (!scopeOk) {
      return fail('blocked',
        `realizability ${realizability} was scored for this family's BASE, but the candidate is the ` +
        `product ${candidate.expId} — a different book, so the score does not transfer. Score the ` +
        `product and set realizabilityScope: ${candidate.expId} on the family page (or show the ` +
        'product is capacity-equivalent to the base).', 'research');
    }
  }
  return { family, universe, status: 'eligible', eligible: true, owner: null,
           why: `${candidate.kind === 'product' ? 'product' : 'member'} ${candidate.sourceFile}` +
                `${candidate.sharpe != null ? ` (sharpe ${candidate.sharpe})` : ''}, VAL ${val.runId} ` +
                `sharpe ${val.sharpe}, realizability ${realizability}`,
           candidate, member, product, champion: candidate, val, realizability };
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
    for (const r of groups[k]) {
      console.log(`   ${r.family.padEnd(12)} [${String(r.owner).padEnd(9)}] ${r.why}`);
    }
  }
  // ⚠ The owner column is what connects this gate back to the pipeline. A `research`-owned block
  // is a step /run-family performs; `utils/family-queue.js` reopens those families so the daily
  // cron reaches them. `human` and `none` are deliberately NOT reopened — see `fail()`.
  const byOwner = o => rows.filter(r => !r.eligible && r.owner === o).map(r => r.family);
  const reopened = byOwner('research');
  console.log(`\n[eligible] owners: research ${reopened.length}  normalize ${byOwner('normalize').length}` +
              `  human ${byOwner('human').length}  none ${byOwner('none').length}`);
  if (reopened.length) {
    console.log(`[eligible] /run-family can clear: ${reopened.join(', ')}`);
    console.log('[eligible] those are reopened in the research queue (node utils/family-queue.js)');
  }
}

module.exports = { assess, all, championOf, validationOf, shelfProductOf,
                   candidateValidated, familyIndex, MIN_REALIZABILITY };
