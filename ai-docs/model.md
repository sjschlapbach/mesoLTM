# mesoltm model reference

Concise, factual reference to the discrete LTM `mesoltm` implements. The core
link/node arithmetic is a verbatim port of de Souza et al. (SIMPAT 140 (2025)
103088) and must not be altered.

## Fundamental diagram (per Link)

Each `Link` has a triangular fundamental diagram with three parameters (standard
traffic-engineering notation):

- `v_f` — free-flow speed (m/s)
- `w` — backward shock-wave speed (m/s)
- `rho_jam` — jam density (veh/m)
- `length` (`L`) — link length (m)

Capacity is derived, not set: `capacity = rho_jam * v_f * w / (v_f + w)` (veh/s).

`v_f`, `w`, `rho_jam` live on `Link`/`ConnectorLink`, NOT on `Vehicle`.

## Wave lags (integer steps)

- `T1 = floor(L / (v_f * dt))` — forward (free-flow) travel time
- `T2 = floor(L / (w * dt))` — backward shock-wave travel time
- Jam storage = `rho_jam * L` vehicles

## Sending (demand) and receiving (supply) flows

Per step `t`, from cumulative inflow `F` and outflow `G`:

```
demand D(t) = min( floor(F(t - T1 + 1) - G(t)),  floor(q_downstream(t)) )
supply S(t) = min( floor(G(t - T2 + 1) + rho_jam*L - F(t)),  floor(q_upstream(t)) )
```

Both are integer (one unit of flow = one vehicle). The first term is
free-flow/queue-storage driven; the second is the integer capacity token.

## Integer capacity tokens

Two token buckets per link (discharge `q_downstream`, entry `q_upstream`)
replenish by `capacity*dt` and are debited by actual flow:

```
q(t+1) = min( q(t) + capacity*dt - flow(t),  ceil(capacity*dt) + 1 )
```

This makes the continuous LTM advance one whole vehicle at a time.

## CFL condition (enforced)

The fastest wave must not cross a link in under one step:

```
max(v_f, w) * dt <= length
```

`mesoltm` raises `ValueError` at `start()` if violated (unlike the reference,
which silently collapses the lags). Fix by decreasing `dt` or increasing `length`.

## Node flow-resolution models

Each node turns inbound demand + outbound supply into integer flows, moving
vehicles FIFO. Chosen automatically from in/out degree by the `Network` builder:

- 1→1 `OneToOneNode`: flow = min(demand, supply) (Eq. 11).
- 1→N `DivergeNode`: FIFO split; the whole stream is limited by the first exhausted
  outbound supply (Algorithm 1). The front vehicle's outbound link is read via the
  routing policy.
- N→1 `MergeNode`: shares scarce outbound supply by priority (Algorithm 2).
  Priorities as integer `priority_vector` or shares `alpha` (fractions summing to
  1). Default = capacity-proportional.
- M→N `GeneralNodeModel`: many-to-many with outbound locking (Algorithm 3).
- `OriginNode`: vertical entry queue; releases vehicles at their departure time
  when the first link has supply. `add_trip(vehicle)` adds demand.
- `DestinationNode`: absorbs arrivals; `get_arrived_trips()` returns records.

## Four-phase simulation loop (per step)

Fixed ordering, ported verbatim:

1. Plugins run first (external routing/gating hook).
2. Nodes prepare (origins release departing vehicles).
3. Links compute demand `D` / supply `S`.
4. Nodes compute flows (Algorithms 1–3), move vehicles.
5. Links commit flows into `F`/`G` and refill capacity tokens.

## Connector links (general graphs)

To let any node act as origin/destination, `Network.compile` auto-inserts a
one-cell `ConnectorLink` (transparent buffer: `T1 = T2 = 1`, storage/capacity sized
from the total vehicle count so it never binds). A source connector holds an
origin's whole entry queue. True zero-length links are impossible in the LTM
(storage = `rho_jam*length`), so connectors are one-cell. The paper's validation
scenarios use direct attachment and stay bit-exact. Connector/queue time is
reported as a trip's `access_time`, not in-network `travel_time`.

## Deviations from the paper

All deviations are behaviour-preserving (verified by an exact regression test) or
additive (routing policies, plugins, step/inject, connectors, metrics, viz). See
the "Deviations from the paper" documentation page
(`docs/model/deviations-from-the-paper.md`) for the full catalogue (sections
A1–A8 behaviour-preserving, B1–B5 additive).
