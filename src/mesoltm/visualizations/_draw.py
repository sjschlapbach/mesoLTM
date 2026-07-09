# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Shared network-drawing primitives for the static map and the animation.

Both :func:`mesoltm.visualizations.plots.plot_network` and the video renderer
(:mod:`mesoltm.visualizations.animation`) fan the links the same way and draw the
same arcs and node markers — this module holds that common logic so the two views
stay in sync and the drawing code is not duplicated.

The functions take a matplotlib ``ax`` and call methods on it, so this module needs
no matplotlib import of its own (keeping the geometry helpers cheap to reuse/test).
"""

from __future__ import annotations

from collections import Counter

# Arc curvature (matplotlib ``arc3`` rad) for links that share a node pair: the
# k-th link on a pair (0-based, per direction) bows by ``PARALLEL_RAD * (k + 1)``,
# and the two directions of a bidirectional edge — drawn opposite at equal curvature
# — bow to opposite sides. A lone link is drawn straight.
PARALLEL_RAD = 0.2

# Node marker / label styling shared by both views.
NODE_FACE = "#ffffff"
NODE_EDGE = "#333333"
NODE_TEXT = "#222222"


def bezier_point(p0: tuple, p1: tuple, rad: float, t: float) -> tuple:
    """Point at parameter ``t`` on the exact quadratic curve matplotlib's ``arc3``
    draws for ``connectionstyle="arc3,rad"``.

    matplotlib places the control point at the chord midpoint offset by ``rad``
    times the chord vector rotated -90° (``(dy, -dx)``). Using that same point here
    means anything positioned on the curve (an agent slot, a link label) lies exactly
    on the arc the link is drawn with, for any ``rad`` and any (incl. diagonal)
    direction. At ``t = 0.5`` this is the arc's apex.
    """
    if rad == 0.0:
        return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    cx, cy = mx + rad * dy, my - rad * dx  # matplotlib arc3 control point
    u = 1.0 - t
    x = u * u * p0[0] + 2 * u * t * cx + t * t * p1[0]
    y = u * u * p0[1] + 2 * u * t * cy + t * t * p1[1]
    return (x, y)


def fan_links(positions: dict, endpoints: dict) -> dict:
    """Return ``{link_id: (p0, p1, rad)}`` — the fanned arc for every link.

    Links sharing an *undirected* node pair (true parallel links, or the two
    directions of a bidirectional edge) are spread onto separate arcs so they never
    overlap; a lone link is drawn straight on the node centres. Each direction gets
    its own arc index, so opposing links — drawn in opposite directions at equal
    curvature — bow to opposite sides, even on diagonal edges.

    Args:
        positions: ``{node: (x, y)}`` drawing positions.
        endpoints: ``{link_id: (u, v)}`` node pair for each link.

    Links whose endpoints lack a position are skipped.
    """
    pair_of = {lid: tuple(sorted((u, v), key=str)) for lid, (u, v) in endpoints.items()}
    shared = Counter(pair_of.values())
    next_arc: dict = {}  # (u, v) -> next arc index for that direction
    arcs: dict = {}
    for lid, (u, v) in endpoints.items():
        if u not in positions or v not in positions:
            continue
        if shared[pair_of[lid]] == 1:
            rad = 0.0
        else:
            k = next_arc.get((u, v), 0)
            next_arc[(u, v)] = k + 1
            rad = PARALLEL_RAD * (k + 1)
        arcs[lid] = (positions[u], positions[v], rad)
    return arcs


def draw_arc(
    ax,
    p0: tuple,
    p1: tuple,
    rad: float,
    *,
    color,
    lw: float,
    node_diam: float,
    linestyle: str = "-",
    zorder: int = 1,
) -> None:
    """Draw one link as an ``arc3`` arrow that stops at the node markers."""
    ax.annotate(
        "",
        xy=p1,
        xytext=p0,
        arrowprops=dict(
            arrowstyle="-|>",
            color=color,
            lw=lw,
            linestyle=linestyle,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=0.5 * node_diam,  # stop the arrow at the node markers
            shrinkB=0.5 * node_diam,
        ),
        zorder=zorder,
    )


def draw_nodes(
    ax, positions: dict, node_diam: float, *, labels: dict | None = None
) -> None:
    """Draw the node markers (and optional bold id labels) in the shared style.

    ``node_diam`` is the marker diameter in points (``scatter`` uses its square as
    the area ``s``).
    """
    for key, (x, y) in positions.items():
        ax.scatter(
            x,
            y,
            s=node_diam**2,
            facecolor=NODE_FACE,
            edgecolors=NODE_EDGE,
            linewidths=1.2,
            zorder=5,
        )
        if labels is not None:
            ax.annotate(
                str(labels[key]),
                (x, y),
                ha="center",
                va="center",
                fontsize=min(8.0, 0.5 * node_diam),
                color=NODE_TEXT,
                zorder=6,
                fontweight="bold",
            )
