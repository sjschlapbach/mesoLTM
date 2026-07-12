# mesoltm simulation and network state

`Simulation` runs the four-phase LTM loop. `NetworkState` is the live view handed
to routing policies and plugins.

## Running

Batch run (initialise, run whole horizon, write outputs):

```python
sim = net.compile(time_step=1.0, total_time=600.0)
sim.run()                       # -> self
sim.run(progress=True)          # show a tqdm progress bar on stderr while running
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
sim.run(progress=False) -> Simulation      # progress=True -> tqdm bar on stderr
sim.start() -> Simulation
sim.step() -> int                          # runs current_step, returns it
sim.current_step                           # next step to run
sim.total_steps                            # int(total_time / time_step)
sim.inject(node_id, vehicle, at_time=None, check_reentry_node=True)  # add demand mid-run
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

For injection, compile with `injection_budget=N` (N ≥ the number of injections you
will make — count each re-injection); it sizes the O/D connectors to hold them.
Defaults to `100`, but set it explicitly. Inject more than the budget and a
`RuntimeWarning` is emitted — the over-budget vehicle is queued at its origin (waits
for connector space, may not enter within the horizon), never silently dropped.
Over-estimating N is safe.

### Re-injecting a vehicle (multiple journeys)

The **same** `Vehicle` may be injected again after it has completed a trip, to make
another one. Each trip is recorded as a separate journey on `vehicle.journeys` (the
single source of truth all metrics read — see
[vehicles-and-routing.md](vehicles-and-routing.md#journeys-the-single-source-of-truth-for-completed-trips)),
so a re-injected vehicle produces one trip record per journey, just as a static
demand profile produces one vehicle per trip.

```python
v = Vehicle(vehicle_id=7, origin="A", destination="B", route=[l_ab])
sim.inject("A", v)                                   # journey 0: A -> B
while sim.current_step < sim.total_steps and v.active:
    sim.step()                                       # v.active -> False when absorbed at B

v.origin, v.destination, v.route = "B", "C", [l_bc]  # define the next trip's real links
sim.inject("B", v)                                   # journey 1: re-enter at B, B -> C
```

Set `v.route` to the new trip before re-injecting: re-injection resets the live
journey state but not `route` (which still holds the previous spliced route).

#### Re-injection guardrails

`inject` protects re-injection with two checks:

- **Still-active check (mandatory):** if the vehicle has not completed its current
  journey (`vehicle.active is True` — still queued or en route), `inject` raises
  `RuntimeError`. Re-inject only after it has been absorbed at a destination.
- **Re-entry-node check (default on):** the vehicle must re-enter at the **real**
  node where it last left the network (the downstream node of its previous journey's
  final real link — auxiliary O/D connector nodes are never considered). A mismatch
  raises `ValueError`. Pass `check_reentry_node=False` to allow a deliberate re-entry
  elsewhere.

```python
sim.inject("A", v)                          # RuntimeError if v is still active
sim.inject("X", v)                          # ValueError if v last left at some other node
sim.inject("X", v, check_reentry_node=False)  # allowed: skip the node check
```

See `examples/multi_trip_injection.py` for a full runnable demo (A→B→C with B both a
destination and an origin) that prints per-journey metrics and both guardrails.

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
state.continuous_free_flow_time(link_id) -> float     # seconds, length/v_f (dt-agnostic; default routing weight)

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
state.movement_demand(node_id, out_link_id) -> list[VehicleView]  # demand for one movement
state.remaining_real_route(vehicle, current_link_id=None) -> list[int]
state.set_route(vehicle, real_route)       # must start at current link
state.inject(node_id, vehicle, at_time=None, check_reentry_node=True)

state.step                                 # current step (engine-maintained)
```

`VehicleView` is a NamedTuple: `(vehicle, link_id, route, destination)` where
`route` is the remaining real-link route from the current link onward.

`movement_demand(node_id, out_link_id)` returns the vehicles demanding to cross onto
one outbound link at a node this step (the node's per-movement diverge demand): for
each inbound link — real approaches and any origin connector — the current LTM sending
flow whose resolved next link is `out_link_id`, as `VehicleView`s (each carrying the
inbound `link_id`). Connector-queued vehicles are included because their route may
load this movement next step. It honours an attached routing policy (else the
vehicle's own route), and is a pure query — it refreshes the inbound links' demand for
`state.step` so it can be called from a plugin (which runs before the demand phase)
without changing any flow result. Ideal for rationing access to a movement: admit
`demand[:cap]`, reroute the rest with `set_route`.
