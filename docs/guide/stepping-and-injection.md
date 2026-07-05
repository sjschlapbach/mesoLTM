# Stepping & dynamic injection

`run()` executes the whole horizon at once. To drive an **external control loop** —
observing the network between steps and adding vehicles on demand — use
`start()` / `step()` and `inject()`. See
[The simulation loop](../model/simulation-loop.md) for the phase ordering.

## Step-driven execution

```python
sim = net.compile(time_step=1.0, total_time=600.0, injection_budget=100)
sim.start()

while sim.current_step < sim.total_steps:
    t = sim.step()                     # runs one step, returns its index
    state = sim.network_state          # inspect the live state between steps
    load = sum(state.occupancy(l) for l in state.link_ids())
    # ... react: decide what to inject next, log, adjust an external policy ...
```

- `start()` initialises links, nodes, and plugins (idempotent).
- `step()` runs the four-phase loop for `current_step` and increments it.
- `current_step` is the next step to run; `total_steps` is `total_time / dt`
  floored.

`run()` is exactly `start()` + a loop of `step()` + writing outputs, so batch and
step-driven runs produce identical results.

## Injecting vehicles mid-run

`inject()` adds a vehicle to an origin's demand during the run. You supply a route
over **real** link ids; the origin/destination [connectors](../model/networks-and-connectors.md)
are spliced on automatically, and the vehicle enters the origin's departure queue
in time order.

```python
from mesoltm import Vehicle

# Between steps, release a new vehicle from an origin toward a destination now:
sim.inject("a", Vehicle(vehicle_id=999, origin="a", destination="c", route=[l1, l2]))
# at_time defaults to the current step's time, so it is considered next step.
```

!!! tip "Size the connectors for injection"
    Compile with `injection_budget=N` so the origin/destination connectors stay
    transparent for the static demand *plus* `N` dynamic injections. An origin that
    carries little or no static demand would otherwise get a connector sized to
    pass only one vehicle per step. Over-estimating is safe — a larger budget only
    makes connectors *more* transparent, never more binding, and purely static runs
    are unaffected.

Injection only appends to a node's demand list, exactly as static demand does — it
never perturbs the per-step arithmetic. See [Deviations §B5](../model/deviations-from-the-paper.md).

## Seeding an injected route with shortest path

To inject toward a destination without hand-writing the route, plan it first with
a [`ShortestPathPolicy`](routing.md):

```python
from mesoltm import ShortestPathPolicy
policy = ShortestPathPolicy(dynamic=True)
route = policy.route(sim.network_state, from_node="a", to_node="c")
sim.inject("a", Vehicle(vehicle_id=999, origin="a", destination="c", route=route))
```

For a full worked example (a coin-toss bottleneck admission policy driven with
`start`/`step`/`inject`), see [`bottleneck_access_policy.py`](examples.md).
