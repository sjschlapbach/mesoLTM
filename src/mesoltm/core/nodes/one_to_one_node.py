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

"""One-to-one node: transfers vehicles between a single inbound and outbound link."""

from __future__ import annotations

from ..base_link import BaseLink
from ..ids import NodeId
from ..vehicle import Vehicle
from .base_node import BaseNode


class OneToOneNode(BaseNode):
    """Moves ``min(inbound demand, outbound supply)`` vehicles across the junction.

    Ported from ``abmmeso`` (``discrete/oneToOneNode.py``). Used where a link
    connects to exactly one downstream link.

    Attributes:
        node_id: Unique node identifier.
        inbound_link: The single upstream link.
        outbound_link: The single downstream link.
    """

    def __init__(
        self, node_id: NodeId, inbound_link: BaseLink, outbound_link: BaseLink
    ) -> None:
        """Create a one-to-one node.

        Args:
            node_id: Unique identifier.
            inbound_link: Upstream link.
            outbound_link: Downstream link.
        """
        super().__init__()
        self.node_id = node_id
        self.inbound_link = inbound_link
        self.outbound_link = outbound_link

    def prepare_step(self, step: int, time: float) -> None:
        """No-op; the transfer happens during flow computation."""

    def compute_flows(self, step: int, time: float) -> None:
        """Transfer the feasible number of vehicles from inbound to outbound.

        Paper Section 3.4.1, Eq. (11): ĝ_u(i) = f̂_d(i) = min{D̂_u(i), Ŝ_d(i)}.
        Since the discrete demand D̂ and supply Ŝ (Eq. 7) are already integers, the
        one-to-one node needs no further rounding — the ``min`` is an integer count
        of vehicles moved from the upstream to the downstream link.
        """
        flow = min(self.inbound_link.get_demand(), self.outbound_link.get_supply())
        vehicles = self.inbound_link.set_outflow(flow, step)
        self.outbound_link.set_inflow(vehicles, step)

    def peek_flows(
        self, step: int, supply_overrides: dict[int, int] | None = None
    ) -> dict[int, list[tuple[Vehicle, int]]]:
        """Predict this step's crossings onto the outbound link, moving nothing.

        Applies Eq. (11) to freshly refreshed demand/supply and peeks the first
        ``min(demand, supply)`` vehicles of the inbound queue instead of moving
        them, so it is a pure query. See :meth:`BaseNode.peek_flows` for the
        contract.
        """
        supply = self._peek_supplies(step, supply_overrides)[0]
        flow = min(self.inbound_link.get_demand(), supply)
        return {
            self.outbound_link.link_id: [
                (self.inbound_link.get_vehicle_from_index(i), self.inbound_link.link_id)
                for i in range(flow)
            ]
        }
