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

"""Diverge node: one inbound link splitting to several outbound links (FIFO)."""

from __future__ import annotations

from ..base_link import BaseLink
from .base_node import BaseNode


class DivergeNode(BaseNode):
    """Routes each vehicle from one inbound link to its chosen outbound link.

    Ported from ``abmmeso`` (``discrete/divergeNode.py``). Vehicles are served in
    strict first-in-first-out order: the front vehicle advances only if its target
    outbound link has supply; if it is blocked, every vehicle behind it is blocked
    too (FIFO diverge). The target outbound link is resolved through the routing
    policy (defaulting to the vehicle's own route).

    Attributes:
        node_id: Unique node identifier.
        inbound_link: The single upstream link.
        outbound_links: Candidate downstream links.
    """

    def __init__(
        self, node_id: object, inbound_link: BaseLink, outbound_links: list[BaseLink]
    ) -> None:
        """Create a diverge node.

        Args:
            node_id: Unique identifier.
            inbound_link: Upstream link.
            outbound_links: List of downstream links.
        """
        super().__init__()
        self.node_id = node_id
        self.inbound_link = inbound_link
        self.outbound_links = outbound_links

    def prepare_step(self, t: int) -> None:
        """No-op; the transfer happens during flow computation."""

    def compute_flows(self, t: int) -> None:
        """Advance vehicles in FIFO order while their target link has supply.

        Paper Section 3.4.2, Algorithm 1 (the discrete, vehicle-level diverge). The
        continuous counterpart is Eq. (4); here it is replaced by an exact FIFO
        walk that keeps flows integer: process the D̂_u sendable vehicles strictly in
        entry order and push each to its next link while that link still has supply
        Ŝ >= 1. The FIFO discipline means the first vehicle that cannot proceed
        (its target link is full) blocks all vehicles behind it — the loop stops.
        """
        upstream_demand = self.inbound_link.get_demand()
        remaining_supplies = [link.get_supply() for link in self.outbound_links]
        vehicles_by_outbound_link: list[list] = [[] for _ in self.outbound_links]
        total_flow = 0
        while True:
            if upstream_demand == 0:
                break

            # Next sendable vehicle in FIFO order (index into the link's queue).
            front_vehicle = self.inbound_link.get_vehicle_from_index(total_flow)
            idx_outb = self._resolve_outbound_index(
                front_vehicle, self.inbound_link.link_id, self.outbound_links
            )

            if idx_outb is None:
                raise ValueError(
                    f"Vehicle {front_vehicle.vehicle_id} has no valid next link at "
                    f"node {self.node_id} from link {self.inbound_link.link_id}"
                )

            if remaining_supplies[idx_outb] >= 1:
                remaining_supplies[idx_outb] -= 1
                total_flow += 1
                upstream_demand -= 1
                front_vehicle.advance_to(self.outbound_links[idx_outb].link_id)
                vehicles_by_outbound_link[idx_outb].append(front_vehicle)
            else:
                break

        ret_val = self.inbound_link.set_outflow(total_flow, t)
        for idx_outb, vehicles in enumerate(vehicles_by_outbound_link):
            self.outbound_links[idx_outb].set_inflow(vehicles, t)

        assert len(ret_val) == sum(len(vs) for vs in vehicles_by_outbound_link)
