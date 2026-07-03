# Progress log

> One dated entry per task: what changed and why. **Newest first.** Protocol: see `CLAUDE.md`.

## 2026-07-03

- Added a `Stop` hook (`.claude/hooks/ai-tracking-reminder.sh`, wired in `.claude/settings.json`) that nudges Claude to update `.ai/` before finishing whenever the working tree has changes outside `.ai/` that aren't yet reflected there. Self-terminating; recorded as a decision.
- Moved the AI tracking system from `docs/ai/` to `.ai/` so `docs/` stays reserved for user documentation.
- Added a basic `README.md` with usage and virtual-environment setup (placeholder content).
- Set up the AI tracking system: `.ai/{README,ARCHITECTURE,CONVENTIONS,DECISIONS,PROGRESS}.md`.
- Added a working protocol to `CLAUDE.md` requiring these files to be read before and updated after every task.
- Added `.DS_Store` to `.gitignore`.
- Created the initial `CLAUDE.md` describing the (empty) repository state and Python 3.13 environment.
