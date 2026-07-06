# mesoltm simulation and network state

`Simulation` runs the four-phase LTM loop. `NetworkState` is the live view handed
to routing policies and plugins.

## Running

Batch run (initialise, run whole horizon, write outputs):

```python
sim = net.compile(time_step=1.0, total_time=600.0)
sim.run()                       # -> self
```

Step-driven run (observe / inject between steps):

```python
sim = net.compile(time_step=1.0, total_time=600.0, injection_budget=100)
sim.start()                     # idempotent; init links/nodes/plugins
while sim.current_step < sim.total_steps:
    t = sim.step()              # run one step, return its index
    state = sim.network_state   # inspect between steps
```

`run()` == `start()` + loop of `step()` + `write_outputs()`, so results are
identical.

## Simulation API

```python
sim.run() -> Simulation
sim.start() -> Simulation
sim.step() -> int                          # runs current_step, returns it
sim.current_step                           # next step to run
sim.total_steps                            # int(total_time / time_step)
sim.inject(node_id, vehicle, at_time=None) # add demand mid-run (real-link route)
sim.network_state                          # NetworkState
sim.history                                # SimulationHistory | None (if record_history)
sim.save_history(path=None) -> str
sim.nodes, sim.links, sim.time_step, sim.total_time
```

Count arrivals after a run:

```python
arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
```

## Dynamic injection

`inject` adds a vehicle to an origin's demand during a run; supply a route over
REAL link ids (connectors are spliced automatically). `at_time` defaults to the
current step's time.

```python
from mesoltm import Vehicle
sim.inject("a", Vehicle(vehicle_id=999, origin="a", destination="c", route=[l1, l2]))
```

Compile with `injection_budget=N` so connectors stay transparent for N injections.

## NetworkState API

Handed to routers/plugins; read-only queries plus rerouting/injection seams.

```python
# topology
state.nodes() -> list
state.link_ids() -> list[int]              # real + connector
state.out_links(node_id) -> list[int]
state.in_links(node_id) -> list[int]
state.links_between(u, v) -> list[int]
state.endpoints(link_id) -> tuple | None   # (u, v); None for connectors
state.position(node_id) -> tuple | None

# static link attributes
state.length(link_id) -> float
state.capacity(link_id) -> float           # veh/s
state.free_flow_time(link_id) -> float     # seconds

# live state
state.vehicles_on(link_id) -> list
state.occupancy(link_id) -> int            # vehicles on link now
state.density(link_id) -> float            # veh/m
state.entry_queue(node_id) -> int          # count waiting at origin
state.waiting_vehicles(node_id) -> list

# cumulative
state.cumulative_inflow(link_id, t=None) -> float
state.cumulative_outflow(link_id, t=None) -> float

# rerouting / dynamic demand
state.vehicles_in_network() -> list[VehicleView]
state.remaining_real_route(vehicle, current_link_id=None) -> list[int]
state.set_route(vehicle, real_route)       # must start at current link
state.inject(node_id, vehicle, at_time=None)

state.step                                 # current step (engine-maintained)
```

`VehicleView` is a NamedTuple: `(vehicle, link_id, route, destination)` where
`route` is the remaining real-link route from the current link onward.
