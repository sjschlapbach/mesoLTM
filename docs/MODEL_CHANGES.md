# Changes with respect to the original model formulation

This document lists **every deviation** of `mesoltm` from the model as formulated
in the reference paper and its reference implementation `abmmeso`:

> F. de Souza, O. Verbas, J. Auld, C. M. J. Tampère,
> *"A mesoscopic link-transmission-model able to track individual vehicles"*,
> Simulation Modelling Practice and Theory **140 (2025) 103088**.
> DOI: 10.1016/j.simpat.2025.103088 — code (AGPL-3.0): https://github.com/felasouza/abmmeso

The guiding principle was **to change the model only where absolutely necessary**.
The core traffic-flow mathematics — link sending/receiving flows, the T1/T2 wave
lags, the integer capacity-token discretization, and the node flow-resolution
algorithms — are ported **verbatim** (identical arithmetic and ordering). A
numeric regression test (`src/mesoltm/tests/test_regression.py`) asserts that
`mesoltm` reproduces `abmmeso`'s cumulative in/outflows **exactly** (zero
difference) on the reference diverge–merge network, which is the objective proof
that none of the changes below alter the model's behaviour.

The changes fall into two groups: **(A) behaviour-preserving** (no effect on
results, verified by the regression test) and **(B) additive extensions** (new
capabilities that do not modify the original dynamics when unused).

---

## A. Behaviour-preserving changes (no effect on model results)

### A1. Pluggable next-link lookup at branching nodes
- **Paper/abmmeso:** a diverge / general / signalized node determines a vehicle's
  next link by reading the vehicle's own route inline
  (`vehicle.route.index(inbound_link_id)` → next entry).
- **mesoltm:** that single lookup is delegated to a `RoutingPolicy`
  (`src/mesoltm/routing/policy.py`). The **default** policy (`StaticRoutePolicy`)
  reproduces the original behaviour exactly by reading `vehicle.route`.
- **Why:** to allow external, per-vehicle routing (shortest path, auctions,
  dynamic access rules) — a stated requirement.
- **Effect on the model:** none. The flow-resolution arithmetic (demand, supply,
  priority merging, FIFO diverging, outbound locking) is unchanged; only *which
  outbound link a given vehicle is assigned to* can be overridden, and only when a
  non-default policy is supplied.

### A2. Per-vehicle route position pointer
- **Paper/abmmeso:** a node finds the current link via the **first** occurrence of
  the inbound link id in the route (`list.index`).
- **mesoltm:** `Vehicle` also carries a `position` index that is advanced as the
  vehicle moves, so routes that revisit a link (possible on general grids) resolve
  to the correct occurrence. When a route does not revisit any link (all the
  paper's scenarios, and any simple path), this is **identical** to `list.index`.
- **Effect on the model:** none for the paper's networks; a strict correctness
  improvement for cyclic routes on grids.

### A3. Transient flow scalars reset to `0` instead of `None`
- **abmmeso:** at the end of each step a link sets its transient scalars
  (`_demand`, `_supply`, `_inflow`, `_outflow`) back to `None` as a defensive
  guard.
- **mesoltm:** these are reset to `0` / `0.0` instead.
- **Why:** purely to give the ported code clean, non-`Optional` type annotations
  (`mypy`-clean) under the two-phase-init pattern.
- **Effect on the model:** none. These values are always recomputed before they
  are next read (the fixed loop order guarantees it), so `0` versus `None` is never
  observed. Confirmed by the exact regression test.

### A4. Naming / packaging only (no logic)
- Files renamed to `snake_case` (`divergeNode.py` → `diverge_node.py`), classes
  kept in `PascalCase`; `Trip` → `Vehicle`, `SimulationRunner` → `Simulation`;
  proper package imports and a `src/` layout. Duplicate `get_capacity` definitions
  in the original were collapsed to one. These are cosmetic and do not touch the
  dynamics.

### A5. Variable names follow standard traffic-engineering notation
- Fundamental-diagram identifiers use the conventional symbols rather than the
  paper/`abmmeso` spellings — **only the names change, never the values**:
  | quantity | paper/abmmeso | mesoltm |
  |---|---|---|
  | free-flow speed | `vf` | `v_f` |
  | backward wave speed | `w` | `w` (unchanged) |
  | jam density | `kj` | `rho_jam` |
  | capacity (max flow) | `cap` / `C` | `capacity` |
  | density (accessor) | — | `density` (ρ) |
  | occupancy (accessor) | — | `occupancy` (o) |
- This affects the public keyword names (`Link(..., v_f=30, w=6, rho_jam=0.2)`)
  and the JSON scenario keys (`"v_f"`, `"rho_jam"`), consistently across the
  package, examples and tests. The FD relationships are identical:
  `capacity = rho_jam·v_f·w/(v_f + w)`, `T1 = L/(v_f·Δt)`, `T2 = L/(w·Δt)`,
  jam storage `rho_jam·L`. The exact regression test still passes, proving the
  rename is behaviour-preserving.

### A6. Per-vehicle trajectory recording
- **Paper/abmmeso:** a link exposes only aggregate cumulative in/outflows; the
  destination stamps each vehicle's arrival step (`end`). Per-link travel times are
  not tracked.
- **mesoltm:** each `Vehicle` carries a `trajectory` log; the `Link` timestamps the
  vehicle's entry/exit as it is placed on / discharged from the link (in the
  existing `set_inflow` / `set_outflow` methods, using the step index the calling
  node passes in — see A8). The `mesoltm.metrics` module derives, per vehicle, the
  route actually driven, per-link travel times, and three durations from this log:
  `access_time` (initial wait in the origin queue and on the origin connector, i.e.
  `network_entry − start`), `network_time` (`arrival − network_entry`), and the
  headline `travel_time` = **total** time in system (`arrival − start`), which
  *includes* the access wait. Access time is reported separately so connector/queue
  time is both counted in the total and distinguishable.
- **Effect on the model:** none. The recording only writes to vehicle/link
  bookkeeping attributes; it reads nothing back into the demand/supply/flow
  arithmetic, and the step index is used only for the timestamp. The exact
  regression test still passes.

### A7. CFL condition enforced (paper Section 3.3)
- **Paper/abmmeso:** Section 3.3 states the Courant–Friedrichs–Lewy condition —
  the fastest wave must not cross a link in less than one step,
  `max(v_f, w) * dt <= length` — but the reference code does not check it: it
  floors the wave lags with `max(1, int(...))`, so a too-short link is silently
  accepted and simulated with an incorrect (collapsed) lag.
- **mesoltm:** `Link.start` validates the CFL condition and raises a `ValueError`
  (with the offending values and the fix — shorten `dt` or lengthen the link) when
  it is violated. A tiny relative tolerance admits the exactly-one-step boundary,
  so auto-configured connector links (which cross in exactly one step) pass.
- **Effect on the model:** none for any CFL-satisfying network (all paper/abmmeso
  scenarios); it only turns a previously silent mis-discretisation into an explicit
  error. The exact regression test still passes.

### A8. Links do not store time; the loop passes it in
- **Paper/abmmeso:** each link keeps its own copy of the time step, total time,
  total step count and the current step index as attributes.
- **mesoltm:** the `Link` stores **no** time state. `start(time_step, total_time)`
  uses those values locally (to size arrays and derive the `T1`/`T2` lags and
  capacity, which are fixed link kinematics, not time) without keeping them; the
  `Simulation` loop owns the clock and passes what each per-step method needs:
  `update_state_variables(t, time_step)`, `set_inflow/​set_outflow(..., step)`
  (the calling node forwards its step index for the A6 timestamp), and
  `get_output_records(sample_time, sim_time_step, total_time)`. The dead
  `total_steps` attribute was dropped.
- **Why:** keep time in one place so a link can never hold a stale copy; there is
  nothing per-step to "forget to update" on a link.
- **Effect on the model:** none — a pure plumbing change; the arithmetic is
  byte-identical. The exact regression test still passes.

---

## B. Additive extensions (new capabilities, original dynamics unchanged)

These add functionality around the model. When they are not used, the model is
exactly the paper's model.

### B1. Origin/destination connector links for general graphs
- **Need:** the paper attaches an origin (or destination) node directly to a
  single link. To let **any node of a general graph** act as an origin and/or
  destination — including junctions with several links and through traffic — the
  `Network` builder auto-inserts a short **connector link** between the
  origin/destination node and the physical junction (only when the node is not a
  "pure" single-link origin/destination, in which case the direct attachment of
  the paper is used unchanged).
- **Connector properties (transparent buffer):** a connector is an ordinary
  discrete-LTM link (`src/mesoltm/core/connector_link.py`) with **auto-derived**
  parameters (the user never configures it): free-flow travel time of exactly one
  step (`T1 == T2 == 1`), and storage/capacity sized from the scenario's total
  vehicle count so that **neither ever binds**. Concretely, with `length = 1`,
  `v_f = w = 1/dt` and `rho_jam = 2·N` (N = total vehicles), storage is `2·N`
  vehicles and the per-step capacity token is `N`, so:
  - the connector is a **transparent buffer** — it is never the binding
    constraint; the adjacent origin / junction / destination governs the flow, and
    the connector is served like any 1-lane link subject to downstream supply and
    merge priorities;
  - a **source connector holds the origin's entire entry queue**: the origin can
    always release every waiting vehicle onto it, so vehicles never queue at the
    origin *and* on the connector simultaneously (no double buffering). Vehicles
    that must wait do so on the connector and are already part of its demand, so
    they are served the instant downstream supply allows — with no extra
    origin→connector hop delay. A vehicle entering an empty connector still crosses
    it in one free-flow step, so it enters the network immediately when served.
  - The vehicle budget carries **no `dt` term**, so the buffer does not shrink for
    a larger time step (this replaced an earlier fixed 4-vehicle buffer that could
    cause `dt`-dependent spurious delays).
- **Deviation from "zero-length links":** the design intent was zero-length
  connectors. A **true zero-length link is impossible in the LTM**, because a
  link's storage is `kj · length`, so a zero-length link could never hold or admit
  a vehicle. The connector is therefore a **one-cell** link (the minimal faithful
  approximation), which introduces at most a one-step free-flow lag at entry/exit.
  The paper's own validation scenarios are built with **direct attachment** (no
  connectors) so they remain bit-exact; connectors only appear when using the
  general-graph `Network` builder. Metrics attribute any waiting on an entry
  connector to `queue_delay` (network-access delay), so reported in-network
  `travel_time` is unaffected by the connector (see A6/`metrics`).

### B2. Merge priorities expressed as shares `alpha`, defaulting to capacity-proportional
- **Paper/abmmeso:** the merge/general node priority is supplied explicitly by the
  modeller as an integer `priority_vector` (e.g. `[0, 0, 0, 1]` for a 0.75/0.25
  split).
- **mesoltm:**
  - The merge/general nodes now also accept the priority as **shares**
    `alpha_1, alpha_2, …` (`alpha[i]` = fraction of the outbound supply inbound
    link `i` may claim). `alpha` is converted to the reference integer
    `priority_vector` (`core/priorities.priority_vector_from_alpha`); the ported
    node arithmetic is untouched — it still consumes the `priority_vector`. (The
    node stores only the `priority_vector`; the earlier redundant `.alpha`
    attribute, and the unused `resolve_priorities`/`alpha_from_priority_vector`
    helpers, were removed.)
  - **Default = capacity-proportional (not equal).** When *neither* a
    `priority_vector` nor `alpha` is supplied, a merge/general node defaults its
    priorities to being proportional to each inbound link's capacity
    `rho_jam·v_f·w/(v_f+w)` (max flow) — resolved in the node's `start()` once the
    link capacities are known. This holds whether the node is built directly or by
    the `Network` builder. (Previously an unprioritised node defaulted to *equal*
    priority; the `Network` builder already passed capacity-proportional `alpha`, so
    this only changes directly-constructed nodes.) The paper notes priority vectors
    are used precisely to mimic capacity/lane-count-proportional merges.
  - The `Network` builder still computes the default explicitly via `_alpha_for`
    (so it can weight a **connector** inbound like the strongest real approach and
    apply per-node overrides); it is overridable at node-definition time via
    `Network.set_merge_priorities(node_id, {inbound_link_id: share})`.
- **Effect on the model:** none for any node with an explicit `priority_vector`
  (all paper examples) or explicit `alpha`; the only behavioural change is that an
  **unprioritised** merge/general node now yields capacity-proportionally rather
  than equally. The exact regression test (explicit priority vectors) still passes.

### B3. Plugin hook for external, per-step logic
- `mesoltm` exposes the engine's existing "run first each step" slot as a typed
  `Plugin` interface (`src/mesoltm/plugins/plugin.py`) for auctions / access rules /
  reactive rerouting / link gating. This is the same hook abmmeso already invoked
  for signal controllers; no change to the loop's four-phase ordering
  (plugins → node prepare → link demand/supply → node flows → link commit). It is
  registered via `Network.compile(..., plugins=[...])`.
- A plugin can change many aspects of the simulation for the step about to run.
  **Rerouting works without any special routing hook** because each vehicle stores
  its own `route` (a list of link ids) on the `Vehicle`; the network/nodes only
  propagate a vehicle along whatever route it holds, so a plugin reroutes one
  vehicle simply by rewriting its `route`. Engine bookkeeping is *not* done via
  plugins — the simulation loop keeps `state.step` current itself (a former
  `_StepTracker` "controller" was removed).
- `ReroutingPlugin` is the simplest routing interface: each step it is handed every
  in-network vehicle's location + remaining real-link route (`NetworkState.
  vehicles_in_network`) and returns only `{vehicle: new_real_route}` for the ones
  to change; omitted vehicles keep their route. Updates go through `NetworkState.
  set_route`, which requires the new route to start at the vehicle's current link
  (rejecting anything that would strand it) and re-attaches the destination
  connector. This is a plugin-layer feature; it never touches the flow arithmetic.

### B4. Built-in shortest-path routing
- An optional `ShortestPathPolicy` (networkx) is provided as a convenience router.
  It is entirely opt-in and, being a `RoutingPolicy` (A1), never affects the flow
  arithmetic.

### B5. Step-driven execution and dynamic vehicle injection
- **Motivation:** drive an external control loop (e.g. a ride-hail dispatcher) that
  observes the network between steps and injects vehicles at a node during the run.
- `Simulation` gains `start()` + `step()` (advance one step) alongside `run()`, plus
  `current_step` / `total_steps`. `run()` is now literally `start()` + a loop of
  `step()` + `write_outputs()`, so its behaviour is unchanged (the exact regression
  test still passes; a stepping-vs-`run()` equality test locks this too).
- `Simulation.inject(node_id, vehicle, at_time=None)` → `NetworkState.inject` →
  `OriginNode.add_trip` adds a vehicle to an origin's demand mid-run. The caller
  supplies a route over **real** link ids; the origin/destination connectors are
  spliced on automatically (same helper logic as static compile), and the vehicle
  is inserted in departure-time order (`bisect.insort`) so the origin's sorted scan
  stays valid. Default `at_time` is the current step, so it is considered next step.
- `Network.compile(..., injection_budget=N)` sizes the connectors to stay
  transparent for the static demand *plus* `N` injections — needed because a node
  carrying little/no static demand would otherwise get a connector sized to pass
  only one vehicle/step. Larger only makes connectors *more* transparent, never more
  binding, so it cannot perturb dynamics; purely static runs are unaffected.
- **Effect on the model:** none on the per-step arithmetic. Injection only appends
  to a node's demand list, exactly as static demand does.

---

## What was **not** changed (verbatim from the paper)

- Link capacity `capacity = rho_jam·v_f·w/(v_f+w)`; step lags `T1 = L/(v_f·Δt)`,
  `T2 = L/(w·Δt)` (paper symbols `C`, `vf`, `kj`; see A5 for the naming map).
- Discrete sending flow `D̄ = min(⌊F(t−T1+1) − G(t)⌋, ⌊q̄_down⌋)` and receiving
  flow `S̄ = min(⌊G(t−T2+1) + kj·L − F(t)⌋, ⌊q̄_up⌋)`.
- The integer capacity-token recursion `q̄(t+1) = min(q̄(t) + C·Δt − flow,
  ⌈C·Δt⌉ + 1)`.
- One-to-one, FIFO diverge (Algorithm 1), priority-vector merge (Algorithm 2), and
  the general node model (Algorithm 3), including outbound locking.
- Origin vertical entry queue; destination absorption.
- The four-phase per-step simulation loop and its ordering.

**Verification:** `pytest` runs `test_regression.py`, which asserts exact equality
(`diff == 0`) between `mesoltm` and the `abmmeso`-derived golden values on the
reference network — the concrete guarantee that the changes above are
behaviour-preserving.
