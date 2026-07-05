# Recording

The recording layer captures a per-step **history** of where every vehicle is,
for later animation. It is deliberately **matplotlib-free** (it is imported by the
core), so recording a run adds no plotting dependency; rendering the history to a
video lives separately under [Visualizations](visualizations.md).

Enable it with `Network.compile(record_history=True)`; the result is a
`SimulationHistory` on `Simulation.history` (JSON-serialisable via `save`/`load`).
See [Movement animations](../guide/animations.md).

## History container

::: mesoltm.recording.SimulationHistory

## Frame and snapshots

::: mesoltm.recording.Frame

::: mesoltm.recording.AgentSnapshot

::: mesoltm.recording.WaitingSnapshot

## Capture helpers

::: mesoltm.recording.capture_frame

::: mesoltm.recording.record_run
