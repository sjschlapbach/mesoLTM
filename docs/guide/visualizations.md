# Visualizations

`mesoltm.visualizations` provides matplotlib plots of flows, travel times, and
network maps. For agent-movement videos, see [Movement animations](animations.md).

!!! info "Requires the `[plot]` extra"
    Install with `pip install "mesoltm[plot]"`. These helpers import matplotlib,
    so they are **not** part of `import mesoltm` — import them from
    `mesoltm.visualizations`.

```python
import matplotlib
matplotlib.use("Agg")                     # headless backend for scripts
import matplotlib.pyplot as plt
from mesoltm.visualizations import plot_network, plot_link_flows
```

## Flow over time

- **`plot_cumulative_curves(sim, link_ids=None)`** — cumulative inflow/outflow
  curves per link.
- **`plot_link_flow(sim, link_ids, window=...)`** — sums several links into one
  flow "across a cut" (veh/h).
- **`plot_link_flows(sim, link_ids, labels=None, window=...)`** — one labelled
  line per link.

```python
fig, ax = plt.subplots()
plot_link_flows(sim, [l1, l2], labels=["upstream", "downstream"], ax=ax)
fig.savefig("flows.png")
```

## Travel times

These take the trip records from [`collect_trips`](metrics.md) (or the simulation):

- **`plot_link_time_series(sim, link_ids, window=5)`** — per-link travel time over
  time (one subplot per link), to watch congestion build up.
- **`plot_travel_time_distribution(trips, bins=20)`** — histogram of per-vehicle
  travel times.
- **`plot_link_travel_times(trips)`** — mean travel time per link (bar chart).

!!! note "Two plots live on the submodule"
    `plot_travel_time_distribution` and `plot_link_travel_times` are currently
    imported from the `mesoltm.visualizations.plots` submodule (not the
    `mesoltm.visualizations` package root):

    ```python
    from mesoltm.visualizations.plots import (
        plot_travel_time_distribution, plot_link_travel_times,
    )
    ```

## Network maps

**`plot_network(state, color_by="occupancy", annotate_links=False)`** draws the
network, colouring links by `"flow"`, `"occupancy"`, `"density"`, or `"capacity"`,
with a colorbar and parallel links fanned out as arcs. Pass the live
[`NetworkState`](../reference/network.md#network-state) (`sim.network_state`):

```python
from mesoltm.visualizations import plot_network
fig, ax = plt.subplots()
plot_network(sim.network_state, color_by="occupancy", annotate_links=True, ax=ax)
```

Most functions accept an `ax=` so you can compose subplots. See the
[Visualizations reference](../reference/visualizations.md) for full signatures, and
[`vehicle_metrics_demo.py`](examples.md) for a worked example.
