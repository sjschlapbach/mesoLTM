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

"""Merge node: several inbound links feeding a single outbound link (priority)."""

from __future__ import annotations

from collections.abc import Sequence

from ..base_link import BaseLink
from ..priorities import priority_vector_from_alpha
from ..ids import NodeId
from ..vehicle import Vehicle
from .base_node import BaseNode


class MergeNode(BaseNode):
    """Merges several inbound links into one outbound link by priority shares.

    Ported from ``abmmeso`` (``discrete/mergeNode.py``). Merge priorities are
    expressed as shares ``alpha_1, alpha_2, ...`` (``alpha[i]`` is the fraction of
    the outbound supply inbound link ``i`` may claim). Internally the ported
    algorithm consumes the equivalent integer ``priority_vector`` — a circular list
    of inbound indices served round-robin (e.g. ``alpha = [0.75, 0.25]`` ⇔
    ``[0, 0, 0, 1]``, serving inbound 0 three times as often as inbound 1). When
    neither is supplied the priorities **default to being proportional to the
    inbound links' capacities** (max flow ``rho_jam*v_f*w/(v_f+w)``), resolved in
    :meth:`start` once those capacities are known.

    Attributes:
        node_id: Unique node identifier.
        outbound_link: The single downstream link.
        inbound_links: Upstream links being merged.
        priority_vector: Circular list of inbound indices encoding merge shares.
        priority_index: Current position in ``priority_vector`` (persists across steps).
    """

    def __init__(
        self,
        node_id: NodeId,
        outbound_link: BaseLink,
        inbound_links: Sequence[BaseLink],
        priority_vector: list[int] | None = None,
        alpha: list[float] | None = None,
    ) -> None:
        """Create a merge node.

        Provide **either** ``priority_vector`` (the reference integer form) **or**
        ``alpha`` (priority shares). If neither is given, the priorities default to
        capacity-proportional (see the class docstring), resolved in :meth:`start`.

        Args:
            node_id: Unique identifier.
            outbound_link: Downstream link.
            inbound_links: List of upstream links.
            priority_vector: Circular list of inbound indices encoding priorities.
            alpha: Priority shares ``alpha_1, alpha_2, ...`` per inbound link;
                converted to a ``priority_vector`` internally.
        """
        super().__init__()
        self.node_id = node_id
        self.outbound_link = outbound_link
        self.inbound_links = inbound_links

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
        """Serve inbound links round-robin by priority until supply runs out.

        Paper Section 3.4.3, Algorithm 2 (the discrete priority merge). The
        continuous merge is Eq. (5), where inbound shares are set by the priorities
        alpha_p (alpha_1 + alpha_2 = 1). Here those shares are encoded as the
        integer ``priority_vector`` (e.g. alpha = [0.75, 0.25] -> [0, 0, 0, 1]) and
        the node walks it round-robin, moving one whole vehicle per served slot from
        the current inbound link into the shared downstream link while its supply
        Ŝ_d >= 1. This keeps every merge flow integer and honours the priorities on
        average without ever splitting a vehicle.

        The walk itself lives in :meth:`_plan_flows` (shared with the read-only
        :meth:`peek_flows`); this method applies the resulting plan.
        """
        inflow_pairs, flow_by_inbound_link, self.priority_index = self._plan_flows(
            downstream_supply=self.outbound_link.get_supply()
        )

        vehicles = [vehicle for vehicle, _ in inflow_pairs]
        for vehicle in vehicles:
            vehicle.advance_to(self.outbound_link.link_id)
        self.outbound_link.set_inflow(vehicles, step)

        for idx_inb, flow in enumerate(flow_by_inbound_link):
            self.inbound_links[idx_inb].set_outflow(flow, step)

    def peek_flows(
        self, step: int, supply_overrides: dict[int, int] | None = None
    ) -> dict[int, list[tuple[Vehicle, int]]]:
        """Predict this step's crossings onto the outbound link, moving nothing.

        Replays the Algorithm 2 walk of :meth:`compute_flows` (shared via
        :meth:`_plan_flows`) against freshly refreshed demands/supplies and
        discards the plan instead of applying it, so it is a pure query. See
        :meth:`BaseNode.peek_flows` for the contract.
        """
        inflow_pairs, _, _ = self._plan_flows(
            downstream_supply=self._peek_supplies(step, supply_overrides)[0]
        )
        return {self.outbound_link.link_id: inflow_pairs}

    def _plan_flows(
        self, downstream_supply: int
    ) -> tuple[list[tuple[Vehicle, int]], list[int], int]:
        """Walk Algorithm 2 and plan this step's transfers, mutating nothing.

        The priority walk of :meth:`compute_flows`, factored out so that
        :meth:`peek_flows` can replay it read-only: demands, cumulative terms and
        the persistent ``priority_index`` are read but never written, and no
        vehicle is moved. The reference arithmetic is unchanged.

        Args:
            downstream_supply: The outbound supply the walk may consume.

        Returns:
            ``(inflow_pairs, flow_by_inbound_link, priority_index)``: the planned
            ``(vehicle, inbound_link_id)`` transfers in crossing order, the
            per-inbound-link flow counts, and the cursor value the node persists
            once the plan is applied.
        """
        remaining_demands = [link.get_demand() for link in self.inbound_links]
        cumulative_terms = [
            link.get_cumulative_demand_term() for link in self.inbound_links
        ]

        flow_by_inbound_link = [0 for _ in self.inbound_links]
        total_flow = 0

        priority_index = self.priority_index
        initial_index = priority_index
        inflow_pairs: list[tuple[Vehicle, int]] = []

        while True:
            idx = self.priority_vector[priority_index]
            approach_with_priority = self.inbound_links[
                self.priority_vector[priority_index]
            ]
            if (
                remaining_demands[idx] == 0
                and cumulative_terms[idx] - flow_by_inbound_link[idx] > 0
            ):
                # A fractional vehicle is pending but not yet a whole one; hold the
                # slot for this approach rather than yielding it.
                break
            elif remaining_demands[idx] < 1:
                priority_index = (priority_index + 1) % len(self.priority_vector)
                if priority_index == initial_index:
                    break
                continue

            if downstream_supply >= 1:
                downstream_supply -= 1
                total_flow += 1
                remaining_demands[self.priority_vector[priority_index]] -= 1
                vehicle = approach_with_priority.get_vehicle_from_index(
                    flow_by_inbound_link[self.priority_vector[priority_index]]
                )
                inflow_pairs.append((vehicle, approach_with_priority.link_id))
                flow_by_inbound_link[self.priority_vector[priority_index]] += 1
                priority_index = (priority_index + 1) % len(self.priority_vector)
                if priority_index == initial_index:
                    break
            else:
                break

        return inflow_pairs, flow_by_inbound_link, priority_index
