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

"""Origin node: injects demand into the network and queues un-admittable vehicles."""

from __future__ import annotations

import bisect

from ..base_link import BaseLink
from ..ids import NodeId
from ..vehicle import Vehicle
from .base_node import BaseNode


class OriginNode(BaseNode):
    """Feeds vehicles onto a link, holding a vertical queue when the link is full.

    Ported from ``abmmeso`` (``discrete/originNode.py``). Vehicles whose departure
    time has passed are released onto the link up to its available supply; any
    excess wait in ``entry_queue`` — the simple, configuration-free entry
    queueing the model relies on. Because a congested downstream lowers the link's
    supply, back-pressure naturally accumulates the queue here at the origin.

    Attributes:
        node_id: Unique node identifier.
        link: The link vehicles are injected onto.
        demand_trips: Vehicles sorted by departure time, not yet released.
        entry_queue: Number of waiting vehicles at the origin by step index.
        outflow: Number of vehicles injected onto the link by step index (kept for
            post-processing).
    """

    def __init__(
        self,
        node_id: NodeId,
        link: BaseLink,
        demand_trips: list[Vehicle],
        **kwargs: object,
    ) -> None:
        """Create an origin node.

        Args:
            node_id: Unique identifier.
            link: The (real or connector) link to inject vehicles onto.
            demand_trips: Vehicles to release, sorted by ``scheduled_departure``.
            **kwargs: Extra attributes set directly on the instance.
        """
        super().__init__()
        self.node_id = node_id
        self.link = link
        self.demand_trips = demand_trips
        self.entry_queue: list[int] = []
        self.outflow: list[int] = []
        self._demand: int = 0
        self.vehicles: list[Vehicle] = []

        for key, value in kwargs.items():
            setattr(self, key, value)

    def start(self, time_step: float, total_time: float) -> None:
        """Allocate the entry-queue and outflow series for the horizon."""
        total_steps = int(total_time / time_step)
        self._demand = 0
        self.entry_queue = [0 for _ in range(total_steps + 1)]
        self.outflow = [0 for _ in range(total_steps)]
        self.vehicles = []

    def prepare_step(self, step: int, time: float) -> None:
        """Move vehicles whose departure time has arrived into the waiting buffer.

        Origins hold a vertical (point) entry queue: vehicles wait here at zero
        length until the first link has supply to admit them, so back-pressure from
        the network builds up at the origin rather than being lost. A vehicle joins
        the waiting buffer once its departure time is reached
        (``scheduled_departure <= time``), i.e. at step ``ceil(scheduled/dt)``.

        This queue-join is the vehicle's **actual departure**: the moment it enters
        the network's origin queue (before any admission to the first link). The
        current simulation ``time`` (passed down from the simulation) is stamped onto
        ``vehicle.departure_time`` here, so travel time is measured from when the
        vehicle really started — which, for a vehicle injected with a departure time
        already in the past, is later than ``ceil(scheduled/dt)`` (it cannot depart
        before it exists).

        Args:
            step: The current simulation step index (unused here; kept for the
                uniform node-step interface).
            time: The current simulation time in seconds (``step * dt``).
        """
        vehicles_departed = 0
        for vehicle in self.demand_trips:
            if vehicle.scheduled_departure <= time:
                vehicle.departure_time = time
                vehicles_departed += 1
                self.vehicles.append(vehicle)
            else:
                break

        self.demand_trips = self.demand_trips[vehicles_departed:]
        self._demand = len(self.vehicles)

    def add_trip(self, vehicle: Vehicle) -> None:
        """Add a vehicle to the pending demand during a run (dynamic injection).

        Inserted in departure-time order so :meth:`prepare_step`'s sorted scan (it
        stops at the first not-yet-departing vehicle) stays valid. Typically called
        via :meth:`~mesoltm.network.state.NetworkState.inject`, which also splices
        on the origin/destination connector links.

        The vehicle is flagged ``active`` here — the single point every vehicle
        (static demand and dynamic injection alike) passes through on its way into
        the network — so re-injection can tell a still-travelling vehicle from an
        idle one.
        """
        vehicle.active = True
        bisect.insort(self.demand_trips, vehicle, key=lambda v: v.scheduled_departure)

    def compute_flows(self, step: int, time: float) -> None:
        """Inject ``min(waiting, link supply)`` vehicles; record the leftover queue.

        The origin's sending flow is the number of vehicles waiting; the admitted
        flow is capped by the first link's discrete supply Ŝ (Eq. 7), so at most
        ``min(waiting, Ŝ)`` whole vehicles enter this step and the rest stay in the
        vertical queue (recorded in ``entry_queue``).

        Args:
            step: The current simulation step index.
            time: The current simulation time in seconds (unused here; kept for the
                uniform node-step interface).
        """
        flow = min(self._demand, self.link.get_supply())
        if flow > 0:
            vehicles = self.vehicles[0:flow]
            self.vehicles = self.vehicles[flow:]
            self.link.set_inflow(vehicles, step)
        else:
            self.link.set_inflow([], step)
        self._demand = 0
        self.entry_queue[step + 1] = len(self.vehicles)
        self.outflow[step] = flow
