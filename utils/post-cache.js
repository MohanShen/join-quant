/**
 * post-cache.js — fetch a community post's body ONCE, reuse it everywhere.
 *
 * The problem this removes
 * ------------------------
 * `community/post/detailV2` is one request per post, and three tools wanted the same
 * bodies independently: `screen-prefilter.js` (to screen on substance), `resource-fetch.js`
 * (to save the write-up) and `tutorial-ingest.js`. Nothing remembered a body, so:
 *   - re-running the prefilter re-fetched every unscreened candidate from scratch, and
 *   - a post that was screened AND later ingested as a resource was fetched twice.
 * With ~2,600 posts in the store that is thousands of avoidable requests against a site
 * that already geo-blocks and that we reach over one SSH tunnel.
 *
 * Identity is `uniqueKey`, never `postId` — JoinQuant re-mints postIds on every request,
 * so a postId-keyed cache would miss every time (the same bug the stores had).
 *
 * Bodies are effectively immutable: an old post's text does not change. `maxAgeDays`
 * exists for the rare edited post and defaults to Infinity (never expire); pass a number
 * to force a refresh.
 *
 * The whole detailV2 payload is cached, not just the text: `resource-fetch.js` needs the
 * post's title, addTime, like/collection counts and notebook fields to write its frontmatter,
 * so caching only the body would have left its request in place.
 *
 * Usage:
 *   const cache = require('./post-cache');
 *   const body   = await cache.body(uniqueKey, postId);     // text only
 *   const detail = await cache.detail(uniqueKey, postId);   // full payload
 *   cache.save();                                           // once, at the end
 */

const fs = require('fs');
const path = require('path');
const jq = require('./jq-http');

const ROOT = path.resolve(__dirname, '..');
const FILE = path.join(ROOT, 'data/post-bodies.json');

let _store = null;
let _dirty = false;
const stats = { hits: 0, misses: 0, failures: 0 };

function load() {
  if (_store) return _store;
  try {
    _store = JSON.parse(fs.readFileSync(FILE, 'utf8'));
  } catch {
    _store = { note: 'community post bodies keyed by uniqueKey; see utils/post-cache.js', posts: {} };
  }
  if (!_store.posts) _store.posts = {};
  return _store;
}

function get(key) {
  const s = load();
  return key ? s.posts[key] || null : null;
}

function put(key, postId, data) {
  if (!key) return;
  const s = load();
  // `data` may be a full detailV2 payload or a bare string body.
  const detail = typeof data === 'string' ? { content: data } : (data || {});
  s.posts[key] = {
    content: String(detail.content || ''),
    detail,
    postId,
    fetchedAt: new Date().toISOString(),
  };
  _dirty = true;
}

/**
 * The body for one post: cached if present, otherwise fetched and cached.
 * Returns '' when the post cannot be fetched — callers treat that as "no body",
 * and a failure is NOT cached, so a transient error retries next run.
 *
 * @param {string} key      uniqueKey (stable identity)
 * @param {string} postId   ephemeral id, only used to make the request
 * @param {{maxAgeDays?:number}} [opts]
 * @returns {Promise<string>}
 */
async function detail(key, postId, { maxAgeDays = Infinity } = {}) {
  const hit = get(key);
  if (hit && hit.detail) {
    const ageDays = (Date.now() - Date.parse(hit.fetchedAt)) / 86400000;
    if (!(ageDays > maxAgeDays)) { stats.hits++; return hit.detail; }
  }
  if (!postId) { stats.failures++; return null; }
  try {
    const d = await jq.jqJson(`https://www.joinquant.com/community/post/detailV2?postId=${postId}`);
    if (!d || d.code !== '00000' || !d.data) { stats.failures++; return null; }
    put(key, postId, d.data);
    stats.misses++;
    return d.data;
  } catch {
    stats.failures++;
    return null;
  }
}

/** The post's text, cached or fetched. '' when unavailable. */
async function body(key, postId, opts) {
  const d = await detail(key, postId, opts);
  return d ? String(d.content || '') : '';
}

/** Persist. Cheap to call repeatedly; writes only when something changed. */
function save() {
  if (!_dirty) return false;
  const s = load();
  s.updatedAt = new Date().toISOString();
  fs.mkdirSync(path.dirname(FILE), { recursive: true });
  fs.writeFileSync(FILE, JSON.stringify(s, null, 1));
  _dirty = false;
  return true;
}

/** `hits`/`misses` are cache hits vs network fetches — the saving is `hits`. */
function report() {
  const total = stats.hits + stats.misses + stats.failures;
  return `${stats.hits} cached, ${stats.misses} fetched, ${stats.failures} failed (of ${total})`;
}

function size() { return Object.keys(load().posts).length; }

module.exports = { body, detail, get, put, save, report, size, stats, FILE };
