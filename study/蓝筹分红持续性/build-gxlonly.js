// i-1-gxlonly (improve): on the REFERENCE BOOK variants/dxpit.py, keep the persistence gate (dxpit L93,
//   base L86) EXACTLY, and replace the four-pass cascade (gxl head(80) -> <20 cut -> gxl2 head(40) ->
//   gxl3 head(20) -> gxl head(10)) by ONE pass: sort qualifiers by gxl descending, head(10);
//   bten = top 10, bfive = top 5 (the two assignment lines are verbatim). Empty-month rule, order logic,
//   sizing and schedule verbatim.
//   Note: with n_qual >= 20 (dxpit min 47) the <20 cut cannot fire, so this is equivalent to the queue's
//   "delete L102-103" design.
//   Observation: dxpit's DXPRE/DXPOST + P&L logger DROPPED (as build-dxpers.js). DXMON kept with n_qual,
//   empty flag, bfive, bten, ref_overlap vs dxpit bfive.
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
body = edit(body, "    _dxp_mon(context, df)  # u-e9-dxpit obs\n", "    _dxg_mon(context, df)  # i-1-gxlonly obs\n");
if (/_dxp_|after_trading_end|DXPNL/.test(body)) throw new Error('dxpit obs residue');
const STRIPPED = body;

// ---- (1) semantic edit: cascade -> single gxl rank ----
const GATE = "        if one_year>comp_value and two_year>comp_value*0.8 and three_year>comp_value*0.64 and (one_year+two_year+three_year)>market_cap*0.1:\n";
if (body.split(GATE).length !== 2) throw new Error('persistence gate not found exactly once');
const CASCADE =
  "    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*16)\n" +
  "    if len(df)<g.stock_num*4:\n" +
  "        df=df.head(len(df) -g.stock_num*2)\n" +
  "    df=df.sort_values(by='gxl2',ascending=False).head(g.stock_num*8)\n" +
  "    df=df.sort_values(by='gxl3',ascending=False).head(g.stock_num*4)\n" +
  "    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*2)\n";
const SINGLE = "    df=df.sort_values(by='gxl',ascending=False).head(g.stock_num*2)  # i-1-gxlonly: cascade collapsed to one gxl rank\n";
body = edit(body, CASCADE, SINGLE);
const SEM = body;

// ---- (2) DXMON + overlap vs reference ----
const refLog = fs.readFileSync(path.join(__dirname, 'variants', 'dxpit.log.txt'), 'utf8');
const refMon = {};
for (const m of refLog.matchAll(/DXMON date=(\S+) n_qual=(\d+) bfive=(\S*) bten=/g)) refMon[m[1]] = m[3].split(',').filter(Boolean);
if (Object.keys(refMon).length !== 12) throw new Error('expected 12 reference DXMON months, got ' + Object.keys(refMon).length);
const pyDict = '{' + Object.entries(refMon).map(([d, l]) => `'${d}': [${l.map(c => `'${c}'`).join(', ')}]`).join(',\n    ') + '}';
const HELPERS = `

# ===== i-1-gxlonly observation helpers (nothing below feeds an order) =====
_DXG_REF_BFIVE = ${pyDict}

def _dxg_mon(context, df):
    try:
        _d = str(context.current_dt.date())
        _ref = _DXG_REF_BFIVE.get(_d)
        _ov = -1 if _ref is None else len([c for c in g.bfive if c in _ref])
        _empty = 1 if df.shape[0] <= g.stock_num*2 else 0
        log.info('DXMON date=%s n_qual=%d empty=%d bfive=%s bten=%s ref_overlap=%d ref_bfive=%s' % (_d, df.shape[0], _empty, ','.join(g.bfive), ','.join(g.bten), _ov, ','.join(_ref or [])))
    except Exception as _e:
        log.error('DXG-ERR mon err=%r' % (_e,))
# ===== end i-1-gxlonly observation helpers =====
`;
body = body + HELPERS;

// ---- assertions ----
for (const k of ['order_target_value', 'order_value', 'order(', 'run_monthly', 'run_daily', 'run_weekly', '.limit(12))', 'board_plan_pub_date<=d0', 'comp_value=market_cap*0.02', GATE, "g.bten=list(df.head(g.stock_num*2)['code'])", "g.bfive=list(df.head(g.stock_num)['code'])", 'g.stock_num = 5']) {
  if (body.split(k).length !== STRIPPED.split(k).length) throw new Error('verbatim element changed: ' + k);
}
if (!body.includes("run_monthly(main,1,time='9:30')")) throw new Error('schedule changed');
if (!body.includes('    if df.shape[0]<=g.stock_num*2: \n        g.bten=[]\n        g.bfive=[]\n        return \n')) throw new Error('empty-month rule changed');
if (/sort_values\(by='gxl[23]'/.test(SEM) || SEM.includes('stock_num*16') || SEM.includes('len(df) -g.stock_num*2')) throw new Error('cascade residue');
const a = STRIPPED.split('\n'), b = SEM.split('\n');
if (a.length - b.length !== 5) throw new Error('expected exactly 5 lines net removed');
if (body.slice(0, body.length - HELPERS.length) !== SEM) throw new Error('obs not additive');

const out = path.join(__dirname, 'variants', 'gxlonly.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
