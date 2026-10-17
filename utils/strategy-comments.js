/**
 * strategy-comments.js
 *
 * Top comments for a JoinQuant strategy post, via the `community/post/replyList` API.
 * Returns `[{ user, content, time, isOwner, isBest }]`.
 *
 * ⚠ Rewritten 2026-10-17 to go through `utils/jq-http.js`. It hand-rolled `https.get` with a
 * cookie header read from `data/cookies.json` — the pattern CLAUDE.md forbids by name, because JQ
 * geo-blocks out-of-region requests with an **HTTP 200 HTML** page and the old `catch { resolve([]) }`
 * reported that as "this post has no comments". It also loaded its own cookie file, which jq-http
 * makes unnecessary: the CDP transport reuses the real logged-in session, so there are no
 * credentials to read and nothing to go stale.
 *
 * ⚠ A GeoBlockedError now PROPAGATES. "No comments" and "we could not ask" are different facts and
 * must not share a return value; a caller that genuinely wants to continue without comments should
 * catch it and say so.
 */

const jq = require('./jq-http');

/**
 * @param {string} postId
 * @param {number} [maxComments=3]
 * @returns {Promise<Array<{user:string,content:string,time:string,isOwner:*,isBest:boolean}>>}
 * @throws {GeoBlockedError} when the request leaves mainland China.
 */
async function fetchComments(postId, maxComments = 3) {
  // ⚠ The old version sent a `Referer` header. jq-http takes no `headers` option, so passing one
  // would be silently ignored — worse than not passing it. It is also unnecessary on the CDP
  // path: that fetch runs inside a joinquant.com tab with `credentials: 'include'`, so the
  // request already carries the real origin and session. If replyList ever turns out to need the
  // header, add it to jq-http with the evidence rather than to this call site.
  const url = `https://www.joinquant.com/community/post/replyList?page=1&postId=${postId}`;
  const json = await jq.jqJson(url);

  const replies = (json && json.data && json.data.replyArr) || [];
  return replies
    .filter(r => r.content && r.content.trim().length > 10)
    // Longer comments are likelier to be substantive; the post author's own replies are demoted
    // because they restate the post rather than react to it.
    .sort((a, b) => (b.content.length + (b.isOwner ? -20 : 0))
                  - (a.content.length + (a.isOwner ? -20 : 0)))
    .slice(0, maxComments)
    .map(r => ({
      user: (r.user && r.user.alias) || '匿名用户',
      content: r.content.replace(/@\S+\s*/g, '').trim().slice(0, 150),
      time: (r.addTime || '').slice(0, 10),
      isOwner: r.isOwner,
      isBest: r.isBest === '1',
    }));
}

module.exports = { fetchComments };
