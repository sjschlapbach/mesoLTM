# Metrics & trip analysis

After a run, `mesoltm.metrics` turns each vehicle's automatically-recorded
`trajectory` into per-vehicle travel-time records and network-level summaries.

```python
from mesoltm import collect_trips, summarize_trips, write_trips_csv

sim.run()
trips = collect_trips(sim)             # one record per completed vehicle
summary = summarize_trips(trips)       # network-level aggregates
write_trips_csv(trips, "trips.csv")    # flat CSV, one row per vehicle
```

Only vehicles that reached a destination are included; vehicles still en route or
queued at the horizon's end are omitted.

## The trip record

`collect_trips` (via `trip_record`) returns, per vehicle:

| Field | Meaning |
|-------|---------|
| `vehicle_id`, `origin`, `destination` | Identity |
| `route` | The ordered real link ids actually driven |
| `start_time` | Desired departure (`vehicle.start`) |
| `network_entry_time` | When it entered the first real link |
| `arrival_time` | When it was absorbed at the destination |
| `travel_time` | **Total** time in system, `arrival − start` |
| `access_time` | Initial wait in the origin queue + access connector, `network_entry − start` |
| `network_time` | In-network time, `arrival − network_entry` |
| `n_links`, `link_travel_times` | Per-link travel times (`{link_id: seconds}`) |

!!! note "Travel time includes access"
    The headline `travel_time` is the **total** time from desired departure to
    arrival, so it *includes* the origin-queue and connector wait. That wait is
    reported separately as `access_time` (and `travel_time = access_time +
    network_time`), so connector/queue time is both counted and distinguishable —
    see [Networks & connectors](../model/networks-and-connectors.md).

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

`write_trips_csv` flattens `route` (`"l1;l2;..."`) and `link_travel_times`
(`"id:seconds;..."`) into single columns so the file stays flat. The
[CLI and JSON scenarios](../getting-started/running-a-scenario.md) can also write
per-trip and per-link CSVs directly via `trip_output_file` / `link_output_file`.

To visualise these results, see [Visualizations](visualizations.md) —
`plot_travel_time_distribution`, `plot_link_travel_times`, and
`plot_link_time_series` all take the trip records or the simulation.
