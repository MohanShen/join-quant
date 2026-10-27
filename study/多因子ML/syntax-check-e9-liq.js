// node -e "require('./study/多因子ML/syntax-check-e9-liq.js')"
// Free local Python syntax check on the three q-e9-liq variants before any backtest minute is
// spent. A compile-error on JQ costs no backtest minutes but does cost a round trip.
const path = require('path');
const { execFileSync } = require('child_process');

const dir = path.join(__dirname, 'variants');
const files = ['q-e9-liq-1', 'q-e9-liq-2', 'q-e9-liq-3'].map(f => path.join(dir, `${f}.py`));
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
  console.log(execFileSync('python3', ['-I', '-c', prog, ...files], { encoding: 'utf8' }).trim());
  console.log('all three variants parse');
} catch (e) {
  console.error((e.stdout || '') + (e.stderr || ''));
  process.exitCode = 1;
}
