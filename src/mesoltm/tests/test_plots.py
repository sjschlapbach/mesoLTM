# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Tests for the static network/flow plots (need the optional [plot] extra)."""

from __future__ import annotations

import math

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

import numpy as np  # noqa: E402

from ..network.network import Network  # noqa: E402
from ..network.builders import corridor_network  # noqa: E402
from ..network.state import NetworkState  # noqa: E402
from ..visualizations.plots import plot_network  # noqa: E402


def _run(net) -> NetworkState:
    """Run ``net`` for a few steps and return its (guaranteed) network state."""
    sim = net.compile(time_step=1.0, total_time=3.0)
    sim.run()
    assert sim.network_state is not None  # attached by compile()
    return sim.network_state


def _state(links, positions) -> NetworkState:
    """Compile a tiny network from ``links`` (u, v pairs) and node ``positions``."""
    net = Network()
    for node, pos in positions.items():
        net.add_node(node, pos)
    for u, v in links:
        net.add_link(u, v, length=1000.0, v_f=15.0, w=5.0, rho_jam=0.2, capacity=1800.0)
    return _run(net)


def _colinear_bidirectional_state() -> NetworkState:
    """A straight corridor with both directions on the n0<->n1 edge (all on y=0)."""
    net = corridor_network([200.0, 200.0])
    net.add_link("n1", "n0", length=200.0)  # reverse link on the n0<->n1 edge
    return _run(net)


def _arrow_paths(ax) -> list[bytes]:
    """Each link arrow's drawn path as hashable bytes, to compare arcs for overlap.

    Links are drawn with ``annotate`` arrows, whose ``FancyArrowPatch`` lives on the
    annotation (``ax.texts``); node/label annotations carry no arrow.
    """
    patches = [t.arrow_patch for t in ax.texts if t.arrow_patch is not None]
    return [np.asarray(p.get_path().vertices).tobytes() for p in patches]


def test_opposing_links_are_fanned_onto_distinct_arcs():
    """A->B and B->A get separate arcs, so the two arrows no longer overlap."""
    ax = plot_network(_colinear_bidirectional_state(), color_by="capacity")
    ax.figure.canvas.draw()  # realise the arc paths in data coordinates
    paths = _arrow_paths(ax)
    # One arrow per real link; the two opposing arrows on the shared edge differ.
    assert len(paths) == 3
    assert len(set(paths)) == len(paths)  # no two arrows trace the same path


def test_bowed_arrows_are_not_clipped_on_a_flat_layout():
    """The arcs' bow extends the y-limits, so a colinear layout does not clip them."""
    ax = plot_network(_colinear_bidirectional_state(), color_by="capacity")
    lo, hi = ax.get_ylim()
    # Nodes alone sit on y=0; a non-trivial y-span means the arcs are in view.
    assert hi - lo > 0.1


def test_many_parallel_links_on_a_non_aligned_layout():
    """More than two links on a pair, with off-grid nodes, draw one arc each."""
    # Three parallel 0->1 links plus a triangle to an off-axis node 2.
    state = _state(
        [(0, 1), (0, 1), (0, 1), (1, 2), (2, 0)],
        {0: (0.0, 0.0), 1: (2.0, 0.0), 2: (1.0, 1.3)},
    )
    ax = plot_network(state, color_by="capacity", annotate_links=True)
    ax.figure.canvas.draw()
    paths = _arrow_paths(ax)
    # One arrow per link; every arc traces a distinct path (no overlap/artefacts).
    assert len(paths) == 5
    assert len(set(paths)) == len(paths)
    # The whole drawing stays within finite, sensible limits.
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    assert x1 > x0 and y1 > y0 and all(map(math.isfinite, (x0, x1, y0, y1)))
