// node -e "require('./study/五福闹新春/wait-e8-3.js')"
// Foreground BLOCKING wait on the detached run's log. Returns when the child's own
// terminal marker appears, or after MAX_MS so the tool call never exceeds its timeout
// (just call it again — it is idempotent and reads a file).
const fs = require('fs');
const LOG = 'data/autostudy-logs/wufu-q-e8-3.log';
const MAX_MS = Number(process.env.WAIT_MAX_MS || 8.5 * 60 * 1000);
const TERMINAL = /SUMMARY|^EXIT |CONCURRENT-STOP|PHANTOM-STOP|UNPINNED-STOP|VAL-BLOCKED|OOS-BLOCKED|USAGE-STOP|compile-error|no-trades|slow-skipped/m;

const t0 = Date.now();
(function poll() {
  const txt = fs.existsSync(LOG) ? fs.readFileSync(LOG, 'utf8') : '';
  const done = TERMINAL.test(txt);
  if (done || Date.now() - t0 > MAX_MS) {
    const tail = txt.trim().split('\n').slice(-18).join('\n');
    console.log(`waited ${((Date.now() - t0) / 60000).toFixed(1)} min | terminal=${done}`);
    console.log('--- tail ---\n' + tail);
    return;
  }
  setTimeout(poll, 15000);
})();
