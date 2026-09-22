// Usage: node study/趋势技术/run.js <rel-path-under-study/趋势技术> <expId>
// One TRAIN backtest, output to data/autostudy-logs/<expId>.log, terminated by an EXIT line.
// The base does a full-pool get_price pass every day at 08:00 (the epoch-2 q-1 run hit the
// executor's 3000s wall), so the slow-skip cap is 45 min, not the 20-min default.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const rel = process.argv[2], id = process.argv[3];
const file = path.join('study', '趋势技术', rel);
fs.mkdirSync('data/autostudy-logs', { recursive: true });
const logPath = `data/autostudy-logs/${id}.log`;
const log = fs.openSync(logPath, 'w');
const r = spawnSync('node', ['utils/strategy-post-backtest.js', file, id, '--window', 'train',
  '--usage-limit', '170', '--max-poll-min', '45'], { stdio: ['ignore', log, log] });
fs.writeSync(log, `\nEXIT ${r.status}\n`);
console.log(fs.readFileSync(logPath, 'utf8').split('\n').filter(l => /^(SUMMARY|SERIES|EXIT)|usage|STOP|error/i.test(l)).join('\n'));
