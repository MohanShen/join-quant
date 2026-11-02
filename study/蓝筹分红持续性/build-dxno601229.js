// u-e9-dxno601229 (understand; one-name robustness): on the REFERENCE BOOK variants/dxpit.py, drop
//   601229.XSHG (上海银行) from the qualifier set immediately after controlReport, so it is never eligible.
//   ONE asserted edit in main(); cascade, empty-month rule, orderStock never-resize logic verbatim.
//   Empty-frame guard: controlReport returns a frame with no 'code' column if nothing qualifies.
//   Observation: dxpit's DXPRE/DXPOST + P&L logger DROPPED (as build-indcap.js / build-gxlonly.js).
//   DXNO date in_qual=<0|1> (read BEFORE the drop) + DXMON with n_qual, bfive, bten, ref_overlap vs dxpit.
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
body = edit(body, "    _dxp_mon(context, df)  # u-e9-dxpit obs\n", "    _dxn_mon(context, df)  # u-e9-dxno601229 obs\n");
if (/_dxp_|after_trading_end|DXPNL/.test(body)) throw new Error('dxpit obs residue');
const CR = "    df=controlReport(df, context.current_dt.date())  # u-e9-dxpit: pass d0\n";
// obs hook (read before the drop) is additive; the semantic edit is the drop line
body = edit(body, CR, CR + "    _dxn_pre(context, df)  # u-e9-dxno601229 obs\n");
const STRIPPED = body;

// ---- (1) the ONE semantic edit ----
const HOOK = CR + "    _dxn_pre(context, df)  # u-e9-dxno601229 obs\n";
body = edit(body, HOOK, HOOK +
  "    if 'code' in df.columns: df=df[df.code!='601229.XSHG'].reset_index(drop=True)  # u-e9-dxno601229\n");
const SEM = body;

// ---- (2) obs ----
const refLog = fs.readFileSync(path.join(__dirname, 'variants', 'dxpit.log.txt'), 'utf8');
const refMon = {};
for (const m of refLog.matchAll(/DXMON date=(\S+) n_qual=(\d+) bfive=(\S*) bten=/g)) refMon[m[1]] = m[3].split(',').filter(Boolean);
if (Object.keys(refMon).length !== 12) throw new Error('expected 12 reference DXMON months, got ' + Object.keys(refMon).length);
const pyDict = '{' + Object.entries(refMon).map(([d, l]) => `'${d}': [${l.map(c => `'${c}'`).join(', ')}]`).join(',\n    ') + '}';
const HELPERS = `

# ===== u-e9-dxno601229 observation helpers (nothing below feeds an order) =====
_DXN_REF_BFIVE = ${pyDict}

def _dxn_pre(context, df):
    try:
        _in = 1 if ('code' in df.columns and '601229.XSHG' in list(df['code'])) else 0
        log.info('DXNO date=%s in_qual=%d n_qual_pre=%d' % (str(context.current_dt.date()), _in, df.shape[0]))
    except Exception as _e:
        log.error('DXN-ERR pre err=%r' % (_e,))

def _dxn_mon(context, df):
    try:
        _d = str(context.current_dt.date())
        _ref = _DXN_REF_BFIVE.get(_d)
        _ov = -1 if _ref is None else len([c for c in g.bfive if c in _ref])
        _empty = 1 if df.shape[0] <= g.stock_num*2 else 0
        _in = [c for c in g.bfive if _ref is not None and c not in _ref]
        _out = [c for c in (_ref or []) if c not in g.bfive]
        log.info('DXMON date=%s n_qual=%d empty=%d bfive=%s bten=%s ref_overlap=%d ref_bfive=%s in=%s out=%s' % (_d, df.shape[0], _empty, ','.join(g.bfive), ','.join(g.bten), _ov, ','.join(_ref or []), ','.join(_in), ','.join(_out)))
    except Exception as _e:
        log.error('DXN-ERR mon err=%r' % (_e,))
# ===== end u-e9-dxno601229 observation helpers =====
`;
body = body + HELPERS;

// ---- assertions ----
for (const k of ['order_target_value', 'order_value', 'order(', 'run_monthly', 'run_daily', 'run_weekly', '.limit(12))', 'board_plan_pub_date<=d0', 'comp_value=market_cap*0.02',
  "g.bten=list(df.head(g.stock_num*2)['code'])", "g.bfive=list(df.head(g.stock_num)['code'])", 'g.stock_num = 5',
  "sort_values(by='gxl'", "sort_values(by='gxl2'", "sort_values(by='gxl3'"]) {
  if (SEM.split(k).length !== STRIPPED.split(k).length) throw new Error('verbatim element changed: ' + k);
}
if (!SEM.includes("run_monthly(main,1,time='9:30')")) throw new Error('schedule changed');
if (!SEM.includes('    if df.shape[0]<=g.stock_num*2: \n        g.bten=[]\n        g.bfive=[]\n        return \n')) throw new Error('empty-month rule changed');
if ((SEM.match(/'601229\.XSHG'/g) || []).length !== 1) throw new Error('expected exactly one 601229 in strategy code');
if (SEM.split('\n').length - STRIPPED.split('\n').length !== 1) throw new Error('expected net +1 line');
if (body.slice(0, body.length - HELPERS.length) !== SEM) throw new Error('obs not additive');

const out = path.join(__dirname, 'variants', 'dxno601229.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
