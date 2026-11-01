// q-e9-s1-only: base = study/价值红利多腿/variants/q-e9-s4-pit.py (the honest-s4 reference, already
// py2to3 + OVERRIDE), with ONE asserted edit: g.strategy_weights -> s1=0.25, s2=0, s3=0, s4=0,
// plus two LOG-ONLY blocks (folded-in U3):
//   S1CNT  date n_noroa n_roa015 n_roa15   — s1's filters (no limit) without roa / roa>0.15 / roa>15
//   S1TOP3 date code:mcap:pct,...           — the 3 retained_profit-top names; pct = mcap rank in 全A / N
//   S1PICK date code mcap pct               — the chosen name
//   S3CNT  date n_noroa n_roa015 n_roa15 pick — the same count on s3's query (s3 still selects at weight 0)
// The blocks issue read-only get_fundamentals queries inside try/except and log; the build asserts they
// contain no order / sub_buy / sub_sell / g.* assignment, and that removing them restores the
// weights-only body exactly. Same method as build-pb-only.js / build-div-only.js.
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const REL = 'study/价值红利多腿/variants/q-e9-s4-pit.py';
let raw = fs.readFileSync(path.join(ROOT, REL), 'utf8');
if (!raw.startsWith('# q-e9-s4-pit')) throw new Error('unexpected reference header');
const hdrEnd = raw.indexOf('\n', raw.indexOf('# built:')) + 1;
raw = raw.slice(hdrEnd);
if (!raw.includes(OVERRIDE)) throw new Error('reference does not carry the live OVERRIDE');
const A = "    g.strategy_weights = {\n        's1': 0.25,\n        's2': 0.25,\n        's3': 0.25,\n        's4': 0.25,\n    }\n";
const A2 = "    g.strategy_weights = {\n        's1': 0.25,\n        's2': 0.0,\n        's3': 0.0,\n        's4': 0.0,\n    }\n";
const n = raw.split(A).length - 1;
if (n !== 1) throw new Error('expected exactly 1 weights block, got ' + n);
const weighted = raw.replace(A, A2);
if (weighted.replace(A2, A) !== raw) throw new Error('diff is not exactly the weights edit');

const HELPER = `
def _qe9_mcap_pct(codes):
    # [q-e9-s1-only LOG-ONLY] market-cap rank in 全A (1 = largest) / N, for each code
    _all = get_fundamentals(query(valuation.code, valuation.market_cap).limit(10000))
    _all = _all.dropna(subset=['market_cap'])
    _n = len(_all)
    _out = {}
    for _c in codes:
        _r = _all[_all['code'] == _c]
        if len(_r) == 0:
            _out[_c] = (float('nan'), float('nan'))
            continue
        _mc = float(_r['market_cap'].iloc[0])
        _rank = int((_all['market_cap'] > _mc).sum()) + 1
        _out[_c] = (_mc, _rank / float(_n))
    return _out, _n

`;
const ANCHOR_S1 = `    log.info("[s1] 目标股票: %s" % final_list)\n`;
const BLOCK_S1 = `    # [q-e9-s1-only LOG-ONLY] no state change, no orders
    try:
        _d = context.current_dt.date()
        _base = [
            valuation.code.in_(initial_list),
            valuation.market_cap > 100,
            valuation.pe_ratio.between(0, 50),
            (balance.total_liability / balance.total_sheet_owner_equities) < 0.5,
            indicator.inc_total_revenue_year_on_year > 0.3,
            indicator.inc_revenue_year_on_year > 0.2,
            balance.retained_profit > 0,
        ]
        _n0 = len(get_fundamentals(query(valuation.code).filter(*_base).limit(10000)))
        _n1 = len(get_fundamentals(query(valuation.code).filter(*(_base + [indicator.roa > 0.15])).limit(10000)))
        _n2 = len(get_fundamentals(query(valuation.code).filter(*(_base + [indicator.roa > 15])).limit(10000)))
        log.info("S1CNT %s n_noroa=%d n_roa015=%d n_roa15=%d" % (_d, _n0, _n1, _n2))
        _pc, _nn = _qe9_mcap_pct(list(code_list) + list(final_list))
        log.info("S1TOP3 %s N=%d %s" % (_d, _nn, ",".join(["%s:%.1f:%.4f" % (c, _pc[c][0], _pc[c][1]) for c in code_list])))
        for _c in final_list:
            log.info("S1PICK %s %s mcap=%.1f pct=%.4f" % (_d, _c, _pc[_c][0], _pc[_c][1]))
    except Exception as _e:
        log.info("S1CNT %s probe-failed %s" % (context.current_dt.date(), str(_e)))
`;
const ANCHOR_S3 = `    log.info("[s3] 选股池: %s" % g.s3_check_out_lists)\n`;
const BLOCK_S3 = `    # [q-e9-s1-only LOG-ONLY] no state change, no orders
    try:
        _d = context.current_dt.date()
        _base = [
            valuation.pb_ratio < 1,
            cash_flow.net_operate_cash_flow > 0.8 * income.net_profit,
            cash_flow.subtotal_operate_cash_inflow > 1e6,
            indicator.adjusted_profit > 1e6,
            indicator.inc_net_profit_year_on_year > 5,
            valuation.code.in_(all_stocks),
        ]
        _n0 = len(get_fundamentals(query(valuation.code).filter(*_base).limit(10000)))
        _n1 = len(get_fundamentals(query(valuation.code).filter(*(_base + [indicator.roa > 0.15])).limit(10000)))
        _n2 = len(get_fundamentals(query(valuation.code).filter(*(_base + [indicator.roa > 15])).limit(10000)))
        log.info("S3CNT %s n_noroa=%d n_roa015=%d n_roa15=%d pick=%s" % (_d, _n0, _n1, _n2, check_out[:g.s3_stock_num]))
    except Exception as _e:
        log.info("S3CNT %s probe-failed %s" % (context.current_dt.date(), str(_e)))
`;
const ANCHOR_FN = `def strategy_1_adjust(context):\n`;
for (const [a, nm] of [[ANCHOR_S1, 's1'], [ANCHOR_S3, 's3'], [ANCHOR_FN, 'fn']]) {
  const k = weighted.split(a).length - 1;
  if (k !== 1) throw new Error(`anchor ${nm} found ${k} times`);
}
// log-only guarantee: the inserted text may not order, trade or assign globals
for (const b of [HELPER, BLOCK_S1, BLOCK_S3]) {
  if (/order\(|order_value|order_target|sub_buy|sub_sell|\bg\.\w+(\[[^\]]*\])?\s*=[^=]|\bg\.\w+\.(append|pop|remove|update|clear)\(/.test(b)) {
    throw new Error('instrumentation block contains a trading/state call');
  }
}
let body = weighted
  .replace(ANCHOR_FN, HELPER.slice(1) + ANCHOR_FN)
  .replace(ANCHOR_S1, ANCHOR_S1 + BLOCK_S1)
  .replace(ANCHOR_S3, ANCHOR_S3 + BLOCK_S3);
const restored = body.replace(HELPER.slice(1), '').replace(BLOCK_S1, '').replace(BLOCK_S3, '');
if (restored !== weighted) throw new Error('removing the log blocks does not restore the weights-only body');
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!body.includes(pin)) throw new Error('missing pin ' + pin);
}
const header =
  `# q-e9-s1-only — family: 价值红利多腿\n` +
  `# source: ${REL} (honest-s4 reference; itself py2to3(cf1ec5bd) + s4 PIT bound + OVERRIDE)\n` +
  `# construction: reference + ONE asserted edit: g.strategy_weights s1=0.25 s2=0 s3=0 s4=0 + LOG-ONLY S1CNT/S1TOP3/S1PICK/S3CNT\n` +
  `# built: ${new Date().toISOString().slice(0, 10)} by study/价值红利多腿/build-s1-only.js\n`;
const out = path.join(__dirname, 'variants', 'q-e9-s1-only.py');
fs.writeFileSync(out, header + body);
console.log('built', path.relative(ROOT, out), 'bytes', (header + body).length);
