# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.
#
# The traffic-flow logic in this module is adapted from the abmmeso package by
# Felipe de Souza (AGPL-3.0) and follows the model of:
#   F. de Souza, O. Verbas, J. Auld, C. M. J. Tampère, "A mesoscopic
#   link-transmission-model able to track individual vehicles", Simulation
#   Modelling Practice and Theory 140 (2025) 103088.
#   https://doi.org/10.1016/j.simpat.2025.103088

"""Abstract node interface and shared routing helper."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ..base_link import BaseLink
from ..ids import NodeId
from ..vehicle import Vehicle

if TYPE_CHECKING:
    from ...network.state import NetworkState
    from ...routing.policy import RoutingPolicy


class BaseNode:
    """Base class for all node models.

    A node connects inbound links to outbound links and, each step, moves
    vehicles across the junction subject to link demand and supply. Nodes that
    branch (diverge/general) resolve each vehicle's next link through a
    :class:`~mesoltm.routing.policy.RoutingPolicy` attached as ``routing_policy``;
    when unset they fall back to the vehicle's own route, reproducing the
    reference behaviour.

    Attributes:
        node_id: Unique node identifier.
        routing_policy: Optional routing policy overriding next-link decisions.
        network_state: Optional read-only network state passed to the policy.
    """

    node_id: NodeId

    def __init__(self) -> None:
        self.node_id: NodeId = None
        self.routing_policy: RoutingPolicy | None = None
        self.network_state: NetworkState | None = None

    def start(self, time_step: float, total_time: float) -> None:
        """Allocate per-step state for the simulation horizon."""

    def prepare_step(self, step: int, time: float) -> None:
        """Hook run before link demand/supply is computed (e.g. load departures).

        Args:
            step: The current simulation step index.
            time: The current simulation time in seconds (``step * dt``), supplied by
                the simulation (the single owner of the clock) so nodes need not
                store the time step themselves.
        """

    def compute_flows(self, step: int, time: float) -> None:
        """Move vehicles across the node for the current step.

        Args:
            step: The current simulation step index.
            time: The current simulation time in seconds (``step * dt``).
        """

    def get_arrived_trips(self) -> list[dict]:
        """Return records of vehicles that finished their trip at this node."""
        return []

    def _resolve_outbound_index(
        self,
        vehicle: Vehicle,
        current_link_id: int,
        outbound_links: Sequence[BaseLink],
    ) -> int | None:
        """Resolve the index of ``vehicle``'s next outbound link at this node.

        Uses ``routing_policy`` if one is attached, otherwise the vehicle's own
        route. The flow logic in the node is unchanged; only this lookup is
        pluggable.

        Args:
            vehicle: The vehicle being routed.
            current_link_id: The inbound link the vehicle is on.
            outbound_links: The node's candidate outbound links.

        Returns:
            Index into ``outbound_links`` of the chosen link, or ``None`` if the
            chosen link is not among this node's outbound links.
        """
        if self.routing_policy is not None:
            next_id = self.routing_policy.next_link(
                vehicle, current_link_id, self, self.network_state
            )
        else:
            next_id = vehicle.next_link(current_link_id)

        for idx, link in enumerate(outbound_links):
            if link.link_id == next_id:
                return idx

        return None

    def _inbound_links(self) -> list[BaseLink]:
        """Return this node's inbound links as a list (single or many)."""
        many: Sequence[BaseLink] | None = getattr(self, "inbound_links", None)
        if many is not None:
            return list(many)

        single: BaseLink | None = getattr(self, "inbound_link", None)
        return [single] if single is not None else []

    def _outbound_links(self) -> list[BaseLink]:
        """Return this node's outbound links as a list (single or many)."""
        many: Sequence[BaseLink] | None = getattr(self, "outbound_links", None)
        if many is not None:
            return list(many)

        single: BaseLink | None = getattr(self, "outbound_link", None)
        return [single] if single is not None else []

    def peek_flows(
        self, step: int, supply_overrides: dict[int, int] | None = None
    ) -> dict[int, list[tuple[Vehicle, int]]]:
        """Predict this step's crossings per outbound link, without moving anything.

        A read-only replay of this node's own flow algorithm (same priorities,
        FIFO order, per-outbound supply bookkeeping), so — unlike
        :meth:`demand_for_outbound`, which lists everyone *wanting* a movement —
        it returns only the vehicles the node would actually transfer this step.

        Args:
            step: The current simulation step index.
            supply_overrides: Optional ``out_link_id -> supply`` replacing the
                matching outbound links' receiving flow in the replay.

        Returns:
            ``out_link_id -> [(vehicle, inbound_link_id), ...]`` in predicted
            crossing order; every outbound link id is present (possibly empty).
        """
        # The base node moves nothing in compute_flows, so it predicts nothing;
        # every junction model overrides this with a replay of its own algorithm.
        del step, supply_overrides
        return {link.link_id: [] for link in self._outbound_links()}

    def _peek_supplies(
        self, step: int, supply_overrides: dict[int, int] | None
    ) -> list[int]:
        """Refresh demand/supply for ``step`` and return the per-outbound supplies.

        Shared by the :meth:`peek_flows` implementations. Refreshing
        ``compute_demand_and_supplies`` first is what makes the replay see this
        step's sending and receiving flows even before the simulation's demand
        phase (the same pure trick as :meth:`demand_for_outbound`), here applied
        to the outbound links too because the replay consumes their supply.

        Args:
            step: The current simulation step index.
            supply_overrides: Optional ``out_link_id -> supply`` replacing
                ``get_supply()`` for the matching outbound links.

        Returns:
            One supply value per outbound link, in ``_outbound_links()`` order.
        """
        for link in [*self._inbound_links(), *self._outbound_links()]:
            link.compute_demand_and_supplies(step)

        overrides = supply_overrides or {}
        return [
            overrides.get(link.link_id, link.get_supply())
            for link in self._outbound_links()
        ]

    def demand_for_outbound(
        self, out_link_id: int, step: int
    ) -> list[tuple[Vehicle, int]]:
        """Return the vehicles demanding to cross onto one outbound link this step.

        For every inbound link (real approaches *and* any origin connector — its
        queued vehicles carry routes that may point at ``out_link_id`` too), the
        current sending flow (the first ``get_demand()`` vehicles, FIFO) is scanned
        and those whose next link resolves to ``out_link_id`` are kept. Resolution
        uses :meth:`_resolve_outbound_index`, so an attached routing policy is
        honoured exactly as in :meth:`compute_flows` (else the vehicle's own route).

        ``compute_demand_and_supplies(step)`` is called on each inbound link first:
        that is what makes ``get_demand()`` reflect this step's sending flow when the
        query runs before the simulation's demand phase (e.g. from a plugin). It only
        refreshes the transient demand/supply scalars, so the query stays a pure read.

        Returns ``(vehicle, inbound_link_id)`` pairs, in inbound-link then FIFO order.
        """
        demand: list[tuple[Vehicle, int]] = []
        outbound = self._outbound_links()

        for link in self._inbound_links():
            link.compute_demand_and_supplies(step)

            for i in range(link.get_demand()):
                vehicle = link.get_vehicle_from_index(i)
                idx = self._resolve_outbound_index(vehicle, link.link_id, outbound)
                if idx is not None and outbound[idx].link_id == out_link_id:
                    demand.append((vehicle, link.link_id))

        return demand
