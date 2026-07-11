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

"""Demand generation: turn step-wise demand profiles into individual vehicles."""

from __future__ import annotations

import random
from collections.abc import Sequence

from ..core.ids import NodeId
from ..core.vehicle import Vehicle


def vehicles_from_demand_profile(
    demand_pattern: Sequence[float],
    total_time: float,
    route: Sequence[int] | None = None,
    route_integer_share: dict[tuple[int, ...], int] | None = None,
    random_route: bool = False,
    origin: NodeId = 0,
    destination: NodeId = 0,
) -> list[Vehicle]:
    """Expand a piecewise-constant demand profile into individual vehicles.

    Ported from ``abmmeso`` (``demand/trip.py`` ``Trip.from_continuous_demand``).
    Each entry of ``demand_pattern`` is a flow rate (veh/s) that applies over an
    equal-length slice of ``total_time``; vehicles are spaced uniformly within
    each slice. Routes may be a single fixed route or drawn from a share map.

    Args:
        demand_pattern: Sequence of flow rates (veh/s), one per equal time slice.
        total_time: Total horizon in seconds spanned by ``demand_pattern``.
        route: A fixed route (``link_id`` sequence) assigned to every vehicle when
            ``route_integer_share`` is not given.
        route_integer_share: Optional map ``{route_tuple: integer_weight}`` used to
            split vehicles across several routes by integer share.
        random_route: If ``True`` and shares are given, draw each route at random
            (weighted); otherwise assign routes deterministically round-robin.
        origin: Origin identifier stored on every vehicle (bookkeeping).
        destination: Destination identifier stored on every vehicle (bookkeeping).

    Returns:
        A list of :class:`Vehicle` objects sorted by departure time.
    """
    # Duration of one demand slice (each entry of demand_pattern covers this long).
    time_step_demand = total_time / len(demand_pattern)
    vehicles: list[Vehicle] = []

    # Flatten the route-share map into one route per unit of weight, so a route with
    # weight w occupies w consecutive entries; picking round-robin over this list
    # then reproduces the requested integer split exactly.
    share_values: list[tuple[int, ...]] = []
    share_sum = 0
    if route_integer_share is not None:
        share_sum = sum(route_integer_share.values())
        for route_key, weight in route_integer_share.items():
            share_values.extend([route_key for _ in range(weight)])

    for i, demand in enumerate(demand_pattern):
        # Vehicles in this slice = rate * slice duration, floored to a whole count.
        num_trips = int(time_step_demand * demand)
        if num_trips <= 0:
            continue

        # Space them uniformly across the slice (constant headway).
        trip_interval = time_step_demand / num_trips
        interval_trips = [
            Vehicle(
                vehicle_id=len(vehicles) + u,
                origin=origin,
                destination=destination,
                scheduled_departure=time_step_demand * i + u * trip_interval,
                route=route,
            )
            for u in range(num_trips)
        ]

        if route_integer_share is not None:
            for u, vehicle in enumerate(interval_trips):
                if random_route:
                    chosen = random.choice(share_values)
                else:
                    # Deterministic round-robin over the flattened shares, indexed by
                    # the vehicle's global position so the split holds across slices.
                    chosen = share_values[(len(vehicles) + u) % share_sum]
                vehicle.route = list(chosen)

        vehicles.extend(interval_trips)

    return vehicles
