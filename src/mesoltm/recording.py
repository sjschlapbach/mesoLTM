# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Per-step simulation history: snapshots for animation/video generation.

This module is intentionally **matplotlib-free** so it can be imported by the
simulation core (which captures a snapshot each step when history logging is
enabled) without pulling in the optional ``[plot]`` dependency. Rendering the
snapshots into figures/video lives in :mod:`mesoltm.visualizations.animation`.

Recording every vehicle's position at every step is *off by default* (it costs
memory and, if persisted, disk) — enable it via
``Network.compile(..., record_history=True)`` (optionally with a
``history_path`` to write the JSON log). A recorded run exposes the history on
``Simulation.history``; :meth:`SimulationHistory.save` / :meth:`load`
round-trip it to disk so the video can be generated in a separate step.

Data captured per step (a :class:`Frame`):

* every agent on a **real** link — its link, its FIFO queue position (index 0 is
  the front, nearest the downstream node), the link it will enter **next**, and
  an optional ``category`` (for colouring, e.g. a coin-toss outcome);
* every **waiting** agent — one queued in an origin's vertical entry queue or
  sitting on an access connector — attributed to the node it wants to enter;
* per-link live occupancy (for optional link tinting).

The snapshot stores **scalars only** (ids, indices, a category string), never
live ``Vehicle`` objects, so frames stay valid as the simulation mutates.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core.vehicle import Vehicle
    from .network.state import NetworkState

# A classifier maps a vehicle (and the live state) to a category label used to
# colour it in the animation; ``None`` means "one category for every agent".
ClassifyFn = Callable[["Vehicle", "NetworkState"], str]

DEFAULT_CATEGORY = "vehicle"


@dataclass(frozen=True)
class AgentSnapshot:
    """One agent travelling on a real link at a given step.

    The whole remaining route is logged verbatim from ``vehicle.route`` (never
    recomputed), so the plan recorded here is exactly the one the simulation used
    — including any exogenous mid-run rerouting — and the next hop is simply read
    back from it.

    Attributes:
        vehicle_id: The vehicle's id (drawn as its label).
        link_id: The real link the agent occupies.
        queue_index: FIFO position on the link; ``0`` is the front (the vehicle
            nearest the downstream node, next to leave).
        queue_len: Number of vehicles on the link this step.
        route: The agent's remaining *real*-link route from the current link
            onward (``route[0] == link_id``), copied from ``vehicle.route``; empty
            when the vehicle carries no explicit route (e.g. pure node-by-node
            policy routing, which stores no plan on the vehicle).
        next_link_id: The link the agent will enter next (``route[1]``), or
            ``None`` if the current link is the last known one.
        next_node: The node the agent heads toward next (downstream node of
            ``next_link_id``), used to draw the intention arrow; ``None`` at the
            end of a route.
        category: Colour/legend category (see :data:`ClassifyFn`).
        props: A snapshot copy of the vehicle's ``props`` metadata (see
            :class:`~mesoltm.core.vehicle.Vehicle`) at this step, so a ``color_by``
            callable (or later analysis) can colour/inspect agents by arbitrary
            per-vehicle information.
    """

    vehicle_id: int
    link_id: object
    queue_index: int
    queue_len: int
    route: list
    next_link_id: object
    next_node: object
    category: str = DEFAULT_CATEGORY
    props: dict = field(default_factory=dict)


@dataclass(frozen=True)
class WaitingSnapshot:
    """One agent waiting to enter the network at a node.

    Waiting means either queued in an origin's vertical entry queue or sitting on
    an access connector — in both cases the agent is drawn beside ``node_id``,
    the node it is waiting to enter.

    Attributes:
        vehicle_id: The vehicle's id.
        node_id: The node the agent is waiting at / wants to enter.
        route: The agent's planned *real*-link route (from ``vehicle.route``),
            empty when it carries no explicit plan.
        next_link_id: The (real) link it intends to enter next (``route[0]``), or
            ``None``.
        next_node: The node it heads toward next, or ``None``.
        category: Colour/legend category (see :data:`ClassifyFn`).
        props: A snapshot copy of the vehicle's metadata (see
            :class:`AgentSnapshot`).
    """

    vehicle_id: int
    node_id: object
    route: list
    next_link_id: object
    next_node: object
    category: str = DEFAULT_CATEGORY
    props: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Frame:
    """A full snapshot of the network at one simulation step.

    Attributes:
        step: The simulation step index this frame captures.
        time: The simulated time in seconds (``step * dt``).
        agents: Agents on real links (see :class:`AgentSnapshot`).
        waiting: Agents waiting to enter, by node (see :class:`WaitingSnapshot`).
        link_occupancy: ``link_id -> live vehicle count`` for every real link.
    """

    step: int
    time: float
    agents: list[AgentSnapshot]
    waiting: list[WaitingSnapshot]
    link_occupancy: dict


def geometry_from_state(state: NetworkState) -> tuple[dict, dict, dict]:
    """Extract the static drawing geometry from a compiled network state.

    Returns:
        ``(node_positions, link_endpoints, connector_nodes)`` where
        ``node_positions`` maps ``node_id -> (x, y) | None``, ``link_endpoints``
        maps each **real** ``link_id -> (u, v)`` node pair, and
        ``connector_nodes`` maps each access-connector ``link_id`` to the node it
        sits at (the node whose junction a source connector feeds, or the
        destination a sink connector drains into).
    """
    node_positions = {node: state.position(node) for node in state.nodes()}
    link_endpoints = {
        lid: state.endpoints(lid)
        for lid in state.link_ids()
        if state.endpoints(lid) is not None
    }
    connector_nodes: dict = {}
    for node, conn in state.source_connectors.items():
        connector_nodes[conn] = node
    for node, conn in state.sink_connectors.items():
        connector_nodes[conn] = node
    return node_positions, link_endpoints, connector_nodes


def _category(
    classify: ClassifyFn | None, vehicle: Vehicle, state: NetworkState
) -> str:
    """Return the vehicle's category, defaulting when no classifier is given."""
    return DEFAULT_CATEGORY if classify is None else classify(vehicle, state)


def _downstream_node(state: NetworkState, link_id: int | None) -> object:
    """Return the downstream node of a real link, or ``None`` (not a real link)."""
    if link_id is None:
        return None
    endpoints = state.endpoints(link_id)
    return None if endpoints is None else endpoints[1]


def _waiting_snapshot(
    state: NetworkState, vehicle: Vehicle, node: object, classify: ClassifyFn | None
) -> WaitingSnapshot:
    """Snapshot a vehicle queued to enter ``node`` (origin queue or connector).

    The planned route is read straight off ``vehicle.route`` (never recomputed);
    the next hop is its first real link.
    """
    route = state.remaining_real_route(vehicle)
    next_link = route[0] if route else None
    return WaitingSnapshot(
        vehicle_id=vehicle.vehicle_id,
        node_id=node,
        route=list(route),
        next_link_id=next_link,
        next_node=_downstream_node(state, next_link),
        category=_category(classify, vehicle, state),
        props=dict(getattr(vehicle, "props", {})),
    )


def capture_frame(
    state: NetworkState,
    classify: ClassifyFn | None = None,
    step: int | None = None,
) -> Frame:
    """Build a :class:`Frame` from the live network state.

    No route is ever computed here. Each agent's remaining plan is read verbatim
    from its ``vehicle.route`` (via :meth:`NetworkState.remaining_real_route`, the
    same helper the rerouting interface uses), so the logged route always matches
    what the simulation actually ran — including any exogenous mid-run rerouting —
    and the drawn next hop is simply read back from it.

    Args:
        state: The live :class:`~mesoltm.network.state.NetworkState`.
        classify: Optional ``classify(vehicle, state) -> str`` for per-agent
            colour categories; ``None`` labels every agent identically.
        step: Step index to stamp on the frame; defaults to ``state.step`` (kept
            current by the simulation loop).

    Returns:
        The captured frame (scalars only; safe to keep as the sim advances).
    """
    t = state.step if step is None else step

    # Agents on real links, grouped by link in FIFO order (front first): each
    # view carries the vehicle's remaining real-link route straight off
    # ``vehicle.route``.
    views_by_link: dict = {}
    for view in state.vehicles_in_network():
        views_by_link.setdefault(view.link_id, []).append(view)

    agents: list[AgentSnapshot] = []
    occupancy: dict = {}
    for lid in state.link_ids():
        if state.endpoints(lid) is None:
            continue  # connector: not drawn as a travelling agent
        occupancy[lid] = state.occupancy(lid)
        views = views_by_link.get(lid, [])
        for index, view in enumerate(views):
            route = view.route  # real links from the current link onward
            next_link = route[1] if len(route) > 1 else None
            agents.append(
                AgentSnapshot(
                    vehicle_id=view.vehicle.vehicle_id,
                    link_id=lid,
                    queue_index=index,
                    queue_len=len(views),
                    route=list(route),
                    next_link_id=next_link,
                    next_node=_downstream_node(state, next_link),
                    category=_category(classify, view.vehicle, state),
                    props=dict(getattr(view.vehicle, "props", {})),
                )
            )

    # Agents waiting to *enter* the network: origin entry queues plus source-
    # connector occupants. (Sink-connector occupants are arriving/exiting, so they
    # are not shown as "waiting" — they vanish as the destination absorbs them.)
    waiting: list[WaitingSnapshot] = []
    for node, lid in state.source_connectors.items():
        for vehicle in state.vehicles_on(lid):
            waiting.append(_waiting_snapshot(state, vehicle, node, classify))
    for node in state.nodes():
        for vehicle in state.waiting_vehicles(node):
            waiting.append(_waiting_snapshot(state, vehicle, node, classify))

    return Frame(
        step=t,
        time=t * state.time_step,
        agents=agents,
        waiting=waiting,
        link_occupancy=occupancy,
    )


@dataclass
class SimulationHistory:
    """A recorded run: static geometry plus one :class:`Frame` per step.

    Produced by a simulation compiled with ``record_history=True`` (exposed as
    ``Simulation.history``) and consumed by
    :mod:`mesoltm.visualizations.animation` to render frames/video. It is
    self-contained — geometry is captured alongside the frames — so
    :meth:`save`/:meth:`load` let the video be generated later, without the live
    simulation.

    Attributes:
        time_step: Simulation step ``dt`` in seconds.
        node_positions: ``node_id -> (x, y) | None``.
        link_endpoints: real ``link_id -> (u, v)``.
        connector_nodes: connector ``link_id -> node_id`` it is attached to.
        frames: One :class:`Frame` per captured step, in order.
    """

    time_step: float
    node_positions: dict = field(default_factory=dict)
    link_endpoints: dict = field(default_factory=dict)
    connector_nodes: dict = field(default_factory=dict)
    frames: list[Frame] = field(default_factory=list)

    @classmethod
    def from_state(cls, state: NetworkState) -> SimulationHistory:
        """Create an empty history, capturing the geometry from ``state``."""
        positions, endpoints, connectors = geometry_from_state(state)
        return cls(
            time_step=state.time_step,
            node_positions=positions,
            link_endpoints=endpoints,
            connector_nodes=connectors,
        )

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict (ids stringified as dict keys)."""
        return {
            "time_step": self.time_step,
            "node_positions": {
                str(n): (list(p) if p is not None else None)
                for n, p in self.node_positions.items()
            },
            "link_endpoints": {
                str(lid): [str(u), str(v)]
                for lid, (u, v) in self.link_endpoints.items()
            },
            "connector_nodes": {
                str(conn): str(node) for conn, node in self.connector_nodes.items()
            },
            "frames": [_frame_to_json(frame) for frame in self.frames],
        }

    @classmethod
    def from_dict(cls, data: dict) -> SimulationHistory:
        """Rebuild a history from :meth:`to_dict` output (ids become strings)."""
        return cls(
            time_step=data["time_step"],
            node_positions={
                n: (tuple(p) if p is not None else None)
                for n, p in data["node_positions"].items()
            },
            link_endpoints={
                lid: (u, v) for lid, (u, v) in data["link_endpoints"].items()
            },
            connector_nodes=dict(data["connector_nodes"]),
            frames=[_frame_from_json(frame) for frame in data["frames"]],
        )

    def save(self, path: str) -> str:
        """Write the history to ``path`` as JSON and return the path."""
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle)
        return path

    @classmethod
    def load(cls, path: str) -> SimulationHistory:
        """Read a history written by :meth:`save`."""
        with open(path, encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))


def _frame_to_json(frame: Frame) -> dict:
    """Serialise a frame to JSON.

    Agents and waiting agents are written as **objects with named keys** (not
    positional arrays), so the log is self-describing and readable without knowing
    the field order. Ids are stringified for stable, type-agnostic keys/values.
    """
    return {
        "step": frame.step,
        "time": frame.time,
        "agents": [
            {
                "vehicle_id": a.vehicle_id,
                "link_id": str(a.link_id),
                "queue_index": a.queue_index,
                "queue_len": a.queue_len,
                "route": [str(lid) for lid in a.route],
                "next_link_id": None if a.next_link_id is None else str(a.next_link_id),
                "next_node": None if a.next_node is None else str(a.next_node),
                "category": a.category,
                "props": a.props,
            }
            for a in frame.agents
        ],
        "waiting": [
            {
                "vehicle_id": w.vehicle_id,
                "node_id": str(w.node_id),
                "route": [str(lid) for lid in w.route],
                "next_link_id": None if w.next_link_id is None else str(w.next_link_id),
                "next_node": None if w.next_node is None else str(w.next_node),
                "category": w.category,
                "props": w.props,
            }
            for w in frame.waiting
        ],
        "link_occupancy": {str(lid): n for lid, n in frame.link_occupancy.items()},
    }


def _frame_from_json(data: dict) -> Frame:
    """Rebuild a frame from :func:`_frame_to_json` output.

    Each agent/waiting object's keys are exactly the snapshot field names, so the
    dataclasses rebuild directly from the mapping.
    """
    return Frame(
        step=data["step"],
        time=data["time"],
        agents=[AgentSnapshot(**a) for a in data["agents"]],
        waiting=[WaitingSnapshot(**w) for w in data["waiting"]],
        link_occupancy=dict(data["link_occupancy"]),
    )


def record_run(sim, classify: ClassifyFn | None = None) -> SimulationHistory:
    """Run a simulation to completion, recording a frame per step.

    A convenience for the batch case (no custom stepping/injection): it enables
    history logging, runs ``sim`` and returns the populated
    :class:`SimulationHistory`. For a custom step loop (e.g. a controller that
    injects vehicles), compile with ``record_history=True`` instead and read
    ``sim.history`` after the loop.

    Args:
        sim: A compiled simulation (its ``network_state`` must be set).
        classify: Optional per-agent category classifier.

    Returns:
        The recorded history.
    """
    sim.record_history = True
    sim.history_classify = classify
    sim.run()
    return sim.history
