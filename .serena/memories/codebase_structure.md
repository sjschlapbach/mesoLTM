# Codebase Structure

Currently a skeleton — no package code yet.

## Top-level
- `CLAUDE.md` — agent operating manual + working protocol.
- `.ai/` — decision log + progress log only (see `mem:ai_tracking_system`).
- `.serena/` — serena project config (`project.yml`, committed) + these memories.
- `.claude/` — Claude Code settings + hooks.
- `docs/` — reserved for user-facing documentation (not present yet).
- `README.md`, `LICENSE` (MIT), `.gitignore`, `venv/` (git-ignored, Python 3.11.15).

## Planned package layout (create on first code)
`src/` layout, hatchling-built:
- `pyproject.toml` — PEP 621 metadata; deps `numpy`, `scipy`; extras `plot`, `dev`.
- `src/mesoltm/` — the package (import name `mesoltm`).
- `tests/` — pytest suite.

## Likely early modules
Network representation; mesoscopic model core (packet/gas-kinetic dynamics + solver); I/O.
Eventual runtime flow: network + demand input → model integration → traffic-state output.

Keep this current when files/modules are added, moved, or removed.
