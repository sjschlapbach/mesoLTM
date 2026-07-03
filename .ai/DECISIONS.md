# Decision log

> Append-only record of systematic or non-obvious decisions. **Newest first.** Protocol: see `CLAUDE.md`.
> Format per entry: date — decision — rationale — implications.

## 2026-07-03 — Project scope: mesoscopic traffic flow model as a pip package

- **Decision:** Build a mesoscopic traffic flow model and distribute it as the pip package `mesoltm`.
- **Rationale:** Stated project goal.
- **Implications:** Library-first design (clean public API, packaging discipline), not an application/script.

## 2026-07-03 — Packaging & tooling defaults

- **Decision:** `src/` layout, hatchling build backend, PEP 621 `pyproject.toml`; **Python 3.11+**; core deps `numpy` + `scipy`; `matplotlib` as optional extra `[plot]`; `pytest` + `ruff` + `mypy` (dev extra). See the `code_style_and_conventions` serena memory.
- **Rationale:** Mainstream, low-friction scientific-Python packaging. 3.11+ and numpy+scipy chosen by the maintainer (dev happens in a 3.11 venv, so dev matches the floor).
- **Implications:** Scaffold accordingly on first code. Reversible, but changing the Python floor or build backend later is disruptive.

## 2026-07-03 — Serena is the primary reference store; `.ai/` keeps only logs

- **Decision:** Activated serena for the project (`.serena/project.yml`, `languages: [python, bash]`) and stored reference knowledge as committed serena memories: `project_overview`, `codebase_structure`, `code_style_and_conventions`, `suggested_commands`, `tools_and_skills`, `task_completion_checklist`, `ai_tracking_system`. Removed the now-duplicated `.ai/ARCHITECTURE.md` and `.ai/CONVENTIONS.md`; `.ai/` now holds only `DECISIONS.md` + `PROGRESS.md`. Trimmed `CLAUDE.md` to protocol + pointers.
- **Rationale:** Per user instruction — keep reference facts in serena memory (queryable, single source of truth) and only maintain separately what serena memory doesn't hold well (the append-only logs). Avoids duplicating the same facts in two places.
- **Implications:** Update memories via serena's `write_memory` when structure/conventions/commands change; append the `.ai/` logs for decisions/progress. The Stop hook now treats `.ai/` **or** `.serena/memories/` as a valid tracking update and uses `git status --untracked-files=all` so nested memory paths are detected. `.serena/project.yml` + memories are committed; `.serena/cache` and `project.local.yml` are git-ignored by serena's own `.gitignore`.

## 2026-07-03 — Expand the agent skill set for package development

- **Decision:** Beyond context7/serena/dataviz/verify/code-review/simplify, also use **run** (drive example scripts/CLI), **security-review** (before publishing to PyPI), and **review** (GitHub PRs). `fewer-permission-prompts`, `update-config`, `session-report` are occasional maintenance helpers. All ship with Claude Code and are on by default — no install step; documented in `CLAUDE.md`.
- **Rationale:** Cover the full library lifecycle (navigate → verify → review → security-review → release), which a publicly pip-installable package warrants.
- **Implications:** No config change needed to enable them; they're referenced in `CLAUDE.md` so agents reach for them at the right stage.

## 2026-07-03 — Use context7 + serena MCPs; pre-approve their read-only tools

- **Decision:** Standardize on the **context7 MCP** for library-doc lookup and the **serena MCP** (LSP-backed) for semantic code navigation/editing. Read-only tools of both, plus common Python dev commands, are allow-listed in `.claude/settings.json`. `dataviz`/`verify`/`code-review`/`simplify` skills are the go-to for viz/verification/review.
- **Rationale:** Optimize the repo for agent development — fewer permission prompts, current library docs instead of memory, symbol-level code intelligence.
- **Implications:** Prefer these over ad-hoc web search / text grep. Editing serena tools are intentionally left to prompt. Plugins are assumed enabled at the user level; pin them in `enabledPlugins` if teammates need them guaranteed.

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

## 2026-07-03 — Local dev on Python 3.11 (stdlib `venv`)

- **Decision:** Use a local `venv/` on **Python 3.11** for development (currently 3.11.15 via Homebrew). Initially the venv was 3.13.9; switched to 3.11 so local dev matches the package floor (`requires-python >= 3.11`).
- **Rationale:** Developing on the minimum supported version catches 3.11-incompatible usage early.
- **Implications:** Recreate the venv with `python3.11 -m venv venv`. Keep package `requires-python` at `>=3.11`.
