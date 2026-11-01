// q-e9-s4-pit: base = strategies/2026-10-27_红利类型选股策略-cf1ec5bd.py, built exactly as the
// normalizer builds it (py2to3(src) + OVERRIDE), with ONE asserted trading edit in
// _s4_choice_stocks' finance.run_query filter: add the point-in-time upper bound
//   finance.STK_XR_XD.board_plan_pub_date <= context.previous_date,
// plus ONE log-only side query (S4PIT line) counting, for the same code set and bonus>0, rows with a
// NULL board_plan_pub_date and rows the new bound excludes (pub_date > previous_date). The side query
// is wrapped in try/except and touches no variable the trading path reads.
// Note: SQL `NULL > x` is not true, so nulls were already excluded by the base's own `> dt_3y`
// filter — the null count is reported, not acted on.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const REL = 'strategies/2026-10-27_红利类型选股策略-cf1ec5bd.py';
const raw = py2to3(fs.readFileSync(path.join(ROOT, REL), 'utf8'));

function once(hay, needle) {
  const n = hay.split(needle).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(needle)}`);
}

// Edit 1 (trading): the upper bound.
const A = '            finance.STK_XR_XD.board_plan_pub_date > dt_3y,\n';
const A2 = A + '            finance.STK_XR_XD.board_plan_pub_date <= context.previous_date,\n';
once(raw, A);

// Edit 2 (log-only): inserted right after `dt_3y = ...`, before the trading query.
const B = '    dt_3y = context.current_dt.date() - datetime.timedelta(days=365)\n';
const B2 = B +
  '    try:\n' +
  '        _pit = finance.run_query(query(\n' +
  '            finance.STK_XR_XD.code,\n' +
  '            finance.STK_XR_XD.board_plan_pub_date,\n' +
  '        ).filter(\n' +
  '            finance.STK_XR_XD.code.in_(stocks),\n' +
  '            finance.STK_XR_XD.bonus_amount_rmb > 0\n' +
  '        ))\n' +
  '        _pd = pd.to_datetime(_pit.board_plan_pub_date)\n' +
  '        _nnull = int(_pd.isnull().sum())\n' +
  '        _nfut = int((_pd > pd.Timestamp(context.previous_date)).sum())\n' +
  '        _futc = sorted(set(_pit.code[_pd > pd.Timestamp(context.previous_date)]))\n' +
  '        log.info("S4PIT %s null_pub=%d future_pub=%d future_codes=%s" % (context.current_dt.date(), _nnull, _nfut, _futc))\n' +
  '    except Exception as _e:\n' +
  '        log.info("S4PIT %s probe-failed %s" % (context.current_dt.date(), str(_e)))\n';
once(raw, B);

const body = raw.replace(A, A2).replace(B, B2);
if (body.length !== raw.length + (A2.length - A.length) + (B2.length - B.length)) throw new Error('edit size mismatch');
// The only non-log change is the one bound line.
const strip = s => s.replace(B2, B);
if (strip(body).replace(A2, A) !== raw) throw new Error('diff is not exactly the two declared insertions');
// The side query's variables never reach the trading path.
for (const v of ['_pit', '_pd', '_nnull', '_nfut', '_futc']) {
  const uses = body.split(v).length - 1;
  if (uses < 1) throw new Error('missing ' + v);
}
const full = body + OVERRIDE;
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!full.includes(pin)) throw new Error(`missing pin: ${pin}`);
}
const header =
  `# q-e9-s4-pit — family: 价值红利多腿\n` +
  `# source: ${REL}\n` +
  `# construction: py2to3(source) + ONE asserted edit (board_plan_pub_date <= context.previous_date in s4) + log-only S4PIT probe + utils/strategy-normalize OVERRIDE\n` +
  `# built: ${new Date().toISOString().slice(0, 10)} by study/价值红利多腿/build-s4-pit.js\n`;
const out = path.join(__dirname, 'variants', 'q-e9-s4-pit.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, header + full);
console.log('built', path.relative(ROOT, out), 'bytes', (header + full).length);
