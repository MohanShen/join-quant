// u-e9-dyla: lookahead probe of calc_dividend_yield. Base 2a323522 + py2to3 + OVERRIDE (== baseline.py)
// plus OBSERVATION ONLY: inside calc_dividend_yield, a SECOND run_query on the identical filter
// (code == stock, a_bonus_date >= current_dt-365, no upper bound) selecting the date columns,
// logging one DYLA line per row with future=1 if any date field > current_dt.date().
// The book's own query, its df and its return value are untouched; the probe is wrapped in
// try/except that log.error's the exception (a bad column name must be loud, never swallowed).
// Control: must reproduce the base exactly (0.3371 / 2.37 / 45.54 / 11.83).
// DECISION RULE (queue.json): CONFIRM lookahead if any rebalance row has a_bonus_date or a
// publication date after current_dt contributing to dy; REFUTE if 0 such rows over 2024.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-26_自己搭建的一个10年230_收益率的银行股策略-2a323522.py';
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

const A = "    df = finance.run_query(q)\n    if df.empty:\n        return 0.0\n    total_div = df['bonus_ratio_rmb'].sum() / 10.0\n";
const PROBE = [
  "    try:  # u-e9-dyla: observation only",
  "        _d0 = context.current_dt.date()",
  "        _cols = ['a_bonus_date', 'board_plan_pub_date', 'shareholders_plan_pub_date',",
  "                 'implementation_pub_date', 'a_registration_date', 'a_xr_date', 'report_date']",
  "        _q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.bonus_ratio_rmb,",
  "                   finance.STK_XR_XD.a_bonus_date, finance.STK_XR_XD.board_plan_pub_date,",
  "                   finance.STK_XR_XD.shareholders_plan_pub_date, finance.STK_XR_XD.implementation_pub_date,",
  "                   finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.a_xr_date,",
  "                   finance.STK_XR_XD.report_date, finance.STK_XR_XD.plan_progress",
  "        ).filter(finance.STK_XR_XD.code == stock, finance.STK_XR_XD.a_bonus_date >= start_date)",
  "        _df = finance.run_query(_q)",
  "        log.error('DYLN date=%s code=%s n_book=%d n_probe=%d' % (str(_d0), stock, len(df), len(_df)))",
  "        for _i in range(len(_df)):",
  "            _r = _df.iloc[_i]",
  "            _fut = []",
  "            _vals = []",
  "            for _c in _cols:",
  "                _v = _r[_c]",
  "                _s = str(_v)[:10]",
  "                _vals.append('%s=%s' % (_c, _s))",
  "                if _s[:4].isdigit() and _s > str(_d0):",
  "                    _fut.append(_c)",
  "            log.error('DYLA date=%s code=%s bonus=%s %s progress=%s future=%d fut_fields=%s' % (str(_d0), stock, _r['bonus_ratio_rmb'], ' '.join(_vals), _r['plan_progress'], 1 if _fut else 0, ','.join(_fut) if _fut else '-'))",
  "    except Exception as _e:",
  "        log.error('DYLA-ERR date=%s code=%s err=%r' % (str(context.current_dt.date()), stock, _e))",
  "",
].join('\n');
let body = edit(raw, A, "    df = finance.run_query(q)\n" + PROBE + "    if df.empty:\n        return 0.0\n    total_div = df['bonus_ratio_rmb'].sum() / 10.0\n");

for (const k of ['order_target', 'order_value', 'order(']) {
  if ((body.split(k).length) !== (raw.split(k).length)) throw new Error('order calls changed: ' + k);
}
if (!body.includes("run_weekly(rebalance, weekday=5, time='close')")) throw new Error('schedule changed');
// the only removed text is none: every raw line must still be present in order
if (body.replace(PROBE, '') !== raw) throw new Error('edit is not purely additive');

const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, 'dyla.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
