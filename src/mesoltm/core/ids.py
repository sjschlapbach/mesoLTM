# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Identifier type aliases shared across the package.

Link ids are always a plain ``int`` (``BaseLink.link_id: int``), so they need no
alias — code just uses ``int``.

Node ids, by contrast, are **deliberately not constrained to a single type**: the
network builder accepts *any* hashable value as a node identifier and propagates it
unchanged. This is an explicit extensibility point, demonstrated by the shipped
builders themselves — :func:`~mesoltm.network.builders.grid_network` labels nodes
with ``(row, col)`` integer tuples while
:func:`~mesoltm.network.builders.corridor_network` uses strings — and user code may
use its own scheme. ``NodeId`` names that intentionally-general type so every place
a node id flows reads as a deliberate domain concept, not an unresolved
``Hashable``/``object``. The only requirement is hashability (node ids are dict keys
and set members), hence the alias to :class:`~collections.abc.Hashable`.
"""

from __future__ import annotations

from collections.abc import Hashable

# A node identifier: any hashable value (see the module docstring for why this is
# intentionally general rather than a concrete type).
NodeId = Hashable
