# Networks & connector links

`mesoltm` lets **any node of a general graph** act as an origin and/or
destination — including busy junctions that also carry through traffic. To make
that possible, the [`Network`](../reference/network.md) builder inserts short
**connector links** where needed, so an origin or destination is never restricted
to being a plain single-link endpoint. Understanding these connectors explains a
few things you will see in outputs.

## Building on a general graph

`Network` lets you add arbitrary nodes and links, mark any node as an
origin/destination, then `compile()` to a simulation:

```python
from mesoltm import Network, Vehicle

net = Network()
for nid in ("a", "b", "c"):
    net.add_node(nid)
l1 = net.add_link("a", "b", length=300.0, v_f=30.0, w=6.0, rho_jam=0.2)
l2 = net.add_link("b", "c", length=300.0, v_f=30.0, w=6.0, rho_jam=0.2)

net.set_origin("a", vehicles=[Vehicle(vehicle_id=0, origin="a", destination="c")])
net.set_destination("c")
sim = net.compile(time_step=1.0, total_time=300.0)
```

The `compile()` step wires up node models, computes capacity-proportional merge
priorities, and inserts connector links where an origin/destination is not a
"pure" single-link endpoint. See [Building networks](../guide/building-networks.md)
for the full builder API.

## What a connector link is

A connector is an ordinary discrete-LTM link with **auto-derived** parameters (you
never configure it), designed to be a **transparent buffer** — never itself the
binding constraint:

- Free-flow travel time of exactly **one step** ($T_1 = T_2 = 1$).
- Storage and capacity sized from the total vehicle count so neither ever binds; a
  **source connector holds the origin's entire entry queue**, so vehicles never
  double-buffer at the origin and on the connector.

Because a connector crosses in one free-flow step, a vehicle entering an empty
connector enters the network immediately once served. The [metrics](../guide/metrics.md)
**remove that one free-flow step** from a trip's travel time, so an empty,
unrestricted connector adds nothing. If a vehicle is instead held on a connector
*longer* than one step — because downstream space is the binding constraint — that
extra time is a real wait to enter/leave the network and is **kept**, reported as
the trip's **access time**. Either way, in-network `network_time` stays
connector-free.

## Why not zero-length connectors?

The design intent was zero-length connectors, but a **true zero-length link is
impossible in the LTM**: a link's storage is `rho_jam · length`, so a zero-length
link could never hold a vehicle. The connector is therefore the minimal faithful
approximation — a **one-cell** link that adds at most a one-step free-flow lag at
entry/exit.

Connectors are inserted **only by the general-graph builder, and only where
needed**: when an origin or destination is already a plain single-link endpoint,
it is attached directly and no connector is added. See
[Deviations §B1](deviations-from-the-paper.md).

## Parallel links

`Network` supports **parallel links** — two links sharing the same pair of
endpoints (a fast and a slow lane, or a detour). Give each a distinct `link_id`
and route vehicles onto the one you want; visualisations fan parallel links out as
separate arcs so their vehicles never coincide.
