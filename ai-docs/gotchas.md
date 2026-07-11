# mesoltm gotchas and constraints

Common pitfalls and hard constraints when using or extending `mesoltm`.

## Vehicle vs Link parameters

`v_f`, `w`, `rho_jam` are **Link** (fundamental-diagram) parameters, NOT `Vehicle`
parameters. `Vehicle(vehicle_id, origin, destination, scheduled_departure, route,
props)` has no FD attributes.

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

## Set `injection_budget` for dynamic injection

If a run uses dynamic demand injection (`Simulation.inject`), compile with
`injection_budget=N` set to at least the number of vehicles you will inject:
`net.compile(..., injection_budget=N)`. It sizes the origin/destination connector
links so they can hold the injected vehicles and stay transparent. **It defaults to
`100`** (light injection works out of the box), but setting it explicitly is
strongly recommended. If more vehicles are injected than the budget, a
`RuntimeWarning` is emitted: the over-budget vehicle is added to its origin's queue
but the connector buffer may be full, so it waits there and enters only once space
frees up (and may not enter within the horizon) — it is never silently discarded.
Over-estimating `N` is safe; purely static runs are unaffected. **Count each
re-injection** toward `N` (a vehicle injected for three trips uses three).

## Re-injecting a vehicle: set `route`, mind the guardrails

The same `Vehicle` can be injected again after it has arrived, to make another trip
(each recorded as a journey on `vehicle.journeys` — the single source of truth for
completed trips; metrics read those, so demand-profile and injected runs account
identically). Two easy mistakes:

- **Forgetting to set `route`.** Re-injection resets the vehicle's live journey
  state (`trajectory`/`end`/`position`) but **not** `route`, which still holds the
  previous connector-spliced route. Set `vehicle.route = [<new real links>]` before
  re-injecting, or the splice will treat the old spliced route as "real" and corrupt
  the trip.
- **Ignoring the guardrails.** `inject` raises `RuntimeError` if the vehicle is still
  active (its current journey hasn't finished — wait until `vehicle.active is False`),
  and `ValueError` if it re-enters at a different **real** node than it last left
  (auxiliary O/D connector nodes are never counted). Pass `check_reentry_node=False`
  to allow a deliberate re-entry elsewhere.

## Trip records are per-journey, keyed `(vehicle_id, journey_index)`

`collect_trips` / `write_trips_csv` emit **one row per completed journey**, not per
vehicle, and `trip_record` takes a **journey record** (from `vehicle.journeys`), not
a live `Vehicle`. A demand-profile vehicle has one journey (`journey_index == 0`); a
re-injected one has several. If you index trips by `vehicle_id` alone you will
collide re-injected vehicles' journeys — key by `(vehicle_id, journey_index)`.

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
