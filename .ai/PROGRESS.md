# Progress log

> One dated entry per task: what changed and why. **Newest first.** Protocol: see `CLAUDE.md`.

## 2026-07-03

- Set up serena: activated the `mesoLTM` project, set `.serena/project.yml` `languages: [python, bash]`, and wrote 7 onboarding memories (overview, structure, conventions, commands, tools, checklist, tracking-system).
- Made serena memory the **primary reference store** (per "only maintain separately what serena memory doesn't hold"): removed `.ai/ARCHITECTURE.md` + `.ai/CONVENTIONS.md` (migrated into memories), slimmed `CLAUDE.md` to protocol + pointers, rewrote `.ai/README.md`. Broadened the Stop hook to accept `.serena/memories/` updates and use `--untracked-files=all`.
- Switched local dev to **Python 3.11** (venv now 3.11.15); updated all version references in `CLAUDE.md`, `README.md`, `.ai/ARCHITECTURE.md`, `.ai/CONVENTIONS.md`, `.ai/DECISIONS.md`. Dev now matches the package floor (3.11+).
- Documented additional Claude Code skills for the package lifecycle (`run`, `security-review`, `review`, plus maintenance helpers) in `CLAUDE.md` and `.ai/DECISIONS.md`.
- Defined the project (mesoscopic traffic flow model → pip package `mesoltm`) and recorded packaging/tooling defaults (src layout, hatchling, Python 3.11+, numpy+scipy, pytest/ruff/mypy) in `CLAUDE.md`, `.ai/ARCHITECTURE.md`, `.ai/CONVENTIONS.md`, `.ai/DECISIONS.md`.
- Surveyed available skills/MCPs and standardized on context7 (docs) + serena (code intelligence); allow-listed their read-only tools and common Python dev commands in `.claude/settings.json` (24 allow rules) to reduce permission prompts.
- Added a `Stop` hook (`.claude/hooks/ai-tracking-reminder.sh`, wired in `.claude/settings.json`) that nudges Claude to update `.ai/` before finishing whenever the working tree has changes outside `.ai/` that aren't yet reflected there. Self-terminating; recorded as a decision.
- Moved the AI tracking system from `docs/ai/` to `.ai/` so `docs/` stays reserved for user documentation.
- Added a basic `README.md` with usage and virtual-environment setup (placeholder content).
- Set up the AI tracking system: `.ai/{README,ARCHITECTURE,CONVENTIONS,DECISIONS,PROGRESS}.md`.
- Added a working protocol to `CLAUDE.md` requiring these files to be read before and updated after every task.
- Added `.DS_Store` to `.gitignore`.
- Created the initial `CLAUDE.md` describing the (empty) repository state and Python 3.13 environment.
