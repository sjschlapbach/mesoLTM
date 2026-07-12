# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Read-only view of a compiled network, for routers, plugins and plots."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from ..core.ids import NodeId
    from ..core.link import Link
    from ..core.nodes.base_node import BaseNode
    from ..core.nodes.origin_node import OriginNode
    from ..core.vehicle import Vehicle


class VehicleView(NamedTuple):
    """A read-only snapshot of one in-network vehicle, for rerouting logic.

    Attributes:
        vehicle: The vehicle itself (carries ``vehicle_id``, ``destination``, ...).
        link_id: The real link the vehicle is currently travelling on (its
            location).
        route: The remaining ordered *real* link ids from the current link onward
            (connectors excluded), i.e. the plan the reroute logic may replace.
        destination: The vehicle's destination node (convenience copy).
    """

    vehicle: Vehicle
    link_id: int
    route: list[int]
    destination: NodeId


class NetworkState:  # pylint: disable=too-many-public-methods
    """A read-only accessor over the links and topology of a compiled network.

    Instances are created by :meth:`~mesoltm.network.network.Network.compile` and
    handed to routing policies and plugins so external logic can inspect the
    live network without reaching into internal objects. Live quantities
    (vehicles on a link, instantaneous density and queue) are read from each
    link's current queue; cumulative quantities are read from the link's
    cumulative-count arrays at a given step.

    Attributes:
        links_by_id: Mapping ``link_id -> link`` for every real and connector link.
        step: The current simulation step, updated by the engine each step.
    """

    def __init__(
        self,
        links_by_id: dict[int, Link],
        out_links: dict[NodeId, list[int]],
        in_links: dict[NodeId, list[int]],
        origin_nodes: dict[NodeId, OriginNode],
        node_positions: dict[NodeId, tuple[float, float] | None],
        endpoints: dict[int, tuple[NodeId, NodeId]],
        nodes_by_id: dict[NodeId, BaseNode] | None = None,
    ) -> None:
        """Create a network state view.

        Args:
            links_by_id: ``link_id -> link`` for all links.
            out_links: ``node_id -> list[link_id]`` of real outbound links.
            in_links: ``node_id -> list[link_id]`` of real inbound links.
            origin_nodes: ``node_id -> OriginNode`` for nodes that inject demand.
            node_positions: ``node_id -> (x, y)`` (may be empty).
            endpoints: ``link_id -> (u, v)`` node endpoints for each real link.
            nodes_by_id: ``node_id -> junction node model`` for every through
                junction (used by :meth:`movement_demand`); may be empty.
        """
        self.links_by_id = links_by_id
        self._out_links = out_links
        self._in_links = in_links
        self._origin_nodes = origin_nodes
        self._node_positions = node_positions
        self._endpoints = endpoints
        self._nodes_by_id = nodes_by_id or {}
        self.step = 0

        # Simulation step dt (s), set by Network.compile; used to default the
        # departure time of injected vehicles to the current step.
        self.time_step: float = 0.0

        # Connector topology, populated by Network.compile (empty for hand-built
        # networks): where each link feeds, and the O/D connector link ids.
        self.downstream_node: dict[int, NodeId] = {}
        self.sink_connectors: dict[NodeId, int] = {}
        self.source_connectors: dict[NodeId, int] = {}

        # Dynamic-injection budget the connectors were sized for (set by
        # Network.compile) and a running count of injected vehicles, used to warn
        # when more vehicles are injected than the buffers can be guaranteed to hold.
        self.injection_budget: int = 0
        self._injected_count: int = 0

    # -- topology --------------------------------------------------------------

    def nodes(self) -> list[NodeId]:
        """Return all node identifiers in the network."""
        return list(self._node_positions.keys())

    def link_ids(self) -> list[int]:
        """Return all link identifiers (real and connector)."""
        return list(self.links_by_id.keys())

    def out_links(self, node_id: NodeId) -> list[int]:
        """Return the real outbound link ids of ``node_id``."""
        return list(self._out_links.get(node_id, []))

    def in_links(self, node_id: NodeId) -> list[int]:
        """Return the real inbound link ids of ``node_id``."""
        return list(self._in_links.get(node_id, []))

    def links_between(self, u: NodeId, v: NodeId) -> list[int]:
        """Return all real link ids going directly from node ``u`` to node ``v``."""
        return [lid for lid, (a, b) in self._endpoints.items() if a == u and b == v]

    def endpoints(self, link_id: int) -> tuple[NodeId, NodeId] | None:
        """Return the ``(u, v)`` node endpoints of a real link, or ``None``."""
        return self._endpoints.get(link_id)

    def position(self, node_id: NodeId) -> tuple[float, float] | None:
        """Return the ``(x, y)`` position of ``node_id`` if one was given."""
        return self._node_positions.get(node_id)

    # -- static link attributes ------------------------------------------------

    def length(self, link_id: int) -> float:
        """Return the length (m) of a link."""
        return self.links_by_id[link_id].length

    def capacity(self, link_id: int) -> float:
        """Return the capacity (veh/s) of a link."""
        # Triangular-FD capacity C = rho_jam*v_f*w/(v_f+w); recomputed from the FD
        # parameters so it is valid even before the link's start() has run.
        link = self.links_by_id[link_id]
        return link.rho_jam * link.v_f * link.w / (link.v_f + link.w)

    def continuous_free_flow_time(self, link_id: int) -> float:
        """Return the continuous-time free-flow travel time (s) of a link.

        This is the continuous LTM value ``length / v_f`` — the exact time a vehicle
        would need to traverse the link at free-flow speed, **independent of the
        simulation time step**. The discrete model advances vehicles in whole steps,
        so the *achievable* free-flow time is instead the link's integer wave lag
        ``T1 * dt`` (see :func:`mesoltm.metrics.free_flow_time` for the route-level
        discrete value). Use this continuous value where a fine-grained, dt-agnostic
        cost is wanted (e.g. as a routing edge weight).
        """
        link = self.links_by_id[link_id]
        return link.length / link.v_f

    # -- live state ------------------------------------------------------------

    def vehicles_on(self, link_id: int) -> list[Vehicle]:
        """Return the vehicles currently queued on a link (live)."""
        return list(self.links_by_id[link_id].vehicles)

    def occupancy(self, link_id: int) -> int:
        """Return the number of vehicles currently on a link (live)."""
        return len(self.links_by_id[link_id].vehicles)

    def density(self, link_id: int) -> float:
        """Return the current density (veh/m) of a link (live)."""
        link = self.links_by_id[link_id]
        return len(link.vehicles) / link.length

    def entry_queue(self, node_id: NodeId) -> int:
        """Return the number of vehicles waiting to enter at an origin node."""
        node = self._origin_nodes.get(node_id)
        if node is None:
            return 0

        return len(node.vehicles)

    def waiting_vehicles(self, node_id: NodeId) -> list[Vehicle]:
        """Return the vehicles waiting in an origin's vertical entry queue (live).

        These are vehicles whose departure time has passed but that the first
        link has not yet admitted (see :class:`~mesoltm.core.nodes.origin_node`).
        Unlike :meth:`entry_queue` (a count), this returns the vehicles
        themselves so callers (e.g. the animation recorder) can read each one's
        id, next link and category. Empty for non-origin nodes.
        """
        node = self._origin_nodes.get(node_id)
        return list(node.vehicles) if node is not None else []

    # -- dynamic demand --------------------------------------------------------

    def inject(
        self,
        node_id: NodeId,
        vehicle: Vehicle,
        at_time: float | None = None,
        check_reentry_node: bool = True,
    ) -> None:
        """Add a vehicle to an origin's demand during the run (dynamic injection).

        The vehicle's ``route`` is treated as a sequence of *real* link ids; the
        origin/destination connector links are spliced on automatically (matching
        how static demand is compiled), so external callers only ever reason about
        real links. The vehicle then joins the origin's departure queue in
        departure-time order and is released like any other vehicle.

        The **same** vehicle may be injected repeatedly to make several trips, each
        recorded as its own journey (see
        :attr:`~mesoltm.core.vehicle.Vehicle.journeys`). Two guardrails protect
        re-injection:

        * The vehicle must not still be moving through, or waiting to enter, the
          network — its previous journey must have completed (it was absorbed at a
          destination). Otherwise a :class:`RuntimeError` is raised.
        * By default the vehicle must re-enter at the **same real node** where it
          last left the network (its previous journey's final real link's downstream
          node — auxiliary O/D connector nodes are never considered). A mismatch
          raises :class:`ValueError`; pass ``check_reentry_node=False`` to allow a
          deliberate re-entry elsewhere.

        If the number of injections exceeds the ``injection_budget`` the connectors
        were sized for (see :meth:`~mesoltm.network.network.Network.compile`), a
        :class:`RuntimeWarning` is emitted: the connector buffer may then be too
        small to admit the vehicle promptly, so it waits in the origin queue (and
        may not enter within the horizon) rather than being silently discarded.

        Args:
            node_id: An origin node (marked via ``Network.set_origin``).
            vehicle: The vehicle to inject; ``scheduled_departure``, ``route`` and
                ``position`` are set here (and the live journey state reset on
                re-injection).
            at_time: Departure time in seconds; defaults to the current step's
                time (``step * dt``) so it is considered in the next step.
            check_reentry_node: When re-injecting an already-used vehicle, require
                it to re-enter at the real node it last left from. Defaults to
                ``True``.

        Raises:
            ValueError: If ``node_id`` is not a registered origin node, or (on
                re-injection with ``check_reentry_node``) the vehicle last left the
                network at a different real node.
            RuntimeError: If the vehicle is still active (its current journey has
                not completed).
        """
        origin = self._origin_nodes.get(node_id)
        if origin is None:
            raise ValueError(
                f"cannot inject at {node_id!r}: it is not an origin "
                f"(call Network.set_origin before compile)"
            )
        if vehicle.active:
            raise RuntimeError(
                f"cannot inject vehicle {vehicle.vehicle_id!r} at {node_id!r}: it is "
                f"still active in the network (its current journey has not completed). "
                f"Wait until it is absorbed at a destination before re-injecting it."
            )

        if vehicle.journeys:
            # Re-injection: reset the live journey state and (by default) verify the
            # vehicle re-enters at the real node where it last left the network.
            if check_reentry_node:
                exit_node = self._journey_exit_node(vehicle.journeys[-1])
                if exit_node is not None and exit_node != node_id:
                    raise ValueError(
                        f"cannot re-inject vehicle {vehicle.vehicle_id!r} at "
                        f"{node_id!r}: it last left the network at node {exit_node!r}. "
                        f"Re-enter it there, or pass check_reentry_node=False."
                    )
            vehicle.reset_for_new_journey()

        self._splice_injection_route(node_id, vehicle)
        vehicle.scheduled_departure = (
            self.step * self.time_step if at_time is None else at_time
        )
        origin.add_trip(vehicle)

        # Warn if more vehicles are injected than the connectors were sized for: the
        # access buffers may then be too small to admit this vehicle promptly.
        self._injected_count += 1
        if self._injected_count > self.injection_budget:
            warnings.warn(
                f"Injected {self._injected_count} vehicle(s), exceeding the "
                f"injection_budget of {self.injection_budget} the connectors were "
                f"sized for. Vehicle {vehicle.vehicle_id!r} was added to the "
                f"departure queue of origin {node_id!r}, but the access (connector) "
                f"buffer may be full, in which case the vehicle waits in that queue "
                f"and enters the network only once space frees up — it may be "
                f"delayed and, if space never frees within the horizon, may not "
                f"enter at all. It is never silently discarded. Re-run with "
                f"injection_budget >= the number of vehicles you inject.",
                RuntimeWarning,
                stacklevel=2,
            )

    def _splice_injection_route(self, node_id: NodeId, vehicle: Vehicle) -> None:
        """Wrap a real-link route with its origin/destination connector links.

        Mirrors ``Network._splice_routes``: prepend the origin's source connector
        (if any) and append the destination's sink connector (if any), then reset
        the vehicle's position pointer to the start of the spliced route.
        """
        real_route = list(vehicle.route or [])
        route: list[int] = []
        source = self.source_connectors.get(node_id)
        if source is not None:
            route.append(source)
        route.extend(real_route)
        self._append_sink_connector(route)
        vehicle.route = route
        vehicle.position = 0

    def _append_sink_connector(self, route: list[int]) -> None:
        """Append the destination access connector for a real-link ``route``.

        The destination is the downstream node of the last real link; if that node
        has a sink connector, it is appended so the vehicle is absorbed there.
        """
        if not route:
            return
        endpoint = self._endpoints.get(route[-1])
        dest_node = endpoint[1] if endpoint is not None else None
        sink = self.sink_connectors.get(dest_node)
        if sink is not None:
            route.append(sink)

    def _journey_exit_node(self, journey: dict) -> NodeId | None:
        """Return the real node at which a completed ``journey`` left the network.

        This is the downstream node of the journey's last **real** (non-connector)
        link. Connector links have no ``endpoints`` entry, so they are naturally
        excluded — only actual network nodes are ever returned, never an auxiliary
        O/D connector node. Returns ``None`` if the journey never reached a real
        link (e.g. it only crossed connectors).
        """
        for segment in reversed(journey["trajectory"]):
            endpoint = self._endpoints.get(segment["link_id"])
            if endpoint is not None:
                return endpoint[1]

        return None

    # -- rerouting -------------------------------------------------------------

    def vehicles_in_network(self) -> list[VehicleView]:
        """Return a snapshot of every vehicle currently on a real link.

        Used by :class:`~mesoltm.plugins.plugin.ReroutingPlugin`: each view
        carries the vehicle, the link it is on, its remaining real-link route and
        its destination. Connector links are skipped — a vehicle on an access
        connector has no downstream choice to reroute yet. Called at the start of a
        step (before flows), when every vehicle is on exactly one link.
        """
        views: list[VehicleView] = []
        for link_id, link in self.links_by_id.items():
            if self._endpoints.get(link_id) is None:
                continue  # connector: not a routing edge, skip

            for vehicle in link.vehicles:
                views.append(
                    VehicleView(
                        vehicle=vehicle,
                        link_id=link_id,
                        route=self.remaining_real_route(vehicle, link_id),
                        destination=vehicle.destination,
                    )
                )
        return views

    def movement_demand(self, node_id: NodeId, out_link_id: int) -> list[VehicleView]:
        """Return the vehicles demanding to cross onto one outbound link this step.

        For the movement at ``node_id`` toward ``out_link_id``, returns one
        :class:`VehicleView` per vehicle whose next link resolves to ``out_link_id``,
        taken from the current sending flow of the node's inbound links — real
        approaches *and* any origin connector, whose queued vehicles also carry
        routes that may load this movement — in FIFO order (``len(...)`` is the
        count). Each view carries the vehicle and the inbound link it is on, so a
        caller can ration the movement and reroute the rest with :meth:`set_route`.

        Next-link resolution matches the node model (an attached routing policy, else
        the vehicle's own route). It is a **pure query**: it refreshes the inbound
        links' demand for ``self.step`` so it works from a plugin (which runs before
        the demand phase) without changing any flow result. Returns ``[]`` if the
        node has no through-junction model.

        Args:
            node_id: The junction the movement is at.
            out_link_id: The outbound (downstream) link id of the movement.
        """
        node = self._nodes_by_id.get(node_id)
        if node is None:
            warnings.warn(
                f"movement_demand: node {node_id!r} has no through-junction model; "
                f"returning no demand.",
                RuntimeWarning,
                stacklevel=2,
            )
            return []

        return [
            VehicleView(
                vehicle=vehicle,
                link_id=inbound_link_id,
                route=self.remaining_real_route(vehicle, inbound_link_id),
                destination=vehicle.destination,
            )
            for vehicle, inbound_link_id in node.demand_for_outbound(
                out_link_id, self.step
            )
        ]

    def remaining_real_route(
        self, vehicle: Vehicle, current_link_id: int | None = None
    ) -> list[int]:
        """Return the real (non-connector) links of ``vehicle.route``, forward-only.

        This reads ``vehicle.route`` (the plan the vehicle already carries) and
        never recomputes a route: the recorder and rerouting logic use it so the
        logged/replaced plan always matches what actually ran. When
        ``current_link_id`` lies on the route the tail from there onward is
        returned (starting with the current link); otherwise — e.g. a vehicle
        still queued at its origin, not yet on a real link — the full real route
        is returned.
        """
        real = [lid for lid in vehicle.route if self._endpoints.get(lid) is not None]
        if current_link_id is not None and current_link_id in real:
            return real[real.index(current_link_id) :]

        return real

    def set_route(self, vehicle: Vehicle, real_route: list[int]) -> None:
        """Replace an in-network vehicle's route with a new real-link route.

        The new route must start at the link the vehicle is currently on — the
        vehicle keeps moving, so its remaining plan can only be rewritten from
        where it is. We read the current link from ``route[position]`` (the pointer
        the movement logic keeps in sync) and reject a mismatch, so a bad update
        can never silently strand the vehicle. The destination access connector is
        re-attached and the position pointer reset to the (unchanged) current link,
        so :meth:`Vehicle.next_link` resolves the new next link seamlessly.

        Args:
            vehicle: An in-network vehicle (see :meth:`vehicles_in_network`).
            real_route: Ordered real link ids from the current link to the
                destination, starting with the current link.

        Raises:
            ValueError: If ``real_route`` is empty or does not start at the
                vehicle's current link.
        """
        pos = vehicle.position
        current = vehicle.route[pos] if 0 <= pos < len(vehicle.route) else None
        if not real_route or real_route[0] != current:
            raise ValueError(
                f"new route for vehicle {vehicle.vehicle_id} must start at its "
                f"current link {current!r}, got {list(real_route)[:1]}"
            )
        route = list(real_route)
        self._append_sink_connector(route)
        vehicle.route = route
        vehicle.position = 0  # vehicle is on route[0] (its current link)

    # -- cumulative state ------------------------------------------------------

    def cumulative_inflow(self, link_id: int, t: int | None = None) -> float:
        """Return cumulative inflow of a link at step ``t`` (default: current step)."""
        # ``self.step`` is kept current by the simulation loop each step.
        t = self.step if t is None else t
        return self.links_by_id[link_id].cumulative_inflows[t]

    def cumulative_outflow(self, link_id: int, t: int | None = None) -> float:
        """Return cumulative outflow of a link at step ``t`` (default: current step)."""
        t = self.step if t is None else t
        return self.links_by_id[link_id].cumulative_outflows[t]
