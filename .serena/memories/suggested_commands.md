# Suggested Commands

Dev environment: **macOS (darwin)**, zsh, BSD userland (not GNU). Local venv is Python 3.11.15.

## Setup
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"          # once pyproject.toml exists
```

## Test / lint / type / build
```bash
pytest                            # all tests
pytest tests/test_x.py::test_y    # single test
ruff check .                      # lint
ruff format .                     # format (use --check in CI)
mypy src                          # type-check
python -m build                   # sdist + wheel
```

Read-only serena/context7 tools and the Python dev commands above are pre-approved in `.claude/settings.json`, so they run without permission prompts. Note: `git worktree` is denied there.
