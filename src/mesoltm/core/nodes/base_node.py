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
