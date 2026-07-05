# Routing

At a branching node, a **routing policy** decides which outbound link each vehicle
takes. Because every vehicle carries its own mutable `route`, routing is a thin
layer *around* the flow arithmetic — it only chooses next links and never changes
the model dynamics. See [Vehicles & routing](../model/vehicles-and-routing.md).

## The three options

### Static routes (default)

With no policy, `StaticRoutePolicy` reads each vehicle's own `route`. Give each
vehicle a route over real link ids and the network follows it:

```python
from mesoltm import Vehicle
v = Vehicle(vehicle_id=1, origin="a", destination="c", route=[l1, l2])
```

This reproduces the paper's behaviour exactly.

### Shortest path

`ShortestPathPolicy` plans each vehicle's path over the live network graph (via
NetworkX) toward its `destination`. Pass it to `compile()`:

```python
from mesoltm import grid_network, ShortestPathPolicy

net = grid_network(4, 4, link_length=200.0, all_nodes_od=True)
# ... set origins/destinations ...
sim = net.compile(time_step=1.0, total_time=400.0,
                  routing_policy=ShortestPathPolicy(dynamic=True))
```

`dynamic=True` rebuilds the routing graph on every decision, so a changing cost
takes effect immediately (rerouting happens automatically).

### Your own policy

Any object implementing the [`RoutingPolicy`](../reference/routing.md) protocol —
a single `next_link(vehicle, current_link_id, node, state) -> int | None` — can be
used.

## Congestion-aware cost

By default `ShortestPathPolicy` minimises free-flow travel time. Supply a `cost`
callback `cost(link_id, state) -> float` to route on live conditions — the `state`
is the [`NetworkState`](../reference/network.md#network-state), so you can read
`occupancy`, `density`, or cumulative flows:

```python
def congestion_cost(link_id, state):
    # free-flow time plus a penalty that grows with the link's current load
    return state.free_flow_time(link_id) + 0.5 * state.occupancy(link_id)

policy = ShortestPathPolicy(cost=congestion_cost, dynamic=True)
```

This spreads traffic onto slower lanes and detours as they become the faster
choice. See [`parallel_links_demo.py`](examples.md) and
[`congestion_aware_routing.py`](examples.md).

## Planning full routes

`ShortestPathPolicy` also exposes a `route(state, from_node, to_node)` planner that
returns the full ordered list of real link ids — useful to seed a vehicle's route
before [injecting](stepping-and-injection.md) it, or inside a
[rerouting plugin](plugins.md). When re-planning many vehicles against the *same*
live state in one step, call `refresh(state)` once and temporarily set
`dynamic=False` so the lookups reuse one graph build.

## Reactive rerouting

For rerouting driven by events rather than a static cost — coin-toss access
control, closing a link, re-planning at every node — use a
[plugin](plugins.md). It runs first each step and can rewrite any in-network
vehicle's route.
