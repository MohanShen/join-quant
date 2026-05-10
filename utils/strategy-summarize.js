/**
 * strategy-summarize.js
 *
 * Parse a strategy source file and extract a human-readable summary:
 * - Data sources used (price, fundamentals, factors)
 * - Time horizon / rebalancing frequency
 * - Strategy type / idea
 * - Key innovations or notable features
 */

const fs = require('fs');
const path = require('path');

const STRATEGIES_DIR = path.join(__dirname, '..', 'strategies');

// ── Strategy type classifiers ────────────────────────────────────────────────

const STRATEGY_TYPES = [
  { pattern: /布林|boll|band/i, label: '布林带均值回归' },
  { pattern: /均线|ma[_ ]|moving average|趋势/i, label: '趋势跟踪' },
  { pattern: /macd|dmi|rsi|动量|趋势跟随/i, label: '趋势/动量' },
  { pattern: /因子|factor|多因子|市值|roe|pe|eps/i, label: '多因子选股' },
  { pattern: /网格|grid/i, label: '网格交易' },
  { pattern: /套利|统计套利|价差|spread/i, label: '套利策略' },
  { pattern: /海龟|turtle/i, label: '海龟交易法则' },
  { pattern: /做市|market[ _]?maker/i, label: '做市策略' },
  { pattern: /高频|转仓|roll/i, label: '高频/换月' },
  { pattern: /价值|低估|股息|dividend/i, label: '价值投资' },
];

function detectStrategyType(code) {
  for (const { pattern, label } of STRATEGY_TYPES) {
    if (pattern.test(code)) return label;
  }
  // Fallback: look for common patterns
  if (/set_universe|get_index_stocks/i.test(code)) return '指数增强';
  if (/future|期货|期权/i.test(code)) return '衍生品策略';
  if (/cash.|position|stock.*hold/i.test(code)) return '股票多头';
  return '通用量化策略';
}

// ── Data source extractor ────────────────────────────────────────────────────

function extractDataSources(code) {
  const sources = new Set();

  if (/get_price|get_history|price.*data/i.test(code)) {
    const m = code.match(/get_price\s*\([^)]*\)/);
    sources.add(m ? `行情数据(${m[0].slice(0, 50)})` : '行情数据(price)');
  }
  if (/get_fundamentals|fundamental|财务|eps|roe|pe\(/i.test(code)) sources.add('基本面数据');
  if (/get_index_stocks|index.*constituent/i.test(code)) sources.add('指数成分股');
  if (/停牌|ST|涨跌停/i.test(code)) sources.add('风险过滤(停牌/ST)');
  if (/finance\.|invalidate|分析师预期/i.test(code)) sources.add('分析师数据');
  if (/stock_rank|sw\d|申万|行业/i.test(code)) sources.add('行业分类');

  return [...sources];
}

// ── Rebalancing frequency ─────────────────────────────────────────────────────

function extractFrequency(code) {
  // Look for rebalancing period settings
  const tcMatch = code.match(/g\.tc\s*=\s*(\d+)/);
  const ybMatch = code.match(/g\.yb\s*=\s*(\d+)/);
  const nMatch = code.match(/g\.N\s*=\s*(\d+)/); // number of stocks held

  // Look for comments mentioning period
  const periodMatch = code.match(/(?:调仓|换仓|换月|rebalanc)[^\n]{0,30}(\d+)\s*(?:天|日|月|年|trading|day)/i);
  const freqMatch = code.match(/(?:日频|分钟|小时|每天|每周|每月)/i);

  if (freqMatch) return freqMatch[0];
  if (tcMatch) return `每${tcMatch[1]}天调仓一次`;
  if (periodMatch) return `每${periodMatch[1]}天调仓`;
  if (/日频|daily|每天/i.test(code)) return '日频调仓';
  if (/handle.*daily|run_daily/i.test(code)) return '日频调仓';
  return '调仓周期未说明';
}

// ── Key parameters ────────────────────────────────────────────────────────────

function extractKeyParams(code) {
  const params = [];
  const paramPatterns = [
    { pattern: /g\.tc\s*=\s*(\d+)/, label: '调仓周期' },
    { pattern: /g\.yb\s*=\s*(\d+)/, label: '样本期' },
    { pattern: /g\.N\s*=\s*(\d+)/, label: '持仓数' },
    { pattern: /g\.factors?\s*=\s*\[(.*?)\]/i, label: '因子列表' },
    { pattern: /滑点|slippage\s*[=:]\s*[\d.]+/i, label: '滑点设置' },
    { pattern: /手续费|commission\s*[=:]\s*[\d.]+/i, label: '手续费设置' },
  ];

  for (const { pattern, label } of paramPatterns) {
    const m = code.match(pattern);
    if (m) params.push(`${label}: ${m[1] || m[0]}`);
  }

  return params;
}

// ── Innovation extractor ─────────────────────────────────────────────────────

function extractInnovation(code) {
  const innovationBlocks = [];

  // Look for commented innovation sections
  const commentLines = code.split('\n').filter(l => l.trim().startsWith('#'));
  for (const line of commentLines) {
    if (/创新|亮点|特点|改进|核心|key|unique|innovation/i.test(line)) {
      innovationBlocks.push(line.replace(/^#+\s*/, '').trim());
    }
  }

  // Check for specific advanced features
  if (/机器学习|ml|sklearn|xgb|lgb|neural|lstm/i.test(code)) innovationBlocks.push('使用机器学习模型');
  if (/风控|risk.*control|止损|stop/i.test(code)) innovationBlocks.push('包含风险/止损机制');
  if (/对冲|hedge|alpha.*beta/i.test(code)) innovationBlocks.push('含对冲/Alpha套利');
  if (/仓位|position.*size|风险管理/i.test(code)) innovationBlocks.push('动态仓位管理');
  if (/ quantile | 分位数 | 百分位 /i.test(code)) innovationBlocks.push('分位数/排序风控');

  if (innovationBlocks.length > 0) {
    return innovationBlocks.slice(0, 3).join(' | ');
  }
  return '无特别说明';
}

// ── Backtest period extractor ────────────────────────────────────────────────

function extractPeriod(code) {
  const m = code.match(/(?:20\d{2}[-年]\d{1,2}[-月]\d{1,2}|start.*date|end.*date)[^\n]{0,50}/i);
  return m ? m[0].slice(0, 60) : '回测时间未标注';
}

// ── Main summarizer ────────────────────────────────────────────────────────────

function summarizeStrategy(filepath) {
  if (!fs.existsSync(filepath)) return { error: `File not found: ${filepath}` };

  const code = fs.readFileSync(filepath, 'utf8');
  const basename = path.basename(filepath, '.py');

  const strategyType = detectStrategyType(code);
  const dataSources = extractDataSources(code);
  const frequency = extractFrequency(code);
  const keyParams = extractKeyParams(code);
  const innovation = extractInnovation(code);
  const period = extractPeriod(code);

  return {
    strategyType,
    dataSources,
    frequency,
    keyParams,
    innovation,
    period,
    // Compact WeChat-friendly summary
    toWeChatSummary(stats) {
      const statsLine = stats && stats.annualReturn != null
        ? `年化${(stats.annualReturn * 100).toFixed(1)}% | 夏普${stats.sharpe} | 回撤${(stats.maxDrawdown * 100).toFixed(1)}%`
        : stats?.annualReturn === null ? '绩效未公开' : '绩效获取失败';

      const lines = [
        `📊 *${basename}*`,
        `📈 类型: ${strategyType}`,
        `📅 调仓: ${frequency}`,
        `📐 数据: ${dataSources.length > 0 ? dataSources.join(', ') : '未说明'}`,
        `💡 亮点: ${innovation}`,
        `🧮 ${statsLine}`,
      ];
      return lines.join('\n');
    },
  };
}

module.exports = { summarizeStrategy };