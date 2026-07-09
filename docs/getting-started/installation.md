# Installation

`mesoltm` requires **Python 3.11 or newer**. Its only runtime dependencies are
[NumPy](https://numpy.org/), [NetworkX](https://networkx.org/) and
[tqdm](https://tqdm.github.io/) (for the optional simulation progress bar).

## From PyPI

```bash
pip install mesoltm
```

For plots and movement animations, add the `plot` extra (pulls in matplotlib):

```bash
pip install "mesoltm[plot]"
```

## Extras

| Extra | Adds | For |
|-------|------|-----|
| `plot` | `matplotlib` | Plots and animations (`mesoltm.visualizations`) |
| `ui` | `netgraph` | Optional interactive network editing |
| `calib` | `scipy` | Calibration examples |
| `dev` | `pytest`, `pylint`, `black`, `mypy`, `build`, `git-cliff` | Development |
| `docs` | `mkdocs-material`, `mkdocstrings[python]` | Building this documentation |

Combine them as needed, e.g. `pip install "mesoltm[plot,dev]"`.

!!! note "Video export needs ffmpeg"
    MP4 export in [Movement animations](../guide/animations.md) calls out to
    [`ffmpeg`](https://ffmpeg.org/); if it is not on your `PATH`, animations fall
    back to an animated **GIF** via Pillow. GIFs work with matplotlib alone.

## From source (editable, for development)

```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -e ".[dev,plot]"     # core + dev tooling + plotting
```

The test suite ships inside the package; verify your install with:

```bash
pytest
```

## Check it works

```python
import mesoltm as m
print(m.__version__)
```
