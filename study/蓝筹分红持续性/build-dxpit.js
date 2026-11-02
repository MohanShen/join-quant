// u-e9-dxpit: honest-announcement baseline. study/蓝筹分红持续性/baseline.py (base 94888e61 + py2to3 +
// OVERRIDE) plus:
//   (1) ONE semantic edit — the L60-63 STK_XR_XD query only counts rows announced by the rebalance date.
//       The bound is in the SQL filter, so .limit(12) is applied AFTER it (== dxla's honest replay).
//       d0 = context.current_dt.date() is passed into controlReport (signature + call site carry it).
//       Null rule = dxla's honest replay: pub = board_plan_pub_date, else min(shareholders_plan_pub_date,
//       implementation_pub_date); a row with NO announcement date at all is KEPT (dxla: 0 such rows,
//       DXNULL=0). Expressed in SQL as
//         board <= d0  OR  (board IS NULL AND (share <= d0 OR impl <= d0 OR (share IS NULL AND impl IS NULL)))
//   (2) observation only (each helper try/except -> log.error, nothing feeds an order):
//       DXMON   per rebalance: n_qual, bfive, bten (cross-check vs dxla bfive_honest/bten_honest)
//       DXPRE / DXPOST  per-holding value before / after orderStock, + cash
//       after_trading_end: DXVAL per holding daily; DXRESID cash not explained by today's fills;
//                          DXDIV STK_XR_XD rows (a_xr_date or a_bonus_date == today) for held names;
//                          DXPNL cumulative per-name P&L (value change + fill cash flows + attributed
//                          dividend residual) on each month's last trading day, incl. 2024-12-31.
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const base = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');
if (!base.endsWith(OVERRIDE)) throw new Error('baseline.py does not end with the live OVERRIDE');
const raw = base.slice(0, base.length - OVERRIDE.length);

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

// ---- (1) the semantic edit ----
let body = edit(raw, "    df=controlReport(df)\n", "    df=controlReport(df, context.current_dt.date())  # u-e9-dxpit: pass d0\n");
body = edit(body, "def controlReport(df):\n", "def controlReport(df, d0):  # u-e9-dxpit: d0 = rebalance date\n");
const F = "            finance.STK_XR_XD.report_date<=statDate\n            ).order_by(finance.STK_XR_XD.report_date.desc()).limit(12))\n";
body = edit(body, F,
  "            finance.STK_XR_XD.report_date<=statDate,\n" +
  "            # u-e9-dxpit: announcement bound (dxla null rule), BEFORE the 12-row limit\n" +
  "            (finance.STK_XR_XD.board_plan_pub_date<=d0) | ((finance.STK_XR_XD.board_plan_pub_date==None) & (\n" +
  "                (finance.STK_XR_XD.shareholders_plan_pub_date<=d0) | (finance.STK_XR_XD.implementation_pub_date<=d0) |\n" +
  "                ((finance.STK_XR_XD.shareholders_plan_pub_date==None) & (finance.STK_XR_XD.implementation_pub_date==None))))\n" +
  "            ).order_by(finance.STK_XR_XD.report_date.desc()).limit(12))\n");
const SEM = body;

// ---- (2) observation only ----
body = edit(body, "    setSmallStocks(df)\n", "    setSmallStocks(df)\n    _dxp_mon(context, df)  # u-e9-dxpit obs\n");
body = edit(body, "    orderStock(context)\n", "    _dxp_pos(context, 'DXPRE')  # u-e9-dxpit obs\n    orderStock(context)\n    _dxp_pos(context, 'DXPOST')  # u-e9-dxpit obs\n");

const HELPERS = `

# ===== u-e9-dxpit observation helpers (nothing below feeds an order) =====
def _dxp_mon(context, df):
    try:
        log.info('DXMON date=%s n_qual=%d bfive=%s bten=%s' % (str(context.current_dt.date()), df.shape[0], ','.join(g.bfive), ','.join(g.bten)))
    except Exception as _e:
        log.error('DXP-ERR mon err=%r' % (_e,))

def _dxp_pos(context, tag):
    try:
        _d = str(context.current_dt.date())
        _t = 0.0
        for _c in sorted(context.portfolio.long_positions.keys()):
            _p = context.portfolio.long_positions[_c]
            _t += _p.value
            log.info('%s date=%s code=%s amount=%d price=%.4f value=%.2f' % (tag, _d, _c, _p.total_amount, _p.price, _p.value))
        log.info('%sTOT date=%s total=%.2f pos=%.2f cash=%.2f n=%d' % (tag, _d, context.portfolio.total_value, _t, context.portfolio.available_cash, len(context.portfolio.long_positions)))
    except Exception as _e:
        log.error('DXP-ERR pos err=%r' % (_e,))

def after_trading_end(context):
    try:
        _d = context.current_dt.date()
        _ds = str(_d)
        if not hasattr(g, 'dxp_pnl'):
            g.dxp_pnl = {}
            g.dxp_prev = {}
            g.dxp_amt = {}
            g.dxp_cash = None
        _flow = {}
        _os = get_orders()
        for _k in _os:
            _o = _os[_k]
            try:
                _f = _o.filled
            except Exception:
                _f = 0
            if not _f:
                continue
            _px = _o.price
            _cm = getattr(_o, 'commission', 0.0) or 0.0
            _cf = (-(_f * _px) - _cm) if _o.is_buy else ((_f * _px) - _cm)
            _flow[_o.security] = _flow.get(_o.security, 0.0) + _cf
            log.info('DXFILL date=%s code=%s buy=%d filled=%d price=%.4f commission=%.2f cashflow=%.2f' % (_ds, _o.security, 1 if _o.is_buy else 0, _f, _px, _cm, _cf))
        _vals = {}
        _amts = {}
        for _c in context.portfolio.long_positions.keys():
            _p = context.portfolio.long_positions[_c]
            _vals[_c] = _p.value
            _amts[_c] = _p.total_amount
            log.info('DXVAL date=%s code=%s amount=%d price=%.4f value=%.2f' % (_ds, _c, _p.total_amount, _p.price, _p.value))
        _cash = context.portfolio.available_cash
        log.info('DXCASH date=%s cash=%.2f total=%.2f' % (_ds, _cash, context.portfolio.total_value))
        _names = set(_vals.keys()) | set(g.dxp_prev.keys()) | set(_flow.keys())
        for _c in _names:
            g.dxp_pnl[_c] = g.dxp_pnl.get(_c, 0.0) + _vals.get(_c, 0.0) - g.dxp_prev.get(_c, 0.0) + _flow.get(_c, 0.0)
        if g.dxp_cash is not None:
            _resid = _cash - g.dxp_cash - sum(_flow.values())
            if abs(_resid) > 0.5:
                _held = list(set(g.dxp_amt.keys()) | set(_amts.keys()))
                _exp = {}
                if _held:
                    S = finance.STK_XR_XD
                    _xr = finance.run_query(query(S.code, S.bonus_ratio_rmb, S.a_xr_date, S.a_bonus_date).filter(
                        S.code.in_(_held)).order_by(S.report_date.desc()).limit(200))
                    for _i in range(len(_xr)):
                        _r = _xr.iloc[_i]
                        _xd = str(_r['a_xr_date'])[:10]
                        _bd = str(_r['a_bonus_date'])[:10]
                        if _xd == _ds or _bd == _ds:
                            _br = _r['bonus_ratio_rmb']
                            _br = 0.0 if _br is None or _br != _br else float(_br)
                            _am = g.dxp_amt.get(_r['code'], _amts.get(_r['code'], 0))
                            _e = _am * _br / 10.0
                            _exp[_r['code']] = _exp.get(_r['code'], 0.0) + _e
                            log.info('DXDIV date=%s code=%s ratio=%.4f amount=%d exp=%.2f xr=%s pay=%s' % (_ds, _r['code'], _br, _am, _e, _xd, _bd))
                _se = sum(_exp.values())
                if _se > 0:
                    for _c in _exp:
                        g.dxp_pnl[_c] = g.dxp_pnl.get(_c, 0.0) + _resid * _exp[_c] / _se
                else:
                    g.dxp_pnl['_unattr'] = g.dxp_pnl.get('_unattr', 0.0) + _resid
                log.info('DXRESID date=%s resid=%.2f exp_sum=%.2f attributed=%d' % (_ds, _resid, _se, 1 if _se > 0 else 0))
        g.dxp_prev = _vals
        g.dxp_amt = _amts
        g.dxp_cash = _cash
        _last = (_ds == '2024-12-31')
        try:
            import datetime as _dtm
            _nx = [x for x in get_trade_days(start_date=_d, end_date=_d + _dtm.timedelta(days=12)) if x > _d]
            if len(_nx) == 0 or _nx[0].month != _d.month:
                _last = True
        except Exception as _e2:
            log.error('DXP-ERR tradedays err=%r' % (_e2,))
        if _last:
            _tot = sum(g.dxp_pnl.values())
            for _c in sorted(g.dxp_pnl.keys(), key=lambda k: -g.dxp_pnl[k]):
                log.info('DXPNL date=%s code=%s pnl=%.2f share=%.4f' % (_ds, _c, g.dxp_pnl[_c], (g.dxp_pnl[_c] / _tot) if _tot else 0.0))
            log.info('DXPNLTOT date=%s pnl=%.2f total_value=%.2f' % (_ds, _tot, context.portfolio.total_value))
    except Exception as _e:
        log.error('DXP-ERR ate err=%r' % (_e,))
# ===== end u-e9-dxpit observation helpers =====
`;
body = body + HELPERS;

// ---- assertions ----
for (const k of ['order_target_value', 'order_value', 'order(', 'run_monthly', 'run_daily', 'run_weekly']) {
  if (body.split(k).length !== raw.split(k).length) throw new Error('order/schedule calls changed: ' + k);
}
if (!body.includes("run_monthly(main,1,time='9:30')")) throw new Error('schedule changed');
if (!body.includes('.limit(12))')) throw new Error('limit(12) missing');
if (raw.includes('after_trading_end')) throw new Error('base already defines after_trading_end');
// obs layer is purely additive over the semantic edit
const stripObs = body
  .replace("    _dxp_mon(context, df)  # u-e9-dxpit obs\n", '')
  .replace("    _dxp_pos(context, 'DXPRE')  # u-e9-dxpit obs\n", '')
  .replace("    _dxp_pos(context, 'DXPOST')  # u-e9-dxpit obs\n", '')
  .replace(HELPERS, '');
if (stripObs !== SEM) throw new Error('observation layer is not purely additive');

const out = path.join(__dirname, 'variants', 'dxpit.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
