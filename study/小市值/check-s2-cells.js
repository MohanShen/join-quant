// Checks every §2 row of the 小市值 page splits to 9 cells under tests/family-pages.test.js's rowCells rule.
const fs = require('fs');
const path = require('path');
const rowCells = line => line.replace(/^\||\|$/g, '').split(/(?<!\\)\|/);
const body = fs.readFileSync(path.join(__dirname, '../../wiki/families/小市值.md'), 'utf8');
let inSec = false, n = 0;
const bad = [];
const KIND = new Set(['raw', 'understand', 'improve', '类型', '---', '—']);
const VERDICT = new Set(['adopted', 'rejected', 'informative', '判定', '---', '—']);
for (const line of body.split('\n')) {
  if (/^## 2\./.test(line)) { inSec = true; continue; }
  if (/^## 3\./.test(line)) inSec = false;
  if (!inSec || !line.trim().startsWith('|')) continue;
  n++;
  const c = rowCells(line);
  if (c.length !== 9) { bad.push(`${c.length} cells: ${line.slice(0, 60)}`); continue; }
  if (!KIND.has(c[1].trim()) || !VERDICT.has(c[7].trim())) bad.push(`bad kind/verdict: ${line.slice(0, 60)}`);
}
console.log(`§2 rows=${n} bad=${bad.length}`);
bad.forEach(b => console.log(b));
console.log(`§6 has entry: ${body.includes('[Q q-e9-champ-numstock]')}`);
