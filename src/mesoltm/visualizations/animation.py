# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Animate a recorded simulation: per-step figures and a rendered video.

Turns a :class:`~mesoltm.recording.SimulationHistory` (captured with
``Network.compile(..., record_history=True)``) into publication-quality frames
and an MP4/GIF showing agents moving link-to-link. Each link is drawn as a FIFO
queue; agents occupy evenly-spaced slots (the front, nearest the downstream
node, is index 0) and snap onto their next link when they cross — the faithful
picture of the discrete LTM.

The rendering scales to dense scenarios (e.g. a large grid): markers, nodes and
labels size themselves to the network's shortest link, and ``detail`` (``"auto"``
by default) drops per-agent annotations on large/dense networks while keeping them
available on request — full detail draws each agent's id and a next-link arrow.
``color_by`` sets what a dot's colour means: ``"category"`` (a recorded classify
category, e.g. a coin-toss outcome) or ``"next_link"`` (the link the agent will
take next, so a diverge's split reads at a glance). Agents waiting to enter (an
origin's entry queue or an access connector) are not yet moving, so they are drawn
as a count badge **on** the node they want to enter rather than as points, to keep
them distinct from travelling agents.

Like :mod:`mesoltm.visualizations.plots`, this module imports matplotlib at the
top and is **not** imported by ``mesoltm``'s package ``__init__``; it needs the
optional ``[plot]`` extra. MP4 output needs ``ffmpeg`` on the PATH; without it,
output gracefully falls back to an animated GIF (Pillow).

Video speed is set by ``subsample`` (frames shown per simulation step) at a fixed
``fps`` (default 25): ``subsample > 1`` holds each step for several frames (a
slower, easier-to-follow video); ``subsample < 1`` drops steps (a faster
overview); ``1`` is one frame per step.
"""

from __future__ import annotations

import math
import os
import warnings
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.animation import FFMpegWriter, PillowWriter
from matplotlib.axes import Axes
from matplotlib.lines import Line2D

from ..recording import DEFAULT_CATEGORY, SimulationHistory
from ._draw import bezier_point as _bezier_point
from ._draw import draw_arc, draw_nodes, fan_links

if TYPE_CHECKING:
    from ..core.simulation import Simulation
    from ..network.state import NetworkState
    from ..recording import AgentSnapshot, ClassifyFn, Frame, WaitingSnapshot

# Okabe-Ito colour-blind-safe qualitative palette (categories are assigned these
# in order of first appearance). Widely used for scientific figures.
OKABE_ITO = [
    "#0072b2",  # blue
    "#e69f00",  # orange
    "#009e73",  # green
    "#cc79a7",  # reddish purple
    "#56b4e9",  # sky blue
    "#d55e00",  # vermillion
    "#f0e442",  # yellow
    "#000000",  # black
]

# Default meaning of an agent dot's colour (the recorded classify category).
DEFAULT_COLOR_BY = "category"

_LINK_BASE = "#c9ced6"
_HIGHLIGHT = "#cc3311"
_TEXT = "#222222"


def _to_key(value: object) -> str:
    """Coerce a node/link id to a string layout key (ids may be int/tuple/str)."""
    return str(value)


class NetworkLayout:
    """Precomputed drawing geometry for a network (positions, link curves, limits).

    Built once and reused for every frame so the video does not jitter and the
    per-frame cost stays low. Create it with :meth:`from_state` (live simulation)
    or :meth:`from_history` (a loaded history file).

    Attributes:
        positions: ``str(node) -> (x, y)`` drawing positions.
        labels: ``str(node) -> label`` (the node's original id, stringified).
        links: ``str(link_id) -> (p0, p1, rad)`` endpoint positions + arc.
        xlim / ylim: fixed axis limits including a margin.
        scale: A characteristic length used to size markers/offsets.
        min_link: The shortest drawn link length (data units) — sets how big a
            marker can be before agents on a link overlap, so markers/labels shrink
            automatically on dense networks (e.g. a large grid).
    """

    def __init__(
        self,
        positions: dict[str, tuple[float, float]],
        labels: dict[str, str],
        links: dict[str, tuple[tuple[float, float], tuple[float, float], float]],
        xlim: tuple[float, float],
        ylim: tuple[float, float],
        scale: float,
        min_link: float,
    ) -> None:
        self.positions = positions
        self.labels = labels
        self.links = links
        self.xlim = xlim
        self.ylim = ylim
        self.scale = scale
        self.min_link = min_link

    @classmethod
    def from_state(cls, state: NetworkState) -> NetworkLayout:
        """Build a layout from a live compiled :class:`NetworkState`."""
        positions = {node: state.position(node) for node in state.nodes()}
        endpoints = {
            lid: state.endpoints(lid)
            for lid in state.link_ids()
            if state.endpoints(lid) is not None
        }
        return cls._build(positions, endpoints)

    @classmethod
    def from_history(cls, history: SimulationHistory) -> NetworkLayout:
        """Build a layout from a recorded :class:`SimulationHistory`."""
        return cls._build(history.node_positions, history.link_endpoints)

    @classmethod
    def _build(cls, node_positions: dict, link_endpoints: dict) -> NetworkLayout:
        """Resolve positions (spring-layout fallback), link arcs and axis limits."""
        labels = {_to_key(node): _to_key(node) for node in node_positions}
        resolved = cls._resolve_positions(node_positions, link_endpoints)

        # Fan links onto arcs the same way plot_network does (shared helper), so the
        # video and the static map draw identical arcs.
        endpoints = {
            _to_key(lid): (_to_key(u), _to_key(v))
            for lid, (u, v) in link_endpoints.items()
        }
        links = fan_links(resolved, endpoints)

        lengths = [math.dist(p0, p1) for (p0, p1, _rad) in links.values()]
        min_link = min(lengths) if lengths else 1.0

        xs = [p[0] for p in resolved.values()]
        ys = [p[1] for p in resolved.values()]
        if xs and ys:
            span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
            scale = max(span_x, span_y, 1.0)
            mx, my = 0.08 * scale + 0.4 * min_link, 0.08 * scale + 0.4 * min_link
            xlim = (min(xs) - mx, max(xs) + mx)
            ylim = (min(ys) - my, max(ys) + my)
        else:
            scale, xlim, ylim = 1.0, (-1.0, 1.0), (-1.0, 1.0)
        return cls(resolved, labels, links, xlim, ylim, scale, min_link)

    @staticmethod
    def _resolve_positions(
        node_positions: dict, link_endpoints: dict
    ) -> dict[str, tuple[float, float]]:
        """Return ``str(node) -> (x, y)``; spring-layout any missing positions."""
        resolved = {
            _to_key(node): (float(pos[0]), float(pos[1]))
            for node, pos in node_positions.items()
            if pos is not None
        }
        missing = [node for node, pos in node_positions.items() if pos is None]
        if missing:
            # Deterministic fallback so a network without positions still animates.
            graph = nx.DiGraph()
            graph.add_nodes_from(_to_key(n) for n in node_positions)
            graph.add_edges_from(
                (_to_key(u), _to_key(v)) for (u, v) in link_endpoints.values()
            )
            spring = nx.spring_layout(graph, seed=0)
            for node in node_positions:
                key = _to_key(node)
                if key not in resolved:
                    resolved[key] = (float(spring[key][0]), float(spring[key][1]))
        return resolved


def _effective_category(
    item: AgentSnapshot | WaitingSnapshot, color_by: str | Callable[..., str] | None
) -> str:
    """Return the colour category of an agent/waiting item under a colour mode.

    ``color_by`` may be:

    * ``None`` — a single category for every agent (colouring effectively off);
    * a **callable** ``fn(item) -> str`` — a custom category from the snapshot,
      which carries the vehicle's ``props`` metadata, ``route``, ``next_link_id``
      etc. (e.g. ``lambda a: a.props["class"]`` or ``lambda a: str(a.route[-1])``);
    * ``"next_link"`` — the id of the link the agent will enter next (so a diverge
      split is visible), or ``"exit"`` when it is about to leave;
    * ``"category"`` (or any other string) — the recorded classify category.
    """
    if color_by is None:
        return DEFAULT_CATEGORY
    if callable(color_by):
        return str(color_by(item))
    if color_by == "next_link":
        return "exit" if item.next_link_id is None else f"→{item.next_link_id}"
    return item.category


def resolve_palette(
    frames: Sequence[Frame],
    palette: dict[str, str] | None = None,
    color_by: str | Callable[..., str] | None = DEFAULT_COLOR_BY,
) -> dict[str, str]:
    """Return a stable ``category -> colour`` map for a sequence of frames.

    Categories keep any colours given in ``palette``; the rest are assigned from
    the Okabe-Ito palette in order of first appearance across **all** frames, so
    agent colours are stable over the whole animation (no per-frame flicker). With
    ``color_by="next_link"`` the categories are next-link ids (the palette cycles
    when there are more than eight).
    """
    resolved = dict(palette or {})
    ordered: list[str] = []
    for frame in frames:
        items: list[AgentSnapshot | WaitingSnapshot] = [*frame.agents, *frame.waiting]
        for item in items:
            category = _effective_category(item, color_by)
            if category not in ordered:
                ordered.append(category)
    available = [c for c in OKABE_ITO if c not in resolved.values()] or OKABE_ITO
    idx = 0
    for category in ordered:
        if category not in resolved:
            resolved[category] = available[idx % len(available)]
            idx += 1
    resolved.setdefault(DEFAULT_CATEGORY, OKABE_ITO[0])
    return resolved


def _slot_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    rad: float,
    count: int,
    max_slots: int,
) -> list[tuple[float, float]]:
    """Return drawing points for up to ``max_slots`` FIFO slots on a link.

    Slot 0 (front of queue) sits near the downstream node ``p1``; later slots
    step back toward ``p0``. The shown agents are spread evenly across the link's
    body (kept off the node markers) so a queue of any length always fits.
    Points lie on the same arc the link is drawn with.
    """
    shown = min(count, max_slots)
    lo, hi = _SLOT_LO, _SLOT_HI  # keep agents clear of the node markers at either end
    points = []
    for i in range(shown):
        if shown == 1:
            t = (lo + hi) / 2
        else:
            # index 0 nearest the downstream node (t=hi), stepping back upstream.
            t = hi - (hi - lo) * (i / (shown - 1))
        points.append(_bezier_point(p0, p1, rad, t))
    return points


def _fit_marker(
    p0: tuple[float, float],
    p1: tuple[float, float],
    pts_per_data: float,
    queue_len: int,
    max_slots: int,
    cap: float,
) -> float:
    """Marker diameter (points) that keeps a link's queued agents from overlapping.

    Shrinks the marker so the drawn FIFO slots on this link stay separated, never
    exceeding the network-scale ``cap``. Isolates any shrinking to genuinely
    crowded links, so uncrowded links keep bold markers.
    """
    shown = min(queue_len, max_slots)
    chord_pts = math.dist(p0, p1) * pts_per_data
    span = (_SLOT_HI - _SLOT_LO) * chord_pts  # drawable length for the queue
    gap = span / (shown - 1) if shown > 1 else span
    return max(3.0, min(cap, 0.85 * gap))


def _pts_per_data(ax, layout: NetworkLayout) -> float:
    """Return points-per-data-unit for the axes (so sizes scale to the network).

    Sets the fixed limits + equal aspect and applies the aspect so
    ``ax.get_position()`` reflects the squared-off box, then converts the axes'
    physical size to points. Independent of dpi (points are physical), so markers
    keep a consistent on-page size across networks of different extents.
    """
    fig = ax.figure
    fig_w, fig_h = fig.get_size_inches()
    ax.set_xlim(*layout.xlim)
    ax.set_ylim(*layout.ylim)
    ax.set_aspect("equal")
    ax.apply_aspect()
    box = ax.get_position()
    ax_w_in, ax_h_in = fig_w * box.width, fig_h * box.height
    x_span = layout.xlim[1] - layout.xlim[0]
    y_span = layout.ylim[1] - layout.ylim[0]
    return min(ax_w_in / x_span, ax_h_in / y_span) * 72.0


def _resolve_detail(
    layout: NetworkLayout, detail: str, overrides: dict[str, bool | None]
) -> dict[str, bool]:
    """Resolve which annotations to draw from a ``detail`` preset + explicit flags.

    ``detail`` is ``"auto"`` (full for compact networks, minimal for large/dense
    ones — so a big grid stays readable), ``"full"`` or ``"minimal"``. Any explicit
    ``show_*`` value in ``overrides`` (not ``None``) wins, so extra detail is always
    available on request.
    """
    if detail == "full":
        full = True
    elif detail == "minimal":
        full = False
    else:  # auto: compact networks get the full annotation set.
        full = len(layout.positions) <= 14
    resolved = {}
    for key in ("ids", "next_link", "node_labels"):
        override = overrides.get(key)
        resolved[key] = full if override is None else override
    return resolved


# A link at/above this many vehicles is drawn as "fully" congested (darker +
# thicker). Absolute (not relative to the frame's busiest link) so a single
# vehicle on a quiet frame does not look maximally congested.
_CONGESTION_REF = 6.0

# The link body agents occupy (fraction of the arc), keeping them off the node
# markers at either end. Slot 0 (front of queue) sits at ``_SLOT_HI``.
_SLOT_LO, _SLOT_HI = 0.22, 0.78


def _draw_backdrop(
    ax: Axes,
    layout: NetworkLayout,
    highlight_links: Iterable[int] | None,
    occupancy: dict[int | str, int],
    node_pts: float,
    show_labels: bool,
) -> None:
    """Draw links (arrows, optional occupancy tint/highlight) and nodes."""
    highlight = {_to_key(lid) for lid in (highlight_links or ())}
    for lid_key, (p0, p1, rad) in layout.links.items():
        base: str | tuple[float, ...] = (
            _HIGHLIGHT if lid_key in highlight else _LINK_BASE
        )
        lw = 2.4 if lid_key in highlight else 1.5
        # A busy link is darkened (and thickened) so congestion reads at a glance
        # even when agent dots are tiny on a dense network. A neutral blue-grey
        # keeps it from clashing with the (coloured) agent dots on top.
        if not highlight or lid_key not in highlight:
            occ = occupancy.get(lid_key, occupancy.get(_from_key_int(lid_key), 0))
            frac = min(1.0, occ / _CONGESTION_REF)
            if frac > 0:
                base = _blend(_LINK_BASE, "#4a5566", 0.6 * frac)
                lw = 1.5 + 1.3 * frac
        draw_arc(
            ax,
            p0,
            p1,
            rad,
            color=base,
            lw=lw,
            node_diam=node_pts,
            linestyle="--" if lid_key in highlight else "-",
        )
    draw_nodes(
        ax, layout.positions, node_pts, labels=layout.labels if show_labels else None
    )


def _from_key_int(lid_key: str) -> int | str:
    """Best-effort int form of a link key so occupancy lookups match either type."""
    try:
        return int(lid_key)
    except (TypeError, ValueError):
        return lid_key


def _blend(color_a: str, color_b: str, t: float) -> tuple[float, ...]:
    """Linearly blend two hex colours (``t`` in [0, 1])."""
    ca = tuple(int(color_a[i : i + 2], 16) / 255 for i in (1, 3, 5))
    cb = tuple(int(color_b[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return tuple(ca[i] + (cb[i] - ca[i]) * t for i in range(3))


def _draw_next_link_arrow(
    ax: Axes,
    pos: tuple[float, float],
    target: tuple[float, float] | None,
    colour: str,
    arrow_len: float,
    label: str | None,
    label_fs: float,
) -> None:
    """Draw a short intention arrow from an agent toward its next node + a label."""
    if target is None:
        return
    dx, dy = target[0] - pos[0], target[1] - pos[1]
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist
    start = (pos[0] + ux * 0.25 * arrow_len, pos[1] + uy * 0.25 * arrow_len)
    end = (pos[0] + ux * arrow_len, pos[1] + uy * arrow_len)
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.5),
        zorder=7,
    )
    if label is not None:
        ax.annotate(
            label,
            end,
            xytext=(ux * 4.0, uy * 4.0),
            textcoords="offset points",
            fontsize=label_fs,
            color=colour,
            ha="center",
            va="center",
            zorder=8,
        )


def render_frame(
    frame: Frame,
    layout: NetworkLayout,
    ax: Axes | None = None,
    *,
    palette: dict[str, str] | None = None,
    color_by: str | Callable[..., str] | None = DEFAULT_COLOR_BY,
    detail: str = "auto",
    show_agent_ids: bool | None = None,
    show_next_link: bool | None = None,
    show_node_labels: bool | None = None,
    max_slots: int = 8,
    highlight_links: Iterable[int] | None = None,
    title: str | None = None,
) -> Axes:
    """Draw a single recorded frame onto ``ax`` (created if omitted).

    Marker, node and label sizes scale to the network so the frame stays readable
    from a small bottleneck to a large dense grid. How much per-agent annotation is
    drawn is controlled by ``detail`` (with per-annotation overrides), so dense
    scenarios can stay clean while the extra detail remains available on request.

    Args:
        frame: The :class:`~mesoltm.recording.Frame` to draw.
        layout: The :class:`NetworkLayout` for the network.
        ax: Optional axes; a new figure/axes is created if omitted.
        palette: ``category -> colour`` map; resolved from the frame if omitted.
        color_by: What the agent dot colour encodes. ``"category"`` (default) uses
            the recorded classify category; ``"next_link"`` colours by the link the
            agent enters next (a diverge's split at a glance); ``None`` gives every
            agent one colour (colouring off); or pass a **callable**
            ``fn(snapshot) -> str`` to colour by anything on the snapshot — most
            usefully the vehicle's ``props`` metadata (e.g.
            ``lambda a: a.props.get("class", "car")``) or its destination
            (``lambda a: str(a.route[-1]) if a.route else "exit"``).
        detail: ``"auto"`` (full annotations for compact networks, minimal for
            large/dense ones), ``"full"`` or ``"minimal"``.
        show_agent_ids: Override — draw the id inside each agent marker.
        show_next_link: Override — draw each agent's next-link intention arrow +
            label.
        show_node_labels: Override — draw node id labels.
        max_slots: Maximum FIFO slots drawn per link; longer queues show a ``+k``
            overflow tag (when agent ids are shown).
        highlight_links: Optional link ids drawn dashed-red (e.g. a bottleneck).
        title: Optional title drawn on the axes.

    Returns:
        The matplotlib axes containing the drawing.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 6))
    colours = (
        palette if palette is not None else resolve_palette([frame], color_by=color_by)
    )
    flags = _resolve_detail(
        layout,
        detail,
        {
            "ids": show_agent_ids,
            "next_link": show_next_link,
            "node_labels": show_node_labels,
        },
    )

    # Size everything from the network's shortest drawn link, so markers never
    # overrun a link on a dense grid yet stay bold on a small network. ``marker_cap``
    # is the network-scale upper bound; each link then shrinks its own marker just
    # enough that its queued agents never overlap (see ``_fit_marker``).
    pts_per_data = _pts_per_data(ax, layout)
    marker_cap = max(3.5, min(0.22 * layout.min_link * pts_per_data, 18.0))  # points
    node_diam = max(4.0, min(0.22 * layout.min_link * pts_per_data, 24.0))
    arrow_len = 0.55 * layout.min_link  # data units

    _draw_backdrop(
        ax,
        layout,
        highlight_links,
        frame.link_occupancy,
        node_diam,
        flags["node_labels"],
    )

    # Group agents by link so each link's queue is laid out together.
    by_link: dict[str, list[AgentSnapshot]] = {}
    for agent in frame.agents:
        by_link.setdefault(_to_key(agent.link_id), []).append(agent)

    for lid_key, agents in by_link.items():
        if lid_key not in layout.links:
            continue
        p0, p1, rad = layout.links[lid_key]
        agents = sorted(agents, key=lambda a: a.queue_index)
        queue_len = agents[0].queue_len
        points = _slot_points(p0, p1, rad, queue_len, max_slots)
        marker_diam = _fit_marker(
            p0, p1, pts_per_data, queue_len, max_slots, marker_cap
        )
        id_fs = 0.5 * marker_diam
        show_ids = flags["ids"] and marker_diam >= 12.0  # only if the dot can hold it
        for agent, point in zip(agents[:max_slots], points):
            colour = colours.get(_effective_category(agent, color_by), OKABE_ITO[0])
            ax.scatter(
                *point,
                s=marker_diam**2,
                facecolor=colour,
                edgecolors="white",
                linewidths=min(1.2, 0.09 * marker_diam),
                zorder=6,
            )
            if show_ids:
                ax.annotate(
                    str(agent.vehicle_id),
                    point,
                    ha="center",
                    va="center",
                    fontsize=id_fs,
                    color="white",
                    zorder=7,
                    fontweight="bold",
                )
            if flags["next_link"]:
                target = layout.positions.get(_to_key(agent.next_node))
                label = None if agent.next_link_id is None else str(agent.next_link_id)
                _draw_next_link_arrow(
                    ax, point, target, colour, arrow_len, label, max(5.0, 0.42 * id_fs)
                )
        overflow = queue_len - max_slots
        if overflow > 0 and flags["ids"]:
            ax.annotate(
                f"+{overflow}",
                points[-1],
                xytext=(0, -9),
                textcoords="offset points",
                fontsize=7,
                color=_TEXT,
                ha="center",
                va="center",
                zorder=7,
            )

    _draw_waiting(ax, frame, layout, colours, node_diam, color_by)

    ax.axis("off")
    ax.annotate(
        f"t = {frame.time:.0f} s   (step {frame.step})",
        (0.01, 0.99),
        xycoords="axes fraction",
        ha="left",
        va="top",
        fontsize=9,
        color=_TEXT,
    )
    if title:
        ax.set_title(title, fontsize=11)
    _draw_legend(ax, frame, colours, color_by)
    return ax


def _draw_waiting(
    ax: Axes,
    frame: Frame,
    layout: NetworkLayout,
    colours: dict[str, str],
    node_diam: float,
    color_by: str | Callable[..., str] | None,
) -> None:
    """Draw each origin's waiting queue as a count badge on the node itself.

    Agents queued to *enter* the network (an origin's vertical entry queue or an
    access connector) are not yet moving on a link, so drawing them as points
    would be confused with travelling agents. Instead the node they wait at is
    overdrawn with a filled badge carrying the number waiting there, coloured by
    their (usually uniform) category.
    """
    by_node: dict[str, list[WaitingSnapshot]] = {}
    for waiter in frame.waiting:
        by_node.setdefault(_to_key(waiter.node_id), []).append(waiter)
    badge_diam = max(1.25 * node_diam, 13.0)
    for node_key, waiters in by_node.items():
        anchor = layout.positions.get(node_key)
        if anchor is None:
            continue
        colour = colours.get(_effective_category(waiters[0], color_by), OKABE_ITO[0])
        ax.scatter(
            *anchor,
            s=badge_diam**2,
            facecolor=colour,
            edgecolors="white",
            linewidths=1.4,
            zorder=8,
        )
        ax.annotate(
            str(len(waiters)),
            anchor,
            ha="center",
            va="center",
            fontsize=max(6.0, 0.55 * badge_diam),
            color="white",
            fontweight="bold",
            zorder=9,
        )


def _draw_legend(
    ax: Axes,
    frame: Frame,
    colours: dict[str, str],
    color_by: str | Callable[..., str] | None,
) -> None:
    """Draw a category legend when there is more than one category on screen.

    Skipped for ``color_by="next_link"`` (one entry per link would be an unreadable
    legend on a dense network); the dot colours speak for themselves there.
    """
    if color_by == "next_link":
        return
    present: list[str] = []
    items: list[AgentSnapshot | WaitingSnapshot] = [*frame.agents, *frame.waiting]
    for item in items:
        category = _effective_category(item, color_by)
        if category not in present:
            present.append(category)
    if len(present) <= 1 and present == [DEFAULT_CATEGORY]:
        return
    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markerfacecolor=colours.get(c),
            markeredgecolor="white",
            markersize=8,
            label=c,
        )
        for c in present
    ]
    if handles:
        ax.legend(
            handles=handles,
            loc="upper right",
            fontsize=8,
            frameon=True,
            framealpha=0.9,
            title="agent state",
        )


def expand_frame_indices(n_frames: int, subsample: float) -> list[int]:
    """Map output-frame index -> source-frame index for a playback ``subsample``.

    ``subsample`` is frames-shown-per-step: ``>1`` repeats each step's frame (a
    slower video), ``<1`` drops steps (a faster video), ``1`` is one-to-one.
    """
    if subsample <= 0:
        raise ValueError("subsample must be > 0")
    out_count = max(1, round(n_frames * subsample))
    return [min(n_frames - 1, int(j / subsample)) for j in range(out_count)]


def save_frames(
    frames: Sequence[Frame],
    layout: NetworkLayout,
    out_dir: str,
    *,
    stride: int = 1,
    dpi: int = 150,
    prefix: str = "frame_",
    palette: dict[str, str] | None = None,
    **render_kw,
) -> list[str]:
    """Save individual per-step PNGs (the "separate pictures" option).

    Args:
        frames: The recorded frames (a list of :class:`Frame`).
        layout: The :class:`NetworkLayout`.
        out_dir: Directory to write PNGs into (created if missing).
        stride: Write every ``stride``-th frame (decimation for fewer images).
        dpi: Output resolution.
        prefix: Filename prefix; files are ``<prefix>0000.png`` ...
        palette: Optional fixed ``category -> colour`` map (resolved once so all
            frames share colours/legend).
        **render_kw: Forwarded to :func:`render_frame` (e.g. ``highlight_links``,
            ``title``, ``show_next_link``, ``max_slots``).

    Returns:
        The list of written file paths.
    """
    os.makedirs(out_dir, exist_ok=True)
    colours = resolve_palette(
        frames, palette, render_kw.get("color_by", DEFAULT_COLOR_BY)
    )
    paths: list[str] = []
    fig, ax = plt.subplots(figsize=(9, 6))
    try:
        for i in range(0, len(frames), max(1, stride)):
            ax.clear()
            render_frame(frames[i], layout, ax=ax, palette=colours, **render_kw)
            path = os.path.join(out_dir, f"{prefix}{i:04d}.png")
            fig.savefig(path, dpi=dpi, bbox_inches="tight")
            paths.append(path)
    finally:
        plt.close(fig)
    return paths


def _make_writer(out_path: str, fps: int) -> tuple[FFMpegWriter | PillowWriter, str]:
    """Pick a writer from the extension; fall back to GIF if ffmpeg is missing.

    Returns ``(writer, out_path)`` — ``out_path`` may be rewritten to ``.gif``
    when an MP4 was requested but ffmpeg is unavailable.
    """
    suffix = os.path.splitext(out_path)[1].lower()
    if suffix == ".gif":
        return PillowWriter(fps=fps), out_path
    if FFMpegWriter.isAvailable():
        return FFMpegWriter(fps=fps), out_path
    gif_path = os.path.splitext(out_path)[0] + ".gif"
    warnings.warn(
        f"ffmpeg not available; writing {gif_path} (GIF) instead of {out_path}. "
        "Install ffmpeg for MP4 output.",
        stacklevel=2,
    )
    return PillowWriter(fps=fps), gif_path


def save_animation(
    frames: Sequence[Frame],
    layout: NetworkLayout,
    out_path: str,
    *,
    fps: int = 25,
    subsample: float = 1.0,
    dpi: int = 150,
    palette: dict[str, str] | None = None,
    frames_dir: str | None = None,
    **render_kw,
) -> str:
    """Render the frames to a video (MP4 or GIF) and return the output path.

    Args:
        frames: The recorded frames (a list of :class:`Frame`).
        layout: The :class:`NetworkLayout`.
        out_path: Output file; ``.mp4`` uses ffmpeg (falls back to ``.gif`` if
            ffmpeg is missing), ``.gif`` uses Pillow.
        fps: Frames per second (default 25).
        subsample: Frames shown per simulation step — ``>1`` slows the video
            down (each step held longer), ``<1`` speeds it up (steps dropped).
        dpi: Output resolution.
        palette: Optional fixed ``category -> colour`` map.
        frames_dir: If given, also write the individual per-step PNGs there — so
            one call can store *both* the video and the separate pictures. When
            omitted, only the video is written.
        **render_kw: Forwarded to :func:`render_frame`.

    Returns:
        The path the video was written to (``.gif`` if ffmpeg was unavailable).
    """
    if not frames:
        raise ValueError("no frames to render")
    colours = resolve_palette(
        frames, palette, render_kw.get("color_by", DEFAULT_COLOR_BY)
    )
    directory = os.path.dirname(out_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    if frames_dir is not None:
        save_frames(frames, layout, frames_dir, dpi=dpi, palette=colours, **render_kw)

    indices = expand_frame_indices(len(frames), subsample)
    writer, out_path = _make_writer(out_path, fps)
    fig, ax = plt.subplots(figsize=(9, 6))
    try:
        with writer.saving(fig, out_path, dpi):
            for source in indices:
                ax.clear()
                render_frame(
                    frames[source], layout, ax=ax, palette=colours, **render_kw
                )
                writer.grab_frame()
    finally:
        plt.close(fig)
    return out_path


def animate_history(history: SimulationHistory, out_path: str, **kwargs) -> str:
    """Render a recorded :class:`SimulationHistory` to a video (builds the layout)."""
    layout = NetworkLayout.from_history(history)
    return save_animation(history.frames, layout, out_path, **kwargs)


def animate_from_history_file(history_path: str, out_path: str, **kwargs) -> str:
    """Load a saved history file and render it, guiding the user if it is missing.

    Args:
        history_path: Path to a JSON history written by
            :meth:`SimulationHistory.save` (or via ``history_path`` at compile).
        out_path: Output video path.
        **kwargs: Forwarded to :func:`save_animation`.

    Raises:
        FileNotFoundError: If ``history_path`` does not exist — with a message
            explaining how to enable history logging.
    """
    if not os.path.exists(history_path):
        raise FileNotFoundError(
            f"history file not found: {history_path}\n"
            "Per-step history logging is off by default. Enable it and re-run, "
            "e.g.:\n"
            "    sim = net.compile(time_step=dt, total_time=T, "
            "record_history=True,\n"
            f"                      history_path={history_path!r})\n"
            "    sim.run()   # writes the history file\n"
            "(for a custom step loop, call sim.save_history(path) after the loop)."
        )
    return animate_history(SimulationHistory.load(history_path), out_path, **kwargs)


def animate_simulation(
    sim: Simulation,
    out_path: str,
    *,
    classify: ClassifyFn | None = None,
    **kwargs,
) -> str:
    """Run a simulation with history logging and render it in one call.

    Convenience for the batch case (no custom stepping): enables recording, runs
    ``sim`` and renders the result. For a custom step loop that injects vehicles,
    compile with ``record_history=True`` and render ``sim.history`` yourself.

    Args:
        sim: A compiled simulation.
        out_path: Output video path.
        classify: Optional per-agent category classifier.
        **kwargs: Forwarded to :func:`save_animation` (``fps``, ``subsample``,
            ``frames_dir``, ``highlight_links``, ...).

    Returns:
        The path the video was written to.
    """
    sim.record_history = True
    sim.history_classify = classify
    sim.run()
    assert sim.history is not None
    return animate_history(sim.history, out_path, **kwargs)
