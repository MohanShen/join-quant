// Waits until the JQ account can accept a new backtest, then exits 0 with "CLEAR".
//
// ⚠ This used to poll for `running.length === 0` and give up after 28 minutes, citing git 31dc1c5
// ("a phantom is reported, never worked around"). That doctrine was right for one day and is now
// superseded: `concurrencyGate` tolerates an entry older than our own cap — it is a run of ours
// that JQ refused to cancel, it will never finish, and `pollUntilComplete` measures completion
// against a baseline that includes it. Waiting for zero therefore waits for something that will
// not happen: an unreapable entry sat on this account for 14 hours.
//
// It also reimplemented `utils/jq-running.js` with weaker semantics (no age filter, no cap
// awareness). A second copy of a rule is free to drift from it, so this delegates instead. The
// interface is unchanged for callers: exit 0 = go, exit 3 = a LIVE run is still in the way.
//
//   node -e "require('./study/打板短线/wait-clear.js')"
//
// MAX_MIN should exceed the slow-skip cap — our own run is entitled to the whole of it, and a
// shorter wait gives up on work that is going to finish (see strategy-normalize.js's note).
const { execFileSync } = require('child_process');
const path = require('path');

const MAX_MIN = parseInt(process.env.WAIT_CLEAR_MAX_MIN || '50', 10);
const CAP_MIN = parseInt(process.env.WAIT_CLEAR_CAP_MIN || '45', 10);

try {
  execFileSync('node', [path.join(__dirname, '../../utils/jq-running.js'),
                        '--wait', '--timeout-min', String(MAX_MIN), '--cap-min', String(CAP_MIN)],
    { stdio: 'inherit', timeout: (MAX_MIN + 3) * 60 * 1000 });
  console.log('CLEAR');
} catch (e) {
  // Exit 2 = the blocker is past the cap: dead, tolerated by the executor, safe to start.
  if (e && e.status === 2) {
    console.log(`CLEAR (blocker is past the ${CAP_MIN}min cap — unreapable and never going to ` +
                'finish; the executor measures completion against it, so starting is safe)');
  } else {
    console.log(`GIVEUP a LIVE backtest is still running after ${MAX_MIN} min`);
    process.exitCode = 3;
  }
}
