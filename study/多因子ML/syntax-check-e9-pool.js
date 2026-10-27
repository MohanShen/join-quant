// node -e "require('./study/多因子ML/syntax-check-e9-pool.js')"
// Free local Python syntax check on the q-e9-pool probe before any backtest minute is spent.
const path = require('path');
const { execFileSync } = require('child_process');

const file = path.join(__dirname, '../_probes/probe-e9-pool-listdates.py');
const prog = [
  'import ast, sys',
  'for p in sys.argv[1:]:',
  '    src = open(p, encoding="utf-8").read()',
  '    try:',
  '        ast.parse(src)',
  '        print("OK    %s  (%d chars)" % (p.split("/")[-1], len(src)))',
  '    except SyntaxError as e:',
  '        print("SYNTAX ERROR  %s  line %s: %s" % (p.split("/")[-1], e.lineno, e.msg))',
  '        sys.exit(1)',
].join('\n');

try {
  console.log(execFileSync('python3', ['-I', '-c', prog, file], { encoding: 'utf8' }).trim());
} catch (e) {
  console.error((e.stdout || '') + (e.stderr || ''));
  process.exitCode = 1;
}
