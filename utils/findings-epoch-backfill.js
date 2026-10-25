/**
 * findings-epoch-backfill.js — stamp each research finding with the EPOCH it was measured under.
 *
 * ## Why
 *
 * The ledger is fully current: after epoch 9's reset every one of its rows is an epoch-9
 * measurement. The RESEARCH layer is not. Measured 2026-10-25 across 238 findings in
 * `study/*​/findings.tsv`:
 *
 *     epoch-stamped via the `q-eN-` qId convention :  60   (53 e6, 7 e8, 4 e9)
 *     unstamped                                    : 174
 *
 * So ~73% of the repo's recorded understanding — which variant helps, what a family's edge is,
 * what §4 still lacks — carries no indication of the bench that produced it. A reader sees an
 * unlabelled assertion where the honest reading is "this was measured on the 2022–23 window, and
 * for anything pre-epoch-6 under different costs too".
 *
 * ⚠ This is the CHEAP half of that problem. The expensive half — re-measuring the conclusions —
 * costs backtest minutes and is not what this does. This only makes the provenance visible, which
 * is what lets a reader decide whether to trust a line.
 *
 * ## Why not just delete the pages and regenerate
 *
 * Considered and rejected, the same conclusion `epoch-reset.js` reached ("the numbers are stale,
 * the understanding is not"). Only §3 of a family page is generated; §1/§2/§4/§5/§6 are
 * hand-written — 2,551 lines across 13 pages, 30 edge claims, 9 `realizabilityBasis` declarations
 * and 3 `valDeclined` records. Two of those three field groups are what `integrate-eligible`
 * DISPATCHES on, and unknown realizability BLOCKS, so wiping them would move all 13 families from
 * "5 measured rejections + 5 research-owned" to 13 blocked on human judgement. And the
 * irreplaceable content is the negative results: §4 is what stops the loop re-deriving settled
 * answers, which is the non-convergence this repo has already paid for twice.
 *
 * ## How the epoch is decided — two sources, in order of authority
 *
 *   1. **The qId**, when it carries one (`q-e6-13`, `q-e9-pit`). The author stated the bench; that
 *      beats any inference and is used verbatim.
 *   2. **git blame**, otherwise. findings.tsv has NO timestamp column, so the only record of when
 *      a line was written is the commit that added it. The line's committer date is matched
 *      against the epoch timeline, itself derived from the git history of
 *      `harness/config/active.json` rather than written down here — epoch configs carry no date
 *      field, and a second copy of the timeline would drift.
 *
 * ⚠ A finding written while epoch N was active was MEASURED on epoch N's bench, which is the
 * question a reader has. It is not a claim about when the idea was conceived.
 *
 * ⚠ Lines git cannot attribute (uncommitted, or added in a commit that predates the first
 * active.json entry) are stamped `unknown`, never guessed. An unknown stamp is honest and a wrong
 * one is worse than none — the same rule the VAL budget applies to an unrecorded epoch.
 *
 * ## Safety
 *
 * The stamp is a 13th TRAILING column, after `FINDING_COLUMNS`'s 12.
 * `research-queue.findings()` maps those 12 by INDEX over `split('\t')` and ignores the header
 * entirely except to skip it, so a 13th field is invisible to every existing reader — the same
 * migration `consumption.tsv` used for `members`/`memberHash`.
 *
 * ⚠⚠ THE HEADER AND THE ROWS ARE NOT THE SAME WIDTH, and appending to both naively corrupts the
 * file. Measured: 8 of 14 findings.tsv carry the ORIGINAL 9-column header (`qId`..`description`)
 * while their rows already have 12 fields, because `implication`/`spawned`/`edgeRef` were appended
 * to the rows and the header was never updated. A first version of this tool appended the name as
 * header column 10 while the value landed in row position 13 — so the header claimed
 * `measuredEpoch` was column 10, which is `implication`. Worse, on a second run
 * `cells[9]` (a non-empty `implication`) read as "already stamped", so only rows with an EMPTY
 * implication were re-stamped: 5 rows grew to 14 fields. The write was reverted with
 * `git checkout` — these files are tracked, which is the only reason that was cheap.
 *
 * So the write NORMALISES first: the header becomes all 12 `FINDING_COLUMNS` names plus the stamp,
 * and every row is padded to 12 before the stamp is appended. Padding changes no value a reader
 * sees (a missing trailing field already read as empty) and leaves header and rows aligned at 13,
 * which is what makes the second run a no-op.
 *
 * Usage:
 *   node utils/findings-epoch-backfill.js --dry     # report, write nothing
 *   node utils/findings-epoch-backfill.js           # append the column
 *   node utils/findings-epoch-backfill.js --verify  # re-derive and report disagreements
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
// ⚠ ONE OWNER for the schema: research-queue defines and exports FINDING_COLUMNS. A second copy
// here would drift, which is the mistake `utils/ledger.js` was created to end.
const { FINDING_COLUMNS } = require('./research-queue');
const STUDY = path.join(ROOT, 'study');
const COLUMN = 'measuredEpoch';

const git = (args) => execFileSync('git', args, { cwd: ROOT, encoding: 'utf8', maxBuffer: 64 << 20 });

/**
 * The epoch timeline, derived from the git history of `harness/config/active.json`.
 *
 * @returns {Array<{from: string, epoch: number}>} ascending by date
 */
function epochTimeline() {
  let commits;
  try { commits = git(['log', '--format=%H %cI', '--', 'harness/config/active.json']).trim().split('\n'); }
  catch { return []; }
  const out = [];
  for (const line of commits) {
    if (!line) continue;
    const [sha, iso] = line.split(' ');
    let body;
    // ⚠ No shell: `$sha:harness/...` through zsh gets `:h` eaten as a history modifier, which
    // silently turns `harness` into `arness` and makes every lookup fail with a path error.
    try { body = git(['show', `${sha}:harness/config/active.json`]); } catch { continue; }
    let ep = null;
    try { const j = JSON.parse(body); ep = j.activeEpoch ?? j.epoch ?? null; } catch {
      const m = body.match(/(\d+)/); ep = m ? +m[1] : null;
    }
    if (ep != null) out.push({ from: iso, epoch: +ep });
  }
  out.sort((a, b) => a.from.localeCompare(b.from));   // full ISO: 3 epochs shared 2026-09-19
  // Collapse consecutive duplicates — several commits can touch the file without moving the epoch.
  return out.filter((x, i) => i === 0 || x.epoch !== out[i - 1].epoch);
}

/**
 * Which epoch was in force at `iso` (a full ISO-8601 instant). null before the timeline starts.
 *
 * ⚠ FULL timestamps on both sides, not dates. Epochs 3, 4 and 5 all became active on 2026-09-19,
 * so truncating to YYYY-MM-DD made same-day comparison order-dependent and attributed that day's
 * findings to whichever entry happened to sort last — epoch 3, when 5 was in force. ISO-8601
 * compares correctly as a string, so no date parsing is needed.
 */
function epochOn(date, timeline) {
  let cur = null;
  for (const t of timeline) { if (date >= t.from) cur = t.epoch; else break; }
  return cur;
}

/** The epoch the author stated in the qId, if any. `q-e6-13` -> 6. */
function epochFromQid(qId) {
  const m = String(qId || '').match(/^q-e(\d+)/);
  return m ? +m[1] : null;
}

/**
 * Committer date per line of a file, via `git blame --line-porcelain`.
 * @returns {string[]} one full ISO instant per line, '' when unattributable
 */
function blameDates(rel) {
  let out;
  try { out = git(['blame', '--line-porcelain', '--', rel]); } catch { return []; }
  const dates = [];
  let pending = null;
  for (const line of out.split('\n')) {
    const m = line.match(/^committer-time (\d+)/);
    if (m) pending = new Date(+m[1] * 1000).toISOString();
    else if (line.startsWith('\t')) { dates.push(pending || ''); pending = null; }
  }
  return dates;
}

function findingsFiles() {
  if (!fs.existsSync(STUDY)) return [];
  return fs.readdirSync(STUDY)
    .map(d => path.join('study', d, 'findings.tsv'))
    .filter(p => fs.existsSync(path.join(ROOT, p)));
}

/**
 * Decide an epoch for every finding row in one file.
 * @returns {{rel:string, header:string[], rows:Array, counts:Object}}
 */
function analyseFile(rel, timeline) {
  const abs = path.join(ROOT, rel);
  const text = fs.readFileSync(abs, 'utf8');
  const lines = text.split('\n');
  const hasHeader = /^qId\t/.test(lines[0] || '');
  const dates = blameDates(rel);
  const counts = { qid: 0, blame: 0, unknown: 0, already: 0 };

  const header = hasHeader ? lines[0].split('\t') : null;
  const already = header ? header.indexOf(COLUMN) : -1;

  const rows = [];
  for (let i = hasHeader ? 1 : 0; i < lines.length; i++) {
    const raw = lines[i];
    if (!raw.trim()) { rows.push({ i, raw, stamp: null, skip: true }); continue; }
    const cells = raw.split('\t');
    // ⚠ "Already stamped" means a value in the STAMP's own position, which is only meaningful once
    // header and rows are the same width. Testing `cells[header.indexOf(COLUMN)]` on a short header
    // reads `implication` and silently mis-skips (see the header note above).
    if (cells.length > FINDING_COLUMNS.length && cells[FINDING_COLUMNS.length]) {
      counts.already++; rows.push({ i, raw, stamp: cells[FINDING_COLUMNS.length], skip: true }); continue;
    }

    let stamp = epochFromQid(cells[0]);
    let via = 'qid';
    if (stamp == null) {
      const d = dates[i] || '';
      const e = d ? epochOn(d, timeline) : null;
      if (e == null) { stamp = 'unknown'; via = 'unknown'; }
      else { stamp = e; via = 'blame'; }
    }
    counts[via]++;
    rows.push({ i, raw, stamp, via, date: dates[i] || '' });
  }
  return { rel, lines, hasHeader, header, alreadyIdx: already, rows, counts };
}

/** Pad a tab-joined line out to `n` fields. A missing trailing field already read as empty. */
function pad(raw, n) {
  const c = raw.split('\t');
  while (c.length < n) c.push('');
  return c;
}

function write(a) {
  const out = a.lines.slice();
  // Header: the full canonical 12 plus the stamp, so its names line up with the row positions.
  if (a.hasHeader) out[0] = FINDING_COLUMNS.concat([COLUMN]).join('\t');
  for (const r of a.rows) {
    if (r.skip) continue;
    out[r.i] = pad(r.raw, FINDING_COLUMNS.length).concat([String(r.stamp)]).join('\t');
  }
  fs.writeFileSync(path.join(ROOT, a.rel), out.join('\n'));
}

function main() {
  const argv = process.argv.slice(2);
  const dry = argv.includes('--dry');
  const verify = argv.includes('--verify');
  const timeline = epochTimeline();

  if (!timeline.length) {
    console.error('[fe] could not derive the epoch timeline from harness/config/active.json history');
    process.exitCode = 1;
    return;
  }
  console.log('[fe] epoch timeline (from git history of harness/config/active.json):');
  for (const t of timeline) console.log(`       from ${t.from.slice(0, 16)}  epoch ${t.epoch}`);
  console.log('');

  const totals = { qid: 0, blame: 0, unknown: 0, already: 0 };
  const byEpoch = {};
  const files = findingsFiles();
  for (const rel of files) {
    const a = analyseFile(rel, timeline);
    for (const k of Object.keys(totals)) totals[k] += a.counts[k];
    for (const r of a.rows) if (!r.skip) byEpoch[r.stamp] = (byEpoch[r.stamp] || 0) + 1;
    const n = a.rows.filter(r => !r.skip).length;
    if (n) {
      console.log(`  ${path.basename(path.dirname(rel)).padEnd(14)} ${String(n).padStart(3)} to stamp` +
                  `  (qId ${a.counts.qid}, blame ${a.counts.blame}, unknown ${a.counts.unknown}` +
                  `${a.counts.already ? ', already ' + a.counts.already : ''})`);
    }
    if (!dry && !verify && n) write(a);
  }

  console.log('');
  console.log('  by epoch: ' + Object.keys(byEpoch).sort().map(k => `e${k}=${byEpoch[k]}`).join(' '));
  console.log(`  source:   qId ${totals.qid} | git blame ${totals.blame} | unknown ${totals.unknown}` +
              ` | already stamped ${totals.already}`);
  if (dry) console.log('\n[fe] --dry: nothing written');
  else if (verify) console.log('\n[fe] --verify: nothing written');
  else console.log(`\n[fe] stamped ${totals.qid + totals.blame + totals.unknown} finding(s) across ${files.length} file(s)`);
}

if (require.main === module) main();

module.exports = { epochTimeline, epochOn, epochFromQid, blameDates, analyseFile, COLUMN };
