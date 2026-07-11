# Building networks

Everything starts with a network: nodes, links, origins, destinations. This page
covers the [`Network`](../reference/network.md) builder and the convenience
builders for common topologies. For the theory behind connectors and parallel
links, see [Networks & connectors](../model/networks-and-connectors.md).

## The `Network` builder

```python
from mesoltm import Network, Vehicle

net = Network(default_fd={"v_f": 30.0, "w": 6.0, "rho_jam": 0.2})

# Nodes (optionally with an (x, y) position for auto lengths and plotting).
net.add_node("a", pos=(0.0, 0.0))
net.add_node("b", pos=(300.0, 0.0))
net.add_node("c", pos=(600.0, 0.0))

# Links (fundamental-diagram params fall back to default_fd). Returns the link id.
l1 = net.add_link("a", "b", length=300.0)
l2 = net.add_link("b", "c", length=300.0)

# Mark origins (with demand) and destinations.
net.set_origin("a", vehicles=[
    Vehicle(vehicle_id=k, scheduled_departure=float(k), origin="a", destination="c", route=[l1, l2])
    for k in range(20)
])
net.set_destination("c")

sim = net.compile(time_step=1.0, total_time=300.0)
sim.run()
```

Builder methods at a glance:

| Method | Purpose |
|--------|---------|
| `add_node(node_id, pos=None)` | Add a node; `pos` enables auto link length + layout. |
| `add_link(u, v, length=None, link_id=None, **fd)` | Directed link; returns its id. Omit `length` to use the Euclidean node distance. |
| `set_origin(node_id, vehicles=None)` | Mark an origin and attach demand (calls append). |
| `set_destination(node_id)` | Mark a destination that absorbs arrivals. |
| `set_merge_priorities(node_id, {link_id: share})` | Override merge priority shares (see [Nodes](../model/nodes.md)). |
| `compile(time_step, total_time, ...)` | Build the runnable simulation (see below). |

!!! warning "`compile()` is single-use"
    Compiling splices connector ids into the vehicles' routes, so a network can
    only be compiled once. To run again, rebuild the network with **fresh**
    `Vehicle` objects.

### `compile()` options

```python
sim = net.compile(
    time_step=1.0,
    total_time=600.0,
    routing_policy=None,      # per-vehicle next-link policy; see Routing guide
    plugins=[],               # per-step loop hooks; see Plugins guide
    injection_budget=100,     # sizes connectors for N dynamic injections (default 100)
    record_history=False,     # capture animation history; see Animations guide
    history_path=None,        # JSON path to save that history on run()
    history_classify=None,    # classify(vehicle, state) -> colour category
)
```

The node model at each junction is chosen automatically from its in/out degree
(one-to-one, diverge, merge, or general), and merge priorities default to
capacity-proportional.

## Convenience builders

### Corridor

A chain of links; the first node is the origin, the last the destination.

```python
from mesoltm import corridor_network
net = corridor_network([300.0, 600.0, 300.0])   # nodes n0..n3
```

### Grid

A `rows × cols` grid addressed by `(row, col)` tuples. Options include
`link_length`, `bidirectional`, holes (`skip_nodes` / `skip_edges`) for a partial
grid, and `all_nodes_od=True` to make every node a valid origin/destination.

```python
from mesoltm import grid_network
net = grid_network(4, 4, link_length=200.0, all_nodes_od=True)
```

### Parallel links (lanes and detours)

Add two links between the same pair of nodes to model a fast/slow lane or a
detour — a detour is just a parallel link with a larger `length`:

```python
fast = net.add_link("b", "c", length=300.0, v_f=30.0, rho_jam=0.2)
slow = net.add_link("b", "c", length=300.0, v_f=15.0, rho_jam=0.1)   # parallel
```

Route vehicles onto whichever you want, or let a [routing policy](routing.md)
choose. See [`parallel_links_demo.py`](examples.md).

## Generating demand from a profile

Instead of building a `Vehicle` list by hand, `vehicles_from_demand_profile`
expands a **time-varying demand rate** into individual vehicles with staggered
departures. Each entry of the profile is a flow rate (veh/s) applied over an equal
slice of the horizon:

```python
from mesoltm import vehicles_from_demand_profile

# 0.5, 0.8, 0.2 veh/s over three equal 200 s slices of a 600 s horizon:
vehicles = vehicles_from_demand_profile(
    [0.5, 0.8, 0.2], total_time=600.0, route=[l1, l2],
    origin="a", destination="c",
)
net.set_origin("a", vehicles=vehicles)
```

Split demand across several routes with `route_integer_share` (a
`{route_tuple: weight}` map; add `random_route=True` to draw routes randomly by
weight instead of round-robin):

```python
vehicles = vehicles_from_demand_profile(
    [0.4] * 15, total_time=150.0,
    route_integer_share={(l_in, l_main, l_out): 1, (l_in, l_detour, l_out): 1},
    origin="O", destination="D",
)
```

The same profile is what a [JSON scenario](../getting-started/running-a-scenario.md)'s
`demand.profile` field drives. See `freeway_onramp.py` and `vehicle_metrics_demo.py`
in [Examples](examples.md).

## Serialising a network

`network_to_dict(net)` and `network_from_dict(data)` round-trip a network's
topology (nodes, links, origins, destinations) as plain dicts — handy for saving
or programmatically transforming a network. For a full runnable configuration
(timing, demand, outputs), use a [JSON scenario](../getting-started/running-a-scenario.md)
instead.

## Low-level assembly (paper-faithful, no connectors)

The `Network` builder is the recommended path. For full control — or to reproduce
a paper scenario with **direct attachment** (no auto-inserted
[connector links](../model/networks-and-connectors.md), so results are bit-exact) —
you can build `Link` and node objects yourself and hand them to a `Simulation`:

```python
from mesoltm import (
    Link, OriginNode, OneToOneNode, MergeNode, DestinationNode,
    Simulation, vehicles_from_demand_profile,
)

upstream = Link(link_id=1, length=900, v_f=29.58, w=5.53, rho_jam=0.32)
ramp     = Link(link_id=3, length=300, v_f=29.58, w=5.53, rho_jam=0.11)
downstream = Link(link_id=4, length=900, v_f=29.58, w=5.53, rho_jam=0.32)

nodes = [
    OriginNode(node_id=1, link=upstream, demand_trips=mainline_trips),
    OriginNode(node_id=2, link=ramp, demand_trips=ramp_trips),
    # explicit integer priority vector (0.75/0.25 mainline:ramp):
    MergeNode(node_id=4, outbound_link=downstream, inbound_links=[upstream, ramp],
              priority_vector=[0, 0, 0, 1]),
    DestinationNode(node_id=5, link=downstream),
]
sim = Simulation(links=[upstream, ramp, downstream], nodes=nodes,
                 time_step=1.0, total_time=3600.0)
sim.run()
```

Here you pick each node model yourself (see [Nodes](../model/nodes.md) and the
[Nodes reference](../reference/nodes.md)) and can pass an explicit
`priority_vector`. This is the style of the `freeway_onramp.py`
[example](examples.md).
