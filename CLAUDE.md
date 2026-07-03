# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**mesoLTM** is a **mesoscopic traffic flow model**, distributed as a **pip-installable Python package** (`mesoltm`). Mesoscopic models sit between microscopic (individual vehicles) and macroscopic (continuum density/flow) — typically modelling vehicle groups/packets or gas-kinetic distributions over a road network.

Status: **early development** — the package is being scaffolded; core model code does not exist yet.

## Working protocol (read first, every session)

Project knowledge is split to avoid duplication, and keeping it current is part of every task:

- **serena memories** (`.serena/memories/`, committed) — the reference knowledge: project overview, codebase structure, code style & conventions, suggested commands, tools & skills, task-completion checklist. **Primary source of truth.**
- **`.ai/`** — only the append-only logs: `DECISIONS.md` (decision log) and `PROGRESS.md` (dated changelog). See `.ai/README.md`.
- **This file** — the protocol and pointers only; it deliberately does **not** restate the content above.

**Before starting a task**
1. Read the relevant **serena memories** — use serena's `list_memories` / `read_memory` (or read `.serena/memories/*.md` directly if serena is unavailable). Start with `project_overview`, then `codebase_structure`, `code_style_and_conventions`, `suggested_commands`, `tools_and_skills`.
2. Read `.ai/DECISIONS.md` — decisions/constraints that bind your work.
3. Check `.ai/PROGRESS.md` — in-flight work and recent changes.

**While working** — follow the `code_style_and_conventions` memory; use the tools in `tools_and_skills` (context7 for library docs, serena for code navigation/editing). If you deviate, record why in `.ai/DECISIONS.md`.

**Before finishing a task (definition of done)** — update whichever apply:
- **serena memory** — update `codebase_structure`, `code_style_and_conventions`, or `suggested_commands` (via serena's `write_memory`) if structure, conventions, or commands changed.
- `.ai/DECISIONS.md` — you made a non-obvious or systematic choice.
- `.ai/PROGRESS.md` — **always** append a dated entry summarizing what changed and why.
- Run the `task_completion_checklist` memory (tests, ruff, mypy).

**A stale tracking file is a bug** — fix it in the same task. A `Stop` hook reminds you if work changed but tracking (`.ai/` **or** `.serena/memories/`) wasn't updated.

## Environment (quick reference — full commands in the `suggested_commands` memory)

- Local dev: Python **3.11** venv (currently 3.11.15 via Homebrew). The package targets **3.11+**, so dev and floor match.
- `venv/` is git-ignored; do not commit it.

```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"       # once pyproject.toml exists
```
