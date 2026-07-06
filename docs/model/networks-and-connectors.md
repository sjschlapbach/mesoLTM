# Networks & connector links

The paper attaches an origin or destination directly to a single link. To let
**any node of a general graph** act as an origin and/or destination — including
busy junctions with through traffic — the [`Network`](../reference/network.md)
builder inserts short **connector links** where needed. Understanding them
explains a few things you will see in outputs.

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
connector enters the network immediately once served. [Metrics](../guide/metrics.md)
attribute connector/queue time to a vehicle's **access time**, so reported
in-network travel time is unaffected by connectors.

## Why not zero-length connectors?

The design intent was zero-length connectors, but a **true zero-length link is
impossible in the LTM**: a link's storage is `rho_jam · length`, so a zero-length
link could never hold a vehicle. The connector is therefore the minimal faithful
approximation — a **one-cell** link that adds at most a one-step free-flow lag at
entry/exit.

The paper's own validation scenarios are built with **direct attachment** (no
connectors), so they remain bit-exact; connectors appear only when you use the
general-graph builder. See [Deviations §B1](deviations-from-the-paper.md).

## Parallel links

`Network` supports **parallel links** — two links sharing the same pair of
endpoints (a fast and a slow lane, or a detour). Give each a distinct `link_id`
and route vehicles onto the one you want; visualisations fan parallel links out as
separate arcs so their vehicles never coincide.
