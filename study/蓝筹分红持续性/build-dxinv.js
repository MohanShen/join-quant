// u-e9-dxinv: edge.test 股息率 — inverted yield rank on the REFERENCE BOOK variants/dxpit.py.
//   (1) ONE semantic change: the four sort_values(by='gxl'|'gxl2'|'gxl3'|'gxl', ascending=False) in
//       setSmallStocks -> ascending=True. Everything else verbatim, including the
//       len < stock_num*4 -> head(len - stock_num*2) truncation (which now drops the HIGHEST-yield
//       tail — part of a faithful inversion) and the bten fill-in.
//   (2) observation: dxpit's DXPRE/DXPOST + after_trading_end P&L logger are DROPPED (the latter
//       crashed every day: jqdata `sum` shadows builtins). DXMON kept, extended with an overlap
//       count of bfive vs the dxpit reference's bfive that month (read from variants/dxpit.log.txt).
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const ref = fs.readFileSync(path.join(__dirname, 'variants', 'dxpit.py'), 'utf8');
if (!ref.endsWith(OVERRIDE)) throw new Error('dxpit.py does not end with the live OVERRIDE');
let body = ref.slice(0, ref.length - OVERRIDE.length);

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

// ---- strip dxpit's observation layer ----
const H0 = '\n\n# ===== u-e9-dxpit observation helpers (nothing below feeds an order) =====\n';
const H1 = '# ===== end u-e9-dxpit observation helpers =====\n';
const i0 = body.indexOf(H0), i1 = body.indexOf(H1);
if (i0 < 0 || i1 < 0 || body.split(H0).length !== 2) throw new Error('dxpit helper block not found exactly once');
body = body.slice(0, i0) + body.slice(i1 + H1.length);
body = edit(body, "    _dxp_pos(context, 'DXPRE')  # u-e9-dxpit obs\n", '');
body = edit(body, "    _dxp_pos(context, 'DXPOST')  # u-e9-dxpit obs\n", '');
body = edit(body, "    _dxp_mon(context, df)  # u-e9-dxpit obs\n", "    _dxi_mon(context, df)  # u-e9-dxinv obs\n");
if (/_dxp_|after_trading_end|DXPNL/.test(body)) throw new Error('dxpit obs residue');
const STRIPPED = body;

// ---- (1) the semantic edit: four sorts in setSmallStocks ----
const SORTS = [
  ["    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*16)\n",
   "    df=df.sort_values(by='gxl',ascending=True).head(g.stock_num*16)  # u-e9-dxinv\n"],
  ["    df=df.sort_values(by='gxl2',ascending=False).head(g.stock_num*8)\n",
   "    df=df.sort_values(by='gxl2',ascending=True).head(g.stock_num*8)  # u-e9-dxinv\n"],
  ["    df=df.sort_values(by='gxl3',ascending=False).head(g.stock_num*4)\n",
   "    df=df.sort_values(by='gxl3',ascending=True).head(g.stock_num*4)  # u-e9-dxinv\n"],
  ["    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*2)\n",
   "    df=df.sort_values(by='gxl',ascending=True).head(g.stock_num*2)  # u-e9-dxinv\n"],
];
for (const [a, b] of SORTS) body = edit(body, a, b);
const SEM = body;

// ---- (2) DXMON + overlap vs reference ----
const refLog = fs.readFileSync(path.join(__dirname, 'variants', 'dxpit.log.txt'), 'utf8');
const refMon = {};
for (const m of refLog.matchAll(/DXMON date=(\S+) n_qual=\d+ bfive=(\S*) bten=/g)) refMon[m[1]] = m[2].split(',').filter(Boolean);
if (Object.keys(refMon).length !== 12) throw new Error('expected 12 reference DXMON months, got ' + Object.keys(refMon).length);
const pyDict = '{' + Object.entries(refMon).map(([d, l]) => `'${d}': [${l.map(c => `'${c}'`).join(', ')}]`).join(',\n    ') + '}';
const HELPERS = `

# ===== u-e9-dxinv observation helpers (nothing below feeds an order) =====
_DXI_REF_BFIVE = ${pyDict}

def _dxi_mon(context, df):
    try:
        _d = str(context.current_dt.date())
        _ref = _DXI_REF_BFIVE.get(_d)
        _ov = -1 if _ref is None else len([c for c in g.bfive if c in _ref])
        log.info('DXMON date=%s n_qual=%d bfive=%s bten=%s ref_overlap=%d ref_bfive=%s' % (_d, df.shape[0], ','.join(g.bfive), ','.join(g.bten), _ov, ','.join(_ref or [])))
    except Exception as _e:
        log.error('DXI-ERR mon err=%r' % (_e,))
# ===== end u-e9-dxinv observation helpers =====
`;
body = body + HELPERS;

// ---- assertions ----
for (const k of ['order_target_value', 'order_value', 'order(', 'run_monthly', 'run_daily', 'run_weekly', '.limit(12))', 'board_plan_pub_date<=d0']) {
  if (body.split(k).length !== STRIPPED.split(k).length) throw new Error('order/schedule/semantic-pit calls changed: ' + k);
}
if (!body.includes("run_monthly(main,1,time='9:30')")) throw new Error('schedule changed');
if (!body.includes('    if len(df)<g.stock_num*4:\n        df=df.head(len(df) -g.stock_num*2)\n')) throw new Error('truncation changed');
// changed lines vs stripped reference are exactly the 4 sorts (+ the obs call rename, done before STRIPPED)
const a = STRIPPED.split('\n'), b = SEM.split('\n');
if (a.length !== b.length) throw new Error('line count changed');
const diff = a.map((l, i) => l === b[i] ? null : i).filter(x => x !== null);
if (diff.length !== 4 || !diff.every(i => b[i].includes('ascending=True') && b[i].includes('u-e9-dxinv'))) throw new Error('semantic diff is not exactly the 4 sorts');
if ((SEM.match(/sort_values\(by='gxl\d?',ascending=False\)/g) || []).length !== 0) throw new Error('a gxl sort still descending');
if (body.slice(0, body.length - HELPERS.length) !== SEM) throw new Error('obs not additive');

const out = path.join(__dirname, 'variants', 'dxinv.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out), 'diff lines', diff.map(i => i + 1).join(','));
