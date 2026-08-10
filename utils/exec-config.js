/**
 * exec-config.js — single source of truth for WHERE the CDP Chrome lives.
 *
 * Two execution modes, selected by `JQ_EXEC_MODE` (env or config/exec.env):
 *
 *   local  (default) — Chrome runs on this machine at JQ_CDP_PORT.
 *                      Falling back to a locally-launched persistent-profile
 *                      browser is allowed (the old behaviour).
 *
 *   remote           — Chrome runs on the Windows QMT server, bound to the
 *                      server's 127.0.0.1 (NOT reachable over the network).
 *                      We reach it through an SSH tunnel:
 *                          localhost:<JQ_CDP_PORT>  ->  server 127.0.0.1:<JQ_REMOTE_CDP_PORT>
 *                      so every existing `connectOverCDP(localhost:9225)` call
 *                      keeps working unchanged. A local browser fallback is
 *                      DISABLED in this mode: the logged-in JoinQuant session
 *                      lives in the server's Chrome profile, so launching a
 *                      browser here would only hit the CAPTCHA.
 *
 * Config precedence: process.env  >  config/exec.env  >  built-in default.
 * The config file is gitignored (it holds the server host); config/exec.env.example
 * is the tracked template.
 *
 * Nothing here throws — callers get a result object and decide what to do.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const { spawnSync } = require('child_process');

const REPO_ROOT = path.join(__dirname, '..');
const CONF_FILE = process.env.JQ_EXEC_ENV || path.join(REPO_ROOT, 'config', 'exec.env');
const TUNNEL_SH = path.join(REPO_ROOT, 'scripts', 'cdp-tunnel.sh');

/** Parse a trivial KEY=VALUE env file. Supports #comments, quotes, $HOME and ~. */
function loadConfFile(file) {
  const out = {};
  let text;
  try { text = fs.readFileSync(file, 'utf8'); } catch { return out; }
  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    const quoted = /^["']/.test(val);
    if (quoted) {
      val = val.replace(/^(["'])(.*)\1\s*(#.*)?$/, '$2');
    } else {
      val = val.replace(/\s+#.*$/, '');            // strip inline comment when unquoted
    }
    val = val.replace(/\$HOME/g, os.homedir()).replace(/^~(?=\/)/, os.homedir());
    out[key] = val;
  }
  return out;
}

const conf = loadConfFile(CONF_FILE);

/** env wins over file wins over default. */
function get(name, dflt) {
  const v = process.env[name] !== undefined && process.env[name] !== ''
    ? process.env[name]
    : conf[name];
  return v === undefined || v === '' ? dflt : v;
}

const MODE        = String(get('JQ_EXEC_MODE', 'local')).toLowerCase();
const LOCAL_PORT  = Number(get('JQ_CDP_PORT', '9225'));
const REMOTE_PORT = Number(get('JQ_REMOTE_CDP_PORT', String(LOCAL_PORT)));
const SSH_HOST    = get('JQ_REMOTE_SSH_HOST', '');

const isRemote = () => MODE === 'remote';

/**
 * The URL every caller should hand to `chromium.connectOverCDP()`.
 * In remote mode this is still a localhost URL — the SSH tunnel makes the
 * server's Chrome appear local, which also keeps Chrome's Host-header check
 * happy (it rejects non-localhost/non-IP Host values).
 */
function cdpUrl() {
  const explicit = process.env.JQ_CDP_URL || conf.JQ_CDP_URL;
  if (explicit) return explicit.replace(/\/+$/, '');
  return `http://localhost:${LOCAL_PORT}`;
}

/** Launching a local browser as a fallback only makes sense in local mode. */
const allowLocalFallback = () => !isRemote();

/** GET <cdpUrl>/json/version — resolves true when a CDP endpoint answers. */
function probe(timeoutMs = 4000) {
  return new Promise(resolve => {
    let done = false;
    const finish = v => { if (!done) { done = true; resolve(v); } };
    let req;
    try {
      req = http.get(`${cdpUrl()}/json/version`, res => {
        res.resume();
        finish(res.statusCode === 200);
      });
    } catch { return finish(false); }
    req.on('error', () => finish(false));
    req.setTimeout(timeoutMs, () => { req.destroy(); finish(false); });
  });
}

/** Bring the SSH tunnel up via scripts/cdp-tunnel.sh (remote mode only). */
function startTunnel() {
  if (!fs.existsSync(TUNNEL_SH)) return { ok: false, error: `missing ${TUNNEL_SH}` };
  const r = spawnSync('bash', [TUNNEL_SH, 'up'], { encoding: 'utf8', timeout: 45000 });
  const out = `${r.stdout || ''}${r.stderr || ''}`.trim();
  return { ok: r.status === 0, error: r.status === 0 ? undefined : out || `exit ${r.status}` };
}

/**
 * Make the CDP endpoint reachable, then report on it.
 *
 * local mode  — just probes; the user is responsible for their own Chrome.
 * remote mode — probes, and if nothing answers, opens the SSH tunnel and
 *               probes again. This is what makes the remote path need no
 *               manual setup step.
 *
 * @returns {Promise<{ok:boolean, url:string, mode:string, tunnelStarted:boolean, error?:string}>}
 */
async function ensureCdp({ quiet = false } = {}) {
  const url = cdpUrl();
  const base = { url, mode: MODE, tunnelStarted: false };
  const log = m => { if (!quiet) console.log(m); };

  if (await probe()) return { ...base, ok: true };

  if (!isRemote()) {
    return { ...base, ok: false, error: `no CDP endpoint at ${url} (local mode — is Chrome running?)` };
  }

  if (!SSH_HOST) {
    return { ...base, ok: false, error: 'JQ_EXEC_MODE=remote but JQ_REMOTE_SSH_HOST is unset (see config/exec.env.example)' };
  }

  log(`[cdp] remote mode — opening SSH tunnel localhost:${LOCAL_PORT} -> ${SSH_HOST} 127.0.0.1:${REMOTE_PORT}`);
  const t = startTunnel();
  if (!t.ok) return { ...base, ok: false, error: `tunnel failed: ${t.error}` };

  if (await probe()) {
    log('[cdp] ✅ tunnel up');
    return { ...base, ok: true, tunnelStarted: true };
  }
  return { ...base, ok: false, tunnelStarted: true, error: `tunnel opened but no CDP endpoint at ${url}` };
}

/**
 * Synchronous twin of ensureCdp(), for the sync call sites (normalize-daily).
 * Uses curl rather than the http module because there is no sync http client.
 * @returns {{ok:boolean, url:string, mode:string, error?:string}}
 */
function ensureCdpSync() {
  const url = cdpUrl();
  const alive = () =>
    spawnSync('curl', ['-s', '-m', '4', `${url}/json/version`], { stdio: 'ignore' }).status === 0;

  if (alive()) return { ok: true, url, mode: MODE };
  if (!isRemote()) return { ok: false, url, mode: MODE, error: `no CDP endpoint at ${url}` };
  if (!SSH_HOST) return { ok: false, url, mode: MODE, error: 'JQ_REMOTE_SSH_HOST unset' };

  const t = startTunnel();
  if (!t.ok) return { ok: false, url, mode: MODE, error: `tunnel failed: ${t.error}` };
  return alive()
    ? { ok: true, url, mode: MODE }
    : { ok: false, url, mode: MODE, error: `tunnel opened but no CDP endpoint at ${url}` };
}

/** One-line human description, for logs. */
function describe() {
  return isRemote()
    ? `remote (${SSH_HOST || '<no host>'} 127.0.0.1:${REMOTE_PORT} via tunnel -> ${cdpUrl()})`
    : `local (${cdpUrl()})`;
}

module.exports = {
  MODE, LOCAL_PORT, REMOTE_PORT, SSH_HOST,
  isRemote, cdpUrl, allowLocalFallback, probe, ensureCdp, ensureCdpSync, describe,
};
