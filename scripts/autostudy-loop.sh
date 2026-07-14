#!/bin/bash
#
# autostudy-loop.sh — RESUME the user's auto-STUDY session unattended (batch over all
# normalized strategies). Sibling of autoresearch-loop.sh; same guards, study paths.
#
# Fired hourly by launchd (scripts/com.mohanshen.join-quant-autostudy.plist). Each firing
# resumes the pinned study session (`claude -p --resume <uuid>`) so the batch keeps grinding
# through study/manifest.json across quota resets, until every strategy is `done` or you stop.
#
# Preconditions (exit 0 = clean no-op if any fails): a pinned session for study/* exists and
# isn't held by a live process; CDP Chrome up; JQ budget < USAGE_LIMIT; no other fire running;
# and the SHARED jq-pipeline lock is free (study & research never backtest at the same time).
#
# Env: REPO, USAGE_LIMIT (default 55), JQ_CDP_URL, USE_BYPASS (see autoresearch-loop.sh).
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
USAGE_LIMIT="${USAGE_LIMIT:-55}"
JQ_CDP_URL="${JQ_CDP_URL:-http://localhost:9225}"
LOG_DIR="$REPO/data/autostudy-logs"
LOCK="$REPO/data/autostudy.lock"
PLOCK="$REPO/data/jq-pipeline.lock"   # shared across research+study crons
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_DIR/wrapper.log"; }
cd "$REPO" || { log "FATAL: cannot cd to $REPO"; exit 1; }

# ── Lock: don't overlap a still-running fire ────────────────────────────────
if [ -e "$LOCK" ]; then
  lockpid="$(cat "$LOCK" 2>/dev/null)"
  if [ -n "$lockpid" ] && kill -0 "$lockpid" 2>/dev/null; then log "skip: previous run (pid $lockpid) still active"; exit 0; fi
  log "stale lock (pid ${lockpid:-?}) — clearing"
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK" "$PLOCK"' EXIT

# ── Resolve study branch ────────────────────────────────────────────────────
CUR_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
case "$CUR_BRANCH" in
  study/*) BRANCH="$CUR_BRANCH" ;;
  *) log "skip: not on a study/* branch (on '$CUR_BRANCH'). Start it interactively first (scripts/autostudy-interactive.sh)."; exit 0 ;;
esac

# ── Precheck 0: a pinned study session exists for THIS branch ───────────────
SID_FILE="$REPO/data/autostudy-session.txt"
if [ ! -f "$SID_FILE" ]; then
  log "skip: no data/autostudy-session.txt — start the batch interactively first (scripts/autostudy-interactive.sh)"; exit 0
fi
SID_BRANCH="$(cut -f1 "$SID_FILE" 2>/dev/null)"; SID="$(cut -f2 "$SID_FILE" 2>/dev/null)"
if [ "$SID_BRANCH" != "$BRANCH" ] || [ -z "$SID" ]; then
  log "skip: session file is for '$SID_BRANCH' (uuid ${SID:-none}), not current branch '$BRANCH'"; exit 0
fi
TRANSCRIPT="$(ls -t "$HOME"/.claude/projects/*/"$SID".jsonl 2>/dev/null | head -1)"
if [ -z "$TRANSCRIPT" ]; then log "skip: no transcript yet for session $SID — start it interactively first"; exit 0; fi

# ── Precheck 0b: is a live process holding this session? ────────────────────
HOLDER="$(pgrep -f "$SID" 2>/dev/null | tr '\n' ' ')"
if [ -n "$HOLDER" ]; then
  log "skip: session $SID is held by live claude pid(s) ${HOLDER}. If that's an interactive TUI you left open, CLOSE it to let the cron resume."; exit 0
fi

# ── Precheck 1: CDP Chrome alive ────────────────────────────────────────────
if ! curl -s -m 5 "$JQ_CDP_URL/json/version" >/dev/null 2>&1; then
  log "skip: CDP Chrome not reachable at $JQ_CDP_URL — keep it running to allow backtests"; exit 0
fi

# ── Precheck 2: JQ daily budget not exhausted ───────────────────────────────
BUDGET="$(node utils/jq-budget.js 2>/dev/null)"
USED="$(printf '%s' "$BUDGET" | sed -n 's/.*used=\([0-9]*\).*/\1/p')"
if [ -n "$USED" ] && [ "$USED" -ge "$USAGE_LIMIT" ] 2>/dev/null; then
  log "skip: JQ budget used=${USED}min >= limit=${USAGE_LIMIT}min — wait for daily reset"; exit 0
fi

# ── Shared lock: don't run backtests while the OTHER pipeline (research) runs ─
if [ -e "$PLOCK" ]; then
  pp="$(cat "$PLOCK" 2>/dev/null)"
  if [ -n "$pp" ] && kill -0 "$pp" 2>/dev/null; then log "skip: another JQ pipeline (pid $pp) is running — serialize"; exit 0; fi
fi
echo $$ > "$PLOCK"
log "budget ok (used=${USED:-unknown}min); resuming study session $SID on $BRANCH"

# ── Resume the study session headless ───────────────────────────────────────
PERM_FLAG="--permission-mode acceptEdits"
[ "${USE_BYPASS:-0}" = "1" ] && PERM_FLAG="--dangerously-skip-permissions"

RUN_LOG="$LOG_DIR/run-$(date '+%Y%m%d-%H%M%S').log"
NUDGE="Quota is available again — continue the auto-study batch exactly where you left off (you are already running /run-study per study/program.md). Work study/manifest.json in order: finish the in-progress strategy, mark it done, take the next pending one; do NOT exit until all are done or I say stop. Have the experimenter run the backtester plain with --usage-limit $USAGE_LIMIT (no JQ_USAGE_LIMIT= prefix, no | tail). NEVER touch the 2025+ OOS window. Keep going until the JQ budget (used>=$USAGE_LIMIT) or the Anthropic quota is hit, then STOP at a clean git state with a one-line status (which strategy, how far). Do NOT git commit wiki/ledgers unless asked."

log "resuming claude study session $SID ($PERM_FLAG) → $RUN_LOG"
JQ_USAGE_LIMIT="$USAGE_LIMIT" claude -p --resume "$SID" "$NUDGE" $PERM_FLAG >"$RUN_LOG" 2>&1
rc=$?
tail -n 3 "$RUN_LOG" 2>/dev/null | sed 's/^/    /' | tee -a "$LOG_DIR/wrapper.log" >/dev/null
if [ $rc -ne 0 ]; then log "claude exited rc=$rc (likely rate-limited — next fire retries after quota reset)"; else log "resume complete rc=0"; fi
exit 0
