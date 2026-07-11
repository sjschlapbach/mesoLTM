# mesoltm quickstart

Minimal runnable patterns. All symbols import from the top-level `mesoltm` package.

## Corridor (single path)

Build a chain of links; first node is origin, last is destination. Routes fill in
automatically on a single path.

```python
from mesoltm import Vehicle, corridor_network

net = corridor_network([300.0, 300.0, 300.0])   # nodes n0..n3
net.set_origin("n0", vehicles=[
    Vehicle(vehicle_id=k, scheduled_departure=2.0 * k, origin="n0", destination="n3")
    for k in range(40)
])
net.set_destination("n3")
sim = net.compile(time_step=1.0, total_time=300.0)
sim.run()
arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
```

## Grid with shortest-path routing

Grid nodes are addressed by `(row, col)` tuples. `all_nodes_od=True` makes every
node a valid origin/destination.

```python
from mesoltm import Vehicle, grid_network, ShortestPathPolicy

net = grid_network(4, 4, link_length=200.0, all_nodes_od=True)
net.set_origin((0, 0), vehicles=[
    Vehicle(vehicle_id=k, scheduled_departure=float(k), origin=(0, 0), destination=(3, 3))
    for k in range(50)
])
sim = net.compile(time_step=1.0, total_time=400.0,
                  routing_policy=ShortestPathPolicy(dynamic=True))
sim.run()
```

## Explicit network with explicit routes

Add nodes/links manually; give each vehicle a route over real link ids.

```python
from mesoltm import Network, Vehicle

net = Network(default_fd={"v_f": 30.0, "w": 6.0, "rho_jam": 0.2})
l1 = net.add_link("a", "b", length=300.0)
l2 = net.add_link("b", "c", length=300.0)
net.set_origin("a", vehicles=[
    Vehicle(vehicle_id=0, origin="a", destination="c", route=[l1, l2])
])
net.set_destination("c")
sim = net.compile(time_step=1.0, total_time=300.0)
sim.run()
```

## Read per-vehicle metrics

```python
from mesoltm import collect_trips, summarize_trips
trips = collect_trips(sim)          # list of per-vehicle dicts
summary = summarize_trips(trips)    # dict of aggregates
# summary keys include: n_trips, n_completed, mean_travel_time, total_vehicle_hours
```

## Run a JSON scenario from the CLI

```bash
python -m mesoltm scenario.json     # writes any configured link/trip CSVs
```

See [scenarios-cli.md](scenarios-cli.md) for the JSON schema.
