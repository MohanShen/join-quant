// u-e9-dxla: lookahead probe of controlReport's STK_XR_XD dividend sums. Base 94888e61 + py2to3 +
// OVERRIDE (== baseline.py) plus OBSERVATION ONLY. Three single-line call sites are added; every
// helper is a new module-level function with its own try/except that log.error's loudly.
//   main() entry        -> _dx_enter(context): stamps d0, resets the honest set, logs DXPOS.
//   controlReport loop  -> _dx_name(...): a SECOND run_query (same filter, report_date <= statDate,
//                          order report_date desc, limit 16) with the pub-date columns. Logs DXLA for
//                          every row the book counted (book = first 12, in a statq window) that has
//                          any date > d0; recomputes one/two/three_year from rows whose pub date
//                          <= d0 with the 12-row cut AFTER the filter; logs DXFLIP when
//                          qualify(book) != qualify(honest). DXTIE if the probe's own unfiltered
//                          first 12 do not reproduce the book's sums (probe control).
//   after setSmallStocks -> _dx_month(context, df): DXMON (book vs honest qualifiers / bfive / bten /
//                          empty), DXREP (replicated selection != g.bfive/g.bten => replica broken),
//                          DXG5 (top-5 by gxl alone), DXIND (industry of bfive_book).
// The book's queries, sums, qualification, selection and orders are untouched.
// Control: must reproduce 39.00 / 1.81 / 15.48 / 0.2352 (TRAIN 2024, e9) bit-identical.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-20_蓝筹大盘分红策略_超稳健-94888e61.py';
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

const CALL1 = "    _dx_enter(context)  # u-e9-dxla probe\n";
const CALL2 = "        _dx_name(code, statDate, statqs, one_year, two_year, three_year, market_cap)  # u-e9-dxla probe\n";
const CALL3 = "    _dx_month(context, df)  # u-e9-dxla probe\n";

const A1 = "def main(context):\n";
const A2 = "            df_qc=df_qc.append(cc,ignore_index=True)\n";
const A3 = "    setSmallStocks(df)\n";

const HELPERS = `

# ===== u-e9-dxla probe helpers (observation only; nothing below feeds an order) =====
def _dx_enter(context):
    try:
        g.dx_d0 = str(context.current_dt.date())
        g.dx_honest = []
        g.dx_cnt = {'names': 0, 'dxla_rows': 0, 'dxla_rows_nz': 0, 'flips': 0, 'ties': 0, 'nulls': 0, 'cut': 0}
        _tot = 0.0
        for _c in list(context.portfolio.long_positions.keys()):
            _p = context.portfolio.long_positions[_c]
            _tot += _p.value
            log.info('DXPOS date=%s code=%s value=%.2f' % (g.dx_d0, _c, _p.value))
        log.info('DXPOSTOT date=%s total=%.2f pos=%.2f cash=%.2f n=%d' % (g.dx_d0, context.portfolio.total_value, _tot, context.portfolio.available_cash, len(context.portfolio.long_positions)))
    except Exception as _e:
        log.error('DX-ERR enter err=%r' % (_e,))

def _dx_ds(v):
    _s = str(v)[:10]
    if len(_s) == 10 and _s[:4].isdigit():
        return _s
    return None

def _dx_sums(bon, rds, statqs):
    _o = 0.0
    _t = 0.0
    _h = 0.0
    for _j in range(len(rds)):
        _rd = rds[_j]
        _sq = str(_rd.year) + 'q' + str(_rd.month // 3)
        if _sq in (statqs[0], statqs[1], statqs[2], statqs[3]):
            _o = _o + bon[_j]
        if _sq in (statqs[4], statqs[5], statqs[6], statqs[7]):
            _t = _t + bon[_j]
        if _sq in (statqs[8], statqs[9], statqs[10], statqs[11]):
            _h = _h + bon[_j]
    return _o, _t, _h

def _dx_qual(o, t, h, mc):
    _cv = mc * 0.02
    return 1 if (o > _cv and t > _cv * 0.8 and h > _cv * 0.64 and (o + t + h) > mc * 0.1) else 0

def _dx_name(code, statDate, statqs, one_year, two_year, three_year, market_cap):
    try:
        _d0 = g.dx_d0
        g.dx_cnt['names'] += 1
        S = finance.STK_XR_XD
        _pq = finance.run_query(query(S.bonus_amount_rmb, S.report_date, S.board_plan_pub_date,
                                      S.shareholders_plan_pub_date, S.implementation_pub_date,
                                      S.a_bonus_date, S.plan_progress).filter(
            S.code == code,
            S.report_date <= statDate
            ).order_by(S.report_date.desc()).limit(16))
        _n = len(_pq)
        _bon = []
        _rds = []
        _pub = []
        _win = set(statqs[:12])
        for _j in range(_n):
            _r = _pq.iloc[_j]
            _b = _r['bonus_amount_rmb']
            try:
                _b = 0.0 if _b != _b or _b is None else float(_b)
            except Exception:
                _b = 0.0
            _bon.append(_b)
            _rd = _r['report_date']
            _rds.append(_rd)
            _bd = _dx_ds(_r['board_plan_pub_date'])
            _sd = _dx_ds(_r['shareholders_plan_pub_date'])
            _id = _dx_ds(_r['implementation_pub_date'])
            _ad = _dx_ds(_r['a_bonus_date'])
            _alt = [x for x in (_sd, _id) if x is not None]
            _p = _bd if _bd is not None else (min(_alt) if _alt else None)
            _pub.append(_p)
            if _j < 12:
                _sq = str(_rd.year) + 'q' + str(_rd.month // 3)
                if _sq in _win:
                    _fut = []
                    for _nm, _v in (('board', _bd), ('share', _sd), ('impl', _id), ('a_bonus', _ad)):
                        if _v is not None and _v > _d0:
                            _fut.append(_nm)
                    if _fut:
                        g.dx_cnt['dxla_rows'] += 1
                        if _b != 0:
                            g.dx_cnt['dxla_rows_nz'] += 1
                        log.info('DXLA date=%s code=%s statDate=%s report_date=%s bonus=%.0f board=%s share=%s impl=%s a_bonus=%s progress=%s fut=%s' % (_d0, code, statDate, str(_rd)[:10], _b, _bd, _sd, _id, _ad, _r['plan_progress'], ','.join(_fut)))
            if _p is None:
                g.dx_cnt['nulls'] += 1
                log.info('DXNULL date=%s code=%s report_date=%s pub=null' % (_d0, code, str(_rd)[:10]))
        # probe control: the probe's own unfiltered first 12 must reproduce the book's sums
        _bo, _bt, _bh = _dx_sums(_bon[:12], _rds[:12], statqs)
        if abs(_bo - one_year) > 1e-6 * max(1.0, abs(one_year)) or abs(_bt - two_year) > 1e-6 * max(1.0, abs(two_year)) or abs(_bh - three_year) > 1e-6 * max(1.0, abs(three_year)):
            g.dx_cnt['ties'] += 1
            log.error('DXTIE date=%s code=%s book=%.0f/%.0f/%.0f probe12=%.0f/%.0f/%.0f' % (_d0, code, one_year, two_year, three_year, _bo, _bt, _bh))
        # honest: drop rows announced after d0 (null pub -> known), THEN cut to 12
        _keep = [_j for _j in range(_n) if _pub[_j] is None or _pub[_j] <= _d0]
        if _n == 16 and len(_keep) < 12:
            g.dx_cnt['cut'] += 1
            log.error('DXCUT date=%s code=%s kept=%d of 16 (limit 16 may truncate the honest set)' % (_d0, code, len(_keep)))
        _keep = _keep[:12]
        _ho, _ht, _hh = _dx_sums([_bon[_j] for _j in _keep], [_rds[_j] for _j in _keep], statqs)
        _qb = _dx_qual(one_year, two_year, three_year, market_cap)
        _qh = _dx_qual(_ho, _ht, _hh, market_cap)
        if _qh:
            g.dx_honest.append((code, _ho / market_cap, _ht / market_cap, _hh / market_cap))
        if _qb != _qh:
            g.dx_cnt['flips'] += 1
            log.info('DXFLIP date=%s code=%s book=%d honest=%d book_sums=%.0f/%.0f/%.0f honest_sums=%.0f/%.0f/%.0f mcap=%.0f' % (_d0, code, _qb, _qh, one_year, two_year, three_year, _ho, _ht, _hh, market_cap))
    except Exception as _e:
        log.error('DX-ERR name date=%s code=%s err=%r' % (str(getattr(g, 'dx_d0', '?')), code, _e))

def _dx_select(df, n):
    # exact replica of setSmallStocks, returning instead of writing g
    if df.shape[0] <= n * 2:
        return [], [], 1
    df = df.sort_values(by='gxl', ascending=False).head(n * 16)
    if len(df) < n * 4:
        df = df.head(len(df) - n * 2)
    df = df.sort_values(by='gxl2', ascending=False).head(n * 8)
    df = df.sort_values(by='gxl3', ascending=False).head(n * 4)
    df = df.sort_values(by='gxl', ascending=False).head(n * 2)
    return list(df.head(n * 2)['code']), list(df.head(n)['code']), 0

def _dx_month(context, df):
    try:
        _d0 = g.dx_d0
        _n = g.stock_num
        _bten, _bfive, _be = _dx_select(df, _n)
        if _bten != list(g.bten) or _bfive != list(g.bfive):
            log.error('DXREP date=%s replica=%s/%s actual=%s/%s' % (_d0, _bfive, _bten, list(g.bfive), list(g.bten)))
        _hdf = pd.DataFrame(g.dx_honest, columns=['code', 'gxl', 'gxl2', 'gxl3'])
        _hten, _hfive, _he = _dx_select(_hdf, _n)
        log.info('DXMON date=%s n_qual_book=%d n_qual_honest=%d bfive_book=%s bfive_honest=%s bten_book=%s bten_honest=%s empty_book=%d empty_honest=%d five_diff=%d ten_diff=%d' % (
            _d0, df.shape[0], len(_hdf), ','.join(g.bfive), ','.join(_hfive), ','.join(g.bten), ','.join(_hten),
            _be, _he, 1 if list(g.bfive) != _hfive else 0, 1 if list(g.bten) != _hten else 0))
        log.info('DXCNT date=%s %s' % (_d0, ' '.join('%s=%d' % (k, g.dx_cnt[k]) for k in sorted(g.dx_cnt))))
        if df.shape[0] > 0:
            _g5 = list(df.sort_values(by='gxl', ascending=False).head(_n)['code'])
        else:
            _g5 = []
        log.info('DXG5 date=%s bfive_gxlonly=%s' % (_d0, ','.join(_g5)))
        if len(g.bfive) > 0:
            _ci = finance.run_query(query(finance.STK_COMPANY_INFO.code, finance.STK_COMPANY_INFO.industry_id,
                                          finance.STK_COMPANY_INFO.industry_1).filter(
                finance.STK_COMPANY_INFO.code.in_(list(g.bfive))))
            for _i in range(len(_ci)):
                log.info('DXIND date=%s code=%s industry_id=%s industry_1=%s' % (_d0, _ci['code'].iloc[_i], _ci['industry_id'].iloc[_i], _ci['industry_1'].iloc[_i]))
    except Exception as _e:
        log.error('DX-ERR month date=%s err=%r' % (str(getattr(g, 'dx_d0', '?')), _e))
# ===== end u-e9-dxla probe helpers =====
`;

let body = edit(raw, A1, A1 + CALL1);
body = edit(body, A2, A2 + CALL2);
body = edit(body, A3, A3 + CALL3);
body = body + HELPERS;

for (const k of ['order_target_value', 'order_value', 'order(', 'run_monthly', 'run_daily', 'run_weekly']) {
  if (body.split(k).length !== raw.split(k).length) throw new Error('order/schedule calls changed: ' + k);
}
if (!body.includes("run_monthly(main,1,time='9:30')")) throw new Error('schedule changed');
if (body.replace(CALL1, '').replace(CALL2, '').replace(CALL3, '').replace(HELPERS, '') !== raw) {
  throw new Error('edit is not purely additive');
}

const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, 'dxla.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
