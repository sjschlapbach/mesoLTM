# mesoltm networks

Build networks with the `Network` builder or the convenience builders, then
`compile()` to a `Simulation`. All import from `mesoltm`.

## Network builder

Create a network, add nodes/links, mark origins/destinations.

```python
from mesoltm import Network, Vehicle

net = Network(default_fd={"v_f": 30.0, "w": 6.0, "rho_jam": 0.2})
net.add_node("a", pos=(0.0, 0.0))          # pos optional (auto length + layout)
net.add_node("b", pos=(300.0, 0.0))
l1 = net.add_link("a", "b", length=300.0)  # returns link id; **fd overrides default
net.set_origin("a", vehicles=[Vehicle(vehicle_id=0, origin="a", destination="b", route=[l1])])
net.set_destination("b")
sim = net.compile(time_step=1.0, total_time=300.0)
```

`Network` builder methods:

```python
Network(default_fd=None)                                  # default_fd = {"v_f","w","rho_jam"}
net.add_node(node_id, pos=None) -> node_id
net.add_link(u, v, length=None, link_id=None, **fd) -> int   # length auto from pos if omitted
net.set_origin(node_id, vehicles=None) -> None               # repeated calls append vehicles
net.set_destination(node_id) -> None
net.set_merge_priorities(node_id, {inbound_link_id: share}) -> None
net.compile(time_step, total_time, routing_policy=None, plugins=None,
            injection_budget=0, record_history=False, history_path=None,
            history_classify=None) -> Simulation
```

`compile()` is single-use per `Network` (it splices connector ids into vehicle
routes). Rebuild with fresh `Vehicle` objects to run again.

## compile() parameters

- `routing_policy`: overrides per-vehicle next-link at branching nodes; default =
  follow each vehicle's own route (`StaticRoutePolicy`).
- `plugins`: list of per-step loop hooks (see [plugins.md](plugins.md)).
- `injection_budget`: **REQUIRED if the run uses dynamic injection** — set it to at
  least the number of vehicles that will be added via `Simulation.inject`. It sizes
  the connectors to hold the injected vehicles; leaving the default `0` while
  injecting means injected vehicles can be blocked or dropped. Over-estimate is
  safe; purely static runs are unaffected.
- `record_history`, `history_path`, `history_classify`: animation history capture
  (see [visualization.md](visualization.md)).

## Parallel links (lanes / detours)

Two links between the same node pair (distinct ids). A slow lane has lower
`v_f`/`rho_jam`; a detour has larger `length`.

```python
fast = net.add_link("b", "c", length=300.0, v_f=30.0, rho_jam=0.2)
slow = net.add_link("b", "c", length=300.0, v_f=15.0, rho_jam=0.1)  # parallel
```

## Convenience builders

Build a corridor (chain of links; first node origin, last destination):

```python
from mesoltm import corridor_network
net = corridor_network([300.0, 600.0, 300.0], fd=None, node_prefix="n")  # -> nodes n0..n3
```

Build a grid (nodes addressed by (row, col) tuples):

```python
from mesoltm import grid_network
net = grid_network(rows=4, cols=4, link_length=200.0, spacing=1.0, fd=None,
                   bidirectional=True, skip_nodes=None, skip_edges=None,
                   all_nodes_od=False)
```

## Serialise topology

Round-trip topology (nodes, links, origins, destinations) as a dict:

```python
from mesoltm import network_to_dict, network_from_dict
data = network_to_dict(net)          # {"nodes","links","origins","destinations"}
net2 = network_from_dict(data)
```

## Demand from a time-varying profile

Expand a demand-rate profile (veh/s per equal time-slice) into vehicles instead of
building the list by hand.

```python
from mesoltm import vehicles_from_demand_profile

vehicles = vehicles_from_demand_profile(
    [0.5, 0.8, 0.2], total_time=600.0,   # three 200 s slices
    route=[l1, l2], origin="a", destination="c",
)
net.set_origin("a", vehicles=vehicles)
```

Split demand across routes by integer weight:

```python
vehicles = vehicles_from_demand_profile(
    [0.4] * 15, total_time=150.0,
    route_integer_share={(l_in, l_main, l_out): 1, (l_in, l_detour, l_out): 1},
    random_route=False, origin="O", destination="D",
)
# signature: vehicles_from_demand_profile(demand_pattern, total_time, route=None,
#   route_integer_share=None, random_route=False, origin=0, destination=0)
```

## Low-level assembly (direct attachment, no connectors)

Build Link/node objects yourself and pass them to a Simulation — reproduces paper
scenarios bit-exactly (no auto connectors) and allows an explicit
`priority_vector`.

```python
from mesoltm import (Link, OriginNode, OneToOneNode, MergeNode, DestinationNode,
                     Simulation)

up = Link(link_id=1, length=900, v_f=29.58, w=5.53, rho_jam=0.32)
ramp = Link(link_id=3, length=300, v_f=29.58, w=5.53, rho_jam=0.11)
down = Link(link_id=4, length=900, v_f=29.58, w=5.53, rho_jam=0.32)
nodes = [
    OriginNode(node_id=1, link=up, demand_trips=mainline_trips),
    OriginNode(node_id=2, link=ramp, demand_trips=ramp_trips),
    MergeNode(node_id=4, outbound_link=down, inbound_links=[up, ramp],
              priority_vector=[0, 0, 0, 1]),
    DestinationNode(node_id=5, link=down),
]
sim = Simulation(links=[up, ramp, down], nodes=nodes, time_step=1.0, total_time=3600.0)
sim.run()
```

## Capacity helper

```python
from mesoltm import link_capacity
cap = link_capacity(v_f=30.0, w=6.0, rho_jam=0.2)   # rho_jam*v_f*w/(v_f+w) veh/s
```
