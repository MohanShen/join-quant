// node -e "require('./study/多因子ML/syntax-check-e9-pit.js')"
// Free local Python syntax check on variants/q-e9-pit.py before any backtest minute is spent.
// A compile-error on JQ costs no backtest minutes but does cost a round trip.
// It also re-asserts the one thing the builder promised: the ETF pool is 13 active entries, down
// from the baseline's 14, with 159525 commented out and nothing else moved.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const file = path.join(__dirname, 'variants', 'q-e9-pit.py');
const prog = [
  'import ast, sys',
  'p = sys.argv[1]',
  'src = open(p, encoding="utf-8").read()',
  'try:',
  '    ast.parse(src)',
  '    print("OK    %s  (%d chars)" % (p.split("/")[-1], len(src)))',
  'except SyntaxError as e:',
  '    print("SYNTAX ERROR  %s  line %s: %s" % (p.split("/")[-1], e.lineno, e.msg))',
  '    sys.exit(1)',
].join('\n');

try {
  console.log(execFileSync('python3', ['-I', '-c', prog, file], { encoding: 'utf8' }).trim());
} catch (e) {
  console.error((e.stdout || '') + (e.stderr || ''));
  process.exitCode = 1;
  return;
}

// Structural re-check, independent of the builder's own assertions.
const count = (t) => {
  const i = t.indexOf("'etf_pool': [");
  const j = t.indexOf(']', i);
  const block = t.slice(i, j);
  const active = block.split('\n').filter(l => /^\s*["'][0-9]{6}\./.test(l)).length;
  const commented = block.split('\n').filter(l => /^\s*#["'][0-9]{6}\./.test(l)).length;
  return { active, commented };
};
const v = count(fs.readFileSync(file, 'utf8'));
const b = count(fs.readFileSync(path.join(__dirname, 'baseline-e6.py'), 'utf8'));
console.log(`[check] etf_pool active: baseline ${b.active} -> variant ${v.active} (commented out: ${v.commented})`);
if (!(b.active === 14 && v.active === 13 && v.commented === 1)) {
  console.error('[check] REFUSE: expected 14 -> 13 with exactly 1 commented');
  process.exitCode = 1;
}
