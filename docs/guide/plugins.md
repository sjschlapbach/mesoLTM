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

## Reading the demand for one movement

An access-control plugin often needs the vehicles that want to enter **one specific
outbound link** at a node this step — to admit some and reroute the rest.
`NetworkState.movement_demand(node_id, out_link_id)` returns exactly that: a list of
`VehicleView`s, one per vehicle whose resolved next link at `node_id` is
`out_link_id`, taken from the current LTM sending flow of the node's inbound links in
FIFO order. This covers the real approaches **and** any origin connector — vehicles
still queued on a source connector already carry a route that may load this movement,
so they count too. The number of demanding vehicles is just `len(...)`.

```python
def ration(t, state, plugin):
    demand = state.movement_demand(node_id, out_link)   # list[VehicleView]
    for view in demand[capacity:]:                       # over the cap → divert
        state.set_route(view.vehicle, [view.link_id, *alt_tail])
```

Each `VehicleView` carries the vehicle **and** the inbound link it is on
(`view.link_id`) — the link `set_route` needs to reroute it. Next-link resolution
matches what the node model itself does: it honours an attached
[routing policy](routing.md), otherwise the vehicle's own route. The call is a
**pure query** — it refreshes the inbound links' demand for the current step (so it
works from a plugin, which runs *before* the demand phase) but never changes any
flow result or model state. It is available on `NetworkState`, so any plugin form
can call it.

## Peeking the realized flows

Under congestion the movement demand can far exceed what the node will actually
transfer this step: queued vehicles keep demanding a movement for many steps while
outbound supply, competing movements and the merge priorities let only a few cross.
A plugin that rations, auctions or tolls a movement usually wants only the vehicles
that **will actually cross now** — not the whole queue.

`NetworkState.peek_flows(node_id)` returns exactly that: a read-only replay of the
junction's own flow algorithm (same priorities, FIFO order, per-outbound supply
bookkeeping and locking), keyed by outbound link id, each value the predicted
crossing vehicles as `VehicleView`s in crossing order. Every outbound link id of the
junction is present, possibly with an empty list.

```python
def ration(t, state, plugin):
    crossing = state.peek_flows(node_id)                # dict[int, list[VehicleView]]
    for view in crossing[out_link][capacity:]:          # over the cap → divert
        state.set_route(view.vehicle, [view.link_id, *alt_tail])
```

`supply_overrides` (a `dict[out_link_id, supply]`) replaces the matching outbound
links' receiving flow *in the replay only* — useful when the plugin itself will cap
an entry below the physical supply, or will divert the overflow onto a parallel
link whose room it wants credited to the movement:

```python
crossing = state.peek_flows(node_id, supply_overrides={fast: budget + spare})
```

Like `movement_demand` the call is a **pure query**: it refreshes the junction's
adjacent links' demand/supply for the current step (so it works from a plugin,
before the demand phase) and never moves a vehicle, changes a flow result, or
advances the node's persistent priority cursor. The prediction is exact as long as
routes do not change between the query and the flow phase — the plugin's own
reroutes are, of course, the intended way to deviate from it.

## What plugins can do

- **Reroute** vehicles (rewrite routes, as above).
- **Ration a movement** — read `movement_demand` (everyone wanting the movement) or
  `peek_flows` (only those crossing this step) and admit / divert vehicles (access
  control).
- **Gate/close links** — e.g. drive a routing cost so the router avoids a link.
- **Access control / dispatch** — admit or divert vehicles, often combined with
  [step-driven injection](stepping-and-injection.md).

For a coin-toss bottleneck access policy and a density-based grid rerouter, see
[Examples](examples.md).
