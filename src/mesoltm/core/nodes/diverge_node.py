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

from collections.abc import Sequence

from ..base_link import BaseLink
from ..ids import NodeId
from ..vehicle import Vehicle
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
        self,
        node_id: NodeId,
        inbound_link: BaseLink,
        outbound_links: Sequence[BaseLink],
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

    def prepare_step(self, step: int, time: float) -> None:
        """No-op; the transfer happens during flow computation."""

    def compute_flows(self, step: int, time: float) -> None:
        """Advance vehicles in FIFO order while their target link has supply.

        Paper Section 3.4.2, Algorithm 1 (the discrete, vehicle-level diverge). The
        continuous counterpart is Eq. (4); here it is replaced by an exact FIFO
        walk that keeps flows integer: process the D̂_u sendable vehicles strictly in
        entry order and push each to its next link while that link still has supply
        Ŝ >= 1. The FIFO discipline means the first vehicle that cannot proceed
        (its target link is full) blocks all vehicles behind it — the loop stops.

        The walk itself lives in :meth:`_plan_flows` (shared with the read-only
        :meth:`peek_flows`); this method applies the resulting plan.
        """
        pairs_by_outbound_link = self._plan_flows(
            remaining_supplies=[link.get_supply() for link in self.outbound_links]
        )
        total_flow = sum(len(pairs) for pairs in pairs_by_outbound_link)

        for idx_outb, pairs in enumerate(pairs_by_outbound_link):
            for vehicle, _ in pairs:
                vehicle.advance_to(self.outbound_links[idx_outb].link_id)

        ret_val = self.inbound_link.set_outflow(total_flow, step)
        for idx_outb, pairs in enumerate(pairs_by_outbound_link):
            self.outbound_links[idx_outb].set_inflow([v for v, _ in pairs], step)

        assert len(ret_val) == total_flow

    def peek_flows(
        self, step: int, supply_overrides: dict[int, int] | None = None
    ) -> dict[int, list[tuple[Vehicle, int]]]:
        """Predict this step's crossings per outbound link, without moving anything.

        Replays the Algorithm 1 FIFO walk of :meth:`compute_flows` (shared via
        :meth:`_plan_flows`) — including its front-blocking discipline — against
        freshly refreshed demands/supplies and discards the plan instead of
        applying it, so it is a pure query. See :meth:`BaseNode.peek_flows` for
        the contract.
        """
        pairs_by_outbound_link = self._plan_flows(
            remaining_supplies=self._peek_supplies(step, supply_overrides)
        )
        return {
            link.link_id: pairs_by_outbound_link[idx]
            for idx, link in enumerate(self.outbound_links)
        }

    def _plan_flows(
        self, remaining_supplies: list[int]
    ) -> list[list[tuple[Vehicle, int]]]:
        """Walk Algorithm 1 and plan this step's transfers, mutating nothing.

        The FIFO walk of :meth:`compute_flows`, factored out so that
        :meth:`peek_flows` can replay it read-only: demands are read but never
        written, and no vehicle is moved. The reference arithmetic is unchanged.

        Args:
            remaining_supplies: Per-outbound-link supply the walk may consume
                (consumed in place; pass a fresh list).

        Returns:
            The planned ``(vehicle, inbound_link_id)`` transfers per outbound
            link, in crossing order.
        """
        upstream_demand = self.inbound_link.get_demand()
        pairs_by_outbound_link: list[list[tuple[Vehicle, int]]] = [
            [] for _ in self.outbound_links
        ]
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
                pairs_by_outbound_link[idx_outb].append(
                    (front_vehicle, self.inbound_link.link_id)
                )
            else:
                break

        return pairs_by_outbound_link
