# Routing

A routing policy decides a vehicle's next link at a branching node. `RoutingPolicy`
is the protocol; `StaticRoutePolicy` (the default) follows each vehicle's own
`route`; `ShortestPathPolicy` plans routes on the live network graph, optionally
with a congestion-aware cost. See [Routing](../guide/routing.md).

::: mesoltm.routing.policy.RoutingPolicy

::: mesoltm.routing.policy.StaticRoutePolicy

::: mesoltm.routing.shortest_path.ShortestPathPolicy
