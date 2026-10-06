#!/usr/bin/env bash
# daily-pipeline.sh — cron entry point for the one-a-day pipeline.
#
# Drains the funnel — research (/run-family) > assign > normalize > discover+fetch — CHAINING
# stages while budget remains, and leaves enough on disk to resume tomorrow. All of the decision
# logic lives in utils/daily-pipeline.js; this wrapper only owns the things a cron must own:
# a lock, the shared pipeline lock, the CDP tunnel, and a log.
#
# ⚠ It chains, up to 6 stages per fire. A 2026-09-22 run took six families in one go; a
# 2026-09-26 run spent 143 backtest-minutes on normalize alone. "One stage a day" was the old
# shape and is no longer true.
#
# ⚠ It takes the SHARED jq-pipeline lock, because only one thing may spend JoinQuant backtest
# minutes at a time — two concurrent consumers produce two half-finished runs rather than one
# finished one. The autostudy/autoenhance crons take the same lock, but neither is loaded any
# more: the funnel's research stage replaced them (they stay reachable via --stage).
#
# ⚠ Exit codes are load-bearing. The node planner exits 1 when a stage is BLOCKED (for example
# an agent loop whose pinned session is on another branch), so a silent daily no-op shows up as
# a failing cron instead of a green one. Do not "fix" that by swallowing the code.
#
# Env: REPO, USAGE_LIMIT (default 55; the plist sets 170 for the VIP 180-minute tier),
#      SLOW_SKIP_MIN (default 30; plist sets 45), STAGE (force one stage), DRY (1 = plan only).
#
# ⚠ USAGE_LIMIT stops new backtests STARTING; one already running is left to finish and keeps
# billing. So the real ceiling is USAGE_LIMIT + SLOW_SKIP_MIN.
#
# The plist now sets USAGE_LIMIT=free, which resolves to JQ's OWN reported tier
# (utils/usage-limit.js). That is deliberate: setting it BELOW the tier to protect the tier is
# what stranded the tail — 2026-10-06 stopped at used=141 with 39 free minutes and 21 strategies
# pending, because nothing may START once used >= limit. The rule now is "stop only once usage is
# past the tier", and the in-flight run carries the small overshoot (2026-09-26 ended on 193).
# A plain number still works and still means what it did: USAGE_LIMIT=135 for strict safety.
#
# Install (launchd, mirroring the existing loops):
#   cp scripts/com.mohanshen.join-quant-daily.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.mohanshen.join-quant-daily.plist

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
USAGE_LIMIT="${USAGE_LIMIT:-55}"
LOG_DIR="$REPO/data/daily-logs"
LOCK="$REPO/data/daily-pipeline.lock"
PLOCK="$REPO/data/jq-pipeline.lock"
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_DIR/wrapper.log"; }
cd "$REPO" || { log "FATAL: cannot cd to $REPO"; exit 1; }

# ── Scheduled-hour gate (UTC) ───────────────────────────────────────────────
# The job is meant to start at a fixed UTC hour, but launchd evaluates
# StartCalendarInterval in the machine's LOCAL timezone — America/Los_Angeles here, which
# observes DST. A fixed local hour would therefore drift by one hour twice a year. So the
# plist fires at BOTH candidate local hours and this gate keeps only the one that is really
# DAILY_RUN_HOUR_UTC; the other exits in milliseconds.
#
# The gate applies ONLY to scheduled fires (the plist sets DAILY_SCHEDULED=1). A human
# running this script by hand is never blocked by the clock.
RUN_HOUR_UTC="${DAILY_RUN_HOUR_UTC:-18}"
if [ "${DAILY_SCHEDULED:-0}" = "1" ] && [ "${FORCE:-0}" != "1" ]; then
  NOW_UTC_H="$(date -u +%H)"
  if [ "$NOW_UTC_H" != "$(printf '%02d' "$RUN_HOUR_UTC")" ]; then
    log "skip: scheduled fire at ${NOW_UTC_H}:00 UTC, want ${RUN_HOUR_UTC}:00 UTC (DST-safe gate)"
    exit 0
  fi
  log "scheduled fire at ${NOW_UTC_H}:00 UTC — this is the ${RUN_HOUR_UTC}:00 UTC slot"
fi

# ── Lock: never overlap our own previous fire ───────────────────────────────
if [ -e "$LOCK" ]; then
  lockpid="$(cat "$LOCK" 2>/dev/null)"
  if [ -n "$lockpid" ] && kill -0 "$lockpid" 2>/dev/null; then
    log "skip: previous daily run (pid $lockpid) still active"; exit 0
  fi
  log "stale lock (pid ${lockpid:-?}) — clearing"
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK" "$PLOCK"' EXIT

# ── Shared pipeline lock: only one JQ backtest consumer at a time ───────────
if [ -e "$PLOCK" ]; then
  ppid="$(cat "$PLOCK" 2>/dev/null)"
  if [ -n "$ppid" ] && kill -0 "$ppid" 2>/dev/null; then
    log "skip: another JQ pipeline (pid $ppid) holds the shared lock"; exit 0
  fi
  log "stale shared lock (pid ${ppid:-?}) — clearing"
fi
echo $$ > "$PLOCK"
# Children (autostudy-loop.sh / autoenhance-loop.sh) want the same shared lock. Tell them we
# already hold it on their behalf, or each nested dispatch would see it held, skip, exit 0 —
# and the planner would record "ran" for work that never started.
export JQ_PIPELINE_LOCK_HELD=1

# ── CDP: everything downstream needs the logged-in browser ──────────────────
# In remote mode exec-config opens the SSH tunnel on demand; this only reports.
BUDGET="$(node utils/jq-budget.js 2>/dev/null || true)"
if ! echo "$BUDGET" | grep -q 'used=[0-9]'; then
  log "skip: CDP/budget unavailable ($BUDGET) — is the logged-in Chrome up? ./scripts/cdp-tunnel.sh status"
  exit 0
fi
log "budget: $BUDGET"

# ── Run ─────────────────────────────────────────────────────────────────────
RUN_LOG="$LOG_DIR/$(date '+%Y-%m-%d_%H%M%S').log"
ARGS=()
[ -n "${STAGE:-}" ] && ARGS+=(--stage "$STAGE")
[ "${DRY:-0}" = "1" ] && ARGS+=(--plan)

log "running: node utils/daily-pipeline.js ${ARGS[*]:-} (log $RUN_LOG)"
USAGE_LIMIT="$USAGE_LIMIT" node utils/daily-pipeline.js "${ARGS[@]:-}" >"$RUN_LOG" 2>&1
RC=$?

tail -n 12 "$RUN_LOG" | while IFS= read -r line; do log "  $line"; done
log "exit=$RC"
exit $RC
