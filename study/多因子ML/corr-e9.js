#!/usr/bin/env node
/**
 * q-e9-corr — ZERO-BACKTEST analysis.
 *
 * Correlate 多因子ML's base (d02cde29) epoch-9 TRAIN curve against every other stored
 * epoch-9 TRAIN curve, grouped by the member's hand-assigned `family:`.
 *
 * Discipline (both measured errors this repo has already paid for):
 *  - returns are CHAINED from cumulative percent by series.dailyReturns(); never differenced.
 *  - alignment is BY DATE via series.correlate(); never by index.
 * Nothing is written. The recorder owns findings.tsv / the family page / the queue.
 */
const fs = require('fs');
const path = require('path');
const series = require('../../utils/backtest-series');
const fm = require('../../utils/frontmatter');
const ledger = require('../../utils/ledger');

const ROOT = path.resolve(__dirname, '../..');
const BASE_KEY = '2026-06-28_高质量稳定上涨策略-d02cde29__train__e9';

// ---- sourceFile -> { family, title } from the wiki (hand-assigned labels) -------------------
const wikiDir = path.join(ROOT, 'wiki/strategies');
const meta = new Map();
for (const f of fs.readdirSync(wikiDir).filter(x => x.endsWith('.md'))) {
  const text = fs.readFileSync(path.join(wikiDir, f), 'utf8');
  const src = fm.field(text, 'sourceFile');
  if (!src) continue;
  meta.set(src, {
    family: fm.link(text, 'family') || null,
    familyProposal: fm.link(text, 'familyProposal') || null,
    title: fm.field(text, 'title') || '',
    flags: fm.field(text, 'realizabilityFlags') || '',
  });
}

// ---- newest-row-wins objective per sourceFile, epoch 9 only --------------------------------
const obj = new Map();
for (const r of ledger.normalized()) {
  if (Number(r.epoch) !== 9) continue;
  obj.set(r.sourceFile, { objective: Number(r.objective), sharpe: Number(r.sharpe), annual: Number(r.annual_pct), maxdd: Number(r.maxdd_pct) });
}

// ---- the base -------------------------------------------------------------------------------
const base = series.load(BASE_KEY);
if (!base) throw new Error('base curve missing: ' + BASE_KEY);

// ---- correlate against every other epoch-9 TRAIN curve --------------------------------------
const keys = series.list().filter(k => k.endsWith('__train__e9') && k !== BASE_KEY);
const rows = [];
for (const k of keys) {
  const rec = series.load(k);
  if (!rec) continue;
  const { corr, overlapDays } = series.correlate(base, rec);
  const m = meta.get(rec.sourceFile) || {};
  const o = obj.get(rec.sourceFile) || {};
  rows.push({
    key: k,
    sourceFile: rec.sourceFile,
    family: m.family || (m.familyProposal ? '(proposal:' + m.familyProposal + ')' : '(unassigned)'),
    title: m.title,
    flags: m.flags,
    rho: corr,
    overlapDays,
    points: rec.points,
    start: rec.start,
    end: rec.end,
    objective: o.objective,
    sharpe: o.sharpe,
    annual: o.annual,
    maxdd: o.maxdd,
  });
}
rows.sort((a, b) => (b.rho ?? -2) - (a.rho ?? -2));

module.exports = { base, rows, BASE_KEY, meta, obj };

if (require.main === module || process.env.CORR_RUN) {
  const mode = process.env.CORR_MODE || 'top';
  const bo = obj.get(base.sourceFile) || {};
  console.log(`BASE  ${base.sourceFile}`);
  console.log(`      ${base.points} pts  ${base.start}..${base.end}  objective ${bo.objective} sharpe ${bo.sharpe} annual ${bo.annual} maxdd ${bo.maxdd}`);
  console.log(`      curves compared: ${rows.length} (of ${keys.length + 1} epoch-9 TRAIN curves)`);
  console.log('');

  const fmtRow = r => [
    (r.rho == null ? 'null' : r.rho.toFixed(4)).padStart(7),
    String(r.overlapDays).padStart(4),
    (r.objective == null ? '—' : r.objective.toFixed(4)).padStart(8),
    (r.sharpe == null ? '—' : r.sharpe.toFixed(2)).padStart(6),
    (r.family || '').padEnd(12),
    r.sourceFile.replace(/^strategies\//, ''),
  ].join('  ');
  const head = ['    rho', ' ovl', '     obj', ' sharpe', 'family      ', 'sourceFile'].join('  ');

  if (mode === 'top' || mode === 'all') {
    const n = mode === 'all' ? rows.length : Number(process.env.CORR_N || 30);
    console.log(`== TOP ${n} BY rho ==`);
    console.log(head);
    for (const r of rows.slice(0, n)) console.log(fmtRow(r));
    console.log('');
    if (mode !== 'all') {
      console.log('== BOTTOM 5 BY rho ==');
      console.log(head);
      for (const r of rows.slice(-5)) console.log(fmtRow(r));
      console.log('');
    }
  }

  // per-family summary
  const byFam = new Map();
  for (const r of rows) {
    if (r.rho == null) continue;
    if (!byFam.has(r.family)) byFam.set(r.family, []);
    byFam.get(r.family).push(r);
  }
  console.log('== PER-FAMILY (max rho, median rho, n) ==');
  const summary = [...byFam.entries()].map(([fam, rs]) => {
    const sorted = [...rs].sort((a, b) => a.rho - b.rho);
    const med = sorted[Math.floor(sorted.length / 2)].rho;
    const max = sorted[sorted.length - 1];
    return { fam, n: rs.length, med, max: max.rho, maxFile: max.sourceFile.replace(/^strategies\//, ''), maxObj: max.objective };
  }).sort((a, b) => b.max - a.max);
  for (const s of summary) {
    console.log(`${s.max.toFixed(4).padStart(7)}  med ${s.med.toFixed(4).padStart(7)}  n=${String(s.n).padStart(3)}  ${s.fam.padEnd(12)}  max by ${s.maxFile} (obj ${s.maxObj == null ? '—' : s.maxObj.toFixed(4)})`);
  }

  // named books the design calls out
  const named = (process.env.CORR_NAMED || 'bba95a11,8dbd994c,a30641fb,b50e4387,73b13d92,1cc495be,914d5724,fd5d388d,7a1c225f,5e874b5b').split(',');
  console.log('');
  console.log('== NAMED IN THE DESIGN ==');
  console.log(head);
  for (const tag of named) {
    const hit = rows.filter(r => r.sourceFile.includes(tag));
    if (!hit.length) { console.log(`   ---   (no epoch-9 TRAIN curve for ${tag})`); continue; }
    for (const r of hit) console.log(fmtRow(r));
  }

  // distribution
  const rhos = rows.map(r => r.rho).filter(v => v != null).sort((a, b) => a - b);
  const q = p => rhos[Math.min(rhos.length - 1, Math.floor(p * rhos.length))];
  console.log('');
  console.log(`== DISTRIBUTION (n=${rhos.length}) == min ${q(0).toFixed(4)} p25 ${q(0.25).toFixed(4)} med ${q(0.5).toFixed(4)} p75 ${q(0.75).toFixed(4)} p95 ${q(0.95).toFixed(4)} max ${q(0.9999).toFixed(4)}`);
  console.log(`   rho>0.8: ${rhos.filter(v => v > 0.8).length}   0.5-0.8: ${rhos.filter(v => v > 0.5 && v <= 0.8).length}   <0.5: ${rhos.filter(v => v <= 0.5).length}`);
  const shortOvl = rows.filter(r => r.rho != null && r.overlapDays < 200);
  console.log(`   overlap < 200 days: ${shortOvl.length}${shortOvl.length ? ' -> ' + shortOvl.slice(0, 8).map(r => r.sourceFile.replace(/^strategies\//, '').slice(0, 40) + ':' + r.overlapDays).join(', ') : ''}`);
}
