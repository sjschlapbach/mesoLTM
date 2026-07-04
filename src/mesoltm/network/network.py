# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""The :class:`Network` builder: define graphs and compile them to a simulation.

The builder lets users describe a road network as nodes and links (including
parallel links and detours), mark any nodes as origins/destinations, and compile
everything into a ready-to-run :class:`~mesoltm.core.simulation.Simulation`. It
selects the appropriate node model per junction from its in/out degree, builds
capacity-proportional merge priorities, and auto-inserts the connector links and
origin/destination nodes needed so that any node can act as an origin or
destination while vehicles queue only at the origin.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..core.connector_link import ConnectorLink
from ..core.link import Link
from ..core.nodes.destination_node import DestinationNode
from ..core.nodes.diverge_node import DivergeNode
from ..core.nodes.general_node_model import GeneralNodeModel
from ..core.nodes.merge_node import MergeNode
from ..core.nodes.one_to_one_node import OneToOneNode
from ..core.nodes.origin_node import OriginNode
from ..core.simulation import Simulation
from .state import NetworkState

if TYPE_CHECKING:
    from ..routing.policy import RoutingPolicy

DEFAULT_FD = {"v_f": 15.0, "w": 5.0, "rho_jam": 0.15}


def link_capacity(v_f: float, w: float, rho_jam: float) -> float:
    """Return the triangular-FD capacity ``rho_jam * v_f * w / (v_f + w)`` in veh/s."""
    return rho_jam * v_f * w / (v_f + w)


class Network:
    """A mutable description of a road network that compiles to a simulation.

    Attributes:
        default_fd: Default fundamental-diagram parameters (``v_f``, ``w``, ``rho_jam``)
            applied to links that do not specify their own.
    """

    def __init__(self, default_fd: dict | None = None) -> None:
        """Create an empty network.

        Args:
            default_fd: Optional default ``{"v_f", "w", "rho_jam"}`` for links.
        """
        self.default_fd = dict(DEFAULT_FD)
        if default_fd:
            self.default_fd.update(default_fd)
        self._positions: dict = {}
        self._links: dict[int, dict] = {}
        self._next_link_id = 1
        self._origins: dict = {}
        self._destinations: set = set()
        self._priorities: dict = {}
        self._compiled = False

    # -- construction ----------------------------------------------------------

    def add_node(self, node_id: object, pos: tuple | None = None) -> object:
        """Add a node (idempotent) and optionally record its ``(x, y)`` position.

        Args:
            node_id: Any hashable identifier.
            pos: Optional position used for auto link length and plotting.

        Returns:
            The node identifier.
        """
        if node_id not in self._positions or pos is not None:
            self._positions[node_id] = pos
        return node_id

    def add_link(
        self,
        u: object,
        v: object,
        length: float | None = None,
        link_id: int | None = None,
        **fd: float,
    ) -> int:
        """Add a directed link from ``u`` to ``v`` and return its id.

        Multiple links between the same pair are allowed (each gets a distinct
        id): a **slow lane** is a parallel link with lower ``v_f``/``rho_jam``, and a
        **detour** is a parallel link whose ``length`` is larger than the direct
        distance — no intermediate nodes required.

        Args:
            u: Upstream node id (auto-created if new).
            v: Downstream node id (auto-created if new).
            length: Link length in metres. If omitted, uses the Euclidean
                distance between node positions when both are known.
            link_id: Optional explicit id; auto-assigned when omitted.
            **fd: Fundamental-diagram overrides (``v_f``, ``w``, ``rho_jam``).

        Returns:
            The assigned ``link_id``.
        """
        self.add_node(u)
        self.add_node(v)
        if length is None:
            pu, pv = self._positions.get(u), self._positions.get(v)
            if pu is not None and pv is not None:
                length = math.dist(pu, pv)
            else:
                raise ValueError(
                    "length is required when node positions are not both set"
                )
        params = dict(self.default_fd)
        params.update(fd)
        if link_id is None:
            link_id = self._next_link_id
        elif link_id in self._links:
            raise ValueError(f"link_id {link_id} is already used by another link")
        self._next_link_id = max(self._next_link_id, link_id) + 1
        self._links[link_id] = {"u": u, "v": v, "length": length, **params}
        return link_id

    def set_origin(self, node_id: object, vehicles: list | None = None) -> None:
        """Mark a node as an origin and attach demand vehicles to release from it.

        Args:
            node_id: The origin node.
            vehicles: Vehicles to release (routes over real link ids). Additional
                calls append more vehicles.
        """
        self.add_node(node_id)
        self._origins.setdefault(node_id, [])
        if vehicles:
            self._origins[node_id].extend(vehicles)

    def set_destination(self, node_id: object) -> None:
        """Mark a node as a destination that absorbs arriving vehicles."""
        self.add_node(node_id)
        self._destinations.add(node_id)

    def set_merge_priorities(self, node_id: object, alpha: dict) -> None:
        """Override the merge priority shares of a node's inbound links.

        By default a merge/general junction serves its inbound links with priority
        shares ``alpha_i`` proportional to each link's capacity. Call this to set
        the shares explicitly at the point where the node's links are defined —
        e.g. to give a main road priority over a ramp regardless of capacity.

        Args:
            node_id: The merge/general junction whose priorities to set.
            alpha: Mapping ``{inbound_link_id: share}`` of relative priority
                weights (they are normalised internally, so any positive scale
                works). Inbound links not listed — including any auto-inserted
                origin connector — fall back to their capacity-proportional weight.
        """
        self.add_node(node_id)
        self._priorities[node_id] = dict(alpha)

    # -- compilation -----------------------------------------------------------

    def _uses_source_connector(self, node_id: object, real_out: list) -> bool:
        """Return whether an origin needs a source connector (vs. direct attach)."""
        real_in = self._real_in(node_id)
        return not (
            len(real_in) == 0
            and len(real_out) == 1
            and node_id not in self._destinations
        )

    def _uses_sink_connector(self, node_id: object, real_in: list) -> bool:
        """Return whether a destination needs a sink connector (vs. direct attach)."""
        real_out = self._real_out(node_id)
        return not (
            len(real_out) == 0 and len(real_in) == 1 and node_id not in self._origins
        )

    def _real_in(self, node_id: object) -> list[int]:
        """Return real inbound link ids of a node."""
        return [lid for lid, d in self._links.items() if d["v"] == node_id]

    def _real_out(self, node_id: object) -> list[int]:
        """Return real outbound link ids of a node."""
        return [lid for lid, d in self._links.items() if d["u"] == node_id]

    def compile(
        self,
        time_step: float,
        total_time: float,
        routing_policy: RoutingPolicy | None = None,
        plugins: list | None = None,
        injection_budget: int = 0,
    ) -> Simulation:
        """Build links, nodes and connectors and return a runnable simulation.

        Args:
            time_step: Simulation step ``dt`` in seconds.
            total_time: Simulated horizon in seconds.
            routing_policy: Optional policy overriding per-vehicle next-link
                decisions at branching nodes. When omitted, vehicles follow their
                own (connector-spliced) routes.
            plugins: Optional per-step plugins run before flows each step (loop
                hooks, e.g. rerouting logic, link gating, or auctions).
            injection_budget: Upper bound on the number of vehicles that will be
                added dynamically via :meth:`~mesoltm.core.simulation.Simulation.inject`
                during the run. Origin/destination connectors are sized to stay
                transparent for the static demand *plus* this many injections, so a
                dispatcher that injects into an origin carrying little or no static
                demand is not throttled by the connector. A larger value only makes
                connectors more transparent (never more binding), so an over-estimate
                is safe; it does not affect purely static runs.

        Returns:
            A configured :class:`~mesoltm.core.simulation.Simulation`.
        """
        # Compiling splices connector ids into the attached vehicles' routes, so a
        # second compile of the same network would corrupt them — fail loudly.
        if self._compiled:
            raise RuntimeError(
                "compile() may only be called once per Network; rebuild the "
                "network (with fresh Vehicles) for another run"
            )

        # 1. Instantiate all real links.
        links_by_id: dict = {}
        for lid, d in self._links.items():
            links_by_id[lid] = Link(
                link_id=lid,
                length=d["length"],
                v_f=d["v_f"],
                w=d["w"],
                rho_jam=d["rho_jam"],
            )

        endpoints = {lid: (d["u"], d["v"]) for lid, d in self._links.items()}
        out_links = {n: self._real_out(n) for n in self._positions}
        in_links = {n: self._real_in(n) for n in self._positions}

        # Connector ids start far above any user link id so the two never collide.
        connector_id = max(self._links, default=0) + 1_000_000
        # Every connector is sized to buffer/pass the whole vehicle population, so
        # it is never the binding constraint (transparent buffer; see ConnectorLink).
        vehicle_budget = sum(len(v) for v in self._origins.values()) + max(
            0, int(injection_budget)
        )
        source_connectors: dict = {}
        sink_connectors: dict = {}
        origin_node_objs: dict = {}
        nodes: list = []

        # 2. Origins: connector (or direct) + OriginNode; splice routes.
        for node_id, vehicles in self._origins.items():
            real_out = self._real_out(node_id)
            if self._uses_source_connector(node_id, real_out):
                conn = ConnectorLink(
                    link_id=connector_id,
                    time_step=time_step,
                    vehicle_budget=vehicle_budget,
                )
                links_by_id[connector_id] = conn
                source_connectors[node_id] = connector_id
                inject_link = conn
                connector_id += 1
            else:
                inject_link = links_by_id[real_out[0]]

            self._splice_routes(vehicles, source_connectors.get(node_id), endpoints)
            origin = OriginNode(
                node_id=f"{node_id}#origin",
                link=inject_link,
                demand_trips=sorted(vehicles, key=lambda x: x.start),
            )
            origin_node_objs[node_id] = origin
            nodes.append(origin)

        # 3. Destinations: connector (or direct) + DestinationNode.
        for node_id in self._destinations:
            real_in = self._real_in(node_id)
            if self._uses_sink_connector(node_id, real_in):
                conn = ConnectorLink(
                    link_id=connector_id,
                    time_step=time_step,
                    vehicle_budget=vehicle_budget,
                )
                links_by_id[connector_id] = conn
                sink_connectors[node_id] = connector_id
                nodes.append(DestinationNode(node_id=f"{node_id}#dest", link=conn))
                connector_id += 1
            else:
                nodes.append(
                    DestinationNode(
                        node_id=f"{node_id}#dest", link=links_by_id[real_in[0]]
                    )
                )

        # 3b. Sink connectors only exist after step 3, but routes were spliced in
        # step 2, so append each vehicle's sink connector now (keyed by the
        # destination node recorded on the vehicle during splicing).
        for origin in origin_node_objs.values():
            for veh in origin.demand_trips:
                dest_node = getattr(veh, "_dest_node", None)
                if dest_node in sink_connectors:
                    veh.route.append(sink_connectors[dest_node])

        # 4. Junction node models for every node with through/connector movements.
        # downstream_node maps each link to the node it flows into; a source
        # connector flows into its own origin junction (its junction shares node_id).
        downstream_node: dict = {lid: v for lid, (u, v) in endpoints.items()}
        for lid, src in source_connectors.items():
            downstream_node[src] = lid  # source connector feeds its junction

        for node_id in self._positions:
            inbound = [links_by_id[lid] for lid in self._real_in(node_id)]
            outbound = [links_by_id[lid] for lid in self._real_out(node_id)]
            if node_id in source_connectors:
                inbound.append(links_by_id[source_connectors[node_id]])
            if node_id in sink_connectors:
                outbound.append(links_by_id[sink_connectors[node_id]])

            junction = self._build_junction(node_id, inbound, outbound)
            if junction is not None:
                nodes.append(junction)

        # 5. Wire routing policy and shared network state into branching nodes.
        state = NetworkState(
            links_by_id,
            out_links,
            in_links,
            origin_node_objs,
            self._positions,
            endpoints,
        )
        state.downstream_node = downstream_node
        state.sink_connectors = sink_connectors
        state.source_connectors = source_connectors
        state.time_step = time_step

        for node in nodes:
            if isinstance(node, (DivergeNode, GeneralNodeModel)):
                node.routing_policy = routing_policy
                node.network_state = state

        # Wire the shared network state into every user plugin so callers don't
        # have to reach into the compiled simulation to attach it.
        all_plugins: list = list(plugins or [])
        for plugin in all_plugins:
            plugin.state = state

        sim = Simulation(
            links=list(links_by_id.values()),
            nodes=nodes,
            time_step=time_step,
            total_time=total_time,
            plugins=all_plugins,
        )
        sim.network_state = state

        self._compiled = True
        return sim

    # -- helpers ---------------------------------------------------------------

    def _splice_routes(
        self, vehicles: list, source_connector: int | None, endpoints: dict
    ) -> None:
        """Prepend the source connector and append each route's sink connector.

        User routes reference only real links; connectors are inserted here so the
        internal routes are consistent with the junction topology.
        """
        for veh in vehicles:
            if not veh.route:
                continue
            dest_node = endpoints[veh.route[-1]][1]
            new_route: list[int] = []
            if source_connector is not None:
                new_route.append(source_connector)
            new_route.extend(veh.route)
            # The matching sink connector (if any) is spliced during compile once
            # all destinations are known; recorded via a deferred marker.
            veh.route = new_route
            veh.position = 0
            # Compiler bookkeeping stored on the vehicle for the later splice step.
            veh._dest_node = dest_node  # pylint: disable=protected-access

    def _build_junction(
        self, node_id: object, inbound: list, outbound: list
    ) -> object | None:
        """Create the node model for a junction from its inbound/outbound links.

        Returns ``None`` for nodes with no through movement (pure origins or pure
        destinations, whose behaviour is provided by their O/D node instead).
        """
        # Pick the node model from the in/out degree: 1->1 one-to-one, 1->N diverge,
        # N->1 merge, M->N general. Merges/general take capacity-proportional shares.
        ni, no = len(inbound), len(outbound)
        if ni == 0 or no == 0:
            return None
        if ni == 1 and no == 1:
            return OneToOneNode(node_id, inbound[0], outbound[0])
        if ni == 1 and no > 1:
            return DivergeNode(node_id, inbound[0], outbound)
        if ni > 1 and no == 1:
            return MergeNode(
                node_id, outbound[0], inbound, alpha=self._alpha_for(node_id, inbound)
            )
        return GeneralNodeModel(
            node_id, inbound, outbound, alpha=self._alpha_for(node_id, inbound)
        )

    def _alpha_for(self, node_id: object, inbound_links: list) -> list[float]:
        """Return the merge priority shares ``alpha_i`` for a node's inbound links.

        By default each inbound link's share is proportional to its capacity, so
        the merge mimics a capacity/lane-count-proportional yield; a connector
        inbound (which carries injected demand) is weighted like the strongest real
        approach so injected traffic merges fairly without dominating. If explicit
        shares were set via :meth:`set_merge_priorities`, listed links use those
        weights and any unlisted link keeps its capacity-proportional weight. The
        returned shares are normalised to sum to 1.
        """
        override = self._priorities.get(node_id, {})
        real_caps = [
            link_capacity(lk.v_f, lk.w, lk.rho_jam)
            for lk in inbound_links
            if not getattr(lk, "is_connector", False)
        ]
        nominal = max(real_caps) if real_caps else 1.0
        weights = []
        for lk in inbound_links:
            if lk.link_id in override:
                weights.append(max(0.0, float(override[lk.link_id])))
            elif getattr(lk, "is_connector", False):
                weights.append(nominal)
            else:
                weights.append(link_capacity(lk.v_f, lk.w, lk.rho_jam))

        total = sum(weights)
        if total <= 0:
            return [1.0 / len(weights)] * len(weights)
        return [w / total for w in weights]
