// q-e9-orphan-fix: base = study/价值红利多腿/variants/q-e9-s4-pit.py (current reference; already
// py2to3 + OVERRIDE). ONE asserted change: a reconcile_sub_holdings(context) helper inserted right
// after daily_init, and ONE call line at the end of daily_init (9:00 daily, before any sleeve trades).
// The helper re-syncs the virtual sub-ledger g.sub_holdings with the real position after a 送转
// (which the sub-ledger never sees): one holder -> set to real; >=2 holders -> pro rata (int floor,
// remainder to the largest holder). Logs ORPHANSYNC for every adjustment and ORPHANREAL for a real
// position no sleeve holds (reported, not acted on). Nothing touches g.sub_cash.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const BASE_REL = 'study/价值红利多腿/variants/q-e9-s4-pit.py';
const baseFull = fs.readFileSync(path.join(ROOT, BASE_REL), 'utf8');

// Drop the base's 4-line build header; the body below it is what the diff is asserted against.
const HDR_LINES = 4;
const lines = baseFull.split('\n');
if (!lines[0].startsWith('# q-e9-s4-pit') || !lines[3].startsWith('# built:')) throw new Error('unexpected base header');
const raw = lines.slice(HDR_LINES).join('\n');

function once(hay, needle) {
  const n = hay.split(needle).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(needle)}`);
}

// The end of daily_init (the closing of its log.info) followed by the blank lines and get_sub_value.
const A =
  '            ", ".join(["%s=%.2f" % (sid, g.sub_cash[sid]) for sid in g.sub_cash])\n' +
  '        ))\n' +
  '\n' +
  '\n' +
  'def get_sub_value(context, sid):\n';
once(raw, A);
const CALL = '    reconcile_sub_holdings(context)\n';
const HELPER =
  'def reconcile_sub_holdings(context):\n' +
  '    """q-e9-orphan-fix: re-sync the virtual sub-ledger with the real position (送转 shares)"""\n' +
  '    _d = context.current_dt.date()\n' +
  '    for _code, _pos in list(context.portfolio.positions.items()):\n' +
  '        _real = int(_pos.total_amount)\n' +
  '        _holders = [(_sid, g.sub_holdings[_sid].get(_code, 0)) for _sid in g.sub_holdings\n' +
  '                    if g.sub_holdings[_sid].get(_code, 0) > 0]\n' +
  '        _virt = sum([_a for _s, _a in _holders])\n' +
  '        if _virt <= 0:\n' +
  '            if _real > 0:\n' +
  '                log.info("ORPHANREAL %s %s %d" % (_d, _code, _real))\n' +
  '            continue\n' +
  '        if _real == _virt:\n' +
  '            continue\n' +
  '        if len(_holders) == 1:\n' +
  '            _new = {_holders[0][0]: _real}\n' +
  '        else:\n' +
  '            _new = {}\n' +
  '            for _s, _a in _holders:\n' +
  '                _new[_s] = int(_a * _real // _virt)\n' +
  '            _big = max(_holders, key=lambda x: x[1])[0]\n' +
  '            _new[_big] += _real - sum(_new.values())\n' +
  '        for _s, _a in _holders:\n' +
  '            log.info("ORPHANSYNC %s %s %s %d %d" % (_d, _s, _code, _a, _new[_s]))\n' +
  '            if _new[_s] > 0:\n' +
  '                g.sub_holdings[_s][_code] = _new[_s]\n' +
  '            else:\n' +
  '                g.sub_holdings[_s].pop(_code, None)\n' +
  '\n' +
  '\n';
const A2 =
  '            ", ".join(["%s=%.2f" % (sid, g.sub_cash[sid]) for sid in g.sub_cash])\n' +
  '        ))\n' +
  CALL +
  '\n' +
  '\n' +
  HELPER +
  'def get_sub_value(context, sid):\n';

const body = raw.replace(A, A2);
if (body.length !== raw.length + CALL.length + HELPER.length) throw new Error('edit size mismatch');
// The diff is exactly the call line + the helper.
if (body.replace(CALL + '\n\n' + HELPER, '\n\n') !== raw) throw new Error('diff is not exactly the helper + one call line');
once(body, 'reconcile_sub_holdings(context)\n');           // one call ...
once(body, 'def reconcile_sub_holdings(context):\n');      // ... one definition
if (/_sub_cash|g\.sub_cash/.test(HELPER)) throw new Error('helper must not touch sub_cash');
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!body.includes(pin)) throw new Error(`missing pin: ${pin}`);
}
const header =
  `# q-e9-orphan-fix — family: 价值红利多腿\n` +
  `# source: ${BASE_REL} (itself strategies/2026-10-27_红利类型选股策略-cf1ec5bd.py + s4 pit bound + OVERRIDE)\n` +
  `# construction: base + ONE asserted edit: reconcile_sub_holdings(context) helper + one call at end of daily_init (ORPHANSYNC/ORPHANREAL logs)\n` +
  `# built: ${new Date().toISOString().slice(0, 10)} by study/价值红利多腿/build-orphan-fix.js\n`;
const out = path.join(__dirname, 'variants', 'q-e9-orphan-fix.py');
fs.writeFileSync(out, header + body);
console.log('built', path.relative(ROOT, out), 'bytes', (header + body).length);
