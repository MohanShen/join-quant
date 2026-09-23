// Usage: node -e "process.argv[2]='variants/u-1_band-liquid.py';process.argv[3]='pt-u-1';require('./study/PT多策略/run.js')"
// One TRAIN backtest, foreground/blocking, output to data/autostudy-logs/<expId>.log, terminated
// by an EXIT line. Paths are relative to study/PT多策略/ unless they start with enhance/.
// Pass process.argv[4]='val' and process.argv[5]='<family>' for the single VAL finalization.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const rel = process.argv[2], id = process.argv[3];
const win = process.argv[4] || 'train';
const file = rel.startsWith('enhance/') ? rel : path.join('study', 'PT多策略', rel);
fs.mkdirSync('data/autostudy-logs', { recursive: true });
const logPath = `data/autostudy-logs/${id}.log`;
const log = fs.openSync(logPath, 'w');
const args = ['utils/strategy-post-backtest.js', file, id, '--window', win,
  '--usage-limit', '170', '--max-poll-min', '30'];
if (win === 'val') args.push('--family', process.argv[5] || 'PT多策略');
const r = spawnSync('node', args, { stdio: ['ignore', log, log] });
fs.writeSync(log, `\nEXIT ${r.status}\n`);
console.log(fs.readFileSync(logPath, 'utf8').split('\n').filter(l => /^(SUMMARY|SERIES|EXIT)|usage|STOP|error|algorithmId|backtestId|\[series\]|BLOCKED|no-trades/i.test(l)).join('\n'));
