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

"""General node model: arbitrary inbound/outbound links with priority merging.

Ported from ``abmmeso`` (``discrete/generalNodeModel.py``). This is the general
LTM node that combines priority-based merging (over inbound links) with
per-vehicle route-based diverging (to outbound links), while locking outbound
links that saturate so blocked movements do not starve others incorrectly. The
only change from the reference is that the outbound link for a vehicle is resolved
through the routing policy instead of reading ``vehicle.route`` inline.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..base_link import BaseLink
from ..priorities import priority_vector_from_alpha
from ..ids import NodeId
from ..vehicle import Vehicle
from .base_node import BaseNode


class GeneralNodeModel(BaseNode):
    """M-inbound by N-outbound node with inbound priority shares (``alpha``).

    Merge priorities among the inbound links are expressed as shares ``alpha_1,
    alpha_2, ...`` and consumed internally as the equivalent integer
    ``priority_vector`` (see :class:`~mesoltm.core.nodes.merge_node.MergeNode`).
    When neither is supplied they default to capacity-proportional, resolved in
    :meth:`start`.

    Attributes:
        node_id: Unique node identifier.
        inbound_links: Upstream links.
        outbound_links: Downstream links.
        priority_vector: Circular list of inbound indices encoding merge shares.
        priority_index: Current position in ``priority_vector`` (persists across steps).
    """

    def __init__(
        self,
        node_id: NodeId,
        inbound_links: Sequence[BaseLink],
        outbound_links: Sequence[BaseLink],
        priority_vector: list[int] | None = None,
        alpha: list[float] | None = None,
    ) -> None:
        """Create a general node.

        Provide **either** ``priority_vector`` **or** ``alpha`` (priority shares).
        If neither is given, the priorities default to capacity-proportional (see
        :class:`~mesoltm.core.nodes.merge_node.MergeNode`), resolved in :meth:`start`.

        Args:
            node_id: Unique identifier.
            inbound_links: List of upstream links.
            outbound_links: List of downstream links.
            priority_vector: Circular list of inbound indices encoding priorities.
            alpha: Priority shares ``alpha_1, alpha_2, ...`` per inbound link;
                converted to a ``priority_vector`` internally.
        """
        super().__init__()
        self.node_id = node_id
        self.inbound_links = inbound_links
        self.outbound_links = outbound_links

        # Explicit vector, or one derived from explicit shares; left empty (and
        # defaulted to capacity-proportional in start()) when neither is given.
        if priority_vector is not None:
            self.priority_vector = priority_vector
        elif alpha is not None:
            self.priority_vector = priority_vector_from_alpha(alpha)
        else:
            self.priority_vector = []

        self.priority_index = 0

    def start(self, time_step: float, total_time: float) -> None:
        """Default the priorities to capacity-proportional if none were given.

        Runs after the links' own ``start`` (the simulation starts links first), so
        each inbound link's capacity is known and can weight the priority vector.
        """
        if not self.priority_vector:
            capacities = [link.get_capacity() for link in self.inbound_links]
            self.priority_vector = priority_vector_from_alpha(capacities)

    def prepare_step(self, step: int, time: float) -> None:
        """No-op; the transfer happens during flow computation."""

    def compute_flows(self, step: int, time: float) -> None:
        """Resolve node flows over all inbound/outbound links for the current step.

        Paper Section 3.4.4, Algorithm 3 (the general M-in x N-out node). It combines
        the priority-vector merge of Algorithm 2 (over inbound links) with the
        per-vehicle FIFO diverge of Algorithm 1 (to outbound links), and adds the
        outbound-locking rule: once an outbound link is saturated (or an inbound
        link has a fractional-but-not-whole vehicle pending) it is locked so a
        blocked movement cannot starve the others. All flows stay integer.
        """
        remaining_supplies = [link.get_supply() for link in self.outbound_links]
        remaining_demands = [link.get_demand() for link in self.inbound_links]
        cumulative_terms = [
            link.get_cumulative_demand_term() for link in self.inbound_links
        ]

        flow_by_inbound_link = [0 for _ in self.inbound_links]
        total_flow = 0

        initial_index = self.priority_index

        flow_order_by_outbound_link: list[list[Vehicle]] = [
            [] for _ in self.outbound_links
        ]
        priority_base = True
        locked_outbound_indices: list[int] = []

        # Seed the round-robin cursor before the loop so it is always bound; the
        # first pass re-sets it to the same value (priority_base starts True), so
        # this is identical to the reference abmmeso algorithm.
        iteration_index = self.priority_index
        while True:
            if priority_base:
                iteration_index = self.priority_index
            idx = self.priority_vector[iteration_index]

            approach_with_priority = self.inbound_links[idx]
            if priority_base:
                if (
                    remaining_demands[idx] == 0
                    and cumulative_terms[idx] - flow_by_inbound_link[idx] > 0
                ):
                    priority_base = False
                    locked_outbound_indices.append(idx)
                    iteration_index = (iteration_index + 1) % len(self.priority_vector)
                    continue

                elif remaining_demands[idx] < 1:
                    self.priority_index = (self.priority_index + 1) % len(
                        self.priority_vector
                    )
                    if self.priority_index == initial_index:
                        break
                    continue
            else:
                if (
                    remaining_demands[idx] == 0
                    and cumulative_terms[idx] - flow_by_inbound_link[idx] > 0
                ):
                    locked_outbound_indices.append(idx)

                if remaining_demands[idx] == 0:
                    iteration_index = (iteration_index + 1) % len(self.priority_vector)
                    if iteration_index == initial_index:
                        break
                    continue

            inb_flow = flow_by_inbound_link[idx]
            vehicle = approach_with_priority.get_vehicle_from_index(inb_flow)
            outbound_index = self._resolve_outbound_index(
                vehicle, approach_with_priority.link_id, self.outbound_links
            )
            if outbound_index is None:
                raise ValueError(
                    f"Vehicle {vehicle.vehicle_id} has no valid next link at "
                    f"node {self.node_id} from link {approach_with_priority.link_id}"
                )

            downstream_supply = remaining_supplies[outbound_index]
            if downstream_supply >= 1 and outbound_index not in locked_outbound_indices:
                remaining_supplies[outbound_index] -= 1

                total_flow += 1
                remaining_demands[idx] -= 1
                vehicle.advance_to(self.outbound_links[outbound_index].link_id)
                flow_order_by_outbound_link[outbound_index].append(vehicle)
                flow_by_inbound_link[idx] += 1

                if priority_base:
                    self.priority_index = (self.priority_index + 1) % len(
                        self.priority_vector
                    )
                    if self.priority_index == initial_index:
                        break
                else:
                    iteration_index = (iteration_index + 1) % len(self.priority_vector)
                    if iteration_index == initial_index:
                        break
            else:
                locked_outbound_indices.append(outbound_index)

                iteration_index = (iteration_index + 1) % len(self.priority_vector)
                if priority_base is False and iteration_index == initial_index:
                    break
                priority_base = False

        for idx_outb, flow in enumerate(flow_order_by_outbound_link):
            self.outbound_links[idx_outb].set_inflow(flow, step)

        for idx_inb, count in enumerate(flow_by_inbound_link):
            self.inbound_links[idx_inb].set_outflow(count, step)
