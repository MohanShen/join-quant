/**
 * val-budget.js — one VALIDATION per (family, epoch).
 *
 * ## Why this is a code guarantee and not an instruction
 *
 * The harness has three surfaces and they are not interchangeable. TRAIN is where selection
 * happens and may be re-run freely. VAL is a CONFIRMATION — it answers "does the thing we chose
 * on TRAIN survive on data we did not choose it with", and that question can be asked once. OOS
 * (2026+) is hard-blocked in the executor and has a 2-test budget for the entire epoch.
 *
 * Nothing protected VAL. `assertNotOOS` guards the reserve, `stageGate` sets a threshold, but a
 * family could be validated any number of times and the only cost was budget. That was tolerable
 * while VAL was reached rarely — only an enhance finalisation got there. It stops being tolerable
 * the moment validation becomes a terminal STAGE of a loop that every family passes through and
 * that reopens whenever `consumption.staleFor` reports new members
 * (`docs/proposals/merged-research-loop.md` §6).
 *
 * The failure is quiet and permanent. Validate five candidates from one family and pick the best
 * VAL number, and VAL has become a second training set — no error, no flag, just a number that no
 * longer means what the harness says it means. And it cannot be undone: once VAL has been selected
 * against, the only clean surface left is the OOS reserve, which is ~9 months and 2 tests.
 *
 * ## The rule
 *
 *   One `validate` event per (family, epoch), full stop.
 *
 * The proposal drafted a softer version — "unless the finalized candidate itself changed" — and
 * that clause is deliberately NOT implemented. It reopens the hole it was meant to close: an
 * agent that produces a new candidate whenever the last VAL disappoints is doing selection on VAL
 * one run at a time, and every one of those runs satisfies "the candidate changed". A legitimate
 * second validation still exists, as a HUMAN decision (`JQ_ALLOW_REVAL=1`), recorded when used —
 * the same shape as `JQ_ALLOW_OOS`.
 *
 * ## Unknown epoch BLOCKS
 *
 * `data/consumption.tsv` gained its `epoch` column at the same time as this file, so a row written
 * earlier carries no epoch. For this rule unknown counts as "already validated in the active
 * epoch" — it blocks. That is the conservative direction on an irreversible resource: blocking is
 * visible and a human can override it in one command, whereas permitting silently re-spends the
 * thing the rule protects. It costs nothing today (no family validation has ever been recorded).
 *
 * Usage:
 *   const val = require('./val-budget');
 *   const v = val.check('ETF动量');       // { allowed, reason, why, prior }
 *   val.record('ETF动量', 'etfprem-007', { outcome: 'pass', note: '…' });
 *
 *   node utils/val-budget.js               # report every family's VAL state
 *   node utils/val-budget.js <family>      # check one
 */

const fs = require('fs');
const path = require('path');
const consumption = require('./consumption');
const harness = require('./harness-config');

// Redirectable for the same reason consumption.js and daily-state.js are: a test must be able to
// use synthetic family names without either touching the real wiki or being refused by the
// existence check below.
const familiesDir = () =>
  process.env.JQ_FAMILIES_DIR || path.resolve(__dirname, '../wiki/families');

const ALLOW_REVAL = process.env.JQ_ALLOW_REVAL === '1';

function activeEpoch() {
  return String(harness.config().epoch);
}

/** Family-level validations already on the ledger, newest last. */
function priorValidations(family) {
  return consumption.events({ stage: 'validate', kind: 'family', key: family });
}

/**
 * May this family be validated right now?
 *
 * `reason` is a stable machine token; `why` is the sentence a human reads. Both are returned so a
 * caller never has to parse prose to decide what happened — the repo has been bitten by grepping
 * rendered output before (`detectCompileError` matching the editor's own source).
 */
function check(family, { epoch = activeEpoch() } = {}) {
  if (!family) {
    return { allowed: false, reason: 'no-family',
             why: 'VAL requires a family: the budget is one validation per (family, epoch), ' +
                  'so a run that does not say which family it belongs to cannot be counted.' };
  }

  // ⚠ The family must EXIST. Without this, a typo in --family ("红利低频X") reads as a family
  // with no prior validation and is waved through — spending a VAL that is then charged to a
  // family nobody will ever look at, while the real one keeps its budget. The whole rule is
  // per-family accounting, so an unaccountable family is not a lesser problem than a second run.
  if (!fs.existsSync(path.join(familiesDir(), `${family}.md`))) {
    return { allowed: false, reason: 'unknown-family',
             why: `VAL-BLOCKED: no family page at wiki/families/${family}.md. The budget is ` +
                  'per (family, epoch), so a name nothing can be charged against is refused — ' +
                  'check the spelling, or register the family first.' };
  }

  const prior = priorValidations(family);
  const blocking = prior.filter(e => e.epoch === epoch || !e.epoch);

  if (!blocking.length) {
    return { allowed: true, reason: 'first-of-epoch',
             why: `no VAL recorded for ${family} at epoch ${epoch}`, prior };
  }

  const p = blocking[blocking.length - 1];
  const when = String(p.at || '').slice(0, 10);
  const unknown = !p.epoch;
  const detail = `${family} was already validated${unknown ? ' (epoch not recorded)' : ''}` +
                 ` on ${when} as "${p.runId || 'unnamed'}" -> ${p.outcome || '?'}`;

  if (ALLOW_REVAL) {
    return { allowed: true, reason: 'human-override', prior,
             why: `JQ_ALLOW_REVAL=1 — ${detail}. This spends VAL a second time at epoch ${epoch}; ` +
                  'it is recorded as an override.' };
  }

  return {
    allowed: false,
    reason: unknown ? 'prior-unknown-epoch' : 'already-validated',
    prior,
    why: `VAL-BLOCKED: ${detail}. The budget is ONE validation per (family, epoch) — ` +
         'validating a second candidate and keeping the better number makes VAL a training set, ' +
         'and that cannot be undone. Iterate on TRAIN, or bump the epoch. ' +
         '(User-only override for a deliberate re-validation: JQ_ALLOW_REVAL=1.)',
  };
}

/** Record a validation. `runId` is the candidate that was validated. */
function record(family, runId, { outcome = '', note = '' } = {}) {
  return consumption.record({
    key: family, kind: 'family', stage: 'validate', runId, outcome,
    note: (ALLOW_REVAL ? '[JQ_ALLOW_REVAL] ' : '') + note,
  });
}

/** Every family the wiki knows, with its VAL state at the active epoch. */
function report() {
  const dir = familiesDir();
  let families = [];
  try {
    families = fs.readdirSync(dir).filter(f => f.endsWith('.md')).map(f => f.replace(/\.md$/, ''));
  } catch { /* no wiki yet */ }
  return families.map(f => ({ family: f, ...check(f) }));
}

module.exports = { check, record, priorValidations, activeEpoch, report, familiesDir };

if (require.main === module) {
  const who = process.argv.slice(2).filter(a => !a.startsWith('--'))[0];
  const epoch = activeEpoch();

  if (who) {
    const v = check(who);
    console.log(`[val] epoch ${epoch}  ${who}: ${v.allowed ? 'ALLOWED' : 'BLOCKED'} (${v.reason})`);
    console.log(`      ${v.why}`);
    process.exit(v.allowed ? 0 : 1);
  }

  const rows = report();
  const blocked = rows.filter(r => !r.allowed);
  console.log(`[val] epoch ${epoch}: budget is ONE validation per (family, epoch)`);
  console.log(`[val] ${rows.length - blocked.length} family(ies) may validate, ${blocked.length} already have`);
  for (const r of blocked) {
    const p = (r.prior || [])[r.prior.length - 1] || {};
    console.log(`   used  ${r.family.padEnd(16)} ${String(p.at || '').slice(0, 10)}  ${p.runId || ''} -> ${p.outcome || '?'}`);
  }
  if (!blocked.length) console.log('   (no family has spent its VAL at this epoch)');
}
