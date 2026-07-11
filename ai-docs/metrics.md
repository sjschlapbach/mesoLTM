# mesoltm metrics

Post-run travel-time analysis. One **journey** = one completed trip. Metrics are
derived from the journey records on `vehicle.journeys` — the **single source of
truth** for a vehicle's completed trips (see
[vehicles-and-routing.md](vehicles-and-routing.md#journeys-the-single-source-of-truth-for-completed-trips)).
All import from `mesoltm`.

## One source of truth, one accounting path

Every completed trip is recorded the same way regardless of how the vehicle came to
exist:

- a **static demand profile** creates one vehicle per trip → one journey each;
- a **hand-injected** vehicle that is re-injected reuses one object → one journey
  per trip (`journey_index` 0, 1, 2, …).

So `collect_trips` produces exactly one record per journey with no special-casing —
you never have to reconcile "demand vehicles" against "injected vehicles". Records
are keyed by `(vehicle_id, journey_index)`.

## Collect and summarise trips

```python
from mesoltm import collect_trips, summarize_trips, write_trips_csv

sim.run()
trips = collect_trips(sim)                    # list[dict], one per completed journey
summary = summarize_trips(trips)              # dict of network aggregates
write_trips_csv(trips, "trips.csv")           # flat CSV, one row per journey
```

Only completed trips (reached a destination) are included. A single vehicle's own
completed trips are also directly available as `vehicle.journeys`.

## Functions

```python
collect_trips(sim, include_connectors=False) -> list[dict]   # sorted by (vehicle_id, journey_index)
trip_record(journey, dt, include_connectors=False) -> dict   # takes a journey record
summarize_trips(trips) -> dict
write_trips_csv(trips, path) -> str
```

`trip_record` takes a **journey record** (a dict from `vehicle.journeys` /
`vehicle.snapshot_journey()`), not a live `Vehicle`.

## Trip record fields (from trip_record / collect_trips)

```
vehicle_id, journey_index, origin, destination
route                # list[int]: real link ids actually driven
start_time           # desired departure = journey's start
network_entry_time   # entered first real link
arrival_time         # absorbed at destination
travel_time          # arrival - start MINUS each connector's 1-step free-flow lag
access_time          # travel_time - network_time (origin-queue + supply-limited connector wait)
network_time         # time on real links only (connector-free)
n_links
link_travel_times    # dict {link_id: seconds}
```

`journey_index` is the 0-based position of this trip in the vehicle's `journeys`
(always `0` for demand-profile vehicles). Time fields are seconds; `None` if
undeterminable. `travel_time = access_time + network_time`. By default connectors
are excluded from `route`/`link_travel_times` (pass `include_connectors=True`).

## Summary fields (from summarize_trips)

```
n_trips, n_completed
mean_travel_time, median_travel_time, min_travel_time, max_travel_time   # or None
mean_access_time
total_vehicle_hours
mean_link_travel_time   # dict {link_id: mean seconds}
```

## CSV output

`write_trips_csv` writes one row per journey (columns start `vehicle_id,
journey_index, …`), flattening `route` -> `"l1;l2;..."` and `link_travel_times` ->
`"id:seconds;..."`. The CLI / JSON scenarios can also write per-trip and per-link
CSVs directly via `trip_output_file` / `link_output_file` (see
[scenarios-cli.md](scenarios-cli.md)).
