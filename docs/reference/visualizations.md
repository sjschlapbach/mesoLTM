# Visualizations

!!! info "Requires the `[plot]` extra"
    These helpers import `matplotlib` at module top, so they are **not** part of
    `import mesoltm`. Install with `pip install "mesoltm[plot]"` and import from
    `mesoltm.visualizations`. MP4 export additionally needs `ffmpeg` on the PATH
    (GIF falls back to Pillow).

See [Visualizations](../guide/visualizations.md) and
[Movement animations](../guide/animations.md) for usage.

## Plots

Most plots are re-exported from `mesoltm.visualizations`. Two —
`plot_travel_time_distribution` and `plot_link_travel_times` — are currently only
importable from the `mesoltm.visualizations.plots` submodule (noted below).

::: mesoltm.visualizations.plots.plot_cumulative_curves

::: mesoltm.visualizations.plots.plot_link_flow

::: mesoltm.visualizations.plots.plot_link_flows

::: mesoltm.visualizations.plots.plot_link_time_series

::: mesoltm.visualizations.plots.plot_network

::: mesoltm.visualizations.plots.plot_travel_time_distribution

::: mesoltm.visualizations.plots.plot_link_travel_times

## Animation

Render a recorded [`SimulationHistory`](recording.md) to a video or per-step
frames. The high-level entry points are `animate_history`,
`animate_from_history_file`, and `animate_simulation`.

::: mesoltm.visualizations.animation.animate_simulation

::: mesoltm.visualizations.animation.animate_history

::: mesoltm.visualizations.animation.animate_from_history_file

::: mesoltm.visualizations.animation.save_animation

::: mesoltm.visualizations.animation.save_frames

::: mesoltm.visualizations.animation.render_frame

::: mesoltm.visualizations.animation.NetworkLayout

::: mesoltm.visualizations.animation.resolve_palette

::: mesoltm.visualizations.animation.expand_frame_indices
