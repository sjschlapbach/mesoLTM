#!/usr/bin/env bash
# Stop hook: keep the .ai/ tracking system current.
#
# Fires when the working tree has changes OUTSIDE .ai/ but nothing under
# .ai/ was touched this session, and asks Claude to update the tracking
# docs before finishing. Self-terminating: once .ai/ is updated (or the
# work is committed), the condition is false and Claude stops normally.
set -euo pipefail

repo="${CLAUDE_PROJECT_DIR:-$(pwd)}"
status="$(git -C "$repo" status --porcelain 2>/dev/null || true)"

# Not a git repo, or a clean tree: nothing to enforce.
[ -z "$status" ] && exit 0

# Changes outside the tracking dir (ignore .DS_Store noise).
non_ai="$(printf '%s\n' "$status" | grep -vE '\.ai/|\.DS_Store' | grep -vE '^[[:space:]]*$' || true)"
# Any pending change already under .ai/ ?
ai_touched="$(printf '%s\n' "$status" | grep -E '\.ai/' || true)"

if [ -n "$non_ai" ] && [ -z "$ai_touched" ]; then
  cat <<'JSON'
{"decision":"block","reason":"There are uncommitted changes but the .ai/ tracking system was not updated this session. Per CLAUDE.md, append a dated entry to .ai/PROGRESS.md (and update ARCHITECTURE/DECISIONS/CONVENTIONS if relevant) describing what changed and why, then finish. If the changes genuinely warrant no tracking update, add a one-line note in .ai/PROGRESS.md saying so (or commit the work), then finish."}
JSON
fi
exit 0
