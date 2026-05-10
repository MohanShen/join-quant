/**
 * strategy-summarize.js
 *
 * Parse a JoinQuant strategy source file and produce:
 * 1. Structured summary (factors, params, risk rules)
 * 2. A FAITHFUL natural-language translation of the actual code logic
 */

const fs = require('fs');
const path = require('path');

// ── Helper: extract function block by line number ────────────────────────────

function getFunctionBlock(code, fnName) {
  const lines = code.split('\n');
  const startIdx = lines.findIndex(l => l.trim().startsWith(`def ${fnName}(`));
  if (startIdx < 0) return null;

  // Scan until next top-level ## comment or def
  let endIdx = lines.length;
  for (let i = startIdx + 1; i < lines.length; i++) {
    const l = lines[i].trim();
    if (l.startsWith('##') || (l.startsWith('def ') && !l.startsWith('def ' + fnName))) {
      endIdx = i;
      break;
    }
  }
  return lines.slice(startIdx, endIdx).join('\n');
}

// ── Helper: extract parameter values ──────────────────────────────────────

function extractGParam(code, name) {
  const m = code.match(new RegExp(`g\\.${name}\\s*=\\s*(\\d+)`));
  return m ? parseInt(m[1]) : null;
}

// ── Faithful description builder ────────────────────────────────────────────

function buildFaithfulDescription(code) {
  const lines = [];
  const g = {
    stocknum: extractGParam(code, 'stocknum'),
    shift: extractGParam(code, 'shift'),
    short_d: extractGParam(code, 'short_d'),
    long_d: extractGParam(code, 'long_d'),
  };

  // ── 1. Trading schedule ─────────────────────────────────────────────────
  const schedules = [...code.matchAll(/run_daily\([^,]+,\s*time\s*=\s*['"]([^'"]+)/g)]
    .map(m => m[1]);
  const unique = [...new Set(schedules)];

  lines.push('【交易时间】');
  if (unique.includes('09:00')) lines.push('  09:00 — 盘前选股：按市值排序构建候选列表');
  if (unique.includes('09:30')) lines.push('  09:30 — 开盘调仓 + 止损检查');
  if (unique.includes('15:30')) lines.push('  15:30 — 收盘记录日志');
  if (unique.length === 0) lines.push('  （未检测到定时任务）');

  // ── 2. Stock pool + selection ──────────────────────────────────────────
  const initBlock = getFunctionBlock(code, 'initialize');
  const poolMatches = [...code.matchAll(/get_index_stocks\(['"]([^'"]+)/g)];
  const poolMap = {
    '000001.XSHG': '上证综指',
    '399106.XSHE': '深证综指',
    '000300.XSHG': '沪深300',
    '000905.XSHG': '中证500',
    '399101.XSHE': '中小板',
    '000852.XSHE': '中证1000',
  };
  const pools = poolMatches.map(m => poolMap[m[1]] || m[1]).filter(Boolean);
  const poolDesc = pools.length > 0 ? pools.join(' + ') : '全市场';

  // Market cap sorting direction
  const ascDesc = /order_by\([^)]*\.asc\(\)/i.test(code) ? '升序（从小到大）' :
                  /order_by\([^)]*\.desc\(\)/i.test(code) ? '降序（从大到小）' : '升序';

  lines.push('');
  lines.push('【选股逻辑】');
  lines.push(`  股票池：${poolDesc}所有成分股`);
  if (g.shift) lines.push(`  排除条件：近${g.shift}个交易日有停牌的股票`);
  lines.push(`  排序方式：按总市值${ascDesc}，取最小的 ${g.stocknum || 'N'} 只`);
  lines.push(`  每日重新计算候选列表，换仓时全量调仓`);

  // ── 3. Position sizing ──────────────────────────────────────────────────
  lines.push('');
  lines.push('【仓位分配】');
  lines.push(`  等权重：账户总权益 ÷ 持有股票数，每只股票分配等额资金`);
  const rebalBlock = getFunctionBlock(code, 'rebalance');
  if (rebalBlock) {
    const isCommented = rebalBlock.includes('#jieti') || rebalBlock.includes('# 执行阶梯');
    if (isCommented) {
      lines.push(`  ⚠️ 阶梯调仓（jieti）已注释，实际不执行`);
    }
  }
  // Detect double order bug
  const doubleOrder = rebalBlock ? rebalBlock.match(/for i in holding_list[\s\S]{1,100}for i in holding_list/) : null;
  if (doubleOrder) lines.push(`  ⚠️ 代码冗余：rebalance 中有两遍相同的循环买入代码（疑似复制粘贴残留）`);

  // ── 4. Stop loss (zhisun) ─────────────────────────────────────────────────
  const zhisunBlock = getFunctionBlock(code, 'zhisun');
  if (zhisunBlock && zhisunBlock.trim().length > 50) {
    const shortD = g.short_d || 2;
    const longD = g.long_d || 20;
    lines.push('');
    lines.push('【止损逻辑】');
    lines.push(`  触发时间：每日 09:30（与调仓同周期）`);
    lines.push(`  指标：MA${shortD}（${shortD}日均线）与 MA${longD}（${longD}日均线）的死叉`);
    lines.push(`  判定：用前一日收盘价计算 MA${shortD} 与 MA${longD}`);
    lines.push(`  条件：当前 MA${shortD} < MA${longD} 且前一交易日 MA${shortD} >= MA${longD}`);
    lines.push(`  执行：市价卖出全部持仓（仅当可卖出数量 > 0 时）`);
  }

  // ── 5. Take profit / ladder rebalance (jieti) ───────────────────────────
  const jietiBlock = getFunctionBlock(code, 'jieti');
  const jietiCalled = code.match(/^\s*jieti\s*\(/m) ||
                       code.match(/market_open[\s\S]{1,200}?jieti\s*\(/m);

  if (jietiBlock && jietiBlock.trim().length > 60) {
    lines.push('');
    lines.push('【阶梯止盈/调仓】（jieti函数）');
    if (!jietiCalled) {
      lines.push(`  ⚠️ 此模块已注释未启用（jieti未在market_open中调用）`);
    } else {
      lines.push(`  启用中：`);
    }
    // Extract take-profit thresholds
    const tpMatches = [...jietiBlock.matchAll(/ret\s*>\s*(0\.\d+)/g)];
    if (tpMatches.length > 0) {
      const actions = ['卖出一半（-50%）', '再卖30%', '再卖20%'];
      lines.push(`  止盈卖出（按成本价收益率）：`);
      tpMatches.forEach((m, i) => {
        const pct = (parseFloat(m[1]) * 100).toFixed(0);
        if (actions[i]) lines.push(`    收益率 > ${pct}% → ${actions[i]}`);
      });
    }
    // Extract buy-back rules
    const buyBackMatches = [...jietiBlock.matchAll(/MA(\d+)\s*>\s*price/g)];
    const buyAmounts = ['增持20%', '增持30%', '增持50%'];
    if (buyBackMatches.length > 0) {
      lines.push(`  均线择时增持（成本价低于对应均线时）：`);
      buyBackMatches.forEach((m, i) => {
        if (buyAmounts[i]) lines.push(`    股价 < MA${m[1]} → ${buyAmounts[i]}`);
      });
    }
  }

  // ── 6. Commission and slippage ─────────────────────────────────────────
  const commBlock = getFunctionBlock(code, 'set_slip_fee');
  if (commBlock) {
    lines.push('');
    lines.push('【交易费用】');
    const buyMatch = commBlock.match(/buy_cost\s*=\s*([\d.]+)/);
    const sellMatch = commBlock.match(/sell_cost\s*=\s*([\d.]+)/);
    if (buyMatch && sellMatch) {
      lines.push(`  买入佣金：${(parseFloat(buyMatch[1]) * 100).toFixed(2)}%（万${(parseFloat(buyMatch[1]) * 10000).toFixed(0)}）`);
      lines.push(`  卖出佣金：${(parseFloat(sellMatch[1]) * 100).toFixed(2)}%（含千分之一印花税）`);
    }
    lines.push(`  最低佣金：5元/笔`);
    if (/FixedSlippage\(0\)/.test(commBlock)) lines.push(`  滑点：0（不考虑滑点）`);
  }

  return lines.join('\n');
}

// ── Structured parse ─────────────────────────────────────────────────────────

function parseCoreLogic(code) {
  const signals = {
    universe: null,
    selectors: new Set(),
    buyCount: null,
    rebalanceFreq: null,
    positionMethod: null,
    riskRules: new Set(),
    exitRules: new Set(),
  };

  for (const raw of code.split('\n')) {
    const l = raw.trim();

    const uMatch = l.match(/get_index_stocks\s*\(\s*['"]([^'"]+)/);
    if (uMatch) {
      const map = { '000300': '沪深300', '000016': '上证50', '000905': '中证500', '399101': '中小板', '399106': '深证100', '000852': '中证1000' };
      signals.universe = map[uMatch[1].split('.')[0]] || uMatch[1];
    }

    const bcMatch = l.match(/(?:g\.)?(stocknum|buy_stock_count|hold_count|N)\s*=\s*(\d+)/);
    if (bcMatch) signals.buyCount = parseInt(bcMatch[2]);

    const rbMatch = l.match(/run_daily\s*\([^,]+,\s*time\s*=\s*['"]([^'"]+)/);
    if (rbMatch) signals.rebalanceFreq = `每天 ${rbMatch[1]}`;

    if (/market_cap.*asc|市值.*升序/i.test(l)) signals.selectors.add('市值升序（最小市值）');
    if (/roe|return_on_equity/i.test(l)) signals.selectors.add('ROE');
    if (/pe_ratio|valuation\.pe|市盈率/i.test(l)) signals.selectors.add('PE');

    if (/平均分配|equal.*weight|等权/i.test(l)) signals.positionMethod = '等权分配';

    if (/is_st|ST股/i.test(l)) signals.riskRules.add('过滤ST股');
    if (/limitup|涨停/i.test(l)) signals.riskRules.add('过滤涨停');
    if (/limitdown|跌停/i.test(l)) signals.riskRules.add('过滤跌停');
    if (/paused|停牌/i.test(l)) signals.riskRules.add('过滤停牌');

    if (/close_position|平仓|清仓/i.test(l)) signals.exitRules.add('持仓不在候选列表时清仓');
  }

  const selArr = [...signals.selectors];
  let coreIdea = '股票多头策略';
  if (selArr.some(s => s.includes('市值'))) coreIdea = `市值因子排序选股（${selArr.join('、')}）`;

  return {
    strategyType: '市值选股策略',
    coreIdea,
    universe: signals.universe,
    buyCount: signals.buyCount,
    rebalanceFreq: signals.rebalanceFreq,
    selectors: selArr,
    positionMethod: signals.positionMethod,
    riskRules: [...signals.riskRules],
    exitRules: [...signals.exitRules],
  };
}

// ── Main builder ─────────────────────────────────────────────────────────────

function buildSummary(filepath, stats, comments) {
  if (!fs.existsSync(filepath)) return null;
  const code = fs.readFileSync(filepath, 'utf8');
  const basename = path.basename(filepath, '.py').replace(/_[^_]+$/, '');

  const { strategyType, coreIdea, universe, buyCount, rebalanceFreq, selectors, positionMethod, riskRules, exitRules } = parseCoreLogic(code);

  const lines = [];
  lines.push(`📌 *${basename}*`);
  lines.push('');

  // ── Structured summary ──────────────────────────────────────────────────
  if (universe) lines.push(`📦 股票池: ${universe}`);
  if (buyCount) lines.push(`🔢 持仓数量: ${buyCount}只`);
  if (rebalanceFreq) lines.push(`⏰ 调仓频率: ${rebalanceFreq}`);
  if (selectors.length > 0) lines.push(`🎯 选股因子: ${[...new Set(selectors)].join(' | ')}`);
  if (positionMethod) lines.push(`💰 仓位: ${positionMethod}`);
  if (riskRules.length > 0) lines.push(`🛡️ 风控: ${[...new Set(riskRules)].join(' | ')}`);
  if (exitRules.length > 0) lines.push(`🚪 出场: ${[...new Set(exitRules)].join(' | ')}`);

  // ── Faithful translation ─────────────────────────────────────────────────
  lines.push('');
  lines.push('📝 忠实翻译（代码逻辑）：');
  const faithful = buildFaithfulDescription(code);
  faithful.split('\n').forEach(l => lines.push('  ' + l));

  // ── Comments ─────────────────────────────────────────────────────────────
  if (comments && comments.length > 0) {
    lines.push('');
    lines.push(`💬 社区评论（${comments.length}条）：`);
    comments.slice(0, 2).forEach(c => {
      if (c.isBest) lines.push(`  ✅ ${c.user}（精华）: ${c.content}`);
      else lines.push(`  💬 ${c.user}: ${c.content}`);
    });
  }

  // ── Stats ───────────────────────────────────────────────────────────────
  const statsLine = stats && stats.annualReturn != null
    ? `📊 年化${(stats.annualReturn * 100).toFixed(1)}% | 夏普${stats.sharpe?.toFixed(2)} | 最大回撤${(stats.maxDrawdown * 100).toFixed(1)}%`
    : stats?.annualReturn === null ? '📊 绩效未公开' : '📊 绩效获取失败';
  lines.push('');
  lines.push(statsLine);

  return lines.join('\n');
}

module.exports = { buildSummary };