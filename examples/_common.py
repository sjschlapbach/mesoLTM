"""Small helpers shared by the example scripts (figure output)."""

from __future__ import annotations

import pathlib

OUTPUT_DIR = pathlib.Path(__file__).parent / "output"


def savefig(fig, name: str, subdir: str | None = None) -> str:
    """Save a matplotlib figure under the examples ``output/`` directory.

    Args:
        fig: The matplotlib figure to save.
        name: File name (a ``.png`` is added if missing).
        subdir: Optional sub-directory of ``output/`` to write into — pass each
            script's own name (e.g. ``pathlib.Path(__file__).stem``) so every
            example's figures land in their own folder and are easy to tell apart.

    Returns:
        The path the figure was written to, as a string.
    """
    out = OUTPUT_DIR if subdir is None else OUTPUT_DIR / subdir
    out.mkdir(parents=True, exist_ok=True)
    if not name.endswith(".png"):
        name += ".png"
    path = out / name
    fig.savefig(path, dpi=120, bbox_inches="tight")
    return str(path)
