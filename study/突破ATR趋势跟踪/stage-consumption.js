// Stage ONLY this family's consumption row on top of HEAD's data/consumption.tsv, leaving rows
// other sessions appended (uncommitted) in the working tree untouched and unstaged.
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const git = (args, input) => execFileSync('git', args, { cwd: ROOT, input, encoding: 'utf8' });

const head = git(['show', 'HEAD:data/consumption.tsv']);
const mine = fs.readFileSync(path.join(ROOT, 'data/consumption.tsv'), 'utf8').split('\n')
  .filter(l => l.startsWith('突破ATR趋势跟踪\t') && !head.includes(l));
if (!mine.length) { console.log('nothing to stage'); return; }
const blob = (head.endsWith('\n') ? head : head + '\n') + mine.join('\n') + '\n';
const sha = git(['hash-object', '-w', '--stdin'], blob).trim();
git(['update-index', '--cacheinfo', `100644,${sha},data/consumption.tsv`]);
console.log(`staged ${mine.length} row(s) on top of HEAD (${sha.slice(0, 8)})`);
