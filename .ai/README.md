# .ai — decision & progress logs

This directory holds only the parts of the project's agent-facing knowledge that are **not** stored as serena memories: the append-only logs.

- `DECISIONS.md` — decision log (newest first): systematic/non-obvious choices + rationale.
- `PROGRESS.md` — dated progress/changelog: what changed each task and why.

## What's NOT here — it lives in serena memory

Reference knowledge — project overview, codebase structure, code style/conventions, suggested commands, tools & skills, task-completion checklist — lives in **serena memories** (`.serena/memories/`, committed to git). Read them via serena's `read_memory` / `list_memories`, or directly as `.serena/memories/*.md` files if serena is unavailable. This split avoids maintaining the same facts in two places. See the `ai_tracking_system` memory for the full picture.

## Rules

1. **Before a task:** read the relevant serena memories + these logs (see `CLAUDE.md`).
2. **Before finishing:** append to `PROGRESS.md` (always); add to `DECISIONS.md` for notable choices; update the relevant serena memory if reference facts changed.
3. Keep entries short and factual. A stale entry (here or in a memory) is a bug — fix it in the same task.
