#!/bin/bash
#
# autoresearch-interactive.sh — start (or reopen) the autoresearch loop in an INTERACTIVE
# claude session with a PINNED session id, so the hourly cron (scripts/autoresearch-loop.sh)
# can resume THIS SAME session headless when the Anthropic quota frees up.
#
# Flow:
#   1. Run this on your research/<tag> branch:  ./scripts/autoresearch-interactive.sh
#   2. Inside claude, type:  /run-experiment
#   3. Watch it work. When quota stops it, just leave — the cron resumes this session.
#   4. To come back and watch again, run this script again (it reopens the same session,
#      now including whatever the cron did while you were away).
#
# The pinned id is stored in data/autoresearch-session.txt as "<branch>\t<uuid>" (gitignored).
# Flags:  --new  force a brand-new session (starts a fresh epoch conversation).
#
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$REPO" || { echo "cannot cd to $REPO"; exit 1; }

SID_FILE="$REPO/data/autoresearch-session.txt"
mkdir -p "$REPO/data"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
case "$BRANCH" in
  research/*) ;;
  *) echo "Not on a research/* branch (on '$BRANCH'). Checkout or create your epoch branch first:"; echo "  git checkout -b research/<tag>"; exit 1 ;;
esac

NEW=0; [ "${1:-}" = "--new" ] && NEW=1

SID=""
if [ "$NEW" = "0" ] && [ -f "$SID_FILE" ]; then
  saved_branch="$(cut -f1 "$SID_FILE" 2>/dev/null)"
  saved_sid="$(cut -f2 "$SID_FILE" 2>/dev/null)"
  if [ "$saved_branch" = "$BRANCH" ] && [ -n "$saved_sid" ]; then SID="$saved_sid"; fi
fi

echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│ IMPORTANT: when you're done watching (or it hits the quota limit), CLOSE   │"
echo "│ this session — exit / Ctrl-D. The hourly cron resumes it ONLY once no      │"
echo "│ process is holding it. Leaving the TUI open (even idle) blocks the cron.   │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
if [ -n "$SID" ] && ls "$HOME"/.claude/projects/*/"$SID".jsonl >/dev/null 2>&1; then
  echo "Reopening autoresearch session $SID on $BRANCH"
  echo "(includes any work the cron did while you were away; auto-continuing the loop)"
  # Auto-submit a resume nudge so you don't have to type "continue" — and tell it to rebuild
  # the team, since teammates die with the prior session (they must be re-spawned on resume).
  RESUME_MSG="Continue the autoresearch loop (you're already running /run-experiment). Your teammates from the prior session are gone — re-spawn the four named teammates, reconcile against git + research/results.tsv + research/ideas-queue.json (disk is ground truth, the transcript may be stale), then continue from the real breakpoint. NEVER touch the 2025+ OOS window. Keep going until I say stop or a budget/quota limit hits."
  exec claude --resume "$SID" "$RESUME_MSG"
else
  SID="$(uuidgen | tr 'A-Z' 'a-z')"
  printf '%s\t%s\n' "$BRANCH" "$SID" > "$SID_FILE"
  echo "New autoresearch session $SID on $BRANCH"
  echo "→ Inside claude, type:  /run-experiment   (to begin the epoch)"
  echo "→ When you stop watching, CLOSE the session so the cron can take over."
  exec claude --session-id "$SID"
fi
