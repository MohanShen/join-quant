/**
 * strategy-summarize.js
 *
 * Parse a JoinQuant strategy source file and produce:
 * 1. A structured summary (factors, params, risk rules)
 * 2. A FAITHFUL natural-language translation of the actual code logic
 *    (long-form paragraphs, not bullet points)
 */

const fs = require('fs');
const path = require('path');

// ── Helper: extract function block by line number ────────────────────────────

function getFunctionBlock(code, fnName) {
  const lines = code.split('\n');
  const startIdx = lines.findIndex(l => l.trim().startsWith(`def ${fnName}(`));
  if (startIdx < 0) return null;
  let endIdx = lines.length;
  for (let i = startIdx + 1; i < lines.length; i++) {
    const l = lines[i].trim();
    if (l.startsWith('##') || (l.startsWith('def ') && !l.startsWith(`def ${fnName}`))) {
      endIdx = i;
      break;
    }
  }
  return lines.slice(startIdx, endIdx).join('\n');
}

// ── Helper: extract g.xxx parameter ─────────────────────────────────────────

function g(code, name) {
  const m = code.match(new RegExp(`g\\.${name}\\s*=\\s*(\\d+)`));
  return m ? parseInt(m[1]) : null;
}

// ── Pool name resolver ──────────────────────────────────────────────────────

const POOL_NAMES = {
  '000001.XSHG': '上证综指',
  '399106.XSHE': '深证综指',
  '000300.XSHG': '沪深300',
  '000905.XSHG': '中证500',
  '399101.XSHE': '中小板',
  '000852.XSHE': '中证1000',
  '000016.XSHG': '上证50',
};

// ── Faithful description (long-form paragraphs) ──────────────────────────────

function buildFaithfulDescription(code, stats) {
  // ── Parse key parameters ────────────────────────────────────────────────────
  const stocknum  = g(code, 'stocknum');
  const shift     = g(code, 'shift');     // pause lookback days
  const short_d   = g(code, 'short_d');   // short MA period
  const long_d    = g(code, 'long_d');    // long MA period

  // ── Stock universe ─────────────────────────────────────────────────────────
  const poolCodes = [...code.matchAll(/get_index_stocks\(['"]([^'"]+)/g)].map(m => m[1]);
  const poolNames = poolCodes.map(c => POOL_NAMES[c] || c).filter(Boolean);
  const poolDesc  = poolNames.length > 0 ? poolNames.join(' + ') : '全市场';
  const poolCountHint = poolNames.length > 1 ? '约4000只' : '';

  // ── Trading schedule ───────────────────────────────────────────────────────
  const schedules = [...code.matchAll(/run_daily\([^,]+,\s*time\s*=\s*['"]([^'"]+)/g)].map(m => m[1]);
  const uniqueTimes = [...new Set(schedules)];

  // ── Rebalance block ─────────────────────────────────────────────────────────
  const rebalBlock = getFunctionBlock(code, 'rebalance');
  const jietiBlock = getFunctionBlock(code, 'jieti');

  // Is jieti called from market_open?
  const marketOpenBlock = getFunctionBlock(code, 'market_open');
  const jietiCalled = marketOpenBlock ? /jieti\s*\(/.test(marketOpenBlock) : false;

  // Double-order bug in rebalance
  const doubleOrder = rebalBlock
    ? (rebalBlock.match(/for i in holding_list[\s\S]{1,150}for i in holding_list/) !== null)
    : false;

  // ── Stop loss block ─────────────────────────────────────────────────────────
  const zhisunBlock = getFunctionBlock(code, 'zhisun');

  // ── Commission block ────────────────────────────────────────────────────────
  const commBlock = getFunctionBlock(code, 'set_slip_fee');
  const buyCostMatch  = commBlock ? commBlock.match(/buy_cost\s*=\s*([\d.]+)/) : null;
  const sellCostMatch = commBlock ? commBlock.match(/sell_cost\s*=\s*([\d.]+)/) : null;

  // ── Benchmark ───────────────────────────────────────────────────────────────
  const bmMatch = code.match(/set_benchmark\(['"]([^'"]+)/);
  const bmNames = { '000300.XSHG': '沪深300', '000016.XSHG': '上证50', '000905.XSHG': '中证500' };
  const benchmark = bmMatch ? (bmNames[bmMatch[1]] || bmMatch[1]) : '未设定';

  // Code stats
  const lineCount = code.split('\n').length;
  const periodMatch = code.match(/#\s*(\d{4}-\d{2}-\d{2})\s*到\s*(\d{4}-\d{2}-\d{2})/);
  const periodStr = periodMatch ? `回测区间：${periodMatch[1]} ~ ${periodMatch[2]}` : null;

  // ─────────────────────────────────────────────────────────────────────────
  // Build paragraphs
  // ─────────────────────────────────────────────────────────────────────────

  const paras = [];

  // ── 选股池 ──────────────────────────────────────────────────────────────
  if (poolNames.length > 0) {
    paras.push(
      `选股池：每天 ${uniqueTimes.includes('09:00') ? '09:00' : '每日盘前'}，` +
      `在「${poolDesc}」${poolCountHint ? `（${poolCountHint}）` : ''}内进行筛选。` +
      (shift
        ? `先剔除近${shift}个交易日内有停牌的股票（确保样本期内持续可交易），再从中选取总市值最小的${stocknum || 'N'}只股票，构建次日买入候选列表。`
        : `按总市值升序排序，选取最小的${stocknum || 'N'}只股票，构建次日买入候选列表。`)
    );
  }

  // ── 仓位分配 ────────────────────────────────────────────────────────────
  paras.push(
    `仓位分配：每日${rebalBlock ? ` ${uniqueTimes.includes('09:30') ? '09:30' : uniqueTimes[0]} 开盘时` : ''}，将账户总权益平均分为${stocknum || 'N'}份，每只股票分配等额资金（总权益/${stocknum || 'N'}）。` +
    `若有持仓股票不在候选列表，则市价卖出；若候选股票不在当前持仓，则等额买入。`
  );

  // ── 止损 ────────────────────────────────────────────────────────────────
  if (zhisunBlock && zhisunBlock.trim().length > 50) {
    const sd = short_d ?? 10;
    const ld = long_d  ?? 50;
    paras.push(
      `止损（每日${uniqueTimes.includes('09:30') ? '09:30' : '每日调仓时'}触发）：检查全部持仓股票，计算${sd}日收盘价均线（MA${sd}）与${ld}日收盘价均线（MA${ld}）。` +
      `若 MA${sd} 从上往下穿越 MA${ld}（死叉），且该股票当前可卖出（不在停牌、且有足够可平数量），则市价清仓。` +
      `此为纯技术面止损，不设固定亏损比例，依赖均线趋势判断。`
    );
  }


  // ── 风控 ────────────────────────────────────────────────────────────────
  const riskParts = [];
  if (shift)    riskParts.push(`剔除近${shift}日有停牌的股票（样本期需持续可交易）`);
  if (/is_st|ST股/.test(code))      riskParts.push('过滤ST股及退市股');
  if (/limitup|涨停/.test(code))     riskParts.push('过滤涨停股（避免追高）');
  if (/limitdown|跌停/.test(code))   riskParts.push('过滤跌停股（避免流动性风险）');
  riskParts.push(`滑点设为0（不考虑滑点）`);
  if (buyCostMatch || sellCostMatch) {
    const b = buyCostMatch  ? `买入万${(parseFloat(buyCostMatch[1])*10000).toFixed(0)}`  : '';
    const s = sellCostMatch ? `卖出千${(parseFloat(sellCostMatch[1])*1000).toFixed(1)}（含印花税）` : '';
    riskParts.push(`手续费：${[b, s].filter(Boolean).join('，')}，最低5元/笔，含印花税千分之一`);
  }
  if (periodStr) riskParts.push(periodStr);
  if (stats?.periodLabel) riskParts.push(`回测区间：${stats.periodLabel}（起）`);
  riskParts.push(`代码行数：${lineCount}行`);
  paras.push(`风控：${riskParts.join('；')}。`);

  return paras.join('\n\n');
}

// ── Structured parse (compact summary line) ─────────────────────────────────

function parseCoreLogic(code) {
  const poolCodes = [...code.matchAll(/get_index_stocks\(['"]([^'"]+)/g)].map(m => m[1]);
  const poolNames = poolCodes.map(c => POOL_NAMES[c] || c).filter(Boolean);
  const bcMatch = code.match(/(?:g\.)?(stocknum|buy_stock_count|N)\s*=\s*(\d+)/);
  const rbMatch = code.match(/run_daily\s*\([^,]+,\s*time\s*=\s*['"]([^'"]+)/);
  const selHasSize = /market_cap.*asc|市值.*asc/i.test(code);
  const hasRoe = /roe|return_on_equity/i.test(code);

  const freq = rbMatch ? `每天 ${rbMatch[1]}` : '';
  const pool = poolNames.length > 0 ? poolNames.join('+') : '全市场';
  const type = selHasSize ? '市值选股策略' : hasRoe ? '多因子选股策略' : '股票多头策略';

  return {
    type,
    pool,
    count: bcMatch ? parseInt(bcMatch[2]) : null,
    freq,
    factors: selHasSize ? ['市值升序'] : (hasRoe ? ['ROE'] : []),
  };
}

// ── Main builder ─────────────────────────────────────────────────────────────

function buildSummary(filepath, stats, comments) {
  if (!fs.existsSync(filepath)) return null;
  const code = fs.readFileSync(filepath, 'utf8');
  const basename = path.basename(filepath, '.py').replace(/_[^_]+$/, '');

  const { type, pool, count, freq, factors } = parseCoreLogic(code);

  const lines = [];
  lines.push(`📌 *${basename}*`);
  lines.push('');

  // Compact summary line
  const summaryParts = [];
  if (pool)   summaryParts.push(`选股池：${pool}`);
  if (count)   summaryParts.push(`持股${count}只`);
  if (freq)    summaryParts.push(`调仓${freq}`);
  if (factors.length > 0) summaryParts.push(`因子：${factors.join(',')}`);
  if (summaryParts.length > 0) lines.push(summaryParts.join(' | '));
  lines.push('');

  // Faithful translation (long-form paragraphs)
  lines.push('忠实翻译（代码逻辑）：');
  const faithful = buildFaithfulDescription(code, stats);
  faithful.split('\n\n').forEach(p => {
    p.split('\n').forEach(l => lines.push(l));
    lines.push('');
  });

  // Comments
  if (comments && comments.length > 0) {
    lines.push(`💬 社区评论（${comments.length}条）：`);
    comments.slice(0, 2).forEach(c => {
      if (c.isBest) lines.push(`  ✅ ${c.user}（精华）: ${c.content}`);
      else lines.push(`  💬 ${c.user}: ${c.content}`);
    });
  }

  // Stats
  const statsLine = stats && stats.annualReturn != null
    ? `📊 年化${(stats.annualReturn * 100).toFixed(1)}% | 夏普${stats.sharpe?.toFixed(2)} | 最大回撤${(stats.maxDrawdown * 100).toFixed(1)}%`
    : stats?.annualReturn === null ? '📊 绩效未公开' : '📊 绩效获取失败';
  lines.push(statsLine);

  return lines.join('\n');
}

module.exports = { buildSummary };