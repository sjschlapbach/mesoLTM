# mesoltm metrics

Post-run per-vehicle travel-time analysis, derived from each vehicle's auto-logged
`trajectory`. All import from `mesoltm`.

## Collect and summarise trips

```python
from mesoltm import collect_trips, summarize_trips, write_trips_csv

sim.run()
trips = collect_trips(sim)                    # list[dict], one per completed vehicle
summary = summarize_trips(trips)              # dict of network aggregates
write_trips_csv(trips, "trips.csv")           # flat CSV, one row per vehicle
```

Only completed trips (reached a destination) are included.

## Functions

```python
collect_trips(sim, include_connectors=False) -> list[dict]      # sorted by vehicle_id
trip_record(vehicle, dt, include_connectors=False) -> dict
summarize_trips(trips) -> dict
write_trips_csv(trips, path) -> str
```

## Trip record fields (from trip_record / collect_trips)

```
vehicle_id, origin, destination
route                # list[int]: real link ids actually driven
start_time           # desired departure = vehicle.start
network_entry_time   # entered first real link
arrival_time         # absorbed at destination
travel_time          # TOTAL time in system = arrival - start (includes access wait)
access_time          # origin-queue + connector wait = network_entry - start
network_time         # in-network = arrival - network_entry
n_links
link_travel_times    # dict {link_id: seconds}
```

Time fields are seconds; `None` if undeterminable. `travel_time = access_time +
network_time`. By default connectors are excluded from `route`/`link_travel_times`
(pass `include_connectors=True` to keep them).

## Summary fields (from summarize_trips)

```
n_trips, n_completed
mean_travel_time, median_travel_time, min_travel_time, max_travel_time   # or None
mean_access_time
total_vehicle_hours
mean_link_travel_time   # dict {link_id: mean seconds}
```

## CSV output

`write_trips_csv` flattens `route` -> `"l1;l2;..."` and `link_travel_times` ->
`"id:seconds;..."`. The CLI / JSON scenarios can also write per-trip and per-link
CSVs directly via `trip_output_file` / `link_output_file` (see
[scenarios-cli.md](scenarios-cli.md)).
