# mesoltm vehicles and routing

Every unit of flow is one `Vehicle`. Routing chooses each vehicle's next link at a
branching node. All import from `mesoltm`.

## Vehicle

Construct a vehicle. Note: `Vehicle` does NOT take FD params (`v_f`, `w`,
`rho_jam` are `Link` properties).

```python
from mesoltm import Vehicle

v = Vehicle(
    vehicle_id=1,
    origin="a",            # bookkeeping identifier
    destination="c",       # used by routing policies
    start=5.0,             # departure time in seconds
    route=[1, 2, 4],       # ordered real link ids (optional; mutable)
    props={"vclass": "car"},  # free-form metadata dict (optional; JSON-serialisable)
)
```

Signature and attributes:

```python
Vehicle(vehicle_id=0, origin=0, destination=0, start=0.0, route=None, props=None, **kwargs)
# attributes:
v.route        # list[int]: ordered link ids; rewrite to reroute
v.position     # int: index of current link within route
v.props        # dict: per-vehicle metadata (core never reads it)
v.trajectory   # list[dict]: auto-log [{link_id, entry_step, exit_step, is_connector}]
v.end          # int | None: arrival step (set by destination node)
v.journeys     # list[dict]: completed-trip records — the single source of truth
v.active       # bool: True while queued/en route, False once absorbed
```

Routes are **propagated, not imposed**: the network moves each vehicle along
whatever `route` it currently holds. Rewriting `vehicle.route` reroutes it from its
next node onward — this is how all rerouting works.

## Journeys: the single source of truth for completed trips

The live fields (`route`/`position`/`trajectory`/`start`/`end`) describe the
vehicle's **current** journey. When the vehicle is absorbed at a destination the
finished trip is frozen into a **journey record** and appended to `v.journeys`:

```python
journey = {
    "vehicle_id": 7,
    "origin": "A", "destination": "B",
    "start": 0.0,          # desired departure (seconds)
    "end": 21,             # arrival step
    "journey_index": 0,    # 0-based position in v.journeys
    "trajectory": [ {link_id, entry_step, exit_step, is_connector}, ... ],  # a copy
}
```

This is the same record you get on the absorbing destination's `completed_journeys`
list (the same dict object, not a copy) — there is exactly **one** record per
completed trip, and it is what all metrics read (see [metrics.md](metrics.md)).

The key property: this works **identically no matter how the vehicle came to
exist**. A vehicle from a static demand profile completes one journey
(`len(v.journeys) == 1`); a hand-injected vehicle that is re-injected completes one
per trip (`journey_index` 0, 1, 2, …). Demand-profile runs and hand-injected runs
therefore share one consistent accounting path — you never special-case them.

### Re-injecting the same vehicle

You can inject the **same** `Vehicle` object again once it has finished a trip, to
send it on another one (only meaningful in the step-driven workflow — see
[simulation.md](simulation.md)):

```python
v = Vehicle(vehicle_id=7, origin="A", destination="B", route=[l_ab])
sim.inject("A", v)                    # journey 0: A -> B
# ... step until v.active is False (it was absorbed at B) ...

v.origin, v.destination, v.route = "B", "C", [l_bc]   # define the NEXT trip
sim.inject("B", v)                    # journey 1: B -> C
# ... step to completion ...
assert len(v.journeys) == 2
```

Two things to know:

- **Set `v.route` to the new trip's real links before re-injecting.** Re-injection
  resets the live journey state (`trajectory`/`end`/`position`) but deliberately
  does **not** touch `route`, which still holds the previous, connector-spliced
  route. `inject` reads `v.route` as the new real-link route, so you must overwrite
  it (as you would when defining any new trip).
- **Guardrails** enforce sane re-entry — a still-moving vehicle can't be re-injected,
  and by default it must re-enter at the real node where it left. See
  [simulation.md](simulation.md#re-injection-guardrails).

## Routing policies

Three options for deciding a vehicle's next link at a branching node.

### StaticRoutePolicy (default)

Follows each vehicle's own `route`. Used when `compile(routing_policy=None)`.
Reproduces the paper exactly.

```python
from mesoltm import StaticRoutePolicy
policy = StaticRoutePolicy()
```

### ShortestPathPolicy

Plans routes on the live network graph (networkx) toward `vehicle.destination`.

```python
from mesoltm import ShortestPathPolicy

policy = ShortestPathPolicy(cost=None, dynamic=False)
sim = net.compile(time_step=1.0, total_time=400.0, routing_policy=policy)
```

- `dynamic=True`: rebuild the routing graph on every decision (needed when `cost`
  depends on live state).
- `cost=callable`: `cost(link_id, state) -> float`; default = free-flow time.

Congestion-aware cost using live `NetworkState`:

```python
def congestion_cost(link_id, state):
    return state.free_flow_time(link_id) + 0.5 * state.occupancy(link_id)

policy = ShortestPathPolicy(cost=congestion_cost, dynamic=True)
```

Extra methods on `ShortestPathPolicy`:

```python
policy.route(state, from_node, to_node) -> list[int]   # full shortest real-link route
policy.refresh(state) -> None                          # rebuild cached graph once
policy.next_link(vehicle, current_link_id, node, state) -> int | None
```

### Custom policy (RoutingPolicy protocol)

Implement `next_link(vehicle, current_link_id, node, state) -> int | None`.

```python
from mesoltm import RoutingPolicy   # runtime_checkable Protocol
```

## Rerouting

Routing is a layer around the flow arithmetic and never changes model dynamics.
For event-driven rerouting (not just a cost), use a plugin — see
[plugins.md](plugins.md). `ShortestPathPolicy(dynamic=True)` reroutes automatically
as costs change.
