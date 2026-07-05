# Suggested Commands

Dev environment: **macOS (darwin)**, zsh, BSD userland (not GNU). Local venv is Python 3.11.15.

## Setup
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -e ".[dev,plot]"      # core + dev tooling + plotting
```

## Test / lint / format / type / build
```bash
pytest                            # all tests (discovered under src/mesoltm/tests)
pytest -k regression              # e.g. the abmmeso fidelity regression
pylint src/mesoltm examples       # lint (black owns formatting)
black src examples                # format;  black --check src examples  in CI
mypy src                          # type-check (clean)
python -m build                   # sdist + wheel
```

## Run
```bash
python -m mesoltm examples/scenario.json   # run a JSON scenario -> CSV outputs
python examples/paper_lane_drop.py         # any example script
for f in examples/*.py; do case $(basename "$f") in _*) ;; *) python "$f";; esac; done  # run all (as CI does)
```

## CI
Each gate is its own workflow in `.github/workflows/`: `test.yml` (pytest, 3.11), `lint.yml` (pylint), `format.yml` (black --check), `typecheck.yml` (mypy), `examples.yml` (runs every `examples/*.py`, skipping `_*`, and fails if any errors), `build.yml` (build sdist+wheel on push to master / PR). `release.yml` is the **automated release**: push a `v<MAJOR>.<MINOR>.<PATCH>` tag whose version matches `pyproject.toml` → git-cliff regenerates `CHANGELOG.md` (config `cliff.toml`, conventional commits), the package is built and published to PyPI (`PYPI_TOKEN` secret), the changelog commit is pushed to `master`, and a GitHub Release is created. Preview the next changelog locally with `git-cliff --bump --output CHANGELOG.md` (and `git-cliff --bumped-version`).

Read-only serena/context7 tools and the Python dev commands above are pre-approved in `.claude/settings.json`, so they run without permission prompts. Note: `git worktree` is denied there.
