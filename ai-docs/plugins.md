# mesoltm plugins

Plugins are per-step loop hooks that run **first** each step (before flows are
computed), with the live `NetworkState` on `self.state`. Register via
`Network.compile(plugins=[...])`. All import from `mesoltm`.

Rerouting needs no special hook: every vehicle carries its own `route` and the
network only propagates it, so rewriting `vehicle.route` reroutes that vehicle.

## Plugin (base class)

Subclass and override `run_step(t)`.

```python
from mesoltm import Plugin

class MyPlugin(Plugin):
    def run_step(self, t: int) -> None:
        state = self.state           # NetworkState, wired in by compile()
        # inspect/act on the simulation for step t
        ...

sim = net.compile(time_step=1.0, total_time=600.0, plugins=[MyPlugin()])
```

`Plugin(state=None)`; also has `start(time_step, total_time)` and
`run_step(t)`. `state` is attached automatically by `Network.compile`.

## FunctionPlugin

Wrap a plain `fn(t, state)` function.

```python
from mesoltm import FunctionPlugin

def log_load(t, state):
    if t % 60 == 0:
        print(t, sum(state.occupancy(l) for l in state.link_ids()))

sim = net.compile(time_step=1.0, total_time=600.0, plugins=[FunctionPlugin(log_load)])
```

## ReroutingPlugin (minimal rerouting interface)

Each step you receive every in-network vehicle (a `VehicleView`) and return
`{vehicle: new_real_route}` for ONLY the ones to change. The returned route must
start at the vehicle's current link.

```python
from mesoltm import ReroutingPlugin

def divert(t, state, vehicles):
    updates = {}
    for view in vehicles:            # view: VehicleView(vehicle, link_id, route, destination)
        if state.occupancy(view.link_id) > 10:
            updates[view.vehicle] = [view.link_id, alt_next_link, *rest]
    return updates

sim = net.compile(time_step=1.0, total_time=600.0, plugins=[ReroutingPlugin(divert)])
```

`ReroutingPlugin(reroute=None, state=None)`. Alternatively subclass and override
`reroute(t, state, vehicles) -> dict[Vehicle, list[int]]`. Updates are applied via
`NetworkState.set_route`, which validates the route starts at the current link
(rejects strands) and re-attaches the destination connector.

## What plugins can do

- Reroute vehicles (rewrite routes / return updates).
- Gate or close links (e.g. drive a routing cost the router reads).
- Access control / dispatch, often with step-driven injection (see
  [simulation.md](simulation.md)).

The four-phase loop ordering is unchanged; plugins are the same slot the reference
used for signal controllers.
