# Movement animations

`mesoltm` can render a video of vehicles moving link-to-link. This is a two-stage
process: **record** a per-step history during the run (matplotlib-free), then
**render** it to a video or frames (needs the `[plot]` extra).

## 1. Record the history

Turn on history capture at compile time. The recorded run exposes the frames on
`Simulation.history`:

```python
sim = net.compile(time_step=1.0, total_time=400.0, record_history=True)
sim.run()
history = sim.history            # a SimulationHistory (JSON-serialisable)
```

The recorder logs, per step, each vehicle's position, its remaining route (read
straight from `vehicle.route` — never recomputed, so the log always matches what
ran), and a copy of its `props` metadata. Vehicles waiting to enter are logged as
a count on their origin node. Optionally persist it:

```python
sim = net.compile(..., record_history=True, history_path="run.json")
sim.run()                        # writes run.json on completion
# or explicitly: sim.save_history("run.json")
```

!!! note "Recording is cheap and dependency-free"
    History capture adds no plotting dependency (`mesoltm.recording` is
    matplotlib-free) but does cost memory, so it is **off by default**.

## 2. Render to video or frames

The rendering helpers live in `mesoltm.visualizations.animation` (needs
`[plot]`; MP4 also needs `ffmpeg` on the PATH — otherwise it falls back to an
animated GIF via Pillow).

```python
from mesoltm.visualizations import animate_simulation
animate_simulation(sim, "run.mp4", fps=25)     # from a recorded simulation
```

Other entry points:

- **`animate_history(history, out_path, ...)`** — from a `SimulationHistory`.
- **`animate_from_history_file(path, out_path, ...)`** — from a saved JSON log.
- **`save_frames(frames, layout, out_dir, ...)`** — per-step PNGs.
- **`save_animation(frames, layout, out_path, fps=25, subsample=1.0, ...)`** —
  MP4/GIF (`subsample` > 1 slows playback, < 1 speeds it up).

## Colouring vehicles

`color_by` chooses what a dot's colour means:

| `color_by` | Meaning |
|------------|---------|
| `"category"` (default) | The classification set at record time (`history_classify`) |
| `"next_link"` | The link each vehicle takes next (read from the logged route) |
| `None` | Uniform colour (colouring off) |
| a callable `fn(snapshot) -> str` | Anything on the snapshot — most usefully `snapshot.props` |

A custom callable is the most flexible — colour by a vehicle class, operator, or
any metadata you attached via `Vehicle(props=...)`, which round-trips through the
log:

```python
from mesoltm.visualizations import animate_simulation
animate_simulation(
    sim, "by_class.mp4",
    color_by=lambda snap: "tab:red" if snap.props.get("vclass") == "truck" else "tab:blue",
)
```

To assign categories at record time instead, pass `history_classify` to
`compile()`:

```python
sim = net.compile(..., record_history=True,
                  history_classify=lambda veh, state: veh.props.get("group", "default"))
```

The renderer scales markers, nodes, and labels to the network so dense grids stay
readable, and auto-drops per-agent detail when crowded (overridable via
`detail`, `show_agent_ids`, `show_next_link`). See the
[Visualizations reference](../reference/visualizations.md) and
[`grid_visualization.py`](examples.md) / [`bottleneck_access_policy.py`](examples.md).
