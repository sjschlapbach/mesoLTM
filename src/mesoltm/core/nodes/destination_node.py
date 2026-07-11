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

"""Destination node: absorbs vehicles that have reached the end of their route."""

from __future__ import annotations

from ..base_link import BaseLink
from ..ids import NodeId
from ..vehicle import Vehicle
from .base_node import BaseNode


class DestinationNode(BaseNode):
    """Removes arriving vehicles from a link and records their arrival time.

    Ported from ``abmmeso`` (``discrete/destinationNode.py``). A destination always
    accepts the full downstream demand of its link, so it never constrains flow.

    Attributes:
        node_id: Unique node identifier.
        link: The link whose arrivals are absorbed.
        inflow: Number of vehicles absorbed by step index (kept for post-processing).
        arrived_vehicles: The vehicle objects absorbed here, in arrival order (an
            event log; a re-injected vehicle that arrives twice appears twice).
        completed_journeys: The completed-journey records that ended here, one per
            arrival. Each entry is the *same* dict object appended to the vehicle's
            :attr:`~mesoltm.core.vehicle.Vehicle.journeys` — there is exactly one
            journey record per completed trip (the single source of truth); this
            list is just the per-destination index the trip metrics aggregate over
            (see :func:`mesoltm.metrics.collect_trips`).
    """

    def __init__(self, node_id: NodeId, link: BaseLink) -> None:
        """Create a destination node.

        Args:
            node_id: Unique identifier.
            link: The (real or connector) link feeding this destination.
        """
        super().__init__()
        self.node_id = node_id
        self.link = link
        self.inflow: list[int] = []
        self.arrived_vehicles: list[Vehicle] = []
        self.completed_journeys: list[dict] = []

    def start(self, time_step: float, total_time: float) -> None:
        """Allocate the per-step arrival series for the horizon."""
        self.inflow = [0] * int(total_time / time_step)

    def prepare_step(self, t: int) -> None:
        """No-op; destinations act only during flow computation."""

    def compute_flows(self, t: int) -> None:
        """Pull all vehicles ready to leave the link and record their journeys.

        For each arriving vehicle the just-finished trip is frozen into a journey
        record (:meth:`~mesoltm.core.vehicle.Vehicle.snapshot_journey`) and appended
        both to the vehicle's ``journeys`` (its own history, and the guard used when
        it is re-injected) and to this node's ``completed_journeys`` (the per-
        destination index the metrics read). The vehicle is marked idle
        (``active = False``) so it may be injected again for a further trip.
        """
        outflow = self.link.get_demand()
        vehicles = self.link.set_outflow(outflow, t)
        for vehicle in vehicles:
            vehicle.end = t
            vehicle.active = False
            journey = vehicle.snapshot_journey()
            vehicle.journeys.append(journey)
            self.completed_journeys.append(journey)
        self.inflow[t] = outflow
        self.arrived_vehicles.extend(vehicles)

    def get_arrived_trips(self) -> list[dict]:
        """Return one arrival record per completed journey that ended here."""
        records = []
        for journey in self.completed_journeys:
            records.append(
                {
                    "trip_id": journey["vehicle_id"],
                    "journey_index": journey["journey_index"],
                    "origin": journey["origin"],
                    "destination": journey["destination"],
                    "start": journey["start"],
                    "end": journey["end"],
                }
            )
        return records
