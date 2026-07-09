# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Flow and network visualisations (require the optional ``[plot]`` extra).

This module imports matplotlib at module top. It is intentionally **not** imported
by ``mesoltm``'s package ``__init__``, so ``import mesoltm`` stays cheap and only
code that actually plots (``import mesoltm.visualizations``) pulls in matplotlib —
which the ``[plot]`` extra installs.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.colors import Normalize

if TYPE_CHECKING:
    from ..core.simulation import Simulation
    from ..network.state import NetworkState


def plot_cumulative_curves(
    sim: Simulation, link_ids: Sequence[int] | None = None, ax=None
):
    """Plot cumulative inflow (solid) and outflow (dashed) for links over time.

    Args:
        sim: A run :class:`~mesoltm.core.simulation.Simulation`.
        link_ids: Link ids to plot; defaults to all links in the simulation.
        ax: Optional matplotlib axes to draw on; a new one is created if omitted.

    Returns:
        The matplotlib axes containing the plot.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 6))

    times = sim.get_times(1)
    by_id = {lk.link_id: lk for lk in sim.links}
    ids = link_ids if link_ids is not None else [lk.link_id for lk in sim.links]
    for lid in ids:
        link = by_id[lid]
        (line,) = ax.plot(times, link.cumulative_inflows, label=f"link {lid} in")
        ax.plot(
            times,
            link.cumulative_outflows,
            linestyle="--",
            color=line.get_color(),
            label=f"link {lid} out",
        )
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Cumulative flow (veh)")
    ax.grid(True)
    ax.legend()
    return ax


def _resolve_window(window: int, window_seconds: float | None, dt: float) -> int:
    """Return the flow-averaging window in steps.

    If ``window_seconds`` is given it wins, converted to steps via ``dt`` (so the
    sampling interval is set in real time and stays the same however small ``dt``
    is); otherwise ``window`` (already in steps) is used. At least one step.
    """
    if window_seconds is not None:
        return max(1, round(window_seconds / dt))

    return max(1, window)


def plot_link_flow(
    sim: Simulation,
    link_ids: Iterable[int],
    window: int = 60,
    window_seconds: float | None = None,
    ax=None,
):
    """Plot the flow (veh/h) through one or a collection of links over time.

    When several link ids are given their flows are summed, so this doubles as a
    "flow across a cut" plot (e.g. total flow leaving a region).

    Args:
        sim: A run simulation.
        link_ids: One or more link ids whose outflow is aggregated.
        window: Averaging/sampling window in **steps** for the flow rate.
        window_seconds: Same window expressed in **seconds**; when given it takes
            precedence over ``window`` (converted via the simulation's time step).
            Prefer this when the simulation step is small, so the sampling interval
            of the flow curve is independent of ``dt``.
        ax: Optional axes; created if omitted.

    Returns:
        The matplotlib axes containing the plot.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 4))

    by_id = {lk.link_id: lk for lk in sim.links}
    ids = list(link_ids)
    n = len(by_id[ids[0]].cumulative_outflows)
    dt = sim.time_step
    window = _resolve_window(window, window_seconds, dt)
    times = []
    flows = []
    for t in range(0, n - window, window):
        total = sum(
            by_id[lid].cumulative_outflows[t + window]
            - by_id[lid].cumulative_outflows[t]
            for lid in ids
        )
        times.append(t * dt)
        flows.append(total / (window * dt) * 3600.0)
    ax.plot(times, flows)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Flow (veh/h)")
    ax.grid(True)
    return ax


def plot_link_flows(
    sim: Simulation,
    link_ids: Iterable[int],
    labels: Sequence[str] | None = None,
    window: int = 60,
    window_seconds: float | None = None,
    ax=None,
):
    """Plot flow (veh/h) over time for each link as its own labelled line.

    Unlike :func:`plot_link_flow` (which sums links into one "cut" curve), this
    draws one line per link so it is clear *which* link carries *which* flow —
    handy for small scenarios (e.g. a freeway merge, parallel lanes).

    Args:
        sim: A run simulation.
        link_ids: The links to plot, one line each.
        labels: Optional legend labels, one per link id (defaults to ``link <id>``).
        window: Averaging/sampling window in **steps** for the flow rate.
        window_seconds: Same window expressed in **seconds**; when given it takes
            precedence over ``window`` (converted via the simulation's time step).
            Prefer this when the simulation step is small, so the sampling interval
            of the flow curve is independent of ``dt``.
        ax: Optional axes; created if omitted.

    Returns:
        The matplotlib axes containing the plot.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 4))

    ids = list(link_ids)
    names = list(labels) if labels is not None else [f"link {lid}" for lid in ids]
    by_id = {lk.link_id: lk for lk in sim.links}
    dt = sim.time_step
    window = _resolve_window(window, window_seconds, dt)
    n = len(by_id[ids[0]].cumulative_outflows)
    for lid, name in zip(ids, names, strict=True):
        out = by_id[lid].cumulative_outflows
        times = [t * dt for t in range(0, n - window, window)]
        flows = [
            (out[t + window] - out[t]) / (window * dt) * 3600.0
            for t in range(0, n - window, window)
        ]
        ax.plot(times, flows, label=name)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Flow (veh/h)")
    ax.grid(True)
    ax.legend()
    return ax


def plot_travel_time_distribution(trips: Sequence[dict], ax=None, bins: int = 20):
    """Plot the distribution of per-vehicle overall travel times.

    Args:
        trips: Trip records from :func:`mesoltm.metrics.collect_trips`.
        ax: Optional axes; created if omitted.
        bins: Number of histogram bins.

    Returns:
        The matplotlib axes containing the plot.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 4))

    values = [t["travel_time"] for t in trips if t["travel_time"] is not None]
    ax.hist(values, bins=bins, color="#4477aa", edgecolor="white")
    if values:
        ax.axvline(
            sum(values) / len(values),
            color="#cc3311",
            linestyle="--",
            label=f"mean = {sum(values) / len(values):.0f} s",
        )
        ax.legend()
    ax.set_xlabel("Travel time (s)")
    ax.set_ylabel("Vehicles")
    ax.set_title("Per-vehicle travel-time distribution")
    ax.grid(True, axis="y")
    return ax


def plot_link_travel_times(trips: Sequence[dict], ax=None):
    """Plot the mean travel time on each link, aggregated over all trips.

    Args:
        trips: Trip records from :func:`mesoltm.metrics.collect_trips`.
        ax: Optional axes; created if omitted.

    Returns:
        The matplotlib axes containing the plot.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 4))

    totals: dict = {}
    counts: dict = {}
    for t in trips:
        for link_id, value in t["link_travel_times"].items():
            totals[link_id] = totals.get(link_id, 0.0) + value
            counts[link_id] = counts.get(link_id, 0) + 1

    link_ids = sorted(totals)
    means = [totals[lid] / counts[lid] for lid in link_ids]
    ax.bar([str(lid) for lid in link_ids], means, color="#228833")
    ax.set_xlabel("Link id")
    ax.set_ylabel("Mean travel time (s)")
    ax.set_title("Mean travel time per link")
    ax.grid(True, axis="y")
    return ax


def _running_average(values: Sequence[float], window: int) -> list[float]:
    """Trailing moving average of ``values`` over ``window`` samples.

    The window ramps up at the start (uses however many samples are available), so
    the output has the same length as the input and no leading gap.
    """
    w = max(1, window)
    averaged = []
    for i in range(len(values)):
        chunk = values[max(0, i - w + 1) : i + 1]
        averaged.append(sum(chunk) / len(chunk))
    return averaged


def plot_link_time_series(
    sim: Simulation,
    link_ids: Sequence[int],
    labels: Sequence[str] | None = None,
    window: int = 5,
    axes=None,
):
    """One subplot per link: the travel time experienced on it, over time.

    Each vehicle that crossed a link contributes one point ``(time it entered the
    link, time it took to cross)``. Points are sorted by entry time and smoothed
    with a trailing moving average, so a link where a queue builds up shows its
    travel time **climbing over the run** — the formation of congestion made
    visible per link.

    Samples are taken from completed vehicles' recorded trajectories (see
    :attr:`mesoltm.core.vehicle.Vehicle.trajectory`).

    Args:
        sim: A run simulation.
        link_ids: The links to plot, one subplot each (e.g. four links -> four
            side-by-side panels).
        labels: Optional per-link subplot titles (defaults to ``link <id>``).
        window: Number of samples in the trailing moving average.
        axes: Optional sequence of axes (one per link); a new row of subplots is
            created if omitted.

    Returns:
        The sequence of axes, one per link.
    """
    ids = list(link_ids)
    names = list(labels) if labels is not None else [f"link {lid}" for lid in ids]
    dt = sim.time_step

    # Gather (entry_time_s, crossing_time_s) per link from every completed vehicle's
    # trajectory. Only closed segments (a recorded exit) on a wanted link count.
    wanted = set(ids)
    samples: dict[int, list[tuple[float, float]]] = {lid: [] for lid in ids}
    for node in sim.nodes:
        for vehicle in getattr(node, "arrived_vehicles", []):
            for seg in vehicle.trajectory:
                lid = seg["link_id"]
                if lid in wanted and seg["exit_step"] is not None:
                    entry_s = seg["entry_step"] * dt
                    crossing_s = (seg["exit_step"] - seg["entry_step"]) * dt
                    samples[lid].append((entry_s, crossing_s))

    if axes is None:
        _, grid = plt.subplots(
            1, len(ids), figsize=(4.2 * len(ids), 3.6), sharey=True, squeeze=False
        )
        axes = grid[0]

    for ax, lid, name in zip(axes, ids, names, strict=True):
        points = sorted(samples[lid])  # chronological by entry time
        if points:
            times = [t for t, _ in points]
            values = [v for _, v in points]
            ax.scatter(times, values, s=14, color="0.75", zorder=1, label="per vehicle")
            ax.plot(
                times,
                _running_average(values, window),
                color="#cc3311",
                lw=2.0,
                zorder=2,
                label=f"running avg (w={window})",
            )
            ax.legend(fontsize=7)
        ax.set_title(name)
        ax.set_xlabel("entry time (s)")
        ax.grid(True)
    axes[0].set_ylabel("link travel time (s)")
    return axes


# Per-key arc curvature used to fan links that share an edge (arc3 ``rad``). Key
# ``k`` (the k-th link between a node pair) bows by ``_PARALLEL_RAD * (k + 1)``; the
# two directions of a bidirectional edge share a key and, drawn in opposite
# directions at equal curvature, bow to opposite sides — so nothing overlaps.
_PARALLEL_RAD = 0.2


def _arc_span(p0: tuple, p1: tuple, rad: float) -> list[tuple]:
    """Two points bounding an ``arc3`` link's outward bow, for the autoscale.

    A curved :class:`~matplotlib.patches.FancyArrowPatch` does not extend the axes'
    data limits on its own, so a fanned/curved link could be clipped on a flat layout
    where the nodes alone give no spread. Returning the mid-span offset to *both*
    sides (the bow's sign depends on draw direction) guarantees it stays in view.
    """
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy) or 1.0
    px, py = -dy / length, dx / length  # unit perpendicular to the chord
    bow = 0.5 * rad * length  # ~apex offset of the arc from the chord midpoint
    return [(mx + bow * px, my + bow * py), (mx - bow * px, my - bow * py)]


def plot_network(
    state: NetworkState,
    color_by: str = "occupancy",
    ax=None,
    node_size: float = 260.0,
    annotate_links: bool = False,
):
    """Draw the network with links coloured by a per-link quantity.

    Drawn with networkx on top of matplotlib, so it is robust to arbitrary node
    placements (not just grid-aligned) and to any number of links between a node
    pair. Requires node positions (set when building the network). Connector links
    are omitted; only real links are drawn. Links that share an edge — true parallel
    links *and* the two directions of a bidirectional edge (``A->B`` and ``B->A``) —
    are fanned onto separate arcs so their arrows never overlap; a lone link is drawn
    straight.

    Args:
        state: A :class:`~mesoltm.network.state.NetworkState`.
        color_by: Link quantity to colour by: ``"flow"`` (total vehicles that have
            traversed the link so far, i.e. cumulative outflow — most useful after
            a run), ``"occupancy"`` (live vehicle count), ``"density"`` or
            ``"capacity"``.
        ax: Optional axes; created if omitted.
        node_size: Marker size for nodes.
        annotate_links: If ``True``, label each link on its arc with its id and
            value — so it is clear which link carries which flow.

    Returns:
        The matplotlib axes containing the plot.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(6, 6))

    def value(lid: int) -> float:
        if color_by == "density":
            return state.density(lid)
        if color_by == "capacity":
            return state.capacity(lid)
        if color_by == "flow":
            return state.cumulative_outflow(lid)
        return state.occupancy(lid)

    # Real (non-connector) links and their endpoints; connectors have no endpoints.
    endpoints = {
        lid: ep for lid in state.link_ids() if (ep := state.endpoints(lid)) is not None
    }
    real_ids = list(endpoints)
    values = {lid: value(lid) for lid in real_ids}
    vmax = max(values.values(), default=0.0) or 1.0
    cmap = plt.get_cmap("viridis")
    norm = Normalize(vmin=0.0, vmax=vmax)

    # Build a directed multigraph so networkx handles the layout and lets several
    # links share a node pair. Positions come straight from the network.
    graph = nx.MultiDiGraph()
    positions: dict = {}
    for node in state.nodes():
        pos = state.position(node)
        if pos is not None:
            positions[node] = (float(pos[0]), float(pos[1]))
            graph.add_node(node)

    # How many links share each *undirected* node pair — a pair with more than one
    # link gets fanned onto arcs; a lone link stays straight.
    pair_of = {lid: tuple(sorted(endpoints[lid], key=str)) for lid in real_ids}
    shared = Counter(pair_of.values())

    straight: list = []  # (u, v, key) tuples of lone links
    curved: list = []  # (u, v, key) tuples of links that share an edge
    straight_c: list = []  # matching colour values
    curved_c: list = []
    straight_lbl: dict = {}  # (u, v, key) -> label text
    curved_lbl: dict = {}
    for lid in real_ids:
        u, v = endpoints[lid]
        if u not in positions or v not in positions:
            continue
        key = graph.add_edge(u, v, link_id=lid)
        is_shared = shared[pair_of[lid]] > 1
        (curved if is_shared else straight).append((u, v, key))
        (curved_c if is_shared else straight_c).append(values[lid])
        (curved_lbl if is_shared else straight_lbl)[
            (u, v, key)
        ] = f"{lid}: {values[lid]:g}"

    # One arc3 style per multi-edge key; index k is the k-th link on a pair.
    max_key = max((k for _, _, k in curved), default=-1)
    curved_styles = [f"arc3,rad={_PARALLEL_RAD * (k + 1)}" for k in range(max_key + 1)]

    # Lone links straight, shared links fanned onto their arcs; same styling otherwise.
    for edges, colours, style in [
        (straight, straight_c, "arc3,rad=0"),
        (curved, curved_c, curved_styles),
    ]:
        if edges:
            nx.draw_networkx_edges(
                graph,
                positions,
                edgelist=edges,
                edge_color=colours,
                connectionstyle=style,
                edge_cmap=cmap,
                edge_vmin=0.0,
                edge_vmax=vmax,
                arrowstyle="-|>",
                arrowsize=13,
                width=2.5,
                node_size=node_size,  # so arrowheads stop at the node markers
                ax=ax,
            )

    nx.draw_networkx_nodes(
        graph,
        positions,
        node_color="white",
        edgecolors="black",
        linewidths=1.0,
        node_size=node_size,
        ax=ax,
    )
    nx.draw_networkx_labels(
        graph, positions, labels={n: str(n) for n in graph.nodes()}, font_size=7, ax=ax
    )

    if annotate_links:
        # networkx places each label on its (curved) arc, so parallel links' labels
        # separate instead of stacking at the shared mid-point.
        bbox = dict(boxstyle="round,pad=0.15", fc="white", ec="0.7", alpha=0.85)
        for edge_labels, style in [
            (straight_lbl, "arc3,rad=0"),
            (curved_lbl, curved_styles),
        ]:
            if edge_labels:
                nx.draw_networkx_edge_labels(
                    graph,
                    positions,
                    edge_labels=edge_labels,
                    connectionstyle=style,
                    font_size=7,
                    rotate=False,
                    bbox=bbox,
                    ax=ax,
                )

    # Keep every arc's bow inside the view (curved patches do not grow the data
    # limits themselves), then let the margin leave headroom below the title.
    extents: list = []
    for u, v, k in curved:
        extents += _arc_span(positions[u], positions[v], _PARALLEL_RAD * (k + 1))
    if extents:
        ax.update_datalim(extents)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    ax.figure.colorbar(sm, ax=ax, fraction=0.046, pad=0.04, label=color_by)
    ax.set_aspect("equal")
    ax.margins(0.12)
    ax.axis("off")
    ax.set_title(f"Network coloured by {color_by}", pad=12)
    return ax
