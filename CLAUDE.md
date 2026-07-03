# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working protocol (read first, every session)

This repository maintains an **AI tracking system** under `.ai/`. Those files are the persistent, shared memory for coding agents — the fast path to understanding the repo without re-reading everything. Treat them as authoritative and keep them current. Maintaining them is part of every task, not optional bookkeeping. (`.ai/` is agent context; `docs/` is reserved for user-facing documentation.)

**Before starting a task**
1. Read `.ai/ARCHITECTURE.md` — current structure and how things fit together.
2. Read `.ai/CONVENTIONS.md` — coding style and patterns to follow.
3. Skim `.ai/DECISIONS.md` — decisions/constraints that bind your work.
4. Check `.ai/PROGRESS.md` — in-flight work and recent changes.

**While working** — follow the conventions. If you must deviate, record why in `DECISIONS.md`.

**Before finishing a task (definition of done)** — update whichever apply:
- `ARCHITECTURE.md` — you added/moved/removed files or modules, or changed how components relate.
- `DECISIONS.md` — you made a non-obvious or systematic choice (library, pattern, structure, trade-off).
- `CONVENTIONS.md` — you established or changed a coding standard.
- `PROGRESS.md` — **always** append a dated entry summarizing what changed and why.

Keep entries short and factual. **A stale tracking file is a bug** — if a change makes one of these files wrong, fix it in the same task.

## Current state

This repository is a brand-new, essentially empty Python project. It currently contains:

- `CLAUDE.md` — this operating manual.
- `.ai/` — the AI tracking system (see `.ai/README.md`).
- `README.md` — a single-line title (`# mesoLTM`).
- `LICENSE` — MIT, © 2026 Julius Schlapbach.
- `.gitignore` — the stock GitHub Python template, plus `.DS_Store`.
- `venv/` — a local virtual environment (git-ignored).

There is no application/library source, no tests, and no dependency/build configuration yet. When adding the first real code, also add the corresponding tooling (dependency manifest, test runner, lint/format config), record the actual build/test/run commands here, and reflect it in `.ai/`.

## Environment

- Python **3.13** (the checked-out `venv/` was created with 3.13.9 via Homebrew).
- Only `pip` is installed in the venv — no project dependencies yet.
- `venv/` is git-ignored; do not commit it.

```bash
python3.13 -m venv venv       # if venv/ is missing
source venv/bin/activate
```

## Notes

- No dependency manager is chosen yet (no `requirements.txt`, `pyproject.toml`, `Pipfile`, `uv.lock`, etc.). Pick one when introducing dependencies, then record the install command here and in `.ai/CONVENTIONS.md`.
