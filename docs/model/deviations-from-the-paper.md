# Deviations from the paper

`mesoltm` is a re-implementation of the discrete Link Transmission Model of
de Souza, Verbas, Auld & Tampère.[^paper] The guiding principle is to **change
the model only where strictly necessary**: the core traffic-flow mathematics — the
link sending/receiving flows, the $T_1$/$T_2$ wave lags, the integer
capacity-token discretisation, and the node flow-resolution algorithms — is ported
**verbatim**, with identical arithmetic and ordering.

This page catalogues every way `mesoltm` differs from the paper and its reference
implementation (`abmmeso`). The differences fall into two kinds:

- **Behaviour-preserving refinements** (§A) — changes that do not affect results.
- **Additive extensions** (§B) — new capabilities that leave the original dynamics
  untouched when they are not used.

The section labels (A1–A8, B1–B5) are stable identifiers referenced from elsewhere
in this documentation (e.g. "see Deviations §A5").

---

## A. Behaviour-preserving refinements

These change *how* the model is expressed or instrumented, not *what* it computes.

### A1 · Pluggable next-link lookup at branching nodes

At a diverge, general, or signalised node the paper reads a vehicle's next link
directly from its route. `mesoltm` delegates that single lookup to a
[`RoutingPolicy`](../guide/routing.md). The default policy, `StaticRoutePolicy`,
reads `vehicle.route` and so reproduces the original behaviour exactly; supplying a
different policy (shortest path, access rules, auctions) is what enables external,
per-vehicle routing. The flow-resolution arithmetic — demand, supply, priority
merging, FIFO diverging, outbound locking — is unchanged; only *which* outbound
link a vehicle is assigned to can be overridden, and only when a non-default policy
is used.

### A2 · Per-vehicle route position pointer

The paper locates a vehicle's current link by the **first** occurrence of the
inbound link id in its route. `mesoltm` also tracks a `position` index that advances
as the vehicle moves, so routes that revisit a link (possible on general grids)
resolve to the correct occurrence. For any simple path — including all of the
paper's scenarios — this is identical to the first-occurrence lookup; for cyclic
routes on grids it is a strict correctness improvement.

### A3 · Transient flow scalars reset to zero, not `None`

At the end of each step the reference resets a link's transient flow scalars
(demand, supply, inflow, outflow) to `None` as a defensive guard; `mesoltm` resets
them to `0`. This exists purely so the ported code carries clean, non-`Optional`
type annotations. The fixed loop order guarantees these values are always recomputed
before they are next read, so `0` versus `None` is never observed.

### A4 · Naming and packaging only

Files use `snake_case` and classes `PascalCase`; a few reference names were
modernised (`Trip` → `Vehicle`, `SimulationRunner` → `Simulation`), duplicate
definitions were collapsed, and the code was arranged into a proper `src/` package.
These are cosmetic and do not touch the dynamics.

### A5 · Standard traffic-engineering notation

Fundamental-diagram identifiers use conventional traffic-engineering symbols
instead of the paper's spellings. **Only the names change — never the values.**

| Quantity | Paper / `abmmeso` | `mesoltm` |
|----------|-------------------|-----------|
| Free-flow speed | `vf` | `v_f` |
| Backward wave speed | `w` | `w` (unchanged) |
| Jam density | `kj` | `rho_jam` |
| Capacity (max flow) | `cap` / `C` | `capacity` |
| Density (accessor) | — | `density` |
| Occupancy (accessor) | — | `occupancy` |

These are the public keyword names (`Link(v_f=30, w=6, rho_jam=0.2)`) and the JSON
scenario keys (`"v_f"`, `"rho_jam"`). The underlying relationships are identical —
`capacity = rho_jam·v_f·w/(v_f + w)`, `T1 = L/(v_f·Δt)`, `T2 = L/(w·Δt)`, jam
storage `rho_jam·L`. Only the names change. See
[Links & the fundamental diagram](links-and-fd.md).

### A6 · Per-vehicle trajectory recording

The paper exposes only aggregate cumulative in/outflows per link and stamps each
vehicle's arrival step. `mesoltm` additionally has each `Vehicle` carry a
`trajectory` log: the link timestamps the vehicle's entry and exit as it is placed
on and discharged from the link. From this log the [metrics](../guide/metrics.md)
module derives, per vehicle, the route actually driven, per-link travel times, and
three durations — `access_time` (origin-queue wait plus any supply-limited O/D
connector wait), `network_time` (time on real links only), and `travel_time`
(desired departure to arrival, with each connector's one-step free-flow lag
removed but any supply-limited connector waiting kept). The recording only writes
to bookkeeping attributes; it reads nothing back into the flow arithmetic, so
results are unchanged.

### A7 · The CFL condition is enforced

The paper (Section 3.3) states the Courant–Friedrichs–Lewy condition — the fastest
wave must not cross a link in less than one step, `max(v_f, w)·dt ≤ length` — but
the reference code does not check it: it floors the wave lags, silently accepting a
too-short link and simulating it with collapsed lags. `mesoltm` validates the
condition in `Link.start` and raises a `ValueError` (naming the offending values and
the fix) when it is violated, with a tiny tolerance admitting the exactly-one-step
boundary so auto-configured connectors pass. For any CFL-satisfying network — all
paper scenarios — nothing changes; a previously silent mis-discretisation simply
becomes an explicit error.

### A8 · Links hold no time state

In the reference, each link stores its own copy of the time step, total time, step
count, and current step index. In `mesoltm` the **`Link` stores no time state**:
`start(time_step, total_time)` uses those values locally to size arrays and derive
the fixed `T1`/`T2` lags and capacity, then discards them, and the `Simulation`
loop owns the clock and passes what each per-step method needs. This keeps time in
one place so a link can never hold a stale copy. The arithmetic is byte-identical.

---

## B. Additive extensions

These add capabilities *around* the model. When they are not used, the model is
exactly the paper's model.

### B1 · Origin/destination connector links for general graphs

The paper attaches an origin or destination directly to a single link. So that
**any node of a general graph** can act as an origin and/or destination — including
junctions with several links and through traffic — the [`Network`](../guide/building-networks.md)
builder auto-inserts a short **connector link** between the origin/destination node
and the junction (only when the node is not a "pure" single-link endpoint, in which
case the paper's direct attachment is used unchanged).

A connector is an ordinary discrete-LTM link with auto-derived parameters (the user
never configures it): a free-flow travel time of exactly one step and storage and
capacity sized from the total vehicle count so that **neither ever binds**. It is a
transparent buffer — the adjacent origin, junction, or destination always governs
the flow — and a source connector holds an origin's entire entry queue, so vehicles
never queue at the origin *and* on the connector at once.

A true zero-length connector is impossible in the LTM, because a link's storage is
`rho_jam·length` and a zero-length link could hold no vehicle; the connector is
therefore the minimal approximation, a **one-cell** link that adds a one-step
free-flow lag at entry and exit. Connectors appear only with the general-graph
builder. The metrics **remove that one free-flow step** from a trip's travel time
(so an empty connector adds nothing), while any *extra* time a vehicle waits on a
connector because downstream space is the binding constraint is kept as the trip's
access time, never as in-network travel time. See
[Networks & connectors](networks-and-connectors.md).

### B2 · Merge priorities as shares, defaulting to capacity-proportional

The paper supplies a merge/general node's priority as an explicit integer
`priority_vector`. `mesoltm` additionally accepts the priority as **shares**
`alpha` — `alpha[i]` is the fraction of outbound supply inbound link `i` may claim,
summing to 1 — and converts it internally to the reference integer vector the node
arithmetic consumes; the ported node code is untouched. When **neither** a
`priority_vector` nor `alpha` is given, an unprioritised merge defaults to
**capacity-proportional** shares (each inbound link weighted by its own capacity)
rather than equal shares, matching the paper's observation that priority vectors are
used precisely to mimic capacity- or lane-count-proportional merges. Any node with
an explicit priority — all paper examples — is unaffected. See
[Nodes & flow resolution](nodes.md).

### B3 · Plugin hook for external per-step logic

`mesoltm` exposes the engine's existing "run first each step" slot — the same hook
`abmmeso` used for signal controllers — as a typed [`Plugin`](../guide/plugins.md)
interface for access rules, reactive rerouting, link gating, and dispatchers. The
four-phase loop ordering is unchanged. Rerouting needs no special hook: because each
vehicle carries its own `route` and the network only propagates it, a plugin
reroutes a vehicle simply by rewriting that route. This is a plugin-layer feature
and never touches the flow arithmetic.

### B4 · Built-in shortest-path routing

An optional [`ShortestPathPolicy`](../guide/routing.md) (built on NetworkX) is
provided as a convenience router, with an optional congestion-aware cost. Being a
routing policy (§A1), it is entirely opt-in and never affects the flow arithmetic.

### B5 · Step-driven execution and dynamic injection

Alongside batch `run()`, `Simulation` offers `start()` + `step()` to advance one
step at a time, plus `inject()` to add a vehicle to an origin's demand mid-run —
enough to drive an external control loop that observes the network between steps
(an admission policy or dispatcher). `run()` is literally `start()` followed by a
loop of `step()` and output writing, so its behaviour is unchanged, and injection
only appends to a node's demand list exactly as static demand does. Connectors are
sized for the static demand plus a declared `injection_budget`, which only makes
them *more* transparent and so cannot perturb dynamics. See
[Stepping & dynamic injection](../guide/stepping-and-injection.md).

---

## What is unchanged

The following are carried over verbatim from the paper, with identical arithmetic
and ordering:

- Link capacity `capacity = rho_jam·v_f·w/(v_f + w)`, and the step lags
  `T1 = L/(v_f·Δt)`, `T2 = L/(w·Δt)`.
- The discrete sending flow `D̄ = min(⌊F(t−T1+1) − G(t)⌋, ⌊q̄_down⌋)` and receiving
  flow `S̄ = min(⌊G(t−T2+1) + rho_jam·L − F(t)⌋, ⌊q̄_up⌋)`.
- The integer capacity-token recursion
  `q̄(t+1) = min(q̄(t) + capacity·Δt − flow, ⌈capacity·Δt⌉ + 1)`.
- The one-to-one node, the FIFO diverge (Algorithm 1), the priority-vector merge
  (Algorithm 2), and the general node model (Algorithm 3), including outbound
  locking.
- The origin's vertical entry queue and the destination's absorption.
- The four-phase per-step simulation loop and its ordering.

[^paper]: F. de Souza, O. Verbas, J. Auld, C. M. J. Tampère, *"A mesoscopic
    link-transmission-model able to track individual vehicles"*, Simulation
    Modelling Practice and Theory **140** (2025) 103088.
    DOI: [10.1016/j.simpat.2025.103088](https://doi.org/10.1016/j.simpat.2025.103088).
