// The family's ONE epoch-6 validation, spent on the base itself (no improve candidate beat it on
// TRAIN: imp-3 −0.12, imp-4 −0.41, imp-1/imp-2 dropped by arithmetic). Pre-registered reading
// (study-dbdx-imp-4): two positive years and sharpe ≥ 1.5 => the base passes VAL; a repeat of
// "one fat-tail year + one losing year" => the edge is a regime event, not a stable premium.
//   node -e "require('./study/打板短线/run-val.js')"
// --family is required on VAL (utils/val-budget.js); a second VAL for this family at epoch 6
// exits 3 with VAL-BLOCKED. Never set JQ_ALLOW_REVAL here.
const fs = require('fs');
const { spawnSync } = require('child_process');
const id = 'dbdx-VAL-base-e6';
fs.mkdirSync('data/autostudy-logs', { recursive: true });
const logPath = `data/autostudy-logs/${id}.log`;
const log = fs.openSync(logPath, 'w');
const r = spawnSync('node', ['utils/strategy-post-backtest.js', 'study/打板短线/baseline-e6.py', id,
  '--window', 'val', '--family', '打板短线', '--usage-limit', '170', '--max-poll-min', '50'], { stdio: ['ignore', log, log] });
fs.writeSync(log, `\nEXIT ${r.status}\n`);
console.log(fs.readFileSync(logPath, 'utf8').split('\n').filter(l => /^(SUMMARY|SERIES|EXIT)|usage|STOP|BLOCKED|error|algorithmId|backtestId|\[val\]/i.test(l)).join('\n'));
