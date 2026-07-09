# mesoltm installation

Requires **Python 3.11+**. Runtime dependencies: `numpy`, `networkx`, `tqdm`.

## Install from PyPI

Core install:

```bash
pip install mesoltm
```

Install with plotting/animation support (adds matplotlib):

```bash
pip install "mesoltm[plot]"
```

## Extras

| Extra | Adds | Purpose |
|-------|------|---------|
| `plot` | matplotlib>=3.7 | Plots and animations (`mesoltm.visualizations`) |
| `ui` | netgraph>=4.13 | Optional network editing |
| `calib` | scipy>=1.10 | Calibration examples |
| `dev` | pytest, pylint, black, mypy, build, git-cliff | Development |
| `docs` | mkdocs-material, mkdocstrings[python], griffe | Building the user docs site |

Combine extras: `pip install "mesoltm[plot,dev]"`.

## Editable install from source

```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -e ".[dev,plot]"
pytest        # tests ship inside the package (src/mesoltm/tests)
```

## Notes

- MP4 export needs `ffmpeg` on the PATH; otherwise animations fall back to an
  animated GIF via Pillow (works with matplotlib alone).
- `import mesoltm` does not import matplotlib; only `mesoltm.visualizations` does.
- Verify: `python -c "import mesoltm; print(mesoltm.__version__)"` prints `0.1.0`.
