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
        arrived_vehicles: All vehicles that have completed their trip here.
    """

    def __init__(self, node_id: object, link: BaseLink) -> None:
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

    def start(self, time_step: float, total_time: float) -> None:
        """Allocate the per-step arrival series for the horizon."""
        self.inflow = [0] * int(total_time / time_step)

    def prepare_step(self, t: int) -> None:
        """No-op; destinations act only during flow computation."""

    def compute_flows(self, t: int) -> None:
        """Pull all vehicles ready to leave the link and stamp their arrival step."""
        outflow = self.link.get_demand()
        vehicles = self.link.set_outflow(outflow, t)
        for vehicle in vehicles:
            vehicle.end = t
        self.inflow[t] = outflow
        self.arrived_vehicles.extend(vehicles)

    def get_arrived_trips(self) -> list[dict]:
        """Return per-vehicle arrival records for trip output."""
        records = []
        for vehicle in self.arrived_vehicles:
            records.append(
                {
                    "trip_id": vehicle.vehicle_id,
                    "origin": vehicle.origin,
                    "destination": vehicle.destination,
                    "start": vehicle.start,
                    "end": vehicle.end,
                }
            )
        return records
