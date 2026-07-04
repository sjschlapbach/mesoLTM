# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Per-vehicle trip metrics derived from the recorded vehicle trajectories.

Each :class:`~mesoltm.core.vehicle.Vehicle` logs, as it moves, which links it
entered and when (``vehicle.trajectory``). After a run these functions turn that
log into compact per-vehicle records — the route actually driven, the total
travel time (which includes the initial origin-queue/connector access wait), that
access time on its own, and the travel time on each link traversed — keyed by
``vehicle_id`` so the data stays associatable with the exact vehicle seen during
routing (the basis for modelling heterogeneous drivers later). Only the most
important metrics are included for now; more detailed ones can be layered on the
same trajectory data.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from statistics import mean, median
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.simulation import Simulation
    from ..core.vehicle import Vehicle


def trip_record(vehicle: Vehicle, dt: float, include_connectors: bool = False) -> dict:
    """Build the travel-time record for a single completed vehicle.

    The reported ``travel_time`` is the **total** time from the vehicle's desired
    departure to its arrival, so it *includes* the initial time spent waiting in
    the origin queue and crossing the origin's access (connector) link. That
    initial waiting portion is also reported separately as ``access_time`` so the
    two can be distinguished, and the pure in-network time as ``network_time``.

    Args:
        vehicle: A vehicle that has finished its trip (``vehicle.end`` set).
        dt: Simulation step ``dt`` in seconds, used to convert steps to seconds.
        include_connectors: If ``True`` keep auto-inserted O/D connector links in
            ``link_travel_times`` and ``route``; by default only real links are
            reported (connectors are internal access stubs).

    Returns:
        A dict with keys:

        * ``vehicle_id``, ``origin``, ``destination``;
        * ``route`` — the ordered real link ids the vehicle actually drove;
        * ``start_time`` — desired departure (``vehicle.start``);
        * ``network_entry_time`` — when it entered the first real link;
        * ``arrival_time`` — when it was absorbed at the destination;
        * ``travel_time`` — total time in system, ``arrival − start`` (includes
          the initial origin-queue/connector wait);
        * ``access_time`` — initial waiting time in the origin queue and on the
          origin's connector link, ``network_entry − start``;
        * ``network_time`` — in-network time, ``arrival − network_entry``;
        * ``n_links`` and ``link_travel_times`` (``{link_id: seconds}``).

        Time fields are seconds; ``None`` where a value cannot be determined (e.g.
        the vehicle never entered the network).
    """
    # Network entry = the first *real* link. Any leading connector holds the entry
    # queue for its origin (see ConnectorLink); together with the origin's vertical
    # queue this is the vehicle's "access" time before it reaches a real road.
    # Trajectories are chronological; without a connector the first segment is
    # already the first real link.
    real_entry = next(
        (seg for seg in vehicle.trajectory if not seg["is_connector"]), None
    )
    network_entry_step = real_entry["entry_step"] if real_entry is not None else None
    arrival_step = vehicle.end

    # The route actually driven = the real links in the order they were traversed
    # (connectors are internal access stubs, dropped unless explicitly requested).
    route = [
        seg["link_id"]
        for seg in vehicle.trajectory
        if include_connectors or not seg["is_connector"]
    ]

    # Per-link travel time = (exit - entry) steps * dt, skipping connectors (unless
    # asked) and any segment still open at the end of the horizon.
    link_travel_times: dict = {}
    for seg in vehicle.trajectory:
        if seg["is_connector"] and not include_connectors:
            continue
        if seg["exit_step"] is None:
            continue
        link_travel_times[seg["link_id"]] = (seg["exit_step"] - seg["entry_step"]) * dt

    network_entry_time = None if network_entry_step is None else network_entry_step * dt
    arrival_time = None if arrival_step is None else arrival_step * dt

    # access = origin queue + connector wait; network = time on real links; total
    # travel time spans desired departure -> arrival and equals access + network.
    access_time = None
    if network_entry_time is not None:
        access_time = max(0.0, network_entry_time - vehicle.start)
    network_time = None
    if network_entry_time is not None and arrival_time is not None:
        network_time = arrival_time - network_entry_time
    travel_time = None
    if arrival_time is not None:
        travel_time = arrival_time - vehicle.start

    return {
        "vehicle_id": vehicle.vehicle_id,
        "origin": vehicle.origin,
        "destination": vehicle.destination,
        "route": route,
        "start_time": vehicle.start,
        "network_entry_time": network_entry_time,
        "arrival_time": arrival_time,
        "travel_time": travel_time,
        "access_time": access_time,
        "network_time": network_time,
        "n_links": len(link_travel_times),
        "link_travel_times": link_travel_times,
    }


def collect_trips(sim: Simulation, include_connectors: bool = False) -> list[dict]:
    """Collect travel-time records for every completed trip in a finished run.

    Completed trips are gathered from the destination nodes' absorbed vehicles.
    Vehicles still en route or waiting in an origin queue at the end of the horizon
    are not included.

    Args:
        sim: A run :class:`~mesoltm.core.simulation.Simulation`.
        include_connectors: Passed through to :func:`trip_record`.

    Returns:
        A list of per-vehicle records (see :func:`trip_record`), sorted by
        ``vehicle_id``.
    """
    dt = sim.time_step
    records: list[dict] = []
    for node in sim.nodes:
        # Only destination nodes carry ``arrived_vehicles``; the getattr default
        # lets us scan every node without type-checking each one.
        for vehicle in getattr(node, "arrived_vehicles", []):
            records.append(trip_record(vehicle, dt, include_connectors))
    records.sort(key=lambda r: r["vehicle_id"])
    return records


def summarize_trips(trips: list[dict]) -> dict:
    """Aggregate a list of trip records into a compact network-level summary.

    Args:
        trips: Records as returned by :func:`collect_trips`.

    Returns:
        A dict of headline metrics: trip counts, mean/median/min/max total travel
        time (which includes the initial access wait), mean access time, total
        vehicle-hours, and the mean travel time per link. Duration fields are
        ``None`` when there are no completed trips.
    """
    completed = [t for t in trips if t["travel_time"] is not None]
    travel_times = [t["travel_time"] for t in completed]
    access_times = [t["access_time"] for t in completed if t["access_time"] is not None]

    per_link: dict = defaultdict(list)
    for t in completed:
        for link_id, value in t["link_travel_times"].items():
            per_link[link_id].append(value)

    return {
        "n_trips": len(trips),
        "n_completed": len(completed),
        "mean_travel_time": mean(travel_times) if travel_times else None,
        "median_travel_time": median(travel_times) if travel_times else None,
        "min_travel_time": min(travel_times) if travel_times else None,
        "max_travel_time": max(travel_times) if travel_times else None,
        "mean_access_time": mean(access_times) if access_times else None,
        "total_vehicle_hours": sum(travel_times) / 3600.0 if travel_times else 0.0,
        "mean_link_travel_time": {
            link_id: mean(values) for link_id, values in sorted(per_link.items())
        },
    }


def write_trips_csv(trips: list[dict], path: str) -> str:
    """Write trip records to a CSV file (one row per vehicle).

    The ``route`` and per-link travel times are flattened into single columns
    (``"l1;l2;..."`` and ``"link_id:seconds;..."``) so the file stays flat.

    Args:
        trips: Records as returned by :func:`collect_trips`.
        path: Destination file path.

    Returns:
        The path written to.
    """
    fields = [
        "vehicle_id",
        "origin",
        "destination",
        "route",
        "start_time",
        "network_entry_time",
        "arrival_time",
        "travel_time",
        "access_time",
        "network_time",
        "n_links",
        "link_travel_times",
    ]
    flattened = {"route", "link_travel_times"}
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for t in trips:
            row = {k: t[k] for k in fields if k not in flattened}
            row["route"] = ";".join(str(lid) for lid in t["route"])
            row["link_travel_times"] = ";".join(
                f"{lid}:{secs:g}" for lid, secs in t["link_travel_times"].items()
            )
            writer.writerow(row)
    return path
