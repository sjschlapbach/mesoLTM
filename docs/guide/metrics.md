# Metrics & trip analysis

After a run, `mesoltm.metrics` turns each completed **journey** into a travel-time
record and network-level summaries. One journey = one completed trip.

```python
from mesoltm import collect_trips, summarize_trips, write_trips_csv

sim.run()
trips = collect_trips(sim)             # one record per completed journey
summary = summarize_trips(trips)       # network-level aggregates
write_trips_csv(trips, "trips.csv")    # flat CSV, one row per journey
```

Only journeys that reached a destination are included; vehicles still en route or
queued at the horizon's end are omitted.

!!! note "One source of truth for all trips"
    A completed trip is recorded the same way no matter how the vehicle came to
    exist. A vehicle from a **static demand profile** makes one trip → one journey;
    a **hand-injected** vehicle [re-injected](stepping-and-injection.md#re-injecting-a-vehicle-for-another-trip)
    for several trips reuses one object → one journey per trip. Every journey lives
    on `vehicle.journeys`, and `collect_trips` reports exactly one record per
    journey — so metrics need no special-casing, and records are keyed by
    `(vehicle_id, journey_index)` (`journey_index` is `0` for a single-trip vehicle).

## The trip record

`collect_trips` (via `trip_record`) returns, per journey:

| Field | Meaning |
|-------|---------|
| `vehicle_id`, `journey_index`, `origin`, `destination` | Identity (which vehicle, which of its trips) |
| `route` | The ordered real link ids actually driven |
| `start_time` | Desired departure (`vehicle.start`) |
| `network_entry_time` | When it entered the first real link |
| `arrival_time` | When it was absorbed at the destination |
| `travel_time` | Time in system, desired departure → arrival, **less each connector's one-step free-flow lag** |
| `access_time` | The part of `travel_time` not on real links: origin-queue wait + any supply-limited connector wait, `travel_time − network_time` |
| `network_time` | Time on real links only (connector-free) |
| `n_links`, `link_travel_times` | Per-link travel times (`{link_id: seconds}`) |

!!! note "How connector time is counted"
    Each auto-inserted O/D connector is a one-cell link that costs exactly **one
    free-flow step** to cross. That single step is a modelling artifact — a vehicle
    incurs it even on an empty connector — so it is **removed** from `travel_time`.
    But if a vehicle is held on a connector **longer** than one step because
    downstream space is the binding constraint, that extra time is a genuine wait to
    enter/leave the network and is **kept** (reported as `access_time`). So
    `travel_time = access_time + network_time`, `network_time` stays connector-free,
    and an empty, unrestricted connector adds nothing — see
    [Networks & connectors](../model/networks-and-connectors.md).

By default connector links are excluded from `route` and `link_travel_times`; pass
`include_connectors=True` to keep them.

## Network summary

`summarize_trips(trips)` returns headline metrics: `n_trips`, `n_completed`,
mean/median/min/max `travel_time`, `mean_access_time`, `total_vehicle_hours`, and
`mean_link_travel_time` (per link).

```python
print(summary["n_completed"], "trips,",
      round(summary["mean_travel_time"], 1), "s mean,",
      round(summary["total_vehicle_hours"], 2), "veh-h")
```

## CSV output

`write_trips_csv` writes one row per journey (columns begin `vehicle_id,
journey_index, …`) and flattens `route` (`"l1;l2;..."`) and `link_travel_times`
(`"id:seconds;..."`) into single columns so the file stays flat. The
[CLI and JSON scenarios](../getting-started/running-a-scenario.md) can also write
per-trip and per-link CSVs directly via `trip_output_file` / `link_output_file`.

To visualise these results, see [Visualizations](visualizations.md) —
`plot_travel_time_distribution`, `plot_link_travel_times`, and
`plot_link_time_series` all take the trip records or the simulation.
