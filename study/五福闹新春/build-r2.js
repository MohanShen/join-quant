// Round 2 (2026-10-11) candidates for 五福闹新春, prompted by new member 1cc495be.
// Same discipline as build-e6.js: py2to3(v5.2 source) + asserted edits + the live OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-07-08_五福闹新春_v5_2-已解密_别再被13_10狙击了_快跑-17b3b439.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

// The cooldown, lifted verbatim from strategies/…-1cc495be.py (lines 2191-2219).
const COOLDOWN_FNS = `

# ==================== 卖出冷却（移植自 1cc495be，逐字） ====================
def mark_sell_cooldown(security, context):
    """记录卖出日，用于冷却期内禁止再买。"""
    if not hasattr(g, 'last_sell_dates') or g.last_sell_dates is None:
        g.last_sell_dates = {}
    sell_day = context.current_dt.date()
    g.last_sell_dates[security] = sell_day


def trading_days_since_sell(security, context):
    """自最近卖出日至今日（含）经过的交易日数；0=卖出当日。"""
    sell_date = getattr(g, 'last_sell_dates', {}).get(security)
    if sell_date is None:
        return None
    today = context.current_dt.date()
    if today < sell_date:
        return None
    trade_days = get_trade_days(start_date=sell_date, end_date=today)
    return len(trade_days) - 1


def is_in_sell_cooldown(security, context):
    """卖出当日不买回；卖出后再过 sell_cooldown_days 个交易日方可再买。"""
    days_since = trading_days_since_sell(security, context)
    if days_since is None:
        return False
    if days_since == 0:
        return True
    return days_since <= g.sell_cooldown_days
`;

const CANDIDATES = {
  // idea-imp-5: 3 holdings in the normal period (rank is uninformative, q-e6-1)
  'wufu-imp-5': s => edit(s, '    g.holdings_num = 1\n', '    g.holdings_num = 3  # imp-5\n'),

  // idea-imp-4: port 1cc495be's sell cooldown onto the family base
  'wufu-imp-4': s => {
    let out = edit(s, '    g.holdings_num = 1\n',
      '    g.holdings_num = 1\n    g.sell_cooldown_days = 2  # imp-4\n    g.last_sell_dates = {}  # imp-4\n');
    // block a buy while the name is in cooldown
    out = edit(out,
      '    diff = target_amount - cur_amount\n',
      '    diff = target_amount - cur_amount\n' +
      '    if diff > 0 and is_in_sell_cooldown(security, context):  # imp-4\n' +
      '        log.info(f"{security} {name} 处于卖出冷却期，跳过买入")\n' +
      '        return False\n');
    // mark the cooldown on a successful sell
    out = edit(out,
      '                log.info(f"📤 卖出 {security} {name} 数量{abs(diff)} 价格{price:.3f}")\n',
      '                log.info(f"📤 卖出 {security} {name} 数量{abs(diff)} 价格{price:.3f}")\n' +
      '                mark_sell_cooldown(security, context)  # imp-4\n');
    return out + COOLDOWN_FNS;
  },
};

fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
for (const [id, fn] of Object.entries(CANDIDATES)) {
  fs.writeFileSync(path.join(ROOT, 'enhance/candidates', `${id}.py`), fn(src) + OVERRIDE);
}
console.log('built', Object.keys(CANDIDATES).join(', '));
