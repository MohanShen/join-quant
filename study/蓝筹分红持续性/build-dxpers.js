// u-e9-dxpers: edge.test 分红持续性 on the REFERENCE BOOK variants/dxpit.py.
//   (1) semantic change: the qualify condition (dxpit L93) -> `one_year > comp_value` only (2% floor kept;
//       two_year / three_year persistence clauses and the 3-year-sum > 10% clause removed), and the
//       gxl2 / gxl3 sort passes (dxpit L109-110) deleted, so the cascade is gxl head(80) -> (<20 cut,
//       verbatim) -> gxl head(10) -> bten / bfive. Empty-month rule (<= stock_num*2) verbatim.
//       two_year / three_year are still accumulated and stored as columns but nothing reads them.
//   (2) observation: dxpit's DXPRE/DXPOST + after_trading_end P&L logger DROPPED (crashed daily, as in
//       build-dxinv.js). DXMON kept with n_qual, empty flag, bfive, bten, ref_overlap vs dxpit bfive.
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
body = edit(body, "    _dxp_mon(context, df)  # u-e9-dxpit obs\n", "    _dxs_mon(context, df)  # u-e9-dxpers obs\n");
if (/_dxp_|after_trading_end|DXPNL/.test(body)) throw new Error('dxpit obs residue');
const STRIPPED = body;

// ---- (1) semantic edits ----
body = edit(body,
  "        if one_year>comp_value and two_year>comp_value*0.8 and three_year>comp_value*0.64 and (one_year+two_year+three_year)>market_cap*0.1:\n",
  "        if one_year>comp_value:  # u-e9-dxpers: persistence + 3y-sum clauses removed\n");
body = edit(body,
  "    df=df.sort_values(by='gxl2',ascending=False).head(g.stock_num*8)\n    df=df.sort_values(by='gxl3',ascending=False).head(g.stock_num*4)\n",
  '');
const SEM = body;

// ---- (2) DXMON + overlap vs reference ----
const refLog = fs.readFileSync(path.join(__dirname, 'variants', 'dxpit.log.txt'), 'utf8');
const refMon = {};
for (const m of refLog.matchAll(/DXMON date=(\S+) n_qual=(\d+) bfive=(\S*) bten=/g)) refMon[m[1]] = m[3].split(',').filter(Boolean);
if (Object.keys(refMon).length !== 12) throw new Error('expected 12 reference DXMON months, got ' + Object.keys(refMon).length);
const pyDict = '{' + Object.entries(refMon).map(([d, l]) => `'${d}': [${l.map(c => `'${c}'`).join(', ')}]`).join(',\n    ') + '}';
const HELPERS = `

# ===== u-e9-dxpers observation helpers (nothing below feeds an order) =====
_DXS_REF_BFIVE = ${pyDict}

def _dxs_mon(context, df):
    try:
        _d = str(context.current_dt.date())
        _ref = _DXS_REF_BFIVE.get(_d)
        _ov = -1 if _ref is None else len([c for c in g.bfive if c in _ref])
        _empty = 1 if df.shape[0] <= g.stock_num*2 else 0
        log.info('DXMON date=%s n_qual=%d empty=%d bfive=%s bten=%s ref_overlap=%d ref_bfive=%s' % (_d, df.shape[0], _empty, ','.join(g.bfive), ','.join(g.bten), _ov, ','.join(_ref or [])))
    except Exception as _e:
        log.error('DXS-ERR mon err=%r' % (_e,))
# ===== end u-e9-dxpers observation helpers =====
`;
body = body + HELPERS;

// ---- assertions ----
for (const k of ['order_target_value', 'order_value', 'order(', 'run_monthly', 'run_daily', 'run_weekly', '.limit(12))', 'board_plan_pub_date<=d0', 'comp_value=market_cap*0.02']) {
  if (body.split(k).length !== STRIPPED.split(k).length) throw new Error('order/schedule/semantic-pit calls changed: ' + k);
}
if (!body.includes("run_monthly(main,1,time='9:30')")) throw new Error('schedule changed');
if (!body.includes('    if len(df)<g.stock_num*4:\n        df=df.head(len(df) -g.stock_num*2)\n')) throw new Error('truncation changed');
if (!body.includes('    if df.shape[0]<=g.stock_num*2: \n        g.bten=[]\n        g.bfive=[]\n        return \n')) throw new Error('empty-month rule changed');
if (!body.includes("    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*16)\n    if len(df)<g.stock_num*4:\n        df=df.head(len(df) -g.stock_num*2)\n    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*2)\n")) throw new Error('cascade not gxl80 -> cut -> gxl10');
if (/sort_values\(by='gxl[23]'/.test(SEM)) throw new Error('gxl2/gxl3 sort remains');
const a = STRIPPED.split('\n'), b = SEM.split('\n');
if (a.length - b.length !== 2) throw new Error('expected exactly 2 lines removed');
const a2 = a.filter(l => !/sort_values\(by='gxl[23]'/.test(l));
const diff = a2.map((l, i) => l === b[i] ? null : i).filter(x => x !== null);
if (a2.length !== b.length || diff.length !== 1 || !b[diff[0]].includes('u-e9-dxpers')) throw new Error('semantic diff is not exactly qualify line + 2 sort deletions');
if (body.slice(0, body.length - HELPERS.length) !== SEM) throw new Error('obs not additive');

const out = path.join(__dirname, 'variants', 'dxpers.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out), 'changed line', diff[0] + 1);
