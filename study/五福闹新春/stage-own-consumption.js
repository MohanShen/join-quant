// Stage ONLY this round's consumption row (HEAD + our line), leaving other sessions' uncommitted rows unstaged.
const { execFileSync } = require('child_process');
const fs = require('fs');
const runId = process.argv[2];
const head = execFileSync('git', ['show', 'HEAD:data/consumption.tsv'], { encoding: 'utf8' });
const ours = fs.readFileSync('data/consumption.tsv', 'utf8').split('\n')
  .filter(l => l.startsWith('五福闹新春\tfamily\tresearch\t' + runId + '\t'));
if (ours.length !== 1) throw new Error(`expected 1 row for ${runId}, got ${ours.length}`);
const staged = head.replace(/\n?$/, '\n') + ours[0] + '\n';
const h = execFileSync('git', ['hash-object', '-w', '--stdin'], { input: staged, encoding: 'utf8' }).trim();
execFileSync('git', ['update-index', '--cacheinfo', `100644,${h},data/consumption.tsv`]);
console.log('staged consumption row', runId);
