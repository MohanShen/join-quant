// q-e9-liq — baseline.py + ONE inserted block after the _liquidity_filter step in _rank_and_build:
// a buy-side feasibility floor "20-day mean daily money >= F", data up to `date` (= context.previous_date,
// rebalance passes it), plus a per-rebalance log line `LIQFLOOR in=<n> out=<n>`. Nothing else changes.
// Floor = capital / SCHD_TOP_N / orderVolumeRatio, capital + ovr READ FROM THE HARNESS (expect 2e5);
// liq-1 = 1x, liq-3 = 10x (2e6). Missing data => nothing removed (status=bypass-nodata).
// Usage: node -e "require('./study/红利质量/build-q-e9-liq.js')"
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');
const ROOT = path.join(__dirname, '../..');
const base = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');
if (!base.endsWith(OVERRIDE)) throw new Error('baseline.py does not end with the current OVERRIDE');

const hc = harness.config();
const CAPITAL = hc.costs.capital, OVR = hc.costs.orderVolumeRatio, SLOTS = 100;
const F1 = CAPITAL / SLOTS / OVR;
if (F1 !== 2e5) throw new Error('feasibility floor expected 2e5, got ' + F1);
if (!/^SCHD_TOP_N = 100\s/m.test(base)) throw new Error('SCHD_TOP_N is not 100');

const ANCHOR = [
  '    stock_list = _liquidity_filter(stock_list, date)',
  '    log.info("【筛选】流动性筛选后: %d只（成交额%s）" % (len(stock_list), _pct_name(SCHD_LIQ_PCT)))',
  '    if not stock_list:',
  '        return {}',
  '',
].join('\n');

function build(tag, mult) {
  const floorExpr = `${CAPITAL}.0 / ${SLOTS} / ${OVR} * ${mult}`;
  const INS = [
    `    # ${tag}: feasibility floor = capital / TopN / order_volume_ratio x ${mult}; 20d mean money, end_date=date (previous_date)`,
    `    _liq_floor = ${floorExpr}`,
    '    _liq_in = len(stock_list)',
    '    try:',
    "        _liq_df = get_price(stock_list, end_date=date, count=20, frequency='daily',",
    "                            fields=['money'], panel=False)",
    "        _liq_m = _liq_df.groupby('code')['money'].mean().to_dict() if _liq_df is not None and not _liq_df.empty else None",
    '    except Exception:',
    '        _liq_m = None',
    '    if _liq_m:',
    '        _liq_rm = [s for s in stock_list if not (float(_liq_m.get(s, 0.0) or 0.0) >= _liq_floor)]',
    '        stock_list = [s for s in stock_list if float(_liq_m.get(s, 0.0) or 0.0) >= _liq_floor]',
    '        log.info("LIQFLOOR date=%s floor=%.0f in=%d out=%d removed=%s status=ok" % (',
    "            date, _liq_floor, _liq_in, len(stock_list), ';'.join(_liq_rm[:40]) or '-'))",
    '    else:',
    '        log.info("LIQFLOOR date=%s floor=%.0f in=%d out=%d removed=- status=bypass-nodata" % (',
    '            date, _liq_floor, _liq_in, _liq_in))',
    '    if not stock_list:',
    '        return {}',
    '',
  ].join('\n');
  const n = base.split(ANCHOR).length - 1;
  if (n !== 1) throw new Error('anchor match count ' + n);
  const body = base.replace(ANCHOR, ANCHOR + INS);
  if (body.replace(INS, '') !== base) throw new Error('removing the insertion does not restore baseline');
  if (/order\w*\(|\bg\.\w+\s*=/.test(INS)) throw new Error('insertion orders or assigns g.*');
  const hdr = `# ${tag} — 红利质量 understand: baseline.py + feasibility floor 20d mean money >= ${(F1 * mult).toExponential(0)} ` +
    `(capital ${CAPITAL} / TopN ${SLOTS} / ovr ${OVR} x ${mult}) after _liquidity_filter; LIQFLOOR log. Built by study/红利质量/build-q-e9-liq.js\n`;
  const dst = path.join(__dirname, 'variants', tag + '.py');
  fs.writeFileSync(dst, hdr + body);
  console.log('built', path.relative(ROOT, dst), 'floor', F1 * mult);
}
build('q-e9-liq-1', 1);
build('q-e9-liq-3', 10);
