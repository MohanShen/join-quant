/**
 * strategy-summarize.js
 *
 * Parse a JoinQuant strategy source file and produce a detailed
 * human-readable Chinese summary covering:
 *   - 选股池与数据源
 *   - 具体财务因子或技术指标
 *   - 调仓逻辑（含参数）
 *   - 止盈止损条件（具体数值）
 *   - 风控规则
 *   - 完整策略描述（一段话）
 */

const fs = require('fs');
const path = require('path');

// ── Parse initialize() for key parameters ───────────────────────────────────

function extractParams(code) {
  const params = {};
  const re = /(?:g\.)?(\w+)\s*=\s*(\d+)/g;
  let m;
  while ((m = re.exec(code)) !== null) {
    params[m[1]] = parseInt(m[2]);
  }
  return params;
}

// ── Detect financial factors ────────────────────────────────────────────────

function extractFactors(code) {
  const factors = [];
  const factorMap = {
    'market_cap': '总市值',
    'circulating_market_cap': '流通市值',
    'roe': 'ROE（净资产收益率）',
    'roa': 'ROA（资产收益率）',
    'pe_ratio': 'PE（市盈率）',
    'pb_ratio': 'PB（市净率）',
    'ps_ratio': 'PS（市销率）',
    'gross_profit_margin': '毛利率',
    'net_profit': '净利润',
    'operating_revenue': '营业收入',
    'total_revenue': '总营收',
    'eps': 'EPS（每股收益）',
    'bps': 'BPS（每股净资产）',
    'cash_flow': '现金流',
    'beta': 'Beta（波动率）',
    'turnover_rate': '换手率',
    'volume_ratio': '量比',
    'vol': '波动率',
    'momentum': '动量',
    'size': '市值因子',
  };
  for (const [key, label] of Object.entries(factorMap)) {
    if (new RegExp(`valuation\\.${key}|\\.${key}\\b`, 'i').test(code)) {
      factors.push(label);
    }
  }
  // Technical indicators
  if (/MA\d|均线|移动平均|ema|ewm/i.test(code)) {
    const maMatches = code.match(/MA(\d+)/gi);
    if (maMatches) factors.push('均线 MA(' + [...new Set(maMatches.map(m => m.match(/\d+/)[0]))].sort().join('/') + ')');
  }
  if (/RSI|相对强弱|rsi/i.test(code)) factors.push('RSI 强弱指标');
  if (/MACD|macd/i.test(code)) factors.push('MACD');
  if (/布林|boll|band/i.test(code)) factors.push('布林带');
  return factors;
}

// ── Detect stop loss / stop profit rules ─────────────────────────────────────

function extractStopRules(code) {
  const rules = [];

  // MA cross stop loss
  const maCrossMatch = code.match(/MA(\d+).*cross.*MA(\d+)|(\d+)[天日]均线.*下穿|短线.*长线.*死叉/i);
  if (maCrossMatch) {
    const short = code.match(/(?:short_d|g\.short)\s*=\s*(\d+)/)?.[1];
    const long = code.match(/(?:long_d|g\.long)\s*=\s*(\d+)/)?.[1];
    if (short && long) rules.push(`均线止损：${short}日均线下穿${long}日均线时清仓`);
    else rules.push('均线死叉止损');
  }

  // Percentage stop loss
  const slMatch = code.match(/stop.*?(?:loss|止损)|亏损.*?(%|percent)|止损.*?(%|percent)/i);
  if (slMatch) rules.push('固定比例止损');

  // Percentage take profit (ladder)
  const tpMatches = code.match(/(?:ret|收益|涨幅)\s*[><=]\s*(0\.\d+|\d+%)/g);
  if (tpMatches) {
    const levels = tpMatches.map(m => {
      const v = m.match(/0\.\d+/)?.[0] || m.match(/\d+/)?.[0];
      if (v) return parseFloat(v) < 1 ? `${(parseFloat(v)*100).toFixed(0)}%` : `${v}%`;
      return m;
    });
    if (levels.length > 0) rules.push(`阶梯止盈：${levels.join('、')} 分批卖出`);
  }

  // Daily rebalance stop loss (收盘止损)
  if (/止损|平仓.*条件|if.*price.*跌破/i.test(code)) {
    rules.push('价格跌破止损线时清仓');
  }

  return rules;
}

// ── Extract rebalancing rules ────────────────────────────────────────────────

function extractRebalance(code) {
  const rules = [];
  const params = extractParams(code);

  if (params.stocknum) rules.push(`持股数量 ${params.stocknum} 只`);
  if (/equal.*weight|平均分配|等权/i.test(code)) rules.push('等权重分配');
  if (/cash\s*\/\s*\w+|每只股票.*金额/i.test(code)) rules.push(`每只股票分配资金 = 总权益 / 持股数`);

  // Ladder rebalance (阶梯调仓)
  if (/jieti|阶梯.*调仓|分批/i.test(code)) {
    const levels = code.match(/ret[><]=?\s*(0\.\d+)/g);
    if (levels.length > 0) {
      const pct = levels.map(m => (parseFloat(m.match(/0\.\d+/)[0]) * 100).toFixed(0) + '%').join('、');
      rules.push(`阶梯调仓（涨${pct}分批减仓）`);
    }
  }

  const rebalTimes = code.match(/run_daily\([^,]+,\s*time\s*=\s*['"]([^'"]+)/g);
  if (rebalTimes) {
    const times = rebalTimes.map(m => m.match(/['"]([^'"]+)/)?.[1]).filter(Boolean);
    rules.push(`每日调仓时间: ${[...new Set(times)].join(', ')}`);
  }

  return rules;
}

// ── Stock universe ───────────────────────────────────────────────────────────

function extractUniverse(code) {
  const stocks = [];
  const maps = { '000300': '沪深300', '000016': '上证50', '000905': '中证500', '399101': '中小板', '399106': '深证综指', '000852': '中证1000', '000001': '上证综指' };
  for (const [code, name] of Object.entries(maps)) {
    if (new RegExp(code + '\\.XSHG|' + code + '\\.XSHE').test(code)) stocks.push(name);
  }
  return stocks;
}

// ── Risk rules ───────────────────────────────────────────────────────────────

function extractRiskRules(code) {
  const rules = [];
  if (/is_st|ST股|filter.*st/i.test(code)) rules.push('过滤 ST 股');
  if (/limitup|涨停/i.test(code)) rules.push('过滤涨停股');
  if (/limitdown|跌停/i.test(code)) rules.push('过滤跌停股');
  if (/paused|停牌|filter.*paused/i.test(code)) rules.push('过滤停牌股');
  if (/set_feasible|feasible.*stock/i.test(code)) rules.push('剔除停牌股（样本期检查）');
  return rules;
}

// ── Full natural language description ───────────────────────────────────────

function buildNaturalDescription(code, params, factors, stopRules, rebalanceRules, universe, riskRules) {
  const parts = [];

  // Stock pool
  if (universe.length > 0) {
    parts.push(`选股池：${universe.join('+')} 所有股票`);
  } else {
    parts.push('选股池：全市场股票');
  }

  // Factor selection
  if (factors.length > 0) {
    const sortedFactors = [...new Set(factors)];
    parts.push(`选股因子：${sortedFactors.join('、')}，按因子值排序选取`);
  } else {
    // Try to infer from code
    if (/market_cap.*asc|市值.*升序/i.test(code)) {
      parts.push('选股方式：市值升序（最小市值）选取');
    } else if (/order_by.*asc/i.test(code)) {
      parts.push('按因子值升序选取');
    }
  }

  // Position sizing
  if (params.stocknum) {
    parts.push(`持仓：固定持有 ${params.stocknum} 只股票，等权分配`);
  }

  // Rebalance
  const rebalTimes = code.match(/run_daily\([^,]+,\s*time\s*=\s*['"]([^'"]+)/g);
  if (rebalTimes) {
    const times = [...new Set(rebalTimes.map(m => m.match(/['"]([^'"]+)/)?.[1]))];
    parts.push(`调仓：每日 ${times.join('/')} 执行调仓和风控`);
  }

  // Stop loss
  const maSL = stopRules.find(r => r.includes('均线止损'));
  if (maSL) parts.push(`止损：${maSL}`);

  const ladderTP = stopRules.find(r => r.includes('阶梯止盈'));
  if (ladderTP) parts.push(`止盈：${ladderTP}`);

  // Risk
  if (riskRules.length > 0) {
    parts.push(`风控：${[...new Set(riskRules)].join('、')}`);
  }

  // Period
  const periodMatch = code.match(/20\d{2}[-年]\d{1,2}[-月]\d{1,2}/);
  if (periodMatch) parts.push(`回测期：${periodMatch[0]} 起`);

  return parts.join('；');
}

// ── Main builder ─────────────────────────────────────────────────────────────

function buildSummary(filepath, stats, comments) {
  if (!fs.existsSync(filepath)) return null;
  const code = fs.readFileSync(filepath, 'utf8');
  const basename = path.basename(filepath, '.py').replace(/_[^_]+$/, '');
  const params = extractParams(code);
  const factors = extractFactors(code);
  const stopRules = extractStopRules(code);
  const rebalanceRules = extractRebalance(code);
  const universe = extractUniverse(code);
  const riskRules = extractRiskRules(code);
  const description = buildNaturalDescription(code, params, factors, stopRules, rebalanceRules, universe, riskRules);

  const lines = [];
  lines.push(`📌 *${basename}*`);
  lines.push('');

  // Natural language description
  lines.push(`🔍 策略逻辑：${description}`);
  lines.push('');

  // Key parameters
  const paramDescs = [];
  if (params.stocknum) paramDescs.push(`持股数=${params.stocknum}`);
  if (params.short_d) paramDescs.push(`短线MA=${params.short_d}日`);
  if (params.long_d) paramDescs.push(`长线MA=${params.long_d}日`);
  if (params.shift) paramDescs.push(`停牌观察=${params.shift}日`);
  if (params.buylist !== undefined) paramDescs.push(`候选股数=${params.buylist}`);
  if (paramDescs.length > 0) lines.push(`⚙️ 关键参数：${paramDescs.join(' | ')}`);

  // Stop rules
  if (stopRules.length > 0) {
    lines.push(`🛑 止盈止损：${[...new Set(stopRules)].join('；')}`);
  }

  // Comments
  if (comments && comments.length > 0) {
    lines.push('');
    lines.push(`💬 社区评论（${comments.length}条）：`);
    comments.slice(0, 2).forEach(c => {
      if (c.isBest) lines.push(`  ✅ ${c.user}（精华）: ${c.content}`);
      else lines.push(`  💬 ${c.user}: ${c.content}`);
    });
  }

  lines.push('');
  const statsLine = stats && stats.annualReturn != null
    ? `📊 年化${(stats.annualReturn * 100).toFixed(1)}% | 夏普${stats.sharpe?.toFixed(2)} | 最大回撤${(stats.maxDrawdown * 100).toFixed(1)}%`
    : stats?.annualReturn === null ? '📊 绩效未公开（回测报告不公开）' : '📊 绩效获取失败';
  lines.push(statsLine);

  return lines.join('\n');
}

module.exports = { buildSummary };