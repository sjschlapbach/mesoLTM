# Plugins

A **plugin** is the framework's general extension point: a per-step hook that runs
**first** each step — before the node models resolve flows — with the live
[`NetworkState`](../reference/network.md#network-state) available on `self.state`.
From there it can reroute vehicles, gate or close links, drive a dispatcher, or
run an access policy. Because plugins run first, any change is seen by the same
step's flow resolution.

Register plugins at compile time:

```python
sim = net.compile(time_step=1.0, total_time=600.0, plugins=[my_plugin])
```

## Three interfaces, simplest last

### `Plugin` — full control

Subclass and override `run_step(t)`:

```python
from mesoltm import Plugin

class CloseLinkAt(Plugin):
    def __init__(self, link_id, close_step):
        super().__init__()
        self.link_id, self.close_step = link_id, close_step

    def run_step(self, t):
        if t == self.close_step:
            # e.g. reroute everyone currently heading through the link, or
            # inflate a routing cost the router reads — self.state is the live view.
            ...
```

### `FunctionPlugin` — wrap a function

```python
from mesoltm import FunctionPlugin

def log_load(t, state):
    if t % 60 == 0:
        print(t, sum(state.occupancy(l) for l in state.link_ids()))

sim = net.compile(time_step=1.0, total_time=600.0,
                  plugins=[FunctionPlugin(log_load)])
```

### `ReroutingPlugin` — the minimal rerouting form

Each step you are handed a snapshot of every in-network vehicle (its current link,
destination, and remaining real-link route). Return a mapping
`{vehicle: new_real_route}` for **only** the vehicles to change; everything else is
left untouched.

```python
from mesoltm import ReroutingPlugin

def divert(t, state, vehicles):
    updates = {}
    for view in vehicles:
        if state.occupancy(view.link_id) > 10:          # link is busy
            # a valid update starts at the vehicle's current link:
            updates[view.vehicle] = [view.link_id, alt_next, *rest]
    return updates

sim = net.compile(time_step=1.0, total_time=600.0,
                  plugins=[ReroutingPlugin(divert)])
```

The returned route must **start at the vehicle's current link** (that is exactly
how `VehicleView.route` is presented). `set_route` validates this and re-attaches
the destination connector, so a bad update can never strand a vehicle.

## Why rerouting needs no special hook

Every vehicle stores its own `route`, and the network only *propagates* it. So
rewriting `vehicle.route` reroutes that one vehicle from its next node onward —
which is all any of the interfaces above ultimately do. This is the same loop slot
the reference used for signal controllers; the four-phase ordering is unchanged.
See [Deviations §B3](../model/deviations-from-the-paper.md).

## What plugins can do

- **Reroute** vehicles (rewrite routes, as above).
- **Gate/close links** — e.g. drive a routing cost so the router avoids a link.
- **Access control / dispatch** — admit or divert vehicles, often combined with
  [step-driven injection](stepping-and-injection.md).

For a coin-toss bottleneck access policy and a density-based grid rerouter, see
[Examples](examples.md).
