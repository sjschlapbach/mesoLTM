#!/usr/bin/env bash
# Stop hook: keep the project tracking current.
#
# Tracking = .ai/ (decision + progress logs) and .serena/memories/ (reference
# knowledge). Fires when the working tree has changes OUTSIDE those (and outside
# noise / .serena config) but neither tracking store was touched this session,
# and asks Claude to update tracking before finishing. Self-terminating: once
# .ai/ or a serena memory is updated (or the work is committed), the condition
# is false and Claude stops normally.
set -euo pipefail

repo="${CLAUDE_PROJECT_DIR:-$(pwd)}"
# --untracked-files=all so git lists each untracked file with its full path
# (default collapses untracked dirs, hiding .serena/memories/ vs .serena/ config).
status="$(git -C "$repo" status --porcelain --untracked-files=all 2>/dev/null || true)"

# Not a git repo, or a clean tree: nothing to enforce.
[ -z "$status" ] && exit 0

# Real "work" changes: exclude the tracking stores, .serena config, and .DS_Store noise.
work="$(printf '%s\n' "$status" | grep -vE '\.ai/|\.serena/|\.DS_Store' | grep -vE '^[[:space:]]*$' || true)"
# Any pending change to a tracking store?
tracking_touched="$(printf '%s\n' "$status" | grep -E '\.ai/|\.serena/memories/' || true)"

if [ -n "$work" ] && [ -z "$tracking_touched" ]; then
  cat <<'JSON'
{"decision":"block","reason":"There are uncommitted changes but project tracking was not updated this session. Per CLAUDE.md: append a dated entry to .ai/PROGRESS.md (always), update the relevant serena memory via write_memory if structure/conventions/commands changed, and add to .ai/DECISIONS.md for notable choices; then finish. If the changes genuinely warrant no tracking update, add a one-line note in .ai/PROGRESS.md saying so (or commit the work), then finish."}
JSON
fi
exit 0
