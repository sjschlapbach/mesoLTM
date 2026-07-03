# AI Tracking System (how project knowledge is split)

To avoid duplicating the same facts in two places, project knowledge is split:

- **Serena memories** (this store, `.serena/memories/`, committed to git) = **reference knowledge**, the single source of truth:
  `mem:project_overview`, `mem:codebase_structure`, `mem:code_style_and_conventions`, `mem:suggested_commands`, `mem:tools_and_skills`, `mem:task_completion_checklist`.
  Read via serena's `read_memory`/`list_memories`, or directly as `.serena/memories/*.md` files if serena is unavailable.

- **`.ai/`** = only what serena memory doesn't hold well — the append-only logs:
  - `.ai/DECISIONS.md` — decision log (newest first) with rationale.
  - `.ai/PROGRESS.md` — dated progress/changelog.
  - `.ai/README.md` — describes this split.

- **`CLAUDE.md`** = the working protocol (auto-loaded each session): what to read before a task and update after. It points here; it does not duplicate the content.

A `Stop` hook (`.claude/hooks/ai-tracking-reminder.sh`) nudges to update tracking when work changes aren't reflected in either `.ai/` or `.serena/memories/`.
