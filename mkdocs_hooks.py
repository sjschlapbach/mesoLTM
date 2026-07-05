"""MkDocs build hooks for the mesoLTM documentation site.

Silences griffe's benign docstring-style warnings so a ``mkdocs build --strict``
build does not abort on them. griffe emits WARNING-level messages for a handful of
plotting/animation helpers whose matplotlib ``ax`` / ``**kwargs`` parameters carry
no type annotation (and for two cosmetic docstring-indentation nits). These do not
affect the rendered reference, but ``--strict`` would otherwise turn them into
failures — masking the link/anchor/nav problems we actually want --strict to catch.

Raising the griffe loggers to ERROR keeps MkDocs' own validation warnings intact.
"""

from __future__ import annotations

import logging

_GRIFFE_LOGGERS = (
    "griffe",
    "mkdocs.plugins.griffe",
    "mkdocs.plugins.mkdocstrings",
    "mkdocs.plugins.mkdocstrings_handlers",
)


def _quiet_griffe() -> None:
    """Raise the griffe/mkdocstrings loggers above WARNING."""
    for name in _GRIFFE_LOGGERS:
        logging.getLogger(name).setLevel(logging.ERROR)


# Set the level as early as the config file is imported, and again on startup so
# it survives any logging reconfiguration MkDocs performs.
_quiet_griffe()


def on_startup(command: str, dirty: bool) -> None:
    """MkDocs lifecycle hook: quiet griffe before the build begins."""
    _quiet_griffe()
