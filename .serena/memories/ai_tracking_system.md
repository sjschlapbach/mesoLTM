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

A `Stop` hook (`.claude/hooks/ai-tracking-reminder.sh`) enforces a tracking update
when **source code** changes. Its behaviour (reworked 2026-07-11):

- **Scope:** it only enforces for changes to code (`*.py`, outside `.ai/`/`.serena/`).
  When code changes, a tracking update is *always* required. Changes confined to
  non-code files (docs, CI, config, ...) should still be reflected in tracking per
  CLAUDE.md, but are **not** enforced by the hook.
- **Detection by mtime, not `git status`:** `.ai/` is git-ignored (`.gitignore:227`;
  `git ls-files .ai/` is empty), so git never lists `.ai/` edits. The hook therefore
  compares file mtimes — tracking counts as current when some tracking file
  (`.ai/DECISIONS.md`, `.ai/PROGRESS.md`, or a `.serena/memories/*.md`) was modified
  at least as recently as the newest changed code file. So editing `.ai/PROGRESS.md`
  now *does* satisfy the hook (no commit or `.serena/` edit required).
