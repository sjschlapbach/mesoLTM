# Network

The `Network` builder is the high-level entry point: add nodes and links, mark
origins/destinations, then `compile()` to a runnable [`Simulation`](core.md#simulation).
`NetworkState` is the read-only-plus-mutation view that plugins and routing
policies see at run time. The convenience builders construct common topologies.
See [Building networks](../guide/building-networks.md).

## Network builder

::: mesoltm.network.network.Network

::: mesoltm.network.network.link_capacity

## Network state

`NetworkState` exposes topology, static link kinematics, and live per-step
quantities (occupancy, density, queues), plus the mutation seams used for
rerouting (`set_route`) and dynamic demand (`inject`).

::: mesoltm.network.state.NetworkState

::: mesoltm.network.state.VehicleView

## Builders

::: mesoltm.network.builders.grid_network

::: mesoltm.network.builders.corridor_network

::: mesoltm.network.builders.network_to_dict

::: mesoltm.network.builders.network_from_dict
