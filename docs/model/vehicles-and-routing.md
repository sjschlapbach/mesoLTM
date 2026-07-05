# Vehicles & routing

In `mesoltm` every unit of node flow is one [`Vehicle`](../reference/core.md#vehicle).
This is the mesoscopic model's defining feature: the LTM's efficient link/node
arithmetic, but with individually tracked agents that carry their own routes and
records.

## The Vehicle object

```python
from mesoltm import Vehicle

v = Vehicle(
    vehicle_id=1,
    origin="n0",
    destination="n3",
    start=5.0,               # departure time in seconds
    route=[1, 2, 4],         # ordered link ids to traverse (optional)
    props={"vclass": "car"}, # free-form metadata (optional)
)
```

Key attributes:

| Attribute | Meaning |
|-----------|---------|
| `route` | Ordered list of `link_id`s the vehicle intends to traverse. **Mutable at any time** — rewriting it reroutes the vehicle at its next node. |
| `position` | Index of the current link within `route` (robust to routes that revisit a link). |
| `props` | Free-form `dict` of per-vehicle metadata. The core never reads it; plugins, `color_by`, and custom metrics do. Must be JSON-serialisable to survive the animation history round-trip. |
| `trajectory` | Auto-populated per-link log (`entry_step`, `exit_step`, `is_connector`) that per-vehicle [metrics](../guide/metrics.md) are derived from. |
| `end` | Arrival step, stamped by the destination node. |

!!! warning "Vehicles do not carry FD parameters"
    `v_f`, `w`, `rho_jam` describe the **road** (`Link`), not the vehicle. A
    `Vehicle` has no fundamental-diagram attributes.

## Routes are propagated, not imposed

The network never computes routes on its own — it simply moves each vehicle along
whatever `route` the vehicle currently holds. That single design choice is why
rerouting needs no special machinery: **rewrite `vehicle.route` and the vehicle is
rerouted** from its next node onward. A [plugin](../guide/plugins.md) or a
[routing policy](../guide/routing.md) does exactly this.

## Routing policies

At a branching node, *which* outbound link a vehicle takes is resolved by a
[`RoutingPolicy`](../reference/routing.md):

- **`StaticRoutePolicy`** (the default) reads the vehicle's own `route`. With this
  policy the model reproduces the paper's behaviour exactly.
- **`ShortestPathPolicy`** plans routes on the live network graph (via NetworkX),
  optionally with a congestion-aware `cost` callback and `dynamic=True` to re-plan
  as conditions change.
- **Your own** — any object implementing the `RoutingPolicy` protocol's
  `next_link(...)`.

Routing is entirely a layer *around* the flow arithmetic: it only chooses a
vehicle's next link and never alters demand, supply, or the merge/diverge
resolution. See [Deviations §A1](deviations-from-the-paper.md) and the
[Routing guide](../guide/routing.md) for details and examples.
