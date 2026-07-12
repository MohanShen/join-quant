#!/bin/bash
#
# autoresearch-loop.sh — resume the join-quant autoresearch loop unattended.
#
# Fired on a schedule by launchd (see scripts/com.mohanshen.join-quant-autoresearch.plist).
# Solves the "Anthropic per-time-slot usage limit" problem for the AUTORESEARCH pipeline:
# each firing is a cheap poll. When both budgets are available it does real work; when
# either is exhausted it exits quickly, so the next firing after a reset picks up
# automatically. The loop is resumable — state lives in the git branch (current best
# candidate), research/results.tsv, and wiki/experiments — so a fresh `claude -p` continues
# from wherever the last one stopped.
#
# Preconditions the wrapper checks (exits 0 = clean no-op if any fails):
#   1. CDP Chrome reachable at $JQ_CDP_URL — backtests need the logged-in session.
#   2. JQ daily backtest budget not exhausted — used < USAGE_LIMIT. Skipping here avoids
#      burning Anthropic quota on a run that can't backtest anyway.
#   3. Not already running — a lockfile prevents overlapping fires (a backtest can take
#      many minutes; JQ allows max 2 concurrent).
#
# Env overrides:
#   REPO       repo root (default: parent of this script's dir)
#   TAG        research epoch tag; branch research/$TAG must already exist
#              (default: current branch, which must be research/*)
#   USAGE_LIMIT JQ backtest-minute cap (default 55 = free tier only; >60 spends credits)
#   JQ_CDP_URL CDP endpoint (default http://localhost:9225)
#   USE_BYPASS if =1, run claude with --dangerously-skip-permissions instead of relying
#              on the project .claude/settings.json allowlist (use only if a run stalls
#              on an un-allowlisted command)
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
USAGE_LIMIT="${USAGE_LIMIT:-55}"
JQ_CDP_URL="${JQ_CDP_URL:-http://localhost:9225}"
LOG_DIR="$REPO/data/autoresearch-logs"
LOCK="$REPO/data/autoresearch.lock"
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_DIR/wrapper.log"; }

cd "$REPO" || { log "FATAL: cannot cd to $REPO"; exit 1; }

# ── Lock: don't overlap a still-running fire ────────────────────────────────
if [ -e "$LOCK" ]; then
  lockpid="$(cat "$LOCK" 2>/dev/null)"
  if [ -n "$lockpid" ] && kill -0 "$lockpid" 2>/dev/null; then
    log "skip: previous run (pid $lockpid) still active"; exit 0
  fi
  log "stale lock (pid ${lockpid:-?}) — clearing"
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

# ── Resolve research branch ─────────────────────────────────────────────────
CUR_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
TAG="${TAG:-}"
if [ -z "$TAG" ]; then
  case "$CUR_BRANCH" in
    research/*) BRANCH="$CUR_BRANCH" ;;
    *) log "skip: not on a research/* branch (on '$CUR_BRANCH') and TAG unset. Create/checkout an epoch first."; exit 0 ;;
  esac
else
  BRANCH="research/$TAG"
fi
if ! git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  log "skip: branch '$BRANCH' does not exist — create the epoch first (see research/program.md Setup)"; exit 0
fi
if [ "$CUR_BRANCH" != "$BRANCH" ]; then
  git checkout "$BRANCH" >/dev/null 2>&1 || { log "skip: cannot checkout $BRANCH (dirty tree?)"; exit 0; }
fi

# ── Precheck 1: CDP Chrome alive ────────────────────────────────────────────
if ! curl -s -m 5 "$JQ_CDP_URL/json/version" >/dev/null 2>&1; then
  log "skip: CDP Chrome not reachable at $JQ_CDP_URL — keep it running to allow backtests"; exit 0
fi

# ── Precheck 2: JQ daily budget not exhausted ───────────────────────────────
# Read the real budget via the CDP-authenticated helper (plain curl can't — JQ cookies
# are httpOnly in Chrome). If it can't get a reading, proceed and let the pipeline's own
# usage-gate (USAGE-STOP) enforce the limit authoritatively.
BUDGET="$(node utils/jq-budget.js 2>/dev/null)"
USED="$(printf '%s' "$BUDGET" | sed -n 's/.*used=\([0-9]*\).*/\1/p')"
if [ -n "$USED" ] && [ "$USED" -ge "$USAGE_LIMIT" ] 2>/dev/null; then
  log "skip: JQ budget used=${USED}min >= limit=${USAGE_LIMIT}min — wait for daily reset"; exit 0
fi
log "budget ok (used=${USED:-unknown}min < ${USAGE_LIMIT}min); resuming autoresearch on $BRANCH"

# ── Run the loop headless ───────────────────────────────────────────────────
PERM_FLAG="--permission-mode acceptEdits"
[ "${USE_BYPASS:-0}" = "1" ] && PERM_FLAG="--dangerously-skip-permissions"

RUN_LOG="$LOG_DIR/run-$(date '+%Y%m%d-%H%M%S').log"
PROMPT="Resume the join-quant autoresearch loop on the current branch ($BRANCH), following research/program.md and the /run-experiment skill. First read research/program.md, docs/research-schema.md, and research/harness.md. Verify CDP Chrome and JQ budget via the /algorithm/index/statistics API. Then run experiments: mutate from the current branch's best candidate, backtest each window with 'JQ_USAGE_LIMIT=$USAGE_LIMIT node utils/strategy-post-backtest.js', keep/discard by objective(VAL)=annualReturn-maxDrawdown with the Sharpe>=2.5 gate, and record every experiment to research/results.tsv + wiki/experiments/<expId>.md + wiki/log.md. LOOP until the JQ budget is exhausted (used>=$USAGE_LIMIT) or the session/Chrome becomes unavailable, then STOP at a clean git state and print a brief summary. Do NOT git commit wiki changes or results.tsv. Do NOT create a new epoch/branch."

log "launching claude -p ($PERM_FLAG) → $RUN_LOG"
JQ_USAGE_LIMIT="$USAGE_LIMIT" claude -p "$PROMPT" $PERM_FLAG >"$RUN_LOG" 2>&1
rc=$?
tail -n 3 "$RUN_LOG" 2>/dev/null | sed 's/^/    /' | tee -a "$LOG_DIR/wrapper.log" >/dev/null
if [ $rc -ne 0 ]; then
  log "claude exited rc=$rc (likely rate-limited or session expired — next fire retries after reset)"
else
  log "run complete rc=0"
fi
exit 0
