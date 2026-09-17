/**
 * screen-score.js — grade a screener run against the sealed calibration set.
 *
 * The screening counterpart to running a backtest: `screen/screen.md` §7 requires this
 * after any rubric change, and a change that lowers AUC is a regression, not an improvement.
 *
 * It reports precision@K and AUC against three reference rankers so a new run is always
 * compared to something, not just to itself:
 *   - popularity (`likes + clones*0.5`) — what the discovery pipeline ranks by today
 *   - "title mentions 小市值" — a one-word rule that is a surprisingly strong baseline
 *   - the epoch-1 blind LLM run, if present
 *
 * ⚠ This grades pass-likelihood (rubric axis S) ONLY. There is no ground truth for marginal
 * information (axis M), the rubric's PRIMARY axis. A good AUC says the screener reads the
 * market well; it does not say it is picking the right posts. See screen/calibration/README.md.
 *
 * Usage:
 *   node utils/screen-score.js <predictions.json>
 *   node utils/screen-score.js                      # grades the epoch-1 reference run
 *
 * predictions.json: { "<ref>": { "score": 0..100, ... }, ... }
 *   `score` may be a 0-100 pass-likelihood or a rubric `priority` (0-40) — only the ORDER
 *   is used, so either works. Missing refs score 0.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const CAL = path.join(ROOT, 'screen/calibration');
const POSTS = path.join(CAL, 'posts.json');
const KEY = path.join(CAL, 'answers.sealed.json');

const readJson = f => JSON.parse(fs.readFileSync(f, 'utf8'));

// ── the rubric's scoring formula, as code (screen/screen.md §4) ──────────────
// Kept here rather than only in prose so a verdict can be machine-checked: a
// screener that writes a priority inconsistent with its own four axes has a bug,
// not a difference of opinion.

/** priority = 3M + 2S + 2R + H, with the realizability veto and the M==0 cap. */
function priorityOf({ M, S, R, H }) {
  for (const [k, v] of Object.entries({ M, S, R, H })) {
    if (!Number.isInteger(v) || v < 0 || v > 5) throw new Error(`axis ${k} must be an integer 0-5, got ${v}`);
  }
  let p = 3 * M + 2 * S + 2 * R + H;
  if (R <= 1) p = Math.min(p, 2);     // cannot trade it, however well it scores
  // The M ladder is what makes marginal information PRIMARY rather than merely
  // heavily weighted. Without it, M=1,S=5,R=5,H=5 scores 28 and a redundant
  // variant of a 35-member family reaches the top band on the strength of the
  // axes we can just go and measure. Weighting alone could not prevent that.
  if (M === 0) p = Math.min(p, 3);    // nothing to learn -> drop
  if (M === 1) p = Math.min(p, 17);   // nothing NEW to learn -> hold, never fetch
  return p;
}

/** Band thresholds (screen/screen.md §4). */
function bandOf(priority) {
  if (priority >= 28) return 'fetch-now';
  if (priority >= 18) return 'fetch';
  if (priority >= 8) return 'hold';
  return 'drop';
}

/** Returns a list of problems with one verdict; empty means it conforms. */
function validateVerdict(v) {
  const errs = [];
  let p;
  try { p = priorityOf(v); } catch (e) { return [e.message]; }
  if (v.priority !== p) errs.push(`priority ${v.priority} != formula ${p}`);
  const b = bandOf(p);
  if (v.band !== b) errs.push(`band "${v.band}" != "${b}" for priority ${p}`);
  for (const f of ['key', 'family', 'mechanism', 'why']) {
    if (!v[f]) errs.push(`missing ${f}`);
  }
  return errs;
}

/** Precision among the top K of a ranking. */
function precisionAt(ranked, key, k) {
  const top = ranked.slice(0, k);
  if (!top.length) return 0;
  return 100 * top.filter(r => key[r].gate === 'pass').length / top.length;
}

/** Probability a random pass outranks a random fail. 0.5 = coin flip. */
function auc(refs, key, scoreOf) {
  const pass = refs.filter(r => key[r].gate === 'pass');
  const fail = refs.filter(r => key[r].gate === 'fail');
  if (!pass.length || !fail.length) return 0.5;
  let w = 0;
  for (const a of pass) for (const b of fail) {
    const sa = scoreOf(a), sb = scoreOf(b);
    w += sa > sb ? 1 : sa === sb ? 0.5 : 0;
  }
  return w / (pass.length * fail.length);
}

function rank(refs, scoreOf) {
  return [...refs].sort((a, b) => scoreOf(b) - scoreOf(a));
}

function grade(predFile) {
  const posts = readJson(POSTS);
  const key = readJson(KEY);
  const byRef = Object.fromEntries(posts.map(p => [p.ref, p]));
  const refs = posts.map(p => p.ref);
  const base = 100 * refs.filter(r => key[r].gate === 'pass').length / refs.length;

  const pred = readJson(predFile);
  const scorers = {
    'popularity (current)': r => (byRef[r].likes || 0) + (byRef[r].clones || 0) * 0.5,
    '"says 小市值" only': r => (/小市值|微盘|小盘/.test(byRef[r].title || '') ? 1e6 : 0) + (byRef[r].clones || 0),
    [path.basename(predFile)]: r => (pred[r] && (pred[r].score ?? pred[r].priority)) || 0,
  };

  const K = [5, 10, 20, 30];
  console.log(`calibration: ${refs.length} posts, ${refs.filter(r => key[r].gate === 'pass').length} pass ` +
              `(base rate ${base.toFixed(1)}%)\n`);
  console.log(`${''.padEnd(34)}${K.map(k => `top-${k}`.padStart(8)).join('')}${'AUC'.padStart(8)}`);
  for (const [label, f] of Object.entries(scorers)) {
    const ranked = rank(refs, f);
    const cells = K.map(k => `${precisionAt(ranked, key, k).toFixed(0)}%`.padStart(8)).join('');
    console.log(`${label.slice(0, 33).padEnd(34)}${cells}${auc(refs, key, f).toFixed(2).padStart(8)}`);
  }
  console.log(`${'base rate'.padEnd(34)}${K.map(() => `${base.toFixed(0)}%`.padStart(8)).join('')}${(0.5).toFixed(2).padStart(8)}`);

  // Coverage + the misses worth reading, which is where a rubric earns its next edit.
  const missing = refs.filter(r => !(r in pred));
  if (missing.length) console.log(`\n⚠ ${missing.length} ref(s) unscored (treated as 0): ${missing.slice(0, 8).join(', ')}`);

  const scoreOf = scorers[path.basename(predFile)];
  const ranked = rank(refs, scoreOf);
  const worst = ranked.filter(r => key[r].gate === 'pass').slice(-5);
  console.log('\npasses ranked LOWEST — the expensive misses:');
  for (const r of worst) {
    const o = key[r].obj;
    console.log(`  score=${String(scoreOf(r)).padStart(3)}  objective=${o == null ? 'DQ' : o.toFixed(3)}  ${key[r].title.slice(0, 40)}`);
  }

  const top = ranked.slice(0, 20).filter(r => key[r].gate === 'pass');
  console.log(`\ntop-20 contains ${top.length} of the ${refs.filter(r => key[r].gate === 'pass').length} passes`);
  console.log('\n⚠ This grades axis S (pass-likelihood) only — NOT axis M (marginal information),');
  console.log('  which screen/screen.md weights highest and which has no ground truth here.');
}

if (require.main === module) {
  const f = process.argv[2] || path.join(CAL, 'epoch1-reference-predictions.json');
  if (!fs.existsSync(f)) { console.error(`no such predictions file: ${f}`); process.exit(1); }
  grade(f);
}

module.exports = { grade, precisionAt, auc, priorityOf, bandOf, validateVerdict };
