#!/bin/bash
#
# autostudy-interactive.sh — start (or reopen) the auto-STUDY batch in an INTERACTIVE claude
# session with a PINNED session id, so the hourly cron (scripts/autostudy-loop.sh) can resume
# THIS SAME session when the Anthropic quota frees up. Sibling of autoresearch-interactive.sh.
#
# Flow:
#   1. Run this on the study/all branch:  ./scripts/autostudy-interactive.sh
#   2. Inside claude, type:  /run-study     (works study/manifest.json — all normalized strategies)
#   3. When you step away, CLOSE the session (exit/Ctrl-D) so the cron takes over.
#
# Pinned id stored in data/autostudy-session.txt as "<branch>\t<uuid>" (gitignored).
# Flag: --new  force a brand-new session.
#
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$REPO" || { echo "cannot cd to $REPO"; exit 1; }

SID_FILE="$REPO/data/autostudy-session.txt"
mkdir -p "$REPO/data"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
case "$BRANCH" in
  study/*) ;;
  *) echo "Not on a study/* branch (on '$BRANCH'). Create/checkout it first:"; echo "  git checkout -b study/all"; exit 1 ;;
esac

NEW=0; [ "${1:-}" = "--new" ] && NEW=1
SID=""
if [ "$NEW" = "0" ] && [ -f "$SID_FILE" ]; then
  sb="$(cut -f1 "$SID_FILE" 2>/dev/null)"; ss="$(cut -f2 "$SID_FILE" 2>/dev/null)"
  [ "$sb" = "$BRANCH" ] && [ -n "$ss" ] && SID="$ss"
fi

echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│ IMPORTANT: when you're done watching (or it hits the quota limit), CLOSE   │"
echo "│ this session — exit / Ctrl-D. The hourly cron resumes it ONLY once no      │"
echo "│ process is holding it. Leaving the TUI open (even idle) blocks the cron.   │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
if [ -n "$SID" ] && ls "$HOME"/.claude/projects/*/"$SID".jsonl >/dev/null 2>&1; then
  echo "Reopening auto-study session $SID on $BRANCH (auto-continuing the batch)"
  RESUME_MSG="Continue the auto-study batch (you're already running /run-study per study/program.md). Work study/manifest.json in order; disk is ground truth (manifest status + findings.tsv + git). Finish the in-progress strategy, then the next pending one; don't exit until all are done or I say stop. NEVER touch the 2025+ OOS window."
  exec claude --resume "$SID" "$RESUME_MSG"
else
  SID="$(uuidgen | tr 'A-Z' 'a-z')"
  printf '%s\t%s\n' "$BRANCH" "$SID" > "$SID_FILE"
  echo "New auto-study session $SID on $BRANCH"
  echo "→ Inside claude, type:  /run-study   (to begin the batch over all normalized strategies)"
  echo "→ When you step away, CLOSE the session so the cron can take over."
  exec claude --session-id "$SID"
fi
