# mesoltm visualization and animation

Plots and movement animations live in `mesoltm.visualizations` and require the
`[plot]` extra (matplotlib). They are NOT in the top-level `mesoltm` package.
Recording the animation history is separate and matplotlib-free
(`mesoltm.recording`, exported from `mesoltm`).

## Plots

Import from `mesoltm.visualizations`:

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mesoltm.visualizations import (
    plot_cumulative_curves, plot_link_flow, plot_link_flows,
    plot_link_time_series, plot_network,
)

fig, ax = plt.subplots()
plot_link_flows(sim, [l1, l2], labels=["up", "down"], ax=ax)
plot_network(sim.network_state, color_by="occupancy", annotate_links=True)
```

Plot functions:

```python
plot_cumulative_curves(sim, link_ids=None, ax=None)
plot_link_flow(sim, link_ids, window=60, window_seconds=None, ax=None)   # summed cut
plot_link_flows(sim, link_ids, labels=None, window=60, window_seconds=None, ax=None)
plot_link_time_series(sim, link_ids, labels=None, window=5, axes=None)
plot_network(state, color_by="occupancy", ax=None, node_size=260.0, annotate_links=False)
# color_by in {"flow","occupancy","density","capacity"}; drawn with networkx.
# Links sharing an edge (parallel links + both directions of a bidirectional edge,
# A->B and B->A) are fanned onto distinct arcs, so opposing arrows never overlap; a
# lone link stays straight. Robust to arbitrary node layouts and any number of links
# between a pair. color_by="flow" after a run shows each link's total load.
```

Two plot functions are NOT re-exported from `mesoltm.visualizations`; import them
from the submodule `mesoltm.visualizations.plots`:

```python
from mesoltm.visualizations.plots import (
    plot_travel_time_distribution,   # (trips, ax=None, bins=20)
    plot_link_travel_times,          # (trips, ax=None)
)
```

## Recording animation history

Enable at compile; history is matplotlib-free and JSON-serialisable.

```python
sim = net.compile(time_step=1.0, total_time=400.0, record_history=True)
sim.run()
history = sim.history                 # SimulationHistory
# or persist: net.compile(..., record_history=True, history_path="run.json")
# or:         sim.save_history("run.json")
```

`record_history=True` logs each vehicle's position and remaining route (read from
`vehicle.route`, never recomputed) plus its `props`. Off by default (memory cost).

## Rendering to video / frames

From `mesoltm.visualizations` (needs `[plot]`; MP4 needs ffmpeg, else GIF fallback):

```python
from mesoltm.visualizations import (
    animate_simulation, animate_history, animate_from_history_file,
    save_animation, save_frames,
)

animate_simulation(sim, "run.mp4", fps=25)                 # from a recorded sim
animate_history(history, "run.mp4")                        # from SimulationHistory
animate_from_history_file("run.json", "run.mp4")           # from saved JSON
```

## Colouring agents (color_by)

`color_by` on the animate/render functions: `"category"` (default; set via
`history_classify`), `"next_link"`, `None` (uniform), or a callable
`fn(snapshot) -> str` colouring by anything on the snapshot, esp. `snapshot.props`.

```python
animate_simulation(
    sim, "by_class.mp4",
    color_by=lambda snap: "tab:red" if snap.props.get("vclass") == "truck" else "tab:blue",
)
```

Assign categories at record time via `compile(history_classify=fn)` where
`fn(vehicle, state) -> str`.
