// Usage: node study/大小盘轮动/run.js <rel-path-under-study/大小盘轮动> <expId>
// One TRAIN backtest, output to data/autostudy-logs/<expId>.log, terminated by an EXIT line.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const rel = process.argv[2], id = process.argv[3];
const file = path.join('study', '大小盘轮动', rel);
fs.mkdirSync('data/autostudy-logs', { recursive: true });
const logPath = `data/autostudy-logs/${id}.log`;
const log = fs.openSync(logPath, 'w');
const r = spawnSync('node', ['utils/strategy-post-backtest.js', file, id, '--window', 'train',
  '--usage-limit', '170', '--max-poll-min', '45'], { stdio: ['ignore', log, log] });
fs.writeSync(log, `\nEXIT ${r.status}\n`);
console.log(fs.readFileSync(logPath, 'utf8').split('\n').filter(l => /^(SUMMARY|SERIES|EXIT)|usage|STOP|error/i.test(l)).join('\n'));
