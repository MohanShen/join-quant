#!/bin/bash
# cdp-tunnel.sh — manage the SSH tunnel to the remote QMT server's CDP Chrome.
#
# The server's Chrome is started with --remote-debugging-address=127.0.0.1, so the
# debug port is NOT reachable over the network (by design — an open CDP port is a
# full remote-control channel for a logged-in brokerage/JoinQuant session). This
# script forwards it over SSH instead:
#
#     localhost:$JQ_CDP_PORT  ->  server 127.0.0.1:$JQ_REMOTE_CDP_PORT
#
# so the repo's existing `connectOverCDP('http://localhost:9225')` calls work
# unchanged against the remote browser.
#
# Usage:
#   ./scripts/cdp-tunnel.sh up       # open (idempotent)
#   ./scripts/cdp-tunnel.sh down     # close
#   ./scripts/cdp-tunnel.sh status   # report
#
# Config: config/exec.env (see config/exec.env.example). Env vars override it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONF="${JQ_EXEC_ENV:-$REPO_ROOT/config/exec.env}"

# Precedence must match utils/exec-config.js: env > config file > default.
# `source` would let the file clobber the environment (the opposite), so stash
# any pre-set env values first and restore them afterwards.
JQ_VARS="JQ_EXEC_MODE JQ_CDP_PORT JQ_REMOTE_CDP_PORT JQ_REMOTE_SSH_HOST JQ_REMOTE_SSH_OPTS"
for _v in $JQ_VARS; do eval "_pre_$_v=\${$_v-}"; done
if [ -f "$CONF" ]; then
  # shellcheck disable=SC1090
  source "$CONF"
fi
for _v in $JQ_VARS; do
  eval "_p=\${_pre_$_v}"
  [ -n "${_p:-}" ] && eval "$_v=\$_p"
done
unset _v _p

LOCAL_PORT="${JQ_CDP_PORT:-9225}"
REMOTE_PORT="${JQ_REMOTE_CDP_PORT:-$LOCAL_PORT}"
SSH_HOST="${JQ_REMOTE_SSH_HOST:-}"
SSH_OPTS="${JQ_REMOTE_SSH_OPTS:-}"

# Matches only OUR forward, so `down` can never kill an unrelated ssh session.
FWD_SPEC="${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}"

port_open()  { nc -z -G 2 127.0.0.1 "$LOCAL_PORT" >/dev/null 2>&1; }
cdp_alive()  { curl -s -m 4 "http://localhost:${LOCAL_PORT}/json/version" >/dev/null 2>&1; }
tunnel_pids() { pgrep -f "ssh.*-L ${FWD_SPEC}" 2>/dev/null || true; }

require_host() {
  if [ -z "$SSH_HOST" ]; then
    echo "JQ_REMOTE_SSH_HOST not set — copy config/exec.env.example to config/exec.env and fill it in." >&2
    exit 1
  fi
}

case "${1:-status}" in
  up)
    if cdp_alive; then
      echo "CDP already reachable at http://localhost:${LOCAL_PORT} (tunnel pids: $(tunnel_pids | tr '\n' ' '))"
      exit 0
    fi
    if [ "${JQ_EXEC_MODE:-local}" != "remote" ]; then
      # local mode: there is nothing to tunnel — the user's own Chrome should be serving
      # this port. Report plainly instead of attempting a pointless SSH connection.
      echo "local mode: no CDP at http://localhost:${LOCAL_PORT} — start Chrome with --remote-debugging-port=${LOCAL_PORT}" >&2
      exit 1
    fi
    if port_open; then
      # Something holds the port but isn't answering CDP — don't stack a second forward.
      echo "port ${LOCAL_PORT} is in use but not answering /json/version — free it first (./scripts/cdp-tunnel.sh down)" >&2
      exit 1
    fi
    require_host
    # -f background, -N no command, ExitOnForwardFailure so a bind clash fails loudly
    # rather than leaving a live-but-useless ssh. Keepalives survive an idle NAT.
    # shellcheck disable=SC2086
    ssh $SSH_OPTS \
      -f -N \
      -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=30 \
      -o ServerAliveCountMax=3 \
      -o ConnectTimeout=15 \
      -L "$FWD_SPEC" \
      "$SSH_HOST"
    for _ in $(seq 1 20); do
      cdp_alive && { echo "tunnel up: localhost:${LOCAL_PORT} -> ${SSH_HOST} 127.0.0.1:${REMOTE_PORT}"; exit 0; }
      sleep 0.5
    done
    echo "tunnel process started but CDP did not answer at http://localhost:${LOCAL_PORT}" >&2
    echo "  -> is Chrome running on the server with --remote-debugging-port=${REMOTE_PORT}?" >&2
    exit 1
    ;;

  down)
    pids="$(tunnel_pids)"
    if [ -z "$pids" ]; then echo "no tunnel running for ${FWD_SPEC}"; exit 0; fi
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.5
    echo "tunnel closed (pids: $(echo $pids | tr '\n' ' '))"
    ;;

  status)
    pids="$(tunnel_pids)"
    echo "mode        : ${JQ_EXEC_MODE:-local}"
    echo "forward     : ${FWD_SPEC}${SSH_HOST:+  -> $SSH_HOST}"
    echo "tunnel pids : ${pids:-none}"
    if cdp_alive; then
      echo "cdp         : OK  $(curl -s -m 4 "http://localhost:${LOCAL_PORT}/json/version" | tr -d '\n')"
    else
      echo "cdp         : unreachable at http://localhost:${LOCAL_PORT}"
      exit 1
    fi
    ;;

  *)
    echo "usage: $0 {up|down|status}" >&2
    exit 2
    ;;
esac
