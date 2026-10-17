// node -e "require('./study/五福闹新春/run-e8-3.js')"
// Launches the ONE TRAIN backtest for q-e8-3 DETACHED, tee'd to
// data/autostudy-logs/wufu-q-e8-3.log, and returns immediately.
// The caller then BLOCKS in the foreground on study/五福闹新春/wait-e8-3.js, which is
// the executor contract's "start it detached to a log and block on the log in the
// foreground" — not a background job awaiting a notification.
const fs = require('fs');
const { spawn } = require('child_process');

fs.mkdirSync('data/autostudy-logs', { recursive: true });
const logPath = 'data/autostudy-logs/wufu-q-e8-3.log';
if (fs.existsSync(logPath)) {
  const prev = fs.readFileSync(logPath, 'utf8');
  if (/^EXIT 0$/m.test(prev)) {
    console.log('REFUSING: a completed run already exists in ' + logPath + ' — do not retry a completed run.');
    process.exitCode = 2;
    return;
  }
}
const log = fs.openSync(logPath, 'w');
const child = spawn('node', [
  'utils/strategy-post-backtest.js',
  'study/五福闹新春/variants/q-e8-3_pit9-liqfloor-2e7.py',
  'q-e8-3',
  '--window', 'train',
  '--usage-limit', 'free',
], { stdio: ['ignore', log, log], detached: true });
fs.writeSync(log, `LAUNCHED pid=${child.pid} at ${new Date().toISOString()}\n`);
child.unref();
console.log('launched pid', child.pid, '-> ', logPath);
