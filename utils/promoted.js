/**
 * promoted.js — the PROMOTED REGISTER: what each universe currently ships.
 *
 * ## Why this state has to exist
 *
 * Integration used to enumerate every PAIR of families in a universe and ask which pairs were
 * mergeable. That treated a universe as a static set and had no notion of what the universe had
 * already delivered, so the same pair came back round after round and the round's own output
 * changed nothing about the next one.
 *
 * The model is now INCREMENTAL (user specification, 2026-10-16). A universe holds a set of
 * promoted candidates. A family that clears `/run-family` arrives one at a time, and meets the
 * promoted set:
 *
 *   1. no promoted candidate OVERLAPS its symbols  -> it is promoted automatically (and when the
 *      set is empty it simply becomes the first — no judgement needed);
 *   2. an overlapping promoted candidate exists and the merge is BETTER -> the merged candidate is
 *      promoted and SUPERSEDES the incumbent; the incoming candidate lives on inside it;
 *   3. an overlapping promoted candidate exists and the merge fails -> the incumbent is unchanged
 *      and the INCOMING candidate is rejected.
 *
 * ⚠ Sequence therefore matters, which is the whole reason this is durable state rather than a
 * computed view: the first arrival defines what everything after it has to beat. Families enter
 * `/run-family` ordered by their champion's TRAIN sharpe, highest first.
 *
 * ## Why a rejection is keyed to the CANDIDATE, not the family
 *
 * Outcome 3 is "rejected until this family has a new best variant". A rejection keyed to the
 * family would be permanent and would silently retire a lineage the moment one merge failed. So
 * the key is `candidateId` — the champion's `sourceFile` for a family candidate, the `expId` for
 * a merged one. A new best variant is a new `candidateId` and therefore a new attempt, with no
 * expiry rule to get wrong.
 *
 * ## Shape
 *
 * Append-only TSV, TRACKED, replayed to get the current set — the same reasoning as
 * `consumption.tsv` and `components.tsv`: concurrent agents append instead of
 * read-modify-write, it survives page regeneration, and "what has this universe ever shipped" is
 * one scan. Never rewrite or delete a row; supersession is itself a row.
 *
 *   at  universe  action  candidateId  kind  members  sharpe  objective  epoch  note
 *
 * `action` is `promote` | `supersede` | `reject`.
 *
 * Usage:
 *   const p = require('./promoted');
 *   p.current('ETF')                       // the promoted set now, strongest first
 *   p.isRejected('ETF', '<candidateId>')   // has this exact candidate already been refused?
 *   p.record({ universe, action, candidateId, kind, members, sharpe, objective, note })
 */

const fs = require('fs');
const path = require('path');
const harness = require('./harness-config');

const ROOT = path.resolve(__dirname, '..');
// ⚠ Redirectable for the same reason consumption.tsv is: this file is TRACKED, and a test that
// appends probe rows would write fiction into the record that decides what a universe ships.
const FILE = () => process.env.JQ_PROMOTED_FILE
  || path.join(process.env.JQ_DAILY_STATE_DIR || path.join(ROOT, 'data'), 'promoted.tsv');

const COLS = ['at', 'universe', 'action', 'candidateId', 'kind', 'members',
              'sharpe', 'objective', 'epoch', 'note'];

const ACTIONS = new Set(['promote', 'supersede', 'reject']);

/** A TSV cell may not contain a tab or newline, or the row stops being one row. */
const clean = v => String(v == null ? '' : v).replace(/[\t\r\n]+/g, ' ').trim();

function events(filter = {}) {
  const p = FILE();
  if (!fs.existsSync(p)) return [];
  const out = [];
  for (const line of fs.readFileSync(p, 'utf8').split('\n').slice(1)) {
    if (!line.trim()) continue;
    const c = line.split('\t');
    const e = {};
    COLS.forEach((k, i) => { e[k] = c[i] == null ? '' : c[i]; });
    if (filter.universe && e.universe !== filter.universe) continue;
    if (filter.action && e.action !== filter.action) continue;
    out.push(e);
  }
  return out;
}

/**
 * Append one event. `epoch` is stamped from the live config and NEVER passed in — a caller that
 * could choose its own epoch could launder a stale promotion into the current one, the same
 * reason `consumption.record()` stamps it.
 */
function record(ev) {
  if (!ev || !ev.universe) throw new Error('promoted.record needs a universe');
  if (!ACTIONS.has(ev.action)) {
    throw new Error(`promoted.record: action must be one of ${[...ACTIONS].join('|')}, got "${ev.action}"`);
  }
  if (!ev.candidateId) throw new Error('promoted.record needs a candidateId (sourceFile or expId)');
  // A reason is required on a reject for the same reason integrate-queue --refuse demands one:
  // the next round must be able to read WHY, not merely that.
  if (ev.action === 'reject' && !clean(ev.note)) {
    throw new Error('promoted.record: a reject needs a note saying why the merge failed');
  }
  const p = FILE();
  fs.mkdirSync(path.dirname(p), { recursive: true });
  if (!fs.existsSync(p)) fs.writeFileSync(p, COLS.join('\t') + '\n');
  const row = {
    at: new Date().toISOString(),
    universe: ev.universe, action: ev.action, candidateId: ev.candidateId,
    kind: ev.kind || 'family',
    members: Array.isArray(ev.members) ? ev.members.join('+') : (ev.members || ''),
    sharpe: ev.sharpe == null ? '' : ev.sharpe,
    objective: ev.objective == null ? '' : ev.objective,
    epoch: harness.config().epoch,
    note: ev.note || '',
  };
  fs.appendFileSync(p, COLS.map(k => clean(row[k])).join('\t') + '\n');
  return row;
}

/**
 * The promoted set for a universe RIGHT NOW, strongest sharpe first (which is the order a new
 * arrival tries them in — the multi-overlap rule is "merge against the strongest incumbent").
 *
 * Replayed rather than stored: a `promote` adds, a `supersede` removes. ⚠ Only promotions made
 * under an epoch the active one still accepts are current — a promotion measured on a superseded
 * bench is history, exactly as a ledger row is.
 */
function current(universe) {
  const live = new Map();
  for (const e of events({ universe })) {
    if (e.action === 'promote') {
      if (!harness.measurementValid(e.epoch || null)) continue;
      live.set(e.candidateId, {
        universe, candidateId: e.candidateId, kind: e.kind || 'family',
        members: e.members ? e.members.split('+') : [],
        sharpe: e.sharpe === '' ? null : parseFloat(e.sharpe),
        objective: e.objective === '' ? null : parseFloat(e.objective),
        epoch: e.epoch, at: e.at, note: e.note,
      });
    } else if (e.action === 'supersede') {
      live.delete(e.candidateId);
    }
  }
  return [...live.values()].sort((a, b) => (b.sharpe ?? -Infinity) - (a.sharpe ?? -Infinity));
}

/**
 * Has this EXACT candidate already been rejected in this universe at a comparable epoch?
 *
 * Keyed to the candidate, so a family whose merge failed gets another attempt as soon as it has a
 * new best variant — which is the spec, and is why there is no expiry rule here.
 */
function isRejected(universe, candidateId) {
  return events({ universe, action: 'reject' })
    .some(e => e.candidateId === candidateId && harness.measurementValid(e.epoch || null));
}

/** Every universe the register has ever touched. */
function universes() {
  return [...new Set(events().map(e => e.universe))].sort();
}

if (require.main === module) {
  const argv = process.argv.slice(2);
  const only = argv.find(a => !a.startsWith('--'));
  const list = only ? [only] : universes();
  if (!list.length) { console.log('[promoted] register is empty — no universe has shipped anything yet'); process.exit(0); }
  for (const u of list) {
    const cur = current(u);
    console.log(`\n■ ${u}  ${cur.length} promoted`);
    for (const c of cur) {
      console.log(`   ${c.kind.padEnd(7)} ${c.candidateId}`);
      console.log(`           sharpe ${c.sharpe ?? '?'}  objective ${c.objective ?? '?'}  e${c.epoch}` +
                  (c.members.length > 1 ? `  <- ${c.members.join(' + ')}` : ''));
    }
    const rej = events({ universe: u, action: 'reject' });
    for (const r of rej) {
      console.log(`   reject  ${r.candidateId}` +
                  `\n           ${r.note}` +
                  '\n           (a NEW best variant for this family is a new candidateId, hence a new attempt)');
    }
  }
}

module.exports = { record, events, current, isRejected, universes, COLS, ACTIONS };
