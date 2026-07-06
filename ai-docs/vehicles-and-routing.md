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
```

Routes are **propagated, not imposed**: the network moves each vehicle along
whatever `route` it currently holds. Rewriting `vehicle.route` reroutes it from its
next node onward — this is how all rerouting works.

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
