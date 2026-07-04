# Codebase Structure

`mesoltm` v0.1 is implemented: a mesoscopic (individual-vehicle) Link Transmission
Model ported faithfully from `abmmeso` with added network/routing/control layers.
See `docs/MODEL_CHANGES.md` for the (small) deviations from the reference model.

## Top-level
- `pyproject.toml` — hatchling, PyPI-ready, `requires-python>=3.11`, deps `numpy`+`networkx`; extras `plot`/`ui`/`calib`/`dev`; `mesoltm` console script.
- `LICENSE` — **AGPL-3.0** (was MIT); `NOTICE` — attribution to de Souza et al. + paper DOI.
- `src/mesoltm/` — the package; `examples/` — runnable scripts (outside src); `docs/` — `MODEL_CHANGES.md`.
- `.github/workflows/` — one workflow per gate: `lint.yml` (pylint), `format.yml` (black --check), `typecheck.yml` (mypy), `test.yml` (pytest, 3.11/3.12 matrix), `release.yml` (build + a commented-out PyPI publish; on default-branch push).
- `CLAUDE.md`, `.ai/` (logs), `.serena/` (config + memories), `.claude/`, `README.md`, `abmmeso/` (temporary reference, to be deleted), `venv/` (git-ignored, 3.11.15).

## Package layout (`src/mesoltm/`)
- `core/` — `base_link`, `link` (discrete LTM, verbatim), `connector_link`, `vehicle`, `simulation` (`Simulation`: `run()` = batch; also `start()`/`step()`/`current_step`/`total_steps` for step-driven control, and `inject(node_id, vehicle, at_time=None)` for dynamic demand); `core/nodes/` — `base_node` (routing seam), `one_to_one_node`, `diverge_node`, `merge_node`, `general_node_model`, `origin_node` (`add_trip` = injectable demand), `destination_node`.
- `network/` — `network` (builder: add_node/add_link/set_origin/set_destination/compile; auto O/D connectors; capacity-proportional priorities; `compile(injection_budget=N)` sizes connectors for dynamic injection), `builders` (grid_network incl. partial, corridor_network, dict I/O), `state` (read-only NetworkState; also `inject(...)` splicing O/D connectors onto a real-link route).
- `routing/` — `policy` (RoutingPolicy protocol + StaticRoutePolicy default; `next_link(state: object)` to match the protocol), `shortest_path` (ShortestPathPolicy, networkx; `route(state, a, b)` = full-route planner; `cost` callback typed `Callable[[int, NetworkState], float]` for congestion-aware costs). `NetworkState` and `VehicleView` are exported from `mesoltm` for external typing.
- `plugins/` (renamed from `control/`) — `plugin`: the general per-step loop hook (run first each step), `Network.compile(..., plugins=[...])`. `Plugin` (base), `FunctionPlugin(fn)`, `ReroutingPlugin(reroute_fn)`. A plugin can change many aspects of the sim; rerouting needs no special hook because each `Vehicle` stores its own `route` and the network only propagates it, so rewriting `vehicle.route` reroutes that vehicle. `ReroutingPlugin` is the simple routing interface: gets `state.vehicles_in_network()` (`VehicleView`s), returns `{vehicle: real_route}` for only the ones to change (applied via `state.set_route`). No step-tracker plugin — the sim loop owns `state.step`.
- `demand/` — `demand.vehicles_from_demand_profile`.
- `metrics/` — `trips` (`collect_trips`, `trip_record`, `summarize_trips`, `write_trips_csv`): per-vehicle `route` driven, `travel_time` = total (incl. access), `access_time` (origin queue + connector), `network_time`, per-link times, keyed by `vehicle_id`. Derived from `Vehicle.trajectory`, which the `Link` fills in `set_inflow`/`set_outflow` (behaviour-preserving; see `MODEL_CHANGES.md` A6).
- `io/` — `scenario` (JSON build/load/save); `cli.py` + `__main__.py` (`python -m mesoltm`).
- `visualizations/` — `plots`: cumulative curves; `plot_link_flow` (sums links into one cut curve) vs `plot_link_flows` (one labelled line per link); `plot_network` (colour links by flow/occupancy/density/capacity, optional `annotate_links` labels, colorbar, parallel links fanned out as arcs); travel-time distribution; per-link travel-time bars; `plot_link_time_series` (one subplot per link: per-vehicle travel time vs entry time as a running average, to show congestion building up). matplotlib imported at module top (`Normalize` from `matplotlib.colors`, not `plt.Normalize`); the package `__init__` does not import this module, so `import mesoltm` stays cheap.
- `tests/` — **inside the package**, relative imports: `test_regression` (exact match vs abmmeso golden), `test_core`, `test_network`, `test_routing`, `test_scenario`, `test_metrics`, `test_priorities`, `test_injection` (step/inject), `test_rerouting` (ReroutingPlugin). 46 tests total.

## Runtime flow
`Network.compile(...)` → `Simulation` of links + nodes → `.run()` → per-link cumulative
in/outflow arrays + arrived-trip records + per-vehicle trajectories (+ optional CSV via
CLI/scenario or `metrics.write_trips_csv`). Routing is per-vehicle via `vehicle.route`
or a `RoutingPolicy`; plugins run first each step.

Keep this current when files/modules are added, moved, or removed.
