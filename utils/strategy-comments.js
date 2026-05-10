/**
 * strategy-comments.js
 *
 * Fetch top comments for a JoinQuant strategy post via the replyList API.
 * Returns an array of { user, content, time, likes } for the top comments.
 */

const https = require('https');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const COOKIES_FILE = path.join(DATA_DIR, 'cookies.json');

function loadCookies() {
  if (!fs.existsSync(COOKIES_FILE)) return null;
  const auth = JSON.parse(fs.readFileSync(COOKIES_FILE, 'utf8'));
  return (auth.cookies || []).map(c => c.name + '=' + c.value).join('; ');
}

const fs = require('fs');

async function fetchComments(postId, maxComments = 3) {
  const cookies = loadCookies();
  if (!cookies) return [];

  return new Promise((resolve) => {
    const url = `https://www.joinquant.com/community/post/replyList?page=1&postId=${postId}`;
    https.get(url, {
      headers: {
        'Cookie': cookies,
        'User-Agent': 'Mozilla/5.0',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': `https://www.joinquant.com/view/community/detail/${postId}`,
      }
    }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          const replies = json?.data?.replyArr || [];
          // Top comments: sort by content length + time (longer thoughtful comments first)
          const scored = replies
            .filter(r => r.content && r.content.trim().length > 10)
            .sort((a, b) => {
              // Prefer comments with more content (likely more thoughtful)
              // and not from the post author
              const scoreA = a.content.length + (a.isOwner ? -20 : 0);
              const scoreB = b.content.length + (b.isOwner ? -20 : 0);
              return scoreB - scoreA;
            })
            .slice(0, maxComments);

          const result = scored.map(r => ({
            user: r.user?.alias || '匿名用户',
            content: r.content.replace(/@\S+\s*/g, '').trim().slice(0, 150),
            time: r.addTime?.slice(0, 10) || '',
            isOwner: r.isOwner,
            isBest: r.isBest === '1',
          }));
          resolve(result);
        } catch {
          resolve([]);
        }
      });
    }).on('error', () => resolve([]));
  });
}

module.exports = { fetchComments };