/**
 * strategy-summarize.js
 *
 * Parse a JoinQuant strategy source file and produce a human-readable
 * Chinese summary covering:
 *   1. 策略类型与核心思路
 *   2. 选股逻辑（数据来源、选股因子、股票池）
 *   3. 交易逻辑（调仓频率、仓位分配、买入卖出规则）
 *   4. 风控逻辑（止损、仓位上限等）
 *   5. 回测时间范围
 */

const fs = require('fs');
const path = require('path');

// ── Core strategy logic parser ─────────────────────────────────────────────

function parseCoreLogic(code) {
  const signals = {
    universe: null,
    selectors: new Set(),
    buyCount: null,
    rebalanceFreq: null,
    positionMethod: null,
    entryRules: new Set(),
    exitRules: new Set(),
    riskRules: new Set(),
  };

  for (const raw of code.split('\n')) {
    const l = raw.trim();

    // Stock universe
    const uMatch = l.match(/get_index_stocks\s*\(\s*['"]([^'"]+)/);
    if (uMatch) {
      const map = { '000300': '沪深300', '000016': '上证50', '000905': '中证500', '399101': '中小板', '399106': '深证100', '000852': '中证1000' };
      const k = uMatch[1].split('.')[0];
      signals.universe = map[k] || uMatch[1];
    }

    // Buy count
    const bcMatch = l.match(/(?:g\.)?(buy_stock_count|hold_count|N)\s*=\s*(\d+)/);
    if (bcMatch) signals.buyCount = parseInt(bcMatch[2]);

    // Rebalance
    const rbMatch = l.match(/run_daily\s*\([^,]+,\s*time\s*=\s*['"]([^'"]+)/);
    if (rbMatch) signals.rebalanceFreq = `每天 ${rbMatch[1]}`;
    if (/run_weekly|周频/i.test(l)) signals.rebalanceFreq = '周频调仓';

    // Selectors
    if (/market_cap.*asc|市值.*升序/i.test(l)) signals.selectors.add('市值升序（最小市值）');
    if (/roe|return_on_equity/i.test(l)) signals.selectors.add('ROE（净资产收益率）');
    if (/pe_ratio|valuation\.pe|市盈率/i.test(l)) signals.selectors.add('PE（市盈率）');
    if (/volume|成交额|momentum|动量/i.test(l)) signals.selectors.add('成交量/动量');

    // Position
    if (/cash\s*\/\s*\w+|平均分配|equal.*weight|等权重/i.test(l)) signals.positionMethod = '资金平均分配（等权）';

    // Filters → risk rules
    if (/is_st|ST股/i.test(l)) signals.riskRules.add('过滤ST股');
    if (/limitup|涨停/i.test(l)) signals.riskRules.add('过滤涨停股');
    if (/limitdown|跌停/i.test(l)) signals.riskRules.add('过滤跌停股');
    if (/paused|停牌/i.test(l)) signals.riskRules.add('过滤停牌股');

    // Exit
    if (/close_position|平仓|卖出.*不在|清仓/i.test(l)) signals.exitRules.add('持仓不在候选列表时清仓');
  }

  // Infer strategy type
  let strategyType = '股票多头策略';
  let coreIdea = '未识别';
  const selArr = [...signals.selectors];
  if (signals.universe?.includes('中小板') && selArr.some(s => s.includes('市值'))) {
    strategyType = '小市值选股策略';
    coreIdea = '每日选取中小板市值最小的N只股票，等权持有，次日调仓';
  } else if (selArr.some(s => s.includes('ROE'))) {
    strategyType = '多因子选股策略';
    coreIdea = `基于因子选股：${selArr.join('、')}`;
  } else if (selArr.some(s => s.includes('市值'))) {
    strategyType = '市值选股策略';
    coreIdea = '基于市值因子排序选股';
  }

  return {
    strategyType,
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

function extractPeriod(code) {
  const m = code.match(/(?:20\d{2}[-年]\d{1,2}[-月]\d{1,2})/);
  return m ? m[0] : null;
}

function buildSummary(filepath, stats) {
  if (!fs.existsSync(filepath)) return null;
  const code = fs.readFileSync(filepath, 'utf8');
  const basename = path.basename(filepath, '.py').replace(/_[^_]+$/, '');

  const { strategyType, coreIdea, universe, buyCount, rebalanceFreq, selectors, positionMethod, riskRules, exitRules } = parseCoreLogic(code);
  const period = extractPeriod(code);

  const lines = [];
  lines.push(`📌 *${basename}*`);
  lines.push(`💡 策略类型: ${strategyType}`);
  lines.push(`🔑 核心逻辑: ${coreIdea}`);
  if (universe) lines.push(`📦 股票池: ${universe}`);
  if (buyCount) lines.push(`🔢 持仓数量: ${buyCount}只`);
  if (rebalanceFreq) lines.push(`⏰ 调仓频率: ${rebalanceFreq}`);
  if (selectors.length > 0) lines.push(`🎯 选股因子: ${[...new Set(selectors)].join(' | ')}`);
  if (positionMethod) lines.push(`💰 仓位分配: ${positionMethod}`);
  if (riskRules.length > 0) lines.push(`🛡️ 风控: ${[...new Set(riskRules)].join(' | ')}`);
  if (exitRules.length > 0) lines.push(`🚪 出场: ${[...new Set(exitRules)].join(' | ')}`);
  if (period) lines.push(`📅 回测期: ${period}`);

  const statsLine = stats && stats.annualReturn != null
    ? `📊 年化${(stats.annualReturn * 100).toFixed(1)}% | 夏普${stats.sharpe?.toFixed(2)} | 回撤${(stats.maxDrawdown * 100).toFixed(1)}%`
    : stats?.annualReturn === null ? '📊 绩效未公开（回测报告不公开）' : '📊 绩效获取失败';
  lines.push(statsLine);

  return lines.join('\n');
}

module.exports = { buildSummary };