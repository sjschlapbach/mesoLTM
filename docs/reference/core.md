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
