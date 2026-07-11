#!/usr/bin/env bash
# Stop hook: require a tracking update when CODE changes.
#
# Tracking = .ai/ (decision + progress logs) and .serena/memories/ (reference
# knowledge). This hook enforces a tracking update ONLY for changes to source
# code (*.py) — in that case it is always required. Changes confined to other
# files (docs, CI, config, ...) should still be reflected in tracking per
# CLAUDE.md, but are deliberately NOT enforced here.
#
# .ai/ is git-ignored, so tracking freshness is detected by file mtime rather
# than `git status` (which never lists ignored files): tracking counts as current
# when some tracking file was modified at least as recently as the newest changed
# code file. Self-terminating: update .ai/ or a serena memory (or commit the
# code) and the condition is false, so Claude stops normally.
set -euo pipefail

repo="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$repo" 2>/dev/null || exit 0

# Seconds-since-epoch mtime for a file: BSD stat (macOS) first, GNU stat as fallback.
mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0; }

status="$(git status --porcelain --untracked-files=all 2>/dev/null || true)"
# Not a git repo, or a clean tree: nothing to enforce.
[ -z "$status" ] && exit 0

# Changed source-code files: strip the "XY " porcelain prefix and any rename
# "old -> new" arrow (keeping the new path), then keep *.py outside the tracking
# stores. Non-code changes leave this empty and the hook stays silent.
code_files="$(printf '%s\n' "$status" | sed 's/^...//; s/.* -> //' | grep -E '\.py$' | grep -vE '^(\.ai/|\.serena/)' || true)"
[ -z "$code_files" ] && exit 0

# Newest mtime among the changed code files.
newest_code=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  m="$(mtime "$f")"
  [ "$m" -gt "$newest_code" ] && newest_code="$m"
done <<< "$code_files"

# Newest mtime among the tracking files.
newest_track=0
for f in .ai/DECISIONS.md .ai/PROGRESS.md .serena/memories/*.md; do
  [ -f "$f" ] || continue
  m="$(mtime "$f")"
  [ "$m" -gt "$newest_track" ] && newest_track="$m"
done

# Tracking touched at least as recently as the newest code change: nothing to do.
[ "$newest_track" -ge "$newest_code" ] && exit 0

cat <<'JSON'
{"decision":"block","reason":"Source code changed but project tracking wasn't updated this session. Per CLAUDE.md: append a dated entry to .ai/PROGRESS.md (always), update the relevant serena memory via write_memory if structure/conventions/commands changed, and add to .ai/DECISIONS.md for notable choices; then finish. (Changes to non-code files are not enforced here, but should still be reflected in tracking per protocol.) If the code change genuinely warrants no tracking update, add a one-line note in .ai/PROGRESS.md saying so (or commit the work), then finish."}
JSON
exit 0
