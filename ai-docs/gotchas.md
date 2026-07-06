# mesoltm gotchas and constraints

Common pitfalls and hard constraints when using or extending `mesoltm`.

## Vehicle vs Link parameters

`v_f`, `w`, `rho_jam` are **Link** (fundamental-diagram) parameters, NOT `Vehicle`
parameters. `Vehicle(vehicle_id, origin, destination, start, route, props)` has no
FD attributes.

## CFL condition raises ValueError

A link must satisfy `max(v_f, w) * dt <= length`. If violated, `Link.start()` (via
`sim.start()`/`sim.run()`) raises `ValueError`. Fix by decreasing `time_step` or
increasing `length`. The reference code silently collapsed the lags instead;
`mesoltm` enforces it.

## compile() is single-use

`Network.compile()` may be called once per `Network` (it splices connector ids into
vehicle routes). To run again, rebuild the network with **fresh** `Vehicle`
objects; reusing compiled vehicles corrupts their routes.

## matplotlib is optional

`import mesoltm` does not import matplotlib and stays cheap. Plotting/animation
(`mesoltm.visualizations`) needs the `[plot]` extra. `mesoltm.recording` (history
capture) is matplotlib-free, so recording a run adds no plotting dependency.

## Two plot functions are not re-exported

`plot_travel_time_distribution` and `plot_link_travel_times` are importable only
from `mesoltm.visualizations.plots`, not from `mesoltm.visualizations`.

## Routes over real links only; connectors are automatic

User/injected routes reference only **real** link ids. `Network.compile` /
`NetworkState.inject` splice origin/destination `ConnectorLink`s automatically.
`NetworkState.set_route` requires the new route to start at the vehicle's current
link (else `ValueError`, preventing stranding).

## props must be JSON-serialisable

`Vehicle.props` is free-form metadata the core never reads. It must be
JSON-serialisable to survive the animation history round-trip.

## Merge priority default is capacity-proportional

An unprioritised `MergeNode`/`GeneralNodeModel` defaults to **capacity-proportional**
shares (not equal). Set explicitly via `alpha`/`priority_vector` or
`Network.set_merge_priorities(node_id, {link_id: share})`.

## travel_time, access_time, network_time

`travel_time` = desired departure -> arrival, MINUS each O/D connector's one-step
free-flow lag (a one-cell connector always costs 1 free-flow step; that artifact is
removed, so an empty connector adds nothing). Time spent on a connector BEYOND one
step (a supply-limited wait to enter/leave the network) is KEPT, reported as
`access_time`. `network_time` = time on real links only (connector-free).
`travel_time = access_time + network_time`.

## Dynamic injection REQUIRES `injection_budget`

If a run uses dynamic demand injection (`Simulation.inject`), you MUST compile with
`injection_budget=N`, where `N` is at least the number of vehicles you will inject:
`net.compile(..., injection_budget=N)`. It sizes the origin/destination connector
links so they can hold the injected vehicles and stay transparent. With the default
`injection_budget=0` the connectors are sized for the static demand only, so
injected vehicles can be blocked or dropped and the injection silently has no
effect. Over-estimating `N` is safe; purely static runs are unaffected.

## Imports are always module-top-level

Project convention: never inline imports or wrap them in try/except; only
`TYPE_CHECKING`-guarded type-only imports are allowed as conditional imports.

## Core arithmetic is a verbatim port

The link demand/supply arithmetic, capacity-token recursion, and node algorithms
(one-to-one, diverge, merge, general) are ported verbatim from de Souza et al.
(SIMPAT 140 (2025) 103088). Do not alter them. All `mesoltm` additions (routing
policies, plugins, step/inject, connectors, metrics, visualisation) sit around
this untouched core.

## License

AGPL-3.0-or-later (adapts AGPL-3.0 `abmmeso` source). Derivative works must be
AGPL.
