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

## Demand for one movement (access control)

`NetworkState.movement_demand(node_id, out_link_id) -> list[VehicleView]` returns
the vehicles demanding to cross onto ONE outbound link at a node this step: for each
inbound link, the current LTM sending flow (first `get_demand()` vehicles, FIFO) whose
resolved next link is `out_link_id`. `len(...)` is the count. Each `VehicleView`
carries the vehicle and its inbound `link_id`, so you can reroute the overflow with
`set_route(vehicle, [link_id, *alt_tail])`.

```python
def ration(t, state, plugin):
    demand = state.movement_demand(node_id, out_link)     # list[VehicleView]
    for view in demand[cap:]:                              # over capacity → divert
        state.set_route(view.vehicle, [view.link_id, *alt_tail])
```

- Next-link resolution matches the node model: an attached routing policy if any,
  otherwise the vehicle's own route.
- Pure query: it refreshes the inbound links' demand for `state.step` (so it works
  from a plugin, which runs BEFORE the demand phase) via the idempotent
  `Link.compute_demand_and_supplies`, and never changes flow results or model state.
- Inbound links include any origin connector — vehicles queued on a source connector
  carry routes that may load this movement, so they are counted (their `link_id` is
  the connector). Only real approaches have topology `endpoints`.

## Predicted crossings (realized flows, not demand)

Under congestion `movement_demand` includes the whole standing queue, but only a few
vehicles actually cross per step. `NetworkState.peek_flows(node_id,
supply_overrides=None) -> dict[int, list[VehicleView]]` replays the junction's OWN
flow algorithm read-only (same priorities, FIFO, per-outbound supply bookkeeping and
locking) and returns, per outbound link id, exactly the vehicles that will cross this
step, in crossing order. Every outbound link id of the junction is a key (possibly
`[]`).

```python
crossing = state.peek_flows(node_id)                     # dict[int, list[VehicleView]]
batch = crossing[out_link]                               # will actually cross now
crossing = state.peek_flows(node_id, supply_overrides={out_link: cap})
```

- `supply_overrides` (`out_link_id -> supply`) replaces the matching links' receiving
  flow in the replay only — e.g. a cap the plugin itself will enforce, or extra room
  on a parallel link it will divert the overflow onto.
- Pure query like `movement_demand`: refreshes the junction's adjacent links'
  demand/supply for `state.step`; never moves a vehicle or advances the node's
  persistent priority cursor.
- Exact as long as routes do not change between the query and the flow phase (the
  plugin's own reroutes are the intended deviation).
- Unknown node / no through-junction model: `RuntimeWarning` + `{}` (like
  `movement_demand`).

## What plugins can do

- Reroute vehicles (rewrite routes / return updates).
- Ration a movement — `movement_demand` (everyone wanting it) or `peek_flows` (only
  this step's actual crossers), then admit/divert.
- Gate or close links (e.g. drive a routing cost the router reads).
- Access control / dispatch, often with step-driven injection (see
  [simulation.md](simulation.md)).

The four-phase loop ordering is unchanged; plugins are the same slot the reference
used for signal controllers.
