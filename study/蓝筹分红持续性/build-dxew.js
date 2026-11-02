// u-e9-dxew: style-basket test on the REFERENCE BOOK variants/dxpit.py.
//   (1) semantic change: hold ALL qualifiers (df after controlReport = names passing the persistence
//       gate) equal-weight, rebalanced monthly. setSmallStocks records g.ball = all qualifier codes
//       (empty-month rule n<=stock_num*2 verbatim, which also empties g.ball). orderStock is replaced:
//       sell every holding not in g.ball, then order_target_value(code, total_value/len(g.ball)) for
//       every qualifier — trims first (frees cash), then buys/tops-up.
//       ⚠ This RESIZES held names every month, whereas the reference never resizes (it only buys
//       names it does not hold, at all_value/5, if cash > half a slot). Necessary for "equal weight"
//       with ~50 names; it is a second difference from the reference beside selection.
//       The bten/bfive cascade still runs (computed, logged) but nothing orders from it.
//   (2) observation: dxpit's DXPRE/DXPOST + after_trading_end P&L logger DROPPED (crashed daily).
//       DXMON kept (n_qual, bfive, bten) + DXEW per month: n_target, orders placed, None-returns
//       (failed / sub-lot), failed codes, holdings count after.
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
body = edit(body, "    _dxp_pos(context, 'DXPOST')  # u-e9-dxpit obs\n", "    _dxe_post(context)  # u-e9-dxew obs\n");
body = edit(body, "    _dxp_mon(context, df)  # u-e9-dxpit obs\n", "    _dxe_mon(context, df)  # u-e9-dxew obs\n");
if (/_dxp_|after_trading_end|DXPNL/.test(body)) throw new Error('dxpit obs residue');
const STRIPPED = body;

// ---- (1) semantic edits ----
body = edit(body,
  "    if df.shape[0]<=g.stock_num*2: \n        g.bten=[]\n        g.bfive=[]\n        return \n",
  "    if df.shape[0]<=g.stock_num*2: \n        g.bten=[]\n        g.bfive=[]\n        g.ball=[]  # u-e9-dxew\n        return \n" +
  "    g.ball=list(df['code'])  # u-e9-dxew: ALL qualifiers\n");

const OLD_ORDER = `def orderStock(context):

    bfive=g.bfive
    bten=g.bten

    all_value=context.portfolio.total_value
    for sell_code in context.portfolio.long_positions.keys():
        if sell_code not in bfive:
            #卖掉
            log.info('sell all:',sell_code)
            order_target_value(sell_code,0)
        #else:
        #    log.info('sell part:'+sell_code)
        #    order_target_value(sell_code,all_value/g.stock_num)

    for buy_code in bten:
        if buy_code not in context.portfolio.long_positions.keys():
            cash_value=context.portfolio.available_cash
            buy_value=all_value/g.stock_num

            if cash_value > buy_value/2 :
                log.info('buy:'+buy_code+'   ' +str(buy_value))
                order_target_value(buy_code,buy_value)
`;
const NEW_ORDER = `def orderStock(context):
    # u-e9-dxew: equal-weight ALL qualifiers, resized monthly (reference never resizes)
    target=list(g.ball)
    g.dxe_n=0
    g.dxe_none=[]
    all_value=context.portfolio.total_value
    for sell_code in list(context.portfolio.long_positions.keys()):
        if sell_code not in target:
            g.dxe_n+=1
            if order_target_value(sell_code,0) is None:
                g.dxe_none.append('S:'+sell_code)
    if len(target)==0:
        return
    tv=all_value/len(target)
    held=context.portfolio.long_positions
    trimmed=[]
    for code in target:
        if code in held.keys() and held[code].value>tv:
            trimmed.append(code)
            g.dxe_n+=1
            if order_target_value(code,tv) is None:
                g.dxe_none.append('T:'+code)
    for code in target:
        if code not in trimmed and (code not in held.keys() or held[code].value<tv):
            g.dxe_n+=1
            if order_target_value(code,tv) is None:
                g.dxe_none.append('B:'+code)
`;
{
  // the source carries trailing-whitespace lines; slice by anchors and compare whitespace-normalised
  const o0 = body.indexOf('def orderStock(context):\n'), o1 = body.indexOf('def set_param():\n');
  if (o0 < 0 || o1 < o0 || body.split('def orderStock(context):\n').length !== 2) throw new Error('orderStock anchors');
  const norm = s => s.split('\n').map(l => l.replace(/\s+$/, '')).join('\n').replace(/\n+$/, '');
  if (norm(body.slice(o0, o1)) !== norm(OLD_ORDER)) throw new Error('orderStock body is not the expected reference text');
  body = body.slice(0, o0) + NEW_ORDER + body.slice(o1);
}
body = edit(body, "    g.bfive=[]\n    g.stock_num = 5\n", "    g.bfive=[]\n    g.ball=[]  # u-e9-dxew\n    g.stock_num = 5\n");
const SEM = body;

// ---- (2) observation ----
const HELPERS = `

# ===== u-e9-dxew observation helpers (nothing below feeds an order) =====
def _dxe_mon(context, df):
    try:
        log.info('DXMON date=%s n_qual=%d n_target=%d bfive=%s bten=%s' % (str(context.current_dt.date()), df.shape[0], len(g.ball), ','.join(g.bfive), ','.join(g.bten)))
    except Exception as _e:
        log.error('DXE-ERR mon err=%r' % (_e,))

def _dxe_post(context):
    try:
        _pos = context.portfolio.long_positions
        _miss = [c for c in g.ball if c not in _pos.keys()]
        _star = [c for c in g.ball if c.startswith('688')]
        log.info('DXEW date=%s n_target=%d n_orders=%d n_none=%d none=%s n_held=%d missing=%s star=%s cash=%.2f total=%.2f' % (
            str(context.current_dt.date()), len(g.ball), getattr(g, 'dxe_n', 0), len(getattr(g, 'dxe_none', [])),
            ','.join(getattr(g, 'dxe_none', [])), len(_pos), ','.join(_miss), ','.join(_star),
            context.portfolio.available_cash, context.portfolio.total_value))
    except Exception as _e:
        log.error('DXE-ERR post err=%r' % (_e,))
# ===== end u-e9-dxew observation helpers =====
`;
body = body + HELPERS;

// ---- assertions ----
for (const k of ['run_monthly', 'run_daily', 'run_weekly', '.limit(12))', 'board_plan_pub_date<=d0', 'comp_value=market_cap*0.02',
  "if one_year>comp_value and two_year>comp_value*0.8 and three_year>comp_value*0.64 and (one_year+two_year+three_year)>market_cap*0.1:"]) {
  if (body.split(k).length !== STRIPPED.split(k).length) throw new Error('schedule/gate/pit changed: ' + k);
}
if (!body.includes("run_monthly(main,1,time='9:30')")) throw new Error('schedule changed');
if (!body.includes('    if df.shape[0]<=g.stock_num*2: \n        g.bten=[]\n        g.bfive=[]\n')) throw new Error('empty-month rule changed');
if (/order_target_value\(buy_code|bten:\n/.test(SEM.slice(SEM.indexOf('def orderStock')))) throw new Error('old order path remains');
const a = STRIPPED.split('\n').length, b = SEM.split('\n').length;
console.log('lines', a, '->', b);
if (body.slice(0, body.length - HELPERS.length) !== SEM) throw new Error('obs not additive');

const out = path.join(__dirname, 'variants', 'dxew.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
