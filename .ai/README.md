# .ai — AI tracking system

Persistent, agent-maintained context for this repository, optimized for quick lookup by coding agents (especially Claude Code). The **operating protocol** lives in the repo-root `CLAUDE.md`; this directory holds the content it points to.

> Note: this is **agent tracking**, distinct from `docs/` (reserved for user-facing documentation).

## Files

| File | Purpose | Read when | Update when |
|------|---------|-----------|-------------|
| `ARCHITECTURE.md` | Repository structure and how components fit together — the map. | Starting any task. | Files/modules added, moved, removed, or reorganized. |
| `CONVENTIONS.md` | Coding style, patterns, tooling standards. | Writing or changing code. | A standard is set or changed. |
| `DECISIONS.md` | Append-only log of systematic/non-obvious decisions + rationale. | Before making a structural choice. | You make such a choice (or deviate from a convention). |
| `PROGRESS.md` | Dated log of what changed each task and why. | Checking recent/in-flight work. | **Every task** (append an entry). |

## Rules

1. Read the relevant files **before** starting a task.
2. Update them **before** finishing (see the "definition of done" in `CLAUDE.md`).
3. Keep entries short and factual — this is a quick-lookup index, not prose.
4. These files are the source of truth for agent context. If one contradicts the code, reconcile it in the same task; **a stale file is a bug**.
