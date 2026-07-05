# Quickstart

This page runs a small network end to end: build a topology, add demand, compile
to a simulation, run it, and read the results. It assumes `mesoltm` is
[installed](installation.md).

## A corridor

The simplest network is a **corridor** — a chain of links. `corridor_network`
builds one from a list of link lengths; the first node is the origin and the last
is the destination.

```python
from mesoltm import Vehicle, corridor_network

# Three links of 300 m each: n0 -> n1 -> n2 -> n3.
net = corridor_network([300.0, 300.0, 300.0])

# Release 40 vehicles from the first node, one every 2 s, all bound for the last.
net.set_origin("n0", vehicles=[
    Vehicle(vehicle_id=k, start=2.0 * k, origin="n0", destination="n3")
    for k in range(40)
])
net.set_destination("n3")

sim = net.compile(time_step=1.0, total_time=300.0)
sim.run()

arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
print(f"{arrived} vehicles arrived")
```

With a single path, each vehicle's `route` is filled in automatically. On networks
with choices, you either give each vehicle an explicit `route` or supply a
[routing policy](../guide/routing.md).

## A grid with shortest-path routing

`grid_network` builds a rows×cols grid. With `all_nodes_od=True`, every node can
be an origin or a destination, and `ShortestPathPolicy` plans each vehicle's path
over the live graph.

```python
from mesoltm import Vehicle, grid_network, ShortestPathPolicy

net = grid_network(4, 4, link_length=200.0, all_nodes_od=True)
net.set_origin((0, 0), vehicles=[
    Vehicle(vehicle_id=k, start=float(k), origin=(0, 0), destination=(3, 3))
    for k in range(50)
])

sim = net.compile(
    time_step=1.0,
    total_time=400.0,
    routing_policy=ShortestPathPolicy(dynamic=True),
)
sim.run()
print(sum(len(n.get_arrived_trips()) for n in sim.nodes), "vehicles arrived")
```

Grid nodes are addressed by `(row, col)` tuples. `dynamic=True` re-plans on the
live graph so the policy can react to a cost that changes with congestion.

## Reading results

After `run()`, inspect the network and derive per-vehicle metrics:

```python
from mesoltm import collect_trips, summarize_trips

trips = collect_trips(sim)          # one record per vehicle
summary = summarize_trips(trips)    # network-level aggregates
print(summary["n_completed"], "completed;",
      round(summary["mean_travel_time"], 1), "s mean travel time")
```

See [Metrics & trip analysis](../guide/metrics.md) for the full record schema, and
[Visualizations](../guide/visualizations.md) to plot flows and travel times.

## Next steps

- Prefer a config file over Python? See [Running a scenario](running-a-scenario.md).
- Want to understand *what* the model computes? Read [The Model](../model/overview.md).
- Ready to build real networks, reroute vehicles, or animate a run? Head to the
  [User Guide](../guide/building-networks.md).
