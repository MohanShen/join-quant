/**
 * strategy-manifest.js
 *
 * Writes a manifest of freshly-fetched strategies to data/fetch-manifest.json.
 * The LLM agent reads this manifest + source files to generate faithful translations.
 */

const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const MANIFEST_FILE = path.join(DATA_DIR, 'fetch-manifest.json');

/**
 * @param {Array<{
 *   postId: string,
 *   backtestId: string,
 *   title: string,
 *   url: string,
 *   sourceFile: string,
 *   stats: object
 * }>} entries
 */
function writeManifest(entries) {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  const records = entries.map(e => ({
    postId: e.postId,
    backtestId: e.backtestId,
    title: e.title,
    url: e.url,
    sourceFile: e.sourceFile,
    stats: e.stats || {},
  }));
  fs.writeFileSync(MANIFEST_FILE, JSON.stringify({ fetchedAt: new Date().toISOString(), entries: records }, null, 2));
  console.log(`[manifest] Wrote ${entries.length} entries to fetch-manifest.json`);
}

function readManifest() {
  if (!fs.existsSync(MANIFEST_FILE)) return null;
  return JSON.parse(fs.readFileSync(MANIFEST_FILE, 'utf8'));
}

module.exports = { writeManifest, readManifest };
