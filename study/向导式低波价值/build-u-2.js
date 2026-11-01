// Builds study/向导式低波价值/variants/u-2-probe.py — u-2 (logging only).
// Base = study/向导式低波价值/baseline.py (py2to3 + OVERRIDE, no edit). Every edit below INSERTS
// log lines; no assignment, filter, order or parameter is changed. Each anchor must match exactly once.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
let src = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');

function insertAfter(anchor, text) {
  const n = src.split(anchor).length - 1;
  if (n !== 1) throw new Error(`anchor matched ${n}x: ${anchor}`);
  src = src.replace(anchor, anchor + text);
}

// 1. final-day close handler (logging only)
insertAfter("    run_daily(selled_security_list_count, 'after_close') #卖出股票日期计数 \n",
  "    run_daily(_probe_final, 'after_close')  # PROBE u-2: logging only\n");

// 2. check_stocks stage counts / lists
const stages = [
  ['g.check_out_lists = get_security_universe(context, g.security_universe_index, g.security_universe_user_securities)\n', 'universe'],
  ['g.check_out_lists = industry_filter(context, g.check_out_lists, g.industry_list)\n', 'industry'],
  ['g.check_out_lists = concept_filter(context, g.check_out_lists, g.concept_list)\n', 'concept'],
  ['    g.check_out_lists = st_filter(context, g.check_out_lists)\n', 'st'],
  ['    g.check_out_lists = delisted_filter(context, g.check_out_lists)\n', 'delisted'],
  ['g.check_out_lists = financial_statements_filter(context, g.check_out_lists)\n', 'pe'],
  ['g.check_out_lists = situation_filter(context, g.check_out_lists)\n', 'situation'],
  ['g.check_out_lists = technical_indicators_filter(context, g.check_out_lists)\n', 'technical'],
  ['g.check_out_lists = pattern_recognition_filter(context, g.check_out_lists)\n', 'pattern'],
  ['g.check_out_lists = other_func_filter(context, g.check_out_lists)\n', 'other'],
  ['g.check_out_lists = check_stocks_sort(context,g.check_out_lists,input_dict,g.check_out_lists_ascending)\n', 'sort'],
];
for (const [a, s] of stages) insertAfter(a, `    _probe_stage(context, '${s}', g.check_out_lists)  # PROBE\n`);

// 3. trade(): buy-side stages + ATR unit rows before the ATR filter, ORDER after it
const tstages = [
  ['        buy_lists = g.check_out_lists\n', 'b_in'],
  ['        buy_lists = st_filter(context, buy_lists)\n', 'b_st'],
  ['        buy_lists = paused_filter(context, buy_lists)\n', 'b_paused'],
  ['        buy_lists = delisted_filter(context, buy_lists)\n', 'b_delisted'],
];
for (const [a, s] of tstages) insertAfter(a, `        _probe_stage(context, '${s}', buy_lists)  # PROBE\n`);
insertAfter('        buy_lists = high_limit_filter(context, buy_lists)\n',
  "        _probe_stage(context, 'b_highlimit', buy_lists)  # PROBE\n" +
  "        _probe_atr(context, buy_lists, 'ATRU')  # PROBE\n");
insertAfter('        buy_lists = [security for security in buy_lists if ATR_judge_xiaoyu(security, 0.15, 14)]\n',
  "        _probe_stage(context, 'b_atr', buy_lists)  # PROBE\n" +
  "        _probe_order(context, buy_lists)  # PROBE\n");

// 4. sell(): held-position ATR rows before the exit filter (dayu side of the unit test)
insertAfter('    ### _出场函数筛选-开始 ###\n',
  "    _probe_atr(context, list(context.portfolio.positions.keys()), 'ATRH')  # PROBE\n");

// 5. buy(): what is actually ordered
insertAfter('    buy_lists = buy_lists[:Num]\n',
  "    log.info('BUYN date=%s num=%d codes=%s' % (context.current_dt.strftime('%Y-%m-%d'), Num, ','.join(buy_lists)))  # PROBE\n");

const helpers = `

# ===== PROBE u-2 helpers (logging only; read-only data calls, no state used by the strategy) =====
_PROBE_FULL_DATES = ['2024-11-04']
_PROBE = {'first': None, 'open0': None}

def _probe_d(context):
    return context.current_dt.strftime('%Y-%m-%d')

def _probe_full(context):
    d = _probe_d(context)
    if _PROBE['first'] is None:
        _PROBE['first'] = d
    return d == _PROBE['first'] or d in _PROBE_FULL_DATES

def _probe_chunks(tag, d, lst):
    lst = list(lst)
    for i in range(0, len(lst), 40):
        log.info('%s date=%s part=%d codes=%s' % (tag, d, i // 40, ','.join(lst[i:i + 40])))

def _probe_pe(lst):
    try:
        if len(lst) == 0:
            return {}
        df = get_fundamentals(query(valuation.code, valuation.pe_ratio).filter(valuation.code.in_(list(lst))))
        return dict(zip(df['code'], df['pe_ratio']))
    except Exception as e:
        log.info('PROBEERR pe %s' % e)
        return {}

def _probe_stage(context, stage, lst):
    d = _probe_d(context)
    lst = list(lst)
    nsz = len([c for c in lst if c.endswith('.XSHE')])
    log.info('CNT date=%s stage=%s n=%d sz=%d' % (d, stage, len(lst), nsz))
    if _probe_full(context) or (stage not in ('universe', 'industry', 'concept', 'st', 'delisted') and len(lst) <= 120):
        _probe_chunks('LIST stage=%s' % stage, d, lst)
    if stage == 'delisted' and _probe_full(context):
        pe = _probe_pe(lst)
        items = ['%s:%s' % (c, ('%.2f' % pe[c]) if (c in pe and pe[c] is not None) else 'NA') for c in lst]
        _probe_chunks('PEU', d, items)

def _probe_atr(context, lst, tag):
    d = _probe_d(context)
    lst = list(lst)
    pe = _probe_pe(lst)
    for c in lst:
        try:
            h = attribute_history(c, 60, '1d', ['high', 'low', 'close'])
            hi = np.array(h['high'].values, dtype=float)
            lo = np.array(h['low'].values, dtype=float)
            cl = np.array(h['close'].values, dtype=float)
            a15 = talib.ATR(hi[-15:], lo[-15:], cl[-15:], 14)[-1]
            a60 = talib.ATR(hi, lo, cl, 14)[-1]
            close = cl[-1]
            x = ATR_judge_xiaoyu(c, 0.15, 14)
            y = ATR_judge_dayu(c, 0.35, 14)
            pv = pe.get(c)
            log.info('%s date=%s code=%s close=%.4f atr15=%.5f atr60=%.5f rel15=%.5f rel60=%.5f pe=%s xiaoyu=%s dayu=%s nb=%d' % (
                tag, d, c, close, a15, a60, a15 / close, a60 / close,
                ('%.3f' % pv) if pv is not None else 'NA', x, y, len(cl)))
        except Exception as e:
            log.info('PROBEERR atr %s %s %s' % (tag, c, e))

def _probe_order(context, lst):
    d = _probe_d(context)
    lst = list(lst)
    log.info('ORDER date=%s n=%d codes=%s' % (d, len(lst), ','.join(lst[:15])))
    if _PROBE['open0'] is None:
        _PROBE['open0'] = lst
        cd = get_current_data()
        for c in lst:
            try:
                log.info('OPEN0 date=%s code=%s open=%.4f' % (d, c, cd[c].day_open))
            except Exception as e:
                log.info('PROBEERR open0 %s %s' % (c, e))

def _probe_final(context):
    d = _probe_d(context)
    end = None
    try:
        end = context.run_params.end_date
        end = end.strftime('%Y-%m-%d') if hasattr(end, 'strftime') else str(end)[:10]
    except Exception:
        end = '2024-12-31'
    if d != end:
        return
    names = list(_PROBE['open0'] or []) + list(context.portfolio.positions.keys())
    seen = set()
    for c in names:
        if c in seen:
            continue
        seen.add(c)
        try:
            h = attribute_history(c, 1, '1d', ['close'])
            lp = get_current_data()[c].last_price
            log.info('CLOSEN date=%s code=%s ah_close=%.4f ah_date=%s last_price=%.4f held=%s' % (
                d, c, float(h['close'].values[-1]), str(h.index[-1])[:10], lp, c in context.portfolio.positions))
        except Exception as e:
            log.info('PROBEERR closen %s %s' % (c, e))
`;
src = src.replace(/^# study baseline[^\n]*\n/, '# study variant u-2 — family: 向导式低波价值 — LOGGING-ONLY probe of the ATR unit + per-stage survivors\n# built from study/向导式低波价值/baseline.py by study/向导式低波价值/build-u-2.js; every insertion is marked # PROBE\n');
src += helpers;
const out = path.join(__dirname, 'variants', 'u-2-probe.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, src);
const added = src.split('\n').filter(l => l.includes('# PROBE')).length;
console.log('built', path.relative(ROOT, out), 'probe-lines', added);
