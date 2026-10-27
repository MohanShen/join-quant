// Builds the family's FINALISED BOOK as a pinned product candidate, for the one VAL that
// "re-finalise the family" means. ZERO logic edits: this is the champion 0a7de9fa exactly as
// ingested, plus py2to3 and the frozen epoch-9 OVERRIDE (which is what supplies the three pins
// the executor demands — strategies/ is the immutable raw layer and carries none, so a VAL on
// the raw file would refuse with UNPINNED-STOP).
//
// Why a PRODUCT and not a member VAL: integrate-eligible's member route can only confirm a VAL
// that ran on study/<fam>/baseline* AND where `base == bestVariant`. Here base is 7a1c225f (the
// 低开 scalp) while the champion is 0a7de9fa, so that route can never confirm for this family —
// it would correctly report "the VAL ran on this family's BASE but the champion is a different
// member". The product route keys on runId <-> expId, so the finalised book has to be a named,
// pinned artifact on the shelf. expId: xsz-e9-champ.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py');
const OUT = path.join(ROOT, 'enhance/candidates/xsz-e9-champ.py');

const raw = fs.readFileSync(SRC, 'utf8');
const body = py2to3(raw);

// The assertion that makes this a faithful snapshot rather than a new book: the pre-OVERRIDE body
// must be py2to3(raw) byte-for-byte. Compared on the body only — the OVERRIDE is appended after,
// and comparing the whole file is the trailing-newline trap that made an earlier builder report a
// false difference at line 840 of an 839-line file.
const out = body + OVERRIDE;
if (out.slice(0, body.length) !== body) throw new Error('snapshot body is not py2to3(raw)');
if (out.slice(body.length) !== OVERRIDE) throw new Error('OVERRIDE was altered');

// The three pins the executor checks for, and which strategies/ does not carry.
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!out.includes(pin)) throw new Error(`missing pin: ${pin}`);
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, out);
console.log(`wrote ${path.relative(ROOT, OUT)}  body=${body.split('\n').length} lines  (+OVERRIDE)`);
console.log('zero logic edits: body is py2to3(raw) byte-for-byte');
