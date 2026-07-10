# Core

The core mesoscopic LTM: the road [links](#links) that carry the discrete
fundamental diagram, the [`Vehicle`](#vehicle) agent tracked individually through
the network, and the [`Simulation`](#simulation) engine that runs the four-phase
time loop. See [The Model](../model/overview.md) for the theory behind these
classes.

## Links

`Link` is the discrete-LTM road link (its demand/supply arithmetic is ported
verbatim from the reference). `BaseLink` is the interface all links implement, and
`ConnectorLink` is the auto-inserted, transparent one-cell buffer that attaches
origins/destinations to a general graph.

::: mesoltm.core.link.Link

::: mesoltm.core.base_link.BaseLink

::: mesoltm.core.connector_link.ConnectorLink

## Vehicle

Every unit of flow is one `Vehicle`. It carries its own mutable `route`, a
`position` pointer, a free-form `props` metadata dict, and an automatically
populated `trajectory`.

::: mesoltm.core.vehicle.Vehicle

## Simulation

`Simulation` runs the LTM over a set of links and nodes. Use `run()` for a batch
run, or `start()`/`step()` to drive the loop yourself and `inject()` vehicles
between steps.

::: mesoltm.core.simulation.Simulation

## Identifiers

A **link id** is always a plain `int`. A **node id** has no fixed type — it is any
hashable value you pass to [`Network.add_node`](network.md): `grid_network` labels
nodes with `(row, col)` integer tuples, `corridor_network` uses strings, and your own
code may use any scheme. The `mesoltm.NodeId` alias (defined in `mesoltm.core.ids`)
names that intentionally-general type wherever a node id flows through the API. In a
recorded [`SimulationHistory`](recording.md) ids round-trip through JSON, so a link id
there is `int | str` (an `int` while live, a `str` after loading).
