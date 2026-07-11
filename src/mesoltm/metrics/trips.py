# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Per-journey trip metrics derived from the recorded vehicle trajectories.

As a :class:`~mesoltm.core.vehicle.Vehicle` moves it logs which links it entered
and when; when it is absorbed at a destination that finished trip is frozen into a
**journey record** on ``vehicle.journeys`` (the single source of truth for a
vehicle's completed trips). These functions turn each journey record into a compact
trip record — the route actually driven, the travel time (desired departure to
arrival, less each connector's one-step free-flow lag but keeping any supply-limited
connector wait), that access time on its own, and the travel time on each link
traversed.

Because every completed trip — whether it came from a static demand profile (one
vehicle, one journey) or from a hand-injected and re-injected vehicle (one vehicle,
many journeys) — is recorded the same way, the metrics have a single, uniform
accounting path. Records are keyed by ``(vehicle_id, journey_index)``: a vehicle
that made one trip yields ``journey_index = 0``, a re-injected one yields ``0, 1,
…`` in order. Only the most important metrics are included for now; more detailed
ones can be layered on the same journey data.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from statistics import mean, median
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.simulation import Simulation


def trip_record(journey: dict, dt: float, include_connectors: bool = False) -> dict:
    """Build the travel-time record for a single completed journey.

    The reported ``travel_time`` is the time from the vehicle's desired departure
    to its arrival, **minus the artificial one-step free-flow lag that each
    auto-inserted O/D connector imposes** (a one-cell connector always costs one
    free-flow step to cross, even when empty and unrestricted). Time a vehicle
    spends on a connector *beyond* that one step is **kept**: it is a genuine
    supply-limited wait to enter or leave the network (downstream space was the
    binding constraint). ``travel_time`` splits into ``access_time`` (origin-queue
    wait plus any supply-limited connector wait) and ``network_time`` (time on real
    links only), so ``travel_time == access_time + network_time``; ``network_time``
    reflects only real links and is unaffected by connectors.

    Args:
        journey: A completed journey record as produced by
            :meth:`~mesoltm.core.vehicle.Vehicle.snapshot_journey` and stored on
            ``vehicle.journeys`` / a destination's ``completed_journeys``.
        dt: Simulation step ``dt`` in seconds, used to convert steps to seconds.
        include_connectors: If ``True`` keep auto-inserted O/D connector links in
            ``link_travel_times`` and ``route``; by default only real links are
            reported (connectors are internal access stubs).

    Returns:
        A dict with keys:

        * ``vehicle_id``, ``journey_index``, ``origin``, ``destination``;
        * ``route`` — the ordered real link ids the vehicle actually drove;
        * ``start_time`` — desired departure (the journey's ``start``);
        * ``network_entry_time`` — when it entered the first real link;
        * ``arrival_time`` — when it was absorbed at the destination;
        * ``travel_time`` — time in system from desired departure to arrival, with
          each connector's one-step free-flow lag removed (supply-limited connector
          waiting is kept);
        * ``access_time`` — the part of ``travel_time`` not spent on real links:
          origin-queue wait plus any supply-limited O/D connector wait,
          ``travel_time − network_time``;
        * ``network_time`` — time on real links only (connector-free);
        * ``n_links`` and ``link_travel_times`` (``{link_id: seconds}``).

        Time fields are seconds; ``None`` where a value cannot be determined (e.g.
        the vehicle never entered the network).
    """
    trajectory = journey["trajectory"]

    # Network entry = the first *real* link. Any leading connector holds the entry
    # queue for its origin (see ConnectorLink); together with the origin's vertical
    # queue this is the vehicle's "access" time before it reaches a real road.
    # Trajectories are chronological; without a connector the first segment is
    # already the first real link.
    real_entry = next((seg for seg in trajectory if not seg["is_connector"]), None)
    network_entry_step = real_entry["entry_step"] if real_entry is not None else None
    arrival_step = journey["end"]

    # The route actually driven = the real links in the order they were traversed
    # (connectors are internal access stubs, dropped unless explicitly requested).
    route = [
        seg["link_id"]
        for seg in trajectory
        if include_connectors or not seg["is_connector"]
    ]

    # Per-link travel time = (exit - entry) steps * dt, skipping connectors (unless
    # asked) and any segment still open at the end of the horizon.
    link_travel_times: dict[int, float] = {}
    for seg in trajectory:
        if seg["is_connector"] and not include_connectors:
            continue
        if seg["exit_step"] is None:
            continue
        link_travel_times[seg["link_id"]] = (seg["exit_step"] - seg["entry_step"]) * dt

    network_entry_time = None if network_entry_step is None else network_entry_step * dt
    arrival_time = None if arrival_step is None else arrival_step * dt

    # network = time actually spent on *real* links (connector-free), summed from
    # the non-connector trajectory segments. Independent of ``include_connectors``,
    # which only controls what appears in ``route``/``link_travel_times``.
    network_time: float | None = None
    for seg in trajectory:
        if seg["is_connector"] or seg["exit_step"] is None:
            continue
        network_time = (network_time or 0.0) + (
            seg["exit_step"] - seg["entry_step"]
        ) * dt

    # Each O/D connector is a one-cell link with a free-flow crossing lag of exactly
    # one step (T1 = T2 = 1). That one step is a modelling artifact — a vehicle
    # incurs it even on an empty, unrestricted connector — so it is removed from the
    # reported travel time. Time spent on a connector *beyond* that one step is NOT
    # removed: it is a genuine supply-limited wait (downstream space was the binding
    # constraint), i.e. time the vehicle really would have waited to enter/leave the
    # network, so it stays part of travel_time (as access).
    connector_free_flow_lag = 0.0
    for seg in trajectory:
        if seg["is_connector"] and seg["exit_step"] is not None:
            crossing = (seg["exit_step"] - seg["entry_step"]) * dt
            connector_free_flow_lag += min(crossing, dt)

    # travel_time = desired departure -> arrival, minus each connector's one-step
    # free-flow lag; access = the part not spent on real links (origin-queue wait +
    # any supply-limited connector wait), so the identity
    # ``travel_time == access_time + network_time`` always holds.
    travel_time = None
    if arrival_time is not None:
        travel_time = max(
            0.0, arrival_time - journey["start"] - connector_free_flow_lag
        )
    access_time = None
    if travel_time is not None and network_time is not None:
        access_time = max(0.0, travel_time - network_time)
    elif travel_time is not None:
        access_time = travel_time

    return {
        "vehicle_id": journey["vehicle_id"],
        "journey_index": journey["journey_index"],
        "origin": journey["origin"],
        "destination": journey["destination"],
        "route": route,
        "start_time": journey["start"],
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

    Completed trips are gathered from the destination nodes' recorded journeys —
    one record per completed journey. A vehicle from a static demand profile
    contributes one journey; a hand-injected vehicle that was re-injected
    contributes one per trip. Vehicles still en route or waiting in an origin queue
    at the end of the horizon have no completed journey and are not included.

    Args:
        sim: A run :class:`~mesoltm.core.simulation.Simulation`.
        include_connectors: Passed through to :func:`trip_record`.

    Returns:
        A list of per-journey records (see :func:`trip_record`), sorted by
        ``(vehicle_id, journey_index)``.
    """
    dt = sim.time_step
    records: list[dict] = []
    for node in sim.nodes:
        # Only destination nodes carry ``completed_journeys``; the getattr default
        # lets us scan every node without type-checking each one. Each journey
        # ended at exactly one destination, so no de-duplication is needed.
        for journey in getattr(node, "completed_journeys", []):
            records.append(trip_record(journey, dt, include_connectors))

    records.sort(key=lambda r: (r["vehicle_id"], r["journey_index"]))
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

    per_link: dict[int, list[float]] = defaultdict(list)
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
    """Write trip records to a CSV file (one row per completed journey).

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
        "journey_index",
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
