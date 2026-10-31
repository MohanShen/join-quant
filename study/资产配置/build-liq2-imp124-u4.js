// Builds liq-2 / imp-2 / imp-4 / u-4 / imp-1 from study/资产配置/baseline.py (liq-2 from
// variants/liq-1-floor.py), each by asserted edits only. Trading logic outside the named
// change is verbatim. Improve candidates go to enhance/candidates/zcpz-<id>.py.
const fs = require('fs');
const path = require('path');
const D = __dirname + '/';
const ROOT = path.join(__dirname, '../..');
const base = fs.readFileSync(D + 'baseline.py', 'utf8');
function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error('expected 1 match, got ' + n + ': ' + from.slice(0, 80));
  return s.replace(from, to);
}
const W = `    g.etf_weights = {
        '515450.XSHG': 0.2,   # 红利低波ETF
        '513630.XSHG': 0.2,   # 香港红利低波ETF
        '513100.XSHG': 0.20,   # 纳指ETF
        '518880.XSHG': 0.20,   # 黄金ETF
        '513650.XSHG': 0.20,  # 标普ETF
    }`;
const N = `    g.etf_names = {
        '515450.XSHG': '红利低波ETF',
        '513630.XSHG': '港股红利低波ETF',
        '513100.XSHG': '纳指ETF',
        '518880.XSHG': '黄金ETF',
        '513650.XSHG': '标普ETF',
    }`;
const LOOP_FROM = `    target_values = {}
    for etf, weight in g.etf_weights.items():`;
const ANCHOR_FN = `def order_target_by_lot(context, security, target_value, current_data):`;
const LISTCHECK = `
    # listing-date check (pre-run fact): every pool name must list before the TRAIN start
    g.listcheck_fail = []
    for _s in g.etf_weights:
        try:
            _sd = get_security_info(_s).start_date
        except Exception as _e:
            _sd = None
        log.error('LISTCHECK %s start_date=%s' % (_s, _sd))
        if _sd is None or str(_sd) >= '2024-01-01':
            g.listcheck_fail.append(_s)
    if g.listcheck_fail:
        log.error('LISTCHECK FAIL %s -- run will not trade' % ','.join(g.listcheck_fail))
`;
const LISTGUARD_FROM = `    if not g.need_rebalance:
        return
`;
const LISTGUARD_TO = LISTGUARD_FROM + `    if g.listcheck_fail:
        return
`;

const out = [];
function write(rel, header, s) {
  fs.writeFileSync(path.join(ROOT, rel), header + '\n' + s);
  out.push(rel);
}

// ---------- liq-2: liq-1 with the floor at 10x ----------
let liq1 = fs.readFileSync(D + 'variants/liq-1-floor.py', 'utf8');
let l2 = edit(liq1, `LIQ_FLOOR = 4000000\n`, `LIQ_FLOOR = 40000000  # liq-2: ONLY change vs liq-1-floor.py — 10x the feasibility floor\n`);
l2 = edit(l2, `# liq-1 variant of study/资产配置/baseline.py\n`, '');
write('study/资产配置/variants/liq-2-floor10x.py', '# liq-2 variant of study/资产配置/variants/liq-1-floor.py (floor 4e7)', l2);

// ---------- shared weight-function insertion ----------
function withWeightFn(s, fnCall, fnSrc) {
  s = edit(s, LOOP_FROM, `    weights = ${fnCall}(context)  # ONLY trading change vs baseline.py
    target_values = {}
    for etf, weight in weights.items():`);
  s = edit(s, ANCHOR_FN, fnSrc + '\n\n' + ANCHOR_FN);
  return s;
}

const RET_HELPER = `def _zcpz_returns(codes, n):
    """n daily returns per code ending previous_date (attribute_history at 09:40 never
    includes today's bar). Returns (DataFrame of returns, dict code->valid count)."""
    import pandas as pd
    cols = {}
    for s in codes:
        h = attribute_history(s, n + 1, '1d', ['close'], skip_paused=False, df=True, fq='pre')
        cols[s] = h['close'].astype(float)
    px = pd.DataFrame(cols)
    rets = px.pct_change().iloc[1:]
    valid = dict((s, int(rets[s].notna().sum())) for s in codes)
    return rets, valid
`;

// ---------- imp-2: ERC (SLSQP) ported from 4730554e get_risk_parity_weights ----------
const IMP2_FN = RET_HELPER + `

COV_DAYS = 120

def erc_weights(context):
    import numpy as np
    import pandas as pd
    from scipy.optimize import minimize
    codes = list(g.etf_weights.keys())
    eq = dict((s, 1.0 / len(codes)) for s in codes)
    mode = 'erc'
    try:
        rets, valid = _zcpz_returns(codes, COV_DAYS)
        if min(valid.values()) < COV_DAYS:
            mode = 'equal-short-history'
            w = eq
        else:
            cov_matrix = rets[codes].cov().values

            def risk_parity(weights):
                sigma = np.sqrt(np.dot(np.dot(weights, cov_matrix), weights))
                if sigma <= 0:
                    return 1e9
                mrc = np.dot(cov_matrix, weights) / sigma
                trc = weights * mrc
                return 10000 * np.sum((trc - np.mean(trc)) ** 2)

            weights0 = np.ones(len(codes)) / len(codes)
            cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
            bounds = tuple((0, 1.0) for _ in weights0)
            res = minimize(risk_parity, weights0, method='SLSQP',
                           constraints=cons, bounds=bounds, options={'maxiter': 100})
            if not res.success:
                mode = 'invvol-fallback'
                vol = rets[codes].std()
                inv_vol = 1.0 / vol.replace(0, np.nan)
                inv_vol = inv_vol.replace([np.inf, -np.inf], np.nan).dropna()
                ws = inv_vol / inv_vol.sum()
            else:
                ws = pd.Series(res.x, index=codes)
                ws = ws / ws.sum()
            w = dict((s, float(ws.get(s, 0.0))) for s in codes)
    except Exception as e:
        log.error('WEIGHTS ERROR %s exc=%s' % (context.current_dt.date(), str(e)))
        mode = 'equal-error'
        w = eq
        valid = {}
    log.error('WEIGHTS %s mode=%s %s minhist=%s' % (context.current_dt.date(), mode,
              ' '.join('%s=%.4f' % (s, w[s]) for s in codes), min(valid.values()) if valid else 'na'))
    return w`;
const imp2 = withWeightFn(base, 'erc_weights', IMP2_FN);
write('enhance/candidates/zcpz-imp-2.py', '# zcpz-imp-2: study/资产配置/baseline.py with ERC (SLSQP, port of 4730554e get_risk_parity_weights), COV_DAYS=120\n# family: 资产配置\n# expId: zcpz-imp-2', imp2);

// ---------- imp-1: inverse-vol, 60-day sigma ----------
const IMP1_FN = RET_HELPER + `

VOL_DAYS = 60

def invvol_weights(context):
    codes = list(g.etf_weights.keys())
    eq = dict((s, 1.0 / len(codes)) for s in codes)
    mode = 'invvol'
    valid = {}
    try:
        rets, valid = _zcpz_returns(codes, VOL_DAYS)
        if min(valid.values()) < VOL_DAYS:
            mode = 'equal-short-history'
            w = eq
        else:
            sig = dict((s, float(rets[s].std())) for s in codes)
            if min(sig.values()) <= 0:
                mode = 'equal-zero-vol'
                w = eq
            else:
                inv = dict((s, 1.0 / sig[s]) for s in codes)
                # explicit loop: on JQ the builtin-looking sum(inv.values()) raised
                # "float / dict_values" (name shadowed by the star import), first run fell back
                tot = 0.0
                for s in codes:
                    tot += inv[s]
                w = dict((s, inv[s] / tot) for s in codes)
    except Exception as e:
        log.error('WEIGHTS ERROR %s exc=%s' % (context.current_dt.date(), str(e)))
        mode = 'equal-error'
        w = eq
    log.error('WEIGHTS %s mode=%s %s minhist=%s' % (context.current_dt.date(), mode,
              ' '.join('%s=%.4f' % (s, w[s]) for s in codes), min(valid.values()) if valid else 'na'))
    return w`;
const imp1 = withWeightFn(base, 'invvol_weights', IMP1_FN);
write('enhance/candidates/zcpz-imp-1.py', '# zcpz-imp-1: study/资产配置/baseline.py with inverse-vol weights (60-day sigma through previous_date)\n# family: 资产配置\n# expId: zcpz-imp-1', imp1);

// ---------- imp-4: base pool + 511010 at 1/6 each ----------
let imp4 = edit(base, W, `    # imp-4: ONLY change vs baseline.py — add 511010 五年国债ETF, 6 names at 1/6 each
    g.etf_weights = {
        '515450.XSHG': 1.0 / 6,   # 红利低波ETF
        '513630.XSHG': 1.0 / 6,   # 香港红利低波ETF
        '513100.XSHG': 1.0 / 6,   # 纳指ETF
        '518880.XSHG': 1.0 / 6,   # 黄金ETF
        '513650.XSHG': 1.0 / 6,   # 标普ETF
        '511010.XSHG': 1.0 / 6,   # 五年国债ETF
    }`);
imp4 = edit(imp4, `        '513650.XSHG': '标普ETF',
    }`, `        '513650.XSHG': '标普ETF',
        '511010.XSHG': '国债ETF',
    }`);
write('enhance/candidates/zcpz-imp-4.py', '# zcpz-imp-4: study/资产配置/baseline.py + 511010.XSHG, 6 names at 1/6\n# family: 资产配置\n# expId: zcpz-imp-4', imp4);

// ---------- u-4: textbook pool, 20% each, with listing check ----------
let u4 = edit(base, W, `    # u-4: ONLY trading change vs baseline.py — textbook 5-class pool, 20% each
    g.etf_weights = {
        '518880.XSHG': 0.2,   # 黄金ETF
        '513100.XSHG': 0.2,   # 纳指ETF
        '510300.XSHG': 0.2,   # 沪深300ETF
        '511260.XSHG': 0.2,   # 十年国债ETF
        '159985.XSHE': 0.2,   # 豆粕ETF
    }`);
u4 = edit(u4, N, `    g.etf_names = {
        '518880.XSHG': '黄金ETF',
        '513100.XSHG': '纳指ETF',
        '510300.XSHG': '沪深300ETF',
        '511260.XSHG': '十年国债ETF',
        '159985.XSHE': '豆粕ETF',
    }
` + LISTCHECK);
u4 = edit(u4, LISTGUARD_FROM, LISTGUARD_TO);
write('study/资产配置/variants/u-4-textbook-pool.py', '# u-4 variant of study/资产配置/baseline.py', u4);

console.log('built ' + out.length + ':\n  ' + out.join('\n  '));
