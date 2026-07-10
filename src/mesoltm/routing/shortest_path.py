# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Shortest-path routing policy over the real network, using networkx."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import networkx as nx

from ..core.ids import NodeId
from ..core.vehicle import Vehicle

if TYPE_CHECKING:
    from ..core.nodes.base_node import BaseNode
    from ..network.state import NetworkState


class ShortestPathPolicy:
    """Routes each vehicle along the current shortest path to its destination.

    At every branching node the policy computes the least-cost path from the node
    the vehicle is entering to ``vehicle.destination`` over the real links, and
    returns the first link on that path. Because it is consulted live at each
    node, rerouting happens automatically as costs change; supply a ``cost``
    function reading the :class:`NetworkState` to make routing congestion-aware.

    Parallel links between two nodes are collapsed to their cheapest option, so a
    slow lane or an inflated-length detour is used only when it is actually the
    faster choice.

    Attributes:
        dynamic: If ``True`` the routing graph is rebuilt on every decision so live
            costs take effect; if ``False`` the free-flow graph is built once.
    """

    def __init__(
        self,
        cost: Callable[[int, NetworkState], float] | None = None,
        dynamic: bool = False,
    ) -> None:
        """Create a shortest-path policy.

        Args:
            cost: Optional ``cost(link_id, state) -> float`` giving each link's
                routing cost, where ``state`` is the live
                :class:`~mesoltm.network.state.NetworkState` (exported as
                ``mesoltm.NetworkState``) — so a congestion-aware cost can read
                ``state.occupancy(link_id)``, ``state.density(link_id)`` etc. with
                full typing. Defaults to the link's free-flow travel time.
            dynamic: Whether to recompute the graph on each decision (needed when
                ``cost`` depends on live state).
        """
        self._cost = cost
        self.dynamic = dynamic
        self._graph: nx.DiGraph | None = None

    def _build_graph(self, state: NetworkState) -> nx.DiGraph:
        """Build a directed graph of real links with the cheapest parallel edge kept."""
        g = nx.DiGraph()
        for lid in state.link_ids():
            ep = state.endpoints(lid)
            if ep is None:
                continue  # skip connectors; they are not routing edges

            u, v = ep
            cost = (
                self._cost(lid, state)
                if self._cost is not None
                else state.free_flow_time(lid)
            )

            if not g.has_edge(u, v) or cost < g[u][v]["cost"]:
                g.add_edge(u, v, cost=cost, link_id=lid)

        return g

    def _graph_for(self, state: NetworkState) -> nx.DiGraph:
        """Return the routing graph, rebuilding it when running in dynamic mode."""
        if self.dynamic or self._graph is None:
            self._graph = self._build_graph(state)

        return self._graph

    def refresh(self, state: NetworkState) -> None:
        """Rebuild the cached routing graph from the live state, once.

        Lets a caller that needs many route lookups against the *same* live state
        (e.g. a rerouting plugin re-planning every vehicle in one step) build the
        dynamic graph a single time, then temporarily set ``dynamic = False`` so
        the lookups reuse it instead of rebuilding it per call.
        """
        self._graph = self._build_graph(state)

    def route(
        self, state: NetworkState, from_node: NodeId, to_node: NodeId
    ) -> list[int]:
        """Return the full shortest real-link route from ``from_node`` to ``to_node``.

        Convenience planner (used e.g. to seed a vehicle's route before injection
        or inside a rerouting plugin). Returns the ordered real link ids, or an
        empty list if the nodes coincide or no path exists. Respects the same cost
        function and ``dynamic`` setting as :meth:`next_link`.
        """
        graph = self._graph_for(state)
        try:
            path = nx.shortest_path(graph, from_node, to_node, weight="cost")

        except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
            raise ValueError(
                f"No path from {from_node} to {to_node} in the routing graph."
            ) from exc

        return [graph[a][b]["link_id"] for a, b in zip(path, path[1:])]

    def next_link(
        self,
        vehicle: Vehicle,
        current_link_id: int,
        node: BaseNode,
        state: NetworkState | None,
    ) -> int | None:
        """Return the first link on the shortest path toward the destination.

        See :class:`~mesoltm.routing.policy.RoutingPolicy` for the argument
        contract (the engine always passes a :class:`NetworkState`; ``None`` yields
        no decision). When the vehicle has arrived at its destination node, the
        destination's sink connector (if any) is returned so it leaves the network.
        """
        if state is None:
            return None
        net_state = state
        arriving_node = net_state.downstream_node.get(current_link_id)
        destination = vehicle.destination

        sink_connectors = net_state.sink_connectors
        if arriving_node == destination and destination in sink_connectors:
            return sink_connectors[destination]

        graph = self._graph_for(net_state)
        try:
            path = nx.shortest_path(graph, arriving_node, destination, weight="cost")
        except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
            raise ValueError(
                f"No path from {arriving_node} to {destination} in the routing graph."
            ) from exc

        if len(path) < 2:
            return None

        return graph[path[0]][path[1]]["link_id"]
