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

## travel_time includes access time

A trip's `travel_time` is the TOTAL time from desired departure to arrival,
including origin-queue and connector wait (`access_time`).
`travel_time = access_time + network_time`.

## Injection needs a budget

To inject vehicles mid-run into an origin with little/no static demand, compile
with `injection_budget=N` so connectors stay transparent. Over-estimating is safe.

## Imports are always module-top-level

Project convention: never inline imports or wrap them in try/except; only
`TYPE_CHECKING`-guarded type-only imports are allowed as conditional imports.

## Core arithmetic is a verbatim port

The link demand/supply arithmetic, capacity-token recursion, and node algorithms
(one-to-one, diverge, merge, general) are ported verbatim from de Souza et al.
(SIMPAT 140 (2025) 103088) and locked by an exact regression test. Do not alter
them. All `mesoltm` additions (routing policies, plugins, step/inject, connectors,
metrics, visualisation) sit around this untouched core.

## License

AGPL-3.0-or-later (adapts AGPL-3.0 `abmmeso` source). Derivative works must be
AGPL.
