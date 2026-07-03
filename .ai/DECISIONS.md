# Decision log

> Append-only record of systematic or non-obvious decisions. **Newest first.** Protocol: see `CLAUDE.md`.
> Format per entry: date — decision — rationale — implications.

## 2026-07-03 — Enforce tracking updates with a `Stop` hook

- **Decision:** A `Stop` hook (`.claude/hooks/ai-tracking-reminder.sh`) blocks Claude from finishing when the working tree has changes outside `.ai/` and `.ai/` was not updated, asking it to update the tracking docs (or commit) first.
- **Rationale:** Make "keep `.ai/` current" enforced, not just documented. The check is self-terminating (updating `.ai/` or committing clears it) so it cannot loop.
- **Implications:** Disable/edit via `/hooks` or by removing the `hooks.Stop` entry in `.claude/settings.json`. `.DS_Store` changes are ignored so they don't trigger it.

## 2026-07-03 — Keep agent tracking in `.ai/`, reserve `docs/` for users

- **Decision:** Store the AI tracking system in `.ai/`. `docs/` is reserved for user-facing documentation to be added later.
- **Rationale:** Separate agent context from human documentation so neither clutters the other.
- **Implications:** Do not put agent tracking under `docs/`. `CLAUDE.md` points at `.ai/`.

## 2026-07-03 — Adopt an AI tracking system

- **Decision:** Maintain agent-facing tracking docs (architecture, conventions, decisions, progress) in a dedicated directory, governed by a working protocol in `CLAUDE.md`.
- **Rationale:** Give coding agents persistent, quick-lookup context and enforce keeping it current, avoiding repeated full-repo re-reading and lost decisions.
- **Implications:** Every task must read the relevant files before starting and update them before finishing (see `CLAUDE.md`).

## 2026-07-03 — Python 3.13 with the stdlib `venv`

- **Decision:** Target Python 3.13 and use a local `venv/` for isolation.
- **Rationale:** Matches the environment already checked out (3.13.9).
- **Implications:** No dependency manager, linter, formatter, or test runner chosen yet — record each here when introduced.
