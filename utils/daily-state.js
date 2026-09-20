/**
 * daily-state.js — durable state for the daily pipeline: what ran, what is mid-flight, and
 * what was deferred for want of budget.
 *
 * The daily loop spends a hard 60 backtest-minutes and then stops wherever it happens to be.
 * Everything needed to pick up tomorrow therefore has to survive on disk, in git, and outside
 * any Claude session:
 *
 *   - `data/daily-state.json`  — the run log + the in-flight marker (this file's `state`).
 *   - `data/deferred.json`     — strategies the bench could not finish at the cap it had.
 *
 * ⚠ Why a SEPARATE deferred pool rather than making `slow-skipped` retriable. In
 * `strategy-normalize.js`, `slow-skipped` sits in TERMINAL precisely so a strategy that blew
 * the cap is not re-run and re-billed on every batch forever — that bug already happened once
 * with `no-trades`. But terminal-forever also means 14 strategies are stranded with no route
 * back. The pool resolves both: the normalizer keeps treating them as done, while the daily
 * pipeline can deliberately re-admit one when it has the headroom for a bigger cap.
 *
 * ⚠ In-flight is a CLAIM, not a lock. A cron that dies mid-run leaves the marker set; the next
 * run treats a marker older than `STALE_HOURS` as abandoned and takes over, instead of
 * deadlocking on a process that no longer exists.
 *
 * Usage:
 *   const st = require('./daily-state');
 *   st.beginRun({ stage, target, budget })   // claim
 *   st.endRun({ outcome, note, minutesUsed })
 *   st.defer(sourceFile, { reason, capMin }) // slow-skip -> pool
 *   st.dueForRetry(capMin)                   // what the pool can offer at this cap
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
/**
 * `JQ_DAILY_STATE_DIR` redirects both files. Tests set it to a temp dir: these are TRACKED
 * state, and a test run that appends probe rows to the real run log or the real deferred pool
 * is writing fiction into the record the next morning's run reads.
 */
const DIR = process.env.JQ_DAILY_STATE_DIR || path.join(ROOT, 'data');
const STATE = path.join(DIR, 'daily-state.json');
const DEFERRED = path.join(DIR, 'deferred.json');

/** A claim older than this is assumed to belong to a run that died. */
const STALE_HOURS = 6;
/** Stop re-offering a strategy that has already eaten this many caps. */
const MAX_ATTEMPTS = 3;

const now = () => new Date().toISOString();
const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };
const writeJson = (f, v) => {
  fs.mkdirSync(path.dirname(f), { recursive: true });
  fs.writeFileSync(f, JSON.stringify(v, null, 2) + '\n');
};

const EMPTY = { inFlight: null, lastRun: null, runs: [] };

function load() {
  const s = readJson(STATE, null);
  return s && typeof s === 'object' ? { ...EMPTY, ...s } : { ...EMPTY };
}
function save(s) { writeJson(STATE, s); return s; }

const hoursSince = iso => (Date.now() - new Date(iso).getTime()) / 3.6e6;

/**
 * Is a previous run still holding the pipeline?
 * @returns {{held:boolean, stale:boolean, claim:object|null}}
 */
function inFlight() {
  const s = load();
  if (!s.inFlight) return { held: false, stale: false, claim: null };
  const stale = hoursSince(s.inFlight.at) > STALE_HOURS;
  return { held: !stale, stale, claim: s.inFlight };
}

/** Claim the pipeline for one stage. Returns false when a live claim already holds it. */
function beginRun({ stage, target = null, budget = null, force = false }) {
  const f = inFlight();
  if (f.held && !force) return false;
  const s = load();
  if (f.stale && s.inFlight) {
    // Record the abandonment rather than silently dropping it — a run that keeps dying
    // mid-stage is a fact worth seeing in the log.
    s.runs.push({ ...s.inFlight, outcome: 'abandoned',
                  note: `no endRun within ${STALE_HOURS}h; taken over`, endedAt: now() });
  }
  s.inFlight = { stage, target, budget, at: now() };
  save(s);
  return true;
}

function endRun({ outcome, note = '', minutesUsed = null }) {
  const s = load();
  const claim = s.inFlight || { stage: 'unknown', at: now() };
  const row = { ...claim, outcome, note, minutesUsed, endedAt: now() };
  s.runs.push(row);
  // Keep the log bounded; it is a breadcrumb trail, not an audit ledger
  // (consumption.tsv is the audit ledger and is append-only).
  if (s.runs.length > 120) s.runs = s.runs.slice(-120);
  s.inFlight = null;
  s.lastRun = row;
  save(s);
  return row;
}

// ── deferred pool ───────────────────────────────────────────────────────────

function deferred() { return readJson(DEFERRED, {}); }

/**
 * Park a strategy the bench could not finish. Records the cap it failed at, so a later run
 * only re-offers it when it can afford MORE than that — re-running at the same cap would
 * spend the same minutes to learn the same thing.
 */
function defer(sourceFile, { reason = 'slow-skipped', capMin = null } = {}) {
  const d = deferred();
  const prev = d[sourceFile] || { attempts: 0, firstDeferredAt: now() };
  d[sourceFile] = {
    ...prev,
    attempts: prev.attempts + 1,
    reason,
    lastCapMin: capMin,
    maxCapTried: Math.max(prev.maxCapTried || 0, capMin || 0),
    lastDeferredAt: now(),
  };
  writeJson(DEFERRED, d);
  return d[sourceFile];
}

/** Mark a deferred strategy as finally resolved (it completed, or is genuinely hopeless). */
function resolve(sourceFile, outcome = 'completed') {
  const d = deferred();
  if (!d[sourceFile]) return false;
  delete d[sourceFile];
  writeJson(DEFERRED, d);
  return outcome;
}

/**
 * Which deferred strategies are worth re-offering at `capMin`.
 * Only those that have never been tried at this cap or higher, and are under the attempt
 * ceiling. Longest-waiting first, so nothing starves behind a repeatedly-retried file.
 */
function dueForRetry(capMin) {
  const d = deferred();
  return Object.entries(d)
    .filter(([, v]) => (v.attempts || 0) < MAX_ATTEMPTS)
    .filter(([, v]) => (v.maxCapTried || 0) < capMin)
    .sort((a, b) => String(a[1].firstDeferredAt).localeCompare(String(b[1].firstDeferredAt)))
    .map(([file, v]) => ({ file, ...v }));
}

/** Deferred entries that will never be re-offered, and why — so they are not invisible. */
function exhausted(capMin) {
  const d = deferred();
  return Object.entries(d)
    .filter(([, v]) => (v.attempts || 0) >= MAX_ATTEMPTS || (v.maxCapTried || 0) >= capMin)
    .map(([file, v]) => ({
      file, ...v,
      why: (v.attempts || 0) >= MAX_ATTEMPTS
        ? `${v.attempts} attempts (ceiling ${MAX_ATTEMPTS})`
        : `already tried at cap ${v.maxCapTried} >= ${capMin}`,
    }));
}

module.exports = {
  load, save, inFlight, beginRun, endRun,
  deferred, defer, resolve, dueForRetry, exhausted,
  STATE, DEFERRED, STALE_HOURS, MAX_ATTEMPTS,
};
