# Metrics

Post-run analysis of per-vehicle travel times, derived from each vehicle's
`trajectory`. `collect_trips` builds one record per vehicle, `summarize_trips`
reduces them to network aggregates, and `write_trips_csv` flattens them to disk.
See [Metrics & trip analysis](../guide/metrics.md).

::: mesoltm.metrics.trips.collect_trips

::: mesoltm.metrics.trips.trip_record

::: mesoltm.metrics.trips.summarize_trips

::: mesoltm.metrics.trips.write_trips_csv
