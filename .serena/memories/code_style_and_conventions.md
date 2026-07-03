# Code Style & Conventions

- **Python 3.11+** for the published package (`requires-python = ">=3.11"`); dev in the 3.11 venv.
- **Packaging:** PEP 621 `pyproject.toml`, **hatchling** backend, **`src/` layout** (`src/mesoltm/`). Distribution + import name: `mesoltm`.
- **Runtime deps:** `numpy`, `scipy`. `matplotlib` is an **optional extra** (`mesoltm[plot]`) — never import it at the top level of core modules; import it lazily inside plotting functions.
- **Dev deps** via `[dev]` extra: `pytest`, `ruff`, `mypy`, `build`.
- **Type hints:** required on public functions/classes/module boundaries; keep `mypy`-clean.
- **Numerics:** prefer vectorized NumPy over Python loops on hot paths; explicit dtypes/shapes. Reach for `scipy` (integration, optimization, sparse) before hand-rolling.
- Keep `import mesoltm` cheap — no heavy imports at import time.
- Export the intended public API explicitly from `src/mesoltm/__init__.py`.
- **Docstrings:** NumPy-style on public API; comments explain *why*, not *what*.
- **Lint + format:** `ruff` (both). **Types:** `mypy` on `src/`.

Refine module-boundary/naming specifics in `mem:codebase_structure` as the package grows.
